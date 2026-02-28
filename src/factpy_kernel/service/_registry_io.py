from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factpy_kernel.authoring import FileAuthoringRegistry

from ._common import facade_error


def load_registry_schema_ir(root_dir: str | Path) -> dict[str, Any]:
    registry = FileAuthoringRegistry(Path(root_dir))
    entry = registry.get_schema_entry()
    if not isinstance(entry, dict):
        raise facade_error(
            "registry schema entry not found",
            kind="registry_schema_missing",
            path="$.registry_root",
            details={"root_dir": str(root_dir)},
        )
    rel_path = entry.get("path")
    if not isinstance(rel_path, str) or not rel_path:
        raise facade_error(
            "registry schema entry missing path",
            kind="registry_schema_manifest_entry_invalid",
            path="$.registry_root",
            details={"root_dir": str(root_dir)},
        )
    abs_path = Path(root_dir) / rel_path
    try:
        payload = json.loads(abs_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise facade_error(
            "registry schema file not found",
            kind="registry_schema_missing",
            path="$.registry_root",
            details={"root_dir": str(root_dir), "schema_path": str(abs_path)},
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise facade_error(
            f"failed to read registry schema_ir: {exc}",
            kind="registry_schema_read_failed",
            path="$.registry_root",
            details={"root_dir": str(root_dir), "schema_path": str(abs_path)},
        ) from exc
    if not isinstance(payload, dict):
        raise facade_error(
            "registry schema_ir file must contain JSON object",
            kind="registry_schema_invalid",
            path="$.registry_root",
            details={"root_dir": str(root_dir), "schema_path": str(abs_path)},
        )
    return payload
