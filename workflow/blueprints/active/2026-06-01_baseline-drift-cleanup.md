# Baseline Drift Cleanup Meta-Blueprint: 189 pre-existing failures across 27 test files

- Status: scoped
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

- **SS1**: `Rule(where=)` keyword TypeError — **44 error instances** across 6 active test files: `tests/application/protocol/test_rule_aggregate.py`, `tests/application/protocol/test_rule_expr_head_validation.py`, `tests/sdk/test_t5_why_not_quarantine.py`, `tests/test_db_attach_lifecycle.py`, `tests/test_sdk_find_partial_identity.py`, `tests/test_sdk_frozen_view_read_runtime_boundaries.py`. **Root cause**: Q-NAMING-E migration leftover — public application `Rule` constructor renamed `where=` kwarg → `when=`; tests still pass legacy `where=` kwarg. **[NARROWED Step 4.2 P2-1: constructor-type discrimination]** SS1 scope is restricted to **traceback-confirmed application `Rule(...)` constructor failures ONLY** (i.e., the public `factgraph.sdk.Rule` per Q-NAMING-E §4.6.2). Explicit carve-outs (NOT in SS1 scope; remain unchanged per Q-NAMING-E inherited):
  - **Legacy DSL Rule.where preserved** per Q-NAMING-E PF-R1 G4 Option D (legacy `sdk.dsl.rule.Rule.where` field at `sdk/dsl/rule.py:71` UNCHANGED — required by Q-PR1 sacred `pyreason/rule_ext.py:101`).
  - **Aggregate helpers `agg_count/sum/min/max/mean(*, where=[...])`** at `sdk/dsl/expr.py:329-349` PRESERVED per Q-NAMING-E PF-v7.
  - **Query.where / Query.where_ir** at `sdk/dsl/rule.py:242` PRESERVED per Q-NAMING-E N17 + B1 N17 + B2/F N18.
  - **Inference body `where`** if any legacy references exist (post-Q-NAMING-E should be `Inference.when`) — verify per traceback at Step 4.3 preflight 2.b.
  - **PyReason adapter test `where=` callsites** that wrap adapter input (different namespace) — verify per file at Step 4.3 preflight 2.b.
  - SS1 implementation: migrate only `Rule(where=[...])` callsites with **public application Rule** receiver — traceback line + test file name confirms which.

- **SS2**: `engine_options=` T5 rejection — **6 error instances** chain-blocked by SS5. **[REORDERED Step 4.2 P2-2 — move SS2 after SS5]** Fresh grep confirms `engine_options=` appears across MUCH BROADER active surface than initially documented: 11 test files (`test_sdk_diagnose.py`, `test_application_diagnose_protocol.py`, `test_problog_engine_eval.py`, `test_pyreason_engine_eval.py`, `test_pyreason_e2e.py`, `test_sdk_check.py`, `test_sdk_fact_overlay.py`, `test_sdk_why_not.py`, `test_pyreason_semantics_profile_migration.py`, `tests/sdk/test_rule_expr_evaluate.py`, `tests/application/protocol/test_evaluate_result_digests.py`) + 12+ src files (`core/store/runtime.py`, `adapters/pyreason/engine_eval.py`, 4 `sdk/shells/*.py`, `sdk/store.py`, `application/derivation_runtime.py`, multiple `sdk/docs/` + `adapters/docs/`). Most src refs are LEGITIMATE error-message strings ("use config= or engine-specific configuration") per Q-NAMING-F G4 — NOT migration targets. Only test fixtures that CONSTRUCT `evaluate(engine_options=...)` are SS2 scope. **Order change**: SS2 ordered AFTER SS5 because 6 errors all chain-blocked by SS5's `meta[confidence]` setup failure in `_make_sdk()`; running SS2 before SS5 produces 0 observable delta (errors still chain-blocked). Default lock: SS2 = "classification only until SS5 ships; then re-census + migrate residual engine_options= test fixtures (likely 0-2 remaining after SS5 unblocks setup)". **Root cause**: T5 migration leftover — `evaluate(engine_options=...)` rejected since T5; tests still pass `engine_options=`. Fix: migrate test fixtures to use `engine=` + `config=` per Q-NAMING-F G4 (only for residual cases after SS5).

- **SS3**: `ReadPolicy` import error — **24 error instances** all in `tests/test_sdk_read_policy.py` (single file). **[LOCKED Step 4.2 P2-3 — retired-surface handling, NOT new import path]** Shipped source confirms ReadPolicy was REMOVED, not migrated to new namespace: `src/factgraph/sdk/store.py:126` declares `_READPOLICY_REMOVED_MESSAGE = "ReadPolicy was removed. Use raw_kind / bound for uncertainty inputs."` Test file `tests/test_sdk_read_policy.py:1` describes itself as **"Phase 1 G1.1 red-baseline tests for the ReadPolicy migration blueprint"** with comment at line 86: `"All ReadPolicy imports are dynamic ... so file collects cleanly while ReadPolicy does not yet exist."` These are HISTORICAL TDD red-baseline tests for a migration design that ultimately went a different direction (ReadPolicy removed entirely, replaced by `raw_kind`/`bound` Uncertainty Phase 1 DSL). **Root cause**: pre-implementation TDD test file for an abandoned migration design path. **Fix LOCKED default**: retire/quarantine `tests/test_sdk_read_policy.py` (rename to `tests/_retired/test_sdk_read_policy.py` with archive header explaining context) OR rewrite to assert `ReadPolicy` removal (`assertNotIn("ReadPolicy", factgraph.sdk.__all__)` + `assertRaises(ImportError)` patterns). Step 4.3 preflight 2.c locks which approach. **Default expectation**: retire (cleanest; honors original "red-baseline" intent now that migration design diverged). NOT hunt for replacement import path.

- **SS4**: `SDKStore.ref/.read/.retract/.set/.get` AttributeError — **92 error instances** (66 .ref + 18 .read + 4 .retract + 2 .set + 2 .get) across multiple test files. **[LOCKED Step 4.2 P2-4 — namespaced migration default; restoration requires separate Red blueprint]** Shipped reality confirms namespaced surfaces are canonical post-Q-NAMING-C: `src/factgraph/sdk/docs/00_user_guide.en.md:60+` documents `fg.entities.ref(User, user_id=...)`, `fg.fields.set(User.name, ref, value)`, `fg.entities.get(User, ...)`; `src/factgraph/sdk/docs/04_api_surface.en.md:23+187+335+350+521` documents `fg.entities.ref`, `fg.entities.get`, `fg.entities.edit`, `fg.fields.set`, `fg.assertions.retract` as canonical entries; `fg.assertions.retract(...)` is "only public assertion-id mutation entry" per line 350. Q-NAMING-C archive `23389a2b` deleted 20 flat shells per documented design decision. **Root cause**: pre-existing SDK shape baseline — flat shells `SDKStore.ref/.read/.retract/.set/.get` deleted in Q-NAMING-C; tests still call legacy flat-shell form. **Fix LOCKED default**: migrate tests to namespaced managers:
  - `sdk.ref(...)` → `sdk.entities.ref(...)` (per user guide:60)
  - `sdk.set(...)` → `sdk.fields.set(...)` (per user guide:62)
  - `sdk.get(...)` → `sdk.entities.get(...)` (per user guide:66)
  - **`sdk.read.match(...)` → `sdk.entities.match(...)`** **[LOCKED Step 4.4 PF-r2]** per shipped docs `sdk/docs/04_api_surface.en.md:557` ("Use `fg.entities.where(...)` for simple snapshot reads and `fg.entities.match(...)` for match"). Note: `sdk.read.*` was a NAMESPACE (not method) per Q-NAMING-C archive `23389a2b` — its replacement is `sdk.entities.*` namespace, NOT a single method rename.
  - `sdk.retract(...)` → `sdk.assertions.retract(...)` (per api_surface:350+521)
- **Restoring flat shells `SDKStore.ref/.read/.retract/.set/.get` is OUT of SS4 scope** — would require separate Red blueprint per Q-NAMING-C precedent (reversing 20-shell deletion is a public-surface decision, not test cleanup). SS4 must NOT add `SDKStore.ref`/`.read`/etc. methods back.
- SS4 audit at Step 4.3 preflight 2.d: per-method confirm namespaced equivalent + verify all 27 test files' callsites can migrate cleanly without source change.

- **SS5**: `meta[confidence] was removed` — **68 error instances** across multiple test files. **Root cause**: Uncertainty Phase 1 (2026-05-11 implemented + pushed at `origin/master 8a11b3a5` per project_uncertainty_phase1_implemented.md) replaced `meta[confidence]` with `raw_kind` / `bound`; tests still pass `meta={"confidence": ...}`. Fix: fixture migration `meta={"confidence": X}` → `raw_kind=... + bound=...` per Uncertainty Phase 1 DSL.

- **SS6**: `_eval_eq_atom() / _eval_arith_atom() missing 1 required positional argument: 'atom'` — **24 error instances** (20 + 4). **[LOCKED Step 4.4 PF-r1 SOURCE TOUCH AUTHORIZED]** Step 4.3 preflight `f8dd647f` traceback origin grep confirms 11 callsites in **`src/factgraph/core/rules/frontier.py`** SOURCE file call helpers with wrong arity + 1 in `application/diagnose_runtime.py` + 1 in `test_t5_why_not_quarantine.py`. Helper signatures at `core/rules/where_eval.py:526` (`_eval_eq_atom(view_facts, envs, atom, *, ast_gate_on)`) + line 857 (`_eval_arith_atom(view_facts, envs, atom, *, ast_gate_on)`) confirm `atom: tuple[Any, ...]` is REQUIRED positional. **Root cause**: BUG is in shipped SOURCE (`frontier.py`), not test fixture — signature drift after `01bac07a blueprint(slice-1): rewrite attr-eq identity lowering` or `765eb10a feat(naming)` was not caught because tests already broken. **SS6 source touch authorization** (per §6 source touch policy + N7 layer authority): SS6 IS the first cleanup sub-slice to invoke source touch authorization clause; explicit audit log entry at source change + per-site rationale required at Step 4.7. Fix: locate per-callsite missing-`atom` site in `frontier.py` + `diagnose_runtime.py` + verify each callsite signature aligns with helper definition; preserve N7 layer authority (no cross-layer signature change).

- **SS7**: `NoneType.proof` AttributeError — **102 error instances** (largest single category). **[LOCKED Step 4.4 PF-R1 — chain hypothesis DISPROVEN; active investigation required]** Step 4.3 preflight `f8dd647f` independent grep verification revealed only **5 of 102 (~5%) NoneType.proof failures have meta[confidence] in immediate setup chain** — NOT the 70-100% initial blueprint hypothesis predicted. The 102 errors are concentrated in 4 SDK rule overlay test files: `test_sdk_rule_literal_replace.py` 15 + `test_sdk_rule_add_condition.py` 15 + `test_sdk_rule_disable.py` 14 + `test_sdk_proof_frame.py` 7 = 51, plus 51 in other files. These are INDEPENDENT test setup failures where `result.evidence_envelope` returns None for reasons NOT related to Uncertainty Phase 1 chain. **Root cause**: post-Q-NAMING-F migration of `engine_payload → proof` field rename; tests setup `result.evidence_envelope` returns None → `.proof` AttributeError. **Chain auto-resolve assumption DISCARDED** per PF-R1 LOCK. SS7 reframed as **direct active investigation** (NOT auto-deferred): SS7 needs root-cause audit of why `evidence_envelope` returns None in SDK rule overlay capability protocol tests, then per-site migration. SS7 reordered: still LAST in execution sequence (per Step 4.2 P2-FP1) so that recensus after SS6 establishes precise SS7 baseline before active investigation begins.

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

**[REVISED Step 4.4 PF-s1 — recensus-gated trajectory]** Per Step 4.3 preflight PF-R1 chain disproval, category counts have overlap/chain effects that violate linear subtraction. Replaced with **recensus-gated trajectory** — each SS ships then runs canonical census per §5.1; expected outcomes documented as direction (DROP / CLASSIFICATION-ONLY / RECENSUS-REQUIRED), not absolute numbers (except SS1/SS3 which have clear non-chained baselines):

| Order | SS | Estimated effort | Risk | Expected outcome |
|---|---|---|---|---|
| 1 | SS1 Rule(where=) — **application Rule constructor ONLY per P2-1** | Small (6 files fixture migration; carve-outs for legacy DSL / aggregate / Query / adapter tests) | Low | DIRECT DROP: 189 → ~145 (Rule(where=) failures cleanly independent) |
| 2 | SS3 ReadPolicy — **retire/quarantine per P2-3 LOCK** | Small (1 file rename/rewrite) | Low | DIRECT DROP: ~145 → ~121 (single test file cleanly independent) |
| 3 | SS4 SDKStore shape — **namespaced migration per P2-4 + P2-r2 LOCK** | Medium (multi-file; per-method namespaced mapping incl. `sdk.read.match → sdk.entities.match`) | Medium | RECENSUS REQUIRED post-SS4 — 92 SDKStore.* error instances may overlap with downstream chains (cannot assume linear -92); re-run canonical census to establish actual residual |
| 4 | SS5 meta[confidence] | Medium (DSL migration `meta[confidence]` → `raw_kind`/`bound`) | Medium | DIRECT meta[confidence] failures EXPECTED TO DROP (~68 direct hits); **SS7 chain auto-resolve DISPROVEN per PF-R1 — only ~5 of 102 NoneType.proof errors auto-resolve via SS5 chain**; recensus required to establish actual residual |
| 5 | SS2 engine_options= — **reordered after SS5 per P2-2** (chain-blocked) | Tiny (residual after SS5 likely 0-2 cases) | Low | CLASSIFICATION-ONLY until SS5 ships; then re-census + migrate residual (likely 0-2 cases) |
| 6 | SS6 _eval_*_atom missing 'atom' — **SOURCE TOUCH AUTHORIZED per PF-r1 LOCK** | Medium (`frontier.py` 11 callsites + `diagnose_runtime.py` 1 + 1 test file) | Medium (SOURCE change requires per-site rationale per §6) | DIRECT DROP: ~24 evaluator drift failures cleanly addressable via shipped-source signature alignment |
| 7 | SS7 NoneType.proof — **DIRECT active investigation per PF-R1 LOCK** | Medium-Large (102 errors; root-cause audit of `evidence_envelope = None` in SDK rule overlay capability protocol tests) | Medium | DIRECT INVESTIGATION: post-SS6 recensus establishes precise SS7 baseline; ~95 of 102 expected to remain (chain disproven); SS7 implementation requires audit-first per `test_sdk_rule_literal_replace/add_condition/disable/proof_frame` cluster |
| 8 | SS8 misc | Tiny (per-site) | Low | FINAL MISC CLEANUP per case-by-case |

**Census-gated discipline**: numerical predictions for SS4/SS5/SS7 are AVOIDED because chain effects + overlapping categories make linear arithmetic unreliable. Each SS ships → runs canonical `PYTHONPATH=src python -m pytest tests/ --tb=no -q --no-header 2>&1 | tail -5` (per §5.1) → records observed delta in audit log; cumulative state tracked in this meta's Event Log.

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

**[ADDED Step 4.2 P3-2 — canonical test runner + census command]**

Per-SS pre-impl + post-impl census must use the SAME canonical command for comparable deltas:

```bash
PYTHONPATH=src python -m pytest tests/ --tb=no -q --no-header 2>&1 | tail -5
```

Expected output format (matches Step 4.1 baseline at `fa030b06`):
```
<N> failed, <N> passed, <N> skipped, <N> subtests passed in <T>s
```

For per-SS targeted error category re-verification + delta isolation:

```bash
# Per-SS category-specific count
PYTHONPATH=src python -m pytest tests/ --tb=line --no-header 2>&1 | grep -E "Error\b" | sed 's/.*[A-Z][a-z]*Error/Error/' | sort | uniq -c | sort -rn | head -20
```

**Failure-log artifact convention**: each SS commit message includes the pre-impl + post-impl numeric delta (e.g., `189 → 145 (−44)`) in the commit footer; audit log Event Log row cites the same numbers with reference to running cumulative state per §5.3.

`PYTHONPATH=src` required because `factgraph` package not installed in pip-editable mode in this environment (per project_evidence_db_view_phase_c_abandoned.md baseline). Use of any other runner (e.g., `pytest tests/`, `uv run pytest`, `pip install -e .`) DEPRECATED for census purposes — variant runners produce non-comparable failure counts.

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
  - **[Step 4.4 PF-r1 SOURCE TOUCH AUTHORIZATION for SS6]**: SS6 explicitly authorized to modify `src/factgraph/core/rules/frontier.py` (11 callsites) + `src/factgraph/application/diagnose_runtime.py` (1 callsite) to align `_eval_eq_atom`/`_eval_arith_atom` callsites with helper signatures at `where_eval.py:526/857` (`atom: tuple[Any, ...]` required positional). SS6 implementation discipline: per-callsite explicit rationale at audit log; preserve N7 layer authority (no cross-layer signature change); no other source-touch beyond signature alignment.
  - When source touch IS required, must explicitly document at audit log + retain N7 layer authority
  - Alpha release; no historical user protection

## 7. Acceptance

- [x] SS1 Rule(where=) — shipped at Step 4.7 SS1; public application Rule fixtures migrated; observed census 189 → 168 (-21) with remaining cohort failures belonging to SS4 SDKStore shape
- [ ] SS2 engine_options= — classified after SS5; residual fixtures migrated if observable (per Step 4.2 P2-2 + Step 4.4 PF-s1 recensus-gated)
- [x] SS3 ReadPolicy import — retired/quarantined; observed census 168 → 139 (-29) with historical red-baseline file moved out of active tests
- [x] SS4 SDKStore shape — shipped at Step 4.7 SS4; tests migrated to namespaced managers (`fg.entities.ref/get/match/where`, `fg.fields.set/add`, `fg.assertions.retract`); observed census 139 → 94 (-45); flat-shell restoration explicitly OUT of scope (requires separate Red blueprint per Q-NAMING-C precedent)
- [ ] SS5 meta[confidence] — 68 errors fixed; tests migrated to Uncertainty Phase 1 DSL (raw_kind/bound)
- [ ] SS6 _eval_*_atom signature — 24 errors fixed; evaluator audit complete
- [ ] SS7 NoneType.proof — direct investigation completed; `evidence_envelope` None root cause fixed/migrated (per Step 4.4 PF-R1 LOCK chain disproven; ~95 of 102 expected to remain after SS5 — active investigation required, not auto-resolved)
- [ ] SS8 misc — ~17 errors fixed
- [ ] Cumulative: 189 → ~0 baseline failures in `tests/` cohort
- [ ] Q-PR1 sacred 5 paths 0-diff vs `4c472b50` preserved across all sub-slices
- [ ] Sacred master unchanged through cleanup
- [ ] Dirty baseline 8 entries preserved
- [ ] No push without explicit per-sub-slice authorization
- [ ] All AD/C/E/B1/B2/F inherited contracts preserved (N12-N24)
- [ ] Audit log Event Log records each SS ship with failure delta + commit hash

## 8. Implementation Plan

1. **Step 4.2 review (Codex)** ✓ COMPLETED at `b3882411` + `aaac284f`: 4 Required (P2-1/P2-2/P2-3/P2-4) + 2 Recommended (P3-1/P3-2) + P2-FP1 cleanup applied. Historical probe questions included (a) sub-slice ordering rationale, (b) SS4 audit-first approach for SDKStore shape decision, (c) **SS5 → SS7 chain propagation hypothesis (initially predicted ~70-100 SS7 errors auto-resolve after SS5; SUPERSEDED at Step 4.4 PF-R1 LOCK — chain disproven, only ~5 of 102 = 5% auto-resolve)**, (d) source touch policy in §6.
2. **Step 4.3 preflight (Claude)**: independent artifact branch `v0.2.0-baseline-drift-cleanup-preflight-2026-06-01`. Re-read all category-source citations at preflight-row drafting time per Rule 1. Build findings table. Mandatory preflight items:
   - 2.a Q-PR1 sacred verification (preserve discipline across all 8 SS)
   - 2.b Per-SS file enumeration (pin exact files per category)
   - 2.c SS3 ReadPolicy migration target (per memory `readpolicy-migration-2026-05-11`)
   - 2.d SS4 namespaced manager audit (which managers replace SDKStore.ref/.read/.retract/.set/.get)
   - 2.e SS5 Uncertainty Phase 1 DSL audit (raw_kind/bound API signature)
   - 2.f SS6 evaluator signature audit (where is `atom` arg added)
   - 2.g SS7 chain hypothesis verification — **COMPLETED at Step 4.3 preflight `f8dd647f`**: PF-R1 LOCK disproved chain (5 of 102 = 5% chain-blocked, not 70-100%); SS7 active investigation locked at Step 4.4 PF-R1.
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

**Step 4.4 PF locks** (per Step 4.3 preflight `f8dd647f`):

- **PF-R1 LOCK SS7 chain hypothesis DISPROVEN**: only 5 of 102 NoneType.proof failures (~5%) chain-blocked by SS5; SS7 reframed as direct active investigation (NOT auto-deferred). 102 errors concentrated in 4 SDK rule overlay test files + 51 others — independent setup failures where `result.evidence_envelope` returns None for reasons unrelated to Uncertainty Phase 1 chain. Blueprint §2 SS7 + §4.2 trajectory + §10.4-style alignment updated.
- **PF-r1 LOCK SS6 SOURCE TOUCH AUTHORIZED**: `frontier.py` 11 callsites + `diagnose_runtime.py` 1 callsite missing required `atom` arg per `where_eval.py:526/857` helper signatures. SS6 IS the first cleanup sub-slice to invoke §6 source touch authorization clause; per-callsite rationale required at audit log; N7 layer authority preserved.
- **PF-r2 LOCK SS4 sdk.read.match → sdk.entities.match**: per shipped `api_surface.en.md:557`. Complete SS4 namespaced migration map.
- **PF-s1 recensus-gated trajectory** (replacing linear subtraction): §4.2 trajectory revised to direction-based outcomes (DIRECT DROP / CLASSIFICATION-ONLY / RECENSUS REQUIRED / DIRECT INVESTIGATION / FINAL MISC); numerical predictions for SS4/SS5/SS7 avoided because chain effects + overlapping categories violate linear arithmetic.

**Step 4.7 implementation discipline carry-forward** (per Step 4.3 preflight PF-s1 at `f8dd647f`):

- **Per-SS canonical census** (per §5.1): `PYTHONPATH=src python -m pytest tests/ --tb=no -q --no-header 2>&1 | tail -5` ran post-impl per SS; recorded observed delta in audit log Event Log; cumulative state tracked in this meta's audit row sequence.
- **SS6 source touch site list** (per PF-r1 LOCK): per-callsite rationale required at audit log when changing `frontier.py` + `diagnose_runtime.py`; verify each callsite signature aligns with helper definition; preserve N7 layer authority (no cross-layer signature change).
- **SS7 active investigation requirement** (per PF-R1 LOCK): post-SS6 recensus establishes precise SS7 baseline; SS7 implementation requires audit-first per `test_sdk_rule_literal_replace/add_condition/disable/proof_frame` cluster (~51 of 102 hits); ~95 of 102 expected to remain after SS5 (chain disproven); SS7 root-cause audit must investigate why `result.evidence_envelope` returns None in SDK rule overlay capability protocol tests.
- **SS4 namespaced migration complete map**: `sdk.ref→sdk.entities.ref`, `sdk.get→sdk.entities.get`, `sdk.set→sdk.fields.set`, `sdk.read.match→sdk.entities.match`, `sdk.retract→sdk.assertions.retract`.
- **SS-by-SS cadence**: each SS = single commit + canonical census + audit log row + sacred verification ritual + per-SS push authorization. NO bundled SS commits.

(Step 4.8 closure outcome / deviations to be filled at implementation closure after all 8 SS ship + cumulative baseline verified.)
