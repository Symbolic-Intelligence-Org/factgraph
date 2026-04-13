from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .tracer import AgentTracer, NoOpTracer


def _load_langfuse_module() -> Any:
    return import_module("langfuse")


@dataclass(frozen=True)
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str | None = None
    release: str | None = None


class LangfuseTracer:
    """Langfuse-backed tracer that never raises into business code."""

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str | None = None,
        release: str | None = None,
    ) -> None:
        self._client: Any | None = None
        try:
            module = _load_langfuse_module()
            client_cls = getattr(module, "Langfuse")
            self._client = client_cls(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                release=release,
            )
        except Exception:
            self._client = None

    def record_single_segment_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        self._safe_trace(
            name="agent.extraction.single_segment",
            attributes=attributes,
        )

    def record_batch_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        self._safe_trace(
            name="agent.extraction.batch",
            attributes=attributes,
        )

    def record_resolution(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        self._safe_trace(
            name="agent.extraction.resolution",
            attributes=attributes,
        )

    def _safe_trace(
        self,
        *,
        name: str,
        attributes: dict[str, Any],
    ) -> None:
        if self._client is None:
            return
        try:
            self._client.trace(name=name, metadata=attributes)
        except Exception:
            return


def build_tracer(
    *,
    langfuse_config: LangfuseConfig | None = None,
) -> AgentTracer:
    if langfuse_config is None:
        return NoOpTracer()
    try:
        _load_langfuse_module()
    except Exception:
        return NoOpTracer()
    return LangfuseTracer(
        public_key=langfuse_config.public_key,
        secret_key=langfuse_config.secret_key,
        host=langfuse_config.host,
        release=langfuse_config.release,
    )
