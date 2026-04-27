from __future__ import annotations

import sqlite3
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from kernel.core.store.ledger import Claim, Ledger


def _claim(*, asrt_id: str, e_ref: str) -> Claim:
    return Claim(
        asrt_id=asrt_id,
        pred_id="user:tag",
        e_ref=e_ref,
        rest_terms=[],
    )


class LedgerConcurrencyTests(unittest.TestCase):
    def test_concurrent_writes_succeed_without_deadlock(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            ledger = Ledger(Path(tmp_dir) / "ledger.db")
            errors: list[str] = []

            def worker(worker_idx: int) -> None:
                try:
                    for item_idx in range(100):
                        ledger.append_assertion(
                            claim=_claim(
                                asrt_id=f"asrt_{worker_idx}_{item_idx}",
                                e_ref=f"idref_v1:User:source_id={worker_idx}_{item_idx}",
                            ),
                            claim_args=[],
                            meta_rows=[],
                        )
                except Exception as exc:  # pragma: no cover - failure path only
                    errors.append(f"{worker_idx}:{exc}")

            threads = [threading.Thread(target=worker, args=(idx,)) for idx in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)

            self.assertEqual(errors, [])
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len(ledger.claims), 1000)

            with sqlite3.connect(Path(tmp_dir) / "ledger.db") as conn:
                count = conn.execute("SELECT count(*) FROM claims").fetchone()[0]
            self.assertEqual(count, 1000)

    def test_reader_blocks_until_post_commit_hooks_finish(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            ledger = Ledger(Path(tmp_dir) / "ledger.db")
            hook_started = threading.Event()
            allow_hook = threading.Event()
            reader_finished = threading.Event()
            reader_result: dict[str, int] = {}

            original_idx_add_claim = ledger._idx_add_claim

            def delayed_idx_add_claim(claim: Claim) -> None:
                hook_started.set()
                allow_hook.wait(timeout=5)
                original_idx_add_claim(claim)

            writer = threading.Thread(
                target=lambda: ledger.append_assertion(
                    claim=_claim(asrt_id="asrt_1", e_ref="idref_v1:User:source_id=u1"),
                    claim_args=[],
                    meta_rows=[],
                )
            )

            with patch.object(ledger, "_idx_add_claim", side_effect=delayed_idx_add_claim):
                writer.start()
                self.assertTrue(hook_started.wait(timeout=5))

                with sqlite3.connect(Path(tmp_dir) / "ledger.db") as conn:
                    db_count = conn.execute("SELECT count(*) FROM claims").fetchone()[0]
                self.assertEqual(db_count, 1)

                def reader() -> None:
                    reader_result["count"] = len(ledger.find_claims())
                    reader_finished.set()

                reader_thread = threading.Thread(target=reader)
                reader_thread.start()
                time.sleep(0.1)
                self.assertFalse(reader_finished.is_set(), "reader must block during post-commit hook window")

                allow_hook.set()
                writer.join(timeout=5)
                reader_thread.join(timeout=5)

            self.assertFalse(writer.is_alive())
            self.assertFalse(reader_thread.is_alive())
            self.assertEqual(reader_result["count"], 1)

    def test_rollback_skips_post_commit_indexes_and_allows_later_write(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            ledger = Ledger(Path(tmp_dir) / "ledger.db")

            with patch.object(ledger, "_insert_meta_rows", side_effect=RuntimeError("boom")):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    ledger.append_assertion(
                        claim=_claim(asrt_id="asrt_fail", e_ref="idref_v1:User:source_id=fail"),
                        claim_args=[],
                        meta_rows=[],
                    )

            self.assertEqual(len(ledger.find_claims()), 0)
            with sqlite3.connect(Path(tmp_dir) / "ledger.db") as conn:
                count = conn.execute("SELECT count(*) FROM claims").fetchone()[0]
            self.assertEqual(count, 0)

            ledger.append_assertion(
                claim=_claim(asrt_id="asrt_ok", e_ref="idref_v1:User:source_id=ok"),
                claim_args=[],
                meta_rows=[],
            )
            self.assertEqual(len(ledger.find_claims()), 1)

    def test_close_is_idempotent_and_blocks_future_access(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            ledger = Ledger(Path(tmp_dir) / "ledger.db")
            current_conn = ledger._get_connection()
            worker_ready = threading.Event()
            worker_done = threading.Event()
            worker_error: dict[str, str] = {}

            def worker() -> None:
                try:
                    ledger._get_connection()
                    worker_ready.set()
                    worker_done.wait(timeout=5)
                    with self.assertRaises(RuntimeError):
                        ledger._get_connection()
                except Exception as exc:  # pragma: no cover - failure path only
                    worker_error["error"] = str(exc)

            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(worker_ready.wait(timeout=5))

            ledger.close()
            ledger.close()

            self.assertEqual(ledger._all_connections, [])
            with self.assertRaises(RuntimeError):
                ledger._get_connection()
            with self.assertRaises(RuntimeError):
                ledger.find_claims()
            with self.assertRaises(sqlite3.ProgrammingError):
                current_conn.execute("SELECT 1")

            worker_done.set()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("error", worker_error)
