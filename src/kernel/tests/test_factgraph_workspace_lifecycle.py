"""Red + guard baseline for FactGraph workspace lifecycle."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kernel.adapters.souffle.package import ExportOptions
from kernel.core.evidence.write_protocol import set_field
from kernel.core.schema.schema_ir import schema_digest
from kernel.sdk import (
    Branch,
    FactGraph,
    Inference,
    Pred,
    Rule,
    SavedRuleRef,
    SDKStore,
    vars as sdk_vars,
)
from kernel.sdk.store import SDKStoreError
from kernel.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Account(Entity):
    account_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _rule(*, rule_id: str = "rule.workspace.tag_seed", version: str = "v1") -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, tag],
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference(*, inference_id: str = "inf.workspace.tag", version: str = "v1") -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inference_id,
            version=version,
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


def _seed_fg(*, path: Path | None = None, registry_root: Path | None = None) -> SDKStore:
    kwargs = {}
    if path is not None:
        kwargs["path"] = path
    if registry_root is not None:
        kwargs["registry_root"] = registry_root
    fg = FactGraph.create(schema_classes=[User], **kwargs)
    alice_ref = fg.ref(User, user_id="Alice")
    set_field(
        fg.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test", "confidence": 1.0},
    )
    set_field(
        fg.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test", "confidence": 1.0},
    )
    return fg


def _read_manifest(workspace: Path) -> dict[str, object]:
    return json.loads((workspace / "factgraph_workspace.json").read_text(encoding="utf-8"))


class WorkspaceCreatePathTests(unittest.TestCase):
    def test_factgraph_create_accepts_path_and_binds_workspace(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"

            fg = FactGraph.create(schema_classes=[User], path=workspace)
            fg.save()

            self.assertIsInstance(fg, FactGraph)
            self.assertTrue((workspace / "factgraph_workspace.json").exists())

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

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.create(
                    schema_classes=[User],
                    path=workspace,
                    registry_root=other_registry,
                )

        self.assertIn("registry_root", str(ctx.exception))
        self.assertIn("workspace", str(ctx.exception))

    def test_create_accepts_path_with_matching_explicit_paths(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            ledger_path = workspace / "ledger.db"
            registry_root = workspace / "registry"

            fg = FactGraph.create(
                schema_classes=[User],
                path=workspace,
                ledger_path=str(ledger_path),
                registry_root=registry_root,
            )
            fg.save()

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
            fg.save()

        self.assertIn(
            "workspace path not bound; pass fg.save(path=...) or create with FactGraph.create(path=...)",
            str(ctx.exception),
        )

    def test_bound_save_writes_level4_layout(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)
            fg.rules.save(_rule())
            fg.inferences.save(_inference())

            fg.save()

            self.assertTrue((workspace / "factgraph_workspace.json").is_file())
            self.assertTrue((workspace / "ledger.db").is_file())
            self.assertTrue((workspace / "registry" / "registry_manifest.json").is_file())
            self.assertTrue((workspace / "registry" / "schema" / "schema_ir.json").is_file())
            self.assertTrue((workspace / "registry" / "rules" / "rule.workspace.tag_seed" / "v1.json").is_file())
            self.assertTrue((workspace / "registry" / "inferences" / "inf.workspace.tag" / "v1.json").is_file())

    def test_save_path_binds_future_no_arg_saves(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save(workspace)
            fg.save()

            self.assertTrue((workspace / "factgraph_workspace.json").exists())
            self.assertTrue((workspace / "ledger.db").exists())

    def test_manifest_v1_shape_is_explicit(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)

            fg.save()

            manifest = _read_manifest(workspace)
        self.assertEqual(manifest["factgraph_workspace_version"], "1")
        self.assertEqual(manifest["save_scope"], "level_4")
        self.assertEqual(manifest["schema_digest"], schema_digest(fg.schema_ir))
        self.assertEqual(manifest["components"]["ledger"], "ledger.db")
        self.assertEqual(manifest["components"]["registry"], "registry/")
        self.assertIsInstance(manifest["created_at"], str)
        self.assertIsInstance(manifest["last_saved_at"], str)

    def test_registryless_save_creates_empty_registry_with_schema_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save(workspace)

            registry = workspace / "registry"
            manifest = json.loads((registry / "registry_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue((registry / "schema" / "schema_ir.json").is_file())
        self.assertIn("schema", manifest)
        self.assertNotIn("rules", manifest)
        self.assertNotIn("inferences", manifest)

    def test_repeated_save_is_idempotent_and_loadable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)

            fg.save()
            first = _read_manifest(workspace)
            fg.save()
            second = _read_manifest(workspace)
            loaded = FactGraph.load(workspace, schema_classes=[User])

        self.assertEqual(first["schema_digest"], second["schema_digest"])
        self.assertEqual(first["components"], second["components"])
        self.assertIsNotNone(loaded.get(User, user_id="Alice"))

    def test_save_to_other_path_uses_ledger_backup_and_binds_new_path(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            first_workspace = Path(tmp_dir) / "first"
            second_workspace = Path(tmp_dir) / "second"
            fg = _seed_fg(path=first_workspace)

            fg.save(second_workspace)
            fg.save()

            loaded = FactGraph.load(second_workspace, schema_classes=[User])
        self.assertTrue((second_workspace / "ledger.db").exists())
        self.assertIsNotNone(loaded.get(User, user_id="Alice"))

    def test_save_syncs_separate_registry_root_into_workspace(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry_root = Path(tmp_dir) / "registry-source"
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(registry_root=registry_root)
            fg.rules.save(_rule())

            fg.save(workspace)

            self.assertTrue((workspace / "registry" / "rules" / "rule.workspace.tag_seed" / "v1.json").exists())


class WorkspaceLoadTests(unittest.TestCase):
    def test_factgraph_load_restores_ledger_and_registry_state(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)
            rule_ref = fg.rules.save(_rule())
            inference_ref = fg.inferences.save(_inference())
            fg.save()

            loaded = FactGraph.load(workspace, schema_classes=[User])

            snap = loaded.get(User, user_id="Alice")
            loaded_rule = loaded.rules.load(rule_ref)
            loaded_inference = loaded.inferences.load(inference_ref)

        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertIsInstance(loaded_rule, Rule)
        self.assertIsInstance(loaded_inference, Inference)

    def test_factgraph_load_requires_schema_classes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            _seed_fg(path=workspace).save()

            with self.assertRaises((TypeError, SDKStoreError)) as ctx:
                FactGraph.load(workspace)

        self.assertIn("schema_classes", str(ctx.exception))

    def test_factgraph_load_rejects_wrong_schema_classes(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            _seed_fg(path=workspace).save()

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load(workspace, schema_classes=[Account])

        msg = str(ctx.exception)
        self.assertIn("schema", msg)
        self.assertIn("digest", msg)

    def test_factgraph_load_rejects_missing_manifest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load(workspace, schema_classes=[User])

        self.assertIn("factgraph_workspace.json", str(ctx.exception))


class ApplicationWorkspaceRuntimeTests(unittest.TestCase):
    def test_workspace_runtime_exports_application_functions(self) -> None:
        module = importlib.import_module("kernel.application.workspace_runtime")

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

            fg.save(workspace)

            self.assertFalse((workspace / "artifacts").exists())
            self.assertFalse((workspace / "support").exists())
            self.assertFalse((workspace / "rule_trace").exists())

    def test_workspace_save_excludes_views(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()
            asrt_id = fg.set(User.name, fg.ref(User, user_id="Bob"), "Bob")
            fg.views.create("review", asrt_ids=[asrt_id])

            fg.save(workspace)

            self.assertFalse((workspace / "views.json").exists())
            self.assertFalse((workspace / "views").exists())

    def test_workspace_save_excludes_audit_and_evidence_files(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg()

            fg.save(workspace)

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
    def test_blueprint2_authoring_persistence_still_works(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)

            rule_ref = fg.rules.save(_rule())
            inference_ref = fg.inferences.save(_inference())
            loaded_rule = fg.rules.load(rule_ref)
            loaded_inference = fg.inferences.load(inference_ref)

        self.assertIsInstance(loaded_rule, Rule)
        self.assertIsInstance(loaded_inference, Inference)

    def test_saved_refs_remain_load_handles_not_runtime_selectors(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        saved_ref = SavedRuleRef(rule_id="rule.workspace.tag_seed", version="v1")

        with self.assertRaises((TypeError, SDKStoreError)):
            fg.eval.run(saved_ref)

    def test_batch_tx_save_keeps_transaction_meaning(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with fg.batch() as tx:
            user = tx.entity(User, user_id="Alice")
            user.name.set("Alice")
            result = tx.save(user)

        snap = fg.get(User, user_id="Alice")
        self.assertTrue(result.apply_result.refs_by_handle_id)
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")

    def test_direct_runtime_value_objects_do_not_need_registry(self) -> None:
        fg = _seed_fg()

        rows = fg.eval.run(_rule())
        candidates = fg.eval.evaluate(_inference(), engine="native")

        self.assertTrue(rows)
        self.assertTrue(candidates)

    def test_views_remain_in_memory_manager(self) -> None:
        fg = _seed_fg()
        asrt_id = fg.set(User.name, fg.ref(User, user_id="Bob"), "Bob")
        view = fg.views.create("review", asrt_ids=[asrt_id])

        self.assertEqual(fg.views.get("review"), view)
        self.assertEqual(fg.views.list()["review"], view)

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
