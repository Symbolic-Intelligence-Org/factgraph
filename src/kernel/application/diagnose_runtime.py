"""Application-layer Diagnose runtime executor.

Native Diagnose supports pass / fail classification, native atom-localization,
and semantic invalid_request prechecks. Non-native engines are currently
represented through the §8 Step 4 request-level representability gate; actual
souffle / problog / pyreason dispatch lands in §8 Step 5-6.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry
from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.rules.where_eval import (
    _ARITH_KINDS,
    _eval_arith_atom,
    _eval_cmp_atom,
    _eval_eq_atom,
    _eval_in_atom,
    _eval_ne_atom,
    _eval_not_atom,
    _eval_pred_atom,
    _normalize_not_body,
    _normalize_where,
    _vars_in_atoms,
    _vars_in_not_bodies,
    _where_ast_gate_enabled,
)
from kernel.core.store._support import BindingItems, normalize_binding_items
from kernel.core.store._support_capture import find_winning_branch_index
from kernel.core.store.runtime import Store
from kernel.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)

from .protocol import DiagnoseAtomLocator, DiagnoseRequest, DiagnoseResult, ErrorDTO


class DiagnoseRuntimeError(ValueError):
    """Runtime-level Diagnose failure that cannot be expressed as DiagnoseResult."""

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


@dataclass(frozen=True)
class _FailedAtomCandidate:
    branch_index: int
    failed_atom_index: int
    atoms_satisfied: int
    attempted_env: dict[str, Any]


def diagnose_derivation_binding(
    request: DiagnoseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> DiagnoseResult:
    """Diagnose why a requested binding does or does not satisfy a derivation plan."""
    representability_errors = _request_diagnostic_representability_precheck(request)
    if representability_errors:
        return _diagnose_unsupported(request, errors=representability_errors)

    if request.engine != "native":
        raise NotImplementedError(
            "Diagnose non-native dispatch is scoped for §8 Step 4-6"
        )
    return _diagnose_native(request, store=store, registry=registry)


def _diagnose_native(
    request: DiagnoseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> DiagnoseResult:
    body = list(request.plan.body_ir)

    body_vars = _all_body_vars(body)
    requested_vars = {key for key, _ in request.binding}
    unknown = requested_vars - body_vars
    if unknown:
        return _diagnose_invalid_request(
            request,
            errors=(
                ErrorDTO(
                    code="UNKNOWN_VARIABLE_IN_BINDING",
                    message=(
                        "requested binding references variables not in rule body: "
                        f"{sorted(unknown)}"
                    ),
                    path=("binding",),
                    details={"unknown_variables": sorted(unknown)},
                ),
            ),
        )

    ruleref_errors = _diagnose_ruleref_preflight(body, registry)
    if ruleref_errors:
        return _diagnose_invalid_request(request, errors=ruleref_errors)

    view_facts = project_view_facts(store.ledger, store.schema_ir)
    witness_facts = project_view_facts_with_witness(store.ledger, store.schema_ir)
    evaluation = evaluate_native_where(
        view_facts,
        body,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=store._remember_support_artifact,
    )

    matches = [
        final_binding
        for final_binding in evaluation.bindings
        if _diagnose_binding_matches(final_binding, request.binding)
    ]
    if matches:
        matched_with_meta: list[tuple[int, BindingItems]] = []
        for match in matches:
            branch_index = find_winning_branch_index(
                where=body,
                binding=match,
                witness_facts=witness_facts,
                rule_ref_resolutions=evaluation.rule_ref_resolutions,
            )
            matched_with_meta.append((branch_index, normalize_binding_items(match)))
        matched_with_meta.sort(key=lambda row: (row[0], row[1]))
        return DiagnoseResult(
            status="passed",
            requested_binding=request.binding,
            matched_count=len(matches),
            matched_binding=matched_with_meta[0][1],
            failure_kind=None,
            diagnostic_payload=None,
            errors=(),
            warnings=(),
        )

    localized = _localize_failed_atom(
        body,
        requested_binding=request.binding,
        view_facts=view_facts,
    )
    if localized is None:
        return DiagnoseResult(
            status="failed",
            requested_binding=request.binding,
            matched_count=0,
            matched_binding=None,
            failure_kind="no_candidate",
            diagnostic_payload=None,
            errors=(),
            warnings=(),
        )

    return DiagnoseResult(
        status="failed",
        requested_binding=request.binding,
        matched_count=0,
        matched_binding=None,
        failure_kind="atom_localized",
        diagnostic_payload=DiagnoseAtomLocator(
            branch_index=localized.branch_index,
            failed_atom_index=localized.failed_atom_index,
            attempted_binding=normalize_binding_items(localized.attempted_env),
        ),
        errors=(),
        warnings=(),
    )


def _localize_failed_atom(
    body: list[Any],
    *,
    requested_binding: BindingItems,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> _FailedAtomCandidate | None:
    branches = _normalize_where(body)
    requested_env = dict(requested_binding)
    requested_vars = set(requested_env)
    candidates: list[_FailedAtomCandidate] = []

    for branch_index, branch in enumerate(branches):
        branch_vars = set(_vars_in_atoms(branch))
        if requested_vars and branch_vars.isdisjoint(requested_vars):
            continue
        envs = [dict(requested_env)]
        atoms_satisfied = 0
        for atom_index, atom in enumerate(branch):
            next_envs: list[dict[str, Any]] = []
            for env in envs:
                next_envs.extend(_extend_env_with_atom(view_facts, env, atom))
            if not next_envs:
                candidates.append(
                    _FailedAtomCandidate(
                        branch_index=branch_index,
                        failed_atom_index=atom_index,
                        atoms_satisfied=atoms_satisfied,
                        attempted_env=_primary_env(envs),
                    )
                )
                break
            envs = _dedupe_envs(next_envs)
            atoms_satisfied += 1

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item.atoms_satisfied, item.branch_index))
    return candidates[0]


def _extend_env_with_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    env: dict[str, Any],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    """Return deterministic env extensions for one atom.

    This deliberately enumerates possible extensions instead of grounding and
    checking a single atom. Ground-and-check would silently false on unbound vars
    and can corrupt Diagnose's reported failed atom index.
    """
    ast_gate_on = _where_ast_gate_enabled()
    kind = atom[0]
    if kind == "pred":
        return _eval_pred_atom(
            view_facts,
            [dict(env)],
            atom,
            pred_lookup_cache={},
        )
    if kind == "eq":
        return _eval_eq_atom([dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind == "in":
        return _eval_in_atom([dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind == "ne":
        return _eval_ne_atom([dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind in {"gt", "ge", "lt", "le"}:
        return _eval_cmp_atom([dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind in _ARITH_KINDS:
        return _eval_arith_atom([dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind == "not":
        return _eval_not_atom(view_facts, [dict(env)], atom, ast_gate_on=ast_gate_on)
    if kind == "ruleref":
        raise DiagnoseRuntimeError(
            "ruleref atom localization requires Step 3 RuleRef hardening",
            code="DIAGNOSE_RULEREF_LOCALIZATION_NOT_READY",
            details={"atom": repr(atom)},
        )
    raise DiagnoseRuntimeError(
        f"unsupported atom kind for Diagnose localization: {kind}",
        code="DIAGNOSE_UNSUPPORTED_ATOM_KIND",
        details={"atom_kind": kind},
    )


def _primary_env(envs: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(envs, key=_env_sort_key)[0]


def _dedupe_envs(envs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for env in envs:
        deduped.setdefault(_env_sort_key(env), dict(env))
    return [deduped[key] for key in sorted(deduped)]


def _env_sort_key(env: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple((key, repr(value)) for key, value in sorted(env.items()))


def _diagnose_binding_matches(final_binding: dict[str, Any], requested: BindingItems) -> bool:
    """Subset match: every requested binding item must appear in final_binding."""
    return all(final_binding.get(key) == value for key, value in requested)


def _diagnose_invalid_request(
    request: DiagnoseRequest, *, errors: tuple[ErrorDTO, ...]
) -> DiagnoseResult:
    return DiagnoseResult(
        status="invalid_request",
        requested_binding=request.binding,
        matched_count=None,
        matched_binding=None,
        failure_kind=None,
        diagnostic_payload=None,
        errors=errors,
        warnings=(),
    )


def _diagnose_unsupported(
    request: DiagnoseRequest, *, errors: tuple[ErrorDTO, ...]
) -> DiagnoseResult:
    return DiagnoseResult(
        status="unsupported",
        requested_binding=request.binding,
        matched_count=None,
        matched_binding=None,
        failure_kind=None,
        diagnostic_payload=None,
        errors=errors,
        warnings=(),
    )


def _request_diagnostic_representability_precheck(
    request: DiagnoseRequest,
) -> tuple[ErrorDTO, ...]:
    """Return errors when a non-native Diagnose request is not representable.

    This is Diagnose-owned per Q1 Sibling. It intentionally mirrors Check's
    current representability policy without importing Check runtime helpers.
    """
    if request.engine in {"native", "souffle"}:
        return ()

    errors: list[ErrorDTO] = []
    head_spec = request.plan.head_spec
    if isinstance(head_spec, dict) and head_spec.get("callee_kind") == "entity_type":
        errors.append(
            ErrorDTO(
                code="ENTITY_TARGET_NOT_REPRESENTABLE",
                message=(
                    f"engine={request.engine!r} Diagnose does not support "
                    "entity-targeted plans in MVP"
                ),
                path=("plan", "head_spec"),
                details={"engine": request.engine},
            )
        )

    # Per `resolve_head_ref` convention in core/store/_builders.py:
    # head_var_names entries are variable references only when $-prefixed;
    # bare names are literal head args and cannot match a requested binding.
    head_vars = {
        name
        for name in request.plan.heads[0].head_var_names
        if isinstance(name, str) and name.startswith("$") and len(name) > 1
    }
    requested_vars = {key for key, _ in request.binding}
    body_only_vars = sorted(requested_vars - head_vars)
    if body_only_vars:
        errors.append(
            ErrorDTO(
                code="BINDING_NOT_REPRESENTABLE",
                message=(
                    f"engine={request.engine!r} Diagnose can only match requested "
                    "variables carried in the candidate head payload"
                ),
                path=("binding",),
                details={
                    "engine": request.engine,
                    "body_only_variables": body_only_vars,
                },
            )
        )

    return tuple(errors)


def _all_body_vars(body: list[Any]) -> set[str]:
    if not body:
        return set()
    if all(isinstance(item, list) for item in body):
        atoms_flat: list[Any] = [atom for branch in body for atom in branch]
    else:
        atoms_flat = list(body)

    found: set[str] = set(_vars_in_atoms(atoms_flat))
    not_bodies: list[list[tuple[Any, ...]]] = []
    for atom in atoms_flat:
        if isinstance(atom, tuple) and atom and atom[0] == "not" and len(atom) == 2:
            not_bodies.extend(_normalize_not_body(atom[1]))
    if not_bodies:
        found.update(_vars_in_not_bodies(not_bodies))

    for atom in atoms_flat:
        if (
            isinstance(atom, tuple)
            and atom
            and atom[0] == "ruleref"
            and len(atom) == 4
            and isinstance(atom[3], list)
        ):
            for term in atom[3]:
                if isinstance(term, str) and term.startswith("$") and len(term) > 1:
                    found.add(term)
    return found


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


def _diagnose_ruleref_preflight(
    body: list[Any], registry: RuleRegistry | None
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
    "DiagnoseRuntimeError",
    "diagnose_derivation_binding",
]
