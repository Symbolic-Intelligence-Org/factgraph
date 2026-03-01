from __future__ import annotations

import unittest

from factpy_kernel.authoring import AuthoringDerivationCompileError, compile_authoring_derivation_v1


class AuthoringDerivationCompileV1Tests(unittest.TestCase):
    def test_compile_aliases_without_materialize_as(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "name": "drv.country",
                "target": "person:country",
                "select": ["E", "country"],
                "body": [("pred", "person:country", ["$E", "$country"])],
                "mode": "python",
                "temporal_view": "active",
            }
        )
        self.assertEqual(payload["derivation_id"], "drv.country")
        self.assertEqual(payload["target"], "person:country")
        self.assertEqual(payload["target_pred_id"], "person:country")
        self.assertEqual(payload["head_vars"], ["$E", "$country"])
        self.assertEqual(payload["where"], [("pred", "person:country", ["$E", "$country"])])
        self.assertNotIn("materialize_as", payload)
        self.assertNotIn("id_policy", payload)

    def test_reject_materialize_as_user_field(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.country",
                    "target_pred_id": "person:country",
                    "head_vars": ["$E", "$country"],
                    "where": [("pred", "person:country", ["$E", "$country"])],
                    "materialize_as": "fact",
                }
            )
        self.assertEqual(ctx.exception.path, "$.materialize_as")

    def test_reject_id_policy_user_field(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.speaks",
                    "target_pred_id": "Speaks",
                    "head_vars": ["$p", "$l"],
                    "where": [("pred", "person:country", ["$p", "de"])],
                    "id_policy": {"kind": "identity_fields_v1", "fields": []},
                }
            )
        self.assertEqual(ctx.exception.path, "$.id_policy")

    def test_schema_aware_fact_head_lowers_target_and_head_vars(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country_copy",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "Person",
                    "field": "country",
                    "kwargs": {"person": "E", "country": "country"},
                },
                "where": [("pred", "person:country", ["$E", "$country"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "person:country")
        self.assertEqual(payload["target"], "person:country")
        self.assertEqual(payload["head_vars"], ["$E", "$country"])
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")

    def test_schema_aware_entity_head_lowers_target_and_head_vars(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "p", "language": "l"},
                },
                "where": [("pred", "person:country", ["$p", "de"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "Speaks")
        self.assertEqual(payload["target"], "Speaks")
        self.assertEqual(payload["head_vars"], ["$p", "$l"])
        self.assertEqual(payload["head"]["callee_kind"], "entity_type")

    def test_schema_aware_legacy_target_synthesizes_fact_head(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$country"],
                "where": [("pred", "person:country", ["$E", "$country"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")
        self.assertEqual(payload["head"]["entity_type"], "Person")
        self.assertEqual(payload["head"]["field"], "country")
        self.assertEqual(payload["head"]["kwargs"], {"person": "$E", "country": "$country"})

    def test_schema_aware_where_lowering_rewrites_record_sugar_predicates(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.lives_in_country",
                "target_pred_id": "person:country",
                "head_vars": ["$p", "$c"],
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


def _schema_for_head_lowering() -> dict[str, object]:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {"entity_type": "Speaks", "identity_fields": [{"name": "uid", "type_domain": "string"}]},
        ],
        "predicates": [
            {
                "pred_id": "person:country",
                "owner_type": "Person",
                "py_field_name": "country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
            {
                "pred_id": "Speaks:exists",
                "owner_type": "Speaks",
                "is_entity_exists": True,
                "arg_specs": [{"name": "speaks", "type_domain": "entity_ref"}],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
            {
                "pred_id": "speaks:person",
                "owner_type": "Speaks",
                "py_field_name": "person",
                "arg_specs": [
                    {"name": "speaks", "type_domain": "entity_ref"},
                    {"name": "person", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
            {
                "pred_id": "speaks:language",
                "owner_type": "Speaks",
                "py_field_name": "language",
                "arg_specs": [
                    {"name": "speaks", "type_domain": "entity_ref"},
                    {"name": "language", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
        ],
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _schema_for_where_record_sugar() -> dict[str, object]:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {"entity_type": "LivesIn", "identity_fields": [{"name": "uid", "type_domain": "string"}]},
        ],
        "predicates": [
            {
                "pred_id": "person:country",
                "owner_type": "Person",
                "py_field_name": "country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            },
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
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
