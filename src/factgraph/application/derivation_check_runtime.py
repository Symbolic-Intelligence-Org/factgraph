"""Application-layer Check runtime executor.

All scoped engines are implemented through representability-gated final-result
matching:

- native enumerates final bindings via ``evaluate_native_where(...)``;
- souffle delegates through ``evaluate_derivation_plans(...)`` and matches
  witness-bearing ``ProofReceipt.binding_items``;
- problog / pyreason delegate through ``evaluate_derivation_plans(...)`` and
  match only payload-representable head-variable bindings carried by
  ``CandidateSet.payload["terms"]``.

Algorithm (per audit log Step 0.C C1+C2 unified):

- Always go through ``evaluate_native_where(...)`` for final bindings plus
  RuleRef resolutions. Complete binding is the special case where subset-match
  equals exact match.
- Subset-match each final binding against the requested binding.
- Deterministic primary by ``(case_index, binding_items)`` sort.
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
  representable requests use evaluate-then-match.
- Runtime / engine / internal failures propagate as-is (engine adapter
  errors, projection failures). Narrow ``CheckRuntimeError`` is provided
  for cases the runtime cannot meaningfully convert into a CheckResult.
"""
from __future__ import annotations

from typing import Any

from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.store._support import (
    BindingItems,
    ProvenanceEnvelope,
    ProofReceipt,
    compute_support_digest,
    normalize_binding_items,
)
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_case_index,
)
from factgraph.core.store.premise_filter import premise_scoped_ledger
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)

from ._derivation_match_helpers import _all_body_vars, _binding_matches
from .derivation_runtime import evaluate_derivation_plans
from .protocol import (
    CheckRequest,
    CheckResult,
    DerivationEvaluateRequest,
    ErrorDTO,
    EvidenceEnvelope,
)

_UNREPRESENTABLE_TERM = object()


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

    Native, souffle, problog, and pyreason all run through final-result
    matching. Non-native engines first apply a request-level representability
    precheck; non-representable questions return ``unsupported`` before
    evaluation, while representable questions delegate to the existing
    derivation evaluation runtime and match the engine output.

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
    # Premise admissibility: the check premise set matches evaluation —
    # assertions excluded via store.premise_exclusions are invisible here.
    # The non-native legs inherit the same filter through
    # evaluate_derivation_plans -> Store.evaluate_engine.
    ledger = premise_scoped_ledger(
        store.ledger, store.premise_exclusions, store.premise_allowances,
        getattr(store, "premise_blocks", ()),
    )
    view_facts = project_view_facts(ledger, store.schema_ir)
    witness_facts = project_view_facts_with_witness(ledger, store.schema_ir)

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
    # native sort key = (case_index, binding_items).
    matched_with_meta: list[tuple[int, BindingItems, dict[str, Any]]] = []
    for fb in matches:
        case_index = find_winning_case_index(
            where=body,
            binding=fb,
            witness_facts=witness_facts,
            rule_ref_resolutions=evaluation.rule_ref_resolutions,
        )
        binding_items = normalize_binding_items(fb)
        matched_with_meta.append((case_index, binding_items, fb))
    matched_with_meta.sort(key=lambda row: (row[0], row[1]))
    primary_branch_index, primary_binding_items, primary_fb = matched_with_meta[0]

    # Build EvidenceEnvelope from primary FULL binding.
    # NEVER pass user partial here -- see topic doc §7.1 trap.
    rule_ref_edges = derive_rule_ref_edges_for_binding(
        where=body,
        binding=primary_fb,
        rule_ref_resolutions=evaluation.rule_ref_resolutions,
        selected_case_index=primary_branch_index,
    )
    root_result_kind = _determine_root_result_kind(request.plan)
    artifact = build_support_artifact_for_binding(
        where=body,
        binding=primary_fb,
        witness_facts=witness_facts,
        root_result_kind=root_result_kind,
        selected_case_index=primary_branch_index,
        rule_ref_edges=rule_ref_edges,
    )
    support_digest = compute_support_digest(artifact)
    store._remember_support_artifact(support_digest, artifact)
    envelope = EvidenceEnvelope(
        engine="native",
        support_kind=artifact.kind,
        support_digest=support_digest,
        case_index=primary_branch_index,
        proof=artifact,
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
    """Representability-gated non-native evaluate-then-match dispatch."""
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

    if request.engine == "souffle":
        return _souffle_check(request, store=store, registry=registry)

    if request.engine in {"problog", "pyreason"}:
        return _problog_pyreason_check(request, store=store, registry=registry)

    raise CheckRuntimeError(
        f"unrecognized engine {request.engine!r}",
        code="CHECK_INTERNAL_UNKNOWN_ENGINE",
        details={"engine": request.engine},
    )


def _souffle_check(
    request: CheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> CheckResult:
    """Souffle Check via evaluate-then-match against witness-bearing ProofReceipt.

    Algorithm (per audit log Step 0.C C3 / C4 / C6):

    - Delegate evaluate to ``evaluate_derivation_plans`` in souffle mode.
    - For each candidate, look up its ``ProofReceipt`` from store; the artifact's
      ``binding_items`` carries the full query binding.
    - Subset-match each candidate's full binding against the requested binding.
    - Primary key = ``(case_index, binding_items, candidate_key)`` (per C4).
    - EvidenceEnvelope reuses the candidate's ``support_kind`` + ``support_digest``
      and embeds the typed ``ProofReceipt`` as ``proof`` (per
      Step 0.B B9 + B10; ``branch_atom_projection`` stays None).

    Candidates without a retrievable artifact are skipped silently in MVP — they
    cannot be matched representably without binding data, so they neither pass
    nor fail the user's request.
    """
    eval_request = DerivationEvaluateRequest(
        plans=(request.plan,),
        engine="souffle",
    )
    candidates = evaluate_derivation_plans(
        eval_request, store=store, registry=registry
    )

    matches: list[tuple[CandidateSet, ProofReceipt, dict[str, Any]]] = []
    for candidate in candidates:
        artifact = _lookup_support_artifact(store, candidate.support_digest)
        if artifact is None:
            continue
        binding_dict = dict(artifact.binding_items)
        if _binding_matches(binding_dict, request.binding):
            matches.append((candidate, artifact, binding_dict))

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

    def _sort_key(item: tuple[CandidateSet, ProofReceipt, dict[str, Any]]) -> tuple[Any, ...]:
        candidate, artifact, binding = item
        case_index = _derive_case_index_from_artifact(artifact)
        # Known case_index participates in source-order sorting. If the artifact
        # does not expose a parseable case index, fall back to binding/candidate
        # ordering behind known-branch candidates.
        case_key = (0, case_index) if case_index is not None else (1, 0)
        return (case_key, normalize_binding_items(binding), candidate.candidate_key)

    matches.sort(key=_sort_key)
    primary_candidate, primary_artifact, primary_binding = matches[0]
    primary_branch_index = _derive_case_index_from_artifact(primary_artifact)

    envelope = EvidenceEnvelope(
        engine="souffle",
        support_kind=primary_artifact.kind,
        support_digest=primary_candidate.support_digest,
        case_index=primary_branch_index,
        proof=primary_artifact,
        branch_atom_projection=None,
    )

    return CheckResult(
        status="passed",
        requested_binding=request.binding,
        matched_count=len(matches),
        matched_binding=normalize_binding_items(primary_binding),
        evidence_envelope=envelope,
        errors=(),
        warnings=(),
    )


def _lookup_support_artifact(store: Store, digest: str) -> ProofReceipt | None:
    """Get the typed ProofReceipt behind a candidate's support_digest.

    Uses ``Store._lookup_support_artifact`` (typed internal API) instead of
    ``Store.explain_support`` (public consumer API that returns a rendered dict).
    Check runtime composes the typed artifact directly into ``EvidenceEnvelope``;
    consumers can serialize via ``explain_support`` themselves if needed.
    """
    return store._lookup_support_artifact(digest)


def _derive_case_index_from_artifact(artifact: ProofReceipt) -> int | None:
    """Extract the case_index from a ProofReceipt via c{n}.c{m}: prefix on condition keys.

    Per audit log Step 0.C C4: souffle ``case_index`` is derived from the
    artifact's condition keys (which encode ``c{case}.c{condition}:...``). Returns the
    integer if all keys agree on a case number; returns None if there are no
    keys to parse or if keys disagree (defensive fallback for sort).
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
    """Parse 'c{n}.c{m}:...' into the {n} integer, or None if not parseable."""
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


def _problog_pyreason_check(
    request: CheckRequest,
    *,
    store: Store,
    registry: RuleRegistry | None,
) -> CheckResult:
    """ProbLog / PyReason Check via evaluate-then-match against ProvenanceEnvelope.

    Algorithm (per audit log Step 0.C C3 / C4 / C6):

    - Delegate evaluate to ``evaluate_derivation_plans`` in the requested engine mode.
    - For each candidate, look up its ``ProvenanceEnvelope`` from store; engine-native
      provenance is preserved as-is in ``EvidenceEnvelope.proof`` (per §6.5
      engine-respectful evidence; not flattened into branch/atom view).
    - Extract the candidate's head-var binding via positional alignment between
      ``plan.heads[0].head_var_names`` and ``candidate.payload['terms']``. Bare
      (non-$-prefixed) head args are literals (per ``resolve_head_ref`` convention)
      and contribute no binding entry.
    - Subset-match each extracted binding against the requested binding.
    - Primary key = ``(candidate_key, binding_items)`` (per C4; ProbLog/PyReason have
      no per-branch concept so ``case_index`` stays None).

    Representability has already been gated at the request level by
    ``_request_representability_precheck`` (only-head-var requests reach here).
    Candidates whose provenance lookup returns None are silently skipped (mirrors
    Souffle path behavior — they cannot be matched representably).

    No provenance-fallback extractor is attempted in MVP (per audit log Step 0.C
    C3); that work belongs to the engine-extension-surface topic.
    """
    eval_request = DerivationEvaluateRequest(
        plans=(request.plan,),
        engine=request.engine,  # type: ignore[arg-type]
    )
    candidates = evaluate_derivation_plans(
        eval_request, store=store, registry=registry
    )

    matches: list[tuple[CandidateSet, ProvenanceEnvelope, dict[str, Any]]] = []
    for candidate in candidates:
        envelope_payload = _lookup_provenance_envelope(store, candidate.support_digest)
        if envelope_payload is None:
            continue
        binding_dict = _extract_head_var_binding(
            candidate=candidate, plan=request.plan
        )
        if _binding_matches(binding_dict, request.binding):
            matches.append((candidate, envelope_payload, binding_dict))

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

    def _sort_key(
        item: tuple[CandidateSet, ProvenanceEnvelope, dict[str, Any]],
    ) -> tuple[Any, ...]:
        candidate, _envelope, binding = item
        # Per C4: ProbLog/PyReason primary key is (candidate_key, binding_items).
        # No case_index participation.
        return (candidate.candidate_key, normalize_binding_items(binding))

    matches.sort(key=_sort_key)
    primary_candidate, primary_envelope, primary_binding = matches[0]

    envelope = EvidenceEnvelope(
        engine=request.engine,
        support_kind=primary_candidate.support_kind,
        support_digest=primary_candidate.support_digest,
        case_index=None,  # ProbLog/PyReason: no per-branch concept
        proof=primary_envelope,
        branch_atom_projection=None,
    )

    return CheckResult(
        status="passed",
        requested_binding=request.binding,
        matched_count=len(matches),
        matched_binding=normalize_binding_items(primary_binding),
        evidence_envelope=envelope,
        errors=(),
        warnings=(),
    )


def _lookup_provenance_envelope(
    store: Store, digest: str
) -> ProvenanceEnvelope | None:
    """Get the typed ProvenanceEnvelope behind a candidate's support_digest.

    Uses ``Store._lookup_provenance_envelope`` (typed internal API) instead of
    ``Store.explain_provenance`` (public consumer API that returns a rendered dict).
    Check runtime composes the typed envelope directly into ``EvidenceEnvelope``;
    consumers can serialize via ``explain_provenance`` themselves if needed.
    """
    return store._lookup_provenance_envelope(digest)


def _extract_head_var_binding(
    *, candidate: CandidateSet, plan: Any
) -> dict[str, Any]:
    """Extract var → value mapping from a candidate via head_var_names alignment.

    Per audit log Step 0.C C3: ProbLog/PyReason representability is bounded to
    head vars carried in ``candidate.payload['terms']``. This helper walks the
    positional alignment between ``plan.heads[0].head_var_names`` and the term
    list, producing a binding dict only for $-prefixed head vars (per
    ``resolve_head_ref`` convention; bare names are literals).

    Returns an empty dict on shape mismatch (length disagreement); the matching
    logic then falls through to "no match" naturally.
    """
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
    """Extract the underlying value from a candidate payload term.

    Term shapes (per ``_normalize_term_for_content`` in core/derivation/candidates.py):
    - ``{"kind": "entity_ref", "value": str}``
    - ``{"kind": "literal", "tag": str, "value": Any}``
    - ``{"kind": "candidate_ref", ...}`` (unrepresentable for MVP Check)
    - ``(tag, value)`` tuple (legacy form)
    """
    if isinstance(term, dict):
        kind = term.get("kind")
        if kind == "candidate_ref":
            return _UNREPRESENTABLE_TERM
        return term.get("value")
    if isinstance(term, tuple) and len(term) == 2:
        return term[1]
    return None


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
