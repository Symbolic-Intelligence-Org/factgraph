"""Phase 1 namespace-shape tests for the post-L SDK ergonomics redesign.

Per blueprint `2026-05-09_post-l-sdk-ergonomics-redesign.md` §5.2 lock
(teaching taxonomy: 8 top-level namespaces + 2 sub-namespaces under
`what_if`) + §5.4 Option 2 lock (additive aliases via property /
private-manager-class pattern per `views` precedent at `store.py:66-104`
+ `EntitySnapshot.assertions` precedent at `facade.py:102-217`).

Asserts:
- Each top-level taxonomy namespace exists as a property on `FactGraph`
  returning the correct private manager type.
- Sub-namespaces under `what_if` (`fact_overlay`, `rule`) exist as
  property-of-property accessors with correct manager types.
- Manager classes are private (underscore-prefixed) and not exported
  in `kernel.sdk.__all__`.
- Read-only enforcement via `__setattr__` raising `FrozenSnapshotError`
  on every manager (mirrors `EntitySnapshot.assertions` precedent).
- Property accessors are idempotent (same instance per call).
"""

from __future__ import annotations

import unittest

import kernel.sdk as kernel_sdk
from kernel.sdk import Entity, FactGraph, Field, FrozenSnapshotError, Identity
from kernel.sdk.store import (
    _SDKAuditManager,
    _SDKEvalManager,
    _SDKPackageManager,
    _SDKReadManager,
    _SDKSchemaManager,
    _SDKViewsManager,
    _SDKWhatIfFactOverlayManager,
    _SDKWhatIfManager,
    _SDKWhatIfRuleManager,
    _SDKWriteManager,
)


class Person(Entity):
    pid: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _new_fg() -> FactGraph:
    return FactGraph.from_schema_classes([Person])


class TopLevelNamespacePresenceTests(unittest.TestCase):
    """8 top-level taxonomy namespaces present on `FactGraph`."""

    def test_schema_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.schema, _SDKSchemaManager)

    def test_read_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.read, _SDKReadManager)

    def test_write_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.write, _SDKWriteManager)

    def test_eval_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.eval, _SDKEvalManager)

    def test_what_if_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.what_if, _SDKWhatIfManager)

    def test_audit_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.audit, _SDKAuditManager)

    def test_package_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.package, _SDKPackageManager)

    def test_views_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.views, _SDKViewsManager)


class WhatIfSubNamespacePresenceTests(unittest.TestCase):
    """2 sub-namespaces under `what_if` (`fact_overlay`, `rule`)."""

    def test_fact_overlay_sub_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.what_if.fact_overlay, _SDKWhatIfFactOverlayManager)

    def test_rule_sub_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.what_if.rule, _SDKWhatIfRuleManager)


class ManagerPrivacyTests(unittest.TestCase):
    """Manager classes are private and NOT in `kernel.sdk.__all__`."""

    MANAGER_CLASS_NAMES = (
        "_SDKSchemaManager",
        "_SDKReadManager",
        "_SDKWriteManager",
        "_SDKEvalManager",
        "_SDKWhatIfManager",
        "_SDKWhatIfFactOverlayManager",
        "_SDKWhatIfRuleManager",
        "_SDKAuditManager",
        "_SDKPackageManager",
        "_SDKViewsManager",
    )

    def test_manager_class_names_start_with_underscore(self) -> None:
        for name in self.MANAGER_CLASS_NAMES:
            with self.subTest(name=name):
                self.assertTrue(
                    name.startswith("_"),
                    f"Manager class {name!r} must be private (underscore prefix)",
                )

    def test_manager_classes_not_in_kernel_sdk_all(self) -> None:
        for name in self.MANAGER_CLASS_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(
                    name,
                    kernel_sdk.__all__,
                    f"Manager class {name!r} must not appear in kernel.sdk.__all__",
                )


class ReadOnlyEnforcementTests(unittest.TestCase):
    """Every manager raises `FrozenSnapshotError` on attribute assignment.

    Mirrors `EntitySnapshot.assertions` precedent at `facade.py:102-217`
    via `__setattr__` override per §5.4 Option 2 lock.
    """

    def _assert_read_only(self, manager: object, namespace_name: str) -> None:
        with self.assertRaises(FrozenSnapshotError):
            manager.foo = "bar"  # type: ignore[attr-defined]

    def test_schema_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().schema, "schema")

    def test_read_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().read, "read")

    def test_write_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().write, "write")

    def test_eval_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().eval, "eval")

    def test_what_if_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().what_if, "what_if")

    def test_what_if_fact_overlay_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().what_if.fact_overlay, "what_if.fact_overlay")

    def test_what_if_rule_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().what_if.rule, "what_if.rule")

    def test_audit_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().audit, "audit")

    def test_package_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().package, "package")


class PropertyAccessorIdempotenceTests(unittest.TestCase):
    """Repeated property access returns the same manager instance.

    Managers are constructed once in `__init__` and held as private
    attributes; the property returns the held instance.
    """

    def test_schema_property_idempotent(self) -> None:
        fg = _new_fg()
        self.assertIs(fg.schema, fg.schema)

    def test_what_if_property_idempotent(self) -> None:
        fg = _new_fg()
        self.assertIs(fg.what_if, fg.what_if)

    def test_what_if_fact_overlay_property_idempotent(self) -> None:
        fg = _new_fg()
        self.assertIs(fg.what_if.fact_overlay, fg.what_if.fact_overlay)

    def test_what_if_rule_property_idempotent(self) -> None:
        fg = _new_fg()
        self.assertIs(fg.what_if.rule, fg.what_if.rule)


class SubNamespaceParentScopingTests(unittest.TestCase):
    """Sub-namespace managers are scoped to their parent FactGraph instance.

    Two distinct FactGraph instances must produce distinct sub-namespace
    manager instances (each binds to its own SDK reference).
    """

    def test_distinct_instances_have_distinct_what_if_managers(self) -> None:
        fg_a = _new_fg()
        fg_b = _new_fg()
        self.assertIsNot(fg_a.what_if, fg_b.what_if)

    def test_distinct_instances_have_distinct_fact_overlay_managers(self) -> None:
        fg_a = _new_fg()
        fg_b = _new_fg()
        self.assertIsNot(fg_a.what_if.fact_overlay, fg_b.what_if.fact_overlay)


if __name__ == "__main__":
    unittest.main()
