"""Canonical examples must reject missing/reordered arguments and retired APIs."""

import unittest
from pathlib import Path

from factgraph.sdk.errors import SDKStoreError
from tests.sdk.api_surface_examples import execute_namespace_map


class NamespaceExampleNegativeControls(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (Path(__file__).resolve().parents[2] / "src/factgraph/sdk/docs/04_api_surface.en.md").read_text()

    def test_missing_field_value_is_rejected(self) -> None:
        changed = self.text.replace("fg.fields.set(User.age, alice, 30)", "fg.fields.set(User.age, alice)")
        self.assertNotEqual(changed, self.text)
        with self.assertRaises(TypeError):
            execute_namespace_map(changed)

    def test_wrong_field_argument_order_is_rejected(self) -> None:
        changed = self.text.replace("fg.fields.set(User.age, alice, 30)", "fg.fields.set(alice, User.age, 30)")
        self.assertNotEqual(changed, self.text)
        with self.assertRaisesRegex(SDKStoreError, "requires a Field descriptor"):
            execute_namespace_map(changed)

    def test_retired_what_if_call_is_not_restored(self) -> None:
        changed = self.text.replace("fg.fields.set(User.age, alice, 30)", "fg.what_if.check(None, {})")
        self.assertNotEqual(changed, self.text)
        with self.assertRaisesRegex(AttributeError, "what_if"):
            execute_namespace_map(changed)

    def test_missing_example_cannot_pass_vacuously(self) -> None:
        with self.assertRaisesRegex(AssertionError, "complete executable example"):
            execute_namespace_map("## 0. Namespace Map\nNo example.\n---\n")
