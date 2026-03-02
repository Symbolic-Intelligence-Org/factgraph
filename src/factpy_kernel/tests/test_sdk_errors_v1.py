from __future__ import annotations

import unittest

from factpy_kernel.sdk import (
    CardinalityError,
    EditorClosedError,
    EntityNotFoundError,
    QUERY_MISSING_REF,
    SDKStoreError,
)


class SDKErrorsV1Tests(unittest.TestCase):
    def test_sdk_store_error_supports_optional_code_and_path(self) -> None:
        err = SDKStoreError("missing ref", code=QUERY_MISSING_REF, path="$.query.where")
        self.assertEqual(str(err), "missing ref")
        self.assertEqual(err.code, QUERY_MISSING_REF)
        self.assertEqual(err.path, "$.query.where")

    def test_sdk_store_error_without_code_is_allowed(self) -> None:
        err = SDKStoreError("plain message")
        self.assertEqual(str(err), "plain message")
        self.assertIsNone(err.code)
        self.assertIsNone(err.path)

    def test_str_does_not_include_code(self) -> None:
        err = SDKStoreError("oops", code=QUERY_MISSING_REF)
        self.assertEqual(str(err), "oops")
        self.assertNotIn("QUERY_MISSING_REF", str(err))

    def test_structured_subclasses_support_explicit_fields(self) -> None:
        not_found = EntityNotFoundError(
            "entity not found",
            entity_type="Person",
            identity_kwargs={"source_id": "u1"},
            code=QUERY_MISSING_REF,
            path="$.query.head",
        )
        self.assertEqual(str(not_found), "entity not found")
        self.assertEqual(not_found.entity_type, "Person")
        self.assertEqual(not_found.identity_kwargs, {"source_id": "u1"})
        self.assertEqual(not_found.code, QUERY_MISSING_REF)
        self.assertEqual(not_found.path, "$.query.head")

        card = CardinalityError(
            "cardinality mismatch",
            field_name="country",
            actual_cardinality="multi",
            operation="set",
            code="CARDINALITY_MISMATCH",
            path="$.edit.country",
        )
        self.assertEqual(str(card), "cardinality mismatch")
        self.assertEqual(card.field_name, "country")
        self.assertEqual(card.actual_cardinality, "multi")
        self.assertEqual(card.operation, "set")
        self.assertEqual(card.code, "CARDINALITY_MISMATCH")
        self.assertEqual(card.path, "$.edit.country")

        closed = EditorClosedError("editor is closed")
        self.assertEqual(str(closed), "editor is closed")
        self.assertIsNone(closed.code)
        self.assertIsNone(closed.path)


if __name__ == "__main__":
    unittest.main()
