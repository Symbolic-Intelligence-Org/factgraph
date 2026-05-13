from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import AgentContractError, AgentRuntimeError
from ._runtime_api import RuntimeAPI, require_ok, resolve_runtime_api


@dataclass
class ExplainSummary:
    candidate_id: str
    kind: str
    summary: dict[str, Any]
    certainty_summary: dict[str, Any] | None = None


@dataclass
class ExplainStep:
    step_num: int
    step_kind: str
    description: str
    node_ref: str | None
    detail: dict[str, Any]


@dataclass
class EvidenceTreeResult:
    candidate_id: str
    tree: dict[str, Any]
    support_kind: str


@dataclass
class TimelineResult:
    candidate_id: str
    timeline: dict[str, Any]


class ExplainTools:
    """Raw-first adapter for candidate explain surfaces."""

    def __init__(
        self,
        runtime_api_base: str | None = None,
        *,
        runtime_api: RuntimeAPI | None = None,
    ) -> None:
        self._runtime = resolve_runtime_api(
            runtime_api_base=runtime_api_base,
            runtime_api=runtime_api,
        )

    def get_summary(self, session_id: str, candidate_id: str) -> ExplainSummary:
        resp = require_ok(
            self._runtime.explain_summary(
                session_id,
                {"kind": "candidate", "id": candidate_id},
            )
        )
        kind = _require_non_empty_str(resp.get("kind"), "kind")
        summary = resp.get("summary")
        if not isinstance(summary, dict):
            raise AgentContractError("runtime explain summary must be object")
        normalized_kind = (
            "timeline_summary"
            if kind == "candidate_provenance_timeline_summary"
            else "tree_summary"
        )
        certainty = resp.get("certainty_summary")
        if certainty is not None and not isinstance(certainty, dict):
            certainty = None
        return ExplainSummary(
            candidate_id=candidate_id,
            kind=normalized_kind,
            summary=summary,
            certainty_summary=certainty,
        )

    def get_steps(self, session_id: str, candidate_id: str) -> list[ExplainStep]:
        resp = require_ok(
            self._runtime.explain_steps(
                session_id,
                {"kind": "candidate", "id": candidate_id},
            )
        )
        raw_steps = resp.get("steps", [])
        if not isinstance(raw_steps, list):
            raise AgentContractError("runtime explain steps must be list")
        out: list[ExplainStep] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                raise AgentContractError("runtime explain step entries must be objects")
            detail = item.get("detail")
            if not isinstance(detail, dict):
                detail = {}
            out.append(
                ExplainStep(
                    step_num=int(item.get("step_num", 0)),
                    step_kind=_require_non_empty_str(item.get("step_kind"), "step_kind"),
                    description=_require_non_empty_str(item.get("description"), "description"),
                    node_ref=_optional_non_empty_str(item.get("node_ref"), "node_ref"),
                    detail=detail,
                )
            )
        return out

    def get_tree(self, session_id: str, candidate_id: str) -> EvidenceTreeResult | None:
        try:
            resp = require_ok(
                self._runtime.explain_tree(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
            )
        except AgentRuntimeError as exc:
            if exc.kind in {"runtime_explain_not_supported", "explain_not_supported"}:
                return None
            raise
        tree = resp.get("tree")
        if not isinstance(tree, dict):
            raise AgentContractError("runtime explain tree must be object")
        return EvidenceTreeResult(
            candidate_id=candidate_id,
            tree=tree,
            support_kind=_require_non_empty_str(tree.get("support_kind"), "support_kind"),
        )

    def get_timeline(self, session_id: str, candidate_id: str) -> TimelineResult | None:
        try:
            resp = require_ok(
                self._runtime.explain_timeline(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
            )
        except AgentRuntimeError as exc:
            if exc.kind in {"runtime_explain_not_supported", "explain_not_supported"}:
                return None
            if exc.kind == "query_explain_timeline":
                summary = self.get_summary(session_id, candidate_id)
                if summary.kind != "timeline_summary":
                    return None
            raise
        timeline = resp.get("timeline")
        if not isinstance(timeline, dict):
            raise AgentContractError("runtime explain timeline must be object")
        return TimelineResult(candidate_id=candidate_id, timeline=timeline)


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value


def _optional_non_empty_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string when provided")
    return value
