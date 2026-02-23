from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.export.package import ExportOptions, export_package
from factpy_kernel.policy.policy_ir import (
    PolicyIRValidationError,
    build_policy_ir_v1,
    policy_digest,
)
from factpy_kernel.protocol.digests import sha256_token
from factpy_kernel.store.api import Store


class PolicyIRV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                }
            ],
            "predicates": [
                {
                    "pred_id": "person:country",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                }
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:country"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }

    def test_policy_ir_digest_stable(self) -> None:
        policy_a = build_policy_ir_v1(self.schema_ir)
        policy_b = build_policy_ir_v1(self.schema_ir)

        policy_a["generated_at"] = 123
        policy_b["generated_at"] = 123

        self.assertEqual(policy_digest(policy_a), policy_digest(policy_b))

    def test_build_policy_ir_generated_at_override(self) -> None:
        policy_ir = build_policy_ir_v1(self.schema_ir, generated_at=0)
        self.assertEqual(policy_ir["generated_at"], 0)

    def test_export_manifest_policy_path_and_digest(self) -> None:
        store = Store(schema_ir=self.schema_ir)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "pkg"
            manifest_path = export_package(store, out_dir, ExportOptions())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["paths"]["policy"], "policy/policy_ir.json")

            policy_path = out_dir / "policy" / "policy_ir.json"
            self.assertTrue(policy_path.exists())
            self.assertEqual(
                manifest["digests"]["policy_digest"],
                sha256_token(policy_path.read_bytes()),
            )

    def test_reject_missing_schema_protocol_version(self) -> None:
        broken = dict(self.schema_ir)
        broken.pop("protocol_version")
        with self.assertRaises(PolicyIRValidationError):
            build_policy_ir_v1(broken)


if __name__ == "__main__":
    unittest.main()
