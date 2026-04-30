from __future__ import annotations

from datetime import datetime
import inspect
import reprlib
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
        if not any(member.primary_key for _, member, _ in identity_fields):
            raise SDKSchemaError(
                f"Entity '{name}' must declare at least one Identity(primary_key=True) field"
            )

        declaration_fields = _extract_entity_declaration_fields(getattr(cls, "Meta", None))
        description = declaration_fields.pop("description", None)
        if description is None:
            description = _extract_entity_docstring(cls)
        spec = {
            "entity_type": name,
            "identity_fields": [
                member.to_authoring(type_domain=_annotation_to_type_domain_runtime(annotation))
                for _, member, annotation in identity_fields
            ],
            "fields": [
                member.to_authoring(type_domain=_annotation_to_type_domain_runtime(annotation))
                for _, member, annotation in fields
            ],
        }
        if "version" in declaration_fields:
            spec["version"] = declaration_fields["version"]
        if description is not None:
            spec["description"] = description
        if "tags" in declaration_fields:
            spec["tags"] = declaration_fields["tags"]
        cls.__sdk_entity_spec__ = spec
        return cls


class Entity(metaclass=EntityMeta):
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise SDKSchemaError(f"unknown entity attribute: {key}")
            setattr(self, key, value)

    def __repr__(self) -> str:
        cls = type(self)
        spec = getattr(cls, "__sdk_entity_spec__", None)
        ordered_names: list[str] = []
        if isinstance(spec, dict):
            ordered_names.extend(
                row["name"]
                for row in spec.get("identity_fields", ())
                if isinstance(row, dict) and isinstance(row.get("name"), str)
            )
            ordered_names.extend(
                row["py_name"]
                for row in spec.get("fields", ())
                if isinstance(row, dict) and isinstance(row.get("py_name"), str)
            )
        seen = set(ordered_names)
        ordered_names.extend(sorted(name for name in self.__dict__.keys() if name not in seen))
        items = [f"{name}={reprlib.repr(getattr(self, name))}" for name in ordered_names]
        preview = ", ".join(items[:8])
        if len(items) > 8:
            preview += f", ... (+{len(items) - 8} fields)"
        return f"{cls.__name__}({preview})"

    @classmethod
    def sdk_entity_spec(cls) -> dict[str, Any]:
        spec = getattr(cls, "__sdk_entity_spec__", None)
        if not isinstance(spec, dict):
            raise SDKSchemaError(f"class '{cls.__name__}' is not a compiled Entity declaration")
        return spec


class RelationshipMeta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        cls = super().__new__(mcls, name, bases, namespace)
        if name == "Relationship":
            return cls

        annotations = dict(getattr(cls, "__annotations__", {}))
        from_entity = namespace.get("from_entity")
        if from_entity is None:
            from_entity = annotations.get("from_entity")
        to_entity = namespace.get("to_entity")
        if to_entity is None:
            to_entity = annotations.get("to_entity")

        if from_entity is None:
            raise SDKSchemaError(f"Relationship '{name}' must declare from_entity")
        if to_entity is None:
            raise SDKSchemaError(f"Relationship '{name}' must declare to_entity")

        from_entity_type = _relationship_endpoint_type_name(
            from_entity,
            relationship_name=name,
            field_name="from_entity",
        )
        to_entity_type = _relationship_endpoint_type_name(
            to_entity,
            relationship_name=name,
            field_name="to_entity",
        )

        fields: list[tuple[str, Field, Any]] = []
        for attr_name, annotation in annotations.items():
            if attr_name in {"from_entity", "to_entity"}:
                continue
            member = getattr(cls, attr_name, None)
            if isinstance(member, Field):
                fields.append((attr_name, member, annotation))

        spec = {
            "relationship_type": name,
            "from_entity_type": from_entity_type,
            "to_entity_type": to_entity_type,
            "fields": [
                member.to_authoring(type_domain=_annotation_to_type_domain_runtime(annotation))
                for _, member, annotation in fields
            ],
        }
        cls.__sdk_relationship_spec__ = spec
        return cls


class Relationship(metaclass=RelationshipMeta):
    """Base class for relationship (edge) type declarations."""

    @classmethod
    def sdk_relationship_spec(cls) -> dict[str, Any]:
        spec = getattr(cls, "__sdk_relationship_spec__", None)
        if not isinstance(spec, dict):
            raise SDKSchemaError(f"class '{cls.__name__}' is not a compiled Relationship declaration")
        return dict(spec)


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


def _extract_entity_declaration_fields(meta_cls: Any) -> dict[str, Any]:
    if meta_cls is None:
        return {}
    allowed = {"version", "description", "tags"}
    raw: dict[str, Any] = {}
    for key, value in vars(meta_cls).items():
        if key.startswith("__"):
            continue
        if callable(value):
            continue
        if key not in allowed:
            raise SDKSchemaError(
                f"Entity.Meta only supports version, description, and tags; got unsupported key: {key}"
            )
        raw[key] = value
    out: dict[str, Any] = {}
    if "version" in raw:
        version = raw["version"]
        if not isinstance(version, str) or not version:
            raise SDKSchemaError("Entity.Meta.version must be non-empty string")
        out["version"] = version
    if "description" in raw:
        description = raw["description"]
        if not isinstance(description, str) or not description:
            raise SDKSchemaError("Entity.Meta.description must be non-empty string")
        out["description"] = description
    if "tags" in raw:
        tags = raw["tags"]
        if not isinstance(tags, list):
            raise SDKSchemaError("Entity.Meta.tags must be list[str]")
        normalized_tags: list[str] = []
        for index, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag:
                raise SDKSchemaError(f"Entity.Meta.tags[{index}] must be non-empty string")
            normalized_tags.append(tag)
        out["tags"] = normalized_tags
    return out


def _extract_entity_docstring(entity_cls: type) -> str | None:
    raw_doc = entity_cls.__dict__.get("__doc__")
    if not isinstance(raw_doc, str):
        return None
    out = inspect.cleandoc(raw_doc).strip()
    return out or None


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


def _relationship_endpoint_type_name(annotation: Any, *, relationship_name: str, field_name: str) -> str:
    if isinstance(annotation, str):
        if not annotation:
            raise SDKSchemaError(f"Relationship '{relationship_name}' {field_name} must be non-empty string")
        return annotation
    if isinstance(annotation, type) and issubclass(annotation, Entity):
        return annotation.__name__
    raise SDKSchemaError(
        f"Relationship '{relationship_name}' {field_name} must be Entity subclass or string"
    )


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
