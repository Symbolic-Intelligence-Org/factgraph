from __future__ import annotations

import unittest

import factgraph.sdk as sdk
from factgraph.application.protocol import Claim, DetachedRowError, EvaluateResult, EvaluateRow, EvidenceRef


class EvaluateResultSDKExportTests(unittest.TestCase):
    def test_sdk_reexports_evaluate_result_dtos_without_rule_flip(self) -> None:
        self.assertIs(sdk.Claim, Claim)
        self.assertIs(sdk.EvidenceRef, EvidenceRef)
        self.assertIs(sdk.EvaluateRow, EvaluateRow)
        self.assertIs(sdk.EvaluateResult, EvaluateResult)
        self.assertIs(sdk.DetachedRowError, DetachedRowError)
        self.assertIsNot(sdk.Rule, sdk.ApplicationRule)
        self.assertIs(sdk.LegacyRule, sdk.Rule)


if __name__ == "__main__":
    unittest.main()
