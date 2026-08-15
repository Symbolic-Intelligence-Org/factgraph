from __future__ import annotations

from copy import deepcopy
import unittest

from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v2 import (
    EvaluationReplayPayloadV2,
    EvaluationReplayWorldV2,
    evaluation_replay_payload_v2_bytes,
    evaluation_replay_payload_v2_from_bytes,
)
from factgraph.application.protocol.execution_profile_v2 import (
    EvaluationEnginePinV2,
    EvaluationExecutionProfileV2,
    EvaluationResourcePolicyV2,
    EvaluationTargetPinV2,
    ExecutionAttachmentSemanticsV2,
    ExecutionAttachmentV2,
    ProbLogPointSemanticsV2,
    DeterministicSemanticsV2,
)
from factgraph.application.protocol.scenario_v1 import (
    ScenarioEnsureMemberV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    ScenarioWithoutFieldV1,
)
from factgraph.application.protocol.scenario_v2 import (
    EffectiveWorldFactV2,
    EffectiveWorldV2,
    ScenarioOperationV2,
    ScenarioSpecV2,
    lower_scenario_meta_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef, EntitySelector, FieldPath
from factgraph.application.scenario_v1_runtime import resolve_scenario_v1
from factgraph.application.scenario_v2_runtime import (
    ScenarioBuilderV2,
    ScenarioResolutionErrorV2,
    resolve_scenario_v2_from_v1,
)
from factgraph.core.store._support import ProjectedFact
from factgraph.sdk import Entity, Field, Identity, SDKStore


_A = "sha256:" + "a" * 64
_B = "sha256:" + "b" * 64


class PersonV2(Entity):
    employee_id: str = Identity()  # type: ignore[assignment]
    age: int = Field()  # type: ignore[assignment]
    skills: list[str] = Field()  # type: ignore[assignment]


def _source(ref: str) -> dict[str, object]:
    return {
        "ref": ref,
        "locator": {"kind": "line_span", "line_start": 3, "line_end": 4},
        "content_digest": _B,
        "origin_role": "scenario_hypothesis",
    }


class ScenarioV2ProtocolTests(unittest.TestCase):
    def _v1_fixture(self):
        graph = SDKStore([PersonV2])
        index = build_schema_index(deepcopy(graph.schema_ir))
        alice = resolve_selector(
            EntitySelector(entity_type="PersonV2", identity={"employee_id": "alice"}), index=index
        )
        assert alice.encoded_ref is not None
        info = entity_info(index, "PersonV2")
        relation = {
            info.exists_predicate_id: (ProjectedFact("exists-alice", (alice.encoded_ref,)),),
            info.identity_predicates["employee_id"].pred_id: (
                ProjectedFact("id-alice", (alice.encoded_ref, "alice")),
            ),
            field_predicate(index, "PersonV2", "age").pred_id: (
                ProjectedFact("age-alice", (alice.encoded_ref, 22)),
            ),
            field_predicate(index, "PersonV2", "skills").pred_id: (
                ProjectedFact("skill-python", (alice.encoded_ref, "python")),
            ),
        }
        return index, relation, EntityRef("PersonV2", {"employee_id": "alice"}, alice.encoded_ref)

    def test_meta_lowers_into_independent_semantic_and_evidence_lanes(self) -> None:
        meta_one = lower_scenario_meta_v2(
            {
                "raw_kind": "probabilistic",
                "bound": [0.8, 0.8],
                "source": _source("meander:source:one"),
                "note": "operator premise",
            }
        )
        meta_two = lower_scenario_meta_v2(
            {
                "raw_kind": "probabilistic",
                "bound": ["0.8", "0.8"],
                "source": _source("meander:source:two"),
                "note": "other source",
            }
        )
        value = ScenarioValueV1.from_raw("string", "alice")
        first = EffectiveWorldFactV2(
            predicate_id="person:name",
            witness_id="scenario:one",
            values=(value,),
            origin="scenario_synthetic",
            fact_semantics=meta_one.fact_semantics,
            provenance=meta_one.provenance,
            display=meta_one.display,
            premise_ids=("one",),
            scenario_operation_digests=(_A,),
        )
        second = EffectiveWorldFactV2(
            predicate_id="person:name",
            witness_id="scenario:two",
            values=(value,),
            origin="scenario_synthetic",
            fact_semantics=meta_two.fact_semantics,
            provenance=meta_two.provenance,
            display=meta_two.display,
            premise_ids=("two",),
            scenario_operation_digests=(_A,),
        )
        one = EffectiveWorldV2(
            schema_digest=_A,
            base_view_digest=_A,
            admissibility_digest=_A,
            dependency_predicate_ids=("person:name",),
            facts=(first,),
        )
        two = EffectiveWorldV2(
            schema_digest=_A,
            base_view_digest=_A,
            admissibility_digest=_A,
            dependency_predicate_ids=("person:name",),
            facts=(second,),
        )
        self.assertEqual(one.semantic_world_digest, two.semantic_world_digest)
        self.assertNotEqual(one.resolution_evidence_digest, two.resolution_evidence_digest)
        assert meta_one.fact_semantics is not None
        self.assertEqual(meta_one.fact_semantics.point_probability, "0.8")

    def test_spec_rejects_stale_nested_fact_semantics_without_resealing(self) -> None:
        """A Scenario cannot execute altered semantic metadata under old pins."""

        graph = SDKStore([PersonV2])
        alice = graph.entities.create(PersonV2, employee_id="alice")
        scenario = (
            graph.scenario()
            .set(
                PersonV2.age,
                alice,
                31,
                premise_id="what-if-age",
                meta={"raw_kind": "probabilistic", "bound": ["0.8", "0.8"]},
            )
            .build()
        )
        semantics = scenario.operations[0].meta.fact_semantics
        assert semantics is not None
        object.__setattr__(semantics, "point_probability", "0.9")

        with self.assertRaises(ProtocolShapeError):
            ScenarioSpecV2.__post_init__(scenario)

    def test_without_and_exact_members_reject_ambiguous_semantic_metadata(self) -> None:
        entity = EntityRef("Person", {"id": "a"})
        field = FieldPath("Person", "skills")
        semantic = lower_scenario_meta_v2({"raw_kind": "probabilistic", "bound": [0.5, 0.5]})
        with self.assertRaisesRegex(ProtocolShapeError, "without operation"):
            ScenarioOperationV2(
                ScenarioWithoutFieldV1("clear", entity, field),
                meta=semantic,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "per member"):
            ScenarioOperationV2(
                ScenarioSetExactMembersV1(
                    "members",
                    entity,
                    field,
                    (ScenarioValueV1.from_raw("string", "python"),),
                ),
                meta=semantic,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "exact point"):
            lower_scenario_meta_v2({"raw_kind": "probabilistic", "bound": [0.2, 0.8]})
        with self.assertRaisesRegex(ProtocolShapeError, "unsupported keys"):
            lower_scenario_meta_v2({"confidence": 0.8})

    def test_builder_keeps_per_member_metadata_aligned_after_v1_canonicalization(self) -> None:
        entity = EntityRef("Person", {"id": "a"})
        field = FieldPath("Person", "skills")
        built = (
            ScenarioBuilderV2()
            .exact_members(
                premise_id="members",
                entity=entity,
                field=field,
                values=(
                    ScenarioValueV1.from_raw("string", "sql"),
                    ScenarioValueV1.from_raw("string", "python"),
                ),
                member_meta=(
                    {"raw_kind": "probabilistic", "bound": [0.2, 0.2]},
                    {"raw_kind": "probabilistic", "bound": [0.8, 0.8]},
                ),
            )
            .build()
        )
        operation = built.operations[0]
        assert isinstance(operation.operation, ScenarioSetExactMembersV1)
        self.assertEqual(
            tuple(value.value for value in operation.operation.values), ("python", "sql")
        )
        self.assertEqual(
            tuple(
                item.fact_semantics.point_probability
                for item in operation.member_meta
                if item.fact_semantics
            ),
            ("0.8", "0.2"),
        )

    def test_v1_resolution_lift_maps_synthetic_and_baseline_metadata_by_witness(self) -> None:
        index, relation, alice = self._v1_fixture()
        v1_operation = ScenarioSetEffectiveValueV1(
            "age-premise",
            alice,
            FieldPath("PersonV2", "age"),
            ScenarioValueV1.from_raw("int", 35),
        )
        resolved_v1 = resolve_scenario_v1(
            ScenarioSpecV1((v1_operation,)),
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_A,
            admissibility_digest=_A,
        )
        v2_operation = ScenarioOperationV2(
            v1_operation,
            meta=lower_scenario_meta_v2(
                {
                    "raw_kind": "probabilistic",
                    "bound": [0.8, 0.8],
                    "source": _source("meander:scenario:age"),
                }
            ),
        )
        resolved_v2 = resolve_scenario_v2_from_v1(
            spec=ScenarioSpecV2((v2_operation,)),
            resolved_v1=resolved_v1,
            baseline_metadata_by_witness_id={
                "age-alice": lower_scenario_meta_v2({"source": _source("baseline:age")})
            },
        )
        baseline_age = next(
            item for item in resolved_v2.baseline_world.facts if item.witness_id == "age-alice"
        )
        effective_age = next(
            item
            for item in resolved_v2.effective_world.facts
            if item.origin == "scenario_synthetic" and item.predicate_id.endswith(":age")
        )
        self.assertEqual(baseline_age.origin, "baseline_support")
        self.assertEqual(baseline_age.provenance[0].source_ref, "baseline:age")
        assert effective_age.fact_semantics is not None
        self.assertEqual(effective_age.fact_semantics.point_probability, "0.8")
        self.assertEqual(effective_age.provenance[0].source_ref, "meander:scenario:age")
        self.assertNotEqual(
            resolved_v2.baseline_world.resolution_evidence_digest,
            resolved_v2.effective_world.resolution_evidence_digest,
        )

    def test_lift_rejects_probability_that_v1_would_drop_on_a_noop(self) -> None:
        index, relation, alice = self._v1_fixture()
        v1_operation = ScenarioEnsureMemberV1(
            "already-present",
            alice,
            FieldPath("PersonV2", "skills"),
            ScenarioValueV1.from_raw("string", "python"),
        )
        resolved_v1 = resolve_scenario_v1(
            ScenarioSpecV1((v1_operation,)),
            schema_index=index,
            baseline_relation=relation,
            base_view_digest=_A,
            admissibility_digest=_A,
        )
        with self.assertRaisesRegex(ScenarioResolutionErrorV2, "did not materialize") as caught:
            resolve_scenario_v2_from_v1(
                spec=ScenarioSpecV2(
                    (
                        ScenarioOperationV2(
                            v1_operation,
                            meta=lower_scenario_meta_v2(
                                {"raw_kind": "probabilistic", "bound": [0.6, 0.6]}
                            ),
                        ),
                    )
                ),
                resolved_v1=resolved_v1,
            )
        self.assertEqual(caught.exception.code, "SCENARIO_V2_SEMANTICS_NOT_MATERIALIZED")

    def test_profile_codec_and_v2_replay_world_codec_are_strict(self) -> None:
        target = EvaluationTargetPinV2(
            side="primary",
            target_kind="policy",
            target_id="risk",
            target_version="1",
            target_digest=_A,
        )
        attachment = ExecutionAttachmentV2(
            kind="occurrence",
            target=target,
            semantics=ExecutionAttachmentSemanticsV2("problog_occurrence_point_v1"),
            rule_id="eligible",
            rule_version="1",
            rule_digest=_B,
            occurrence_alias="older",
        )
        profile = EvaluationExecutionProfileV2(
            kind="problog_point_v2",
            name="risk-v1",
            compiler_digest=_A,
            engines=(
                EvaluationEnginePinV2("problog", "1", "1"),
                EvaluationEnginePinV2("native", "1", "1"),
                EvaluationEnginePinV2("souffle", "1", "1"),
            ),
            semantics=ProbLogPointSemanticsV2(),
            target_pins=(target,),
            attachments=(attachment, attachment),
        )
        decoded = EvaluationExecutionProfileV2.from_bytes(profile.to_bytes())
        self.assertEqual(decoded.profile_digest, profile.profile_digest)
        self.assertEqual(len(decoded.attachments), 1)

        native_profile = EvaluationExecutionProfileV2(
            kind="native_deterministic_v2",
            name=None,
            compiler_digest=_A,
            engines=(EvaluationEnginePinV2("native", "1", "1"),),
            semantics=DeterministicSemanticsV2(),
        )
        fact = EffectiveWorldFactV2(
            predicate_id="p",
            witness_id="baseline:p",
            values=(ScenarioValueV1.from_raw("string", "x"),),
            origin="baseline_support",
        )
        world = EffectiveWorldV2(
            schema_digest=_A,
            base_view_digest=_A,
            admissibility_digest=_A,
            dependency_predicate_ids=("p",),
            facts=(fact,),
        )
        payload = EvaluationReplayPayloadV2(
            schema_digest=_A,
            address_space_digest=_B,
            profile_bytes=native_profile.to_bytes(),
            compiled_program_bytes=b"{}",
            worlds=(
                EvaluationReplayWorldV2("baseline", world),
                EvaluationReplayWorldV2("effective", world),
            ),
        )
        self.assertEqual(
            evaluation_replay_payload_v2_from_bytes(
                evaluation_replay_payload_v2_bytes(payload)
            ).payload_digest,
            payload.payload_digest,
        )

    def test_payload_serializer_rejects_stale_nested_world_without_resealing(self) -> None:
        """Wire encoding is an integrity gate, not a way to bless mutation."""

        profile = EvaluationExecutionProfileV2(
            kind="native_deterministic_v2",
            name=None,
            compiler_digest=_A,
            engines=(EvaluationEnginePinV2("native", "1", "1"),),
            semantics=DeterministicSemanticsV2(),
        )
        fact = EffectiveWorldFactV2(
            predicate_id="p",
            witness_id="baseline:p",
            values=(ScenarioValueV1.from_raw("string", "x"),),
            origin="baseline_support",
        )
        world = EffectiveWorldV2(
            schema_digest=_A,
            base_view_digest=_A,
            admissibility_digest=_A,
            dependency_predicate_ids=("p",),
            facts=(fact,),
        )
        payload = EvaluationReplayPayloadV2(
            schema_digest=_A,
            address_space_digest=_B,
            profile_bytes=profile.to_bytes(),
            compiled_program_bytes=b"{}",
            worlds=(
                EvaluationReplayWorldV2("baseline", world),
                EvaluationReplayWorldV2("effective", world),
            ),
        )
        original_payload_digest = payload.payload_digest
        # A frozen public carrier remains mutable through object.__setattr__.
        # The outer payload digest deliberately stays stale here; serialization
        # must reject rather than re-run __post_init__ and bless the mutation.
        object.__setattr__(world, "base_view_digest", _B)

        with self.assertRaises(ProtocolShapeError):
            evaluation_replay_payload_v2_bytes(payload)

        self.assertEqual(payload.payload_digest, original_payload_digest)

    def test_fresh_payload_constructor_rejects_stale_replay_world_wrapper(self) -> None:
        """An outer fresh payload cannot rebless an already stale child."""

        profile = EvaluationExecutionProfileV2(
            kind="native_deterministic_v2",
            name=None,
            compiler_digest=_A,
            engines=(EvaluationEnginePinV2("native", "1", "1"),),
            semantics=DeterministicSemanticsV2(),
        )
        world = EffectiveWorldV2(
            schema_digest=_A,
            base_view_digest=_A,
            admissibility_digest=_A,
            dependency_predicate_ids=("p",),
            facts=(
                EffectiveWorldFactV2(
                    predicate_id="p",
                    witness_id="baseline:p",
                    values=(ScenarioValueV1.from_raw("string", "x"),),
                    origin="baseline_support",
                ),
            ),
        )
        baseline = EvaluationReplayWorldV2("baseline", world)
        effective = EvaluationReplayWorldV2("effective", world)
        # Both wrappers now retain their original capture digests.  A fresh
        # payload must inspect the child world, not merely trust those digests.
        object.__setattr__(world, "base_view_digest", _B)

        with self.assertRaises(ProtocolShapeError):
            EvaluationReplayPayloadV2(
                schema_digest=_A,
                address_space_digest=_B,
                profile_bytes=profile.to_bytes(),
                compiled_program_bytes=b"{}",
                worlds=(baseline, effective),
            )

    def test_fresh_profile_constructor_rejects_stale_nested_resource_policy(self) -> None:
        """Profile construction recursively checks supplied child seals."""

        resources = EvaluationResourcePolicyV2(max_rows=10)
        object.__setattr__(resources, "max_rows", 11)

        with self.assertRaises(ProtocolShapeError):
            EvaluationExecutionProfileV2(
                kind="native_deterministic_v2",
                name=None,
                compiler_digest=_A,
                engines=(EvaluationEnginePinV2("native", "1", "1"),),
                semantics=DeterministicSemanticsV2(),
                resources=resources,
            )

    def test_profile_serializer_rejects_stale_nested_resource_without_resealing(self) -> None:
        """Profile byte encoding is also a current-seal gate."""

        resources = EvaluationResourcePolicyV2(max_rows=10)
        profile = EvaluationExecutionProfileV2(
            kind="native_deterministic_v2",
            name=None,
            compiler_digest=_A,
            engines=(EvaluationEnginePinV2("native", "1", "1"),),
            semantics=DeterministicSemanticsV2(),
            resources=resources,
        )
        original_digest = profile.profile_digest
        object.__setattr__(resources, "max_rows", 11)

        with self.assertRaises(ProtocolShapeError):
            profile.to_bytes()

        self.assertEqual(profile.profile_digest, original_digest)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
