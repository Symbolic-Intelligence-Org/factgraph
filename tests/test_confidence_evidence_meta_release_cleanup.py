"""Red baseline for confidence/evidence meta release cleanup."""

from __future__ import annotations

import unittest

from factpy.core.derivation.accept import AcceptOptions, accept_candidate_set
from factpy.core.derivation.candidates import CandidateSet
from factpy.core.evidence.write_protocol import set_field
from factpy.core.store._candidate_evidence_tree import build_candidate_evidence_tree
from factpy.core.store.ledger import AnnotationRow, Ledger
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore
from factpy.adapters.problog.problog_export import _claim_probability
from factpy.adapters.pyreason.session import PyReasonSession
from factpy.service.runtime_v1 import _candidate_from_dict, _candidate_to_dict


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag: str = Field(cardinality="single")


def _eref(token: str = "alice") -> str:
    return f"idref_v1:User:{token}"


def _candidate(*, confidence: float | None = 0.42, confidence_kind: str = "probability") -> CandidateSet:
    return CandidateSet(
        derivation_id="drv.cleanup",
        derivation_version="v1",
        run_id="run.cleanup",
        target="user:tag",
        key_tuple_digest="sha256:" + ("0" * 64),
        tup_digest=None,
        payload={
            "pred_id": "user:tag",
            "terms": [
                {"kind": "entity_ref", "value": _eref()},
                {"kind": "literal", "tag": "string", "value": "vip"},
            ],
        },
        support_digest="sha256:" + ("1" * 64),
        support_kind="native",
        generated_at=1,
        state="proposed",
        confidence=confidence,
        confidence_kind=confidence_kind,
        candidate_kind="fact",
    )


class AcceptConfidenceCleanupTests(unittest.TestCase):
    def test_accept_does_not_persist_candidate_confidence_meta(self) -> None:
        ledger = Ledger()
        result = accept_candidate_set(
            ledger,
            _candidate(confidence=0.42, confidence_kind="probability"),
            AcceptOptions(),
            "drv.cleanup",
            "v1",
        )
        asrt_id = result.written_assertions[0]["asrt_id"]

        self.assertEqual(ledger.find_meta(asrt_id=asrt_id, key="confidence"), [])
        self.assertEqual(ledger.find_meta(asrt_id=asrt_id, key="confidence_kind"), [])

    def test_legacy_confidence_difference_does_not_prevent_duplicate_detection(self) -> None:
        ledger = Ledger()
        first = accept_candidate_set(
            ledger,
            _candidate(confidence=0.25, confidence_kind="probability"),
            AcceptOptions(),
            "drv.cleanup",
            "v1",
        )
        second = accept_candidate_set(
            ledger,
            _candidate(confidence=0.75, confidence_kind="certainty"),
            AcceptOptions(),
            "drv.cleanup",
            "v1",
        )

        self.assertEqual(first.accepted_count, 1)
        self.assertEqual(second.skipped_reason_counts, {"duplicate": 1})
        self.assertEqual(len(ledger.claims), 1)


class WriteProtocolConfidenceCleanupTests(unittest.TestCase):
    def test_generic_confidence_meta_is_not_shared_annotation(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:tag",
            _eref(),
            [("string", "vip")],
            meta={"source": "manual", "confidence": 0.85},
        )

        self.assertEqual(
            ledger.find_annotations(
                asrt_id=asrt_id,
                namespace="shared",
                category="derived",
                key="confidence",
            ),
            [],
        )
        self.assertEqual([row.value for row in ledger.find_meta(asrt_id=asrt_id, key="confidence")], [0.85])

    def test_source_annotation_projection_is_preserved(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:tag",
            _eref(),
            [("string", "vip")],
            meta={"source": "manual"},
        )

        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="shared", category="source", key="source")
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].value, "manual")


class RuntimeCandidateCompatibilityTests(unittest.TestCase):
    def test_runtime_candidate_dict_omits_legacy_confidence_by_default(self) -> None:
        payload = _candidate_to_dict(_candidate(confidence=0.42, confidence_kind="probability"))

        self.assertNotIn("confidence", payload)
        self.assertNotIn("confidence_kind", payload)

    def test_runtime_accept_parser_keeps_legacy_confidence_payload_parseable(self) -> None:
        payload = _candidate_to_dict(_candidate(confidence=None, confidence_kind="none"))
        payload["confidence"] = 0.64
        payload["confidence_kind"] = "probability"

        parsed = _candidate_from_dict(payload, path="$.candidate")

        self.assertEqual(parsed.confidence, 0.64)
        self.assertEqual(parsed.confidence_kind, "probability")


class AdapterConfidenceCleanupTests(unittest.TestCase):
    def test_problog_ignores_generic_meta_confidence_fallback(self) -> None:
        sdk = SDKStore([User])
        asrt_id = set_field(
            sdk.ledger,
            "user:tag",
            _eref(),
            [("string", "vip")],
            meta={"confidence": 0.25},
        )

        self.assertEqual(_claim_probability(sdk.store, asrt_id), 1.0)

    def test_problog_native_probability_annotation_is_preserved(self) -> None:
        sdk = SDKStore([User])
        asrt_id = set_field(sdk.ledger, "user:tag", _eref(), [("string", "vip")], meta={})
        sdk.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=asrt_id,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=0.8,
                    origin="derived",
                    derivation="drv.problog",
                )
            ]
        )

        self.assertEqual(_claim_probability(sdk.store, asrt_id), 0.8)

    def test_pyreason_bound_templates_remain_without_shared_confidence_template(self) -> None:
        session = PyReasonSession(
            {
                "predicates": [
                    {"pred_id": "user:tag", "arity": 2},
                ]
            }
        )
        session.write_node_fact("user:tag", _eref(), "vip", bound=[0.3, 0.7])

        templates = session.annotation_templates
        keys = {(row["namespace"], row["category"], row["key"]) for row in templates}
        self.assertIn(("pyreason", "semantic", "bound_lower"), keys)
        self.assertIn(("pyreason", "semantic", "bound_upper"), keys)
        self.assertNotIn(("shared", "derived", "confidence"), keys)


class EvidenceTreeConfidenceCleanupTests(unittest.TestCase):
    def test_generic_fact_confidence_is_not_lifted_into_evidence_tree(self) -> None:
        tree = build_candidate_evidence_tree(
            candidate_id="cand.cleanup",
            support_digest="sha256:" + ("2" * 64),
            support_kind="native",
            support={
                "binding": [],
                "root_result_kind": "success",
                "pred_witnesses": [
                    {
                        "pred_atom_key": "b0.a0:user:tag",
                        "asrt_ids": ["a1"],
                    }
                ],
                "non_fact_steps": [],
            },
            assertion_lookup=lambda _asrt_id: {
                "claim": {"pred_id": "user:tag", "e_ref": _eref()},
                "claim_args": [{"idx": 0, "tag": "string", "val": "vip"}],
                "confidence": 0.7,
            },
            support_lookup=lambda _digest: None,
        )

        support_section = tree["root"]["children"][0]
        witness_group = support_section["children"][0]
        assertion = witness_group["children"][0]
        self.assertNotIn("confidence", assertion)
        self.assertNotIn("condition_confidence", witness_group)


class CandidateCarrierPreservationTests(unittest.TestCase):
    def test_candidates_keep_internal_legacy_carrier_fields(self) -> None:
        candidate = _candidate(confidence=0.42, confidence_kind="probability")

        self.assertEqual(candidate.confidence, 0.42)
        self.assertEqual(candidate.confidence_kind, "probability")
