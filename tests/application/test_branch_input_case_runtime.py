from __future__ import annotations

import unittest

from factgraph.application.branch_input_case_runtime import (
    BranchAwareInputCaseDefinitionV1,
    BranchInputCaseError,
    BranchSemanticMappingV1,
    InputCaseFieldDefinitionV1,
    ResultCaseFieldDefinitionV1,
    compile_branch_aware_input_case_v1,
    instantiate_compiled_input_case_v1,
)
from factgraph.application.evaluation_query_target_runtime import (
    resolve_evaluation_query_target,
)
from factgraph.application.goal_plan_v2_runtime import (
    ProductEvaluationRuntimeErrorV2,
    ProductInvocationAggregateLimitsV2,
    build_product_evaluation_invocation_v2,
    replay_product_evaluation_run_v2,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_evidence_capture_v2 import (
    EvaluationEvidenceArtifactV2,
    evaluation_evidence_artifact_from_bytes_v2,
    project_evaluation_evidence_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import AssetMeta, Entity, Field, Identity, SDKStore


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _fixture():
    graph = SDKStore([Person])
    alice = graph.entities.create(Person, person_id="alice")
    set_field(graph.ledger, "person:age", alice, [("int", 20)])
    person, age = Var("$person"), Var("$age")
    rule = graph.build_rule(
        id="person_values",
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
    builder = graph.policy_builder("two_paths", version="1", meta=AssetMeta(name="Two paths"))
    left = builder.use(rule, as_="left")
    right = builder.use(rule, as_="right")
    product = builder.build(builder.any(left, right))
    target = resolve_evaluation_query_target(
        product.policy,
        address_space=product.address_space,
        schema_index=graph._application_schema_index,
    )
    branch_ids = tuple(branch.branch_id for branch in target.compiled_policy.branches)
    definition = BranchAwareInputCaseDefinitionV1(
        case_key="person",
        applicable_branch_ids=branch_ids,
        inputs=(
            InputCaseFieldDefinitionV1(
                "person",
                True,
                tuple(
                    BranchSemanticMappingV1(branch_id, SemanticPortAddress(alias, "person"))
                    for branch_id, alias in zip(branch_ids, ("left", "right"), strict=True)
                ),
            ),
        ),
        results=(
            ResultCaseFieldDefinitionV1(
                "age",
                True,
                tuple(
                    BranchSemanticMappingV1(branch_id, SemanticPortAddress(alias, "age"))
                    for branch_id, alias in zip(branch_ids, ("left", "right"), strict=True)
                ),
            ),
        ),
    )
    template = compile_branch_aware_input_case_v1(
        definition,
        target=target,
        schema_index=graph._application_schema_index,
    )
    return graph, product, template, branch_ids


class BranchInputCaseRuntimeTests(unittest.TestCase):
    def test_case_is_total_and_retains_two_branch_witnesses_for_one_row(self) -> None:
        graph, product, template, branch_ids = _fixture()
        targeted = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "alice"})},
        )
        profile = graph.execution.native_deterministic(target=product).build()
        run = build_product_evaluation_invocation_v2(
            graph=graph,
            primary=targeted,
            product_target=product,
            profile=profile,
            aggregate_limits=ProductInvocationAggregateLimitsV2(
                timeout_ms=30_000,
                max_rows=10,
                max_units=20,
                max_evidence_bytes=20_000,
                max_capture_bytes=1_000_000,
                max_scenarios=1,
            ),
        ).run()

        frame = run.effective.engine_frames[0]
        self.assertEqual(len(frame.observations), 1)
        self.assertEqual(
            {item.compiled_branch_id for item in frame.branch_witnesses},
            set(branch_ids),
        )
        self.assertEqual(len(frame.branch_witnesses), 2)
        self.assertEqual(
            {item.row_identity_digest for item in frame.branch_witnesses},
            {frame.observations[0].row_identity_digest},
        )
        self.assertEqual(run.evidence_capture.availability, "available")
        artifact = run.evidence_capture.artifact
        self.assertIsInstance(artifact, EvaluationEvidenceArtifactV2)
        assert artifact is not None
        restored = evaluation_evidence_artifact_from_bytes_v2(artifact.to_bytes())
        graph.close()
        evidence = project_evaluation_evidence_v2(
            restored,
            run_digest=run.run_digest,
            side="effective",
            engine="native",
            observation_digest=frame.observations[0].observation_digest,
        )
        self.assertEqual(evidence.subject_binding["age"], 20)
        self.assertEqual(len(evidence.paths), 2)
        self.assertEqual(replay_product_evaluation_run_v2(run).status, "matched")

    def test_retained_evidence_rejects_target_and_byte_substitution(self) -> None:
        graph, product, template, _branch_ids = _fixture()
        targeted = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "alice"})},
        )
        run = build_product_evaluation_invocation_v2(
            graph=graph,
            primary=targeted,
            product_target=product,
            profile=graph.execution.native_deterministic(target=product).build(),
            aggregate_limits=ProductInvocationAggregateLimitsV2(
                max_evidence_bytes=20_000,
                max_capture_bytes=1_000_000,
            ),
        ).run()
        artifact = run.evidence_capture.artifact
        assert artifact is not None
        with self.assertRaises(ProtocolShapeError):
            project_evaluation_evidence_v2(
                artifact,
                run_digest="sha256:" + "0" * 64,
                side="effective",
                engine="native",
                observation_digest=run.effective.engine_frames[0].observations[0].observation_digest,
            )
        raw = bytearray(artifact.to_bytes())
        raw[-2] = ord("0") if raw[-2] != ord("0") else ord("1")
        with self.assertRaises(ProtocolShapeError):
            evaluation_evidence_artifact_from_bytes_v2(bytes(raw))

    def test_evidence_availability_is_explicit_for_zero_rows_and_no_budget(self) -> None:
        graph, product, template, _branch_ids = _fixture()
        missing = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "missing"})},
        )
        zero = build_product_evaluation_invocation_v2(
            graph=graph,
            primary=missing,
            product_target=product,
            profile=graph.execution.native_deterministic(target=product).build(),
            aggregate_limits=ProductInvocationAggregateLimitsV2(
                max_evidence_bytes=20_000,
                max_capture_bytes=1_000_000,
            ),
        ).run()
        self.assertEqual(zero.evidence_capture.availability, "zero_row")
        present = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "alice"})},
        )
        not_requested = build_product_evaluation_invocation_v2(
            graph=graph,
            primary=present,
            product_target=product,
            profile=graph.execution.native_deterministic(target=product).build(),
            aggregate_limits=ProductInvocationAggregateLimitsV2(
                max_evidence_bytes=None,
                max_capture_bytes=1_000_000,
            ),
        ).run()
        self.assertEqual(not_requested.evidence_capture.availability, "not_requested")

    def test_evidence_budget_fails_the_whole_invocation(self) -> None:
        graph, product, template, _branch_ids = _fixture()
        targeted = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "alice"})},
        )
        with self.assertRaises(ProductEvaluationRuntimeErrorV2) as raised:
            build_product_evaluation_invocation_v2(
                graph=graph,
                primary=targeted,
                product_target=product,
                profile=graph.execution.native_deterministic(target=product).build(),
                aggregate_limits=ProductInvocationAggregateLimitsV2(
                    max_evidence_bytes=1,
                    max_capture_bytes=1_000_000,
                ),
            ).run()
        self.assertEqual(
            raised.exception.code,
            "PRODUCT_INVOCATION_AGGREGATE_LIMIT_EXCEEDED",
        )

    def test_missing_required_value_never_instantiates_unconstrained_query(self) -> None:
        _graph, _product, template, _branch_ids = _fixture()
        with self.assertRaises(BranchInputCaseError) as raised:
            instantiate_compiled_input_case_v1(template, values={})
        self.assertEqual(raised.exception.code, "INPUT_CASE_REQUIRED_VALUE_MISSING")

    def test_aggregate_limit_fails_the_whole_invocation(self) -> None:
        graph, product, template, _branch_ids = _fixture()
        targeted = instantiate_compiled_input_case_v1(
            template,
            values={"person": EntityRef("Person", {"person_id": "alice"})},
        )
        with self.assertRaises(ProductEvaluationRuntimeErrorV2) as raised:
            build_product_evaluation_invocation_v2(
                graph=graph,
                primary=targeted,
                product_target=product,
                profile=graph.execution.native_deterministic(target=product).build(),
                aggregate_limits=ProductInvocationAggregateLimitsV2(max_rows=0),
            ).run()
        self.assertEqual(
            raised.exception.code,
            "PRODUCT_INVOCATION_AGGREGATE_LIMIT_EXCEEDED",
        )


if __name__ == "__main__":
    unittest.main()
