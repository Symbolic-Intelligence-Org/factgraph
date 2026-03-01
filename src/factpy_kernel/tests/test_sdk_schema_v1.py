from __future__ import annotations

import unittest

from factpy_kernel.sdk import Entity, Field, Identity, SDKSchemaError


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    works_at: Company = Field(cardinality="multi")
    name_by_lang: str = Field(
        cardinality="functional",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )

    class Meta:
        owner = "demo"
        security_level = "PII"


class Employment(Entity):
    uid: str = Identity(default_factory="uuid4")
    employee: Person = Field(cardinality="functional")
    employer: "Company" = Field(cardinality="functional")
    since: int = Field(cardinality="functional")

    class Meta:
        is_record = True


class Language(Entity):
    source_system: str = Identity(default="ISO639")
    code: str = Identity()
    name: str = Field(cardinality="multi")


class SDKSchemaV1Tests(unittest.TestCase):
    def test_entity_spec_collects_identity_fields_and_fields(self) -> None:
        spec = Person.sdk_entity_spec()
        self.assertEqual(spec["entity_type"], "Person")
        self.assertEqual(spec["identity_fields"][0]["name"], "source_id")
        self.assertEqual(spec["identity_fields"][0]["type_domain"], "string")
        field_names = [f["py_name"] for f in spec["fields"]]
        self.assertEqual(field_names, ["country", "works_at", "name_by_lang"])

        country = next(f for f in spec["fields"] if f["py_name"] == "country")
        self.assertEqual(country["pred_id"], "person:country")
        self.assertEqual(country["type_domain"], "string")

        works_at = next(f for f in spec["fields"] if f["py_name"] == "works_at")
        self.assertEqual(works_at["type_domain"], "entity_ref")

        by_lang = next(f for f in spec["fields"] if f["py_name"] == "name_by_lang")
        self.assertEqual(by_lang["dims"], [{"name": "lang", "type_domain": "string"}])
        self.assertEqual(by_lang["fact_key"], ["lang"])

        self.assertEqual(spec["meta"]["owner"], "demo")
        self.assertEqual(spec["meta"]["security_level"], "PII")

    def test_record_meta_flag_is_promoted(self) -> None:
        spec = Employment.sdk_entity_spec()
        self.assertNotIn("is_record", spec)
        self.assertTrue(spec["meta"]["is_record"])
        self.assertEqual(spec["identity_fields"][0]["default_factory"], "uuid4")

    def test_identity_default_is_preserved_in_entity_spec(self) -> None:
        spec = Language.sdk_entity_spec()
        self.assertEqual(spec["identity_fields"][0]["name"], "source_system")
        self.assertEqual(spec["identity_fields"][0]["default"], "ISO639")

    def test_entity_instances_can_hold_declared_values(self) -> None:
        person = Person(source_id="u1")
        person.country = "de"
        self.assertEqual(person.source_id, "u1")
        self.assertEqual(person.country, "de")
        with self.assertRaises(SDKSchemaError):
            Person(unknown="x")

    def test_unset_field_batch_methods_raise_helpful_error(self) -> None:
        person = Person(source_id="u1")
        self.assertFalse(person.country)
        self.assertEqual(repr(person.country), "None")
        with self.assertRaises(SDKSchemaError) as ctx:
            person.country.set("de")
        msg = str(ctx.exception)
        self.assertIn("plain Entity instance", msg)
        self.assertIn("sdk.batch()", msg)
        self.assertIn("tx.entity(...)", msg)
        self.assertIn("obj.country = value", msg)

    def test_missing_identity_is_rejected(self) -> None:
        with self.assertRaises(SDKSchemaError):
            class NoIdentity(Entity):
                name: str = Field(cardinality="multi")


if __name__ == "__main__":
    unittest.main()
