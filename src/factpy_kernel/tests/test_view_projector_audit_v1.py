from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.view.projector import (
    ProjectorAudit,
    project_view_facts,
    project_view_facts_with_audit,
)


class ViewProjectorAuditV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "schema_ir_v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                },
            ],
            "predicates": [
                {
                    "pred_id": "person:country",
                    "arg_specs": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:nick",
                    "arg_specs": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "nick", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "temporal",
                },
            ],
            "projection": {"entities": [], "predicates": []},
            "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
            "generated_at": "2026-01-01T00:00:00Z",
        }
        self.store = Store(schema_ir=self.schema_ir)
        self.person_ref = "idref_v1:Person:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_project_view_facts_with_audit_matches_default_api(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )

        facts_default = project_view_facts(self.store.ledger, self.schema_ir)
        facts_audit, audit = project_view_facts_with_audit(self.store.ledger, self.schema_ir)

        self.assertEqual(facts_default, facts_audit)
        self.assertEqual(audit.contract_version, 2)
        self.assertIsInstance(audit, ProjectorAudit)
        self._assert_audit_invariants(audit)

    def test_temporal_active_vs_current(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:nick",
            e_ref=self.person_ref,
            rest_terms=[("string", "neo")],
            meta={"source": "seed"},
        )
        set_field(
            self.store.ledger,
            pred_id="person:nick",
            e_ref=self.person_ref,
            rest_terms=[("string", "one")],
            meta={"source": "seed"},
        )

        facts_active, audit_active = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            temporal_view="active",
        )
        facts_current, audit_current = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            temporal_view="current",
        )

        self.assertEqual(len(facts_active["person:nick"]), 2)
        self.assertEqual(len(facts_current["person:nick"]), 1)
        self.assertGreaterEqual(audit_active.selected_claim_count, audit_current.selected_claim_count)
        self._assert_audit_invariants(audit_active)
        self._assert_audit_invariants(audit_current)

    def test_audit_reports_policy_drops_for_functional_predicate(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "fr")],
            meta={"source": "seed"},
        )

        _, audit = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            temporal_view="active",
        )
        self.assertGreaterEqual(audit.dropped_by_policy_count, 1)
        self._assert_audit_invariants(audit)

    def _assert_audit_invariants(self, audit: ProjectorAudit) -> None:
        self.assertEqual(audit.contract_version, 2)
        self.assertGreaterEqual(audit.predicate_count, 0)
        self.assertGreaterEqual(audit.active_claim_count, 0)
        self.assertGreaterEqual(audit.selected_claim_count, 0)
        self.assertGreaterEqual(audit.active_claim_count, audit.selected_claim_count)
        self.assertEqual(audit.selected_claim_count, sum(audit.selected_by_pred.values()))


if __name__ == "__main__":
    unittest.main()
