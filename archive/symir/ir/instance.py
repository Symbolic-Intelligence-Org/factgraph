"""Instance representation for facts and relations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable
import hashlib
import json

from symir.errors import SchemaError
from symir.ir.fact_schema import FactSchema, PredicateSchema, InstanceRef


def _canonical_json(payload: object, *, sort_keys: bool = True) -> str:
    return json.dumps(payload, sort_keys=sort_keys, separators=(",", ":"), ensure_ascii=False)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ordered_key_pairs(keys: Iterable[str], props: dict[str, object]) -> list[tuple[str, object]]:
    pairs: list[tuple[str, object]] = []
    for key in keys:
        if key not in props:
            raise SchemaError(f"Missing key field value: {key}")
        pairs.append((key, props[key]))
    return pairs


def _compute_entity_id(schema_id: str, key_fields: list[str], props: dict[str, object]) -> str:
    ordered_pairs = _ordered_key_pairs(key_fields, props)
    payload = schema_id + _canonical_json(ordered_pairs, sort_keys=False)
    return _hash_text(payload)


def _compute_record_id(
    schema_id: str,
    primary_ids: list[str],
    props: dict[str, object],
    meta: dict[str, object],
) -> str:
    evidence_id = meta.get("evidence_id")
    if not evidence_id:
        fallback = {
            "props": props,
            "source": meta.get("source"),
            "observed_at": meta.get("observed_at"),
            "ingested_at": meta.get("ingested_at"),
        }
        evidence_id = _hash_text(_canonical_json(fallback))
    payload = schema_id + "".join(primary_ids) + str(evidence_id)
    return _hash_text(payload)


def _ensure_meta(meta: Optional[dict[str, object]]) -> dict[str, object]:
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise SchemaError("Instance meta must be a dict if provided.")
    meta_copy = dict(meta)
    _validate_meta(meta_copy)
    return meta_copy


def _validate_meta(meta: dict[str, object]) -> None:
    allowed_keys = {
        "source",
        "observed_at",
        "ingested_at",
        "confidence",
        "status",
        "evidence_id",
        "trace_id",
        "provenance",
        "tags",
    }
    unknown = [key for key in meta.keys() if key not in allowed_keys]
    if unknown:
        raise SchemaError(f"Unknown meta keys: {sorted(unknown)}")
    allowed_status = {"asserted", "inferred", "retracted"}
    if "source" in meta and not isinstance(meta["source"], str):
        raise SchemaError("meta.source must be a string.")
    if "observed_at" in meta and not isinstance(meta["observed_at"], str):
        raise SchemaError("meta.observed_at must be a string.")
    if "ingested_at" in meta and not isinstance(meta["ingested_at"], str):
        raise SchemaError("meta.ingested_at must be a string.")
    if "confidence" in meta:
        confidence = meta["confidence"]
        if not isinstance(confidence, (int, float)):
            raise SchemaError("meta.confidence must be a number.")
        if not (0.0 <= float(confidence) <= 1.0):
            raise SchemaError("meta.confidence must be within [0.0, 1.0].")
    if "status" in meta:
        status = meta["status"]
        if not isinstance(status, str) or status not in allowed_status:
            raise SchemaError(
                f"meta.status must be one of {sorted(allowed_status)}."
            )
    if "evidence_id" in meta and not isinstance(meta["evidence_id"], str):
        raise SchemaError("meta.evidence_id must be a string.")
    if "trace_id" in meta and not isinstance(meta["trace_id"], str):
        raise SchemaError("meta.trace_id must be a string.")
    if "provenance" in meta and not isinstance(meta["provenance"], dict):
        raise SchemaError("meta.provenance must be a dict.")
    if "tags" in meta:
        tags = meta["tags"]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise SchemaError("meta.tags must be a list of strings.")


def _validate_prob(prob: Optional[float]) -> None:
    if prob is None:
        return
    if not isinstance(prob, (int, float)):
        raise SchemaError("Instance prob must be a number if provided.")
    if not (0.0 <= float(prob) <= 1.0):
        raise SchemaError("Instance prob must be within [0.0, 1.0].")


def _normalize_keys(value: dict[str, object], prefix: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SchemaError("Key dict must be a mapping.")
    normalized: dict[str, object] = {}
    for key, val in value.items():
        key_name = str(key)
        if key_name.startswith(prefix):
            key_name = key_name[len(prefix) :]
        normalized[key_name] = val
    return normalized


@dataclass(frozen=True, init=False)
class Instance:
    """Canonical instance for a fact or relation."""

    schema_id: str
    kind: str
    props: dict[str, object]
    prob: Optional[float] = None
    meta: dict[str, object]
    entity_id: Optional[str] = None
    sub_entity_id: Optional[str] = None
    obj_entity_id: Optional[str] = None
    record_id: Optional[str] = None
    _sub_key_props: Optional[dict[str, object]] = None
    _obj_key_props: Optional[dict[str, object]] = None

    def __init__(
        self,
        schema: PredicateSchema,
        terms: list[object] | tuple[object, ...] | dict[str, object],
        *,
        registry: Optional[FactSchema] = None,
        prob: Optional[float] = None,
        meta: Optional[dict[str, object]] = None,
        strict: bool = True,
        resolve_mode: str = "strict",
    ) -> None:
        _validate_prob(prob)
        meta = _ensure_meta(meta)
        if resolve_mode not in {"strict", "heuristic"}:
            raise SchemaError("resolve_mode must be 'strict' or 'heuristic'.")

        schema_obj: Optional[PredicateSchema] = None
        schema_id: Optional[str] = None
        if isinstance(schema, PredicateSchema):
            schema_obj = schema
            schema_id = schema.schema_id
        else:
            raise SchemaError("Instance schema must be a PredicateSchema (Fact/Rel).")

        kind = schema_obj.kind
        merge_policy = schema_obj.merge_policy
        if kind == "fact":
            props = self._parse_fact_terms(schema_obj, terms, strict=strict)
            entity_id = _compute_entity_id(schema_id, list(schema_obj.key_fields or []), props)
            record_id = None
            if merge_policy == "keep_all":
                record_id = _compute_record_id(schema_id, [entity_id], props, meta)
            object.__setattr__(self, "schema_id", schema_id)
            object.__setattr__(self, "kind", kind)
            object.__setattr__(self, "props", props)
            object.__setattr__(self, "prob", prob)
            object.__setattr__(self, "meta", meta)
            object.__setattr__(self, "entity_id", entity_id)
            object.__setattr__(self, "record_id", record_id)
            object.__setattr__(self, "_sub_key_props", None)
            object.__setattr__(self, "_obj_key_props", None)
            return

        sub_keys, obj_keys, rel_props, sub_id, obj_id = self._parse_rel_terms(
            schema_obj,
            terms,
            strict=strict,
            resolve_mode=resolve_mode,
        )
        record_id = None
        if merge_policy == "keep_all":
            record_id = _compute_record_id(schema_id, [sub_id, obj_id], rel_props, meta)
        object.__setattr__(self, "schema_id", schema_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "props", rel_props)
        object.__setattr__(self, "prob", prob)
        object.__setattr__(self, "meta", meta)
        object.__setattr__(self, "sub_entity_id", sub_id)
        object.__setattr__(self, "obj_entity_id", obj_id)
        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "_sub_key_props", sub_keys)
        object.__setattr__(self, "_obj_key_props", obj_keys)

    def to_dict(self, *, include_keys: bool = False) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_id": self.schema_id,
            "kind": self.kind,
            "props": dict(self.props),
            "prob": self.prob,
            "meta": dict(self.meta),
        }
        if self.kind == "fact":
            data["entity_id"] = self.entity_id
        else:
            data["sub_entity_id"] = self.sub_entity_id
            data["obj_entity_id"] = self.obj_entity_id
            if include_keys:
                if self._sub_key_props is None or self._obj_key_props is None:
                    raise SchemaError(
                        "Rel instance missing endpoint key props; "
                        "construct with schema/terms or use include_keys=False."
                    )
                data["sub_key"] = dict(self._sub_key_props)
                data["obj_key"] = dict(self._obj_key_props)
        if self.record_id is not None:
            data["record_id"] = self.record_id
        return data

    @staticmethod
    def from_dict(
        data: dict[str, object],
        *,
        registry: Optional[FactSchema] = None,
        strict: bool = True,
    ) -> "Instance":
        schema_id = data.get("schema_id")
        if not schema_id:
            raise SchemaError("Instance requires schema_id.")
        schema_id = str(schema_id)
        kind = data.get("kind")
        schema = None
        if registry is not None:
            schema = registry.get(schema_id)
            if kind is None:
                kind = schema.kind
            elif str(kind) != schema.kind:
                raise SchemaError(
                    f"Instance kind mismatch for {schema_id}: {kind} vs {schema.kind}"
                )
        if kind is None:
            raise SchemaError("Instance requires kind when registry is not provided.")
        if str(kind) not in {"fact", "rel"}:
            raise SchemaError(f"Instance kind must be 'fact' or 'rel': {kind}")
        props = data.get("props")
        if not isinstance(props, dict):
            raise SchemaError("Instance props must be a dict.")
        meta = _ensure_meta(data.get("meta") if isinstance(data, dict) else None)
        prob = data.get("prob")
        _validate_prob(prob)
        entity_id = data.get("entity_id")
        sub_entity_id = data.get("sub_entity_id")
        obj_entity_id = data.get("obj_entity_id")
        record_id = data.get("record_id")
        instance = object.__new__(Instance)
        object.__setattr__(instance, "schema_id", schema_id)
        object.__setattr__(instance, "kind", str(kind))
        object.__setattr__(instance, "props", dict(props))
        object.__setattr__(instance, "prob", prob)
        object.__setattr__(instance, "meta", meta)
        object.__setattr__(instance, "entity_id", entity_id if kind == "fact" else None)
        object.__setattr__(instance, "sub_entity_id", sub_entity_id if kind == "rel" else None)
        object.__setattr__(instance, "obj_entity_id", obj_entity_id if kind == "rel" else None)
        object.__setattr__(instance, "record_id", record_id)
        object.__setattr__(instance, "_sub_key_props", None)
        object.__setattr__(instance, "_obj_key_props", None)
        if kind == "fact":
            if not entity_id:
                raise SchemaError("Fact instance requires entity_id.")
            if schema is not None and schema.merge_policy == "keep_all" and not record_id:
                object.__setattr__(
                    instance,
                    "record_id",
                    _compute_record_id(schema_id, [entity_id], dict(props), meta),
                )
        else:
            if not sub_entity_id or not obj_entity_id:
                raise SchemaError("Rel instance requires sub_entity_id and obj_entity_id.")
            if schema is not None and schema.merge_policy == "keep_all" and not record_id:
                object.__setattr__(
                    instance,
                    "record_id",
                    _compute_record_id(schema_id, [str(sub_entity_id), str(obj_entity_id)], dict(props), meta),
                )
        if strict and registry is not None:
            schema = registry.get(schema_id)
            if kind == "fact":
                keys = list(schema.key_fields or [])
                for key in keys:
                    if key not in props:
                        raise SchemaError(f"Fact instance missing key field: {key}")
            else:
                if schema.endpoints is None:
                    raise SchemaError("Rel schema missing endpoints.")
        return instance

    def to_terms(self, schema: PredicateSchema) -> list[object]:
        if schema.schema_id != self.schema_id:
            raise SchemaError("Schema mismatch for instance terms rendering.")
        if schema.kind == "fact":
            terms: list[object] = []
            for arg in schema.signature:
                if arg.name not in self.props:
                    raise SchemaError(f"Missing fact prop: {arg.name}")
                terms.append(self.props[arg.name])
            return terms
        if self._sub_key_props is None or self._obj_key_props is None:
            raise SchemaError("Rel instance missing endpoint key props for term rendering.")
        terms = []
        for arg in schema.signature:
            if arg.role == "sub_key":
                key_name = arg.name[4:] if arg.name.startswith("sub_") else arg.name
                if key_name not in self._sub_key_props:
                    raise SchemaError(f"Missing sub key prop: {key_name}")
                terms.append(self._sub_key_props[key_name])
            elif arg.role == "obj_key":
                key_name = arg.name[4:] if arg.name.startswith("obj_") else arg.name
                if key_name not in self._obj_key_props:
                    raise SchemaError(f"Missing obj key prop: {key_name}")
                terms.append(self._obj_key_props[key_name])
            else:
                if arg.name not in self.props:
                    raise SchemaError(f"Missing rel prop: {arg.name}")
                terms.append(self.props[arg.name])
        return terms

    def _parse_fact_terms(
        self,
        schema: PredicateSchema,
        terms: list[object] | tuple[object, ...] | dict[str, object],
        *,
        strict: bool,
    ) -> dict[str, object]:
        signature_names = [arg.name for arg in schema.signature]
        if isinstance(terms, (list, tuple)):
            if strict and len(terms) != len(signature_names):
                raise SchemaError(
                    f"Fact terms length mismatch for {schema.name}: expected {len(signature_names)}"
                )
            if len(terms) != len(signature_names):
                raise SchemaError("Fact terms list must match signature length.")
            return {name: value for name, value in zip(signature_names, terms)}
        if isinstance(terms, dict):
            props: dict[str, object] = {}
            for key, value in terms.items():
                key_name = str(key)
                if strict and key_name not in signature_names:
                    raise SchemaError(f"Unknown fact prop: {key_name}")
                props[key_name] = value
            key_fields = list(schema.key_fields or [])
            missing = [key for key in key_fields if key not in props]
            if missing:
                raise SchemaError(f"Fact terms missing key fields: {missing}")
            return props
        raise SchemaError("Fact terms must be list/tuple or dict.")

    def _parse_rel_terms(
        self,
        schema: PredicateSchema,
        terms: list[object] | tuple[object, ...] | dict[str, object],
        *,
        strict: bool,
        resolve_mode: str,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], str, str]:
        endpoints = schema.endpoints or {}
        sub_key_fields = list(endpoints.get("sub_key_fields", []))
        obj_key_fields = list(endpoints.get("obj_key_fields", []))
        prop_names = [arg.name for arg in (schema.props or [])]
        if isinstance(terms, (list, tuple)):
            if len(terms) < 2:
                raise SchemaError("Rel terms must include sub and obj endpoints.")
            sub_term = terms[0]
            obj_term = terms[1]
            prop_terms = list(terms[2:])
            if strict and len(prop_terms) != len(prop_names):
                raise SchemaError(
                    f"Rel props length mismatch for {schema.name}: expected {len(prop_names)}"
                )
            if len(prop_terms) != len(prop_names):
                raise SchemaError("Rel props length must match schema props length.")
            rel_props = {name: value for name, value in zip(prop_names, prop_terms)}
            sub_props, sub_id = self._resolve_endpoint(
                sub_term,
                schema.sub_schema_id or "",
                sub_key_fields,
                prefix="sub_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            obj_props, obj_id = self._resolve_endpoint(
                obj_term,
                schema.obj_schema_id or "",
                obj_key_fields,
                prefix="obj_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            return sub_props, obj_props, rel_props, sub_id, obj_id
        if isinstance(terms, dict):
            return self._parse_rel_terms_dict(
                schema,
                terms,
                sub_key_fields=sub_key_fields,
                obj_key_fields=obj_key_fields,
                prop_names=prop_names,
                strict=strict,
                resolve_mode=resolve_mode,
            )
        raise SchemaError("Rel terms must be list/tuple or dict.")

    def _parse_rel_terms_dict(
        self,
        schema: PredicateSchema,
        terms: dict[str, object],
        *,
        sub_key_fields: list[str],
        obj_key_fields: list[str],
        prop_names: list[str],
        strict: bool,
        resolve_mode: str,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], str, str]:
        if "sub_ref" in terms or "obj_ref" in terms:
            sub_ref = terms.get("sub_ref")
            obj_ref = terms.get("obj_ref")
            if sub_ref is None or obj_ref is None:
                raise SchemaError("Rel dict terms require sub_ref and obj_ref.")
            rel_props_raw: dict[str, object] = {}
            inline_props = {
                key: value
                for key, value in terms.items()
                if key not in {"sub_ref", "obj_ref", "props"}
            }
            if "props" in terms:
                props_value = terms.get("props")
                if not isinstance(props_value, dict):
                    raise SchemaError("Rel props must be a dict.")
                rel_props_raw = dict(props_value)
            overlap = set(inline_props).intersection(rel_props_raw)
            if overlap:
                raise SchemaError(f"Rel props duplicated in inline/props: {sorted(overlap)}")
            rel_props = {**inline_props, **rel_props_raw}
            if strict:
                unknown = [k for k in rel_props if k not in prop_names]
                if unknown:
                    raise SchemaError(f"Unknown rel props: {unknown}")
                missing = [k for k in prop_names if k not in rel_props]
                if missing:
                    raise SchemaError(f"Missing rel props: {missing}")
            sub_props, sub_id = self._resolve_endpoint(
                sub_ref,
                schema.sub_schema_id or "",
                sub_key_fields,
                prefix="sub_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            obj_props, obj_id = self._resolve_endpoint(
                obj_ref,
                schema.obj_schema_id or "",
                obj_key_fields,
                prefix="obj_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            return sub_props, obj_props, rel_props, sub_id, obj_id
        if "sub_key" in terms or "obj_key" in terms:
            sub_key = terms.get("sub_key")
            obj_key = terms.get("obj_key")
            if not isinstance(sub_key, dict) or not isinstance(obj_key, dict):
                raise SchemaError("Rel dict terms require sub_key and obj_key dicts.")
            inline_props = {
                key: value
                for key, value in terms.items()
                if key not in {"sub_key", "obj_key", "props"}
            }
            rel_props_raw = terms.get("props", {})
            if not isinstance(rel_props_raw, dict):
                raise SchemaError("Rel props must be a dict.")
            overlap = set(inline_props).intersection(rel_props_raw)
            if overlap:
                raise SchemaError(f"Rel props duplicated in inline/props: {sorted(overlap)}")
            rel_props = {**inline_props, **rel_props_raw}
            if strict:
                unknown = [k for k in rel_props if k not in prop_names]
                if unknown:
                    raise SchemaError(f"Unknown rel props: {unknown}")
                missing = [k for k in prop_names if k not in rel_props]
                if missing:
                    raise SchemaError(f"Missing rel props: {missing}")
            sub_props, sub_id = self._resolve_endpoint(
                sub_key,
                schema.sub_schema_id or "",
                sub_key_fields,
                prefix="sub_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            obj_props, obj_id = self._resolve_endpoint(
                obj_key,
                schema.obj_schema_id or "",
                obj_key_fields,
                prefix="obj_",
                resolve_mode=resolve_mode,
                strict=strict,
            )
            return sub_props, obj_props, rel_props, sub_id, obj_id

        sub_props: dict[str, object] = {}
        obj_props: dict[str, object] = {}
        rel_props: dict[str, object] = {}
        for key, value in terms.items():
            key_name = str(key)
            if key_name in prop_names:
                rel_props[key_name] = value
                continue
            if key_name in sub_key_fields and key_name in obj_key_fields:
                raise SchemaError(f"Ambiguous rel endpoint key: {key_name}")
            if key_name in sub_key_fields:
                sub_props[key_name] = value
                continue
            if key_name in obj_key_fields:
                obj_props[key_name] = value
                continue
            if key_name.startswith("sub_") and key_name[4:] in sub_key_fields:
                sub_props[key_name[4:]] = value
                continue
            if key_name.startswith("obj_") and key_name[4:] in obj_key_fields:
                obj_props[key_name[4:]] = value
                continue
            if strict:
                raise SchemaError(f"Unknown rel field: {key_name}")
            rel_props[key_name] = value

        if strict:
            missing = [k for k in prop_names if k not in rel_props]
            if missing:
                raise SchemaError(f"Missing rel props: {missing}")

        sub_props, sub_id = self._resolve_endpoint(
            sub_props,
            schema.sub_schema_id or "",
            sub_key_fields,
            prefix="sub_",
            resolve_mode=resolve_mode,
            strict=strict,
        )
        obj_props, obj_id = self._resolve_endpoint(
            obj_props,
            schema.obj_schema_id or "",
            obj_key_fields,
            prefix="obj_",
            resolve_mode=resolve_mode,
            strict=strict,
        )
        return sub_props, obj_props, rel_props, sub_id, obj_id

    def _resolve_endpoint(
        self,
        term: object,
        schema_id: str,
        key_fields: list[str],
        *,
        prefix: str,
        resolve_mode: str,
        strict: bool,
    ) -> tuple[dict[str, object], str]:
        if isinstance(term, Instance):
            if term.kind != "fact":
                raise SchemaError("Rel endpoint must be a fact instance.")
            if term.schema_id != schema_id:
                raise SchemaError("Rel endpoint schema_id mismatch.")
            if term.entity_id is None:
                raise SchemaError("Rel endpoint instance missing entity_id.")
            key_props = {k: term.props[k] for k in key_fields if k in term.props}
            if strict and len(key_props) < len(key_fields):
                raise SchemaError("Rel endpoint instance missing key fields.")
            return key_props, term.entity_id
        if isinstance(term, InstanceRef):
            if term.schema_id != schema_id:
                raise SchemaError("Rel endpoint InstanceRef schema_id mismatch.")
            key_props = dict(term.key_values)
            key_props = _normalize_keys(key_props, prefix=prefix)
            missing = [key for key in key_fields if key not in key_props]
            if missing:
                raise SchemaError(f"Rel endpoint missing key fields: {missing}")
            return key_props, _compute_entity_id(schema_id, key_fields, key_props)
        if isinstance(term, dict):
            key_props = _normalize_keys(term, prefix=prefix)
            missing = [key for key in key_fields if key not in key_props]
            if missing:
                raise SchemaError(f"Rel endpoint missing key fields: {missing}")
            return key_props, _compute_entity_id(schema_id, key_fields, key_props)
        if resolve_mode == "heuristic" and len(key_fields) == 1:
            key_props = {key_fields[0]: term}
            return key_props, _compute_entity_id(schema_id, key_fields, key_props)
        raise SchemaError("Rel endpoint must be Instance, InstanceRef, or key dict.")
