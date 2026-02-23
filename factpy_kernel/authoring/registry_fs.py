from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from factpy_kernel.authoring.derivation_compile import compile_authoring_derivation_v1
from factpy_kernel.protocol.digests import sha256_token
from factpy_kernel.rules.rule_ir import RuleSpec
from factpy_kernel.schema.schema_ir import canonicalize_schema_ir_jcs, ensure_schema_ir, schema_digest


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_.-]+")


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
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    @property
    def manifest_path(self) -> Path:
        return self.root_dir / "registry_manifest.json"

    @property
    def apply_log_path(self) -> Path:
        return self.root_dir / "authoring_apply_events.jsonl"

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

    def register_rule_spec(self, rule_spec_payload: dict[str, Any]) -> dict[str, Any]:
        canonical = _canonical_rule_spec_payload(rule_spec_payload)
        rule_id = str(canonical["rule_id"])
        version = str(canonical["version"])
        data = _canonical_json_bytes(canonical)
        rel_dir = f"rules/{_safe_id(rule_id)}"
        rel_path = f"{rel_dir}/{_safe_id(version)}.json"
        abs_path = self.root_dir / rel_path
        write_status = self._write_if_changed(
            abs_path,
            data + b"\n",
            reject_on_conflict=True,
            conflict_code="registry_rule_version_conflict",
            conflict_path=f"$.rules[{rule_id}@{version}]",
            conflict_details={"rule_id": rule_id, "version": version},
        )

        manifest = self._load_manifest()
        rules = _normalize_manifest_items(manifest.get("rules"))
        key = f"{rule_id}@{version}"
        rules[key] = {
            "rule_id": rule_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
        }
        manifest["rules"] = [rules[k] for k in sorted(rules)]
        self._save_manifest(manifest)
        return {
            "kind": "rule",
            "status": write_status,
            "rule_id": rule_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
        }

    def preview_register_rule_spec(self, rule_spec_payload: dict[str, Any]) -> dict[str, Any]:
        canonical = _canonical_rule_spec_payload(rule_spec_payload)
        rule_id = str(canonical["rule_id"])
        version = str(canonical["version"])
        data = _canonical_json_bytes(canonical)
        rel_dir = f"rules/{_safe_id(rule_id)}"
        rel_path = f"{rel_dir}/{_safe_id(version)}.json"
        abs_path = self.root_dir / rel_path
        preview_status = self._preview_write_if_changed(
            abs_path,
            data + b"\n",
            reject_on_conflict=True,
            conflict_code="registry_rule_version_conflict",
            conflict_path=f"$.rules[{rule_id}@{version}]",
            conflict_details={"rule_id": rule_id, "version": version},
        )
        return {
            "kind": "rule",
            "status": preview_status,
            "rule_id": rule_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
        }

    def register_derivation_spec(self, derivation_spec_payload: dict[str, Any]) -> dict[str, Any]:
        canonical = compile_authoring_derivation_v1(derivation_spec_payload)
        derivation_id = str(canonical["derivation_id"])
        version = str(canonical["version"])
        data = _canonical_json_bytes(canonical)
        rel_dir = f"derivations/{_safe_id(derivation_id)}"
        rel_path = f"{rel_dir}/{_safe_id(version)}.json"
        abs_path = self.root_dir / rel_path
        write_status = self._write_if_changed(
            abs_path,
            data + b"\n",
            reject_on_conflict=True,
            conflict_code="registry_derivation_version_conflict",
            conflict_path=f"$.derivations[{derivation_id}@{version}]",
            conflict_details={"derivation_id": derivation_id, "version": version},
        )

        manifest = self._load_manifest()
        derivations = _normalize_manifest_items(manifest.get("derivations"))
        key = f"{derivation_id}@{version}"
        derivations[key] = {
            "derivation_id": derivation_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
            "target_pred_id": canonical.get("target_pred_id"),
        }
        manifest["derivations"] = [derivations[k] for k in sorted(derivations)]
        self._save_manifest(manifest)
        return {
            "kind": "derivation",
            "status": write_status,
            "derivation_id": derivation_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
        }

    def preview_register_derivation_spec(self, derivation_spec_payload: dict[str, Any]) -> dict[str, Any]:
        canonical = compile_authoring_derivation_v1(derivation_spec_payload)
        derivation_id = str(canonical["derivation_id"])
        version = str(canonical["version"])
        data = _canonical_json_bytes(canonical)
        rel_dir = f"derivations/{_safe_id(derivation_id)}"
        rel_path = f"{rel_dir}/{_safe_id(version)}.json"
        abs_path = self.root_dir / rel_path
        preview_status = self._preview_write_if_changed(
            abs_path,
            data + b"\n",
            reject_on_conflict=True,
            conflict_code="registry_derivation_version_conflict",
            conflict_path=f"$.derivations[{derivation_id}@{version}]",
            conflict_details={"derivation_id": derivation_id, "version": version},
        )
        return {
            "kind": "derivation",
            "status": preview_status,
            "derivation_id": derivation_id,
            "version": version,
            "path": rel_path,
            "digest": sha256_token(data),
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
        if not self.apply_log_path.exists():
            return None
        matched: dict[str, Any] | None = None
        for line_no, line in enumerate(self.apply_log_path.read_text(encoding="utf-8").splitlines(), start=1):
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
            if not isinstance(payload, dict):
                continue
            if payload.get("kind") != "authoring_apply_execute_run":
                continue
            if payload.get("apply_request_id") != apply_request_id:
                continue
            matched = payload
        return matched

    def list_apply_execute_runs(self) -> list[dict[str, Any]]:
        if not self.apply_log_path.exists():
            return []
        latest_by_request: dict[str, dict[str, Any]] = {}
        for line_no, line in enumerate(self.apply_log_path.read_text(encoding="utf-8").splitlines(), start=1):
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

    def list_rule_ids(self) -> list[str]:
        manifest = self._load_manifest()
        rules = _normalize_manifest_items(manifest.get("rules"))
        return sorted(
            {
                str(item.get("rule_id"))
                for item in rules.values()
                if isinstance(item.get("rule_id"), str) and item.get("rule_id")
            }
        )

    def list_derivation_ids(self) -> list[str]:
        manifest = self._load_manifest()
        derivations = _normalize_manifest_items(manifest.get("derivations"))
        return sorted(
            {
                str(item.get("derivation_id"))
                for item in derivations.values()
                if isinstance(item.get("derivation_id"), str) and item.get("derivation_id")
            }
        )

    def list_rule_versions(self, rule_id: str) -> list[dict[str, Any]]:
        if not isinstance(rule_id, str) or not rule_id:
            raise AuthoringRegistryFSError("rule_id must be non-empty string")
        manifest = self._load_manifest()
        rows = _normalize_manifest_items(manifest.get("rules"))
        out = [
            dict(item)
            for item in rows.values()
            if isinstance(item.get("rule_id"), str) and item.get("rule_id") == rule_id
        ]
        return sorted(out, key=lambda row: _version_sort_key(row.get("version")))

    def list_derivation_versions(self, derivation_id: str) -> list[dict[str, Any]]:
        if not isinstance(derivation_id, str) or not derivation_id:
            raise AuthoringRegistryFSError("derivation_id must be non-empty string")
        manifest = self._load_manifest()
        rows = _normalize_manifest_items(manifest.get("derivations"))
        out = [
            dict(item)
            for item in rows.values()
            if isinstance(item.get("derivation_id"), str) and item.get("derivation_id") == derivation_id
        ]
        return sorted(out, key=lambda row: _version_sort_key(row.get("version")))

    def get_latest_rule_spec(self, rule_id: str) -> dict[str, Any] | None:
        versions = self.list_rule_versions(rule_id)
        if not versions:
            return None
        latest = versions[-1]
        path = latest.get("path")
        if not isinstance(path, str) or not path:
            raise AuthoringRegistryFSError(
                "rule manifest entry missing path",
                code="registry_rule_manifest_entry_invalid",
                path="$.rules",
                details={"rule_id": rule_id},
            )
        payload = _read_json_object(self.root_dir / path)
        return payload

    def read_rule_spec(self, rule_id: str, version: str) -> dict[str, Any] | None:
        if not isinstance(rule_id, str) or not rule_id:
            raise AuthoringRegistryFSError("rule_id must be non-empty string")
        if not isinstance(version, str) or not version:
            raise AuthoringRegistryFSError("version must be non-empty string")
        manifest = self._load_manifest()
        rules = _normalize_manifest_items(manifest.get("rules"))
        item = rules.get(f"{rule_id}@{version}")
        if item is None:
            return None
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise AuthoringRegistryFSError(
                "rule manifest entry missing path",
                code="registry_rule_manifest_entry_invalid",
                path="$.rules",
                details={"rule_id": rule_id, "version": version},
            )
        return _read_json_object(self.root_dir / path)

    def get_latest_derivation_spec(self, derivation_id: str) -> dict[str, Any] | None:
        versions = self.list_derivation_versions(derivation_id)
        if not versions:
            return None
        latest = versions[-1]
        path = latest.get("path")
        if not isinstance(path, str) or not path:
            raise AuthoringRegistryFSError(
                "derivation manifest entry missing path",
                code="registry_derivation_manifest_entry_invalid",
                path="$.derivations",
                details={"derivation_id": derivation_id},
            )
        payload = _read_json_object(self.root_dir / path)
        return payload

    def read_derivation_spec(self, derivation_id: str, version: str) -> dict[str, Any] | None:
        if not isinstance(derivation_id, str) or not derivation_id:
            raise AuthoringRegistryFSError("derivation_id must be non-empty string")
        if not isinstance(version, str) or not version:
            raise AuthoringRegistryFSError("version must be non-empty string")
        manifest = self._load_manifest()
        derivations = _normalize_manifest_items(manifest.get("derivations"))
        item = derivations.get(f"{derivation_id}@{version}")
        if item is None:
            return None
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise AuthoringRegistryFSError(
                "derivation manifest entry missing path",
                code="registry_derivation_manifest_entry_invalid",
                path="$.derivations",
                details={"derivation_id": derivation_id, "version": version},
            )
        return _read_json_object(self.root_dir / path)

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "authoring_registry_fs_version": "authoring_registry_fs_v1",
                "schema": None,
                "rules": [],
                "derivations": [],
            }
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuthoringRegistryFSError(f"invalid registry manifest: {exc}") from exc
        if not isinstance(payload, dict):
            raise AuthoringRegistryFSError("registry manifest must be object")
        payload.setdefault("authoring_registry_fs_version", "authoring_registry_fs_v1")
        payload.setdefault("schema", None)
        payload.setdefault("rules", [])
        payload.setdefault("derivations", [])
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


def _canonical_rule_spec_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise AuthoringRegistryFSError("rule_spec_payload must be object")
    try:
        spec = RuleSpec(
            rule_id=payload["rule_id"],
            version=payload["version"],
            select_vars=payload["select_vars"],
            where=payload["where"],
            expose=bool(payload.get("expose", False)),
        )
    except Exception as exc:  # noqa: BLE001 - normalize to registry error
        raise AuthoringRegistryFSError(f"invalid rule spec payload: {exc}") from exc

    out: dict[str, Any] = {
        "rule_id": spec.rule_id,
        "version": spec.version,
        "select_vars": list(spec.select_vars),
        "where": spec.where,
    }
    if spec.expose:
        out["expose"] = True
    return out


def _normalize_manifest_items(value: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        if "rule_id" in item and "version" in item:
            key = f"{item.get('rule_id')}@{item.get('version')}"
        elif "derivation_id" in item and "version" in item:
            key = f"{item.get('derivation_id')}@{item.get('version')}"
        else:
            continue
        out[key] = item
    return out


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
