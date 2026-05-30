from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKDSLError, SDKStore
from factgraph.sdk.errors import SDKError


class SDKErrorHierarchyTests(unittest.TestCase):
    def test_sdk_dsl_error_is_sdk_error_subclass(self) -> None:
        self.assertTrue(issubclass(SDKDSLError, SDKError))

    def test_sdk_dsl_error_caught_by_sdk_error(self) -> None:
        with self.assertRaises(SDKError) as ctx:
            raise SDKDSLError("dsl problem", code="X", path="$.test")
        exc = ctx.exception
        self.assertIsInstance(exc, SDKDSLError)
        self.assertEqual(str(exc), "dsl problem")
        self.assertEqual(exc.code, "X")
        self.assertEqual(exc.path, "$.test")


class _ReprUser(Entity):
    user_id: str = Identity()
    name: str = Field()


class SDKStoreReprTests(unittest.TestCase):
    def test_repr_starts_with_class_name(self) -> None:
        sdk = SDKStore([_ReprUser])
        text = repr(sdk)
        self.assertTrue(
            text.startswith("SDKStore("),
            f"unexpected repr: {text!r}",
        )

    def test_repr_includes_entity_count_and_schema_digest(self) -> None:
        sdk = SDKStore([_ReprUser])
        text = repr(sdk)
        self.assertIn("entities=1", text)
        self.assertIn("schema=", text)

    def test_repr_is_not_default_object_repr(self) -> None:
        sdk = SDKStore([_ReprUser])
        text = repr(sdk)
        self.assertFalse(text.startswith("<"))
        self.assertNotIn("object at 0x", text)


if __name__ == "__main__":
    unittest.main()
