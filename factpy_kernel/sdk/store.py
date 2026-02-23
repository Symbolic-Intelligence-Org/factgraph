from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from factpy_kernel.derivation.accept import AcceptOptions, AcceptResult
from factpy_kernel.derivation.candidates import CandidateSet
from factpy_kernel.evidence.write_protocol import add_field, retract_by_asrt, set_field
from factpy_kernel.export.package import ExportOptions, export_package
from factpy_kernel.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.runner.runner import run_package
from factpy_kernel.store.api import Store
from factpy_kernel.store.ledger import Ledger

from .compile import compile_schema_from_classes
from .errors import SDKSchemaError, SDKStoreError
from .schema import Entity, Field


class SDKStore:
    def __init__(self, classes: list[type[Entity]], *, store: Store | None = None, schema_ir: dict | None = None) -> None:
        if not isinstance(classes, list) or not classes:
            raise SDKStoreError("classes must be non-empty list[Entity]")
        self._classes = list(classes)
        for index, cls in enumerate(self._classes):
            if not isinstance(cls, type) or not issubclass(cls, Entity):
                raise SDKStoreError(f"classes[{index}] must be Entity subclass")

        if store is not None and schema_ir is not None and store.schema_ir is not schema_ir:
            raise SDKStoreError("provide either store or schema_ir (or matching store.schema_ir)")
        self._store = store if store is not None else Store(schema_ir=schema_ir or compile_schema_from_classes(self._classes))
        self._schema_ir = self._store.schema_ir
        self._field_pred_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._field_decl_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._entity_spec_by_class: dict[type[Entity], dict[str, Any]] = {}
        self._index_schema()

    @classmethod
    def from_schema_classes(
        cls,
        classes: list[type[Entity]],
        *,
        ledger: Ledger | None = None,
    ) -> "SDKStore":
        schema_ir = compile_schema_from_classes(classes)
        return cls(classes, store=Store(schema_ir=schema_ir, ledger=ledger))

    @property
    def store(self) -> Store:
        return self._store

    @property
    def ledger(self) -> Ledger:
        return self._store.ledger

    @property
    def schema_ir(self) -> dict[str, Any]:
        return self._schema_ir

    def ref(self, entity_cls: type[Entity], **identity_values: Any) -> str:
        spec = self._entity_spec_by_class.get(entity_cls)
        if spec is None:
            raise SDKStoreError(f"unknown Entity class: {getattr(entity_cls, '__name__', entity_cls)!r}")

        expected_names = {field["name"] for field in spec["identity_fields"]}
        extra_keys = sorted(set(identity_values.keys()) - expected_names)
        if extra_keys:
            raise SDKStoreError(f"unknown identity fields for {entity_cls.__name__}: {extra_keys}")

        tuples: list[tuple[str, str, Any]] = []
        for field in spec["identity_fields"]:
            name = field["name"]
            tag = field["type_domain"]
            if name in identity_values:
                raw_value = identity_values[name]
            elif field.get("default_factory") == "uuid4":
                raw_value = _default_uuid4_for_tag(tag)
            else:
                raise SDKStoreError(f"missing identity field: {entity_cls.__name__}.{name}")
            tuples.append((name, tag, _coerce_sdk_value_to_tag(tag, raw_value)))
        return encode_idref_v1(spec["entity_type"], tuples)

    def set(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        pred = self._schema_pred_for_field(field)
        rest_terms = self._rest_terms_for_field(pred, dims=dims, value=value)
        return set_field(self._store.ledger, pred["pred_id"], e_ref, rest_terms, meta)

    def add(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        pred = self._schema_pred_for_field(field)
        rest_terms = self._rest_terms_for_field(pred, dims=dims, value=value)
        return add_field(self._store.ledger, pred["pred_id"], e_ref, rest_terms, meta)

    def retract(self, asrt_id: str, *, meta: dict[str, Any] | None = None) -> str | None:
        return retract_by_asrt(self._store.ledger, asrt_id, meta)

    def evaluate(self, *args: Any, **kwargs: Any) -> list[CandidateSet]:
        return self._store.evaluate(*args, **kwargs)

    def accept(self, *args: Any, **kwargs: Any) -> AcceptResult:
        return self._store.accept(*args, **kwargs)

    def explain_fact(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.explain_fact(*args, **kwargs)

    def conflicts(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.conflicts(*args, **kwargs)

    def export_package(self, out_dir, options: ExportOptions, **kwargs: Any):
        return export_package(self._store, out_dir, options, **kwargs)

    def run_package(self, package_dir, *, entrypoints: list[str], engine: str = "souffle"):
        return run_package(package_dir, entrypoints=entrypoints, engine=engine)

    def _index_schema(self) -> None:
        pred_index: dict[tuple[str, str], dict[str, Any]] = {}
        for pred in self._schema_ir.get("predicates", []):
            if not isinstance(pred, dict):
                continue
            owner_type = pred.get("owner_type")
            py_field_name = pred.get("py_field_name")
            if isinstance(owner_type, str) and isinstance(py_field_name, str):
                pred_index[(owner_type, py_field_name)] = pred

        for cls in self._classes:
            spec = cls.sdk_entity_spec()
            self._entity_spec_by_class[cls] = spec
            for field_decl in spec.get("fields", []):
                py_name = field_decl["py_name"]
                descriptor = getattr(cls, py_name, None)
                if not isinstance(descriptor, Field):
                    continue
                key = (spec["entity_type"], py_name)
                pred = pred_index.get(key)
                if pred is None:
                    raise SDKStoreError(f"schema predicate not found for {spec['entity_type']}.{py_name}")
                self._field_pred_by_descriptor[descriptor] = pred
                self._field_decl_by_descriptor[descriptor] = field_decl

    def _schema_pred_for_field(self, field: Field) -> dict[str, Any]:
        if not isinstance(field, Field):
            raise SDKStoreError("field must be sdk.Field descriptor (e.g. Person.country)")
        pred = self._field_pred_by_descriptor.get(field)
        if pred is None:
            owner_name = getattr(getattr(field, "sdk_owner_cls", None), "__name__", "<unknown>")
            attr_name = getattr(field, "sdk_attr_name", "<unknown>")
            raise SDKStoreError(f"field is not bound in this SDKStore schema: {owner_name}.{attr_name}")
        return pred

    def _rest_terms_for_field(
        self,
        schema_pred: dict[str, Any],
        *,
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
        value: Any,
    ) -> list[tuple[str, Any]]:
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) < 2:
            raise SDKStoreError("schema predicate arg_specs invalid")

        dim_names = schema_pred.get("dims") or []
        if not isinstance(dim_names, list):
            raise SDKStoreError("schema predicate dims invalid")

        dim_specs = arg_specs[1:-1]
        value_spec = arg_specs[-1]
        if len(dim_names) != len(dim_specs):
            raise SDKStoreError("schema predicate dims/arg_specs mismatch")

        dim_values = self._normalize_dims_input(dim_names, dims)
        rest_terms: list[tuple[str, Any]] = []
        for dim_spec, dim_name in zip(dim_specs, dim_names):
            tag = dim_spec.get("type_domain")
            if not isinstance(tag, str):
                raise SDKStoreError("dim type_domain missing")
            rest_terms.append((tag, _coerce_sdk_value_to_tag(tag, dim_values[dim_name])))

        value_tag = value_spec.get("type_domain")
        if not isinstance(value_tag, str):
            raise SDKStoreError("value type_domain missing")
        rest_terms.append((value_tag, _coerce_sdk_value_to_tag(value_tag, value)))
        return rest_terms

    @staticmethod
    def _normalize_dims_input(
        dim_names: list[str],
        dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
    ) -> dict[str, Any]:
        if not dim_names:
            if dims is not None:
                raise SDKStoreError("dims not allowed for field without dims")
            return {}
        if dims is None:
            raise SDKStoreError(f"dims required: {dim_names}")
        if isinstance(dims, dict):
            missing = [name for name in dim_names if name not in dims]
            extra = [name for name in dims.keys() if name not in dim_names]
            if missing:
                raise SDKStoreError(f"missing dims: {missing}")
            if extra:
                raise SDKStoreError(f"unknown dims: {extra}")
            return {name: dims[name] for name in dim_names}
        if isinstance(dims, (list, tuple)):
            if len(dims) != len(dim_names):
                raise SDKStoreError(f"dims length mismatch: expected {len(dim_names)}")
            return {name: value for name, value in zip(dim_names, dims)}
        raise SDKStoreError("dims must be dict or list/tuple")


def _default_uuid4_for_tag(tag: str) -> str:
    if tag == "uuid":
        return str(uuid4()).lower()
    if tag == "string":
        return uuid4().hex
    raise SDKStoreError(f"default_factory='uuid4' not supported for type_domain={tag}")


def _coerce_sdk_value_to_tag(tag: str, value: Any) -> Any:
    if tag == "entity_ref":
        if not isinstance(value, str) or not value.startswith("idref_v1:"):
            raise SDKStoreError("entity_ref value must be canonical idref_v1 token")
        return value
    if tag == "string":
        if not isinstance(value, str):
            raise SDKStoreError("string field expects str")
        return value
    if tag == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SDKStoreError("int field expects int")
        return value
    if tag == "bool":
        if not isinstance(value, bool):
            raise SDKStoreError("bool field expects bool")
        return value
    if tag == "bytes":
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, memoryview):
            return value.tobytes()
        raise SDKStoreError("bytes field expects bytes-like")
    if tag == "time":
        if isinstance(value, bool):
            raise SDKStoreError("time field expects epoch-nanos int or aware datetime")
        if isinstance(value, int):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                raise SDKStoreError("time datetime must be timezone-aware")
            value_utc = value.astimezone(timezone.utc)
            return int(value_utc.timestamp() * 1_000_000_000)
        raise SDKStoreError("time field expects epoch-nanos int or aware datetime")
    if tag == "uuid":
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, str):
            return value.lower()
        raise SDKStoreError("uuid field expects UUID or canonical string")
    if tag == "float64":
        if isinstance(value, (float, str)):
            return value
        raise SDKStoreError("float64 field expects float or 0x<16hex> string")
    raise SDKStoreError(f"unsupported type_domain: {tag}")
