"""Agent observability Langfuse tracer tests."""

from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from factpy.agent import LangfuseConfig, LangfuseTracer, build_tracer


class _RecordingLangfuseClient:
    instances: list["_RecordingLangfuseClient"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.__class__.instances.append(self)

    def trace(self, *, name: str, metadata: dict[str, object]) -> None:
        self.calls.append((name, metadata))


class _FailingTraceLangfuseClient(_RecordingLangfuseClient):
    def trace(self, *, name: str, metadata: dict[str, object]) -> None:
        raise RuntimeError(f"trace failed: {name} {metadata}")


class AgentObservabilityLangfuseTests(unittest.TestCase):
    def tearDown(self) -> None:
        _RecordingLangfuseClient.instances.clear()
        _FailingTraceLangfuseClient.instances.clear()

    def test_langfuse_tracer_forwards_name_and_metadata(self) -> None:
        fake_module = types.SimpleNamespace(Langfuse=_RecordingLangfuseClient)
        with patch(
            "agent.observability.langfuse_tracer._load_langfuse_module",
            return_value=fake_module,
        ):
            tracer = build_tracer(
                langfuse_config=LangfuseConfig(
                    public_key="pk",
                    secret_key="sk",
                    host="https://lf.example",
                    release="test",
                )
            )
        self.assertIsInstance(tracer, LangfuseTracer)
        tracer.record_batch_extraction(
            attributes={
                "doc_id": "doc_1",
                "total_segments": 2,
            }
        )
        client = _RecordingLangfuseClient.instances[-1]
        self.assertEqual(client.kwargs["public_key"], "pk")
        self.assertEqual(client.kwargs["secret_key"], "sk")
        self.assertEqual(client.kwargs["host"], "https://lf.example")
        self.assertEqual(client.kwargs["release"], "test")
        self.assertEqual(
            client.calls,
            [("agent.extraction.batch", {"doc_id": "doc_1", "total_segments": 2})],
        )

    def test_langfuse_trace_failure_is_swallowed(self) -> None:
        fake_module = types.SimpleNamespace(Langfuse=_FailingTraceLangfuseClient)
        with patch(
            "agent.observability.langfuse_tracer._load_langfuse_module",
            return_value=fake_module,
        ):
            tracer = build_tracer(
                langfuse_config=LangfuseConfig(
                    public_key="pk",
                    secret_key="sk",
                )
            )
        tracer.record_resolution(attributes={"doc_id": "doc_1"})


if __name__ == "__main__":
    unittest.main()
