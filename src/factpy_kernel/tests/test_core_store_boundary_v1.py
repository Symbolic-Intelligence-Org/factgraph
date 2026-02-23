from __future__ import annotations

import importlib
import re
import unittest
from pathlib import Path

from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store, register_engine_evaluator


class CoreStoreBoundaryV1Tests(unittest.TestCase):
    def test_core_files_do_not_import_adapters(self) -> None:
        core_root = Path(__file__).resolve().parents[1] / "core"
        import_line = re.compile(r"^\s*(from|import)\s+factpy_kernel\.adapters\b")
        offenders: list[str] = []
        for path in sorted(core_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if import_line.match(line):
                    offenders.append(f"{path}:{line.strip()}")
                    break
        self.assertEqual(offenders, [])

    def test_engine_mode_requires_registration_and_adapter_can_register(self) -> None:
        import factpy_kernel.core.store.api as store_api

        prev = getattr(store_api, "_ENGINE_EVALUATOR")
        try:
            register_engine_evaluator(None)
            store = Store(schema_ir=_minimal_schema())
            with self.assertRaises(WhereValidationError):
                store.evaluate_engine(
                    derivation_id="drv",
                    version="v1",
                    target_pred_id="person:country",
                    head_vars=["$E", "$C"],
                    where=[("pred", "person:country", ["$E", "$C"])],
                )

            adapter_mod = importlib.import_module("factpy_kernel.adapters.souffle")
            importlib.reload(adapter_mod)
            self.assertIsNotNone(getattr(store_api, "_ENGINE_EVALUATOR"))
        finally:
            register_engine_evaluator(prev)


def _minimal_schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "source_id", "type_domain": "string"}],
            }
        ],
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


if __name__ == "__main__":
    unittest.main()
