"""Runtime tests for native Rule Disable."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.application import (
    build_schema_index,
    check_rule_disable_action,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    EntitySelector,
    EvaluationOverlay,
    FactValueOverride,
    RuleDisableAction,
    RuleDisableRequest,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.rules.rule_ir import RuleSpec
from kernel.core.store import Store
from kernel.core.store._support import NonFactStep, PredWitness, RuleRefEdge, SupportArtifact
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


def _seed_person(
    store: Store,
    index: Any,
    *,
    name: str,
    age: int = 25,
    region: str = "us",
) -> SeededPerson:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    exists_asrt_id = set_field(store.ledger, info.exists_predicate_id, encoded, [])
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", age)])
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    region_asrt_id = set_field(
        store.ledger,
        region_pred_id,
        encoded,
        [("string", region)],
    )
    return SeededPerson(
        e_ref=encoded,
        exists_asrt_id=exists_asrt_id,
        age_asrt_id=age_asrt_id,
        region_asrt_id=region_asrt_id,
        exists_pred_id=info.exists_predicate_id,
        age_pred_id=age_pred_id,
        region_pred_id=region_pred_id,
    )


def _rule_spec(index: Any, *, where: list[Any] | None = None) -> RuleSpec:
    info = entity_info(index, "Person")
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=where
        if where is not None
        else [
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", age_pred_id, ["$p", "$age"]),
            ("pred", region_pred_id, ["$p", "$region"]),
            ("eq", "$region", "us"),
        ],
    )


def _artifact(seeded: SeededPerson, **kwargs: object) -> SupportArtifact:
    fields = {
        "kind": "native_binding_v1",
        "root_result_kind": "row",
        "binding_items": (("$p", seeded.e_ref),),
        "pred_witnesses": (
            PredWitness(
                pred_atom_key=f"b0.a0:{seeded.exists_pred_id}",
                asrt_ids=(seeded.exists_asrt_id,),
            ),
            PredWitness(
                pred_atom_key=f"b0.a1:{seeded.age_pred_id}",
                asrt_ids=(seeded.age_asrt_id,),
            ),
            PredWitness(
                pred_atom_key=f"b0.a2:{seeded.region_pred_id}",
                asrt_ids=(seeded.region_asrt_id,),
            ),
        ),
        "non_fact_steps": (
            NonFactStep(step_key="b0.a3:eq", kind="eq", status="satisfied"),
        ),
    }
    fields.update(kwargs)
    return SupportArtifact(**fields)  # type: ignore[arg-type]


def _action(**kwargs: object) -> RuleDisableAction:
    fields = {
        "rule_id": "person.eligible",
        "version": "1.0",
        "branch_index": 0,
        "atom_index": 3,
    }
    fields.update(kwargs)
    return RuleDisableAction(**fields)  # type: ignore[arg-type]


def _request(
    rule_spec: RuleSpec,
    artifact: SupportArtifact,
    overlay: EvaluationOverlay,
) -> RuleDisableRequest:
    return RuleDisableRequest(rule_spec=rule_spec, support_artifact=artifact, overlay=overlay)


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


class RuleDisableRuntimeNativeTests(unittest.TestCase):
    def test_disable_non_fact_atom_returns_variant_rows_and_invalidates_old_frame(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", region="us")
        bob = _seed_person(store, index, name="bob", region="eu")
        rule_spec = _rule_spec(index)

        result = check_rule_disable_action(
            _request(rule_spec, _artifact(alice), EvaluationOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", alice.e_ref),), (("$p", bob.e_ref),)))
        self.assertIsNotNone(result.proof_frame)
        proof_frame = result.proof_frame
        assert proof_frame is not None
        self.assertEqual(proof_frame.status, "invalidated")
        verdicts = {verdict.atom_key: verdict for verdict in proof_frame.atom_verdicts}
        self.assertEqual(verdicts["b0.a3:eq"].verdict, "invalidated")
        self.assertEqual(verdicts["b0.a3:eq"].affected_action_indices, (0,))
        self.assertEqual(verdicts[f"b0.a2:{alice.region_pred_id}"].verdict, "still_valid")

    def test_support_artifact_without_disabled_locator_stays_valid(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", region="us")
        artifact = _artifact(alice, non_fact_steps=())

        result = check_rule_disable_action(
            _request(_rule_spec(index), artifact, EvaluationOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.proof_frame)
        proof_frame = result.proof_frame
        assert proof_frame is not None
        self.assertEqual(proof_frame.status, "still_valid")
        self.assertEqual(
            [verdict.atom_key for verdict in proof_frame.atom_verdicts],
            [
                f"b0.a0:{alice.exists_pred_id}",
                f"b0.a1:{alice.age_pred_id}",
                f"b0.a2:{alice.region_pred_id}",
            ],
        )

    def test_fact_actions_are_rejected_in_rule_disable_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        fact_action = FactValueOverride(
            asrt_id=alice.age_asrt_id,
            pred_id=alice.age_pred_id,
            e_ref=alice.e_ref,
            old_fact_tuple=(alice.e_ref, 25),
            new_fact_tuple=(alice.e_ref, 26),
        )

        result = check_rule_disable_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(fact_actions=(fact_action,), rule_actions=(_action(),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_DISABLE_FACT_ACTIONS_UNSUPPORTED")

    def test_batch_5a_requires_exactly_one_rule_action(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        for actions in ((), (_action(), _action(atom_index=2))):
            with self.subTest(actions=len(actions)):
                result = check_rule_disable_action(
                    _request(
                        _rule_spec(index),
                        _artifact(alice),
                        EvaluationOverlay(rule_actions=actions),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, "RULE_DISABLE_ACTION_COUNT")

    def test_rule_identity_mismatch_is_invalid_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        result = check_rule_disable_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(rule_id="other.rule"),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_DISABLE_RULE_MISMATCH")

    def test_target_not_found_is_invalid_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        result = check_rule_disable_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(atom_index=99),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_DISABLE_TARGET_NOT_FOUND")

    def test_ruleref_rule_body_is_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        rule_spec = _rule_spec(
            index,
            where=[("ruleref", "child.rule", "1.0", ["$p"])],
        )

        result = check_rule_disable_action(
            _request(
                rule_spec,
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(atom_index=0),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "RULE_DISABLE_RULE_REF_UNSUPPORTED")

    def test_non_native_or_rule_ref_support_artifacts_are_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        edge = RuleRefEdge(
            ruleref_atom_key="b0.a1:ruleref",
            rule_ref_id="child.rule",
            rule_ref_version="1.0",
            child_support_digest="sha256:" + ("0" * 64),
        )

        for artifact in (
            _artifact(alice, kind="souffle_witness_v1"),
            _artifact(alice, rule_ref_edges=(edge,)),
        ):
            with self.subTest(kind=artifact.kind, edges=len(artifact.rule_ref_edges)):
                result = check_rule_disable_action(
                    _request(
                        _rule_spec(index),
                        artifact,
                        EvaluationOverlay(rule_actions=(_action(),)),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "unsupported")

    def test_native_eval_error_maps_to_invalid_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        rule_spec = RuleSpec(
            rule_id="person.eligible",
            version="1.0",
            select_vars=["$missing"],
            where=[("pred", alice.exists_pred_id, ["$p"])],
        )

        result = check_rule_disable_action(
            _request(
                rule_spec,
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(atom_index=0),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_DISABLE_NATIVE_EVAL_ERROR")

    def test_no_write_invariant(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        before = _ledger_dump(store)

        check_rule_disable_action(
            _request(_rule_spec(index), _artifact(alice), EvaluationOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(_ledger_dump(store), before)
        self.assertEqual(store._support_artifacts, {})


class RuleDisableRuntimeExportTests(unittest.TestCase):
    def test_application_package_exports_runtime_entrypoint(self) -> None:
        from kernel import application

        self.assertIs(application.check_rule_disable_action, check_rule_disable_action)


class RuleDisableRuntimeBoundaryTests(unittest.TestCase):
    def test_runtime_does_not_import_sibling_capability_runtimes_or_sdk(self) -> None:
        source = Path("src/kernel/application/rule_disable_runtime.py").read_text()

        self.assertNotIn("fact_overlay_runtime", source)
        self.assertNotIn("proofframe_runtime", source)
        self.assertNotIn("derivation_check_runtime", source)
        self.assertNotIn("diagnose_runtime", source)
        self.assertNotIn("why_not_runtime", source)
        self.assertNotIn("kernel.sdk", source)

    def test_no_sdk_rule_disable_surface(self) -> None:
        sdk_sources = "\n".join(
            path.read_text()
            for path in Path("src/kernel/sdk").rglob("*.py")
        )

        self.assertNotIn("check_rule_disable_action", sdk_sources)
        self.assertNotIn("RuleDisableAction", sdk_sources)

    def test_batch_4_proofframe_protocol_has_no_rule_disable_drift(self) -> None:
        source = Path("src/kernel/application/protocol/proofframe.py").read_text()

        self.assertNotIn("RuleDisable", source)
        self.assertNotIn("rule_actions", source)

    def test_fact_overlay_and_proofframe_runtime_guards_are_narrow(self) -> None:
        fact_source = Path("src/kernel/application/fact_overlay_runtime.py").read_text()
        proof_source = Path("src/kernel/application/proofframe_runtime.py").read_text()

        self.assertNotIn("RuleDisableAction", fact_source)
        self.assertIn("RULE_ACTIONS_NOT_SUPPORTED", fact_source)
        self.assertNotIn("RuleDisableAction", proof_source)
        self.assertEqual(proof_source.count("rule_actions"), 1)


if __name__ == "__main__":
    unittest.main()
