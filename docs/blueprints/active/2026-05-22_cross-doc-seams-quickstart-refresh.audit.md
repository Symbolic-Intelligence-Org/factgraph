# Task Blueprint Audit: Cross-Doc Seams And Quickstart Refresh

- Blueprint: [2026-05-22_cross-doc-seams-quickstart-refresh.md](./2026-05-22_cross-doc-seams-quickstart-refresh.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Docs-only post-Slice-7C scope recorded before cross-doc seam and quickstart edits. |
| 2026-05-22 | draft | Audit findings folded | A-1 through A-6 identify stale quickstart persistence/rules/namespace-map pages, reference-only cross-doc seam docs, and `registry=None` preservation in evidence docs. |
| 2026-05-22 | scoped | Scope locked | Quickstart persistence/rules/namespace-map refresh, narrow reference-doc current-truth pointers, and stale module-doc cleanup are in scope; source code and Q-chain decisions remain out of scope. |
| 2026-05-22 | implemented | Docs updated | Commit 69850a2d rewrote quickstart persistence, updated rules/inferences and namespace map, renamed the index entry, and added current-truth pointers to two design-point reference docs. |

## Decision Notes

### 2026-05-22 — Initial scope

This task is a documentation alignment pass on top of Slice 7C implementation
state (`f592733a`). It does not reopen Q-chain decisions, does not edit source
code, and does not perform release or push operations.

### 2026-05-22 — Audit findings

- A-1: `quickstart/persistence.md` is a required rewrite because it still
  teaches removed saved-rule/inference persistence handles.
- A-2: `quickstart/rules-and-inferences.md` must stop pointing users to saved
  refs and registry persistence.
- A-3: `quickstart/namespace-map.md` must remove saved-rule/inference namespace
  methods and handles.
- A-4: `quickstart/index.md` should rename the persistence page to workspace
  persistence / migration.
- A-5: design-point docs are non-authoritative working references; add narrow
  current-truth pointers if needed instead of performing a full redesign.
- A-6: `quickstart/evidence.md` valid `registry=None` runtime examples are
  preserved by design.
