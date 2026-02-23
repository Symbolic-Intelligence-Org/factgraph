from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringSchemaDSLParseError,
    compile_authoring_schema_v1,
    parse_authoring_schema_dsl_v1,
)


class AuthoringSchemaDSLParseV1Tests(unittest.TestCase):
    def test_parse_basic_entity_dsl_to_authoring_payload(self) -> None:
        payload = parse_authoring_schema_dsl_v1(
            """
class Person(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="multi")
    age: int = Field(name="has_age", cardinality="functional", description="Age")
    phone: str = Field(cardinality="multi", aliases=["mobile", "handy"], display_name="Phone")
"""
        )
        self.assertEqual(list(payload.keys()), ["entities"])
        self.assertEqual(len(payload["entities"]), 1)
        person = payload["entities"][0]
        self.assertEqual(person["entity_type"], "Person")
        self.assertEqual([f["name"] for f in person["identity_fields"]], ["source_system", "source_id"])
        age = next(field for field in person["fields"] if field["py_name"] == "age")
        self.assertEqual(age["cardinality"], "functional")
        self.assertEqual(age["name"], "has_age")
        self.assertEqual(age["type_domain"], "int")
        phone = next(field for field in person["fields"] if field["py_name"] == "phone")
        self.assertEqual(phone["aliases"], ["mobile", "handy"])
        self.assertEqual(phone["display_name"], "Phone")

    def test_parse_relational_field_dims_and_fact_key(self) -> None:
        payload = parse_authoring_schema_dsl_v1(
            """
class Person(Entity):
    source_id: str = Identity()
    salary: str = Field(
        cardinality="functional",
        dims=[("year", str)],
        fact_key=["year"],
        value_name="amount"
    )
"""
        )
        field = payload["entities"][0]["fields"][0]
        self.assertEqual(field["dims"], [{"name": "year", "type_domain": "string"}])
        self.assertEqual(field["fact_key"], ["year"])
        self.assertEqual(field["value_name"], "amount")
        schema_ir = compile_authoring_schema_v1(payload, generated_at="2026-01-01T00:00:00Z")
        pred = next(p for p in schema_ir["predicates"] if p["pred_id"] == "person:salary")
        self.assertEqual(pred["group_key_indexes"], [0, 1])

    def test_parse_record_entity_meta_and_identity_default_factory(self) -> None:
        payload = parse_authoring_schema_dsl_v1(
            """
class Employment(Entity):
    uid: str = Identity(default_factory="uuid4")
    employee: "Person" = Field(cardinality="functional")
    employer: "Company" = Field(cardinality="functional")
    class Meta:
        is_record = True
        owner = "HR"
"""
        )
        entity = payload["entities"][0]
        self.assertTrue(entity["is_record"])
        self.assertEqual(entity["meta"]["owner"], "HR")
        self.assertEqual(entity["identity_fields"][0]["default_factory"], "uuid4")
        self.assertEqual(entity["fields"][0]["type_domain"], "entity_ref")

    def test_reject_unsupported_top_level_statement(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError):
            parse_authoring_schema_dsl_v1("def f():\n    return 1\n")

    def test_reject_field_without_cardinality(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1(
                """
class Person(Entity):
    source_id: str = Identity()
    age: int = Field()
"""
            )
        self.assertIsNotNone(ctx.exception.path)

    def test_reject_positional_args_in_identity_or_field(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError):
            parse_authoring_schema_dsl_v1(
                """
class Person(Entity):
    source_id: str = Identity("x")
"""
            )

    def test_schema_dsl_parse_error_exposes_syntax_kind_and_path(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1("class Person(Entity):\n  x: str = Identity(\n")
        self.assertEqual(ctx.exception.kind, "syntax")
        self.assertTrue((ctx.exception.path or "").startswith("$.dsl:line:"))
        self.assertIsNone(getattr(ctx.exception, "details", None))

    def test_schema_dsl_parse_error_exposes_top_level_statement_details(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1("def f():\n    return 1\n")
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.body[0]")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "unsupported_top_level_statement")
        self.assertEqual(ctx.exception.details["statement_type"], "FunctionDef")

    def test_schema_dsl_parse_error_exposes_positional_arg_details(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1(
                """
class Person(Entity):
    source_id: str = Identity("x")
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.entities[0].body[0].Identity.args")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "call_positional_args_not_supported")
        self.assertEqual(ctx.exception.details["call_name"], "Identity")

    def test_schema_dsl_parse_error_exposes_unsupported_keywords_details(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1(
                """
class Person(Entity):
    source_id: str = Identity()
    age: int = Field(cardinality="functional", bad_kw=True)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.entities[0].body[1].Field")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "unsupported_keywords")
        self.assertEqual(ctx.exception.details["call_name"], "Field")
        self.assertEqual(ctx.exception.details["unsupported_keywords"], "bad_kw")
        self.assertEqual(ctx.exception.details["unsupported_keyword_count"], 1)

    def test_fixtures_doc_schema_dsl_examples_parse_and_shape(self) -> None:
        text = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")
        dsl_source = self._extract_code_block_after_header(
            text,
            "### F5-G schema DSL parser（语法层 → Authoring payload，最小切片）",
            "python",
            which=1,
        )
        payload = parse_authoring_schema_dsl_v1(dsl_source)
        self.assertEqual(payload["entities"][0]["entity_type"], "Person")
        json_snippet = self._extract_code_block_after_header(
            text,
            "### F5-G schema DSL parser（语法层 → Authoring payload，最小切片）",
            "json",
            which=1,
        )
        expected_shape = json.loads(json_snippet)
        self.assertEqual(expected_shape["entities"][0]["entity_type"], "Person")
        self.assertEqual(expected_shape["entities"][0]["identity_fields"][0]["name"], "source_id")
        self.assertEqual(expected_shape["entities"][0]["fields"][0]["py_name"], "age")
        self.assertEqual(expected_shape["entities"][0]["fields"][1]["aliases"], ["mobile"])

    def _extract_code_block_after_header(self, text: str, header: str, lang: str, *, which: int) -> str:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        matches = list(re.finditer(rf"```{lang}\s*\n(.*?)\n```", tail, flags=re.S))
        self.assertGreaterEqual(len(matches), which, f"missing code block #{which} lang={lang} after {header}")
        return matches[which - 1].group(1)


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs"


if __name__ == "__main__":
    unittest.main()
