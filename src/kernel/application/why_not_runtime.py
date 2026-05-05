"""Application-layer Why-not Universe Diagnose runtime executor.

Step 2 scope is board assembly only: evaluate the selected derivation plan,
extract comparable head bindings, and partition the explicit candidate universe
into green and red rows. Step 3 replaces the provisional coarse red-row
diagnostics with Sibling-with-Diagnose mapping.
"""
from __future__ import annotations

from typing import Any

from kernel.core.derivation.candidates import CandidateSet
from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry
from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.store._support import BindingItems, SupportArtifact, normalize_binding_items
from kernel.core.store.runtime import Store
from kernel.core.view.projector import project_view_facts

from .derivation_runtime import evaluate_derivation_plans
from .protocol import (
    DerivationEvaluateRequest,
    ErrorDTO,
    WhyNotRedRow,
    WhyNotRowDiagnostic,
    WhyNotUniverseRequest,
    WhyNotUniverseResult,
)

_UNREPRESENTABLE_TERM = object()
_UNREPRESENTABLE_BINDING = object()


class WhyNotRuntimeError(ValueError):
    """Runtime-level Why-not failure that cannot be expressed as a result DTO."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def check_why_not_universe(
    request: WhyNotUniverseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> WhyNotUniverseResult:
    """Assemble a red/green board for an explicit finite head-binding universe."""

    if not request.candidate_universe:
        return WhyNotUniverseResult(
            status="completed",
            requested_universe=request.candidate_universe,
            green=(),
            red=(),
            errors=(),
            warnings=(),
        )

    body = list(request.plan.body_ir)
    ruleref_errors = _ruleref_preflight(body, registry)
    if ruleref_errors:
        return _invalid_request(request, errors=ruleref_errors)

    if request.engine == "native":
        extracted = _native_head_bindings(request, store=store, registry=registry)
    elif request.engine == "souffle":
        extracted = _souffle_head_bindings(request, store=store, registry=registry)
    elif request.engine in {"problog", "pyreason"}:
        representability_errors = _problog_pyreason_representability_precheck(request)
        if representability_errors:
            return _unsupported(request, errors=representability_errors)
        extracted = _problog_pyreason_head_bindings(
            request,
            store=store,
            registry=registry,
        )
    else:
        raise WhyNotRuntimeError(
            f"unknown Why-not engine: {request.engine}",
            code="WHY_NOT_INTERNAL_UNKNOWN_ENGINE",
            details={"engine": request.engine},
        )

    if isinstance(extracted, _UnsupportedHeadBindings):
        return _unsupported(request, errors=extracted.errors)

    derived_bindings = _dedupe_bindings(extracted)
    green: list[BindingItems] = []
    red: list[WhyNotRedRow] = []
    for binding in request.candidate_universe:
        if _binding_in(binding, derived_bindings):
            green.append(binding)
            continue
        red.append(
            WhyNotRedRow(
                binding=binding,
                diagnostic=_coarse_no_candidate_diagnostic(),
            )
        )

    return WhyNotUniverseResult(
        status="completed",
        requested_universe=request.candidate_universe,
        green=tuple(green),
        red=tuple(red),
        errors=(),
        warnings=(),
    )


class _UnsupportedHeadBindings:
    def __init__(self, errors: tuple[ErrorDTO, ...]) -> None:
        self.errors = errors


def _native_head_bindings(
    request: WhyNotUniverseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> tuple[BindingItems, ...] | _UnsupportedHeadBindings:
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    evaluation = evaluate_native_where(
        view_facts,
        list(request.plan.body_ir),
        registry=registry,
    )

    bindings: list[BindingItems] = []
    for final_binding in evaluation.bindings:
        extracted = _extract_head_binding_from_mapping(final_binding, request.plan)
        if extracted is _UNREPRESENTABLE_BINDING:
            return _unrepresentable_candidate_error(
                request,
                engine="native",
                reason="native final binding did not contain all plan head variables",
            )
        bindings.append(extracted)
    return tuple(bindings)


def _souffle_head_bindings(
    request: WhyNotUniverseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> tuple[BindingItems, ...] | _UnsupportedHeadBindings:
    candidates = evaluate_derivation_plans(
        DerivationEvaluateRequest(plans=(request.plan,), engine="souffle"),
        store=store,
        registry=registry,
    )

    bindings: list[BindingItems] = []
    for candidate in candidates:
        artifact = _lookup_support_artifact(store, candidate.support_digest)
        if artifact is None:
            return _UnsupportedHeadBindings(
                (
                    ErrorDTO(
                        code="EVIDENCE_LOOKUP_MISS",
                        message=(
                            "souffle candidate advertised witness support but lookup "
                            "returned None"
                        ),
                        path=("candidates",),
                        details={
                            "engine": "souffle",
                            "support_kind": candidate.support_kind,
                            "support_digest": candidate.support_digest,
                            "candidate_key": candidate.candidate_key,
                        },
                    ),
                )
            )
        extracted = _extract_head_binding_from_mapping(
            dict(artifact.binding_items),
            request.plan,
        )
        if extracted is _UNREPRESENTABLE_BINDING:
            return _unrepresentable_candidate_error(
                request,
                engine="souffle",
                reason="support artifact binding did not contain all plan head variables",
                candidate=candidate,
            )
        bindings.append(extracted)
    return tuple(bindings)


def _problog_pyreason_head_bindings(
    request: WhyNotUniverseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> tuple[BindingItems, ...] | _UnsupportedHeadBindings:
    candidates = evaluate_derivation_plans(
        DerivationEvaluateRequest(plans=(request.plan,), engine=request.engine),
        store=store,
        registry=registry,
    )

    bindings: list[BindingItems] = []
    for candidate in candidates:
        extracted = _extract_head_binding_from_candidate_payload(
            candidate=candidate,
            plan=request.plan,
        )
        if extracted is _UNREPRESENTABLE_BINDING:
            return _unrepresentable_candidate_error(
                request,
                engine=request.engine,
                reason="candidate payload did not expose all plan head variables",
                candidate=candidate,
            )
        bindings.append(extracted)
    return tuple(bindings)


def _extract_head_binding_from_mapping(
    source: dict[str, Any],
    plan: Any,
) -> BindingItems | object:
    binding: dict[str, Any] = {}
    for var_name in _head_vars(plan):
        if var_name not in source:
            return _UNREPRESENTABLE_BINDING
        binding[var_name] = source[var_name]
    return normalize_binding_items(binding)


def _extract_head_binding_from_candidate_payload(
    *,
    candidate: CandidateSet,
    plan: Any,
) -> BindingItems | object:
    payload = candidate.payload
    if not isinstance(payload, dict):
        return _UNREPRESENTABLE_BINDING
    terms = payload.get("terms")
    head_terms = plan.heads[0].head_var_names
    if not isinstance(terms, list) or len(terms) != len(head_terms):
        return _UNREPRESENTABLE_BINDING

    binding: dict[str, Any] = {}
    for var_name, term in zip(head_terms, terms):
        if not _is_head_var(var_name):
            continue
        value = _extract_term_value(term)
        if value is _UNREPRESENTABLE_TERM:
            return _UNREPRESENTABLE_BINDING
        binding[var_name] = value
    return normalize_binding_items(binding)


def _extract_term_value(term: Any) -> Any:
    if isinstance(term, dict):
        kind = term.get("kind")
        if kind == "candidate_ref":
            return _UNREPRESENTABLE_TERM
        return term.get("value")
    if isinstance(term, tuple) and len(term) == 2:
        return term[1]
    return None


def _head_vars(plan: Any) -> tuple[str, ...]:
    return tuple(name for name in plan.heads[0].head_var_names if _is_head_var(name))


def _is_head_var(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$") and len(value) > 1


def _dedupe_bindings(bindings: tuple[BindingItems, ...]) -> tuple[BindingItems, ...]:
    deduped: list[BindingItems] = []
    for binding in bindings:
        if not _binding_in(binding, deduped):
            deduped.append(binding)
    return tuple(deduped)


def _binding_in(
    binding: BindingItems,
    haystack: tuple[BindingItems, ...] | list[BindingItems],
) -> bool:
    return any(existing == binding for existing in haystack)


def _coarse_no_candidate_diagnostic() -> WhyNotRowDiagnostic:
    return WhyNotRowDiagnostic(
        status="failed",
        failure_kind="no_candidate",
        diagnostic_granularity="coarse",
        atom_locator=None,
        errors=(),
        warnings=(),
    )


def _problog_pyreason_representability_precheck(
    request: WhyNotUniverseRequest,
) -> tuple[ErrorDTO, ...]:
    if request.engine not in {"problog", "pyreason"}:
        return ()
    head_spec = request.plan.head_spec
    if isinstance(head_spec, dict) and head_spec.get("callee_kind") == "entity_type":
        return (
            ErrorDTO(
                code="ENTITY_TARGET_NOT_REPRESENTABLE",
                message=(
                    f"engine={request.engine!r} Why-not does not support "
                    "entity-targeted plans in MVP"
                ),
                path=("plan", "head_spec"),
                details={"engine": request.engine},
            ),
        )
    return ()


def _unrepresentable_candidate_error(
    request: WhyNotUniverseRequest,
    *,
    engine: str,
    reason: str,
    candidate: CandidateSet | None = None,
) -> _UnsupportedHeadBindings:
    details: dict[str, Any] = {
        "engine": engine,
        "reason": reason,
        "head_variables": list(_head_vars(request.plan)),
    }
    if candidate is not None:
        details.update(
            {
                "candidate_key": candidate.candidate_key,
                "support_kind": candidate.support_kind,
            }
        )
    return _UnsupportedHeadBindings(
        (
            ErrorDTO(
                code="CANDIDATE_BINDING_NOT_REPRESENTABLE",
                message=(
                    f"engine={engine!r} Why-not could not extract comparable "
                    "head bindings from derived candidates"
                ),
                path=("candidates",),
                details=details,
            ),
        )
    )


def _lookup_support_artifact(store: Store, digest: str) -> SupportArtifact | None:
    return store._lookup_support_artifact(digest)


def _invalid_request(
    request: WhyNotUniverseRequest,
    *,
    errors: tuple[ErrorDTO, ...],
) -> WhyNotUniverseResult:
    return WhyNotUniverseResult(
        status="invalid_request",
        requested_universe=request.candidate_universe,
        green=(),
        red=(),
        errors=errors,
        warnings=(),
    )


def _unsupported(
    request: WhyNotUniverseRequest,
    *,
    errors: tuple[ErrorDTO, ...],
) -> WhyNotUniverseResult:
    return WhyNotUniverseResult(
        status="unsupported",
        requested_universe=request.candidate_universe,
        green=(),
        red=(),
        errors=errors,
        warnings=(),
    )


def _find_ruleref_atoms(body: list[Any]) -> list[tuple[Any, ...]]:
    if not body:
        return []
    if all(isinstance(item, list) for item in body):
        atoms_flat: list[Any] = [atom for branch in body for atom in branch]
    else:
        atoms_flat = list(body)
    return [
        atom
        for atom in atoms_flat
        if isinstance(atom, tuple) and atom and atom[0] == "ruleref"
    ]


def _ruleref_preflight(
    body: list[Any],
    registry: RuleRegistry | None,
) -> tuple[ErrorDTO, ...]:
    ruleref_atoms = _find_ruleref_atoms(body)
    if not ruleref_atoms:
        return ()
    if registry is None:
        return (
            ErrorDTO(
                code="REGISTRY_REQUIRED",
                message=(
                    "rule body contains ruleref atoms but no registry was provided"
                ),
                path=("registry",),
                details={"ruleref_count": len(ruleref_atoms)},
            ),
        )
    errors: list[ErrorDTO] = []
    seen: set[tuple[str, str]] = set()
    for atom in ruleref_atoms:
        if len(atom) < 4:
            continue
        rule_id = atom[1] if isinstance(atom[1], str) else None
        version = atom[2] if isinstance(atom[2], str) else None
        if rule_id is None or version is None:
            continue
        key = (rule_id, version)
        if key in seen:
            continue
        seen.add(key)
        try:
            registry.resolve(rule_id, version)
        except RuleCompileError as exc:
            errors.append(
                ErrorDTO(
                    code="RULE_REF_UNRESOLVABLE",
                    message=f"ruleref {rule_id}@{version} could not be resolved",
                    path=("registry",),
                    details={
                        "rule_id": rule_id,
                        "version": version,
                        "reason": str(exc),
                    },
                )
            )
    return tuple(errors)


__all__ = [
    "WhyNotRuntimeError",
    "check_why_not_universe",
]
