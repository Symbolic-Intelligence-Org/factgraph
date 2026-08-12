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


@dataclass(frozen=True)
class PolicyNodeLineage:
    node_id: str
    node_kind: Literal["occurrence", "all", "any", "unify"]
    lowered_refs: tuple[PolicyLoweredRef, ...]


@dataclass(frozen=True)
class PolicyLineage:
    authored_nodes: tuple[PolicyNodeLineage, ...]
    lowered_origins: tuple[tuple[PolicyLoweredRef, tuple[str, ...]], ...]


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


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise _shape(f"{name} must be a non-empty string", "INVALID_POLICY_SHAPE")


def _shape(message: str, code: str) -> PolicyError:
    return PolicyError(message, code=code, stage="policy_construct")


__all__ = ["Policy", "PolicyAll", "PolicyAny", "PolicyError", "PolicyLineage", "PolicyLoweredRef", "PolicyNodeLineage", "PolicyOccurrence", "PolicyUnify"]
