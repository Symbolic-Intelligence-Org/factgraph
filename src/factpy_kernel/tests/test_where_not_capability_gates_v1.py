from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store.api import Store


class WhereNotCapabilityGatesV1Tests(unittest.TestCase):
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
        self.store = Store(schema_ir=self.schema_ir)
        set_field(
            self.store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:not-cap-gate",
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "seed-1"},
        )

    def _assert_rejected_both_modes(self, where: list) -> None:
        for mode in ("python", "engine"):
            with self.assertRaises(WhereValidationError):
                self.store.evaluate(
                    derivation_id=f"drv.where.not.cap.{mode}",
                    version="v1",
                    target_pred_id="person:country",
                    head_vars=["$E", "$country"],
                    where=where,
                    mode=mode,
                )

    def test_reject_nested_not(self) -> None:
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("not", [("not", [("pred", "person:country", ["$E", "$country"])])]),
        ]
        self._assert_rejected_both_modes(where)

    def test_reject_nested_or_inside_not_body(self) -> None:
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("not", [[[("pred", "person:country", ["$E", "$country"])]]]),
        ]
        self._assert_rejected_both_modes(where)

    def test_reject_uncorrelated_not_without_outer_var_reference(self) -> None:
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            ("not", [("pred", "person:country", ["idref_v1:Person:any", "de"])]),
        ]
        self._assert_rejected_both_modes(where)

    def test_reject_not_or_branch_missing_correlated_vars(self) -> None:
        where = [
            ("pred", "person:country", ["$E", "$country"]),
            (
                "not",
                [
                    [("pred", "person:country", ["$E", "$country"])],
                    [("eq", "$country", "de")],
                ],
            ),
        ]
        self._assert_rejected_both_modes(where)


if __name__ == "__main__":
    unittest.main()
