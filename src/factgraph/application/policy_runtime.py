from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import product
import json
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var

from .protocol.policy import (
    Policy, PolicyAll, PolicyAny, PolicyError, PolicyExpression, PolicyLineage,
    PolicyLoweredRef, PolicyNode, PolicyNodeLineage, PolicyOccurrence, PolicyStage,
    PolicyUnify,
)
from .protocol.rule import _PROJECTION_ID_PREFIX
from .protocol.rule_expr import (
    RuleExpr, RuleExprError, RuleJoinConstraint, _AndGroup, _RuleExpr,
    _canonical_join_constraint,
)
from .protocol.rule_expr_lowering import _DNF_BRANCH_LIMIT, _RuleExprBodyPlan, _lower_rule_expr_body
from .protocol.semantic_address import SemanticPortAddress
from .semantic_address_runtime import ManagedRuleOccurrence, SemanticAddressResolutionError, SemanticAddressSpace
from .semantic_port_runtime import SemanticPortResolutionError, assert_rule_contract_current

_CMP_OPS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})


@dataclass(frozen=True)
class PolicyRulePin:
    occurrence_alias: str
    rule_id: str
    rule_version: str | None
    rule_content_digest: str
    semantic_contract_digest: str


@dataclass(frozen=True)
class PolicyCompiledBranch:
    branch_id: str
    authored_occurrence_aliases: tuple[str, ...]
    lowered_occurrence_aliases: tuple[str, ...]


@dataclass(frozen=True)
class CompiledPolicyV0:
    policy_id: str
    policy_version: str | None
    policy_digest: str
    address_space_digest: str
    rule_pins: tuple[PolicyRulePin, ...]
    rule_expr: _RuleExpr
    branches: tuple[PolicyCompiledBranch, ...]
    lineage: PolicyLineage
    _body_plan: _RuleExprBodyPlan = field(repr=False, compare=False)


def compile_policy(policy: Policy, *, address_space: SemanticAddressSpace) -> CompiledPolicyV0:
    if not isinstance(policy, Policy):
        raise _error("policy must be Policy", "INVALID_POLICY", "policy_compile", ("policy",))
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
    _admit(managed)
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
    _validate_unifies(policy.when, address_space, joins)
    try:
        rule_expr = _compile_expr(policy.when, managed, joins)
        body_plan = _lower_rule_expr_body(rule_expr)
    except RuleExprError as exc:
        raise _error(
            f"RuleExpr rejected compiled Policy: {exc}",
            "POLICY_LOWERING_REJECTED",
            "policy_lowering_adapter",
            ("policy", "when"),
            {"cause_type": type(exc).__name__},
        ) from exc

    branches, lineage = _lineage(nodes, body_plan, managed)
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
    return CompiledPolicyV0(
        policy.id,
        policy.version,
        _digest(policy, address_space.address_space_digest),
        address_space.address_space_digest,
        pins,
        rule_expr,
        branches,
        lineage,
        body_plan,
    )


def _validate_structure(nodes: tuple[PolicyNode, ...], managed: dict[str, ManagedRuleOccurrence]) -> None:
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
            supported_cmp = (
                isinstance(atom, CmpAtom)
                and atom.op in _CMP_OPS
                and isinstance(atom.lhs, (Var, Const))
                and isinstance(atom.rhs, (Var, Const))
            )
            if not isinstance(atom, PredAtom) and not supported_cmp:
                raise _error(
                    f"Rule {rule.id!r} uses unsupported body atom {type(atom).__name__}",
                    "UNSUPPORTED_MANAGED_RULE_CAPABILITY",
                    "policy_admission",
                    ("address_space", alias, "rule", "when", str(index)),
                    {"atom_kind": type(atom).__name__},
                )


def _validate_unifies(
    node: PolicyExpression,
    address_space: SemanticAddressSpace,
    joins: dict[str, RuleJoinConstraint],
) -> None:
    if isinstance(node, PolicyOccurrence):
        return
    if isinstance(node, PolicyAny):
        for child in node.children:
            _validate_unifies(child, address_space, joins)
        return
    structural = tuple(child for child in node.children if not isinstance(child, PolicyUnify))
    branches = _branch_product(structural)
    for item in node.children:
        if not isinstance(item, PolicyUnify):
            _validate_unifies(item, address_space, joins)
            continue
        required = {item.left.occurrence_alias, item.right.occurrence_alias}
        missing = [index for index, aliases in enumerate(branches) if not required <= aliases]
        if missing:
            raise _error(
                "Unify endpoints are absent from a local Any branch",
                "PARTIAL_BRANCH_CONSTRAINT",
                "policy_compile",
                ("policy", "when", item.node_id),
                {"missing_branch_indexes": missing},
            )
        joins[item.node_id] = _resolve_unify(item, address_space)


def _resolve_unify(unify: PolicyUnify, address_space: SemanticAddressSpace) -> RuleJoinConstraint:
    path = ("policy", "when", unify.node_id)
    if unify.left.occurrence_alias == unify.right.occurrence_alias:
        raise _error("Unify must connect distinct occurrences", "SELF_UNIFY_UNSUPPORTED", "policy_compile", path)
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
    structural = tuple(child for child in node.children if not isinstance(child, PolicyUnify))
    children = tuple(_compile_expr(child, managed, joins) for child in structural)
    if isinstance(node, PolicyAny):
        return RuleExpr.any(*children)
    compiled = RuleExpr.all(*children)
    constraints = tuple(joins[child.node_id] for child in node.children if isinstance(child, PolicyUnify))
    if constraints:
        if not isinstance(compiled, _AndGroup):
            raise _error("All did not compile to AND", "POLICY_COMPILER_INVARIANT", "policy_compiler_invariant")
        compiled = compiled.join(*constraints)
    return compiled


def _branch_count(node: PolicyExpression) -> int:
    if isinstance(node, PolicyOccurrence):
        return 1
    children = tuple(child for child in node.children if not isinstance(child, PolicyUnify))
    counts = tuple(_branch_count(child) for child in children)
    if isinstance(node, PolicyAny):
        return sum(counts)
    result = 1
    for count in counts:
        result *= count
    return result


def _branch_aliases(node: PolicyExpression) -> tuple[frozenset[str], ...]:
    if isinstance(node, PolicyOccurrence):
        return (frozenset((node.alias,)),)
    structural = tuple(child for child in node.children if not isinstance(child, PolicyUnify))
    if isinstance(node, PolicyAny):
        return tuple(branch for child in structural for branch in _branch_aliases(child))
    return _branch_product(structural)


def _branch_product(nodes: tuple[PolicyExpression, ...]) -> tuple[frozenset[str], ...]:
    return tuple(frozenset().union(*parts) for parts in product(*map(_branch_aliases, nodes)))


def _nodes(node: PolicyNode) -> tuple[PolicyNode, ...]:
    if isinstance(node, (PolicyOccurrence, PolicyUnify)):
        return (node,)
    return (node, *(nested for child in node.children for nested in _nodes(child)))


def _lineage(
    nodes: tuple[PolicyNode, ...],
    plan: _RuleExprBodyPlan,
    managed: dict[str, ManagedRuleOccurrence],
) -> tuple[tuple[PolicyCompiledBranch, ...], PolicyLineage]:
    bindings = {binding.alias: binding for binding in plan.occurrence_map}
    authored = {alias: binding.authored_alias or alias for alias, binding in bindings.items()}
    refs: dict[str, set[PolicyLoweredRef]] = {node.node_id: set() for node in nodes}
    occurrence_nodes = {node.alias: node for node in nodes if isinstance(node, PolicyOccurrence)}
    unify_nodes = {
        _unify_key(node.left, node.right): node for node in nodes if isinstance(node, PolicyUnify)
    }
    signatures = {
        node.node_id: _branch_aliases(node) for node in nodes if not isinstance(node, PolicyUnify)
    }
    branches: list[PolicyCompiledBranch] = []
    universe: set[PolicyLoweredRef] = set()

    for branch in plan.branches:
        authored_aliases = tuple(authored[alias] for alias in branch.occurrence_aliases)
        branch_ref = PolicyLoweredRef("branch", branch.branch_id)
        universe.add(branch_ref)
        for node_id, alternatives in signatures.items():
            if any(option <= frozenset(authored_aliases) for option in alternatives):
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
                    "body_atom", branch.branch_id, lowered_alias,
                    source_index=source_index, lowered_index=body_index,
                )
                refs[occurrence_node.node_id].add(atom_ref)
                universe.add(atom_ref)
                body_index += 1
        if body_index != len(branch.body_atoms):
            raise _invariant("lowered atoms do not match occurrence Rule bodies", branch.branch_id)

        unique = {_canonical_join_constraint(join): join for join in branch.pending_joins}
        for ordinal, key in enumerate(sorted(unique, key=repr)):
            join = unique[key]
            left = SemanticPortAddress(authored[join.left.occurrence_alias], join.left.port_name)
            right = SemanticPortAddress(authored[join.right.occurrence_alias], join.right.port_name)
            source = unify_nodes.get(_unify_key(left, right))
            if source is None:
                raise _invariant("lowered Unify has no authored origin", branch.branch_id)
            unify_ref = PolicyLoweredRef(
                "unify", branch.branch_id, join.left.occurrence_alias, join.left.port_name,
                lowered_index=ordinal, peer_occurrence_alias=join.right.occurrence_alias,
                peer_port_name=join.right.port_name,
            )
            refs[source.node_id].add(unify_ref)
            universe.add(unify_ref)
        branches.append(PolicyCompiledBranch(branch.branch_id, authored_aliases, branch.occurrence_aliases))

    forward: list[PolicyNodeLineage] = []
    reverse: dict[PolicyLoweredRef, set[str]] = {}
    for node in sorted(nodes, key=lambda item: item.node_id):
        targets = tuple(sorted(refs[node.node_id]))
        if not targets:
            raise _invariant("authored node has no lowered target", node.node_id)
        forward.append(PolicyNodeLineage(node.node_id, _kind(node), targets))
        for target in targets:
            reverse.setdefault(target, set()).add(node.node_id)
    if set(reverse) != universe:
        raise _invariant("lowered structure has an orphan lineage reference")
    origins = tuple((target, tuple(sorted(reverse[target]))) for target in sorted(reverse))
    return tuple(branches), PolicyLineage(tuple(forward), origins)


def _kind(node: PolicyNode) -> Literal["occurrence", "all", "any", "unify"]:
    if isinstance(node, PolicyOccurrence):
        return "occurrence"
    if isinstance(node, PolicyAll):
        return "all"
    if isinstance(node, PolicyAny):
        return "any"
    return "unify"


def _unify_key(
    left: SemanticPortAddress,
    right: SemanticPortAddress,
) -> tuple[tuple[str, str], tuple[str, str]]:
    ends = sorted(((left.occurrence_alias, left.port_name), (right.occurrence_alias, right.port_name)))
    return ends[0], ends[1]


def _digest(policy: Policy, address_space_digest: str) -> str:
    payload = {
        "format": "compiled_policy_v0",
        "policy": {"id": policy.id, "version": policy.version, "root_node_id": policy.when.node_id},
        "address_space_digest": address_space_digest,
        "dnf_branch_limit": _DNF_BRANCH_LIMIT,
        "capability_profile": "managed_policy_v0_pred_cmp_unify",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return sha256_hex(raw)


def _invariant(message: str, *path: str) -> PolicyError:
    return _error(message, "POLICY_LINEAGE_NOT_TOTAL", "policy_compiler_invariant", ("lineage", *path))


def _error(
    message: str,
    code: str,
    stage: PolicyStage,
    path: tuple[str, ...] = (),
    details: dict[str, Any] | None = None,
) -> PolicyError:
    return PolicyError(message, code=code, stage=stage, path=path, details=details)


__all__ = ["CompiledPolicyV0", "PolicyCompiledBranch", "PolicyRulePin", "compile_policy"]
