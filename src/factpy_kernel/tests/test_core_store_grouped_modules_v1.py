from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.store import builders
from factpy_kernel.core.store.evaluation import evaluate_store
from factpy_kernel.core.store.queries import explain_fact
from factpy_kernel.core.store.runtime import Store


class CoreStoreGroupedModulesV1Tests(unittest.TestCase):
    def test_public_grouped_modules_align_with_store_runtime(self) -> None:
        store = Store(schema_ir=_minimal_schema())
        e_ref = encode_idref_v1("Person", [("source_id", "string", "u1")])
        set_field(
            store.ledger,
            "person:country",
            e_ref,
            [("string", "de")],
            {"source": "seed"},
        )

        schema_pred = builders.find_schema_pred(store, "person:country")
        self.assertIsNotNone(schema_pred)
        assert schema_pred is not None
        self.assertEqual(schema_pred["pred_id"], "person:country")

        candidates = evaluate_store(
            store,
            derivation_id="drv.copy_country",
            version="1.0.0",
            target_pred_id="person:country",
            head_vars=["$E", "$C"],
            where=[("pred", "person:country", ["$E", "$C"])],
            mode="python",
            temporal_view="active",
            head=None,
            engine_evaluate=store.evaluate_engine,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].payload["terms"],
            [
                {"kind": "entity_ref", "value": e_ref},
                {"kind": "literal", "tag": "string", "value": "de"},
            ],
        )

        detail = explain_fact(store, "person:country", e_ref, "de")
        self.assertEqual(detail["pred_id"], "person:country")
        self.assertEqual(detail["chosen_asrt_id"], detail["active_claims"][0]["asrt_id"])


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
