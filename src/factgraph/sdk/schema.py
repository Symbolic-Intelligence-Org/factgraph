from __future__ import annotations

import ast
import re
import reprlib
from dataclasses import dataclass
from datetime import datetime
from types import UnionType
from typing import Any, Literal, get_args, get_origin
from uuid import UUID

from factgraph.core.schema.schema_repr import (
    SchemaReprTemplateError,
    validate_member_repr_template,
    validate_meta_repr_template,
)

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
        """Return the Python attribute name bound by the Entity metaclass."""
        if not self._sdk_attr_name:
            raise SDKSchemaError("descriptor is not bound to entity class")
        return self._sdk_attr_name

    @property
    def sdk_owner_cls(self) -> type:
        """Return the Entity class that owns this descriptor."""
        if self._sdk_owner_cls is None:
            raise SDKSchemaError("descriptor owner is not available")
        return self._sdk_owner_cls

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.sdk_attr_name)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__[self.sdk_attr_name] = value


@dataclass(frozen=True)
class _AnnotationPlan:
    type_domain: str
    cardinality: str = "single"
    enum_values: tuple[Any, ...] | None = None


class _DataMember(_DeclaredMember):
    def __init__(self, *, pattern: str | None = None, repr: str | None = None) -> None:
        super().__init__()
        if pattern is not None:
            if not isinstance(pattern, str) or not pattern:
                raise SDKSchemaError("pattern must be a non-empty string when provided")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise SDKSchemaError(f"pattern must be a valid regular expression: {exc}") from exc
        if repr is not None and (not isinstance(repr, str) or not repr):
            raise SDKSchemaError("repr must be a non-empty string when provided")
        self.pattern = pattern
        self.repr = repr

    def _add_common_authoring(self, out: dict[str, Any], *, plan: _AnnotationPlan) -> None:
        if self.pattern is not None:
            if plan.type_domain != "string":
                raise SDKSchemaError("pattern= is only supported for string-typed Identity/Field members")
            out["pattern"] = self.pattern
        if self.repr is not None:
            out["repr"] = self.repr


class Identity(_DataMember):
    """Declare an identity field on an `Entity`.

    Identity fields are part of an entity's stable identity and are used to
    build `idref_v1` references. Every `Identity()` field participates in the
    complete immutable identity bundle.

    Args:
        pattern: Optional regular-expression constraint for string identity
            values.
        repr: Optional explain-layer representation template. This metadata is
            validated and compiled into Schema IR without affecting schema identity.
    """

    def __init__(
        self,
        *,
        pattern: str | None = None,
        repr: str | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        if legacy_kwargs:
            legacy = ", ".join(sorted(legacy_kwargs))
            raise SDKSchemaError(
                "Identity() only accepts pattern= and repr= in Form I; "
                f"unsupported argument(s): {legacy}. "
                "Remove primary_key/default/default_factory. All Identity fields are immutable "
                "anchor members, and callers must provide the complete identity bundle explicitly."
            )
        super().__init__(pattern=pattern, repr=repr)

    def to_authoring(self, *, plan: _AnnotationPlan) -> dict[str, Any]:
        """Return canonical schema-authoring data for this identity field.

        Args:
            plan: Type/cardinality information derived from the annotation.

        Returns:
            A canonical identity-field authoring mapping.
        """
        if plan.cardinality != "single":
            raise SDKSchemaError("Identity fields must use a single-value annotation")
        out: dict[str, Any] = {
            "name": self.sdk_attr_name,
            "type_domain": plan.type_domain,
        }
        self._add_common_authoring(out, plan=plan)
        return out


class Field(_DataMember):
    """Declare a non-identity field on an `Entity`.

    Cardinality is inferred from the type annotation: scalar annotations create
    single-value fields, while list/set/frozenset and variadic tuple
    annotations create multi-value fields. Fields do not support defaults or
    backfill; missing added fields read as `None` for single fields and `()` for
    multi fields.

    Args:
        pattern: Optional regular-expression constraint for string fields.
        repr: Optional explain-layer representation template. This metadata is
            validated and compiled into Schema IR without affecting schema identity.
    """

    def __init__(
        self,
        *,
        pattern: str | None = None,
        repr: str | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        if legacy_kwargs:
            legacy = ", ".join(sorted(legacy_kwargs))
            raise SDKSchemaError(
                "Field() only accepts pattern= and repr= in Form I; "
                f"unsupported argument(s): {legacy}. "
                "Replace Field(cardinality='single') with a scalar annotation and Field(), "
                "or Field(cardinality='multi') with list[T]/set[T]/frozenset[T]/tuple[T, ...] "
                "and Field()."
            )
        super().__init__(pattern=pattern, repr=repr)
        self._inferred_cardinality: str | None = None

    @property
    def cardinality(self) -> str:
        """Return the cardinality inferred from the bound type annotation."""
        if self._inferred_cardinality is None:
            raise SDKSchemaError("Field cardinality is unavailable until the descriptor is bound to a schema class")
        return self._inferred_cardinality

    def to_authoring(self, *, plan: _AnnotationPlan) -> dict[str, Any]:
        """Return canonical schema-authoring data for this field.

        Args:
            plan: Type/cardinality information derived from the annotation.

        Returns:
            A canonical field authoring mapping.
        """
        self._inferred_cardinality = plan.cardinality
        out: dict[str, Any] = {
            "py_name": self.sdk_attr_name,
            "type_domain": plan.type_domain,
            "cardinality": plan.cardinality,
        }
        if plan.enum_values is not None:
            out["enum_values"] = list(plan.enum_values)
        self._add_common_authoring(out, plan=plan)
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
                _validate_member_repr_for_sdk(member, field_name=attr_name)
                identity_fields.append((attr_name, member, annotation))
            elif isinstance(member, Field):
                _validate_member_repr_for_sdk(member, field_name=attr_name)
                fields.append((attr_name, member, annotation))

        if not identity_fields:
            raise SDKSchemaError(f"Entity '{name}' must declare at least one Identity field")

        declaration_fields = _extract_entity_declaration_fields(
            getattr(cls, "Meta", None),
            identity_field_names=tuple(name for name, _member, _annotation in identity_fields),
        )
        spec = {
            "entity_type": name,
            "identity_fields": [
                member.to_authoring(plan=_annotation_plan_runtime(annotation))
                for _, member, annotation in identity_fields
            ],
            "fields": [
                member.to_authoring(plan=_annotation_plan_runtime(annotation))
                for _, member, annotation in fields
            ],
        }
        if "version" in declaration_fields:
            spec["version"] = declaration_fields["version"]
        if "repr" in declaration_fields:
            spec["repr"] = declaration_fields["repr"]
        if "tags" in declaration_fields:
            spec["tags"] = declaration_fields["tags"]
        cls.__sdk_entity_spec__ = spec
        return cls


class Entity(metaclass=EntityMeta):
    """Base class for Python schema entity declarations.

    Subclass `Entity` and declare annotated `Identity` and `Field` descriptors.
    The metaclass compiles those annotations into `__sdk_entity_spec__`, which
    `FactGraph.create(schema_classes=[...])` uses to build the graph schema.
    """

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
        ordered_names.extend(sorted(name for name in self.__dict__ if name not in seen))
        items = [f"{name}={reprlib.repr(getattr(self, name))}" for name in ordered_names]
        preview = ", ".join(items[:8])
        if len(items) > 8:
            preview += f", ... (+{len(items) - 8} fields)"
        return f"{cls.__name__}({preview})"

    @classmethod
    def sdk_entity_spec(cls) -> dict[str, Any]:
        """Return the schema specification compiled for this Entity class.

        Returns:
            The Entity declaration consumed by FactGraph schema compilation.

        Raises:
            SDKSchemaError: If the class is not a compiled Entity declaration.
        """
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
                _validate_member_repr_for_sdk(member, field_name=attr_name)
                fields.append((attr_name, member, annotation))

        spec = {
            "relationship_type": name,
            "from_entity_type": from_entity_type,
            "to_entity_type": to_entity_type,
            "fields": [
                member.to_authoring(plan=_annotation_plan_runtime(annotation))
                for _, member, annotation in fields
            ],
        }
        cls.__sdk_relationship_spec__ = spec
        return cls


class Relationship(metaclass=RelationshipMeta):
    """Base class for relationship (edge) type declarations."""

    @classmethod
    def sdk_relationship_spec(cls) -> dict[str, Any]:
        """Return the schema specification compiled for this Relationship.

        Returns:
            A copy of the relationship declaration.

        Raises:
            SDKSchemaError: If the class is not a compiled Relationship.
        """
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


def _extract_entity_declaration_fields(meta_cls: Any, *, identity_field_names: tuple[str, ...]) -> dict[str, Any]:
    if meta_cls is None:
        return {}
    allowed = {"version", "tags", "repr"}
    raw: dict[str, Any] = {}
    for key, value in vars(meta_cls).items():
        if key.startswith("__"):
            continue
        if callable(value):
            continue
        if key not in allowed:
            raise SDKSchemaError(
                f"Entity.Meta only supports version, tags, and repr; got unsupported key: {key}"
            )
        raw[key] = value
    out: dict[str, Any] = {}
    if "version" in raw:
        version = raw["version"]
        if not isinstance(version, str) or not version:
            raise SDKSchemaError("Entity.Meta.version must be non-empty string")
        out["version"] = version
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
    if "repr" in raw:
        try:
            validate_meta_repr_template(raw["repr"], identity_field_names=identity_field_names)
        except SchemaReprTemplateError as exc:
            raise SDKSchemaError(str(exc)) from exc
        out["repr"] = raw["repr"]
    return out


def _validate_member_repr_for_sdk(member: _DataMember, *, field_name: str) -> None:
    try:
        validate_member_repr_template(member.repr, field_name=field_name)
    except SchemaReprTemplateError as exc:
        raise SDKSchemaError(str(exc)) from exc


def _is_sdk_dsl_value(value: Any) -> bool:
    try:
        from .dsl.expr import is_dsl_head_kwarg_value
    except Exception:  # noqa: BLE001 - optional DSL module import boundary: an unimportable dsl.expr means the value cannot be a DSL head kwarg
        return False
    return bool(is_dsl_head_kwarg_value(value))


def _looks_like_sdk_dsl_entity_call(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    if args and kwargs:
        return False
    if kwargs:
        return any(_is_sdk_dsl_value(v) for v in kwargs.values())
    if len(args) == 1:
        if args[0] is Ellipsis:
            return True
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
    return _annotation_plan_runtime(annotation).type_domain


def _annotation_plan_runtime(annotation: Any) -> _AnnotationPlan:
    if isinstance(annotation, str):
        return _annotation_plan_from_string(annotation)
    return _annotation_plan_from_object(annotation)


def _annotation_plan_from_object(annotation: Any) -> _AnnotationPlan:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {list, set, frozenset}:
        return _multi_annotation_plan(args, annotation=annotation)
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return _multi_annotation_plan((args[0],), annotation=annotation)
        raise SDKSchemaError("tuple fields must use tuple[T, ...] for multi-cardinality Form I fields")
    if origin is Literal:
        return _literal_annotation_plan(args)
    if origin in {UnionType} or origin is _typing_union_origin():
        raise SDKSchemaError("Optional/Union annotations are not supported in Form I schema declarations")
    if origin is dict:
        raise SDKSchemaError("dict annotations are not supported in Form I schema declarations")
    if origin is not None:
        raise SDKSchemaError("unsupported generic annotation in Form I schema declarations")

    return _scalar_annotation_plan(annotation)


def _multi_annotation_plan(args: tuple[Any, ...], *, annotation: Any) -> _AnnotationPlan:
    if len(args) != 1:
        raise SDKSchemaError(f"multi-cardinality field annotation must specify exactly one element type: {annotation!r}")
    inner = _annotation_plan_from_object(args[0])
    if inner.cardinality != "single":
        raise SDKSchemaError("multi-cardinality fields must use a scalar element annotation")
    return _AnnotationPlan(type_domain=inner.type_domain, cardinality="multi", enum_values=inner.enum_values)


def _literal_annotation_plan(values: tuple[Any, ...]) -> _AnnotationPlan:
    if not values:
        raise SDKSchemaError("Literal[...] enum fields must declare at least one value")
    type_domains = {_literal_value_type_domain(value) for value in values}
    if len(type_domains) != 1:
        raise SDKSchemaError("Literal[...] enum values must all use the same canonical type")
    type_domain = next(iter(type_domains))
    if type_domain == "float64":
        raise SDKSchemaError("Literal[...] float enum values are not supported; use an unconstrained float field")
    return _AnnotationPlan(type_domain=type_domain, enum_values=tuple(values))


def _literal_value_type_domain(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, UUID):
        return "uuid"
    if isinstance(value, datetime):
        return "time"
    raise SDKSchemaError(f"Literal[...] enum value has unsupported type: {type(value).__name__}")


def _scalar_annotation_plan(annotation: Any) -> _AnnotationPlan:
    if annotation in _BUILTIN_TAG_MAP:
        return _AnnotationPlan(_BUILTIN_TAG_MAP[annotation])
    if annotation is UUID:
        return _AnnotationPlan("uuid")
    if annotation is datetime:
        return _AnnotationPlan("time")
    if isinstance(annotation, type):
        if issubclass(annotation, Entity):
            return _AnnotationPlan("entity_ref")
        if annotation.__name__ in {"UUID"}:
            return _AnnotationPlan("uuid")
        if annotation.__name__ in {"datetime"}:
            return _AnnotationPlan("time")
    return _AnnotationPlan("entity_ref")


def _annotation_plan_from_string(annotation: str) -> _AnnotationPlan:
    if not annotation:
        raise SDKSchemaError("empty annotation strings are not supported")
    try:
        expr = ast.parse(annotation, mode="eval").body
    except SyntaxError:
        return _scalar_annotation_plan_from_name(annotation)
    return _annotation_plan_from_ast(expr)


def _annotation_plan_from_ast(node: ast.AST) -> _AnnotationPlan:
    if isinstance(node, ast.Name):
        return _scalar_annotation_plan_from_name(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _scalar_annotation_plan_from_name(node.value)
    if isinstance(node, ast.Attribute):
        name = _ast_dotted_name(node)
        if name in {"uuid.UUID", "UUID"}:
            return _AnnotationPlan("uuid")
        if name in {"datetime.datetime", "datetime"}:
            return _AnnotationPlan("time")
        return _AnnotationPlan("entity_ref")
    if isinstance(node, ast.Subscript):
        name = _ast_dotted_name(node.value)
        args = _ast_subscript_args(node.slice)
        if name in {"list", "List", "set", "Set", "frozenset", "FrozenSet"}:
            if len(args) != 1:
                raise SDKSchemaError(f"{name}[...] must specify exactly one element type")
            inner = _annotation_plan_from_ast(args[0])
            if inner.cardinality != "single":
                raise SDKSchemaError("multi-cardinality fields must use a scalar element annotation")
            return _AnnotationPlan(type_domain=inner.type_domain, cardinality="multi", enum_values=inner.enum_values)
        if name in {"tuple", "Tuple"}:
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                inner = _annotation_plan_from_ast(args[0])
                if inner.cardinality != "single":
                    raise SDKSchemaError("multi-cardinality fields must use a scalar element annotation")
                return _AnnotationPlan(type_domain=inner.type_domain, cardinality="multi", enum_values=inner.enum_values)
            raise SDKSchemaError("tuple fields must use tuple[T, ...] for multi-cardinality Form I fields")
        if name in {"Literal", "typing.Literal"}:
            return _literal_annotation_plan(tuple(_ast_literal_value(arg) for arg in args))
        if name in {"dict", "Dict", "typing.Dict"}:
            raise SDKSchemaError("dict annotations are not supported in Form I schema declarations")
        if name in {"Optional", "typing.Optional", "Union", "typing.Union"}:
            raise SDKSchemaError("Optional/Union annotations are not supported in Form I schema declarations")
        raise SDKSchemaError("unsupported generic annotation in Form I schema declarations")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        raise SDKSchemaError("Optional/Union annotations are not supported in Form I schema declarations")
    return _AnnotationPlan("entity_ref")


def _scalar_annotation_plan_from_name(name: str) -> _AnnotationPlan:
    builtin_name_map = {
        "str": "string",
        "int": "int",
        "bool": "bool",
        "bytes": "bytes",
        "float": "float64",
        "UUID": "uuid",
        "uuid.UUID": "uuid",
        "datetime": "time",
        "datetime.datetime": "time",
    }
    if name in builtin_name_map:
        return _AnnotationPlan(builtin_name_map[name])
    if name in {"entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"}:
        return _AnnotationPlan(name)
    return _AnnotationPlan("entity_ref")


def _ast_dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _ast_dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _ast_subscript_args(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.Tuple):
        return tuple(node.elts)
    return (node,)


def _ast_literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError) as exc:
        raise SDKSchemaError("Literal[...] values must be literal constants") from exc


def _typing_union_origin() -> Any:
    try:
        from typing import Union
    except Exception:  # noqa: BLE001 - typing import boundary: without typing.Union there is no union origin to compare against
        return None
    return Union
