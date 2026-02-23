"""Expression IR for rule conditions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from symir.errors import SchemaError
from symir.ir.fact_schema import PredicateSchema
from symir.ir.instance import Instance


class ExprIR:
    """Base class for expression IR."""

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class Var(ExprIR):
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise SchemaError("Var name must be non-empty.")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "var", "name": self.name}


@dataclass(frozen=True)
class Const(ExprIR):
    value: object

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "const", "value": self.value}


@dataclass(frozen=True, init=False)
class Ref(ExprIR):
    schema: str
    terms: list["ExprTerm"]
    negated: bool = False

    def __init__(
        self,
        schema: PredicateSchema | Instance,
        terms: list["ExprTerm"] | None = None,
        negated: bool = False,
    ) -> None:
        pred_obj: PredicateSchema | None = None
        pred_id: str | None
        if isinstance(schema, Instance):
            if terms is not None:
                raise SchemaError("Ref terms must be omitted when schema is an Instance.")
            pred_id = schema.schema_id
            pred_obj = _resolve_schema_from_cache(pred_id)
            if pred_obj is None:
                raise SchemaError(
                    "Ref schema Instance requires predicate schema in cache. "
                    "Pass the schema object explicitly."
                )
            try:
                values = schema.to_terms(pred_obj)
            except SchemaError as exc:
                raise SchemaError(
                    "Ref schema Instance could not be expanded to terms. "
                    "Ensure the instance has full key props (include_keys) "
                    "or pass the schema object explicitly."
                ) from exc
            terms = [Const(value=value) for value in values]
        elif isinstance(schema, PredicateSchema):
            pred_obj = schema
            pred_id = schema.schema_id
        else:
            raise SchemaError("Ref schema must be a PredicateSchema or Instance.")
        if not pred_id:
            raise SchemaError("Ref requires schema.")
        if terms is None:
            raise SchemaError("Ref terms must be provided.")
        for term in terms:
            if not isinstance(term, (Var, Const)):
                raise SchemaError("Ref terms must be Var or Const.")
        if pred_obj is not None:
            if len(terms) != pred_obj.arity:
                raise SchemaError(
                    f"Ref terms length must match predicate arity: "
                    f"expected {pred_obj.arity}, got {len(terms)}."
                )
            for term, arg in zip(terms, pred_obj.signature):
                if isinstance(term, Const) and arg.datatype:
                    _validate_const_value(term.value, arg.datatype)
        object.__setattr__(self, "schema", pred_id)
        object.__setattr__(self, "terms", list(terms))
        object.__setattr__(self, "negated", bool(negated))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "ref",
            "schema": self.schema,
            "terms": [t.to_dict() for t in self.terms],
            "negated": self.negated,
        }

    @property
    def schema_id(self) -> str:
        return self.schema


@dataclass(frozen=True)
class Call(ExprIR):
    op: str
    args: list[ExprIR]

    def __post_init__(self) -> None:
        if not self.op:
            raise SchemaError("Call op must be non-empty.")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "call", "op": self.op, "args": [a.to_dict() for a in self.args]}


@dataclass(frozen=True)
class Unify(ExprIR):
    lhs: ExprIR
    rhs: ExprIR

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "unify", "lhs": self.lhs.to_dict(), "rhs": self.rhs.to_dict()}


@dataclass(frozen=True)
class If(ExprIR):
    cond: ExprIR
    then: ExprIR
    else_: ExprIR

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "if",
            "cond": self.cond.to_dict(),
            "then": self.then.to_dict(),
            "else": self.else_.to_dict(),
        }


@dataclass(frozen=True)
class NotExpr(ExprIR):
    expr: ExprIR

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "not", "expr": self.expr.to_dict()}


ExprTerm = Var | Const


def expr_from_dict(data: dict[str, Any]) -> ExprIR:
    kind = data.get("kind")
    if kind == "var":
        return Var(name=data["name"])
    if kind == "const":
        return Const(value=data.get("value"))
    if kind == "ref":
        pred_id = None
        schema_payload = data.get("schema")
        pred_obj: PredicateSchema | None = None
        if isinstance(schema_payload, dict):
            pred_obj = PredicateSchema.from_dict(schema_payload)
            pred_id = pred_obj.schema_id
        elif schema_payload is not None:
            pred_id = str(schema_payload)
        if pred_id is None:
            pred_id = data.get("schema_id") or data.get("predicate_id")
        if pred_id is None and "predicate" in data:
            predicate = data.get("predicate")
            pred_obj = PredicateSchema.from_dict(predicate) if predicate else None
            if pred_obj is not None:
                pred_id = pred_obj.schema_id
        terms = [expr_from_dict(t) for t in data.get("terms", [])]
        for term in terms:
            if not isinstance(term, (Var, Const)):
                raise SchemaError("Ref terms must be Var or Const.")
        if pred_obj is None:
            if pred_id:
                pred_obj = _resolve_schema_from_cache(str(pred_id))
        if pred_obj is None:
            raise SchemaError(
                "Ref requires a schema object. Provide schema in payload or ensure "
                "the predicate schema is cached before parsing."
            )
        return Ref(schema=pred_obj, terms=terms, negated=bool(data.get("negated", False)))
    if kind == "call":
        return Call(op=data["op"], args=[expr_from_dict(a) for a in data.get("args", [])])
    if kind == "unify":
        return Unify(lhs=expr_from_dict(data["lhs"]), rhs=expr_from_dict(data["rhs"]))
    if kind == "if":
        return If(
            cond=expr_from_dict(data["cond"]),
            then=expr_from_dict(data["then"]),
            else_=expr_from_dict(data["else"]),
        )
    if kind == "not":
        return NotExpr(expr=expr_from_dict(data["expr"]))
    raise SchemaError(f"Unknown ExprIR kind: {kind}")


def _validate_const_value(value: object, datatype: str) -> None:
    dtype = datatype.strip().lower()
    if dtype == "string":
        if not isinstance(value, str):
            raise SchemaError(f"Const value must be string for datatype 'string': {value}")
        return
    if dtype == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaError(f"Const value must be int for datatype 'int': {value}")
        return
    if dtype == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaError(f"Const value must be float for datatype 'float': {value}")
        return
    if dtype == "bool":
        if not isinstance(value, bool):
            raise SchemaError(f"Const value must be bool for datatype 'bool': {value}")
        return


def _resolve_schema_from_cache(schema_id: str) -> PredicateSchema | None:
    try:
        from symir.ir.fact_schema import load_predicate_schemas_from_cache
    except Exception:
        return None
    try:
        items = load_predicate_schemas_from_cache()
    except Exception:
        return None
    for pred in items:
        if pred.schema_id == schema_id:
            return pred
    return None
