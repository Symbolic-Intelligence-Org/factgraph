"""End-to-end integration tests for the PyReason execution surface."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import factpy_kernel.adapters.pyreason  # noqa: F401
from factpy_kernel.adapters.pyreason.accept import persist_pyreason_annotations
from factpy_kernel.adapters.pyreason.rule_ext import PyReasonRuleExt
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.adapters.pyreason.where_compile import PyReasonWhereCompileError
from factpy_kernel.core.derivation.accept import AcceptOptions
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.ledger import Claim
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.sdk.dsl import Derivation, Pred, vars as sdk_vars
from factpy_kernel.sdk.schema import Entity, Field, Identity, Relationship
from factpy_kernel.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


def _mock_run_pyreason(session, *, rules=None, rule_defs=None, facts=None, fact_defs=None, config=None):
    del rule_defs
    del facts
    del fact_defs

    alice_ref = next(
        (
            fact.get("node_ref")
            for fact in session.node_facts
            if fact.get("pred_id") == "user:name" and fact.get("value") == "Alice"
        ),
        None,
    )
    if not isinstance(alice_ref, str) or not alice_ref:
        alice_ref = "idref_v1:User:Alice"

    derived = PyReasonSession(session._schema_ir)
    derived._write_node_fact_internal(
        "user:popular",
        alice_ref,
        "true",
        bound=[0.8, 0.9],
    )
    return PyReasonRunResult(
        interpretation=None,
        trace=None,
        trace_dict=None,
        derived_session=derived,
        config=config or PyReasonRunConfig(),
        elapsed_seconds=0.01,
    )


class PyReasonExecutionSurfaceE2ETests(unittest.TestCase):
    def _make_sdk(self) -> SDKStore:
        schema_ir = compile_schema_from_classes([User, Friends])
        for pred in schema_ir.get("predicates", []):
            if isinstance(pred, dict) and pred.get("relationship_type") and not pred.get("owner_type"):
                pred["owner_type"] = pred["relationship_type"]
        sdk = SDKStore([User], schema_ir=schema_ir)

        alice_ref = sdk.ref(User, user_id="Alice")
        bob_ref = sdk.ref(User, user_id="Bob")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test", "confidence": 1.0},
        )
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=bob_ref,
            rest_terms=[("string", "Bob")],
            meta={"source": "test", "confidence": 1.0},
        )
        set_field(
            sdk.ledger,
            pred_id="friends:strength",
            e_ref=alice_ref,
            rest_terms=[("entity_ref", bob_ref), ("string", "0.9")],
            meta={"source": "test", "confidence": 1.0},
        )
        return sdk

    def _make_derivation(self, *, engine_ext: PyReasonRuleExt | None = None, where=None) -> Derivation:
        with sdk_vars("u", "name") as (u, name):
            return Derivation(
                id="drv.pyreason_popular",
                version="v1",
                where=where if where is not None else [Pred("user:name", u, name)],
                target="user:popular",
                head_vars=[u],
                mode="pyreason",
                engine_ext=engine_ext,
            )

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_sdk_evaluate_derivation_returns_candidates(self, mock_run) -> None:
        sdk = self._make_sdk()
        derivation = self._make_derivation()

        candidates = sdk.evaluate(derivation)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.derivation_id, "drv.pyreason_popular")
        self.assertEqual(candidate.derivation_version, "v1")
        self.assertEqual(candidate.target, "user:popular")
        self.assertEqual(candidate.support_kind, "engine_no_witness_v1")
        self.assertEqual(candidate.state, "generated")
        self.assertEqual(candidate.payload["pred_id"], "user:popular")
        self.assertEqual(candidate.payload["terms"][0]["value"], sdk.ref(User, user_id="Alice"))
        self.assertEqual(candidate.payload["terms"][1]["value"], "true")
        self.assertEqual(candidate.confidence, 0.8)
        mock_run.assert_called_once()

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_engine_ext_flows_outside_compiled_payload(self, mock_run) -> None:
        sdk = self._make_sdk()
        derivation = self._make_derivation(engine_ext=PyReasonRuleExt(timestep_delay=2))

        compiled = sdk._compile_derivation_input(derivation)
        self.assertEqual(compiled[0]["mode"], "pyreason")
        self.assertNotIn("engine_ext", compiled[0])

        sdk.evaluate(derivation)

        rules = mock_run.call_args.kwargs["rules"]
        self.assertEqual(len(rules), 1)
        self.assertIn("<-2", rules[0][0])

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_runner_receives_materialized_edb_from_ledger(self, mock_run) -> None:
        sdk = self._make_sdk()
        derivation = self._make_derivation()

        sdk.evaluate(derivation)

        session = mock_run.call_args.args[0]
        self.assertEqual(len(session.node_facts), 2)
        self.assertEqual(len(session.edge_facts), 1)
        node_pred_ids = {fact["pred_id"] for fact in session.node_facts}
        self.assertEqual(node_pred_ids, {"user:name"})
        self.assertEqual(session.edge_facts[0]["pred_id"], "friends:strength")

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_core_accept_persists_claim_and_pending_annotations(self, mock_run) -> None:
        del mock_run
        sdk = self._make_sdk()
        derivation = self._make_derivation(engine_ext=PyReasonRuleExt(timestep_delay=1))

        candidates = sdk.evaluate(derivation)
        candidate = candidates[0]

        self.assertTrue(hasattr(sdk.store, "_engine_pending_annotations"))
        self.assertIn(candidate.run_id, sdk.store._engine_pending_annotations)

        accept_result = sdk.store.accept(
            derivation_id=candidate.derivation_id,
            version=candidate.derivation_version,
            candidate_set=candidate,
            options=AcceptOptions(),
        )

        self.assertEqual(accept_result.accepted_count, 1)
        self.assertEqual(accept_result.skipped_count, 0)
        self.assertEqual(len(accept_result.written_assertions), 1)

        asrt_id = accept_result.written_assertions[0]["asrt_id"]
        claim = sdk.ledger.get_claim(asrt_id)
        self.assertEqual(
            claim,
            Claim(
                asrt_id=asrt_id,
                pred_id="user:popular",
                e_ref=sdk.ref(User, user_id="Alice"),
                rest_terms=[("string", "true")],
            ),
        )

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_post_accept_annotation_persist_binds_pending_templates(self, mock_run) -> None:
        del mock_run
        sdk = self._make_sdk()
        derivation = self._make_derivation(engine_ext=PyReasonRuleExt(timestep_delay=1))

        candidate = sdk.evaluate(derivation)[0]
        accept_result = sdk.store.accept(
            derivation_id=candidate.derivation_id,
            version=candidate.derivation_version,
            candidate_set=candidate,
            options=AcceptOptions(),
        )
        asrt_id = accept_result.written_assertions[0]["asrt_id"]

        self.assertEqual(sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason"), [])

        written_count = persist_pyreason_annotations(
            sdk.ledger,
            candidate.run_id,
            sdk.store,
            accept_result,
        )

        self.assertGreaterEqual(written_count, 2)
        self.assertNotIn(candidate.run_id, getattr(sdk.store, "_engine_pending_annotations", {}))

        saved = sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        saved_keys = {row.key for row in saved}
        self.assertIn("bound_lower", saved_keys)
        self.assertIn("bound_upper", saved_keys)

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_persist_helper_writes_annotations(self, mock_run) -> None:
        del mock_run
        sdk = self._make_sdk()
        derivation = self._make_derivation()

        candidate = sdk.evaluate(derivation)[0]
        accept_result = sdk.store.accept(
            derivation_id=candidate.derivation_id,
            version=candidate.derivation_version,
            candidate_set=candidate,
            options=AcceptOptions(),
        )

        count = persist_pyreason_annotations(
            sdk.ledger,
            candidate.run_id,
            sdk.store,
            accept_result,
        )

        self.assertGreater(count, 0)
        asrt_id = accept_result.written_assertions[0]["asrt_id"]
        saved = sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        self.assertGreaterEqual(len(saved), 2)

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_pyreason)
    def test_sdk_evaluate_rejects_unsupported_where_atom(self, mock_run) -> None:
        sdk = self._make_sdk()
        derivation = self._make_derivation(where=[("eq", "$u", "Alice")])

        with self.assertRaises(PyReasonWhereCompileError):
            sdk.evaluate(derivation)

        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
