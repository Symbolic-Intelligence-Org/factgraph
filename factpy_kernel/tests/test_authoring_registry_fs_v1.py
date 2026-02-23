from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.authoring import AuthoringRegistryFSError, FileAuthoringRegistry


class AuthoringRegistryFSV1Tests(unittest.TestCase):
    def test_upsert_schema_rule_derivation_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            schema_result = registry.upsert_schema_ir(_schema())
            rule_result = registry.register_rule_spec(_rule_spec())
            drv_result = registry.register_derivation_spec(_derivation_spec())

            self.assertEqual(schema_result["status"], "applied")
            self.assertEqual(rule_result["status"], "applied")
            self.assertEqual(drv_result["status"], "applied")

            self.assertTrue((Path(tmpdir) / schema_result["path"]).exists())
            self.assertTrue((Path(tmpdir) / rule_result["path"]).exists())
            self.assertTrue((Path(tmpdir) / drv_result["path"]).exists())

            manifest = registry.read_manifest()
            self.assertEqual(manifest["authoring_registry_fs_version"], "authoring_registry_fs_v1")
            self.assertEqual(manifest["schema"]["schema_digest"], schema_result["schema_digest"])
            self.assertEqual(len(manifest["rules"]), 1)
            self.assertEqual(manifest["rules"][0]["rule_id"], "rules.country_rows")
            self.assertEqual(len(manifest["derivations"]), 1)
            self.assertEqual(manifest["derivations"][0]["derivation_id"], "drv.country")

    def test_reapply_same_payloads_are_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            self.assertEqual(registry.upsert_schema_ir(_schema())["status"], "applied")
            self.assertEqual(registry.register_rule_spec(_rule_spec())["status"], "applied")
            self.assertEqual(registry.register_derivation_spec(_derivation_spec())["status"], "applied")

            self.assertEqual(registry.upsert_schema_ir(_schema())["status"], "noop")
            self.assertEqual(registry.register_rule_spec(_rule_spec())["status"], "noop")
            self.assertEqual(registry.register_derivation_spec(_derivation_spec())["status"], "noop")

    def test_reject_invalid_rule_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            with self.assertRaises(AuthoringRegistryFSError):
                registry.register_rule_spec({"rule_id": "x", "version": "v1", "select_vars": [], "where": []})

    def test_reject_same_rule_version_with_different_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            registry.register_rule_spec(_rule_spec())
            changed = _rule_spec()
            changed["select_vars"] = ["$E"]
            changed["where"] = [("pred", "person:country", ["$E", "de"])]
            with self.assertRaises(AuthoringRegistryFSError) as ctx:
                registry.register_rule_spec(changed)
            self.assertEqual(ctx.exception.code, "registry_rule_version_conflict")
            self.assertIn("rules.country_rows", str(ctx.exception.path))

    def test_reject_same_derivation_version_with_different_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            registry.register_derivation_spec(_derivation_spec())
            changed = _derivation_spec()
            changed["where"] = [("pred", "person:country", ["$E", "fr"])]
            with self.assertRaises(AuthoringRegistryFSError) as ctx:
                registry.register_derivation_spec(changed)
            self.assertEqual(ctx.exception.code, "registry_derivation_version_conflict")
            self.assertIn("drv.country", str(ctx.exception.path))

    def test_append_apply_event_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            registry.append_apply_event({"kind": "authoring_apply_execute_action", "status": "applied"})
            registry.append_apply_event({"kind": "authoring_apply_execute_action", "status": "noop"})
            lines = (Path(tmpdir) / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["status"], "applied")
            self.assertEqual(json.loads(lines[1])["status"], "noop")

    def test_find_apply_execute_run_by_request_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            registry.append_apply_event({"kind": "authoring_apply_execute_run", "apply_request_id": "req-1", "status": "ok"})
            registry.append_apply_event({"kind": "authoring_apply_execute_action", "action_id": "a1"})
            registry.append_apply_event({"kind": "authoring_apply_execute_run", "apply_request_id": "req-2", "status": "warning"})
            self.assertEqual(registry.find_apply_execute_run("req-1")["status"], "ok")
            self.assertEqual(registry.find_apply_execute_run("req-2")["status"], "warning")
            self.assertIsNone(registry.find_apply_execute_run("req-404"))
            self.assertEqual(registry.list_apply_run_ids(), ["req-1", "req-2"])
            self.assertEqual(
                [row["apply_request_id"] for row in registry.list_apply_execute_runs()],
                ["req-1", "req-2"],
            )

    def test_list_versions_and_get_latest_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            rule_v1 = _rule_spec()
            rule_v2 = _rule_spec()
            rule_v2["version"] = "v2"
            rule_v2["where"] = [("pred", "person:country", ["$E", "fr"])]
            drv_v1 = _derivation_spec()
            drv_v2 = _derivation_spec()
            drv_v2["version"] = "v2"
            drv_v2["where"] = [("pred", "person:country", ["$E", "fr"])]

            registry.register_rule_spec(rule_v1)
            registry.register_rule_spec(rule_v2)
            registry.register_derivation_spec(drv_v1)
            registry.register_derivation_spec(drv_v2)

            rule_versions = registry.list_rule_versions("rules.country_rows")
            self.assertEqual([row["version"] for row in rule_versions], ["v1", "v2"])
            self.assertEqual(registry.get_latest_rule_spec("rules.country_rows")["version"], "v2")
            self.assertEqual(registry.get_latest_rule_spec("rules.country_rows")["where"][0][2][1], "fr")
            self.assertIsNone(registry.get_latest_rule_spec("missing.rule"))

            drv_versions = registry.list_derivation_versions("drv.country")
            self.assertEqual([row["version"] for row in drv_versions], ["v1", "v2"])
            self.assertEqual(registry.get_latest_derivation_spec("drv.country")["version"], "v2")
            self.assertEqual(registry.get_latest_derivation_spec("drv.country")["where"][0][2][1], "fr")
            self.assertIsNone(registry.get_latest_derivation_spec("missing.drv"))

    def test_list_ids_and_read_specific_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            self.assertIsNone(registry.get_schema_entry())
            self.assertEqual(registry.list_rule_ids(), [])
            self.assertEqual(registry.list_derivation_ids(), [])

            registry.upsert_schema_ir(_schema())
            rule_v1 = _rule_spec()
            rule_v2 = _rule_spec()
            rule_v2["version"] = "v2"
            rule_v2["where"] = [("pred", "person:country", ["$E", "fr"])]
            drv_v1 = _derivation_spec()
            drv_v2 = _derivation_spec()
            drv_v2["version"] = "v2"
            registry.register_rule_spec(rule_v1)
            registry.register_rule_spec(rule_v2)
            registry.register_derivation_spec(drv_v1)
            registry.register_derivation_spec(drv_v2)

            schema_entry = registry.get_schema_entry()
            self.assertIsNotNone(schema_entry)
            self.assertEqual(schema_entry["path"], "schema/schema_ir.json")
            self.assertEqual(registry.list_rule_ids(), ["rules.country_rows"])
            self.assertEqual(registry.list_derivation_ids(), ["drv.country"])
            self.assertEqual(registry.read_rule_spec("rules.country_rows", "v1")["version"], "v1")
            self.assertEqual(registry.read_rule_spec("rules.country_rows", "v2")["where"][0][2][1], "fr")
            self.assertIsNone(registry.read_rule_spec("rules.country_rows", "v404"))
            self.assertEqual(registry.read_derivation_spec("drv.country", "v1")["version"], "v1")
            self.assertIsNone(registry.read_derivation_spec("missing", "v1"))


def _schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [{"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]}],
        "predicates": [
            {
                "pred_id": "person:country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            }
        ],
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _rule_spec() -> dict:
    return {
        "rule_id": "rules.country_rows",
        "version": "v1",
        "select_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "expose": True,
    }


def _derivation_spec() -> dict:
    return {
        "derivation_id": "drv.country",
        "version": "v1",
        "target_pred_id": "person:country",
        "head_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "mode": "python",
        "temporal_view": "record",
    }


if __name__ == "__main__":
    unittest.main()
