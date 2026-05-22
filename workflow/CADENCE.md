# Audit-to-Archive Workflow Cadence

## Provenance

This document was promoted to canonical workflow status on 2026-05-22 from the Claude auto-memory file `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_audit_to_archive_cadence.md`, as part of the workflow-governance-promotion slice (implementing blueprint at `workflow/blueprints/active/2026-05-22_workflow-governance-promotion.md`).

The auto-memory copy may continue to exist as a Claude session-priming pointer, but **this file is the canonical source of truth**. If the two diverge, this file wins.

**Validation provenance**: this cadence was built and validated end-to-end across 2026-05-20 → 2026-05-22, covering 1 audit (976 lines) + 8 Q closures (Q1-Q8) + 1 Q-delta decision (Q6-A) + 1 post-Q synthesis + 9 implementation slices (Slice 1 through Slice 7C, plus the post-Slice-7C docs-only cross-doc quickstart slice). The 9-slice lineage produced 80+ commits, all local, with sacred branches untouched and all focused test suites passing (25/25 on Slice 7C, 74/74 on Slice 7B, 68/68 on Slice 7A, 62/62 on Slice 6, 52/52 on Slice 5, 38/38 on Slice 4, 27/27 cross-slice tests on prior branches).

## Scope and Applicability

This cadence is the **primary work mode for large-scope audit-first implementation work**, including but not limited to:

- Subtractive removal slices (deletion of public surface, e.g., Slice 6 SavedRule Phase 2)
- Substrate migration slices (cross-module protocol or contract changes)
- Split-phase governance slices (e.g., A20(E) 7A + 7B + 7C lineage)
- v0.X.0 cadence steps (preparation for release boundary)
- Architecture-facing docs/workflow refactors (validated 2026-05-22 by the workflow-governance-promotion slice itself)

This cadence is **not mandatory for**:

- Tiny local typo fixes
- Comment-only edits
- Single-line bug fixes within established surface
- Test helper adjustments with no behavioral change
- Pure internal refactors with no public-API or workflow impact

Tasks that change workflow, architecture, protocol, or cross-module behavior must follow this cadence regardless of size; tiny local fixes may use the lightweight exception path per `workflow/AGENTS.md` and per the cleanup-slice cadence section of `workflow/blueprints/AGENTS.md`.

## Why this exists

The 2026-05-20/22 session produced:

- 1 audit doc (Phase 1-4, 976 lines) + Slice 7C audit amendment
- 8 Q decision closures (Q1-Q8 each on its own branch) + Q6-A delta decision
- 1 post-Q synthesis
- 9 implementation slices each going through full lifecycle (Slice 6 = large subtractive Q8 Phase 2 removal; Slice 7A + 7B = Q8 Phase 3 / A20(E) two-slice split-phase governance migration; Slice 7C = v0.2.0 cadence step / final registry adapter removal gated by Q6-A delta decision)
- 80+ commits, all local, sacred branches untouched
- 4 unrelated dirty files preserved across the entire session

This output was achieved with **zero scope creep, zero Phase-C-style over-introduction, zero accidental writes to sacred branches, zero N-3-style over-broadening into native runtime semantics**. The discipline below is why.

**Docs-only slice cadence applicability (validated 2026-05-22)**: the full 9-stage audit→blueprint→close→archive cadence is NOT exclusive to substrate/code work. The post-Slice-7C cross-doc seams + quickstart refresh slice (`v0.2.0-docs-cross-doc-quickstart-2026-05-22 @ 12d488cc`, 6-commit chain `4f55fe11/2055a887/69850a2d/d2cd83e4/c7ab669a/12d488cc`) validated that docs-only work can follow the same audit-first discipline — independent dedicated branch, full lineage, archive on completion. The cadence machinery is generalizable to any audit-first effort with a defined deliverable, even when no source code is touched.

## Top-level always-apply rules

### Sacred-branch isolation

- `master` and `v0.1-oss-prep` are **sacred**. Never auto-push, never auto-merge, never modify without explicit user authorization.
- All audit/blueprint/implementation work goes on `v<version>-<topic>-<date>` style branches.
- Verify with `git branch --show-current` and check sacred branch commit unchanged after each commit.

### Unrelated dirty file preservation

- At session start, observe and record the set of unrelated dirty files (modified + untracked).
- Throughout the entire session, **never `git add` or `git restore` these files**.
- Every per-commit `git status` check should confirm the unrelated set is unchanged.
- Even when running tests/lint, do not auto-fix unrelated failures (record as carry-forward in closure §10 instead).

### Single small commits

- Each commit should have a single clear purpose: blueprint stage transition, implementation, closure, archive, etc.
- Never batch multiple stage transitions into one commit.
- A scoped anchor commit (Status: draft → scoped) should literally change only Status + audit log event line (+ optional minor cleanup).
- An archive commit should be a pure `git mv` + README entry (+ optional cross-ref label fix).

### Per-commit verification ritual

After **every** commit, the other party verifies with at least:

```
git log -1 --stat <hash>          # commit message + file count + line counts
git status                         # unrelated dirty preserved + no rogue files
git branch --show-current          # correct branch
```

Plus stage-specific checks:

- **Blueprint commits**: `grep -n "^- Status:"` to confirm Status line.
- **Implementation commits**: re-run target test suite independently.
- **Closure commits**: Status `implemented` + audit log `implemented` event + tests pass.
- **Archive commits**: `ls active/ archive/` to confirm move + README entry.

Verification report includes a table showing each check + result + ✓/⚠. Always state what was **independently verified** vs what was **claimed**.

### "可以推进" mutual authorization

- Never auto-advance to the next phase. Every phase transition requires explicit "可以推进" (or equivalent) from the other party.
- Pattern works both directions:
  - User authorizes Claude → "可以推进" before Claude drafts something
  - Claude authorizes user → "可以推进" before user starts implementation
- Even when prerequisites are obviously met, do not skip the authorization step.
- The user remains the **decision-maker**; agent-side authorizations are procedural acknowledgements that prerequisites are satisfied, not independent decisions.

## Audit-discipline pipeline (workflow stages)

### Stage 1: Audit phase

Before any blueprint or implementation work touching a non-trivial subsystem:

- Read all relevant shipped source files **completely** (not grep snippets, not head/tail). Per `feedback_preflight_code_audit_required.md` Rule.
- Build a triage table classifying each design commitment as: (a) shipped covers / (b) small gap / (c) shape conflict / (d) genuinely new / (e) deferred-aligned.
- Surface open questions as Q1, Q2, ... blocking specific drift rows.
- Output single audit doc under `workflow/audit/active/<date>_<topic>-vs-shipped.md`.
- Phase the audit by batch to allow user review between batches (Phase 1 inventory → Phase 2 I-series triage → Phase 3 A-series triage by batches of 5 → Phase 4 D-series + cross-doc seams + recommendations).

### Stage 2: Q-resolution phase

Each open question gets its own decision doc + branch:

- Branch: `v<version>-q<N>-<topic>-decision-<date>` (single-Q form). Multi-Q slices serving the same blueprint may consolidate decisions on the blueprint branch — document the consolidation as a deviation in closure §10.
- Doc: `workflow/design/decisions/active/<date>_q<N>-<topic>-decision.md`
- Structure: Status / Created / Branch / Inputs / Scope / Non-scope / Decision / Rejected Alternatives / Supporting Evidence / Consequences / Acceptance Criteria / Decision Record.
- Cadence: one Q at a time. Per-Q review uncovers tightenings (typically 1-3 per Q).
- Severity-rank Q dependencies: load-bearing first (e.g., Q1 Database boundary), downstream/contingent last.

### Stage 3: Post-Q synthesis

After all Q closures, walk the audit §9 drift inventory and reclassify under closed-Q state:

- `blueprint-eligible` — gated only by closed Qs.
- `cross-doc blocked` — requires sibling-doc redraft (independent of internal Q closure).
- `no independent action` — projection / future gate / conditional.
- `already aligned` — shipped honors design intent.
- `deferred / v2+` — design defers + shipped honors.

Output single synthesis doc under `workflow/audit/active/<date>_post-q-<topic>-synthesis.md`. Lists recommended blueprint slice order with dependency analysis. Synthesis is not implementation authorization.

### Stage 4: Per-slice blueprint lifecycle (9 steps)

Each implementation slice goes through:

#### Step 4.1: Blueprint draft

- Branch: `v<version>-blueprint-<topic>-<date>`.
- Files: `workflow/blueprints/active/<date>_<topic>.md` + `<date>_<topic>.audit.md` (audit log pair).
- Blueprint structure: Status / Related Modules / Related Docs / Audit Log / Problem / Goals / Non-goals / Current Context / Proposed Shape / Boundaries And Invariants / Acceptance / Implementation Plan / Docs To Update / Outcome.
- `Status: draft`.
- Audit log Event Log: 1 row "draft | Blueprint created".

#### Step 4.2: Draft review + tightening

Reviewer (whoever didn't draft) checks:

- Per Rule 1: cite spot-check (file:line precision).
- Per Rule 2 bidirectional: not softening design strictness AND not over-broadening form-specific constraints.
- Q-contract honoring + prior-slice contract preservation.
- Scope discipline (Non-goals coverage).

Reviewer flags polish (P1, P2, ...) — typically 2-4 per draft. Drafter applies and commits tightening (or folds into preflight phase).

#### Step 4.3: Preflight (independent branch)

- Branch: `v<version>-<topic>-preflight-<date>` (separate from blueprint branch, so preflight is independent artifact).
- File: `workflow/audit/active/<date>_<topic>-preflight.md`.
- Re-read all blueprint-referenced shipped files **at preflight-row drafting time** (per Rule 1).
- Build findings table with 5-bucket severity:
  - **Required amendment before scoped** — true blocker, blueprint can't move to scoped without fix.
  - **Recommended amendment before scoped** — substance polish, implementation may surface ambiguity without.
  - **Verified assumption** — confirms blueprint assumption against shipped reality.
  - **Scoped-detail item** — push to scoped-blueprint or implementation phase.
  - **Abandonment blocker** — stop the whole slice (rare).
- Spot-check verification: at minimum, independently verify the 2-3 most critical/sharpest findings against source.

#### Step 4.4: Preflight amendment

- On blueprint branch (not preflight branch).
- Apply each required PF + each recommended PF.
- Update audit log Event Log + Decision Notes section with per-PF applied decision.
- Independent reviewer diff-checks each PF: blueprint diff + audit log diff cross-verified.
- Cleanup any "Decide ... during preflight" stale boilerplate in §8 Implementation Plan after amendment.

#### Step 4.5: Self-check (lightweight)

- Read amended blueprint + audit log.
- Confirm PF-1 to PF-N all covered in §5/§6/§7 + audit log decision notes.
- Independent reviewer second-opinion (verify no stale residual, no internal inconsistency, no remaining blockers).
- Self-check is doc-only, no commit (unless tightening needed).

#### Step 4.6: Scoped anchor

- Single small commit: `Status: draft` → `Status: scoped` + audit log event "scoped | Preflight amendments and self-check passed | PF-1 through PF-N covered by <hash>".
- Often +2/-1 line diff.
- Optional: cleanup any final redundancy spotted in self-check.

#### Step 4.6.5: Pre-impl grep amendment (Slice 6 finding, optional but recommended for subtractive slices)

Before opening the implementation branch, drafter runs a **deletion-grep** against shipped code to verify §5.10 (or equivalent cross-layer-consumer enumeration) is exhaustive:

```
grep -rnE "(<removed-symbol-1>|<removed-symbol-2>|...)" src/ tests/
```

For each new hit beyond §5.10 enumeration, surface as N-1, N-2, ... finding. User locks ONE of two options:

- **Option 1 (status rollback)**: status flips `scoped` → `draft`, blueprint re-amended, full self-check + new scoped anchor required before impl.
- **Option 2 (no status rollback)**: single amendment commit (or 2-commit pair: blueprint .md + audit log) folds new consumers into §5.10; status stays `scoped`; audit log records "scoped | Pre-impl grep amendment | N-1 through N-N from pre-implementation deletion grep folded into scoped blueprint; no code implementation started". This is the cadence used for Slice 6 per user lock.

This substage caught 5 consumers Slice 6 preflight missed (`_confidence_kind_resolver.py` Protocol, Souffle adapter `_load_query_rule_registry`, broader `cli.py:182-230` registry subcommands, `session.py:28-119` schema-only refactor, 2 ECSS tests). Without this substage, those would have surfaced as in-impl scope drift requiring blueprint walkback.

When to skip this substage:

- Pure additive slices (no removal grep target exists).
- Very small slices where §5 + §6 already covers all consumers (verify before skipping).

When this substage is critical:

- Any `delete` / `remove` / `drop` slice.
- Any slice touching shipped API surface that has unknown downstream callers.
- Any slice with §5.10-style cross-layer-consumer enumeration.

#### Step 4.7: Implementation

- Branch: `v<version>-impl-<topic>-<date>` (fork from scoped anchor).
- Per Rule 1: re-read source files at task-execution time, not relying on memory of earlier reads.
- Scope-bounded: implement only what's in scoped blueprint §3 Goals + §5 Proposed Shape; do not implement Non-goals items.
- Tests: cover each acceptance criterion + cross-slice non-regression.
- Lint pass (e.g., `ruff check`).
- Single feat commit with implementation + tests + docs together (see also 3-commit impl pattern below).

Reviewer verification:

- Independent test re-run (re-execute, don't trust claim).
- Independent scope grep (excluded API surfaces / cross-doc items).
- Cross-check PF-1 to PF-N implementation.
- Cross-check prior-slice contract preservation (identity formulas, API stability, etc.).

##### (A-fallback) mid-impl scope correction deviation (Slice 6 finding)

If impl-time re-read or grep surfaces additional consumers OUTSIDE blueprint §5.10 enumeration that were not caught by preflight or pre-impl grep substage, drafter MUST surface via `AskUserQuestion` with at least three options:

- **(Option strict-cite)** Stay within blueprint §5.10 enumeration literally; do not touch surfaces outside §5.10 even if they are now broken refs.
- **(Option expand)** Expand scope to include the newly-found consumers; risk: out-of-blueprint files (e.g., `src/agent/` when blueprint is factgraph+service).
- **(Option pause + blueprint amendment)** Pause impl; open a single amendment commit clarifying scope; re-anchor blueprint; then resume impl.

The (Option strict-cite) variant is the **A-fallback** — most discipline-aligned when the impl-time finding reveals a scope boundary the blueprint correctly intended to exclude. Document the choice in closure §10.6 deviations with citation back to the AskUserQuestion turn.

Slice 6 used (A-fallback) for `get_runtime_session_rules`: blueprint cite was `:1207-1224` (the FS-iteration block) but the function ALSO had a preserved-runtime ephemeral branch AND cascading consumers in `src/agent/` (out of §5.10 scope). User locked (A-fallback): strict-cite scope, FS branch removed, function/route/agent surface preserved as ephemeral-only with `fs_count: 0` constant. Documented in closure §10.6 + impl commit body.

This deviation pattern is DIFFERENT from in-impl scope drift:

- Scope drift = drafter unilaterally expanding scope ("while I'm here I'll fix X") → **anti-pattern, do not do**.
- (A-fallback) deviation = AskUserQuestion-mediated correction when blueprint enumeration meets reality with a true boundary case → **acceptable cadence with user-locked decision + closure §10.6 documentation**.

#### Step 4.8: Closure

- Single doc-only commit: `Status: scoped` → `Status: implemented` + §10 Outcome filled + audit log "implemented | Scoped implementation landed | Implementation `<hash>` ...".
- §10 Outcome records:
  - Landed modules + line counts.
  - PF alignment summary.
  - Implementation choices that carry forward (atomicity, etc.).
  - Acknowledged unrelated baseline failures (don't expand scope to fix).
  - Any deviations from PFs (justified).

#### Step 4.9: Archive

- Single `git mv` commit: blueprint pair from `active/` to `archive/` + README entry.
- Optional: cross-ref label fix (e.g., links pointing to `active/` need to flip to `archive/`).
- Can be batched across multiple slices (e.g., one archive commit moving slice 1 + slice 2 together).

## Cross-flip drafter/reviewer roles

The session validated both directions of role assignment:

- **User-drafts → Claude-reviews**: used for blueprints (slice 1, 2, 3) + implementations (slice 1, 2, 3) + preflights (slice 1, 2, 3).
- **Claude-drafts → User-reviews**: used for Q-decision docs (Q7, Q8, Q2, Q4, Q5, Q6).
- **Claude Stage-0/source-audits + drafts blueprint → User reviews + User drafts preflight/amend/scoped/implementation/closure/archive**: validated for Slice 4 attach lifecycle and Slice 5 SavedRule Phase 1 deprecation on 2026-05-21. This proved the workflow also holds when Claude opens the design entry and the user drives validation + implementation landing.
- **User Stage-0/source-audits → User drafts blueprint → Claude tightens + drafts preflight + drafts amendment + Claude drafts pre-impl-grep amendment + Claude implements + User reviews each stage**: validated for Slice 6 SavedRule Phase 2 removal on 2026-05-21. This proved the workflow also holds when Claude drives the high-touch substages and the user is the per-stage reviewer + decision authorizer.
- **User Stage-0/source-audits → User drafts blueprint → Claude reviews + Claude drafts preflight + Claude drafts amendment + Claude drafts scoped anchor + User drafts pre-impl grep + User implements + Claude reviews + User fixes P1 + Claude reviews + User closure + Claude archive**: validated for Slice 7A A20(E) schema anchor migration on 2026-05-21. Most-balanced cross-flip pattern to date.
- **Claude Stage-0/source-audits → User OQ locks → Claude drafts blueprint → User reviews + User drafts preflight + Claude drafts amendment (mis-landed on wrong branch + Option A recovery) + User cleanup + User scoped anchor + User pre-impl grep + User implements + Claude reviews (clean, 0 P1) + Claude drafts closure + Claude drafts archive**: validated for Slice 7B A20(E) registry final exit on 2026-05-21. First slice where Claude drove Stage 0 + blueprint draft + Step 4.4 + Step 4.8 + Step 4.9.

Both work. The signal for switching:

- Reviewer's authorization to drafter: "可以推进 [drafting X]".
- Drafter's request for review: "请 review" / "等待 review" / "下一步 review".

Discipline applies symmetrically regardless of who's in which role.

## Option A wrong-branch recovery pattern (Slice 7B finding)

**When**: a blueprint-stage amendment (typically Step 4.4 preflight amendment, Step 4.5 cleanup, Step 4.8 closure, or any commit that belongs on the blueprint branch) is committed by mistake on a preflight/independent-artifact branch. Slice 7B Step 4.4 hit this: Claude was on the preflight branch (after user landed the Step 4.3 preflight commit there) and committed `7e500b04` "preflight amendment" without switching to the blueprint branch.

**Symptoms**:

- `git branch --show-current` shows preflight/independent-artifact branch instead of blueprint branch.
- The commit content is correct (right files, right edits) but the branch placement is wrong.
- Preflight branch was supposed to stay at preflight-only HEAD as an independent artifact; now has an extra commit on top.

**Detection**: should be caught immediately by per-commit ritual `git branch --show-current` check. If missed at commit time, surfaces in subsequent state-report verification.

**Recovery — Option A (recommended)**: cherry-pick the commit content onto the correct branch + use user-authorized `git branch -f` to move the wrong-branch ref back. Sequence:

1. `git checkout <correct-blueprint-branch>` (switches HEAD, working tree carries unrelated dirty unchanged).
2. `git cherry-pick <wrong-commit-hash>` (produces new commit with same content on correct branch; new hash).
3. **User-authorized destructive step**: `git branch -f <preflight-or-independent-branch> <correct-pre-mistake-hash>` (moves the wrong-branch ref back to its proper HEAD; the misplaced commit becomes orphaned but reachable via reflog for ~30 days).
4. Verify: both branches at correct HEADs, sacred unchanged, unrelated dirty unchanged.

**Why this is OK**:

- Cherry-pick is non-destructive (just adds a commit).
- `git branch -f` is destructive per cadence ("NEVER run destructive git commands unless the user explicitly requests these actions"), so it requires explicit user authorization — never run automatically.
- The misplaced commit is preserved in reflog; no data loss.
- The commit content is recreated on the correct branch with content-identical diff (only hash differs).

**Rejected alternatives**:

- Option B (cherry-pick only, leave wrong-branch as-is): leaves preflight branch with an extra commit it shouldn't have; soft cadence violation we'd carry forward.
- Option C (`git revert` on wrong-branch + redo on correct branch): adds 2 extra commits; the revert itself is a violation marker; most discipline-aligned but noisiest.

**Documentation handling** (Slice 7B precedent):

- Recovery is documented in the **closure §10 deviations** section.
- Recovery is documented in **cross-session memory consolidation** entries.
- Recovery is **NOT** added as a blueprint audit-log row (per user direction during Slice 7B recovery: "do not add another blueprint audit-log row just for the branch-placement mistake unless the recovery changes task content"). The misplaced commit's audit-log content already covers the substantive change; adding a "we put it on the wrong branch then moved it" row would be process noise, not substantive task content.

**Hard lock**: "DO NOT commit a blueprint-stage amendment on a preflight/independent-artifact branch by mistake. Slice 7B Step 4.4 caught this and resolved via Option A recovery; if this recurs, follow the same recovery path."

## First clean Step 4.7 review with zero P1 fix (Slice 7B finding)

**Observation**: Slice 6 had Step 4.7 review surface P1-2 (`apply_execute.py` no-op shim) fixed in `d64d5513`. Slice 7A had Step 4.7 review surface P1-A1 (`save_workspace(...)` no-op shim) fixed in `98be5c5a`. Both were the same family pattern (function signature retains no-longer-used parameters as silent no-op kwargs). Slice 7B implementation passed Step 4.7 independent review with **0 P1 findings, 0 recommended, 11 verified, 1 scoped-detail, 0 abandonment**, requiring zero post-review fix commits.

**Why this matters**: validates that early-stage cadence substages (Step 4.2 review tightening + Step 4.3 preflight + Step 4.4 preflight amendment + Step 4.6.5 pre-impl grep amendment) absorbed the structural risks before implementation began. The no-op shim repeat pattern was specifically called out in Slice 7B preflight PF-2 (deprecation scope-restriction) and PF-3 (dead-import cleanup) such that implementation handled both correctly on first pass.

**When to expect clean Step 4.7**:

- After preflight has enumerated all symbol-removal scopes (PF-2/PF-3-style) and pre-impl grep substage has caught residual external callers (N-findings).
- After Step 4.2 tightening has resolved any "preflight may decide" wording (avoiding open-ended scope drift).
- For slices that follow the formalized 9-stage cadence including Step 4.6.5.

**When NOT to expect clean Step 4.7**:

- For slices where preflight is rushed or sparse.
- For slices that touch new functional areas where the no-op-shim repeat pattern hasn't been preemptively listed.
- For slices with cross-package impacts that exceed grep coverage.

This pattern is now expected for well-prepared slices. Reviewers should still independently run Step 4.7 verification (re-run tests, scope grep, cross-slice contract check) even when a clean result is anticipated.

## Preemptive Option A application (Slice 7C finding)

Slice 7C Step 4.4 preflight amendment landed **directly on the blueprint branch** (`8207eee4`) with no Slice 7B-style cherry-pick + `git branch -f` recovery operation. This validates Slice 7B's Option A cadence-learning defensive value: once a recovery pattern is documented, the **explicit knowledge of the failure mode prevents recurrence**.

**Pattern**:

- After preflight branch produces independent-artifact preflight commit (e.g., `2adf3438`).
- Drafter switches back to blueprint branch BEFORE any amendment work.
- Amendment commit lands on blueprint branch from the start.
- No recovery operation needed.

**Why this matters**: The Slice 7B incident `7e500b04` (wrong-branch commit) was costly even with successful Option A recovery — it required user-authorized destructive `git branch -f` ref movement. Slice 7C's preemptive avoidance demonstrates that **cadence learnings act as forward-looking defenses**, not just retrospective postmortems.

**When to apply**: Every slice with a separate preflight branch. Drafter should explicitly switch branches between preflight commit and blueprint-stage amendment as a routine step, not as a recovery action.

## 3-commit impl pattern generalization

Two slices have used the same 3-commit impl pattern: Slice 6 (`0d128fc4` main + `9cfd82e7` doc cleanup + `d64d5513` Step 4.7 fix) and Slice 7C (`cc327987` main + `ff79870b` P1 fix + `f592733a` docs cleanup). This is now a **standard pattern for large-scope slices** (~15-30 file impl + extensive test/docs cascade).

**Pattern structure**:

1. **First commit — `feat: main impl`**: Production code + new tests + core test refactors. Single feat commit per blueprint §8 step 12 preference. Target: cover Steps 2-9 of typical 9-step impl plan.
2. **Second commit — `fix: Step 4.7 P1 fix`**: After Step 4.7 review surfaces P1 findings (test-collection regressions, narrow contract corrections, new test coverage for R-1-style recommendations). Surgical scope.
3. **Third commit — `docs: align`**: Comprehensive doc updates across blueprint §10 targets. Often largest by file count but mechanical. May include OpenAPI / quickstart / module docs.

**When to use 3-commit vs 1-commit**:

- **1-commit (clean)**: Small/medium slices, well-prepared, Step 4.7 produces 0 P1 findings (Slice 7B precedent).
- **3-commit**: Large-scope slices touching many doc + test surfaces, or where Step 4.7 P1 review reveals a needed narrow correction. Acceptable per blueprint §8 step 12 "prefer one feat commit unless review forces a narrow fix commit".

**Anti-pattern (avoid)**: Single mega-commit attempting docs + code + tests + P1 fixes simultaneously. Always allow Step 4.7 review to find issues post-impl + apply a narrow follow-up.

## Q-delta-decision multi-sub-issue lock pattern (Slice 7C finding)

Slice 7C's Q6-A delta decision locked **six sub-issues `(a)-(f)` in a single decision document** (`docs/decisions/2026-05-21_q6a-registry-adapter-final-removal-decision.md` @ `c9aeafae`; will migrate to `workflow/design/decisions/archive/` after slice closure). This pattern emerged when:

- A previously closed Q-decision (Q6) has a pre-commitment clause that needs revisiting.
- Multiple sub-issues span apply-execute survival / service field policy / Souffle ruleref / historical-marker handling / error-type / version-bump cadence.
- Each sub-issue has multiple shipped options requiring user lock-down.

**Pattern structure**:

1. **Open delta decision** (not full Q reopen): `Q<N>-<letter>` naming (e.g., Q6-A).
2. **Identify N sub-issues** in audit phase, each with 2-4 distinct shipped options.
3. **Single decision document** with §3.N per-sub-issue sections: Decision / Rejected Alternatives / Supporting Evidence / Consequences.
4. **Step 2 review** challenges per-sub-issue, surfaces tightenings.
5. **Final closure** locks all N sub-issues before any blueprint stage.
6. **Blueprint §4.2 lock table** cites the closed Q-delta-decision as input; impl phase has **zero mid-impl re-litigation** of locked sub-issues.

**Why this matters**: Without this pattern, mid-impl scope correction (Slice 6 (A-fallback) style) would be much more frequent and disruptive for slices touching multiple controversial sub-issues.

**When to use**: Future slices that need to override a single clause of a closed Q-decision while preserving the rest of the Q as historical anchor.

## N-3 generic-runtime-registry protective preservation lock (Slice 7C finding)

Slice 7C's pre-impl grep amendment (`f2960fd4`) introduced **N-3 as a protective preservation lock** — a finding type that prevents impl over-broadening into native runtime semantics.

**Pattern**:

- During pre-impl grep (Step 4.6.5), drafter surfaces symbols that LOOK like targets for the slice's removal but are **semantically distinct** (e.g., generic in-memory `RuleRegistry` vs filesystem `FileAuthoringRegistry`).
- Blueprint §6 / §7 explicitly LOCK these symbols as unchanged.
- Post-impl verification confirms 0 diff in protected directories (e.g., `git diff <impl-base>..HEAD -- src/factgraph/core/rules/`).
- Future-slice hard locks prevent re-litigation.

**Slice 7C example**: `core/rules/ruleref_common.py`, `core/rules/rule_ir.py`, `core/rules/ruleref_substrate.py`, and generic `registry` parameters in `application/*_runtime.py` / `core/store/_evaluate.py` / SDK shell methods — all NOT filesystem-registry adapters, all preserved with 0 diff verified post-impl.

**When to use**: Any slice with **name-similar symbols spanning multiple semantic layers**. Common in subtractive removal slices where one class shares its name with a parent abstraction (e.g., `Registry` vs `FileAuthoringRegistry`).

**Anti-pattern (avoid)**: Letting impl phase decide what's "the same" based on symbol name — always require explicit pre-impl distinction in blueprint §6 / §7.

## Cross-slice contract preservation

Each new slice must verify it preserves all prior-slice contracts:

- Identity formulas locked by prior slices (e.g., `canonical_bytes_dbtx_v1`, `canonical_bytes_view_v1`) must not change without explicit revision.
- API surfaces locked by prior slices (e.g., `Database.commit_assertions`, `Database.create_view`) must not change without explicit revision.
- Prior-slice test suites must not regress (independent re-run mandate).
- Each slice's review section should include a "Cross-slice consistency" table mapping prior slice contracts → current verification.

## Rule 1 calibration: spot-check vs full re-read

- **Full re-read required** when:
  - First time touching a file in this session.
  - Adding new finding/cite at row-drafting time.
  - Preflight phase (re-read all blueprint-referenced shipped files).
  - Implementation phase (re-read scoped blueprint + preflight + key source per Rule 1).
- **Spot-check sufficient** when:
  - Cite was independently verified earlier in same session.
  - Verifying the most critical findings (don't re-verify everything every commit).
  - Independent verification of user-claimed test/grep results.

Use Rule 1 budget wisely. Full re-read every commit burns context. Spot-check + cross-check earlier-session reads conserves it.

## Memory consolidation timing

- **Never** auto-update memory mid-session.
- Triggers for batched memory update:
  - Major milestone (e.g., full Q-chain closed, N slices implemented+archived).
  - User explicit request.
- Single batched update after milestone records all accumulated state, with cross-refs to commits.
- Don't update memory per-commit or per-stage — too churny + creates stale state immediately.

## Communication style

- **Tables** for structured comparisons (PF coverage / Cross-slice contract / Severity distribution / Slice-stage comparison).
- **File:line precision** in all citations (never "around line ~200").
- **Concise verification reports**: state result first, then evidence.
- **Independent vs claimed** distinction: always say "independently verified" or "per user report".
- **Per-established-cadence** references: "per slice 1 precedent" / "类似 slice 2 模式".
- **Sacred-state always at session end**: total commits, branches, push state, sacred branches, dirty files preserved.

## 5-bucket severity (preflight finding classification)

When drafting preflight findings:

1. **Required amendment before scoped**: true blocker — blueprint section X cannot land as-is, must amend blueprint before moving to scoped.
2. **Recommended amendment before scoped**: substance polish — implementation will surface ambiguity if not fixed, but blueprint is not strictly blocked.
3. **Verified assumption**: confirms blueprint assumption against current shipped state (positive finding, no action).
4. **Scoped-detail item**: push to scoped-blueprint or implementation phase — implementation can decide concrete answer.
5. **Abandonment blocker**: stop the slice — design assumption is wrong, must revise upstream Q or audit.

Healthy distribution: 1-4 required, 1-2 recommended, 0-3 verified, 0-2 scoped-detail, 0 abandonment. If 0 required, preflight may be too light. If >5 required, blueprint may need re-drafting before preflight.

## Closure §10 records (Outcome / Deviations)

What to record:

- Landed modules + final line counts (helps future audit baseline).
- Per-PF alignment summary (how each preflight finding was satisfied).
- Carry-forward implementation choices (atomicity, API exposure, etc.) that may need future hardening.
- Acknowledged unrelated baseline test failures (so future implementer knows these existed pre-slice).
- Any deviations from scoped blueprint contract + justification.
- Archive intent (if slice will move to archive/ in separate commit).

What NOT to record:

- Implementation step-by-step narrative (commit message + diff carries that).
- Re-justification of design decisions (those live in Q-decision docs).
- Speculation about future slices (those live in synthesis or future Q decisions).

## Anti-patterns (DO NOT DO)

- ❌ Auto-advance to next phase without explicit "可以推进".
- ❌ Auto-fix unrelated test failures (record as carry-forward instead).
- ❌ Update memory mid-session (batch only).
- ❌ Skip preflight before scoped (validated to catch issues review misses).
- ❌ Batch multiple stage transitions into one commit.
- ❌ Trust user-claimed verification without independent re-run + grep.
- ❌ Modify sacred branches without explicit authorization.
- ❌ Add to scope during implementation ("while I'm in this file I'll also fix X").
- ❌ Soften design strict prohibitions to fit shipped reality (Rule 2).
- ❌ Over-broaden form-specific design constraints to global rules (Rule 2 bidirectionality).
- ❌ Copy line numbers from memory without re-reading source (Rule 1).
- ❌ Re-litigate closed Q decisions without explicit user revision request.

## Companion rules (currently in auto-memory)

The following rule files remain in Claude auto-memory and have not yet been promoted to canonical workflow docs:

- `feedback_preflight_code_audit_required.md` — preflight discipline for audit-before-design/blueprint phase.
- `feedback_audit_execution_discipline.md` — Rule 1 (re-read cites at row-drafting time) + Rule 2 bidirectional (don't soften, don't over-broaden).
- `feedback_push_master_gate.md` — never auto-push, push only at scoped-unit completion with single ask.
- `feedback_blueprint_workflow.md` — direct creation in active/, no plan mode.
- `feedback_milestone_branch_refs.md` — milestones are branch refs under `refs/heads/milestone/...`, not git tags.
- `feedback_smaller_batch_design_blueprints.md` — single-PR cadence for rule-touching blueprints.

This file is the integrating cadence over those rules — it tells the next agent how to combine them into the audit→Q→synthesis→per-slice rhythm that the 2026-05-20 session validated. Future slices may promote these into per-pillar AGENTS.md files; the promotion plan is captured in the workflow-governance-promotion slice's Q5 decision record.

## Quick start for next agent

If a new session continues with this workflow:

1. Read this file + `workflow/AGENTS.md` + relevant per-pillar AGENTS (e.g., `workflow/blueprints/AGENTS.md`).
2. Read the latest project-state checkpoint in `workflow/memory/` (e.g., `current.md` or the most recent topic checkpoint) and the latest session handoff in `workflow/memory/session_handoffs/`.
3. Check current branch + workspace state (`git status`, `git branch --show-current`, `git log -5 --oneline`).
4. Note unrelated dirty file set — preserve throughout session.
5. Wait for user direction — never auto-advance, never auto-push, never auto-update memory.

The pre-impl grep substage (Step 4.6.5) is now a formalized cadence step. Use it for any subtractive or migration slice going forward.
