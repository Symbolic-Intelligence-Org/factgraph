"""Constraint schemas for rule IR decoding."""

from __future__ import annotations

from typing import Any, Literal, Annotated, Union

from pydantic import BaseModel, Field, model_validator

from symir.errors import SchemaError
from symir.ir.fact_schema import FactView, PredicateSchema, ArgField, Value
from symir.rules.library import Library, LibrarySpec


def build_pydantic_rule_model(
    view: FactView,
    library: Library | None = None,
    *,
    mode: Literal["verbose", "compact"] = "verbose",
) -> type[BaseModel]:
    """Build a Pydantic model that validates rule conditions only."""

    allowed_predicate_ids = {pred.schema_id: pred.arity for pred in view.predicates()}
    predicate_info: dict[
        str,
        tuple[
            str,
            int,
            list[tuple[str | None, str | None, str | None, str | None]] | None,
            str | None,
        ],
    ] = {}
    for pred in view.predicates():
        predicate_info[pred.schema_id] = (
            pred.name,
            pred.arity,
            [(a.datatype, a.role, a.namespace, a.arg_name) for a in pred.signature],
            pred.description,
        )
    if library is not None:
        for pred_id, spec in library.predicate_ids().items():
            allowed_predicate_ids[pred_id] = spec.arity
            signature = None
            if spec.signature is not None:
                signature = [(item, None, None, None) for item in spec.signature]
            predicate_info[pred_id] = (spec.name, spec.arity, signature, spec.description)
    allowed_expr_ops = set(_builtin_ops())
    if library is not None:
        allowed_expr_ops.update(library.expr_ops())

    def _validate_const_value(value: object, datatype: str | None) -> None:
        if datatype is None:
            return
        dtype = datatype.strip().lower()
        if dtype == "string":
            if not isinstance(value, str):
                raise ValueError(f"Const value must be string for datatype 'string': {value}")
            return
        if dtype == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Const value must be int for datatype 'int': {value}")
            return
        if dtype == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"Const value must be float for datatype 'float': {value}")
            return
        if dtype == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"Const value must be bool for datatype 'bool': {value}")
            return

    class VarModel(BaseModel):
        kind: Literal["var"] = "var"
        name: str

    class ConstModel(BaseModel):
        kind: Literal["const"] = "const"
        value: str | int | float | bool

    ExprTermModel = Annotated[Union[VarModel, ConstModel], Field(discriminator="kind")]

    class ArgValueModel(BaseModel):
        name: str
        value: ExprTermModel

    def _signature_hints(schema_id: str) -> list[str]:
        info = predicate_info.get(schema_id)
        if info is None:
            expected = allowed_predicate_ids.get(schema_id, 0)
            return [f"Arg{i + 1}" for i in range(expected)]
        _, arity, signature, _ = info
        if signature is None:
            return [f"Arg{i + 1}" for i in range(arity)]
        hints: list[str] = []
        for idx, item in enumerate(signature):
            datatype, _role, _namespace, arg_name = item
            label = arg_name or f"Arg{idx + 1}"
            if datatype:
                label = f"{label} ({datatype})"
            hints.append(label)
        return hints

    def _predicate_display_name(schema_id: str) -> str:
        info = predicate_info.get(schema_id)
        if info is None:
            return schema_id
        return info[0]

    def _arity_error_message(
        schema_id: str,
        *,
        expected: int,
        got: int,
        provided_arg_names: list[str] | None = None,
    ) -> str:
        expected_args = ", ".join(_signature_hints(schema_id))
        provided_text = ""
        if provided_arg_names:
            provided_text = f" Provided arg names: {', '.join(provided_arg_names)}."
        mode_hint = ""
        if mode == "compact":
            mode_hint = (
                " Compact mode requires all args. "
                "Arg names are descriptive/free-form; binding is by signature order "
                "unless exact signature names are provided."
            )
        return (
            f"Ref arity mismatch for predicate '{_predicate_display_name(schema_id)}' "
            f"(schema={schema_id}): expected {expected}, got {got}. "
            f"Expected args: {expected_args}.{provided_text}{mode_hint}"
        )

    class CallModel(BaseModel):
        kind: Literal["call"] = "call"
        op: str
        args: list["ExprModel"]

        @model_validator(mode="after")
        def _check_op(self):
            if self.op not in allowed_expr_ops:
                raise ValueError(f"Expr op not allowed: {self.op}")
            return self

    class UnifyModel(BaseModel):
        kind: Literal["unify"] = "unify"
        lhs: "ExprModel"
        rhs: "ExprModel"

    class IfModel(BaseModel):
        kind: Literal["if"] = "if"
        cond: "ExprModel"
        then: "ExprModel"
        else_: "ExprModel" = Field(alias="else")

    class NotModel(BaseModel):
        kind: Literal["not"] = "not"
        expr: "ExprModel"

    class ArgSpecModel(BaseModel):
        datatype: str
        role: str | None = None
        namespace: str | None = None
        arg_name: str | None = None

    class PredicateInfoModel(BaseModel):
        name: str
        arity: int
        signature: list[ArgSpecModel] | None = None
        description: str | None = None

    class RefExprModel(BaseModel):
        kind: Literal["ref"] = "ref"
        schema: str
        terms: list[ExprTermModel] | None = None
        args: list[ArgValueModel] | None = None
        negated: bool = False

        @model_validator(mode="after")
        def _check_allowed(self):
            if self.schema not in allowed_predicate_ids:
                raise ValueError(f"Ref predicate not in FactView: {self.schema}")
            expected = allowed_predicate_ids[self.schema]
            if mode == "verbose":
                if self.terms is None:
                    raise ValueError("Ref terms required in verbose mode.")
                if len(self.terms) != expected:
                    raise ValueError(_arity_error_message(
                        self.schema,
                        expected=expected,
                        got=len(self.terms),
                    ))
            else:
                if self.args is None:
                    raise ValueError("Ref args required in compact mode.")
                if len(self.args) != expected:
                    raise ValueError(_arity_error_message(
                        self.schema,
                        expected=expected,
                        got=len(self.args),
                        provided_arg_names=[arg.name for arg in self.args],
                    ))
            info = predicate_info.get(self.schema)
            if info is not None:
                _, _, signature, _ = info
                if signature is not None:
                    if mode == "verbose" and self.terms is not None:
                        for term, expected_sig in zip(self.terms, signature):
                            expected_datatype = expected_sig[0]
                            if isinstance(term, ConstModel):
                                _validate_const_value(term.value, expected_datatype)
                    if mode == "compact" and self.args is not None:
                        for arg_value, expected_sig in zip(self.args, signature):
                            expected_datatype = expected_sig[0]
                            if isinstance(arg_value.value, ConstModel):
                                _validate_const_value(arg_value.value.value, expected_datatype)
            return self

    ExprModel = Annotated[
        Union[VarModel, ConstModel, CallModel, UnifyModel, IfModel, NotModel, RefExprModel],
        Field(discriminator="kind"),
    ]

    CallModel.model_rebuild()
    UnifyModel.model_rebuild()
    IfModel.model_rebuild()
    NotModel.model_rebuild()
    RefExprModel.model_rebuild()

    class RefModel(BaseModel):
        kind: Literal["ref"] = "ref"
        schema: str
        terms: list[ExprTermModel] | None = None
        args: list[ArgValueModel] | None = None
        negated: bool = False

        @model_validator(mode="after")
        def _check_allowed(self):
            if self.schema not in allowed_predicate_ids:
                raise ValueError(f"Ref predicate not in FactView: {self.schema}")
            expected = allowed_predicate_ids[self.schema]
            if mode == "verbose":
                if self.terms is None:
                    raise ValueError("Ref terms required in verbose mode.")
                if len(self.terms) != expected:
                    raise ValueError(_arity_error_message(
                        self.schema,
                        expected=expected,
                        got=len(self.terms),
                    ))
            else:
                if self.args is None:
                    raise ValueError("Ref args required in compact mode.")
                if len(self.args) != expected:
                    raise ValueError(_arity_error_message(
                        self.schema,
                        expected=expected,
                        got=len(self.args),
                        provided_arg_names=[arg.name for arg in self.args],
                    ))
            info = predicate_info.get(self.schema)
            if info is not None:
                _, _, signature, _ = info
                if signature is not None:
                    if mode == "verbose" and self.terms is not None:
                        for term, expected_sig in zip(self.terms, signature):
                            expected_datatype = expected_sig[0]
                            if isinstance(term, ConstModel):
                                _validate_const_value(term.value, expected_datatype)
                    if mode == "compact" and self.args is not None:
                        for arg_value, expected_sig in zip(self.args, signature):
                            expected_datatype = expected_sig[0]
                            if isinstance(arg_value.value, ConstModel):
                                _validate_const_value(arg_value.value.value, expected_datatype)
            return self

    class ExprWrapperModel(BaseModel):
        kind: Literal["expr"] = "expr"
        expr: ExprModel

    LiteralModel = Annotated[
        Union[RefModel, ExprWrapperModel],
        Field(discriminator="kind"),
    ]

    class CondModel(BaseModel):
        literals: list[LiteralModel]
        prob: float | None = Field(default=None, ge=0.0, le=1.0)

    class RuleInstanceModel(BaseModel):
        conditions: list[CondModel]

    return RuleInstanceModel


def _ref_schema(
    schema_id: str,
    name: str,
    arity: int,
    signature: list[ArgField] | None,
    description: str | None,
) -> dict[str, Any]:
    if signature is None:
        signature = [Value(name=f"Arg{i + 1}", datatype="any") for i in range(arity)]
    term_schema = {
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "const": "var"},
                    "name": {"type": "string"},
                },
                "required": ["kind", "name"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "const": "const"},
                    "value": {"type": ["string", "number", "boolean"]},
                },
                "required": ["kind", "value"],
                "additionalProperties": False,
            },
        ]
    }
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "const": "ref"},
            "schema": {"type": "string", "const": schema_id},
            "terms": {
                "type": "array",
                "items": term_schema,
                "minItems": arity,
                "maxItems": arity,
            },
            "negated": {"type": "boolean"},
        },
        "required": ["kind", "schema", "terms", "negated"],
        "additionalProperties": False,
    }


def build_responses_schema(
    view: FactView,
    library: Library | None = None,
    *,
    mode: Literal["verbose", "compact"] = "verbose",
) -> dict[str, Any]:
    """Build a JSON schema for OpenAI Responses API strict decoding (conditions only)."""
    allowed_preds = view.predicates()
    if not allowed_preds and (library is None or not library.predicate_ids()):
        raise SchemaError("FactView has no predicates.")

    # Expr IR schema
    expr_ref = {"$ref": "#/$defs/expr"}
    defs: dict[str, Any] = {
        "var": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "var"},
                "name": {"type": "string"},
            },
            "required": ["kind", "name"],
            "additionalProperties": False,
        },
        "const": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "const"},
                "value": {"type": ["string", "number", "boolean"]},
            },
            "required": ["kind", "value"],
            "additionalProperties": False,
        },
        "call": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "call"},
                "op": {"type": "string"},
                "args": {"type": "array", "items": expr_ref},
            },
            "required": ["kind", "op", "args"],
            "additionalProperties": False,
        },
        "unify": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "unify"},
                "lhs": expr_ref,
                "rhs": expr_ref,
            },
            "required": ["kind", "lhs", "rhs"],
            "additionalProperties": False,
        },
        "if": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "if"},
                "cond": expr_ref,
                "then": expr_ref,
                "else": expr_ref,
            },
            "required": ["kind", "cond", "then", "else"],
            "additionalProperties": False,
        },
        "not": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "not"},
                "expr": expr_ref,
            },
            "required": ["kind", "expr"],
            "additionalProperties": False,
        },
        "ref": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "const": "ref"},
                "schema": {"type": "string"},
                "terms": {
                    "type": "array",
                    "items": {
                        "anyOf": [
                            {"$ref": "#/$defs/var"},
                            {"$ref": "#/$defs/const"},
                        ]
                    },
                },
                "args": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {
                                "anyOf": [
                                    {"$ref": "#/$defs/var"},
                                    {"$ref": "#/$defs/const"},
                                ]
                            },
                        },
                        "required": ["name", "value"],
                        "additionalProperties": False,
                    },
                },
                "negated": {"type": "boolean"},
            },
            "required": ["kind", "schema", "negated"],
            "additionalProperties": False,
        },
    }
    if mode == "verbose":
        defs["ref"]["required"] = ["kind", "schema", "terms", "negated"]
    else:
        defs["ref"]["required"] = ["kind", "schema", "args", "negated"]

    defs["expr"] = {
        "anyOf": [
            {"$ref": "#/$defs/var"},
            {"$ref": "#/$defs/const"},
            {"$ref": "#/$defs/call"},
            {"$ref": "#/$defs/unify"},
            {"$ref": "#/$defs/if"},
            {"$ref": "#/$defs/not"},
            {"$ref": "#/$defs/ref"},
        ]
    }

    if mode == "verbose":
        ref_items: list[dict[str, Any]] = []
        for pred in allowed_preds:
            ref_items.append(
                _ref_schema(
                    pred.schema_id,
                    pred.name,
                    pred.arity,
                    pred.signature,
                    pred.description,
                )
            )
        if library is not None:
            for pred_id, spec in library.predicate_ids().items():
                signature = None
                if spec.signature is not None:
                    signature = [
                        Value(name=f"Arg{idx + 1}", datatype=item)
                        for idx, item in enumerate(spec.signature)
                    ]
                ref_items.append(
                    _ref_schema(pred_id, spec.name, spec.arity, signature, spec.description)
                )
        ref_schema = {"anyOf": ref_items}
    else:
        # compact: predicate-specific refs with fixed args length by arity.
        ref_items: list[dict[str, Any]] = []
        compact_arg_item = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {
                    "anyOf": [
                        {"$ref": "#/$defs/var"},
                        {"$ref": "#/$defs/const"},
                    ]
                },
            },
            "required": ["name", "value"],
            "additionalProperties": False,
        }
        for pred in allowed_preds:
            ref_items.append(
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "const": "ref"},
                        "schema": {"type": "string", "const": pred.schema_id},
                        "args": {
                            "type": "array",
                            "items": compact_arg_item,
                            "minItems": pred.arity,
                            "maxItems": pred.arity,
                        },
                        "negated": {"type": "boolean"},
                    },
                    "required": ["kind", "schema", "args", "negated"],
                    "additionalProperties": False,
                }
            )
        if library is not None:
            for pred_id, spec in library.predicate_ids().items():
                ref_items.append(
                    {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "const": "ref"},
                            "schema": {"type": "string", "const": pred_id},
                            "args": {
                                "type": "array",
                                "items": compact_arg_item,
                                "minItems": spec.arity,
                                "maxItems": spec.arity,
                            },
                            "negated": {"type": "boolean"},
                        },
                        "required": ["kind", "schema", "args", "negated"],
                        "additionalProperties": False,
                    }
                )
        ref_schema = {"anyOf": ref_items}
    expr_literal_schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "const": "expr"},
            "expr": expr_ref,
        },
        "required": ["kind", "expr"],
        "additionalProperties": False,
    }
    literal_schema = {"anyOf": [ref_schema, expr_literal_schema]}
    cond_schema = {
        "type": "object",
        "properties": {
            "literals": {"type": "array", "items": literal_schema},
            "prob": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["literals", "prob"],
        "additionalProperties": False,
    }

    result = {
        "type": "object",
        "properties": {
            "conditions": {"type": "array", "items": cond_schema},
        },
        "required": ["conditions"],
        "additionalProperties": False,
        "$defs": defs,
    }
    return _normalize_strict_schema(result)


def _format_arg_inline(name: str | None, datatype: str | None) -> str:
    arg_name = name or "Arg"
    dtype = datatype or "any"
    return f"'{arg_name}':({dtype})"


def _build_catalog_head_block(
    payload_mode: Literal["compact", "verbose"],
    rel_mode: Literal["none", "flattened", "composed"],
) -> str:
    ref_compact = (
        '{"kind":"ref","schema":"<schema_id>","args":[{"name":"ArgName","value":'
        '{"kind":"var","name":"X"}}],"negated":false}'
    )
    ref_verbose = (
        '{"kind":"ref","schema":"<schema_id>","terms":[{"kind":"var","name":"X"}],'
        '"negated":false}'
    )
    lines = [
        "Output JSON payload only (no prose).",
        "Graph abstraction: fact = entity node; rel = relation edge.",
        "Rel structure: Sub (subject endpoint), Obj (object endpoint), Props (edge attributes).",
        "Top-level payload: {\"conditions\":[{\"literals\":[...],\"prob\":0.0~1.0}]}",
        "Literal kinds: ref or expr.",
        f"Ref literal syntax ({payload_mode} mode):",
        f"- {ref_compact if payload_mode == 'compact' else ref_verbose}",
        "Expr literal syntax: {\"kind\":\"expr\",\"expr\":Expr}",
        "Expr forms: var, const, call, unify, if, not, ref.",
        "Term forms: {\"kind\":\"var\",\"name\":\"X\"} | {\"kind\":\"const\",\"value\":...}.",
        (
            "Call op whitelist: eq|ne|lt|le|gt|ge|add|sub|mul|div|mod "
            "(plus registered library expr ops)."
        ),
        (
            "Argument meaning should be inferred from argument names and roles; "
            "follow each predicate block argument order."
        ),
        f"Selected rel_mode for relation rendering context: {rel_mode}.",
        f"Selected payload mode for this catalog: {payload_mode}.",
        "Use only schema IDs listed in this catalog.",
    ]
    return "\n".join(lines)


def _predicate_prompt_block(
    pred: PredicateSchema,
    view: FactView,
    *,
    payload_mode: Literal["compact", "verbose"],
    rel_mode: Literal["none", "flattened", "composed"],
) -> str:
    lines = [
        f"[name={pred.name} | id={pred.schema_id}]",
        f"kind: {pred.kind}",
        f"arity: {pred.arity}",
        f"description: {pred.description or '-'}",
    ]
    if pred.kind == "fact":
        args = ", ".join(
            _format_arg_inline(arg.arg_name, arg.datatype) for arg in pred.signature
        )
        key_fields = list(pred.key_fields or [])
        by_name = {arg.arg_name: arg for arg in pred.signature}
        keys = ", ".join(
            _format_arg_inline(name, by_name.get(name).datatype if name in by_name else "any")
            for name in key_fields
        )
        lines.append("Context:")
        lines.append(
            f"- This predicate represents {pred.name} entities."
            + (f" {pred.description}" if pred.description else "")
        )
        lines.append("Generation constraints:")
        lines.append(f"- Args (required): {args or '-'}")
        lines.append(f"- Key fields (structured): {keys or '-'}")
        return "\n".join(lines)

    sub_schema = view.schema.get(str(pred.sub_schema_id))
    obj_schema = view.schema.get(str(pred.obj_schema_id))
    sub_keys = list((pred.endpoints or {}).get("sub_key_fields", []))
    obj_keys = list((pred.endpoints or {}).get("obj_key_fields", []))
    sub_by_name = {arg.arg_name: arg for arg in sub_schema.signature}
    obj_by_name = {arg.arg_name: arg for arg in obj_schema.signature}

    sub_key_text = ", ".join(
        _format_arg_inline(name, sub_by_name.get(name).datatype if name in sub_by_name else "any")
        for name in sub_keys
    )
    obj_key_text = ", ".join(
        _format_arg_inline(name, obj_by_name.get(name).datatype if name in obj_by_name else "any")
        for name in obj_keys
    )
    props = list(pred.props or [])
    props_text = ", ".join(_format_arg_inline(arg.arg_name, arg.datatype) for arg in props)
    composed_order = ", ".join(
        ["Sub", "Obj"] + [_format_arg_inline(arg.arg_name, arg.datatype) for arg in props]
    )
    flattened_order = ", ".join(
        _format_arg_inline(arg.arg_name, arg.datatype) for arg in pred.signature
    )

    lines.append("Context:")
    lines.append(
        "- The subject entity (Sub) is "
        f"a {sub_schema.name} node"
        + (f": {sub_schema.description}" if sub_schema.description else ".")
    )
    lines.append(
        "- The object entity (Obj) is "
        f"a {obj_schema.name} node"
        + (f": {obj_schema.description}" if obj_schema.description else ".")
    )
    lines.append(
        "- Relation semantics: "
        + (pred.description if pred.description else "No explicit description.")
    )
    lines.append("Generation constraints:")
    lines.append(f"- Sub key args (structured, required): {sub_key_text or '-'}")
    lines.append(f"- Obj key args (structured, required): {obj_key_text or '-'}")
    lines.append(f"- Prop args (structured, required): {props_text or '-'}")
    lines.append(f"- Required payload args: {flattened_order}")
    selected_view = flattened_order if rel_mode == "flattened" else composed_order
    lines.append(f"- Selected relation view (rel_mode={rel_mode}): {selected_view}")
    lines.append(
        "- If an arg is not semantically important for a condition, use a var placeholder "
        "such as {'kind':'var','name':'_'} instead of dropping the arg."
    )

    return "\n".join(lines)


def _library_prompt_block(pred_id: str, spec: LibrarySpec) -> str:
    arg_types = list(spec.signature or [])
    args = ", ".join(_format_arg_inline(f"Arg{idx + 1}", dtype) for idx, dtype in enumerate(arg_types))
    lines = [
        f"[name={spec.name} | id={pred_id}]",
        "kind: library",
        f"arity: {spec.arity}",
        f"description: {spec.description or '-'}",
        f"Args: {args or '-'}",
    ]
    return "\n".join(lines)


def build_predicate_catalog(
    view: FactView,
    library: Library | None = None,
    *,
    style: Literal["structured", "prompt_blocks"] = "structured",
    payload_mode: Literal["compact", "verbose"] = "compact",
    rel_mode: Literal["none", "flattened", "composed"] = "flattened",
) -> dict[str, Any]:
    """Build predicate catalog for LLM prompting (not strict decoding schema)."""

    if style not in {"structured", "prompt_blocks"}:
        raise SchemaError("Catalog style must be 'structured' or 'prompt_blocks'.")
    if payload_mode not in {"compact", "verbose"}:
        raise SchemaError("Catalog payload_mode must be 'compact' or 'verbose'.")
    if rel_mode not in {"none", "flattened", "composed"}:
        raise SchemaError("Catalog rel_mode must be 'none', 'flattened', or 'composed'.")

    catalog: dict[str, Any] = {}
    if style == "prompt_blocks":
        catalog["head"] = _build_catalog_head_block(payload_mode, rel_mode)

    for pred in view.predicates():
        if style == "prompt_blocks":
            catalog[pred.schema_id] = _predicate_prompt_block(
                pred,
                view,
                payload_mode=payload_mode,
                rel_mode=rel_mode,
            )
            continue

        entry: dict[str, Any] = {
            "name": pred.name,
            "kind": pred.kind,
            "arity": pred.arity,
            "arg_types": [arg.datatype for arg in pred.signature],
            "arg_names": [arg.arg_name for arg in pred.signature],
            "description": pred.description,
        }
        if pred.kind == "fact":
            entry["key_fields"] = list(pred.key_fields or [])
        else:
            entry["sub_schema_id"] = pred.sub_schema_id
            entry["obj_schema_id"] = pred.obj_schema_id
            entry["endpoints"] = pred.endpoints
            entry["props"] = [
                {"name": arg.arg_name, "datatype": arg.datatype}
                for arg in (pred.props or [])
            ]
        catalog[pred.schema_id] = entry

    if library is not None:
        for pred_id, spec in library.predicate_ids().items():
            if style == "prompt_blocks":
                catalog[pred_id] = _library_prompt_block(pred_id, spec)
                continue
            catalog[pred_id] = {
                "name": spec.name,
                "kind": "library",
                "arity": spec.arity,
                "arg_types": spec.signature or [],
                "arg_names": [f"Arg{idx + 1}" for idx in range(spec.arity)],
                "description": spec.description,
            }
    return catalog


def _builtin_ops() -> list[str]:
    return [
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
        "add",
        "sub",
        "mul",
        "div",
        "mod",
    ]


def _normalize_strict_schema(schema: Any) -> Any:
    """Normalize schema to strict JSON schema subset for structured outputs."""

    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            properties = schema["properties"]
            schema["required"] = sorted(properties.keys())
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False
        for value in schema.values():
            _normalize_strict_schema(value)
    elif isinstance(schema, list):
        for item in schema:
            _normalize_strict_schema(item)
    return schema
