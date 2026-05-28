# Audit: T8-D Round 4 PyReason + ProbLog Canonical User Docs

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t8-d-round4-pyreason-problog-canonical-user-docs.md`
- Stage: scoped
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T8-D round 4 canonical user-docs blueprint pair drafted | Triggered by T10-1 `cde072fa`, T10-2-A `65cc79a3`, T10-2-B `92fd6013`, T10-3-A `e7bab90f`, and T10-3-B `ac42a379`; Q1-Q12 pending Step 4.6 after amend. |
| 2026-05-28 | draft amend | this commit | Scope expanded to include `rules-and-inferences.md` deprecation cleanup | User source-backed stale first-class `Inference` / `Query` teaching; Q11-Q12 added. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed inventory completed | Four-file implementation surface selected; focused docs-only baseline `140 OK`. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-1 shipped public `ProbLogSemantics.uncertainty_projection` and ProbLog
  adapter consumption of canonical `raw_kind` / `bound` annotations.
- T10-2-A shipped public `PyReasonSemantics.iteration_count` and canonical
  `SemanticsProfile.iteration_count`, with explicit conflict behavior for
  legacy temporal timesteps modes.
- T10-2-B shipped `PyReasonSemantics.derived_bound` and `atom_bounds`, with
  application atom ids converted to PyReason body-atom targets.
- T10-3-A shipped `fact_boundaries` as a canonical alias while preserving
  legacy `valid_time_boundaries`.
- T10-3-B shipped `time_binned` with strict `bin_size` whitelist and binned
  temporal materialization.
- T8-D round 3 already aligned ProbLog row provenance evidence docs; this cycle
  must not reopen `evidence.md` unless Step 4.6 finds a direct contradiction.
- User source-back reports `rules-and-inferences.md` has substantial stale
  first-class `Inference` teaching and deprecated `Query` one-off projection
  teaching. Step 4.6 must independently grep every `Inference` / `Query`
  occurrence and map delete / rewrite / legacy-compat treatment.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs and target-file line refs.

## 2A. Step 4.6 Scoped Findings

- `semantics.md` edit map: wrapper table `:18-41`, ProbLog section `:101-137`,
  PyReason section `:139-175`, SemanticsProfile note `:177-194`, complete
  example/checklist `:269-340`.
- `assertions.md` already has raw carrier teaching at `:136-231`; add a short
  T10-1 projection-policy note instead of duplicating schema.
- `rules-and-inferences.md` cleanup is real: stale `Query` section `:491-514`,
  large `Inference` compatibility section `:516-589`, lifecycle/checklist
  mentions `:608-625, :644-759`. Current `Rule` / `RuleExpr` / match/evaluate
  sections `:60-489` should be preserved.
- `00_user_guide.en.md` is stale enough to include as the fourth file:
  `:578-630` and `:1038-1081` still list old PyReason temporal/canonical
  surfaces.
- Source-backed behavior anchors:
  - ProbLog default reject and policies:
    `tests/test_problog_semantics_profile_migration.py:400-525`.
  - PyReason C74/C78/C77 tests:
    `tests/test_pyreason_semantics_profile_migration.py:293-893`.
  - SemanticsProfile temporal modes:
    `src/factgraph/core/semantics/profile.py:165-250`.
  - PyReason temporal adapter conflicts/materializers:
    `src/factgraph/adapters/pyreason/engine_eval.py:283-580`.
- Verification: focused docs-only set ran `140 tests` and passed.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What exact `semantics.md` sections will be edited? | Answered: `:18-41`, `:101-175`, light `:177-194`, `:269-340`. |
| Q2 | Where does the `assertions.md` raw uncertainty annotation text belong? | Answered: existing raw carrier area `:177-212`. |
| Q3 | Should the SDK guide be edited? | Answered: yes, stale `:578-630` and `:1038-1081`. |
| Q4 | How should T10-2-A's default `iteration_count=1` behavior change be explained? | Answered: wrapper default 1 vs no-profile engine default 2; explicit temporal conflicts reject. |
| Q5 | How deep should `bin_size` documentation go? | Answered: full whitelist + reject examples, no parser dump. |
| Q6 | How deep should `atom_bounds` atom-id documentation go? | Answered: user-facing `<rule_id>:atom_<index>` only, no internal conversion dump. |
| Q7 | How should `fact_boundaries` be taught without encouraging legacy spelling? | Answered: canonical-first; legacy compatibility sentence only. |
| Q8 | Which files are explicitly left alone? | Answered: evidence, audit docs, adapter docs, unrelated quickstarts, runtime/tests, dirty baseline, design-points. |
| Q9 | What implementation split should be used? | Answered: four docs commits plus close/archive. |
| Q10 | Are there stop/amend findings? | Answered: no. |
| Q11 | How should `Inference` be taught? | Answered: legacy compatibility section, not first/default path. |
| Q12 | How should `Query` be taught? | Answered: remove one-off projection example; mark internal-only only if referenced. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| T10 behavior is documented inaccurately | User docs teach a contract the runtime does not ship | Source-back every teaching point to T10 archive and current source/tests. |
| T10-2-A default warning is unclear | Users may confuse wrapper default `1` with no-profile engine default | Require explicit Q4 wording before implementation. |
| `time_binned` docs accept arbitrary durations | User docs contradict strict whitelist and parser behavior | Document exact whitelist and reject examples. |
| `atom_bounds` docs leak internal conversion details | Quickstart becomes implementation docs | Explain user-facing atom id format only. |
| Legacy `valid_time_boundaries` becomes preferred in docs | Canonical migration message is weakened | Teach `fact_boundaries` first, legacy only as compatibility note. |
| `rules-and-inferences.md` cleanup becomes destructive | Docs could imply `Inference` / `Query` runtime removal | Keep implementation untouched; mark compatibility or internal-only as needed. |
| Current `Rule` / `RuleExpr` / match/evaluate teaching regresses | Quickstart would weaken the canonical user path | Ensure canonical API leads after cleanup and keep unrelated sections stable. |
| Evidence docs regress | T8-D round 3 shipped row-provenance wording is weakened | Keep `evidence.md` out of scope unless Step 4.6 stop/amend fires. |
| Adapter module docs enter scope | S docs cycle expands beyond user quickstart alignment | Name adapter docs as future owner, not edit target. |
| Runtime/tests/governance/dirty baseline touched | Workflow violation | Status checks before closure and push. |
| Four untracked design-point files are absorbed | Claim-first / design-point intake leaks into docs cycle | Keep design-point intake explicitly out of scope. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q12 answered.
- [x] File scope stays at four files or fewer.
- [x] T10-2-A default warning reviewed.
- [x] `bin_size` whitelist wording reviewed.
- [x] `atom_bounds` atom-id wording reviewed.
- [x] `rules-and-inferences.md` deprecation cleanup map reviewed.
- [x] Leave-alone sweep reviewed.
- [x] Focused docs-only verification plan reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending implementation / closure.
