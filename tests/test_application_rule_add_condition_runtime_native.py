"""Runtime tests for native Rule Add Condition."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.application import (
    build_schema_index,
    check_rule_add_condition_action,
    check_rule_disable_action,
    check_rule_literal_replace_action,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntitySelector,
    EvaluationOverlay,
    FactValueOverride,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    RuleAddedAtom,
    RuleDisableAction,
    RuleDisableRequest,
    RuleLiteralReplaceRequest,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store import Store
from factgraph.core.store._support import NonFactStep, PredWitness, RuleRefEdge, SupportArtifact
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


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


def _action(**kwargs: object) -> RuleAddConditionAction:
    fields = {
        "rule_id": "person.eligible",
        "version": "1.0",
        "branch_index": 0,
        "added_atom": RuleAddedAtom(("lt", "$age", 20)),
    }
    fields.update(kwargs)
    return RuleAddConditionAction(**fields)  # type: ignore[arg-type]


def _request(
    rule_spec: RuleSpec,
    artifact: SupportArtifact,
    overlay: EvaluationOverlay,
) -> RuleAddConditionRequest:
    return RuleAddConditionRequest(
        rule_spec=rule_spec,
        support_artifact=artifact,
        overlay=overlay,
    )


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


class RuleAddConditionRuntimeNativeTests(unittest.TestCase):
    def test_added_filter_returns_variant_rows_and_invalidates_old_frame(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", age=25)
        bob = _seed_person(store, index, name="bob", age=17)

        result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", bob.e_ref),),))
        self.assertIsNotNone(result.proof_frame)
        proof_frame = result.proof_frame
        assert proof_frame is not None
        self.assertEqual(proof_frame.status, "invalidated")
        verdicts = {verdict.atom_key: verdict for verdict in proof_frame.atom_verdicts}
        self.assertEqual(verdicts["b0.add0:lt"].verdict, "invalidated")
        self.assertEqual(verdicts["b0.add0:lt"].affected_action_indices, (0,))
        self.assertEqual(verdicts[f"b0.a0:{alice.exists_pred_id}"].verdict, "still_valid")
        self.assertEqual(verdicts["b0.a3:eq"].verdict, "still_valid")

    def test_added_filter_preserves_old_frame_when_binding_remains(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", age=25)

        result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(
                    rule_actions=(_action(added_atom=RuleAddedAtom(("lt", "$age", 65))),)
                ),
            ),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", alice.e_ref),),))
        assert result.proof_frame is not None
        verdicts = {verdict.atom_key: verdict for verdict in result.proof_frame.atom_verdicts}
        self.assertEqual(verdicts["b0.add0:lt"].verdict, "still_valid")
        self.assertEqual(verdicts["b0.add0:lt"].affected_action_indices, ())
        self.assertEqual(result.proof_frame.status, "still_valid")

    def test_in_and_eq_filter_atoms_are_supported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", region="us")

        for atom in (("in", "$region", ["us", "ca"]), ("eq", "$region", "us")):
            with self.subTest(atom=atom):
                result = check_rule_add_condition_action(
                    _request(
                        _rule_spec(index),
                        _artifact(alice),
                        EvaluationOverlay(
                            rule_actions=(_action(added_atom=RuleAddedAtom(atom)),)
                        ),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "completed")
                self.assertEqual(result.variant_rows, ((("$p", alice.e_ref),),))

    def test_fact_actions_and_wrong_rule_action_type_are_rejected(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        fact_action = FactValueOverride(
            asrt_id=alice.age_asrt_id,
            pred_id=alice.age_pred_id,
            e_ref=alice.e_ref,
            old_fact_tuple=(alice.e_ref, 25),
            new_fact_tuple=(alice.e_ref, 26),
        )

        fact_result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(fact_actions=(fact_action,), rule_actions=(_action(),)),
            ),
            store=store,
        )
        type_result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(
                    rule_actions=(
                        RuleDisableAction(
                            rule_id="person.eligible",
                            version="1.0",
                            branch_index=0,
                            atom_index=3,
                        ),
                    )
                ),
            ),
            store=store,
        )

        self.assertEqual(fact_result.status, "invalid_request")
        self.assertEqual(
            fact_result.errors[0].code,
            "RULE_ADD_CONDITION_FACT_ACTIONS_UNSUPPORTED",
        )
        self.assertEqual(type_result.status, "invalid_request")
        self.assertEqual(type_result.errors[0].code, "RULE_ADD_CONDITION_ACTION_TYPE_UNSUPPORTED")

    def test_action_count_identity_and_branch_errors(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        cases = [
            ((), "RULE_ADD_CONDITION_ACTION_COUNT"),
            ((_action(), _action(added_atom=RuleAddedAtom(("lt", "$age", 65)))), "RULE_ADD_CONDITION_ACTION_COUNT"),
            ((_action(rule_id="other.rule"),), "RULE_ADD_CONDITION_RULE_MISMATCH"),
            ((_action(branch_index=99),), "RULE_ADD_CONDITION_BRANCH_NOT_FOUND"),
        ]
        for actions, code in cases:
            with self.subTest(code=code):
                result = check_rule_add_condition_action(
                    _request(
                        _rule_spec(index),
                        _artifact(alice),
                        EvaluationOverlay(rule_actions=actions),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, code)

    def test_added_atom_validation_errors(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        cases = [
            (("lt", "$age"), "RULE_ADD_CONDITION_ATOM_MALFORMED"),
            (("pred", alice.age_pred_id, ["$p", "$age"]), "RULE_ADD_CONDITION_ATOM_UNSUPPORTED"),
            (("not", [("pred", alice.age_pred_id, ["$p", 25])]), "RULE_ADD_CONDITION_NOT_UNSUPPORTED"),
            (("eq", "$new", "us"), "RULE_ADD_CONDITION_BINDS_NEW_VARIABLE"),
            (("lt", "$unknown", 65), "RULE_ADD_CONDITION_BINDS_NEW_VARIABLE"),
        ]

        for atom, code in cases:
            with self.subTest(code=code):
                result = check_rule_add_condition_action(
                    _request(
                        _rule_spec(index),
                        _artifact(alice),
                        EvaluationOverlay(
                            rule_actions=(_action(added_atom=RuleAddedAtom(atom)),)
                        ),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, code)

    def test_ruleref_inputs_are_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        edge = RuleRefEdge(
            ruleref_atom_key="b0.a1:ruleref",
            rule_ref_id="child.rule",
            rule_ref_version="1.0",
            child_support_digest="sha256:" + ("0" * 64),
        )
        rule_spec = _rule_spec(index, where=[("ruleref", "child.rule", "1.0", ["$p"])])
        nested_rule_spec = _rule_spec(
            index,
            where=[
                ("pred", alice.exists_pred_id, ["$p"]),
                ("not", [("ruleref", "child.rule", "1.0", ["$p"])]),
            ],
        )

        for request in (
            _request(
                rule_spec,
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
            _request(
                nested_rule_spec,
                _artifact(alice),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
            _request(
                _rule_spec(index),
                _artifact(alice, rule_refs=("child.rule",)),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
            _request(
                _rule_spec(index),
                _artifact(alice, rule_ref_edges=(edge,)),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
        ):
            with self.subTest(request=request):
                result = check_rule_add_condition_action(request, store=store)
                self.assertEqual(result.status, "unsupported")
                self.assertEqual(
                    result.errors[0].code,
                    "RULE_ADD_CONDITION_RULE_REF_UNSUPPORTED",
                )

    def test_non_native_support_artifact_is_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice, kind="souffle_witness_v1"),
                EvaluationOverlay(rule_actions=(_action(),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "RULE_ADD_CONDITION_SUPPORT_UNSUPPORTED")

    def test_native_eval_error_maps_to_invalid_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        result = check_rule_add_condition_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                EvaluationOverlay(
                    rule_actions=(_action(added_atom=RuleAddedAtom(("lt", "$age", "not-an-int"))),)
                ),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_ADD_CONDITION_NATIVE_EVAL_ERROR")

    def test_no_write_invariant(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        before = _ledger_dump(store)

        check_rule_add_condition_action(
            _request(_rule_spec(index), _artifact(alice), EvaluationOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(_ledger_dump(store), before)
        self.assertEqual(store._support_artifacts, {})


class RuleAddConditionRuntimeExportTests(unittest.TestCase):
    def test_application_package_exports_runtime_entrypoint(self) -> None:
        from factgraph import application

        self.assertIs(
            application.check_rule_add_condition_action,
            check_rule_add_condition_action,
        )


class RuleAddConditionCrossRuntimeGuardTests(unittest.TestCase):
    def test_existing_rule_runtimes_reject_rule_add_condition_action(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        overlay = EvaluationOverlay(rule_actions=(_action(),))

        disable_result = check_rule_disable_action(
            RuleDisableRequest(_rule_spec(index), _artifact(alice), overlay),
            store=store,
        )
        replace_result = check_rule_literal_replace_action(
            RuleLiteralReplaceRequest(_rule_spec(index), _artifact(alice), overlay),
            store=store,
        )

        self.assertEqual(disable_result.status, "invalid_request")
        self.assertEqual(disable_result.errors[0].code, "RULE_DISABLE_ACTION_TYPE_UNSUPPORTED")
        self.assertEqual(replace_result.status, "invalid_request")
        self.assertEqual(
            replace_result.errors[0].code,
            "RULE_LITERAL_REPLACE_ACTION_TYPE_UNSUPPORTED",
        )


class RuleAddConditionRuntimeBoundaryTests(unittest.TestCase):
    def test_runtime_does_not_import_sibling_capability_runtimes_or_sdk(self) -> None:
        source = Path("src/factgraph/application/rule_add_condition_runtime.py").read_text()

        self.assertNotIn("fact_overlay_runtime", source)
        self.assertNotIn("proofframe_runtime", source)
        self.assertNotIn("rule_disable_runtime", source)
        self.assertNotIn("rule_literal_replace_runtime", source)
        self.assertNotIn("derivation_check_runtime", source)
        self.assertNotIn("diagnose_runtime", source)
        self.assertNotIn("why_not_runtime", source)
        self.assertNotIn("factgraph.sdk", source)

    def test_sdk_rule_add_condition_shell_imports_runtime_only_in_shell(self) -> None:
        """G3 Phase 3 retrofit (per `#P1` carve-out, mirroring G2 Phase 0
        retrofits of G1 + G4 archived invariants and G3 Phase 1 / Phase 2
        retrofits of the Rule Disable + Rule Literal Replace boundary
        tests): the SDK Rule Add Condition shell at
        ``factgraph/sdk/shells/rule_add_condition.py`` is now the active L
        Direction entry point. The original "no SDK surface" assertion
        is replaced by a narrower invariant: the runtime entrypoint
        ``check_rule_add_condition_action`` is imported only by the
        shell file, and ``RuleAddConditionAction`` is never IMPORTED
        anywhere in SDK code (docstring references documenting the
        boundary contract are allowed; the application A helper
        ``build_rule_add_condition_request`` constructs the action
        internally).
        """
        shell_path = Path("src/factgraph/sdk/shells/rule_add_condition.py")
        self.assertTrue(
            shell_path.is_file(), f"{shell_path} should exist after G3 Phase 3"
        )

        shell_source = shell_path.read_text()
        self.assertIn(
            "from factgraph.application.rule_add_condition_runtime import (",
            shell_source,
        )
        self.assertIn("check_rule_add_condition_action", shell_source)
        self.assertNotIn("import RuleAddConditionAction", shell_source)
        self.assertNotIn(", RuleAddConditionAction", shell_source)
        self.assertNotIn("RuleAddConditionAction(", shell_source)

        other_sdk_sources = "\n".join(
            path.read_text()
            for path in Path("src/factgraph/sdk").rglob("*.py")
            if path != shell_path
        )
        self.assertNotIn("check_rule_add_condition_action", other_sdk_sources)
        self.assertNotIn("import RuleAddConditionAction", other_sdk_sources)
        self.assertNotIn(", RuleAddConditionAction", other_sdk_sources)
        self.assertNotIn("RuleAddConditionAction(", other_sdk_sources)

    def test_frontier_protected_entrypoints_do_not_drift(self) -> None:
        ruleref_source = Path("src/factgraph/core/rules/ruleref_substrate.py").read_text()
        proof_protocol = Path("src/factgraph/application/protocol/proofframe.py").read_text()
        proof_runtime = Path("src/factgraph/application/proofframe_runtime.py").read_text()
        fact_runtime = Path("src/factgraph/application/fact_overlay_runtime.py").read_text()
        where_source = Path("src/factgraph/core/rules/where_eval.py").read_text()

        self.assertNotIn("added_conditions", ruleref_source)
        self.assertNotIn("RuleAddCondition", proof_protocol)
        self.assertNotIn("RuleAddCondition", proof_runtime)
        self.assertEqual(proof_runtime.count("rule_actions"), 1)
        self.assertNotIn("RuleAddCondition", fact_runtime)
        self.assertIn("def evaluate_where(", where_source)
        self.assertNotIn("def evaluate_native_where(", where_source)


if __name__ == "__main__":
    unittest.main()
