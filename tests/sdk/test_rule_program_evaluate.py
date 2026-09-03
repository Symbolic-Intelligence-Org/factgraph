from __future__ import annotations

import hashlib
import json

import pytest

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
    SDKStoreError,
    PredicatePremiseBlock,
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


def test_evaluation_scope_cannot_bypass_schema_premise_closure() -> None:
    fg, case_ref, _gate_ref, outcome_ref, _evidence_assertion = _world()
    before = tuple(fg.ledger.claims)

    with pytest.raises(SDKStoreError, match="not declared premise_eligible"):
        fg.eval.evaluate_program(
            _program(),
            _goal(case_ref, outcome_ref),
            scope=EvaluationPremiseScope(
                blocks=(
                    PredicatePremiseBlock(
                        pred_id="decision_case:evidence",
                        key="undeclared",
                        blocked_values=frozenset({"blocked"}),
                    ),
                )
            ),
        )

    assert tuple(fg.ledger.claims) == before


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


def _program_overlay_world():
    fg = FactGraph.create(schema_classes=[DecisionCase, Gate, Outcome])
    case_ref = fg.entities.create(DecisionCase, case_id="case-1")
    evidence_id = fg.fields.set(DecisionCase.evidence, case_ref, "received")
    fg.fields.set(DecisionCase.approval, case_ref, "approved")
    gate_ref = fg.entities.ref(Gate, gate_id="met")
    outcome_ref = fg.entities.ref(Outcome, outcome_id="allow")
    facts = tuple(
        RuleProgramFact(ref, predicate, terms, {"declared_by": {"rules": ["test"]}})
        for ref, predicate, terms in (
            ("program:gate:exists", "Gate:exists", (gate_ref,)),
            ("program:gate:id", "gate:gate_id", (gate_ref, "met")),
            ("program:outcome:exists", "Outcome:exists", (outcome_ref,)),
            ("program:outcome:id", "outcome:outcome_id", (outcome_ref, "allow")),
        )
    )
    return fg, RuleProgram(_program().clauses, facts), _goal(case_ref, outcome_ref), evidence_id


def test_native_report_retains_every_original_mixed_origin_occurrence() -> None:
    fg, program, goal, evidence_id = _program_overlay_world()
    before = tuple(fg.ledger.claims)
    explanation = fg.eval.evaluate_program(program, goal).explain()
    report = explanation.witness_report.to_dict()
    assert report["contract"] == "factgraph.rule-program-witness-report.v1"
    assert report["status"] == "complete"
    assert report["availability_basis"] == "captured_evaluation"
    original = sorted(
        (step["support_digest"], witness["pred_condition_key"], ref)
        for step in explanation.steps
        for witness in step["factgraph_explain"]["pred_witnesses"]
        for ref in witness["asrt_ids"]
    )
    items = report["occurrences"]
    assert sorted((item["support_digest"], item["condition_key"], item["witness_ref"])
                  for item in items) == original
    assert len(items) == 14  # Includes the repeated head-foundation conditions.
    assert {item["kind"] for item in items} == {"assertion", "program_fact", "virtual"}
    assert {item["kind"] for item in items if item["witness_ref"] == evidence_id} == {"assertion"}
    for fact in program.facts:
        matches = [item for item in items if item["witness_ref"] == fact.fact_id]
        assert len(matches) == 2
        assert all(item["kind"] == "program_fact" for item in matches)
        assert all(item["program_fact_provenance"] == dict(fact.provenance) for item in matches)
        assert matches[0]["terms"][0] == {"tag": "entity_ref", "value": fact.terms[0]}
    assert all(item["availability"] == "available" for item in items)
    assert tuple(fg.ledger.claims) == before


def test_native_report_links_exact_sources_and_is_deeply_frozen() -> None:
    fg, program, goal, _ = _program_overlay_world()
    result = fg.eval.evaluate_program(program, goal)
    explanation = result.explain()
    expected = explanation.witness_report.to_dict()
    sources = {
        f"/paths/{p}/rules/{r}/atoms/{a}/verdict/support/{s}": source
        for p, path in enumerate(expected["evidence"]["paths"])
        for r, rule in enumerate(path["rules"])
        for a, atom in enumerate(rule["atoms"])
        for s, source in enumerate(atom["verdict"].get("support", []))
    }
    links = expected["source_links"]
    assert {link["pointer"] for link in links} == set(sources)
    items = {(item["support_digest"], item["condition_key"], item["witness_ref"]): item
             for item in expected["occurrences"]}
    for link in links:
        assert link["status"] == "captured"
        assert len(link["occurrences"]) == 1
        coordinate = link["occurrences"][0]
        item = items[(coordinate["support_digest"], coordinate["condition_key"], coordinate["witness_ref"])]
        assert item["witness_ref"] == sources[link["pointer"]]["ref"]
        assert item["predicate_id"] == sources[link["pointer"]]["field"]
    before_narration = explanation.narrate()
    explanation.steps[0]["factgraph_explain"].clear()
    with pytest.raises(TypeError):
        explanation.evidence.metadata["rule_set_digest"] = "tampered"
    program.facts[0].provenance["declared_by"]["rules"].append("mutated")
    detached = explanation.witness_report.to_dict()
    detached["occurrences"].clear()
    fg.fields.set(DecisionCase.evidence, goal.terms[0], "changed")
    fg.close()
    assert result.explain().witness_report.to_dict() == expected
    assert list(result.explain().steps) == expected["support_steps"]
    assert result.explain().narrate() == before_narration


@pytest.mark.parametrize("corruption", ["digest", "receipt", "source", "occurrence", "field", "typed_value"])
def test_native_report_codec_rejects_tamper_and_invalid_associations(corruption) -> None:
    from factgraph.sdk import RuleProgramWitnessError, RuleProgramWitnessReportV1

    fg, program, goal, _ = _program_overlay_world()
    report = fg.eval.evaluate_program(program, goal).explain().witness_report
    assert RuleProgramWitnessReportV1.from_json(report.to_json()).to_dict() == report.to_dict()
    payload = report.to_dict()
    if corruption == "digest":
        payload["engine"] = "tampered"
    elif corruption == "receipt":
        next(step["factgraph_explain"]["binding"] for step in payload["support_steps"]
             if step["factgraph_explain"]["binding"]).clear()
    elif corruption == "source":
        payload["source_links"][0]["occurrences"][0]["condition_key"] = "not-an-original-condition"
    elif corruption == "occurrence":
        payload["occurrences"].pop()
    elif corruption == "field":
        payload["invented_permission"] = True
    else:
        payload["occurrences"][0]["terms"][0]["tag"] = "string"
    if corruption != "digest":
        payload.pop("report_digest")
        payload["report_digest"] = "sha256:" + hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
    with pytest.raises(RuleProgramWitnessError):
        RuleProgramWitnessReportV1.from_dict(payload)


def test_native_report_why_not_and_duplicate_json_keys_fail_closed() -> None:
    from factgraph.sdk import RuleProgramWitnessError, RuleProgramWitnessReportV1

    fg, case_ref, _, outcome_ref, _ = _world(evidence=None)
    report = fg.eval.evaluate_program(_program(), _goal(case_ref, outcome_ref)).explain().witness_report
    payload = report.to_dict()
    assert payload["status"] == "not_applicable"
    assert payload["occurrences"] == []
    assert payload["source_links"]
    assert all(link["status"] == "diagnostic_only" and not link["occurrences"]
               for link in payload["source_links"])
    assert RuleProgramWitnessReportV1.from_json(report.to_json()).to_dict() == payload
    with pytest.raises(RuleProgramWitnessError, match="Duplicate"):
        RuleProgramWitnessReportV1.from_json(b'{"contract": "one", "contract": "two"}')


def test_native_overlay_equal_tuple_keeps_selected_ledger_origin() -> None:
    fg, case, gate, outcome, _ = _world()
    unused = RuleProgramFact("unused-overlay", "gate:gate_id", (gate, "met"), {"kind": "unused"})
    program = RuleProgram(_program().clauses, (unused,))
    report = fg.eval.evaluate_program(program, _goal(case, outcome)).explain().witness_report.to_dict()
    assert "unused-overlay" not in {item["witness_ref"] for item in report["occurrences"]}
    assert {item["kind"] for item in report["occurrences"] if item["predicate_id"] == "gate:gate_id"} == {"assertion"}


def test_native_overlay_ref_collision_fails_without_ledger_write() -> None:
    from factgraph.sdk import RuleProgramWitnessError

    fg, case, _, outcome, evidence_id = _world()
    colliding = RuleProgramFact(evidence_id, "gate:gate_id", (fg.entities.ref(Gate, gate_id="other"), "other"), {"kind": "test"})
    before = tuple(fg.ledger.claims)
    with pytest.raises(RuleProgramWitnessError) as error:
        fg.eval.evaluate_program(RuleProgram(_program().clauses, (colliding,)), _goal(case, outcome))
    assert error.value.code == "program_witness_ref_collision"
    assert tuple(fg.ledger.claims) == before


@pytest.mark.parametrize("invalid", [float("nan"), {1: "non-string key"}, object()])
def test_native_program_provenance_must_be_finite_json(invalid) -> None:
    from factgraph.sdk import RuleProgramWitnessError

    fg, program, goal, _ = _program_overlay_world()
    original = program.facts[0]
    bad = RuleProgramFact(original.fact_id, original.predicate, original.terms, {"nested": [invalid]})
    with pytest.raises(RuleProgramWitnessError) as error:
        fg.eval.evaluate_program(RuleProgram(program.clauses, (bad, *program.facts[1:])), goal)
    assert error.value.code == "invalid_capture_shape"


def _reseal_report(payload):
    for digest_key, material_key in (("support_graph_digest", "support_steps"), ("evidence_digest", "evidence")):
        payload[digest_key] = "sha256:" + hashlib.sha256(json.dumps(
            payload[material_key], sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
    payload.pop("report_digest")
    payload["report_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()).hexdigest()
    return payload


def test_native_report_partial_capture_retains_missing_child_coordinate() -> None:
    from factgraph.sdk import RuleProgramWitnessReportV1

    fg, program, goal, _ = _program_overlay_world()
    payload = fg.eval.evaluate_program(program, goal).explain().witness_report.to_dict()
    missing = next(step["support_digest"] for step in payload["support_steps"] if not step["child_support_digests"])
    payload["support_steps"] = [step for step in payload["support_steps"] if step["support_digest"] != missing]
    payload["occurrences"] = [item for item in payload["occurrences"] if item["support_digest"] != missing]
    for link in payload["source_links"]:
        if any(item["support_digest"] == missing for item in link["occurrences"]):
            link.update(status="not_captured", occurrences=[])
    payload["issues"] = [{"support_digest": missing, "reason": "support_not_captured"}]
    payload["status"] = "partial"
    decoded = RuleProgramWitnessReportV1.from_dict(_reseal_report(payload))
    assert decoded.status == "partial"
    assert decoded.to_dict()["issues"] == [{"support_digest": missing, "reason": "support_not_captured"}]


def test_manual_legacy_native_result_does_not_infer_witness_capture() -> None:
    from dataclasses import replace

    fg, case, _, outcome, _ = _world()
    current = fg.eval.evaluate_program(_program(), _goal(case, outcome))
    legacy = replace(current, _witness_report=None)
    assert legacy.explain().witness_report is None
    assert legacy.explain().narrate() == current.explain().narrate()


class TypedWitnessCase(Entity):
    case_id: str = Identity()
    text: str = Field()
    number: int = Field()
    flag: bool = Field()
    ratio: float = Field()
    blob: bytes = Field()
    decision: Outcome = Field()


@pytest.mark.parametrize("program_bytes", [False, True])
def test_native_report_uses_schema_types_not_python_equality_or_ref_prefix(program_bytes) -> None:
    fg = FactGraph.create(schema_classes=[TypedWitnessCase, Outcome])
    case = fg.entities.create(TypedWitnessCase, case_id="typed")
    outcome = fg.entities.create(Outcome, outcome_id="allow")
    for field, value in ((TypedWitnessCase.text, "idref_v1:literal-not-reference"),
                         (TypedWitnessCase.number, 1), (TypedWitnessCase.flag, True),
                         (TypedWitnessCase.ratio, 1.5), (TypedWitnessCase.blob, b"\x00\xff")):
        if field is TypedWitnessCase.blob and program_bytes:
            continue
        fg.fields.set(field, case, value)
    c, o = Var("$case"), Var("$outcome")
    foundation = (PredAtom("TypedWitnessCase:exists", [c]), PredAtom("Outcome:exists", [o]))
    body = Rule(id="typed_body", when=foundation + tuple(
        PredAtom("typed_witness_case:" + field, [c, Var("$" + field)])
        for field in ("text", "number", "flag", "ratio", "blob")
    ), ports={"case": c, "outcome": o})
    head = Rule(id="typed_witness_case:decision", when=foundation, ports={"case": c, "outcome": o})
    facts = (RuleProgramFact("binary-program-input", "typed_witness_case:blob", (case, b"\x00\xff"), {"kind": "test"}),) if program_bytes else ()
    result = fg.eval.evaluate_program(RuleProgram((RuleProgramClause("typed", body, head),), facts),
                                      RuleProgramGoal("typed_witness_case:decision", (case, outcome)))
    assert result.entailed
    items = result.explain().witness_report.to_dict()["occurrences"]
    values = {item["predicate_id"]: item["terms"][-1] for item in items}
    assert values["typed_witness_case:text"] == {"tag": "string", "value": "idref_v1:literal-not-reference"}
    assert values["typed_witness_case:number"] == {"tag": "int", "value": 1}
    assert values["typed_witness_case:flag"] == {"tag": "bool", "value": True}
    assert values["typed_witness_case:ratio"] == {"tag": "float64", "value": "0x3ff8000000000000"}
    assert values["typed_witness_case:blob"] == {"tag": "bytes", "value": "AP8"}
