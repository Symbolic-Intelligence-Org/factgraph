from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import time_ns
from typing import Any, Literal

from .candidate_cache import CandidatePayloadCache
from .documents.bundle import BundleManager
from .draft import DraftManager
from .errors import AgentContractError, AgentRecoveryError, AgentRuntimeError
from .session import AgentSession
from .tools._runtime_api import RuntimeAPI, resolve_runtime_api


@dataclass
class RecoveryResult:
    session: AgentSession
    draft_manager: DraftManager
    bundle_manager: BundleManager
    candidate_cache: CandidatePayloadCache
    mode: Literal["warm", "cold"]
    stale_candidates: list[dict[str, Any]]


class AgentCheckpointStore:
    """Minimal SQLite checkpoint store for AgentSession + Draft/Bundle manager state."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_checkpoint (
                agent_session_id   TEXT PRIMARY KEY,
                session_json       TEXT NOT NULL,
                draft_manager_json TEXT NOT NULL,
                bundle_manager_json TEXT,
                updated_at_ns      INTEGER NOT NULL
            )
            """
        )
        columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(agent_checkpoint)").fetchall()
        }
        if "bundle_manager_json" not in columns:
            self._conn.execute(
                "ALTER TABLE agent_checkpoint ADD COLUMN bundle_manager_json TEXT"
            )
        self._conn.commit()

    def save(
        self,
        session: AgentSession,
        draft_manager: DraftManager,
        bundle_manager: BundleManager | None = None,
    ) -> None:
        if not isinstance(session, AgentSession):
            raise AgentContractError("session must be AgentSession")
        if not isinstance(draft_manager, DraftManager):
            raise AgentContractError("draft_manager must be DraftManager")
        if bundle_manager is None:
            bundle_manager = BundleManager(draft_manager=draft_manager)
        if not isinstance(bundle_manager, BundleManager):
            raise AgentContractError("bundle_manager must be BundleManager")
        self._conn.execute(
            """
            INSERT OR REPLACE INTO agent_checkpoint
                (agent_session_id, session_json, draft_manager_json, bundle_manager_json, updated_at_ns)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session.agent_session_id,
                json.dumps(session.to_checkpoint(), sort_keys=True),
                json.dumps(draft_manager.to_checkpoint(), sort_keys=True),
                json.dumps(bundle_manager.to_checkpoint(), sort_keys=True),
                time_ns(),
            ),
        )
        self._conn.commit()

    def load(self, agent_session_id: str) -> tuple[AgentSession, DraftManager, BundleManager]:
        row = self._conn.execute(
            """
            SELECT session_json, draft_manager_json, bundle_manager_json
            FROM agent_checkpoint
            WHERE agent_session_id=?
            """,
            (agent_session_id,),
        ).fetchone()
        if row is None:
            raise AgentRecoveryError(f"checkpoint not found: {agent_session_id}")
        session = AgentSession.from_checkpoint(json.loads(row[0]))
        draft_manager = DraftManager.from_checkpoint(json.loads(row[1]))
        if row[2]:
            bundle_manager = BundleManager.from_checkpoint(
                json.loads(row[2]),
                draft_manager=draft_manager,
            )
        else:
            bundle_manager = BundleManager(draft_manager=draft_manager)
        return session, draft_manager, bundle_manager

    def delete(self, agent_session_id: str) -> int:
        cursor = self._conn.execute(
            "DELETE FROM agent_checkpoint WHERE agent_session_id=?",
            (agent_session_id,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()


def recover_agent_session(
    agent_session_id: str,
    *,
    db_path: str | Path,
    runtime_api_base: str | None = None,
    runtime_api: RuntimeAPI | None = None,
) -> RecoveryResult:
    checkpoint = AgentCheckpointStore(db_path)
    try:
        session, draft_manager, bundle_manager = checkpoint.load(agent_session_id)
        runtime = resolve_runtime_api(
            runtime_api_base=runtime_api_base,
            runtime_api=runtime_api,
        )
        cache = CandidatePayloadCache(db_path)

        old_runtime_id = session.runtime_session_id
        if old_runtime_id is None:
            raise AgentRecoveryError("agent session has no runtime_session_id")

        try:
            resp = runtime.get_session(old_runtime_id)
            if resp.get("ok") is True:
                session.status = "active"
                session.touch()
                checkpoint.save(session, draft_manager, bundle_manager)
                return RecoveryResult(
                    session=session,
                    draft_manager=draft_manager,
                    bundle_manager=bundle_manager,
                    candidate_cache=cache,
                    mode="warm",
                    stale_candidates=[],
                )
        except AgentRuntimeError:
            pass

        if session.bootstrap_spec is None:
            raise AgentRecoveryError("no bootstrap spec saved; cannot cold restart")

        open_resp = runtime.open_session(dict(session.bootstrap_spec.open_dto))
        if open_resp.get("ok") is not True:
            raise AgentRecoveryError("cold restart failed to open runtime session")
        new_runtime_id = open_resp.get("session", {}).get("session_id")
        if not isinstance(new_runtime_id, str) or not new_runtime_id:
            raise AgentRecoveryError("cold restart response missing session_id")

        session.runtime_session_id = new_runtime_id
        session.status = "active"
        session.touch()
        stale = cache.list_stale(session.agent_session_id, new_runtime_id)
        checkpoint.save(session, draft_manager, bundle_manager)
        return RecoveryResult(
            session=session,
            draft_manager=draft_manager,
            bundle_manager=bundle_manager,
            candidate_cache=cache,
            mode="cold",
            stale_candidates=stale,
        )
    finally:
        checkpoint.close()
