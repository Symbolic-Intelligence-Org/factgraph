from __future__ import annotations

import json
import struct
from collections.abc import Mapping, Sequence
from typing import Any

from factgraph.application.explain.evidence_tree import (
    BOOLEAN_CERTAINTY,
    Certainty,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidencePolicyCondition,
    EvidenceRule,
    EvidenceTree,
    Holds,
    LAYOUT_TREE,
    PortRef,
    Source,
)
from factgraph.application.explain.prober import (
    ProbeEnv,
    _atom_form,
    _bake_repr_text,
    _repr_not_atom,
)
from factgraph.application.explain.structure_keys import atom_id_for_condition
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.store._support import binding_dict_from_items

from .evaluation_run_bundle_runtime import (
    _receipt_case_index,
    _validate_proof_receipt_bytes,
)
from .evaluation_run_verification_runtime import _materialize_evaluation_run_bundle_input
from .protocol.common import ProtocolShapeError
from .protocol.evaluation_run_bundle import (
    EvaluationRunBundleV0,
    EvaluationRunProjectionRowV0,
)
from .protocol.policy import PolicyConditionLoweredRefV0, PolicyLoweredRef
from .schema_runtime import build_schema_index


def evaluation_run_bundle_evidence(
    bundle: EvaluationRunBundleV0,
    *,
    row_capture_digest: str,
) -> EvidenceGraph:
    """Play back one captured positive row as detached, unverified engine evidence."""
    return _evaluation_run_bundle_evidence(
        bundle,
        row_capture_digest=row_capture_digest,
    )


def _evaluation_run_bundle_evidence(
    bundle: EvaluationRunBundleV0,
    *,
    row_capture_digest: str,
    source_meta_by_assertion: Mapping[str, Mapping[str, object]] | None = None,
    metadata_extra: Mapping[str, object] | None = None,
) -> EvidenceGraph:
    """Private source-aware receipt playback used by ScenarioRun.

    Public F4 callers continue through :func:`evaluation_run_bundle_evidence`
    and therefore retain their byte/API-compatible source vocabulary.  A
    ScenarioRun supplies a complete exact assertion inventory so a synthetic
    effective witness cannot be emitted as an ordinary ledger witness.
    """
    if not isinstance(row_capture_digest, str) or not row_capture_digest:
        raise ProtocolShapeError("row_capture_digest must be a non-empty string")
    where, relation, view = _materialize_evaluation_run_bundle_input(bundle)
    matches = tuple(row for row in bundle.rows if row.row_capture_digest == row_capture_digest)
    if not matches:
        raise ProtocolShapeError("EvaluationRun row_capture_digest was not found")
    if len(matches) != 1:
        raise ProtocolShapeError("EvaluationRun row_capture_digest is ambiguous")
    row = matches[0]
    receipt = _validate_proof_receipt_bytes(row.proof_receipt_bytes)
    branch_index = _receipt_case_index(receipt)
    branch_id = f"c{branch_index}"
    branch = _selected_branch(where, branch_index)
    binding = binding_dict_from_items(receipt.binding_items)
    envs = (ProbeEnv.from_bindings(binding),)
    schema_index = build_schema_index(json.loads(bundle.schema_bytes.decode("utf-8")))

    body_refs, condition_refs, unify_refs = _selected_lineage(bundle, branch_id)
    body_count = len(body_refs)
    policy_condition_count = len(condition_refs)
    query_binding_count = len(bundle.run_anchor.bindings)
    join_count = len(unify_refs)
    head_link_count = len(bundle.run_anchor.selections)
    if len(branch) != (
        body_count
        + policy_condition_count
        + query_binding_count
        + join_count
        + head_link_count
    ):
        raise ProtocolShapeError(
            "captured branch cannot be partitioned into Policy, Query, join, and head atoms"
        )

    witnesses = {item.pred_condition_key: item for item in receipt.pred_witnesses}
    steps = {item.step_key: item for item in receipt.non_fact_steps}
    relation_by_assertion = _relation_assertion_index(bundle)
    if source_meta_by_assertion is not None:
        if not isinstance(source_meta_by_assertion, Mapping) or set(
            source_meta_by_assertion
        ) != set(relation_by_assertion):
            raise ProtocolShapeError(
                "Scenario source metadata must exactly cover captured assertions"
            )
        if not all(isinstance(item, Mapping) for item in source_meta_by_assertion.values()):
            raise ProtocolShapeError("Scenario source metadata values must be mappings")
    if metadata_extra is not None and not isinstance(metadata_extra, Mapping):
        raise ProtocolShapeError("Scenario evidence metadata must be mapping or None")
    atom_condition_keys: list[tuple[str, str]] = []
    atoms_by_occurrence: dict[str, list[EvidenceAtom]] = {}
    policy_conditions: list[EvidencePolicyCondition] = []
    outside_atoms: list[EvidenceAtom] = []
    query_atom_ids: list[str] = []
    head_atom_ids: list[str] = []
    policy_condition_atom_ids: list[str] = []

    for index, atom in enumerate(branch):
        authored = body_refs.get(index)
        is_policy_condition = body_count <= index < body_count + policy_condition_count
        atom_id = atom_id_for_condition(
            branch_id,
            index,
            # Policy conditions are authored Policy leaves, unlike Query binds,
            # joins and projection-head links.  Keep their stable `atom` ids so
            # the exact lineage coordinate matches live Explain.
            materialized=authored is None and not is_policy_condition,
        )
        evidence, condition_key = _captured_atom_evidence(
            atom,
            index=index,
            branch_index=branch_index,
            atom_id=atom_id,
            envs=envs,
            view=view,
            schema_index=schema_index,
            witnesses=witnesses,
            steps=steps,
            relation_by_assertion=relation_by_assertion,
            bundle=bundle,
            row=row,
            source_meta_by_assertion=source_meta_by_assertion,
        )
        atom_condition_keys.append((atom_id, condition_key))
        if authored is not None:
            assert authored.occurrence_alias is not None
            atoms_by_occurrence.setdefault(authored.occurrence_alias, []).append(evidence)
        elif is_policy_condition:
            ref = condition_refs[index - body_count]
            if ref.lowered_index != index:
                raise ProtocolShapeError("Policy condition lineage does not match its branch coordinate")
            policy_conditions.append(
                EvidencePolicyCondition(
                    policy_node_id=ref.policy_node_id,
                    condition_id=ref.condition_id,
                    role=ref.role,
                    atom=evidence,
                )
            )
            policy_condition_atom_ids.append(atom_id)
        elif (
            body_count + policy_condition_count
            <= index
            < body_count + policy_condition_count + query_binding_count
        ):
            query_atom_ids.append(atom_id)
            outside_atoms.append(evidence)
        elif index >= body_count + policy_condition_count + query_binding_count + join_count:
            head_atom_ids.append(atom_id)
            outside_atoms.append(evidence)

    joins, join_condition_ids = _captured_joins(
        branch,
        branch_id=branch_id,
        branch_index=branch_index,
        body_count=body_count,
        policy_condition_count=policy_condition_count,
        query_binding_count=query_binding_count,
        refs=unify_refs,
        steps=steps,
    )
    rules = _body_rules(bundle, branch_id, atoms_by_occurrence)
    rules = (
        EvidenceRule(
            occurrence_alias=bundle.run_anchor.projection_head_id,
            rule_id=bundle.run_anchor.projection_head_id,
            role="head",
            status="holds",
            ports=_subject_binding(row),
            atoms=tuple(outside_atoms),
        ),
        *rules,
    )
    selected_anchor = bundle.run_anchor.row_anchors[row.ordinal]
    certainty = _certainty(row)
    outside_ids = tuple((*query_atom_ids, *head_atom_ids))
    metadata = {
        "evidence_mode": "detached_receipt_playback_v0",
        "logical_verification": "not_performed",
        "replay_verified": False,
        "integrity": bundle.integrity,
        "authenticity": bundle.authenticity,
        "bundle_digest": bundle.bundle_digest,
        "run_anchor_digest": bundle.run_anchor.anchor_digest,
        "target_digest": bundle.run_anchor.target.target_digest,
        "policy_digest": bundle.run_anchor.target.policy_digest,
        "policy_structure_digest": bundle.run_anchor.target.policy_structure.structure_digest,
        "query_digest": bundle.query_digest,
        "result_id": bundle.run_anchor.result_id,
        "result_digest": bundle.run_anchor.result_digest,
        "row_id": row.row_id,
        "claim_digest": row.claim_digest,
        "row_capture_digest": row.row_capture_digest,
        "semantic_row_anchor_digest": selected_anchor.semantic_anchor_digest,
        "proof_receipt_digest": row.proof_receipt_digest,
        "selected_branch_id": branch_id,
        "outside_policy_lineage_atom_ids": outside_ids,
        "policy_condition_atom_ids": tuple(policy_condition_atom_ids),
        "query_binding_atom_ids": tuple(query_atom_ids),
        "projection_head_link_atom_ids": tuple(head_atom_ids),
        "atom_condition_keys": tuple(atom_condition_keys),
        "non_fact_step_statuses": tuple(
            (item.step_key, item.kind, item.status) for item in receipt.non_fact_steps
        ),
        "join_condition_ids": tuple(join_condition_ids),
    }
    if metadata_extra is not None:
        overlap = set(metadata) & set(metadata_extra)
        if overlap:
            raise ProtocolShapeError(
                "Scenario evidence metadata must not override F4 metadata: "
                + ", ".join(sorted(overlap))
            )
        metadata.update(dict(metadata_extra))
    tree = EvidenceTree(
        tree_id=branch_id,
        status="holds",
        rules=rules,
        joins=joins,
        policy_conditions=tuple(policy_conditions),
        certainty=certainty,
        metadata=metadata,
    )
    return EvidenceGraph(
        graph_id=sha256_token(
            f"evaluation_run_bundle_evidence_v0\0{bundle.bundle_digest}\0{row.row_capture_digest}".encode()
        ),
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding=_subject_binding(row),
        paths=(tree,),
        certainty=certainty,
        metadata=metadata,
    )


def _selected_branch(where: list[Any], branch_index: int) -> list[tuple[Any, ...]]:
    if all(isinstance(item, tuple) for item in where):
        branches = (where,)
    elif all(isinstance(item, list) for item in where):
        branches = tuple(where)
    else:
        raise ProtocolShapeError("captured native plan branch shape is invalid")
    if branch_index >= len(branches):
        raise ProtocolShapeError("ProofReceipt selected branch is absent from the native plan")
    branch = branches[branch_index]
    if not branch or not all(isinstance(atom, tuple) and atom for atom in branch):
        raise ProtocolShapeError("captured native plan branch is malformed")
    return branch


def _selected_lineage(
    bundle: EvaluationRunBundleV0,
    branch_id: str,
) -> tuple[
    dict[int, PolicyLoweredRef],
    tuple[PolicyConditionLoweredRefV0, ...],
    tuple[PolicyLoweredRef, ...],
]:
    body: dict[int, PolicyLoweredRef] = {}
    unify: dict[int, PolicyLoweredRef] = {}
    conditions: dict[int, PolicyConditionLoweredRefV0] = {}
    for node in bundle.run_anchor.target.policy_lineage.authored_nodes:
        for ref in node.lowered_refs:
            if ref.branch_id != branch_id:
                continue
            if isinstance(ref, PolicyLoweredRef) and ref.kind == "body_atom":
                assert ref.lowered_index is not None
                if ref.lowered_index in body:
                    raise ProtocolShapeError("Policy lineage duplicates a body atom coordinate")
                body[ref.lowered_index] = ref
            elif isinstance(ref, PolicyLoweredRef) and ref.kind == "unify":
                assert ref.lowered_index is not None
                if ref.lowered_index in unify:
                    raise ProtocolShapeError("Policy lineage duplicates a Unify coordinate")
                unify[ref.lowered_index] = ref
            elif isinstance(ref, PolicyConditionLoweredRefV0):
                if ref.lowered_index in conditions:
                    raise ProtocolShapeError("Policy lineage duplicates a condition coordinate")
                conditions[ref.lowered_index] = ref
    if tuple(sorted(body)) != tuple(range(len(body))):
        raise ProtocolShapeError("Policy lineage body coordinates are not contiguous")
    expected_condition_indexes = tuple(range(len(body), len(body) + len(conditions)))
    if tuple(sorted(conditions)) != expected_condition_indexes:
        raise ProtocolShapeError("Policy condition lineage coordinates are not contiguous")
    if tuple(sorted(unify)) != tuple(range(len(unify))):
        raise ProtocolShapeError("Policy lineage Unify coordinates are not contiguous")
    return (
        body,
        tuple(conditions[index] for index in expected_condition_indexes),
        tuple(unify[index] for index in range(len(unify))),
    )


def _captured_atom_evidence(
    atom: tuple[Any, ...],
    *,
    index: int,
    branch_index: int,
    atom_id: str,
    envs: tuple[ProbeEnv, ...],
    view: dict[str, list[tuple[Any, ...]]],
    schema_index: object,
    witnesses: Mapping[str, Any],
    steps: Mapping[str, Any],
    relation_by_assertion: Mapping[str, tuple[str, tuple[tuple[str, object], ...]]],
    bundle: EvaluationRunBundleV0,
    row: EvaluationRunProjectionRowV0,
    source_meta_by_assertion: Mapping[str, Mapping[str, object]] | None,
) -> tuple[EvidenceAtom, str]:
    kind = str(atom[0])
    form = _atom_form(atom, envs)
    repr_text = (
        _repr_not_atom(atom, envs, schema_index, view_facts=view)
        if kind == "not"
        else _bake_repr_text(form, schema_index, view_facts=view)
    )
    support: tuple[Source, ...] = ()
    if kind == "pred":
        pred_id = str(atom[1])
        condition_key = f"c{branch_index}.c{index}:{pred_id}"
        witness = witnesses.get(condition_key)
        if witness is None:
            raise ProtocolShapeError("ProofReceipt is missing predicate evidence")
        sources: list[Source] = []
        for assertion_id in witness.asrt_ids:
            captured = relation_by_assertion.get(assertion_id)
            if captured is None or captured[0] != pred_id:
                raise ProtocolShapeError("ProofReceipt assertion does not match its predicate")
            base_meta: dict[str, object] = {
                "role": "captured_witness",
                "origin": "evaluation_run_bundle_v0",
                "predicate_id": pred_id,
                "pred_condition_key": condition_key,
                "assertion_id": assertion_id,
                "bundle_digest": bundle.bundle_digest,
                "row_capture_digest": row.row_capture_digest,
            }
            if source_meta_by_assertion is not None:
                supplied = dict(source_meta_by_assertion[assertion_id])
                overlap = set(base_meta) & set(supplied)
                # ScenarioRun is the only private caller allowed to replace
                # source classification.  It must still agree on the captured
                # predicate/assertion identities and cannot alter any bundle or
                # row binding metadata below.
                allowed = {"predicate_id", "assertion_id", "role", "origin"}
                if overlap - allowed:
                    raise ProtocolShapeError(
                        "Scenario source metadata overrides protected F4 source keys"
                    )
                identity_overlap = overlap & {"predicate_id", "assertion_id"}
                if any(supplied[key] != base_meta[key] for key in identity_overlap):
                    raise ProtocolShapeError("Scenario source metadata contradicts captured assertion")
                base_meta.update(supplied)
            sources.append(
                Source(
                    ref=assertion_id,
                    field=pred_id,
                    value=captured[1],
                    meta=base_meta,
                )
            )
        support = tuple(sources)
    else:
        condition_key = f"c{branch_index}.c{index}:{kind}"
        step = steps.get(condition_key)
        expected_status = "no_match" if kind == "not" else "satisfied"
        if step is None or step.kind != kind or step.status != expected_status:
            raise ProtocolShapeError("ProofReceipt non-fact step does not match native plan")
    return (
        EvidenceAtom(
            form=form,
            verdict=Holds(certainty=_certainty(row) or BOOLEAN_CERTAINTY, support=support),
            atom_id=atom_id,
            repr_text=repr_text,
            negated=kind == "not",
        ),
        condition_key,
    )


def _captured_joins(
    branch: Sequence[tuple[Any, ...]],
    *,
    branch_id: str,
    branch_index: int,
    body_count: int,
    policy_condition_count: int,
    query_binding_count: int,
    refs: tuple[PolicyLoweredRef, ...],
    steps: Mapping[str, Any],
) -> tuple[tuple[EvidenceJoin, ...], tuple[tuple[str, str], ...]]:
    joins: list[EvidenceJoin] = []
    keys: list[tuple[str, str]] = []
    offset = body_count + policy_condition_count + query_binding_count
    for ordinal, ref in enumerate(refs):
        index = offset + ordinal
        atom = branch[index]
        condition_key = f"c{branch_index}.c{index}:eq"
        step = steps.get(condition_key)
        if atom[0] != "eq" or step is None or step.kind != "eq" or step.status != "satisfied":
            raise ProtocolShapeError("captured Unify does not match its materialized equality")
        assert (
            ref.occurrence_alias is not None
            and ref.port_name is not None
            and ref.peer_occurrence_alias is not None
            and ref.peer_port_name is not None
        )
        join_id = (
            f"{branch_id}:{ref.occurrence_alias}.{ref.port_name}="
            f"{ref.peer_occurrence_alias}.{ref.peer_port_name}"
        )
        joins.append(
            EvidenceJoin(
                left=PortRef(ref.occurrence_alias, ref.port_name),
                right=PortRef(ref.peer_occurrence_alias, ref.peer_port_name),
                status="holds",
                join_id=join_id,
            )
        )
        keys.append((join_id, condition_key))
    return tuple(joins), tuple(keys)


def _body_rules(
    bundle: EvaluationRunBundleV0,
    branch_id: str,
    atoms: Mapping[str, list[EvidenceAtom]],
) -> tuple[EvidenceRule, ...]:
    pins = {pin.occurrence_alias: pin for pin in bundle.run_anchor.target.rule_pins}
    aliases = {
        ref.occurrence_alias
        for node in bundle.run_anchor.target.policy_lineage.authored_nodes
        for ref in node.lowered_refs
        if ref.branch_id == branch_id and ref.kind == "occurrence"
    }
    if None in aliases or not aliases:
        raise ProtocolShapeError("selected Policy branch has no occurrence lineage")
    rules: list[EvidenceRule] = []
    for alias in sorted(str(item) for item in aliases):
        authored_alias = _authored_alias(bundle, branch_id, alias)
        pin = pins.get(authored_alias)
        if pin is None:
            raise ProtocolShapeError("selected Policy occurrence has no Rule pin")
        occurrence_atoms = tuple(atoms.get(alias, ()))
        if not occurrence_atoms:
            raise ProtocolShapeError("selected Policy occurrence has no captured body evidence")
        rules.append(
            EvidenceRule(
                occurrence_alias=alias,
                rule_id=pin.rule_id,
                role="body",
                status="holds",
                atoms=occurrence_atoms,
            )
        )
    return tuple(rules)


def _authored_alias(bundle: EvaluationRunBundleV0, branch_id: str, lowered_alias: str) -> str:
    candidates: list[str] = []
    structure = {
        node.node_id: node
        for node in bundle.run_anchor.target.policy_structure.nodes
        if node.kind == "occurrence"
    }
    for lineage in bundle.run_anchor.target.policy_lineage.authored_nodes:
        node = structure.get(lineage.node_id)
        if node is None or node.occurrence_alias is None:
            continue
        if any(
            ref.kind == "occurrence"
            and ref.branch_id == branch_id
            and ref.occurrence_alias == lowered_alias
            for ref in lineage.lowered_refs
        ):
            candidates.append(node.occurrence_alias)
    if len(candidates) != 1:
        raise ProtocolShapeError("lowered Policy occurrence does not have one authored origin")
    return candidates[0]


def _relation_assertion_index(
    bundle: EvaluationRunBundleV0,
) -> dict[str, tuple[str, tuple[tuple[str, object], ...]]]:
    return {
        assertion_id: (
            relation.predicate_id,
            tuple((value.tag, value.value) for value in values),
        )
        for relation in bundle.relations
        for assertion_id, values in relation.facts
    }


def _subject_binding(row: EvaluationRunProjectionRowV0) -> dict[str, object]:
    return {
        alias: (
            {"kind": "entity_ref", "value": value.value}
            if value.tag == "entity_ref"
            else {"kind": "literal", "tag": value.tag, "value": value.value}
        )
        for alias, value in row.values
    }


def _certainty(row: EvaluationRunProjectionRowV0) -> Certainty | None:
    if row.certainty is None:
        return None
    lo, hi, kind = row.certainty
    return Certainty(_float64(lo), _float64(hi), kind)  # type: ignore[arg-type]


def _float64(value: str) -> float:
    return struct.unpack(">d", int(value, 16).to_bytes(8, "big"))[0]


__all__ = ["evaluation_run_bundle_evidence"]
