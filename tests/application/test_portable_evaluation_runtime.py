from __future__ import annotations

import shutil
import unittest
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    encode_entity_ref,
    entity_info,
    field_predicate,
    manage_rule_occurrence,
    resolve_selector,
)
from factgraph.application import portable_evaluation_runtime
from factgraph.application.portable_evaluation_runtime import (
    PORTABLE_DETERMINISTIC_V1,
    PortableEvaluationError,
    execute_portable_deterministic_v1,
    materialize_portable_effective_world_v1,
    observe_portable_deterministic_v1,
    validate_portable_deterministic_v1,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntityRef,
    EntitySelector,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    Policy,
    PolicyOccurrence,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.store._support import ProjectedFact
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


def _compiled_query_and_relation() -> tuple[
    CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]
]:
    source = SDKStore([Person])
    index = build_schema_index(source.schema_ir)
    for employee_id, age, score in (("alice", 22, 9), ("bob", 19, 7)):
        ref = resolve_selector(
            EntitySelector(entity_type="Person", identity={"employee_id": employee_id}),
            index=index,
        )
        encoded = ref.encoded_ref or ""
        info = entity_info(index, "Person")
        set_field(source.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            source.ledger,
            info.identity_predicates["employee_id"].pred_id,
            encoded,
            [("string", employee_id)],
        )
        set_field(
            source.ledger,
            field_predicate(index, "Person", "age").pred_id,
            encoded,
            [("int", age)],
        )
        set_field(
            source.ledger,
            field_predicate(index, "Person", "score").pred_id,
            encoded,
            [("int", score)],
        )

    person, age, score = Var("$person"), Var("$age"), Var("$score")
    rule = build_resolved_rule(
        id="person_values",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
            PredAtom("person:score", [person, score]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            "score": SemanticRulePort(score, field_endpoint("Person", "score")),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(rule, "pair"),))
    policy = compile_policy(
        Policy("portable-person", PolicyOccurrence("pair")),
        address_space=space,
    )
    compiled = compile_evaluation_query(
        EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("person", SemanticPortAddress("pair", "person")),
                EvaluationQuerySelection("age", SemanticPortAddress("pair", "age")),
            ),
            (
                EvaluationQueryBinding(
                    SemanticPortAddress("pair", "person"),
                    EntityRef("Person", {"employee_id": "alice"}),
                ),
            ),
        ),
        compiled_policy=policy,
        address_space=space,
        schema_index=index,
    )
    plan, _traces = _materialize_adapter_derivation_plan(
        compiled._lowering_plan,
        engine="native",
    )
    projected = project_view_facts_with_witness(source.ledger, source.schema_ir)
    dependencies = ("Person:exists", "person:age", "person:score")
    relation = {predicate_id: tuple(projected[predicate_id]) for predicate_id in dependencies}
    return plan, source.schema_ir, relation


class PortableObservationFrameContractTests(unittest.TestCase):
    """Observation framing must be testable even where external CLIs are absent."""

    def test_observation_returns_all_terminal_frames_over_one_isolated_store(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()
        observed_store_ids: list[int] = []
        problog_messages = iter(("first transient failure", "second transient failure"))

        def _available(_engine: str) -> None:
            return None

        def _evaluate(request: object, *, store: object) -> list[object]:
            engine = getattr(request, "engine")
            observed_store_ids.append(id(store))
            if engine == "souffle":
                raise PortableEvaluationError(
                    "fixture adapter absent",
                    code="PORTABLE_ENGINE_UNAVAILABLE",
                    details={"component": "fixture_adapter"},
                )
            if engine == "problog":
                raise RuntimeError(next(problog_messages))
            return []

        with (
            patch.object(
                portable_evaluation_runtime,
                "_assert_portable_engine_available_v1",
                side_effect=_available,
            ),
            patch.object(
                portable_evaluation_runtime,
                "evaluate_derivation_plans",
                side_effect=_evaluate,
            ),
        ):
            first = observe_portable_deterministic_v1(
                plan,
                schema_ir=schema_ir,
                effective_relations=relation,
            )
            second = observe_portable_deterministic_v1(
                plan,
                schema_ir=schema_ir,
                effective_relations=relation,
            )

        self.assertEqual(
            tuple(frame.engine for frame in first.frames),
            ("native", "souffle", "problog"),
        )
        self.assertEqual(
            tuple(frame.status for frame in first.frames),
            ("succeeded", "unsupported", "failed"),
        )
        self.assertEqual(len(observed_store_ids), 6)
        self.assertEqual(len(set(observed_store_ids[:3])), 1)
        self.assertEqual(len(set(observed_store_ids[3:])), 1)
        self.assertNotEqual(observed_store_ids[0], observed_store_ids[3])

        supported, unsupported, failed = first.frames
        self.assertEqual(supported.evaluation.rows, ())  # type: ignore[union-attr]
        self.assertIsNone(supported.diagnostic)
        self.assertIsNone(unsupported.evaluation)
        self.assertEqual(unsupported.diagnostic.code, "PORTABLE_ENGINE_UNAVAILABLE")  # type: ignore[union-attr]
        self.assertEqual(
            unsupported.diagnostic.details_json,  # type: ignore[union-attr]
            '{"cause_type":"PortableEvaluationError","component":"fixture_adapter","engine":"souffle"}',
        )
        self.assertIsNone(failed.evaluation)
        self.assertEqual(failed.diagnostic.code, "PORTABLE_ENGINE_EXECUTION_FAILED")  # type: ignore[union-attr]
        self.assertEqual(
            failed.diagnostic.details_json,  # type: ignore[union-attr]
            '{"cause_type":"RuntimeError","engine":"problog"}',
        )
        self.assertEqual(
            tuple(frame.frame_digest for frame in first.frames),
            tuple(frame.frame_digest for frame in second.frames),
        )
        self.assertEqual(first.observation_digest, second.observation_digest)

    def test_observation_does_not_soften_existing_portable_fail_closed_execution(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()

        def _evaluate(request: object, *, store: object) -> list[object]:
            if getattr(request, "engine") == "souffle":
                raise RuntimeError("fixture execution failure")
            return []

        with patch.object(
            portable_evaluation_runtime,
            "evaluate_derivation_plans",
            side_effect=_evaluate,
        ):
            with self.assertRaises(PortableEvaluationError) as ctx:
                execute_portable_deterministic_v1(
                    plan,
                    schema_ir=schema_ir,
                    effective_relations=relation,
                )

        self.assertEqual(ctx.exception.code, "PORTABLE_ENGINE_EXECUTION_FAILED")


@unittest.skipUnless(
    shutil.which("souffle") and shutil.which("problog"),
    "portable runtime test requires installed Souffle and ProbLog binaries",
)
class PortableEvaluationRuntimeTests(unittest.TestCase):
    def test_observation_frames_are_successful_and_stably_sealed_when_all_engines_run(
        self,
    ) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()

        first = observe_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )
        second = observe_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            tuple(frame.engine for frame in first.frames),
            ("native", "souffle", "problog"),
        )
        self.assertTrue(all(frame.status == "succeeded" for frame in first.frames))
        self.assertTrue(all(frame.evaluation is not None for frame in first.frames))
        self.assertTrue(all(frame.diagnostic is None for frame in first.frames))
        self.assertEqual(first.observation_digest, second.observation_digest)
        self.assertEqual(
            tuple(frame.frame_digest for frame in first.frames),
            tuple(frame.frame_digest for frame in second.frames),
        )

    def test_real_compiled_query_runs_all_three_engines_over_captured_relation(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()

        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(result.profile, PORTABLE_DETERMINISTIC_V1)
        self.assertEqual(result.proof_parity, "not_claimed")
        self.assertEqual(
            tuple(item.engine for item in result.executions), ("native", "souffle", "problog")
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)
        self.assertEqual(
            result.selected_row_set_digest, result.executions[0].selected_row_set_digest
        )
        self.assertEqual(
            result.executions[0].rows[0].terms[1],
            ("int", 22),
        )

    def test_materialized_world_is_new_and_does_not_need_a_source_store(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()

        materialized = materialize_portable_effective_world_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            {claim.pred_id for claim in materialized.ledger.find_claims()},
            {"Person:exists", "person:age", "person:score"},
        )
        self.assertEqual(len(materialized.ledger.find_claims()), 6)

    def test_explicit_empty_dependency_relation_is_not_a_missing_relation(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()
        empty_age_relation = dict(relation)
        empty_age_relation["person:age"] = ()

        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=empty_age_relation,
        )

        self.assertEqual(
            result.selected_row_set_digest, result.executions[0].selected_row_set_digest
        )
        self.assertTrue(all(item.rows == () for item in result.executions))

    def test_branch_total_or_of_and_runs_across_all_three_engines(self) -> None:
        _plan, schema_ir, relation = _compiled_query_and_relation()
        branch_plan = CompiledDerivationPlan(
            derivation_id="portable-total-or",
            version="1",
            body_ir=[
                [
                    ("pred", "Person:exists", ["$person"]),
                    ("pred", "person:age", ["$person", "$value"]),
                    ("eq", "$selected", "$value"),
                ],
                [
                    ("pred", "Person:exists", ["$person"]),
                    ("pred", "person:score", ["$person", "$value"]),
                    ("eq", "$selected", "$value"),
                ],
            ],
            heads=(CompiledHeadCall("portable:selection", ("$selected",)),),
        )

        result = execute_portable_deterministic_v1(
            branch_plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            [row.terms for row in result.executions[0].rows],
            [
                (("int", 7),),
                (("int", 9),),
                (("int", 19),),
                (("int", 22),),
            ],
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)

    def test_relation_inventory_is_exact_including_empty_relations(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()
        missing = dict(relation)
        missing.pop("person:score")

        with self.assertRaises(PortableEvaluationError) as ctx:
            validate_portable_deterministic_v1(
                plan,
                schema_ir=schema_ir,
                effective_relations=missing,
            )
        self.assertEqual(ctx.exception.code, "PORTABLE_RELATION_INVENTORY_MISMATCH")

    def test_unsupported_semantics_reject_before_engine_execution(self) -> None:
        schema_ir = SDKStore([Person]).schema_ir
        index = build_schema_index(schema_ir)
        person = encode_entity_ref(EntityRef("Person", {"employee_id": "alice"}), index=index)
        relation = {"Person:exists": (ProjectedFact("exists", (person,)),)}
        cases = {
            "negative": (
                [
                    ("pred", "Person:exists", ["$person"]),
                    ("not", [("pred", "Person:exists", ["$person"])]),
                ],
                "PORTABLE_NEGATION_UNSUPPORTED",
            ),
            "rule-ref": (
                [("ruleref", "other", "1", ["$person"])],
                "PORTABLE_RULE_REFERENCE_UNSUPPORTED",
            ),
            "builtin": (
                [("pred", "Person:exists", ["$person"]), ("add", "$value", 1, "$next")],
                "PORTABLE_BUILTIN_UNSUPPORTED",
            ),
        }
        for name, (body_ir, code) in cases.items():
            with self.subTest(name=name):
                plan = CompiledDerivationPlan(
                    derivation_id="portable-reject",
                    version="1",
                    body_ir=body_ir,
                    heads=(CompiledHeadCall("portable:selection", ("$person",)),),
                )
                with self.assertRaises(PortableEvaluationError) as ctx:
                    validate_portable_deterministic_v1(
                        plan,
                        schema_ir=schema_ir,
                        effective_relations=relation,
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_engine_configuration_is_rejected(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation()
        configured = CompiledDerivationPlan(
            derivation_id=plan.derivation_id,
            version=plan.version,
            body_ir=plan.body_ir,
            heads=plan.heads,
            engine_options={"timeout": 5},
        )

        with self.assertRaises(PortableEvaluationError) as ctx:
            validate_portable_deterministic_v1(
                configured,
                schema_ir=schema_ir,
                effective_relations=relation,
            )
        self.assertEqual(ctx.exception.code, "PORTABLE_ENGINE_CONFIGURATION_UNSUPPORTED")

    def test_or_branch_with_non_total_execution_variables_is_rejected(self) -> None:
        _plan, schema_ir, relation = _compiled_query_and_relation()
        branch_plan = CompiledDerivationPlan(
            derivation_id="portable-partial-or",
            version="1",
            body_ir=[
                [("pred", "Person:exists", ["$person"])],
                [("pred", "Person:exists", ["$other"])],
            ],
            heads=(CompiledHeadCall("portable:selection", ("$person",)),),
        )

        with self.assertRaises(PortableEvaluationError) as ctx:
            validate_portable_deterministic_v1(
                branch_plan,
                schema_ir=schema_ir,
                effective_relations={"Person:exists": relation["Person:exists"]},
            )
        self.assertEqual(ctx.exception.code, "PORTABLE_PARTIAL_BRANCH_VARIABLE")
