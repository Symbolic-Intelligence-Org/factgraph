"""Layer 4C3-a ExtractionAgent tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factpy.agent import AgentScope, ExtractionConfig
from factpy.agent.documents import DocumentSegment
from factpy.agent.extraction.extractor import ExtractionAgent
from tests._test_helpers import _schema_ir


class _FakeCompletions:
    def __init__(self, behavior):
        self._behavior = behavior
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._behavior(kwargs)


class _FakeChat:
    def __init__(self, behavior):
        self.completions = _FakeCompletions(behavior)


class _FakeClient:
    def __init__(self, behavior):
        self.chat = _FakeChat(behavior)


def _segment() -> DocumentSegment:
    return DocumentSegment(
        segment_id="seg_1",
        doc_id="doc_1",
        segment_index=0,
        section_label="Section 1",
        page_number=1,
        char_offset_start=0,
        char_offset_end=120,
        raw_text="Alice is a VIP customer. Bob is a staff user.",
        structural_clarity=0.85,
        pattern_type="entity_relation",
        parser_version="txt_v1",
    )


class AgentLayer4C3aExtractorTests(unittest.TestCase):
    def test_dependency_missing_when_default_client_unavailable(self) -> None:
        agent = ExtractionAgent(config=ExtractionConfig())
        with patch(
            "agent.extraction.extractor.build_default_llm_client",
            side_effect=ImportError("missing deps"),
        ):
            result = agent.extract_from_segment(
                segment=_segment(),
                schema_ir=_schema_ir(),
                scope=AgentScope(agent_id="agent-l4c3a"),
            )
        self.assertEqual(result.error_kind, "dependency_missing")

    def test_extract_success_and_scope_max_batch_truncation(self) -> None:
        def _behavior(kwargs):
            response_model = kwargs["response_model"]
            return response_model(
                proposals=[
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-1"},
                            {"name": "locale", "value": "zh"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "vip"}],
                        "confidence": 0.9,
                    },
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-2"},
                            {"name": "locale", "value": "en"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "staff"}],
                        "confidence": 0.8,
                    },
                    {
                        "entity_type": "User",
                        "entity_identity": [
                            {"name": "user_id", "value": "u-3"},
                            {"name": "locale", "value": "en"},
                        ],
                        "pred_id": "user:tag",
                        "field_values": [{"tag": "string", "value": "review"}],
                        "confidence": 0.7,
                    },
                ]
            )

        fake = _FakeClient(_behavior)
        agent = ExtractionAgent(
            config=ExtractionConfig(max_text_chars=10),
            llm_client=fake,
        )
        result = agent.extract_from_segment(
            segment=_segment(),
            schema_ir=_schema_ir(),
            scope=AgentScope(max_batch_size=2, agent_id="agent-l4c3a"),
        )
        self.assertEqual(result.total_proposals, 3)
        self.assertEqual(len(result.valid_specs), 2)
        self.assertEqual(result.rejections[0].reason, "scope_max_batch_size")
        user_prompt = fake.chat.completions.calls[0]["messages"][1]["content"]
        self.assertIn("Alice is a", user_prompt)
        self.assertNotIn("VIP customer", user_prompt)

    def test_timeout_maps_to_extraction_error(self) -> None:
        fake = _FakeClient(lambda _kwargs: (_ for _ in ()).throw(TimeoutError("timed out")))
        agent = ExtractionAgent(llm_client=fake)
        result = agent.extract_from_segment(
            segment=_segment(),
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3a"),
        )
        self.assertEqual(result.error_kind, "llm_timeout")

    def test_invalid_config_returns_config_invalid(self) -> None:
        agent = ExtractionAgent(config=ExtractionConfig(max_text_chars=0), llm_client=_FakeClient(lambda kwargs: kwargs))
        result = agent.extract_from_segment(
            segment=_segment(),
            schema_ir=_schema_ir(),
            scope=AgentScope(agent_id="agent-l4c3a"),
        )
        self.assertEqual(result.error_kind, "config_invalid")

    def test_native_mistral_path_omits_timeout_and_uses_normalized_model(self) -> None:
        def _behavior(kwargs):
            self.assertEqual(kwargs["model"], "mistral-small-latest")
            self.assertNotIn("timeout", kwargs)
            response_model = kwargs["response_model"]
            return response_model(proposals=[])

        agent = ExtractionAgent(config=ExtractionConfig(model="mistral/mistral-small-latest"))
        with patch(
            "agent.extraction.extractor.build_default_llm_client",
            return_value=(_FakeClient(_behavior), "mistral-small-latest"),
        ):
            result = agent.extract_from_segment(
                segment=_segment(),
                schema_ir=_schema_ir(),
                scope=AgentScope(agent_id="agent-l4c3a"),
            )
        self.assertEqual(result.total_proposals, 0)
        self.assertEqual(len(result.valid_specs), 0)


if __name__ == "__main__":
    unittest.main()
