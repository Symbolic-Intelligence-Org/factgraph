from __future__ import annotations

import unittest

from factpy_kernel.authoring import (
    build_derivation_preview_from_authoring_dto,
    build_derivation_preview_dto,
    build_rule_preflight_from_authoring_dto,
    build_rule_preflight_dto,
    build_schema_preflight_dto,
    build_schema_preflight_from_authoring_dto,
)
from factpy_kernel.authoring.diagnostic_codes import (
    AUTHORING_DIAGNOSTIC_CODES_V1,
    AUTHORING_DIAGNOSTIC_PHASES_V1,
    CODE_EMPTY_PREDICATES,
    CODE_PREVIEW_TRUNCATED,
    CODE_RULE_COMPILE_ERROR,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store


class AuthoringDTOV1Tests(unittest.TestCase):
    def test_build_schema_preflight_dto_warning_status(self) -> None:
        schema = _schema()
        schema["predicates"] = []
        schema["projection"] = {"entities": [], "predicates": []}
        dto = build_schema_preflight_dto(schema)
        self.assertEqual(dto["authoring_ui_dto_version"], "authoring_ui_dto_v1")
        self.assertEqual(dto["kind"], "schema_preflight")
        self.assertEqual(dto["source_kind"], "schema")
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "warning")
        self.assertEqual(
            dto["diagnostics_contract"]["diagnostics_contract_version"],
            "authoring_diagnostics_contract_v1",
        )
        self.assertEqual(dto["diagnostics_contract"]["codes"], list(AUTHORING_DIAGNOSTIC_CODES_V1))
        self.assertEqual(dto["diagnostics_contract"]["phases"], list(AUTHORING_DIAGNOSTIC_PHASES_V1))
        self.assertEqual(dto["counts"]["diagnostic_count"], 0)
        self.assertEqual(dto["counts"]["warning_count"], 1)
        self.assertEqual(dto["warnings"][0]["code"], CODE_EMPTY_PREDICATES)

    def test_build_rule_preflight_dto_compile_error(self) -> None:
        store = Store(schema_ir=_schema())
        dto = build_rule_preflight_dto(
            store=store,
            rule_spec_payload={
                "rule_id": "rules.bad",
                "version": "v1",
                "select_vars": ["$E"],
                "where": [("pred", "missing:pred", ["$E"])],
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["kind"], "rule_preflight")
        self.assertEqual(dto["source_kind"], "rule")
        self.assertEqual(dto["diagnostics"][0]["code"], CODE_RULE_COMPILE_ERROR)
        self.assertEqual(dto["diagnostics"][0]["path"], "$.rule_spec_payload.where")
        self.assertIn("errors", dto)

    def test_build_schema_preflight_from_authoring_dto(self) -> None:
        dto = build_schema_preflight_from_authoring_dto(
            {
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [{"py_name": "country", "type_domain": "string", "cardinality": "functional"}],
                    }
                ]
            }
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["kind"], "schema_preflight")
        self.assertEqual(dto["source_kind"], "schema")
        self.assertEqual(dto["status"], "ok")
        self.assertIn("person:country", dto["summary"]["pred_ids"])

    def test_build_schema_preflight_from_authoring_dto_propagates_compile_path(self) -> None:
        dto = build_schema_preflight_from_authoring_dto(
            {
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [
                            {
                                "py_name": "name_by_lang",
                                "type_domain": "string",
                                "cardinality": "functional",
                                "dims": [{"name": "lang", "type_domain": "string"}],
                                "fact_key": ["missing_dim"],
                            }
                        ],
                    }
                ]
            }
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["diagnostics"][0]["path"], "$.entities[0].fields[0].fact_key[0]")

    def test_build_derivation_preview_dto_truncation_warning(self) -> None:
        store = Store(schema_ir=_schema())
        for idx in range(23):
            set_field(
                store.ledger,
                pred_id="person:country",
                e_ref=f"idref_v1:Person:authoring-dto-{idx}",
                rest_terms=[("string", f"c{idx}")],
                meta={"source": "seed"},
            )
        dto = build_derivation_preview_dto(
            store=store,
            derivation_id="drv.dto",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$C"],
            where=[("pred", "person:country", ["$E", "$C"])],
            mode="python",
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "warning")
        self.assertEqual(dto["kind"], "derivation_preview")
        self.assertEqual(dto["source_kind"], "derivation_dry_run")
        self.assertEqual(dto["summary"]["candidate_count"], 23)
        self.assertEqual(len(dto["summary"]["preview_candidates"]), 20)
        self.assertTrue(any(item["code"] == CODE_PREVIEW_TRUNCATED for item in dto["warnings"]))
        self.assertEqual(dto["counts"]["warning_count"], 1)
        self.assertEqual(dto["counts"]["diagnostic_count"], 0)

    def test_build_rule_preflight_from_authoring_dto(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-dto-rule-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        dto = build_rule_preflight_from_authoring_dto(
            store=store,
            authoring_rule_payload={
                "name": "rules.country_rows",
                "select": ["E", "C"],
                "body": [("pred", "person:country", ["$E", "$C"])],
                "public": True,
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "ok")
        self.assertEqual(dto["rule"]["rule_id"], "rules.country_rows")
        self.assertEqual(dto["rule"]["select_vars"], ["$E", "$C"])

    def test_build_rule_preflight_from_authoring_dto_compile_error_path(self) -> None:
        store = Store(schema_ir=_schema())
        dto = build_rule_preflight_from_authoring_dto(
            store=store,
            authoring_rule_payload={
                "rule_id": "rules.bad",
                "select": ["bad-name"],
                "body": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["diagnostics"][0]["path"], "$.select[0]")

    def test_build_derivation_preview_from_authoring_dto(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:authoring-dto-deriv-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        dto = build_derivation_preview_from_authoring_dto(
            store=store,
            authoring_derivation_payload={
                "name": "drv.country",
                "target": "person:country",
                "select": ["E", "C"],
                "body": [("pred", "person:country", ["$E", "$C"])],
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["kind"], "derivation_preview")
        self.assertEqual(dto["status"], "ok")
        self.assertEqual(dto["summary"]["candidate_count"], 1)

    def test_build_derivation_preview_from_authoring_dto_compile_error_path(self) -> None:
        store = Store(schema_ir=_schema())
        dto = build_derivation_preview_from_authoring_dto(
            store=store,
            authoring_derivation_payload={
                "derivation_id": "drv.bad",
                "target_pred_id": "person:country",
                "select": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "bad",
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["diagnostics"][0]["path"], "$.mode")


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


if __name__ == "__main__":
    unittest.main()
