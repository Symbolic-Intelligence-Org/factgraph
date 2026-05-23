# Task Blueprint Audit: T2.3d — Aggregate ProbLog adapter wire

- Status: implemented
- Created: 2026-05-23
- Last Updated: 2026-05-23 (Step 4.8 closure)
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3d-aggregate-problog-wire.md](./2026-05-23_t2-3d-aggregate-problog-wire.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md)
  - Archived T2.3b [2026-05-23_t2-3b-aggregate-sdk-bridge.md](../archive/2026-05-23_t2-3b-aggregate-sdk-bridge.md)
  - Archived T2.3c [2026-05-23_t2-3c-aggregate-souffle-wire.md](../archive/2026-05-23_t2-3c-aggregate-souffle-wire.md)
- Blueprint: [2026-05-23_t2-3d-aggregate-problog-wire.md](./2026-05-23_t2-3d-aggregate-problog-wire.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-23 | draft | Blueprint created | User-drafts / Claude-reviews pattern restored per T2.3c retrospective. T2.3d scope is ProbLog adapter-only aggregate wire over T2.3a substrate + T2.3b SDK + T2.3c query-variable extraction. No SDK/core/application/Souffle changes. |
| 2026-05-23 | draft | Step 4.2 v2 tightening | Claude review surfaced 3 Required + 1 Worth-considering: two line-cite drifts, empty `sum_list([], 0)` ambiguity, inaccurate G7 #5 "rejects or mishandles" wording, and unlocked fresh-var naming. Applied all four: corrected cites, locked `sum_list([], 0)` as SWI-Prolog/ProbLog standard behavior, changed G7 #5 to silent JSON-quoted literal mishandle, and added `Agg{Prefix}{N}` fresh-var naming invariant. |
| 2026-05-23 | scoped | Status: draft → scoped | Claude v2 re-review passed with 0 Blocker / 0 Required / 0 Worth-considering. Anti-pattern propagation grep clean. User-drafts pattern validated for T2.3d (2 rounds / 4 findings vs T2.3c 6 rounds / 21 findings). Ready to fork impl branch. |
| 2026-05-23 | g7-precondition | G7 precondition recorded before implementation | All G7 checks completed before code edits. Local ProbLog binary smoke found list predicates require `:- use_module(library(lists)).`; blueprint amended in scoped state to conditionally emit the directive for aggregate exports. Sacred master and dirty set preserved. |
| 2026-05-23 | implemented | Step 4.8 closure | Implementation landed in `a33b876e`; Step 4.7 Worth-considering dead helper cleanup landed in `d7e2a650`; Claude review passed with 0 Blocker / 0 Required. Blueprint Status moved to implemented and §10 Outcome completed. |

## Decision Notes

### 2026-05-23 — Initial scope lock

- **T2.3d closes only ProbLog adapter aggregate export**. It does not revisit T2.3a substrate semantics, T2.3b SDK authoring, or T2.3c Souffle lowering.
- **ProbLog lowering strategy follows parent essay §8.8 / §1719**: `findall/3` + list predicates. There is no native aggregate operator analogous to Souffle.
- **Empty-set semantics mirror C101 without a sentinel object**:
  - count/sum emit 0 via `length` / `sum_list`
  - min/max/mean use `L = [_|_]` guard so empty set fails the enclosing rule body
- **Docs status flip is in scope** because existing docs explicitly defer ProbLog aggregates to T2.3.d.

### 2026-05-23 — S-class assessment

| Factor | T2.3d reality | Trigger |
|---|---|---|
| Public API impact | None; no new SDK symbol | No |
| Core/substrate change | None; consumes T2.3a unchanged | No |
| Cross-engine semantic decision | None; ProbLog-specific lowering mirrors C101 and T2.3c semantics | No |
| Size | Estimated 250-450 LOC code+tests after T2.3c calibration | S with caution |
| Public API rename | None | No |
| New commitment conflict | None known | No |

Conclusion: S-class lightweight blueprint is appropriate. If G7 reveals missing ProbLog list predicates or incompatible runtime behavior requiring a new design decision, pause and amend/escalate. Empty `sum_list([], 0)` is now locked as standard SWI-Prolog/ProbLog behavior, not an open design choice.

### 2026-05-23 — G1-G7 visible mapping

- **G1**: Blueprint §1 and §2 cite parent essay C99-C104 plus §8.8/§1719 lowering strategy. Hygiene/source-of-truth drivers are explicitly tied to prior archive rows.
- **G2**: Draft-time source read covered `problog_export.py:1-359`, `tests/test_problog_export.py`, `tests/test_problog_engine_eval.py`, T2.3a/b/c archive docs, current SDK/application docs rows, and track plan/memory T2.3.d rows.
- **G3**: Blueprint §4 uses concrete file:line cites for ProbLog dispatch, term conversion, tests, and docs rows. Step 4.2 v2 corrected `_to_problog_var` to `problog_export.py:335-340` and `_to_problog_literal` to `:343-355`.
- **G4**: Goals §2.1-§2.7 map to C99/C100/C101/C104 or docs/gate obligations.
- **G5**: Non-goals explicitly exclude SDK/core/application/Souffle/PyReason/probability semantic changes and runtime binary execution requirement.
- **G6**: Reviewer should independently verify `problog_export.py` dispatch lines, current absence of aggregate handling, list-predicate algorithm, query-var behavior from T2.3c, and docs rows.
- **G7**: Blueprint §5.9 defines pre-impl checks, including T2.3a/b/c contract presence and current ProbLog aggregate gap. Step 4.2 v2 clarified that the current gap is silent mishandling: aggregate tuples are JSON-encoded/quoted as Prolog literals rather than rejected.

### 2026-05-23 — Cross-slice contract preservation table

| Prior slice | Contract in T2.3d |
|---|---|
| T1.1 Rule DTO | 0 diff expected in `application/protocol/rule.py` |
| T1.2 DSL bridge | 0 diff expected in `sdk/dsl/application_rule.py` |
| T2.1 `ne` | Existing ProbLog `\=` dispatch stays intact |
| T2.2 ArithExpr | Existing `is/2` arithmetic builtin export stays intact |
| ProbLog hygiene | Import-cycle boundary remains intact |
| meta-confidence fixture cleanup | ProbLog export tests should stay fully runnable |
| T2.3a substrate | 0 diff expected in `core/rules/*` and `application/protocol/rule.py` |
| T2.3b SDK | 0 diff expected in `sdk/dsl/*` and `sdk/docs/04_api_surface.en.md`; `sdk/docs/03_rules_and_inferences.en.md` row may flip |
| T2.3c Souffle | 0 diff expected in `adapters/souffle/where_compile.py`; `extract_where_variables` consumed unchanged |

### 2026-05-23 — Review focus areas for Claude Step 4.2

1. **Mean derivation correctness**: verify `Mean is Sum / Count` after `L = [_|_]` is sufficient and uses valid ProbLog/Prolog syntax.
2. **Empty sum behavior**: verify implementation/tests preserve the locked standard behavior `sum_list([], 0)`; fallback is only a §10 deviation path if actual ProbLog binary behavior contradicts SWI-Prolog `library(lists)`.
3. **Variable scoping inside `findall/3`**: confirm aggregate-local variables do not escape and correlated outer variables remain visible.
4. **Two-aggregate comparison**: ensure blueprint acceptance covers both sides aggregate and fresh variable collision avoidance.
5. **`not` in aggregate filter**: confirm existing `_compile_atom` recursion can be reused safely.
6. **Validation boundary**: decide whether unknown aggregate-like tuple operands should be rejected specifically as aggregate shape errors or generic unsupported term errors.
7. **Runtime smoke scope**: decide whether exported-text tests are enough or local ProbLog binary smoke should be required if available.

### 2026-05-23 — Step 4.2 v2 tightening decisions

Claude Step 4.2 review surfaced:

| Finding | Resolution |
|---|---|
| P1 Required — line citation drift for `_to_problog_var` / `_to_problog_literal` | Blueprint §4.3 corrected to `problog_export.py:335-340` and `:343-355`. |
| P2 Required — empty `sum_list([], 0)` was both provisional and definitive | Locked definitive behavior: `sum_list([], 0)` is standard SWI-Prolog `library(lists)` behavior inherited by ProbLog. Any contrary binary result becomes §10 deviation/amendment, not an implementation choice. |
| P3 Required — G7 #5 said "rejects or mishandles" but shipped exporter silently mishandles | G7 #5 now requires reproducing JSON-quoted literal output through `_to_problog_term:315-318` → `_to_problog_literal:343-355`. |
| P4 Worth-considering — fresh variable naming unlocked | Adopted. `_CompileContext.fresh(...)` must emit reserved `Agg{Prefix}{N}` names, never `V_...`, preventing collision with user variables converted by `_to_problog_var(...)`. |

Status remains `draft`; no scoped transition authorized.

### 2026-05-23 — Step 4.6 scoped anchor

Claude v2 re-review passed cleanly:

- P1 line cites verified.
- P2 `sum_list([], 0)` language consistent across §2.4 / §5.3 / §5.7 / §5.8.
- P3 G7 #5 now precisely describes silent JSON-quoted literal mishandling.
- P4 fresh-var naming convention locked as `Agg{Prefix}{N}`.
- Anti-pattern grep found no stale "to be verified by G7" / "fallback if unavailable" / "rejects or mishandles" / old `AGG_*` naming / old line-cite text.

Status moved to `scoped`. No code changes have started. Implementation branch should fork from this scoped commit.

### 2026-05-23 — G7 precondition results and scoped amendment

G7 was executed on `v0.2.0-impl-t2-3d-aggregate-problog-wire-2026-05-23` before any code edits.

| # | Check | Result |
|---|---|---|
| 1 | T2.3a substrate exists | PASS — `where_ast.py:75` `AggregateAtom`, `where_ast.py:102` `_AGGREGATE_KINDS`, `where_ast_validate.py:68` `validate_where_ast`, `where_eval.py:769` `_resolve_aggregate_term_for_env`. |
| 2 | T2.3b SDK bridge can produce aggregate IR | PASS — `sdk/dsl/expr.py:213` `_AggregateRef`, `:329` `agg_count`, `:334` `agg_sum`, `:459` `_lower_compare_with_aggregate`, `:482` `_lower_aggregate_ref`; bridge validator call at `sdk/dsl/application_rule.py:62`. |
| 3 | T2.3c query-var extraction excludes aggregate-local vars | PASS — smoke returned `['$total', '$u']` for an aggregate filter containing `$o` and `$_agg1`; aggregate-local vars did not escape. |
| 4 | ProbLog aggregate dispatch currently absent | PASS — `rg "AggregateAtom|_AGGREGATE_KINDS|aggregate|findall|sum_list|min_list|max_list" src/factgraph/adapters/problog/problog_export.py` returned no semantic aggregate hits. |
| 5 | Current ProbLog exporter silently mishandles aggregate IR | PASS — `_compile_atom(("eq", "$total", ("sum", "$_agg1", ...)))` emitted `V_TOTAL = '["sum","$_agg1",...]'`, confirming JSON-quoted literal mishandle rather than rejection. |
| 6 | ProbLog export test module is healthy | PASS — `PYTHONPATH=src python -m unittest tests.test_problog_export` ran 14 tests OK. |
| 7 | Local ProbLog binary/list predicate smoke | PASS with amendment — `problog` binary exists. Smoke without imports failed with `UnknownClause: No clauses found for 'sum_list/2'`; same smoke with `:- use_module(library(lists)).` passed (`ok: 1`). |

**Scoped amendment**: T2.3d remains S-class. The locked semantics do not change, but aggregate exports must conditionally emit `:- use_module(library(lists)).` when aggregate lowering uses list predicates. Non-aggregate exports should not gain the directive so existing exact-output tests remain stable.

This amendment is recorded before implementation code edits, matching the G7 timing discipline established by fixture cleanup and T2.3a/T2.3c.

### 2026-05-23 — Step 4.8 closure notes

Implementation lineage:

| Commit | Purpose |
|---|---|
| `c3127703` | G7 precondition record + scoped amendment for conditional `library(lists)` directive |
| `a33b876e` | Main ProbLog aggregate wire implementation, tests, and docs flip |
| `d7e2a650` | Step 4.7 follow-up: remove unused `_is_aggregate` helper |

Claude Step 4.7 review result:

- PASS — 0 Blocker / 0 Required
- 1 Worth-considering: unused `_is_aggregate(...)` helper
- Resolution: adopted option (a), deleted the dead helper in `d7e2a650`

Verification recorded for closure:

- `tests.test_problog_export`: 26 tests OK
- relevant cross-slice sweep: 114 tests OK locally before closure; Claude reviewer reported 124 relevant tests OK
- ruff clean on touched ProbLog exporter + tests
- local ProbLog binary smoke passed with generated aggregate program and `:- use_module(library(lists)).`

Outcome:

- ProbLog aggregate wire is implemented.
- No SDK/core/application/Souffle code changed.
- Docs status rows now mark ProbLog aggregate support as shipped.
- No new unrelated baseline drift surfaced.
- Ready for Step 4.9 archive.

### 2026-05-23 — Branch state at draft commit time

- Branch: `v0.2.0-blueprint-t2-3d-aggregate-problog-wire-2026-05-23`
- Base: `7331a152` (T2.3c memory sync)
- Sacred `master`: `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty set preserved: 4 M + 1 untracked
