"""Strict, detached Scenario component codec for the C2 sealed protocol.

The older ``scenario_v1`` DTOs remain the runtime model.  This module is the
wire boundary: it deliberately validates hostile JSON before constructing
those DTOs, in particular because the legacy ``EntityRef`` validator accepts
more JSON than a sealed invocation may contain.
"""

from __future__ import annotations

import json

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError
from .scenario_v1 import (
    ExactLocalClosureTargetV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioOperationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
)
from .schema_runtime import EntityRef, FieldPath

MAX_COMPONENT_BYTES = 4 * 1024 * 1024
MAX_OPERATIONS = 256
MAX_IDENTITY_DEPTH = 8
MAX_IDENTITY_NODES = 256
MAX_CONTAINER_ITEMS = 64
MAX_IDENTITY_STRING_BYTES = 4096
MAX_IDENTITY_BYTES = 16384
MAX_JSON_DEPTH = 64
_IDENTITY_DIGEST_DOMAIN = "factgraph.sealed-evaluation-entity-identity.v1"
_ENTITY_DIGEST_DOMAIN = "factgraph.sealed-evaluation-entity-ref.v1"


def _fail(message: str) -> ProtocolShapeError:
    return ProtocolShapeError(message)


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise _fail("duplicate JSON key")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise _fail(f"non-finite JSON constant {value}")


def _float(value: str) -> object:
    raise _fail(f"raw JSON float {value} is forbidden")


def _depth(value: object) -> int:
    if type(value) is dict:
        return 1 + max((_depth(item) for item in value.values()), default=0)
    if type(value) is list:
        return 1 + max((_depth(item) for item in value), default=0)
    return 0


def _plain(value: object, label: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        raise _fail(f"{label} contains raw float")
    if type(value) is list:
        for index, item in enumerate(value):
            _plain(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise _fail(f"{label} contains non-string key")
            _plain(item, f"{label}[{key!r}]")
        return
    raise _fail(f"{label} contains unsupported rich type")


def _canonical(value: object, label: str, *, limit: int = MAX_COMPONENT_BYTES) -> bytes:
    _plain(value, label)
    if _depth(value) > MAX_JSON_DEPTH:
        raise _fail(f"{label} exceeds JSON depth")
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise _fail(f"{label} is not canonical JSON") from exc
    if not raw or len(raw) > limit:
        raise _fail(f"{label} exceeds byte bound")
    return raw


def _load(raw: object, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_COMPONENT_BYTES:
        raise _fail(f"{label} requires bounded bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
        )
    except ProtocolShapeError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise _fail(f"{label} is not strict canonical JSON") from exc
    if type(value) is not dict or _canonical(value, label) != raw:
        raise _fail(f"{label} is not canonical JSON")
    return value


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise _fail(f"{label} has unknown, missing, or null fields")
    return value


def _text(
    value: object,
    label: str,
    max_bytes: int = 256,
    *,
    non_empty: bool = True,
) -> str:
    if (
        type(value) is not str
        or (non_empty and not value)
        or any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F for c in value)
    ):
        raise _fail(f"{label} must be control-free Unicode text")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise _fail(f"{label} contains invalid Unicode scalar") from exc
    if size > max_bytes:
        raise _fail(f"{label} exceeds UTF-8 byte bound")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or len(value) != 71 or not value.startswith("sha256:"):
        raise _fail(f"{label} must be sha256 token")
    if any(c not in "0123456789abcdef" for c in value[7:]):
        raise _fail(f"{label} must be lowercase sha256 token")
    return value


def _domain_token(domain: str, payload: object) -> str:
    return "sha256:" + sha256_hex(
        _canonical(
            {"format": domain, "payload": payload},
            f"{domain} digest payload",
            limit=MAX_COMPONENT_BYTES,
        )
    )


def _identity_value(value: object, *, depth: int, counter: list[int], label: str) -> object:
    if depth > MAX_IDENTITY_DEPTH:
        raise _fail(f"{label} exceeds identity depth")
    counter[0] += 1
    if counter[0] > MAX_IDENTITY_NODES:
        raise _fail("identity exceeds node bound")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -(2**63) <= value <= 2**63 - 1:
            raise _fail(f"{label} integer outside signed 64-bit range")
        return value
    if type(value) is float:
        raise _fail(f"{label} raw float is forbidden")
    if type(value) is str:
        return _text(value, label, MAX_IDENTITY_STRING_BYTES, non_empty=False)
    if type(value) is list:
        if len(value) > MAX_CONTAINER_ITEMS:
            raise _fail(f"{label} exceeds item bound")
        return [
            _identity_value(item, depth=depth + 1, counter=counter, label=f"{label}[]")
            for item in value
        ]
    if type(value) is dict:
        if len(value) > MAX_CONTAINER_ITEMS:
            raise _fail(f"{label} exceeds member bound")
        out: dict[str, object] = {}
        for key, item in value.items():
            _text(key, f"{label}.key", 256)
            out[key] = _identity_value(
                item, depth=depth + 1, counter=counter, label=f"{label}[{key!r}]"
            )
        return out
    raise _fail(f"{label} contains unsupported rich type")


def _entity_wire(entity: EntityRef) -> dict[str, object]:
    if type(entity) is not EntityRef or entity.encoded_ref is not None:
        raise _fail("EntityRef must be exact and must not carry encoded_ref")
    entity_type = _text(entity.entity_type, "entity_type")
    identity = _identity_value(entity.identity, depth=1, counter=[0], label="identity")
    if type(identity) is not dict or not identity:
        raise _fail("identity must be non-empty object")
    _canonical(identity, "identity", limit=MAX_IDENTITY_BYTES)
    identity_digest = _domain_token(_IDENTITY_DIGEST_DOMAIN, identity)
    entity_digest = _domain_token(
        _ENTITY_DIGEST_DOMAIN,
        {"entity_type": entity_type, "identity_digest": identity_digest},
    )
    return {
        "entity_type": entity_type,
        "identity": identity,
        "identity_digest": identity_digest,
        "entity_digest": entity_digest,
    }


def _entity_from(value: object) -> EntityRef:
    row = _exact(
        value, {"entity_type", "identity", "identity_digest", "entity_digest"}, "EntityRef"
    )
    entity_type = _text(row["entity_type"], "entity_type")
    identity = _identity_value(row["identity"], depth=1, counter=[0], label="identity")
    if type(identity) is not dict or not identity:
        raise _fail("identity must be non-empty object")
    _canonical(identity, "identity", limit=MAX_IDENTITY_BYTES)
    identity_digest = _domain_token(_IDENTITY_DIGEST_DOMAIN, identity)
    if row["identity_digest"] != identity_digest:
        raise _fail("identity digest mismatch")
    entity_digest = _domain_token(
        _ENTITY_DIGEST_DOMAIN,
        {"entity_type": entity_type, "identity_digest": identity_digest},
    )
    if row["entity_digest"] != entity_digest:
        raise _fail("entity digest mismatch")
    return EntityRef(entity_type, identity, encoded_ref=None)


def _value_wire(value: ScenarioValueV1) -> dict[str, object]:
    if type(value) is not ScenarioValueV1:
        raise _fail("exact ScenarioValueV1 required")
    ScenarioValueV1.__post_init__(value)
    return {
        "tag": value.tag,
        "value": value.value,
        "value_digest": value.value_digest,
    }


def _value_from(value: object) -> ScenarioValueV1:
    row = _exact(value, {"tag", "value", "value_digest"}, "ScenarioValueV1")
    if type(row["tag"]) is not str:
        raise _fail("ScenarioValueV1 tag must be string")
    try:
        result = ScenarioValueV1(row["tag"], row["value"])
    except (ProtocolShapeError, TypeError, ValueError) as exc:
        raise _fail("ScenarioValueV1 is malformed") from exc
    if row["value_digest"] != result.value_digest:
        raise _fail("ScenarioValueV1 value_digest mismatch")
    return result


def _field_wire(field: FieldPath) -> dict[str, object]:
    if type(field) is not FieldPath:
        raise _fail("exact FieldPath required")
    FieldPath.__post_init__(field)
    return {
        "entity_type": _text(field.entity_type, "field.entity_type"),
        "field_name": _text(field.field_name, "field.field_name"),
    }


def _field_from(value: object) -> FieldPath:
    row = _exact(value, {"entity_type", "field_name"}, "FieldPath")
    try:
        return FieldPath(
            _text(row["entity_type"], "field.entity_type"),
            _text(row["field_name"], "field.field_name"),
        )
    except (ProtocolShapeError, TypeError, ValueError) as exc:
        raise _fail("FieldPath is malformed") from exc


def _refs(values: tuple[str, ...], label: str) -> list[str]:
    if type(values) is not tuple:
        raise _fail(f"{label} must be tuple[str,...]")
    result = [_text(value, f"{label}[]") for value in values]
    if result != sorted(set(result)):
        raise _fail(f"{label} must be sorted and unique")
    return result


def _refs_from(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise _fail(f"{label} must be string array")
    result = tuple(_text(item, f"{label}[]") for item in value)
    if list(result) != sorted(set(result)):
        raise _fail(f"{label} must be sorted and unique")
    return result


def _fresh_entity(value: object) -> EntityRef:
    if type(value) is not EntityRef:
        raise _fail("exact EntityRef required")
    return _entity_from(_entity_wire(value))


def _fresh_field(value: object) -> FieldPath:
    if type(value) is not FieldPath:
        raise _fail("exact FieldPath required")
    return _field_from(_field_wire(value))


def _fresh_value(value: object) -> ScenarioValueV1:
    if type(value) is not ScenarioValueV1:
        raise _fail("exact ScenarioValueV1 required")
    try:
        return ScenarioValueV1(value.tag, value.value)
    except (ProtocolShapeError, TypeError, ValueError) as exc:
        raise _fail("ScenarioValueV1 is malformed") from exc


def _fresh_operation(op: ScenarioOperationV1) -> ScenarioOperationV1:
    """Rebuild a Scenario operation without trusting frozen cached state."""
    try:
        if type(op) is ScenarioSetEffectiveValueV1:
            fresh: ScenarioOperationV1 = ScenarioSetEffectiveValueV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                field=_fresh_field(op.field),
                value=_fresh_value(op.value),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioEnsureMemberV1:
            fresh = ScenarioEnsureMemberV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                field=_fresh_field(op.field),
                value=_fresh_value(op.value),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioSetExactMembersV1:
            if type(op.values) is not tuple:
                raise _fail("values must be tuple[ScenarioValueV1,...]")
            fresh = ScenarioSetExactMembersV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                field=_fresh_field(op.field),
                values=tuple(_fresh_value(item) for item in op.values),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioWithoutFieldV1:
            fresh = ScenarioWithoutFieldV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                field=_fresh_field(op.field),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioWithoutValueV1:
            fresh = ScenarioWithoutValueV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                field=_fresh_field(op.field),
                value=_fresh_value(op.value),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioCreateEphemeralEntityV1:
            fresh = ScenarioCreateEphemeralEntityV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioEnsureRelationV1:
            if type(op.values) is not tuple:
                raise _fail("values must be tuple[ScenarioValueV1,...]")
            fresh = ScenarioEnsureRelationV1(
                premise_id=_text(op.premise_id, "premise_id"),
                predicate_id=_text(op.predicate_id, "predicate_id"),
                values=tuple(_fresh_value(item) for item in op.values),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioWithoutRelationV1:
            fresh = ScenarioWithoutRelationV1(
                premise_id=_text(op.premise_id, "premise_id"),
                predicate_id=_text(op.predicate_id, "predicate_id"),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioWithoutEntityV1:
            fresh = ScenarioWithoutEntityV1(
                premise_id=_text(op.premise_id, "premise_id"),
                entity=_fresh_entity(op.entity),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        elif type(op) is ScenarioWithoutAssertionV1:
            fresh = ScenarioWithoutAssertionV1(
                premise_id=_text(op.premise_id, "premise_id"),
                assertion_id=_text(op.assertion_id, "assertion_id"),
                origin_refs=tuple(_refs(op.origin_refs, "origin_refs")),
            )
        else:
            raise _fail("exact Scenario operation required")
    except ProtocolShapeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise _fail("Scenario operation is malformed") from exc
    if fresh.statement_digest != op.statement_digest:
        raise _fail("Scenario operation statement_digest is stale")
    return fresh


def _op_wire(op: ScenarioOperationV1) -> dict[str, object]:
    op = _fresh_operation(op)
    row: dict[str, object] = {
        "$type": "FactGraphScenarioOperationV1",
        "kind": _kind(op),
        "premise_id": op.premise_id,
        "origin_refs": _refs(op.origin_refs, "origin_refs"),
        "statement_digest": op.statement_digest,
    }
    if type(op) in {
        ScenarioSetEffectiveValueV1,
        ScenarioEnsureMemberV1,
        ScenarioSetExactMembersV1,
        ScenarioWithoutFieldV1,
        ScenarioWithoutValueV1,
    }:
        row.update({"entity": _entity_wire(op.entity), "field": _field_wire(op.field)})
    if type(op) in {
        ScenarioSetEffectiveValueV1,
        ScenarioEnsureMemberV1,
        ScenarioWithoutValueV1,
    }:
        row["value"] = _value_wire(op.value)
    if type(op) is ScenarioSetExactMembersV1:
        row["values"] = [_value_wire(v) for v in op.values]
    if type(op) is ScenarioEnsureRelationV1:
        row.update({"predicate_id": op.predicate_id, "values": [_value_wire(v) for v in op.values]})
    elif type(op) is ScenarioWithoutRelationV1:
        row["predicate_id"] = op.predicate_id
    elif type(op) in {ScenarioWithoutEntityV1, ScenarioCreateEphemeralEntityV1}:
        row["entity"] = _entity_wire(op.entity)
    elif type(op) is ScenarioWithoutAssertionV1:
        row["assertion_id"] = op.assertion_id
    return row


def _kind(op: ScenarioOperationV1) -> str:
    return {
        ScenarioSetEffectiveValueV1: "set_effective_value",
        ScenarioEnsureMemberV1: "ensure_member",
        ScenarioSetExactMembersV1: "set_exact_members",
        ScenarioWithoutFieldV1: "without_field",
        ScenarioWithoutValueV1: "without_value",
        ScenarioCreateEphemeralEntityV1: "create_ephemeral_entity",
        ScenarioEnsureRelationV1: "ensure_relation",
        ScenarioWithoutRelationV1: "without_relation",
        ScenarioWithoutEntityV1: "without_entity",
        ScenarioWithoutAssertionV1: "without_assertion",
    }[type(op)]


def _op_from(value: object) -> ScenarioOperationV1:
    if type(value) is not dict:
        raise _fail("Scenario operation must be exact object")
    row = value
    kind = _text(row.get("kind"), "operation.kind")
    common = {"$type", "kind", "premise_id", "origin_refs", "statement_digest"}
    premise = _text(row.get("premise_id"), "operation.premise_id")
    origin = _refs_from(row.get("origin_refs"), "operation.origin_refs")

    def base(extra: set[str]) -> dict[str, object]:
        data = _exact(row, common | extra, f"operation {kind}")
        if data["$type"] != "FactGraphScenarioOperationV1":
            raise _fail("operation type mismatch")
        _digest(data["statement_digest"], "operation.statement_digest")
        return data

    try:
        if kind == "set_effective_value":
            data = base({"entity", "field", "value"})
            op: ScenarioOperationV1 = ScenarioSetEffectiveValueV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                field=_field_from(data["field"]),
                value=_value_from(data["value"]),
                origin_refs=origin,
            )
        elif kind == "ensure_member":
            data = base({"entity", "field", "value"})
            op = ScenarioEnsureMemberV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                field=_field_from(data["field"]),
                value=_value_from(data["value"]),
                origin_refs=origin,
            )
        elif kind == "set_exact_members":
            data = base({"entity", "field", "values"})
            if type(data["values"]) is not list:
                raise _fail("operation.values must be array")
            op = ScenarioSetExactMembersV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                field=_field_from(data["field"]),
                values=tuple(_value_from(item) for item in data["values"]),
                origin_refs=origin,
            )
        elif kind == "without_field":
            data = base({"entity", "field"})
            op = ScenarioWithoutFieldV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                field=_field_from(data["field"]),
                origin_refs=origin,
            )
        elif kind == "without_value":
            data = base({"entity", "field", "value"})
            op = ScenarioWithoutValueV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                field=_field_from(data["field"]),
                value=_value_from(data["value"]),
                origin_refs=origin,
            )
        elif kind == "create_ephemeral_entity":
            data = base({"entity"})
            op = ScenarioCreateEphemeralEntityV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                origin_refs=origin,
            )
        elif kind == "ensure_relation":
            data = base({"predicate_id", "values"})
            if type(data["values"]) is not list:
                raise _fail("operation.values must be array")
            op = ScenarioEnsureRelationV1(
                premise_id=premise,
                predicate_id=_text(data["predicate_id"], "operation.predicate_id"),
                values=tuple(_value_from(item) for item in data["values"]),
                origin_refs=origin,
            )
        elif kind == "without_relation":
            data = base({"predicate_id"})
            op = ScenarioWithoutRelationV1(
                premise_id=premise,
                predicate_id=_text(data["predicate_id"], "operation.predicate_id"),
                origin_refs=origin,
            )
        elif kind == "without_entity":
            data = base({"entity"})
            op = ScenarioWithoutEntityV1(
                premise_id=premise,
                entity=_entity_from(data["entity"]),
                origin_refs=origin,
            )
        elif kind == "without_assertion":
            data = base({"assertion_id"})
            op = ScenarioWithoutAssertionV1(
                premise_id=premise,
                assertion_id=_text(data["assertion_id"], "operation.assertion_id"),
                origin_refs=origin,
            )
        else:
            raise _fail("unsupported operation kind")
    except ProtocolShapeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise _fail("Scenario operation is malformed") from exc
    if data["statement_digest"] != op.statement_digest:
        raise _fail("statement digest mismatch")
    if _op_wire(op) != row:
        raise _fail("Scenario operation is not canonical")
    return op


def _target_wire(target: ExactLocalClosureTargetV1) -> dict[str, object]:
    if type(target) is not ExactLocalClosureTargetV1 or type(target.members) is not tuple:
        raise _fail("exact closure target required")
    try:
        fresh = ExactLocalClosureTargetV1(
            kind=target.kind,
            entity_ref=None
            if target.entity_ref is None
            else _text(target.entity_ref, "closure_target.entity_ref"),
            predicate_id=None
            if target.predicate_id is None
            else _text(target.predicate_id, "closure_target.predicate_id"),
            value=None if target.value is None else _fresh_value(target.value),
            assertion_id=None
            if target.assertion_id is None
            else _text(target.assertion_id, "closure_target.assertion_id"),
            members=tuple(_fresh_value(item) for item in target.members),
        )
    except ProtocolShapeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise _fail("closure target is malformed") from exc
    if fresh.target_digest != target.target_digest:
        raise _fail("closure target digest is stale")
    return {
        "kind": fresh.kind,
        "entity_ref": fresh.entity_ref,
        "predicate_id": fresh.predicate_id,
        "value": None if fresh.value is None else _value_wire(fresh.value),
        "assertion_id": fresh.assertion_id,
        "members": [_value_wire(value) for value in fresh.members],
        "target_digest": fresh.target_digest,
    }


def exact_local_closure_target_v1_bytes(target: ExactLocalClosureTargetV1) -> bytes:
    return _canonical(
        {"$type": "FactGraphExactLocalClosureTargetV1", **_target_wire(target)},
        "closure target",
    )


def exact_local_closure_target_v1_to_wire(target: ExactLocalClosureTargetV1) -> dict[str, object]:
    """Return a detached exact wire object (the caller must not mutate it)."""
    raw = exact_local_closure_target_v1_bytes(target)
    row = _load(raw, "closure target")
    return dict(row)


def exact_local_closure_target_v1_from_bytes(raw: bytes) -> ExactLocalClosureTargetV1:
    row = _load(raw, "closure target")
    data = _exact(
        row,
        {
            "$type",
            "kind",
            "entity_ref",
            "predicate_id",
            "value",
            "assertion_id",
            "members",
            "target_digest",
        },
        "closure target",
    )
    if data["$type"] != "FactGraphExactLocalClosureTargetV1":
        raise _fail("closure target type mismatch")
    if type(data["members"]) is not list:
        raise _fail("closure target members must be array")
    _digest(data["target_digest"], "closure_target.target_digest")
    try:
        target = ExactLocalClosureTargetV1(
            kind=_text(data["kind"], "closure_target.kind"),
            entity_ref=None
            if data["entity_ref"] is None
            else _text(data["entity_ref"], "closure_target.entity_ref"),
            predicate_id=None
            if data["predicate_id"] is None
            else _text(data["predicate_id"], "closure_target.predicate_id"),
            value=None if data["value"] is None else _value_from(data["value"]),
            assertion_id=None
            if data["assertion_id"] is None
            else _text(data["assertion_id"], "closure_target.assertion_id"),
            members=tuple(_value_from(item) for item in data["members"]),
        )
    except ProtocolShapeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise _fail("closure target is malformed") from exc
    if data["target_digest"] != target.target_digest:
        raise _fail("closure target digest mismatch")
    if exact_local_closure_target_v1_bytes(target) != raw:
        raise _fail("closure target is not canonical")
    return target


def exact_local_closure_target_v1_from_wire(value: object) -> ExactLocalClosureTargetV1:
    """Decode one exact wire object through the canonical byte boundary."""
    if type(value) is not dict:
        raise _fail("closure target wire must be exact dict")
    return exact_local_closure_target_v1_from_bytes(_canonical(value, "closure target"))


def scenario_spec_v1_bytes(spec: ScenarioSpecV1) -> bytes:
    if type(spec) is not ScenarioSpecV1 or type(spec.operations) is not tuple:
        raise _fail("exact ScenarioSpecV1 required")
    if len(spec.operations) > MAX_OPERATIONS:
        raise _fail("ScenarioSpecV1 exceeds operation bound")
    fresh = ScenarioSpecV1(tuple(_fresh_operation(operation) for operation in spec.operations))
    if fresh.spec_digest != spec.spec_digest:
        raise _fail("ScenarioSpecV1 spec_digest is stale")
    return _canonical(
        {
            "$type": "FactGraphScenarioSpecV1",
            "operations": [_op_wire(operation) for operation in fresh.operations],
            "spec_digest": fresh.spec_digest,
        },
        "ScenarioSpecV1",
    )


def scenario_spec_v1_from_bytes(raw: bytes) -> ScenarioSpecV1:
    row = _load(raw, "ScenarioSpecV1")
    data = _exact(row, {"$type", "operations", "spec_digest"}, "ScenarioSpecV1")
    if data["$type"] != "FactGraphScenarioSpecV1":
        raise _fail("ScenarioSpecV1 type mismatch")
    if type(data["operations"]) is not list or len(data["operations"]) > MAX_OPERATIONS:
        raise _fail("ScenarioSpecV1 operations are malformed")
    _digest(data["spec_digest"], "ScenarioSpecV1.spec_digest")
    try:
        spec = ScenarioSpecV1(tuple(_op_from(item) for item in data["operations"]))
    except ProtocolShapeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise _fail("ScenarioSpecV1 is malformed") from exc
    if data["spec_digest"] != spec.spec_digest:
        raise _fail("ScenarioSpecV1 digest mismatch")
    if scenario_spec_v1_bytes(spec) != raw:
        raise _fail("ScenarioSpecV1 is not canonical")
    return spec


__all__ = [
    "exact_local_closure_target_v1_bytes",
    "exact_local_closure_target_v1_from_bytes",
    "exact_local_closure_target_v1_from_wire",
    "exact_local_closure_target_v1_to_wire",
    "scenario_spec_v1_bytes",
    "scenario_spec_v1_from_bytes",
]
