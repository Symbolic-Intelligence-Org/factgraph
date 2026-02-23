from __future__ import annotations

import unittest

from factpy_kernel.authoring import AuthoringSchemaCompileError, compile_authoring_schema_v1
from factpy_kernel.authoring.preflight import schema_preflight
from factpy_kernel.core.schema.schema_ir import ensure_schema_ir


class AuthoringSchemaCompileV1Tests(unittest.TestCase):
    def test_compile_basic_entities_to_schema_ir(self) -> None:
        schema_ir = compile_authoring_schema_v1(_basic_authoring_schema(), generated_at="2026-01-01T00:00:00Z")
        ensure_schema_ir(schema_ir)
        self.assertEqual(schema_ir["schema_ir_version"], "v1")
        pred_ids = [pred["pred_id"] for pred in schema_ir["predicates"]]
        self.assertIn("person:has_age", pred_ids)
        self.assertIn("person:phone", pred_ids)
        self.assertIn("company:sector", pred_ids)

        age_pred = _find_pred(schema_ir, "person:has_age")
        self.assertEqual(age_pred["cardinality"], "functional")
        self.assertEqual(age_pred["group_key_indexes"], [0])
        self.assertEqual(age_pred["arg_specs"][0]["type_domain"], "entity_ref")
        self.assertEqual(age_pred["arg_specs"][1]["type_domain"], "int")

        phone_pred = _find_pred(schema_ir, "person:phone")
        self.assertEqual(phone_pred["aliases"], ["mobile", "handy"])
        self.assertEqual(phone_pred["display_name"], "Phone")

        preflight = schema_preflight(schema_ir)
        self.assertTrue(preflight["ok"])

    def test_compile_fact_key_dims_to_group_key_indexes(self) -> None:
        schema_ir = compile_authoring_schema_v1(_schema_with_fact_key_dims(), generated_at="2026-01-01T00:00:00Z")
        pred = _find_pred(schema_ir, "person:name_by_lang")
        self.assertEqual(pred["cardinality"], "functional")
        self.assertEqual(pred["dims"], ["lang"])
        self.assertEqual(pred["group_key_indexes"], [0, 1])
        self.assertEqual([arg["name"] for arg in pred["arg_specs"]], ["person", "lang", "value"])

    def test_reject_invalid_fact_key_unknown_dim(self) -> None:
        bad = _schema_with_fact_key_dims()
        bad["entities"][0]["fields"][0]["fact_key"] = ["missing_dim"]
        with self.assertRaises(AuthoringSchemaCompileError):
            compile_authoring_schema_v1(bad)

    def test_pred_id_override_takes_precedence_over_name(self) -> None:
        payload = {
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_system", "type_domain": "string"},
                        {"name": "source_id", "type_domain": "string"},
                    ],
                    "fields": [
                        {
                            "py_name": "age",
                            "name": "ignored_local_name",
                            "pred_id": "person:custom_age",
                            "type_domain": "int",
                            "cardinality": "functional",
                        }
                    ],
                }
            ]
        }
        schema_ir = compile_authoring_schema_v1(payload, generated_at="2026-01-01T00:00:00Z")
        pred = _find_pred(schema_ir, "person:custom_age")
        self.assertEqual(pred["py_field_name"], "age")

    def test_record_entity_adds_exists_predicate(self) -> None:
        payload = {
            "entities": [
                {
                    "entity_type": "employment",
                    "is_record": True,
                    "identity_fields": [{"name": "uid", "type_domain": "uuid"}],
                    "fields": [
                        {"py_name": "employee", "type_domain": "entity_ref", "cardinality": "functional"},
                        {"py_name": "employer", "type_domain": "entity_ref", "cardinality": "functional"},
                    ],
                }
            ]
        }
        schema_ir = compile_authoring_schema_v1(payload, generated_at="2026-01-01T00:00:00Z")
        pred_ids = [pred["pred_id"] for pred in schema_ir["predicates"]]
        self.assertIn("employment:exists", pred_ids)
        ensure_schema_ir(schema_ir)


def _find_pred(schema_ir: dict, pred_id: str) -> dict:
    for pred in schema_ir["predicates"]:
        if pred.get("pred_id") == pred_id:
            return pred
    raise AssertionError(f"predicate not found: {pred_id}")


def _basic_authoring_schema() -> dict:
    return {
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "source_system", "type_domain": "string"},
                    {"name": "source_id", "type_domain": "string"},
                ],
                "fields": [
                    {"py_name": "name", "type_domain": "string", "cardinality": "multi"},
                    {
                        "py_name": "age",
                        "name": "has_age",
                        "type_domain": "int",
                        "cardinality": "functional",
                        "description": "Age in years",
                    },
                    {
                        "py_name": "phone",
                        "type_domain": "string",
                        "cardinality": "multi",
                        "aliases": ["mobile", "handy"],
                        "display_name": "Phone",
                    },
                    {
                        "py_name": "works_at",
                        "type_domain": "entity_ref",
                        "cardinality": "multi",
                    },
                ],
            },
            {
                "entity_type": "Company",
                "identity_fields": [
                    {"name": "source_system", "type_domain": "string"},
                    {"name": "source_id", "type_domain": "string"},
                ],
                "fields": [
                    {"py_name": "sector", "type_domain": "string", "cardinality": "functional"},
                ],
            },
        ]
    }


def _schema_with_fact_key_dims() -> dict:
    return {
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "source_system", "type_domain": "string"},
                    {"name": "source_id", "type_domain": "string"},
                ],
                "fields": [
                    {
                        "py_name": "name_by_lang",
                        "type_domain": "string",
                        "value_name": "value",
                        "cardinality": "functional",
                        "dims": [{"name": "lang", "type_domain": "string"}],
                        "fact_key": ["lang"],
                    }
                ],
            }
        ]
    }


if __name__ == "__main__":
    unittest.main()
