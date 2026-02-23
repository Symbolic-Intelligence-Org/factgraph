from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .authoring_events import load_authoring_apply_events


class AuditReadError(Exception):
    pass


@dataclass(frozen=True)
class AuditPackageData:
    package_dir: Path
    manifest: dict[str, Any]
    run_manifest: dict[str, Any] | None
    run_ledger: list[dict[str, Any]]
    candidate_ledger: list[dict[str, Any]]
    materialize_ledger: list[dict[str, Any]]
    decision_log: list[dict[str, Any]]
    accept_failed: list[dict[str, Any]]
    mapping_resolution: dict[str, Any] | None
    authoring_apply_events: list[dict[str, Any]]


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
    return AuditPackageData(
        package_dir=root,
        manifest=manifest,
        run_manifest=run_manifest,
        run_ledger=_read_jsonl(_required_rel_path(root, audit_files, "run_ledger")),
        candidate_ledger=_read_jsonl(_required_rel_path(root, audit_files, "candidate_ledger")),
        materialize_ledger=_read_jsonl(_required_rel_path(root, audit_files, "materialize_ledger")),
        decision_log=_read_jsonl(_required_rel_path(root, audit_files, "decision_log")),
        accept_failed=_read_jsonl(_required_rel_path(root, audit_files, "accept_failed")),
        mapping_resolution=mapping_resolution,
        authoring_apply_events=[dict(evt.raw) for evt in load_authoring_apply_events(root)],
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
        "materialize_ledger",
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
    return out


def _required_rel_path(root: Path, mapping: dict[str, str], key: str) -> Path:
    rel = mapping.get(key)
    if rel is None:
        raise AuditReadError(f"missing audit file key: {key}")
    path = root / rel
    if not path.exists():
        raise AuditReadError(f"missing audit file: {path}")
    return path


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
