# Task Blueprint Audit: T2.3c — Aggregate Souffle adapter wire

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3c-aggregate-souffle-wire.md](./2026-05-23_t2-3c-aggregate-souffle-wire.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md)
  - Archived T2.3b [2026-05-23_t2-3b-aggregate-sdk-bridge.md](../archive/2026-05-23_t2-3b-aggregate-sdk-bridge.md)
  - Archived T2.1 [2026-05-23_t2-1-ne-adapter-dispatch.md](../archive/2026-05-23_t2-1-ne-adapter-dispatch.md)
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md)
- Blueprint: [2026-05-23_t2-3c-aggregate-souffle-wire.md](./2026-05-23_t2-3c-aggregate-souffle-wire.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | T2 Track 5th implementation sub-slice (after T2.1 ne / T2.2 ArithExpr / T2.3a Aggregate substrate / T2.3b Aggregate SDK bridge). Closes Souffle adapter aggregate wire gap. T2.3a + T2.3b consumed unchanged. T2.3.d ProbLog wire remains separate. Estimated ~300 LOC (150 code + 150 tests). S-class lightweight per §5.7 trigger analysis. Cross-flip: Claude drafts, user reviews (continued from T2.3b inverted pattern). |

## Decision Notes

### 2026-05-23 — Initial scope lock

- **T2.3a substrate is the foundation**:5 layers shipped at `477fcccb`(IR + validator + Python eval + raw resolver + application Rule serialization + two-pass)。**T2.3c does NOT touch any of these 5 layers**;scope diff verified via §6.2。
- **T2.3b SDK is the IR producer**:5 helpers + `_AggregateRef` + DSL→IR lowering + bridge validator gate shipped at `4e3176d2`。**T2.3c does NOT touch T2.3b**;SDK lowering output is consumed unchanged as the IR shape T2.3c Souffle wire receives。
- **T2.3c ships only**:(a)Souffle adapter dispatch extension recognizing aggregate-tuple in cmp atoms;(b)`_compile_aggregate` helper for Souffle DL aggregate body lowering;(c)`_compile_cmp_side` aggregate-aware extension;(d)`_vars_in_atom` aggregate-walking extension(correlated outer vars only,target_var excluded);(e)`_validate_atom_subset` aggregate shape validation;(f)`application/docs/rule.md` adapter status table flip。
- **T2.3.d / PyReason 仍 future**:ProbLog `findall/3` + list predicates wire — separate slice;PyReason aggregate marked N/A in parent essay §10.6.3 line 1711 — out of scope。

### 2026-05-23 — S-class assessment

Per Track plan §1.2.1 + §1.2.4 trigger analysis(mirror of T2.3b §5.7):

| Factor | T2.3c reality | Trigger fire? |
|---|---|---|
| Public API impact | None — adapter-internal extension;no public-facing API rename/add/remove | NO |
| Cross-commitment Q load-bearing | None — parent C99 / C100 / C101 / C104 already locked at T2.3a substrate;Souffle wire is mechanical lowering | NO |
| Design vs shipped ≥ 3 commitments conflict | None — additive over T2.3a substrate + T2.3b SDK | NO |
| Sub-slice count | Track plan §1.2.6 lists T2.3a/b/c/d as 4 sub-slices;T2.3c is 3rd | Within prediction |
| Cross-file commitment mismatch ≥ 2 files | None — extension limited to `where_compile.py` + `application/docs/rule.md`;all consistent with T2.1/T2.2 adapter precedent patterns | NO |
| Public API rename ≥ 3 caller sites | NO — no API surface change | NO |
| Cross-engine semantic decision | None — Souffle wire only,ProbLog separated to T2.3.d per Track plan §1.2.6 | NO |
| Size budget(S ≤ ~300 LOC + ~200 tests = ~500)| ~300 LOC est total | Within budget |

**Conclusion**:S-class lightweight applies。No Stage 2 decision doc opened。

### 2026-05-23 — G1-G7 visible gate mapping

- **G1** — Blueprint §1 + §2 cite parent essay §10.6.3 (C99) + §10.6.4 (C100) + §10.6.5 (C101) + §10.6.7 (C103) + §10.6.8 (C104) + §8.8 explicitly;§2 sub-goal headers reference C99/C100/C101/C104 or specific adapter-wire responsibilities。
- **G2** — Blueprint §4.1 documents G2 source-grep audit on `src/factgraph/adapters/souffle/`(`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate"` → 0 hits;dispatch fallthrough at line 731)。T2.3a substrate visibility verified at `where_ast.py:75` + `:102` + `where_ast_validate.py`。T2.3b SDK lowering output verified at `sdk/dsl/expr.py:209` + `:459` + bridge validator gate。
- **G3** — Blueprint §4.2 uses file:line citations(where_compile.py:20/434-626/506-512/561-567/679-731/905-908/1060-1103/1139-1173/1176)。Citations to be re-verified at row-drafting / impl time per CADENCE Rule 1。
- **G4** — Blueprint §2 sub-goals 2.1-2.9 each labeled with C-number(C99/C100/C101/C104)or specific responsibility(dispatch extension / helper / cmp side extension / filter atom recursion / var extraction / validation / acceptance / G7)。
- **G5** — Blueprint §3 Non-goals lists 12 explicit deferrals or out-of-scope items with rationale(T2.3.d ProbLog / PyReason / T2.3a substrate change / T2.3b SDK change / Nit aggregate-in-arith / nested aggregate / new kinds / new filter atoms / witness layout / Souffle mean derived fallback / AggregateNoValue Souffle sentinel / M-class doc)。
- **G6** — Reviewer should independently spot-check:
  1. T2.3a substrate present at cited where_ast.py / where_ast_validate.py lines
  2. T2.3b SDK lowering present at sdk/dsl/expr.py:209/459 + bridge validator gate
  3. Souffle adapter aggregate empty(`rg` returns 0)
  4. ProbLog + PyReason adapter aggregate empty(`rg` returns 0)
  5. `where_compile.py:434-626` dispatch structure matches blueprint §4.2 description
  6. Souffle native aggregator syntax(parent essay claim "Souffle 原生 count/sum/min/max/mean")— spot-check Souffle 2.x documentation or our project's Souffle dependency
  7. §5.7 S-class trigger row claims accurate against §1.2.4 trigger conditions
- **G7** — Blueprint §5.6 lists 6 pre-impl precondition checks:
  1. T2.3a substrate landed
  2. T2.3b SDK lowering present
  3. Souffle aggregate dispatch empty(this slice's add point)
  4. ProbLog aggregate dispatch empty(T2.3.d boundary)
  5. PyReason aggregate dispatch empty(out-of-scope boundary)
  6. **Souffle end-to-end smoke** — `build_application_rule(...)` with `agg_sum(...)` example produces IR that current Souffle adapter rejects via `WhereValidationError("unsupported atom kind: ...")` at line 731(confirms precondition gap)

### 2026-05-23 — User's Step 4.2 review focus areas (anticipated upfront)

Drafter anticipates user's Step 4.2 review will focus on:

1. **Souffle DL syntax correctness** — particularly `mean` native support claim. Parent essay line 1711 claims native;blueprint §4.3 backs with Souffle 2.x reference but no project-level Souffle version pin found in `pyproject.toml` / installation docs. If reviewer doubts `mean` support,decision options:(a)trust parent essay,verify at impl;(b)defer `mean` to a sub-slice;(c)derive `mean` as `sum/count` upfront。Drafter leans (a) with (A-fallback) deviation path documented in §10 Outcome at closure if impl reveals incompatibility。
2. **Aggregate-local var isolation algorithm in `_vars_in_atom`** — §5.5 uses a simplification:return ALL referenced vars in filter,let upstream `extract_where_variables(where)` intersect with outer-scope known vars。Reviewer may push for stricter binding-order analysis inside the helper itself。Drafter rationale:upstream consumer already has outer-scope knowledge;duplicating binding logic inside `_vars_in_atom` adds complexity without correctness benefit。Test 7.5(TRUE isolation discriminator)verifies the simplification holds。
3. **`AggregateNoValue` Souffle semantic gap** — §2.5 explicitly defers the `AggregateNoValue` sentinel handling at Souffle DL layer;Souffle's native empty-set behavior(min/max/mean → 0)deviates from C101。Reviewer may want this either(a)hard-blocked(force Souffle wire to detect empty sets explicitly via `count : {body} = 0` branch),or(b)accepted as scoped deferral with explicit docs warning。Drafter leans (b) per parent essay §8.9 "Aggregate Empty Set Behavior Convergence" deferral language;Python evaluator path remains source-of-truth for `AggregateNoValue` semantics。
4. **Filter atom compile factoring** — §5.3 proposes a separate `_compile_filter_atom_within_aggregate` function;alternative is extending `_compile_atom` with a `within_aggregate=True` flag。Reviewer may prefer the flag-extension approach for less code duplication。Drafter neutral;impl can pick cleaner factoring。
5. **`_AGGREGATE_KINDS` import vs adapter-local mirror** — §5.1 prefers import from substrate(single source of truth);some lint rules forbid underscore-prefix cross-module imports。If lint complains,fallback to adapter-local mirror with explicit invariant check。Reviewer may want lock-down on choice upfront。Drafter rationale:try import first;fallback only if lint forces it。

### 2026-05-23 — Anticipated reviewer P-finding candidates

Drafter anticipates these from Step 4.2 review:

- **Souffle DL aggregate result `to_string(...)` wrap** — §5.3 wraps aggregate output in `to_string(...)` for symbol-typed outer var binding consistency with `_compile_arith_atom`(line 1103 precedent)。Reviewer may verify Souffle 2.x aggregator return type:if native return is already string-coercible without explicit `to_string`,wrap may be redundant。Or:if aggregate return is numeric and outer var is bool-domain,`to_string` may produce wrong DL。Likely impl-time verification + (A-fallback) deviation if needed。
- **Test 7.5 isolation discriminator strength** — test relies on `("pred", "user:exists", ["$o"])` in outer scope to fail because `$o` is aggregate-local。If Souffle adapter does not raise but silently emits invalid DL,the test should still catch via either:(a)`WhereValidationError` from dataflow gate,or(b)Souffle compile error at runtime。Drafter expects (a)but should add explicit pytest `assertRaises` rather than rely on downstream test infrastructure。
- **`_vars_in_atom` simplification target_var exclusion** — §5.5 explicitly `found.discard(target_var)` to exclude aggregate-local result binding。But what if `target_var` happens to equal an outer-scope var name(`$total` could be aggregate target var OR outer-bound var depending on caller)? T2.3b SDK lowering uses `$_agg<N>` for target vars(per T2.3b acceptance tests);impl trusts this convention。Reviewer may push for explicit precondition test that target_var is always `$_agg<N>` prefixed。
- **Filter `not` body recursion depth** — §5.3 recurses into filter atoms;`not` body itself contains pred atoms。Compile path may need to handle `_compile_not_body_atom`(line 939)precedent or compile not-body inside aggregate manually。Drafter may need to clarify or push to §8 step 6 impl detail。

### 2026-05-23 — Cross-slice contract preservation summary

| Prior slice | Contract preserved | Verification at T2.3c review |
|---|---|---|
| T1.1 application `Rule` DTO | `factgraph.application.protocol.Rule` consumed unchanged | 0 diff in `application/protocol/rule.py`(verify post-impl `git diff <impl-base>..HEAD -- src/factgraph/application/`) |
| T1.2 DSL→application bridge | `build_application_rule(...)` consumed unchanged | 0 diff in `sdk/dsl/application_rule.py` |
| T2.1 `ne` adapter dispatch | Souffle `_compile_ne_filter` unchanged | 0 diff at where_compile.py:876-902 |
| T2.2 ArithExpr substrate | Souffle `_compile_arith_atom` unchanged | 0 diff at where_compile.py:1060-1103 |
| ProbLog hygiene | Import cycle fix unchanged | 0 diff in `audit/round_events.py` aggregate area |
| Fixture cleanup | `meta[confidence]` cleanup unchanged | 0 diff in tests/test_problog_export.py / tests/test_problog_engine_eval.py |
| T2.3a Aggregate substrate | IR + validator + Python eval + application Rule serialization unchanged | 0 diff in `core/rules/where_ast.py` / `where_ast_validate.py` / `where_eval.py` / `application/protocol/rule.py` aggregate-related lines |
| T2.3b Aggregate SDK + bridge | 5 helpers + `_AggregateRef` + DSL→IR lowering + bridge validator gate unchanged | 0 diff in `sdk/dsl/expr.py` / `sdk/dsl/application_rule.py` / `sdk/dsl/__init__.py` / `sdk/docs/` |

Cross-slice non-regression test plan:run T2.3a + T2.3b + T2.1 + T2.2 relevant suites at Step 4.7 impl verification(scope at §8 step 11)。

### 2026-05-23 — Cross-flip inversion blindness mitigations

Per T2.3b retrospective(memory `feedback_audit_to_archive_cadence` + topic file `project_rule_expression_t1_progress`):cross-flip inversion(Claude drafts,user reviews)risks "drafter assumption blindness" compounding across v1/v2 rounds。

T2.3c mitigations applied at draft time:

- **Full source re-read**(first-touch this session)of `where_compile.py:434-626` dispatch + `:679-731` validation + `:905-908` cmp side + `:1060-1103` arith compile precedent + `:1139-1173` var extraction。Cited file:line precision in §4.2。
- **G2 source-grep audit** verified absence of aggregate handling(0 hits)。
- **Acceptance tests designed as discriminators** per T2.3b lesson:test 7.5(TRUE C104 isolation discriminator)is the analog of T2.3b's TRUE self-ensure test。Other tests(7.1 per-kind / 7.4 correlated pass-through)isolate one algorithm decision each。
- **Anticipated P-finding candidates pre-listed** so reviewer can quickly flag known sharp edges(Souffle mean support / `_vars_in_atom` simplification / `AggregateNoValue` gap / filter factoring / `_AGGREGATE_KINDS` import)。
- **Cross-slice contract preservation table** in this audit log makes 0-diff expectations explicit for every prior slice。

If Step 4.2 still requires multi-round tightening,that signals further mitigations needed for future Claude-drafts slices(e.g.,more sub-decisions locked in upfront,or smaller drafting scope per round)。

### 2026-05-23 — Branch state at draft commit time

- Current branch:`v0.2.0-blueprint-t2-3c-aggregate-souffle-wire-2026-05-23`
- Forked from:`1666ffd3 docs(memory): consolidate T2.3b aggregate SDK bridge progress`(T2.3b memory sync commit on impl branch)
- Sacred `master`:`562c74195df43e933bed92a3ff25de94dd8ce666` — unchanged
- Dirty set:4 M(docs design-points readme + 3 examples notebooks)+ 1 untracked(`rainbird-ai sdk code/`)— preserved
