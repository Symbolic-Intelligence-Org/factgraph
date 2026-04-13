from __future__ import annotations

from time import time_ns
from typing import Any, Literal

from .candidate_cache import CandidatePayloadCache
from .documents import (
    BundleCommitResult,
    BundleManager,
    BundleReviewAction,
    DocumentSegment,
    DocumentStaging,
    DraftBundle,
    FactDraftSpec,
    StagingError,
    StagingResult,
)
from .documents.bundle import _provenance_to_draft_source
from .draft import DraftManager, FactDraft
from .errors import AgentContractError, AgentRuntimeError, AgentScopeViolation
from .extraction import (
    BatchExtractionConfig,
    BatchExtractionError,
    BatchExtractionResult,
    BatchExtractor,
    EntityResolver,
    ExtractionAgent,
    ExtractionConfig,
    ExtractionError,
    ExtractionResult,
    ResolutionConfig,
    ResolutionError,
    ResolutionResult,
)
from .recovery import AgentCheckpointStore
from .session import AgentScopeGuard, AgentSession
from .tools._runtime_api import require_ok
from .tools.evaluate import (
    AcceptResult,
    CacheRecoveryOutcome,
    CandidateReviewItem,
    EvaluateRequest,
    EvaluateResult,
    EvaluateTools,
)
from .tools.explain import EvidenceTreeResult, ExplainStep, ExplainSummary, ExplainTools, TimelineResult
from .tools.kg_read import CandidateSummary, ClaimResult, EntitySnapshot, KGReadTools, RuleSummary
from .tools.rules import (
    CompilePreviewResult,
    EphemeralRuleSummary,
    EvaluateOutcome,
    RegisterError,
    RegisterResult,
    RuleSpec,
    RuleTools,
    ValidateResult,
)
from .tools.routing import ConsistencyWarning, EngineRoutingAdvisor, EngineRoutingHint
from .tools.write import WriteError, WriteResult, WriteTools
from .tools.write import RetractError, RetractRequest, RetractResult


class ReadReviewOrchestrator:
    """Read-first / review-first orchestration over Layer 1 and Layer 2 tools."""

    def __init__(
        self,
        *,
        session: AgentSession,
        draft_manager: DraftManager,
        kg_read_tools: KGReadTools,
        explain_tools: ExplainTools,
        evaluate_tools: EvaluateTools,
        candidate_cache: CandidatePayloadCache,
        checkpoint_store: AgentCheckpointStore,
        write_tools: WriteTools | None = None,
        rule_tools: RuleTools | None = None,
        document_staging: DocumentStaging | None = None,
        bundle_manager: BundleManager | None = None,
        extraction_agent: ExtractionAgent | None = None,
        default_extraction_config: ExtractionConfig | None = None,
        batch_extractor: BatchExtractor | None = None,
        entity_resolver: EntityResolver | None = None,
    ) -> None:
        if not isinstance(session, AgentSession):
            raise AgentContractError("session must be AgentSession")
        if not isinstance(draft_manager, DraftManager):
            raise AgentContractError("draft_manager must be DraftManager")
        if bundle_manager is not None and not isinstance(bundle_manager, BundleManager):
            raise AgentContractError("bundle_manager must be BundleManager when provided")
        self._session = session
        self._draft_manager = draft_manager
        self._kg_read_tools = kg_read_tools
        self._explain_tools = explain_tools
        self._evaluate_tools = evaluate_tools
        self._candidate_cache = candidate_cache
        self._checkpoint_store = checkpoint_store
        self._write_tools = write_tools
        self._rule_tools = rule_tools
        self._document_staging = document_staging
        self._bundle_manager = bundle_manager
        self._extraction_agent = extraction_agent
        self._default_extraction_config = default_extraction_config or ExtractionConfig()
        self._batch_extractor = batch_extractor
        self._entity_resolver = entity_resolver
        self._routing_advisor: EngineRoutingAdvisor | None = None

    @property
    def session(self) -> AgentSession:
        return self._session

    @property
    def runtime_session_id(self) -> str:
        runtime_session_id = self._session.runtime_session_id
        if not isinstance(runtime_session_id, str) or not runtime_session_id:
            raise AgentRuntimeError(
                "AgentSession is not bound to a runtime session",
                kind="runtime_session_missing",
            )
        return runtime_session_id

    def get_schema(self) -> dict[str, Any]:
        return self._kg_read_tools.get_schema_summary(self.runtime_session_id)

    def query_claims(
        self,
        pred_id: str | None = None,
        e_ref: str | None = None,
    ) -> list[ClaimResult]:
        return self._kg_read_tools.query_claims(
            self.runtime_session_id,
            pred_id=pred_id,
            e_ref=e_ref,
        )

    def get_entity(self, entity_type: str, identity: dict[str, object]) -> EntitySnapshot:
        return self._kg_read_tools.get_entity_snapshot(
            self.runtime_session_id,
            entity_type=entity_type,
            identity=identity,
        )

    def list_candidates(self, pred_id: str | None = None) -> list[CandidateSummary]:
        return self._kg_read_tools.list_candidates(self.runtime_session_id, pred_id=pred_id)

    def list_rules(self, include_spec: bool = False) -> list[RuleSummary]:
        return self._kg_read_tools.list_rules(self.runtime_session_id, include_spec=include_spec)

    def explain_summary(self, candidate_id: str) -> ExplainSummary:
        return self._explain_tools.get_summary(self.runtime_session_id, candidate_id)

    def explain_steps(self, candidate_id: str) -> list[ExplainStep]:
        return self._explain_tools.get_steps(self.runtime_session_id, candidate_id)

    def explain_tree(self, candidate_id: str) -> EvidenceTreeResult | None:
        return self._explain_tools.get_tree(self.runtime_session_id, candidate_id)

    def explain_timeline(self, candidate_id: str) -> TimelineResult | None:
        return self._explain_tools.get_timeline(self.runtime_session_id, candidate_id)

    def evaluate(self, request: EvaluateRequest) -> EvaluateResult:
        result = self._evaluate_tools.evaluate(request)
        self._session.touch()
        self._checkpoint()
        return result

    def review_candidate(
        self,
        candidate_id: str,
        *,
        include_steps: bool = True,
    ) -> CandidateReviewItem | CacheRecoveryOutcome:
        return self._evaluate_tools.review_candidate(
            candidate_id,
            include_steps=include_steps,
            include_summary=True,
        )

    def review_all(self) -> list[CandidateReviewItem | CacheRecoveryOutcome]:
        return self._evaluate_tools.review_all(include_steps=False, include_summary=True)

    def accept(
        self,
        candidate_id: str,
        *,
        dry_run: bool = False,
    ) -> AcceptResult | CacheRecoveryOutcome:
        result = self._evaluate_tools.accept_candidate(candidate_id, dry_run=dry_run)
        if isinstance(result, AcceptResult):
            self._session.touch()
            self._checkpoint()
        return result

    def accept_many(
        self,
        candidate_ids: list[str],
        *,
        dry_run: bool = False,
    ) -> list[AcceptResult | CacheRecoveryOutcome]:
        results = self._evaluate_tools.accept_many(candidate_ids, dry_run=dry_run)
        if any(isinstance(item, AcceptResult) for item in results):
            self._session.touch()
            self._checkpoint()
        return results

    def check_session_health(self) -> Literal["healthy", "runtime_lost"]:
        try:
            response = self._evaluate_tools.runtime_api.get_session(self.runtime_session_id)
        except AgentRuntimeError:
            return "runtime_lost"
        return "healthy" if response.get("ok") is True else "runtime_lost"

    def get_stale_candidates(self) -> list[dict[str, Any]]:
        return self._candidate_cache.list_stale(
            self._session.agent_session_id,
            self.runtime_session_id,
        )

    def stage_document(
        self,
        *,
        doc_name: str,
        content: bytes,
        doc_type: str | None = None,
    ) -> StagingResult | StagingError:
        return self._require_document_staging().stage_document(
            doc_name=doc_name,
            content=content,
            doc_type=doc_type,
        )

    def list_supported_document_formats(self) -> list[str]:
        return self._require_document_staging().list_supported_formats()

    def extract_from_segment(
        self,
        *,
        segment: DocumentSegment,
        config: ExtractionConfig | None = None,
    ) -> ExtractionResult | ExtractionError:
        if not isinstance(segment, DocumentSegment):
            raise AgentContractError("segment must be DocumentSegment")
        if self._session.scope is None:
            return ExtractionError(
                segment_id=segment.segment_id,
                error_kind="config_invalid",
                error_message="AgentSession.scope must be set for extraction",
            )
        if self._extraction_agent is None:
            return ExtractionError(
                segment_id=segment.segment_id,
                error_kind="dependency_missing",
                error_message="extraction_agent is not configured",
            )
        schema_ir = self._resolve_extraction_schema_ir()
        if schema_ir is None:
            return ExtractionError(
                segment_id=segment.segment_id,
                error_kind="config_invalid",
                error_message="no schema_ir available for extraction",
            )
        return self._extraction_agent.extract_from_segment(
            segment=segment,
            schema_ir=schema_ir,
            scope=self._session.scope,
            config=config or self._default_extraction_config,
        )

    def extract_and_create_bundle(
        self,
        *,
        segment: DocumentSegment,
        source_document_name: str,
        config: ExtractionConfig | None = None,
    ) -> tuple[ExtractionResult | ExtractionError, DraftBundle | None]:
        result = self.extract_from_segment(segment=segment, config=config)
        if isinstance(result, ExtractionError):
            return result, None
        if not result.valid_specs:
            return result, None
        bundle = self.create_document_bundle(
            source_document_id=segment.doc_id,
            source_document_name=source_document_name,
            facts=result.valid_specs,
        )
        return result, bundle

    def extract_from_segments(
        self,
        *,
        segments: list[DocumentSegment],
        batch_config: BatchExtractionConfig | None = None,
    ) -> BatchExtractionResult | BatchExtractionError:
        if self._session.scope is None:
            return BatchExtractionError(
                doc_id=_doc_id_or_none(segments),
                error_kind="config_invalid",
                error_message="AgentSession.scope must be set for extraction",
            )
        schema_ir = self._resolve_extraction_schema_ir()
        if schema_ir is None:
            return BatchExtractionError(
                doc_id=_doc_id_or_none(segments),
                error_kind="config_invalid",
                error_message="no schema_ir available for extraction",
            )
        return self._require_batch_extractor().extract_batch(
            segments=segments,
            schema_ir=schema_ir,
            scope=self._session.scope,
            batch_config=batch_config,
        )

    def extract_and_create_document_bundle(
        self,
        *,
        segments: list[DocumentSegment],
        source_document_name: str,
        batch_config: BatchExtractionConfig | None = None,
    ) -> tuple[BatchExtractionResult | BatchExtractionError, DraftBundle | None]:
        result = self.extract_from_segments(
            segments=segments,
            batch_config=batch_config,
        )
        if isinstance(result, BatchExtractionError):
            return result, None
        if not result.aggregated_specs:
            return result, None
        bundle = self.create_document_bundle(
            source_document_id=result.doc_id,
            source_document_name=source_document_name,
            facts=list(result.aggregated_specs),
        )
        return result, bundle

    def resolve_batch_extraction(
        self,
        batch_result: BatchExtractionResult,
        *,
        config: ResolutionConfig | None = None,
    ) -> ResolutionResult | ResolutionError:
        if not isinstance(batch_result, BatchExtractionResult):
            raise AgentContractError("batch_result must be BatchExtractionResult")
        if not batch_result.aggregated_specs:
            return ResolutionError(
                doc_id=batch_result.doc_id,
                error_kind="empty_specs",
                error_message="batch_result.aggregated_specs must be non-empty",
            )
        return self._require_entity_resolver().resolve_batch(
            list(batch_result.aggregated_specs),
            config=config,
        )

    def extract_resolve_and_create_document_bundle(
        self,
        *,
        segments: list[DocumentSegment],
        source_document_name: str,
        batch_config: BatchExtractionConfig | None = None,
        resolution_config: ResolutionConfig | None = None,
    ) -> tuple[
        BatchExtractionResult | BatchExtractionError,
        ResolutionResult | ResolutionError | None,
        DraftBundle | None,
    ]:
        batch_result = self.extract_from_segments(
            segments=segments,
            batch_config=batch_config,
        )
        if isinstance(batch_result, BatchExtractionError):
            return batch_result, None, None
        if not batch_result.aggregated_specs:
            return batch_result, None, None
        resolution = self.resolve_batch_extraction(
            batch_result,
            config=resolution_config,
        )
        if isinstance(resolution, ResolutionError):
            return batch_result, resolution, None
        bundle = self.create_document_bundle(
            source_document_id=resolution.doc_id,
            source_document_name=source_document_name,
            facts=list(resolution.resolved_specs),
        )
        return batch_result, resolution, bundle

    def create_document_bundle(
        self,
        *,
        source_document_id: str,
        source_document_name: str,
        facts: list[FactDraftSpec],
    ) -> DraftBundle:
        bundle_manager = self._require_bundle_manager()
        if not isinstance(facts, list):
            raise AgentContractError("facts must be list")
        for spec in facts:
            if not isinstance(spec, FactDraftSpec):
                raise AgentContractError("facts entries must be FactDraftSpec")
            if self._session.scope is not None:
                source, source_loc = _provenance_to_draft_source(
                    spec.extraction_provenance,
                    source_document_name,
                )
                AgentScopeGuard().validate(
                    FactDraft.from_checkpoint(
                        {
                            "draft_id": "draft_scope_preview",
                            "entity_type": spec.entity_type,
                            "entity_identity": spec.entity_identity,
                            "pred_id": spec.pred_id,
                            "field_values": spec.field_values,
                            "confidence": spec.confidence,
                            "source": source,
                            "source_loc": source_loc,
                            "note": spec.note,
                            "created_at": self._session.created_at,
                            "status": "pending",
                            "session_id": self._session.agent_session_id,
                            "conversation_turn": spec.conversation_turn,
                            "extraction_provenance": spec.extraction_provenance.to_checkpoint(),
                            "assertion_id": None,
                        }
                    ),
                    self._session.scope,
                )
        bundle = bundle_manager.create_bundle(
            session_id=self._session.agent_session_id,
            source_document_id=source_document_id,
            source_document_name=source_document_name,
            facts=facts,
            created_by=self._agent_id(),
        )
        self._session.touch()
        self._checkpoint()
        return bundle

    def list_document_bundles(
        self,
        *,
        status: str | None = None,
    ) -> list[DraftBundle]:
        return self._require_bundle_manager().list_bundles(status=status)

    def open_bundle_review(self, bundle_id: str) -> DraftBundle:
        bundle = self._require_bundle_manager().open_review(bundle_id)
        self._session.touch()
        self._checkpoint()
        return bundle

    def apply_bundle_review(
        self,
        bundle_id: str,
        actions: list[BundleReviewAction],
    ) -> DraftBundle:
        bundle = self._require_bundle_manager().apply_review(bundle_id, actions)
        self._session.touch()
        self._checkpoint()
        return bundle

    def commit_bundle(
        self,
        bundle_id: str,
        *,
        kind: Literal["set", "add"] = "set",
        confirmed_by: str | None = None,
    ) -> BundleCommitResult:
        bundle = self._require_bundle_manager().get_bundle(bundle_id)
        if bundle is None:
            raise AgentContractError(f"bundle not found: {bundle_id}")
        if bundle.status != "approved":
            raise AgentContractError("bundle must be approved before commit")
        if not bundle.approved_draft_ids:
            raise AgentContractError("bundle has no approved drafts")

        bundle.status = "committing"
        if confirmed_by is not None:
            bundle.confirmed_by = confirmed_by
        if bundle.confirmed_by is not None and bundle.confirmed_at is None:
            bundle.confirmed_at = time_ns()

        per_item_results = self.confirm_and_commit_many(
            draft_ids=list(bundle.approved_draft_ids),
            kind=kind,
            bundle_id=bundle.bundle_id,
            confirmed_by=confirmed_by or bundle.confirmed_by,
        )
        committed_count = sum(
            1 for item in per_item_results if isinstance(item, WriteResult)
        )
        failed_count = len(per_item_results) - committed_count
        rejected_count = sum(
            1
            for draft_id in bundle.draft_ids
            if (
                (draft := self._draft_manager.get_draft(draft_id)) is not None
                and draft.status == "rejected"
            )
        )
        bundle.status = "committed"
        bundle.committed_at = time_ns()
        self._session.touch()
        self._checkpoint()
        return BundleCommitResult(
            bundle_id=bundle.bundle_id,
            total=len(bundle.approved_draft_ids),
            committed_count=committed_count,
            rejected_count=rejected_count,
            failed_count=failed_count,
            per_item_results=per_item_results,
            committed_at=bundle.committed_at,
        )

    def abandon_bundle(
        self,
        bundle_id: str,
        *,
        reason: str | None = None,
    ) -> DraftBundle:
        bundle = self._require_bundle_manager().abandon_bundle(bundle_id, reason=reason)
        self._session.touch()
        self._checkpoint()
        return bundle

    def prepare_draft(
        self,
        *,
        entity_type: str,
        entity_identity: dict[str, Any],
        pred_id: str,
        field_values: list[tuple[str, Any]],
        confidence: float | None = None,
        source: str | None = None,
        source_loc: str | None = None,
        note: str | None = None,
        conversation_turn: int = 0,
    ) -> FactDraft:
        temp_draft = FactDraft.from_checkpoint(
            {
                "draft_id": "draft_scope_preview",
                "entity_type": entity_type,
                "entity_identity": entity_identity,
                "pred_id": pred_id,
                "field_values": field_values,
                "confidence": confidence,
                "source": source,
                "source_loc": source_loc,
                "note": note,
                "created_at": self._session.created_at,
                "status": "pending",
                "session_id": self._session.agent_session_id,
                "conversation_turn": conversation_turn,
                "assertion_id": None,
            }
        )
        if self._session.scope is not None:
            AgentScopeGuard().validate(temp_draft, self._session.scope)
        draft = self._draft_manager.create_draft(
            self._session.agent_session_id,
            entity_type=entity_type,
            entity_identity=entity_identity,
            pred_id=pred_id,
            field_values=field_values,
            confidence=confidence,
            source=source,
            source_loc=source_loc,
            note=note,
            conversation_turn=conversation_turn,
        )
        self._session.touch()
        return draft

    def confirm_and_commit(
        self,
        draft_id: str,
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> WriteResult | WriteError:
        try:
            result = self._confirm_and_commit_no_checkpoint(
                draft_id,
                kind=kind,
                bundle_id=bundle_id,
                confirmed_by=confirmed_by,
            )
        except AgentScopeViolation:
            self._session.touch()
            self._checkpoint()
            raise
        self._session.touch()
        self._checkpoint()
        return result

    def confirm_and_commit_many(
        self,
        draft_ids: list[str],
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> list[WriteResult | WriteError]:
        if not isinstance(draft_ids, list):
            raise AgentContractError("draft_ids must be list")
        results: list[WriteResult | WriteError] = []
        for draft_id in draft_ids:
            try:
                results.append(
                    self._confirm_and_commit_no_checkpoint(
                        draft_id,
                        kind=kind,
                        bundle_id=bundle_id,
                        confirmed_by=confirmed_by,
                    )
                )
            except AgentScopeViolation as exc:
                results.append(
                    WriteError(
                        draft_id=str(draft_id),
                        kind=kind,
                        error_kind="scope_violation",
                        error_path="$.draft_id",
                        error_message=str(exc),
                    )
                )
            except AgentContractError as exc:
                results.append(
                    WriteError(
                        draft_id=str(draft_id),
                        kind=kind,
                        error_kind="contract",
                        error_path="$.draft_id",
                        error_message=str(exc),
                    )
                )
        self._session.touch()
        self._checkpoint()
        return results

    def list_committed_drafts(self) -> list[FactDraft]:
        return self._draft_manager.list_drafts(
            self._session.agent_session_id,
            status="committed",
        )

    def preview_retract(self, asrt_id: str) -> ClaimResult | None:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise AgentContractError("asrt_id must be non-empty string")
        claims = self._kg_read_tools.query_claims(self.runtime_session_id, pred_id=None, e_ref=None)
        for claim in claims:
            if claim.asrt_id == asrt_id:
                return claim
        return None

    def confirm_and_retract(
        self,
        asrt_id: str,
        *,
        note: str | None = None,
        confirmed_by: str | None = None,
        trace_id: str | None = None,
    ) -> RetractResult | RetractError:
        preview = self.preview_retract(asrt_id)
        if preview is None:
            return RetractError(
                asrt_id=asrt_id,
                error_kind="not_found",
                error_message=f"assertion not found: {asrt_id}",
            )
        result = self._require_write_tools().retract(
            RetractRequest(
                asrt_id=asrt_id,
                note=note,
                confirmed_by=confirmed_by,
                trace_id=trace_id,
            )
        )
        self._session.touch()
        self._checkpoint()
        return result

    def validate_rule(self, spec: RuleSpec) -> ValidateResult:
        return self._require_rule_tools().validate(spec)

    def preview_rule(self, spec: RuleSpec) -> CompilePreviewResult:
        return self._require_rule_tools().compile_preview(spec)

    def register_and_evaluate_rule(
        self,
        spec: RuleSpec,
        *,
        evaluate_target_pred_id: str | None = None,
        evaluate_limit: int | None = None,
    ) -> tuple[RegisterResult | RegisterError, EvaluateOutcome]:
        validation = self._require_rule_tools().validate(spec)
        if not validation.valid:
            return (
                RegisterError(
                    rule_id=spec.rule_id,
                    error_kind=(
                        str(validation.errors[0].get("kind", "rule_invalid"))
                        if validation.errors
                        else "rule_invalid"
                    ),
                    error_message=_first_error_message(
                        validation.errors,
                        "rule validation failed",
                    ),
                ),
                EvaluateOutcome(status="skipped"),
            )

        register_result = self._require_rule_tools().register_ephemeral(spec)
        if isinstance(register_result, RegisterError):
            return register_result, EvaluateOutcome(status="skipped")

        if evaluate_target_pred_id is None:
            outcome = EvaluateOutcome(status="not_requested")
        else:
            request = EvaluateRequest(
                derivation={
                    "derivation_id": f"agent_rule_eval_{spec.rule_id}",
                    "version": spec.version,
                    "target": evaluate_target_pred_id,
                    "head_vars": list(spec.select_vars),
                    "where": [["ruleref", spec.rule_id, spec.version, list(spec.select_vars)]],
                    "mode": "native",
                },
                limit=evaluate_limit,
            )
            try:
                evaluate_result = self._evaluate_tools.evaluate(request)
            except AgentRuntimeError as exc:
                outcome = EvaluateOutcome(status="error", error_message=str(exc))
            else:
                outcome = EvaluateOutcome(status="ok", result=evaluate_result)

        self._session.touch()
        self._checkpoint()
        return register_result, outcome

    def list_ephemeral_rules(self) -> list[EphemeralRuleSummary]:
        return self._require_rule_tools().list_ephemeral()

    def clear_ephemeral_rules(self) -> int:
        cleared = self._require_rule_tools().clear_ephemeral()
        self._session.touch()
        self._checkpoint()
        return cleared

    def recommend_engine_for_rule(self, spec: RuleSpec) -> EngineRoutingHint:
        return self._require_routing_advisor().recommend_for_rule(spec)

    def recommend_engine_for_evaluate(
        self,
        derivation: dict[str, Any],
    ) -> EngineRoutingHint:
        return self._require_routing_advisor().recommend_for_evaluate(derivation)

    def check_engine_consistency(
        self,
        pred_id: str,
        suggested_engine: str,
    ) -> ConsistencyWarning | None:
        return self._require_routing_advisor().check_consistency(pred_id, suggested_engine)

    def register_and_evaluate_rule_with_routing(
        self,
        spec: RuleSpec,
        *,
        evaluate_target_pred_id: str | None = None,
        evaluate_limit: int | None = None,
        override_engine: str | None = None,
    ) -> tuple[RegisterResult | RegisterError | None, EvaluateOutcome, EngineRoutingHint]:
        hint = self.recommend_engine_for_rule(spec)
        actual_engine = hint.suggested_engine or "native"
        if override_engine is not None:
            normalized_override = _normalize_engine_name(override_engine)
            if normalized_override is None:
                raise AgentContractError("override_engine must be one of native|souffle|problog|pyreason")
            actual_engine = normalized_override
            hint = EngineRoutingHint(
                suggested_engine=normalized_override,
                reason=_combine_reason(hint.reason, f"override applied: {normalized_override}"),
                source="explicit",
                overrideable=hint.overrideable,
                confidence=1.0,
            )

        if evaluate_target_pred_id is not None:
            warning = self.check_engine_consistency(evaluate_target_pred_id, actual_engine)
            if warning is not None:
                hint = EngineRoutingHint(
                    suggested_engine=hint.suggested_engine,
                    reason=_combine_reason(hint.reason, f"consistency warning: {warning.message}"),
                    source=hint.source,
                    overrideable=hint.overrideable,
                    confidence=hint.confidence,
                )

        if actual_engine != "native":
            return (
                None,
                EvaluateOutcome(
                    status="skipped",
                    error_message=(
                        f"non-native engine '{actual_engine}' selected; register rule to FS "
                        "registry via authoring pipeline, then evaluate with target engine"
                    ),
                ),
                hint,
            )

        register_result, outcome = self.register_and_evaluate_rule(
            spec,
            evaluate_target_pred_id=evaluate_target_pred_id,
            evaluate_limit=evaluate_limit,
        )
        return register_result, outcome, hint

    def _checkpoint(self) -> None:
        self._checkpoint_store.save(
            self._session,
            self._draft_manager,
            self._bundle_manager,
        )

    def _resolve_extraction_schema_ir(self) -> dict[str, Any] | None:
        bootstrap = self._session.bootstrap_spec
        if bootstrap is not None:
            schema_ir = bootstrap.open_dto.get("schema_ir")
            if isinstance(schema_ir, dict):
                return schema_ir
        try:
            response = require_ok(self._evaluate_tools.runtime_api.get_schema(self.runtime_session_id))
        except AgentRuntimeError:
            return None
        result = response.get("result", {})
        if not isinstance(result, dict):
            return None
        schema_ir = result.get("schema_ir")
        return schema_ir if isinstance(schema_ir, dict) else None

    def _confirm_and_commit_no_checkpoint(
        self,
        draft_id: str,
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> WriteResult | WriteError:
        draft = self._draft_manager.get_draft(draft_id)
        if draft is None:
            raise AgentContractError(f"draft not found: {draft_id}")
        if draft.status != "pending":
            raise AgentContractError("only pending drafts may be committed")
        if self._session.scope is not None:
            try:
                AgentScopeGuard().validate(draft, self._session.scope)
            except AgentScopeViolation:
                self._draft_manager.reject_draft(draft_id)
                raise
        confirmed = self._draft_manager.confirm_draft(draft_id)
        result = self._require_write_tools().commit_draft(
            confirmed,
            kind=kind,
            bundle_id=bundle_id,
            confirmed_by=confirmed_by,
        )
        if isinstance(result, WriteResult):
            self._draft_manager.mark_committed(draft_id, result.assertion_id)
            return result
        self._draft_manager.reject_draft(draft_id)
        return result

    def _require_write_tools(self) -> WriteTools:
        if self._write_tools is None:
            raise AgentContractError("write_tools are not configured on this orchestrator")
        return self._write_tools

    def _require_rule_tools(self) -> RuleTools:
        if self._rule_tools is None:
            raise AgentContractError("rule_tools are not configured on this orchestrator")
        return self._rule_tools

    def _require_routing_advisor(self) -> EngineRoutingAdvisor:
        if self._routing_advisor is None:
            self._routing_advisor = EngineRoutingAdvisor(
                runtime_api=self._evaluate_tools.runtime_api,
                session=self._session,
            )
        return self._routing_advisor

    def _require_document_staging(self) -> DocumentStaging:
        if self._document_staging is None:
            raise AgentContractError("document_staging is not configured on this orchestrator")
        return self._document_staging

    def _require_bundle_manager(self) -> BundleManager:
        if self._bundle_manager is None:
            raise AgentContractError("bundle_manager is not configured on this orchestrator")
        return self._bundle_manager

    def _require_batch_extractor(self) -> BatchExtractor:
        if self._batch_extractor is None:
            raise AgentContractError("batch_extractor is not configured on this orchestrator")
        return self._batch_extractor

    def _require_entity_resolver(self) -> EntityResolver:
        if self._entity_resolver is None:
            raise AgentContractError("entity_resolver is not configured on this orchestrator")
        return self._entity_resolver

    def _agent_id(self) -> str:
        if self._session.scope is not None:
            return self._session.scope.agent_id
        return "agent"


def _first_error_message(errors: list[dict[str, Any]], default_message: str) -> str:
    if errors:
        details = errors[0].get("details")
        if isinstance(details, dict) and isinstance(details.get("message"), str):
            return details["message"]
        message = errors[0].get("message")
        if isinstance(message, str) and message:
            return message
    return default_message


def _normalize_engine_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"native", "souffle", "problog", "pyreason"}:
        return normalized
    return None


def _combine_reason(base: str, extra: str) -> str:
    if not base:
        return extra
    return f"{base}; {extra}"


def _doc_id_or_none(segments: Any) -> str | None:
    if isinstance(segments, list) and segments and isinstance(segments[0], DocumentSegment):
        return segments[0].doc_id
    return None
