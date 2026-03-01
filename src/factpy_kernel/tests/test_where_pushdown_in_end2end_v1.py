from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.store.api import Store


class WherePushdownInEnd2EndV1Tests(unittest.TestCase):
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

    @staticmethod
    def _payload_sig(cand) -> tuple[str, tuple[tuple[str, object], ...]]:
        terms = cand.payload["terms"]
        return (
            terms[0]["value"],
            tuple(
                (term["tag"], term["value"])
                if term["kind"] == "literal"
                else ("entity_ref", term["value"])
                for term in terms[1:]
            ),
        )

    def test_where_pushdown_in_single_value(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:in-e1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:in-e2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        candidates = store.evaluate(
            derivation_id="drv.where.in.single",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=[
                ("pred", "person:country", ["$E", "$country"]),
                ("in", "$country", ["de"]),
            ],
            mode="engine",
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(self._payload_sig(candidates[0]), ("idref_v1:Person:in-e1", (("string", "de"),)))

    def test_where_pushdown_in_multi_values(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:in-m1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:in-m2",
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "row-2"},
        )

        candidates = store.evaluate(
            derivation_id="drv.where.in.multi",
            version="v1",
            target_pred_id="person:country",
            head_vars=["$E", "$country"],
            where=[
                ("pred", "person:country", ["$E", "$country"]),
                ("in", "$country", ["de", "fr"]),
            ],
            mode="engine",
        )

        self.assertEqual(
            {
                self._payload_sig(cand)
                for cand in candidates
            },
            {
                ("idref_v1:Person:in-m1", (("string", "de"),)),
                ("idref_v1:Person:in-m2", (("string", "fr"),)),
            },
        )


if __name__ == "__main__":
    unittest.main()
