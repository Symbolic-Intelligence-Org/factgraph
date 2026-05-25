from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
from typing import Literal

from factgraph.application.derivation_runtime import evaluate_derivation_plans
from factgraph.core.derivation.candidates import CandidateSet
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
from .rule import PortType, Rule
from .rule_expr import (
    RuleExprError,
    RuleJoinConstraint,
    _AndGroup,
    _OrGroup,
    _RuleExpr,
    _RuleOperand,
    _canonical_join_constraint,
    _coerce_rule_expr_operand,
)

RuleExprAdapterEngine = Literal["native", "souffle", "problog"]
RuleExprAdapterRejectionSource = Literal["ruleexpr-join", "source-rule-grammar", "aggregate", "branch-shape"]


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

    def __post_init__(self) -> None:
        _require_non_empty_str(self.alias, field_name="alias")
        _require_non_empty_str(self.rule_id, field_name="rule_id")
        _require_non_empty_str(self.content_digest, field_name="content_digest")
        _require_tuple(self.port_bindings, field_name="port_bindings", item_type=RuleExprPortBinding)


@dataclass(frozen=True)
class RuleExprHeadBinding:
    kind: Literal["external", "inline"]
    head_rule_id: str
    head_content_digest: str
    projection_occurrence_alias: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"external", "inline"}:
            raise RuleExprError("RuleExprHeadBinding.kind must be 'external' or 'inline'")
        _require_non_empty_str(self.head_rule_id, field_name="head_rule_id")
        _require_non_empty_str(self.head_content_digest, field_name="head_content_digest")
        if self.projection_occurrence_alias is not None:
            _require_non_empty_str(self.projection_occurrence_alias, field_name="projection_occurrence_alias")
        if self.kind == "external" and self.projection_occurrence_alias is not None:
            raise RuleExprError("external head binding must not set projection_occurrence_alias")
        if self.kind == "inline" and self.projection_occurrence_alias is None:
            raise RuleExprError("inline head binding requires projection_occurrence_alias")


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


@dataclass(frozen=True)
class RuleExprJoinMaterialization:
    branch_id: str
    join_key: tuple[object, ...]
    left_occurrence_alias: str
    left_port_name: str
    right_occurrence_alias: str
    right_port_name: str
    materialized_atom_index: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        if not isinstance(self.join_key, tuple) or not self.join_key:
            raise RuleExprError("RuleExprJoinMaterialization.join_key must be non-empty tuple")
        _require_non_empty_str(self.left_occurrence_alias, field_name="left_occurrence_alias")
        _require_non_empty_str(self.left_port_name, field_name="left_port_name")
        _require_non_empty_str(self.right_occurrence_alias, field_name="right_occurrence_alias")
        _require_non_empty_str(self.right_port_name, field_name="right_port_name")
        _require_non_negative_int(self.materialized_atom_index, field_name="materialized_atom_index")


@dataclass(frozen=True)
class RuleExprEvaluationTrace:
    canonical_key: tuple[object, ...]
    engine: RuleExprAdapterEngine
    branch_id: str
    runtime_branch_index: int
    occurrence_aliases: tuple[str, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    join_materializations: tuple[RuleExprJoinMaterialization, ...]
    head_binding: RuleExprHeadBinding
    support_digest: str | None = None
    support_kind: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_key, tuple) or not self.canonical_key:
            raise RuleExprError("RuleExprEvaluationTrace.canonical_key must be non-empty tuple")
        if self.engine not in {"native", "souffle", "problog"}:
            raise RuleExprError("RuleExprEvaluationTrace.engine must be native, souffle, or problog")
        _require_non_empty_str(self.branch_id, field_name="branch_id")
        _require_non_negative_int(self.runtime_branch_index, field_name="runtime_branch_index")
        _require_tuple(self.occurrence_aliases, field_name="occurrence_aliases", item_type=str)
        _require_tuple(self.occurrence_map, field_name="occurrence_map", item_type=RuleExprOccurrenceBinding)
        _require_tuple(
            self.join_materializations,
            field_name="join_materializations",
            item_type=RuleExprJoinMaterialization,
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


def _lower_application_rule(rule: Rule, *, head: Rule) -> RuleExprLoweringPlan:
    if not isinstance(rule, Rule):
        raise RuleExprError("rule must be application protocol Rule")
    return _build_lowering_plan(_coerce_rule_expr_operand(rule), head=head, source_kind="rule")


def _lower_rule_expr(expr: _RuleExpr, *, head: Rule) -> RuleExprLoweringPlan:
    if not isinstance(expr, _RuleExpr):
        raise RuleExprError("expr must be RuleExpr")
    return _build_lowering_plan(expr, head=head, source_kind="rule_expr")


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
    if plan.head_binding.kind == "external":
        raise RuleExprError("external head body concatenation is deferred to T3L.3")

    materialized_branches: list[list[object]] = []
    traces: list[RuleExprEvaluationTrace] = []
    head_vars = _head_var_names(plan)
    for runtime_branch_index, branch in enumerate(plan.branches):
        body, joins = _materialize_branch(branch, plan.occurrence_map)
        materialized_branches.append(body)
        traces.append(
            RuleExprEvaluationTrace(
                canonical_key=plan.canonical_key,
                engine=engine,
                branch_id=branch.branch_id,
                runtime_branch_index=runtime_branch_index,
                occurrence_aliases=branch.occurrence_aliases,
                occurrence_map=plan.occurrence_map,
                join_materializations=joins,
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
    compiled, traces = _materialize_adapter_derivation_plan(plan, engine="native")
    branch_join_indexes = {
        trace.runtime_branch_index: {join.materialized_atom_index for join in trace.join_materializations}
        for trace in traces
    }
    branches = _where_ir_branches(compiled.body_ir)
    if not branches:
        return _unsupported_pyreason("branch-shape", "branch-shape")
    for branch_index, branch in enumerate(branches):
        for atom_index, atom in enumerate(branch):
            unsupported = _pyreason_unsupported_atom(
                atom,
                is_join_atom=atom_index in branch_join_indexes.get(branch_index, set()),
            )
            if unsupported is not None:
                source, feature = unsupported
                return _unsupported_pyreason(source, feature)
    return RuleExprAdapterSupport(engine="pyreason", supported=True)


def _evaluate_rule_expr_native_for_tests(
    expr: _RuleExpr,
    *,
    head: Rule,
    store: Store,
) -> list[CandidateSet]:
    plan = _lower_rule_expr(expr, head=head)
    compiled, _traces = _materialize_native_derivation_plan(plan)
    return evaluate_derivation_plans(DerivationEvaluateRequest(plans=(compiled,), engine="native"), store=store)


def _build_lowering_plan(expr: _RuleExpr, *, head: Rule, source_kind: Literal["rule", "rule_expr"]) -> RuleExprLoweringPlan:
    if not isinstance(head, Rule):
        raise RuleExprError("head must be application protocol Rule")
    occurrence_map_by_alias: dict[str, RuleExprOccurrenceBinding] = {}
    branches = _assign_branch_ids(_lower_expr(expr, occurrence_map_by_alias, path=()))
    occurrence_map = tuple(occurrence_map_by_alias[alias] for alias in sorted(occurrence_map_by_alias))
    head_binding = _head_binding(head, occurrence_map)
    return RuleExprLoweringPlan(
        source_kind=source_kind,
        head=head,
        head_binding=head_binding,
        branches=branches,
        occurrence_map=occurrence_map,
        canonical_key=(source_kind, expr._canonical(), head_binding.kind, head.id, head.content_digest),
    )


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
    alias_var_map = _alias_var_map(operand.alias, operand.rule.where)
    body_atoms = tuple(_rewrite_atom(atom, alias_var_map) for atom in operand.rule.where)
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
    return tuple(replace(branch, branch_id=f"b{idx}") for idx, branch in enumerate(branches))


def _materialize_branch(
    branch: RuleExprLoweringBranch,
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
) -> tuple[list[object], tuple[RuleExprJoinMaterialization, ...]]:
    materialized_atoms: list[Atom] = list(branch.body_atoms)
    joins: list[RuleExprJoinMaterialization] = []
    unique_joins: dict[tuple[object, ...], RuleJoinConstraint] = {}
    for join in branch.pending_joins:
        unique_joins.setdefault(_canonical_join_constraint(join), join)
    for join_key in sorted(unique_joins, key=repr):
        join = unique_joins[join_key]
        left = _resolve_endpoint(join.left, occurrence_map)
        right = _resolve_endpoint(join.right, occurrence_map)
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
                materialized_atom_index=materialized_index,
            )
        )
    return lower_ast_to_where_ir(AndExpr(materialized_atoms)), tuple(joins)


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
    if plan.head_binding.projection_occurrence_alias is None:
        raise RuleExprError("external head body concatenation is deferred to T3L.3")
    occurrence = _occurrence_binding(plan.occurrence_map, plan.head_binding.projection_occurrence_alias)
    names: list[str] = []
    for port_name in plan.head.ports:
        binding = _port_binding(occurrence, port_name)
        names.append(binding.alias_local_execution_var.name)
    return tuple(names)


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


def _canonical_children(children: tuple[_RuleExpr, ...]) -> tuple[_RuleExpr, ...]:
    return tuple(sorted(children, key=lambda child: repr(child._canonical())))


def _alias_var_map(alias: str, atoms: tuple[Atom, ...]) -> dict[Var, Var]:
    variables: dict[Var, Var] = {}
    for atom in atoms:
        for var in _vars_in_atom(atom):
            variables.setdefault(var, Var(_alias_var_name(alias, var)))
    return variables


def _alias_var_name(alias: str, var: Var) -> str:
    source = var.name[1:] if var.name.startswith("$") else var.name
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
