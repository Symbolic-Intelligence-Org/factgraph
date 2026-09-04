from __future__ import annotations

import json
import shutil
import unittest
from dataclasses import replace

from factgraph.application.goal_plan_v2_runtime import (
    ProductEvaluationRuntimeErrorV2,
    replay_evaluation_run_v2,
)
from factgraph.application.policy_runtime import compile_policy
from factgraph.application.protocol.policy import Policy, PolicyError
from factgraph.core.evidence.write_protocol import set_field
from factgraph.sdk import AssetMeta, Entity, Field, Identity, SDKStore, outcome_from_run_v2, vars
from factgraph.sdk.errors import SDKStoreError


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _assets(graph: SDKStore, calls: list[int]):
    with vars("person", "age") as (person, age):
        rule = graph.build_rule(
            id="person_values",
            version="1",
            when=(Person(person), Person(person).age == age),
            ports={"person": person, "age": age},
            semantic_ports={"person": Person, "age": Person.age},
        )

    def decade(age: int) -> int:
        calls.append(age)
        return age // 10

    function = graph.build_function(
        id="decade",
        version="1",
        meta=AssetMeta(name="Age decade"),
        implementation=decade,
    )
    policy = graph.policy_builder("ranked_people", version="1")
    people = policy.use(rule).as_("people")
    computed = policy.use(function).as_("computed")
    computed.inputs(age=people.age)
    target = policy.build(policy.all(people, computed, computed.result >= 2))
    return rule, function, target, people, computed


class ProductFunctionV2Tests(unittest.TestCase):
    def test_direct_and_staged_function_authoring_are_identical(self) -> None:
        graph = SDKStore([Person])

        def decade(age: int) -> int:
            return age // 10

        meta = AssetMeta(name="Age decade", tags=("function",))
        direct = graph.build_function(id="decade", version="1", meta=meta, implementation=decade)
        staged = graph.function_builder("decade", version="1", meta=meta).build(decade)

        self.assertEqual(direct.signature_digest, staged.signature_digest)
        self.assertEqual(direct.logical_identity_digest, staged.logical_identity_digest)
        self.assertEqual(direct.asset_binding_digest, staged.asset_binding_digest)

    def test_native_scenario_and_detached_replay_materialize_function_once_per_world(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        calls: list[int] = []
        _rule, function, target, people, computed = _assets(graph, calls)
        profile = graph.execution.native_deterministic(target=target).build()
        scenario = (
            graph.scenario()
            .set(
                Person.age,
                alice,
                35,
                premise_id="older-alice",
                meta={"note": "operator review"},
            )
            .build()
        )

        run = (
            graph.query(target)
            .select("age", people.age)
            .select("decade", computed.result)
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        self.assertEqual(calls, [27, 35])
        self.assertEqual(
            tuple(
                value.value for _name, value in run.baseline.engine_frames[0].observations[0].values
            ),
            (27, 2),
        )
        self.assertEqual(
            tuple(
                value.value
                for _name, value in run.effective.engine_frames[0].observations[0].values
            ),
            (35, 3),
        )
        self.assertEqual(
            run.effective.function_materializations[0].function_digest,
            function.logical_identity_digest,
        )
        outcome = outcome_from_run_v2(run)
        self.assertEqual(outcome.effective.functions.definition_capture.state, "captured")
        function_view = outcome.effective.functions.occurrences[0]
        self.assertEqual(function_view.function_id, "decade")
        self.assertEqual(function_view.asset.name, "Age decade")
        self.assertEqual(function_view.calls[0].inputs[0].value, 35)
        self.assertEqual(function_view.calls[0].output.value, 3)
        explanation = outcome.explain(outcome.effective.rows[0])
        self.assertEqual(explanation.functions.materialization_capture.state, "captured")
        self.assertEqual(explanation.functions.occurrences[0].calls[0].output.value, 3)
        self.assertIn("Function materialization: captured", explanation.render_text())
        self.assertIsNone(explanation.evidence.graph)
        wire = explanation.to_dict()
        function_wire = wire["functions"]
        assert isinstance(function_wire, dict)
        materialization_capture = function_wire["materialization_capture"]
        assert isinstance(materialization_capture, dict)
        self.assertEqual(materialization_capture["state"], "captured")
        occurrences = function_wire["occurrences"]
        assert isinstance(occurrences, list)
        occurrence = occurrences[0]
        assert isinstance(occurrence, dict)
        calls_wire = occurrence["calls"]
        assert isinstance(calls_wire, list)
        call = calls_wire[0]
        assert isinstance(call, dict)
        output = call["output"]
        assert isinstance(output, dict)
        self.assertEqual(output["value"], 3)
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")
        self.assertEqual(calls, [27, 35], "detached replay must not invoke the callable")

    def test_function_is_intrinsically_v2_only_and_output_cannot_be_bound(self) -> None:
        graph = SDKStore([Person])
        calls: list[int] = []
        _rule, _function, target, _people, computed = _assets(graph, calls)

        with self.assertRaises(SDKStoreError) as bind_error:
            (
                graph.query(target)
                .bind(computed.result, 2)
                .select("result", computed.result)
                .plan(profile=graph.execution.native_deterministic(target=target).build())
            )
        self.assertEqual(bind_error.exception.code, "EVALUATION_QUERY_OUTPUT_BINDING_UNSUPPORTED")

        rewrapped = Policy(target.policy.id, target.policy.when, target.policy.version)
        with self.assertRaises(PolicyError) as compile_error:
            compile_policy(
                rewrapped,
                address_space=target.address_space,
                schema_index=graph._application_schema_index,
            )
        self.assertEqual(compile_error.exception.code, "FUNCTION_V2_ONLY")

    def test_function_cannot_consume_another_function_output(self) -> None:
        graph = SDKStore([Person])
        calls: list[int] = []
        rule, first, _target, _people, _computed = _assets(graph, calls)
        second = graph.build_function(
            id="increment",
            implementation=lambda value: value + 1,
            inputs={"value": "int"},
            output="int",
        )
        policy = graph.policy_builder("no_function_chaining")
        people = policy.use(rule).as_("people")
        first_call = policy.use(first).as_("first_call")
        first_call.inputs(age=people.age)
        second_call = policy.use(second).as_("second_call")

        with self.assertRaises(SDKStoreError) as error:
            second_call.inputs(value=first_call.result)
        self.assertEqual(error.exception.code, "PRODUCT_FUNCTION_INPUT_SOURCE_UNSUPPORTED")

    def test_function_inputs_reject_missing_domain_and_cross_draft_connections(self) -> None:
        graph = SDKStore([Person])
        calls: list[int] = []
        rule, function, _target, _people, _computed = _assets(graph, calls)

        missing_builder = graph.policy_builder("missing_input")
        missing_people = missing_builder.use(rule).as_("people")
        missing_call = missing_builder.use(function).as_("computed")
        with self.assertRaises(SDKStoreError) as missing_error:
            missing_builder.build(missing_builder.all(missing_people, missing_call))
        self.assertEqual(missing_error.exception.code, "PRODUCT_FUNCTION_INPUT_COVERAGE_MISMATCH")

        string_function = graph.build_function(
            id="string_length",
            implementation=lambda value: len(value),
            inputs={"value": "string"},
            output="int",
        )
        domain_builder = graph.policy_builder("wrong_domain")
        domain_people = domain_builder.use(rule).as_("people")
        domain_call = domain_builder.use(string_function).as_("computed")
        with self.assertRaises(SDKStoreError) as domain_error:
            domain_call.inputs(value=domain_people.age)
        self.assertEqual(domain_error.exception.code, "PRODUCT_FUNCTION_INPUT_DOMAIN_MISMATCH")

        other_builder = graph.policy_builder("other")
        other_people = other_builder.use(rule).as_("people")
        with self.assertRaises(SDKStoreError) as owner_error:
            missing_call.inputs(age=other_people.age)
        self.assertEqual(owner_error.exception.code, "POLICY_CROSS_DRAFT_HANDLE")

    def test_multiple_parallel_functions_share_one_rule_occurrence(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        calls: list[int] = []
        rule, decade, _target, _people, _computed = _assets(graph, calls)
        adult = graph.build_function(
            id="is_adult",
            implementation=lambda age: age >= 18,
            inputs={"age": "int"},
            output="bool",
        )
        policy = graph.policy_builder("parallel_functions")
        people = policy.use(rule).as_("people")
        decade_call = policy.use(decade).as_("decade")
        adult_call = policy.use(adult).as_("adult")
        decade_call.inputs(age=people.age)
        adult_call.inputs(age=people.age)
        target = policy.build(policy.all(people, decade_call, adult_call))

        run = (
            graph.query(target)
            .select("decade", decade_call.result)
            .select("adult", adult_call.result)
            .plan(profile=graph.execution.native_deterministic(target=target).build())
            .run()
        )
        values = {
            name: value.value
            for name, value in run.effective.engine_frames[0].observations[0].values
        }
        self.assertEqual(values, {"decade": 2, "adult": True})

    def test_candidate_policy_uses_its_own_function_asset_and_replays(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        with vars("person", "age") as (person, age):
            rule = graph.build_rule(
                id="person_values",
                when=(Person(person), Person(person).age == age),
                ports={"person": person, "age": age},
                semantic_ports={"person": Person, "age": Person.age},
            )

        def target_for(function_id: str, implementation: object):
            function = graph.build_function(
                id=function_id,
                implementation=implementation,
                inputs={"age": "int"},
                output="int",
            )
            builder = graph.policy_builder(f"policy_{function_id}")
            people = builder.use(rule).as_("people")
            computed = builder.use(function).as_("computed")
            computed.inputs(age=people.age)
            return builder.build(builder.all(people, computed)), people, computed

        primary, people, computed = target_for("decade", lambda age: age // 10)
        candidate, _candidate_people, _candidate_computed = target_for(
            "five_year_band", lambda age: age // 5
        )
        profile = (
            graph.execution.native_deterministic(target=primary)
            .for_target(candidate, side="candidate")
            .build()
        )
        run = (
            graph.query(primary)
            .select("age", people.age)
            .select("band", computed.result)
            .plan(profile=profile, candidate=candidate)
            .run()
        )

        self.assertEqual(run.effective.engine_frames[0].observations[0].values[1][1].value, 2)
        assert run.candidate_effective is not None
        self.assertEqual(
            run.candidate_effective.engine_frames[0].observations[0].values[1][1].value,
            5,
        )
        outcome = outcome_from_run_v2(run)
        assert outcome.candidate_effective is not None
        self.assertEqual(
            outcome.candidate_effective.functions.occurrences[0].function_id,
            "five_year_band",
        )
        self.assertEqual(outcome.replay().status, "matched")

    def test_live_function_asset_rejects_callable_swap(self) -> None:
        graph = SDKStore([Person])
        calls: list[int] = []
        _rule, function, target, _people, _computed = _assets(graph, calls)
        object.__setattr__(function, "implementation", lambda age: age + 100)

        with self.assertRaises(SDKStoreError) as error:
            graph.execution.native_deterministic(target=target).build()
        self.assertEqual(error.exception.code, "PRODUCT_FUNCTION_SIGNATURE_STALE")

    def test_function_materialization_seal_rejects_output_mutation(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        calls: list[int] = []
        _rule, _function, target, people, computed = _assets(graph, calls)
        run = (
            graph.query(target)
            .select("age", people.age)
            .select("decade", computed.result)
            .plan(profile=graph.execution.native_deterministic(target=target).build())
            .run()
        )
        materialization = run.effective.function_materializations[0]
        call = materialization.calls[0]
        altered = replace(call, output=(call.output[0], replace(call.output[1], value=9)))
        object.__setattr__(materialization, "calls", (altered,))

        with self.assertRaises(Exception):
            replay_evaluation_run_v2(run)

    def test_replay_rejects_function_definition_capture_tamper(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        calls: list[int] = []
        _rule, _function, target, people, computed = _assets(graph, calls)
        run = (
            graph.query(target)
            .select("age", people.age)
            .select("decade", computed.result)
            .plan(profile=graph.execution.native_deterministic(target=target).build())
            .run()
        )
        envelope = json.loads(run.replay_payload.compiled_program_bytes.decode("utf-8"))
        envelope["primary"]["function_capture"]["occurrences"][0]["implementation_digest"] = (
            "sha256:" + "0" * 64
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
        self.assertEqual(error.exception.code, "V2_REPLAY_PROGRAM_PIN_MISMATCH")

    def test_function_fails_closed_on_source_graph_side_effect(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])

        def mutating(age: int) -> int:
            set_field(graph.ledger, "person:age", alice, [("int", 99)])
            return age // 10

        with vars("person", "age") as (person, age):
            rule = graph.build_rule(
                id="person_values",
                when=(Person(person), Person(person).age == age),
                ports={"person": person, "age": age},
                semantic_ports={"person": Person, "age": Person.age},
            )
        function = graph.build_function(id="mutating", implementation=mutating)
        policy = graph.policy_builder("guarded")
        people = policy.use(rule).as_("people")
        computed = policy.use(function).as_("computed")
        computed.inputs(age=people.age)
        target = policy.build(policy.all(people, computed))

        with self.assertRaises(ProductEvaluationRuntimeErrorV2) as error:
            (
                graph.query(target)
                .select("result", computed.result)
                .plan(profile=graph.execution.native_deterministic(target=target).build())
                .run()
            )
        self.assertEqual(error.exception.code, "V2_VIEW_CHANGED_DURING_FUNCTION")

    def test_function_fails_closed_on_observed_nondeterminism(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        counter = 0

        def unstable(age: int) -> int:
            nonlocal counter
            counter += 1
            return age + counter

        with vars("person", "age") as (person, age):
            rule = graph.build_rule(
                id="person_values",
                when=(Person(person), Person(person).age == age),
                ports={"person": person, "age": age},
                semantic_ports={"person": Person, "age": Person.age},
            )
        function = graph.build_function(id="unstable", implementation=unstable)
        policy = graph.policy_builder("unstable_policy")
        people = policy.use(rule).as_("people")
        computed = policy.use(function).as_("computed")
        computed.inputs(age=people.age)
        target = policy.build(policy.all(people, computed))

        with self.assertRaises(ProductEvaluationRuntimeErrorV2) as error:
            (
                graph.query(target)
                .select("result", computed.result)
                .plan(profile=graph.execution.native_deterministic(target=target).build())
                .run()
            )
        self.assertEqual(error.exception.code, "V2_FUNCTION_NONDETERMINISTIC_OUTPUT")

    @unittest.skipUnless(
        shutil.which("souffle") and shutil.which("problog"),
        "requires real Souffle and ProbLog CLIs",
    )
    def test_portable_profile_runs_one_materialized_function_relation_on_all_engines(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", alice, [("int", 27)])
        calls: list[int] = []
        _rule, _function, target, people, computed = _assets(graph, calls)

        run = (
            graph.query(target)
            .select("age", people.age)
            .select("decade", computed.result)
            .plan(profile=graph.execution.portable_deterministic(target=target).build())
            .run()
        )

        self.assertEqual(calls, [27, 27])
        self.assertEqual(
            tuple((frame.engine, frame.status) for frame in run.effective.engine_frames),
            (("native", "succeeded"), ("souffle", "succeeded"), ("problog", "succeeded")),
        )
        self.assertEqual(
            {
                tuple((name, value.value) for name, value in frame.observations[0].values)
                for frame in run.effective.engine_frames
            },
            {(("age", 27), ("decade", 2))},
        )
        self.assertEqual(replay_evaluation_run_v2(run).status, "matched")
        self.assertEqual(calls, [27, 27])


if __name__ == "__main__":
    unittest.main()
