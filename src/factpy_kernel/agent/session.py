from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time_ns
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from factpy_kernel.core.schema.schema_ir import schema_digest

from .errors import AgentContractError, AgentScopeViolation

if TYPE_CHECKING:
    from .draft import FactDraft


@dataclass(frozen=True)
class RuntimeBootstrapSpec:
    """Cold-restart specification for reopening a runtime session."""

    schema_ir_digest: str
    open_dto: dict[str, Any]

    @classmethod
    def from_open_dto(cls, open_dto: dict[str, Any]) -> "RuntimeBootstrapSpec":
        if not isinstance(open_dto, dict):
            raise AgentContractError("open_dto must be object")
        schema_ir = open_dto.get("schema_ir")
        if isinstance(schema_ir, dict):
            digest = schema_digest(schema_ir)
        else:
            digest = ""
        return cls(schema_ir_digest=digest, open_dto=dict(open_dto))

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "schema_ir_digest": self.schema_ir_digest,
            "open_dto": dict(self.open_dto),
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "RuntimeBootstrapSpec":
        if not isinstance(data, dict):
            raise AgentContractError("bootstrap checkpoint must be object")
        digest = data.get("schema_ir_digest", "")
        open_dto = data.get("open_dto")
        if not isinstance(digest, str):
            raise AgentContractError("bootstrap.schema_ir_digest must be string")
        if not isinstance(open_dto, dict):
            raise AgentContractError("bootstrap.open_dto must be object")
        return cls(schema_ir_digest=digest, open_dto=dict(open_dto))


@dataclass(frozen=True)
class AgentScope:
    """Access-control constraints injected into an agent session."""

    allowed_entity_types: frozenset[str] | None = None
    allowed_pred_ids: frozenset[str] | None = None
    max_batch_size: int = 10
    require_source: bool = False
    min_confidence: float = 0.0
    agent_id: str = "agent"
    allow_document_ingest: bool = True
    allowed_engines: frozenset[str] | None = None
    allow_schema_draft: bool = False

    def __post_init__(self) -> None:
        if self.max_batch_size <= 0:
            raise AgentContractError("max_batch_size must be positive")
        if not (0.0 <= self.min_confidence <= 1.0):
            raise AgentContractError("min_confidence must be in [0, 1]")
        if not isinstance(self.agent_id, str) or not self.agent_id:
            raise AgentContractError("agent_id must be non-empty string")

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "allowed_entity_types": (
                sorted(self.allowed_entity_types) if self.allowed_entity_types is not None else None
            ),
            "allowed_pred_ids": (
                sorted(self.allowed_pred_ids) if self.allowed_pred_ids is not None else None
            ),
            "max_batch_size": self.max_batch_size,
            "require_source": self.require_source,
            "min_confidence": self.min_confidence,
            "agent_id": self.agent_id,
            "allow_document_ingest": self.allow_document_ingest,
            "allowed_engines": (
                sorted(self.allowed_engines) if self.allowed_engines is not None else None
            ),
            "allow_schema_draft": self.allow_schema_draft,
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "AgentScope":
        if not isinstance(data, dict):
            raise AgentContractError("scope checkpoint must be object")
        return cls(
            allowed_entity_types=_maybe_frozenset(data.get("allowed_entity_types")),
            allowed_pred_ids=_maybe_frozenset(data.get("allowed_pred_ids")),
            max_batch_size=int(data.get("max_batch_size", 10)),
            require_source=bool(data.get("require_source", False)),
            min_confidence=float(data.get("min_confidence", 0.0)),
            agent_id=str(data.get("agent_id", "agent")),
            allow_document_ingest=bool(data.get("allow_document_ingest", True)),
            allowed_engines=_maybe_frozenset(data.get("allowed_engines")),
            allow_schema_draft=bool(data.get("allow_schema_draft", False)),
        )


@dataclass
class AgentSession:
    """Agent-side session, loosely bound to a kernel runtime session."""

    agent_session_id: str = field(default_factory=lambda: f"agent_{uuid4().hex[:12]}")
    runtime_session_id: str | None = None
    bootstrap_spec: RuntimeBootstrapSpec | None = None
    scope: AgentScope | None = None
    status: Literal["created", "active", "closed"] = "created"
    created_at: int = field(default_factory=time_ns)
    last_active_at: int = field(default_factory=time_ns)
    burr_db_path: str | None = None

    def bind_runtime_session(
        self,
        runtime_session_id: str,
        *,
        bootstrap_spec: RuntimeBootstrapSpec,
        burr_db_path: str | None = None,
    ) -> None:
        if self.status == "closed":
            raise AgentContractError("cannot bind runtime session after close")
        if not isinstance(runtime_session_id, str) or not runtime_session_id:
            raise AgentContractError("runtime_session_id must be non-empty string")
        self.runtime_session_id = runtime_session_id
        self.bootstrap_spec = bootstrap_spec
        if burr_db_path is not None:
            self.burr_db_path = burr_db_path
        self.status = "active"
        self.touch()

    def close(self) -> None:
        self.status = "closed"
        self.touch()

    def touch(self) -> None:
        self.last_active_at = time_ns()

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "agent_session_id": self.agent_session_id,
            "runtime_session_id": self.runtime_session_id,
            "bootstrap_spec": (
                self.bootstrap_spec.to_checkpoint() if self.bootstrap_spec is not None else None
            ),
            "scope": self.scope.to_checkpoint() if self.scope is not None else None,
            "status": self.status,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "burr_db_path": self.burr_db_path,
        }

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "AgentSession":
        if not isinstance(data, dict):
            raise AgentContractError("agent session checkpoint must be object")
        session = cls(
            agent_session_id=_require_non_empty_str(
                data.get("agent_session_id"), path="agent_session_id"
            ),
            runtime_session_id=_optional_non_empty_str(
                data.get("runtime_session_id"), path="runtime_session_id"
            ),
            bootstrap_spec=(
                RuntimeBootstrapSpec.from_checkpoint(data["bootstrap_spec"])
                if isinstance(data.get("bootstrap_spec"), dict)
                else None
            ),
            scope=(
                AgentScope.from_checkpoint(data["scope"])
                if isinstance(data.get("scope"), dict)
                else None
            ),
            status=_require_status(data.get("status", "created")),
            created_at=int(data.get("created_at", time_ns())),
            last_active_at=int(data.get("last_active_at", time_ns())),
            burr_db_path=_optional_non_empty_str(data.get("burr_db_path"), path="burr_db_path"),
        )
        return session


class AgentScopeGuard:
    """Validates drafts against the current agent scope."""

    def validate(self, draft: "FactDraft", scope: AgentScope) -> None:
        if scope.allowed_entity_types is not None and draft.entity_type not in scope.allowed_entity_types:
            raise AgentScopeViolation(
                f"entity_type not allowed: {draft.entity_type}",
                details={"entity_type": draft.entity_type},
            )
        if scope.allowed_pred_ids is not None and draft.pred_id not in scope.allowed_pred_ids:
            raise AgentScopeViolation(
                f"pred_id not allowed: {draft.pred_id}",
                details={"pred_id": draft.pred_id},
            )
        if draft.confidence is not None and draft.confidence < scope.min_confidence:
            raise AgentScopeViolation(
                f"confidence below min_confidence: {draft.confidence}",
                details={
                    "confidence": draft.confidence,
                    "min_confidence": scope.min_confidence,
                },
            )
        if scope.require_source and not draft.source:
            raise AgentScopeViolation(
                "source is required by scope",
                details={"require_source": True},
            )


def _maybe_frozenset(value: Any) -> frozenset[str] | None:
    if value is None:
        return None
    if isinstance(value, frozenset):
        return value
    if not isinstance(value, (list, tuple, set)):
        raise AgentContractError("expected sequence for frozenset field")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise AgentContractError("frozenset field items must be non-empty strings")
        out.append(item)
    return frozenset(out)


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{path} must be non-empty string")
    return value


def _optional_non_empty_str(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{path} must be non-empty string when provided")
    return value


def _require_status(value: Any) -> Literal["created", "active", "closed"]:
    if value not in {"created", "active", "closed"}:
        raise AgentContractError("status must be created|active|closed")
    return value

