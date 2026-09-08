from __future__ import annotations

import unittest
from dataclasses import replace

from factgraph.application import (
    PolicyCompiledBranch,
    PolicyRulePin,
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_policy,
    encode_entity_ref,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyError,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLiteral,
    PolicyLoweredRef,
    PolicyNodeLineage,
    PolicyOccurrence,
    PolicyUnify,
    EntityRef,
    SemanticPortAddress,
    SemanticRulePort,
    FieldPath,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.policy import PolicyStructureNodeV0, PolicyStructureV0
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    Var,
)
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


class Unrelated(Entity):
    code: str = Identity()


class ComparisonTypes(Entity):
    comparison_id: str = Identity()
    count: int = Field()
    label: str = Field()
    ratio: float = Field()
    active: bool = Field()


def _index(*, unrelated: bool = False):
    entities = [Person, Unrelated] if unrelated else [Person]
    return build_schema_index(
        compile_schema_from_classes(entities, generated_at="2026-08-12T00:00:00Z")
    )


def _person_bundle(
    *,
    rule_id: str = "person_values",
    schema_index=None,
    extra_atoms: tuple[object, ...] = (),
):
    person, age, score = Var("$person"), Var("$age"), Var("$score")
    return build_resolved_rule(
        id=rule_id,
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
            PredAtom("person:score", [person, score]),
            *extra_atoms,
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            "score": SemanticRulePort(score, field_endpoint("Person", "score")),
        },
        schema_index=_index() if schema_index is None else schema_index,
    )


def _space(bundle, *aliases: str) -> SemanticAddressSpace:
    return SemanticAddressSpace(tuple(manage_rule_occurrence(bundle, alias) for alias in aliases))


def _comparison_types_bundle():
    index = build_schema_index(
        compile_schema_from_classes([ComparisonTypes], generated_at="2026-08-13T00:00:00Z")
    )
    item, count, label, ratio, active = (
        Var("$item"),
        Var("$count"),
        Var("$label"),
        Var("$ratio"),
        Var("$active"),
    )
    return index, build_resolved_rule(
        id="comparison_types",
        version="1",
        when=(
            PredAtom("ComparisonTypes:exists", [item]),
            PredAtom("comparison_types:count", [item, count]),
            PredAtom("comparison_types:label", [item, label]),
            PredAtom("comparison_types:ratio", [item, ratio]),
            PredAtom("comparison_types:active", [item, active]),
        ),
        ports={
            "item": SemanticRulePort(item, entity_identity("ComparisonTypes")),
            "count": SemanticRulePort(count, field_endpoint("ComparisonTypes", "count")),
            "label": SemanticRulePort(label, field_endpoint("ComparisonTypes", "label")),
            "ratio": SemanticRulePort(ratio, field_endpoint("ComparisonTypes", "ratio")),
            "active": SemanticRulePort(
                active, field_endpoint("ComparisonTypes", "active")
            ),
        },
        schema_index=index,
    )


def _occ(alias: str) -> PolicyOccurrence:
    return PolicyOccurrence(alias)


def _address(alias: str, port: str = "person") -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _unify(left: str, right: str, port: str = "person") -> PolicyUnify:
    return PolicyUnify(_address(left, port), _address(right, port))


def _nav(alias: str, field: str = "age") -> PolicyFieldNavigation:
    return PolicyFieldNavigation(_address(alias), FieldPath("Person", field))


class PolicyCompileTests(unittest.TestCase):
    def test_occurrence_all_any_and_branch_local_unify_compile(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b", "c")
        policy = Policy(
            "people",
            PolicyAny(
                (
                    PolicyAll((_occ("a"), _occ("b"), _unify("a", "b"))),
                    _occ("c"),
                )
            ),
            version="3",
        )

        compiled = compile_policy(policy, address_space=space)

        self.assertEqual(compiled.policy_id, "people")
        self.assertEqual(compiled.policy_version, "3")
        self.assertEqual(len(compiled.branches), 2)
        self.assertEqual(sum(len(branch.pending_joins) for branch in compiled._body_plan.branches), 1)
        joined = next(branch for branch in compiled._body_plan.branches if branch.pending_joins)
        self.assertEqual(len(joined.occurrence_aliases), 2)

    def test_same_rule_occurrences_stay_distinct_and_join_only_when_explicit(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b")
        no_join = compile_policy(
            Policy("separate", PolicyAll((_occ("a"), _occ("b")))),
            address_space=space,
        )
        joined = compile_policy(
            Policy("joined", PolicyAll((_occ("a"), _occ("b"), _unify("a", "b")))),
            address_space=space,
        )

        self.assertEqual(no_join._body_plan.branches[0].pending_joins, ())
        self.assertEqual(len(joined._body_plan.branches[0].pending_joins), 1)
        self.assertEqual(
            {pin.occurrence_alias for pin in joined.rule_pins},
            {"a", "b"},
        )

    def test_partial_unify_rejects_but_branch_local_form_compiles(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b", "c")
        partial = Policy(
            "partial",
            PolicyAll(
                (
                    _occ("a"),
                    PolicyAny((_occ("b"), _occ("c"))),
                    _unify("a", "b"),
                )
            ),
        )
        with self.assertRaises(PolicyError) as ctx:
            compile_policy(partial, address_space=space)
        self.assertEqual(ctx.exception.code, "PARTIAL_BRANCH_CONSTRAINT")
        self.assertEqual(ctx.exception.stage, "policy_compile")

        local = Policy(
            "local",
            PolicyAny((PolicyAll((_occ("a"), _occ("b"), _unify("a", "b"))), _occ("c"))),
        )
        self.assertEqual(len(compile_policy(local, address_space=space).branches), 2)

    def test_unify_requires_distinct_occurrences_and_exact_endpoint(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b")
        cases = (
            (
                PolicyUnify(_address("a", "person"), _address("b", "age")),
                "INCOMPATIBLE_UNIFY_ENDPOINTS",
            ),
            (
                PolicyUnify(_address("a", "age"), _address("b", "score")),
                "INCOMPATIBLE_UNIFY_ENDPOINTS",
            ),
            (
                PolicyUnify(_address("a", "age"), _address("a", "score")),
                "SELF_UNIFY_UNSUPPORTED",
            ),
        )
        for unify, code in cases:
            with self.subTest(code=code):
                policy = Policy("bad", PolicyAll((_occ("a"), _occ("b"), unify)))
                with self.assertRaises(PolicyError) as ctx:
                    compile_policy(policy, address_space=space)
                self.assertEqual(ctx.exception.code, code)

    def test_equal_unify_addresses_reject_during_construction(self) -> None:
        with self.assertRaises(PolicyError) as ctx:
            PolicyUnify(_address("a", "age"), _address("a", "age"))
        self.assertEqual(ctx.exception.code, "INVALID_UNIFY")

    def test_policy_aliases_exactly_cover_address_space(self) -> None:
        bundle = _person_bundle()
        with self.assertRaises(PolicyError) as extra:
            compile_policy(Policy("p", _occ("a")), address_space=_space(bundle, "a", "b"))
        self.assertEqual(extra.exception.code, "POLICY_OCCURRENCE_COVERAGE_MISMATCH")

        duplicate = Policy(
            "p",
            PolicyAll((_occ("a"), PolicyAny((_occ("a"), _occ("b"))))),
        )
        with self.assertRaises(PolicyError) as repeated:
            compile_policy(duplicate, address_space=_space(bundle, "a", "b"))
        self.assertEqual(repeated.exception.code, "DUPLICATE_POLICY_OCCURRENCE")

    def test_schema_staleness_and_reserved_namespace_reject_distinctly(self) -> None:
        left = _person_bundle()
        right = _person_bundle(schema_index=_index(unrelated=True))
        mixed = SemanticAddressSpace(
            (manage_rule_occurrence(left, "a"), manage_rule_occurrence(right, "b"))
        )
        with self.assertRaises(PolicyError) as schema:
            compile_policy(Policy("p", PolicyAll((_occ("a"), _occ("b")))), address_space=mixed)
        self.assertEqual(schema.exception.code, "POLICY_SCHEMA_MISMATCH")

        stale_bundle = _person_bundle()
        stale_space = _space(stale_bundle, "a")
        stale_bundle.rule.when[0].terms[0] = Var("$changed")
        with self.assertRaises(PolicyError) as stale:
            compile_policy(Policy("p", _occ("a")), address_space=stale_space)
        self.assertEqual(stale.exception.code, "MANAGED_OCCURRENCE_NOT_CURRENT")

        reserved = _person_bundle(rule_id="__factgraph_projection__authored")
        with self.assertRaises(PolicyError) as namespace:
            compile_policy(Policy("p", _occ("a")), address_space=_space(reserved, "a"))
        self.assertEqual(namespace.exception.code, "RESERVED_COMPILER_NAMESPACE")

    def test_branch_limit_accepts_1_and_32_but_rejects_33_before_lowering(self) -> None:
        bundle = _person_bundle()
        for count in (1, 32):
            aliases = tuple(f"p{index}" for index in range(count))
            root = _occ(aliases[0]) if count == 1 else PolicyAny(tuple(map(_occ, aliases)))
            compiled = compile_policy(Policy(f"p{count}", root), address_space=_space(bundle, *aliases))
            self.assertEqual(len(compiled.branches), count)

        aliases = tuple(f"p{index}" for index in range(33))
        with self.assertRaises(PolicyError) as ctx:
            compile_policy(
                Policy("p33", PolicyAny(tuple(map(_occ, aliases)))),
                address_space=_space(bundle, *aliases),
            )
        self.assertEqual(ctx.exception.code, "POLICY_DNF_BRANCH_LIMIT_EXCEEDED")
        self.assertEqual(ctx.exception.details, {"limit": 32, "projected_count": 33})

    def test_nested_branch_product_reports_projected_count(self) -> None:
        bundle = _person_bundle()
        left = tuple(f"a{index}" for index in range(6))
        right = tuple(f"b{index}" for index in range(6))
        root = PolicyAll((PolicyAny(tuple(map(_occ, left))), PolicyAny(tuple(map(_occ, right)))))
        with self.assertRaises(PolicyError) as ctx:
            compile_policy(Policy("p36", root), address_space=_space(bundle, *left, *right))
        self.assertEqual(ctx.exception.details["projected_count"], 36)

    def test_cross_occurrence_execution_variable_collision_rejects(self) -> None:
        index = _index()
        left = build_resolved_rule(
            id="left", when=(PredAtom("Person:exists", [Var("$b__x")]),),
            ports={"person": SemanticRulePort(Var("$b__x"), entity_identity("Person"))},
            schema_index=index,
        )
        right = build_resolved_rule(
            id="right", when=(PredAtom("Person:exists", [Var("$x")]),),
            ports={"person": SemanticRulePort(Var("$x"), entity_identity("Person"))},
            schema_index=index,
        )
        space = SemanticAddressSpace((
            manage_rule_occurrence(left, "a"), manage_rule_occurrence(right, "a__b"),
        ))

        with self.assertRaises(PolicyError) as ctx:
            compile_policy(
                Policy("collision", PolicyAll((_occ("a"), _occ("a__b")))),
                address_space=space,
            )
        self.assertEqual(ctx.exception.code, "POLICY_EXECUTION_VAR_COLLISION")
        self.assertEqual(ctx.exception.stage, "policy_lowering_adapter")


class PolicyComparisonCompileTests(unittest.TestCase):
    def test_compare_ast_is_canonical_and_only_an_all_constraint(self) -> None:
        left, right = _address("left", "age"), _address("right", "age")
        forward = PolicyCompare.eq(left, right)
        reversed_ = PolicyCompare.eq(right, left)

        self.assertEqual(forward, reversed_)
        self.assertEqual(forward.node_id, reversed_.node_id)
        self.assertEqual((forward.left, forward.right), (left, right))

        with self.assertRaises(PolicyError) as ctx:
            PolicyAny((_occ("left"), PolicyCompare.gt(left, right)))  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.code, "INVALID_POLICY_CONSTRAINT_SCOPE")

    def test_direct_scalar_compare_and_navigation_compile_to_total_condition_lineage(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "left", "right")
        direct = PolicyCompare.gt(_address("left", "age"), _address("right", "score"))
        navigation = PolicyCompare.gt(_nav("left"), _nav("right"))
        policy = Policy(
            "older_workers",
            PolicyAll((_occ("left"), _occ("right"), direct, navigation)),
            version="1",
        )

        compiled = compile_policy(policy, address_space=space, schema_index=_index())

        compare_nodes = {
            node.node_id: node for node in compiled.policy_structure.nodes if node.kind == "compare"
        }
        self.assertEqual(set(compare_nodes), {direct.node_id, navigation.node_id})
        direct_refs = next(
            item.lowered_refs
            for item in compiled.lineage.authored_nodes
            if item.node_id == direct.node_id
        )
        navigation_refs = next(
            item.lowered_refs
            for item in compiled.lineage.authored_nodes
            if item.node_id == navigation.node_id
        )
        self.assertEqual({ref.kind for ref in direct_refs}, {"policy_condition"})
        self.assertEqual({getattr(ref, "role", None) for ref in direct_refs}, {"compare"})
        self.assertEqual({ref.kind for ref in navigation_refs}, {"policy_condition"})
        self.assertEqual(
            {getattr(ref, "role", None) for ref in navigation_refs},
            {"left_field", "right_field", "compare"},
        )
        self.assertEqual(
            {
                ref.branch_id
                for refs in (direct_refs, navigation_refs)
                for ref in refs
            },
            {compiled.branches[0].branch_id},
        )

    def test_compare_requires_schema_and_rejects_invalid_navigation_or_endpoint(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "left", "right")
        comparison = PolicyCompare.gt(_nav("left"), _nav("right"))
        policy = Policy("older", PolicyAll((_occ("left"), _occ("right"), comparison)))

        with self.assertRaises(PolicyError) as no_index:
            compile_policy(policy, address_space=space)
        self.assertEqual(no_index.exception.code, "POLICY_SCHEMA_INDEX_REQUIRED")

        invalid_navigation = PolicyCompare.gt(
            PolicyFieldNavigation(_address("left", "age"), FieldPath("Person", "score")),
            _nav("right"),
        )
        with self.assertRaises(PolicyError) as invalid_nav:
            compile_policy(
                Policy("bad_navigation", PolicyAll((_occ("left"), _occ("right"), invalid_navigation))),
                address_space=space,
                schema_index=_index(),
            )
        self.assertEqual(invalid_nav.exception.code, "INVALID_POLICY_NAVIGATION")

        invalid_endpoint = PolicyCompare.gt(_address("left", "person"), _address("right", "age"))
        with self.assertRaises(PolicyError) as endpoint:
            compile_policy(
                Policy("bad_endpoint", PolicyAll((_occ("left"), _occ("right"), invalid_endpoint))),
                address_space=space,
                schema_index=_index(),
            )
        self.assertEqual(endpoint.exception.code, "UNSUPPORTED_POLICY_COMPARE_ENDPOINT")

    def test_compare_is_branch_total_or_explicitly_branch_local(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "common", "left", "right")
        partial = Policy(
            "partial_compare",
            PolicyAll((
                _occ("common"),
                PolicyAny((_occ("left"), _occ("right"))),
                PolicyCompare.gt(_nav("common"), _nav("left")),
            )),
        )
        with self.assertRaises(PolicyError) as partial_ctx:
            compile_policy(partial, address_space=space, schema_index=_index())
        self.assertEqual(partial_ctx.exception.code, "PARTIAL_BRANCH_CONSTRAINT")

        local = Policy(
            "local_compare",
            PolicyAny((
                PolicyAll((_occ("left"), _occ("right"), PolicyCompare.gt(_nav("left"), _nav("right")))),
                _occ("common"),
            )),
        )
        compiled = compile_policy(local, address_space=space, schema_index=_index())
        local_all = next(child for child in local.when.children if isinstance(child, PolicyAll))
        compare = next(node for node in local_all.children if isinstance(node, PolicyCompare))
        refs = next(item.lowered_refs for item in compiled.lineage.authored_nodes if item.node_id == compare.node_id)
        local_branch = next(
            branch
            for branch in compiled.branches
            if set(branch.authored_occurrence_aliases) == {"left", "right"}
        )
        self.assertEqual({ref.branch_id for ref in refs}, {local_branch.branch_id})

    def test_compare_rejects_mixed_scalar_domains_and_float_ordering(self) -> None:
        index, bundle = _comparison_types_bundle()
        space = _space(bundle, "left", "right")
        mixed = PolicyCompare.eq(_address("left", "count"), _address("right", "label"))
        with self.assertRaises(PolicyError) as mixed_ctx:
            compile_policy(
                Policy("mixed", PolicyAll((_occ("left"), _occ("right"), mixed))),
                address_space=space,
                schema_index=index,
            )
        self.assertEqual(mixed_ctx.exception.code, "INCOMPATIBLE_POLICY_COMPARE_DOMAIN")

        float_order = PolicyCompare.gt(_address("left", "ratio"), _address("right", "ratio"))
        with self.assertRaises(PolicyError) as ordering_ctx:
            compile_policy(
                Policy("float_order", PolicyAll((_occ("left"), _occ("right"), float_order))),
                address_space=space,
                schema_index=index,
            )
        self.assertEqual(ordering_ctx.exception.code, "UNSUPPORTED_POLICY_COMPARE_ORDERING")

    def test_literal_is_canonical_typed_and_sealed_into_compare_identity(self) -> None:
        literal = PolicyLiteral("int", 12)
        self.assertEqual(literal, PolicyLiteral("int", 12))
        self.assertNotEqual(literal, PolicyLiteral("int", 13))
        with self.assertRaises(PolicyError) as bool_ctx:
            PolicyLiteral("int", True)  # type: ignore[arg-type]
        self.assertEqual(bool_ctx.exception.code, "INVALID_POLICY_LITERAL")
        with self.assertRaises(PolicyError) as range_ctx:
            PolicyLiteral("time", 1 << 63)
        self.assertEqual(range_ctx.exception.code, "INVALID_POLICY_LITERAL")
        with self.assertRaises(PolicyError) as domain_ctx:
            PolicyLiteral("float64", 12)  # type: ignore[arg-type]
        self.assertEqual(domain_ctx.exception.code, "INVALID_POLICY_LITERAL")
        self.assertEqual(PolicyLiteral("string", "gold").value, "gold")
        self.assertIs(PolicyLiteral("bool", True).value, True)
        with self.assertRaises(PolicyError):
            PolicyLiteral("string", True)  # type: ignore[arg-type]
        with self.assertRaises(PolicyError):
            PolicyLiteral("bool", 1)  # type: ignore[arg-type]
        with self.assertRaises(PolicyError) as entity_ref_ctx:
            PolicyLiteral("entity_ref", "idref_v1:Person:not-a-canonical-digest")
        self.assertEqual(entity_ref_ctx.exception.code, "INVALID_POLICY_LITERAL")
        with self.assertRaises(PolicyError) as source_ctx:
            PolicyCompare.gt(PolicyLiteral("int", 1), PolicyLiteral("int", 2))
        self.assertEqual(source_ctx.exception.code, "INVALID_POLICY_COMPARE")

        bundle = _person_bundle()
        space = _space(bundle, "left")
        first = compile_policy(
            Policy(
                "adult",
                PolicyAll((_occ("left"), PolicyCompare.gt(_address("left", "age"), literal))),
                version="1",
            ),
            address_space=space,
            schema_index=_index(),
        )
        same = compile_policy(
            Policy(
                "adult",
                PolicyAll((_occ("left"), PolicyCompare.gt(_address("left", "age"), PolicyLiteral("int", 12)))),
                version="1",
            ),
            address_space=space,
            schema_index=_index(),
        )
        changed = compile_policy(
            Policy(
                "adult",
                PolicyAll((_occ("left"), PolicyCompare.gt(_address("left", "age"), PolicyLiteral("int", 13)))),
                version="1",
            ),
            address_space=space,
            schema_index=_index(),
        )
        self.assertEqual(first.policy_digest, same.policy_digest)
        self.assertEqual(first.policy_structure, same.policy_structure)
        self.assertEqual(
            first.policy_digest,
            "bc735da76871869bef325c6f23e01202920145b99ac078d0cbf98847ad91ff2c",
        )
        self.assertEqual(
            first.policy_structure.structure_digest,
            "a088bb29b9bbb0928b33b1aa34ec59b538111756feb8a6ca9b1cbe9f872d20cb",
        )
        self.assertEqual(
            PolicyCompare.gt(
                _address("left", "age"), PolicyLiteral("int", 12)
            ).node_id,
            "pn:9459f1a5ebec5a1bcad00f65ea182c8124cdef7a8116c9f0c22b64816d44e00d",
        )
        self.assertEqual(
            PolicyCompare.gt(
                _address("left", "age"), PolicyLiteral("time", 12)
            ).node_id,
            "pn:2a64f5fe73ffd9c8395eb5c491bb8afb0fdb1bab6525d5b562026c514cd7b894",
        )
        self.assertNotEqual(first.policy_digest, changed.policy_digest)
        self.assertNotEqual(first.policy_structure.structure_digest, changed.policy_structure.structure_digest)
        compare_refs = next(
            item.lowered_refs
            for item in first.lineage.authored_nodes
            if item.node_kind == "compare"
        )
        self.assertEqual({getattr(ref, "role", None) for ref in compare_refs}, {"compare"})
        condition = first._policy_conditions[0]
        self.assertEqual(condition.atom, CmpAtom("gt", condition.atom.lhs, Const(12)))

    def test_string_bool_and_entity_ref_equality_literals_compile(self) -> None:
        index, bundle = _comparison_types_bundle()
        space = _space(bundle, "item")
        string_compare = PolicyCompare.eq(
            _address("item", "label"), PolicyLiteral("string", "gold")
        )
        bool_compare = PolicyCompare.ne(
            _address("item", "active"), PolicyLiteral("bool", False)
        )
        compiled = compile_policy(
            Policy(
                "literal-equality",
                PolicyAll((_occ("item"), string_compare, bool_compare)),
            ),
            address_space=space,
            schema_index=index,
        )
        atoms = tuple(condition.atom for condition in compiled._policy_conditions)
        self.assertTrue(any(atom == CmpAtom("eq", atom.lhs, Const("gold")) for atom in atoms))
        self.assertTrue(any(atom == CmpAtom("ne", atom.lhs, Const(False)) for atom in atoms))

        person_index = _index(unrelated=True)
        person_bundle = _person_bundle(schema_index=person_index)
        alice = encode_entity_ref(
            EntityRef("Person", {"employee_id": "alice"}), index=person_index
        )
        entity_compiled = compile_policy(
            Policy(
                "specific-person",
                PolicyAll(
                    (
                        _occ("person"),
                        PolicyCompare.eq(
                            _address("person"),
                            PolicyLiteral("entity_ref", alice),
                        ),
                    )
                ),
            ),
            address_space=_space(person_bundle, "person"),
            schema_index=person_index,
        )
        self.assertEqual(entity_compiled._policy_conditions[0].atom.rhs, Const(alice))

        unrelated_ref = encode_entity_ref(
            EntityRef("Unrelated", {"code": "x"}), index=person_index
        )
        with self.assertRaises(PolicyError) as mismatch:
            compile_policy(
                Policy(
                    "wrong-entity-type",
                    PolicyAll(
                        (
                            _occ("person"),
                            PolicyCompare.eq(
                                _address("person"),
                                PolicyLiteral("entity_ref", unrelated_ref),
                            ),
                        )
                    ),
                ),
                address_space=_space(person_bundle, "person"),
                schema_index=person_index,
            )
        self.assertEqual(mismatch.exception.code, "INCOMPATIBLE_POLICY_ENTITY_REF_TYPE")

    def test_new_literal_domains_keep_ordering_and_float_closed(self) -> None:
        index, bundle = _comparison_types_bundle()
        space = _space(bundle, "item")
        for port, literal in (
            ("label", PolicyLiteral("string", "gold")),
            ("active", PolicyLiteral("bool", True)),
        ):
            with self.subTest(port=port):
                with self.assertRaises(PolicyError) as ordering:
                    compile_policy(
                        Policy(
                            f"bad-{port}-ordering",
                            PolicyAll(
                                (
                                    _occ("item"),
                                    PolicyCompare.gt(_address("item", port), literal),
                                )
                            ),
                        ),
                        address_space=space,
                        schema_index=index,
                    )
                self.assertEqual(
                    ordering.exception.code, "UNSUPPORTED_POLICY_COMPARE_ORDERING"
                )
        with self.assertRaises(PolicyError):
            PolicyLiteral("float64", 1.0)  # type: ignore[arg-type]

    def test_literal_requires_matching_domain_and_preserves_branch_totality(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "common", "left", "right")
        with self.assertRaises(PolicyError) as mismatch_ctx:
            compile_policy(
                Policy(
                    "bad-time",
                    PolicyAll((_occ("common"), PolicyCompare.gt(_address("common", "age"), PolicyLiteral("time", 1)))),
                ),
                address_space=_space(bundle, "common"),
                schema_index=_index(),
            )
        self.assertEqual(mismatch_ctx.exception.code, "INCOMPATIBLE_POLICY_COMPARE_DOMAIN")

        partial = Policy(
            "partial-literal",
            PolicyAll((
                _occ("common"),
                PolicyAny((_occ("left"), _occ("right"))),
                PolicyCompare.gt(_address("left", "age"), PolicyLiteral("int", 12)),
            )),
        )
        with self.assertRaises(PolicyError) as partial_ctx:
            compile_policy(partial, address_space=space, schema_index=_index())
        self.assertEqual(partial_ctx.exception.code, "PARTIAL_BRANCH_CONSTRAINT")
        self.assertEqual(partial_ctx.exception.details["not_guaranteed_aliases"], ["left"])

        navigation = PolicyCompare.gt(_nav("common"), PolicyLiteral("int", 12))
        compiled = compile_policy(
            Policy("nav-literal", PolicyAll((_occ("common"), navigation))),
            address_space=_space(bundle, "common"),
            schema_index=_index(),
        )
        refs = next(item.lowered_refs for item in compiled.lineage.authored_nodes if item.node_id == navigation.node_id)
        self.assertEqual({getattr(ref, "role", None) for ref in refs}, {"left_field", "compare"})


class PolicyAdmissionTests(unittest.TestCase):
    def test_predicate_and_non_aggregate_comparison_are_admitted(self) -> None:
        value = Var("$age")
        bundle = _person_bundle(extra_atoms=(CmpAtom("ge", value, Const(18)),))
        compiled = compile_policy(Policy("adult", _occ("a")), address_space=_space(bundle, "a"))
        self.assertEqual(len(compiled.branches), 1)

    def test_not_in_builtin_and_aggregate_are_rejected_at_admission(self) -> None:
        person, value = Var("$person"), Var("$age")
        unsupported = (
            NotAtom(AndExpr([PredAtom("person:blocked", [person])])),
            InAtom(value, [Const(18), Const(21)]),
            BuiltinAtom("addc", [value, Const(1)]),
            PredAtom(
                "aggregate_predicate",
                [AggregateAtom("count", None, [PredAtom("Person:exists", [person])])],
            ),
            CmpAtom(
                "eq",
                value,
                AggregateAtom("count", None, [PredAtom("Person:exists", [person])]),
            ),
        )
        for index, atom in enumerate(unsupported):
            with self.subTest(atom=type(atom).__name__):
                bundle = _person_bundle(rule_id=f"unsupported_{index}", extra_atoms=(atom,))
                with self.assertRaises(PolicyError) as ctx:
                    compile_policy(Policy("p", _occ("a")), address_space=_space(bundle, "a"))
                self.assertEqual(ctx.exception.code, "UNSUPPORTED_MANAGED_RULE_CAPABILITY")
                self.assertEqual(ctx.exception.stage, "policy_admission")


class PolicyLineageTests(unittest.TestCase):
    def test_authored_structure_preserves_nested_topology_and_unify_endpoints(self) -> None:
        bundle = _person_bundle()
        policy = Policy(
            "structure",
            PolicyAll((
                _occ("a"),
                PolicyAny((
                    PolicyAll((_occ("b"), _occ("c"), _unify("b", "c"))),
                    _occ("d"),
                )),
            )),
        )

        compiled = compile_policy(
            policy, address_space=_space(bundle, "a", "b", "c", "d"),
        )
        structure = compiled.policy_structure
        by_id = {node.node_id: node for node in structure.nodes}

        self.assertEqual(structure.root_node_id, policy.when.node_id)
        self.assertEqual(by_id[structure.root_node_id].kind, "all")
        self.assertEqual(
            by_id[structure.root_node_id].child_node_ids,
            tuple(child.node_id for child in policy.when.children),
        )
        occurrence_aliases = {
            node.occurrence_alias for node in structure.nodes if node.kind == "occurrence"
        }
        self.assertEqual(occurrence_aliases, {"a", "b", "c", "d"})
        unify = next(node for node in structure.nodes if node.kind == "unify")
        self.assertEqual((unify.left, unify.right), (_address("b"), _address("c")))
        self.assertEqual(
            {node.node_id: node.kind for node in structure.nodes},
            {node.node_id: node.node_kind for node in compiled.lineage.authored_nodes},
        )

    def test_policy_structure_rejects_malformed_shape_and_splicing(self) -> None:
        occurrence = _occ("a")
        valid = PolicyStructureNodeV0(
            occurrence.node_id, "occurrence", occurrence_alias="a",
        )
        with self.assertRaises(PolicyError):
            PolicyStructureNodeV0(occurrence.node_id, "occurrence", occurrence_alias="b")
        with self.assertRaises(PolicyError):
            PolicyStructureV0("pn:absent", (valid,))

        bundle = _person_bundle()
        space = _space(bundle, "a", "b")
        conjunctive = compile_policy(
            Policy("same", PolicyAll((_occ("a"), _occ("b")))), address_space=space,
        )
        disjunctive = compile_policy(
            Policy("same", PolicyAny((_occ("a"), _occ("b")))), address_space=space,
        )
        with self.assertRaises(PolicyError) as sealed:
            replace(conjunctive, policy_structure=disjunctive.policy_structure)
        self.assertEqual(sealed.exception.code, "COMPILED_POLICY_INTEGRITY_MISMATCH")
        with self.assertRaises(PolicyError) as self_consistent_digest:
            replace(
                conjunctive,
                policy_structure=disjunctive.policy_structure,
                policy_digest=disjunctive.policy_digest,
            )
        self.assertEqual(
            self_consistent_digest.exception.code, "COMPILED_POLICY_INTEGRITY_MISMATCH",
        )

    def test_public_lineage_dtos_reject_malformed_or_non_total_shapes(self) -> None:
        invalid_refs = (
            lambda: PolicyLoweredRef("bogus", "c0"),  # type: ignore[arg-type]
            lambda: PolicyLoweredRef("branch", ""),
            lambda: PolicyLoweredRef("branch", "c0", occurrence_alias="extra"),
            lambda: PolicyLoweredRef(
                "body_atom", "c0", "a", source_index=-1, lowered_index=0
            ),
            lambda: PolicyLoweredRef("unify", "c0"),
        )
        for factory in invalid_refs:
            with self.subTest(factory=factory):
                with self.assertRaises(PolicyError) as ctx:
                    factory()
                self.assertEqual(ctx.exception.code, "INVALID_POLICY_LINEAGE")

        branch = PolicyLoweredRef("branch", "c0")
        with self.assertRaises(PolicyError):
            PolicyNodeLineage("", "occurrence", (branch,))
        with self.assertRaises(PolicyError):
            PolicyNodeLineage("pn:x", "bogus", (branch,))  # type: ignore[arg-type]
        with self.assertRaises(PolicyError):
            PolicyNodeLineage("pn:x", "occurrence", ())
        node = PolicyNodeLineage("pn:x", "occurrence", (branch,))
        with self.assertRaises(PolicyError):
            PolicyLineage((), ())
        with self.assertRaises(PolicyError):
            PolicyLineage((node,), ((PolicyLoweredRef("branch", "c1"), ("pn:x",)),))
        other_ref = PolicyLoweredRef("branch", "c1")
        other_node = PolicyNodeLineage("pn:y", "occurrence", (other_ref,))
        with self.assertRaises(PolicyError):
            PolicyLineage(
                (node, other_node),
                ((branch, ("pn:y",)), (other_ref, ("pn:x",))),
            )

    def test_runtime_artifact_dtos_reject_empty_inventory(self) -> None:
        with self.assertRaises(ValueError):
            PolicyRulePin("", "rule", None, "digest", "contract")
        with self.assertRaises(ValueError):
            PolicyCompiledBranch("c0", (), ())
        bundle = _person_bundle()
        compiled = compile_policy(Policy("p", _occ("a")), address_space=_space(bundle, "a"))
        with self.assertRaises(ValueError):
            replace(compiled, branches=())

    def test_compiled_policy_rejects_cross_artifact_splicing(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b")
        conjunctive = compile_policy(
            Policy("all", PolicyAll((_occ("a"), _occ("b")))), address_space=space,
        )
        disjunctive = compile_policy(
            Policy("any", PolicyAny((_occ("a"), _occ("b")))), address_space=space,
        )

        with self.assertRaises(PolicyError) as ctx:
            replace(
                conjunctive,
                branches=disjunctive.branches,
                _body_plan=disjunctive._body_plan,
            )
        self.assertEqual(ctx.exception.code, "COMPILED_POLICY_INTEGRITY_MISMATCH")

    def test_alias_rewrite_survives_generated_name_collision(self) -> None:
        bundle = _person_bundle()
        aliases = ("d", "d__c0", "other")
        policy = Policy(
            "collision",
            PolicyAll((_occ("d"), PolicyAny((_occ("d__c0"), _occ("other"))))),
        )
        compiled = compile_policy(policy, address_space=_space(bundle, *aliases))
        copied = [binding for binding in compiled._body_plan.occurrence_map if binding.authored_alias == "d"]

        self.assertEqual(len(copied), 2)
        self.assertNotIn("d", {binding.alias for binding in copied})
        self.assertEqual(len({binding.alias for binding in copied}), 2)
        self.assertNotIn("d__c0", {binding.alias for binding in copied})
        self.assertEqual(
            {alias for branch in compiled.branches for alias in branch.authored_occurrence_aliases},
            set(aliases),
        )

    def test_lineage_is_total_in_both_directions(self) -> None:
        bundle = _person_bundle()
        policy = Policy(
            "lineage",
            PolicyAll(
                (
                    _occ("d"),
                    PolicyAny(
                        (
                            PolicyAll((_occ("a"), _occ("b"), _unify("a", "b"))),
                            _occ("c"),
                        )
                    ),
                )
            ),
        )
        compiled = compile_policy(policy, address_space=_space(bundle, "a", "b", "c", "d"))
        forward = {
            ref
            for authored_node in compiled.lineage.authored_nodes
            for ref in authored_node.lowered_refs
        }
        reverse = {ref for ref, _origins in compiled.lineage.lowered_origins}

        self.assertEqual(forward, reverse)
        self.assertTrue(all(node.lowered_refs for node in compiled.lineage.authored_nodes))
        self.assertTrue(all(origins for _ref, origins in compiled.lineage.lowered_origins))
        self.assertEqual(
            len([ref for ref in reverse if ref.kind == "branch"]),
            len(compiled.branches),
        )
        self.assertEqual(
            len([ref for ref in reverse if ref.kind == "body_atom"]),
            sum(len(branch.body_atoms) for branch in compiled._body_plan.branches),
        )
        self.assertEqual(len([ref for ref in reverse if ref.kind == "unify"]), 1)

    def test_commutative_reordering_preserves_digest_branches_and_lineage(self) -> None:
        bundle = _person_bundle()
        space = _space(bundle, "a", "b", "c")
        first = Policy(
            "stable",
            PolicyAll((_occ("a"), PolicyAny((_occ("b"), _occ("c"))))),
            version="1",
        )
        second = Policy(
            "stable",
            PolicyAll((PolicyAny((_occ("c"), _occ("b"))), _occ("a"))),
            version="1",
        )

        left = compile_policy(first, address_space=space)
        right = compile_policy(second, address_space=space)
        self.assertEqual(left.policy_digest, right.policy_digest)
        self.assertEqual(left.policy_structure, right.policy_structure)
        self.assertEqual(
            left.policy_structure.structure_digest,
            right.policy_structure.structure_digest,
        )
        self.assertEqual(left.branches, right.branches)
        self.assertEqual(left.lineage, right.lineage)


if __name__ == "__main__":
    unittest.main()
