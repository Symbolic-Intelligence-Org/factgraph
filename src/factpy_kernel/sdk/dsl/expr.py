from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from typing import Any

from .errors import SDKDSLError


_VAR_IDS = count(1)


def is_dsl_term(value: Any) -> bool:
    return isinstance(
        value,
        (
            LogicVar,
            AttrRef,
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
        token = self.token
        if token is None:
            base = self.label or f"v{next(_VAR_IDS)}"
            token = f"${base}"
            object.__setattr__(self, "token", token)
        if not isinstance(token, str) or not token.startswith("$") or len(token) < 2:
            raise SDKDSLError("LogicVar token must start with '$'")

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

    def __post_init__(self) -> None:
        if not isinstance(self.field_name, str) or not self.field_name:
            raise SDKDSLError("AttrRef.field_name must be non-empty string")

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
    if len(args) == 1 and isinstance(args[0], LogicVar):
        return ExistsAtom(entity_type=entity_type, var=args[0])
    raise SDKDSLError(
        "entity DSL call expects exactly one LogicVar for where exists syntax, or keyword args for derivation head"
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
    if not isinstance(body, list) or not body:
        raise SDKDSLError("Not(...) requires non-empty list body")
    return NotExpr(body=list(body))


def Pred(pred_id: str, *terms: Any) -> PredAtom:
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKDSLError("Pred(...) pred_id must be non-empty string")
    if not terms:
        raise SDKDSLError("Pred(...) requires at least one term")
    return PredAtom(pred_id=pred_id, terms=tuple(terms))


def lower_where(where: list[Any]) -> list[Any]:
    if not isinstance(where, list) or not where:
        raise SDKDSLError("where must be non-empty list")
    if all(isinstance(item, list) for item in where):
        return [lower_where_branch(branch) for branch in where]
    return lower_where_branch(where)


def lower_where_branch(body: list[Any]) -> list[Any]:
    if not isinstance(body, list) or not body:
        raise SDKDSLError("where body must be non-empty list")
    bindings: dict[LogicVar, str] = {}
    lowered: list[Any] = []
    temp_seq = count(1)
    for atom in body:
        lowered.extend(lower_where_atom(atom, bindings, temp_seq=temp_seq))
    return lowered


def lower_where_atom(atom: Any, bindings: dict[LogicVar, str], *, temp_seq: Any) -> list[Any]:
    if isinstance(atom, ExistsAtom):
        bindings.setdefault(atom.var, atom.entity_type)
        return [("pred", f"{atom.entity_type}:exists", [atom.var.token])]
    if isinstance(atom, PredAtom):
        return [("pred", atom.pred_id, [lower_term(x, in_where=True) for x in atom.terms])]
    if isinstance(atom, RuleRefAtom):
        return [("ruleref", atom.rule_id, atom.version, [lower_term(x, in_where=True) for x in atom.terms])]
    if isinstance(atom, NotExpr):
        return [("not", lower_where_branch(atom.body))]
    if isinstance(atom, CompareExpr):
        return _lower_compare(atom, bindings, temp_seq=temp_seq)
    if isinstance(atom, tuple):
        return [atom]
    raise SDKDSLError(f"unsupported where atom: {type(atom).__name__}")


def _lower_compare(expr: CompareExpr, bindings: dict[LogicVar, str], *, temp_seq: Any) -> list[Any]:
    if isinstance(expr.left, AttrRef) and isinstance(expr.right, AttrRef):
        # Blueprint shorthand can express this, but runtime SDK lowering avoids implicit temp vars in v1.
        raise SDKDSLError(
            "attribute-to-attribute comparison is not supported in SDK object DSL v1; bind one side to a variable first"
        )
    if isinstance(expr.left, AttrRef) or isinstance(expr.right, AttrRef):
        attr = expr.left if isinstance(expr.left, AttrRef) else expr.right
        other = expr.right if isinstance(expr.left, AttrRef) else expr.left
        if not isinstance(attr, AttrRef):
            raise SDKDSLError("internal attr compare lowering error")
        if expr.op != "eq":
            raise SDKDSLError("record attribute comparison sugar currently supports only '==' in SDK object DSL v1")
        record_type = bindings.get(attr.record_var)
        if record_type is None:
            raise SDKDSLError(
                f"record variable {attr.record_var.token} used in path comparison before {attr.record_var.token} is bound"
            )
        pred_id = f"{record_type.lower()}:{attr.field_name}"
        return [("pred", pred_id, [attr.record_var.token, lower_term(other, in_where=True)])]

    pre_left, left = _lower_expr_term(expr.left, temp_seq=temp_seq)
    pre_right, right = _lower_expr_term(expr.right, temp_seq=temp_seq)
    out = [*pre_left, *pre_right]
    if expr.op == "ne":
        out.append(("not", [("eq", left, right)]))
        return out
    if expr.op == "eq":
        out.append(("eq", left, right))
        return out
    if expr.op in {"gt", "ge", "lt", "le"}:
        out.append((expr.op, left, right))
        return out
    raise SDKDSLError(f"unsupported compare op: {expr.op}")


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
