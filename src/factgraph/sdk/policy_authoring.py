"""Typed SDK façade for authored managed Policies.

This module deliberately owns only ergonomic authoring syntax.  It compiles
to the established application ``Policy`` / ``SemanticAddressSpace`` values
and never evaluates a Policy itself.  In particular, it is not the legacy
``sdk.dsl`` language and it does not introduce a Policy registry or a second
Query compiler.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast

from factgraph.application.protocol.policy import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyComparisonOperand,
    PolicyError,
    PolicyFieldNavigation,
    PolicyLiteral,
    PolicyNode,
    PolicyOccurrence,
    PolicyUnify,
)
from factgraph.application.protocol.schema_runtime import EntityRef, FieldPath
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import (
    EntityIdentityEndpoint,
    FieldEndpoint,
    FunctionValueEndpointV1,
)
from factgraph.application.schema_runtime import (
    SchemaResolutionError,
    encode_entity_ref,
    field_value_type,
    materialize_identity,
)
from factgraph.application.semantic_address_runtime import (
    ManagedRuleOccurrence,
    SemanticAddressResolutionError,
    SemanticAddressSpace,
    manage_rule_occurrence,
)
from factgraph.application.semantic_port_runtime import ResolvedRuleBundle

from .errors import SDKStoreError

if TYPE_CHECKING:
    from factgraph.application.schema_runtime import SchemaIndex

    from .store import SDKStore


class PolicyAuthoringError(SDKStoreError):
    """A typed rejection while using the ergonomic Policy authoring façade."""


_AuthoringNode: TypeAlias = PolicyOccurrence | PolicyAll | PolicyAny
_AuthoringConstraint: TypeAlias = PolicyUnify | PolicyCompare
_CompareOp: TypeAlias = Literal["eq", "ne", "gt", "ge", "lt", "le"]


@dataclass(frozen=True)
class AuthoredPolicyTargetV1:
    """One frozen SDK-authored Policy plus its exact occurrence namespace.

    This remains deliberately in-process.  Query target resolution still checks
    the underlying managed Rule contracts against the receiving graph's schema
    and is the sole compiler ingress.
    """

    policy: Policy
    address_space: SemanticAddressSpace
    _authoring_owner: object = field(default_factory=object, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not isinstance(self.policy, Policy):
            raise TypeError("AuthoredPolicyTargetV1.policy must be Policy")
        if not isinstance(self.address_space, SemanticAddressSpace):
            raise TypeError("AuthoredPolicyTargetV1.address_space must be SemanticAddressSpace")


class _PolicyHandle:
    """Shared owner and host-language trap behavior for symbolic SDK values."""

    __slots__ = ("_owner",)

    def __init__(self, owner: object) -> None:
        self._owner = owner

    def __hash__(self) -> int:
        raise TypeError("Policy symbolic values cannot be used as hash keys")

    def __bool__(self) -> bool:
        raise PolicyAuthoringError(
            "Policy symbolic values have no Python truth value; use draft.all(...) or draft.any(...)",
            code="POLICY_SYMBOLIC_BOOLEAN_UNSUPPORTED",
        )

    def _require_same_draft(self, other: object, *, label: str) -> _PolicyHandle:
        if not isinstance(other, _PolicyHandle) or other._owner is not self._owner:
            raise PolicyAuthoringError(
                f"{label} must use handles from the same Policy draft",
                code="POLICY_CROSS_DRAFT_HANDLE",
            )
        return other


class PolicyNodeHandle(_PolicyHandle):
    """A structural authored Policy node belonging to one draft."""

    __slots__ = ("_node",)
    __hash__ = _PolicyHandle.__hash__

    def __init__(self, owner: object, node: _AuthoringNode) -> None:
        super().__init__(owner)
        self._node = node

    def __eq__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "Policy nodes are symbolic; compose constraints with draft.same(...) or scalar comparisons",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )

    def __ne__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "Policy nodes are symbolic; compose constraints with draft.same(...) or scalar comparisons",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )


class PolicyConstraintHandle(_PolicyHandle):
    """One Policy-owned direct ``all`` constraint."""

    __slots__ = ("_node",)
    __hash__ = _PolicyHandle.__hash__

    def __init__(self, owner: object, node: _AuthoringConstraint) -> None:
        super().__init__(owner)
        self._node = node

    def __eq__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "Policy constraints are symbolic and cannot be compared as Python values",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )

    def __ne__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "Policy constraints are symbolic and cannot be compared as Python values",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )


class PolicyOccurrenceHandle(PolicyNodeHandle):
    """A named resolved Rule occurrence with typed semantic ports."""

    __slots__ = ("_managed", "_schema_index")

    def __init__(
        self,
        owner: object,
        managed: ManagedRuleOccurrence,
        schema_index: SchemaIndex,
    ) -> None:
        super().__init__(owner, PolicyOccurrence(managed.occurrence.alias))
        self._managed = managed
        self._schema_index = schema_index

    @property
    def alias(self) -> str:
        """Return this occurrence's Policy-local alias."""
        return self._managed.occurrence.alias

    def port(self, name: str) -> PolicyPortHandle:
        """Resolve one declared semantic port as an owner-bound handle.

        Args:
            name: Public semantic-port name on the resolved Rule contract.

        Returns:
            A typed entity or scalar port handle.

        Raises:
            PolicyAuthoringError: If the port is unknown or unsupported.
        """
        if not isinstance(name, str) or not name:
            raise PolicyAuthoringError(
                "Policy port name must be a non-empty string", code="POLICY_UNKNOWN_PORT"
            )
        declared = self._managed.contract.ports.get(name)
        if declared is None:
            raise PolicyAuthoringError(
                f"Policy occurrence {self.alias!r} has no semantic port {name!r}",
                code="POLICY_UNKNOWN_PORT",
            )
        address = SemanticPortAddress(self.alias, name)
        endpoint = declared.endpoint
        if isinstance(endpoint, EntityIdentityEndpoint):
            return PolicyEntityPortHandle(
                self._owner, address, endpoint.entity_type, self._schema_index
            )
        if isinstance(endpoint, FieldEndpoint):
            try:
                value_type = field_value_type(
                    self._schema_index, endpoint.path.entity_type, endpoint.path.field_name
                )
            except SchemaResolutionError as exc:
                raise PolicyAuthoringError(
                    f"Policy port {self.alias}.{name} no longer resolves in the schema",
                    code="POLICY_PORT_SCHEMA_MISMATCH",
                ) from exc
            if (
                value_type.value_kind != "scalar"
                or value_type.cardinality != "single"
                or value_type.scalar_domain is None
            ):
                raise PolicyAuthoringError(
                    f"Policy port {self.alias}.{name} is not a single scalar comparison port",
                    code="POLICY_UNSUPPORTED_PORT_ENDPOINT",
                )
            return PolicyScalarPortHandle(
                self._owner,
                address,
                value_type.scalar_domain,
            )
        if isinstance(endpoint, FunctionValueEndpointV1):
            return PolicyScalarPortHandle(self._owner, address, endpoint.scalar_domain)
        raise PolicyAuthoringError(
            f"Policy port {self.alias}.{name} has an unsupported semantic endpoint",
            code="POLICY_UNSUPPORTED_PORT_ENDPOINT",
        )

    def __getattr__(self, name: str) -> PolicyPortHandle:
        if not _is_safe_attribute_name(name):
            raise AttributeError(name)
        try:
            return self.port(name)
        except PolicyAuthoringError as exc:
            raise AttributeError(name) from exc


class PolicyPortHandle(_PolicyHandle):
    """Base class for direct structured semantic-port handles."""

    __slots__ = ("address",)
    __hash__ = _PolicyHandle.__hash__

    def __init__(self, owner: object, address: SemanticPortAddress) -> None:
        super().__init__(owner)
        self.address = address

    def __eq__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "entity ports require draft.same(left, right); scalar ports support ==",
            code="POLICY_ENTITY_COMPARISON_UNSUPPORTED",
        )

    def __ne__(self, other: object) -> Any:
        raise PolicyAuthoringError(
            "entity ports require draft.same(left, right); scalar ports support !=",
            code="POLICY_ENTITY_COMPARISON_UNSUPPORTED",
        )


class PolicyEntityPortHandle(PolicyPortHandle):
    """One entity-identity port that may navigate to an owned scalar field."""

    __slots__ = ("_schema_index", "entity_type")
    __hash__ = _PolicyHandle.__hash__

    def __init__(
        self,
        owner: object,
        address: SemanticPortAddress,
        entity_type: str,
        schema_index: SchemaIndex,
    ) -> None:
        super().__init__(owner, address)
        self.entity_type = entity_type
        self._schema_index = schema_index

    def __eq__(self, other: object) -> Any:
        return self._compare_entity_literal("eq", other)

    def __ne__(self, other: object) -> Any:
        return self._compare_entity_literal("ne", other)

    def _compare_entity_literal(
        self, op: Literal["eq", "ne"], other: object
    ) -> PolicyConstraintHandle:
        if not isinstance(other, EntityRef):
            raise PolicyAuthoringError(
                "entity ports require draft.same(left, right) or comparison with EntityRef",
                code="POLICY_ENTITY_COMPARISON_UNSUPPORTED",
            )
        if other.entity_type != self.entity_type:
            raise PolicyAuthoringError(
                "Policy entity literal type must match the entity port type",
                code="POLICY_ENTITY_LITERAL_TYPE_MISMATCH",
            )
        try:
            identity = materialize_identity(
                self.entity_type,
                other.identity,
                index=self._schema_index,
            )
            encoded = encode_entity_ref(
                EntityRef(self.entity_type, identity),
                index=self._schema_index,
            )
            literal = PolicyLiteral("entity_ref", encoded)
            return PolicyConstraintHandle(
                self._owner,
                PolicyCompare(op, self.address, literal),
            )
        except (PolicyError, SchemaResolutionError, TypeError, ValueError) as exc:
            code = getattr(exc, "code", "POLICY_ENTITY_LITERAL_INVALID")
            raise PolicyAuthoringError(
                f"Policy entity literal is invalid: {exc}",
                code=code,
            ) from exc

    def field(self, name: str) -> PolicyFieldHandle:
        """Navigate an entity port to one single scalar field.

        Args:
            name: Field name on the entity type.

        Returns:
            An owner-bound scalar field-navigation handle.

        Raises:
            PolicyAuthoringError: If the field is unknown or not a supported
                single scalar field.
        """
        if not isinstance(name, str) or not name:
            raise PolicyAuthoringError(
                "Policy field name must be a non-empty string", code="POLICY_INVALID_FIELD"
            )
        try:
            value_type = field_value_type(self._schema_index, self.entity_type, name)
        except SchemaResolutionError as exc:
            raise PolicyAuthoringError(
                f"Policy field {self.entity_type}.{name} is unknown",
                code="POLICY_UNKNOWN_FIELD",
            ) from exc
        if (
            value_type.value_kind != "scalar"
            or value_type.cardinality != "single"
            or value_type.scalar_domain is None
        ):
            raise PolicyAuthoringError(
                f"Policy field {self.entity_type}.{name} is not a single scalar comparison field",
                code="POLICY_UNSUPPORTED_FIELD_ENDPOINT",
            )
        return PolicyFieldHandle(
            self._owner,
            PolicyFieldNavigation(self.address, FieldPath(self.entity_type, name)),
            value_type.scalar_domain,
        )

    def __getattr__(self, name: str) -> PolicyFieldHandle:
        if not _is_safe_attribute_name(name):
            raise AttributeError(name)
        try:
            return self.field(name)
        except PolicyAuthoringError as exc:
            raise AttributeError(name) from exc


class _PolicyScalarHandle(PolicyPortHandle):
    """Shared rich comparison implementation for direct and navigated fields."""

    __slots__ = ("_operand", "scalar_domain")
    __hash__ = _PolicyHandle.__hash__

    def __init__(
        self,
        owner: object,
        address: SemanticPortAddress,
        operand: PolicyComparisonOperand,
        scalar_domain: str,
    ) -> None:
        super().__init__(owner, address)
        self._operand = operand
        self.scalar_domain = scalar_domain

    def __eq__(self, other: object) -> Any:
        return self._compare("eq", other)

    def __ne__(self, other: object) -> Any:
        return self._compare("ne", other)

    def __gt__(self, other: object) -> PolicyConstraintHandle:
        return self._compare("gt", other)

    def __ge__(self, other: object) -> PolicyConstraintHandle:
        return self._compare("ge", other)

    def __lt__(self, other: object) -> PolicyConstraintHandle:
        return self._compare("lt", other)

    def __le__(self, other: object) -> PolicyConstraintHandle:
        return self._compare("le", other)

    def _compare(self, op: _CompareOp, other: object) -> PolicyConstraintHandle:
        if op in {"gt", "ge", "lt", "le"} and self.scalar_domain not in {"int", "time"}:
            raise PolicyAuthoringError(
                f"Policy ordering is not supported for {self.scalar_domain}",
                code="POLICY_ORDERING_DOMAIN_UNSUPPORTED",
            )
        if isinstance(other, _PolicyScalarHandle):
            self._require_same_draft(other, label="Policy comparison")
            operand: PolicyComparisonOperand = other._operand
        elif isinstance(other, PolicyPortHandle):
            raise PolicyAuthoringError(
                "Policy comparison requires scalar ports or a supported canonical literal",
                code="POLICY_UNSUPPORTED_COMPARE_ENDPOINT",
            )
        elif isinstance(other, PolicyLiteral):
            if other.scalar_domain != self.scalar_domain:
                raise PolicyAuthoringError(
                    "Policy literal domain must match the scalar port domain",
                    code="POLICY_LITERAL_DOMAIN_MISMATCH",
                )
            operand = other
        else:
            if self.scalar_domain not in {"int", "time", "string", "bool"}:
                raise PolicyAuthoringError(
                    f"Policy literals are not supported for {self.scalar_domain}",
                    code="POLICY_LITERAL_DOMAIN_UNSUPPORTED",
                )
            expected_type = {
                "int": int,
                "time": int,
                "string": str,
                "bool": bool,
            }[self.scalar_domain]
            if type(other) is not expected_type:
                raise PolicyAuthoringError(
                    f"Policy literal does not match {self.scalar_domain}",
                    code="POLICY_LITERAL_TYPE_MISMATCH",
                )
            try:
                operand = PolicyLiteral(
                    cast(
                        Literal["int", "time", "string", "bool", "entity_ref"],
                        self.scalar_domain,
                    ),
                    cast(int | str | bool, other),
                )
            except (PolicyError, TypeError, ValueError) as exc:
                raise PolicyAuthoringError(
                    f"Policy literal is invalid for {self.scalar_domain}: {exc}",
                    code="POLICY_LITERAL_TYPE_MISMATCH",
                ) from exc
        try:
            return PolicyConstraintHandle(self._owner, PolicyCompare(op, self._operand, operand))
        except PolicyError as exc:
            raise PolicyAuthoringError(
                f"Policy comparison is invalid: {exc}", code=exc.code
            ) from exc


class PolicyScalarPortHandle(_PolicyScalarHandle):
    """A direct single-scalar semantic port."""

    __slots__ = ()

    def __init__(self, owner: object, address: SemanticPortAddress, scalar_domain: str) -> None:
        super().__init__(owner, address, address, scalar_domain)


class PolicyFieldHandle(_PolicyScalarHandle):
    """A Policy-owned one-hop entity-to-scalar-field navigation."""

    __slots__ = ()

    def __init__(
        self,
        owner: object,
        navigation: PolicyFieldNavigation,
        scalar_domain: str,
    ) -> None:
        super().__init__(owner, navigation.base, navigation, scalar_domain)

    @property
    def navigation(self) -> PolicyFieldNavigation:
        """Return the canonical Policy field-navigation operand."""
        assert isinstance(self._operand, PolicyFieldNavigation)
        return self._operand


class PolicyDraft:
    """Mutable authoring session that owns one future immutable Policy."""

    __slots__ = ("_graph", "_id", "_occurrences", "_owner", "_version")

    def __init__(self, graph: SDKStore, policy_id: str, *, version: str | None = None) -> None:
        if not isinstance(policy_id, str) or not policy_id:
            raise PolicyAuthoringError(
                "Policy id must be a non-empty string", code="POLICY_INVALID_ID"
            )
        if version is not None and (not isinstance(version, str) or not version):
            raise PolicyAuthoringError(
                "Policy version must be a non-empty string or None", code="POLICY_INVALID_VERSION"
            )
        self._graph = graph
        self._id = policy_id
        self._version = version
        self._owner = object()
        self._occurrences: dict[str, PolicyOccurrenceHandle] = {}

    @property
    def id(self) -> str:
        """Return the Policy identifier assigned to this draft."""
        return self._id

    @property
    def version(self) -> str | None:
        """Return the optional Policy version assigned to this draft."""
        return self._version

    def use(self, rule: ResolvedRuleBundle, *, as_: str) -> PolicyOccurrenceHandle:
        """Declare one resolved Rule occurrence in this Policy draft.

        Args:
            rule: Resolved Rule bundle compatible with this graph's schema.
            as_: Unique Policy-local occurrence alias.

        Returns:
            An owner-bound occurrence handle exposing typed semantic ports.

        Raises:
            PolicyAuthoringError: If the Rule, schema, or alias is invalid.

        Notes:
            This declares local topology; it does not register or execute the
            Rule and does not write to the ledger.
        """
        if not isinstance(rule, ResolvedRuleBundle):
            raise PolicyAuthoringError(
                "PolicyDraft.use(...) requires a resolved Rule bundle",
                code="POLICY_RESOLVED_RULE_REQUIRED",
            )
        if rule.contract.schema_digest != self._graph._application_schema_index.schema_digest:
            raise PolicyAuthoringError(
                "Policy occurrence Rule contract does not match this graph's schema",
                code="POLICY_SCHEMA_MISMATCH",
            )
        if as_ in self._occurrences:
            raise PolicyAuthoringError(
                f"Policy occurrence alias {as_!r} is already used",
                code="POLICY_DUPLICATE_OCCURRENCE_ALIAS",
            )
        try:
            managed = manage_rule_occurrence(rule, as_)
        except (SemanticAddressResolutionError, TypeError, ValueError) as exc:
            code = getattr(exc, "code", "POLICY_INVALID_OCCURRENCE_ALIAS")
            raise PolicyAuthoringError(f"Policy occurrence rejected: {exc}", code=code) from exc
        handle = PolicyOccurrenceHandle(self._owner, managed, self._graph._application_schema_index)
        self._occurrences[as_] = handle
        return handle

    def all(self, *items: PolicyNodeHandle | PolicyConstraintHandle) -> PolicyNodeHandle:
        """Compose structural nodes and constraints with logical conjunction.

        Args:
            *items: Owner-bound nodes or direct constraints from this draft.

        Returns:
            A structural handle preserving the authored ``All`` topology.

        Raises:
            PolicyAuthoringError: If the group is empty or crosses drafts.
        """
        nodes = self._owned_nodes(items, label="Policy all")
        try:
            return PolicyNodeHandle(self._owner, PolicyAll(nodes))
        except PolicyError as exc:
            raise PolicyAuthoringError(f"Policy all is invalid: {exc}", code=exc.code) from exc

    def any(self, *items: PolicyNodeHandle) -> PolicyNodeHandle:
        """Compose structural nodes with logical disjunction.

        Args:
            *items: Owner-bound structural nodes from this draft.

        Returns:
            A structural handle preserving the authored ``Any`` topology.

        Raises:
            PolicyAuthoringError: If the group is empty, crosses drafts, or
                contains a constraint outside an ``all`` group.
        """
        nodes: list[_AuthoringNode] = []
        for item in items:
            self._require_owned(item, label="Policy any")
            if not isinstance(item, PolicyNodeHandle):
                raise PolicyAuthoringError(
                    "Policy constraints must be direct draft.all(...) children, not draft.any(...) children",
                    code="POLICY_CONSTRAINT_SCOPE",
                )
            nodes.append(item._node)
        if not nodes:
            raise PolicyAuthoringError(
                "Policy any requires at least one child", code="POLICY_EMPTY_GROUP"
            )
        try:
            return PolicyNodeHandle(self._owner, PolicyAny(tuple(nodes)))
        except PolicyError as exc:
            raise PolicyAuthoringError(f"Policy any is invalid: {exc}", code=exc.code) from exc

    def same(
        self, left: PolicyEntityPortHandle, right: PolicyEntityPortHandle
    ) -> PolicyConstraintHandle:
        """Require two entity-identity ports to refer to the same entity.

        Args:
            left: First owner-bound entity port.
            right: Second owner-bound entity port.

        Returns:
            An identity-unification constraint for a containing ``all`` node.

        Raises:
            PolicyAuthoringError: If either endpoint is not an entity port or
                comes from another draft.
        """
        self._require_owned(left, label="Policy identity unification")
        self._require_owned(right, label="Policy identity unification")
        if not isinstance(left, PolicyEntityPortHandle) or not isinstance(
            right, PolicyEntityPortHandle
        ):
            raise PolicyAuthoringError(
                "draft.same(...) requires two entity identity ports",
                code="POLICY_UNIFY_ENDPOINT_UNSUPPORTED",
            )
        try:
            return PolicyConstraintHandle(self._owner, PolicyUnify(left.address, right.address))
        except PolicyError as exc:
            raise PolicyAuthoringError(
                f"Policy identity unification is invalid: {exc}", code=exc.code
            ) from exc

    def build(self, root: PolicyNodeHandle) -> AuthoredPolicyTargetV1:
        """Freeze the authored topology as a typed Query target.

        Args:
            root: Structural root containing every declared occurrence once.

        Returns:
            An immutable Policy plus its exact semantic address space.

        Raises:
            PolicyAuthoringError: If ownership, occurrence coverage, or
                address-space resolution is invalid.

        Notes:
            Building does not execute the Policy or write it to a registry.
        """
        self._require_owned(root, label="Policy root")
        if not isinstance(root, PolicyNodeHandle):
            raise PolicyAuthoringError(
                "Policy root must be a structural draft node", code="POLICY_INVALID_ROOT"
            )
        occurrences = _occurrence_alias_counts(root._node)
        declared = set(self._occurrences)
        if set(occurrences) != declared or any(count != 1 for count in occurrences.values()):
            raise PolicyAuthoringError(
                "Policy root must contain every declared occurrence exactly once",
                code="POLICY_OCCURRENCE_COVERAGE_MISMATCH",
            )
        try:
            space = SemanticAddressSpace(
                tuple(handle._managed for _alias, handle in sorted(self._occurrences.items()))
            )
            return AuthoredPolicyTargetV1(
                Policy(self._id, root._node, version=self._version),
                space,
                self._owner,
            )
        except (PolicyError, SemanticAddressResolutionError, TypeError, ValueError) as exc:
            code = getattr(exc, "code", "POLICY_BUILD_REJECTED")
            raise PolicyAuthoringError(f"Policy build rejected: {exc}", code=code) from exc

    def _owned_nodes(
        self,
        items: tuple[PolicyNodeHandle | PolicyConstraintHandle, ...],
        *,
        label: str,
    ) -> tuple[PolicyNode, ...]:
        if not items:
            raise PolicyAuthoringError(
                f"{label} requires at least one child", code="POLICY_EMPTY_GROUP"
            )
        result: list[PolicyNode] = []
        for item in items:
            self._require_owned(item, label=label)
            if isinstance(item, (PolicyNodeHandle, PolicyConstraintHandle)):
                result.append(item._node)
            else:  # pragma: no cover - _require_owned gives the public error.
                raise AssertionError("unreachable")  # noqa: TRY004 - Unreachable defensive branch; public rejection is PolicyAuthoringError.
        return tuple(result)

    def _require_owned(self, value: object, *, label: str) -> _PolicyHandle:
        if not isinstance(value, _PolicyHandle) or value._owner is not self._owner:
            raise PolicyAuthoringError(
                f"{label} must use values from this Policy draft",
                code="POLICY_CROSS_DRAFT_HANDLE",
            )
        return value


def policy_draft(graph: SDKStore, policy_id: str, *, version: str | None = None) -> PolicyDraft:
    """Build one SDK Policy draft owned by ``graph``'s trusted schema index."""

    return PolicyDraft(graph, policy_id, version=version)


def _is_safe_attribute_name(value: str) -> bool:
    return value.isidentifier() and not value.startswith("_")


def _occurrence_alias_counts(node: _AuthoringNode) -> Counter[str]:
    if isinstance(node, PolicyOccurrence):
        return Counter((node.alias,))
    result: Counter[str] = Counter()
    for child in node.children:
        if isinstance(child, (PolicyOccurrence, PolicyAll, PolicyAny)):
            result.update(_occurrence_alias_counts(child))
    return result


__all__ = [
    "AuthoredPolicyTargetV1",
    "PolicyAuthoringError",
    "PolicyConstraintHandle",
    "PolicyDraft",
    "PolicyEntityPortHandle",
    "PolicyFieldHandle",
    "PolicyNodeHandle",
    "PolicyOccurrenceHandle",
    "PolicyPortHandle",
    "PolicyScalarPortHandle",
    "policy_draft",
]
