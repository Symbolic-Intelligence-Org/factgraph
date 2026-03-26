"""Tests for PyReason engine-specific write session.

Validates schema enforcement, bound handling, confidence auto-derivation,
and node/edge fact separation. No real PyReason dependency.
"""
from __future__ import annotations

import unittest

from factpy_kernel.adapters.pyreason.session import PyReasonSession


def _test_schema_ir() -> dict:
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {"pred_id": "user:tag", "arity": 2},
            {"pred_id": "friends:strength", "arity": 3, "relationship_type": "Friends",
             "from_entity_type": "User", "to_entity_type": "User"},
        ],
    }


class PyReasonSessionTests(unittest.TestCase):

    def _session(self) -> PyReasonSession:
        return PyReasonSession(_test_schema_ir())

    # ── Schema validation ──

    def test_write_node_fact_validates_pred_id(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s.write_node_fact("nonexistent:pred", "ref", "val")
        self.assertIn("not found in schema_ir", str(ctx.exception))

    def test_write_node_fact_rejects_relationship_pred(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s.write_node_fact("friends:strength", "ref", "val")
        self.assertIn("relationship predicate", str(ctx.exception))

    def test_write_edge_fact_validates_pred_id(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s.write_edge_fact("nonexistent:pred", "a", "b")
        self.assertIn("not found in schema_ir", str(ctx.exception))

    def test_write_edge_fact_rejects_non_relationship_pred(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s.write_edge_fact("user:name", "a", "b")
        self.assertIn("not a relationship predicate", str(ctx.exception))

    # ── Bound handling ──

    def test_default_bound_is_definitely_true(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice")
        self.assertEqual(s.node_facts[0]["bound"], (1.0, 1.0))

    def test_custom_bound_stored(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice", bound=[0.6, 0.9])
        self.assertEqual(s.node_facts[0]["bound"], (0.6, 0.9))

    def test_bound_validation_rejects_out_of_range(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError):
            s.write_node_fact("user:name", "ref", "val", bound=[1.5, 2.0])

    def test_bound_validation_rejects_inverted(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError):
            s.write_node_fact("user:name", "ref", "val", bound=[0.9, 0.3])

    def test_bound_accepts_zero_lower(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "val", bound=[0.0, 0.5])
        self.assertEqual(s.node_facts[0]["bound"], (0.0, 0.5))

    # ── Confidence auto-derivation ──

    def test_confidence_auto_derived_from_bound_lower(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice", bound=[0.7, 0.9])
        self.assertAlmostEqual(s.node_facts[0]["meta"]["confidence"], 0.7)

    def test_explicit_confidence_preserved(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice", bound=[0.7, 0.9],
                          meta={"confidence": 0.85})
        self.assertAlmostEqual(s.node_facts[0]["meta"]["confidence"], 0.85)

    def test_edge_fact_confidence_auto_derived(self) -> None:
        s = self._session()
        s.write_edge_fact("friends:strength", "a", "b", "0.9", bound=[0.5, 0.8])
        self.assertAlmostEqual(s.edge_facts[0]["meta"]["confidence"], 0.5)

    # ── Node/edge separation ──

    def test_node_and_edge_facts_separate(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref1", "Alice")
        s.write_node_fact("user:tag", "ref1", "vip")
        s.write_edge_fact("friends:strength", "ref1", "ref2", "0.9")
        self.assertEqual(len(s.node_facts), 2)
        self.assertEqual(len(s.edge_facts), 1)

    def test_edge_fact_stores_from_to_refs(self) -> None:
        s = self._session()
        s.write_edge_fact("friends:strength", "ref_a", "ref_b", "0.9")
        ef = s.edge_facts[0]
        self.assertEqual(ef["from_ref"], "ref_a")
        self.assertEqual(ef["to_ref"], "ref_b")

    # ── Temporal parameters ──

    def test_active_from_to_stored(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice", active_from=2, active_to=7)
        self.assertEqual(s.node_facts[0]["active_from"], 2)
        self.assertEqual(s.node_facts[0]["active_to"], 7)

    def test_default_active_from_is_zero(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice")
        self.assertEqual(s.node_facts[0]["active_from"], 0)
        self.assertIsNone(s.node_facts[0]["active_to"])

    # ── Meta passthrough ──

    def test_meta_fields_preserved(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice",
                          meta={"source": "ESA Report", "analyst": "Dr. Weber"})
        m = s.node_facts[0]["meta"]
        self.assertEqual(m["source"], "ESA Report")
        self.assertEqual(m["analyst"], "Dr. Weber")
        # confidence auto-derived
        self.assertIn("confidence", m)

    # ── Audit meta aggregation ──

    def test_all_facts_meta_includes_all(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "r1", "Alice", meta={"source": "a"})
        s.write_edge_fact("friends:strength", "r1", "r2", "0.9", meta={"source": "b"})
        all_meta = s.all_facts_meta
        self.assertEqual(len(all_meta), 2)
        self.assertEqual(all_meta[0]["meta"]["source"], "a")
        self.assertEqual(all_meta[1]["meta"]["source"], "b")

    def test_empty_session_has_no_facts(self) -> None:
        s = self._session()
        self.assertEqual(len(s.node_facts), 0)
        self.assertEqual(len(s.edge_facts), 0)
        self.assertEqual(len(s.all_facts_meta), 0)


if __name__ == "__main__":
    unittest.main()
