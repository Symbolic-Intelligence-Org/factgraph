from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
from itertools import product
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var

from .protocol.policy import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyComparisonOperand,
    PolicyCompareStructureNodeV0,
    PolicyConditionLoweredRefV0,
    PolicyError,
    PolicyExpression,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLineageRef,
    PolicyLiteral,
    PolicyLoweredRef,
    PolicyNode,
    PolicyNodeLineage,
    PolicyOccurrence,
    PolicyStage,
    PolicyStructureNode,
    PolicyStructureNodeV0,
    PolicyStructureV0,
    PolicyUnify,
    PolicyV2Only,
    policy_contains_weighted_choice,
)
from .protocol.rule import _PROJECTION_ID_PREFIX
from .protocol.rule_expr import (
    RuleExpr,
    RuleExprError,
    RuleJoinConstraint,
    _AndGroup,
    _RuleExpr,
    _canonical_join_constraint,
)
from .protocol.rule_expr_lowering import (
    RuleExprLoweringBranch,
    RuleExprPolicyCondition,
    _DNF_BRANCH_LIMIT,
    _RuleExprBodyPlan,
    _lower_rule_expr_body,
    _vars_in_atom,
)
from .protocol.semantic_address import SemanticPortAddress
from .protocol.semantic_port import EntityIdentityEndpoint, FieldEndpoint
from .schema_runtime import (
    SchemaIndex,
    SchemaResolutionError,
    field_predicate,
    field_value_type,
)
from .semantic_address_runtime import (
    ManagedRuleOccurrence,
    SemanticAddressResolutionError,
    SemanticAddressSpace,
)
from .semantic_port_runtime import SemanticPortResolutionError, assert_rule_contract_current

_CMP_OPS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
_ORDERING_DOMAINS = frozenset({"int", "time"})


@dataclass(frozen=True)
class _ResolvedPolicyOperand:
    """Compiler-only scalar operand after trusted semantic/schema resolution."""

    source_address: SemanticPortAddress | None
    scalar_domain: str
    lookup_predicate_id: str | None = None
    literal: PolicyLiteral | None = None

    def __post_init__(self) -> None:
        if (self.source_address is None) == (self.literal is None):
            raise ValueError("resolved Policy operand must be exactly one source or literal")
        if self.literal is not None and self.lookup_predicate_id is not None:
            raise ValueError("resolved Policy literal cannot require a field lookup")


@dataclass(frozen=True)
class _ResolvedPolicyCompare:
    compare: PolicyCompare
    left: _ResolvedPolicyOperand
    right: _ResolvedPolicyOperand


@dataclass(frozen=True)
class _PolicyBranchVariant:
    """One authored-policy DNF path before RuleExpr's execution lowering."""

    aliases: frozenset[str]
    active_node_ids: frozenset[str]
    compare_node_ids: frozenset[str]


@dataclass(frozen=True)
class PolicyRulePin:
    occurrence_alias: str
    rule_id: str
    rule_version: str | None
    rule_content_digest: str
    semantic_contract_digest: str

    def __post_init__(self) -> None:
        for name in (
            "occurrence_alias",
            "rule_id",
            "rule_content_digest",
            "semantic_contract_digest",
        ):
            _runtime_text(getattr(self, name), name)
        if self.rule_version is not None:
            _runtime_text(self.rule_version, "rule_version")


@dataclass(frozen=True)
class PolicyCompiledBranch:
    branch_id: str
    authored_occurrence_aliases: tuple[str, ...]
    lowered_occurrence_aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        _runtime_text(self.branch_id, "branch_id")
        for name in ("authored_occurrence_aliases", "lowered_occurrence_aliases"):
            value = getattr(self, name)
            if (
                not isinstance(value, tuple)
                or not value
                or not all(isinstance(alias, str) and alias for alias in value)
            ):
                raise ValueError(f"{name} must be a non-empty string tuple")
        if len(self.authored_occurrence_aliases) != len(self.lowered_occurrence_aliases):
            raise ValueError("authored and lowered occurrence inventories must align")


@dataclass(frozen=True)
class CompiledPolicyV0:
    policy_id: str
    policy_version: str | None
    policy_digest: str
    address_space_digest: str
    rule_pins: tuple[PolicyRulePin, ...]
    policy_structure: PolicyStructureV0
    rule_expr: _RuleExpr
    branches: tuple[PolicyCompiledBranch, ...]
    lineage: PolicyLineage
    _body_plan: _RuleExprBodyPlan = field(repr=False, compare=False)
    _policy_conditions: tuple[RuleExprPolicyCondition, ...] = field(
        default=(), repr=False, compare=False
    )

    def __post_init__(self) -> None:
        for name in ("policy_id", "policy_digest", "address_space_digest"):
            _runtime_text(getattr(self, name), name)
        if self.policy_version is not None:
            _runtime_text(self.policy_version, "policy_version")
        if (
            not isinstance(self.rule_pins, tuple)
            or not self.rule_pins
            or not all(isinstance(pin, PolicyRulePin) for pin in self.rule_pins)
        ):
            raise ValueError("rule_pins must be a non-empty PolicyRulePin tuple")
        if (
            not isinstance(self.branches, tuple)
            or not self.branches
            or not all(isinstance(branch, PolicyCompiledBranch) for branch in self.branches)
        ):
            raise ValueError("branches must be a non-empty PolicyCompiledBranch tuple")
        if (
            not isinstance(self.policy_structure, PolicyStructureV0)
            or not isinstance(self.rule_expr, _RuleExpr)
            or not isinstance(self.lineage, PolicyLineage)
            or not isinstance(self._body_plan, _RuleExprBodyPlan)
        ):
            raise ValueError("compiled Policy structure has invalid runtime types")
        if not isinstance(self._policy_conditions, tuple) or not all(
            isinstance(item, RuleExprPolicyCondition) for item in self._policy_conditions
        ):
            raise ValueError("compiled Policy conditions have invalid runtime types")
        _assert_compiled_policy_current(self)


def compile_policy(
    policy: Policy,
    *,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex | None = None,
) -> CompiledPolicyV0:
    if not isinstance(policy, Policy):
        raise _error("policy must be Policy", "INVALID_POLICY", "policy_compile", ("policy",))
    if isinstance(policy, PolicyV2Only) or policy_contains_weighted_choice(policy):
        raise _error(
            "this Policy contains V2-only WeightedChoice semantics and cannot be compiled as legacy deterministic Policy",
            "WEIGHTED_CHOICE_V2_ONLY",
            "policy_compile",
            ("policy",),
        )
    if not isinstance(address_space, SemanticAddressSpace):
        raise _error(
            "address_space must be SemanticAddressSpace",
            "INVALID_ADDRESS_SPACE",
            "policy_compile",
            ("address_space",),
        )

    nodes = _nodes(policy.when)
    managed = {item.occurrence.alias: item for item in address_space.occurrences}
    _validate_structure(nodes, managed)
    policy_structure = _policy_structure(policy.when, nodes)
    _admit(managed)
    compares = tuple(node for node in nodes if isinstance(node, PolicyCompare))
    if compares:
        if not isinstance(schema_index, SchemaIndex):
            raise _error(
                "Policy comparisons require the trusted SchemaIndex",
                "POLICY_SCHEMA_INDEX_REQUIRED",
                "policy_compile",
                ("schema_index",),
            )
        _validate_schema_index_for_space(schema_index, managed)
    branch_count = _branch_count(policy.when)
    if branch_count > _DNF_BRANCH_LIMIT:
        raise _error(
            f"Policy projects {branch_count} DNF branches; maximum is {_DNF_BRANCH_LIMIT}",
            "POLICY_DNF_BRANCH_LIMIT_EXCEEDED",
            "policy_compile",
            ("policy", "when"),
            {"limit": _DNF_BRANCH_LIMIT, "projected_count": branch_count},
        )

    joins: dict[str, RuleJoinConstraint] = {}
    resolved_compares: dict[str, _ResolvedPolicyCompare] = {}
    _validate_constraints(
        policy.when,
        address_space,
        schema_index,
        joins,
        resolved_compares,
    )
    try:
        rule_expr = _compile_expr(policy.when, managed, joins)
        body_plan = _lower_rule_expr_body(rule_expr)
        _validate_execution_var_ownership(body_plan, managed)
    except RuleExprError as exc:
        raise _error(
            f"RuleExpr rejected compiled Policy: {exc}",
            "POLICY_LOWERING_REJECTED",
            "policy_lowering_adapter",
            ("policy", "when"),
            {"cause_type": type(exc).__name__},
        ) from exc

    policy_conditions = _compile_policy_conditions(policy.when, body_plan, resolved_compares)
    branches, lineage = _lineage(
        policy.when,
        nodes,
        body_plan,
        managed,
        policy_conditions,
    )
    pins = tuple(
        PolicyRulePin(
            alias,
            item.occurrence.rule.id,
            item.occurrence.rule.version,
            item.occurrence.rule.content_digest,
            item.contract.semantic_contract_digest,
        )
        for alias, item in sorted(managed.items())
    )
    policy_digest = _digest(
        policy.id,
        policy.version,
        address_space.address_space_digest,
        pins,
        policy_structure,
        rule_expr,
        branches,
        lineage,
        policy_conditions,
    )
    return CompiledPolicyV0(
        policy.id,
        policy.version,
        policy_digest,
        address_space.address_space_digest,
        pins,
        policy_structure,
        rule_expr,
        branches,
        lineage,
        body_plan,
        policy_conditions,
    )


def _validate_structure(
    nodes: tuple[PolicyNode, ...], managed: dict[str, ManagedRuleOccurrence]
) -> None:
    aliases = [node.alias for node in nodes if isinstance(node, PolicyOccurrence)]
    duplicates = sorted(alias for alias, count in Counter(aliases).items() if count > 1)
    if duplicates:
        raise _error(
            "each occurrence alias must appear once",
            "DUPLICATE_POLICY_OCCURRENCE",
            "policy_compile",
            ("policy", "when"),
            {"aliases": duplicates},
        )
    authored, supplied = set(aliases), set(managed)
    if authored != supplied:
        raise _error(
            "Policy aliases must exactly match the address space",
            "POLICY_OCCURRENCE_COVERAGE_MISMATCH",
            "policy_compile",
            ("address_space", "occurrences"),
            {"missing": sorted(authored - supplied), "extra": sorted(supplied - authored)},
        )
    duplicate_nodes = sorted(
        node_id for node_id, count in Counter(node.node_id for node in nodes).items() if count > 1
    )
    if duplicate_nodes:
        raise _error(
            "Policy contains duplicate canonical nodes",
            "DUPLICATE_POLICY_NODE",
            "policy_compile",
            ("policy", "when"),
            {"node_ids": duplicate_nodes},
        )


def _validate_execution_var_ownership(
    plan: _RuleExprBodyPlan,
    managed: dict[str, ManagedRuleOccurrence],
) -> None:
    occurrence_map = {binding.alias: binding for binding in plan.occurrence_map}
    for branch in plan.branches:
        offset, owners = 0, dict[str, str]()
        for lowered_alias in branch.occurrence_aliases:
            binding = occurrence_map[lowered_alias]
            authored_alias = binding.authored_alias or lowered_alias
            atom_count = len(managed[authored_alias].occurrence.rule.when)
            for atom in branch.body_atoms[offset : offset + atom_count]:
                for variable in _vars_in_atom(atom):
                    owner = owners.setdefault(variable.name, lowered_alias)
                    if owner != lowered_alias:
                        raise _error(
                            "distinct Policy occurrences lower to the same execution variable",
                            "POLICY_EXECUTION_VAR_COLLISION",
                            "policy_lowering_adapter",
                            ("policy", "when", branch.branch_id),
                            {
                                "variable": variable.name,
                                "occurrence_aliases": sorted((owner, lowered_alias)),
                            },
                        )
            offset += atom_count
        if offset != len(branch.body_atoms):
            raise _invariant("lowered atoms do not match occurrence Rule bodies", branch.branch_id)


def _admit(managed: dict[str, ManagedRuleOccurrence]) -> None:
    schema_digests = {item.contract.schema_digest for item in managed.values()}
    if len(schema_digests) != 1:
        raise _error(
            "all occurrences must use one schema digest",
            "POLICY_SCHEMA_MISMATCH",
            "policy_admission",
            ("address_space", "occurrences"),
            {"schema_digests": sorted(schema_digests)},
        )
    for alias, item in sorted(managed.items()):
        rule = item.occurrence.rule
        try:
            assert_rule_contract_current(rule, item.contract)
        except SemanticPortResolutionError as exc:
            raise _error(
                "managed occurrence is stale",
                "MANAGED_OCCURRENCE_NOT_CURRENT",
                "policy_admission",
                ("address_space", alias),
                {"semantic_port_code": exc.code},
            ) from exc
        if rule.id.startswith(_PROJECTION_ID_PREFIX):
            raise _error(
                f"Rule id {rule.id!r} uses a compiler-reserved namespace",
                "RESERVED_COMPILER_NAMESPACE",
                "policy_admission",
                ("address_space", alias, "rule", "id"),
                {"reserved_prefix": _PROJECTION_ID_PREFIX},
            )
        for index, atom in enumerate(rule.when):
            supported_pred = isinstance(atom, PredAtom) and all(
                isinstance(term, (Var, Const)) for term in atom.terms
            )
            supported_cmp = (
                isinstance(atom, CmpAtom)
                and atom.op in _CMP_OPS
                and isinstance(atom.lhs, (Var, Const))
                and isinstance(atom.rhs, (Var, Const))
            )
            if not supported_pred and not supported_cmp:
                raise _error(
                    f"Rule {rule.id!r} uses unsupported body atom {type(atom).__name__}",
                    "UNSUPPORTED_MANAGED_RULE_CAPABILITY",
                    "policy_admission",
                    ("address_space", alias, "rule", "when", str(index)),
                    {"atom_kind": type(atom).__name__},
                )


def _validate_constraints(
    node: PolicyExpression,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex | None,
    joins: dict[str, RuleJoinConstraint],
    compares: dict[str, _ResolvedPolicyCompare],
) -> None:
    """Resolve only branch-total constraints; structural lowering stays pure.

    A constraint is owned by its immediate ``PolicyAll``.  This keeps an inner
    ``Any(All(..., Compare(...)), other)`` comparison local to the first branch
    instead of accidentally applying it merely because some aliases are shared
    by both descendants.
    """

    if isinstance(node, PolicyOccurrence):
        return
    if isinstance(node, PolicyAny):
        for child in node.children:
            _validate_constraints(child, address_space, schema_index, joins, compares)
        return

    guaranteed = _guaranteed_aliases(node)
    for item in node.children:
        if isinstance(item, PolicyUnify):
            required = {item.left.occurrence_alias, item.right.occurrence_alias}
            if not required <= guaranteed:
                _raise_partial_constraint(item.node_id, required, guaranteed)
            joins[item.node_id] = _resolve_unify(item, address_space)
            continue
        if isinstance(item, PolicyCompare):
            required = _compare_aliases(item)
            if not required <= guaranteed:
                _raise_partial_constraint(item.node_id, required, guaranteed)
            assert schema_index is not None  # checked at the top-level for any Compare
            compares[item.node_id] = _resolve_compare(item, address_space, schema_index)
            continue
        _validate_constraints(item, address_space, schema_index, joins, compares)


def _raise_partial_constraint(
    node_id: str,
    required: set[str],
    guaranteed: frozenset[str],
) -> None:
    raise _error(
        "Policy constraint endpoints are absent from a local Any branch",
        "PARTIAL_BRANCH_CONSTRAINT",
        "policy_compile",
        ("policy", "when", node_id),
        {"not_guaranteed_aliases": sorted(required - guaranteed)},
    )


def _validate_schema_index_for_space(
    schema_index: SchemaIndex,
    managed: dict[str, ManagedRuleOccurrence],
) -> None:
    schema_digests = {item.contract.schema_digest for item in managed.values()}
    if schema_digests != {schema_index.schema_digest}:
        raise _error(
            "Policy comparison SchemaIndex does not match managed Rule contracts",
            "POLICY_SCHEMA_MISMATCH",
            "policy_admission",
            ("schema_index",),
            {"schema_digests": sorted(schema_digests), "provided": schema_index.schema_digest},
        )


def _compare_aliases(compare: PolicyCompare) -> set[str]:
    aliases: set[str] = set()
    for operand in (compare.left, compare.right):
        if isinstance(operand, PolicyLiteral):
            continue
        aliases.add(
            operand.base.occurrence_alias
            if isinstance(operand, PolicyFieldNavigation)
            else operand.occurrence_alias
        )
    return aliases


def _resolve_compare(
    compare: PolicyCompare,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex,
) -> _ResolvedPolicyCompare:
    path = ("policy", "when", compare.node_id)
    left = _resolve_compare_operand(compare.left, address_space, schema_index, path=(*path, "left"))
    right = _resolve_compare_operand(
        compare.right, address_space, schema_index, path=(*path, "right")
    )
    if left.scalar_domain != right.scalar_domain:
        raise _error(
            "Policy comparison operands must have the same scalar domain",
            "INCOMPATIBLE_POLICY_COMPARE_DOMAIN",
            "policy_compile",
            path,
            {"left": left.scalar_domain, "right": right.scalar_domain},
        )
    if compare.op in {"gt", "ge", "lt", "le"} and left.scalar_domain not in _ORDERING_DOMAINS:
        raise _error(
            "Policy ordering comparison requires int or time scalar operands",
            "UNSUPPORTED_POLICY_COMPARE_ORDERING",
            "policy_compile",
            path,
            {"scalar_domain": left.scalar_domain},
        )
    return _ResolvedPolicyCompare(compare, left, right)


def _resolve_compare_operand(
    operand: PolicyComparisonOperand,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex,
    *,
    path: tuple[str, ...],
) -> _ResolvedPolicyOperand:
    if isinstance(operand, PolicyLiteral):
        return _ResolvedPolicyOperand(
            source_address=None,
            scalar_domain=operand.scalar_domain,
            literal=operand,
        )

    if isinstance(operand, SemanticPortAddress):
        try:
            resolved = address_space.resolve(operand)
        except SemanticAddressResolutionError as exc:
            raise _error(
                str(exc),
                "UNRESOLVED_SEMANTIC_ADDRESS",
                "policy_compile",
                path,
                {"semantic_address_code": exc.code},
            ) from exc
        if not isinstance(resolved.endpoint, FieldEndpoint):
            raise _error(
                "Policy comparison direct operands must resolve to scalar Field ports",
                "UNSUPPORTED_POLICY_COMPARE_ENDPOINT",
                "policy_compile",
                path,
            )
        return _resolved_scalar_field(
            operand,
            resolved.endpoint.path.entity_type,
            resolved.endpoint.path.field_name,
            schema_index,
            path=path,
            lookup_predicate_id=None,
        )

    assert isinstance(operand, PolicyFieldNavigation)
    try:
        base = address_space.resolve(operand.base)
    except SemanticAddressResolutionError as exc:
        raise _error(
            str(exc),
            "UNRESOLVED_SEMANTIC_ADDRESS",
            "policy_compile",
            path,
            {"semantic_address_code": exc.code},
        ) from exc
    if not isinstance(base.endpoint, EntityIdentityEndpoint):
        raise _error(
            "Policy field navigation must start at an EntityIdentity port",
            "INVALID_POLICY_NAVIGATION",
            "policy_compile",
            path,
        )
    if base.endpoint.entity_type != operand.field.entity_type:
        raise _error(
            "Policy field navigation must stay on the identity endpoint entity type",
            "INVALID_POLICY_NAVIGATION",
            "policy_compile",
            path,
            {
                "base_entity_type": base.endpoint.entity_type,
                "field_entity_type": operand.field.entity_type,
            },
        )
    return _resolved_scalar_field(
        operand.base,
        operand.field.entity_type,
        operand.field.field_name,
        schema_index,
        path=path,
        lookup_predicate_id="required",
    )


def _resolved_scalar_field(
    source_address: SemanticPortAddress,
    entity_type: str,
    field_name: str,
    schema_index: SchemaIndex,
    *,
    path: tuple[str, ...],
    lookup_predicate_id: str | None,
) -> _ResolvedPolicyOperand:
    try:
        info = field_predicate(schema_index, entity_type, field_name)
        value_type = field_value_type(schema_index, entity_type, field_name)
    except SchemaResolutionError as exc:
        raise _error(
            str(exc),
            "INVALID_POLICY_NAVIGATION"
            if lookup_predicate_id is not None
            else "UNSUPPORTED_POLICY_COMPARE_ENDPOINT",
            "policy_compile",
            path,
            {"schema_code": exc.code},
        ) from exc
    if (
        value_type.value_kind != "scalar"
        or value_type.cardinality != "single"
        or value_type.scalar_domain is None
    ):
        raise _error(
            "Policy comparison operands must be single scalar fields",
            "UNSUPPORTED_POLICY_COMPARE_ENDPOINT",
            "policy_compile",
            path,
            {"value_kind": value_type.value_kind, "cardinality": value_type.cardinality},
        )
    return _ResolvedPolicyOperand(
        source_address,
        value_type.scalar_domain,
        info.pred_id if lookup_predicate_id is not None else None,
    )


def _resolve_unify(unify: PolicyUnify, address_space: SemanticAddressSpace) -> RuleJoinConstraint:
    path = ("policy", "when", unify.node_id)
    if unify.left.occurrence_alias == unify.right.occurrence_alias:
        raise _error(
            "Unify must connect distinct occurrences",
            "SELF_UNIFY_UNSUPPORTED",
            "policy_compile",
            path,
        )
    try:
        left, right = address_space.resolve(unify.left), address_space.resolve(unify.right)
    except SemanticAddressResolutionError as exc:
        raise _error(
            str(exc),
            "UNRESOLVED_SEMANTIC_ADDRESS",
            "policy_compile",
            path,
            {"semantic_address_code": exc.code},
        ) from exc
    if left.endpoint != right.endpoint:
        raise _error(
            "Unify endpoints must resolve to the same semantic endpoint",
            "INCOMPATIBLE_UNIFY_ENDPOINTS",
            "policy_compile",
            path,
        )
    try:
        return left.execution_ref.eq(right.execution_ref)
    except RuleExprError as exc:
        raise _error(str(exc), "INVALID_UNIFY", "policy_compile", path) from exc


def _compile_expr(
    node: PolicyExpression,
    managed: dict[str, ManagedRuleOccurrence],
    joins: dict[str, RuleJoinConstraint],
) -> _RuleExpr:
    if isinstance(node, PolicyOccurrence):
        return RuleExpr.all(managed[node.alias].occurrence)
    structural = tuple(
        child for child in node.children if not isinstance(child, (PolicyUnify, PolicyCompare))
    )
    children = tuple(_compile_expr(child, managed, joins) for child in structural)
    if isinstance(node, PolicyAny):
        return RuleExpr.any(*children)
    compiled = RuleExpr.all(*children)
    constraints = tuple(
        joins[child.node_id] for child in node.children if isinstance(child, PolicyUnify)
    )
    if constraints:
        if not isinstance(compiled, _AndGroup):
            raise _error(
                "All did not compile to AND",
                "POLICY_COMPILER_INVARIANT",
                "policy_compiler_invariant",
            )
        compiled = compiled.join(*constraints)
    return compiled


def _branch_count(node: PolicyExpression) -> int:
    if isinstance(node, PolicyOccurrence):
        return 1
    children = tuple(
        child for child in node.children if not isinstance(child, (PolicyUnify, PolicyCompare))
    )
    counts = tuple(_branch_count(child) for child in children)
    if isinstance(node, PolicyAny):
        return sum(counts)
    result = 1
    for count in counts:
        result *= count
    return result


def _guaranteed_aliases(node: PolicyExpression) -> frozenset[str]:
    if isinstance(node, PolicyOccurrence):
        return frozenset((node.alias,))
    structural = tuple(
        child for child in node.children if not isinstance(child, (PolicyUnify, PolicyCompare))
    )
    if isinstance(node, PolicyAny):
        return frozenset.intersection(*map(_guaranteed_aliases, structural))
    return frozenset().union(*map(_guaranteed_aliases, structural))


def _occurrence_aliases(node: PolicyNode) -> frozenset[str]:
    if isinstance(node, PolicyOccurrence):
        return frozenset((node.alias,))
    if isinstance(node, PolicyUnify):
        return frozenset()
    if isinstance(node, PolicyCompare):
        return frozenset(_compare_aliases(node))
    return frozenset().union(*map(_occurrence_aliases, node.children))


def _nodes(node: PolicyNode) -> tuple[PolicyNode, ...]:
    if isinstance(node, (PolicyOccurrence, PolicyUnify, PolicyCompare)):
        return (node,)
    return (node, *(nested for child in node.children for nested in _nodes(child)))


def _policy_structure(
    root: PolicyExpression,
    nodes: tuple[PolicyNode, ...],
) -> PolicyStructureV0:
    result: list[PolicyStructureNode] = []
    for node in nodes:
        value: PolicyStructureNode
        if isinstance(node, PolicyOccurrence):
            value = PolicyStructureNodeV0(
                node.node_id,
                "occurrence",
                occurrence_alias=node.alias,
            )
        elif isinstance(node, PolicyUnify):
            value = PolicyStructureNodeV0(
                node.node_id,
                "unify",
                left=node.left,
                right=node.right,
            )
        elif isinstance(node, PolicyCompare):
            value = PolicyCompareStructureNodeV0(
                node.node_id,
                node.op,
                node.left,
                node.right,
            )
        else:
            value = PolicyStructureNodeV0(
                node.node_id,
                "all" if isinstance(node, PolicyAll) else "any",
                tuple(child.node_id for child in node.children),
            )
        result.append(value)
    return PolicyStructureV0(root.node_id, tuple(sorted(result, key=lambda item: item.node_id)))


def _compile_policy_conditions(
    root: PolicyExpression,
    plan: _RuleExprBodyPlan,
    resolved_compares: dict[str, _ResolvedPolicyCompare],
) -> tuple[RuleExprPolicyCondition, ...]:
    """Emit private lookup/compare atoms after the authored Rule bodies.

    ``_RuleExprBodyPlan`` intentionally remains a pure representation of Rule
    occurrences.  This separate immutable segment is injected only when the
    Query projection head is attached, which preserves old RuleExpr semantics
    and gives evidence an explicit ownership boundary.
    """

    if not resolved_compares:
        return ()
    variants = _policy_branch_variants(root)
    branch_to_variant = _match_variants_to_lowered_branches(variants, plan)
    emitted: list[RuleExprPolicyCondition] = []
    for branch in plan.branches:
        variant = branch_to_variant[branch.branch_id]
        occupied = {variable.name for atom in branch.body_atoms for variable in _vars_in_atom(atom)}
        for compare_id in sorted(variant.compare_node_ids):
            resolved = resolved_compares.get(compare_id)
            if resolved is None:
                raise _invariant(
                    "authored Compare has no resolved condition", branch.branch_id, compare_id
                )
            left, left_conditions = _materialize_policy_operand(
                branch,
                plan,
                resolved.compare.node_id,
                "left",
                resolved.left,
                occupied,
            )
            right, right_conditions = _materialize_policy_operand(
                branch,
                plan,
                resolved.compare.node_id,
                "right",
                resolved.right,
                occupied,
            )
            emitted.extend(left_conditions)
            emitted.extend(right_conditions)
            emitted.append(
                RuleExprPolicyCondition(
                    branch.branch_id,
                    resolved.compare.node_id,
                    "compare",
                    "compare",
                    CmpAtom(resolved.compare.op, left, right),
                )
            )
    return tuple(sorted(emitted, key=_policy_condition_sort_key))


def _materialize_policy_operand(
    branch: RuleExprLoweringBranch,
    plan: _RuleExprBodyPlan,
    compare_node_id: str,
    side: Literal["left", "right"],
    operand: _ResolvedPolicyOperand,
    occupied: set[str],
) -> tuple[Var | Const, tuple[RuleExprPolicyCondition, ...]]:
    if operand.literal is not None:
        return Const(operand.literal.value), ()
    assert operand.source_address is not None  # _ResolvedPolicyOperand invariant.
    source = _branch_execution_var(
        plan,
        branch.branch_id,
        branch.occurrence_aliases,
        operand.source_address,
    )
    if operand.lookup_predicate_id is None:
        return source, ()
    generated = _fresh_policy_condition_var(compare_node_id, branch.branch_id, side, occupied)
    role: Literal["left_field", "right_field"] = "left_field" if side == "left" else "right_field"
    return generated, (
        RuleExprPolicyCondition(
            branch.branch_id,
            compare_node_id,
            f"{side}_field",
            role,
            PredAtom(operand.lookup_predicate_id, [source, generated]),
        ),
    )


def _branch_execution_var(
    plan: _RuleExprBodyPlan,
    branch_id: str,
    lowered_aliases: tuple[str, ...],
    address: SemanticPortAddress,
) -> Var:
    by_alias = {binding.alias: binding for binding in plan.occurrence_map}
    matches: list[object] = []
    for lowered_alias in lowered_aliases:
        occurrence = by_alias.get(lowered_alias)
        if occurrence is None:
            raise _invariant("lowered occurrence is absent from occurrence map", branch_id)
        authored_alias = occurrence.authored_alias or lowered_alias
        if authored_alias != address.occurrence_alias:
            continue
        matches.extend(
            binding
            for binding in occurrence.port_bindings
            if binding.port_name == address.port_name
        )
    if len(matches) != 1:
        raise _invariant(
            "Policy comparison address does not have exactly one branch execution var",
            branch_id,
            address.occurrence_alias,
            address.port_name,
        )
    match = matches[0]
    if not hasattr(match, "alias_local_execution_var") or not isinstance(
        match.alias_local_execution_var, Var
    ):
        raise _invariant("Policy comparison execution var is malformed", branch_id)
    return match.alias_local_execution_var


def _fresh_policy_condition_var(
    compare_node_id: str,
    branch_id: str,
    side: str,
    occupied: set[str],
) -> Var:
    stem = f"$__policy_condition__{compare_node_id[3:19]}__{branch_id}__{side}"
    candidate = stem
    suffix = 1
    while candidate in occupied:
        candidate = f"{stem}_{suffix}"
        suffix += 1
    occupied.add(candidate)
    return Var(candidate)


def _policy_branch_variants(node: PolicyExpression) -> tuple[_PolicyBranchVariant, ...]:
    if isinstance(node, PolicyOccurrence):
        return (
            _PolicyBranchVariant(frozenset((node.alias,)), frozenset((node.node_id,)), frozenset()),
        )
    if isinstance(node, PolicyAny):
        any_variants: list[_PolicyBranchVariant] = []
        for child in node.children:
            for variant in _policy_branch_variants(child):
                any_variants.append(
                    _PolicyBranchVariant(
                        variant.aliases,
                        variant.active_node_ids | frozenset((node.node_id,)),
                        variant.compare_node_ids,
                    )
                )
        return tuple(any_variants)

    structural = tuple(
        child for child in node.children if not isinstance(child, (PolicyUnify, PolicyCompare))
    )
    constraints = tuple(
        child for child in node.children if isinstance(child, (PolicyUnify, PolicyCompare))
    )
    all_variants: list[_PolicyBranchVariant] = []
    for parts in product(*(_policy_branch_variants(child) for child in structural)):
        aliases = frozenset().union(*(part.aliases for part in parts))
        active = frozenset(
            (node.node_id, *(constraint.node_id for constraint in constraints))
        ).union(*(part.active_node_ids for part in parts))
        compare_ids = frozenset(
            constraint.node_id
            for constraint in constraints
            if isinstance(constraint, PolicyCompare)
        ).union(*(part.compare_node_ids for part in parts))
        all_variants.append(_PolicyBranchVariant(aliases, active, compare_ids))
    return tuple(all_variants)


def _match_variants_to_lowered_branches(
    variants: tuple[_PolicyBranchVariant, ...],
    plan: _RuleExprBodyPlan,
) -> dict[str, _PolicyBranchVariant]:
    buckets: dict[frozenset[str], list[_PolicyBranchVariant]] = {}
    for variant in variants:
        buckets.setdefault(variant.aliases, []).append(variant)
    result: dict[str, _PolicyBranchVariant] = {}
    by_alias = {binding.alias: binding for binding in plan.occurrence_map}
    for branch in plan.branches:
        aliases = frozenset(
            by_alias[alias].authored_alias or alias for alias in branch.occurrence_aliases
        )
        candidates = buckets.get(aliases, [])
        if len(candidates) != 1:
            raise _invariant(
                "authored Policy branches do not map uniquely to lowered branches", branch.branch_id
            )
        result[branch.branch_id] = candidates[0]
    if len(result) != len(plan.branches) or len(variants) != len(plan.branches):
        raise _invariant("authored Policy branch count does not match lowered branches")
    return result


def _lineage(
    root: PolicyExpression,
    nodes: tuple[PolicyNode, ...],
    plan: _RuleExprBodyPlan,
    managed: dict[str, ManagedRuleOccurrence],
    policy_conditions: tuple[RuleExprPolicyCondition, ...],
) -> tuple[tuple[PolicyCompiledBranch, ...], PolicyLineage]:
    bindings = {binding.alias: binding for binding in plan.occurrence_map}
    authored = {alias: binding.authored_alias or alias for alias, binding in bindings.items()}
    refs: dict[str, set[PolicyLineageRef]] = {node.node_id: set() for node in nodes}
    occurrence_nodes = {node.alias: node for node in nodes if isinstance(node, PolicyOccurrence)}
    unify_nodes = {
        _unify_key(node.left, node.right): node for node in nodes if isinstance(node, PolicyUnify)
    }
    branch_to_variant = _match_variants_to_lowered_branches(_policy_branch_variants(root), plan)
    conditions_by_branch: dict[str, tuple[RuleExprPolicyCondition, ...]] = {
        branch.branch_id: tuple(
            condition for condition in policy_conditions if condition.branch_id == branch.branch_id
        )
        for branch in plan.branches
    }
    branches: list[PolicyCompiledBranch] = []
    universe: set[PolicyLineageRef] = set()

    for branch in plan.branches:
        authored_aliases = tuple(authored[alias] for alias in branch.occurrence_aliases)
        variant = branch_to_variant[branch.branch_id]
        branch_ref = PolicyLoweredRef("branch", branch.branch_id)
        universe.add(branch_ref)
        for node_id in variant.active_node_ids:
            # A Compare owns concrete condition refs rather than a coarse
            # branch ref.  Giving it both would blur whether its own predicate
            # was materialized and makes the EvidenceTree unable to distinguish
            # a failed comparison from a branch that was merely considered.
            if node_id in variant.compare_node_ids:
                continue
            refs[node_id].add(branch_ref)

        body_index = 0
        for lowered_alias in branch.occurrence_aliases:
            source_alias = authored[lowered_alias]
            occurrence_node = occurrence_nodes[source_alias]
            occurrence_ref = PolicyLoweredRef("occurrence", branch.branch_id, lowered_alias)
            refs[occurrence_node.node_id].add(occurrence_ref)
            universe.add(occurrence_ref)
            for source_index, _atom in enumerate(managed[source_alias].occurrence.rule.when):
                atom_ref = PolicyLoweredRef(
                    "body_atom",
                    branch.branch_id,
                    lowered_alias,
                    source_index=source_index,
                    lowered_index=body_index,
                )
                refs[occurrence_node.node_id].add(atom_ref)
                universe.add(atom_ref)
                body_index += 1
        if body_index != len(branch.body_atoms):
            raise _invariant("lowered atoms do not match occurrence Rule bodies", branch.branch_id)

        for ordinal, condition in enumerate(conditions_by_branch[branch.branch_id]):
            if condition.policy_node_id not in variant.compare_node_ids:
                raise _invariant(
                    "Policy condition is outside its authored branch", branch.branch_id
                )
            condition_ref = PolicyConditionLoweredRefV0(
                branch.branch_id,
                condition.policy_node_id,
                condition.condition_id,
                condition.role,
                body_index + ordinal,
            )
            refs[condition.policy_node_id].add(condition_ref)
            universe.add(condition_ref)

        unique = {_canonical_join_constraint(join): join for join in branch.pending_joins}
        for ordinal, key in enumerate(sorted(unique, key=repr)):
            join = unique[key]
            left = SemanticPortAddress(authored[join.left.occurrence_alias], join.left.port_name)
            right = SemanticPortAddress(authored[join.right.occurrence_alias], join.right.port_name)
            source = unify_nodes.get(_unify_key(left, right))
            if source is None:
                raise _invariant("lowered Unify has no authored origin", branch.branch_id)
            unify_ref = PolicyLoweredRef(
                "unify",
                branch.branch_id,
                join.left.occurrence_alias,
                join.left.port_name,
                lowered_index=ordinal,
                peer_occurrence_alias=join.right.occurrence_alias,
                peer_port_name=join.right.port_name,
            )
            refs[source.node_id].add(unify_ref)
            universe.add(unify_ref)
        branches.append(
            PolicyCompiledBranch(branch.branch_id, authored_aliases, branch.occurrence_aliases)
        )

    forward: list[PolicyNodeLineage] = []
    reverse: dict[PolicyLineageRef, set[str]] = {}
    for node in sorted(nodes, key=lambda item: item.node_id):
        targets = tuple(sorted(refs[node.node_id], key=_lineage_ref_sort_key))
        if not targets:
            raise _invariant("authored node has no lowered target", node.node_id)
        forward.append(PolicyNodeLineage(node.node_id, _kind(node), targets))
        for target in targets:
            reverse.setdefault(target, set()).add(node.node_id)
    if set(reverse) != universe:
        raise _invariant("lowered structure has an orphan lineage reference")
    origins = tuple(
        (target, tuple(sorted(reverse[target])))
        for target in sorted(reverse, key=_lineage_ref_sort_key)
    )
    return tuple(branches), PolicyLineage(tuple(forward), origins)


def _policy_condition_sort_key(condition: RuleExprPolicyCondition) -> tuple[object, ...]:
    order = {"left_field": 0, "right_field": 1, "compare": 2}
    return (
        condition.branch_id,
        condition.policy_node_id,
        order[condition.role],
        condition.condition_id,
    )


def _lineage_ref_sort_key(ref: PolicyLineageRef) -> tuple[object, ...]:
    if isinstance(ref, PolicyLoweredRef):
        return (
            "legacy",
            ref.kind,
            ref.branch_id,
            ref.occurrence_alias or "",
            ref.port_name or "",
            -1 if ref.source_index is None else ref.source_index,
            -1 if ref.lowered_index is None else ref.lowered_index,
            ref.peer_occurrence_alias or "",
            ref.peer_port_name or "",
        )
    return (
        "condition",
        ref.branch_id,
        ref.policy_node_id,
        ref.lowered_index,
        ref.role,
        ref.condition_id,
    )


def _kind(node: PolicyNode) -> Literal["occurrence", "all", "any", "unify", "compare"]:
    if isinstance(node, PolicyOccurrence):
        return "occurrence"
    if isinstance(node, PolicyAll):
        return "all"
    if isinstance(node, PolicyAny):
        return "any"
    if isinstance(node, PolicyUnify):
        return "unify"
    return "compare"


def _unify_key(
    left: SemanticPortAddress,
    right: SemanticPortAddress,
) -> tuple[tuple[str, str], tuple[str, str]]:
    ends = sorted(
        ((left.occurrence_alias, left.port_name), (right.occurrence_alias, right.port_name))
    )
    return ends[0], ends[1]


def _assert_compiled_policy_current(compiled: CompiledPolicyV0) -> None:
    try:
        current_body = _lower_rule_expr_body(compiled.rule_expr)
    except Exception as exc:
        raise _error(
            "compiled Policy RuleExpr no longer lowers",
            "COMPILED_POLICY_INTEGRITY_MISMATCH",
            "policy_compiler_invariant",
            details={"cause_type": type(exc).__name__},
        ) from exc
    bindings = {item.alias: item for item in current_body.occurrence_map}
    expected_branches = tuple(
        PolicyCompiledBranch(
            branch.branch_id,
            tuple((bindings[alias].authored_alias or alias) for alias in branch.occurrence_aliases),
            branch.occurrence_aliases,
        )
        for branch in current_body.branches
    )
    expected_digest = _digest(
        compiled.policy_id,
        compiled.policy_version,
        compiled.address_space_digest,
        compiled.rule_pins,
        compiled.policy_structure,
        compiled.rule_expr,
        compiled.branches,
        compiled.lineage,
        compiled._policy_conditions,
    )
    structure_kinds = {node.node_id: node.kind for node in compiled.policy_structure.nodes}
    lineage_kinds = {node.node_id: node.node_kind for node in compiled.lineage.authored_nodes}
    conditions_current = _policy_conditions_current(compiled, current_body)
    if (
        current_body != compiled._body_plan
        or expected_branches != compiled.branches
        or structure_kinds != lineage_kinds
        or not conditions_current
        or expected_digest != compiled.policy_digest
    ):
        raise _error(
            "compiled Policy structure does not match its integrity seal",
            "COMPILED_POLICY_INTEGRITY_MISMATCH",
            "policy_compiler_invariant",
        )


def _digest(
    policy_id: str,
    policy_version: str | None,
    address_space_digest: str,
    rule_pins: tuple[PolicyRulePin, ...],
    policy_structure: PolicyStructureV0,
    rule_expr: _RuleExpr,
    branches: tuple[PolicyCompiledBranch, ...],
    lineage: PolicyLineage,
    policy_conditions: tuple[RuleExprPolicyCondition, ...] = (),
) -> str:
    payload = {
        "format": "compiled_policy_v0",
        "policy": [policy_id, policy_version, address_space_digest],
        "rule_pins": [asdict(item) for item in rule_pins],
        "policy_structure": asdict(policy_structure),
        "rule_expr": repr(rule_expr._canonical()),
        "branches": [asdict(item) for item in branches],
        "lineage": asdict(lineage),
    }
    # Keep the historical no-comparison payload byte-for-byte unchanged.  A
    # non-empty condition segment is a new compiler-owned extension and must
    # be committed explicitly by the Policy digest.
    if policy_conditions:
        payload["policy_conditions"] = [
            {
                "branch_id": condition.branch_id,
                "policy_node_id": condition.policy_node_id,
                "condition_id": condition.condition_id,
                "role": condition.role,
                "atom": repr(condition.atom),
            }
            for condition in policy_conditions
        ]
    return sha256_hex(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    )


def _policy_conditions_current(
    compiled: CompiledPolicyV0,
    current_body: _RuleExprBodyPlan,
) -> bool:
    """Validate the sealed, Policy-owned segment without mutating RuleExpr.

    The segment is intentionally not reconstructed from the source Policy: a
    compiled policy stores only its trusted lowering result.  We can still
    prove all local invariants (canonical order, branch ownership, compare
    ancestry, atom shape and exact lineage coordinates), while the digest
    commits the complete atom payload.
    """

    conditions = compiled._policy_conditions
    compare_ids = {
        node.node_id
        for node in compiled.policy_structure.nodes
        if isinstance(node, PolicyCompareStructureNodeV0)
    }
    if not conditions:
        return not compare_ids
    if not compare_ids:
        return False
    if tuple(sorted(conditions, key=_policy_condition_sort_key)) != conditions:
        return False
    branch_ids = {branch.branch_id for branch in current_body.branches}
    expected_refs = {
        ref
        for node in compiled.lineage.authored_nodes
        for ref in node.lowered_refs
        if isinstance(ref, PolicyConditionLoweredRefV0)
    }
    actual_refs: set[PolicyConditionLoweredRefV0] = set()
    seen: set[tuple[str, str, str]] = set()
    by_branch = {branch.branch_id: branch for branch in current_body.branches}
    for condition in conditions:
        key = (condition.branch_id, condition.policy_node_id, condition.condition_id)
        if (
            key in seen
            or condition.branch_id not in branch_ids
            or condition.policy_node_id not in compare_ids
        ):
            return False
        seen.add(key)
        branch = by_branch[condition.branch_id]
        try:
            index = _conditions_for_branch(conditions, branch.branch_id).index(condition)
        except ValueError:
            return False
        # Conditions are inserted immediately after the pure Rule body and
        # before Query bindings/joins/projection links.  That stable offset is
        # the lineage/evidence contract.
        actual_refs.add(
            PolicyConditionLoweredRefV0(
                condition.branch_id,
                condition.policy_node_id,
                condition.condition_id,
                condition.role,
                len(branch.body_atoms) + index,
            )
        )
    return actual_refs == expected_refs


def _conditions_for_branch(
    conditions: tuple[RuleExprPolicyCondition, ...], branch_id: str
) -> tuple[RuleExprPolicyCondition, ...]:
    return tuple(condition for condition in conditions if condition.branch_id == branch_id)


def _invariant(message: str, *path: str) -> PolicyError:
    return _error(
        message, "POLICY_LINEAGE_NOT_TOTAL", "policy_compiler_invariant", ("lineage", *path)
    )


def _runtime_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _error(
    message: str,
    code: str,
    stage: PolicyStage,
    path: tuple[str, ...] = (),
    details: dict[str, Any] | None = None,
) -> PolicyError:
    return PolicyError(message, code=code, stage=stage, path=path, details=details)


__all__ = ["CompiledPolicyV0", "PolicyCompiledBranch", "PolicyRulePin", "compile_policy"]
