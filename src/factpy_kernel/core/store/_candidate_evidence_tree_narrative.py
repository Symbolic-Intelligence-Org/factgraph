from __future__ import annotations

from collections.abc import Mapping
from typing import Any


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

    total_nodes = sum(node_count_by_role.values())
    headline = (
        f"Candidate {candidate_id} uses degraded support kind {support_kind} without witness artifacts."
        if is_degraded
        else f"Candidate {candidate_id} uses support kind {support_kind} across {total_nodes} tree node(s)."
    )

    overview_lines = [
        f"Root result kind: {root_result_kind if root_result_kind is not None else '-'}.",
        "Role counts: "
        + ", ".join(f"{role}={node_count_by_role[role]}" for role in _ROLE_ORDER)
        + ".",
        f"Recursive depth: {recursive_depth}.",
    ]

    if is_degraded:
        evidence_lines = [
            "No witness assertions or constraint checks are available because this candidate uses degraded support."
        ]
        rule_chain_lines = ["No recursive rule-chain proof is available for degraded support."]
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

    return {
        "headline": headline,
        "overview_lines": overview_lines,
        "evidence_lines": evidence_lines,
        "rule_chain_lines": rule_chain_lines,
        "terminal_lines": terminal_lines,
        "drilldown_lines": drilldown_lines,
    }


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be non-empty string")
    return value


def _require_non_negative_int(value: Any, *, path: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be non-negative int")
    return value


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


def _require_role_counts(value: Any, *, path: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise CandidateEvidenceTreeNarrativeError(f"{path} must be object")
    out: dict[str, int] = {}
    for role in _ROLE_ORDER:
        count = value.get(role)
        if not isinstance(count, int) or count < 0:
            raise CandidateEvidenceTreeNarrativeError(f"{path}.{role} must be non-negative int")
        out[role] = count
    return out


__all__ = [
    "CandidateEvidenceTreeNarrativeError",
    "render_candidate_evidence_tree_narrative",
]
