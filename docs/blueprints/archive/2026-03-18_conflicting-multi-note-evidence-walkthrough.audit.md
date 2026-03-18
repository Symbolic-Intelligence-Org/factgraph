# Task Blueprint Audit: Conflicting Multi-Note Evidence Walkthrough

- Blueprint: [2026-03-18_conflicting-multi-note-evidence-walkthrough.md](./2026-03-18_conflicting-multi-note-evidence-walkthrough.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the first conflicting-evidence implementation-facing slice after the anchoring concluded that explicit conflict retention is the right near-term pressure test and that source-linkage, uncertainty, and judgment contracts remain deferred. |
| 2026-03-18 | scoped | Scope freeze | Locked the walkthrough to explicit conflict retention, test-scope extraction helper and optional conflict meta, natural rule matching without automated resolution, and five-layer explain validation without source-linkage, uncertainty, or judgment contracts. |
| 2026-03-18 | implemented | Conflicting multi-note walkthrough regression landed | Added a synthetic conflicting multi-note walkthrough to `test_phase3_contracts_v1.py`, including retained low-risk/high-risk extracted facts, per-note round-trip checks, explicit conflict meta, non-witnessed-side retention checks, and five-layer explain delivery. |
| 2026-03-18 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 74 tests, confirming the conflict-retention walkthrough fits inside the current explain substrate without new source-linkage, extraction-uncertainty, or judgment contracts. |
| 2026-03-18 | archived | Blueprint archived | The walkthrough concluded that first-round explicit conflict retention can remain a test-scope vertical slice; no immediate source-linkage, uncertainty, judgment, or durable conflict-API blocker was exposed. |

## Decision Notes

- 2026-03-18
  - Direction rule: this slice must validate `notes -> conflicting facts -> rule` continuity, not reopen non-conflicting multi-note questions.
- 2026-03-18
  - Scope rule: extraction helper and optional conflict meta may exist in test scope, but this slice must not freeze a durable conflict, linkage, or judgment API.
- 2026-03-18
  - Outcome rule: if the walkthrough fails, classify the blocker as a single conflicting-evidence gap rather than expanding into a general provenance, uncertainty, or judgment framework.
- 2026-03-18
  - Validation rule: the walkthrough must explicitly prove retained conflict visibility by fetching the non-witnessed conflicting extracted fact through `assertion_index.get_assertion_detail()` and checking that its `claim_args` still carry the conflicting value and originating `note_id`.
- 2026-03-18
  - Outcome: the existing explain stack remained honest enough for first-round conflicting multi-note evidence. Conflicting low-risk and high-risk extracted facts remained independently inspectable, the non-witnessed side stayed retrievable in audit detail, and runtime/audit wording did not over-claim resolution, certainty, or judgment.

