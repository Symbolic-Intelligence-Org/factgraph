"""Layer 4C3-a extraction models tests."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from agent import (
    ExtractionRejection,
    ExtractionResult,
    ExtractionProvenance,
    FactDraftSpec,
    build_response_model,
)
from kernel.tests._test_helpers import _schema_ir


class AgentLayer4C3aModelsTests(unittest.TestCase):
    def test_build_response_model_accepts_schema_values(self) -> None:
        response_model = build_response_model(_schema_ir())
        response = response_model(
            proposals=[
                {
                    "entity_type": "User",
                    "entity_identity": [
                        {"name": "user_id", "value": "u-1"},
                        {"name": "locale", "value": "zh"},
                    ],
                    "pred_id": "user:tag",
                    "field_values": [{"tag": "string", "value": "vip"}],
                    "confidence": 0.8,
                }
            ]
        )
        self.assertEqual(len(response.proposals), 1)
        self.assertEqual(response.proposals[0].pred_id, "user:tag")

    def test_build_response_model_rejects_unknown_pred_id(self) -> None:
        response_model = build_response_model(_schema_ir())
        with self.assertRaises(ValidationError):
            response_model(
                proposals=[
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:missing",
                        "field_values": [{"tag": "string", "value": "vip"}],
                    }
                ]
            )

    def test_extraction_result_accepts_scope_max_batch_rejection(self) -> None:
        spec = FactDraftSpec(
            entity_type="User",
            entity_identity={"user_id": "u-1", "locale": "zh"},
            pred_id="user:tag",
            field_values=[("string", "vip")],
            extraction_provenance=ExtractionProvenance(
                source_document_id="doc_1",
                segment_id="seg_1",
                char_offset_start=0,
                char_offset_end=10,
                raw_text="Alice VIP",
                extraction_method="llm_refined",
            ),
        )
        result = ExtractionResult(
            segment_id="seg_1",
            valid_specs=[spec],
            total_proposals=2,
            rejections=[
                ExtractionRejection(
                    reason="scope_max_batch_size",
                    detail="proposal exceeds scope.max_batch_size=1",
                    proposal_index=1,
                )
            ],
            model="gpt-4o-mini",
            llm_latency_ms=12,
        )
        self.assertEqual(result.total_proposals, 2)
        self.assertEqual(result.rejections[0].reason, "scope_max_batch_size")


if __name__ == "__main__":
    unittest.main()
