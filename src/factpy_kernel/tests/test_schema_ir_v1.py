from __future__ import annotations

import copy
import unittest

from factpy_kernel.core.schema.schema_ir import (
    SchemaIRValidationError,
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest,
)


def _base_schema_ir() -> dict:
    return {
        "schema_ir_version": "schema_ir_v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "source_id", "type_domain": "string"},
                ],
            },
            {
                "entity_type": "Speaks",
                "is_record": True,
                "identity_fields": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "language", "type_domain": "string"},
                ],
            },
        ],
        "predicates": [
            {
                "pred_id": "person:country",
                "cardinality": "functional",
                "arg_specs": [
                    {"name": "E", "type_domain": "entity_ref"},
                    {"name": "Country", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "aliases": [],
            },
            {
                "pred_id": "Speaks:exists",
                "cardinality": "functional",
                "arg_specs": [
                    {"name": "E", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "aliases": [],
            },
        ],
        "projection": {"entities": [], "predicates": []},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-03-02T10:11:12Z",
    }


class SchemaIRV1Tests(unittest.TestCase):
    def test_schema_digest_stable_under_key_order(self) -> None:
        s1 = _base_schema_ir()
        s2 = {
            "generated_at": s1["generated_at"],
            "protocol_version": {
                "export_v1": "export_v1",
                "tup_v1": "tup_v1",
                "idref_v1": "idref_v1",
            },
            "projection": {"predicates": [], "entities": []},
            "predicates": copy.deepcopy(s1["predicates"]),
            "entities": copy.deepcopy(s1["entities"]),
            "schema_ir_version": s1["schema_ir_version"],
        }
        self.assertEqual(schema_digest(s1), schema_digest(s2))

    def test_reject_unknown_type_domain(self) -> None:
        bad = _base_schema_ir()
        bad["predicates"][0]["arg_specs"][1]["type_domain"] = "decimal"
        with self.assertRaises(SchemaIRValidationError):
            ensure_schema_ir(bad)

    def test_reject_float_number_in_schema_ir(self) -> None:
        bad = _base_schema_ir()
        bad["entities"][0]["meta"] = {"x": 1.0}
        with self.assertRaises(SchemaIRValidationError):
            canonicalize_schema_ir_jcs(bad)


if __name__ == "__main__":
    unittest.main()
