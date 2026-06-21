from __future__ import annotations

import unittest

from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticAtomProbability,
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.application.explain.diagnostic_assemble import diagnostic_problog_result_to_evidence_graph
from factgraph.application.explain.diagnostic_projection import BranchCompanion, CompanionProgram
from factgraph.application.protocol import Rule
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.explanation_render import narrate_evidence
from factgraph.application.protocol.rule_expr_lowering import RuleExprLoweringPlan, _lower_application_rule
from factgraph.core.rules.where_ast import Const, PredAtom, Var


def _minimal_companion(plan: RuleExprLoweringPlan, anchor: dict[str, object]) -> CompanionProgram:
    return CompanionProgram(
        anchor={key: Const(value) for key, value in anchor.items()},
        branches=tuple(
            BranchCompanion(
                branch_id=branch.branch_id,
                atoms=(),
                branch_body=(),
                occ_bodies={},
                bound_defs={},
            )
            for branch in plan.branches
        ),
    )


class DiagnosticProjectionTests(unittest.TestCase):
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
        program = _minimal_companion(
            plan,
            {
                "$language_for_user__user": "u-1",
                "$language_for_user__name": "German",
            },
        )
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
        self.assertTrue(any(line.startswith("  language_for_user  [holds]") and "0.765" in line for line in narrative))

    def test_assembly_not_reached_without_witness_does_not_render_unbound_terms(self) -> None:
        user = Var("$user")
        country = Var("$country")
        language = Var("$language")
        rule = Rule(
            id="language_for_user",
            when=(
                PredAtom("user:country", [user, country]),
                PredAtom("country:language", [country, language]),
            ),
            ports={"user": user},
        )
        plan = _lower_application_rule(rule, head=rule)
        program = _minimal_companion(plan, {"$language_for_user__user": "u-1"})
        branch_id = program.branches[0].branch_id
        result = DiagnosticProbLogResult(
            atom_probabilities=(
                DiagnosticAtomProbability(branch_id, 0, "holds", 1.0),
                DiagnosticAtomProbability(branch_id, 1, "not_reached", 1.0, blocked_by="upstream"),
            ),
            witnesses=(
                DiagnosticWitnessProbability(branch_id, 0, ("u-1", "US"), 1.0),
            ),
            branch_probabilities={branch_id: 1.0},
        )

        graph = diagnostic_problog_result_to_evidence_graph(
            result,
            plan=plan,
            companion=program,
            graph_id="graph",
            engine="souffle",
            view_facts={},
            schema_index=None,
            rules_by_id={rule.id: rule},
            subject_binding={"user": "u-1"},
            probabilistic=False,
        )

        narrative = "\n".join(narrate_evidence(graph, status="passed"))
        self.assertIn("country:language not reached", narrative)
        self.assertNotIn("<unbound>", narrative)


if __name__ == "__main__":
    unittest.main()
