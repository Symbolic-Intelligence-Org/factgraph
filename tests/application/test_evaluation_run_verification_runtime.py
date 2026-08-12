from __future__ import annotations

from dataclasses import fields, replace
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
    verify_evaluation_run_bundle,
)
from factgraph.application.evaluation_run_verification_runtime import (
    MAX_EVALUATION_RUN_VERIFICATION_WORK,
    _estimate_verification_work,
)
from factgraph.application.protocol import (
    EntitySelector,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    EvaluationRunVerificationV0,
    Policy,
    PolicyOccurrence,
    ProtocolShapeError,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.evaluation_run import _plain, _token as _anchor_token
from factgraph.application.protocol.evaluation_run_bundle import _token as _bundle_token
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.ruleref_substrate import NativeWhereEvaluation
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    score: int = Field()


def _capture(*, score: int | None = None):
    graph = SDKStore([Person])
    index = build_schema_index(graph.schema_ir)
    info = entity_info(index, "Person")
    for employee_id, age, person_score in (("alice", 22, 9), ("bob", 19, 7)):
        ref = (
            resolve_selector(
                EntitySelector(entity_type="Person", identity={"employee_id": employee_id}),
                index=index,
            ).encoded_ref
            or ""
        )
        set_field(graph.ledger, info.exists_predicate_id, ref, [])
        set_field(
            graph.ledger,
            info.identity_predicates["employee_id"].pred_id,
            ref,
            [("string", employee_id)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Person", "age").pred_id,
            ref,
            [("int", age)],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "Person", "score").pred_id,
            ref,
            [("int", person_score)],
        )
    person, age, score_var = Var("$person"), Var("$age"), Var("$score")
    resolved = build_resolved_rule(
        id="person_values",
        version="1",
        when=(
            PredAtom(info.exists_predicate_id, [person]),
            PredAtom(field_predicate(index, "Person", "age").pred_id, [person, age]),
            PredAtom(
                field_predicate(index, "Person", "score").pred_id,
                [person, score_var],
            ),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            "score": SemanticRulePort(score_var, field_endpoint("Person", "score")),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(resolved, "person"),))
    policy = compile_policy(
        Policy("people", PolicyOccurrence("person")),
        address_space=space,
    )
    query = EvaluationQuery(
        policy.policy_digest,
        (
            EvaluationQuerySelection("person", SemanticPortAddress("person", "person")),
            EvaluationQuerySelection("age", SemanticPortAddress("person", "age")),
        ),
        (
            ()
            if score is None
            else (
                EvaluationQueryBinding(
                    SemanticPortAddress("person", "score"),
                    score,
                ),
            )
        ),
    )
    compiled = compile_evaluation_query(
        query,
        compiled_policy=policy,
        address_space=space,
        schema_index=index,
    )
    result = graph.eval.evaluate(compiled, capture="run_bundle_v0")
    assert result.run_bundle is not None
    return graph, resolved.rule, result.run_bundle


def _with_unpinned_profile(bundle):
    anchor = bundle.run_anchor
    profile = replace(
        anchor.execution_profile,
        engine_version=None,
        adapter_version=None,
        version_pinning="incomplete",
    )
    return _with_profile(bundle, profile)


def _with_profile(bundle, profile):
    anchor = bundle.run_anchor
    anchor_values = tuple(
        profile if name == "execution_profile" else getattr(anchor, name)
        for name in anchor.__dataclass_fields__
        if name != "anchor_digest"
    )
    next_anchor = replace(
        anchor,
        execution_profile=profile,
        anchor_digest=_anchor_token("evaluation_run_anchor_v0", _plain(anchor_values)),
    )
    bundle_values = (
        next_anchor.anchor_digest,
        bundle.query_capture_digest,
        bundle.native_plan.plan_digest,
        bundle.schema_capture_digest,
        bundle.relations_capture_digest,
        bundle.rows_capture_digest,
        bundle.execution_contract,
        bundle.integrity,
        bundle.authenticity,
        bundle.privacy,
        bundle.custody,
        bundle.playback,
        bundle.replay_availability,
    )
    return replace(
        bundle,
        run_anchor=next_anchor,
        bundle_digest=_bundle_token("evaluation_run_bundle_v0", bundle_values),
    )


def _with_self_sealed_inconsistent_row(bundle):
    """Forge a DTO-sealed row whose values no longer match its Run anchor."""
    row = bundle.rows[0]
    changed_value = replace(row.values[-1][1], value=23)
    changed_values = (*row.values[:-1], (row.values[-1][0], changed_value))
    row_payload = (
        row.ordinal,
        row.row_id,
        row.claim_digest,
        row.head_scope_digest,
        row.certainty,
        row.certainty_digest,
        changed_values,
        row.proof_receipt_digest,
    )
    changed_row = replace(
        row,
        values=changed_values,
        row_capture_digest=_bundle_token("evaluation_run_projection_row_v0", row_payload),
    )
    rows = (changed_row, *bundle.rows[1:])
    rows_capture_digest = _bundle_token(
        "evaluation_run_rows_capture_v0", tuple(item.row_capture_digest for item in rows)
    )
    bundle_values = (
        bundle.run_anchor.anchor_digest,
        bundle.query_capture_digest,
        bundle.native_plan.plan_digest,
        bundle.schema_capture_digest,
        bundle.relations_capture_digest,
        rows_capture_digest,
        bundle.execution_contract,
        bundle.integrity,
        bundle.authenticity,
        bundle.privacy,
        bundle.custody,
        bundle.playback,
        bundle.replay_availability,
    )
    return replace(
        bundle,
        rows=rows,
        rows_capture_digest=rows_capture_digest,
        bundle_digest=_bundle_token("evaluation_run_bundle_v0", bundle_values),
    )


class EvaluationRunVerificationRuntimeTests(unittest.TestCase):
    def test_declared_runtime_verifies_semantic_and_support_multisets(self) -> None:
        graph, _rule, bundle = _capture()
        graph.close()

        first = verify_evaluation_run_bundle(bundle)
        second = verify_evaluation_run_bundle(bundle)

        self.assertEqual(first.verdict, "matched_declared_runtime")
        self.assertEqual(first.semantic_comparison, "match")
        self.assertEqual(first.support_comparison, "match")
        self.assertEqual(first.observed_row_count, 2)
        self.assertEqual(first.verification_digest, second.verification_digest)
        self.assertEqual(first.source_authenticity, "unverified")
        self.assertFalse(
            {"run_id", "result_id", "row_id"}
            & {item.name for item in fields(EvaluationRunVerificationV0)}
        )
        self.assertFalse(hasattr(first, "replay"))
        self.assertFalse(hasattr(first, "explain"))
        with self.assertRaisesRegex(ProtocolShapeError, "comparisons"):
            replace(
                first,
                semantic_comparison="mismatch",
                verification_digest=first.verification_digest,
            )

    def test_zero_rows_match_without_interpreting_false(self) -> None:
        _graph, _rule, bundle = _capture(score=999)

        record = verify_evaluation_run_bundle(bundle)

        self.assertEqual(record.verdict, "matched_declared_runtime")
        self.assertEqual((record.expected_row_count, record.observed_row_count), (0, 0))

    def test_old_unpinned_bundle_has_explicitly_weaker_match(self) -> None:
        _graph, _rule, bundle = _capture()

        record = verify_evaluation_run_bundle(_with_unpinned_profile(bundle))

        self.assertEqual(record.verdict, "matched_unpinned_runtime")
        self.assertEqual(record.runtime_compatibility, "source_unpinned")
        self.assertEqual(record.reason_codes, ("SOURCE_RUNTIME_UNPINNED",))

    def test_runtime_or_gate_mismatch_does_not_execute(self) -> None:
        _graph, _rule, bundle = _capture()
        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "NATIVE_WHERE_SEMANTICS_VERSION",
                "native_where_future",
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where"
            ) as evaluator,
        ):
            record = verify_evaluation_run_bundle(bundle)
        evaluator.assert_not_called()
        self.assertEqual(record.verdict, "runtime_incompatible")
        self.assertIn("ENGINE_VERSION_MISMATCH", record.reason_codes)

        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime._where_ast_gate_enabled",
                return_value=False,
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where"
            ) as evaluator,
        ):
            record = verify_evaluation_run_bundle(bundle)
        evaluator.assert_not_called()
        self.assertEqual(record.verdict, "runtime_incompatible")
        self.assertIn("WHERE_AST_GATE_MISMATCH", record.reason_codes)

        forged_profile = replace(
            bundle.run_anchor.execution_profile,
            engine="souffle",
            config_digest="sha256:" + "1" * 64,
        )
        with patch(
            "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where"
        ) as evaluator:
            record = verify_evaluation_run_bundle(_with_profile(bundle, forged_profile))
        evaluator.assert_not_called()
        self.assertEqual(record.verdict, "runtime_incompatible")
        self.assertIn("ENGINE_PROFILE_MISMATCH", record.reason_codes)
        self.assertIn("CONFIG_PROFILE_MISMATCH", record.reason_codes)

    def test_work_budget_rejects_before_evaluation(self) -> None:
        _graph, _rule, bundle = _capture()
        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "_estimate_verification_work",
                return_value=MAX_EVALUATION_RUN_VERIFICATION_WORK + 1,
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where"
            ) as evaluator,
        ):
            record = verify_evaluation_run_bundle(bundle)

        evaluator.assert_not_called()
        self.assertEqual(record.verdict, "resource_rejected")
        self.assertEqual(record.execution_status, "not_run")
        self.assertEqual(
            _estimate_verification_work(
                [
                    ("pred", "left", ["$left"]),
                    ("pred", "right", ["$right"]),
                ],
                {"left": 400, "right": 400},
            ),
            MAX_EVALUATION_RUN_VERIFICATION_WORK + 1,
        )
        self.assertGreaterEqual(
            _estimate_verification_work(
                [("not", [("pred", "blocked", ["$person"])])],
                {"blocked": 7},
            ),
            7,
        )
        self.assertGreaterEqual(
            _estimate_verification_work(
                [("eq", "$n", ("count", None, [("pred", "item", ["$x"])]))],
                {"item": 5},
            ),
            5,
        )

    def test_work_budget_includes_per_binding_receipt_reconstruction(self) -> None:
        # One raw native binding per fact can collapse to a single projected row.
        # The verifier still has to select a branch and rebuild a ProofReceipt for
        # every raw binding, so this must be rejected before the evaluator runs.
        where = [("pred", "many", ["$value"])]
        estimate = _estimate_verification_work(where, {"many": 200})
        self.assertGreater(estimate, MAX_EVALUATION_RUN_VERIFICATION_WORK)

        _graph, _rule, bundle = _capture()
        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "_preflight_verification_input",
                return_value=(where, {"many": 200}),
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "evaluate_native_where"
            ) as evaluator,
        ):
            record = verify_evaluation_run_bundle(bundle)

        evaluator.assert_not_called()
        self.assertEqual(record.verdict, "resource_rejected")
        self.assertGreater(record.estimated_work, record.work_limit)

    def test_static_bundle_inconsistency_cannot_be_masked_by_early_exit(self) -> None:
        _graph, _rule, bundle = _capture()
        forged = _with_self_sealed_inconsistent_row(bundle)

        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "NATIVE_WHERE_SEMANTICS_VERSION",
                "native_where_future",
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "evaluate_native_where"
            ) as evaluator,
        ):
            with self.assertRaisesRegex(ProtocolShapeError, "projection values"):
                verify_evaluation_run_bundle(forged)
        evaluator.assert_not_called()

        with (
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "_estimate_verification_work",
                return_value=MAX_EVALUATION_RUN_VERIFICATION_WORK + 1,
            ),
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "evaluate_native_where"
            ) as evaluator,
        ):
            with self.assertRaisesRegex(ProtocolShapeError, "projection values"):
                verify_evaluation_run_bundle(forged)
        evaluator.assert_not_called()

    def test_semantic_support_and_execution_failures_are_distinct(self) -> None:
        _graph, _rule, bundle = _capture()
        with patch(
            "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where",
            return_value=NativeWhereEvaluation(bindings=[]),
        ):
            semantic = verify_evaluation_run_bundle(bundle)
        self.assertEqual(semantic.verdict, "semantic_mismatch")
        self.assertEqual(semantic.support_comparison, "mismatch")

        with patch(
            "factgraph.application.evaluation_run_verification_runtime.compute_support_digest",
            return_value="sha256:" + "0" * 64,
        ):
            support = verify_evaluation_run_bundle(bundle)
        self.assertEqual(support.verdict, "support_mismatch")
        self.assertEqual(support.semantic_comparison, "match")

        with patch(
            "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where",
            side_effect=WhereValidationError("boom"),
        ):
            failed = verify_evaluation_run_bundle(bundle)
        self.assertEqual(failed.verdict, "execution_failed")
        self.assertEqual(failed.execution_status, "failed")

    def test_stable_pins_apply_only_to_compiled_evaluation_query(self) -> None:
        graph, rule, bundle = _capture()
        profile = bundle.run_anchor.execution_profile
        self.assertEqual(profile.engine_version, "native_where_v1")
        self.assertEqual(profile.adapter_version, "evaluation_query_projection_v0")
        self.assertEqual(profile.version_pinning, "complete")

        legacy = graph.eval.evaluate(rule, head=rule, engine="native")
        self.assertEqual(
            dict(legacy.engine_meta),
            {"engine_version": None, "adapter_version": None},
        )


if __name__ == "__main__":
    unittest.main()
