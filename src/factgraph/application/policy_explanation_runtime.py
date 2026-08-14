from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Literal, cast

from .explain.evidence_tree import (
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidencePolicyCondition,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fails,
    Holds,
    NotReached,
    Source,
)
from .protocol.evaluation_run import EvaluationRunAnchorV0
from .protocol.policy import (
    PolicyCompareStructureNodeV0,
    PolicyConditionLoweredRefV0,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLoweredRef,
    PolicyNodeLineage,
    PolicyStructureV0,
    PolicyStructureNode,
    PolicyStructureNodeV0,
)
from .protocol.policy_explanation import (
    PolicyBranchEvaluationV0,
    PolicyBranchParticipation,
    PolicyEvaluationProjectionV0,
    PolicyEvidenceLocatorV0,
    PolicyExplanationProjectionError,
    PolicyExplanationState,
    PolicyExplanationViewV0,
    PolicyNodeBranchStateV0,
    PolicyNodeEvaluationV0,
    PolicyNodeProvenanceV0,
    PolicyProvenanceIndexV0,
)
from .protocol.semantic_address import SemanticPortAddress

_TreeState = Literal["holds", "fails", "not_reached"]
_EvidenceKey = tuple[str, Literal["atom", "join", "condition"], str]


@dataclass(frozen=True)
class _AtomRecord:
    rule: EvidenceRule
    atom: EvidenceAtom
    locator: PolicyEvidenceLocatorV0


@dataclass(frozen=True)
class _JoinRecord:
    join: EvidenceJoin
    locator: PolicyEvidenceLocatorV0


@dataclass(frozen=True)
class _ConditionRecord:
    condition: EvidencePolicyCondition
    locator: PolicyEvidenceLocatorV0


@dataclass(frozen=True)
class _TreeIndex:
    tree: EvidenceTree
    body_rules: dict[str, EvidenceRule]
    atoms: dict[str, _AtomRecord]
    joins: dict[str, _JoinRecord]
    conditions: dict[str, _ConditionRecord]


def project_policy_explanation_v0(
    run_anchor: EvaluationRunAnchorV0,
    evidence: EvidenceGraph,
    *,
    semantic_row_anchor_digest: str,
) -> PolicyExplanationViewV0:
    """Project inner engine evidence onto the immutable authored Policy tree.

    The projection consumes exact ``PolicyLineage`` coordinates. It never parses
    generated aliases, never treats Query/head materialization as authored Policy,
    and returns no partial view when any represented branch is ambiguous.
    """
    _validate_inputs(run_anchor, evidence, semantic_row_anchor_digest)
    target = run_anchor.target
    evaluation, provenance = _project_policy_evidence_core(
        structure=target.policy_structure,
        lineage=target.policy_lineage,
        rule_pins=target.rule_pins,
        evidence=evidence,
    )
    return PolicyExplanationViewV0(
        run_anchor_digest=run_anchor.anchor_digest,
        semantic_row_anchor_digest=semantic_row_anchor_digest,
        query_digest=run_anchor.query_digest,
        policy_id=target.normalized_policy_id,
        policy_version=target.normalized_policy_version,
        policy_digest=target.policy_digest,
        structure_digest=target.policy_structure.structure_digest,
        evidence_graph_id=evidence.graph_id,
        structure=target.policy_structure,
        evaluation=evaluation,
        provenance=provenance,
        interpretation="logical_policy_evidence_not_authorization",
    )


def project_policy_evidence_v1(
    *,
    structure: PolicyStructureV0,
    lineage: PolicyLineage,
    rule_pins: tuple[object, ...],
    evidence: EvidenceGraph,
) -> tuple[PolicyEvaluationProjectionV0, PolicyProvenanceIndexV0]:
    """Project sealed V1 native evidence without manufacturing a V0 Run anchor.

    V1 runs have their own query/result/replay identities, so they must not be
    coerced into :class:`EvaluationRunAnchorV0` merely to reuse the authored
    Policy projection algorithm.  The shared core consumes only the invariant
    mapping authority: immutable authored structure, total compiler lineage,
    occurrence Rule pins and one tree-shaped EvidenceGraph.
    """

    if not isinstance(structure, PolicyStructureV0) or not isinstance(lineage, PolicyLineage):
        raise _projection_error(
            "POLICY_STRUCTURE_LINEAGE_MISMATCH",
            "V1 Policy projection requires a sealed Policy structure and lineage",
        )
    if not isinstance(rule_pins, tuple) or not rule_pins:
        raise _projection_error(
            "POLICY_RULE_IDENTITY_MISMATCH",
            "V1 Policy projection requires non-empty Rule pins",
        )
    if not isinstance(evidence, EvidenceGraph) or not evidence.graph_id:
        raise _projection_error("INVALID_EVIDENCE_GRAPH", "V1 inner EvidenceGraph is invalid")
    if evidence.layout_hint != "tree" or not evidence.paths:
        raise _projection_error(
            "UNSUPPORTED_EVIDENCE_LAYOUT",
            "V1 Policy projection requires one or more EvidenceTree paths",
        )
    return _project_policy_evidence_core(
        structure=structure,
        lineage=lineage,
        rule_pins=rule_pins,
        evidence=evidence,
    )


def _project_policy_evidence_core(
    *,
    structure: PolicyStructureV0,
    lineage: PolicyLineage,
    rule_pins: tuple[object, ...],
    evidence: EvidenceGraph,
) -> tuple[PolicyEvaluationProjectionV0, PolicyProvenanceIndexV0]:
    """Common lineage-total Policy projection for V0 and V1 outer run contracts."""

    structure_by_id = {node.node_id: node for node in structure.nodes}
    lineage_by_id = {node.node_id: node for node in lineage.authored_nodes}
    if set(structure_by_id) != set(lineage_by_id):
        raise _projection_error(
            "POLICY_STRUCTURE_LINEAGE_MISMATCH",
            "Policy structure and lineage do not cover the same authored nodes",
        )

    all_branch_ids = _lineage_branch_ids(lineage_by_id.values())
    indexes = _evidence_indexes(evidence, allowed_branch_ids=all_branch_ids)
    projected_branch_ids = tuple(sorted(indexes))
    rule_pin_by_alias_raw = {getattr(pin, "occurrence_alias", None): pin for pin in rule_pins}
    if None in rule_pin_by_alias_raw or len(rule_pin_by_alias_raw) != len(rule_pins):
        raise _projection_error(
            "POLICY_RULE_IDENTITY_MISMATCH",
            "Policy Rule pins have invalid or duplicate occurrence aliases",
        )
    rule_pin_by_alias = cast(Mapping[str, object], rule_pin_by_alias_raw)
    direct_locators: dict[str, list[PolicyEvidenceLocatorV0]] = {
        node_id: [] for node_id in structure_by_id
    }
    mapped_evidence: set[_EvidenceKey] = set()
    states_by_node: dict[str, dict[str, PolicyExplanationState]] = {
        node_id: {} for node_id in structure_by_id
    }

    for branch_id in projected_branch_ids:
        index = indexes[branch_id]
        for node_id, node in structure_by_id.items():
            lineage_node = lineage_by_id[node_id]
            if node.kind != lineage_node.node_kind:
                raise _projection_error(
                    "POLICY_STRUCTURE_LINEAGE_MISMATCH",
                    f"Policy node {node_id!r} kind disagrees with lineage",
                )
            if node.kind == "occurrence":
                state, locators = _project_occurrence(
                    branch_id,
                    node,
                    lineage_node,
                    index,
                    rule_pin_by_alias,
                )
                states_by_node[node_id][branch_id] = state
                direct_locators[node_id].extend(locators)
                _mark_mapped(mapped_evidence, locators)
            elif node.kind == "unify":
                state, locators = _project_unify(branch_id, lineage_node, index)
                states_by_node[node_id][branch_id] = state
                direct_locators[node_id].extend(locators)
                _mark_mapped(mapped_evidence, locators)
            elif node.kind == "compare":
                if not isinstance(node, PolicyCompareStructureNodeV0):
                    raise _projection_error(
                        "POLICY_STRUCTURE_LINEAGE_MISMATCH",
                        f"Compare node {node_id!r} has an invalid persisted structure shape",
                    )
                state, locators = _project_compare(branch_id, node, lineage_node, index)
                states_by_node[node_id][branch_id] = state
                direct_locators[node_id].extend(locators)
                _mark_mapped(mapped_evidence, locators)

        memo: dict[str, PolicyExplanationState] = {}
        for node_id in structure_by_id:
            _project_structural_state(
                node_id,
                branch_id,
                structure_by_id,
                lineage_by_id,
                states_by_node,
                memo,
                active=set(),
            )

    branch_evaluations: list[PolicyBranchEvaluationV0] = []
    root_node_id = structure.root_node_id
    for branch_id in projected_branch_ids:
        root_state = states_by_node[root_node_id][branch_id]
        if root_state not in {"holds", "fails", "not_reached"}:
            raise _projection_error(
                "POLICY_ROOT_MAPPING_INCOMPLETE",
                f"Policy root has no determinate state for branch {branch_id!r}",
            )
        root_tree_state = cast(_TreeState, root_state)
        path_state = indexes[branch_id].tree.status
        if path_state == "holds" and root_tree_state != "holds":
            raise _projection_error(
                "POLICY_EVIDENCE_CONTRADICTION",
                f"Holding engine path {branch_id!r} has a non-holding Policy root",
            )
        participation = _participation(root_tree_state, path_state)
        branch_evaluations.append(
            PolicyBranchEvaluationV0(branch_id, root_tree_state, path_state, participation)
        )
    if not any(item.participation == "contributes" for item in branch_evaluations):
        raise _projection_error(
            "POSITIVE_ROW_HAS_NO_HOLDING_POLICY_PATH",
            "A positive row requires at least one holding Policy and engine path",
        )

    node_evaluations = tuple(
        PolicyNodeEvaluationV0(
            node_id=node.node_id,
            kind=node.kind,
            state=_aggregate_node_state(
                node.node_id,
                structure.root_node_id,
                states_by_node[node.node_id],
            ),
            branch_states=tuple(
                PolicyNodeBranchStateV0(branch_id, states_by_node[node.node_id][branch_id])
                for branch_id in projected_branch_ids
            ),
        )
        for node in structure.nodes
    )
    evaluation = PolicyEvaluationProjectionV0(
        root_node_id=root_node_id,
        root_state=next(item.state for item in node_evaluations if item.node_id == root_node_id),
        nodes=node_evaluations,
        branches=tuple(branch_evaluations),
    )

    all_evidence = {
        _locator_key(locator): locator
        for index in indexes.values()
        for locator in (
            *(record.locator for record in index.atoms.values()),
            *(record.locator for record in index.joins.values()),
            *(record.locator for record in index.conditions.values()),
        )
    }
    if not mapped_evidence <= set(all_evidence):
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            "Mapped Policy evidence is absent from the inner graph",
        )
    provenance = PolicyProvenanceIndexV0(
        node_evidence=tuple(
            PolicyNodeProvenanceV0(
                node.node_id,
                tuple(sorted(direct_locators[node.node_id], key=_protocol_locator_key)),
            )
            for node in structure.nodes
        ),
        outside_policy_lineage=tuple(
            sorted(
                (locator for key, locator in all_evidence.items() if key not in mapped_evidence),
                key=_protocol_locator_key,
            )
        ),
        coverage="lineage_total_for_projected_branches",
        source_identity="inner_evidence_source_refs",
        authenticity="unverified",
    )
    return evaluation, provenance


def _validate_inputs(
    run_anchor: EvaluationRunAnchorV0,
    evidence: EvidenceGraph,
    semantic_row_anchor_digest: str,
) -> None:
    if not isinstance(run_anchor, EvaluationRunAnchorV0):
        raise _projection_error("INVALID_RUN_ANCHOR", "run_anchor must be EvaluationRunAnchorV0")
    try:
        replace(run_anchor)
    except Exception as exc:
        raise _projection_error(
            "INVALID_RUN_ANCHOR", "run_anchor failed its integrity seal"
        ) from exc
    if run_anchor.summary.row_count == 0:
        raise _projection_error(
            "ZERO_ROW_HAS_NO_POLICY_VIEW",
            "A zero-row run does not assert false and has no Policy explanation view",
        )
    matches = tuple(
        row
        for row in run_anchor.row_anchors
        if row.semantic_anchor_digest == semantic_row_anchor_digest
    )
    if not matches:
        raise _projection_error(
            "SEMANTIC_ROW_ANCHOR_NOT_FOUND",
            "semantic_row_anchor_digest does not belong to the EvaluationRun",
        )
    if not isinstance(evidence, EvidenceGraph):
        raise _projection_error("INVALID_EVIDENCE_GRAPH", "evidence must be EvidenceGraph")
    if not isinstance(evidence.graph_id, str) or not evidence.graph_id:
        raise _projection_error("INVALID_EVIDENCE_GRAPH", "EvidenceGraph.graph_id is invalid")
    selected = tuple(row for row in matches if row.row_id == evidence.metadata.get("row_id"))
    if len(selected) != 1:
        raise _projection_error(
            "EVIDENCE_ROW_ANCHOR_MISMATCH",
            "EvidenceGraph row_id does not uniquely select the semantic Run row",
        )
    selected_row = selected[0]
    if evidence.engine != run_anchor.execution_profile.engine:
        raise _projection_error(
            "EVIDENCE_ENGINE_MISMATCH",
            "EvidenceGraph engine does not match the EvaluationRun",
        )
    expected_metadata = {
        "result_id": run_anchor.result_id,
        "row_id": selected_row.row_id,
        "claim_digest": selected_row.claim_digest,
    }
    for key, expected in expected_metadata.items():
        if evidence.metadata.get(key) != expected:
            raise _projection_error(
                "EVIDENCE_ROW_ANCHOR_MISMATCH",
                f"EvidenceGraph metadata {key!r} does not match the selected Run row",
            )
    semantic_metadata = evidence.metadata.get("semantic_row_anchor_digest")
    if semantic_metadata is not None and semantic_metadata != semantic_row_anchor_digest:
        raise _projection_error(
            "EVIDENCE_ROW_ANCHOR_MISMATCH",
            "EvidenceGraph semantic row anchor does not match the selected Run row",
        )
    if evidence.layout_hint != "tree" or not evidence.paths:
        raise _projection_error(
            "UNSUPPORTED_EVIDENCE_LAYOUT",
            "Policy projection requires one or more EvidenceTree paths",
        )


def _lineage_branch_ids(nodes: Iterable[PolicyNodeLineage]) -> set[str]:
    branch_ids: set[str] = set()
    for node in nodes:
        for ref in node.lowered_refs:
            branch_ids.add(ref.branch_id)
    if not branch_ids:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            "Policy lineage has no lowered branches",
        )
    return branch_ids


def _evidence_indexes(
    evidence: EvidenceGraph,
    *,
    allowed_branch_ids: set[str],
) -> dict[str, _TreeIndex]:
    indexes: dict[str, _TreeIndex] = {}
    for path in evidence.paths:
        if isinstance(path, EvidenceTimeline) or not isinstance(path, EvidenceTree):
            raise _projection_error(
                "UNSUPPORTED_EVIDENCE_LAYOUT",
                "Policy projection does not accept EvidenceTimeline paths",
            )
        branch_id = path.tree_id
        if branch_id not in allowed_branch_ids:
            raise _projection_error(
                "UNKNOWN_EVIDENCE_BRANCH",
                f"Evidence branch {branch_id!r} is absent from Policy lineage",
            )
        if branch_id in indexes:
            raise _projection_error(
                "DUPLICATE_EVIDENCE_BRANCH",
                f"Evidence branch {branch_id!r} occurs more than once",
            )
        if path.status not in {"holds", "fails", "not_reached"}:
            raise _projection_error(
                "INVALID_EVIDENCE_STATUS",
                f"Evidence branch {branch_id!r} has invalid status",
            )
        indexes[branch_id] = _index_tree(path)
    return indexes


def _index_tree(tree: EvidenceTree) -> _TreeIndex:
    body_rules: dict[str, EvidenceRule] = {}
    atoms: dict[str, _AtomRecord] = {}
    joins: dict[str, _JoinRecord] = {}
    conditions: dict[str, _ConditionRecord] = {}
    for rule in tree.rules:
        if not isinstance(rule, EvidenceRule) or rule.role not in {"head", "body"}:
            raise _projection_error(
                "INVALID_EVIDENCE_SHAPE",
                f"Branch {tree.tree_id!r} has an invalid rule",
            )
        if rule.status not in {"holds", "fails", "not_reached"}:
            raise _projection_error(
                "INVALID_EVIDENCE_STATUS",
                f"Rule {rule.occurrence_alias!r} has invalid status",
            )
        if rule.role == "body":
            if rule.occurrence_alias in body_rules:
                raise _projection_error(
                    "DUPLICATE_EVIDENCE_COORDINATE",
                    f"Body occurrence {rule.occurrence_alias!r} occurs more than once",
                )
            body_rules[rule.occurrence_alias] = rule
        for atom in rule.atoms:
            if (
                not isinstance(atom, EvidenceAtom)
                or not isinstance(atom.atom_id, str)
                or not atom.atom_id
            ):
                raise _projection_error("INVALID_EVIDENCE_SHAPE", "Evidence atom is invalid")
            if atom.atom_id in atoms:
                raise _projection_error(
                    "DUPLICATE_EVIDENCE_COORDINATE",
                    f"Evidence atom {atom.atom_id!r} occurs more than once",
                )
            locator = PolicyEvidenceLocatorV0(
                branch_id=tree.tree_id,
                evidence_kind="atom",
                evidence_id=atom.atom_id,
                status=_verdict_state(atom),
                occurrence_alias=rule.occurrence_alias,
                source_refs=_source_refs(atom),
            )
            atoms[atom.atom_id] = _AtomRecord(rule, atom, locator)
    for join in tree.joins:
        if (
            not isinstance(join, EvidenceJoin)
            or not isinstance(join.join_id, str)
            or not join.join_id
        ):
            raise _projection_error("INVALID_EVIDENCE_SHAPE", "Evidence join is invalid")
        if join.join_id in joins:
            raise _projection_error(
                "DUPLICATE_EVIDENCE_COORDINATE",
                f"Evidence join {join.join_id!r} occurs more than once",
            )
        if join.status not in {"holds", "fails", "not_reached"}:
            raise _projection_error("INVALID_EVIDENCE_STATUS", "Evidence join status is invalid")
        left = SemanticPortAddress(join.left.rule_occurrence_alias, join.left.port_name)
        right = SemanticPortAddress(join.right.rule_occurrence_alias, join.right.port_name)
        joins[join.join_id] = _JoinRecord(
            join,
            PolicyEvidenceLocatorV0(
                branch_id=tree.tree_id,
                evidence_kind="join",
                evidence_id=join.join_id,
                status=join.status,
                left=left,
                right=right,
            ),
        )
    for condition in tree.policy_conditions:
        if not isinstance(condition, EvidencePolicyCondition):
            raise _projection_error(
                "INVALID_EVIDENCE_SHAPE", "Policy condition evidence is invalid"
            )
        atom = condition.atom
        if not isinstance(atom.atom_id, str) or not atom.atom_id:
            raise _projection_error("INVALID_EVIDENCE_SHAPE", "Policy condition atom id is invalid")
        if atom.atom_id in conditions or atom.atom_id in atoms:
            raise _projection_error(
                "DUPLICATE_EVIDENCE_COORDINATE",
                f"Policy condition atom {atom.atom_id!r} overlaps another evidence atom",
            )
        conditions[atom.atom_id] = _ConditionRecord(
            condition,
            PolicyEvidenceLocatorV0(
                branch_id=tree.tree_id,
                evidence_kind="condition",
                evidence_id=atom.atom_id,
                status=_verdict_state(atom),
                policy_node_id=condition.policy_node_id,
                condition_id=condition.condition_id,
                condition_role=condition.role,
                source_refs=_source_refs(atom),
            ),
        )
    return _TreeIndex(tree, body_rules, atoms, joins, conditions)


def _project_occurrence(
    branch_id: str,
    node: PolicyStructureNodeV0,
    lineage: PolicyNodeLineage,
    index: _TreeIndex,
    rule_pin_by_alias: Mapping[str, object],
) -> tuple[PolicyExplanationState, tuple[PolicyEvidenceLocatorV0, ...]]:
    branch_refs = _legacy_refs(lineage, branch_id, "branch")
    occurrence_refs = _legacy_refs(lineage, branch_id, "occurrence")
    body_refs = _legacy_refs(lineage, branch_id, "body_atom")
    if not branch_refs:
        if occurrence_refs or body_refs:
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                f"Occurrence {node.node_id!r} has partial lineage in {branch_id!r}",
            )
        return "not_applicable", ()
    if len(branch_refs) != 1 or len(occurrence_refs) != 1 or not body_refs:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Occurrence {node.node_id!r} lacks total lineage in {branch_id!r}",
        )
    lowered_alias = occurrence_refs[0].occurrence_alias
    assert lowered_alias is not None and node.occurrence_alias is not None
    if any(ref.occurrence_alias != lowered_alias for ref in body_refs):
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Occurrence {node.node_id!r} body lineage aliases disagree",
        )
    body_rule = index.body_rules.get(lowered_alias)
    if body_rule is None:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Evidence has no body occurrence {lowered_alias!r} in {branch_id!r}",
        )
    pin = rule_pin_by_alias.get(node.occurrence_alias)
    if pin is None or body_rule.rule_id != getattr(pin, "rule_id", None):
        raise _projection_error(
            "POLICY_RULE_IDENTITY_MISMATCH",
            f"Evidence body occurrence {lowered_alias!r} has the wrong Rule identity",
        )
    lowered_indexes = tuple(ref.lowered_index for ref in body_refs)
    source_indexes = tuple(ref.source_index for ref in body_refs)
    if (
        any(value is None for value in lowered_indexes + source_indexes)
        or len(set(lowered_indexes)) != len(lowered_indexes)
        or tuple(sorted(cast(tuple[int, ...], source_indexes))) != tuple(range(len(source_indexes)))
    ):
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Occurrence {node.node_id!r} body indexes are not total",
        )
    declared_rule_state = _fold_all([_verdict_state(atom) for atom in body_rule.atoms])
    if body_rule.status != declared_rule_state:
        raise _projection_error(
            "POLICY_EVIDENCE_CONTRADICTION",
            f"Evidence body occurrence {lowered_alias!r} status disagrees with its atoms",
        )
    locators: list[PolicyEvidenceLocatorV0] = []
    statuses: list[_TreeState] = []
    for ref in body_refs:
        assert ref.lowered_index is not None
        expected_atom_id = f"{branch_id}:atom:{ref.lowered_index}"
        record = index.atoms.get(expected_atom_id)
        if (
            record is None
            or record.rule.role != "body"
            or record.rule.occurrence_alias != lowered_alias
        ):
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                f"Authored atom {expected_atom_id!r} is missing or ambiguously owned",
            )
        statuses.append(record.locator.status)
        locators.append(record.locator)
    atom_state = _fold_all(statuses)
    if body_rule.status != atom_state:
        raise _projection_error(
            "POLICY_EVIDENCE_CONTRADICTION",
            f"Evidence body occurrence {lowered_alias!r} has non-lineage atoms that change its state",
        )
    return atom_state, tuple(locators)


def _project_unify(
    branch_id: str,
    lineage: PolicyNodeLineage,
    index: _TreeIndex,
) -> tuple[PolicyExplanationState, tuple[PolicyEvidenceLocatorV0, ...]]:
    refs = _legacy_refs(lineage, branch_id, "unify")
    if not refs:
        return "not_applicable", ()
    if len(refs) != 1:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_AMBIGUOUS",
            f"Unify {lineage.node_id!r} has multiple mappings in {branch_id!r}",
        )
    ref = refs[0]
    assert (
        ref.occurrence_alias is not None
        and ref.port_name is not None
        and ref.peer_occurrence_alias is not None
        and ref.peer_port_name is not None
    )
    expected_id = (
        f"{branch_id}:{ref.occurrence_alias}.{ref.port_name}="
        f"{ref.peer_occurrence_alias}.{ref.peer_port_name}"
    )
    record = index.joins.get(expected_id)
    if record is None:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Authored Unify evidence {expected_id!r} is missing",
        )
    join = record.join
    actual = (
        join.left.rule_occurrence_alias,
        join.left.port_name,
        join.right.rule_occurrence_alias,
        join.right.port_name,
    )
    expected = (
        ref.occurrence_alias,
        ref.port_name,
        ref.peer_occurrence_alias,
        ref.peer_port_name,
    )
    if actual != expected:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Authored Unify evidence {expected_id!r} has mismatched endpoints",
        )
    return record.locator.status, (record.locator,)


def _project_compare(
    branch_id: str,
    node: PolicyCompareStructureNodeV0,
    lineage: PolicyNodeLineage,
    index: _TreeIndex,
) -> tuple[PolicyExplanationState, tuple[PolicyEvidenceLocatorV0, ...]]:
    """Project exact compiler-owned lookup/compare evidence to one compare leaf."""

    condition_refs = _condition_refs(lineage, branch_id)
    # Compare is deliberately not assigned a coarse ``branch`` lineage ref.
    # Its compiler-owned condition refs are both its precise branch membership
    # and its atom coordinates.  Requiring a legacy branch ref here would turn
    # a fully materialized direct comparison into a false ``not_applicable``.
    if not condition_refs:
        return "not_applicable", ()
    branch_refs = _legacy_refs(lineage, branch_id, "branch")
    if len(branch_refs) > 1:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Compare {node.node_id!r} has ambiguous legacy branch lineage in {branch_id!r}",
        )
    if any(ref.policy_node_id != node.node_id for ref in condition_refs):
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Compare {node.node_id!r} condition lineage names another Policy node",
        )

    expected_roles = {"compare"}
    if isinstance(node.left, PolicyFieldNavigation):
        expected_roles.add("left_field")
    if isinstance(node.right, PolicyFieldNavigation):
        expected_roles.add("right_field")
    refs_by_role = {ref.role: ref for ref in condition_refs}
    if len(refs_by_role) != len(condition_refs) or set(refs_by_role) != expected_roles:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            f"Compare {node.node_id!r} condition roles are incomplete or ambiguous",
        )

    locators: list[PolicyEvidenceLocatorV0] = []
    statuses: list[_TreeState] = []
    for role in ("left_field", "right_field", "compare"):
        ref = refs_by_role.get(role)
        if ref is None:
            continue
        expected_atom_id = f"{branch_id}:atom:{ref.lowered_index}"
        record = index.conditions.get(expected_atom_id)
        if record is None:
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                f"Policy condition {expected_atom_id!r} is missing from EvidenceTree",
            )
        locator = record.locator
        if (
            locator.policy_node_id != node.node_id
            or locator.condition_id != ref.condition_id
            or locator.condition_role != ref.role
        ):
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                f"Policy condition {expected_atom_id!r} has mismatched authored coordinates",
            )
        statuses.append(locator.status)
        locators.append(locator)
    return _fold_all(statuses), tuple(locators)


def _project_structural_state(
    node_id: str,
    branch_id: str,
    structure_by_id: dict[str, PolicyStructureNode],
    lineage_by_id: dict[str, PolicyNodeLineage],
    states_by_node: dict[str, dict[str, PolicyExplanationState]],
    memo: dict[str, PolicyExplanationState],
    *,
    active: set[str],
) -> PolicyExplanationState:
    if node_id in memo:
        return memo[node_id]
    if node_id in active:
        raise _projection_error("INVALID_POLICY_STRUCTURE", "Policy structure contains a cycle")
    node = structure_by_id[node_id]
    if node.kind in {"occurrence", "unify", "compare"}:
        state = states_by_node[node_id].get(branch_id)
        if state is None:
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                f"Leaf Policy node {node_id!r} was not projected",
            )
        memo[node_id] = state
        return state
    active.add(node_id)
    applicable = bool(_legacy_refs(lineage_by_id[node_id], branch_id, "branch"))
    if not applicable:
        state = "not_applicable"
    else:
        child_states = tuple(
            _project_structural_state(
                child_id,
                branch_id,
                structure_by_id,
                lineage_by_id,
                states_by_node,
                memo,
                active=active,
            )
            for child_id in node.child_node_ids
        )
        applicable_children = tuple(item for item in child_states if item != "not_applicable")
        if node.kind == "all":
            if len(applicable_children) != len(child_states) or not applicable_children:
                raise _projection_error(
                    "POLICY_LINEAGE_MAPPING_INCOMPLETE",
                    f"Policy All node {node_id!r} has a partial branch mapping",
                )
            state = _fold_all(cast(tuple[_TreeState, ...], applicable_children))
        else:
            if len(applicable_children) != 1:
                raise _projection_error(
                    "POLICY_LINEAGE_MAPPING_AMBIGUOUS",
                    f"Policy Any node {node_id!r} must select exactly one child per branch",
                )
            state = applicable_children[0]
    active.remove(node_id)
    memo[node_id] = state
    states_by_node[node_id][branch_id] = state
    return state


def _legacy_refs(
    lineage: PolicyNodeLineage,
    branch_id: str,
    kind: str,
) -> tuple[PolicyLoweredRef, ...]:
    return tuple(
        ref
        for ref in lineage.lowered_refs
        if isinstance(ref, PolicyLoweredRef) and ref.branch_id == branch_id and ref.kind == kind
    )


def _condition_refs(
    lineage: PolicyNodeLineage,
    branch_id: str,
) -> tuple[PolicyConditionLoweredRefV0, ...]:
    return tuple(
        ref
        for ref in lineage.lowered_refs
        if isinstance(ref, PolicyConditionLoweredRefV0) and ref.branch_id == branch_id
    )


def _fold_all(states: tuple[_TreeState, ...] | list[_TreeState]) -> _TreeState:
    if not states:
        raise _projection_error(
            "POLICY_LINEAGE_MAPPING_INCOMPLETE",
            "Cannot fold an empty Policy conjunction",
        )
    if any(state == "fails" for state in states):
        return "fails"
    if any(state == "not_reached" for state in states):
        return "not_reached"
    return "holds"


def _aggregate_node_state(
    node_id: str,
    root_node_id: str,
    branch_states: dict[str, PolicyExplanationState],
) -> PolicyExplanationState:
    applicable = tuple(state for state in branch_states.values() if state != "not_applicable")
    if not applicable:
        return "not_applicable"
    if node_id == root_node_id:
        if "holds" in applicable:
            return "holds"
        if all(state == "fails" for state in applicable):
            return "fails"
        if all(state == "not_reached" for state in applicable):
            return "not_reached"
        return "indeterminate"
    if len(set(applicable)) == 1:
        return applicable[0]
    return "indeterminate"


def _participation(root: _TreeState, path: _TreeState) -> PolicyBranchParticipation:
    if root == "holds" and path == "holds":
        return "contributes"
    if root == "holds":
        return "outside_policy_filtered"
    if root == "fails":
        return "policy_failed"
    if root == "not_reached":
        return "blocked"
    return "unknown"


def _verdict_state(atom: EvidenceAtom) -> _TreeState:
    if isinstance(atom.verdict, Holds):
        return "holds"
    if isinstance(atom.verdict, Fails):
        return "fails"
    if isinstance(atom.verdict, NotReached):
        return "not_reached"
    raise _projection_error("INVALID_EVIDENCE_STATUS", "Evidence atom verdict is invalid")


def _source_refs(atom: EvidenceAtom) -> tuple[str, ...]:
    verdict = atom.verdict
    support = verdict.support if isinstance(verdict, (Holds, Fails)) else ()
    refs: list[str] = []
    for source in support:
        if not isinstance(source, Source) or not isinstance(source.ref, str) or not source.ref:
            raise _projection_error("INVALID_EVIDENCE_SOURCE", "Evidence source ref is invalid")
        refs.append(source.ref)
    return tuple(sorted(set(refs)))


def _mark_mapped(
    mapped: set[_EvidenceKey],
    locators: tuple[PolicyEvidenceLocatorV0, ...],
) -> None:
    for locator in locators:
        key = _locator_key(locator)
        if key in mapped:
            raise _projection_error(
                "POLICY_LINEAGE_MAPPING_AMBIGUOUS",
                f"Evidence coordinate {locator.evidence_id!r} maps to multiple Policy nodes",
            )
        mapped.add(key)


def _locator_key(locator: PolicyEvidenceLocatorV0) -> _EvidenceKey:
    return locator.branch_id, locator.evidence_kind, locator.evidence_id


def _protocol_locator_key(
    locator: PolicyEvidenceLocatorV0,
) -> tuple[str, str, str, str, str, str, str]:
    return (
        locator.branch_id,
        locator.evidence_kind,
        locator.evidence_id,
        locator.occurrence_alias or "",
        locator.policy_node_id or "",
        locator.condition_id or "",
        locator.condition_role or "",
    )


def _projection_error(code: str, message: str) -> PolicyExplanationProjectionError:
    return PolicyExplanationProjectionError(message, code=code)


__all__ = ["project_policy_evidence_v1", "project_policy_explanation_v0"]
