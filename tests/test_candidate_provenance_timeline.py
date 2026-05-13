"""Tests for CandidateProvenanceTimeline builder, summary, and narrative.

Blueprint: 2026-03-30_pyreason-runtime-explain-timeline.md
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from factpy.core.store._candidate_provenance_timeline import (
    CandidateProvenanceTimeline,
    TimelineChain,
    TimelineEvent,
    build_candidate_provenance_timeline,
    summarize_candidate_provenance_timeline,
    render_candidate_provenance_timeline_narrative,
)


# ---------------------------------------------------------------------------
# Minimal stub that matches PyReasonTraceV0 shape (duck-typed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubEvent:
    time: int
    fixpoint_op: int
    component: str
    component_type: str
    label: str
    old_bound: tuple[float, float]
    new_bound: tuple[float, float]
    occurred_due_to: str
    clause_groundings: tuple[str, ...]


@dataclass(frozen=True)
class _StubTrace:
    timesteps: int
    node_events: tuple[_StubEvent, ...]
    edge_events: tuple[_StubEvent, ...]


def _make_payload(pred_id: str, entity_ref: str) -> dict[str, Any]:
    """Build a minimal candidate payload for a single-entity-ref predicate."""
    return {
        "pred_id": pred_id,
        "terms": [{"kind": "entity_ref", "value": entity_ref}],
    }


class TestBuildCandidateProvenanceTimeline(unittest.TestCase):
    """Step 1: builder correctness."""

    def _make_trace(self) -> _StubTrace:
        return _StubTrace(
            timesteps=2,
            node_events=(
                _StubEvent(
                    time=0, fixpoint_op=1,
                    component="ACME", component_type="node",
                    label="at_risk", old_bound=(0.0, 1.0), new_bound=(1.0, 1.0),
                    occurred_due_to="seed_fact", clause_groundings=(),
                ),
                _StubEvent(
                    time=1, fixpoint_op=2,
                    component="PAY", component_type="node",
                    label="at_risk", old_bound=(0.0, 1.0), new_bound=(1.0, 1.0),
                    occurred_due_to="risk_prop", clause_groundings=("[ACME]",),
                ),
                _StubEvent(
                    time=0, fixpoint_op=1,
                    component="PAY", component_type="node",
                    label="gap", old_bound=(0.0, 1.0), new_bound=(1.0, 1.0),
                    occurred_due_to="seed_fact", clause_groundings=(),
                ),
            ),
            edge_events=(),
        )

    def test_basic_build(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "PAY")
        result = build_candidate_provenance_timeline(
            candidate_id="cand-1", trace=trace, candidate_payload=payload,
        )
        self.assertEqual(result["kind"], "candidate_provenance_timeline")
        self.assertEqual(result["candidate_id"], "cand-1")
        self.assertEqual(result["engine"], "pyreason")
        self.assertEqual(result["timesteps"], 2)

    def test_chains_sorted_by_key(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "PAY")
        result = build_candidate_provenance_timeline(
            candidate_id="cand-1", trace=trace, candidate_payload=payload,
        )
        chains = result["chains"]
        keys = [(c["component_type"], c["component"], c["label"]) for c in chains]
        self.assertEqual(keys, sorted(keys))

    def test_root_chain_key_matches_payload(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "PAY")
        result = build_candidate_provenance_timeline(
            candidate_id="cand-1", trace=trace, candidate_payload=payload,
        )
        root_key = tuple(result["root_chain_key"])
        self.assertEqual(root_key, ("node", "PAY", "at_risk"))

    def test_events_ordered_within_chain(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "PAY")
        result = build_candidate_provenance_timeline(
            candidate_id="cand-1", trace=trace, candidate_payload=payload,
        )
        for chain in result["chains"]:
            events = chain["events"]
            times = [(e["time"], e["fixpoint_op"]) for e in events]
            self.assertEqual(times, sorted(times))

    def test_missing_root_raises(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "MISSING_ENTITY")
        with self.assertRaises(ValueError) as ctx:
            build_candidate_provenance_timeline(
                candidate_id="cand-1", trace=trace, candidate_payload=payload,
            )
        self.assertIn("candidate anchor not found", str(ctx.exception))

    def test_empty_trace_raises(self) -> None:
        trace = _StubTrace(timesteps=0, node_events=(), edge_events=())
        payload = _make_payload("vendor:at_risk", "ACME")
        with self.assertRaises(ValueError):
            build_candidate_provenance_timeline(
                candidate_id="cand-1", trace=trace, candidate_payload=payload,
            )

    def test_empty_candidate_id_raises(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "ACME")
        with self.assertRaises(ValueError):
            build_candidate_provenance_timeline(
                candidate_id="", trace=trace, candidate_payload=payload,
            )

    def test_groundings_preserved(self) -> None:
        trace = self._make_trace()
        payload = _make_payload("vendor:at_risk", "PAY")
        result = build_candidate_provenance_timeline(
            candidate_id="cand-1", trace=trace, candidate_payload=payload,
        )
        # Find the PAY at_risk chain
        pay_at_risk = [
            c for c in result["chains"]
            if c["component"] == "PAY" and c["label"] == "at_risk"
        ]
        self.assertEqual(len(pay_at_risk), 1)
        events = pay_at_risk[0]["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["groundings"], ["[ACME]"])

    def test_edge_component_normalization(self) -> None:
        trace = _StubTrace(
            timesteps=1,
            node_events=(),
            edge_events=(
                _StubEvent(
                    time=0, fixpoint_op=1,
                    component="('A', 'B')", component_type="edge",
                    label="link", old_bound=(0.0, 1.0), new_bound=(1.0, 1.0),
                    occurred_due_to="seed_fact", clause_groundings=(),
                ),
            ),
        )
        payload = {
            "pred_id": "rel:link",
            "terms": [
                {"kind": "entity_ref", "value": "A"},
                {"kind": "entity_ref", "value": "B"},
            ],
        }
        result = build_candidate_provenance_timeline(
            candidate_id="cand-edge", trace=trace, candidate_payload=payload,
        )
        self.assertEqual(tuple(result["root_chain_key"]), ("edge", "A->B", "link"))
        self.assertEqual(result["chains"][0]["component"], "A->B")


class TestSummarize(unittest.TestCase):
    """Step 2: summary correctness."""

    def _make_timeline(self) -> dict[str, Any]:
        return {
            "kind": "candidate_provenance_timeline",
            "candidate_id": "cand-1",
            "engine": "pyreason",
            "timesteps": 3,
            "chains": [
                {
                    "component": "ACME", "component_type": "node", "label": "risk",
                    "events": [
                        {"time": 0, "fixpoint_op": 1, "old_bound": [0, 1],
                         "new_bound": [1, 1], "trigger": "seed_fact", "groundings": []},
                    ],
                },
                {
                    "component": "PAY", "component_type": "node", "label": "risk",
                    "events": [
                        {"time": 1, "fixpoint_op": 2, "old_bound": [0, 1],
                         "new_bound": [1, 1], "trigger": "risk_prop", "groundings": ["[ACME]"]},
                    ],
                },
            ],
            "root_chain_key": ["node", "PAY", "risk"],
        }

    def test_summary_fields(self) -> None:
        summary = summarize_candidate_provenance_timeline(self._make_timeline())
        self.assertEqual(summary["explain_kind"], "timeline")
        self.assertEqual(summary["timesteps"], 3)
        self.assertEqual(summary["chain_count"], 2)
        self.assertEqual(summary["seed_count"], 1)
        self.assertEqual(summary["derived_count"], 1)
        self.assertEqual(summary["trigger_rules"], ["risk_prop"])
        self.assertEqual(summary["final_bound"], [1, 1])

    def test_summary_with_no_root_match(self) -> None:
        tl = self._make_timeline()
        tl["root_chain_key"] = ["node", "MISSING", "risk"]
        summary = summarize_candidate_provenance_timeline(tl)
        self.assertIsNone(summary["final_bound"])


class TestNarrative(unittest.TestCase):
    """Step 3: narrative correctness."""

    def _make_timeline(self) -> dict[str, Any]:
        return {
            "kind": "candidate_provenance_timeline",
            "candidate_id": "cand-1",
            "engine": "pyreason",
            "timesteps": 2,
            "chains": [
                {
                    "component": "ACME", "component_type": "node", "label": "risk",
                    "events": [
                        {"time": 0, "fixpoint_op": 1, "old_bound": [0, 1],
                         "new_bound": [1, 1], "trigger": "seed_fact", "groundings": []},
                    ],
                },
                {
                    "component": "PAY", "component_type": "node", "label": "risk",
                    "events": [
                        {"time": 1, "fixpoint_op": 2, "old_bound": [0, 1],
                         "new_bound": [1, 1], "trigger": "risk_prop", "groundings": ["[ACME]"]},
                    ],
                },
            ],
            "root_chain_key": ["node", "PAY", "risk"],
        }

    def test_narrative_structure(self) -> None:
        narr = render_candidate_provenance_timeline_narrative(self._make_timeline())
        self.assertIn("headline", narr)
        self.assertIn("propagation_lines", narr)
        self.assertIn("seed_summary", narr)
        self.assertIn("convergence", narr)

    def test_narrative_is_chain_local(self) -> None:
        """V1 narrative must NOT infer cross-chain causality from groundings."""
        narr = render_candidate_provenance_timeline_narrative(self._make_timeline())
        for line in narr["propagation_lines"]:
            # Must not contain "← rule(SOURCE)" cross-chain pattern
            self.assertNotIn("←", line)
            self.assertNotIn("from ACME", line)

    def test_narrative_lines_ordered_by_time(self) -> None:
        narr = render_candidate_provenance_timeline_narrative(self._make_timeline())
        times = []
        for line in narr["propagation_lines"]:
            t_str = line.split(":")[0].split("=")[1]
            times.append(int(t_str))
        self.assertEqual(times, sorted(times))

    def test_seed_summary(self) -> None:
        narr = render_candidate_provenance_timeline_narrative(self._make_timeline())
        self.assertIn("1 seed chain", narr["seed_summary"])


class TestDataclasses(unittest.TestCase):
    """Dataclass invariants."""

    def test_timeline_event_frozen(self) -> None:
        ev = TimelineEvent(0, 1, (0.0, 1.0), (1.0, 1.0), "seed", ())
        with self.assertRaises(AttributeError):
            ev.time = 5  # type: ignore[misc]

    def test_timeline_chain_frozen(self) -> None:
        chain = TimelineChain("A", "node", "risk", ())
        with self.assertRaises(AttributeError):
            chain.component = "B"  # type: ignore[misc]

    def test_candidate_provenance_timeline_frozen(self) -> None:
        tl = CandidateProvenanceTimeline("cand", "pyreason", 0, (), ("node", "A", "x"))
        with self.assertRaises(AttributeError):
            tl.engine = "souffle"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
