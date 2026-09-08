from __future__ import annotations

import json
import multiprocessing
import os
import random
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.core.protocol.lthash import (
    LtHashError,
    add as lthash_add,
    decode_state,
    empty_state,
    encode_state,
    from_elements,
    remove as lthash_remove,
)
from factgraph.core.store.database import (
    AssertionInput,
    AssertionRecord,
    Database,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseLockedError,
    HeadConflictError,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    SchemaTransitionInput,
    _atomic_write_bytes,
    assertion_digest_for,
    resolve_database_workspace_paths,
)
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.store.ledger import Claim, ClaimArg, Ledger, MetaRow


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
        "generated_at": "2026-07-31T00:00:00Z",
    }


def _assertion(person_id: str, name: str) -> AssertionInput:
    return AssertionInput(
        pred_id="person:name",
        fact_tuple=(
            ("entity_ref", f"idref_v1:Person:{person_id}"),
            ("string", name),
        ),
    )


def _oracle_state_digest(assertions: dict[str, str]) -> str:
    def _field(value: str) -> bytes:
        encoded = value.encode("utf-8")
        return len(encoded).to_bytes(4, "big") + encoded

    prefix = b"factgraph\x00dbstate_element_v2\x00"
    elements = (
        prefix + _field(asrt_id) + _field(assertion_digest)
        for asrt_id, assertion_digest in sorted(assertions.items())
    )
    return encode_state(from_elements(elements))


def _try_open_worker(path: str, schema_ir: dict, queue: multiprocessing.Queue) -> None:
    try:
        db = Database.open(path, schema_ir=schema_ir)
    except Exception as exc:  # pragma: no cover - assertion occurs in parent process
        queue.put((type(exc).__name__, str(exc)))
        return
    db.close()
    queue.put(("opened", ""))


def _crash_mid_commit_worker(path: str, schema_ir: dict) -> None:
    db = Database.open(path, schema_ir=schema_ir)

    def _kill_during_sqlite_transaction(*args: object, **kwargs: object) -> None:
        os._exit(91)

    db._ledger._insert_meta_rows = _kill_during_sqlite_transaction  # type: ignore[method-assign]
    db.commit_assertions((_assertion("crash", "Crash"),))


class LtHashProtocolTests(unittest.TestCase):
    def test_state_encoding_is_canonical_and_add_remove_are_inverse(self) -> None:
        element = b"asrt:" + b"1" * 32
        state = lthash_add(empty_state(), element)

        self.assertEqual(decode_state(encode_state(state)), state)
        self.assertEqual(lthash_remove(state, element), empty_state())
        self.assertEqual(
            from_elements((element, b"asrt:" + b"2" * 32)),
            from_elements((b"asrt:" + b"2" * 32, element)),
        )

        with self.assertRaises(LtHashError):
            from_elements((element, element))
        with self.assertRaises(LtHashError):
            decode_state(encode_state(state) + "=")


class StorageHardeningPhase1Tests(unittest.TestCase):
    def assert_state_matches_full_recompute(self, db: Database) -> None:
        active_assertions = {
            claim.asrt_id: db._ledger.find_meta(
                asrt_id=claim.asrt_id,
                key="assertion_digest",
                kind="str",
            )[0].value
            for claim in db._ledger.find_claims()
            if not claim.pred_id.startswith("__system__.")
            and not db._ledger.has_active_revocation(claim.asrt_id)
        }
        self.assertEqual(db.head().state_digest, _oracle_state_digest(active_assertions))

    def test_incremental_state_matches_full_recompute_through_revoke_and_reassert(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        self.assert_state_matches_full_recompute(db)

        first = db.commit_assertions((_assertion("p1", "Ada"),)).assertions[0]
        db.commit_assertions((_assertion("p2", "Grace"),))
        self.assert_state_matches_full_recompute(db)

        revoked = db.commit_changes(
            assertions=(),
            revocations=(RevocationInput(first.asrt_id),),
        )
        self.assert_state_matches_full_recompute(db)

        reasserted = db.commit_assertions((_assertion("p1", "Ada"),)).assertions[0]
        self.assertNotEqual(reasserted.asrt_id, first.asrt_id)
        self.assert_state_matches_full_recompute(db)

        with self.assertRaisesRegex(Exception, "revoke-of-revoke"):
            db.commit_changes(
                assertions=(),
                revocations=(RevocationInput(revoked.revocations[0].revoker_asrt_id),),
            )

    def test_seeded_random_sequences_match_independent_state_oracle(self) -> None:
        rng = random.Random(0x5A17A)
        db = Database.create(schema_ir=_schema_ir())
        active: dict[str, str] = {}

        for step in range(200):
            if active and rng.random() < 0.45:
                target = rng.choice(sorted(active))
                db.commit_changes(
                    assertions=(),
                    revocations=(RevocationInput(target),),
                )
                del active[target]
            else:
                value = rng.randrange(17)
                committed = db.commit_assertions(
                    (_assertion(f"p-{step}", f"name-{value}"),)
                ).assertions[0]
                active[committed.asrt_id] = committed.assertion_digest
            self.assertEqual(db.head().state_digest, _oracle_state_digest(active))

    def test_system_namespace_guards_use_exact_inv13_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            reserved = AssertionInput(
                pred_id="__system__.user-forbidden",
                fact_tuple=(("entity_ref", "idref_v1:Person:p1"), ("string", "x")),
            )
            with self.assertRaisesRegex(DatabaseError, "reserved '__system__.'"):
                db.commit_assertions((reserved,))

            # INV-13 reserves the dotted namespace, not arbitrary names that
            # merely begin with the characters "__system__".
            allowed = AssertionInput(
                pred_id="__system__user_predicate",
                fact_tuple=(("entity_ref", "idref_v1:Person:p2"), ("string", "y")),
            )
            committed = db.commit_assertions((allowed,))
            self.assert_state_matches_full_recompute(db)
            db.close()

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), committed.value)
            reopened.close()

    def test_same_batch_revocation_guard_checks_added_system_claim(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        asrt_id = "asrt:" + "a" * 32
        system_record = AssertionRecord(
            asrt_id=asrt_id,
            pred_id="__system__.internal",
            fact_tuple=(("entity_ref", "idref_v1:Person:p1"), ("string", "x")),
            schema_digest=db.schema_digest,
            assertion_digest="sha256:" + "b" * 64,
            tx_id="tx:" + "c" * 64,
            meta=(),
        )
        with self.assertRaisesRegex(DatabaseError, "system claims cannot be revoked"):
            db._prepare_revocations(
                (RevocationInput(asrt_id),),
                added_assertions={asrt_id: system_record},
            )

    def test_tx_object_commits_ordered_delta_and_digest_scheme_not_full_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            committed = db.commit_assertions((_assertion("p1", "Ada"),))
            paths = resolve_database_workspace_paths(path)
            tx_path = paths.tx_objects / f"{committed.value.tx_id.removeprefix('tx:')}.json"
            payload = json.loads(tx_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["digest_scheme"], "lthash16-v2")
            self.assertEqual(payload["tx_seq"], 1)
            self.assertNotIn("state_digest", payload)
            self.assertNotIn("data_digest", payload)
            self.assertEqual(
                payload["operations"],
                [
                    {
                        "kind": "assertion",
                        "asrt_id": committed.assertions[0].asrt_id,
                        "assertion_digest": committed.assertions[0].assertion_digest,
                    }
                ],
            )

            revoked = db.commit_changes(
                assertions=(),
                revocations=(
                    RevocationInput(
                        committed.assertions[0].asrt_id,
                        meta=(MetaEntry("reason", "str", "test"),),
                    ),
                ),
            )
            revoke_path = paths.tx_objects / f"{revoked.value.tx_id.removeprefix('tx:')}.json"
            revoke_payload = json.loads(revoke_path.read_text(encoding="utf-8"))
            self.assertEqual(revoke_payload["operations"][0]["kind"], "revocation")
            self.assertEqual(
                revoke_payload["operations"][0]["revoked_asrt_id"],
                committed.assertions[0].asrt_id,
            )
            self.assertEqual(
                revoke_payload["operations"][0]["meta"],
                [{"key": "reason", "kind": "str", "value": "test"}],
            )

    def test_append_meta_is_an_ordered_history_event_without_state_digest_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            assertion = db.commit_assertions((_assertion("p1", "Ada"),)).assertions[0]
            before = db.head()

            committed = db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(assertion.asrt_id, "provenance_class", "str", "observed"),
                    MetaAppendInput(assertion.asrt_id, "provenance_class", "str", "accredited"),
                ),
            )

            self.assertEqual(committed.value.tx_seq, before.tx_seq + 1)
            self.assertEqual(committed.value.state_digest, before.state_digest)
            self.assertEqual(
                [row.value for row in db._ledger.find_meta(
                    asrt_id=assertion.asrt_id,
                    key="provenance_class",
                )],
                ["observed", "accredited"],
            )
            paths = resolve_database_workspace_paths(path)
            tx_path = paths.tx_objects / f"{committed.value.tx_id.removeprefix('tx:')}.json"
            payload = json.loads(tx_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["operations"],
                [
                    {
                        "asrt_id": assertion.asrt_id,
                        "kind": "append_meta",
                        "meta": {
                            "key": "provenance_class",
                            "kind": "str",
                            "value": "observed",
                        },
                    },
                    {
                        "asrt_id": assertion.asrt_id,
                        "kind": "append_meta",
                        "meta": {
                            "key": "provenance_class",
                            "kind": "str",
                            "value": "accredited",
                        },
                    },
                ],
            )
            db.close()

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), committed.value)
            reopened.close()

    def test_schema_change_commits_digest_pair_and_requires_both_schema_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            old_schema = _schema_ir()
            new_schema = json.loads(json.dumps(old_schema))
            new_schema["predicates"].append(
                {
                    "pred_id": "person:status",
                    "arg_specs": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "status", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                }
            )
            new_schema["projection"]["predicates"].append("person:status")

            db = Database.create(path, schema_ir=old_schema)
            before = db.head()
            committed = db.commit_changes(
                assertions=(),
                revocations=(),
                schema_transition=SchemaTransitionInput(
                    old_schema_digest=before.schema_digest,
                    new_schema_ir=new_schema,
                ),
            )

            self.assertNotEqual(committed.value.schema_digest, before.schema_digest)
            self.assertEqual(committed.value.state_digest, before.state_digest)
            self.assertEqual(db.schema_digest, committed.value.schema_digest)
            paths = resolve_database_workspace_paths(path)
            tx_path = paths.tx_objects / f"{committed.value.tx_id.removeprefix('tx:')}.json"
            payload = json.loads(tx_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["operations"],
                [
                    {
                        "kind": "schema_change",
                        "old_schema_digest": before.schema_digest,
                        "new_schema_digest": committed.value.schema_digest,
                    }
                ],
            )
            db.close()

            reopened = Database.open(path, schema_ir=new_schema)
            self.assertEqual(reopened.head(), committed.value)
            reopened.close()

            old_schema_path = (
                paths.schema_objects / f"{before.schema_digest.removeprefix('sha256:')}.json"
            )
            old_schema_path.unlink()
            with self.assertRaisesRegex(DatabaseIntegrityError, "schema object missing"):
                Database.open(path, schema_ir=new_schema)

    def test_schema_change_rejects_mixed_or_stale_transitions_without_advancing_head(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        before = db.head()
        new_schema = json.loads(json.dumps(_schema_ir()))
        new_schema["projection"]["entities"].append("Other")

        with self.assertRaisesRegex(DatabaseError, "isolated"):
            db.commit_changes(
                assertions=(_assertion("p1", "Ada"),),
                revocations=(),
                schema_transition=SchemaTransitionInput(before.schema_digest, new_schema),
            )
        with self.assertRaisesRegex(DatabaseError, "old_schema_digest"):
            db.commit_changes(
                assertions=(),
                revocations=(),
                schema_transition=SchemaTransitionInput("sha256:" + "f" * 64, new_schema),
            )
        self.assertEqual(db.head(), before)

    def test_content_tampering_fails_closed_even_when_assertion_id_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            committed = db.commit_assertions((_assertion("p1", "Alice"),))
            original_state = committed.value.state_digest
            asrt_id = committed.assertions[0].asrt_id
            db.close()

            paths = resolve_database_workspace_paths(path)
            with sqlite3.connect(paths.assertions) as conn:
                stored = conn.execute(
                    "SELECT value FROM claims WHERE asrt_id = ?",
                    (asrt_id,),
                ).fetchone()[0]
                self.assertIn("Alice", stored)
                conn.execute(
                    "UPDATE claims SET value = ? WHERE asrt_id = ?",
                    (stored.replace("Alice", "Mallory"), asrt_id),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT value FROM ledger_meta WHERE key = 'head_state_digest'"
                    ).fetchone()[0],
                    original_state,
                )

            with self.assertRaisesRegex(DatabaseIntegrityError, "assertion_digest"):
                Database.open(path, schema_ir=_schema_ir())

    def test_legacy_ledger_write_mode_is_rejected_with_migration_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy_path = Path(tmp) / "legacy.db"
            ledger = Ledger(legacy_path)
            with self.assertRaisesRegex(DatabaseError, "python -m factgraph migrate-workspace"):
                Database(
                    ledger=ledger,
                    db_id="db:legacy",
                    schema_digest=schema_digest(_schema_ir()),
                )
            ledger.close()

            with self.assertRaisesRegex(DatabaseError, "python -m factgraph migrate-workspace"):
                Database.open(legacy_path, schema_ir=_schema_ir())

            workspace = Path(tmp) / "v0.2-layout"
            current = Database.create(workspace, schema_ir=_schema_ir())
            current.close()
            paths = resolve_database_workspace_paths(workspace)
            with sqlite3.connect(paths.assertions) as conn:
                conn.execute(
                    "UPDATE ledger_meta SET value = 'lthash16-v1' WHERE key = 'digest_scheme'"
                )
            with self.assertRaisesRegex(DatabaseError, "explicit format migration"):
                Database.open(workspace, schema_ir=_schema_ir())
            with self.assertRaisesRegex(DatabaseError, "explicit format migration"):
                Database.repair(workspace, schema_ir=_schema_ir())

    def test_object_and_directory_fsync_failures_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch(
                    "factgraph.core.store.database.os.fsync",
                    side_effect=OSError("injected file fsync failure"),
                ),
                self.assertRaisesRegex(DatabaseError, "fsync failed for object file"),
            ):
                _atomic_write_bytes(root / "file-fsync.json", b"{}")

            with (
                patch(
                    "factgraph.core.store.database.os.fsync",
                    side_effect=(None, OSError("injected directory fsync failure")),
                ),
                self.assertRaisesRegex(DatabaseError, "directory fsync failed"),
            ):
                _atomic_write_bytes(root / "directory-fsync.json", b"{}")

    def test_different_histories_with_same_terminal_set_have_distinct_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            original = Database.create(base, schema_ir=_schema_ir())
            original.commit_assertions((_assertion("stable", "Stable"),))
            original.close()

            left_path = root / "left"
            right_path = root / "right"
            shutil.copytree(base, left_path)
            shutil.copytree(base, right_path)

            left = Database.open(left_path, schema_ir=_schema_ir())
            left_transient = left.commit_assertions((_assertion("left", "Transient L"),))
            left_final = left.commit_changes(
                assertions=(),
                revocations=(RevocationInput(left_transient.assertions[0].asrt_id),),
            ).value
            left.close()

            right = Database.open(right_path, schema_ir=_schema_ir())
            right_transient = right.commit_assertions((_assertion("right", "Transient R"),))
            right_final = right.commit_changes(
                assertions=(),
                revocations=(RevocationInput(right_transient.assertions[0].asrt_id),),
            ).value
            right.close()

            self.assertEqual(left_final.state_digest, right_final.state_digest)
            self.assertNotEqual(left_final.tx_id, right_final.tx_id)

            reopened_left = Database.open(left_path, schema_ir=_schema_ir())
            self.assertEqual(reopened_left.head(), left_final)
            reopened_left.close()
            reopened_right = Database.open(right_path, schema_ir=_schema_ir())
            self.assertEqual(reopened_right.head(), right_final)
            reopened_right.close()

    def test_batch_failure_rolls_back_facts_and_head_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            before = db.head()

            with (
                patch.object(
                    db._ledger,
                    "_insert_meta_rows",
                    side_effect=RuntimeError("injected transaction failure"),
                ),
                self.assertRaisesRegex(RuntimeError, "injected transaction failure"),
            ):
                db.commit_assertions((_assertion("p1", "Ada"),))

            self.assertEqual(db.head(), before)
            self.assertEqual(db._ledger.find_claims(), [])
            db.close()

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), before)
            reopened.close()

    def test_process_kill_inside_transaction_recovers_previous_valid_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            before = db.head()
            db.close()

            context = multiprocessing.get_context("spawn")
            process = context.Process(
                target=_crash_mid_commit_worker,
                args=(str(path), _schema_ir()),
            )
            process.start()
            process.join(15)
            self.assertEqual(process.exitcode, 91)

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), before)
            self.assertEqual(reopened._ledger.find_claims(), [])
            reopened.close()

    def test_open_fails_closed_on_drift_and_explicit_repair_records_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            db.commit_assertions((_assertion("p1", "Ada"),))
            before_repair = db.head()
            db.close()

            rogue_id = "asrt:" + "f" * 32
            paths = resolve_database_workspace_paths(path)
            rogue_fact = (
                ("entity_ref", "idref_v1:Person:rogue"),
                ("string", "Rogue"),
            )
            rogue_user_meta = (MetaEntry("source", "str", "repair-drift"),)
            rogue_digest = assertion_digest_for(
                pred_id="person:name",
                fact_tuple=rogue_fact,
                schema_digest=schema_digest(_schema_ir()),
                meta=rogue_user_meta,
            )
            drift_ledger = Ledger(paths.assertions)
            drift_ledger.append_assertion(
                claim=Claim(
                    asrt_id=rogue_id,
                    pred_id="person:name",
                    e_ref=rogue_fact[0][1],
                    rest_terms=[rogue_fact[1]],
                ),
                claim_args=[
                    ClaimArg(
                        asrt_id=rogue_id,
                        idx=0,
                        val_atom=rogue_fact[1][1],
                        tag=rogue_fact[1][0],
                    )
                ],
                meta_rows=[
                    *(MetaRow(rogue_id, row.key, row.kind, row.value) for row in rogue_user_meta),
                    MetaRow(rogue_id, "schema_digest", "str", schema_digest(_schema_ir())),
                    MetaRow(rogue_id, "assertion_digest", "str", rogue_digest),
                    MetaRow(rogue_id, "tx_id", "str", before_repair.tx_id),
                ],
                asrt_id=rogue_id,
            )
            drift_ledger.close()

            with self.assertRaisesRegex(DatabaseIntegrityError, "terminal set"):
                Database.open(path, schema_ir=_schema_ir())

            repaired = Database.repair(
                path,
                schema_ir=_schema_ir(),
                reason="phase1-test-injected-ledger-drift",
            )
            self.assertEqual(repaired.head().tx_seq, before_repair.tx_seq + 1)
            self.assertIsNotNone(repaired._ledger.get_claim(rogue_id))
            physical_position = (
                repaired._ledger._claim_tx_refs[rogue_id],
                repaired._ledger._claim_op_ordinals[rogue_id],
            )
            repair_meta = repaired._ledger.get_ledger_meta("last_repair")
            self.assertIsNotNone(repair_meta)
            self.assertIn("phase1-test-injected-ledger-drift", repair_meta or "")
            repaired.close()

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assert_state_matches_full_recompute(reopened)
            reopened.close()

            with sqlite3.connect(paths.assertions) as conn:
                conn.execute(
                    "INSERT INTO claim_meta "
                    "(asrt_id, key, kind, value, tx_seq, op_ordinal) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        rogue_id,
                        "origin_binding",
                        "str",
                        "forged-after-tx-marker",
                        *physical_position,
                    ),
                )

            with self.assertRaisesRegex(
                DatabaseIntegrityError,
                "claim_meta 'assertion_digest' disagrees",
            ):
                Database.open(path, schema_ir=_schema_ir())

    def test_workspace_flock_rejects_second_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            owner = Database.create(path, schema_ir=_schema_ir())
            context = multiprocessing.get_context("spawn")
            queue = context.Queue()
            process = context.Process(
                target=_try_open_worker,
                args=(str(path), _schema_ir(), queue),
            )
            process.start()
            process.join(15)
            self.assertEqual(process.exitcode, 0)
            error_type, message = queue.get(timeout=5)
            self.assertEqual(error_type, DatabaseLockedError.__name__)
            self.assertIn("already open for writing", message)

            owner.close()
            reopened = Database.open(path, schema_ir=_schema_ir())
            reopened.close()

    def test_concurrent_commits_from_same_parent_have_one_cas_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            original_head = db.head
            barrier = threading.Barrier(2)
            outcomes: list[object] = []
            outcomes_lock = threading.Lock()

            def synchronized_head():
                value = original_head()
                barrier.wait(timeout=5)
                return value

            def commit(person_id: str) -> None:
                try:
                    outcome: object = db.commit_assertions(
                        (_assertion(person_id, person_id.title()),)
                    )
                except Exception as exc:
                    outcome = exc
                with outcomes_lock:
                    outcomes.append(outcome)

            db.head = synchronized_head  # type: ignore[method-assign]
            try:
                threads = [
                    threading.Thread(target=commit, args=("left",)),
                    threading.Thread(target=commit, args=("right",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(10)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
            finally:
                db.head = original_head  # type: ignore[method-assign]

            failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
            successes = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
            self.assertEqual(len(successes), 1)
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0], HeadConflictError)
            self.assertEqual(len(db._ledger.find_claims()), 1)
            self.assertEqual(db.head(), successes[0].value)

            db.close()
            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), successes[0].value)
            reopened.close()

    def test_commit_hot_path_does_not_scan_active_ledger(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        with patch(
            "factgraph.core.store.database._active_factual_assertions",
            side_effect=AssertionError("commit performed a full active-set scan"),
        ):
            db.commit_assertions((_assertion("p1", "Ada"),))


if __name__ == "__main__":
    unittest.main()
