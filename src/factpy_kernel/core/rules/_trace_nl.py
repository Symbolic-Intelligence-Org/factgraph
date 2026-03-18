from __future__ import annotations

from typing import Any, Mapping


class RuleTraceNLExplainError(ValueError):
    pass


def render_rule_run_nl_explain(
    summary: dict[str, Any],
    narrative: dict[str, Any],
    *,
    locale: str = "en",
) -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        raise RuleTraceNLExplainError("summary must be object")
    if not isinstance(narrative, Mapping):
        raise RuleTraceNLExplainError("narrative must be object")
    if not isinstance(locale, str) or not locale:
        raise RuleTraceNLExplainError("locale must be non-empty string")

    root_rule = summary.get("root_rule")
    if not isinstance(root_rule, Mapping):
        raise RuleTraceNLExplainError("summary.root_rule must be object")
    rule_id = _require_non_empty_str(root_rule.get("rule_id"), path="summary.root_rule.rule_id")
    version = _require_non_empty_str(root_rule.get("version"), path="summary.root_rule.version")
    root_row_count = _require_non_negative_int(summary.get("root_row_count"), path="summary.root_row_count")
    invocation_count = _require_non_negative_int(summary.get("invocation_count"), path="summary.invocation_count")
    witness_assertion_ids = _require_string_list(
        summary.get("witness_assertion_ids"),
        path="summary.witness_assertion_ids",
    )
    predicate_witness_groups = _require_group_count_list(
        summary.get("predicate_witness_groups"),
        path="summary.predicate_witness_groups",
        key="pred_id",
    )
    non_fact_step_groups = _require_group_count_list(
        summary.get("non_fact_step_groups"),
        path="summary.non_fact_step_groups",
        key="kind",
    )

    narrative_headline = _require_non_empty_str(narrative.get("headline"), path="narrative.headline")
    overview_lines = _require_string_list(narrative.get("overview_lines"), path="narrative.overview_lines")
    predicate_lines = _require_string_list(narrative.get("predicate_lines"), path="narrative.predicate_lines")
    non_fact_check_lines = _require_string_list(
        narrative.get("non_fact_check_lines"),
        path="narrative.non_fact_check_lines",
    )
    drilldown_lines = _require_string_list(narrative.get("drilldown_lines"), path="narrative.drilldown_lines")

    headline = f"Rule {rule_id}@{version} matched {root_row_count} root row(s) across {invocation_count} invocation(s)."
    paragraphs = [
        (
            f"{narrative_headline} "
            f"This run identified {len(witness_assertion_ids)} unique witness assertion(s), "
            f"{len(predicate_witness_groups)} predicate witness group(s), and "
            f"{len(non_fact_step_groups)} non-fact check group(s). "
            f"{_join_sentences(overview_lines)}"
        ),
        f"Evidence summary: {_join_sentences(predicate_lines)}",
        f"Check summary: {_join_sentences(non_fact_check_lines)}",
        f"Drill-down guidance: {_join_sentences(drilldown_lines)}",
    ]

    return {"headline": headline, "paragraphs": paragraphs}


def _join_sentences(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if isinstance(line, str) and line.strip())


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleTraceNLExplainError(f"{path} must be non-empty string")
    return value


def _require_non_negative_int(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise RuleTraceNLExplainError(f"{path} must be non-negative int")
    return value


def _require_string_list(value: Any, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise RuleTraceNLExplainError(f"{path} must be list[str]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise RuleTraceNLExplainError(f"{path} must be list[str]")
        out.append(item)
    return out


def _require_group_count_list(value: Any, *, path: str, key: str) -> list[str]:
    if not isinstance(value, list):
        raise RuleTraceNLExplainError(f"{path} must be list[object]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuleTraceNLExplainError(f"{path} must be list[object]")
        group_key = item.get(key)
        if not isinstance(group_key, str) or not group_key:
            raise RuleTraceNLExplainError(f"{path}.{key} must be non-empty string")
        out.append(group_key)
    return out


__all__ = ["RuleTraceNLExplainError", "render_rule_run_nl_explain"]
