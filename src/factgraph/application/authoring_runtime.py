"""Application-layer authoring asset persistence helpers.

This module owns the registry-facing persistence contract for saved authoring
assets. SDK managers adapt these pure helpers into the ``fg.rules.*`` and
``fg.inferences.*`` facades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factgraph.authoring.registry_fs import AuthoringRegistryFSError, FileAuthoringRegistry
from factgraph.core.schema.schema_ir import ensure_schema_ir, schema_digest


class AuthoringRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class SavedRuleRef:
    """Registry handle for a saved rule asset.

    Returned by `fg.rules.save(...)`, `fg.rules.list()`, and
    `fg.rules.get(...)`. It is a load handle, not a runtime selector: call
    `fg.rules.load(ref)` to retrieve a `Rule` before running it.
    """

    rule_id: str
    version: str

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.rule_id, field_name="rule_id")
        _validate_non_empty_text(self.version, field_name="version")


@dataclass(frozen=True)
class SavedInferenceRef:
    """Registry handle for a saved inference asset.

    Returned by `fg.inferences.save(...)`, `fg.inferences.list()`, and
    `fg.inferences.get(...)`. It is a load handle, not a runtime selector:
    call `fg.inferences.load(ref)` before evaluation.
    """

    inference_id: str
    version: str

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.inference_id, field_name="inference_id")
        _validate_non_empty_text(self.version, field_name="version")


def save_rule(
    registry: FileAuthoringRegistry,
    rule_payload: dict[str, Any],
    *,
    schema_ir: dict[str, Any] | None = None,
) -> SavedRuleRef:
    _ensure_schema_if_requested(registry, schema_ir)
    try:
        result = registry.register_rule_spec(rule_payload)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    return SavedRuleRef(rule_id=str(result["rule_id"]), version=str(result["version"]))


def save_inference(
    registry: FileAuthoringRegistry,
    inference_payload: dict[str, Any],
    *,
    schema_ir: dict[str, Any] | None = None,
) -> SavedInferenceRef:
    _ensure_schema_if_requested(registry, schema_ir)
    try:
        result = registry.register_inference_spec(inference_payload)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    return SavedInferenceRef(inference_id=str(result["inference_id"]), version=str(result["version"]))


def load_rule(
    registry: FileAuthoringRegistry,
    rule: SavedRuleRef | str,
    *,
    version: str | None = None,
) -> dict[str, Any]:
    rule_id, rule_version = _resolve_rule_ref(rule, version=version)
    try:
        payload = registry.read_rule_spec(rule_id, rule_version)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    if payload is None:
        raise AuthoringRuntimeError(f"rule asset not found: {rule_id}@{rule_version}")
    return payload


def load_inference(
    registry: FileAuthoringRegistry,
    inference: SavedInferenceRef | str,
    *,
    version: str | None = None,
) -> dict[str, Any]:
    inference_id, inference_version = _resolve_inference_ref(inference, version=version)
    try:
        payload = registry.read_inference_spec(inference_id, inference_version)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    if payload is None:
        raise AuthoringRuntimeError(f"inference asset not found: {inference_id}@{inference_version}")
    return payload


def list_rules(registry: FileAuthoringRegistry) -> list[SavedRuleRef]:
    try:
        rows = [
            row
            for rule_id in registry.list_rule_ids()
            for row in registry.list_rule_versions(rule_id)
        ]
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    return [
        SavedRuleRef(rule_id=str(row["rule_id"]), version=str(row["version"]))
        for row in rows
    ]


def list_inferences(registry: FileAuthoringRegistry) -> list[SavedInferenceRef]:
    try:
        rows = [
            row
            for inference_id in registry.list_inference_ids()
            for row in registry.list_inference_versions(inference_id)
        ]
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    return [
        SavedInferenceRef(inference_id=str(row["inference_id"]), version=str(row["version"]))
        for row in rows
    ]


def get_rule(registry: FileAuthoringRegistry, rule_id: str) -> SavedRuleRef:
    _validate_non_empty_text(rule_id, field_name="rule_id")
    try:
        versions = registry.list_rule_versions(rule_id)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    if not versions:
        raise AuthoringRuntimeError(f"rule asset not found: {rule_id}")
    latest = versions[-1]
    return SavedRuleRef(rule_id=str(latest["rule_id"]), version=str(latest["version"]))


def get_inference(registry: FileAuthoringRegistry, inference_id: str) -> SavedInferenceRef:
    _validate_non_empty_text(inference_id, field_name="inference_id")
    try:
        versions = registry.list_inference_versions(inference_id)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc
    if not versions:
        raise AuthoringRuntimeError(f"inference asset not found: {inference_id}")
    latest = versions[-1]
    return SavedInferenceRef(inference_id=str(latest["inference_id"]), version=str(latest["version"]))


def get_latest_rule(registry: FileAuthoringRegistry, rule_id: str) -> SavedRuleRef:
    return get_rule(registry, rule_id)


def get_latest_inference(registry: FileAuthoringRegistry, inference_id: str) -> SavedInferenceRef:
    return get_inference(registry, inference_id)


def _ensure_schema_if_requested(
    registry: FileAuthoringRegistry,
    schema_ir: dict[str, Any] | None,
) -> None:
    if schema_ir is None:
        return
    validated = ensure_schema_ir(schema_ir)
    digest = schema_digest(validated)
    try:
        existing = registry.get_schema_entry()
        if existing is not None:
            existing_digest = existing.get("schema_digest")
            if existing_digest != digest:
                raise AuthoringRuntimeError(
                    "registry schema_digest mismatch; refusing to overwrite existing schema_ir"
                )
            registry.upsert_schema_ir(validated)
            return
        registry.upsert_schema_ir(validated)
    except AuthoringRegistryFSError as exc:
        raise AuthoringRuntimeError(str(exc)) from exc


def _resolve_rule_ref(rule: SavedRuleRef | str, *, version: str | None) -> tuple[str, str]:
    if isinstance(rule, SavedRuleRef):
        if version is not None and version != rule.version:
            raise AuthoringRuntimeError("version conflicts with SavedRuleRef.version")
        return rule.rule_id, rule.version
    _validate_non_empty_text(rule, field_name="rule_id")
    if not isinstance(version, str) or not version:
        raise AuthoringRuntimeError("version is required when loading by rule_id")
    return str(rule), version


def _resolve_inference_ref(
    inference: SavedInferenceRef | str,
    *,
    version: str | None,
) -> tuple[str, str]:
    if isinstance(inference, SavedInferenceRef):
        if version is not None and version != inference.version:
            raise AuthoringRuntimeError("version conflicts with SavedInferenceRef.version")
        return inference.inference_id, inference.version
    _validate_non_empty_text(inference, field_name="inference_id")
    if not isinstance(version, str) or not version:
        raise AuthoringRuntimeError("version is required when loading by inference_id")
    return str(inference), version


def _validate_non_empty_text(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise AuthoringRuntimeError(f"{field_name} must be non-empty string")


__all__ = [
    "AuthoringRuntimeError",
    "SavedInferenceRef",
    "SavedRuleRef",
    "get_inference",
    "get_latest_inference",
    "get_latest_rule",
    "get_rule",
    "list_inferences",
    "list_rules",
    "load_inference",
    "load_rule",
    "save_inference",
    "save_rule",
]
