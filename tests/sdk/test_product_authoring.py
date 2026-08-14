from __future__ import annotations

import factgraph.application as factgraph_application
import factgraph.application.protocol as factgraph_protocol
import factgraph.application.protocol.policy as policy_protocol
import factgraph.sdk as factgraph_sdk
import unittest

from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.application.policy_runtime import compile_policy
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.policy import (
    Policy,
    PolicyError,
    PolicyV2Only,
    policy_contains_weighted_choice,
)
from factgraph.application.semantic_port_runtime import ResolvedRuleBundle
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import (
    ASSET_META_ABSENT_V1,
    AssetMeta,
    Entity,
    Field,
    Identity,
    ProductPolicyV1,
    ProductRuleV1,
    SDKStore,
    assert_asset_binding_current_v1,
    asset_meta_for_target,
    vars,
)
from factgraph.sdk.errors import SDKStoreError


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _product_rule(graph: SDKStore, *, meta: AssetMeta | None = None) -> ProductRuleV1:
    person, age = Var("$person"), Var("$age")
    return graph.build_rule(
        id="person_values",
        version="1",
        meta=meta,
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


def _weighted_choice_target(graph: SDKStore) -> ProductPolicyV1:
    rule = _product_rule(graph)
    policy = graph.policy_builder("chosen", version="1", meta=AssetMeta(name="Chosen"))
    key = policy.use(rule, as_="key")
    declared = policy.use(rule, as_="declared")
    inferred = policy.use(rule, as_="inferred")
    choice = policy.weighted_choice(
        id="eligibility_source",
        on=(key.person,),
        choices=(
            policy.choice("inferred", probability="0.3", when=policy.all(inferred)),
            policy.choice("declared", probability="0.7", when=policy.all(declared)),
        ),
    )
    return policy.build(policy.all(key, choice))


class ProductAuthoringTests(unittest.TestCase):
    def test_asset_meta_is_canonical_and_separate_from_rule_logic(self) -> None:
        graph = SDKStore([Person])
        first = _product_rule(
            graph,
            meta=AssetMeta(
                name="People",
                description="A source Rule",
                tags=("people", "demo", "people"),
            ),
        )
        second = _product_rule(graph, meta=AssetMeta(name="Another label"))

        self.assertEqual(first.asset_meta.tags, ("demo", "people"))
        self.assertEqual(first.rule.content_digest, second.rule.content_digest)
        self.assertNotEqual(first.asset_binding_digest, second.asset_binding_digest)
        self.assertEqual(
            first.asset_snapshot()["descriptor_digest"], first.asset_meta.descriptor_digest
        )
        self.assertIs(asset_meta_for_target(first), first.asset_meta)

    def test_raw_rule_has_an_explicit_absent_descriptor_state(self) -> None:
        graph = SDKStore([Person])
        product = _product_rule(graph)
        self.assertIs(product.asset_meta, ASSET_META_ABSENT_V1)
        # The base view is intentionally raw compatibility input, not a hidden
        # product metadata registry.
        raw = ResolvedRuleBundle(product.rule, product.contract)
        self.assertIs(asset_meta_for_target(raw), ASSET_META_ABSENT_V1)

    def test_asset_binding_rejects_a_descriptor_splice(self) -> None:
        graph = SDKStore([Person])
        first = _product_rule(graph, meta=AssetMeta(name="First"))
        second = _product_rule(graph, meta=AssetMeta(name="Second"))
        assert_asset_binding_current_v1(first)
        # Frozen dataclasses prevent ordinary mutation.  Deliberately bypass it
        # here to emulate an untrusted decoded run that cross-wires B's
        # descriptor onto A while retaining A's binding seal.
        object.__setattr__(first, "asset_meta", second.asset_meta)
        with self.assertRaisesRegex(SDKStoreError, "asset binding digest") as error:
            assert_asset_binding_current_v1(first)
        self.assertEqual(error.exception.code, "ASSET_BINDING_DIGEST_MISMATCH")

    def test_rule_builder_and_direct_form_resolve_the_same_rule(self) -> None:
        graph = SDKStore([Person])
        person, age = Var("$person"), Var("$age")
        builder = graph.rule_builder(
            "person_values",
            version="1",
            meta=AssetMeta(name="Person values"),
        )
        staged = builder.build(
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
        direct = _product_rule(graph, meta=AssetMeta(name="Person values"))

        self.assertIsInstance(staged, ProductRuleV1)
        self.assertEqual(staged.rule.content_digest, direct.rule.content_digest)
        self.assertEqual(
            staged.contract.semantic_contract_digest, direct.contract.semantic_contract_digest
        )
        self.assertEqual(staged.asset_binding_digest, direct.asset_binding_digest)
        # ProductRuleV1 remains compatible with the single established Query
        # target resolver because it is a fully resolved Rule bundle.
        self.assertIsNotNone(
            graph.query(staged).select("age", SemanticPortAddress("target", "age")).compile()
        )

    def test_rule_builder_accepts_public_entity_and_field_semantic_descriptors(self) -> None:
        """A product Rule needs no application/core imports for semantic ports."""

        graph = SDKStore([Person])
        with vars("person", "age") as (person, age):
            product = graph.rule_builder(
                "person_values_public_sdk",
                version="1",
                meta=AssetMeta(name="Public SDK Rule"),
            ).build(
                when=(Person(person), Person(person).age == age),
                ports={"person": person, "age": age},
                semantic_ports={"person": Person, "age": Person.age},
            )

        person_endpoint = product.contract.ports["person"].endpoint
        age_endpoint = product.contract.ports["age"].endpoint
        self.assertEqual(getattr(person_endpoint, "entity_type", None), "Person")
        self.assertEqual(getattr(age_endpoint, "entity_type", None), "Person")
        self.assertEqual(getattr(age_endpoint, "field_name", None), "age")
        self.assertIsNotNone(
            graph.query(product).select("age", SemanticPortAddress("target", "age")).compile()
        )

    def test_policy_builder_and_direct_callback_preserve_same_owner_handles(self) -> None:
        graph = SDKStore([Person])
        rule = _product_rule(graph, meta=AssetMeta(name="Person values"))

        builder = graph.policy_builder("adult", version="1", meta=AssetMeta(name="Adult"))
        people = builder.use(rule, as_="people")
        staged = builder.build(builder.all(people, people.age > 12))

        def direct_body(policy):
            people = policy.use(rule, as_="people")
            return policy.all(people, people.age > 12)

        direct = graph.build_policy(
            id="adult",
            version="1",
            meta=AssetMeta(name="Adult"),
            build=direct_body,
        )

        self.assertIsInstance(staged, ProductPolicyV1)
        self.assertEqual(staged.policy.when.node_id, direct.policy.when.node_id)
        self.assertEqual(staged.asset_binding_digest, direct.asset_binding_digest)
        self.assertIsNotNone(graph.query(staged).select("age", people.age).compile())

    def test_direct_callback_cannot_use_foreign_builder_handle(self) -> None:
        graph = SDKStore([Person])
        rule = _product_rule(graph)
        foreign = graph.policy_builder("foreign")
        foreign_people = foreign.use(rule, as_="people")

        with self.assertRaisesRegex(SDKStoreError, "different Policy builder"):
            graph.build_policy(
                id="local",
                build=lambda local: local.all(foreign_people),
            )

    def test_weighted_choice_is_canonical_v2_sidecar_and_legacy_fails_closed(self) -> None:
        graph = SDKStore([Person])
        target = _weighted_choice_target(graph)

        topology = target.weighted_choices[0]
        self.assertIsInstance(target.policy, PolicyV2Only)
        self.assertEqual(tuple(arm.arm_id for arm in topology.arms), ("declared", "inferred"))
        self.assertTrue(topology.node_id.startswith("wc:"))
        self.assertTrue(target.requires_v2_profile)
        query = graph.query(target).select("age", SemanticPortAddress("key", "age"))
        with self.assertRaisesRegex(SDKStoreError, "V2 ProbLog-only") as compile_error:
            query.compile()
        self.assertEqual(compile_error.exception.code, "WEIGHTED_CHOICE_V2_ONLY")
        with self.assertRaisesRegex(SDKStoreError, "V2 ProbLog-only"):
            query.plan()

    def test_weighted_choice_raw_policy_unwrap_is_rejected_at_legacy_target_resolution(
        self,
    ) -> None:
        graph = SDKStore([Person])
        target = _weighted_choice_target(graph)

        # The exact public carrier has a defense-in-depth marker; supplying its
        # address space cannot reclassify the intrinsic choice as legacy logic.
        with self.assertRaises(SDKStoreError) as error:
            graph.query(target.policy, address_space=target.address_space)
        self.assertEqual(error.exception.code, "WEIGHTED_CHOICE_V2_ONLY")

        # The outer marker is defense in depth, not the semantic boundary.
        # A caller can create a fresh base Policy, but the intrinsic choice
        # expression remains in `.when` and is still rejected before legacy
        # `PolicyAny` compilation could happen.
        rewrapped = Policy(target.policy.id, target.policy.when, target.policy.version)
        self.assertNotIsInstance(rewrapped, PolicyV2Only)
        self.assertTrue(policy_contains_weighted_choice(rewrapped))
        with self.assertRaises(SDKStoreError) as rewrapped_error:
            graph.query(rewrapped, address_space=target.address_space)
        self.assertEqual(rewrapped_error.exception.code, "WEIGHTED_CHOICE_V2_ONLY")
        with self.assertRaises(PolicyError) as compiler_error:
            compile_policy(
                rewrapped,
                address_space=target.address_space,
                schema_index=graph._application_schema_index,
            )
        self.assertEqual(getattr(compiler_error.exception, "code", None), "WEIGHTED_CHOICE_V2_ONLY")

        # ProductPolicy cannot discard the sidecar replay projection while
        # retaining the intrinsic source AST.
        with self.assertRaises(SDKStoreError) as missing_sidecar:
            ProductPolicyV1(
                target.policy,
                target.address_space,
                target._authoring_owner,
                target.asset_meta,
                (),
            )
        self.assertEqual(missing_sidecar.exception.code, "WEIGHTED_CHOICE_AST_SIDECAR_MISMATCH")

    def test_weighted_choice_skeleton_lowering_is_not_a_public_surface(self) -> None:
        """Only the controlled V2 bridge may derive the compiler skeleton."""

        public_name = "lower_policy_weighted_choices_to_any_skeleton"
        for surface in (factgraph_application, factgraph_protocol, policy_protocol, factgraph_sdk):
            with self.subTest(surface=surface.__name__):
                self.assertFalse(hasattr(surface, public_name))
                self.assertNotIn(public_name, getattr(surface, "__all__", ()))

    def test_weighted_choice_asset_binding_recomputes_live_topology_fields(self) -> None:
        def mutate_arms(target: ProductPolicyV1) -> None:
            first, second = target.weighted_choices[0].arms
            object.__setattr__(first, "probability", "0.4")
            object.__setattr__(second, "probability", "0.6")

        def mutate_key(target: ProductPolicyV1) -> None:
            object.__setattr__(
                target.weighted_choices[0],
                "selection_key",
                (SemanticPortAddress("key", "age"),),
            )

        def mutate_skeleton(target: ProductPolicyV1) -> None:
            object.__setattr__(
                target.weighted_choices[0],
                "skeleton_node_id",
                target.policy.when.node_id,
            )

        for label, mutate in (
            ("arms", mutate_arms),
            ("selection_key", mutate_key),
            ("skeleton", mutate_skeleton),
        ):
            with self.subTest(label=label):
                target = _weighted_choice_target(SDKStore([Person]))
                mutate(target)
                with self.assertRaises(SDKStoreError) as integrity_error:
                    assert_asset_binding_current_v1(target)
                self.assertEqual(
                    integrity_error.exception.code,
                    "WEIGHTED_CHOICE_TOPOLOGY_DIGEST_MISMATCH",
                )
                # The public V2 asset snapshot invokes the same check before
                # it exposes the target/descriptor association to a runner.
                with self.assertRaises(SDKStoreError) as snapshot_error:
                    target.asset_snapshot()
                self.assertEqual(
                    snapshot_error.exception.code,
                    "WEIGHTED_CHOICE_TOPOLOGY_DIGEST_MISMATCH",
                )

    def test_weighted_choice_rejects_partial_key_and_noncanonical_weight(self) -> None:
        graph = SDKStore([Person])
        rule = _product_rule(graph)
        policy = graph.policy_builder("bad_choice")
        key = policy.use(rule, as_="key")
        left = policy.use(rule, as_="left")
        right = policy.use(rule, as_="right")

        with self.assertRaisesRegex(SDKStoreError, "canonical decimal string"):
            policy.choice("left", probability=0.5, when=policy.all(left))  # type: ignore[arg-type]

        choice = policy.weighted_choice(
            id="source",
            on=(left.person,),
            choices=(
                policy.choice("left", probability="0.5", when=policy.all(left)),
                policy.choice("right", probability="0.5", when=policy.all(right)),
            ),
        )
        with self.assertRaisesRegex(SDKStoreError, "branch-total"):
            policy.build(policy.all(key, choice))

    def test_ordinary_any_remains_deterministic_and_can_compile(self) -> None:
        graph = SDKStore([Person])
        rule = _product_rule(graph)
        policy = graph.policy_builder("ordinary_any")
        key = policy.use(rule, as_="key")
        left = policy.use(rule, as_="left")
        right = policy.use(rule, as_="right")
        target = policy.build(policy.all(key, policy.any(policy.all(left), policy.all(right))))

        self.assertFalse(target.requires_v2_profile)
        self.assertNotIsInstance(target.policy, PolicyV2Only)
        self.assertEqual(target.weighted_choices, ())
        self.assertIsNotNone(graph.query(target).select("age", key.age).compile())


if __name__ == "__main__":
    unittest.main()
