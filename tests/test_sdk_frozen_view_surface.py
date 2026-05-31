from __future__ import annotations

import inspect
import unittest

import factgraph.sdk as sdk_module
from factgraph.core.view.projector import project_view_facts
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


class FrozenViewSurfaceTests(unittest.TestCase):
    def test_public_exports_remain_unchanged(self) -> None:
        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIn("ProbLogSemantics", sdk_module.__all__)
        self.assertIn("PyReasonSemantics", sdk_module.__all__)
        self.assertNotIn("FrozenAssertionSet", sdk_module.__all__)
        self.assertNotIn("AssertionRecordSet", sdk_module.__all__)

    def test_assertions_namespace_is_top_level_property_not_export(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        self.assertTrue(hasattr(fg, "assertions"))
        self.assertNotIn("assertions", sdk_module.__all__)
        self.assertFalse(hasattr(fg, "read"))
        self.assertFalse(hasattr(fg, "write"))

    def test_no_view_patch_or_diff_surface(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        self.assertFalse(hasattr(fg.assertion_views, "patch"))
        self.assertFalse(hasattr(fg.assertion_views, "diff"))

    def test_project_view_facts_signature_unchanged(self) -> None:
        signature = inspect.signature(project_view_facts)

        self.assertEqual(tuple(signature.parameters), ("ledger", "schema_ir"))
        self.assertNotIn("assertion_universe", signature.parameters)


if __name__ == "__main__":
    unittest.main()
