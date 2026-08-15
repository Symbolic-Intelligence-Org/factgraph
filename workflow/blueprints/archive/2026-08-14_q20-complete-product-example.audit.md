# Task Blueprint Audit: Q20 complete product example

- Blueprint: [2026-08-14_q20-complete-product-example.md](2026-08-14_q20-complete-product-example.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | draft | Blueprint created | User requested that the current examples include a complete runnable Q20 workflow. |
| 2026-08-14 | scoped | Scope frozen | Extend the existing Q20 notebook with side-pinned candidate comparison; repair the documented managed-ref versus `EntityRef` boundary discovered during example audit. |
| 2026-08-14 | implementing | Notebook integration started | A public-SDK smoke run confirms an independently authored candidate Policy, a shared deterministic Scenario world and a side-pinned Native profile execute and replay as intended. |
| 2026-08-14 | implementing | Scope refined after examples audit | A complete user workflow must also execute Scenario collection mutation forms and all three attachment shapes.  The Rule-level attachment will use a distinct Rule so the tutorial demonstrates the overlap boundary correctly rather than triggering it. |
| 2026-08-14 | implementing | Initial tutorial/docs check completed | The first end-to-end pass persisted candidate, probability and choice output. A later pedagogical audit was still required before archival. |
| 2026-08-15 | implementing | CRUD audit correction | Review found that placing `add` and `without` on one field group can normalize away the non-conflicting mask. The example was changed to mask Carol's separate `obsolete` tag and to assert resolved operation evidence rather than infer it from API construction. |
| 2026-08-15 | implemented | Final tutorial and docs verified | Real `factpy` execution: all 13 code cells in the 28-cell notebook passed. The four CRUD operations resolve as `set_effective_value`, `ensure_member`, `set_exact_members`, and `without_value`; the last carries one masked witness. Candidate comparison and replay matched. Focused Q20 regression: 55 passed, 7 subtests; diff check clean. |
| 2026-08-15 | archived | Blueprint/audit pair archived | The current tutorial and SDK guide are the implementation truth; this pair retains the example-scope rationale and verification record. |

## Decision Notes

- The existing Q20 tutorial remains the single current product example rather
  than creating a competing duplicate notebook.
- Candidate comparison will be added as the missing complete-workflow segment;
  probability and WeightedChoice remain separately bounded, explicit sections.
- The public-SDK API currently requires `EntityRef` for a Query entity bind and
  the managed string reference for Scenario fields.  The example will teach
  that distinction rather than hide it with an unsupported coercion.
- The existing V1/Q19 and v0.2 examples remain separate historical/advanced
  paths.  Q20 stays a single SDK-only product tutorial in notebook 09.
- We updated the existing notebook rather than adding a duplicate: it is the
  sole current product journey and links both construction forms, fact/world
  variants, probability boundary and structured presentation/replay surface.
- Scenario construction alone is not sufficient pedagogical evidence. The
  final example checks resolved `operation_evidence`: a `without` operation is
  demonstrated through its actual masked witness, not merely through metadata
  on an unresolved request.
