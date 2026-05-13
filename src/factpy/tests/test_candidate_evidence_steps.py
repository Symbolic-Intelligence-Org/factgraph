"""
Tests for Phase 2 of Evidence Explain Depth blueprint:
- build_candidate_evidence_steps(): native tree shape — DFS post-order, step_kind mapping,
  node_ref, detail.depth / detail.parent_node_ref, transparent-kind pass-through
- build_candidate_evidence_steps(): problog tree shape — proof_leaf / proof_goal ordering
- build_candidate_provenance_steps(): bound_seed / bound_update ordering, convergence step
- Error handling for both builders
"""
from __future__ import annotations

import unittest
from typing import Any

from factpy.core.store._candidate_evidence_tree_steps import (
    CandidateEvidenceStepsError,
    build_candidate_evidence_steps,
)
from factpy.core.store._candidate_provenance_timeline import (
    build_candidate_provenance_steps,
)


# ---------------------------------------------------------------------------
# Tree Helpers
# ---------------------------------------------------------------------------


def _make_assertion_fact(
    asrt_id: str,
    pred_id: str = "score",
    e_ref: str = "entity:alice",
    claim_args: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "node_id": f"asrt:{asrt_id}",
        "node_kind": "assertion_fact",
        "title": f"Assertion {asrt_id}",
        "asrt_id": asrt_id,
        "pred_id": pred_id,
        "e_ref": e_ref,
        "claim_args": claim_args if claim_args is not None else [{"idx": 0, "tag": "val", "val": "720"}],
        "children": [],
    }


def _make_native_tree(
    assertion_nodes: list[dict[str, Any]],
    *,
    rule_ref_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Minimal native candidate_evidence_tree with support_section + predicate_witness_group."""
    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": "c1",
        "support_kind": "native_binding_v1",
        "root": {
            "node_id": "cand:c1",
            "node_kind": "candidate_result",
            "title": "Candidate c1",
            "root_result_kind": "match",
            "binding": {},
            "rule_refs": [],
            "rule_ref_edges": [],
            "children": [
                {
                    "node_id": "support:s1",
                    "node_kind": "support_section",
                    "title": "Support",
                    "rule_ref_ids": list(rule_ref_ids or []),
                    "children": [
                        {
                            "node_id": "pwg:p1",
                            "node_kind": "predicate_witness_group",
                            "title": "pred_group",
                            "pred_id": "score",
                            "children": assertion_nodes,
                        }
                    ],
                }
            ],
        },
    }


def _make_proof_leaf(leaf_id: str, goal: str = "a(alice)") -> dict[str, Any]:
    return {
        "node_id": f"pl:{leaf_id}",
        "node_kind": "proof_leaf",
        "title": f"Proof leaf {leaf_id}",
        "goal": goal,
        "goal_args": ["alice"],
        "pred_id": "a",
        "children": [],
    }


def _make_problog_tree(proof_leaves: list[dict[str, Any]]) -> dict[str, Any]:
    """Minimal problog candidate_evidence_tree: root → support_section → proof_goal → proof_leaves."""
    proof_goal: dict[str, Any] = {
        "node_id": "pg:g1",
        "node_kind": "proof_goal",
        "title": "Proof goal c",
        "goal": "c(alice)",
        "goal_args": ["alice"],
        "pred_id": "c",
        "children": proof_leaves,
    }
    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": "c1",
        "support_kind": "problog_provenance_v1",
        "root": {
            "node_id": "cand:c1",
            "node_kind": "candidate_result",
            "title": "Candidate c1",
            "root_result_kind": "match",
            "binding": {},
            "rule_refs": [],
            "rule_ref_edges": [],
            "engine_meta": {"probability": 0.35},
            "children": [
                {
                    "node_id": "support:s1",
                    "node_kind": "support_section",
                    "title": "Support",
                    "children": [proof_goal],
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Timeline Helpers
# ---------------------------------------------------------------------------


def _make_event(
    time: int,
    trigger: str,
    old_bound: list[float],
    new_bound: list[float],
    fixpoint_op: int = 0,
    groundings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "time": time,
        "fixpoint_op": fixpoint_op,
        "old_bound": old_bound,
        "new_bound": new_bound,
        "trigger": trigger,
        "groundings": groundings or [],
    }


def _make_chain(
    component: str,
    label: str,
    events: list[dict[str, Any]],
    component_type: str = "node",
) -> dict[str, Any]:
    return {
        "component": component,
        "component_type": component_type,
        "label": label,
        "events": events,
    }


def _make_timeline(chains: list[dict[str, Any]], timesteps: int = 2) -> dict[str, Any]:
    return {
        "kind": "candidate_provenance_timeline",
        "candidate_id": "c1",
        "engine": "pyreason",
        "timesteps": timesteps,
        "chains": chains,
        "root_chain_key": ["node", "alice", "score"],
    }


# ---------------------------------------------------------------------------
# §1 Native tree — step ordering (DFS post-order)
# ---------------------------------------------------------------------------


class NativeTreeStepsOrderingTests(unittest.TestCase):
    def _single_assertion_tree(self) -> dict[str, Any]:
        return _make_native_tree([_make_assertion_fact("a1")])

    def test_fact_check_before_rule_apply_before_conclusion(self) -> None:
        """Core AC: DFS post-order ensures fact_check → rule_apply → conclusion."""
        tree = self._single_assertion_tree()
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        assert "fact_check" in kinds
        assert "rule_apply" in kinds
        assert "conclusion" in kinds
        fc_idx = kinds.index("fact_check")
        ra_idx = kinds.index("rule_apply")
        co_idx = kinds.index("conclusion")
        assert fc_idx < ra_idx < co_idx, f"Expected fact_check < rule_apply < conclusion, got {kinds}"

    def test_step_nums_are_sequential_from_one(self) -> None:
        tree = self._single_assertion_tree()
        steps = build_candidate_evidence_steps(tree)
        assert [s["step_num"] for s in steps] == list(range(1, len(steps) + 1))

    def test_two_assertion_facts_both_become_fact_check(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])
        steps = build_candidate_evidence_steps(tree)
        fact_check_steps = [s for s in steps if s["step_kind"] == "fact_check"]
        assert len(fact_check_steps) == 2

    def test_two_assertion_facts_ordered_before_rule_apply(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        last_fact_check = max(i for i, k in enumerate(kinds) if k == "fact_check")
        first_rule_apply = kinds.index("rule_apply")
        assert last_fact_check < first_rule_apply

    def test_total_step_count_single_assertion(self) -> None:
        """1 assertion_fact + 1 support_section + 1 candidate_result = 3 steps."""
        tree = self._single_assertion_tree()
        steps = build_candidate_evidence_steps(tree)
        assert len(steps) == 3

    def test_total_step_count_two_assertions(self) -> None:
        """2 assertion_facts + 1 support_section + 1 candidate_result = 4 steps."""
        tree = _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])
        steps = build_candidate_evidence_steps(tree)
        assert len(steps) == 4


# ---------------------------------------------------------------------------
# §2 Native tree — node_ref, depth, parent_node_ref
# ---------------------------------------------------------------------------


class NativeTreeStepsDetailTests(unittest.TestCase):
    def _two_assertion_tree(self) -> dict[str, Any]:
        return _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])

    def test_fact_check_node_ref_is_asrt_id(self) -> None:
        """For assertion_fact, node_ref must be the asrt_id, not node_id."""
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        assert fact_step["node_ref"] == "a1"

    def test_rule_apply_node_ref_is_support_section_node_id(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["node_ref"] == "support:s1"

    def test_conclusion_node_ref_is_candidate_result_node_id(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        conclusion = next(s for s in steps if s["step_kind"] == "conclusion")
        assert conclusion["node_ref"] == "cand:c1"

    def test_depth_increases_for_nested_nodes(self) -> None:
        """candidate_result is depth 0; support_section is depth 1; assertion_fact is depth 2."""
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        by_kind = {s["step_kind"]: s for s in steps}
        assert by_kind["conclusion"]["detail"]["depth"] == 0
        assert by_kind["rule_apply"]["detail"]["depth"] == 1
        assert by_kind["fact_check"]["detail"]["depth"] == 2

    def test_parent_node_ref_for_fact_check_is_support_section(self) -> None:
        """Transparent predicate_witness_group is skipped; parent_node_ref points to support_section."""
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        # Transparent pwg is invisible; parent is the support_section
        assert fact_step["detail"]["parent_node_ref"] == "support:s1"

    def test_parent_node_ref_for_rule_apply_is_candidate_result(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["detail"]["parent_node_ref"] == "cand:c1"

    def test_parent_node_ref_for_conclusion_is_none(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        conclusion = next(s for s in steps if s["step_kind"] == "conclusion")
        assert conclusion["detail"]["parent_node_ref"] is None

    def test_transparent_predicate_witness_group_generates_no_step(self) -> None:
        """predicate_witness_group is transparent — no step with step_kind that maps it."""
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        node_refs = [s["node_ref"] for s in steps]
        assert "pwg:p1" not in node_refs

    def test_fact_check_detail_contains_pred_id_and_e_ref(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1", pred_id="score", e_ref="entity:alice")])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        assert fact_step["detail"]["pred_id"] == "score"
        assert fact_step["detail"]["e_ref"] == "entity:alice"

    def test_rule_apply_detail_contains_witness_count(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["detail"]["witness_count"] == 2

    def test_rule_apply_detail_contains_single_rule_ref_id(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")], rule_ref_ids=["q.child_rule_a@v1"])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["detail"]["rule_ref_ids"] == ["q.child_rule_a@v1"]

    def test_rule_apply_detail_contains_multiple_rule_ref_ids(self) -> None:
        tree = _make_native_tree(
            [_make_assertion_fact("a1")],
            rule_ref_ids=["q.child_rule_a@v1", "q.child_rule_b@v1"],
        )
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["detail"]["rule_ref_ids"] == ["q.child_rule_a@v1", "q.child_rule_b@v1"]

    def test_rule_apply_detail_contains_empty_rule_ref_ids_when_absent(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["detail"]["rule_ref_ids"] == []

    def test_fact_meta_forwarded_in_detail_when_present(self) -> None:
        node = _make_assertion_fact("a1")
        node["fact_meta"] = {"source": "Q1 Report", "approved_by": "agent-1"}
        tree = _make_native_tree([node])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        assert "fact_meta" in fact_step["detail"]
        assert fact_step["detail"]["fact_meta"]["source"] == "Q1 Report"

    def test_fact_meta_absent_in_detail_when_not_present(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        assert "fact_meta" not in fact_step["detail"]


# ---------------------------------------------------------------------------
# §3 Native tree — description format
# ---------------------------------------------------------------------------


class NativeTreeStepsDescriptionTests(unittest.TestCase):
    def test_fact_check_description_contains_pred_entity_val_and_checkmark(self) -> None:
        tree = _make_native_tree([
            _make_assertion_fact("a1", pred_id="score", e_ref="entity:alice",
                                 claim_args=[{"idx": 0, "tag": "val", "val": "720"}])
        ])
        steps = build_candidate_evidence_steps(tree)
        fact_step = next(s for s in steps if s["step_kind"] == "fact_check")
        desc = fact_step["description"]
        assert "score" in desc
        assert "entity:alice" in desc
        assert "720" in desc
        assert "\u2713" in desc  # checkmark

    def test_rule_apply_description_contains_condition_count(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1"), _make_assertion_fact("a2")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert "2" in rule_step["description"]
        assert "condition" in rule_step["description"]

    def test_rule_apply_description_uses_single_rule_label_when_present(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")], rule_ref_ids=["q.child_rule_a@v1"])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["description"] == "Rule q.child_rule_a@v1: 1 condition(s) met"

    def test_rule_apply_description_uses_multiple_rule_labels_when_present(self) -> None:
        tree = _make_native_tree(
            [_make_assertion_fact("a1"), _make_assertion_fact("a2")],
            rule_ref_ids=["q.child_rule_a@v1", "q.child_rule_b@v1"],
        )
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["description"] == "Rules [q.child_rule_a@v1, q.child_rule_b@v1]: 2 condition(s) met"

    def test_rule_apply_description_falls_back_when_rule_labels_absent(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        rule_step = next(s for s in steps if s["step_kind"] == "rule_apply")
        assert rule_step["description"] == "Support group satisfied: 1 condition(s) met"

    def test_conclusion_description_contains_candidate_id_and_result_kind(self) -> None:
        tree = _make_native_tree([_make_assertion_fact("a1")])
        steps = build_candidate_evidence_steps(tree)
        conclusion = next(s for s in steps if s["step_kind"] == "conclusion")
        desc = conclusion["description"]
        assert "c1" in desc       # candidate_id extracted from "cand:c1"
        assert "match" in desc    # root_result_kind


# ---------------------------------------------------------------------------
# §4 ProbLog-shaped tree — proof_leaf / proof_goal ordering
# ---------------------------------------------------------------------------


class ProblogShapedTreeStepsTests(unittest.TestCase):
    def test_proof_leaf_check_step_kind_from_proof_leaf_node(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        assert "proof_leaf_check" in kinds

    def test_proof_goal_derive_step_kind_from_proof_goal_node(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        assert "proof_goal_derive" in kinds

    def test_proof_leaf_check_before_proof_goal_derive_before_conclusion(self) -> None:
        """Core AC: proof_leaf_check → proof_goal_derive → conclusion (post-order)."""
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        pl_idx = kinds.index("proof_leaf_check")
        pg_idx = kinds.index("proof_goal_derive")
        co_idx = kinds.index("conclusion")
        assert pl_idx < pg_idx < co_idx, f"Expected leaf < goal < conclusion, got {kinds}"

    def test_two_proof_leaves_both_before_proof_goal(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1"), _make_proof_leaf("l2")])
        steps = build_candidate_evidence_steps(tree)
        kinds = [s["step_kind"] for s in steps]
        leaf_indices = [i for i, k in enumerate(kinds) if k == "proof_leaf_check"]
        goal_idx = kinds.index("proof_goal_derive")
        assert len(leaf_indices) == 2
        assert all(i < goal_idx for i in leaf_indices)

    def test_proof_leaf_check_description_contains_goal(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1", goal="a(alice)")])
        steps = build_candidate_evidence_steps(tree)
        leaf_step = next(s for s in steps if s["step_kind"] == "proof_leaf_check")
        assert "a(alice)" in leaf_step["description"]
        assert "base fact" in leaf_step["description"]

    def test_proof_goal_derive_description_contains_goal(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        goal_step = next(s for s in steps if s["step_kind"] == "proof_goal_derive")
        assert "c(alice)" in goal_step["description"]
        assert "derived" in goal_step["description"]

    def test_proof_goal_detail_contains_goal_and_goal_args(self) -> None:
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        goal_step = next(s for s in steps if s["step_kind"] == "proof_goal_derive")
        assert goal_step["detail"]["goal"] == "c(alice)"
        assert goal_step["detail"]["goal_args"] == ["alice"]

    def test_proof_leaf_node_ref_is_node_id(self) -> None:
        """proof_leaf has no asrt_id; node_ref falls back to node_id."""
        tree = _make_problog_tree([_make_proof_leaf("l1")])
        steps = build_candidate_evidence_steps(tree)
        leaf_step = next(s for s in steps if s["step_kind"] == "proof_leaf_check")
        assert leaf_step["node_ref"] == "pl:l1"


# ---------------------------------------------------------------------------
# §5 PyReason provenance timeline — bound_seed / bound_update / convergence
# ---------------------------------------------------------------------------


class ProvenanceTimelineStepsTests(unittest.TestCase):
    def _single_chain_timeline(self) -> dict[str, Any]:
        events = [
            _make_event(0, "seed_fact", [0.0, 1.0], [0.7, 1.0]),
            _make_event(1, "rule:high_score", [0.7, 1.0], [0.8, 1.0], groundings=["alice"]),
        ]
        chain = _make_chain("alice", "score", events)
        return _make_timeline([chain], timesteps=2)

    def test_seed_fact_trigger_becomes_bound_seed(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        seed_steps = [s for s in steps if s["step_kind"] == "bound_seed"]
        assert len(seed_steps) == 1

    def test_rule_trigger_becomes_bound_update(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        update_steps = [s for s in steps if s["step_kind"] == "bound_update"]
        assert len(update_steps) == 1

    def test_convergence_step_is_last(self) -> None:
        """Convergence step must be appended after all event steps."""
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        assert steps[-1]["step_kind"] == "convergence"

    def test_convergence_node_ref_is_none(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        convergence = steps[-1]
        assert convergence["node_ref"] is None

    def test_bound_seed_appears_before_bound_update(self) -> None:
        """Core AC: seed events at t=0 before update events at t=1."""
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        kinds = [s["step_kind"] for s in steps]
        seed_idx = kinds.index("bound_seed")
        update_idx = kinds.index("bound_update")
        assert seed_idx < update_idx

    def test_step_nums_sequential_from_one(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        assert [s["step_num"] for s in steps] == list(range(1, len(steps) + 1))

    def test_event_node_ref_format(self) -> None:
        """node_ref = {component_type}/{component}/{label}"""
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        event_steps = [s for s in steps if s["step_kind"] != "convergence"]
        for step in event_steps:
            assert step["node_ref"] == "node/alice/score"

    def test_bound_seed_description_format(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        seed_step = next(s for s in steps if s["step_kind"] == "bound_seed")
        desc = seed_step["description"]
        assert "t=0" in desc
        assert "alice.score" in desc
        assert "initialized" in desc
        assert "0.700" in desc  # formatted new_bound lower

    def test_bound_update_description_format(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        update_step = next(s for s in steps if s["step_kind"] == "bound_update")
        desc = update_step["description"]
        assert "t=1" in desc
        assert "alice.score" in desc
        assert "rule:high_score" in desc
        assert "->" in desc

    def test_convergence_description_contains_timesteps_and_chain_count(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        convergence = steps[-1]
        desc = convergence["description"]
        assert "2" in desc        # timesteps
        assert "1" in desc        # chain count
        assert "alice.score" in desc  # final bound summary

    def test_convergence_detail_has_timesteps_and_chain_count(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        convergence = steps[-1]
        assert convergence["detail"]["timesteps"] == 2
        assert convergence["detail"]["chain_count"] == 1

    def test_multi_chain_events_ordered_by_time(self) -> None:
        """Events from different chains sorted by time, then chain index."""
        events_a = [
            _make_event(0, "seed_fact", [0.0, 1.0], [0.5, 1.0]),
            _make_event(2, "rule:r1", [0.5, 1.0], [0.6, 1.0]),
        ]
        events_b = [
            _make_event(1, "seed_fact", [0.0, 1.0], [0.4, 1.0]),
        ]
        chain_a = _make_chain("alice", "score", events_a)
        chain_b = _make_chain("bob", "score", events_b)
        timeline = _make_timeline([chain_a, chain_b], timesteps=3)
        steps = build_candidate_provenance_steps(timeline)
        # Extract time from detail for non-convergence steps
        times = [s["detail"]["time"] for s in steps if s["step_kind"] != "convergence"]
        assert times == sorted(times), f"Expected sorted times, got {times}"

    def test_multi_chain_total_event_steps(self) -> None:
        """3 events across 2 chains → 3 event steps + 1 convergence = 4 total."""
        events_a = [
            _make_event(0, "seed_fact", [0.0, 1.0], [0.5, 1.0]),
            _make_event(2, "rule:r1", [0.5, 1.0], [0.6, 1.0]),
        ]
        events_b = [
            _make_event(1, "seed_fact", [0.0, 1.0], [0.4, 1.0]),
        ]
        timeline = _make_timeline([_make_chain("alice", "score", events_a),
                                   _make_chain("bob", "score", events_b)], timesteps=3)
        steps = build_candidate_provenance_steps(timeline)
        assert len(steps) == 4  # 3 events + 1 convergence

    def test_empty_chains_returns_empty_list(self) -> None:
        """No events → no steps, no convergence."""
        timeline = _make_timeline([], timesteps=0)
        steps = build_candidate_provenance_steps(timeline)
        assert steps == []

    def test_chain_with_no_events_is_skipped(self) -> None:
        """Chain with empty events list contributes no event steps."""
        chain_empty = _make_chain("alice", "score", [])
        chain_with = _make_chain("bob", "score", [_make_event(0, "seed_fact", [0.0, 1.0], [0.5, 1.0])])
        timeline = _make_timeline([chain_empty, chain_with], timesteps=1)
        steps = build_candidate_provenance_steps(timeline)
        event_steps = [s for s in steps if s["step_kind"] != "convergence"]
        assert len(event_steps) == 1

    def test_event_detail_contains_component_and_bound_info(self) -> None:
        steps = build_candidate_provenance_steps(self._single_chain_timeline())
        seed_step = next(s for s in steps if s["step_kind"] == "bound_seed")
        d = seed_step["detail"]
        assert d["component"] == "alice"
        assert d["label"] == "score"
        assert d["component_type"] == "node"
        assert d["time"] == 0
        assert d["new_bound"] == [0.7, 1.0]


# ---------------------------------------------------------------------------
# §6 Error handling
# ---------------------------------------------------------------------------


class CandidateEvidenceStepsErrorTests(unittest.TestCase):
    def test_non_mapping_raises(self) -> None:
        with self.assertRaises(CandidateEvidenceStepsError):
            build_candidate_evidence_steps("not a dict")  # type: ignore[arg-type]

    def test_wrong_kind_raises(self) -> None:
        with self.assertRaises(CandidateEvidenceStepsError):
            build_candidate_evidence_steps({"kind": "candidate_provenance_timeline", "root": {}})

    def test_missing_kind_raises(self) -> None:
        with self.assertRaises(CandidateEvidenceStepsError):
            build_candidate_evidence_steps({"root": {}})

    def test_missing_root_raises(self) -> None:
        with self.assertRaises(CandidateEvidenceStepsError):
            build_candidate_evidence_steps({"kind": "candidate_evidence_tree"})

    def test_non_mapping_root_raises(self) -> None:
        with self.assertRaises(CandidateEvidenceStepsError):
            build_candidate_evidence_steps({"kind": "candidate_evidence_tree", "root": "bad"})


if __name__ == "__main__":
    unittest.main()
