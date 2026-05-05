"""Step 3 runtime tests for Fact Overlay native MVP scaffolding."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from kernel.application import (
    build_schema_index,
    check_fact_overlay_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    FactOverlayCheckRequest,
    FactValueOverride,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.rules.rule_ir import RuleRegistry
from kernel.core.store import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(
    store: Store,
    index: Any,
    name: str,
    age: int,
    region: str,
) -> str:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "age").pred_id,
        encoded,
        [("int", age)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "region").pred_id,
        encoded,
        [("string", region)],
    )
    return encoded


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("$p",),
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="overlay-test",
        version="1.0",
        body_ir=body_ir,
        heads=(
            CompiledHeadCall(
                target_pred_id=target_pred_id,
                head_var_names=head_var_names,
            ),
        ),
    )


def _exists_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    body: list[Any] = [("pred", info.exists_predicate_id, ["$p"])]
    return body, info.exists_predicate_id


def _exists_plus_age_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
    ]
    return body, info.exists_predicate_id


def _override(encoded: str = "person:alice") -> FactValueOverride:
    return FactValueOverride(
        asrt_id="asrt-placeholder",
        pred_id="Person.age",
        e_ref=encoded,
        old_fact_tuple=(encoded, 25),
        new_fact_tuple=(encoded, 26),
    )


def _request(
    *,
    plan: CompiledDerivationPlan,
    binding: tuple[tuple[str, object], ...],
    overlay: tuple[FactValueOverride, ...],
    engine: str = "native",
) -> FactOverlayCheckRequest:
    return FactOverlayCheckRequest(
        plan=plan,
        binding=binding,
        overlay=overlay,
        engine=engine,  # type: ignore[arg-type]
    )


class FactOverlayRuntimePreflightTests(unittest.TestCase):
    def test_empty_overlay_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(),
            overlay=(),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)
        self.assertEqual(result.errors[0].code, "EMPTY_OVERLAY_NOT_PERMITTED")

    def test_ruleref_without_registry_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(
            body + [("ruleref", "person.exists", "1.0", ["$p"])],
            exists_pred,
        )
        request = _request(plan=plan, binding=(), overlay=(_override(),))

        result = check_fact_overlay_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_unresolvable_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(
            body + [("ruleref", "missing.rule", "1.0", ["$p"])],
            exists_pred,
        )
        request = _request(plan=plan, binding=(), overlay=(_override(),))

        result = check_fact_overlay_binding(request, store=store, registry=RuleRegistry())

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_REF_UNRESOLVABLE")

    def test_non_native_engines_short_circuit_unsupported(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        for engine in ("souffle", "problog", "pyreason"):
            with self.subTest(engine=engine):
                result = check_fact_overlay_binding(
                    _request(
                        plan=plan,
                        binding=(),
                        overlay=(_override(),),
                        engine=engine,
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "unsupported")
                self.assertIsNone(result.before)
                self.assertIsNone(result.after)
                self.assertIsNone(result.diff)
                self.assertEqual(result.errors[0].code, "ENGINE_OVERLAY_NOT_SUPPORTED")


class FactOverlayRuntimeNativeScaffoldTests(unittest.TestCase):
    def test_native_happy_path_passed_degenerate_result(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", encoded), ("$age", 25)),
            overlay=(_override(encoded),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertIsNotNone(result.before)
        self.assertIsNotNone(result.after)
        self.assertIsNotNone(result.diff)
        self.assertEqual(result.after.status, "passed")
        self.assertEqual(result.before, result.after)
        self.assertFalse(result.diff.status_changed)
        self.assertEqual(result.diff.matched_count_delta, 0)
        self.assertEqual(result.diff.bindings_added, ())
        self.assertEqual(result.diff.bindings_removed, ())

    def test_native_happy_path_failed_degenerate_result(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", encoded), ("$age", 99)),
            overlay=(_override(encoded),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.after.status, "failed")
        self.assertEqual(result.before, result.after)
        self.assertEqual(result.after.matched_count, 0)
        self.assertIsNone(result.after.matched_binding)
        self.assertFalse(result.diff.status_changed)

    def test_native_top_level_status_matches_after_status(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", encoded),),
            overlay=(_override(encoded),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, result.after.status)

    def test_native_phase_passes_remember_support_artifact_none(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", encoded),),
            overlay=(_override(encoded),),
        )

        from kernel.application import fact_overlay_runtime

        calls: list[dict[str, object]] = []
        original = fact_overlay_runtime.evaluate_native_where

        def spy_evaluate_native_where(*args: object, **kwargs: object) -> object:
            calls.append(dict(kwargs))
            return original(*args, **kwargs)  # type: ignore[misc]

        with patch.object(
            fact_overlay_runtime,
            "evaluate_native_where",
            side_effect=spy_evaluate_native_where,
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(len(calls), 1)
        self.assertIn("remember_support_artifact", calls[0])
        self.assertIsNone(calls[0]["remember_support_artifact"])


if __name__ == "__main__":
    unittest.main()
