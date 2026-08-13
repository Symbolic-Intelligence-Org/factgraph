from __future__ import annotations

import unittest
from dataclasses import asdict, replace
from datetime import datetime
import inspect
import json
from typing import get_type_hints
from unittest.mock import patch
from uuid import UUID

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    entity_info,
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
    field_predicate,
    manage_rule_occurrence,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntityRef,
    EntitySelector,
    DetachedRowError,
    EvaluateResult,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    EvaluationRunBundleV0,
    FieldPath,
    Policy,
    PolicyOccurrence,
    ProtocolShapeError,
    Rule,
    ScenarioFieldSubstitutionV0,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.evaluation_run import _plain, _token
from factgraph.application.protocol.evaluation_run_bundle import _token as _bundle_token
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
    unrelated: int = Field()


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
        self.assertNotIn(
            "capture",
            evaluator.call_args.kwargs,
        )
        self.assertIsNone(result.run_bundle)
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
        anchor = result.run_anchor
        self.assertIsNotNone(anchor)
        assert anchor is not None
        self.assertEqual(anchor.target.policy_structure, compiled.compiled_policy.policy_structure)
        self.assertEqual(anchor.query_digest, compiled.query_digest)
        self.assertEqual(anchor.capture_level, "identity_only")
        self.assertEqual(anchor.replay_availability, "not_available")
        json.dumps(asdict(anchor), sort_keys=True)
        explanation = row.explain()
        self.assertEqual(explanation.status, "passed")
        self.assertEqual(explanation.checked_scope["evaluation_run_anchor_digest"], anchor.anchor_digest)
        self.assertIsInstance(row.close(), Rule)
        with self.assertRaises(TypeError):
            row.bindings["selected_age"]["value"] = 99

    def test_run_bundle_capture_is_opt_in_strict_and_detached(self) -> None:
        graph = SDKStore([Person])
        alice_ref = _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(
            graph,
            employee_id="alice",
            selections=(("person", "person"), ("age", "age")),
        )

        ordinary = graph.eval.evaluate(compiled)
        import factgraph.sdk.store as store_module

        observed_relations = []
        original_evaluate = store_module._evaluate_derivation_plans_with_native_relation_capture

        def observe_relation(*args, **kwargs):
            outputs, snapshot = original_evaluate(*args, **kwargs)
            observed_relations.append(snapshot)
            return outputs, snapshot

        with patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_relation_capture",
            side_effect=observe_relation,
        ), patch(
            "factgraph.sdk.store._build_evaluation_run_bundle_v0",
            wraps=store_module._build_evaluation_run_bundle_v0,
        ) as builder:
            captured = graph.eval.evaluate(compiled, capture="run_bundle_v0")

        self.assertEqual(builder.call_count, 1)
        self.assertEqual(len(observed_relations), 1)
        self.assertIs(
            builder.call_args.kwargs["effective_relations"],
            observed_relations[0],
        )
        self.assertIsNone(ordinary.run_bundle)
        self.assertIsNotNone(captured.run_bundle)
        assert captured.run_bundle is not None
        payload = evaluation_run_bundle_bytes(captured.run_bundle)
        detached = evaluation_run_bundle_from_bytes(payload)

        self.assertEqual(detached, captured.run_bundle)
        self.assertEqual(detached.run_anchor, captured.run_anchor)
        self.assertIn(alice_ref.encode("utf-8"), payload)
        self.assertNotIn(alice_ref, repr(captured.run_bundle))
        self.assertFalse(hasattr(detached, "replay"))
        self.assertFalse(hasattr(detached, "explain"))

        _seed_person(graph, "bob", age=19, score=7)
        self.assertEqual(evaluation_run_bundle_from_bytes(payload), detached)

        for invalid in (True, False, "unknown", 1):
            with self.subTest(capture=invalid):
                with self.assertRaisesRegex(SDKStoreError, "capture"):
                    graph.eval.evaluate(compiled, capture=invalid)

        with self.assertRaisesRegex(SDKStoreError, "only accepted for CompiledEvaluationQueryV0"):
            graph.eval.evaluate({"derivation_id": "not-a-query"}, capture="run_bundle_v0")

    def test_non_query_evaluate_and_candidate_paths_reject_scenario_keyword(self) -> None:
        import factgraph.sdk as sdk

        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        scenario = ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "alice"}),
            FieldPath("Person", "age"),
            35,
            "must-not-be-silent",
        )
        with sdk.vars("person") as (person,):
            inference = sdk.Inference(
                id="legacy-person",
                version="1",
                when=[sdk.Pred("Person:exists", person)],
                emits=sdk.EmitSpec("Person:exists", [person]),
            )
        for operation, input_value in (
            (graph.eval.evaluate, inference),
            (graph.eval.evaluate, inference.to_authoring_payload()),
            (graph.eval.evaluate_candidates, inference),
            (graph.eval.evaluate_candidates, inference.to_authoring_payload()),
        ):
            with self.subTest(operation=operation.__name__, input_type=type(input_value).__name__), self.assertRaisesRegex(
                SDKStoreError,
                "scenario=",
            ):
                operation(input_value, scenario=scenario)

    def test_bundle_annotation_and_public_evaluate_signatures_are_reflectable(self) -> None:
        import factgraph.application.derivation_runtime as runtime
        import factgraph.core.store.evaluation as core_evaluation

        self.assertEqual(
            get_type_hints(EvaluateResult)["run_bundle"],
            EvaluationRunBundleV0 | None,
        )
        self.assertNotIn("observer", str(inspect.signature(runtime.evaluate_derivation_plans)))
        self.assertNotIn("observer", str(inspect.signature(core_evaluation.evaluate_store)))

    def test_zero_row_bundle_preserves_dependency_relations_without_asserting_false(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph, score=999)

        result = graph.eval.evaluate(compiled, capture="run_bundle_v0")

        assert result.run_bundle is not None
        self.assertEqual(result.run_bundle.rows, ())
        self.assertGreater(len(result.run_bundle.relations), 0)
        self.assertEqual(result.run_bundle.run_anchor.summary.truth_interpretation, "not_asserted")

    def test_run_bundle_capture_is_atomic_with_the_live_view_guard(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        import factgraph.sdk.store as store_module

        original = store_module._build_evaluation_run_bundle_v0

        def mutate_after_capture(*args, **kwargs):
            bundle = original(*args, **kwargs)
            _seed_person(graph, "bob", age=19, score=7)
            return bundle

        with patch(
            "factgraph.sdk.store._build_evaluation_run_bundle_v0",
            side_effect=mutate_after_capture,
        ):
            with self.assertRaisesRegex(SDKStoreError, "view changed"):
                graph.eval.evaluate(compiled, capture="run_bundle_v0")

    def test_run_bundle_cannot_be_attached_to_another_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        first = graph.eval.evaluate(compiled, capture="run_bundle_v0")
        second = graph.eval.evaluate(compiled, capture="run_bundle_v0")

        assert second.run_bundle is not None
        with self.assertRaises(ProtocolShapeError):
            replace(first, run_bundle=second.run_bundle)

    def test_self_consistent_receipt_splice_cannot_be_attached(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        _seed_person(graph, "bob", age=19, score=7)
        compiled, _bundle = _compiled_person_query(graph)
        result = graph.eval.evaluate(compiled, capture="run_bundle_v0")
        bundle = result.run_bundle
        assert bundle is not None and len(bundle.rows) == 2
        first, second = bundle.rows
        row_payload = (
            first.ordinal,
            first.row_id,
            first.claim_digest,
            first.head_scope_digest,
            first.certainty,
            first.certainty_digest,
            first.values,
            second.proof_receipt_digest,
        )
        forged_row = replace(
            first,
            proof_receipt_bytes=second.proof_receipt_bytes,
            proof_receipt_digest=second.proof_receipt_digest,
            row_capture_digest=_bundle_token(
                "evaluation_run_projection_row_v0", row_payload
            ),
        )
        forged_rows = (forged_row, second)
        rows_digest = _bundle_token(
            "evaluation_run_rows_capture_v0",
            tuple(row.row_capture_digest for row in forged_rows),
        )
        bundle_payload = (
            bundle.run_anchor.anchor_digest,
            bundle.query_capture_digest,
            bundle.native_plan.plan_digest,
            bundle.schema_capture_digest,
            bundle.relations_capture_digest,
            rows_digest,
            bundle.execution_contract,
            bundle.integrity,
            bundle.authenticity,
            bundle.privacy,
            bundle.custody,
            bundle.playback,
            bundle.replay_availability,
        )
        forged_bundle = replace(
            bundle,
            rows=forged_rows,
            rows_capture_digest=rows_digest,
            bundle_digest=_bundle_token("evaluation_run_bundle_v0", bundle_payload),
        )

        with self.assertRaisesRegex(ProtocolShapeError, "ProofReceipt"):
            replace(result, run_bundle=forged_bundle)

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
        self.assertIsNotNone(result.run_anchor)
        assert result.run_anchor is not None
        self.assertEqual(result.run_anchor.row_anchors, ())
        self.assertEqual(result.run_anchor.summary.row_count, 0)
        self.assertEqual(result.run_anchor.summary.truth_interpretation, "not_asserted")

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
        assert first_result.run_anchor is not None
        assert repeated_result.run_anchor is not None
        self.assertNotEqual(first_result.run_anchor.run_id, repeated_result.run_anchor.run_id)
        self.assertEqual(
            first_result.run_anchor.summary.summary_anchor_digest,
            repeated_result.run_anchor.summary.summary_anchor_digest,
        )
        self.assertEqual(
            tuple(item.semantic_anchor_digest for item in first_result.run_anchor.row_anchors),
            tuple(item.semantic_anchor_digest for item in repeated_result.run_anchor.row_anchors),
        )

    def test_run_anchor_splicing_fails_closed(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        result = graph.eval.evaluate(compiled)
        anchor = result.run_anchor
        assert anchor is not None

        with self.assertRaises(ProtocolShapeError):
            replace(anchor, result_id="evalr_v1:" + "0" * 64)
        with self.assertRaises(ProtocolShapeError):
            replace(anchor, result_id="evalr_v1:not-a-digest")
        with self.assertRaises(ProtocolShapeError):
            replace(anchor, run_id="run_v1:" + "A" * 64)
        with self.assertRaises(ProtocolShapeError):
            replace(anchor.target, target_id="forged")
        with self.assertRaises(ProtocolShapeError):
            replace(anchor.row_anchors[0], claim_digest="sha256:" + "0" * 64)
        with self.assertRaises(ProtocolShapeError):
            replace(anchor, anchor_digest="")
        with self.assertRaises(ProtocolShapeError):
            replace(
                anchor.row_anchors[0],
                bindings_digest="sha256:" + "0" * 64,
                semantic_anchor_digest="sha256:" + "0" * 64,
            )

        other, _bundle = _compiled_person_query(graph, alias="other")
        other_result = graph.eval.evaluate(other)
        with self.assertRaises(ProtocolShapeError):
            replace(result, run_anchor=other_result.run_anchor)

    def test_self_consistent_run_anchor_splices_still_must_match_result(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph)
        result = graph.eval.evaluate(compiled)
        anchor = result.run_anchor
        assert anchor is not None

        def reseal_anchor(**changes):
            values = tuple(
                changes.get(name, getattr(anchor, name))
                for name in anchor.__dataclass_fields__
                if name != "anchor_digest"
            )
            return replace(
                anchor,
                **changes,
                anchor_digest=_token("evaluation_run_anchor_v0", _plain(values)),
            )

        profile_changes = (
            {"engine": "forged"},
            {"engine_version": "forged"},
            {"adapter_version": "forged"},
            {"config_digest": "sha256:" + "0" * 64},
        )
        forged_anchors = [
            reseal_anchor(evaluated_at="2099-01-01T00:00:00+00:00"),
            *(
                reseal_anchor(execution_profile=replace(anchor.execution_profile, **change))
                for change in profile_changes
            ),
        ]

        original_row = anchor.row_anchors[0]
        for change in (
            {"claim_kind": "fact_triple"},
            {"bindings_digest": "sha256:" + "0" * 64},
            {"certainty_digest": "sha256:" + "0" * 64},
        ):
            row_values = tuple(
                change.get(name, getattr(original_row, name))
                for name in original_row.__dataclass_fields__
                if name != "semantic_anchor_digest"
            )
            forged_row = replace(
                original_row,
                **change,
                semantic_anchor_digest=_token("evaluation_run_row_anchor_v0", row_values[2:]),
            )
            summary_values = (
                anchor.query_digest, 1, (forged_row.semantic_anchor_digest,),
                "not_asserted", "unknown", "unspecified",
            )
            forged_summary = replace(
                anchor.summary,
                row_anchor_digests=summary_values[2],
                summary_anchor_digest=_token("evaluation_run_summary_anchor_v0", summary_values),
            )
            forged_anchors.append(
                reseal_anchor(row_anchors=(forged_row,), summary=forged_summary)
            )

        for forged in forged_anchors:
            with self.subTest(forged=forged):
                with self.assertRaises(ProtocolShapeError):
                    replace(result, run_anchor=forged)

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
        original = graph._derivation_outputs_to_evaluate_result

        def mutate_after_adaptation(*args, **kwargs):
            result = original(*args, **kwargs)
            _seed_person(graph, "bob", age=19, score=7)
            return result

        with patch.object(
            graph,
            "_derivation_outputs_to_evaluate_result",
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

        scenario_result = graph.eval.evaluate(
            compiled,
            scenario=ScenarioFieldSubstitutionV0(
                EntityRef("Record", {"record_id": "r1"}),
                FieldPath("Record", "observed_at"),
                456,
                "time-value-only",
            ),
        )
        self.assertEqual(
            scenario_result[0].bindings["observed_at"],
            {"kind": "literal", "tag": "time", "value": 456},
        )
        assert scenario_result.scenario is not None
        self.assertEqual(scenario_result.scenario.effective_value.tag, "time")

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


class EvaluationQueryScenarioFieldSubstitutionTests(unittest.TestCase):
    def _scenario(self, *, value: object, field: FieldPath | None = None) -> ScenarioFieldSubstitutionV0:
        return ScenarioFieldSubstitutionV0(
            entity=EntityRef("Person", {"employee_id": "alice"}, encoded_ref="idref_v1:Person:forged"),
            field=field or FieldPath("Person", "age"),
            value=value,
            premise_id="review-age-hypothesis",
        )

    @staticmethod
    def _support_state(graph: SDKStore) -> tuple[object, ...]:
        store = graph._store
        return (
            dict(store._support_artifacts),
            dict(store._candidate_support_index),
            dict(store._candidate_support_kind_index),
            dict(store._candidate_confidence_kind_index),
            dict(store._candidate_pred_index),
        )

    def test_scenario_replaces_one_existing_field_with_same_query_evaluator_and_no_persistence(self) -> None:
        graph = SDKStore([Person])
        alice_ref = _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(
            graph,
            employee_id="alice",
            selections=(("person", "person"), ("age", "age"), ("score", "score")),
        )
        claims_before = tuple(graph.ledger.find_claims())
        support_before = self._support_state(graph)

        import factgraph.sdk.store as store_module

        with patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation",
            wraps=store_module._evaluate_derivation_plans_with_native_effective_relation,
        ) as evaluator, patch.object(
            graph._store,
            "_remember_support_artifact",
            wraps=graph._store._remember_support_artifact,
        ) as remember_artifact, patch.object(
            graph._store,
            "_remember_candidate_support",
            wraps=graph._store._remember_candidate_support,
        ) as remember_candidate:
            result = graph.eval.evaluate(compiled, scenario=self._scenario(value=35))

        self.assertEqual(evaluator.call_count, 2)
        self.assertIs(evaluator.call_args_list[0].args[0].plans[0], evaluator.call_args_list[1].args[0].plans[0])
        remember_artifact.assert_not_called()
        remember_candidate.assert_not_called()
        self.assertIsInstance(result, EvaluateResult)
        self.assertIsNone(result.run_anchor)
        self.assertIsNone(result.run_bundle)
        self.assertEqual(dict(result[0].bindings)["person"], {"kind": "entity_ref", "value": alice_ref})
        self.assertEqual(dict(result[0].bindings)["age"], {"kind": "literal", "tag": "int", "value": 35})
        self.assertEqual(dict(result[0].bindings)["score"], {"kind": "literal", "tag": "int", "value": 9})
        assert result.scenario is not None
        self.assertEqual(result.scenario.entity_ref, alice_ref)
        self.assertEqual(result.scenario.baseline_value.value, 22)
        self.assertEqual(result.scenario.effective_value.value, 35)
        self.assertTrue(result.scenario.semantic_value_changed)
        self.assertTrue(result.scenario.effective_source_changed)
        self.assertIsNotNone(result.scenario.result_diff)
        assert result.scenario.result_diff is not None
        self.assertTrue(result.scenario.result_diff.result_changed)
        self.assertEqual(tuple(graph.ledger.find_claims()), claims_before)
        self.assertEqual(self._support_state(graph), support_before)
        self.assertEqual(
            dict(graph.eval.evaluate(compiled)[0].bindings)["age"],
            {"kind": "literal", "tag": "int", "value": 22},
        )

    def test_same_value_and_unselected_change_are_distinguished_from_result_change(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        selected_age, _bundle = _compiled_person_query(graph, employee_id="alice")
        same = graph.eval.evaluate(selected_age, scenario=self._scenario(value=22))
        assert same.scenario is not None and same.scenario.result_diff is not None
        self.assertFalse(same.scenario.semantic_value_changed)
        self.assertTrue(same.scenario.effective_source_changed)
        self.assertFalse(same.scenario.result_diff.result_changed)

        selected_score, _bundle = _compiled_person_query(
            graph,
            employee_id="alice",
            selections=(("score", "score"),),
        )
        unselected = graph.eval.evaluate(selected_score, scenario=self._scenario(value=35))
        assert unselected.scenario is not None and unselected.scenario.result_diff is not None
        self.assertTrue(unselected.scenario.semantic_value_changed)
        self.assertFalse(unselected.scenario.result_diff.result_changed)

    def test_scenario_disables_ledger_evidence_closure_and_capture(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph, employee_id="alice")
        result = graph.eval.evaluate(compiled, scenario=self._scenario(value=35))
        with self.assertRaisesRegex(DetachedRowError, "ScenarioFieldSubstitutionV0"):
            result[0].close()
        explanation = result[0].explain()
        self.assertEqual(explanation.status, "unsupported")
        self.assertIn("ScenarioFieldSubstitutionV0", explanation.errors[0].message)
        for capture in (None, "run_bundle_v0"):
            with self.subTest(capture=capture), self.assertRaisesRegex(
                SDKStoreError,
                "does not support capture",
            ):
                graph.eval.evaluate(compiled, scenario=self._scenario(value=35), capture=capture)
        ordinary = graph.eval.evaluate(compiled)
        self.assertIsNotNone(ordinary.run_anchor)
        self.assertEqual(ordinary[0].explain().status, "passed")
        self.assertIsInstance(ordinary[0].close(), Rule)

    def test_scenario_rejects_invalid_target_shape_and_value_before_execution(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph, employee_id="alice")
        import factgraph.sdk.store as store_module

        for scenario, expected in (
            (self._scenario(value=True), "SCENARIO_VALUE_TYPE_MISMATCH"),
            (self._scenario(value="22"), "SCENARIO_VALUE_TYPE_MISMATCH"),
            (self._scenario(value=35, field=FieldPath("Person", "employee_id")), "SCENARIO_FIELD_UNSUPPORTED"),
            (self._scenario(value=35, field=FieldPath("Person", "unrelated")), "SCENARIO_TARGET_OUTSIDE_QUERY"),
        ):
            with self.subTest(expected=expected), patch(
                "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation",
                wraps=store_module._evaluate_derivation_plans_with_native_effective_relation,
            ) as evaluator, self.assertRaisesRegex(SDKStoreError, expected):
                graph.eval.evaluate(compiled, scenario=scenario)
            evaluator.assert_not_called()

    def test_scenario_rejects_missing_visible_target_and_view_change(self) -> None:
        graph = SDKStore([Person])
        _seed_person(graph, "alice", age=22, score=9)
        compiled, _bundle = _compiled_person_query(graph, employee_id="alice")
        age_pred = field_predicate(build_schema_index(graph.schema_ir), "Person", "age").pred_id
        import factgraph.application.evaluation_scenario_runtime as scenario_runtime
        import factgraph.sdk.store as store_module

        original_projector = scenario_runtime.project_view_facts_with_witness
        missing_target = original_projector(graph.ledger, graph.schema_ir)
        missing_target[age_pred] = []
        with patch.object(
            scenario_runtime,
            "project_view_facts_with_witness",
            return_value=missing_target,
        ), self.assertRaisesRegex(SDKStoreError, "SCENARIO_TARGET_UNAVAILABLE"):
            graph.eval.evaluate(compiled, scenario=self._scenario(value=35))

        ambiguous_target = original_projector(graph.ledger, graph.schema_ir)
        ambiguous_target[age_pred] = [
            *ambiguous_target[age_pred],
            ambiguous_target[age_pred][0],
        ]
        with patch.object(
            scenario_runtime,
            "project_view_facts_with_witness",
            return_value=ambiguous_target,
        ), patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation",
            wraps=store_module._evaluate_derivation_plans_with_native_effective_relation,
        ) as evaluator, self.assertRaisesRegex(SDKStoreError, "SCENARIO_TARGET_UNAVAILABLE"):
            graph.eval.evaluate(compiled, scenario=self._scenario(value=35))
        evaluator.assert_not_called()

        original_evaluator = store_module._evaluate_derivation_plans_with_native_effective_relation
        call_count = 0

        def mutate_after_baseline(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            outputs = original_evaluator(*args, **kwargs)
            if call_count == 1:
                _seed_person(graph, "bob", age=19, score=7)
            return outputs

        with patch(
            "factgraph.sdk.store._evaluate_derivation_plans_with_native_effective_relation",
            side_effect=mutate_after_baseline,
        ), self.assertRaisesRegex(SDKStoreError, "view changed"):
            graph.eval.evaluate(compiled, scenario=self._scenario(value=35))
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
