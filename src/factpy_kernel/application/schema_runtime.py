from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.schema.schema_ir import ensure_schema_ir, schema_digest

from .protocol import EntityRef, EntitySelector, ErrorDTO


@dataclass(frozen=True)
class IdentityFieldInfo:
    name: str
    type_domain: str
    has_default: bool = False
    default_value: Any = None
    default_factory: str | None = None
    primary_key: bool = False


@dataclass(frozen=True)
class PredicateInfo:
    pred_id: str
    owner_type: str
    py_field_name: str | None
    cardinality: str
    value_type_domain: str | None
    is_entity_exists: bool = False
    is_identity_field: bool = False


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


@dataclass(frozen=True)
class SchemaIndex:
    schema_ir: dict[str, Any]
    schema_digest: str
    entities: dict[str, EntityTypeInfo]
    field_predicates: dict[tuple[str, str], PredicateInfo]
    predicates_by_id: dict[str, PredicateInfo]


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
                    has_default="default" in row,
                    default_value=row.get("default"),
                    default_factory=row.get("default_factory") if isinstance(row.get("default_factory"), str) else None,
                    primary_key=bool(row.get("primary_key", False)),
                )
            )
        entity_infos[entity_type] = EntityTypeInfo(
            entity_type=entity_type,
            identity_fields=tuple(identity_fields),
            exists_predicate_id="",
            identity_predicates={},
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
        )

    return SchemaIndex(
        schema_ir=validated,
        schema_digest=schema_digest(validated),
        entities=normalized_entities,
        field_predicates=field_predicates,
        predicates_by_id=predicates_by_id,
    )


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


def materialize_identity(
    entity_type: str,
    partial_identity: dict[str, Any],
    *,
    index: SchemaIndex,
    allow_identity_defaults: bool = False,
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
    missing_defaulted: list[str] = []
    for field in info.identity_fields:
        if field.name in partial_identity:
            materialized[field.name] = _normalize_identity_value(
                field.type_domain,
                partial_identity[field.name],
                entity_type=entity_type,
                field_name=field.name,
            )
            continue
        if field.has_default:
            if not allow_identity_defaults:
                missing_defaulted.append(field.name)
                continue
            materialized[field.name] = _normalize_identity_value(
                field.type_domain,
                field.default_value,
                entity_type=entity_type,
                field_name=field.name,
            )
            continue
        if field.default_factory is not None:
            if not allow_identity_defaults:
                missing_defaulted.append(field.name)
                continue
            materialized[field.name] = _materialize_default_factory(
                field.default_factory,
                type_domain=field.type_domain,
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
    if missing_defaulted:
        raise SchemaResolutionError(
            f"identity requires defaults for {entity_type}, but allow_identity_defaults is False: {missing_defaulted}",
            code="IDENTITY_DEFAULTS_NOT_ALLOWED",
            path=("identity",),
            details={"entity_type": entity_type, "defaulted_fields": missing_defaulted},
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
        allow_identity_defaults=selector.allow_identity_defaults,
    )
    ref = EntityRef(entity_type=selector.entity_type, identity=identity)
    encoded = encode_entity_ref(ref, index=index)
    return EntityRef(entity_type=ref.entity_type, identity=ref.identity, encoded_ref=encoded)


def _materialize_default_factory(
    default_factory: str,
    *,
    type_domain: str,
    entity_type: str,
    field_name: str,
) -> str:
    if default_factory != "uuid4":
        raise SchemaResolutionError(
            f"unsupported default_factory for {entity_type}.{field_name}: {default_factory}",
            code="UNSUPPORTED_DEFAULT_FACTORY",
            path=("identity", field_name),
            details={"default_factory": default_factory, "type_domain": type_domain},
        )
    if type_domain == "uuid":
        return str(uuid4()).lower()
    if type_domain == "string":
        return uuid4().hex
    raise SchemaResolutionError(
        f"default_factory='uuid4' is not supported for {entity_type}.{field_name} type_domain={type_domain}",
        code="UNSUPPORTED_DEFAULT_FACTORY_DOMAIN",
        path=("identity", field_name),
        details={"default_factory": default_factory, "type_domain": type_domain},
    )


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
    "field_predicate",
    "field_value_type",
    "materialize_identity",
    "resolve_selector",
]
