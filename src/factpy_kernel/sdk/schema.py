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
    def __init__(
        self,
        *,
        default: Any = None,
        default_factory: str | None = None,
        primary_key: bool = False,
    ) -> None:
        super().__init__()
        self.default = default
        self.default_factory = default_factory
        self.primary_key = bool(primary_key)

    def to_authoring(self, *, type_domain: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.sdk_attr_name,
            "type_domain": type_domain,
        }
        if self.default is not None:
            out["default"] = self.default
        if self.default_factory is not None:
            out["default_factory"] = self.default_factory
        if self.primary_key:
            out["primary_key"] = True
        return out


class Field(_DeclaredMember):
    def __init__(
        self,
        *,
        cardinality: str,
        description: str | None = None,
    ) -> None:
        super().__init__()
        self.cardinality = cardinality
        self.description = description

    def to_authoring(self, *, type_domain: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            "py_name": self.sdk_attr_name,
            "type_domain": type_domain,
            "cardinality": self.cardinality,
        }
        if self.description is not None:
            out["description"] = self.description
        return out

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.sdk_attr_name in instance.__dict__:
            return instance.__dict__[self.sdk_attr_name]
        return _UnsetFieldValue(instance=instance, field=self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if args:
            raise SDKSchemaError("Field head call does not support positional arguments")
        if not kwargs:
            raise SDKSchemaError("Field head call requires keyword arguments")
        if not any(_is_sdk_dsl_value(v) for v in kwargs.values()):
            raise SDKSchemaError("Field head call expects SDK DSL values (e.g. vars())")
        try:
            from .dsl.expr import build_field_head_call
        except Exception as exc:
            raise SDKSchemaError(f"SDK DSL is unavailable: {exc}") from exc
        return build_field_head_call(self, kwargs)


class EntityMeta(type):
    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls.__name__ != "Entity" and _looks_like_sdk_dsl_entity_call(args, kwargs):
            try:
                from .dsl.expr import build_entity_dsl_call
            except Exception as exc:
                raise SDKSchemaError(f"SDK DSL is unavailable: {exc}") from exc
            return build_entity_dsl_call(cls, args, kwargs)
        return super().__call__(*args, **kwargs)

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


class _UnsetFieldValue:
    """Sentinel for an unset `Field` value on a plain `Entity` instance.

    This preserves a more helpful error when users accidentally call batch-only
    methods (`.set/.add/.retract`) on regular in-memory entity objects.
    """

    def __init__(self, *, instance: Any, field: Field) -> None:
        self._instance = instance
        self._field = field

    def __repr__(self) -> str:
        return "None"

    __str__ = __repr__

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: Any) -> bool:
        return other is None

    def _raise_batch_only(self, method: str) -> None:
        owner = type(self._instance).__name__
        field_name = self._field.sdk_attr_name
        raise SDKSchemaError(
            f"'{owner}.{field_name}' is an unset Field value on a plain Entity instance; "
            f"'{method}(...)' is only available on sdk.batch() managed handles from tx.entity(...). "
            f"Use normal assignment (`obj.{field_name} = value`) for in-memory objects, "
            f"or create the object via tx.entity({owner}, ...) and then call '{field_name}.{method}(...)'."
        )

    def set(self, *args: Any, **kwargs: Any) -> None:
        self._raise_batch_only("set")

    def add(self, *args: Any, **kwargs: Any) -> None:
        self._raise_batch_only("add")

    def retract(self, *args: Any, **kwargs: Any) -> None:
        self._raise_batch_only("retract")


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


def _is_sdk_dsl_value(value: Any) -> bool:
    try:
        from .dsl.expr import is_dsl_head_kwarg_value
    except Exception:
        return False
    return bool(is_dsl_head_kwarg_value(value))


def _looks_like_sdk_dsl_entity_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    if args and kwargs:
        return False
    if kwargs:
        return any(_is_sdk_dsl_value(v) for v in kwargs.values())
    if len(args) == 1:
        return _is_sdk_dsl_value(args[0])
    return False


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
