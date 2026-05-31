# Baseline Drift Cleanup Meta-Blueprint Audit: 189 pre-existing failures across 27 test files

- Blueprint: [2026-06-01_baseline-drift-cleanup.md](./2026-06-01_baseline-drift-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-01 | draft | Meta-blueprint created + fresh failure census | Post Q-NAMING 6-phase routemap completion (AD/C/E/B1/B2/F all archived + pushed origin), launching baseline drift cleanup cycle per user 2026-06-01 directive (方案 C quick wins + 方案 A meta-blueprint framework). Branch `v0.2.0-blueprint-baseline-drift-cleanup-2026-06-01` forked from Q-NAMING-F archive HEAD `10b10981` (inherits AD + C + E + B1 + B2 + F complete lifecycles + N1-N24 invariants from F). Sacred Q-PR1 5-path 0-diff preserved at draft commit; sacred master `562c74195df4...` unchanged; dirty baseline (4 M + 2 D + 2 untracked) preserved. **Fresh `tests/` cohort census 2026-06-01**: 189 failed / 2294 passed / 32 skipped / 1037 subtests passed. Error category breakdown (per traceback grep): 102 `NoneType.proof` (SS7, chain-blocked by SS5), 68 `meta[confidence] removed` (SS5), 66 `SDKStore.ref` + 18 `.read` + 4 `.retract` + 2 `.set` + 2 `.get` = 92 SDKStore shape (SS4), 44 `Rule.where` TypeError (SS1), 24 `ReadPolicy` import (SS3), 20 `_eval_eq_atom` + 4 `_eval_arith_atom` = 24 evaluator drift (SS6), 6 `engine_options=` T5 (SS2), 4 `0 != 1` + 4 `'failed' != 'passed'` + 2 sha256 + 2 idref_v1 + 2×2 Tuples + 2 `EvaluateRow.support_kind` = ~17 misc (SS8). Total error instances ~378 across 189 distinct failures across 27 unique failing test files. Sub-slice sequence locked per 方案 C quick wins first: SS1 (44 ✓ small) → SS2 (6 ✓ tiny) → SS3 (24 ✓ small) → SS4 (92 medium, audit-first) → SS5 (68 medium, unblocks SS7) → SS6 (24 medium) → SS7 (102 → ~0 expected via upstream propagation) → SS8 (~17 individual cases). Target: 189 → ~0 baseline failures. Lightweight per-SS mini-cadence per §5.1 (no full 9-stage CADENCE per SS unless surfacing Red-risk findings); single audit log tracks cumulative state. |
| 2026-06-01 | draft (amended) | Step 4.2 review tightening | Codex Step 4.2 review surfaced 4 Required + 2 Recommended findings, all shipped-code-grounded via Rule 1 re-reads; all 6 applied in this single doc-only amend commit. (P2-1) SS1 Rule(where=) scope needs constructor-type discrimination — fresh grep confirms `where=` has multiple legitimate buckets per Q-NAMING-E inherited: aggregate helpers `agg_count/sum/min/max/mean(*, where=...)` at `sdk/dsl/expr.py:329-349` + Query.where at `sdk/dsl/rule.py:242` (N17 preserved) + legacy DSL Rule.where preserved per Q-NAMING-E PF-R1 G4 Option D + PyReason adapter test wrappers (different namespace). SS1 narrowed to "traceback-confirmed application `Rule(...)` constructor failures ONLY" (public `factgraph.sdk.Rule` per Q-NAMING-E §4.6.2) with explicit carve-outs for legacy DSL / aggregate / Query / adapter tests. Step 4.3 preflight 2.b verifies per-file callsite traceback. (P2-2) SS2 ordering + file enumeration unstable — fresh grep confirms `engine_options=` appears in 11 test files + 12+ src files (mostly legitimate error-message strings per Q-NAMING-F G4, NOT migration targets) — initial "1 file" estimate wrong. Plus SS2 chain-blocked by SS5 but ordered BEFORE SS5 in initial draft. Reordered: SS2 now AFTER SS5 in sequence table per P2-2; SS2 = "classification only until SS5 ships; then re-census + migrate residual engine_options= test fixtures (likely 0-2 remaining)". Default lock: 0 expected delta until SS5 unblocks chain. (P2-3) SS3 ReadPolicy target should default to retired-surface handling — shipped source confirms `_READPOLICY_REMOVED_MESSAGE = "ReadPolicy was removed..."` at `sdk/store.py:126`; test file `tests/test_sdk_read_policy.py` is described as "Phase 1 G1.1 red-baseline tests for the ReadPolicy migration blueprint" with comment "All ReadPolicy imports are dynamic ... so file collects cleanly while ReadPolicy does not yet exist" — pre-implementation TDD tests for migration design that ultimately diverged. LOCKED default: retire/quarantine `tests/test_sdk_read_policy.py` (rename to `_retired/` with archive header) OR rewrite to assert `ReadPolicy` removal (`assertNotIn` + `assertRaises(ImportError)`). NOT hunt for replacement import. Step 4.3 preflight 2.c locks final approach. (P2-4) SS4 must prohibit restoring flat SDKStore shells by default — shipped docs confirm namespaced canonical surfaces per Q-NAMING-C: `fg.entities.ref/get`, `fg.fields.set`, `fg.assertions.retract` at `sdk/docs/00_user_guide.en.md:60+` + `sdk/docs/04_api_surface.en.md:23+187+335+350+521` ("only public assertion-id mutation entry"). Q-NAMING-C archive `23389a2b` deleted 20 flat shells per design. LOCKED default: migrate tests to namespaced managers (sdk.ref→sdk.entities.ref, sdk.set→sdk.fields.set, sdk.get→sdk.entities.get, sdk.retract→sdk.assertions.retract, sdk.read→audit-required at preflight 2.d). **Restoring flat shells `SDKStore.ref/.read/.retract/.set/.get` is OUT of SS4 scope — would require separate Red blueprint per Q-NAMING-C precedent**. (P3-1) SS4 count internally inconsistent — line 45 + 210 said "88+" but listed counts 66+18+4+2+2=92. Corrected to "92 observed error instances" everywhere. (P3-2) Define canonical test runner/census command — added explicit `PYTHONPATH=src python -m pytest tests/ --tb=no -q --no-header 2>&1 \| tail -5` as canonical census command + expected output format + per-SS commit footer convention citing pre→post delta. Other runners (uv/pip-editable) DEPRECATED for census purposes. Also updated §4.2 sub-slice sequence table to reflect new SS1→SS3→SS4→SS5→SS2→SS6→SS7→SS8 order. Sacred Q-PR1 0-diff preserved through amend; master unchanged; dirty baseline preserved. |

## Decision Notes

### 2026-06-01 — Initial scope freeze rationale

- **Cleanup vs release prep priority**: per user 2026-06-01 direct directive, baseline drift cleanup precedes v0.2.0-rc release prep because 189 pre-existing failures repeatedly forced expensive failure-categorization analysis during Q-NAMING-E + B2 + F Step 4.7 Red slice reviews. Cleaning these now means future release gates and any subsequent slice reviews start from a clean baseline.

- **方案 C + 方案 A locked**: quick wins first ordering + meta-blueprint with sub-slice tracking. Rationale **[REVISED Step 4.2 P2-FP1 — sequence reorder per amend]**:
  - **Early quick wins = SS1 + SS3 (44 + 24 = 68 errors)** are small + well-defined fixture migrations → fast baseline drop establishes momentum. SS1 = application Rule constructor only (carve-outs locked per P2-1); SS3 = retire/quarantine red-baseline ReadPolicy test file (locked per P2-3).
  - **SS4 (92 errors) ordered after SS3 but before SS5** as audit-first medium slice — namespaced migration to `fg.entities.ref/get`, `fg.fields.set`, `fg.assertions.retract` per Q-NAMING-C documented canonical surfaces (locked per P2-4). SS4 in this position clears SDK shape noise that otherwise compounds downstream errors during SS5/SS6 reviews.
  - **SS5 (68 errors) ordered after SS4** — Uncertainty Phase 1 DSL migration (`meta[confidence]` → `raw_kind`/`bound`). Unblocks SS7 chain.
  - **SS2 (6 errors) ordered AFTER SS5 per P2-2** — chain-blocked by SS5's `meta[confidence]` setup failure. SS2 = classification-only until SS5 ships; expected 0 delta until chain unblocks. Likely 0-2 residual fixtures to migrate.
  - **SS6 (24 errors) follows SS2** — evaluator signature drift audit (`_eval_eq_atom/_eval_arith_atom` missing 'atom').
  - SS7 (NoneType.proof 102 errors) deferred to LAST because hypothesis predicts upstream SS5 (meta[confidence]) will unblock most of them via chain propagation (test setup at `_make_sdk()` calls `set_field(meta={"confidence":...})` which fails → `evidence_envelope` returns None → `.proof` access fails).
  - SS8 misc deferred to LAST because likely individual case-by-case investigation.
  - Meta-blueprint avoids one giant cleanup commit; tracks cumulative progress; allows per-SS independent review.

- **Lightweight mini-cadence per SS**: cleanup is not Red slice — does not require full 9-stage CADENCE per SS. Per §5.1:
  - Each SS = pre-impl census + root cause + migration + post-impl census + audit log + single commit + per-commit ritual + push (with explicit per-SS authorization)
  - Skip preflight branches per SS (not deep architecture)
  - Skip Decision Notes per SS (cumulative tracking in this single meta audit)
  - Apply full CADENCE only if SS surfaces Red-risk findings (cross-Q-PR1 touch or N12-N24 inherited contract violation)

- **Sub-slice scope discipline**: each SS strictly bounded by error category + test file enumeration. No category merging. No scope creep. Source touch (SDK / core) only when required to unblock test fixture + explicit per-site rationale + retain N7 layer authority.

- **Q-PR1 sacred invariant**: 0-diff vs `4c472b50` preserved across ALL sub-slices. Cleanup work is test-fixture-focused; should not touch Q-PR1 sacred 5 paths. If any SS surfaces Q-PR1 touch requirement, escalate to dedicated Red blueprint per Q-NAMING-E + F precedent.

- **Per-SS push authorization**: per `feedback_push_master_gate`, no auto-push. Each SS push requires explicit user signal. Allows fine-grained progress control + intermediate review.

- **AD/C/E/B1/B2/F inherited contracts preserved**: SS1-SS8 inherit N12-N24 from F. No re-litigation. Any SS finding that would touch inherited contracts surfaces as separate Red blueprint.

### Cross-flip role assignment (per user 2026-06-01 "延续一直以来的模式" directive)

User explicitly continued AD/C/E/B1/B2/F cross-flip pattern for baseline cleanup:

- Step 4.1 meta-blueprint draft → Claude (this commit)
- Step 4.2 review → Codex
- Step 4.3 preflight drafter → Claude (per AD/C/E/B1/B2/F precedent)
- Step 4.4 preflight amendment → Claude
- Step 4.5 self-check → Claude (doc-only)
- Step 4.6 scoped anchor → Claude
- Step 4.6.5 pre-impl grep — N/A for meta-blueprint; each sub-slice does mini pre-impl census instead
- Step 4.7 implementation (per sub-slice) → Codex (per user directive)
- Step 4.7 review (per sub-slice) → Claude (per user directive — CRITICAL independent test re-run for each SS per Q-NAMING-E + B2 + F lesson)
- Step 4.8 closure → Codex or Claude (per CADENCE no strict assignment) — only after ALL 8 SS shipped
- Step 4.9 archive → Codex or Claude (per CADENCE no strict assignment)

If user wants to flip any role assignment, they may signal at any handoff point.
