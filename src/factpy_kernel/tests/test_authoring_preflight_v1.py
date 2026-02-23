from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy_kernel.authoring import (
    derivation_dry_run_preview,
    derivation_dry_run_preview_authoring,
    rule_preflight,
    rule_preflight_authoring,
    schema_preflight,
    schema_preflight_authoring,
)
from factpy_kernel.authoring.diagnostic_codes import (
    CODE_AUTHORING_DERIVATION_COMPILE_ERROR,
    CODE_AUTHORING_RULE_COMPILE_ERROR,
    CODE_AUTHORING_SCHEMA_COMPILE_ERROR,
    CODE_DERIVATION_PREVIEW_ERROR,
    CODE_EMPTY_PREDICATES,
    CODE_PREVIEW_TRUNCATED,
    CODE_REGISTRY_RULE_ERROR,
    CODE_RULE_COMPILE_ERROR,
    CODE_SCHEMA_VALIDATION_ERROR,
    CODE_SOUFFLE_BINARY_MISSING,
    CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store


class AuthoringPreflightV1Tests(unittest.TestCase):
    def test_schema_preflight_valid(self) -> None:
        payload = schema_preflight(_schema())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "schema")
        self.assertTrue(str(payload["schema_digest"]).startswith("sha256:"))
        self.assertIn("person:country", payload["summary"]["pred_ids"])
        self.assertEqual(payload["diagnostics"], [])
        self.assertEqual(payload["warnings"], [])

    def test_schema_preflight_invalid(self) -> None:
        bad = _schema()
        bad["predicates"][0]["arg_specs"][1]["type_domain"] = "float"
        payload = schema_preflight(bad)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["kind"], "schema")
        self.assertEqual(payload["errors"][0]["code"], CODE_SCHEMA_VALIDATION_ERROR)
        self.assertEqual(payload["diagnostics"][0]["phase"], "schema.validate")
        self.assertEqual(payload["diagnostics"][0]["path"], "$")
        self.assertEqual(payload["diagnostics"][0]["severity"], "error")
        self.assertEqual(payload["warnings"], [])

    def test_schema_preflight_empty_predicates_warning(self) -> None:
        schema = _schema()
        schema["predicates"] = []
        schema["projection"] = {"entities": [], "predicates": []}
        payload = schema_preflight(schema)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["diagnostics"], [])
        self.assertEqual(payload["warnings"][0]["code"], CODE_EMPTY_PREDICATES)
        self.assertEqual(payload["warnings"][0]["severity"], "warning")
        self.assertEqual(payload["warnings"][0]["path"], "$.predicates")

    def test_schema_preflight_authoring_success_and_compile_error(self) -> None:
        ok_payload = schema_preflight_authoring(_authoring_schema_basic())
        self.assertTrue(ok_payload["ok"])
        self.assertEqual(ok_payload["kind"], "schema")
        self.assertIn("person:has_age", ok_payload["summary"]["pred_ids"])

        bad_payload = schema_preflight_authoring({"entities": [{"entity_type": "Person", "identity_fields": [], "fields": []}]})
        self.assertFalse(bad_payload["ok"])
        self.assertEqual(bad_payload["diagnostics"][0]["phase"], "schema.authoring_compile")
        self.assertEqual(bad_payload["diagnostics"][0]["code"], CODE_AUTHORING_SCHEMA_COMPILE_ERROR)
        self.assertEqual(bad_payload["diagnostics"][0]["path"], "$.entities[0].identity_fields")

    def test_rule_preflight_valid_and_invalid(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        ok_payload = rule_preflight(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.country_rows",
                "version": "v1",
                "select_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "expose": True,
            },
        )
        self.assertTrue(ok_payload["ok"])
        self.assertEqual(ok_payload["kind"], "rule")
        self.assertEqual(ok_payload["summary"]["row_count"], 1)
        self.assertEqual(ok_payload["summary"]["preview_rows"][0][1], "de")
        self.assertEqual(ok_payload["diagnostics"], [])
        self.assertEqual(ok_payload["warnings"], [])

        bad_payload = rule_preflight(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.bad",
                "version": "v1",
                "select_vars": ["$E"],
                "where": [("pred", "unknown:pred", ["$E"])],
            },
        )
        self.assertFalse(bad_payload["ok"])
        self.assertEqual(bad_payload["errors"][0]["code"], CODE_RULE_COMPILE_ERROR)
        self.assertEqual(bad_payload["diagnostics"][0]["phase"], "rule.compile")
        self.assertEqual(bad_payload["diagnostics"][0]["path"], "$.rule_spec_payload.where")
        self.assertEqual(bad_payload["warnings"], [])

        registry_bad_payload = rule_preflight(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.country_rows",
                "version": "v1",
                "select_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
            },
            registry_payloads=[{"version": "v1", "select_vars": ["$E"], "where": [("pred", "x:y", ["$E"])]}],
        )
        self.assertFalse(registry_bad_payload["ok"])
        self.assertEqual(registry_bad_payload["diagnostics"][0]["code"], CODE_REGISTRY_RULE_ERROR)
        self.assertEqual(registry_bad_payload["diagnostics"][0]["phase"], "rule.registry")
        self.assertEqual(registry_bad_payload["diagnostics"][0]["path"], "$.registry_payloads[0]")
        self.assertEqual(registry_bad_payload["warnings"], [])

    def test_rule_preflight_authoring_success_and_compile_error(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-rule-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        ok_payload = rule_preflight_authoring(
            store=store,
            authoring_rule_payload={
                "name": "rules.country_rows",
                "version": "v1",
                "select": ["E", "C"],
                "body": [("pred", "person:country", ["$E", "$C"])],
                "public": True,
            },
        )
        self.assertTrue(ok_payload["ok"])
        self.assertEqual(ok_payload["summary"]["row_count"], 1)

        bad_payload = rule_preflight_authoring(
            store=store,
            authoring_rule_payload={
                "rule_id": "rules.bad",
                "select": ["bad-name"],
                "where": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertFalse(bad_payload["ok"])
        self.assertEqual(bad_payload["diagnostics"][0]["phase"], "rule.authoring_compile")
        self.assertEqual(bad_payload["diagnostics"][0]["code"], CODE_AUTHORING_RULE_COMPILE_ERROR)
        self.assertEqual(bad_payload["diagnostics"][0]["path"], "$.select[0]")

    def test_rule_preflight_warns_when_preview_truncated(self) -> None:
        store = Store(schema_ir=_schema())
        for idx in range(25):
            set_field(
                store.ledger,
                pred_id="person:country",
                e_ref=f"idref_v1:Person:authoring-rule-trunc-{idx}",
                rest_terms=[("string", f"c{idx}")],
                meta={"source": "seed"},
            )
        payload = rule_preflight(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.country_rows.trunc",
                "version": "v1",
                "select_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["row_count"], 25)
        self.assertEqual(len(payload["summary"]["preview_rows"]), 20)
        self.assertTrue(any(item["code"] == CODE_PREVIEW_TRUNCATED for item in payload["warnings"]))
        self.assertTrue(any(item["path"] == "$.summary.preview_rows" for item in payload["warnings"]))

    def test_derivation_dry_run_preview(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-2",
            rest_terms=[("string", "fr")],
            meta={"source": "seed"},
        )

        ok_payload = derivation_dry_run_preview(
            store=store,
            derivation_id="drv.country",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$C"],
            where=[("pred", "person:country", ["$E", "$C"])],
            mode="python",
        )
        self.assertTrue(ok_payload["ok"])
        self.assertEqual(ok_payload["kind"], "derivation_dry_run")
        self.assertEqual(ok_payload["summary"]["candidate_count"], 1)
        self.assertEqual(ok_payload["summary"]["preview_candidates"][0]["rest_terms"], [("string", "fr")])
        self.assertEqual(ok_payload["diagnostics"], [])
        self.assertEqual(ok_payload["warnings"], [])

        err_payload = derivation_dry_run_preview(
            store=store,
            derivation_id="drv.country",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$C"],
            where=[("pred", "missing:pred", ["$E", "$C"])],
            mode="python",
        )
        self.assertFalse(err_payload["ok"])
        self.assertEqual(err_payload["errors"][0]["code"], CODE_DERIVATION_PREVIEW_ERROR)
        self.assertEqual(err_payload["diagnostics"][0]["phase"], "derivation.preview")
        self.assertEqual(err_payload["diagnostics"][0]["path"], "$.where")
        self.assertEqual(err_payload["warnings"], [])

    def test_derivation_dry_run_preview_authoring_success_and_compile_error(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-deriv-1",
            rest_terms=[("string", "fr")],
            meta={"source": "seed"},
        )
        ok_payload = derivation_dry_run_preview_authoring(
            store=store,
            authoring_derivation_payload={
                "name": "drv.country",
                "target": "person:country",
                "select": ["E", "C"],
                "body": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertTrue(ok_payload["ok"])
        self.assertEqual(ok_payload["summary"]["candidate_count"], 1)

        head_payload = derivation_dry_run_preview_authoring(
            store=store,
            authoring_derivation_payload={
                "name": "drv.country.head",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "Person",
                    "field": "country",
                    "kwargs": {"person": "E", "country": "C"},
                },
                "materialize_as": "fact",
                "body": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertTrue(head_payload["ok"])
        self.assertEqual(head_payload["summary"]["candidate_count"], 1)

        record_store = Store(schema_ir=_schema_with_record_speaks())
        set_field(
            record_store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-deriv-record-1",
            rest_terms=[("string", "fr")],
            meta={"source": "seed"},
        )
        record_payload = derivation_dry_run_preview_authoring(
            store=record_store,
            authoring_derivation_payload={
                "name": "drv.speaks.record",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {
                        "person": "$E",
                        "language": "idref_v1:Language:cccccccccccccccccccccccccccccccccccccccccccccccccccc",
                    },
                },
                "materialize_as": "record",
                "body": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertTrue(record_payload["ok"])
        self.assertEqual(record_payload["summary"]["candidate_count"], 1)
        preview = record_payload["summary"]["preview_candidates"][0]
        self.assertEqual(preview["materialize_as"], "record")
        self.assertEqual(preview["record_type"], "Speaks")
        self.assertNotIn("id_policy", preview)
        self.assertEqual(len(preview["roles"]), 2)

        bad_payload = derivation_dry_run_preview_authoring(
            store=store,
            authoring_derivation_payload={
                "derivation_id": "drv.bad",
                "target_pred_id": "person:country",
                "select": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "bad",
            },
        )
        self.assertFalse(bad_payload["ok"])
        self.assertEqual(bad_payload["diagnostics"][0]["phase"], "derivation.authoring_compile")
        self.assertEqual(bad_payload["diagnostics"][0]["code"], CODE_AUTHORING_DERIVATION_COMPILE_ERROR)
        self.assertEqual(bad_payload["diagnostics"][0]["path"], "$.mode")

    def test_derivation_dry_run_warns_when_preview_truncated(self) -> None:
        store = Store(schema_ir=_schema())
        for idx in range(24):
            set_field(
                store.ledger,
                pred_id="person:country",
                e_ref=f"idref_v1:Person:authoring-deriv-trunc-{idx}",
                rest_terms=[("string", f"c{idx}")],
                meta={"source": "seed"},
            )
        payload = derivation_dry_run_preview(
            store=store,
            derivation_id="drv.country.trunc",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$C"],
            where=[("pred", "person:country", ["$E", "$C"])],
            mode="python",
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["candidate_count"], 24)
        self.assertEqual(len(payload["summary"]["preview_candidates"]), 20)
        self.assertTrue(any(item["code"] == CODE_PREVIEW_TRUNCATED for item in payload["warnings"]))
        self.assertTrue(any(item["path"] == "$.summary.preview_candidates" for item in payload["warnings"]))

    def test_derivation_dry_run_engine_warning_when_souffle_missing(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-3",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        with patch("factpy_kernel.authoring.preflight._find_souffle_binary_safe", return_value=None), patch(
            "factpy_kernel.adapters.souffle.runner.find_souffle_binary",
            return_value=None,
        ):
            payload = derivation_dry_run_preview(
                store=store,
                derivation_id="drv.country",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$C"],
                where=[("pred", "person:country", ["$E", "$C"])],
                mode="python",
            )
            self.assertEqual(payload["warnings"], [])

            engine_payload = derivation_dry_run_preview(
                store=store,
                derivation_id="drv.country",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$C"],
                where=[("pred", "person:country", ["$E", "$C"])],
                mode="engine",
            )
        self.assertFalse(engine_payload["ok"])
        self.assertTrue(any(item["code"] == CODE_SOUFFLE_BINARY_MISSING for item in engine_payload["warnings"]))
        self.assertTrue(any(item["severity"] == "warning" for item in engine_payload["warnings"]))

    def test_rule_preflight_warns_temporal_current_without_temporal_predicates(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-4",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        payload = rule_preflight(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.country_rows.current",
                "version": "v1",
                "select_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "expose": False,
            },
            temporal_view="current",
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(
            any(
                item["code"] == CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES
                for item in payload["warnings"]
            )
        )

    def test_rule_preflight_authoring_schema_aware_where_lowering_for_record_sugar(self) -> None:
        store = Store(schema_ir=_schema_with_record_speaks())
        payload = rule_preflight_authoring(
            store=store,
            authoring_rule_payload={
                "name": "rules.speaks_records",
                "select": ["s", "p", "l"],
                "where": [
                    ("pred", "Speaks:exists", ["$s"]),
                    ("pred", "speaks:person", ["$s", "$p"]),
                    ("pred", "speaks:language", ["$s", "$l"]),
                ],
            },
        )
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["summary"]["row_count"], 0)
        self.assertEqual(payload["diagnostics"], [])

    def test_derivation_dry_run_no_temporal_current_warning_when_temporal_predicate_referenced(self) -> None:
        store = Store(schema_ir=_schema_with_temporal())
        e_ref = "idref_v1:Person:authoring-5"
        set_field(
            store.ledger,
            pred_id="person:seen_at",
            e_ref=e_ref,
            rest_terms=[("time", 100)],
            meta={"source": "seed"},
        )
        payload = derivation_dry_run_preview(
            store=store,
            derivation_id="drv.seen_at",
            version="v1",
            target_pred_id="person:seen_at",
            head_vars=["$E", "$Ts"],
            where=[("pred", "person:seen_at", ["$E", "$Ts"])],
            mode="python",
            temporal_view="current",
        )
        self.assertTrue(payload["ok"])
        self.assertFalse(
            any(item["code"].startswith("temporal_current_") for item in payload["warnings"]),
            payload["warnings"],
        )


def _schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [{"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]}],
        "predicates": [
            {
                "pred_id": "person:country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            }
        ],
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _schema_with_temporal() -> dict:
    schema = _schema()
    schema["predicates"].append(
        {
            "pred_id": "person:seen_at",
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "seen_at", "type_domain": "time"},
            ],
            "group_key_indexes": [0],
            "cardinality": "temporal",
        }
    )
    schema["projection"]["predicates"] = ["person:country", "person:seen_at"]
    return schema


def _schema_with_record_speaks() -> dict:
    schema = _schema()
    schema["entities"].append(
        {
            "entity_type": "Speaks",
            "identity_fields": [{"name": "uid", "type_domain": "string"}],
            "is_record": True,
        }
    )
    schema["predicates"].extend(
        [
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
            },
        ]
    )
    schema["projection"]["predicates"] = [
        "person:country",
        "Speaks:exists",
        "speaks:person",
        "speaks:language",
    ]
    return schema


def _authoring_schema_basic() -> dict:
    return {
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "source_system", "type_domain": "string"},
                    {"name": "source_id", "type_domain": "string"},
                ],
                "fields": [
                    {"py_name": "age", "name": "has_age", "type_domain": "int", "cardinality": "functional"},
                    {"py_name": "country", "type_domain": "string", "cardinality": "functional"},
                ],
            }
        ]
    }


if __name__ == "__main__":
    unittest.main()
