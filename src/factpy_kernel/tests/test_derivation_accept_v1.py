from __future__ import annotations

import warnings
import unittest
from unittest.mock import patch

from factpy_kernel.authoring import compile_authoring_derivation_v1
import factpy_kernel.core.derivation.accept as derivation_accept_module
from factpy_kernel.core.derivation.accept import AcceptOptions
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError
from factpy_kernel.core.policy.policy_ir import (
    PolicyIRValidationError,
    build_policy_ir_v1,
    policy_digest as compute_policy_digest,
)
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.protocol.digests import sha256_hex, sha256_token
from factpy_kernel.core.schema.schema_ir import (
    SchemaIRValidationError,
    schema_digest as compute_schema_digest,
)
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.view.projector import project_view_facts


class DerivationAcceptV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "schema_ir_v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                },
                {
                    "entity_type": "Speaks",
                    "identity_fields": [
                        {"name": "key", "type_domain": "string"},
                    ],
                    "is_record": True,
                    "projection_pred_id": "person:speaks",
                    "projection_arg_order": ["person", "language"],
                },
                {
                    "entity_type": "Language",
                    "identity_fields": [
                        {"name": "code", "type_domain": "string"},
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
                }
                ,
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
                }
            ],
            "projection": {"entities": [], "predicates": []},
            "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
            "generated_at": "2026-01-01T00:00:00Z",
        }
        self.store = Store(schema_ir=self.schema_ir)
        self.derivation_id = "derive_country"
        self.version = "v1"
        self.e_ref = "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"

    def test_evaluate_dummy_generates_candidate_set(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        self.assertEqual(candidate.derivation_id, self.derivation_id)
        self.assertEqual(candidate.derivation_version, self.version)
        self.assertEqual(candidate.target, "person:country")
        self.assertTrue(candidate.key_tuple_digest.startswith("sha256:"))
        self.assertEqual(candidate.payload["e_ref"], self.e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("string", "de")])

    def test_accept_writes_claim_claim_args_and_meta(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        result = self.store.accept(
            derivation_id=self.derivation_id,
            version=self.version,
            candidate_set=candidate,
            options=AcceptOptions(approved_by="alice", note="ok"),
        )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.diagnostics, [])
        self.assertEqual(len(result.written_assertions), 1)

        claims = self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref)
        self.assertEqual(len(claims), 1)
        asrt_id = claims[0].asrt_id

        claim_args = [row for row in self.store.ledger.claim_args if row.asrt_id == asrt_id]
        self.assertEqual(len(claim_args), 1)

        meta_rows = self.store.ledger.find_meta(asrt_id=asrt_id)
        meta_keys = {row.key for row in meta_rows}
        self.assertIn("materialize_id", meta_keys)
        self.assertIn("run_id", meta_keys)
        self.assertIn("key_tuple_digest", meta_keys)
        self.assertIn("cand_key_digest", meta_keys)
        self.assertIn("schema_digest", meta_keys)
        self.assertIn("policy_digest", meta_keys)
        materialize_id = next(row.value for row in meta_rows if row.key == "materialize_id")
        cand_key_digest = next(row.value for row in meta_rows if row.key == "cand_key_digest")
        schema_digest = next(row.value for row in meta_rows if row.key == "schema_digest")
        policy_digest = next(row.value for row in meta_rows if row.key == "policy_digest")
        self.assertTrue(isinstance(materialize_id, str) and materialize_id.startswith("mat_v1:"))
        self.assertEqual(
            materialize_id,
            "mat_v1:"
            + sha256_hex(
                b"factpy\x00mat_v1\x00"
                + candidate.run_id.encode("utf-8")
                + b"\x00"
                + candidate.derivation_id.encode("utf-8")
                + b"\x00"
                + candidate.derivation_version.encode("utf-8")
                + b"\x00"
            ),
        )
        self.assertEqual(
            cand_key_digest,
            sha256_token(
                b"factpy\x00cand_key_v1\x00"
                + candidate.target.encode("utf-8")
                + b"\x00"
                + candidate.key_tuple_digest.encode("utf-8")
                + b"\x00"
            ),
        )
        self.assertEqual(schema_digest, compute_schema_digest(self.schema_ir))
        policy_ir = build_policy_ir_v1(self.schema_ir, policy_mode="edb")
        policy_ir["generated_at"] = 0
        self.assertEqual(policy_digest, compute_policy_digest(policy_ir))

    def test_accept_warns_when_schema_digest_unavailable_but_still_writes(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        with patch(
            "factpy_kernel.core.store._accept.compute_schema_digest",
            side_effect=SchemaIRValidationError("simulated schema digest failure"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = self.store.accept(
                    derivation_id=self.derivation_id,
                    version=self.version,
                    candidate_set=candidate,
                    options=AcceptOptions(),
                )

        self.assertEqual(result.accepted_count, 1)
        self.assertTrue(
            any("schema_digest unavailable" in str(item.message) for item in caught),
            msg=[str(item.message) for item in caught],
        )
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0]["code"], "accept_meta_schema_digest_unavailable")
        self.assertEqual(result.diagnostics[0]["severity"], "warning")
        self.assertEqual(result.diagnostics[0]["path"], "$.accept.meta")
        self.assertEqual(result.diagnostics[0]["data"]["error_type"], "SchemaIRValidationError")
        self.assertIn("schema_digest unavailable", result.diagnostics[0]["message"])

        claims = self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref)
        self.assertEqual(len(claims), 1)
        meta_keys = {row.key for row in self.store.ledger.find_meta(asrt_id=claims[0].asrt_id)}
        self.assertNotIn("schema_digest", meta_keys)
        self.assertIn("policy_digest", meta_keys)

    def test_accept_warns_when_policy_digest_unavailable_but_still_writes(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        with patch(
            "factpy_kernel.core.store._accept.build_policy_ir_v1",
            side_effect=PolicyIRValidationError("simulated policy digest failure"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = self.store.accept(
                    derivation_id=self.derivation_id,
                    version=self.version,
                    candidate_set=candidate,
                    options=AcceptOptions(),
                )

        self.assertEqual(result.accepted_count, 1)
        self.assertTrue(any("policy_digest unavailable" in str(item.message) for item in caught))
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0]["code"], "accept_meta_policy_digest_unavailable")
        self.assertEqual(result.diagnostics[0]["data"]["error_type"], "PolicyIRValidationError")

        claims = self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref)
        self.assertEqual(len(claims), 1)
        meta_keys = {row.key for row in self.store.ledger.find_meta(asrt_id=claims[0].asrt_id)}
        self.assertIn("schema_digest", meta_keys)
        self.assertNotIn("policy_digest", meta_keys)

    def test_accept_warns_when_schema_and_policy_digest_unavailable(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        with patch(
            "factpy_kernel.core.store._accept.compute_schema_digest",
            side_effect=SchemaIRValidationError("simulated schema digest failure"),
        ):
            with patch(
                "factpy_kernel.core.store._accept.build_policy_ir_v1",
                side_effect=PolicyIRValidationError("simulated policy digest failure"),
            ):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    result = self.store.accept(
                        derivation_id=self.derivation_id,
                        version=self.version,
                        candidate_set=candidate,
                        options=AcceptOptions(),
                    )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(len(result.diagnostics), 2)
        self.assertEqual(
            {item["code"] for item in result.diagnostics},
            {"accept_meta_schema_digest_unavailable", "accept_meta_policy_digest_unavailable"},
        )
        self.assertGreaterEqual(len(caught), 2)

    def test_repeat_accept_is_noop(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )

        first = self.store.accept(
            derivation_id=self.derivation_id,
            version=self.version,
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        second = self.store.accept(
            derivation_id=self.derivation_id,
            version=self.version,
            candidate_set=candidate,
            options=AcceptOptions(),
        )

        claims = self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref)
        self.assertEqual(len(claims), 1)
        self.assertEqual(second.accepted_count, 0)
        self.assertEqual(second.skipped_count, 1)
        self.assertEqual(second.materialize_id, first.materialize_id)

    def test_repeat_accept_rejects_changed_meta(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            dims_terms=[],
        )
        self.store.accept(
            derivation_id=self.derivation_id,
            version=self.version,
            candidate_set=candidate,
            options=AcceptOptions(approved_by="alice", note="ok"),
        )
        with self.assertRaises(WriteProtocolError):
            self.store.accept(
                derivation_id=self.derivation_id,
                version=self.version,
                candidate_set=candidate,
                options=AcceptOptions(approved_by="bob", note="ok"),
            )

    def test_dry_run_does_not_write_ledger(self) -> None:
        candidate = self.store.evaluate_dummy(
            derivation_id=self.derivation_id,
            version=self.version,
            target="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "fr")],
            dims_terms=[],
        )

        before = len(self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref))
        result = self.store.accept(
            derivation_id=self.derivation_id,
            version=self.version,
            candidate_set=candidate,
            options=AcceptOptions(dry_run=True),
        )
        after = len(self.store.ledger.find_claims(pred_id="person:country", e_ref=self.e_ref))

        self.assertEqual(before, after)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertTrue(bool(result.materialize_id))
        self.assertEqual(len(result.written_assertions), 1)

    def test_accept_record_materialization_writes_exists_and_roles(self) -> None:
        lang_ref = "idref_v1:Language:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        candidate = CandidateSet(
            derivation_id="derive_speaks",
            derivation_version="v1",
            run_id="run_record_1",
            target="Speaks",
            key_tuple_digest="sha256:" + ("1" * 64),
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": {"kind": "key_tuple_digest_v1"},
                "roles": [
                    {"pred_id": "speaks:person", "rest_terms": [("entity_ref", self.e_ref)]},
                    {"pred_id": "speaks:language", "rest_terms": [("entity_ref", lang_ref)]},
                ],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=1,
            state="generated",
        )

        result = self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(approved_by="alice"),
        )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(len(result.written_assertions), 3)

        exists_claims = self.store.ledger.find_claims(pred_id="Speaks:exists")
        self.assertEqual(len(exists_claims), 1)
        record_e_ref = exists_claims[0].e_ref
        self.assertTrue(record_e_ref.startswith("idref_v1:Speaks:"))
        self.assertEqual(exists_claims[0].rest_terms, [])

        role_person = self.store.ledger.find_claims(pred_id="speaks:person", e_ref=record_e_ref)
        role_language = self.store.ledger.find_claims(pred_id="speaks:language", e_ref=record_e_ref)
        self.assertEqual(len(role_person), 1)
        self.assertEqual(len(role_language), 1)
        self.assertEqual(role_person[0].rest_terms, [("entity_ref", self.e_ref)])
        self.assertEqual(role_language[0].rest_terms, [("entity_ref", lang_ref)])

        meta_keys = {row.key for row in self.store.ledger.find_meta(asrt_id=exists_claims[0].asrt_id)}
        self.assertIn("materialize_kind", meta_keys)
        self.assertIn("record_type", meta_keys)
        self.assertIn("record_id_policy", meta_keys)

    def test_accept_record_materialization_with_identity_fields_id_policy(self) -> None:
        lang_ref = "idref_v1:Language:cccccccccccccccccccccccccccccccccccccccccccccccccccc"
        candidate = CandidateSet(
            derivation_id="derive_speaks",
            derivation_version="v1",
            run_id="run_record_1b",
            target="Speaks",
            key_tuple_digest="sha256:" + ("7" * 64),
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": {
                    "kind": "identity_fields_v1",
                    "fields": [
                        {"name": "person", "role": "person", "type_domain": "entity_ref"},
                        {"name": "language", "role": "language", "type_domain": "entity_ref"},
                    ],
                },
                "roles": [
                    {
                        "pred_id": "speaks:person",
                        "field_name": "person",
                        "type_domain": "entity_ref",
                        "rest_terms": [("entity_ref", self.e_ref)],
                    },
                    {
                        "pred_id": "speaks:language",
                        "field_name": "language",
                        "type_domain": "entity_ref",
                        "rest_terms": [("entity_ref", lang_ref)],
                    },
                ],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=11,
            state="generated",
        )

        result = self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        self.assertEqual(result.accepted_count, 1)
        exists_claim = self.store.ledger.find_claims(pred_id="Speaks:exists")[0]
        expected_record_e_ref = encode_idref_v1(
            "Speaks",
            [
                ("person", "entity_ref", self.e_ref),
                ("language", "entity_ref", lang_ref),
            ],
        )
        self.assertEqual(exists_claim.e_ref, expected_record_e_ref)

    def test_repeat_accept_record_is_noop(self) -> None:
        candidate = CandidateSet(
            derivation_id="derive_speaks",
            derivation_version="v1",
            run_id="run_record_2",
            target="Speaks",
            key_tuple_digest="sha256:" + ("2" * 64),
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": "key_tuple_digest_v1",
                "roles": [{"pred_id": "speaks:person", "rest_terms": [("entity_ref", self.e_ref)]}],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=2,
            state="generated",
        )
        first = self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        second = self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        self.assertEqual(first.accepted_count, 1)
        self.assertEqual(second.accepted_count, 0)
        self.assertEqual(second.skipped_count, 1)
        self.assertEqual(second.skipped_reason_counts, {"duplicate": 1})
        self.assertEqual(first.materialize_id, second.materialize_id)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:person")), 1)

    def test_record_partial_write_can_retry_and_complete_when_exists_write_failed(self) -> None:
        candidate = CandidateSet(
            derivation_id="derive_speaks",
            derivation_version="v1",
            run_id="run_record_partial_retry",
            target="Speaks",
            key_tuple_digest="sha256:" + ("8" * 64),
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": "key_tuple_digest_v1",
                "roles": [{"pred_id": "speaks:person", "rest_terms": [("entity_ref", self.e_ref)]}],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=8,
            state="generated",
        )

        original_set_field = derivation_accept_module.set_field
        fail_state = {"fail_exists_once": True}

        def flaky_set_field(*args, **kwargs):
            if kwargs.get("pred_id") == "Speaks:exists" and fail_state["fail_exists_once"]:
                fail_state["fail_exists_once"] = False
                raise WriteProtocolError("simulated exists write failure")
            return original_set_field(*args, **kwargs)

        with patch("factpy_kernel.core.derivation.accept.set_field", side_effect=flaky_set_field):
            with self.assertRaises(WriteProtocolError):
                self.store.accept(
                    derivation_id="derive_speaks",
                    version="v1",
                    candidate_set=candidate,
                    options=AcceptOptions(),
                )

        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 0)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:person")), 1)
        partial_view = project_view_facts(self.store.ledger, self.schema_ir, temporal_view="record")
        self.assertEqual(partial_view["Speaks:exists"], [])
        self.assertEqual(partial_view["speaks:person"], [])

        retry = self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        self.assertEqual(retry.accepted_count, 1)
        self.assertTrue(any(d["code"] == "ACCEPT_RECORD_RECOVERED_PARTIAL" for d in retry.diagnostics))
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:person")), 1)
        committed_view = project_view_facts(self.store.ledger, self.schema_ir, temporal_view="record")
        self.assertEqual(len(committed_view["Speaks:exists"]), 1)
        self.assertEqual(len(committed_view["speaks:person"]), 1)

    def test_repeat_accept_record_rejects_changed_note(self) -> None:
        candidate = CandidateSet(
            derivation_id="derive_speaks",
            derivation_version="v1",
            run_id="run_record_3",
            target="Speaks",
            key_tuple_digest="sha256:" + ("3" * 64),
            tup_digest=None,
            payload={
                "materialize_as": "record",
                "record_type": "Speaks",
                "record_exists_pred_id": "Speaks:exists",
                "id_policy": "key_tuple_digest_v1",
                "roles": [{"pred_id": "speaks:person", "rest_terms": [("entity_ref", self.e_ref)]}],
            },
            support_digest="sha256:" + ("0" * 64),
            support_kind="none",
            generated_at=3,
            state="generated",
        )
        self.store.accept(
            derivation_id="derive_speaks",
            version="v1",
            candidate_set=candidate,
            options=AcceptOptions(note="first"),
        )
        with self.assertRaises(WriteProtocolError):
            self.store.accept(
                derivation_id="derive_speaks",
                version="v1",
                candidate_set=candidate,
                options=AcceptOptions(note="changed"),
            )

    def test_record_derivation_head_preview_and_accept_end_to_end(self) -> None:
        lang_ref = "idref_v1:Language:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e_ref,
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
                    "kwargs": {"person": "$E", "language": lang_ref},
                },
                "materialize_as": "record",
                "id_policy": {"kind": "key_tuple_digest_v1"},
                "where": [
                    ("pred", "person:country", ["$E", "$C"]),
                    ("eq", "$C", "de"),
                ],
            },
            schema_ir=self.schema_ir,
        )
        self.assertEqual(compiled["target_pred_id"], "Speaks")
        self.assertEqual(compiled["head_vars"], ["$E", lang_ref])

        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            materialize_as=compiled["materialize_as"],
            head=compiled["head"],
            id_policy=compiled["id_policy"],
            mode="python",
        )
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.target, "Speaks")
        self.assertEqual(candidate.payload["materialize_as"], "record")
        self.assertEqual(candidate.payload["record_exists_pred_id"], "Speaks:exists")
        self.assertEqual(len(candidate.payload["roles"]), 2)

        result = self.store.accept(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            candidate_set=candidate,
            options=AcceptOptions(approved_by="tester"),
        )
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:person")), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="speaks:language")), 1)

    def test_record_derivation_head_preview_and_accept_end_to_end_identity_fields_id_policy(self) -> None:
        lang_ref = "idref_v1:Language:dddddddddddddddddddddddddddddddddddddddddddddddddddd"
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        compiled = compile_authoring_derivation_v1(
            {
                "derivation_id": "derive_speaks_from_country_if",
                "version": "v1",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$E", "language": lang_ref},
                },
                "materialize_as": "record",
                "id_policy": {
                    "kind": "identity_fields_v1",
                    "fields": [
                        {"name": "person", "role": "person", "type_domain": "entity_ref"},
                        {"name": "language", "role": "language", "type_domain": "entity_ref"},
                    ],
                },
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
            id_policy=compiled["id_policy"],
            mode="python",
        )
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["id_policy"]["kind"], "identity_fields_v1")
        result = self.store.accept(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        self.assertEqual(result.accepted_count, 1)
        exists_claim = self.store.ledger.find_claims(pred_id="Speaks:exists")[0]
        expected_record_e_ref = encode_idref_v1(
            "Speaks",
            [
                ("person", "entity_ref", self.e_ref),
                ("language", "entity_ref", lang_ref),
            ],
        )
        self.assertEqual(exists_claim.e_ref, expected_record_e_ref)

    def test_record_derivation_head_preview_and_accept_end_to_end_autoderived_id_policy(self) -> None:
        lang_ref = "idref_v1:Language:ffffffffffffffffffffffffffffffffffffffffffffffffffff"
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e_ref,
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        compiled = compile_authoring_derivation_v1(
            {
                "derivation_id": "derive_speaks_from_country_auto_if",
                "version": "v1",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "entity_type",
                    "entity_type": "Speaks",
                    "kwargs": {"person": "$E", "language": lang_ref},
                },
                "materialize_as": "record",
                "where": [
                    ("pred", "person:country", ["$E", "$C"]),
                    ("eq", "$C", "de"),
                ],
            },
            schema_ir=self.schema_ir,
        )
        self.assertEqual(compiled["id_policy"]["kind"], "identity_fields_v1")
        self.assertEqual(
            compiled["id_policy"]["fields"],
            [
                {"name": "person", "role": "person", "type_domain": "entity_ref"},
                {"name": "language", "role": "language", "type_domain": "entity_ref"},
            ],
        )
        candidates = self.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            materialize_as=compiled["materialize_as"],
            head=compiled["head"],
            id_policy=compiled["id_policy"],
            mode="python",
        )
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.payload["id_policy"]["kind"], "identity_fields_v1")
        result = self.store.accept(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        self.assertEqual(result.accepted_count, 1)

    def test_record_head_fact_materialize_uses_projection_predicate_end_to_end(self) -> None:
        lang_ref = "idref_v1:Language:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref=self.e_ref,
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
                    ("eq", "$l", lang_ref),
                ],
            },
            schema_ir=self.schema_ir,
        )
        self.assertEqual(compiled["target_pred_id"], "person:speaks")
        self.assertEqual(compiled["head_vars"], ["$p", "$l"])
        self.assertEqual(compiled["projection_pred_id"], "person:speaks")
        self.assertEqual(compiled["projection_arg_order"], ["person", "language"])

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
        candidate = candidates[0]
        self.assertEqual(candidate.target, "person:speaks")
        self.assertEqual(candidate.payload["e_ref"], self.e_ref)
        self.assertEqual(candidate.payload["rest_terms"], [("entity_ref", lang_ref)])

        result = self.store.accept(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            candidate_set=candidate,
            options=AcceptOptions(approved_by="tester"),
        )
        self.assertEqual(result.accepted_count, 1)
        fact_claims = self.store.ledger.find_claims(pred_id="person:speaks", e_ref=self.e_ref)
        self.assertEqual(len(fact_claims), 1)
        self.assertEqual(len(self.store.ledger.find_claims(pred_id="Speaks:exists")), 0)


if __name__ == "__main__":
    unittest.main()
