from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kernel.core.annotation import (  # noqa: E402
    CertaintySummary,
    ConditionImpact,
    RankedCondition,
    derive_certainty_summary,
    rank_certainty_conditions,
)


def _make_tree(*condition_nodes: dict) -> dict:
    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": "cand_v2:test",
        "support_digest": "sha256:test",
        "support_kind": "native_binding_v1",
        "root": {
            "node_id": "cand:cand_v2:test",
            "node_kind": "candidate_result",
            "children": [
                {
                    "node_id": "support:cand_v2:test",
                    "node_kind": "support_section",
                    "children": list(condition_nodes),
                }
            ],
        },
    }


def _pwg(pred_atom_key: str, *, confidence: float | None = None) -> dict:
    node = {
        "node_id": f"atom:{pred_atom_key}",
        "node_kind": "predicate_witness_group",
        "pred_atom_key": pred_atom_key,
        "pred_id": pred_atom_key.split(":", 1)[1] if ":" in pred_atom_key else pred_atom_key,
        "assertion_count": 1,
        "children": [],
    }
    if confidence is not None:
        node["condition_confidence"] = confidence
    return node


def _nfc(step_key: str, *, confidence: float | None = None) -> dict:
    node = {
        "node_id": f"step:{step_key}",
        "node_kind": "non_fact_check",
        "step_key": step_key,
        "check_kind": "constraint",
        "status": "satisfied",
        "details": {},
        "children": [],
    }
    if confidence is not None:
        node["condition_confidence"] = confidence
    return node


class CertaintyAnnotationKernelTests(unittest.TestCase):
    def test_certainty_lane_produces_summary(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        result = derive_certainty_summary(tree, {"b0.a0": 0.8}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result, CertaintySummary)
        self.assertEqual(result.confidence_kind, "certainty")

    def test_probability_lane_returns_none(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        self.assertIsNone(derive_certainty_summary(tree, {"b0.a0": 0.8}, "probability"))

    def test_none_lane_returns_none(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        self.assertIsNone(derive_certainty_summary(tree, {"b0.a0": 0.8}, "none"))

    def test_weighted_predicate_witness_group_uses_condition_key_prefix(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"), _pwg("b0.a1:user:tag"))
        result = derive_certainty_summary(tree, {"b0.a0": 0.8, "b0.a1": 0.5}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 2)
        self.assertEqual(result.weighted_condition_count, 2)
        self.assertEqual(
            result.conditions[0],
            ConditionImpact(
                atom_key="b0.a0",
                node_kind="predicate_witness_group",
                weight=0.8,
                impact=0.8,
            ),
        )
        self.assertEqual(
            result.conditions[1],
            ConditionImpact(
                atom_key="b0.a1",
                node_kind="predicate_witness_group",
                weight=0.5,
                impact=0.5,
            ),
        )

    def test_weighted_non_fact_check_uses_condition_key_prefix(self) -> None:
        tree = _make_tree(_nfc("b0.a2:eq"))
        result = derive_certainty_summary(tree, {"b0.a2": 0.6}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 1)
        self.assertEqual(result.conditions[0].node_kind, "non_fact_check")
        self.assertEqual(result.conditions[0].weight, 0.6)
        self.assertEqual(result.conditions[0].impact, 0.6)

    def test_weighted_condition_with_explicit_confidence_multiplies(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name", confidence=0.5))
        result = derive_certainty_summary(tree, {"b0.a0": 0.8}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.conditions[0].impact, 0.4)
        self.assertEqual(result.aggregate_certainty, 0.4)

    def test_unweighted_condition_impact_is_none(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        result = derive_certainty_summary(tree, {}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 1)
        self.assertEqual(result.weighted_condition_count, 0)
        self.assertIsNone(result.conditions[0].weight)
        self.assertIsNone(result.conditions[0].impact)

    def test_mixed_weighted_and_unweighted_conditions(self) -> None:
        tree = _make_tree(
            _pwg("b0.a0:user:name"),
            _pwg("b0.a1:user:tag"),
            _nfc("b0.a2:eq"),
        )
        result = derive_certainty_summary(tree, {"b0.a0": 0.9}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 3)
        self.assertEqual(result.weighted_condition_count, 1)
        self.assertEqual(result.conditions[0].impact, 0.9)
        self.assertIsNone(result.conditions[1].impact)
        self.assertIsNone(result.conditions[2].impact)

    def test_bottleneck_is_minimum_weighted_impact(self) -> None:
        tree = _make_tree(
            _pwg("b0.a0:user:name"),
            _pwg("b0.a1:user:tag"),
            _pwg("b0.a2:user:status"),
        )
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.9, "b0.a1": 0.3, "b0.a2": 0.7},
            "certainty",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.aggregate_certainty, 0.3)

    def test_all_unweighted_aggregate_is_none(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"), _pwg("b0.a1:user:tag"))
        result = derive_certainty_summary(tree, {}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsNone(result.aggregate_certainty)

    def test_empty_tree_root_returns_empty_summary(self) -> None:
        tree = {
            "kind": "candidate_evidence_tree",
            "root": {
                "node_id": "result:empty",
                "node_kind": "candidate_result",
                "children": [],
            },
        }
        result = derive_certainty_summary(tree, {"b0.a0": 1.0}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 0)
        self.assertIsNone(result.aggregate_certainty)

    def test_missing_root_returns_empty_summary(self) -> None:
        result = derive_certainty_summary({"kind": "candidate_evidence_tree"}, {}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 0)

    def test_deeply_nested_conditions_are_collected(self) -> None:
        tree = {
            "kind": "candidate_evidence_tree",
            "root": {
                "node_id": "result:deep",
                "node_kind": "candidate_result",
                "children": [
                    {
                        "node_id": "support:top",
                        "node_kind": "support_section",
                        "children": [
                            {
                                "node_id": "rref:section",
                                "node_kind": "rule_ref_section",
                                "children": [
                                    {
                                        "node_id": "ref:r1",
                                        "node_kind": "referenced_support",
                                        "children": [
                                            {
                                                "node_id": "support:nested",
                                                "node_kind": "support_section",
                                                "children": [_pwg("b0.a0:user:name")],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }
        result = derive_certainty_summary(tree, {"b0.a0": 0.4}, "certainty")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.condition_count, 1)
        self.assertEqual(result.conditions[0].impact, 0.4)

    def test_summary_dataclass_is_frozen(self) -> None:
        summary = CertaintySummary(
            confidence_kind="certainty",
            condition_count=0,
            weighted_condition_count=0,
            conditions=(),
            aggregate_certainty=None,
            aggregation="bottleneck",
        )
        with self.assertRaises(FrozenInstanceError):
            summary.condition_count = 5  # type: ignore[misc]

    def test_additive_single_condition(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name", confidence=0.8))
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.9},
            "certainty",
            aggregation="additive",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.aggregation, "additive")
        self.assertEqual(result.condition_count, 1)
        self.assertAlmostEqual(result.conditions[0].impact, 0.8)
        self.assertAlmostEqual(result.aggregate_certainty, 0.8)

    def test_additive_two_conditions_normalized(self) -> None:
        tree = _make_tree(
            _pwg("b0.a0:user:name", confidence=0.9),
            _pwg("b0.a1:user:tag", confidence=0.6),
        )
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.9, "b0.a1": 0.4},
            "certainty",
            aggregation="additive",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.aggregation, "additive")
        self.assertAlmostEqual(result.aggregate_certainty, 0.807692, places=4)
        impacts = {condition.atom_key: condition.impact for condition in result.conditions}
        self.assertAlmostEqual(impacts["b0.a0"], 0.623077, places=4)
        self.assertAlmostEqual(impacts["b0.a1"], 0.184615, places=4)

    def test_additive_no_confidence_defaults_to_one(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.5},
            "certainty",
            aggregation="additive",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.aggregate_certainty, 1.0)

    def test_additive_all_confidence_one_gives_aggregate_one(self) -> None:
        tree = _make_tree(
            _pwg("b0.a0:user:name", confidence=1.0),
            _pwg("b0.a1:user:tag", confidence=1.0),
        )
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.7, "b0.a1": 0.3},
            "certainty",
            aggregation="additive",
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.aggregate_certainty, 1.0)

    def test_additive_ranking_no_bottleneck(self) -> None:
        tree = _make_tree(
            _pwg("b0.a0:user:name", confidence=0.9),
            _pwg("b0.a1:user:tag", confidence=0.5),
        )
        result = derive_certainty_summary(
            tree,
            {"b0.a0": 0.6, "b0.a1": 0.4},
            "certainty",
            aggregation="additive",
        )
        self.assertIsNotNone(result)
        assert result is not None
        ranked = rank_certainty_conditions(
            result.conditions,
            result.aggregate_certainty,
            aggregation="additive",
        )
        self.assertTrue(all(not item.is_bottleneck for item in ranked))
        impacts = [item.impact for item in ranked if item.impact is not None]
        self.assertEqual(impacts, sorted(impacts))

    def test_invalid_aggregation_raises(self) -> None:
        tree = _make_tree(_pwg("b0.a0:user:name"))
        with self.assertRaises(ValueError):
            derive_certainty_summary(
                tree,
                {"b0.a0": 0.5},
                "certainty",
                aggregation="unknown",
            )


class RankCertaintyConditionsTests(unittest.TestCase):
    def test_weighted_conditions_sorted_by_impact_ascending(self) -> None:
        conditions = (
            ConditionImpact(
                atom_key="b0.a2",
                node_kind="predicate_witness_group",
                weight=0.7,
                impact=0.56,
            ),
            ConditionImpact(
                atom_key="b0.a0",
                node_kind="predicate_witness_group",
                weight=0.4,
                impact=0.24,
            ),
            ConditionImpact(
                atom_key="b0.a1",
                node_kind="predicate_witness_group",
                weight=0.6,
                impact=0.54,
            ),
        )
        ranked = rank_certainty_conditions(conditions, aggregate_certainty=0.24)
        self.assertEqual([item.atom_key for item in ranked], ["b0.a0", "b0.a1", "b0.a2"])
        self.assertEqual([item.impact for item in ranked], [0.24, 0.54, 0.56])

    def test_unweighted_conditions_sorted_after_weighted_by_atom_key(self) -> None:
        conditions = (
            ConditionImpact(atom_key="b0.c1", node_kind="non_fact_check", weight=None, impact=None),
            ConditionImpact(
                atom_key="b0.a0",
                node_kind="predicate_witness_group",
                weight=0.5,
                impact=0.4,
            ),
            ConditionImpact(atom_key="b0.c0", node_kind="non_fact_check", weight=None, impact=None),
        )
        ranked = rank_certainty_conditions(conditions, aggregate_certainty=0.4)
        self.assertEqual([item.atom_key for item in ranked], ["b0.a0", "b0.c0", "b0.c1"])
        self.assertFalse(ranked[1].is_bottleneck)
        self.assertFalse(ranked[2].is_bottleneck)

    def test_bottleneck_marked_for_min_impact(self) -> None:
        conditions = (
            ConditionImpact(
                atom_key="b0.a0",
                node_kind="predicate_witness_group",
                weight=0.4,
                impact=0.24,
            ),
            ConditionImpact(
                atom_key="b0.a1",
                node_kind="predicate_witness_group",
                weight=0.6,
                impact=0.54,
            ),
        )
        ranked = rank_certainty_conditions(conditions, aggregate_certainty=0.24)
        self.assertTrue(ranked[0].is_bottleneck)
        self.assertFalse(ranked[1].is_bottleneck)

    def test_tie_all_bottlenecks_marked(self) -> None:
        conditions = (
            ConditionImpact(
                atom_key="b0.a0",
                node_kind="predicate_witness_group",
                weight=0.3,
                impact=0.3,
            ),
            ConditionImpact(
                atom_key="b0.a1",
                node_kind="predicate_witness_group",
                weight=0.3,
                impact=0.3,
            ),
            ConditionImpact(
                atom_key="b0.a2",
                node_kind="predicate_witness_group",
                weight=0.9,
                impact=0.9,
            ),
        )
        ranked = rank_certainty_conditions(conditions, aggregate_certainty=0.3)
        self.assertTrue(ranked[0].is_bottleneck)
        self.assertTrue(ranked[1].is_bottleneck)
        self.assertFalse(ranked[2].is_bottleneck)
        self.assertEqual(ranked[0].atom_key, "b0.a0")
        self.assertEqual(ranked[1].atom_key, "b0.a1")

    def test_unweighted_only_no_bottleneck(self) -> None:
        conditions = (
            ConditionImpact(atom_key="b0.c1", node_kind="non_fact_check", weight=None, impact=None),
            ConditionImpact(atom_key="b0.c0", node_kind="non_fact_check", weight=None, impact=None),
        )
        ranked = rank_certainty_conditions(conditions, aggregate_certainty=None)
        self.assertEqual(len(ranked), 2)
        self.assertEqual([item.atom_key for item in ranked], ["b0.c0", "b0.c1"])
        self.assertFalse(any(item.is_bottleneck for item in ranked))

    def test_empty_conditions(self) -> None:
        ranked = rank_certainty_conditions((), aggregate_certainty=None)
        self.assertEqual(ranked, [])

    def test_ranked_condition_is_frozen(self) -> None:
        ranked_condition = RankedCondition(
            atom_key="b0.a0",
            node_kind="predicate_witness_group",
            weight=0.5,
            impact=0.4,
            is_bottleneck=True,
        )
        with self.assertRaises(FrozenInstanceError):
            ranked_condition.is_bottleneck = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
