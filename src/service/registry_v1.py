from __future__ import annotations

from pathlib import Path
from typing import Any

from factgraph.authoring import FileAuthoringRegistry

from ._common import error_response, exception_to_error, facade_error, ok_response
from ._registry_io import load_registry_schema_ir


# Q8 Phase 2 (Slice 6) note:
#   `read_registry_rule(...)` and `read_registry_inference(...)` now return
#   removed envelopes because the underlying SavedRule/SavedInference
#   persistence was removed in Slice 6. Callers should construct in-memory
#   `Rule(...)` / `Inference(...)` values directly.
#   `list_registry_assets(...)` no longer reports `rule_ids` / `inference_ids`
#   fields; the response is locked to schema_entry + apply_run_ids.


_SAVEDRULE_PHASE2_REMOVED_DETAILS = {
    "message": (
        "registry-backed SavedRule/SavedInference persistence was removed by "
        "Q8 Phase 2; use in-memory Rule(...) / Inference(...) instead of "
        "registry-backed reads"
    ),
}


def read_registry_manifest(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        registry = _registry_from_dto(dto)
        return ok_response(manifest=registry.read_manifest())
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def read_registry_schema(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        root_dir = _root_dir_from_dto(dto)
        return ok_response(schema_ir=load_registry_schema_ir(root_dir))
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def list_registry_assets(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        registry = _registry_from_dto(dto)
        return ok_response(
            registry={
                "schema_entry": registry.get_schema_entry(),
                "apply_run_ids": registry.list_apply_run_ids(),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def read_registry_rule(dto: dict[str, Any]) -> dict[str, Any]:
    return error_response(
        [
            {
                "kind": "removed",
                "path": "$",
                "details": dict(_SAVEDRULE_PHASE2_REMOVED_DETAILS),
            }
        ]
    )


def read_registry_inference(dto: dict[str, Any]) -> dict[str, Any]:
    return error_response(
        [
            {
                "kind": "removed",
                "path": "$",
                "details": dict(_SAVEDRULE_PHASE2_REMOVED_DETAILS),
            }
        ]
    )


def _registry_from_dto(dto: dict[str, Any]) -> FileAuthoringRegistry:
    return FileAuthoringRegistry(Path(_root_dir_from_dto(dto)))


def _root_dir_from_dto(dto: dict[str, Any]) -> str:
    if not isinstance(dto, dict):
        raise facade_error("dto must be object", kind="shape", path="$")
    return _require_non_empty_str(dto.get("root_dir"), path="$.root_dir")


def _require_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise facade_error("must be non-empty string", kind="shape", path=path)
    return value
