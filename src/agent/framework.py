from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any, Callable

from .errors import AgentContractError
from .orchestrator import ReadReviewOrchestrator
from .session import AgentSession
from .tools.explain import ExplainTools
from .tools.kg_read import KGReadTools

LAYER1_STATE_SEQUENCE = (
    "IDLE",
    "INTENT_IDENTIFIED",
    "SLOT_FILLING",
    "DRAFT_PREVIEW",
    "COMMITTING",
    "COMMITTED",
)


@dataclass(frozen=True)
class OptionalDependencyStatus:
    pydantic_ai_available: bool
    burr_available: bool
    langfuse_available: bool


@dataclass(frozen=True)
class AgentToolBinding:
    name: str
    handler: Callable[..., Any]
    description: str


@dataclass
class Layer1AgentSkeleton:
    session: AgentSession
    kg_read_tools: KGReadTools
    explain_tools: ExplainTools
    tool_registry: dict[str, AgentToolBinding]
    state_sequence: tuple[str, ...] = field(default_factory=lambda: LAYER1_STATE_SEQUENCE)
    dependency_status: OptionalDependencyStatus = field(default_factory=lambda: probe_optional_dependencies())
    tracing_enabled: bool = False


def probe_optional_dependencies() -> OptionalDependencyStatus:
    return OptionalDependencyStatus(
        pydantic_ai_available=find_spec("pydantic_ai") is not None,
        burr_available=find_spec("burr") is not None,
        langfuse_available=find_spec("langfuse") is not None,
    )


def build_tool_registry(
    *,
    kg_read_tools: KGReadTools,
    explain_tools: ExplainTools,
) -> dict[str, AgentToolBinding]:
    return {
        "get_schema_summary": AgentToolBinding(
            name="get_schema_summary",
            handler=kg_read_tools.get_schema_summary,
            description="Return a compact schema summary for agent prompt scaffolding.",
        ),
        "query_claims": AgentToolBinding(
            name="query_claims",
            handler=kg_read_tools.query_claims,
            description="Query runtime claims by predicate and optional entity ref.",
        ),
        "get_entity_snapshot": AgentToolBinding(
            name="get_entity_snapshot",
            handler=kg_read_tools.get_entity_snapshot,
            description="Reconstruct an entity-level snapshot from schema + claims.",
        ),
        "list_candidates": AgentToolBinding(
            name="list_candidates",
            handler=kg_read_tools.list_candidates,
            description="List candidate handles from the current runtime session.",
        ),
        "list_rules": AgentToolBinding(
            name="list_rules",
            handler=kg_read_tools.list_rules,
            description="List effective rule inventory for the current runtime session.",
        ),
        "get_summary": AgentToolBinding(
            name="get_summary",
            handler=explain_tools.get_summary,
            description="Fetch raw-first candidate explain summary.",
        ),
        "get_steps": AgentToolBinding(
            name="get_steps",
            handler=explain_tools.get_steps,
            description="Fetch explain steps for agent-first reasoning.",
        ),
        "get_tree": AgentToolBinding(
            name="get_tree",
            handler=explain_tools.get_tree,
            description="Fetch evidence tree when a branch-level drill-down is required.",
        ),
        "get_timeline": AgentToolBinding(
            name="get_timeline",
            handler=explain_tools.get_timeline,
            description="Fetch provenance timeline when the candidate is PyReason-backed.",
        ),
    }


def build_layer1_agent_skeleton(
    *,
    session: AgentSession,
    kg_read_tools: KGReadTools,
    explain_tools: ExplainTools,
    enable_tracing: bool = False,
) -> Layer1AgentSkeleton:
    if not isinstance(session, AgentSession):
        raise AgentContractError("session must be AgentSession")
    dependency_status = probe_optional_dependencies()
    tracing_enabled = enable_tracing and dependency_status.langfuse_available
    return Layer1AgentSkeleton(
        session=session,
        kg_read_tools=kg_read_tools,
        explain_tools=explain_tools,
        tool_registry=build_tool_registry(
            kg_read_tools=kg_read_tools,
            explain_tools=explain_tools,
        ),
        dependency_status=dependency_status,
        tracing_enabled=tracing_enabled,
    )


def build_layer2_tool_registry(
    *,
    orchestrator: ReadReviewOrchestrator,
) -> dict[str, AgentToolBinding]:
    if not isinstance(orchestrator, ReadReviewOrchestrator):
        raise AgentContractError("orchestrator must be ReadReviewOrchestrator")
    return {
        "get_schema_summary": AgentToolBinding(
            name="get_schema_summary",
            handler=orchestrator.get_schema,
            description="Return a compact schema summary for agent prompt scaffolding.",
        ),
        "query_claims": AgentToolBinding(
            name="query_claims",
            handler=orchestrator.query_claims,
            description="Query runtime claims by predicate and optional entity ref.",
        ),
        "get_entity_snapshot": AgentToolBinding(
            name="get_entity_snapshot",
            handler=orchestrator.get_entity,
            description="Reconstruct an entity-level snapshot from schema + claims.",
        ),
        "list_candidates": AgentToolBinding(
            name="list_candidates",
            handler=orchestrator.list_candidates,
            description="List candidate handles from the current runtime session.",
        ),
        "list_rules": AgentToolBinding(
            name="list_rules",
            handler=orchestrator.list_rules,
            description="List effective rule inventory for the current runtime session.",
        ),
        "get_summary": AgentToolBinding(
            name="get_summary",
            handler=orchestrator.explain_summary,
            description="Fetch raw-first candidate explain summary.",
        ),
        "get_steps": AgentToolBinding(
            name="get_steps",
            handler=orchestrator.explain_steps,
            description="Fetch explain steps for agent-first reasoning.",
        ),
        "get_tree": AgentToolBinding(
            name="get_tree",
            handler=orchestrator.explain_tree,
            description="Fetch evidence tree when a branch-level drill-down is required.",
        ),
        "get_timeline": AgentToolBinding(
            name="get_timeline",
            handler=orchestrator.explain_timeline,
            description="Fetch provenance timeline when the candidate is PyReason-backed.",
        ),
        "evaluate": AgentToolBinding(
            name="evaluate",
            handler=orchestrator.evaluate,
            description="Evaluate a structured derivation and cache the returned candidates.",
        ),
        "review_candidate": AgentToolBinding(
            name="review_candidate",
            handler=orchestrator.review_candidate,
            description="Review a single candidate from cache using summary and optional steps.",
        ),
        "review_all": AgentToolBinding(
            name="review_all",
            handler=orchestrator.review_all,
            description="Review all active cached candidates in the current runtime session.",
        ),
        "accept_candidate": AgentToolBinding(
            name="accept_candidate",
            handler=orchestrator.accept,
            description="Accept one active cached candidate, optionally in dry-run mode.",
        ),
        "accept_many": AgentToolBinding(
            name="accept_many",
            handler=orchestrator.accept_many,
            description="Accept multiple active cached candidates one by one.",
        ),
        "check_session_health": AgentToolBinding(
            name="check_session_health",
            handler=orchestrator.check_session_health,
            description="Probe whether the bound runtime session is still alive.",
        ),
        "get_stale_candidates": AgentToolBinding(
            name="get_stale_candidates",
            handler=orchestrator.get_stale_candidates,
            description="List stale cached candidates left behind by cold restart.",
        ),
    }


def build_layer3a_tool_registry(
    *,
    orchestrator: ReadReviewOrchestrator,
) -> dict[str, AgentToolBinding]:
    registry = build_layer2_tool_registry(orchestrator=orchestrator)
    registry.update(
        {
            "prepare_draft": AgentToolBinding(
                name="prepare_draft",
                handler=orchestrator.prepare_draft,
                description="Validate scope and create a pending structured fact draft.",
            ),
            "confirm_and_commit": AgentToolBinding(
                name="confirm_and_commit",
                handler=orchestrator.confirm_and_commit,
                description="Confirm one pending draft and write it to the runtime ledger.",
            ),
            "confirm_and_commit_many": AgentToolBinding(
                name="confirm_and_commit_many",
                handler=orchestrator.confirm_and_commit_many,
                description="Commit multiple pending drafts with best-effort batch semantics.",
            ),
            "list_committed_drafts": AgentToolBinding(
                name="list_committed_drafts",
                handler=orchestrator.list_committed_drafts,
                description="List committed drafts and their assertion ids for the current agent session.",
            ),
            "preview_retract": AgentToolBinding(
                name="preview_retract",
                handler=orchestrator.preview_retract,
                description="Preview one assertion before exact retract by scanning current session claims.",
            ),
            "confirm_and_retract": AgentToolBinding(
                name="confirm_and_retract",
                handler=orchestrator.confirm_and_retract,
                description="Retract one assertion after explicit confirmation and checkpoint the result.",
            ),
            "validate_rule": AgentToolBinding(
                name="validate_rule",
                handler=orchestrator.validate_rule,
                description="Validate a structured rule spec using rules_v1 preflight checks.",
            ),
            "preview_rule": AgentToolBinding(
                name="preview_rule",
                handler=orchestrator.preview_rule,
                description="Compile-preview a structured rule spec before runtime registration.",
            ),
            "register_and_evaluate_rule": AgentToolBinding(
                name="register_and_evaluate_rule",
                handler=orchestrator.register_and_evaluate_rule,
                description="Validate, register an ephemeral rule, and optionally evaluate it in native mode.",
            ),
            "list_ephemeral_rules": AgentToolBinding(
                name="list_ephemeral_rules",
                handler=orchestrator.list_ephemeral_rules,
                description="List session-scoped ephemeral rules currently registered in runtime.",
            ),
            "clear_ephemeral_rules": AgentToolBinding(
                name="clear_ephemeral_rules",
                handler=orchestrator.clear_ephemeral_rules,
                description="Clear all session-scoped ephemeral rules and checkpoint the agent session.",
            ),
            "recommend_engine_for_rule": AgentToolBinding(
                name="recommend_engine_for_rule",
                handler=orchestrator.recommend_engine_for_rule,
                description="Recommend a conservative engine for a rule spec without executing it.",
            ),
            "recommend_engine_for_evaluate": AgentToolBinding(
                name="recommend_engine_for_evaluate",
                handler=orchestrator.recommend_engine_for_evaluate,
                description="Recommend a conservative engine for a structured evaluate request.",
            ),
            "check_engine_consistency": AgentToolBinding(
                name="check_engine_consistency",
                handler=orchestrator.check_engine_consistency,
                description="Warn when the suggested engine diverges from historical candidate support kinds.",
            ),
            "register_and_evaluate_rule_with_routing": AgentToolBinding(
                name="register_and_evaluate_rule_with_routing",
                handler=orchestrator.register_and_evaluate_rule_with_routing,
                description="Recommend an engine, avoid non-native ephemeral pollution, and only execute native ephemeral flows.",
            ),
            "stage_document": AgentToolBinding(
                name="stage_document",
                handler=orchestrator.stage_document,
                description="Deterministically stage one document into auditable segments without ledger writes.",
            ),
            "list_supported_document_formats": AgentToolBinding(
                name="list_supported_document_formats",
                handler=orchestrator.list_supported_document_formats,
                description="List currently available document formats based on registered parsers and installed dependencies.",
            ),
            "create_document_bundle": AgentToolBinding(
                name="create_document_bundle",
                handler=orchestrator.create_document_bundle,
                description="Create a document-scoped draft bundle from fact draft specs with segment-level provenance.",
            ),
            "list_document_bundles": AgentToolBinding(
                name="list_document_bundles",
                handler=orchestrator.list_document_bundles,
                description="List document draft bundles for the current agent session.",
            ),
            "open_bundle_review": AgentToolBinding(
                name="open_bundle_review",
                handler=orchestrator.open_bundle_review,
                description="Move one draft bundle into review mode and checkpoint the state change.",
            ),
            "apply_bundle_review": AgentToolBinding(
                name="apply_bundle_review",
                handler=orchestrator.apply_bundle_review,
                description="Apply approve/reject actions to one document draft bundle with bundle-level review semantics.",
            ),
            "commit_bundle": AgentToolBinding(
                name="commit_bundle",
                handler=orchestrator.commit_bundle,
                description="Commit all approved drafts in one bundle through the existing Layer 3A best-effort write path.",
            ),
            "abandon_bundle": AgentToolBinding(
                name="abandon_bundle",
                handler=orchestrator.abandon_bundle,
                description="Reject pending drafts and mark one document bundle as abandoned.",
            ),
            "extract_from_segment": AgentToolBinding(
                name="extract_from_segment",
                handler=orchestrator.extract_from_segment,
                description="Run single-segment LLM extraction and return validated FactDraftSpec proposals.",
            ),
            "extract_and_create_bundle": AgentToolBinding(
                name="extract_and_create_bundle",
                handler=orchestrator.extract_and_create_bundle,
                description="Extract from one segment and, when specs survive validation, create a document bundle.",
            ),
            "extract_from_segments": AgentToolBinding(
                name="extract_from_segments",
                handler=orchestrator.extract_from_segments,
                description="Run sequential multi-segment extraction for one document and return mixed per-segment results.",
            ),
            "extract_and_create_document_bundle": AgentToolBinding(
                name="extract_and_create_document_bundle",
                handler=orchestrator.extract_and_create_document_bundle,
                description="Run batch extraction and create a document bundle from all surviving fact draft specs.",
            ),
            "resolve_batch_extraction": AgentToolBinding(
                name="resolve_batch_extraction",
                handler=orchestrator.resolve_batch_extraction,
                description="Resolve cross-segment duplicate fact specs into merged document facts with preserved provenance.",
            ),
            "extract_resolve_and_create_document_bundle": AgentToolBinding(
                name="extract_resolve_and_create_document_bundle",
                handler=orchestrator.extract_resolve_and_create_document_bundle,
                description="Run batch extraction, resolve duplicate facts, and create a document bundle from resolved specs.",
            ),
        }
    )
    return registry
