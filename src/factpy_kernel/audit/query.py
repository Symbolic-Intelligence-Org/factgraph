from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reader import AuditPackageData


class AuditQueryError(Exception):
    pass


@dataclass(frozen=True)
class AuditQuery:
    package: AuditPackageData

    def __post_init__(self) -> None:
        if not isinstance(self.package, AuditPackageData):
            raise AuditQueryError("package must be AuditPackageData")

    def list_runs(self) -> list[dict[str, Any]]:
        return sorted(
            [dict(row) for row in self.package.run_ledger],
            key=lambda row: str(row.get("run_id", "")),
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if not isinstance(run_id, str) or not run_id:
            raise AuditQueryError("run_id must be non-empty string")
        for row in self.package.run_ledger:
            if row.get("run_id") == run_id:
                return dict(row)
        return None

    def list_materializations(
        self,
        *,
        run_id: str | None = None,
        materialize_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.materialize_ledger]
        if run_id is not None:
            rows = [row for row in rows if row.get("run_id") == run_id]
        if materialize_id is not None:
            rows = [row for row in rows if row.get("materialize_id") == materialize_id]
        return sorted(rows, key=lambda row: (str(row.get("materialize_id", "")), str(row.get("asrt_id", ""))))

    def list_candidates(
        self,
        *,
        run_id: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.candidate_ledger]
        if run_id is not None:
            rows = [row for row in rows if row.get("run_id") == run_id]
        if state is not None:
            rows = [row for row in rows if row.get("state") == state]
        return sorted(rows, key=lambda row: (str(row.get("candidate_id", "")), str(row.get("asrt_id", ""))))

    def list_decisions(
        self,
        *,
        run_id: str | None = None,
        event_source: str | None = None,
        event_kind: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.decision_log]
        if run_id is not None:
            rows = [row for row in rows if self._row_has_run_id(row, run_id)]
        if event_source is not None:
            rows = [row for row in rows if row.get("event_source") == event_source]
        if event_kind is not None:
            rows = [row for row in rows if row.get("event_kind") == event_kind]
        return sorted(rows, key=self._decision_sort_key)

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        if not isinstance(decision_id, str) or not decision_id:
            raise AuditQueryError("decision_id must be non-empty string")
        for row in self.package.decision_log:
            if row.get("decision_id") == decision_id:
                return dict(row)
        return None

    def list_failures(
        self,
        *,
        run_id: str | None = None,
        error_class: str | None = None,
        event_kind: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.accept_failed]
        if run_id is not None:
            rows = [row for row in rows if self._row_has_run_id(row, run_id)]
        if error_class is not None:
            rows = [row for row in rows if row.get("error_class") == error_class]
        if event_kind is not None:
            rows = [row for row in rows if row.get("event_kind") == event_kind]
        return sorted(rows, key=self._failure_sort_key)

    def get_run_bundle(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            raise AuditQueryError(f"run not found: {run_id}")

        decisions = self.list_decisions(run_id=run_id)
        materializations = self.list_materializations(run_id=run_id)
        candidates = self.list_candidates(run_id=run_id)
        failures = self.list_failures(run_id=run_id)
        materialize_ids = {row.get("materialize_id") for row in materializations if isinstance(row.get("materialize_id"), str)}
        decision_index = {
            row["decision_id"]: row
            for row in decisions
            if isinstance(row.get("decision_id"), str)
        }

        return {
            "run": run,
            "decisions": decisions,
            "materializations": materializations,
            "candidates": candidates,
            "failures": failures,
            "decision_index": decision_index,
            "materialize_ids": sorted(materialize_ids),
        }

    def get_mapping_resolution(self, *, pred_id: str | None = None) -> dict[str, Any] | list[dict[str, Any]] | None:
        payload = self.package.mapping_resolution
        if payload is None:
            return None
        if pred_id is None:
            return dict(payload)
        predicates = payload.get("predicates")
        if not isinstance(predicates, list):
            return []
        return [
            dict(row)
            for row in predicates
            if isinstance(row, dict) and row.get("pred_id") == pred_id
        ]

    def list_authoring_apply_events(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
        section: str | None = None,
        apply_request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.authoring_apply_events]
        if kind is not None:
            rows = [row for row in rows if row.get("kind") == kind]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if section is not None:
            rows = [row for row in rows if row.get("section") == section]
        if apply_request_id is not None:
            rows = [row for row in rows if row.get("apply_request_id") == apply_request_id]
        return sorted(rows, key=self._authoring_apply_sort_key)

    def list_authoring_apply_runs(self) -> list[dict[str, Any]]:
        return self.list_authoring_apply_events(kind="authoring_apply_execute_run")

    def get_authoring_apply_run(self, apply_request_id: str) -> dict[str, Any] | None:
        if not isinstance(apply_request_id, str) or not apply_request_id:
            raise AuditQueryError("apply_request_id must be non-empty string")
        rows = self.list_authoring_apply_runs()
        for row in rows:
            if row.get("apply_request_id") == apply_request_id:
                return row
        return None

    def get_authoring_apply_bundle(self, apply_request_id: str) -> dict[str, Any]:
        run = self.get_authoring_apply_run(apply_request_id)
        if run is None:
            raise AuditQueryError(f"authoring apply run not found: {apply_request_id}")
        events = self.list_authoring_apply_events(apply_request_id=apply_request_id)
        status_counts: dict[str, int] = {}
        section_counts: dict[str, int] = {}
        for row in events:
            status = row.get("status")
            if isinstance(status, str) and status:
                status_counts[status] = status_counts.get(status, 0) + 1
            section = row.get("section")
            if isinstance(section, str) and section:
                section_counts[section] = section_counts.get(section, 0) + 1
        summary = {
            "event_count": len(events),
            "status_counts": {key: status_counts[key] for key in sorted(status_counts)},
            "section_counts": {key: section_counts[key] for key in sorted(section_counts)},
        }
        return {
            "run": run,
            "events": events,
            "summary": summary,
        }

    @staticmethod
    def _row_has_run_id(row: dict[str, Any], run_id: str) -> bool:
        direct = row.get("run_id")
        if direct == run_id:
            return True
        run_ids = row.get("run_ids")
        if isinstance(run_ids, list):
            return any(value == run_id for value in run_ids)
        return False

    @staticmethod
    def _decision_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        event_ts = row.get("event_ts")
        event_ts_key = event_ts if isinstance(event_ts, int) and not isinstance(event_ts, bool) else -1
        return (
            event_ts_key,
            str(row.get("decision_id", "")),
        )

    @staticmethod
    def _failure_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        event_ts = row.get("event_ts")
        event_ts_key = event_ts if isinstance(event_ts, int) and not isinstance(event_ts, bool) else -1
        return (
            event_ts_key,
            str(row.get("decision_id", "")),
        )

    @staticmethod
    def _authoring_apply_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            str(row.get("apply_request_id", "")),
            str(row.get("kind", "")),
            str(row.get("action_id", "")),
        )
