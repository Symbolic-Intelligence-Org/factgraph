from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factgraph.core.annotation import ConditionImpact, rank_certainty_conditions
from factgraph.core.store._support import PROBLOG_PROVENANCE_KIND


class CandidateEvidenceTreeNarrativeError(ValueError):
    pass


_ROLE_ORDER = (
    "structural",
    "witness",
    "constraint",
    "rule_chain",
    "terminal",
    "degraded",
)


def render_candidate_evidence_tree_narrative(
    summary: dict[str, Any],
    *,
    certainty_summary: dict[str, Any] | None = None,
    tree: dict[str, Any] | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    if not isinstance(summary, Mapping):
        raise CandidateEvidenceTreeNarrativeError("summary must be object")
    if not isinstance(locale, str) or not locale:
        raise CandidateEvidenceTreeNarrativeError("locale must be non-empty string")

    candidate_id = _require_non_empty_str(summary.get("candidate_id"), path="summary.candidate_id")
    support_kind = _require_non_empty_str(summary.get("support_kind"), path="summary.support_kind")
    is_degraded = _require_bool(summary.get("is_degraded"), path="summary.is_degraded")
    root_result_kind = summary.get("root_result_kind")
    if root_result_kind is not None and (not isinstance(root_result_kind, str) or not root_result_kind):
        raise CandidateEvidenceTreeNarrativeError("summary.root_result_kind must be non-empty string or null")
    node_count_by_role = _require_role_counts(summary.get("node_count_by_role"), path="summary.node_count_by_role")
    witness_assertion_count = _require_non_negative_int(
        summary.get("witness_assertion_count"),
        path="summary.witness_assertion_count",
    )
    rule_ref_count = _require_non_negative_int(summary.get("rule_ref_count"), path="summary.rule_ref_count")
    recursive_depth = _require_non_negative_int(summary.get("recursive_depth"), path="summary.recursive_depth")
    has_unresolved = _require_bool(summary.get("has_unresolved"), path="summary.has_unresolved")
    has_boundary = _require_bool(summary.get("has_boundary"), path="summary.has_boundary")
    unresolved_reasons = _require_string_list(
        summary.get("unresolved_reasons"),
        path="summary.unresolved_reasons",
    )
    boundary_reasons = _require_string_list(
        summary.get("boundary_reasons"),
        path="summary.boundary_reasons",
    )
    proof_goal_count = _optional_non_negative_int(
        summary.get("proof_goal_count"),
        path="summary.proof_goal_count",
    )
    proof_leaf_count = _optional_non_negative_int(
        summary.get("proof_leaf_count"),
        path="summary.proof_leaf_count",
    )
    problog_probability = _optional_number(
        summary.get("problog_probability"),
        path="summary.problog_probability",
    )
    is_problog = (
        support_kind == PROBLOG_PROVENANCE_KIND
        or proof_goal_count is not None
        or proof_leaf_count is not None
        or problog_probability is not None
    )

    total_nodes = sum(node_count_by_role.values())
    headline = (
        f"Candidate {candidate_id} uses degraded support kind {support_kind} without witness artifacts."
        if is_degraded
        else f"Candidate {candidate_id} uses support kind {support_kind} across {total_nodes} tree node(s)."
    )

    overview_lines = [
        f"Root result kind: {root_result_kind if root_result_kind is not None else '-'}.",
        "Role counts: "
        + ", ".join(
            f"{role}={node_count_by_role[role]}"
            for role in (_ROLE_ORDER + (("proof",) if "proof" in node_count_by_role or is_problog else ()))
        )
        + ".",
        f"Recursive depth: {recursive_depth}.",
    ]

    if is_degraded:
        evidence_lines = [
            "No witness assertions or constraint checks are available because this candidate uses degraded support."
        ]
        rule_chain_lines = ["No recursive rule-chain proof is available for degraded support."]
    elif is_problog:
        evidence_lines = [
            "ProbLog proof tree: "
            f"{proof_goal_count or 0} intermediate goals, {proof_leaf_count or 0} leaf facts."
        ]
        rule_chain_lines = [f"Proof depth: {recursive_depth}."]
    else:
        evidence_lines = [
            f"Witness assertions: {witness_assertion_count}.",
            (
                f"Witness nodes: {node_count_by_role['witness']}; "
                f"constraint nodes: {node_count_by_role['constraint']}."
            ),
        ]
        rule_chain_lines = (
            [
                f"Rule reference nodes: {rule_ref_count}.",
                f"Recursive proof depth: {recursive_depth}.",
            ]
            if rule_ref_count > 0
            else ["No rule-chain nodes were captured."]
        )

    if has_unresolved or has_boundary:
        terminal_lines: list[str] = []
        if has_unresolved:
            terminal_lines.append(f"Unresolved support reasons: {', '.join(unresolved_reasons)}.")
        if has_boundary:
            terminal_lines.append(f"Recursion boundary reasons: {', '.join(boundary_reasons)}.")
    else:
        terminal_lines = ["No unresolved support or recursion boundaries were encountered."]

    if is_degraded:
        drilldown_lines = [
            "Open the raw tree below to inspect the degraded support envelope.",
            "This candidate does not expose native witness assertions or recursive child proof.",
        ]
    elif is_problog:
        drilldown_lines = [
            "Open proof goal nodes to inspect recursive subgoals.",
            "Proof leaf nodes are logical terminals and do not link to ledger assertions.",
        ]
    else:
        drilldown_lines = [
            (
                "Open referenced support branches to inspect recursive child proof."
                if rule_ref_count > 0
                else "This tree has no recursive rule-chain branches to inspect."
            ),
            (
                "Open linked assertion nodes to inspect witness facts."
                if witness_assertion_count > 0
                else "No assertion witness pages are linked in this tree."
            ),
        ]

    narrative = {
        "headline": headline,
        "overview_lines": overview_lines,
        "evidence_lines": evidence_lines,
        "rule_chain_lines": rule_chain_lines,
        "terminal_lines": terminal_lines,
        "drilldown_lines": drilldown_lines,
    }
    if problog_probability is not None:
        narrative["probability_lines"] = [f"ProbLog probability: {_format_probability(problog_probability)}."]
    if certainty_summary is not None:
        certainty_lines, certainty_bottleneck = _build_certainty_section(certainty_summary)
        narrative["certainty_lines"] = certainty_lines
        if certainty_bottleneck is not None:
            narrative["certainty_bottleneck"] = certainty_bottleneck
    if tree is not None:
        source_lines = _collect_source_lines(tree)
        if source_lines:
            narrative["source_lines"] = source_lines
    return narrative


def _build_certainty_section(value: Any) -> tuple[list[str], dict[str, Any] | None]:
    """Return (certainty_lines, certainty_bottleneck) from certainty_summary dict."""
    if not isinstance(value, Mapping):
        raise CandidateEvidenceTreeNarrativeError("certainty_summary must be object")
    aggregate_certainty = _optional_number(
        value.get("aggregate_certainty"),
        path="certainty_summary.aggregate_certainty",
    )
    conditions = value.get("conditions")
    if not isinstance(conditions, list):
        raise CandidateEvidenceTreeNarrativeError("certainty_summary.conditions must be list[object]")

    condition_impacts: list[ConditionImpact] = []
    for index, item in enumerate(conditions):
        if not isinstance(item, Mapping):
            raise CandidateEvidenceTreeNarrativeError("certainty_summary.conditions must be list[object]")
        atom_key = _require_non_empty_str(
            item.get("atom_key"),
            path=f"certainty_summary.conditions[{index}].atom_key",
        )
        node_kind = _require_non_empty_str(
            item.get("node_kind"),
            path=f"certainty_summary.conditions[{index}].node_kind",
        )
        weight = _optional_number(
            item.get("weight"),
            path=f"certainty_summary.conditions[{index}].weight",
        )
        impact = _optional_number(
            item.get("impact"),
            path=f"certainty_summary.conditions[{index}].impact",
        )
        condition_impacts.append(
            ConditionImpact(
                atom_key=atom_key,
                node_kind=node_kind,
                weight=weight,
                impact=impact,
            )
        )

    aggregation = value.get("aggregation", "bottleneck")
    if not isinstance(aggregation, str) or not aggregation:
        raise CandidateEvidenceTreeNarrativeError("certainty_summary.aggregation must be non-empty string")

    ranked = rank_certainty_conditions(
        condition_impacts,
        aggregate_certainty,
        aggregation=aggregation,
    )

    aggregate_label = "additive" if aggregation == "additive" else "bottleneck"
    lines = [
        "Certainty (eligible child-proof subtree): "
        f"aggregate certainty ({aggregate_label}): {aggregate_certainty if aggregate_certainty is not None else '-'}."
    ]
    bottleneck_keys: list[str] = []
    bottleneck_impact: float | None = None
    for ranked_condition in ranked:
        if ranked_condition.weight is None:
            lines.append(
                f"Condition {ranked_condition.atom_key} ({ranked_condition.node_kind}): unweighted."
            )
            continue
        impact_text = ranked_condition.impact if ranked_condition.impact is not None else "-"
        suffix = " [bottleneck]" if ranked_condition.is_bottleneck else ""
        lines.append(
            f"Condition {ranked_condition.atom_key} ({ranked_condition.node_kind}): "
            f"weight={ranked_condition.weight}, impact={impact_text}.{suffix}"
        )
        if ranked_condition.is_bottleneck:
            bottleneck_keys.append(ranked_condition.atom_key)
            bottleneck_impact = ranked_condition.impact

    bottleneck: dict[str, Any] | None = None
    if bottleneck_keys and bottleneck_impact is not None:
        bottleneck = {"atom_keys": bottleneck_keys, "impact": bottleneck_impact}

    return lines, bottleneck


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be non-empty string")
    return value


def _require_non_negative_int(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be non-negative int")
    return value


def _optional_non_negative_int(value: Any, *, path: str) -> int | None:
    if value is None:
        return None
    return _require_non_negative_int(value, path=path)


def _optional_number(value: Any, *, path: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be number or null")
    return float(value)


def _format_probability(value: float) -> str:
    return f"{float(value):.12g}"


def _require_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be bool")
    return value


def _require_string_list(value: Any, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be list[str]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise CandidateEvidenceTreeNarrativeError(f"{path} must be list[str]")
        out.append(item)
    return out


def _collect_source_lines(tree: Any) -> list[str]:
    """DFS scan of the evidence tree for assertion_fact nodes with fact_meta.source.
    The tree argument is the full candidate_evidence_tree wrapper dict (with a 'root' key).
    """
    lines: list[str] = []
    root = tree.get("root") if isinstance(tree, Mapping) else None
    _collect_source_lines_node(root if root is not None else tree, lines)
    return lines


def _collect_source_lines_node(node: Any, lines: list[str]) -> None:
    if not isinstance(node, Mapping):
        return
    if node.get("node_kind") == "assertion_fact":
        fact_meta = node.get("fact_meta")
        if isinstance(fact_meta, Mapping):
            source = fact_meta.get("source")
            if source:
                pred_id = node.get("pred_id", "")
                e_ref = node.get("e_ref", "")
                label = f"{pred_id}({e_ref})" if pred_id else str(node.get("asrt_id", ""))
                approved_by = fact_meta.get("approved_by")
                line = f"{label} - from '{source}'"
                if approved_by:
                    line += f" (approved by {approved_by})"
                lines.append(line)
    for child in node.get("children", []):
        _collect_source_lines_node(child, lines)


def _require_role_counts(value: Any, *, path: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be object")
    out: dict[str, int] = {}
    for role in _ROLE_ORDER:
        count = value.get(role)
        if not isinstance(count, int) or count < 0:
            raise CandidateEvidenceTreeNarrativeError(f"{path}.{role} must be non-negative int")
        out[role] = count
    proof_count = value.get("proof")
    if proof_count is not None:
        if not isinstance(proof_count, int) or proof_count < 0:
            raise CandidateEvidenceTreeNarrativeError(f"{path}.proof must be non-negative int")
        out["proof"] = proof_count
    return out


__all__ = [
    "CandidateEvidenceTreeNarrativeError",
    "render_candidate_evidence_tree_narrative",
]
