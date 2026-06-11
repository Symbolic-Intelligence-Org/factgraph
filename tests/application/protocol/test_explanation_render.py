from __future__ import annotations

import inspect
import unittest

from factgraph.application.protocol import BOOLEAN_CERTAINTY, ErrorDTO, EvaluateRow, Explanation
from factgraph.application.explain.evidence_tree import (
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    LAYOUT_TREE,
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


def _paths_graph(*, status: str = "holds") -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-1",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={"person": "alice", "age": 25},
        paths=(
            EvidenceTree(
                tree_id="row-1",
                status=status,
                rules=(
                    EvidenceRule(
                        occurrence_alias="adult_rule",
                        rule_id="adult_rule",
                        role="head",
                        status=status,
                        ports={"person": "alice", "age": 25},
                        atoms=(),
                    ),
                ),
            ),
        ),
        certainty=BOOLEAN_CERTAINTY,
    )


class ExplanationRenderTests(unittest.TestCase):
    def test_explanation_repr_is_computed_property_and_cached(self) -> None:
        self.assertNotIn("repr", inspect.signature(Explanation).parameters)
        explanation = Explanation(
            status="passed",
            evidence=_paths_graph(),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
        )

        first = explanation.repr
        second = explanation.repr

        self.assertIs(first, second)
        assert first is not None
        self.assertEqual(first[0], "Conclusion: row-1 [row-1]")

    def test_failed_explanation_repr_uses_paths_evidence(self) -> None:
        explanation = Explanation(
            status="failed",
            evidence=_paths_graph(status="fails"),
            row=_row(),
            result_id="evalr_v1:" + "1" * 64,
            failure_class="closed_head_false",
            suggested_next_steps=("Retry with a row returned by evaluate().",),
        )

        self.assertEqual(
            explanation.repr,
            (
                "NOT concluded: row-1 [row-1] (closed_head_false)",
                '  Rule "adult_rule": fails',
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
