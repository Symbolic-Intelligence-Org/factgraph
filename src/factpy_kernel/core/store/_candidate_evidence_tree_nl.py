from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CandidateEvidenceTreeNLExplainError(ValueError):
    pass


def render_candidate_evidence_tree_nl_explain(
    summary: dict[str, Any],
    narrative: dict[str, Any],
    *,
    locale: str = "en",
) -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        raise CandidateEvidenceTreeNLExplainError("summary must be object")
    if not isinstance(narrative, Mapping):
        raise CandidateEvidenceTreeNLExplainError("narrative must be object")
    if not isinstance(locale, str) or not locale:
        raise CandidateEvidenceTreeNLExplainError("locale must be non-empty string")

    candidate_id = _require_non_empty_str(summary.get("candidate_id"), path="summary.candidate_id")
    support_kind = _require_non_empty_str(summary.get("support_kind"), path="summary.support_kind")
    is_degraded = _require_bool(summary.get("is_degraded"), path="summary.is_degraded")
    root_result_kind = summary.get("root_result_kind")
    if root_result_kind is not None and (not isinstance(root_result_kind, str) or not root_result_kind):
        raise CandidateEvidenceTreeNLExplainError("summary.root_result_kind must be non-empty string or null")
    narrative_headline = _require_non_empty_str(narrative.get("headline"), path="narrative.headline")
    overview_lines = _require_string_list(narrative.get("overview_lines"), path="narrative.overview_lines")
    evidence_lines = _require_string_list(narrative.get("evidence_lines"), path="narrative.evidence_lines")
    rule_chain_lines = _require_string_list(narrative.get("rule_chain_lines"), path="narrative.rule_chain_lines")
    terminal_lines = _require_string_list(narrative.get("terminal_lines"), path="narrative.terminal_lines")
    drilldown_lines = _require_string_list(narrative.get("drilldown_lines"), path="narrative.drilldown_lines")
    certainty_lines: list[str] | None = None
    if narrative.get("certainty_lines") is not None:
        certainty_lines = _require_string_list(
            narrative.get("certainty_lines"),
            path="narrative.certainty_lines",
        )

    headline = (
        f"Candidate {candidate_id} has degraded support kind {support_kind}."
        if is_degraded
        else (
            f"Candidate {candidate_id} is explained by support kind {support_kind}"
            f" with root result kind {root_result_kind if root_result_kind is not None else '-'}."
        )
    )
    paragraphs = [
        f"{narrative_headline} {_join_sentences(overview_lines)}",
        f"Evidence summary: {_join_sentences(evidence_lines)}",
        f"Rule-chain summary: {_join_sentences(rule_chain_lines)}",
        f"Terminal and drill-down summary: {_join_sentences(terminal_lines + drilldown_lines)}",
    ]
    if certainty_lines:
        paragraphs.append(f"Certainty summary: {_join_sentences(certainty_lines)}")
    return {"headline": headline, "paragraphs": paragraphs}


def _join_sentences(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if isinstance(line, str) and line.strip())


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidateEvidenceTreeNLExplainError(f"{path} must be non-empty string")
    return value


def _require_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise CandidateEvidenceTreeNLExplainError(f"{path} must be bool")
    return value


def _require_string_list(value: Any, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise CandidateEvidenceTreeNLExplainError(f"{path} must be list[str]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise CandidateEvidenceTreeNLExplainError(f"{path} must be list[str]")
        out.append(item)
    return out


__all__ = [
    "CandidateEvidenceTreeNLExplainError",
    "render_candidate_evidence_tree_nl_explain",
]
