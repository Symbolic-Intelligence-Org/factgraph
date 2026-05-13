"""Tests for the ProbLog provenance trace carrier (adapter-local, V0 spike)."""

from __future__ import annotations

import unittest

from kernel.adapters.problog.provenance import (
    ProbLogTraceV0,
    parse_problog_trace,
    problog_trace_to_dict,
)


_SUCCESS_TRACE = """
 call query(X1) {0.00000} []
  result query(X1) (c(alice),) {{}} {0.00012} []
 complete query(X1) {0.00013} {0.00013} []
 call c(alice) {0.00019} [at 4:7]
  call a(alice) {0.00026} [at 3:9]
   result a(alice) (alice,) {{}} {0.00038} [at 3:9]
  complete a(alice) {0.00039} {0.00013} []
  call b(alice) {0.00041} [at 3:15]
   result b(alice) (alice,) {{}} {0.00053} [at 3:15]
  complete b(alice) {0.00055} {0.00014} []
  result c(alice) (alice,) {{}} {0.00060} []
 complete c(alice) {0.00061} {0.00042} []

c(alice):\t0.35
""".strip()

_FAIL_TRACE = """
 call query(X1) {0.00000} []
  result query(X1) (c(alice),) {{}} {0.00012} []
 complete query(X1) {0.00013} {0.00013} []
 call c(alice) {0.00019} [at 4:7]
  call a(alice) {0.00026} [at 3:9]
   result a(alice) (alice,) {{}} {0.00036} [at 3:9]
  complete a(alice) {0.00037} {0.00011} []
  call b(alice) {0.00039} [at 3:15]
  fail b(alice) {0.00041} {0.00002} []
 fail c(alice) {0.00043} {0.00024} []

c(alice):\t0
""".strip()


class ProbLogProvenanceV0Tests(unittest.TestCase):
    def test_parse_success_trace(self) -> None:
        trace = parse_problog_trace(_SUCCESS_TRACE)

        self.assertIsInstance(trace, ProbLogTraceV0)
        self.assertEqual(len(trace.events), 12)
        self.assertEqual(len(trace.answers), 1)
        self.assertEqual(trace.answers[0].query, "c(alice)")
        self.assertEqual(trace.answers[0].probability, 0.35)

        first_call = trace.events[0]
        self.assertEqual(first_call.event_type, "call")
        self.assertEqual(first_call.depth, 0)
        self.assertEqual(first_call.goal, "query(X1)")
        self.assertEqual(first_call.location, None)

        nested_result = trace.events[5]
        self.assertEqual(nested_result.event_type, "result")
        self.assertEqual(nested_result.depth, 2)
        self.assertEqual(nested_result.goal, "a(alice)")
        self.assertEqual(nested_result.result_terms, ("alice",))
        self.assertEqual(nested_result.location, "at 3:9")

    def test_parse_fail_trace(self) -> None:
        trace = parse_problog_trace(_FAIL_TRACE)

        fail_events = [event for event in trace.events if event.event_type == "fail"]
        self.assertEqual(len(fail_events), 2)
        self.assertEqual(fail_events[0].goal, "b(alice)")
        self.assertEqual(fail_events[0].elapsed_seconds, 0.00002)
        self.assertEqual(fail_events[1].goal, "c(alice)")

    def test_trace_to_dict(self) -> None:
        payload = problog_trace_to_dict(parse_problog_trace(_SUCCESS_TRACE))

        self.assertEqual(payload["engine"], "problog")
        self.assertEqual(payload["trace_type"], "proof_trace")
        self.assertEqual(payload["answers"][0]["query"], "c(alice)")
        self.assertEqual(payload["events"][0]["goal"], "query(X1)")


if __name__ == "__main__":
    unittest.main()
