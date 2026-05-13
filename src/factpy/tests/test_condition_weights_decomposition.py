"""Guard-baseline tests for Track 3 / A4 condition_weights decomposition."""

from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from factpy.agent.tools.rules import RuleSpec as AgentRuleSpec
from factpy.authoring.registry_fs import FileAuthoringRegistry
from factpy.authoring.rule_compile import AuthoringRuleCompileError, compile_authoring_rule_v1
from factpy.core.store._certainty_materializer import materialize_certainty_summary
from factpy.core.store._confidence_kind_resolver import CertaintyConfidenceKindResolver
from factpy.core.store._support import PredWitness, RuleRefEdge, SupportArtifact, compute_support_digest
from factpy.sdk import Pred, Rule, SDKDSLError
from factpy.service.rules_v1 import compile_rule_preview


def _weighted_rule() -> Rule:
    return Rule(
        id="rule.a4.weighted",
        version="v1",
        select=["$u"],
        where=[
            Pred("user:name", "$u", "$name"),
            Pred("user:tag", "$u", "vip"),
        ],
        condition_weights={"b0.a1": 0.25, "b0.a0": 0.75},
    )


def _compiled_weighted_rule() -> dict[str, Any]:
    return compile_authoring_rule_v1(_weighted_rule().to_authoring_payload())


class SDKConditionWeightsGuardTests(unittest.TestCase):
    def test_rule_condition_weights_remains_public_sdk_field(self) -> None:
        self.assertIn("condition_weights", {field.name for field in fields(Rule)})

    def test_rule_condition_weights_emit_sorted_authoring_payload(self) -> None:
        payload = _weighted_rule().to_authoring_payload()

        self.assertEqual(payload["condition_weights"], {"b0.a0": 0.75, "b0.a1": 0.25})

    def test_rule_condition_weights_invalid_values_still_reject(self) -> None:
        with self.assertRaises(SDKDSLError):
            Rule(
                id="rule.a4.invalid",
                version="v1",
                select=["$u"],
                where=[Pred("user:tag", "$u", "vip")],
                condition_weights={"b0.a0": 0},
            )


class AuthoringConditionWeightsGuardTests(unittest.TestCase):
    def test_authoring_compile_preserves_valid_condition_weights(self) -> None:
        compiled = _compiled_weighted_rule()

        self.assertEqual(compiled["condition_weights"], {"b0.a0": 0.75, "b0.a1": 0.25})

    def test_authoring_compile_rejects_unknown_atom_position_key(self) -> None:
        payload = _weighted_rule().to_authoring_payload()
        payload["condition_weights"] = {"b0.a9": 0.5}

        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(payload)

        self.assertEqual(ctx.exception.path, '$.condition_weights["b0.a9"]')


class ServiceAndAgentConditionWeightsGuardTests(unittest.TestCase):
    def test_service_compile_preview_and_registry_preserve_condition_weights(self) -> None:
        compiled = _compiled_weighted_rule()
        preview = compile_rule_preview(
            {
                "api_version": "v1",
                "mode": "souffle",
                "rule": compiled,
            }
        )

        self.assertTrue(preview["ok"])
        self.assertEqual(
            preview["preview"]["compiled_payload"]["condition_weights"],
            {"b0.a0": 0.75, "b0.a1": 0.25},
        )

        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.register_rule_spec(compiled)
            stored = registry.read_rule_spec("rule.a4.weighted", "v1")

        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored["condition_weights"], {"b0.a0": 0.75, "b0.a1": 0.25})

    def test_agent_rule_spec_serializes_condition_weights(self) -> None:
        spec = AgentRuleSpec(
            rule_id="rule.a4.agent",
            version="v1",
            select_vars=["$u"],
            where=[("pred", "user:tag", ["$u", "vip"])],
            condition_weights={"b0.a0": 0.8},
        )

        self.assertEqual(spec.to_rule_dict()["condition_weights"], {"b0.a0": 0.8})


class CertaintyConditionWeightsGuardTests(unittest.TestCase):
    def test_confidence_kind_resolver_routes_weighted_rule_to_certainty(self) -> None:
        child = SupportArtifact(
            kind="native_binding_v1",
            root_result_kind="row",
            binding_items=(),
            pred_witnesses=(PredWitness("b0.a0:user:tag", ("asrt-1",)),),
        )
        child_digest = compute_support_digest(child)
        parent = SupportArtifact(
            kind="native_binding_v1",
            root_result_kind="row",
            binding_items=(),
            pred_witnesses=(),
            rule_refs=("q.child_rule@1.0.0",),
            rule_ref_edges=(
                RuleRefEdge(
                    "b0.a0:q.child_rule",
                    "q.child_rule",
                    "1.0.0",
                    child_support_digest=child_digest,
                ),
            ),
        )
        parent_digest = compute_support_digest(parent)
        artifacts = {
            parent_digest: parent,
            child_digest: child,
        }

        class Reader:
            def read_rule_spec(self, rule_id: str, version: str) -> dict[str, Any] | None:
                return {"condition_weights": {"b0.a0": 0.8}}

        resolver = CertaintyConfidenceKindResolver(Reader())

        self.assertEqual(
            resolver.resolve(parent_digest, parent.kind, artifacts.get),
            "certainty",
        )

    def test_materialize_certainty_summary_preserves_weighted_output(self) -> None:
        class FakeStore:
            def get_candidate_confidence_kind(self, candidate_id: str) -> str:
                return "certainty"

        tree = {
            "kind": "candidate_evidence_tree",
            "root": {
                "node_id": "candidate:a4",
                "node_kind": "candidate_result",
                "children": [
                    {
                        "node_id": "support:a4",
                        "node_kind": "referenced_support",
                        "children": [
                            {
                                "node_id": "condition:a4",
                                "node_kind": "predicate_witness_group",
                                "pred_atom_key": "b0.a0:user:tag",
                                "pred_id": "user:tag",
                                "condition_confidence": 0.5,
                                "children": [],
                            }
                        ],
                    }
                ],
            },
        }

        summary = materialize_certainty_summary(
            FakeStore(),  # type: ignore[arg-type]
            "candidate:a4",
            tree,
            condition_weights={"b0.a0": 0.8},
        )

        self.assertEqual(
            summary,
            {
                "confidence_kind": "certainty",
                "condition_count": 1,
                "weighted_condition_count": 1,
                "conditions": [
                    {
                        "atom_key": "b0.a0",
                        "node_kind": "predicate_witness_group",
                        "weight": 0.8,
                        "impact": 0.4,
                    }
                ],
                "aggregate_certainty": 0.4,
                "aggregation": "bottleneck",
            },
        )


if __name__ == "__main__":
    unittest.main()
