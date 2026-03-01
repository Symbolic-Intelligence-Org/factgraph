from __future__ import annotations

import re
from typing import Any

from factpy_kernel.core.schema.schema_ir import CANONICAL_TAGS
from factpy_kernel.authoring.where_schema_lowering import (
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

    head = _compile_head(authoring_derivation)
    materialize_as = _compile_materialize_as(authoring_derivation)
    if materialize_as is None and isinstance(head, dict):
        materialize_as = "record" if head.get("callee_kind") == "entity_type" else "fact"
    if materialize_as is not None and isinstance(head, dict):
        callee_kind = head.get("callee_kind")
        if callee_kind == "pred_ref" and materialize_as != "fact":
            raise _compile_error(
                "predicate head must materialize as 'fact'",
                path="$.materialize_as",
            )

    explicit_target_pred_id = authoring_derivation.get("target_pred_id", authoring_derivation.get("target"))
    id_policy = _compile_id_policy(authoring_derivation)
    if materialize_as == "record":
        if head is None:
            raise _compile_error("materialize_as='record' requires head", path="$.head")
        if head.get("callee_kind") != "entity_type":
            raise _compile_error(
                "materialize_as='record' requires EntityType head (e.g. Speaks(...))",
                path="$.head.callee_kind",
            )
    lowered_target_pred_id: str | None = None
    lowered_head_vars: list[Any] | None = None
    if (
        head is not None
        and materialize_as == "record"
        and schema_ir is not None
        and (
            not isinstance(explicit_target_pred_id, str)
            or not explicit_target_pred_id
            or ("head_vars" not in authoring_derivation and "select" not in authoring_derivation)
        )
    ):
        lowered_target_pred_id, lowered_head_vars = _lower_record_head_with_schema(head=head, schema_ir=schema_ir)
        _validate_record_id_policy_with_schema(
            id_policy=id_policy,
            schema_ir=schema_ir,
            record_type=lowered_target_pred_id,
        )
    if materialize_as == "record" and id_policy is None and schema_ir is not None and isinstance(head, dict):
        record_type_for_id_policy = lowered_target_pred_id
        if not isinstance(record_type_for_id_policy, str) or not record_type_for_id_policy:
            entity_type = head.get("entity_type")
            if isinstance(entity_type, str) and entity_type:
                record_type_for_id_policy = entity_type
        if not isinstance(record_type_for_id_policy, str) or not record_type_for_id_policy:
            raise _compile_error(
                "cannot auto-derive record id_policy without record_type",
                path="$.id_policy",
            )
        id_policy = _derive_default_record_id_policy_with_schema(
            schema_ir=schema_ir,
            record_type=record_type_for_id_policy,
        )
        _validate_record_id_policy_with_schema(
            id_policy=id_policy,
            schema_ir=schema_ir,
            record_type=record_type_for_id_policy,
        )
    if (
        head is not None
        and materialize_as in {None, "fact"}
        and schema_ir is not None
        and (
            not isinstance(explicit_target_pred_id, str)
            or not explicit_target_pred_id
            or ("head_vars" not in authoring_derivation and "select" not in authoring_derivation)
        )
    ):
        if head.get("callee_kind") == "pred_ref":
            lowered_target_pred_id, lowered_head_vars = _lower_fact_head_with_schema(head=head, schema_ir=schema_ir)
        elif head.get("callee_kind") == "entity_type":
            lowered_target_pred_id, lowered_head_vars = _lower_record_head_projection_fact_with_schema(
                head=head,
                schema_ir=schema_ir,
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
    where = _compile_where(authoring_derivation, schema_ir=schema_ir)
    mode = _compile_mode(authoring_derivation)
    temporal_view = _compile_temporal_view(authoring_derivation)

    materialize_as_out = materialize_as or "fact"

    synthesized_head: dict[str, Any] | None = None
    if head is None and materialize_as_out == "fact" and schema_ir is not None:
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
        "temporal_view": temporal_view,
        "materialize_as": materialize_as_out,
    }
    if canonical_head is not None:
        out["head"] = canonical_head
    if id_policy is not None:
        out["id_policy"] = id_policy
    if (
        canonical_head is not None
        and materialize_as_out == "fact"
        and isinstance(canonical_head, dict)
        and canonical_head.get("callee_kind") == "entity_type"
        and schema_ir is not None
    ):
        projection = _resolve_record_projection_with_schema(
            schema_ir=schema_ir,
            record_type=canonical_head.get("entity_type"),
        )
        out["projection_pred_id"] = projection["projection_pred_id"]
        out["projection_arg_order"] = list(projection["projection_arg_order"])
    return out


def _lower_fact_head_with_schema(*, head: dict[str, Any], schema_ir: dict[str, Any]) -> tuple[str, list[Any]]:
    if head.get("kind") != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    if head.get("callee_kind") != "pred_ref":
        raise _compile_error(
            "schema-aware head lowering currently supports only predicate heads for materialize_as='fact'",
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

    missing = [name for name in arg_names if name not in kwargs]
    if missing:
        raise _compile_error(
            f"head kwargs missing predicate args: {', '.join(missing)}",
            path="$.head.kwargs",
        )
    extra = sorted([key for key in kwargs.keys() if key not in set(arg_names)])
    if extra:
        raise _compile_error(
            f"head kwargs includes unknown predicate args: {', '.join(extra)}",
            path="$.head.kwargs",
        )
    head_vars = [kwargs[name] for name in arg_names]
    return pred_id, head_vars


def _lower_record_head_with_schema(*, head: dict[str, Any], schema_ir: dict[str, Any]) -> tuple[str, list[Any]]:
    if head.get("kind") != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    if head.get("callee_kind") != "entity_type":
        raise _compile_error(
            "schema-aware record head lowering requires EntityType head for materialize_as='record'",
            path="$.head.callee_kind",
        )
    record_type = head.get("entity_type")
    kwargs = head.get("kwargs")
    if not isinstance(record_type, str) or not record_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    if not isinstance(kwargs, dict) or not kwargs:
        raise _compile_error("head.kwargs must be non-empty object", path="$.head.kwargs")

    role_specs = _find_record_role_specs(schema_ir=schema_ir, record_type=record_type)
    role_names = [role["field_name"] for role in role_specs]
    missing = [name for name in role_names if name not in kwargs]
    if missing:
        raise _compile_error(
            f"head kwargs missing record roles: {', '.join(missing)}",
            path="$.head.kwargs",
        )
    extra = sorted([key for key in kwargs.keys() if key not in set(role_names)])
    if extra:
        raise _compile_error(
            f"head kwargs includes unknown record roles: {', '.join(extra)}",
            path="$.head.kwargs",
        )
    head_vars = [kwargs[name] for name in role_names]
    return record_type, head_vars


def _lower_record_head_projection_fact_with_schema(
    *,
    head: dict[str, Any],
    schema_ir: dict[str, Any],
) -> tuple[str, list[Any]]:
    if head.get("kind") != "head_call":
        raise _compile_error("head.kind must be 'head_call'", path="$.head.kind")
    if head.get("callee_kind") != "entity_type":
        raise _compile_error(
            "schema-aware projection head lowering requires EntityType head for materialize_as='fact'",
            path="$.head.callee_kind",
        )
    record_type = head.get("entity_type")
    kwargs = head.get("kwargs")
    if not isinstance(record_type, str) or not record_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    if not isinstance(kwargs, dict) or not kwargs:
        raise _compile_error("head.kwargs must be non-empty object", path="$.head.kwargs")

    role_specs = _find_record_role_specs(schema_ir=schema_ir, record_type=record_type)
    role_names = [role["field_name"] for role in role_specs]
    missing_roles = [name for name in role_names if name not in kwargs]
    if missing_roles:
        raise _compile_error(
            f"head kwargs missing record roles: {', '.join(missing_roles)}",
            path="$.head.kwargs",
        )
    extra = sorted([key for key in kwargs.keys() if key not in set(role_names)])
    if extra:
        raise _compile_error(
            f"head kwargs includes unknown record roles: {', '.join(extra)}",
            path="$.head.kwargs",
        )

    projection = _resolve_record_projection_with_schema(schema_ir=schema_ir, record_type=record_type)
    projection_pred_id = projection["projection_pred_id"]
    projection_arg_order = projection["projection_arg_order"]
    role_map = {role["field_name"]: role for role in role_specs}

    pred = next(
        (
            p
            for p in schema_ir.get("predicates", [])
            if isinstance(p, dict) and p.get("pred_id") == projection_pred_id
        ),
        None,
    )
    if not isinstance(pred, dict):
        raise _compile_error(f"projection predicate not found: {projection_pred_id}", path="$.head")
    arg_specs = pred.get("arg_specs")
    if not isinstance(arg_specs, list) or len(arg_specs) != len(projection_arg_order):
        raise _compile_error(
            "projection predicate arity must match projection_arg_order length",
            path="$.head",
        )
    for idx, role_name in enumerate(projection_arg_order):
        role = role_map.get(role_name)
        arg_spec = arg_specs[idx] if idx < len(arg_specs) else None
        if role is None:
            raise _compile_error(
                f"projection_arg_order references unknown record role: {role_name}",
                path=f"$.head.projection_arg_order[{idx}]",
            )
        if not isinstance(arg_spec, dict):
            raise _compile_error("projection predicate arg_specs entry must be object", path="$.head")
        role_type = role["type_domain"]
        arg_type = arg_spec.get("type_domain")
        if isinstance(arg_type, str) and arg_type != role_type:
            raise _compile_error(
                "projection predicate arg type mismatches record role type",
                path=f"$.head.projection_arg_order[{idx}]",
            )

    head_vars = [kwargs[name] for name in projection_arg_order]
    return projection_pred_id, head_vars


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


def _find_record_role_specs(*, schema_ir: dict[str, Any], record_type: str) -> list[dict[str, str]]:
    predicates = schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise _compile_error("schema_ir.predicates must be list for head-based derivation compile", path="$.head")

    role_specs: list[dict[str, str]] = []
    exists_found = False
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != record_type:
            continue
        if pred.get("is_record_exists") is True:
            exists_found = True
            continue
        pred_id = pred.get("pred_id")
        arg_specs = pred.get("arg_specs")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise _compile_error(
                f"record role predicate {pred_id} must have arity 2 in v1 record derivation lowering",
                path="$.head",
            )
        if not isinstance(arg_specs[0], dict) or arg_specs[0].get("type_domain") != "entity_ref":
            raise _compile_error(
                f"record role predicate {pred_id} arg0 must be entity_ref",
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
        raise _compile_error(f"record exists predicate not found for {record_type}", path="$.head")
    if not role_specs:
        raise _compile_error(f"record role predicates not found for {record_type}", path="$.head")
    return role_specs


def _resolve_record_projection_with_schema(*, schema_ir: dict[str, Any], record_type: Any) -> dict[str, Any]:
    if not isinstance(record_type, str) or not record_type:
        raise _compile_error("head.entity_type must be non-empty string", path="$.head.entity_type")
    entities = schema_ir.get("entities", [])
    if not isinstance(entities, list):
        raise _compile_error("schema_ir.entities must be list for head-based derivation compile", path="$.head")
    record_entity = next(
        (e for e in entities if isinstance(e, dict) and e.get("entity_type") == record_type),
        None,
    )
    if not isinstance(record_entity, dict):
        raise _compile_error(f"record entity not found in schema: {record_type}", path="$.head")

    projection_pred_id = record_entity.get("projection_pred_id")
    if not isinstance(projection_pred_id, str) or not projection_pred_id:
        raise _compile_error(
            "record entity missing projection_pred_id for materialize_as='fact'",
            path="$.head",
        )
    projection_arg_order = record_entity.get("projection_arg_order")
    if not isinstance(projection_arg_order, list) or not projection_arg_order:
        raise _compile_error(
            "record entity missing projection_arg_order for materialize_as='fact'",
            path="$.head",
        )
    out_order: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(projection_arg_order):
        if not isinstance(item, str) or not item:
            raise _compile_error(
                "projection_arg_order entries must be non-empty strings",
                path=f"$.head.projection_arg_order[{idx}]",
            )
        if item in seen:
            raise _compile_error("projection_arg_order must not contain duplicates", path=f"$.head.projection_arg_order[{idx}]")
        seen.add(item)
        out_order.append(item)
    return {
        "projection_pred_id": projection_pred_id,
        "projection_arg_order": out_order,
    }


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
    if pred.get("is_record_exists") is True:
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


def _validate_record_id_policy_with_schema(
    *,
    id_policy: Any,
    schema_ir: dict[str, Any],
    record_type: str,
) -> None:
    if not isinstance(id_policy, dict):
        return
    if id_policy.get("kind") != "identity_fields_v1":
        return
    fields = id_policy.get("fields")
    if not isinstance(fields, list):
        return
    role_specs = _find_record_role_specs(schema_ir=schema_ir, record_type=record_type)
    role_map = {role["field_name"]: role for role in role_specs}
    for idx, item in enumerate(fields):
        if not isinstance(item, dict):
            continue
        role_name = item.get("role")
        if not isinstance(role_name, str):
            continue
        role_spec = role_map.get(role_name)
        if role_spec is None:
            raise _compile_error(
                f"id_policy references unknown record role: {role_name}",
                path=f"$.id_policy.fields[{idx}].role",
            )
        type_domain = item.get("type_domain")
        if isinstance(type_domain, str):
            pred = next(
                (
                    p
                    for p in schema_ir.get("predicates", [])
                    if isinstance(p, dict) and p.get("pred_id") == role_spec["pred_id"]
                ),
                None,
            )
            if isinstance(pred, dict):
                arg_specs = pred.get("arg_specs")
                if (
                    isinstance(arg_specs, list)
                    and len(arg_specs) >= 2
                    and isinstance(arg_specs[1], dict)
                ):
                    role_type = arg_specs[1].get("type_domain")
                    if isinstance(role_type, str) and role_type != type_domain:
                        raise _compile_error(
                            "id_policy field.type_domain mismatches record role type_domain",
                            path=f"$.id_policy.fields[{idx}].type_domain",
                        )


def _derive_default_record_id_policy_with_schema(
    *,
    schema_ir: dict[str, Any],
    record_type: str,
) -> dict[str, Any]:
    role_specs = _find_record_role_specs(schema_ir=schema_ir, record_type=record_type)
    fields: list[dict[str, str]] = []
    for role in role_specs:
        field_name = role.get("field_name")
        type_domain = role.get("type_domain")
        if not isinstance(field_name, str) or not field_name:
            raise _compile_error("record role missing field_name for id_policy auto-derive", path="$.id_policy")
        if not isinstance(type_domain, str) or type_domain not in CANONICAL_TAGS:
            raise _compile_error("record role missing canonical type_domain for id_policy auto-derive", path="$.id_policy")
        fields.append(
            {
                "name": field_name,
                "role": field_name,
                "type_domain": type_domain,
            }
        )
    return {
        "kind": "identity_fields_v1",
        "fields": fields,
    }


def _compile_materialize_as(payload: dict[str, Any]) -> str | None:
    if "materialize_as" not in payload:
        return None
    value = payload["materialize_as"]
    if value not in {"fact", "record"}:
        raise _compile_error("materialize_as must be 'fact' or 'record'", path="$.materialize_as")
    return str(value)


def _compile_id_policy(payload: dict[str, Any]) -> Any:
    if "id_policy" not in payload:
        return None
    raw = payload["id_policy"]
    if isinstance(raw, str):
        if not raw:
            raise _compile_error("id_policy must be non-empty string or object", path="$.id_policy")
        return raw
    if isinstance(raw, dict):
        kind = raw.get("kind")
        if not isinstance(kind, str) or not kind:
            raise _compile_error("id_policy.kind must be non-empty string", path="$.id_policy.kind")
        if kind == "identity_fields_v1":
            return _compile_identity_fields_id_policy(raw)
        return dict(raw)
    raise _compile_error("id_policy must be string or object", path="$.id_policy")


def _compile_identity_fields_id_policy(raw: dict[str, Any]) -> dict[str, Any]:
    fields = raw.get("fields")
    if not isinstance(fields, list) or not fields:
        raise _compile_error(
            "id_policy.fields must be non-empty list for identity_fields_v1",
            path="$.id_policy.fields",
        )
    normalized_fields: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for idx, item in enumerate(fields):
        path = f"$.id_policy.fields[{idx}]"
        if not isinstance(item, dict):
            raise _compile_error("id_policy field entry must be object", path=path)
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise _compile_error("id_policy field.name must be non-empty string", path=f"{path}.name")
        if name in seen_names:
            raise _compile_error("duplicate id_policy field.name", path=f"{path}.name")
        seen_names.add(name)

        role = item.get("role", item.get("from_role"))
        if not isinstance(role, str) or not role:
            raise _compile_error("id_policy field.role must be non-empty string", path=f"{path}.role")
        type_domain = item.get("type_domain")
        if not isinstance(type_domain, str) or type_domain not in CANONICAL_TAGS:
            raise _compile_error(
                "id_policy field.type_domain must be canonical tag",
                path=f"{path}.type_domain",
            )
        normalized_fields.append(
            {
                "name": name,
                "role": role,
                "type_domain": type_domain,
            }
        )
    return {"kind": "identity_fields_v1", "fields": normalized_fields}


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
    mode = payload.get("mode", "python")
    if mode not in {"python", "engine"}:
        raise _compile_error("mode must be 'python' or 'engine'", path="$.mode")
    return str(mode)


def _compile_temporal_view(payload: dict[str, Any]) -> str:
    temporal_view = payload.get("temporal_view", "record")
    if temporal_view not in {"record", "current"}:
        raise _compile_error("temporal_view must be 'record' or 'current'", path="$.temporal_view")
    return str(temporal_view)


def _compile_error(message: str, *, path: str) -> AuthoringDerivationCompileError:
    return AuthoringDerivationCompileError(message, path=path)
