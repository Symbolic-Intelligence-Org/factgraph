"""Q20 product result/Explain facade coverage.

These tests intentionally build a sealed V1 run directly.  The V2 product
facade must not need a Store, an evaluator callback, or a live V0 row to make
the presentation data available.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from hashlib import sha256
import json
from types import MappingProxyType
from typing import get_args, get_origin
import unittest
from unittest.mock import patch

from factgraph.application import build_schema_index, encode_entity_ref
import factgraph.application.product_explanation_data_v2 as product_explanation_data_v2
from factgraph.application.evaluation_run_v1_runtime import (
    capture_evaluation_replay_payload_v1,
    capture_evaluation_replay_world_v1,
)
from factgraph.application.explain.evidence_tree import (
    BoundVar,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    Fact,
    Holds,
    Source,
)
from factgraph.application.product_explanation_data_v2 import (
    EvaluationExplanationDataV2,
    PolicyOperandViewV2,
    PolicyTopologyNodeViewV2,
    _policy_operand_v2,
    evidence_graph_view_v2_from_graph,
    evaluation_explanation_data_v2_from_evaluation_run_v2,
    evaluation_explanation_data_v2_from_run,
    render_evaluation_run_v2_explanation_text_v2,
    render_evaluation_explanation_text_v2,
    safe_opaque_provenance_descriptor_v2,
)
from factgraph.application.product_result_views_v2 import (
    EvaluationRunV2ExplainTarget,
    ProductViewErrorV2,
    result_view_v2_from_evaluation_run_v2,
    result_view_v2_from_run,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntityRef,
    PolicyLiteral,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationEngineResultV1,
    EvaluationExecutionProfileV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
)
from factgraph.application.protocol.goal_plan_v1 import (
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
)
from factgraph.application.protocol.provenance_v1 import ProvenanceLocatorV1, ProvenanceRefV1
from factgraph.application.protocol.evaluation_run_v2 import (
    EvaluationEngineFrameV2,
    EvaluationReplayPayloadV2,
    EvaluationReplayWorldV2,
    EvaluationRunPlanV2,
    EvaluationRunSideV2 as ProtocolEvaluationRunSideV2,
    EvaluationRunV2,
    EvaluationSelectedRowV2,
    problog_probability_materialization_v2_from_world,
)
from factgraph.application.protocol.execution_profile_v2 import (
    EvaluationCapturePolicyV2,
    EvaluationEnginePinV2,
    EvaluationExecutionProfileV2,
    EvaluationResourcePolicyV2,
    EvaluationTargetPinV2,
    ExecutionAttachmentSemanticsV2,
    ExecutionAttachmentV2,
    ProbLogPointSemanticsV2,
)
from factgraph.application.protocol.scenario_v1 import ScenarioValueV1
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.scenario_v2 import (
    EffectiveWorldFactV2,
    EffectiveWorldV2,
    FactSemanticsV2,
    ScenarioDisplayV2,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import (
    AssetMeta,
    Entity,
    Field,
    Identity,
    SDKStore,
    WeightedChoiceArmV1,
    WeightedChoiceTopologyV1,
    native_deterministic_profile_v1,
)


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


def _facade_wire_dataclass_closure() -> frozenset[type[object]]:
    """Derive the closed wire DTO set from the two public facade annotations."""

    discovered: set[type[object]] = set()

    def visit(annotation: object) -> None:
        origin = get_origin(annotation)
        if origin is not None:
            for argument in get_args(annotation):
                visit(argument)
            return
        if not isinstance(annotation, type) or not is_dataclass(annotation):
            return
        if annotation in discovered:
            return
        discovered.add(annotation)
        for field_type in product_explanation_data_v2.get_type_hints(annotation).values():
            visit(field_type)

    visit(product_explanation_data_v2.EvaluationExplanationDataV2)
    visit(product_explanation_data_v2.EvaluationRunV2ExplanationDataV2)
    return frozenset(discovered)


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _side(
    *,
    name: str,
    plan: GoalPlanV1,
    world_side: str,
    world_capture_digest: str,
    age: int | None,
) -> EvaluationRunSideV1:
    rows = () if age is None else (GoalResultRowV1((("age", GoalValueV1("int", age)),)),)
    result = GoalResultV1(plan.plan_digest, "rows", "complete", rows)
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "not_requested",
        "succeeded",
        "not_requested",
        "complete",
        "not_requested",
        "available",
        "available",
    )
    return EvaluationRunSideV1(
        name,  # type: ignore[arg-type]  # exact literal values come from fixture callers.
        plan.plan_digest,
        world_side,  # type: ignore[arg-type]
        world_capture_digest,
        result,
        (EvaluationEngineResultV1("native", result),),
        assessment,
    )


def _run(*, effective_age: int | None = 22) -> EvaluationRunV1:
    graph = SDKStore([Person])
    schema = graph.schema_ir
    index = build_schema_index(schema)
    alice = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=index)
    baseline_relation = {
        "Person:exists": (ProjectedFact("base:exists:alice", (alice,)),),
        "person:age": (ProjectedFact("base:age:alice", (alice, 35)),),
    }
    effective_relation = {
        "Person:exists": (ProjectedFact("effective:exists:alice", (alice,)),),
        "person:age": (
            (ProjectedFact("effective:age:alice", (alice, effective_age)),)
            if effective_age is not None
            else ()
        ),
    }
    compiled = CompiledDerivationPlan(
        derivation_id="product-view-age-query",
        version="1",
        body_ir=[
            ("pred", "Person:exists", ["$person"]),
            ("pred", "person:age", ["$person", "$age"]),
        ],
        heads=(CompiledHeadCall("__factgraph_projection__v1_age", ("$age",)),),
    )
    profile = EvaluationExecutionProfileV1(
        "native_deterministic_v1",
        _token("c"),
        None,
        (EvaluationEnginePinV1("native", "test-native", "test-adapter"),),
    )
    plan = GoalPlanV1(
        GoalTargetRefV1("policy", "person.age", "1", _token("a")),
        _token("b"),
        "rows",
        (GoalSelectionV1("age", "int"),),
        execution_profile_digest=profile.profile_digest,
    )
    baseline_world = capture_evaluation_replay_world_v1(
        side="baseline",
        schema_ir=schema,
        semantic_world_digest=_token("d"),
        resolution_evidence_digest=_token("e"),
        closure_target_digests=(),
        relations=baseline_relation,
    )
    effective_world = capture_evaluation_replay_world_v1(
        side="effective",
        schema_ir=schema,
        semantic_world_digest=_token("f"),
        resolution_evidence_digest=_token("0"),
        closure_target_digests=(),
        relations=effective_relation,
    )
    payload = capture_evaluation_replay_payload_v1(
        schema_ir=schema,
        address_space_digest=_token("1"),
        plan=plan,
        execution_profile=profile,
        primary_compiled_plan=compiled,
        baseline_world=baseline_world,
        effective_world=effective_world,
    )
    return EvaluationRunV1(
        plan,
        profile,
        payload,
        _side(
            name="baseline",
            plan=plan,
            world_side="baseline",
            world_capture_digest=payload.world("baseline").world_capture_digest,
            age=35,
        ),
        _side(
            name="effective",
            plan=plan,
            world_side="effective",
            world_capture_digest=payload.world("effective").world_capture_digest,
            age=effective_age,
        ),
    )


def _native_policy_run_v1_with_explain() -> EvaluationRunV1:
    graph = SDKStore([Person])
    alice = graph.entities.create(Person, employee_id="alice")
    set_field(graph.ledger, "person:age", alice, [("int", 22)])
    person, age = Var("$person"), Var("$age")
    rule = graph.build_rule(
        id="person_values",
        version="1",
        meta=AssetMeta(name="Person values"),
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={"person": person, "age": age},
        semantic_ports={"person": Person, "age": Person.age},
    )
    draft = graph.policy_builder(
        id="adult_people",
        version="1",
        meta=AssetMeta(name="Adult people"),
    )
    people = draft.use(rule, as_="people")
    target = draft.build(draft.all(people, people.age > 12))
    outcome = (
        graph.query(target)
        .bind(people.person, EntityRef("Person", {"employee_id": "alice"}))
        .select("age", people.age)
        .plan(profile=native_deterministic_profile_v1())
        .run()
    )
    return outcome.run


def _world_v2(*, side: str, synthetic: bool, probability: str = "0.7") -> EffectiveWorldV2:
    provenance = ProvenanceRefV1(
        source_ref=f"scenario:{side}",
        locator=ProvenanceLocatorV1.line_span(2, 2),
        origin_role="scenario_hypothesis",
        content_digest=_token("a"),
    )
    operation_digest = _token("b")
    fact = EffectiveWorldFactV2(
        predicate_id="person:risk_flag",
        witness_id=f"witness:{side}",
        values=(ScenarioValueV1("string", "alice"), ScenarioValueV1("bool", True)),
        origin="scenario_synthetic" if synthetic else "baseline_support",
        fact_semantics=FactSemanticsV2("probabilistic", probability),
        provenance=(provenance,),
        display=ScenarioDisplayV2(note="What-if premise", labels=("demo",)),
        premise_ids=("premise:risk",) if synthetic else (),
        scenario_operation_digests=(operation_digest,) if synthetic else (),
    )
    return EffectiveWorldV2(
        schema_digest=_token("c"),
        base_view_digest=_token("d"),
        admissibility_digest=_token("e"),
        dependency_predicate_ids=("person:risk_flag",),
        facts=(fact,),
    )


def _choice_topology_v2() -> WeightedChoiceTopologyV1:
    """Detached topology returned by the runner-owned validated extractor."""

    return WeightedChoiceTopologyV1(
        choice_id="risk_source",
        selection_key=(SemanticPortAddress("key", "person"),),
        arms=(
            WeightedChoiceArmV1("declared", "0.7", "pn:declared"),
            WeightedChoiceArmV1("inferred", "0.3", "pn:inferred"),
        ),
        skeleton_node_id="pn:risk_choice_skeleton",
    )


def _run_v2(*, probability: str = "0.7") -> EvaluationRunV2:
    target = EvaluationTargetPinV2("primary", "policy", "risk_policy", "1", _token("f"))
    choice = _choice_topology_v2()
    choice_attachment = ExecutionAttachmentV2(
        "choice",
        target,
        ExecutionAttachmentSemanticsV2("problog_choice_activation_v1"),
        structural_node_id=choice.node_id,
    )
    profile = EvaluationExecutionProfileV2(
        "problog_point_v2",
        "what-if",
        _token("0"),
        (
            EvaluationEnginePinV2("problog", "test-problog", "test-adapter"),
            EvaluationEnginePinV2("native", "test-native", "test-adapter"),
            EvaluationEnginePinV2("souffle", "test-souffle", "test-adapter"),
        ),
        ProbLogPointSemanticsV2(),
        EvaluationResourcePolicyV2(max_rows=50),
        EvaluationCapturePolicyV2(max_capture_bytes=4096),
        target_pins=(target,),
        attachments=(choice_attachment,),
    )
    asset = AssetMeta(name="Risk policy", description="What-if test", tags=("demo", "risk"))
    descriptor_bytes = json.dumps(
        asset.to_wire(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    plan = EvaluationRunPlanV2(
        target=target,
        query_digest=_token("1"),
        asset_descriptor_bytes=descriptor_bytes,
        asset_descriptor_digest=asset.descriptor_digest,
        asset_binding_digest=_token("2"),
        address_space_digest=_token("3"),
    )
    baseline_world = EvaluationReplayWorldV2(
        "baseline", _world_v2(side="baseline", synthetic=False, probability=probability)
    )
    effective_world = EvaluationReplayWorldV2(
        "effective", _world_v2(side="effective", synthetic=True, probability=probability)
    )
    payload = EvaluationReplayPayloadV2(
        schema_digest=_token("c"),
        address_space_digest=_token("3"),
        profile_bytes=profile.to_bytes(),
        compiled_program_bytes=b"{}",
        worlds=(baseline_world, effective_world),
    )
    observation = EvaluationSelectedRowV2(
        (("person", GoalValueV1("string", "alice")),), point_probability=probability
    )

    def frames(world: EvaluationReplayWorldV2) -> tuple[EvaluationEngineFrameV2, ...]:
        return (
            EvaluationEngineFrameV2(
                "problog",
                "succeeded",
                (observation,),
                probability_materialization=problog_probability_materialization_v2_from_world(
                    world.world
                ),
            ),
            EvaluationEngineFrameV2(
                "native", "unsupported", diagnostic_code="NATIVE_V2_NOT_SELECTED"
            ),
            EvaluationEngineFrameV2(
                "souffle", "unsupported", diagnostic_code="SOUFFLE_V2_NOT_SELECTED"
            ),
        )

    return EvaluationRunV2(
        primary_plan=plan,
        profile=profile,
        replay_payload=payload,
        baseline=ProtocolEvaluationRunSideV2(
            "baseline",
            plan.plan_digest,
            baseline_world.world_capture_digest,
            frames(baseline_world),
            "unsupported",
        ),
        effective=ProtocolEvaluationRunSideV2(
            "effective",
            plan.plan_digest,
            effective_world.world_capture_digest,
            frames(effective_world),
            "unsupported",
        ),
    )


class ProductViewsV2Tests(unittest.TestCase):
    def test_canonical_projection_closed_type_registry_matches_facade_annotations(self) -> None:
        derived = _facade_wire_dataclass_closure()
        self.assertEqual(len(derived), 55)
        self.assertEqual(
            product_explanation_data_v2._PRODUCT_EXPLANATION_WIRE_DATACLASS_TYPES,
            derived,
        )
        self.assertEqual(
            set(product_explanation_data_v2._PRODUCT_EXPLANATION_WIRE_DATACLASS_HINTS),
            set(derived),
        )

    def test_v1_graph_available_explain_has_canonical_json_read_projection(self) -> None:
        run = _native_policy_run_v1_with_explain()
        result = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(
            run, target=result.rows[0].to_explain_target()
        )

        self.assertEqual(data.evidence.state, "native_detached_recomputed")
        self.assertIsNotNone(data.evidence.graph)
        wire = data.to_dict()
        canonical = data.to_canonical_bytes()
        self.assertEqual(wire["$schema"], "factgraph.product_explanation")
        self.assertEqual(wire["schema_version"], 2)
        self.assertEqual(wire["source_protocol"], "evaluation_run_v1")
        self.assertEqual(
            set(wire),
            {
                "$schema",
                "schema_version",
                "source_protocol",
                "identity",
                "query_descriptor",
                "outcome",
                "execution",
                "policy",
                "scenario",
                "evidence",
                "comparison",
                "boundaries",
            },
        )
        self.assertEqual(json.loads(canonical), wire)
        self.assertEqual(data.content_digest, f"sha256:{sha256(canonical).hexdigest()}")
        evidence = wire["evidence"]
        assert isinstance(evidence, dict)
        self.assertEqual(evidence["state"], "native_detached_recomputed")
        self.assertIsInstance(evidence["graph"], dict)
        self.assertEqual(data.to_canonical_bytes(), canonical)
        digest = data.content_digest
        self.assertEqual(data.content_digest, digest)
        evidence["state"] = "tampered"
        fresh_evidence = data.to_dict()["evidence"]
        assert isinstance(fresh_evidence, dict)
        self.assertEqual(fresh_evidence["state"], "native_detached_recomputed")
        self.assertEqual(data.content_digest, digest)

        portable = replace(
            data,
            evidence=replace(data.evidence, state="portable_native_inner_not_parity"),
        )
        portable_evidence = portable.to_dict()["evidence"]
        assert isinstance(portable_evidence, dict)
        self.assertEqual(portable_evidence["state"], "portable_native_inner_not_parity")
        self.assertIsInstance(portable_evidence["graph"], dict)

    def test_policy_literal_presentation_preserves_new_equality_domains(self) -> None:
        values = (
            PolicyLiteral("string", "gold"),
            PolicyLiteral("bool", True),
            PolicyLiteral(
                "entity_ref",
                "idref_v1:Person:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ),
        )
        for literal in values:
            with self.subTest(domain=literal.scalar_domain):
                view = _policy_operand_v2(literal)
                self.assertEqual(view.kind, "literal")
                self.assertEqual(view.scalar_domain, literal.scalar_domain)
                self.assertEqual(view.value, literal.value)

    def test_explicit_row_and_summary_targets_keep_v0_live_methods_out(self) -> None:
        view = result_view_v2_from_run(_run(), side="effective")

        self.assertEqual(view.source_protocol, "evaluation_run_v1")
        self.assertEqual(view.rows[0].to_explain_target().kind, "row")
        self.assertEqual(view.summary.to_explain_target().kind, "summary")
        self.assertEqual(view.summary.negative_proof, "not_claimed")
        self.assertFalse(hasattr(view.rows[0], "close"))
        with self.assertRaises(ProductViewErrorV2) as caught:
            view.row(_token("9"))
        self.assertEqual(caught.exception.code, "PRODUCT_VIEW_V2_ROW_TARGET_INVALID")

    def test_v1_adapter_marks_new_lanes_not_captured_and_summary_has_no_proof(self) -> None:
        run = _run(effective_age=None)
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.summary.to_explain_target())

        self.assertEqual(data.source_protocol, "evaluation_run_v1")
        self.assertEqual(data.outcome.observation, "result_summary_observed")
        self.assertEqual(data.outcome.logical_conclusion, "not_claimed")
        self.assertIsNone(data.outcome.row)
        self.assertEqual(data.outcome.negative_proof, "not_claimed")
        self.assertIsNone(data.evidence.graph)
        self.assertIn(data.evidence.state, {"not_captured", "not_available"})
        self.assertEqual(data.execution.semantic_model.state, "not_captured")
        self.assertEqual(data.scenario.v2_semantic_metadata.state, "not_captured")
        self.assertEqual(view.v2_probability_observation.state, "not_captured")
        self.assertEqual(data.policy.asset_descriptor.state, "not_captured")
        self.assertIn("no negative proof", render_evaluation_explanation_text_v2(data))
        summary_wire = data.to_dict()
        summary_outcome = summary_wire["outcome"]
        summary_evidence = summary_wire["evidence"]
        assert isinstance(summary_outcome, dict)
        assert isinstance(summary_evidence, dict)
        self.assertEqual(summary_outcome["negative_proof"], "not_claimed")
        self.assertIsNone(summary_evidence["graph"])

    def test_v2_problog_result_view_keeps_row_identity_probability_and_captured_lanes(self) -> None:
        run = _run_v2()
        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            view = result_view_v2_from_evaluation_run_v2(run, side="effective")

        self.assertEqual(view.source_protocol, "evaluation_run_v2")
        self.assertEqual(view.engine, "problog")
        self.assertEqual(
            view.rows[0].row_identity_digest,
            run.effective.engine_frames[0].observations[0].row_identity_digest,
        )
        self.assertEqual(view.rows[0].point_probability, "0.7")
        self.assertEqual(view.asset.descriptor_capture.state, "captured")
        self.assertEqual(view.asset.name, "Risk policy")
        self.assertEqual(view.scenario.world_capture.state, "captured")
        self.assertEqual(view.scenario.world.facts[0].origin, "scenario_synthetic")
        self.assertEqual(
            view.scenario.world.facts[0].provenance[0].source_ref, "scenario:effective"
        )
        self.assertEqual(view.profile.semantic_model, "independent_bernoulli_v1")
        self.assertEqual(view.profile.probability_materialization_model, "problog_float64_v1")
        assert view.probability_materialization is not None
        self.assertEqual(view.probability_materialization.model, "problog_float64_v1")
        self.assertEqual(
            tuple(
                (
                    entry.declared_point_probability,
                    entry.float64_text,
                    entry.problog_text,
                    entry.action,
                )
                for entry in view.probability_materialization.entries
            ),
            (("0.7", "0.7", "0.7", "emitted"),),
        )
        self.assertEqual(view.choice.attachment_capture.state, "captured")
        self.assertEqual(view.choice.authored_topology.state, "captured")
        self.assertEqual(view.choice.structural_node_ids, (_choice_topology_v2().node_id,))
        assert view.choice.topology is not None
        self.assertEqual(view.choice.topology.choice_id, "risk_source")
        self.assertEqual(
            tuple(
                (key.occurrence_alias, key.port_name) for key in view.choice.topology.selection_key
            ),
            (("key", "person"),),
        )
        self.assertEqual(
            tuple(
                (arm.arm_id, arm.probability, arm.condition_node_id)
                for arm in view.choice.topology.arms
            ),
            (("declared", "0.7", "pn:declared"), ("inferred", "0.3", "pn:inferred")),
        )
        self.assertEqual(view.choice.topology.skeleton_node_id, "pn:risk_choice_skeleton")
        self.assertEqual(view.summary_capture.state, "not_captured")

    def test_v2_probability_materialization_keeps_declared_zero_and_omission_visible(self) -> None:
        run = _run_v2(probability="0")
        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            view = result_view_v2_from_evaluation_run_v2(run, side="effective")

        assert view.probability_materialization is not None
        self.assertEqual(
            tuple(
                (
                    entry.declared_point_probability,
                    entry.float64_text,
                    entry.problog_text,
                    entry.action,
                )
                for entry in view.probability_materialization.entries
            ),
            (("0", "0.0", None, "omitted_zero"),),
        )

    def test_v2_problog_explain_is_explicit_data_and_never_fabricates_evidence_graph(self) -> None:
        run = _run_v2()
        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            view = result_view_v2_from_evaluation_run_v2(run, side="effective")
            data = evaluation_explanation_data_v2_from_evaluation_run_v2(
                run, target=view.rows[0].to_explain_target()
            )

        self.assertEqual(data.source_protocol, "evaluation_run_v2")
        self.assertEqual(data.outcome.point_probability, "0.7")
        self.assertEqual(data.outcome.logical_conclusion, "not_claimed")
        self.assertEqual(data.evidence.state, "not_available")
        self.assertEqual(data.evidence.reason_code, "PROBLOG_V2_EVIDENCE_GRAPH_NOT_CAPTURED")
        self.assertIsNone(data.evidence.graph)
        self.assertEqual(data.scenario.world.facts[0].premise_ids, ("premise:risk",))
        self.assertEqual(data.profile.semantics_digest, run.profile.semantics.semantics_digest)
        assert data.probability_materialization is not None
        self.assertEqual(
            data.probability_materialization.materialization_digest,
            run.effective.engine_frames[0].probability_materialization.materialization_digest,
        )
        self.assertIn("no evidence graph", render_evaluation_run_v2_explanation_text_v2(data))

        wire = data.to_dict()
        canonical = data.to_canonical_bytes()
        self.assertEqual(wire["$schema"], "factgraph.product_explanation")
        self.assertEqual(wire["schema_version"], 2)
        self.assertEqual(wire["source_protocol"], "evaluation_run_v2")
        self.assertEqual(json.loads(canonical), wire)
        self.assertEqual(data.content_digest, f"sha256:{sha256(canonical).hexdigest()}")
        evidence = wire["evidence"]
        assert isinstance(evidence, dict)
        self.assertEqual(evidence["state"], "not_available")
        self.assertEqual(evidence["reason_code"], "PROBLOG_V2_EVIDENCE_GRAPH_NOT_CAPTURED")
        self.assertIsNone(evidence["graph"])
        self.assertIsInstance(wire["probability_materialization"], dict)
        self.assertIsInstance(wire["scenario"], dict)
        self.assertIsInstance(wire["choice"], dict)
        self.assertIsInstance(wire["functions"], dict)

        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            changed_run = _run_v2(probability="0.8")
            changed_view = result_view_v2_from_evaluation_run_v2(changed_run, side="effective")
            changed = evaluation_explanation_data_v2_from_evaluation_run_v2(
                changed_run, target=changed_view.rows[0].to_explain_target()
            )
        self.assertNotEqual(changed.content_digest, data.content_digest)

        spliced = replace(view.rows[0].to_explain_target(), run_digest=_token("9"))
        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            with self.assertRaises(ProductViewErrorV2) as caught:
                evaluation_explanation_data_v2_from_evaluation_run_v2(run, target=spliced)
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_TARGET_INVALID")

        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            with self.assertRaises(ProductViewErrorV2) as caught:
                evaluation_explanation_data_v2_from_evaluation_run_v2(
                    run,
                    target=EvaluationRunV2ExplainTarget(
                        run.run_digest, "effective", "problog", _token("8")
                    ),
                )
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_TARGET_INVALID")

    def test_v2_view_rejects_nested_row_mutation_under_stale_run_seal(self) -> None:
        run = _run_v2()
        observation = run.effective.engine_frames[0].observations[0]
        object.__setattr__(observation, "point_probability", "0.8")

        with self.assertRaises(ProductViewErrorV2) as caught:
            result_view_v2_from_evaluation_run_v2(run, side="effective")
        self.assertEqual(caught.exception.code, "PRODUCT_VIEW_V2_RUN_INVALID")

    def test_fresh_run_constructor_rejects_stale_nested_plan(self) -> None:
        """A new outer run cannot turn a stale plan into a fresh run seal."""

        run = _run_v2()
        object.__setattr__(run.primary_plan, "query_digest", _token("9"))

        with self.assertRaises(ProtocolShapeError):
            EvaluationRunV2(
                primary_plan=run.primary_plan,
                profile=run.profile,
                replay_payload=run.replay_payload,
                baseline=run.baseline,
                effective=run.effective,
                candidate_plan=run.candidate_plan,
                candidate_effective=run.candidate_effective,
            )

    def test_evidence_source_metadata_is_allowlisted_and_explicit_descriptor_is_opaque(
        self,
    ) -> None:
        provenance = ProvenanceRefV1(
            source_ref="doc:alpha",
            locator=ProvenanceLocatorV1.line_span(3, 4),
            origin_role="agent_extraction",
            content_digest=_token("d"),
            admission_ref="admission:1",
        )
        source = Source(
            ref="witness:1",
            field="person:age",
            value=("alice_secret", 22),
            meta={
                "source_kind": "captured_witness",
                "provenance_ref": provenance,
                "raw_text": "must-not-leak",
                "credentials": "must-not-leak",
            },
        )
        graph = EvidenceGraph(
            graph_id="graph:1",
            engine="native",
            layout_hint="tree",
            subject_binding={},
            paths=(
                EvidenceTree(
                    tree_id="branch:1",
                    status="holds",
                    rules=(
                        EvidenceRule(
                            occurrence_alias="age_rule",
                            rule_id="age_rule",
                            role="body",
                            status="holds",
                            atoms=(
                                EvidenceAtom(
                                    form=Fact("person:age", (BoundVar("age", 22),)),
                                    verdict=Holds(support=(source,)),
                                    atom_id="atom:1",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            metadata={"run_digest": _token("a"), "raw_text": "must-not-leak"},
        )

        view = evidence_graph_view_v2_from_graph(graph)
        support = view.paths[0].rules[0].atoms[0].support[0]  # type: ignore[union-attr]
        self.assertEqual(dict(support.metadata), {"source_kind": "captured_witness"})
        self.assertEqual(
            support.omitted_metadata_keys, ("credentials", "provenance_ref", "raw_text")
        )
        self.assertIsNotNone(support.opaque_provenance)
        assert support.opaque_provenance is not None
        self.assertEqual(support.opaque_provenance.source_ref, "doc:alpha")
        self.assertEqual(dict(support.opaque_provenance.locator)["kind"], "line_span")
        self.assertNotIn("raw_text", dict(view.metadata))
        self.assertIn("raw_text", view.omitted_metadata_keys)
        self.assertNotIn("must-not-leak", repr(support))

    def test_generic_source_meta_is_not_implicitly_promoted_to_provenance(self) -> None:
        self.assertIsNone(
            safe_opaque_provenance_descriptor_v2(
                {"source": "document", "locator": {"kind": "opaque", "opaque_ref": "line:3"}}
            )
        )

    def test_canonical_projection_rejects_an_injected_foreign_dataclass(self) -> None:
        @dataclass(frozen=True)
        class ForeignPayload:
            secret: str

        run = _run_v2()
        with patch(
            "factgraph.application.goal_plan_v2_runtime.choice_capture_from_evaluation_run_v2",
            return_value=_choice_topology_v2(),
        ):
            view = result_view_v2_from_evaluation_run_v2(run, side="effective")
            data = evaluation_explanation_data_v2_from_evaluation_run_v2(
                run, target=view.rows[0].to_explain_target()
            )
        hostile = replace(data, query_descriptor=ForeignPayload("must-not-serialize"))  # type: ignore[arg-type]

        with self.assertRaises(ProductViewErrorV2) as caught:
            hostile.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")

        hostile_mapping = replace(
            data,
            query_descriptor={"secret": "must-not-serialize"},  # type: ignore[arg-type]
        )
        with self.assertRaises(ProductViewErrorV2) as caught:
            hostile_mapping.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")

    def test_canonical_projection_rejects_module_spoofed_dataclass_without_hint_evaluation(
        self,
    ) -> None:
        @dataclass(frozen=True)
        class ForgedPayload:
            secret: str

        ForgedPayload.__module__ = "factgraph.application.product_explanation_data_v2"
        ForgedPayload.__annotations__["secret"] = "_product_explanation_test_probe()"
        probe_calls: list[str] = []

        def probe() -> type[str]:
            probe_calls.append("called")
            return str

        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())
        hostile = replace(
            data,
            policy=replace(
                data.policy,
                topology=(
                    PolicyTopologyNodeViewV2(
                        node_id="injected-literal",
                        kind="literal",
                        child_node_ids=(),
                        left=PolicyOperandViewV2(
                            kind="literal", value=ForgedPayload("must-not-serialize")
                        ),
                    ),
                ),
            ),
        )

        with patch(
            "factgraph.application.product_explanation_data_v2._product_explanation_test_probe",
            probe,
            create=True,
        ):
            with self.assertRaises(ProductViewErrorV2) as caught:
                hostile.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")
        self.assertEqual(probe_calls, [])

    def test_canonical_projection_rejects_hostile_or_unbounded_dynamic_values(self) -> None:
        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())

        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)
        cyclic_mapping: dict[str, object] = {}
        cyclic_mapping["self"] = cyclic_mapping
        deep_value: object = "leaf"
        for _ in range(13):
            deep_value = [deep_value]
        oversize_value = list(range(129))

        class ListSubclass(list[object]):
            pass

        for label, value in (
            ("cyclic-list", cyclic_list),
            ("cyclic-mapping", cyclic_mapping),
            ("too-deep", deep_value),
            ("too-many-items", oversize_value),
            ("list-subclass", ListSubclass([1])),
        ):
            with self.subTest(label=label):
                hostile = replace(
                    data,
                    policy=replace(
                        data.policy,
                        topology=(
                            PolicyTopologyNodeViewV2(
                                node_id=f"injected-{label}",
                                kind="literal",
                                child_node_ids=(),
                                left=PolicyOperandViewV2(kind="literal", value=value),
                            ),
                        ),
                    ),
                )
                with self.assertRaises(ProductViewErrorV2) as caught:
                    hostile.to_dict()
                self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")

    def test_canonical_projection_snapshots_legitimate_mapping_proxies_and_rejects_hostile_ones(
        self,
    ) -> None:
        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())

        def with_dynamic_value(value: object):
            return replace(
                data,
                policy=replace(
                    data.policy,
                    topology=(
                        PolicyTopologyNodeViewV2(
                            node_id="injected-mapping-value",
                            kind="literal",
                            child_node_ids=(),
                            left=PolicyOperandViewV2(kind="literal", value=value),
                        ),
                    ),
                ),
            )

        normal = with_dynamic_value(MappingProxyType({"safe": [1, "two"]}))
        normal_wire = normal.to_dict()
        normal_policy = normal_wire["policy"]
        assert isinstance(normal_policy, dict)
        normal_topology = normal_policy["topology"]
        assert isinstance(normal_topology, list)
        normal_left = normal_topology[0]["left"]
        assert isinstance(normal_left, dict)
        self.assertEqual(normal_left["value"], {"safe": [1, "two"]})

        class HostileDict(dict[str, object]):
            def __iter__(self):
                raise RuntimeError("hostile mapping must not leak its exception")

        proxy = MappingProxyType(HostileDict({"secret": "must-not-serialize"}))
        declared_data = evaluation_explanation_data_v2_from_run(
            run, target=view.rows[0].to_explain_target()
        )
        for label, hostile in (
            ("dynamic", with_dynamic_value(proxy)),
            ("declared", declared_data),
        ):
            with self.subTest(label=label):
                if label == "declared":
                    assert hostile.evidence.graph is not None
                    object.__setattr__(hostile.evidence.graph, "metadata", proxy)
                for operation, invoke in (
                    ("dict", lambda: hostile.to_dict()),
                    ("bytes", lambda: hostile.to_canonical_bytes()),
                    ("digest", lambda: hostile.content_digest),
                ):
                    with self.subTest(operation=operation):
                        with self.assertRaises(ProductViewErrorV2) as caught:
                            invoke()
                        self.assertEqual(
                            caught.exception.code,
                            "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID",
                        )

        class CountMapping(Mapping[str, object]):
            def __init__(self) -> None:
                self.iteration_count = 0
                self.lookup_count = 0

            def __iter__(self):
                for index in range(1_000):
                    self.iteration_count += 1
                    yield f"key_{index}"

            def __len__(self) -> int:
                return 1_000

            def __getitem__(self, key: str) -> object:
                self.lookup_count += 1
                return key

        for label in ("dynamic", "declared"):
            with self.subTest(label=f"bounded-{label}"):
                source = CountMapping()
                bounded_proxy = MappingProxyType(source)
                if label == "dynamic":
                    bounded = with_dynamic_value(bounded_proxy)
                else:
                    bounded = evaluation_explanation_data_v2_from_run(
                        run, target=view.rows[0].to_explain_target()
                    )
                    assert bounded.evidence.graph is not None
                    object.__setattr__(bounded.evidence.graph, "metadata", bounded_proxy)
                with self.assertRaises(ProductViewErrorV2) as caught:
                    bounded.to_dict()
                self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")
                self.assertLessEqual(source.iteration_count, 129)
                self.assertLessEqual(source.lookup_count, 128)

    def test_canonical_projection_rejects_rich_type_hashes_without_executing_them(self) -> None:
        probe_calls: list[str] = []

        class ProbeMeta(type):
            def __hash__(cls) -> int:
                probe_calls.append("hash")
                return 1

        class ProbeValue(metaclass=ProbeMeta):
            pass

        class HostileFacade(EvaluationExplanationDataV2, metaclass=ProbeMeta):
            pass

        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())
        hostile_value = replace(
            data,
            policy=replace(
                data.policy,
                topology=(
                    PolicyTopologyNodeViewV2(
                        node_id="injected-hash-probe",
                        kind="literal",
                        child_node_ids=(),
                        left=PolicyOperandViewV2(kind="literal", value=ProbeValue()),
                    ),
                ),
            ),
        )

        probe_calls.clear()
        with self.assertRaises(ProductViewErrorV2) as caught:
            hostile_value.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")
        self.assertEqual(probe_calls, [])

        hostile_facade = HostileFacade(*(getattr(data, item.name) for item in fields(data)))
        probe_calls.clear()
        with self.assertRaises(ProductViewErrorV2) as caught:
            hostile_facade.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")
        self.assertEqual(probe_calls, [])

    def test_canonical_projection_rejects_non_utf8_dynamic_strings_across_public_operations(
        self,
    ) -> None:
        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())
        hostile = replace(
            data,
            policy=replace(
                data.policy,
                topology=(
                    PolicyTopologyNodeViewV2(
                        node_id="injected-non-utf8",
                        kind="literal",
                        child_node_ids=(),
                        left=PolicyOperandViewV2(kind="literal", value="\ud800"),
                    ),
                ),
            ),
        )

        for operation, invoke in (
            ("dict", lambda: hostile.to_dict()),
            ("bytes", lambda: hostile.to_canonical_bytes()),
            ("digest", lambda: hostile.content_digest),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ProductViewErrorV2) as caught:
                    invoke()
                self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")

    def test_canonical_projection_rejects_literal_with_hostile_equality(self) -> None:
        class EqualityProbe:
            def __eq__(self, other: object) -> bool:
                raise AssertionError("literal comparison must not call value.__eq__")

        run = _native_policy_run_v1_with_explain()
        view = result_view_v2_from_run(run, side="effective")
        data = evaluation_explanation_data_v2_from_run(run, target=view.rows[0].to_explain_target())
        hostile = replace(
            data,
            outcome=replace(
                data.outcome,
                logical_conclusion=EqualityProbe(),  # type: ignore[arg-type]
            ),
        )

        with self.assertRaises(ProductViewErrorV2) as caught:
            hostile.to_dict()
        self.assertEqual(caught.exception.code, "PRODUCT_EXPLAIN_V2_SERIALIZATION_INVALID")
