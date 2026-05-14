from __future__ import annotations

import unittest

from factgraph.sdk import Branch, Entity, FactGraph, Field, Identity, Inference, Pred
from factgraph.sdk import vars as sdk_vars
from factgraph.audit.proof_frame_diff import ProofFrameDiff
from factgraph.audit.round_events import (
    RoundEvent,
    make_round_finalized_event,
    make_round_started_event,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _age_inference() -> Inference:
    with sdk_vars("u", "age") as (u, age):
        return Inference(
            id="inf.namespace.age",
            version="v1",
            where=[Branch([Pred("user:age", u, age)], id="age_path")],
            target="user:age",
            head_vars=[u, age],
        )


def _tag_inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.namespace.tag",
            version="v1",
            where=[Branch([Pred("user:tag_seed", u, tag)], id="tag_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


def _empty_round(round_id: str) -> tuple[RoundEvent, ...]:
    started = make_round_started_event(round_id, event_ts=100)
    finalized = make_round_finalized_event(
        round_id,
        sequence=1,
        events=(started,),
        event_ts=200,
    )
    return (started, finalized)


class FactGraphSchemaIngestNamespaceTests(unittest.TestCase):
    def test_schema_ingest_writes_via_namespace(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")

        result = fg.schema.ingest(
            [
                {
                    "kind": "set",
                    "field": User.age,
                    "e_ref": ref,
                    "value": 30,
                }
            ]
        )

        self.assertEqual(len(result.written_assertion_ids), 1)
        self.assertEqual(fg.read.get(User, user_id="u-1").age, 30)


class FactGraphWriteRetractNamespaceTests(unittest.TestCase):
    def test_write_retract_hides_retracted_assertion(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        asrt_id = fg.write.set(User.age, ref, 30)

        fg.write.retract(asrt_id, meta={"source": "review"})

        self.assertIsNone(fg.read.get(User, user_id="u-1").age)


class FactGraphEvalAcceptNamespaceTests(unittest.TestCase):
    def test_eval_accept_commits_one_candidate(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.tag_seed, ref, "vip")

        candidate = fg.eval.evaluate(_tag_inference())[0]
        result = fg.eval.accept(candidate)

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(len(result.written_assertions), 1)
        self.assertEqual(tuple(fg.read.get(User, user_id="u-1").tag), ("vip",))


class FactGraphWhatIfNamespaceTests(unittest.TestCase):
    def test_what_if_diagnose_returns_raw_diagnose_result(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.age, ref, 30)

        result = fg.what_if.diagnose(_age_inference(), {"$u": ref, "$age": 99})

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.diagnostic_payload)

    def test_what_if_why_not_returns_green_and_red_candidates(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.age, ref, 30)

        result = fg.what_if.why_not(
            _age_inference(),
            [
                {"$u": ref, "$age": 30},
                {"$u": "idref_v1:User:user_id:missing", "$age": 30},
            ],
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(tuple(dict(row)["$u"] for row in result.green), (ref,))
        self.assertEqual(len(result.red), 1)


class FactGraphAuditDiffNamespaceTests(unittest.TestCase):
    def test_audit_diff_proof_frames_namespace_returns_diff(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        diff = fg.audit.diff_proof_frames(
            "round-a",
            "round-b",
            _empty_round("round-a"),
            _empty_round("round-b"),
        )

        self.assertIsInstance(diff, ProofFrameDiff)
        self.assertEqual(diff.frame_deltas, ())


if __name__ == "__main__":
    unittest.main()
