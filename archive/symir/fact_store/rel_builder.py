"""Relation instance builder with fact matching."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Literal, Optional

from symir.errors import SchemaError
from symir.ir.fact_schema import Rel, FactSchema
from symir.ir.instance import Instance


ROW_PROB_KEY = "__prob__"
_ROW_PROB_KEY = ROW_PROB_KEY


@dataclass(frozen=True)
class RelBuilder:
    rel: Rel
    match_keys: list[str] | dict[str, dict[str, str]] | None = None
    match_props: list[str] | Literal["all"] | None = None
    key_mode: Literal["strict", "partial"] = "strict"
    multi: Literal["error", "cartesian"] = "error"

    def build(
        self,
        *,
        facts: Iterable[Instance],
        rows: Iterable[dict[str, object]],
        registry: Optional[FactSchema] = None,
        datatype_cast: Literal["none", "coerce", "strict"] = "none",
    ) -> list[Instance]:
        if self.key_mode not in {"strict", "partial"}:
            raise SchemaError("key_mode must be 'strict' or 'partial'.")
        if self.multi not in {"error", "cartesian"}:
            raise SchemaError("multi must be 'error' or 'cartesian'.")

        rel = self.rel
        sub_schema_id = rel.sub_schema_id
        obj_schema_id = rel.obj_schema_id
        if not sub_schema_id or not obj_schema_id:
            raise SchemaError("RelBuilder requires rel with sub/obj schema_id.")

        sub_key_fields = list(rel.endpoints.get("sub_key_fields", []) if rel.endpoints else [])
        obj_key_fields = list(rel.endpoints.get("obj_key_fields", []) if rel.endpoints else [])
        prop_specs = list(rel.props or [])
        prop_names = [spec.name for spec in prop_specs if spec.name]

        match_map = self._normalize_match_keys(
            sub_key_fields=sub_key_fields,
            obj_key_fields=obj_key_fields,
        )

        sub_facts = [fact for fact in facts if fact.kind == "fact" and fact.schema_id == sub_schema_id]
        obj_facts = [fact for fact in facts if fact.kind == "fact" and fact.schema_id == obj_schema_id]
        for fact in sub_facts + obj_facts:
            if fact.entity_id is None:
                raise SchemaError("Fact instance missing entity_id; cannot build relations.")

        sub_index = self._build_index(sub_facts, sub_key_fields)
        obj_index = self._build_index(obj_facts, obj_key_fields)

        sub_types = self._resolve_key_types(registry, sub_schema_id, sub_key_fields)
        obj_types = self._resolve_key_types(registry, obj_schema_id, obj_key_fields)
        prop_types = {spec.name: spec.datatype for spec in prop_specs if spec.name}

        instances: list[Instance] = []
        seen: set[tuple[object, ...]] = set()

        for row in rows:
            if not isinstance(row, dict):
                raise SchemaError("RelBuilder rows must be dicts.")
            row_prob = row.get(_ROW_PROB_KEY)

            sub_keys = self._extract_keys(
                row,
                match_map["sub"],
                sub_key_fields,
                datatype_cast=datatype_cast,
                datatypes=sub_types,
            )
            obj_keys = self._extract_keys(
                row,
                match_map["obj"],
                obj_key_fields,
                datatype_cast=datatype_cast,
                datatypes=obj_types,
            )

            if self.key_mode == "strict":
                missing_sub = [k for k in sub_key_fields if k not in sub_keys]
                missing_obj = [k for k in obj_key_fields if k not in obj_keys]
                if missing_sub or missing_obj:
                    messages: list[str] = []
                    if missing_sub:
                        messages.append(f"Missing sub key fields in row: {missing_sub}")
                    if missing_obj:
                        messages.append(f"Missing obj key fields in row: {missing_obj}")
                    raise SchemaError("; ".join(messages))
            else:
                if not sub_keys or not obj_keys:
                    # No usable keys; skip in partial mode to avoid cartesian explosion.
                    continue

            sub_matches = self._match_facts(sub_index, sub_facts, sub_key_fields, sub_keys)
            obj_matches = self._match_facts(obj_index, obj_facts, obj_key_fields, obj_keys)

            if not sub_matches or not obj_matches:
                if self.key_mode == "strict":
                    raise SchemaError("No matching facts for relation endpoints.")
                continue

            if self.multi == "error":
                if len(sub_matches) != 1 or len(obj_matches) != 1:
                    raise SchemaError("Multiple matches found; use multi='cartesian' to allow.")
                pairs = [(sub_matches[0], obj_matches[0])]
            else:
                pairs = list(product(sub_matches, obj_matches))

            rel_props = self._extract_props(
                row,
                prop_names,
                datatype_cast=datatype_cast,
                datatypes=prop_types,
            )

            for sub_fact, obj_fact in pairs:
                if self.match_props is not None:
                    key = self._relation_key(
                        sub_fact.entity_id,
                        obj_fact.entity_id,
                        rel_props,
                        match_props=self.match_props,
                        prop_names=prop_names,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                instances.append(
                    Instance(
                        schema=rel,
                        terms={
                            "sub_ref": sub_fact,
                            "obj_ref": obj_fact,
                            "props": rel_props,
                        },
                        prob=row_prob if isinstance(row_prob, (int, float)) else None,
                    )
                )

        return instances

    def _normalize_match_keys(
        self,
        *,
        sub_key_fields: list[str],
        obj_key_fields: list[str],
    ) -> dict[str, dict[str, str]]:
        if self.match_keys is None:
            return {
                "sub": {key: f"sub_{key}" for key in sub_key_fields},
                "obj": {key: f"obj_{key}" for key in obj_key_fields},
            }
        if isinstance(self.match_keys, list):
            if len(sub_key_fields) != 1 or len(obj_key_fields) != 1:
                raise SchemaError("match_keys list requires single key per endpoint.")
            if len(self.match_keys) != 2:
                raise SchemaError("match_keys list must have two items (sub, obj).")
            sub_key = self._parse_key_spec(self.match_keys[0], sub_key_fields[0])
            obj_key = self._parse_key_spec(self.match_keys[1], obj_key_fields[0])
            return {"sub": {sub_key_fields[0]: sub_key}, "obj": {obj_key_fields[0]: obj_key}}
        if isinstance(self.match_keys, dict):
            sub_map = self.match_keys.get("sub")
            obj_map = self.match_keys.get("obj")
            if not isinstance(sub_map, dict) or not isinstance(obj_map, dict):
                raise SchemaError("match_keys dict must have 'sub'/'obj' dict mappings.")
            return {"sub": dict(sub_map), "obj": dict(obj_map)}
        raise SchemaError("match_keys must be list, dict, or None.")

    def _parse_key_spec(self, spec: str, default_field: str) -> str:
        if ":" in spec:
            row_key, key_field = (part.strip() for part in spec.split(":", 1))
            if key_field and key_field != default_field:
                raise SchemaError(
                    f"match_keys spec key_field mismatch: {key_field} vs {default_field}"
                )
            return row_key
        return spec

    def _build_index(
        self,
        facts: list[Instance],
        key_fields: list[str],
    ) -> dict[tuple[object, ...], list[Instance]]:
        index: dict[tuple[object, ...], list[Instance]] = {}
        for fact in facts:
            key = tuple(fact.props.get(field) for field in key_fields)
            index.setdefault(key, []).append(fact)
        return index

    def _match_facts(
        self,
        index: dict[tuple[object, ...], list[Instance]],
        facts: list[Instance],
        key_fields: list[str],
        key_values: dict[str, object],
    ) -> list[Instance]:
        if self.key_mode == "strict":
            key = tuple(key_values[field] for field in key_fields)
            return list(index.get(key, []))
        matches: list[Instance] = []
        for fact in facts:
            ok = True
            for field, value in key_values.items():
                if fact.props.get(field) != value:
                    ok = False
                    break
            if ok:
                matches.append(fact)
        return matches

    def _extract_keys(
        self,
        row: dict[str, object],
        mapping: dict[str, str],
        key_fields: list[str],
        *,
        datatype_cast: Literal["none", "coerce", "strict"],
        datatypes: dict[str, str],
    ) -> dict[str, object]:
        keys: dict[str, object] = {}
        for field in key_fields:
            row_key = mapping.get(field)
            if not row_key or row_key not in row:
                continue
            value = row[row_key]
            keys[field] = self._cast_value(value, datatypes.get(field), datatype_cast)
        return keys

    def _extract_props(
        self,
        row: dict[str, object],
        prop_names: list[str],
        *,
        datatype_cast: Literal["none", "coerce", "strict"],
        datatypes: dict[str, str],
    ) -> dict[str, object]:
        props: dict[str, object] = {}
        for name in prop_names:
            if name not in row:
                raise SchemaError(f"Missing rel prop value in row: {name}")
            props[name] = self._cast_value(row[name], datatypes.get(name), datatype_cast)
        return props

    def _relation_key(
        self,
        sub_id: object,
        obj_id: object,
        props: dict[str, object],
        *,
        match_props: list[str] | Literal["all"],
        prop_names: list[str],
    ) -> tuple[object, ...]:
        if match_props == "all":
            keys = prop_names
        else:
            keys = list(match_props)
        return (sub_id, obj_id, *[props.get(name) for name in keys])

    def _resolve_key_types(
        self,
        registry: Optional[FactSchema],
        schema_id: str,
        key_fields: list[str],
    ) -> dict[str, str]:
        if registry is None:
            return {}
        schema = registry.get(schema_id)
        return {
            arg.name: arg.datatype
            for arg in schema.signature
            if arg.name in key_fields
        }

    def _cast_value(
        self,
        value: object,
        datatype: Optional[str],
        mode: Literal["none", "coerce", "strict"],
    ) -> object:
        if mode == "none":
            return value
        if datatype is None:
            if mode == "strict":
                raise SchemaError("Missing datatype for strict casting.")
            return value
        dtype = datatype.strip().lower()
        if dtype == "string":
            return str(value)
        if dtype == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                if mode == "strict":
                    raise SchemaError(f"Invalid int value: {value}")
                return value
        if dtype == "float":
            try:
                return float(value)
            except (TypeError, ValueError):
                if mode == "strict":
                    raise SchemaError(f"Invalid float value: {value}")
                return value
        if dtype == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in {"true", "1", "yes"}:
                    return True
                if lowered in {"false", "0", "no"}:
                    return False
            if mode == "strict":
                raise SchemaError(f"Invalid bool value: {value}")
            return value
        if mode == "strict":
            raise SchemaError(f"Unsupported datatype for casting: {datatype}")
        return value
