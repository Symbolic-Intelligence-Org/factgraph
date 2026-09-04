"""Fault-injection characterization for the broad boundary in core/derivation/accept.

``accept_many_candidate_sets`` accepts each candidate through the ledger and
write-protocol adapters.  An unexpected adapter fault must become an explicit
``FAILED_RUNTIME`` item that blocks the candidate key - it must never be
reported as accepted, and its message/code must survive into the item.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factgraph.core.derivation import accept as accept_module
from factgraph.core.derivation.accept import accept_many_candidate_sets
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import WriteProtocolError
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    nickname: str = Field()


class _BoundaryFault(Exception):
    """Custom, non-WriteProtocolError failure injected into the accept boundary."""


def _ledger() -> object:
    return Store(compile_schema_from_classes([Person])).ledger


def _candidate(target: str = "t:p") -> CandidateSet:
    digest = "sha256:" + ("0" * 64)
    return CandidateSet(
        derivation_id="d1",
        derivation_version="1.0",
        run_id="run-1",
        target=target,
        key_tuple_digest=digest,
        tup_digest=None,
        payload={"terms": []},
        support_digest=digest,
        support_kind="native",
        generated_at=0,
        state="proposed",
    )


class AcceptManyBoundaryTests(unittest.TestCase):
    """src/factgraph/core/derivation/accept.py: ``accept_candidate_set`` boundary."""

    def test_unexpected_fault_becomes_a_failed_runtime_item(self) -> None:
        ledger = _ledger()
        candidate = _candidate()

        with patch.object(
            accept_module,
            "accept_candidate_set",
            side_effect=_BoundaryFault("injected accept failure detail"),
        ):
            items = accept_many_candidate_sets(ledger, [candidate], mode="best_effort")

        self.assertEqual(len(items), 1)
        item = items[0]
        # Not reported as success: the item is an explicit runtime failure.
        self.assertEqual(item["state"], "FAILED_RUNTIME")
        self.assertIsNone(item["entity_ref"])
        # Preserved detail: message and derived error code.
        self.assertEqual(item["error"]["message"], "injected accept failure detail")
        self.assertEqual(item["error"]["code"], "_BoundaryFault")
        # Nothing was written to the ledger.
        self.assertEqual(list(ledger.find_claims()), [])

    def test_write_protocol_error_is_classified_as_failed_validation(self) -> None:
        ledger = _ledger()
        candidate = _candidate()

        with patch.object(
            accept_module,
            "accept_candidate_set",
            side_effect=WriteProtocolError("protocol rejection detail"),
        ):
            items = accept_many_candidate_sets(ledger, [candidate], mode="best_effort")

        self.assertEqual(items[0]["state"], "FAILED_VALIDATION")
        self.assertEqual(items[0]["error"]["message"], "protocol rejection detail")

    def test_uppercase_code_prefix_is_preserved_as_the_error_code(self) -> None:
        ledger = _ledger()
        candidate = _candidate()

        with patch.object(
            accept_module,
            "accept_candidate_set",
            side_effect=_BoundaryFault("ACCEPT_ADAPTER_DOWN: engine unavailable"),
        ):
            items = accept_many_candidate_sets(ledger, [candidate], mode="best_effort")

        self.assertEqual(items[0]["error"]["code"], "ACCEPT_ADAPTER_DOWN")
        self.assertEqual(items[0]["state"], "FAILED_RUNTIME")

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        ledger = _ledger()
        candidate = _candidate()

        with patch.object(accept_module, "accept_candidate_set", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                accept_many_candidate_sets(ledger, [candidate], mode="best_effort")


if __name__ == "__main__":
    unittest.main()
