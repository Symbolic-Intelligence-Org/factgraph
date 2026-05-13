from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factpy.authoring.registry_fs import FileAuthoringRegistry
from factpy.authoring.rule_compile import AuthoringRuleCompileError, compile_authoring_rule_v1
from factpy.authoring.schema_compile import compile_authoring_schema_v1
from factpy.authoring.schema_dsl_parse import (
    AuthoringSchemaDSLParseError,
    parse_authoring_schema_dsl_v1,
)
from factpy.service.registry_v1 import read_registry_rule
from factpy.service.rules_v1 import compile_rule_preview
from factpy.sdk import (
    Inference,
    Entity,
    Field,
    Identity,
    Pred,
    Rule,
    SDKSchemaError,
    SDKStore,
    compile_schema_from_classes,
    vars as sdk_vars,
)


class DeclarationMetadataV1Tests(unittest.TestCase):
    def test_entity_meta_description_overrides_docstring_and_preserves_version_tags(self) -> None:
        class EmploymentEvent(Entity):
            """Docstring fallback that should be overridden."""

            class Meta:
                version = "v2"
                description = "Explicit employment event description"
                tags = ["employment", "event"]

            event_id: str = Identity(primary_key=True)

        spec = EmploymentEvent.sdk_entity_spec()
        self.assertEqual(spec["version"], "v2")
        self.assertEqual(spec["description"], "Explicit employment event description")
        self.assertEqual(spec["tags"], ["employment", "event"])
        self.assertNotIn("meta", spec)

        schema_ir = compile_schema_from_classes([EmploymentEvent])
        entity = schema_ir["entities"][0]
        self.assertEqual(entity["version"], "v2")
        self.assertEqual(entity["description"], "Explicit employment event description")
        self.assertEqual(entity["tags"], ["employment", "event"])

    def test_entity_docstring_falls_back_when_meta_description_is_absent(self) -> None:
        class Account(Entity):
            """Account description from docstring."""

            class Meta:
                version = "v1"
                tags = ["billing"]

            account_id: str = Identity(primary_key=True)

        spec = Account.sdk_entity_spec()
        self.assertEqual(spec["description"], "Account description from docstring.")
        self.assertEqual(spec["version"], "v1")
        self.assertEqual(spec["tags"], ["billing"])

    def test_plain_entity_repr_previews_declared_identity_and_fields(self) -> None:
        class Account(Entity):
            account_id: str = Identity(primary_key=True)
            owner: str = Field(cardinality="single")
            status: str = Field(cardinality="single")

        account = Account(account_id="acct-1", owner="alice")
        self.assertEqual(repr(account), "Account(account_id='acct-1', owner='alice', status=None)")

    def test_entity_meta_rejects_unknown_keys(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:
            class InvalidEntity(Entity):
                class Meta:
                    owner = "hr"

                invalid_id: str = Identity(primary_key=True)

        self.assertIn("only supports version, description, and tags", str(ctx.exception))

    def test_schema_dsl_meta_fields_override_docstring(self) -> None:
        parsed = parse_authoring_schema_dsl_v1(
            """
class EmploymentEvent(Entity):
    \"\"\"Docstring fallback description.\"\"\"

    class Meta:
        version = "v3"
        description = "Schema DSL explicit description"
        tags = ["employment", "dsl"]

    event_id: str = Identity(primary_key=True)
""".strip()
        )
        entity = parsed["entities"][0]
        self.assertEqual(entity["version"], "v3")
        self.assertEqual(entity["description"], "Schema DSL explicit description")
        self.assertEqual(entity["tags"], ["employment", "dsl"])
        self.assertNotIn("meta", entity)

        schema_ir = compile_authoring_schema_v1(parsed)
        self.assertEqual(schema_ir["entities"][0]["version"], "v3")
        self.assertEqual(schema_ir["entities"][0]["description"], "Schema DSL explicit description")
        self.assertEqual(schema_ir["entities"][0]["tags"], ["employment", "dsl"])

    def test_schema_dsl_meta_rejects_unknown_keys(self) -> None:
        with self.assertRaises(AuthoringSchemaDSLParseError) as ctx:
            parse_authoring_schema_dsl_v1(
                """
class EmploymentEvent(Entity):
    class Meta:
        owner = "hr"

    event_id: str = Identity(primary_key=True)
""".strip()
            )

        self.assertEqual(ctx.exception.path, "$.dsl.entities[0].Meta")
        self.assertIn("unsupported keyword(s): owner", str(ctx.exception))

    def test_rule_description_and_tags_round_trip_through_compiler(self) -> None:
        rule = Rule(
            id="employment_match",
            version="v1",
            select=["$u"],
            where=[("pred", "user:name", ["$u", "$name"])],
            description="Find employment related matches",
            tags=["employment", "match"],
        )

        compiled = compile_authoring_rule_v1(rule.to_authoring_payload())
        self.assertEqual(compiled["description"], "Find employment related matches")
        self.assertEqual(compiled["tags"], ["employment", "match"])

    def test_rule_condition_weights_round_trip_through_compiler(self) -> None:
        rule = Rule(
            id="employment_match",
            version="v1",
            select=["$u"],
            where=[
                ("pred", "user:name", ["$u", "$name"]),
                ("pred", "user:tag", ["$u", "employment"]),
            ],
            description="Find employment related matches",
            tags=["employment", "match"],
            condition_weights={"b0.a1": 0.25, "b0.a0": 0.75},
        )

        compiled = compile_authoring_rule_v1(rule.to_authoring_payload())
        self.assertEqual(compiled["description"], "Find employment related matches")
        self.assertEqual(compiled["tags"], ["employment", "match"])
        self.assertEqual(compiled["condition_weights"], {"b0.a0": 0.75, "b0.a1": 0.25})

    def test_rule_authoring_payload_has_no_engine_ext(self) -> None:
        rule = Rule(
            id="employment_match",
            version="v1",
            select=["$u"],
            where=[("pred", "user:name", ["$u", "$name"])],
        )

        payload = rule.to_authoring_payload()
        self.assertNotIn("engine_ext", payload)

    def test_rule_compiler_rejects_invalid_tags(self) -> None:
        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "employment_match",
                    "version": "v1",
                    "description": "Find employment related matches",
                    "tags": ["employment", ""],
                    "select": ["$u"],
                    "where": [("pred", "user:name", ["$u", "$name"])],
                }
            )

        self.assertEqual(ctx.exception.path, "$.tags[1]")

    def test_rule_compiler_rejects_unknown_condition_weight_key(self) -> None:
        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "employment_match",
                    "version": "v1",
                    "select": ["$u"],
                    "where": [
                        ("pred", "user:name", ["$u", "$name"]),
                        ("pred", "user:tag", ["$u", "employment"]),
                    ],
                    "condition_weights": {"b0.a9": 0.5},
                }
            )

        self.assertEqual(ctx.exception.path, '$.condition_weights["b0.a9"]')

    def test_rule_compiler_rejects_non_positive_condition_weight(self) -> None:
        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "employment_match",
                    "version": "v1",
                    "select": ["$u"],
                    "where": [
                        ("pred", "user:name", ["$u", "$name"]),
                        ("pred", "user:tag", ["$u", "employment"]),
                    ],
                    "condition_weights": {"b0.a0": 0},
                }
            )

        self.assertEqual(ctx.exception.path, '$.condition_weights["b0.a0"]')

    def test_rule_metadata_survives_service_compile_preview(self) -> None:
        compiled = compile_authoring_rule_v1(
            {
                "rule_id": "employment_match",
                "version": "v1",
                "description": "Find employment related matches",
                "tags": ["employment", "match"],
                "condition_weights": {"b0.a1": 0.25, "b0.a0": 0.75},
                "select": ["$u"],
                "where": [
                    ("pred", "user:name", ["$u", "$name"]),
                    ("pred", "user:tag", ["$u", "employment"]),
                ],
            }
        )

        response = compile_rule_preview(
            {
                "api_version": "v1",
                "mode": "souffle",
                "rule": compiled,
            }
        )

        self.assertTrue(response["ok"])
        self.assertEqual(
            response["preview"]["compiled_payload"]["description"],
            "Find employment related matches",
        )
        self.assertEqual(
            response["preview"]["compiled_payload"]["tags"],
            ["employment", "match"],
        )
        self.assertEqual(
            response["preview"]["compiled_payload"]["condition_weights"],
            {"b0.a0": 0.75, "b0.a1": 0.25},
        )

    def test_rule_metadata_survives_registry_round_trip(self) -> None:
        compiled = compile_authoring_rule_v1(
            {
                "rule_id": "employment_match",
                "version": "v1",
                "description": "Find employment related matches",
                "tags": ["employment", "match"],
                "condition_weights": {"b0.a1": 0.25, "b0.a0": 0.75},
                "select": ["$u"],
                "where": [
                    ("pred", "user:name", ["$u", "$name"]),
                    ("pred", "user:tag", ["$u", "employment"]),
                ],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.register_rule_spec(compiled)

            response = read_registry_rule(
                {
                    "root_dir": tmp_dir,
                    "rule_id": "employment_match",
                    "version": "v1",
                }
            )

        self.assertTrue(response["ok"])
        self.assertEqual(
            response["rule_spec"]["description"],
            "Find employment related matches",
        )
        self.assertEqual(response["rule_spec"]["tags"], ["employment", "match"])
        self.assertEqual(
            response["rule_spec"]["condition_weights"],
            {"b0.a0": 0.75, "b0.a1": 0.25},
        )

    def test_derivation_description_and_tags_survive_sdk_store_compile_path(self) -> None:
        class User(Entity):
            user_id: str = Identity(primary_key=True)
            name: str = Field(cardinality="single")

        sdk = SDKStore([User])
        with sdk_vars("u", "name") as (u, name):
            derivation = Inference(
                id="user_name_derivation",
                version="v1",
                where=[Pred("user:name", u, name)],
                target="user:name",
                head_vars=[u, name],
                description="Derive user name facts",
                tags=["derivation", "user"],
            )

        compiled_payloads = sdk._compile_derivation_input(derivation)
        self.assertEqual(len(compiled_payloads), 1)
        self.assertEqual(compiled_payloads[0]["description"], "Derive user name facts")
        self.assertEqual(compiled_payloads[0]["tags"], ["derivation", "user"])

    def test_derivation_compiler_rejects_invalid_description(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "user_name_derivation",
                    "version": "v1",
                    "description": "",
                    "target": "user:name",
                    "head_vars": ["$u", "$name"],
                    "where": [("pred", "user:name", ["$u", "$name"])],
                }
            )

        self.assertEqual(ctx.exception.path, "$.description")


if __name__ == "__main__":
    unittest.main()
