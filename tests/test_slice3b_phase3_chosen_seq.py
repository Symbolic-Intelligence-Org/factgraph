from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.adapters.souffle.package import _build_fact_rows
from factgraph.core.policy.chosen import choose_one
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    MetaEntry,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import LedgerFormatError, _enc, _enc_rest_terms
from factgraph.core.store.runtime import Store


_FIRST_ID = "asrt:11111111111111111111111111111111"
_SECOND_ID = "asrt:ffffffffffffffffffffffffffffffff"


class ChosenByClaimSequenceTests(unittest.TestCase):
    def test_equal_sample_time_chooses_later_sequence_not_lexical_id(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_FIRST_ID, _SECOND_ID],
        ):
            database = Database.create(schema_ir=_schema_ir())
            try:
                first = database.commit_assertions((_assertion("first", 100),)).assertions[0]
                second = database.commit_assertions((_assertion("second", 100),)).assertions[0]
                ledger = database._ledger_for_attach()
                self.assertLess(
                    ledger.claim_sequence(first.asrt_id),
                    ledger.claim_sequence(second.asrt_id),
                )
                self.assertEqual(
                    choose_one(ledger, [second.asrt_id, first.asrt_id]),
                    second.asrt_id,
                )
                claim_seq_rows = _build_fact_rows(Store(_schema_ir(), ledger=ledger))[8]
                self.assertEqual(
                    claim_seq_rows,
                    [
                        [first.asrt_id, str(ledger.claim_sequence(first.asrt_id))],
                        [second.asrt_id, str(ledger.claim_sequence(second.asrt_id))],
                    ],
                )
            finally:
                database.close()

    def test_v02_import_order_is_the_chosen_order_even_when_event_time_is_inverted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "legacy.db"
            target = root / "workspace"
            first_id = "1" * 32
            second_id = "f" * 32
            _write_v02_fixture(source, first_id=first_id, second_id=second_id)

            Database.migrate_legacy_ledger(
                source_ledger_path=source,
                target_workspace=target,
                schema_ir=_schema_ir(),
            )
            database = Database.open(target, schema_ir=_schema_ir())
            try:
                ledger = database._ledger_for_attach()
                self.assertEqual(choose_one(ledger, [first_id, second_id]), second_id)
                self.assertLess(
                    ledger.claim_sequence(first_id),
                    ledger.claim_sequence(second_id),
                )
            finally:
                database.close()

    def test_seq_tamper_that_reverses_tx_order_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_FIRST_ID, _SECOND_ID],
        ):
            workspace = Path(raw) / "workspace"
            database = Database.create(workspace, schema_ir=_schema_ir())
            database.commit_assertions((_assertion("first", 200),))
            database.commit_assertions((_assertion("second", 100),))
            ledger_path = resolve_database_workspace_paths(workspace).assertions
            database.close()

            with sqlite3.connect(ledger_path) as conn:
                first_seq = conn.execute(
                    "SELECT seq FROM claims WHERE asrt_id = ?", (_FIRST_ID,)
                ).fetchone()[0]
                second_seq = conn.execute(
                    "SELECT seq FROM claims WHERE asrt_id = ?", (_SECOND_ID,)
                ).fetchone()[0]
                conn.execute("UPDATE claims SET seq = -1 WHERE asrt_id = ?", (_FIRST_ID,))
                conn.execute(
                    "UPDATE claims SET seq = ? WHERE asrt_id = ?",
                    (first_seq, _SECOND_ID),
                )
                conn.execute(
                    "UPDATE claims SET seq = ? WHERE asrt_id = ?",
                    (second_seq, _FIRST_ID),
                )

            with self.assertRaisesRegex(
                LedgerFormatError,
                "claims.seq order disagrees with committed tx_ref order",
            ):
                Database.open(workspace, schema_ir=_schema_ir())


def _assertion(value: str, ingested_at: int) -> AssertionInput:
    return AssertionInput(
        "person:name",
        (
            ("entity_ref", "idref_v1:Person:alice"),
            ("string", value),
        ),
        (MetaEntry("ingested_at", "time", ingested_at),),
    )


def _write_v02_fixture(path: Path, *, first_id: str, second_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE claims (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                asrt_id TEXT NOT NULL UNIQUE,
                pred_id TEXT NOT NULL,
                e_ref TEXT NOT NULL,
                rest_terms TEXT NOT NULL
            );
            CREATE TABLE claim_args (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asrt_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                val_atom TEXT NOT NULL,
                tag TEXT NOT NULL
            );
            CREATE TABLE meta_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asrt_id TEXT NOT NULL,
                key TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL
            );
            CREATE TABLE revokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revoker_asrt_id TEXT NOT NULL,
                revoked_asrt_id TEXT NOT NULL
            );
            CREATE TABLE ingest_keys (
                ingest_key TEXT PRIMARY KEY,
                asrt_id TEXT NOT NULL,
                kind TEXT NOT NULL
            );
            CREATE TABLE ledger_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE annotation_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asrt_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                origin TEXT NOT NULL,
                derivation TEXT,
                UNIQUE(asrt_id, namespace, category, key)
            );
            """
        )
        for asrt_id, value, ingested_at in (
            (first_id, "first", 200),
            (second_id, "second", 100),
        ):
            conn.execute(
                "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) "
                "VALUES (?, 'person:name', 'idref_v1:Person:alice', ?)",
                (asrt_id, _enc_rest_terms([("string", value)])),
            )
            conn.execute(
                "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) "
                "VALUES (?, 0, ?, 'string')",
                (asrt_id, _enc(value)),
            )
            conn.execute(
                "INSERT INTO meta_rows (asrt_id, key, kind, value) "
                "VALUES (?, 'ingested_at', 'time', ?)",
                (asrt_id, _enc(ingested_at)),
            )


def _schema_ir() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "person_id", "type_domain": "string"}
                ],
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
                "cardinality": "single",
            }
        ],
        "projection": {"entities": ["Person"], "predicates": ["person:name"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-08-03T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
