from __future__ import annotations

import re
from typing import Any

from kernel.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AuthoringDerivationCompileError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


def compile_authoring_derivation_v1(
    authoring_derivation: dict[str, Any],
    *,
    schema_ir: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(authoring_derivation, dict):
        raise _compile_error("authoring_derivation must be object", path="$")

    derivation_id = authoring_derivation.get("derivation_id", authoring_derivation.get("name"))
    if not isinstance(derivation_id, str) or not derivation_id:
        raise _compile_error("derivation_id (or name) must be non-empty string", path="$.derivation_id")

    version = authoring_derivation.get("version", "v1")
    if not isinstance(version, str) or not version:
        raise _compile_error("version must be non-empty string", path="$.version")
    description = _compile_optional_description(authoring_derivation.get("description"), path="$.description")
    tags = _compile_optional_tags(authoring_derivation.get("tags"), path="$.tags")
    if "mode" in authoring_derivation:
        raise _compile_error(
            "mode is not accepted in derivation payload; use call-site engine selection",
            path="$.mode",
        )
    if "body_confidences" in authoring_derivation:
        raise _compile_error(
            "body_confidences is not accepted in derivation payload; "
            "use ProbLogRuleExt.branch_probabilities or future SemanticsProfile.rule_projection.problog",
            path="$.body_confidences",
        )
    if "engine_ext" in authoring_derivation:
        raise _compile_error(
            "engine_ext is not accepted in derivation payload; use future SemanticsProfile.rule_projection",
            path="$.engine_ext",
        )
    if "temporal_view" in authoring_derivation:
        # TODO: Support derivation-side temporal materialization semantics.
        # Snapshot read views already support .at(t) / .version(v) in sdk.facade.
        # This guard only blocks derivation/runtime temporal_view until rule-head
        # temporal write semantics (valid_from/valid_to/version) are specified.
        raise _compile_error(
            "temporal_view is removed; derivation evaluation uses active projection only",
            path="$.temporal_view",
        )
    where = _compile_where(authoring_derivation, schema_ir=schema_ir)

    head = _compile_head(authoring_derivation)
    if "materialize_as" in authoring_derivation:
        raise _compile_error(
            "materialize_as is removed from user syntax; candidate kind is inferred from head shape",
            path="$.materialize_as",
        )
    if "id_policy" in authoring_derivation:
        raise _compile_error(
            "id_policy is removed from user syntax in candidate protocol v2",
            path="$.id_policy",
        )

    explicit_target_pred_id = authoring_derivation.get("target_pred_id", authoring_derivation.get("target"))
    lowered_target_pred_id: str | None = None
    lowered_head_vars: list[Any] | None = None
    if (
        head is not None
        and schema_ir is not None
        and (
            not isinstance(explicit_target_pred_id, str)
            or not explicit_target_pred_id
            or ("head_vars" not in authoring_derivation and "select" not in authoring_derivation)
        )
    ):
        if head.get("callee_kind") == "pred_ref":
            lowered_target_pred_id, lowered_head_vars = _lower_fact_head_with_schema(
                head=head,
                schema_ir=schema_ir,
                where=where,
            )
        elif head.get("callee_kind") == "entity_type":
            lowered_target_pred_id, lowered_head_vars = _lower_entity_head_with_schema(
                head=head,
                schema_ir=schema_ir,
                where=where,
            )

    target_pred_id = explicit_target_pred_id if isinstance(explicit_target_pred_id, str) and explicit_target_pred_id else lowered_target_pred_id
    if not isinstance(target_pred_id, str) or not target_pred_id:
        if head is not None:
            raise _compile_error(
                "head-based derivation requires target_pred_id/target in current v1 implementation (or schema-aware compile context)",
                path="$.head",
            )
        raise _compile_error("target_pred_id (or target) must be non-empty string", path="$.target_pred_id")
    if lowered_target_pred_id is not None and target_pred_id != lowered_target_pred_id:
        raise _compile_error(
            "target_pred_id/target conflicts with head-derived target from schema",
            path="$.target_pred_id" if "target_pred_id" in authoring_derivation else "$.target",
        )

    if "head_vars" in authoring_derivation or "select" in authoring_derivation:
        head_vars = _compile_head_vars(authoring_derivation)
        if lowered_head_vars is not None and head_vars != lowered_head_vars:
            raise _compile_error(
                "head_vars/select conflicts with head-derived positional mapping from schema arg_specs",
                path="$.head_vars" if "head_vars" in authoring_derivation else "$.select",
            )
    elif lowered_head_vars is not None:
        head_vars = lowered_head_vars
    else:
        head_vars = _compile_head_vars(authoring_derivation)
    mode = _compile_mode(authoring_derivation)

    synthesized_head: dict[str, Any] | None = None
    if head is None and schema_ir is not None:
        synthesized_head = _synthesize_fact_head_from_target_with_schema(
            schema_ir=schema_ir,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
        )

    canonical_head = head if head is not None else synthesized_head

    out = {
        "derivation_id": derivation_id,
        "version": version,
        "target": target_pred_id,
        "target_pred_id": target_pred_id,
        "head_vars": head_vars,
        "where": where,
        "mode": mode,
    }
    if canonical_head is not None:
        out["head"] = canonical_head
    if description is not None:
        out["description"] = description
    if tags is not None:
        out["tags"] = tags
    return out


def _lower_fact_head_with_schema(
    *,
    head: dict[str, Any],
    schema_ir: dict[str, Any],
    where: list[Any],
) -> tuple[str, list[Any]]:
    if head.get("kind") != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    if head.get("callee_kind") != "pred_ref":
        raise _compile_error(
            "schema-aware head lowering requires predicate head form: Entity.field(...)",
            path="$.head.callee_kind",
        )
    entity_type = head.get("entity_type")
    field = head.get("field")
    kwargs = head.get("kwargs")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    if not isinstance(field, str) or not field:
        raise _compile_error("head.field must be non-empty string", path="$.head.field")
    if not isinstance(kwargs, dict) or not kwargs:
        raise _compile_error("head.kwargs must be non-empty object", path="$.head.kwargs")

    pred = _find_pred_for_head(schema_ir=schema_ir, entity_type=entity_type, field=field)
    pred_id = pred.get("pred_id")
    arg_specs = pred.get("arg_specs")
    if not isinstance(pred_id, str) or not pred_id:
        raise _compile_error("matched predicate missing pred_id", path="$.head")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise _compile_error("matched predicate missing arg_specs", path="$.head")

    arg_names: list[str] = []
    for idx, spec in enumerate(arg_specs):
        if not isinstance(spec, dict):
            raise _compile_error("matched predicate arg_specs entry must be object", path=f"$.head.arg_specs[{idx}]")
        arg_name = spec.get("name")
        if not isinstance(arg_name, str) or not arg_name:
            raise _compile_error("matched predicate arg_specs.name must be non-empty string", path=f"$.head.arg_specs[{idx}].name")
        arg_names.append(arg_name)

    if len(arg_names) != 2:
        raise _compile_error(
            f"matched predicate {pred_id} must have arity 2 for field head lowering",
            path="$.head",
        )

    primary_keys, non_primary_identity = _identity_field_names(schema_ir=schema_ir, entity_type=entity_type)
    forbidden_primary = sorted([name for name in kwargs.keys() if name in set(primary_keys)])
    if forbidden_primary:
        raise _compile_error(
            "head must not include primary_key identity fields; they are implicit from where entity binding: "
            + ", ".join(forbidden_primary),
            path="$.head.kwargs",
        )

    missing_non_primary = [name for name in non_primary_identity if name not in kwargs]
    if missing_non_primary:
        raise _compile_error(
            "head kwargs missing non-primary identity fields: " + ", ".join(missing_non_primary),
            path="$.head.kwargs",
        )

    value_keys = [field, "value", arg_names[1]]
    present_value_keys = [key for key in value_keys if key in kwargs]
    if not present_value_keys:
        raise _compile_error(
            f"head kwargs missing field value; provide '{field}=...' (or 'value=...')",
            path="$.head.kwargs",
        )
    chosen_value_key = present_value_keys[0]
    if len(set(present_value_keys)) > 1:
        first_value = kwargs[present_value_keys[0]]
        for key in present_value_keys[1:]:
            if kwargs[key] != first_value:
                raise _compile_error(
                    f"head value is ambiguous across keys: {', '.join(sorted(set(present_value_keys)))}",
                    path="$.head.kwargs",
                )
    allowed = set(non_primary_identity) | set(value_keys)
    extra = sorted([key for key in kwargs.keys() if key not in allowed])
    if extra:
        raise _compile_error(
            f"head kwargs includes unknown args: {', '.join(extra)}",
            path="$.head.kwargs",
        )

    entity_var = _infer_unique_entity_binding_var(
        schema_ir=schema_ir,
        where=where,
        entity_type=entity_type,
        required_field_terms={
            **{name: kwargs[name] for name in non_primary_identity},
            field: kwargs[chosen_value_key],
        },
    )
    head_vars = [entity_var, kwargs[chosen_value_key]]
    return pred_id, head_vars


def _lower_entity_head_with_schema(
    *,
    head: dict[str, Any],
    schema_ir: dict[str, Any],
    where: list[Any],
) -> tuple[str, list[Any]]:
    if head.get("kind") != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    if head.get("callee_kind") != "entity_type":
        raise _compile_error(
            "schema-aware entity head lowering requires EntityType head form: Entity(...)",
            path="$.head.callee_kind",
        )
    entity_type = head.get("entity_type")
    kwargs = head.get("kwargs")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    if not isinstance(kwargs, dict) or not kwargs:
        raise _compile_error("head.kwargs must be non-empty object", path="$.head.kwargs")

    primary_keys, _ = _identity_field_names(schema_ir=schema_ir, entity_type=entity_type)
    forbidden_primary = sorted([name for name in kwargs.keys() if name in set(primary_keys)])
    if forbidden_primary:
        raise _compile_error(
            "head must not include primary_key identity fields; they are implicit from where entity binding: "
            + ", ".join(forbidden_primary),
            path="$.head.kwargs",
        )
    _infer_unique_entity_binding_var(
        schema_ir=schema_ir,
        where=where,
        entity_type=entity_type,
        required_field_terms=dict(kwargs),
    )

    role_specs = _find_entity_field_specs(schema_ir=schema_ir, entity_type=entity_type)
    role_names = [role["field_name"] for role in role_specs]
    missing = [name for name in role_names if name not in kwargs]
    if missing:
        raise _compile_error(
            f"head kwargs missing entity fields: {', '.join(missing)}",
            path="$.head.kwargs",
        )
    extra = sorted([key for key in kwargs.keys() if key not in set(role_names)])
    if extra:
        raise _compile_error(
            f"head kwargs includes unknown entity fields: {', '.join(extra)}",
            path="$.head.kwargs",
        )
    head_vars = [kwargs[name] for name in role_names]
    return entity_type, head_vars


def _find_pred_for_head(*, schema_ir: dict[str, Any], entity_type: str, field: str) -> dict[str, Any]:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise _compile_error("schema_ir.predicates must be list for head-based derivation compile", path="$.head")

    matches: list[dict[str, Any]] = []
    fallback_matches: list[dict[str, Any]] = []
    expected_pred_id = f"{entity_type.lower()}:{field}"

    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        owner_type = pred.get("owner_type")
        py_field_name = pred.get("py_field_name")
        pred_id = pred.get("pred_id")
        if owner_type == entity_type and py_field_name == field:
            matches.append(pred)
            continue
        if isinstance(pred_id, str) and pred_id == expected_pred_id:
            fallback_matches.append(pred)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise _compile_error(
            f"head resolves ambiguously to multiple predicates for {entity_type}.{field}",
            path="$.head",
        )
    if len(fallback_matches) == 1:
        return fallback_matches[0]
    if len(fallback_matches) > 1:
        raise _compile_error(
            f"head fallback resolution ambiguous for {expected_pred_id}",
            path="$.head",
        )
    raise _compile_error(
        f"head predicate not found in schema for {entity_type}.{field}",
        path="$.head",
    )


def _find_entity_field_specs(*, schema_ir: dict[str, Any], entity_type: str) -> list[dict[str, str]]:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise _compile_error("schema_ir.predicates must be list for head-based derivation compile", path="$.head")

    role_specs: list[dict[str, str]] = []
    exists_found = False
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        if pred.get("is_entity_exists") is True:
            exists_found = True
            continue
        if pred.get("is_identity_field") is True:
            continue
        pred_id = pred.get("pred_id")
        arg_specs = pred.get("arg_specs")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise _compile_error(
                f"entity field predicate {pred_id} must have arity 2",
                path="$.head",
            )
        if not isinstance(arg_specs[0], dict) or arg_specs[0].get("type_domain") != "entity_ref":
            raise _compile_error(
                f"entity field predicate {pred_id} arg0 must be entity_ref",
                path="$.head",
            )
        field_name = pred.get("py_field_name")
        if not isinstance(field_name, str) or not field_name:
            local_name = pred_id.split(":", 1)[1] if ":" in pred_id else pred_id
            if not isinstance(local_name, str) or not local_name:
                raise _compile_error(f"cannot infer role field name for {pred_id}", path="$.head")
            field_name = local_name
        role_type = arg_specs[1].get("type_domain")
        role_specs.append({"field_name": field_name, "pred_id": pred_id, "type_domain": role_type})

    if not exists_found:
        raise _compile_error(f"entity exists predicate not found for {entity_type}", path="$.head")
    if not role_specs:
        raise _compile_error(f"entity field predicates not found for {entity_type}", path="$.head")
    return role_specs


def _synthesize_fact_head_from_target_with_schema(
    *,
    schema_ir: dict[str, Any],
    target_pred_id: str,
    head_vars: list[Any],
) -> dict[str, Any] | None:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        return None
    pred = next(
        (
            p
            for p in predicates
            if isinstance(p, dict) and p.get("pred_id") == target_pred_id
        ),
        None,
    )
    if not isinstance(pred, dict):
        return None
    if pred.get("is_entity_exists") is True:
        return None
    owner_type = pred.get("owner_type")
    py_field_name = pred.get("py_field_name")
    arg_specs = pred.get("arg_specs")
    if not isinstance(owner_type, str) or not owner_type:
        return None
    if not isinstance(py_field_name, str) or not py_field_name:
        return None
    if not isinstance(arg_specs, list) or len(arg_specs) != len(head_vars):
        return None
    kwargs: dict[str, Any] = {}
    for idx, spec in enumerate(arg_specs):
        if not isinstance(spec, dict):
            return None
        arg_name = spec.get("name")
        if not isinstance(arg_name, str) or not arg_name:
            return None
        kwargs[arg_name] = head_vars[idx]
    return {
        "kind": "head_call",
        "callee_kind": "pred_ref",
        "entity_type": owner_type,
        "field": py_field_name,
        "kwargs": kwargs,
    }


def _compile_head(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "head" not in payload:
        return None
    raw = payload["head"]
    if not isinstance(raw, dict):
        raise _compile_error("head must be object", path="$.head")
    kind = raw.get("kind")
    if kind != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    callee_kind = raw.get("callee_kind")
    if callee_kind not in {"pred_ref", "entity_type"}:
        raise _compile_error("head.callee_kind must be 'pred_ref' or 'entity_type'", path="$.head.callee_kind")
    entity_type = raw.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    out: dict[str, Any] = {
        "kind": "head_call",
        "callee_kind": callee_kind,
        "entity_type": entity_type,
    }
    if callee_kind == "pred_ref":
        field = raw.get("field")
        if not isinstance(field, str) or not field:
            raise _compile_error("head.field must be non-empty string", path="$.head.field")
        out["field"] = field
    kwargs = raw.get("kwargs")
    if not isinstance(kwargs, dict) or not kwargs:
        raise _compile_error("head.kwargs must be non-empty object", path="$.head.kwargs")
    norm_kwargs: dict[str, Any] = {}
    for key, value in kwargs.items():
        if not isinstance(key, str) or not key:
            raise _compile_error("head.kwargs keys must be non-empty strings", path="$.head.kwargs")
        norm_kwargs[key] = _normalize_head_kwarg_value(value, path=f"$.head.kwargs.{key}")
    out["kwargs"] = norm_kwargs
    return out


def _normalize_head_kwarg_value(value: Any, *, path: str) -> Any:
    if isinstance(value, str):
        if value.startswith("$"):
            if not _IDENT_RE.fullmatch(value[1:]):
                raise _compile_error("head variable must be '$' + identifier", path=path)
            return value
        if _IDENT_RE.fullmatch(value):
            return f"${value}"
        return value
    if isinstance(value, (int, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_normalize_head_kwarg_value(item, path=f"{path}[]") for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_head_kwarg_value(item, path=f"{path}[]") for item in value)
    raise _compile_error("head kwarg value must be str|int|bool|null|list|tuple", path=path)


def _compile_head_vars(payload: dict[str, Any]) -> list[Any]:
    has_head = "head_vars" in payload
    has_select = "select" in payload
    if not has_head and not has_select:
        raise _compile_error("head_vars (or select) is required", path="$.head_vars")
    if has_head and has_select and payload["head_vars"] != payload["select"]:
        raise _compile_error("head_vars and select conflict", path="$.select")
    raw = payload["head_vars"] if has_head else payload["select"]
    path = "$.head_vars" if has_head else "$.select"
    if not isinstance(raw, list) or not raw:
        raise _compile_error("head_vars must be non-empty list", path=path)

    out: list[Any] = []
    for idx, item in enumerate(raw):
        item_path = f"{path}[{idx}]"
        if isinstance(item, str):
            if item.startswith("$"):
                if not _IDENT_RE.fullmatch(item[1:]):
                    raise _compile_error("variable must be '$' + identifier", path=item_path)
                out.append(item)
                continue
            # bare identifier is interpreted as variable alias; other strings are literals
            if _IDENT_RE.fullmatch(item):
                out.append(f"${item}")
            else:
                out.append(item)
            continue
        if isinstance(item, (int, bool)):
            out.append(item)
            continue
        raise _compile_error("head var/literal must be str|int|bool", path=item_path)
    return out


def _compile_where(payload: dict[str, Any], *, schema_ir: dict[str, Any] | None = None) -> list[Any]:
    has_where = "where" in payload
    has_body = "body" in payload
    if not has_where and not has_body:
        raise _compile_error("where (or body) is required", path="$.where")
    if has_where and has_body and payload["where"] != payload["body"]:
        raise _compile_error("where and body conflict", path="$.body")
    raw = payload["where"] if has_where else payload["body"]
    if not isinstance(raw, list) or not raw:
        raise _compile_error("where must be non-empty list", path="$.where" if has_where else "$.body")
    try:
        return lower_blueprint_where_sugar_with_schema_v1(raw, schema_ir=schema_ir, path="$.where" if has_where else "$.body")
    except WhereSchemaLoweringError as exc:
        err_path = getattr(exc, "path", None) or ("$.where" if has_where else "$.body")
        raise _compile_error(str(exc), path=err_path)


def _compile_mode(payload: dict[str, Any]) -> str:
    del payload
    return "native"


def _identity_field_names(*, schema_ir: dict[str, Any], entity_type: str) -> tuple[list[str], list[str]]:
    entities = schema_ir.get("entities", [])
    if not isinstance(entities, list):
        raise _compile_error("schema_ir.entities must be list for head compile", path="$.head")
    entity = next(
        (
            row
            for row in entities
            if isinstance(row, dict) and row.get("entity_type") == entity_type
        ),
        None,
    )
    if not isinstance(entity, dict):
        raise _compile_error(f"entity type not found in schema: {entity_type}", path="$.head.entity_type")
    identity_fields = entity.get("identity_fields")
    if not isinstance(identity_fields, list) or not identity_fields:
        raise _compile_error(f"entity identity_fields missing for {entity_type}", path="$.head.entity_type")
    primary: list[str] = []
    non_primary: list[str] = []
    for idx, row in enumerate(identity_fields):
        if not isinstance(row, dict):
            raise _compile_error("identity field entry must be object", path=f"$.head.identity_fields[{idx}]")
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise _compile_error("identity field name must be non-empty string", path=f"$.head.identity_fields[{idx}].name")
        if row.get("primary_key") is True:
            primary.append(name)
        else:
            non_primary.append(name)
    return primary, non_primary


def _infer_unique_entity_binding_var(
    *,
    schema_ir: dict[str, Any],
    where: list[Any],
    entity_type: str,
    required_field_terms: dict[str, Any] | None = None,
) -> str:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise _compile_error("schema_ir.predicates must be list for head compile", path="$.where")
    owner_by_pred: dict[str, str] = {}
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        owner_type = pred.get("owner_type")
        if isinstance(pred_id, str) and pred_id and isinstance(owner_type, str) and owner_type:
            owner_by_pred[pred_id] = owner_type

    seen_vars: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, tuple) or not node:
            return
        if node[0] == "not" and len(node) == 2:
            walk(node[1])
            return
        if node[0] != "pred" or len(node) != 3:
            return
        pred_id, terms = node[1], node[2]
        if not isinstance(pred_id, str) or not isinstance(terms, list) or not terms:
            return
        if owner_by_pred.get(pred_id) != entity_type:
            return
        first = terms[0]
        if isinstance(first, str) and first.startswith("$") and len(first) > 1:
            seen_vars.add(first)

    walk(where)
    if not seen_vars:
        raise _compile_error(
            f"where must bind one {entity_type} entity variable for head primary_key implicit carry",
            path="$.where",
        )
    if len(seen_vars) > 1 and isinstance(required_field_terms, dict) and required_field_terms:
        disambiguated = _disambiguate_entity_binding_with_head_terms(
            schema_ir=schema_ir,
            where=where,
            entity_type=entity_type,
            candidate_vars=seen_vars,
            required_field_terms=required_field_terms,
        )
        if isinstance(disambiguated, str):
            return disambiguated
    if len(seen_vars) > 1:
        raise _compile_error(
            f"where binds multiple {entity_type} entity variables (ambiguous): {', '.join(sorted(seen_vars))}",
            path="$.where",
        )
    return next(iter(seen_vars))


def _disambiguate_entity_binding_with_head_terms(
    *,
    schema_ir: dict[str, Any],
    where: list[Any],
    entity_type: str,
    candidate_vars: set[str],
    required_field_terms: dict[str, Any],
) -> str | None:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        return None
    pred_by_field: dict[str, str] = {}
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        field_name = pred.get("py_field_name")
        pred_id = pred.get("pred_id")
        if isinstance(field_name, str) and field_name and isinstance(pred_id, str) and pred_id:
            pred_by_field[field_name] = pred_id

    field_requirements: list[tuple[str, Any]] = []
    for field_name, term in required_field_terms.items():
        pred_id = pred_by_field.get(field_name)
        if isinstance(pred_id, str) and pred_id:
            field_requirements.append((pred_id, term))
    if not field_requirements:
        return None

    requirement_matches: list[set[str]] = []
    for expected_pred_id, expected_term in field_requirements:
        requirement_vars: set[str] = set()

        def walk_requirement(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk_requirement(item)
                return
            if not isinstance(node, tuple) or len(node) != 3 or node[0] != "pred":
                return
            pred_id, terms = node[1], node[2]
            if pred_id != expected_pred_id:
                return
            if not isinstance(terms, list) or len(terms) < 2:
                return
            first = terms[0]
            if not (isinstance(first, str) and first in candidate_vars):
                return
            if terms[1] == expected_term:
                requirement_vars.add(first)

        walk_requirement(where)
        if requirement_vars:
            requirement_matches.append(requirement_vars)

    if not requirement_matches:
        return None
    intersection = set(candidate_vars)
    for row in requirement_matches:
        intersection &= row
    if len(intersection) == 1:
        return next(iter(intersection))
    return None


def _compile_error(message: str, *, path: str) -> AuthoringDerivationCompileError:
    return AuthoringDerivationCompileError(message, path=path)


def _compile_optional_description(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _compile_error("description must be non-empty string", path=path)
    return value


def _compile_optional_tags(value: Any, *, path: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _compile_error("tags must be list[str]", path=path)
    out: list[str] = []
    for index, tag in enumerate(value):
        if not isinstance(tag, str) or not tag:
            raise _compile_error("tags items must be non-empty string", path=f"{path}[{index}]")
        out.append(tag)
    return out
