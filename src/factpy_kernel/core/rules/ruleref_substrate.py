from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from factpy_kernel.core.rules.ruleref_common import internal_rule_pred_id, resolve_exposed_rule_ref
from factpy_kernel.core.rules.ruleref_types import NativeRuleRefResolution, NativeRuleRefRowSupport
from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where
from factpy_kernel.core.store._support import ProjectedFact, SupportArtifact, compute_support_digest
from factpy_kernel.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_branch_index,
)


@dataclass(frozen=True)
class NativeWhereEvaluation:
    bindings: list[dict[str, Any]]
    rule_refs: tuple[str, ...] = ()
    rule_ref_resolutions: tuple[NativeRuleRefResolution, ...] = ()


@dataclass(frozen=True)
class _RegisteredRuleEvaluation:
    rows: tuple[tuple[Any, ...], ...]
    row_supports: tuple[NativeRuleRefRowSupport, ...]


def evaluate_native_where(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: Any | None = None,
    witness_facts: dict[str, list[ProjectedFact]] | None = None,
    remember_support_artifact: Callable[[str, SupportArtifact], None] | None = None,
) -> NativeWhereEvaluation:
    memo_outputs: dict[tuple[str, str], _RegisteredRuleEvaluation] = {}
    stack: set[tuple[str, str]] = set()
    return _evaluate_native_where_internal(
        view_facts,
        where,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=remember_support_artifact,
        memo_outputs=memo_outputs,
        stack=stack,
    )


def _evaluate_native_where_internal(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: Any | None,
    witness_facts: dict[str, list[ProjectedFact]] | None,
    remember_support_artifact: Callable[[str, SupportArtifact], None] | None,
    memo_outputs: dict[tuple[str, str], _RegisteredRuleEvaluation],
    stack: set[tuple[str, str]],
) -> NativeWhereEvaluation:
    has_ruleref = _contains_ruleref_atom(where)
    if registry is None:
        if has_ruleref:
            raise WhereValidationError("RuleRef execution requires explicit RuleRegistry")
        return NativeWhereEvaluation(bindings=evaluate_where(view_facts, where))

    if has_ruleref:
        _validate_where_for_ruleref(where)
        rewritten_where, overlay, resolutions = _rewrite_where_rule_refs(
            where,
            registry=registry,
            base_view_facts=view_facts,
            witness_facts=witness_facts,
            remember_support_artifact=remember_support_artifact,
            memo_outputs=memo_outputs,
            stack=stack,
        )
        resolved_view_facts = dict(view_facts)
        resolved_view_facts.update(overlay)
        bindings = evaluate_where(resolved_view_facts, rewritten_where)
        return NativeWhereEvaluation(
            bindings=bindings,
            rule_refs=tuple(sorted({row.rule_ref_id for row in resolutions})),
            rule_ref_resolutions=tuple(sorted(resolutions, key=lambda row: row.ruleref_atom_key)),
        )

    return NativeWhereEvaluation(bindings=evaluate_where(view_facts, where))


def _validate_where_for_ruleref(where: list[Any]) -> None:
    try:
        ast = parse_where_ir_to_ast(where)
        validate_where_ast(
            ast,
            mode="python",
            capabilities={"allow_ruleref": True},
        )
    except (WhereASTError, WhereASTValidationError) as exc:
        adapted = WhereValidationError(str(exc))
        setattr(adapted, "path", getattr(exc, "path", None) or "$.where")
        raise adapted from exc


def _rewrite_where_rule_refs(
    where: list[Any],
    *,
    registry: Any,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    witness_facts: dict[str, list[ProjectedFact]] | None,
    remember_support_artifact: Callable[[str, SupportArtifact], None] | None,
    memo_outputs: dict[tuple[str, str], _RegisteredRuleEvaluation],
    stack: set[tuple[str, str]],
) -> tuple[list[Any], dict[str, list[tuple[Any, ...]]], tuple[NativeRuleRefResolution, ...]]:
    overlay: dict[str, list[tuple[Any, ...]]] = {}
    resolutions: list[NativeRuleRefResolution] = []

    def rewrite_atom(branch_index: int, atom_index: int, atom: Any) -> Any:
        if not isinstance(atom, tuple) or not atom:
            return atom
        if atom[0] != "ruleref":
            return atom
        if len(atom) != 4:
            raise WhereValidationError("ruleref atom must be ('ruleref', rule_id, version, [terms...])")
        _, rule_id, version, terms = atom
        if not isinstance(terms, list):
            raise WhereValidationError("ruleref atom terms must be list")
        ref_spec = resolve_exposed_rule_ref(
            registry,
            rule_id=rule_id,
            version=version,
            terms_len=len(terms),
            error_factory=WhereValidationError,
        )
        registered = _evaluate_registered_rule_output(
            ref_spec,
            base_view_facts=base_view_facts,
            witness_facts=witness_facts,
            registry=registry,
            remember_support_artifact=remember_support_artifact,
            memo_outputs=memo_outputs,
            stack=stack,
        )
        pred_id = internal_rule_pred_id(ref_spec.rule_id, ref_spec.version)
        overlay[pred_id] = list(registered.rows)
        resolutions.append(
            NativeRuleRefResolution(
                ruleref_atom_key=f"b{branch_index}.a{atom_index}:ruleref",
                rule_ref_id=ref_spec.rule_id,
                rule_ref_version=ref_spec.version,
                row_supports=registered.row_supports,
            )
        )
        return ("pred", pred_id, terms)

    if all(isinstance(item, tuple) for item in where):
        return (
            [rewrite_atom(0, atom_index, atom) for atom_index, atom in enumerate(where)],
            overlay,
            tuple(sorted(resolutions, key=lambda row: row.ruleref_atom_key)),
        )
    if all(isinstance(item, list) for item in where):
        out_branches: list[list[Any]] = []
        for branch_index, branch in enumerate(where):
            if not isinstance(branch, list):
                raise WhereValidationError("invalid where branch")
            out_branches.append(
                [rewrite_atom(branch_index, atom_index, atom) for atom_index, atom in enumerate(branch)]
            )
        return out_branches, overlay, tuple(sorted(resolutions, key=lambda row: row.ruleref_atom_key))
    return where, overlay, tuple()


def _evaluate_registered_rule_output(
    rule_spec: Any,
    *,
    base_view_facts: dict[str, list[tuple[Any, ...]]],
    witness_facts: dict[str, list[ProjectedFact]] | None,
    registry: Any,
    remember_support_artifact: Callable[[str, SupportArtifact], None] | None,
    memo_outputs: dict[tuple[str, str], _RegisteredRuleEvaluation],
    stack: set[tuple[str, str]],
) -> _RegisteredRuleEvaluation:
    key = (rule_spec.rule_id, rule_spec.version)
    if key in memo_outputs:
        return memo_outputs[key]
    if key in stack:
        raise WhereValidationError(f"RuleRef cycle detected at {rule_spec.rule_id}@{rule_spec.version}")

    stack.add(key)
    try:
        evaluation = _evaluate_native_where_internal(
            base_view_facts,
            rule_spec.where,
            registry=registry,
            witness_facts=witness_facts,
            remember_support_artifact=remember_support_artifact,
            memo_outputs=memo_outputs,
            stack=stack,
        )
        row_supports_by_terms: dict[tuple[Any, ...], NativeRuleRefRowSupport] = {}
        for binding in evaluation.bindings:
            row_terms = tuple(binding[var] for var in rule_spec.select_vars)
            row_support = _build_rule_row_support(
                rule_spec_where=rule_spec.where,
                binding=binding,
                row_terms=row_terms,
                witness_facts=witness_facts,
                remember_support_artifact=remember_support_artifact,
                child_rule_ref_resolutions=evaluation.rule_ref_resolutions,
            )
            existing = row_supports_by_terms.get(row_terms)
            if existing is None or _row_support_sort_key(row_support) < _row_support_sort_key(existing):
                row_supports_by_terms[row_terms] = row_support
        output = _RegisteredRuleEvaluation(
            rows=tuple(sorted(row_supports_by_terms.keys(), key=lambda row: tuple(str(cell) for cell in row))),
            row_supports=tuple(sorted(row_supports_by_terms.values(), key=_row_support_sort_key)),
        )
        memo_outputs[key] = output
        return output
    finally:
        stack.remove(key)


def _build_rule_row_support(
    *,
    rule_spec_where: list[Any],
    binding: dict[str, Any],
    row_terms: tuple[Any, ...],
    witness_facts: dict[str, list[ProjectedFact]] | None,
    remember_support_artifact: Callable[[str, SupportArtifact], None] | None,
    child_rule_ref_resolutions: tuple[NativeRuleRefResolution, ...],
) -> NativeRuleRefRowSupport:
    if witness_facts is None or remember_support_artifact is None:
        return NativeRuleRefRowSupport(
            row_terms=row_terms,
            child_support_digest=None,
            unresolved_reason="child_support_unavailable",
        )

    selected_branch_index = find_winning_branch_index(
        where=rule_spec_where,
        binding=binding,
        witness_facts=witness_facts,
        rule_ref_resolutions=child_rule_ref_resolutions,
    )
    rule_ref_edges = derive_rule_ref_edges_for_binding(
        where=rule_spec_where,
        binding=binding,
        rule_ref_resolutions=child_rule_ref_resolutions,
        selected_branch_index=selected_branch_index,
    )
    artifact = build_support_artifact_for_binding(
        where=rule_spec_where,
        binding=binding,
        witness_facts=witness_facts,
        root_result_kind="row",
        selected_branch_index=selected_branch_index,
        rule_ref_edges=rule_ref_edges,
    )
    support_digest = compute_support_digest(artifact)
    remember_support_artifact(support_digest, artifact)
    return NativeRuleRefRowSupport(
        row_terms=row_terms,
        child_support_digest=support_digest,
        unresolved_reason=None,
    )


def _row_support_sort_key(row: NativeRuleRefRowSupport) -> tuple[tuple[Any, ...], str, str]:
    return (
        row.row_terms,
        row.child_support_digest or "",
        row.unresolved_reason or "",
    )


def _contains_ruleref_atom(where: Any) -> bool:
    if isinstance(where, tuple):
        if where and where[0] == "ruleref":
            return True
        return any(_contains_ruleref_atom(item) for item in where[1:])
    if isinstance(where, list):
        return any(_contains_ruleref_atom(item) for item in where)
    return False


__all__ = ["NativeWhereEvaluation", "evaluate_native_where"]
