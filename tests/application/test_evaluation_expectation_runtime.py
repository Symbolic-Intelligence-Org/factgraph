from __future__ import annotations

import unittest

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    manage_rule_occurrence,
)
from factgraph.application.evaluation_expectation_runtime import (
    EvaluationExpectationError,
    compile_contains_row_expectations_v0,
    evaluate_contains_row_expectations_v0,
)
from factgraph.application.protocol import (
    ContainsRowExpectationV0,
    EvaluationQuery,
    EvaluationQuerySelection,
    Policy,
    PolicyOccurrence,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.evaluate_result import (
    BOOLEAN_CERTAINTY,
    EvaluateResult,
    EvaluateRow,
    ResultFingerprint,
    claim_digest_for,
    closed_head_digest_for,
    result_digest_for,
    result_id_for,
    row_id_for,
)
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _address(port: str) -> SemanticPortAddress:
    return SemanticPortAddress("person", port)


def _compiled():
    index = build_schema_index(compile_schema_from_classes([Person], generated_at="2026-08-13T00:00:00Z"))
    person, age = Var("$person"), Var("$age")
    bundle = build_resolved_rule(
        id="person_age",
        version="1",
        when=(PredAtom("Person:exists", [person]), PredAtom("person:age", [person, age])),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
    policy = compile_policy(Policy("people", PolicyOccurrence("person")), address_space=space)
    query = compile_evaluation_query(
        EvaluationQuery(policy.policy_digest, (EvaluationQuerySelection("age", _address("age")),)),
        compiled_policy=policy,
        address_space=space,
        schema_index=index,
    )
    return index, space, query


def _result(query, *, age: int | None) -> EvaluateResult:
    run_id = "run_v1:" + "1" * 64
    expr_digest = f"sha256:{query.query_digest}"
    rule_set = sha256_token(b"rules")
    view = sha256_token(b"view")
    result_id = result_id_for(
        run_id=run_id,
        expr_digest=expr_digest,
        rule_set_digest=rule_set,
        view_snapshot_digest=view,
        config_digest=None,
        engine="native",
        head_id=query.projection_head.id,
        head_content_digest=query.projection_head.content_digest,
    )
    rows = ()
    if age is not None:
        bindings = {"age": {"kind": "literal", "tag": "int", "value": age}}
        rows = (
            EvaluateRow(
                row_id=row_id_for(run_id, bindings),
                bindings=bindings,
                kind="projection",
                digest=claim_digest_for("projection", query.projection_head.id, bindings),
                closed_head_digest=closed_head_digest_for(query.projection_head),
                certainty=BOOLEAN_CERTAINTY,
            ),
        )
    result_digest = result_digest_for(
        result_id=result_id,
        run_id=run_id,
        row_digests=(),
        head_id=query.projection_head.id,
        head_content_digest=query.projection_head.content_digest,
        engine="native",
        engine_version=None,
        adapter_version=None,
        expr_digest=expr_digest,
        rule_set_digest=rule_set,
        view_snapshot_digest=view,
        config_digest=None,
    )
    return EvaluateResult(
        result_id=result_id,
        rows=rows,
        head=query.projection_head,
        engine="native",
        evaluated_at="now",
        fingerprint=ResultFingerprint(expr_digest, rule_set, view, None, result_digest, run_id),
        engine_meta={"engine_version": None, "adapter_version": None},
    )


class EvaluationExpectationRuntimeTests(unittest.TestCase):
    def test_compilation_uses_selected_alias_domains(self) -> None:
        index, space, query = _compiled()
        compiled = compile_contains_row_expectations_v0(
            (ContainsRowExpectationV0("age_is_19", (("age", 19),)),),
            compiled_query=query,
            address_space=space,
            schema_index=index,
        )
        self.assertEqual(compiled[0].values[0].value_type, "int")
        with self.assertRaisesRegex(EvaluationExpectationError, "not selected"):
            compile_contains_row_expectations_v0(
                (ContainsRowExpectationV0("bad", (("missing", 19),)),),
                compiled_query=query,
                address_space=space,
                schema_index=index,
            )
        with self.assertRaisesRegex(EvaluationExpectationError, "incompatible"):
            compile_contains_row_expectations_v0(
                (ContainsRowExpectationV0("bad-type", (("age", True),)),),
                compiled_query=query,
                address_space=space,
                schema_index=index,
            )

    def test_truth_table_keeps_unknown_distinct_from_complete_negative(self) -> None:
        index, space, query = _compiled()
        expectations = compile_contains_row_expectations_v0(
            (ContainsRowExpectationV0("age_is_19", (("age", 19),)),),
            compiled_query=query,
            address_space=space,
            schema_index=index,
        )
        matching = evaluate_contains_row_expectations_v0(
            expectations,
            result=_result(query, age=19),
            targeted_query_wrapper_digest=sha256_token(b"wrapper"),
            completeness_basis="unknown",
        )
        self.assertEqual(matching[0].status, "satisfied")
        complete_negative = evaluate_contains_row_expectations_v0(
            expectations,
            result=_result(query, age=None),
            targeted_query_wrapper_digest=sha256_token(b"wrapper"),
            completeness_basis="complete_native_enumeration_v0",
        )
        self.assertEqual(complete_negative[0].status, "not_satisfied")
        unknown = evaluate_contains_row_expectations_v0(
            expectations,
            result=_result(query, age=None),
            targeted_query_wrapper_digest=sha256_token(b"wrapper"),
            completeness_basis="unknown",
        )
        self.assertEqual(unknown[0].status, "underdetermined")
        unsupported = evaluate_contains_row_expectations_v0(
            expectations,
            result=_result(query, age=None),
            targeted_query_wrapper_digest=sha256_token(b"wrapper"),
            completeness_basis="unsupported",
        )
        self.assertEqual(unsupported[0].status, "unsupported")
