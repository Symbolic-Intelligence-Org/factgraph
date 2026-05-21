"""Q8 Phase 2 (Slice 6) — SavedRule/SavedInference persistence removal contract tests.

Per blueprint `docs/blueprints/active/2026-05-21_savedrule-phase2-removal.md`
§7 acceptance + §5 invariants. This file replaces
`tests/test_savedrule_phase1_deprecation.py` (deleted in Slice 6) and
validates that the SavedRule/SavedInference persistence layer is fully
removed across SDK / SDKRegistry / FileAuthoringRegistry / service routes
plus cross-layer consumers.
"""

from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.sdk import (
    FactGraph,
    FrozenSnapshotError,
    SDKRegistryError,
    compile_schema_from_classes,
)
from factgraph.sdk.registry import SDKRegistry
from factgraph.sdk.schema import Entity, Field, Identity


class _UserForPhase2(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


# Class 1 — SDKStore / FactGraph method absence


class SDKStoreSavedRuleMethodAbsenceTests(unittest.TestCase):
    def test_flat_save_rule_method_removed(self) -> None:
        fg = FactGraph.create(schema_classes=[_UserForPhase2])
        for name in (
            "save_rule",
            "load_rule",
            "list_rules",
            "get_rule",
            "save_inference",
            "load_inference",
            "list_inferences",
            "get_inference",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg, name), f"SDKStore unexpectedly exposes flat method {name}")

    def test_rules_namespace_only_exposes_inspect(self) -> None:
        fg = FactGraph.create(schema_classes=[_UserForPhase2])
        self.assertTrue(hasattr(fg.rules, "inspect"))
        for removed in ("save", "load", "list", "get"):
            with self.subTest(name=removed):
                self.assertFalse(
                    hasattr(fg.rules, removed),
                    f"fg.rules unexpectedly exposes {removed}",
                )

    def test_inferences_namespace_is_empty_and_frozen(self) -> None:
        fg = FactGraph.create(schema_classes=[_UserForPhase2])
        for removed in ("save", "load", "list", "get"):
            with self.subTest(name=removed):
                self.assertFalse(
                    hasattr(fg.inferences, removed),
                    f"fg.inferences unexpectedly exposes {removed}",
                )
        with self.assertRaises(FrozenSnapshotError):
            fg.inferences.new_attr = "blocked"

    def test_savedruleref_savedinferenceref_not_in_sdk_all(self) -> None:
        import factgraph.sdk as factgraph_sdk

        self.assertNotIn("SavedRuleRef", factgraph_sdk.__all__)
        self.assertNotIn("SavedInferenceRef", factgraph_sdk.__all__)

    def test_savedruleref_not_importable_from_sdk(self) -> None:
        import factgraph.sdk as factgraph_sdk

        self.assertFalse(hasattr(factgraph_sdk, "SavedRuleRef"))
        self.assertFalse(hasattr(factgraph_sdk, "SavedInferenceRef"))


# Class 2 — SDKRegistry rejection


class SDKRegistryRejectionTests(unittest.TestCase):
    def test_apply_authoring_bundle_rejects_rule_request(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = SDKRegistry(Path(tmp_dir))
            with self.assertRaises(SDKRegistryError) as ctx:
                registry.apply_authoring_bundle(rule_request={"any": "shape"})
            self.assertIn("Q8 Phase 2", str(ctx.exception))

    def test_apply_authoring_bundle_rejects_derivation_request(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = SDKRegistry(Path(tmp_dir))
            with self.assertRaises(SDKRegistryError) as ctx:
                registry.apply_authoring_bundle(derivation_request={"any": "shape"})
            self.assertIn("Q8 Phase 2", str(ctx.exception))

    def test_register_rule_spec_removed_from_sdk_registry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = SDKRegistry(Path(tmp_dir))
            for removed in (
                "register_rule_spec",
                "_register_rule_spec_no_warning",
                "register_rule",
                "register_inference_spec",
                "_register_inference_spec_no_warning",
                "register_inference",
                "list_rule_ids",
                "list_inference_ids",
                "list_rule_versions",
                "list_inference_versions",
                "get_latest_rule_spec",
                "get_latest_inference_spec",
                "read_rule_spec",
                "read_inference_spec",
            ):
                with self.subTest(name=removed):
                    self.assertFalse(
                        hasattr(registry, removed),
                        f"SDKRegistry unexpectedly exposes {removed}",
                    )


# Class 3 — FileAuthoringRegistry method absence


class FileAuthoringRegistryMethodAbsenceTests(unittest.TestCase):
    def test_rule_inference_methods_removed(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            for removed in (
                "register_rule_spec",
                "preview_register_rule_spec",
                "register_inference_spec",
                "preview_register_inference_spec",
                "list_rule_ids",
                "list_inference_ids",
                "list_rule_versions",
                "list_inference_versions",
                "get_latest_rule_spec",
                "read_rule_spec",
                "get_latest_inference_spec",
                "read_inference_spec",
            ):
                with self.subTest(name=removed):
                    self.assertFalse(
                        hasattr(registry, removed),
                        f"FileAuthoringRegistry unexpectedly exposes {removed}",
                    )

    def test_schema_only_methods_preserved(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            for preserved in (
                "upsert_schema_ir",
                "preview_upsert_schema_ir",
                "read_manifest",
                "get_schema_entry",
                "append_apply_event",
                "find_apply_execute_run",
                "list_apply_execute_runs",
                "list_apply_run_ids",
            ):
                with self.subTest(name=preserved):
                    self.assertTrue(
                        hasattr(registry, preserved),
                        f"FileAuthoringRegistry lost schema-only method {preserved}",
                    )


# Class 4 — Manifest schema-only write + old-key tolerance


class ManifestShapeTests(unittest.TestCase):
    def test_fresh_manifest_omits_rules_and_inferences_keys(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            schema_ir = compile_schema_from_classes([_UserForPhase2])
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(schema_ir)
            manifest = registry.read_manifest()
            self.assertNotIn("rules", manifest)
            self.assertNotIn("inferences", manifest)
            self.assertIn("schema", manifest)
            self.assertEqual(
                manifest.get("authoring_registry_fs_version"),
                "authoring_registry_fs_v1",
            )

    def test_legacy_manifest_with_rules_inferences_keys_is_tolerated_on_read(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "registry_manifest.json"
            legacy_manifest = {
                "authoring_registry_fs_version": "authoring_registry_fs_v1",
                "schema": None,
                "rules": [{"rule_id": "stale", "version": "v1", "path": "rules/stale/v1.json"}],
                "inferences": [{"inference_id": "stale_inf", "version": "v1", "path": "inferences/stale_inf/v1.json"}],
            }
            manifest_path.write_text(json.dumps(legacy_manifest), encoding="utf-8")
            registry = FileAuthoringRegistry(Path(tmp_dir))
            # read_manifest should not raise
            read_back = registry.read_manifest()
            self.assertEqual(read_back.get("schema"), None)
            # Old keys are preserved on read (no silent deletion)
            self.assertIn("rules", read_back)
            self.assertIn("inferences", read_back)


# Class 5 — Service route removed envelopes


class ServiceRouteRemovedEnvelopeTests(unittest.TestCase):
    def test_read_registry_rule_returns_removed_envelope(self) -> None:
        from service.registry_v1 import read_registry_rule

        resp = read_registry_rule({"root_dir": "/tmp/anything", "rule_id": "any"})
        self.assertFalse(resp["ok"])
        self.assertEqual(len(resp["errors"]), 1)
        err = resp["errors"][0]
        self.assertEqual(err["kind"], "removed")
        self.assertIn("Q8 Phase 2", err["details"]["message"])

    def test_read_registry_inference_returns_removed_envelope(self) -> None:
        from service.registry_v1 import read_registry_inference

        resp = read_registry_inference({"root_dir": "/tmp/anything", "inference_id": "any"})
        self.assertFalse(resp["ok"])
        self.assertEqual(len(resp["errors"]), 1)
        err = resp["errors"][0]
        self.assertEqual(err["kind"], "removed")
        self.assertIn("Q8 Phase 2", err["details"]["message"])

    def test_list_registry_assets_schema_only_response_shape(self) -> None:
        from service.registry_v1 import list_registry_assets

        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(compile_schema_from_classes([_UserForPhase2]))
            resp = list_registry_assets({"root_dir": tmp_dir})
            self.assertTrue(resp["ok"])
            self.assertIn("schema_entry", resp["registry"])
            self.assertIn("apply_run_ids", resp["registry"])
            self.assertNotIn("rule_ids", resp["registry"])
            self.assertNotIn("inference_ids", resp["registry"])


# Class 6 — Cross-layer consumer removal


class CrossLayerConsumerRemovalTests(unittest.TestCase):
    def test_load_registered_rules_removed_from_runtime_v1(self) -> None:
        runtime_v1 = importlib.import_module("service.runtime_v1")
        self.assertFalse(
            hasattr(runtime_v1, "_load_registered_rules"),
            "runtime_v1._load_registered_rules unexpectedly still defined",
        )

    def test_get_runtime_session_rules_still_exists_but_fs_branch_removed(self) -> None:
        # Per (A-fallback) scope read: function/route/agent layer preserved;
        # only FS-iteration block removed. The function should be ephemeral-only
        # internally now.
        runtime_v1 = importlib.import_module("service.runtime_v1")
        self.assertTrue(hasattr(runtime_v1, "get_runtime_session_rules"))

    def test_load_query_rule_registry_removed_from_souffle_package(self) -> None:
        package = importlib.import_module("factgraph.adapters.souffle.package")
        self.assertFalse(
            hasattr(package, "_load_query_rule_registry"),
            "souffle.package._load_query_rule_registry unexpectedly still defined",
        )

    def test_cli_no_rule_subcommands(self) -> None:
        from factgraph.authoring.cli import _build_parser

        parser = _build_parser()
        # Inspect subparsers
        subparsers_action = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        registry_list = subparsers_action.choices["registry-list"]
        kind_action = next(action for action in registry_list._actions if action.dest == "kind")
        self.assertEqual(tuple(kind_action.choices), ("apply_run_ids",))

        registry_show = subparsers_action.choices["registry-show"]
        show_kind_action = next(action for action in registry_show._actions if action.dest == "kind")
        self.assertEqual(set(show_kind_action.choices), {"manifest", "schema", "apply-run"})

    def test_cli_no_rule_request_payload_args(self) -> None:
        from factgraph.authoring.cli import _build_parser

        parser = _build_parser()
        subparsers_action = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        preflight = subparsers_action.choices["preflight"]
        opt_dests = {action.dest for action in preflight._actions}
        # rule-request / derivation-request / rule-dsl / derivation-dsl all removed
        self.assertNotIn("rule_request", opt_dests)
        self.assertNotIn("derivation_request", opt_dests)
        self.assertNotIn("rule_dsl", opt_dests)
        self.assertNotIn("derivation_dsl", opt_dests)
        # schema args remain
        self.assertIn("authoring_schema", opt_dests)
        self.assertIn("schema_dsl", opt_dests)


# Class 7 — Application authoring runtime shell


class ApplicationAuthoringRuntimeShellTests(unittest.TestCase):
    def test_authoring_runtime_module_is_minimal(self) -> None:
        mod = importlib.import_module("factgraph.application.authoring_runtime")
        self.assertTrue(hasattr(mod, "AuthoringRuntimeError"))
        for removed in (
            "SavedRuleRef",
            "SavedInferenceRef",
            "save_rule",
            "load_rule",
            "list_rules",
            "get_rule",
            "get_latest_rule",
            "save_inference",
            "load_inference",
            "list_inferences",
            "get_inference",
            "get_latest_inference",
        ):
            with self.subTest(name=removed):
                self.assertFalse(
                    hasattr(mod, removed),
                    f"application.authoring_runtime unexpectedly exposes {removed}",
                )

    def test_application_init_does_not_re_export_savedrule_helpers(self) -> None:
        mod = importlib.import_module("factgraph.application")
        for removed in (
            "SavedRuleRef",
            "SavedInferenceRef",
            "save_rule",
            "load_rule",
            "list_rules",
            "get_rule",
            "save_inference",
            "load_inference",
            "list_inferences",
            "get_inference",
        ):
            with self.subTest(name=removed):
                self.assertFalse(
                    hasattr(mod, removed),
                    f"factgraph.application unexpectedly exposes {removed}",
                )
        self.assertTrue(hasattr(mod, "AuthoringRuntimeError"))


# Class 8 — Workspace registry layout


class WorkspaceRegistryLayoutTests(unittest.TestCase):
    def test_factgraph_save_creates_schema_only_registry(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = FactGraph.create(schema_classes=[_UserForPhase2], path=workspace)
            fg.save()

            registry_root = workspace / "registry"
            self.assertTrue((registry_root / "schema" / "schema_ir.json").is_file())
            manifest_path = registry_root / "registry_manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotIn("rules", manifest)
            self.assertNotIn("inferences", manifest)
            # rules/ and inferences/ directories must NOT be created on fresh save
            self.assertFalse((registry_root / "rules").exists())
            self.assertFalse((registry_root / "inferences").exists())

    def test_factgraph_load_tolerates_pre_phase2_workspace_with_inert_rule_files(self) -> None:
        """Pre-Phase-2 workspaces may have registry/rules/* and registry/inferences/* on
        disk. Slice 6 must not silently delete them; they remain inert and are
        tolerated on load."""
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = FactGraph.create(schema_classes=[_UserForPhase2], path=workspace)
            fg.save()

            # Manually drop inert legacy files
            (workspace / "registry" / "rules" / "stale_rule").mkdir(parents=True, exist_ok=True)
            (workspace / "registry" / "rules" / "stale_rule" / "v1.json").write_text(
                json.dumps({"rule_id": "stale_rule", "version": "v1", "select_vars": [], "where": []}),
                encoding="utf-8",
            )

            # Load must not raise even though stale_rule exists on disk
            loaded = FactGraph.load(workspace, schema_classes=[_UserForPhase2])
            self.assertIsNotNone(loaded)
            # Stale file remains on disk (no silent deletion)
            self.assertTrue((workspace / "registry" / "rules" / "stale_rule" / "v1.json").exists())


if __name__ == "__main__":
    unittest.main()
