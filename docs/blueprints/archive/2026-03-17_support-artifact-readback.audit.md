# Task Blueprint Audit: Support Artifact Readback

- Blueprint: [2026-03-17_support-artifact-readback.md](./2026-03-17_support-artifact-readback.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a focused follow-up blueprint to expose in-process support artifacts through a minimal readback path without touching service contracts or `run_rule` trace. |
| 2026-03-17 | draft | Readback shape aligned | Locked the readback shape to the existing `support_artifact_to_dict(...)` output, keeping `binding` as list-of-pairs and `pred_witnesses` as list-of-dicts rather than inventing a second display schema. |
| 2026-03-17 | implemented | Readback helper implemented | Added `core/store/_explain_support.py` and wired `Store.explain_support(...)` as the single public support readback entry. |
| 2026-03-17 | implemented | Minimal validation passed | `compileall` passed for touched store/view modules, and a native evaluate smoke confirmed `candidate.support_digest -> store.explain_support(...)` returns a non-None witness breakdown while unknown digests return `None`. |

## Decision Notes

- 2026-03-17: `render_support_artifact(...)` should remain a thin wrapper over `support_artifact_to_dict(...)`; if canonical and display shapes diverge later, the wrapper is the intended branching point.
- 2026-03-17: `Store.explain_support(...)` is the only public readback entry in this slice; `_support_artifacts` and `_lookup_support_artifact(...)` stay private implementation details.
- 2026-03-17: This slice does not attempt `candidate_id -> support_digest` reverse lookup, HTTP/service exposure, or durable artifact storage.
- 2026-03-17: The readback shape intentionally stays aligned with the canonical `_support.py` serialization (`binding` as list-of-pairs, `pred_witnesses` as list-of-dicts) to avoid maintaining two competing “official” dict formats at this stage.
