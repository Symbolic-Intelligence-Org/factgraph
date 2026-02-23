from __future__ import annotations

import unittest

from factpy_kernel.sdk import (
    Entity,
    Field,
    Identity,
    build_authoring_schema_from_classes,
    compile_schema_from_classes,
    schema_preflight_from_classes,
)


class Company(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")


class Person(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    age: int = Field(cardinality="functional", name="has_age")
    name_by_lang: str = Field(
        cardinality="functional",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )
    works_at: Company = Field(cardinality="multi")


class SDKCompileV1Tests(unittest.TestCase):
    def test_build_authoring_schema_from_classes(self) -> None:
        payload = build_authoring_schema_from_classes([Person, Company])
        self.assertEqual([e["entity_type"] for e in payload["entities"]], ["Person", "Company"])
        person = payload["entities"][0]
        self.assertEqual(person["identity_fields"][0]["name"], "source_system")
        self.assertEqual(person["fields"][0]["name"], "has_age")
        self.assertEqual(person["fields"][1]["fact_key"], ["lang"])

    def test_compile_schema_from_classes(self) -> None:
        schema_ir = compile_schema_from_classes([Person, Company], generated_at="2026-01-01T00:00:00Z")
        pred_ids = [pred["pred_id"] for pred in schema_ir["predicates"]]
        self.assertIn("person:has_age", pred_ids)
        self.assertIn("person:name_by_lang", pred_ids)
        self.assertIn("company:sector", pred_ids)

        by_lang = next(pred for pred in schema_ir["predicates"] if pred["pred_id"] == "person:name_by_lang")
        self.assertEqual(by_lang["group_key_indexes"], [0, 1])
        self.assertEqual([a["name"] for a in by_lang["arg_specs"]], ["person", "lang", "value"])

    def test_schema_preflight_from_classes(self) -> None:
        preflight = schema_preflight_from_classes([Person, Company], generated_at="2026-01-01T00:00:00Z")
        self.assertTrue(preflight["ok"])
        self.assertEqual(preflight["kind"], "schema")
        self.assertIn("schema_digest", preflight)


if __name__ == "__main__":
    unittest.main()

