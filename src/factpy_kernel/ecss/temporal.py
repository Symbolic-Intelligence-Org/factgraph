from __future__ import annotations

import copy
from typing import Any


class EcssTemporalError(Exception):
    pass


_ECSS_TEMPORAL_OWNER_TYPE = "ecss_temporal_anchor"

ECSS_OBLIGATION_TIMESTAMP_PRED_ID = "ecss:obligation_timestamp"
ECSS_WINDOW_START_PRED_ID = "ecss:window_start"
ECSS_WINDOW_END_PRED_ID = "ecss:window_end"
ECSS_INTERVAL_START_PRED_ID = "ecss:interval_start"
ECSS_INTERVAL_END_PRED_ID = "ecss:interval_end"

ECSS_TEMPORAL_PRED_IDS = (
    ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
    ECSS_WINDOW_START_PRED_ID,
    ECSS_WINDOW_END_PRED_ID,
    ECSS_INTERVAL_START_PRED_ID,
    ECSS_INTERVAL_END_PRED_ID,
)


def ecss_temporal_predicates() -> list[dict[str, Any]]:
    return [
        {
            "pred_id": ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
            "owner_type": _ECSS_TEMPORAL_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "anchor_ref", "type_domain": "entity_ref"},
                {"name": "timestamp", "type_domain": "time"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_WINDOW_START_PRED_ID,
            "owner_type": _ECSS_TEMPORAL_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "anchor_ref", "type_domain": "entity_ref"},
                {"name": "window_start", "type_domain": "time"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_WINDOW_END_PRED_ID,
            "owner_type": _ECSS_TEMPORAL_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "anchor_ref", "type_domain": "entity_ref"},
                {"name": "window_end", "type_domain": "time"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_INTERVAL_START_PRED_ID,
            "owner_type": _ECSS_TEMPORAL_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "anchor_ref", "type_domain": "entity_ref"},
                {"name": "interval_start", "type_domain": "time"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_INTERVAL_END_PRED_ID,
            "owner_type": _ECSS_TEMPORAL_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "anchor_ref", "type_domain": "entity_ref"},
                {"name": "interval_end", "type_domain": "time"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
    ]


def extend_schema_ir_with_ecss_temporal_predicates(schema_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema_ir, dict):
        raise EcssTemporalError("schema_ir must be dict")

    predicates = schema_ir.get("predicates")
    projection = schema_ir.get("projection")
    if not isinstance(predicates, list):
        raise EcssTemporalError("schema_ir.predicates must be list")
    if not isinstance(projection, dict):
        raise EcssTemporalError("schema_ir.projection must be object")
    projection_predicates = projection.get("predicates")
    if not isinstance(projection_predicates, list):
        raise EcssTemporalError("schema_ir.projection.predicates must be list")

    out = copy.deepcopy(schema_ir)
    out_predicates = out["predicates"]
    out_projection_predicates = out["projection"]["predicates"]

    existing_pred_ids = {
        pred.get("pred_id")
        for pred in out_predicates
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
    }
    for predicate in ecss_temporal_predicates():
        pred_id = predicate["pred_id"]
        if pred_id not in existing_pred_ids:
            out_predicates.append(predicate)
            existing_pred_ids.add(pred_id)
        if pred_id not in out_projection_predicates:
            out_projection_predicates.append(pred_id)
    return out


__all__ = [
    "ECSS_OBLIGATION_TIMESTAMP_PRED_ID",
    "ECSS_WINDOW_START_PRED_ID",
    "ECSS_WINDOW_END_PRED_ID",
    "ECSS_INTERVAL_START_PRED_ID",
    "ECSS_INTERVAL_END_PRED_ID",
    "ECSS_TEMPORAL_PRED_IDS",
    "EcssTemporalError",
    "ecss_temporal_predicates",
    "extend_schema_ir_with_ecss_temporal_predicates",
]
