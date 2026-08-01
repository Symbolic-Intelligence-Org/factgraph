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
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factgraph.application.workspace_runtime import (
    save_workspace as save_v02_workspace,
    save_workspace_manifest,
)
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.store.database import write_schema_object_for_workspace
from factgraph.core.store.ledger import MetaRow, _enc, _enc_rest_terms
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


class _UserForA20E(Entity):
    user_id: str = Identity()
    name: str = Field()


class V02MigrationUser(Entity):
    user_id: str = Identity()
    name: str = Field()
    payload: bytes = Field()


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

    def test_missing_and_noop_paths_report_interrupted_replacement_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir)
            missing = parent / "workspace"
            backup = parent / "workspace.legacy-20260801T000000Z"
            backup.mkdir()

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(missing)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            payload = json.loads(stderr)
            self.assertEqual(payload["kind"], "workspace_recovery_required")
            self.assertEqual(
                payload["details"]["recovery_candidates"],
                [str(backup.resolve())],
            )
            self.assertFalse(payload["details"]["replacement_present"])

            fg = FactGraph.create(schema_classes=[_UserForA20E], path=missing)
            fg.close()
            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(missing)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            payload = json.loads(stderr)
            self.assertEqual(payload["kind"], "workspace_recovery_required")
            self.assertTrue(payload["details"]["replacement_present"])

    def test_incomplete_and_registry_only_sources_do_not_loop_as_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            incomplete = Path(tmp_dir) / "torn-create"
            (incomplete / "db").mkdir(parents=True)
            (incomplete / "factgraph_workspace.json").write_text(
                json.dumps(
                    {
                        "factgraph_workspace_version": "1",
                        "components": {"db": "db/", "views": "views/"},
                    }
                ),
                encoding="utf-8",
            )
            (incomplete / "db" / "meta.json").write_text("{}", encoding="utf-8")

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(incomplete)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            self.assertEqual(json.loads(stderr)["kind"], "workspace_incomplete")

            registry_only = Path(tmp_dir) / "registry-only"
            schema_dir = registry_only / "registry" / "schema"
            schema_dir.mkdir(parents=True)
            schema_graph = FactGraph.create(schema_classes=[_UserForA20E])
            schema_ir = schema_graph.schema_ir
            schema_graph.close()
            (schema_dir / "schema_ir.json").write_text(
                json.dumps(schema_ir, sort_keys=True),
                encoding="utf-8",
            )
            (registry_only / "factgraph_workspace.json").write_text(
                json.dumps(
                    {
                        "factgraph_workspace_version": "1",
                        "schema_digest": schema_digest(schema_ir),
                        "components": {"registry": "registry/"},
                    }
                ),
                encoding="utf-8",
            )

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(registry_only)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            self.assertEqual(json.loads(stderr)["kind"], "workspace_incomplete")
            self.assertFalse((registry_only / "db" / "assertions.db").exists())

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

    def test_v02_workspace_round_trip_preserves_rows_and_becomes_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "legacy workspace"
            legacy = FactGraph.from_schema_classes([V02MigrationUser])
            e_ref = legacy.entities.create(V02MigrationUser, user_id="alice")
            superseded_id = legacy.fields.set(
                V02MigrationUser.name,
                e_ref,
                "Alice One",
                meta={"source": "v0.2"},
            )
            current_id = legacy.fields.set(
                V02MigrationUser.name,
                e_ref,
                "Alice Two",
                meta={"source": "v0.2"},
            )
            revoker_id = legacy.assertions.retract(superseded_id)
            payload_id = legacy.fields.set(
                V02MigrationUser.payload,
                e_ref,
                b"\x00v0.2\xff",
            )
            legacy.assertions.append_meta(current_id, "reviewed", False)
            legacy.assertions.append_meta(current_id, "reviewed", True)
            expected_claims = tuple(legacy.ledger.claims)
            expected_args = tuple(legacy.ledger.claim_args)
            expected_revokes = tuple(legacy.ledger.revokes)
            expected_user_meta = tuple(legacy.ledger.meta_rows)
            expected_ids = {claim.asrt_id for claim in expected_claims}
            self.assertFalse(any(asrt_id.startswith("asrt:") for asrt_id in expected_ids))
            self.assertEqual(legacy.ledger.find_revoker(superseded_id), revoker_id)

            digest = schema_digest(legacy.schema_ir)
            save_v02_workspace(
                workspace,
                schema_digest=digest,
                ledger=legacy.ledger,
            )
            write_schema_object_for_workspace(workspace, legacy.schema_ir)
            legacy.ledger.close()

            rc, stdout, stderr = self._run_cli(
                ["migrate-workspace", str(workspace), "--dry-run"]
            )
            self.assertEqual(rc, 0, f"stderr={stderr!r}")
            dry_run = json.loads(stdout)
            self.assertEqual(dry_run["status"], "dry_run")
            self.assertTrue((workspace / "ledger.db").is_file())
            self.assertFalse((workspace / "db" / "assertions.db").is_file())

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(workspace)])
            self.assertEqual(rc, 0, f"stdout={stdout!r} stderr={stderr!r}")
            migrated = json.loads(stdout)
            self.assertEqual(migrated["status"], "migrated")
            self.assertEqual(migrated["schema_digest"], digest)
            self.assertTrue(migrated["head_tx_id"].startswith("tx:"))
            self.assertFalse((workspace / "ledger.db").exists())
            manifest = json.loads(
                (workspace / "factgraph_workspace.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["components"], {"db": "db/", "views": "views/"})
            archives = list(workspace.glob("workspace.legacy.*"))
            self.assertEqual(len(archives), 1)
            self.assertTrue((archives[0] / "ledger.db").is_file())
            self.assertTrue((archives[0] / "factgraph_workspace.json").is_file())

            loaded = FactGraph.load_workspace(
                workspace,
                schema_classes=[V02MigrationUser],
            )
            try:
                self.assertEqual(tuple(loaded.ledger.claims), expected_claims)
                self.assertEqual(tuple(loaded.ledger.claim_args), expected_args)
                self.assertEqual(tuple(loaded.ledger.revokes), expected_revokes)
                self.assertEqual(loaded.fields.get(V02MigrationUser.name, e_ref), "Alice Two")
                self.assertEqual(
                    loaded.fields.get(V02MigrationUser.payload, e_ref),
                    b"\x00v0.2\xff",
                )
                self.assertEqual(
                    [
                        row.value
                        for row in loaded.ledger.find_meta(
                            asrt_id=current_id,
                            key="reviewed",
                        )
                    ],
                    [False, True],
                )
                self.assertEqual(
                    tuple(
                        row
                        for row in loaded.ledger.meta_rows
                        if row.key not in {"assertion_digest", "schema_digest", "tx_id"}
                    ),
                    expected_user_meta,
                )
                self.assertEqual(
                    loaded.ledger.find_meta(asrt_id=current_id, key="reviewed")[-1].value,
                    True,
                )
                self.assertIn(payload_id, {claim.asrt_id for claim in loaded.ledger.claims})
                head = loaded._database.head()
                self.assertEqual(head.tx_seq, 0)
                self.assertEqual(head.tx_id, migrated["head_tx_id"])
                self.assertEqual(
                    loaded.ledger.get_ledger_meta("migration_source_version"),
                    "v0.2",
                )

                managed_ref = loaded.entities.ref(V02MigrationUser, user_id="alice")
                self.assertEqual(managed_ref, e_ref)
                replacement_id = loaded.fields.set(
                    V02MigrationUser.name,
                    managed_ref,
                    "Alice Three",
                )
                self.assertTrue(replacement_id.startswith("asrt:"))
                self.assertEqual(loaded._database.head().tx_seq, 1)
                self.assertEqual(loaded.fields.get(V02MigrationUser.name, e_ref), "Alice Three")
            finally:
                loaded.close()

    def test_released_seven_table_v02_fixture_migrates_directly_to_three_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "released-seven-table"
            workspace.mkdir()
            source = workspace / "ledger.db"
            claim_id = "1" * 32
            edge_id = "2" * 32
            revoker_id = "3" * 32
            alice_ref = "idref_v1:User:alice"
            bob_ref = "idref_v1:User:bob"
            edge_terms = [("entity_ref", bob_ref), ("string", "context")]
            conn = sqlite3.connect(source)
            try:
                conn.executescript(
                    """
                    CREATE TABLE claims (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        asrt_id TEXT NOT NULL UNIQUE,
                        pred_id TEXT NOT NULL,
                        e_ref TEXT NOT NULL,
                        rest_terms TEXT NOT NULL
                    );
                    CREATE TABLE claim_args (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asrt_id TEXT NOT NULL,
                        idx INTEGER NOT NULL,
                        val_atom TEXT NOT NULL,
                        tag TEXT NOT NULL
                    );
                    CREATE TABLE meta_rows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asrt_id TEXT NOT NULL,
                        key TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE revokes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        revoker_asrt_id TEXT NOT NULL,
                        revoked_asrt_id TEXT NOT NULL
                    );
                    CREATE TABLE ingest_keys (
                        ingest_key TEXT PRIMARY KEY,
                        asrt_id TEXT NOT NULL,
                        kind TEXT NOT NULL
                    );
                    CREATE TABLE ledger_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE annotation_rows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asrt_id TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        value TEXT NOT NULL,
                        origin TEXT NOT NULL,
                        derivation TEXT,
                        UNIQUE(asrt_id, namespace, category, key)
                    );
                    """
                )
                conn.executemany(
                    "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) VALUES (?, ?, ?, ?)",
                    (
                        (
                            claim_id,
                            "legacy.name",
                            alice_ref,
                            _enc_rest_terms([("string", "Alice")]),
                        ),
                        (edge_id, "legacy.edge", alice_ref, _enc_rest_terms(edge_terms)),
                    ),
                )
                conn.executemany(
                    "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
                    (
                        (claim_id, 0, _enc("Alice"), "string"),
                        (edge_id, 0, _enc(bob_ref), "entity_ref"),
                        (edge_id, 1, _enc("context"), "string"),
                    ),
                )
                conn.executemany(
                    "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                    (
                        (claim_id, "source", "str", _enc("v0.2")),
                        (claim_id, "reviewed", "bool", _enc(False)),
                        (claim_id, "reviewed", "bool", _enc(True)),
                        (edge_id, "ingest_key", "str", _enc("legacy-edge-key")),
                        (revoker_id, "reason", "str", _enc("superseded")),
                    ),
                )
                conn.execute(
                    "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                    (revoker_id, claim_id),
                )
                conn.execute(
                    "INSERT INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, ?)",
                    ("legacy-edge-key", edge_id, "assertion"),
                )
                conn.executemany(
                    "INSERT INTO annotation_rows "
                    "(asrt_id, namespace, category, key, kind, value, origin, derivation) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        (
                            claim_id,
                            "shared",
                            "source",
                            "source",
                            "str",
                            _enc("v0.2"),
                            "observed",
                            None,
                        ),
                        (
                            edge_id,
                            "legacy",
                            "derived",
                            "score",
                            "float",
                            _enc(0.5),
                            "derived",
                            "rule:1",
                        ),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            schema_graph = FactGraph.from_schema_classes([V02MigrationUser])
            schema_ir = schema_graph.schema_ir
            schema_graph.close()
            digest = schema_digest(schema_ir)
            save_workspace_manifest(workspace, schema_digest=digest)
            write_schema_object_for_workspace(workspace, schema_ir)

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(workspace)])
            self.assertEqual(rc, 0, f"stdout={stdout!r} stderr={stderr!r}")
            self.assertEqual(json.loads(stdout)["status"], "migrated")

            with sqlite3.connect(workspace / "db" / "assertions.db") as migrated_conn:
                tables = {
                    str(row[0])
                    for row in migrated_conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                }
            self.assertEqual(tables, {"claims", "claim_meta", "ledger_meta"})

            loaded = FactGraph.load_workspace(workspace, schema_classes=[V02MigrationUser])
            try:
                self.assertEqual(
                    [(row.asrt_id, row.rest_terms) for row in loaded.ledger.claims],
                    [(claim_id, [("string", "Alice")]), (edge_id, edge_terms)],
                )
                self.assertEqual(
                    loaded.ledger.revokes,
                    [type(loaded.ledger.revokes[0])(revoker_id, claim_id)],
                )
                self.assertEqual(
                    [
                        row.value
                        for row in loaded.ledger.find_meta(asrt_id=claim_id, key="reviewed")
                    ],
                    [False, True],
                )
                self.assertEqual(
                    [
                        (row.namespace, row.category, row.key, row.value, row.derivation)
                        for row in loaded.ledger.find_annotations(asrt_id=edge_id)
                    ],
                    [("legacy", "derived", "score", 0.5, "rule:1")],
                )
                self.assertEqual(loaded._database.head().tx_seq, 0)
                loaded.entities.create(V02MigrationUser, user_id="after-migration")
                self.assertEqual(loaded._database.head().tx_seq, 1)
            finally:
                loaded.close()

    def test_v02_migration_rejects_corrupt_ledger_without_replacing_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "corrupt-source"
            legacy = FactGraph.from_schema_classes([V02MigrationUser])
            digest = schema_digest(legacy.schema_ir)
            save_v02_workspace(workspace, schema_digest=digest, ledger=legacy.ledger)
            write_schema_object_for_workspace(workspace, legacy.schema_ir)
            legacy.ledger.close()
            corrupt_bytes = b"not-a-sqlite-database"
            (workspace / "ledger.db").write_bytes(corrupt_bytes)

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(workspace)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            self.assertEqual(json.loads(stderr)["kind"], "workspace_layout_migration_failed")
            self.assertEqual((workspace / "ledger.db").read_bytes(), corrupt_bytes)
            self.assertEqual(list(workspace.parent.glob(f"{workspace.name}.legacy-*")), [])

    def test_v02_migration_rejects_reserved_assertion_digest_on_revoker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "reserved-revoker"
            legacy = FactGraph.from_schema_classes([V02MigrationUser])
            e_ref = legacy.entities.create(V02MigrationUser, user_id="alice")
            name_id = legacy.fields.set(V02MigrationUser.name, e_ref, "Alice")
            revoker_id = legacy.assertions.retract(name_id)
            self.assertIsNotNone(revoker_id)
            legacy.ledger.append_meta(
                [MetaRow(revoker_id, "assertion_digest", "str", "legacy-collision")]
            )
            digest = schema_digest(legacy.schema_ir)
            save_v02_workspace(workspace, schema_digest=digest, ledger=legacy.ledger)
            write_schema_object_for_workspace(workspace, legacy.schema_ir)
            legacy.ledger.close()

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(workspace)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            payload = json.loads(stderr)
            self.assertEqual(payload["kind"], "workspace_layout_migration_failed")
            self.assertIn("legacy revoker", payload["message"])
            self.assertTrue((workspace / "ledger.db").is_file())

    def test_v02_migration_no_archive_removes_source_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "no-archive"
            legacy = FactGraph.from_schema_classes([V02MigrationUser])
            legacy.entities.create(V02MigrationUser, user_id="alice")
            digest = schema_digest(legacy.schema_ir)
            save_v02_workspace(workspace, schema_digest=digest, ledger=legacy.ledger)
            write_schema_object_for_workspace(workspace, legacy.schema_ir)
            legacy.ledger.close()

            rc, stdout, stderr = self._run_cli(
                ["migrate-workspace", str(workspace), "--no-archive"]
            )
            self.assertEqual(rc, 0, f"stdout={stdout!r} stderr={stderr!r}")
            self.assertEqual(json.loads(stdout)["status"], "migrated")
            self.assertEqual(list(workspace.glob("workspace.legacy.*")), [])
            self.assertEqual(list(workspace.parent.glob(f"{workspace.name}.legacy-*")), [])
            loaded = FactGraph.load_workspace(workspace, schema_classes=[V02MigrationUser])
            loaded.close()

    def test_v02_manifest_digest_mismatch_names_manifest_and_object_digests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "digest-mismatch"
            legacy = FactGraph.from_schema_classes([V02MigrationUser])
            digest = schema_digest(legacy.schema_ir)
            save_v02_workspace(workspace, schema_digest=digest, ledger=legacy.ledger)
            write_schema_object_for_workspace(workspace, legacy.schema_ir)
            legacy.ledger.close()
            manifest_path = workspace / "factgraph_workspace.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            wrong_digest = "sha256:" + "0" * 64
            manifest["schema_digest"] = wrong_digest
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            rc, stdout, stderr = self._run_cli(["migrate-workspace", str(workspace)])
            self.assertEqual(rc, 1, f"stdout={stdout!r}")
            payload = json.loads(stderr)
            self.assertEqual(payload["kind"], "schema_digest_mismatch")
            self.assertEqual(payload["details"]["manifest_schema_digest"], wrong_digest)
            self.assertEqual(payload["details"]["object_schema_digest"], digest)


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
