from __future__ import annotations

import unittest
from types import MappingProxyType

from factgraph.application.capabilities import compute_capabilities
from factgraph.core.protocol.tup_v1 import CANONICAL_TAGS
from factgraph.sdk import Entity, FactGraph, Field, FrozenSnapshotError, Identity


class _DummyEntity(Entity):
    user_id: str = Identity()
    region: str = Field()


def _fg() -> FactGraph:
    return FactGraph.create(schema_classes=[_DummyEntity])


class FgMetaCapabilitiesTests(unittest.TestCase):
    def test_fg_has_meta_namespace_with_capabilities(self) -> None:
        fg = _fg()
        caps = fg.meta.capabilities()

        self.assertEqual(set(caps.keys()), {"value_kinds", "scalar_tags", "cardinalities"})

    def test_capabilities_values_match_shipped_constants(self) -> None:
        caps = _fg().meta.capabilities()

        self.assertEqual(caps["value_kinds"], frozenset({"scalar", "entity_ref"}))
        self.assertEqual(caps["cardinalities"], frozenset({"single", "multi"}))
        expected_scalar_tags = frozenset(tag for tag in CANONICAL_TAGS if tag != "entity_ref")
        self.assertEqual(caps["scalar_tags"], expected_scalar_tags)

    def test_capabilities_result_is_immutable(self) -> None:
        caps = _fg().meta.capabilities()

        self.assertIsInstance(caps, MappingProxyType)
        for value in caps.values():
            self.assertIsInstance(value, frozenset)

    def test_fg_meta_is_read_only(self) -> None:
        fg = _fg()
        with self.assertRaises(FrozenSnapshotError):
            fg.meta.something = "x"  # type: ignore[attr-defined]

    def test_application_layer_compute_capabilities_matches_sdk_shell(self) -> None:
        application_caps = compute_capabilities()
        sdk_caps = _fg().meta.capabilities()

        self.assertEqual(dict(application_caps), dict(sdk_caps))


if __name__ == "__main__":
    unittest.main()
