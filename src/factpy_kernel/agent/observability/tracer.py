from __future__ import annotations

from typing import Any, Protocol


class AgentTracer(Protocol):
    """Agent-layer observability sink."""

    def record_single_segment_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...

    def record_batch_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...

    def record_resolution(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...


class NoOpTracer:
    """Default tracer implementation that discards all events."""

    def record_single_segment_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        return None

    def record_batch_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        return None

    def record_resolution(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None:
        return None
