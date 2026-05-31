"""Application-layer Diagnose runtime executor.

Native Diagnose supports pass / fail classification, native atom-localization,
and semantic invalid_request prechecks. Souffle dispatch lands in §8 Step 5
(evaluate-then-classify with three-bucket logic + lookup-miss precedence per
audit C4 + §6.3 Decision #5). ProbLog / PyReason dispatch lands in §8 Step 6
with the same C4 bucket precedence over provenance envelopes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.rules.where_eval import (
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
from factgraph.core.store._support import (
    BindingItems,
    ProvenanceEnvelope,
    ProofReceipt,
    normalize_binding_items,
)
from factgraph.core.store._support_capture import find_winning_case_index
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)

from .derivation_runtime import evaluate_derivation_plans
from .protocol import (
    DerivationEvaluateRequest,
    DiagnoseConditionLocator,
    DiagnoseRequest,
    DiagnoseResult,
    ErrorDTO,
)


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
    case_index: int
    failed_atom_index: int
    atoms_satisfied: int
    attempted_env: dict[str, Any]


_UNREPRESENTABLE_TERM = object()


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

    if request.engine == "native":
        return _diagnose_native(request, store=store, registry=registry)
    if request.engine == "souffle":
        return _diagnose_souffle(request, store=store, registry=registry)
    if request.engine in {"problog", "pyreason"}:
        return _diagnose_problog_pyreason(
            request,
            store=store,
            registry=registry,
        )
    raise DiagnoseRuntimeError(
        f"unknown Diagnose engine: {request.engine}",
        code="DIAGNOSE_INTERNAL_UNKNOWN_ENGINE",
        details={"engine": request.engine},
    )


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
            case_index = find_winning_case_index(
                where=body,
                binding=match,
                witness_facts=witness_facts,
                rule_ref_resolutions=evaluation.rule_ref_resolutions,
            )
            matched_with_meta.append((case_index, normalize_binding_items(match)))
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
        diagnostic_payload=DiagnoseConditionLocator(
            case_index=localized.case_index,
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

    for case_index, branch in enumerate(branches):
        branch_vars = set(_vars_in_atoms(branch))
        if requested_vars and branch_vars.isdisjoint(requested_vars):
            continue
        envs = [dict(requested_env)]
        atoms_satisfied = 0
        for condition_index, atom in enumerate(branch):
            next_envs: list[dict[str, Any]] = []
            for env in envs:
                next_envs.extend(_extend_env_with_atom(view_facts, env, atom))
            if not next_envs:
                candidates.append(
                    _FailedAtomCandidate(
                        case_index=case_index,
                        failed_atom_index=condition_index,
                        atoms_satisfied=atoms_satisfied,
                        attempted_env=_primary_env(envs),
                    )
                )
                break
            envs = _dedupe_envs(next_envs)
            atoms_satisfied += 1

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item.atoms_satisfied, item.case_index))
    return candidates[0]


def _extend_env_with_atom(
    view_facts: dict[str, list[tuple[Any, ...]]],
    env: dict[str, Any],
    atom: tuple[Any, ...],
) -> list[dict[str, Any]]:
    """Return deterministic env extensions for one atom.

    This deliberately enumerates possible extensions instead of grounding and
    checking a single atom. Ground-and-check would silently false on unbound vars
    and can corrupt Diagnose's reported failed condition index.
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


def _diagnose_souffle(
    request: DiagnoseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> DiagnoseResult:
    """Souffle Diagnose dispatch via three-bucket classification (audit C4).

    Algorithm:

    - Delegate evaluate to ``evaluate_derivation_plans`` in souffle mode.
    - For each candidate, look up its ``ProofReceipt`` from the store via
      the typed internal API. Three buckets per candidate:
      - **lookup-miss**: artifact lookup returned ``None`` (engine advertised
        ``souffle_witness_v1`` support but no payload was retrievable).
      - **match**: artifact present and ``binding_items`` subset-matches
        ``request.binding``.
      - **no-match**: artifact present but binding does not subset-match.
    - Result classification (precedence-ordered):
      - match bucket non-empty → ``status="passed"`` (primary by Check 0.C C4
        sort: ``(case_index, binding_items, candidate_key)``)
      - match empty AND lookup-miss bucket non-empty → ``status="unsupported"``
        with ``EVIDENCE_LOOKUP_MISS`` errors (one per missing candidate)
      - all buckets accounted, no match, no lookup-miss → ``status="failed"``
        with ``failure_kind="no_candidate"``

    **Lookup-miss outranks no_candidate** per §6.3 Decision #5: evidence-miss
    is an observable contract problem, never silent-skipped (Diagnose's
    independent §6.3 binding is what motivates Q1 Sibling — see audit Q1
    supersede note).

    Diagnose-side helpers (``_lookup_support_artifact``,
    ``_derive_case_index_from_artifact``, ``_parse_case_index``) are local
    copies of Check's per Q1 Sibling D11 invariant; deferred refactor per
    topic §1.3 + §6.2 wave-ordering second-consumer rule.
    """
    eval_request = DerivationEvaluateRequest(
        plans=(request.plan,),
        engine="souffle",
    )
    candidates = evaluate_derivation_plans(
        eval_request, store=store, registry=registry
    )

    matches: list[tuple[CandidateSet, ProofReceipt, dict[str, Any]]] = []
    lookup_miss: list[CandidateSet] = []
    for candidate in candidates:
        artifact = _lookup_support_artifact(store, candidate.support_digest)
        if artifact is None:
            lookup_miss.append(candidate)
            continue
        binding_dict = dict(artifact.binding_items)
        if _diagnose_binding_matches(binding_dict, request.binding):
            matches.append((candidate, artifact, binding_dict))

    if matches:
        def _sort_key(
            item: tuple[CandidateSet, ProofReceipt, dict[str, Any]],
        ) -> tuple[Any, ...]:
            candidate, artifact, binding = item
            case_index = _derive_case_index_from_artifact(artifact)
            case_key = (
                (0, case_index) if case_index is not None else (1, 0)
            )
            return (
                case_key,
                normalize_binding_items(binding),
                candidate.candidate_key,
            )

        matches.sort(key=_sort_key)
        _primary_candidate, _primary_artifact, primary_binding = matches[0]
        return DiagnoseResult(
            status="passed",
            requested_binding=request.binding,
            matched_count=len(matches),
            matched_binding=normalize_binding_items(primary_binding),
            failure_kind=None,
            diagnostic_payload=None,
            errors=(),
            warnings=(),
        )

    if lookup_miss:
        errors = tuple(
            ErrorDTO(
                code="EVIDENCE_LOOKUP_MISS",
                message=(
                    f"souffle candidate advertised support_kind="
                    f"{candidate.support_kind!r} but lookup returned None"
                ),
                path=("candidates",),
                details={
                    "engine": "souffle",
                    "support_kind": candidate.support_kind,
                    "support_digest": candidate.support_digest,
                    "candidate_key": candidate.candidate_key,
                },
            )
            for candidate in lookup_miss
        )
        return _diagnose_unsupported(request, errors=errors)

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


def _lookup_support_artifact(store: Store, digest: str) -> ProofReceipt | None:
    """Diagnose's own typed support-artifact lookup (Q1 Sibling D11 invariant).

    Mirrors Check's ``_lookup_support_artifact`` without importing Check
    runtime helpers; uses ``Store._lookup_support_artifact`` typed internal API
    per audit §6.3 ownership boundary.
    """
    return store._lookup_support_artifact(digest)


def _diagnose_problog_pyreason(
    request: DiagnoseRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> DiagnoseResult:
    """ProbLog / PyReason Diagnose via C4 three-bucket provenance classification.

    Representability has already been gated at the request level: only
    head-carried variables reach this path. Diagnose extracts match bindings by
    positional alignment between ``plan.heads[0].head_var_names`` and
    ``candidate.payload["terms"]``. Missing provenance envelopes are observable
    ``unsupported`` results with ``EVIDENCE_LOOKUP_MISS``; this is the deliberate
    Diagnose divergence from Check's grandfathered silent-skip path.
    """
    eval_request = DerivationEvaluateRequest(
        plans=(request.plan,),
        engine=request.engine,
    )
    candidates = evaluate_derivation_plans(
        eval_request, store=store, registry=registry
    )

    matches: list[tuple[CandidateSet, ProvenanceEnvelope, dict[str, Any]]] = []
    lookup_miss: list[CandidateSet] = []
    for candidate in candidates:
        envelope = _lookup_provenance_envelope(store, candidate.support_digest)
        if envelope is None:
            lookup_miss.append(candidate)
            continue
        binding_dict = _extract_head_var_binding(
            candidate=candidate,
            plan=request.plan,
        )
        if _diagnose_binding_matches(binding_dict, request.binding):
            matches.append((candidate, envelope, binding_dict))

    if matches:
        def _sort_key(
            item: tuple[CandidateSet, ProvenanceEnvelope, dict[str, Any]],
        ) -> tuple[Any, ...]:
            candidate, _envelope, binding = item
            return (candidate.candidate_key, normalize_binding_items(binding))

        matches.sort(key=_sort_key)
        _primary_candidate, _primary_envelope, primary_binding = matches[0]
        return DiagnoseResult(
            status="passed",
            requested_binding=request.binding,
            matched_count=len(matches),
            matched_binding=normalize_binding_items(primary_binding),
            failure_kind=None,
            diagnostic_payload=None,
            errors=(),
            warnings=(),
        )

    if lookup_miss:
        errors = tuple(
            ErrorDTO(
                code="EVIDENCE_LOOKUP_MISS",
                message=(
                    f"{request.engine} candidate advertised support_kind="
                    f"{candidate.support_kind!r} but lookup returned None"
                ),
                path=("candidates",),
                details={
                    "engine": request.engine,
                    "support_kind": candidate.support_kind,
                    "support_digest": candidate.support_digest,
                    "candidate_key": candidate.candidate_key,
                },
            )
            for candidate in lookup_miss
        )
        return _diagnose_unsupported(request, errors=errors)

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


def _lookup_provenance_envelope(
    store: Store,
    digest: str,
) -> ProvenanceEnvelope | None:
    """Diagnose's own typed provenance lookup (Q1 Sibling D11 invariant)."""
    return store._lookup_provenance_envelope(digest)


def _extract_head_var_binding(
    *,
    candidate: CandidateSet,
    plan: Any,
) -> dict[str, Any]:
    """Extract var → value mapping from a candidate via head-var alignment."""
    head_vars = plan.heads[0].head_var_names
    payload = candidate.payload
    if not isinstance(payload, dict):
        return {}
    terms = payload.get("terms")
    if not isinstance(terms, list) or len(terms) != len(head_vars):
        return {}

    binding: dict[str, Any] = {}
    for var_name, term in zip(head_vars, terms):
        if not (
            isinstance(var_name, str)
            and var_name.startswith("$")
            and len(var_name) > 1
        ):
            continue
        value = _extract_term_value(term)
        if value is _UNREPRESENTABLE_TERM:
            continue
        binding[var_name] = value
    return binding


def _extract_term_value(term: Any) -> Any:
    if isinstance(term, dict):
        kind = term.get("kind")
        if kind == "candidate_ref":
            return _UNREPRESENTABLE_TERM
        return term.get("value")
    if isinstance(term, tuple) and len(term) == 2:
        return term[1]
    return None


def _derive_case_index_from_artifact(artifact: ProofReceipt) -> int | None:
    """Extract case_index from a ProofReceipt's condition-key prefixes.

    Mirror of Check's helper per Q1 Sibling. Souffle artifacts encode branch
    indices via ``c{n}.c{m}:...`` on ``pred_witnesses`` and ``non_fact_steps``;
    return the integer if all keys agree, ``None`` otherwise.
    """
    case_indices: set[int] = set()
    for witness in artifact.pred_witnesses:
        parsed = _parse_case_index(witness.pred_condition_key)
        if parsed is not None:
            case_indices.add(parsed)
    for step in artifact.non_fact_steps:
        parsed = _parse_case_index(step.step_key)
        if parsed is not None:
            case_indices.add(parsed)
    if len(case_indices) == 1:
        return next(iter(case_indices))
    return None


def _parse_case_index(key: str) -> int | None:
    """Parse ``c{n}.c{m}:...`` into the ``{n}`` integer (Diagnose's local copy)."""
    if not isinstance(key, str) or not key.startswith("c"):
        return None
    try:
        dot_pos = key.index(".")
    except ValueError:
        return None
    if dot_pos <= 1:
        return None
    if dot_pos + 1 >= len(key) or key[dot_pos + 1] != "c":
        return None
    colon_pos = key.find(":", dot_pos + 2)
    if colon_pos == -1:
        return None
    condition_index_text = key[dot_pos + 2 : colon_pos]
    if not condition_index_text.isdigit():
        return None
    try:
        return int(key[1:dot_pos])
    except ValueError:
        return None


__all__ = [
    "DiagnoseRuntimeError",
    "diagnose_derivation_binding",
]
