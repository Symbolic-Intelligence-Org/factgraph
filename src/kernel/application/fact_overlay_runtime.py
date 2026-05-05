"""Application-layer Fact Overlay Check runtime executor."""

from __future__ import annotations

from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry
from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.store._support import BindingItems, ProjectedFact, normalize_binding_items
from kernel.core.store.runtime import Store
from kernel.core.view.projector import project_view_facts_with_witness

from ._derivation_match_helpers import _binding_matches
from .protocol import (
    ErrorDTO,
    FactOverlayCheckRequest,
    FactOverlayCheckResult,
    OverlayCheckDiff,
    OverlayCheckPhase,
)


def check_fact_overlay_binding(
    request: FactOverlayCheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> FactOverlayCheckResult:
    """Evaluate Overlay Check.

    Step 3 scaffolding intentionally returns a degenerate native result:
    ``before == after`` with an empty diff. Step 4 replaces the ``after`` phase
    with the overlay-applied phase and builds the real diff.
    """

    if not request.overlay:
        return _invalid_request(
            request,
            errors=(
                ErrorDTO(
                    code="EMPTY_OVERLAY_NOT_PERMITTED",
                    message="Fact Overlay Check requires at least one fact override",
                    path=("overlay",),
                ),
            ),
        )

    body = list(request.plan.body_ir)
    ruleref_errors = _overlay_ruleref_preflight(body, registry)
    if ruleref_errors:
        return _invalid_request(request, errors=ruleref_errors)

    unsupported = _overlay_engine_support_preflight(request)
    if unsupported is not None:
        return unsupported

    projected_witness = project_view_facts_with_witness(store.ledger, store.schema_ir)
    phase = _run_native_overlay_phase(
        projected_witness,
        plan_body=body,
        binding=request.binding,
        registry=registry,
    )
    diff = OverlayCheckDiff(
        status_changed=False,
        matched_count_delta=0,
        bindings_added=(),
        bindings_removed=(),
    )
    return FactOverlayCheckResult(
        status=phase.status,
        requested_binding=request.binding,
        before=phase,
        after=phase,
        diff=diff,
        errors=(),
        warnings=(),
    )


def _overlay_engine_support_preflight(
    request: FactOverlayCheckRequest,
) -> FactOverlayCheckResult | None:
    if request.engine == "native":
        return None
    return FactOverlayCheckResult(
        status="unsupported",
        requested_binding=request.binding,
        before=None,
        after=None,
        diff=None,
        errors=(
            ErrorDTO(
                code="ENGINE_OVERLAY_NOT_SUPPORTED",
                message=f"engine={request.engine!r} does not support Fact Overlay Check in MVP",
                path=("engine",),
                details={"engine": request.engine},
            ),
        ),
        warnings=(),
    )


def _overlay_ruleref_preflight(
    body: list[Any], registry: RuleRegistry | None
) -> tuple[ErrorDTO, ...]:
    ruleref_atoms = _find_ruleref_atoms(body)
    if not ruleref_atoms:
        return ()

    if registry is None:
        return (
            ErrorDTO(
                code="REGISTRY_REQUIRED",
                message="rule body contains ruleref atoms but no registry was provided",
                path=("registry",),
                details={"ruleref_count": len(ruleref_atoms)},
            ),
        )

    errors: list[ErrorDTO] = []
    seen: set[tuple[str, str]] = set()
    for atom in ruleref_atoms:
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


def _run_native_overlay_phase(
    projected_witness: dict[str, list[ProjectedFact]],
    *,
    plan_body: list[Any],
    binding: BindingItems,
    registry: RuleRegistry | None,
) -> OverlayCheckPhase:
    view_facts = _projected_witness_to_view_facts(projected_witness)
    evaluation = evaluate_native_where(
        view_facts,
        plan_body,
        registry=registry,
        witness_facts=projected_witness,
        remember_support_artifact=None,
    )
    matches = [fb for fb in evaluation.bindings if _binding_matches(fb, binding)]
    if not matches:
        return OverlayCheckPhase(
            status="failed",
            matched_count=0,
            matched_binding=None,
        )

    normalized = sorted(normalize_binding_items(match) for match in matches)
    return OverlayCheckPhase(
        status="passed",
        matched_count=len(matches),
        matched_binding=normalized[0],
    )


def _projected_witness_to_view_facts(
    projected_witness: dict[str, list[ProjectedFact]],
) -> dict[str, list[tuple[Any, ...]]]:
    return {
        pred_id: [row.fact_tuple for row in rows]
        for pred_id, rows in projected_witness.items()
    }


def _find_ruleref_atoms(body: list[Any]) -> list[tuple[Any, ...]]:
    """Return all ``ruleref`` atoms in body (one-level AND or OR-of-AND)."""
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


def _invalid_request(
    request: FactOverlayCheckRequest, *, errors: tuple[ErrorDTO, ...]
) -> FactOverlayCheckResult:
    return FactOverlayCheckResult(
        status="invalid_request",
        requested_binding=request.binding,
        before=None,
        after=None,
        diff=None,
        errors=errors,
        warnings=(),
    )


__all__ = [
    "check_fact_overlay_binding",
]
