from __future__ import annotations

import copy
from typing import Any


class EcssVcdError(Exception):
    pass


ECSS_REQUIREMENT_PRED_ID = "ecss:requirement"
ECSS_VERIFICATION_METHOD_PRED_ID = "ecss:verification_method"
ECSS_COMPLIANCE_STATUS_PRED_ID = "ecss:compliance_status"
ECSS_REQUIREMENT_RID_PRED_ID = "ecss:requirement_rid"
ECSS_REVIEW_MILESTONE_PRED_ID = "ecss:review_milestone"

ECSS_VCD_PRED_IDS = (
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
)


def ecss_vcd_predicates() -> list[dict[str, Any]]:
    return [
        {
            "pred_id": ECSS_REQUIREMENT_PRED_ID,
            "owner_type": "ecss_requirement",
            "arity": 4,
            "arg_specs": [
                {"name": "requirement_ref", "type_domain": "entity_ref"},
                {"name": "req_id", "type_domain": "string"},
                {"name": "title", "type_domain": "string"},
                {"name": "standard_ref", "type_domain": "string"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_VERIFICATION_METHOD_PRED_ID,
            "owner_type": "ecss_requirement",
            "arity": 2,
            "arg_specs": [
                {"name": "requirement_ref", "type_domain": "entity_ref"},
                {"name": "method", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_COMPLIANCE_STATUS_PRED_ID,
            "owner_type": "ecss_requirement",
            "arity": 2,
            "arg_specs": [
                {"name": "requirement_ref", "type_domain": "entity_ref"},
                {"name": "status", "type_domain": "string"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_REQUIREMENT_RID_PRED_ID,
            "owner_type": "ecss_requirement",
            "arity": 2,
            "arg_specs": [
                {"name": "requirement_ref", "type_domain": "entity_ref"},
                {"name": "rid_id", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
        {
            "pred_id": ECSS_REVIEW_MILESTONE_PRED_ID,
            "owner_type": "ecss_requirement",
            "arity": 2,
            "arg_specs": [
                {"name": "requirement_ref", "type_domain": "entity_ref"},
                {"name": "milestone", "type_domain": "string"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
    ]


def extend_schema_ir_with_ecss_vcd_predicates(schema_ir: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema_ir, dict):
        raise EcssVcdError("schema_ir must be dict")

    predicates = schema_ir.get("predicates")
    projection = schema_ir.get("projection")
    if not isinstance(predicates, list):
        raise EcssVcdError("schema_ir.predicates must be list")
    if not isinstance(projection, dict):
        raise EcssVcdError("schema_ir.projection must be object")
    projection_predicates = projection.get("predicates")
    if not isinstance(projection_predicates, list):
        raise EcssVcdError("schema_ir.projection.predicates must be list")

    out = copy.deepcopy(schema_ir)
    out_predicates = out["predicates"]
    out_projection_predicates = out["projection"]["predicates"]

    existing_pred_ids = {
        pred.get("pred_id")
        for pred in out_predicates
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str)
    }
    for predicate in ecss_vcd_predicates():
        pred_id = predicate["pred_id"]
        if pred_id not in existing_pred_ids:
            out_predicates.append(predicate)
            existing_pred_ids.add(pred_id)
        if pred_id not in out_projection_predicates:
            out_projection_predicates.append(pred_id)
    return out


__all__ = [
    "ECSS_REQUIREMENT_PRED_ID",
    "ECSS_VERIFICATION_METHOD_PRED_ID",
    "ECSS_COMPLIANCE_STATUS_PRED_ID",
    "ECSS_REQUIREMENT_RID_PRED_ID",
    "ECSS_REVIEW_MILESTONE_PRED_ID",
    "ECSS_VCD_PRED_IDS",
    "EcssVcdError",
    "ecss_vcd_predicates",
    "extend_schema_ir_with_ecss_vcd_predicates",
]
