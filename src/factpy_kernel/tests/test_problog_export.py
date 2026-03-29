"""Tests for ProbLog export probability sourcing."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy_kernel.adapters.problog.problog_export import ProbLogExportError, export_problog
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.ledger import AnnotationRow
from factpy_kernel.sdk.schema import Entity, Field, Identity
from factpy_kernel.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class ProbLogExportTests(unittest.TestCase):
    def _make_sdk(self) -> SDKStore:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test", "confidence": 0.25},
        )
        return sdk

    def _export_program(self, sdk: SDKStore) -> str:
        rule_spec = {
            "derivation_id": "drv.problog_export",
            "version": "v1",
            "target_pred_id": "user:name",
            "head_vars": ["$u", "$name"],
            "where": [("pred", "user:name", ["$u", "$name"])],
            "query_pred": "answer",
        }
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "query.pl"
            export_problog(sdk.store, rule_spec, out_path)
            return out_path.read_text(encoding="utf-8")

    def test_export_prefers_problog_probability_annotation(self) -> None:
        sdk = self._make_sdk()
        claim = sdk.ledger.claims[0]
        sdk.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=claim.asrt_id,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=0.8,
                    origin="derived",
                    derivation="drv.problog_tag",
                )
            ]
        )

        program = self._export_program(sdk)

        self.assertIn("0.8::edb_fact(", program)
        self.assertNotIn("0.25::edb_fact(", program)

    def test_export_falls_back_to_meta_confidence(self) -> None:
        sdk = self._make_sdk()

        program = self._export_program(sdk)

        self.assertIn("0.25::edb_fact(", program)

    def test_export_defaults_to_deterministic_without_probability_data(self) -> None:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test"},
        )

        program = self._export_program(sdk)

        self.assertIn("1::edb_fact(", program)

    def test_invalid_canonical_probability_raises(self) -> None:
        sdk = self._make_sdk()
        claim = sdk.ledger.claims[0]
        sdk.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=claim.asrt_id,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=1.2,
                    origin="derived",
                    derivation="drv.problog_tag",
                )
            ]
        )

        with self.assertRaises(ProbLogExportError) as ctx:
            self._export_program(sdk)

        self.assertIn("problog/semantic/probability out of range", str(ctx.exception))


class TestProbLogExportReadsSharedProbability(unittest.TestCase):
    """ProbLog export reads shared/semantic/probability from write_protocol."""

    def test_export_reads_shared_semantic_probability(self) -> None:
        from factpy_kernel.adapters.problog.problog_export import _claim_probability

        class Item(Entity):
            item_id: str = Identity(primary_key=True)
            label: str = Field(cardinality="single")

        sdk = SDKStore([Item])
        ref = sdk.ref(Item, item_id="x")
        asrt_id = set_field(
            sdk.ledger,
            pred_id="item:label",
            e_ref=ref,
            rest_terms=[("string", "val")],
            meta={"probability": 0.65},
        )
        prob = _claim_probability(sdk.store, asrt_id)
        self.assertAlmostEqual(prob, 0.65)


if __name__ == "__main__":
    unittest.main()
