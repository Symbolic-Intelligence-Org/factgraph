from __future__ import annotations

import unittest

from factgraph.adapters.problog.diagnostic_emit import (
    emit_diagnostic_problog,
    parse_diagnostic_problog_output,
)
from factgraph.application.explain.diagnostic_projection import (
    BranchCompanion,
    CompanionAtomRules,
    CompanionLiteral,
    CompanionNotReached,
    CompanionProgram,
    CompanionWitness,
)
from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import Const, PredAtom, Var
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStore


class DiagnosticEmitUser(Entity):
    user_id: str = Identity()
    name: str = Field()


class ProbLogDiagnosticEmitTests(unittest.TestCase):
    def test_emit_includes_companion_queries_and_bound_defs(self) -> None:
        sdk = SDKStore([DiagnosticEmitUser])
        rule = Rule(
            id="diagnostic_emit_rule",
            when=(PredAtom("diagnostic_emit_user:name", [Var("$u"), Var("$name")]),),
            ports={"user": Var("$u")},
        )
        program = CompanionProgram(
            anchor={"$u": Const("u-1")},
            branches=(
                BranchCompanion(
                    branch_id="c0",
                    atoms=(
                        CompanionAtomRules(
                            branch_id="c0",
                            atom_index=0,
                            holds_body=(CompanionLiteral("diagnostic_emit_user:name", (Const("u-1"), Var("$name"))),),
                            fails_body=(CompanionLiteral("diagnostic_emit_user:name", (Const("u-1"),)),),
                            not_reached=(CompanionNotReached("$name"),),
                            witness=CompanionWitness((Const("u-1"), Var("$name"))),
                        ),
                    ),
                    branch_body=(CompanionLiteral("diagnostic_emit_user:name", (Const("u-1"), Var("$name"))),),
                    occ_bodies={"body": (CompanionLiteral("diagnostic_emit_user:name", (Const("u-1"), Var("$name"))),)},
                    bound_defs={"$name": (CompanionLiteral("diagnostic_emit_user:name", (Const("u-1"), Var("$name"))),)},
                ),
            ),
        )
        from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule

        plan = _lower_application_rule(rule, head=rule)

        text = emit_diagnostic_problog(sdk.store, plan, program)

        self.assertIn("bound_c0_name :- edb_fact(", text)
        self.assertIn("expl('c0', 0, 'holds')", text)
        self.assertIn("expl_wit('c0', 0, 'u-1', V_NAME)", text)
        self.assertIn("query(expl(_, _, _)).", text)
        self.assertIn("query(expl_occ(_, _)).", text)

    def test_parse_diagnostic_output(self) -> None:
        parsed = parse_diagnostic_problog_output(
            "\n".join(
                [
                    "expl(c0,0,holds): 0.4",
                    "expl(c0,1,not_reached,'$x'): 1",
                    "expl_wit(c0,0,'idref_v1:Sensor:abc','online'): 0.4",
                    "expl_branch(c0): 0.4",
                    "expl_occ(c0,status_rule): 0.4",
                ]
            )
        )

        self.assertEqual(parsed.atom_probabilities[0].verdict, "holds")
        self.assertEqual(parsed.atom_probabilities[1].blocked_by, "$x")
        self.assertEqual(parsed.witnesses[0].terms, ("idref_v1:Sensor:abc", "online"))
        self.assertEqual(parsed.branch_probabilities["c0"], 0.4)
        self.assertEqual(parsed.occurrence_probabilities[("c0", "status_rule")], 0.4)


if __name__ == "__main__":
    unittest.main()
