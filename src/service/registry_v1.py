from __future__ import annotations

from typing import Any

from ._common import error_response


_REGISTRY_PHASE3_REMOVED_DETAILS = {
    "message": (
        "registry-backed authoring APIs were removed by A20(E) registry final "
        "exit; use FactGraph workspace APIs and in-memory Rule(...) / "
        "Inference(...) values instead of registry-backed service reads"
    ),
}


def read_registry_manifest(dto: dict[str, Any]) -> dict[str, Any]:
    return _registry_removed_response()


def read_registry_schema(dto: dict[str, Any]) -> dict[str, Any]:
    return _registry_removed_response()


def list_registry_assets(dto: dict[str, Any]) -> dict[str, Any]:
    return _registry_removed_response()


def read_registry_rule(dto: dict[str, Any]) -> dict[str, Any]:
    return _registry_removed_response()


def read_registry_inference(dto: dict[str, Any]) -> dict[str, Any]:
    return _registry_removed_response()


def _registry_removed_response() -> dict[str, Any]:
    return error_response(
        [
            {
                "kind": "removed",
                "path": "$",
                "details": dict(_REGISTRY_PHASE3_REMOVED_DETAILS),
            }
        ]
    )
