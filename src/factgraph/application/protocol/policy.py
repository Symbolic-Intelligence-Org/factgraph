from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ErrorDTO
from .schema_runtime import FieldPath
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
class PolicyFieldNavigation:
    """One policy-owned identity-to-scalar-field lookup.

    This deliberately stores a structured direct semantic address and a schema
    path.  It is not a dotted-string parser and is not a Query bind/select
    target.  The compiler resolves its actual field predicate and type against
    the trusted address space and SchemaIndex.
    """

    base: SemanticPortAddress
    field: FieldPath

    def __post_init__(self) -> None:
        if not isinstance(self.base, SemanticPortAddress):
            raise _shape("PolicyFieldNavigation.base must be SemanticPortAddress", "INVALID_POLICY_NAVIGATION")
        if not isinstance(self.field, FieldPath):
            raise _shape("PolicyFieldNavigation.field must be FieldPath", "INVALID_POLICY_NAVIGATION")


PolicyComparisonOperand: TypeAlias = SemanticPortAddress | PolicyFieldNavigation


@dataclass(frozen=True)
class PolicyCompare:
    """A branch-total Policy comparison between two scalar operands.

    Constructor-level validation only establishes the structured syntax.  The
    exact endpoint, scalar domain, cardinality and native-engine compatibility
    are compiler responsibilities because they depend on the trusted runtime
    address space and schema.
    """

    op: Literal["eq", "ne", "gt", "ge", "lt", "le"]
    left: PolicyComparisonOperand
    right: PolicyComparisonOperand
    node_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.op not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise _shape("PolicyCompare.op is unsupported", "INVALID_POLICY_COMPARE")
        if not isinstance(self.left, (SemanticPortAddress, PolicyFieldNavigation)) or not isinstance(
            self.right, (SemanticPortAddress, PolicyFieldNavigation)
        ):
            raise _shape("PolicyCompare operands must be semantic addresses or field navigation", "INVALID_POLICY_COMPARE")
        left, right = self.left, self.right
        if self.op in {"eq", "ne"}:
            left, right = sorted((left, right), key=_comparison_operand_key)
            object.__setattr__(self, "left", left)
            object.__setattr__(self, "right", right)
        object.__setattr__(
            self,
            "node_id",
            _node_id(("compare", self.op, _comparison_operand_key(left), _comparison_operand_key(right))),
        )

    @classmethod
    def gt(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("gt", left, right)

    @classmethod
    def ge(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("ge", left, right)

    @classmethod
    def lt(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("lt", left, right)

    @classmethod
    def le(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("le", left, right)

    @classmethod
    def eq(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("eq", left, right)

    @classmethod
    def ne(cls, left: PolicyComparisonOperand, right: PolicyComparisonOperand) -> "PolicyCompare":
        return cls("ne", left, right)
@dataclass(frozen=True)
class PolicyAll:
    children: tuple[PolicyNode, ...]
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        children = _children(self.children, "ALL")
        if all(isinstance(child, (PolicyUnify, PolicyCompare)) for child in children):
            raise _shape("PolicyAll requires a structural child", "INVALID_POLICY_ALL")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "node_id", _node_id(("all", tuple(c.node_id for c in children))))
@dataclass(frozen=True)
class PolicyAny:
    children: tuple[PolicyExpression, ...]
    node_id: str = field(init=False)
    def __post_init__(self) -> None:
        children = _children(self.children, "ANY")
        if any(isinstance(child, (PolicyUnify, PolicyCompare)) for child in children):
            raise _shape("Policy constraints must be direct PolicyAll children", "INVALID_POLICY_CONSTRAINT_SCOPE")
        if any(not isinstance(child, (PolicyOccurrence, PolicyAll, PolicyAny)) for child in children):
            raise _shape("PolicyAny children must be structural", "INVALID_POLICY_ANY")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "node_id", _node_id(("any", tuple(c.node_id for c in children))))
PolicyExpression: TypeAlias = PolicyOccurrence | PolicyAll | PolicyAny
PolicyNode: TypeAlias = PolicyExpression | PolicyUnify | PolicyCompare
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
@dataclass(frozen=True)
class PolicyStructureNodeV0:
    node_id: str
    kind: Literal["occurrence", "all", "any", "unify"]
    child_node_ids: tuple[str, ...] = ()
    occurrence_alias: str | None = None
    left: SemanticPortAddress | None = None
    right: SemanticPortAddress | None = None
    def __post_init__(self) -> None:
        _text(self.node_id, "node_id", "INVALID_POLICY_STRUCTURE")
        if self.kind not in {"occurrence", "all", "any", "unify"}:
            raise _shape("invalid Policy structure node kind", "INVALID_POLICY_STRUCTURE")
        if not isinstance(self.child_node_ids, tuple) or not all(
            isinstance(item, str) and item for item in self.child_node_ids
        ):
            raise _shape("child_node_ids must be a string tuple", "INVALID_POLICY_STRUCTURE")
        expected = {
            "occurrence": (False, True, False, False),
            "all": (True, False, False, False),
            "any": (True, False, False, False),
            "unify": (False, False, True, True),
        }[self.kind]
        actual = (
            bool(self.child_node_ids), self.occurrence_alias is not None,
            self.left is not None, self.right is not None,
        )
        if actual != expected:
            raise _shape("Policy structure fields do not match node kind", "INVALID_POLICY_STRUCTURE")
        if self.occurrence_alias is not None:
            _text(self.occurrence_alias, "occurrence_alias", "INVALID_POLICY_STRUCTURE")
        if self.left is not None and not isinstance(self.left, SemanticPortAddress):
            raise _shape("left must be SemanticPortAddress", "INVALID_POLICY_STRUCTURE")
        if self.right is not None and not isinstance(self.right, SemanticPortAddress):
            raise _shape("right must be SemanticPortAddress", "INVALID_POLICY_STRUCTURE")
        if self.kind == "unify":
            assert self.left is not None and self.right is not None
            endpoints = (self.left, self.right)
            if self.left == self.right or endpoints != tuple(sorted(endpoints, key=_address_key)):
                raise _shape("Unify endpoints must be distinct and canonical", "INVALID_POLICY_STRUCTURE")
        expected_id = _structure_node_id(
            self.kind, self.child_node_ids, self.occurrence_alias, self.left, self.right,
        )
        if self.node_id != expected_id:
            raise _shape("Policy structure node_id does not match its content", "INVALID_POLICY_STRUCTURE")


@dataclass(frozen=True)
class PolicyCompareStructureNodeV0:
    """Persisted compare leaf kept separate from the legacy v0 structure DTO.

    Adding fields to ``PolicyStructureNodeV0`` would alter historical
    EvaluationRun seals through ``asdict``.  This independent DTO lets the
    structure container grow while retaining old serialized node shapes.
    """

    node_id: str
    op: Literal["eq", "ne", "gt", "ge", "lt", "le"]
    left: PolicyComparisonOperand
    right: PolicyComparisonOperand

    @property
    def kind(self) -> Literal["compare"]:
        return "compare"

    @property
    def child_node_ids(self) -> tuple[()]:
        return ()

    def __post_init__(self) -> None:
        if self.op not in {"eq", "ne", "gt", "ge", "lt", "le"}:
            raise _shape("Policy compare structure op is invalid", "INVALID_POLICY_STRUCTURE")
        if not isinstance(self.left, (SemanticPortAddress, PolicyFieldNavigation)) or not isinstance(
            self.right, (SemanticPortAddress, PolicyFieldNavigation)
        ):
            raise _shape("Policy compare structure operands are invalid", "INVALID_POLICY_STRUCTURE")
        left, right = self.left, self.right
        if self.op in {"eq", "ne"}:
            canonical = tuple(sorted((left, right), key=_comparison_operand_key))
            if (left, right) != canonical:
                raise _shape("symmetric compare structure operands must be canonical", "INVALID_POLICY_STRUCTURE")
        expected_id = _node_id(("compare", self.op, _comparison_operand_key(left), _comparison_operand_key(right)))
        if self.node_id != expected_id:
            raise _shape("Policy compare structure node_id does not match its content", "INVALID_POLICY_STRUCTURE")


PolicyStructureNode: TypeAlias = PolicyStructureNodeV0 | PolicyCompareStructureNodeV0
@dataclass(frozen=True)
class PolicyStructureV0:
    root_node_id: str
    nodes: tuple[PolicyStructureNode, ...]
    structure_digest: str = field(init=False)
    def __post_init__(self) -> None:
        _text(self.root_node_id, "root_node_id", "INVALID_POLICY_STRUCTURE")
        if not isinstance(self.nodes, tuple) or not self.nodes or not all(
            isinstance(node, (PolicyStructureNodeV0, PolicyCompareStructureNodeV0)) for node in self.nodes
        ):
            raise _shape("nodes must be a non-empty PolicyStructureNodeV0 tuple", "INVALID_POLICY_STRUCTURE")
        ordered = tuple(sorted(self.nodes, key=lambda node: node.node_id))
        if ordered != self.nodes or len({node.node_id for node in ordered}) != len(ordered):
            raise _shape("Policy structure nodes must be unique and canonically ordered", "INVALID_POLICY_STRUCTURE")
        by_id = {node.node_id: node for node in ordered}
        if self.root_node_id not in by_id:
            raise _shape("Policy structure root is absent", "INVALID_POLICY_STRUCTURE")
        if by_id[self.root_node_id].kind not in {"occurrence", "all", "any"}:
            raise _shape("Policy structure root must be structural", "INVALID_POLICY_STRUCTURE")
        for node in ordered:
            child_kinds = tuple(by_id[child].kind for child in node.child_node_ids if child in by_id)
            if node.kind == "any" and ({"unify", "compare"} & set(child_kinds)):
                raise _shape("PolicyAny cannot contain Policy constraints", "INVALID_POLICY_STRUCTURE")
            if node.kind == "all" and child_kinds and all(kind in {"unify", "compare"} for kind in child_kinds):
                raise _shape("PolicyAll requires a structural child", "INVALID_POLICY_STRUCTURE")
        child_counts = {
            child: sum(child in node.child_node_ids for node in ordered)
            for child in {item for node in ordered for item in node.child_node_ids}
        }
        if set(child_counts) - set(by_id):
            raise _shape("Policy structure child is absent", "INVALID_POLICY_STRUCTURE")
        if child_counts != {node_id: 1 for node_id in set(by_id) - {self.root_node_id}}:
            raise _shape("Policy structure must be one rooted tree", "INVALID_POLICY_STRUCTURE")
        reachable, pending = set[str](), [self.root_node_id]
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                raise _shape("Policy structure contains a cycle", "INVALID_POLICY_STRUCTURE")
            reachable.add(node_id)
            pending.extend(by_id[node_id].child_node_ids)
        if reachable != set(by_id):
            raise _shape("Policy structure contains unreachable nodes", "INVALID_POLICY_STRUCTURE")
        object.__setattr__(self, "structure_digest", _structure_digest(self.root_node_id, ordered))
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
class PolicyConditionLoweredRefV0:
    """One compiler-owned Policy condition in one lowered branch.

    Kept separate from ``PolicyLoweredRef`` so historical persisted lineage
    retains its exact DTO shape and seal.
    """

    branch_id: str
    policy_node_id: str
    condition_id: str
    role: Literal["left_field", "right_field", "compare"]
    lowered_index: int

    @property
    def kind(self) -> Literal["policy_condition"]:
        return "policy_condition"

    def __post_init__(self) -> None:
        for name in ("branch_id", "policy_node_id", "condition_id"):
            _text(getattr(self, name), name, "INVALID_POLICY_LINEAGE")
        if self.role not in {"left_field", "right_field", "compare"}:
            raise _shape("Policy condition role is invalid", "INVALID_POLICY_LINEAGE")
        if not isinstance(self.lowered_index, int) or isinstance(self.lowered_index, bool) or self.lowered_index < 0:
            raise _shape("Policy condition lowered_index must be a non-negative integer", "INVALID_POLICY_LINEAGE")


PolicyLineageRef: TypeAlias = PolicyLoweredRef | PolicyConditionLoweredRefV0
@dataclass(frozen=True)
class PolicyNodeLineage:
    node_id: str
    node_kind: Literal["occurrence", "all", "any", "unify", "compare"]
    lowered_refs: tuple[PolicyLineageRef, ...]
    def __post_init__(self) -> None:
        _text(self.node_id, "node_id", "INVALID_POLICY_LINEAGE")
        if self.node_kind not in {"occurrence", "all", "any", "unify", "compare"}:
            raise _shape("invalid lineage node kind", "INVALID_POLICY_LINEAGE")
        if not isinstance(self.lowered_refs, tuple) or not self.lowered_refs or not all(
            isinstance(ref, (PolicyLoweredRef, PolicyConditionLoweredRefV0)) for ref in self.lowered_refs
        ):
            raise _shape("lowered_refs must be a non-empty PolicyLoweredRef tuple", "INVALID_POLICY_LINEAGE")
        if len(set(self.lowered_refs)) != len(self.lowered_refs):
            raise _shape("lowered_refs must be unique", "INVALID_POLICY_LINEAGE")
@dataclass(frozen=True)
class PolicyLineage:
    authored_nodes: tuple[PolicyNodeLineage, ...]
    lowered_origins: tuple[tuple[PolicyLineageRef, tuple[str, ...]], ...]
    def __post_init__(self) -> None:
        if not isinstance(self.authored_nodes, tuple) or not self.authored_nodes or not all(isinstance(node, PolicyNodeLineage) for node in self.authored_nodes):
            raise _shape("authored_nodes must be a non-empty lineage tuple", "INVALID_POLICY_LINEAGE")
        node_ids = {node.node_id for node in self.authored_nodes}
        if len(node_ids) != len(self.authored_nodes) or not isinstance(self.lowered_origins, tuple) or not self.lowered_origins:
            raise _shape("lineage nodes and origins must be non-empty and unique", "INVALID_POLICY_LINEAGE")
        reverse: set[PolicyLineageRef] = set()
        for item in self.lowered_origins:
            if not isinstance(item, tuple) or len(item) != 2 or not isinstance(
                item[0], (PolicyLoweredRef, PolicyConditionLoweredRefV0)
            ):
                raise _shape("invalid lowered origin", "INVALID_POLICY_LINEAGE")
            ref, origins = item
            valid_origins = isinstance(origins, tuple) and origins and all(isinstance(origin, str) and origin for origin in origins)
            if ref in reverse or not valid_origins or len(set(origins)) != len(origins) or set(origins) - node_ids:
                raise _shape("lowered origins must be unique and reference authored nodes", "INVALID_POLICY_LINEAGE")
            reverse.add(ref)
        forward = {(ref, node.node_id) for node in self.authored_nodes for ref in node.lowered_refs}
        backward = {(ref, origin) for ref, origins in self.lowered_origins for origin in origins}
        if forward != backward:
            raise _shape("Policy lineage must be total in both directions", "INVALID_POLICY_LINEAGE")
def _children(value: object, kind: str) -> tuple[PolicyNode, ...]:
    allowed = (PolicyOccurrence, PolicyAll, PolicyAny, PolicyUnify, PolicyCompare)
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
def _structure_node_id(
    kind: str,
    child_node_ids: tuple[str, ...],
    occurrence_alias: str | None,
    left: SemanticPortAddress | None,
    right: SemanticPortAddress | None,
) -> str:
    if kind == "occurrence":
        return _node_id((kind, occurrence_alias))
    if kind in {"all", "any"}:
        if child_node_ids != tuple(sorted(set(child_node_ids))):
            raise _shape("structural child ids must be unique and canonical", "INVALID_POLICY_STRUCTURE")
        return _node_id((kind, child_node_ids))
    assert left is not None and right is not None
    left_key, right_key = sorted((_address_key(left), _address_key(right)))
    return _node_id((kind, left_key, right_key))
def _structure_digest(root_node_id: str, nodes: tuple[PolicyStructureNode, ...]) -> str:
    payload = {
        "format": "policy_structure_v0",
        "root_node_id": root_node_id,
        "nodes": [_structure_node_payload(node) for node in nodes],
    }
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()
    return sha256_hex(raw)
def _address_key(address: SemanticPortAddress) -> tuple[str, str]:
    return address.occurrence_alias, address.port_name


def _comparison_operand_key(value: PolicyComparisonOperand) -> tuple[object, ...]:
    if isinstance(value, SemanticPortAddress):
        return ("address", *_address_key(value))
    return (
        "navigation",
        *_address_key(value.base),
        value.field.entity_type,
        value.field.field_name,
    )


def _structure_node_payload(node: PolicyStructureNode) -> dict[str, object]:
    if isinstance(node, PolicyStructureNodeV0):
        # Preserve the legacy v0 payload exactly for historical structure seals.
        return {
            "node_id": node.node_id,
            "kind": node.kind,
            "child_node_ids": node.child_node_ids,
            "occurrence_alias": node.occurrence_alias,
            "left": None if node.left is None else _address_key(node.left),
            "right": None if node.right is None else _address_key(node.right),
        }
    return {
        "node_id": node.node_id,
        "kind": node.kind,
        "child_node_ids": (),
        "op": node.op,
        "left": _comparison_operand_key(node.left),
        "right": _comparison_operand_key(node.right),
    }
def _text(value: object, name: str, code: str = "INVALID_POLICY_SHAPE") -> None:
    if not isinstance(value, str) or not value:
        raise _shape(f"{name} must be a non-empty string", code)
def _shape(message: str, code: str) -> PolicyError:
    return PolicyError(message, code=code, stage="policy_construct")
__all__ = [
    "Policy", "PolicyAll", "PolicyAny", "PolicyCompare", "PolicyComparisonOperand",
    "PolicyCompareStructureNodeV0", "PolicyConditionLoweredRefV0", "PolicyError",
    "PolicyFieldNavigation", "PolicyLineage", "PolicyLineageRef", "PolicyLoweredRef",
    "PolicyNodeLineage", "PolicyOccurrence", "PolicyStructureNode", "PolicyStructureNodeV0",
    "PolicyStructureV0", "PolicyUnify",
]
