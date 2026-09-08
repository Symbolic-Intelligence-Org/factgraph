"""Fault-injection characterization for the broad boundaries in factgraph.cli.

Every guarded site in the workspace-migration command turns an unexpected
failure into a machine-readable error JSON on stderr plus exit code 1 (or a
``None`` load result).  A fault must never end as a ``migrated``/``noop``
success payload, and the original message must survive into the JSON.
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from factgraph import cli
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()


def _schema_ir() -> dict:
    return compile_schema_from_classes([Person])


class _BoundaryFault(Exception):
    """Custom, non-Database failure injected into a CLI migration boundary."""


def _capture(fn) -> tuple[Any, dict[str, Any], str]:
    """Run ``fn`` capturing the error JSON written to stderr."""
    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        value = fn()
    payload: dict[str, Any] = {}
    text = err.getvalue().strip()
    if text:
        payload = json.loads(text.splitlines()[-1])
    return value, payload, out.getvalue()


def _v03_workspace(root: Path) -> Path:
    workspace = root / "ws"
    (workspace / "db").mkdir(parents=True)
    (workspace / "db" / "meta.json").write_text("{}", encoding="utf-8")
    (workspace / "db" / "assertions.db").write_text("", encoding="utf-8")
    (workspace / "registry" / "schema").mkdir(parents=True)
    (workspace / "registry" / "schema" / "schema_ir.json").write_text(
        json.dumps(_schema_ir()), encoding="utf-8"
    )
    (workspace / "factgraph_workspace.json").write_text(
        json.dumps({"components": {"registry": "registry"}}), encoding="utf-8"
    )
    return workspace


def _v02_workspace(root: Path) -> Path:
    workspace = root / "ws02"
    (workspace / "registry" / "schema").mkdir(parents=True)
    (workspace / "registry" / "schema" / "schema_ir.json").write_text(
        json.dumps(_schema_ir()), encoding="utf-8"
    )
    (workspace / "factgraph_workspace.json").write_text(
        json.dumps({"components": {"registry": "registry", "ledger": "ledger.db"}}),
        encoding="utf-8",
    )
    connection = sqlite3.connect(workspace / "ledger.db")
    connection.close()
    return workspace


class SchemaDigestBoundaryTests(unittest.TestCase):
    """src/factgraph/cli.py: ``schema_digest`` boundary in ``_run_migrate_workspace``."""

    def test_digest_fault_becomes_the_schema_digest_failed_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v03_workspace(Path(tmp))

            with patch.object(
                cli, "schema_digest", side_effect=_BoundaryFault("injected digest failure")
            ):
                code, payload, stdout = _capture(
                    lambda: cli._run_migrate_workspace(
                        path=str(workspace), dry_run=False, archive=False
                    )
                )

            # Not reported as success: exit code 1, error JSON, no success payload.
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["kind"], "schema_digest_failed")
            self.assertIn("injected digest failure", payload["message"])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v03_workspace(Path(tmp))
            with (
                patch.object(cli, "schema_digest", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                cli._run_migrate_workspace(path=str(workspace), dry_run=False, archive=False)


class SchemaObjectWriteBoundaryTests(unittest.TestCase):
    """src/factgraph/cli.py: ``write_schema_object_for_workspace`` boundary."""

    def test_write_fault_becomes_the_db_schema_object_write_failed_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v03_workspace(Path(tmp))

            with patch.object(
                cli,
                "write_schema_object_for_workspace",
                side_effect=_BoundaryFault("injected schema object write failure"),
            ):
                code, payload, stdout = _capture(
                    lambda: cli._run_migrate_workspace(
                        path=str(workspace), dry_run=False, archive=False
                    )
                )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(payload["kind"], "db_schema_object_write_failed")
            self.assertIn("unexpected error", payload["message"])
            self.assertIn("injected schema object write failure", payload["message"])
            # The legacy registry/ marker is untouched by the failed migration.
            self.assertTrue((workspace / "registry").exists())

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v03_workspace(Path(tmp))
            with patch.object(
                cli, "write_schema_object_for_workspace", side_effect=KeyboardInterrupt
            ), self.assertRaises(KeyboardInterrupt):
                cli._run_migrate_workspace(path=str(workspace), dry_run=False, archive=False)


class LegacySchemaLoadBoundaryTests(unittest.TestCase):
    """src/factgraph/cli.py: ``_load_v02_schema_ir`` read/digest boundary."""

    def test_load_fault_reports_legacy_schema_unreadable_and_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v02_workspace(Path(tmp))

            with patch.object(
                cli, "schema_digest", side_effect=_BoundaryFault("injected legacy digest failure")
            ):
                value, payload, stdout = _capture(
                    lambda: cli._load_v02_schema_ir(
                        workspace=workspace,
                        manifest={},
                        legacy_registry_dir=workspace / "registry",
                    )
                )

            self.assertIsNone(value)
            self.assertEqual(stdout, "")
            self.assertEqual(payload["kind"], "legacy_schema_unreadable")
            self.assertIn("injected legacy digest failure", payload["message"])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v02_workspace(Path(tmp))
            with (
                patch.object(cli, "schema_digest", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                cli._load_v02_schema_ir(
                    workspace=workspace,
                    manifest={},
                    legacy_registry_dir=workspace / "registry",
                )


class LayoutMigrationBoundaryTests(unittest.TestCase):
    """src/factgraph/cli.py: v0.2 layout migration filesystem boundary."""

    def _migrate(self, workspace: Path, side_effect: BaseException):
        manifest = json.loads(
            (workspace / "factgraph_workspace.json").read_text(encoding="utf-8")
        )
        with patch.object(cli.Database, "migrate_legacy_ledger", side_effect=side_effect):
            return _capture(
                lambda: cli._run_v02_layout_migration(
                    workspace=workspace,
                    manifest=manifest,
                    legacy_ledger_path=workspace / "ledger.db",
                    legacy_registry_dir=workspace / "registry",
                    dry_run=False,
                    archive=False,
                )
            )

    def test_migration_fault_reports_failure_and_leaves_the_workspace_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v02_workspace(Path(tmp))
            code, payload, stdout = self._migrate(
                workspace, _BoundaryFault("injected legacy ledger migration failure")
            )

            # Not reported as success: exit code 1 and no "migrated" payload.
            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(payload["kind"], "workspace_layout_migration_failed")
            self.assertIn("injected legacy ledger migration failure", payload["message"])
            # The original v0.2 workspace survives; no half-replaced layout, no staging leak.
            self.assertTrue((workspace / "ledger.db").is_file())
            self.assertTrue((workspace / "registry" / "schema" / "schema_ir.json").is_file())
            leftovers = list(Path(tmp).glob(".ws02.migrate-*"))
            self.assertEqual(leftovers, [])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _v02_workspace(Path(tmp))
            with self.assertRaises(KeyboardInterrupt):
                self._migrate(workspace, KeyboardInterrupt())


if __name__ == "__main__":
    unittest.main()
