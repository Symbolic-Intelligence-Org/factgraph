"""L4 tests for ProbLog semantic annotation parity."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import factpy.application.protocol.common  # noqa: F401 - primes audit/problog import cycle
from factpy.adapters.problog.accept import persist_problog_annotations
from factpy.adapters.souffle.package import ExportOptions, export_package
from factpy.audit.assertions import load_assertion_index
from factpy.audit.reader import load_audit_package
from factpy.sdk.dsl import Inference, Pred
from factpy.service.static_ui import _render_annotation_panel
from factpy.core.evidence.write_protocol import set_field
from factpy.sdk.dsl import vars as sdk_vars
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


class ProbLogSemanticAnnotationParityTests(unittest.TestCase):
    def _make_sdk(self) -> SDKStore:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test", "confidence": 1.0},
        )
        set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=alice_ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "confidence": 1.0},
        )
        return sdk

    def _make_derivation(self) -> Inference:
        with sdk_vars("u", "tag") as (u, tag):
            return Inference(
                id="drv.problog_tag",
                version="v1",
                where=[Pred("user:tag_seed", u, tag)],
                target="user:tag",
                head_vars=[u, tag],
            )

    def _mock_output(self, sdk: SDKStore) -> str:
        # ProbLog answer(...) follows extract_where_variables(), which sorts
        # query vars lexicographically: $tag before $u for this rule.
        return f'answer("vip","{sdk.ref(User, user_id="Alice")}"): 0.42'

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_evaluate_caches_pending_probability_annotation(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidate = sdk.evaluate(self._make_derivation(), engine="problog")[0]

        self.assertEqual(candidate.confidence, 0.42)
        self.assertEqual(candidate.confidence_kind, "probability")
        pending_by_run = getattr(sdk.store, "_problog_pending_annotations", {})
        self.assertIn(candidate.run_id, pending_by_run)
        self.assertIn(candidate.candidate_id, pending_by_run[candidate.run_id])
        template = pending_by_run[candidate.run_id][candidate.candidate_id][0]
        self.assertEqual(template["namespace"], "problog")
        self.assertEqual(template["key"], "probability")
        self.assertEqual(template["value"], 0.42)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_persist_problog_annotations_writes_annotation_and_clears_pending(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidate = sdk.evaluate(self._make_derivation(), engine="problog")[0]
        accept_result = sdk.accept(candidate)

        written = persist_problog_annotations(
            sdk.ledger,
            candidate.run_id,
            sdk.store,
            accept_result,
        )

        self.assertEqual(written, 1)
        asrt_id = accept_result.written_assertions[0]["asrt_id"]
        annotations = sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="problog")
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].key, "probability")
        self.assertAlmostEqual(float(annotations[0].value), 0.42)
        self.assertEqual(annotations[0].category, "semantic")
        self.assertEqual(annotations[0].origin, "derived")
        self.assertNotIn(candidate.run_id, getattr(sdk.store, "_problog_pending_annotations", {}))

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_persist_problog_annotations_keeps_pending_on_dry_run(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidate = sdk.evaluate(self._make_derivation(), engine="problog")[0]
        accept_result = sdk.accept(candidate, dry_run=True)

        written = persist_problog_annotations(
            sdk.ledger,
            candidate.run_id,
            sdk.store,
            accept_result,
        )

        self.assertEqual(written, 0)
        pending_by_run = getattr(sdk.store, "_problog_pending_annotations", {})
        self.assertIn(candidate.run_id, pending_by_run)
        self.assertIn(candidate.candidate_id, pending_by_run[candidate.run_id])

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_audit_export_and_static_panel_consume_problog_annotation(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidate = sdk.evaluate(self._make_derivation(), engine="problog")[0]
        accept_result = sdk.accept(candidate)
        asrt_id = accept_result.written_assertions[0]["asrt_id"]
        persist_problog_annotations(
            sdk.ledger,
            candidate.run_id,
            sdk.store,
            accept_result,
        )

        with TemporaryDirectory() as tmpdir:
            export_package(sdk.store, Path(tmpdir), ExportOptions(package_kind="audit"))
            package = load_audit_package(Path(tmpdir))
            self.assertTrue(any(row.get("namespace") == "problog" for row in package.assertion_annotations))

            assertion_index = load_assertion_index(package)
            detail = assertion_index.get_assertion_detail(asrt_id)
            self.assertIsNotNone(detail)
            annotations = detail["annotations"]
            self.assertTrue(any(row.get("namespace") == "problog" and row.get("key") == "probability" for row in annotations))

            panel = _render_annotation_panel(annotations)
            self.assertIn("ProbLog", panel)
            self.assertIn("probability", panel)
            self.assertIn("0.42", panel)


if __name__ == "__main__":
    unittest.main()
