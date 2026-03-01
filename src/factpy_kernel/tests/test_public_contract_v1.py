from __future__ import annotations

import warnings
import unittest
from unittest.mock import patch

import factpy_kernel.tests._warnings as test_warnings
from factpy_kernel.core.derivation.accept import AcceptOptions
from factpy_kernel.core.schema.schema_ir import SchemaIRValidationError
from factpy_kernel.core.view.projector import project_view_facts_with_audit
from factpy_kernel.service.rules_v1 import validate_rule
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


def setUpModule() -> None:
    test_warnings.install_test_warning_filters()


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")


class PublicContractV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person])
        self.p_ref = self.sdk.ref(Person, source_id="u1")

    def test_accept_result_diagnostics_contract_version_and_diag_item_shape(self) -> None:
        candidate = self.sdk.store.evaluate_dummy(
            derivation_id="drv.copy_country",
            version="1.0.0",
            target="person:country",
            e_ref=self.p_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )
        with patch(
            "factpy_kernel.core.store._accept.compute_schema_digest",
            side_effect=SchemaIRValidationError("boom"),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = self.sdk.store.accept(
                    derivation_id=candidate.derivation_id,
                    version=candidate.derivation_version,
                    candidate_set=candidate,
                    options=AcceptOptions(),
                )

        self.assertEqual(result.diagnostics_contract_version, 1)
        self.assertGreaterEqual(len(result.diagnostics), 1)
        diag = result.diagnostics[0]
        self.assertIsInstance(diag, dict)
        self.assertEqual(
            {"code", "severity", "path", "message", "data"}.issubset(set(diag.keys())),
            True,
        )
        self.assertIsInstance(diag["code"], str)
        self.assertIsInstance(diag["severity"], str)
        self.assertTrue(diag["severity"] in {"info", "warning", "error"})
        self.assertTrue(diag["path"] is None or isinstance(diag["path"], str))
        self.assertIsInstance(diag["message"], str)
        self.assertIsInstance(diag["data"], dict)

    def test_projector_audit_contract_version_and_invariants(self) -> None:
        facts, audit = project_view_facts_with_audit(self.sdk.ledger, self.sdk.schema_ir)
        self.assertIn("person:country", facts)
        self.assertEqual(audit.contract_version, 2)
        self.assertGreaterEqual(audit.predicate_count, 1)
        self.assertGreaterEqual(audit.active_claim_count, audit.selected_claim_count)
        self.assertEqual(audit.selected_claim_count, sum(audit.selected_by_pred.values()))

    def test_facade_rule_string_dsl_is_rejected_with_stable_kind(self) -> None:
        body = validate_rule(
            {
                "api_version": "v1",
                "mode": "souffle",
                "rule": "q_country_rows := person:country($E, $C).",
            }
        )
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["kind"], "string_dsl_unsupported")
        self.assertEqual(body["errors"][0]["path"], "$.rule")
        self.assertEqual(body["errors"][0]["details"]["strategy"], "object_rule_only")

    def test_sdk_string_rule_and_derivation_dsl_are_rejected(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx_rule:
            self.sdk.run("q_country_rows := person:country($E, $C).")
        self.assertIn("string rule DSL is not supported in SDK v1", str(ctx_rule.exception))

        with self.assertRaises(SDKStoreError) as ctx_drv:
            self.sdk.evaluate("drv.copy_country := person:country($E, $C).")
        self.assertIn("string derivation DSL is not supported in SDK v1", str(ctx_drv.exception))


if __name__ == "__main__":
    unittest.main()
