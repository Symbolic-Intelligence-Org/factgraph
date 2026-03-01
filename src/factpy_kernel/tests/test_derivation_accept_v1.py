from __future__ import annotations

import unittest

from factpy_kernel.authoring import compile_authoring_derivation_v1
from factpy_kernel.core.derivation.accept import AcceptOptions
from factpy_kernel.core.derivation.candidates import CandidateSet, make_candidate
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError, now_epoch_nanos, set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.store.runtime import Store


class DerivationAcceptV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
                {"entity_type": "Language", "identity_fields": [{"name": "code", "type_domain": "string"}]},
                {
                    "entity_type": "Speaks",
                    "identity_fields": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "language", "type_domain": "entity_ref"},
                    ],
                },
                {
                    "entity_type": "User",
                    "identity_fields": [
                        {"name": "source_system", "type_domain": "string"},
                        {"name": "source_id", "type_domain": "string"},
                    ],
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
                {
                    "pred_id": "User:exists",
                    "owner_type": "User",
                    "is_entity_exists": True,
                    "arg_specs": [{"name": "user", "type_domain": "entity_ref"}],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "user:name",
                    "owner_type": "User",
                    "py_field_name": "name",
                    "arg_specs": [
                        {"name": "user", "type_domain": "entity_ref"},
                        {"name": "name", "type_domain": "string"},
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
        self.person_ref = encode_idref_v1("Person", [("source_id", "string", "u1")])
        self.lang_ref = encode_idref_v1("Language", [("code", "string", "de")])

    def test_evaluate_entity_head_emits_entity_and_fact_candidates(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        compiled = compile_authoring_derivation_v1(
            {
                "derivation_id": "derive_speaks_from_country",
                "version": "v1",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$E", "language": self.lang_ref},
                },
                "where": [("pred", "person:country", ["$E", "de"])],
            },
            schema_ir=self.schema_ir,
        )
        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            head=compiled["head"],
            mode="python",
        )
        self.assertEqual(len(candidates), 3)
        entity_candidates = [cand for cand in candidates if cand.candidate_kind == "entity"]
        fact_candidates = [cand for cand in candidates if cand.candidate_kind == "fact"]
        self.assertEqual(len(entity_candidates), 1)
        self.assertEqual(len(fact_candidates), 2)
        entity = entity_candidates[0]
        self.assertEqual(entity.target, "Speaks")
        for fact in fact_candidates:
            self.assertEqual(fact.payload["terms"][0]["kind"], "candidate_ref")
            self.assertEqual(fact.payload["terms"][0]["candidate_key"], entity.candidate_key)

    def test_accept_many_atomic_accepts_entity_and_dependent_facts(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        compiled = compile_authoring_derivation_v1(
            {
                "derivation_id": "derive_speaks_atomic",
                "version": "v1",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$E", "language": self.lang_ref},
                },
                "where": [("pred", "person:country", ["$E", "de"])],
            },
            schema_ir=self.schema_ir,
        )
        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            head=compiled["head"],
            mode="python",
        )
        rows = self.store.accept_many(candidates, mode="atomic")
        self.assertEqual({row["state"] for row in rows}, {"ACCEPTED"})
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:person")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:language")), 1)

    def test_accept_many_best_effort_blocks_fact_when_entity_identity_incomplete(self) -> None:
        entity_candidate = make_candidate(
            derivation_id="derive_user",
            derivation_version="v1",
            run_id="run_u1",
            target="User",
            key_terms=[("string", "User"), ("string", "APP"), ("string", "missing")],
            payload={
                "entity_type": "User",
                "identity_fields": ["source_system", "source_id"],
                "identity_types": {"source_system": "string", "source_id": "string"},
                "resolved_identity": {"source_system": "APP"},
                "missing_identity_fields": ["source_id"],
                "proposed_entity_ref": None,
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=now_epoch_nanos(),
            candidate_kind="entity",
        )
        fact_candidate = make_candidate(
            derivation_id="derive_user",
            derivation_version="v1",
            run_id="run_u1",
            target="user:name",
            key_terms=[("string", "user:name"), ("string", entity_candidate.candidate_key)],
            payload={
                "pred_id": "user:name",
                "terms": [
                    {"kind": "candidate_ref", "candidate_key": entity_candidate.candidate_key},
                    {"kind": "literal", "tag": "string", "value": "Alice"},
                ],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=now_epoch_nanos(),
            candidate_kind="fact",
        )
        rows = self.store.accept_many([entity_candidate, fact_candidate], mode="best_effort")
        by_key = {row["candidate_key"]: row for row in rows}
        self.assertEqual(by_key[entity_candidate.candidate_key]["state"], "FAILED_VALIDATION")
        self.assertEqual(by_key[fact_candidate.candidate_key]["state"], "BLOCKED_DEPENDENCY")
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="User:exists")), 0)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="user:name")), 0)

    def test_entity_accept_requires_identity_override(self) -> None:
        entity_candidate = make_candidate(
            derivation_id="derive_user",
            derivation_version="v1",
            run_id="run_u2",
            target="User",
            key_terms=[("string", "User"), ("string", "APP"), ("string", "missing")],
            payload={
                "entity_type": "User",
                "identity_fields": ["source_system", "source_id"],
                "identity_types": {"source_system": "string", "source_id": "string"},
                "resolved_identity": {"source_system": "APP"},
                "missing_identity_fields": ["source_id"],
                "proposed_entity_ref": None,
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=now_epoch_nanos(),
            candidate_kind="entity",
        )
        with self.assertRaises(WriteProtocolError):
            self.store.accept(
                derivation_id=entity_candidate.derivation_id,
                version=entity_candidate.derivation_version,
                candidate_set=entity_candidate,
                options=AcceptOptions(),
            )
        result = self.store.accept(
            derivation_id=entity_candidate.derivation_id,
            version=entity_candidate.derivation_version,
            candidate_set=entity_candidate,
            options=AcceptOptions(identity_override={"source_id": "u-1"}),
        )
        self.assertEqual(result.accepted_count, 1)
        self.assertTrue(isinstance(result.entity_ref, str) and result.entity_ref.startswith("idref_v1:User:"))

    def test_identity_override_conflict_and_unknown_field_raise(self) -> None:
        entity_candidate = make_candidate(
            derivation_id="derive_user",
            derivation_version="v1",
            run_id="run_u3",
            target="User",
            key_terms=[("string", "User"), ("string", "APP"), ("string", "u-1")],
            payload={
                "entity_type": "User",
                "identity_fields": ["source_system", "source_id"],
                "identity_types": {"source_system": "string", "source_id": "string"},
                "resolved_identity": {"source_system": "APP", "source_id": "u-1"},
                "missing_identity_fields": [],
                "proposed_entity_ref": encode_idref_v1(
                    "User",
                    [("source_system", "string", "APP"), ("source_id", "string", "u-1")],
                ),
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=now_epoch_nanos(),
            candidate_kind="entity",
        )
        with self.assertRaises(WriteProtocolError):
            self.store.accept(
                derivation_id=entity_candidate.derivation_id,
                version=entity_candidate.derivation_version,
                candidate_set=entity_candidate,
                options=AcceptOptions(identity_override={"source_id": "u-2"}),
            )
        with self.assertRaises(WriteProtocolError):
            self.store.accept(
                derivation_id=entity_candidate.derivation_id,
                version=entity_candidate.derivation_version,
                candidate_set=entity_candidate,
                options=AcceptOptions(identity_override={"unknown": "x"}),
            )

    def test_legacy_fact_payload_is_rejected_at_candidate_construction(self) -> None:
        with self.assertRaises(ValueError):
            CandidateSet(
                derivation_id="legacy_d",
                derivation_version="v1",
                run_id="legacy_run",
                target="person:country",
                key_tuple_digest="sha256:" + ("0" * 64),
                tup_digest=None,
                payload={
                    "e_ref": self.person_ref,
                    "rest_terms": [("string", "de")],
                },
                support_digest="sha256:" + ("0" * 64),
                support_kind="none",
                generated_at=now_epoch_nanos(),
                state="generated",
                candidate_kind="fact",
            )


if __name__ == "__main__":
    unittest.main()
