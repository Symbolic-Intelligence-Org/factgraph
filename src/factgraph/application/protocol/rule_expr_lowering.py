from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from itertools import product
from typing import Literal

from factgraph.application.derivation_runtime import evaluate_derivation_plans
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    AndExpr,
    Atom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    Term,
    Var,
    lower_ast_to_where_ir,
)
from factgraph.core.store import Store

from .derivation import CompiledDerivationPlan, CompiledHeadCall, DerivationEvaluateRequest
from .rule import PortType, Rule, RulePortRef, _is_projection_rule
from .rule_expr import (
    RuleExprError,
    RuleJoinConstraint,
    _AndGroup,
    _canonical_join_constraint,
    _coerce_rule_expr_operand,
    _normalize_join_constraints,
    _OrGroup,
    _RuleExpr,
    _RuleOperand,
)

RuleExprAdapterEngine = Literal["native", "souffle", "problog"]
RuleExprAdapterRejectionSource = Literal["ruleexpr-join", "source-rule-grammar", "aggregate", "branch-shape"]
_DNF_BRANCH_LIMIT = 32


@dataclass(frozen=True)
class _DNFBranch:
    operands: tuple[_RuleOperand, ...]
    joins: tuple[RuleJoinConstraint, ...] = ()


@dataclass(frozen=True)
class RuleExprPortBinding:
    occurrence_alias: str
    port_name: str
    port_type: PortType
    source_var: Var
    alias_local_execution_var: Var

    def __post_init__(self) -> None:
        _require_non_empty_str(self.occurrence_alias, field_name="occurrence_alias")
        _require_non_empty_str(self.port_name, field_name="port_name")
        if not isinstance(self.port_type, PortType):
            raise RuleExprError("RuleExprPortBinding.port_type must be PortType")
        if not isinstance(self.source_var, Var):
            raise RuleExprError("RuleExprPortBinding.source_var must be Var")
        if not isinstance(self.alias_local_execution_var, Var):
            raise RuleExprError("RuleExprPortBinding.alias_local_execution_var must be Var")


@dataclass(frozen=True)
class RuleExprOccurrenceBinding:
    alias: str
    rule_id: str
    content_digest: str
    port_bindings: tuple[RuleExprPortBinding, ...]
    rule_version: str | None = None
    authored_alias: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.alias, field_name="alias")
        _require_non_empty_str(self.rule_id, field_name="rule_id")
        _require_non_empty_str(self.content_digest, field_name="content_digest")
        _require_tuple(self.port_bindings, field_name="port_bindings", item_type=RuleExprPortBinding)
        _require_optional_str(self.rule_version, field_name="rule_version")
        _require_optional_str(self.authored_alias, field_name="authored_alias")


@dataclass(frozen=True)
class _RuleExprBodyPlan:
    """Head-independent exact structural lowering used by the Policy compiler."""

    source_kind: Literal["rule", "rule_expr"]
    branches: tuple[RuleExprLoweringBranch, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    canonical_key: tuple[object, ...]

    def __post_init__(self) -> None:
        if self.source_kind not in {"rule", "rule_expr"}:
            raise RuleExprError("_RuleExprBodyPlan.source_kind must be 'rule' or 'rule_expr'")
        _require_tuple(self.branches, field_name="branches", item_type=RuleExprLoweringBranch)
        if not self.branches:
            raise RuleExprError("_RuleExprBodyPlan.branches must not be empty")
        _require_tuple(self.occurrence_map, field_name="occurrence_map", item_type=RuleExprOccurrenceBinding)
        if not isinstance(self.canonical_key, tuple) or not self.canonical_key:
            raise RuleExprError("_RuleExprBodyPlan.canonical_key must be non-empty tuple")


@dataclass(frozen=True)
class RuleExprHeadBinding:
    kind: Literal["external", "inline", "projection"]
    head_rule_id: str
    head_content_digest: str
    projection_occurrence_alias: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"external", "inline", "projection"}:
            raise RuleExprError("RuleExprHeadBinding.kind must be external, inline, or projection")
        _require_non_empty_str(self.head_rule_id, field_name="head_rule_id")
        _require_non_empty_str(self.head_content_digest, field_name="head_content_digest")
        if self.projection_occurrence_alias is not None:
            _require_non_empty_str(self.projection_occurrence_alias, field_name="projection_occurrence_alias")
        if self.kind in {"external", "projection"} and self.projection_occurrence_alias is not None:
            raise RuleExprError("external/projection head binding must not set projection_occurrence_alias")
        if self.kind == "inline" and self.projection_occurrence_alias is None:
            raise RuleExprError("inline head binding requires projection_occurrence_alias")


@dataclass(frozen=True, order=True)
class _RuleExprQueryHeadLink:
    branch_id: str
    head_port_name: str
    occurrence_alias: str
    port_name: str

    def __post_init__(self) -> None:
        for name in ("branch_id", "head_port_name", "occurrence_alias", "port_name"):
            _require_non_empty_str(getattr(self, name), field_name=name)


@dataclass(frozen=True)
class _RuleExprQueryValueBinding:
    branch_id: str
    occurrence_alias: str
    port_name: str
    value: Const

    def __post_init__(self) -> None:
        for name in ("branch_id", "occurrence_alias", "port_name"):
            _require_non_empty_str(getattr(self, name), field_name=name)
        if not isinstance(self.value, Const):
            raise RuleExprError("query value binding must contain Const")


@dataclass(frozen=True, order=True)
class _RuleExprQueryNavigationLookup:
    """Compiler-private Query projection lookup.

    Unlike ``_RuleExprQueryHeadLink``, this does not claim the projected scalar
    is a reusable Rule port.  It reads a schema field from a selected identity
    and feeds the synthetic projection head through a generated local variable.
    """

    branch_id: str
    head_port_name: str
    occurrence_alias: str
    port_name: str
    field_predicate_id: str

    def __post_init__(self) -> None:
        for name in (
            "branch_id", "head_port_name", "occurrence_alias", "port_name",
            "field_predicate_id",
        ):
            _require_non_empty_str(getattr(self, name), field_name=name)


PolicyConditionRole = Literal["left_field", "right_field", "compare"]


@dataclass(frozen=True)
class RuleExprPolicyCondition:
    """One compiler-owned Policy condition to inject after Rule bodies.

    The RuleExpr lowerer intentionally knows no Policy AST or schema.  It only
    receives an already-resolved Atom plus the stable authored Policy node and
    condition coordinates needed for trace/evidence ownership.
    """

    branch_id: str
    policy_node_id: str
    condition_id: str
    role: PolicyConditionRole
    atom: PredAtom | CmpAtom

    def __post_init__(self) -> None:
        for name in ("branch_id", "policy_node_id", "condition_id"):
            _require_non_empty_str(getattr(self, name), field_name=name)
        if self.role not in {"left_field", "right_field", "compare"}:
            raise RuleExprError("RuleExprPolicyCondition.role is invalid")
        if self.role in {"left_field", "right_field"} and not isinstance(self.atom, PredAtom):
            raise RuleExprError("Policy field condition must materialize a PredAtom")
        if self.role == "compare" and not isinstance(self.atom, CmpAtom):
            raise RuleExprError("Policy compare condition must materialize a CmpAtom")

    @property
    def canonical_key(self) -> tuple[object, ...]:
        return (
            self.branch_id,
            self.policy_node_id,
            self.condition_id,
            self.role,
            repr(self.atom),
        )


@dataclass(frozen=True)
class RuleExprLoweringBranch:
    branch_id: str
    path: tuple[int, ...]
    occurrence_aliases: tuple[str, ...]
    body_atoms: tuple[Atom, ...]
    pending_joins: tuple[RuleJoinConstraint, ...] = ()

    def __post_init__(self) -> None:
        if self.branch_id and not isinstance(self.branch_id, str):
            raise RuleExprError("RuleExprLoweringBranch.branch_id must be string")
        _require_tuple(self.path, field_name="path", item_type=int)
        _require_tuple(self.occurrence_aliases, field_name="occurrence_aliases", item_type=str)
        if not isinstance(self.body_atoms, tuple) or not self.body_atoms:
            raise RuleExprError("RuleExprLoweringBranch.body_atoms must be non-empty tuple")
        _require_tuple(self.pending_joins, field_name="pending_joins", item_type=RuleJoinConstraint)


@dataclass(frozen=True)
class RuleExprLoweringPlan:
    source_kind: Literal["rule", "rule_expr"]
    head: Rule
    head_binding: RuleExprHeadBinding
    branches: tuple[RuleExprLoweringBranch, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    canonical_key: tuple[object, ...]
    query_head_links: tuple[_RuleExprQueryHeadLink, ...] = ()
    query_value_bindings: tuple[_RuleExprQueryValueBinding, ...] = ()
    query_navigation_lookups: tuple[_RuleExprQueryNavigationLookup, ...] = ()
    policy_conditions: tuple[RuleExprPolicyCondition, ...] = ()

    def __post_init__(self) -> None:
        if self.source_kind not in {"rule", "rule_expr"}:
            raise RuleExprError("RuleExprLoweringPlan.source_kind must be 'rule' or 'rule_expr'")
        if not isinstance(self.head, Rule):
            raise RuleExprError("RuleExprLoweringPlan.head must be application protocol Rule")
        if not isinstance(self.head_binding, RuleExprHeadBinding):
            raise RuleExprError("RuleExprLoweringPlan.head_binding must be RuleExprHeadBinding")
        _require_tuple(self.branches, field_name="branches", item_type=RuleExprLoweringBranch)
        if not self.branches:
            raise RuleExprError("RuleExprLoweringPlan.branches must not be empty")
        _require_tuple(self.occurrence_map, field_name="occurrence_map", item_type=RuleExprOccurrenceBinding)
        if not isinstance(self.canonical_key, tuple) or not self.canonical_key:
            raise RuleExprError("RuleExprLoweringPlan.canonical_key must be non-empty tuple")
        _require_tuple(self.query_head_links, field_name="query_head_links", item_type=_RuleExprQueryHeadLink)
        _require_tuple(
            self.query_value_bindings,
            field_name="query_value_bindings",
            item_type=_RuleExprQueryValueBinding,
        )
        _require_tuple(
            self.query_navigation_lookups,
            field_name="query_navigation_lookups",
            item_type=_RuleExprQueryNavigationLookup,
        )
        _require_tuple(
            self.policy_conditions,
            field_name="policy_conditions",
            item_type=RuleExprPolicyCondition,
        )
        _validate_query_extensions(self)
        _validate_policy_conditions(self)


@dataclass(frozen=True)
class RuleExprJoinMaterialization:
    branch_id: str
    join_key: tuple[object, ...]
    left_occurrence_alias: str
    left_port_name: str
    right_occurrence_alias: str
    right_port_name: str
    materialized_condition_index: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        if not isinstance(self.join_key, tuple) or not self.join_key:
            raise RuleExprError("RuleExprJoinMaterialization.join_key must be non-empty tuple")
        _require_non_empty_str(self.left_occurrence_alias, field_name="left_occurrence_alias")
        _require_non_empty_str(self.left_port_name, field_name="left_port_name")
        _require_non_empty_str(self.right_occurrence_alias, field_name="right_occurrence_alias")
        _require_non_empty_str(self.right_port_name, field_name="right_port_name")
        _require_non_negative_int(self.materialized_condition_index, field_name="materialized_condition_index")


@dataclass(frozen=True)
class RuleExprHeadPortLinkMaterialization:
    branch_id: str
    head_port_name: str
    source_occurrence_alias: str
    source_port_name: str
    materialized_condition_index: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        _require_non_empty_str(self.head_port_name, field_name="head_port_name")
        _require_non_empty_str(self.source_occurrence_alias, field_name="source_occurrence_alias")
        _require_non_empty_str(self.source_port_name, field_name="source_port_name")
        _require_non_negative_int(self.materialized_condition_index, field_name="materialized_condition_index")


@dataclass(frozen=True)
class RuleExprQueryNavigationMaterialization:
    """Trace coordinates for one Query-owned field lookup and its head link."""

    branch_id: str
    head_port_name: str
    base_occurrence_alias: str
    base_port_name: str
    field_predicate_id: str
    lookup_var_name: str
    lookup_materialized_condition_index: int
    projection_head_link_materialized_condition_index: int

    def __post_init__(self) -> None:
        for name in (
            "branch_id", "head_port_name", "base_occurrence_alias", "base_port_name",
            "field_predicate_id", "lookup_var_name",
        ):
            _require_non_empty_str(getattr(self, name), field_name=name)
        _require_non_negative_int(
            self.lookup_materialized_condition_index,
            field_name="lookup_materialized_condition_index",
        )
        _require_non_negative_int(
            self.projection_head_link_materialized_condition_index,
            field_name="projection_head_link_materialized_condition_index",
        )


@dataclass(frozen=True)
class RuleExprPolicyConditionMaterialization:
    branch_id: str
    policy_node_id: str
    condition_id: str
    role: PolicyConditionRole
    materialized_condition_index: int

    def __post_init__(self) -> None:
        for name in ("branch_id", "policy_node_id", "condition_id"):
            _require_non_empty_str(getattr(self, name), field_name=name)
        if self.role not in {"left_field", "right_field", "compare"}:
            raise RuleExprError("RuleExprPolicyConditionMaterialization.role is invalid")
        _require_non_negative_int(self.materialized_condition_index, field_name="materialized_condition_index")


@dataclass(frozen=True)
class RuleExprEvaluationTrace:
    canonical_key: tuple[object, ...]
    engine: RuleExprAdapterEngine
    branch_id: str
    runtime_case_index: int
    occurrence_aliases: tuple[str, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    join_materializations: tuple[RuleExprJoinMaterialization, ...]
    head_binding: RuleExprHeadBinding
    head_port_link_materializations: tuple[RuleExprHeadPortLinkMaterialization, ...] = ()
    query_navigation_materializations: tuple[RuleExprQueryNavigationMaterialization, ...] = ()
    policy_condition_materializations: tuple[RuleExprPolicyConditionMaterialization, ...] = ()
    support_digest: str | None = None
    support_kind: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_key, tuple) or not self.canonical_key:
            raise RuleExprError("RuleExprEvaluationTrace.canonical_key must be non-empty tuple")
        if self.engine not in {"native", "souffle", "problog"}:
            raise RuleExprError("RuleExprEvaluationTrace.engine must be native, souffle, or problog")
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        _require_non_negative_int(self.runtime_case_index, field_name="runtime_case_index")
        _require_tuple(self.occurrence_aliases, field_name="occurrence_aliases", item_type=str)
        _require_tuple(self.occurrence_map, field_name="occurrence_map", item_type=RuleExprOccurrenceBinding)
        _require_tuple(
            self.join_materializations,
            field_name="join_materializations",
            item_type=RuleExprJoinMaterialization,
        )
        _require_tuple(
            self.head_port_link_materializations,
            field_name="head_port_link_materializations",
            item_type=RuleExprHeadPortLinkMaterialization,
        )
        _require_tuple(
            self.query_navigation_materializations,
            field_name="query_navigation_materializations",
            item_type=RuleExprQueryNavigationMaterialization,
        )
        _require_tuple(
            self.policy_condition_materializations,
            field_name="policy_condition_materializations",
            item_type=RuleExprPolicyConditionMaterialization,
        )
        if not isinstance(self.head_binding, RuleExprHeadBinding):
            raise RuleExprError("RuleExprEvaluationTrace.head_binding must be RuleExprHeadBinding")
        _require_optional_str(self.support_digest, field_name="support_digest")
        _require_optional_str(self.support_kind, field_name="support_kind")


@dataclass(frozen=True)
class RuleExprAdapterSupport:
    engine: Literal["pyreason"]
    supported: bool
    unsupported_feature: str | None = None
    rejection_source: RuleExprAdapterRejectionSource | None = None
    alternative_engines: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.engine != "pyreason":
            raise RuleExprError("RuleExprAdapterSupport.engine must be 'pyreason'")
        if not isinstance(self.supported, bool):
            raise RuleExprError("RuleExprAdapterSupport.supported must be bool")
        _require_optional_str(self.unsupported_feature, field_name="unsupported_feature")
        if self.rejection_source is not None and self.rejection_source not in {
            "ruleexpr-join",
            "source-rule-grammar",
            "aggregate",
            "branch-shape",
        }:
            raise RuleExprError("RuleExprAdapterSupport.rejection_source is unsupported")
        _require_tuple(self.alternative_engines, field_name="alternative_engines", item_type=str)
        if self.supported and (self.unsupported_feature is not None or self.rejection_source is not None):
            raise RuleExprError("supported adapter classification must not include rejection details")
        if not self.supported and (self.unsupported_feature is None or self.rejection_source is None):
            raise RuleExprError("unsupported adapter classification requires rejection details")


@dataclass(frozen=True)
class RuleExprDeclaredPortBranchSource:
    branch_id: str
    occurrence_alias: str
    port_name: str
    port_type: PortType
    alias_local_execution_var: Var

    def __post_init__(self) -> None:
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        _require_non_empty_str(self.occurrence_alias, field_name="occurrence_alias")
        _require_non_empty_str(self.port_name, field_name="port_name")
        if not isinstance(self.port_type, PortType):
            raise RuleExprError("RuleExprDeclaredPortBranchSource.port_type must be PortType")
        if not isinstance(self.alias_local_execution_var, Var):
            raise RuleExprError("RuleExprDeclaredPortBranchSource.alias_local_execution_var must be Var")


@dataclass(frozen=True)
class RuleExprDeclaredPort:
    name: str
    port_type: PortType
    branch_sources: tuple[RuleExprDeclaredPortBranchSource, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, field_name="name")
        if not isinstance(self.port_type, PortType):
            raise RuleExprError("RuleExprDeclaredPort.port_type must be PortType")
        _require_tuple(self.branch_sources, field_name="branch_sources", item_type=RuleExprDeclaredPortBranchSource)
        if not self.branch_sources:
            raise RuleExprError("RuleExprDeclaredPort.branch_sources must not be empty")


@dataclass(frozen=True)
class RuleExprHeadValidation:
    identity_state: Literal["external", "inline", "projection", "version-warning"]
    head_binding: RuleExprHeadBinding
    declared_ports: tuple[RuleExprDeclaredPort, ...]
    matched_occurrence_alias: str | None = None
    version_warning_emitted: bool = False

    def __post_init__(self) -> None:
        if self.identity_state not in {"external", "inline", "projection", "version-warning"}:
            raise RuleExprError("RuleExprHeadValidation.identity_state is unsupported")
        if not isinstance(self.head_binding, RuleExprHeadBinding):
            raise RuleExprError("RuleExprHeadValidation.head_binding must be RuleExprHeadBinding")
        _require_tuple(self.declared_ports, field_name="declared_ports", item_type=RuleExprDeclaredPort)
        if self.matched_occurrence_alias is not None:
            _require_non_empty_str(self.matched_occurrence_alias, field_name="matched_occurrence_alias")
        if not isinstance(self.version_warning_emitted, bool):
            raise RuleExprError("RuleExprHeadValidation.version_warning_emitted must be bool")
        if self.identity_state in {"external", "projection"} and self.matched_occurrence_alias is not None:
            raise RuleExprError("external/projection head validation must not set matched_occurrence_alias")
        if self.identity_state in {"inline", "version-warning"} and self.matched_occurrence_alias is None:
            raise RuleExprError("inline head validation requires matched_occurrence_alias")
        if self.identity_state != "version-warning" and self.version_warning_emitted:
            raise RuleExprError("version_warning_emitted requires version-warning identity_state")


def compile_derivation_plan(
    source: Rule | _RuleExpr,
    *,
    head: Rule,
    engine: str = "native",
) -> CompiledDerivationPlan:
    """Lower an application ``Rule`` or ``RuleExpr`` to a ``CompiledDerivationPlan``.

    This is a named facade over the lowering that already exists and is already
    exercised: the same two steps ``rule_program_runtime`` takes for every clause
    it compiles, and the same steps the adapters take for their engines. No
    lowering logic lives here.

    It exists so the capability shells can take the rule form the application
    layer authors anyway. Before this, that form was reachable only through
    callers that happened to be inside the package; the shells validated for the
    SDK ``Inference`` builder and had no way to reach the identical runtime with
    an equivalent rule.

    ``head`` is required: a ``Rule`` or ``RuleExpr`` says what holds, not what it
    concludes, and a default head would invent the conclusion.

    Args:
        source: Application Rule or composed RuleExpr to lower.
        head: Explicit conclusion/projection Rule.
        engine: Target engine materialization. Defaults to ``"native"``.

    Returns:
        A compiled derivation plan for the selected engine.

    Raises:
        RuleExprError: If source, head, joins, closure, or engine lowering is
            invalid.

    Notes:
        This advanced compiler surface does not execute the plan or read the
        ledger.
    """
    if isinstance(source, Rule):
        lowering = _lower_application_rule(source, head=head)
    elif isinstance(source, _RuleExpr):
        lowering = _lower_rule_expr(source, head=head)
    else:
        raise RuleExprError("source must be application protocol Rule or RuleExpr")
    if engine == "native":
        compiled, _traces = _materialize_native_derivation_plan(lowering)
        return compiled
    compiled, _traces = _materialize_adapter_derivation_plan(lowering, engine=engine)
    return compiled


def _lower_application_rule(rule: Rule, *, head: Rule) -> RuleExprLoweringPlan:
    if not isinstance(rule, Rule):
        raise RuleExprError("rule must be application protocol Rule")
    body = _build_body_plan(_coerce_rule_expr_operand(rule), source_kind="rule")
    return _attach_head(body, head=head)


def _lower_rule_expr(expr: _RuleExpr, *, head: Rule) -> RuleExprLoweringPlan:
    return _attach_head(_lower_rule_expr_body(expr), head=head)


def _lower_rule_expr_body(expr: _RuleExpr) -> _RuleExprBodyPlan:
    """Normalize and lower one RuleExpr without inventing a result head."""

    if not isinstance(expr, _RuleExpr):
        raise RuleExprError("expr must be RuleExpr")
    expr = _normalize_to_dnf(expr)
    return _build_body_plan(expr, source_kind="rule_expr")


def _materialize_native_derivation_plan(
    plan: RuleExprLoweringPlan,
) -> tuple[CompiledDerivationPlan, tuple[RuleExprEvaluationTrace, ...]]:
    return _materialize_adapter_derivation_plan(plan, engine="native")


def _materialize_adapter_derivation_plan(
    plan: RuleExprLoweringPlan,
    *,
    engine: RuleExprAdapterEngine,
) -> tuple[CompiledDerivationPlan, tuple[RuleExprEvaluationTrace, ...]]:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise RuleExprError("plan must be RuleExprLoweringPlan")
    if engine not in {"native", "souffle", "problog"}:
        raise RuleExprError("engine must be native, souffle, or problog")

    materialized_branches: list[list[object]] = []
    traces: list[RuleExprEvaluationTrace] = []
    head_vars = _head_var_names(plan)
    for runtime_case_index, branch in enumerate(plan.branches):
        body, joins, head_links, navigations, policy_conditions = _materialize_branch(branch, plan)
        materialized_branches.append(body)
        traces.append(
            RuleExprEvaluationTrace(
                canonical_key=plan.canonical_key,
                engine=engine,
                branch_id=branch.branch_id,
                runtime_case_index=runtime_case_index,
                occurrence_aliases=branch.occurrence_aliases,
                occurrence_map=plan.occurrence_map,
                join_materializations=joins,
                head_port_link_materializations=head_links,
                query_navigation_materializations=navigations,
                policy_condition_materializations=policy_conditions,
                head_binding=plan.head_binding,
            )
        )

    body_ir: list[object]
    if len(materialized_branches) == 1:
        body_ir = materialized_branches[0]
    else:
        body_ir = materialized_branches

    compiled = CompiledDerivationPlan(
        derivation_id=f"ruleexpr:{plan.head.id}",
        version=plan.head.version or "1.0",
        body_ir=body_ir,
        heads=(CompiledHeadCall(target_pred_id=plan.head.id, head_var_names=head_vars),),
    )
    return compiled, tuple(traces)


def _classify_pyreason_rule_expr_support(plan: RuleExprLoweringPlan) -> RuleExprAdapterSupport:
    """Classify PyReason support for materialized RuleExpr plans."""
    compiled, traces = _materialize_adapter_derivation_plan(plan, engine="native")
    branch_join_indexes = {
        trace.runtime_case_index: {join.materialized_condition_index for join in trace.join_materializations}
        for trace in traces
    }
    branches = _where_ir_branches(compiled.body_ir)
    if not branches:
        return _unsupported_pyreason("branch-shape", "branch-shape")
    for case_index, branch in enumerate(branches):
        for condition_index, atom in enumerate(branch):
            unsupported = _pyreason_unsupported_atom(
                atom,
                is_join_atom=condition_index in branch_join_indexes.get(case_index, set()),
            )
            if unsupported is not None:
                source, feature = unsupported
                return _unsupported_pyreason(source, feature)
    return RuleExprAdapterSupport(engine="pyreason", supported=True)


def _validate_rule_expr_head_foundation(plan: RuleExprLoweringPlan) -> RuleExprHeadValidation:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise RuleExprError("plan must be RuleExprLoweringPlan")
    if plan.query_navigation_lookups:
        # A Query navigation produces a compiler-local scalar, not a Rule port.
        # Do not fabricate a ``RuleExprDeclaredPortBranchSource`` merely to fit
        # the legacy head-validation model: that DTO means an authored reusable
        # Rule interface.  Query-extension validation already proves complete
        # projection coverage; the empty declared-port inventory is deliberate.
        if plan.head_binding.kind != "projection":
            raise RuleExprError("query navigation requires a projection head")
        return RuleExprHeadValidation(
            identity_state="projection",
            head_binding=plan.head_binding,
            declared_ports=(),
        )
    declared_ports, partial_ports = _declared_port_state_for_rule_expr_plan(plan)
    if plan.head_binding.kind == "projection":
        _validate_head_declared_ports(plan.head, declared_ports, partial_ports=partial_ports, compare_port_types=False)
        return RuleExprHeadValidation(
            identity_state="projection",
            head_binding=plan.head_binding,
            declared_ports=declared_ports,
        )

    exact_matches = [
        occurrence
        for occurrence in plan.occurrence_map
        if occurrence.rule_id == plan.head.id and occurrence.content_digest == plan.head.content_digest
    ]
    stale_matches = [
        occurrence
        for occurrence in plan.occurrence_map
        if occurrence.rule_id == plan.head.id and occurrence.content_digest != plan.head.content_digest
    ]
    if stale_matches:
        raise RuleExprError(
            f"head rule {plan.head.id!r} matches an expression occurrence with a different content digest"
        )
    if len(exact_matches) > 1:
        raise RuleExprError(
            f"head rule {plan.head.id!r} matches multiple expression occurrences with the same content digest"
        )

    _validate_head_declared_ports(plan.head, declared_ports, partial_ports=partial_ports, compare_port_types=True)

    if not exact_matches:
        return RuleExprHeadValidation(
            identity_state="external",
            head_binding=plan.head_binding,
            declared_ports=declared_ports,
        )

    occurrence = exact_matches[0]
    if occurrence.rule_version != plan.head.version:
        warnings.warn(
            f"head rule {plan.head.id!r} matches expression occurrence {occurrence.alias!r} "
            "by id and content digest but has a different version",
            UserWarning,
            stacklevel=2,
        )
        return RuleExprHeadValidation(
            identity_state="version-warning",
            head_binding=plan.head_binding,
            declared_ports=declared_ports,
            matched_occurrence_alias=occurrence.alias,
            version_warning_emitted=True,
        )

    return RuleExprHeadValidation(
        identity_state="inline",
        head_binding=plan.head_binding,
        declared_ports=declared_ports,
        matched_occurrence_alias=occurrence.alias,
    )


def _declared_ports_for_rule_expr_plan(plan: RuleExprLoweringPlan) -> tuple[RuleExprDeclaredPort, ...]:
    declared_ports, _partial_ports = _declared_port_state_for_rule_expr_plan(plan)
    return declared_ports


def probe_seed_vars_by_head_port(plan: RuleExprLoweringPlan) -> dict[str, tuple[str, ...]]:
    """Return every lowered variable that should receive each result-row head value."""
    if not isinstance(plan, RuleExprLoweringPlan):
        raise RuleExprError("plan must be RuleExprLoweringPlan")

    out: dict[str, list[str]] = {port_name: [] for port_name in plan.head.ports}

    def add(port_name: str, var_name: str) -> None:
        if port_name not in out:
            return
        if var_name not in out[port_name]:
            out[port_name].append(var_name)

    for port_name, var_name in zip(plan.head.ports, _head_var_names(plan), strict=True):
        add(port_name, var_name)

    if plan.query_head_links or plan.query_navigation_lookups:
        for link in plan.query_head_links:
            query_source = _query_port_binding(plan, link.branch_id, link.occurrence_alias, link.port_name)
            add(link.head_port_name, query_source.alias_local_execution_var.name)
        for lookup in plan.query_navigation_lookups:
            add(lookup.head_port_name, _query_navigation_lookup_var(lookup).name)
        return {port_name: tuple(var_names) for port_name, var_names in out.items()}

    for port_name in plan.head.ports:
        for branch in plan.branches:
            source = _branch_declared_port_source_for_name(branch, plan.occurrence_map, port_name)
            if source is not None:
                add(port_name, source.alias_local_execution_var.name)
    for branch in plan.branches:
        for alias in branch.occurrence_aliases:
            occurrence = _occurrence_binding(plan.occurrence_map, alias)
            for binding in occurrence.port_bindings:
                if binding.port_name in plan.head.ports:
                    add(binding.port_name, binding.alias_local_execution_var.name)

    for port_name, head_var in plan.head.ports.items():
        source_name = head_var.name
        for occurrence in plan.occurrence_map:
            for binding in occurrence.port_bindings:
                if binding.source_var.name == source_name:
                    add(port_name, binding.alias_local_execution_var.name)

    return {port_name: tuple(var_names) for port_name, var_names in out.items()}


def transitively_expand_seed(
    valued: dict[str, object],
    branches: list[list[tuple[object, ...]]],
) -> dict[str, object]:
    """Expand a base ``{var: value}`` reach seed over the eq-atom graph.

    ``probe_seed_vars_by_head_port`` seeds only vars whose occurrence exposes a
    *head* port (the head var + the head-exposing occurrence, e.g. ``colleagues``).
    An occurrence-local var reached only through a cross-occurrence join (e.g.
    ``works_b``'s subject, joined to the head via ``colleagues.B = works_b.Ub``)
    is NOT seeded by the base probe — and because lowering appends the join /
    head-link eq-atoms *after* the occurrence bodies, such a var runs free in the
    linear reach chain, producing unfaithful per-atom verdicts for a non-holding
    subject (a false culprit, or a masked culprit bound to the wrong entity).

    This propagates each seeded value along the eq-atoms that link two lowered
    vars (the join + head-link equalities the materialized body already carries),
    to a fixpoint, so every var transitively pinned by a head port is scoped. An
    eq-atom whose two endpoints are both unseeded (a purely existential join,
    e.g. ``works_a.Pa = works_b.Pb`` with neither project pinned) stays dormant —
    both vars remain free for the engine to search. The base seed is only
    extended, never narrowed; both-seeded endpoints are left untouched (they
    derive from the same head port and so already agree).
    """
    expanded: dict[str, object] = dict(valued)
    edges: list[tuple[str, str]] = []
    for atoms in branches:
        for atom in atoms:
            if (
                isinstance(atom, tuple)
                and len(atom) == 3
                and atom[0] == "eq"
                and isinstance(atom[1], str)
                and atom[1].startswith("$")
                and isinstance(atom[2], str)
                and atom[2].startswith("$")
            ):
                edges.append((atom[1], atom[2]))
    changed = True
    while changed:
        changed = False
        for lhs, rhs in edges:
            lhs_seeded = lhs in expanded
            rhs_seeded = rhs in expanded
            if lhs_seeded and not rhs_seeded:
                expanded[rhs] = expanded[lhs]
                changed = True
            elif rhs_seeded and not lhs_seeded:
                expanded[lhs] = expanded[rhs]
                changed = True
    return expanded


def _branch_declared_port_source_for_name(
    branch: RuleExprLoweringBranch,
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
    name: str,
) -> RuleExprDeclaredPortBranchSource | None:
    bindings = [
        binding
        for alias in branch.occurrence_aliases
        for binding in _occurrence_binding(occurrence_map, alias).port_bindings
        if binding.port_name == name
    ]
    if not bindings:
        return None
    if len(bindings) == 1:
        return _branch_source(branch.branch_id, bindings[0])
    if any(binding.port_type != bindings[0].port_type for binding in bindings):
        raise RuleExprError(f"declared port {name!r} has incompatible same-name port types")
    if not _same_name_bindings_are_joined(name, bindings, branch.pending_joins, occurrence_map):
        aliases = ", ".join(sorted(binding.occurrence_alias for binding in bindings))
        raise RuleExprError(f"declared port {name!r} is ambiguous across occurrences: {aliases}")
    return _branch_source(branch.branch_id, min(bindings, key=_binding_sort_key))


def _declared_port_state_for_rule_expr_plan(
    plan: RuleExprLoweringPlan,
) -> tuple[tuple[RuleExprDeclaredPort, ...], frozenset[str]]:
    if not isinstance(plan, RuleExprLoweringPlan):
        raise RuleExprError("plan must be RuleExprLoweringPlan")
    if plan.query_navigation_lookups:
        # A navigation source has no authored Rule-port equivalent.  Returning
        # an empty inventory preserves that boundary for both navigation-only
        # and mixed projections; the query-extension validator separately
        # proves total projection coverage.
        return (), frozenset()
    if plan.query_head_links:
        query_declared: list[RuleExprDeclaredPort] = []
        for port_name in sorted(plan.head.ports):
            query_sources: list[RuleExprDeclaredPortBranchSource] = []
            for branch in plan.branches:
                direct = next(
                    (
                        item
                        for item in plan.query_head_links
                        if item.branch_id == branch.branch_id and item.head_port_name == port_name
                    ),
                    None,
                )
                if direct is not None:
                    binding = _query_port_binding(
                        plan, branch.branch_id, direct.occurrence_alias, direct.port_name
                    )
                    query_sources.append(_branch_source(branch.branch_id, binding))
                    continue
                raise RuleExprError("query projection is missing a direct branch source")
            port_type = query_sources[0].port_type
            if any(source.port_type != port_type for source in query_sources):
                raise RuleExprError(f"query selection {port_name!r} has incompatible branch types")
            query_declared.append(RuleExprDeclaredPort(port_name, port_type, tuple(query_sources)))
        return tuple(query_declared), frozenset()
    by_branch: list[dict[str, RuleExprDeclaredPortBranchSource]] = []
    seen_names: set[str] = set()
    for branch in plan.branches:
        branch_ports = _branch_declared_port_sources(branch, plan.occurrence_map)
        by_branch.append(branch_ports)
        seen_names.update(branch_ports)

    declared: list[RuleExprDeclaredPort] = []
    partial: set[str] = set()
    for name in sorted(seen_names):
        sources = [branch_ports.get(name) for branch_ports in by_branch]
        if any(source is None for source in sources):
            partial.add(name)
            continue
        resolved_sources = tuple(source for source in sources if source is not None)
        port_type = resolved_sources[0].port_type
        if any(source.port_type != port_type for source in resolved_sources):
            raise RuleExprError(f"declared port {name!r} has incompatible port types across branches")
        declared.append(RuleExprDeclaredPort(name=name, port_type=port_type, branch_sources=resolved_sources))
    return tuple(declared), frozenset(partial)


def _branch_declared_port_sources(
    branch: RuleExprLoweringBranch,
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
) -> dict[str, RuleExprDeclaredPortBranchSource]:
    bindings_by_name: dict[str, list[RuleExprPortBinding]] = {}
    for alias in branch.occurrence_aliases:
        occurrence = _occurrence_binding(occurrence_map, alias)
        for binding in occurrence.port_bindings:
            bindings_by_name.setdefault(binding.port_name, []).append(binding)

    declared: dict[str, RuleExprDeclaredPortBranchSource] = {}
    for name, bindings in bindings_by_name.items():
        if len(bindings) == 1:
            declared[name] = _branch_source(branch.branch_id, bindings[0])
            continue
        if any(binding.port_type != bindings[0].port_type for binding in bindings):
            raise RuleExprError(f"declared port {name!r} has incompatible same-name port types")
        if not _same_name_bindings_are_joined(name, bindings, branch.pending_joins, occurrence_map):
            aliases = ", ".join(sorted(binding.occurrence_alias for binding in bindings))
            raise RuleExprError(f"declared port {name!r} is ambiguous across occurrences: {aliases}")
        declared[name] = _branch_source(branch.branch_id, min(bindings, key=_binding_sort_key))
    return declared


def _same_name_bindings_are_joined(
    port_name: str,
    bindings: list[RuleExprPortBinding],
    joins: tuple[RuleJoinConstraint, ...],
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
) -> bool:
    aliases = {binding.occurrence_alias for binding in bindings}
    if len(aliases) != len(bindings):
        return False
    graph: dict[str, set[str]] = {alias: set() for alias in aliases}
    unique_joins: dict[tuple[object, ...], RuleJoinConstraint] = {}
    for join in joins:
        unique_joins.setdefault(_canonical_join_constraint(join), join)
    for join_key in sorted(unique_joins, key=repr):
        join = unique_joins[join_key]
        left = _resolve_endpoint(join.left, occurrence_map)
        right = _resolve_endpoint(join.right, occurrence_map)
        if left.port_name != port_name or right.port_name != port_name:
            continue
        if left.occurrence_alias not in aliases or right.occurrence_alias not in aliases:
            continue
        if left.port_type != right.port_type:
            raise RuleExprError(f"declared port {port_name!r} has incompatible same-name port types")
        graph[left.occurrence_alias].add(right.occurrence_alias)
        graph[right.occurrence_alias].add(left.occurrence_alias)

    remaining = set(aliases)
    stack = [next(iter(remaining))]
    while stack:
        alias = stack.pop()
        if alias not in remaining:
            continue
        remaining.remove(alias)
        stack.extend(graph[alias])
    return not remaining


def _validate_head_declared_ports(
    head: Rule,
    declared_ports: tuple[RuleExprDeclaredPort, ...],
    *,
    partial_ports: frozenset[str],
    compare_port_types: bool = True,
) -> None:
    declared_by_name = {port.name: port for port in declared_ports}
    issues: list[str] = []
    for name, head_var in head.ports.items():
        declared = declared_by_name.get(name)
        if declared is None:
            if name in partial_ports:
                issues.append(f"head port {name!r} is only declared in some RuleExpr branches")
            else:
                issues.append(f"head port {name!r} is not declared by the RuleExpr")
            continue
        if compare_port_types:
            head_type = head.port_types[name]
            if declared.port_type != head_type:
                issues.append(f"head port {name!r} type {head_type!r} does not match RuleExpr port type {declared.port_type!r}")
        if not isinstance(head_var, Var):
            issues.append(f"head port {name!r} is not backed by a Var")
    if issues:
        raise RuleExprError("RuleExpr head validation failed: " + "; ".join(issues))


def _branch_source(branch_id: str, binding: RuleExprPortBinding) -> RuleExprDeclaredPortBranchSource:
    return RuleExprDeclaredPortBranchSource(
        branch_id=branch_id,
        occurrence_alias=binding.occurrence_alias,
        port_name=binding.port_name,
        port_type=binding.port_type,
        alias_local_execution_var=binding.alias_local_execution_var,
    )


def _binding_sort_key(binding: RuleExprPortBinding) -> tuple[str, str]:
    return (binding.occurrence_alias, binding.port_name)


def _evaluate_rule_expr_native_for_tests(
    expr: _RuleExpr,
    *,
    head: Rule,
    store: Store,
) -> list[DerivationOutput]:
    plan = _lower_rule_expr(expr, head=head)
    compiled, _traces = _materialize_native_derivation_plan(plan)
    return evaluate_derivation_plans(DerivationEvaluateRequest(plans=(compiled,), engine="native"), store=store)


def _normalize_to_dnf(expr: _RuleExpr) -> _RuleExpr:
    branches = _rewrite_dnf_aliases(_dnf_branches(expr))
    if len(branches) == 1:
        return _branch_to_expr(branches[0])
    return _OrGroup(tuple(_branch_to_expr(branch) for branch in branches))


def _dnf_branches(expr: _RuleExpr) -> tuple[_DNFBranch, ...]:
    if isinstance(expr, _RuleOperand):
        return (_DNFBranch(operands=(expr,)),)
    if isinstance(expr, _OrGroup):
        branches: list[_DNFBranch] = []
        for child in expr.children:
            branches.extend(_dnf_branches(child))
            _validate_dnf_branch_count(len(branches))
        return tuple(branches)
    if isinstance(expr, _AndGroup):
        child_branch_sets = tuple(_dnf_branches(child) for child in expr.children)
        branches: list[_DNFBranch] = []
        for branch_product in product(*child_branch_sets):
            operands: list[_RuleOperand] = []
            joins: list[RuleJoinConstraint] = []
            for branch in branch_product:
                operands.extend(branch.operands)
                joins.extend(branch.joins)
            aliases = {operand.alias for operand in operands}
            joins.extend(_join for _join in expr.joins if _join_applies_to_aliases(_join, aliases))
            branches.append(_DNFBranch(operands=tuple(operands), joins=_normalize_join_constraints(joins)))
            _validate_dnf_branch_count(len(branches))
        return tuple(branches)
    raise RuleExprError(f"unsupported RuleExpr node: {type(expr).__name__}")


def _validate_dnf_branch_count(count: int) -> None:
    if count > _DNF_BRANCH_LIMIT:
        raise RuleExprError(
            f"RuleExpr DNF normalization produced {count} branches; maximum supported is {_DNF_BRANCH_LIMIT}"
        )


def _join_applies_to_aliases(join: RuleJoinConstraint, aliases: set[str]) -> bool:
    return join.left.occurrence_alias in aliases and join.right.occurrence_alias in aliases


def _rewrite_dnf_aliases(branches: tuple[_DNFBranch, ...]) -> tuple[_DNFBranch, ...]:
    alias_counts: dict[str, int] = {}
    for branch in branches:
        for operand in branch.operands:
            alias_counts[operand.alias] = alias_counts.get(operand.alias, 0) + 1
    repeated = {alias for alias, count in alias_counts.items() if count > 1}
    if not repeated:
        return branches

    used_aliases = {operand.alias for branch in branches for operand in branch.operands}
    rewritten: list[_DNFBranch] = []
    for branch_index, branch in enumerate(branches):
        alias_map: dict[str, str] = {}
        operands: list[_RuleOperand] = []
        for operand in branch.operands:
            alias = operand.alias
            authored_alias = operand.authored_alias
            if alias in repeated:
                alias = _generated_branch_alias(operand.alias, branch_index, used_aliases)
                alias_map[operand.alias] = alias
                authored_alias = operand.authored_alias or operand.alias
            operands.append(
                _RuleOperand(
                    rule=operand.rule,
                    alias=alias,
                    explicit_alias=True if operand.alias in repeated else operand.explicit_alias,
                    authored_alias=authored_alias,
                )
            )
        joins = tuple(_rewrite_join_aliases(join, alias_map) for join in branch.joins)
        rewritten.append(_DNFBranch(operands=tuple(operands), joins=_normalize_join_constraints(joins)))
    return tuple(rewritten)


def _generated_branch_alias(alias: str, branch_index: int, used_aliases: set[str]) -> str:
    candidate = f"{alias}__c{branch_index}"
    if candidate not in used_aliases:
        used_aliases.add(candidate)
        return candidate
    suffix = 1
    while True:
        alternate = f"{candidate}_{suffix}"
        if alternate not in used_aliases:
            used_aliases.add(alternate)
            return alternate
        suffix += 1


def _rewrite_join_aliases(join: RuleJoinConstraint, alias_map: dict[str, str]) -> RuleJoinConstraint:
    return RuleJoinConstraint(
        left=_rewrite_join_endpoint(join.left, alias_map),
        right=_rewrite_join_endpoint(join.right, alias_map),
        op=join.op,
    )


def _rewrite_join_endpoint(ref: RulePortRef, alias_map: dict[str, str]) -> RulePortRef:
    alias = alias_map.get(ref.occurrence_alias)
    if alias is None:
        return ref
    return RulePortRef(
        occurrence_alias=alias,
        rule_id=ref.rule_id,
        port_name=ref.port_name,
        var=ref.var,
        port_type=ref.port_type,
    )


def _branch_to_expr(branch: _DNFBranch) -> _RuleExpr:
    if len(branch.operands) == 1 and not branch.joins:
        return branch.operands[0]
    return _AndGroup(children=branch.operands, joins=branch.joins)


def _build_body_plan(
    expr: _RuleExpr,
    *,
    source_kind: Literal["rule", "rule_expr"],
) -> _RuleExprBodyPlan:
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding] = {}
    branches = _assign_branch_ids(_lower_expr(expr, occurrence_map_by_alias, path=()))
    occurrence_map = tuple(occurrence_map_by_alias[alias] for alias in sorted(occurrence_map_by_alias))
    return _RuleExprBodyPlan(
        source_kind=source_kind,
        branches=branches,
        occurrence_map=occurrence_map,
        canonical_key=(source_kind, expr._canonical()),
    )


def _attach_head(body: _RuleExprBodyPlan, *, head: Rule) -> RuleExprLoweringPlan:
    if not isinstance(body, _RuleExprBodyPlan):
        raise RuleExprError("body must be _RuleExprBodyPlan")
    if not isinstance(head, Rule):
        raise RuleExprError("head must be application protocol Rule")
    head_binding = _head_binding(head, body.occurrence_map)
    return RuleExprLoweringPlan(
        source_kind=body.source_kind,
        head=head,
        head_binding=head_binding,
        branches=body.branches,
        occurrence_map=body.occurrence_map,
        canonical_key=(*body.canonical_key, head_binding.kind, head.id, head.content_digest),
    )


def _attach_evaluation_query_head(
    body: _RuleExprBodyPlan,
    *,
    head: Rule,
    query_digest: str,
    head_links: tuple[_RuleExprQueryHeadLink, ...],
    value_bindings: tuple[_RuleExprQueryValueBinding, ...],
    navigation_lookups: tuple[_RuleExprQueryNavigationLookup, ...] = (),
    policy_conditions: tuple[RuleExprPolicyCondition, ...] = (),
) -> RuleExprLoweringPlan:
    """Attach exact query projection metadata without changing legacy plans."""

    _require_non_empty_str(query_digest, field_name="query_digest")
    base = _attach_head(body, head=head)
    return replace(
        base,
        canonical_key=(*base.canonical_key, "evaluation_query_v0", query_digest),
        query_head_links=tuple(sorted(head_links)),
        query_value_bindings=tuple(
            sorted(value_bindings, key=lambda item: (item.branch_id, item.occurrence_alias, item.port_name))
        ),
        query_navigation_lookups=tuple(sorted(navigation_lookups)),
        # Condition ids are stable authored/compiler coordinates, but their
        # lexical order is deliberately not the evaluation order.  A field
        # lookup has to bind before the comparison which consumes it.
        policy_conditions=tuple(sorted(policy_conditions, key=_policy_condition_sort_key)),
    )


def _build_lowering_plan(
    expr: _RuleExpr,
    *,
    head: Rule,
    source_kind: Literal["rule", "rule_expr"],
) -> RuleExprLoweringPlan:
    """Compatibility helper for internal callers that already provide normalized input."""

    return _attach_head(_build_body_plan(expr, source_kind=source_kind), head=head)


def _lower_expr(
    expr: _RuleExpr,
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding],
    *,
    path: tuple[int, ...],
) -> tuple[RuleExprLoweringBranch, ...]:
    if isinstance(expr, _RuleOperand):
        return (_lower_operand(expr, occurrence_map_by_alias, path=path),)
    if isinstance(expr, _AndGroup):
        return _lower_and(expr, occurrence_map_by_alias, path=path)
    if isinstance(expr, _OrGroup):
        return _lower_or(expr, occurrence_map_by_alias, path=path)
    raise RuleExprError(f"unsupported RuleExpr node: {type(expr).__name__}")


def _lower_operand(
    operand: _RuleOperand,
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding],
    *,
    path: tuple[int, ...],
) -> RuleExprLoweringBranch:
    alias_var_map = _alias_var_map(operand.alias, operand.rule.when)
    body_atoms = tuple(_rewrite_atom(atom, alias_var_map) for atom in operand.rule.when)
    port_bindings = tuple(
        RuleExprPortBinding(
            occurrence_alias=operand.alias,
            port_name=name,
            port_type=operand.rule.port_types[name],
            source_var=source_var,
            alias_local_execution_var=alias_var_map[source_var],
        )
        for name, source_var in operand.rule.ports.items()
    )
    binding = RuleExprOccurrenceBinding(
        alias=operand.alias,
        rule_id=operand.rule.id,
        content_digest=operand.rule.content_digest,
        port_bindings=port_bindings,
        rule_version=operand.rule.version,
        authored_alias=operand.authored_alias,
    )
    existing = occurrence_map_by_alias.get(operand.alias)
    if existing is not None and existing != binding:
        raise RuleExprError(f"duplicate occurrence binding for alias {operand.alias!r}")
    occurrence_map_by_alias[operand.alias] = binding
    return RuleExprLoweringBranch(
        branch_id="",
        path=path,
        occurrence_aliases=(operand.alias,),
        body_atoms=body_atoms,
    )


def _lower_and(
    group: _AndGroup,
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding],
    *,
    path: tuple[int, ...],
) -> tuple[RuleExprLoweringBranch, ...]:
    child_sets = [
        _lower_expr(child, occurrence_map_by_alias, path=(*path, idx))
        for idx, child in enumerate(_canonical_children(group.children))
    ]
    branches: list[RuleExprLoweringBranch] = []
    for branch_product in product(*child_sets):
        branches.append(_concat_branches(branch_product, pending_joins=group.joins))
    return tuple(branches)


def _lower_or(
    group: _OrGroup,
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding],
    *,
    path: tuple[int, ...],
) -> tuple[RuleExprLoweringBranch, ...]:
    branches: list[RuleExprLoweringBranch] = []
    for idx, child in enumerate(_canonical_children(group.children)):
        branches.extend(_lower_expr(child, occurrence_map_by_alias, path=(*path, idx)))
    return tuple(branches)


def _concat_branches(
    branches: tuple[RuleExprLoweringBranch, ...],
    *,
    pending_joins: tuple[RuleJoinConstraint, ...],
) -> RuleExprLoweringBranch:
    if not branches:
        raise RuleExprError("AND branch product must not be empty")
    body_atoms: list[Atom] = []
    aliases: list[str] = []
    path: list[int] = []
    joins: list[RuleJoinConstraint] = []
    for branch in branches:
        body_atoms.extend(branch.body_atoms)
        aliases.extend(branch.occurrence_aliases)
        path.extend(branch.path)
        joins.extend(branch.pending_joins)
    joins.extend(pending_joins)
    return RuleExprLoweringBranch(
        branch_id="",
        path=tuple(path),
        occurrence_aliases=tuple(aliases),
        body_atoms=tuple(body_atoms),
        pending_joins=tuple(dict.fromkeys(joins)),
    )


def _assign_branch_ids(branches: tuple[RuleExprLoweringBranch, ...]) -> tuple[RuleExprLoweringBranch, ...]:
    if not branches:
        raise RuleExprError("RuleExpr lowering produced no branches")
    return tuple(replace(branch, branch_id=f"c{idx}") for idx, branch in enumerate(branches))


def _materialize_branch(
    branch: RuleExprLoweringBranch,
    plan: RuleExprLoweringPlan,
) -> tuple[
    list[object],
    tuple[RuleExprJoinMaterialization, ...],
    tuple[RuleExprHeadPortLinkMaterialization, ...],
    tuple[RuleExprQueryNavigationMaterialization, ...],
    tuple[RuleExprPolicyConditionMaterialization, ...],
]:
    materialized_atoms: list[Atom] = list(branch.body_atoms)
    if plan.head_binding.kind == "external":
        head_var_map = _head_alias_var_map(plan.head)
        materialized_atoms.extend(_rewrite_atom(atom, head_var_map) for atom in plan.head.when)

    policy_conditions: list[RuleExprPolicyConditionMaterialization] = []
    for condition in plan.policy_conditions:
        if condition.branch_id != branch.branch_id:
            continue
        materialized_index = len(materialized_atoms)
        materialized_atoms.append(condition.atom)
        policy_conditions.append(
            RuleExprPolicyConditionMaterialization(
                branch_id=branch.branch_id,
                policy_node_id=condition.policy_node_id,
                condition_id=condition.condition_id,
                role=condition.role,
                materialized_condition_index=materialized_index,
            )
        )

    for query_binding in plan.query_value_bindings:
        if query_binding.branch_id != branch.branch_id:
            continue
        query_source = _query_port_binding(plan, branch.branch_id, query_binding.occurrence_alias, query_binding.port_name)
        materialized_atoms.append(CmpAtom(op="eq", lhs=query_source.alias_local_execution_var, rhs=query_binding.value))

    # Query-owned field navigation is deliberately materialized after direct
    # Query bindings and before joins.  It is neither an authored Rule atom nor
    # a Policy condition: the trace below gives Explain/F4 an explicit ownership
    # boundary instead of trying to infer one from generated variable names.
    navigation_vars: dict[str, tuple[_RuleExprQueryNavigationLookup, Var, int]] = {}
    for lookup in plan.query_navigation_lookups:
        if lookup.branch_id != branch.branch_id:
            continue
        if lookup.head_port_name in navigation_vars:
            raise RuleExprError("query navigation duplicates a projection head port")
        query_source = _query_port_binding(
            plan, branch.branch_id, lookup.occurrence_alias, lookup.port_name
        )
        lookup_var = _query_navigation_lookup_var(lookup)
        materialized_index = len(materialized_atoms)
        materialized_atoms.append(
            PredAtom(
                lookup.field_predicate_id,
                [query_source.alias_local_execution_var, lookup_var],
            )
        )
        navigation_vars[lookup.head_port_name] = (lookup, lookup_var, materialized_index)

    joins: list[RuleExprJoinMaterialization] = []
    unique_joins: dict[tuple[object, ...], RuleJoinConstraint] = {}
    for join in branch.pending_joins:
        unique_joins.setdefault(_canonical_join_constraint(join), join)
    for join_key in sorted(unique_joins, key=repr):
        join = unique_joins[join_key]
        left = _resolve_endpoint(join.left, plan.occurrence_map)
        right = _resolve_endpoint(join.right, plan.occurrence_map)
        if left.port_type != right.port_type:
            raise RuleExprError("join endpoint port types are incompatible")
        materialized_index = len(materialized_atoms)
        materialized_atoms.append(
            CmpAtom(
                op="eq",
                lhs=left.alias_local_execution_var,
                rhs=right.alias_local_execution_var,
            )
        )
        joins.append(
            RuleExprJoinMaterialization(
                branch_id=branch.branch_id,
                join_key=join_key,
                left_occurrence_alias=join.left.occurrence_alias,
                left_port_name=join.left.port_name,
                right_occurrence_alias=join.right.occurrence_alias,
                right_port_name=join.right.port_name,
                materialized_condition_index=materialized_index,
            )
        )

    head_links: list[RuleExprHeadPortLinkMaterialization] = []
    navigations: list[RuleExprQueryNavigationMaterialization] = []
    if plan.head_binding.kind in {"external", "projection"}:
        is_query_projection = plan.head_binding.kind == "projection" and (
            plan.query_head_links or plan.query_navigation_lookups
        )
        if is_query_projection:
            declared_by_name: dict[str, RuleExprDeclaredPort] = {}
        else:
            declared_ports, partial_ports = _declared_port_state_for_rule_expr_plan(plan)
            _validate_head_declared_ports(
                plan.head,
                declared_ports,
                partial_ports=partial_ports,
                compare_port_types=plan.head_binding.kind != "projection",
            )
            declared_by_name = {port.name: port for port in declared_ports}
        head_var_map = _head_alias_var_map(plan.head) if plan.head_binding.kind == "external" else None
        for port_name in sorted(plan.head.ports):
            head_var = plan.head.ports[port_name]
            lhs = head_var_map[head_var] if head_var_map is not None else head_var
            navigation = navigation_vars.get(port_name)
            if navigation is not None:
                lookup, lookup_var, lookup_index = navigation
                materialized_index = len(materialized_atoms)
                materialized_atoms.append(CmpAtom(op="eq", lhs=lhs, rhs=lookup_var))
                navigations.append(
                    RuleExprQueryNavigationMaterialization(
                        branch_id=branch.branch_id,
                        head_port_name=port_name,
                        base_occurrence_alias=lookup.occurrence_alias,
                        base_port_name=lookup.port_name,
                        field_predicate_id=lookup.field_predicate_id,
                        lookup_var_name=lookup_var.name,
                        lookup_materialized_condition_index=lookup_index,
                        projection_head_link_materialized_condition_index=materialized_index,
                    )
                )
                continue
            if is_query_projection:
                direct = next(
                    (
                        item
                        for item in plan.query_head_links
                        if item.branch_id == branch.branch_id and item.head_port_name == port_name
                    ),
                    None,
                )
                if direct is None:
                    raise RuleExprError("query projection is missing a direct head source")
                source_binding = _query_port_binding(
                    plan,
                    branch.branch_id,
                    direct.occurrence_alias,
                    direct.port_name,
                )
                materialized_index = len(materialized_atoms)
                materialized_atoms.append(
                    CmpAtom(op="eq", lhs=lhs, rhs=source_binding.alias_local_execution_var)
                )
                head_links.append(
                    RuleExprHeadPortLinkMaterialization(
                        branch_id=branch.branch_id,
                        head_port_name=port_name,
                        source_occurrence_alias=source_binding.occurrence_alias,
                        source_port_name=source_binding.port_name,
                        materialized_condition_index=materialized_index,
                    )
                )
                continue
            declared = declared_by_name[port_name]
            source = _declared_port_branch_source(declared, branch.branch_id)
            materialized_index = len(materialized_atoms)
            materialized_atoms.append(CmpAtom(op="eq", lhs=lhs, rhs=source.alias_local_execution_var))
            head_links.append(
                RuleExprHeadPortLinkMaterialization(
                    branch_id=branch.branch_id,
                    head_port_name=port_name,
                    source_occurrence_alias=source.occurrence_alias,
                    source_port_name=source.port_name,
                    materialized_condition_index=materialized_index,
                )
            )

    return (
        lower_ast_to_where_ir(AndExpr(materialized_atoms)),
        tuple(joins),
        tuple(head_links),
        tuple(navigations),
        tuple(policy_conditions),
    )


def _declared_port_branch_source(
    declared_port: RuleExprDeclaredPort,
    branch_id: str,
) -> RuleExprDeclaredPortBranchSource:
    for source in declared_port.branch_sources:
        if source.branch_id == branch_id:
            return source
    raise RuleExprError(f"declared port {declared_port.name!r} is missing branch source {branch_id!r}")


def _resolve_endpoint(
    endpoint: object,
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
) -> RuleExprPortBinding:
    matches = [
        binding
        for occurrence in occurrence_map
        for binding in occurrence.port_bindings
        if binding.occurrence_alias == getattr(endpoint, "occurrence_alias", None)
        and binding.port_name == getattr(endpoint, "port_name", None)
    ]
    if len(matches) != 1:
        raise RuleExprError("join endpoint did not resolve to exactly one port binding")
    binding = matches[0]
    if binding.source_var != getattr(endpoint, "var", None):
        raise RuleExprError("join endpoint source var does not match port binding")
    if binding.port_type != getattr(endpoint, "port_type", None):
        raise RuleExprError("join endpoint port type does not match port binding")
    return binding


def _head_binding(head: Rule, occurrence_map: tuple[RuleExprOccurrenceBinding, ...]) -> RuleExprHeadBinding:
    if _is_projection_rule(head):
        return RuleExprHeadBinding(
            kind="projection",
            head_rule_id=head.id,
            head_content_digest=head.content_digest,
        )
    matches = [
        occurrence.alias
        for occurrence in occurrence_map
        if occurrence.rule_id == head.id and occurrence.content_digest == head.content_digest
    ]
    if len(matches) > 1:
        raise RuleExprError("head rule matches multiple inline occurrences")
    if matches:
        return RuleExprHeadBinding(
            kind="inline",
            head_rule_id=head.id,
            head_content_digest=head.content_digest,
            projection_occurrence_alias=matches[0],
        )
    return RuleExprHeadBinding(
        kind="external",
        head_rule_id=head.id,
        head_content_digest=head.content_digest,
    )


def _head_var_names(plan: RuleExprLoweringPlan) -> tuple[str, ...]:
    if plan.head_binding.kind == "projection":
        return tuple(var.name for var in plan.head.ports.values())
    if plan.head_binding.kind == "external":
        head_var_map = _head_alias_var_map(plan.head)
        return tuple(head_var_map[var].name for var in plan.head.ports.values())
    if plan.head_binding.projection_occurrence_alias is None:
        raise RuleExprError("inline head binding requires projection occurrence alias")
    occurrence = _occurrence_binding(plan.occurrence_map, plan.head_binding.projection_occurrence_alias)
    names: list[str] = []
    for port_name in plan.head.ports:
        binding = _port_binding(occurrence, port_name)
        names.append(binding.alias_local_execution_var.name)
    return tuple(names)


def _head_alias_var_map(head: Rule) -> dict[Var, Var]:
    return _alias_var_map("__head", head.when)


def _occurrence_binding(
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
    alias: str,
) -> RuleExprOccurrenceBinding:
    for occurrence in occurrence_map:
        if occurrence.alias == alias:
            return occurrence
    raise RuleExprError(f"head projection occurrence {alias!r} is missing")


def _port_binding(occurrence: RuleExprOccurrenceBinding, port_name: str) -> RuleExprPortBinding:
    for binding in occurrence.port_bindings:
        if binding.port_name == port_name:
            return binding
    raise RuleExprError(f"head port {port_name!r} is missing from projection occurrence")


def _query_port_binding(
    plan: RuleExprLoweringPlan,
    branch_id: str,
    occurrence_alias: str,
    port_name: str,
) -> RuleExprPortBinding:
    branch = next((item for item in plan.branches if item.branch_id == branch_id), None)
    if branch is None or occurrence_alias not in branch.occurrence_aliases:
        raise RuleExprError("query source is absent from its declared branch")
    return _port_binding(_occurrence_binding(plan.occurrence_map, occurrence_alias), port_name)


def _query_navigation_lookup_var(lookup: _RuleExprQueryNavigationLookup) -> Var:
    """Return an opaque, deterministic scalar variable for one Query lookup.

    The name intentionally belongs to a compiler-only namespace.  It is not an
    occurrence port and therefore cannot be confused with a reusable Rule
    interface during evidence assembly.
    """

    components = (
        lookup.branch_id,
        lookup.head_port_name,
        lookup.occurrence_alias,
        lookup.port_name,
        lookup.field_predicate_id,
    )
    payload = "\x00".join(components).encode("utf-8")
    return Var(f"$__query_navigation__{sha256_hex(payload)[:20]}")


def _validate_query_extensions(plan: RuleExprLoweringPlan) -> None:
    if not (
        plan.query_head_links
        or plan.query_value_bindings
        or plan.query_navigation_lookups
    ):
        return
    if plan.head_binding.kind != "projection" or not (
        plan.query_head_links or plan.query_navigation_lookups
    ):
        raise RuleExprError("query extensions require an explicit projection head")

    expected = {
        (branch.branch_id, port_name)
        for branch in plan.branches
        for port_name in plan.head.ports
    }
    direct = {(query_link.branch_id, query_link.head_port_name) for query_link in plan.query_head_links}
    navigation = {
        (lookup.branch_id, lookup.head_port_name)
        for lookup in plan.query_navigation_lookups
    }
    if (
        len(direct) != len(plan.query_head_links)
        or len(navigation) != len(plan.query_navigation_lookups)
        or direct & navigation
        or direct | navigation != expected
    ):
        raise RuleExprError(
            "query direct links and navigation lookups must exactly and disjointly "
            "cover every head port in every branch"
        )
    for query_link in plan.query_head_links:
        _query_port_binding(plan, query_link.branch_id, query_link.occurrence_alias, query_link.port_name)
    for lookup in plan.query_navigation_lookups:
        _query_port_binding(plan, lookup.branch_id, lookup.occurrence_alias, lookup.port_name)

    binding_keys = {
        (query_binding.branch_id, query_binding.occurrence_alias, query_binding.port_name)
        for query_binding in plan.query_value_bindings
    }
    if len(binding_keys) != len(plan.query_value_bindings):
        raise RuleExprError("query value bindings must be unique per branch port")
    for query_binding in plan.query_value_bindings:
        _query_port_binding(plan, query_binding.branch_id, query_binding.occurrence_alias, query_binding.port_name)


def _validate_policy_conditions(plan: RuleExprLoweringPlan) -> None:
    """Keep Policy compiler injections branch-local and unique.

    This is intentionally independent from Query extension validation: Policy
    conditions are valid on a head-independent compiled Policy as well as on a
    synthetic Query projection plan.
    """

    if not plan.policy_conditions:
        return
    branch_ids = {branch.branch_id for branch in plan.branches}
    seen: set[tuple[str, str, str]] = set()
    last_by_compare: dict[tuple[str, str], int] = {}
    role_order = {"left_field": 0, "right_field": 1, "compare": 2}
    for condition in plan.policy_conditions:
        if condition.branch_id not in branch_ids:
            raise RuleExprError("Policy condition references an absent lowering branch")
        key = (condition.branch_id, condition.policy_node_id, condition.condition_id)
        if key in seen:
            raise RuleExprError("Policy condition coordinates must be unique")
        seen.add(key)
        # Conditions are canonically ordered by role within a compare, so its
        # lookup(s) always precede the comparison atom that consumes them.
        compare_key = (condition.branch_id, condition.policy_node_id)
        current = role_order[condition.role]
        previous = last_by_compare.get(compare_key, -1)
        if current < previous:
            raise RuleExprError("Policy conditions must preserve lookup-before-compare order")
        last_by_compare[compare_key] = current


def _policy_condition_sort_key(condition: RuleExprPolicyCondition) -> tuple[object, ...]:
    role_order = {"left_field": 0, "right_field": 1, "compare": 2}
    return (
        condition.branch_id,
        condition.policy_node_id,
        role_order[condition.role],
        condition.condition_id,
        repr(condition.atom),
    )


def _canonical_children(children: tuple[_RuleExpr, ...]) -> tuple[_RuleExpr, ...]:
    return tuple(sorted(children, key=lambda child: repr(child._canonical())))


def _alias_var_map(alias: str, atoms: tuple[Atom, ...]) -> dict[Var, Var]:
    variables: dict[Var, Var] = {}
    for atom in atoms:
        for var in _vars_in_atom(atom):
            variables.setdefault(var, Var(_alias_var_name(alias, var)))
    return variables


def _alias_var_name(alias: str, var: Var) -> str:
    source = var.name.removeprefix("$")
    return f"${alias}__{source}"


def _vars_in_atom(atom: Atom) -> tuple[Var, ...]:
    if isinstance(atom, PredAtom):
        return _vars_in_terms(atom.terms)
    if isinstance(atom, CmpAtom):
        return _vars_in_terms((atom.lhs, atom.rhs))
    if isinstance(atom, InAtom):
        return (atom.var, *_vars_in_terms(atom.values))
    if isinstance(atom, BuiltinAtom):
        return _vars_in_terms(atom.args)
    if isinstance(atom, NotAtom):
        return tuple(var for branch in _where_branches(atom.body) for body_atom in branch for var in _vars_in_atom(body_atom))
    return ()


def _vars_in_terms(terms: object) -> tuple[Var, ...]:
    variables: list[Var] = []
    for term in terms if isinstance(terms, (list, tuple)) else (terms,):
        if isinstance(term, Var):
            variables.append(term)
        elif isinstance(term, AggregateAtom):
            if term.target is not None:
                variables.extend(_vars_in_terms(term.target))
            for atom in term.filter:
                variables.extend(_vars_in_atom(atom))
    return tuple(variables)


def _where_branches(expr: object) -> tuple[tuple[Atom, ...], ...]:
    from factgraph.core.rules.where_ast import AndExpr, OrExpr

    if isinstance(expr, AndExpr):
        return (tuple(expr.atoms),)
    if isinstance(expr, OrExpr):
        return tuple(tuple(branch.atoms) for branch in expr.branches)
    return ()


def _rewrite_atom(atom: Atom, var_map: dict[Var, Var]) -> Atom:
    if isinstance(atom, PredAtom):
        return PredAtom(atom.pred_id, [_rewrite_term(term, var_map) for term in atom.terms], atom.origin)
    if isinstance(atom, CmpAtom):
        return CmpAtom(atom.op, _rewrite_term(atom.lhs, var_map), _rewrite_term(atom.rhs, var_map), atom.origin)
    if isinstance(atom, InAtom):
        return InAtom(
            _rewrite_term(atom.var, var_map),
            [_rewrite_term(value, var_map) for value in atom.values],
            atom.origin,
        )
    if isinstance(atom, BuiltinAtom):
        return BuiltinAtom(atom.op, [_rewrite_term(arg, var_map) for arg in atom.args], atom.origin)
    if isinstance(atom, NotAtom):
        return NotAtom(_rewrite_where(atom.body, var_map), atom.origin)
    raise RuleExprError(f"unsupported atom for RuleExpr lowering: {type(atom).__name__}")


def _rewrite_where(expr: object, var_map: dict[Var, Var]) -> object:
    from factgraph.core.rules.where_ast import AndExpr, OrExpr

    if isinstance(expr, AndExpr):
        return AndExpr([_rewrite_atom(atom, var_map) for atom in expr.atoms], expr.origin)
    if isinstance(expr, OrExpr):
        return OrExpr(
            [AndExpr([_rewrite_atom(atom, var_map) for atom in branch.atoms], branch.origin) for branch in expr.branches],
            expr.origin,
        )
    raise RuleExprError(f"unsupported where expression for RuleExpr lowering: {type(expr).__name__}")


def _rewrite_term(term: Term, var_map: dict[Var, Var]) -> Term:
    if isinstance(term, Var):
        return var_map[term]
    if isinstance(term, Const):
        return term
    if isinstance(term, AggregateAtom):
        return AggregateAtom(
            term.kind,
            None if term.target is None else _rewrite_term(term.target, var_map),
            [_rewrite_atom(atom, var_map) for atom in term.filter],
            term.origin,
        )
    raise RuleExprError(f"unsupported term for RuleExpr lowering: {type(term).__name__}")


def _where_ir_branches(where: list[object]) -> tuple[tuple[object, ...], ...]:
    if not isinstance(where, list) or not where:
        return ()
    if all(isinstance(item, list) for item in where):
        return tuple(tuple(branch) for branch in where)
    return (tuple(where),)


def _pyreason_unsupported_atom(
    atom: object,
    *,
    is_join_atom: bool,
) -> tuple[RuleExprAdapterRejectionSource, str] | None:
    if not isinstance(atom, tuple) or not atom:
        return ("source-rule-grammar", "invalid-atom")
    kind = atom[0]
    if _where_ir_atom_contains_aggregate(atom):
        return ("aggregate", "aggregate")
    if kind == "pred":
        return None
    if is_join_atom and kind == "eq":
        return ("ruleexpr-join", "eq")
    if isinstance(kind, str):
        return ("source-rule-grammar", kind)
    return ("source-rule-grammar", "invalid-atom-kind")


def _where_ir_atom_contains_aggregate(atom: tuple[object, ...]) -> bool:
    return any(_where_ir_value_contains_aggregate(value) for value in atom[1:])


def _where_ir_value_contains_aggregate(value: object) -> bool:
    if isinstance(value, tuple) and value:
        kind = value[0]
        if kind in {"count", "sum", "min", "max", "mean"}:
            return True
        return any(_where_ir_value_contains_aggregate(item) for item in value[1:])
    if isinstance(value, list):
        return any(_where_ir_value_contains_aggregate(item) for item in value)
    return False


def _unsupported_pyreason(source: RuleExprAdapterRejectionSource, feature: str) -> RuleExprAdapterSupport:
    return RuleExprAdapterSupport(
        engine="pyreason",
        supported=False,
        unsupported_feature=feature,
        rejection_source=source,
        alternative_engines=("native", "souffle", "problog"),
    )


def _require_non_empty_str(value: object, *, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise RuleExprError(f"{field_name} must be non-empty string")


def _require_optional_str(value: object, *, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise RuleExprError(f"{field_name} must be non-empty string or None")


def _require_non_negative_int(value: object, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuleExprError(f"{field_name} must be non-negative int")


def _require_tuple(value: object, *, field_name: str, item_type: type[object]) -> None:
    if not isinstance(value, tuple):
        raise RuleExprError(f"{field_name} must be tuple")
    for idx, item in enumerate(value):
        if not isinstance(item, item_type):
            raise RuleExprError(f"{field_name}[{idx}] must be {item_type.__name__}")


__all__: list[str] = []
