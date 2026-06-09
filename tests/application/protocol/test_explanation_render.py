from __future__ import annotations

import inspect
import unittest

from factgraph.application.protocol import BOOLEAN_CERTAINTY, ErrorDTO, EvaluateRow, Explanation, walk_evidence
from factgraph.audit.evidence_graph import (
    EDGE_DERIVED_BY,
    EDGE_HAS_ATOM,
    EDGE_SUPPORTED_BY,
    EDGE_USES,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NODE_ATOM,
    NODE_CONCLUSION,
    NODE_RULE,
    NODE_RULE_EXPR,
    NODE_SEED,
)
from factgraph.core.protocol.digests import sha256_token


def _row() -> EvaluateRow:
    return EvaluateRow(
        row_id="row-1",
        bindings={"person": "alice", "age": 25},
        kind="fact_triple",
        digest=sha256_token(b"row-digest"),
        closed_head_digest=sha256_token(b"closed-head"),
        certainty=BOOLEAN_CERTAINTY,
    )


def _layered_graph() -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-1",
        engine="native",
        root_node_id="row-1",
        nodes=(
            EvidenceNode(
                node_id="row-1",
                node_kind=NODE_CONCLUSION,
                component="adult_rule",
                label="adult_rule",
                value_summary="adult_rule(person=alice)",
            ),
            EvidenceNode(
                node_id="rule_expr-1",
                node_kind=NODE_RULE_EXPR,
                component="adult_rule",
                label="single",
                value_summary="single",
                engine_meta={"ast_form": "single"},
            ),
            EvidenceNode(
                node_id="rule-1",
                node_kind=NODE_RULE,
                component="adult_rule",
                label="adult_rule",
                value_summary="adult_rule",
                engine_meta={"rule_id": "adult_rule"},
            ),
            EvidenceNode(
                node_id="atom-1",
                node_kind=NODE_ATOM,
                component="adult_rule",
                label="age_check",
                value_summary="age > 18",
                engine_meta={"atom_index": 0, "atom_status": "support"},
            ),
            EvidenceNode(
                node_id="seed-1",
                node_kind=NODE_SEED,
                component="person:age",
                label="person:age",
                value_summary="person:age(alice, 25)",
            ),
        ),
        edges=(
            EvidenceEdge("e1", from_node_id="rule_expr-1", to_node_id="row-1", edge_kind=EDGE_DERIVED_BY),
            EvidenceEdge("e2", from_node_id="rule-1", to_node_id="rule_expr-1", edge_kind=EDGE_USES),
            EvidenceEdge("e3", from_node_id="atom-1", to_node_id="rule-1", edge_kind=EDGE_HAS_ATOM),
            EvidenceEdge("e4", from_node_id="seed-1", to_node_id="atom-1", edge_kind=EDGE_SUPPORTED_BY),
        ),
        support_kind="native_binding_v1",
    )


class ExplanationRenderTests(unittest.TestCase):
    def test_walk_evidence_renders_layered_graph_in_shipped_direction(self) -> None:
        lines = walk_evidence(_layered_graph(), row=_row())

        self.assertEqual(
            lines,
            (
                "Conclusion: adult_rule(person=alice) [row-1]",
                "  is derived by RuleExpr(single)",
                '    which uses Rule "adult_rule"',
                "      which has atom Atom[0]: age > 18 — support",
                "        is supported by ledger fact: person:age(alice, 25)",
            ),
        )

    def test_explanation_repr_is_computed_property_and_cached(self) -> None:
        self.assertNotIn("repr", inspect.signature(Explanation).parameters)
        explanation = Explanation(
            status="passed",
            evidence=_layered_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        first = explanation.repr
        second = explanation.repr

        self.assertIs(first, second)
        assert first is not None
        self.assertEqual(first[0], "Conclusion: adult_rule(person=alice) [row-1]")

    def test_failed_explanation_repr_uses_summary_without_evidence(self) -> None:
        explanation = Explanation(
            status="failed",
            evidence=None,
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            failure_class="closed_head_false",
            suggested_next_steps=("Retry with a row returned by evaluate().",),
        )

        self.assertEqual(
            explanation.repr,
            (
                "NOT concluded",
                "failure_class: closed_head_false",
                "result_id: evalr_v1:" + "1" * 64,
                "row_id: row-1",
                "next_step: Retry with a row returned by evaluate().",
            ),
        )

    def test_unsupported_and_invalid_request_repr_is_none(self) -> None:
        unsupported = Explanation(
            status="unsupported",
            evidence=None,
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            errors=(ErrorDTO(code="UNSUPPORTED", message="unsupported"),),
        )
        invalid = Explanation(
            status="invalid_request",
            evidence=None,
            row=None,
            result_id=None,
            errors=(ErrorDTO(code="INVALID_REQUEST", message="bad request"),),
        )

        self.assertIsNone(unsupported.repr)
        self.assertIsNone(invalid.repr)


if __name__ == "__main__":
    unittest.main()
