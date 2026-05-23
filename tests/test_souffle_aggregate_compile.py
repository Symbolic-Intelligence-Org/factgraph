"""T2.3c — Souffle aggregate adapter wire acceptance tests.

Tests organized per blueprint §7.1-§7.11 with discriminator design per
the T2.3b cross-flip inversion lesson: each test discriminates a specific
algorithm decision in the impl.
"""

from __future__ import annotations

import os
import unittest

from factgraph.adapters.souffle.where_compile import (
    compile_where_to_query_dl,
    extract_where_variables,
    _infer_var_type_domains,
    _validate_atom_subset,
)
from factgraph.core.rules.where_eval import WhereValidationError


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "User:exists",
                "arg_specs": [{"name": "u", "type_domain": "User"}],
            },
            {
                "pred_id": "Order:exists",
                "arg_specs": [{"name": "o", "type_domain": "Order"}],
            },
            {
                "pred_id": "user:status",
                "arg_specs": [
                    {"name": "u_ref", "type_domain": "User"},
                    {"name": "status", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "order:amount",
                "arg_specs": [
                    {"name": "o_ref", "type_domain": "Order"},
                    # T2.3c test schema uses "int" type_domain so
                    # _assert_cmp_var_allowed accepts filter-internal numeric
                    # cmp on this field. Production schemas using "number"
                    # type for numeric fields would currently fall outside
                    # cmp-allowed types — a pre-existing limitation not
                    # specific to T2.3c.
                    {"name": "amount", "type_domain": "int"},
                ],
            },
            {
                "pred_id": "order:buyer",
                "arg_specs": [
                    {"name": "o_ref", "type_domain": "Order"},
                    {"name": "buyer", "type_domain": "User"},
                ],
            },
            {
                "pred_id": "order:cancelled",
                "arg_specs": [{"name": "o_ref", "type_domain": "Order"}],
            },
        ]
    }


class _PerKindCompileDiscriminatorTests(unittest.TestCase):
    """§7.1 — per-kind compile discriminators (5 tests)."""

    def test_count_compiles_to_native_count_clause(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$cnt", ("count", None, [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("count : {", dl)
        # No guard for count (empty-set=0 is legal C101 value).
        self.assertNotIn("} > 0,", dl)

    def test_sum_compiles_with_target_to_number(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$total", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("sum to_number(", dl)
        # No guard for sum.
        self.assertNotIn("} > 0,", dl)

    def test_min_compiles_with_guard_prefix(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$mn", ("min", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("count : {", dl)
        self.assertIn("} > 0", dl)
        self.assertIn("min to_number(", dl)

    def test_max_compiles_with_guard_prefix(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$mx", ("max", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("} > 0", dl)
        self.assertIn("max to_number(", dl)

    def test_mean_compiles_with_guard_prefix(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$avg", ("mean", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("} > 0", dl)
        self.assertIn("mean to_number(", dl)


class _CmpAndBindingTests(unittest.TestCase):
    """§7.2 / §7.3 — aggregate in eq RHS / gt cmp."""

    def test_eq_aggregate_rhs_binds_outer_var_via_to_string(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$total", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Eq binding: var = to_string(<aggregate>) per §5.3.5 v3 lock
        self.assertIn("= to_string(sum to_number", dl)

    def test_gt_aggregate_lhs_int_literal_rhs_no_to_string(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("gt", ("count", None, [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
            ]), 5),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Numeric cmp with literal: bare aggregate, no to_string wrap
        self.assertIn("count : {", dl)
        self.assertIn("} > 5", dl)
        self.assertNotIn("to_string(count", dl)


class _CorrelationAndIsolationTests(unittest.TestCase):
    """§7.4 / §7.5 — correlated outer var pass-through + aggregate-local isolation."""

    def test_extract_where_variables_excludes_aggregate_local_vars(self) -> None:
        """§7.4 / §7.5 P1 v2 + P1 v3: aggregate side contributes ZERO outer vars.

        $u is contributed by outer User:exists pred (NOT by aggregate-filter
        reference). $o and $_agg1 are aggregate-local and MUST NOT appear in
        outer extract.
        """
        where = [
            [("pred", "User:exists", ["$u"]),
             ("eq", "$total", ("sum", "$_agg1", [
                 ("pred", "Order:exists", ["$o"]),
                 ("pred", "order:buyer", ["$o", "$u"]),
                 ("pred", "order:amount", ["$o", "$_agg1"]),
             ]))]
        ]
        variables = extract_where_variables(where)
        self.assertEqual(variables, ["$total", "$u"])

    def test_aggregate_local_var_leak_into_outer_raises(self) -> None:
        """§7.5 TRUE C104 isolation discriminator via `ne` bound-required atom.

        If aggregate-local $o leaked into outer bound_vars, subsequent
        `ne $o "blocked"` would compile silently. Since $o is correctly
        isolated, either substrate C104 validator catches first (gate ON)
        OR adapter `ne` filter raises 'variable must be bound before filter'
        (gate OFF). Both paths assert WhereValidationError; message-level
        match accepts either upstream or downstream error.
        """
        where = [
            ("eq", "$total", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
            ("ne", "$o", "blocked"),
        ]
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        msg = str(ctx.exception).lower()
        # Either substrate message ("aggregate-local vars leak into outer
        # scope") or adapter message ("ne variable must be bound") is
        # acceptable — both indicate isolation correctly enforced.
        self.assertTrue(
            "leak" in msg or "must be bound" in msg or "$o" in msg,
            f"Expected isolation-related error, got: {ctx.exception}",
        )


class _FilterNotBodyTests(unittest.TestCase):
    """§7.6 — filter `not` body inside aggregate."""

    def test_not_body_in_aggregate_filter_extracts_synthetic_relation(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$cnt", ("count", None, [
                ("pred", "Order:exists", ["$o"]),
                ("not", [("pred", "order:cancelled", ["$o"])]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Synthetic not-relation declaration + use inside aggregate body
        self.assertIn(".decl __not_", dl)
        self.assertIn("p_order_cancelled(", dl)
        # Aggregate body references the synthetic not-relation via !
        self.assertIn("!__not_", dl)


class _MalformedAggregateTests(unittest.TestCase):
    """§7.7 — validation rejects malformed aggregate shape."""

    def test_validate_rejects_unknown_aggregate_kind(self) -> None:
        """Unknown aggregate kind: `_is_aggregate` returns False (kind not in
        _AGGREGATE_KINDS) so validator does not specifically reject as
        aggregate, but compile path raises 'unsupported literal type' when
        the unknown tuple reaches `_literal_to_*`. Test verifies SOME error
        surfaces (compile-time safety net) — either validation or compile.
        """
        where = [("eq", "$x", ("bogus_kind", "$y", []))]
        with self.assertRaises(WhereValidationError):
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")

    def test_validate_rejects_aggregate_tuple_wrong_arity(self) -> None:
        atom = ("eq", "$x", ("sum",))
        with self.assertRaises(WhereValidationError) as ctx:
            _validate_atom_subset(atom)
        self.assertIn("aggregate atom must be", str(ctx.exception))


class _GuardEmitShapeTests(unittest.TestCase):
    """§7.8 — empty-set guard + to_string/to_number wrapping discriminators (P0 v2 + P3 v3)."""

    def test_eq_binding_min_emits_guard_and_to_string(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$min_amount", ("min", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Guard clause must be peer body atom (NOT inside to_string)
        self.assertRegex(dl, r"count : \{[^}]+\} > 0")
        # Value clause wrapped in to_string for symbol binding
        self.assertRegex(dl, r"= to_string\(min to_number\(")

    def test_gt_max_with_literal_no_to_string_wrap(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("gt", ("max", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ]), 5),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Guard prefix
        self.assertRegex(dl, r"count : \{[^}]+\} > 0,")
        # Numeric cmp: no to_string wrap around aggregate value
        self.assertIn("max to_number(", dl)
        self.assertNotIn("to_string(max", dl)

    def test_eq_binding_mean_emits_guard_and_to_string(self) -> None:
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$avg", ("mean", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertRegex(dl, r"count : \{[^}]+\} > 0")
        self.assertRegex(dl, r"= to_string\(mean to_number\(")

    def test_count_no_guard_emit_to_string(self) -> None:
        """§7.8(e) negative discriminator — count/sum must NOT have guard."""
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$cnt", ("count", None, [
                ("pred", "Order:exists", ["$o"]),
            ])),
        ]
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # to_string wrap for symbol binding
        self.assertIn("= to_string(count : {", dl)
        # NO guard prefix for count
        self.assertNotIn("} > 0,", dl)


class _GateValidationTests(unittest.TestCase):
    """§7.10 — adapter validates regardless of FACTPY_WHERE_AST_VALIDATE gate state."""

    def _set_gate(self, value: str) -> None:
        os.environ["FACTPY_WHERE_AST_VALIDATE"] = value

    def tearDown(self) -> None:
        # Restore default gate state.
        os.environ["FACTPY_WHERE_AST_VALIDATE"] = "1"

    def test_unknown_aggregate_kind_rejected_with_gate_on(self) -> None:
        self._set_gate("1")
        where = [("eq", "$x", ("bogus_kind", "$y", []))]
        with self.assertRaises(WhereValidationError):
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")

    def test_unknown_aggregate_kind_rejected_with_gate_off(self) -> None:
        """Gate OFF + unknown aggregate kind: SOME WhereValidationError must
        surface (adapter is only safety net; compile path cannot proceed on
        unknown tuple shape). Per-message form: 'unsupported literal type'
        (current fallback path via _literal_to_text) or future-proofed
        'unsupported aggregate kind' if `_is_aggregate` widens.
        """
        self._set_gate("0")
        where = [("eq", "$x", ("bogus_kind", "$y", []))]
        with self.assertRaises(WhereValidationError):
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")


class _ArithInFilterTests(unittest.TestCase):
    """§7.10b — adapter rejects non-C100 filter atom kinds regardless of gate (P1 v4 lock)."""

    def tearDown(self) -> None:
        os.environ["FACTPY_WHERE_AST_VALIDATE"] = "1"

    def test_arith_atom_in_aggregate_filter_rejected_gate_on(self) -> None:
        """Gate ON: substrate T2.3a C100 validator catches first with its
        own error message ('aggregate filter[N] kind not allowed: add').
        Both substrate and adapter messages indicate rejection — verify
        WhereValidationError surfaces.
        """
        os.environ["FACTPY_WHERE_AST_VALIDATE"] = "1"
        where = [
            ("eq", "$result", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
                ("add", "$z", "$_agg1", 5),  # ArithExpr not in C100 filter list
            ])),
        ]
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        msg = str(ctx.exception).lower()
        self.assertTrue(
            "add" in msg and ("not allowed" in msg or "kind" in msg),
            f"Expected C100-rejection error, got: {ctx.exception}",
        )

    def test_arith_atom_in_aggregate_filter_rejected_gate_off(self) -> None:
        """Gate OFF: substrate validator skipped; adapter `_validate_aggregate_
        atom_shape` is only safety net. Adapter message: 'add not allowed
        inside aggregate filter (C100)'.
        """
        os.environ["FACTPY_WHERE_AST_VALIDATE"] = "0"
        where = [
            ("eq", "$result", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
                ("add", "$z", "$_agg1", 5),
            ])),
        ]
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        # Adapter is sole safety net; expect adapter's structural message.
        self.assertIn("not allowed inside aggregate filter", str(ctx.exception))


class _TypeDomainInferenceTests(unittest.TestCase):
    """§7.11 — _infer_var_type_domains aggregate-filter recursion (P2 v3 lock)."""

    def test_aggregate_target_var_marked_int(self) -> None:
        body = [
            ("eq", "$result", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ]))
        ]
        pred_types = {
            "Order:exists": ["Order"],
            "order:amount": ["Order", "number"],
        }
        domains = _infer_var_type_domains(body, pred_types)
        # Aggregate target_var explicitly marked int per C102
        self.assertIn("$_agg1", domains)
        self.assertIn("int", domains["$_agg1"])

    def test_filter_internal_numeric_cmp_compiles_with_inferred_type(self) -> None:
        """Filter-internal `gt($_agg1, 5)` needs $_agg1 in type domain.

        Without §2.6b v3 P2 fix (`_infer_var_type_domains` not walking
        aggregate filter), this would raise 'gt variable type unknown'.
        """
        where = [
            ("pred", "User:exists", ["$u"]),
            ("eq", "$result", ("sum", "$_agg1", [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
                ("gt", "$_agg1", 5),  # filter-internal cmp
            ])),
        ]
        # Should compile without "unknown type" error.
        dl = compile_where_to_query_dl(where=where, schema_ir=_schema_ir(), query_rel="Q")
        self.assertIn("sum to_number(", dl)


class _AggregateValidatorShapeTests(unittest.TestCase):
    """Extra shape-validation coverage for §5.7.5 Layer 1 structural validation."""

    def test_count_target_var_must_be_none(self) -> None:
        atom = ("eq", "$x", ("count", "$something", []))
        with self.assertRaises(WhereValidationError) as ctx:
            _validate_atom_subset(atom)
        self.assertIn("count aggregate target_var must be None", str(ctx.exception))

    def test_numeric_aggregate_target_var_must_be_dollar_prefixed(self) -> None:
        atom = ("eq", "$x", ("sum", "no_dollar_prefix", []))
        with self.assertRaises(WhereValidationError) as ctx:
            _validate_atom_subset(atom)
        self.assertIn("$-prefixed variable", str(ctx.exception))

    def test_nested_aggregate_rejected_in_filter(self) -> None:
        atom = ("eq", "$x", ("sum", "$_agg1", [
            ("sum", "$_agg2", [("pred", "Order:exists", ["$o"])]),
        ]))
        with self.assertRaises(WhereValidationError) as ctx:
            _validate_atom_subset(atom)
        self.assertIn("aggregate not allowed inside aggregate filter", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
