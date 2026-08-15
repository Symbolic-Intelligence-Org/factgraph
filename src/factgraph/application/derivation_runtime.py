"""Application-layer derivation runtime executor.

Commit 1 scope: thin orchestrator that returns core DerivationOutput / AcceptResult /
accept_many output without wrapping them in application-specific DTOs.

- evaluate_derivation_plans iterates plans and heads, calls evaluate_store per head
  using store.evaluate_engine as the EngineEvaluatorFn, and returns the flattened
  list of DerivationOutput objects.
- materialization wrappers delegate through Store-owned write seams so Store
  schema/policy digest enrichment is preserved. The single-item application
  seam may retain a stable authored/business rule identity distinct from a
  compiler-generated output identity.

Commit 2a parity:
- ``CompiledDerivationPlan.head_spec`` (HeadSpecIR dict) is forwarded as the
  ``head=`` payload to ``evaluate_store`` when set; in that case ``len(heads) == 1``
  and ``heads[0]`` provides ``target_pred_id`` / ``head_var_names``.
- ``CompiledDerivationPlan.engine_ext`` (``EngineExtBase``) is forwarded.
- Multi-plan ``run_id`` is propagated by rebuilding each ``DerivationOutput`` with the
  shared ``run_id`` via ``dataclasses.replace``.
- ``DerivationAcceptRequest`` exposes the legitimate ``AcceptOptions`` fields
  (``approved_by``/``note``/``dry_run``/``identity_override``); ``idempotent_duplicate_ok``
  remains an ``accept_many`` flag and is intentionally not part of ``AcceptOptions``.
"""
from __future__ import annotations

from dataclasses import replace
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from factgraph.core.derivation.accept import (
    AcceptOptions,
    AcceptRequest,
    AcceptResult,
)
from factgraph.core.derivation.candidates import CandidateSet, DerivationOutput
from factgraph.core.store import _accept as _store_accept
from factgraph.core.store._evaluate import (
    _NativeEffectiveRelationObserver,
    _NativeEffectiveRelationSnapshot,
    _NativeEffectiveRelationSupportArtifactObserver,
    _evaluate_store,
)
from factgraph.core.store._support import ProofReceipt, ProjectedFact, compute_support_digest
from factgraph.core.store.runtime import Store

from .protocol import (
    CompiledDerivationPlan,
    DerivationAcceptRequest,
    DerivationEvaluateRequest,
    ErrorDTO,
)


class DerivationRuntimeError(ValueError):
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


def evaluate_derivation_plans(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
    registry: Any | None = None,
) -> list[DerivationOutput]:
    """Evaluate compiled derivation plans against the store.

    For each plan the executor iterates over the plan's heads and calls
    factgraph.core.store._evaluate.evaluate_store once per head, using
    ``store.evaluate_engine`` as the EngineEvaluatorFn. The flattened list of
    DerivationOutput objects is returned to the caller (no application-side wrapping).
    """
    return _evaluate_derivation_plans(
        request,
        store=store,
        registry=registry,
        _native_effective_relation_observer=None,
    )


def _evaluate_derivation_plans_with_native_relation_capture(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
) -> tuple[list[DerivationOutput], _NativeEffectiveRelationSnapshot]:
    """Private atomic-capture seam for the SDK EvaluationRun bundle path."""
    if (
        request.engine != "native"
        or len(request.plans) != 1
        or len(request.plans[0].heads) != 1
    ):
        raise DerivationRuntimeError(
            "native relation capture requires one native plan with one head",
            code="NATIVE_RELATION_CAPTURE_SCOPE",
        )
    observed: list[_NativeEffectiveRelationSnapshot] = []
    outputs = _evaluate_derivation_plans(
        request,
        store=store,
        registry=None,
        _native_effective_relation_observer=observed.append,
    )
    if len(observed) != 1:
        raise DerivationRuntimeError(
            "native relation capture requires exactly one evaluated plan head",
            code="NATIVE_RELATION_CAPTURE_CARDINALITY",
        )
    return outputs, observed[0]


def _evaluate_derivation_plans_with_native_effective_relation(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
    effective_relation: Mapping[str, Sequence[ProjectedFact]],
) -> list[DerivationOutput]:
    """Private no-provenance seam for one in-memory native Query relation.

    This is intentionally distinct from EvaluationRun capture: the supplied
    relation may contain a synthetic Scenario hypothesis witness and must never
    be recorded in a Store proof sidecar or candidate-support index.
    """

    if (
        request.engine != "native"
        or len(request.plans) != 1
        or len(request.plans[0].heads) != 1
    ):
        raise DerivationRuntimeError(
            "native effective relation execution requires one native plan with one head",
            code="NATIVE_EFFECTIVE_RELATION_SCOPE",
        )
    return _evaluate_derivation_plans(
        request,
        store=store,
        registry=None,
        _native_effective_relation_observer=None,
        _native_effective_relation_override=effective_relation,
        _record_support_artifacts=False,
    )


def _evaluate_derivation_plans_with_native_effective_relation_capture(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
    effective_relation: Mapping[str, Sequence[ProjectedFact]],
) -> tuple[list[DerivationOutput], Mapping[str, ProofReceipt]]:
    """Capture native receipts for an in-memory Scenario relation without Store writes.

    This is intentionally private.  Unlike ordinary EvaluationRun capture, the
    relation may contain Scenario-only synthetic witnesses.  Receipts therefore
    live only in the returned immutable mapping and never enter a support
    sidecar or candidate-support index.
    """

    if (
        request.engine != "native"
        or len(request.plans) != 1
        or len(request.plans[0].heads) != 1
    ):
        raise DerivationRuntimeError(
            "native effective relation capture requires one native plan with one head",
            code="NATIVE_EFFECTIVE_RELATION_CAPTURE_SCOPE",
        )
    artifacts: dict[str, ProofReceipt] = {}

    def _observe(digest: str, artifact: ProofReceipt) -> None:
        existing = artifacts.get(digest)
        if existing is not None and existing != artifact:
            raise DerivationRuntimeError(
                "native effective relation capture observed a support digest collision",
                code="NATIVE_EFFECTIVE_RELATION_SUPPORT_COLLISION",
            )
        artifacts[digest] = artifact

    observer: _NativeEffectiveRelationSupportArtifactObserver = _observe
    outputs = _evaluate_derivation_plans(
        request,
        store=store,
        registry=None,
        _native_effective_relation_observer=None,
        _native_effective_relation_override=effective_relation,
        _record_support_artifacts=False,
        _native_effective_relation_support_artifact_observer=observer,
    )
    for output in outputs:
        artifact = artifacts.get(output.support_digest)
        if (
            output.support_kind != "native_binding_v1"
            or artifact is None
            or compute_support_digest(artifact) != output.support_digest
        ):
            raise DerivationRuntimeError(
                "native effective relation capture did not retain an exact receipt for every output",
                code="NATIVE_EFFECTIVE_RELATION_CAPTURE_INCOMPLETE",
            )
    return outputs, MappingProxyType(dict(sorted(artifacts.items())))


def _evaluate_derivation_plans(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
    registry: Any | None,
    _native_effective_relation_observer: _NativeEffectiveRelationObserver | None,
    _native_effective_relation_override: Mapping[str, Sequence[ProjectedFact]] | None = None,
    _record_support_artifacts: bool = True,
    _native_effective_relation_support_artifact_observer: (
        _NativeEffectiveRelationSupportArtifactObserver | None
    ) = None,
) -> list[DerivationOutput]:
    outputs: list[DerivationOutput] = []
    for plan in request.plans:
        outputs.extend(
            _evaluate_plan(
                plan,
                request=request,
                store=store,
                registry=registry,
                _native_effective_relation_observer=_native_effective_relation_observer,
                _native_effective_relation_override=_native_effective_relation_override,
                _record_support_artifacts=_record_support_artifacts,
                _native_effective_relation_support_artifact_observer=(
                    _native_effective_relation_support_artifact_observer
                ),
            )
        )
    if request.run_id is not None and len(request.plans) > 1:
        outputs = _attach_run_id(outputs, run_id=request.run_id)
    return outputs


def _evaluate_plan(
    plan: CompiledDerivationPlan,
    *,
    request: DerivationEvaluateRequest,
    store: Store,
    registry: Any | None,
    _native_effective_relation_observer: _NativeEffectiveRelationObserver | None,
    _native_effective_relation_override: Mapping[str, Sequence[ProjectedFact]] | None,
    _record_support_artifacts: bool,
    _native_effective_relation_support_artifact_observer: (
        _NativeEffectiveRelationSupportArtifactObserver | None
    ),
) -> list[DerivationOutput]:
    engine_options = dict(plan.engine_options) if plan.engine_options else None
    if plan.head_spec is not None:
        # Single-head call with the HeadSpecIR forwarded; heads tuple length 1 invariant
        # is enforced at CompiledDerivationPlan __post_init__.
        primary = plan.heads[0]
        return list(
            _evaluate_store(
                store,
                derivation_id=plan.derivation_id,
                version=plan.version,
                target_pred_id=primary.target_pred_id,
                head_vars=list(primary.head_var_names),
                where=list(plan.body_ir),
                mode=request.engine,
                head=dict(plan.head_spec),
                engine_evaluate=store.evaluate_engine,
                registry=registry,
                engine_ext=plan.engine_ext,
                engine_options=engine_options,
                semantics_profile=request.semantics_profile,
                _native_effective_relation_observer=_native_effective_relation_observer,
                _native_effective_relation_override=_native_effective_relation_override,
                _record_support_artifacts=_record_support_artifacts,
                _native_effective_relation_support_artifact_observer=(
                    _native_effective_relation_support_artifact_observer
                ),
            )
        )

    results: list[DerivationOutput] = []
    for head in plan.heads:
        head_results = _evaluate_store(
            store,
            derivation_id=plan.derivation_id,
            version=plan.version,
            target_pred_id=head.target_pred_id,
            head_vars=list(head.head_var_names),
            where=list(plan.body_ir),
            mode=request.engine,
            engine_evaluate=store.evaluate_engine,
            registry=registry,
            engine_ext=plan.engine_ext,
            engine_options=engine_options,
            semantics_profile=request.semantics_profile,
            _native_effective_relation_observer=_native_effective_relation_observer,
            _native_effective_relation_override=_native_effective_relation_override,
            _record_support_artifacts=_record_support_artifacts,
            _native_effective_relation_support_artifact_observer=(
                _native_effective_relation_support_artifact_observer
            ),
        )
        results.extend(head_results)
    return results


def _attach_run_id(
    outputs: list[DerivationOutput], *, run_id: str
) -> list[DerivationOutput]:
    return [
        replace(
            candidate,
            run_id=run_id,
            payload=dict(candidate.payload),
            candidate_id="",
        )
        for candidate in outputs
    ]


def accept_derivation_candidate_set(
    candidate_set: CandidateSet,
    accept_request: DerivationAcceptRequest,
    *,
    store: Store,
    derived_rule_id: str,
    derived_rule_version: str,
) -> AcceptResult:
    """Accept a single CandidateSet against the store ledger.

    The application wrapper delegates to the Store-owned enriched write seam.
    It preserves the established application contract in which the declared
    authored/business rule identity can differ from a compiler-generated output
    identity; direct ``Store.accept`` keeps its stricter identity-match guard.
    """
    options = AcceptOptions(
        approved_by=accept_request.approved_by,
        note=accept_request.note,
        dry_run=accept_request.dry_run,
        identity_override=(
            dict(accept_request.identity_override)
            if accept_request.identity_override is not None
            else None
        ),
        # Forward the caller's actor/business provenance onto the derived assertions
        # (DerivationAcceptRequest.meta -> AcceptOptions.actor_meta -> write meta).
        actor_meta=dict(accept_request.meta) if accept_request.meta else None,
    )
    return _store_accept._accept_store_candidate_as_derived_rule(
        store,
        derivation_id=derived_rule_id,
        version=derived_rule_version,
        candidate_set=candidate_set,
        options=options,
    )


def accept_derivation_candidate_sets(
    candidate_sets: list[CandidateSet],
    accept_request: DerivationAcceptRequest,
    *,
    store: Store,
) -> list[dict[str, Any]]:
    """Accept many CandidateSets against the store ledger.

    Delegates to the Store-owned batch write seam after preserving per-item intent.
    Batch dry-run is not implemented by the core protocol and therefore fails closed.
    """
    if not candidate_sets:
        return []
    if accept_request.dry_run:
        raise DerivationRuntimeError(
            "batch acceptance does not support dry_run=True",
            code="DERIVATION_BATCH_DRY_RUN_UNSUPPORTED",
            path=("accept_request", "dry_run"),
        )
    if len(candidate_sets) > 1 and accept_request.identity_override is not None:
        raise DerivationRuntimeError(
            "identity_override is ambiguous for multiple derivation outputs",
            code="DERIVATION_BATCH_IDENTITY_OVERRIDE_AMBIGUOUS",
            path=("accept_request", "identity_override"),
        )
    requests: list[AcceptRequest | CandidateSet | dict[str, Any]] = [
        AcceptRequest(
            candidate_set=candidate_set,
            identity_override=(
                dict(accept_request.identity_override)
                if accept_request.identity_override is not None
                else None
            ),
            approved_by=accept_request.approved_by,
            note=accept_request.note,
            actor_meta=dict(accept_request.meta) if accept_request.meta else None,
        )
        for candidate_set in candidate_sets
    ]
    return store.accept_many(
        requests,
        mode="atomic" if accept_request.accept_mode == "atomic" else "best_effort",
        idempotent_duplicate_ok=accept_request.idempotent_duplicate_ok,
    )


__all__ = [
    "DerivationRuntimeError",
    "accept_derivation_candidate_set",
    "accept_derivation_candidate_sets",
    "evaluate_derivation_plans",
    "_evaluate_derivation_plans_with_native_effective_relation_capture",
]
