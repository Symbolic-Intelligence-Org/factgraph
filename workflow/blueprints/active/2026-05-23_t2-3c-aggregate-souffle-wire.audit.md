# Task Blueprint Audit: T2.3c — Aggregate Souffle adapter wire

- Status: scoped
- Created: 2026-05-23
- Last Updated: 2026-05-23 (Step 4.6 scoped anchor — v6 review passed 0 findings)
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
| 2026-05-23 | draft | Step 4.2 v2 tightening | User v1 review surfaced 2 Blockers (P0 C101 empty-set semantics + P1 `_vars_in_atom` scope model false) + 4 Required (P2 §7.5 discriminator weak + P3 failure-path cite wrong + P4 SDK docs optional + P5 gate-off behavior unspec). User locked **A** for P0: implement empty-set guard now via `count : { same_body } > 0` prefix on min/max/mean; count/sum keep native empty=0. No Souffle sentinel object — `AggregateNoValue` represented by branch-not-firing (matches C101 "comparison violated / no env pollution"). P1-P5 v2 fixes applied in single amendment commit. Acceptance count grew from 11 to 17+ tests (new §7.8/§7.9/§7.10 + revised §7.5). Status stays `draft` pending v2 re-review. |
| 2026-05-23 | draft | Step 4.2 v3 tightening | User v2 re-review surfaced 5 Required findings on contract-precision gaps that would surface at impl time: P1 §2.6 still had v1 stale algorithm (outer_var_universe approach) contradicting v2 §5.5; P2 `_infer_var_type_domains` (`where_compile.py:829-861`) not covered — needs aggregate-aware recursion or impl-time `_assert_cmp_var_allowed` would fail on aggregate-internal cmp like `gt($_agg1, 5)`; P3 to_string/to_number boundary not precisely locked — eq binding vs numeric cmp wrapping rules unclear; P4 §6.2 still listed `sdk/docs/` 0-diff invariant contradicting P4 v2 fix that mandates `sdk/docs/03_rules_and_inferences.en.md` flip; P5 audit log G5 + Anticipated reviewer P-findings retained v1 stale claims. v3 fixes applied: §2.6 rewritten to align with §5.5; new §2.6b + new I11 invariant + §7.11 acceptance for `_infer_var_type_domains`; new §5.3.5 lock table for to_string/to_number rules + §7.8 expanded to 4 tests + new test (d); §6.2 narrowed to per-file 0-diff (sdk/docs/03 row exempt); audit log G5 updated + Anticipated P-findings marked superseded. Acceptance grew 17+ → 19+ tests. Status stays `draft` pending v3 re-review. |
| 2026-05-23 | draft | Step 4.2 v4 tightening | User v3 re-review surfaced 5 Required findings, no Blockers — convergence stage. P1 gate-off C100 contract self-contradiction in §5.7.5 (table said adapter enforces filter kind list "defense-in-depth" while narrative said C100 NOT in adapter) — split into Layer 1 structural validation (MANDATORY regardless of gate) and Layer 2 semantic checks (upstream-only); rationale that `_ARITH_KINDS` in aggregate filter is structurally undefined; new §7.10b 2-test discriminator. P2 §8 step 5 stale v1/v2 var-extraction text contradicting v3 §5.5 — split into step 5 (`_vars_in_atom` zero contribution) + step 5b (`_infer_var_type_domains` aggregate recursion); separation of concerns clarified. P3 §8 step 12 stale Outcome wording said "AggregateNoValue empty-set gap" which v2 lock A eliminated — reworded to "empty-set guard implementation status + Souffle deviations if discovered". P4 §2.5 line 146 prematurely claimed Souffle parse verification "Confirmed at Step 4.7" — flipped to future-tense "MUST be verified at Step 4.7" + impl requirement + (A-fallback) deviation path. P5 audit log Anticipated P-findings #1/#2/#3 still presented v1 framing — marked SUPERSEDED with v2/v3 cross-ref + cross-slice contract preservation `sdk/docs/` 0-diff narrowed per-file (04 stays 0-diff; 03 §3.2 row MUST flip; rest of 03 0-diff). Acceptance grew 19+ → 21+ tests. Status stays `draft` pending v4 re-review. |
| 2026-05-23 | draft | Step 4.2 v5 tightening | User v4 re-review verdict: no Blockers, 2 Required text/contract residuals — final convergence. P1 §4.2 touch-point line 317 `_vars_in_atom(...)` description still said "T2.3c extends to walk aggregate filter atoms (correlated outer vars only)" — v1/v2 stale algorithm contradicting v3/v4 §5.5 + §8 step 5; corrected to "aggregate operand contributes ZERO outer vars" + added separate `_infer_var_type_domains` line at where_compile.py:829-861 documenting recursion as separate concern with different consumer/algorithm. P2 §6 invariants I5/I10 wording weakened adapter's gate-off responsibility ("substrate enforces upstream, Souffle adapter trusts" + "C100 semantic restrictions deferred to upstream") contradicting v4 §5.7.5 Layer 1 structural lock — rewrote I5 to explicitly state adapter enforces filter kind list regardless of gate state (rationale: `_ARITH_KINDS` in aggregate filter is structurally undefined, not just semantically violated); rewrote I10 to mirror §5.7.5's two-layer table (Layer 1 structural mandatory regardless of gate + Layer 2 semantic upstream-only with C100-outside-kind-list / C102 / C104 / C103 examples); I8 also updated to reflect §5.3.5 v3 lock table (to_string only for eq binding to unbound var, not blanket). Status stays `draft` pending v5 re-review. User indicated this should be the final round before scoped. |
| 2026-05-23 | draft | Step 4.2 v6 tightening | User v5 re-review verdict: no Blockers, 3 Required current-text residuals all rooted in stale "adapter trusts upstream" wording surviving in three header / §2 sections. P1 header Outputs line 18 still said `_vars_in_atom` aggregate-aware with "correlated outer vars only" — v1/v2 stale; rewrote to explicit "aggregate operand contributes ZERO outer-var" + new `_infer_var_type_domains` line documenting aggregate-filter recursion as separate concern. P2 §2.4 filter-kind restriction bullet (line 106) said "T2.3a substrate validator upstream already rejects these, so Souffle adapter trusts the IR shape" — contradicts v4/v5 §5.7.5 Layer 1 lock; rewrote to explicit structural enforcement at adapter regardless of gate state (with rationale: `_ARITH_KINDS` would emit var-binding clauses Souffle aggregate body slots cannot accept; nested aggregate would recurse undefined) + cross-ref to §5.7.5 Layer 1/Layer 2 split. P3 Non-goal "Nested aggregate" bullet (line 282) said adapter trusts upstream — rewrote to "adapter rejects nested aggregate as structural invalid input at `_validate_atom_subset` regardless of gate state; substrate also rejects upstream when gate ON (defense-in-depth); adapter is only safety net when gate OFF". Status stays `draft` pending v6 re-review. |
| 2026-05-23 | scoped | Status: draft → scoped | User v6 re-review verdict: **PASS — 0 Blocker / 0 Required / 0 Minor**. Convergence reached after 6 Step 4.2 tightening rounds (v1: 2B + 4R; v2: 0B + 5R; v3: 0B + 5R; v4: 0B + 2R; v5: 0B + 3R; v6: 0B + 0R). All algorithm + contract decisions locked across header / §2 / §3 Non-goals / §4 Current Context / §5 Proposed Shape / §5.3.5 wrapper table / §5.7.5 Layer 1/Layer 2 split / §6 invariants I1-I11 / §7 21+ acceptance tests with discriminator design / §8 Implementation Plan / §9 mandatory docs. Anti-pattern audit (v6) cleared all stale "adapter trusts upstream" instances. Sacred `master` untouched. Dirty set preserved. Ready for impl branch fork. |

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
- **G2** — Blueprint §4.1 documents G2 source-grep audit on `src/factgraph/adapters/souffle/`(`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate"` → 0 hits;P3 v2 corrected dispatch path note:aggregate-in-cmp reaches `_literal_to_text` via cmp side compile,not top-level atom dispatch)。T2.3a substrate visibility verified at `where_ast.py:75` + `:102` + `where_ast_validate.py`。T2.3b SDK lowering output verified at `sdk/dsl/expr.py:209` + `:459` + bridge validator gate。
- **G3** — Blueprint §4.2 uses file:line citations(where_compile.py:20/434-626/506-512/561-567/679-731/829-861/905-908/1060-1103/1139-1173/1176);v3 P2 adds `:829-861` `_infer_var_type_domains` to touch points。Citations to be re-verified at row-drafting / impl time per CADENCE Rule 1。
- **G4** — Blueprint §2 sub-goals 2.1-2.9 each labeled with C-number(C99/C100/C101/C104)or specific responsibility(dispatch extension / helper / cmp side extension / filter atom recursion / var extraction / type domain inference [v3 §2.6b] / validation / acceptance / G7)。
- **G5** — Blueprint §3 Non-goals lists 11 explicit deferrals or out-of-scope items with rationale(T2.3.d ProbLog / PyReason / T2.3a substrate change / T2.3b SDK change / Nit aggregate-in-arith / nested aggregate / new kinds / new filter atoms / witness layout / Souffle mean derived fallback / M-class doc)。**v2 supersedes** v1 "AggregateNoValue Souffle DL sentinel" non-goal — replaced by §3 row "Souffle DL sentinel object for AggregateNoValue" with v2 lock(no separate sentinel;branch-not-firing represents NoValue per §2.5)。
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
  6. **Souffle end-to-end smoke**(P3 v2-corrected wording) — `build_application_rule(...)` with `agg_sum(...)` example produces IR that current Souffle adapter rejects via `WhereValidationError("unsupported literal type")` at `_literal_to_text` line 1106-1113(aggregate tuple reaches via cmp side compile path,not via top-level atom kind dispatch);confirms precondition gap T2.3c fills

### 2026-05-23 — User's Step 4.2 review focus areas (anticipated upfront — v3 status annotations)

Drafter anticipated user's Step 4.2 review would focus on:

1. **Souffle DL syntax correctness** — particularly `mean` native support claim. Parent essay line 1711 claims native;blueprint §4.3 backs with Souffle 2.x reference but no project-level Souffle version pin found in `pyproject.toml` / installation docs. If reviewer doubts `mean` support,decision options:(a)trust parent essay,verify at impl;(b)defer `mean` to a sub-slice;(c)derive `mean` as `sum/count` upfront。Drafter leans (a) with (A-fallback) deviation path documented in §10 Outcome at closure if impl reveals incompatibility。 **[Status: not surfaced in v1/v2 review;still applies at impl-time]**
2. ~~Aggregate-local var isolation algorithm in `_vars_in_atom`~~ — **SUPERSEDED by v2 P1 Blocker**:v1 §5.5 "simplification"(return all filter vars,let upstream filter)was based on false assumption about `extract_where_variables`(which directly unions,does NOT filter)。User v1 review surfaced this as P1 Blocker;v2 corrected to aggregate-side-contributes-ZERO algorithm。v3 P1 fixed stale §2.6 v1 algorithm text。
3. ~~`AggregateNoValue` Souffle semantic gap~~ — **SUPERSEDED by v1 P0 Blocker**:user locked direction A(implement empty-set guard now via `count > 0` prefix on min/max/mean)。v2 §2.5 fully rewritten with guard algorithm;no sentinel object;branch-not-firing represents NoValue per C101 semantics。
4. **Filter atom compile factoring** — §5.3 proposes a separate `_compile_filter_atom_within_aggregate` function;alternative is extending `_compile_atom` with a `within_aggregate=True` flag。Reviewer may prefer the flag-extension approach for less code duplication。Drafter neutral;impl can pick cleaner factoring。 **[Status: not surfaced in v1/v2 review;still impl-time decision]**
5. **`_AGGREGATE_KINDS` import vs adapter-local mirror** — §5.1 prefers import from substrate(single source of truth);some lint rules forbid underscore-prefix cross-module imports。If lint complains,fallback to adapter-local mirror with explicit invariant check。Reviewer may want lock-down on choice upfront。Drafter rationale:try import first;fallback only if lint forces it。 **[Status: not surfaced in v1/v2 review;still applies at impl-time]**

### 2026-05-23 — Anticipated reviewer P-finding candidates

Drafter anticipated these at v1 draft;v3 status annotations below:

- ~~Souffle DL aggregate result `to_string(...)` wrap~~ — **SUPERSEDED by v3 P3 lock**:the `to_string(...)` wrap decision is now precisely locked in blueprint §5.3.5 v3 wrapper table covering 8 caller-context combinations。`_compile_aggregate` returns bare numeric;caller(eq branch / cmp branch)decides wrap based on §5.3.5 table。If Souffle aggregator return type still requires impl-time verification,§8 step 11 Souffle binary smoke covers it。
- ~~Test 7.5 isolation discriminator strength~~ — **SUPERSEDED by v2 P2 fix**:v1 `("pred", "user:exists", ["$o"])` did not discriminate(pred always binds);v2 replaced with `("ne", "$o", "blocked")` per reviewer suggestion(`ne` requires lhs pre-bound per `where_compile.py:888-893`);v2 §7.5 uses explicit `assertRaises(WhereValidationError)`。Concern resolved。
- ~~`_vars_in_atom` simplification target_var exclusion~~ — **SUPERSEDED by v2 P1 fix + v3 P1 fix**:v1/v2 stale "walk filter + exclude target_var" algorithm was based on false assumption about `extract_where_variables`(direct union,not filter)。v2 §5.5 rewritten to "aggregate side contributes ZERO outer vars";v3 §2.6 brought into alignment(v1 stale text removed)。Target_var collision concern no longer applies — `$_agg<N>` SDK convention locked in §6 invariant I11 v3。
- **Filter `not` body recursion depth** — §5.3 recurses into filter atoms;`not` body itself contains pred atoms。Compile path may need to handle `_compile_not_body_atom`(line 939)precedent or compile not-body inside aggregate manually。Drafter may need to clarify or push to §8 step 6 impl detail。**[Status: not surfaced in v1/v2/v3 review;still impl-time decision]**

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
| T2.3b Aggregate SDK + bridge | 5 helpers + `_AggregateRef` + DSL→IR lowering + bridge validator gate unchanged | 0 diff in `sdk/dsl/expr.py` / `sdk/dsl/application_rule.py` / `sdk/dsl/__init__.py` / `sdk/docs/04_api_surface.en.md`;**`sdk/docs/03_rules_and_inferences.en.md` §3.2 adapter status row MUST flip per P4 v2 lock**(rest of file 0 diff)|

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

### 2026-05-23 — Step 4.2 v1 review findings + v2 resolutions

User Step 4.2 v1 re-review surfaced 2 Blockers + 4 Required across §1 / §2.5 / §5.5 / §5.6 / §7 / §9。Direction confirmed acceptable;tightening required before scoped。

**P0 Blocker — C101 empty-set semantics conflict**(blueprint §2.5)

User flagged that v1 §2.5 deferring `AggregateNoValue` semantic gap to follow-up violates parent essay C101 lock("comparison violated / no env pollution" is a closed-decision,not a deferral candidate)。Listed 3 resolution options:(a)implement empty guard now,(b)narrow scope to count/sum,(c)escalate to M-class decision。

User locked **(a) Implement empty-set guard now** with reasoning:
- C unnecessary — C101 already decided;not a pending decision
- B creates half-finished semantics — T2.3a/T2.3b already exposed 5 kinds;partial Souffle support complicates state table and downstream docs/acceptance
- A still S-class — adapter-internal lowering only;no public API / substrate / SDK touch

**Locked algorithm shape**(blueprint §2.5 v2):
- `count` / `sum`:empty=0 is legal C101 value → emit aggregate directly,no guard
- `min` / `max` / `mean`:compile MUST prefix `count : { same_body } > 0,` guard clause → empty body → guard fails → branch does not fire → matches C101 "violated comparison / no env pollution"。No separate Souffle sentinel object。
- `AggregateNoValue` represented by **rule branch not firing**(branch-not-fire = no query row emitted = no env to pollute)

Acceptance §7.8 added 3 DL emit-shape discriminator tests(min binding / max cmp / mean binding)+ §7.9 1 optional runtime integration test(empty set → no query row)+ test 7.8(d)symmetric negative discriminator(count/sum must NOT have guard)。

**P1 Blocker — `_vars_in_atom` scope model was false**(blueprint §5.5)

User verified `where_compile.py:188-195` `extract_where_variables` directly unions `_vars_in_atom` results — does NOT filter against outer scope。v1 §5.5 "simplification" of returning all aggregate filter vars would leak `$o` / `$_agg1` into query variables AND witness layout(via `build_query_witness_layout` line 217-237)。

**v2 fix**(blueprint §5.5):aggregate side of cmp atom contributes **ZERO** outer vars to `_vars_in_atom`。Correctness argument:
1. Correlated outer vars are bound by their original outer atom(per C104),which contributes them independently — ignoring the aggregate-filter reference does not lose them
2. Aggregate-local vars(target_var + filter-introduced)are private per C104 — MUST stay out of query vars / witness layout
3. Result-binding var(`$total` from `("eq", "$total", aggregate)`)is captured by the existing non-aggregate-side branch

Test §7.5 strengthened with explicit `extract_where_variables(...) == ["$total", "$u"]` assertion(aggregate-local `$o`/`$_agg1` MUST NOT appear)。

**P2 Required — §7.5 discriminator did not discriminate**(blueprint §7.5)

User flagged that `("pred", "user:exists", ["$o"])` would bind `$o` regardless of leak state(pred always binds new vars at `where_compile.py:466`),so the test would pass even if isolation was broken。

**v2 fix**(blueprint §7.5):replaced with `("ne", "$o", "blocked")` per user suggestion。`ne` requires lhs var to be already-bound(`where_compile.py:888-893`)so test now discriminates:if `$o` leaked into outer `bound_vars`,compile succeeds(test FAILS);if isolated,compile raises `WhereValidationError`(test PASSES via `assertRaises`)。

**P3 Required — current failure-path cite was wrong**(blueprint §1 + §5.6 G7 #6)

User verified the actual error is `WhereValidationError("unsupported literal type")` at `_literal_to_text` line 1106-1113,not "unsupported atom kind" at line 731。Aggregate tuple inside cmp atom reaches `_literal_to_text` via cmp side compile path because the tuple is neither bool/int/str。

**v2 fix**(blueprint §1 + §5.6 G7 #6 + audit log G7 #6 above):updated wording to reflect actual failure path。Note added in §1 explicitly correcting v1's incorrect "line 731 unsupported atom kind" claim。

**P4 Required — SDK docs update was optional**(blueprint §9)

User noted `sdk/docs/03_rules_and_inferences.en.md` §3.2 currently has row "Souffle adapter | Deferred to T2.3.c"(shipped in T2.3b archive `4e3176d2`)。If T2.3c does not flip this row,the docs become stale immediately upon ship。

**v2 fix**(blueprint §6.1 + §8 step 10 + §9):both docs updates MANDATORY in T2.3c。Specific row content locked in §9。

**P5 Required — adapter fallback validation needed gate-off behavior**(blueprint §2.7)

User flagged `FACTPY_WHERE_AST_VALIDATE=0` gate-off path:upstream T2.3a substrate validator skipped → malformed aggregate IR can reach Souffle adapter without semantic guard。Existing T2.1/T2.2 adapters have gate-off fallback patterns。

**v2 fix**(new blueprint §5.7.5 + new §6 invariant I10):adapter-side aggregate shape validation(`_validate_atom_subset`)is mandatory regardless of gate state。Locked checks:
- Aggregate kind ∈ `_AGGREGATE_KINDS`
- Tuple arity == 3
- `target_var` shape per kind(None for count,$-prefixed otherwise)
- `filter_atoms` is list;each recurses
- Nested aggregate rejected

Semantic-only checks(C100 filter restriction,C102 numeric target,C104 binding-order scoping)remain upstream-only — adapter does NOT re-implement(if gate OFF user is explicitly opting out of semantic validation)。

Acceptance §7.10 added 2 tests verifying adapter rejects unknown kind both with gate ON and OFF。

### 2026-05-23 — Cross-flip inversion v1→v2 retrospective

v1 review surfaced 6 findings(2 Blockers + 4 Required)— consistent with T2.3b's v1 round count(1 Blocker + 3 Required = 4 findings)。Cross-flip inversion blindness(Claude drafts,user reviews)remains a real cost:

- **P0** was a semantic misjudgment(deferring instead of solving)— drafter assumption ("Python eval path is source-of-truth so Souffle can deviate")did not survive parent essay re-read at reviewer time。**Pattern**:when drafter encounters semantic divergence,default to honoring the locked design,not deferring。
- **P1** was a code-reading miss(drafter did not re-read `extract_where_variables` carefully enough to notice the direct union)— even though `extract_where_variables` was cited in §G3,the drafter relied on memory of "upstream filters" rather than re-reading the actual implementation。**Pattern**:cited code MUST be re-read at row-drafting time per CADENCE Rule 1。
- **P3** was a copy-paste error(drafter assumed line 731 fallback fires without verifying the dispatch path that aggregate-in-cmp follows)— v1 G7 #6 was speculative not empirical。**Pattern**:G7 preconditions MUST be reproducible by reviewer in their own re-read,not just drafter's claim。

v2 mitigation:explicit user-verified P3 reproduction;explicit cited-line citations for P1 fix(`where_compile.py:188-195` extraction;`:217-237` witness layout);explicit algorithm walkthrough for P0(no "deferred" wiggle-room)。

If v2 review still surfaces Blocker-class findings,that signals cross-flip inversion pattern's overhead exceeds value for adapter-shaped slices — future T2 Track adapter slices(T2.3.d ProbLog)should consider reverting to user-drafts pattern。

### 2026-05-23 — Step 4.2 v2 review findings + v3 resolutions

User Step 4.2 v2 re-review verdict:**still not ready for scoped**。P0 direction correct;P1-P5 v2 main fixes landed;but 5 contract-precision gaps remain that would surface at impl time。

**P1 Required — §2.6 retained v1 stale algorithm**(blueprint line 152-175)

§2.6 v1 wrote `outer_var_universe` + `referenced_vars & outer_var_universe` intersection — based on the false assumption(P1 v1 Blocker)that `extract_where_variables` filters against outer scope。v2 §5.5 was rewritten correctly but §2.6 was not updated,leaving contradictory specifications。Impl reading §2.6 would write wrong algorithm。

**v3 fix**:§2.6 rewritten to align with v2 §5.5 truth — aggregate side contributes ZERO outer vars;correlated outer vars are bound by their original outer-scope atom independently。Explicit "v1/v2 wrong algorithm removed" note in §2.6 header。

**P2 Required — `_infer_var_type_domains` aggregate coverage gap**(blueprint §2.6b new + §6 I11 new + §7.11 new)

`where_compile.py:829-861` `_infer_var_type_domains` only scans top-level `pred` / `_ARITH_KINDS` / `not`。It does NOT descend into cmp atom operands or aggregate filter atoms。Concrete gap:if aggregate filter contains numeric compare like `gt($_agg1, 5)` after `pred order:amount($o, $_agg1)`,the type domain for `$_agg1` is NOT inferred(pred is inside aggregate filter,not at top level)。Subsequent `_assert_cmp_var_allowed` call for the `gt` would see `$_agg1` with no/unknown type and raise unexpectedly。

**v3 fix**:
- New blueprint §2.6b documents the gap + algorithm extension(walk aggregate filter atoms recursively + explicit `target_var` int classification per C102)
- New §6 invariant I11:aggregate-local var naming(`$_agg<N>` prefix per T2.3b SDK convention)to avoid name collision in flat type domain dict
- New §7.11 acceptance(2 tests):type domain inference includes aggregate target_var + filter-internal numeric cmp compiles without "unknown type" error

**P3 Required — to_string/to_number boundary not precisely locked**(blueprint §5.3 return shape note + new §5.3.5 + §7.8 expanded)

§5.3 originally said `_compile_aggregate` returns aggregate expression but §7.8 expected `to_string(...)` wrap for binding。Inconsistent guidance on where to apply `to_string` vs `to_number` would cause impl to guess at the symbol/numeric domain boundary。

**v3 fix**:
- §5.3 return shape clarified — `_compile_aggregate` returns **bare numeric aggregate expression**(no wrap);wrapping decision moves to call site
- New §5.3.5 lock table covers 8 combinations:eq binding vs eq filter vs numeric cmp,each paired with var(bound/unbound)/ literal / aggregate operand
- Eq binding to unbound var:`v_X = to_string(<agg_expr>)` symbol binding(matches `_compile_arith_atom:1103` precedent)
- Eq filter with bound var:`<agg_expr> = to_number(v_X)` numeric eq
- Numeric cmp(gt/ge/lt/le/ne):raw numeric `<agg_expr> <op> <other>`
- §7.8 expanded from 3 tests to 4 + negative test (e);test (b) and (d) discriminate the `to_string` vs `to_number` boundary

**P4 Required — §6.2 self-contradiction**(blueprint §6.2 narrowed)

§6.1 listed `sdk/docs/03_rules_and_inferences.en.md` as MUST change(P4 v2 lock)。§6.2 broad invariant "src/factgraph/sdk/docs/ — 0 diff" contradicted this。

**v3 fix**:§6.2 narrowed — `sdk/docs/04_api_surface.en.md` stays 0 diff;`sdk/docs/03_rules_and_inferences.en.md` is 0 diff EXCEPT §3.2 adapter status row(which MUST flip)。Other sdk/docs files explicit case-by-case if added later。

**P5 Required — audit log G1-G7 + Anticipated reviewer P-findings retained v1 stale**(audit log line 59 + 81)

Audit log G5 description still listed "AggregateNoValue Souffle DL sentinel" as Non-goal — superseded by v2 §3 row "Souffle DL sentinel object for AggregateNoValue" reframe(no separate sentinel;branch-not-firing represents)。Anticipated reviewer P-findings section #2 + #3 still presented v1 framing without marking superseded by v2 review。Since these sections describe current G1-G7 mapping(not historical event log),they should reflect v3 truth。

**v3 fix**:
- G5 description rewritten:11 non-goals(was 12);"AggregateNoValue Souffle DL sentinel" removed and replaced with v2 reframe explicitly marked
- Anticipated reviewer P-findings #2 + #3 marked **SUPERSEDED** with cross-ref to v1/v2 review outcome;remaining #1/#4/#5 retain "not surfaced in v1/v2;still impl-time decision" annotation

### 2026-05-23 — Cross-flip inversion v2→v3 retrospective

v3 round surfaced **5 Required(no Blockers)** — improvement from v2 round(2 Blockers + 4 Required = 6 total)。Trend suggests cross-flip inversion drafter blindness compounds across multiple rounds but converges:

| Round | Blockers | Required | Total | Pattern |
|---|---|---|---|---|
| v1 | 2 | 4 | 6 | Semantic misjudgment + scope model false + cite wrong + scope optionalism |
| v2 | 0 | 5 | 5 | Contract-precision gaps surface only after big-picture is correct |
| (v3 prediction) | 0 | 0-2 | 0-2 | Should converge if v3 fixes are tight |

**Lesson for future cross-flip-inverted drafts**:
- Big-picture errors(P0 v1 type)dominate first round
- Mid-precision errors(P1-P5 v1 type)dominate second round
- Contract-precision gaps(v2 P1-P5 type — stale specs,helper coverage gaps,wrapper rules,invariant contradictions,gate mapping drift)dominate third round
- Drafter mitigations:explicit superseded-marking when rewriting sections;cross-section consistency check before each commit;helper coverage diff vs touched-file enumeration

v3 mitigation applied:every v3 edit cross-verified against §5(impl) ↔ §2(goals) ↔ §6(invariants) ↔ §7(acceptance) ↔ audit log G1-G7 for consistency。If v3 review still surfaces Blocker-class,the cross-flip inversion pattern's overhead clearly exceeds value for adapter-shaped slices and T2.3.d should revert to user-drafts pattern。

### 2026-05-23 — Step 4.2 v3 review findings + v4 resolutions

User Step 4.2 v3 re-review verdict:**still requires v4 tightening, but converging — no Blockers**。5 Required findings spanning contract/text consistency and one gate-off semantic boundary。

**P1 Required — gate-off C100 contract self-contradiction in §5.7.5**

§5.7.5 had two contradictory statements:table listed "Filter atom kind ∈ C100 list — YES with gate ON — defense-in-depth" while narrative said "C100 filter restriction — substrate validator enforces (NOT in adapter)"。User locked:aggregate filter kind restriction is **structural** at adapter,not semantic — `_ARITH_KINDS` top-level atoms compile to var-binding clauses which Souffle aggregate body slots cannot accept;adapter MUST reject regardless of gate state。

**v4 fix**:§5.7.5 reorganized into two explicit Layers:
- Layer 1(structural,MANDATORY regardless of gate):aggregate kind in `_AGGREGATE_KINDS` / tuple arity / target_var shape / filter_atoms list / recursive shape / no nested aggregate / **filter atom kind ∈ C100 list**(promoted from "defense-in-depth" to "structurally required because compile path itself cannot proceed otherwise")
- Layer 2(semantic,upstream-only):C100 *outside* kind-list constraint(RuleRef object semantics / RuleExpr nesting at AST layer)/ C102 numeric runtime type / C104 binding-order scoping / C103 snapshot semantics

Added rationale paragraph explaining why `_ARITH_KINDS` in aggregate filter is structurally undefined(emits `<z> = to_string(<expr>)` var-binding clause,not Souffle aggregate body slot-compatible clause)。

**Acceptance §7.10b added(2 tests)**:gate ON + ArithExpr in aggregate filter → raises;gate OFF + ArithExpr in aggregate filter → raises with SAME error message(adapter is only safety net)。Without v4 P1 lock,gate-off would let `add`/`sub` reach `_compile_filter_atom_within_aggregate` and either crash on dispatch or emit malformed DL。

**P2 Required — §8 Implementation Plan step 5 stale**

§8 step 5 still wrote "Extend `_vars_in_atom` cmp branches to walk aggregate filter atoms;explicitly exclude target_var" — v1/v2 stale algorithm contradicting v3 §5.5(aggregate side contributes ZERO outer vars)。Impl reading §8 would write wrong algorithm。

**v4 fix**:§8 step 5 split into:
- step 5:`_vars_in_atom` aggregate operand → ZERO outer var contribution(no walk;per §5.5 v2 + §2.6 v3)
- step 5b:`_infer_var_type_domains` aggregate filter recursion(separate concern;per §2.6b v3 P2)

Separation of concerns made explicit:`_vars_in_atom` tracks outer-scope membership(query variable set);`_infer_var_type_domains` tracks value types for cmp safety。Different algorithms,different consumers,different responsibilities。

**P3 Required — §8 step 12 Outcome wording stale**

§8 step 12 said closure should document "the `AggregateNoValue` empty-set gap" — v2 lock A eliminated the gap(guard implements branch-not-firing = C101 "violated comparison")。Stale language。

**v4 fix**:§8 step 12 reworded — "empty-set guard implementation status + any Souffle syntax/runtime deviations discovered at impl-time(particularly `mean` aggregator support if version-pinned)"。

**P4 Required — §2.5 premature confirmation claim**

§2.5 line 146 said "Confirmed at Step 4.7 impl-time round-trip test against Souffle binary" — Step 4.7 has not happened;claim is forward-looking,not factual。

**v4 fix**:flipped to future tense — "Verification requirement(P4 v4 wording — future tense,not yet confirmed)" + "MUST be verified at Step 4.7" + explicit (A-fallback) deviation path if Souffle parse rejects the conjunction pattern。Cross-ref to §8 step 11 Souffle binary smoke。

**P5 Required — audit log Anticipated reviewer P-findings + cross-slice table stale**

Audit log Anticipated reviewer P-findings #1 (`to_string` wrap concern), #2 (test 7.5 `pred` discriminator), #3 (`_vars_in_atom` target_var exclusion) still presented v1 framing without superseded markers despite v2/v3 fixes addressing each。Cross-slice contract preservation table still had broad "`sdk/docs/` 0 diff" claim contradicting §6.2 v3 narrowing。

**v4 fix**:
- Anticipated #1 / #2 / #3 marked **SUPERSEDED** with explicit v2/v3 fix cross-refs;#4(filter `not` body recursion)retained "not surfaced in v1/v2/v3 review;still impl-time decision" status
- Cross-slice T2.3b row narrowed:`sdk/docs/04_api_surface.en.md` stays 0 diff;`sdk/docs/03_rules_and_inferences.en.md` §3.2 row MUST flip per P4 v2 lock(rest of file 0 diff)

### 2026-05-23 — Cross-flip inversion v3→v4 retrospective

v4 round surfaced **5 Required(no Blockers)** — exactly as v3 prediction lower bound suggested(predicted 0-2 Required;actual 5 Required is still in convergence trajectory but slightly above prediction)。Updated pattern:

| Round | Blockers | Required | Total | Pattern |
|---|---|---|---|---|
| v1 | 2 | 4 | 6 | Big-picture(semantic / scope model / cite / docs) |
| v2 | 0 | 5 | 5 | Contract-precision(stale specs / helper gaps / wrappers / invariant contradictions / gate mapping drift) |
| v3 | 0 | 5 | 5 | Text consistency(impl plan stale / Outcome stale / future-tense confusion / gate-off semantics edge / audit log stale anticipated) |
| (v4 prediction) | 0 | 0-1 | 0-1 | Should converge if v4 mitigations hold |

v3-to-v4 lesson:**section-level rewrites need to propagate through ALL referencing sections**(§5 / §6 / §7 / §8 / audit log)— v3 fixed §2.6 + §5.5 but missed §8 step 5(P2 v4);v3 added §5.3.5 wrapper lock but missed audit log Anticipated #1 stale(P5 v4)。Rewrite-and-propagate discipline:after editing any §N section,grep blueprint for cross-references to §N's old content + update。

v4 mitigation applied:every v4 edit cross-verified against §1 / §2 / §5 / §6 / §7 / §8 / §9 / audit log for stale references。Implementation Plan §8 + audit log Anticipated section explicitly cross-checked for stale v1/v2/v3 specs。If v4 review still surfaces Blocker-class,cross-flip inversion overhead clearly exceeds value;T2.3.d should revert to user-drafts。If v4 review surfaces zero Required,convergence reached and v4 ready for scoped anchor。

### 2026-05-23 — Step 4.2 v4 review findings + v5 resolutions

User Step 4.2 v4 re-review verdict:**no Blockers, 2 Required text/contract residuals — final convergence**。User explicitly indicated this should be the final round before scoped。Trend exactly matched v4 prediction(0 Blockers + 0-1 Required;actual 2 Required slightly above prediction)。

**P1 Required — §4.2 touch-point `_vars_in_atom` description stale**(blueprint §4.2 line 317)

Touch-point line said "T2.3c extends `_vars_in_atom` to walk aggregate filter atoms(correlated outer vars only)" — v1/v2 stale algorithm contradicting v3 §5.5 + v4 §8 step 5。Current Context / G3 cited touch-point must reflect current truth at scoped time。

**v5 fix**:
- §4.2 `_vars_in_atom` line rewritten:"aggregate operand contributes ZERO outer vars(per §5.5 v2 + §2.6 v3);correlated outer vars bound by their original outer-scope atom independently;aggregate-local vars stay private per C104"
- §4.2 added new line for `_infer_var_type_domains(...)` at `where_compile.py:829-861` documenting:type domain inference recursion into aggregate filter atoms,mark target_var as int per C102,separate concern from `_vars_in_atom`(different consumer / different algorithm)

**P2 Required — §6 invariants I5/I10 weak adapter responsibility**(blueprint §6 invariants)

I5 said "filter kinds restricted to C100 list;T2.3a substrate enforces upstream,Souffle adapter trusts" — contradicting v4 §5.7.5 Layer 1 lock。I10 said "C100 semantic restrictions deferred to upstream substrate validator(adapter does NOT re-implement)" — same contradiction。Both invariants weakened the adapter's mandatory gate-off responsibility for filter kind-list enforcement。

**v5 fix**:
- **I5 rewritten** to explicitly state adapter enforces filter kind list inside aggregate filter regardless of `FACTPY_WHERE_AST_VALIDATE` gate state(P1 v4 lock — `_ARITH_KINDS` in aggregate filter is structurally undefined,not just semantically violated;Souffle aggregate body slot cannot accept var-binding clauses from arith atoms)。T2.3a substrate also enforces as semantic check when gate ON;adapter is defense-in-depth + only safety net when gate OFF。
- **I10 rewritten** to mirror §5.7.5's two-layer structure explicitly:
  - Layer 1(structural,mandatory regardless of gate):aggregate kind ∈ `_AGGREGATE_KINDS` / tuple arity / target_var shape / filter_atoms list / recursive shape / no nested aggregate / **filter atom kind ∈ C100 list per I5**
  - Layer 2(deeper semantic checks deferred upstream-only):C100 semantics OUTSIDE kind-list constraint(RuleRef object semantics / RuleExpr nesting at AST layer)/ C102 runtime numeric / C104 binding-order / C103 snapshot
- **I8 also updated**(consistency with §5.3.5 v3 lock table):`to_string(...)` wrap only for eq binding to unbound var(symbol-domain target);numeric cmp / eq filter / aggregate-vs-aggregate paths leave aggregate raw numeric。Original I8 wording was overly broad ("Souffle DL wraps with `to_string(...)` for symbol-typed outer var binding consistency")— now precise per §5.3.5 table。

### 2026-05-23 — Cross-flip inversion v4→v5 retrospective (final round)

v5 round surfaced **2 Required(no Blockers)** — exactly within v4 prediction trajectory(predicted 0-1;actual 2 still in convergence)。Updated final pattern:

| Round | Blockers | Required | Total | Pattern |
|---|---|---|---|---|
| v1 | 2 | 4 | 6 | Big-picture(semantic / scope model / cite / docs) |
| v2 | 0 | 5 | 5 | Contract-precision(stale specs / helper gaps / wrappers / contradictions / drift) |
| v3 | 0 | 5 | 5 | Text consistency(impl plan stale / Outcome stale / future-tense confusion / gate-off semantics edge / audit log stale anticipated) |
| v4 | 0 | 2 | 2 | Current-Context cite stale + invariant weakening contradicting Proposed Shape |

**5-round total**:2 Blockers + 16 Required = 18 findings across 5 rounds for a single S-class adapter blueprint。Cost analysis:

| Cost | Quantity |
|---|---|
| Drafter rounds | 5 amendments(v1 + v2 + v3 + v4 + v5)|
| Reviewer rounds | 4 reviews(v1 → v2 / v2 → v3 / v3 → v4 / v4 → v5)|
| Total commits | 5 amendment commits(c34e73a6 was T2.3b;here:5971669f / 105a2cb4 / 9ebd9654 / f620a54f / (v5 pending))|
| Total blueprint LOC | 560 → 1033+ → eventually scoped |
| Total audit log LOC | 128 → 369+ → eventually scoped |

**Lesson for T2.3.d**:cross-flip inversion(Claude drafts,user reviews)on adapter-shaped slices accumulates 4-5 rounds of tightening to reach convergence。This is **significantly higher cost** than the user-drafts pattern's 0-1 round Step 4.2(T2.2 / fixture cleanup / T2.3a all had clean Step 4.2 drafts)。**T2.3.d should revert to user-drafts pattern**(per audit log retrospective lesson recorded across v2/v3/v4 rounds + final confirmation here)。

**Convergence success criterion for v5**:if v5 review surfaces zero Required findings,scoped anchor proceeds and the cross-flip inversion experiment closes with a documented cost-value analysis。If v5 surfaces another Required,we should escalate to a meta-decision:abandon T2.3.c blueprint and re-draft via user-drafts pattern,or accept N=6 rounds as the new ceiling for cross-flip inversion overhead。

### 2026-05-23 — Step 4.2 v5 review findings + v6 resolutions

User Step 4.2 v5 re-review verdict:**no Blockers, 3 Required current-text residuals**。All 3 rooted in the same anti-pattern:"adapter trusts upstream"/"substrate validator upstream already rejects" wording surviving in header / §2 sections that describe current truth — contradicting v4/v5 §5.7.5 Layer 1 structural lock。

**P1 Required — header Outputs line 18 stale `_vars_in_atom` semantics**

Outputs line still wrote `_vars_in_atom` "aggregate-aware extension(correlated outer vars only;aggregate-local vars stay private per C104)" — v1/v2 stale framing contradicting v3 §5.5 + v5 §4.2 + v5 I6。

**v6 fix**:
- Outputs line rewritten:"`_vars_in_atom` aggregate operand contributes **ZERO** outer-var(query-variable set unaffected;correlated outer vars contributed by their original outer-scope atom independently;aggregate-local vars stay private per C104)"
- Added new Outputs line for `_infer_var_type_domains` aggregate-filter recursion documenting it as separate concern from `_vars_in_atom`(different consumer / different algorithm,per §2.6b)
- `_validate_atom_subset` Outputs line annotated "structural,mandatory regardless of `FACTPY_WHERE_AST_VALIDATE` gate state"

**P2 Required — §2.4 filter-kind restriction said adapter trusts upstream**(blueprint §2.4 line 106)

§2.4 bullet read:"Per C100,filter atom kinds restricted to pred / eq / ne / gt / ge / lt / le / in / **not**(no Rule reference / no RuleExpr / no nested aggregate / no ArithExpr — but T2.3a substrate validator upstream already rejects these,so Souffle adapter trusts the IR shape)" — directly contradicting v4/v5 §5.7.5 Layer 1 structural lock。

**v6 fix**:§2.4 bullet rewritten to:
- Explicit structural enforcement at adapter regardless of gate state(v4/v5 lock)
- Rationale spelled out:`_ARITH_KINDS` would emit var-binding clauses Souffle aggregate body slots cannot accept;nested aggregate would recurse undefined
- T2.3a substrate validator also enforces semantically when gate ON(defense-in-depth);adapter is only safety net when gate OFF
- Deeper semantic checks(RuleRef object shape / RuleExpr AST nesting / C102 runtime / C104 binding-order)remain upstream-only per §5.7.5 Layer 1 / Layer 2 split

**P3 Required — Non-goal "Nested aggregate" said adapter trusts upstream**(blueprint §3 line 282)

§3 Non-goal bullet read:"Nested aggregate — T2.3a validator rejects upstream;Souffle adapter trusts upstream" — contradicts v4/v5 §5.7.5 Layer 1 lock(nested aggregate IS rejected at adapter structurally,not just upstream)。

**v6 fix**:Non-goal bullet rewritten:
- "Nested aggregate support — out of scope for ANY future expansion in T2.3c"(scope clarification preserved)
- "Adapter rejects nested aggregate(aggregate appearing inside another aggregate's filter)as structural invalid input at `_validate_atom_subset`(mandatory regardless of gate state per §5.7.5 Layer 1 / I10 v5)"
- "T2.3a substrate validator also rejects upstream when gate ON(defense-in-depth)。Adapter is only safety net when gate OFF"

### 2026-05-23 — Cross-flip inversion v5→v6 retrospective (post-final-round)

v6 round surfaced **3 Required(no Blockers)** — exceeded v5 prediction(predicted 0)。Updated final pattern:

| Round | Blockers | Required | Total | Pattern |
|---|---|---|---|---|
| v1 | 2 | 4 | 6 | Big-picture |
| v2 | 0 | 5 | 5 | Contract-precision |
| v3 | 0 | 5 | 5 | Text consistency(impl plan / Outcome / future-tense / gate-off edge / audit anticipated) |
| v4 | 0 | 2 | 2 | Touch-point cite + invariant weakening |
| v5 | 0 | 3 | 3 | Header Outputs + §2.4 bullet + §3 Non-goal bullet — same "adapter trusts upstream" anti-pattern surviving across 3 sections |

**5-round cumulative**:2 Blockers + 19 Required = 21 findings(updated from v5's "18")。

**v5→v6 lesson**:**anti-pattern propagation outlives section-level rewrites**。The "adapter trusts upstream" framing was the v1/v2 simplification;v4 §5.7.5 corrected the core lock but the same anti-pattern survived in 3 other places(header Outputs / §2.4 / §3 Non-goal)— all describing current truth,all using stale framing。This is **deeper than rewrite-and-propagate**(v3→v4 lesson):it's **anti-pattern audit across all section types**(header / Goals / Non-goals / Current Context / Proposed Shape / Invariants / Acceptance / Impl Plan / Docs)。

**v6 mitigation applied**:grep blueprint for residual "adapter trusts" / "substrate validator upstream already" / "Souffle adapter trusts" phrases — all 3 instances fixed。Anti-pattern audit pass added to v6 mitigation discipline。

**Convergence success criterion for v6**:if v6 review surfaces zero Required findings,scoped anchor proceeds — but cost-value analysis already conclusive:**6 rounds for a single S-class adapter blueprint is significantly higher than the user-drafts pattern's 0-1 round baseline**。T2.3.d MUST revert to user-drafts pattern(no longer a "should consider";now a hard recommendation locked across 5+ retrospectives)。

**If v6 still surfaces Required**:escalate to abandon-T2.3.c meta-decision。Cost ceiling has been reached at N=6 rounds。

### 2026-05-23 — Step 4.6 scoped anchor

User v6 review verdict: **PASS — 0 Blocker / 0 Required / 0 Minor**。Quote:
> "v6 re-review: **PASS — 0 Blocker / 0 Required / 0 Minor**. ...
> Header Outputs now correctly says `_vars_in_atom` contributes ZERO outer vars... §2.4 now locks adapter-side structural enforcement... Non-goal 'nested aggregate' now says adapter rejects it structurally... §5.7.5, I5/I10, §8 step 5/5b, docs scope, and audit current sections are now internally consistent。Anti-pattern grep only hits historical audit-trail quotes, not current blueprint truth.
> **可以推进 Step 4.6 scoped anchor。**"

State at anchor moment:
- HEAD prior to scoped commit:`18861f3c`(v6 amendment)
- Sacred `master`:`562c74195df43e933bed92a3ff25de94dd8ce666` 未动
- Dirty set:4 M + 1 untracked 保留(整个 6-round 流程中)
- Step 4.2 review converged through 6 tightening rounds(v1 → v6),total **2 Blockers + 19 Required = 21 findings** addressed

Scope-freeze content(per v6-passed blueprint):

| Section | Locked content |
|---|---|
| Header `Outputs / Downstream` | `_vars_in_atom` ZERO outer-var + `_infer_var_type_domains` separate concern + `_validate_atom_subset` structural mandatory |
| §2.1-2.9 + §2.6b | Sub-goals labeled C99/C100/C101/C102/C104 or specific responsibility |
| §2.5 | Empty-set guard algorithm:count/sum native;min/max/mean `count : { same_body } > 0,` prefix;no Souffle sentinel;branch-not-firing = C101 violated |
| §2.6 | `_vars_in_atom` aggregate operand ZERO contribution(no walk)|
| §2.6b | `_infer_var_type_domains` aggregate-filter recursion + target_var int classification |
| §3 Non-goals | 12 items including nested aggregate adapter-rejects-structurally lock |
| §4 Current Context | G2 source-grep + G3 file:line citations including `_infer_var_type_domains:829-861` |
| §5.3 + §5.3.5 | `_compile_aggregate` returns bare numeric;to_string/to_number wrapper decision per 8-combination lock table at call site |
| §5.5 | `_vars_in_atom` aggregate side pass(zero contribution)|
| §5.6 | G7 6 preconditions with v3-corrected failure-path wording |
| §5.7 | S-class trigger analysis(no M-class triggers)|
| §5.7.5 | Layer 1(structural mandatory regardless of gate)+ Layer 2(semantic upstream-only)split |
| §6 invariants I1-I11 | Including I5(adapter enforces filter kind list regardless of gate)+ I8(to_string only for eq binding to unbound)+ I10(two-layer)+ I11(`$_agg<N>` SDK naming convention)|
| §7 acceptance(21+ tests)| Per-kind compile(5)+ eq binding(1)+ gt filter(1)+ correlated pass-through(1)+ TRUE C104 isolation discriminator via `ne`(1)+ filter `not` body(1)+ validation reject malformed(2)+ guard prefix + to_string/to_number wrapper(4)+ count/sum no-guard(1)+ runtime branch-not-firing(1)+ gate ON/OFF validation(2)+ arith-in-filter reject ON/OFF(2)+ type domain inference(2)|
| §8 Implementation Plan(12 steps + step 5b)| G7 precondition → import → `_is_aggregate` → `_validate_atom_subset` → `_vars_in_atom` zero contribution → `_infer_var_type_domains` aggregate recursion → `_compile_aggregate` → `_compile_cmp_side` → `_compile_atom` wire → tests → docs(both mandatory)→ gates(incl. Souffle binary smoke)→ Outcome |
| §9 Docs | `application/docs/rule.md` + `sdk/docs/03_rules_and_inferences.en.md` §3.2 row(both mandatory)|

Next step(per user authorization): fork impl branch `v0.2.0-impl-t2-3c-aggregate-souffle-wire-2026-05-23` from this scoped commit。Cross-flip rotation per v6 retrospective lesson: **T2.3.c impl phase MAY revert to user-implements / Claude-reviews per the original T2.3b cross-flip rotation**(i.e.,Step 4.7 reviewer pass on user impl)。Final cross-flip role for T2.3.c impl to be confirmed at impl-start。

Anchor commit will be small:Status field flips(blueprint + audit log)+ Last Updated bumps + this Decision Note + scoped Event Log row。No code changes。
