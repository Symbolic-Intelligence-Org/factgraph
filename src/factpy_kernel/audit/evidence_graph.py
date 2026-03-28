from __future__ import annotations

from dataclasses import dataclass, field
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
]
