"""PyReason engine-specific write session.

Validates facts against shared schema_ir, handles engine-specific
parameters (bound, active_from/to), and records compat confidence
for audit-facing shared metadata.

This is an engine-specific write path per ADR-14a. It does NOT
go through ``write_runtime_fact`` or ``write_protocol``.
"""
from __future__ import annotations

from typing import Any


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
        """Write a node-level fact (entity attribute)."""
        if pred_id not in self._pred_ids:
            raise ValueError(f"pred_id '{pred_id}' not found in schema_ir")
        if pred_id in self._relationship_preds:
            raise ValueError(f"pred_id '{pred_id}' is a relationship predicate; use write_edge_fact")
        if not isinstance(node_ref, str) or not node_ref:
            raise ValueError("node_ref must be non-empty string")
        if not isinstance(value, str):
            raise ValueError("value must be string")

        lo, hi = _validate_bound(bound)
        resolved_meta = _resolve_shared_meta(meta, lower_bound=lo)

        self._node_facts.append(
            {
                "pred_id": pred_id,
                "node_ref": node_ref,
                "value": value,
                "bound": (lo, hi),
                "active_from": _validate_active_from(active_from),
                "active_to": _validate_active_to(active_to),
                "meta": resolved_meta,
            }
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
        """Write an edge-level fact (relationship between entities)."""
        if pred_id not in self._pred_ids:
            raise ValueError(f"pred_id '{pred_id}' not found in schema_ir")
        if pred_id not in self._relationship_preds:
            raise ValueError(f"pred_id '{pred_id}' is not a relationship predicate; use write_node_fact")
        if not isinstance(from_ref, str) or not from_ref:
            raise ValueError("from_ref must be non-empty string")
        if not isinstance(to_ref, str) or not to_ref:
            raise ValueError("to_ref must be non-empty string")
        if not isinstance(value, str):
            raise ValueError("value must be string")

        lo, hi = _validate_bound(bound)
        resolved_meta = _resolve_shared_meta(meta, lower_bound=lo)

        self._edge_facts.append(
            {
                "pred_id": pred_id,
                "from_ref": from_ref,
                "to_ref": to_ref,
                "value": value,
                "bound": (lo, hi),
                "active_from": _validate_active_from(active_from),
                "active_to": _validate_active_to(active_to),
                "meta": resolved_meta,
            }
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
        return {"confidence": lower_bound}
    if not isinstance(meta, dict):
        raise ValueError("meta must be dict when provided")

    resolved = dict(meta)
    confidence = resolved.get("confidence")
    if confidence is None:
        resolved["confidence"] = lower_bound
        return resolved
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("meta['confidence'] must be float when provided")
    normalized = float(confidence)
    if not (0.0 < normalized <= 1.0):
        raise ValueError("meta['confidence'] must be in (0, 1]")
    resolved["confidence"] = normalized
    return resolved
