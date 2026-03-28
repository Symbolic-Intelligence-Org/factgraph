from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from types import MappingProxyType
from typing import Any, Mapping

LAYOUT_TREE = "tree"
LAYOUT_TIMELINE = "timeline"

NODE_CONCLUSION = "conclusion"
NODE_PREMISE = "premise"
NODE_SEED = "seed"

EDGE_SUPPORTS = "supports"
EDGE_DERIVES = "derives"
EDGE_UPDATES = "updates"

_VALID_LAYOUT_HINTS = frozenset((LAYOUT_TREE, LAYOUT_TIMELINE))
_VALID_NODE_KINDS = frozenset((NODE_CONCLUSION, NODE_PREMISE, NODE_SEED))
_VALID_EDGE_KINDS = frozenset((EDGE_SUPPORTS, EDGE_DERIVES, EDGE_UPDATES))


@dataclass(frozen=True)
class EvidenceNode:
    """Renderer-facing evidence point normalized from an engine-native carrier."""

    node_id: str
    node_kind: str
    component: str
    label: str
    value_summary: str
    timestamp: int | None = None
    engine_meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine_meta", MappingProxyType(dict(self.engine_meta)))
        if self.node_kind not in _VALID_NODE_KINDS:
            raise ValueError(f"unsupported node_kind: {self.node_kind}")


@dataclass(frozen=True)
class EvidenceEdge:
    """Directed causal/support relation between two normalized evidence nodes."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_kind: str
    rule_label: str | None = None
    engine_meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine_meta", MappingProxyType(dict(self.engine_meta)))
        if self.edge_kind not in _VALID_EDGE_KINDS:
            raise ValueError(f"unsupported edge_kind: {self.edge_kind}")


@dataclass(frozen=True)
class EvidenceGraph:
    """Shared cross-engine explainability representation for audit-layer consumers."""

    graph_id: str
    engine: str
    root_node_id: str
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    support_kind: str
    layout_hint: str = LAYOUT_TREE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.layout_hint not in _VALID_LAYOUT_HINTS:
            raise ValueError(f"unsupported layout_hint: {self.layout_hint}")

        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node_id in EvidenceGraph.nodes")

        edge_ids = [edge.edge_id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate edge_id in EvidenceGraph.edges")

        node_id_set = set(node_ids)
        if self.root_node_id not in node_id_set:
            raise ValueError(f"root_node_id '{self.root_node_id}' not in nodes")

        for edge in self.edges:
            if edge.from_node_id not in node_id_set:
                raise ValueError(f"edge from_node_id '{edge.from_node_id}' not in nodes")
            if edge.to_node_id not in node_id_set:
                raise ValueError(f"edge to_node_id '{edge.to_node_id}' not in nodes")


def render_evidence_graph_html(graph: EvidenceGraph) -> str:
    """Render an EvidenceGraph as a standalone HTML fragment."""
    if graph.layout_hint == LAYOUT_TREE:
        return _render_tree_layout(graph)
    if graph.layout_hint == LAYOUT_TIMELINE:
        return _render_timeline_layout(graph)
    raise ValueError(f"unsupported layout_hint: {graph.layout_hint}")


def evidence_graph_to_dict(graph: EvidenceGraph) -> dict[str, Any]:
    """Serialize an ``EvidenceGraph`` to a JSON-friendly dict."""
    if not isinstance(graph, EvidenceGraph):
        raise ValueError("graph must be EvidenceGraph")
    return {
        "graph_id": graph.graph_id,
        "engine": graph.engine,
        "root_node_id": graph.root_node_id,
        "nodes": [
            {
                "node_id": node.node_id,
                "node_kind": node.node_kind,
                "component": node.component,
                "label": node.label,
                "value_summary": node.value_summary,
                "timestamp": node.timestamp,
                "engine_meta": _to_jsonable(node.engine_meta),
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "edge_id": edge.edge_id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "edge_kind": edge.edge_kind,
                "rule_label": edge.rule_label,
                "engine_meta": _to_jsonable(edge.engine_meta),
            }
            for edge in graph.edges
        ],
        "support_kind": graph.support_kind,
        "layout_hint": graph.layout_hint,
        "metadata": _to_jsonable(graph.metadata),
    }


def evidence_graph_from_dict(row: Mapping[str, Any]) -> EvidenceGraph:
    """Reconstruct an ``EvidenceGraph`` from a JSON-friendly dict."""
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    raw_nodes = row.get("nodes")
    raw_edges = row.get("edges")
    if not isinstance(raw_nodes, list):
        raise ValueError("row.nodes must be list")
    if not isinstance(raw_edges, list):
        raise ValueError("row.edges must be list")
    metadata = row.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("row.metadata must be Mapping[str, Any]")

    return EvidenceGraph(
        graph_id=_require_non_empty_str(row.get("graph_id"), "row.graph_id"),
        engine=_require_non_empty_str(row.get("engine"), "row.engine"),
        root_node_id=_require_non_empty_str(row.get("root_node_id"), "row.root_node_id"),
        nodes=tuple(_evidence_node_from_dict(node_row) for node_row in raw_nodes),
        edges=tuple(_evidence_edge_from_dict(edge_row) for edge_row in raw_edges),
        support_kind=_require_non_empty_str(row.get("support_kind"), "row.support_kind"),
        layout_hint=_require_non_empty_str(row.get("layout_hint"), "row.layout_hint"),
        metadata=_from_jsonable(metadata),
    )


def _render_tree_layout(graph: EvidenceGraph) -> str:
    node_by_id = {node.node_id: node for node in graph.nodes}
    incoming_edges: dict[str, list[EvidenceEdge]] = {node.node_id: [] for node in graph.nodes}
    for edge in graph.edges:
        incoming_edges.setdefault(edge.to_node_id, []).append(edge)
    for edge_list in incoming_edges.values():
        edge_list.sort(key=lambda edge: _tree_edge_sort_key(edge, node_by_id))

    tree_html = _render_tree_node(
        graph.root_node_id,
        node_by_id=node_by_id,
        incoming_edges=incoming_edges,
        ancestry=(),
        is_root=True,
    )
    return (
        "<section class='evidence-graph evidence-graph-tree' data-layout='tree' "
        "style='background:var(--color-surface,#fffdf8);border:1px solid var(--color-border,#d6d1c4);"
        "border-radius:10px;padding:18px 20px;margin:14px 0;box-shadow:0 10px 30px rgba(43,43,43,0.08)'>"
        f"{_render_graph_header(graph, title='Unified Evidence Graph', subtitle='Tree Layout')}"
        "<div class='evidence-tree-root' style='display:block'>"
        f"{tree_html}"
        "</div>"
        "</section>"
    )


def _render_tree_node(
    node_id: str,
    *,
    node_by_id: Mapping[str, EvidenceNode],
    incoming_edges: Mapping[str, list[EvidenceEdge]],
    ancestry: tuple[str, ...],
    is_root: bool = False,
) -> str:
    node = node_by_id[node_id]
    if node_id in ancestry:
        return (
            "<div class='evidence-tree-recursion' "
            "style='margin:8px 0 0 20px;padding:8px 12px;border-left:3px solid var(--color-terminal,#b42318);"
            "background:#fdecea;border-radius:8px;font-size:.85rem'>Cycle detected</div>"
        )

    border_color, header_color, background = _node_palette(node.node_kind)
    header_badges = [_node_kind_badge(node.node_kind)]
    if is_root:
        header_badges.append(
            "<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:#ece4d6;"
            "color:#6b4f1d;font-size:.72rem;font-weight:700;letter-spacing:.03em'>ROOT</span>"
        )
    props_html = _render_node_properties(node)

    child_fragments: list[str] = []
    for edge in incoming_edges.get(node_id, []):
        edge_html = _render_edge_note(edge)
        child_fragments.append(
            "<div class='evidence-tree-branch' style='margin:8px 0 0 20px'>"
            f"{edge_html}"
            f"{_render_tree_node(edge.from_node_id, node_by_id=node_by_id, incoming_edges=incoming_edges, ancestry=(*ancestry, node_id))}"
            "</div>"
        )

    return (
        "<div class='evidence-tree-node' "
        f"data-node-id='{escape(node.node_id, quote=True)}' data-node-kind='{escape(node.node_kind, quote=True)}' "
        f"style='border-left:4px solid {border_color};background:{background};border-radius:10px;"
        "margin:10px 0;overflow:hidden;box-shadow:0 10px 30px rgba(43,43,43,0.06)'>"
        f"<div class='evidence-tree-node-header' style='padding:10px 14px;background:{header_color};color:#fff'>"
        f"<div style='display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap'>"
        f"<div><strong style='font-size:.95rem'>{escape(node.label)}</strong> "
        f"<code style='font-size:.8rem;color:rgba(255,255,255,0.9)'>{escape(node.component)}</code></div>"
        f"<div style='display:flex;gap:6px;flex-wrap:wrap'>{''.join(header_badges)}</div>"
        "</div>"
        "</div>"
        "<div class='evidence-tree-node-body' style='padding:10px 14px;font-size:.86rem'>"
        f"{props_html}"
        "</div>"
        f"{''.join(child_fragments)}"
        "</div>"
    )


def _render_timeline_layout(graph: EvidenceGraph) -> str:
    nodes = sorted(
        graph.nodes,
        key=lambda node: (
            -1 if node.timestamp is None else int(node.timestamp),
            str(node.component),
            str(node.label),
            str(node.node_id),
        ),
    )
    timestamps = sorted({int(node.timestamp) for node in nodes if node.timestamp is not None})
    if not timestamps:
        timestamps = [0]

    component_order: list[str] = []
    for node in nodes:
        if node.component not in component_order:
            component_order.append(node.component)

    nodes_by_cell: dict[tuple[str, int], list[EvidenceNode]] = {}
    for node in nodes:
        bucket_ts = int(node.timestamp) if node.timestamp is not None else timestamps[0]
        nodes_by_cell.setdefault((node.component, bucket_ts), []).append(node)
    for bucket_nodes in nodes_by_cell.values():
        bucket_nodes.sort(
            key=lambda node: (
                int(node.timestamp) if node.timestamp is not None else -1,
                _node_kind_order(node.node_kind),
                str(node.label),
                str(node.node_id),
            )
        )

    grid_columns = f"180px repeat({len(timestamps)}, minmax(180px, 1fr))"
    grid_parts: list[str] = [
        (
            "<div class='evidence-timeline-grid' style='display:grid;"
            f"grid-template-columns:{grid_columns};gap:8px;align-items:stretch'>"
        ),
        (
            "<div class='evidence-timeline-corner' style='padding:10px 12px;border:1px solid var(--color-border,#d6d1c4);"
            "border-radius:8px;background:#ece4d6;font-size:.78rem;font-weight:700;letter-spacing:.05em;"
            "text-transform:uppercase;color:var(--color-muted,#6b6b6b)'>Component</div>"
        ),
    ]
    for timestamp in timestamps:
        grid_parts.append(
            "<div class='evidence-timeline-colhead' "
            f"data-timestep='{escape(str(timestamp), quote=True)}' "
            "style='padding:10px 12px;border:1px solid var(--color-border,#d6d1c4);border-radius:8px;"
            "background:#ece4d6;font-size:.78rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;"
            "color:var(--color-muted,#6b6b6b)'>"
            f"Timestep {escape(str(timestamp))}"
            "</div>"
        )

    for component in component_order:
        grid_parts.append(
            "<div class='evidence-timeline-rowhead' "
            f"data-component='{escape(component, quote=True)}' "
            "style='padding:12px;border:1px solid var(--color-border,#d6d1c4);border-radius:8px;background:#f7f4ee;"
            "font-weight:600;word-break:break-all'>"
            f"{escape(component)}"
            "</div>"
        )
        for timestamp in timestamps:
            cards = "".join(_render_timeline_card(node, graph.root_node_id) for node in nodes_by_cell.get((component, timestamp), []))
            empty_cell = "<div style='color:var(--color-muted,#6b6b6b);font-size:.8rem'>&nbsp;</div>"
            grid_parts.append(
                "<div class='evidence-timeline-cell' "
                f"data-component='{escape(component, quote=True)}' data-timestep='{escape(str(timestamp), quote=True)}' "
                "style='min-height:90px;padding:8px;border:1px solid var(--color-border,#d6d1c4);border-radius:8px;"
                "background:rgba(255,255,255,0.7)'>"
                f"{cards or empty_cell}"
                "</div>"
            )
    grid_parts.append("</div>")

    return (
        "<section class='evidence-graph evidence-graph-timeline' data-layout='timeline' "
        "style='background:var(--color-surface,#fffdf8);border:1px solid var(--color-border,#d6d1c4);"
        "border-radius:10px;padding:18px 20px;margin:14px 0;box-shadow:0 10px 30px rgba(43,43,43,0.08)'>"
        f"{_render_graph_header(graph, title='Unified Evidence Graph', subtitle='Timeline Layout')}"
        f"{''.join(grid_parts)}"
        "</section>"
    )


def _render_timeline_card(node: EvidenceNode, root_node_id: str) -> str:
    border_color, _header_color, background = _node_palette(node.node_kind)
    occurred_due_to = node.engine_meta.get("occurred_due_to")
    rule_line = ""
    if isinstance(occurred_due_to, str) and occurred_due_to:
        rule_line = (
            "<div class='evidence-timeline-card-rule' style='color:var(--color-muted,#6b6b6b);font-size:.75rem'>"
            f"{escape(occurred_due_to)}"
            "</div>"
        )
    timestamp_line = ""
    if node.timestamp is not None:
        timestamp_line = (
            "<div class='evidence-timeline-card-ts' style='color:var(--color-muted,#6b6b6b);font-size:.72rem'>"
            f"t={escape(str(node.timestamp))}"
            "</div>"
        )
    root_badge = ""
    if node.node_id == root_node_id:
        root_badge = (
            "<span style='display:inline-block;padding:1px 7px;border-radius:999px;background:#ece4d6;"
            "color:#6b4f1d;font-size:.7rem;font-weight:700;letter-spacing:.03em'>ROOT</span>"
        )
    return (
        "<div class='evidence-timeline-card' "
        f"data-node-id='{escape(node.node_id, quote=True)}' data-node-kind='{escape(node.node_kind, quote=True)}' "
        f"style='border-left:4px solid {border_color};background:{background};border-radius:8px;padding:8px 10px;"
        "margin-bottom:8px;box-shadow:0 6px 18px rgba(43,43,43,0.05)'>"
        "<div style='display:flex;justify-content:space-between;gap:8px;align-items:flex-start'>"
        f"<div><strong>{escape(node.label)}</strong><div style='font-size:.8rem;color:var(--color-muted,#6b6b6b)'>{escape(node.value_summary)}</div></div>"
        f"{root_badge}"
        "</div>"
        f"{timestamp_line}"
        f"{rule_line}"
        f"{_node_kind_badge(node.node_kind)}"
        "</div>"
    )


def _render_graph_header(graph: EvidenceGraph, *, title: str, subtitle: str) -> str:
    meta_items = [
        _header_chip("Engine", graph.engine),
        _header_chip("Support", graph.support_kind),
        _header_chip("Root", graph.root_node_id),
    ]
    return (
        "<div class='evidence-graph-header' style='display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:16px'>"
        "<div>"
        "<p style='margin:0 0 4px;font-size:.75rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--color-accent,#9c6b2f)'>"
        f"{escape(subtitle)}"
        "</p>"
        f"<h3 style='margin:0;font-size:1.05rem'>{escape(title)}</h3>"
        "</div>"
        f"<div style='display:flex;gap:8px;flex-wrap:wrap'>{''.join(meta_items)}</div>"
        "</div>"
    )


def _header_chip(label: str, value: str) -> str:
    return (
        "<span class='evidence-graph-chip' style='display:inline-flex;gap:6px;align-items:center;padding:6px 10px;"
        "border-radius:999px;background:#f1ede3;border:1px solid var(--color-border,#d6d1c4);font-size:.78rem'>"
        f"<strong style='color:var(--color-muted,#6b6b6b)'>{escape(label)}:</strong>{escape(value)}"
        "</span>"
    )


def _render_node_properties(node: EvidenceNode) -> str:
    props = [
        _prop_row("Component", node.component),
        _prop_row("Value", node.value_summary),
    ]
    if node.timestamp is not None:
        props.append(_prop_row("Timestep", str(node.timestamp)))
    for label, key in (
        ("Goal", "goal"),
        ("Status", "event_status"),
        ("Location", "location"),
        ("Rule", "occurred_due_to"),
    ):
        value = node.engine_meta.get(key)
        if isinstance(value, str) and value:
            props.append(_prop_row(label, value))
    clause_groundings = node.engine_meta.get("clause_groundings")
    if isinstance(clause_groundings, tuple) and clause_groundings:
        props.append(_prop_row("Groundings", "; ".join(str(item) for item in clause_groundings)))
    return "".join(props)


def _render_edge_note(edge: EvidenceEdge) -> str:
    note_items = [edge.edge_kind]
    if edge.rule_label:
        note_items.append(edge.rule_label)
    return (
        "<div class='evidence-tree-edge-note' style='margin:0 0 6px 8px;font-size:.75rem;color:var(--color-muted,#6b6b6b)'>"
        f"{escape(' • '.join(note_items))}"
        "</div>"
    )


def _prop_row(label: str, value: str) -> str:
    return (
        "<div class='evidence-node-prop' style='display:flex;gap:8px;padding:2px 0'>"
        f"<span style='min-width:96px;color:var(--color-muted,#6b6b6b)'>{escape(label)}</span>"
        f"<span style='word-break:break-all'>{escape(value)}</span>"
        "</div>"
    )


def _node_palette(node_kind: str) -> tuple[str, str, str]:
    if node_kind == NODE_CONCLUSION:
        return ("#375a7f", "#375a7f", "#f0f6fb")
    if node_kind == NODE_SEED:
        return ("#2e7d32", "#2e7d32", "#eef7ef")
    return ("#7c4d9d", "#7c4d9d", "#f5f0ff")


def _node_kind_badge(node_kind: str) -> str:
    return (
        "<span class='evidence-node-kind-badge' style='display:inline-block;margin-top:6px;padding:1px 8px;"
        "border-radius:999px;background:#ece4d6;color:#6b4f1d;font-size:.72rem;font-weight:700;letter-spacing:.03em'>"
        f"{escape(node_kind.replace('_', ' '))}"
        "</span>"
    )


def _tree_edge_sort_key(edge: EvidenceEdge, node_by_id: Mapping[str, EvidenceNode]) -> tuple[str, str, str]:
    child = node_by_id[edge.from_node_id]
    return (str(child.label), str(child.component), str(edge.edge_id))


def _node_kind_order(node_kind: str) -> int:
    if node_kind == NODE_CONCLUSION:
        return 0
    if node_kind == NODE_SEED:
        return 1
    return 2


def _evidence_node_from_dict(row: Any) -> EvidenceNode:
    if not isinstance(row, Mapping):
        raise ValueError("node row must be Mapping[str, Any]")
    engine_meta = row.get("engine_meta", {})
    if not isinstance(engine_meta, Mapping):
        raise ValueError("node.engine_meta must be Mapping[str, Any]")
    timestamp = row.get("timestamp")
    if timestamp is not None and (isinstance(timestamp, bool) or not isinstance(timestamp, int)):
        raise ValueError("node.timestamp must be int | None")
    return EvidenceNode(
        node_id=_require_non_empty_str(row.get("node_id"), "node.node_id"),
        node_kind=_require_non_empty_str(row.get("node_kind"), "node.node_kind"),
        component=_require_non_empty_str(row.get("component"), "node.component"),
        label=_require_non_empty_str(row.get("label"), "node.label"),
        value_summary=_require_non_empty_str(row.get("value_summary"), "node.value_summary"),
        timestamp=timestamp,
        engine_meta=_from_jsonable(engine_meta),
    )


def _evidence_edge_from_dict(row: Any) -> EvidenceEdge:
    if not isinstance(row, Mapping):
        raise ValueError("edge row must be Mapping[str, Any]")
    engine_meta = row.get("engine_meta", {})
    if not isinstance(engine_meta, Mapping):
        raise ValueError("edge.engine_meta must be Mapping[str, Any]")
    rule_label = row.get("rule_label")
    if rule_label is not None and not isinstance(rule_label, str):
        raise ValueError("edge.rule_label must be str | None")
    return EvidenceEdge(
        edge_id=_require_non_empty_str(row.get("edge_id"), "edge.edge_id"),
        from_node_id=_require_non_empty_str(row.get("from_node_id"), "edge.from_node_id"),
        to_node_id=_require_non_empty_str(row.get("to_node_id"), "edge.to_node_id"),
        edge_kind=_require_non_empty_str(row.get("edge_kind"), "edge.edge_kind"),
        rule_label=rule_label,
        engine_meta=_from_jsonable(engine_meta),
    )


def _require_non_empty_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be non-empty string")
    return value


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _from_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_from_jsonable(item) for item in value)
    return value


__all__ = [
    "LAYOUT_TREE",
    "LAYOUT_TIMELINE",
    "NODE_CONCLUSION",
    "NODE_PREMISE",
    "NODE_SEED",
    "EDGE_SUPPORTS",
    "EDGE_DERIVES",
    "EDGE_UPDATES",
    "EvidenceNode",
    "EvidenceEdge",
    "EvidenceGraph",
    "evidence_graph_to_dict",
    "evidence_graph_from_dict",
    "render_evidence_graph_html",
]
