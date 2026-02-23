from __future__ import annotations

import unittest

from factpy_kernel.authoring import AuthoringDerivationCompileError, compile_authoring_derivation_v1


class AuthoringDerivationCompileV1Tests(unittest.TestCase):
    def test_compile_authoring_derivation_aliases(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "name": "drv.country",
                "target": "person:country",
                "select": ["E", "country"],
                "body": [("pred", "person:country", ["$E", "$country"])],
                "mode": "python",
                "temporal_view": "record",
            }
        )
        self.assertEqual(payload["derivation_id"], "drv.country")
        self.assertEqual(payload["target"], "person:country")
        self.assertEqual(payload["target_pred_id"], "person:country")
        self.assertEqual(payload["materialize_as"], "fact")
        self.assertEqual(payload["head_vars"], ["$E", "$country"])
        self.assertEqual(payload["where"], [("pred", "person:country", ["$E", "$country"])])

    def test_compile_legacy_fact_target_defaults_materialize_as_fact(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$country"],
                "where": [("pred", "person:country", ["$E", "$country"])],
            }
        )
        self.assertEqual(payload["materialize_as"], "fact")
        self.assertNotIn("head", payload)

    def test_reject_invalid_mode_with_path(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.bad",
                    "target_pred_id": "person:country",
                    "head_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                    "mode": "bad",
                }
            )
        self.assertEqual(ctx.exception.path, "$.mode")

    def test_reject_head_vars_conflict_path(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.bad",
                    "target_pred_id": "person:country",
                    "head_vars": ["$E", "$C"],
                    "select": ["$E", "$X"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                }
            )
        self.assertEqual(ctx.exception.path, "$.select")

    def test_compile_derivation_with_head_and_materialize_as_fact_preserves_head(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks",
                "target_pred_id": "person:speaks",
                "head_vars": ["$E", "$L"],
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "Person",
                    "field": "speaks",
                    "kwargs": {"person": "p", "language": "$l"},
                },
                "materialize_as": "fact",
                "where": [("pred", "person:speaks", ["$E", "$L"])],
            }
        )
        self.assertEqual(payload["materialize_as"], "fact")
        self.assertEqual(payload["target"], "person:speaks")
        self.assertEqual(payload["head"]["kwargs"]["person"], "$p")
        self.assertEqual(payload["head"]["kwargs"]["language"], "$l")

    def test_reject_head_without_materialize_as(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.country",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "Person",
                        "field": "country",
                        "kwargs": {"person": "$E", "country": "$country"},
                    },
                    "where": [("pred", "person:country", ["$E", "$country"])],
                },
                schema_ir=_schema_for_head_lowering(),
            )
        self.assertEqual(ctx.exception.path, "$.materialize_as")

    def test_compile_record_head_with_schema_lowers_target_and_head_vars(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks_rec",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$p", "language": "$l"},
                },
                "materialize_as": "record",
                "id_policy": {"kind": "key_tuple_digest_v1"},
                "where": [("pred", "person:country", ["$p", "de"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "Speaks")
        self.assertEqual(payload["target"], "Speaks")
        self.assertEqual(payload["head_vars"], ["$p", "$l"])
        self.assertEqual(payload["materialize_as"], "record")
        self.assertEqual(payload["id_policy"]["kind"], "key_tuple_digest_v1")

    def test_compile_record_head_with_identity_fields_id_policy(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks_rec",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$p", "language": "$l"},
                },
                "materialize_as": "record",
                "id_policy": {
                    "kind": "identity_fields_v1",
                    "fields": [
                        {"name": "person", "role": "person", "type_domain": "entity_ref"},
                        {"name": "language", "role": "language", "type_domain": "entity_ref"},
                    ],
                },
                "where": [("pred", "person:country", ["$p", "de"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "Speaks")
        self.assertEqual(payload["id_policy"]["kind"], "identity_fields_v1")
        self.assertEqual(
            payload["id_policy"]["fields"][0],
            {"name": "person", "role": "person", "type_domain": "entity_ref"},
        )

    def test_reject_record_id_policy_unknown_role_with_schema(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.speaks_rec",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "entity_type",
                        "entity_type": "Speaks",
                        "kwargs": {"person": "$p", "language": "$l"},
                    },
                    "materialize_as": "record",
                    "id_policy": {
                        "kind": "identity_fields_v1",
                        "fields": [
                            {"name": "x", "role": "unknown", "type_domain": "entity_ref"},
                        ],
                    },
                    "where": [("pred", "person:country", ["$p", "de"])],
                },
                schema_ir=_schema_for_head_lowering(),
            )
        self.assertEqual(ctx.exception.path, "$.id_policy.fields[0].role")

    def test_compile_record_head_without_id_policy_autoderives_identity_fields_with_schema(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks_rec",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$p", "language": "$l"},
                },
                "materialize_as": "record",
                "where": [("pred", "person:country", ["$p", "de"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["id_policy"]["kind"], "identity_fields_v1")
        self.assertEqual(
            payload["id_policy"]["fields"],
            [
                {"name": "person", "role": "person", "type_domain": "entity_ref"},
                {"name": "language", "role": "language", "type_domain": "entity_ref"},
            ],
        )

    def test_reject_record_materialize_without_id_policy_without_schema(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.speaks_rec",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "entity_type",
                        "entity_type": "Speaks",
                        "kwargs": {"person": "$p", "language": "$l"},
                    },
                    "materialize_as": "record",
                    "where": [("pred", "person:country", ["$p", "de"])],
                }
            )
        self.assertEqual(ctx.exception.path, "$.id_policy")

    def test_reject_head_only_without_target_in_v1(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.speaks",
                    "head_vars": ["$E", "$L"],
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "Person",
                        "field": "speaks",
                        "kwargs": {"person": "$p", "language": "$l"},
                    },
                    "materialize_as": "fact",
                    "where": [("pred", "person:speaks", ["$E", "$L"])],
                }
            )
        self.assertEqual(ctx.exception.path, "$.head")

    def test_schema_aware_fact_head_lowers_target_and_head_vars(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "Person",
                    "field": "country",
                    "kwargs": {"person": "E", "country": "country"},
                },
                "materialize_as": "fact",
                "where": [("pred", "person:country", ["$E", "$country"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "person:country")
        self.assertEqual(payload["target"], "person:country")
        self.assertEqual(payload["head_vars"], ["$E", "$country"])
        self.assertEqual(payload["materialize_as"], "fact")

    def test_schema_aware_legacy_fact_target_synthesizes_head(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$country"],
                "where": [("pred", "person:country", ["$E", "$country"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["materialize_as"], "fact")
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")
        self.assertEqual(payload["head"]["entity_type"], "Person")
        self.assertEqual(payload["head"]["field"], "country")
        self.assertEqual(payload["head"]["kwargs"], {"person": "$E", "country": "$country"})

    def test_schema_aware_fact_head_entity_type_uses_projection_predicate(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.speaks_proj",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "p", "language": "l"},
                },
                "materialize_as": "fact",
                "where": [("pred", "person:country", ["$p", "de"])],
            },
            schema_ir=_schema_for_head_lowering(),
        )
        self.assertEqual(payload["target_pred_id"], "person:speaks")
        self.assertEqual(payload["target"], "person:speaks")
        self.assertEqual(payload["head_vars"], ["$p", "$l"])
        self.assertEqual(payload["projection_pred_id"], "person:speaks")
        self.assertEqual(payload["projection_arg_order"], ["person", "language"])

    def test_schema_aware_fact_head_entity_type_rejects_missing_projection_metadata(self) -> None:
        schema_ir = _schema_for_head_lowering()
        schema_ir["entities"][1].pop("projection_pred_id", None)
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.speaks_proj",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "entity_type",
                        "entity_type": "Speaks",
                        "kwargs": {"person": "$p", "language": "$l"},
                    },
                    "materialize_as": "fact",
                    "where": [("pred", "person:country", ["$p", "de"])],
                },
                schema_ir=schema_ir,
            )
        self.assertEqual(ctx.exception.path, "$.head")

    def test_schema_aware_fact_head_rejects_unknown_kwargs(self) -> None:
        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.country",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "Person",
                        "field": "country",
                        "kwargs": {"person": "$E", "bad": "$x"},
                    },
                    "materialize_as": "fact",
                    "where": [("pred", "person:country", ["$E", "$country"])],
                },
                schema_ir=_schema_for_head_lowering(),
            )
        self.assertEqual(ctx.exception.path, "$.head.kwargs")

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

def _schema_for_head_lowering() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {
                "entity_type": "Speaks",
                "identity_fields": [{"name": "uid", "type_domain": "string"}],
                "is_record": True,
                "projection_pred_id": "person:speaks",
                "projection_arg_order": ["person", "language"],
            },
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
            }
            ,
            {
                "pred_id": "person:speaks",
                "owner_type": "Person",
                "py_field_name": "speaks",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "language", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0, 1],
                "cardinality": "multi",
            },
            {
                "pred_id": "Speaks:exists",
                "owner_type": "Speaks",
                "is_record_exists": True,
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
            }
        ],
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _schema_for_where_record_sugar() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {"entity_type": "LivesIn", "identity_fields": [{"name": "uid", "type_domain": "string"}], "is_record": True},
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
                "is_record_exists": True,
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
