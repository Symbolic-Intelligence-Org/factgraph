"""PyReason engine-specific write session.

Validates facts against shared schema_ir, handles engine-specific
parameters (bound, active_from/to), and records compat confidence
for audit-facing shared metadata.

This is an engine-specific write path per ADR-14a. It does NOT
go through ``write_runtime_fact`` or ``write_protocol``.

Entity-level batch API (2026-03-26):
    with session.batch() as tx:
        alice = tx.entity(User, user_id="Alice")
        alice.name.set("Alice", bound=[1.0, 1.0])
        tx.relationship(
            Friends,
            from_entity=alice,
            to_entity=bob,
            strength="0.9",
            bound=[0.9, 0.9],
        )
        tx.commit()
"""
from __future__ import annotations

from typing import Any


def _owner_prefix(entity_type: str) -> str:
    """Convert CamelCase declaration names to snake_case predicate prefixes."""
    if not entity_type:
        return entity_type
    out: list[str] = []
    for idx, ch in enumerate(entity_type):
        if ch.isupper() and idx > 0 and (
            (idx + 1 < len(entity_type) and entity_type[idx + 1].islower())
            or entity_type[idx - 1].islower()
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


_ANNOTATION_SOURCE_KEYS = ("source", "analyst", "method")


def _generate_annotation_templates(
    fact_index: int,
    fact_kind: str,
    bound: tuple[float, float],
    active_from: int,
    active_to: int | None,
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate annotation-ready dicts for a single buffered fact."""
    lo, hi = bound
    templates: list[dict[str, Any]] = [
        {
            "asrt_id": "",
            "fact_index": fact_index,
            "fact_kind": fact_kind,
            "namespace": "pyreason",
            "category": "semantic",
            "key": "bound_lower",
            "kind": "float",
            "value": lo,
            "origin": "observed",
            "derivation": None,
        },
        {
            "asrt_id": "",
            "fact_index": fact_index,
            "fact_kind": fact_kind,
            "namespace": "pyreason",
            "category": "semantic",
            "key": "bound_upper",
            "kind": "float",
            "value": hi,
            "origin": "observed",
            "derivation": None,
        },
        {
            "asrt_id": "",
            "fact_index": fact_index,
            "fact_kind": fact_kind,
            "namespace": "shared",
            "category": "derived",
            "key": "confidence",
            "kind": "float",
            "value": lo,
            "origin": "derived",
            "derivation": "pyreason:lower_bound",
        },
        {
            "asrt_id": "",
            "fact_index": fact_index,
            "fact_kind": fact_kind,
            "namespace": "shared",
            "category": "derived",
            "key": "confidence_source",
            "kind": "str",
            "value": "pyreason:lower_bound",
            "origin": "derived",
            "derivation": "pyreason:lower_bound",
        },
    ]
    if active_from != 0:
        templates.append(
            {
                "asrt_id": "",
                "fact_index": fact_index,
                "fact_kind": fact_kind,
                "namespace": "pyreason",
                "category": "semantic",
                "key": "active_from",
                "kind": "int",
                "value": active_from,
                "origin": "observed",
                "derivation": None,
            }
        )
    if active_to is not None:
        templates.append(
            {
                "asrt_id": "",
                "fact_index": fact_index,
                "fact_kind": fact_kind,
                "namespace": "pyreason",
                "category": "semantic",
                "key": "active_to",
                "kind": "int",
                "value": active_to,
                "origin": "observed",
                "derivation": None,
            }
        )
    for meta_key in _ANNOTATION_SOURCE_KEYS:
        value = meta.get(meta_key)
        if value is None:
            continue
        templates.append(
            {
                "asrt_id": "",
                "fact_index": fact_index,
                "fact_kind": fact_kind,
                "namespace": "shared",
                "category": "source",
                "key": meta_key,
                "kind": "str",
                "value": value,
                "origin": "observed",
                "derivation": None,
            }
        )
    return templates


class PyReasonFieldHandle:
    """Proxy for field mutations on a managed entity."""

    __slots__ = ("_tx", "_entity_handle", "_field_name", "_pred_id")

    def __init__(
        self,
        tx: PyReasonBatchTx,
        entity_handle: PyReasonEntityHandle,
        field_name: str,
        pred_id: str,
    ) -> None:
        self._tx = tx
        self._entity_handle = entity_handle
        self._field_name = field_name
        self._pred_id = pred_id

    def set(
        self,
        value: str,
        *,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> PyReasonEntityHandle:
        """Set a field value using PyReason-specific parameters."""
        self._tx._session._write_node_fact_internal(
            self._pred_id,
            self._entity_handle._node_ref,
            value,
            bound=bound,
            active_from=active_from,
            active_to=active_to,
            meta=meta,
        )
        return self._entity_handle


class PyReasonEntityHandle:
    """Managed handle for an entity in a batch transaction."""

    __slots__ = (
        "_tx",
        "_entity_cls",
        "_entity_type",
        "_node_ref",
        "_owner_prefix",
        "_field_pred_ids",
        "_identity_values",
        "_field_handles",
    )

    def __init__(
        self,
        tx: PyReasonBatchTx,
        entity_cls: type,
        entity_type: str,
        node_ref: str,
        owner_prefix: str,
        field_pred_ids: dict[str, str],
        identity_values: dict[str, Any],
    ) -> None:
        self._tx = tx
        self._entity_cls = entity_cls
        self._entity_type = entity_type
        self._node_ref = node_ref
        self._owner_prefix = owner_prefix
        self._field_pred_ids = field_pred_ids
        self._identity_values = identity_values
        self._field_handles: dict[str, PyReasonFieldHandle] = {}

    def __getattr__(self, name: str) -> PyReasonFieldHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        cached = self._field_handles.get(name)
        if cached is not None:
            return cached
        pred_id = self._field_pred_ids.get(name)
        if pred_id is None:
            raise AttributeError(
                f"'{self._entity_cls.__name__}' has no field '{name}'. "
                f"Available: {sorted(self._field_pred_ids.keys())}"
            )
        handle = PyReasonFieldHandle(self._tx, self, name, pred_id)
        self._field_handles[name] = handle
        return handle


class PyReasonBatchTx:
    """Batch transaction for entity-level fact writing."""

    __slots__ = ("_session", "_entity_handles")

    def __init__(self, session: PyReasonSession) -> None:
        self._session = session
        self._entity_handles: dict[tuple[str, str], PyReasonEntityHandle] = {}

    def entity(self, entity_cls: type, **identity_values: Any) -> PyReasonEntityHandle:
        """Create or reuse an entity handle."""
        spec = getattr(entity_cls, "__sdk_entity_spec__", None)
        if spec is None:
            raise ValueError(
                f"{entity_cls.__name__} is not an Entity class "
                f"(missing __sdk_entity_spec__)"
            )
        entity_type = str(spec["entity_type"])
        prefix = _owner_prefix(entity_type)
        if not identity_values:
            raise ValueError(
                f"entity() requires at least one identity value for {entity_type}"
            )

        identity_order = [
            row["name"]
            for row in spec.get("identity_fields", [])
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        ]
        ordered_values: list[str] = []
        for field_name in identity_order:
            if field_name not in identity_values:
                continue
            ordered_values.append(str(identity_values[field_name]))
        if not ordered_values:
            ordered_values = [str(v) for _, v in identity_values.items()]
        node_ref = ordered_values[0] if len(ordered_values) == 1 else "_".join(ordered_values)

        handle_key = (entity_type, node_ref)
        existing = self._entity_handles.get(handle_key)
        if existing is not None:
            return existing

        field_pred_ids: dict[str, str] = {}
        for field_spec in spec.get("fields", []):
            if not isinstance(field_spec, dict):
                continue
            py_name = field_spec.get("py_name")
            if not isinstance(py_name, str):
                continue
            pred_id = f"{prefix}:{py_name}"
            if pred_id in self._session._pred_ids and pred_id not in self._session._relationship_preds:
                field_pred_ids[py_name] = pred_id

        handle = PyReasonEntityHandle(
            self,
            entity_cls,
            entity_type,
            node_ref,
            prefix,
            field_pred_ids,
            dict(identity_values),
        )
        self._entity_handles[handle_key] = handle
        return handle

    def relationship(
        self,
        rel_cls: type,
        *,
        from_entity: PyReasonEntityHandle,
        to_entity: PyReasonEntityHandle,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
        **field_values: str,
    ) -> None:
        """Write relationship edge facts for each relationship field."""
        spec = getattr(rel_cls, "__sdk_relationship_spec__", None)
        if spec is None:
            raise ValueError(
                f"{rel_cls.__name__} is not a Relationship class "
                f"(missing __sdk_relationship_spec__)"
            )
        if not isinstance(from_entity, PyReasonEntityHandle):
            raise ValueError("from_entity must be a PyReasonEntityHandle")
        if not isinstance(to_entity, PyReasonEntityHandle):
            raise ValueError("to_entity must be a PyReasonEntityHandle")

        rel_type = str(spec["relationship_type"])
        prefix = _owner_prefix(rel_type)
        spec_fields = {
            field_spec["py_name"]
            for field_spec in spec.get("fields", [])
            if isinstance(field_spec, dict) and isinstance(field_spec.get("py_name"), str)
        }
        unknown = set(field_values.keys()) - spec_fields
        if unknown:
            raise ValueError(f"Unknown fields for {rel_type}: {sorted(unknown)}")

        for py_name, value in field_values.items():
            pred_id = f"{prefix}:{py_name}"
            if pred_id not in self._session._pred_ids:
                raise ValueError(f"pred_id '{pred_id}' not found in schema_ir")
            self._session._write_edge_fact_internal(
                pred_id,
                from_entity._node_ref,
                to_entity._node_ref,
                str(value),
                bound=bound,
                active_from=active_from,
                active_to=active_to,
                meta=meta,
            )

    def commit(self) -> None:
        """No-op: facts are staged immediately on each call."""

    def __enter__(self) -> PyReasonBatchTx:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None


class PyReasonSession:
    """Engine-specific fact write session for PyReason."""

    def __init__(self, schema_ir: dict[str, Any]) -> None:
        if not isinstance(schema_ir, dict):
            raise ValueError("schema_ir must be dict")
        self._schema_ir = schema_ir
        predicates = schema_ir.get("predicates", [])
        if not isinstance(predicates, list):
            raise ValueError("schema_ir.predicates must be list")
        self._pred_ids = {
            pred["pred_id"]
            for pred in predicates
            if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
        }
        self._relationship_preds = {
            pred["pred_id"]
            for pred in predicates
            if isinstance(pred, dict)
            and isinstance(pred.get("pred_id"), str)
            and pred.get("relationship_type")
        }
        self._node_facts: list[dict[str, Any]] = []
        self._edge_facts: list[dict[str, Any]] = []
        self._annotation_templates: list[dict[str, Any]] = []

    def batch(self) -> PyReasonBatchTx:
        """Create a batch transaction for entity-level fact writing."""
        return PyReasonBatchTx(self)

    def write_node_fact(
        self,
        pred_id: str,
        node_ref: str,
        value: str,
        *,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Backward-compatible public node-fact writer."""
        self._write_node_fact_internal(
            pred_id,
            node_ref,
            value,
            bound=bound,
            active_from=active_from,
            active_to=active_to,
            meta=meta,
        )

    def write_edge_fact(
        self,
        pred_id: str,
        from_ref: str,
        to_ref: str,
        value: str = "",
        *,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Backward-compatible public edge-fact writer."""
        self._write_edge_fact_internal(
            pred_id,
            from_ref,
            to_ref,
            value,
            bound=bound,
            active_from=active_from,
            active_to=active_to,
            meta=meta,
        )

    def _write_node_fact_internal(
        self,
        pred_id: str,
        node_ref: str,
        value: str,
        *,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Write a node-level fact (entity attribute)."""
        if pred_id not in self._pred_ids:
            raise ValueError(f"pred_id '{pred_id}' not found in schema_ir")
        if pred_id in self._relationship_preds:
            raise ValueError(
                f"pred_id '{pred_id}' is a relationship predicate; "
                f"use _write_edge_fact_internal"
            )
        if not isinstance(node_ref, str) or not node_ref:
            raise ValueError("node_ref must be non-empty string")
        if not isinstance(value, str):
            raise ValueError("value must be string")

        lo, hi = _validate_bound(bound)
        resolved_meta = _resolve_shared_meta(meta, lower_bound=lo)
        validated_from = _validate_active_from(active_from)
        validated_to = _validate_active_to(active_to)

        fact_index = len(self._node_facts)
        self._node_facts.append(
            {
                "pred_id": pred_id,
                "node_ref": node_ref,
                "value": value,
                "bound": (lo, hi),
                "active_from": validated_from,
                "active_to": validated_to,
                "meta": resolved_meta,
            }
        )
        self._annotation_templates.extend(
            _generate_annotation_templates(
                fact_index,
                "node",
                (lo, hi),
                validated_from,
                validated_to,
                resolved_meta,
            )
        )

    def _write_edge_fact_internal(
        self,
        pred_id: str,
        from_ref: str,
        to_ref: str,
        value: str = "",
        *,
        bound: tuple[float, float] | list[float] = (1.0, 1.0),
        active_from: int = 0,
        active_to: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Write an edge-level fact (relationship between entities)."""
        if pred_id not in self._pred_ids:
            raise ValueError(f"pred_id '{pred_id}' not found in schema_ir")
        if pred_id not in self._relationship_preds:
            raise ValueError(
                f"pred_id '{pred_id}' is not a relationship predicate; "
                f"use _write_node_fact_internal"
            )
        if not isinstance(from_ref, str) or not from_ref:
            raise ValueError("from_ref must be non-empty string")
        if not isinstance(to_ref, str) or not to_ref:
            raise ValueError("to_ref must be non-empty string")
        if not isinstance(value, str):
            raise ValueError("value must be string")

        lo, hi = _validate_bound(bound)
        resolved_meta = _resolve_shared_meta(meta, lower_bound=lo)
        validated_from = _validate_active_from(active_from)
        validated_to = _validate_active_to(active_to)

        fact_index = len(self._edge_facts)
        self._edge_facts.append(
            {
                "pred_id": pred_id,
                "from_ref": from_ref,
                "to_ref": to_ref,
                "value": value,
                "bound": (lo, hi),
                "active_from": validated_from,
                "active_to": validated_to,
                "meta": resolved_meta,
            }
        )
        self._annotation_templates.extend(
            _generate_annotation_templates(
                fact_index,
                "edge",
                (lo, hi),
                validated_from,
                validated_to,
                resolved_meta,
            )
        )

    @property
    def node_facts(self) -> list[dict[str, Any]]:
        return list(self._node_facts)

    @property
    def edge_facts(self) -> list[dict[str, Any]]:
        return list(self._edge_facts)

    @property
    def all_facts_meta(self) -> list[dict[str, Any]]:
        """Return audit-friendly metadata rows for all buffered facts."""
        result: list[dict[str, Any]] = []
        for fact in self._node_facts:
            result.append(
                {
                    "pred_id": fact["pred_id"],
                    "ref": fact["node_ref"],
                    "meta": dict(fact["meta"]),
                }
            )
        for fact in self._edge_facts:
            result.append(
                {
                    "pred_id": fact["pred_id"],
                    "ref": f"{fact['from_ref']}->{fact['to_ref']}",
                    "meta": dict(fact["meta"]),
                }
            )
        return result

    @property
    def annotation_templates(self) -> list[dict[str, Any]]:
        """Return annotation-ready dicts for all buffered facts."""
        return list(self._annotation_templates)


def _validate_bound(bound: tuple[float, float] | list[float]) -> tuple[float, float]:
    if isinstance(bound, (list, tuple)) and len(bound) == 2:
        lo, hi = float(bound[0]), float(bound[1])
        if not (0.0 <= lo <= 1.0) or not (0.0 <= hi <= 1.0):
            raise ValueError(f"bound values must be in [0, 1], got [{lo}, {hi}]")
        if lo > hi:
            raise ValueError(f"bound lower must be <= upper, got [{lo}, {hi}]")
        return (lo, hi)
    raise ValueError(f"bound must be [float, float], got {bound!r}")


def _validate_active_from(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("active_from must be non-negative int")
    return value


def _validate_active_to(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("active_to must be non-negative int or None")
    return value


def _resolve_shared_meta(meta: dict[str, Any] | None, *, lower_bound: float) -> dict[str, Any]:
    if meta is None:
        return {
            "confidence": lower_bound,
            "confidence_source": "pyreason:lower_bound",
        }
    if not isinstance(meta, dict):
        raise ValueError("meta must be dict when provided")

    resolved = dict(meta)
    confidence = resolved.get("confidence")
    if confidence is None:
        resolved["confidence"] = lower_bound
    else:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("meta['confidence'] must be float when provided")
        normalized = float(confidence)
        if not (0.0 < normalized <= 1.0):
            raise ValueError("meta['confidence'] must be in (0, 1]")
        resolved["confidence"] = normalized
    if "confidence_source" not in resolved:
        resolved["confidence_source"] = "meta:confidence" if confidence is not None else "pyreason:lower_bound"
    return resolved
