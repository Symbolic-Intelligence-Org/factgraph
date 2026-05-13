from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import kernel.sdk as kernel_sdk
from kernel.sdk import Entity, FactGraph, Field, Identity


REPO_ROOT = Path(__file__).resolve().parents[3]
BLUEPRINT_AUDIT = (
    REPO_ROOT
    / "docs"
    / "blueprints"
    / "archive"
    / "2026-05-13_official-kernel-docstrings-and-tutorials.audit.md"
)
OFFICIAL_DOCS_ROOT = REPO_ROOT / "docs" / "official" / "kernel"


class _DocGateUser(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _new_factgraph() -> FactGraph:
    return FactGraph.create(schema_classes=[_DocGateUser])


def _assert_has_docstring(testcase: unittest.TestCase, obj: object, label: str) -> None:
    doc = inspect.getdoc(obj)
    testcase.assertIsInstance(doc, str, f"{label} must expose an inspect.getdoc(...) string")
    testcase.assertTrue(doc.strip(), f"{label} must expose a non-empty inspect.getdoc(...) string")


class TestDocstringCoverageGate(unittest.TestCase):
    def test_all_public_exports_have_docstring(self) -> None:
        for name in kernel_sdk.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(kernel_sdk, name), f"kernel.sdk missing export {name!r}")
                _assert_has_docstring(self, getattr(kernel_sdk, name), f"kernel.sdk.{name}")

    def test_selected_factgraph_namespace_methods_have_docstring(self) -> None:
        fg = _new_factgraph()
        method_paths = (
            ("FactGraph.create", FactGraph.create),
            ("FactGraph.load", FactGraph.load),
            ("FactGraph.save", FactGraph.save),
            ("fg.schema.add", fg.schema.add),
            ("fg.read.get", fg.read.get),
            ("fg.read.find", fg.read.find),
            ("fg.read.ref", fg.read.ref),
            ("fg.write.set", fg.write.set),
            ("fg.write.add", fg.write.add),
            ("fg.write.retract", fg.write.retract),
            ("fg.rules.inspect", fg.rules.inspect),
            ("fg.rules.save", fg.rules.save),
            ("fg.rules.load", fg.rules.load),
            ("fg.rules.list", fg.rules.list),
            ("fg.rules.get", fg.rules.get),
            ("fg.inferences.save", fg.inferences.save),
            ("fg.inferences.load", fg.inferences.load),
            ("fg.inferences.list", fg.inferences.list),
            ("fg.inferences.get", fg.inferences.get),
            ("fg.eval.run", fg.eval.run),
            ("fg.eval.evaluate", fg.eval.evaluate),
            ("fg.eval.accept", fg.eval.accept),
            ("fg.eval.accept_many", fg.eval.accept_many),
            ("fg.eval.inspect_semantics", fg.eval.inspect_semantics),
            ("fg.what_if.check", fg.what_if.check),
            ("fg.what_if.diagnose", fg.what_if.diagnose),
            ("fg.what_if.why_not", fg.what_if.why_not),
            ("fg.what_if.fact_overlay.check", fg.what_if.fact_overlay.check),
            (
                "fg.what_if.fact_overlay.recheck_proof_frame",
                fg.what_if.fact_overlay.recheck_proof_frame,
            ),
            ("fg.what_if.rule.disable", fg.what_if.rule.disable),
            ("fg.what_if.rule.literal_replace", fg.what_if.rule.literal_replace),
            ("fg.what_if.rule.add_condition", fg.what_if.rule.add_condition),
            ("fg.audit.explain_fact", fg.audit.explain_fact),
            ("fg.audit.conflicts", fg.audit.conflicts),
            ("fg.audit.diff_proof_frames", fg.audit.diff_proof_frames),
            ("fg.package.export_package", fg.package.export_package),
            ("fg.package.run_package", fg.package.run_package),
            ("fg.views.create", fg.views.create),
            ("fg.views.update", fg.views.update),
            ("fg.views.delete", fg.views.delete),
            ("fg.views.get", fg.views.get),
            ("fg.views.list", fg.views.list),
        )
        for label, obj in method_paths:
            with self.subTest(method=label):
                _assert_has_docstring(self, obj, label)

    def test_private_helpers_are_not_in_docstring_gate_scope(self) -> None:
        for name in kernel_sdk.__all__:
            with self.subTest(name=name):
                self.assertFalse(name.startswith("_"), "kernel.sdk.__all__ must not export private helpers")


class TestOfficialDocsTreeGate(unittest.TestCase):
    def test_official_docs_tree_structure_exists(self) -> None:
        paths = (
            OFFICIAL_DOCS_ROOT,
            OFFICIAL_DOCS_ROOT / "index.md",
            OFFICIAL_DOCS_ROOT / "quickstart",
            OFFICIAL_DOCS_ROOT / "quickstart" / "index.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "first-factgraph.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "schema.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "read-write.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "rules-and-inferences.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "semantics.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "persistence.md",
            OFFICIAL_DOCS_ROOT / "quickstart" / "namespace-map.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertTrue(path.exists(), f"expected official docs path to exist: {path}")

    def test_official_docs_tree_is_quickstart_only(self) -> None:
        for name in ("concepts", "how-to", "reference"):
            path = OFFICIAL_DOCS_ROOT / name
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertFalse(path.exists(), f"official docs should be quickstart-only: {path}")


class TestPageBriefTemplateGate(unittest.TestCase):
    REQUIRED_FIELDS = (
        "Reader goal",
        "Core mental model",
        "Common misconception to prevent",
        "APIs covered",
        "Non-goals",
        "Source files checked",
        "Module docs checked",
        "Design references checked",
        "Archived blueprints checked",
        "Example snippets planned",
        "Validation method",
        "External style reference",
    )

    def _audit_text(self) -> str:
        return BLUEPRINT_AUDIT.read_text(encoding="utf-8")

    def test_audit_log_has_page_briefs_section(self) -> None:
        self.assertIn("## Page Briefs", self._audit_text())

    def test_page_brief_template_lists_required_fields(self) -> None:
        text = self._audit_text()
        for field in self.REQUIRED_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"- {field}:", text)


if __name__ == "__main__":
    unittest.main()
