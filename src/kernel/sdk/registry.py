from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.authoring import (
    AuthoringApplyExecuteError,
    AuthoringRegistryFSError,
    FileAuthoringRegistry,
    build_authoring_publish_workflow_apply_bundle_dto,
)
from kernel.authoring.derivations import compile_authoring_derivation_v1
from kernel.authoring.rules import compile_authoring_rule_v1

from .compile import build_authoring_schema_from_classes
from .errors import SDKRegistryError
from .schema import Entity


class SDKRegistry:
    def __init__(
        self,
        root_dir: str | Path | None = None,
        *,
        registry: FileAuthoringRegistry | None = None,
    ) -> None:
        if registry is not None and root_dir is not None and Path(root_dir) != registry.root_dir:
            raise SDKRegistryError("root_dir and registry.root_dir must match when both are provided")
        if registry is None and root_dir is None:
            raise SDKRegistryError("provide root_dir or registry")
        self._registry = registry if registry is not None else FileAuthoringRegistry(Path(root_dir))

    @property
    def registry(self) -> FileAuthoringRegistry:
        return self._registry

    @property
    def root_dir(self) -> Path:
        return self._registry.root_dir

    def apply_schema_classes(
        self,
        classes: list[type[Entity]],
        *,
        apply_request_id: str | None = None,
        transaction_policy: str | None = None,
    ) -> dict[str, Any]:
        authoring_schema = build_authoring_schema_from_classes(classes)
        return self.apply_authoring_bundle(
            authoring_schema=authoring_schema,
            apply_request_id=apply_request_id,
            transaction_policy=transaction_policy,
        )

    def apply_authoring_bundle(
        self,
        *,
        authoring_schema: dict[str, Any] | None = None,
        rule_request: dict[str, Any] | None = None,
        derivation_request: dict[str, Any] | None = None,
        apply_request_id: str | None = None,
        transaction_policy: str | None = None,
        store: Any | None = None,
        schema_ir: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return build_authoring_publish_workflow_apply_bundle_dto(
                registry=self._registry,
                store=store,
                schema_ir=schema_ir,
                authoring_schema=authoring_schema,
                rule_request=rule_request,
                derivation_request=derivation_request,
                apply_request_id=apply_request_id,
                transaction_policy=transaction_policy,
            )
        except (AuthoringApplyExecuteError, AuthoringRegistryFSError) as exc:
            raise SDKRegistryError(str(exc)) from exc

    def read_manifest(self) -> dict[str, Any]:
        try:
            return self._registry.read_manifest()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def upsert_schema_ir(self, schema_ir: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._registry.upsert_schema_ir(schema_ir)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def register_rule_spec(self, rule_spec_payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._registry.register_rule_spec(rule_spec_payload)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def register_rule(self, rule: Any, *, schema_ir: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = rule.to_authoring_payload() if hasattr(rule, "to_authoring_payload") else rule
        if not isinstance(payload, dict):
            raise SDKRegistryError("rule must be SDK Rule object or authoring rule payload dict")
        try:
            compiled = compile_authoring_rule_v1(payload, schema_ir=schema_ir)
        except Exception as exc:
            raise SDKRegistryError(str(exc)) from exc
        return self.register_rule_spec(compiled)

    def register_derivation_spec(self, derivation_spec_payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._registry.register_derivation_spec(derivation_spec_payload)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def register_derivation(self, derivation: Any, *, schema_ir: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = derivation.to_authoring_payload() if hasattr(derivation, "to_authoring_payload") else derivation
        if not isinstance(payload, dict):
            raise SDKRegistryError("derivation must be SDK Derivation object or authoring derivation payload dict")
        _reject_multi_head_derivation_payload(payload)
        try:
            compiled = compile_authoring_derivation_v1(payload, schema_ir=schema_ir)
        except Exception as exc:
            if schema_ir is None:
                fallback_schema_ir = self._read_registry_schema_ir()
                if fallback_schema_ir is not None:
                    try:
                        compiled = compile_authoring_derivation_v1(payload, schema_ir=fallback_schema_ir)
                    except Exception as retry_exc:
                        raise SDKRegistryError(str(retry_exc)) from retry_exc
                else:
                    raise SDKRegistryError(str(exc)) from exc
            else:
                raise SDKRegistryError(str(exc)) from exc
        return self.register_derivation_spec(compiled)

    def _read_registry_schema_ir(self) -> dict[str, Any] | None:
        try:
            schema_entry = self._registry.get_schema_entry()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc
        if not isinstance(schema_entry, dict):
            return None
        rel_path = schema_entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            return None
        abs_path = self.root_dir / rel_path
        if not abs_path.exists():
            return None
        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SDKRegistryError(f"failed to read registry schema_ir: {exc}") from exc
        if not isinstance(data, dict):
            raise SDKRegistryError("registry schema_ir file must contain JSON object")
        return data

    def get_schema_entry(self) -> dict[str, Any] | None:
        try:
            return self._registry.get_schema_entry()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_rule_ids(self) -> list[str]:
        try:
            return self._registry.list_rule_ids()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_derivation_ids(self) -> list[str]:
        try:
            return self._registry.list_derivation_ids()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_rule_versions(self, rule_id: str) -> list[dict[str, Any]]:
        try:
            return self._registry.list_rule_versions(rule_id)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_derivation_versions(self, derivation_id: str) -> list[dict[str, Any]]:
        try:
            return self._registry.list_derivation_versions(derivation_id)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_apply_run_ids(self) -> list[str]:
        try:
            return self._registry.list_apply_run_ids()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def list_apply_runs(self) -> list[dict[str, Any]]:
        try:
            return self._registry.list_apply_execute_runs()
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def show_apply_run(self, apply_request_id: str) -> dict[str, Any] | None:
        try:
            return self._registry.find_apply_execute_run(apply_request_id)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def get_latest_rule_spec(self, rule_id: str) -> dict[str, Any] | None:
        try:
            return self._registry.get_latest_rule_spec(rule_id)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def get_latest_derivation_spec(self, derivation_id: str) -> dict[str, Any] | None:
        try:
            return self._registry.get_latest_derivation_spec(derivation_id)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def read_rule_spec(self, rule_id: str, version: str) -> dict[str, Any] | None:
        try:
            return self._registry.read_rule_spec(rule_id, version)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

    def read_derivation_spec(self, derivation_id: str, version: str) -> dict[str, Any] | None:
        try:
            return self._registry.read_derivation_spec(derivation_id, version)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc


def _reject_multi_head_derivation_payload(payload: dict[str, Any]) -> None:
    if isinstance(payload.get("head"), list):
        raise SDKRegistryError("multi-head Derivation is not accepted in Track 1; use one Derivation per head")
