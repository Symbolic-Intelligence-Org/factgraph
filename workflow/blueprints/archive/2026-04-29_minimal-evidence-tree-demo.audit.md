# Task Blueprint Audit: Minimal Evidence Tree Demo

- Blueprint: [2026-04-29_minimal-evidence-tree-demo.md](./2026-04-29_minimal-evidence-tree-demo.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-29 | draft | Blueprint created | Initial scope recorded for a meeting-friendly minimal evidence-tree example. |
| 2026-04-29 | scoped | Scope freeze | Adopted source-backed DORA/EUR-Lex regulatory anchors and an examples-only notebook; no runtime or SDK behavior changes. |
| 2026-04-29 | implemented | Notebook and examples index added | Added the minimal DORA evidence-tree notebook and linked it from the learning path and notebook 02 next-step cells. |
| 2026-04-29 | verified | Notebook execution passed | `python -m jupyter nbconvert --to notebook --execute examples/03_dora_minimal_evidence_tree.ipynb --output 03_dora_minimal_evidence_tree.executed.ipynb --output-dir /tmp --ExecutePreprocessor.timeout=180` passed from the repo root after validating the notebook also runs from `examples/`. The resulting tree had one rule ref, recursive depth 1, 17 witness assertions, and no unresolved support. |
| 2026-04-29 | archived | Blueprint archived | Scope closed as examples-only with no module behavior docs required. |

## Decision Notes

- 2026-04-29: The demo must avoid fabricated entity facts. It will derive a review finding from public regulatory anchors, not assert compliance by a real or invented institution.
- 2026-04-29: The notebook should show the full process while staying native-only and local-runtime-only.
- 2026-04-29: Article and instrument facts were included in the rule conditions so the evidence tree visibly lands on article-level source anchors.
