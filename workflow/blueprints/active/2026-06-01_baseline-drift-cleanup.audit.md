# Baseline Drift Cleanup Meta-Blueprint Audit: 189 pre-existing failures across 27 test files

- Blueprint: [2026-06-01_baseline-drift-cleanup.md](./2026-06-01_baseline-drift-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-01 | draft | Meta-blueprint created + fresh failure census | Post Q-NAMING 6-phase routemap completion (AD/C/E/B1/B2/F all archived + pushed origin), launching baseline drift cleanup cycle per user 2026-06-01 directive (方案 C quick wins + 方案 A meta-blueprint framework). Branch `v0.2.0-blueprint-baseline-drift-cleanup-2026-06-01` forked from Q-NAMING-F archive HEAD `10b10981` (inherits AD + C + E + B1 + B2 + F complete lifecycles + N1-N24 invariants from F). Sacred Q-PR1 5-path 0-diff preserved at draft commit; sacred master `562c74195df4...` unchanged; dirty baseline (4 M + 2 D + 2 untracked) preserved. **Fresh `tests/` cohort census 2026-06-01**: 189 failed / 2294 passed / 32 skipped / 1037 subtests passed. Error category breakdown (per traceback grep): 102 `NoneType.proof` (SS7, chain-blocked by SS5), 68 `meta[confidence] removed` (SS5), 66 `SDKStore.ref` + 18 `.read` + 4 `.retract` + 2 `.set` + 2 `.get` = 92 SDKStore shape (SS4), 44 `Rule.where` TypeError (SS1), 24 `ReadPolicy` import (SS3), 20 `_eval_eq_atom` + 4 `_eval_arith_atom` = 24 evaluator drift (SS6), 6 `engine_options=` T5 (SS2), 4 `0 != 1` + 4 `'failed' != 'passed'` + 2 sha256 + 2 idref_v1 + 2×2 Tuples + 2 `EvaluateRow.support_kind` = ~17 misc (SS8). Total error instances ~378 across 189 distinct failures across 27 unique failing test files. Sub-slice sequence locked per 方案 C quick wins first: SS1 (44 ✓ small) → SS2 (6 ✓ tiny) → SS3 (24 ✓ small) → SS4 (92 medium, audit-first) → SS5 (68 medium, unblocks SS7) → SS6 (24 medium) → SS7 (102 → ~0 expected via upstream propagation) → SS8 (~17 individual cases). Target: 189 → ~0 baseline failures. Lightweight per-SS mini-cadence per §5.1 (no full 9-stage CADENCE per SS unless surfacing Red-risk findings); single audit log tracks cumulative state. |

## Decision Notes

### 2026-06-01 — Initial scope freeze rationale

- **Cleanup vs release prep priority**: per user 2026-06-01 direct directive, baseline drift cleanup precedes v0.2.0-rc release prep because 189 pre-existing failures repeatedly forced expensive failure-categorization analysis during Q-NAMING-E + B2 + F Step 4.7 Red slice reviews. Cleaning these now means future release gates and any subsequent slice reviews start from a clean baseline.

- **方案 C + 方案 A locked**: quick wins first ordering + meta-blueprint with sub-slice tracking. Rationale:
  - Quick wins (SS1 Rule.where + SS2 engine_options + SS3 ReadPolicy = 74 errors) are small + well-defined fixture migrations → fast baseline drop establishes momentum
  - Medium-risk sub-slices (SS4 SDKStore shape + SS5 uncertainty + SS6 evaluator = 184 errors) need audit-first investigation but bounded scope
  - SS7 (NoneType.proof 102 errors) deferred to LAST because hypothesis predicts upstream SS5 (meta[confidence]) will unblock most of them via chain propagation (test setup at `_make_sdk()` calls `set_field(meta={"confidence":...})` which fails → `evidence_envelope` returns None → `.proof` access fails)
  - SS8 misc deferred to LAST because likely individual case-by-case investigation
  - Meta-blueprint avoids one giant cleanup commit; tracks cumulative progress; allows per-SS independent review

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
