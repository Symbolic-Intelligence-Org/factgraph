from __future__ import annotations

from datetime import datetime
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
    FieldPath,
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyFieldNavigation,
    PolicyLiteral,
    PolicyOccurrence,
    PolicyUnify,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.core.store._support import ProjectedFact
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


class TimedPerson(Entity):
    employee_id: str = Identity()
    observed_at: datetime = Field()


class LiteralDomainPerson(Entity):
    employee_id: str = Identity()
    label: str = Field()
    active: bool = Field()


def _compiled_query_and_relation(
    *, literal_threshold: int | None = None
) -> tuple[CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]]:
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
    root = PolicyOccurrence("pair")
    policy = compile_policy(
        Policy(
            "portable-person",
            root
            if literal_threshold is None
            else PolicyAll(
                (
                    root,
                    PolicyCompare.gt(
                        SemanticPortAddress("pair", "age"),
                        PolicyLiteral("int", literal_threshold),
                    ),
                )
            ),
        ),
        address_space=space,
        schema_index=index if literal_threshold is not None else None,
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
    dependencies = (
        "Person:exists",
        "person:age",
        "person:employee_id",
        "person:score",
    )
    relation = {predicate_id: tuple(projected[predicate_id]) for predicate_id in dependencies}
    return plan, source.schema_ir, relation


def _compiled_time_literal_query_and_relation() -> tuple[
    CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]
]:
    """Build a real ``time``-typed literal comparison over captured facts.

    This deliberately uses the schema's ``datetime -> time`` field mapping and
    raw epoch-nanosecond evidence values.  The portable execution test below
    therefore covers the actual native/Souffle/ProbLog lowering path rather
    than merely Policy construction or codec round-tripping.
    """

    source = SDKStore([TimedPerson])
    index = build_schema_index(source.schema_ir)
    info = entity_info(index, "TimedPerson")
    observed_at_predicate = field_predicate(index, "TimedPerson", "observed_at")
    for employee_id, observed_at in (
        ("alice", 1_700_000_000_000_000_000),
        ("bob", 1_600_000_000_000_000_000),
    ):
        ref = resolve_selector(
            EntitySelector(entity_type="TimedPerson", identity={"employee_id": employee_id}),
            index=index,
        )
        encoded = ref.encoded_ref or ""
        set_field(source.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            source.ledger,
            info.identity_predicates["employee_id"].pred_id,
            encoded,
            [("string", employee_id)],
        )
        set_field(
            source.ledger,
            observed_at_predicate.pred_id,
            encoded,
            [("time", observed_at)],
        )

    person, observed_at = Var("$person"), Var("$observed_at")
    rule = build_resolved_rule(
        id="timed_person_values",
        version="1",
        when=(
            PredAtom(info.exists_predicate_id, [person]),
            PredAtom(observed_at_predicate.pred_id, [person, observed_at]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("TimedPerson")),
            "observed_at": SemanticRulePort(
                observed_at,
                field_endpoint("TimedPerson", "observed_at"),
            ),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(rule, "pair"),))
    policy = compile_policy(
        Policy(
            "portable-time-literal",
            PolicyAll(
                (
                    PolicyOccurrence("pair"),
                    PolicyCompare.gt(
                        SemanticPortAddress("pair", "observed_at"),
                        PolicyLiteral("time", 1_650_000_000_000_000_000),
                    ),
                )
            ),
        ),
        address_space=space,
        schema_index=index,
    )
    compiled = compile_evaluation_query(
        EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("person", SemanticPortAddress("pair", "person")),
                EvaluationQuerySelection(
                    "observed_at",
                    SemanticPortAddress("pair", "observed_at"),
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
    dependencies = (info.exists_predicate_id, observed_at_predicate.pred_id)
    relation = {predicate_id: tuple(projected[predicate_id]) for predicate_id in dependencies}
    return plan, source.schema_ir, relation


def _compiled_equality_literal_query_and_relation(
    domain: str,
    op: str,
) -> tuple[CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]]:
    source = SDKStore([LiteralDomainPerson])
    index = build_schema_index(source.schema_ir)
    info = entity_info(index, "LiteralDomainPerson")
    label_predicate = field_predicate(index, "LiteralDomainPerson", "label")
    active_predicate = field_predicate(index, "LiteralDomainPerson", "active")
    encoded_by_id: dict[str, str] = {}
    for employee_id, label, active in (
        ("alice", "gold", True),
        ("bob", "silver", False),
    ):
        ref = resolve_selector(
            EntitySelector(
                entity_type="LiteralDomainPerson",
                identity={"employee_id": employee_id},
            ),
            index=index,
        )
        encoded = ref.encoded_ref or ""
        encoded_by_id[employee_id] = encoded
        set_field(source.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            source.ledger,
            info.identity_predicates["employee_id"].pred_id,
            encoded,
            [("string", employee_id)],
        )
        set_field(
            source.ledger,
            label_predicate.pred_id,
            encoded,
            [("string", label)],
        )
        set_field(
            source.ledger,
            active_predicate.pred_id,
            encoded,
            [("bool", active)],
        )

    person, label, active = Var("$person"), Var("$label"), Var("$active")
    rule = build_resolved_rule(
        id="literal_domain_person_values",
        version="1",
        when=(
            PredAtom(info.exists_predicate_id, [person]),
            PredAtom(label_predicate.pred_id, [person, label]),
            PredAtom(active_predicate.pred_id, [person, active]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("LiteralDomainPerson")),
            "label": SemanticRulePort(
                label, field_endpoint("LiteralDomainPerson", "label")
            ),
            "active": SemanticRulePort(
                active, field_endpoint("LiteralDomainPerson", "active")
            ),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(rule, "person"),))
    operand_by_domain = {
        "string": (
            SemanticPortAddress("person", "label"),
            PolicyLiteral("string", "gold"),
        ),
        "bool": (
            SemanticPortAddress("person", "active"),
            PolicyLiteral("bool", True),
        ),
        "entity_ref": (
            SemanticPortAddress("person", "person"),
            PolicyLiteral("entity_ref", encoded_by_id["alice"]),
        ),
    }
    left, right = operand_by_domain[domain]
    policy = compile_policy(
        Policy(
            f"portable-{domain}-{op}-literal",
            PolicyAll(
                (
                    PolicyOccurrence("person"),
                    PolicyCompare(op, left, right),  # type: ignore[arg-type]
                )
            ),
        ),
        address_space=space,
        schema_index=index,
    )
    compiled = compile_evaluation_query(
        EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection(
                    "person", SemanticPortAddress("person", "person")
                ),
                EvaluationQuerySelection(
                    "label", SemanticPortAddress("person", "label")
                ),
                EvaluationQuerySelection(
                    "active", SemanticPortAddress("person", "active")
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
    dependencies = (
        info.exists_predicate_id,
        label_predicate.pred_id,
        active_predicate.pred_id,
    )
    relation = {
        predicate_id: tuple(projected[predicate_id]) for predicate_id in dependencies
    }
    return plan, source.schema_ir, relation


def _compiled_common_any_query_and_relation() -> tuple[
    CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]
]:
    """Compile a real Policy Any query whose public alias is common to both arms.

    Each arm has private occurrence variables.  The left/right constraints are
    deliberately local to their respective ``PolicyAll`` arm, so this fixture
    exercises the exact shape that must not invent a cross-branch value merely
    to satisfy Soufflé witness capture.
    """

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

    def _person_rule(rule_id: str, *, threshold: int | None):
        person, age, score = Var("$person"), Var("$age"), Var("$score")
        when: tuple[object, ...] = (
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        )
        if threshold is None:
            when = (*when, PredAtom("person:score", [person, score]))
        else:
            when = (*when, CmpAtom("gt", age, Const(threshold)))
        ports = {
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        }
        return build_resolved_rule(
            id=rule_id,
            version="1",
            when=when,
            ports=ports,
            schema_index=index,
        )

    common = _person_rule("portable_common", threshold=None)
    eligible_left = _person_rule("portable_eligible_left", threshold=20)
    eligible_right = _person_rule("portable_eligible_right", threshold=20)
    never_left = _person_rule("portable_never_left", threshold=100)
    never_right = _person_rule("portable_never_right", threshold=100)
    space = SemanticAddressSpace(
        (
            manage_rule_occurrence(common, "common"),
            manage_rule_occurrence(eligible_left, "eligible_left"),
            manage_rule_occurrence(eligible_right, "eligible_right"),
            manage_rule_occurrence(never_left, "never_left"),
            manage_rule_occurrence(never_right, "never_right"),
        )
    )
    common_person = SemanticPortAddress("common", "person")
    common_age = SemanticPortAddress("common", "age")
    eligible_left_person = SemanticPortAddress("eligible_left", "person")
    eligible_left_age = SemanticPortAddress("eligible_left", "age")
    eligible_right_person = SemanticPortAddress("eligible_right", "person")
    eligible_right_age = SemanticPortAddress("eligible_right", "age")
    never_left_person = SemanticPortAddress("never_left", "person")
    never_left_age = SemanticPortAddress("never_left", "age")
    never_right_person = SemanticPortAddress("never_right", "person")
    never_right_age = SemanticPortAddress("never_right", "age")
    policy = compile_policy(
        Policy(
            "portable_common_any",
            PolicyAll(
                (
                    PolicyOccurrence("common"),
                    PolicyAny(
                        (
                            PolicyAll(
                                (
                                    PolicyOccurrence("eligible_left"),
                                    PolicyOccurrence("eligible_right"),
                                    PolicyUnify(eligible_left_person, eligible_right_person),
                                    PolicyCompare.ge(eligible_left_age, eligible_right_age),
                                )
                            ),
                            PolicyAll(
                                (
                                    PolicyOccurrence("never_left"),
                                    PolicyOccurrence("never_right"),
                                    PolicyUnify(never_left_person, never_right_person),
                                    PolicyCompare.ge(never_left_age, never_right_age),
                                )
                            ),
                        )
                    ),
                )
            ),
            version="1",
        ),
        address_space=space,
        schema_index=index,
    )
    compiled = compile_evaluation_query(
        EvaluationQuery(
            policy.policy_digest,
            (EvaluationQuerySelection("age", common_age),),
            (
                EvaluationQueryBinding(
                    common_person,
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


def _compiled_cross_entity_navigation_comparison_query_and_relation() -> tuple[
    CompiledDerivationPlan, dict, dict[str, tuple[ProjectedFact, ...]]
]:
    """Compile two distinct same-predicate occurrences joined by field navigation.

    The two ``PolicyOccurrence`` values intentionally share one underlying
    Rule.  This produces repeated ``Person:exists`` / ``person:age`` /
    ``person:score`` atoms with different values in one concrete branch: the
    shape that exercises Soufflé witness capture's occurrence identity.
    """

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
    person_values = build_resolved_rule(
        id="portable_cross_entity_person_values",
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
    space = SemanticAddressSpace(
        (
            manage_rule_occurrence(person_values, "older"),
            manage_rule_occurrence(person_values, "younger"),
        )
    )
    older_person = SemanticPortAddress("older", "person")
    younger_person = SemanticPortAddress("younger", "person")
    older_age = SemanticPortAddress("older", "age")
    younger_age = SemanticPortAddress("younger", "age")
    policy = compile_policy(
        Policy(
            "portable_cross_entity_navigation",
            PolicyAll(
                (
                    PolicyOccurrence("older"),
                    PolicyOccurrence("younger"),
                    PolicyCompare.gt(
                        PolicyFieldNavigation(older_person, FieldPath("Person", "age")),
                        PolicyFieldNavigation(younger_person, FieldPath("Person", "age")),
                    ),
                )
            ),
            version="1",
        ),
        address_space=space,
        schema_index=index,
    )
    compiled = compile_evaluation_query(
        EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("older", older_person),
                EvaluationQuerySelection("younger", younger_person),
                EvaluationQuerySelection("older_age", older_age),
                EvaluationQuerySelection("younger_age", younger_age),
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

    def test_real_compiled_policy_literal_runs_all_three_engines(self) -> None:
        plan, schema_ir, relation = _compiled_query_and_relation(literal_threshold=12)

        contract = validate_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )
        self.assertEqual(contract.selected_head_var_names, ("$__projection_0", "$__projection_1"))
        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            tuple(item.engine for item in result.executions), ("native", "souffle", "problog")
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)
        self.assertEqual(len(result.executions[0].rows), 1)
        self.assertEqual(result.executions[0].rows[0].terms[1], ("int", 22))

    def test_real_compiled_policy_time_literal_runs_all_three_engines(self) -> None:
        plan, schema_ir, relation = _compiled_time_literal_query_and_relation()

        contract = validate_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )
        self.assertEqual(contract.selected_head_var_names, ("$__projection_0", "$__projection_1"))
        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            tuple(item.engine for item in result.executions), ("native", "souffle", "problog")
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)
        self.assertEqual(len(result.executions[0].rows), 1)
        self.assertEqual(
            result.executions[0].rows[0].terms[1],
            ("time", 1_700_000_000_000_000_000),
        )

    def test_string_bool_and_entity_ref_literals_run_all_three_engines(self) -> None:
        for domain in ("string", "bool", "entity_ref"):
            for op, expected_label in (("eq", "gold"), ("ne", "silver")):
                with self.subTest(domain=domain, op=op):
                    plan, schema_ir, relation = (
                        _compiled_equality_literal_query_and_relation(domain, op)
                    )
                    result = execute_portable_deterministic_v1(
                        plan,
                        schema_ir=schema_ir,
                        effective_relations=relation,
                    )
                    self.assertEqual(
                        tuple(item.engine for item in result.executions),
                        ("native", "souffle", "problog"),
                    )
                    self.assertEqual(
                        len(
                            {
                                item.selected_row_set_digest
                                for item in result.executions
                            }
                        ),
                        1,
                    )
                    expected = tuple(row.terms for row in result.executions[0].rows)
                    self.assertEqual(len(expected), 1)
                    self.assertEqual(expected[0][1], ("string", expected_label))
                    self.assertTrue(
                        all(
                            tuple(row.terms for row in execution.rows) == expected
                            for execution in result.executions
                        )
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

    def test_policy_any_keeps_private_witness_variables_local_to_each_arm(self) -> None:
        """A common Query binding/selection must not require Any-arm aliases.

        The real Query compiler has already proven the common address total.
        The portable executor must therefore run each DNF arm with only that
        arm's local witness variables, rather than requiring ``eligible`` and
        ``never`` variables to share one impossible synthetic projection head.
        """

        plan, schema_ir, relation = _compiled_common_any_query_and_relation()
        contract = validate_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )
        self.assertEqual(contract.selected_head_var_names, ("$__projection_0",))
        self.assertEqual(len(contract.execution_branch_head_var_names), 2)
        branch_heads = tuple(set(item) for item in contract.execution_branch_head_var_names)
        eligible_head = next(item for item in branch_heads if "$eligible_left__person" in item)
        never_head = next(item for item in branch_heads if "$never_left__person" in item)
        self.assertNotIn("$never_left__person", eligible_head)
        self.assertNotIn("$eligible_left__person", never_head)

        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            tuple(item.engine for item in result.executions), ("native", "souffle", "problog")
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)
        self.assertEqual(result.executions[0].rows[0].terms, (("int", 22),))

    def test_cross_entity_field_navigation_comparison_preserves_each_souffle_witness_occurrence(
        self,
    ) -> None:
        """All engines agree when one predicate occurs twice with distinct values.

        This is a real compiled Policy, not raw where IR.  Its direct
        ``PolicyFieldNavigation`` comparison requires two Person occurrences:
        collapsing Soufflé witness facts by predicate id would make the
        ``younger`` occurrence borrow the ``older`` witness and reject this
        valid row during support reconstruction.
        """

        plan, schema_ir, relation = (
            _compiled_cross_entity_navigation_comparison_query_and_relation()
        )

        result = execute_portable_deterministic_v1(
            plan,
            schema_ir=schema_ir,
            effective_relations=relation,
        )

        self.assertEqual(
            tuple(item.engine for item in result.executions), ("native", "souffle", "problog")
        )
        self.assertEqual(len({item.selected_row_set_digest for item in result.executions}), 1)
        expected = tuple(row.terms for row in result.executions[0].rows)
        self.assertEqual(len(expected), 1)
        self.assertEqual(expected[0][0][0], "entity_ref")
        self.assertEqual(expected[0][1][0], "entity_ref")
        self.assertNotEqual(expected[0][0][1], expected[0][1][1])
        self.assertEqual(expected[0][2:], (("int", 22), ("int", 19)))
        self.assertTrue(
            all(
                tuple(row.terms for row in execution.rows) == expected
                for execution in result.executions
            )
        )

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
