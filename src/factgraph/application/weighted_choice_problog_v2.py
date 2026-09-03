"""Bounded V2 lowering from product WeightedChoice topology to ProbLog AD.

This module deliberately has one job: convert one product Policy's intrinsic
choice AST plus its verified capture projection into one adapter-local
``ProbLogRuleExt``. It neither changes the deterministic Policy compiler nor
runs an engine. A future V2 Query runner owns invocation and may call the
public helper after it has materialized its ordinary ``CompiledDerivationPlan``.

The supported shape is intentionally narrow and fail-closed:

* one intrinsic product choice and its exact derived capture projection;
* its controlled compiler skeleton is the Policy's only ``Any`` node;
* each authored arm maps through compiled Policy lineage to exactly one DNF
  branch; and
* every structured key port resolves in every branch and is bridged to one
  canonical categorical-domain tuple.

Those restrictions make a single annotated disjunction truthful.  Treating a
nested/ambiguous topology as independent weighted OR branches would be a
semantic bug, not a useful fallback.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, NoReturn

from factgraph.adapters.problog.rule_ext import (
    ProbLogRuleExt,
    ProbLogWeightedChoiceArm,
    ProbLogWeightedChoiceBranch,
    ProbLogWeightedChoiceExt,
)
from factgraph.application.policy_runtime import (
    CompiledPolicyV0,
    _assert_compiled_policy_current,
    compile_policy,
)
from factgraph.application.protocol.derivation import CompiledDerivationPlan
from factgraph.application.protocol.policy import (
    PolicyAll,
    PolicyAny,
    PolicyLoweredRef,
    PolicyNode,
    PolicyWeightedChoice,
    _lower_policy_weighted_choices_to_any_skeleton,
    policy_contains_weighted_choice,
)
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.schema_runtime import SchemaIndex
from factgraph.core.rules.where_ast import AndExpr, lower_ast_to_where_ir
from factgraph.sdk.product_authoring import (
    ProductPolicyV1,
    WeightedChoiceTopologyV1,
    assert_asset_binding_current_v1,
)


class ProductWeightedChoiceProbLogV2Error(ValueError):
    """Typed rejection at the V2 product-to-ProbLog lowering boundary."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


def _compile_product_policy_v2_skeleton_for_lowering(
    *,
    target: ProductPolicyV1,
    schema_index: SchemaIndex,
) -> CompiledPolicyV0:
    """Compile only the structural carrier needed by the V2 lowering seam.

    A public ``ProductPolicyV1.policy`` with ``WeightedChoice`` contains an
    intrinsic V2-only node (and carries ``PolicyV2Only`` as defense in depth),
    so every legacy entrypoint rejects it. This private helper is the narrow
    exception: it derives an ordinary in-process skeleton *only* to obtain the
    existing typed lineage required by the V2 annotated-disjunction lowerer.
    The helper neither evaluates that Policy nor exposes a legacy terminal;
    callers must retain the original product envelope and immediately verify
    it through :func:`lower_product_policy_weighted_choice_to_problog_v2`.
    """

    if not isinstance(target, ProductPolicyV1):
        _fail(
            "V2 skeleton compilation requires ProductPolicyV1",
            code="WEIGHTED_CHOICE_V2_INVALID_TARGET",
        )
    if not target.requires_v2_profile or not policy_contains_weighted_choice(target.policy):
        _fail(
            "V2 skeleton compilation requires an intrinsic WeightedChoice Policy",
            code="WEIGHTED_CHOICE_V2_MARKER_REQUIRED",
        )
    try:
        assert_asset_binding_current_v1(target)
    except Exception as exc:
        _fail(
            "product Policy asset/topology seal is not current",
            code="WEIGHTED_CHOICE_V2_TARGET_SEAL_MISMATCH",
            details={"cause_type": type(exc).__name__},
        )
    try:
        # Do not ever feed ``target.policy`` itself into the deterministic
        # compiler: its intrinsic choice node is the public boundary.  This
        # transient plain carrier is intentionally not returned to SDK callers.
        return compile_policy(
            _lower_policy_weighted_choices_to_any_skeleton(target.policy),
            address_space=target.address_space,
            schema_index=schema_index,
        )
    except Exception as exc:
        _fail(
            "V2 structural Policy skeleton could not be compiled",
            code="WEIGHTED_CHOICE_V2_SKELETON_COMPILE_FAILED",
            details={"cause_type": type(exc).__name__},
        )


def lower_product_policy_weighted_choice_to_problog_v2(
    *,
    target: ProductPolicyV1,
    compiled_policy: CompiledPolicyV0,
    plan: CompiledDerivationPlan,
) -> CompiledDerivationPlan:
    """Attach one sealed exclusive choice as a ProbLog annotated-disjunction ext.

    The returned plan is a regular :class:`CompiledDerivationPlan` whose
    ``engine_ext`` is a :class:`~factgraph.adapters.problog.rule_ext.ProbLogRuleExt`.
    The caller must evaluate that plan with ``DerivationEvaluateRequest(engine="problog")``.
    This helper purposely does not add an engine field to a compiled plan or
    create a V2 terminal; that remains the owning runner's responsibility.
    """

    if not isinstance(target, ProductPolicyV1):
        _fail(
            "weighted choice V2 lowering requires ProductPolicyV1",
            code="WEIGHTED_CHOICE_V2_INVALID_TARGET",
        )
    if not isinstance(compiled_policy, CompiledPolicyV0):
        _fail(
            "weighted choice V2 lowering requires CompiledPolicyV0",
            code="WEIGHTED_CHOICE_V2_INVALID_COMPILED_POLICY",
        )
    if not isinstance(plan, CompiledDerivationPlan):
        _fail(
            "weighted choice V2 lowering requires CompiledDerivationPlan",
            code="WEIGHTED_CHOICE_V2_INVALID_PLAN",
        )
    if plan.engine_ext is not None:
        _fail(
            "weighted choice V2 lowering cannot replace an existing engine extension",
            code="WEIGHTED_CHOICE_V2_PLAN_ENGINE_EXT_CONFLICT",
        )

    try:
        assert_asset_binding_current_v1(target)
    except Exception as exc:
        _fail(
            "product Policy asset/topology seal is not current",
            code="WEIGHTED_CHOICE_V2_TARGET_SEAL_MISMATCH",
            details={"cause_type": type(exc).__name__},
        )
    try:
        _assert_compiled_policy_current(compiled_policy)
    except Exception as exc:
        _fail(
            "compiled Policy integrity check failed",
            code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_STALE",
            details={"cause_type": type(exc).__name__},
        )

    _assert_target_matches_compiled_policy(target, compiled_policy)
    choice = _single_choice(target)
    _assert_supported_raw_shape(target, choice)
    plan_branches = _plan_branches(plan)
    _assert_plan_matches_compiled_policy(plan_branches, compiled_policy)

    branch_index_by_id = {
        branch.branch_id: index for index, branch in enumerate(compiled_policy.branches)
    }
    choice_branch_ids = _lineage_branch_ids(compiled_policy, choice.skeleton_node_id)
    if choice_branch_ids != set(branch_index_by_id):
        _fail(
            "choice skeleton lineage does not cover every compiled Policy branch",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_SKELETON",
            details={
                "expected_branch_ids": sorted(branch_index_by_id),
                "actual_branch_ids": sorted(choice_branch_ids),
            },
        )

    mapped: list[tuple[int, str]] = []
    for arm in choice.arms:
        branch_ids = _lineage_branch_ids(compiled_policy, arm.condition_node_id)
        if len(branch_ids) != 1:
            _fail(
                "each exclusive WeightedChoice arm must map to exactly one compiled branch",
                code="WEIGHTED_CHOICE_V2_NESTED_OR_UNSUPPORTED",
                details={"arm_id": arm.arm_id, "branch_ids": sorted(branch_ids)},
            )
        branch_id = next(iter(branch_ids))
        branch_index = branch_index_by_id.get(branch_id)
        if branch_index is None or branch_id not in choice_branch_ids:
            _fail(
                "WeightedChoice arm lineage points outside the choice skeleton",
                code="WEIGHTED_CHOICE_V2_UNMAPPED_ARM",
                details={"arm_id": arm.arm_id, "branch_id": branch_id},
            )
        mapped.append((branch_index, arm.arm_id))

    if len({index for index, _arm_id in mapped}) != len(mapped) or {
        index for index, _arm_id in mapped
    } != set(range(len(compiled_policy.branches))):
        _fail(
            "WeightedChoice arms must cover every compiled branch exactly once",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_ARM",
            details={"mapped_branch_indexes": sorted(index for index, _ in mapped)},
        )

    domain_body, domain_key_variables = _choice_domain(
        target=target,
        compiled_policy=compiled_policy,
        plan_branches=plan_branches,
        branch_index=min(index for index, _arm_id in mapped),
        selection_key=choice.selection_key,
    )
    branch_specs: list[ProbLogWeightedChoiceBranch] = []
    for branch_index, arm_id in sorted(mapped):
        key_variables = _branch_key_variables(
            compiled_policy,
            branch_index=branch_index,
            selection_key=choice.selection_key,
        )
        branch_specs.append(ProbLogWeightedChoiceBranch(branch_index, arm_id, key_variables))

    extension = ProbLogWeightedChoiceExt(
        choice_id=choice.choice_id,
        choice_node_id=choice.node_id,
        topology_digest=choice.topology_digest,
        arms=tuple(ProbLogWeightedChoiceArm(arm.arm_id, arm.probability) for arm in choice.arms),
        branches=tuple(branch_specs),
        domain_key_variables=domain_key_variables,
        domain_body=domain_body,
    )
    return replace(plan, engine_ext=ProbLogRuleExt(weighted_choice=extension))


def _fail(
    message: str,
    *,
    code: str,
    details: dict[str, object] | None = None,
) -> NoReturn:
    raise ProductWeightedChoiceProbLogV2Error(message, code=code, details=details)


def _single_choice(target: ProductPolicyV1) -> WeightedChoiceTopologyV1:
    if len(target.weighted_choices) != 1:
        _fail(
            "this V2 ProbLog seam supports exactly one WeightedChoice sidecar",
            code="WEIGHTED_CHOICE_V2_MULTIPLE_UNSUPPORTED",
            details={"choice_count": len(target.weighted_choices)},
        )
    return target.weighted_choices[0]


def _raw_nodes(node: PolicyNode) -> tuple[PolicyNode, ...]:
    if isinstance(node, (PolicyAll, PolicyAny, PolicyWeightedChoice)):
        return (node, *(nested for child in node.children for nested in _raw_nodes(child)))
    return (node,)


def _raw_kind(node: PolicyNode) -> str:
    from factgraph.application.protocol.policy import PolicyCompare, PolicyOccurrence, PolicyUnify

    if isinstance(node, PolicyOccurrence):
        return "occurrence"
    if isinstance(node, PolicyAll):
        return "all"
    if isinstance(node, PolicyAny):
        return "any"
    if isinstance(node, PolicyWeightedChoice):
        return "weighted_choice"
    if isinstance(node, PolicyUnify):
        return "unify"
    if isinstance(node, PolicyCompare):
        return "compare"
    _fail(
        "product Policy contains an unsupported raw node", code="WEIGHTED_CHOICE_V2_TARGET_TOPOLOGY"
    )


def _assert_target_matches_compiled_policy(
    target: ProductPolicyV1,
    compiled_policy: CompiledPolicyV0,
) -> None:
    if (
        compiled_policy.policy_id != target.policy.id
        or compiled_policy.policy_version != target.policy.version
        or compiled_policy.address_space_digest != target.address_space.address_space_digest
    ):
        _fail(
            "compiled Policy identity does not match the product Policy target",
            code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_TARGET_MISMATCH",
        )
    skeleton = _lower_policy_weighted_choices_to_any_skeleton(target.policy)
    raw = {node.node_id: _raw_kind(node) for node in _raw_nodes(skeleton.when)}
    compiled = {node.node_id: node.kind for node in compiled_policy.policy_structure.nodes}
    if compiled_policy.policy_structure.root_node_id != skeleton.when.node_id or raw != compiled:
        _fail(
            "compiled Policy topology does not match the product Policy target",
            code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_TARGET_MISMATCH",
        )


def _assert_supported_raw_shape(
    target: ProductPolicyV1,
    choice: WeightedChoiceTopologyV1,
) -> None:
    authored_nodes = _raw_nodes(target.policy.when)
    intrinsic = [node for node in authored_nodes if isinstance(node, PolicyWeightedChoice)]
    ordinary_any = [node for node in authored_nodes if isinstance(node, PolicyAny)]
    if len(intrinsic) != 1 or intrinsic[0].choice_id != choice.choice_id or ordinary_any:
        _fail(
            "V2 ProbLog choice supports one intrinsic choice and no nested ordinary PolicyAny",
            code="WEIGHTED_CHOICE_V2_NESTED_OR_UNSUPPORTED",
            details={
                "intrinsic_choice_node_ids": sorted(node.node_id for node in intrinsic),
                "ordinary_any_node_ids": sorted(node.node_id for node in ordinary_any),
            },
        )
    skeleton = _lower_policy_weighted_choices_to_any_skeleton(target.policy)
    any_nodes = [node for node in _raw_nodes(skeleton.when) if isinstance(node, PolicyAny)]
    if len(any_nodes) != 1 or any_nodes[0].node_id != choice.skeleton_node_id:
        _fail(
            "V2 ProbLog intrinsic choice did not lower to its canonical PolicyAny skeleton",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_SKELETON",
        )


def _lineage_branch_ids(compiled_policy: CompiledPolicyV0, node_id: str) -> set[str]:
    node = next(
        (item for item in compiled_policy.lineage.authored_nodes if item.node_id == node_id),
        None,
    )
    if node is None:
        _fail(
            "WeightedChoice topology node is absent from compiled Policy lineage",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_ARM",
            details={"node_id": node_id},
        )
    refs = {
        ref.branch_id
        for ref in node.lowered_refs
        if isinstance(ref, PolicyLoweredRef) and ref.kind == "branch"
    }
    if not refs:
        _fail(
            "WeightedChoice topology node has no compiled branch lineage",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_ARM",
            details={"node_id": node_id},
        )
    return refs


def _plan_branches(plan: CompiledDerivationPlan) -> tuple[tuple[Any, ...], ...]:
    body = plan.body_ir
    if not isinstance(body, list) or not body:
        _fail("compiled plan body must be a non-empty list", code="WEIGHTED_CHOICE_V2_INVALID_PLAN")
    if all(isinstance(item, tuple) for item in body):
        return (tuple(body),)
    if all(isinstance(item, list) and item for item in body):
        return tuple(tuple(item) for item in body)
    _fail(
        "compiled plan body must be one AND branch or canonical DNF branch lists",
        code="WEIGHTED_CHOICE_V2_INVALID_PLAN",
    )


def _assert_plan_matches_compiled_policy(
    plan_branches: tuple[tuple[Any, ...], ...],
    compiled_policy: CompiledPolicyV0,
) -> None:
    if len(plan_branches) != len(compiled_policy.branches):
        _fail(
            "compiled plan DNF branch count does not match compiled Policy lineage",
            code="WEIGHTED_CHOICE_V2_PLAN_BRANCH_MISMATCH",
            details={
                "plan_branch_count": len(plan_branches),
                "policy_branch_count": len(compiled_policy.branches),
            },
        )
    body_by_id = {branch.branch_id: branch for branch in compiled_policy._body_plan.branches}
    for index, policy_branch in enumerate(compiled_policy.branches):
        source = body_by_id.get(policy_branch.branch_id)
        if source is None:
            _fail(
                "compiled Policy branch is absent from its lowering plan",
                code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_STALE",
            )
        try:
            prefix = tuple(lower_ast_to_where_ir(AndExpr(list(source.body_atoms))))
        except Exception as exc:
            _fail(
                "compiled Policy branch cannot be converted to canonical where IR",
                code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_STALE",
                details={"cause_type": type(exc).__name__},
            )
        if plan_branches[index][: len(prefix)] != prefix:
            _fail(
                "compiled plan is not rooted in the supplied compiled Policy branch order",
                code="WEIGHTED_CHOICE_V2_PLAN_POLICY_MISMATCH",
                details={"branch_index": index, "branch_id": policy_branch.branch_id},
            )


def _branch_key_variables(
    compiled_policy: CompiledPolicyV0,
    *,
    branch_index: int,
    selection_key: tuple[SemanticPortAddress, ...],
) -> tuple[str, ...]:
    branch = compiled_policy.branches[branch_index]
    bindings = {binding.alias: binding for binding in compiled_policy._body_plan.occurrence_map}
    names: list[str] = []
    for address in selection_key:
        try:
            occurrence_index = branch.authored_occurrence_aliases.index(address.occurrence_alias)
            lowered_alias = branch.lowered_occurrence_aliases[occurrence_index]
            occurrence = bindings[lowered_alias]
        except (IndexError, KeyError, ValueError) as exc:
            _fail(
                "selection key is not present in one compiled Policy branch",
                code="WEIGHTED_CHOICE_V2_UNMAPPED_SELECTION_KEY",
                details={
                    "branch_id": branch.branch_id,
                    "address": (address.occurrence_alias, address.port_name),
                    "cause_type": type(exc).__name__,
                },
            )
        candidates = [
            binding.alias_local_execution_var.name
            for binding in occurrence.port_bindings
            if binding.port_name == address.port_name
        ]
        if len(candidates) != 1 or not candidates[0].startswith("$"):
            _fail(
                "selection key does not have exactly one compiled execution variable",
                code="WEIGHTED_CHOICE_V2_UNMAPPED_SELECTION_KEY",
                details={
                    "branch_id": branch.branch_id,
                    "address": (address.occurrence_alias, address.port_name),
                },
            )
        names.append(candidates[0])
    return tuple(names)


def _choice_domain(
    *,
    target: ProductPolicyV1,
    compiled_policy: CompiledPolicyV0,
    plan_branches: tuple[tuple[Any, ...], ...],
    branch_index: int,
    selection_key: tuple[SemanticPortAddress, ...],
) -> tuple[tuple[Any, ...], tuple[str, ...]]:
    """Extract a canonical selection-key domain from one source DNF branch.

    The Policy lowerer deliberately copies a branch-total occurrence into
    aliases such as ``key__c0`` / ``key__c1``.  Their variable names must not
    be mistaken for different categorical keys.  We select the source Rule
    atoms for all key occurrences from one verified compiled branch, rewrite
    their local variables to a fresh canonical namespace, and let each output
    branch call the same AD predicates with its own local key tuple.

    Any source fragments omitted here can only create unused categorical
    variables, never turn one output fact into a different key: the full
    branch body still gates every emitted ``rule_body_N``.  The selected Rule
    witnesses themselves are retained so every domain key is grounded.
    """

    branch = compiled_policy.branches[branch_index]
    body_plan_by_id = {item.branch_id: item for item in compiled_policy._body_plan.branches}
    source = body_plan_by_id.get(branch.branch_id)
    if source is None:
        _fail(
            "compiled Policy branch is absent from its source lowering plan",
            code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_STALE",
        )
    if branch_index >= len(plan_branches):
        _fail(
            "compiled plan is missing the choice source branch",
            code="WEIGHTED_CHOICE_V2_PLAN_BRANCH_MISMATCH",
        )
    rule_by_alias = {
        managed.occurrence.alias: managed.occurrence.rule
        for managed in target.address_space.occurrences
    }
    selected_aliases = {address.occurrence_alias for address in selection_key}
    fragments: list[Any] = []
    offset = 0
    for lowered_alias in source.occurrence_aliases:
        binding = next(
            (
                item
                for item in compiled_policy._body_plan.occurrence_map
                if item.alias == lowered_alias
            ),
            None,
        )
        if binding is None:
            _fail(
                "compiled Policy occurrence is missing its source binding",
                code="WEIGHTED_CHOICE_V2_COMPILED_POLICY_STALE",
            )
        authored_alias = binding.authored_alias or lowered_alias
        rule = rule_by_alias.get(authored_alias)
        if rule is None:
            _fail(
                "selection-key occurrence is absent from the product address space",
                code="WEIGHTED_CHOICE_V2_UNMAPPED_SELECTION_KEY",
                details={"occurrence_alias": authored_alias},
            )
        atom_count = len(rule.when)
        if authored_alias in selected_aliases:
            fragment = plan_branches[branch_index][offset : offset + atom_count]
            if len(fragment) != atom_count:
                _fail(
                    "compiled plan truncates a selection-key source occurrence",
                    code="WEIGHTED_CHOICE_V2_PLAN_POLICY_MISMATCH",
                    details={"occurrence_alias": authored_alias},
                )
            fragments.extend(fragment)
        offset += atom_count
    if not fragments:
        _fail(
            "WeightedChoice selection key has no source Rule witnesses",
            code="WEIGHTED_CHOICE_V2_UNMAPPED_SELECTION_KEY",
        )

    source_key_variables = _branch_key_variables(
        compiled_policy,
        branch_index=branch_index,
        selection_key=selection_key,
    )
    variable_map: dict[str, str] = {}
    domain_key_variables: list[str] = []
    for source_name in source_key_variables:
        canonical = variable_map.get(source_name)
        if canonical is None:
            canonical = f"$__weighted_choice_key_{len(variable_map)}"
            variable_map[source_name] = canonical
        domain_key_variables.append(canonical)

    aux_index = 0

    def _rewrite(value: Any) -> Any:
        nonlocal aux_index
        if isinstance(value, str) and value.startswith("$"):
            canonical = variable_map.get(value)
            if canonical is None:
                canonical = f"$__weighted_choice_aux_{aux_index}"
                aux_index += 1
                variable_map[value] = canonical
            return canonical
        if isinstance(value, tuple):
            return tuple(_rewrite(item) for item in value)
        if isinstance(value, list):
            return [_rewrite(item) for item in value]
        return value

    rewritten = tuple(_rewrite(fragment) for fragment in fragments)
    return rewritten, tuple(domain_key_variables)


__all__ = [
    "ProductWeightedChoiceProbLogV2Error",
    "lower_product_policy_weighted_choice_to_problog_v2",
]
