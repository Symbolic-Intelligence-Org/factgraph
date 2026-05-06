"""Application-layer Rule Disable runtime executor."""

from __future__ import annotations

from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec
from kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from kernel.core.store._support import BindingItems, SupportArtifact, normalize_binding_items
from kernel.core.store.runtime import Store
from kernel.core.view.projector import project_view_facts

from .protocol import (
    ErrorDTO,
    ProofFrameAtomVerdict,
    ProofFrameRecheckResult,
    RuleDisableAction,
    RuleDisableRequest,
    RuleDisableResult,
    aggregate_proof_frame_status,
)

_NATIVE_SUPPORT_KIND = "native_binding_v1"


def check_rule_disable_action(
    request: RuleDisableRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> RuleDisableResult:
    """Evaluate a native rule under one temporary disabled-locator action."""

    del registry
    artifact = request.support_artifact
    if artifact.kind != _NATIVE_SUPPORT_KIND or artifact.root_result_kind != "row":
        return _unsupported(
            code="RULE_DISABLE_SUPPORT_UNSUPPORTED",
            message="Rule Disable supports native row support artifacts only",
            path=("support_artifact",),
            details={
                "kind": artifact.kind,
                "root_result_kind": artifact.root_result_kind,
            },
        )
    if artifact.rule_ref_edges or artifact.rule_refs:
        return _unsupported(
            code="RULE_DISABLE_RULE_REF_UNSUPPORTED",
            message="Rule Disable does not support RuleRef-bearing support artifacts in Batch 5a",
            path=("support_artifact",),
            details={
                "rule_ref_edge_count": len(artifact.rule_ref_edges),
                "rule_refs_count": len(artifact.rule_refs),
            },
        )
    if _contains_ruleref_atom(request.rule_spec.where):
        return _unsupported(
            code="RULE_DISABLE_RULE_REF_UNSUPPORTED",
            message="Rule Disable does not support rule bodies containing ruleref atoms",
            path=("rule_spec", "where"),
        )
    if request.overlay.fact_actions:
        return _invalid_request(
            code="RULE_DISABLE_FACT_ACTIONS_UNSUPPORTED",
            message="RuleDisableRequest.overlay must not contain fact actions",
            path=("overlay", "fact_actions"),
            details={"fact_action_count": len(request.overlay.fact_actions)},
        )
    if len(request.overlay.rule_actions) != 1:
        return _invalid_request(
            code="RULE_DISABLE_ACTION_COUNT",
            message="Rule Disable Batch 5a requires exactly one rule action",
            path=("overlay", "rule_actions"),
            details={"rule_action_count": len(request.overlay.rule_actions)},
        )

    action = request.overlay.rule_actions[0]
    if action.rule_id != request.rule_spec.rule_id or action.version != request.rule_spec.version:
        return _invalid_request(
            code="RULE_DISABLE_RULE_MISMATCH",
            message="RuleDisableAction rule identity must match request.rule_spec",
            path=("overlay", "rule_actions", "0"),
            details={
                "action_rule_id": action.rule_id,
                "action_version": action.version,
                "rule_id": request.rule_spec.rule_id,
                "version": request.rule_spec.version,
            },
        )
    target_atom = _atom_at(
        request.rule_spec.where,
        branch_index=action.branch_index,
        atom_index=action.atom_index,
    )
    if target_atom is None:
        return _invalid_request(
            code="RULE_DISABLE_TARGET_NOT_FOUND",
            message="RuleDisableAction target locator does not exist in rule_spec.where",
            path=("overlay", "rule_actions", "0"),
            details={
                "branch_index": action.branch_index,
                "atom_index": action.atom_index,
            },
        )
    if target_atom[0] == "ruleref":
        return _unsupported(
            code="RULE_DISABLE_RULE_REF_UNSUPPORTED",
            message="Rule Disable does not support disabling ruleref atoms in Batch 5a",
            path=("overlay", "rule_actions", "0"),
            details={
                "branch_index": action.branch_index,
                "atom_index": action.atom_index,
            },
        )

    try:
        variant_rows = _evaluate_variant_rows(
            request.rule_spec,
            action=action,
            store=store,
        )
    except (KeyError, RuleCompileError, TypeError, ValueError, WhereValidationError) as exc:
        return _invalid_request(
            code="RULE_DISABLE_NATIVE_EVAL_ERROR",
            message="Rule Disable native variant evaluation failed",
            path=("runtime",),
            details={"exception": type(exc).__name__, "reason": str(exc)},
        )

    proof_frame = _build_proof_frame_result(artifact, action_index=0, action=action)
    return RuleDisableResult(
        status="completed",
        variant_rows=variant_rows,
        proof_frame=proof_frame,
        errors=(),
        warnings=(),
    )


def _evaluate_variant_rows(
    rule_spec: RuleSpec,
    *,
    action: RuleDisableAction,
    store: Store,
) -> tuple[BindingItems, ...]:
    bindings = evaluate_where(
        project_view_facts(store.ledger, store.schema_ir),
        rule_spec.where,
        disabled_locators=frozenset({(action.branch_index, action.atom_index)}),
    )
    rows: set[BindingItems] = set()
    for binding in bindings:
        rows.add(normalize_binding_items((var, binding[var]) for var in rule_spec.select_vars))
    return tuple(sorted(rows, key=_binding_items_sort_key))


def _build_proof_frame_result(
    artifact: SupportArtifact,
    *,
    action_index: int,
    action: RuleDisableAction,
) -> ProofFrameRecheckResult:
    target_prefix = _atom_key_prefix(action)
    atom_verdicts = tuple(
        [
            *(
                ProofFrameAtomVerdict(
                    atom_key=witness.pred_atom_key,
                    verdict=(
                        "invalidated"
                        if witness.pred_atom_key.startswith(target_prefix)
                        else "still_valid"
                    ),
                    affected_action_indices=(
                        (action_index,)
                        if witness.pred_atom_key.startswith(target_prefix)
                        else ()
                    ),
                )
                for witness in artifact.pred_witnesses
            ),
            *(
                ProofFrameAtomVerdict(
                    atom_key=step.step_key,
                    verdict=(
                        "invalidated"
                        if step.step_key.startswith(target_prefix)
                        else "still_valid"
                    ),
                    affected_action_indices=(
                        (action_index,) if step.step_key.startswith(target_prefix) else ()
                    ),
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


def _atom_key_prefix(action: RuleDisableAction) -> str:
    return f"b{action.branch_index}.a{action.atom_index}:"


def _atom_at(
    where: list[Any],
    *,
    branch_index: int,
    atom_index: int,
) -> tuple[Any, ...] | None:
    branches = _where_branches(where)
    if branches is None:
        return None
    if branch_index >= len(branches):
        return None
    branch = branches[branch_index]
    if atom_index >= len(branch):
        return None
    atom = branch[atom_index]
    if not isinstance(atom, tuple) or not atom:
        return None
    return atom


def _where_branches(where: list[Any]) -> list[list[Any]] | None:
    if not isinstance(where, list) or not where:
        return None
    if all(isinstance(item, tuple) for item in where):
        return [where]
    if all(isinstance(item, list) for item in where):
        return where
    return None


def _contains_ruleref_atom(where: list[Any]) -> bool:
    branches = _where_branches(where)
    if branches is None:
        return False
    return any(
        isinstance(atom, tuple) and bool(atom) and atom[0] == "ruleref"
        for branch in branches
        for atom in branch
    )


def _binding_items_sort_key(binding_items: BindingItems) -> tuple[tuple[str, str], ...]:
    return tuple((key, repr(value)) for key, value in binding_items)


def _unsupported(
    *,
    code: str,
    message: str,
    path: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> RuleDisableResult:
    return RuleDisableResult(
        status="unsupported",
        variant_rows=(),
        proof_frame=None,
        errors=(ErrorDTO(code=code, message=message, path=path, details=details or {}),),
        warnings=(),
    )


def _invalid_request(
    *,
    code: str,
    message: str,
    path: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> RuleDisableResult:
    return RuleDisableResult(
        status="invalid_request",
        variant_rows=(),
        proof_frame=None,
        errors=(ErrorDTO(code=code, message=message, path=path, details=details or {}),),
        warnings=(),
    )


__all__ = ["check_rule_disable_action"]
