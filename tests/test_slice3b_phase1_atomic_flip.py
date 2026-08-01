from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.core.store.database import (
    AssertionInput,
    Database,
    DatabaseError,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import (
    Claim,
    Ledger,
    LedgerFormatError,
    MetaRow,
    Revokes,
)


_IDS = (
    "asrt:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "asrt:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
)


class Slice3bAtomicFlipTests(unittest.TestCase):
    def test_new_workspace_has_exact_three_table_shape_and_tx_refs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=_IDS,
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            asserted = db.commit_changes(
                assertions=(_assertion("Alice"),),
                revocations=(),
            )
            revoked = db.commit_changes(
                assertions=(),
                revocations=(RevocationInput(_IDS[0]),),
            )
            self.assertEqual(asserted.assertions[0].asrt_id, _IDS[0])
            self.assertEqual(revoked.revocations[0].revoker_asrt_id, _IDS[1])
            db.close()

            paths = resolve_database_workspace_paths(workspace)
            with sqlite3.connect(paths.assertions) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
                self.assertEqual(tables, {"claims", "claim_meta", "ledger_meta"})
                self.assertEqual(
                    [row[1] for row in conn.execute("PRAGMA table_info(claim_meta)")],
                    ["asrt_id", "key", "kind", "value", "tx_seq", "op_ordinal"],
                )
                rows = conn.execute(
                    "SELECT asrt_id, pred_id, tx_ref FROM claims ORDER BY seq"
                ).fetchall()
                self.assertEqual(
                    rows,
                    [
                        (_IDS[0], "person:name", asserted.value.tx_seq),
                        (_IDS[1], "__system__.revokes", revoked.value.tx_seq),
                    ],
                )

    def test_initial_meta_repeated_key_is_rejected_without_advancing_head(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            db = Database.create(Path(raw_tmp) / "workspace", schema_ir=_schema_ir())
            before = db.head()
            duplicate = (
                MetaEntry("source", "str", "first"),
                MetaEntry("source", "str", "second"),
            )
            with self.assertRaisesRegex(DatabaseError, "initial meta keys must be unique"):
                db.commit_changes(
                    assertions=(
                        AssertionInput(
                            "person:name",
                            (
                                ("entity_ref", "idref_v1:Person:alice"),
                                ("string", "Alice"),
                            ),
                            duplicate,
                        ),
                    ),
                    revocations=(),
                )
            self.assertEqual(db.head(), before)

            created = db.commit_changes(assertions=(_assertion("Alice"),), revocations=())
            before_revoke = db.head()
            with self.assertRaisesRegex(DatabaseError, "initial meta keys must be unique"):
                db.commit_changes(
                    assertions=(),
                    revocations=(RevocationInput(created.assertions[0].asrt_id, duplicate),),
                )
            self.assertEqual(db.head(), before_revoke)

            db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(created.assertions[0].asrt_id, "review", "str", "one"),
                    MetaAppendInput(created.assertions[0].asrt_id, "review", "str", "two"),
                ),
            )
            self.assertEqual(
                [row.value for row in db._ledger_for_attach().find_meta(
                    asrt_id=created.assertions[0].asrt_id,
                    key="review",
                )],
                ["one", "two"],
            )
            db.close()

    def test_direct_ledger_initial_meta_guards_match_database_boundary(self) -> None:
        ledger = Ledger()
        target = "asrt:cccccccccccccccccccccccccccccccc"
        duplicate = [
            MetaRow(target, "source", "str", "one"),
            MetaRow(target, "source", "str", "two"),
        ]
        with self.assertRaisesRegex(ValueError, "initial meta keys must be unique"):
            ledger.append_assertion(
                claim=Claim(target, "person:name", "idref_v1:Person:alice", []),
                claim_args=[],
                meta_rows=duplicate,
                asrt_id=target,
            )
        ledger.append_assertion(
            claim=Claim(target, "person:name", "idref_v1:Person:alice", []),
            claim_args=[],
            meta_rows=[],
            asrt_id=target,
        )
        revoker = "asrt:dddddddddddddddddddddddddddddddd"
        with self.assertRaisesRegex(ValueError, "initial meta keys must be unique"):
            ledger.append_revocation(
                revokes=Revokes(revoker, target),
                meta_rows=[
                    MetaRow(revoker, "reason", "str", "one"),
                    MetaRow(revoker, "reason", "str", "two"),
                ],
                revoker_asrt_id=revoker,
            )
        ledger.close()

    def test_claim_meta_kind_value_nullability_is_symmetric(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            ledger = Ledger(path)
            ledger.close()
            with sqlite3.connect(path) as conn:
                conn.execute(
                    "INSERT INTO claim_meta "
                    "(asrt_id, key, kind, value, tx_seq, op_ordinal) "
                    "VALUES ('asrt:tombstone', 'k', NULL, NULL, 0, 0)"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO claim_meta VALUES "
                        "('asrt:bad-kind', 'k', NULL, 'value', 0, 0)"
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO claim_meta VALUES "
                        "('asrt:bad-value', 'k', 'str', NULL, 0, 0)"
                    )

    def test_seven_table_workspace_is_rejected_with_recovery_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "legacy.db"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE claims (seq INTEGER PRIMARY KEY, rest_terms TEXT)")
                conn.execute("CREATE TABLE meta_rows (id INTEGER PRIMARY KEY)")
            with self.assertRaisesRegex(
                LedgerFormatError,
                "seven-table v0.3.*rebuild.*migrate-workspace",
            ):
                Ledger(path)

            workspace = Path(raw_tmp) / "workspace"
            database = Database.create(workspace, schema_ir=_schema_ir())
            database.close()
            paths = resolve_database_workspace_paths(workspace)
            with sqlite3.connect(paths.assertions) as conn:
                conn.execute("CREATE TABLE meta_rows (id INTEGER PRIMARY KEY)")
            with self.assertRaisesRegex(
                LedgerFormatError,
                "seven-table v0.3.*rebuild.*migrate-workspace",
            ):
                Database.open(workspace, schema_ir=_schema_ir())


def _assertion(name: str) -> AssertionInput:
    return AssertionInput(
        "person:name",
        (
            ("entity_ref", "idref_v1:Person:alice"),
            ("string", name),
        ),
        (MetaEntry("source", "str", "slice3b-phase1"),),
    )


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
        "generated_at": "2026-08-01T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
