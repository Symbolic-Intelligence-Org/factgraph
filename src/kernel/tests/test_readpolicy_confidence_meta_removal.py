"""Red baseline for ReadPolicy and legacy assertion confidence removal.

These tests are the Phase 1 scaffold for
`docs/blueprints/active/2026-05-13_readpolicy-confidence-meta-removal.md`.
They intentionally lock the removal target before the implementation lands.
Some tests are expected to fail against the current pre-cleanup code.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from kernel.core.derivation.candidates import CandidateSet
from kernel.core.mapping.canon import MappingResolveError, resolve_mapping_predicate
from kernel.core.store.ledger import MetaRow, Ledger
from kernel.sdk import Entity, Field, Identity, Rule, SDKStore, SDKStoreError, vars
from kernel.adapters.problog.problog_export import _claim_probability
from kernel.adapters.pyreason.session import PyReasonSession


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _sdk() -> SDKStore:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    sdk.set(User.name, ref, "Alice", meta={"source": "seed"})
    sdk.add(User.tag, ref, "vip", meta={"source": "seed"})
    return sdk


def _name_rule() -> Rule:
    with vars("u", "name") as (u, name):
        return Rule(
            id="cleanup.name",
            version="v1",
            select=[u, name],
            where=[User(u), u.name == name],
        )


def _assert_removed_guidance(testcase: unittest.TestCase, message: str) -> None:
    lowered = message.lower()
    testcase.assertIn("readpolicy", lowered)
    testcase.assertIn("removed", lowered)
    testcase.assertIn("raw_kind", lowered)
    testcase.assertIn("bound", lowered)


class ReadPolicyImportRemovalTests(unittest.TestCase):
    def test_readpolicy_not_exported_from_kernel_sdk(self) -> None:
        with self.assertRaises(ImportError):
            from kernel.sdk import ReadPolicy  # noqa: F401

    def test_readpolicy_not_exported_from_core_store_types(self) -> None:
        with self.assertRaises(ImportError):
            from kernel.core.store.types import ReadPolicy  # noqa: F401


class SDKReadPolicyRemovalTests(unittest.TestCase):
    def test_find_policy_rejects_with_removed_guidance(self) -> None:
        sdk = _sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, policy={"confidence_strategy": "max"})  # type: ignore[arg-type]

        _assert_removed_guidance(self, str(ctx.exception))

    def test_run_policy_rejects_with_removed_guidance(self) -> None:
        sdk = _sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_name_rule(), policy={"confidence_strategy": "max"})  # type: ignore[arg-type]

        _assert_removed_guidance(self, str(ctx.exception))

    def test_run_return_display_meta_rejects_with_removed_guidance(self) -> None:
        sdk = _sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_name_rule(), row_format="dict", return_display_meta=True)

        _assert_removed_guidance(self, str(ctx.exception))

    def test_evaluate_policy_rejects_with_removed_guidance(self) -> None:
        sdk = _sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.evaluate(object(), policy={"confidence_strategy": "max"})  # type: ignore[call-arg]

        message = str(ctx.exception).lower()
        self.assertIn("policy", message)
        self.assertIn("removed", message)

    def test_find_view_rejection_no_longer_points_to_readpolicy(self) -> None:
        sdk = _sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view="review_set")  # type: ignore[call-arg]

        self.assertIn("view", str(ctx.exception).lower())
        self.assertNotIn("ReadPolicy", str(ctx.exception))


class ServicePolicyRemovalTests(unittest.TestCase):
    def test_runtime_view_facts_policy_is_rejected(self) -> None:
        from service.runtime_v1 import (
            open_runtime_session,
            project_runtime_view_facts,
            reset_runtime_sessions_for_tests,
        )

        reset_runtime_sessions_for_tests()
        session = open_runtime_session({"schema_ir": _sdk().schema_ir})
        self.assertTrue(session["ok"], session)
        session_id = session["session"]["session_id"]

        response = project_runtime_view_facts(
            session_id,
            {"policy": {"confidence_strategy": "max"}},
        )

        self.assertFalse(response.get("ok"), response)
        message = str(response.get("errors", [{}])[0]).lower()
        self.assertIn("policy", message)
        self.assertIn("removed", message)


class WriteConfidenceMetaRemovalTests(unittest.TestCase):
    def test_user_authored_meta_confidence_is_rejected(self) -> None:
        sdk = _sdk()
        ref = sdk.ref(User, user_id="u-2")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.set(User.name, ref, "Bob", meta={"confidence": 0.5})

        message = str(ctx.exception).lower()
        self.assertIn("confidence", message)
        self.assertIn("raw_kind", message)
        self.assertIn("bound", message)

    def test_user_authored_meta_confidence_source_is_rejected(self) -> None:
        sdk = _sdk()
        ref = sdk.ref(User, user_id="u-3")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.set(User.name, ref, "Chandra", meta={"confidence_source": "legacy"})

        message = str(ctx.exception).lower()
        self.assertIn("confidence_source", message)
        self.assertIn("removed", message)

    def test_raw_meta_escape_hatch_preserves_confidence_key(self) -> None:
        sdk = _sdk()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None
        record = snap.field("name").active.one()

        sdk.ledger.append_meta(
            [
                MetaRow(
                    asrt_id=record.asrt_id,
                    key="confidence",
                    kind="float",
                    value=0.42,
                )
            ]
        )

        refreshed = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        refreshed_record = refreshed.field("name").active.one()
        self.assertEqual(refreshed_record.meta.raw["confidence"], 0.42)


class FirstClassConfidenceRemovalTests(unittest.TestCase):
    def test_assertion_meta_has_no_confidence_attribute(self) -> None:
        sdk = _sdk()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        record = snap.field("name").active.one()

        self.assertFalse(hasattr(record.meta, "confidence"))

    def test_assertion_record_set_where_confidence_is_removed(self) -> None:
        sdk = _sdk()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        records = snap.field("tag").active

        with self.assertRaises(TypeError):
            records.where(confidence=0.5)  # type: ignore[call-arg]


class MappingTieBreakRemovalTests(unittest.TestCase):
    def test_max_confidence_tie_break_is_rejected(self) -> None:
        schema_pred = {
            "pred_id": "user:name",
            "is_mapping": True,
            "mapping_kind": "single_valued",
            "arg_specs": [
                {"name": "user", "kind": "entity_ref"},
                {"name": "name", "kind": "literal"},
            ],
            "mapping_key_positions": [0],
            "mapping_value_positions": [1],
            "tie_break": "max_confidence",
        }

        with self.assertRaises(MappingResolveError) as ctx:
            resolve_mapping_predicate(Ledger(), schema_pred)

        self.assertIn("max_confidence", str(ctx.exception))


class ConfidenceCarrierPreservationTests(unittest.TestCase):
    def test_candidates_keep_internal_confidence_carriers(self) -> None:
        candidate = CandidateSet(
            derivation_id="drv.cleanup",
            derivation_version="v1",
            run_id="run.cleanup",
            target="user:tag",
            key_tuple_digest="sha256:" + ("0" * 64),
            tup_digest=None,
            payload={
                "pred_id": "user:tag",
                "terms": [
                    {"kind": "entity_ref", "value": "idref_v1:User:u-1"},
                    {"kind": "literal", "tag": "string", "value": "vip"},
                ],
            },
            support_digest="sha256:" + ("1" * 64),
            support_kind="native",
            generated_at=1,
            state="proposed",
            confidence=0.7,
            confidence_kind="probability",
            candidate_kind="fact",
        )

        self.assertEqual(candidate.confidence, 0.7)
        self.assertEqual(candidate.confidence_kind, "probability")

    def test_problog_native_probability_annotation_still_wins(self) -> None:
        from kernel.core.evidence.write_protocol import set_field
        from kernel.core.store.ledger import AnnotationRow

        sdk = _sdk()
        asrt_id = set_field(sdk.ledger, "user:tag", "idref_v1:User:u-1", [("string", "vip")], meta={})
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

    def test_pyreason_session_keeps_generic_confidence_out_of_shared_meta(self) -> None:
        session = PyReasonSession({"predicates": [{"pred_id": "user:popular", "arity": 2}]})

        session.write_node_fact(
            "user:popular",
            "idref_v1:User:u-1",
            "true",
            bound=(0.6, 0.9),
            meta={"confidence": 0.5, "confidence_source": "legacy", "source": "seed"},
        )

        self.assertEqual(session.node_facts[0]["meta"], {"source": "seed"})


class TestFixtureMigrationGate(unittest.TestCase):
    def test_no_user_authored_meta_confidence_seed_fixtures_remain(self) -> None:
        root = Path(__file__).resolve().parents[3]
        pattern = re.compile(r"meta\s*=\s*\{[^\n}]*[\"']confidence[\"']")
        offenders: list[str] = []
        for base in (root / "src" / "kernel" / "tests", root / "src" / "service" / "tests"):
            for path in sorted(base.rglob("test_*.py")):
                if path.name == Path(__file__).name:
                    continue
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    if pattern.search(line):
                        offenders.append(f"{path.relative_to(root)}:{lineno}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
