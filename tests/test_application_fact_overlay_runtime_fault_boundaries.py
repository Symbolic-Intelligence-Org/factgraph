"""Fault-injection characterization for the broad boundary in fact_overlay_runtime.

The guarded site wraps the native overlay phases and the overlay projection.
A fault there must produce the typed ``invalid_request`` result with
``OVERLAY_PHASE_RUNTIME_ERROR`` and *no* partial phases - a half-run overlay
must never be presented as a completed before/after comparison.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from factgraph.application import (
    build_schema_index,
    check_fact_overlay_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application import fact_overlay_runtime
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    FactOverlayCheckRequest,
    ReplaceFact,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    age: int = Field()


class _BoundaryFault(Exception):
    """Custom, non-domain failure injected into the native overlay phase."""


def _build() -> tuple[Store, Any, FactOverlayCheckRequest]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)

    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": "alice"}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", "alice")],
    )
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", 25)])

    plan = CompiledDerivationPlan(
        derivation_id="overlay-fault-test",
        version="1.0",
        body_ir=[("pred", info.exists_predicate_id, ["$p"])],
        heads=(
            CompiledHeadCall(
                target_pred_id=info.exists_predicate_id,
                head_var_names=("$p",),
            ),
        ),
    )
    request = FactOverlayCheckRequest(
        plan=plan,
        binding=(("$p", encoded),),
        overlay=(
            ReplaceFact(
                asrt_id=age_asrt_id,
                pred_id=age_pred_id,
                e_ref=encoded,
                old_fact_tuple=(encoded, 25),
                new_fact_tuple=(encoded, 26),
            ),
        ),
        engine="native",
    )
    return store, index, request


class FactOverlayPhaseBoundaryTests(unittest.TestCase):
    """src/factgraph/application/fact_overlay_runtime.py: native phase boundary."""

    def test_phase_fault_becomes_invalid_request_without_partial_phases(self) -> None:
        store, _index, request = _build()

        with patch.object(
            fact_overlay_runtime,
            "_run_native_overlay_phase",
            side_effect=_BoundaryFault("injected overlay phase failure"),
        ):
            result = check_fact_overlay_binding(request, store=store)

        # Not reported as success: no status leak, no partial before/after/diff.
        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)

        self.assertEqual(len(result.errors), 1)
        error = result.errors[0]
        self.assertEqual(error.code, "OVERLAY_PHASE_RUNTIME_ERROR")
        # Preserved detail: the exception class survives into the typed error DTO.
        self.assertEqual(error.details.get("exception"), "_BoundaryFault")
        self.assertEqual(tuple(error.path), ("runtime",))
        self.assertEqual(result.requested_binding, request.binding)

    def test_projection_fault_takes_the_same_typed_outcome(self) -> None:
        store, _index, request = _build()

        with patch.object(
            fact_overlay_runtime,
            "_apply_fact_overlay_projection",
            side_effect=_BoundaryFault("injected projection failure"),
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.after)
        self.assertEqual(result.errors[0].code, "OVERLAY_PHASE_RUNTIME_ERROR")
        self.assertEqual(result.errors[0].details.get("exception"), "_BoundaryFault")

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        store, _index, request = _build()

        with patch.object(
            fact_overlay_runtime,
            "_run_native_overlay_phase",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                check_fact_overlay_binding(request, store=store)

    def test_happy_path_still_produces_both_phases(self) -> None:
        store, _index, request = _build()
        result = check_fact_overlay_binding(request, store=store)
        self.assertNotEqual(result.status, "invalid_request")
        self.assertIsNotNone(result.before)
        self.assertIsNotNone(result.after)


if __name__ == "__main__":
    unittest.main()
