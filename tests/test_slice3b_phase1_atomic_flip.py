from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.core.evidence.write_protocol import WriteProtocolError, set_field
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
    AnnotationRow,
    Claim,
    ClaimArg,
    Idempotency,
    LedgerAssertionWrite,
    Ledger,
    LedgerFormatError,
    MetaRow,
    Revokes,
)
from factgraph.core.store.premise_filter import MetaExclusion, premise_scoped_ledger
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


_IDS = (
    "asrt:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "asrt:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
)


class Inv15Person(Entity):
    person_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


class Slice3bAtomicFlipTests(unittest.TestCase):
    def test_initial_meta_contract_and_custom_companion_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            ledger = Ledger(path)

            late_id = "asrt:11111111111111111111111111111111"
            ledger.append_assertion(
                claim=Claim(late_id, "person:name", "idref_v1:Person:late", []),
                claim_args=[],
                meta_rows=[],
                asrt_id=late_id,
            )
            ledger.append_meta([MetaRow(late_id, "source", "str", "late-only")])
            self.assertEqual(ledger.find_annotations(asrt_id=late_id), [])

            initial_id = "asrt:22222222222222222222222222222222"
            custom = AnnotationRow(
                initial_id,
                "custom",
                "source",
                "source",
                "str",
                "initial-and-custom",
                "observed",
            )
            ledger.append_assertion(
                claim=Claim(initial_id, "person:name", "idref_v1:Person:initial", []),
                claim_args=[],
                meta_rows=[MetaRow(initial_id, "source", "str", "initial-and-custom")],
                annotation_rows=[custom],
                asrt_id=initial_id,
            )
            self.assertEqual(
                [row.namespace for row in ledger.find_annotations(asrt_id=initial_id)],
                ["shared", "custom"],
            )
            ledger.close()

            reopened = Ledger(path)
            self.assertEqual(reopened.find_annotations(asrt_id=late_id), [])
            self.assertEqual(
                [row.namespace for row in reopened.find_annotations(asrt_id=initial_id)],
                ["shared", "custom"],
            )
            reopened.close()

    def test_general_claim_write_paths_reject_system_predicates_before_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            ledger = Ledger(path)
            for index, pred_id in enumerate(
                ("__system__.revokes", "__system__.unsupported"),
                start=1,
            ):
                asrt_id = f"asrt:{index:032x}"
                claim = Claim(asrt_id, pred_id, "idref_v1:Person:alice", [])
                with self.subTest(path="append_assertion", pred_id=pred_id):
                    with self.assertRaisesRegex(ValueError, "reserved '__system__.'"):
                        ledger.append_assertion(
                            claim=claim,
                            claim_args=[],
                            meta_rows=[],
                            asrt_id=asrt_id,
                        )
                with self.subTest(path="append_claim", pred_id=pred_id):
                    with self.assertRaisesRegex(ValueError, "reserved '__system__.'"):
                        ledger.append_claim(claim)
                with self.subTest(path="commit_batch", pred_id=pred_id):
                    with self.assertRaisesRegex(ValueError, "reserved '__system__.'"):
                        ledger.commit_batch(
                            assertions=(
                                LedgerAssertionWrite(
                                    claim=claim,
                                    claim_args=(),
                                    meta_rows=(),
                                ),
                            ),
                            revocations=(),
                            expected_head_tx_id=None,
                            head_tx_id="tx:rejected-before-cas",
                            metadata={"head_tx_seq": "0"},
                        )
                with self.subTest(path="write_protocol.set_field", pred_id=pred_id):
                    with self.assertRaisesRegex(WriteProtocolError, "reserved '__system__.'"):
                        set_field(ledger, pred_id, "idref_v1:Person:alice", [])

            self.assertEqual(ledger.find_claims(), [])
            self.assertIsNone(ledger.get_ledger_meta("head_tx_id"))
            ledger.close()

            reopened = Ledger(path)
            self.assertEqual(reopened.find_claims(), [])
            self.assertEqual(reopened.revokes, [])
            self.assertIsNone(reopened.get_ledger_meta("head_tx_id"))
            reopened.close()

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
                self.assertEqual(
                    [row[1] for row in conn.execute("PRAGMA table_info(claims)")],
                    [
                        "seq",
                        "asrt_id",
                        "pred_id",
                        "e_ref",
                        "rest_terms",
                        "value",
                        "value_tag",
                        "tx_ref",
                    ],
                )
                rows = conn.execute(
                    "SELECT asrt_id, pred_id, rest_terms, value, value_tag, tx_ref "
                    "FROM claims ORDER BY seq"
                ).fetchall()
                self.assertEqual(
                    rows,
                    [
                        (
                            _IDS[0],
                            "person:name",
                            "[]",
                            "Alice",
                            "string",
                            asserted.value.tx_seq,
                        ),
                        (
                            _IDS[1],
                            "__system__.revokes",
                            "[]",
                            _IDS[0],
                            "string",
                            revoked.value.tx_seq,
                        ),
                    ],
                )

    def test_legacy_nary_claim_uses_rest_terms_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            ledger = Ledger(path)
            asrt_id = "asrt:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            terms = [("entity_ref", "idref_v1:Person:bob"), ("string", "0.9")]
            ledger.append_assertion(
                claim=Claim(asrt_id, "person:edge", "idref_v1:Person:alice", terms),
                claim_args=[
                    ClaimArg(asrt_id, 0, "idref_v1:Person:bob", "entity_ref"),
                    ClaimArg(asrt_id, 1, "0.9", "string"),
                ],
                meta_rows=[],
                asrt_id=asrt_id,
            )
            self.assertEqual(ledger.get_claim(asrt_id).rest_terms, terms)
            ledger.close()

            with sqlite3.connect(path) as conn:
                row = conn.execute(
                    "SELECT rest_terms, value, value_tag FROM claims WHERE asrt_id = ?",
                    (asrt_id,),
                ).fetchone()
                self.assertEqual(
                    row,
                    ('[["entity_ref","idref_v1:Person:bob"],["string","0.9"]]', None, None),
                )

            reopened = Ledger(path)
            self.assertEqual(reopened.get_claim(asrt_id).rest_terms, terms)
            self.assertEqual(
                [(row.idx, row.val_atom, row.tag) for row in reopened.find_claim_args(asrt_id)],
                [
                    (0, "idref_v1:Person:bob", "entity_ref"),
                    (1, "0.9", "string"),
                ],
            )
            reopened.close()

    def test_append_assertion_rejects_claim_args_drift_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            ledger = Ledger(path)
            asrt_id = "asrt:edededededededededededededededed"
            with self.assertRaisesRegex(ValueError, "exactly match claim.rest_terms"):
                ledger.append_assertion(
                    claim=Claim(
                        asrt_id,
                        "person:edge",
                        "idref_v1:Person:alice",
                        [("entity_ref", "idref_v1:Person:bob")],
                    ),
                    claim_args=[],
                    meta_rows=[],
                    asrt_id=asrt_id,
                )
            self.assertIsNone(ledger.get_claim(asrt_id))
            ledger.close()

            reopened = Ledger(path)
            self.assertIsNone(reopened.get_claim(asrt_id))
            reopened.close()

    def test_idempotency_is_materialized_and_survives_reload(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "ledger.db"
            assertion_key = "import:assertion:1"
            revocation_key = "import:revocation:1"
            target_id = "asrt:abababababababababababababababab"
            revoker_id = "asrt:cdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"

            ledger = Ledger(path)
            first = ledger.append_assertion(
                claim=Claim(target_id, "person:name", "idref_v1:Person:alice", []),
                claim_args=[],
                meta_rows=[],
                idempotency=Idempotency(assertion_key),
                asrt_id=target_id,
            )
            self.assertTrue(first.written)
            self.assertEqual(
                [(row.kind, row.value) for row in ledger.find_meta(target_id, "ingest_key")],
                [("str", assertion_key)],
            )
            duplicate = ledger.append_assertion(
                claim=Claim("", "person:name", "idref_v1:Person:alice", []),
                claim_args=[],
                meta_rows=[],
                idempotency=Idempotency(assertion_key),
            )
            self.assertEqual(duplicate.asrt_id, target_id)
            self.assertFalse(duplicate.written)
            ledger.close()

            reopened = Ledger(path)
            duplicate_after_reload = reopened.append_assertion(
                claim=Claim("", "person:name", "idref_v1:Person:alice", []),
                claim_args=[],
                meta_rows=[],
                idempotency=Idempotency(assertion_key),
            )
            self.assertEqual(duplicate_after_reload.asrt_id, target_id)
            self.assertFalse(duplicate_after_reload.written)
            revocation = reopened.append_revocation(
                revokes=Revokes(revoker_id, target_id),
                meta_rows=[],
                idempotency=Idempotency(revocation_key),
                revoker_asrt_id=revoker_id,
            )
            self.assertTrue(revocation.written)
            reopened.close()

            reopened = Ledger(path)
            duplicate_revoke = reopened.append_revocation(
                revokes=Revokes("asrt:efefefefefefefefefefefefefefefef", target_id),
                meta_rows=[],
                idempotency=Idempotency(revocation_key),
            )
            self.assertEqual(duplicate_revoke.asrt_id, revoker_id)
            self.assertFalse(duplicate_revoke.written)
            reopened.close()

    def test_inv15_system_revocation_is_hidden_except_exact_id_audit_lookup(self) -> None:
        fg = FactGraph.create(schema_classes=[Inv15Person])
        e_ref = fg.entities.create(Inv15Person, person_id="alice")
        name_id = fg.fields.set(Inv15Person.name, e_ref, "Alice")
        revoker_id = fg.assertions.retract(name_id)
        self.assertIsInstance(revoker_id, str)
        assert revoker_id is not None

        ledger = fg._store.ledger
        system_claim = ledger._get_claim_including_system(revoker_id)
        self.assertIsNotNone(system_claim)
        assert system_claim is not None
        self.assertEqual(system_claim.pred_id, "__system__.revokes")

        # Ledger's five logical read families remain byte-compatible with the
        # old separate-revokes shape: system Claims are not factual Claims.
        self.assertIsNone(ledger.get_claim(revoker_id))
        self.assertNotIn(revoker_id, [row.asrt_id for row in ledger.claims])
        self.assertNotIn(revoker_id, [row.asrt_id for row in ledger.find_claims()])
        self.assertNotIn(revoker_id, [row.asrt_id for row in ledger.claim_args])
        scoped = premise_scoped_ledger(
            ledger,
            MetaExclusion("provenance_class", frozenset({"never"})),
        )
        self.assertNotIn(revoker_id, [row.asrt_id for row in scoped.claims])
        projected = project_view_facts_with_witness(ledger, fg.schema_ir)
        self.assertNotIn(revoker_id, repr(projected))

        # SDK canonical scans filter, while exact-id audit/replay bypasses.
        self.assertNotIn(revoker_id, [row.asrt_id for row in fg.assertions.all])
        self.assertNotIn(revoker_id, [row.asrt_id for row in fg.assertions.active])
        self.assertNotIn(
            revoker_id,
            [row.asrt_id for row in fg.assertions.where(e_ref=e_ref)],
        )
        self.assertNotIn(
            revoker_id,
            [row.asrt_id for row in fg.assertions.field(Inv15Person.name).all],
        )
        self.assertEqual(fg.fields.get(Inv15Person.name, e_ref), None)
        self.assertEqual(len(tuple(fg.entities.where(Inv15Person))), 1)
        self.assertTrue(fg.entities.exists(Inv15Person, person_id="alice"))

        audit_record = fg.assertions.by_id(revoker_id)
        self.assertIsNotNone(audit_record)
        self.assertEqual(audit_record.pred_id, "__system__.revokes")
        self.assertEqual(
            [row.asrt_id for row in fg.assertions.by_ids((revoker_id,))],
            [revoker_id],
        )
        with self.assertRaisesRegex(SDKStoreError, "revoke-of-revoke.*ADR-SYS-B"):
            fg.assertions.retract(revoker_id)
        database = fg._database
        self.assertIsNotNone(database)
        assert database is not None
        head_before = database.head()
        with self.assertRaisesRegex(DatabaseError, "revoke-of-revoke is forbidden"):
            database.commit_changes(
                assertions=(),
                revocations=(RevocationInput(revoker_id),),
            )
        self.assertEqual(database.head(), head_before)

    def test_ingest_table_retirement_preserves_set_and_adds_multiset_semantics(self) -> None:
        fg = FactGraph.create(schema_classes=[Inv15Person])
        e_ref = fg.entities.create(Inv15Person, person_id="alice")
        first = fg.fields.set(Inv15Person.name, e_ref, "Alice")
        repeated = fg.fields.set(Inv15Person.name, e_ref, "Alice")
        self.assertEqual(first, repeated)

        add_one = fg.fields.add(Inv15Person.tags, e_ref, "vip")
        add_two = fg.fields.add(Inv15Person.tags, e_ref, "vip")
        self.assertNotEqual(add_one, add_two)
        self.assertEqual(fg.fields.get(Inv15Person.tags, e_ref), ("vip", "vip"))

    def test_shared_annotation_is_one_physical_meta_event(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            committed = db.commit_changes(
                assertions=(
                    AssertionInput(
                        "person:name",
                        (
                            ("entity_ref", "idref_v1:Person:alice"),
                            ("string", "Alice"),
                        ),
                        (MetaEntry("source", "str", "single-physical-event"),),
                    ),
                ),
                revocations=(),
            )
            asrt_id = committed.assertions[0].asrt_id
            annotations = db._ledger_for_attach().find_annotations(
                asrt_id=asrt_id,
                key="source",
            )
            self.assertEqual([row.value for row in annotations], ["single-physical-event"])
            db.close()

            paths = resolve_database_workspace_paths(workspace)
            with sqlite3.connect(paths.assertions) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM claim_meta WHERE asrt_id = ? AND key = 'source'",
                        (asrt_id,),
                    ).fetchone()[0],
                    1,
                )

    def test_claim_meta_event_index_matches_physical_rows_before_and_after_reopen(self) -> None:
        benchmark_path = (
            Path(__file__).resolve().parents[1] / "benchmarks" / "slice3b_storage_baseline.py"
        )
        spec = importlib.util.spec_from_file_location("slice3b_storage_baseline", benchmark_path)
        assert spec is not None and spec.loader is not None
        benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benchmark)

        with tempfile.TemporaryDirectory() as raw_tmp:
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            committed = db.commit_changes(
                assertions=(_assertion("Alice"),),
                revocations=(),
            )
            asrt_id = committed.assertions[0].asrt_id
            db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(MetaAppendInput(asrt_id, "review", "str", "approved"),),
            )
            ledger = db._ledger_for_attach()
            live_events = tuple(ledger._claim_meta_events)
            storage = benchmark._storage_snapshot(workspace)
            self.assertEqual(set(storage["physical_meta_rows"]), {"claim_meta"})
            self.assertEqual(
                storage["physical_meta_rows"]["claim_meta"],
                len(live_events),
            )
            workset = benchmark._workset_snapshot(ledger, claim_count=1)
            self.assertEqual(
                workset["resident_claim_meta_event_objects"],
                len(live_events),
            )
            self.assertGreaterEqual(
                workset["resident_meta_bearing_row_objects"],
                workset["resident_claim_meta_event_objects"],
            )
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            self.assertEqual(
                tuple(reopened._ledger_for_attach()._claim_meta_events),
                live_events,
            )
            reopened.close()

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
