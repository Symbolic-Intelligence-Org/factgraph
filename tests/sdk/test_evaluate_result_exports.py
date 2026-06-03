from __future__ import annotations

import unittest

import factgraph.sdk as sdk
import factgraph.sdk.dsl as dsl
from factgraph.application.protocol import (
    Claim,
    DetachedRowError,
    EvaluateResult,
    EvaluateRow,
    EvidenceRef,
    Explanation,
    ResultFingerprint,
)
from factgraph.application.protocol import Rule


class EvaluateResultSDKExportTests(unittest.TestCase):
    def test_sdk_reexports_evaluate_result_dtos_with_final_rule_flip(self) -> None:
        self.assertIs(sdk.Claim, Claim)
        self.assertIs(sdk.EvidenceRef, EvidenceRef)
        self.assertIs(sdk.EvaluateRow, EvaluateRow)
        self.assertIs(sdk.EvaluateResult, EvaluateResult)
        self.assertIs(sdk.Explanation, Explanation)
        self.assertIs(sdk.ResultFingerprint, ResultFingerprint)
        self.assertIs(sdk.DetachedRowError, DetachedRowError)
        self.assertIs(sdk.Rule, Rule)
        self.assertIs(sdk.ApplicationRule, sdk.Rule)
        self.assertIsNot(sdk.Rule, dsl.Rule)
        self.assertFalse(hasattr(sdk, "LegacyRule"))


if __name__ == "__main__":
    unittest.main()
