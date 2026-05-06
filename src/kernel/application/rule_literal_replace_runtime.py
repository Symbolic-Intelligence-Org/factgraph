"""Application-layer Rule Literal Replace runtime executor."""

from __future__ import annotations

from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry, RuleSpec
from kernel.core.rules.where_eval import (
    WhereLiteralReplacement,
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
    RuleLiteralPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
    RuleLiteralReplaceResult,
    aggregate_proof_frame_status,
)

_NATIVE_SUPPORT_KIND = "native_binding_v1"
_REPLACE_SUPPORTED_ATOM_KINDS = {
    "pred",
    "eq",
    "ne",
    "gt",
    "ge",
    "lt",
    "le",
    "in",
    "addc",
    "mulc",
}


def check_rule_literal_replace_action(
    request: RuleLiteralReplaceRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> RuleLiteralReplaceResult:
    """Evaluate a native rule under one temporary rule-literal replacement."""

    del registry
    artifact = request.support_artifact
    if artifact.kind != _NATIVE_SUPPORT_KIND or artifact.root_result_kind != "row":
        return _unsupported(
            code="RULE_LITERAL_REPLACE_SUPPORT_UNSUPPORTED",
            message="Rule Literal Replace supports native row support artifacts only",
            path=("support_artifact",),
            details={
                "kind": artifact.kind,
                "root_result_kind": artifact.root_result_kind,
            },
        )
    if artifact.rule_ref_edges or artifact.rule_refs:
        return _unsupported(
            code="RULE_LITERAL_REPLACE_RULE_REF_UNSUPPORTED",
            message="Rule Literal Replace does not support RuleRef-bearing support artifacts in Batch 5b",
            path=("support_artifact",),
            details={
                "rule_ref_edge_count": len(artifact.rule_ref_edges),
                "rule_refs_count": len(artifact.rule_refs),
            },
        )
    if _contains_ruleref_atom(request.rule_spec.where):
        return _unsupported(
            code="RULE_LITERAL_REPLACE_RULE_REF_UNSUPPORTED",
            message="Rule Literal Replace does not support rule bodies containing ruleref atoms",
            path=("rule_spec", "where"),
        )
    if request.overlay.fact_actions:
        return _invalid_request(
            code="RULE_LITERAL_REPLACE_FACT_ACTIONS_UNSUPPORTED",
            message="RuleLiteralReplaceRequest.overlay must not contain fact actions",
            path=("overlay", "fact_actions"),
            details={"fact_action_count": len(request.overlay.fact_actions)},
        )
    if len(request.overlay.rule_actions) != 1:
        return _invalid_request(
            code="RULE_LITERAL_REPLACE_ACTION_COUNT",
            message="Rule Literal Replace Batch 5b requires exactly one rule action",
            path=("overlay", "rule_actions"),
            details={"rule_action_count": len(request.overlay.rule_actions)},
        )

    action = request.overlay.rule_actions[0]
    if not isinstance(action, RuleLiteralReplaceAction):
        return _invalid_request(
            code="RULE_LITERAL_REPLACE_ACTION_TYPE_UNSUPPORTED",
            message="RuleLiteralReplaceRequest.overlay requires RuleLiteralReplaceAction",
            path=("overlay", "rule_actions", "0"),
            details={"action_type": type(action).__name__},
        )
    if action.rule_id != request.rule_spec.rule_id or action.version != request.rule_spec.version:
        return _invalid_request(
            code="RULE_LITERAL_REPLACE_RULE_MISMATCH",
            message="RuleLiteralReplaceAction rule identity must match request.rule_spec",
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
            code="RULE_LITERAL_REPLACE_TARGET_NOT_FOUND",
            message="RuleLiteralReplaceAction target locator does not exist in rule_spec.where",
            path=("overlay", "rule_actions", "0"),
            details={
                "branch_index": action.branch_index,
                "atom_index": action.atom_index,
            },
        )
    target_error = _validate_action_target(action, target_atom)
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
    except (KeyError, RuleCompileError, TypeError, ValueError, WhereValidationError) as exc:
        return _invalid_request(
            code="RULE_LITERAL_REPLACE_NATIVE_EVAL_ERROR",
            message="Rule Literal Replace native variant evaluation failed",
            path=("runtime",),
            details={"exception": type(exc).__name__, "reason": str(exc)},
        )

    proof_frame = _build_proof_frame_result(artifact, action_index=0, action=action)
    return RuleLiteralReplaceResult(
        status="completed",
        variant_rows=variant_rows,
        proof_frame=proof_frame,
        errors=(),
        warnings=(),
    )


def _evaluate_variant_rows(
    rule_spec: RuleSpec,
    *,
    action: RuleLiteralReplaceAction,
    store: Store,
) -> tuple[BindingItems, ...]:
    bindings = evaluate_where(
        project_view_facts(store.ledger, store.schema_ir),
        rule_spec.where,
        literal_replacements=frozenset({_where_literal_replacement(action)}),
    )
    rows: set[BindingItems] = set()
    for binding in bindings:
        rows.add(normalize_binding_items((var, binding[var]) for var in rule_spec.select_vars))
    return tuple(sorted(rows, key=_binding_items_sort_key))


def _where_literal_replacement(
    action: RuleLiteralReplaceAction,
) -> WhereLiteralReplacement:
    return WhereLiteralReplacement(
        branch_index=action.branch_index,
        atom_index=action.atom_index,
        literal_path=_core_literal_path(action.literal_path),
        old_literal=action.old_literal,
        new_literal=action.new_literal,
    )


def _core_literal_path(path: RuleLiteralPath) -> tuple[str, int | None]:
    return (path.kind, path.index)


def _validate_action_target(
    action: RuleLiteralReplaceAction,
    atom: tuple[Any, ...],
) -> ErrorDTO | None:
    if atom[0] not in _REPLACE_SUPPORTED_ATOM_KINDS:
        return ErrorDTO(
            code="RULE_LITERAL_REPLACE_ATOM_UNSUPPORTED",
            message="Rule Literal Replace target atom kind is not supported in Batch 5b",
            path=("overlay", "rule_actions", "0", "literal_path"),
            details={"atom_kind": atom[0]},
        )
    try:
        current = _literal_at_path(atom, action.literal_path)
    except ValueError as exc:
        return ErrorDTO(
            code="RULE_LITERAL_REPLACE_PATH_INVALID",
            message="RuleLiteralReplaceAction literal_path is incompatible with target atom",
            path=("overlay", "rule_actions", "0", "literal_path"),
            details={"reason": str(exc)},
        )
    if not _is_native_literal(current) or current != action.old_literal:
        return ErrorDTO(
            code="RULE_LITERAL_REPLACE_STALE_LITERAL",
            message="RuleLiteralReplaceAction old_literal does not match current target literal",
            path=("overlay", "rule_actions", "0", "old_literal"),
            details={"current_literal": repr(current)},
        )
    if not _is_native_literal(action.new_literal):
        return ErrorDTO(
            code="RULE_LITERAL_REPLACE_NEW_LITERAL_INVALID",
            message="RuleLiteralReplaceAction new_literal must be bool, int, or non-variable string",
            path=("overlay", "rule_actions", "0", "new_literal"),
            details={"new_literal": repr(action.new_literal)},
        )
    return None


def _literal_at_path(atom: tuple[Any, ...], path: RuleLiteralPath) -> Any:
    kind = path.kind
    index = path.index
    atom_kind = atom[0]
    if kind == "pred_term":
        if atom_kind != "pred" or index is None:
            raise ValueError("pred_term path requires pred atom and index")
        terms = atom[2]
        if index >= len(terms):
            raise ValueError("pred_term index out of range")
        return terms[index]
    if kind == "lhs":
        if atom_kind not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise ValueError("lhs path requires comparison/filter atom")
        return atom[1]
    if kind == "rhs":
        if atom_kind not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise ValueError("rhs path requires comparison/filter atom")
        return atom[2]
    if kind == "in_value":
        if atom_kind != "in" or index is None:
            raise ValueError("in_value path requires in atom and index")
        values = atom[2]
        if index >= len(values):
            raise ValueError("in_value index out of range")
        return values[index]
    if kind == "const_operand":
        if atom_kind not in {"addc", "mulc"}:
            raise ValueError("const_operand path requires addc or mulc atom")
        return atom[3]
    raise ValueError("unsupported literal path kind")


def _is_native_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    return isinstance(value, str) and not value.startswith("$")


def _build_proof_frame_result(
    artifact: SupportArtifact,
    *,
    action_index: int,
    action: RuleLiteralReplaceAction,
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


def _atom_key_prefix(action: RuleLiteralReplaceAction) -> str:
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
) -> RuleLiteralReplaceResult:
    return RuleLiteralReplaceResult(
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
) -> RuleLiteralReplaceResult:
    return RuleLiteralReplaceResult(
        status="invalid_request",
        variant_rows=(),
        proof_frame=None,
        errors=(ErrorDTO(code=code, message=message, path=path, details=details or {}),),
        warnings=(),
    )


__all__ = ["check_rule_literal_replace_action"]
