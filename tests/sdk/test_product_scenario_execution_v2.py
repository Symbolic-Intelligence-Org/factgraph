"""Product SDK ingress coverage for Q20 Scenario/profile construction."""

from __future__ import annotations

import unittest

from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import (
    AssetMeta,
    Entity,
    EvaluationExecutionProfileV2,
    Field,
    Identity,
    ProductScenarioExecutionError,
    ScenarioSpecV2,
    SDKStore,
)

_DIGEST = "sha256:" + "a" * 64


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()
    tags: list[str] = Field()


def _source(ref: str) -> dict[str, object]:
    return {
        "ref": ref,
        "locator": {"kind": "line_span", "line_start": 1, "line_end": 2},
        "content_digest": _DIGEST,
        "origin_role": "scenario_hypothesis",
    }


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


class ProductScenarioExecutionV2Tests(unittest.TestCase):
    def test_scenario_builder_uses_sdk_fields_managed_refs_and_strict_meta(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.ref(Person, person_id="alice")

        scenario = (
            graph.scenario()
            .set(
                Person.age,
                alice,
                34,
                premise_id="age-hypothesis",
                meta={
                    "raw_kind": "probabilistic",
                    "bound": [0.8, 0.8],
                    "source": _source("operator:age"),
                    "note": "operator supplied premise",
                },
            )
            .add(
                Person.tags,
                alice,
                "candidate",
                meta={"source": _source("operator:tag")},
            )
            .set_exact(
                Person.tags,
                alice,
                ("python", "sql"),
                member_meta=(
                    {"source": _source("operator:python")},
                    {
                        "raw_kind": "probabilistic",
                        "bound": ["0.7", "0.7"],
                        "source": _source("operator:sql"),
                    },
                ),
            )
            .without(
                Person.tags,
                alice,
                "obsolete",
                meta={"source": _source("operator:without")},
            )
            .build()
        )

        self.assertIsInstance(scenario, ScenarioSpecV2)
        self.assertEqual(len(scenario.operations), 4)
        set_age = next(item for item in scenario.operations if item.premise_id == "age-hypothesis")
        self.assertEqual(set_age.meta.fact_semantics.point_probability, "0.8")
        self.assertEqual(set_age.meta.provenance[0].source_ref, "operator:age")
        exact = next(item for item in scenario.operations if item.kind == "set_exact_members")
        self.assertEqual(
            tuple(
                item.fact_semantics.point_probability if item.fact_semantics else None
                for item in exact.member_meta
            ),
            (None, "0.7"),
        )

    def test_scenario_meta_never_accepts_legacy_source_or_confidence_and_preserves_cardinality(
        self,
    ) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.ref(Person, person_id="alice")

        with self.assertRaisesRegex(ProductScenarioExecutionError, "Scenario meta") as source_error:
            graph.scenario().set(Person.age, alice, 20, meta={"source": "legacy-source"})
        self.assertEqual(source_error.exception.code, "SCENARIO_V2_META_INVALID")

        with self.assertRaisesRegex(
            ProductScenarioExecutionError, "Scenario meta"
        ) as confidence_error:
            graph.scenario().set(Person.age, alice, 20, meta={"confidence": 0.8})
        self.assertEqual(confidence_error.exception.code, "SCENARIO_V2_META_INVALID")

        with self.assertRaisesRegex(ProductScenarioExecutionError, "multi-value") as add_error:
            graph.scenario().add(Person.age, alice, 20)
        self.assertEqual(add_error.exception.code, "SCENARIO_V2_CARDINALITY_MISMATCH")

        with self.assertRaisesRegex(ProductScenarioExecutionError, "multi-value") as remove_error:
            graph.scenario().without(Person.age, alice, 20)
        self.assertEqual(remove_error.exception.code, "SCENARIO_V2_CARDINALITY_MISMATCH")

        with self.assertRaisesRegex(
            ProductScenarioExecutionError, "Scenario operation"
        ) as semantic_without:
            graph.scenario().without(
                Person.age,
                alice,
                meta={"raw_kind": "probabilistic", "bound": [0.5, 0.5]},
            )
        self.assertEqual(semantic_without.exception.code, "SCENARIO_V2_OPERATION_INVALID")

    def test_set_exact_keeps_member_metadata_paired_through_canonical_value_order(self) -> None:
        graph = SDKStore([Person])
        alice = graph.entities.ref(Person, person_id="alice")

        scenario = (
            graph.scenario()
            .set_exact(
                Person.tags,
                alice,
                ("z", "a"),
                member_meta=(
                    {
                        "raw_kind": "probabilistic",
                        "bound": ["0.2", "0.2"],
                        "source": _source("operator:z"),
                        "note": "for z",
                    },
                    {
                        "raw_kind": "probabilistic",
                        "bound": ["0.8", "0.8"],
                        "source": _source("operator:a"),
                        "note": "for a",
                    },
                ),
            )
            .build()
        )

        exact = scenario.operations[0]
        self.assertEqual(
            tuple((value.tag, value.value) for value in exact.operation.values),
            (("string", "a"), ("string", "z")),
        )
        self.assertEqual(
            tuple(item.fact_semantics.point_probability for item in exact.member_meta),
            ("0.8", "0.2"),
        )
        self.assertEqual(
            tuple(item.provenance[0].source_ref for item in exact.member_meta),
            ("operator:a", "operator:z"),
        )

    def test_explicit_target_context_seals_rule_occurrence_and_choice_attachments(self) -> None:
        graph = SDKStore([Person])
        rule = _rule(graph)
        attached_rule = _rule(graph, id="attached_values")
        builder = graph.policy_builder("chosen", version="1", meta=AssetMeta(name="Chosen"))
        key = builder.use(rule, as_="key")
        attached = builder.use(attached_rule, as_="attached")
        declared = builder.use(rule, as_="declared")
        inferred = builder.use(rule, as_="inferred")
        choice = builder.weighted_choice(
            id="source",
            on=(key.person,),
            choices=(
                builder.choice("declared", probability="0.7", when=builder.all(declared)),
                builder.choice("inferred", probability="0.3", when=builder.all(inferred)),
            ),
        )
        policy = builder.build(builder.all(key, attached, choice))

        profile = (
            graph.execution.problog(target=policy, name="risk-v1")
            .fact_semantics(identity_probability=True)
            .for_occurrence(key, graph.problog.occurrence_semantics())
            .for_rule(attached_rule, graph.problog.rule_semantics())
            .for_choice(choice, graph.problog.choice_semantics())
            .build()
        )

        self.assertIsInstance(profile, EvaluationExecutionProfileV2)
        self.assertEqual(profile.kind, "problog_point_v2")
        self.assertEqual(
            tuple(pin.engine for pin in profile.engines), ("problog", "native", "souffle")
        )
        self.assertEqual(
            {item.kind for item in profile.attachments}, {"choice", "occurrence", "rule"}
        )
        self.assertTrue(
            all(
                item.target.target_digest == policy.logical_identity_digest
                for item in profile.attachments
            )
        )
        self.assertEqual(len(profile.target_pins), 1)
        self.assertEqual(profile.target_pins[0].target_digest, policy.logical_identity_digest)

    def test_profile_fact_semantics_is_explicit_and_target_ownership_is_checked(self) -> None:
        graph = SDKStore([Person])
        rule = _rule(graph)

        with self.assertRaisesRegex(
            ProductScenarioExecutionError, "must be selected explicitly"
        ) as missing:
            graph.execution.problog(target=rule).build()
        self.assertEqual(missing.exception.code, "V2_PROFILE_SEMANTICS_REQUIRED")

        native = graph.execution.native_deterministic(target=rule, name="native-v2").build()
        self.assertEqual(native.kind, "native_deterministic_v2")
        self.assertEqual(native.attachments, ())
        self.assertEqual(native.target_pins[0].target_kind, "rule")
        self.assertEqual(native.target_pins[0].target_id, rule.rule.id)
        self.assertEqual(native.target_pins[0].target_version, rule.rule.version)
        self.assertEqual(native.target_pins[0].target_digest, rule.logical_identity_digest)

        direct_profile = (
            graph.execution.problog(target=rule)
            .fact_semantics()
            .for_rule(rule, graph.problog.rule_semantics())
            .build()
        )
        direct_attachment = direct_profile.attachments[0]
        self.assertEqual(direct_attachment.target.target_digest, rule.logical_identity_digest)
        self.assertEqual(direct_attachment.rule_digest, "sha256:" + rule.rule.content_digest)

        first = graph.policy_builder("first")
        first_occurrence = first.use(rule, as_="person")
        first_target = first.build(first_occurrence)
        second = graph.policy_builder("second")
        foreign_occurrence = second.use(rule, as_="person")
        with self.assertRaisesRegex(
            ProductScenarioExecutionError, "different Policy target"
        ) as foreign:
            (
                graph.execution.problog(target=first_target)
                .fact_semantics()
                .for_occurrence(foreign_occurrence, graph.problog.occurrence_semantics())
            )
        self.assertEqual(foreign.exception.code, "V2_PROFILE_OCCURRENCE_TARGET_MISMATCH")

    def test_policy_rule_and_its_occurrence_cannot_both_own_problog_semantics(self) -> None:
        graph = SDKStore([Person])
        rule = _rule(graph)
        builder = graph.policy_builder("overlap")
        occurrence = builder.use(rule, as_="person")
        policy = builder.build(occurrence)

        with self.assertRaisesRegex(ProductScenarioExecutionError, "both Rule-level") as rule_first:
            (
                graph.execution.problog(target=policy)
                .fact_semantics()
                .for_rule(rule, graph.problog.rule_semantics())
                .for_occurrence(occurrence, graph.problog.occurrence_semantics())
            )
        self.assertEqual(rule_first.exception.code, "V2_PROFILE_ATTACHMENT_OVERLAP")

        with self.assertRaisesRegex(
            ProductScenarioExecutionError, "both Rule-level"
        ) as occurrence_first:
            (
                graph.execution.problog(target=policy)
                .fact_semantics()
                .for_occurrence(occurrence, graph.problog.occurrence_semantics())
                .for_rule(rule, graph.problog.rule_semantics())
            )
        self.assertEqual(occurrence_first.exception.code, "V2_PROFILE_ATTACHMENT_OVERLAP")


if __name__ == "__main__":
    unittest.main()
