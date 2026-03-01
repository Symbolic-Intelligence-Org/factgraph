from __future__ import annotations

import unittest

from factpy_kernel.authoring import AuthoringRuleCompileError, compile_authoring_rule_v1


class AuthoringRuleCompileV1Tests(unittest.TestCase):
    def test_compile_authoring_rule_aliases(self) -> None:
        payload = compile_authoring_rule_v1(
            {
                "name": "rules.country_rows",
                "version": "v1",
                "select": ["E", "$C"],
                "body": [("pred", "person:country", ["$E", "$C"])],
                "public": True,
            }
        )
        self.assertEqual(payload["rule_id"], "rules.country_rows")
        self.assertEqual(payload["version"], "v1")
        self.assertEqual(payload["select_vars"], ["$E", "$C"])
        self.assertEqual(payload["where"], [("pred", "person:country", ["$E", "$C"])])
        self.assertTrue(payload["expose"])

    def test_reject_conflicting_select_aliases_with_path(self) -> None:
        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "rules.bad",
                    "version": "v1",
                    "select_vars": ["$E"],
                    "select": ["$X"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                }
            )
        self.assertEqual(ctx.exception.path, "$.select")

    def test_reject_invalid_select_item_path(self) -> None:
        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "rules.bad",
                    "where": [("pred", "person:country", ["$E", "$C"])],
                    "select": ["bad-name"],
                }
            )
        self.assertEqual(ctx.exception.path, "$.select[0]")

    def test_schema_aware_where_lowering_rewrites_record_sugar_predicates(self) -> None:
        payload = compile_authoring_rule_v1(
            {
                "rule_id": "rules.lives_in_rows",
                "select": ["li", "p", "c"],
                "where": [
                    ("pred", "LivesIn:exists", ["$li"]),
                    ("pred", "livesin:person", ["$li", "$p"]),
                    ("pred", "livesin:country", ["$li", "$c"]),
                ],
            },
            schema_ir=_schema_for_where_record_sugar(),
        )
        self.assertEqual(payload["where"][0], ("pred", "li_record:exists", ["$li"]))
        self.assertEqual(payload["where"][1], ("pred", "li_record:who", ["$li", "$p"]))
        self.assertEqual(payload["where"][2], ("pred", "li_record:nation", ["$li", "$c"]))

    def test_schema_aware_where_lowering_rejects_exists_sugar_when_schema_missing_exists_pred(self) -> None:
        schema = _schema_for_where_record_sugar()
        schema["predicates"] = [pred for pred in schema["predicates"] if pred.get("owner_type") != "LivesIn"]

        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(
                {
                    "rule_id": "rules.bad_exists_sugar",
                    "select": ["li"],
                    "where": [("pred", "LivesIn:exists", ["$li"])],
                },
                schema_ir=schema,
            )
        self.assertEqual(ctx.exception.path, "$.where[0]")
        self.assertIn("entity exists predicate not found in schema for LivesIn", str(ctx.exception))


def _schema_for_where_record_sugar() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {"entity_type": "LivesIn", "identity_fields": [{"name": "uid", "type_domain": "string"}]},
        ],
        "predicates": [
            {
                "pred_id": "li_record:exists",
                "owner_type": "LivesIn",
                "is_entity_exists": True,
                "arg_specs": [{"name": "lives_in", "type_domain": "entity_ref"}],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
            {
                "pred_id": "li_record:who",
                "owner_type": "LivesIn",
                "py_field_name": "person",
                "arg_specs": [
                    {"name": "lives_in", "type_domain": "entity_ref"},
                    {"name": "person", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
            {
                "pred_id": "li_record:nation",
                "owner_type": "LivesIn",
                "py_field_name": "country",
                "arg_specs": [
                    {"name": "lives_in", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
        ],
        "projection": {"entities": [], "predicates": []},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
