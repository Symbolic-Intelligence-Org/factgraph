"""Tests for PyReason runner helper."""
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from factpy.adapters.pyreason.runner import (
    PyReasonRunConfig,
    PyReasonRunResult,
    _PYREASON_LOCK,
    _extract_derived_facts,
    _parse_edge_component,
    build_pyreason_graph,
    run_pyreason,
)
from factpy.adapters.pyreason.session import PyReasonSession


def _test_schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {"pred_id": "user:popular", "arity": 2},
            {"pred_id": "user:outdoorsy", "arity": 2},
            {"pred_id": "pet:species", "arity": 2},
            {"pred_id": "pet:dog_breed", "arity": 2},
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
            {
                "pred_id": "owns:since",
                "arity": 3,
                "relationship_type": "Owns",
                "from_entity_type": "User",
                "to_entity_type": "Pet",
            },
        ],
    }


def _bounded_schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "pyreason_bounded": True,
            },
            {
                "pred_id": "user:popular",
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "popular", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "user:risk_score",
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "risk_score", "type_domain": "float64"},
                ],
                "pyreason_bounded": True,
            },
            {
                "pred_id": "friends:strength",
                "relationship_type": "Friends",
                "arg_specs": [
                    {"name": "from_ref", "type_domain": "entity_ref"},
                    {"name": "to_ref", "type_domain": "entity_ref"},
                    {"name": "strength", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "friends:trust_score",
                "relationship_type": "Friends",
                "arg_specs": [
                    {"name": "from_ref", "type_domain": "entity_ref"},
                    {"name": "to_ref", "type_domain": "entity_ref"},
                    {"name": "trust_score", "type_domain": "float64"},
                ],
                "pyreason_bounded": True,
            },
        ],
    }


class RunConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PyReasonRunConfig()
        self.assertEqual(cfg.timesteps, 1)
        self.assertTrue(cfg.atom_trace)
        self.assertIsNone(cfg.convergence_threshold)

    def test_custom(self) -> None:
        cfg = PyReasonRunConfig(timesteps=5, atom_trace=False)
        self.assertEqual(cfg.timesteps, 5)
        self.assertFalse(cfg.atom_trace)


class BuildGraphTests(unittest.TestCase):
    def _session(self) -> PyReasonSession:
        return PyReasonSession(_test_schema_ir())

    def test_empty_session_empty_graph(self) -> None:
        session = self._session()
        graph = build_pyreason_graph(session)
        self.assertEqual(graph.number_of_nodes(), 0)
        self.assertEqual(graph.number_of_edges(), 0)

    def test_node_facts_contribute_nodes_only(self) -> None:
        session = self._session()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        session._write_node_fact_internal("user:popular", "Alice", "true")
        graph = build_pyreason_graph(session)
        self.assertIn("Alice", graph.nodes)
        self.assertEqual(dict(graph.nodes["Alice"]), {})

    def test_edge_facts_become_edge_attributes(self) -> None:
        session = self._session()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        session._write_node_fact_internal("user:name", "Bob", "Bob")
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
        graph = build_pyreason_graph(session)
        self.assertTrue(graph.has_edge("Alice", "Bob"))
        self.assertEqual(graph.edges["Alice", "Bob"]["strength"], 1)

    def test_multiple_edge_facts_share_one_edge_with_multiple_attributes(self) -> None:
        session = self._session()
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
        session._write_edge_fact_internal("owns:since", "Alice", "Bob", "2024")
        graph = build_pyreason_graph(session)
        self.assertTrue(graph.has_edge("Alice", "Bob"))
        self.assertEqual(graph.edges["Alice", "Bob"]["strength"], 1)
        self.assertEqual(graph.edges["Alice", "Bob"]["since"], 1)

    def test_nodes_from_edge_refs_included(self) -> None:
        session = self._session()
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
        graph = build_pyreason_graph(session)
        self.assertIn("Alice", graph.nodes)
        self.assertIn("Bob", graph.nodes)

    def test_graph_is_directed(self) -> None:
        import networkx as nx

        session = self._session()
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
        graph = build_pyreason_graph(session)
        self.assertIsInstance(graph, nx.DiGraph)


class ParseEdgeComponentTests(unittest.TestCase):
    def test_paren_format(self) -> None:
        self.assertEqual(_parse_edge_component("(Alice, Bob)"), ("Alice", "Bob"))

    def test_dash_format(self) -> None:
        self.assertEqual(_parse_edge_component("Alice-Bob"), ("Alice", "Bob"))

    def test_unknown_format_returns_none(self) -> None:
        self.assertIsNone(_parse_edge_component("Alice"))

    def test_paren_with_spaces(self) -> None:
        self.assertEqual(_parse_edge_component("( Alice , Bob )"), ("Alice", "Bob"))


class ExtractDerivedFactsTests(unittest.TestCase):
    def _session_with_input(self) -> PyReasonSession:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[1.0, 1.0])
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        return session

    def _mock_interpretation(self, data: dict[int, dict[str, dict[str, tuple[float, float]]]]) -> object:
        class MockInterpretation:
            def __init__(self, payload) -> None:
                self._payload = payload

            def get_dict(self):
                return self._payload

        return MockInterpretation(data)

    def test_no_derived_facts_at_t0(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation({0: {"Alice": {"popular": (1.0, 1.0)}}})
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(len(derived.node_facts), 0)

    def test_derived_node_fact_at_t1(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation(
            {
                0: {"Alice": {"popular": (1.0, 1.0)}},
                1: {
                    "Alice": {"popular": (1.0, 1.0)},
                    "Bob": {"popular": (0.9, 0.9)},
                },
            }
        )
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(len(derived.node_facts), 1)
        fact = derived.node_facts[0]
        self.assertEqual(fact["pred_id"], "user:popular")
        self.assertEqual(fact["node_ref"], "Bob")
        self.assertEqual(fact["bound"], (0.9, 0.9))
        self.assertEqual(fact["active_from"], 1)

    def test_input_facts_not_duplicated(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation(
            {
                0: {"Alice": {"popular": (1.0, 1.0)}},
                1: {"Alice": {"popular": (1.0, 1.0)}},
            }
        )
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(len(derived.node_facts), 0)

    def test_zero_bound_skipped(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation({1: {"Bob": {"popular": (0.0, 0.0)}}})
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(len(derived.node_facts), 0)

    def test_unknown_pred_skipped(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation({1: {"Alice": {"unknown_attr": (1.0, 1.0)}}})
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(len(derived.node_facts), 0)

    def test_derived_facts_have_source_meta(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation({1: {"Bob": {"popular": (0.8, 0.9)}}})
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertEqual(derived.node_facts[0]["meta"]["source"], "pyreason_derived")

    def test_derived_session_has_annotation_templates(self) -> None:
        session = self._session_with_input()
        interpretation = self._mock_interpretation({1: {"Bob": {"popular": (0.8, 0.9)}}})
        derived = _extract_derived_facts(interpretation, _test_schema_ir(), session)
        self.assertGreater(len(derived.annotation_templates), 0)


class BoundedRoutingTests(unittest.TestCase):
    def _session(self) -> PyReasonSession:
        return PyReasonSession(_bounded_schema_ir())

    def _mock_interpretation(self, data: dict[int, dict[str, dict[str, tuple[float, float]]]]) -> object:
        class MockInterpretation:
            def __init__(self, payload) -> None:
                self._payload = payload

            def get_dict(self):
                return self._payload

        return MockInterpretation(data)

    def test_bounded_node_fact_does_not_write_graph_attributes(self) -> None:
        session = self._session()
        session._write_node_fact_internal("user:risk_score", "Alice", "0.85")
        session._write_node_fact_internal("user:name", "Alice", "0.85")

        graph = build_pyreason_graph(session, schema_ir=_bounded_schema_ir())

        self.assertIn("Alice", graph.nodes)
        self.assertEqual(dict(graph.nodes["Alice"]), {})

    def test_bounded_edge_fact_uses_bound_summary_on_graph_attribute(self) -> None:
        session = self._session()
        session._write_edge_fact_internal("friends:trust_score", "Alice", "Bob", "0.9", bound=[0.9, 0.9])
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")

        graph = build_pyreason_graph(session, schema_ir=_bounded_schema_ir())

        self.assertTrue(graph.has_edge("Alice", "Bob"))
        self.assertEqual(graph.edges["Alice", "Bob"]["trust_score"], 0.9)
        self.assertEqual(graph.edges["Alice", "Bob"]["strength"], 1)

    def test_invalid_bounded_edge_value_falls_back_to_default_graph_truth(self) -> None:
        session = self._session()
        session._write_node_fact_internal("user:risk_score", "Alice", "1.2")
        session._write_edge_fact_internal("friends:trust_score", "Alice", "Bob", "-0.1")

        graph = build_pyreason_graph(session, schema_ir=_bounded_schema_ir())

        self.assertIn("Alice", graph.nodes)
        self.assertTrue(graph.has_edge("Alice", "Bob"))
        self.assertEqual(graph.edges["Alice", "Bob"]["trust_score"], 1)

    def test_extract_derived_uses_bound_summary_only_for_bounded_preds(self) -> None:
        session = self._session()
        session._write_node_fact_internal("user:name", "Alice", "Alice")

        interpretation = self._mock_interpretation(
            {
                1: {
                    "Bob": {
                        "risk_score": (0.85, 0.9),
                        "popular": (1.0, 1.0),
                    }
                }
            }
        )

        derived = _extract_derived_facts(interpretation, _bounded_schema_ir(), session)
        by_pred = {str(fact["pred_id"]): fact for fact in derived.node_facts}

        self.assertEqual(by_pred["user:risk_score"]["value"], "0.85")
        self.assertEqual(by_pred["user:popular"]["value"], "true")

    def test_extract_derived_bounded_edge_uses_lower_bound_string(self) -> None:
        session = self._session()
        interpretation = self._mock_interpretation(
            {
                1: {
                    "(Alice, Bob)": {
                        "trust_score": (0.7, 0.9),
                        "strength": (1.0, 1.0),
                    }
                }
            }
        )

        derived = _extract_derived_facts(interpretation, _bounded_schema_ir(), session)
        by_pred = {str(fact["pred_id"]): fact for fact in derived.edge_facts}

        self.assertEqual(by_pred["friends:trust_score"]["value"], "0.7")
        self.assertEqual(by_pred["friends:strength"]["value"], "")


class RunResultShapeTests(unittest.TestCase):
    def test_result_fields(self) -> None:
        result = PyReasonRunResult(
            interpretation=None,
            trace=None,
            trace_dict=None,
            derived_session=PyReasonSession(_test_schema_ir()),
            config=PyReasonRunConfig(),
            elapsed_seconds=1.5,
        )
        self.assertIsNone(result.interpretation)
        self.assertIsNone(result.trace)
        self.assertAlmostEqual(result.elapsed_seconds, 1.5)
        self.assertEqual(result.config.timesteps, 1)


class LockAndCleanupTests(unittest.TestCase):
    """Tests for F-PR-1: PyReason global state isolation and exception cleanup."""

    def _make_mock_pr(self) -> MagicMock:
        mock_pr = MagicMock()
        mock_interp = MagicMock()
        mock_interp.get_dict.return_value = {}
        mock_pr.reason.return_value = mock_interp
        mock_pr.get_rule_trace.return_value = (None, None)
        return mock_pr

    def _make_session(self) -> PyReasonSession:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        return session

    def test_pyreason_lock_is_threading_lock(self) -> None:
        self.assertIsInstance(_PYREASON_LOCK, type(threading.Lock()))

    def test_lock_held_during_reason(self) -> None:
        """Verify _PYREASON_LOCK is held while pr.reason() executes."""
        lock_was_held: list[bool] = []
        mock_pr = self._make_mock_pr()
        mock_interp = MagicMock()
        mock_interp.get_dict.return_value = {}

        def reason_side_effect(**kwargs: object) -> MagicMock:
            lock_was_held.append(_PYREASON_LOCK.locked())
            return mock_interp

        mock_pr.reason.side_effect = reason_side_effect

        with patch.dict("sys.modules", {"pyreason": mock_pr}):
            run_pyreason(self._make_session(), config=PyReasonRunConfig(atom_trace=False))

        self.assertEqual(lock_was_held, [True])

    def test_reset_called_on_exception(self) -> None:
        """pr.reset() must be called in finally even when pr.reason() throws."""
        mock_pr = self._make_mock_pr()
        mock_pr.reason.side_effect = RuntimeError("engine failure")

        with patch.dict("sys.modules", {"pyreason": mock_pr}):
            with self.assertRaises(RuntimeError):
                run_pyreason(self._make_session(), config=PyReasonRunConfig(atom_trace=False))

        # pr.reset() should have been called twice:
        # once before try (initial cleanup), once in finally (exception cleanup)
        reset_calls = [c for c in mock_pr.method_calls if c[0] == "reset"]
        self.assertEqual(len(reset_calls), 2)

    def test_lock_released_after_exception(self) -> None:
        """Lock must be released even when pr.reason() throws."""
        mock_pr = self._make_mock_pr()
        mock_pr.reason.side_effect = RuntimeError("engine failure")

        with patch.dict("sys.modules", {"pyreason": mock_pr}):
            with self.assertRaises(RuntimeError):
                run_pyreason(self._make_session(), config=PyReasonRunConfig(atom_trace=False))

        self.assertFalse(_PYREASON_LOCK.locked())


if __name__ == "__main__":
    unittest.main()
