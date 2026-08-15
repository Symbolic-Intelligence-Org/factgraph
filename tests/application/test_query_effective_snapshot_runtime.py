from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    entity_info,
    field_predicate,
    manage_rule_occurrence,
    resolve_selector,
)
from factgraph.application.query_effective_snapshot_runtime import (
    assert_resolved_query_effective_snapshot_current,
    resolve_query_effective_snapshot_v1,
)
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
    EvaluationQuerySelection,
    FieldPath,
    Policy,
    PolicyOccurrence,
    ProtocolShapeError,
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()
    unrelated: int = Field()


class FloatKeyPerson(Entity):
    key: float = Identity()
    age: int = Field()


class UnrelatedEntity(Entity):
    unrelated_id: str = Identity()
    value: int = Field()


def _address(alias: str, port: str) -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _seed(graph: SDKStore, employee_id: str, *, age: int, score: int, unrelated: int = 0) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"employee_id": employee_id}), index=index
    )
    encoded = ref.encoded_ref or ""
    info = entity_info(index, "Person")
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        graph.ledger,
        info.identity_predicates["employee_id"].pred_id,
        encoded,
        [("string", employee_id)],
    )
    for field, value in (("age", age), ("score", score), ("unrelated", unrelated)):
        set_field(
            graph.ledger,
            field_predicate(index, "Person", field).pred_id,
            encoded,
            [("int", value)],
        )
    return encoded


def _compiled(graph: SDKStore, *, navigation: bool = False):
    index = build_schema_index(graph.schema_ir)
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
    policy = compile_policy(Policy("person_policy", PolicyOccurrence("pair")), address_space=space)
    selections = (
        EvaluationQueryNavigationSelectionV0(
            "age_navigation",
            EvaluationQueryFieldNavigationV0(_address("pair", "person"), FieldPath("Person", "age")),
        ),
    ) if navigation else (
        EvaluationQuerySelection("age", _address("pair", "age")),
        EvaluationQuerySelection("score", _address("pair", "score")),
    )
    query = EvaluationQuery(
        policy.policy_digest,
        selections,
        (EvaluationQueryBinding(_address("pair", "person"), EntityRef("Person", {"employee_id": "alice"})),),
    )
    compiled = compile_evaluation_query(
        query, compiled_policy=policy, address_space=space, schema_index=index
    )
    materialized, _ = _materialize_adapter_derivation_plan(compiled._lowering_plan, engine="native")
    return compiled, materialized.body_ir


def _resolve(graph: SDKStore, scenario: object, *, navigation: bool = False):
    compiled, body = _compiled(graph, navigation=navigation)
    return resolve_query_effective_snapshot_v1(
        scenario,  # type: ignore[arg-type]
        compiled_query=compiled,
        materialized_body=body,
        store=graph._store,
        schema_index=graph._application_schema_index,
        base_view_digest=graph._view_snapshot_digest(query_typed_values=True),
    )


class QueryEffectiveSnapshotRuntimeTests(unittest.TestCase):
    def _single(self, value: int = 35) -> ScenarioFieldSubstitutionV0:
        return ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "alice"}),
            FieldPath("Person", "age"),
            value,
            "alice-age",
        )

    def test_identity_is_pre_evaluation_and_same_value_still_changes_relation_source(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        changed = _resolve(graph, self._single(35))
        same = _resolve(graph, self._single(22))
        self.assertEqual(changed.snapshot.scope, "query_dependency_relation_v1")
        self.assertEqual(changed.snapshot.normalization_profile, "single_field_replacement_v0")
        self.assertNotEqual(changed.snapshot.snapshot_digest, same.snapshot.snapshot_digest)
        self.assertFalse(same.snapshot.operations[0].semantic_value_changed)
        self.assertNotEqual(
            same.snapshot.baseline_relation_digest, same.snapshot.effective_relation_digest
        )
        self.assertNotIn("result", changed.snapshot.__dataclass_fields__)
        assert_resolved_query_effective_snapshot_current(changed)

    def test_q7_compatibility_adapter_exposes_the_parallel_pre_evaluation_identity(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        compiled, body = _compiled(graph)
        from factgraph.application.evaluation_scenario_runtime import (
            resolve_scenario_field_substitution_v0,
        )

        resolved = resolve_scenario_field_substitution_v0(
            self._single(35),
            compiled_query=compiled,
            materialized_body=body,
            store=graph._store,
            schema_index=graph._application_schema_index,
            base_view_digest=graph._view_snapshot_digest(query_typed_values=True),
        )
        self.assertEqual(
            resolved.effective_snapshot.effective_relation_digest,
            resolved.resolution.effective_relation_digest,
        )
        # Q7's result-aware compatibility digest remains a different, later
        # identity.  It is not silently substituted for the pre-eval snapshot.
        self.assertNotEqual(
            resolved.effective_snapshot.snapshot_digest,
            resolved.resolution.scenario_digest,
        )
        from factgraph.application.evaluation_scenario_runtime import (
            assert_resolved_scenario_compatibility_current,
        )

        assert_resolved_scenario_compatibility_current(resolved)
        with self.assertRaisesRegex(ValueError, "compatibility adapter"):
            assert_resolved_scenario_compatibility_current(
                replace(resolved, effective_relation=resolved.baseline_relation)
            )
        with self.assertRaisesRegex(ValueError, "compatibility adapter"):
            assert_resolved_scenario_compatibility_current(
                replace(
                    resolved,
                    effective_snapshot=replace(
                        resolved.effective_snapshot,
                        base_view_digest=resolved.effective_snapshot.effective_relation_digest,
                    ),
                )
            )
        # An old DTO can re-seal its own digest after a field mutation.  The
        # adapter must still reject it when its durable-looking legacy fields
        # disagree with the authoritative v1 operation.
        mutated_resolution = replace(resolved.resolution, premise_id="wrong-premise")
        with self.assertRaisesRegex(ValueError, "Q7 premise binding"):
            assert_resolved_scenario_compatibility_current(
                replace(
                    resolved,
                    resolution=mutated_resolution,
                    premise_bindings=(
                        replace(
                            resolved.premise_bindings[0],
                            operation_digest=mutated_resolution.operation_digest,
                        ),
                    ),
                )
            )
        with self.assertRaisesRegex(ValueError, "invalid private"):
            assert_resolved_scenario_compatibility_current(
                replace(resolved, _effective_snapshot_runtime="not-a-runtime")  # type: ignore[arg-type]
            )

    def test_q11_compatibility_adapter_rejects_a_self_consistent_legacy_operation_splice(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        _seed(graph, "bob", age=19, score=7)
        compiled, body = _compiled(graph)
        from factgraph.application.evaluation_scenario_runtime import (
            assert_resolved_scenario_compatibility_current,
            resolve_scenario_field_substitution_set_v0,
        )

        resolved = resolve_scenario_field_substitution_set_v0(
            ScenarioFieldSubstitutionSetV0(
                (
                    self._single(35),
                    ScenarioFieldSubstitutionV0(
                        EntityRef("Person", {"employee_id": "bob"}),
                        FieldPath("Person", "score"),
                        11,
                        "bob-score",
                    ),
                )
            ),
            compiled_query=compiled,
            materialized_body=body,
            store=graph._store,
            schema_index=graph._application_schema_index,
            base_view_digest=graph._view_snapshot_digest(query_typed_values=True),
        )
        mutated_legacy = replace(resolved.resolution.operations[0], premise_id="wrong-premise")
        mutated_resolution = replace(
            resolved.resolution,
            operations=(mutated_legacy, *resolved.resolution.operations[1:]),
        )
        with self.assertRaisesRegex(ValueError, "Q11 operation"):
            assert_resolved_scenario_compatibility_current(
                replace(
                    resolved,
                    resolution=mutated_resolution,
                    premise_bindings=(
                        replace(
                            resolved.premise_bindings[0],
                            operation_digest=mutated_legacy.operation_digest,
                        ),
                        *resolved.premise_bindings[1:],
                    ),
                )
            )

    def test_set_input_permutation_canonicalizes_and_keeps_only_dependency_relations(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9, unrelated=1)
        _seed(graph, "bob", age=19, score=7, unrelated=2)
        alice = self._single(35)
        bob = ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "bob"}), FieldPath("Person", "score"), 11, "bob-score"
        )
        forward = _resolve(graph, ScenarioFieldSubstitutionSetV0((alice, bob)))
        reverse = _resolve(graph, ScenarioFieldSubstitutionSetV0((bob, alice)))
        self.assertEqual(forward.snapshot, reverse.snapshot)
        self.assertEqual(forward.snapshot.snapshot_digest, reverse.snapshot.snapshot_digest)
        unrelated_id = field_predicate(build_schema_index(graph.schema_ir), "Person", "unrelated").pred_id
        self.assertNotIn(unrelated_id, forward.snapshot.dependency_predicate_ids)
        self.assertNotIn(unrelated_id, forward.baseline_relation)
        self.assertEqual(
            tuple(item.premise_id for item in forward.snapshot.operations), ("alice-age", "bob-score")
        )

    def test_navigation_lookup_is_a_dependency_and_can_be_replaced(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        resolved = _resolve(graph, self._single(35), navigation=True)
        age_id = field_predicate(build_schema_index(graph.schema_ir), "Person", "age").pred_id
        self.assertIn(age_id, resolved.snapshot.dependency_predicate_ids)
        self.assertEqual(resolved.snapshot.operations[0].predicate_id, age_id)

    def test_hybrid_or_undeclared_effective_delta_fails_closed(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        resolved = _resolve(graph, self._single(35))
        with self.assertRaisesRegex(ValueError, "digest|undeclared"):
            assert_resolved_query_effective_snapshot_current(
                replace(
                    resolved,
                    effective_relation=resolved.baseline_relation,
                )
            )
        with self.assertRaises(ProtocolShapeError):
            replace(
                resolved.snapshot,
                dependency_predicate_ids=("person:age", "Person:exists", "person:age"),
            )

    def test_identity_admission_uses_the_captured_resolver_context(self) -> None:
        graph = SDKStore([Person])
        _seed(graph, "alice", age=22, score=9)
        compiled, body = _compiled(graph)
        base_view_digest = graph._view_snapshot_digest(query_typed_values=True)
        resolved = resolve_query_effective_snapshot_v1(
            self._single(35),
            compiled_query=compiled,
            materialized_body=body,
            store=graph._store,
            schema_index=graph._application_schema_index,
            base_view_digest=base_view_digest,
        )
        self.assertEqual(resolved.snapshot.operations[0].premise_id, "alice-age")

    def test_identity_capture_reads_only_the_submitted_scenario_identity(self) -> None:
        graph = SDKStore([Person, UnrelatedEntity])
        encoded = _seed(graph, "alice", age=22, score=9)
        compiled, body = _compiled(graph)
        projected = project_view_facts_with_witness(graph._store.ledger, graph._store.schema_ir)
        base_view_digest = graph._view_snapshot_digest(query_typed_values=True)
        identity_predicate = graph._application_schema_index.entities["Person"].identity_predicates[
            "employee_id"
        ].pred_id
        calls: list[tuple[str | None, str | None]] = []
        original_find_claims = graph._store.ledger.find_claims

        def traced_find_claims(
            pred_id: str | None = None,
            e_ref: str | None = None,
        ) -> object:
            calls.append((pred_id, e_ref))
            return original_find_claims(pred_id=pred_id, e_ref=e_ref)

        with patch.object(graph._store.ledger, "find_claims", side_effect=traced_find_claims):
            resolve_query_effective_snapshot_v1(
                self._single(35),
                compiled_query=compiled,
                materialized_body=body,
                store=graph._store,
                schema_index=graph._application_schema_index,
                base_view_digest=base_view_digest,
                _projector=lambda _ledger, _schema: projected,
            )

        self.assertEqual(calls, [(identity_predicate, encoded)])

    def test_q7_active_identity_admission_is_captured_before_projection(self) -> None:
        graph = SDKStore([Person])
        encoded = _seed(graph, "alice", age=22, score=9)
        index = build_schema_index(graph.schema_ir)
        identity_predicate = index.entities["Person"].identity_predicates["employee_id"].pred_id
        # This remains active but loses the single-cardinality chosen projection.
        # Q7 admitted the matching active claim, so P2 must preserve that fact.
        set_field(graph.ledger, identity_predicate, encoded, [("string", "other")])
        resolved = _resolve(graph, self._single(35))
        self.assertEqual(resolved.snapshot.operations[0].entity_ref, encoded)

    def test_q7_float_identity_admission_retains_stored_term_semantics(self) -> None:
        graph = SDKStore([FloatKeyPerson])
        index = build_schema_index(graph.schema_ir)
        ref = resolve_selector(
            EntitySelector(entity_type="FloatKeyPerson", identity={"key": 1.0}), index=index
        )
        encoded = ref.encoded_ref or ""
        info = entity_info(index, "FloatKeyPerson")
        set_field(graph.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            graph.ledger,
            info.identity_predicates["key"].pred_id,
            encoded,
            [("float64", 1.0)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "FloatKeyPerson", "age").pred_id,
            encoded,
            [("int", 22)],
        )
        person, age = Var("$person"), Var("$age")
        rule = build_resolved_rule(
            id="float_person_age",
            version="1",
            when=(
                PredAtom("FloatKeyPerson:exists", [person]),
                PredAtom("float_key_person:age", [person, age]),
            ),
            ports={
                "person": SemanticRulePort(person, entity_identity("FloatKeyPerson")),
                "age": SemanticRulePort(age, field_endpoint("FloatKeyPerson", "age")),
            },
            schema_index=index,
        )
        space = SemanticAddressSpace((manage_rule_occurrence(rule, "pair"),))
        policy = compile_policy(Policy("float_person_policy", PolicyOccurrence("pair")), address_space=space)
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("age", _address("pair", "age")),),
                (EvaluationQueryBinding(_address("pair", "person"), EntityRef("FloatKeyPerson", {"key": 1.0})),),
            ),
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        materialized, _ = _materialize_adapter_derivation_plan(compiled._lowering_plan, engine="native")
        resolved = resolve_query_effective_snapshot_v1(
            ScenarioFieldSubstitutionV0(
                EntityRef("FloatKeyPerson", {"key": 1.0}),
                FieldPath("FloatKeyPerson", "age"),
                35,
                "float-age",
            ),
            compiled_query=compiled,
            materialized_body=materialized.body_ir,
            store=graph._store,
            schema_index=index,
            base_view_digest=graph._view_snapshot_digest(query_typed_values=True),
        )
        self.assertEqual(resolved.snapshot.operations[0].entity_ref, encoded)


if __name__ == "__main__":
    unittest.main()
