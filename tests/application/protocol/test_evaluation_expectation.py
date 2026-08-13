from __future__ import annotations

import unittest

from factgraph.application.protocol import (
    ContainsRowExpectationV0,
    ExpectationResultV0,
    ProtocolShapeError,
    ResolvedExpectationValueV0,
)
from factgraph.application.protocol.evaluation_expectation import (
    CompiledContainsRowExpectationV0,
)
from factgraph.core.protocol.digests import sha256_hex


def _hex(label: str) -> str:
    return sha256_hex(label.encode())


def _token(label: str) -> str:
    return f"sha256:{_hex(label)}"


class EvaluationExpectationProtocolTests(unittest.TestCase):
    def test_intent_canonicalizes_alias_order_and_rejects_empty_or_duplicate(self) -> None:
        intent = ContainsRowExpectationV0("bob_present", (("age", 19), ("person", "bob")))
        self.assertEqual(tuple(alias for alias, _ in intent.selected_values), ("age", "person"))
        with self.assertRaisesRegex(ProtocolShapeError, "non-empty"):
            ContainsRowExpectationV0("exists_disguised", ())
        with self.assertRaisesRegex(ProtocolShapeError, "unique"):
            ContainsRowExpectationV0("duplicate", (("age", 19), ("age", 20)))

    def test_compiled_expectation_digest_is_value_and_query_bound(self) -> None:
        value = ResolvedExpectationValueV0("age", "int", 19, _hex("age-19"))
        one = CompiledContainsRowExpectationV0("bob_present", _hex("query-a"), (value,))
        two = CompiledContainsRowExpectationV0("bob_present", _hex("query-b"), (value,))
        self.assertNotEqual(one.expectation_digest, two.expectation_digest)

    def test_outcome_requires_status_specific_evidence(self) -> None:
        common = dict(
            expectation_id="bob_present",
            kind="contains_row",
            expectation_digest=_token("expectation"),
            query_digest=_hex("query"),
            targeted_query_wrapper_digest=_token("wrapper"),
            result_id="evalr_v1:" + _hex("result"),
            result_digest=_token("result-digest"),
            run_anchor_digest=_token("anchor"),
        )
        satisfied = ExpectationResultV0(
            **common,
            status="satisfied",
            completeness_basis="complete_native_enumeration_v0",
            matched_row_ids=("row-b",),
            diagnostic_code="EXPECTATION_CONTAINS_ROW_SATISFIED",
        )
        self.assertTrue(satisfied.outcome_digest.startswith("sha256:"))
        with self.assertRaisesRegex(ProtocolShapeError, "complete native"):
            ExpectationResultV0(
                **common,
                status="not_satisfied",
                completeness_basis="unknown",
                matched_row_ids=(),
                diagnostic_code="EXPECTATION_CONTAINS_ROW_NOT_SATISFIED",
            )
        with self.assertRaisesRegex(ProtocolShapeError, "matching rows"):
            ExpectationResultV0(
                **common,
                status="satisfied",
                completeness_basis="unknown",
                matched_row_ids=(),
                diagnostic_code="EXPECTATION_CONTAINS_ROW_SATISFIED",
            )
