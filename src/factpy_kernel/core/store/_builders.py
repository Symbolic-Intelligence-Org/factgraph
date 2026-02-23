from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from uuid import uuid4

from factpy_kernel.core.derivation.candidates import CandidateSet, compute_key_tuple_digest, make_candidate
from factpy_kernel.core.evidence.write_protocol import now_epoch_nanos
from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.protocol.tup_v1 import CANONICAL_TAGS, canonical_bytes_tup_v1
from factpy_kernel.core.rules.where_eval import WhereValidationError

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
    bindings: list[dict[str, Any]],
) -> list[CandidateSet]:
    run_id = uuid4().hex
    group_key_indexes = read_group_key_indexes(schema_pred, len(arg_specs))

    candidates: list[CandidateSet] = []
    for binding in bindings:
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
                "e_ref": e_ref,
                "rest_terms": rest_terms,
            },
            support_digest=f"sha256:{'0' * 64}",
            support_kind="none",
            generated_at=now_epoch_nanos(),
            tup_digest=tup_digest,
            state="generated",
        )
        candidates.append(candidate)

    unique: dict[tuple[Any, ...], CandidateSet] = {}
    for candidate in candidates:
        payload = candidate.payload
        rest_terms = payload.get("rest_terms", [])
        key = (
            candidate.key_tuple_digest,
            payload.get("e_ref"),
            tuple((tag, hashable_value(value)) for tag, value in rest_terms),
        )
        if key not in unique:
            unique[key] = candidate

    return sorted(unique.values(), key=lambda cand: (cand.key_tuple_digest, cand.tup_digest or ""))


def record_candidates_from_bindings(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    record_spec: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> list[CandidateSet]:
    run_id = uuid4().hex
    record_type = record_spec["record_type"]
    role_defs = record_spec["roles"]
    record_exists_pred_id = record_spec["record_exists_pred_id"]
    id_policy = record_spec["id_policy"]
    head_values = record_spec["head_vars"]

    candidates: list[CandidateSet] = []
    for binding in bindings:
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

        key_terms = [("string", record_type), *tagged_role_terms]
        key_tuple_digest = compute_key_tuple_digest(key_terms)
        candidate = CandidateSet(
            derivation_id=derivation_id,
            derivation_version=version,
            run_id=run_id,
            target=record_type,
            key_tuple_digest=key_tuple_digest,
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": record_type,
                "record_exists_pred_id": record_exists_pred_id,
                "id_policy": id_policy,
                "roles": role_payloads,
            },
            support_digest=f"sha256:{'0' * 64}",
            support_kind="none",
            generated_at=now_epoch_nanos(),
            state="generated",
        )
        candidates.append(candidate)

    unique: dict[tuple[Any, ...], CandidateSet] = {}
    for candidate in candidates:
        roles = candidate.payload.get("roles", [])
        role_key = []
        for role in roles:
            rest_terms = role.get("rest_terms", [])
            role_key.append(
                (
                    role.get("pred_id"),
                    tuple((tag, hashable_value(value)) for tag, value in rest_terms),
                )
            )
        key = (candidate.key_tuple_digest, tuple(role_key))
        if key not in unique:
            unique[key] = candidate
    return sorted(unique.values(), key=lambda cand: cand.key_tuple_digest)


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


def record_materialize_spec_from_head(
    store: Any,
    *,
    record_type: str,
    head: dict[str, Any] | None,
    id_policy: Any | None,
) -> dict[str, Any]:
    if not isinstance(record_type, str) or not record_type:
        raise WhereValidationError("record target must be non-empty entity type string")
    if not isinstance(head, dict):
        raise WhereValidationError("record derivation requires head object")
    if head.get("kind") != "head_call" or head.get("callee_kind") != "entity_type":
        raise WhereValidationError("record derivation head must be EntityType(...)")
    if head.get("entity_type") != record_type:
        raise WhereValidationError("record derivation head entity_type must equal target")
    if id_policy is None:
        raise WhereValidationError("record derivation requires id_policy")
    kwargs = head.get("kwargs")
    if not isinstance(kwargs, dict) or not kwargs:
        raise WhereValidationError("record derivation head.kwargs must be non-empty object")

    entities = store.schema_ir.get("entities", [])
    if not isinstance(entities, list):
        raise WhereValidationError("schema_ir.entities must be list")
    record_entity = None
    for entity in entities:
        if isinstance(entity, dict) and entity.get("entity_type") == record_type:
            record_entity = entity
            break
    if not isinstance(record_entity, dict) or record_entity.get("is_record") is not True:
        raise WhereValidationError(f"record entity not found or not marked is_record: {record_type}")

    predicates = store.schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise WhereValidationError("schema_ir.predicates must be list")
    record_exists_pred_id: str | None = None
    role_defs: list[dict[str, Any]] = []
    for pred in predicates:
        if not isinstance(pred, dict):
            continue
        if pred.get("owner_type") != record_type:
            continue
        pred_id = pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if pred.get("is_record_exists") is True:
            record_exists_pred_id = pred_id
            continue
        arg_specs = pred.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise WhereValidationError(f"record role predicate must be arity 2: {pred_id}")
        if not isinstance(arg_specs[0], dict) or arg_specs[0].get("type_domain") != "entity_ref":
            raise WhereValidationError(f"record role predicate arg0 must be entity_ref: {pred_id}")
        if not isinstance(arg_specs[1], dict):
            raise WhereValidationError(f"record role predicate arg1 spec invalid: {pred_id}")
        tag = arg_specs[1].get("type_domain")
        if tag not in CANONICAL_TAGS:
            raise WhereValidationError(f"record role predicate arg1 type_domain invalid: {pred_id}")
        field_name = pred.get("py_field_name")
        if not isinstance(field_name, str) or not field_name:
            field_name = pred_id.split(":", 1)[1] if ":" in pred_id else pred_id
        role_defs.append({"field_name": field_name, "pred_id": pred_id, "type_domain": tag})
    if not isinstance(record_exists_pred_id, str) or not record_exists_pred_id:
        raise WhereValidationError(f"record exists predicate not found for: {record_type}")
    if not role_defs:
        raise WhereValidationError(f"record role predicates not found for: {record_type}")

    role_names = [role["field_name"] for role in role_defs]
    missing = [name for name in role_names if name not in kwargs]
    if missing:
        raise WhereValidationError(f"record head missing role kwargs: {missing}")
    extra = sorted([key for key in kwargs.keys() if key not in set(role_names)])
    if extra:
        raise WhereValidationError(f"record head contains unknown role kwargs: {extra}")

    head_vars = [kwargs[name] for name in role_names]
    return {
        "record_type": record_type,
        "record_exists_pred_id": record_exists_pred_id,
        "roles": role_defs,
        "head_vars": head_vars,
        "id_policy": id_policy,
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
