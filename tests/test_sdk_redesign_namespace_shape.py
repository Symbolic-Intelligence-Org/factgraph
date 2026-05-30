"""Namespace-shape tests for the shipped SDK namespace surface.

Asserts:
- Each top-level taxonomy namespace exists as a property on `FactGraph`
  returning the correct private manager type.
- Legacy `read` / `write` namespaces are removed by the Slice 3a hard-cut.
- Manager classes are private (underscore-prefixed) and not exported
  in `factgraph.sdk.__all__`.
- Read-only enforcement via `__setattr__` raising `FrozenSnapshotError`
  on every manager (mirrors `EntitySnapshot.assertions` precedent).
- Property accessors are idempotent (same instance per call).
"""

from __future__ import annotations

import unittest

import factgraph.sdk as factgraph_sdk
from factgraph.sdk import Entity, FactGraph, Field, FrozenSnapshotError, Identity
from factgraph.sdk.store import (
    AssertionsManager,
    _SDKAuditManager,
    _SDKEntitiesManager,
    _SDKEvalManager,
    _SDKFieldsManager,
    _SDKInferencesManager,
    _SDKPackageManager,
    _SDKRulesManager,
    _SDKSchemaManager,
    _SDKViewsManager,
)


class Person(Entity):
    pid: str = Identity()
    name: str = Field()


def _new_fg() -> FactGraph:
    return FactGraph.from_schema_classes([Person])


class TopLevelNamespacePresenceTests(unittest.TestCase):
    """Current top-level taxonomy namespaces present on `FactGraph`."""

    def test_schema_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.schema, _SDKSchemaManager)

    def test_entities_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.entities, _SDKEntitiesManager)

    def test_fields_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.fields, _SDKFieldsManager)

    def test_assertions_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.assertions, AssertionsManager)

    def test_rules_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.rules, _SDKRulesManager)

    def test_inferences_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.inferences, _SDKInferencesManager)

    def test_eval_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.eval, _SDKEvalManager)

    def test_read_namespace_removed(self) -> None:
        fg = _new_fg()
        self.assertFalse(hasattr(fg, "read"))

    def test_write_namespace_removed(self) -> None:
        fg = _new_fg()
        self.assertFalse(hasattr(fg, "write"))

    def test_audit_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.audit, _SDKAuditManager)

    def test_package_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.package, _SDKPackageManager)

    def test_views_namespace_present(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.views, _SDKViewsManager)


class ManagerPrivacyTests(unittest.TestCase):
    """Manager classes are private and NOT in `factgraph.sdk.__all__`."""

    MANAGER_CLASS_NAMES = (
        "_SDKSchemaManager",
        "_SDKEntitiesManager",
        "_SDKFieldsManager",
        "_SDKEvalManager",
        "_SDKAuditManager",
        "_SDKPackageManager",
        "_SDKViewsManager",
        "_SDKRulesManager",
        "_SDKInferencesManager",
    )

    def test_manager_class_names_start_with_underscore(self) -> None:
        for name in self.MANAGER_CLASS_NAMES:
            with self.subTest(name=name):
                self.assertTrue(
                    name.startswith("_"),
                    f"Manager class {name!r} must be private (underscore prefix)",
                )

    def test_manager_classes_not_in_factgraph_sdk_all(self) -> None:
        for name in self.MANAGER_CLASS_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(
                    name,
                    factgraph_sdk.__all__,
                    f"Manager class {name!r} must not appear in factgraph.sdk.__all__",
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

    def test_entities_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().entities, "entities")

    def test_fields_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().fields, "fields")

    def test_assertions_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().assertions, "assertions")

    def test_rules_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().rules, "rules")

    def test_inferences_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().inferences, "inferences")

    def test_eval_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().eval, "eval")

    def test_audit_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().audit, "audit")

    def test_package_manager_read_only(self) -> None:
        self._assert_read_only(_new_fg().package, "package")

    def test_views_manager_read_only(self) -> None:
        """Per pre-publish audit Blocker 2: `views` is part of the 8
        top-level taxonomy and must enforce read-only attribute
        boundary uniformly with the other managers."""
        self._assert_read_only(_new_fg().views, "views")


class PropertyAccessorIdempotenceTests(unittest.TestCase):
    """Repeated property access returns the same manager instance.

    Managers are constructed once in `__init__` and held as private
    attributes; the property returns the held instance.
    """

    def test_schema_property_idempotent(self) -> None:
        fg = _new_fg()
        self.assertIs(fg.schema, fg.schema)


if __name__ == "__main__":
    unittest.main()
