from __future__ import annotations

from pathlib import Path
from typing import Any

from factpy_kernel.authoring import (
    AuthoringApplyExecuteError,
    AuthoringRegistryFSError,
    FileAuthoringRegistry,
    build_authoring_publish_workflow_apply_bundle_dto,
)

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

    def register_derivation_spec(self, derivation_spec_payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._registry.register_derivation_spec(derivation_spec_payload)
        except AuthoringRegistryFSError as exc:
            raise SDKRegistryError(str(exc)) from exc

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
