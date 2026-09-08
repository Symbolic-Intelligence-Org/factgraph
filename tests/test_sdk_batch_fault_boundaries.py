"""Fault-injection characterization for the broad boundaries in factgraph.sdk.batch.

Two sites guard the schema/value lowering calls made while a staged batch is
translated into the application write-plan protocol:

* ``_first_unrepresentable_batch_op`` - turns a lowering failure into the typed
  reason string that the fail-closed ``SDKStoreError`` quotes.
* ``_application_write_value_for_op`` - a value that does not lower makes the
  delegated write command unavailable, so preview refuses to delegate.

Both must fail closed (no writes, no partial delegation) and must not swallow
KeyboardInterrupt.
"""

from __future__ import annotations

import unittest

from factgraph.sdk import (
    Database,
    Entity,
    FactGraph,
    Field,
    Identity,
    SDKStore,
    compile_schema_from_classes,
)
from factgraph.sdk.batch import BatchPlan, SetOp, _first_unrepresentable_batch_op
from factgraph.sdk.errors import SDKStoreError


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


class _BoundaryFault(Exception):
    """Custom, non-SDK failure raised from the injected lowering boundary."""


def _attached_sdk() -> tuple[Database, SDKStore]:
    db = Database.create(schema_ir=compile_schema_from_classes([Country, User]))
    return db, FactGraph.attach(db, schema_classes=[Country, User])


class FirstUnrepresentableBatchOpBoundaryTests(unittest.TestCase):
    """src/factgraph/sdk/batch.py: lowering boundary inside _first_unrepresentable_batch_op."""

    def _plan(self) -> BatchPlan:
        return BatchPlan(
            ops=[
                SetOp(
                    handle_id=1,
                    entity_type="User",
                    field_name="name",
                    field=User.name,
                    value_kind="scalar",
                    value="Alice",
                    meta={},
                    path="User#1.name",
                )
            ],
            warnings=[],
        )

    def test_lowering_failure_is_reported_as_a_typed_reason_preserving_detail(self) -> None:
        _db, sdk = _attached_sdk()
        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise _BoundaryFault("injected lowering failure detail")

        SDKStore._rest_terms_for_field = _boom
        try:
            path, reason = _first_unrepresentable_batch_op(self._plan(), sdk)
        finally:
            SDKStore._rest_terms_for_field = original

        # Typed outcome: a (path, reason) pair - never an exception escaping, and
        # never an empty reason that would read as "nothing wrong here".
        self.assertEqual(path, "User#1.name")
        self.assertIsInstance(reason, str)
        # Preserved detail: the original failure message survives into the reason.
        self.assertIn("injected lowering failure detail", reason)

    def test_lowering_keyboard_interrupt_is_not_swallowed(self) -> None:
        _db, sdk = _attached_sdk()
        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise KeyboardInterrupt

        SDKStore._rest_terms_for_field = _boom
        try:
            with self.assertRaises(KeyboardInterrupt):
                _first_unrepresentable_batch_op(self._plan(), sdk)
        finally:
            SDKStore._rest_terms_for_field = original


class ApplicationWriteValueBoundaryTests(unittest.TestCase):
    """src/factgraph/sdk/batch.py: lowering boundary inside _application_write_value_for_op."""

    def test_lowering_failure_refuses_delegation_and_commits_nothing(self) -> None:
        db, sdk = _attached_sdk()
        before = db.head()
        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise _BoundaryFault("injected lowering failure detail")

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            # Stage while lowering still works: staging itself fails closed earlier,
            # so the guard under test is the second-line defence during preview.
            user.name.set("Alice")
            SDKStore._rest_terms_for_field = _boom
            try:
                plan = tx.preview(objects=[user])
                # The delegated path is unavailable: no application handle order.
                self.assertFalse(plan._application_handle_order)
                # Fail-closed typed outcome, not a silent no-op success.
                with self.assertRaises(SDKStoreError) as ctx:
                    plan.apply(sdk)
            finally:
                SDKStore._rest_terms_for_field = original

        self.assertIn("no writes were committed", str(ctx.exception))
        self.assertIn("injected lowering failure detail", str(ctx.exception))
        # Nothing was committed: the database head did not advance.
        self.assertEqual(db.head().tx_seq, before.tx_seq)

    def test_lowering_keyboard_interrupt_during_preview_is_not_swallowed(self) -> None:
        _db, sdk = _attached_sdk()
        original = SDKStore._rest_terms_for_field

        def _boom(self, schema_pred, *, value):
            raise KeyboardInterrupt

        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            user.name.set("Alice")
            SDKStore._rest_terms_for_field = _boom
            try:
                with self.assertRaises(KeyboardInterrupt):
                    tx.preview(objects=[user])
            finally:
                SDKStore._rest_terms_for_field = original

    def test_happy_path_still_delegates_and_commits(self) -> None:
        db, sdk = _attached_sdk()
        before = db.head()
        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1")
            user.name.set("Alice")
            plan = tx.preview(objects=[user])
            self.assertTrue(plan._application_handle_order)
            result = plan.apply(sdk)
        self.assertTrue(result.assertion_ids)
        self.assertEqual(db.head().tx_seq, before.tx_seq + 1)


if __name__ == "__main__":
    unittest.main()
