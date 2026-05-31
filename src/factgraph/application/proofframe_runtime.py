"""Application-layer ProofFrame recheck runtime."""

from __future__ import annotations

from factgraph.core.store._support import (
    NonFactStep,
    PredWitness,
    ProjectedFact,
)
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts_with_witness

from .protocol import (
    FactOverlay,
    FactOverlayAction,
    RemoveFact,
    ReplaceFact,
    ProofFrameConditionVerdict,
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    aggregate_proof_frame_status,
)

_NATIVE_SUPPORT_KIND = "native_binding_v1"
_BINDING_DRIVEN_NON_FACT_KINDS = frozenset(
    {"eq", "ne", "in", "gt", "ge", "lt", "le", "neg", "add", "sub", "addc", "mulc"}
)


def recheck_proof_frame(
    request: ProofFrameRecheckRequest,
    *,
    store: Store,
    registry: object | None = None,
) -> ProofFrameRecheckResult:
    """Recheck one support frame under a fact-side evaluation overlay."""

    del registry
    artifact = request.support_artifact
    if artifact.kind != _NATIVE_SUPPORT_KIND:
        return _unknown_frame_result(request)
    if artifact.rule_ref_edges:
        return _unknown_frame_result(request)
    if request.overlay.rule_actions:
        return _unknown_frame_result(request)

    projected_witness = project_view_facts_with_witness(store.ledger, store.schema_ir)
    visible_rows = _visible_projected_rows(projected_witness)
    action_index = _index_overlay_actions(request.overlay)
    frame_relevant_action_indices = _frame_relevant_action_indices(
        artifact.pred_witnesses,
        action_index=action_index,
    )

    atom_verdicts = tuple(
        [
            *(
                _recheck_pred_witness(
                    witness,
                    visible_rows=visible_rows,
                    action_index=action_index,
                )
                for witness in artifact.pred_witnesses
            ),
            *(
                _recheck_non_fact_step(
                    step,
                    frame_relevant_action_indices=frame_relevant_action_indices,
                )
                for step in artifact.non_fact_steps
            ),
        ]
    )
    return ProofFrameRecheckResult(
        status=aggregate_proof_frame_status(atom_verdicts),
        binding_items=artifact.binding_items,
        atom_verdicts=atom_verdicts,
    )


def render_proof_frame_narrative(
    result: ProofFrameRecheckResult,
    *,
    overlay: FactOverlay,
) -> str:
    """Render a deterministic single-frame English summary."""

    lines = [f"Proof frame status: {result.status}."]
    if not result.atom_verdicts:
        lines.append("No recheckable proof atoms were evaluated.")
        return "\n".join(lines)

    for verdict in result.atom_verdicts:
        if verdict.verdict == "still_valid":
            continue
        suffix = _action_suffix(verdict.affected_action_indices, overlay=overlay)
        lines.append(f"- {verdict.atom_key}: {verdict.verdict}{suffix}.")
    return "\n".join(lines)


def _recheck_pred_witness(
    witness: PredWitness,
    *,
    visible_rows: dict[tuple[str, str], ProjectedFact],
    action_index: dict[tuple[str, str], list[tuple[int, FactOverlayAction]]],
) -> ProofFrameConditionVerdict:
    pred_id = _pred_id_from_atom_key(witness.pred_atom_key)
    affected: list[int] = []
    still_witnessed = False

    for asrt_id in witness.asrt_ids:
        key = (pred_id, asrt_id)
        actions = action_index.get(key, [])
        affected.extend(index for index, _ in actions)
        row = visible_rows.get(key)
        if not actions:
            if row is not None:
                still_witnessed = True
            continue
        if _action_preserves_witness(actions[-1][1], row):
            still_witnessed = True

    verdict = "still_valid" if still_witnessed else "invalidated"
    return ProofFrameConditionVerdict(
        atom_key=witness.pred_atom_key,
        verdict=verdict,
        affected_action_indices=tuple(sorted(set(affected))),
    )


def _recheck_non_fact_step(
    step: NonFactStep,
    *,
    frame_relevant_action_indices: tuple[int, ...],
) -> ProofFrameConditionVerdict:
    if step.kind == "not":
        return ProofFrameConditionVerdict(
            atom_key=step.step_key,
            verdict="unknown",
            affected_action_indices=(),
        )
    if step.kind in _BINDING_DRIVEN_NON_FACT_KINDS:
        return ProofFrameConditionVerdict(
            atom_key=step.step_key,
            verdict="still_valid",
            affected_action_indices=(),
        )
    if not frame_relevant_action_indices:
        return ProofFrameConditionVerdict(
            atom_key=step.step_key,
            verdict="still_valid",
            affected_action_indices=(),
        )
    return ProofFrameConditionVerdict(
        atom_key=step.step_key,
        verdict="unknown",
        affected_action_indices=frame_relevant_action_indices,
    )


def _index_overlay_actions(
    overlay: FactOverlay,
) -> dict[tuple[str, str], list[tuple[int, FactOverlayAction]]]:
    output: dict[tuple[str, str], list[tuple[int, FactOverlayAction]]] = {}
    for index, action in enumerate(overlay.fact_actions):
        output.setdefault((action.pred_id, action.asrt_id), []).append((index, action))
    return output


def _frame_relevant_action_indices(
    pred_witnesses: tuple[PredWitness, ...],
    *,
    action_index: dict[tuple[str, str], list[tuple[int, FactOverlayAction]]],
) -> tuple[int, ...]:
    relevant: set[int] = set()
    for witness in pred_witnesses:
        pred_id = _pred_id_from_atom_key(witness.pred_atom_key)
        for asrt_id in witness.asrt_ids:
            for index, _ in action_index.get((pred_id, asrt_id), ()):
                relevant.add(index)
    return tuple(sorted(relevant))


def _action_preserves_witness(
    action: FactOverlayAction,
    row: ProjectedFact | None,
) -> bool:
    if row is None:
        return False
    if isinstance(action, RemoveFact):
        return False
    return isinstance(action, ReplaceFact) and action.new_fact_tuple == row.fact_tuple


def _visible_projected_rows(
    projected_witness: dict[str, list[ProjectedFact]],
) -> dict[tuple[str, str], ProjectedFact]:
    return {
        (pred_id, row.asrt_id): row
        for pred_id, rows in projected_witness.items()
        for row in rows
    }


def _pred_id_from_atom_key(atom_key: str) -> str:
    _, separator, pred_id = atom_key.partition(":")
    if not separator or not pred_id:
        return atom_key
    return pred_id


def _unknown_frame_result(request: ProofFrameRecheckRequest) -> ProofFrameRecheckResult:
    return ProofFrameRecheckResult(
        status="unknown",
        binding_items=request.support_artifact.binding_items,
        atom_verdicts=(),
    )


def _action_suffix(
    affected_action_indices: tuple[int, ...],
    *,
    overlay: FactOverlay,
) -> str:
    if not affected_action_indices:
        return ""
    labels = ", ".join(
        _action_label(index, overlay=overlay)
        for index in affected_action_indices
    )
    return f" by {labels}"


def _action_label(index: int, *, overlay: FactOverlay) -> str:
    try:
        action = overlay.fact_actions[index]
    except IndexError:
        return f"action #{index}"
    action_kind = "remove" if isinstance(action, RemoveFact) else "replace"
    return f"action #{index}({action_kind} {action.pred_id})"


__all__ = [
    "recheck_proof_frame",
    "render_proof_frame_narrative",
]
