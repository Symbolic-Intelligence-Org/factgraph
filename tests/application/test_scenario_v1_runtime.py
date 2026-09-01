from __future__ import annotations

import unittest
from copy import deepcopy

from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntityRef, EntitySelector, FieldPath, ProtocolShapeError
from factgraph.application.protocol.scenario_v1 import (
    EvidenceScopeV1,
    ResolvedScenarioOperationV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
)
from factgraph.application.scenario_v1_runtime import (
    ScenarioResolutionErrorV1,
    apply_evidence_scope_v1,
    effective_world_to_relation_v1,
    resolve_scenario_v1,
    select_dependency_relation_v1,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore

_DIGEST = "sha256:" + "a" * 64


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    skills: list[str] = Field()


class Country(Entity):
    code: str = Identity()


class Resident(Entity):
    resident_id: str = Identity()
    lives_in: Country = Field()


class ScenarioV1RuntimeTests(unittest.TestCase):
    def _fixture(self, *, membership: bool = False, single_membership: bool = False):
        graph = SDKStore([Person])
        schema_ir = deepcopy(graph.schema_ir)
        if membership:
            schema_ir["predicates"].append(
                {
                    "pred_id": "membership",
                    "owner_type": "Person",
                    "arity": 2,
                    "arg_specs": [
                        {"name": "person", "type_domain": "entity_ref"},
                        {"name": "group", "type_domain": "string"},
                    ],
                    "cardinality": "single" if single_membership else "multi",
                    "group_key_indexes": [0],
                }
            )
        index = build_schema_index(schema_ir)
        alice = resolve_selector(
            EntitySelector(entity_type="Person", identity={"employee_id": "alice"}), index=index
        )
        bob = resolve_selector(
            EntitySelector(entity_type="Person", identity={"employee_id": "bob"}), index=index
        )
        assert alice.encoded_ref is not None and bob.encoded_ref is not None
        info = entity_info(index, "Person")
        relation = {
            info.exists_predicate_id: (ProjectedFact("exists-alice", (alice.encoded_ref,)),),
            info.identity_predicates["employee_id"].pred_id: (
                ProjectedFact("id-alice", (alice.encoded_ref, "alice")),
            ),
            field_predicate(index, "Person", "age").pred_id: (
                ProjectedFact("age-alice", (alice.encoded_ref, 22)),
            ),
            field_predicate(index, "Person", "skills").pred_id: (
                ProjectedFact("skill-python", (alice.encoded_ref, "python")),
                ProjectedFact("skill-sql", (alice.encoded_ref, "sql")),
            ),
        }
        if membership:
            relation["membership"] = (
                ProjectedFact("member-alice", (alice.encoded_ref, "engineering")),
            )
        return (
            index,
            relation,
            EntityRef("Person", {"employee_id": "alice"}, alice.encoded_ref),
            EntityRef("Person", {"employee_id": "bob"}, bob.encoded_ref),
        )

    def _resolve(self, spec: ScenarioSpecV1, *, membership: bool = False):
        index, relation, alice, bob = self._fixture(membership=membership)
        return (
            resolve_scenario_v1(
                spec,
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            ),
            index,
            relation,
            alice,
            bob,
        )

    def test_constructors_canonicalize_unordered_spec_and_exact_members(self) -> None:
        alice = EntityRef("Person", {"employee_id": "alice"})
        skills = FieldPath("Person", "skills")
        one = ScenarioEnsureMemberV1(
            "one",
            alice,
            skills,
            ScenarioValueV1.from_raw("string", "python"),
            origin_refs=("z", "a", "z"),
        )
        two = ScenarioSetExactMembersV1(
            "two",
            alice,
            skills,
            (
                ScenarioValueV1.from_raw("string", "sql"),
                ScenarioValueV1.from_raw("string", "python"),
            ),
        )
        left = ScenarioSpecV1((one, two))
        right = ScenarioSpecV1((two, one))
        self.assertEqual(left.spec_digest, right.spec_digest)
        self.assertEqual(one.origin_refs, ("a", "z"))
        self.assertEqual(tuple(value.value for value in two.values), ("python", "sql"))
        with self.assertRaisesRegex(ValueError, "premise_id"):
            ScenarioSpecV1(
                (
                    one,
                    ScenarioEnsureMemberV1(
                        "one", alice, skills, ScenarioValueV1.from_raw("string", "go")
                    ),
                )
            )

    def test_without_is_exact_local_and_evidence_ignore_is_only_exclusion(self) -> None:
        index, relation, alice, _ = self._fixture()
        admitted = apply_evidence_scope_v1(relation, EvidenceScopeV1(("skill-sql",)))
        self.assertEqual(admitted.excluded_assertion_ids, ("skill-sql",))
        admitted_world = resolve_scenario_v1(
            ScenarioSpecV1(()),
            schema_index=index,
            baseline_relation=admitted.relation,
            base_view_digest=_DIGEST,
            admissibility_digest=admitted.admissibility_digest,
        )
        self.assertEqual(admitted_world.effective_world.closure.mode, "open")

        without = ScenarioSpecV1(
            (
                ScenarioWithoutValueV1(
                    "without-sql",
                    alice,
                    FieldPath("Person", "skills"),
                    ScenarioValueV1.from_raw("string", "sql"),
                ),
            )
        )
        resolved = resolve_scenario_v1(
            without,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        self.assertEqual(resolved.effective_world.closure.mode, "exact_local")
        self.assertEqual(resolved.effective_world.closure.targets[0].kind, "member")
        relation_again = effective_world_to_relation_v1(resolved.effective_world)
        skill_rows = relation_again[field_predicate(index, "Person", "skills").pred_id]
        self.assertEqual(tuple(row.fact_tuple[1] for row in skill_rows), ("python",))
        self.assertFalse(hasattr(admitted, "closure"))

    def test_without_assertion_is_sdk_local_and_binds_one_admitted_witness(self) -> None:
        index, relation, alice, _ = self._fixture()
        spec = ScenarioSpecV1((ScenarioWithoutAssertionV1("remove-sql", "skill-sql"),))
        resolved = resolve_scenario_v1(
            spec,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        skills_id = field_predicate(index, "Person", "skills").pred_id
        skills = effective_world_to_relation_v1(resolved.effective_world)[skills_id]
        self.assertEqual(tuple(row.fact_tuple for row in skills), ((alice.encoded_ref, "python"),))
        operation = next(
            item for item in resolved.effective_world.operations if item.kind == "without_assertion"
        )
        self.assertIsNone(operation.entity_ref)
        self.assertEqual(operation.assertion_id, "skill-sql")
        self.assertEqual(
            tuple(value.to_raw() for value in operation.values), (alice.encoded_ref, "sql")
        )
        target = resolved.effective_world.closure.targets[0]
        self.assertEqual(
            (target.kind, target.predicate_id, target.assertion_id),
            ("assertion", skills_id, "skill-sql"),
        )

        # An evidence admission exclusion removes a witness from input, but it
        # must never acquire the Scenario operation or the exact closure.
        admitted = apply_evidence_scope_v1(relation, EvidenceScopeV1(("skill-sql",)))
        ignored = resolve_scenario_v1(
            ScenarioSpecV1(()),
            schema_index=index,
            baseline_relation=admitted.relation,
            base_view_digest=_DIGEST,
            admissibility_digest=admitted.admissibility_digest,
        )
        self.assertEqual(ignored.effective_world.closure.mode, "open")
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "not uniquely admitted"):
            resolve_scenario_v1(
                spec,
                schema_index=index,
                baseline_relation=admitted.relation,
                base_view_digest=_DIGEST,
                admissibility_digest=admitted.admissibility_digest,
            )

    def test_scalar_multi_and_ephemeral_resolution_have_order_free_conflicts(self) -> None:
        index, relation, alice, bob = self._fixture()
        spec = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "age", alice, FieldPath("Person", "age"), ScenarioValueV1.from_raw("int", 35)
                ),
                ScenarioSetExactMembersV1(
                    "skills",
                    alice,
                    FieldPath("Person", "skills"),
                    (ScenarioValueV1.from_raw("string", "go"),),
                ),
                ScenarioCreateEphemeralEntityV1("create-bob", bob),
                ScenarioSetEffectiveValueV1(
                    "bob-age", bob, FieldPath("Person", "age"), ScenarioValueV1.from_raw("int", 19)
                ),
            )
        )
        resolved = resolve_scenario_v1(
            spec,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        output = effective_world_to_relation_v1(resolved.effective_world)
        age_pred = field_predicate(index, "Person", "age").pred_id
        self.assertIn((bob.encoded_ref, 19), tuple(row.fact_tuple for row in output[age_pred]))
        self.assertEqual(resolved.effective_world.closure.mode, "exact_local")
        self.assertIn(
            "create_ephemeral_entity",
            tuple(item.kind for item in resolved.effective_world.operations),
        )
        conflict = ScenarioSpecV1(
            (
                ScenarioSetEffectiveValueV1(
                    "a", alice, FieldPath("Person", "age"), ScenarioValueV1.from_raw("int", 30)
                ),
                ScenarioSetEffectiveValueV1(
                    "b", alice, FieldPath("Person", "age"), ScenarioValueV1.from_raw("int", 31)
                ),
            )
        )
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "conflicting scalar"):
            resolve_scenario_v1(
                conflict,
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )
        compatible = ScenarioSpecV1(
            (
                ScenarioWithoutFieldV1("clear", alice, FieldPath("Person", "age")),
                ScenarioSetEffectiveValueV1(
                    "new", alice, FieldPath("Person", "age"), ScenarioValueV1.from_raw("int", 30)
                ),
            )
        )
        normalized, *_ = self._resolve(compatible)
        self.assertEqual(
            tuple(item.kind for item in normalized.effective_world.operations),
            ("set_effective_value",),
        )

        # A field clear plus an affirmative membership and a removal of that
        # same membership has no order-independent interpretation.
        triple_conflict = ScenarioSpecV1(
            (
                ScenarioWithoutFieldV1("clear", alice, FieldPath("Person", "skills")),
                ScenarioEnsureMemberV1(
                    "ensure-sql",
                    alice,
                    FieldPath("Person", "skills"),
                    ScenarioValueV1.from_raw("string", "sql"),
                ),
                ScenarioWithoutValueV1(
                    "without-sql",
                    alice,
                    FieldPath("Person", "skills"),
                    ScenarioValueV1.from_raw("string", "sql"),
                ),
            )
        )
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "ensure member conflicts"):
            resolve_scenario_v1(
                triple_conflict,
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

    def test_exact_set_closure_is_not_field_empty_closure(self) -> None:
        index, relation, alice, _ = self._fixture()
        spec = ScenarioSpecV1(
            (
                ScenarioSetExactMembersV1(
                    "exact-skills",
                    alice,
                    FieldPath("Person", "skills"),
                    (ScenarioValueV1.from_raw("string", "go"),),
                ),
            )
        )
        resolved = resolve_scenario_v1(
            spec,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        target = resolved.effective_world.closure.targets[0]
        self.assertEqual(target.kind, "exact_set")
        self.assertEqual(tuple(member.to_raw() for member in target.members), ("go",))
        self.assertIsNone(target.value)

    def test_relation_and_entity_operations_have_exact_local_boundary(self) -> None:
        index, relation, alice, _ = self._fixture(membership=True)
        relation_spec = ScenarioSpecV1(
            (
                ScenarioEnsureRelationV1(
                    "ensure",
                    "membership",
                    (
                        ScenarioValueV1.from_raw("entity_ref", alice.encoded_ref),
                        ScenarioValueV1.from_raw("string", "security"),
                    ),
                ),
                ScenarioWithoutRelationV1("remove", "membership"),
            )
        )
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "without relation conflicts"):
            resolve_scenario_v1(
                relation_spec,
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

        remove = ScenarioSpecV1((ScenarioWithoutRelationV1("remove", "membership"),))
        removed = resolve_scenario_v1(
            remove,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        self.assertEqual(effective_world_to_relation_v1(removed.effective_world)["membership"], ())
        self.assertEqual(removed.effective_world.closure.targets[0].kind, "relation")
        entity_remove = ScenarioSpecV1((ScenarioWithoutEntityV1("remove-alice", alice),))
        entity_result = resolve_scenario_v1(
            entity_remove,
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        self.assertEqual(entity_result.effective_world.closure.targets[0].kind, "entity")
        self.assertFalse(
            any(
                row.fact_tuple and row.fact_tuple[0] == alice.encoded_ref
                for rows in effective_world_to_relation_v1(entity_result.effective_world).values()
                for row in rows
            )
        )
        with self.assertRaisesRegex(
            ScenarioResolutionErrorV1, "not an allowed extensional relation"
        ):
            resolve_scenario_v1(
                ScenarioSpecV1(
                    (
                        ScenarioEnsureRelationV1(
                            "bad",
                            "person:age",
                            (
                                ScenarioValueV1.from_raw("entity_ref", alice.encoded_ref),
                                ScenarioValueV1.from_raw("int", 25),
                            ),
                        ),
                    )
                ),
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

    def test_ensure_relation_accepts_schema_declared_entity_relation_field(self) -> None:
        graph = SDKStore([Country, Resident])
        index = build_schema_index(graph.schema_ir)
        resident = resolve_selector(
            EntitySelector(entity_type="Resident", identity={"resident_id": "alice"}),
            index=index,
        )
        country = resolve_selector(
            EntitySelector(entity_type="Country", identity={"code": "de"}),
            index=index,
        )
        assert resident.encoded_ref is not None and country.encoded_ref is not None
        resident_info = entity_info(index, "Resident")
        country_info = entity_info(index, "Country")
        predicate_id = field_predicate(index, "Resident", "lives_in").pred_id
        relation = {
            resident_info.exists_predicate_id: (
                ProjectedFact("exists-resident", (resident.encoded_ref,)),
            ),
            country_info.exists_predicate_id: (
                ProjectedFact("exists-country", (country.encoded_ref,)),
            ),
            predicate_id: (),
        }

        resolved = resolve_scenario_v1(
            ScenarioSpecV1(
                (
                    ScenarioEnsureRelationV1(
                        "assume-residence",
                        predicate_id,
                        (
                            ScenarioValueV1.from_raw("entity_ref", resident.encoded_ref),
                            ScenarioValueV1.from_raw("entity_ref", country.encoded_ref),
                        ),
                    ),
                )
            ),
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )

        self.assertEqual(
            effective_world_to_relation_v1(resolved.effective_world)[predicate_id][0].fact_tuple,
            (resident.encoded_ref, country.encoded_ref),
        )

    def test_relation_rejects_removed_or_invisible_entities_and_allows_created_entity(self) -> None:
        index, relation, alice, bob = self._fixture(membership=True)
        security = ScenarioValueV1.from_raw("string", "security")
        alice_ref = ScenarioValueV1.from_raw("entity_ref", alice.encoded_ref)
        bob_ref = ScenarioValueV1.from_raw("entity_ref", bob.encoded_ref)
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "conflicts with without entity"):
            resolve_scenario_v1(
                ScenarioSpecV1(
                    (
                        ScenarioWithoutEntityV1("remove-alice", alice),
                        ScenarioEnsureRelationV1(
                            "readd-alice", "membership", (alice_ref, security)
                        ),
                    )
                ),
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "not visible"):
            resolve_scenario_v1(
                ScenarioSpecV1(
                    (ScenarioEnsureRelationV1("unseen-bob", "membership", (bob_ref, security)),)
                ),
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

        create_then_add = (
            ScenarioCreateEphemeralEntityV1("create-bob", bob),
            ScenarioEnsureRelationV1("add-bob", "membership", (bob_ref, security)),
        )
        add_then_create = tuple(reversed(create_then_add))
        first = resolve_scenario_v1(
            ScenarioSpecV1(create_then_add),
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        second = resolve_scenario_v1(
            ScenarioSpecV1(add_then_create),
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_DIGEST,
            admissibility_digest=_DIGEST,
        )
        self.assertEqual(first.effective_world.world_digest, second.effective_world.world_digest)

        # A relation tuple cannot acquire entity existence through a later
        # Store lookup; the dependency relation must carry that fact itself.
        no_exists = dict(relation)
        no_exists.pop(entity_info(index, "Person").exists_predicate_id)
        with self.assertRaisesRegex(
            ScenarioResolutionErrorV1, "lacks a sealed existence dependency"
        ):
            resolve_scenario_v1(
                ScenarioSpecV1(
                    (
                        ScenarioEnsureRelationV1(
                            "no-live-fallback", "membership", (alice_ref, security)
                        ),
                    )
                ),
                schema_index=index,
                baseline_relation=no_exists,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

    def test_single_relation_group_key_rejects_implicit_replacement(self) -> None:
        index, relation, alice, _ = self._fixture(membership=True, single_membership=True)
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "would replace"):
            resolve_scenario_v1(
                ScenarioSpecV1(
                    (
                        ScenarioEnsureRelationV1(
                            "replace-membership",
                            "membership",
                            (
                                ScenarioValueV1.from_raw("entity_ref", alice.encoded_ref),
                                ScenarioValueV1.from_raw("string", "security"),
                            ),
                        ),
                    )
                ),
                schema_index=index,
                baseline_relation=relation,
                base_view_digest=_DIGEST,
                admissibility_digest=_DIGEST,
            )

    def test_resolved_assertion_operation_cannot_be_malformed_as_relation_or_partial_mask(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ProtocolShapeError, "relation operation must not carry assertion"
        ):
            ResolvedScenarioOperationV1(
                "without_relation",
                None,
                None,
                "membership",
                None,
                assertion_id="unexpected",
                premise_ids=("remove",),
            )
        with self.assertRaisesRegex(ProtocolShapeError, "mask exactly"):
            ResolvedScenarioOperationV1(
                "without_assertion",
                None,
                None,
                "membership",
                None,
                assertion_id="assertion-1",
                values=(ScenarioValueV1.from_raw("string", "x"),),
                premise_ids=("remove",),
                masked_witness_ids=("some-other-assertion",),
            )

    def test_dependency_subset_is_explicit_and_never_treated_as_empty(self) -> None:
        _index, relation, _, _ = self._fixture()
        chosen = tuple(sorted(relation))
        subset = select_dependency_relation_v1(relation, dependency_predicate_ids=chosen)
        self.assertEqual(tuple(subset), chosen)
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "omits required dependency"):
            select_dependency_relation_v1(
                relation, dependency_predicate_ids=tuple(sorted((*chosen, "unknown:predicate")))
            )

    def test_duplicate_assertion_witness_is_rejected_before_scenario_resolution(self) -> None:
        index, relation, _, _ = self._fixture()
        duplicated = dict(relation)
        age_predicate_id = field_predicate(index, "Person", "age").pred_id
        age_rows = tuple(duplicated[age_predicate_id])
        duplicated[age_predicate_id] = age_rows + (
            ProjectedFact("skill-sql", age_rows[0].fact_tuple),
        )
        with self.assertRaisesRegex(ScenarioResolutionErrorV1, "repeats assertion id"):
            apply_evidence_scope_v1(duplicated, EvidenceScopeV1())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
