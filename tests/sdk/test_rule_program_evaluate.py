from __future__ import annotations

from factgraph.core.rules.where_ast import Const, PredAtom, Var
from factgraph.application.explain import evidence_graph_to_dict
from factgraph.application.protocol.explanation_render import narrate_evidence
from factgraph.sdk import (
    Entity,
    EvaluationPremiseScope,
    FactGraph,
    Field,
    Identity,
    MetaExclusion,
    Rule,
    RuleProgram,
    RuleProgramClause,
    RuleProgramFact,
    RuleProgramGoal,
)


class Gate(Entity):
    gate_id: str = Identity()


class Outcome(Entity):
    outcome_id: str = Identity()


class DecisionCase(Entity):
    case_id: str = Identity()
    evidence: str = Field()
    approval: str = Field()
    gate: Gate = Field()
    decision: Outcome = Field()


def _program() -> RuleProgram:
    case = Var("$case")
    gate = Var("$gate")
    outcome = Var("$outcome")

    evidence_gate_body = Rule(
        id="evidence_gate_body",
        when=(
            PredAtom("DecisionCase:exists", [case]),
            PredAtom("decision_case:evidence", [case, Const("received")]),
            PredAtom("Gate:exists", [gate]),
            PredAtom("gate:gate_id", [gate, Const("met")]),
        ),
        ports={"case": case, "gate": gate},
    )
    evidence_gate_head = Rule(
        id="decision_case:gate",
        when=(
            PredAtom("DecisionCase:exists", [case]),
            PredAtom("Gate:exists", [gate]),
            PredAtom("gate:gate_id", [gate, Const("met")]),
        ),
        ports={"case": case, "gate": gate},
    )
    allow_body = Rule(
        id="allow_body",
        when=(
            PredAtom("DecisionCase:exists", [case]),
            PredAtom("decision_case:gate", [case, gate]),
            PredAtom("decision_case:approval", [case, Const("approved")]),
            PredAtom("Outcome:exists", [outcome]),
            PredAtom("outcome:outcome_id", [outcome, Const("allow")]),
        ),
        ports={"case": case, "outcome": outcome},
    )
    allow_head = Rule(
        id="decision_case:decision",
        when=(
            PredAtom("DecisionCase:exists", [case]),
            PredAtom("Outcome:exists", [outcome]),
            PredAtom("outcome:outcome_id", [outcome, Const("allow")]),
        ),
        ports={"case": case, "outcome": outcome},
    )
    return RuleProgram(
        (
            RuleProgramClause(
                rule_id="decision.evidence_gate",
                body=evidence_gate_body,
                head=evidence_gate_head,
            ),
            RuleProgramClause(
                rule_id="decision.allow",
                body=allow_body,
                head=allow_head,
            ),
        )
    )


def _world(*, evidence: str | None = "received", evidence_meta=None):
    fg = FactGraph.create(schema_classes=[DecisionCase, Gate, Outcome])
    case_ref = fg.entities.create(DecisionCase, case_id="case-1")
    gate_ref = fg.entities.create(Gate, gate_id="met")
    outcome_ref = fg.entities.create(Outcome, outcome_id="allow")
    evidence_assertion = None
    if evidence is not None:
        evidence_assertion = fg.fields.set(
            DecisionCase.evidence,
            case_ref,
            evidence,
            meta=evidence_meta,
        )
    fg.fields.set(DecisionCase.approval, case_ref, "approved")
    return fg, case_ref, gate_ref, outcome_ref, evidence_assertion


def _goal(case_ref: str, outcome_ref: str) -> RuleProgramGoal:
    return RuleProgramGoal(
        predicate="decision_case:decision",
        terms=(case_ref, outcome_ref),
    )


def test_multilayer_program_uses_same_ledger_and_original_assertion_ids() -> None:
    fg, case_ref, _gate_ref, outcome_ref, evidence_assertion = _world()
    before_claims = tuple(fg.ledger.claims)
    before_revokes = tuple(fg.ledger.revokes)

    result = fg.eval.evaluate_program(_program(), _goal(case_ref, outcome_ref))

    assert result.entailed is True
    assert result.matched_rule_ids == ("decision.allow", "decision.evidence_gate")
    assert tuple(fg.ledger.claims) == before_claims
    assert tuple(fg.ledger.revokes) == before_revokes
    explanation = result.explain()
    assert explanation.status == "passed"
    assert len(explanation.steps) >= 3
    witness_ids = {
        assertion_id
        for step in explanation.steps
        for witness in step["factgraph_explain"].get("pred_witnesses", [])
        for assertion_id in witness.get("asrt_ids", [])
    }
    assert evidence_assertion in witness_ids
    narration = explanation.narrate()
    assert narration[0].startswith("Conclusion ──")
    assert any("decision.allow" in line and "[holds]" in line for line in narration)
    assert any("decision.evidence_gate" in line and "[holds]" in line for line in narration)
    assert any("received" in line for line in narration)
    assert narration == narrate_evidence(
        explanation.evidence,
        status=explanation.status,
        failure_class=explanation.failure_class,
    )
    encoded = evidence_graph_to_dict(explanation.evidence)
    sources = {
        source["ref"]
        for path in encoded["paths"]
        for rule in path.get("rules", [])
        for atom in rule.get("atoms", [])
        for source in atom.get("verdict", {}).get("support", [])
    }
    assert evidence_assertion in sources


def test_program_ignores_materialized_head_from_rule_outside_selected_program() -> None:
    fg, case_ref, gate_ref, outcome_ref, _evidence_assertion = _world(evidence=None)
    fg.fields.set(
        DecisionCase.gate,
        case_ref,
        gate_ref,
        meta={"derived_rule_id": "outside.policy.rule"},
    )
    before = tuple(fg.ledger.claims)

    result = fg.eval.evaluate_program(_program(), _goal(case_ref, outcome_ref))

    assert result.entailed is False
    explanation = result.explain()
    assert explanation.failure_class == "closed_goal_not_entailed"
    assert explanation.narrate()[0].startswith("NOT concluded ──")
    assert explanation.checked_scope["effective_rule_ids"] == [
        "decision.allow",
        "decision.evidence_gate",
    ]
    assert explanation.evidence.paths[0].status == "fails"
    failed_rules = [
        rule
        for rule in explanation.evidence.paths[0].rules
        if rule.status == "fails"
    ]
    assert [rule.rule_id for rule in failed_rules] == ["decision.allow"]
    assert any(
        type(atom.verdict).__name__ == "Fails"
        for atom in failed_rules[0].atoms
    )
    assert tuple(fg.ledger.claims) == before


def test_program_narration_is_frozen_with_the_evaluation_snapshot() -> None:
    fg, case_ref, _gate_ref, outcome_ref, _evidence_assertion = _world()
    result = fg.eval.evaluate_program(_program(), _goal(case_ref, outcome_ref))
    expected = result.explain().narrate()

    fg.fields.set(DecisionCase.evidence, case_ref, "changed later")
    fg.store._support_artifacts.clear()

    assert result.explain().narrate() == expected
    assert result.explain().steps


def test_evaluation_scope_can_relax_one_filter_without_mutating_graph_config() -> None:
    fg, case_ref, _gate_ref, outcome_ref, evidence_assertion = _world(
        evidence_meta={"provenance_class": "claimed_by_agent"}
    )
    exclusion = MetaExclusion(
        key="provenance_class",
        values=frozenset({"claimed_by_agent"}),
    )
    fg.set_premise_exclusions((exclusion,))

    authoritative = fg.eval.evaluate_program(_program(), _goal(case_ref, outcome_ref))
    advisory = fg.eval.evaluate_program(
        _program(),
        _goal(case_ref, outcome_ref),
        scope=EvaluationPremiseScope(exclusions=()),
    )

    assert authoritative.entailed is False
    assert advisory.entailed is True
    assert fg.premise_exclusions == (exclusion,)
    advisory_ids = {
        assertion_id
        for step in advisory.explain().steps
        for witness in step["factgraph_explain"].get("pred_witnesses", [])
        for assertion_id in witness.get("asrt_ids", [])
    }
    assert evidence_assertion in advisory_ids
    assert authoritative.view_snapshot_digest != advisory.view_snapshot_digest


def test_program_facts_ground_ontology_constants_without_ledger_writes() -> None:
    fg = FactGraph.create(schema_classes=[DecisionCase, Gate, Outcome])
    case_ref = fg.entities.create(DecisionCase, case_id="case-1")
    fg.fields.set(DecisionCase.evidence, case_ref, "received")
    fg.fields.set(DecisionCase.approval, case_ref, "approved")
    gate_ref = fg.entities.ref(Gate, gate_id="met")
    outcome_ref = fg.entities.ref(Outcome, outcome_id="allow")
    facts = (
        RuleProgramFact(
            fact_id="program:gate:exists",
            predicate="Gate:exists",
            terms=(gate_ref,),
            provenance={"kind": "ontology_constant", "rule_id": "decision.evidence_gate"},
        ),
        RuleProgramFact(
            fact_id="program:gate:id",
            predicate="gate:gate_id",
            terms=(gate_ref, "met"),
            provenance={"kind": "ontology_constant", "rule_id": "decision.evidence_gate"},
        ),
        RuleProgramFact(
            fact_id="program:outcome:exists",
            predicate="Outcome:exists",
            terms=(outcome_ref,),
            provenance={"kind": "ontology_constant", "rule_id": "decision.allow"},
        ),
        RuleProgramFact(
            fact_id="program:outcome:id",
            predicate="outcome:outcome_id",
            terms=(outcome_ref, "allow"),
            provenance={"kind": "ontology_constant", "rule_id": "decision.allow"},
        ),
    )
    base = _program()
    program = RuleProgram(base.clauses, facts=facts)
    before = tuple(fg.ledger.claims)

    result = fg.eval.evaluate_program(program, _goal(case_ref, outcome_ref))

    assert result.entailed is True
    assert tuple(fg.ledger.claims) == before
    witness_ids = {
        assertion_id
        for step in result.explain().steps
        for witness in step["factgraph_explain"].get("pred_witnesses", [])
        for assertion_id in witness.get("asrt_ids", [])
    }
    assert {fact.fact_id for fact in facts} <= witness_ids
    assert result.program_facts == facts
