from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from factgraph.adapters.problog.accept import persist_problog_annotations
from factgraph.adapters.pyreason.accept import persist_pyreason_annotations
from factgraph.adapters.souffle.package import _build_fact_rows
from factgraph.audit.meta_history import (
    effective_meta_at,
    export_meta_history,
    import_meta_history,
    read_meta_history,
)
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    DatabaseError,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    _MetaUnsetInput,
    resolve_database_workspace_paths,
)
from factgraph.core.mapping.canon import MappingResolveError, _required_meta_time
from factgraph.core.policy.chosen import choose_one
from factgraph.core.store.ledger import (
    AnnotationRow,
    Claim,
    Ledger,
    LedgerFormatError,
    MetaRow,
    _annotation_storage_key,
)
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    is_predicate_premise_excluded,
    is_predicate_premise_blocked,
    is_premise_excluded,
)
from factgraph.core.store.runtime import Store


_ASSERTION_ID = "asrt:11111111111111111111111111111111"
_REVOKER_ID = "asrt:22222222222222222222222222222222"


class Slice3bMetaEventSemanticsTests(unittest.TestCase):
    def test_system_managed_meta_cannot_be_appended_or_unset(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("ingested_at", "time", 200),),
                    ),
                )
            ).assertions[0]
            head = db.head()

            for item in (
                MetaAppendInput(assertion.asrt_id, "ingested_at", "time", 100),
                MetaAppendInput(assertion.asrt_id, "ingest_key", "str", "forged"),
                MetaAppendInput(
                    assertion.asrt_id,
                    "revoked_asrt_id",
                    "str",
                    "asrt:forged",
                ),
            ):
                with self.subTest(key=item.key), self.assertRaisesRegex(
                    DatabaseError,
                    "system-managed",
                ):
                    db.commit_changes(assertions=(), revocations=(), meta_appends=(item,))
                self.assertEqual(db.head(), head)

            with self.assertRaisesRegex(DatabaseError, "system-managed"):
                db._commit_meta_unsets((_MetaUnsetInput(assertion.asrt_id, "ingested_at"),))
            self.assertEqual(db.head(), head)
            db.close()

    def test_phase3_chosen_orders_by_later_commit_not_sample_time(self) -> None:
        later_sample_id = "asrt:33333333333333333333333333333333"
        earlier_sample_later_commit_id = "asrt:44444444444444444444444444444444"
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[later_sample_id, earlier_sample_later_commit_id],
        ):
            db = Database.create(schema_ir=_schema_ir())
            first = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "first")),
                        (MetaEntry("ingested_at", "time", 200),),
                    ),
                )
            ).assertions[0]
            second = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "second")),
                        (MetaEntry("ingested_at", "time", 100),),
                    ),
                )
            ).assertions[0]

            ledger = db._ledger_for_attach()
            self.assertGreater(
                ledger._claim_tx_refs[second.asrt_id],
                ledger._claim_tx_refs[first.asrt_id],
            )
            self.assertEqual(
                choose_one(ledger, [first.asrt_id, second.asrt_id]),
                second.asrt_id,
            )
            db.close()

    def test_mapping_canon_still_rejects_duplicate_ingested_at_history(self) -> None:
        ledger = Ledger()
        ledger.append_claim(
            Claim(
                asrt_id=_ASSERTION_ID,
                pred_id="person:name",
                e_ref="idref_v1:Person:alice",
                rest_terms=[("string", "Alice")],
            )
        )
        ledger.append_meta([MetaRow(_ASSERTION_ID, "ingested_at", "time", 100)])
        ledger.append_meta([MetaRow(_ASSERTION_ID, "ingested_at", "time", 200)])

        self.assertEqual(choose_one(ledger, [_ASSERTION_ID]), _ASSERTION_ID)
        with self.assertRaisesRegex(MappingResolveError, "exactly one ingested_at"):
            _required_meta_time(ledger, _ASSERTION_ID, "ingested_at")
        ledger.close()

    def test_managed_ledger_append_meta_routes_through_database_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            ledger = db._ledger_for_attach()
            before = db.head()

            with patch.object(
                ledger,
                "_next_direct_tx_seq",
                side_effect=AssertionError("managed append_meta reached the direct writer"),
            ):
                ledger.append_meta(
                    [MetaRow(assertion.asrt_id, "provenance_class", "str", "observed")]
                )

            after = db.head()
            self.assertEqual(after.tx_seq, before.tx_seq + 1)
            self.assertEqual(after.state_digest, before.state_digest)
            tx_object = json.loads(
                (
                    resolve_database_workspace_paths(workspace).tx_objects
                    / f"{after.tx_id.removeprefix('tx:')}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                tx_object["operations"],
                [
                    {
                        "asrt_id": assertion.asrt_id,
                        "kind": "append_meta",
                        "meta": {
                            "key": "provenance_class",
                            "kind": "str",
                            "value": "observed",
                        },
                    }
                ],
            )

            clean_head = db.head()
            with self.assertRaisesRegex(DatabaseError, "Database-reserved key"):
                ledger.append_meta(
                    [MetaRow(assertion.asrt_id, "assertion_digest", "str", "forged")]
                )
            self.assertEqual(db.head(), clean_head)
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            try:
                self.assertEqual(reopened.head(), after)
                self.assertEqual(
                    reopened._ledger_for_attach().find_meta(
                        asrt_id=assertion.asrt_id,
                        key="provenance_class",
                    )[-1].value,
                    "observed",
                )
            finally:
                reopened.close()

    def test_adapter_annotations_commit_hidden_m_ops_and_reload_symmetrically(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            ledger = db._ledger_for_attach()
            state_digest = db.head().state_digest

            problog_store = SimpleNamespace(
                _problog_pending_annotations={
                    "run-1": {
                        "candidate-1": [
                            {
                                "fact_index": 0,
                                "namespace": "problog",
                                "category": "semantic",
                                "key": "probability",
                                "kind": "float",
                                "value": 0.75,
                                "origin": "derived",
                                "derivation": "run-1",
                            }
                        ]
                    }
                }
            )
            accept_result = SimpleNamespace(
                candidate_id="candidate-1",
                written_assertions=[{"asrt_id": assertion.asrt_id}],
            )
            self.assertEqual(
                persist_problog_annotations(ledger, "run-1", problog_store, accept_result),
                1,
            )
            problog_head = db.head()
            self.assertEqual(problog_head.state_digest, state_digest)
            self.assertEqual(problog_head.tx_seq, 2)

            pyreason_store = SimpleNamespace(
                _engine_pending_annotations={
                    "run-2": [
                        {
                            "fact_index": 0,
                            "namespace": "pyreason",
                            "category": "semantic",
                            "key": "bound_lower",
                            "kind": "float",
                            "value": 0.5,
                            "origin": "derived",
                            "derivation": "run-2",
                        }
                    ]
                }
            )
            self.assertEqual(
                persist_pyreason_annotations(ledger, "run-2", pyreason_store, accept_result),
                1,
            )
            self.assertEqual(db.head().tx_seq, 3)
            live = ledger.find_annotations(asrt_id=assertion.asrt_id)
            self.assertEqual(
                [(row.namespace, row.key, row.value) for row in live],
                [("problog", "probability", 0.75), ("pyreason", "bound_lower", 0.5)],
            )

            paths = resolve_database_workspace_paths(workspace)
            problog_object = json.loads(
                (
                    paths.tx_objects
                    / f"{problog_head.tx_id.removeprefix('tx:')}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual([op["kind"] for op in problog_object["operations"]], ["append_meta"])
            self.assertTrue(
                problog_object["operations"][0]["meta"]["key"].startswith(
                    "__factgraph_annotation_v1__:"
                )
            )
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            try:
                cold = reopened._ledger_for_attach().find_annotations(asrt_id=assertion.asrt_id)
                self.assertEqual(cold, live)
            finally:
                reopened.close()

    def test_repeated_key_unset_as_of_and_cold_export_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            record = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("provenance_class", "str", "observed"),),
                    ),
                )
            ).assertions[0]
            first = db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(record.asrt_id, "provenance_class", "str", "agent"),
                ),
            )
            second = db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(record.asrt_id, "provenance_class", "str", "human"),
                ),
            )
            unset = db._commit_meta_unsets(
                (_MetaUnsetInput(record.asrt_id, "provenance_class"),)
            )

            ledger = db._ledger_for_attach()
            history = read_meta_history(
                ledger,
                asrt_id=record.asrt_id,
                key="provenance_class",
            )
            self.assertEqual(
                [(event.tx_seq, event.op_ordinal, event.kind, event.value) for event in history],
                [
                    (1, 0, "str", "observed"),
                    (first.value.tx_seq, 0, "str", "agent"),
                    (second.value.tx_seq, 0, "str", "human"),
                    (unset.value.tx_seq, 0, None, None),
                ],
            )
            self.assertEqual(
                ledger.effective_meta_rows(
                    asrt_id=record.asrt_id,
                    key="provenance_class",
                ),
                (),
            )
            self.assertEqual(
                effective_meta_at(
                    ledger,
                    asrt_id=record.asrt_id,
                    as_of=(second.value.tx_seq, 0),
                )["provenance_class"],
                "human",
            )
            before = export_meta_history(ledger, asrt_id=record.asrt_id)
            self.assertEqual(import_meta_history(before), read_meta_history(ledger, asrt_id=record.asrt_id))
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            try:
                cold = export_meta_history(
                    reopened._ledger_for_attach(),
                    asrt_id=record.asrt_id,
                )
                self.assertEqual(cold, before)
                self.assertEqual(import_meta_history(cold), import_meta_history(before))
            finally:
                reopened.close()

            tx_path = (
                resolve_database_workspace_paths(workspace).tx_objects
                / f"{unset.value.tx_id.removeprefix('tx:')}.json"
            )
            operation = json.loads(tx_path.read_text(encoding="utf-8"))["operations"][0]
            self.assertEqual(
                operation["meta"],
                {"key": "provenance_class", "kind": None, "value": None},
            )

    def test_unset_is_missing_for_exclusion_allowance_and_revoker(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID, _REVOKER_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("provenance_class", "str", "blocked"),),
                    ),
                )
            ).assertions[0]
            revoker = db.commit_changes(
                assertions=(),
                revocations=(
                    RevocationInput(
                        assertion.asrt_id,
                        (MetaEntry("provenance_class", "str", "blocked"),),
                    ),
                ),
            ).revocations[0]
            ledger = db._ledger_for_attach()
            exclusion = (MetaExclusion("provenance_class", frozenset({"blocked"})),)
            block = {
                "person:name": PredicatePremiseBlock(
                    "person:name",
                    "provenance_class",
                    frozenset({"blocked"}),
                )
            }
            self.assertTrue(is_premise_excluded(ledger, revoker.revoker_asrt_id, exclusion))
            self.assertTrue(is_predicate_premise_blocked(ledger, assertion.asrt_id, block))

            db._commit_meta_unsets(
                (
                    _MetaUnsetInput(assertion.asrt_id, "provenance_class"),
                    _MetaUnsetInput(revoker.revoker_asrt_id, "provenance_class"),
                )
            )
            self.assertFalse(is_premise_excluded(ledger, assertion.asrt_id, exclusion))
            self.assertFalse(is_premise_excluded(ledger, revoker.revoker_asrt_id, exclusion))
            self.assertFalse(is_predicate_premise_blocked(ledger, assertion.asrt_id, block))
            self.assertTrue(
                is_predicate_premise_excluded(
                    ledger,
                    assertion.asrt_id,
                    {
                        "person:name": PredicatePremiseAllowance(
                            "person:name",
                            "provenance_class",
                            frozenset({"observed"}),
                            absent_ok=False,
                        )
                    },
                )
            )
            self.assertFalse(
                is_predicate_premise_excluded(
                    ledger,
                    assertion.asrt_id,
                    {
                        "person:name": PredicatePremiseAllowance(
                            "person:name",
                            "provenance_class",
                            frozenset({"observed"}),
                            absent_ok=True,
                        )
                    },
                )
            )
            db.close()

    def test_souffle_fact_rows_include_only_effective_meta(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("source", "str", "old"),),
                    ),
                )
            ).assertions[0]
            db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(MetaAppendInput(assertion.asrt_id, "source", "str", "new"),),
            )
            store = Store(_schema_ir(), ledger=db._ledger_for_attach())

            meta_str_rows = _build_fact_rows(store)[2]
            self.assertEqual(
                [row for row in meta_str_rows if row[0] == assertion.asrt_id and row[1] == "source"],
                [[assertion.asrt_id, "source", "new"]],
            )

            db._commit_meta_unsets((_MetaUnsetInput(assertion.asrt_id, "source"),))
            meta_str_rows = _build_fact_rows(store)[2]
            self.assertEqual(
                [row for row in meta_str_rows if row[0] == assertion.asrt_id and row[1] == "source"],
                [],
            )
            db.close()

    def test_generic_meta_inputs_cannot_forge_dual_null_event(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            head = db.head()
            with self.assertRaisesRegex(DatabaseError, "unsupported meta kind"):
                db.commit_changes(
                    assertions=(),
                    revocations=(),
                    meta_appends=(MetaAppendInput(assertion.asrt_id, "source", None, None),),  # type: ignore[arg-type]
                )
            self.assertEqual(db.head(), head)

            ledger = db._ledger_for_attach()
            with self.assertRaisesRegex(ValueError, "unsupported meta kind"):
                ledger.append_meta(
                    [MetaRow(assertion.asrt_id, "source", None, None)]  # type: ignore[arg-type]
                )
            self.assertEqual(db.head(), head)
            db.close()

    def test_open_detects_each_append_meta_column_and_annotation_payload_tamper(self) -> None:
        cases = {
            "asrt_id": ("asrt_id", "asrt:99999999999999999999999999999999"),
            "key": ("key", "review_tampered"),
            "kind": ("kind", "json"),
            "value": ("value", "tampered"),
            "tx_seq": ("tx_seq", 99),
            "op_ordinal": ("op_ordinal", 99),
        }
        for name, (column, replacement) in cases.items():
            with self.subTest(column=name), tempfile.TemporaryDirectory() as raw_tmp:
                workspace = Path(raw_tmp) / "workspace"
                with patch(
                    "factgraph.core.store.database._new_assertion_id",
                    side_effect=[_ASSERTION_ID],
                ):
                    db = Database.create(workspace, schema_ir=_schema_ir())
                    assertion = db.commit_assertions(
                        (
                            AssertionInput(
                                "person:name",
                                (
                                    ("entity_ref", "idref_v1:Person:alice"),
                                    ("string", "Alice"),
                                ),
                            ),
                        )
                    ).assertions[0]
                    db.commit_changes(
                        assertions=(),
                        revocations=(),
                        meta_appends=(
                            MetaAppendInput(assertion.asrt_id, "review", "str", "clean"),
                        ),
                    )
                    db.close()
                _tamper_meta_column(workspace, "review", column, replacement)
                with self.assertRaises((DatabaseError, LedgerFormatError)):
                    Database.open(workspace, schema_ir=_schema_ir())

        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            row = AnnotationRow(
                assertion.asrt_id,
                "problog",
                "semantic",
                "probability",
                "float",
                0.75,
                "derived",
                "run-1",
            )
            db._ledger_for_attach().append_annotations([row])
            db.close()
            changed = AnnotationRow(
                assertion.asrt_id,
                "pyreason",
                "semantic",
                "probability",
                "float",
                0.75,
                "derived",
                "run-1",
            )
            _tamper_meta_column(
                workspace,
                _annotation_storage_key(row),
                "key",
                _annotation_storage_key(changed),
            )
            with self.assertRaises((DatabaseError, LedgerFormatError)):
                Database.open(workspace, schema_ir=_schema_ir())


def _schema_ir() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "person_id", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": "person:name",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            }
        ],
        "projection": {"entities": ["Person"], "predicates": ["person:name"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-08-02T00:00:00Z",
    }


def _tamper_meta_column(
    workspace: Path,
    key: str,
    column: str,
    replacement: object,
) -> None:
    path = resolve_database_workspace_paths(workspace).assertions
    connection = sqlite3.connect(path)
    try:
        cursor = connection.execute(
            f"UPDATE claim_meta SET {column} = ? WHERE key = ?",  # noqa: S608 - fixed test columns
            (replacement, key),
        )
        if cursor.rowcount != 1:
            raise AssertionError(f"expected one tamper target for {key!r}, got {cursor.rowcount}")
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
