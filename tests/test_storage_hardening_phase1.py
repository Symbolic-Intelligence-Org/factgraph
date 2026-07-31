from __future__ import annotations

import multiprocessing
import json
import os
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
    Database,
    DatabaseIntegrityError,
    DatabaseLockedError,
    HeadConflictError,
    MetaEntry,
    RevocationInput,
    _state_digest_for_ids,
    resolve_database_workspace_paths,
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
        active_ids = {
            claim.asrt_id
            for claim in db._ledger.find_claims()
            if not claim.pred_id.startswith("__system__")
            and not db._ledger.has_active_revocation(claim.asrt_id)
        }
        self.assertEqual(db.head().state_digest, _state_digest_for_ids(active_ids))

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

    def test_tx_object_commits_ordered_delta_and_digest_scheme_not_full_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            committed = db.commit_assertions((_assertion("p1", "Ada"),))
            paths = resolve_database_workspace_paths(path)
            tx_path = paths.tx_objects / f"{committed.value.tx_id.removeprefix('tx:')}.json"
            payload = json.loads(tx_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["digest_scheme"], "lthash16-v1")
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
            before_repair_seq = db.head().tx_seq
            db.close()

            rogue_id = "asrt:" + "f" * 32
            paths = resolve_database_workspace_paths(path)
            with sqlite3.connect(paths.assertions) as conn:
                conn.execute(
                    "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) VALUES (?, ?, ?, ?)",
                    (rogue_id, "person:name", "idref_v1:Person:rogue", "[]"),
                )

            with self.assertRaisesRegex(DatabaseIntegrityError, "terminal set"):
                Database.open(path, schema_ir=_schema_ir())

            repaired = Database.repair(
                path,
                schema_ir=_schema_ir(),
                reason="phase1-test-injected-ledger-drift",
            )
            self.assertEqual(repaired.head().tx_seq, before_repair_seq + 1)
            self.assertIsNotNone(repaired._ledger.get_claim(rogue_id))
            repair_meta = repaired._ledger.get_ledger_meta("last_repair")
            self.assertIsNotNone(repair_meta)
            self.assertIn("phase1-test-injected-ledger-drift", repair_meta or "")
            repaired.close()

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assert_state_matches_full_recompute(reopened)
            reopened.close()

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
            "factgraph.core.store.database._active_factual_assertion_ids",
            side_effect=AssertionError("commit performed a full active-set scan"),
        ):
            db.commit_assertions((_assertion("p1", "Ada"),))


if __name__ == "__main__":
    unittest.main()
