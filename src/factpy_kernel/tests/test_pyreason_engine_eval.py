"""Tests for the PyReason engine evaluator."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

from factpy_kernel.adapters.pyreason.engine_eval import (
    _materialize_edb_session,
    pyreason_engine_eval,
)
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store._support import ENGINE_NO_WITNESS_KIND
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.core.store.runtime import get_engine_evaluator
from factpy_kernel.core.store.types import EngineExtBase


@dataclass(frozen=True)
class MockPyReasonRuleExt(EngineExtBase):
    timestep_delay: int = 0


def _test_schema_ir() -> dict[str, Any]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "arity": 2,
                "cardinality": "single",
                "group_key_indexes": [0],
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "user:popular",
                "arity": 2,
                "cardinality": "single",
                "group_key_indexes": [0],
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "popular", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "cardinality": "single",
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
                "group_key_indexes": [0, 1],
                "arg_specs": [
                    {"name": "from_ref", "type_domain": "entity_ref"},
                    {"name": "to_ref", "type_domain": "entity_ref"},
                    {"name": "strength", "type_domain": "string"},
                ],
            },
        ],
    }


def _mock_store_with_facts(facts: list[dict[str, Any]]) -> Any:
    ledger = Ledger()
    for fact in facts:
        set_field(
            ledger,
            pred_id=fact["pred_id"],
            e_ref=fact["e_ref"],
            rest_terms=fact.get("rest_terms", []),
            meta=fact.get("meta", {}),
        )

    class MockStore:
        pass

    store = MockStore()
    store.schema_ir = _test_schema_ir()
    store.ledger = ledger
    return store


class MaterializeEDBTests(unittest.TestCase):
    def test_empty_ledger_produces_empty_session(self) -> None:
        store = _mock_store_with_facts([])
        session = _materialize_edb_session(store, store.schema_ir)
        self.assertEqual(session.node_facts, [])
        self.assertEqual(session.edge_facts, [])

    def test_node_fact_materialized_with_default_bound(self) -> None:
        store = _mock_store_with_facts(
            [
                {
                    "pred_id": "user:name",
                    "e_ref": "idref_v1:User:Alice",
                    "rest_terms": [("string", "Alice")],
                }
            ]
        )
        session = _materialize_edb_session(store, store.schema_ir)
        self.assertEqual(len(session.node_facts), 1)
        fact = session.node_facts[0]
        self.assertEqual(fact["pred_id"], "user:name")
        self.assertEqual(fact["bound"], (1.0, 1.0))

    def test_edge_fact_materialized_with_default_bound(self) -> None:
        store = _mock_store_with_facts(
            [
                {
                    "pred_id": "friends:strength",
                    "e_ref": "idref_v1:User:Alice",
                    "rest_terms": [("entity_ref", "idref_v1:User:Bob"), ("string", "0.9")],
                }
            ]
        )
        session = _materialize_edb_session(store, store.schema_ir)
        self.assertEqual(len(session.edge_facts), 1)
        fact = session.edge_facts[0]
        self.assertEqual(fact["pred_id"], "friends:strength")
        self.assertEqual(fact["bound"], (1.0, 1.0))


class EngineEvalRegistrationTests(unittest.TestCase):
    def test_registration_on_import(self) -> None:
        import factpy_kernel.adapters.pyreason  # noqa: F401

        evaluator = get_engine_evaluator("pyreason")
        self.assertIs(evaluator, pyreason_engine_eval)


class EngineEvalTests(unittest.TestCase):
    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_pending_annotations_cached_on_store(self, mock_run: Any) -> None:
        derived = PyReasonSession(_test_schema_ir())
        derived._write_node_fact_internal("user:popular", "idref_v1:User:Alice", "true", bound=[0.8, 0.9])
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=None,
            derived_session=derived,
            config=PyReasonRunConfig(),
            elapsed_seconds=0.01,
        )

        store = _mock_store_with_facts(
            [
                {
                    "pred_id": "user:name",
                    "e_ref": "idref_v1:User:Alice",
                    "rest_terms": [("string", "Alice")],
                }
            ]
        )
        candidates = pyreason_engine_eval(
            store,
            derivation_id="drv.popular",
            version="1.0.0",
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            engine_ext=MockPyReasonRuleExt(timestep_delay=2),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].support_kind, ENGINE_NO_WITNESS_KIND)
        self.assertEqual(candidates[0].support_digest, f"sha256:{'0' * 64}")
        self.assertAlmostEqual(candidates[0].confidence or 0.0, 0.8)
        self.assertTrue(hasattr(store, "_engine_pending_annotations"))
        self.assertIn(candidates[0].run_id, store._engine_pending_annotations)
        pending = store._engine_pending_annotations[candidates[0].run_id]
        self.assertGreaterEqual(len(pending), 4)

    @patch("factpy_kernel.adapters.pyreason.engine_eval.run_pyreason")
    def test_edge_candidate_includes_to_ref_in_key(self, mock_run: Any) -> None:
        derived = PyReasonSession(_test_schema_ir())
        derived._write_edge_fact_internal(
            "friends:strength",
            "idref_v1:User:Alice",
            "idref_v1:User:Bob",
            "",
            bound=[0.7, 0.9],
        )
        mock_run.return_value = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=None,
            derived_session=derived,
            config=PyReasonRunConfig(),
            elapsed_seconds=0.01,
        )

        store = _mock_store_with_facts([])
        candidates = pyreason_engine_eval(
            store,
            derivation_id="drv.strength",
            version="1.0.0",
            target_pred_id="friends:strength",
            head_vars=["$x", "$y"],
            where=[("pred", "user:popular", ["$x", "$v"])],
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].target, "friends:strength")
        self.assertEqual(candidates[0].payload["terms"][1]["value"], "idref_v1:User:Bob")


if __name__ == "__main__":
    unittest.main()
