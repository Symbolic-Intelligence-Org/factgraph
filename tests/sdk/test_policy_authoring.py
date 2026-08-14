from __future__ import annotations

import unittest

from factgraph.application import build_resolved_rule, build_schema_index
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    PolicyLiteral,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.schema_runtime import (
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import (
    Entity,
    ExplainTargetV1,
    Field,
    Identity,
    SDKStore,
    portable_deterministic_profile_v1,
)
from factgraph.sdk.errors import SDKStoreError


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


def _bundle(graph: SDKStore):
    index = build_schema_index(graph.schema_ir)
    person, age, score = Var("$person"), Var("$age"), Var("$score")
    return build_resolved_rule(
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


def _identity_bundle(graph: SDKStore):
    index = build_schema_index(graph.schema_ir)
    person = Var("$person")
    return build_resolved_rule(
        id="person_identity",
        version="1",
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": SemanticRulePort(person, entity_identity("Person"))},
        schema_index=index,
    )


def _seed(graph: SDKStore, employee_id: str, *, age: int, score: int) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"employee_id": employee_id}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        graph.ledger,
        info.identity_predicates["employee_id"].pred_id,
        encoded,
        [("string", employee_id)],
    )
    set_field(
        graph.ledger, field_predicate(index, "Person", "age").pred_id, encoded, [("int", age)]
    )
    set_field(
        graph.ledger, field_predicate(index, "Person", "score").pred_id, encoded, [("int", score)]
    )
    return encoded


class PolicyAuthoringTests(unittest.TestCase):
    def test_literal_compare_handles_lower_to_existing_query_path(self) -> None:
        graph = SDKStore([Person])
        alice = _seed(graph, "alice", age=22, score=7)
        draft = graph.policy("adult", version="1")
        people = draft.use(_bundle(graph), as_="people")
        target = draft.build(draft.all(people, people.age > 12))

        compiled = (
            graph.query(target)
            .bind(people.person, EntityRef("Person", {"employee_id": "alice"}))
            .select("age", people.age)
            .compile()
        )

        result = graph.eval.evaluate(compiled)
        self.assertEqual(result[0].bindings["age"]["value"], 22)
        self.assertEqual(compiled.target.compiled_policy.policy_id, "adult")
        self.assertEqual(compiled.target.compiled_policy.policy_version, "1")
        self.assertTrue(alice.startswith("idref_v1:Person:"))

    def test_explicit_literal_domain_mismatch_rejects_during_authoring(self) -> None:
        graph = SDKStore([Person])
        draft = graph.policy("literal_domain")
        people = draft.use(_bundle(graph), as_="people")
        with self.assertRaisesRegex(SDKStoreError, "domain must match"):
            _ = people.age > PolicyLiteral("time", 12)

    def test_dot_navigation_and_nested_all_any_preserve_authored_structure(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=30, score=7)
        _seed(graph, "bob", age=20, score=4)
        bundle = _bundle(graph)
        draft = graph.policy("ranked", version="1")
        older = draft.use(bundle, as_="older")
        younger = draft.use(bundle, as_="younger")
        left_gate = draft.use(bundle, as_="left_gate")
        right_gate = draft.use(bundle, as_="right_gate")
        target = draft.build(
            draft.all(
                older,
                younger,
                older.age > 12,
                older.person.age > younger.person.age,
                draft.any(draft.all(left_gate), draft.all(right_gate)),
            )
        )

        compiled = (
            graph.query(target)
            .bind(older.person, EntityRef("Person", {"employee_id": "alice"}))
            .select("age", older.age)
            .compile()
        )
        result = graph.eval.evaluate(compiled)
        self.assertEqual(result[0].bindings["age"]["value"], 30)
        structure = compiled.target.compiled_policy.policy_structure
        self.assertEqual(
            {node.kind for node in structure.nodes},
            {"occurrence", "all", "any", "compare"},
        )

    def test_authored_literal_policy_reaches_all_three_engines_and_detached_explain(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=7)
        draft = graph.policy("portable_adult", version="1")
        people = draft.use(_bundle(graph), as_="people")
        target = draft.build(draft.all(people, people.age > 12))

        outcome = (
            graph.query(target)
            .bind(people.person, EntityRef("Person", {"employee_id": "alice"}))
            .select("age", people.age)
            .plan(profile=portable_deterministic_profile_v1())
            .run()
        )
        self.assertEqual(
            tuple(frame.engine for frame in outcome.run.effective.engine_results),
            ("native", "souffle", "problog"),
        )
        self.assertEqual(outcome.run.effective.assessment.parity, "equivalent")
        row = outcome.run.effective.canonical_result.rows[0]
        assert row.anchor is not None
        explanation = outcome.explain(ExplainTargetV1("effective", "row", row.anchor.anchor_digest))
        self.assertEqual(explanation.engine_evidence, "native_detached_recomputed")
        self.assertEqual(explanation.proof_parity, "not_claimed")
        self.assertIsNotNone(explanation.policy_projection)
        self.assertEqual(outcome.replay().status, "matched")

    def test_query_select_accepts_entity_field_handle_as_query_navigation(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=7)
        draft = graph.policy("identity", version="1")
        people = draft.use(_identity_bundle(graph), as_="people")
        target = draft.build(draft.all(people))
        result = graph.eval.evaluate(
            graph.query(target)
            .bind(people.person, EntityRef("Person", {"employee_id": "alice"}))
            .select("age", people.person.field("age"))
            .compile()
        )
        self.assertEqual(result[0].bindings["age"]["value"], 22)

    def test_symbolic_boolean_and_chained_comparison_fail_loudly(self) -> None:
        graph = SDKStore([Person])
        draft = graph.policy("traps")
        people = draft.use(_bundle(graph), as_="people")

        with self.assertRaisesRegex(SDKStoreError, "truth value"):
            bool(people.age > 12)
        with self.assertRaisesRegex(SDKStoreError, "truth value"):
            _ = (people.age > 12) and (people.age < 65)
        with self.assertRaisesRegex(SDKStoreError, "truth value"):
            _ = 12 < people.age < 65
        with self.assertRaisesRegex(TypeError, "hash keys"):
            hash(people.age)

        valid = draft.all(people, people.age >= 12, people.age < 65)
        self.assertIsNotNone(valid)

    def test_identity_unification_is_explicit(self) -> None:
        graph = SDKStore([Person])
        bundle = _bundle(graph)
        draft = graph.policy("same_person")
        left = draft.use(bundle, as_="left")
        right = draft.use(bundle, as_="right")

        with self.assertRaisesRegex(SDKStoreError, "draft.same"):
            _ = left.person == right.person
        target = draft.build(draft.all(left, right, draft.same(left.person, right.person)))
        self.assertEqual(target.policy.id, "same_person")

    def test_cross_draft_unknown_or_unused_handles_reject_early(self) -> None:
        graph = SDKStore([Person])
        first = graph.policy("first")
        first_people = first.use(_bundle(graph), as_="people")
        second = graph.policy("second")
        second_people = second.use(_bundle(graph), as_="people")

        with self.assertRaisesRegex(SDKStoreError, "this Policy draft"):
            second.all(first_people, second_people)
        with self.assertRaisesRegex(SDKStoreError, "has no semantic port"):
            first_people.port("missing")
        unused = graph.policy("unused")
        a = unused.use(_bundle(graph), as_="a")
        unused.use(_bundle(graph), as_="b")
        with self.assertRaisesRegex(SDKStoreError, "contain every declared occurrence"):
            unused.build(unused.all(a))

    def test_query_rejects_handles_from_a_different_authored_target(self) -> None:
        graph = SDKStore([Person])
        first = graph.policy("first")
        first_people = first.use(_bundle(graph), as_="people")
        first_target = first.build(first.all(first_people))
        second = graph.policy("second")
        second_people = second.use(_bundle(graph), as_="people")
        second_target = second.build(second.all(second_people))

        with self.assertRaisesRegex(SDKStoreError, "different Policy draft"):
            graph.query(first_target).bind(
                second_people.person,
                EntityRef("Person", {"employee_id": "alice"}),
            )
        with self.assertRaisesRegex(SDKStoreError, "different Policy draft"):
            graph.query(first_target).select("age", second_people.age)

        # The handles from the target being queried remain accepted.
        self.assertIsNotNone(graph.query(first_target).select("age", first_people.age))
        self.assertIsNotNone(graph.query(second_target).select("age", second_people.age))

    def test_authored_target_rejects_address_space_override(self) -> None:
        graph = SDKStore([Person])
        draft = graph.policy("one")
        people = draft.use(_bundle(graph), as_="people")
        target = draft.build(draft.all(people))
        with self.assertRaisesRegex(SDKStoreError, "already carries"):
            graph.query(target, address_space=target.address_space)

    def test_field_navigation_handle_is_select_only(self) -> None:
        graph = SDKStore([Person])
        draft = graph.policy("navigation")
        people = draft.use(_bundle(graph), as_="people")
        target = draft.build(draft.all(people))

        with self.assertRaisesRegex(SDKStoreError, "direct Policy ports"):
            graph.query(target).bind(people.person.field("age"), 22)


if __name__ == "__main__":
    unittest.main()
