from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.application.protocol.common import WarningDTO

from .authoring_events import load_authoring_apply_events
from .evidence_graph import EvidenceGraph, evidence_graph_from_dict
from .round_events import (
    ROUND_EVENTS_AUDIT_FILE_KEY,
    RoundEvent,
    RoundEventError,
    make_warning,
    round_event_from_row,
)


class AuditReadError(Exception):
    pass


@dataclass(frozen=True)
class AuditPackageData:
    package_dir: Path
    manifest: dict[str, Any]
    run_manifest: dict[str, Any] | None
    run_ledger: list[dict[str, Any]]
    candidate_ledger: list[dict[str, Any]]
    accept_write_ledger: list[dict[str, Any]]
    decision_log: list[dict[str, Any]]
    accept_failed: list[dict[str, Any]]
    mapping_resolution: dict[str, Any] | None
    support_artifacts: list[dict[str, Any]]
    rule_trace_artifacts: list[dict[str, Any]]
    authoring_apply_events: list[dict[str, Any]]
    certainty_summaries: dict[str, dict[str, Any]]
    provenance_trees: dict[str, dict[str, Any]]
    provenance_statuses: dict[str, dict[str, Any]]
    evidence_graphs: dict[str, EvidenceGraph]
    assertion_annotations: list[dict[str, Any]]
    provenance_timelines: dict[str, dict[str, Any]]
    round_events: tuple[RoundEvent, ...] = ()
    round_event_warnings: tuple[WarningDTO, ...] = ()


def load_audit_package(package_dir: str | Path) -> AuditPackageData:
    root = Path(package_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise AuditReadError(f"missing manifest.json: {manifest_path}")

    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise AuditReadError("manifest.json must be JSON object")

    package_kind = manifest.get("package_kind")
    if package_kind != "audit":
        raise AuditReadError(f"package_kind must be 'audit', got: {package_kind!r}")

    audit_files = _read_manifest_audit_files(manifest)
    run_manifest = _maybe_read_json(root / "outputs" / "run_manifest.json")

    mapping_resolution = _maybe_read_json(_required_rel_path(root, audit_files, "mapping_resolution"))
    round_events, round_event_warnings = _read_round_events(root, audit_files)
    return AuditPackageData(
        package_dir=root,
        manifest=manifest,
        run_manifest=run_manifest,
        run_ledger=_read_jsonl(_required_rel_path(root, audit_files, "run_ledger")),
        candidate_ledger=_read_jsonl(_required_rel_path(root, audit_files, "candidate_ledger")),
        accept_write_ledger=_read_jsonl(_required_rel_path(root, audit_files, "accept_write_ledger")),
        decision_log=_read_jsonl(_required_rel_path(root, audit_files, "decision_log")),
        accept_failed=_read_jsonl(_required_rel_path(root, audit_files, "accept_failed")),
        mapping_resolution=mapping_resolution,
        support_artifacts=_read_optional_jsonl(root, audit_files, "support_artifacts"),
        rule_trace_artifacts=_read_optional_jsonl(root, audit_files, "rule_trace_artifacts"),
        authoring_apply_events=[dict(evt.raw) for evt in load_authoring_apply_events(root)],
        certainty_summaries=_read_certainty_summaries(root, audit_files),
        provenance_trees=_read_provenance_trees(root, audit_files),
        provenance_statuses=_read_provenance_statuses(root, audit_files),
        evidence_graphs=_read_evidence_graphs(root, audit_files),
        assertion_annotations=_read_optional_jsonl(root, audit_files, "assertion_annotations"),
        provenance_timelines=_read_provenance_timelines(root, audit_files),
        round_events=round_events,
        round_event_warnings=round_event_warnings,
    )


def _read_manifest_audit_files(manifest: dict[str, Any]) -> dict[str, str]:
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise AuditReadError("manifest.paths must be object")
    audit_files = paths.get("audit_files")
    if not isinstance(audit_files, dict):
        raise AuditReadError("manifest.paths.audit_files must be object for audit package")
    required = {
        "run_ledger",
        "candidate_ledger",
        "accept_write_ledger",
        "accept_failed",
        "mapping_resolution",
        "decision_log",
    }
    out: dict[str, str] = {}
    for key in required:
        value = audit_files.get(key)
        if not isinstance(value, str) or not value:
            raise AuditReadError(f"manifest.paths.audit_files.{key} must be non-empty string")
        out[key] = value
    for key in (
        "rule_trace_artifacts",
        "support_artifacts",
        "certainty_summaries",
        "provenance_trees",
        "provenance_statuses",
        "evidence_graphs",
        "assertion_annotations",
        "provenance_timelines",
        ROUND_EVENTS_AUDIT_FILE_KEY,
    ):
        value = audit_files.get(key)
        if isinstance(value, str) and value:
            out[key] = value
    return out


def _required_rel_path(root: Path, mapping: dict[str, str], key: str) -> Path:
    rel = mapping.get(key)
    if rel is None:
        raise AuditReadError(f"missing audit file key: {key}")
    path = root / rel
    if not path.exists():
        raise AuditReadError(f"missing audit file: {path}")
    return path


def _read_optional_jsonl(root: Path, mapping: dict[str, str], key: str) -> list[dict[str, Any]]:
    rel = mapping.get(key)
    if not isinstance(rel, str) or not rel:
        return []
    path = root / rel
    if not path.exists():
        return []
    return _read_jsonl(path)


def _read_certainty_summaries(root: Path, mapping: dict[str, str]) -> dict[str, dict[str, Any]]:
    rows = _read_optional_jsonl(root, mapping, "certainty_summaries")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        certainty_summary = row.get("certainty_summary")
        if (
            isinstance(candidate_id, str)
            and candidate_id
            and isinstance(certainty_summary, dict)
        ):
            result[candidate_id] = certainty_summary
    return result


def _read_provenance_trees(root: Path, mapping: dict[str, str]) -> dict[str, dict[str, Any]]:
    rows = _read_optional_jsonl(root, mapping, "provenance_trees")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        provenance_tree = row.get("provenance_tree")
        if (
            isinstance(candidate_id, str)
            and candidate_id
            and isinstance(provenance_tree, dict)
        ):
            result[candidate_id] = provenance_tree
    return result


def _read_provenance_statuses(root: Path, mapping: dict[str, str]) -> dict[str, dict[str, Any]]:
    rows = _read_optional_jsonl(root, mapping, "provenance_statuses")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        status_row = {key: value for key, value in row.items() if key != "candidate_id"}
        if status_row:
            result[candidate_id] = status_row
    return result


def _read_evidence_graphs(root: Path, mapping: dict[str, str]) -> dict[str, EvidenceGraph]:
    rows = _read_optional_jsonl(root, mapping, "evidence_graphs")
    result: dict[str, EvidenceGraph] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        evidence_graph = row.get("evidence_graph")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        if not isinstance(evidence_graph, dict):
            continue
        if candidate_id in result:
            raise AuditReadError(f"duplicate candidate_id in evidence_graphs: {candidate_id}")
        try:
            result[candidate_id] = evidence_graph_from_dict(evidence_graph)
        except ValueError as exc:
            raise AuditReadError(f"invalid evidence_graph for candidate {candidate_id}: {exc}") from exc
    return result


def _read_provenance_timelines(root: Path, mapping: dict[str, str]) -> dict[str, dict[str, Any]]:
    rows = _read_optional_jsonl(root, mapping, "provenance_timelines")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        provenance_timeline = row.get("provenance_timeline")
        if (
            isinstance(candidate_id, str)
            and candidate_id
            and isinstance(provenance_timeline, dict)
        ):
            result[candidate_id] = provenance_timeline
    return result


def _read_round_events(
    root: Path, mapping: dict[str, str]
) -> tuple[tuple[RoundEvent, ...], tuple[WarningDTO, ...]]:
    rel = mapping.get(ROUND_EVENTS_AUDIT_FILE_KEY)
    if not isinstance(rel, str) or not rel:
        return (), ()
    path = root / rel
    if not path.exists():
        return (), ()

    events: list[RoundEvent] = []
    warnings: list[WarningDTO] = []
    seen: set[tuple[str, int]] = set()
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(
                    make_warning(
                        code="ROUND_EVENT_MALFORMED",
                        message=f"invalid round event JSON at {rel}:{lineno}: {exc}",
                        details={"line": lineno},
                    )
                )
                continue
            if not isinstance(row, dict):
                warnings.append(
                    make_warning(
                        code="ROUND_EVENT_MALFORMED",
                        message=f"round event row must be object at {rel}:{lineno}",
                        details={"line": lineno},
                    )
                )
                continue
            try:
                event = round_event_from_row(row)
            except RoundEventError as exc:
                warnings.append(
                    make_warning(
                        code="ROUND_EVENT_MALFORMED",
                        message=f"invalid round event row at {rel}:{lineno}: {exc}",
                        details={"line": lineno},
                    )
                )
                continue
            identity = (event.round_id, event.sequence)
            if identity in seen:
                warnings.append(
                    make_warning(
                        code="ROUND_EVENT_DUPLICATE",
                        message=(
                            "duplicate round event identity "
                            f"{event.round_id}:{event.sequence} at {rel}:{lineno}"
                        ),
                        details={
                            "round_id": event.round_id,
                            "sequence": event.sequence,
                            "line": lineno,
                        },
                    )
                )
                continue
            seen.add(identity)
            events.append(event)
    return tuple(events), tuple(warnings)


def _read_json(path: Path) -> dict[str, Any] | list[Any] | Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditReadError(f"invalid JSON at {path}: {exc}") from exc


def _maybe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise AuditReadError(f"expected JSON object at {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditReadError(f"invalid JSONL at {path}:{lineno}: {exc}") from exc
            if not isinstance(row, dict):
                raise AuditReadError(f"JSONL row must be object at {path}:{lineno}")
            rows.append(row)
    return rows
