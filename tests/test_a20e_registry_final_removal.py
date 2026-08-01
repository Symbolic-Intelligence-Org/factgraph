"""Slice 7C / Q6-A registry adapter final removal coverage.

Replaces the Slice 7B ``test_a20e_registry_final_exit.py`` file. Validates:

1. SDK constructor rejection of ``registry_root=`` / ``registry=`` with
   ``SDKStoreError`` (Q6-A (e.1)).
2. SDK class absence (``SDKRegistry``, ``SDKRegistryError``,
   ``FileAuthoringRegistry`` are gone).
3. Workspace manifest layout no longer carries a registry component
   (Q6-A (d) + R-1 from audit).
4. Migration CLI output classes: dry-run / migrated / noop / error
   (PF-5 amendment).
5. ``FactGraph.load_workspace(...)`` loudly rejects legacy ``registry/`` markers.
6. Service registry routes are gone (PF-6 amendment).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factgraph.core.schema.schema_ir import schema_digest
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class _UserForA20E(Entity):
    user_id: str = Identity()
    name: str = Field()


class SDKConstructorRejectionTests(unittest.TestCase):
    def test_create_rejects_registry_root(self) -> None:
        with self.assertRaises(SDKStoreError) as cm:
            FactGraph.create(
                schema_classes=[_UserForA20E],
                registry_root="/tmp/legacy-registry",
            )
        self.assertIn("registry_root=", str(cm.exception))

    def test_create_rejects_registry(self) -> None:
        with self.assertRaises(SDKStoreError) as cm:
            FactGraph.create(
                schema_classes=[_UserForA20E],
                registry=object(),
            )
        self.assertIn("registry_root=", str(cm.exception))

    def test_from_schema_classes_rejects_registry_root(self) -> None:
        with self.assertRaises(SDKStoreError):
            FactGraph.from_schema_classes(
                classes=[_UserForA20E],
                registry_root="/tmp/legacy-registry",
            )

    def test_init_rejects_registry_root(self) -> None:
        with self.assertRaises(SDKStoreError):
            FactGraph(
                [_UserForA20E],
                registry_root="/tmp/legacy-registry",
            )



class SDKSurfaceAbsenceTests(unittest.TestCase):
    def test_sdk_registry_class_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("factgraph.sdk.registry")

    def test_sdk_registry_error_is_gone(self) -> None:
        import factgraph.sdk as sdk

        self.assertNotIn("SDKRegistryError", sdk.__all__)
        self.assertFalse(hasattr(sdk, "SDKRegistryError"))

    def test_file_authoring_registry_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("factgraph.authoring.registry_fs")

    def test_authoring_registry_workflow_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("factgraph.authoring.registry_workflow")

    def test_authoring_apply_execute_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("factgraph.authoring.apply_execute")

    def test_service_registry_v1_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("service.registry_v1")

    def test_service_registry_io_is_gone(self) -> None:
        with self.assertRaises(ImportError):
            importlib.import_module("service._registry_io")

    def test_workspace_registry_constant_is_gone(self) -> None:
        from factgraph.application import workspace_runtime

        self.assertFalse(hasattr(workspace_runtime, "WORKSPACE_REGISTRY"))
        self.assertFalse(hasattr(workspace_runtime, "sync_registry_to_workspace"))

    def test_workspace_paths_has_no_registry_field(self) -> None:
        from factgraph.application.workspace_runtime import WorkspacePaths, resolve_workspace_paths

        paths = resolve_workspace_paths("/tmp/x")
        self.assertFalse(hasattr(paths, "registry"))
        self.assertEqual(
            set(WorkspacePaths.__dataclass_fields__.keys()),
            {"root", "manifest", "ledger"},
        )

    def test_database_workspace_paths_has_no_registry_field(self) -> None:
        from factgraph.core.store.database import DatabaseWorkspacePaths, resolve_database_workspace_paths

        paths = resolve_database_workspace_paths("/tmp/x")
        self.assertFalse(hasattr(paths, "registry"))
        self.assertNotIn("registry", DatabaseWorkspacePaths.__dataclass_fields__)


class WorkspaceManifestLayoutTests(unittest.TestCase):
    def test_save_writes_manifest_without_registry_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=tmp_dir)
            fg.save_workspace()
            manifest_path = Path(tmp_dir) / "factgraph_workspace.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            components = payload.get("components", {})
            self.assertNotIn("registry", components)
            self.assertEqual(components, {"db": "db/", "views": "views/"})
            self.assertTrue((Path(tmp_dir) / "db" / "assertions.db").is_file())
            fg.close()

    def test_load_rejects_legacy_registry_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=tmp_dir)
            fg.save_workspace()
            # Plant a legacy registry/ directory to trigger the rejection.
            legacy = Path(tmp_dir) / "registry"
            legacy.mkdir()
            with self.assertRaises(SDKStoreError) as cm:
                FactGraph.load_workspace(tmp_dir, schema_classes=[_UserForA20E])
            self.assertIn("migrate-workspace", str(cm.exception))


class MigrationCLIOutputTests(unittest.TestCase):
    """PF-5 amendment: 4 output classes (dry-run / migrated / noop / error)."""

    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        proc = subprocess.run(
            [sys.executable, "-m", "factgraph", *args],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={"PYTHONPATH": "src", **{k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}},
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_error_class_workspace_not_found(self) -> None:
        rc, stdout, stderr = self._run_cli(["migrate-workspace", "/nonexistent/path/should/not/exist"])
        self.assertEqual(rc, 1, f"stdout={stdout!r} stderr={stderr!r}")
        payload = json.loads(stderr)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["kind"], "workspace_not_found")

    def test_noop_class_already_migrated_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=tmp_dir)
            fg.save_workspace()
            fg.close()
            rc, stdout, stderr = self._run_cli(["migrate-workspace", tmp_dir])
            self.assertEqual(rc, 0, f"stderr={stderr!r}")
            payload = json.loads(stdout)
            self.assertEqual(payload["status"], "noop")
            self.assertEqual(payload["actions"], [])

    def test_dry_run_class_legacy_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=tmp_dir)
            fg.save_workspace()
            legacy = Path(tmp_dir) / "registry" / "schema"
            legacy.mkdir(parents=True)
            schema_path = legacy / "schema_ir.json"
            schema_path.write_text(json.dumps(fg.schema_ir, sort_keys=True), encoding="utf-8")
            fg.close()
            rc, stdout, stderr = self._run_cli(["migrate-workspace", tmp_dir, "--dry-run"])
            self.assertEqual(rc, 0, f"stderr={stderr!r}")
            payload = json.loads(stdout)
            self.assertEqual(payload["status"], "dry_run")
            self.assertTrue(len(payload["actions"]) >= 1)
            # Dry run must not have actually renamed legacy registry/.
            self.assertTrue(legacy.parent.exists())

    def test_migrated_class_legacy_workspace_to_db_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[_UserForA20E], path=tmp_dir)
            fg.save_workspace()
            legacy = Path(tmp_dir) / "registry" / "schema"
            legacy.mkdir(parents=True)
            schema_path = legacy / "schema_ir.json"
            schema_path.write_text(json.dumps(fg.schema_ir, sort_keys=True), encoding="utf-8")
            expected_digest = schema_digest(fg.schema_ir)
            fg.close()
            rc, stdout, stderr = self._run_cli(["migrate-workspace", tmp_dir])
            self.assertEqual(rc, 0, f"stderr={stderr!r}")
            payload = json.loads(stdout)
            self.assertEqual(payload["status"], "migrated")
            # Legacy registry/ should have been archived.
            self.assertFalse((Path(tmp_dir) / "registry").exists())
            archives = list(Path(tmp_dir).glob("registry.legacy.*"))
            self.assertEqual(len(archives), 1)
            # Subsequent load should succeed now.
            fg2 = FactGraph.load_workspace(tmp_dir, schema_classes=[_UserForA20E])
            self.assertEqual(schema_digest(fg2.schema_ir), expected_digest)
            fg2.close()


class ServiceRouteRemovalTests(unittest.TestCase):
    def test_service_app_v1_drops_registry_routes(self) -> None:
        from service.app_v1 import app

        registry_routes = [r for r in app.routes if "/v1/registry" in getattr(r, "path", "")]
        self.assertEqual(registry_routes, [])


class ApplyLogReadbackTests(unittest.TestCase):
    """Step 4.7 P1-3 fix + R-1: verify load_authoring_apply_events covers
    all three legacy + canonical read paths.
    """

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )

    def test_package_root_apply_log_is_read(self) -> None:
        from factgraph.audit.authoring_events import load_authoring_apply_events

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_jsonl(
                root / "authoring_apply_events.jsonl",
                [{"action_id": "pkg-1", "status": "ok"}],
            )
            events = load_authoring_apply_events(root)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].action_id, "pkg-1")

    def test_workspace_db_audit_apply_log_is_read(self) -> None:
        from factgraph.audit.authoring_events import load_authoring_apply_events

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_jsonl(
                root / "db" / "audit" / "authoring_apply_events.jsonl",
                [{"action_id": "ws-1", "status": "ok"}],
            )
            events = load_authoring_apply_events(root)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].action_id, "ws-1")

    def test_legacy_workspace_registry_apply_log_is_read(self) -> None:
        from factgraph.audit.authoring_events import load_authoring_apply_events

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "factgraph_workspace.json").write_text("{}", encoding="utf-8")
            (workspace / "db").mkdir()
            registry_dir = workspace / "registry"
            registry_dir.mkdir()
            self._write_jsonl(
                registry_dir / "authoring_apply_events.jsonl",
                [{"action_id": "legacy-1", "status": "ok"}],
            )
            events = load_authoring_apply_events(registry_dir)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].action_id, "legacy-1")

    def test_missing_apply_log_returns_empty_list(self) -> None:
        from factgraph.audit.authoring_events import load_authoring_apply_events

        with tempfile.TemporaryDirectory() as tmp_dir:
            events = load_authoring_apply_events(Path(tmp_dir))
            self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
