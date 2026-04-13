"""Agent observability build_tracer tests."""

from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from factpy_kernel.agent import LangfuseConfig, LangfuseTracer, NoOpTracer, build_tracer


class _BrokenLangfuseClient:
    def __init__(self, **_kwargs) -> None:
        raise RuntimeError("bad config")


class AgentObservabilityBuildTracerTests(unittest.TestCase):
    def test_build_tracer_without_config_returns_noop(self) -> None:
        tracer = build_tracer()
        self.assertIsInstance(tracer, NoOpTracer)

    def test_build_tracer_missing_dependency_returns_noop(self) -> None:
        with patch(
            "factpy_kernel.agent.observability.langfuse_tracer._load_langfuse_module",
            side_effect=ImportError("missing langfuse"),
        ):
            tracer = build_tracer(
                langfuse_config=LangfuseConfig(
                    public_key="pk",
                    secret_key="sk",
                )
            )
        self.assertIsInstance(tracer, NoOpTracer)

    def test_build_tracer_invalid_client_setup_stays_safe(self) -> None:
        fake_module = types.SimpleNamespace(Langfuse=_BrokenLangfuseClient)
        with patch(
            "factpy_kernel.agent.observability.langfuse_tracer._load_langfuse_module",
            return_value=fake_module,
        ):
            tracer = build_tracer(
                langfuse_config=LangfuseConfig(
                    public_key="pk",
                    secret_key="sk",
                )
            )
        self.assertIsInstance(tracer, LangfuseTracer)
        tracer.record_single_segment_extraction(attributes={"segment_id": "seg_1"})


if __name__ == "__main__":
    unittest.main()
