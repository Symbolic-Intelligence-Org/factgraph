from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factpy_kernel.core.store._support import PROBLOG_PROVENANCE_KIND, _DEGRADED_SUPPORT_KINDS


class CandidateEvidenceTreeSummaryError(ValueError):
    pass


_ROLE_ORDER = (
    "structural",
    "witness",
    "constraint",
    "rule_chain",
    "terminal",
    "degraded",
)

_ROLE_BY_NODE_KIND = {
    "candidate_result": "structural",
    "support_section": "structural",
    "rule_ref_section": "structural",
    "proof_goal": "proof",
    "proof_leaf": "proof",
    "predicate_witness_group": "witness",
    "assertion_fact": "witness",
    "non_fact_check": "constraint",
    "rule_ref": "rule_chain",
    "referenced_support": "rule_chain",
    "unresolved_support": "terminal",
    "recursion_boundary": "terminal",
    "degraded_support": "degraded",
}


def summarize_candidate_evidence_tree_dict(tree: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(tree, Mapping):
        raise CandidateEvidenceTreeSummaryError("tree must be object")

    kind = tree.get("kind")
    if kind != "candidate_evidence_tree":
        raise CandidateEvidenceTreeSummaryError("tree.kind must be candidate_evidence_tree")

    candidate_id = _require_non_empty_str(tree.get("candidate_id"), path="tree.candidate_id")
    support_kind = _require_non_empty_str(tree.get("support_kind"), path="tree.support_kind")
    root = tree.get("root")
    if not isinstance(root, Mapping):
        raise CandidateEvidenceTreeSummaryError("tree.root must be object")

    root_result_kind = root.get("root_result_kind")
    if root_result_kind is not None and (not isinstance(root_result_kind, str) or not root_result_kind):
        raise CandidateEvidenceTreeSummaryError("tree.root.root_result_kind must be non-empty string or null")

    node_count_by_role = {role: 0 for role in _ROLE_ORDER}
    witness_assertion_count = 0
    rule_ref_count = 0
    recursive_depth = 0
    unresolved_reasons: set[str] = set()
    boundary_reasons: set[str] = set()
    proof_goal_count = 0
    proof_leaf_count = 0
    root_engine_meta = root.get("engine_meta")
    problog_probability = _optional_probability(root_engine_meta, path="tree.root.engine_meta")

    def walk(node: Mapping[str, Any], *, depth: int) -> None:
        nonlocal witness_assertion_count, rule_ref_count, recursive_depth
        nonlocal proof_goal_count, proof_leaf_count

        node_kind = _require_non_empty_str(node.get("node_kind"), path="tree.node.node_kind")
        role = _ROLE_BY_NODE_KIND.get(node_kind)
        if role is None:
            raise CandidateEvidenceTreeSummaryError(f"unsupported tree node_kind: {node_kind}")
        if role not in node_count_by_role:
            node_count_by_role[role] = 0
        node_count_by_role[role] += 1

        next_depth = depth
        if node_kind == "assertion_fact":
            witness_assertion_count += 1
        elif node_kind == "proof_goal":
            proof_goal_count += 1
            next_depth = depth + 1
            recursive_depth = max(recursive_depth, next_depth)
        elif node_kind == "proof_leaf":
            proof_leaf_count += 1
        elif node_kind == "rule_ref":
            rule_ref_count += 1
        elif node_kind == "referenced_support":
            next_depth = depth + 1
            recursive_depth = max(recursive_depth, next_depth)
        elif node_kind == "unresolved_support":
            unresolved_reasons.add(_require_non_empty_str(node.get("reason"), path="tree.node.reason"))
        elif node_kind == "recursion_boundary":
            boundary_reasons.add(
                _require_non_empty_str(node.get("boundary_reason"), path="tree.node.boundary_reason")
            )

        children = node.get("children", [])
        if not isinstance(children, list):
            raise CandidateEvidenceTreeSummaryError("tree.node.children must be list[object]")
        for child in children:
            if not isinstance(child, Mapping):
                raise CandidateEvidenceTreeSummaryError("tree.node.children must be list[object]")
            walk(child, depth=next_depth)

    walk(root, depth=0)

    summary = {
        "candidate_id": candidate_id,
        "support_kind": support_kind,
        "is_degraded": support_kind in _DEGRADED_SUPPORT_KINDS,
        "root_result_kind": root_result_kind,
        "node_count_by_role": dict(node_count_by_role),
        "witness_assertion_count": witness_assertion_count,
        "rule_ref_count": rule_ref_count,
        "recursive_depth": recursive_depth,
        "has_unresolved": bool(unresolved_reasons),
        "has_boundary": bool(boundary_reasons),
        "unresolved_reasons": sorted(unresolved_reasons),
        "boundary_reasons": sorted(boundary_reasons),
    }
    if support_kind == PROBLOG_PROVENANCE_KIND or "proof" in node_count_by_role:
        summary["node_count_by_role"] = {
            **summary["node_count_by_role"],
            "proof": int(node_count_by_role.get("proof", 0)),
        }
        summary["proof_goal_count"] = proof_goal_count
        summary["proof_leaf_count"] = proof_leaf_count
    if problog_probability is not None:
        summary["problog_probability"] = problog_probability
    return summary


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidateEvidenceTreeSummaryError(f"{path} must be non-empty string")
    return value


def _optional_probability(value: Any, *, path: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise CandidateEvidenceTreeSummaryError(f"{path} must be object when present")
    probability = value.get("probability")
    if probability is None:
        return None
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        raise CandidateEvidenceTreeSummaryError(f"{path}.probability must be number when present")
    return float(probability)


__all__ = [
    "CandidateEvidenceTreeSummaryError",
    "summarize_candidate_evidence_tree_dict",
]
