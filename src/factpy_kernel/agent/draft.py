from __future__ import annotations

from dataclasses import asdict, dataclass
from time import time_ns
from typing import Any, Literal
from uuid import uuid4

from .documents.models import ExtractionProvenance
from .errors import AgentContractError


@dataclass
class FactDraft:
    draft_id: str
    entity_type: str
    entity_identity: dict[str, Any]
    pred_id: str
    field_values: list[tuple[str, Any]]
    confidence: float | None
    source: str | None
    source_loc: str | None
    note: str | None
    created_at: int
    status: Literal["pending", "confirmed", "committed", "rejected", "expired"]
    session_id: str
    conversation_turn: int
    extraction_provenance: ExtractionProvenance | None = None
    assertion_id: str | None = None

    def to_checkpoint(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "FactDraft":
        if not isinstance(data, dict):
            raise AgentContractError("fact draft checkpoint must be object")
        draft_id = data.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id:
            raise AgentContractError("draft_id must be non-empty string")
        status = data.get("status")
        if status not in {"pending", "confirmed", "committed", "rejected", "expired"}:
            raise AgentContractError("invalid draft status")
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
            draft_id=draft_id,
            entity_type=_require_non_empty_str(data.get("entity_type"), "entity_type"),
            entity_identity=_require_dict(data.get("entity_identity"), "entity_identity"),
            pred_id=_require_non_empty_str(data.get("pred_id"), "pred_id"),
            field_values=field_values,
            confidence=_optional_float(data.get("confidence"), "confidence"),
            source=_optional_str(data.get("source"), "source"),
            source_loc=_optional_str(data.get("source_loc"), "source_loc"),
            note=_optional_str(data.get("note"), "note"),
            created_at=int(data.get("created_at", time_ns())),
            status=status,
            session_id=_require_non_empty_str(data.get("session_id"), "session_id"),
            conversation_turn=int(data.get("conversation_turn", 0)),
            extraction_provenance=_optional_extraction_provenance(
                data.get("extraction_provenance"), "extraction_provenance"
            ),
            assertion_id=_optional_str(data.get("assertion_id"), "assertion_id"),
        )


class DraftManager:
    """In-memory draft lifecycle manager with checkpoint serialization."""

    def __init__(self) -> None:
        self._drafts: dict[str, FactDraft] = {}

    def create_draft(self, session_id: str, **kwargs: Any) -> FactDraft:
        draft = FactDraft(
            draft_id=f"draft_{uuid4().hex[:12]}",
            entity_type=_require_non_empty_str(kwargs.get("entity_type"), "entity_type"),
            entity_identity=_require_dict(kwargs.get("entity_identity"), "entity_identity"),
            pred_id=_require_non_empty_str(kwargs.get("pred_id"), "pred_id"),
            field_values=_normalize_field_values(kwargs.get("field_values", [])),
            confidence=_optional_float(kwargs.get("confidence"), "confidence"),
            source=_optional_str(kwargs.get("source"), "source"),
            source_loc=_optional_str(kwargs.get("source_loc"), "source_loc"),
            note=_optional_str(kwargs.get("note"), "note"),
            created_at=int(kwargs.get("created_at", time_ns())),
            status="pending",
            session_id=_require_non_empty_str(session_id, "session_id"),
            conversation_turn=int(kwargs.get("conversation_turn", 0)),
            extraction_provenance=_optional_extraction_provenance(
                kwargs.get("extraction_provenance"), "extraction_provenance"
            ),
        )
        self._drafts[draft.draft_id] = draft
        return draft

    def get_draft(self, draft_id: str) -> FactDraft | None:
        return self._drafts.get(draft_id)

    def list_drafts(self, session_id: str, status: str | None = None) -> list[FactDraft]:
        drafts = [d for d in self._drafts.values() if d.session_id == session_id]
        if status is not None:
            drafts = [d for d in drafts if d.status == status]
        return sorted(drafts, key=lambda d: (d.created_at, d.draft_id))

    def update_draft(self, draft_id: str, **fields: Any) -> FactDraft:
        draft = self._require_draft(draft_id)
        if draft.status != "pending":
            raise AgentContractError("only pending drafts may be updated")
        if "status" in fields:
            raise AgentContractError("status must be updated via dedicated transitions")
        updated = draft.to_checkpoint()
        for key, value in fields.items():
            if key not in updated:
                raise AgentContractError(f"unknown draft field: {key}")
            updated[key] = value
        next_draft = FactDraft.from_checkpoint(updated)
        self._drafts[draft_id] = next_draft
        return next_draft

    def confirm_draft(self, draft_id: str) -> FactDraft:
        draft = self._require_draft(draft_id)
        if draft.status != "pending":
            raise AgentContractError("only pending drafts may be confirmed")
        return self._replace_status(draft, "confirmed")

    def reject_draft(self, draft_id: str) -> FactDraft:
        draft = self._require_draft(draft_id)
        if draft.status not in {"pending", "confirmed"}:
            raise AgentContractError("only pending/confirmed drafts may be rejected")
        return self._replace_status(draft, "rejected")

    def mark_committed(self, draft_id: str, asrt_id: str) -> FactDraft:
        draft = self._require_draft(draft_id)
        if draft.status != "confirmed":
            raise AgentContractError("only confirmed drafts may be marked committed")
        next_draft = FactDraft.from_checkpoint(
            {
                **draft.to_checkpoint(),
                "status": "committed",
                "assertion_id": _require_non_empty_str(asrt_id, "assertion_id"),
            }
        )
        self._drafts[draft_id] = next_draft
        return next_draft

    def expire_drafts(self, session_id: str, max_age_ns: int) -> list[str]:
        if max_age_ns < 0:
            raise AgentContractError("max_age_ns must be non-negative")
        now = time_ns()
        expired: list[str] = []
        for draft in self.list_drafts(session_id, status="pending"):
            if now - draft.created_at >= max_age_ns:
                self._replace_status(draft, "expired")
                expired.append(draft.draft_id)
        return expired

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "drafts": [draft.to_checkpoint() for draft in sorted(self._drafts.values(), key=lambda d: d.draft_id)]
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "DraftManager":
        if not isinstance(data, dict):
            raise AgentContractError("draft manager checkpoint must be object")
        drafts_raw = data.get("drafts", [])
        if not isinstance(drafts_raw, list):
            raise AgentContractError("draft manager checkpoint drafts must be list")
        manager = cls()
        for item in drafts_raw:
            draft = FactDraft.from_checkpoint(item)
            manager._drafts[draft.draft_id] = draft
        return manager

    def _require_draft(self, draft_id: str) -> FactDraft:
        draft = self._drafts.get(draft_id)
        if draft is None:
            raise AgentContractError(f"draft not found: {draft_id}")
        return draft

    def _replace_status(self, draft: FactDraft, status: Literal["confirmed", "rejected", "expired"]) -> FactDraft:
        next_draft = FactDraft.from_checkpoint({**draft.to_checkpoint(), "status": status})
        self._drafts[draft.draft_id] = next_draft
        return next_draft


def _normalize_field_values(value: Any) -> list[tuple[str, Any]]:
    if not isinstance(value, list):
        raise AgentContractError("field_values must be list")
    out: list[tuple[str, Any]] = []
    for item in value:
        if isinstance(item, tuple) and len(item) == 2:
            out.append(item)
        elif isinstance(item, list) and len(item) == 2:
            out.append((item[0], item[1]))
        else:
            raise AgentContractError("field_values entries must be pair")
    return out


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value


def _optional_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AgentContractError(f"{name} must be string when provided")
    return value


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)


def _optional_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AgentContractError(f"{name} must be float when provided")
    if not isinstance(value, (int, float)):
        raise AgentContractError(f"{name} must be float when provided")
    out = float(value)
    if not (0.0 <= out <= 1.0):
        raise AgentContractError(f"{name} must be in [0, 1]")
    return out


def _optional_extraction_provenance(
    value: Any,
    name: str,
) -> ExtractionProvenance | None:
    if value is None:
        return None
    if isinstance(value, ExtractionProvenance):
        return value
    if isinstance(value, dict):
        return ExtractionProvenance.from_checkpoint(value)
    raise AgentContractError(f"{name} must be ExtractionProvenance when provided")
