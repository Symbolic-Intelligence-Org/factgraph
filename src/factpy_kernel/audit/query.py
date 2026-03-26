from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.core.store._candidate_evidence_tree import (
    build_candidate_evidence_tree,
    build_degraded_candidate_evidence_tree,
)
from factpy_kernel.core.store._candidate_evidence_tree_narrative import (
    render_candidate_evidence_tree_narrative,
)
from factpy_kernel.core.store._candidate_evidence_tree_summary import (
    summarize_candidate_evidence_tree_dict,
)
from factpy_kernel.core.store._support import _DEGRADED_SUPPORT_KINDS, _WITNESS_BEARING_SUPPORT_KINDS
from factpy_kernel.core.rules._trace_narrative import render_rule_run_narrative
from factpy_kernel.core.rules._trace import summarize_rule_trace_artifact_dict

from .assertions import AuditAssertionReadError, load_assertion_index
from .compliance import AuditComplianceError, build_compliance_matrix_rows
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

    def list_accept_writes(
        self,
        *,
        run_id: str | None = None,
        candidate_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.package.accept_write_ledger]
        if run_id is not None:
            rows = [row for row in rows if row.get("run_id") == run_id]
        if candidate_id is not None:
            rows = [row for row in rows if row.get("candidate_id") == candidate_id]
        return sorted(rows, key=lambda row: (str(row.get("candidate_id", "")), str(row.get("asrt_id", ""))))

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

    def get_candidate_evidence_tree(self, candidate_id: str) -> dict[str, Any] | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AuditQueryError("candidate_id must be non-empty string")
        rows = [dict(row) for row in self.package.candidate_ledger if row.get("candidate_id") == candidate_id]
        if not rows:
            return None
        support_digests = {
            row["support_digest"]
            for row in rows
            if isinstance(row.get("support_digest"), str) and row.get("support_digest")
        }
        support_kinds = {
            row["support_kind"]
            for row in rows
            if isinstance(row.get("support_kind"), str) and row.get("support_kind")
        }
        if len(support_digests) != 1:
            raise AuditQueryError(f"candidate has inconsistent support_digest rows: {candidate_id}")
        if len(support_kinds) != 1:
            raise AuditQueryError(f"candidate has inconsistent support_kind rows: {candidate_id}")
        support_digest = next(iter(support_digests))
        support_kind = next(iter(support_kinds))
        if support_kind not in _WITNESS_BEARING_SUPPORT_KINDS:
            if support_kind in _DEGRADED_SUPPORT_KINDS:
                return build_degraded_candidate_evidence_tree(
                    candidate_id=candidate_id,
                    support_digest=support_digest,
                    support_kind=support_kind,
                )
            raise AuditQueryError(
                f"candidate evidence tree only supports native or degraded support_kind, got: {support_kind}"
            )
        support = self._get_support_artifact(support_digest)
        if support is None:
            raise AuditQueryError(f"support artifact not found: {support_digest}")
        try:
            assertion_index = load_assertion_index(self.package)
        except AuditAssertionReadError as exc:
            raise AuditQueryError(str(exc)) from exc
        try:
            return build_candidate_evidence_tree(
                candidate_id=candidate_id,
                support_digest=support_digest,
                support_kind=support_kind,
                support=support,
                assertion_lookup=assertion_index.get_assertion_detail,
                support_lookup=self._get_support_artifact,
            )
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def get_candidate_evidence_tree_summary(self, candidate_id: str) -> dict[str, Any] | None:
        tree = self.get_candidate_evidence_tree(candidate_id)
        if tree is None:
            return None
        try:
            return summarize_candidate_evidence_tree_dict(tree)
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def get_candidate_evidence_tree_narrative(self, candidate_id: str) -> dict[str, Any] | None:
        summary = self.get_candidate_evidence_tree_summary(candidate_id)
        if summary is None:
            return None
        certainty_summary = self.get_candidate_certainty_summary(candidate_id)
        try:
            return render_candidate_evidence_tree_narrative(
                summary,
                certainty_summary=certainty_summary,
                locale="en",
            )
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def get_candidate_certainty_summary(self, candidate_id: str) -> dict[str, Any] | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AuditQueryError("candidate_id must be non-empty string")
        return self.package.certainty_summaries.get(candidate_id)

    def get_candidate_provenance_tree(self, candidate_id: str) -> dict[str, Any] | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AuditQueryError("candidate_id must be non-empty string")
        return self.package.provenance_trees.get(candidate_id)

    def get_candidate_provenance_status(self, candidate_id: str) -> dict[str, Any] | None:
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AuditQueryError("candidate_id must be non-empty string")
        return self.package.provenance_statuses.get(candidate_id)

    def list_candidates_with_provenance(self) -> list[dict[str, Any]]:
        """Return unique candidate rows that have materialized provenance trees."""
        result: list[dict[str, Any]] = []
        for row in self._unique_candidate_rows():
            candidate_id = row.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            status = self.package.provenance_statuses.get(candidate_id, {})
            if status.get("status") == "present":
                result.append(row)
        return result

    def list_candidates_without_provenance(self) -> list[dict[str, Any]]:
        """Return unique candidate rows missing provenance, with status and reason."""
        result: list[dict[str, Any]] = []
        for row in self._unique_candidate_rows():
            candidate_id = row.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            status = self.package.provenance_statuses.get(candidate_id, {})
            if status.get("status") == "present":
                continue
            item = dict(row)
            item["provenance_status"] = status.get("status", "unknown")
            item["provenance_reason"] = status.get("reason", "")
            result.append(item)
        return result

    def summarize_provenance_coverage(self) -> dict[str, Any]:
        """Return package-level provenance coverage for unique candidates."""
        candidates = self._unique_candidate_rows()
        total = len(candidates)
        by_status: dict[str, int] = {}
        truncated_count = 0

        for row in candidates:
            candidate_id = row.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            status = self.package.provenance_statuses.get(candidate_id, {})
            status_value = status.get("status", "unknown")
            status_key = status_value if isinstance(status_value, str) and status_value else "unknown"
            by_status[status_key] = by_status.get(status_key, 0) + 1
            if status.get("truncated") is True:
                truncated_count += 1

        with_provenance = by_status.get("present", 0)
        without_provenance = total - with_provenance
        coverage_pct = round((with_provenance / total) * 100, 1) if total > 0 else 0.0

        return {
            "total_candidates": total,
            "with_provenance": with_provenance,
            "without_provenance": without_provenance,
            "truncated": truncated_count,
            "by_status": by_status,
            "coverage_pct": coverage_pct,
        }

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
        accept_writes = self.list_accept_writes(run_id=run_id)
        candidates = self.list_candidates(run_id=run_id)
        failures = self.list_failures(run_id=run_id)
        candidate_ids = {row.get("candidate_id") for row in accept_writes if isinstance(row.get("candidate_id"), str)}
        decision_index = {
            row["decision_id"]: row
            for row in decisions
            if isinstance(row.get("decision_id"), str)
        }

        return {
            "run": run,
            "decisions": decisions,
            "accept_writes": accept_writes,
            "candidates": candidates,
            "failures": failures,
            "decision_index": decision_index,
            "candidate_ids": sorted(candidate_ids),
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

    def _unique_candidate_rows(self) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in self.list_candidates():
            candidate_id = row.get("candidate_id")
            if isinstance(candidate_id, str) and candidate_id and candidate_id not in out:
                out[candidate_id] = row
        return [out[candidate_id] for candidate_id in sorted(out)]

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

    def list_compliance_matrix(
        self,
        *,
        req_id: str | None = None,
        status: str | None = None,
        milestone: str | None = None,
    ) -> list[dict[str, Any]]:
        if req_id is not None and (not isinstance(req_id, str) or not req_id):
            raise AuditQueryError("req_id must be non-empty string when provided")
        if status is not None and (not isinstance(status, str) or not status):
            raise AuditQueryError("status must be non-empty string when provided")
        if milestone is not None and (not isinstance(milestone, str) or not milestone):
            raise AuditQueryError("milestone must be non-empty string when provided")

        try:
            assertion_index = load_assertion_index(self.package)
            rows = build_compliance_matrix_rows(assertion_index)
        except (AuditAssertionReadError, AuditComplianceError) as exc:
            raise AuditQueryError(str(exc)) from exc

        if req_id is not None:
            rows = [row for row in rows if row.get("req_id") == req_id]
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if milestone is not None:
            rows = [row for row in rows if row.get("review_milestone") == milestone]
        return rows

    def list_rule_traces(
        self,
        *,
        root_rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if root_rule_id is not None and (not isinstance(root_rule_id, str) or not root_rule_id):
            raise AuditQueryError("root_rule_id must be non-empty string when provided")
        rows = [dict(row) for row in self.package.rule_trace_artifacts]
        if root_rule_id is not None:
            rows = [
                row
                for row in rows
                if isinstance(row.get("root_rule"), dict) and row["root_rule"].get("rule_id") == root_rule_id
            ]
        return sorted(rows, key=lambda row: str(row.get("rule_run_id", "")))

    def list_rule_trace_summaries(
        self,
        *,
        root_rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            rows = self.list_rule_traces(root_rule_id=root_rule_id)
            return [summarize_rule_trace_artifact_dict(row) for row in rows]
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def get_rule_trace(self, rule_run_id: str) -> dict[str, Any] | None:
        if not isinstance(rule_run_id, str) or not rule_run_id:
            raise AuditQueryError("rule_run_id must be non-empty string")
        for row in self.package.rule_trace_artifacts:
            if row.get("rule_run_id") == rule_run_id:
                return dict(row)
        return None

    def get_rule_trace_summary(self, rule_run_id: str) -> dict[str, Any] | None:
        try:
            trace = self.get_rule_trace(rule_run_id)
            if trace is None:
                return None
            return summarize_rule_trace_artifact_dict(trace)
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def get_rule_trace_narrative(self, rule_run_id: str) -> dict[str, Any] | None:
        try:
            summary = self.get_rule_trace_summary(rule_run_id)
            if summary is None:
                return None
            return render_rule_run_narrative(summary, locale="en")
        except ValueError as exc:
            raise AuditQueryError(str(exc)) from exc

    def _get_support_artifact(self, support_digest: str) -> dict[str, Any] | None:
        for row in self.package.support_artifacts:
            if row.get("support_digest") == support_digest:
                return dict(row)
        return None

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
