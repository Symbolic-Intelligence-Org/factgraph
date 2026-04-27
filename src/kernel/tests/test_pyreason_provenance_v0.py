"""Tests for PyReason provenance trace carrier (adapter-local, V0 spike).

These tests use synthetic DataFrame fixtures. They do NOT run actual
PyReason reasoning, which keeps the suite fast and avoids relying on
Numba JIT warmup during normal test execution.
"""
from __future__ import annotations

import json
import unittest

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - environment-dependent
    pd = None  # type: ignore[assignment]

from kernel.adapters.pyreason.provenance import (
    PyReasonTraceV0,
    parse_pyreason_trace,
    pyreason_trace_to_dict,
)


@unittest.skipIf(pd is None, "pandas is unavailable; skipping PyReason provenance tests")
def _synthetic_nodes_trace():
    """Build a synthetic nodes_trace DataFrame matching PyReason's output shape."""
    return pd.DataFrame(
        [
            {
                "Time": 0,
                "Fixed-Point-Operation": 0,
                "Node": "Alice",
                "Label": "popular",
                "Old Bound": "[0.0,1.0]",
                "New Bound": "[1.0,1.0]",
                "Occurred Due To": "alice_popular_fact",
                "Clause-1": None,
                "Clause-2": None,
            },
            {
                "Time": 1,
                "Fixed-Point-Operation": 1,
                "Node": "Bob",
                "Label": "popular",
                "Old Bound": "[0.0,1.0]",
                "New Bound": "[1.0,1.0]",
                "Occurred Due To": "shared_pet_rule",
                "Clause-1": "[Alice]",
                "Clause-2": "[(Bob, Alice)]",
            },
            {
                "Time": 1,
                "Fixed-Point-Operation": 1,
                "Node": "Alice",
                "Label": "outdoorsy",
                "Old Bound": "[0.0,1.0]",
                "New Bound": "[0.8,0.9]",
                "Occurred Due To": "dog_owner_rule",
                "Clause-1": "[(Alice, Dog)]",
                "Clause-2": None,
            },
        ]
    )


@unittest.skipIf(pd is None, "pandas is unavailable; skipping PyReason provenance tests")
def _synthetic_edges_trace():
    """Empty edges trace (common case for node-predicate reasoning)."""
    return pd.DataFrame()


@unittest.skipIf(pd is None, "pandas is unavailable; skipping PyReason provenance tests")
class PyReasonProvenanceV0Tests(unittest.TestCase):
    def test_parse_synthetic_trace(self) -> None:
        """parse_pyreason_trace converts DataFrames to PyReasonTraceV0."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )
        self.assertIsInstance(trace, PyReasonTraceV0)
        self.assertEqual(trace.timesteps, 2)
        self.assertEqual(len(trace.node_events), 3)
        self.assertEqual(len(trace.edge_events), 0)

    def test_event_fields_parsed_correctly(self) -> None:
        """Each trace event has correct field values from the DataFrame row."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )

        event0 = trace.node_events[0]
        self.assertEqual(event0.time, 0)
        self.assertEqual(event0.component, "Alice")
        self.assertEqual(event0.component_type, "node")
        self.assertEqual(event0.label, "popular")
        self.assertEqual(event0.old_bound, (0.0, 1.0))
        self.assertEqual(event0.new_bound, (1.0, 1.0))
        self.assertEqual(event0.occurred_due_to, "alice_popular_fact")
        self.assertEqual(event0.clause_groundings, ())

        event1 = trace.node_events[1]
        self.assertEqual(event1.time, 1)
        self.assertEqual(event1.component, "Bob")
        self.assertEqual(event1.occurred_due_to, "shared_pet_rule")
        self.assertEqual(len(event1.clause_groundings), 2)

    def test_interval_bound_parsing(self) -> None:
        """Interval bounds are parsed from string '[lo,hi]' format."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )
        event2 = trace.node_events[2]
        self.assertAlmostEqual(event2.new_bound[0], 0.8)
        self.assertAlmostEqual(event2.new_bound[1], 0.9)

    def test_serialization_roundtrip(self) -> None:
        """pyreason_trace_to_dict produces a JSON-serializable dict."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )
        payload = pyreason_trace_to_dict(trace)

        self.assertEqual(payload["engine"], "pyreason")
        self.assertEqual(payload["trace_type"], "event_log")
        self.assertEqual(payload["timesteps"], 2)
        self.assertEqual(len(payload["node_events"]), 3)
        self.assertEqual(len(payload["edge_events"]), 0)

        json_text = json.dumps(payload)
        parsed = json.loads(json_text)
        self.assertEqual(parsed["node_events"][0]["component"], "Alice")
        self.assertEqual(parsed["node_events"][1]["occurred_due_to"], "shared_pet_rule")

    def test_empty_trace(self) -> None:
        """Empty DataFrames produce an empty trace."""
        trace = parse_pyreason_trace(pd.DataFrame(), pd.DataFrame(), timesteps=0)
        self.assertEqual(len(trace.node_events), 0)
        self.assertEqual(len(trace.edge_events), 0)

    def test_frozen_dataclass(self) -> None:
        """Trace and trace events are immutable."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )
        with self.assertRaises(AttributeError):
            trace.timesteps = 5  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            trace.node_events[0].time = 99  # type: ignore[misc]

    def test_trace_type_marker(self) -> None:
        """Serialized trace explicitly marks itself as event_log, not proof_tree."""
        trace = parse_pyreason_trace(
            _synthetic_nodes_trace(),
            _synthetic_edges_trace(),
            timesteps=2,
        )
        payload = pyreason_trace_to_dict(trace)
        self.assertEqual(payload["trace_type"], "event_log")
        self.assertNotEqual(payload["trace_type"], "proof_tree")


if __name__ == "__main__":
    unittest.main()
