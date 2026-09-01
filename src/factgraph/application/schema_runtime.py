from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any, Literal

from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.protocol.tup_v1 import display_float64_value
from factgraph.core.schema.schema_ir import ensure_schema_ir, schema_digest

from .protocol import EntityRef, EntitySelector, ErrorDTO

_REPR_PLACEHOLDER_RE = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class IdentityFieldInfo:
    name: str
    type_domain: str


@dataclass(frozen=True)
class PredicateInfo:
    pred_id: str
    owner_type: str
    py_field_name: str | None
    cardinality: str
    value_type_domain: str | None
    is_entity_exists: bool = False
    is_identity_field: bool = False
    enum_values: tuple[Any, ...] | None = None
    pattern: str | None = None
    repr: str | None = None


@dataclass(frozen=True)
class FieldTypeInfo:
    value_kind: Literal["scalar", "entity_ref"]
    cardinality: Literal["single", "multi"]
    scalar_domain: str | None = None
    ref_target_type: str | None = None


@dataclass(frozen=True)
class EntityTypeInfo:
    entity_type: str
    identity_fields: tuple[IdentityFieldInfo, ...]
    exists_predicate_id: str
    identity_predicates: dict[str, PredicateInfo]
    meta_repr: str | None = None


@dataclass(frozen=True)
class SchemaIndex:
    schema_ir: dict[str, Any]
    schema_digest: str
    entities: dict[str, EntityTypeInfo]
    field_predicates: dict[tuple[str, str], PredicateInfo]
    predicates_by_id: dict[str, PredicateInfo]
    identity_pred_ids: frozenset[str]
    """Identity Claim pred_ids — INV-7c protected per ADR-IC §4.3.1."""
    exists_pred_ids: frozenset[str]
    """<EntityType>:exists Claim pred_ids — existence-claim transitional guard per ADR-IC §4.4.2.

    NOT part of INV-7c (per ADR-IC §4.4.2: :exists is not in idref_v1 hash
    inputs and is not part of Identity bundle); guard lifecycle is tied to
    :exists co-emission and may retire when Step 2+ removes :exists per
    ADR-IC §4.4.4 forward-pointer.
    """

    @property
    def protected_anchor_pred_ids(self) -> frozenset[str]:
        """Union of identity_pred_ids and exists_pred_ids.

        Read-only helper for callers that need a single membership check.
        Per ADR-IC §4.3.1 SF9: two independent frozensets are the storage
        of truth; this property is a derived view, NOT a single set.
        """
        return self.identity_pred_ids | self.exists_pred_ids


class SchemaResolutionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def build_schema_index(schema_ir: dict[str, Any]) -> SchemaIndex:
    validated = ensure_schema_ir(schema_ir)
    entity_infos: dict[str, EntityTypeInfo] = {}

    for entity in validated["entities"]:
        entity_type = entity["entity_type"]
        if entity_type in entity_infos:
            raise SchemaResolutionError(
                f"duplicate entity_type in schema_ir: {entity_type}",
                code="DUPLICATE_ENTITY_TYPE",
                path=("entities", entity_type),
            )
        identity_fields: list[IdentityFieldInfo] = []
        for row in entity["identity_fields"]:
            identity_fields.append(
                IdentityFieldInfo(
                    name=str(row["name"]),
                    type_domain=str(row["type_domain"]),
                )
            )
        entity_infos[entity_type] = EntityTypeInfo(
            entity_type=entity_type,
            identity_fields=tuple(identity_fields),
            exists_predicate_id="",
            identity_predicates={},
            meta_repr=entity.get("repr") if isinstance(entity.get("repr"), str) else None,
        )

    predicates_by_id: dict[str, PredicateInfo] = {}
    field_predicates: dict[tuple[str, str], PredicateInfo] = {}
    exists_by_entity: dict[str, str] = {}
    identity_predicates_by_entity: dict[str, dict[str, PredicateInfo]] = {name: {} for name in entity_infos}

    for pred in validated["predicates"]:
        pred_id = str(pred["pred_id"])
        if pred_id in predicates_by_id:
            raise SchemaResolutionError(
                f"duplicate pred_id in schema_ir: {pred_id}",
                code="DUPLICATE_PREDICATE_ID",
                path=("predicates", pred_id),
            )
        owner_type = pred.get("owner_type")
        if not isinstance(owner_type, str) or not owner_type:
            raise SchemaResolutionError(
                f"predicate {pred_id} is missing owner_type",
                code="INVALID_PREDICATE_OWNER",
                path=("predicates", pred_id, "owner_type"),
            )
        arg_specs = pred.get("arg_specs")
        value_type_domain = None
        if isinstance(arg_specs, list) and len(arg_specs) >= 2 and isinstance(arg_specs[1], dict):
            domain = arg_specs[1].get("type_domain")
            if isinstance(domain, str) and domain:
                value_type_domain = domain
        cardinality = pred.get("cardinality")
        if cardinality not in {"single", "multi"}:
            raise SchemaResolutionError(
                f"predicate {pred_id} has invalid cardinality: {cardinality!r}",
                code="INVALID_PREDICATE_CARDINALITY",
                path=("predicates", pred_id, "cardinality"),
            )
        info = PredicateInfo(
            pred_id=pred_id,
            owner_type=owner_type,
            py_field_name=pred.get("py_field_name") if isinstance(pred.get("py_field_name"), str) else None,
            cardinality=cardinality,
            value_type_domain=value_type_domain,
            is_entity_exists=bool(pred.get("is_entity_exists", False)),
            is_identity_field=bool(pred.get("is_identity_field", False)),
            enum_values=tuple(pred["enum_values"]) if isinstance(pred.get("enum_values"), list) else None,
            pattern=pred.get("pattern") if isinstance(pred.get("pattern"), str) else None,
            repr=pred.get("repr") if isinstance(pred.get("repr"), str) else None,
        )
        if not info.is_entity_exists and info.py_field_name is not None and info.value_type_domain is None:
            raise SchemaResolutionError(
                f"predicate {pred_id} is missing value type_domain",
                code="INVALID_PREDICATE_VALUE_DOMAIN",
                path=("predicates", pred_id, "arg_specs"),
            )
        predicates_by_id[pred_id] = info
        if info.py_field_name is not None:
            key = (owner_type, info.py_field_name)
            if key in field_predicates:
                raise SchemaResolutionError(
                    f"duplicate field predicate for {owner_type}.{info.py_field_name}",
                    code="DUPLICATE_FIELD_PREDICATE",
                    path=("predicates", pred_id),
                )
            field_predicates[key] = info
        if info.is_entity_exists:
            if owner_type in exists_by_entity:
                raise SchemaResolutionError(
                    f"multiple exists predicates for {owner_type}",
                    code="DUPLICATE_EXISTS_PREDICATE",
                    path=("predicates", pred_id),
                )
            exists_by_entity[owner_type] = pred_id
        if info.is_identity_field and info.py_field_name is not None:
            bucket = identity_predicates_by_entity.setdefault(owner_type, {})
            if info.py_field_name in bucket:
                raise SchemaResolutionError(
                    f"multiple identity predicates for {owner_type}.{info.py_field_name}",
                    code="DUPLICATE_IDENTITY_PREDICATE",
                    path=("predicates", pred_id),
                )
            bucket[info.py_field_name] = info

    normalized_entities: dict[str, EntityTypeInfo] = {}
    for entity_type, info in entity_infos.items():
        exists_predicate_id = exists_by_entity.get(entity_type)
        if not isinstance(exists_predicate_id, str) or not exists_predicate_id:
            raise SchemaResolutionError(
                f"missing exists predicate for {entity_type}",
                code="MISSING_EXISTS_PREDICATE",
                path=("entities", entity_type),
            )
        identity_predicates = dict(identity_predicates_by_entity.get(entity_type, {}))
        missing_identity_preds = [
            field.name for field in info.identity_fields if field.name not in identity_predicates
        ]
        if missing_identity_preds:
            raise SchemaResolutionError(
                f"missing identity predicates for {entity_type}: {missing_identity_preds}",
                code="MISSING_IDENTITY_PREDICATE",
                path=("entities", entity_type, "identity_fields"),
                details={"missing_identity_fields": missing_identity_preds},
            )
        normalized_entities[entity_type] = EntityTypeInfo(
            entity_type=info.entity_type,
            identity_fields=info.identity_fields,
            exists_predicate_id=exists_predicate_id,
            identity_predicates=identity_predicates,
            meta_repr=info.meta_repr,
        )

    # Per ADR-IC §4.3.1 + Slice 2 SF1/SF9:
    # Build the two independent frozensets from PredicateInfo flags.
    # Single pass over predicates_by_id values keeps build cost low.
    identity_pred_ids = frozenset(
        info.pred_id for info in predicates_by_id.values() if info.is_identity_field
    )
    exists_pred_ids = frozenset(
        info.pred_id for info in predicates_by_id.values() if info.is_entity_exists
    )

    return SchemaIndex(
        schema_ir=validated,
        schema_digest=schema_digest(validated),
        entities=normalized_entities,
        field_predicates=field_predicates,
        predicates_by_id=predicates_by_id,
        identity_pred_ids=identity_pred_ids,
        exists_pred_ids=exists_pred_ids,
    )


def render_entity_repr(index: SchemaIndex, entity_type: str, identity_values: Mapping[str, Any]) -> str:
    """Render the display label for an entity identity bundle.

    `Entity.Meta.repr` templates may reference `%CLS` and identity placeholders
    such as `%user_id`. Without a template, the fallback label is
    `"<EntityCls> <first identity value>"`.
    """

    if not isinstance(identity_values, Mapping):
        raise SchemaResolutionError(
            "identity_values must be a mapping",
            code="INVALID_ENTITY_REPR_INPUT",
            path=("entities", entity_type, "repr"),
        )
    try:
        entity = index.entities[entity_type]
    except KeyError as exc:
        raise SchemaResolutionError(
            f"unknown entity_type: {entity_type}",
            code="UNKNOWN_ENTITY_TYPE",
            path=("entities", entity_type),
        ) from exc

    if entity.meta_repr is None:
        if not entity.identity_fields:
            raise SchemaResolutionError(
                f"entity_type has no identity fields: {entity_type}",
                code="INVALID_ENTITY_IDENTITY",
                path=("entities", entity_type, "identity_fields"),
            )
        field = entity.identity_fields[0]
        return f"{entity_type} {_identity_value_text(identity_values, entity_type=entity_type, field_name=field.name, type_domain=field.type_domain)}"

    placeholder_values = {
        "%CLS": entity_type,
        **{
            f"%{field.name}": _identity_value_text(
                identity_values,
                entity_type=entity_type,
                field_name=field.name,
                type_domain=field.type_domain,
            )
            for field in entity.identity_fields
        },
    }

    def replace_placeholder(match: re.Match[str]) -> str:
        token = match.group(0)
        return placeholder_values.get(token, token)

    return _REPR_PLACEHOLDER_RE.sub(replace_placeholder, entity.meta_repr)


def display_value(
    index: SchemaIndex | None,
    value: Any,
    *,
    entity_identity_resolver: object | None = None,
) -> Any:
    """Return the presentation value for schema-aware bindings.

    Entity refs are rendered through ``render_entity_repr`` when their identity
    can be recovered. Non-entity values are returned unchanged so digest and
    evaluation surfaces never depend on this display helper.
    """

    if index is None:
        return value
    if isinstance(value, EntityRef):
        try:
            return render_entity_repr(index, value.entity_type, value.identity)
        except Exception:
            return value.encoded_ref or value
    if isinstance(value, Mapping):
        identity = value.get("identity")
        entity_type = value.get("entity_type")
        if isinstance(entity_type, str) and isinstance(identity, Mapping):
            try:
                return render_entity_repr(index, entity_type, identity)
            except Exception:
                return value
    if isinstance(value, str):
        entity_type = entity_type_from_ref(value)
        if entity_type is None:
            return value
        resolver = entity_identity_resolver
        if callable(resolver):
            try:
                identity = resolver(entity_type, value, index)
                if isinstance(identity, Mapping):
                    return render_entity_repr(index, entity_type, identity)
            except Exception:
                return value
    return value


def _identity_value_text(
    identity_values: Mapping[str, Any],
    *,
    entity_type: str,
    field_name: str,
    type_domain: str,
) -> str:
    if field_name not in identity_values:
        raise SchemaResolutionError(
            f"missing identity value for {entity_type}.{field_name}",
            code="MISSING_ENTITY_IDENTITY_VALUE",
            path=("entities", entity_type, "identity_fields", field_name),
            details={"entity_type": entity_type, "field_name": field_name},
        )
    value = identity_values[field_name]
    if type_domain == "float64":
        try:
            return display_float64_value(value)
        except Exception:
            return str(value)
    return str(value)


def entity_info(index: SchemaIndex, entity_type: str) -> EntityTypeInfo:
    info = index.entities.get(entity_type)
    if info is None:
        raise SchemaResolutionError(
            f"unknown entity_type: {entity_type}",
            code="ENTITY_TYPE_NOT_FOUND",
            path=("entity_type",),
            details={"entity_type": entity_type},
        )
    return info


def field_predicate(index: SchemaIndex, entity_type: str, field_name: str) -> PredicateInfo:
    key = (entity_type, field_name)
    info = index.field_predicates.get(key)
    if info is None:
        raise SchemaResolutionError(
            f"unknown field path: {entity_type}.{field_name}",
            code="FIELD_PATH_NOT_FOUND",
            path=("field_path",),
            details={"entity_type": entity_type, "field_name": field_name},
        )
    return info


def entity_type_from_ref(e_ref: str) -> str | None:
    if not isinstance(e_ref, str) or not e_ref.startswith("idref_v1:"):
        return None
    parts = e_ref.split(":", 2)
    if len(parts) != 3:
        return None
    entity_type = parts[1]
    digest = parts[2]
    if not entity_type or not digest:
        return None
    return entity_type


def field_value_type(index: SchemaIndex, entity_type: str, field_name: str) -> FieldTypeInfo:
    pred = field_predicate(index, entity_type, field_name)
    if pred.value_type_domain == "entity_ref":
        return FieldTypeInfo(
            value_kind="entity_ref",
            cardinality=pred.cardinality,
            ref_target_type=None,
        )
    return FieldTypeInfo(
        value_kind="scalar",
        cardinality=pred.cardinality,
        scalar_domain=pred.value_type_domain,
    )


def is_scenario_relation_predicate_v1(index: SchemaIndex, predicate_id: str) -> bool:
    """Return whether one schema predicate is an admissible relation Scenario target."""

    info = index.predicates_by_id.get(predicate_id)
    record = next(
        (
            item
            for item in index.schema_ir.get("predicates", ())
            if isinstance(item, dict) and item.get("pred_id") == predicate_id
        ),
        None,
    )
    if info is None or record is None:
        return False
    return not (
        info.is_entity_exists
        or info.is_identity_field
        or (
            info.py_field_name is not None
            and info.value_type_domain != "entity_ref"
        )
        or bool(record.get("is_derived"))
        or record.get("kind") == "derived"
        or record.get("source_kind") == "derived"
        or predicate_id.startswith("**")
    )


def materialize_identity(
    entity_type: str,
    partial_identity: dict[str, Any],
    *,
    index: SchemaIndex,
) -> dict[str, Any]:
    info = entity_info(index, entity_type)
    if not isinstance(partial_identity, dict):
        raise SchemaResolutionError(
            "identity must be object",
            code="INVALID_IDENTITY",
            path=("identity",),
        )
    allowed_names = {field.name for field in info.identity_fields}
    unknown = sorted(set(partial_identity.keys()) - allowed_names)
    if unknown:
        raise SchemaResolutionError(
            f"unknown identity fields for {entity_type}: {unknown}",
            code="UNKNOWN_IDENTITY_FIELD",
            path=("identity",),
            details={"entity_type": entity_type, "unknown_fields": unknown},
        )

    materialized: dict[str, Any] = {}
    missing_required: list[str] = []
    for field in info.identity_fields:
        if field.name in partial_identity:
            materialized[field.name] = _normalize_identity_value(
                field.type_domain,
                partial_identity[field.name],
                entity_type=entity_type,
                field_name=field.name,
            )
            continue
        missing_required.append(field.name)

    if missing_required:
        raise SchemaResolutionError(
            f"identity is incomplete for {entity_type}; missing required fields: {missing_required}",
            code="IDENTITY_INCOMPLETE",
            path=("identity",),
            details={"entity_type": entity_type, "missing_fields": missing_required},
        )
    return materialized


def encode_entity_ref(ref: EntityRef, *, index: SchemaIndex) -> str:
    info = entity_info(index, ref.entity_type)
    tuples: list[tuple[str, str, Any]] = []
    for field in info.identity_fields:
        if field.name not in ref.identity:
            raise SchemaResolutionError(
                f"EntityRef identity is incomplete for {ref.entity_type}: missing {field.name}",
                code="IDENTITY_INCOMPLETE",
                path=("identity", field.name),
                details={"entity_type": ref.entity_type, "field_name": field.name},
            )
        tuples.append((field.name, field.type_domain, ref.identity[field.name]))
    return encode_idref_v1(ref.entity_type, tuples)


def resolve_selector(selector: EntitySelector, *, index: SchemaIndex) -> EntityRef:
    if not isinstance(selector, EntitySelector):
        raise SchemaResolutionError(
            "selector must be EntitySelector",
            code="INVALID_SELECTOR",
            path=("selector",),
        )
    identity = materialize_identity(
        selector.entity_type,
        selector.identity,
        index=index,
    )
    ref = EntityRef(entity_type=selector.entity_type, identity=identity)
    encoded = encode_entity_ref(ref, index=index)
    return EntityRef(entity_type=ref.entity_type, identity=ref.identity, encoded_ref=encoded)


def _normalize_identity_value(
    type_domain: str,
    value: Any,
    *,
    entity_type: str,
    field_name: str,
) -> Any:
    path = ("identity", field_name)
    if type_domain == "string":
        if not isinstance(value, str):
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects string identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value
    if type_domain == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects int identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value
    if type_domain == "bool":
        if not isinstance(value, bool):
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects bool identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value
    if type_domain == "float64":
        # The protocol is JSON-safe. Keep accepting the legacy hex-string form used by
        # existing runtime/storage paths in addition to native JSON float values.
        if isinstance(value, bool) or not isinstance(value, (float, str)):
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects float64 identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value
    if type_domain == "time":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects epoch-nanos int identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value
    if type_domain == "uuid":
        if not isinstance(value, str) or not value:
            raise SchemaResolutionError(
                f"{entity_type}.{field_name} expects uuid string identity value",
                code="IDENTITY_TYPE_MISMATCH",
                path=path,
                details={"expected_type_domain": type_domain},
            )
        return value.lower()
    if type_domain == "bytes":
        raise SchemaResolutionError(
            f"{entity_type}.{field_name} uses unsupported protocol identity domain: bytes",
            code="UNSUPPORTED_IDENTITY_DOMAIN",
            path=path,
            details={"expected_type_domain": type_domain},
        )
    if type_domain == "entity_ref":
        raise SchemaResolutionError(
            f"{entity_type}.{field_name} uses unsupported protocol identity domain: entity_ref",
            code="UNSUPPORTED_IDENTITY_DOMAIN",
            path=path,
            details={"expected_type_domain": type_domain},
        )
    raise SchemaResolutionError(
        f"{entity_type}.{field_name} uses unknown identity domain: {type_domain}",
        code="UNKNOWN_IDENTITY_DOMAIN",
        path=path,
        details={"expected_type_domain": type_domain},
    )


__all__ = [
    "EntityTypeInfo",
    "FieldTypeInfo",
    "IdentityFieldInfo",
    "PredicateInfo",
    "SchemaIndex",
    "SchemaResolutionError",
    "build_schema_index",
    "encode_entity_ref",
    "entity_info",
    "entity_type_from_ref",
    "display_value",
    "field_predicate",
    "field_value_type",
    "materialize_identity",
    "resolve_selector",
]
