from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from factgraph.core.schema.meta_policy import MetaKeyPolicy
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    MetaAppendInput,
    MetaEntry,
    _MetaUnsetInput,
)
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class _LazyMetaEntity(Entity):
    entity_id: str = Identity()


def _schema_ir(*, lazy: bool) -> dict:
    return compile_schema_from_classes(
        [_LazyMetaEntity],
        meta_keys=(
            {
                "source": MetaKeyPolicy(),
                "trace_id": MetaKeyPolicy(
                    reader_class="audit",
                    load_policy="lazy",
                    storage_scope="tx_liftable",
                ),
            }
            if lazy
            else None
        ),
    )


def _assertion() -> AssertionInput:
    return AssertionInput(
        "_lazy_meta_entity:entity_id",
        (
            ("entity_ref", "idref_v1:_LazyMetaEntity:one"),
            ("string", "one"),
        ),
        meta=(
            MetaEntry("source", "str", "observed"),
            MetaEntry("trace_id", "str", "trace-initial"),
        ),
    )


def _benchmark_module():
    path = Path(__file__).resolve().parents[1] / "benchmarks" / "slice3b_storage_baseline.py"
    spec = importlib.util.spec_from_file_location("slice3b_storage_baseline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LazyMetaProjectionTests(unittest.TestCase):
    def test_lazy_meta_is_read_on_demand_without_eager_index_residency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            database = Database.create(workspace, schema_ir=_schema_ir(lazy=True))
            record = database.commit_assertions((_assertion(),)).assertions[0]
            ledger = database._ledger_for_attach()

            self.assertEqual(ledger._lazy_meta_keys, frozenset({"trace_id"}))
            lazy_meta_rows = ledger.meta_rows
            lazy_annotation_rows = ledger.annotation_rows
            ledger.configure_meta_load_policy(())
            self.assertEqual(ledger.meta_rows, lazy_meta_rows)
            self.assertEqual(ledger.annotation_rows, lazy_annotation_rows)
            ledger.configure_meta_load_policy(("trace_id",))
            self.assertFalse(any(row.key == "trace_id" for row in ledger._claim_meta_events))
            self.assertFalse(any(row.key == "trace_id" for row in ledger._meta_rows_data))
            self.assertFalse(any(row.key == "trace_id" for row in ledger._annotation_rows_data))
            self.assertEqual(
                [row.value for row in ledger.find_meta(asrt_id=record.asrt_id, key="trace_id")],
                ["trace-initial"],
            )
            self.assertEqual(
                [
                    (row.namespace, row.category, row.value)
                    for row in ledger.find_annotations(
                        asrt_id=record.asrt_id,
                        key="trace_id",
                    )
                ],
                [("shared", "source", "trace-initial")],
            )

            database.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(record.asrt_id, "trace_id", "str", "trace-later"),
                ),
            )
            self.assertEqual(
                [
                    row.value
                    for row in ledger.effective_meta_rows(
                        asrt_id=record.asrt_id,
                        key="trace_id",
                    )
                ],
                ["trace-later"],
            )
            self.assertEqual(
                [row.value for row in ledger.find_annotations(key="trace_id")],
                ["trace-initial"],
            )
            database._commit_meta_unsets(
                (_MetaUnsetInput(record.asrt_id, "trace_id"),)
            )
            self.assertEqual(
                ledger.effective_meta_rows(
                    asrt_id=record.asrt_id,
                    key="trace_id",
                ),
                (),
            )
            history_before = ledger.meta_history_events(
                asrt_id=record.asrt_id,
                key="trace_id",
            )
            projected_meta_before = ledger.meta_rows
            projected_annotations_before = ledger.annotation_rows
            database.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir(lazy=True))
            try:
                cold = reopened._ledger_for_attach()
                self.assertEqual(
                    cold.meta_history_events(
                        asrt_id=record.asrt_id,
                        key="trace_id",
                    ),
                    history_before,
                )
                self.assertEqual(cold.meta_rows, projected_meta_before)
                self.assertEqual(cold.annotation_rows, projected_annotations_before)
                self.assertFalse(
                    any(row.key == "trace_id" for row in cold._claim_meta_events)
                )
            finally:
                reopened.close()

    def test_schema_without_lazy_declarations_preserves_phase2_eager_indexes(self) -> None:
        database = Database.create(schema_ir=_schema_ir(lazy=False))
        try:
            record = database.commit_assertions((_assertion(),)).assertions[0]
            ledger = database._ledger_for_attach()
            self.assertEqual(ledger._lazy_meta_keys, frozenset())
            self.assertTrue(any(row.key == "trace_id" for row in ledger._claim_meta_events))
            self.assertTrue(any(row.key == "trace_id" for row in ledger._meta_rows_data))
            self.assertEqual(
                [row.value for row in ledger.find_meta(asrt_id=record.asrt_id, key="trace_id")],
                ["trace-initial"],
            )
        finally:
            database.close()

    def test_baseline_workset_reports_lazy_rows_as_projected_not_resident(self) -> None:
        benchmark = _benchmark_module()
        database = Database.create(schema_ir=benchmark._schema_ir())
        try:
            committed = database.commit_changes(
                assertions=(
                    benchmark._assertion(
                        0,
                        batch_time=1,
                        entity_count=1,
                    ),
                ),
                revocations=(),
                meta_defaults=benchmark._batch_meta_defaults(0),
            )
            self.assertEqual(len(committed.assertions), 1)
            workset = benchmark._workset_snapshot(
                database._ledger_for_attach(),
                claim_count=1,
            )
            self.assertEqual(
                workset["configured_lazy_meta_keys"],
                ["request_id", "trace_id"],
            )
            self.assertEqual(workset["projected_lazy_meta_rows"], 0)
            self.assertEqual(workset["effective_lazy_meta_rows"], 2)
            self.assertEqual(workset["resident_lazy_meta_event_objects"], 0)
            self.assertEqual(workset["resident_tx_default_objects"], 2)
            self.assertLess(
                workset["resident_claim_meta_event_objects"],
                workset["effective_ledger_meta_rows"],
            )
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
