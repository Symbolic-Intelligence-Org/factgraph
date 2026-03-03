from __future__ import annotations

from datetime import datetime, timezone
import os
import warnings
from typing import Any
from uuid import UUID, uuid4

from factpy_kernel.authoring.derivations import compile_authoring_derivation_v1
from factpy_kernel.authoring.rules import compile_authoring_rule_v1
from factpy_kernel.core.derivation.accept import AcceptOptions, AcceptRequest, AcceptResult
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.evidence.write_protocol import add_field, retract_by_asrt, set_field
from factpy_kernel.core.schema.schema_ir import schema_digest
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule
from factpy_kernel.adapters.souffle.runner import run_package
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.core.store.ledger import Ledger

from .compile import compile_schema_from_classes
from .error_codes import (
    INVALID_ROW_FORMAT,
    QUERY_INVALID_ROW_FORMAT,
)
from .errors import SDKSchemaError, SDKStoreError
from .query_lower import QueryPlan, lower_query
from .query_runtime import execute_query_plan
from .schema import Entity, Field


class SDKStore:
    def __init__(
        self,
        classes: list[type[Entity]],
        *,
        store: Store | None = None,
        schema_ir: dict | None = None,
        default_row_format: str | None = None,
    ) -> None:
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
        self._schema_digest = schema_digest(self._schema_ir)
        self._field_pred_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._field_decl_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._entity_spec_by_class: dict[type[Entity], dict[str, Any]] = {}
        self._identity_values_by_e_ref: dict[str, dict[str, Any]] = {}
        self._default_row_format = default_row_format
        # Read once at init time; do not re-read env on each run().
        self._env_row_format = os.environ.get("FACTPY_ROW_FORMAT")
        self._index_schema()

    @classmethod
    def from_schema_classes(
        cls,
        classes: list[type[Entity]],
        *,
        ledger: Ledger | None = None,
        ledger_path: str | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        if ledger is not None and ledger_path is not None:
            raise SDKStoreError("provide either ledger or ledger_path, not both")

        schema_ir = compile_schema_from_classes(classes)
        digest = schema_digest(schema_ir)

        if ledger_path is not None:
            ledger = Ledger(path=ledger_path)

        if ledger is not None:
            stored_digest = ledger.get_ledger_meta("schema_digest")
            if stored_digest is None:
                ledger.set_ledger_meta("schema_digest", digest)
            elif stored_digest != digest:
                raise SDKStoreError(
                    f"schema mismatch: ledger file was written with schema_digest={stored_digest!r}, "
                    f"but current schema has digest={digest!r}. "
                    "Use the same Entity classes that were used when this ledger was created."
                )

        return cls(
            classes,
            store=Store(schema_ir=schema_ir, ledger=ledger),
            default_row_format=default_row_format,
        )

    @property
    def store(self) -> Store:
        return self._store

    @property
    def ledger(self) -> Ledger:
        return self._store.ledger

    @property
    def schema_ir(self) -> dict[str, Any]:
        return self._schema_ir

    def batch(self, *, meta: dict[str, Any] | None = None):
        from .batch import SDKBatchTx

        return SDKBatchTx(self, meta=meta)

    def get(self, entity_cls: type[Entity], **identity_kwargs: Any):
        from .facade import sdk_get

        return sdk_get(self, entity_cls, **identity_kwargs)

    def find(
        self,
        entity_cls: type[Entity],
        *,
        limit: int | None = None,
        **filter_kwargs: Any,
    ):
        from .facade import sdk_find

        return sdk_find(
            self,
            entity_cls,
            limit=limit,
            **filter_kwargs,
        )

    def edit(self, entity_cls: type[Entity], **identity_kwargs: Any):
        from .facade import sdk_edit

        return sdk_edit(self, entity_cls, **identity_kwargs)

    def ingest(
        self,
        data: Any,
        *,
        meta: dict[str, Any] | None = None,
        allow_sensitive_meta: bool = False,
    ):
        from .ingest import sdk_ingest

        return sdk_ingest(self, data, meta=meta, allow_sensitive_meta=allow_sensitive_meta)

    def validate_provenance(self, obj: Any, *, standard: str = "derivation_v1"):
        from .ingest import sdk_validate_provenance

        return sdk_validate_provenance(self, obj, standard=standard)

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
            elif "default" in field:
                raw_value = field["default"]
            elif field.get("default_factory") == "uuid4":
                raw_value = _default_uuid4_for_tag(tag)
            else:
                raise SDKStoreError(f"missing identity field: {entity_cls.__name__}.{name}")
            tuples.append((name, tag, _coerce_sdk_value_to_tag(tag, raw_value)))
        e_ref = encode_idref_v1(spec["entity_type"], tuples)
        self._identity_values_by_e_ref[e_ref] = {name: value for name, _, value in tuples}
        return e_ref

    def set(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        pred = self._schema_pred_for_field(field)
        owner_type = pred.get("owner_type")
        if isinstance(owner_type, str) and owner_type:
            self._ensure_identity_predicates_for_ref(owner_type=owner_type, e_ref=e_ref)
        rest_terms = self._rest_terms_for_field(pred, value=value)
        return set_field(self._store.ledger, pred["pred_id"], e_ref, rest_terms, meta)

    def add(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        pred = self._schema_pred_for_field(field)
        owner_type = pred.get("owner_type")
        if isinstance(owner_type, str) and owner_type:
            self._ensure_identity_predicates_for_ref(owner_type=owner_type, e_ref=e_ref)
        rest_terms = self._rest_terms_for_field(pred, value=value)
        return add_field(self._store.ledger, pred["pred_id"], e_ref, rest_terms, meta)

    def retract(self, asrt_id: str, *, meta: dict[str, Any] | None = None) -> str | None:
        return retract_by_asrt(self._store.ledger, asrt_id, meta)

    def run(
        self,
        obj: Any,
        *,
        row_format: str | None = None,
        registry: RuleRegistry | None = None,
    ) -> list[Any]:
        dispatch_key = self._run_dispatch_key(obj)
        dispatch_map = {
            "query": self._run_dispatch_query,
            "derivation": self._run_dispatch_derivation,
            "rule": self._run_dispatch_rule,
        }
        return dispatch_map[dispatch_key](
            obj,
            row_format=row_format,
            registry=registry,
        )

    def _run_dispatch_key(self, obj: Any) -> str:
        detectors = (
            ("query", _is_sdk_query_object),
            ("derivation", _is_derivation_run_object),
        )
        for key, detector in detectors:
            if detector(obj):
                return key
        return "rule"

    def _run_dispatch_query(
        self,
        query: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,  # reserved for unified run() signature
    ) -> list[Any]:
        del registry
        resolved_row_format = _resolve_query_row_format(row_format)
        return self._run_query(query, row_format=resolved_row_format)

    def _run_dispatch_derivation(
        self,
        derivation: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        del derivation, row_format, registry
        raise SDKStoreError(
            "Derivation is not supported by run(); use sdk.evaluate() instead",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.obj",
        )

    def _run_dispatch_rule(
        self,
        rule: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        resolved_row_format = _resolve_row_format(
            call_site=row_format,
            store_default=self._default_row_format,
            env_var=self._env_row_format,
        )
        return self._run_rule(
            rule,
            row_format=resolved_row_format,
            registry=registry,
        )

    def _run_rule(
        self,
        rule: Any,
        *,
        row_format: str,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        if isinstance(rule, str):
            raise SDKStoreError(
                "string rule DSL is not supported in SDK v1; use Rule object, RuleSpec, or structured rule dict"
            )
        compiled = self._compile_rule_input(rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        active_registry = registry if registry is not None else RuleRegistry()
        if registry is None:
            self._register_rule_dependencies(active_registry, rule)
        rows = run_rule(self._store, rule_spec, active_registry)
        return _format_rule_rows(rows, select_vars=list(rule_spec.select_vars), row_format=row_format)

    def _run_query(self, query: Any, *, row_format: str = "dict") -> list[Any]:
        plan = self._lower_query(query, return_mode=row_format)
        return execute_query_plan(self, plan)

    def _lower_query(self, query: Any, *, return_mode: str = "dict") -> QueryPlan:
        try:
            from .dsl import Query as SDKQuery
        except Exception as exc:
            raise SDKStoreError(f"Query DSL is unavailable: {exc}", path="$.run.obj") from exc

        if not isinstance(query, SDKQuery):
            raise SDKStoreError("query must be Query", path="$.run.obj")

        return lower_query(
            query,
            schema_ir=self._schema_ir,
            schema_digest=self._schema_digest,
            return_mode=return_mode,
        )

    def evaluate(self, *args: Any, **kwargs: Any) -> list[CandidateSet]:
        if "temporal_view" in kwargs:
            # TODO: temporal_view for evaluate() remains blocked.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable only after derivation/runtime temporal write semantics are defined.
            raise SDKStoreError("temporal_view is removed from evaluate(); use active/history views on read APIs")
        if args and isinstance(args[0], str):
            raise SDKStoreError(
                "string derivation DSL is not supported in SDK v1; use Derivation object or structured derivation dict"
            )
        if args and hasattr(args[0], "to_authoring_payload"):
            derivation = args[0]
            compiled_plans = self._compile_derivation_input(derivation)
            return self._evaluate_compiled_derivation_plans(
                compiled_plans,
                mode=kwargs.pop("mode", None),
            )
        if args and isinstance(args[0], dict) and ("derivation_id" in args[0] or "target_pred_id" in args[0] or "head" in args[0]):
            compiled_plans = self._compile_derivation_input(args[0])
            return self._evaluate_compiled_derivation_plans(
                compiled_plans,
                mode=kwargs.pop("mode", None),
            )
        return self._store.evaluate(*args, **kwargs)

    def _evaluate_compiled_derivation_plans(
        self,
        compiled_plans: list[dict[str, Any]],
        *,
        mode: str | None,
    ) -> list[CandidateSet]:
        if len(compiled_plans) == 1:
            return self._evaluate_single_derivation_plan(
                compiled_plans[0],
                mode=mode,
            )

        shared_run_id = self._derive_shared_run_id(compiled_plans[0]["derivation_id"])
        merged: list[CandidateSet] = []
        for plan in compiled_plans:
            plan_candidates = self._evaluate_single_derivation_plan(
                plan,
                mode=mode,
            )
            merged.extend(_with_candidate_run_id(plan_candidates, run_id=shared_run_id))
        return merged

    def _evaluate_single_derivation_plan(
        self,
        compiled: dict[str, Any],
        *,
        mode: str | None,
    ) -> list[CandidateSet]:
        resolved_mode = mode if mode is not None else compiled.get("mode", "python")
        return self._store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=list(compiled["head_vars"]),
            where=list(compiled["where"]),
            mode=resolved_mode,
            head=compiled.get("head"),
        )

    @staticmethod
    def _derive_shared_run_id(derivation_id: Any) -> str:
        if isinstance(derivation_id, str) and derivation_id:
            return f"{derivation_id}:{uuid4().hex[:8]}"
        return f"derive:{uuid4().hex[:8]}"

    def evaluate_compiled(self, *args: Any, **kwargs: Any) -> list[CandidateSet]:
        return self._store.evaluate(*args, **kwargs)

    def accept(self, *args: Any, **kwargs: Any) -> AcceptResult:
        if args and isinstance(args[0], CandidateSet):
            if len(args) != 1:
                raise SDKStoreError("accept(candidate_set, ...) accepts exactly one positional argument")
            candidate_set = args[0]
            options = self._accept_options_from_user_kwargs(kwargs)
            if kwargs:
                unknown = ", ".join(sorted(kwargs.keys()))
                raise SDKStoreError(f"unknown accept keyword(s): {unknown}")
            return self._store.accept(
                derivation_id=candidate_set.derivation_id,
                version=candidate_set.derivation_version,
                candidate_set=candidate_set,
                options=options,
            )
        return self._store.accept(*args, **kwargs)

    def accept_compiled(self, *args: Any, **kwargs: Any) -> AcceptResult:
        return self._store.accept(*args, **kwargs)

    def accept_many(
        self,
        requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
        *,
        mode: str = "atomic",
        idempotent_duplicate_ok: bool = True,
    ) -> list[dict[str, Any]]:
        return self._store.accept_many(
            requests,
            mode=mode,
            idempotent_duplicate_ok=idempotent_duplicate_ok,
        )

    def explain_fact(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.explain_fact(*args, **kwargs)

    def conflicts(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.conflicts(*args, **kwargs)

    def export_package(self, out_dir, options: ExportOptions, **kwargs: Any):
        return export_package(self._store, out_dir, options, **kwargs)

    def run_package(self, package_dir, *, entrypoints: list[str], engine: str = "souffle"):
        return run_package(package_dir, entrypoints=entrypoints, engine=engine)

    def _compile_rule_input(self, rule: Any) -> dict[str, Any]:
        if isinstance(rule, RuleSpec):
            return {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "select_vars": list(rule.select_vars),
                "where": list(rule.where),
                "expose": rule.expose,
            }
        if hasattr(rule, "to_authoring_payload"):
            payload = rule.to_authoring_payload()
        elif isinstance(rule, dict):
            payload = dict(rule)
        else:
            raise SDKStoreError("rule must be RuleSpec, SDK Rule object, or authoring rule payload dict")
        try:
            return compile_authoring_rule_v1(payload, schema_ir=self._schema_ir)
        except Exception as exc:
            raise SDKStoreError(f"invalid rule input: {exc}") from exc

    def _register_rule_dependencies(self, registry: RuleRegistry, rule: Any) -> None:
        if not hasattr(rule, "dependency_rules"):
            return
        deps = rule.dependency_rules()
        if not isinstance(deps, list):
            return
        visited: set[tuple[str, str]] = set()

        def add_dep(dep_rule: Any) -> None:
            if not hasattr(dep_rule, "to_authoring_payload"):
                return
            dep_compiled = self._compile_rule_input(dep_rule)
            key = (dep_compiled["rule_id"], dep_compiled["version"])
            if key in visited:
                return
            visited.add(key)
            if hasattr(dep_rule, "dependency_rules"):
                for child in dep_rule.dependency_rules():
                    add_dep(child)
            registry.register(
                RuleSpec(
                    rule_id=dep_compiled["rule_id"],
                    version=dep_compiled["version"],
                    select_vars=list(dep_compiled["select_vars"]),
                    where=list(dep_compiled["where"]),
                    expose=bool(dep_compiled.get("expose", False)),
                )
            )

        for dep in deps:
            add_dep(dep)

    def _compile_derivation_input(self, derivation: Any) -> list[dict[str, Any]]:
        if isinstance(derivation, dict) and {
            "derivation_id",
            "version",
            "target_pred_id",
            "head_vars",
            "where",
        }.issubset(set(derivation.keys())) and not isinstance(derivation.get("head"), list):
            return [dict(derivation)]
        if hasattr(derivation, "to_authoring_payload"):
            payload = derivation.to_authoring_payload()
        elif isinstance(derivation, dict):
            payload = dict(derivation)
        else:
            raise SDKStoreError(
                "derivation must be SDK Derivation object, compiled derivation dict, or authoring derivation payload dict"
            )
        payloads = _expand_authoring_derivation_heads(payload)
        try:
            return [
                compile_authoring_derivation_v1(single_payload, schema_ir=self._schema_ir)
                for single_payload in payloads
            ]
        except Exception as exc:
            raise SDKStoreError(f"invalid derivation input: {exc}") from exc

    @staticmethod
    def _accept_options_from_user_kwargs(kwargs: dict[str, Any]) -> AcceptOptions:
        raw_meta_overrides = kwargs.pop("meta_overrides", None)
        if raw_meta_overrides is None:
            meta_overrides: dict[str, Any] = {}
        elif isinstance(raw_meta_overrides, dict):
            meta_overrides = dict(raw_meta_overrides)
        else:
            raise SDKStoreError("meta_overrides must be dict when provided")

        # Blueprints commonly use meta_overrides={"approved_by": ...}; also support keyword sugar.
        for key in ("approved_by", "note", "dry_run", "identity_override"):
            if key in kwargs:
                if key in meta_overrides:
                    raise SDKStoreError(f"duplicate accept option: {key} provided in meta_overrides and keyword")
                meta_overrides[key] = kwargs.pop(key)

        approved_by = meta_overrides.pop("approved_by", None)
        note = meta_overrides.pop("note", None)
        dry_run = meta_overrides.pop("dry_run", False)
        identity_override = meta_overrides.pop("identity_override", None)
        if identity_override is not None and not isinstance(identity_override, dict):
            raise SDKStoreError("identity_override must be dict when provided")
        if meta_overrides:
            unknown = ", ".join(sorted(meta_overrides.keys()))
            raise SDKStoreError(f"unsupported meta_overrides keys for accept(): {unknown}")
        return AcceptOptions(
            approved_by=approved_by,
            note=note,
            dry_run=bool(dry_run),
            identity_override=dict(identity_override) if isinstance(identity_override, dict) else None,
        )

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
        value: Any,
    ) -> list[tuple[str, Any]]:
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise SDKStoreError("schema predicate arg_specs invalid")
        value_tag = arg_specs[1].get("type_domain")
        if not isinstance(value_tag, str):
            raise SDKStoreError("value type_domain missing")
        return [(value_tag, _coerce_sdk_value_to_tag(value_tag, value))]

    def _ensure_identity_predicates_for_ref(self, *, owner_type: str, e_ref: str) -> None:
        identity_values = self._identity_values_by_e_ref.get(e_ref)
        if not isinstance(identity_values, dict) or not identity_values:
            return
        for pred in self._schema_ir.get("predicates", []):
            if not isinstance(pred, dict):
                continue
            if pred.get("owner_type") != owner_type:
                continue
            if pred.get("is_identity_field") is not True:
                continue
            pred_id = pred.get("pred_id")
            field_name = pred.get("py_field_name")
            arg_specs = pred.get("arg_specs")
            if not isinstance(pred_id, str) or not pred_id:
                continue
            if not isinstance(field_name, str) or field_name not in identity_values:
                continue
            if not isinstance(arg_specs, list) or len(arg_specs) != 2:
                raise SDKStoreError(f"identity predicate arg_specs invalid for {pred_id}")
            value_spec = arg_specs[1] if isinstance(arg_specs[1], dict) else None
            type_domain = value_spec.get("type_domain") if isinstance(value_spec, dict) else None
            if not isinstance(type_domain, str) or not type_domain:
                raise SDKStoreError(f"identity predicate value type_domain invalid for {pred_id}")
            try:
                set_field(
                    self._store.ledger,
                    pred_id,
                    e_ref,
                    [(type_domain, identity_values[field_name])],
                    None,
                )
            except Exception as exc:
                raise SDKStoreError(
                    f"failed to materialize identity predicate for {owner_type}.{field_name}: {exc}"
                ) from exc


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


def _expand_authoring_derivation_heads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    head = payload.get("head")
    if not isinstance(head, list):
        return [dict(payload)]
    if not head:
        raise SDKStoreError("derivation head list must be non-empty", path="$.head")

    expanded: list[dict[str, Any]] = []
    for idx, head_item in enumerate(head):
        if not isinstance(head_item, dict):
            raise SDKStoreError("derivation head list item must be object", path=f"$.head[{idx}]")
        item_payload = dict(payload)
        item_payload["head"] = dict(head_item)
        expanded.append(item_payload)
    return expanded


def _with_candidate_run_id(candidates: list[CandidateSet], *, run_id: str) -> list[CandidateSet]:
    rewritten: list[CandidateSet] = []
    for candidate in candidates:
        rewritten.append(
            CandidateSet(
                derivation_id=candidate.derivation_id,
                derivation_version=candidate.derivation_version,
                run_id=run_id,
                target=candidate.target,
                key_tuple_digest=candidate.key_tuple_digest,
                tup_digest=candidate.tup_digest,
                payload=dict(candidate.payload),
                support_digest=candidate.support_digest,
                support_kind=candidate.support_kind,
                generated_at=candidate.generated_at,
                state=candidate.state,
                candidate_key=candidate.candidate_key,
                candidate_kind=candidate.candidate_kind,
            )
        )
    return rewritten


def _resolve_row_format(*, call_site: Any, store_default: Any, env_var: Any) -> str:
    for raw_value, path, source in (
        (call_site, "$.run.row_format", "call_site"),
        (store_default, "$.store.default_row_format", "store_default"),
        (env_var, "env:FACTPY_ROW_FORMAT", "env_var"),
    ):
        normalized = _normalize_row_format_value(raw_value, path=path)
        if normalized is not None:
            _warn_deprecated_tuple_row_format_if_needed(normalized, source=source)
            return normalized
    return "dict"


def _resolve_query_row_format(value: Any) -> str:
    if value is None:
        return "dict"
    if not isinstance(value, str):
        raise SDKStoreError(
            "Query row_format must be 'dict' or 'instance'",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )
    normalized = value.strip().lower()
    if normalized not in {"dict", "instance"}:
        raise SDKStoreError(
            "Query row_format must be 'dict' or 'instance'",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )
    return normalized


def _normalize_row_format_value(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path=path,
        )
    normalized = value.strip().lower()
    if normalized not in {"tuple", "dict"}:
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path=path,
        )
    return normalized


def _warn_deprecated_tuple_row_format_if_needed(normalized: str, *, source: str) -> None:
    if normalized != "tuple":
        return
    warnings.warn(
        "row_format='tuple' is deprecated and will be removed in a future release "
        f"(source={source}); use row_format='dict' or set FACTPY_ROW_FORMAT=dict.",
        DeprecationWarning,
        stacklevel=4,
    )


def _format_rule_rows(
    rows: list[tuple[Any, ...]],
    *,
    select_vars: list[str],
    row_format: str,
) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
    if row_format == "tuple":
        return rows
    if row_format != "dict":
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )

    columns: list[str] = []
    seen: set[str] = set()
    for idx, var in enumerate(select_vars):
        if not isinstance(var, str) or not var:
            raise SDKStoreError(
                "rule select_vars must be non-empty strings for row_format='dict'",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        key = var[1:] if var.startswith("$") else var
        if not key:
            raise SDKStoreError(
                "rule select_vars must not be empty for row_format='dict'",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        if key in seen:
            raise SDKStoreError(
                f"rule select_vars are not unique after alias normalization: {key}",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        seen.add(key)
        columns.append(key)

    out: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if len(row) != len(columns):
            raise SDKStoreError(
                f"row arity mismatch at row {row_index}: expected {len(columns)}, got {len(row)}",
                code=INVALID_ROW_FORMAT,
                path="$.run.result",
            )
        out.append({col: row[col_index] for col_index, col in enumerate(columns)})
    return out


def _is_sdk_query_object(obj: Any) -> bool:
    try:
        from .dsl import Query
    except Exception:
        return False
    return isinstance(obj, Query)


def _is_derivation_run_object(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(key in obj for key in ("derivation_id", "target_pred_id", "head"))
    try:
        from .dsl import Derivation
    except Exception:
        return False
    return isinstance(obj, Derivation)
