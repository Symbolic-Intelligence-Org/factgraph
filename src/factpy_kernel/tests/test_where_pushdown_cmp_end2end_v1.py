from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.runner import find_souffle_binary
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store


class WherePushdownCmpEnd2EndV1Tests(unittest.TestCase):
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
                    "pred_id": "person:rank",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "rank", "type_domain": "int"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:seen_at",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "ts", "type_domain": "time"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
                {
                    "pred_id": "person:country",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0],
                    "cardinality": "functional",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": ["person:rank", "person:seen_at", "person:country"],
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

    def test_gt_rank_filter(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:cmp-r1",
            rest_terms=[("int", 1)],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:cmp-r3",
            rest_terms=[("int", 3)],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:rank",
            e_ref="idref_v1:Person:cmp-r5",
            rest_terms=[("int", 5)],
            meta={"source": "test", "source_loc": "row-3"},
        )

        candidates = store.evaluate(
            derivation_id="drv.where.cmp.gt",
            version="v1",
            target_pred_id="person:rank",
            head_vars=["$E", "$rank"],
            where=[
                ("pred", "person:rank", ["$E", "$rank"]),
                ("gt", "$rank", 2),
            ],
            mode="engine",
        )

        self.assertEqual(
            {
                self._payload_sig(cand)
                for cand in candidates
            },
            {
                ("idref_v1:Person:cmp-r3", (("int", 3),)),
                ("idref_v1:Person:cmp-r5", (("int", 5),)),
            },
        )

    def test_le_time_filter(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:seen_at",
            e_ref="idref_v1:Person:cmp-t100",
            rest_terms=[("time", 100)],
            meta={"source": "test", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="person:seen_at",
            e_ref="idref_v1:Person:cmp-t200",
            rest_terms=[("time", 200)],
            meta={"source": "test", "source_loc": "row-2"},
        )
        set_field(
            store.ledger,
            pred_id="person:seen_at",
            e_ref="idref_v1:Person:cmp-t300",
            rest_terms=[("time", 300)],
            meta={"source": "test", "source_loc": "row-3"},
        )

        candidates = store.evaluate(
            derivation_id="drv.where.cmp.le",
            version="v1",
            target_pred_id="person:seen_at",
            head_vars=["$E", "$ts"],
            where=[
                ("pred", "person:seen_at", ["$E", "$ts"]),
                ("le", "$ts", 200),
            ],
            mode="engine",
        )

        self.assertEqual(
            {
                self._payload_sig(cand)
                for cand in candidates
            },
            {
                ("idref_v1:Person:cmp-t100", (("time", 100),)),
                ("idref_v1:Person:cmp-t200", (("time", 200),)),
            },
        )

    def test_reject_string_comparison(self) -> None:
        if find_souffle_binary() is None:
            self.skipTest("souffle binary not found")

        store = Store(schema_ir=self.schema_ir)
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:cmp-c1",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "row-1"},
        )

        with self.assertRaises(WhereValidationError):
            store.evaluate(
                derivation_id="drv.where.cmp.reject",
                version="v1",
                target_pred_id="person:country",
                head_vars=["$E", "$country"],
                where=[
                    ("pred", "person:country", ["$E", "$country"]),
                    ("gt", "$country", "de"),
                ],
                mode="engine",
            )


if __name__ == "__main__":
    unittest.main()
