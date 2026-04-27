"""
Tests for Phase 1 of Evidence Explain Depth blueprint:
- _extract_fact_meta(): runtime path (flat_meta) and audit path (kind-grouped meta)
- _build_assertion_leaf(): fact_meta populated in assertion_fact nodes
- render_candidate_evidence_tree_narrative(..., tree=tree): source_lines when fact_meta present
- render_candidate_evidence_tree_nl_explain(): source_lines paragraph
- static_ui assertion_fact HTML: source tooltip
"""
from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from service.static_ui import render_candidate_evidence_html
from kernel.core.store._candidate_evidence_tree import (
    _build_assertion_leaf,
    _extract_fact_meta,
)
from kernel.core.store._candidate_evidence_tree_narrative import (
    render_candidate_evidence_tree_narrative,
)
from kernel.core.store._candidate_evidence_tree_nl import (
    render_candidate_evidence_tree_nl_explain,
)
from kernel.core.store._candidate_evidence_tree_summary import (
    summarize_candidate_evidence_tree_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_tree(assertion_nodes: list[dict]) -> dict:
    """Build a minimal candidate_evidence_tree wrapping given assertion_fact nodes."""
    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": "c1",
        "support_kind": "native",
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


def _make_assertion_fact(asrt_id: str, fact_meta: dict | None = None) -> dict:
    node: dict[str, Any] = {
        "node_id": f"asrt:{asrt_id}",
        "node_kind": "assertion_fact",
        "title": f"Assertion {asrt_id}",
        "asrt_id": asrt_id,
        "pred_id": "score",
        "e_ref": "entity:alice",
        "claim_args": [{"idx": 0, "tag": "val", "val": "720"}],
        "children": [],
    }
    if fact_meta is not None:
        node["fact_meta"] = fact_meta
    return node


def _minimal_summary(tree: dict) -> dict:
    return summarize_candidate_evidence_tree_dict(tree)


# ---------------------------------------------------------------------------
# _extract_fact_meta: runtime path (flat_meta)
# ---------------------------------------------------------------------------

class ExtractFactMetaRuntimePathTests(unittest.TestCase):
    def test_flat_meta_with_source(self) -> None:
        detail = {
            "asrt_id": "a1",
            "flat_meta": {"source": "Q1 Report", "approved_by": "agent-1"},
        }
        result = _extract_fact_meta(detail)
        assert result is not None
        assert result["source"] == "Q1 Report"
        assert result["approved_by"] == "agent-1"

    def test_flat_meta_all_keys(self) -> None:
        detail = {
            "flat_meta": {
                "source": "doc.pdf",
                "source_loc": "p.3",
                "approved_by": "ag-xyz",
                "trace_id": "bundle-1",
                "note": "manual review",
            }
        }
        result = _extract_fact_meta(detail)
        assert result is not None
        assert result["source_loc"] == "p.3"
        assert result["trace_id"] == "bundle-1"
        assert result["note"] == "manual review"

    def test_flat_meta_empty_returns_none(self) -> None:
        detail = {"flat_meta": {}}
        assert _extract_fact_meta(detail) is None

    def test_flat_meta_only_unknown_keys_filtered(self) -> None:
        detail = {"flat_meta": {"unknown_key": "value"}}
        assert _extract_fact_meta(detail) is None

    def test_no_flat_meta_no_meta_returns_none(self) -> None:
        detail = {"asrt_id": "a1", "claim": {}, "claim_args": []}
        assert _extract_fact_meta(detail) is None


# ---------------------------------------------------------------------------
# _extract_fact_meta: audit path (kind-grouped meta)
# ---------------------------------------------------------------------------

class ExtractFactMetaAuditPathTests(unittest.TestCase):
    def test_str_rows_with_source(self) -> None:
        detail = {
            "meta": {
                "str": [
                    {"key": "source", "kind": "str", "value": "contract.pdf"},
                    {"key": "approved_by", "kind": "str", "value": "agent-2"},
                ]
            }
        }
        result = _extract_fact_meta(detail)
        assert result is not None
        assert result["source"] == "contract.pdf"
        assert result["approved_by"] == "agent-2"

    def test_str_rows_unknown_keys_filtered(self) -> None:
        detail = {
            "meta": {
                "str": [
                    {"key": "irrelevant_key", "kind": "str", "value": "x"},
                ]
            }
        }
        assert _extract_fact_meta(detail) is None

    def test_empty_str_rows_returns_none(self) -> None:
        detail = {"meta": {"str": []}}
        assert _extract_fact_meta(detail) is None

    def test_no_str_key_returns_none(self) -> None:
        detail = {"meta": {"float": [{"key": "confidence", "value": "0.9"}]}}
        assert _extract_fact_meta(detail) is None

    def test_flat_meta_takes_precedence_over_grouped(self) -> None:
        """Runtime flat_meta wins when both paths are present."""
        detail = {
            "flat_meta": {"source": "from-runtime"},
            "meta": {
                "str": [{"key": "source", "kind": "str", "value": "from-audit"}]
            },
        }
        result = _extract_fact_meta(detail)
        assert result is not None
        assert result["source"] == "from-runtime"


# ---------------------------------------------------------------------------
# _build_assertion_leaf: fact_meta field
# ---------------------------------------------------------------------------

class BuildAssertionLeafFactMetaTests(unittest.TestCase):
    def _lookup_with_meta(self, asrt_id: str) -> dict:
        return {
            "asrt_id": asrt_id,
            "claim": {"asrt_id": asrt_id, "pred_id": "score", "e_ref": "entity:alice"},
            "claim_args": [{"idx": 0, "tag": "val", "val": "720"}],
            "flat_meta": {"source": "Q1 Report", "approved_by": "agent-1"},
        }

    def _lookup_without_meta(self, asrt_id: str) -> dict:
        return {
            "asrt_id": asrt_id,
            "claim": {"asrt_id": asrt_id, "pred_id": "score", "e_ref": "entity:alice"},
            "claim_args": [{"idx": 0, "tag": "val", "val": "720"}],
        }

    def test_fact_meta_populated_when_source_present(self) -> None:
        node = _build_assertion_leaf("a1", assertion_lookup=self._lookup_with_meta)
        assert "fact_meta" in node
        assert node["fact_meta"]["source"] == "Q1 Report"
        assert node["fact_meta"]["approved_by"] == "agent-1"

    def test_fact_meta_absent_when_no_source(self) -> None:
        node = _build_assertion_leaf("a1", assertion_lookup=self._lookup_without_meta)
        assert "fact_meta" not in node


# ---------------------------------------------------------------------------
# render_candidate_evidence_tree_narrative: source_lines
# ---------------------------------------------------------------------------

class NarrativeSourceLinesTests(unittest.TestCase):
    def _make_tree_with_source(self) -> dict:
        node = _make_assertion_fact("a1", fact_meta={"source": "Q1 Report", "approved_by": "agent-1"})
        return _make_minimal_tree([node])

    def _make_tree_without_source(self) -> dict:
        node = _make_assertion_fact("a2")
        return _make_minimal_tree([node])

    def test_source_lines_present_when_tree_has_fact_meta(self) -> None:
        tree = self._make_tree_with_source()
        summary = _minimal_summary(tree)
        narrative = render_candidate_evidence_tree_narrative(summary, tree=tree)
        assert "source_lines" in narrative
        assert len(narrative["source_lines"]) == 1
        assert "Q1 Report" in narrative["source_lines"][0]
        assert "agent-1" in narrative["source_lines"][0]

    def test_source_lines_absent_when_no_tree(self) -> None:
        tree = self._make_tree_with_source()
        summary = _minimal_summary(tree)
        narrative = render_candidate_evidence_tree_narrative(summary)
        assert "source_lines" not in narrative

    def test_source_lines_absent_when_tree_has_no_fact_meta(self) -> None:
        tree = self._make_tree_without_source()
        summary = _minimal_summary(tree)
        narrative = render_candidate_evidence_tree_narrative(summary, tree=tree)
        assert "source_lines" not in narrative

    def test_backward_compat_existing_fields_unaffected(self) -> None:
        """Passing tree=None preserves all existing narrative fields."""
        tree = self._make_tree_without_source()
        summary = _minimal_summary(tree)
        baseline = render_candidate_evidence_tree_narrative(summary)
        with_tree = render_candidate_evidence_tree_narrative(summary, tree=tree)
        for key in baseline:
            assert key in with_tree
            assert with_tree[key] == baseline[key]

    def test_source_line_format_pred_entity(self) -> None:
        """source_line contains pred_id(e_ref) label."""
        node = _make_assertion_fact("a1", fact_meta={"source": "report.pdf"})
        tree = _make_minimal_tree([node])
        summary = _minimal_summary(tree)
        narrative = render_candidate_evidence_tree_narrative(summary, tree=tree)
        line = narrative["source_lines"][0]
        assert "score(entity:alice)" in line
        assert "report.pdf" in line


# ---------------------------------------------------------------------------
# render_candidate_evidence_tree_nl_explain: source paragraph
# ---------------------------------------------------------------------------

class NLSourceParagraphTests(unittest.TestCase):
    def _narrative_with_source_lines(self, tree: dict) -> dict:
        summary = _minimal_summary(tree)
        return render_candidate_evidence_tree_narrative(summary, tree=tree)

    def _narrative_without_source_lines(self, tree: dict) -> dict:
        summary = _minimal_summary(tree)
        return render_candidate_evidence_tree_narrative(summary)

    def test_source_paragraph_in_nl_when_source_lines_present(self) -> None:
        node = _make_assertion_fact("a1", fact_meta={"source": "Q1 Report"})
        tree = _make_minimal_tree([node])
        summary = _minimal_summary(tree)
        narrative = self._narrative_with_source_lines(tree)
        nl = render_candidate_evidence_tree_nl_explain(summary, narrative)
        assert any("Fact sources:" in p for p in nl["paragraphs"])
        assert any("Q1 Report" in p for p in nl["paragraphs"])

    def test_no_source_paragraph_when_no_source_lines(self) -> None:
        node = _make_assertion_fact("a2")
        tree = _make_minimal_tree([node])
        summary = _minimal_summary(tree)
        narrative = self._narrative_without_source_lines(tree)
        nl = render_candidate_evidence_tree_nl_explain(summary, narrative)
        assert not any("Fact sources:" in p for p in nl["paragraphs"])

    def test_other_paragraphs_unaffected(self) -> None:
        """Adding source_lines doesn't remove existing NL paragraphs."""
        node = _make_assertion_fact("a1", fact_meta={"source": "rep"})
        tree = _make_minimal_tree([node])
        summary = _minimal_summary(tree)
        narrative_with = self._narrative_with_source_lines(tree)
        narrative_without = self._narrative_without_source_lines(tree)
        nl_with = render_candidate_evidence_tree_nl_explain(summary, narrative_with)
        nl_without = render_candidate_evidence_tree_nl_explain(summary, narrative_without)
        # All paragraphs from baseline are present in the richer version
        for p in nl_without["paragraphs"]:
            assert p in nl_with["paragraphs"]


# ---------------------------------------------------------------------------
# static_ui: source tooltip on assertion_fact
# ---------------------------------------------------------------------------

class StaticUISourceTooltipTests(unittest.TestCase):
    def _render_tree(self, assertion_nodes: list) -> str:
        tree = _make_minimal_tree(assertion_nodes)
        summary = _minimal_summary(tree)
        narrative = render_candidate_evidence_tree_narrative(summary)
        return render_candidate_evidence_html(tree, narrative=narrative)

    def test_source_tooltip_rendered_when_fact_meta_present(self) -> None:
        node = _make_assertion_fact(
            "a1",
            fact_meta={"source": "Q1 Report", "source_loc": "p.5", "approved_by": "agent-xyz"},
        )
        html = self._render_tree([node])
        assert "Source" in html
        assert "Q1 Report" in html

    def test_source_tooltip_absent_when_no_fact_meta(self) -> None:
        node = _make_assertion_fact("a2")
        html = self._render_tree([node])
        assert "Source" not in html

    def test_source_tooltip_absent_when_fact_meta_has_no_source(self) -> None:
        node = _make_assertion_fact("a3", fact_meta={"approved_by": "agent-1"})
        html = self._render_tree([node])
        assert "Source" not in html


if __name__ == "__main__":
    unittest.main()
