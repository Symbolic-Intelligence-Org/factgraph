"""Layer 4C3-a validation pipeline tests."""

from __future__ import annotations

import unittest

from factpy_kernel.agent import AgentScope
from factpy_kernel.agent.documents import DocumentSegment
from factpy_kernel.agent.extraction.validation import validate_proposal
from factpy_kernel.tests._test_helpers import _schema_ir


def _segment() -> DocumentSegment:
    return DocumentSegment(
        segment_id="seg_1",
        doc_id="doc_1",
        segment_index=0,
        section_label="Section 1",
        page_number=1,
        char_offset_start=0,
        char_offset_end=42,
        raw_text="Alice is a VIP customer.",
        structural_clarity=0.9,
        pattern_type="entity_relation",
        parser_version="txt_v1",
    )


class AgentLayer4C3aValidationTests(unittest.TestCase):
    def test_valid_proposal_builds_fact_draft_spec_with_provenance(self) -> None:
        spec, rejection = validate_proposal(
            {
                "entity_type": "User",
                "entity_identity": {"user_id": "u-1", "locale": "zh"},
                "pred_id": "user:tag",
                "field_values": [("string", "vip")],
                "confidence": 0.9,
                "llm_note": "direct statement",
            },
            0,
            schema_ir=_schema_ir(),
            scope=AgentScope(
                allowed_entity_types=frozenset({"User"}),
                allowed_pred_ids=frozenset({"user:tag"}),
                min_confidence=0.5,
                agent_id="agent-l4c3a",
            ),
            segment=_segment(),
        )
        self.assertIsNone(rejection)
        assert spec is not None
        self.assertEqual(spec.pred_id, "user:tag")
        self.assertEqual(spec.extraction_provenance.segment_id, "seg_1")
        self.assertEqual(spec.extraction_provenance.raw_text, "Alice is a VIP customer.")

    def test_unknown_pred_id_is_rejected(self) -> None:
        spec, rejection = validate_proposal(
            {
                "entity_type": "User",
                "entity_identity": {"user_id": "u-1", "locale": "zh"},
                "pred_id": "user:missing",
                "field_values": [("string", "vip")],
            },
            0,
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3a"),
            segment=_segment(),
        )
        self.assertIsNone(spec)
        assert rejection is not None
        self.assertEqual(rejection.reason, "schema_pred_id_unknown")

    def test_field_type_mismatch_is_rejected(self) -> None:
        spec, rejection = validate_proposal(
            {
                "entity_type": "User",
                "entity_identity": {"user_id": "u-1", "locale": "zh"},
                "pred_id": "user:tag",
                "field_values": [("int", 7)],
            },
            0,
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3a"),
            segment=_segment(),
        )
        self.assertIsNone(spec)
        assert rejection is not None
        self.assertEqual(rejection.reason, "schema_field_type_mismatch")

    def test_scope_min_confidence_is_rejected(self) -> None:
        spec, rejection = validate_proposal(
            {
                "entity_type": "User",
                "entity_identity": {"user_id": "u-1", "locale": "zh"},
                "pred_id": "user:tag",
                "field_values": [("string", "vip")],
                "confidence": 0.2,
            },
            0,
            schema_ir=_schema_ir(),
            scope=AgentScope(min_confidence=0.5, agent_id="agent-l4c3a"),
            segment=_segment(),
        )
        self.assertIsNone(spec)
        assert rejection is not None
        self.assertEqual(rejection.reason, "scope_min_confidence")


if __name__ == "__main__":
    unittest.main()
