"""Red + guard baseline for FactGraph workspace lifecycle."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
from unittest.mock import patch

# Slice 7C / Q6-A (a.2): FileAuthoringRegistry was removed. Test methods
# that exercised the legacy adapter directly are skipped below.
from factgraph.adapters.souffle.package import ExportOptions
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.sdk import (
    Case,
    EmitSpec,
    FactGraph,
    Inference,
    Pred,
    SDKStore,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from factgraph.sdk.dsl import Rule
from factgraph.sdk.store import SDKStoreError
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag: list[str] = Field()


class Account(Entity):
    account_id: str = Identity()
    name: str = Field()


def _rule(*, rule_id: str = "rule.workspace.tag_seed", version: str = "v1") -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, tag],
            where=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference(*, inference_id: str = "inf.workspace.tag", version: str = "v1") -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inference_id,
            version=version,
            when=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            emits=EmitSpec("user:tag", [u, tag]),
        )


def _seed_fg(*, path: Path | None = None, registry_root: Path | None = None) -> SDKStore:
    kwargs = {}
    if path is not None:
        kwargs["path"] = path
    if registry_root is not None:
        kwargs["registry_root"] = registry_root
    fg = FactGraph.create(schema_classes=[User], **kwargs)
    alice_ref = fg.entities.ref(User, user_id="Alice")
    set_field(
        fg.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test"},
    )
    set_field(
        fg.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test"},
    )
    return fg


def _read_manifest(workspace: Path) -> dict[str, object]:
    return json.loads((workspace / "factgraph_workspace.json").read_text(encoding="utf-8"))


def _schema_object_file(workspace: Path, digest: str) -> Path:
    return workspace / "db" / "objects" / "schema" / f"{digest.removeprefix('sha256:')}.json"


class WorkspaceCreatePathTests(unittest.TestCase):
    def test_factgraph_create_accepts_path_and_binds_workspace(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"

            fg = FactGraph.create(schema_classes=[User], path=workspace)
            fg.save_workspace()

            self.assertIsInstance(fg, FactGraph)
            self.assertTrue((workspace / "factgraph_workspace.json").exists())
            manifest = _read_manifest(workspace)
            self.assertEqual(manifest["components"]["ledger"], "ledger.db")
            self.assertEqual(manifest["components"]["db"], "db/")
            self.assertEqual(manifest["components"]["views"], "views/")
            self.assertNotIn("registry", manifest["components"])
            self.assertTrue(_schema_object_file(workspace, schema_digest(fg.schema_ir)).is_file())

    def test_create_rejects_path_with_different_ledger_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            other_ledger = Path(tmp_dir) / "other" / "ledger.db"

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.create(
                    schema_classes=[User],
                    path=workspace,
                    ledger_path=str(other_ledger),
                )

        self.assertIn("ledger_path", str(ctx.exception))
        self.assertIn("workspace", str(ctx.exception))

    def test_create_rejects_path_with_different_registry_root(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            other_registry = Path(tmp_dir) / "other-registry"

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                with self.assertRaises(SDKStoreError) as ctx:
                    FactGraph.create(
                        schema_classes=[User],
                        path=workspace,
                        registry_root=other_registry,
                    )

        self.assertIn("registry_root", str(ctx.exception))
        self.assertIn("workspace", str(ctx.exception))

    def test_create_accepts_path_with_matching_explicit_paths(self) -> None:
        self.skipTest("registry_root= was removed by A20(E) / Q6-A")
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            ledger_path = workspace / "ledger.db"
            registry_root = workspace / "registry"

            with self.assertWarnsRegex(DeprecationWarning, "registry_root"):
                fg = FactGraph.create(
                    schema_classes=[User],
                    path=workspace,
                    ledger_path=str(ledger_path),
                    registry_root=registry_root,
                )
            fg.save_workspace()

            self.assertTrue((workspace / "ledger.db").exists())
            self.assertTrue((workspace / "registry" / "registry_manifest.json").exists())

    def test_from_schema_classes_does_not_accept_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with self.assertRaises(TypeError):
                FactGraph.from_schema_classes([User], path=Path(tmp_dir) / "workspace")


class WorkspaceSaveTests(unittest.TestCase):
    def test_unbound_save_requires_workspace_path_with_anchored_message(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with self.assertRaises(SDKStoreError) as ctx:
            fg.save_workspace()

        self.assertIn(
            "workspace path not bound; pass fg.save_workspace(path=...) or create with FactGraph.create(path=...)",
            str(ctx.exception),
        )

    # Q8 Phase 2 (Slice 6): test_bound_save_writes_level4_layout was removed.
    # SavedRule/SavedInference persistence was removed in Slice 6, so writing
    # rule/inference assets to the workspace registry is no longer possible.
    # Schema/manifest persistence is still covered by tests below.

    def test_save_path_binds_future_no_arg_saves(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save_workspace(workspace)
            fg.save_workspace()

            self.assertTrue((workspace / "factgraph_workspace.json").exists())
            self.assertTrue((workspace / "ledger.db").exists())

    def test_manifest_v1_shape_is_explicit(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)

            fg.save_workspace()

            manifest = _read_manifest(workspace)
        self.assertEqual(manifest["factgraph_workspace_version"], "1")
        self.assertEqual(manifest["save_scope"], "level_4")
        self.assertEqual(manifest["schema_digest"], schema_digest(fg.schema_ir))
        self.assertEqual(manifest["components"]["ledger"], "ledger.db")
        self.assertEqual(manifest["components"]["db"], "db/")
        self.assertEqual(manifest["components"]["views"], "views/")
        self.assertNotIn("registry", manifest["components"])
        self.assertIsInstance(manifest["created_at"], str)
        self.assertIsInstance(manifest["last_saved_at"], str)

    def test_registryless_save_creates_db_schema_object_without_registry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save_workspace(workspace)

            self.assertFalse((workspace / "registry").exists())
            self.assertTrue(_schema_object_file(workspace, schema_digest(fg.schema_ir)).is_file())

    def test_repeated_save_is_idempotent_and_loadable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)

            fg.save_workspace()
            first = _read_manifest(workspace)
            fg.save_workspace()
            second = _read_manifest(workspace)
            loaded = FactGraph.load_workspace(workspace, schema_classes=[User])

        self.assertEqual(first["schema_digest"], second["schema_digest"])
        self.assertEqual(first["components"], second["components"])
        self.assertIsNotNone(loaded.entities.get(User, user_id="Alice"))

    def test_load_workspace_accepts_same_schema_with_new_generated_at(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            with patch(
                "factgraph.authoring.schema_compile._utc_now_iso_z",
                side_effect=("2026-06-06T00:00:00Z", "2026-06-06T00:00:01Z"),
            ):
                fg = _seed_fg(path=workspace)
                fg.save_workspace()
                manifest = _read_manifest(workspace)
                loaded = FactGraph.load_workspace(workspace, schema_classes=[User])

        self.assertEqual(schema_digest(fg.schema_ir), manifest["schema_digest"])
        self.assertEqual(schema_digest(loaded.schema_ir), manifest["schema_digest"])
        self.assertNotEqual(fg.schema_ir["generated_at"], loaded.schema_ir["generated_at"])
        self.assertIsNotNone(loaded.entities.get(User, user_id="Alice"))

    def test_save_to_other_path_uses_ledger_backup_and_binds_new_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            first_workspace = Path(tmp_dir) / "first"
            second_workspace = Path(tmp_dir) / "second"
            fg = _seed_fg(path=first_workspace)

            fg.save_workspace(second_workspace)
            fg.save_workspace()

            loaded = FactGraph.load_workspace(second_workspace, schema_classes=[User])
            self.assertTrue((second_workspace / "ledger.db").exists())
            self.assertFalse((second_workspace / "registry").exists())
            self.assertTrue(_schema_object_file(second_workspace, schema_digest(fg.schema_ir)).is_file())
        self.assertIsNotNone(loaded.entities.get(User, user_id="Alice"))

    # Q8 Phase 2 (Slice 6): test_save_syncs_separate_registry_root_into_workspace
    # was removed. SavedRule persistence is gone; registry sync only carries
    # schema + apply-log artifacts now (covered by other tests in this class).


class WorkspaceLoadTests(unittest.TestCase):
    # Q8 Phase 2 (Slice 6): test_factgraph_load_restores_ledger_and_registry_state
    # was removed. fg.rules.save / fg.inferences.save / load no longer exist.
    # Workspace ledger restoration is still covered by
    # test_repeated_save_is_idempotent_and_loadable and
    # test_save_to_other_path_uses_ledger_backup_and_binds_new_path.

    def test_factgraph_load_requires_schema_classes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            _seed_fg(path=workspace).save_workspace()

            with self.assertRaises((TypeError, SDKStoreError)) as ctx:
                FactGraph.load_workspace(workspace)

        self.assertIn("schema_classes", str(ctx.exception))

    def test_factgraph_load_rejects_wrong_schema_classes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            _seed_fg(path=workspace).save_workspace()

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load_workspace(workspace, schema_classes=[Account])

        msg = str(ctx.exception)
        self.assertIn("schema", msg)
        self.assertIn("digest", msg)

    def test_factgraph_load_rejects_missing_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load_workspace(workspace, schema_classes=[User])

        self.assertIn("factgraph_workspace.json", str(ctx.exception))

    def test_factgraph_load_migrates_legacy_registry_schema_to_db_schema_object(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            registry_root = workspace / "registry"
            fg = FactGraph.create(schema_classes=[User], path=workspace, registry_root=registry_root)
            fg.save_workspace()
            digest = schema_digest(fg.schema_ir)
            schema_object = _schema_object_file(workspace, digest)
            schema_object.unlink()

            loaded = FactGraph.load_workspace(workspace, schema_classes=[User])
            self.assertTrue(schema_object.is_file())

        self.assertIsNotNone(loaded)

    def test_factgraph_load_rejects_legacy_registry_conflicting_with_db_schema_object(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            registry_root = workspace / "registry"
            fg = FactGraph.create(schema_classes=[User], path=workspace, registry_root=registry_root)
            fg.save_workspace()

            FileAuthoringRegistry(registry_root).upsert_schema_ir(compile_schema_from_classes([Account]))

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load_workspace(workspace, schema_classes=[User])

        self.assertIn("workspace schema digest mismatch", str(ctx.exception))
        self.assertIn("registry", str(ctx.exception))


class ApplicationWorkspaceRuntimeTests(unittest.TestCase):
    def test_workspace_runtime_exports_application_functions(self) -> None:
        module = importlib.import_module("factgraph.application.workspace_runtime")

        for name in (
            "save_workspace",
            "load_workspace",
            "resolve_workspace_paths",
            "validate_workspace_manifest",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))


class WorkspaceExclusionTests(unittest.TestCase):
    def test_workspace_save_excludes_artifact_sidecar(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            artifact_root = Path(tmp_dir) / "artifacts"
            fg = FactGraph.create(schema_classes=[User], artifact_store_root=str(artifact_root))

            fg.save_workspace(workspace)

            self.assertFalse((workspace / "artifacts").exists())
            self.assertFalse((workspace / "support").exists())
            self.assertFalse((workspace / "rule_trace").exists())

    def test_workspace_save_excludes_views(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()
            asrt_id = fg.fields.set(User.name, fg.entities.ref(User, user_id="Bob"), "Bob")
            fg.assertion_views.create("review", asrt_ids=[asrt_id])

            fg.save_workspace(workspace)

            self.assertFalse((workspace / "views.json").exists())
            self.assertFalse((workspace / "views").exists())

    def test_workspace_save_excludes_audit_and_evidence_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save_workspace(workspace)

            names = {child.name for child in workspace.iterdir()}
            self.assertNotIn("audit", names)
            self.assertNotIn("evidence", names)
            self.assertNotIn("rounds", names)

    def test_workspace_layout_is_distinct_from_package_export_layout(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            package_dir = Path(tmp_dir) / "package"
            fg = _seed_fg()

            fg.package.export_package(package_dir, ExportOptions(package_kind="audit"))

            self.assertTrue((package_dir / "manifest.json").exists())
            self.assertFalse((package_dir / "factgraph_workspace.json").exists())


class PreservationGuards(unittest.TestCase):
    # Q8 Phase 2 (Slice 6): test_blueprint2_authoring_persistence_still_works
    # and test_saved_refs_remain_load_handles_not_runtime_selectors were
    # removed. fg.rules.save / fg.inferences.save / fg.rules.load /
    # fg.inferences.load / SavedRuleRef no longer exist. Pre-Phase-2 Blueprint 2
    # commitments are now superseded by Q8 Phase 2 removal scope.

    def test_batch_tx_save_keeps_transaction_meaning(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with fg.batch() as tx:
            user = tx.entity(User, user_id="Alice")
            user.name.set("Alice")
            result = tx.save(user)

        snap = fg.entities.get(User, user_id="Alice")
        self.assertTrue(result.apply_result.refs_by_handle_id)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_direct_runtime_value_objects_do_not_need_registry(self) -> None:
        fg = _seed_fg()

        rule_info = fg.rules.inspect(_rule())
        candidates = fg.eval.evaluate(_inference(), engine="native")

        self.assertEqual(rule_info["kind"], "Rule")
        self.assertTrue(candidates)

    def test_views_remain_in_memory_manager(self) -> None:
        fg = _seed_fg()
        asrt_id = fg.fields.set(User.name, fg.entities.ref(User, user_id="Bob"), "Bob")
        view = fg.assertion_views.create("review", asrt_ids=[asrt_id])

        self.assertEqual(fg.assertion_views.get("review"), view)
        self.assertEqual(fg.assertion_views.list()["review"], view)

    def test_rules_inspect_still_accepts_rule_and_inference(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        inspected_rule = fg.rules.inspect(_rule())
        inspected_inference = fg.rules.inspect(_inference())

        self.assertEqual(inspected_rule["kind"], "Rule")
        self.assertEqual(inspected_inference["kind"], "Inference")

    def test_from_schema_classes_remains_lower_level_constructor(self) -> None:
        params = inspect.signature(FactGraph.from_schema_classes).parameters
        fg = FactGraph.from_schema_classes([User])

        self.assertNotIn("path", params)
        self.assertIsInstance(fg, FactGraph)


if __name__ == "__main__":
    unittest.main()
