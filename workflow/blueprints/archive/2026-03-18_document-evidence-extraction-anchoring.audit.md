# Task Blueprint Audit: Document Evidence Extraction Anchoring

- Blueprint: [2026-03-18_document-evidence-extraction-anchoring.md](./2026-03-18_document-evidence-extraction-anchoring.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the next upstream anchoring slice after structured-source normalization proved viable, in order to compare the first document-evidence routes without immediately falling into OCR/LLM extraction scope. |
| 2026-03-18 | scoped | Scope freeze | Closed the route comparison by adopting structured form-like document extraction as the first document-evidence slice and treating free-text narrative extraction as a deferred route. |
| 2026-03-18 | implemented | Gate answers recorded | Resolved all three gates to walkthrough-level answers: document identifiers must appear in extracted fact terms, snippet/span provenance stays deferred, and first implementation should remain a test-scope walkthrough helper rather than a durable extraction API. |
| 2026-03-18 | archived | Blueprint archived | The anchoring concluded without code changes: the next slice is `form-document-extraction-walkthrough`, while source-handle, snippet provenance, and free-text extraction remain deferred. |

## Decision Notes

- 2026-03-18
  - Direction rule: the next slice must pressure provenance and extraction-boundary honesty, not continue revalidating structured feed behavior.
- 2026-03-18
  - Comparison rule: structured form-like document extraction is the default near-term candidate; free-text narrative extraction is only a comparison route, not the assumed first implementation.
- 2026-03-18
  - Scope rule: this anchoring must choose the first document-evidence vertical slice, not design a general provenance or extraction framework.
- 2026-03-18
  - Gate answer: first-round does not require first-class source-handle contract, but document identifiers must be embedded in extracted fact terms so same-document facts remain manually correlatable via assertion drill-down.
- 2026-03-18
  - Gate answer: snippet/span provenance is deferred for free-text scenarios; form-like extraction may rely on field-to-fact mapping, but ambiguous fields must not be silently discarded.
- 2026-03-18
  - Gate answer: first implementation remains a walkthrough/regression with test-scope extraction/normalize helper; durable extraction/provenance API is explicitly deferred.
