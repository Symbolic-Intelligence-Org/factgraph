# Quickstart Docs Sync Blueprint: Audit Log

- Blueprint: [2026-06-01_quickstart-docs-sync.md](./2026-06-01_quickstart-docs-sync.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-01 | scoped | Blueprint + paired audit doc created post-strict-audit | Forked from `d12352e4` (docs-sync slice HEAD post-release-surface-audit archive). User directive 2026-06-01: "请根据我们 adopt 的完整设计文档以及实际代码来对文档的内容是否和实际代码行为对齐进行严格的审核" followed by "选 C, 查缺补漏" (Option C = full audit cycle + supplementary gap-finding). 7 parallel general-purpose agents executed against 12 quickstart docs vs shipped `src/factgraph/`; 28 findings reported. Supplementary "查缺补漏" verification by Claude found 5 additional findings (1 new broken anchor at namespace-map.md:144, 4 `factpy-kernel` legacy project name residuals). Total 33 actionable findings catalogued in `workflow/audit/active/2026-06-01_quickstart-vs-shipped.md`: 18 DRIFT + 13 AMBIGUOUS + 2 BUG. Priority tiers: P0 (2 user-runtime-error sites) + P1 (4 broken cross-refs) + P2 (13 signature/wording drift) + P3 (13 prose polish). Scope locked at "all 33 findings fixed in single commit". Lightweight CADENCE per docs-only post-archive pattern established by `d12352e4`; no separate preflight branch needed since audit doc IS the scope freeze artifact. Sacred Q-PR1 5-path 0-diff vs `4c472b50` preserved; master `562c74195df4...` unchanged; dirty baseline 8 entries preserved. |
| 2026-06-01 | implemented | Step 4.7 fix commit + factgraph re-projection + Step 4.8 closure | Step 4.7 single fix commit `b3c99f2f docs(quickstart): apply 33 audit findings (P0+P1+P2+P3)` landed all 33 audit findings across 11 doc files (105 insertions / 43 deletions). Factgraph feature branch `feature/v0.2.0-release-surface-audit-2026-06-01` force-pushed (5th iteration, `ca916dee` → `7ef339ee`). Step 4.8 closure populated blueprint §10 Outcome with per-priority deliverable + method effectiveness records (L1 parallel-agent breadth + supplementary depth; L2 single-commit P0..P3 absorption; L3 assertions.md as raw_kind/bound source-of-truth). Deviations recorded: agent-reported "27 omissions" was 18; AggregateAtom claim promoted to P0; factpy-kernel rename missed by all 7 agents. Teammate handoff `--source-ref` updated from `d12352e4` → `b3c99f2f`. Blueprint Status: `scoped → implemented`. Sacred Q-PR1 5-path 0-diff preserved through Step 4.7 + Step 4.8; master `562c74195df4...` unchanged; dirty baseline 8 entries preserved; 0 src/ touch; 0 release.sh execution. |

## Decision Notes

### 2026-06-01 — Audit-then-fix lightweight cadence rationale

- **Why audit-then-fix in one cycle, not full 9-stage CADENCE**: 33 doc fixes are all (b)/(c)-class drift per CADENCE 5-state classification. None require new design decisions. The audit doc already serves as the scope freeze artifact. Per CLAUDE.md exception path, "task blueprint" can be lightweight when the task is docs-only and audit-grounded.

- **Why 7 parallel agents + supplementary check**: scope (12 docs × ~30 claims each = ~360 claims) too large for sequential audit. Parallel agents covered breadth; supplementary check covered systematic patterns agents may have missed (project naming consistency, broken anchors).

- **Why "选 C, 查缺补漏" matters**: user explicitly requested supplementary gap-finding beyond initial findings. The 5 additional findings (1 BUG + 4 DRIFT) confirm the audit's value-add beyond the 7 agents — agents focused on API claims but missed systematic project-naming drift and cross-reference verification.

- **P0/P1/P2/P3 tier rationale**:
  - P0: user copy-pastes example → runtime error. Highest urgency.
  - P1: user clicks link → 404 or wrong section. High urgency, easy fix.
  - P2: signature in doc differs from code. Misleading but doesn't crash.
  - P3: prose unclear or inconsistent. Polish, not blocking.

- **factgraph re-projection strategy**: 4th force-push to `factgraph/feature/v0.2.0-release-surface-audit-2026-06-01` (`37cb335f` → `3e306c02` → `ec85b287` → `ca916dee` → next). Same overlay strategy proven in `ca916dee`: preserve 11 publish-infra files from factgraph/main, replace src/tests/, add docs/SECURITY.md + .github/workflows/factgraph-tests.yml from staging, copy docs/official/* from hnsm-backend (now including the 33 fixes).
