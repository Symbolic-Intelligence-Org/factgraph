from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from time import time_ns
from typing import Any

from .errors import AgentContractError


class CandidatePayloadCache:
    """SQLite-backed cache for evaluate-response candidate payloads."""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_payload_cache (
                agent_session_id    TEXT    NOT NULL,
                runtime_session_id  TEXT    NOT NULL,
                candidate_id        TEXT    NOT NULL,
                payload_json        TEXT    NOT NULL,
                stored_at           INTEGER NOT NULL,
                PRIMARY KEY (agent_session_id, runtime_session_id, candidate_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cpc_runtime
                ON candidate_payload_cache(runtime_session_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cpc_agent
                ON candidate_payload_cache(agent_session_id)
            """
        )
        self._conn.commit()

    def store(
        self,
        agent_session_id: str,
        runtime_session_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        _require_non_empty_str(agent_session_id, "agent_session_id")
        _require_non_empty_str(runtime_session_id, "runtime_session_id")
        if not isinstance(candidates, list):
            raise AgentContractError("candidates must be list")
        now = time_ns()
        rows: list[tuple[str, str, str, str, int]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise AgentContractError("candidate payloads must be objects")
            candidate_id = _require_non_empty_str(candidate.get("candidate_id"), "candidate_id")
            rows.append(
                (
                    agent_session_id,
                    runtime_session_id,
                    candidate_id,
                    json.dumps(candidate, sort_keys=True),
                    now,
                )
            )
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO candidate_payload_cache
                (agent_session_id, runtime_session_id, candidate_id, payload_json, stored_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def lookup_active(self, runtime_session_id: str, candidate_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT payload_json FROM candidate_payload_cache
            WHERE runtime_session_id=? AND candidate_id=?
            """,
            (
                _require_non_empty_str(runtime_session_id, "runtime_session_id"),
                _require_non_empty_str(candidate_id, "candidate_id"),
            ),
        ).fetchone()
        return json.loads(row[0]) if row is not None else None

    def lookup_active_by_runtime(self, runtime_session_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT payload_json FROM candidate_payload_cache
            WHERE runtime_session_id=?
            ORDER BY stored_at, candidate_id
            """,
            (_require_non_empty_str(runtime_session_id, "runtime_session_id"),),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_stale(
        self,
        agent_session_id: str,
        current_runtime_session_id: str,
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT runtime_session_id, candidate_id, payload_json, stored_at
            FROM candidate_payload_cache
            WHERE agent_session_id=? AND runtime_session_id!=?
            ORDER BY stored_at, candidate_id
            """,
            (
                _require_non_empty_str(agent_session_id, "agent_session_id"),
                _require_non_empty_str(current_runtime_session_id, "current_runtime_session_id"),
            ),
        ).fetchall()
        return [
            {
                "runtime_session_id": row[0],
                "candidate_id": row[1],
                "payload": json.loads(row[2]),
                "stored_at": row[3],
            }
            for row in rows
        ]

    def evict_agent_session(self, agent_session_id: str) -> int:
        cursor = self._conn.execute(
            "DELETE FROM candidate_payload_cache WHERE agent_session_id=?",
            (_require_non_empty_str(agent_session_id, "agent_session_id"),),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
