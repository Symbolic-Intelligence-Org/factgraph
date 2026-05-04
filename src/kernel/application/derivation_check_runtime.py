"""Application-layer Check runtime executor.

Step 4.1 scope: native engine plus non-native request-level representability
precheck. Non-native requests that are not askable return ``unsupported``;
representable non-native requests still raise ``NotImplementedError`` until
Step 4.2 / Step 4.3 land evaluate-then-match.

Algorithm (per audit log Step 0.C C1+C2 unified):

- Always go through ``evaluate_native_where(...)`` for final bindings plus
  RuleRef resolutions. Complete binding is the special case where subset-match
  equals exact match.
- Subset-match each final binding against the requested binding.
- Deterministic primary by ``(branch_index, binding_items)`` sort.
- Build ``EvidenceEnvelope`` from primary FULL binding (never user partial,
  per topic doc §7.1 trap).

RuleRef preflight (per audit log Step 0.C C5):

- Scan the body for ``ruleref`` atoms before evaluation.
- If no registry but ruleref present -> ``REGISTRY_REQUIRED``.
- For each ruleref: ``registry.resolve(rule_id, version)``; on
  ``RuleCompileError`` -> ``RULE_REF_UNRESOLVABLE`` with reason in details.
- Cycle / version mismatch are not classified here; native eval may raise.

Errors / status mapping:

- DTO shape errors raised at DTO construction (``ProtocolShapeError``,
  per Step 0.B B2) -- runtime never converts shape errors to status.
- Semantic invalid (unknown variable, missing/unresolvable registry)
  -> ``CheckResult(status="invalid_request")`` with errors populated.
- Non-native engine representability failure -> ``status="unsupported"``;
  representable-but-not-yet-implemented -> ``NotImplementedError`` (loud
  staging, per topic doc §7 outcome purity).
- Runtime / engine / internal failures propagate as-is (engine adapter
  errors, projection failures). Narrow ``CheckRuntimeError`` is provided
  for cases the runtime cannot meaningfully convert into a CheckResult.
"""
from __future__ import annotations

from typing import Any

from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry
from kernel.core.rules.ruleref_substrate import evaluate_native_where
from kernel.core.rules.where_eval import (
    _normalize_not_body,
    _vars_in_atoms,
    _vars_in_not_bodies,
)
from kernel.core.store._support import (
    BindingItems,
    compute_support_digest,
    normalize_binding_items,
)
from kernel.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_branch_index,
)
from kernel.core.store.runtime import Store
from kernel.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)

from .protocol import (
    CheckRequest,
    CheckResult,
    ErrorDTO,
    EvidenceEnvelope,
)


class CheckRuntimeError(ValueError):
    """Runtime-level Check failure that cannot be expressed as ``CheckResult``.

    Narrow use: only for internal failures the runtime cannot meaningfully
    convert to a ``CheckResult`` (e.g., invariant violations from primitives
    that should never happen on a final binding). Most expected errors are
    either raised as ``ProtocolShapeError`` at DTO construction or returned
    as ``CheckResult(status="invalid_request")``.
    """

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


def check_derivation_binding(
    request: CheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None = None,
) -> CheckResult:
    """Verify whether the requested binding satisfies the rule.

    Native runs fully. Non-native engines run request-level representability
    precheck; representable requests raise ``NotImplementedError`` until
    Step 4.2 / Step 4.3 land evaluate-then-match.

    See blueprint ``2026-05-03_check-operation.md`` and audit log
    Step 0.B / Step 0.C for the full contract.
    """
    if request.engine != "native":
        return _non_native_check(request, store=store, registry=registry)

    return _native_check(request, store=store, registry=registry)


def _native_check(
    request: CheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> CheckResult:
    """Native Check implementation via final-result matching."""

    body = list(request.plan.body_ir)

    # Semantic precheck 1: unknown variable in requested binding.
    body_vars = _all_body_vars(body)
    requested_vars = {key for key, _ in request.binding}
    unknown = requested_vars - body_vars
    if unknown:
        return _invalid_request(
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

    # Semantic precheck 2: RuleRef preflight (per Step 0.C C5).
    ruleref_errors = _ruleref_preflight(body, registry)
    if ruleref_errors:
        return _invalid_request(request, errors=ruleref_errors)

    # Project facts at read time (per Step 0.C input boundary §3.1).
    view_facts = project_view_facts(store.ledger, store.schema_ir)
    witness_facts = project_view_facts_with_witness(store.ledger, store.schema_ir)

    # Unified native evaluation (per Step 0.C C1+C2 -- complete binding is the
    # special case where subset-match equals exact match).
    evaluation = evaluate_native_where(
        view_facts,
        body,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=store._remember_support_artifact,
    )

    # Subset-match each final binding (handles complete + partial uniformly).
    matches: list[dict[str, Any]] = [
        fb for fb in evaluation.bindings if _binding_matches(fb, request.binding)
    ]

    if not matches:
        return CheckResult(
            status="failed",
            requested_binding=request.binding,
            matched_count=0,
            matched_binding=None,
            evidence_envelope=None,
            errors=(),
            warnings=(),
        )

    # Deterministic primary selection (per Step 0.C C4):
    # native sort key = (branch_index, binding_items).
    matched_with_meta: list[tuple[int, BindingItems, dict[str, Any]]] = []
    for fb in matches:
        branch_index = find_winning_branch_index(
            where=body,
            binding=fb,
            witness_facts=witness_facts,
            rule_ref_resolutions=evaluation.rule_ref_resolutions,
        )
        binding_items = normalize_binding_items(fb)
        matched_with_meta.append((branch_index, binding_items, fb))
    matched_with_meta.sort(key=lambda row: (row[0], row[1]))
    primary_branch_index, primary_binding_items, primary_fb = matched_with_meta[0]

    # Build EvidenceEnvelope from primary FULL binding.
    # NEVER pass user partial here -- see topic doc §7.1 trap.
    rule_ref_edges = derive_rule_ref_edges_for_binding(
        where=body,
        binding=primary_fb,
        rule_ref_resolutions=evaluation.rule_ref_resolutions,
        selected_branch_index=primary_branch_index,
    )
    root_result_kind = _determine_root_result_kind(request.plan)
    artifact = build_support_artifact_for_binding(
        where=body,
        binding=primary_fb,
        witness_facts=witness_facts,
        root_result_kind=root_result_kind,
        selected_branch_index=primary_branch_index,
        rule_ref_edges=rule_ref_edges,
    )
    support_digest = compute_support_digest(artifact)
    store._remember_support_artifact(support_digest, artifact)
    envelope = EvidenceEnvelope(
        engine="native",
        support_kind=artifact.kind,
        support_digest=support_digest,
        branch_index=primary_branch_index,
        engine_payload=artifact,
        branch_atom_projection=None,
    )

    return CheckResult(
        status="passed",
        requested_binding=request.binding,
        matched_count=len(matches),
        matched_binding=primary_binding_items,
        evidence_envelope=envelope,
        errors=(),
        warnings=(),
    )


def _non_native_check(
    request: CheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> CheckResult:
    """Representability-gated non-native staging.

    Step 4.1 lands request-level representability precheck only. If the
    question is representable for the requested engine/output shape, the
    evaluate-then-match implementation comes in Step 4.2 / Step 4.3.
    """
    del store, registry  # Step 4.1 only decides whether the question is askable.
    errors = _request_representability_precheck(request)
    if errors:
        return CheckResult(
            status="unsupported",
            requested_binding=request.binding,
            matched_count=None,
            matched_binding=None,
            evidence_envelope=None,
            errors=errors,
            warnings=(),
        )
    raise NotImplementedError(
        f"Evaluate-then-match for engine={request.engine!r} comes in Step 4.2/4.3"
    )


def _request_representability_precheck(request: CheckRequest) -> tuple[ErrorDTO, ...]:
    """Return errors when a non-native Check request cannot be represented.

    Per Step 0.C C6 this is a request-level check, not a result-level check.
    Unsupported means "cannot ask this question", before any adapter evaluate
    call is made.
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
                    f"engine={request.engine!r} Check does not support "
                    "entity-targeted plans in MVP"
                ),
                path=("plan", "head_spec"),
                details={"engine": request.engine},
            )
        )

    head_vars = set(request.plan.heads[0].head_var_names)
    requested_vars = {key for key, _ in request.binding}
    body_only_vars = sorted(requested_vars - head_vars)
    if body_only_vars:
        errors.append(
            ErrorDTO(
                code="BINDING_NOT_REPRESENTABLE",
                message=(
                    f"engine={request.engine!r} Check can only match requested "
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


def _binding_matches(final_binding: dict[str, Any], requested: BindingItems) -> bool:
    """Subset match: every (var, value) in requested must appear in final_binding.

    Empty requested binding matches any final binding (any-result-exists semantics
    per audit log Step 0.C). Complete binding is the special case where the
    subset equals the full set.
    """
    return all(final_binding.get(key) == value for key, value in requested)


def _invalid_request(
    request: CheckRequest, *, errors: tuple[ErrorDTO, ...]
) -> CheckResult:
    return CheckResult(
        status="invalid_request",
        requested_binding=request.binding,
        matched_count=None,
        matched_binding=None,
        evidence_envelope=None,
        errors=errors,
        warnings=(),
    )


def _all_body_vars(body: list[Any]) -> set[str]:
    """Extract every $-variable referenced in the where body.

    Walks one-level AND or two-level OR-of-AND, plus into ``not`` subexpressions
    and ``ruleref`` term lists.
    """
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


def _ruleref_preflight(
    body: list[Any], registry: RuleRegistry | None
) -> tuple[ErrorDTO, ...]:
    """Preflight RuleRef resolution before native evaluation.

    Returns an ``ErrorDTO`` tuple if preflight fails, empty tuple otherwise.

    Detects:

    - ``REGISTRY_REQUIRED``: ruleref atoms present but no registry provided.
    - ``RULE_REF_UNRESOLVABLE``: ``registry.resolve`` raises ``RuleCompileError``;
      the original reason is preserved in ``details.reason`` to avoid brittle
      adapter-text parsing later.

    Cycles / version mismatches are NOT classified here (per audit log
    Step 0.C C5 softening); native eval may surface those as runtime errors.
    """
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


def _determine_root_result_kind(plan: Any) -> str:
    """Per audit log Step 0.B / baseline §P0-2: head_spec.callee_kind == 'entity_type'
    -> 'entity'; else 'fact'.
    """
    head_spec = plan.head_spec
    if isinstance(head_spec, dict) and head_spec.get("callee_kind") == "entity_type":
        return "entity"
    return "fact"


__all__ = [
    "CheckRuntimeError",
    "check_derivation_binding",
]
