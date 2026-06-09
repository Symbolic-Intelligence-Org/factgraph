from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factgraph.application.explain.evidence_tree import (
    EvidenceGraph as PathsEvidenceGraph,
    EvidenceTree,
    EvidenceRule,
)
from factgraph.audit.evidence_graph import (
    EDGE_DERIVED_BY,
    EDGE_DERIVES,
    EDGE_HAS_ATOM,
    EDGE_SUPPORTED_BY,
    EDGE_SUPPORTS,
    EDGE_UPDATES,
    EDGE_USES,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NODE_ATOM,
    NODE_CONCLUSION,
    NODE_PREMISE,
    NODE_RULE,
    NODE_RULE_EXPR,
    NODE_SEED,
)


_EDGE_CONNECTORS = {
    EDGE_DERIVED_BY: "is derived by",
    EDGE_USES: "which uses",
    EDGE_HAS_ATOM: "which has atom",
    EDGE_SUPPORTED_BY: "is supported by",
    EDGE_SUPPORTS: "is supported by",
    EDGE_DERIVES: "derives",
    EDGE_UPDATES: "updates",
}


def walk_evidence(
    graph: EvidenceGraph | PathsEvidenceGraph,
    *,
    row: object | None = None,
    status: str = "passed",
    failure_class: str | None = None,
) -> tuple[str, ...]:
    """Walk a layered EvidenceGraph from root and produce deterministic NL lines."""
    if isinstance(graph, PathsEvidenceGraph):
        return _walk_paths_evidence(graph, row=row, status=status, failure_class=failure_class)
    if not isinstance(graph, EvidenceGraph):
        raise ValueError("graph must be EvidenceGraph")

    node_by_id = {node.node_id: node for node in graph.nodes}
    child_edges: dict[str, list[EvidenceEdge]] = {node.node_id: [] for node in graph.nodes}
    for edge in graph.edges:
        child_edges.setdefault(edge.to_node_id, []).append(edge)
    for edges in child_edges.values():
        edges.sort(key=_edge_sort_key)

    lines: list[str] = []

    def visit(node_id: str, *, depth: int, incoming_edge: EvidenceEdge | None) -> None:
        node = node_by_id[node_id]
        indent = "  " * depth
        rendered = _render_node(node, row=row, status=status, failure_class=failure_class)
        if incoming_edge is None:
            lines.append(f"{indent}{rendered}")
        else:
            connector = _EDGE_CONNECTORS.get(incoming_edge.edge_kind, incoming_edge.edge_kind)
            lines.append(f"{indent}{connector} {rendered}")
        for edge in child_edges.get(node_id, ()):
            visit(edge.from_node_id, depth=depth + 1, incoming_edge=edge)

    visit(graph.root_node_id, depth=0, incoming_edge=None)
    return tuple(lines)


def _walk_paths_evidence(
    graph: PathsEvidenceGraph,
    *,
    row: object | None,
    status: str,
    failure_class: str | None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for path_index, path in enumerate(graph.paths):
        if not isinstance(path, EvidenceTree):
            lines.append(f"Timeline[{path_index}]: {path.status}")
            continue
        prefix = "Conclusion" if status == "passed" else "NOT concluded"
        row_id = getattr(row, "row_id", None)
        row_suffix = f" [{row_id}]" if isinstance(row_id, str) and row_id else ""
        failure_suffix = f" ({failure_class})" if status == "failed" and failure_class else ""
        lines.append(f"{prefix}: {path.tree_id}{row_suffix}{failure_suffix}")
        for rule in sorted(path.rules, key=_paths_rule_sort_key):
            lines.extend(_render_paths_rule(rule))
        for join in path.joins:
            lines.append(
                f"  Join: {join.left.rule_occurrence_alias}.{join.left.port_name} = "
                f"{join.right.rule_occurrence_alias}.{join.right.port_name} — {join.status}"
            )
    return tuple(lines)


def _paths_rule_sort_key(rule: EvidenceRule) -> tuple[int, str]:
    role_rank = 0 if rule.role == "head" else 1
    return (role_rank, rule.occurrence_alias)


def _render_paths_rule(rule: EvidenceRule) -> tuple[str, ...]:
    label = f'Rule "{rule.rule_id}"' if rule.role == "head" else f'Body "{rule.occurrence_alias}"'
    lines = [f"  {label}: {rule.status}"]
    for atom in rule.atoms:
        rendered = atom.repr_text or type(atom.form).__name__
        lines.append(f"    Atom: {rendered} — {_paths_verdict_status(atom.verdict)}")
    return tuple(lines)


def _paths_verdict_status(verdict: object) -> str:
    name = type(verdict).__name__
    if name == "Holds":
        return "holds"
    if name == "NotReached":
        return "not_reached"
    return "fails"


def _edge_sort_key(edge: EvidenceEdge) -> tuple[str, str, str]:
    return (edge.edge_kind, edge.rule_label or "", edge.from_node_id)


def _render_node(
    node: EvidenceNode,
    *,
    row: object | None,
    status: str,
    failure_class: str | None,
) -> str:
    summary = _node_summary(node)
    if node.node_kind == NODE_CONCLUSION:
        return _render_conclusion(node, summary=summary, row=row, status=status, failure_class=failure_class)
    if node.node_kind == NODE_RULE_EXPR:
        ast_form = _engine_meta_str(node.engine_meta, "ast_form")
        return f"RuleExpr({ast_form})" if ast_form else f"RuleExpr: {summary}"
    if node.node_kind == NODE_RULE:
        rule_id = _engine_meta_str(node.engine_meta, "rule_id") or summary
        return f'Rule "{rule_id}"'
    if node.node_kind == NODE_ATOM:
        return _render_atom(node, summary=summary)
    if node.node_kind == NODE_SEED:
        return f"ledger fact: {summary}"
    if node.node_kind == NODE_PREMISE:
        return f"Premise: {summary}"
    return summary


def _render_conclusion(
    node: EvidenceNode,
    *,
    summary: str,
    row: object | None,
    status: str,
    failure_class: str | None,
) -> str:
    if status == "failed":
        suffix = f" ({failure_class})" if failure_class else ""
        return f"NOT concluded: {summary}{suffix}"
    row_id = getattr(row, "row_id", None)
    row_suffix = f" [{row_id}]" if isinstance(row_id, str) and row_id else ""
    return f"Conclusion: {summary}{row_suffix}"


def _render_atom(node: EvidenceNode, *, summary: str) -> str:
    atom_status = _engine_meta_str(node.engine_meta, "atom_status")
    atom_index = node.engine_meta.get("atom_index")
    prefix = f"Atom[{atom_index}]" if isinstance(atom_index, int) else "Atom"
    if atom_status:
        return f"{prefix}: {summary} — {atom_status}"
    return f"{prefix}: {summary}"


def _node_summary(node: EvidenceNode) -> str:
    if node.value_summary:
        return node.value_summary
    if node.label:
        return node.label
    return node.node_id


def _engine_meta_str(engine_meta: Mapping[str, Any], key: str) -> str | None:
    value = engine_meta.get(key)
    return value if isinstance(value, str) and value else None
