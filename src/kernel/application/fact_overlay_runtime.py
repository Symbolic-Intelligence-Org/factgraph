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
    FactValueOverride,
    OverlayCheckDiff,
    OverlayCheckPhase,
)


def check_fact_overlay_binding(
    request: FactOverlayCheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> FactOverlayCheckResult:
    """Evaluate Overlay Check."""

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
    override_errors = _validate_fact_value_overrides(
        request.overlay,
        projected_witness,
        store.schema_ir,
    )
    if override_errors:
        return _invalid_request(request, errors=tuple(override_errors))

    try:
        before = _run_native_overlay_phase(
            projected_witness,
            plan_body=body,
            binding=request.binding,
            registry=registry,
        )
        overlay_witness = _apply_fact_overlay_projection(
            request.overlay,
            projected_witness,
        )
        after = _run_native_overlay_phase(
            overlay_witness,
            plan_body=body,
            binding=request.binding,
            registry=registry,
        )
        diff = _build_overlay_diff(before, after)
    except Exception as exc:  # pragma: no cover - exercised through patched runtime tests
        return _invalid_request(
            request,
            errors=(
                ErrorDTO(
                    code="OVERLAY_PHASE_RUNTIME_ERROR",
                    message="Fact Overlay Check native phase execution failed",
                    path=("runtime",),
                    details={"exception": type(exc).__name__},
                ),
            ),
        )
    return FactOverlayCheckResult(
        status=after.status,
        requested_binding=request.binding,
        before=before,
        after=after,
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


def _validate_fact_value_overrides(
    overrides: tuple[FactValueOverride, ...],
    projected_witness: dict[str, list[ProjectedFact]],
    schema_ir: dict[str, Any],
) -> list[ErrorDTO]:
    errors: list[ErrorDTO] = []
    visible_rows = _visible_projected_rows(projected_witness)
    schema_predicates = _schema_predicates_by_id(schema_ir)
    seen_asrt_ids: set[str] = set()

    for index, override in enumerate(overrides):
        path = ("overlay", str(index))
        if override.asrt_id in seen_asrt_ids:
            errors.append(
                ErrorDTO(
                    code="OVERLAY_DUPLICATE_ASRT_ID",
                    message=f"duplicate overlay assertion id: {override.asrt_id}",
                    path=path + ("asrt_id",),
                    details={"asrt_id": override.asrt_id},
                )
            )
        seen_asrt_ids.add(override.asrt_id)

        row = visible_rows.get((override.pred_id, override.asrt_id))
        if row is None:
            errors.append(
                ErrorDTO(
                    code="OVERLAY_ASRT_ID_NOT_VISIBLE",
                    message=(
                        "overlay assertion id is not active and visible for the "
                        f"requested predicate: {override.asrt_id}"
                    ),
                    path=path + ("asrt_id",),
                    details={"asrt_id": override.asrt_id, "pred_id": override.pred_id},
                )
            )
            continue

        current_tuple = row.fact_tuple
        if override.old_fact_tuple != current_tuple:
            errors.append(
                ErrorDTO(
                    code="OVERLAY_STALE_OLD_FACT_TUPLE",
                    message="overlay old_fact_tuple does not match the visible projected fact",
                    path=path + ("old_fact_tuple",),
                    details={"asrt_id": override.asrt_id, "pred_id": override.pred_id},
                )
            )

        expected_arity = len(current_tuple)
        if (
            len(override.old_fact_tuple) != expected_arity
            or len(override.new_fact_tuple) != expected_arity
        ):
            errors.append(
                ErrorDTO(
                    code="OVERLAY_TUPLE_ARITY_MISMATCH",
                    message="overlay fact tuples must preserve projected fact arity",
                    path=path,
                    details={
                        "asrt_id": override.asrt_id,
                        "expected_arity": expected_arity,
                        "old_arity": len(override.old_fact_tuple),
                        "new_arity": len(override.new_fact_tuple),
                    },
                )
            )

        if not _e_ref_position_matches(override, current_tuple):
            errors.append(
                ErrorDTO(
                    code="OVERLAY_E_REF_POSITION_MISMATCH",
                    message="overlay e_ref must match fact_tuple[0] and the visible fact entity",
                    path=path + ("e_ref",),
                    details={"asrt_id": override.asrt_id, "e_ref": override.e_ref},
                )
            )

        schema_pred = schema_predicates.get(override.pred_id)
        if schema_pred is not None and _group_key_changed(
            schema_pred,
            current_tuple,
            override.new_fact_tuple,
        ):
            errors.append(
                ErrorDTO(
                    code="OVERLAY_GROUP_KEY_CHANGED",
                    message="overlay must not change group_key_indexes positions",
                    path=path + ("new_fact_tuple",),
                    details={"asrt_id": override.asrt_id, "pred_id": override.pred_id},
                )
            )

    return errors


def _apply_fact_overlay_projection(
    overrides: tuple[FactValueOverride, ...],
    projected_witness: dict[str, list[ProjectedFact]],
) -> dict[str, list[ProjectedFact]]:
    override_by_key = {
        (override.pred_id, override.asrt_id): override for override in overrides
    }
    output: dict[str, list[ProjectedFact]] = {}
    for pred_id, rows in projected_witness.items():
        copied_rows: list[ProjectedFact] = []
        for row in rows:
            override = override_by_key.get((pred_id, row.asrt_id))
            if override is None:
                copied_rows.append(row)
                continue
            copied_rows.append(
                ProjectedFact(
                    asrt_id=row.asrt_id,
                    fact_tuple=override.new_fact_tuple,
                )
            )
        output[pred_id] = copied_rows
    return output


def _build_overlay_diff(
    before: OverlayCheckPhase,
    after: OverlayCheckPhase,
) -> OverlayCheckDiff:
    before_bindings = _phase_bindings(before)
    after_bindings = _phase_bindings(after)
    return OverlayCheckDiff(
        status_changed=before.status != after.status,
        matched_count_delta=after.matched_count - before.matched_count,
        bindings_added=_binding_difference(after_bindings, before_bindings),
        bindings_removed=_binding_difference(before_bindings, after_bindings),
    )


def _projected_witness_to_view_facts(
    projected_witness: dict[str, list[ProjectedFact]],
) -> dict[str, list[tuple[Any, ...]]]:
    return {
        pred_id: [row.fact_tuple for row in rows]
        for pred_id, rows in projected_witness.items()
    }


def _visible_projected_rows(
    projected_witness: dict[str, list[ProjectedFact]],
) -> dict[tuple[str, str], ProjectedFact]:
    return {
        (pred_id, row.asrt_id): row
        for pred_id, rows in projected_witness.items()
        for row in rows
    }


def _schema_predicates_by_id(schema_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    predicates = schema_ir.get("predicates")
    if not isinstance(predicates, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        pred_id = predicate.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            output[pred_id] = predicate
    return output


def _e_ref_position_matches(
    override: FactValueOverride,
    current_tuple: tuple[Any, ...],
) -> bool:
    if not current_tuple:
        return False
    if current_tuple[0] != override.e_ref:
        return False
    if not override.old_fact_tuple or override.old_fact_tuple[0] != override.e_ref:
        return False
    return bool(override.new_fact_tuple and override.new_fact_tuple[0] == override.e_ref)


def _group_key_changed(
    schema_pred: dict[str, Any],
    current_tuple: tuple[Any, ...],
    new_tuple: tuple[Any, ...],
) -> bool:
    group_key_indexes = schema_pred.get("group_key_indexes")
    if not isinstance(group_key_indexes, list):
        return False
    for raw_index in group_key_indexes:
        if not isinstance(raw_index, int):
            continue
        if raw_index < 0 or raw_index >= len(current_tuple) or raw_index >= len(new_tuple):
            continue
        if current_tuple[raw_index] != new_tuple[raw_index]:
            return True
    return False


def _phase_bindings(phase: OverlayCheckPhase) -> tuple[BindingItems, ...]:
    if phase.matched_binding is None:
        return ()
    return (phase.matched_binding,)


def _binding_difference(
    left: tuple[BindingItems, ...],
    right: tuple[BindingItems, ...],
) -> tuple[BindingItems, ...]:
    diff = tuple(binding for binding in left if binding not in right)
    return tuple(sorted(diff, key=repr))


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
