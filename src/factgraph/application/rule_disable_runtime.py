"""Application-layer Rule Disable runtime executor."""

from __future__ import annotations

from typing import Any

from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec
from factgraph.core.rules.where_eval import WhereValidationError, evaluate_where
from factgraph.core.store._support import BindingItems, ProofReceipt, normalize_binding_items
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts

from .protocol import (
    ErrorDTO,
    ProofFrameConditionVerdict,
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
    if not isinstance(action, RuleDisableAction):
        return _invalid_request(
            code="RULE_DISABLE_ACTION_TYPE_UNSUPPORTED",
            message="RuleDisableRequest.overlay requires RuleDisableAction",
            path=("overlay", "rule_actions", "0"),
            details={"action_type": type(action).__name__},
        )
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
        case_index=action.case_index,
        condition_index=action.condition_index,
    )
    if target_atom is None:
        return _invalid_request(
            code="RULE_DISABLE_TARGET_NOT_FOUND",
            message="RuleDisableAction target locator does not exist in rule_spec.where",
            path=("overlay", "rule_actions", "0"),
            details={
                "case_index": action.case_index,
                "condition_index": action.condition_index,
            },
        )
    if target_atom[0] == "ruleref":
        return _unsupported(
            code="RULE_DISABLE_RULE_REF_UNSUPPORTED",
            message="Rule Disable does not support disabling ruleref atoms in Batch 5a",
            path=("overlay", "rule_actions", "0"),
            details={
                "case_index": action.case_index,
                "condition_index": action.condition_index,
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
        disabled_locators=frozenset({(action.case_index, action.condition_index)}),
    )
    rows: set[BindingItems] = set()
    for binding in bindings:
        rows.add(normalize_binding_items((var, binding[var]) for var in rule_spec.select_vars))
    return tuple(sorted(rows, key=_binding_items_sort_key))


def _build_proof_frame_result(
    artifact: ProofReceipt,
    *,
    action_index: int,
    action: RuleDisableAction,
) -> ProofFrameRecheckResult:
    target_prefix = _atom_key_prefix(action)
    atom_verdicts = (
        *(
            ProofFrameConditionVerdict(
                condition_key=witness.pred_condition_key,
                verdict=(
                    "invalidated"
                    if witness.pred_condition_key.startswith(target_prefix)
                    else "still_valid"
                ),
                affected_action_indices=(
                    (action_index,)
                    if witness.pred_condition_key.startswith(target_prefix)
                    else ()
                ),
            )
            for witness in artifact.pred_witnesses
        ),
        *(
            ProofFrameConditionVerdict(
                condition_key=step.step_key,
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
    )
    return ProofFrameRecheckResult(
        status=aggregate_proof_frame_status(atom_verdicts),
        binding_items=artifact.binding_items,
        atom_verdicts=atom_verdicts,
    )


def _atom_key_prefix(action: RuleDisableAction) -> str:
    return f"c{action.case_index}.c{action.condition_index}:"


def _atom_at(
    where: list[Any],
    *,
    case_index: int,
    condition_index: int,
) -> tuple[Any, ...] | None:
    branches = _where_branches(where)
    if branches is None:
        return None
    if case_index >= len(branches):
        return None
    branch = branches[case_index]
    if condition_index >= len(branch):
        return None
    atom = branch[condition_index]
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
    return any(_atom_contains_ruleref(atom) for branch in branches for atom in branch)


def _atom_contains_ruleref(atom: Any) -> bool:
    if not isinstance(atom, tuple) or not atom:
        return False
    if atom[0] == "ruleref":
        return True
    if atom[0] == "not" and len(atom) >= 2 and isinstance(atom[1], list):
        return any(_atom_contains_ruleref(child) for child in atom[1])
    return False


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
