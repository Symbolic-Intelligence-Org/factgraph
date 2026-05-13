"""Tests for provenance_timelines.jsonl audit export + AuditQuery round-trip."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import kernel.adapters.pyreason  # noqa: F401
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.audit import AuditQuery, load_audit_package
from kernel.sdk.compile import compile_schema_from_classes
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore
from service.runtime_v1 import (
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    export_runtime_package,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class Vendor(Entity):
    vendor_id: str = Identity(primary_key=True)
    at_risk_signal: str = Field(cardinality="single")
    name: str = Field(cardinality="single")


def _pyreason_trace_dict(vendor_ref: str) -> dict[str, object]:
    return {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": 2,
        "node_events": [
            {
                "time": 0,
                "fixpoint_op": 0,
                "component": vendor_ref,
                "component_type": "node",
                "label": "at_risk_signal",
                "old_bound": [0.0, 1.0],
                "new_bound": [1.0, 1.0],
                "occurred_due_to": "seed_fact",
                "clause_groundings": [],
            },
            {
                "time": 1,
                "fixpoint_op": 1,
                "component": vendor_ref,
                "component_type": "node",
                "label": "at_risk_signal",
                "old_bound": [1.0, 1.0],
                "new_bound": [1.0, 1.0],
                "occurred_due_to": "risk_propagation",
                "clause_groundings": ["[ACME]"],
            },
        ],
        "edge_events": [],
    }


class ProvenanceTimelineAuditDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> tuple[str, SDKStore]:
        schema_ir = compile_schema_from_classes([Vendor])
        sdk = SDKStore([Vendor], schema_ir=schema_ir)
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        return open_resp["session"]["session_id"], sdk

    def _accept_first_candidate(
        self,
        session_id: str,
        derivation: dict[str, object],
        *,
        engine: str = "native",
    ) -> dict[str, object]:
        eval_resp = evaluate_runtime_derivation(
            session_id,
            {"engine": engine, "inference": derivation},
        )
        self.assertTrue(eval_resp["ok"])
        candidate = dict(eval_resp["evaluation"]["candidates"][0])
        accept_resp = accept_runtime_derivation(
            session_id,
            {"candidate": candidate, "options": {"approved_by": "test"}},
        )
        self.assertTrue(accept_resp["ok"])
        return candidate

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_pyreason_audit_package_exports_provenance_timelines_jsonl(self, mock_run) -> None:
        """provenance_timelines.jsonl is written and AuditQuery can read it back."""
        session_id, sdk = self._open_session()
        acme_ref = sdk.ref(Vendor, vendor_id="ACME")
        derived = PyReasonSession(sdk.schema_ir)
        derived._write_node_fact_internal("vendor:at_risk_signal", acme_ref, "true", bound=[1.0, 1.0])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=_pyreason_trace_dict(acme_ref),
            derived_session=derived,
            config=PyReasonRunConfig(timesteps=2, atom_trace=True),
            elapsed_seconds=0.01,
        )

        try:
            write_runtime_fact(
                session_id,
                {"pred_id": "vendor:name", "e_ref": acme_ref, "rest_terms": [["string", "ACME Corp"]]},
                kind="add",
            )
            candidate = self._accept_first_candidate(
                session_id,
                {
                    "derivation_id": "drv.pyreason_timeline",
                    "version": "1.0.0",
                    "target": "vendor:at_risk_signal",
                    "head_vars": ["$v"],
                    "where": [["pred", "vendor:name", ["$v", "$name"]]],
                },
                engine="pyreason",
            )

            with TemporaryDirectory() as tmpdir:
                pkg_dir = Path(tmpdir) / "audit_pkg"
                export_resp = export_runtime_package(
                    session_id, {"out_dir": str(pkg_dir), "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])

                # Verify file exists
                timeline_jsonl = pkg_dir / "audit" / "provenance_timelines.jsonl"
                self.assertTrue(timeline_jsonl.exists(), "provenance_timelines.jsonl not written")

                # Verify manifest entry
                package = load_audit_package(pkg_dir)
                audit_files = package.manifest["paths"]["audit_files"]
                self.assertIn("provenance_timelines", audit_files)
                self.assertEqual(audit_files["provenance_timelines"], "audit/provenance_timelines.jsonl")

                # Verify AuditQuery round-trip
                query = AuditQuery(package)
                cid = candidate["candidate_id"]

                timeline = query.get_candidate_provenance_timeline(cid)
                self.assertIsNotNone(timeline, "timeline not found via AuditQuery")
                self.assertEqual(timeline["kind"], "candidate_provenance_timeline")
                self.assertEqual(timeline["engine"], "pyreason")
                self.assertEqual(timeline["candidate_id"], cid)
                self.assertGreater(len(timeline["chains"]), 0)

                # Verify summary derivation
                summary = query.get_candidate_timeline_summary(cid)
                self.assertIsNotNone(summary)
                self.assertEqual(summary["explain_kind"], "timeline")
                self.assertGreater(summary["chain_count"], 0)

        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_non_pyreason_candidate_not_in_provenance_timelines(self, mock_run) -> None:
        """Native/problog candidates should NOT appear in provenance_timelines.jsonl."""
        import kernel.adapters.problog  # noqa: F401

        session_id, sdk = self._open_session()
        acme_ref = sdk.ref(Vendor, vendor_id="ACME")

        try:
            write_runtime_fact(
                session_id,
                {"pred_id": "vendor:name", "e_ref": acme_ref, "rest_terms": [["string", "ACME"]]},
                kind="add",
            )
            # Native mode candidate — should not produce timeline
            candidate = self._accept_first_candidate(
                session_id,
                {
                    "derivation_id": "drv.native_no_timeline",
                    "version": "1.0.0",
                    "target": "vendor:name",
                    "head_vars": ["$v", "$name"],
                    "where": [["pred", "vendor:name", ["$v", "$name"]]],
                },
            )

            with TemporaryDirectory() as tmpdir:
                pkg_dir = Path(tmpdir) / "audit_pkg"
                export_resp = export_runtime_package(
                    session_id, {"out_dir": str(pkg_dir), "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])

                package = load_audit_package(pkg_dir)
                query = AuditQuery(package)

                # Native candidate should have no timeline
                timeline = query.get_candidate_provenance_timeline(candidate["candidate_id"])
                self.assertIsNone(timeline)

        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_provenance_timelines_coexist_with_evidence_graphs(self, mock_run) -> None:
        """Both provenance_timelines.jsonl and evidence_graphs.jsonl should be exported for pyreason."""
        session_id, sdk = self._open_session()
        acme_ref = sdk.ref(Vendor, vendor_id="ACME")
        derived = PyReasonSession(sdk.schema_ir)
        derived._write_node_fact_internal("vendor:at_risk_signal", acme_ref, "true", bound=[1.0, 1.0])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=_pyreason_trace_dict(acme_ref),
            derived_session=derived,
            config=PyReasonRunConfig(timesteps=2, atom_trace=True),
            elapsed_seconds=0.01,
        )

        try:
            write_runtime_fact(
                session_id,
                {"pred_id": "vendor:name", "e_ref": acme_ref, "rest_terms": [["string", "ACME"]]},
                kind="add",
            )
            candidate = self._accept_first_candidate(
                session_id,
                {
                    "derivation_id": "drv.pyreason_coexist",
                    "version": "1.0.0",
                    "target": "vendor:at_risk_signal",
                    "head_vars": ["$v"],
                    "where": [["pred", "vendor:name", ["$v", "$name"]]],
                },
                engine="pyreason",
            )
            cid = candidate["candidate_id"]

            with TemporaryDirectory() as tmpdir:
                pkg_dir = Path(tmpdir) / "audit_pkg"
                export_runtime_package(
                    session_id, {"out_dir": str(pkg_dir), "package_kind": "audit"},
                )

                package = load_audit_package(pkg_dir)
                query = AuditQuery(package)

                # Both should exist for the same pyreason candidate
                timeline = query.get_candidate_provenance_timeline(cid)
                evidence_graph = query.get_candidate_evidence_graph(cid)

                self.assertIsNotNone(timeline)
                self.assertIsNotNone(evidence_graph)

                # They serve different purposes
                self.assertEqual(timeline["kind"], "candidate_provenance_timeline")
                self.assertEqual(evidence_graph.engine, "pyreason")
                self.assertEqual(evidence_graph.layout_hint, "timeline")

        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
