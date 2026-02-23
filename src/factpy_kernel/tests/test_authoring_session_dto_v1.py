from __future__ import annotations

import unittest

from factpy_kernel.authoring import AuthoringSessionError, build_authoring_session_dto
from factpy_kernel.authoring.diagnostic_codes import (
    AUTHORING_DIAGNOSTIC_CODES_V1,
    AUTHORING_DIAGNOSTIC_PHASES_V1,
    CODE_RULE_COMPILE_ERROR,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store


class AuthoringSessionDTOV1Tests(unittest.TestCase):
    def test_session_dto_all_ok(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:session-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        dto = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            rule_request={
                "rule_spec_payload": {
                    "rule_id": "rules.country_rows",
                    "version": "v1",
                    "select_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                }
            },
            derivation_request={
                "derivation_id": "drv.country",
                "version": "v1",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "python",
            },
        )
        self.assertEqual(dto["authoring_session_dto_version"], "authoring_session_dto_v1")
        self.assertEqual(
            dto["diagnostics_contract"]["diagnostics_contract_version"],
            "authoring_diagnostics_contract_v1",
        )
        self.assertEqual(dto["diagnostics_contract"]["codes"], list(AUTHORING_DIAGNOSTIC_CODES_V1))
        self.assertEqual(dto["diagnostics_contract"]["phases"], list(AUTHORING_DIAGNOSTIC_PHASES_V1))
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "ok")
        self.assertEqual(dto["order"], ["schema_preflight", "rule_preflight", "derivation_preview"])
        self.assertEqual(dto["summary"]["section_count"], 3)
        self.assertEqual(dto["summary"]["diagnostic_count"], 0)
        self.assertEqual(dto["summary"]["warning_count"], 0)
        self.assertEqual(dto["summary"]["status_counts"]["ok"], 3)
        self.assertEqual(dto["sections"]["rule_preflight"]["summary"]["row_count"], 1)
        self.assertEqual(dto["sections"]["derivation_preview"]["summary"]["candidate_count"], 1)

    def test_session_dto_aggregates_warnings(self) -> None:
        store = Store(schema_ir=_schema())
        for idx in range(22):
            set_field(
                store.ledger,
                pred_id="person:country",
                e_ref=f"idref_v1:Person:session-warn-{idx}",
                rest_terms=[("string", f"c{idx}")],
                meta={"source": "seed"},
            )
        schema_warn = _schema()
        schema_warn["predicates"] = []
        schema_warn["projection"] = {"entities": [], "predicates": []}
        dto = build_authoring_session_dto(
            store=store,
            schema_ir=schema_warn,
            derivation_request={
                "derivation_id": "drv.country.warn",
                "version": "v1",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "python",
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "warning")
        self.assertEqual(dto["summary"]["warning_count"], 2)
        self.assertEqual(dto["summary"]["diagnostic_count"], 0)
        self.assertEqual(dto["summary"]["status_counts"]["warning"], 2)

    def test_session_dto_error_aggregation(self) -> None:
        store = Store(schema_ir=_schema())
        dto = build_authoring_session_dto(
            store=store,
            rule_request={
                "rule_spec_payload": {
                    "rule_id": "rules.bad",
                    "version": "v1",
                    "select_vars": ["$E"],
                    "where": [("pred", "missing:pred", ["$E"])],
                }
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["summary"]["diagnostic_count"], 1)
        self.assertEqual(dto["summary"]["status_counts"]["error"], 1)
        self.assertEqual(
            dto["sections"]["rule_preflight"]["diagnostics"][0]["code"],
            CODE_RULE_COMPILE_ERROR,
        )

    def test_session_dto_requires_store_for_rule_or_derivation(self) -> None:
        with self.assertRaises(AuthoringSessionError):
            build_authoring_session_dto(
                rule_request={
                    "rule_spec_payload": {
                        "rule_id": "rules.x",
                        "version": "v1",
                        "select_vars": ["$E"],
                        "where": [("pred", "person:country", ["$E"])],
                    }
                }
            )

    def test_session_dto_auto_compiles_authoring_schema_and_builds_store(self) -> None:
        dto = build_authoring_session_dto(
            authoring_schema={
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [
                            {"py_name": "country", "type_domain": "string", "cardinality": "functional"},
                        ],
                    }
                ]
            },
            rule_request={
                "rule_spec_payload": {
                    "rule_id": "rules.country_rows",
                    "version": "v1",
                    "select_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                }
            },
            derivation_request={
                "derivation_id": "drv.country",
                "version": "v1",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "python",
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["status"], "ok")
        self.assertEqual(dto["summary"]["section_count"], 3)
        self.assertEqual(dto["sections"]["schema_preflight"]["kind"], "schema_preflight")
        self.assertEqual(dto["sections"]["rule_preflight"]["summary"]["row_count"], 0)
        self.assertEqual(dto["sections"]["derivation_preview"]["summary"]["candidate_count"], 0)

    def test_session_dto_authoring_schema_compile_error_has_granular_path(self) -> None:
        dto = build_authoring_session_dto(
            authoring_schema={
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [
                            {
                                "py_name": "country_by_lang",
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
        self.assertEqual(dto["sections"]["schema_preflight"]["diagnostics"][0]["path"], "$.entities[0].fields[0].fact_key[0]")

    def test_session_dto_accepts_authoring_rule_payload(self) -> None:
        dto = build_authoring_session_dto(
            authoring_schema={
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [{"py_name": "country", "type_domain": "string", "cardinality": "functional"}],
                    }
                ]
            },
            rule_request={
                "authoring_rule_payload": {
                    "name": "rules.country_rows",
                    "select": ["E", "C"],
                    "body": [("pred", "person:country", ["$E", "$C"])],
                    "public": True,
                }
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["sections"]["rule_preflight"]["rule"]["rule_id"], "rules.country_rows")
        self.assertEqual(dto["sections"]["rule_preflight"]["rule"]["select_vars"], ["$E", "$C"])

    def test_session_dto_authoring_rule_compile_error_path(self) -> None:
        dto = build_authoring_session_dto(
            authoring_schema={
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [{"py_name": "country", "type_domain": "string", "cardinality": "functional"}],
                    }
                ]
            },
            rule_request={
                "authoring_rule_payload": {
                    "rule_id": "rules.bad",
                    "select": ["bad-name"],
                    "body": [("pred", "person:country", ["$E", "$C"])],
                }
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["sections"]["rule_preflight"]["diagnostics"][0]["path"], "$.select[0]")

    def test_session_dto_accepts_authoring_derivation_payload(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:session-deriv-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        dto = build_authoring_session_dto(
            store=store,
            derivation_request={
                "authoring_derivation_payload": {
                    "name": "drv.country",
                    "target": "person:country",
                    "select": ["E", "C"],
                    "body": [("pred", "person:country", ["$E", "$C"])],
                }
            },
        )
        self.assertTrue(dto["ok"])
        self.assertEqual(dto["sections"]["derivation_preview"]["summary"]["candidate_count"], 1)

    def test_session_dto_authoring_derivation_compile_error_path(self) -> None:
        dto = build_authoring_session_dto(
            authoring_schema={
                "entities": [
                    {
                        "entity_type": "Person",
                        "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                        "fields": [{"py_name": "country", "type_domain": "string", "cardinality": "functional"}],
                    }
                ]
            },
            derivation_request={
                "authoring_derivation_payload": {
                    "derivation_id": "drv.bad",
                    "target_pred_id": "person:country",
                    "select": ["$E", "$C"],
                    "body": [("pred", "person:country", ["$E", "$C"])],
                    "mode": "bad",
                }
            },
        )
        self.assertFalse(dto["ok"])
        self.assertEqual(dto["status"], "error")
        self.assertEqual(dto["sections"]["derivation_preview"]["diagnostics"][0]["path"], "$.mode")


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
