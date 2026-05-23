# Task Blueprint Audit: T2.3b — Aggregate SDK ergonomic + bridge support

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3b-aggregate-sdk-bridge.md](./2026-05-23_t2-3b-aggregate-sdk-bridge.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md)
  - Archived T1.2 [2026-05-22_t1-2-dsl-to-application-rule.md](../archive/2026-05-22_t1-2-dsl-to-application-rule.md)
- Blueprint: [2026-05-23_t2-3b-aggregate-sdk-bridge.md](./2026-05-23_t2-3b-aggregate-sdk-bridge.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | T2 Track 4th implementation sub-slice (after T2.1 ne / T2.2 ArithExpr / T2.3a Aggregate substrate). Closes SDK ergonomic + bridge surface gap left by T2.3a. T2.3a substrate frozen (5 layers UNTOUCHED). User-facing 5 `agg_*` helpers exposed via existing `Not`/`Pred` precedent. Estimated ~470 LOC. S-class lightweight per §5.7 trigger analysis. |

## Decision Notes

### 2026-05-23 — Initial scope lock

- **T2.3a substrate is the foundation**:5 layers shipped at `477fcccb` — core IR(`AggregateAtom`/`_AGGREGATE_KINDS`/parse/lower)+ validator(filter/scoping/target binding/numeric construct + 2 错误 classes)+ Python eval(per-env + NoValue + raw resolver)+ application Rule(serialization + two-pass)。**T2.3b does NOT touch any of these 5 layers**;scope diff verifies via §7 acceptance。
- **T2.3b ships only**:(a) SDK ergonomic — 5 `agg_*` helpers + `_AggregateRef` DSL type + comparison dunders;(b) DSL → IR lowering branch;(c) bridge support — `_collect_vars_from_term` + `_canonicalize_vars` aggregate-aware;(d) public docs in `application/docs/rule.md`;(e) re-export via `factgraph.sdk.dsl.__init__`。
- **T2.3.c / T2.3.d 仍 future**:Souffle aggregate body wire / ProbLog `findall/3` + list predicates wire — both deferred per Track plan §1.2.6。

### 2026-05-23 — S-class assessment

Per Track plan §1.2.1 + §1.2.4 trigger analysis:

| Factor | T2.3b reality | Trigger fire? |
|---|---|---|
| Public API impact | **5 NEW helper functions** in `factgraph.sdk.dsl` namespace — purely additive,no rename/replacement | NO |
| Cross-commitment Q load-bearing | None — parent C99 / T2.3a fully locks semantics;T2.3b only exposes via SDK | NO |
| Design vs shipped ≥ 3 commitments conflict | None — purely additive over T2.3a | NO |
| Sub-slice count | Track plan §1.2.6 lists T2.3a/b/c/d as 4 sub-slices;T2.3b is 2nd | Within prediction |
| Cross-file commitment mismatch ≥ 2 files | None — extension limited to `expr.py` + `application_rule.py` + docs;all consistent with T2.3a + T1.2 patterns | NO |
| Public API rename ≥ 3 caller sites | NO — `agg_*` are NEW | NO |
| Size budget(S ≤ ~300 LOC + ~200 tests = ~500)| ~470 LOC est | Within budget |

**Conclusion**:S-class lightweight applies。No Stage 2 decision doc opened。

### 2026-05-23 — G1-G7 visible gate mapping

- **G1** — Blueprint §1 + §2 cite parent essay §10.6.3 (C99) explicitly;§2 sub-goal headers reference C99 or specific user-facing rationale (helper naming / export / lowering / bridge / docs / G7)。
- **G2** — Blueprint §4 documents G2 source-grep audit across 4 files (where_ast.py / sdk/dsl/expr.py / sdk/dsl/application_rule.py + namespace collision check)。Verified:T2.3a substrate landed;SDK aggregate ergonomic empty;bridge currently lacks aggregate-aware extension;`agg_*` namespace clean;`Not`/`Pred` export pattern applicable as precedent。
- **G3** — Blueprint §4 uses file:line citations (where_ast.py:75/96/102/236;sdk/dsl/expr.py:134/205/217/235/276/288;sdk/dsl/application_rule.py:54/159-174/181/188-193)。
- **G4** — Blueprint §2 sub-goals 2.1-2.6 each labeled with C-number or specific responsibility(2.1 _AggregateRef / 2.2 helpers / 2.3 lowering / 2.4 bridge / 2.5 docs / 2.6 G7)。Helper naming + export policy lock(per user focus area 1)folded into §2.2 with explicit rationale and §5.7 M-class trigger analysis。
- **G5** — Blueprint §3 Non-goals lists 11 explicit deferrals or out-of-scope items with rationale(no new kinds / no core IR change / no validator change / no Python eval change / no application Rule change / no Souffle wire / no ProbLog wire / no PyReason / no SDK top-level promotion / no M-class decision doc / no SDK Quickstart)。
- **G6** — Reviewer should independently spot-check:
  1. T2.3a substrate present at cited where_ast.py lines
  2. `agg_*` and `_AggregateRef` truly absent from current SDK DSL
  3. Bridge `_collect_vars_from_term` + `_canonicalize_vars` line locations and behavior
  4. `Not` / `Pred` export pattern in `factgraph.sdk.dsl.__init__`
  5. Application Rule `_validate_aggregate_term` at line 191(per T2.3a)still in place
  6. §5.7 M-class trigger row claims accurate against §1.2.4 trigger conditions
- **G7** — Blueprint §5.6 lists 6 pre-impl precondition checks:
  1. T2.3a substrate landed
  2. SDK aggregate ergonomic empty(this slice's add point)
  3. Bridge currently lacks aggregate-aware extension(this slice's add point)
  4. Adapter aggregate dispatch still absent(T2.3.c/d deferred)
  5. **Round-trip smoke**(direct AggregateAtom IR → parse → validate → eval all pass)— gates "T2.3a substrate healthy" assumption
  6. Naming + export collision check(`Not`/`Pred` precedent applies cleanly)

### 2026-05-23 — User's 5 Step 4.2 review focus areas (addressed upfront)

User Step 4.2 review focus(per cross-flip authorization message):

1. **Helper 命名 + export policy 不触发 M-class** — Addressed in §2.2 + §5.7:names match parent essay verbatim;export follows `Not`/`Pred` precedent in `factgraph.sdk.dsl` namespace;NOT promoted to `factgraph.sdk` top-level(narrow_public_api);no rename/replacement → no M-class trigger per §1.2.4 row "Public API rename ≥ 3 caller sites"。
2. **`_AggregateRef` 不绕过 T2.3a validation** — Addressed in §2.1 + §5.1:`_AggregateRef` is pure syntactic sugar;NO validation logic embedded;all validation runs via lowered IR → `parse_where_ir_to_ast` → `validate_where_ast` → application Rule `__post_init__`(T2.3a layers)。§7 acceptance includes "Invalid filters trigger T2.3a `AggregateValidationError`" + "Invalid scoping triggers `AggregateVariableScopeError`" tests verifying this。
3. **Bridge var collection / canonicalize 与 T1.2 + T2.3a two-pass 一致** — Addressed in §2.4 + §5.4:bridge collects ALL aggregate Vars(target + filter)— consistent with T1.2 baseline pattern of bridge-side over-collection;T2.3a application Rule Pass 2 algorithm runs independently downstream and filters out aggregate-local-only Vars before ports validation。Defense-in-depth preserved。§7 acceptance includes "Application Rule two-pass isolation still works:filter-local-only var in SDK-authored aggregate NOT in ports" test。
4. **Docs 明确 adapter wires 仍未落地** — Addressed in §2.5 + §5.5:`application/docs/rule.md` extension MUST include adapter status table(Python ✓ / Souffle deferred T2.3.c / ProbLog deferred T2.3.d / PyReason out-of-scope)+ note `_AggregateRef` is internal。§7 acceptance includes docs update。
5. **G7 包含 "SDK aggregate IR 能被 T2.3a substrate parse/validate/eval,但 adapters 仍不支持"** — Addressed in §5.6:G7 check #5 explicitly tests round-trip via T2.3a(direct AggregateAtom IR → parse → validate → eval)to confirm SDK-side aggregate IR will flow correctly;G7 check #4 verifies adapter dispatch still absent。

### 2026-05-23 — Anticipated reviewer P-finding candidates

Drafter anticipates these:

- **Bridge over-collection vs strict filter-local isolation philosophy**:§5.4 says bridge over-collects(safe per defense-in-depth)。Reviewer may prefer strict bridge-side isolation matching application Rule Pass 2 algorithm directly。Drafter rationale:simpler bridge + downstream defense is preferred for layered design;but reviewer may push for symmetry。
- **`_AggregateRef` `filter` field tuple vs list**:§2.1 used `tuple[Any, ...]` for immutability;but downstream lowering expects iterable atom list。Should be functionally equivalent but worth confirming consistent style with `Not(body: list)` precedent。
- **Helper kwarg-only `where`**:§2.2 uses `def agg_sum(target, *, where: list)` with kwarg-only `where`。Decision:matches parent essay example call shape `agg_sum(Order(o).amount, where=[...])`。Reviewer may have preference for positional `where` or different shape。
- **Tests location**:new test file `tests/sdk/dsl/test_aggregate_ergonomic.py` vs extending existing `tests/sdk/dsl/test_application_rule.py`。Drafter leans new file(separation of concerns + matches T1.2 bridge tests location pattern)。

### 2026-05-23 — Cross-slice contract preservation summary

T2.3a substrate completely frozen:`where_ast.py` / `where_ast_validate.py` / `where_eval.py` / `application/protocol/rule.py` all 0-touch in T2.3b。Verified by §7 acceptance scope diff。

T1.1 / T1.2 / T2.1 / T2.2 / ProbLog hygiene / fixture cleanup — all untouched。

SDK DSL `expr.py` extension is additive(new class + new helpers + new lowering branch),no removal of existing functions / classes。SDK DSL `application_rule.py` extension is additive(new branches in existing helpers)— no breaking changes to existing bridge behavior。

Adapter dispatch unchanged:Souffle / ProbLog aggregate aware path NOT introduced in T2.3b。Verified by §7 acceptance scope diff。

**Blueprint stays `Status: draft`** pending user Step 4.2 review。
