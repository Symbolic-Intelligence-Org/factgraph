from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, TypeAlias, cast

from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    OrExpr,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    WhereExpr,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store import builders
from factgraph.core.store._support import (
    _DEGRADED_SUPPORT_KINDS,
    _PROVENANCE_BEARING_SUPPORT_KINDS,
    _WITNESS_BEARING_SUPPORT_KINDS,
    ENGINE_NO_WITNESS_KIND,
    BindingSupportCapture,
    ProjectedFact,
    ProofReceipt,
    compute_support_digest,
    normalize_binding_items,
)
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_matching_case_indexes,
    find_winning_case_index,
)
from factgraph.core.store.premise_filter import premise_scoped_ledger
from factgraph.core.store.types import (
    EngineEvaluatorFn,
    EngineExtBase,
    EngineOptionsIR,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    WhereIR,
)
from factgraph.core.view.projector import project_view_facts, project_view_facts_with_witness

_NativeEffectiveRelationSnapshot: TypeAlias = Mapping[
    str, tuple[ProjectedFact, ...]
]
_NativeEffectiveRelationObserver: TypeAlias = Callable[
    [_NativeEffectiveRelationSnapshot], None
]
_NativeEffectiveRelationSupportArtifactObserver: TypeAlias = Callable[
    [str, ProofReceipt], None
]


def evaluate_store(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: HeadVarsIR,
    where: WhereIR,
    mode: EvaluateMode = "native",
    head: HeadSpecIR | None = None,
    engine_evaluate: EngineEvaluatorFn,
    registry: Any | None = None,
    confidence_kind_resolver: Any | None = None,
    engine_ext: EngineExtBase | None = None,
    engine_options: EngineOptionsIR = None,
    semantics_profile: Any | None = None,
) -> list[DerivationOutput]:
    """Public evaluation entrypoint; native relation capture is not exposed here."""
    return _evaluate_store(
        store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        head_vars=head_vars,
        where=where,
        mode=mode,
        head=head,
        engine_evaluate=engine_evaluate,
        registry=registry,
        confidence_kind_resolver=confidence_kind_resolver,
        engine_ext=engine_ext,
        engine_options=engine_options,
        semantics_profile=semantics_profile,
        _native_effective_relation_observer=None,
    )


def _evaluate_store(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: HeadVarsIR,
    where: WhereIR,
    mode: EvaluateMode = "native",
    head: HeadSpecIR | None = None,
    engine_evaluate: EngineEvaluatorFn,
    registry: Any | None = None,
    confidence_kind_resolver: Any | None = None,
    engine_ext: EngineExtBase | None = None,
    engine_options: EngineOptionsIR = None,
    semantics_profile: Any | None = None,
    _native_effective_relation_observer: _NativeEffectiveRelationObserver | None = None,
    _native_effective_relation_override: _NativeEffectiveRelationSnapshot | None = None,
    _record_support_artifacts: bool = True,
    _capture_witness_metadata: bool = False,
    _native_effective_relation_support_artifact_observer: (
        _NativeEffectiveRelationSupportArtifactObserver | None
    ) = None,
) -> list[DerivationOutput]:
    if mode == "python":
        raise ValueError("mode='python' is removed; use mode='native'")
    if mode == "engine":
        raise ValueError("mode='engine' is removed; use mode='souffle'")
    if mode not in {"native", "souffle", "problog", "pyreason"}:
        raise ValueError("mode must be one of: native, souffle, problog, pyreason")
    if engine_ext is not None and not isinstance(engine_ext, EngineExtBase):
        raise ValueError(
            f"engine_ext must be an EngineExtBase instance, got {type(engine_ext).__name__}"
        )
    if engine_options is not None and not isinstance(engine_options, dict):
        raise ValueError(
            f"engine_options must be dict[str, Any] or None, got {type(engine_options).__name__}"
        )
    if semantics_profile is not None:
        profile_engine = getattr(semantics_profile, "engine", None)
        if mode not in {"problog", "pyreason"}:
            if profile_engine in {"problog", "pyreason"}:
                raise ValueError(
                    f"semantics_profile with SemanticsProfile.engine={profile_engine!r} requires mode='{profile_engine}'"
                )
            raise ValueError("semantics_profile is only supported for mode='problog' or mode='pyreason'")
        if profile_engine != mode:
            raise ValueError(
                f"{mode} consumption expected SemanticsProfile.engine='{mode}', got {profile_engine!r}"
            )
    if mode == "native" and engine_options:
        raise ValueError("engine_options are not supported for mode='native'")
    if _native_effective_relation_observer is not None:
        if not callable(_native_effective_relation_observer):
            raise TypeError("_native_effective_relation_observer must be callable or None")
        if mode != "native":
            raise ValueError(
                "_native_effective_relation_observer is only supported for mode='native'"
            )
        if registry is not None:
            raise ValueError(
                "_native_effective_relation_observer does not support registry-backed evaluation"
            )
    if not isinstance(_record_support_artifacts, bool):
        raise TypeError("_record_support_artifacts must be bool")
    if not _record_support_artifacts and mode != "native":
        raise ValueError("_record_support_artifacts=False is only supported for mode='native'")
    if _native_effective_relation_override is not None:
        if mode != "native":
            raise ValueError(
                "_native_effective_relation_override is only supported for mode='native'"
            )
        if registry is not None:
            raise ValueError(
                "_native_effective_relation_override does not support registry-backed evaluation"
            )
        if _native_effective_relation_observer is not None:
            raise ValueError(
                "_native_effective_relation_override cannot be combined with native relation capture"
            )
        if _record_support_artifacts:
            raise ValueError(
                "_native_effective_relation_override requires _record_support_artifacts=False"
            )
        if (
            getattr(store, "premise_exclusions", ())
            or getattr(store, "premise_allowances", ())
            or getattr(store, "premise_blocks", ())
        ):
            raise ValueError(
                "_native_effective_relation_override does not support premise-filtered evaluation"
            )
    if _native_effective_relation_support_artifact_observer is not None:
        if not callable(_native_effective_relation_support_artifact_observer):
            raise TypeError(
                "_native_effective_relation_support_artifact_observer must be callable or None"
            )
        if (
            mode != "native"
            or registry is not None
            or _native_effective_relation_override is None
            or _record_support_artifacts
        ):
            raise ValueError(
                "_native_effective_relation_support_artifact_observer requires "
                "native effective-relation execution with durable support disabled"
            )

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        if mode in {"souffle", "problog", "pyreason"}:
            engine_kwargs = {
                "mode": mode,
                "derivation_id": derivation_id,
                "version": version,
                "target_pred_id": target_pred_id,
                "head_vars": head_vars,
                "where": where,
                "head": head,
            }
            if engine_ext is not None:
                engine_kwargs["engine_ext"] = engine_ext
            if engine_options is not None:
                engine_kwargs["engine_options"] = engine_options
            if semantics_profile is not None:
                engine_kwargs["semantics_profile"] = semantics_profile
            outputs = engine_evaluate(**engine_kwargs)
            _remember_output_support_backrefs(store, outputs)
            return outputs
        if mode != "native":
            raise ValueError("mode must be one of: native, souffle, problog, pyreason")

        entity_spec = builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        captures = _evaluate_where_over_view_with_support(
            store,
            where,
            root_result_kind="entity",
            _capture_witness_metadata=_capture_witness_metadata,
            registry=registry,
            _native_effective_relation_observer=_native_effective_relation_observer,
            _native_effective_relation_override=_native_effective_relation_override,
            _record_support_artifacts=_record_support_artifacts,
            _native_effective_relation_support_artifact_observer=(
                _native_effective_relation_support_artifact_observer
            ),
        )
        if not captures:
            return []
        outputs = builders.entity_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            rows=captures,
            confidence_kind_resolver=confidence_kind_resolver,
        )
        if _record_support_artifacts:
            _remember_output_support_backrefs(store, outputs)
        return outputs

    if mode in {"souffle", "problog", "pyreason"}:
        engine_kwargs = {
            "mode": mode,
            "derivation_id": derivation_id,
            "version": version,
            "target_pred_id": target_pred_id,
            "head_vars": head_vars,
            "where": where,
            "head": head,
        }
        if engine_ext is not None:
            engine_kwargs["engine_ext"] = engine_ext
        if engine_options is not None:
            engine_kwargs["engine_options"] = engine_options
        if semantics_profile is not None:
            engine_kwargs["semantics_profile"] = semantics_profile
        outputs = engine_evaluate(**engine_kwargs)
        _remember_output_support_backrefs(store, outputs)
        return outputs
    if mode != "native":
        raise ValueError("mode must be one of: native, souffle, problog, pyreason")

    schema_pred = builders.find_schema_pred(store, target_pred_id)
    arg_specs = None
    if schema_pred is not None:
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or not arg_specs:
            raise WhereValidationError("target predicate arg_specs must be non-empty list")
        if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
            raise WhereValidationError("head_vars length must match target arg_specs")
    elif not isinstance(head_vars, list) or not head_vars:
        raise WhereValidationError("head_vars must be non-empty list")

    captures = _evaluate_where_over_view_with_support(
        store,
        where,
        root_result_kind="fact",
        _capture_witness_metadata=_capture_witness_metadata,
        registry=registry,
        _native_effective_relation_observer=_native_effective_relation_observer,
        _native_effective_relation_override=_native_effective_relation_override,
        _record_support_artifacts=_record_support_artifacts,
        _native_effective_relation_support_artifact_observer=(
            _native_effective_relation_support_artifact_observer
        ),
    )
    if not captures:
        return []

    if schema_pred is None:
        outputs = builders.query_style_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            rows=captures,
            confidence_kind_resolver=confidence_kind_resolver,
        )
    else:
        outputs = builders.derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            arg_specs=arg_specs,
            head_vars=head_vars,
            schema_pred=schema_pred,
            rows=captures,
            confidence_kind_resolver=confidence_kind_resolver,
        )
    if _record_support_artifacts and not getattr(
        store, "_capture_all_query_style_supports", False
    ):
        _remember_output_support_backrefs(store, outputs)
    return outputs


def _evaluate_where_over_view(
    store: Any,
    where: WhereIR,
    *,
    registry: Any | None = None,
    witness_facts: Mapping[str, Sequence[ProjectedFact]] | None = None,
    ledger: Any | None = None,
    _record_support_artifacts: bool = True,
) -> Any:
    if ledger is None:
        # Premise admissibility: the native projection is the only fact
        # source of native evaluation; reading through the premise-scoped
        # ledger keeps excluded assertions out of support AND negation.
        # Zero-config returns store.ledger unchanged.
        ledger = premise_scoped_ledger(
            store.ledger,
            getattr(store, "premise_exclusions", ()),
            getattr(store, "premise_allowances", ()),
            getattr(store, "premise_blocks", ()),
        )
    view_facts = (
        project_view_facts(ledger, store.schema_ir)
        if witness_facts is None
        else _view_facts_from_projected_relation(witness_facts)
    )
    return evaluate_native_where(
        view_facts,
        where,
        registry=registry,
        witness_facts=cast(Any, witness_facts),
        remember_support_artifact=(
            store._remember_support_artifact
            if witness_facts is not None and _record_support_artifacts
            else None
        ),
    )


def _evaluate_where_over_view_with_support(
    store: Any,
    where: WhereIR,
    *,
    root_result_kind: str,
    registry: Any | None = None,
    _native_effective_relation_observer: _NativeEffectiveRelationObserver | None = None,
    _native_effective_relation_override: _NativeEffectiveRelationSnapshot | None = None,
    _record_support_artifacts: bool = True,
    _capture_witness_metadata: bool = False,
    _native_effective_relation_support_artifact_observer: (
        _NativeEffectiveRelationSupportArtifactObserver | None
    ) = None,
) -> list[BindingSupportCapture]:
    if _native_effective_relation_observer is not None and registry is not None:
        raise ValueError(
            "_native_effective_relation_observer does not support registry-backed evaluation"
        )
    if not isinstance(_record_support_artifacts, bool):
        raise TypeError("_record_support_artifacts must be bool")
    if _native_effective_relation_support_artifact_observer is not None:
        if not callable(_native_effective_relation_support_artifact_observer):
            raise TypeError(
                "_native_effective_relation_support_artifact_observer must be callable or None"
            )
        if (
            _native_effective_relation_override is None
            or _record_support_artifacts
            or registry is not None
        ):
            raise ValueError(
                "_native_effective_relation_support_artifact_observer requires "
                "an override relation and disabled durable support"
            )
    if _native_effective_relation_override is not None:
        if _native_effective_relation_observer is not None:
            raise ValueError(
                "_native_effective_relation_override cannot be combined with native relation capture"
            )
        if _record_support_artifacts:
            raise ValueError(
                "_native_effective_relation_override requires _record_support_artifacts=False"
            )
        if (
            getattr(store, "premise_exclusions", ())
            or getattr(store, "premise_allowances", ())
            or getattr(store, "premise_blocks", ())
        ):
            raise ValueError(
                "_native_effective_relation_override does not support premise-filtered evaluation"
            )
        dependency_predicates = _native_where_dependency_predicates(where)
        actual_predicates = tuple(sorted(_native_effective_relation_override))
        expected_predicates = tuple(sorted(dependency_predicates))
        if actual_predicates != expected_predicates:
            raise ValueError(
                "native effective relation override must exactly cover query dependencies"
            )
        witness_facts: Mapping[str, Sequence[ProjectedFact]] = _immutable_effective_relation_copy(
            _native_effective_relation_override
        )
        ledger = store.ledger
    else:
        # One premise-scoped view per evaluate call, shared between the witness
        # projection and the native where evaluation; visibility is decided live
        # per access inside the view (see premise_filter.py).
        ledger = premise_scoped_ledger(
            store.ledger,
            getattr(store, "premise_exclusions", ()),
            getattr(store, "premise_allowances", ()),
            getattr(store, "premise_blocks", ()),
        )
        witness_facts = project_view_facts_with_witness(ledger, store.schema_ir)
    if _native_effective_relation_observer is not None:
        dependency_predicates = _native_where_dependency_predicates(where)
        reduced_relation = {
            pred_id: witness_facts[pred_id]
            for pred_id in dependency_predicates
            if pred_id in witness_facts
        }
        missing_dependencies = tuple(
            pred_id
            for pred_id in dependency_predicates
            if pred_id not in witness_facts
        )
        if missing_dependencies:
            raise ValueError(
                "native effective relation dependencies are absent from schema projection: "
                + ", ".join(missing_dependencies)
            )
        # Freeze once: capture and evaluator consume the exact same relation
        # object rather than independently copied/filterable representations.
        witness_facts = _immutable_effective_relation_copy(reduced_relation)
        _native_effective_relation_observer(witness_facts)
    evaluation = _evaluate_where_over_view(
        store,
        where,
        registry=registry,
        witness_facts=witness_facts,
        ledger=ledger,
        _record_support_artifacts=_record_support_artifacts,
    )
    bindings = evaluation.bindings
    if not bindings:
        return []

    if (
        not _record_support_artifacts
        and _native_effective_relation_support_artifact_observer is None
    ):
        captures = [
            BindingSupportCapture(
                binding_items=normalize_binding_items(binding),
                support_digest=f"sha256:{'0' * 64}",
                support_kind=ENGINE_NO_WITNESS_KIND,
            )
            for binding in bindings
        ]
        captures.sort(key=lambda row: (row.binding_items, row.support_digest, row.support_kind))
        return captures

    captures: list[BindingSupportCapture] = []
    for binding in bindings:
        if getattr(store, "_capture_all_query_style_supports", False):
            selected_case_indexes = find_matching_case_indexes(
                where=where,
                binding=binding,
                witness_facts=cast(Any, witness_facts),
                rule_ref_resolutions=evaluation.rule_ref_resolutions,
            )
        else:
            selected_case_indexes = (
                find_winning_case_index(
                    where=where,
                    binding=binding,
                    witness_facts=cast(Any, witness_facts),
                    rule_ref_resolutions=evaluation.rule_ref_resolutions,
                ),
            )
        for selected_case_index in selected_case_indexes:
            rule_ref_edges = derive_rule_ref_edges_for_binding(
                where=where,
                binding=binding,
                rule_ref_resolutions=evaluation.rule_ref_resolutions,
                selected_case_index=selected_case_index,
            )
            artifact = build_support_artifact_for_binding(
                capture_witness_metadata=_capture_witness_metadata,
                where=where,
                binding=binding,
                witness_facts=cast(Any, witness_facts),
                root_result_kind=root_result_kind,
                selected_case_index=selected_case_index,
                rule_ref_edges=rule_ref_edges,
            )
            support_digest = compute_support_digest(artifact)
            if _record_support_artifacts:
                store._remember_support_artifact(support_digest, artifact)
            else:
                assert _native_effective_relation_support_artifact_observer is not None
                _native_effective_relation_support_artifact_observer(support_digest, artifact)
            captures.append(
                BindingSupportCapture(
                    binding_items=artifact.binding_items,
                    support_digest=support_digest,
                    support_kind=artifact.kind,
                )
            )
    captures.sort(key=lambda row: (row.binding_items, row.support_digest, row.support_kind))
    return captures


def _view_facts_from_projected_relation(
    projected_relation: Mapping[str, Sequence[ProjectedFact]],
) -> dict[str, list[tuple[Any, ...]]]:
    """Derive the evaluator input from the already-projected witness relation."""

    return {
        pred_id: [row.fact_tuple for row in rows]
        for pred_id, rows in projected_relation.items()
    }


def _immutable_effective_relation_copy(
    projected_relation: Mapping[str, Sequence[ProjectedFact]],
) -> _NativeEffectiveRelationSnapshot:
    """Copy a projected native relation into a callback-safe immutable shape."""

    return MappingProxyType(
        {
            pred_id: tuple(
                ProjectedFact(asrt_id=row.asrt_id, fact_tuple=tuple(row.fact_tuple))
                for row in rows
            )
            for pred_id, rows in projected_relation.items()
        }
    )


def _native_where_dependency_predicates(where: WhereIR) -> tuple[str, ...]:
    """Return the exact predicate dependency set for supported native WhereIR."""

    expression = parse_where_ir_to_ast(where)
    predicates: set[str] = set()
    _collect_where_expr_predicates(expression, predicates)
    return tuple(sorted(predicates))


def _collect_where_expr_predicates(
    expression: WhereExpr,
    predicates: set[str],
) -> None:
    branches = expression.branches if isinstance(expression, OrExpr) else (expression,)
    for branch in branches:
        for atom in branch.atoms:
            _collect_atom_predicates(atom, predicates)


def _collect_atom_predicates(atom: Atom, predicates: set[str]) -> None:
    if isinstance(atom, PredAtom):
        if not isinstance(atom.pred_id, str) or not atom.pred_id:
            raise ValueError("native effective relation predicate id must be non-empty string")
        predicates.add(atom.pred_id)
        for term in atom.terms:
            _collect_term_predicates(term, predicates)
        return
    if isinstance(atom, NotAtom):
        _collect_where_expr_predicates(atom.body, predicates)
        return
    if isinstance(atom, RuleRefAtom):
        raise ValueError(  # noqa: TRY004 - Wrapped by scenario dependency resolution (SCENARIO_QUERY_DEPENDENCY_UNSUPPORTED).
            "native effective relation capture requires materialized where without ruleref atoms"
        )
    if isinstance(atom, CmpAtom):
        _collect_term_predicates(atom.lhs, predicates)
        _collect_term_predicates(atom.rhs, predicates)
        return
    if isinstance(atom, InAtom):
        _collect_term_predicates(atom.var, predicates)
        for value in atom.values:
            _collect_term_predicates(value, predicates)
        return
    if isinstance(atom, BuiltinAtom):
        for term in atom.args:
            _collect_term_predicates(term, predicates)
        return
    raise ValueError(
        "native effective relation dependency analysis does not support "
        f"{type(atom).__name__}"
    )


def _collect_term_predicates(term: Term, predicates: set[str]) -> None:
    if isinstance(term, AggregateAtom):
        if term.target is not None:
            _collect_term_predicates(term.target, predicates)
        for atom in term.filter:
            _collect_atom_predicates(atom, predicates)
        return
    if isinstance(term, (Var, Const)):
        return
    raise ValueError(
        "native effective relation dependency analysis does not support "
        f"{type(term).__name__}"
    )


def _remember_output_support_backrefs(
    store: Any,
    outputs: list[DerivationOutput],
) -> None:
    if not outputs:
        return

    for output in outputs:
        support_kind = output.support_kind
        support_digest = output.support_digest
        if support_kind in _DEGRADED_SUPPORT_KINDS or support_kind in _PROVENANCE_BEARING_SUPPORT_KINDS:
            store._remember_candidate_support(
                output.candidate_id,
                support_digest,
                support_kind,
                confidence_kind=output.confidence_kind,
                target_pred_id=output.target,
            )
            continue
        if support_kind not in _WITNESS_BEARING_SUPPORT_KINDS:
            continue
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            continue
        if support_digest == f"sha256:{'0' * 64}":
            continue
        store._remember_candidate_support(
            output.candidate_id,
            support_digest,
            support_kind,
            confidence_kind=output.confidence_kind,
            target_pred_id=output.target,
        )
