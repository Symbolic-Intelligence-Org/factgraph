from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import Any

from .branch import Case
from .errors import SDKDSLError

_VAR_IDS = count(1)


def is_dsl_term(value: Any) -> bool:
    return isinstance(
        value,
        (
            LogicVar,
            AttrRef,
            _AggregateRef,
            BinaryExpr,
            HeadCall,
            ExistsAtom,
            CompareExpr,
            RuleRefAtom,
            NotExpr,
            PredAtom,
        ),
    )


def is_dsl_head_kwarg_value(value: Any) -> bool:
    return is_dsl_term(value)


@dataclass(frozen=True)
class LogicVar:
    label: str | None = None
    token: str | None = None

    def __post_init__(self) -> None:
        if self.label is not None and (not isinstance(self.label, str) or not self.label):
            raise SDKDSLError("LogicVar label must be non-empty string")
        if isinstance(self.label, str) and self.label.startswith("__"):
            raise SDKDSLError("LogicVar labels starting with '__' are reserved for system temporaries")
        token = self.token
        if token is None:
            base = self.label or f"v{next(_VAR_IDS)}"
            token = f"${base}"
            object.__setattr__(self, "token", token)
        if not isinstance(token, str) or not token.startswith("$") or len(token) < 2:
            raise SDKDSLError("LogicVar token must start with '$'")
        if token[1:].startswith("__"):
            raise SDKDSLError("LogicVar token suffix starting with '__' is reserved for system temporaries")

    def __getattr__(self, item: str) -> AttrRef:
        if item.startswith("_"):
            raise AttributeError(item)
        return AttrRef(self, item)

    def __eq__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("eq", self, other)

    def __ne__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("ne", self, other)

    def __gt__(self, other: Any) -> CompareExpr:
        return CompareExpr("gt", self, other)

    def __ge__(self, other: Any) -> CompareExpr:
        return CompareExpr("ge", self, other)

    def __lt__(self, other: Any) -> CompareExpr:
        return CompareExpr("lt", self, other)

    def __le__(self, other: Any) -> CompareExpr:
        return CompareExpr("le", self, other)

    def __add__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("add", self, other)

    def __sub__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("sub", self, other)

    def __radd__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("add", other, self)

    def __rsub__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("sub", other, self)

    def __mul__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("mul", self, other)

    def __rmul__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("mul", other, self)

    def __neg__(self) -> BinaryExpr:
        return BinaryExpr("neg", self, None)


@dataclass(frozen=True)
class AttrRef:
    record_var: LogicVar
    field_name: str
    entity_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field_name, str) or not self.field_name:
            raise SDKDSLError("AttrRef.field_name must be non-empty string")
        if self.entity_type is not None and (
            not isinstance(self.entity_type, str) or not self.entity_type
        ):
            raise SDKDSLError("AttrRef.entity_type must be non-empty string or None")

    def __eq__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("eq", self, other)

    def __ne__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("ne", self, other)

    def __gt__(self, other: Any) -> CompareExpr:
        return CompareExpr("gt", self, other)

    def __ge__(self, other: Any) -> CompareExpr:
        return CompareExpr("ge", self, other)

    def __lt__(self, other: Any) -> CompareExpr:
        return CompareExpr("lt", self, other)

    def __le__(self, other: Any) -> CompareExpr:
        return CompareExpr("le", self, other)


@dataclass(frozen=True)
class BinaryExpr:
    op: str
    left: Any
    right: Any

    def __eq__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("eq", self, other)

    def __ne__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("ne", self, other)

    def __gt__(self, other: Any) -> CompareExpr:
        return CompareExpr("gt", self, other)

    def __ge__(self, other: Any) -> CompareExpr:
        return CompareExpr("ge", self, other)

    def __lt__(self, other: Any) -> CompareExpr:
        return CompareExpr("lt", self, other)

    def __le__(self, other: Any) -> CompareExpr:
        return CompareExpr("le", self, other)

    def __add__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("add", self, other)

    def __sub__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("sub", self, other)

    def __mul__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("mul", self, other)

    def __radd__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("add", other, self)

    def __rsub__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("sub", other, self)

    def __rmul__(self, other: Any) -> BinaryExpr:
        return BinaryExpr("mul", other, self)

    def __neg__(self) -> BinaryExpr:
        return BinaryExpr("neg", self, None)


@dataclass(frozen=True)
class ExistsAtom:
    entity_type: str
    var: LogicVar

    def __getattr__(self, item: str) -> AttrRef:
        if item.startswith("_"):
            raise AttributeError(item)
        return AttrRef(self.var, item, entity_type=self.entity_type)


@dataclass(frozen=True)
class PredAtom:
    pred_id: str
    terms: tuple[Any, ...]


@dataclass(frozen=True)
class RuleRefAtom:
    rule_id: str
    version: str
    terms: tuple[Any, ...]
    rule_obj: Any | None = None


@dataclass(frozen=True)
class CompareExpr:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class _AggregateRef:
    kind: str
    target: Any
    filter: tuple[Any, ...]

    def __eq__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("eq", self, other)

    def __ne__(self, other: Any) -> CompareExpr:  # type: ignore[override]
        return CompareExpr("ne", self, other)

    def __gt__(self, other: Any) -> CompareExpr:
        return CompareExpr("gt", self, other)

    def __ge__(self, other: Any) -> CompareExpr:
        return CompareExpr("ge", self, other)

    def __lt__(self, other: Any) -> CompareExpr:
        return CompareExpr("lt", self, other)

    def __le__(self, other: Any) -> CompareExpr:
        return CompareExpr("le", self, other)


@dataclass(frozen=True)
class NotExpr:
    body: list[Any]


@dataclass(frozen=True)
class HeadCall:
    callee_kind: str  # pred_ref | entity_type
    entity_type: str
    field: str | None
    kwargs: dict[str, Any]

    def to_authoring_head(self) -> dict[str, Any]:
        out = {
            "kind": "head_call",
            "callee_kind": self.callee_kind,
            "entity_type": self.entity_type,
            "kwargs": {k: lower_term(v, in_where=False) for k, v in self.kwargs.items()},
        }
        if self.field is not None:
            out["field"] = self.field
        return out


def build_entity_dsl_call(entity_cls: type, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    entity_type = getattr(entity_cls, "__name__", None)
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKDSLError("invalid entity class for DSL call")
    if kwargs:
        if args:
            raise SDKDSLError("entity DSL call does not support mixing positional and keyword arguments")
        return HeadCall(
            callee_kind="entity_type",
            entity_type=entity_type,
            field=None,
            kwargs=dict(kwargs),
        )
    if len(args) == 1:
        if args[0] is Ellipsis:
            return ExistsAtom(entity_type=entity_type, var=LogicVar())
        if isinstance(args[0], LogicVar):
            return ExistsAtom(entity_type=entity_type, var=args[0])
    raise SDKDSLError(
        "entity DSL call expects exactly one LogicVar or Ellipsis for where exists syntax, or keyword args for derivation head"
    )


def build_field_head_call(field_descriptor: Any, kwargs: dict[str, Any]) -> HeadCall:
    owner = getattr(field_descriptor, "sdk_owner_cls", None)
    entity_type = getattr(owner, "__name__", None)
    field_name = getattr(field_descriptor, "sdk_attr_name", None)
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKDSLError("Field head call is not bound to an Entity owner")
    if not isinstance(field_name, str) or not field_name:
        raise SDKDSLError("Field head call is missing field name")
    if not kwargs:
        raise SDKDSLError("predicate head call requires keyword arguments")
    return HeadCall(
        callee_kind="pred_ref",
        entity_type=entity_type,
        field=field_name,
        kwargs=dict(kwargs),
    )


def Not(body: list[Any]) -> NotExpr:
    """Negate a body fragment inside a `where` clause.

    Use `Not([...])` for absence or anti-join style checks. The wrapped body
    may correlate with variables already bound by earlier atoms.

    Args:
        body: Non-empty list of body atoms to negate.

    Returns:
        A symbolic negation expression for a legacy DSL body.

    Raises:
        SDKDSLError: If ``body`` is not a non-empty list.
    """

    if not isinstance(body, list) or not body:
        raise SDKDSLError("Not(...) requires non-empty list body")
    return NotExpr(body=list(body))


def Pred(pred_id: str, *terms: Any) -> PredAtom:
    """Create a predicate atom for a `where` clause.

    Args:
        pred_id: Predicate id such as `"User:exists"` or `"User:tag"`.
        *terms: Logic variables or literal terms passed to the predicate.

    Returns:
        A symbolic predicate atom for the legacy DSL.

    Raises:
        SDKDSLError: If the predicate id or term list is empty.
    """

    if not isinstance(pred_id, str) or not pred_id:
        raise SDKDSLError("Pred(...) pred_id must be non-empty string")
    if not terms:
        raise SDKDSLError("Pred(...) requires at least one term")
    return PredAtom(pred_id=pred_id, terms=tuple(terms))


def agg_count(*, where: list[Any]) -> _AggregateRef:
    _require_aggregate_filter(where)
    return _AggregateRef(kind="count", target=None, filter=tuple(where))


def agg_sum(target: Any, *, where: list[Any]) -> _AggregateRef:
    _require_aggregate_filter(where)
    return _AggregateRef(kind="sum", target=target, filter=tuple(where))


def agg_min(target: Any, *, where: list[Any]) -> _AggregateRef:
    _require_aggregate_filter(where)
    return _AggregateRef(kind="min", target=target, filter=tuple(where))


def agg_max(target: Any, *, where: list[Any]) -> _AggregateRef:
    _require_aggregate_filter(where)
    return _AggregateRef(kind="max", target=target, filter=tuple(where))


def agg_mean(target: Any, *, where: list[Any]) -> _AggregateRef:
    _require_aggregate_filter(where)
    return _AggregateRef(kind="mean", target=target, filter=tuple(where))


def _require_aggregate_filter(where: list[Any]) -> None:
    if not isinstance(where, list) or not where:
        raise SDKDSLError("aggregate where= must be non-empty list")


def lower_where(
    where: list[Any],
    *,
    initial_bindings: dict[LogicVar, str] | None = None,
) -> list[Any]:
    if not isinstance(where, list) or not where:
        raise SDKDSLError("where must be non-empty list")
    where = _normalize_where_branch_wrappers(where)
    if all(isinstance(item, list) for item in where):
        return [lower_where_branch(branch, initial_bindings=initial_bindings) for branch in where]
    return lower_where_branch(where, initial_bindings=initial_bindings)


def lower_where_branch(
    body: list[Any],
    *,
    initial_bindings: dict[LogicVar, str] | None = None,
) -> list[Any]:
    if not isinstance(body, list) or not body:
        raise SDKDSLError("where body must be non-empty list")
    bindings: dict[LogicVar, str] = dict(initial_bindings or {})
    lowered: list[Any] = []
    temp_seq = count(1)
    for atom in body:
        lowered.extend(lower_where_atom(atom, bindings, temp_seq=temp_seq))
    return lowered


def lower_where_atom(atom: Any, bindings: dict[LogicVar, str], *, temp_seq: Any) -> list[Any]:
    if isinstance(atom, Case):
        return lower_where_branch(atom.atoms, initial_bindings=bindings)
    if (
        isinstance(atom, tuple)
        and len(atom) == 3
        and atom[0] == "__body__"
        and isinstance(atom[1], list)
    ):
        return lower_where_branch(atom[1], initial_bindings=bindings)
    if isinstance(atom, ExistsAtom):
        bindings.setdefault(atom.var, atom.entity_type)
        return [("pred", f"{atom.entity_type}:exists", [atom.var.token])]
    if isinstance(atom, PredAtom):
        return [("pred", atom.pred_id, [lower_term(x, in_where=True) for x in atom.terms])]
    if isinstance(atom, RuleRefAtom):
        return [("ruleref", atom.rule_id, atom.version, [lower_term(x, in_where=True) for x in atom.terms])]
    if isinstance(atom, NotExpr):
        # not body can correlate with already bound outer vars.
        return [("not", lower_where_branch(atom.body, initial_bindings=bindings))]
    if isinstance(atom, CompareExpr):
        return _lower_compare(atom, bindings, temp_seq=temp_seq)
    if isinstance(atom, tuple):
        return [atom]
    raise SDKDSLError(f"unsupported where atom: {type(atom).__name__}")


def _lower_compare(expr: CompareExpr, bindings: dict[LogicVar, str], *, temp_seq: Any) -> list[Any]:
    if isinstance(expr.left, _AggregateRef) or isinstance(expr.right, _AggregateRef):
        return _lower_compare_with_aggregate(expr, bindings, temp_seq=temp_seq)
    if isinstance(expr.left, AttrRef) and isinstance(expr.right, AttrRef):
        if expr.op != "eq":
            raise SDKDSLError("entity attribute comparison sugar currently supports only '==' in SDK object DSL v1")
        prefix: list[Any] = []
        _ensure_attr_record_binding(expr.left, bindings, prefix)
        _ensure_attr_record_binding(expr.right, bindings, prefix)
        return [
            *prefix,
            (
                "attr_eq",
                (expr.left.record_var.token, expr.left.field_name),
                (expr.right.record_var.token, expr.right.field_name),
            )
        ]
    if isinstance(expr.left, AttrRef) or isinstance(expr.right, AttrRef):
        attr = expr.left if isinstance(expr.left, AttrRef) else expr.right
        other = expr.right if isinstance(expr.left, AttrRef) else expr.left
        if not isinstance(attr, AttrRef):
            raise SDKDSLError("internal attr compare lowering error")
        if expr.op != "eq":
            raise SDKDSLError("entity attribute comparison sugar currently supports only '==' in SDK object DSL v1")
        prefix: list[Any] = []
        record_type = _ensure_attr_record_binding(attr, bindings, prefix)
        pred_id = f"{record_type.lower()}:{attr.field_name}"
        other_term = _lower_attr_compare_other(other, bindings, prefix)
        return [*prefix, ("pred", pred_id, [attr.record_var.token, other_term])]

    pre_left, left = _lower_expr_term(expr.left, temp_seq=temp_seq)
    pre_right, right = _lower_expr_term(expr.right, temp_seq=temp_seq)
    out = [*pre_left, *pre_right]
    if expr.op == "ne":
        out.append(("ne", left, right))
        return out
    if expr.op == "eq":
        out.append(("eq", left, right))
        return out
    if expr.op in {"gt", "ge", "lt", "le"}:
        out.append((expr.op, left, right))
        return out
    raise SDKDSLError(f"unsupported compare op: {expr.op}")


def _lower_compare_with_aggregate(
    expr: CompareExpr,
    bindings: dict[LogicVar, str],
    *,
    temp_seq: Any,
) -> list[Any]:
    left = (
        _lower_aggregate_ref(expr.left, bindings, temp_seq=temp_seq)
        if isinstance(expr.left, _AggregateRef)
        else lower_term(expr.left, in_where=True)
    )
    right = (
        _lower_aggregate_ref(expr.right, bindings, temp_seq=temp_seq)
        if isinstance(expr.right, _AggregateRef)
        else lower_term(expr.right, in_where=True)
    )
    if expr.op == "ne":
        return [("ne", left, right)]
    if expr.op in {"eq", "gt", "ge", "lt", "le"}:
        return [(expr.op, left, right)]
    raise SDKDSLError(f"unsupported compare op: {expr.op}")


def _lower_aggregate_ref(
    ref: _AggregateRef,
    outer_bindings: dict[LogicVar, str],
    *,
    temp_seq: Any,
) -> tuple[Any, Any, list[Any]]:
    filter_bindings = dict(outer_bindings)
    filter_ir: list[Any] = []
    for atom in ref.filter:
        filter_ir.extend(lower_where_atom(atom, filter_bindings, temp_seq=temp_seq))

    target, extra_filter = _lower_aggregate_target(ref.target, filter_bindings, temp_seq=temp_seq)
    filter_ir.extend(extra_filter)
    return (ref.kind, target, filter_ir)


def _lower_aggregate_target(
    target: Any,
    filter_bindings: dict[LogicVar, str],
    *,
    temp_seq: Any,
) -> tuple[Any, list[Any]]:
    if target is None:
        return None, []
    if isinstance(target, AttrRef):
        extra: list[Any] = []
        record_type = _ensure_attr_record_binding(target, filter_bindings, extra)
        tmp = f"$_agg{next(temp_seq)}"
        extra.append(
            (
                "pred",
                f"{record_type.lower()}:{target.field_name}",
                [target.record_var.token, tmp],
            )
        )
        return tmp, extra
    return lower_term(target, in_where=True), []


def _ensure_attr_record_binding(
    attr: AttrRef,
    bindings: dict[LogicVar, str],
    prefix: list[Any],
) -> str:
    record_type = bindings.get(attr.record_var)
    if record_type is not None:
        return record_type
    if attr.entity_type is None:
        raise SDKDSLError(
            f"entity variable {attr.record_var.token} used in path comparison before {attr.record_var.token} is bound"
        )
    bindings[attr.record_var] = attr.entity_type
    prefix.append(("pred", f"{attr.entity_type}:exists", [attr.record_var.token]))
    return attr.entity_type


def _lower_attr_compare_other(
    value: Any,
    bindings: dict[LogicVar, str],
    prefix: list[Any],
) -> Any:
    if isinstance(value, ExistsAtom):
        bound_type = bindings.get(value.var)
        if bound_type is None:
            bindings[value.var] = value.entity_type
            prefix.append(("pred", f"{value.entity_type}:exists", [value.var.token]))
        return value.var.token
    return lower_term(value, in_where=True)


def _lower_expr_term(value: Any, *, temp_seq: Any) -> tuple[list[Any], Any]:
    if isinstance(value, BinaryExpr):
        return _lower_binary_expr(value, temp_seq=temp_seq)
    return ([], lower_term(value, in_where=True))


def _lower_binary_expr(expr: BinaryExpr, *, temp_seq: Any) -> tuple[list[Any], str]:
    if expr.op == "neg":
        pre_x, x_term = _lower_expr_term(expr.left, temp_seq=temp_seq)
        tmp = f"$_arith{next(temp_seq)}"
        return [*pre_x, ("neg", tmp, x_term)], tmp

    pre_l, l_term = _lower_expr_term(expr.left, temp_seq=temp_seq)
    pre_r, r_term = _lower_expr_term(expr.right, temp_seq=temp_seq)
    tmp = f"$_arith{next(temp_seq)}"

    if expr.op == "add":
        if _is_numeric_literal(l_term):
            return [*pre_l, *pre_r, ("addc", tmp, r_term, l_term)], tmp
        if _is_numeric_literal(r_term):
            return [*pre_l, *pre_r, ("addc", tmp, l_term, r_term)], tmp
        return [*pre_l, *pre_r, ("add", tmp, l_term, r_term)], tmp
    if expr.op == "sub":
        if _is_numeric_literal(r_term):
            return [*pre_l, *pre_r, ("addc", tmp, l_term, -int(r_term))], tmp
        return [*pre_l, *pre_r, ("sub", tmp, l_term, r_term)], tmp
    if expr.op == "mul":
        if _is_numeric_literal(l_term):
            return [*pre_l, *pre_r, ("mulc", tmp, r_term, l_term)], tmp
        if _is_numeric_literal(r_term):
            return [*pre_l, *pre_r, ("mulc", tmp, l_term, r_term)], tmp
        raise SDKDSLError("non-linear multiplication (x * y) is not supported in SDK object DSL v1")
    raise SDKDSLError(f"unsupported arithmetic expression op: {expr.op}")


def _is_numeric_literal(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _normalize_where_branch_wrappers(where: list[Any]) -> list[Any]:
    has_branch = any(isinstance(item, Case) for item in where)
    if not has_branch:
        return where
    if not all(isinstance(item, Case) for item in where):
        raise SDKDSLError("where/case cannot mix Case(...) with bare cases")
    return [list(item.atoms) for item in where]


def lower_term(value: Any, *, in_where: bool) -> Any:
    if isinstance(value, LogicVar):
        return value.token
    if isinstance(value, AttrRef):
        if in_where:
            raise SDKDSLError("AttrRef must appear in a comparison, not as a standalone term")
        raise SDKDSLError("AttrRef is not allowed in derivation head terms")
    if isinstance(value, BinaryExpr):
        # Core where/runtime does not support arithmetic expressions yet.
        raise SDKDSLError("arithmetic expressions in where/head are not supported in SDK object DSL v1")
    if isinstance(value, (str, int, bool, float)) or value is None:
        return value
    if isinstance(value, list):
        return [lower_term(item, in_where=in_where) for item in value]
    if isinstance(value, tuple):
        return tuple(lower_term(item, in_where=in_where) for item in value)
    raise SDKDSLError(f"unsupported DSL term: {type(value).__name__}")
