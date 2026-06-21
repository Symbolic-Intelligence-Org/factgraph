from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.where_compile import (
    build_query_witness_layout,
    compile_where_to_per_branch_witness_dl,
    compile_where_to_query_dl,
)
from factgraph.core.rules.ruleref_common import internal_rule_pred_id
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.rules.where_eval import WhereValidationError


class SouffleWitnessWhereCompileV1Tests(unittest.TestCase):
    def test_build_query_witness_layout_collects_pred_atoms_in_branch_order(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        layout = build_query_witness_layout(where)

        self.assertEqual(layout.query_variables, ("$e", "$value"))
        self.assertEqual(
            [row.pred_condition_key for row in layout.pred_witness_columns],
            ["c0.c0:user:name", "c1.c0:user:status"],
        )

    def test_compile_where_to_query_dl_with_witness_columns_uses_w_relations(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__test",
            include_pred_witness_columns=True,
        )

        self.assertIn(".decl query__test(C0:symbol, C1:symbol, W0:symbol, W1:symbol)", dl)
        self.assertIn(".output query__test", dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_name_w(C0, C1, W0), W1 = "".', dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_status_w(C0, C1, W1), W0 = "".', dl)

    def test_compile_where_to_per_branch_witness_dl_keeps_branch_outputs_narrow(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        program = compile_where_to_per_branch_witness_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__test",
            query_variables=["$e"],
        )

        self.assertIn(".decl query__test(C0:symbol)", program.text)
        self.assertIn(".decl query__test__b0_w(C0:symbol, W0:symbol)", program.text)
        self.assertIn(".decl query__test__b1_w(C0:symbol, W0:symbol)", program.text)
        self.assertNotIn(".decl query__test(C0:symbol, W0:symbol, W1:symbol)", program.text)
        self.assertEqual([rel.case_index for rel in program.branch_relations], [0, 1])
        self.assertEqual(
            [rel.layout.pred_witness_columns[0].pred_condition_key for rel in program.branch_relations],
            ["c0.c0:user:name", "c1.c0:user:status"],
        )

    def test_compile_where_to_per_branch_witness_dl_rejects_overwide_branch(self) -> None:
        branch = [("pred", "user:name", ["$e", f"v{index}"]) for index in range(22)]

        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_per_branch_witness_dl(
                schema_ir=_schema_ir(),
                where=branch,
                query_rel="query__wide",
                query_variables=["$e"],
            )

        message = str(ctx.exception)
        self.assertIn("souffle witness relation arity exceeds supported limit", message)
        self.assertIn("branch c0", message)
        self.assertIn("arity=23", message)
        self.assertIn("limit=22", message)
        self.assertIn("witness_predicates=22", message)

    def test_compile_where_to_query_dl_keeps_legacy_shape_by_default(self) -> None:
        where = [
            ("pred", "user:name", ["$e", "$name"]),
            ("pred", "user:status", ["$e", "$status"]),
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__legacy",
        )

        self.assertIn(".decl query__legacy(C0:symbol, C1:symbol, C2:symbol)", dl)
        self.assertNotIn("W0:symbol", dl)
        self.assertIn("p_user_name(C0, C1)", dl)
        self.assertIn("p_user_status(C0, C2)", dl)
        self.assertNotIn("p_user_name_w(", dl)

    def test_compile_where_to_query_dl_rewrites_ruleref_with_registry(self) -> None:
        internal_rel = normalize_pred_id(internal_rule_pred_id("q.user_name_rows", "1.0.0"))
        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=[
                ("ruleref", "q.user_name_rows", "1.0.0", ["$e", "$name"]),
                ("pred", "user:status", ["$e", "$status"]),
            ],
            query_rel="query__ruleref",
            registry=_rule_registry(),
        )

        self.assertIn(f".decl {internal_rel}(C0:symbol, C1:symbol)", dl)
        self.assertIn(f"{internal_rel}(C0, C1) :- p_user_name(C0, C1).", dl)
        self.assertIn(
            f"query__ruleref(C0, C1, C2) :- {internal_rel}(C0, C1), p_user_status(C0, C2).",
            dl,
        )

    def test_compile_where_to_query_dl_ruleref_requires_registry(self) -> None:
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(
                schema_ir=_schema_ir(),
                where=[("ruleref", "q.user_name_rows", "1.0.0", ["$e", "$name"])],
                query_rel="query__ruleref",
            )
        self.assertIn("requires an in-memory rule resolver", str(ctx.exception))

    def test_compile_where_to_query_dl_supports_ne_filter(self) -> None:
        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=[
                ("pred", "user:name", ["$e", "$name"]),
                ("ne", "$name", "blocked"),
            ],
            query_rel="query__ne",
        )

        self.assertIn('query__ne(C0, C1) :- p_user_name(C0, C1), C1 != "blocked".', dl)

    def test_compile_where_to_query_dl_rejects_unbound_ne_filter(self) -> None:
        with patch.dict(os.environ, {"FACTPY_WHERE_AST_VALIDATE": "0"}):
            with self.assertRaises(WhereValidationError) as ctx:
                compile_where_to_query_dl(
                    schema_ir=_schema_ir(),
                    where=[("ne", "$name", "blocked")],
                    query_rel="query__ne_unbound",
                )

        self.assertIn("ne variable must be bound before filter: $name", str(ctx.exception))

    def test_compile_where_to_query_dl_supports_ne_in_not_body(self) -> None:
        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=[
                ("pred", "user:name", ["$e", "$name"]),
                ("not", [("ne", "$name", "blocked")]),
            ],
            query_rel="query__not_ne",
        )

        self.assertIn('C1 != "blocked"', dl)
        self.assertIn("!__not_", dl)

    def test_compile_where_to_query_dl_rejects_malformed_ne_shape(self) -> None:
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(
                schema_ir=_schema_ir(),
                where=[("ne", "$name")],
                query_rel="query__ne_bad",
            )

        self.assertIn("ne atom must be", str(ctx.exception))

    def test_ne_variables_participate_in_query_variable_extraction(self) -> None:
        layout = build_query_witness_layout(
            [
                ("pred", "user:name", ["$e", "$name"]),
                ("ne", "$name", "$other"),
            ]
        )

        self.assertEqual(layout.query_variables, ("$e", "$name", "$other"))

    # Q8 Phase 2 (Slice 6):
    # - test_export_package_threads_query_registry_root_for_ruleref was removed
    #   because `_load_query_rule_registry` was deleted; export_package no
    #   longer loads FS-saved rules via `query.registry_root`.
    # - test_export_package_loads_nested_ruleref_rules_from_registry_files was
    #   removed because `FileAuthoringRegistry.register_rule_spec` was deleted
    #   and export_package no longer supports FS-backed nested ruleref
    #   expansion. Equivalent in-memory testing of `compile_where_to_query_dl`
    #   with a `RuleRegistry` is covered by
    #   `test_compile_where_to_query_dl_rewrites_ruleref_with_registry` above.


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
            {
                "pred_id": "user:status",
                "cardinality": "single",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "status", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
        ]
    }


def _rule_registry() -> RuleRegistry:
    registry = RuleRegistry()
    registry.register(
        RuleSpec(
            rule_id="q.user_name_rows",
            version="1.0.0",
            select_vars=["$e", "$name"],
            where=[("pred", "user:name", ["$e", "$name"])],
            expose=True,
        )
    )
    return registry


if __name__ == "__main__":
    unittest.main()
