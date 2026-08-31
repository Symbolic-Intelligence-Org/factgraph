"""Public SDK end-to-end coverage for the sealed Q20 V2 runner."""

from __future__ import annotations

import json
import shutil
import unittest
from dataclasses import replace

from factgraph.application.goal_plan_v2_runtime import (
    ProductEvaluationRuntimeErrorV2,
    _decode_structural,
    _encode_structural,
    replay_evaluation_run_v2,
)
from factgraph.application.product_result_views_v2 import result_view_v2_from_evaluation_run_v2
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v2 import (
    EvaluationReplayPayloadV2,
    EvaluationReplayWorldV2,
)
from factgraph.application.protocol.execution_profile_v2 import EvaluationTargetPinV2
from factgraph.application.protocol.rule import PortType
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import Origin, PredAtom, Var
from factgraph.sdk import AssetMeta, Entity, Field, Identity, SDKStore


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _rule(graph: SDKStore, *, id: str = "person_values"):
    person, age = Var("$person"), Var("$age")
    return graph.build_rule(
        id=id,
        version="1",
        meta=AssetMeta(name="Person values"),
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={"person": person, "age": age},
        semantic_ports={
            "person": entity_identity("Person"),
            "age": field_endpoint("Person", "age"),
        },
    )


def _graph_and_rule() -> tuple[SDKStore, object, str]:
    graph = SDKStore([Person])
    alice = graph.entities.create(Person, person_id="alice")
    set_field(graph.ledger, "person:age", alice, [("int", 20)])
    return graph, _rule(graph), alice


class GoalPlanV2RuntimeTests(unittest.TestCase):
    def test_replay_structural_codec_preserves_typed_rule_material(self) -> None:
        value = {
            "entity": Var("$entity", Origin("authoring", "query.nodes.case")),
            "result": PortType("entity_ref", "Span"),
        }

        self.assertEqual(_decode_structural(_encode_structural(value)), value)

    def test_replay_structural_codec_rejects_unknown_typed_material(self) -> None:
        malformed = (
            {
                "$type": "FactGraphStructuralValueV1",
                "kind": "var",
                "name": "$entity",
                "origin": {"source": "provider", "path": None},
            },
            {
                "$type": "FactGraphStructuralValueV1",
                "kind": "port_type",
                "port_kind": "collection",
                "entity_type": "Person",
            },
        )

        for value in malformed:
            with self.subTest(value=value), self.assertRaises(
                ProductEvaluationRuntimeErrorV2
            ) as raised:
                _decode_structural(value)
            self.assertEqual(raised.exception.code, "V2_REPLAY_PROGRAM_SHAPE_INVALID")

    def test_public_native_scenario_set_is_isolated_and_replays(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = graph.execution.native_deterministic(target=rule).build()
        scenario = graph.scenario().set(Person.age, alice, 34, premise_id="adjusted-age").build()

        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        baseline = run.baseline.engine_frames[0].observations
        effective = run.effective.engine_frames[0].observations
        self.assertEqual([row.values[0][1].value for row in baseline], [20])
        self.assertEqual([row.values[0][1].value for row in effective], [34])
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    def test_native_profile_can_explicitly_pin_and_run_a_candidate_target(self) -> None:
        graph, rule, _alice = _graph_and_rule()
        profile = (
            graph.execution.native_deterministic(target=rule)
            .for_target(rule, side="candidate")
            .build()
        )

        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, candidate=rule)
            .run()
        )

        self.assertEqual({pin.side for pin in profile.target_pins}, {"primary", "candidate"})
        self.assertIsNotNone(run.candidate_plan)
        self.assertIsNotNone(run.candidate_effective)
        assert run.candidate_effective is not None
        self.assertEqual(
            [
                row.values[0][1].value
                for row in run.candidate_effective.engine_frames[0].observations
            ],
            [20],
        )
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    def test_candidate_with_independent_address_space_replays(self) -> None:
        """Candidate replay pins each compiled target's own address space."""

        graph, primary, _alice = _graph_and_rule()
        candidate = _rule(graph, id="person_values_candidate")
        profile = (
            graph.execution.native_deterministic(target=primary)
            .for_target(candidate, side="candidate")
            .build()
        )

        run = (
            graph.query(primary)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, candidate=candidate)
            .run()
        )

        assert run.candidate_plan is not None
        self.assertNotEqual(
            run.primary_plan.address_space_digest,
            run.candidate_plan.address_space_digest,
        )
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    def test_replay_rejects_compiled_body_swap_before_engine_execution(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = graph.execution.native_deterministic(target=rule).build()
        scenario = graph.scenario().set(Person.age, alice, 34, premise_id="adjusted-age").build()
        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )
        envelope = json.loads(run.replay_payload.compiled_program_bytes.decode("utf-8"))
        self.assertTrue(
            _replace_scalar(
                envelope["primary"]["compiled"]["body_ir"], "person:age", "person:age_tampered"
            )
        )
        payload = replace(
            run.replay_payload,
            compiled_program_bytes=json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8"),
        )
        tampered = replace(run, replay_payload=payload)

        with self.assertRaises(ProductEvaluationRuntimeErrorV2) as error:
            replay_evaluation_run_v2(tampered)
        self.assertEqual(error.exception.code, "V2_PROGRAM_LOWERING_MISMATCH")

    @unittest.skipUnless(shutil.which("problog"), "requires the real ProbLog CLI")
    def test_public_problog_scenario_point_has_typed_unsupported_frames(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = (
            graph.execution.problog(target=rule)
            .fact_semantics()
            .for_rule(rule, graph.problog.rule_semantics())
            .build()
        )
        scenario = (
            graph.scenario()
            .set(
                Person.age,
                alice,
                34,
                premise_id="probabilistic-age",
                meta={"raw_kind": "probabilistic", "bound": [0.8, 0.8]},
            )
            .build()
        )

        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        frames = run.effective.engine_frames
        self.assertEqual(
            tuple((frame.engine, frame.status) for frame in frames),
            (("problog", "succeeded"), ("native", "unsupported"), ("souffle", "unsupported")),
        )
        self.assertEqual(frames[0].observations[0].point_probability, "0.8")
        materialization = frames[0].probability_materialization
        self.assertIsNotNone(materialization)
        assert materialization is not None
        self.assertEqual(materialization.model, "problog_float64_v1")
        self.assertEqual(materialization.entries[0].declared_point_probability, "0.8")
        self.assertEqual(materialization.entries[0].float64_text, "0.8")
        self.assertEqual(materialization.entries[0].problog_text, "0.8")
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    @unittest.skipUnless(shutil.which("problog"), "requires the real ProbLog CLI")
    def test_problog_decimal_materialization_is_explicit_not_silently_exact(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = (
            graph.execution.problog(target=rule)
            .fact_semantics()
            .for_rule(rule, graph.problog.rule_semantics())
            .build()
        )
        declared = "0.123456789012345678"
        scenario = (
            graph.scenario()
            .set(
                Person.age,
                alice,
                34,
                premise_id="high-precision-probability",
                meta={"raw_kind": "probabilistic", "bound": [declared, declared]},
            )
            .build()
        )

        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        frame = run.effective.engine_frames[0]
        materialization = frame.probability_materialization
        self.assertIsNotNone(materialization)
        assert materialization is not None
        entry = materialization.entries[0]
        self.assertEqual(entry.declared_point_probability, declared)
        # This is the exact shortest decimal spelling of the float64 that the
        # current ProbLog adapter receives, not a claim that ProbLog computes
        # arbitrary-precision Decimal probabilities.
        self.assertEqual(entry.float64_text, "0.12345678901234568")
        self.assertEqual(entry.problog_text, "0.12345678901234568")
        self.assertEqual(entry.action, "emitted")
        self.assertNotEqual(frame.observations[0].point_probability, declared)
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    @unittest.skipUnless(shutil.which("problog"), "requires the real ProbLog CLI")
    def test_problog_zero_probability_is_explicitly_omitted_and_replays(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = (
            graph.execution.problog(target=rule)
            .fact_semantics()
            .for_rule(rule, graph.problog.rule_semantics())
            .build()
        )
        scenario = (
            graph.scenario()
            .set(
                Person.age,
                alice,
                34,
                premise_id="zero-probability",
                meta={"raw_kind": "probabilistic", "bound": [0, 0]},
            )
            .build()
        )

        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        frame = run.effective.engine_frames[0]
        self.assertEqual(frame.observations, ())
        materialization = frame.probability_materialization
        self.assertIsNotNone(materialization)
        assert materialization is not None
        self.assertEqual(materialization.entries[0].declared_point_probability, "0")
        self.assertEqual(materialization.entries[0].action, "omitted_zero")
        self.assertIsNone(materialization.entries[0].problog_text)
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    @unittest.skipUnless(shutil.which("problog"), "requires the real ProbLog CLI")
    def test_weighted_choice_uses_one_annotated_disjunction_and_replays(self) -> None:
        graph, rule, _alice = _graph_and_rule()
        builder = graph.policy_builder("chosen_people", version="1", meta=AssetMeta(name="Chosen"))
        key = builder.use(rule, as_="key")
        left = builder.use(rule, as_="left")
        right = builder.use(rule, as_="right")
        choice = builder.weighted_choice(
            id="source",
            on=(key.person,),
            choices=(
                builder.choice("left", probability="0.7", when=builder.all(left)),
                builder.choice("right", probability="0.3", when=builder.all(right)),
            ),
        )
        policy = builder.build(builder.all(key, choice))
        profile = (
            graph.execution.problog(target=policy)
            .fact_semantics()
            .for_choice(choice, graph.problog.choice_semantics())
            .build()
        )

        run = graph.query(policy).select("age", key.age).plan(profile=profile).run()

        observation = run.effective.engine_frames[0].observations[0]
        self.assertEqual(observation.values[0][1].value, 20)
        # Both overlapping branches hold.  A categorical AD yields 0.7 + 0.3,
        # not the independent-branch result 0.79.
        self.assertEqual(observation.point_probability, "1")
        view = result_view_v2_from_evaluation_run_v2(run, side="effective")
        self.assertEqual(view.choice.authored_topology.state, "captured")
        assert view.choice.topology is not None
        self.assertEqual(view.choice.topology.choice_id, "source")
        self.assertEqual(
            tuple(
                (key.occurrence_alias, key.port_name) for key in view.choice.topology.selection_key
            ),
            (("key", "person"),),
        )
        self.assertEqual(
            tuple((arm.arm_id, arm.probability) for arm in view.choice.topology.arms),
            (("left", "0.7"), ("right", "0.3")),
        )
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")

    def test_replay_payload_rejects_world_capture_splice(self) -> None:
        graph, rule, alice = _graph_and_rule()
        profile = graph.execution.native_deterministic(target=rule).build()
        scenario = graph.scenario().set(Person.age, alice, 34, premise_id="adjusted-age").build()
        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile, scenario=scenario)
            .run()
        )
        baseline = run.replay_payload.world("baseline")
        effective = run.replay_payload.world("effective")
        spliced_world = replace(
            effective.world,
            base_view_digest="sha256:" + "f" * 64,
        )
        with self.assertRaises(ProtocolShapeError):
            EvaluationReplayPayloadV2(
                schema_digest=run.replay_payload.schema_digest,
                address_space_digest=run.replay_payload.address_space_digest,
                profile_bytes=run.replay_payload.profile_bytes,
                compiled_program_bytes=run.replay_payload.compiled_program_bytes,
                worlds=(
                    baseline,
                    EvaluationReplayWorldV2("effective", spliced_world),
                ),
            )

    def test_run_protocol_rejects_primary_candidate_side_splice(self) -> None:
        graph, rule, _alice = _graph_and_rule()
        profile = graph.execution.native_deterministic(target=rule).build()
        run = (
            graph.query(rule)
            .select("age", SemanticPortAddress("target", "age"))
            .plan(profile=profile)
            .run()
        )
        invalid_target = EvaluationTargetPinV2(
            side="candidate",
            target_kind=run.primary_plan.target.target_kind,
            target_id=run.primary_plan.target.target_id,
            target_version=run.primary_plan.target.target_version,
            target_digest=run.primary_plan.target.target_digest,
        )
        with self.assertRaises(ProtocolShapeError):
            replace(
                run,
                primary_plan=replace(run.primary_plan, target=invalid_target),
            )


if __name__ == "__main__":
    unittest.main()


def _replace_scalar(value: object, before: str, after: str) -> bool:
    if isinstance(value, dict):
        if value.get("kind") == "scalar" and value.get("value") == before:
            value["value"] = after
            return True
        return any(_replace_scalar(item, before, after) for item in value.values())
    if isinstance(value, list):
        return any(_replace_scalar(item, before, after) for item in value)
    return False
