from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from factgraph.core.protocol.digests import sha256_token
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs, ensure_schema_ir, schema_digest


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_APPLY_LOG_FILE_NAME = "authoring_apply_events.jsonl"


def _workspace_apply_log_path_for_registry(root_dir: str | Path) -> Path | None:
    root = Path(root_dir)
    workspace = root.parent
    if (
        root.name == "registry"
        and (workspace / "factgraph_workspace.json").exists()
        and (workspace / "db").exists()
    ):
        return workspace / "db" / "audit" / _APPLY_LOG_FILE_NAME
    return None


def resolve_apply_log_write_path(root_dir: str | Path) -> Path:
    return _workspace_apply_log_path_for_registry(root_dir) or (Path(root_dir) / _APPLY_LOG_FILE_NAME)


def resolve_apply_log_read_paths(root_dir: str | Path) -> list[Path]:
    root = Path(root_dir)
    legacy = root / _APPLY_LOG_FILE_NAME
    workspace_path = _workspace_apply_log_path_for_registry(root)
    if workspace_path is None:
        return [legacy]
    return [legacy, workspace_path]


class AuthoringRegistryFSError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.details = details or {}


class FileAuthoringRegistry:
    """Legacy schema/apply-log adapter after A20(E) registry final exit.

    After Q8 Phase 2 removal (Slice 6), this class retains only schema
    persistence and apply-log responsibilities. Rule/inference persistence
    methods were removed entirely. Historical workspace files under
    ``registry/rules/`` and ``registry/inferences/`` are left inert; new
    manifests are schema-only and do not write ``rules`` / ``inferences`` keys.
    Workspace apply logs write to ``db/audit/authoring_apply_events.jsonl`` and
    read both the new and legacy registry paths; non-workspace registry roots
    keep the historical ``registry/authoring_apply_events.jsonl`` behavior.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    @property
    def manifest_path(self) -> Path:
        return self.root_dir / "registry_manifest.json"

    @property
    def apply_log_path(self) -> Path:
        return self.root_dir / _APPLY_LOG_FILE_NAME

    def upsert_schema_ir(self, schema_ir: dict[str, Any]) -> dict[str, Any]:
        validated = ensure_schema_ir(schema_ir)
        data = canonicalize_schema_ir_jcs(validated)
        digest = schema_digest(validated)
        rel_path = "schema/schema_ir.json"
        abs_path = self.root_dir / rel_path
        write_status = self._write_if_changed(abs_path, data + b"\n")

        manifest = self._load_manifest()
        manifest["schema"] = {
            "path": rel_path,
            "schema_digest": digest,
            "bytes_digest": sha256_token(data),
        }
        self._save_manifest(manifest)
        return {
            "kind": "schema",
            "status": write_status,
            "path": rel_path,
            "schema_digest": digest,
        }

    def preview_upsert_schema_ir(self, schema_ir: dict[str, Any]) -> dict[str, Any]:
        validated = ensure_schema_ir(schema_ir)
        data = canonicalize_schema_ir_jcs(validated)
        digest = schema_digest(validated)
        rel_path = "schema/schema_ir.json"
        abs_path = self.root_dir / rel_path
        preview_status = self._preview_write_if_changed(abs_path, data + b"\n")
        return {
            "kind": "schema",
            "status": preview_status,
            "path": rel_path,
            "schema_digest": digest,
        }

    def append_apply_event(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise AuthoringRegistryFSError("event must be object")
        self.apply_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.apply_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            fh.write("\n")

    def find_apply_execute_run(self, apply_request_id: str) -> dict[str, Any] | None:
        if not isinstance(apply_request_id, str) or not apply_request_id:
            raise AuthoringRegistryFSError("apply_request_id must be non-empty string")
        matched: dict[str, Any] | None = None
        for payload in self._iter_apply_events():
            if not isinstance(payload, dict):
                continue
            if payload.get("kind") != "authoring_apply_execute_run":
                continue
            if payload.get("apply_request_id") != apply_request_id:
                continue
            matched = payload
        return matched

    def list_apply_execute_runs(self) -> list[dict[str, Any]]:
        latest_by_request: dict[str, dict[str, Any]] = {}
        for payload in self._iter_apply_events():
            if not isinstance(payload, dict):
                continue
            if payload.get("kind") != "authoring_apply_execute_run":
                continue
            apply_request_id = payload.get("apply_request_id")
            if not isinstance(apply_request_id, str) or not apply_request_id:
                continue
            latest_by_request[apply_request_id] = payload
        return [latest_by_request[key] for key in sorted(latest_by_request)]

    def list_apply_run_ids(self) -> list[str]:
        return [
            str(row.get("apply_request_id"))
            for row in self.list_apply_execute_runs()
            if isinstance(row.get("apply_request_id"), str) and row.get("apply_request_id")
        ]

    def read_manifest(self) -> dict[str, Any]:
        return self._load_manifest()

    def get_schema_entry(self) -> dict[str, Any] | None:
        manifest = self._load_manifest()
        schema = manifest.get("schema")
        if schema is None:
            return None
        if not isinstance(schema, dict):
            raise AuthoringRegistryFSError(
                "registry manifest schema entry must be object or null",
                code="registry_schema_manifest_entry_invalid",
                path="$.schema",
            )
        return dict(schema)

    def _iter_apply_events(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in resolve_apply_log_read_paths(self.root_dir):
            if not path.exists():
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AuthoringRegistryFSError(
                        f"invalid apply event JSON at line {line_no}: {exc}",
                        code="registry_apply_event_json_invalid",
                        path=f"$.authoring_apply_events[{line_no}]",
                    ) from exc
                if isinstance(payload, dict):
                    out.append(payload)
        return out

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "authoring_registry_fs_version": "authoring_registry_fs_v1",
                "schema": None,
            }
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuthoringRegistryFSError(f"invalid registry manifest: {exc}") from exc
        if not isinstance(payload, dict):
            raise AuthoringRegistryFSError("registry manifest must be object")
        payload.setdefault("authoring_registry_fs_version", "authoring_registry_fs_v1")
        payload.setdefault("schema", None)
        # Q8 Phase 2 (Slice 6): no longer inject `setdefault("rules", [])` or
        # `setdefault("inferences", [])` into freshly-loaded manifests. Old
        # manifests that already contain those keys still load tolerantly —
        # the loader does not delete them and does not rewrite them. New
        # manifests written via `_save_manifest(...)` are schema-only.
        return payload

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_bytes(_canonical_json_bytes(manifest) + b"\n")

    def _write_if_changed(
        self,
        path: Path,
        data: bytes,
        *,
        reject_on_conflict: bool = False,
        conflict_code: str | None = None,
        conflict_path: str | None = None,
        conflict_details: dict[str, Any] | None = None,
    ) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            current = path.read_bytes()
            if current == data:
                return "noop"
            if reject_on_conflict:
                raise AuthoringRegistryFSError(
                    "version conflict: existing payload differs from requested payload",
                    code=conflict_code or "registry_version_conflict",
                    path=conflict_path or "$",
                    details=conflict_details or {},
                )
        path.write_bytes(data)
        return "applied"

    def _preview_write_if_changed(
        self,
        path: Path,
        data: bytes,
        *,
        reject_on_conflict: bool = False,
        conflict_code: str | None = None,
        conflict_path: str | None = None,
        conflict_details: dict[str, Any] | None = None,
    ) -> str:
        if path.exists():
            current = path.read_bytes()
            if current == data:
                return "noop"
            if reject_on_conflict:
                raise AuthoringRegistryFSError(
                    "version conflict: existing payload differs from requested payload",
                    code=conflict_code or "registry_version_conflict",
                    path=conflict_path or "$",
                    details=conflict_details or {},
                )
        return "applied"


def _safe_id(text: str) -> str:
    collapsed = _SAFE_SEGMENT_RE.sub("_", text).strip("_")
    if not collapsed:
        collapsed = "x"
    digest = sha256_token(text.encode("utf-8"))[-8:]
    return f"{collapsed}__{digest}"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AuthoringRegistryFSError(f"missing registry object file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthoringRegistryFSError(f"invalid registry object JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthoringRegistryFSError(f"registry object must be JSON object: {path}")
    return payload


def _version_sort_key(value: Any) -> tuple[int, Any]:
    if isinstance(value, str):
        match = re.fullmatch(r"v(\d+)", value)
        if match:
            return (0, int(match.group(1)))
        return (1, value)
    return (2, str(value))
