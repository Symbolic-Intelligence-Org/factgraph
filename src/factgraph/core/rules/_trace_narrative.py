from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RuleTraceNarrativeError(ValueError):
    pass


def render_rule_run_narrative(summary: dict[str, Any], *, locale: str = "en") -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        raise RuleTraceNarrativeError("summary must be object")
    if not isinstance(locale, str) or not locale:
        raise RuleTraceNarrativeError("locale must be non-empty string")

    rule_run_id = summary.get("rule_run_id")
    if not isinstance(rule_run_id, str) or not rule_run_id:
        raise RuleTraceNarrativeError("summary.rule_run_id must be non-empty string")

    root_rule = summary.get("root_rule")
    if not isinstance(root_rule, Mapping):
        raise RuleTraceNarrativeError("summary.root_rule must be object")
    rule_id = root_rule.get("rule_id")
    version = root_rule.get("version")
    if not isinstance(rule_id, str) or not rule_id:
        raise RuleTraceNarrativeError("summary.root_rule.rule_id must be non-empty string")
    if not isinstance(version, str) or not version:
        raise RuleTraceNarrativeError("summary.root_rule.version must be non-empty string")

    root_row_count = _require_non_negative_int(summary.get("root_row_count"), path="summary.root_row_count")
    invocation_count = _require_non_negative_int(summary.get("invocation_count"), path="summary.invocation_count")
    witness_assertion_ids = _require_string_list(
        summary.get("witness_assertion_ids"),
        path="summary.witness_assertion_ids",
    )
    predicate_witness_groups = _require_group_list(
        summary.get("predicate_witness_groups"),
        path="summary.predicate_witness_groups",
        key="pred_id",
    )
    non_fact_step_groups = _require_group_list(
        summary.get("non_fact_step_groups"),
        path="summary.non_fact_step_groups",
        key="kind",
    )

    headline = (
        f"Rule {rule_id}@{version} produced {root_row_count} root row(s) "
        f"across {invocation_count} invocation(s)."
    )
    overview_lines = [
        f"Witness assertions: {len(witness_assertion_ids)} unique assertion(s).",
        f"Predicate witness groups: {len(predicate_witness_groups)}.",
        f"Non-fact check groups: {len(non_fact_step_groups)}.",
    ]

    predicate_lines = [
        (
            f"Predicate {pred_id} was witnessed by {len(asrt_ids)} assertion(s) "
            f"across {len(invocation_ids)} invocation(s)."
        )
        for pred_id, asrt_ids, invocation_ids in sorted(predicate_witness_groups, key=lambda item: item[0])
    ]
    if not predicate_lines:
        predicate_lines = ["No predicate witness groups were captured."]

    non_fact_check_lines = [
        (
            f"Check kind {kind} was evaluated {count} time(s) "
            f"across {len(invocation_ids)} invocation(s)."
        )
        for kind, count, invocation_ids in sorted(non_fact_step_groups, key=lambda item: item[0])
    ]
    if not non_fact_check_lines:
        non_fact_check_lines = ["No non-fact check groups were captured."]

    drilldown_lines = []
    if witness_assertion_ids:
        drilldown_lines.append(
            f"Open the linked assertion detail page(s) for {len(witness_assertion_ids)} witness assertion(s) "
            "to inspect supporting facts."
        )
    else:
        drilldown_lines.append("No witness assertion pages are available for this rule run.")
    drilldown_lines.append("Continue below for invocation-level detail and the full raw trace payload.")

    return {
        "headline": headline,
        "overview_lines": overview_lines,
        "predicate_lines": predicate_lines,
        "non_fact_check_lines": non_fact_check_lines,
        "drilldown_lines": drilldown_lines,
    }


def _require_non_negative_int(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise RuleTraceNarrativeError(f"{path} must be non-negative int")
    return value


def _require_string_list(value: Any, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise RuleTraceNarrativeError(f"{path} must be list[str]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise RuleTraceNarrativeError(f"{path} must be list[str]")
        out.append(item)
    return out


def _require_group_list(value: Any, *, path: str, key: str) -> list[tuple[str, Any, list[str]]]:
    if not isinstance(value, list):
        raise RuleTraceNarrativeError(f"{path} must be list[object]")
    out: list[tuple[str, Any, list[str]]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuleTraceNarrativeError(f"{path} must be list[object]")
        group_key = item.get(key)
        if not isinstance(group_key, str) or not group_key:
            raise RuleTraceNarrativeError(f"{path}.{key} must be non-empty string")
        invocation_ids = _require_string_list(item.get("invocation_ids"), path=f"{path}.invocation_ids")
        if key == "pred_id":
            asrt_ids = _require_string_list(item.get("asrt_ids"), path=f"{path}.asrt_ids")
            out.append((group_key, asrt_ids, invocation_ids))
            continue
        count = _require_non_negative_int(item.get("count"), path=f"{path}.count")
        out.append((group_key, count, invocation_ids))
    return out


__all__ = ["RuleTraceNarrativeError", "render_rule_run_narrative"]
