"""Fault-injection characterization for the broad boundary in product_explanation_data_v2.

``_opaque_locator_wire`` accepts third-party locator descriptors that expose
``to_wire()``.  A descriptor whose ``to_wire()`` raises must be rejected exactly
like malformed wire input - it must not produce a half-built locator and must
not let the provenance descriptor be assembled from a broken locator.
"""

from __future__ import annotations

import unittest

from factgraph.application.product_explanation_data_v2 import _opaque_locator_wire


class _BoundaryFault(Exception):
    """Custom failure raised by a hostile third-party locator descriptor."""


class _ExplodingLocator:
    kind = "opaque"

    def to_wire(self):
        raise _BoundaryFault("injected to_wire failure")


class _InterruptingLocator:
    kind = "opaque"

    def to_wire(self):
        raise KeyboardInterrupt


class _GoodLocator:
    kind = "opaque"

    def to_wire(self):
        return {"kind": "opaque", "opaque_ref": "ref-1"}


class OpaqueLocatorWireBoundaryTests(unittest.TestCase):
    """src/factgraph/application/product_explanation_data_v2.py: ``to_wire()`` boundary."""

    def test_to_wire_fault_is_rejected_as_unusable_wire(self) -> None:
        # Typed outcome: None, i.e. "no usable locator", identical to malformed input.
        self.assertIsNone(_opaque_locator_wire(_ExplodingLocator()))

    def test_non_mapping_to_wire_is_rejected_the_same_way(self) -> None:
        class _WrongType:
            kind = "opaque"

            def to_wire(self):
                return "not-a-mapping"

        self.assertIsNone(_opaque_locator_wire(_WrongType()))

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            _opaque_locator_wire(_InterruptingLocator())

    def test_healthy_descriptor_still_produces_wire(self) -> None:
        wire = _opaque_locator_wire(_GoodLocator())
        self.assertIsNotNone(wire)
        assert wire is not None
        self.assertEqual(wire.get("kind"), "opaque")
        self.assertEqual(wire.get("opaque_ref"), "ref-1")


if __name__ == "__main__":
    unittest.main()
