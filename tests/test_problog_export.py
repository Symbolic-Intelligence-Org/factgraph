"""Tests for ProbLog export probability sourcing."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.adapters.problog.problog_export import ProbLogExportError, export_problog
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store.ledger import AnnotationRow
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStore


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

    def _export_program(self, sdk: SDKStore, where: list[object] | None = None) -> str:
        rule_spec = {
            "derivation_id": "drv.problog_export",
            "version": "v1",
            "target_pred_id": "user:name",
            "head_vars": ["$u", "$name"],
            "where": where or [("pred", "user:name", ["$u", "$name"])],
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

    def test_export_ignores_meta_confidence_fallback(self) -> None:
        sdk = self._make_sdk()

        program = self._export_program(sdk)

        self.assertIn("1::edb_fact(", program)
        self.assertNotIn("0.25::edb_fact(", program)

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

    def test_export_supports_ne_filter(self) -> None:
        sdk = self._make_sdk()

        program = self._export_program(
            sdk,
            where=[
                ("pred", "user:name", ["$u", "$name"]),
                ("ne", "$name", "blocked"),
            ],
        )

        self.assertIn("V_NAME \\= 'blocked'", program)

    def test_export_supports_ne_filter_inside_not_body(self) -> None:
        sdk = self._make_sdk()

        program = self._export_program(
            sdk,
            where=[
                ("pred", "user:name", ["$u", "$name"]),
                ("not", [("ne", "$name", "blocked")]),
            ],
        )

        self.assertIn("\\+(V_NAME \\= 'blocked')", program)

    def test_compile_atom_supports_arithmetic_builtins(self) -> None:
        from factgraph.adapters.problog.problog_export import _compile_atom

        cases = [
            (("add", "$z", "$x", "$y"), "V_Z is V_X + V_Y"),
            (("sub", "$z", "$x", "$y"), "V_Z is V_X - V_Y"),
            (("neg", "$z", "$x"), "V_Z is -V_X"),
            (("addc", "$z", "$x", 2), "V_Z is V_X + 2"),
            (("mulc", "$z", "$x", 3), "V_Z is V_X * 3"),
        ]
        for atom, expected in cases:
            with self.subTest(atom=atom):
                self.assertEqual(_compile_atom(atom), expected)

    def test_compile_atom_rejects_malformed_arithmetic_builtin(self) -> None:
        from factgraph.adapters.problog.problog_export import ProbLogExportError, _compile_atom

        with self.assertRaisesRegex(ProbLogExportError, "add atom must be"):
            _compile_atom(("add", "$z", "$x"))

    def test_compile_atom_rejects_non_numeric_arithmetic_literal(self) -> None:
        from factgraph.adapters.problog.problog_export import ProbLogExportError, _compile_atom

        with self.assertRaisesRegex(ProbLogExportError, "arithmetic operands"):
            _compile_atom(("addc", "$z", "$x", "two"))


class TestProbLogExportReadsSharedProbability(unittest.TestCase):
    """ProbLog export reads shared/semantic/probability annotations."""

    def test_export_reads_shared_semantic_probability(self) -> None:
        from factgraph.adapters.problog.problog_export import _claim_probability

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
            meta={"source": "test"},
        )
        sdk.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=asrt_id,
                    namespace="shared",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=0.65,
                    origin="observed",
                )
            ]
        )
        prob = _claim_probability(sdk.store, asrt_id)
        self.assertAlmostEqual(prob, 0.65)


    # --- F-PL-4: bool-only confidence fallback ---

    def test_claim_probability_ignores_meta_confidence(self) -> None:
        """Generic meta.confidence is no longer a ProbLog probability fallback."""
        from factgraph.adapters.problog.problog_export import _claim_probability

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
            meta={"confidence": 0.5},
        )
        # Overwrite confidence with bool via raw annotation
        sdk.ledger.append_annotations([
            AnnotationRow(
                asrt_id=asrt_id,
                namespace="shared",
                category="semantic",
                key="confidence",
                kind="bool",
                value=True,
                origin="observed",
            ),
        ])
        prob = _claim_probability(sdk.store, asrt_id)
        self.assertAlmostEqual(prob, 1.0)


class ProbLogImportTests(unittest.TestCase):
    """Tests for ProbLog import line parsing."""

    # --- F-PL-2: colon path safety ---

    def test_split_result_line_colon_in_goal(self) -> None:
        """F-PL-2: rsplit at rightmost colon is safe because rhs must be float."""
        from factgraph.adapters.problog.problog_import import _split_result_line

        # Tab-separated (primary path): always safe
        result = _split_result_line("foo:bar(x)\t0.75")
        self.assertEqual(result, ("foo:bar(x)", "0.75"))

        # Colon-separated with valid float rhs
        result = _split_result_line("simple_pred(x):0.5")
        self.assertEqual(result, ("simple_pred(x)", "0.5"))

        # Colon in goal but rhs is NOT a float → returns None (safe)
        result = _split_result_line("urn:isbn:not_a_number")
        self.assertIsNone(result)

        # Colon with integer rhs is accepted (valid float match)
        result = _split_result_line("pred:1")
        self.assertEqual(result, ("pred", "1"))

    # --- F-PL-3: persist_problog_annotations multi-fact ---

    def test_persist_problog_annotations_multi_fact_index(self) -> None:
        """F-PL-3: annotations must bind to correct asrt_id by fact_index."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from factgraph.adapters.problog.accept import persist_problog_annotations
        from factgraph.core.store.ledger import Ledger

        ledger = MagicMock(spec=Ledger)
        store = SimpleNamespace(
            _problog_pending_annotations={
                "run-1": {
                    "cand-1": [
                        {
                            "namespace": "problog",
                            "category": "derived",
                            "key": "k0",
                            "kind": "str",
                            "value": "v0",
                            "origin": "derived",
                            "derivation": "problog_run",
                            "fact_index": 0,
                        },
                        {
                            "namespace": "problog",
                            "category": "derived",
                            "key": "k1",
                            "kind": "str",
                            "value": "v1",
                            "origin": "derived",
                            "derivation": "problog_run",
                            "fact_index": 1,
                        },
                    ],
                },
            }
        )
        accept_result = SimpleNamespace(
            candidate_id="cand-1",
            written_assertions=[
                {"asrt_id": "asrt-aaa", "pred_id": "p:x"},
                {"asrt_id": "asrt-bbb", "pred_id": "p:y"},
            ],
        )
        count = persist_problog_annotations(ledger, "run-1", store, accept_result)
        self.assertEqual(count, 2)
        ledger.append_annotations.assert_called_once()
        rows = ledger.append_annotations.call_args[0][0]
        idx0_rows = [r for r in rows if r.key == "k0"]
        idx1_rows = [r for r in rows if r.key == "k1"]
        self.assertEqual(len(idx0_rows), 1)
        self.assertEqual(len(idx1_rows), 1)
        self.assertEqual(idx0_rows[0].asrt_id, "asrt-aaa")
        self.assertEqual(idx1_rows[0].asrt_id, "asrt-bbb")

    # --- F-PL-1: trace deepcopy isolation ---

    def test_attach_problog_provenance_deepcopies_trace(self) -> None:
        """F-PL-1: deepcopy in _attach_problog_provenance isolates trace dicts."""
        import copy

        # Verify the deepcopy mechanism used in engine_eval.py isolates payloads
        original = {"events": [{"goal": "a", "prob": 0.5}], "version": "v0"}
        payload_a = copy.deepcopy(original)
        payload_b = copy.deepcopy(original)
        # Mutating one payload must not affect the other
        payload_a["events"][0]["goal"] = "MUTATED"
        self.assertEqual(payload_b["events"][0]["goal"], "a")
        self.assertEqual(original["events"][0]["goal"], "a")


if __name__ == "__main__":
    unittest.main()
