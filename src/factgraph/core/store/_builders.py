from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from uuid import uuid4

from factgraph.core.derivation.candidates import CandidateSet, compute_key_tuple_digest, make_candidate
from factgraph.core.evidence.write_protocol import now_epoch_nanos
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import CANONICAL_TAGS, canonical_bytes_tup_v1
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    BindingSupportCapture,
    normalize_binding_items,
)

_BYTES_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")


def candidates_from_bindings(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    arg_specs: list[dict[str, Any]],
    head_vars: list[Any],
    schema_pred: dict[str, Any],
    rows: list[BindingSupportCapture] | None = None,
    bindings: list[dict[str, Any]] | None = None,
    confidence_kind_resolver: Any | None = None,
) -> list[CandidateSet]:
    run_id = uuid4().hex
    group_key_indexes = read_group_key_indexes(schema_pred, len(arg_specs))
    binding_rows = _coerce_binding_rows(rows=rows, bindings=bindings)

    candidates: list[CandidateSet] = []
    for row in binding_rows:
        binding = row.binding_dict()
        tagged_args = build_tagged_args(arg_specs, head_vars, binding)

        e_tag, e_ref = tagged_args[0]
        if e_tag != "entity_ref":
            raise WhereValidationError("target arg0 must be entity_ref")

        rest_terms = [(tag, value) for tag, value in tagged_args[1:]]
        try:
            canonical_bytes_tup_v1(rest_terms)
        except ValueError as exc:
            raise WhereValidationError(f"invalid rest_terms for target payload: {exc}") from exc

        dims_terms: list[tuple[str, Any]] = []
        for idx in group_key_indexes:
            if idx == 0:
                continue
            dims_terms.append(tagged_args[idx])

        key_terms = [("string", target_pred_id), ("entity_ref", e_ref), *dims_terms]
        tup_digest = sha256_token(canonical_bytes_tup_v1(rest_terms))

        candidate = make_candidate(
            derivation_id=derivation_id,
            derivation_version=version,
            run_id=run_id,
            target=target_pred_id,
            key_terms=key_terms,
            payload={
                "pred_id": target_pred_id,
                "terms": [_term_from_tag_value(tag, value) for tag, value in tagged_args],
            },
            support_digest=row.support_digest,
            support_kind=row.support_kind,
            generated_at=now_epoch_nanos(),
            tup_digest=tup_digest,
            state="generated",
            candidate_kind="fact",
            confidence_kind=_resolve_confidence_kind(
                confidence_kind_resolver,
                row.support_digest,
                row.support_kind,
                store,
            ),
        )
        candidates.append(candidate)

    unique: dict[str, CandidateSet] = {}
    for candidate in candidates:
        existing = unique.get(candidate.candidate_key)
        if existing is None or _support_is_better(candidate, existing):
            unique[candidate.candidate_key] = candidate

    return sorted(unique.values(), key=lambda cand: cand.candidate_key)


def entity_candidates_from_bindings(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    entity_spec: dict[str, Any],
    rows: list[BindingSupportCapture] | None = None,
    bindings: list[dict[str, Any]] | None = None,
    confidence_kind_resolver: Any | None = None,
) -> list[CandidateSet]:
    run_id = uuid4().hex
    entity_type = entity_spec["entity_type"]
    role_defs = entity_spec["roles"]
    head_values = entity_spec["head_vars"]
    binding_rows = _coerce_binding_rows(rows=rows, bindings=bindings)

    candidates: list[CandidateSet] = []
    for row in binding_rows:
        binding = row.binding_dict()
        tagged_role_terms: list[tuple[str, Any]] = []
        role_payloads: list[dict[str, Any]] = []
        for role_def, head_ref in zip(role_defs, head_values):
            tag = role_def["type_domain"]
            value = resolve_head_ref(head_ref, binding)
            coerced = coerce_value_for_tag(tag, value)
            tagged_role_terms.append((tag, coerced))
            role_payloads.append(
                {
                    "pred_id": role_def["pred_id"],
                    "field_name": role_def["field_name"],
                    "type_domain": tag,
                    "rest_terms": [(tag, coerced)],
                }
            )

        key_terms = [("string", entity_type), *tagged_role_terms]
        key_tuple_digest = compute_key_tuple_digest(key_terms)

        identity_fields, resolved_identity, missing_identity_fields = _derive_entity_identity_from_roles(
            entity_type=entity_type,
            key_tuple_digest=key_tuple_digest,
            roles=role_payloads,
            schema_identity_fields=entity_spec.get("entity_identity_fields"),
        )
        proposed_entity_ref: str | None = None
        if not missing_identity_fields:
            proposed_entity_ref = encode_idref_v1(
                entity_type,
                [(name, tag, resolved_identity[name]) for name, tag in identity_fields if name in resolved_identity],
            )

        entity_candidate = CandidateSet(
            derivation_id=derivation_id,
            derivation_version=version,
            run_id=run_id,
            target=entity_type,
            key_tuple_digest=key_tuple_digest,
            tup_digest=None,
            payload={
                "entity_type": entity_type,
                "identity_fields": [name for name, _ in identity_fields],
                "identity_types": {name: tag for name, tag in identity_fields},
                "resolved_identity": resolved_identity,
                "missing_identity_fields": missing_identity_fields,
                "proposed_entity_ref": proposed_entity_ref,
            },
            support_digest=row.support_digest,
            support_kind=row.support_kind,
            generated_at=now_epoch_nanos(),
            state="generated",
            candidate_kind="entity",
            confidence_kind=_resolve_confidence_kind(
                confidence_kind_resolver,
                row.support_digest,
                row.support_kind,
                store,
            ),
        )
        candidates.append(entity_candidate)

        for role in role_payloads:
            role_terms = role["rest_terms"]
            value_tag, value_atom = role_terms[0]
            fact_terms = [
                {"kind": "candidate_ref", "candidate_key": entity_candidate.candidate_key},
                _term_from_tag_value(value_tag, value_atom),
            ]
            fact_key_terms = [("string", role["pred_id"]), ("string", entity_candidate.candidate_key)]
            fact_tup_digest = sha256_token(canonical_bytes_tup_v1(role_terms))
            role_candidate = make_candidate(
                derivation_id=derivation_id,
                derivation_version=version,
                run_id=run_id,
                target=role["pred_id"],
                key_terms=fact_key_terms,
                payload={
                    "pred_id": role["pred_id"],
                    "terms": fact_terms,
                },
                support_digest=row.support_digest,
                support_kind=row.support_kind,
                generated_at=now_epoch_nanos(),
                tup_digest=fact_tup_digest,
                state="generated",
                candidate_kind="fact",
                confidence_kind=_resolve_confidence_kind(
                    confidence_kind_resolver,
                    row.support_digest,
                    row.support_kind,
                    store,
                ),
            )
            candidates.append(role_candidate)

    unique: dict[tuple[Any, ...], CandidateSet] = {}
    for candidate in candidates:
        key = (candidate.candidate_kind, candidate.candidate_key)
        existing = unique.get(key)
        if existing is None or _support_is_better(candidate, existing):
            unique[key] = candidate
    return sorted(unique.values(), key=lambda cand: (cand.candidate_kind, cand.candidate_key))


def _coerce_binding_rows(
    *,
    rows: list[BindingSupportCapture] | None,
    bindings: list[dict[str, Any]] | None,
) -> list[BindingSupportCapture]:
    if rows is not None and bindings is not None:
        raise ValueError("pass either rows or bindings, not both")
    if rows is not None:
        return list(rows)
    if bindings is None:
        raise ValueError("rows or bindings must be provided")
    return [
        BindingSupportCapture(
            binding_items=normalize_binding_items(binding),
            support_digest=f"sha256:{'0' * 64}",
            support_kind=ENGINE_NO_WITNESS_KIND,
        )
        for binding in bindings
    ]


def _support_is_better(candidate: CandidateSet, existing: CandidateSet) -> bool:
    if candidate.support_digest < existing.support_digest:
        return True
    if candidate.support_digest == existing.support_digest:
        return candidate.support_kind < existing.support_kind
    return False


def _resolve_confidence_kind(
    resolver: Any | None,
    support_digest: str,
    support_kind: str,
    store: Any,
) -> str:
    if resolver is None:
        return "none"
    return resolver.resolve(support_digest, support_kind, store._lookup_support_artifact)


def find_schema_pred(store: Any, pred_id: str) -> dict[str, Any] | None:
    predicates = store.schema_ir.get("predicates")
    if not isinstance(predicates, list):
        return None
    for schema_pred in predicates:
        if not isinstance(schema_pred, dict):
            continue
        if schema_pred.get("pred_id") == pred_id:
            return schema_pred
    return None


def entity_spec_from_head(
    store: Any,
    *,
    entity_type: str,
    head: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(entity_type, str) or not entity_type:
        raise WhereValidationError("entity target must be non-empty entity type string")
    if not isinstance(head, dict):
        raise WhereValidationError("entity derivation requires head object")
    if head.get("kind") != "head_call" or head.get("callee_kind") != "entity_type":
        raise WhereValidationError("entity derivation head must be EntityType(...)")
    if head.get("entity_type") != entity_type:
        raise WhereValidationError("entity derivation head entity_type must equal target")
    kwargs = head.get("kwargs")
    if not isinstance(kwargs, dict) or not kwargs:
        raise WhereValidationError("entity derivation head.kwargs must be non-empty object")

    entities = store.schema_ir.get("entities", [])
    if not isinstance(entities, list):
        raise WhereValidationError("schema_ir.entities must be list")
    schema_entity = None
    for entity in entities:
        if isinstance(entity, dict) and entity.get("entity_type") == entity_type:
            schema_entity = entity
            break
    if not isinstance(schema_entity, dict):
        raise WhereValidationError(f"entity not found in schema: {entity_type}")

    predicates = store.schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise WhereValidationError("schema_ir.predicates must be list")
    role_defs: list[dict[str, Any]] = []
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != entity_type:
            continue
        pred_id = pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if pred.get("is_entity_exists") is True:
            continue
        if pred.get("is_identity_field") is True:
            continue
        arg_specs = pred.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise WhereValidationError(f"entity field predicate must be arity 2: {pred_id}")
        if not isinstance(arg_specs[0], dict) or arg_specs[0].get("type_domain") != "entity_ref":
            raise WhereValidationError(f"entity field predicate arg0 must be entity_ref: {pred_id}")
        if not isinstance(arg_specs[1], dict):
            raise WhereValidationError(f"entity field predicate arg1 spec invalid: {pred_id}")
        tag = arg_specs[1].get("type_domain")
        if tag not in CANONICAL_TAGS:
            raise WhereValidationError(f"entity field predicate arg1 type_domain invalid: {pred_id}")
        field_name = pred.get("py_field_name")
        if not isinstance(field_name, str) or not field_name:
            field_name = pred_id.split(":", 1)[1] if ":" in pred_id else pred_id
        role_defs.append({"field_name": field_name, "pred_id": pred_id, "type_domain": tag})
    if not role_defs:
        raise WhereValidationError(f"entity field predicates not found for: {entity_type}")

    role_names = [role["field_name"] for role in role_defs]
    missing = [name for name in role_names if name not in kwargs]
    if missing:
        raise WhereValidationError(f"entity head missing field kwargs: {missing}")
    extra = sorted([key for key in kwargs.keys() if key not in set(role_names)])
    if extra:
        raise WhereValidationError(f"entity head contains unknown field kwargs: {extra}")

    head_vars = [kwargs[name] for name in role_names]
    return {
        "entity_type": entity_type,
        "roles": role_defs,
        "head_vars": head_vars,
        "entity_identity_fields": schema_entity.get("identity_fields"),
    }


def read_group_key_indexes(schema_pred: dict, arg_count: int) -> list[int]:
    group_key_indexes = schema_pred.get("group_key_indexes")
    if not isinstance(group_key_indexes, list):
        raise WhereValidationError("group_key_indexes must be list")

    last = -1
    out: list[int] = []
    for idx in group_key_indexes:
        if isinstance(idx, bool) or not isinstance(idx, int):
            raise WhereValidationError("group_key_indexes values must be int")
        if idx < 0 or idx >= arg_count:
            raise WhereValidationError("group_key_indexes contains out-of-range value")
        if idx <= last:
            raise WhereValidationError("group_key_indexes must be strictly ascending")
        out.append(idx)
        last = idx
    return out


def _term_from_tag_value(tag: str, value: Any) -> dict[str, Any]:
    if tag == "entity_ref":
        if not isinstance(value, str) or not value:
            raise WhereValidationError("entity_ref value must be non-empty string")
        return {"kind": "entity_ref", "value": value}
    return {"kind": "literal", "tag": tag, "value": value}


def _derive_entity_identity_from_roles(
    *,
    entity_type: str,
    key_tuple_digest: str,
    roles: list[dict[str, Any]],
    schema_identity_fields: list[dict[str, Any]] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, Any], list[str]]:
    role_map: dict[str, tuple[str, Any]] = {}
    for role in roles:
        field_name = role.get("field_name")
        rest_terms = role.get("rest_terms")
        if not isinstance(field_name, str) or not isinstance(rest_terms, list) or len(rest_terms) != 1:
            continue
        tag, val = rest_terms[0]
        role_map[field_name] = (str(tag), val)

    if isinstance(schema_identity_fields, list) and schema_identity_fields:
        identity_fields: list[tuple[str, str]] = []
        resolved_identity: dict[str, Any] = {}
        missing_identity_fields: list[str] = []
        for idx, field in enumerate(schema_identity_fields):
            if not isinstance(field, dict):
                raise WhereValidationError(f"identity_fields[{idx}] must be object")
            name = field.get("name")
            type_domain = field.get("type_domain")
            if not isinstance(name, str) or not name:
                raise WhereValidationError(f"identity_fields[{idx}].name must be non-empty string")
            if not isinstance(type_domain, str) or type_domain not in CANONICAL_TAGS:
                raise WhereValidationError(f"identity_fields[{idx}].type_domain must be canonical tag")
            identity_fields.append((name, type_domain))

            if name in role_map:
                actual_tag, value = role_map[name]
                if actual_tag != type_domain:
                    raise WhereValidationError(
                        f"identity field {name} type mismatches role tag: expected {type_domain}, got {actual_tag}"
                    )
                resolved_identity[name] = value
                continue

            if "default" in field:
                resolved_identity[name] = coerce_value_for_tag(type_domain, field.get("default"))
                continue

            if field.get("default_factory") == "uuid4":
                # Non-deterministic factory is never auto-filled in derivation evaluation.
                missing_identity_fields.append(name)
                continue

            missing_identity_fields.append(name)
        return identity_fields, resolved_identity, missing_identity_fields

    # Fallback deterministic identity: key tuple digest.
    identity_fields = [("key_tuple_digest", "string")]
    resolved_identity = {"key_tuple_digest": key_tuple_digest}
    missing_identity_fields: list[str] = []
    _ = entity_type  # reserved for future per-entity defaults
    return identity_fields, resolved_identity, missing_identity_fields


def build_tagged_args(
    arg_specs: list[dict[str, Any]],
    head_vars: list[Any],
    binding: dict[str, Any],
) -> list[tuple[str, Any]]:
    tagged_args: list[tuple[str, Any]] = []

    for idx, (arg_spec, head_ref) in enumerate(zip(arg_specs, head_vars)):
        if not isinstance(arg_spec, dict):
            raise WhereValidationError(f"arg_specs[{idx}] must be object")
        tag = arg_spec.get("type_domain")
        if tag not in CANONICAL_TAGS:
            raise WhereValidationError(f"arg_specs[{idx}].type_domain invalid: {tag}")

        value = resolve_head_ref(head_ref, binding)
        coerced = coerce_value_for_tag(tag, value)
        tagged_args.append((tag, coerced))

    return tagged_args


def resolve_head_ref(head_ref: Any, binding: dict[str, Any]) -> Any:
    if isinstance(head_ref, str) and head_ref.startswith("$"):
        if head_ref not in binding:
            raise WhereValidationError(f"unbound head variable: {head_ref}")
        return binding[head_ref]
    return head_ref


def coerce_value_for_tag(tag: str, value: Any) -> Any:
    if tag == "entity_ref":
        if not isinstance(value, str) or not value.startswith("idref_v1:"):
            raise WhereValidationError("entity_ref value must be idref_v1 token")
        candidate = value
    elif tag == "string":
        if not isinstance(value, str):
            raise WhereValidationError("string value must be str")
        candidate = value
    elif tag == "int":
        if isinstance(value, str):
            if not re.fullmatch(r"-?\d+", value):
                raise WhereValidationError("int string must be decimal integer")
            candidate = int(value)
        elif isinstance(value, bool) or not isinstance(value, int):
            raise WhereValidationError("int value must be int")
        else:
            candidate = value
    elif tag == "float64":
        if isinstance(value, bool) or not isinstance(value, (float, str)):
            raise WhereValidationError("float64 value must be float or 0x<16hex> string")
        candidate = value
    elif tag == "bool":
        if isinstance(value, str):
            if value == "true":
                candidate = True
            elif value == "false":
                candidate = False
            else:
                raise WhereValidationError("bool string must be 'true' or 'false'")
        elif not isinstance(value, bool):
            raise WhereValidationError("bool value must be bool")
        else:
            candidate = value
    elif tag == "bytes":
        candidate = coerce_bytes(value)
    elif tag == "time":
        if isinstance(value, str):
            if not re.fullmatch(r"-?\d+", value):
                raise WhereValidationError("time string must be epoch-nanos decimal int")
            candidate = int(value)
        elif isinstance(value, bool) or not isinstance(value, int):
            raise WhereValidationError("time value must be epoch-nanos int")
        else:
            candidate = value
    elif tag == "uuid":
        if not isinstance(value, str):
            raise WhereValidationError("uuid value must be canonical string")
        candidate = value
    else:
        raise WhereValidationError(f"unsupported tag: {tag}")

    try:
        canonical_bytes_tup_v1([(tag, candidate)])
    except ValueError as exc:
        raise WhereValidationError(f"invalid {tag} value: {exc}") from exc
    return candidate


def coerce_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, str):
        if not _BYTES_B64URL_RE.fullmatch(value):
            raise WhereValidationError("bytes string must be base64url no-pad")
        padded = value + ("=" * ((4 - len(value) % 4) % 4))
        try:
            return base64.urlsafe_b64decode(padded.encode("ascii"))
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise WhereValidationError("bytes string must be valid base64url") from exc
    raise WhereValidationError("bytes value must be bytes-like or base64url string")


def hashable_value(value: Any) -> Any:
    if isinstance(value, (str, int, bool, bytes)):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    return str(value)
