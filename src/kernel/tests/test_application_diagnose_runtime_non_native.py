"""Non-native Diagnose runtime tests (§8 Step 4 representability gate)."""
from __future__ import annotations

import unittest
from typing import Any

from kernel.application import (
    build_schema_index,
    diagnose_derivation_binding,
    entity_info,
    field_predicate,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
)
from kernel.core.store import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("$p",),
    *,
    head_spec: dict[str, Any] | None = None,
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="diagnose-non-native-test",
        version="1.0",
        body_ir=body_ir,
        heads=(
            CompiledHeadCall(
                target_pred_id=target_pred_id,
                head_var_names=head_var_names,
            ),
        ),
        head_spec=head_spec,
    )


def _exists_age_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
    ]
    return body, info.exists_predicate_id


class NonNativeRepresentabilityGateTests(unittest.TestCase):
    def _request(
        self,
        engine: str,
        *,
        binding: tuple[tuple[str, object], ...] = (),
        head_var_names: tuple[str, ...] = ("$p",),
        head_spec: dict[str, Any] | None = None,
    ) -> tuple[Store, DiagnoseRequest]:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        plan = _build_plan(
            body,
            target,
            head_var_names=head_var_names,
            head_spec=head_spec,
        )
        request = DiagnoseRequest(plan=plan, binding=binding, engine=engine)  # type: ignore[arg-type]
        return store, request

    def test_problog_body_only_binding_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request("problog", binding=(("$age", 25),))

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertEqual(result.errors[0].details["body_only_variables"], ["$age"])

    def test_pyreason_body_only_binding_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request("pyreason", binding=(("$age", 25),))

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")

    def test_problog_entity_target_plan_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request(
            "problog",
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")

    def test_pyreason_entity_target_plan_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request(
            "pyreason",
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")

    def test_pyreason_accumulates_entity_and_body_only_errors(self) -> None:
        store, request = self._request(
            "pyreason",
            binding=(("$age", 25),),
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(
            [error.code for error in result.errors],
            ["ENTITY_TARGET_NOT_REPRESENTABLE", "BINDING_NOT_REPRESENTABLE"],
        )
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)

    def test_problog_head_only_binding_is_representable_for_later_dispatch(self) -> None:
        store, request = self._request("problog", binding=(("$p", "person-1"),))

        with self.assertRaises(NotImplementedError):
            diagnose_derivation_binding(request, store=store)

    def test_pyreason_bare_head_var_treats_requested_var_as_body_only(self) -> None:
        store, request = self._request(
            "pyreason",
            binding=(("$p", "person-1"),),
            head_var_names=("p",),
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertEqual(result.errors[0].details["body_only_variables"], ["$p"])

    def test_souffle_body_only_binding_is_representable_for_later_dispatch(self) -> None:
        store, request = self._request("souffle", binding=(("$age", 25),))

        with self.assertRaises(NotImplementedError):
            diagnose_derivation_binding(request, store=store)

    def test_souffle_head_only_binding_is_representable_for_later_dispatch(self) -> None:
        store, request = self._request("souffle", binding=(("$p", "person-1"),))

        with self.assertRaises(NotImplementedError):
            diagnose_derivation_binding(request, store=store)


if __name__ == "__main__":
    unittest.main()
