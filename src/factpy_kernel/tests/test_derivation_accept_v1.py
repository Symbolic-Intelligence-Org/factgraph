from __future__ import annotations

import unittest
import warnings

from factpy_kernel.authoring import compile_authoring_derivation_v1
from factpy_kernel.core.derivation.accept import (
    AcceptOptions,
    LegacyAcceptFallbackWarning,
)
from factpy_kernel.core.derivation.candidates import make_candidate
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError, now_epoch_nanos, set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.store.api import Store


class DerivationAcceptV2Tests(unittest.TestCase):
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
                    "identity_fields": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "language", "type_domain": "entity_ref"},
                    ],
                    "is_record": True,
                    "projection_pred_id": "person:speaks",
                    "projection_arg_order": ["person", "language"],
                },
                {
                    "entity_type": "Language",
                    "identity_fields": [{"name": "code", "type_domain": "string"}],
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
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:speaks",
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
                    "is_entity_exists": True,
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
                {
                    "pred_id": "User:exists",
                    "owner_type": "User",
                    "is_record_exists": True,
                    "is_entity_exists": True,
                    "arg_specs": [{"name": "U", "type_domain": "entity_ref"}],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "user:name",
                    "owner_type": "User",
                    "py_field_name": "name",
                    "arg_specs": [
                        {"name": "U", "type_domain": "entity_ref"},
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
        self.person_ref = "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"
        self.lang_ref = "idref_v1:Language:llllllllllllllllllllllllllllllllllllllllllllllllllll"

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
                "materialize_as": "record",
                "where": [
                    ("pred", "person:country", ["$E", "$C"]),
                    ("eq", "$C", "de"),
                ],
            },
            schema_ir=self.schema_ir,
        )
        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            materialize_as=compiled["materialize_as"],
            head=compiled["head"],
            id_policy=compiled.get("id_policy"),
            mode="python",
        )
        self.assertEqual(len(candidates), 3)
        entity_candidates = [cand for cand in candidates if cand.candidate_kind == "entity"]
        fact_candidates = [cand for cand in candidates if cand.candidate_kind == "fact"]
        self.assertEqual(len(entity_candidates), 1)
        self.assertEqual(len(fact_candidates), 2)
        entity = entity_candidates[0]
        self.assertEqual(entity.target, "Speaks")
        self.assertIn("resolved_identity", entity.payload)
        self.assertIn("missing_identity_fields", entity.payload)
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
                "materialize_as": "record",
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
            materialize_as=compiled["materialize_as"],
            head=compiled["head"],
            id_policy=compiled.get("id_policy"),
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

    def test_record_head_fact_projection_path_is_still_fact_candidate(self) -> None:
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.person_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        compiled = compile_authoring_derivation_v1(
            {
                "derivation_id": "derive_speaks_fact_projection",
                "version": "v1",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$p", "language": "$l"},
                },
                "materialize_as": "fact",
                "where": [
                    ("pred", "person:country", ["$p", "$c"]),
                    ("eq", "$c", "de"),
                    ("eq", "$l", self.lang_ref),
                ],
            },
            schema_ir=self.schema_ir,
        )
        self.assertEqual(compiled["target_pred_id"], "person:speaks")
        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            materialize_as=compiled["materialize_as"],
            head=compiled["head"],
            mode="python",
        )
        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        self.assertEqual(cand.candidate_kind, "fact")
        self.assertIn("terms", cand.payload)
        self.assertEqual(cand.payload["pred_id"], "person:speaks")

    def test_legacy_record_payload_emits_warning(self) -> None:
        legacy_candidate = make_candidate(
            derivation_id="legacy_d",
            derivation_version="v1",
            run_id="legacy_run",
            target="Speaks",
            key_terms=[("string", "Speaks"), ("string", "legacy")],
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": "key_tuple_digest_v1",
                "roles": [
                    {"pred_id": "speaks:person", "rest_terms": [("entity_ref", self.person_ref)]},
                    {"pred_id": "speaks:language", "rest_terms": [("entity_ref", self.lang_ref)]},
                ],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=now_epoch_nanos(),
            candidate_kind="entity",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = self.store.accept(
                derivation_id="legacy_d",
                version="v1",
                candidate_set=legacy_candidate,
                options=AcceptOptions(),
            )
        self.assertEqual(result.accepted_count, 1)
        self.assertTrue(any(isinstance(row.message, LegacyAcceptFallbackWarning) for row in caught))


if __name__ == "__main__":
    unittest.main()
