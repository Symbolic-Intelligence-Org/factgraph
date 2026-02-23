from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factpy_kernel.sdk import Entity, Field, Identity, SDKRegistry, SDKRegistryError


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    country_copy: str = Field(cardinality="functional", pred_id="person:country_copy")


class SDKRegistryV1Tests(unittest.TestCase):
    def test_apply_schema_classes_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk_registry = SDKRegistry(tmpdir)

            first = sdk_registry.apply_schema_classes(
                [Person],
                apply_request_id="req-1",
                transaction_policy="best_effort_no_rollback_v1",
            )
            self.assertTrue(first["ok"])
            self.assertEqual(first["apply_execute"]["status"], "ok")
            self.assertFalse(first["apply_execute"]["idempotency"]["replayed"])

            second = sdk_registry.apply_schema_classes(
                [Person],
                apply_request_id="req-1",
                transaction_policy="best_effort_no_rollback_v1",
            )
            self.assertTrue(second["ok"])
            self.assertEqual(second["apply_execute"]["status"], "ok")
            self.assertTrue(second["apply_execute"]["idempotency"]["replayed"])

            self.assertEqual(sdk_registry.list_apply_run_ids(), ["req-1"])
            self.assertIsNotNone(sdk_registry.show_apply_run("req-1"))
            schema_entry = sdk_registry.get_schema_entry()
            self.assertIsNotNone(schema_entry)
            self.assertIn("schema_digest", schema_entry)

    def test_read_and_register_rule_derivation_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk_registry = SDKRegistry(tmpdir)

            rule_res = sdk_registry.register_rule_spec(
                {
                    "rule_id": "rule.country_rows",
                    "version": "1.0.0",
                    "select_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                    "expose": True,
                }
            )
            self.assertEqual(rule_res["status"], "applied")

            derivation_res = sdk_registry.register_derivation_spec(
                {
                    "derivation_id": "drv.country_copy",
                    "version": "1.0.0",
                    "target": "person:country_copy",
                    "head_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                    "materialize_as": "fact",
                }
            )
            self.assertEqual(derivation_res["status"], "applied")

            self.assertEqual(sdk_registry.list_rule_ids(), ["rule.country_rows"])
            self.assertEqual(sdk_registry.list_derivation_ids(), ["drv.country_copy"])
            self.assertEqual([v["version"] for v in sdk_registry.list_rule_versions("rule.country_rows")], ["1.0.0"])
            self.assertEqual(
                [v["version"] for v in sdk_registry.list_derivation_versions("drv.country_copy")],
                ["1.0.0"],
            )

            latest_rule = sdk_registry.get_latest_rule_spec("rule.country_rows")
            self.assertIsNotNone(latest_rule)
            self.assertEqual(latest_rule["rule_id"], "rule.country_rows")
            self.assertTrue(latest_rule["expose"])
            read_rule = sdk_registry.read_rule_spec("rule.country_rows", "1.0.0")
            self.assertEqual(read_rule, latest_rule)

            latest_drv = sdk_registry.get_latest_derivation_spec("drv.country_copy")
            self.assertIsNotNone(latest_drv)
            self.assertEqual(latest_drv["target_pred_id"], "person:country_copy")
            read_drv = sdk_registry.read_derivation_spec("drv.country_copy", "1.0.0")
            self.assertEqual(read_drv, latest_drv)

    def test_constructor_validates_root_dir_and_registry_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk_registry = SDKRegistry(tmpdir)
            with self.assertRaises(SDKRegistryError):
                SDKRegistry(Path(tmpdir) / "other", registry=sdk_registry.registry)


if __name__ == "__main__":
    unittest.main()
