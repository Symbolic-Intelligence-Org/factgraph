# v0.2.0 Release Surface Audit Blueprint: Audit Log

- Blueprint: [2026-06-01_release-surface-audit.md](./2026-06-01_release-surface-audit.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-01 | draft | Audit blueprint created post Q-NAMING + baseline cleanup closure | Step 4.1 draft on `v0.2.0-blueprint-release-surface-audit-2026-06-01` (forked from baseline cleanup archive HEAD `be0f2351`). User directive 2026-06-01: "可以考虑 A, 不过要先看关于 push 为 feature 分支的要求, 尤其是'我们只推 feature 分支', 具体的 release 由队友来实现" + clarification "我们指的是发布仓库 factgraph; origin 可以自由的 merge 因为它不是发布仓库, 此外同意 A'". Three governance anchors consulted: `feedback_push_master_gate` (master sacred, feature branches OK to push with auth), `project_release_branch_invariants` ("agent role = keep stack ready, NOT execute release"; factgraph publish repo is separate from `hnsm-backend/origin`), `feedback_release_workflow_traps` (6 traps T1-T6 from v0.1.0-rc.1 dry-run iterations). Scope: 7-bucket read-only audit (G1 allowlist freshness, G2 test exclusion, G3 deny-pattern, G4 EN-only, G5 typing-extensions informational, G6 release.sh dry-run feasibility, G7 v0.2.0 fresh additions delta vs v0.1.0-rc.1 `1aa157cc`). Out of scope per 11 non-goals (N1-N11): NO release.sh execution / NO factgraph repo push / NO release/0.1.x or 0.2.x touching / NO master mod / NO v0.1-oss-prep touching / NO Q-PR1 touching / NO release execution tasks (RELEASE_CHANGES.md / version bump / tag / PyPI / GitHub Release / milestone creation / factgraph projection commit) / NO new public-API surface creation / NO auto-decide on drift Options / NO dirty baseline touching / NO sacred precedent amend. Cross-flip per "延续一直以来的模式": Step 4.1 Claude draft (this), Step 4.2 Codex review, Step 4.3 Claude preflight, Step 4.4 Claude amend, Step 4.5 Claude self-check, Step 4.6 Claude scope freeze, Step 4.7 conditional (skip if 0 drift; Codex implements if drift found with Claude review), Step 4.8 closure, Step 4.9 archive. Sacred state at draft: Q-PR1 5 paths 0-diff vs `4c472b50`; master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged; dirty baseline 8 entries (4 M + 2 D + 2 untracked) preserved. |

## Decision Notes

### 2026-06-01 — Initial scope rationale (audit-first feature blueprint per A' direction)

- **Why audit-first, not impl-first**: per `project_release_branch_invariants` "agent's role is to keep stack ready, not to push it through to release", and per user 2026-06-01 directive "具体的 release 由队友来实现", the agent's deliverable is a STACK-READY REPORT, not a release execution. Audit-first cadence produces evidence + classification + recommendation; impl only fires conditionally if drift surfaced.

- **Why feature branch + cross-flip cadence**: matches Q-NAMING + baseline cleanup precedent established 2026-05-31 / 2026-06-01. User explicitly continued the cross-flip pattern via "延续一直以来的模式" earlier in the session; this audit inherits the same Claude-drafts / Codex-reviews-or-implements structure.

- **Why 7 G-buckets (not fewer)**: 6 from `feedback_release_workflow_traps` T1-T6 + 1 from delta-vs-v0.1.0-rc.1 (G7) needed to cover both regression risk (allowlist/file deletions from Q-NAMING-C/F + baseline cleanup) AND forward risk (new additions since v0.1.0-rc.1 publish lineage at `1aa157cc`). G5 (typing-extensions) intentionally INFORMATIONAL because that's environment hygiene not source/doc fix; including it surfaces the check explicitly so it doesn't get forgotten at handoff time.

- **Why 11 non-goals (high count)**: release-adjacent work has high collateral damage risk; explicit enumeration of what is OUT of scope protects against scope creep into actual release execution territory. N7 (NOT performing release execution tasks) is the load-bearing boundary that separates this audit from teammate work.

- **Predecessor commit lineage**: blueprint forked from `be0f2351` (baseline cleanup archive HEAD) NOT from `master` (which is at sacred `562c74195df4...`, pre-v0.2 line). This is intentional — the audit operates on the v0.2 feature-line state because that's what represents v0.2 publish candidate. Sacred master will be referenced at preflight (Step 4.3 2.a) as the master HEAD baseline that the projection actually consumes.

- **Cross-flip role assignment notes for this audit**: Step 4.2 review by Codex is critical because Claude drafted the scope; Codex's source-grounded review (Rule 1) is the first cross-check. Step 4.3 preflight by Claude is the actual finding-table production — independent artifact branch per Slice 7B Option A. Step 4.7 implementation conditional: if drift found, Codex implements + Claude reviews per established 8-SS pattern; if no drift, blueprint becomes audit-only deliverable.

- **Push gate posture**: this blueprint will produce 1 + N commits (where N = preflight commits + optional fix slice commits + closure/archive). Per `feedback_push_master_gate`, no auto-push of any commit. Each push decision requires user signal. Feature branches push to `hnsm-backend/origin` is OK per user clarification 2026-06-01; projection to `factgraph` publish repo NEVER by agent.

### 2026-06-01 — Cross-flip role assignment (per user "延续一直以来的模式" directive)

User explicitly continued AD/C/E/B1/B2/F + Baseline Drift Cleanup cross-flip pattern for this audit:

- Step 4.1 audit blueprint draft → Claude (this commit)
- Step 4.2 review → Codex
- Step 4.3 preflight drafter → Claude (per all prior precedents)
- Step 4.4 preflight amendment → Claude
- Step 4.5 self-check → Claude (doc-only)
- Step 4.6 scoped anchor → Claude
- Step 4.7 implementation **conditional**: Codex if drift found + Claude review per cross-flip; skip if 0 drift
- Step 4.8 closure → Codex or Claude (per CADENCE no strict assignment)
- Step 4.9 archive → Codex or Claude

If user wants to flip any role assignment, they may signal at any handoff point.
