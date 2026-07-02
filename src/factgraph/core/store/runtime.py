from __future__ import annotations

import warnings
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from factgraph.core.derivation.accept import AcceptOptions, AcceptRequest, AcceptResult
from factgraph.core.derivation.candidates import CandidateSet, make_candidate
from factgraph.core.evidence.write_protocol import now_epoch_nanos
from factgraph.core.mapping.canon import MappingResolution
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.core.rules._trace import RuleTraceArtifact
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store._explain_rule_trace import render_rule_trace_artifact
from factgraph.core.schema.schema_ir import ensure_schema_ir
from factgraph.core.store import _accept as _store_accept
from factgraph.core.store._artifact_sidecar import ArtifactSidecar
from factgraph.core.store._explain_support import render_support_artifact
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    ProvenanceEnvelope,
    ProofReceipt,
    provenance_envelope_to_dict,
)
from factgraph.core.store.evaluation import evaluate_store
from factgraph.core.store.ledger import Ledger
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    normalize_premise_allowances,
    normalize_premise_exclusions,
    premise_scoped_ledger,
)
from factgraph.core.store.queries import conflicts as store_conflicts
from factgraph.core.store.queries import explain_fact as store_explain_fact
from factgraph.core.store.queries import resolve_mapping as store_resolve_mapping
from factgraph.core.store.types import (
    EngineExtBase,
    EngineEvaluatorFn,
    EngineOptionsIR,
    EvaluateMode,
    HeadSpecIR,
    HeadVarsIR,
    WhereIR,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from factgraph.core.rules.rule_ir import RuleRegistry


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
        artifact_sidecar: ArtifactSidecar | None = None,
        premise_exclusions: "MetaExclusion | Iterable[MetaExclusion] | None" = None,
        premise_allowances: "PredicatePremiseAllowance | Iterable[PredicatePremiseAllowance] | None" = None,
    ) -> None:
        if not isinstance(schema_ir, dict):
            raise ValueError("schema_ir must be dict")
        self.schema_ir = ensure_schema_ir(schema_ir)
        self.ledger = ledger if ledger is not None else Ledger()
        self._premise_exclusions = normalize_premise_exclusions(premise_exclusions)
        self._premise_allowances = normalize_premise_allowances(premise_allowances)
        self._engine_overrides: dict[str, EngineEvaluatorFn] = {}
        self._artifact_sidecar = artifact_sidecar
        self._support_artifacts: dict[str, ProofReceipt] = {}
        self._provenance_envelopes: dict[str, ProvenanceEnvelope] = {}
        self._candidate_support_index: dict[str, str] = {}
        self._candidate_support_kind_index: dict[str, str] = {}
        self._candidate_confidence_kind_index: dict[str, str] = {}
        self._candidate_pred_index: dict[str, str] = {}
        self._rule_trace_artifacts: dict[str, RuleTraceArtifact] = {}
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

    @property
    def premise_exclusions(self) -> tuple[MetaExclusion, ...]:
        """Configured meta-based premise admissibility exclusions (empty = disabled)."""
        return self._premise_exclusions

    def set_premise_exclusions(
        self,
        exclusions: "MetaExclusion | Iterable[MetaExclusion] | None",
    ) -> None:
        """Configure evaluation premise exclusions; see core/store/premise_filter.py.

        Assertions whose meta rows carry an excluded key/value are invisible
        to every rule evaluation (all engine modes, proof-frame recheck, and
        the derivation check). Read/query paths outside evaluation stay
        unfiltered. Passing ``None`` or an empty iterable disables filtering.
        """
        self._premise_exclusions = normalize_premise_exclusions(exclusions)

    @property
    def premise_allowances(self) -> tuple[PredicatePremiseAllowance, ...]:
        """Configured per-predicate premise admissibility allowances (empty = disabled)."""
        return self._premise_allowances

    def set_premise_allowances(
        self,
        allowances: "PredicatePremiseAllowance | Iterable[PredicatePremiseAllowance] | None",
    ) -> None:
        """Configure per-predicate evaluation allowances; see core/store/premise_filter.py.

        For each configured predicate, an assertion of that predicate is
        visible to rule evaluation only when its meta ``key`` last-value is in
        the predicate's ``allowed_values`` (an assertion missing the key is
        admitted only when ``absent_ok`` is set). Predicates without an entry
        are unaffected. This is OR-combined with ``premise_exclusions`` (an
        assertion excluded by either is invisible), so the global exclusion
        floor is never lifted. Passing ``None`` or an empty iterable disables
        per-predicate filtering.
        """
        self._premise_allowances = normalize_premise_allowances(allowances)

    def _remember_support_artifact(
        self,
        support_digest: str,
        artifact: ProofReceipt,
    ) -> None:
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must be sha256 token")
        if not isinstance(artifact, ProofReceipt):
            raise ValueError("artifact must be ProofReceipt")
        existing = self._support_artifacts.get(support_digest)
        if existing is None:
            if self._artifact_sidecar is not None:
                self._artifact_sidecar.write_support(support_digest, artifact)
            self._support_artifacts[support_digest] = artifact
            return
        if existing != artifact:
            raise ValueError("support_digest collision for different ProofReceipt")

    def _lookup_support_artifact(
        self,
        support_digest: str,
    ) -> ProofReceipt | None:
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must be sha256 token")
        artifact = self._support_artifacts.get(support_digest)
        if artifact is not None:
            return artifact
        if self._artifact_sidecar is None:
            return None
        artifact = self._artifact_sidecar.read_support(support_digest)
        if artifact is None:
            return None
        self._support_artifacts[support_digest] = artifact
        return artifact

    def _remember_provenance_envelope(
        self,
        support_digest: str,
        envelope: ProvenanceEnvelope,
    ) -> None:
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must be sha256 token")
        if not isinstance(envelope, ProvenanceEnvelope):
            raise ValueError("envelope must be ProvenanceEnvelope")
        existing = self._provenance_envelopes.get(support_digest)
        if existing is None:
            self._provenance_envelopes[support_digest] = envelope
            return
        if existing != envelope:
            raise ValueError("support_digest collision for different ProvenanceEnvelope")

    def _lookup_provenance_envelope(
        self,
        support_digest: str,
    ) -> ProvenanceEnvelope | None:
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must be sha256 token")
        return self._provenance_envelopes.get(support_digest)

    def _remember_candidate_support(
        self,
        candidate_id: str,
        support_digest: str,
        support_kind: str,
        *,
        confidence_kind: str = "none",
        target_pred_id: str = "",
    ) -> None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id must be non-empty string")
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must be sha256 token")
        if not isinstance(support_kind, str) or not support_kind:
            raise ValueError("support_kind must be non-empty string")
        if not isinstance(confidence_kind, str) or not confidence_kind:
            raise ValueError("confidence_kind must be non-empty string")
        if not isinstance(target_pred_id, str):
            raise ValueError("target_pred_id must be string")
        if candidate_id in self._candidate_support_index:
            existing_digest = self._candidate_support_index[candidate_id]
            if existing_digest != support_digest:
                raise ValueError(
                    f"candidate_id {candidate_id!r} already registered with "
                    f"different support_digest"
                )
            self._candidate_support_kind_index.setdefault(candidate_id, support_kind)
            self._candidate_confidence_kind_index.setdefault(candidate_id, confidence_kind)
            self._candidate_pred_index.setdefault(candidate_id, target_pred_id)
            return
        self._candidate_support_index[candidate_id] = support_digest
        self._candidate_support_kind_index[candidate_id] = support_kind
        self._candidate_confidence_kind_index[candidate_id] = confidence_kind
        self._candidate_pred_index[candidate_id] = target_pred_id

    def _lookup_candidate_support(
        self,
        candidate_id: str,
    ) -> str | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id must be non-empty string")
        return self._candidate_support_index.get(candidate_id)

    def _lookup_candidate_support_kind(
        self,
        candidate_id: str,
    ) -> str | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id must be non-empty string")
        return self._candidate_support_kind_index.get(candidate_id)

    def _lookup_candidate_confidence_kind(
        self,
        candidate_id: str,
    ) -> str | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id must be non-empty string")
        return self._candidate_confidence_kind_index.get(candidate_id)

    def _remember_rule_trace_artifact(
        self,
        rule_run_id: str,
        artifact: RuleTraceArtifact,
    ) -> None:
        if not isinstance(rule_run_id, str) or not rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")
        if not isinstance(artifact, RuleTraceArtifact):
            raise ValueError("artifact must be RuleTraceArtifact")
        existing = self._rule_trace_artifacts.get(rule_run_id)
        if existing is None:
            if self._artifact_sidecar is not None:
                self._artifact_sidecar.write_rule_trace(rule_run_id, artifact)
            self._rule_trace_artifacts[rule_run_id] = artifact
            return
        if existing != artifact:
            raise ValueError("rule_run_id collision for different RuleTraceArtifact")

    def _lookup_rule_trace_artifact(
        self,
        rule_run_id: str,
    ) -> RuleTraceArtifact | None:
        if not isinstance(rule_run_id, str) or not rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")
        artifact = self._rule_trace_artifacts.get(rule_run_id)
        if artifact is not None:
            return artifact
        if self._artifact_sidecar is None:
            return None
        artifact = self._artifact_sidecar.read_rule_trace(rule_run_id)
        if artifact is None:
            return None
        self._rule_trace_artifacts[rule_run_id] = artifact
        return artifact

    def evaluate(
        self,
        derivation_id: str,
        version: str,
        target_pred_id: str,
        head_vars: HeadVarsIR,
        where: WhereIR,
        mode: EvaluateMode = "native",
        head: HeadSpecIR | None = None,
        registry: "RuleRegistry | None" = None,
        confidence_kind_resolver: Any | None = None,
        engine_ext: EngineExtBase | None = None,
        engine_options: EngineOptionsIR = None,
        semantics_profile: Any | None = None,
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
            engine_evaluate=self.evaluate_engine,
            registry=registry,
            confidence_kind_resolver=confidence_kind_resolver,
            engine_ext=engine_ext,
            engine_options=engine_options,
            semantics_profile=semantics_profile,
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
        engine_ext: EngineExtBase | None = None,
        engine_options: EngineOptionsIR = None,
        semantics_profile: Any | None = None,
    ) -> list[CandidateSet]:
        """Internal adapter entrypoint; prefer evaluate(mode='souffle'|'problog'|'pyreason')."""
        if not isinstance(mode, str) or not mode:
            raise WhereValidationError("mode must be non-empty string")
        evaluator = self._engine_overrides.get(mode)
        if evaluator is None:
            evaluator = get_engine_evaluator(mode)
        if evaluator is None:
            raise WhereValidationError(
                f"{mode} evaluator not registered; import factgraph.adapters.{mode} first"
            )
        call_kwargs: dict[str, Any] = {
            "derivation_id": derivation_id,
            "version": version,
            "target_pred_id": target_pred_id,
            "head_vars": head_vars,
            "where": where,
            "head": head,
        }
        if engine_ext is not None:
            call_kwargs["engine_ext"] = engine_ext
        if engine_options is not None:
            call_kwargs["engine_options"] = engine_options
        if semantics_profile is not None:
            call_kwargs["semantics_profile"] = semantics_profile
        # Premise admissibility: engine adapters read all facts through
        # store.ledger (souffle/problog exports, pyreason projection, witness
        # reconstruction). Handing them the premise-scoped view is the single
        # seam that filters every engine mode without engine-specific logic.
        # Zero-config returns ``self`` unchanged.
        return evaluator(premise_scoped_store_view(self), **call_kwargs)

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
            support_kind=ENGINE_NO_WITNESS_KIND,
            generated_at=now_epoch_nanos(),
            tup_digest=tup_digest,
            state="generated",
            candidate_kind="fact",
            confidence_kind="none",
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

    def explain_support(self, support_digest: str) -> dict[str, Any] | None:
        artifact = self._lookup_support_artifact(support_digest)
        if artifact is None:
            return None
        return render_support_artifact(artifact)

    def explain_provenance(self, support_digest: str) -> dict[str, Any] | None:
        envelope = self._lookup_provenance_envelope(support_digest)
        if envelope is None:
            return None
        return provenance_envelope_to_dict(envelope)

    def get_candidate_support_digest(self, candidate_id: str) -> str | None:
        return self._lookup_candidate_support(candidate_id)

    def get_candidate_support_kind(self, candidate_id: str) -> str | None:
        return self._lookup_candidate_support_kind(candidate_id)

    def get_candidate_confidence_kind(self, candidate_id: str) -> str | None:
        return self._lookup_candidate_confidence_kind(candidate_id)

    def get_candidate_pred_id(self, candidate_id: str) -> str | None:
        return self._candidate_pred_index.get(candidate_id)

    def list_candidate_ids(self) -> list[str]:
        return sorted(self._candidate_support_index.keys())

    def explain_rule_trace(self, rule_run_id: str) -> dict[str, Any] | None:
        artifact = self._lookup_rule_trace_artifact(rule_run_id)
        if artifact is None:
            return None
        return render_rule_trace_artifact(artifact)

    def explain_fact(self, pred_id: str, e_ref: str, *val_atoms: Any) -> dict[str, Any]:
        return store_explain_fact(self, pred_id, e_ref, *val_atoms)

    def conflicts(self, pred_id: str, e_ref: str) -> dict[str, Any]:
        return store_conflicts(self, pred_id, e_ref)

    def resolve_mapping(self, pred_id: str, *, policy_mode: str = "edb") -> MappingResolution:
        return store_resolve_mapping(self, pred_id, policy_mode=policy_mode)


class _PremiseScopedStore(Store):
    """Per-evaluation-call view of a Store with a premise-filtered ledger.

    Everything except ``ledger`` is the base store: attribute reads fall
    through to the base (support-artifact dicts, engine overrides, sidecar,
    dynamic adapter state such as ``_problog_pending_annotations``) and
    attribute writes land on the base, so ``_remember_*`` bookkeeping during
    evaluation mutates the real store. Subclassing keeps the adapters'
    ``isinstance(store, Store)`` gates (souffle package export, problog
    export) satisfied. Instances are transient — constructed per evaluate
    call by ``premise_scoped_store_view`` and never persisted.
    """

    def __init__(self, base: Store, ledger: Ledger) -> None:
        # Deliberately no Store.__init__: this is a view, not a new store.
        object.__setattr__(self, "_premise_base", base)
        object.__setattr__(self, "ledger", ledger)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_premise_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_premise_base"), name, value)


def premise_scoped_store_view(store: Store) -> Store:
    """Return ``store`` unchanged when neither exclusions nor allowances are configured, else a premise-scoped view.

    With either dimension configured the view is always introduced — visibility
    is decided live per access inside the scoped ledger (see premise_filter.py),
    so a fact classified only after view construction is still filtered.
    """
    if isinstance(store, _PremiseScopedStore):
        return store
    exclusions = getattr(store, "premise_exclusions", ())
    allowances = getattr(store, "premise_allowances", ())
    if not exclusions and not allowances:
        return store
    scoped_ledger = premise_scoped_ledger(store.ledger, exclusions, allowances)
    if scoped_ledger is store.ledger:
        return store
    return _PremiseScopedStore(store, scoped_ledger)


__all__ = [
    "Store",
    "premise_scoped_store_view",
    "register_engine_evaluator",
    "get_engine_evaluator",
]
