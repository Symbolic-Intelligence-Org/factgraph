"""Fault-injection characterization for the broad boundaries in factgraph.sdk.ingest.

Both guarded sites turn a schema/lowering failure into a typed ingest diagnostic.
These tests inject a custom exception subclass at each site and pin the exact
typed outcome: the item is rejected (never silently written), the original
failure detail survives in the diagnostic message, and KeyboardInterrupt is not
swallowed.
"""

from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.errors import SDKStoreError


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag: list[str] = Field()
    lives_in: Country = Field()


class _BoundaryFault(Exception):
    """Custom, non-SDK failure raised from the injected schema/lowering boundary."""


def _build_sdk() -> SDKStore:
    return SDKStore([Country, User])


def _item(sdk: SDKStore, e_ref: str) -> dict:
    return {"kind": "set", "field": User.name, "e_ref": e_ref, "value": "Alice"}


class IngestSchemaPredBoundaryTests(unittest.TestCase):
    """src/factgraph/sdk/ingest.py: sdk._schema_pred_for_field(...) boundary."""

    def test_schema_pred_failure_becomes_typed_diagnostic_and_writes_nothing(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")
        before = len(list(sdk.ledger.find_claims(e_ref=user_ref)))

        def _boom(field):
            raise _BoundaryFault("injected schema pred failure detail")

        original = SDKStore._schema_pred_for_field
        SDKStore._schema_pred_for_field = lambda self, field: _boom(field)
        try:
            result = sdk.schema.ingest([_item(sdk, user_ref)])
        finally:
            SDKStore._schema_pred_for_field = original

        # Not reported as success: no assertions written, ledger untouched.
        self.assertEqual(list(result.written_assertion_ids), [])
        self.assertEqual(len(list(sdk.ledger.find_claims(e_ref=user_ref))), before)

        errors = [d for d in result.diagnostics if d.get("severity") == "error"]
        codes = {d.get("code") for d in errors}
        self.assertIn("ingest_item_field_invalid", codes)

        # Preserved detail: the original exception message survives into the diagnostic.
        detail = next(d for d in errors if d.get("code") == "ingest_item_field_invalid")
        self.assertIn("injected schema pred failure detail", str(detail.get("message")))
        self.assertTrue(str(detail.get("path", "")).endswith(".field"))

    def test_schema_pred_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")

        def _boom(field):
            raise KeyboardInterrupt

        original = SDKStore._schema_pred_for_field
        SDKStore._schema_pred_for_field = lambda self, field: _boom(field)
        try:
            with self.assertRaises(KeyboardInterrupt):
                sdk.schema.ingest([_item(sdk, user_ref)])
        finally:
            SDKStore._schema_pred_for_field = original

    def test_native_sdk_store_error_still_becomes_the_same_diagnostic(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")

        original = SDKStore._schema_pred_for_field

        def _boom(self, field):
            raise SDKStoreError("native lowering rejection")

        SDKStore._schema_pred_for_field = _boom
        try:
            result = sdk.schema.ingest([_item(sdk, user_ref)])
        finally:
            SDKStore._schema_pred_for_field = original

        self.assertEqual(list(result.written_assertion_ids), [])
        codes = {d.get("code") for d in result.diagnostics if d.get("severity") == "error"}
        self.assertIn("ingest_item_field_invalid", codes)


class IngestRestTermsBoundaryTests(unittest.TestCase):
    """src/factgraph/sdk/ingest.py: sdk._rest_terms_for_field(...) boundary."""

    def test_value_lowering_failure_becomes_typed_diagnostic_and_writes_nothing(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")
        before = len(list(sdk.ledger.find_claims(e_ref=user_ref)))

        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise _BoundaryFault("injected value lowering failure detail")

        SDKStore._rest_terms_for_field = _boom
        try:
            result = sdk.schema.ingest([_item(sdk, user_ref)])
        finally:
            SDKStore._rest_terms_for_field = original

        self.assertEqual(list(result.written_assertion_ids), [])
        self.assertEqual(len(list(sdk.ledger.find_claims(e_ref=user_ref))), before)

        errors = [d for d in result.diagnostics if d.get("severity") == "error"]
        codes = {d.get("code") for d in errors}
        self.assertIn("ingest_item_field_value_invalid", codes)

        detail = next(d for d in errors if d.get("code") == "ingest_item_field_value_invalid")
        self.assertIn("injected value lowering failure detail", str(detail.get("message")))
        self.assertTrue(str(detail.get("path", "")).endswith(".value"))

    def test_value_lowering_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")

        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise KeyboardInterrupt

        SDKStore._rest_terms_for_field = _boom
        try:
            with self.assertRaises(KeyboardInterrupt):
                sdk.schema.ingest([_item(sdk, user_ref)])
        finally:
            SDKStore._rest_terms_for_field = original

    def test_happy_path_still_writes_the_item(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.entities.create(User, user_id="u-1")
        result = sdk.schema.ingest([_item(sdk, user_ref)])
        self.assertEqual(len(result.written_assertion_ids), 1)


if __name__ == "__main__":
    unittest.main()
