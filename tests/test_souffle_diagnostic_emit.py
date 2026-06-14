from __future__ import annotations

import unittest

from factgraph.adapters.souffle.diagnostic_emit import emit_diagnostic_souffle, run_diagnostic_souffle
from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.explain.diagnostic_projection import build_companion_program
from factgraph.application.explain.diagnostic_projection import (
    BranchCompanion,
    CompanionAtomRules,
    CompanionLiteral,
    CompanionNotReached,
    CompanionProgram,
    CompanionWitness,
)
from factgraph.application.protocol import EntitySelector, Rule
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, SDKStore


class DiagnosticSouffleUser(Entity):
    user_id: str = Identity()
    region: str = Field()


def _store() -> tuple[SDKStore, str]:
    graph = SDKStore([DiagnosticSouffleUser])
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(
        EntitySelector(entity_type="DiagnosticSouffleUser", identity={"user_id": "u-1"}),
        index=index,
    )
    encoded = ref.encoded_ref or ""
    info = entity_info(index, "DiagnosticSouffleUser")
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["user_id"].pred_id, encoded, [("string", "u-1")])
    set_field(
        graph.ledger,
        field_predicate(index, "DiagnosticSouffleUser", "region").pred_id,
        encoded,
        [("string", "us")],
    )
    return graph, encoded


def _rule() -> Rule:
    user = Var("$user")
    region = Var("$region")
    return Rule(
        id="souffle_diagnostic_region",
        when=(PredAtom("diagnostic_souffle_user:region", [user, region]),),
        ports={"user": user, "region": region},
    )


class DiagnosticSouffleEmitTests(unittest.TestCase):
    def test_emit_uses_normalized_schema_predicate_and_grounded_not_reached(self) -> None:
        _graph, encoded = _store()
        rule = _rule()
        plan = _lower_application_rule(rule, head=rule)
        companion = build_companion_program(plan, {"user": encoded})

        text = emit_diagnostic_souffle(companion)

        self.assertIn(normalize_pred_id("diagnostic_souffle_user:region"), text)
        self.assertIn(".decl dx_expl(", text)
        self.assertIn("dx_expl_occ(", text)

        manual = CompanionProgram(
            anchor={},
            branches=(
                BranchCompanion(
                    branch_id="c0",
                    atoms=(
                        CompanionAtomRules(
                            branch_id="c0",
                            atom_index=0,
                            holds_body=(CompanionLiteral("diagnostic_souffle_user:region", (Var("$u"), Var("$r"))),),
                            fails_body=(CompanionLiteral("diagnostic_souffle_user:region", (Var("$u"),)),),
                            not_reached=(CompanionNotReached("$r"),),
                            witness=CompanionWitness((Var("$u"), Var("$r"))),
                        ),
                    ),
                    branch_body=(CompanionLiteral("diagnostic_souffle_user:region", (Var("$u"), Var("$r"))),),
                    occ_bodies={},
                    bound_defs={"$r": (CompanionLiteral("diagnostic_souffle_user:region", (Var("$u"), Var("$r"))),)},
                ),
            ),
        )
        manual_text = emit_diagnostic_souffle(manual)
        self.assertIn(".decl dx_expl_bound_c0_r", manual_text)
        self.assertIn('!dx_expl_bound_c0_r("t")', manual_text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_run_reads_boolean_verdicts_and_witnesses(self) -> None:
        graph, encoded = _store()
        rule = _rule()
        plan = _lower_application_rule(rule, head=rule)
        companion = build_companion_program(plan, {"user": encoded})

        result = run_diagnostic_souffle(graph.store, companion)

        verdicts = {(row.branch_id, row.atom_index, row.verdict) for row in result.atom_probabilities}
        self.assertIn(("c0", 0, "holds"), verdicts)
        self.assertEqual(result.branch_probabilities["c0"], 1.0)
        self.assertTrue(result.witnesses)
        self.assertIn(encoded, result.witnesses[0].terms)
        self.assertIn("us", result.witnesses[0].terms)


if __name__ == "__main__":
    unittest.main()
