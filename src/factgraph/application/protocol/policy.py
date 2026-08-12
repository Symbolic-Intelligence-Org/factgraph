from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ErrorDTO
from .semantic_address import SemanticPortAddress

PolicyStage: TypeAlias = Literal[
    "policy_construct", "policy_admission", "policy_compile", "policy_lowering_adapter", "policy_compiler_invariant",
]
class PolicyError(ValueError):
    """Typed managed-Policy construction or compilation failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: PolicyStage,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.stage, self.path = code, stage, tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code, message=str(self), path=self.path,
            details={"stage": self.stage, **self.details},
        )
@dataclass(frozen=True)
class PolicyOccurrence:
    alias: str
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        _text(self.alias, "alias")
        object.__setattr__(self, "node_id", _node_id(("occurrence", self.alias)))
@dataclass(frozen=True)
class PolicyUnify:
    left: SemanticPortAddress
    right: SemanticPortAddress
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        if not all(isinstance(item, SemanticPortAddress) for item in (self.left, self.right)):
            raise _shape("PolicyUnify endpoints must be SemanticPortAddress", "INVALID_UNIFY")
        if self.left == self.right:
            raise _shape("PolicyUnify endpoints must be distinct", "INVALID_UNIFY")
        left, right = sorted((self.left, self.right), key=_address_key)
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)
        object.__setattr__(self, "node_id", _node_id(("unify", _address_key(left), _address_key(right))))
@dataclass(frozen=True)
class PolicyAll:
    children: tuple[PolicyNode, ...]
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        children = _children(self.children, "ALL")
        if all(isinstance(child, PolicyUnify) for child in children):
            raise _shape("PolicyAll requires a structural child", "INVALID_POLICY_ALL")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "node_id", _node_id(("all", tuple(c.node_id for c in children))))
@dataclass(frozen=True)
class PolicyAny:
    children: tuple[PolicyExpression, ...]
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        children = _children(self.children, "ANY")
        if any(isinstance(child, PolicyUnify) for child in children):
            raise _shape("PolicyUnify must be a direct PolicyAll child", "INVALID_UNIFY_SCOPE")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "node_id", _node_id(("any", tuple(c.node_id for c in children))))
PolicyExpression: TypeAlias = PolicyOccurrence | PolicyAll | PolicyAny
PolicyNode: TypeAlias = PolicyExpression | PolicyUnify
@dataclass(frozen=True)
class Policy:
    id: str
    when: PolicyExpression
    version: str | None = None
    def __post_init__(self) -> None:
        _text(self.id, "id")
        if self.version is not None:
            _text(self.version, "version")
        if not isinstance(self.when, (PolicyOccurrence, PolicyAll, PolicyAny)):
            raise _shape("Policy.when must be structural", "INVALID_POLICY_ROOT")
@dataclass(frozen=True, order=True)
class PolicyLoweredRef:
    kind: Literal["branch", "occurrence", "body_atom", "unify"]
    branch_id: str
    occurrence_alias: str | None = None
    port_name: str | None = None
    source_index: int | None = None
    lowered_index: int | None = None
    peer_occurrence_alias: str | None = None
    peer_port_name: str | None = None
    def __post_init__(self) -> None:
        shapes = {
            "branch": (False, False, False, False, False, False),
            "occurrence": (True, False, False, False, False, False),
            "body_atom": (True, False, True, True, False, False),
            "unify": (True, True, False, True, True, True),
        }
        values = (
            self.occurrence_alias, self.port_name, self.source_index,
            self.lowered_index, self.peer_occurrence_alias, self.peer_port_name,
        )
        _text(self.branch_id, "branch_id", "INVALID_POLICY_LINEAGE")
        if self.kind not in shapes or tuple(value is not None for value in values) != shapes[self.kind]:
            raise _shape("lowered reference fields do not match kind", "INVALID_POLICY_LINEAGE")
        for name in ("occurrence_alias", "port_name", "peer_occurrence_alias", "peer_port_name"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name, "INVALID_POLICY_LINEAGE")
        for name in ("source_index", "lowered_index"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise _shape(f"{name} must be a non-negative integer", "INVALID_POLICY_LINEAGE")
@dataclass(frozen=True)
class PolicyNodeLineage:
    node_id: str
    node_kind: Literal["occurrence", "all", "any", "unify"]
    lowered_refs: tuple[PolicyLoweredRef, ...]
    def __post_init__(self) -> None:
        _text(self.node_id, "node_id", "INVALID_POLICY_LINEAGE")
        if self.node_kind not in {"occurrence", "all", "any", "unify"}:
            raise _shape("invalid lineage node kind", "INVALID_POLICY_LINEAGE")
        if not isinstance(self.lowered_refs, tuple) or not self.lowered_refs or not all(isinstance(ref, PolicyLoweredRef) for ref in self.lowered_refs):
            raise _shape("lowered_refs must be a non-empty PolicyLoweredRef tuple", "INVALID_POLICY_LINEAGE")
        if len(set(self.lowered_refs)) != len(self.lowered_refs):
            raise _shape("lowered_refs must be unique", "INVALID_POLICY_LINEAGE")
@dataclass(frozen=True)
class PolicyLineage:
    authored_nodes: tuple[PolicyNodeLineage, ...]
    lowered_origins: tuple[tuple[PolicyLoweredRef, tuple[str, ...]], ...]
    def __post_init__(self) -> None:
        if not isinstance(self.authored_nodes, tuple) or not self.authored_nodes or not all(isinstance(node, PolicyNodeLineage) for node in self.authored_nodes):
            raise _shape("authored_nodes must be a non-empty lineage tuple", "INVALID_POLICY_LINEAGE")
        node_ids = {node.node_id for node in self.authored_nodes}
        if len(node_ids) != len(self.authored_nodes) or not isinstance(self.lowered_origins, tuple) or not self.lowered_origins:
            raise _shape("lineage nodes and origins must be non-empty and unique", "INVALID_POLICY_LINEAGE")
        reverse: set[PolicyLoweredRef] = set()
        for item in self.lowered_origins:
            if not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], PolicyLoweredRef):
                raise _shape("invalid lowered origin", "INVALID_POLICY_LINEAGE")
            ref, origins = item
            valid_origins = isinstance(origins, tuple) and origins and all(isinstance(origin, str) and origin for origin in origins)
            if ref in reverse or not valid_origins or len(set(origins)) != len(origins) or set(origins) - node_ids:
                raise _shape("lowered origins must be unique and reference authored nodes", "INVALID_POLICY_LINEAGE")
            reverse.add(ref)
        forward = {ref for node in self.authored_nodes for ref in node.lowered_refs}
        if forward != reverse:
            raise _shape("Policy lineage must be total in both directions", "INVALID_POLICY_LINEAGE")
def _children(value: object, kind: str) -> tuple[PolicyNode, ...]:
    allowed = (PolicyOccurrence, PolicyAll, PolicyAny, PolicyUnify)
    if not isinstance(value, tuple) or not value or any(not isinstance(x, allowed) for x in value):
        raise _shape(f"Policy{kind}.children must be a non-empty node tuple", f"INVALID_POLICY_{kind}")
    by_id = {child.node_id: child for child in value}
    if len(by_id) != len(value):
        raise _shape("Policy children contain a duplicate node", "DUPLICATE_POLICY_NODE")
    return tuple(by_id[node_id] for node_id in sorted(by_id))
def _node_id(payload: tuple[object, ...]) -> str:
    raw = json.dumps(
        {"format": "policy_node_v0", "payload": payload},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()
    return f"pn:{sha256_hex(raw)}"
def _address_key(address: SemanticPortAddress) -> tuple[str, str]:
    return address.occurrence_alias, address.port_name
def _text(value: object, name: str, code: str = "INVALID_POLICY_SHAPE") -> None:
    if not isinstance(value, str) or not value:
        raise _shape(f"{name} must be a non-empty string", code)
def _shape(message: str, code: str) -> PolicyError:
    return PolicyError(message, code=code, stage="policy_construct")
__all__ = ["Policy", "PolicyAll", "PolicyAny", "PolicyError", "PolicyLineage", "PolicyLoweredRef", "PolicyNodeLineage", "PolicyOccurrence", "PolicyUnify"]
