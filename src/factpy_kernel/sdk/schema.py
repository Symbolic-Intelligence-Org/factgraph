from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from .errors import SDKSchemaError

_BUILTIN_TAG_MAP = {
    str: "string",
    int: "int",
    bool: "bool",
    bytes: "bytes",
    float: "float64",
}


class _DeclaredMember:
    def __init__(self) -> None:
        self._sdk_attr_name: str | None = None
        self._sdk_owner_cls: type | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._sdk_attr_name = name
        self._sdk_owner_cls = owner

    @property
    def sdk_attr_name(self) -> str:
        if not self._sdk_attr_name:
            raise SDKSchemaError("descriptor is not bound to entity class")
        return self._sdk_attr_name

    @property
    def sdk_owner_cls(self) -> type:
        if self._sdk_owner_cls is None:
            raise SDKSchemaError("descriptor owner is not available")
        return self._sdk_owner_cls

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.sdk_attr_name)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.sdk_attr_name] = value


class Identity(_DeclaredMember):
    def __init__(self, *, default: Any = None, default_factory: str | None = None) -> None:
        super().__init__()
        self.default = default
        self.default_factory = default_factory

    def to_authoring(self, *, type_domain: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.sdk_attr_name,
            "type_domain": type_domain,
        }
        if self.default is not None:
            out["default"] = self.default
        if self.default_factory is not None:
            out["default_factory"] = self.default_factory
        return out


class Field(_DeclaredMember):
    def __init__(
        self,
        *,
        cardinality: str,
        name: str | None = None,
        pred_id: str | None = None,
        aliases: list[str] | None = None,
        display_name: str | None = None,
        description: str | None = None,
        value_name: str | None = None,
        fact_key: list[str] | None = None,
        dims: list[Any] | None = None,
        type_domain: str | None = None,
    ) -> None:
        super().__init__()
        self.cardinality = cardinality
        self.name = name
        self.pred_id = pred_id
        self.aliases = aliases
        self.display_name = display_name
        self.description = description
        self.value_name = value_name
        self.fact_key = fact_key
        self.dims = dims
        self.type_domain_override = type_domain

    def to_authoring(self, *, type_domain: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "py_name": self.sdk_attr_name,
            "type_domain": self.type_domain_override or type_domain,
            "cardinality": self.cardinality,
        }
        if self.name is not None:
            out["name"] = self.name
        if self.pred_id is not None:
            out["pred_id"] = self.pred_id
        if self.aliases is not None:
            out["aliases"] = list(self.aliases)
        if self.display_name is not None:
            out["display_name"] = self.display_name
        if self.description is not None:
            out["description"] = self.description
        if self.value_name is not None:
            out["value_name"] = self.value_name
        if self.fact_key is not None:
            out["fact_key"] = list(self.fact_key)
        if self.dims is not None:
            out["dims"] = _normalize_dims_for_authoring(self.dims)
        return out


class EntityMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, namespace)
        if name == "Entity":
            return cls

        annotations = dict(getattr(cls, "__annotations__", {}))
        identity_fields: list[tuple[str, Identity, Any]] = []
        fields: list[tuple[str, Field, Any]] = []

        for attr_name, annotation in annotations.items():
            member = getattr(cls, attr_name, None)
            if isinstance(member, Identity):
                identity_fields.append((attr_name, member, annotation))
            elif isinstance(member, Field):
                fields.append((attr_name, member, annotation))

        if not identity_fields:
            raise SDKSchemaError(f"Entity '{name}' must declare at least one Identity field")

        meta_dict = _extract_meta(getattr(cls, "Meta", None))
        cls.__sdk_entity_spec__ = {
            "entity_type": name,
            "identity_fields": [
                member.to_authoring(type_domain=_annotation_to_type_domain_runtime(annotation))
                for _, member, annotation in identity_fields
            ],
            "fields": [
                member.to_authoring(type_domain=_annotation_to_type_domain_runtime(annotation))
                for _, member, annotation in fields
            ],
            **({"meta": meta_dict} if meta_dict else {}),
            **({"is_record": True} if meta_dict.get("is_record") is True else {}),
        }
        return cls


class Entity(metaclass=EntityMeta):
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise SDKSchemaError(f"unknown entity attribute: {key}")
            setattr(self, key, value)

    @classmethod
    def sdk_entity_spec(cls) -> dict[str, Any]:
        spec = getattr(cls, "__sdk_entity_spec__", None)
        if not isinstance(spec, dict):
            raise SDKSchemaError(f"class '{cls.__name__}' is not a compiled Entity declaration")
        return spec


def _extract_meta(meta_cls: Any) -> dict[str, Any]:
    if meta_cls is None:
        return {}
    out: dict[str, Any] = {}
    for key, value in vars(meta_cls).items():
        if key.startswith("__"):
            continue
        if callable(value):
            continue
        out[key] = value
    return out


def _annotation_to_type_domain_runtime(annotation: Any) -> str:
    if annotation in _BUILTIN_TAG_MAP:
        return _BUILTIN_TAG_MAP[annotation]
    if annotation is UUID:
        return "uuid"
    if annotation is datetime:
        return "time"
    if isinstance(annotation, str):
        builtin_name_map = {
            "str": "string",
            "int": "int",
            "bool": "bool",
            "bytes": "bytes",
            "float": "float64",
            "UUID": "uuid",
            "datetime": "time",
        }
        if annotation in builtin_name_map:
            return builtin_name_map[annotation]
        if annotation in {"entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"}:
            return annotation
        return "entity_ref"
    if isinstance(annotation, type):
        if issubclass(annotation, Entity):
            return "entity_ref"
        if annotation.__name__ in {"UUID"}:
            return "uuid"
        if annotation.__name__ in {"datetime"}:
            return "time"
    return "entity_ref"


def _normalize_dims_for_authoring(dims: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in dims:
        if isinstance(item, dict):
            name = item.get("name")
            type_domain = item.get("type_domain")
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            name, type_domain = item
        else:
            raise SDKSchemaError("Field.dims entries must be {'name','type_domain'} or (name, type)")
        if not isinstance(name, str) or not name:
            raise SDKSchemaError("Field.dims name must be non-empty string")
        if not isinstance(type_domain, str) or not type_domain:
            raise SDKSchemaError("Field.dims type_domain must be non-empty string")
        if type_domain == "float":
            type_domain = "float64"
        out.append({"name": name, "type_domain": type_domain})
    return out
