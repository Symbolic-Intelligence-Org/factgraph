from __future__ import annotations

import unittest

from factgraph import sdk
from factgraph.application.protocol import (
    DetachedRowError,
    EvaluateResult,
    EvaluateRow,
    Explanation,
    ResultFingerprint,
    Rule,
)
from factgraph.sdk import dsl


class EvaluateResultSDKExportTests(unittest.TestCase):
    def test_sdk_reexports_evaluate_result_dtos_with_final_rule_flip(self) -> None:
        self.assertFalse(hasattr(sdk, "Claim"))
        self.assertFalse(hasattr(sdk, "EvidenceRef"))
        self.assertFalse(hasattr(sdk, "DetachedClaimError"))
        self.assertFalse(hasattr(sdk, "DetachedEvidenceRefError"))
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
