"""Fault-injection characterization for the broad boundaries in application/ingest_runtime.

Both guarded sites turn an adapter failure (write planning over the schema
index/store, ledger or SQLite retraction) into a typed ``ErrorDTO`` item.  A
fault must never be reported as a written or skipped item, and the original
exception type/message must survive into the diagnostic.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factgraph.application import (
    apply_ingest_request,
    build_schema_index,
    ingest_runtime,
)
from factgraph.application.protocol import (
    EntitySelector,
    FieldPath,
    IngestRequest,
    IngestRetractItem,
    IngestSetItem,
)
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Post(Entity):
    slug: str = Identity()
    title: str = Field()


class _BoundaryFault(Exception):
    """Custom, non-domain failure injected at the planning / retraction boundary."""


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Post])
    return Store(schema_ir), build_schema_index(schema_ir)


def _set_request() -> IngestRequest:
    return IngestRequest(
        items=(
            IngestSetItem(
                target=EntitySelector(entity_type="Post", identity={"slug": "p1"}),
                field=FieldPath(entity_type="Post", field_name="title"),
                value="Hello",
            ),
        ),
    )


class IngestPlanBoundaryTests(unittest.TestCase):
    """src/factgraph/application/ingest_runtime.py: ``plan_write_command`` boundary."""

    def test_plan_fault_becomes_a_typed_item_error_and_writes_nothing(self) -> None:
        store, index = _build_store()
        before = len(list(store.ledger.find_claims()))

        with patch.object(
            ingest_runtime,
            "plan_write_command",
            side_effect=_BoundaryFault("injected plan failure detail"),
        ):
            result = apply_ingest_request(_set_request(), store=store, index=index)

        # Not reported as success: nothing written, nothing skipped as a no-op.
        self.assertEqual(list(result.written_assertion_ids), [])
        self.assertEqual(list(result.skipped_indices), [])
        self.assertEqual(len(list(store.ledger.find_claims())), before)

        self.assertEqual(len(result.errors), 1)
        error = result.errors[0]
        self.assertEqual(error.code, "INGEST_PLAN_FAILED")
        # Preserved detail: original message and exception class name.
        self.assertIn("injected plan failure detail", error.message)
        self.assertEqual(error.details.get("exception"), "_BoundaryFault")
        self.assertEqual(tuple(error.path), ("items", "0"))

    def test_plan_keyboard_interrupt_is_not_swallowed(self) -> None:
        store, index = _build_store()
        with (
            patch.object(ingest_runtime, "plan_write_command", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            apply_ingest_request(_set_request(), store=store, index=index)

    def test_happy_path_still_writes(self) -> None:
        store, index = _build_store()
        result = apply_ingest_request(_set_request(), store=store, index=index)
        self.assertEqual(result.errors, ())
        self.assertGreaterEqual(len(result.written_assertion_ids), 1)


class IngestRetractBoundaryTests(unittest.TestCase):
    """src/factgraph/application/ingest_runtime.py: ledger retraction boundary."""

    def _seed(self) -> tuple[Store, object, str]:
        store, index = _build_store()
        result = apply_ingest_request(_set_request(), store=store, index=index)
        return store, index, result.written_assertion_ids[-1]

    def test_retract_fault_becomes_a_typed_item_error_and_revokes_nothing(self) -> None:
        store, index, asrt_id = self._seed()

        with patch.object(
            ingest_runtime,
            "retract_by_asrt",
            side_effect=_BoundaryFault("injected retraction failure detail"),
        ):
            result = apply_ingest_request(
                IngestRequest(items=(IngestRetractItem(assertion_id=asrt_id),)),
                store=store,
                index=index,
            )

        # Not reported as success, and not silently degraded to a skipped no-op.
        self.assertEqual(list(result.written_assertion_ids), [])
        self.assertEqual(list(result.skipped_indices), [])
        self.assertIsNone(store.ledger.find_revoker(asrt_id))

        self.assertEqual(len(result.errors), 1)
        error = result.errors[0]
        self.assertEqual(error.code, "INGEST_RETRACT_FAILED")
        self.assertIn("injected retraction failure detail", error.message)
        self.assertEqual(error.details.get("exception"), "_BoundaryFault")
        self.assertEqual(error.details.get("assertion_id"), asrt_id)
        self.assertEqual(tuple(error.path), ("items", "0"))

    def test_retract_keyboard_interrupt_is_not_swallowed(self) -> None:
        store, index, asrt_id = self._seed()
        with (
            patch.object(ingest_runtime, "retract_by_asrt", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            apply_ingest_request(
                IngestRequest(items=(IngestRetractItem(assertion_id=asrt_id),)),
                store=store,
                index=index,
            )

    def test_happy_path_still_revokes(self) -> None:
        store, index, asrt_id = self._seed()
        result = apply_ingest_request(
            IngestRequest(items=(IngestRetractItem(assertion_id=asrt_id),)),
            store=store,
            index=index,
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(len(result.written_assertion_ids), 1)


if __name__ == "__main__":
    unittest.main()
