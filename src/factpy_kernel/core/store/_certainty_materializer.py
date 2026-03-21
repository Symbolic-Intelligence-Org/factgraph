from __future__ import annotations

from typing import Any

from factpy_kernel.core.annotation import CertaintySummary, derive_certainty_summary

from .runtime import Store


def extract_single_referenced_support_tree(tree_dict: dict[str, Any]) -> dict[str, Any] | None:
    root = tree_dict.get("root")
    if not isinstance(root, dict):
        return None
    referenced_support_nodes = _collect_referenced_support_nodes(root)
    if len(referenced_support_nodes) != 1:
        return None
    referenced_support = referenced_support_nodes[0]
    if _node_has_nested_referenced_support(
        referenced_support,
        inside_referenced_support=False,
    ):
        return None
    return {
        "kind": tree_dict.get("kind", "candidate_evidence_tree"),
        "root": referenced_support,
    }


def _collect_referenced_support_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if node.get("node_kind") == "referenced_support":
        out.append(node)
    children = node.get("children")
    if not isinstance(children, list):
        return out
    for child in children:
        if isinstance(child, dict):
            out.extend(_collect_referenced_support_nodes(child))
    return out


def _node_has_nested_referenced_support(
    node: dict[str, Any],
    *,
    inside_referenced_support: bool,
) -> bool:
    node_is_referenced_support = node.get("node_kind") == "referenced_support"
    if node_is_referenced_support and inside_referenced_support:
        return True
    children = node.get("children")
    if not isinstance(children, list):
        return False
    child_inside = inside_referenced_support or node_is_referenced_support
    for child in children:
        if isinstance(child, dict) and _node_has_nested_referenced_support(
            child,
            inside_referenced_support=child_inside,
        ):
            return True
    return False


def certainty_summary_to_dict(summary: CertaintySummary) -> dict[str, Any]:
    return {
        "confidence_kind": summary.confidence_kind,
        "condition_count": summary.condition_count,
        "weighted_condition_count": summary.weighted_condition_count,
        "conditions": [
            {
                "atom_key": item.atom_key,
                "node_kind": item.node_kind,
                "weight": item.weight,
                "impact": item.impact,
            }
            for item in summary.conditions
        ],
        "aggregate_certainty": summary.aggregate_certainty,
    }


def materialize_certainty_summary(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    condition_weights: dict[str, float] | None,
) -> dict[str, Any] | None:
    confidence_kind = store.get_candidate_confidence_kind(candidate_id)
    if confidence_kind != "certainty":
        return None
    certainty_tree = extract_single_referenced_support_tree(tree_dict)
    if condition_weights is None or certainty_tree is None:
        return None
    raw = derive_certainty_summary(certainty_tree, condition_weights, confidence_kind)
    if raw is None:
        return None
    return certainty_summary_to_dict(raw)
