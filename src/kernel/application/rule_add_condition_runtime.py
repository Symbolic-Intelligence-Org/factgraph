"""Application-layer Rule Add Condition runtime executor."""

from __future__ import annotations

from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec
from kernel.core.rules.where_ast_validate import (
    WhereASTValidationError,
    atom_binds_new_variables,
)
from kernel.core.rules.where_eval import (
    WhereAddedCondition,
    WhereValidationError,
    evaluate_where,
)
from kernel.core.store._support import BindingItems, SupportArtifact, normalize_binding_items
from kernel.core.store.runtime import Store
from kernel.core.view.projector import project_view_facts

from .protocol import (
    ErrorDTO,
    ProofFrameAtomVerdict,
    ProofFrameRecheckResult,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    RuleAddConditionResult,
    aggregate_proof_frame_status,
)

_NATIVE_SUPPORT_KIND = "native_binding_v1"
_ADD_CONDITION_SUPPORTED_ATOM_KINDS = {"eq", "ne", "gt", "ge", "lt", "le", "in"}


def check_rule_add_condition_action(
    request: RuleAddConditionRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> RuleAddConditionResult:
    """Evaluate a native rule under one temporary added-filter condition."""

    del registry
    artifact = request.support_artifact
    if artifact.kind != _NATIVE_SUPPORT_KIND or artifact.root_result_kind != "row":
        return _unsupported(
            code="RULE_ADD_CONDITION_SUPPORT_UNSUPPORTED",
            message="Rule Add Condition supports native row support artifacts only",
            path=("support_artifact",),
            details={
                "kind": artifact.kind,
                "root_result_kind": artifact.root_result_kind,
            },
        )
    if artifact.rule_ref_edges or artifact.rule_refs:
        return _unsupported(
            code="RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED",
            message="Rule Add Condition does not support RuleRef-bearing support artifacts in Batch 5c",
            path=("support_artifact",),
            details={
                "rule_ref_edge_count": len(artifact.rule_ref_edges),
                "rule_refs_count": len(artifact.rule_refs),
            },
        )
    if _contains_ruleref_atom(request.rule_spec.where):
        return _unsupported(
            code="RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED",
            message="Rule Add Condition does not support rule bodies containing ruleref atoms",
            path=("rule_spec", "where"),
        )
    if request.overlay.fact_actions:
        return _invalid_request(
            code="RULE_ADD_CONDITION_FACT_ACTIONS_UNSUPPORTED",
            message="RuleAddConditionRequest.overlay must not contain fact actions",
            path=("overlay", "fact_actions"),
            details={"fact_action_count": len(request.overlay.fact_actions)},
        )
    if len(request.overlay.rule_actions) != 1:
        return _invalid_request(
            code="RULE_ADD_CONDITION_ACTION_COUNT",
            message="Rule Add Condition Batch 5c requires exactly one rule action",
            path=("overlay", "rule_actions"),
            details={"rule_action_count": len(request.overlay.rule_actions)},
        )

    action = request.overlay.rule_actions[0]
    if not isinstance(action, RuleAddConditionAction):
        return _invalid_request(
            code="RULE_ADD_CONDITION_ACTION_TYPE_UNSUPPORTED",
            message="RuleAddConditionRequest.overlay requires RuleAddConditionAction",
            path=("overlay", "rule_actions", "0"),
            details={"action_type": type(action).__name__},
        )
    if action.rule_id != request.rule_spec.rule_id or action.version != request.rule_spec.version:
        return _invalid_request(
            code="RULE_ADD_CONDITION_RULE_MISMATCH",
            message="RuleAddConditionAction rule identity must match request.rule_spec",
            path=("overlay", "rule_actions", "0"),
            details={
                "action_rule_id": action.rule_id,
                "action_version": action.version,
                "rule_id": request.rule_spec.rule_id,
                "version": request.rule_spec.version,
            },
        )

    branches = _where_branches(request.rule_spec.where)
    if branches is None or action.branch_index >= len(branches):
        return _invalid_request(
            code="RULE_ADD_CONDITION_BRANCH_NOT_FOUND",
            message="RuleAddConditionAction target branch does not exist in rule_spec.where",
            path=("overlay", "rule_actions", "0"),
            details={"branch_index": action.branch_index},
        )

    target_error = _validate_added_atom(action, branches[action.branch_index])
    if target_error is not None:
        return _invalid_request(
            code=target_error.code,
            message=target_error.message,
            path=target_error.path,
            details=target_error.details,
        )

    try:
        variant_rows = _evaluate_variant_rows(
            request.rule_spec,
            action=action,
            store=store,
        )
    except (
        KeyError,
        RuleCompileError,
        TypeError,
        ValueError,
        WhereASTValidationError,
        WhereValidationError,
    ) as exc:
        return _invalid_request(
            code="RULE_ADD_CONDITION_NATIVE_EVAL_ERROR",
            message="Rule Add Condition native variant evaluation failed",
            path=("runtime",),
            details={"exception": type(exc).__name__, "reason": str(exc)},
        )

    proof_frame = _build_proof_frame_result(
        artifact,
        action_index=0,
        action=action,
        variant_rows=variant_rows,
    )
    return RuleAddConditionResult(
        status="completed",
        variant_rows=variant_rows,
        proof_frame=proof_frame,
        errors=(),
        warnings=(),
    )


def _validate_added_atom(
    action: RuleAddConditionAction,
    branch: list[Any],
) -> ErrorDTO | None:
    atom = action.added_atom.atom
    if not isinstance(atom, tuple) or not atom or not isinstance(atom[0], str):
        return ErrorDTO(
            code="RULE_ADD_CONDITION_ATOM_MALFORMED",
            message="RuleAddConditionAction added_atom must be a native atom tuple",
            path=("overlay", "rule_actions", "0", "added_atom"),
        )
    atom_kind = atom[0]
    if atom_kind == "not":
        return ErrorDTO(
            code="RULE_ADD_CONDITION_NOT_UNSUPPORTED",
            message="Rule Add Condition does not support adding not atoms in Batch 5c",
            path=("overlay", "rule_actions", "0", "added_atom"),
            details={"atom_kind": atom_kind},
        )
    if atom_kind not in _ADD_CONDITION_SUPPORTED_ATOM_KINDS:
        return ErrorDTO(
            code="RULE_ADD_CONDITION_ATOM_UNSUPPORTED",
            message="Rule Add Condition target atom kind is not supported in Batch 5c",
            path=("overlay", "rule_actions", "0", "added_atom"),
            details={"atom_kind": atom_kind},
        )
    malformed_reason = _added_atom_malformed_reason(atom)
    if malformed_reason is not None:
        return ErrorDTO(
            code="RULE_ADD_CONDITION_ATOM_MALFORMED",
            message="RuleAddConditionAction added_atom has invalid native atom shape",
            path=("overlay", "rule_actions", "0", "added_atom"),
            details={"reason": malformed_reason},
        )
    bound_vars = frozenset(_vars_in_branch(branch))
    try:
        binds_new = atom_binds_new_variables(atom, bound_vars=bound_vars)
    except WhereASTValidationError as exc:
        return ErrorDTO(
            code="RULE_ADD_CONDITION_BINDS_NEW_VARIABLE",
            message="RuleAddConditionAction added_atom must reference variables already bound in the branch",
            path=("overlay", "rule_actions", "0", "added_atom"),
            details={"reason": str(exc), "bound_vars": sorted(bound_vars)},
        )
    if binds_new:
        return ErrorDTO(
            code="RULE_ADD_CONDITION_BINDS_NEW_VARIABLE",
            message="RuleAddConditionAction added_atom must not bind new variables",
            path=("overlay", "rule_actions", "0", "added_atom"),
            details={"bound_vars": sorted(bound_vars)},
        )
    return None


def _added_atom_malformed_reason(atom: tuple[Any, ...]) -> str | None:
    atom_kind = atom[0]
    if atom_kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        if len(atom) != 3:
            return f"{atom_kind} atom must have 3 items"
        return None
    if atom_kind == "in":
        if len(atom) != 3:
            return "in atom must have 3 items"
        if not isinstance(atom[2], list):
            return "in values must be list"
        if not atom[2]:
            return "in values must be non-empty"
        return None
    return None


def _evaluate_variant_rows(
    rule_spec: RuleSpec,
    *,
    action: RuleAddConditionAction,
    store: Store,
) -> tuple[BindingItems, ...]:
    bindings = evaluate_where(
        project_view_facts(store.ledger, store.schema_ir),
        rule_spec.where,
        added_conditions=frozenset(
            {
                WhereAddedCondition(
                    branch_index=action.branch_index,
                    atom=action.added_atom.atom,
                )
            }
        ),
    )
    rows: set[BindingItems] = set()
    for binding in bindings:
        rows.add(normalize_binding_items((var, binding[var]) for var in rule_spec.select_vars))
    return tuple(sorted(rows, key=_binding_items_sort_key))


def _build_proof_frame_result(
    artifact: SupportArtifact,
    *,
    action_index: int,
    action: RuleAddConditionAction,
    variant_rows: tuple[BindingItems, ...],
) -> ProofFrameRecheckResult:
    synthetic_key = _synthetic_atom_key(action, action_index=action_index)
    old_binding_still_present = artifact.binding_items in set(variant_rows)
    synthetic_verdict = "still_valid" if old_binding_still_present else "invalidated"
    atom_verdicts = tuple(
        [
            *(
                ProofFrameAtomVerdict(
                    atom_key=witness.pred_atom_key,
                    verdict="still_valid",
                    affected_action_indices=(),
                )
                for witness in artifact.pred_witnesses
            ),
            *(
                ProofFrameAtomVerdict(
                    atom_key=step.step_key,
                    verdict="still_valid",
                    affected_action_indices=(),
                )
                for step in artifact.non_fact_steps
            ),
            ProofFrameAtomVerdict(
                atom_key=synthetic_key,
                verdict=synthetic_verdict,
                affected_action_indices=(
                    (action_index,) if synthetic_verdict == "invalidated" else ()
                ),
            ),
        ]
    )
    return ProofFrameRecheckResult(
        status=aggregate_proof_frame_status(atom_verdicts),
        binding_items=artifact.binding_items,
        atom_verdicts=atom_verdicts,
    )


def _synthetic_atom_key(action: RuleAddConditionAction, *, action_index: int) -> str:
    return f"b{action.branch_index}.add{action_index}:{action.added_atom.atom[0]}"


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


def _vars_in_branch(branch: list[Any]) -> set[str]:
    found: set[str] = set()
    for atom in branch:
        if isinstance(atom, tuple):
            _collect_vars(atom, found)
    return found


def _collect_vars(value: Any, found: set[str]) -> None:
    if isinstance(value, str) and value.startswith("$") and len(value) > 1:
        found.add(value)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _collect_vars(item, found)


def _binding_items_sort_key(binding_items: BindingItems) -> tuple[tuple[str, str], ...]:
    return tuple((key, repr(value)) for key, value in binding_items)


def _unsupported(
    *,
    code: str,
    message: str,
    path: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> RuleAddConditionResult:
    return RuleAddConditionResult(
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
) -> RuleAddConditionResult:
    return RuleAddConditionResult(
        status="invalid_request",
        variant_rows=(),
        proof_frame=None,
        errors=(ErrorDTO(code=code, message=message, path=path, details=details or {}),),
        warnings=(),
    )


__all__ = ["check_rule_add_condition_action"]
