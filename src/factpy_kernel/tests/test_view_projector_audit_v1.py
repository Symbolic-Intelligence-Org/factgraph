from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.record_staging import RECORD_STAGE_MARKER_PRED_ID
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
                {
                    "entity_type": "Speaks",
                    "identity_fields": [{"name": "key", "type_domain": "string"}],
                    "is_record": True,
                    "projection_pred_id": "person:speaks",
                    "projection_arg_order": ["person", "language"],
                },
                {
                    "entity_type": "Language",
                    "identity_fields": [{"name": "code", "type_domain": "string"}],
                },
            ],
            "predicates": [
                {
                    "pred_id": "person:country",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "Speaks:exists",
                    "owner_type": "Speaks",
                    "is_record_exists": True,
                    "arg_specs": [{"name": "S", "type_domain": "entity_ref"}],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "speaks:person",
                    "owner_type": "Speaks",
                    "py_field_name": "person",
                    "arg_specs": [
                        {"name": "S", "type_domain": "entity_ref"},
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
                        {"name": "S", "type_domain": "entity_ref"},
                        {"name": "language", "type_domain": "entity_ref"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {"entities": [], "predicates": []},
            "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
            "generated_at": "2026-01-01T00:00:00Z",
        }
        self.store = Store(schema_ir=self.schema_ir)
        self.person_ref = "idref_v1:Person:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        self.lang_ref = "idref_v1:Language:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

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

        self.assertEqual(facts_audit, facts_default)
        self.assertEqual(audit.contract_version, 1)
        self.assertEqual(audit, ProjectorAudit())
        self._assert_audit_invariants(audit)

    def test_audit_counts_legacy_records_by_exists_unit_and_exists_without_roles(self) -> None:
        record_e_ref = "idref_v1:Speaks:legacy-1"
        legacy_meta = {
            "source": "seed",
            "materialize_kind": "record",
            "materialize_id": "mat-legacy-1",
            "key_tuple_digest": "sha256:" + ("1" * 64),
            "cand_key_digest": "sha256:" + ("2" * 64),
            "record_type": "Speaks",
            "record_e_ref": record_e_ref,
            "record_id_policy": "key_tuple_digest_v1",
        }
        set_field(
            self.store.ledger,
            pred_id="Speaks:exists",
            e_ref=record_e_ref,
            rest_terms=[],
            meta=legacy_meta,
        )
        # Role-only legacy group should not inflate exists-unit legacy counters.
        set_field(
            self.store.ledger,
            pred_id="speaks:person",
            e_ref="idref_v1:Speaks:legacy-role-only",
            rest_terms=[("entity_ref", self.person_ref)],
            meta={**legacy_meta, "materialize_id": "mat-legacy-role-only", "record_e_ref": "idref_v1:Speaks:legacy-role-only"},
        )

        facts, audit = project_view_facts_with_audit(self.store.ledger, self.schema_ir)

        self.assertEqual(audit.legacy_record_total, 1)
        self.assertEqual(audit.legacy_record_by_pred, {"Speaks:exists": 1})
        self.assertEqual(audit.legacy_exists_without_roles_total, 1)
        self.assertEqual(audit.legacy_exists_without_roles_by_pred, {"Speaks:exists": 1})
        self.assertEqual(len(facts["Speaks:exists"]), 1)
        self._assert_audit_invariants(audit)

    def test_legacy_record_visibility_allow_and_audit_match_but_deny_hides_legacy_records(self) -> None:
        record_e_ref = "idref_v1:Speaks:legacy-visibility"
        legacy_meta = {
            "source": "seed",
            "materialize_kind": "record",
            "materialize_id": "mat-legacy-visibility",
            "key_tuple_digest": "sha256:" + ("7" * 64),
            "cand_key_digest": "sha256:" + ("8" * 64),
            "record_type": "Speaks",
            "record_e_ref": record_e_ref,
            "record_id_policy": "key_tuple_digest_v1",
        }
        set_field(
            self.store.ledger,
            pred_id="Speaks:exists",
            e_ref=record_e_ref,
            rest_terms=[],
            meta=legacy_meta,
        )
        set_field(
            self.store.ledger,
            pred_id="speaks:person",
            e_ref=record_e_ref,
            rest_terms=[("entity_ref", self.person_ref)],
            meta=legacy_meta,
        )

        facts_allow, audit_allow = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            legacy_record_visibility="allow",
        )
        facts_audit, audit_mode = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            legacy_record_visibility="audit",
        )
        facts_deny, audit_deny = project_view_facts_with_audit(
            self.store.ledger,
            self.schema_ir,
            legacy_record_visibility="deny",
        )

        self.assertEqual(facts_allow, facts_audit)
        self.assertEqual(len(facts_allow["Speaks:exists"]), 1)
        self.assertEqual(len(facts_allow["speaks:person"]), 1)
        self.assertEqual(facts_deny["Speaks:exists"], [])
        self.assertEqual(facts_deny["speaks:person"], [])
        # `audit` mode is visibility-compatible with `allow`; it only affects observability.
        self.assertEqual(audit_allow.legacy_record_total, 1)
        self.assertEqual(audit_mode.legacy_record_total, 1)
        self.assertEqual(audit_deny.legacy_record_total, 1)
        self._assert_audit_invariants(audit_allow)
        self._assert_audit_invariants(audit_mode)
        self._assert_audit_invariants(audit_deny)

    def test_audit_counts_marker_conflict_by_reason(self) -> None:
        record_e_ref, materialize_id, record_digest = self._write_legacy_record_claims_and_committed_marker(
            suffix="3",
            include_language=False,
        )
        self.assertTrue(record_digest.startswith("sha256:"))

        set_field(
            self.store.ledger,
            pred_id=RECORD_STAGE_MARKER_PRED_ID,
            e_ref=record_e_ref,
            rest_terms=[
                ("string", materialize_id),
                ("string", "begin"),
                ("string", "sha256:" + ("f" * 64)),
            ],
            meta={"source": "test", "roles_count_expected": 1},
        )

        facts, audit = project_view_facts_with_audit(self.store.ledger, self.schema_ir)

        self.assertEqual(facts["Speaks:exists"], [])
        self.assertEqual(facts["speaks:person"], [])
        self.assertEqual(audit.marker_conflict_total, 1)
        self.assertEqual(audit.marker_conflict_by_reason.get("committed_and_inflight_mismatch"), 1)
        self._assert_audit_invariants(audit)

    def test_audit_counts_committed_hidden_count_mismatch(self) -> None:
        record_e_ref, materialize_id, _ = self._write_legacy_record_claims_and_committed_marker(
            suffix="4",
            include_language=False,
        )
        self._rewrite_stage_roles_count_expected(e_ref=record_e_ref, materialize_id=materialize_id, new_value=2)

        facts, audit = project_view_facts_with_audit(self.store.ledger, self.schema_ir)

        self.assertEqual(facts["Speaks:exists"], [])
        self.assertEqual(facts["speaks:person"], [])
        self.assertEqual(audit.committed_hidden_count_mismatch_total, 1)
        self.assertEqual(audit.committed_hidden_count_mismatch_by_pred, {"Speaks:exists": 1})
        self._assert_audit_invariants(audit)

    def _write_legacy_record_claims_and_committed_marker(
        self,
        *,
        suffix: str,
        include_language: bool,
    ) -> tuple[str, str, str]:
        record_e_ref = f"idref_v1:Speaks:legacy-seeded-{suffix}"
        materialize_id = f"mat-legacy-seeded-{suffix}"
        record_digest = "sha256:" + (suffix * 64)
        legacy_meta = {
            "source": "seed",
            "materialize_kind": "record",
            "materialize_id": materialize_id,
            "key_tuple_digest": "sha256:" + (suffix * 64),
            "cand_key_digest": "sha256:" + ("9" * 64),
            "record_type": "Speaks",
            "record_e_ref": record_e_ref,
            "record_id_policy": "key_tuple_digest_v1",
            "record_digest": record_digest,
        }
        set_field(
            self.store.ledger,
            pred_id="speaks:person",
            e_ref=record_e_ref,
            rest_terms=[("entity_ref", self.person_ref)],
            meta=legacy_meta,
        )
        if include_language:
            set_field(
                self.store.ledger,
                pred_id="speaks:language",
                e_ref=record_e_ref,
                rest_terms=[("entity_ref", self.lang_ref)],
                meta=legacy_meta,
            )
        set_field(
            self.store.ledger,
            pred_id="Speaks:exists",
            e_ref=record_e_ref,
            rest_terms=[],
            meta=legacy_meta,
        )
        set_field(
            self.store.ledger,
            pred_id=RECORD_STAGE_MARKER_PRED_ID,
            e_ref=record_e_ref,
            rest_terms=[
                ("string", materialize_id),
                ("string", "committed"),
                ("string", record_digest),
            ],
            meta={
                "source": "seed",
                "roles_count_expected": 1 if not include_language else 2,
                "materialize_kind": "record_stage",
                "record_type": "Speaks",
                "record_e_ref": record_e_ref,
                "materialize_id": materialize_id,
                "key_tuple_digest": legacy_meta["key_tuple_digest"],
                "cand_key_digest": legacy_meta["cand_key_digest"],
                "record_digest": record_digest,
            },
        )
        return record_e_ref, materialize_id, record_digest

    def _rewrite_stage_roles_count_expected(self, *, e_ref: str, materialize_id: str, new_value: int) -> None:
        stage_asrt_ids: set[str] = set()
        for claim in self.store.ledger.find_claims(pred_id=RECORD_STAGE_MARKER_PRED_ID, e_ref=e_ref):
            if len(claim.rest_terms) != 3:
                continue
            first_term = claim.rest_terms[0]
            if not (isinstance(first_term, tuple) and len(first_term) == 2):
                continue
            tag, value = first_term
            if tag == "string" and value == materialize_id:
                stage_asrt_ids.add(claim.asrt_id)
        updated = list(self.store.ledger.meta_rows)
        for idx, row in enumerate(updated):
            if row.asrt_id in stage_asrt_ids and row.key == "roles_count_expected":
                updated[idx] = row.__class__(
                    asrt_id=row.asrt_id,
                    key=row.key,
                    kind="num",
                    value=new_value,
                )
        self.store.ledger._force_replace_meta_rows(updated)

    def _assert_audit_invariants(self, audit: ProjectorAudit) -> None:
        self.assertEqual(audit.contract_version, 1)
        self.assertEqual(audit.legacy_record_total, sum(audit.legacy_record_by_pred.values()))
        self.assertEqual(audit.marker_conflict_total, sum(audit.marker_conflict_by_reason.values()))
        self.assertEqual(
            audit.committed_hidden_count_mismatch_total,
            sum(audit.committed_hidden_count_mismatch_by_pred.values()),
        )


if __name__ == "__main__":
    unittest.main()
