"""Agent observability NoOpTracer tests."""

from __future__ import annotations

import unittest

from factpy.agent import NoOpTracer


class AgentObservabilityNoOpTests(unittest.TestCase):
    def test_noop_methods_do_not_raise(self) -> None:
        tracer = NoOpTracer()
        tracer.record_single_segment_extraction(attributes={"segment_id": "seg_1"})
        tracer.record_batch_extraction(attributes={"doc_id": "doc_1"})
        tracer.record_resolution(attributes={"doc_id": "doc_1"})


if __name__ == "__main__":
    unittest.main()
