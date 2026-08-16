"""Build one private R3d capture-only receipt inventory from a sealed bundle.

The existing ``evaluation_run_bundle_evidence(...)->EvidenceGraph`` path is a
separate playback contract and is intentionally not imported, called, replaced,
or re-exported here.  This module only derives a selected native receipt
inventory after taking a fresh canonical ``EvaluationRunBundleV0`` snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evaluation_run_bundle_runtime import (
    _receipt_case_index,
    _validate_native_where_bytes,
    _validate_proof_receipt_bytes,
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
)
from .protocol.captured_receipt_evidence import (
    CapturedReceiptBranchV0,
    CapturedReceiptConditionV0,
    CapturedReceiptEvidenceV0,
    _capture_context_digest,
    _token,
)
from .protocol.common import ProtocolShapeError
from .protocol.evaluation_run_bundle import EvaluationRunBundleV0


def build_captured_receipt_evidence_v0(
    bundle: EvaluationRunBundleV0,
    *,
    row_capture_digest: str,
) -> CapturedReceiptEvidenceV0:
    """Build one sealed native receipt inventory from a detached bundle snapshot.

    Args:
        bundle: Candidate ``EvaluationRunBundleV0`` capture.  The full bundle
            must canonically validate and decode before the row selector is
            inspected.
        row_capture_digest: Exact captured-row seal selecting one row.  It is a
            selector only, never a public row anchor or ordinal.

    Returns:
        ``CapturedReceiptEvidenceV0`` for exactly one receipt-selected native
        branch, with sealed condition, predicate, and assertion-id inventory.

    Raises:
        ProtocolShapeError: If the source bundle/snapshot is malformed or
            stale; if the selector is malformed, absent, or ambiguous; or if a
            selected receipt disagrees with the captured native plan/relation.

    FactGraph Contract:
        The builder first fully validates, canonically encodes, freshly decodes,
        and revalidates the whole bundle; only then can it validate or match the
        selector.  It fails closed for zero, absent, ambiguous, foreign, stale,
        or malformed input and never fabricates an empty or failed inventory.
        It reads no Store, ledger, cache, sidecar, registry, or evaluator and
        writes none.  It does not run verification or replay, use or project
        Policy/Rule lineage to derive the inventory, construct an
        ``EvidenceGraph`` or ``Explanation``, or infer truth,
        source/admission/governance, authenticity, authorization, or proof
        parity.  Full bundle snapshot validation still validates every sealed
        bundle component required by that existing codec.  Availability is
        fixed to ``unverified``, logical and
        replay verification ``not_performed``, and proof parity ``not_claimed``;
        those labels do not mean falsehood.  This is application-internal only:
        no application/protocol root, SDK, Product, Meander, Agent, or MCP
        façade exposes it.
    """

    snapshot = _validated_bundle_snapshot(bundle)
    row = _select_snapshot_row(snapshot.rows, row_capture_digest)

    # This is deliberately local rather than the verification materialization
    # helper: R3d validates the same freshly decoded native-plan bytes but does
    # not import or invoke a verifier/evaluator seam.
    where = _validate_native_where_bytes(snapshot.native_plan.where_bytes)
    receipt = _validate_proof_receipt_bytes(row.proof_receipt_bytes)
    branch_index = _receipt_case_index(receipt)
    branch_id = f"c{branch_index}"
    branch = _selected_native_branch(where, branch_index)
    context_digest = _capture_context_digest(
        bundle_digest=snapshot.bundle_digest,
        row_capture_digest=row.row_capture_digest,
        native_plan_digest=snapshot.native_plan.plan_digest,
        proof_receipt_digest=row.proof_receipt_digest,
        branch_id=branch_id,
    )
    witnesses = _receipt_index(
        receipt.pred_witnesses,
        key_name="pred_condition_key",
        duplicate_message="ProofReceipt has duplicate predicate condition keys",
    )
    steps = _receipt_index(
        receipt.non_fact_steps,
        key_name="step_key",
        duplicate_message="ProofReceipt has duplicate non-fact step keys",
    )
    relation_by_assertion = _relation_assertion_index(snapshot)
    conditions = tuple(
        _captured_condition(
            atom,
            index=index,
            branch_index=branch_index,
            branch_id=branch_id,
            context_digest=context_digest,
            witnesses=witnesses,
            steps=steps,
            relation_by_assertion=relation_by_assertion,
        )
        for index, atom in enumerate(branch)
    )
    branch_digest = _token(
        "captured_receipt_branch_v0",
        (
            context_digest,
            branch_id,
            tuple(condition.condition_digest for condition in conditions),
        ),
    )
    captured_branch = CapturedReceiptBranchV0(
        capture_context_digest=context_digest,
        branch_id=branch_id,
        conditions=conditions,
        branch_digest=branch_digest,
    )
    try:
        selected_anchor = snapshot.run_anchor.row_anchors[row.ordinal]
    except (IndexError, TypeError) as exc:
        raise ProtocolShapeError("Captured receipt row anchor is absent") from exc

    evidence_values = (
        snapshot.bundle_digest,
        snapshot.run_anchor.anchor_digest,
        snapshot.native_plan.plan_digest,
        snapshot.native_plan.where_digest,
        snapshot.query_digest,
        snapshot.run_anchor.result_id,
        snapshot.run_anchor.result_digest,
        row.row_id,
        row.claim_digest,
        row.row_capture_digest,
        selected_anchor.semantic_anchor_digest,
        row.proof_receipt_digest,
        "selected_receipt_captured",
        "sealed_native_plan_relation_receipt",
        snapshot.integrity,
        snapshot.authenticity,
        "not_performed",
        "not_performed",
        "not_claimed",
        captured_branch.branch_digest,
    )
    return CapturedReceiptEvidenceV0(
        bundle_digest=snapshot.bundle_digest,
        run_anchor_digest=snapshot.run_anchor.anchor_digest,
        native_plan_digest=snapshot.native_plan.plan_digest,
        native_where_digest=snapshot.native_plan.where_digest,
        query_digest=snapshot.query_digest,
        result_id=snapshot.run_anchor.result_id,
        result_digest=snapshot.run_anchor.result_digest,
        row_id=row.row_id,
        claim_digest=row.claim_digest,
        row_capture_digest=row.row_capture_digest,
        semantic_row_anchor_digest=selected_anchor.semantic_anchor_digest,
        proof_receipt_digest=row.proof_receipt_digest,
        capture_status="selected_receipt_captured",
        capture_basis="sealed_native_plan_relation_receipt",
        integrity=snapshot.integrity,
        authenticity=snapshot.authenticity,
        logical_verification="not_performed",
        replay_verification="not_performed",
        proof_parity="not_claimed",
        branch=captured_branch,
        evidence_digest=_token("captured_receipt_evidence_v0", evidence_values),
    )


def _validated_bundle_snapshot(bundle: EvaluationRunBundleV0) -> EvaluationRunBundleV0:
    """Return a fresh fully revalidated canonical bundle snapshot.

    Args:
        bundle: Candidate detached capture container.

    Returns:
        Freshly decoded, fully revalidated ``EvaluationRunBundleV0`` snapshot.

    Raises:
        ProtocolShapeError: If bundle validation, canonical encoding, decoding,
            or round-trip stability fails.

    FactGraph Contract:
        This freshness boundary runs before selector validation or lookup, so
        caller-side mutation cannot change the data subsequently selected.  It
        does not open a Store, execute a verifier/evaluator, replay a source
        run, authenticate data, recover source/admission/governance context, or
        create Explain/EvidenceGraph material.
    """

    raw = evaluation_run_bundle_bytes(bundle)
    snapshot = evaluation_run_bundle_from_bytes(raw)
    if evaluation_run_bundle_bytes(snapshot) != raw:
        raise ProtocolShapeError("EvaluationRun bundle snapshot changed after validation")
    return snapshot


def _select_snapshot_row(rows: object, row_capture_digest: object) -> Any:
    """Select exactly one row only after the caller has produced a snapshot.

    This helper is intentionally separate from snapshot construction so the
    no-fabrication rules for malformed, absent, and ambiguous selectors can be
    exercised independently.  The public builder always invokes it after
    ``_validated_bundle_snapshot``; it is not a shortcut around that boundary.
    """

    if type(rows) is not tuple:
        raise ProtocolShapeError("EvaluationRun snapshot rows are malformed")
    if type(row_capture_digest) is not str or not row_capture_digest:
        raise ProtocolShapeError("row_capture_digest must be a non-empty string")
    matches = tuple(
        row for row in rows if getattr(row, "row_capture_digest", None) == row_capture_digest
    )
    if not matches:
        raise ProtocolShapeError("EvaluationRun row_capture_digest was not found")
    if len(matches) != 1:
        raise ProtocolShapeError("EvaluationRun row_capture_digest is ambiguous")
    return matches[0]


def _selected_native_branch(where: list[Any], branch_index: int) -> tuple[tuple[Any, ...], ...]:
    """Select exactly one non-empty native plan branch without executing it."""

    if type(branch_index) is not int or branch_index < 0:
        raise ProtocolShapeError("ProofReceipt selected branch index is malformed")
    branches: tuple[tuple[tuple[Any, ...], ...], ...]
    if all(isinstance(item, tuple) for item in where):
        branches = (tuple(where),)
    elif all(isinstance(item, list) for item in where):
        branches = tuple(tuple(branch) for branch in where)
    else:
        raise ProtocolShapeError("captured native plan branch shape is invalid")
    if branch_index >= len(branches):
        raise ProtocolShapeError("ProofReceipt selected branch is absent from the native plan")
    branch = branches[branch_index]
    if not branch or not all(isinstance(atom, tuple) and atom for atom in branch):
        raise ProtocolShapeError("captured native plan branch is malformed")
    return branch


def _receipt_index(
    entries: object,
    *,
    key_name: str,
    duplicate_message: str,
) -> dict[str, Any]:
    """Build an exact receipt-key index and reject malformed duplicates."""

    if type(entries) is not tuple:
        raise ProtocolShapeError("ProofReceipt entry inventory is malformed")
    index: dict[str, Any] = {}
    for entry in entries:
        key = getattr(entry, key_name, None)
        if type(key) is not str or not key:
            raise ProtocolShapeError("ProofReceipt entry key is malformed")
        if key in index:
            raise ProtocolShapeError(duplicate_message)
        index[key] = entry
    return index


def _captured_condition(
    atom: tuple[Any, ...],
    *,
    index: int,
    branch_index: int,
    branch_id: str,
    context_digest: str,
    witnesses: Mapping[str, Any],
    steps: Mapping[str, Any],
    relation_by_assertion: Mapping[str, str],
) -> CapturedReceiptConditionV0:
    """Seal one receipt-validated native condition inventory entry."""

    if not atom or type(atom[0]) is not str or not atom[0]:
        raise ProtocolShapeError("captured native condition kind is malformed")
    kind = atom[0]
    condition_id = f"{branch_id}:native:{index}"
    if kind == "pred":
        if len(atom) != 3 or type(atom[1]) is not str or not atom[1]:
            raise ProtocolShapeError("captured native predicate is malformed")
        predicate_id = atom[1]
        receipt_condition_key = f"c{branch_index}.c{index}:{predicate_id}"
        witness = witnesses.get(receipt_condition_key)
        if witness is None:
            raise ProtocolShapeError("ProofReceipt is missing predicate evidence")
        assertion_ids = getattr(witness, "asrt_ids", None)
        if (
            type(assertion_ids) is not tuple
            or not assertion_ids
            or any(type(item) is not str or not item for item in assertion_ids)
            or tuple(sorted(assertion_ids)) != assertion_ids
            or len(set(assertion_ids)) != len(assertion_ids)
        ):
            raise ProtocolShapeError(
                "ProofReceipt predicate assertion ids must be sorted, unique, and non-empty"
            )
        for assertion_id in assertion_ids:
            if relation_by_assertion.get(assertion_id) != predicate_id:
                raise ProtocolShapeError("ProofReceipt assertion does not match its predicate")
        captured_step_kind: str | None = None
    else:
        predicate_id = None
        assertion_ids = ()
        receipt_condition_key = f"c{branch_index}.c{index}:{kind}"
        step = steps.get(receipt_condition_key)
        expected_status = "no_match" if kind == "not" else "satisfied"
        if (
            step is None
            or getattr(step, "kind", None) != kind
            or getattr(step, "status", None) != expected_status
        ):
            raise ProtocolShapeError("ProofReceipt non-fact step does not match native plan")
        captured_step_kind = kind
    condition_values = (
        context_digest,
        branch_id,
        index,
        condition_id,
        receipt_condition_key,
        kind,
        predicate_id,
        assertion_ids,
        captured_step_kind,
    )
    return CapturedReceiptConditionV0(
        capture_context_digest=context_digest,
        branch_id=branch_id,
        condition_index=index,
        condition_id=condition_id,
        receipt_condition_key=receipt_condition_key,
        native_kind=kind,
        predicate_id=predicate_id,
        assertion_ids=assertion_ids,
        captured_step_kind=captured_step_kind,
        condition_digest=_token("captured_receipt_condition_v0", condition_values),
    )


def _relation_assertion_index(bundle: EvaluationRunBundleV0) -> dict[str, str]:
    """Return the selected snapshot's assertion-id to predicate inventory."""

    index: dict[str, str] = {}
    for relation in bundle.relations:
        for assertion_id, _values in relation.facts:
            if assertion_id in index:
                raise ProtocolShapeError("captured relation has duplicate assertion id")
            index[assertion_id] = relation.predicate_id
    return index
