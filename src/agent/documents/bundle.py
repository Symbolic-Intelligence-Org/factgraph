from __future__ import annotations

from dataclasses import dataclass, field
from time import time_ns
from typing import Any, Literal
from uuid import uuid4

from ..draft import DraftManager, FactDraft
from ..errors import AgentContractError
from .models import ExtractionProvenance


@dataclass(frozen=True)
class FactDraftSpec:
    entity_type: str
    entity_identity: dict[str, Any]
    pred_id: str
    field_values: list[tuple[str, Any]]
    extraction_provenance: ExtractionProvenance
    confidence: float | None = None
    note: str | None = None
    conversation_turn: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.entity_type, str) or not self.entity_type:
            raise AgentContractError("entity_type must be non-empty string")
        if not isinstance(self.entity_identity, dict):
            raise AgentContractError("entity_identity must be object")
        if not isinstance(self.pred_id, str) or not self.pred_id:
            raise AgentContractError("pred_id must be non-empty string")
        if not isinstance(self.field_values, list):
            raise AgentContractError("field_values must be list")
        for item in self.field_values:
            if isinstance(item, tuple) and len(item) == 2:
                continue
            if isinstance(item, list) and len(item) == 2:
                continue
            raise AgentContractError("field_values entries must be pair")
        if not isinstance(self.extraction_provenance, ExtractionProvenance):
            raise AgentContractError("extraction_provenance must be ExtractionProvenance")
        if self.note is not None and (not isinstance(self.note, str) or not self.note):
            raise AgentContractError("note must be non-empty string when provided")
        if isinstance(self.confidence, bool):
            raise AgentContractError("confidence must be float when provided")
        if self.confidence is not None and not isinstance(self.confidence, (int, float)):
            raise AgentContractError("confidence must be float when provided")
        if self.confidence is not None and not (0.0 <= float(self.confidence) <= 1.0):
            raise AgentContractError("confidence must be in [0, 1]")

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_identity": dict(self.entity_identity),
            "pred_id": self.pred_id,
            "field_values": [list(item) for item in self.field_values],
            "extraction_provenance": self.extraction_provenance.to_checkpoint(),
            "confidence": self.confidence,
            "note": self.note,
            "conversation_turn": self.conversation_turn,
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "FactDraftSpec":
        if not isinstance(data, dict):
            raise AgentContractError("fact draft spec checkpoint must be object")
        field_values_raw = data.get("field_values", [])
        if not isinstance(field_values_raw, list):
            raise AgentContractError("field_values must be list")
        field_values: list[tuple[str, Any]] = []
        for item in field_values_raw:
            if isinstance(item, tuple) and len(item) == 2:
                field_values.append(item)
                continue
            if isinstance(item, list) and len(item) == 2:
                field_values.append((item[0], item[1]))
                continue
            raise AgentContractError("field_values entries must be pair")
        return cls(
            entity_type=_require_non_empty_str(data.get("entity_type"), "entity_type"),
            entity_identity=_require_dict(data.get("entity_identity"), "entity_identity"),
            pred_id=_require_non_empty_str(data.get("pred_id"), "pred_id"),
            field_values=field_values,
            extraction_provenance=ExtractionProvenance.from_checkpoint(
                _require_dict(data.get("extraction_provenance"), "extraction_provenance")
            ),
            confidence=_optional_float(data.get("confidence"), "confidence"),
            note=_optional_str(data.get("note"), "note"),
            conversation_turn=int(data.get("conversation_turn", 0)),
        )


@dataclass
class DraftBundle:
    bundle_id: str
    source_document_id: str
    source_document_name: str
    draft_ids: list[str]
    approved_draft_ids: list[str]
    created_at: int
    created_by: str
    status: Literal[
        "created",
        "under_review",
        "approved",
        "rejected",
        "abandoned",
        "committing",
        "committed",
    ] = "created"
    confirmed_by: str | None = None
    confirmed_at: int | None = None
    committed_at: int | None = None
    abandoned_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_id, str) or not self.bundle_id:
            raise AgentContractError("bundle_id must be non-empty string")
        if not isinstance(self.source_document_id, str) or not self.source_document_id:
            raise AgentContractError("source_document_id must be non-empty string")
        if not isinstance(self.source_document_name, str) or not self.source_document_name:
            raise AgentContractError("source_document_name must be non-empty string")
        if not isinstance(self.draft_ids, list) or not self.draft_ids:
            raise AgentContractError("draft_ids must be non-empty list")
        if not isinstance(self.approved_draft_ids, list):
            raise AgentContractError("approved_draft_ids must be list")
        if not set(self.approved_draft_ids).issubset(set(self.draft_ids)):
            raise AgentContractError("approved_draft_ids must be subset of draft_ids")
        if not isinstance(self.created_by, str) or not self.created_by:
            raise AgentContractError("created_by must be non-empty string")
        if self.status not in {
            "created",
            "under_review",
            "approved",
            "rejected",
            "abandoned",
            "committing",
            "committed",
        }:
            raise AgentContractError("invalid bundle status")
        if self.confirmed_by is not None and (
            not isinstance(self.confirmed_by, str) or not self.confirmed_by
        ):
            raise AgentContractError("confirmed_by must be non-empty string when provided")
        if self.abandoned_reason is not None and (
            not isinstance(self.abandoned_reason, str) or not self.abandoned_reason
        ):
            raise AgentContractError("abandoned_reason must be non-empty string when provided")

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "source_document_id": self.source_document_id,
            "source_document_name": self.source_document_name,
            "draft_ids": list(self.draft_ids),
            "approved_draft_ids": list(self.approved_draft_ids),
            "created_at": self.created_at,
            "created_by": self.created_by,
            "status": self.status,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
            "committed_at": self.committed_at,
            "abandoned_reason": self.abandoned_reason,
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "DraftBundle":
        if not isinstance(data, dict):
            raise AgentContractError("draft bundle checkpoint must be object")
        draft_ids = data.get("draft_ids", [])
        approved_draft_ids = data.get("approved_draft_ids", [])
        if not isinstance(draft_ids, list) or not isinstance(approved_draft_ids, list):
            raise AgentContractError("draft_ids and approved_draft_ids must be list")
        return cls(
            bundle_id=_require_non_empty_str(data.get("bundle_id"), "bundle_id"),
            source_document_id=_require_non_empty_str(
                data.get("source_document_id"), "source_document_id"
            ),
            source_document_name=_require_non_empty_str(
                data.get("source_document_name"), "source_document_name"
            ),
            draft_ids=[_require_non_empty_str(item, "draft_id") for item in draft_ids],
            approved_draft_ids=[
                _require_non_empty_str(item, "approved_draft_id") for item in approved_draft_ids
            ],
            created_at=int(data.get("created_at", time_ns())),
            created_by=_require_non_empty_str(data.get("created_by"), "created_by"),
            status=str(data.get("status", "created")),
            confirmed_by=_optional_str(data.get("confirmed_by"), "confirmed_by"),
            confirmed_at=_optional_int(data.get("confirmed_at"), "confirmed_at"),
            committed_at=_optional_int(data.get("committed_at"), "committed_at"),
            abandoned_reason=_optional_str(data.get("abandoned_reason"), "abandoned_reason"),
        )


@dataclass(frozen=True)
class BundleReviewAction:
    draft_id: str
    action: Literal["approve", "reject"]
    note: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.draft_id, str) or not self.draft_id:
            raise AgentContractError("draft_id must be non-empty string")
        if self.action not in {"approve", "reject"}:
            raise AgentContractError("action must be approve|reject")
        if self.note is not None and (not isinstance(self.note, str) or not self.note):
            raise AgentContractError("note must be non-empty string when provided")


@dataclass
class BundleCommitResult:
    bundle_id: str
    total: int
    committed_count: int
    rejected_count: int
    failed_count: int
    per_item_results: list[Any]
    committed_at: int


class BundleManager:
    """Agent-side document draft bundle lifecycle manager."""

    def __init__(self, *, draft_manager: DraftManager) -> None:
        if not isinstance(draft_manager, DraftManager):
            raise AgentContractError("draft_manager must be DraftManager")
        self._draft_manager = draft_manager
        self._bundles: dict[str, DraftBundle] = {}

    def create_bundle(
        self,
        *,
        session_id: str,
        source_document_id: str,
        source_document_name: str,
        facts: list[FactDraftSpec],
        created_by: str,
    ) -> DraftBundle:
        if not isinstance(facts, list) or not facts:
            raise AgentContractError("facts must be non-empty list")
        _require_non_empty_str(session_id, "session_id")
        _require_non_empty_str(source_document_id, "source_document_id")
        _require_non_empty_str(source_document_name, "source_document_name")
        _require_non_empty_str(created_by, "created_by")

        for spec in facts:
            if not isinstance(spec, FactDraftSpec):
                raise AgentContractError("facts entries must be FactDraftSpec")
            if spec.extraction_provenance.source_document_id != source_document_id:
                raise AgentContractError("fact provenance source_document_id must match bundle")

        draft_ids: list[str] = []
        for spec in facts:
            prov = spec.extraction_provenance
            source, source_loc = _provenance_to_draft_source(prov, source_document_name)
            draft = self._draft_manager.create_draft(
                session_id,
                entity_type=spec.entity_type,
                entity_identity=spec.entity_identity,
                pred_id=spec.pred_id,
                field_values=list(spec.field_values),
                confidence=spec.confidence,
                source=source,
                source_loc=source_loc,
                note=spec.note,
                conversation_turn=spec.conversation_turn,
                extraction_provenance=prov,
            )
            draft_ids.append(draft.draft_id)

        bundle = DraftBundle(
            bundle_id=f"bundle_{uuid4().hex[:12]}",
            source_document_id=source_document_id,
            source_document_name=source_document_name,
            draft_ids=draft_ids,
            approved_draft_ids=[],
            created_at=time_ns(),
            created_by=created_by,
            status="created",
        )
        self._bundles[bundle.bundle_id] = bundle
        return bundle

    def get_bundle(self, bundle_id: str) -> DraftBundle | None:
        return self._bundles.get(bundle_id)

    def list_bundles(self, *, status: str | None = None) -> list[DraftBundle]:
        bundles = list(self._bundles.values())
        if status is not None:
            bundles = [bundle for bundle in bundles if bundle.status == status]
        return sorted(bundles, key=lambda bundle: (bundle.created_at, bundle.bundle_id))

    def open_review(self, bundle_id: str) -> DraftBundle:
        bundle = self._require_bundle(bundle_id)
        if bundle.status == "under_review":
            return bundle
        if bundle.status != "created":
            raise AgentContractError("only created bundles may enter review")
        bundle.status = "under_review"
        return bundle

    def apply_review(self, bundle_id: str, actions: list[BundleReviewAction]) -> DraftBundle:
        bundle = self._require_bundle(bundle_id)
        if bundle.status not in {"created", "under_review"}:
            raise AgentContractError("bundle must be created|under_review")
        if not isinstance(actions, list):
            raise AgentContractError("actions must be list")
        applied = False
        for action in actions:
            if not isinstance(action, BundleReviewAction):
                raise AgentContractError("actions entries must be BundleReviewAction")
            if action.draft_id not in bundle.draft_ids:
                raise AgentContractError("draft_id is not part of bundle")
            draft = self._draft_manager.get_draft(action.draft_id)
            if draft is None:
                raise AgentContractError(f"draft not found: {action.draft_id}")
            if action.action == "approve":
                if draft.status != "pending":
                    raise AgentContractError("only pending drafts may be approved")
                if action.draft_id not in bundle.approved_draft_ids:
                    bundle.approved_draft_ids.append(action.draft_id)
                applied = True
                continue
            if draft.status in {"pending", "confirmed"}:
                self._draft_manager.reject_draft(action.draft_id)
            elif draft.status != "rejected":
                raise AgentContractError("only pending/confirmed drafts may be rejected")
            if action.draft_id in bundle.approved_draft_ids:
                bundle.approved_draft_ids = [
                    draft_id
                    for draft_id in bundle.approved_draft_ids
                    if draft_id != action.draft_id
                ]
            applied = True

        if not applied:
            return bundle
        if bundle.approved_draft_ids:
            bundle.status = "approved"
            return bundle
        draft_statuses = [
            self._draft_manager.get_draft(draft_id).status  # type: ignore[union-attr]
            for draft_id in bundle.draft_ids
        ]
        bundle.status = "rejected" if draft_statuses and all(status == "rejected" for status in draft_statuses) else "under_review"
        return bundle

    def abandon_bundle(self, bundle_id: str, *, reason: str | None = None) -> DraftBundle:
        bundle = self._require_bundle(bundle_id)
        for draft_id in bundle.draft_ids:
            draft = self._draft_manager.get_draft(draft_id)
            if draft is None:
                continue
            if draft.status in {"pending", "confirmed"}:
                self._draft_manager.reject_draft(draft_id)
        bundle.approved_draft_ids = []
        bundle.status = "abandoned"
        bundle.abandoned_reason = reason
        return bundle

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "bundles": [
                bundle.to_checkpoint()
                for bundle in sorted(self._bundles.values(), key=lambda item: item.bundle_id)
            ]
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any], *, draft_manager: DraftManager) -> "BundleManager":
        if not isinstance(data, dict):
            raise AgentContractError("bundle manager checkpoint must be object")
        bundles_raw = data.get("bundles", [])
        if not isinstance(bundles_raw, list):
            raise AgentContractError("bundle manager checkpoint bundles must be list")
        manager = cls(draft_manager=draft_manager)
        for item in bundles_raw:
            bundle = DraftBundle.from_checkpoint(item)
            manager._bundles[bundle.bundle_id] = bundle
        return manager

    def _require_bundle(self, bundle_id: str) -> DraftBundle:
        if not isinstance(bundle_id, str) or not bundle_id:
            raise AgentContractError("bundle_id must be non-empty string")
        bundle = self._bundles.get(bundle_id)
        if bundle is None:
            raise AgentContractError(f"bundle not found: {bundle_id}")
        return bundle


def _provenance_to_draft_source(
    provenance: ExtractionProvenance,
    doc_name: str,
) -> tuple[str, str]:
    if provenance.is_merged():
        source_segment_ids = provenance.source_segment_ids()
        merged_count = max(0, len(source_segment_ids) - 1)
        return (
            f"doc:{doc_name}:seg:{provenance.segment_id}:merged_from:{merged_count}",
            (
                f"chars:{provenance.char_offset_start}-{provenance.char_offset_end}"
                f":segments:{','.join(source_segment_ids)}"
            ),
        )
    return (
        f"doc:{doc_name}:seg:{provenance.segment_id}",
        f"chars:{provenance.char_offset_start}-{provenance.char_offset_end}",
    )


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)


def _optional_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string when provided")
    return value


def _optional_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentContractError(f"{name} must be float when provided")
    out = float(value)
    if not (0.0 <= out <= 1.0):
        raise AgentContractError(f"{name} must be in [0, 1]")
    return out


def _optional_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentContractError(f"{name} must be int when provided")
    return value
