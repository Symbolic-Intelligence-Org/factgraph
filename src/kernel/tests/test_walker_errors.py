"""Hierarchy import + isinstance tests for walker error classes.

Per blueprint §4.1 Round 2 (B-R2-2 lightweight) and §8 Phase 0 acceptance.
"""

from __future__ import annotations

import unittest


class TestWalkerErrorHierarchyImport(unittest.TestCase):
    def test_all_seven_classes_importable_from_package(self) -> None:
        from kernel.application.walker import (
            UnboundedStreamError,
            WalkerError,
            WalkerFrozenError,
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
        )

        for cls in (
            WalkerError,
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
            WalkerFrozenError,
            UnboundedStreamError,
        ):
            self.assertTrue(isinstance(cls, type))

    def test_all_subclasses_extend_walker_error(self) -> None:
        from kernel.application.walker import (
            UnboundedStreamError,
            WalkerError,
            WalkerFrozenError,
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
        )

        for cls in (
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
            WalkerFrozenError,
            UnboundedStreamError,
        ):
            self.assertTrue(issubclass(cls, WalkerError))

    def test_walker_error_extends_exception_not_value_error(self) -> None:
        from kernel.application.walker import WalkerError

        self.assertTrue(issubclass(WalkerError, Exception))
        # Per blueprint §4.1 Round 2: WalkerError does NOT extend ValueError.
        # CapabilityHelperError(ValueError) is a different convention used in A.
        self.assertFalse(issubclass(WalkerError, ValueError))

    def test_each_subclass_can_be_raised_and_caught_as_walker_error(self) -> None:
        from kernel.application.walker import (
            WalkerError,
            WalkerFrozenError,
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
        )

        for cls in (
            WalkerLookupError,
            WalkerParseError,
            WalkerReferenceError,
            WalkerSnapshotError,
            WalkerFrozenError,
        ):
            with self.assertRaises(WalkerError):
                raise cls("test message")
            with self.assertRaises(cls):
                raise cls("test message")


class TestWalkerErrorPackageExports(unittest.TestCase):
    def test_all_seven_error_classes_listed_in_package_all(self) -> None:
        from kernel.application import walker

        expected_error_names = {
            "UnboundedStreamError",
            "WalkerError",
            "WalkerFrozenError",
            "WalkerLookupError",
            "WalkerParseError",
            "WalkerReferenceError",
            "WalkerSnapshotError",
        }
        self.assertLessEqual(expected_error_names, set(walker.__all__))

    def test_package_error_exports_are_errors_module_classes(self) -> None:
        from kernel.application import walker
        from kernel.application.walker import errors

        for name in (
            "UnboundedStreamError",
            "WalkerError",
            "WalkerFrozenError",
            "WalkerLookupError",
            "WalkerParseError",
            "WalkerReferenceError",
            "WalkerSnapshotError",
        ):
            self.assertIs(getattr(walker, name), getattr(errors, name))


if __name__ == "__main__":
    unittest.main()
