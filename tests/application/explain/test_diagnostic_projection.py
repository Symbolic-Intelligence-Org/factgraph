from __future__ import annotations

import unittest

from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticAtomProbability,
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.application.explain.diagnostic_assemble import diagnostic_problog_result_to_evidence_graph
from factgraph.application.explain.diagnostic_projection import (
    CompanionCompare,
    CompanionLiteral,
    DiagnosticProjectionError,
    Wildcard,
    build_companion_program,
)
from factgraph.application.protocol import Rule
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.explanation_render import narrate_evidence
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var


def _literal_predicates(body: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(atom.pred_id for atom in body if isinstance(atom, CompanionLiteral))


class DiagnosticProjectionTests(unittest.TestCase):
    def test_spike_companion_shapes_bind_chain_and_not_reached(self) -> None:
        employee = Var("$E")
        months = Var("$M")
        rule = Rule(
            id="full_time",
            when=(
                PredAtom("employee:exists", [employee]),
                PredAtom("employee:tenure_months", [employee, months]),
                CmpAtom("ge", months, Const(12)),
            ),
            ports={"employee": employee, "months": months},
        )
        plan = _lower_application_rule(rule, head=rule)

        program = build_companion_program(plan, {"employee": "emp-1"})

        branch = program.branches[0]
        self.assertEqual(program.anchor["$full_time__E"].value, "emp-1")
        self.assertEqual(len(branch.atoms), 3)
        exists, tenure, check = branch.atoms
        self.assertEqual(_literal_predicates(exists.holds_body), ("employee:exists",))
        self.assertEqual(_literal_predicates(tenure.holds_body), ("employee:tenure_months",))
        self.assertEqual(_literal_predicates(check.holds_body), ("employee:tenure_months",))
        self.assertIsInstance(check.holds_body[-1], CompanionCompare)
        self.assertEqual(check.not_reached[0].var, "$full_time__M")
        self.assertEqual(_literal_predicates(branch.bound_defs["$full_time__M"]), ("employee:tenure_months",))

    def test_join_bodies_group_occurrences_and_branch_body_keeps_join_and_head_links(self) -> None:
        speaker = Var("$speaker")
        language = Var("$language")
        age = Var("$age")
        speaks = Rule(
            id="speaks_language",
            when=(PredAtom("user:language", [speaker, language]),),
            ports={"speaker": speaker, "language": language},
        )
        age_filter = Rule(
            id="age_filter",
            when=(PredAtom("user:age", [speaker, age]), CmpAtom("ge", age, Const(5))),
            ports={"speaker": speaker, "age": age},
        )
        head = Rule(
            id="head",
            when=(PredAtom("head:result", [speaker, language]),),
            ports={"speaker": speaker, "language": language},
        )
        expr = (speaks.as_("speaks") & age_filter.as_("age")).join_by_ports("speaker")
        plan = _lower_rule_expr(expr, head=head)

        program = build_companion_program(plan, {"speaker": "Carol", "language": "German"})

        branch = program.branches[0]
        self.assertEqual(set(branch.occ_bodies), {"age", "speaks"})
        self.assertEqual(_literal_predicates(branch.occ_bodies["speaks"]), ("user:language",))
        self.assertEqual(_literal_predicates(branch.occ_bodies["age"]), ("user:age",))
        self.assertTrue(any(isinstance(atom, CompanionCompare) and atom.op == "eq" for atom in branch.branch_body))
        self.assertTrue(any(isinstance(atom, CompanionLiteral) and atom.pred_id == "head:result" for atom in branch.branch_body))

    def test_or_branches_are_projected_independently(self) -> None:
        x = Var("$x")
        left = Rule(id="left_rule", when=(PredAtom("left:p", [x]),), ports={"x": x})
        right = Rule(id="right_rule", when=(PredAtom("right:p", [x]),), ports={"x": x})
        head = Rule(id="head", when=(PredAtom("head:p", [x]),), ports={"x": x})
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=head)

        program = build_companion_program(plan, {"x": "v"})

        self.assertEqual([branch.branch_id for branch in program.branches], ["c0", "c1"])
        self.assertEqual(_literal_predicates(program.branches[0].occ_bodies["left"]), ("left:p",))
        self.assertEqual(_literal_predicates(program.branches[1].occ_bodies["right"]), ("right:p",))

    def test_seeded_variables_are_const_and_do_not_emit_not_reached(self) -> None:
        x = Var("$x")
        rule = Rule(id="seeded", when=(PredAtom("thing:p", [x]),), ports={"x": x})
        plan = _lower_application_rule(rule, head=rule)

        program = build_companion_program(plan, {"x": {"kind": "literal", "value": "item-1"}})

        atom = program.branches[0].atoms[0]
        literal = atom.holds_body[-1]
        self.assertIsInstance(literal, CompanionLiteral)
        self.assertEqual(literal.terms[0], Const("item-1"))
        self.assertEqual(atom.not_reached, ())

    def test_witness_preserves_full_term_order_with_constants_and_wildcard_failures(self) -> None:
        user = Var("$user")
        status = Var("$status")
        rule = Rule(
            id="status_rule",
            when=(PredAtom("sensor:status", [user, Const("online"), status]),),
            ports={"user": user, "status": status},
        )
        plan = _lower_application_rule(rule, head=rule)

        program = build_companion_program(plan, {"user": "sensor-1"})

        atom = program.branches[0].atoms[0]
        assert atom.witness is not None
        self.assertEqual(atom.witness.terms, (Const("sensor-1"), Const("online"), Var("$status_rule__status")))
        fail_literal = atom.fails_body[-1]
        self.assertIsInstance(fail_literal, CompanionLiteral)
        self.assertEqual(fail_literal.terms, (Const("sensor-1"), Const("online"), Wildcard()))

    def test_bound_defs_keep_positive_multi_hop_chain_for_not_reached(self) -> None:
        user = Var("$user")
        country = Var("$country")
        language = Var("$language")
        name = Var("$name")
        rule = Rule(
            id="language_name",
            when=(
                PredAtom("user:country", [user, country]),
                PredAtom("country:language", [country, language]),
                PredAtom("language:name", [language, name]),
            ),
            ports={"user": user, "name": name},
        )
        plan = _lower_application_rule(rule, head=rule)

        program = build_companion_program(plan, {"user": "u-1"})

        branch = program.branches[0]
        lowered_language = "$language_name__language"
        self.assertEqual(
            _literal_predicates(branch.bound_defs[lowered_language]),
            ("user:country", "country:language"),
        )
        last = branch.atoms[2]
        self.assertEqual(last.not_reached[0].var, lowered_language)

    def test_missing_binder_var_has_no_bound_def_but_still_emits_not_reached(self) -> None:
        left = Var("$left")
        right = Var("$right")
        rule = Rule(id="missing_binder", when=(CmpAtom("eq", left, right),), ports={"left": left})
        plan = _lower_application_rule(rule, head=rule)

        program = build_companion_program(plan, {"left": "x"})

        branch = program.branches[0]
        lowered_right = "$missing_binder__right"
        self.assertEqual(branch.bound_defs, {})
        self.assertEqual(branch.atoms[0].not_reached[0].var, lowered_right)

    def test_defer_aggregate_terms_with_clear_error(self) -> None:
        total = Var("$total")
        amount = Var("$amount")
        order = Var("$order")
        aggregate = AggregateAtom("sum", amount, [PredAtom("order:amount", [order, amount])])
        rule = Rule(id="agg_rule", when=(CmpAtom("eq", total, aggregate),), ports={"total": total})
        plan = _lower_application_rule(rule, head=rule)

        with self.assertRaisesRegex(DiagnosticProjectionError, "aggregate terms are not supported"):
            build_companion_program(plan, {"total": 10})

    def test_problog_assembly_uses_input_certainty_for_pred_atoms(self) -> None:
        user = Var("$user")
        country = Var("$country")
        language = Var("$language")
        name = Var("$name")
        rule = Rule(
            id="language_for_user",
            when=(
                PredAtom("user:country", [user, country]),
                PredAtom("country:language", [country, language]),
                PredAtom("language:name", [language, name]),
            ),
            ports={"user": user, "name": name},
            repr="%user speaks %name",
        )
        plan = _lower_application_rule(rule, head=rule)
        program = build_companion_program(plan, {"user": "u-1", "name": "German"})
        branch_id = program.branches[0].branch_id
        occurrence_alias = plan.branches[0].occurrence_aliases[0]
        result = DiagnosticProbLogResult(
            atom_probabilities=(
                DiagnosticAtomProbability(branch_id, 0, "holds", 0.765),
                DiagnosticAtomProbability(branch_id, 1, "holds", 0.765),
                DiagnosticAtomProbability(branch_id, 2, "holds", 0.765),
            ),
            witnesses=(
                DiagnosticWitnessProbability(branch_id, 0, ("u-1", "US"), 0.765),
                DiagnosticWitnessProbability(branch_id, 1, ("US", "de"), 0.765),
                DiagnosticWitnessProbability(branch_id, 2, ("de", "German"), 0.765),
            ),
            branch_probabilities={branch_id: 0.765},
            occurrence_probabilities={(branch_id, occurrence_alias): 0.765},
        )

        def input_certainty(goal_name: str, goal_args: tuple[object, ...]) -> Certainty | None:
            self.assertEqual(goal_name, "edb_fact")
            pred_id = goal_args[1]
            if pred_id == "user:country":
                return Certainty(0.9, 0.9, "probabilistic")
            if pred_id == "country:language":
                return Certainty(0.85, 0.85, "probabilistic")
            return None

        graph = diagnostic_problog_result_to_evidence_graph(
            result,
            plan=plan,
            companion=program,
            graph_id="graph",
            engine="problog",
            view_facts={},
            schema_index=None,
            rules_by_id={rule.id: rule},
            subject_binding={"user": "u-1", "name": "German"},
            graph_certainty=Certainty(0.765, 0.765, "probabilistic"),
            input_certainty_for_goal=input_certainty,
        )

        atoms = graph.paths[0].rules[1].atoms
        self.assertEqual(
            [atom.verdict.certainty for atom in atoms],
            [
                Certainty(0.9, 0.9, "probabilistic"),
                Certainty(0.85, 0.85, "probabilistic"),
                Certainty(1.0, 1.0, "boolean"),
            ],
        )
        narrative = narrate_evidence(graph, status="passed")
        self.assertIn("  language_for_user  [holds]  (p = 0.9 × 0.85 × 1 = 0.765)", narrative)


if __name__ == "__main__":
    unittest.main()
