from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.rules.rule_ir import (
    RuleCompileError,
    RuleRegistry,
    RuleSpec,
    run_rule,
)
from factpy_kernel.core.store.api import Store


class RuleRefV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema_ir = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "Person",
                    "identity_fields": [
                        {"name": "source_id", "type_domain": "string"},
                    ],
                },
                {
                    "entity_type": "Country",
                    "identity_fields": [
                        {"name": "code", "type_domain": "string"},
                    ],
                },
            ],
            "predicates": [
                {
                    "pred_id": "rel:lives_in",
                    "arg_specs": [
                        {"name": "E", "type_domain": "entity_ref"},
                        {"name": "country", "type_domain": "entity_ref"},
                    ],
                    "group_key_indexes": [0, 1],
                    "cardinality": "multi",
                },
                {
                    "pred_id": "rel:has_lang",
                    "arg_specs": [
                        {"name": "country", "type_domain": "entity_ref"},
                        {"name": "lang", "type_domain": "string"},
                    ],
                    "group_key_indexes": [0, 1],
                    "cardinality": "multi",
                },
            ],
            "projection": {
                "entities": [],
                "predicates": ["rel:lives_in", "rel:has_lang"],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        }
        self.store = Store(schema_ir=self.schema_ir)
        self.p1 = "idref_v1:Person:p1"
        self.p2 = "idref_v1:Person:p2"
        self.c_de = "idref_v1:Country:de"
        self.c_fr = "idref_v1:Country:fr"

        set_field(
            self.store.ledger,
            pred_id="rel:lives_in",
            e_ref=self.p1,
            rest_terms=[("entity_ref", self.c_de)],
            meta={"source": "test", "source_loc": "lives-1"},
        )
        set_field(
            self.store.ledger,
            pred_id="rel:lives_in",
            e_ref=self.p2,
            rest_terms=[("entity_ref", self.c_fr)],
            meta={"source": "test", "source_loc": "lives-2"},
        )
        set_field(
            self.store.ledger,
            pred_id="rel:has_lang",
            e_ref=self.c_de,
            rest_terms=[("string", "de")],
            meta={"source": "test", "source_loc": "lang-1"},
        )
        set_field(
            self.store.ledger,
            pred_id="rel:has_lang",
            e_ref=self.c_de,
            rest_terms=[("string", "en")],
            meta={"source": "test", "source_loc": "lang-2"},
        )
        set_field(
            self.store.ledger,
            pred_id="rel:has_lang",
            e_ref=self.c_fr,
            rest_terms=[("string", "fr")],
            meta={"source": "test", "source_loc": "lang-3"},
        )

    def test_rule_ref_chain_end_to_end(self) -> None:
        registry = RuleRegistry()
        speaks = RuleSpec(
            rule_id="q_speaks_candidate",
            version="1.0.0",
            select_vars=["$E", "$L"],
            where=[
                ("pred", "rel:lives_in", ["$E", "$C"]),
                ("pred", "rel:has_lang", ["$C", "$L"]),
            ],
            expose=True,
        )
        poly = RuleSpec(
            rule_id="q_polyglot",
            version="1.0.0",
            select_vars=["$E"],
            where=[
                ("ruleref", "q_speaks_candidate", "1.0.0", ["$E", "$L1"]),
                ("ruleref", "q_speaks_candidate", "1.0.0", ["$E", "$L2"]),
                ("not", [("eq", "$L1", "$L2")]),
            ],
            expose=False,
        )
        registry.register(speaks)
        registry.register(poly)

        rows = run_rule(self.store, poly, registry)
        self.assertEqual(rows, [(self.p1,)])

    def test_rule_ref_requires_exposed_target(self) -> None:
        registry = RuleRegistry()
        hidden = RuleSpec(
            rule_id="q_hidden",
            version="1.0.0",
            select_vars=["$E"],
            where=[("pred", "rel:lives_in", ["$E", "$C"])],
            expose=False,
        )
        parent = RuleSpec(
            rule_id="q_parent",
            version="1.0.0",
            select_vars=["$E"],
            where=[("ruleref", "q_hidden", "1.0.0", ["$E"])],
            expose=False,
        )
        registry.register(hidden)
        registry.register(parent)
        with self.assertRaisesRegex(RuleCompileError, r"expose=True"):
            run_rule(self.store, parent, registry)

    def test_rule_ref_unknown_version_rejected(self) -> None:
        registry = RuleRegistry()
        parent = RuleSpec(
            rule_id="q_parent",
            version="1.0.0",
            select_vars=["$E"],
            where=[("ruleref", "missing_rule", "9.9.9", ["$E"])],
            expose=False,
        )
        registry.register(parent)
        with self.assertRaisesRegex(RuleCompileError, r"unknown RuleRef"):
            run_rule(self.store, parent, registry)


if __name__ == "__main__":
    unittest.main()
