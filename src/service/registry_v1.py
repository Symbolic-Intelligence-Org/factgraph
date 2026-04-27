from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.authoring import FileAuthoringRegistry

from ._common import error_response, exception_to_error, facade_error, ok_response
from ._registry_io import load_registry_schema_ir


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
                "rule_ids": registry.list_rule_ids(),
                "derivation_ids": registry.list_derivation_ids(),
                "apply_run_ids": registry.list_apply_run_ids(),
            }
        )
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def read_registry_rule(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        registry = _registry_from_dto(dto)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        rule_id = _require_non_empty_str(dto.get("rule_id"), path="$.rule_id")
        version = dto.get("version")
        if version is None:
            payload = registry.get_latest_rule_spec(rule_id)
        else:
            payload = registry.read_rule_spec(rule_id, _require_non_empty_str(version, path="$.version"))
        return ok_response(rule_spec=payload)
    except Exception as exc:
        return error_response([exception_to_error(exc)])


def read_registry_derivation(dto: dict[str, Any]) -> dict[str, Any]:
    try:
        registry = _registry_from_dto(dto)
        if not isinstance(dto, dict):
            raise facade_error("dto must be object", kind="shape", path="$")
        derivation_id = _require_non_empty_str(dto.get("derivation_id"), path="$.derivation_id")
        version = dto.get("version")
        if version is None:
            payload = registry.get_latest_derivation_spec(derivation_id)
        else:
            payload = registry.read_derivation_spec(
                derivation_id,
                _require_non_empty_str(version, path="$.version"),
            )
        return ok_response(derivation_spec=payload)
    except Exception as exc:
        return error_response([exception_to_error(exc)])


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
