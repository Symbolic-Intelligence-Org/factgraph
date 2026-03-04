from __future__ import annotations

import warnings
from typing import Any
from uuid import uuid4

from factpy_kernel.core.derivation.accept import AcceptOptions, AcceptRequest, AcceptResult
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
    BodyConfidencesIR,
    EngineEvaluatorFn,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    WhereIR,
)


_ENGINE_REGISTRY: dict[str, EngineEvaluatorFn] = {}


def register_engine_evaluator(
    evaluator: EngineEvaluatorFn | None,
    name: str,
) -> None:
    """Register (or clear) an engine evaluation adapter for Store.evaluate()."""
    if not isinstance(name, str) or not name:
        raise ValueError("name must be non-empty string")
    if evaluator is None:
        _ENGINE_REGISTRY.pop(name, None)
    else:
        _ENGINE_REGISTRY[name] = evaluator


def get_engine_evaluator(name: str) -> EngineEvaluatorFn | None:
    if not isinstance(name, str) or not name:
        raise ValueError("name must be non-empty string")
    return _ENGINE_REGISTRY.get(name)


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
        self._engine_overrides: dict[str, EngineEvaluatorFn] = {}
        if engine_evaluator is not None:
            self._engine_overrides["souffle"] = engine_evaluator

    def set_engine_evaluator(
        self,
        evaluator: EngineEvaluatorFn | None,
    ) -> None:
        if evaluator is None:
            self._engine_overrides.pop("souffle", None)
        else:
            self._engine_overrides["souffle"] = evaluator

    def evaluate(
        self,
        derivation_id: str,
        version: str,
        target_pred_id: str,
        head_vars: HeadVarsIR,
        where: WhereIR,
        mode: EvaluateMode = "native",
        head: HeadSpecIR | None = None,
        body_confidences: BodyConfidencesIR = None,
    ) -> list[CandidateSet]:
        return evaluate_store(
            self,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            where=where,
            mode=mode,
            head=head,
            body_confidences=body_confidences,
            engine_evaluate=self.evaluate_engine,
        )

    def evaluate_engine(
        self,
        derivation_id: str,
        version: str,
        target_pred_id: str,
        head_vars: HeadVarsIR,
        where: WhereIR,
        mode: str = "souffle",
        head: HeadSpecIR | None = None,
        body_confidences: list[float] | None = None,
    ) -> list[CandidateSet]:
        """Internal adapter entrypoint; prefer evaluate(mode='souffle'|'problog')."""
        if not isinstance(mode, str) or not mode:
            raise WhereValidationError("mode must be non-empty string")
        evaluator = self._engine_overrides.get(mode)
        if evaluator is None:
            evaluator = get_engine_evaluator(mode)
        if evaluator is None:
            raise WhereValidationError(
                f"{mode} evaluator not registered; import factpy_kernel.adapters.{mode} first"
            )
        call_kwargs: dict[str, Any] = {
            "derivation_id": derivation_id,
            "version": version,
            "target_pred_id": target_pred_id,
            "head_vars": head_vars,
            "where": where,
            "head": head,
        }
        if mode == "problog":
            call_kwargs["body_confidences"] = body_confidences
        return evaluator(self, **call_kwargs)

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
            "pred_id": target,
            "terms": [{"kind": "entity_ref", "value": e_ref}]
            + [{"kind": "literal", "tag": tag, "value": value} for tag, value in rest_terms],
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
            candidate_kind="fact",
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

    def accept_many(
        self,
        requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
        *,
        mode: str = "atomic",
        idempotent_duplicate_ok: bool = True,
    ) -> list[dict[str, Any]]:
        return _store_accept.accept_store_candidates_many(
            self,
            requests=requests,
            mode=mode,
            idempotent_duplicate_ok=idempotent_duplicate_ok,
        )

    def explain_fact(self, pred_id: str, e_ref: str, *val_atoms: Any) -> dict[str, Any]:
        return store_explain_fact(self, pred_id, e_ref, *val_atoms)

    def conflicts(self, pred_id: str, e_ref: str) -> dict[str, Any]:
        return store_conflicts(self, pred_id, e_ref)

    def resolve_mapping(self, pred_id: str, *, policy_mode: str = "edb") -> MappingResolution:
        return store_resolve_mapping(self, pred_id, policy_mode=policy_mode)


__all__ = ["Store", "register_engine_evaluator", "get_engine_evaluator"]
