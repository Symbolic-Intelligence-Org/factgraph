"""Application-layer derivation runtime executor.

Commit 1 scope: thin orchestrator that returns core CandidateSet / AcceptResult /
accept_many output without wrapping them in application-specific DTOs.

- evaluate_derivation_plans iterates plans and heads, calls evaluate_store per head
  using store.evaluate_engine as the EngineEvaluatorFn, and returns the flattened
  list of CandidateSet objects.
- accept_derivation_candidate_sets passes through to
  kernel.core.derivation.accept.accept_many_candidate_sets.

Body confidence handling, multi-head shared run_id propagation, and engine_ext
construction are intentionally not wired here. SDK adapters (commit 2) are
expected to provide engine-specific options via the existing core APIs while
authoring lowering / payload normalization stays on the SDK side.
"""
from __future__ import annotations

from typing import Any

from kernel.core.derivation.accept import (
    AcceptOptions,
    AcceptResult,
    accept_candidate_set,
    accept_many_candidate_sets,
)
from kernel.core.derivation.candidates import CandidateSet
from kernel.core.store._evaluate import evaluate_store
from kernel.core.store.runtime import Store

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
) -> list[CandidateSet]:
    """Evaluate compiled derivation plans against the store.

    For each plan the executor iterates over the plan's heads and calls
    kernel.core.store._evaluate.evaluate_store once per head, using
    ``store.evaluate_engine`` as the EngineEvaluatorFn. The flattened list of
    CandidateSet objects is returned to the caller (no application-side wrapping).
    """
    candidate_sets: list[CandidateSet] = []
    for plan in request.plans:
        candidate_sets.extend(
            _evaluate_plan(plan, request=request, store=store, registry=registry)
        )
    return candidate_sets


def _evaluate_plan(
    plan: CompiledDerivationPlan,
    *,
    request: DerivationEvaluateRequest,
    store: Store,
    registry: Any | None,
) -> list[CandidateSet]:
    engine_options = dict(plan.engine_options) if plan.engine_options else None
    results: list[CandidateSet] = []
    for head in plan.heads:
        head_results = evaluate_store(
            store,
            derivation_id=plan.derivation_id,
            version=plan.version,
            target_pred_id=head.target_pred_id,
            head_vars=list(head.head_var_names),
            where=list(plan.body_ir),
            mode=request.engine,
            engine_evaluate=store.evaluate_engine,
            registry=registry,
            engine_options=engine_options,
        )
        results.extend(head_results)
    return results


def accept_derivation_candidate_set(
    candidate_set: CandidateSet,
    accept_request: DerivationAcceptRequest,
    *,
    store: Store,
    derived_rule_id: str,
    derived_rule_version: str,
) -> AcceptResult:
    """Accept a single CandidateSet against the store ledger.

    Thin wrapper over kernel.core.derivation.accept.accept_candidate_set; SDK
    adapters keep responsibility for resolved_candidate_refs, schema/policy digest
    tokens, and schema_ir provisioning.
    """
    options = AcceptOptions(idempotent_duplicate_ok=accept_request.idempotent_duplicate_ok)
    return accept_candidate_set(
        store.ledger,
        candidate_set,
        options,
        derived_rule_id,
        derived_rule_version,
    )


def accept_derivation_candidate_sets(
    candidate_sets: list[CandidateSet],
    accept_request: DerivationAcceptRequest,
    *,
    store: Store,
) -> list[dict[str, Any]]:
    """Accept many CandidateSets against the store ledger.

    Pass-through to kernel.core.derivation.accept.accept_many_candidate_sets;
    callers receive the raw list[dict[str, Any]] result without application-side
    rewrapping.
    """
    if not candidate_sets:
        return []
    return accept_many_candidate_sets(
        store.ledger,
        list(candidate_sets),
        mode="atomic" if accept_request.accept_mode == "atomic" else "best_effort",
        idempotent_duplicate_ok=accept_request.idempotent_duplicate_ok,
    )


__all__ = [
    "DerivationRuntimeError",
    "accept_derivation_candidate_set",
    "accept_derivation_candidate_sets",
    "evaluate_derivation_plans",
]
