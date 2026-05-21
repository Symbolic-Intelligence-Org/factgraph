"""A20(E) Slice 7B registry final-exit contract tests."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.sdk import FactGraph
from factgraph.audit.authoring_events import load_authoring_apply_events
from factgraph.sdk.registry import SDKRegistry
from factgraph.sdk.schema import Entity, Field, Identity


class _UserForA20E(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _write_event(path: Path, *, apply_request_id: str, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": "authoring_apply_execute_run",
        "apply_request_id": apply_request_id,
        "status": status,
        "ok": status == "ok",
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        fh.write("\n")


class ServiceRegistryFinalExitTests(unittest.TestCase):
    def test_all_registry_routes_return_removed_envelopes(self) -> None:
        from service.registry_v1 import (
            list_registry_assets,
            read_registry_inference,
            read_registry_manifest,
            read_registry_rule,
            read_registry_schema,
        )

        for func in (
            read_registry_manifest,
            read_registry_schema,
            list_registry_assets,
            read_registry_rule,
            read_registry_inference,
        ):
            with self.subTest(func=func.__name__):
                resp = func({"root_dir": "/tmp/ignored"})
                self.assertFalse(resp["ok"])
                self.assertEqual(len(resp["errors"]), 1)
                error = resp["errors"][0]
                self.assertEqual(error["kind"], "removed")
                self.assertEqual(error["path"], "$")
                self.assertIn("A20(E)", error["details"]["message"])


class ApplyLogMigrationTests(unittest.TestCase):
    def test_workspace_apply_log_writes_to_db_audit_and_reads_via_adapter(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=workspace)
            fg.save()
            registry_root = workspace / "registry"
            registry = FileAuthoringRegistry(registry_root)

            SDKRegistry(registry=registry).apply_schema_classes(
                [_UserForA20E],
                apply_request_id="apply-schema",
            )

            migrated_log = workspace / "db" / "audit" / "authoring_apply_events.jsonl"
            legacy_log = registry_root / "authoring_apply_events.jsonl"
            self.assertTrue(migrated_log.is_file())
            self.assertFalse(legacy_log.exists())
            self.assertEqual(registry.list_apply_run_ids(), ["apply-schema"])
            self.assertEqual(
                [
                    evt.raw.get("apply_request_id")
                    for evt in load_authoring_apply_events(registry_root)
                    if evt.raw.get("kind") == "authoring_apply_execute_run"
                ],
                ["apply-schema"],
            )

    def test_workspace_apply_log_readers_prefer_db_audit_over_legacy(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=workspace)
            fg.save()
            registry_root = workspace / "registry"
            legacy_log = registry_root / "authoring_apply_events.jsonl"
            migrated_log = workspace / "db" / "audit" / "authoring_apply_events.jsonl"
            _write_event(legacy_log, apply_request_id="same", status="legacy")
            _write_event(migrated_log, apply_request_id="same", status="migrated")

            registry = FileAuthoringRegistry(registry_root)
            self.assertEqual(registry.find_apply_execute_run("same")["status"], "migrated")
            self.assertEqual(registry.list_apply_execute_runs()[0]["status"], "migrated")
            self.assertEqual(
                [evt.raw.get("status") for evt in load_authoring_apply_events(registry_root)],
                ["legacy", "migrated"],
            )

    def test_non_workspace_apply_log_path_stays_legacy(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry_root = Path(tmp_dir) / "standalone-registry"
            registry = FileAuthoringRegistry(registry_root)

            SDKRegistry(registry=registry).apply_schema_classes(
                [_UserForA20E],
                apply_request_id="standalone",
            )

            self.assertTrue((registry_root / "authoring_apply_events.jsonl").is_file())
            self.assertEqual(
                [
                    evt.raw.get("apply_request_id")
                    for evt in load_authoring_apply_events(registry_root)
                    if evt.raw.get("kind") == "authoring_apply_execute_run"
                ],
                ["standalone"],
            )


class RegistryRootDeprecationTests(unittest.TestCase):
    def test_explicit_registry_root_warns_once_from_sdk_constructor_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                FactGraph.create(schema_classes=[_UserForA20E], registry_root=Path(tmp_dir))

            matches = [
                warning
                for warning in caught
                if issubclass(warning.category, DeprecationWarning)
                and "registry_root" in str(warning.message)
            ]
            self.assertEqual(len(matches), 1)

    def test_factgraph_load_and_direct_adapters_do_not_warn(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            FactGraph.create(schema_classes=[_UserForA20E], path=workspace).save()

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                FactGraph.load(workspace, schema_classes=[_UserForA20E])
                registry = FileAuthoringRegistry(Path(tmp_dir) / "registry")
                SDKRegistry(registry=registry)

            self.assertEqual(
                [
                    warning
                    for warning in caught
                    if issubclass(warning.category, DeprecationWarning)
                    and "registry_root" in str(warning.message)
                ],
                [],
            )


if __name__ == "__main__":
    unittest.main()
