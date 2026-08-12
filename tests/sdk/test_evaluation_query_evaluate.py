from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch
from uuid import UUID

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
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    EvaluateResult,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    Policy,
    PolicyOccurrence,
    Rule,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.errors import SDKStoreError


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
    text: str = Field()
    observed_at: datetime = Field()
    ratio: float = Field()


def _address(alias: str, port: str) -> SemanticPortAddress:
    return SemanticPortAddress(alias, port)


def _person_rule(index: object):
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


def _compiled_person_query(
    graph: SDKStore,
    *,
    alias: str = "pair",
    employee_id: str | None = None,
    score: int | None = None,
    selections: tuple[tuple[str, str], ...] = (("age", "age"),),
):
    index = build_schema_index(graph.schema_ir)
    bundle = _person_rule(index)
    space = SemanticAddressSpace((manage_rule_occurrence(bundle, alias),))
    policy = compile_policy(
        Policy(f"people-{alias}", PolicyOccurrence(alias)),
        address_space=space,
    )
    bindings = []
    if employee_id is not None:
        bindings.append(
            EvaluationQueryBinding(
                _address(alias, "person"),
                EntityRef("Person", {"employee_id": employee_id}),
            )
        )
    if score is not None:
        bindings.append(EvaluationQueryBinding(_address(alias, "score"), score))
    query = EvaluationQuery(
        policy.policy_digest,
        tuple(
            EvaluationQuerySelection(output, _address(alias, port))
            for output, port in selections
        ),
        tuple(bindings),
    )
    return (
        compile_evaluation_query(
            query,
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        ),
        bundle,
    )


def _seed_person(
    graph: SDKStore,
    employee_id: str,
    *,
    age: int,
    score: int,
) -> str:
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
        graph.ledger,
        field_predicate(index, "Person", "age").pred_id,
        encoded,
        [("int", age)],
    )
    set_field(
        graph.ledger,
        field_predicate(index, "Person", "score").pred_id,
        encoded,
        [("int", score)],
    )
    return encoded


class EvaluationQueryNativeEvaluateTests(unittest.TestCase):
    def test_native_bind_select_returns_projection_result_and_is_read_only(self) -> None:
        graph = SDKStore([Person])
        alice_ref = _seed_person(graph, "alice", age=22, score=9)
        _seed_person(graph, "bob", age=19, score=7)
        compiled, _bundle = _compiled_person_query(
            graph,
            employee_id="alice",
            selections=(
                ("selected_person", "person"),
                ("selected_score", "score"),
                ("selected_age", "age"),
            ),
        )
        before = tuple(graph.ledger.find_claims())

        import factgraph.sdk.store as store_module

        with patch(
            "factgraph.sdk.store._materialize_adapter_derivation_plan",
            wraps=store_module._materialize_adapter_derivation_plan,
        ) as materializer, patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            wraps=store_module.evaluate_derivation_plans,
        ) as evaluator:
            result = graph.eval.evaluate(compiled, engine="native")

        self.assertEqual(materializer.call_count, 1)
        self.assertIs(materializer.call_args.args[0], compiled._lowering_plan)
        self.assertEqual(materializer.call_args.kwargs, {"engine": "native"})
        self.assertEqual(evaluator.call_count, 1)
        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(tuple(graph.ledger.find_claims()), before)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row.kind, "projection")
        self.assertEqual(
            tuple(row.bindings),
            ("selected_person", "selected_score", "selected_age"),
        )
        self.assertEqual(
            dict(row.bindings),
            {
                "selected_person": {"kind": "entity_ref", "value": alice_ref},
                "selected_score": {"kind": "literal", "tag": "int", "value": 9},
                "selected_age": {"kind": "literal", "tag": "int", "value": 22},
            },
        )
        self.assertEqual(result.head, compiled.projection_head)
        self.assertEqual(row.explain().status, "passed")
        self.assertIsInstance(row.close(), Rule)
        with self.assertRaises(TypeError):
            row.bindings["selected_age"]["value"] = 99

    def test_non_matching_bind_returns_valid_empty_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph, score=999)

        result = graph.eval.evaluate(compiled)

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(result.count(), 0)
        self.assertFalse(result.exists())
        self.assertIsNone(result.first())
        self.assertTrue(result.fingerprint.expr_digest.startswith("sha256:"))

    def test_query_candidate_arity_mismatch_fails_closed(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)

        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def add_extra_term(*args, **kwargs):
            candidates = original(*args, **kwargs)
            candidate = candidates[0]
            payload = dict(candidate.payload)
            payload["terms"] = [
                *payload["terms"],
                {"kind": "literal", "tag": "int", "value": 999},
            ]
            return [
                replace(
                    candidate,
                    payload=payload,
                    candidate_key="",
                    candidate_id="",
                )
            ]

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=add_extra_term,
        ):
            with self.assertRaisesRegex(SDKStoreError, "exactly align"):
                graph.eval.evaluate(compiled)

    def test_query_candidate_target_mismatch_fails_closed(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)

        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def change_target(*args, **kwargs):
            candidate = original(*args, **kwargs)[0]
            payload = dict(candidate.payload)
            payload["pred_id"] = "not-the-query-head"
            return [
                replace(
                    candidate,
                    target="not-the-query-head",
                    payload=payload,
                    candidate_key="",
                    candidate_id="",
                )
            ]

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=change_target,
        ):
            with self.assertRaisesRegex(SDKStoreError, "exactly match"):
                graph.eval.evaluate(compiled)

    def test_query_candidate_runtime_tag_must_be_self_consistent(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)

        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def contradict_runtime_tag(*args, **kwargs):
            candidate = original(*args, **kwargs)[0]
            payload = dict(candidate.payload)
            payload["terms"] = [
                {"kind": "literal", "tag": "string", "value": 22}
            ]
            return [replace(candidate, payload=payload, candidate_key="", candidate_id="")]

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=contradict_runtime_tag,
        ):
            with self.assertRaisesRegex(SDKStoreError, "contradicts its runtime tag"):
                graph.eval.evaluate(compiled)

    def test_query_and_occurrence_identity_are_in_result_fingerprints(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        first, _bundle = _compiled_person_query(graph, alias="pair")
        second, _bundle = _compiled_person_query(graph, alias="other")

        first_result = graph.eval.evaluate(first)
        repeated_result = graph.eval.evaluate(first)
        second_result = graph.eval.evaluate(second)

        self.assertEqual(
            first_result.fingerprint.expr_digest,
            repeated_result.fingerprint.expr_digest,
        )
        self.assertEqual(
            first_result.fingerprint.rule_set_digest,
            repeated_result.fingerprint.rule_set_digest,
        )
        self.assertNotEqual(
            first_result.fingerprint.expr_digest,
            second_result.fingerprint.expr_digest,
        )
        self.assertNotEqual(
            first_result.fingerprint.rule_set_digest,
            second_result.fingerprint.rule_set_digest,
        )

    def test_execution_revalidates_artifact_and_store_schema_before_engine(self) -> None:
        graph = SDKStore([Person])
        compiled, bundle = _compiled_person_query(graph)
        bundle.rule.when[1].terms[1] = Var("$changed")

        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "integrity check"):
                graph.eval.evaluate(compiled)
        evaluator.assert_not_called()

        clean, _bundle = _compiled_person_query(graph)
        other_graph = SDKStore([Person, Other])
        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "schema does not match"):
                other_graph.eval.evaluate(clean)
        evaluator.assert_not_called()

    def test_query_only_surfaces_and_native_boundary_reject_explicitly(self) -> None:
        graph = SDKStore([Person])
        compiled, _bundle = _compiled_person_query(graph)
        profile = SemanticsProfile(name="probabilistic", engine="problog")

        with self.assertRaisesRegex(SDKStoreError, "only engine='native'"):
            graph.eval.evaluate(compiled, engine="problog")
        with self.assertRaisesRegex(SDKStoreError, "does not accept config"):
            graph.eval.evaluate(compiled, config=profile)
        with self.assertRaisesRegex(SDKStoreError, "unknown.*head"):
            graph.eval.evaluate(compiled, head=compiled.projection_head)
        with self.assertRaisesRegex(SDKStoreError, "does not accept CompiledEvaluationQueryV0"):
            graph.eval.evaluate_candidates(compiled)
        with self.assertRaisesRegex(SDKStoreError, "evaluate it first"):
            graph.eval.explain(compiled)

    def test_view_change_during_execution_aborts_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)

        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def mutate_after_evaluate(*args, **kwargs):
            candidates = original(*args, **kwargs)
            _seed_person(graph, "bob", age=19, score=7)
            return candidates

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=mutate_after_evaluate,
        ):
            with self.assertRaisesRegex(SDKStoreError, "view changed during"):
                graph.eval.evaluate(compiled)

    def test_view_change_during_result_adaptation_aborts_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        original = graph._candidate_sets_to_evaluate_result

        def mutate_after_adaptation(*args, **kwargs):
            result = original(*args, **kwargs)
            _seed_person(graph, "bob", age=19, score=7)
            return result

        with patch.object(
            graph,
            "_candidate_sets_to_evaluate_result",
            side_effect=mutate_after_adaptation,
        ):
            with self.assertRaisesRegex(SDKStoreError, "view changed during"):
                graph.eval.evaluate(compiled)

    def test_premise_policy_is_rejected_and_cannot_appear_during_or_after_run(self) -> None:
        exclusion = MetaExclusion("provenance_class", frozenset({"untrusted"}))

        blocked = SDKStore([Person])
        compiled, _bundle = _compiled_person_query(blocked)
        blocked.set_premise_exclusions(exclusion)
        with patch("factgraph.sdk.store.evaluate_derivation_plans") as evaluator:
            with self.assertRaisesRegex(SDKStoreError, "premise-filtered"):
                blocked.eval.evaluate(compiled)
        evaluator.assert_not_called()

        during = SDKStore([Person])
        _seed_person(during, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(during)
        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def enable_filter(*args, **kwargs):
            candidates = original(*args, **kwargs)
            during.set_premise_exclusions(exclusion)
            return candidates

        with patch("factgraph.sdk.store.evaluate_derivation_plans", side_effect=enable_filter):
            with self.assertRaisesRegex(SDKStoreError, "premise policy changed"):
                during.eval.evaluate(compiled)

        after = SDKStore([Person])
        _seed_person(after, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(after)
        row = after.eval.evaluate(compiled)[0]
        after.set_premise_exclusions(exclusion)
        with self.assertRaisesRegex(ValueError, "premise policy is stale"):
            row.close()
        self.assertEqual(row.explain().status, "unsupported")

    def test_query_explain_rejects_graph_without_holding_path(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        original_factory = graph._row_graph_builder_for_engine

        def failing_factory(**kwargs):
            delegate = original_factory(**kwargs)

            def build(row, result, metadata):
                evidence = delegate(row, result, metadata)
                return replace(
                    evidence,
                    paths=tuple(replace(path, status="fails") for path in evidence.paths),
                )

            return build

        with patch.object(graph, "_row_graph_builder_for_engine", side_effect=failing_factory):
            row = graph.eval.evaluate(compiled)[0]
        explanation = row.explain()
        self.assertEqual(explanation.status, "unsupported")
        self.assertIn("no holding evidence path", explanation.errors[0].message)

    def test_artifact_change_during_execution_aborts_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, bundle = _compiled_person_query(graph)

        import factgraph.sdk.store as store_module

        original = store_module.evaluate_derivation_plans

        def mutate_artifact_after_evaluate(*args, **kwargs):
            candidates = original(*args, **kwargs)
            bundle.rule.when[1].terms[1] = Var("$changed")
            return candidates

        with patch(
            "factgraph.sdk.store.evaluate_derivation_plans",
            side_effect=mutate_artifact_after_evaluate,
        ):
            with self.assertRaisesRegex(SDKStoreError, "integrity check"):
                graph.eval.evaluate(compiled)

    def test_view_change_after_result_blocks_close_and_explain(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        result = graph.eval.evaluate(compiled)
        row = result[0]
        self.assertEqual(row.explain().status, "passed")
        self.assertIsInstance(row.close(), Rule)

        _seed_person(graph, "bob", age=19, score=7)

        with self.assertRaisesRegex(ValueError, "view is stale"):
            row.close()
        explanation = row.explain()
        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIn("view is stale", explanation.errors[0].message)

    def test_artifact_change_after_result_blocks_close_and_explain(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, bundle = _compiled_person_query(graph)
        row = graph.eval.evaluate(compiled)[0]

        bundle.rule.when[1].terms[1] = Var("$changed")

        with self.assertRaisesRegex(ValueError, "integrity"):
            row.close()
        explanation = row.explain()
        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIn("integrity", explanation.errors[0].message)

    def test_uuid_and_bytes_projection_restore_compiler_value_domains(self) -> None:
        graph = SDKStore([Record])
        index = build_schema_index(graph.schema_ir)
        record, marker, payload, text, observed_at, ratio = (
            Var("$record"),
            Var("$marker"),
            Var("$payload"),
            Var("$text"),
            Var("$observed_at"),
            Var("$ratio"),
        )
        bundle = build_resolved_rule(
            id="record_values",
            when=(
                PredAtom("Record:exists", [record]),
                PredAtom("record:marker", [record, marker]),
                PredAtom("record:payload", [record, payload]),
                PredAtom("record:text", [record, text]),
                PredAtom("record:observed_at", [record, observed_at]),
                PredAtom("record:ratio", [record, ratio]),
            ),
            ports={
                "record": SemanticRulePort(record, entity_identity("Record")),
                "marker": SemanticRulePort(marker, field_endpoint("Record", "marker")),
                "payload": SemanticRulePort(payload, field_endpoint("Record", "payload")),
                "text": SemanticRulePort(text, field_endpoint("Record", "text")),
                "observed_at": SemanticRulePort(
                    observed_at,
                    field_endpoint("Record", "observed_at"),
                ),
                "ratio": SemanticRulePort(ratio, field_endpoint("Record", "ratio")),
            },
            schema_index=index,
        )
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "record"),))
        policy = compile_policy(
            Policy("records", PolicyOccurrence("record")),
            address_space=space,
        )
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (
                    EvaluationQuerySelection("marker", _address("record", "marker")),
                    EvaluationQuerySelection("payload", _address("record", "payload")),
                    EvaluationQuerySelection("text", _address("record", "text")),
                    EvaluationQuerySelection(
                        "observed_at",
                        _address("record", "observed_at"),
                    ),
                    EvaluationQuerySelection("ratio", _address("record", "ratio")),
                ),
            ),
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        ref = resolve_selector(
            EntitySelector(entity_type="Record", identity={"record_id": "r1"}),
            index=index,
        )
        info = entity_info(index, "Record")
        encoded = ref.encoded_ref or ""
        marker_value = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        set_field(graph.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            graph.ledger,
            info.identity_predicates["record_id"].pred_id,
            encoded,
            [("string", "r1")],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Record", "marker").pred_id,
            encoded,
            [("uuid", marker_value)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Record", "payload").pred_id,
            encoded,
            [("bytes", b"\x00\xff")],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Record", "text").pred_id,
            encoded,
            [("string", encoded)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Record", "observed_at").pred_id,
            encoded,
            [("time", 123)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Record", "ratio").pred_id,
            encoded,
            [("float64", 1.5)],
        )

        row = graph.eval.evaluate(compiled)[0]

        self.assertEqual(
            row.bindings["marker"],
            {"kind": "literal", "tag": "uuid", "value": marker_value},
        )
        self.assertEqual(
            row.bindings["payload"],
            {"kind": "literal", "tag": "bytes", "value": "AP8"},
        )
        self.assertEqual(
            row.bindings["text"],
            {"kind": "literal", "tag": "string", "value": encoded},
        )
        self.assertEqual(row.explain().evidence.subject_binding["text"], encoded)
        self.assertEqual(
            row.bindings["observed_at"],
            {"kind": "literal", "tag": "time", "value": 123},
        )
        self.assertEqual(
            row.bindings["ratio"],
            {"kind": "literal", "tag": "float64", "value": "0x3ff8000000000000"},
        )

    def test_query_view_bytes_normalization_is_address_independent(self) -> None:
        from factgraph.sdk.store import _evaluation_query_digest_safe

        expected = _evaluation_query_digest_safe(("bytes", b"\x00\xff"))
        self.assertEqual(
            expected,
            _evaluation_query_digest_safe(("bytes", bytearray(b"\x00\xff"))),
        )
        self.assertEqual(
            expected,
            _evaluation_query_digest_safe(("bytes", memoryview(b"\x00\xff"))),
        )

    def test_legacy_display_of_idref_looking_literal_is_unchanged(self) -> None:
        from types import SimpleNamespace

        graph = SDKStore([Person])
        encoded = _seed_person(graph, "alice", age=22, score=9)
        legacy_row = SimpleNamespace(
            kind="fact_triple",
            bindings={"value": {"kind": "literal", "tag": "string", "value": encoded}},
        )
        self.assertEqual(graph._display_bindings_for_row(legacy_row)["value"], "Person alice")


if __name__ == "__main__":
    unittest.main()
