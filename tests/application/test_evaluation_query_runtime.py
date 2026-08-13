from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import UUID

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    encode_entity_ref,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    EntityRef,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQueryError,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
    EvaluationQuerySelection,
    FieldPath,
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyOccurrence,
    Rule,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.rule_expr_lowering import (
    _materialize_native_derivation_plan,
    _validate_rule_expr_head_foundation,
    probe_seed_vars_by_head_port,
)
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


class Other(Entity):
    code: str = Identity()


class Record(Entity):
    record_id: str = Identity()
    marker: UUID = Field()
    payload: bytes = Field()
    label: str = Field()


def _index(*, include_other: bool = False):
    entities = [Person, Other] if include_other else [Person]
    return build_schema_index(
        compile_schema_from_classes(entities, generated_at="2026-08-12T00:00:00Z")
    )


def _bundle(index=None):
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
        schema_index=_index() if index is None else index,
    )


def _space(bundle, *aliases: str):
    return SemanticAddressSpace(tuple(manage_rule_occurrence(bundle, alias) for alias in aliases))


def _address(alias: str, port: str):
    return SemanticPortAddress(alias, port)


def _compiled_all(*aliases: str):
    index, bundle = _index(), _bundle()
    space = _space(bundle, *aliases)
    root = PolicyOccurrence(aliases[0]) if len(aliases) == 1 else PolicyAll(
        tuple(PolicyOccurrence(alias) for alias in aliases)
    )
    return index, bundle, space, compile_policy(Policy("people", root), address_space=space)


class EvaluationQueryProtocolTests(unittest.TestCase):
    def test_bindings_canonicalize_but_selections_preserve_order(self) -> None:
        digest = "a" * 64
        age, score = _address("pair", "age"), _address("pair", "score")
        query = EvaluationQuery(
            digest,
            (
                EvaluationQuerySelection("score_out", score),
                EvaluationQuerySelection("age_out", age),
            ),
            (EvaluationQueryBinding(score, 9), EvaluationQueryBinding(age, 18)),
        )

        self.assertEqual(tuple(item.address.port_name for item in query.bindings), ("age", "score"))
        self.assertEqual(tuple(item.alias for item in query.selections), ("score_out", "age_out"))

    def test_duplicate_and_empty_shapes_fail_during_construction(self) -> None:
        digest, age = "a" * 64, _address("pair", "age")
        cases = (
            lambda: EvaluationQuery(digest, ()),
            lambda: EvaluationQuery(
                digest,
                (EvaluationQuerySelection("x", age), EvaluationQuerySelection("x", _address("pair", "score"))),
            ),
            lambda: EvaluationQuery(
                digest,
                (EvaluationQuerySelection("x", age), EvaluationQuerySelection("y", age)),
            ),
            lambda: EvaluationQuery(
                digest,
                (EvaluationQuerySelection("x", age),),
                (EvaluationQueryBinding(age, 1), EvaluationQueryBinding(age, 2)),
            ),
        )
        for factory in cases:
            with self.subTest(factory=factory):
                with self.assertRaises(EvaluationQueryError):
                    factory()

    def test_direct_and_navigation_selection_sources_are_independently_deduplicated(self) -> None:
        digest = "a" * 64
        person = _address("pair", "person")
        navigation = EvaluationQueryFieldNavigationV0(person, FieldPath("Person", "age"))
        query = EvaluationQuery(
            digest,
            (
                EvaluationQuerySelection("person", person),
                EvaluationQueryNavigationSelectionV0("age", navigation),
            ),
        )
        self.assertEqual(tuple(item.alias for item in query.selections), ("person", "age"))
        with self.assertRaisesRegex(EvaluationQueryError, "navigation selections must be unique"):
            EvaluationQuery(
                digest,
                (
                    EvaluationQueryNavigationSelectionV0("age", navigation),
                    EvaluationQueryNavigationSelectionV0("another_age", navigation),
                ),
            )


class EvaluationQueryCompileTests(unittest.TestCase):
    def test_navigation_select_compiles_to_query_owned_lookup_after_bind(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("pair")
        query = EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("person", _address("pair", "person")),
                EvaluationQueryNavigationSelectionV0(
                    "age",
                    EvaluationQueryFieldNavigationV0(
                        _address("pair", "person"), FieldPath("Person", "age")
                    ),
                ),
            ),
            (EvaluationQueryBinding(_address("pair", "score"), 9),),
        )
        compiled = compile_evaluation_query(
            query, compiled_policy=policy, address_space=space, schema_index=index
        )
        navigation = compiled.selections[1]
        self.assertEqual(type(navigation).__name__, "ResolvedEvaluationQueryNavigationSelectionV0")
        self.assertEqual(navigation.value_type, "int")
        self.assertEqual(navigation.field_predicate_id, "person:age")
        materialized, traces = _materialize_native_derivation_plan(compiled._lowering_plan)
        body = materialized.body_ir
        self.assertEqual(body[3], ("eq", "$pair__score", 9))
        self.assertEqual(body[4][0:2], ("pred", "person:age"))
        self.assertEqual(
            traces[0].query_navigation_materializations[0].lookup_materialized_condition_index,
            4,
        )

    def test_navigation_common_base_is_branch_total_and_partial_base_rejects(self) -> None:
        index, bundle = _index(), _bundle()
        space = _space(bundle, "common", "left", "right")
        policy = compile_policy(
            Policy(
                "branches",
                PolicyAll((
                    PolicyOccurrence("common"),
                    PolicyAny((PolicyOccurrence("left"), PolicyOccurrence("right"))),
                )),
            ),
            address_space=space,
        )
        common = EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQueryNavigationSelectionV0(
                    "age",
                    EvaluationQueryFieldNavigationV0(
                        _address("common", "person"), FieldPath("Person", "age")
                    ),
                ),
            ),
        )
        compiled = compile_evaluation_query(
            common, compiled_policy=policy, address_space=space, schema_index=index
        )
        self.assertEqual(len(compiled.selections[0].sources), 2)
        with self.assertRaisesRegex(EvaluationQueryError, "not present in every Policy branch"):
            compile_evaluation_query(
                EvaluationQuery(
                    policy.policy_digest,
                    (
                        EvaluationQueryNavigationSelectionV0(
                            "age",
                            EvaluationQueryFieldNavigationV0(
                                _address("left", "person"), FieldPath("Person", "age")
                            ),
                        ),
                    ),
                ),
                compiled_policy=policy,
                address_space=space,
                schema_index=index,
            )

    def test_navigation_rejects_non_identity_cross_entity_and_identity_fields(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("pair")
        cases = (
            EvaluationQueryFieldNavigationV0(_address("pair", "age"), FieldPath("Person", "score")),
            EvaluationQueryFieldNavigationV0(_address("pair", "person"), FieldPath("Person", "employee_id")),
            EvaluationQueryFieldNavigationV0(_address("pair", "person"), FieldPath("Other", "code")),
        )
        for navigation in cases:
            with self.subTest(navigation=navigation):
                with self.assertRaises(EvaluationQueryError):
                    compile_evaluation_query(
                        EvaluationQuery(
                            policy.policy_digest,
                            (EvaluationQueryNavigationSelectionV0("value", navigation),),
                        ),
                        compiled_policy=policy,
                        address_space=space,
                        schema_index=index,
                    )

    def test_navigation_digest_changes_but_policy_identity_does_not(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("pair")
        direct = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("age", _address("pair", "age")),),
            ),
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        navigation = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (
                    EvaluationQueryNavigationSelectionV0(
                        "age",
                        EvaluationQueryFieldNavigationV0(
                            _address("pair", "person"), FieldPath("Person", "age")
                        ),
                    ),
                ),
            ),
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        self.assertNotEqual(direct.query_digest, navigation.query_digest)
        self.assertEqual(direct.compiled_policy.policy_digest, navigation.compiled_policy.policy_digest)
        self.assertEqual(direct.compiled_policy.policy_structure, navigation.compiled_policy.policy_structure)
        self.assertEqual(direct.compiled_policy.lineage, navigation.compiled_policy.lineage)
        with self.assertRaises(ValueError):
            replace(navigation, selections=direct.selections)
    def test_exact_occurrence_projection_and_typed_bind_materialize(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("left", "right")
        forged = EntityRef(
            "Person", {"employee_id": "alice"}, encoded_ref="idref_v1:Person:forged"
        )
        query = EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("left_age", _address("left", "age")),
                EvaluationQuerySelection("right_age", _address("right", "age")),
            ),
            (EvaluationQueryBinding(_address("left", "person"), forged),),
        )

        compiled = compile_evaluation_query(
            query, compiled_policy=policy, address_space=space, schema_index=index
        )
        expected_ref = encode_entity_ref(
            EntityRef("Person", {"employee_id": "alice"}), index=index
        )
        self.assertEqual(compiled.bindings[0].normalized_value, expected_ref)
        self.assertNotEqual(compiled.bindings[0].normalized_value, forged.encoded_ref)
        self.assertEqual(tuple(compiled.projection_head.ports), ("left_age", "right_age"))

        foundation = _validate_rule_expr_head_foundation(compiled._lowering_plan)
        materialized, traces = _materialize_native_derivation_plan(compiled._lowering_plan)
        self.assertEqual(tuple(port.name for port in foundation.declared_ports), ("left_age", "right_age"))
        self.assertIn(("eq", "$left__person", expected_ref), materialized.body_ir)
        links = {
            (link.head_port_name, link.source_occurrence_alias, link.source_port_name)
            for link in traces[0].head_port_link_materializations
        }
        self.assertEqual(
            links,
            {("left_age", "left", "age"), ("right_age", "right", "age")},
        )

    def test_query_probe_seeds_only_explicit_sources_not_same_name_ports(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("left", "right")
        query = EvaluationQuery(
            policy.policy_digest,
            (EvaluationQuerySelection("chosen", _address("right", "age")),),
        )
        compiled = compile_evaluation_query(
            query, compiled_policy=policy, address_space=space, schema_index=index
        )

        seeds = probe_seed_vars_by_head_port(compiled._lowering_plan)

        self.assertEqual(seeds["chosen"], ("$__projection_0", "$right__age"))
        self.assertNotIn("$left__age", seeds["chosen"])

    def test_common_address_maps_to_every_dnf_copy_without_parsing_aliases(self) -> None:
        index, bundle = _index(), _bundle()
        space = _space(bundle, "common", "left", "right")
        policy = compile_policy(
            Policy(
                "branches",
                PolicyAll(
                    (
                        PolicyOccurrence("common"),
                        PolicyAny((PolicyOccurrence("left"), PolicyOccurrence("right"))),
                    )
                ),
            ),
            address_space=space,
        )
        query = EvaluationQuery(
            policy.policy_digest,
            (EvaluationQuerySelection("age", _address("common", "age")),),
            (EvaluationQueryBinding(_address("common", "score"), 7),),
        )

        compiled = compile_evaluation_query(
            query, compiled_policy=policy, address_space=space, schema_index=index
        )

        self.assertEqual(len(compiled.selections[0].sources), 2)
        self.assertEqual(
            {source.occurrence_alias for source in compiled.selections[0].sources},
            {branch.lowered_occurrence_aliases[
                branch.authored_occurrence_aliases.index("common")
            ] for branch in policy.branches},
        )
        materialized, traces = _materialize_native_derivation_plan(compiled._lowering_plan)
        self.assertEqual(len(materialized.body_ir), 2)
        self.assertEqual(tuple(len(trace.head_port_link_materializations) for trace in traces), (1, 1))
        for branch in materialized.body_ir:
            self.assertTrue(any(atom[0] == "eq" and atom[2] == 7 for atom in branch))

    def test_branch_local_bind_and_select_fail_closed(self) -> None:
        index, bundle = _index(), _bundle()
        space = _space(bundle, "common", "left", "right")
        policy = compile_policy(
            Policy(
                "branches",
                PolicyAll((
                    PolicyOccurrence("common"),
                    PolicyAny((PolicyOccurrence("left"), PolicyOccurrence("right"))),
                )),
            ),
            address_space=space,
        )
        cases = (
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("left_age", _address("left", "age")),),
            ),
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("common_age", _address("common", "age")),),
                (EvaluationQueryBinding(_address("left", "score"), 1),),
            ),
        )
        for query in cases:
            with self.subTest(query=query):
                with self.assertRaises(EvaluationQueryError) as ctx:
                    compile_evaluation_query(
                        query, compiled_policy=policy, address_space=space, schema_index=index
                    )
                self.assertEqual(ctx.exception.code, "PARTIAL_BRANCH_QUERY_ADDRESS")

    def test_digest_is_binding_order_stable_and_selection_order_sensitive(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("pair")
        selections = (
            EvaluationQuerySelection("age", _address("pair", "age")),
            EvaluationQuerySelection("score", _address("pair", "score")),
        )
        bindings = (
            EvaluationQueryBinding(_address("pair", "age"), 18),
            EvaluationQueryBinding(_address("pair", "score"), 9),
        )
        first = EvaluationQuery(policy.policy_digest, selections, bindings)
        reordered_bind = EvaluationQuery(policy.policy_digest, selections, tuple(reversed(bindings)))
        reordered_select = EvaluationQuery(policy.policy_digest, tuple(reversed(selections)), bindings)
        changed_value = EvaluationQuery(
            policy.policy_digest,
            selections,
            (bindings[0], EvaluationQueryBinding(_address("pair", "score"), 10)),
        )

        def compiled(item):
            return compile_evaluation_query(
                item, compiled_policy=policy, address_space=space, schema_index=index
            )
        self.assertEqual(compiled(first).query_digest, compiled(reordered_bind).query_digest)
        self.assertNotEqual(compiled(first).query_digest, compiled(reordered_select).query_digest)
        self.assertNotEqual(compiled(first).query_digest, compiled(changed_value).query_digest)

    def test_compiled_query_rejects_metadata_or_digest_splicing(self) -> None:
        index, _bundle_value, space, policy = _compiled_all("pair")
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("age", _address("pair", "age")),),
                (EvaluationQueryBinding(_address("pair", "score"), 9),),
            ),
            compiled_policy=policy, address_space=space, schema_index=index,
        )
        altered_binding = replace(compiled.bindings[0], normalized_value=999)
        altered_selection = replace(compiled.selections[0], address=_address("pair", "score"))
        branch = compiled._lowering_plan.branches[0]
        altered_plan = replace(
            compiled._lowering_plan,
            branches=(replace(branch, body_atoms=(*branch.body_atoms, CmpAtom("ge", Var("$pair__age"), Const(100)))),),
        )
        altered_head = replace(compiled.projection_head, version="attacker-version")
        altered_head_plan = replace(compiled._lowering_plan, head=altered_head)
        cases = (
            {"bindings": (altered_binding,)},
            {"selections": (altered_selection,)},
            {"policy_digest": "0" * 64},
            {"bindings": list(compiled.bindings)},
            {"_lowering_plan": altered_plan},
            {"projection_head": altered_head, "_lowering_plan": altered_head_plan},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(compiled, **changes)

    def test_final_artifact_validation_uses_typed_compiler_boundary(self) -> None:
        import factgraph.application.evaluation_query_runtime as query_runtime

        index, _bundle_value, space, policy = _compiled_all("pair")
        query = EvaluationQuery(
            policy.policy_digest,
            (EvaluationQuerySelection("age", _address("pair", "age")),),
        )
        original_attach = query_runtime._attach_evaluation_query_head
        calls = 0
        def malformed_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            plan = original_attach(*args, **kwargs)
            return replace(plan, canonical_key=("malformed",)) if calls == 1 else plan
        with patch(
            "factgraph.application.evaluation_query_runtime._attach_evaluation_query_head",
            side_effect=malformed_once,
        ), self.assertRaises(EvaluationQueryError) as ctx:
            compile_evaluation_query(
                query, compiled_policy=policy, address_space=space, schema_index=index,
            )
        self.assertEqual(ctx.exception.code, "QUERY_LOWERING_INVARIANT")
        self.assertEqual(ctx.exception.stage, "query_compiler_invariant")

    def test_uuid_field_binding_is_storage_canonical(self) -> None:
        index = build_schema_index(
            compile_schema_from_classes([Record], generated_at="2026-08-12T00:00:00Z")
        )
        record, marker = Var("$record"), Var("$marker")
        bundle = build_resolved_rule(
            id="record_marker",
            when=(PredAtom("Record:exists", [record]), PredAtom("record:marker", [record, marker])),
            ports={
                "record": SemanticRulePort(record, entity_identity("Record")),
                "marker": SemanticRulePort(marker, field_endpoint("Record", "marker")),
            },
            schema_index=index,
        )
        space = _space(bundle, "record")
        policy = compile_policy(Policy("record", PolicyOccurrence("record")), address_space=space)
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("marker", _address("record", "marker")),),
                (EvaluationQueryBinding(
                    _address("record", "marker"), "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
                ),),
            ),
            compiled_policy=policy, address_space=space, schema_index=index,
        )
        self.assertEqual(
            compiled.bindings[0].normalized_value,
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )

    def test_bytes_field_binding_keeps_self_verifying_storage_atom(self) -> None:
        index = build_schema_index(
            compile_schema_from_classes([Record], generated_at="2026-08-12T00:00:00Z")
        )
        record, payload = Var("$record"), Var("$payload")
        bundle = build_resolved_rule(
            id="record_payload",
            when=(PredAtom("Record:exists", [record]), PredAtom("record:payload", [record, payload])),
            ports={
                "record": SemanticRulePort(record, entity_identity("Record")),
                "payload": SemanticRulePort(payload, field_endpoint("Record", "payload")),
            }, schema_index=index,
        )
        space = _space(bundle, "record")
        policy = compile_policy(Policy("record", PolicyOccurrence("record")), address_space=space)
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (EvaluationQuerySelection("payload", _address("record", "payload")),),
                (EvaluationQueryBinding(_address("record", "payload"), b"\x00\xff\x10"),),
            ), compiled_policy=policy, address_space=space, schema_index=index,
        )
        self.assertEqual(compiled.bindings[0].normalized_value, "AP8Q")

    def test_native_variable_like_string_field_fails_closed(self) -> None:
        index = build_schema_index(
            compile_schema_from_classes([Record], generated_at="2026-08-12T00:00:00Z")
        )
        record, label = Var("$record"), Var("$label")
        bundle = build_resolved_rule(
            id="record_label",
            when=(PredAtom("Record:exists", [record]), PredAtom("record:label", [record, label])),
            ports={
                "record": SemanticRulePort(record, entity_identity("Record")),
                "label": SemanticRulePort(label, field_endpoint("Record", "label")),
            }, schema_index=index,
        )
        space = _space(bundle, "record")
        policy = compile_policy(Policy("record", PolicyOccurrence("record")), address_space=space)
        for value in ("$alice", "$"):
            with self.subTest(value=value), self.assertRaises(EvaluationQueryError) as ctx:
                compile_evaluation_query(
                    EvaluationQuery(
                        policy.policy_digest,
                        (EvaluationQuerySelection("label", _address("record", "label")),),
                        (EvaluationQueryBinding(_address("record", "label"), value),),
                    ), compiled_policy=policy, address_space=space, schema_index=index,
                )
            self.assertEqual(ctx.exception.code, "QUERY_BINDING_TYPE_MISMATCH")

    def test_projection_id_collision_with_schema_rejects(self) -> None:
        schema_ir = compile_schema_from_classes([Person], generated_at="2026-08-12T00:00:00Z")
        projection_id = Rule.projection("age").id
        schema_ir["predicates"].append({
            "pred_id": projection_id, "owner_type": "Person", "arity": 1,
            "arg_specs": [{"name": "person", "type_domain": "entity_ref"}],
            "cardinality": "single", "group_key_indexes": [0],
        })
        schema_ir["projection"]["predicates"].append(projection_id)
        index = build_schema_index(schema_ir)
        bundle = _bundle(index)
        space = _space(bundle, "pair")
        policy = compile_policy(Policy("p", PolicyOccurrence("pair")), address_space=space)

        with self.assertRaises(EvaluationQueryError) as ctx:
            compile_evaluation_query(
                EvaluationQuery(
                    policy.policy_digest,
                    (EvaluationQuerySelection("age", _address("pair", "age")),),
                ),
                compiled_policy=policy, address_space=space, schema_index=index,
            )
        self.assertEqual(ctx.exception.code, "QUERY_PROJECTION_NAMESPACE_COLLISION")

    def test_policy_address_schema_staleness_and_types_fail_distinctly(self) -> None:
        index, bundle, space, policy = _compiled_all("pair")
        valid_selection = (EvaluationQuerySelection("age", _address("pair", "age")),)

        with self.assertRaises(EvaluationQueryError) as digest:
            compile_evaluation_query(
                EvaluationQuery("0" * 64, valid_selection),
                compiled_policy=policy, address_space=space, schema_index=index,
            )
        self.assertEqual(digest.exception.code, "QUERY_POLICY_DIGEST_MISMATCH")

        with self.assertRaises(EvaluationQueryError) as address_space:
            compile_evaluation_query(
                EvaluationQuery(policy.policy_digest, valid_selection),
                compiled_policy=policy, address_space=_space(bundle, "other"), schema_index=index,
            )
        self.assertEqual(address_space.exception.code, "QUERY_ADDRESS_SPACE_MISMATCH")

        with self.assertRaises(EvaluationQueryError) as unresolved:
            compile_evaluation_query(
                EvaluationQuery(
                    policy.policy_digest,
                    (EvaluationQuerySelection("missing", _address("pair", "missing")),),
                ),
                compiled_policy=policy, address_space=space, schema_index=index,
            )
        self.assertEqual(unresolved.exception.code, "UNRESOLVED_QUERY_ADDRESS")

        with self.assertRaises(EvaluationQueryError) as schema:
            compile_evaluation_query(
                EvaluationQuery(policy.policy_digest, valid_selection),
                compiled_policy=policy, address_space=space, schema_index=_index(include_other=True),
            )
        self.assertEqual(schema.exception.code, "QUERY_SCHEMA_CONTEXT_MISMATCH")

        wrong_type = EvaluationQuery(
            policy.policy_digest,
            valid_selection,
            (EvaluationQueryBinding(_address("pair", "age"), True),),
        )
        with self.assertRaises(EvaluationQueryError) as typed:
            compile_evaluation_query(
                wrong_type, compiled_policy=policy, address_space=space, schema_index=index
            )
        self.assertEqual(typed.exception.code, "QUERY_BINDING_TYPE_MISMATCH")

        variable_like_string = EvaluationQuery(
            policy.policy_digest, valid_selection,
            (EvaluationQueryBinding(_address("pair", "person"), EntityRef("Person", {"employee_id": "$alice"})),),
        )
        # EntityRef hashes to an idref and remains safe; only direct string fields are rejected.
        compile_evaluation_query(
            variable_like_string, compiled_policy=policy, address_space=space, schema_index=index
        )

        bundle.rule.when[1].terms[1] = Var("$changed")
        with self.assertRaises(EvaluationQueryError) as stale:
            compile_evaluation_query(
                EvaluationQuery(policy.policy_digest, valid_selection),
                compiled_policy=policy, address_space=space, schema_index=index,
            )
        self.assertEqual(stale.exception.code, "QUERY_POLICY_CONTEXT_STALE")


if __name__ == "__main__":
    unittest.main()
