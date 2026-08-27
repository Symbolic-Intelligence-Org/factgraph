from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
import json
import re
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms

from .common import ErrorDTO
from .schema_runtime import FieldPath
from .semantic_address import SemanticPortAddress

PolicyStage: TypeAlias = Literal[
    "policy_construct",
    "policy_admission",
    "policy_compile",
    "policy_lowering_adapter",
    "policy_compiler_invariant",
]

_WEIGHTED_CHOICE_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_WEIGHTED_CHOICE_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_POLICY_ENTITY_REF_RE = re.compile(
    r"idref_v1:[A-Za-z][A-Za-z0-9_.-]{0,127}:[a-z2-7]{52}\Z"
)
_MAX_WEIGHTED_CHOICE_ID_CHARS = 128
_MAX_WEIGHTED_CHOICE_KEY_PORTS = 8
_MAX_WEIGHTED_CHOICE_ARMS = 32
_MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS = 32
_MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE = 18


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
            code=self.code,
            message=str(self),
            path=self.path,
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
class PolicyFunctionOccurrenceV1:
    """Intrinsic V2-only marker for one Product Function occurrence.

    The marker deliberately survives ordinary ``Policy`` rewrapping.  Legacy
    compilation therefore cannot reinterpret a Function as a Rule.  The
    controlled Product V2 compiler bridge alone lowers it to the synthetic
    relation-backed occurrence with the same alias.
    """

    alias: str
    function_digest: str
    relation_predicate_id: str
    signature_digest: str
    input_bindings: tuple[tuple[str, SemanticPortAddress], ...]
    node_id: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.alias, "alias")
        _text(self.relation_predicate_id, "relation_predicate_id")
        for value, name in (
            (self.function_digest, "function_digest"),
            (self.signature_digest, "signature_digest"),
        ):
            if not isinstance(value, str) or not value.startswith("sha256:"):
                raise _shape(f"{name} must be a sha256 token", "INVALID_POLICY_FUNCTION")
        if not isinstance(self.input_bindings, tuple) or not self.input_bindings:
            raise _shape(
                "Function occurrence input bindings must be a non-empty tuple",
                "INVALID_POLICY_FUNCTION",
            )
        normalized: list[tuple[str, SemanticPortAddress]] = []
        for item in self.input_bindings:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0]
                or not isinstance(item[1], SemanticPortAddress)
            ):
                raise _shape(
                    "Function occurrence input binding is malformed",
                    "INVALID_POLICY_FUNCTION",
                )
            normalized.append(item)
        bindings = tuple(sorted(normalized, key=lambda item: item[0]))
        if len({name for name, _address in bindings}) != len(bindings):
            raise _shape(
                "Function occurrence input bindings must have unique ports",
                "INVALID_POLICY_FUNCTION",
            )
        object.__setattr__(self, "input_bindings", bindings)
        object.__setattr__(
            self,
            "node_id",
            _node_id(
                (
                    "function_occurrence_v1",
                    self.alias,
                    self.function_digest,
                    self.relation_predicate_id,
                    self.signature_digest,
                    tuple(
                        (name, address.occurrence_alias, address.port_name)
                        for name, address in bindings
                    ),
                )
            ),
        )


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
        object.__setattr__(
            self, "node_id", _node_id(("unify", _address_key(left), _address_key(right)))
        )


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
            raise _shape(
                "PolicyFieldNavigation.base must be SemanticPortAddress",
                "INVALID_POLICY_NAVIGATION",
            )
        if not isinstance(self.field, FieldPath):
            raise _shape(
                "PolicyFieldNavigation.field must be FieldPath", "INVALID_POLICY_NAVIGATION"
            )


@dataclass(frozen=True)
class PolicyLiteral:
    """One canonical scalar literal admissible in a managed Policy comparison.

    Ordering remains limited to the domains the native, Souffle, and ProbLog
    profile share: signed-int64 ``int`` and epoch-nanosecond ``time``.
    Equality additionally admits canonical ``string``, ``bool``, and encoded
    ``entity_ref`` values. It is typed here rather than inferred from a Python
    value so a literal's Policy identity stays stable before compiler admission
    resolves its peer endpoint.
    """

    scalar_domain: Literal["int", "time", "string", "bool", "entity_ref"]
    value: int | str | bool

    def __post_init__(self) -> None:
        if self.scalar_domain not in {"int", "time", "string", "bool", "entity_ref"}:
            raise _shape(
                "PolicyLiteral.scalar_domain is unsupported", "INVALID_POLICY_LITERAL"
            )
        expected_type = {
            "int": int,
            "time": int,
            "string": str,
            "bool": bool,
            "entity_ref": str,
        }[self.scalar_domain]
        if type(self.value) is not expected_type:
            raise _shape(
                "PolicyLiteral.value does not match its domain",
                "INVALID_POLICY_LITERAL",
            )
        if self.scalar_domain == "entity_ref":
            assert isinstance(self.value, str)  # Exact-type check above.
            if not _POLICY_ENTITY_REF_RE.fullmatch(self.value):
                raise _shape(
                    "PolicyLiteral entity_ref must be a canonical idref_v1 token",
                    "INVALID_POLICY_LITERAL",
                )
        try:
            normalized = claim_args_from_rest_terms([(self.scalar_domain, self.value)])[0][1]
        except (TypeError, ValueError) as exc:
            raise _shape(
                "PolicyLiteral.value is invalid for its domain",
                "INVALID_POLICY_LITERAL",
            ) from exc
        if type(normalized) is not expected_type or normalized != self.value:
            raise _shape("PolicyLiteral.value is not canonical", "INVALID_POLICY_LITERAL")
        object.__setattr__(self, "value", normalized)


PolicyComparisonOperand: TypeAlias = SemanticPortAddress | PolicyFieldNavigation | PolicyLiteral


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
        if not isinstance(
            self.left, (SemanticPortAddress, PolicyFieldNavigation, PolicyLiteral)
        ) or not isinstance(
            self.right, (SemanticPortAddress, PolicyFieldNavigation, PolicyLiteral)
        ):
            raise _shape(
                "PolicyCompare operands must be semantic addresses, field navigation, or PolicyLiteral",
                "INVALID_POLICY_COMPARE",
            )
        if isinstance(self.left, PolicyLiteral) and isinstance(self.right, PolicyLiteral):
            raise _shape(
                "PolicyCompare requires at least one semantic address or field navigation operand",
                "INVALID_POLICY_COMPARE",
            )
        left, right = self.left, self.right
        if self.op in {"eq", "ne"}:
            left, right = sorted((left, right), key=_comparison_operand_key)
            object.__setattr__(self, "left", left)
            object.__setattr__(self, "right", right)
        object.__setattr__(
            self,
            "node_id",
            _node_id(
                ("compare", self.op, _comparison_operand_key(left), _comparison_operand_key(right))
            ),
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
            raise _shape(
                "Policy constraints must be direct PolicyAll children",
                "INVALID_POLICY_CONSTRAINT_SCOPE",
            )
        if any(
            not isinstance(
                child,
                (
                    PolicyOccurrence,
                    PolicyFunctionOccurrenceV1,
                    PolicyAll,
                    PolicyAny,
                    PolicyWeightedChoice,
                ),
            )
            for child in children
        ):
            raise _shape("PolicyAny children must be structural", "INVALID_POLICY_ANY")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "node_id", _node_id(("any", tuple(c.node_id for c in children))))


@dataclass(frozen=True)
class PolicyWeightedChoiceArm:
    """One authored arm of an exclusive V2-only Policy choice.

    The exact canonical weight and condition are part of the structural AST,
    rather than an SDK-only sidecar.  Rewrapping a ``Policy`` therefore cannot
    silently downgrade a categorical choice into deterministic ``PolicyAny``.
    """

    arm_id: str
    probability: str
    condition: "PolicyExpression"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.arm_id, str)
            or len(self.arm_id) > _MAX_WEIGHTED_CHOICE_ID_CHARS
            or not _WEIGHTED_CHOICE_ID_RE.fullmatch(self.arm_id)
        ):
            raise _shape("WeightedChoice arm id is invalid", "INVALID_POLICY_WEIGHTED_CHOICE")
        object.__setattr__(
            self, "probability", _canonical_weighted_choice_probability(self.probability)
        )
        if not isinstance(
            self.condition, (PolicyOccurrence, PolicyFunctionOccurrenceV1, PolicyAll, PolicyAny)
        ):
            raise _shape(
                "WeightedChoice arm condition must be a structural Policy expression",
                "INVALID_POLICY_WEIGHTED_CHOICE",
            )

    @property
    def condition_node_id(self) -> str:
        return self.condition.node_id


@dataclass(frozen=True)
class PolicyWeightedChoice:
    """Intrinsic exclusive categorical Policy expression, executable only in V2.

    It preserves all authored business semantics necessary to refuse legacy
    execution: choice identity, direct selection key, canonical arm weights,
    and arm conditions.  The controlled V2 bridge may derive a temporary
    ``PolicyAny`` skeleton for the established typed compiler, but that
    skeleton is not the public authored AST.
    """

    choice_id: str
    selection_key: tuple[SemanticPortAddress, ...]
    arms: tuple[PolicyWeightedChoiceArm, ...]
    kind: Literal["exclusive"] = "exclusive"
    node_id: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.choice_id, str)
            or len(self.choice_id) > _MAX_WEIGHTED_CHOICE_ID_CHARS
            or not _WEIGHTED_CHOICE_ID_RE.fullmatch(self.choice_id)
        ):
            raise _shape("WeightedChoice id is invalid", "INVALID_POLICY_WEIGHTED_CHOICE")
        if self.kind != "exclusive":
            raise _shape(
                "only exclusive WeightedChoice is supported", "INVALID_POLICY_WEIGHTED_CHOICE"
            )
        if (
            not isinstance(self.selection_key, tuple)
            or not self.selection_key
            or len(self.selection_key) > _MAX_WEIGHTED_CHOICE_KEY_PORTS
            or not all(isinstance(item, SemanticPortAddress) for item in self.selection_key)
            or len(set(self.selection_key)) != len(self.selection_key)
        ):
            raise _shape(
                "WeightedChoice selection key must be a bounded, non-empty direct-address tuple",
                "INVALID_POLICY_WEIGHTED_CHOICE",
            )
        if (
            not isinstance(self.arms, tuple)
            or not self.arms
            or len(self.arms) > _MAX_WEIGHTED_CHOICE_ARMS
            or not all(isinstance(item, PolicyWeightedChoiceArm) for item in self.arms)
        ):
            raise _shape("WeightedChoice arms are invalid", "INVALID_POLICY_WEIGHTED_CHOICE")
        arms = tuple(sorted(self.arms, key=lambda item: item.arm_id))
        if len({item.arm_id for item in arms}) != len(arms):
            raise _shape("WeightedChoice arm ids must be unique", "INVALID_POLICY_WEIGHTED_CHOICE")
        if len({item.condition_node_id for item in arms}) != len(arms):
            raise _shape(
                "WeightedChoice arm conditions must be unique",
                "INVALID_POLICY_WEIGHTED_CHOICE",
            )
        with localcontext() as context:
            context.prec = 128
            total = sum((Decimal(item.probability) for item in arms), Decimal("0"))
        if total != Decimal("1"):
            raise _shape(
                "exclusive WeightedChoice probabilities must sum exactly to 1",
                "INVALID_POLICY_WEIGHTED_CHOICE",
            )
        object.__setattr__(self, "arms", arms)
        object.__setattr__(
            self,
            "node_id",
            _node_id(
                (
                    "weighted_choice",
                    self.choice_id,
                    tuple(_address_key(item) for item in self.selection_key),
                    tuple((item.arm_id, item.probability, item.condition_node_id) for item in arms),
                    self.kind,
                )
            ),
        )

    @property
    def children(self) -> tuple["PolicyExpression", ...]:
        """Arm conditions for generic structural traversal only."""

        return tuple(item.condition for item in self.arms)


PolicyExpression: TypeAlias = (
    PolicyOccurrence | PolicyFunctionOccurrenceV1 | PolicyAll | PolicyAny | PolicyWeightedChoice
)
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
        if not isinstance(
            self.when,
            (
                PolicyOccurrence,
                PolicyFunctionOccurrenceV1,
                PolicyAll,
                PolicyAny,
                PolicyWeightedChoice,
            ),
        ):
            raise _shape("Policy.when must be structural", "INVALID_POLICY_ROOT")


@dataclass(frozen=True)
class PolicyV2Only(Policy):
    """Defense-in-depth marker for a Policy that must not enter legacy execution.

    ``PolicyWeightedChoice`` is the durable source-of-truth boundary: it
    survives ordinary Policy rewrapping.  Product authoring retains this
    marker as a second early-rejection signal for the exact wrapper it returns.
    A controlled private V2 bridge alone derives a temporary plain skeleton
    while retaining the original Product target for identity and lowering.
    """

    execution_boundary: Literal["v2_only"] = field(default="v2_only", init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()


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
            bool(self.child_node_ids),
            self.occurrence_alias is not None,
            self.left is not None,
            self.right is not None,
        )
        if actual != expected:
            raise _shape(
                "Policy structure fields do not match node kind", "INVALID_POLICY_STRUCTURE"
            )
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
                raise _shape(
                    "Unify endpoints must be distinct and canonical", "INVALID_POLICY_STRUCTURE"
                )
        expected_id = _structure_node_id(
            self.kind,
            self.child_node_ids,
            self.occurrence_alias,
            self.left,
            self.right,
        )
        if self.node_id != expected_id:
            raise _shape(
                "Policy structure node_id does not match its content", "INVALID_POLICY_STRUCTURE"
            )


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
        if not isinstance(
            self.left, (SemanticPortAddress, PolicyFieldNavigation, PolicyLiteral)
        ) or not isinstance(
            self.right, (SemanticPortAddress, PolicyFieldNavigation, PolicyLiteral)
        ):
            raise _shape(
                "Policy compare structure operands are invalid", "INVALID_POLICY_STRUCTURE"
            )
        if isinstance(self.left, PolicyLiteral) and isinstance(self.right, PolicyLiteral):
            raise _shape(
                "Policy compare structure requires a semantic operand", "INVALID_POLICY_STRUCTURE"
            )
        left, right = self.left, self.right
        if self.op in {"eq", "ne"}:
            canonical = tuple(sorted((left, right), key=_comparison_operand_key))
            if (left, right) != canonical:
                raise _shape(
                    "symmetric compare structure operands must be canonical",
                    "INVALID_POLICY_STRUCTURE",
                )
        expected_id = _node_id(
            ("compare", self.op, _comparison_operand_key(left), _comparison_operand_key(right))
        )
        if self.node_id != expected_id:
            raise _shape(
                "Policy compare structure node_id does not match its content",
                "INVALID_POLICY_STRUCTURE",
            )


PolicyStructureNode: TypeAlias = PolicyStructureNodeV0 | PolicyCompareStructureNodeV0


@dataclass(frozen=True)
class PolicyStructureV0:
    root_node_id: str
    nodes: tuple[PolicyStructureNode, ...]
    structure_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.root_node_id, "root_node_id", "INVALID_POLICY_STRUCTURE")
        if (
            not isinstance(self.nodes, tuple)
            or not self.nodes
            or not all(
                isinstance(node, (PolicyStructureNodeV0, PolicyCompareStructureNodeV0))
                for node in self.nodes
            )
        ):
            raise _shape(
                "nodes must be a non-empty PolicyStructureNodeV0 tuple", "INVALID_POLICY_STRUCTURE"
            )
        ordered = tuple(sorted(self.nodes, key=lambda node: node.node_id))
        if ordered != self.nodes or len({node.node_id for node in ordered}) != len(ordered):
            raise _shape(
                "Policy structure nodes must be unique and canonically ordered",
                "INVALID_POLICY_STRUCTURE",
            )
        by_id = {node.node_id: node for node in ordered}
        if self.root_node_id not in by_id:
            raise _shape("Policy structure root is absent", "INVALID_POLICY_STRUCTURE")
        if by_id[self.root_node_id].kind not in {"occurrence", "all", "any"}:
            raise _shape("Policy structure root must be structural", "INVALID_POLICY_STRUCTURE")
        for node in ordered:
            child_kinds = tuple(
                by_id[child].kind for child in node.child_node_ids if child in by_id
            )
            if node.kind == "any" and ({"unify", "compare"} & set(child_kinds)):
                raise _shape(
                    "PolicyAny cannot contain Policy constraints", "INVALID_POLICY_STRUCTURE"
                )
            if (
                node.kind == "all"
                and child_kinds
                and all(kind in {"unify", "compare"} for kind in child_kinds)
            ):
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
            self.occurrence_alias,
            self.port_name,
            self.source_index,
            self.lowered_index,
            self.peer_occurrence_alias,
            self.peer_port_name,
        )
        _text(self.branch_id, "branch_id", "INVALID_POLICY_LINEAGE")
        if (
            self.kind not in shapes
            or tuple(value is not None for value in values) != shapes[self.kind]
        ):
            raise _shape("lowered reference fields do not match kind", "INVALID_POLICY_LINEAGE")
        for name in ("occurrence_alias", "port_name", "peer_occurrence_alias", "peer_port_name"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name, "INVALID_POLICY_LINEAGE")
        for name in ("source_index", "lowered_index"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
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
        if (
            not isinstance(self.lowered_index, int)
            or isinstance(self.lowered_index, bool)
            or self.lowered_index < 0
        ):
            raise _shape(
                "Policy condition lowered_index must be a non-negative integer",
                "INVALID_POLICY_LINEAGE",
            )


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
        if (
            not isinstance(self.lowered_refs, tuple)
            or not self.lowered_refs
            or not all(
                isinstance(ref, (PolicyLoweredRef, PolicyConditionLoweredRefV0))
                for ref in self.lowered_refs
            )
        ):
            raise _shape(
                "lowered_refs must be a non-empty PolicyLoweredRef tuple", "INVALID_POLICY_LINEAGE"
            )
        if len(set(self.lowered_refs)) != len(self.lowered_refs):
            raise _shape("lowered_refs must be unique", "INVALID_POLICY_LINEAGE")


@dataclass(frozen=True)
class PolicyLineage:
    authored_nodes: tuple[PolicyNodeLineage, ...]
    lowered_origins: tuple[tuple[PolicyLineageRef, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.authored_nodes, tuple)
            or not self.authored_nodes
            or not all(isinstance(node, PolicyNodeLineage) for node in self.authored_nodes)
        ):
            raise _shape(
                "authored_nodes must be a non-empty lineage tuple", "INVALID_POLICY_LINEAGE"
            )
        node_ids = {node.node_id for node in self.authored_nodes}
        if (
            len(node_ids) != len(self.authored_nodes)
            or not isinstance(self.lowered_origins, tuple)
            or not self.lowered_origins
        ):
            raise _shape(
                "lineage nodes and origins must be non-empty and unique", "INVALID_POLICY_LINEAGE"
            )
        reverse: set[PolicyLineageRef] = set()
        for item in self.lowered_origins:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], (PolicyLoweredRef, PolicyConditionLoweredRefV0))
            ):
                raise _shape("invalid lowered origin", "INVALID_POLICY_LINEAGE")
            ref, origins = item
            valid_origins = (
                isinstance(origins, tuple)
                and origins
                and all(isinstance(origin, str) and origin for origin in origins)
            )
            if (
                ref in reverse
                or not valid_origins
                or len(set(origins)) != len(origins)
                or set(origins) - node_ids
            ):
                raise _shape(
                    "lowered origins must be unique and reference authored nodes",
                    "INVALID_POLICY_LINEAGE",
                )
            reverse.add(ref)
        forward = {(ref, node.node_id) for node in self.authored_nodes for ref in node.lowered_refs}
        backward = {(ref, origin) for ref, origins in self.lowered_origins for origin in origins}
        if forward != backward:
            raise _shape(
                "Policy lineage must be total in both directions", "INVALID_POLICY_LINEAGE"
            )


def _children(value: object, kind: str) -> tuple[PolicyNode, ...]:
    allowed = (
        PolicyOccurrence,
        PolicyFunctionOccurrenceV1,
        PolicyAll,
        PolicyAny,
        PolicyWeightedChoice,
        PolicyUnify,
        PolicyCompare,
    )
    if not isinstance(value, tuple) or not value or any(not isinstance(x, allowed) for x in value):
        raise _shape(
            f"Policy{kind}.children must be a non-empty node tuple", f"INVALID_POLICY_{kind}"
        )
    by_id = {child.node_id: child for child in value}
    if len(by_id) != len(value):
        raise _shape("Policy children contain a duplicate node", "DUPLICATE_POLICY_NODE")
    return tuple(by_id[node_id] for node_id in sorted(by_id))


def _node_id(payload: tuple[object, ...]) -> str:
    raw = json.dumps(
        {"format": "policy_node_v0", "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return f"pn:{sha256_hex(raw)}"


def _canonical_weighted_choice_probability(value: object) -> str:
    """Accept the bounded decimal wire used by intrinsic choice arms."""

    if (
        type(value) is not str
        or not value
        or len(value) > _MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS
        or not _WEIGHTED_CHOICE_DECIMAL_RE.fullmatch(value)
        or ("." in value and value.endswith("0"))
        or len(value.partition(".")[2]) > _MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE
    ):
        raise _shape(
            "WeightedChoice probability must be a bounded canonical decimal string",
            "INVALID_POLICY_WEIGHTED_CHOICE",
        )
    try:
        numeric = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex guards parsing.
        raise _shape(
            "WeightedChoice probability is not a decimal",
            "INVALID_POLICY_WEIGHTED_CHOICE",
        ) from exc
    if not Decimal("0") < numeric <= Decimal("1"):
        raise _shape(
            "WeightedChoice probability must lie in (0, 1]",
            "INVALID_POLICY_WEIGHTED_CHOICE",
        )
    return value


def policy_contains_weighted_choice(value: object) -> bool:
    """Return whether a public Policy AST contains intrinsic V2-only choice."""

    if isinstance(value, Policy):
        return policy_contains_weighted_choice(value.when)
    if isinstance(value, PolicyWeightedChoice):
        return True
    if isinstance(value, (PolicyAll, PolicyAny)):
        return any(policy_contains_weighted_choice(item) for item in value.children)
    return False


def policy_contains_product_function(value: object) -> bool:
    """Return whether a Policy carries a V2-only Function occurrence."""

    if isinstance(value, Policy):
        return policy_contains_product_function(value.when)
    if isinstance(value, PolicyFunctionOccurrenceV1):
        return True
    if isinstance(value, (PolicyAll, PolicyAny, PolicyWeightedChoice)):
        return any(policy_contains_product_function(item) for item in value.children)
    return False


def _lower_policy_weighted_choices_to_any_skeleton(policy: Policy) -> Policy:
    """Create the V2-internal deterministic skeleton for typed compilation.

    This is not a legacy execution entrypoint.  Callers must retain the
    original ProductPolicy/WeightedChoice AST for identity, activation, and
    annotated-disjunction lowering checks.  It is intentionally pure and
    transient: no marker or sidecar information is written back to callers.
    """

    if not isinstance(policy, Policy):
        raise _shape(
            "WeightedChoice skeleton lowering requires Policy", "INVALID_POLICY_WEIGHTED_CHOICE"
        )

    def lower_expression(node: PolicyExpression) -> PolicyExpression:
        if isinstance(node, PolicyOccurrence):
            return node
        if isinstance(node, PolicyFunctionOccurrenceV1):
            return PolicyOccurrence(node.alias)
        if isinstance(node, PolicyWeightedChoice):
            return PolicyAny(tuple(lower_expression(item.condition) for item in node.arms))
        if isinstance(node, PolicyAny):
            lowered_children = tuple(lower_expression(item) for item in node.children)
            return PolicyAny(lowered_children)
        all_children: list[PolicyNode] = []
        for item in node.children:
            if isinstance(item, (PolicyUnify, PolicyCompare)):
                all_children.append(item)
            else:
                all_children.append(lower_expression(item))
        return PolicyAll(tuple(all_children))

    return Policy(policy.id, lower_expression(policy.when), policy.version)


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
            raise _shape(
                "structural child ids must be unique and canonical", "INVALID_POLICY_STRUCTURE"
            )
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
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return sha256_hex(raw)


def _address_key(address: SemanticPortAddress) -> tuple[str, str]:
    return address.occurrence_alias, address.port_name


def _comparison_operand_key(value: PolicyComparisonOperand) -> tuple[object, ...]:
    if isinstance(value, SemanticPortAddress):
        return ("address", *_address_key(value))
    if isinstance(value, PolicyLiteral):
        return ("literal", value.scalar_domain, value.value)
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
    "Policy",
    "PolicyAll",
    "PolicyAny",
    "PolicyCompare",
    "PolicyComparisonOperand",
    "PolicyV2Only",
    "PolicyWeightedChoice",
    "PolicyWeightedChoiceArm",
    "PolicyCompareStructureNodeV0",
    "PolicyConditionLoweredRefV0",
    "PolicyError",
    "PolicyFieldNavigation",
    "PolicyFunctionOccurrenceV1",
    "PolicyLineage",
    "PolicyLineageRef",
    "PolicyLiteral",
    "PolicyLoweredRef",
    "PolicyNodeLineage",
    "PolicyOccurrence",
    "PolicyStructureNode",
    "PolicyStructureNodeV0",
    "PolicyStructureV0",
    "PolicyUnify",
    "policy_contains_weighted_choice",
    "policy_contains_product_function",
]
