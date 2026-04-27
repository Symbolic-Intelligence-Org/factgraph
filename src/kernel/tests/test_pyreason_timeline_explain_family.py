"""Tests for the PyReason timeline explain family: timeline/summary/narrative/NL.

Verifies that all four timeline explain endpoints return correct response
shapes for accepted PyReason candidates, and that explain-tree still returns
error (PyReason uses timeline, not tree).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import kernel.adapters.pyreason  # noqa: F401
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.store._support import PYREASON_PROVENANCE_KIND
from kernel.sdk.compile import compile_schema_from_classes
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore
from service.runtime_v1 import (
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_narrative,
    explain_runtime_nl,
    explain_runtime_summary,
    explain_runtime_timeline,
    explain_runtime_timeline_narrative,
    explain_runtime_timeline_summary,
    explain_runtime_tree,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class Vendor(Entity):
    vendor_id: str = Identity(primary_key=True)
    risk_signal: str = Field(cardinality="single")


def _pyreason_trace_with_events(e_ref: str) -> dict[str, object]:
    return {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": 2,
        "node_events": [
            {
                "time": 0,
                "fixpoint_op": 1,
                "component": e_ref,
                "component_type": "node",
                "label": "risk_signal",
                "old_bound": [0.0, 1.0],
                "new_bound": [1.0, 1.0],
                "occurred_due_to": "seed_fact",
                "clause_groundings": [],
            },
        ],
        "edge_events": [],
    }


class PyReasonTimelineExplainFamilyTests(unittest.TestCase):
    """Verify all timeline explain endpoints for accepted PyReason candidates."""

    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _setup_accepted_pyreason_candidate(self, mock_run):
        """Create session, evaluate PyReason derivation, accept candidate."""
        schema_ir = compile_schema_from_classes([Vendor])
        sdk = SDKStore([Vendor], schema_ir=schema_ir)
        acme_ref = sdk.ref(Vendor, vendor_id="ACME")

        derived = PyReasonSession(schema_ir)
        derived._write_node_fact_internal("vendor:risk_signal", acme_ref, "true", bound=[1.0, 1.0])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=_pyreason_trace_with_events(acme_ref),
            derived_session=derived,
            config=PyReasonRunConfig(timesteps=2, atom_trace=True),
            elapsed_seconds=0.01,
        )

        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]

        write_resp = write_runtime_fact(
            session_id,
            {"pred_id": "vendor:risk_signal", "e_ref": acme_ref, "rest_terms": [["string", "true"]]},
            kind="add",
        )
        self.assertTrue(write_resp["ok"])

        eval_resp = evaluate_runtime_derivation(
            session_id,
            {
                "derivation": {
                    "derivation_id": "drv.pyreason_risk",
                    "version": "1.0.0",
                    "target": "vendor:risk_signal",
                    "head_vars": ["$v"],
                    "where": [["pred", "vendor:risk_signal", ["$v", "$val"]]],
                    "mode": "pyreason",
                }
            },
        )
        self.assertTrue(eval_resp["ok"])
        candidate = eval_resp["evaluation"]["candidates"][0]
        self.assertEqual(candidate["support_kind"], PYREASON_PROVENANCE_KIND)

        # Accept the candidate so explain can reconstruct payload
        accept_resp = accept_runtime_derivation(session_id, {"candidate": candidate})
        self.assertTrue(accept_resp["ok"])

        return session_id, candidate

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_tree_returns_error_for_pyreason(self, mock_run) -> None:
        """explain-tree is tree-only; PyReason should still return error."""
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertFalse(resp["ok"])
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_timeline_returns_timeline(self, mock_run) -> None:
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_timeline(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["kind"], "candidate_provenance_timeline")
            self.assertIn("timeline", resp)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_timeline_summary_returns_summary(self, mock_run) -> None:
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_timeline_summary(
                session_id, {"kind": "candidate", "id": candidate["candidate_id"]}
            )
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["kind"], "candidate_provenance_timeline_summary")
            self.assertIn("summary", resp)
            summary = resp["summary"]
            self.assertEqual(summary["explain_kind"], "timeline")
            self.assertIn("chain_count", summary)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_timeline_narrative_returns_narrative(self, mock_run) -> None:
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_timeline_narrative(
                session_id, {"kind": "candidate", "id": candidate["candidate_id"]}
            )
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["kind"], "candidate_provenance_timeline_narrative")
            self.assertIn("narrative", resp)
            narrative = resp["narrative"]
            self.assertIn("headline", narrative)
            self.assertIn("propagation_lines", narrative)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_summary_polymorphic_returns_timeline_summary(self, mock_run) -> None:
        """explain-summary (shared endpoint) dispatches to timeline for PyReason."""
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["kind"], "candidate_provenance_timeline_summary")
            self.assertIn("summary", resp)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_narrative_polymorphic_returns_timeline_narrative(self, mock_run) -> None:
        """explain-narrative (shared endpoint) dispatches to timeline for PyReason."""
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_narrative(
                session_id, {"kind": "candidate", "id": candidate["candidate_id"]}
            )
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["kind"], "candidate_provenance_timeline_narrative")
            self.assertIn("narrative", resp)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_explain_nl_returns_timeline_nl_for_pyreason(self, mock_run) -> None:
        """explain-nl (shared endpoint) dispatches to timeline NL for PyReason.

        This is the critical test: verifies the NL early dispatch in
        explain_runtime_nl() actually routes PyReason candidates through
        the timeline NL pipeline.
        """
        session_id, candidate = self._setup_accepted_pyreason_candidate(mock_run)
        try:
            resp = explain_runtime_nl(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertTrue(resp["ok"], f"NL should succeed for accepted PyReason candidate, got: {resp}")
            self.assertEqual(resp["kind"], "candidate_provenance_timeline_nl_explain")
            self.assertIn("explain_nl", resp)
            nl = resp["explain_nl"]
            self.assertIn("headline", nl)
            self.assertIn("paragraphs", nl)
            self.assertIsInstance(nl["paragraphs"], list)
            self.assertGreater(len(nl["paragraphs"]), 0, "NL should produce at least one paragraph")
        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
