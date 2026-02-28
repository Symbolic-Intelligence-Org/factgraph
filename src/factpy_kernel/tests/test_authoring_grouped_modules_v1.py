from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factpy_kernel.authoring.derivations import compile_authoring_derivation_v1
from factpy_kernel.authoring.registry_workflow import FileAuthoringRegistry
from factpy_kernel.authoring.rules import compile_authoring_rule_v1
from factpy_kernel.authoring.schemas import compile_authoring_schema_v1, schema_preflight_authoring


class AuthoringGroupedModulesV1Tests(unittest.TestCase):
    def test_schemas_module_exposes_compile_and_preflight(self) -> None:
        authoring_schema = {
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                    "fields": [
                        {
                            "py_name": "country",
                            "type_domain": "string",
                            "cardinality": "functional",
                            "pred_id": "person:country",
                        }
                    ],
                }
            ]
        }
        schema_ir = compile_authoring_schema_v1(authoring_schema)
        self.assertEqual(schema_ir["entities"][0]["entity_type"], "Person")

        preflight = schema_preflight_authoring(authoring_schema)
        self.assertTrue(preflight["ok"])
        self.assertEqual(preflight["kind"], "schema")

    def test_rules_module_exposes_compile(self) -> None:
        payload = compile_authoring_rule_v1(
            {
                "rule_id": "q_country_rows",
                "version": "1.0.0",
                "select": ["E", "C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "expose": True,
            }
        )
        self.assertEqual(payload["rule_id"], "q_country_rows")
        self.assertEqual(payload["where"], [("pred", "person:country", ["$E", "$C"])])

    def test_derivations_module_exposes_compile(self) -> None:
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.country",
                "target": "person:country",
                "select": ["E", "country"],
                "body": [("pred", "person:country", ["$E", "$country"])],
            }
        )
        self.assertEqual(payload["derivation_id"], "drv.country")
        self.assertEqual(payload["target_pred_id"], "person:country")

    def test_registry_workflow_module_exposes_registry_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = FileAuthoringRegistry(Path(tmp))
            manifest = registry.read_manifest()
            self.assertEqual(manifest["authoring_registry_fs_version"], "authoring_registry_fs_v1")


if __name__ == "__main__":
    unittest.main()
