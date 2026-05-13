"""Runtime candidate explain tests for engine provenance surfaces."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import factpy.adapters.problog  # noqa: F401
import factpy.adapters.pyreason  # noqa: F401
from factpy.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from factpy.adapters.pyreason.session import PyReasonSession
from factpy.core.store._support import (
    PROBLOG_PROVENANCE_KIND,
    PYREASON_PROVENANCE_KIND,
)
from factpy.sdk.compile import compile_schema_from_classes
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore
from factpy.service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_ref,
    explain_runtime_tree,
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


def _pyreason_trace_dict() -> dict[str, object]:
    return {
        "engine": "pyreason",
        "trace_type": "event_log",
        "timesteps": 2,
        "node_events": [],
        "edge_events": [],
    }


class EngineProvenanceSurfaceTests(unittest.TestCase):
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

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_pyreason_candidate_explain_returns_provenance_envelope(self, mock_run) -> None:
        session_id, sdk = self._open_session()
        alice_ref = sdk.ref(User, user_id="Alice")
        derived = PyReasonSession(sdk.schema_ir)
        derived._write_node_fact_internal("user:popular", alice_ref, "true", bound=[0.8, 0.9])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=_pyreason_trace_dict(),
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

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "pyreason",
                    "inference": {
                        "derivation_id": "drv.pyreason_runtime_provenance",
                        "version": "1.0.0",
                        "target": "user:popular",
                        "head_vars": ["$u"],
                        "where": [["pred", "user:name", ["$u", "$name"]]],
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["support_kind"], PYREASON_PROVENANCE_KIND)

            explain_resp = explain_runtime_ref(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertTrue(explain_resp["ok"])
            self.assertEqual(explain_resp["explain"]["support_kind"], PYREASON_PROVENANCE_KIND)
            self.assertEqual(explain_resp["explain"]["provenance"]["engine"], "pyreason")
            self.assertEqual(explain_resp["explain"]["provenance"]["payload_type"], "event_log")

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertFalse(tree_resp["ok"])
            self.assertEqual(tree_resp["errors"][0]["kind"], "runtime_explain_not_supported")
        finally:
            close_runtime_session(session_id)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_problog_candidate_explain_returns_provenance_envelope(self, mock_run) -> None:
        session_id, sdk = self._open_session()
        alice_ref = sdk.ref(User, user_id="Alice")
        mock_run.return_value = "\n".join(
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

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "problog",
                    "inference": {
                        "derivation_id": "drv.problog_runtime_provenance",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["support_kind"], PROBLOG_PROVENANCE_KIND)

            explain_resp = explain_runtime_ref(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertTrue(explain_resp["ok"])
            self.assertEqual(explain_resp["explain"]["support_kind"], PROBLOG_PROVENANCE_KIND)
            self.assertEqual(explain_resp["explain"]["provenance"]["engine"], "problog")
            self.assertEqual(explain_resp["explain"]["provenance"]["payload_type"], "proof_trace")

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
            self.assertFalse(tree_resp["ok"])
            self.assertEqual(tree_resp["errors"][0]["kind"], "explain_not_supported")
        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
