"""Runtime tests for native Rule Literal Replace."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.application import (
    build_schema_index,
    check_rule_literal_replace_action,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntitySelector,
    FactOverlay,
    ReplaceFact,
    RuleDisableAction,
    ConditionPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store import Store
from factgraph.core.store._support import NonFactStep, PredWitness, RuleRefEdge, ProofReceipt
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


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
    identity_pred_id = field_predicate(index, "Person", "name").pred_id
    set_field(store.ledger, identity_pred_id, encoded, [("string", name)])
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", age)])
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    region_asrt_id = set_field(
        store.ledger,
        region_pred_id,
        encoded,
        [("string", region)],
    )
    exists_asrt_id = next(
        row.asrt_id
        for row in project_view_facts_with_witness(store.ledger, store.schema_ir)[
            info.exists_predicate_id
        ]
        if row.fact_tuple == (encoded,)
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


def _artifact(seeded: SeededPerson, **kwargs: object) -> ProofReceipt:
    fields = {
        "kind": "native_binding_v1",
        "root_result_kind": "row",
        "binding_items": (("$p", seeded.e_ref),),
        "pred_witnesses": (
            PredWitness(
                pred_condition_key=f"c0.c0:{seeded.exists_pred_id}",
                asrt_ids=(seeded.exists_asrt_id,),
            ),
            PredWitness(
                pred_condition_key=f"c0.c1:{seeded.age_pred_id}",
                asrt_ids=(seeded.age_asrt_id,),
            ),
            PredWitness(
                pred_condition_key=f"c0.c2:{seeded.region_pred_id}",
                asrt_ids=(seeded.region_asrt_id,),
            ),
        ),
        "non_fact_steps": (
            NonFactStep(step_key="c0.c3:eq", kind="eq", status="satisfied"),
        ),
    }
    fields.update(kwargs)
    return ProofReceipt(**fields)  # type: ignore[arg-type]


def _action(**kwargs: object) -> RuleLiteralReplaceAction:
    fields = {
        "rule_id": "person.eligible",
        "version": "1.0",
        "case_index": 0,
        "condition_index": 3,
        "literal_path": ConditionPath(kind="rhs"),
        "old_literal": "us",
        "new_literal": "eu",
    }
    fields.update(kwargs)
    return RuleLiteralReplaceAction(**fields)  # type: ignore[arg-type]


def _request(
    rule_spec: RuleSpec,
    artifact: ProofReceipt,
    overlay: FactOverlay,
) -> RuleLiteralReplaceRequest:
    return RuleLiteralReplaceRequest(
        rule_spec=rule_spec,
        support_artifact=artifact,
        overlay=overlay,
    )


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


class RuleLiteralReplaceRuntimeNativeTests(unittest.TestCase):
    def test_replace_eq_literal_returns_variant_rows_and_invalidates_old_frame(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", region="us")
        bob = _seed_person(store, index, name="bob", region="eu")
        rule_spec = _rule_spec(index)

        result = check_rule_literal_replace_action(
            _request(rule_spec, _artifact(alice), FactOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", bob.e_ref),),))
        self.assertIsNotNone(result.proof_frame)
        proof_frame = result.proof_frame
        assert proof_frame is not None
        self.assertEqual(proof_frame.status, "invalidated")
        verdicts = {verdict.condition_key: verdict for verdict in proof_frame.atom_verdicts}
        self.assertEqual(verdicts["c0.c3:eq"].verdict, "invalidated")
        self.assertEqual(verdicts["c0.c3:eq"].affected_action_indices, (0,))
        self.assertEqual(verdicts[f"c0.c2:{alice.region_pred_id}"].verdict, "still_valid")

    def test_replace_pred_constant_literal(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice", region="us")
        bob = _seed_person(store, index, name="bob", region="eu")
        rule_spec = _rule_spec(
            index,
            where=[
                ("pred", alice.exists_pred_id, ["$p"]),
                ("pred", alice.region_pred_id, ["$p", "us"]),
            ],
        )
        artifact = _artifact(
            alice,
            pred_witnesses=(
                PredWitness(
                    pred_condition_key=f"c0.c0:{alice.exists_pred_id}",
                    asrt_ids=(alice.exists_asrt_id,),
                ),
                PredWitness(
                    pred_condition_key=f"c0.c1:{alice.region_pred_id}",
                    asrt_ids=(alice.region_asrt_id,),
                ),
            ),
            non_fact_steps=(),
        )

        result = check_rule_literal_replace_action(
            _request(
                rule_spec,
                artifact,
                FactOverlay(
                    rule_actions=(
                        _action(
                            condition_index=1,
                            literal_path=ConditionPath(kind="pred_term", index=1),
                            old_literal="us",
                            new_literal="eu",
                        ),
                    )
                ),
            ),
            store=store,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", bob.e_ref),),))
        assert result.proof_frame is not None
        verdicts = {verdict.condition_key: verdict for verdict in result.proof_frame.atom_verdicts}
        self.assertEqual(verdicts[f"c0.c1:{alice.region_pred_id}"].verdict, "invalidated")

    def test_fact_actions_and_wrong_rule_action_type_are_rejected(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        fact_action = ReplaceFact(
            asrt_id=alice.age_asrt_id,
            pred_id=alice.age_pred_id,
            e_ref=alice.e_ref,
            old_fact_tuple=(alice.e_ref, 25),
            new_fact_tuple=(alice.e_ref, 26),
        )

        fact_result = check_rule_literal_replace_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                FactOverlay(fact_actions=(fact_action,), rule_actions=(_action(),)),
            ),
            store=store,
        )
        type_result = check_rule_literal_replace_action(
            _request(
                _rule_spec(index),
                _artifact(alice),
                FactOverlay(
                    rule_actions=(
                        RuleDisableAction(
                            rule_id="person.eligible",
                            version="1.0",
                            case_index=0,
                            condition_index=3,
                        ),
                    )
                ),
            ),
            store=store,
        )

        self.assertEqual(fact_result.status, "invalid_request")
        self.assertEqual(
            fact_result.errors[0].code,
            "RULE_LITERAL_REPLACE_FACT_ACTIONS_UNSUPPORTED",
        )
        self.assertEqual(type_result.status, "invalid_request")
        self.assertEqual(
            type_result.errors[0].code,
            "RULE_LITERAL_REPLACE_ACTION_TYPE_UNSUPPORTED",
        )

    def test_action_count_identity_and_target_errors(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        cases = [
            ((), "RULE_LITERAL_REPLACE_ACTION_COUNT"),
            ((_action(), _action(condition_index=2)), "RULE_LITERAL_REPLACE_ACTION_COUNT"),
            ((_action(rule_id="other.rule"),), "RULE_LITERAL_REPLACE_RULE_MISMATCH"),
            ((_action(condition_index=99),), "RULE_LITERAL_REPLACE_TARGET_NOT_FOUND"),
        ]
        for actions, code in cases:
            with self.subTest(code=code):
                result = check_rule_literal_replace_action(
                    _request(
                        _rule_spec(index),
                        _artifact(alice),
                        FactOverlay(rule_actions=actions),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, code)

    def test_literal_path_and_value_errors(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        cases = [
            (
                _rule_spec(
                    index,
                    where=[
                        ("pred", alice.age_pred_id, ["$p", "$age"]),
                        ("add", "$next", "$age", 1),
                    ],
                ),
                _action(
                    condition_index=1,
                    literal_path=ConditionPath(kind="const_operand"),
                    old_literal=1,
                    new_literal=2,
                ),
                "RULE_LITERAL_REPLACE_ATOM_UNSUPPORTED",
            ),
            (
                _rule_spec(index),
                _action(literal_path=ConditionPath(kind="pred_term", index=0)),
                "RULE_LITERAL_REPLACE_PATH_INVALID",
            ),
            (
                _rule_spec(index),
                _action(old_literal="ca"),
                "RULE_LITERAL_REPLACE_STALE_LITERAL",
            ),
            (
                _rule_spec(index),
                _action(new_literal="$region"),
                "RULE_LITERAL_REPLACE_NEW_LITERAL_INVALID",
            ),
        ]

        for rule_spec, action, code in cases:
            with self.subTest(code=code):
                result = check_rule_literal_replace_action(
                    _request(
                        rule_spec,
                        _artifact(alice),
                        FactOverlay(rule_actions=(action,)),
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, code)

    def test_ruleref_inputs_are_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        edge = RuleRefEdge(
            ruleref_condition_key="c0.c1:ruleref",
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
                FactOverlay(rule_actions=(_action(condition_index=0),)),
            ),
            _request(
                nested_rule_spec,
                _artifact(alice),
                FactOverlay(rule_actions=(_action(condition_index=0),)),
            ),
            _request(
                _rule_spec(index),
                _artifact(alice, rule_refs=("child.rule",)),
                FactOverlay(rule_actions=(_action(),)),
            ),
            _request(
                _rule_spec(index),
                _artifact(alice, rule_ref_edges=(edge,)),
                FactOverlay(rule_actions=(_action(),)),
            ),
        ):
            with self.subTest(request=request):
                result = check_rule_literal_replace_action(request, store=store)
                self.assertEqual(result.status, "unsupported")
                self.assertEqual(
                    result.errors[0].code,
                    "RULE_LITERAL_REPLACE_RULE_REF_UNSUPPORTED",
                )

    def test_non_native_support_artifact_is_unsupported(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")

        result = check_rule_literal_replace_action(
            _request(
                _rule_spec(index),
                _artifact(alice, kind="souffle_witness_v1"),
                FactOverlay(rule_actions=(_action(),)),
            ),
            store=store,
        )

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "RULE_LITERAL_REPLACE_SUPPORT_UNSUPPORTED")

    def test_native_eval_error_maps_to_invalid_request(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        rule_spec = _rule_spec(
            index,
            where=[
                ("pred", alice.age_pred_id, ["$p", "$age"]),
                ("gt", "$age", 20),
            ],
        )

        result = check_rule_literal_replace_action(
            _request(
                rule_spec,
                _artifact(alice, non_fact_steps=(NonFactStep(step_key="c0.c1:gt", kind="gt", status="satisfied"),)),
                FactOverlay(
                    rule_actions=(
                        _action(
                            condition_index=1,
                            literal_path=ConditionPath(kind="rhs"),
                            old_literal=20,
                            new_literal="not-an-int",
                        ),
                    )
                ),
            ),
            store=store,
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_LITERAL_REPLACE_NATIVE_EVAL_ERROR")

    def test_no_write_invariant(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, name="alice")
        before = _ledger_dump(store)

        check_rule_literal_replace_action(
            _request(_rule_spec(index), _artifact(alice), FactOverlay(rule_actions=(_action(),))),
            store=store,
        )

        self.assertEqual(_ledger_dump(store), before)
        self.assertEqual(store._support_artifacts, {})


class RuleLiteralReplaceRuntimeExportTests(unittest.TestCase):
    def test_application_package_exports_runtime_entrypoint(self) -> None:
        from factgraph import application

        self.assertIs(
            application.check_rule_literal_replace_action,
            check_rule_literal_replace_action,
        )


class RuleLiteralReplaceRuntimeBoundaryTests(unittest.TestCase):
    def test_runtime_does_not_import_sibling_capability_runtimes_or_sdk(self) -> None:
        source = Path("src/factgraph/application/rule_literal_replace_runtime.py").read_text()

        self.assertNotIn("fact_overlay_runtime", source)
        self.assertNotIn("proofframe_runtime", source)
        self.assertNotIn("rule_disable_runtime", source)
        self.assertNotIn("derivation_check_runtime", source)
        self.assertNotIn("diagnose_runtime", source)
        self.assertNotIn("why_not_runtime", source)
        self.assertNotIn("factgraph.sdk", source)

    def test_sdk_rule_literal_replace_shell_imports_runtime_only_in_shell(self) -> None:
        """G3 Phase 2 retrofit (per `#P1` carve-out, mirroring G2 Phase 0
        retrofits of G1 + G4 archived invariants and G3 Phase 1 retrofit
        of the Rule Disable boundary test): the SDK Rule Literal Replace
        shell at ``factgraph/sdk/shells/rule_literal_replace.py`` is now the
        active L Direction entry point. The original "no SDK surface"
        assertion is replaced by a narrower invariant: the runtime
        entrypoint ``check_rule_literal_replace_action`` is imported
        only by the shell file, and ``RuleLiteralReplaceAction`` is
        never IMPORTED anywhere in SDK code (docstring references
        documenting the boundary contract are allowed; the application
        A helper ``build_rule_literal_replace_request`` constructs the
        action internally).
        """
        shell_path = Path("src/factgraph/sdk/shells/rule_literal_replace.py")
        self.assertTrue(
            shell_path.is_file(), f"{shell_path} should exist after G3 Phase 2"
        )

        shell_source = shell_path.read_text()
        self.assertIn(
            "from factgraph.application.rule_literal_replace_runtime import (",
            shell_source,
        )
        self.assertIn("check_rule_literal_replace_action", shell_source)
        self.assertNotIn("import RuleLiteralReplaceAction", shell_source)
        self.assertNotIn(", RuleLiteralReplaceAction", shell_source)
        self.assertNotIn("RuleLiteralReplaceAction(", shell_source)

        other_sdk_sources = "\n".join(
            path.read_text()
            for path in Path("src/factgraph/sdk").rglob("*.py")
            if path != shell_path
        )
        self.assertNotIn("check_rule_literal_replace_action", other_sdk_sources)
        self.assertNotIn("import RuleLiteralReplaceAction", other_sdk_sources)
        self.assertNotIn(", RuleLiteralReplaceAction", other_sdk_sources)
        self.assertNotIn("RuleLiteralReplaceAction(", other_sdk_sources)

    def test_frontier_protected_entrypoints_do_not_drift(self) -> None:
        ruleref_source = Path("src/factgraph/core/rules/ruleref_substrate.py").read_text()
        proof_protocol = Path("src/factgraph/application/protocol/proofframe.py").read_text()

        self.assertNotIn("literal_replacements", ruleref_source)
        self.assertNotIn("RuleLiteralReplace", proof_protocol)

    def test_fact_overlay_and_proofframe_runtime_guards_remain_generic(self) -> None:
        fact_source = Path("src/factgraph/application/fact_overlay_runtime.py").read_text()
        proof_source = Path("src/factgraph/application/proofframe_runtime.py").read_text()

        self.assertNotIn("RuleLiteralReplaceAction", fact_source)
        self.assertIn("RULE_ACTIONS_NOT_SUPPORTED", fact_source)
        self.assertNotIn("RuleLiteralReplaceAction", proof_source)
        self.assertEqual(proof_source.count("rule_actions"), 1)


if __name__ == "__main__":
    unittest.main()
