from __future__ import annotations

import warnings
from typing import Any
from uuid import uuid4

from factpy_kernel.core.derivation.accept import AcceptOptions, AcceptResult
from factpy_kernel.core.derivation.candidates import CandidateSet, make_candidate
from factpy_kernel.core.evidence.write_protocol import now_epoch_nanos
from factpy_kernel.core.mapping.canon import MappingResolution
from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.schema.schema_ir import ensure_schema_ir
from factpy_kernel.core.store import _accept as _store_accept
from factpy_kernel.core.store.evaluation import evaluate_store
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.core.store.queries import conflicts as store_conflicts
from factpy_kernel.core.store.queries import explain_fact as store_explain_fact
from factpy_kernel.core.store.queries import resolve_mapping as store_resolve_mapping
from factpy_kernel.core.store.types import (
    EngineEvaluatorFn,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    IdPolicyIR,
    MaterializeAs,
    TemporalView,
    WhereIR,
)


_ENGINE_EVALUATOR: EngineEvaluatorFn | None = None


def register_engine_evaluator(
    evaluator: EngineEvaluatorFn | None,
) -> None:
    """Register an engine evaluation adapter for Store.evaluate(mode='engine')."""
    global _ENGINE_EVALUATOR
    _ENGINE_EVALUATOR = evaluator


class Store:
    def __init__(
        self,
        schema_ir: dict,
        ledger: Ledger | None = None,
        *,
        engine_evaluator: EngineEvaluatorFn | None = None,
    ) -> None:
        if not isinstance(schema_ir, dict):
            raise ValueError("schema_ir must be dict")
        self.schema_ir = ensure_schema_ir(schema_ir)
        self.ledger = ledger if ledger is not None else Ledger()
        self._engine_evaluator = engine_evaluator

    def set_engine_evaluator(
        self,
        evaluator: EngineEvaluatorFn | None,
    ) -> None:
        self._engine_evaluator = evaluator

    def evaluate(
        self,
        derivation_id: str,
        version: str,
        target_pred_id: str,
        head_vars: HeadVarsIR,
        where: WhereIR,
        mode: EvaluateMode = "python",
        temporal_view: TemporalView = "record",
        materialize_as: MaterializeAs = None,
        head: HeadSpecIR | None = None,
        id_policy: IdPolicyIR | None = None,
    ) -> list[CandidateSet]:
        return evaluate_store(
            self,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            where=where,
            mode=mode,
            temporal_view=temporal_view,
            materialize_as=materialize_as,
            head=head,
            id_policy=id_policy,
            engine_evaluate=self.evaluate_engine,
        )

    def evaluate_engine(
        self,
        derivation_id: str,
        version: str,
        target_pred_id: str,
        head_vars: HeadVarsIR,
        where: WhereIR,
        temporal_view: TemporalView = "record",
        materialize_as: MaterializeAs = None,
        head: HeadSpecIR | None = None,
        id_policy: IdPolicyIR | None = None,
    ) -> list[CandidateSet]:
        """Internal/legacy entrypoint; prefer evaluate(mode='engine')."""
        if temporal_view not in {"record", "current"}:
            raise ValueError("temporal_view must be 'record' or 'current'")
        evaluator = self._engine_evaluator if self._engine_evaluator is not None else _ENGINE_EVALUATOR
        if evaluator is None:
            raise WhereValidationError(
                "engine evaluator not registered; import factpy_kernel.adapters.souffle first"
            )
        return evaluator(
            self,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            where=where,
            temporal_view=temporal_view,
            materialize_as=materialize_as,
            head=head,
            id_policy=id_policy,
        )

    def evaluate_dummy(
        self,
        derivation_id: str,
        version: str,
        target: str,
        e_ref: str,
        rest_terms: list[tuple[str, Any]],
        dims_terms: list[tuple[str, Any]],
    ) -> CandidateSet:
        warnings.warn(
            "evaluate_dummy is deprecated; use evaluate()",
            DeprecationWarning,
            stacklevel=2,
        )

        run_id = uuid4().hex
        key_terms = [("string", target), ("entity_ref", e_ref), *dims_terms]
        payload = {
            "e_ref": e_ref,
            "rest_terms": list(rest_terms),
        }
        tup_digest = sha256_token(canonical_bytes_tup_v1(rest_terms))
        return make_candidate(
            derivation_id=derivation_id,
            derivation_version=version,
            run_id=run_id,
            target=target,
            key_terms=key_terms,
            payload=payload,
            support_digest=f"sha256:{'0' * 64}",
            support_kind="none",
            generated_at=now_epoch_nanos(),
            tup_digest=tup_digest,
            state="generated",
        )

    def accept(
        self,
        derivation_id: str,
        version: str,
        candidate_set: CandidateSet,
        options: AcceptOptions,
    ) -> AcceptResult:
        return _store_accept.accept_store_candidate(
            self,
            derivation_id=derivation_id,
            version=version,
            candidate_set=candidate_set,
            options=options,
        )

    def explain_fact(self, pred_id: str, e_ref: str, *val_atoms: Any) -> dict[str, Any]:
        return store_explain_fact(self, pred_id, e_ref, *val_atoms)

    def conflicts(self, pred_id: str, e_ref: str) -> dict[str, Any]:
        return store_conflicts(self, pred_id, e_ref)

    def resolve_mapping(self, pred_id: str, *, policy_mode: str = "edb") -> MappingResolution:
        return store_resolve_mapping(self, pred_id, policy_mode=policy_mode)


__all__ = ["Store", "register_engine_evaluator"]
