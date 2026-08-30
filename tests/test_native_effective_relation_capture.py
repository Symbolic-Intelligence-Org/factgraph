from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
import inspect
from types import MappingProxyType
from unittest.mock import patch

from factgraph.application import (
    build_schema_index,
    evaluate_derivation_plans,
    field_predicate,
    resolve_selector,
)
from factgraph.application.derivation_runtime import (
    _evaluate_derivation_plans_with_native_effective_relation_capture,
    _evaluate_derivation_plans_with_native_relation_capture,
    _evaluate_derivation_plans_with_native_effective_relation,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationEvaluateRequest,
    EntitySelector,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store import Store
from factgraph.core.store import _evaluate as evaluate_module
from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, MetaKeyPolicy, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    nickname: str = Field()
    unused: str = Field()


def _store_with_people(*names: str) -> Store:
    store = Store(compile_schema_from_classes([Person]))
    index = build_schema_index(store.schema_ir)
    identity_pred_id = field_predicate(index, "Person", "name").pred_id
    for name in names:
        ref = resolve_selector(
            EntitySelector(entity_type="Person", identity={"name": name}),
            index=index,
        )
        assert ref.encoded_ref is not None
        set_field(
            store.ledger,
            identity_pred_id,
            ref.encoded_ref,
            [("string", name)],
        )
    return store


def _plan(where: list[object], *, derivation_id: str = "capture") -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id=derivation_id,
        version="1",
        body_ir=where,
        heads=(
            CompiledHeadCall(
                target_pred_id=f"{derivation_id}:row",
                head_var_names=("$x",),
            ),
        ),
    )


def _stable_outputs(outputs: list[object]) -> list[tuple[object, ...]]:
    return [
        (
            output.target,
            output.payload,
            output.key_tuple_digest,
            output.tup_digest,
            output.support_digest,
            output.support_kind,
            output.candidate_key,
            output.candidate_kind,
        )
        for output in outputs
    ]


class NativeEffectiveRelationCoreTests(unittest.TestCase):
    def test_private_effective_relation_capture_keeps_receipts_in_memory_only(self) -> None:
        store = _store_with_people("alice")
        request = DerivationEvaluateRequest(
            plans=(_plan([("pred", "Person:exists", ["$x"])]),),
            engine="native",
        )
        relation = project_view_facts_with_witness(store.ledger, store.schema_ir)
        effective = {"Person:exists": tuple(relation["Person:exists"])}
        support_before = dict(store._support_artifacts)
        candidates_before = dict(store._candidate_support_index)

        with patch.object(store, "_remember_support_artifact", wraps=store._remember_support_artifact) as artifacts, patch.object(
            store,
            "_remember_candidate_support",
            wraps=store._remember_candidate_support,
        ) as candidates:
            outputs, receipts = _evaluate_derivation_plans_with_native_effective_relation_capture(
                request,
                store=store,
                effective_relation=effective,
            )

        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].support_kind, "native_binding_v1")
        self.assertEqual(set(receipts), {outputs[0].support_digest})
        self.assertEqual(receipts[outputs[0].support_digest].kind, "native_binding_v1")
        artifacts.assert_not_called()
        candidates.assert_not_called()
        self.assertEqual(store._support_artifacts, support_before)
        self.assertEqual(store._candidate_support_index, candidates_before)
        with self.assertRaises(TypeError):
            receipts["sha256:" + "0" * 64] = receipts[outputs[0].support_digest]  # type: ignore[index]

    def test_private_receipt_observer_is_fail_closed_outside_override_scope(self) -> None:
        store = _store_with_people("alice")
        relation = project_view_facts_with_witness(store.ledger, store.schema_ir)
        effective = {"Person:exists": tuple(relation["Person:exists"])}

        def observer(_digest: str, _receipt: object) -> None:
            return None

        kwargs = dict(
            store=store,
            derivation_id="override",
            version="1",
            target_pred_id="override:row",
            head_vars=["$x"],
            where=[("pred", "Person:exists", ["$x"])],
            mode="native",
            engine_evaluate=store.evaluate_engine,
            _native_effective_relation_support_artifact_observer=observer,
        )
        with self.assertRaisesRegex(ValueError, "requires native effective-relation"):
            evaluate_module._evaluate_store(**kwargs)
        with self.assertRaisesRegex(ValueError, "requires _record_support_artifacts=False"):
            evaluate_module._evaluate_store(
                **kwargs,
                _native_effective_relation_override=effective,
            )
        with self.assertRaisesRegex(ValueError, "does not support registry-backed"):
            evaluate_module._evaluate_store(
                **kwargs,
                _native_effective_relation_override=effective,
                _record_support_artifacts=False,
                registry=object(),
            )
    def test_private_effective_relation_execution_is_no_provenance_and_requires_exact_dependencies(self) -> None:
        store = _store_with_people("alice")
        request = DerivationEvaluateRequest(
            plans=(_plan([("pred", "Person:exists", ["$x"])]),),
            engine="native",
        )
        relation = project_view_facts_with_witness(store.ledger, store.schema_ir)
        effective = {"Person:exists": tuple(relation["Person:exists"])}
        support_before = dict(store._support_artifacts)
        candidates_before = dict(store._candidate_support_index)

        with patch.object(store, "_remember_support_artifact", wraps=store._remember_support_artifact) as artifacts, patch.object(
            store,
            "_remember_candidate_support",
            wraps=store._remember_candidate_support,
        ) as candidates:
            outputs = _evaluate_derivation_plans_with_native_effective_relation(
                request,
                store=store,
                effective_relation=effective,
            )

        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].support_kind, "engine_no_witness_v1")
        artifacts.assert_not_called()
        candidates.assert_not_called()
        self.assertEqual(store._support_artifacts, support_before)
        self.assertEqual(store._candidate_support_index, candidates_before)
        with self.assertRaisesRegex(ValueError, "exactly cover"):
            _evaluate_derivation_plans_with_native_effective_relation(
                request,
                store=store,
                effective_relation={},
            )

    def test_effective_relation_override_requires_no_provenance_and_no_premise_filter(self) -> None:
        store = _store_with_people("alice")
        request = DerivationEvaluateRequest(
            plans=(_plan([("pred", "Person:exists", ["$x"])]),),
            engine="native",
        )
        relation = project_view_facts_with_witness(store.ledger, store.schema_ir)
        effective = {"Person:exists": tuple(relation["Person:exists"])}
        with self.assertRaisesRegex(ValueError, "requires _record_support_artifacts=False"):
            evaluate_module._evaluate_store(
                store,
                derivation_id="override",
                version="1",
                target_pred_id="override:row",
                head_vars=["$x"],
                where=[("pred", "Person:exists", ["$x"])],
                mode="native",
                engine_evaluate=store.evaluate_engine,
                _native_effective_relation_override=effective,
            )
        with self.assertRaisesRegex(ValueError, "requires _record_support_artifacts=False"):
            evaluate_module._evaluate_where_over_view_with_support(
                store,
                [("pred", "Person:exists", ["$x"])],
                root_result_kind="fact",
                _native_effective_relation_override=effective,
            )
        premise_schema = compile_schema_from_classes(
            [Person],
            meta_keys={"source": MetaKeyPolicy(premise_eligible=True)},
        )
        filtered_store = Store(
            premise_schema,
            premise_exclusions=MetaExclusion("source", frozenset({"blocked"})),
        )
        with self.assertRaisesRegex(ValueError, "does not support premise-filtered"):
            _evaluate_derivation_plans_with_native_effective_relation(
                request,
                store=filtered_store,
                effective_relation=effective,
            )
        with self.assertRaisesRegex(ValueError, "does not support premise-filtered"):
            evaluate_module._evaluate_where_over_view_with_support(
                filtered_store,
                [("pred", "Person:exists", ["$x"])],
                root_result_kind="fact",
                _native_effective_relation_override=effective,
                _record_support_artifacts=False,
            )

    def test_dependency_scan_does_not_treat_tuple_constants_as_atoms(self) -> None:
        self.assertEqual(
            evaluate_module._native_where_dependency_predicates(
                [
                    ("eq", ("pred", "not-a-dependency", ()), ("pred", "not-a-dependency", ())),
                    ("eq", ("ruleref", "constant"), ("ruleref", "constant")),
                ]
            ),
            (),
        )

    def test_observer_sees_the_single_projection_used_by_the_evaluator(self) -> None:
        store = _store_with_people("bob", "alice")
        projected = project_view_facts_with_witness(store.ledger, store.schema_ir)
        observed: list[object] = []

        with (
            patch.object(
                evaluate_module,
                "project_view_facts_with_witness",
                return_value=projected,
            ) as projector,
            patch.object(
                evaluate_module,
                "project_view_facts",
                wraps=evaluate_module.project_view_facts,
            ) as legacy_projector,
            patch.object(
                evaluate_module,
                "evaluate_native_where",
                wraps=evaluate_module.evaluate_native_where,
            ) as evaluator,
        ):
            outputs = evaluate_module._evaluate_store(
                store,
                derivation_id="capture",
                version="1",
                target_pred_id="capture:row",
                head_vars=["$x"],
                where=[("pred", "Person:exists", ["$x"])],
                mode="native",
                engine_evaluate=store.evaluate_engine,
                _native_effective_relation_observer=observed.append,
            )

        self.assertEqual(len(outputs), 2)
        projector.assert_called_once_with(store.ledger, store.schema_ir)
        legacy_projector.assert_not_called()
        evaluator.assert_called_once()
        self.assertEqual(len(observed), 1)

        snapshot = observed[0]
        self.assertIsInstance(snapshot, MappingProxyType)
        self.assertEqual(tuple(snapshot), ("Person:exists",))
        self.assertNotIn("person:name", snapshot)
        self.assertNotIn("person:nickname", snapshot)
        self.assertNotIn("person:unused", snapshot)
        self.assertEqual(snapshot["Person:exists"], tuple(projected["Person:exists"]))
        self.assertIsNot(snapshot["Person:exists"][0], projected["Person:exists"][0])
        evaluator_view = evaluator.call_args.args[0]
        self.assertEqual(
            evaluator_view,
            {
                "Person:exists": [
                    row.fact_tuple for row in projected["Person:exists"]
                ]
            },
        )
        for index, row in enumerate(projected["Person:exists"]):
            self.assertEqual(evaluator_view["Person:exists"][index], row.fact_tuple)
        witness_relation = evaluator.call_args.kwargs["witness_facts"]
        self.assertIs(witness_relation, snapshot)

        with self.assertRaises(TypeError):
            snapshot["new"] = ()  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            snapshot["Person:exists"][0].asrt_id = "changed"  # type: ignore[misc]

    def test_capture_seam_is_private_and_public_signatures_have_no_observer(self) -> None:
        store = _store_with_people("alice")
        plan = _plan([("pred", "Person:exists", ["$x"])])
        self.assertNotIn("observer", str(inspect.signature(evaluate_derivation_plans)))
        self.assertNotIn("observer", str(inspect.signature(evaluate_module.evaluate_store)))

        outputs, snapshot = _evaluate_derivation_plans_with_native_relation_capture(
            DerivationEvaluateRequest(plans=(plan,), engine="native"),
            store=store,
        )
        self.assertEqual(len(outputs), 1)
        self.assertEqual(tuple(snapshot), ("Person:exists",))
        with self.assertRaisesRegex(
            ValueError, "one native plan with one head"
        ):
            _evaluate_derivation_plans_with_native_relation_capture(
                DerivationEvaluateRequest(plans=(plan,), engine="souffle"),
                store=store,
            )


class NativeEffectiveRelationApplicationTests(unittest.TestCase):
    def test_zero_rows_still_capture_empty_predicate_inventory_once(self) -> None:
        store = _store_with_people("alice")
        plan = _plan(
            [("pred", "person:nickname", ["$x", "missing"])],
            derivation_id="zero",
        )
        observed: list[object] = []

        outputs, snapshot = _evaluate_derivation_plans_with_native_relation_capture(
            DerivationEvaluateRequest(plans=(plan,)),
            store=store,
        )
        observed.append(snapshot)

        self.assertEqual(outputs, [])
        self.assertEqual(len(observed), 1)
        self.assertEqual(tuple(observed[0]), ("person:nickname",))
        self.assertEqual(observed[0]["person:nickname"], ())

    def test_negation_uses_the_same_captured_empty_relation(self) -> None:
        store = _store_with_people("alice")
        plan = _plan(
            [
                ("pred", "Person:exists", ["$x"]),
                ("not", [("pred", "person:nickname", ["$x", "blocked"])]),
            ],
            derivation_id="negation",
        )
        observed: list[object] = []

        outputs, snapshot = _evaluate_derivation_plans_with_native_relation_capture(
            DerivationEvaluateRequest(plans=(plan,)),
            store=store,
        )
        observed.append(snapshot)

        self.assertEqual(len(outputs), 1)
        self.assertEqual(len(observed), 1)
        self.assertEqual(
            tuple(observed[0]),
            ("Person:exists", "person:nickname"),
        )
        self.assertEqual(observed[0]["person:nickname"], ())

    def test_nested_not_and_aggregate_dependencies_exclude_unrelated_schema(self) -> None:
        store = _store_with_people("alice")
        plan = _plan(
            [
                ("pred", "Person:exists", ["$x"]),
                ("not", [("pred", "person:nickname", ["$x", "blocked"])]),
                (
                    "eq",
                    "$identity_count",
                    (
                        "count",
                        None,
                        [("pred", "person:name", ["$who", "$identity_name"])],
                    ),
                ),
            ],
            derivation_id="recursive-dependencies",
        )
        observed: list[object] = []

        outputs, snapshot = _evaluate_derivation_plans_with_native_relation_capture(
            DerivationEvaluateRequest(plans=(plan,)),
            store=store,
        )
        observed.append(snapshot)

        self.assertEqual(len(outputs), 1)
        self.assertEqual(len(observed), 1)
        self.assertEqual(
            tuple(observed[0]),
            ("Person:exists", "person:name", "person:nickname"),
        )
        self.assertEqual(len(observed[0]["person:name"]), 1)
        self.assertEqual(observed[0]["person:name"][0].fact_tuple[1], "alice")
        self.assertEqual(observed[0]["person:nickname"], ())
        self.assertNotIn("person:unused", observed[0])

    def test_omitting_observer_preserves_legacy_output_semantics(self) -> None:
        store = _store_with_people("alice")
        request = DerivationEvaluateRequest(
            plans=(_plan([("pred", "Person:exists", ["$x"])]),)
        )

        legacy = evaluate_derivation_plans(request, store=store)
        observed: list[object] = []
        captured, snapshot = _evaluate_derivation_plans_with_native_relation_capture(
            request,
            store=store,
        )
        observed.append(snapshot)

        self.assertEqual(_stable_outputs(legacy), _stable_outputs(captured))
        self.assertEqual(len(observed), 1)


if __name__ == "__main__":
    unittest.main()
