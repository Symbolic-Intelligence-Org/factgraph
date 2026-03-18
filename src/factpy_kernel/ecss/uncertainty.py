from __future__ import annotations

import copy
from typing import Any


class EcssUncertaintyError(Exception):
    pass


_ECSS_UNCERTAINTY_OWNER_TYPE = "ecss_uncertainty_anchor"

ECSS_COLLISION_PROBABILITY_PPM_PRED_ID = "ecss:collision_probability_ppm"
ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID = "ecss:collision_probability_threshold_ppm"
ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID = "ecss:disposal_success_probability_ppm"
ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID = "ecss:disposal_success_threshold_ppm"

ECSS_UNCERTAINTY_PRED_IDS = (
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
)


def ecss_uncertainty_predicates() -> list[dict[str, Any]]:
    return [
        {
            "pred_id": ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
            "owner_type": _ECSS_UNCERTAINTY_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "assessment_ref", "type_domain": "entity_ref"},
                {"name": "probability_ppm", "type_domain": "int"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
            "owner_type": _ECSS_UNCERTAINTY_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "assessment_ref", "type_domain": "entity_ref"},
                {"name": "threshold_ppm", "type_domain": "int"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
            "owner_type": _ECSS_UNCERTAINTY_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "assessment_ref", "type_domain": "entity_ref"},
                {"name": "probability_ppm", "type_domain": "int"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
            "owner_type": _ECSS_UNCERTAINTY_OWNER_TYPE,
            "arity": 2,
            "arg_specs": [
                {"name": "assessment_ref", "type_domain": "entity_ref"},
                {"name": "threshold_ppm", "type_domain": "int"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
    ]


def extend_schema_ir_with_ecss_uncertainty_predicates(schema_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema_ir, dict):
        raise EcssUncertaintyError("schema_ir must be dict")

    predicates = schema_ir.get("predicates")
    projection = schema_ir.get("projection")
    if not isinstance(predicates, list):
        raise EcssUncertaintyError("schema_ir.predicates must be list")
    if not isinstance(projection, dict):
        raise EcssUncertaintyError("schema_ir.projection must be object")
    projection_predicates = projection.get("predicates")
    if not isinstance(projection_predicates, list):
        raise EcssUncertaintyError("schema_ir.projection.predicates must be list")

    out = copy.deepcopy(schema_ir)
    out_predicates = out["predicates"]
    out_projection_predicates = out["projection"]["predicates"]

    existing_pred_ids = {
        pred.get("pred_id")
        for pred in out_predicates
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
    }
    for predicate in ecss_uncertainty_predicates():
        pred_id = predicate["pred_id"]
        if pred_id not in existing_pred_ids:
            out_predicates.append(predicate)
            existing_pred_ids.add(pred_id)
        if pred_id not in out_projection_predicates:
            out_projection_predicates.append(pred_id)
    return out


__all__ = [
    "ECSS_COLLISION_PROBABILITY_PPM_PRED_ID",
    "ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID",
    "ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID",
    "ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID",
    "ECSS_UNCERTAINTY_PRED_IDS",
    "EcssUncertaintyError",
    "ecss_uncertainty_predicates",
    "extend_schema_ir_with_ecss_uncertainty_predicates",
]
