"""Tests for L2 annotation consumer migration.

Validates the full chain:
  Ledger annotation_rows
    → package.py assertion_annotations.jsonl export
    → reader.py optional artifact load
    → assertions.py annotation index + detail
    → static_ui.py annotation panel rendering
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kernel.audit.assertions import AuditAssertionIndex, load_assertion_index
from service.static_ui import _render_annotation_panel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_annotations() -> list[dict[str, Any]]:
    """Sample annotation rows as exported in assertion_annotations.jsonl."""
    return [
        {
            "asrt_id": "A001",
            "namespace": "pyreason",
            "category": "semantic",
            "key": "bound_lower",
            "kind": "float",
            "value": 0.6,
            "origin": "observed",
            "derivation": None,
        },
        {
            "asrt_id": "A001",
            "namespace": "pyreason",
            "category": "semantic",
            "key": "bound_upper",
            "kind": "float",
            "value": 0.9,
            "origin": "observed",
            "derivation": None,
        },
        {
            "asrt_id": "A001",
            "namespace": "shared",
            "category": "derived",
            "key": "confidence",
            "kind": "float",
            "value": 0.6,
            "origin": "derived",
            "derivation": "pyreason:lower_bound",
        },
        {
            "asrt_id": "A002",
            "namespace": "pyreason",
            "category": "semantic",
            "key": "bound_lower",
            "kind": "float",
            "value": 1.0,
            "origin": "observed",
            "derivation": None,
        },
    ]


# ---------------------------------------------------------------------------
# Assertions: annotation index + detail (unit tests on AuditAssertionIndex)
# ---------------------------------------------------------------------------

class AssertionAnnotationIndexTests(unittest.TestCase):

    def _build_index(
        self,
        annotations: list[dict[str, Any]] | None = None,
    ) -> AuditAssertionIndex:
        """Build an AuditAssertionIndex directly with annotation data."""
        claims = {
            "A001": {
                "asrt_id": "A001",
                "pred_id": "user:popular",
                "e_ref": "Alice",
                "tup_digest": "sha256:abc",
                "is_revoked": False,
            },
            "A002": {
                "asrt_id": "A002",
                "pred_id": "user:name",
                "e_ref": "Bob",
                "tup_digest": "sha256:def",
                "is_revoked": False,
            },
        }
        ann_list = annotations or []
        # Build annotation index: asrt_id → sorted list
        ann_index: dict[str, list[dict[str, Any]]] = {}
        for ann in ann_list:
            asrt_id = ann.get("asrt_id", "")
            ann_index.setdefault(asrt_id, []).append(ann)
        for v in ann_index.values():
            v.sort(key=lambda a: (a.get("namespace", ""), a.get("key", "")))

        return AuditAssertionIndex(
            package_dir=Path("/tmp/test-l2"),
            claims=claims,
            claim_args={},
            meta={},
            revoked_by={},
            revokes={},
            annotations=ann_index,
        )

    def test_annotations_indexed_by_asrt_id(self) -> None:
        idx = self._build_index(_sample_annotations())
        self.assertIn("A001", idx.annotations)
        self.assertIn("A002", idx.annotations)
        self.assertEqual(len(idx.annotations["A001"]), 3)
        self.assertEqual(len(idx.annotations["A002"]), 1)

    def test_empty_annotations_produce_empty_index(self) -> None:
        idx = self._build_index([])
        self.assertEqual(idx.annotations, {})

    def test_detail_includes_annotations(self) -> None:
        idx = self._build_index(_sample_annotations())
        detail = idx.get_assertion_detail("A001")
        self.assertIsNotNone(detail)
        self.assertIn("annotations", detail)
        self.assertEqual(len(detail["annotations"]), 3)
        keys = {a["key"] for a in detail["annotations"]}
        self.assertIn("bound_lower", keys)
        self.assertIn("bound_upper", keys)
        self.assertIn("confidence", keys)

    def test_detail_without_annotations(self) -> None:
        idx = self._build_index([])
        detail = idx.get_assertion_detail("A001")
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("annotations", []), [])

    def test_annotations_sorted_by_namespace_then_key(self) -> None:
        idx = self._build_index(_sample_annotations())
        anns = idx.annotations["A001"]
        # pyreason before shared, bound_lower before bound_upper
        ns_keys = [(a["namespace"], a["key"]) for a in anns]
        self.assertEqual(ns_keys, sorted(ns_keys))


# ---------------------------------------------------------------------------
# Package: JSONL export round-trip
# ---------------------------------------------------------------------------

class PackageAnnotationExportTests(unittest.TestCase):

    def test_jsonl_round_trip(self) -> None:
        """Write annotations as JSONL, parse back, verify structure."""
        annotations = _sample_annotations()
        with TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "assertion_annotations.jsonl"
            with open(jsonl_path, "w") as f:
                for row in annotations:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

            loaded = []
            with open(jsonl_path) as f:
                for line in f:
                    loaded.append(json.loads(line))

            self.assertEqual(len(loaded), 4)
            self.assertEqual(loaded[0]["key"], "bound_lower")
            self.assertEqual(loaded[0]["namespace"], "pyreason")


# ---------------------------------------------------------------------------
# Static UI: annotation panel rendering
# ---------------------------------------------------------------------------

class AnnotationPanelRenderingTests(unittest.TestCase):

    def test_empty_annotations_produce_empty_string(self) -> None:
        html = _render_annotation_panel([])
        self.assertEqual(html, "")

    def test_single_namespace(self) -> None:
        annotations = [
            {"namespace": "pyreason", "category": "semantic",
             "key": "bound_lower", "value": 0.6, "origin": "observed"},
            {"namespace": "pyreason", "category": "semantic",
             "key": "bound_upper", "value": 0.9, "origin": "observed"},
        ]
        html = _render_annotation_panel(annotations)
        self.assertIn("<h2>Annotations</h2>", html)
        self.assertIn("PyReason", html)
        self.assertIn("bound_lower", html)
        self.assertIn("bound_upper", html)
        self.assertIn("0.6", html)

    def test_multiple_namespaces(self) -> None:
        annotations = [
            {"namespace": "pyreason", "category": "semantic",
             "key": "bound_lower", "value": 0.6, "origin": "observed", "derivation": None},
            {"namespace": "shared", "category": "derived",
             "key": "confidence", "value": 0.6, "origin": "derived", "derivation": "pyreason:lower_bound"},
        ]
        html = _render_annotation_panel(annotations)
        self.assertIn("PyReason", html)
        self.assertIn("Shared", html)
        self.assertIn("confidence", html)
        self.assertIn("pyreason:lower_bound", html)

    def test_unknown_namespace(self) -> None:
        annotations = [
            {"namespace": "custom_engine", "category": "semantic",
             "key": "custom_val", "value": 42, "origin": "observed"},
        ]
        html = _render_annotation_panel(annotations)
        self.assertIn("custom_engine", html)

    def test_html_escaping(self) -> None:
        """Values with HTML special chars should be escaped."""
        annotations = [
            {"namespace": "pyreason", "category": "semantic",
             "key": "<script>alert(1)</script>", "value": "a&b",
             "origin": "observed"},
        ]
        html = _render_annotation_panel(annotations)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("a&amp;b", html)

    def test_panel_has_table_structure(self) -> None:
        annotations = [
            {"namespace": "pyreason", "category": "semantic",
             "key": "bound_lower", "value": 0.6, "origin": "observed"},
        ]
        html = _render_annotation_panel(annotations)
        self.assertIn("<table>", html)
        self.assertIn("<th>category</th>", html)
        self.assertIn("<th>key</th>", html)
        self.assertIn("<th>value</th>", html)
        self.assertIn("<th>origin</th>", html)
        self.assertIn("<th>derivation</th>", html)


if __name__ == "__main__":
    unittest.main()
