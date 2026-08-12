from __future__ import annotations

import unittest

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_policy,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyError,
    PolicyOccurrence,
    PolicyUnify,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
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


def _occ(alias: str) -> PolicyOccurrence:
    return PolicyOccurrence(alias)


def _address(alias: str, port: str = "person") -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _unify(left: str, right: str, port: str = "person") -> PolicyUnify:
    return PolicyUnify(_address(left, port), _address(right, port))


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
        self.assertEqual(left.branches, right.branches)
        self.assertEqual(left.lineage, right.lineage)


if __name__ == "__main__":
    unittest.main()
