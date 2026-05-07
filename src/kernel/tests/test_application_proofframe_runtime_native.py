"""Runtime tests for native ProofFrame rechecking."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from kernel.application import (
    build_schema_index,
    entity_info,
    field_predicate,
    recheck_proof_frame,
    resolve_selector,
)
from kernel.application.protocol import (
    EntitySelector,
    EvaluationOverlay,
    FactRemoveAction,
    FactValueOverride,
    ProofFrameRecheckRequest,
    RuleDisableAction,
    aggregate_proof_frame_status,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.store import Store
from kernel.core.store._support import (
    NonFactStep,
    PredWitness,
    ProjectedFact,
    RuleRefEdge,
    SupportArtifact,
)
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


@dataclass(frozen=True)
class SeededPerson:
    e_ref: str
    exists_asrt_id: str
    age_asrt_id: str
    region_asrt_id: str
    exists_pred_id: str
    age_pred_id: str
    region_pred_id: str


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(store: Store, index: Any, *, name: str = "alice") -> SeededPerson:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    exists_asrt_id = set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", 25)])
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    region_asrt_id = set_field(store.ledger, region_pred_id, encoded, [("string", "us")])
    return SeededPerson(
        e_ref=encoded,
        exists_asrt_id=exists_asrt_id,
        age_asrt_id=age_asrt_id,
        region_asrt_id=region_asrt_id,
        exists_pred_id=info.exists_predicate_id,
        age_pred_id=age_pred_id,
        region_pred_id=region_pred_id,
    )


def _artifact(
    seeded: SeededPerson,
    *,
    pred_witnesses: tuple[PredWitness, ...] | None = None,
    non_fact_steps: tuple[NonFactStep, ...] = (),
    kind: str = "native_binding_v1",
    rule_ref_edges: tuple[RuleRefEdge, ...] = (),
) -> SupportArtifact:
    return SupportArtifact(
        kind=kind,
        root_result_kind="row",
        binding_items=(("$age", 25), ("$p", seeded.e_ref)),
        pred_witnesses=pred_witnesses
        if pred_witnesses is not None
        else (
            PredWitness(
                pred_atom_key=f"b0.a0:{seeded.age_pred_id}",
                asrt_ids=(seeded.age_asrt_id,),
            ),
        ),
        non_fact_steps=non_fact_steps,
        rule_ref_edges=rule_ref_edges,
    )


def _replace_age(seeded: SeededPerson, *, new_age: int) -> FactValueOverride:
    return FactValueOverride(
        asrt_id=seeded.age_asrt_id,
        pred_id=seeded.age_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, 25),
        new_fact_tuple=(seeded.e_ref, new_age),
    )


def _replace_region(seeded: SeededPerson, *, new_region: str) -> FactValueOverride:
    return FactValueOverride(
        asrt_id=seeded.region_asrt_id,
        pred_id=seeded.region_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, "us"),
        new_fact_tuple=(seeded.e_ref, new_region),
    )


def _remove_age(seeded: SeededPerson) -> FactRemoveAction:
    return FactRemoveAction(
        asrt_id=seeded.age_asrt_id,
        pred_id=seeded.age_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, 25),
    )


def _request(
    artifact: SupportArtifact,
    overlay: EvaluationOverlay,
) -> ProofFrameRecheckRequest:
    return ProofFrameRecheckRequest(support_artifact=artifact, overlay=overlay)


def _overlay(*actions: object) -> EvaluationOverlay:
    return EvaluationOverlay(fact_actions=actions)  # type: ignore[arg-type]


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


class ProofFrameRuntimeNativeTests(unittest.TestCase):
    def test_empty_overlay_keeps_pred_witness_still_valid(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)

        result = recheck_proof_frame(
            _request(_artifact(seeded), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, "still_valid")
        self.assertEqual(result.atom_verdicts[0].verdict, "still_valid")
        self.assertEqual(result.atom_verdicts[0].affected_action_indices, ())

    def test_replace_invalidates_exact_pred_witness(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)

        result = recheck_proof_frame(
            _request(_artifact(seeded), _overlay(_replace_age(seeded, new_age=26))),
            store=store,
        )

        self.assertEqual(result.status, "invalidated")
        self.assertEqual(result.atom_verdicts[0].verdict, "invalidated")
        self.assertEqual(result.atom_verdicts[0].affected_action_indices, (0,))

    def test_remove_invalidates_single_pred_witness(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)

        result = recheck_proof_frame(
            _request(_artifact(seeded), _overlay(_remove_age(seeded))),
            store=store,
        )

        self.assertEqual(result.status, "invalidated")
        self.assertEqual(result.atom_verdicts[0].verdict, "invalidated")
        self.assertEqual(result.atom_verdicts[0].affected_action_indices, (0,))

    def test_multi_witness_pred_atom_stays_valid_when_alternative_remains(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        witness = {
            seeded.age_pred_id: [
                ProjectedFact(
                    asrt_id=seeded.age_asrt_id,
                    fact_tuple=(seeded.e_ref, 25),
                ),
                ProjectedFact(asrt_id="alt-age", fact_tuple=(seeded.e_ref, 25)),
            ]
        }
        artifact = _artifact(
            seeded,
            pred_witnesses=(
                PredWitness(
                    pred_atom_key=f"b0.a0:{seeded.age_pred_id}",
                    asrt_ids=tuple(sorted(("alt-age", seeded.age_asrt_id))),
                ),
            ),
        )

        with patch(
            "kernel.application.proofframe_runtime.project_view_facts_with_witness",
            return_value=witness,
        ):
            result = recheck_proof_frame(
                _request(artifact, _overlay(_remove_age(seeded))),
                store=store,
            )

        self.assertEqual(result.status, "still_valid")
        self.assertEqual(result.atom_verdicts[0].affected_action_indices, (0,))

    def test_not_step_always_yields_unknown(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:not", kind="not", status="no_match")

        result = recheck_proof_frame(
            _request(
                _artifact(seeded, non_fact_steps=(step,)),
                _overlay(_replace_age(seeded, new_age=26)),
            ),
            store=store,
        )

        verdicts = {verdict.atom_key: verdict for verdict in result.atom_verdicts}
        self.assertEqual(verdicts["b0.a1:not"].verdict, "unknown")
        self.assertEqual(verdicts["b0.a1:not"].affected_action_indices, ())
        self.assertEqual(result.status, "invalidated")

    def test_not_step_can_drive_frame_unknown_without_invalidated_atom(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:not", kind="not", status="no_match")

        result = recheck_proof_frame(
            _request(_artifact(seeded, non_fact_steps=(step,)), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.atom_verdicts[1].verdict, "unknown")

    def test_binding_driven_non_fact_step_stays_valid(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:eq", kind="eq", status="satisfied")

        result = recheck_proof_frame(
            _request(_artifact(seeded, non_fact_steps=(step,)), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, "still_valid")
        self.assertEqual(result.atom_verdicts[1].verdict, "still_valid")

    def test_unknown_future_non_fact_kind_with_overlay_is_unknown(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:future", kind="future", status="satisfied")

        result = recheck_proof_frame(
            _request(
                _artifact(seeded, non_fact_steps=(step,)),
                _overlay(_replace_age(seeded, new_age=25)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.atom_verdicts[1].affected_action_indices, (0,))

    def test_unknown_future_non_fact_kind_with_unrelated_overlay_stays_valid(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:future", kind="future", status="satisfied")

        result = recheck_proof_frame(
            _request(
                _artifact(seeded, non_fact_steps=(step,)),
                _overlay(_replace_region(seeded, new_region="eu")),
            ),
            store=store,
        )

        self.assertEqual(result.status, "still_valid")
        self.assertEqual(result.atom_verdicts[1].verdict, "still_valid")
        self.assertEqual(result.atom_verdicts[1].affected_action_indices, ())

    def test_non_native_support_kind_returns_unknown_frame_level_result(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)

        result = recheck_proof_frame(
            _request(_artifact(seeded, kind="souffle_witness_v1"), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.atom_verdicts, ())

    def test_rule_ref_edges_return_unknown_frame_level_result(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        edge = RuleRefEdge(
            ruleref_atom_key="b0.a1:ruleref",
            rule_ref_id="person.exists",
            rule_ref_version="1.0",
            child_support_digest="sha256:" + ("0" * 64),
        )

        result = recheck_proof_frame(
            _request(_artifact(seeded, rule_ref_edges=(edge,)), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.atom_verdicts, ())

    def test_rule_actions_return_unknown_frame_level_result(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)

        result = recheck_proof_frame(
            _request(
                _artifact(seeded),
                EvaluationOverlay(
                    rule_actions=(
                        RuleDisableAction(
                            rule_id="person.eligible",
                            version="1.0",
                            branch_index=0,
                            atom_index=0,
                        ),
                    )
                ),
            ),
            store=store,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.atom_verdicts, ())

    def test_no_write_invariant(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        before = _ledger_dump(store)

        recheck_proof_frame(
            _request(_artifact(seeded), _overlay(_remove_age(seeded))),
            store=store,
        )

        self.assertEqual(_ledger_dump(store), before)
        self.assertEqual(store._support_artifacts, {})

    def test_result_status_matches_aggregate(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index)
        step = NonFactStep(step_key="b0.a1:not", kind="not", status="no_match")

        result = recheck_proof_frame(
            _request(_artifact(seeded, non_fact_steps=(step,)), _overlay()),
            store=store,
        )

        self.assertEqual(result.status, aggregate_proof_frame_status(result.atom_verdicts))


class ProofFrameRuntimeExportTests(unittest.TestCase):
    def test_application_package_exports_runtime_entrypoint(self) -> None:
        from kernel import application

        self.assertIs(application.recheck_proof_frame, recheck_proof_frame)


class ProofFrameRuntimeBoundaryTests(unittest.TestCase):
    def test_runtime_does_not_import_sibling_capability_runtimes_or_sdk(self) -> None:
        source = Path("src/kernel/application/proofframe_runtime.py").read_text()

        self.assertNotIn("fact_overlay_runtime", source)
        self.assertNotIn("_apply_fact_overlay_projection", source)
        self.assertNotIn("derivation_check_runtime", source)
        self.assertNotIn("diagnose_runtime", source)
        self.assertNotIn("why_not_runtime", source)
        self.assertNotIn("kernel.sdk", source)

    def test_capability_helpers_package_does_not_call_proofframe_runtime(self) -> None:
        source = Path("src/kernel/application/capability_helpers/proof_frame.py").read_text()

        self.assertNotIn("proofframe_runtime", source)
        self.assertNotIn("recheck_proof_frame", source)
