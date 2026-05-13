from __future__ import annotations

import inspect
import unittest

import factpy.sdk as sdk_module
from factpy.core.view.projector import project_view_facts
from factpy.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class FrozenViewSurfaceTests(unittest.TestCase):
    def test_public_exports_remain_unchanged(self) -> None:
        self.assertEqual(len(sdk_module.__all__), 41)
        self.assertIn("ReadPolicy", sdk_module.__all__)
        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIn("ProbLogSemantics", sdk_module.__all__)
        self.assertIn("PyReasonSemantics", sdk_module.__all__)
        self.assertNotIn("FrozenAssertionView", sdk_module.__all__)
        self.assertNotIn("AssertionRecordSet", sdk_module.__all__)

    def test_assertions_namespace_is_top_level_property_not_export(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        self.assertTrue(hasattr(fg, "assertions"))
        self.assertNotIn("assertions", sdk_module.__all__)
        self.assertFalse(hasattr(fg.read, "assertions"))
        self.assertFalse(hasattr(fg.write, "assertions"))

    def test_no_view_patch_or_diff_surface(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        self.assertFalse(hasattr(fg.views, "patch"))
        self.assertFalse(hasattr(fg.views, "diff"))

    def test_project_view_facts_signature_unchanged(self) -> None:
        signature = inspect.signature(project_view_facts)

        self.assertEqual(tuple(signature.parameters), ("ledger", "schema_ir"))
        self.assertNotIn("assertion_universe", signature.parameters)


if __name__ == "__main__":
    unittest.main()
