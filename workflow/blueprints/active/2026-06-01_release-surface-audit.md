# v0.2.0 Release Surface Audit Blueprint: stack-ready readiness for factgraph publish handoff

- Status: draft
- Created: 2026-06-01
- Last Updated: 2026-06-01
- Related Modules:
  - `scripts/release.sh` (release machinery)
  - `scripts/release_surface_allowlist.txt` (projection allowlist, 271 entries)
  - `scripts/project_release_surface.sh` (projection script)
  - `src/factgraph/` (current canonical source namespace, post-2026-04-27 split)
  - `docs/official/kernel/` (public quickstart docs target)
  - `docs/SECURITY.md` + `docs/api/openapi.yaml` (release-surface docs)
- Related Docs:
  - [`workflow/blueprints/archive/2026-06-01_baseline-drift-cleanup.md`](./2026-06-01_baseline-drift-cleanup.md) — direct predecessor; cleared 189 baseline failures to 0
  - [`workflow/blueprints/archive/2026-05-31_q-naming-f.md`](./2026-05-31_q-naming-f.md) — final Q-NAMING phase that closed the 6-phase naming routemap
  - [`workflow/CADENCE.md`](../../CADENCE.md) — 9-stage cadence (full variant for this audit-first blueprint)
  - [`workflow/AGENTS.md`](../../AGENTS.md) — workflow governance + sacred branch rules
  - Memory `project_v0_1_0_rc1_published.md` — v0.1.0-rc.1 published 2026-05-10 precedent
  - Memory `feedback_release_workflow_traps.md` — 6 traps caught during v0.1.0-rc.1 dry-runs (T1 allowlist sync, T2 test imports, T3 deny-pattern grep, T4 same-day re-tag, T5 typing-extensions, T6 EN README)
  - Memory `project_release_branch_invariants.md` — `master` + `v0.1-oss-prep` sacred; agent role = keep stack ready, NOT execute release
  - Memory `feedback_push_master_gate.md` — never auto-push master; feature branches OK to push
- Audit Log:
  - [2026-06-01_release-surface-audit.audit.md](./2026-06-01_release-surface-audit.audit.md)

## 1. Problem

Q-NAMING 6-phase routemap (AD/C/E/B1/B2/F) closed 2026-05-31 with 189 baseline failures inherited; Baseline Drift Cleanup meta-blueprint closed 2026-06-01 at `be0f2351` with cohort census 189 → 0. Both milestones pushed to `hnsm-backend/origin`. v0.2.0-rc release prep is now unblocked from a functional/test perspective.

However, the **publish projection surface** to the separate `factgraph` repo has NOT been re-audited since these two milestones. Each of them introduced concrete changes that touch what `scripts/release.sh` and `scripts/release_surface_allowlist.txt` consume:

- Q-NAMING-C archive `23389a2b` deleted 20 flat SDK shells (file deletions affect T1 allowlist sync)
- Q-NAMING-F renamed ~12 cluster file/class names (file path / symbol drift affects T1 + T3)
- Baseline cleanup SS3 moved `tests/test_sdk_read_policy.py` → `tests/_retired/` (file relocation affects T1 + T2)
- Baseline cleanup SS4 added new namespaced fixture imports (`sdk.entities`, `sdk.fields`, `sdk.assertions`) that may or may not need allowlist coverage
- Baseline cleanup SS5/SS6/SS7/SS8 modified ~22 test files (T2 test-import landscape changed)
- Multiple new test fixture body migrations to `Pred("person:age", p, age)` etc. may have re-arranged what the release projection sees

The agent's role per `project_release_branch_invariants` is **NOT to execute release**, but to **keep the stack ready** for teammate handoff. This blueprint is a feature-branch read-only audit producing a "stack-ready: YES/NO + N must-fix items" report. The release itself stays with the teammate per division of responsibility.

## 2. Goals

- **G1 Allowlist freshness vs Q-NAMING-C/F + baseline cleanup changes**: verify every entry in `scripts/release_surface_allowlist.txt` still resolves to an existing file; verify no shipped public-API file is missing from allowlist; classify each delta into `(a) shipped covers / (b) small gap / (c) shape conflict / (d) genuinely new / (e) deferred-aligned` (5-state per CADENCE Stage 1).
- **G2 Test exclusion landscape**: enumerate any test file in `tests/` or `src/domains/*/tests/` that imports modules not present in the kernel-only release projection (per T2). Post-2026-04-27 namespace is `src/factgraph/`, NOT the historical `src/factpy_kernel/` or `src/kernel/`; verify excluded-import patterns are reset to current reality.
- **G3 Deny-pattern audit**: grep shipped docs (those in allowlist) for references to private dev-only paths (`AGENTS.md`, `docs/blueprints/`, `docs/references/`, `workflow/`, `CLAUDE.md`, `AGENTS.md` in any sub-package) per T3. Each hit triages to (a) legitimate cross-ref / (b) needs rephrasing.
- **G4 EN-only verification**: scan allowlist for any `*.zh.md` entries; scan shipped source/docs for CN halves of CN/EN pairs that would need T6 projection handling. Verify v0.2.0 maintains v0.1.0-rc.1's EN-only kernel artifact convention.
- **G5 typing-extensions environment hygiene (informational)**: document the current host env state per T5; this is environment hygiene, not a code/doc fix, but the audit records the check.
- **G6 release.sh dry-run feasibility**: assess whether a `--dry-run` invocation of `scripts/release.sh v0.2.0-rc.1` is **safe to attempt** at audit time (without authorization to perform the dry-run itself). Identify any blocker that would prevent dry-run before the user authorizes it.
- **G7 v0.2.0 fresh additions delta vs v0.1.0-rc.1**: enumerate every shipped public-API file added since v0.1.0-rc.1 publish HEAD `1aa157cc` that requires new allowlist entries; surface any module/file expectation gap.

## 3. Non-goals

- N1 **NOT executing** `scripts/release.sh` (with or without `--dry-run`) without explicit user authorization.
- N2 **NOT pushing to the separate `factgraph` publish repo**; this blueprint operates entirely on `hnsm-backend/origin`.
- N3 **NOT touching `release/0.1.x` or `release/0.2.x`** (release-projection branches).
- N4 **NOT modifying `master`** (`hnsm-backend/master` = `562c74195df43e933bed92a3ff25de94dd8ce666` per `project_release_branch_invariants` sacred rule).
- N5 **NOT touching `v0.1-oss-prep`** (sacred per same memory).
- N6 **NOT touching Q-PR1 5 sacred paths** (`write_protocol.py` / `ledger.py` / `_builders.py` / `pyreason/` / `accept.py`) per AD/C/E/B1/B2/F + baseline cleanup inheritance.
- N7 **NOT performing release execution tasks** that belong to the release teammate (RELEASE_CHANGES.md authoring, version bump in `pyproject.toml`, git tag creation, PyPI metadata upload, GitHub Release creation, milestone branch creation, factgraph repo projection commit).
- N8 **NOT creating new public-API surfaces** during audit; this is read-only audit + optional drift-fix recommendation, not feature work.
- N9 **NOT auto-decide on Option D PRESERVE vs Option A MIGRATE** for surfaced drift; user reviews audit findings table and decides per-row.
- N10 **NOT touching the dirty baseline** (4 M + 2 D + 2 untracked entries preserved through entire baseline cleanup; remains preserved).
- N11 **NOT amending sacred or release-prep precedents** (`project_v0_1_0_rc1_published.md` lineage at `1aa157cc` immutable).

## 4. Current Context

### §4.1 Current branch + sacred state at audit start

- Branch `v0.2.0-blueprint-release-surface-audit-2026-06-01` forked from `v0.2.0-impl-baseline-drift-cleanup-2026-06-01` HEAD `be0f2351` (baseline cleanup archive HEAD).
- Inherits: AD/C/E/B1/B2/F complete lifecycles + N1-N24 invariants + Baseline Drift Cleanup N1-N9 + cumulative 189 → 0 baseline + all 8 SS shipped + Step 4.8 closure `c68b5626` + Step 4.9 archive `be0f2351`.
- Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- Q-PR1 5 sacred paths 0-diff vs `4c472b50`.
- Dirty baseline (4 M + 2 D + 2 untracked) preserved.

### §4.2 Release machinery inventory (read-only census at draft)

- `scripts/release.sh`: 1 entrypoint, projects source to `release/X.Y.x` and tags `vX.Y.Z[-rc.N]`. Per-trap defense from `feedback_release_workflow_traps` baked in.
- `scripts/release_surface_allowlist.txt`: 271 lines. Each line = a path that the projection includes; deletions of source files on `master` require simultaneous allowlist edits (T1).
- `scripts/project_release_surface.sh`: the projection script invoked by `release.sh`.
- `docs/official/kernel/`: public quickstart docs target (per `CLAUDE.md` "Non-workflow content only" doc map).
- `docs/SECURITY.md`: shipped security policy.
- `docs/api/openapi.yaml`: shipped OpenAPI spec.

### §4.3 Predecessor commit lineage referenced by this audit

- Q-NAMING-F archive `10b10981` — final 6-phase Q-NAMING closure
- Baseline cleanup Step 4.8 closure `c68b5626` + Step 4.9 archive `be0f2351` — current HEAD source for audit
- v0.1.0-rc.1 published `1aa157cc` on `origin/release/0.1.x` — historical precedent for the publish lineage

### §4.4 Cross-flip role assignment (per "延续一直以来的模式" user directive)

- Step 4.1 audit blueprint draft → Claude (this commit)
- Step 4.2 review → Codex (surfaces scope/methodology gaps)
- Step 4.3 preflight execution → Claude (independent artifact branch; reads release machinery + grep allowlist + categorize findings table)
- Step 4.4 preflight amend → Claude
- Step 4.5 self-check → Claude (doc-only, no commit)
- Step 4.6 scope freeze → Claude (`draft` → `scoped`)
- Step 4.7 implementation → **conditional**: if 0 drift → audit-only blueprint, skip to 4.8; if drift found → Codex implements fix slice with Claude review per cross-flip
- Step 4.8 closure → Claude or Codex (per CADENCE no strict assignment)
- Step 4.9 archive → Claude or Codex

## 5. Proposed Shape

### §5.1 7-bucket audit deliverable per CADENCE Stage 1 5-state classification

The Step 4.3 preflight produces a findings table with one row per investigated unit, classified into:

- **(a) shipped covers** — allowlist/docs/test correctly reflects current shipped state
- **(b) small gap** — minor rename/path adjustment needed (e.g., allowlist entry points to renamed file)
- **(c) shape conflict** — semantic mismatch requires user decision (e.g., should a new file be in allowlist or excluded as private)
- **(d) genuinely new** — no current allowlist coverage; needs decision on inclusion
- **(e) deferred-aligned** — intentionally excluded; no action needed

### §5.2 Stack-ready output report structure

Step 4.3 preflight produces a single report file at `workflow/audit/active/2026-06-01_release-surface-vs-shipped.md` (sub-type `vs-shipped`) with:

- §1 Scope (7 buckets G1-G7)
- §2 Inputs (release machinery + shipped public-API surface + predecessor commit refs)
- §3 Triage table per G-bucket, rows tagged with 5-state class
- §4 Open Questions (Q1, Q2, ... for c-class rows requiring user decision)
- §5 Frictions (anything ambiguous or surprising)
- §6 Cross-doc seams (out of scope for this audit but flagged for downstream)
- §7 Recommendations: either "stack ready; no fix needed; handoff to teammate" OR "drift found in rows X/Y/Z; recommend fix slice covering..."
- §8 Audit method notes
- §9 Completeness checklist

### §5.3 Conditional implementation slice

If §7 surfaces drift:
- A separate fix slice opens with its own narrow scope (LOCKED to surfaced drift rows only)
- Cross-flip per standard pattern: Codex implements fix, Claude reviews
- Scope discipline: no expansion beyond audit findings

If §7 declares "stack ready":
- Skip Step 4.7 implementation entirely
- Step 4.8 closure documents the "stack-ready: YES" outcome + records the handoff package for release teammate
- Step 4.9 archives audit blueprint

## 6. Boundaries And Invariants

- **Q-PR1 sacred 5 paths**: 0-diff vs `4c472b50` preserved through every commit of this blueprint (no source touch expected; audit is read-only + doc-only).
- **Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666`**: never modified.
- **Sacred `v0.1-oss-prep`**: never modified.
- **Dirty baseline**: 8 entries (4 M + 2 D + 2 untracked) preserved through every commit.
- **N7 layer authority**: preserved; audit does NOT touch `src/factgraph/`. If audit surfaces a drift that requires source touch, it is recorded as a finding for separate fix slice — NOT auto-implemented.
- **AD/C/E/B1/B2/F + baseline cleanup inherited contracts**: N1-N24 + baseline cleanup N1-N9 all preserved; no re-litigation.
- **Release execution boundary**: this blueprint NEVER executes `scripts/release.sh`. If §7 recommends a dry-run, that recommendation is delivered to the user, who decides whether to authorize.
- **Push policy**: feature branches (`v0.2.0-blueprint-release-surface-audit-2026-06-01` + any preflight + any impl) may be pushed to `hnsm-backend/origin` only with explicit user authorization at each push. `master` push NEVER auto. Projection to `factgraph` repo NEVER by agent.
- **Alpha release context**: factgraph is an alpha line; no historical user backward-compat guarantee. Drift fixes should align with Q-NAMING-C "no flat shells restoration without independent Red blueprint" precedent.

## 7. Acceptance

- [ ] Step 4.3 preflight findings table covers all 7 G-buckets (G1-G7) with 5-state classification per row
- [ ] Every allowlist entry resolves to an existing file in `master` HEAD source
- [ ] Every shipped public-API file is either in allowlist OR explicitly classified `(e) deferred-aligned`
- [ ] All `(c)`-class rows surfaced as formal Open Questions
- [ ] Stack-ready determination recorded: **YES** with handoff package OR **NO** with fix slice recommendation
- [ ] Q-PR1 sacred 5 paths 0-diff vs `4c472b50` preserved across all blueprint commits
- [ ] Sacred master unchanged
- [ ] Dirty baseline 8 entries preserved
- [ ] No push without explicit per-commit authorization
- [ ] If fix slice required: shipped after Codex implementation + Claude review + per-fix-slice canonical pytest census ≥ baseline cleanup HEAD `f1e0dc67` (2450 passed / 0 failed, recorded in audit log)
- [ ] AD/C/E/B1/B2/F + baseline cleanup inherited contracts preserved (verified via re-grep of N1-N24 + baseline N1-N9)
- [ ] `v0.1-oss-prep` + `master` + `release/0.1.x` + `release/0.2.x` (if exists) all untouched

## 8. Implementation Plan

1. **Step 4.2 review (Codex)**: surface scope/methodology gaps. Likely probes: (a) is G6 dry-run feasibility OUT of scope vs read-only audit definition? (b) is G5 typing-extensions purely informational vs needing remediation step? (c) is there a gap between G1 file-level allowlist freshness and G7 v0.2.0 fresh additions delta (overlap risk)? (d) should the audit also cover the prior Q-NAMING-C archive `23389a2b` 20-shell deletion as a discrete allowlist regression check?
2. **Step 4.3 preflight (Claude)**: on independent artifact branch `v0.2.0-release-surface-audit-preflight-2026-06-01` (forked from this scope-frozen blueprint HEAD). Execute:
   - 2.a Allowlist file-existence sweep: for each of 271 entries, verify file exists at current `master` HEAD `562c74195df4...` (NOT current blueprint branch HEAD, which has baseline cleanup local-only commits)
   - 2.b Shipped public-API enumeration: list every `src/factgraph/**/*.py` + every documented public docs file; cross-check vs allowlist
   - 2.c Q-NAMING-C archive `23389a2b` 20-shell deletion delta check: explicit grep of allowlist for any flat-shell file path that no longer exists
   - 2.d Q-NAMING-F renamed file delta check: explicit grep of allowlist for any pre-Q-NAMING-F file name (per Q-NAMING-F archive §10 closure)
   - 2.e Baseline cleanup SS3 retired file `tests/test_sdk_read_policy.py` → `tests/_retired/test_sdk_read_policy.py` allowlist check
   - 2.f T2 test-import landscape: grep all `tests/**/*.py` for imports of any module excluded by allowlist
   - 2.g T3 deny-pattern: grep allowlist-included docs for references to `AGENTS.md`, `workflow/`, `docs/blueprints/`, `docs/references/`, `CLAUDE.md`
   - 2.h T6 EN-only audit: grep allowlist for `*.zh.md`; grep source tree for CN/EN pair files
3. **Step 4.4 amend (Claude)**: apply preflight Required + Recommended LOCKs (PF-R / PF-r) on blueprint branch per Slice 7B Option A learning.
4. **Step 4.5 self-check (Claude)**: doc-only, no commit; verify PF coverage matrix consistent, invariant coverage complete.
5. **Step 4.6 scope freeze (Claude)**: blueprint Status `draft` → `scoped`.
6. **Step 4.7 implementation (conditional)**: as per §5.3.
7. **Step 4.8 closure**: blueprint Status `scoped` → `implemented`; populate §10 Outcome with stack-ready determination + handoff package OR fix-slice outcome.
8. **Step 4.9 archive**: `git mv` blueprint + audit log pair from `active/` to `archive/`; update `INVENTORY.md`; preflight artifact branch retained as immutable snapshot per Slice 7B Option A pattern.

## 9. Docs To Update

- This blueprint's audit log (`2026-06-01_release-surface-audit.audit.md`) — cumulative tracking through Step 4.8 closure
- Step 4.3 preflight artifact (`workflow/audit/active/2026-06-01_release-surface-vs-shipped.md`) — moved to `workflow/audit/archive/` at Step 4.9
- IF fix slice required: any allowlist edit to `scripts/release_surface_allowlist.txt` recorded as separate fix-slice commit with its own audit log row
- IF fix slice required + touches public-API docs: respective `src/factgraph/*/docs/` module docs updated per CADENCE Stage 4.8 docs sync
- NO update to `docs/README.md` expected (no new persistent docs entry from this audit)
- NO update to `scripts/release.sh` itself expected (release machinery is teammate territory)

## 10. Outcome / Deviations

(Step 4.8 closure outcome / deviations to be filled at implementation closure after Step 4.3 preflight findings + optional Step 4.7 fix slice.)
