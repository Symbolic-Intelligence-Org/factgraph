# Baseline Drift Cleanup Meta-Blueprint: 189 pre-existing failures across 27 test files

- Status: draft
- Created: 2026-06-01
- Last Updated: 2026-06-01
- Related Modules:
  - `tests/` (test fixture migration leftover + import baseline)
  - `src/factgraph/sdk/` (SDK shape baseline — `SDKStore.ref/.read/.retract/.set/.get`)
  - `src/factgraph/core/derivation/` (evaluator signature drift — `_eval_eq_atom/_eval_arith_atom`)
  - `src/factgraph/core/evidence/write_protocol.py` (Uncertainty Phase 1 `meta[confidence]` removal)
- Related Docs:
  - [`workflow/blueprints/archive/2026-05-31_q-naming-f.md`](../archive/2026-05-31_q-naming-f.md) §10.6 — B2/F baseline failures classification + carry-forward
  - [`workflow/blueprints/archive/2026-05-31_q-naming-b2.md`](../archive/2026-05-31_q-naming-b2.md) §10.6 — B2 189-failure baseline source
  - [`workflow/CADENCE.md`](../../CADENCE.md) — 9-stage Audit-to-Archive Cadence (lightweight variant for cleanup sub-slices)
  - [`workflow/AGENTS.md`](../../AGENTS.md) — workflow governance
- Audit Log:
  - [2026-06-01_baseline-drift-cleanup.audit.md](./2026-06-01_baseline-drift-cleanup.audit.md)

## 1. Problem

Q-NAMING decision 6-phase routemap (AD/C/E/B1/B2/F) completed and pushed to origin 2026-06-01. Across multiple Red slice Step 4.7 independent reviews (E + B2 + F), the **189 pre-existing baseline failures** in `tests/` cohort repeatedly forced expensive failure-categorization analysis to distinguish NEW regressions from inherited baseline. This pattern is documented at Q-NAMING-B2 §10.6 (189 failures) + Q-NAMING-F Step 4.7 review (verified unchanged).

**Goal**: systematically reduce the 189 baseline failures to ~0 BEFORE entering v0.2.0-rc release prep, so that future Red slice reviews (if any) and release gates are clean.

**Strategy** (per user 2026-06-01 直接 directive): meta-blueprint + sub-slice sequencing per方案 C (quick wins first) + 方案 A (single meta record).

**Why meta-blueprint instead of one-off cleanup**:
- 8 sub-slice categories with distinct root causes (fixture migration vs API contract vs DSL transition vs evaluator drift)
- Per-sub-slice ship + independent verification + failure delta census (avoid "new vs baseline" review ambiguity per CADENCE Rule 1)
- Lightweight cadence per sub-slice (cleanup is not Red slice — does not require full 9-stage every time)
- Single audit log records cumulative progress across all sub-slices

## 2. Goals

**Per fresh failure census 2026-06-01 at F archive HEAD `10b10981`** (full `tests/` cohort: 189 failed / 2294 passed / 32 skipped / 1037 subtests passed):

**Sub-slice priority (quick wins first per 方案 C)**:

- **SS1**: `Rule(where=)` keyword TypeError — **44 error instances** across 6 active test files: `tests/application/protocol/test_rule_aggregate.py`, `tests/application/protocol/test_rule_expr_head_validation.py`, `tests/sdk/test_t5_why_not_quarantine.py`, `tests/test_db_attach_lifecycle.py`, `tests/test_sdk_find_partial_identity.py`, `tests/test_sdk_frozen_view_read_runtime_boundaries.py`. **Root cause**: Q-NAMING-E migration leftover — Rule class renamed `where` field → `when` field; tests still pass legacy `where=` kwarg. Fix: fixture migration `Rule(where=[...])` → `Rule(when=[...])` per Q-NAMING-E + B1 fixture migration precedent.

- **SS2**: `engine_options=` T5 rejection — **6 error instances** in `tests/test_pyreason_e2e.py` (chain-blocked by SS5 setup but error msg per F G4 says "use config="). **Root cause**: T5 migration leftover — `evaluate(engine_options=...)` rejected since T5; tests still pass `engine_options=`. Fix: migrate test fixtures to use `engine=` + `config=` per Q-NAMING-F G4. **Note**: 6 errors all chain-blocked by SS5 (meta[confidence]) — may auto-resolve after SS5.

- **SS3**: `ReadPolicy` import error — **24 error instances** all in `tests/test_sdk_read_policy.py` (single file). **Root cause**: pre-existing import baseline — `ReadPolicy` no longer exported from `factgraph.sdk.__init__`. Fix: investigate per project_readpolicy_migration_implemented.md (ReadPolicy/policy= migration implemented 2026-05-11 @ origin/master `b53e9bd1` + retired flat-shell access). Likely test file needs migration to new import path OR test file marked deprecated.

- **SS4**: `SDKStore.ref/.read/.retract/.set/.get` AttributeError — **88+ error instances** (66 .ref + 18 .read + 4 .retract + 2 .set + 2 .get) across multiple test files. **Root cause**: pre-existing SDK shape baseline — flat shells were removed in Q-NAMING-C archive `23389a2b` (20 flat shells deleted); tests still call `sdk.ref(...)` / `sdk.read(...)` / etc. Fix: investigate per Q-NAMING-C precedent — should the tests be:
  - (a) migrated to use namespaced manager methods (e.g., `sdk.facts.read(...)`)?
  - (b) deleted as obsolete (Q-NAMING-C N16 documented commit_assertions preservation; what's the equivalent decision for these methods)?
  - SS4 starts with audit grep to discover the namespaced equivalent for each method before migration.

- **SS5**: `meta[confidence] was removed` — **68 error instances** across multiple test files. **Root cause**: Uncertainty Phase 1 (2026-05-11 implemented + pushed at `origin/master 8a11b3a5` per project_uncertainty_phase1_implemented.md) replaced `meta[confidence]` with `raw_kind` / `bound`; tests still pass `meta={"confidence": ...}`. Fix: fixture migration `meta={"confidence": X}` → `raw_kind=... + bound=...` per Uncertainty Phase 1 DSL.

- **SS6**: `_eval_eq_atom() / _eval_arith_atom() missing 1 required positional argument: 'atom'` — **24 error instances** (20 + 4). **Root cause**: core/derivation evaluator signature drift — internal `_eval_*` helpers gained required `atom` parameter; some callsites still call legacy 1-arg form. Fix: locate evaluator definition + audit per N7 layer authority — is the signature change in shipped code consistent with the rest of the codebase, or is it itself a baseline drift bug?

- **SS7**: `NoneType.proof` AttributeError — **102 error instances** (largest single category). **Root cause**: post-Q-NAMING-F migration of `engine_payload → proof` field rename; tests setup `result.evidence_envelope` returns None → `.proof` AttributeError. **Investigation hypothesis**: 102 errors likely chain-blocked by upstream SS5 (meta[confidence] in `_make_sdk()` setup) — `_make_sdk()` fails at `set_field(meta={"confidence":...})` → test setup incomplete → `evidence_envelope` is None → `.proof` access fails. Expected behavior: **after SS5 ships, SS7 should drop dramatically** (perhaps to <30 errors). Defer SS7 to last position to measure auto-resolve effect.

- **SS8**: Miscellaneous (~17 error instances): 4 `0 != 1`, 4 `'failed' != 'passed'`, 2×2 `Tuples differ`, 2 sha256 mismatch, 2 idref_v1 mismatch, 2 `EvaluateRow.support_kind`. **Root cause**: per-site investigation. Likely individual fixture or assertion drift cases.

**Cross-cutting per CADENCE invariants**:

- **G_ALL**: each sub-slice ships independently with mini-cadence (Step 4.1 sub-blueprint + Step 4.7 implement + Step 4.7 review + Step 4.8 closure recorded in this meta-blueprint's audit log).
- **G_NET**: after each sub-slice ship, run full `tests/` cohort census + record delta (e.g., "SS1 shipped → 189 → 145 failures"); meta-blueprint audit log tracks running total.
- **G_Q-PR1**: Q-PR1 sacred 5 paths 0-diff vs `4c472b50` preserved across all sub-slices.
- **G_master**: sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- **G_dirty**: dirty baseline 8 entries preserved.
- **G_AD/C/E/B1/B2/F**: all Q-NAMING inherited contracts preserved (no re-litigation).

## 3. Non-goals

- N1: Q-NAMING decision re-litigation (all 6 phases archived; SS1-SS8 inherit AD/C/E/B1/B2/F contracts).
- N2: Sacred Q-PR1 5-path modification.
- N3: Sacred master rewrite.
- N4: Dirty baseline cleanup (separate decision; per `feedback_push_master_gate` + dirty baseline §4.8.8 invariant).
- N5: New feature work mixed into cleanup commits (cleanup-only, no feature additions per sub-slice).
- N6: SS Reordering without user authorization (sequence locked per 方案 C quick wins first).
- N7: Push without explicit user authorization per sub-slice.
- N8: Auto-merge / auto-archive without per-sub-slice review.
- N9: Sub-slice scope creep — each SS strictly bounded by its category enumeration; cross-category dependencies surface as separate findings.

## 4. Current Context

### §4.1 Fresh failure census (2026-06-01 at F archive HEAD `10b10981`)

Full `tests/` cohort: **189 failed / 2294 passed / 32 skipped / 1037 subtests passed**

Error category breakdown (per `tests/` cohort with traceback):

| # | Error pattern | Count | SS |
|---|---|---|---|
| 1 | `'NoneType' object has no attribute 'proof'` | 102 | SS7 (chain-blocked by SS5) |
| 2 | `meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.` | 68 | SS5 |
| 3 | `'SDKStore' object has no attribute 'ref'. Did you mean: '_ref'?` | 66 | SS4 |
| 4 | `Rule.__init__() got an unexpected keyword argument 'where'` | 44 | SS1 |
| 5 | `cannot import name 'ReadPolicy' from 'factgraph.sdk'` | 24 | SS3 |
| 6 | `_eval_eq_atom() missing 1 required positional argument: 'atom'` | 20 | SS6 |
| 7 | `'SDKStore' object has no attribute 'read'` | 18 | SS4 |
| 8 | `evaluate() does not accept engine_options= in T5; use config= or engine-specific configuration` | 6 | SS2 |
| 9 | `_eval_arith_atom() missing 1 required positional argument: 'atom'` | 4 | SS6 |
| 10 | `0 != 1` | 4 | SS8 |
| 11 | `'failed' != 'passed'` | 4 | SS8 (chained from SS5) |
| 12 | `'SDKStore' object has no attribute 'retract'` | 4 | SS4 |
| 13 | `Tuples differ: () != ({...})` | 2 | SS8 |
| 14 | `Tuples differ: () != (...)` | 2 | SS8 |
| 15 | `'sha256:...' != 'sha256:...'` | 2 | SS8 |
| 16 | `'idref_v1:Person:...' != 'idref_v1:Person:...'` | 2 | SS8 |
| 17 | `'SDKStore' object has no attribute 'set'` | 2 | SS4 |
| 18 | `'SDKStore' object has no attribute 'get'` | 2 | SS4 |
| 19 | `'EvaluateRow' object has no attribute 'support_kind'` | 2 | SS8 |

Total error instances: ~378 (errors > failures because chain-triggered failures show multiple error categorizations in traceback)
Total unique failing test files: **27**

### §4.2 Sub-slice sequence (per 方案 C quick wins first, locked)

| Order | SS | Estimated effort | Risk | Expected baseline after |
|---|---|---|---|---|
| 1 | SS1 Rule(where=) | Small (6 files fixture migration) | Low | 189 → ~145 |
| 2 | SS2 engine_options= | Tiny (1 file?) | Low | ~145 → ~139 (or auto-resolved by SS5) |
| 3 | SS3 ReadPolicy | Small (1 file) | Low (per memory: ReadPolicy migration 2026-05-11) | ~139 → ~115 |
| 4 | SS4 SDKStore shape | Medium (multi-file; needs API audit) | Medium | ~115 → ~25 |
| 5 | SS5 meta[confidence] | Medium (DSL migration; unblocks SS7) | Medium | ~25 → ~25 (-68 direct, but unblocks ~70-100 SS7 errors) |
| 6 | SS6 _eval_*_atom missing 'atom' | Medium (evaluator audit) | Medium | ~25 → ~1 |
| 7 | SS7 NoneType.proof | Auto-deferred; measure after SS5 | Low if upstream fixed | ~1 → ~0 |
| 8 | SS8 misc | Tiny (per-site) | Low | ~0 |

**Target**: 189 → ~0 baseline failures after all 8 sub-slices.

### §4.3 Current branch + sacred state

- Branch: `v0.2.0-blueprint-baseline-drift-cleanup-2026-06-01` (forked from F archive HEAD `10b10981`)
- Sacred master: `562c74195df43e933bed92a3ff25de94dd8ce666`
- Q-PR1 5-path 0-diff vs `4c472b50` preserved
- Dirty baseline 8 entries preserved
- Not pushed

## 5. Proposed Shape

### §5.1 Sub-slice mini-cadence (lightweight CADENCE variant for cleanup)

Each sub-slice ships independently using:

1. **Pre-impl census**: re-run failing tests for this SS only; verify count matches §4.1 baseline
2. **Identify root cause**: locate source of mismatch (test fixture vs SDK API vs DSL transition)
3. **Migrate**: minimum fixture migration to fix the SS category; NO scope creep into other SS
4. **Post-impl census**: re-run full `tests/` cohort; verify failure count drops by expected amount
5. **Audit log update**: append `SS<N> shipped | <N> failures fixed | baseline: 189 → X` row + commit hash + delta
6. **Commit**: single `cleanup(baseline-drift): SS<N> <description>` commit on this branch
7. **Per-commit ritual**: Q-PR1 0-diff + sacred master + dirty baseline checks
8. **Push**: only at explicit user authorization per sub-slice (not bundled)

Skip full 9-stage CADENCE per sub-slice because:
- No new architecture decisions (cleanup-only)
- No cross-cutting design (each SS bounded by enumerated category)
- No Red-risk classification (per-SS risk is Low to Medium)
- Single audit log (this meta) tracks cumulative state

Apply full CADENCE if any sub-slice surfaces:
- Cross-Q-PR1 sacred touch (escalate to dedicated Red blueprint)
- N12-N24 inherited contract violation
- New API decision needed

### §5.2 Sub-slice scope discipline

Each SS strictly bounded by:
- Error category from §4.1 census (single category only — no merging)
- Test file enumeration from pre-impl census (per-SS)
- No SDK / core code change unless required to unblock the test fixture (and even then, only with explicit per-site rationale)

### §5.3 Failure delta tracking convention

Audit log Event Log records each SS ship with:
- `Date | Stage | Event | Notes` row including:
  - Pre-SS failure count
  - Files migrated
  - Post-SS failure count
  - Delta (e.g., `189 → 145 (-44)`)

### §5.4 Sacred invariant verification per SS commit

Per Q-NAMING precedent verification ritual:
- `git rev-parse master` must equal `562c74195df43e933bed92a3ff25de94dd8ce666`
- `git diff --stat 4c472b50 HEAD -- <Q-PR1 paths>` must be empty
- `git status --short` must show 8 dirty baseline entries
- `git diff --check` must be clean
- No `release/0.1.x` / `v0.1-oss-prep` touched

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - Q-PR1 sacred 5 paths: 0-diff vs `4c472b50` after every commit
  - Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` — never modified
  - Dirty baseline preserved
  - Q-NAMING inherited contracts (N12-N24 from B2/F) — no re-litigation
  - Per-sub-slice scope discipline (no category merging)
  - Per-sub-slice user push authorization
- **明确不做的内容**:
  - N1-N9 above
  - Feature additions
  - SDK API contract changes (unless explicitly required to unblock test fixture)
  - Multi-category bundled commits
- **兼容性约束**:
  - Cleanup commits do NOT touch shipped source unless required to unblock test fixture
  - When source touch IS required, must explicitly document at audit log + retain N7 layer authority
  - Alpha release; no historical user protection

## 7. Acceptance

- [ ] SS1 Rule(where=) — 44 errors fixed; 6 test files migrated
- [ ] SS2 engine_options= — 6 errors fixed (or auto-resolved by SS5)
- [ ] SS3 ReadPolicy import — 24 errors fixed
- [ ] SS4 SDKStore shape — 88+ errors fixed; tests migrated to namespaced managers OR deleted as obsolete
- [ ] SS5 meta[confidence] — 68 errors fixed; tests migrated to Uncertainty Phase 1 DSL (raw_kind/bound)
- [ ] SS6 _eval_*_atom signature — 24 errors fixed; evaluator audit complete
- [ ] SS7 NoneType.proof — ~102 errors fixed (mostly via upstream SS5 propagation)
- [ ] SS8 misc — ~17 errors fixed
- [ ] Cumulative: 189 → ~0 baseline failures in `tests/` cohort
- [ ] Q-PR1 sacred 5 paths 0-diff vs `4c472b50` preserved across all sub-slices
- [ ] Sacred master unchanged through cleanup
- [ ] Dirty baseline 8 entries preserved
- [ ] No push without explicit per-sub-slice authorization
- [ ] All AD/C/E/B1/B2/F inherited contracts preserved (N12-N24)
- [ ] Audit log Event Log records each SS ship with failure delta + commit hash

## 8. Implementation Plan

1. **Step 4.2 review (Codex)**: surface 2-4 tightenings — particularly probe: (a) sub-slice ordering rationale (quick wins justification per category), (b) SS4 audit-first approach for SDKStore shape decision, (c) SS5 → SS7 chain propagation hypothesis (expected ~70-100 SS7 errors auto-resolve after SS5), (d) source touch policy in §6 (when is shipped source change required to unblock test fixture).
2. **Step 4.3 preflight (Claude)**: independent artifact branch `v0.2.0-baseline-drift-cleanup-preflight-2026-06-01`. Re-read all category-source citations at preflight-row drafting time per Rule 1. Build findings table. Mandatory preflight items:
   - 2.a Q-PR1 sacred verification (preserve discipline across all 8 SS)
   - 2.b Per-SS file enumeration (pin exact files per category)
   - 2.c SS3 ReadPolicy migration target (per memory `readpolicy-migration-2026-05-11`)
   - 2.d SS4 namespaced manager audit (which managers replace SDKStore.ref/.read/.retract/.set/.get)
   - 2.e SS5 Uncertainty Phase 1 DSL audit (raw_kind/bound API signature)
   - 2.f SS6 evaluator signature audit (where is `atom` arg added)
   - 2.g SS7 chain hypothesis verification (run subset after SS5 simulation)
   - 2.h AD/C/E/B1/B2/F inherited contract preservation
3. **Step 4.4 amendment**: apply Required + Recommended PFs.
4. **Step 4.5 self-check (lightweight)**: PF coverage verification, no commit.
5. **Step 4.6 scoped anchor**: `Status: draft` → `Status: scoped`.
6. **Step 4.7 implementation (Codex 承接)** on branch `v0.2.0-impl-baseline-drift-cleanup-2026-06-01`. Per sub-slice mini-cadence per §5.1. Each SS = single commit + cohort census + audit log row + sacred verification.
7. **Step 4.7 review (Claude)**: per-sub-slice independent test re-run + cumulative cohort census + verify expected delta per §4.2.
8. **Step 4.8 closure**: `Status: scoped` → `Status: implemented` only after all 8 SS shipped + cumulative baseline → ~0 verified.
9. **Step 4.9 archive**: `git mv` blueprint + audit log pair from `active/` to `archive/` + `INVENTORY.md` entry.

## 9. Docs To Update

- This meta-blueprint's audit log (cumulative SS tracking)
- Likely no module docs change (cleanup is test/fixture-only by §6 + §5.2)
- If SS4 (SDKStore shape) requires source change, update affected `src/factgraph/sdk/docs/` per CADENCE Stage 4.8

## 10. Outcome / Deviations

(To be filled at Step 4.8 closure after all 8 SS ship.)
