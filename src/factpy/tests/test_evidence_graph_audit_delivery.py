from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import factpy.adapters.problog  # noqa: F401
import factpy.adapters.pyreason  # noqa: F401
from factpy.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from factpy.adapters.pyreason.session import PyReasonSession
from factpy.audit import AuditQuery, load_audit_package
from factpy.service.static_ui import _slug_id, render_audit_static_site
from factpy.sdk.compile import compile_schema_from_classes
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore
from factpy.service.runtime_v1 import (
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    export_runtime_package,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _pyreason_trace_dict(alice_ref: str) -> dict[str, object]:
    return {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": 2,
        "node_events": [
            {
                "time": 1,
                "fixpoint_op": 0,
                "component": alice_ref,
                "component_type": "node",
                "label": "popular",
                "old_bound": [0.0, 0.0],
                "new_bound": [0.8, 0.9],
                "occurred_due_to": "seed_fact",
                "clause_groundings": [],
            }
        ],
        "edge_events": [],
    }


def _problog_output(alice_ref: str) -> str:
    return "\n".join(
        [
            " call query(X1,X2) {0.00000} []",
            f'  result query(X1,X2) ("vip","{alice_ref}") {{{{}}}} {{0.00012}} []',
            " complete query(X1,X2) {0.00013} {0.00013} []",
            f' call answer("vip","{alice_ref}") {{0.00019}} [at 4:7]',
            f'  result answer("vip","{alice_ref}") ("vip","{alice_ref}") {{{{}}}} {{0.00060}} []',
            f' complete answer("vip","{alice_ref}") {{0.00061}} {{0.00042}} []',
            "",
            f'answer("vip","{alice_ref}"):\t0.42',
        ]
    )


class EvidenceGraphAuditDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> tuple[str, SDKStore]:
        schema_ir = compile_schema_from_classes([User])
        sdk = SDKStore([User], schema_ir=schema_ir)
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
            {
                "candidate": candidate,
                "options": {"approved_by": "alice"},
            },
        )
        self.assertTrue(accept_resp["ok"])
        return candidate

    def _export_package_artifacts(self, session_id: str, candidate_id: str) -> tuple[AuditQuery, str]:
        with TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "audit_package"
            export_resp = export_runtime_package(
                session_id,
                {
                    "out_dir": str(package_dir),
                    "package_kind": "audit",
                },
            )
            self.assertTrue(export_resp["ok"])

            package = load_audit_package(package_dir)
            self.assertEqual(
                package.manifest["paths"]["audit_files"]["evidence_graphs"],
                "audit/evidence_graphs.jsonl",
            )
            query = AuditQuery(package)

            site_dir = Path(tmpdir) / "site"
            render_audit_static_site(package_dir, site_dir)
            candidate_page = (
                site_dir / "candidate_evidence" / f"{_slug_id(candidate_id)}.html"
            ).read_text(encoding="utf-8")
            return query, candidate_page

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_pyreason_audit_package_exports_and_renders_evidence_graph(self, mock_run) -> None:
        session_id, sdk = self._open_session()
        alice_ref = sdk.ref(User, user_id="Alice")
        derived = PyReasonSession(sdk.schema_ir)
        derived._write_node_fact_internal("user:popular", alice_ref, "true", bound=[0.8, 0.9])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=_pyreason_trace_dict(alice_ref),
            derived_session=derived,
            config=PyReasonRunConfig(timesteps=2, atom_trace=True),
            elapsed_seconds=0.01,
        )

        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:name",
                    "e_ref": alice_ref,
                    "rest_terms": [["string", "Alice"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            candidate = self._accept_first_candidate(
                session_id,
                {
                    "derivation_id": "drv.pyreason_audit_graph",
                    "version": "1.0.0",
                    "target": "user:popular",
                    "head_vars": ["$u"],
                    "where": [["pred", "user:name", ["$u", "$name"]]],
                },
                engine="pyreason",
            )
            query, candidate_page = self._export_package_artifacts(session_id, candidate["candidate_id"])

            graph = query.get_candidate_evidence_graph(candidate["candidate_id"])
            self.assertIsNotNone(graph)
            self.assertEqual(graph.engine, "pyreason")
            self.assertEqual(graph.layout_hint, "timeline")

            tree = query.get_candidate_evidence_tree(candidate["candidate_id"])
            self.assertEqual(tree["support_kind"], "pyreason_provenance_v1")

            self.assertIn("Unified Evidence Graph", candidate_page)
            self.assertIn("Timeline Layout", candidate_page)
            self.assertIn("Engine: <strong>pyreason</strong>", candidate_page)
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_problog_audit_package_exports_and_renders_evidence_graph(self, mock_run) -> None:
        session_id, sdk = self._open_session()
        alice_ref = sdk.ref(User, user_id="Alice")
        mock_run.return_value = _problog_output(alice_ref)

        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag_seed",
                    "e_ref": alice_ref,
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            candidate = self._accept_first_candidate(
                session_id,
                {
                    "derivation_id": "drv.problog_audit_graph",
                    "version": "1.0.0",
                    "target": "user:tag",
                    "head_vars": ["$u", "$tag"],
                    "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
                },
                engine="problog",
            )
            query, candidate_page = self._export_package_artifacts(session_id, candidate["candidate_id"])

            graph = query.get_candidate_evidence_graph(candidate["candidate_id"])
            self.assertIsNotNone(graph)
            self.assertEqual(graph.engine, "problog")
            self.assertEqual(graph.layout_hint, "tree")

            tree = query.get_candidate_evidence_tree(candidate["candidate_id"])
            self.assertEqual(tree["support_kind"], "problog_provenance_v1")

            self.assertIn("Unified Evidence Graph", candidate_page)
            self.assertIn("Tree Layout", candidate_page)
            self.assertIn("Engine: <strong>problog</strong>", candidate_page)
        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
