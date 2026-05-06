# Task Blueprint Audit: Rule Add Condition + Binding Planner(Batch 5c)

- Blueprint: [2026-05-05_add-condition-binding-planner.md](./2026-05-05_add-condition-binding-planner.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 5c Step 0 framing drafted on `v0.1-add-condition-binding-planner-2026-05-05` off Batch 5b final `5213e76`. The draft intentionally treats "add condition + binding planner" as a falsifiable premise rather than a pre-scoped implementation path. |

## Decision Notes

### 2026-05-06 — Initial Draft Framing

- **Default conservative posture:** Batch 5c has no v0.1.x prior art,so the draft makes abandonment/suspension and split outcomes first-class. Path A is only a narrow first-slice candidate.
- **False-merge risk is higher than v0.1.4:** v0.1.4 merged four parameter lanes under one DTO. Batch 5c may merge two lifecycle-different concerns:add-condition execution and binding-planner design. The draft's first falsifier tests that directly.
- **Parent-plan ProofFrame conflict surfaced early:** master plan §5.5c mentions `superseded_by_full_eval`,but Batch 4 collapsed that status. The draft requires Step 0 to resolve this explicitly instead of reviving the status by implication.
- **Current substrate grounding:** `where_ast_validate.py` already has dataflow rules for bound variables,`eq` binding,and `not` correlation. The draft asks Step 0 to decide whether this is enough for a narrow no-new-variable add-filter slice or whether a new binding planner is required.
- **Deferred hardening kept separate:** the Batch 4 ProofFrame `rule_refs` symmetric gap is named as out-of-scope unless explicitly scoped,so Batch 5c cannot hide unrelated hardening inside its implementation.

### 2026-05-06 — Pre-commit Review Pass 1

Review accepted the falsifiability-first framing and requested three P3 polish edits before draft commit:Path C was sharpened so it only means split into child blueprint(s),not an alternate spelling of Path A;falsifier #5 now cross-references the parent-plan ProofFrame conflict in §5.6;and inserted-locator identity options now list their hidden trade-offs so Step 0.B cannot treat them as equivalent.
