"""Predicate schema and view definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Iterable, Literal, TypeAlias, get_args
import hashlib
import json
import os
from pathlib import Path
import tempfile

from diskcache import Cache

from symir.errors import SchemaError


_PREDICATE_SCHEMA_CACHE_ENV = "SYMR_PREDICATE_SCHEMA_CACHE_DIR"
_CACHE_ENV = "SYMR_CACHE_DIR"
_KEY_ROLE_ORDER = ("key", "id", "name")
_DEFAULT_KEY_NAME = "Name"
_DEFAULT_PARAM_NAME = "Param"
_SCHEMA_VERSION = 1
_ALLOWED_MERGE_POLICIES = {"max", "latest", "noisy_or", "overwrite", "keep_all"}
_ENTITY_ROLES = {"key", "id", "name", "sub_key", "obj_key"}
DatalogDatatype: TypeAlias = Literal[
    "string",
    "int",
    "float",
    "bool",
    "any",
]
_ALLOWED_DATATYPES = set(get_args(DatalogDatatype))


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _predicate_schema_cache_dir() -> Path:
    env_dir = os.environ.get(_PREDICATE_SCHEMA_CACHE_ENV) or os.environ.get(_CACHE_ENV)
    if env_dir:
        return Path(env_dir).expanduser()
    return Path(tempfile.gettempdir()) / "symir" / "predicate_schema_cache"


def _open_predicate_schema_cache() -> Cache:
    return Cache(str(_predicate_schema_cache_dir()))


def cache_predicate_schema(schema: "PredicateSchema") -> None:
    cache = _open_predicate_schema_cache()
    try:
        cache.set(schema.schema_id, schema.to_dict())
    finally:
        cache.close()


def load_predicate_schemas_from_cache() -> list["PredicateSchema"]:
    cache = _open_predicate_schema_cache()
    try:
        if hasattr(cache, "values"):
            items = list(cache.values())
        else:
            items = [cache[key] for key in cache]
    finally:
        cache.close()
    loaded: list[PredicateSchema] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            loaded.append(PredicateSchema.from_dict(item))
        except SchemaError:
            continue
    return loaded


def _normalize_datatype(datatype: object) -> str:
    if not isinstance(datatype, str) or not datatype.strip():
        raise SchemaError("Argument datatype must be a non-empty string.")
    normalized = datatype.strip()
    if normalized not in _ALLOWED_DATATYPES:
        raise SchemaError(
            f"Unsupported datatype '{normalized}'. Allowed: {sorted(_ALLOWED_DATATYPES)}."
        )
    return normalized


def _normalize_name(name: object, *, label: str) -> Optional[str]:
    if name is None:
        return None
    if not isinstance(name, str) or not name.strip():
        raise SchemaError(f"{label} must be a non-empty string.")
    return name.strip()


@dataclass(frozen=True, init=False)
class Entity:
    """Entity argument in predicate signatures. Always treated as key-like."""

    name: Optional[str]
    datatype: str
    namespace: Optional[str] = None
    role: str = "key"

    def __init__(
        self,
        name: str | None,
        datatype: DatalogDatatype,
        namespace: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        normalized_name = _normalize_name(name, label="Entity name")
        normalized_datatype = _normalize_datatype(datatype)
        normalized_role = role or "key"
        if normalized_role not in _ENTITY_ROLES:
            raise SchemaError(
                f"Entity role must be one of {sorted(_ENTITY_ROLES)}. Got: {normalized_role}"
            )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "datatype", normalized_datatype)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "role", normalized_role)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "entity",
            "datatype": self.datatype,
            "role": self.role,
            "namespace": self.namespace,
            "arg_name": self.name,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "Entity":
        if "datatype" not in data:
            raise SchemaError("Entity requires datatype.")
        name = data.get("name")
        if name is None:
            name = data.get("arg_name")
        return Entity(
            name=name if name is not None else None,
            datatype=str(data["datatype"]),
            role=data.get("role") if data.get("role") is not None else None,
            namespace=data.get("namespace") if data.get("namespace") is not None else None,
        )

    @property
    def arg_name(self) -> Optional[str]:
        return self.name


@dataclass(frozen=True, init=False)
class Value:
    """Value argument in predicate signatures."""

    name: Optional[str]
    datatype: str
    namespace: Optional[str] = None
    role: Optional[str] = None

    def __init__(
        self,
        name: str | None,
        datatype: DatalogDatatype,
        namespace: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        normalized_name = _normalize_name(name, label="Value name")
        normalized_datatype = _normalize_datatype(datatype)
        if role is not None and role in _ENTITY_ROLES:
            raise SchemaError("Value role cannot be key-like; use Entity instead.")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "datatype", normalized_datatype)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "role", role)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "value",
            "datatype": self.datatype,
            "role": self.role,
            "namespace": self.namespace,
            "arg_name": self.name,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> "Value":
        if "datatype" not in data:
            raise SchemaError("Value requires datatype.")
        name = data.get("name")
        if name is None:
            name = data.get("arg_name")
        return Value(
            name=name if name is not None else None,
            datatype=str(data["datatype"]),
            role=data.get("role") if data.get("role") is not None else None,
            namespace=data.get("namespace") if data.get("namespace") is not None else None,
        )

    @property
    def arg_name(self) -> Optional[str]:
        return self.name


ArgField: TypeAlias = Entity | Value


def field_from_dict(data: dict[str, object]) -> ArgField:
    kind = data.get("kind")
    role = data.get("role")
    if kind is not None:
        if kind == "entity":
            return Entity.from_dict(data)
        if kind == "value":
            return Value.from_dict(data)
        raise SchemaError("Argument kind must be either 'entity' or 'value'.")
    if role in _ENTITY_ROLES:
        return Entity.from_dict(data)
    return Value.from_dict(data)


def _order_fields_by_signature(signature: list[ArgField], field_names: list[str]) -> list[str]:
    if not isinstance(field_names, list) or not field_names:
        return []
    normalized = []
    seen = set()
    signature_names = {arg.name for arg in signature if arg.name}
    for name in field_names:
        if not isinstance(name, str) or not name.strip():
            raise SchemaError("Key field names must be non-empty strings.")
        if name not in signature_names:
            raise SchemaError(f"Key field {name} not found in signature.")
        seen.add(name)
    for arg in signature:
        if arg.name in seen:
            normalized.append(arg.name)
    return normalized


def _derive_key_field_names(signature: list[ArgField]) -> list[str]:
    for role in _KEY_ROLE_ORDER:
        names = [arg.name for arg in signature if arg.role == role]
        if names:
            return names
    return []


def _normalize_predicate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise SchemaError("Predicate name must be a non-empty string.")
    return name.strip().lower()


@dataclass(frozen=True)
class InstanceRef:
    """Reference to an instance using schema_id + key values."""

    schema_id: str
    key_values: dict[str, object]


@dataclass(frozen=True)
class PredicateSchema:
    """Schema for a predicate (fact or rule-level)."""

    name: str
    arity: int
    signature: list[ArgField]
    description: str | None = None
    kind: str = "fact"
    sub_schema_id: str | None = None
    obj_schema_id: str | None = None
    props: list[Value] | None = None
    key_fields: list[str] | None = None
    endpoints: dict[str, list[str]] | None = None
    merge_policy: Literal["max", "latest", "noisy_or", "overwrite", "keep_all"] | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise SchemaError("Predicate name must be non-empty.")
        if self.arity < 0:
            raise SchemaError("Predicate arity must be non-negative.")
        if self.kind not in {"fact", "rel"}:
            raise SchemaError("Predicate kind must be 'fact' or 'rel'.")
        if self.kind == "rel":
            if not self.sub_schema_id or not self.obj_schema_id:
                raise SchemaError("Rel predicates require sub_schema_id and obj_schema_id.")
        if self.arity != len(self.signature):
            raise SchemaError("Predicate arity must match signature length.")
        if self.description is not None and not isinstance(self.description, str):
            raise SchemaError("Predicate description must be a string if provided.")
        if self.merge_policy is not None:
            if not isinstance(self.merge_policy, str) or self.merge_policy not in _ALLOWED_MERGE_POLICIES:
                raise SchemaError(
                    f"merge_policy must be one of {sorted(_ALLOWED_MERGE_POLICIES)}."
                )
        normalized_signature = self._normalize_signature(self.signature)
        object.__setattr__(self, "signature", normalized_signature)
        if self.props is not None:
            if not isinstance(self.props, list):
                raise SchemaError("Predicate props must be a list of Value.")
            normalized_props = self._normalize_signature(self.props, allow_entity=False)
            object.__setattr__(self, "props", normalized_props)
        elif self.kind == "rel":
            object.__setattr__(self, "props", [])

        if self.kind == "fact":
            key_fields = self.key_fields
            if key_fields is None:
                key_fields = _derive_key_field_names(normalized_signature)
            else:
                if not isinstance(key_fields, list):
                    raise SchemaError("key_fields must be a list of strings.")
                key_fields = _order_fields_by_signature(normalized_signature, key_fields)
            if type(self).__name__ == "Fact" and not key_fields:
                raise SchemaError("Fact requires at least one key field.")
            object.__setattr__(self, "key_fields", key_fields)
            object.__setattr__(self, "endpoints", None)
        else:
            if self.endpoints is None:
                raise SchemaError("Rel predicates require endpoints.")
            sub_keys = self.endpoints.get("sub_key_fields")
            obj_keys = self.endpoints.get("obj_key_fields")
            if not isinstance(sub_keys, list) or not isinstance(obj_keys, list):
                raise SchemaError("Rel endpoints must define sub_key_fields and obj_key_fields.")
            for key in sub_keys + obj_keys:
                if not isinstance(key, str) or not key.strip():
                    raise SchemaError("Rel endpoint key fields must be non-empty strings.")
            if not sub_keys or not obj_keys:
                raise SchemaError(
                    "Rel subject and object each require at least one key field."
                )
            object.__setattr__(
                self,
                "endpoints",
                {"sub_key_fields": list(sub_keys), "obj_key_fields": list(obj_keys)},
            )
            object.__setattr__(self, "key_fields", None)
        cache_predicate_schema(self)

    @staticmethod
    def _normalize_signature(
        signature: list[ArgField],
        used: Optional[set[str]] = None,
        *,
        allow_entity: bool = True,
    ) -> list[ArgField]:
        used_names = set(used) if used is not None else set()
        normalized: list[ArgField] = []
        for arg in signature:
            if not isinstance(arg, (Entity, Value)):
                raise SchemaError("Predicate signature entries must be Entity or Value.")
            if isinstance(arg, Entity) and not allow_entity:
                raise SchemaError("Rel props cannot use Entity; use Value instead.")
            arg_name = arg.name
            if arg_name is None:
                key_like = isinstance(arg, Entity) or arg.role in _KEY_ROLE_ORDER
                base = _DEFAULT_KEY_NAME if key_like else _DEFAULT_PARAM_NAME
                candidate = base
                if candidate in used_names:
                    suffix = 2
                    while f"{base}{suffix}" in used_names:
                        suffix += 1
                    candidate = f"{base}{suffix}"
                arg_name = candidate
            else:
                if not isinstance(arg_name, str) or not arg_name.strip():
                    raise SchemaError("Argument name must be a non-empty string.")
                arg_name = arg_name.strip()
                if arg_name in used_names:
                    raise SchemaError(f"Duplicate argument name: {arg_name}")
            used_names.add(arg_name)
            if isinstance(arg, Entity):
                normalized.append(
                    Entity(
                        name=arg_name,
                        datatype=arg.datatype,
                        role=arg.role,
                        namespace=arg.namespace,
                    )
                )
            else:
                normalized.append(
                    Value(
                        name=arg_name,
                        datatype=arg.datatype,
                        role=arg.role,
                        namespace=arg.namespace,
                    )
                )
        return normalized

    def build_instance_ref(self, terms: list[object]) -> InstanceRef:
        """Build an InstanceRef for the given terms based on the key fields."""
        if len(terms) != self.arity:
            raise SchemaError("Instance terms length must match predicate arity.")
        index_map = {idx: arg for idx, arg in enumerate(self.signature)}
        key_names: list[str] = []
        if self.kind == "rel" and self.endpoints is not None:
            sub_keys = [f"sub_{name}" for name in self.endpoints.get("sub_key_fields", [])]
            obj_keys = [f"obj_{name}" for name in self.endpoints.get("obj_key_fields", [])]
            key_names = sub_keys + obj_keys
        elif self.key_fields is not None:
            key_names = list(self.key_fields)
        key_values: dict[str, object] = {}
        for idx, arg in index_map.items():
            if arg.name in key_names:
                key_values[arg.name or str(idx)] = terms[idx]
        return InstanceRef(schema_id=self.schema_id, key_values=key_values)

    @property
    def schema_id(self) -> str:
        if self.kind == "fact":
            payload = {
                "kind": self.kind,
                "name": self.name,
                "signature": [s.to_dict() for s in self.signature],
                "key_fields": list(self.key_fields or []),
            }
        else:
            payload = {
                "kind": self.kind,
                "name": self.name,
                "sub_schema_id": self.sub_schema_id,
                "obj_schema_id": self.obj_schema_id,
                "endpoints": self.endpoints,
                "props": [p.to_dict() for p in (self.props or [])],
            }
        return _hash_payload(payload)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "arity": self.arity,
            "schema_id": self.schema_id,
            "description": self.description,
            "kind": self.kind,
        }
        if self.merge_policy is not None:
            data["merge_policy"] = self.merge_policy
        if self.kind == "fact":
            data["signature"] = [s.to_dict() for s in self.signature]
            data["key_fields"] = list(self.key_fields or [])
        else:
            if self.sub_schema_id is not None:
                data["sub_schema_id"] = self.sub_schema_id
            if self.obj_schema_id is not None:
                data["obj_schema_id"] = self.obj_schema_id
            data["endpoints"] = self.endpoints
            data["props"] = [p.to_dict() for p in (self.props or [])]
            derived = getattr(self, "_derived_signature", None)
            if derived is None:
                sub_args = [{"arg_name": "Sub", "datatype": "fact"}]
                obj_args = [{"arg_name": "Obj", "datatype": "fact"}]
                prop_args = []
                for spec in self.signature:
                    if spec.role == "sub_key":
                        sub_args.append(spec.to_dict())
                    elif spec.role == "obj_key":
                        obj_args.append(spec.to_dict())
                    else:
                        prop_args.append(spec.to_dict())
                derived = {
                    "derived": True,
                    "sub_args": sub_args,
                    "obj_args": obj_args,
                    "prop_args": prop_args,
                }
            data["derived_signature"] = derived
        return data

    @staticmethod
    def from_dict(data: dict[str, object]) -> "PredicateSchema":
        if "name" not in data:
            raise SchemaError("PredicateSchema requires name.")
        kind = str(data.get("kind") or "fact")
        signature_data = data.get("signature")
        if kind == "rel" and signature_data is None:
            derived = data.get("derived_signature") or {}
            signature_data = derived.get("args")
            if signature_data is None:
                combined: list[object] = []
                for key in ("sub_args", "obj_args", "prop_args"):
                    items = derived.get(key) or []
                    if not isinstance(items, list):
                        raise SchemaError("PredicateSchema derived_signature args must be lists.")
                    combined.extend(items)
                def _include_item(item: object) -> bool:
                    if not isinstance(item, dict):
                        return False
                    item_datatype = item.get("datatype")
                    normalized_datatype = str(item_datatype).lower() if item_datatype is not None else None
                    if item.get("arg_name") in {"Sub", "Obj"} and normalized_datatype == "fact":
                        return False
                    role = item.get("role")
                    if role is None:
                        return True
                    return role in {"sub_key", "obj_key", "prop"}

                signature_data = [item for item in combined if _include_item(item)]
        if not isinstance(signature_data, list):
            raise SchemaError("PredicateSchema signature must be a list.")
        arity = data.get("arity")
        if arity is None:
            arity = len(signature_data)
        props_data = data.get("props")
        props = None
        if props_data is not None:
            if not isinstance(props_data, list):
                raise SchemaError("Predicate props must be a list.")
            props = []
            for item in props_data:
                if not isinstance(item, dict):
                    raise SchemaError("Predicate props entries must be dicts.")
                spec = field_from_dict(item)
                if isinstance(spec, Entity):
                    raise SchemaError("Predicate props must use Value, not Entity.")
                props.append(spec)
        key_fields = data.get("key_fields")
        endpoints = data.get("endpoints")
        signature: list[ArgField] = []
        for item in signature_data:
            if not isinstance(item, dict):
                raise SchemaError("Predicate signature entries must be dicts.")
            signature.append(field_from_dict(item))
        return PredicateSchema(
            name=str(data["name"]),
            arity=int(arity),
            signature=signature,
            description=data.get("description"),
            kind=kind,
            sub_schema_id=data.get("sub_schema_id"),
            obj_schema_id=data.get("obj_schema_id"),
            props=props,
            key_fields=key_fields,
            endpoints=endpoints,
            merge_policy=data.get("merge_policy"),
        )


@dataclass(frozen=True, init=False)
class Fact(PredicateSchema):
    """Predicate schema for node-like facts."""

    def __init__(
        self,
        name: str,
        args: list[ArgField],
        description: str | None = None,
        key_fields: list[str] | None = None,
        merge_policy: Literal["max", "latest", "noisy_or", "overwrite", "keep_all"] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            arity=len(args),
            signature=list(args),
            description=description,
            kind="fact",
            key_fields=key_fields,
            merge_policy=merge_policy,
        )


@dataclass(frozen=True, init=False)
class Rel(PredicateSchema):
    """Predicate schema for relations between facts."""

    props: list[Value] = field(default_factory=list)

    def __init__(
        self,
        name: str,
        sub: Fact,
        obj: Fact,
        props: list[Value] | None = None,
        description: str | None = None,
        endpoints: dict[str, list[str]] | None = None,
        merge_policy: Literal["max", "latest", "noisy_or", "overwrite", "keep_all"] | None = None,
    ) -> None:
        if sub.kind != "fact" or obj.kind != "fact":
            raise SchemaError("Rel requires fact sub/obj schemas.")
        props = list(props) if props else []

        if endpoints is None:
            sub_key_fields = list(sub.key_fields or [])
            obj_key_fields = list(obj.key_fields or [])
        else:
            sub_key_fields = endpoints.get("sub_key_fields", [])
            obj_key_fields = endpoints.get("obj_key_fields", [])
        sub_key_fields = _order_fields_by_signature(sub.signature, list(sub_key_fields))
        obj_key_fields = _order_fields_by_signature(obj.signature, list(obj_key_fields))
        endpoints = {"sub_key_fields": sub_key_fields, "obj_key_fields": obj_key_fields}

        sub_signature = []
        sub_by_name = {arg.name: arg for arg in sub.signature}
        for key_name in sub_key_fields:
            arg = sub_by_name[key_name]
            sub_signature.append(
                Entity(
                    name=f"sub_{arg.name}",
                    datatype=arg.datatype,
                    role="sub_key",
                    namespace=arg.namespace,
                )
            )
        obj_signature = []
        obj_by_name = {arg.name: arg for arg in obj.signature}
        for key_name in obj_key_fields:
            arg = obj_by_name[key_name]
            obj_signature.append(
                Entity(
                    name=f"obj_{arg.name}",
                    datatype=arg.datatype,
                    role="obj_key",
                    namespace=arg.namespace,
                )
            )
        used_names = {arg.name for arg in sub_signature + obj_signature if arg.name}
        normalized_props = PredicateSchema._normalize_signature(
            props,
            used=used_names,
            allow_entity=False,
        )
        value_props: list[Value] = []
        for arg in normalized_props:
            if not isinstance(arg, Value):
                raise SchemaError("Rel props must use Value arguments.")
            value_props.append(arg)
        prop_signature = [
            Value(
                name=arg.name,
                datatype=arg.datatype,
                role="prop",
                namespace=arg.namespace,
            )
            for arg in value_props
        ]
        signature = sub_signature + obj_signature + prop_signature
        super().__init__(
            name=name,
            arity=len(signature),
            signature=signature,
            description=description,
            kind="rel",
            sub_schema_id=sub.schema_id,
            obj_schema_id=obj.schema_id,
            props=value_props,
            endpoints=endpoints,
            merge_policy=merge_policy,
        )
        object.__setattr__(self, "props", value_props)
        derived_sub_args = [{"arg_name": "Sub", "datatype": "fact"}]
        for arg in sub.signature:
            role = "sub_key" if arg.name in sub_key_fields else "sub_attr"
            if role == "sub_key":
                derived_arg = Entity(
                    name=f"sub_{arg.name}",
                    datatype=arg.datatype,
                    role=role,
                    namespace=arg.namespace,
                )
            else:
                derived_arg = Value(
                    name=f"sub_{arg.name}",
                    datatype=arg.datatype,
                    role=role,
                    namespace=arg.namespace,
                )
            derived_sub_args.append(
                derived_arg.to_dict()
            )
        derived_obj_args = [{"arg_name": "Obj", "datatype": "fact"}]
        for arg in obj.signature:
            role = "obj_key" if arg.name in obj_key_fields else "obj_attr"
            if role == "obj_key":
                derived_arg = Entity(
                    name=f"obj_{arg.name}",
                    datatype=arg.datatype,
                    role=role,
                    namespace=arg.namespace,
                )
            else:
                derived_arg = Value(
                    name=f"obj_{arg.name}",
                    datatype=arg.datatype,
                    role=role,
                    namespace=arg.namespace,
                )
            derived_obj_args.append(
                derived_arg.to_dict()
            )
        derived_prop_args = [arg.to_dict() for arg in prop_signature]
        object.__setattr__(
            self,
            "_derived_signature",
            {
                "derived": True,
                "sub_args": derived_sub_args,
                "obj_args": derived_obj_args,
                "prop_args": derived_prop_args,
            },
        )


class FactSchema:
    """Collection of predicate schemas for facts."""

    def __init__(self, predicates: Iterable[PredicateSchema]):
        self._predicates = list(predicates)
        self._by_id: dict[str, PredicateSchema] = {}
        self._facts_by_name: dict[str, str] = {}
        self._rels_by_name: dict[str, str] = {}
        self._rels_by_triplet: dict[tuple[str, str, str], str] = {}
        self._validate()

    def _validate(self) -> None:
        self._by_id = {}
        self._facts_by_name = {}
        self._rels_by_name = {}
        self._rels_by_triplet = {}
        for pred in self._predicates:
            if pred.schema_id in self._by_id:
                raise SchemaError(
                    f"Duplicate predicate schema_id detected: {pred.schema_id} ({pred.name})."
                )
            self._by_id[pred.schema_id] = pred
            if pred.kind == "fact":
                normalized = _normalize_predicate_name(pred.name)
                if normalized in self._facts_by_name:
                    raise SchemaError(f"Duplicate fact name detected: {pred.name}.")
                self._facts_by_name[normalized] = pred.schema_id
            else:
                normalized = _normalize_predicate_name(pred.name)
                if normalized in self._rels_by_name:
                    raise SchemaError(f"Duplicate rel name detected: {pred.name}.")
                self._rels_by_name[normalized] = pred.schema_id
                triplet = (normalized, pred.sub_schema_id or "", pred.obj_schema_id or "")
                if triplet in self._rels_by_triplet:
                    raise SchemaError(
                        f"Duplicate rel triplet detected: {pred.name}({pred.sub_schema_id},{pred.obj_schema_id})."
                    )
                self._rels_by_triplet[triplet] = pred.schema_id
        for pred in self._predicates:
            if pred.kind == "rel":
                if pred.sub_schema_id not in self._by_id or pred.obj_schema_id not in self._by_id:
                    raise SchemaError(
                        f"Rel predicate {pred.name} requires known sub/obj schema ids."
                    )
                sub = self._by_id[pred.sub_schema_id]
                obj = self._by_id[pred.obj_schema_id]
                if sub.kind != "fact" or obj.kind != "fact":
                    raise SchemaError(
                        f"Rel predicate {pred.name} requires fact sub/obj schemas."
                    )

    def predicates(self) -> list[PredicateSchema]:
        return list(self._predicates)

    def facts(self) -> list[PredicateSchema]:
        return [pred for pred in self._predicates if pred.kind == "fact"]

    def rels(self) -> list[PredicateSchema]:
        return [pred for pred in self._predicates if pred.kind == "rel"]

    def names(self) -> dict[str, list[str]]:
        fact_names = sorted((pred.name for pred in self.facts()), key=str.lower)
        rel_names = sorted((pred.name for pred in self.rels()), key=str.lower)
        return {
            "facts": fact_names,
            "rels": rel_names,
        }

    def get(self, schema_id: str) -> PredicateSchema:
        if schema_id not in self._by_id:
            raise SchemaError(f"Unknown predicate schema_id: {schema_id}")
        return self._by_id[schema_id]

    def fact(self, name: str) -> Fact:
        schema_id = self._facts_by_name.get(_normalize_predicate_name(name))
        if not schema_id:
            raise SchemaError(f"Unknown fact name: {name}")
        pred = self.get(schema_id)
        if pred.kind != "fact":
            raise SchemaError(f"Predicate {name} is not a fact schema.")
        return pred  # type: ignore[return-value]

    def rel(self, name: str) -> Rel:
        schema_id = self._rels_by_name.get(_normalize_predicate_name(name))
        if not schema_id:
            raise SchemaError(f"Unknown rel name: {name}")
        pred = self.get(schema_id)
        if pred.kind != "rel":
            raise SchemaError(f"Predicate {name} is not a rel schema.")
        return pred  # type: ignore[return-value]

    def resolve(self, kind: str, name: str) -> str:
        if kind == "fact":
            schema_id = self._facts_by_name.get(_normalize_predicate_name(name))
        elif kind == "rel":
            schema_id = self._rels_by_name.get(_normalize_predicate_name(name))
        else:
            raise SchemaError(f"Unknown predicate kind: {kind}")
        if not schema_id:
            raise SchemaError(f"Unknown {kind} name: {name}")
        return schema_id

    def rel_of_ids(self, name: str, sub_schema_id: str, obj_schema_id: str) -> Rel:
        key = (_normalize_predicate_name(name), sub_schema_id, obj_schema_id)
        schema_id = self._rels_by_triplet.get(key)
        if not schema_id:
            raise SchemaError(
                f"Unknown rel triplet: {name}({sub_schema_id},{obj_schema_id})."
            )
        pred = self.get(schema_id)
        if pred.kind != "rel":
            raise SchemaError(f"Predicate {name} is not a rel schema.")
        return pred  # type: ignore[return-value]

    def describe(self, schema: PredicateSchema | str) -> dict[str, object]:
        schema_id = schema.schema_id if isinstance(schema, PredicateSchema) else str(schema)
        pred = self.get(schema_id)
        info: dict[str, object] = {
            "schema_id": pred.schema_id,
            "kind": pred.kind,
            "name": pred.name,
            "arity": pred.arity,
        }
        if pred.kind == "fact":
            info["key_fields"] = list(pred.key_fields or [])
            info["signature"] = [arg.to_dict() for arg in pred.signature]
        else:
            info["sub_schema_id"] = pred.sub_schema_id
            info["obj_schema_id"] = pred.obj_schema_id
            info["endpoints"] = pred.endpoints
            info["props"] = [arg.to_dict() for arg in (pred.props or [])]
        return info

    def to_dict(self) -> dict[str, object]:
        ordered = sorted(
            self._predicates, key=lambda pred: (pred.kind, pred.name, pred.schema_id)
        )
        return {"version": _SCHEMA_VERSION, "predicates": [p.to_dict() for p in ordered]}

    @staticmethod
    def from_dict(data: dict[str, object]) -> "FactSchema":
        version = data.get("version")
        if version is None:
            version = _SCHEMA_VERSION
        try:
            version = int(version)
        except (TypeError, ValueError) as exc:
            raise SchemaError("Schema version must be an integer.") from exc
        if version != _SCHEMA_VERSION:
            raise SchemaError(
                f"Unsupported schema version: {version}. Expected {_SCHEMA_VERSION}."
            )
        items = data.get("predicates")
        if not isinstance(items, list):
            raise SchemaError("FactSchema requires a list of predicates.")
        facts: list[PredicateSchema] = []
        rel_items: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                raise SchemaError("Predicate entries must be dicts.")
            kind = str(item.get("kind") or "fact")
            if kind not in {"fact", "rel"}:
                raise SchemaError(f"Predicate kind must be 'fact' or 'rel': {kind}")
            if kind == "rel":
                rel_items.append(item)
            else:
                signature = item.get("signature")
                if not isinstance(signature, list):
                    raise SchemaError("Predicate signature must be a list.")
                key_fields = item.get("key_fields")
                if key_fields is not None and not isinstance(key_fields, list):
                    raise SchemaError("key_fields must be a list of strings.")
                fact = Fact(
                    name=str(item["name"]),
                    args=[field_from_dict(arg) for arg in signature],
                    description=item.get("description"),
                    key_fields=key_fields,
                    merge_policy=item.get("merge_policy"),
                )
                if "schema_id" in item:
                    expected = str(item["schema_id"])
                    if expected != fact.schema_id:
                        raise SchemaError(
                            f"Fact schema_id mismatch for {fact.name}: {expected} vs {fact.schema_id}"
                        )
                if "arity" in item and int(item["arity"]) != fact.arity:
                    raise SchemaError(
                        f"Predicate arity mismatch for {fact.name}: {item['arity']} vs {fact.arity}"
                    )
                facts.append(fact)
        by_id = {fact.schema_id: fact for fact in facts}
        rels: list[PredicateSchema] = []
        for item in rel_items:
            sub_id = item.get("sub_schema_id")
            obj_id = item.get("obj_schema_id")
            if not sub_id or not obj_id:
                raise SchemaError("Rel predicate requires sub_schema_id and obj_schema_id.")
            sub = by_id.get(str(sub_id))
            obj = by_id.get(str(obj_id))
            if sub is None or obj is None:
                raise SchemaError("Rel predicate references unknown sub/obj schema.")
            props: list[Value] = []
            for arg in item.get("props", []):
                if not isinstance(arg, dict):
                    raise SchemaError("Rel props entries must be dicts.")
                spec = field_from_dict(arg)
                if isinstance(spec, Entity):
                    raise SchemaError("Rel props must use Value, not Entity.")
                props.append(spec)
            endpoints = item.get("endpoints")
            if endpoints is not None:
                if not isinstance(endpoints, dict):
                    raise SchemaError("Rel endpoints must be a dict.")
                if "sub_key_fields" not in endpoints or "obj_key_fields" not in endpoints:
                    raise SchemaError("Rel endpoints must include sub_key_fields and obj_key_fields.")
            rel = Rel(
                name=str(item["name"]),
                sub=sub,
                obj=obj,
                props=props,
                description=item.get("description"),
                endpoints=endpoints,
                merge_policy=item.get("merge_policy"),
            )
            if "schema_id" in item:
                expected = str(item["schema_id"])
                if expected != rel.schema_id:
                    raise SchemaError(
                        f"Rel schema_id mismatch for {rel.name}: {expected} vs {rel.schema_id}"
                    )
            if "arity" in item and int(item["arity"]) != rel.arity:
                raise SchemaError(
                    f"Rel predicate arity mismatch for {rel.name}: {item['arity']} vs {rel.arity}"
                )
            rels.append(rel)
            by_id[rel.schema_id] = rel
        return FactSchema(facts + rels)

    def view(self, schemas: Iterable[PredicateSchema | str]) -> "FactView":
        schema_ids: list[str] = []
        for item in schemas:
            if isinstance(item, PredicateSchema):
                schema_ids.append(item.schema_id)
            else:
                schema_ids.append(str(item))
        return FactView(self, schema_ids)

    def view_from_filter(self, filt) -> "FactView":
        from symir.ir.filters import apply_filter

        filtered = apply_filter(self._predicates, filt)
        return FactView(self, [p.schema_id for p in filtered])


# Alias for user-facing naming consistency.
FactLayer = FactSchema


class FactView:
    """View over a FactSchema containing a subset of predicate schemas."""

    def __init__(self, schema: FactSchema, schema_ids: Iterable[str]):
        self.schema = schema
        self.schema_ids = set(schema_ids)
        for schema_id in self.schema_ids:
            schema.get(schema_id)

    def allows(self, schema: PredicateSchema | str) -> bool:
        schema_id = schema.schema_id if isinstance(schema, PredicateSchema) else str(schema)
        return schema_id in self.schema_ids

    def predicates(self) -> list[PredicateSchema]:
        return [
            pred for pred in self.schema.predicates() if pred.schema_id in self.schema_ids
        ]

    def facts(self) -> list[PredicateSchema]:
        return [pred for pred in self.predicates() if pred.kind == "fact"]

    def rels(self) -> list[PredicateSchema]:
        return [pred for pred in self.predicates() if pred.kind == "rel"]

    def get(self, schema: PredicateSchema | str) -> PredicateSchema:
        schema_id = schema.schema_id if isinstance(schema, PredicateSchema) else str(schema)
        if schema_id not in self.schema_ids:
            raise SchemaError(f"Schema id not allowed in view: {schema_id}")
        return self.schema.get(schema_id)

    def fact(self, name: str) -> Fact:
        pred = self.schema.fact(name)
        if pred.schema_id not in self.schema_ids:
            raise SchemaError(f"Fact not allowed in view: {name}")
        return pred

    def rel(self, name: str) -> Rel:
        pred = self.schema.rel(name)
        if pred.schema_id not in self.schema_ids:
            raise SchemaError(f"Rel not allowed in view: {name}")
        return pred

    def resolve(self, kind: str, name: str) -> str:
        schema_id = self.schema.resolve(kind, name)
        if schema_id not in self.schema_ids:
            raise SchemaError(f"{kind} not allowed in view: {name}")
        return schema_id

    def names(self) -> dict[str, list[str]]:
        fact_names = sorted((pred.name for pred in self.facts()), key=str.lower)
        rel_names = sorted((pred.name for pred in self.rels()), key=str.lower)
        return {
            "facts": fact_names,
            "rels": rel_names,
        }

    def describe(self, schema: PredicateSchema | str) -> dict[str, object]:
        schema_id = schema.schema_id if isinstance(schema, PredicateSchema) else str(schema)
        if schema_id not in self.schema_ids:
            raise SchemaError(f"Schema id not allowed in view: {schema_id}")
        return self.schema.describe(schema_id)
