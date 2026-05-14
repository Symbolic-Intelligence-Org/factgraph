from __future__ import annotations

import unittest

from factgraph.application import (
    IngestRuntimeError,
    apply_ingest_request,
    build_schema_index,
)
from factgraph.application.protocol import (
    EntitySelector,
    FieldPath,
    IngestAddItem,
    IngestRequest,
    IngestResult,
    IngestRetractItem,
    IngestSetItem,
    ProtocolShapeError,
)
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Tag(Entity):
    label: str = Identity(primary_key=True)


class Post(Entity):
    slug: str = Identity(primary_key=True)
    title: str = Field(cardinality="single")
    tag: Tag = Field(cardinality="multi")


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Tag, Post])
    return Store(schema_ir), build_schema_index(schema_ir)


class IngestDTOValidationTests(unittest.TestCase):
    def test_set_item_requires_entity_type_match(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            IngestSetItem(
                target=EntitySelector(entity_type="Post", identity={"slug": "p1"}),
                field=FieldPath(entity_type="Tag", field_name="label"),
                value="hello",
            )

    def test_add_item_requires_field_path_instance(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            IngestAddItem(
                target=EntitySelector(entity_type="Post", identity={"slug": "p1"}),
                field="not-a-field-path",  # type: ignore[arg-type]
                value="hello",
            )

    def test_retract_item_requires_assertion_id(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            IngestRetractItem(assertion_id="")

    def test_request_rejects_unknown_item_type(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            IngestRequest(items=("not-an-item",))  # type: ignore[arg-type]

    def test_request_collect_mode_literal(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            IngestRequest(items=(), collect_mode="loose")  # type: ignore[arg-type]


class ApplyIngestSmokeTests(unittest.TestCase):
    def test_set_item_writes_assertion(self) -> None:
        store, index = _build_store()
        request = IngestRequest(
            items=(
                IngestSetItem(
                    target=EntitySelector(entity_type="Post", identity={"slug": "p1"}),
                    field=FieldPath(entity_type="Post", field_name="title"),
                    value="Hello",
                ),
            ),
        )
        result = apply_ingest_request(request, store=store, index=index)
        self.assertIsInstance(result, IngestResult)
        self.assertEqual(result.errors, ())
        # create_if_missing=True so the new entity also writes exists + identity predicates;
        # we just assert at least the title write succeeded.
        self.assertGreaterEqual(len(result.written_assertion_ids), 1)
        self.assertTrue(all(result.written_assertion_ids))

    def test_collect_mode_stop_aborts_on_first_error(self) -> None:
        store, index = _build_store()
        bad_target = EntitySelector(entity_type="Post", identity={"missing": "?"})
        good_target = EntitySelector(entity_type="Post", identity={"slug": "p2"})
        request = IngestRequest(
            items=(
                IngestSetItem(
                    target=bad_target,
                    field=FieldPath(entity_type="Post", field_name="title"),
                    value="Bad",
                ),
                IngestSetItem(
                    target=good_target,
                    field=FieldPath(entity_type="Post", field_name="title"),
                    value="Good",
                ),
            ),
            collect_mode="stop",
        )
        result = apply_ingest_request(request, store=store, index=index)
        self.assertGreaterEqual(len(result.errors), 1)
        self.assertEqual(len(result.written_assertion_ids), 0)

    def test_retract_unknown_assertion_records_skip_or_error(self) -> None:
        store, index = _build_store()
        request = IngestRequest(
            items=(IngestRetractItem(assertion_id="unknown-asrt-id"),),
            collect_mode="collect",
        )
        result = apply_ingest_request(request, store=store, index=index)
        # Either an explicit error recorded, or skipped no-op; never silent success.
        self.assertEqual(len(result.written_assertion_ids), 0)
        self.assertTrue(len(result.errors) > 0 or len(result.skipped_indices) > 0)


class IngestRuntimeErrorTests(unittest.TestCase):
    def test_to_error_dto_round_trip(self) -> None:
        err = IngestRuntimeError(
            "boom",
            code="INGEST_PLAN_FAILED",
            path=("items", "0"),
            details={"hint": "x"},
        )
        dto = err.to_error_dto()
        self.assertEqual(dto.code, "INGEST_PLAN_FAILED")
        self.assertEqual(dto.path, ("items", "0"))


if __name__ == "__main__":
    unittest.main()
