# Current Operational Memory

最后更新:2026-05-25(rule-expression T1/T2 closed + T3 Stage 1-3 complete + T3.1-T3.6 archived; T3 INITIAL CYCLE COMPLETE; **push gate executed — 4 origin refs created**; next-track decision pending)

## 当前阶段(2026-05-25 — T3 CYCLE COMPLETE + PUSH GATE EXECUTED — NEXT-TRACK DECISION PENDING)

**Current local branch:** `v0.2.0-t3-6-docs-and-examples-2026-05-24 @ 96baa609`.

**Sacred branch state:** `master = 562c74195df43e933bed92a3ff25de94dd8ce666` remained untouched throughout the T1/T2 local batch.

**Known dirty worktree outside these slices:**
- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- untracked `rainbird-ai sdk code/`

### Archived S-class slices in this batch

| Slice | Class | Archived at | Key implementation |
|---|---|---:|---|
| T1.1 Rule DTO | S | `40c1c70e` | `c155f3b1 feat(application): add Rule protocol DTO` |
| T1.2 DSL→application bridge | S | `ca68103e` | `3aa229c6 feat(sdk): add DSL to application Rule bridge` |
| T2.1 `ne` adapter dispatch | S | `1ca39726` | `575d48d7 feat(adapters): add raw tuple ne dispatch` |
| ProbLog import-cycle hygiene | S | `cc8f9a96` | `d0fec968 fix(audit): break ProbLog import cycle at round_events` |
| T2.2 ArithExpr substrate | S | `b17a62c1` | `04ac0cb9 feat(problog): export arithmetic builtins` |
| ProbLog `meta[confidence]` fixture cleanup | S | `1da49c41` | `e3c3d7bc test(problog): migrate meta-confidence fixtures` |
| T2.3a AggregateExpr substrate | S | `477fcccb` | `b94576f5 feat(rules): add AggregateExpr substrate` |
| T2.3b AggregateExpr SDK + bridge | S | `4e3176d2` | `94045e54 feat(sdk): add aggregate DSL helpers and bridge support` |
| T2.3c AggregateExpr Souffle wire | S | `b217f309` | `3f64fe4d feat(adapters/souffle): add aggregate compile wire over T2.3a substrate` + `84564bf2 fix(adapters/souffle): T2.3c Step 4.7 P1+P2 + dead helper removal` |
| T2.3d AggregateExpr ProbLog wire | S | `26fa7e54` | `a33b876e feat(adapters/problog): add aggregate export wire` + `d7e2a650 fix(adapters/problog): remove unused aggregate helper` |
| **T1.3 SDK Top-Level Rule Naming (first M-class)** | **M** | `df1dae2d` | `c846af09 feat(sdk): add transitional Rule naming exports` (no Step 4.7 fix) |
| **T1.4 Alias / Port Contract** | S | `a3411207` | `64135b85 feat(application): add Rule occurrence port refs` (no Step 4.7 fix) |
| **T3.1 Base RuleExpr + Bool Guards** | M | `a0718e85` | `e049c93e feat(application): add T3.1 RuleExpr base and bool guards` (A-fallback `8de03372`, no Step 4.7 fix) |
| **T3.2 Expression-Scope Occurrence Validation** | S | `21fa0914` | `2a16dd98 feat(application): add T3.2 expression-scope occurrence validation` (T-1 deviation recorded in closure) |
| **T3.3 Joins + Every-Proof-Path Reach Rule** | M | `1100ea78` | `0b80fe9b feat(application): add T3.3 joins and reach rule` (0 deviation — first T3 feat with zero Step 4.7 findings) |
| **T3.4 Join By Ports** | S | `02fcaec6` | `8f248212 feat(application): add T3.4 join by ports` (0 deviation — second consecutive T3 feat with zero Step 4.7 findings) |
| **T3.5 RuleExpr Inspect** | M | `12bd9221` | `55d9e67b feat(application): add T3.5 ruleexpr inspect` (0 deviation — third consecutive T3 feat, first proactive Step 4.6 A-fallback catch) |
| **T3.6 Docs and Examples** | S (docs-only) | `96baa609` | `f8abaad1 docs(sdk): add T3 RuleExpr user-facing docs and examples` (0 deviation — fourth consecutive T3 feat + T3 cycle final) |

### Current landed behavior

**T1.1 — application `Rule` DTO**
- `factgraph.application.protocol.Rule` exists in `src/factgraph/application/protocol/rule.py`.
- `Rule.where` stores core AST atoms directly and rejects `RuleRefAtom`.
- Supports `atom_ids`, deterministic `content_digest`, `render_desc(...)`, shallow/container immutability.
- Recursive immutability hardening remains deferred because core AST internals use mutable lists.

**T1.2 — DSL to application Rule bridge**
- `factgraph.sdk.dsl.build_application_rule(...)` and `DSLToApplicationRuleError` exist.
- `ExistsAtom.__getattr__`, additive `AttrRef.entity_type`, and positional `User(...)` Ellipsis support landed.
- Unified equality/bare-existence forms emit `EntityType:exists` predicates and field predicates; cross-entity ref emits both existence predicates.
- Legacy bare AttrRef, two-line legacy form, raw `Pred(...)`, raw RuleRef, OR-shaped where, and anonymous ports are rejected.
- Non-eq AttrRef compare, `AttrRef` arithmetic, float literals, and `/` remain deferred.

**T2.1 — atom kind `ne` adapter dispatch**
- Souffle raw tuple adapter validates and compiles `("ne", lhs, rhs)` in main body and `not` body.
- Souffle variable extraction includes `ne`.
- ProbLog exports raw tuple `ne` to `\=` term inequality.
- T2.1 exposed a pre-existing ProbLog import cycle; fixed in the next hygiene slice.

**ProbLog import-cycle hygiene**
- `factgraph.adapters.problog.problog_export` can import directly.
- `get_engine_evaluator("problog") is evaluate_problog` works.
- Actual fix boundary moved deeper than the initial blueprint: `audit/round_events.py` stopped top-level importing application protocol common types.
- A G7 precondition failure caused an amendment before implementation; this is the model for future boundary-sensitive hygiene slices.

**T2.2 — ArithExpr substrate + ProbLog builtin parity**
- ProbLog `_compile_atom(...)` exports existing arithmetic builtin atoms `add`, `sub`, `neg`, `addc`, `mulc` via `is/2`.
- SDK bridge tests now prove existing `BinaryExpr` shapes lower through `build_application_rule(...)` to `BuiltinAtom("addc")` / `BuiltinAtom("mulc")` plus comparisons.
- No production support added for `div`, `/`, `AttrRef` arithmetic, float literals, or div-by-zero evidence semantics.
- G7 checks ran before implementation, but the audit-log record landed after the implementation commit; this timing miss was disclosed in `407cd71b`.

**ProbLog `meta[confidence]` fixture cleanup**
- Removed four stale `meta[confidence]` fixture sites in `tests/test_problog_export.py` and `tests/test_problog_engine_eval.py`.
- Full ProbLog gates now pass:
  - `tests.test_problog_export` — 14 tests OK.
  - `tests.test_problog_engine_eval` — 10 tests OK.
  - combined export + engine gate — 24 tests OK.
- The G7 precondition gate was amended before fixture edits: broad `tests.test_sdk_assertion_record_set` was removed as a precondition because it has unrelated `snap.field(...).active.where` baseline drift; the valid canonical gate is `tests.test_write_protocol_annotations.TestRawUncertaintyWriteLane`.

**T2.3a — AggregateExpr substrate**
- Core `AggregateAtom` landed in `src/factgraph/core/rules/where_ast.py` as a term-position value form, not as a top-level truth atom.
- Validation landed in `where_ast_validate.py`: aggregate filter restrictions, per-env variable scoping, target binding, numeric target checks, and aggregate-specific error classes.
- Python evaluator landed in `where_eval.py`: per-env aggregate resolution, `AggregateNoValue`, aggregate-aware comparison/arithmetic raw resolvers, and helper coverage for planning/scoring/variable extraction.
- Application Rule serialization landed in `application/protocol/rule.py`: `_serialize_term` and two-pass variable collection now understand aggregate terms while isolating aggregate-local filter variables.
- SDK ergonomic helpers, DSL bridge aggregate support, and public docs all shipped in T2.3b (see below). Souffle/ProbLog/PyReason adapter wires are deferred to follow-up slices T2.3c/T2.3d (PyReason out of scope).
- G7 precondition was recorded before implementation in `f3d217a3`, implementation landed in `b94576f5`, closure in `b554b0f1`, audit status sync in `c0a80f79`, and archive in `477fcccb`.

**T2.3b — AggregateExpr SDK ergonomic + bridge**
- 5 public helpers `agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean` landed in `src/factgraph/sdk/dsl/expr.py` and are exported from `factgraph.sdk.dsl.__all__` only; top-level `factgraph.sdk` intentionally not promoted (narrow-public-api).
- Internal `_AggregateRef` frozen dataclass added with 6 comparison dunders; pure syntactic sugar with no embedded validation. T2.3a substrate validates lowered IR.
- DSL→IR lowering branch `_lower_compare_with_aggregate` / `_lower_aggregate_ref` / `_lower_aggregate_target` landed with filter-then-target order, `filter_bindings = dict(outer_bindings)` isolation copy, and **Option 2 self-ensure pattern**: target `AttrRef` record var auto-injects `EntityType:exists($var)` only when the aggregate filter did not already bind it, via the existing `_ensure_attr_record_binding` helper (early-return on hit prevents duplicate existence predicates). Order-independent by design.
- Bridge extensions in `src/factgraph/sdk/dsl/application_rule.py`:
  - `_reject_legacy_aggregate_ref` recurses through target + filter to preserve T1.2 P3 legacy hard-cut policy.
  - `_collect_vars_from_term` + `_canonicalize_term` now understand `AggregateAtom` (over-collect target + filter atoms; T2.3a application Rule Pass 2 still independently isolates aggregate-local-only vars before ports — defense-in-depth).
  - **Bridge validation gate wired** (scoped amendment `13f79337`): `validate_where_ast(where_expr, mode="python", capabilities={"allow_ruleref": False}, initial_bound_vars=<port LogicVar tokens>)` runs after parse/canonicalize; `WhereASTValidationError` wraps as `DSLToApplicationRuleError`. Port LogicVar tokens are passed as `initial_bound_vars` so existing arithmetic/input-port behavior remains valid; ApplicationRule still independently rejects aggregate-local port leakage downstream.
- Three-layer docs updated: `application/docs/rule.md` (removed deferral language, added adapter status), `sdk/docs/03_rules_and_inferences.en.md` (new §3.2 with end-to-end example + per-env semantics + isolation + adapter status table), `sdk/docs/04_api_surface.en.md` (5 helpers in dsl namespace table + advanced-direct-import entry).
- New 10-test acceptance file `tests/sdk/dsl/test_aggregate_ergonomic.py` includes the **3-test self-ensure discriminator trio** (filter-bound + filter-bound-via-unified-syntax + TRUE self-ensure `agg_sum(Order(o).amount, where=[User(u)])`) plus isolation-leak prevention, bridge legacy rejection, validator-gate, two-pass isolation, and end-to-end correlated Python eval tests.
- Commit lineage: scoped `26d11d81` → G7 precondition `99729ca5` (recorded BEFORE impl) → bridge validator amendment `13f79337` (scoped amendment BEFORE feat) → feat `94045e54` (impl + tests + 3-layer docs combined) → closure `f16a80db` (§10 Outcome filled, Nit deferral recorded) → archive `4e3176d2` (100% rename).
- Verification at archive: 10 new aggregate tests pass; 98-test cross-slice scope pass (per §10.3); 153 wider-discover failures unrelated (frontier/diagnose/localizer paths, T2.3b touched none). Ruff clean on touched files. Sacred `master` + dirty set preserved throughout.
- **Deferred Nit accepted as follow-up** (Step 4.7 single Nit observation, user chose deferral): `_lower_compare_with_aggregate` non-aggregate side currently calls `lower_term(..., in_where=True)` which raises for AttrRef and BinaryExpr. `Order(o).amount == agg_count(...)` and `(n + 1) == agg_count(...)` fail loudly with `SDKDSLError`; two-aggregate `agg_count(...) == agg_count(...)` works. T2.3.b1 / T2.3.e candidate; workaround = bind aggregate result to Var first.
- Souffle adapter wire shipped in T2.3c (see below). ProbLog adapter wire shipped in T2.3d (see below). T2.3 AggregateExpr full track now closed (substrate + SDK + Souffle + ProbLog). PyReason aggregate permanently out of scope.

**T2.3c — AggregateExpr Souffle adapter wire**
- Souffle adapter `src/factgraph/adapters/souffle/where_compile.py` now lowers SDK-produced aggregate IR (T2.3b output shape `("eq", lhs, ("kind", target_var, filter_atoms))`) to Souffle DL aggregate body syntax. Added `_AGGREGATE_KINDS` import + `_AGGREGATE_GUARD_KINDS = {"min", "max", "mean"}` + `_is_aggregate` strict helper + `_AGGREGATE_FILTER_ATOM_KINDS` C100 filter list.
- **Empty-set guard algorithm** (blueprint §2.5 v2 lock per user direction A): `count` / `sum` use native Souffle empty=0 matching C101 legal values (no guard). `min` / `max` / `mean` emit `count : { same_body } > 0,` guard prefix → empty body → guard fails → branch does not fire → matches C101 "comparison violated / no env pollution". No Souffle sentinel object — `AggregateNoValue` represented by branch-not-firing.
- **to_string/to_number wrapping** (blueprint §5.3.5 v3 lock table): eq binding to unbound var uses `v_X = to_string(<value>)` (symbol domain); eq filter with bound var uses `<value> = to_number(v_X)` (numeric); 8 cases total covering eq/ne/gt/ge/lt/le with var/literal/aggregate operands.
- **Var extraction** (blueprint §5.5 v2 + §2.6 v3): `_vars_in_atom` cmp branches treat aggregate operand as ZERO outer-var contribution. Correlated outer vars come from their original outer-scope atom; aggregate-local vars (target_var + filter-introduced) stay private per C104.
- **Type domain inference** (blueprint §2.6b v3 P2): `_infer_var_type_domains` recurses into aggregate filter atoms; marks aggregate `target_var` as int per C102; eq-binding to aggregate also marks bound var as int.
- **Adapter validation** (blueprint §5.7.5 Layer 1 + §6 I5/I10/I11): `_validate_aggregate_atom_shape` mandatory regardless of `FACTPY_WHERE_AST_VALIDATE` gate state. Cmp operand tuples always routed to aggregate structural validation — unknown kinds rejected with "unsupported aggregate kind" (Step 4.7 P2 v7 fix). Layer 1 checks (kind/arity/target_var shape/filter list/nested aggregate/C100 filter atom kinds) mandatory; Layer 2 (C100 outside kind-list / C102 runtime / C104 binding-order / C103 snapshot) deferred upstream-only.
- **`_compile_filter_atom_within_aggregate`** mirrors `_compile_atom` (no witness symbols, `local_bound_vars` scope, synthetic not-relation extraction via `agg:` namespace prefix). Multi-atom and OR-branch not bodies inside aggregate supported via same synthetic-relation pattern as outer-where.
- **Three-layer docs flip** (mandatory per §9 + §6.1 P4 v2): `application/docs/rule.md` (Souffle row pending → ✓ + empty-set guard explanation) + `sdk/docs/03_rules_and_inferences.en.md` §3.2 (Souffle row Deferred → Supported).
- 27-test acceptance file `tests/test_souffle_aggregate_compile.py` covers §7.1-§7.11 + extra shape coverage + 2 Step 4.7 P1 v7 tests (numeric bound var pass + entity-typed bound var reject).
- Commit lineage: scoped `6083e305` → G7 precondition `6dd4272b` (BEFORE impl, doc-only) → feat main `3f64fe4d` (impl + 25 tests + 3-layer docs) → Step 4.7 fix `84564bf2` (P1 aggregate eq/ne bound-var `_assert_cmp_var_allowed` + P2 unknown kind structural rejection regardless of gate + dead `_compile_aggregate` wrapper removal) → closure `f7cc3a07` → archive `b217f309`.
- Verification at archive: 27 T2.3c tests pass; 88 cross-slice tests pass (T2.3a + T2.3b + T2.1 + T2.2 + SDK DSL + application protocol — 0 regression). Ruff clean. Sacred `master` + dirty set preserved throughout.
- **Cross-flip inversion experiment closed with documented cost-value verdict**: 6 Step 4.2 rounds + Step 4.7 v1 + Step 4.7 v2 = 8 review rounds, 25 findings (2 Blockers + 22 Required + 1 Worth-considering). Compared to user-drafts baseline (T2.2 / fixture cleanup / T2.3a — all 0-1 round Step 4.2). **Verdict: T2.3.d MUST revert to user-drafts pattern**. Hard recommendation locked across multiple retrospectives.
- **Size deviation accepted as S-class** per Step 4.8 user closure guidance: actual ~1090 LOC (630 code + 460 tests) vs blueprint §5.7 estimate ~300 LOC. Qualitative S-class criteria all hold (adapter-only scope, no public API rename, no cross-engine semantic decision, no substrate/SDK change, no new baseline drift surfaced).
- Deferred follow-ups per T2.3c §10.4: T2.3.d ProbLog wire **shipped at `26fa7e54` (see T2.3d below)** + T2.3.b1/T2.3.e Nit (T2.3b carried over) + schema "number" vs "int" cmp compatibility (general adapter hygiene, pre-existing Souffle-only concern) + Souffle native `mean` aggregator binary verification ((A-fallback) deviation path documented if incompatibility surfaces).

**T2.3d — AggregateExpr ProbLog adapter wire**
- ProbLog adapter `src/factgraph/adapters/problog/problog_export.py` now lowers SDK-produced aggregate IR via `findall/3` + `library(lists)` predicates (`length/2`, `sum_list/2`, `min_list/2`, `max_list/2`) + derived mean via `sum_list + length + is/2`. Closes T2.3 AggregateExpr full track (substrate + SDK + Souffle + ProbLog). PyReason aggregate permanently out of scope per parent essay §10.6.3.
- Module-level additions: `_AGGREGATE_KINDS` + `_AGGREGATE_FILTER_ATOM_KINDS` constants + `_CompileContext` dataclass (`next_id` counter + `requires_lists` bool flag) + `_CompileContext.fresh(prefix)` producing `Agg{Prefix}{N}` names (AggList1, AggResult2, AggSum3, AggCount4) per blueprint I10 v2 lock, avoiding `V_<UPPER>` user-var namespace collision.
- **Per-kind lowering** (blueprint §5.3): `count` via `findall(1,...) + length`; `sum` via `findall(target,...) + sum_list`; `min`/`max` via `L = [_|_]` guard + `min_list`/`max_list`; `mean` via `L = [_|_]` + `sum_list` + `length` + `Result is Sum / Count`. The `L = [_|_]` guard for min/max/mean makes empty body fail Prolog unification → enclosing rule body fails → matches C101 "comparison violated / no env pollution" semantics. No Souffle-like sentinel object; ProbLog's `findall/3` runtime + branch-not-firing model handles it naturally.
- **Cmp dispatch composition** (blueprint §5.4): `_is_tuple_operand(value)` discriminator → `_compile_cmp_with_aggregate(kind, lhs, rhs, ctx)` emits `lhs_goals + rhs_goals + "lhs_term op rhs_term"`. Per P3 v2 lesson (T2.3c retrospective), any tuple cmp operand is aggregate-shaped (cmp operands cannot be raw atoms); unknown kinds rejected with "unsupported aggregate kind" via `_validate_aggregate_shape`. Two-aggregate cmp emits both goals + cmp on result vars.
- **Aggregate-local var isolation** (blueprint I6): two layers. Layer 1 — Prolog `findall(Template, Goal, List)` runtime scope (vars not bound at call site are local to body). Layer 2 — `extract_where_variables(...)` from T2.3c (Souffle adapter) returns ZERO outer contribution for aggregate operands; ProbLog imports unchanged via `problog_export.py:12`. Aggregate-local vars never enter `query_vars` / `rule_body_N(...)` / `answer(...)` heads.
- **Adapter validation** (blueprint §2.6 + §5.6 + I8): `_validate_aggregate_shape` mandatory regardless of `FACTPY_WHERE_AST_VALIDATE` gate state. Rejects unknown kind / wrong arity / target_var shape (None for count, `$`-prefixed otherwise) / non-list filter / non-C100 filter atom kinds / nested aggregate. Recursive validation into `not` body filter atoms.
- **`library(lists)` conditional directive** (G7 (A-fallback) amendment, invariant I2a): G7 #7 smoke proactively discovered local ProbLog binary requires explicit `:- use_module(library(lists)).` for `sum_list/2`, `min_list/2`, `max_list/2`. Blueprint amended pre-impl per (A-fallback) discipline (in scoped state, before any code edits), 7-section propagation (Outputs + §2.2 + §5.2 + §5.3 + §5.8 + §5.9 G7 #7 + new I2a). Implementation: `ctx.requires_lists = True` set inside `_compile_aggregate_parts`; `export_problog` precompiles all bodies BEFORE line emission; conditional `:- use_module(library(lists)).` line emitted after `% query_vars=...` header IFF `ctx.requires_lists=True`. Non-aggregate exports keep existing exact-output behavior.
- **`not` filter recursion**: existing `_compile_atom("not", ...)` at problog_export.py:318-326 reused inside aggregate filter via `ctx` threading. Emits `\+(...)` standard Prolog negation-as-failure. Multi-atom and OR-branch not bodies inside aggregate supported via `_normalize_not_bodies` pattern.
- 12-test acceptance added to existing `tests/test_problog_export.py` (now 26 tests total, was 14 from T2.1/T2.2). Covers 5 per-kind compile + negative discriminator (count/sum no guard) + eq binding + numeric cmp + two-aggregate cmp + filter `not` body + library(lists) directive integration + 3 structural validation tests (unknown kind / malformed target / non-C100 filter atom kind).
- **Two-layer docs flip** (mandatory per §9 + §6.1 P4 v2 + I9): `application/docs/rule.md` (ProbLog row pending → ✓ + `findall/3` + list predicates + `L = [_|_]` empty-set explanation) + `sdk/docs/03_rules_and_inferences.en.md` §3.2 (ProbLog row Deferred → Supported).
- **6-commit canonical lineage**:
  - `42104ec2` scoped anchor
  - `c3127703` G7 precondition + scoped (A-fallback) amendment (BEFORE code edits)
  - `a33b876e` feat main (impl + 12 tests + 2-layer docs)
  - `d7e2a650` Step 4.7 fix (removed unused `_is_aggregate` dead helper)
  - `d2c46bc7` closure (Status: implemented + §10 Outcome)
  - `26fa7e54` archive (100% rename)
- Verification at archive: 26 T2.3.d tests pass; 124 cross-slice tests pass (T2.3a + T2.3b + T2.3c + T2.1 + T2.2 + SDK DSL + application protocol + ProbLog export + engine eval — 0 regression). Ruff clean. Local `problog` binary smoke verified end-to-end with generated aggregate program. Sacred `master` + dirty set preserved throughout.
- **Cross-flip retrospective verdict CONFIRMED**: 2 Step 4.2 rounds + Step 4.7 v1 = 5 findings total (0 Blockers + 3 Required + 2 Worth-considering). **5x cost reduction vs T2.3c** (25 findings / 8 rounds with cross-flip inversion). T2.3c retrospective lesson "T2.3.d MUST revert to user-drafts" validated. Future adapter-shaped slices should default to user-drafts pattern.
- **Implementation size**: ~141 LOC code + ~140 LOC tests = ~281 LOC. Well within blueprint §5.8 estimate 250-450 LOC; much smaller than T2.3c ~1090 LOC because ProbLog's `findall/3` runtime scoping eliminates the Souffle "filter-within-aggregate mirror" pattern (~150 LOC saved).
- Deferred follow-ups per T2.3d §10.4: T2.3.b1/T2.3.e Nit (T2.3b carried over) + schema "number" vs "int" cmp compatibility (Souffle-only, N/A for ProbLog untyped).

**T1.3 — SDK Top-Level Rule Naming (first M-class slice)**
- **First M-class slice** in T1/T2 batch. Resolved TPQ-2 (parent essay §3.10 naming conflict — old `Rule` with `select`/`head` vs new application Rule atomic AND-only). Decision: **A-staged** — timing refinement of parent alternative A (full replacement), deferring final `Rule` flip to T5 legacy `.eval` / old rule hard-cut. Parent §325 promise ("new user sees `Rule` as atomic AND-only") explicitly deferred during staged period, not canceled.
- **Decision doc** at `workflow/design/decisions/archive/2026-05-23_t1-3-sdk-rule-top-level-naming.md`:
  - **Lifecycle**: `proposed` (draft) → `reviewed` (Step 4.2 v2 pass) → `accepted` (concurrent with Step 4.6 scoped anchor; impl gate unlocked) → `superseded` (if later decision overrides).
  - **4 alternatives compared**: A immediate replacement / B `sdk.v2.Rule` namespace / C mode flag / **D A-staged (chosen)**. A's concrete cost: 15 caller-site migration (13 tests + 2 docs from `grep -rln "from factgraph.sdk import.*Rule"`).
  - **No `DeprecationWarning`** in T1.3 on legacy `Rule` (deferred to final hard-cut to avoid noisy output across 15 callers).
- **5 transitional top-level SDK exports** in `factgraph.sdk.__init__.py`:
  - `LegacyRule` — explicit alias for legacy `factgraph.sdk.dsl.Rule`
  - `ApplicationRule` — alias for `factgraph.application.protocol.Rule`
  - `build_application_rule` — promoted to top-level (was DSL-only per T2.3b)
  - `DSLToApplicationRuleError` — promoted to top-level
  - `Rule` — kept as legacy-compatible (final flip deferred)
- **T2.3b docs guidance broadening** explicit in `sdk/docs/04_api_surface.en.md`: `build_application_rule` now top-level AND DSL (T2.3b directed DSL-only); `agg_*` helpers remain DSL-only (narrow_public_api preserved). Old text "Use `from factgraph.sdk.dsl import agg_sum, build_application_rule`" updated to "Use `from factgraph.sdk import build_application_rule` and `from factgraph.sdk.dsl import agg_sum`".
- **6 identity-based tests** in `tests/sdk/test_rule_naming.py` covering all alias `is` assertions + legacy construction + top-level bridge + `__all__` export.
- **2-layer docs flip**: `sdk/docs/04_api_surface.en.md` updated `Rule` row + 4 new rows; `sdk/docs/03_rules_and_inferences.en.md` §3.2 example import updated. `06_what_if_and_proof.en.md` explicitly out-of-scope (legacy `Rule` still valid per A-staged).
- **Canonical 4-commit M-class impl pattern** (no Step 4.7 fix — review passed clean):
  - `f134dc8c` scoped anchor + decision doc `accepted` concurrent (per lifecycle)
  - `dd323698` G7 precondition (doc-only, BEFORE feat — recorded `sdk.Rule is dsl.Rule: True`, `has LegacyRule: False`, `has ApplicationRule: False`, `has top build_application_rule: False`, `has top DSLToApplicationRuleError: False`, application rule identity)
  - `c846af09` feat main (~91 LOC: impl + 6 tests + 2-layer docs)
  - `0616f4ed` closure (Status: scoped → implemented + §10 Outcome)
  - `df1dae2d` archive (3-file 100% rename: blueprint pair + decision doc)
- Verification at archive: 6 T1.3 tests pass; 145 cross-slice tests pass (T1.1/T1.2/T2.1/T2.2/T2.3a-d targeted suites all 0-regression); ruff clean; 0-diff under `src/factgraph/adapters/` / `src/factgraph/core/` / `src/factgraph/application/protocol/rule.py` (per blueprint §7 acceptance #8). Sacred `master` + dirty set preserved throughout.
- **Convergence**: 2 Step 4.2 rounds + Step 4.7 v1 clean = **7 total findings at v1** (0B + 4R + 3WC, all closed at v2). Pattern matches T2.3d S-class (5 findings / 3 rounds). M-class adds ~2 decision-doc findings (lifecycle + framing) but otherwise same cost.
- **User-drafts pattern validated for M-class**: same rotation as T2.3d S-class. No Step 4.7 fix commit needed (variant of canonical 5-commit pattern: Step 4.7 fix is OPTIONAL).
- Deferred follow-ups (per T1.3 §10):
  - Final `Rule` flip at T5 legacy `.eval` / old rule hard-cut (parent §3.10 alternative A finalization)
  - `LegacyRule` retention decision at hard-cut (keep temporarily? remove?)
  - `DeprecationWarning` policy decision at hard-cut

**T1.4 — Alias / Port Contract**
- **Application protocol substrate for future T3 RuleExpr joins**. Adds `Rule.as_()`, `RuleOccurrence`, `RulePortRef` to `factgraph.application.protocol`. Closes parent §3.6 commitment 6 substrate requirement; T3 will consume these DTOs for `.join(...)` constraints and `fg.rules.inspect(...)` output.
- **`Rule.as_(alias: str | None = None)` method** in `factgraph/application/protocol/rule.py`:
  - Default `alias = rule.id` per parent §3.6 commitment 6
  - Explicit alias validated via `_validate_occurrence_alias` using `re.fullmatch(_OCCURRENCE_ALIAS_RE)` pattern `[A-Za-z][A-Za-z0-9_]*`
  - Rejects empty/digit-start/underscore-start/hyphen/punctuation
  - Template-stable: no mutation; repeated calls produce value-equal occurrences (but NOT interned)
  - Edge case: non-identifier `rule.id` (e.g., `"my-rule"`) causes `rule.as_()` default to raise; user must call `.as_("custom_alias")` explicitly
- **`RuleOccurrence` frozen DTO**:
  - `rule: Rule` + `alias: str` fields
  - `__post_init__` defense-in-depth re-validates alias (catches direct `RuleOccurrence(...)` construction bypassing `Rule.as_()`)
  - `port(name)` returns `RulePortRef`; missing port → `RuleValidationError`
  - `__getattr__(name)` for `occ.user` style; `_`-prefix → `AttributeError`; missing port → `AttributeError` (via caught `RuleValidationError`); preserves Python `hasattr()` semantics
  - Explicit `__hash__` for hashability
- **`RulePortRef` frozen DTO** (5 fields): `occurrence_alias`, `rule_id`, `port_name`, `var: Var`, `port_type: PortType`. Reference descriptor for T3 joins, not a core AST term. Stores `rule_id` (lightweight) per G6 spot-check #3 choice.
- **Validation pathway (defense-in-depth)**: `Rule.as_(alias)` → `_validate_occurrence_alias` → `RuleOccurrence(rule, alias)` → `__post_init__` validates again (idempotent + safe). Direct `RuleOccurrence(rule=..., alias=invalid)` still raises.
- **Invariants** (per blueprint §6):
  - `Rule.content_digest` alias-independent (occurrence wrappers are expression-level, not template-level)
  - Port names (not internal `Var.name`) are the public cross-Rule interface (parent §C54)
  - Same-name ports across Rules do NOT auto-join in T1.4 (T3 owns join semantics)
  - `Rule.ports` remains frozen `MappingProxyType` (T1.1 contract preserved)
- **Docs flip**: `application/docs/rule.md` gets new "Ports and Occurrence Aliases" section. `sdk/docs/03_rules_and_inferences.en.md` intentionally NOT updated (deferred to T3 when `.as_(...)` becomes user-visible via RuleExpr).
- **Tests**: 10-test acceptance in `tests/application/protocol/test_rule.py` + 1 bridge compat test in `tests/sdk/dsl/test_application_rule.py`. Verifies default alias, explicit alias, value-equality-not-interning, 4 invalid alias patterns, non-identifier rule.id edge case, port reference 5 fields, missing port `RuleValidationError` vs `AttributeError` discrimination, frozen + hashable, content_digest alias-independent, parent §C54 different-Var-same-port-name, bridge compat.
- **Canonical 4-commit impl pattern** (no Step 4.7 fix — second instance after T1.3):
  - `8835812c` scoped anchor + edge case acceptance locked
  - `f04907ea` G7 precondition (doc-only, BEFORE feat — recorded `has Rule.as_: False`, `has RuleOccurrence: False`, `has RulePortRef: False`, `sdk.ApplicationRule is Rule: True`, top `build_application_rule` available)
  - `64135b85` feat main (61 LOC impl + 119 LOC tests + 20 LOC docs + 4 LOC exports)
  - `2b4b2648` closure (Status: scoped → implemented + §10 Outcome)
  - `a3411207` archive (2-file 100% rename — blueprint pair only, no decision doc since S-class)
- Verification at archive: 39 T1.4 acceptance tests pass; 121 cross-slice tests pass (0 regression); ruff clean; **0-diff verified** under `src/factgraph/adapters/`, `src/factgraph/core/`, legacy `src/factgraph/sdk/dsl/rule.py`. Sacred `master` + dirty set preserved throughout.
- **Convergence**: 2 Step 4.2 rounds + Step 4.7 v1 clean = **5 total findings at v1** (0B + 1R + 4WC, all closed at v2 + 1 minor WC at scoped). Pattern matches T2.3d S-class.
- Deferred follow-ups (per T1.4 §10):
  - T3 RuleExpr `.as_(rule)` occurrence alias + expression-level alias uniqueness check + multi-occurrence detection (depends on T1.4 substrate — now unblocked)
  - T3 RuleExpr `&` / `|` / `.join(...)` / `.join_by_ports(...)` composition operators
  - T3 `fg.rules.inspect(expr)` `unjoined_same_name_ports` discoverability hint
  - SDK user-facing `.as_(...)` docs in `sdk/docs/03_rules_and_inferences.en.md` (defer to T3 when RuleExpr ships)

**T1 Track CLOSED.** T1.1 (Rule DTO) + T1.2 (DSL bridge) + T1.3 (SDK naming) + T1.4 (alias/port substrate) all shipped. T3 RuleExpr (L-class) unblocked.

**T3 Stage 1-3 + T3.1 — Base RuleExpr + Bool Guards**
- **Stage 1 audit + Stage 2 decisions + Stage 3 synthesis complete**:
  - Stage 1 audit `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` established shipped-vs-design baseline for C23-C35 + C49-C51 + C58 + C59.
  - Stage 2 adopted five decision docs D1-D5 covering public surface / operand boundary, join constraint construction, inspect coexistence, structural equality/hash, and slice split + bool guard timing.
  - Stage 3 synthesis `workflow/audit/active/2026-05-24_t3-ruleexpr-synthesis.md` mapped T3.1-T3.6 + later execution tranche; track plan sync landed at `9c857d0c`.
- **T3.1 archived at `a0718e85`**:
  - Blueprint lineage: `81551dd4` draft → `3d92a48a` P2 amend → `e184f3c5` scoped+P3 → `0abe8386` Step 4.6 grep clean → `febe7028` G7 baseline → `8de03372` A-fallback → `e049c93e` feat → `2190edce` closure → `a0718e85` archive.
  - Landed base `RuleExpr` surface: `RuleExpr`, `RuleExprError`, `ExplicitBoolError`; frozen `_RuleExpr` / `_AndGroup` / `_OrGroup`; `RuleExpr.all` / `RuleExpr.any`; application `Rule.__and__` / `__or__` / `__bool__`; SDK top-level exports.
  - A-fallback `8de03372` introduced neutral `factgraph._sdk_errors` to avoid application→SDK import cycle while preserving `factgraph.sdk.dsl.errors.SDKDSLError` class identity for `RuleExprError(SDKDSLError)`.
  - Verification: G7 baseline 23 tests OK; post-impl core gate 38 tests OK; cross-slice 88 tests OK; ruff clean. `pytest` SIGSEGV remains a separate tooling issue and does not block T3.1.
  - Negative-action gates preserved: legacy SDK `Rule.__bool__` unchanged; no direct `application_rule == rule_expr` cross-type equality; T1.4 `Rule.as_` / `RuleOccurrence` / `RulePortRef` untouched; T2.3 aggregate substrate untouched; T1.3 staged top-level `Rule` remains legacy.
- **Deferred T3.1 follow-ups**:
  - Inline in T3.2 if touching the same files: add `-> _RuleExpr` annotations to `Rule.__and__` / `Rule.__or__`, tighten `_RuleOperand.rule` typing from `object` to `Rule`, and optionally replace the duck-typed legacy SDK Rule detector if a cycle-safe nominal check is available.
  - T3.2 owns expression-scope occurrence validation: alias uniqueness, repeated same Rule requires explicit aliases, default alias behavior for single occurrence, and duplicate diagnostics.

**T3.2 — Expression-Scope Occurrence Validation**
- **T3.2 archived at `21fa0914`**:
  - Lineage: `e7dbf693` draft → `24ca01cd` P2 amendment (T3.1 duplicate-multiplicity supersedence) → `b0963c17` scoped + P3 → `c8e4fce8` Step 4.6 grep clean → `62c04100` G7 baseline → `2a16dd98` feat → `90598e95` closure → `21fa0914` archive.
  - Landed expression-scope validation in `rule_expr.py`: `_RuleOperand(rule: Rule, alias: str, explicit_alias: bool)`, `RuleOccurrence` operand coercion, default-alias validation via T1.4 `Rule.as_()`, `_validate_expression_scope(...)`, deterministic aggregate diagnostics, and alias-inclusive canonical equality/hash.
  - T3.1 P3 follow-ups landed inline: `Rule.__and__` / `Rule.__or__` now have `-> _RuleExpr` annotations, and `_RuleOperand.rule` tightened from `object` to application `Rule`. `_is_legacy_sdk_rule` remains duck-typed by explicit deferral.
  - Verification: G7 baseline 38 tests OK; post-impl core gate 45 tests OK; cross-slice gate 54 tests OK; ruff clean. T1.4 23-test baseline preserved.
  - Seven negative-action gates preserved: legacy SDK `Rule.__bool__` unchanged; no direct `application_rule == rule_expr`; T1.4 `Rule.as_` / alias regex / port APIs preserved; T1.3 staged naming unchanged; T2.3 aggregate substrate untouched; T3.1 acceptance preserved after explicit-alias test supersedence; duck-typed legacy detector retained.
  - **T-1 deviation recorded in §10**: implementation discovered explicit-alias infix expressions require `RuleOccurrence.__and__` / `__or__`. The additive method change was bundled into feat rather than a pre-feat (A-fallback) scope amendment. Closure records this as process-discipline drift and future slices must pause for a pre-feat scope amendment when discovered operator/dunder additions expand scope.

**T3.3 — Joins + Every-Proof-Path Reach Rule**
- **T3.3 archived at `1100ea78`**:
  - Lineage: `5496d076` draft → `a3a78702` scoped + P3 → `52eec99e` Step 4.6 grep clean → `83489a07` G7 baseline → `0b80fe9b` feat → `c43c3613` closure → `1100ea78` archive.
  - Landed join surface: `RuleJoinConstraint` frozen DTO; `RulePortRef.eq(...)`; `_AndGroup.joins` + `.join(...)`; `_OrGroup.join(...)` diagnostic; symmetric/dedup canonical join helpers; direct-AND-spine `_validate_join_reach(...)`; endpoint-vs-operand validation; `_combine("and", ...)` merge/revalidation; `_AndGroup._canonical()` includes normalized joins.
  - Verification: G7 45 tests OK; post-impl core 55 tests OK; cross-slice 64 tests OK; ruff clean.
  - Nine negative-action gates preserved: legacy SDK `Rule.__bool__` unchanged; no direct `application_rule == rule_expr`; T1.4 substrate preserved except pre-scoped additive `RulePortRef.eq`; `RulePortRef.__eq__` remains value equality; T1.3 staged naming unchanged; T2.3 aggregate substrate untouched; T3.1/T3.2 acceptance + negative-action gates preserved; `_is_legacy_sdk_rule` duck-typed detector retained; no new error subclass.
  - **0-deviation milestone**: first T3 feat with 0 P0/P1/P2/P3 at Step 4.7. Clean result attributed to §5.2 preemptive `RulePortRef.eq()` scope lock, §5.3 validation-location layering, §5.6 Reach Rule pseudocode/complexity, and §5.7 canonical symmetric equality lock.

**T3.4 — Join By Ports**
- **T3.4 archived at `02fcaec6`**:
  - Lineage: `6242c7a1` draft → `5fb525eb` scoped + P3 → `4035d360` Step 4.6 grep clean → `81285e98` G7 baseline → `8f248212` feat → `67f9fed2` closure → `02fcaec6` archive.
  - Landed strict two-file scope: `rule_expr.py` adds `itertools.combinations`, `_AndGroup.join_by_ports(...)`, `_OrGroup.join_by_ports(...)` diagnostic, `_validate_join_by_port_names`, `_expand_join_by_ports`, and `_port_refs_for_name`; `test_rule_expr.py` adds 8 T3.4 tests including `test_join_by_ports_preserves_export_scope`.
  - Verification: G7 baseline 55 tests OK; post-impl core gate 63 tests OK; cross-slice gate 72 tests OK; ruff clean.
  - Nine T3.3 negative-action gates plus six T3.4 explicit "no" locks preserved: no legacy SDK change, no cross-type equality, no T1.4 DTO change, no `Rule.join_by_ports`, no `RuleOccurrence.join_by_ports`, no helper module, no new error subclass, and no new SDK export.
  - **Second consecutive 0-deviation milestone**: T3.4 repeated T3.3's clean result with 0 P0/P1/P2/P3 at Step 4.7. Closure attributes this to §5.5 preemptive scope locking, §5.3 algorithm pseudocode with `itertools.combinations`, §5.7 validation ordering, and §5.4 stable diagnostics.

**T3.5 — RuleExpr Inspect**
- **T3.5 archived at `12bd9221`**:
  - Lineage: `a56012bd` draft → `7a0db88c` P2 amendment (F1-F3) → `59518e3f` scoped + P3 (F4) → `d5d185bf` Step 4.6 (A-fallback) scope amend (F5) → `325798ca` G7 baseline → `55d9e67b` feat → `71d4d504` closure → `12bd9221` archive.
  - Landed strict six-file scope: new `rule_expr_inspect.py` sibling module with `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, and `PortInspect`; application protocol + SDK exports; SDK inspect dispatch extension with lazy imports; API surface docs rows + runtime `__all__` count correction; and 13 focused tests in `tests/sdk/test_ruleexpr_inspect.py`.
  - Verification: G7 baseline 63 tests OK; post-impl core+inspect gate 76 tests OK; focused cross-slice gate 99 tests OK; ruff clean. `tests.test_public_inference_factgraph_create` has unrelated pre-existing failures at G7 baseline (`meta[confidence]` removal + missing `sdk.inferences` persistence methods).
  - Twenty-five negative-action gates preserved: T3.3 nine + T3.4 six + T3.5 ten, including legacy SDK Rule / Inference dict inspect preservation, no T1.4 DTO changes, no RuleExpr authoring substrate changes, no new error subclass, and lazy SDK dispatch imports.
  - **Third consecutive 0-deviation milestone**: T3.5 is the largest M-class T3 slice so far and still landed with zero scope deviation. Step 4.6 proactively caught F5 (`:exists` strict pseudocode vs T1.4 permissive entity inference) and amended scope before feat — the first proactive Step 4.6 (A-fallback) catch in the T3 cycle.

**T3.6 — Docs and Examples**
- **T3.6 archived at `96baa609`**:
  - Lineage: `314827bb` draft → `a66fdfce` scoped + P3 (F1-F3) → `ab77ce6b` Step 4.6 docs grep clean → `24e55668` G7 baseline → `f8abaad1` docs feat → `2c0ae623` closure → `96baa609` archive.
  - Landed strict docs-only scope: `application/docs/rule.md`, `sdk/docs/00_user_guide.en.md`, `sdk/docs/01_concepts.en.md`, and `sdk/docs/03_rules_and_inferences.en.md`. Python source, tests, `sdk/docs/04_api_surface.en.md`, and `sdk/docs/06_what_if_and_proof.en.md` were untouched.
  - User-facing docs now cover staged imports, `.eq(...)` join syntax, `&` / `|` precedence and parentheses, bool guards, same-name ports no auto-join plus `unjoined_same_name_ports`, and legacy dict inspect vs `RuleExprInspect` return shapes.
  - Verification: G7 baseline 76 tests OK; focused preservation gate 99 tests OK; markdown grep gates clean; ruff not applicable because no Python files changed.
  - **Fourth consecutive 0-deviation milestone**: final initial T3 slice landed with 0 P0/P1/P2/P3 and closes the T3 initial authoring + inspect + docs cycle.

### T3 cycle complete milestone

| Slice | Class | Feat | Deviation |
|---|---|---|---|
| T3.1 | M | `e049c93e` | A-fallback `8de03372` mid-impl reactive |
| T3.2 | S | `2a16dd98` | T-1 bundled into feat (reactive) |
| T3.3 | M | `0b80fe9b` | **0 deviation** (first preemptive) |
| T3.4 | S | `8f248212` | **0 deviation** (second consecutive) |
| T3.5 | M | `55d9e67b` | **0 deviation** (third consecutive + first proactive Step 4.6 catch) |
| T3.6 | S (docs-only) | `f8abaad1` | **0 deviation** (fourth consecutive + T3 cycle final) |

- T3 initial cycle is complete: Stage 1-3 + T3.1-T3.6 all archived locally; later execution lowering remains deferred per D5 §4.8.
- Cadence pattern validated across M/S/M/S/M/S slices: preemptive scope locking, algorithm/validation layer specification, sibling-module isolation, proactive Step 4.6 (A-fallback) catch, docs-only scope discipline, and preservation-test gates.
- Total local T3 cycle span from track plan sync `9c857d0c` through T3.6 archive `96baa609`: 52 commits, 0 pushed **at cycle close** (subsequently mirrored to origin via the post-cycle push gate; see next subsection).
- Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`; unrelated dirty set stayed preserved throughout.

### Push gate executed (2026-05-25)

Single batched push session to `origin` (not `factgraph`), 4 new origin refs:

| Origin ref | Anchor commit | Role |
|---|---|---|
| `origin/milestone/t1-complete-2026-05-23` | `a3411207` (T1.4 archive) | T1 track close immutable ref |
| `origin/milestone/t2-complete-2026-05-23` | `26fa7e54` (T2.3d archive) | T2 track close immutable ref |
| `origin/milestone/t3-cycle-complete-2026-05-24` | `96baa609` (T3.6 archive) | T3 initial cycle close immutable ref |
| `origin/v0.2.0-t3-6-docs-and-examples-2026-05-24` | `0d5b9c22` (handoff doc) | Current cumulative HEAD branch |

Push semantics verified:

- Destination: `origin` only — `factgraph` skipped per Human direction.
- No force push, no ref override; all 4 are NEW refs.
- ~258 net new commits uploaded (275 total ahead of `origin/master` minus ~17 already on origin via Slice 7C chain).
- Sacred `master` / `origin/master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty set (4 M + 1 untracked) stayed unstaged and out of push history.
- Hook bypass not used.
- Session push count: 0 → 1.

Push approach selected by Human: "Cycle milestones" — 3 milestone refs at T1/T2/T3-cycle archive commits + current HEAD branch. Aligns with prior Track 3 milestone pattern; provides per-cycle immutable references + cumulative HEAD for navigation.

### Workflow governance state

`workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` §1.2 was upgraded in `a5bc010a` to a size-class policy:

- S: lightweight blueprint path.
- M: midweight with decision doc when public API / load-bearing choice appears.
- L: full audit/Q/synthesis cadence for high-commitment clusters.

G1-G7 now apply to every class:

- G1 canonical source / parent essay citation.
- G2 shipped source read before drafting.
- G3 file:line citations.
- G4 goal-to-driver mapping.
- G5 documented deviations and class upgrade triggers.
- G6 reviewer spot-check of shipped source.
- G7 pre-implementation precondition checks for boundary-sensitive slices.

Since T2.2, the cross-flip pattern stabilized as user-drafts / Claude-reviews for design artifacts, with clean Step 4.2 drafts for T2.2 and fixture cleanup. T2.3a needed four tightening rounds because it was the largest S-class slice so far, but it still stayed S-class: no Stage 2 decision doc was required, G7 did not trigger escalation, and implementation reviewer pass found 0 P1 findings.

T2.3b inverted the cross-flip pattern (Claude drafts, user reviews) and needed three tightening rounds (v1 1 Blocker + 3 Required → v2 1 Blocker → v3 1 Required acceptance discriminator gap). Step 4.7 came back with 0 P-findings and 1 Nit, and the Nit was explicitly deferred rather than expanded — preserving the clean-impl record. T2.3b also validated a 3-commit impl variant: G7 precondition commit + pre-impl scope amendment commit + single feat (combining impl + tests + 3-layer docs).

**T2.3c extended cross-flip inversion to impl phase as well** (Claude drafts blueprint, Claude implements, user reviews everything) — and the experiment closed with a documented cost-value verdict. 6 Step 4.2 rounds + Step 4.7 v1 + Step 4.7 v2 = **8 review rounds, 25 findings** (2 Blockers + 22 Required + 1 Worth-considering). Compared to user-drafts baseline (T2.2 / fixture cleanup / T2.3a — all 0-1 round Step 4.2). **Verdict: T2.3.d MUST revert to user-drafts pattern**. Cost differential is bounded for blueprint drafting alone (manageable with anti-pattern audit discipline + section-level rewrite propagation) but compounds further when extended to impl phase. Future adapter-shaped slices: user-drafts is the default unless a specific reason to invert. T2.3c also validated the canonical 3-commit impl pattern (G7 precondition → feat main → Step 4.7 fix).

**T2.3d CONFIRMED the cross-flip retrospective verdict.** Codex drafted blueprint + impl, Claude reviewed Step 4.2 + Step 4.7 + did memory consolidation. Total cost: 2 Step 4.2 rounds + Step 4.7 v1 = **5 findings** (0B + 3R + 2WC). **5x cost reduction vs T2.3c** (25 findings / 8 rounds). User-drafts pattern is the default for adapter-shaped slices going forward; cross-flip inversion is reserved for special cases with explicit cost-benefit justification. T2.3d also validated the canonical **5-commit impl pattern with Worth-considering fix**: scoped → G7 → feat → Step 4.7 fix → closure (+ archive = 6 total). G7 (A-fallback) discovery at scoped state for `library(lists)` requirement was textbook — zero re-implementation cost despite a runtime-binary dependency surprise.

**T1.3 validated user-drafts pattern for M-class as well.** First M-class slice in batch. Codex drafted blueprint pair + decision doc + impl; Claude reviewed Step 4.2 + Step 4.7 + did memory consolidation. Total cost: 2 Step 4.2 rounds + Step 4.7 v1 clean (0 findings) = **7 total findings at v1** (0B + 4R + 3WC, all closed at v2). Pattern matches T2.3d S-class; M-class only adds ~2 decision-doc findings (lifecycle + framing relative to parent alternatives) but otherwise same cost-efficiency. T1.3 also validated:(1)**canonical 4-commit M-class impl pattern** (no Step 4.7 fix needed — variant of 5-commit pattern where Step 4.7 fix is OPTIONAL); (2)**decision doc lifecycle pattern** (`proposed` → `reviewed` → `accepted` → `superseded` with impl gating on `accepted`); (3)**A-staged framing for parent §X alternative deferrals** — when parent locks final commitment but pragmatic timing requires deferral, frame as "X-staged" (where X is parent-listed alternative) rather than introducing a new alternative.

**T1.4 closed the T1 Track.** Second canonical 4-commit S-class impl pattern (no Step 4.7 fix). Codex drafted blueprint + impl; Claude reviewed Step 4.2 + Step 4.7 + did memory consolidation. Total cost: 2 Step 4.2 rounds + Step 4.7 v1 clean = **5 total findings at v1** (0B + 1R + 4WC, all closed at v2 + 1 minor WC at scoped). Pattern matches T2.3d S-class exactly. T1.4 also validated:(1) **defense-in-depth validation pattern** (`Rule.as_()` validates + `RuleOccurrence.__post_init__` re-validates idempotently — catches direct construction bypassing factory); (2) **`__getattr__` Python convention preservation** (re-raise `RuleValidationError` as `AttributeError` for `hasattr()` compat); (3) **minor WC in scoped anchor pattern** (non-identifier `rule.id` edge case addressed at Step 4.6 scoped commit, not v3 round — reduces cadence overhead); (4) **stricter downstream validation than upstream** (T1.4 `_OCCURRENCE_ALIAS_RE` stricter than T1.1 `Rule.id` validation; user fallback path documented in invariants + acceptance).

**T3 Stage 1-3 validated the L-class front-loaded cadence.** Codex drafted Stage 1 audit, five Stage 2 decision docs, Stage 3 synthesis, track-plan sync, and the T3.1 blueprint/impl; Claude reviewed each gate. T3.1 used the first RuleExpr per-slice M-class path after L-class synthesis: draft → P2 amend → scoped/P3 → Step 4.6 grep → G7 → A-fallback → feat → clean Step 4.7 → closure → archive. The A-fallback (`8de03372`) confirmed that mid-impl scope correction is valid when it records a discovered import-cycle boundary before the feat commit and preserves the adopted decision's error hierarchy intent.

### Process lessons carried forward

- **Branch isolation:** T1.1 did not use a separate implementation branch; T1.2 onward corrected this. Continue paired blueprint/impl branch discipline.
- **Dirty preservation:** T2.1 had a temporary `git stash` incident; the stash was popped and the original 4 M + 1 untracked dirty set restored. Do not repeat.
- **G7 timing:** T2.2 ran preconditions before implementation but recorded them after. Fixture cleanup fixed the timing by committing the G7 record before fixture edits.
- **G7 amendment discipline:** ProbLog hygiene and fixture cleanup both used scoped amendments when preconditions exposed an unsafe or noisy gate. This is the expected S-class (A-fallback) pattern.
- **Baseline hygiene:** ProbLog import cycle and `meta[confidence]` fixture drift are now cleared. New known baseline: `tests.test_sdk_assertion_record_set` has unrelated `snap.field(...).active.where` drift.
- **Large S-class boundary:** T2.3a validated that a larger S-class substrate slice can remain lightweight when G1-G7 are explicit, preconditions pass, public API is not changed, and SDK/adapters are kept out of scope.
- **Cross-flip inversion blindness:** T2.3b reverted to Claude-drafts / user-reviews and needed three Step 4.2 rounds. Drafter assumption blindness compounded across v1 and v2; v3 closed it only when the reviewer demanded a discriminator test that would actually fail if the corrected algorithm branch were dropped. When inverting cross-flip, the reviewer must explicitly verify each acceptance test discriminates the intended algorithm branch, not just exercises the nominal path.
- **Reusable helper preference:** T2.3b implemented its self-ensure logic by reusing the existing `_ensure_attr_record_binding` helper instead of writing a new injection function. The helper's existing "early-return-on-hit" semantics gave "no duplicate `Type:exists`" behavior for free. When adding new lowering paths, scan for existing helpers with matching semantics first.
- **Step 4.7 Nit discipline:** T2.3b had a single Nit observation (non-aggregate-side AttrRef/BinaryExpr asymmetry in `_lower_compare_with_aggregate`). User chose deferral over expansion. Preserve S-class minimal scope and the 0-P1-fix clean impl record; document the deferral in §10.4 and flag as a follow-up micro-slice rather than expanding after a clean reviewer pass.
- **T2.3c cross-flip inversion cost ceiling reached:** extending cross-flip inversion to BOTH blueprint drafting + impl phase compounds the round count. T2.3c needed 8 review rounds vs user-drafts baseline 0-1. Hard recommendation: T2.3.d MUST revert. Future adapter slices: user-drafts is the default unless a specific reason to invert.
- **T2.3c anti-pattern propagation discipline:** v5→v6 found 3 Required findings all rooted in the same "adapter trusts upstream" framing surviving in header / §2.4 / §3 Non-goals despite v4 §5.7.5 having corrected the core lock. Lesson: section-level rewrites must propagate through ALL referencing sections via anti-pattern grep. v6 mitigation added an explicit grep audit pass for stale phrasing. Pattern generalizes: when changing a contract clause, search the full blueprint for the OLD framing and update every instance.
- **T2.3c rewrite-and-propagate discipline:** v3→v4 found 5 Required findings in sections referencing v3-corrected sections. Lesson: after editing any §N section, grep blueprint for cross-references to §N's content and update. Cross-section consistency check (§1 ↔ §5 ↔ §6 ↔ §7 ↔ §8 ↔ §9 ↔ audit log G1-G7) before each commit.
- **T2.3c 3-commit impl pattern (canonical):** G7 precondition (doc-only, BEFORE impl) → feat main (impl + tests + docs) → Step 4.7 fix (P1/P2 + dead-code removal). Step 4.7 review can surface P1 findings post-feat; focused fix commit covers them without re-running pipeline.
- **T2.3c size estimate calibration:** actual ~1090 LOC vs blueprint §5.7 estimate ~300 LOC. Future adapter-slice §5.7 estimates should account for "mirror-and-extend" patterns (filter-within-aggregate, scope-isolated copy of dispatch logic, per-case wiring across all cmp branches). T2.3.d ProbLog wire likely faces similar size pressure (~150 LOC mirror at minimum).
- **T2.3d user-drafts pattern validated with 5x cost reduction:** 5 findings / 3 rounds total (vs T2.3c 25 / 8 rounds). User-drafts is now the locked default for adapter-shaped slices. Cross-flip inversion remains an option with explicit cost-benefit justification but is no longer the default.
- **T2.3d G7 (A-fallback) discovery exemplary:** G7 #7 smoke proactively caught `library(lists)` import requirement on local ProbLog binary BEFORE any code edits. Blueprint amended at scoped state via 7-section propagation (Outputs + §2.2 + §5.2 + §5.3 + §5.8 + §5.9 + new I2a invariant). Implementation went straight against amended spec. Zero re-implementation cost. **Lesson:** G7 smoke should be substantive (runtime / binary verification, not just file presence checks) when adapter slices have runtime dependencies. The pre-impl smoke cost is paid back many times if it catches dependency issues.
- **T2.3d size calibration validated:** ~281 LOC actual (141 code + 140 tests) vs blueprint estimate 250-450 LOC — delivered at the lower end. ProbLog's `findall/3` runtime scoping naturally eliminates the Souffle "filter-within-aggregate mirror" pattern (~150 LOC saved vs T2.3c). **Lesson:** size estimates for adapter slices should account for engine-native lowering style — Souffle requires explicit mirror-and-extend (large), ProbLog benefits from runtime scope semantics (compact).
- **T2.3d cross-engine semantic mirror discipline:** T2.3c locked C101 empty-set semantics via Souffle `count : { same_body } > 0` guard; T2.3d mirrored the SAME semantics via ProbLog `L = [_|_]` guard. Different syntax, same C101 contract. **Lesson:** when the parent contract is well-locked at substrate (C101 at T2.3a), each adapter slice translates to engine-native idiom without renegotiating semantics. T2.3c P0 ("implement guard now, not deferred") was the right semantic discipline; T2.3d benefited directly.
- **T2.3d canonical 5-commit impl pattern with Worth-considering fix:** scoped → G7 → feat → Step 4.7 fix → closure → archive (6 commits total). Step 4.7 Worth-considering (dead `_is_aggregate` helper) → fix commit `d7e2a650` between feat and closure, mirroring T2.3c v7 dead `_compile_aggregate` removal pattern. Canonical and reproducible across adapter slices.
- **T1.3 first M-class slice cadence validated:** M-class adds decision doc (proposed → reviewed → accepted lifecycle) + Stage 2 process compared to S-class. Cost overhead at v1: ~2 extra findings vs S-class (decision-doc lifecycle + framing relative to parent alternatives). Convergence pattern matches T2.3d: 2 Step 4.2 rounds + Step 4.7 v1 clean. **User-drafts pattern works for M-class** — same cost-efficiency as S-class.
- **T1.3 canonical 4-commit M-class impl pattern (no Step 4.7 fix):** G7 → feat → closure → archive (4 commits when Step 4.7 review passes clean at v1). Variant of T2.3d's canonical 5-commit pattern — Step 4.7 fix is OPTIONAL. When Step 4.7 surfaces findings (e.g., dead helper at T2.3d), impl branch is 5 commits; when clean (T1.3), 4 commits.
- **T1.3 decision doc lifecycle pattern:** `proposed` (at draft) → `reviewed` (Step 4.2 v? pass) → `accepted` (concurrent with Step 4.6 scoped anchor; impl gate unlocked) → `superseded` (if later decision overrides; historical record kept). Lifecycle is in the decision doc itself + invariants in blueprint §6. Implementation strictly blocked until `accepted`. **Lesson:** M-class decision doc Status field is the impl gate — must be designed with explicit lifecycle states, not just a single Status.
- **T1.3 A-staged framing pattern for parent §X alternative deferrals:** when a parent essay locks a final commitment (e.g., "Rule = atomic AND-only" at §325) but pragmatic timing requires deferral, frame the decision as "X-staged" (where X is the parent-listed alternative) rather than introducing a new alternative. This preserves parent framework alignment while explicitly recognizing timing refinement. Decision doc must:(a) cite parent §X alignment; (b) explicitly defer parent's hard promise during staged period; (c) lock the trigger for final flip (e.g., T5 hard-cut). T1.3 used this for parent §3.10 A vs §325 promise tension.
- **T1.3 cross-slice docs guidance reversal pattern:** when a new slice intentionally reverses an earlier slice's docs guidance (T2.3b → T1.3 example: `build_application_rule` from DSL-only to top-level), the reversal must be: (a) acknowledged in blueprint §6 invariant; (b) explicitly handled in §9 docs scope; (c) documented in decision doc §Consequences; (d) reflected in audit log Cross-Slice Contract Preservation table. Otherwise reviewer surfaces the reversal as a P-finding.
- **T1.3 caller-site cost quantification:** Decision doc Alternative cost-benefit analysis should cite **concrete grep counts** rather than abstract "breaks existing callers" language. T1.3 v2 added `15 caller-site` count to Alternative A cost (from `grep -rln "from factgraph.sdk import.*Rule"`). Concrete numbers strengthen alternative comparison.
- **T1.4 second canonical 4-commit S-class pattern (no-Step-4.7-fix confirmed 2x):** T1.3 first validated the 4-commit pattern at M-class; T1.4 second-instance at S-class. **Lesson:** Step 4.7 fix commit is OPTIONAL — skipped when Step 4.7 review surfaces 0 findings. Cadence flexes:4-commit (G7 + feat + closure + archive) if clean Step 4.7;5-commit (G7 + feat + Step 4.7 fix + closure + archive) if findings.
- **T1.4 `__getattr__` Python convention preservation:** For `RuleOccurrence`, `__getattr__(name)` re-raises `RuleValidationError` as `AttributeError` when name is not a declared port. **Lesson:** `__getattr__` MUST raise `AttributeError` (not other types) so Python `hasattr()` + attribute probing work. Explicit port lookup via `occ.port(name)` raises `RuleValidationError` for explicit caller errors. Dual-path pattern preserves both Python convention (attribute access) and explicit caller-error signaling.
- **T1.4 defense-in-depth validation pattern:** `Rule.as_(alias)` validates alias before constructing `RuleOccurrence`; `RuleOccurrence.__post_init__` validates again (idempotent on already-validated values, but catches direct `RuleOccurrence(rule, alias=invalid)` construction bypassing `Rule.as_()`). **Lesson:** when a DTO can be constructed via multiple paths (factory method + direct constructor), validate in `__post_init__` for defense-in-depth even if all factory paths already validate.
- **T1.4 v2 scoped anchor edge case lock:** v2 review surfaced 1 minor Worth-considering about non-identifier `rule.id` causing `rule.as_()` default to fail. Codex addressed in Step 4.6 scoped anchor commit (not in v3 round) by adding edge case acceptance test + §6 invariant note. **Lesson:** minor Worth-considerings can be addressed in scoped anchor commit alongside `Status: draft → scoped` transition, avoiding an extra v3 round. Reduces cadence overhead when fix is small + uncontroversial.
- **T1.4 stricter downstream validation than upstream:** parent §3.6 commitment 6 says default alias = `rule.id` but T1.1 `Rule.id` accepts any non-empty string while T1.4 `_OCCURRENCE_ALIAS_RE` enforces `[A-Za-z][A-Za-z0-9_]*`. T1.4 lock: non-identifier `rule.id` → `rule.as_()` raises, user falls back to `.as_("custom_alias")`. **Lesson:** when a downstream slice's validation is stricter than its upstream input, document the fallback contract explicitly in invariants + acceptance tests. Don't silently swallow upstream values that would fail downstream validation.
- **T3 L-class audit-to-synthesis cadence validated:** T3 ran full Stage 1 audit → Stage 2 D1-D5 decisions → Stage 3 synthesis → track-plan sync before per-slice blueprinting. This is now the reference pattern for high-commitment clusters: do not start a T3.x blueprint until the synthesis ladder and cross-doc sync are explicit.
- **T3.1 neutral SDK error module A-fallback:** `RuleExprError(SDKDSLError)` was required by adopted D1, but direct application protocol imports from SDK would create a cycle. The neutral `factgraph._sdk_errors` module plus SDK re-export preserved class identity and unblocked implementation. Reuse this pattern when application-layer code must satisfy SDK-facing exception hierarchy contracts without importing SDK modules.
- **T3.1 pre-impl grep discipline:** Step 4.6 grep proved no existing truthiness/operator/export/catch-site conflict before adding `Rule.__bool__`, `Rule.__and__`, and `Rule.__or__`. For slices adding Python dunder behavior, pre-impl grep is mandatory even after Stage 1 audit.
- **T3.1 pytest SIGSEGV handling:** pytest segfaulted in the local environment, while unittest gates passed and matched G7 baseline. The correct cadence was to lock unittest as the runner for this slice, record the pytest issue as out-of-scope tooling drift, and investigate separately rather than blocking feature closure.
- **T3.1 P3 follow-up discipline:** Step 4.7 surfaced only minor type-precision items. When review has 0 P0/P1/P2 and the fixes naturally touch the next adjacent slice's files, defer them explicitly to that slice instead of polluting closure/archive with code churn.
- **T3.2 cross-slice supersedence trace:** When a later slice deliberately invalidates an earlier acceptance test, record it in §6 invariants, §7 acceptance, §8 implementation plan, and audit-log reviewer focus before implementation. T3.2 did this for T3.1 `test_duplicate_operands_preserve_multiplicity`, preserving multiplicity semantics through explicit aliases while rejecting bare repeated Rule operands.
- **T3.2 (A-fallback) discipline drift lesson:** `RuleOccurrence.__and__` / `__or__` was a necessary discovered additive method change for explicit-alias infix expressions, but it was bundled into feat instead of a pre-feat blueprint amendment. Closure §10 records this as process-discipline drift. Future T3.x slices discovering operator/dunder scope expansion must pause for a doc-only (A-fallback) scope amendment before feat.
- **T3.2 validation diagnostics pattern:** Aggregate expression-scope diagnostics with stable ordering when multiple authoring issues can coexist; fail immediately only for operand construction failures that prevent representing the operand (non-identifier default alias). This avoids fix-one-error-per-run churn without hiding invalid default-alias guidance.
- **T3.3 preemptive scope locking pattern:** T3.2 T-1 drift lesson was applied in T3.3 §5.2 by explicitly locking `RulePortRef.eq()` as an additive method on the T1.4 frozen DTO before implementation. Result: 0 deviation. Future slices should pre-lock any method/dunder additions implied by prior drift.
- **T3.3 0-deviation milestone:** first T3 feat with 0 P0/P1/P2/P3 at Step 4.7. The winning pattern was preemptive scope + explicit validation-layer placement + algorithm pseudocode + canonical equality spec in the blueprint.
- **T3.3 cadence cycle most efficient:** 7 commits total versus T3.1 9 and T3.2 8; no P2 amendment, no A-fallback, no Step 4.7 fix. Strong evidence that lessons from prior slices now land in draft/scoped stages.
- **T3.4 repeatable preemptive scope locking:** T3.4 reused T3.3's pattern with six explicit "no" locks and one explicit "yes" lock in §5.5, strict two-file scope, and no new public export. Result: second consecutive 0-deviation feat.
- **T3.4 second consecutive 0-deviation milestone:** 0 P0/P1/P2/P3 at Step 4.7 with 72 cross-slice tests and ruff clean. The pattern is now repeatable, not slice-specific: preemptive scope lock + algorithm spec + validation ordering + stable diagnostics.
- **T3.4 scope-boundary test discipline:** `test_join_by_ports_preserves_export_scope` actively asserts no new SDK export. Future slices should test important negative scope locks directly when cheap, not only test positive behavior.
- **T3.5 third consecutive 0-deviation milestone:** largest M-class T3 slice landed with 0 scope deviation after 31 acceptance gates, 25 negative-action gates, 99 focused cross-slice tests, and ruff clean. The preemptive pattern holds across small, medium, and large T3 scope.
- **T3.5 proactive Step 4.6 (A-fallback) catch:** Step 4.6 grep found F5 before feat — T1.4 `_find_entity_ref_type_in_atom(...)` accepts any `:exists` term while T3.5 §5.6 initially required exactly one term. Scope amend `d5d185bf` aligned inspect pseudocode before implementation, avoiding mid-impl drift.
- **T3.5 sibling-module scope economy:** estimated 8-file scope landed in 6 files because `rule_expr_inspect.py` isolated inspect traversal and kept `rule_expr.py` / `test_rule_expr.py` untouched. Prefer sibling modules when a public projection layer is large but can consume existing authoring substrate read-only.
- **T3.6 fourth consecutive 0-deviation milestone:** docs-only final slice landed with 0 P0/P1/P2/P3 and completed the initial T3 authoring + inspect + docs cycle.
- **T3.6 strict docs-only scope discipline:** 4 docs files changed, 0 Python files, 0 tests, and explicit no-touch locks for `04_api_surface.en.md` + `06_what_if_and_proof.en.md` held through Step 4.7.
- **T3.6 preservation-test discipline for docs-only slices:** even with no Python edits, the slice ran 76-test G7 baseline and 99-test preservation gate to prove user-facing docs did not mask regressions.
- **T3 aggregate cadence lesson:** preemptive scope locking + algorithm specification + sibling module isolation + proactive Step 4.6 catch + docs-only discipline spans M/S/M/S/M/S and is repeatable, not slice-specific.

### Recommended next work

- **T3 INITIAL CYCLE COMPLETE** — T3.1-T3.6 are all archived. Later execution lowering remains a separate tranche deferred by D5 §4.8 and needs a fresh decision before blueprinting.
- **Step A2 cadence lesson sediment** — update `feedback_audit_to_archive_cadence.md` with the T3 cycle pattern: 4 consecutive 0-deviation feats, proactive Step 4.6 catch, sibling-module isolation, and docs-only scope discipline.
- **Step A3 next-track decision review** — choose among T3 later tranche, T4 Head + closed-head, T5 EvaluateResult/Semantics/hard-cut/WhyNot redesign, push gate evaluation, tooling tasks, or a hybrid.
- **T3 later execution tranche** — RuleExpr execution lowering / adapter integration deferred per D5 §4.8; class TBD (M or L) and requires a fresh decision before blueprinting.
- **T4 Head + closed-head** — 0% started; likely next independent capability track after T3 initial cycle.
- **T5 EvaluateResult + Semantics + legacy hard-cut + WhyNot** — 0% started; largest redesign zone and trigger for T1.3 final `Rule` flip.
- **T2.3.b1 / T2.3.e (Nit follow-up, deferred from T2.3b)** — S-class micro-slice for `_lower_compare_with_aggregate` non-aggregate side AttrRef/BinaryExpr handling.
- **Pytest SIGSEGV tooling investigation** — independent task; T3 locked unittest fallback and did not block on pytest runner instability.
- **Push / publish gate** — T1/T2 + T3.1-T3.6 archived slices and memory sync commits remain local: 52 commits across the T3 cycle, 0 pushed. Sacred `master` untouched throughout the entire T3 cycle. Push gate evaluation pending Step A3 decision review.

<!-- Historical 2026-05-13 official docs state follows. -->

最后更新:2026-05-13(official kernel docs quickstart-only consolidation implemented locally; source pending commit, not pushed)

## 当前阶段(2026-05-13 — OFFICIAL KERNEL DOCS QUICKSTART-ONLY CONSOLIDATION IMPLEMENTED LOCALLY)

**Current local source state:** working tree includes the implemented quickstart-only official docs consolidation; commit pending at time of this memory update.

**Remote baseline:** `origin/master = 293b98a5` before this consolidation commit.

**Local publish state:**
- Worktree has one pre-existing dirty notebook:
  `examples/archive/01_sdk_basics.ipynb`.
- The official docs slice is implemented and archived locally, but not pushed.

**Official docs slice state:**
- Archived blueprint:
  `docs/blueprints/archive/2026-05-13_official-kernel-docstrings-and-tutorials.md`.
- Archived audit:
  `docs/blueprints/archive/2026-05-13_official-kernel-docstrings-and-tutorials.audit.md`.
- G0 decisions locked docstrings-first, official Markdown under
  `docs/official/kernel/`, Page Brief discipline, kernel-only release
  boundary, and multi-session completion. G2.20 scope adjustment changed the
  Markdown tree to quickstart-only.

**Final official kernel docs tree:**
- `docs/official/kernel/index.md`
- `docs/official/kernel/quickstart/index.md`
- `docs/official/kernel/quickstart/first-factgraph.md`
- `docs/official/kernel/quickstart/schema.md`
- `docs/official/kernel/quickstart/read-write.md`
- `docs/official/kernel/quickstart/rules-and-inferences.md`
- `docs/official/kernel/quickstart/semantics.md`
- `docs/official/kernel/quickstart/persistence.md`
- `docs/official/kernel/quickstart/namespace-map.md`

**Important docs-as-validation outcome:**
- While validating `quickstart/persistence.md`, the tutorial round-trip exposed
  a real product bug: loaded authoring `Rule` / `Inference` objects could not
  execute because already-lowered `where` IR was lowered again.
- Fix commit: `63348765 fix(sdk): preserve loaded authoring where payloads`.
- Regression added to `test_authoring_asset_persistence_facade.py`.

**Latest validation:**
- All Python blocks in `docs/official/kernel/quickstart/*.md` extracted and
  executed OK.
- Official docs baseline: 7/7 OK.
- Focused schema/read-write/rules/persistence/semantics preservation suites:
  276/276 OK.

**Remaining official docs work:**
- Commit and push the implemented quickstart-only consolidation.
- Optional future docs work should be a new scoped docs slice, not a continuation
  of the archived official-kernel-docstrings-and-tutorials blueprint.

<!-- Historical 2026-05-13 confidence/evidence cleanup state follows. -->

最后更新:2026-05-13(confidence/evidence meta release cleanup published; source `843cf515`)

## 当前阶段(2026-05-13 — CONFIDENCE / EVIDENCE META RELEASE CLEANUP PUBLISHED)

**Current source state:** `origin/master = 843cf515`.

**Published slice:**
- `origin/milestone/confidence-evidence-meta-release-cleanup-2026-05-13 = 843cf515`.
- G0-G4 confidence / evidence meta release cleanup slice is implemented,
  archived, and published.
- This is a defensive pre-release cleanup that cuts legacy generic confidence
  propagation while preserving adapter-native uncertainty lanes.

**Release refs remain intact:**
- `origin/release/0.1.x = e996aa5b`.
- `v0.1.0-rc.1`, `v0.1.0-rc.2`, and `v0.1.0-rc.3` remain untouched.

**Landed behavior:**
- `CandidateSet.confidence` and `CandidateSet.confidence_kind` remain
  internal/session compatibility carriers.
- Runtime accept remains parse-compatible with old candidate payloads that echo
  `confidence` / `confidence_kind`.
- `accept(...)` no longer writes candidate confidence fields into assertion
  meta by default.
- Generic `meta.confidence` remains a ledger meta row but is not projected into
  shared derived annotations.
- Legacy confidence differences do not affect duplicate detection.
- ProbLog export no longer falls back to generic `meta.confidence`.
- PyReason sessions keep adapter-native bound annotations and filter generic
  confidence metadata from shared projections.
- Service candidate DTOs and candidate inventory omit legacy confidence fields
  by default.
- Candidate evidence trees do not lift generic assertion `meta.confidence` into
  default evidence/certainty display.

**Verification:**
- Confidence cleanup baseline: 11/11 OK.
- Full kernel discovery: 2198 OK / 1 skipped.
- Post-publish verification confirmed `origin/master`, the milestone branch
  ref, release branch, and rc tags.

**Memory detail:** [project_confidence_evidence_meta_release_cleanup_implemented.md](./project_confidence_evidence_meta_release_cleanup_implemented.md).

**Remaining independent design lines:**
- future explicit confidence/certainty/probability redesign if needed;
- explain/evidence user surface;
- query persistence;
- relationship schema extension;
- identity changes;
- field defaults / nullability / backfill;
- destructive schema lifecycle (`delete` / `deprecate` / `update` / `migrate`);
- class-less dynamic workspace load.

<!-- Historical 2026-05-13 schema field-add lifecycle state follows. -->

最后更新:2026-05-13(schema field-add lifecycle published; source `925354c6`)

## 当前阶段(2026-05-13 — SCHEMA FIELD-ADD LIFECYCLE PUBLISHED)

**Current source state:** `origin/master = 925354c6`.

**Published slice:**
- `origin/milestone/schema-field-add-lifecycle-2026-05-13 = 925354c6`.
- G0-G4 schema field-add lifecycle slice is implemented, archived, and
  published.
- This is the second post-rc.3 schema mutation slice after additive
  entity-class schema mutation.

**Release refs remain intact:**
- `origin/release/0.1.x = e996aa5b`.
- `v0.1.0-rc.1`, `v0.1.0-rc.2`, and `v0.1.0-rc.3` remain untouched.

**Landed behavior:**
- `fg.schema.add(...)` accepts same-entity replacement classes that add
  non-identity fields.
- `SchemaAddResult` now records `added_fields`.
- Superseded entity classes and field descriptors raise `SDKStoreError`; use
  the post-add class object.
- Existing assertions are not backfilled; missing added single fields read as
  `None`, and missing added multi fields read as `()`.
- Ledger and registry digest anchors reuse the schema mutation lifecycle.
- Workspace manifests remain save-time state until explicit `fg.save(...)`.

**Verification:**
- `test_schema_field_add_lifecycle.py`: 33/33 OK.
- Combined schema/lifecycle preservation + SDK invariant stack: 217/217 OK.
- Post-publish verification confirmed `origin/master`, the milestone branch
  ref, release branch, and rc tags.

**Memory detail:** [project_schema_field_add_lifecycle_implemented.md](./project_schema_field_add_lifecycle_implemented.md).

**Remaining independent design lines:**
- relationship schema extension;
- identity changes;
- field defaults / nullability / backfill;
- destructive schema lifecycle (`delete` / `deprecate` / `update` / `migrate`);
- query persistence;
- explain/evidence user surface;
- class-less dynamic workspace load.

<!-- Historical 2026-05-13 schema mutation lifecycle state follows. -->

最后更新:2026-05-13(schema mutation lifecycle published; source `f0279791`)

## 当前阶段(2026-05-13 — SCHEMA MUTATION LIFECYCLE PUBLISHED)

**Current source state:** `origin/master = f0279791`.

**Published slice:**
- `origin/milestone/schema-mutation-lifecycle-2026-05-13 = f0279791`.
- G0-G4 schema mutation lifecycle slice is implemented, archived, and published.
- This is the first post-rc.3 slice milestone.

**Release refs remain intact:**
- `origin/release/0.1.x = e996aa5b`.
- `v0.1.0-rc.1`, `v0.1.0-rc.2`, and `v0.1.0-rc.3` remain untouched.

**Landed behavior:**
- `fg.schema.add(EntityCls)` and `fg.schema.add(schema_classes=[...])` are public.
- `SchemaAddResult(old_digest, new_digest, added_entities)` is exported from `kernel.sdk`.
- New application layer module: `kernel.application.schema_mutation_runtime`.
- Additive schema extension updates in-memory SDK/core state immediately.
- Ledger and registry schema digests are anchored before mutation and updated after validation.
- Workspace manifests remain save-time state; `fg.save()` records the new digest.
- `fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, and `fg.schema.deprecate` remain absent.

**Verification:**
- `test_schema_mutation_lifecycle.py`: 39/39 OK.
- Lifecycle/assets preservation: 88/88 OK.
- SDK invariants: 57/57 OK.
- Post-publish verification confirmed `origin/master`, the milestone branch ref, release branch, and rc tags.

**Memory detail:** [project_schema_mutation_lifecycle_implemented.md](./project_schema_mutation_lifecycle_implemented.md).

**Remaining independent design lines:**
- destructive schema lifecycle (`delete` / `deprecate` / `update` / `migrate`);
- query persistence;
- explain/evidence user surface;
- class-less dynamic workspace load;
- package/workspace convergence;
- legacy docs hygiene, including `docs/blueprint_history/` disclaimers if needed.

<!-- Historical 2026-05-13 rc.3 publish state follows. -->

最后更新:2026-05-13(`v0.1.0-rc.3` published; source `f49ccc58`, release commit `e996aa5b`)

## 当前阶段(2026-05-13 — v0.1.0-rc.3 PUBLISHED)

**Current source state:** `origin/master = f49ccc58`.

**Release state:**
- `origin/release/0.1.x = e996aa5b`.
- `v0.1.0-rc.3` annotated tag object = `efb44868`.
- `v0.1.0-rc.3^{}` = `e996aa5b`.
- `origin/milestone/rc-0.1.0-rc.3-2026-05-13 = f49ccc58`.

**Verification:**
- Final dry-run from current HEAD `f49ccc58`: projection `361` files, staging verification `1633` OK / `1` skipped.
- Live publish completed through `scripts/release.sh v0.1.0-rc.3 --source-ref HEAD --yes`.
- Post-publish `git ls-remote` confirmed `master`, `release/0.1.x`, `v0.1.0-rc.3`, and the rc.3 milestone branch.
- Prior milestone branch refs remain present.

**Release surface included:**
- public `Inference` vocabulary;
- inference service/registry vocabulary;
- semantics wrappers and PyReason branch bounds;
- authoring asset persistence facade;
- FactGraph workspace lifecycle.

**Memory detail:** [project_v0_1_0_rc3_published.md](./project_v0_1_0_rc3_published.md).

**Important: design not complete.** rc.3 is a release checkpoint, not lifecycle
/ assets design closure. Remaining independent design lines are recorded in
[project_lifecycle_assets_remaining_after_rc3.md](./project_lifecycle_assets_remaining_after_rc3.md).
Recommended next blueprint: schema mutation (`fg.schema.add/deprecate/update`
or migration vocabulary), with query persistence and explain/evidence kept as
separate future threads.

<!-- Historical 2026-05-11 ReadPolicy state follows. -->

最后更新:2026-05-11(`v0.1-readpolicy-call-site-migration-impl-2026-05-11 @ b13adda4`;**ReadPolicy call-site migration implemented + archived**, rc.3 dry-run passed, no push performed)

## 当前阶段(2026-05-11 — READPOLICY CALL-SITE MIGRATION IMPLEMENTED + ARCHIVED)

**当前工作树:** `/Users/zhenzhili/hnsm-backend/.claude/worktrees/laughing-blackburn-c072da` on `v0.1-readpolicy-call-site-migration-impl-2026-05-11 @ b13adda4`.

**Blueprint state:** `docs/blueprints/archive/2026-05-11_readpolicy-call-site-migration.md` is `implemented`; paired audit archived. Active blueprint pair removed from `docs/blueprints/active/`.

**Commit chain after scope-freeze `73033ce`:**
- `be95373` — `chore(release): bump version to 0.1.0rc3`
- `3effae6` — `feat(kernel): replace ViewSpec core type with ReadPolicy`
- `c3f8596` — `feat(sdk): migrate ReadPolicy call-site surface`
- `448709b` — `feat(service): migrate runtime view policy wire surface`
- `f1510cf` — `test(sdk): align invariants with ReadPolicy export`
- `0b6004e` — `docs(sdk): explain ReadPolicy and frozen views concepts`
- `e9b84b7` — `docs(sdk): update ReadPolicy API references`
- `ea803f1` — `docs(sdk): update user guide for ReadPolicy views`
- `c3271a2` — `docs(examples): refresh assertion views notebook for ReadPolicy`
- `1898fa1` — `docs(service): rename runtime queries policy contract`
- `42b7c98` — `test(release): add legacy view syntax gate`
- `e80f8cf` — `docs(blueprints): close ReadPolicy call-site migration blueprint`
- `f8d2a5d` — `docs(blueprints): archive ReadPolicy call-site migration blueprint`
- `b13adda` — `fix(scripts): require ripgrep in legacy view syntax gate`

**Final shipped behavior:**
- `ViewSpec` removed from `kernel.core.store.types` and not importable from `kernel.sdk`.
- `ReadPolicy` is the read-time resolution/display policy DTO, defined in `kernel.core.store.types`, re-exported from `kernel.sdk`; `kernel.sdk.__all__` is 35→36 with only `ReadPolicy` added.
- `ReadPolicy` fields: `respect_revocations: bool = True`, `confidence_strategy: "max"|"mean"|"median"|"prefer_source" = "max"`, `prefer_source: str | None = None`.
- `find(...)` and `run(...)` use value-only `policy=ReadPolicy(...) | None`; dict, str, and `FrozenAssertionView` are rejected.
- `run(..., view=...)` tombstones old syntax, including explicit `view=None`; `return_display_meta=True` requires non-None `policy`.
- `fg.views` is frozen assertion membership only; no built-in/reserved `default`; no policy payloads.
- Service runtime removed named policy registry, `RuntimeSession.views`, `view_name`, and 5 runtime-view endpoints; wire policy is inline `policy` with `respect_revocations`.

**Verification:**
- Critical rejection/absence suite: 11 OK, including `ViewSpec` absence and R4 `run(view=None)` tombstone.
- Focused ReadPolicy/frozen/service suite: 67 OK.
- Kernel unittest discovery: 1848 OK / 1 skipped.
- `scripts/check_legacy_view_syntax.sh`: exits 0 with `rg`; exits 2 with a clear error if `rg` is absent (fixed in `b13adda`).
- Release dry-run passed: `./scripts/release.sh v0.1.0-rc.3 --source-ref v0.1-readpolicy-call-site-migration-impl-2026-05-11 --dry-run --yes`; projected verification reported 1630 tests OK / 1 skipped.
- Broad service/ECSS discovery still carries the pre-existing audit/application circular-import noise; targeted service policy tests pass.

**Publish state:** no push, no merge to `master`, no rc.3 tag, no release publish yet. Next publish action requires explicit user authorization.

<!-- Historical 2026-05-09 post-L state follows. -->

## 当前阶段(2026-05-09 — POST-L SDK ERGONOMICS REDESIGN PUBLISHED)

**当前工作树:** `/Users/zhenzhili/hnsm-backend` 当前停在 impl branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09 @ 30810c9`(pre-publish audit-fix HEAD).

**两个 publish refs 已推送到 origin:**
- `origin/v0.1-post-l-sdk-ergonomics-redesign-2026-05-09` @ `30810c9`(standalone)
- `origin/v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-post-l-redesign-2026-05-09` @ `30810c9`(Path B 6th immutable combined snapshot,extends 5th at `d4ceb3e`)

**最终 surface(已发布):**
- `FactGraph` 进入 `kernel.sdk.__all__`;`FactGraph is SDKStore` literal alias。
- `kernel.sdk.__all__` 从 34 → 35,唯一新增导出是 `FactGraph`;9 个 manager classes 全部私有(包括预存的 `_SDKViewsManager`,pre-publish Blocker 2 fix 加上 `__setattr__` 守卫)。
- 8 top-level taxonomy namespaces + 2 `what_if` sub-namespaces: `schema`, `read`, `write`, `eval`, `what_if`, `what_if.fact_overlay`, `what_if.rule`, `audit`, `package`, `views`。
- Flat `SDKStore.<method>` / `FactGraph.<method>` 永久保留为 foundational API;无 deprecation warning,无 removal plan,无 package rename。
- 9 SDK shells (`kernel/sdk/shells/`) 行为未重写;manager methods 只 `*args, **kwargs` delegate 到既有 flat methods(call-compatible,not signature-identical;per Clarify 1 narrowing)。

**Commit chain on impl branch:**
- `af99c87` — Phase 1: `FactGraph` alias + 9 namespace managers + alias parity / namespace shape tests。
- `31889ae` — Phase 2: taxonomy-first docs + redesign invariants。
- `380e391` — Phase 2 audit-fix: README stale L Direction boundary paragraph + stale test baseline fixed;regression lint added。
- `eb0fdae` — Phase 3 close-out: 填 §9,归档 blueprint,更新 archive inventory + memory,本地 prepare publish refs。
- `30810c9` — pre-publish audit-fix: 2 Blockers + 4 Clarify + 3 Minors 全部修;archived blueprint amendments(Clarify 1/2 + Minor 3 narrowing);ruff cleanup of inherited unused imports(Clarify 3);regression-prevention lint added(Blocker 1 prevention)。**PUBLISHED HEAD**.

**Pre-publish audit catches(经验记录):**
1. Blocker 1 — `04_api_surface.md` + `.en.md` taxonomy code examples 用错 canonical signatures(`fg.what_if.check(rule, binding)` 应该是 `(derivation, binding)`;`fg.what_if.fact_overlay.check(support, overlay)` 缺 2 个 positional args)。
2. Blocker 2 — `_SDKViewsManager` 没有 `__setattr__` 守卫,违反 8-namespace 教学 taxonomy 的 read-only invariant。
3. Clarify 1 — manager `*args, **kwargs` 是有意选择(call-compatible not signature-identical);archived blueprint §8 narrowing 已加。
4. Clarify 2 — Tier 1 docs 实际是 "taxonomy intro note + cross-ref + flat-form foundational body",不是逐示例 taxonomy-first;archived blueprint §5.5 narrowing 已加。
5. Clarify 3 — full `ruff check src/kernel` 在 2 个 inherited 测试文件 fail(unused imports);auto-fix 已清。
6. Minor 1 — 4 个 source files 引用 stale `docs/blueprints/active/` 路径;已更新到 `archive/`。
7. Minor 2 — `application/01_overview` Batch 8 wording outdated;已 reframe 为 "historical Batch 8 state, since updated by L Direction G1-G5 + post-L redesign"。
8. Minor 3 — archived blueprint "no `DeprecationWarning` references in any doc" overbroad claim;已 narrow 到 "no flat-vs-nested DeprecationWarning"(预存的 `row_format='tuple'` 警告 separately scoped)。

**Verification at published HEAD `30810c9`:**
- Focused redesign + G1-G5 invariant suite: **100 OK**(98 + 2 new tests:views read-only + canonical-signature lint)。
- Full `ruff check src/kernel`: ALL CHECKS PASSED(post Clarify 3 cleanup)。
- `git diff --check` clean。
- `git ls-remote origin` 验证两个 published refs 都在 `30810c9`。

**Sacred + 5 prior L snapshots verified untouched at publish:**
- `origin/master 81c6f775`,`origin/v0.1-oss-prep f5ade36d`
- G1 `d6716a01`,G4 `acb5a6ed`,G2 `d6583907`,G3 `cb6d3bd8`,G5 `d4ceb3eb`

**Forward triggers:**
- Optional notebook/example taxonomy updates 可机会主义跟进;current state 保留 notebooks 不变。
- `factpy` package rename 仍 deferred 到独立 scoped blueprint。
- Flat method deprecation/removal 仍显式 out of scope,直到 future user signal 重开。
- Per-method explicit manager signatures 仍 deferred 直到具体 IDE-hint consumer signal 出现。
- Per-body Tier 1 docs rewrite(vs current intro-note treatment)仍 deferred 直到 consumer signal 给出 churn justification。

<!-- Historical 2026-05-09 G5 published state follows. -->

## 当前阶段(2026-05-09 — L DIRECTION G5 PROOFFRAME DIFF SDK SHELL PUBLISHED; **L SEQUENCE CLOSED ON ORIGIN**)

**当前工作树:** `/Users/zhenzhili/hnsm-backend` 当前停在 topic branch `codex/v0.1-l-g5-round-events-proofframe-diff-2026-05-08` @ `d4ceb3e`. G5 3-phase implementation + 7-commit Step 0 lock chain + pre-publish polish done (draft seed `90c5c05` → §5.1 `2b493b1` → §5.3 `75f2826` → §5.2+§5.4 batch `b1ff0e6` → §5.5+§5.6+§5.7 batch `150d740` → §5.8+§5.9 batch `2f81b56` → scope-freeze `5fe0e6b` → Phase 1 `a961e1d` → Phase 2 `754d2a2` → Phase 3 close-out `480ebc6` → pre-publish polish `d4ceb3e`).

**G5 published snapshots (verified post-push 2026-05-09):**
- `origin/v0.1-l-g5-round-events-proofframe-diff-2026-05-08` @ `d4ceb3e` — G5-only.
- `origin/v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-2026-05-08` @ `d4ceb3e` — Path B combined (G1+G4+G2+G3+G5 cumulative, **5th immutable Path B snapshot**).
- Prior snapshots unchanged: G3-only and G3 combined still at `cb6d3bd`; G2-only and G2 combined still at `d658390`; G1-only at `d6716a0`; G4-only at `acb5a6e`; sacred `master` @ `81c6f775` and `v0.1-oss-prep` @ `f5ade36d` untouched. Only the two new G5 refs were added.

**Convention reminder — `memory/current.md` tracks topic-branch HEAD, not published snapshot HEAD.** This file is updated on the topic branch *after* a publish event, so at any published snapshot HEAD the file naturally lags by 1 commit (the post-publish memory sync). Recorded in G3 archive audit log post-archive addendum 2026-05-08 and continues for G5.

**G5 post-publish verification round (2026-05-09) — option B fix landed forward-only on topic.** Multi-agent read-only audit on the published HEAD `d4ceb3e` found 2 Blockers + 2 Minors, all doc/inventory drift from incomplete pre-publish polish — the polish updated SDK shell + SDKStore docstring + invariant test + §5.8 lock body + §9.4 test catalogue but missed (a) SDK API docs CN/EN per-method paragraph for `diff_proof_frames` (still listed 7-path / omitted `.include_unchanged`), (b) archive README G5 inventory row (7-path / 5 inline / 16 contract tests), (c) archived blueprint §7 acceptance line for §5.8, (d) archived blueprint §5.9 / §9.4 falsifier text. **Runtime at `d4ceb3e` is correct** — `isinstance(.., bool)` strict check is in place; consumer with `include_unchanged="yes"` gets `SDKStoreError` (safer than the docs claimed). Per option B (G3 structural-lag convention), published refs `d4ceb3e` stay immutable; doc polish lands forward-only on G5 topic; future Path B combined snapshot picks up the fix. **Published `d4ceb3e` has correct runtime but stale 7-path wording in 4 doc/inventory locations** until next combined snapshot.

### G5 outcome

- **Shipped SDK method (1):** `SDKStore.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False) -> ProofFrameDiff`.
- **Input contract:** two non-empty round-id strings + two raw `tuple[RoundEvent, ...]` (`kernel.audit.round_events.RoundEvent`) + optional `tuple[WarningDTO, ...]`. SDK shell is pure — no Store / no registry / no engine arg / no IO. Mirrors `kernel.audit.proof_frame_diff.build_proof_frame_diff(...)` 1:1.
- **Return contract:** raw application-canonical `ProofFrameDiff` (`kernel.audit.proof_frame_diff.ProofFrameDiff`); `kernel.sdk.__all__` length still 34.
- **Method naming:** Group A `diff_proof_frames` chosen over Group B per §5.7 falsifier (Group B would collide with the DTO name).
- **Recorder lifecycle deferred per §5.1:** `start_round` / `record_round_event` / `finalize_round` stay at `kernel.audit.round_events` advanced importable. **Capture path is `from kernel.audit.round_events import ...`** (existing UX, not changed by G5).
- **Cross-cutting precedent layer rule encoded verbatim in §6 invariants** (G5 architectural deliverable): "**frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary**" — keeps `kernel.audit` frozen DTOs IN scope; preserves G3 substrate-IR-out carve-out.
- **Error paths (7):** `$.diff_proof_frames.{round_a_id,round_b_id,round_a_events,round_b_events,warnings,request,}` + base. NO `ProtocolShapeError` / `.dependencies` / `CapabilityHelperError` paths.
- **9-shell Sibling discipline scope** active forward-only.
- **Blueprint:** `docs/blueprints/archive/2026-05-08_l-direction-g5-round-events-proofframe-diff.md` + `.audit.md` archived and marked `implemented`.
- **Verification basis:** post-Phase-2 1683 OK / 1 skipped (was 1661/1 at G3 polish baseline `2f81b56` topic tip; +22 new G5 tests); ruff clean; `git diff --check` clean.

### G5 follow-up

- G5-only + Path B combined snapshots published 2026-05-09 from pre-publish polish HEAD `d4ceb3e`. **L Direction sequence CLOSED on origin.** No remaining publish action.
- Pre-publish verification round caught + fixed at `d4ceb3e`: 1 Blocker (include_unchanged isinstance(bool); 7-path → 8-path) + 1 Clarify (overview docs) + 3 Minors (checkboxes / docstring refs / test count). 18 contract + 6 invariants now; full kernel 1685 OK / 1 skipped at published HEAD.
- **Post-L SDK ergonomics redesign blueprint (per `feedback_sdk_ergonomics_redesign_target`) is now UNBLOCKED.** With L Direction complete on origin, the redesign blueprint may revisit `SDKStore.<method>` flat pattern and consider OpenAI-style `Client.<family>.<method>` namespace migration.
- Sacred branches remain untouched: `master` and `v0.1-oss-prep`.
- G1 + G4 + G2 + G3 published snapshot branches remain untouched at `d6716a0` / `acb5a6e` / `d658390` / `cb6d3bd`.
- Watch for a post-publish verification round on the new G5 published HEAD (G1/G4/G2/G3 each had one; G5's pre-publish round caught the Blocker, but a fresh round on the published HEAD remains cheap insurance).
- Post-L hygiene tracker (carry-forward; not blocking redesign):
  - `store.py:1024` (`run`) and `store.py:1154` (`evaluate`) call `_resolve_runtime_registry` directly without the shared boundary normalizer (originally G3 verification-round addendum).
  - `kernel.audit.proof_frame_diff` cold-import circularity worked around inline in `test_sdk_proof_frame_diff.py` (G5 Phase 1 implementation discovery).

<!-- Historical 2026-05-08 G3 publish state follows. -->

最后更新:2026-05-08(`v0.1-l-g3-rule-overlays-2026-05-08` @ `cb6d3bd` published;G3 Rule Overlay SDK shells implemented + archived + verification-round Blocker fix + published snapshot)

## 当前阶段(2026-05-08 — L DIRECTION G3 RULE OVERLAY SDK SHELLS PUBLISHED)

**当前工作树:** `/Users/zhenzhili/hnsm-backend` 当前停在 topic branch `codex/v0.1-l-g3-rule-overlays-2026-05-08` @ `cb6d3bd`. G3 6-phase implementation + 2-commit Phase 5 close-out + 1-commit verification-round polish done (Phase 0 `5437cd6` / Phase 1 `7f761bd` / Phase 2 `3526cc1` / Phase 3 `63c47ea` / Phase 4 `df772e2` / Phase 5 close-out `430bce2` rename + `3215083` content / verification-round polish `cb6d3bd`).

**G3 published snapshots (verified post-push 2026-05-08):**
- `origin/v0.1-l-g3-rule-overlays-2026-05-08` @ `cb6d3bd` — G3-only.
- `origin/v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-2026-05-08` @ `cb6d3bd` — Path B combined (G1+G4+G2+G3 cumulative).
- Prior snapshots unchanged: G2-only and G2 combined still at `d658390`; G1-only at `d6716a0`; G4-only at `acb5a6e`; sacred `master` and `v0.1-oss-prep` untouched.

**Convention — `memory/current.md` tracks topic-branch HEAD, not published snapshot HEAD.** This file is updated on the topic branch *after* a publish event, so at any published snapshot HEAD the file naturally lags by 1 commit (the post-publish memory sync). When auditing a published ref, treat operational handoff cues here as referring to what's true on the topic branch tip; the canonical published refs and external `~/.claude/.../memory/project_g*_published.md` are the authoritative published-state record. Path B published refs are immutable per `feedback_worktree_parallel_implementation`; we do NOT advance them just to make this file self-describing. Recorded in G3 archive audit log post-archive addendum 2026-05-08.

### G3 outcome

- **Shipped SDK methods (3):** `SDKStore.check_rule_disable(rule, support, *, branch_index, atom_index, overlay=None, note=None) -> RuleDisableResult`; `SDKStore.check_rule_literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None) -> RuleLiteralReplaceResult`; `SDKStore.check_rule_add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None) -> RuleAddConditionResult`.
- **Input contract:** SDK `Rule` (lowered through `_compile_rule_input` to substrate `RuleSpec` per §5.2 — substrate IR `RuleSpec` rejected at SDK boundary; G2 §5.1+§5.2 cross-cutting precedent scoped to `kernel.application.protocol` DTOs only); raw `SupportArtifact`; raw `RuleLiteralPath` / `RuleAddedAtom`; optional `EvaluationOverlay` (None or empty only — rule-action overlay constructed internally by A helper).
- **Return contract:** raw application result DTOs (documented passthrough; `kernel.sdk.__all__` length still 34).
- **Method naming:** Group A (`check_rule_*`) chosen over Group B per §5.7 falsifier (Group B `disable_rule` would semantically collide with persistent-write family).
- **Phase 0 fired G2 §5.2 deferred validator-extraction trigger:** promoted ProofFrame Recheck's local `_validate_support_artifact` to shared `validate_support_artifact`; added `validate_rule` and `validate_optional_evaluation_overlay`. Post-Blocker-fix: also added shared `resolve_runtime_registry` boundary normalizer (catches both `RuleCompileError` and pathless `SDKStoreError` from `_compile_rule_input`).
- **`#P1` carve-out applied 3×:** one per Phase 1/2/3 retrofit on pre-G3 application-runtime boundary tests `test_no_sdk_rule_{disable,literal_replace,add_condition}_surface`.
- **Blueprint:** `docs/blueprints/archive/2026-05-08_l-direction-g3-rule-overlays.md` + `.audit.md` archived and marked `implemented`.
- **Verification basis:** post-Blocker-fix 198 SDK shell + invariant + validation tests OK; full kernel suite (re-run incoming); ruff clean; `git diff --check` clean.

### G3 follow-up

- G3-only + Path B combined snapshots published 2026-05-08 from verification-round HEAD `cb6d3bd`. No remaining publish action.
- G5 (TBD — Round events / ProofFrame diff) is next in L sequence; will inherit `kernel/sdk/shells/` subpackage at 8 modules + shared `resolve_runtime_registry` boundary normalizer + §5.1+§5.2 substrate-IR-out clarification.
- Sacred branches remain untouched: `master` and `v0.1-oss-prep`.
- G1 + G4 + G2 published snapshot branches remain untouched at `d6716a0` / `acb5a6e` / `d658390`.
- Watch for a post-publish verification round (G1/G4/G2 each had one with 1 Blocker + minor polish; G3's first Blocker was caught pre-publish, but a fresh round may still surface follow-ups).

<!-- Historical 2026-05-08 G4 close-out state follows. -->

最后更新:2026-05-08(`codex/v0.1-l-g4-why-not-frontier-2026-05-08`;G4 Why-not SDK shell implemented,archived,ready to publish snapshot)

## 当前阶段(2026-05-08 — L DIRECTION G4 WHY-NOT SDK SHELL COMPLETE)

**当前工作树:** `/Users/zhenzhili/hnsm-backend` 当前停在 topic branch `codex/v0.1-l-g4-why-not-frontier-2026-05-08`; G4 close-out/archive commit is `a3b7f119`, followed by this operational memory sync.

**G4 published snapshot target:** `v0.1-l-g4-why-not-frontier-2026-05-08` should point to the final G4 close-out HEAD after publish.

### G4 outcome

- **Shipped SDK method:** `SDKStore.why_not(derivation, candidates, *, engine="native", registry=None) -> WhyNotUniverseResult`.
- **Input contract:** SDK `Derivation` only; explicit finite `candidates` rows as `Sequence[Mapping[str, Any] | Sequence[Any]]`.
- **Return contract:** raw application `WhyNotUniverseResult` documented passthrough; `kernel.sdk.__all__` remains unchanged.
- **Frontier:** remains advanced importable; no `SDKStore.frontier`, no `kernel/sdk/frontier.py`, no SDK/core frontier import.
- **Blueprint:** `docs/blueprints/archive/2026-05-08_l-direction-g4-why-not-frontier.md` + `.audit.md` archived and marked `implemented`.
- **Verification basis:** 76 SDK shell targeted tests OK; 109 Why-not application/helper regression tests OK; full kernel suite 1538 OK / 1 skipped; ruff clean; `git diff --check` clean.

### G4 follow-up

- Publish `v0.1-l-g4-why-not-frontier-2026-05-08` from the final close-out HEAD.
- G2 is next in L sequence and MUST re-evaluate `kernel/sdk/shells/` migration before adding more SDK shell files; this is the re-recorded G1/G4 flat-layout trigger.
- Sacred branches remain untouched: `master` and `v0.1-oss-prep`.

<!-- Historical 2026-05-08 A+B / pre-G4 state follows. -->

最后更新:2026-05-08(`v0.1-public-surface-helpers-walker-2026-05-08`;A+B post-routemap Tier 2 helpers + walker complete,blueprints archived,combined snapshot pushed,dirty notebooks reverted)

## 当前阶段(2026-05-08 — A+B POST-ROUTEMAP TIER 2 SURFACE COMPLETE)

**当前工作树:** `/Users/zhenzhili/hnsm-backend` 当前停在 combined latest branch `v0.1-public-surface-helpers-walker-2026-05-08` @ `6162f1e`。

**重要修正:** 早前 memory 里“parent branch untouched”应理解为 `v0.1-public-surface-2026-05-06` 分支没有承载 A/B implementation commits；不是说 `/Users/zhenzhili/hnsm-backend` 工作树 HEAD 一直停在该旧 parent branch。A+B integration 后，主工作树已切到 combined latest branch。若需要回看 A+B 前状态，显式切回 `v0.1-public-surface-2026-05-06` @ `95bbbb8`。

**Working tree 状态:** clean。此前 6 个 pre-existing notebook execution-output artifacts 已全部 revert；没有 notebook changes 残留。

### A+B published branch state

| Branch | HEAD | Status |
|---|---|---|
| `v0.1-public-surface-helpers-walker-2026-05-08` | `6162f1e` | local + remote;combined A+B latest;current worktree branch |
| `v0.1-public-surface-walker-2026-05-08` | `90d5b06` | local + remote;B-only walker snapshot retained |
| `v0.1-public-surface-2026-05-06` | `95bbbb8` | local parent baseline;no A/B implementation commits |
| `codex/v0.1-application-helpers-extension-2026-05-07` | `0d0b490` | local A implementation branch;blueprint archived |
| `codex/v0.1-walker-mechanism-2026-05-07` | `7cf4ae4` | local B implementation branch;blueprint archived |

### A+B outcome

- **Direction B walker mechanism** complete:
  - Implementation branch: `codex/v0.1-walker-mechanism-2026-05-07`
  - Published B-only snapshot: `v0.1-public-surface-walker-2026-05-08` @ `90d5b06`
  - Blueprint archived: `docs/blueprints/archive/2026-05-07_walker-mechanism.md` + `.audit.md`
  - Delivered Tier 2 walker/view package under `kernel.application.walker`; B3 audit/store stream walker remains future-only.
- **Direction A application ergonomic helpers** complete:
  - Implementation branch: `codex/v0.1-application-helpers-extension-2026-05-07`
  - Blueprint archived: `docs/blueprints/archive/2026-05-07_application-ergonomic-helpers-extension.md` + `.audit.md`
  - Delivered `kernel.application.capability_helpers` package with 8 capability-family coverage (Batch 2 prior helpers + 5 new builder families).
- **Combined latest**:
  - Branch: `v0.1-public-surface-helpers-walker-2026-05-08` @ `6162f1e`
  - Remote pushed to `origin`
  - Focused regression on combined branch passed: 190 tests + 417 subtests.

### Fresh session first action

1. Confirm current branch and clean state:
   - expected current branch: `v0.1-public-surface-helpers-walker-2026-05-08`
   - expected HEAD: `6162f1e`
   - expected `git status --short`: clean
2. If starting **L direction / SDK shells G1-G5**, use the combined latest branch as the baseline unless explicitly comparing against pre-A+B parent.
3. If housekeeping first, optional cleanup remains:
   - remove no-longer-needed worktrees `/Users/zhenzhili/hnsm-backend-A` and `/Users/zhenzhili/hnsm-backend-B` only after confirming their branches are no longer needed locally.
4. Sacred branches remain untouched: `master` and `v0.1-oss-prep`.

<!-- Historical 2026-05-06 post-routemap state follows. -->

最后更新:2026-05-06(`v0.1-public-surface-2026-05-06`;post-routemap light wrap-up:master plan close-out + tutorials committed,operational memory sync current)

## 当前阶段(2026-05-06 — ROUND STORY COMPLETION PLAN COMPLETE)

**当前分支:** `v0.1-public-surface-2026-05-06`,基于 Batch 7 hardening final `3baf4ac` 切出。Batch 8 closed at `6b32972`;post-routemap wrap-up additionally committed master-plan close-out docs and tutorial expansion.

**Working tree 状态(预期 after this memory sync commit):**
```
clean
```

### Round Story Completion Plan progress

- ✅ Batch 0 — Inventory / reference cleanup
- ✅ Batch 1 — Canonical Round Story
- ✅ Batch 2 — Capability Ergonomics
- ✅ Batch 3 — EvaluationOverlay(`replace + remove`,fact-side add deferred)
- ✅ Batch 4 — ProofFrame Rechecker(narrow Shape B,3-status,strict `not` deferral)
- ✅ Batch 5a — Rule Disable(single-action native rule locator disable)
- ✅ Batch 5b — Rule Literal Replace(narrow Const-to-Const native literal replace)
- ✅ Batch 5c — Rule Add Condition / Binding Planner(narrow filter-only add condition;binding planner deferred)
- ✅ Batch 6 — Durable Round Persistence(optional `audit/round_events.jsonl`,external buffered recorder,AuditQuery round-event methods)
- ✅ Batch 7 — Evidence Diff / Cross-Run(first slice:L4 ProofFrame diff;L5 aggregation deferred)
- ✅ Batch 8 — Public Surface Decision(docs/checklist-only public boundary close-out)
- ⚠️ Deferred hardening tracked separately:Batch 4 ProofFrame symmetric `rule_refs` legacy-field rejection gap.

### Batch 8 landed commits

- `33b0afe` — drafted Batch 8 Public Surface blueprint/audit with Step-0-first framing;key false-merge risk:SDK shell,service routes,release projection,and README baseline are lifecycle-different decisions.
- `4273d8f` — Step 0.A selected **Path A docs/checklist first slice**:no SDK/service code,no application/audit protocol drift,no release branch action,no projection expansion by default.
- `c26cb88` — Step 0.B froze public boundary tiers and scoped files:
  - product public:`kernel.sdk`;
  - advanced importable:`kernel.application` + `kernel.audit`;
  - internal/deferred:service/agent/domains,SDK shells for Batches 3-7,service routes,example projection add-back,Batch 6/7 deferred families,Batch 4 `rule_refs` hardening.
- `f2a4448` — scope freeze(`draft → scoped`).
- `6b32972` — implementation + archive:
  - README / README.en public-boundary table;
  - SDK API docs clarify no Batch 3-7 SDK shells;
  - application/audit docs label advanced importable surfaces;
  - release-candidate blueprint gains Batch 8 public-surface checkpoint;
  - Batch 8 blueprint archived to `docs/blueprints/archive/2026-05-06_public-surface.md`.

### Batch 8 shipped behavior

- No Python code changed.
- No SDK shell / service route / release projection allowlist expansion / package-scope change shipped.
- `kernel.sdk` remains product public surface.
- `kernel.application` and `kernel.audit` are documented as advanced importable kernel surfaces.
- Public source projection remains 261 files and default-deny.

### Verification

- `scripts/project_release_surface.sh` — passed(261 files).
- README and README.en quickstart blocks — both print `Alice`.
- public-doc deny-pattern scan over changed projected docs — clean.
- `git diff --check` — clean.
- Drift guards:only scoped docs/checklist files changed;0 SDK/application/audit Python code drift;0 service/agent/domain drift;0 release script/allowlist/pyproject drift.

### Fresh session first action

1. Confirm branch `v0.1-public-surface-2026-05-06` and clean worktree.
2. If auditing Batch 8,read `docs/blueprints/archive/2026-05-06_public-surface.md`, `README.md`, `README.en.md`, and the scoped module docs changed in `6b32972`.
3. Round Story Completion Plan is complete and the master plan §10 close-out is filled. Remaining work is optional/post-routemap:
   - Batch 4 ProofFrame symmetric `rule_refs` hardening;
   - optional final release-day workflow on `v0.1-oss-prep` / public projection,only with explicit user authorization;
   - post-routemap design-intent reconciliation items recorded in the master plan §3.


<!-- Historical CAPABILITIES E2E DEMO SHIPPED state follows. -->

## 当前阶段(2026-05-05 — CAPABILITIES E2E DEMO SHIPPED)

**当前分支:** `v0.1-capabilities-e2e-demo-2026-05-05`,HEAD `1ec314c`(`docs(examples): add capabilities e2e demo`)。基于 `v0.1-evaluator-architecture-step0-2026-05-05` @ `8ebbe70` 切出。release base `v0.1-oss-prep` 与 `master` 未触碰。

**落地内容:**
- `examples/11_capabilities_e2e_demo.py`:deterministic assertion-bearing script,one `Person(name, age, region)` fixture composes all 5 shipped surfaces:
  1. Check
  2. Diagnose
  3. Fact Overlay Check
  4. Why-not Universe Diagnose
  5. Evaluator Frontier Trace
- `src/kernel/tests/test_examples_capabilities_demo.py`:imports demo by path and calls `run_demo(verbose=False)`.
- `examples/README.md`:adds script section and clarifies notebook/script convention.
- Blueprint archived:
  - `docs/blueprints/archive/2026-05-05_capabilities-e2e-demo.md`
  - `docs/blueprints/archive/2026-05-05_capabilities-e2e-demo.audit.md`
- Archive inventory row added for `capabilities-e2e-demo`.

**Verification:**
- `python examples/11_capabilities_e2e_demo.py` — passed
- `python -m unittest src.kernel.tests.test_examples_capabilities_demo` — 1 OK
- Related capability suites — 143 OK
- Full kernel — 1081 OK / 1 skipped
- `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` — clean
- `git diff --check` — clean

**Worktree note:** only `memory/current.md` remains modified,continuing lightweight sync policy. Demo commit is local-only unless pushed later.

<!-- Historical EVALUATOR FRONTIER POST-SHIP state follows. -->

## 当前阶段(2026-05-05 — EVALUATOR FRONTIER POST-SHIP)

**当前分支:** `v0.1-evaluator-architecture-step0-2026-05-05`,HEAD `8ebbe70`(P3 hardening commit after archive)。

**远端状态:** Branch tracks `origin/v0.1-evaluator-architecture-step0-2026-05-05` @ `8ebbe70`。Portfolio 全 origin-backed —— 5 个 v0.1.x preview branch + 1 frozen reference,全部上传 origin。release base `v0.1-oss-prep` 与 `master` 未触碰。

### Shipped capability portfolio(5 个)

| Capability | 日期 | 层 | Branch | Cross-session anchor |
|---|---|---|---|---|
| Check | 2026-05-03 | application | `v0.1-redesign-2026-05-03` @ `422ffcf` | `project_check_operation_shipped.md` |
| Diagnose | 2026-05-04 | application | `v0.1-redesign-2026-05-03` @ `422ffcf` | `project_diagnose_operation_shipped.md` |
| Fact Overlay Check | 2026-05-04 | application | `v0.1-fact-overlay-2026-05-04` @ `f484367` | `project_fact_overlay_operation_shipped.md` |
| Why-not Universe Diagnose | 2026-05-05 | application | `v0.1-why-not-step0-2026-05-05` @ `32ed594` | `project_why_not_universe_diagnose_shipped.md` |
| Evaluator Frontier Trace | 2026-05-05 | **evaluator (substrate)** | `v0.1-evaluator-architecture-step0-2026-05-05` @ `8ebbe70` | `project_evaluator_frontier_trace_shipped.md` |

### 架构线索(关键 invariant 仍 hold)

- **Application-first hard constraint**:每新 application capability 在 `kernel.application.protocol` + `kernel.application` 起步;`kernel.sdk` 不背 substrate
- **Q1 Sibling discipline**(application 层 3 梯度):
  - Diagnose vs Check:不 call 不 import(strict)
  - Fact Overlay vs Check:不 call,共享 helper via `_derivation_match_helpers`
  - Why-not vs Diagnose:可 call runtime + 构造 `DiagnoseRequest`,但**不 import** Diagnose result types(duck-typing access via duck typing,protocol 完全 owned)
- **§6.6 working hypothesis**:跨 3 个 application capability(Diagnose / Fact Overlay / Why-not Universe Diagnose)三次 validate 仍 hold;§6.7 declarative capability schema 未触发
- **Layer-separation invariant**(evaluator-frontier 引入):`frontier.py` 在 `kernel.core.rules.*`,不 import application/SDK/adapter/candidate/evidence types;application 层不 sneak-import frontier(§7-EvaluatorFrontier-10 静态扫强制,5 种 access pattern 全 catch)

### Why-not Shape B fork resolution

Why-not Step 0.A 时显式 deferred 的 "true near-miss" 现已 resolved as **Evaluator Frontier Trace** —— substrate piece 已 ship。Future application capability(如新 Why-not 变体)若想做 Shape B,可组合 frontier rows + Diagnose 行映射,不需要打开新 evaluator architecture topic。`project_why_not_step0_scoped.md` description 已更新反映此 fork closure。

### Post-ship review(evaluator frontier)

- **P3 §7-EvaluatorFrontier-10 hardening**:`8ebbe70` 加 5-pattern detection helper(direct import / module import / from-import / Name reference / Attribute access),双层 enforcement(应用扫 + helper 自身 self-test)
- **P2 deferred**:raw binding values dedupe/sort 限制 inherited from `evaluate_native_where`,frontier 单独修会破 §7-EvaluatorFrontier-7 success parity → 留作 shared evaluator value-stability 议题(audit + memory anchor 已记录)

### 测试状态

- 全 kernel:**1080 tests OK / 1 skipped**(从 redesign reset 时 ~782 → 现 1080,新增 ~298 tests across 5 capabilities)
- frontier focused:37 OK
- ruff clean

### 下一步可选方向(无 pending,均独立议题)

- **停**:portfolio 已 origin-backed,compact-safe
- **Demo / integration showcase**:5 capability 端到端示例,验证 composition + 防 integration drift
- **跨分支 consolidation**:5 个 v0.1.x preview branch 合并整理,需新 blueprint 入口判断
- **第 6 capability**:收益边际继续递减,除非 structurally novel(如 5th Sibling 梯度 / evaluator-layer 扩展 / fact-overlay 与 frontier 集成)
- **OSS publish**:独立议题,需显式 publish 决策(per `project_release_branch_invariants.md`)
- **Engine-extension Wave 2**(§3.3 / §3.5):无 trigger,§6.6 仍 hold
- **§6.7**:仍未触发

任何新工作仍须满足 application-first hard constraint(per `project_application_first_runtime_authority.md`)+ release branch invariants(per `project_release_branch_invariants.md`)。

### 启动阅读顺序(新 session 用)

1. 本文件
2. `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` index
3. 5 个 shipped anchor + 2 个 invariant anchor(per index)
4. `docs/blueprints/archive/README.md` inventory(5 个 implemented blueprint)
5. `src/kernel/application/docs/01_overview.md` + `_en.md`(application capability 列表)
6. `src/kernel/core/docs/01_architecture.md` + `.en.md`(evaluator frontier 在此)

<!-- Stale Why-not Step 1 checkpoint section removed; superseded by EVALUATOR FRONTIER POST-SHIP top section above. Historical REDESIGN BASE follows. -->

## 当前阶段(2026-05-03 — REDESIGN BASE)

**本分支 `v0.1-redesign-2026-05-03` 是 active development 起点**,从 `master`(`8af9da9`)起,clean baseline:
- src 代码:pre-rule-replay 状态(无 `kernel.sdk.replay*`、无 `kernel.authoring.module_ir`、无 `disabled_locators` threading)
- memory + docs:master 状态(`v0.1 onboarding hardening implemented + merged` 时刻)

### 为什么有这个分支(2026-05-03 RESET 决定)

2026-05-01..02 共 ~42 小时窗口内试做了 v0.1.x rule-replay 设计实验(v0.1.1 rule-replay + v0.1.2 module-IR + v0.1.3 disable-condition + v0.1.4 abandoned param-override),但架构 review 发现 substrate 整体落 SDK,违反 application-first;Decision 1 当时提的 strangler migration 在"无真用户反馈信号"前提下不成立 —— preview line 按定义没承诺界面,可推倒。**作初步试错放弃,redesign 基于经验重起**。详细论证见 design-discussion 引用。

### Frozen design probe references(do NOT touch,可 git-access)

**唯一保留分支:** `v0.1.1-evidence-tree-operational-overlay` rollup,含 v0.1.1+v0.1.2+v0.1.3 全部 implemented impl + v0.1.4 abandoned blueprint + 全部 design 材料。

v0.1.2-rule-module-ir / v0.1.3-disable-condition / v0.1.4-param-override 单独分支已**删除**(local + remote,2026-05-03):
- v0.1.2 + v0.1.3 全部 commits 在 rollup `--no-ff` merge 历史里(无内容损失)
- v0.1.4 abandoned blueprint 在删分支前已 cherry 入 rollup `docs/blueprints/archive/`(commit `1f9eac9`)

| 资源 | 位置 | 角色 |
|---|---|---|
| `v0.1.1-evidence-tree-operational-overlay` 分支 | @ `d5c14a3` | **唯一 design probe rollup**(含全部 v0.1.x impl + design 材料 + v0.1.4 archived blueprint) |
| `v0.1.1-preview` tag | @ `b7c9169` | preview 试做 tag(rollup 历史里) |
| `v0.1.2-preview` tag | @ `98474a1` | preview 试做 tag(rollup 历史里) |
| `v0.1.3-preview` tag | @ rollup merge HEAD | preview 试做 tag(rollup 历史里) |

**Reference bundles**(在 rollup 分支上,通过 git access):
- `docs/references/working/rule-replay/`(B'/B'' 设计讨论历史)
- `docs/references/working/evidence-vision/`(L0-L11 能力分层)
- `docs/references/working/design-landscape/`(架构 drift 分析)
- `docs/references/working/design-discussion-2026-05-02/`(A 方向讨论 + Decision 1 历史 framing)

**Archived blueprints**(在 rollup 分支上,通过 git access):
- `docs/blueprints/archive/2026-05-01_rule-replay-with-evidence-diff.md`
- `docs/blueprints/archive/2026-05-02_v0.1.2-rule-module-ir.md`
- `docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md`
- `docs/blueprints/archive/2026-05-02_v0.1.4-param-override.md`(abandoned)

**Git access 老 impl 范例:**
```
git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay.py
git show v0.1.1-evidence-tree-operational-overlay:src/kernel/authoring/module_ir.py
git show v0.1.1-evidence-tree-operational-overlay:docs/references/working/evidence-vision/evidence-vision-synthesis-2026-05-02.md
```

### 新 hard constraint(replaces 之前的 strangler migration)

每一个新 capability 必须:
1. 第一步在 `kernel/application/protocol/` 加 DTO
2. 第二步在 `kernel/application/<runtime>.py` 加纯函数 `(request, store) -> result`
3. 第三步(可选)SDK shell wrapper,**绝不带 substrate**
4. **不允许新 substrate 长在 `kernel/sdk/`**
5. Step 0 spike 必须明确回答:"这个 capability 的 application DTO 形状是什么?" — 答不出 → 不 scope

详见 `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`(在 reset 后已更新)。

### 已学经验保留作 redesign 输入

不重读 v0.1.x 代码也已学会的:
- B'' pivot(rule operable + evidence read-only)的设计正确性 — 仍生效
- candidate_key vs candidate_id(cross-run identity)— 用 `candidate_key`
- ConditionModule.atom 必须递归 immutable(`feedback_invariant_defense_in_depth.md`)
- Locator stability invariant — disable / replace 时 `b{branch}.a{atom}` 不位移
- macOS+zsh+BSD-sed 5 个执行陷阱(`feedback_refactor_execution_traps.md`)
- 4 类 "param" 语义不可合并(v0.1.4 abandonment 教训)
- L0-L11 evidence 能力分层是会议室 taxonomy,实施时 L4/L5 可能合并 / L7 必须降级 / L9 不应在 kernel
- Application 是设计中心(`derivation_runtime.evaluate_derivation_plans()` 是 canonical executor)
- Filter CandidateSet 不可靠(head_vars 投影 + dedupe 丢失 body-only var)
- 不 inject initial env(`where_eval` 每 branch `envs=[{}]` 起)
- failed_atom_locator 不是 native evaluator 的自然产物

### Release branch invariant(继续生效)

- `v0.1-oss-prep` @ `f5ade36` 是唯一 release base,**冻结**,无显式 publish 决策不动
- `master` 同样冻结,无显式决策不动
- 本 redesign 分支也是 internal preview line,不向 release base 流入

### 启动阅读顺序(新 session 用)

1. 本文件
2. 新 hard constraint:`~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`
3. Release branch invariant:`~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_release_branch_invariants.md`
4. **设计材料 consolidation**(in-tree,无需 git show 翻 rollup):**[docs/references/working/rule-replay-line-redesign-input/README.md](/Users/zhenzhili/hnsm-backend/docs/references/working/rule-replay-line-redesign-input/README.md)** —— 用户原始 brainstorm + B'/B'' 设计历史 + L0-L11 能力分层 + drift 分析 + A 段讨论 + 4 个 abandoned blueprint + lessons learned
5. AGENTS.md + docs/blueprints/AGENTS.md
6. docs/architecture_principles.md(four-layer data architecture + layer split + release governance)
7. src/kernel/application/docs/README.md(canonical runtime authority)
8. src/kernel/sdk/docs/README.md(product surface,**不再背 substrate**)
9. (可选,深度回溯老 impl)`git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay.py` 等

### 下一步方向(2026-05-04 起)

详情见 [`session_handoffs/2026-05-04.md`](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-05-04.md) §10,但该 handoff 写于 §6.2 前;当前 continuation 已到 Diagnose Step 8 close-out。摘要:

- engine-extension-surface topic Wave 1 已 closed:
  - §6.2 strategic framing:`1f084f8`
  - §6.3 §3.4 minimum engine adapter contract:`9c2d8e5`
  - §3.4 Check evidence-miss follow-up trace:`2c13470`
  - §6.4 §3.2 engine options placement light commit:`24bd22b`
  - §6.5 §3.1 typed payload working hypothesis / migration triggers:`44eefab`
- Diagnose operation Step 0 draft blueprint opened:`docs/blueprints/active/2026-05-04_diagnose-operation.md` + audit (`9b69178`);after Step 8 archive path is `docs/blueprints/archive/2026-05-04_diagnose-operation.md`
- Diagnose Step 0.A source pass complete + conformance-aligned audit:`5aa261d`
- Diagnose Step 0.B DTO contract frozen:`e90835a`
- Diagnose Step 0.C algorithm + drift-prevention frozen:`815192d`
- Diagnose Step 0.D lift complete + blueprint moved `draft → scoped`:`e1dc6d4`
- Diagnose §8 Step 1 protocol DTOs complete:`ceb54bb`
- Diagnose §8 Step 2 native runtime MVP complete:`bf9abf6`
- Diagnose §8 Step 3 native hardening complete:`7092bdf`
- Diagnose §8 Step 4 non-native representability gate complete:`b011757`
- Diagnose §8 Step 5 souffle dispatch complete:`8a6c449`
- Diagnose §8 Step 6 problog/pyreason dispatch complete:`267b0a7`
- Diagnose §8 Step 7 drift-prevention test pass complete:`86351bc`
- Diagnose §8 Step 8 close-out complete;blueprint status `scoped → implemented`
- Diagnose archived;next topic selected as engine-extension §6.6 on new branch.
- baseline P1/P2 仍待填,但应随 Diagnose source pass 从 consumer angle 补,不单独 abstract inventory

任何新工作必须满足 application-first hard constraint(per `project_application_first_runtime_authority.md`)+ release branch invariants(per `project_release_branch_invariants.md`)。

---

## 2026-05-04 update — Check shipped + engine-extension-surface topic opened

**Check operation 完整闭环 end-to-end(2026-05-04 完成):**

- Topic doc `cited`:`docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md`
- Blueprint archived:`docs/blueprints/archive/2026-05-03_check-operation.md` + audit
- Code:`src/kernel/application/protocol/derivation_check.py`(166 LOC, DTOs)+ `src/kernel/application/derivation_check_runtime.py`(795 LOC, runtime + per-engine paths)
- Tests:73 focused(22 protocol + 51 runtime),782 total kernel green + 1 skip
- 4 engines 全 covered:native (via `evaluate_native_where`)+ souffle (SupportArtifact path)+ problog/pyreason (ProvenanceEnvelope path)— Option IV representability-gated multi-engine
- Application-first hard constraint **100% 落实**;SDK shell 显式 skip per `feedback_narrow_public_api`

**Memory 新增** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_check_operation_shipped.md` — Check archive 作为 reference template for future application capabilities

**Process patterns validated** (use as templates,详见 handoff §6):
- 4-sub-round Step 0(.A source pass / .B DTO freeze / .C algorithm freeze / .D lift)
- 3-round blind validation(by independent subagents reading only docs)
- §7 drift prevention(每 trap mapped to anti-regression test)
- Conformance audit before `scoped → implemented`
- Archive sequence(`git mv` + inventory + topic doc cross-ref rewire)

**engine-extension-surface-architecture topic opened**(Status: `draft`):

- 新 venue topic doc:`docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md`
- §6.1 ASP scenario demo committed(paper demo of adding 5th engine)
- §6.2 strategic framing committed:`1f084f8`
- §6.3 resolved §3.4 engine adapter contract:`9c2d8e5`
- §3.4 follow-up trace committed:`2c13470` — future Check lookup→None changes must replace MVP silent-skip with observable warning/error before claiming conformance
- §6.4 resolved §3.2 engine options placement(light commit):`24bd22b`
- §6.5 resolved §3.1 payload DTO shape as typed-Union working hypothesis:`44eefab`
- Wave 1 closed; still unresolved/deferred:§3.3 package architecture,§3.5 onboarding workflow,§3.6 capability declaration

**Diagnose operation shipped + archived**(Status:`archived`):

- Blueprint:`docs/blueprints/archive/2026-05-04_diagnose-operation.md`
- Audit:`docs/blueprints/archive/2026-05-04_diagnose-operation.audit.md`
- Commit:`9b69178`
- Step 0.A complete:`5aa261d`;Step 0.B frozen:`e90835a`;Step 0.C frozen:`815192d`
- Step 0.D lift complete:`e1dc6d4`;blueprint §5 / §7 / §8 now carry the frozen contract / acceptance / ordered implementation plan
- Scope now moves to implementation;Step 0 gate is closed and code may begin at §8 Step 1
- 0.B Q1 supersede:Hybrid → Sibling. Diagnose owns dispatch/representability/evidence lookup and does **not** call `check_derivation_binding(...)`,because Hybrid would launder Check's grandfathered non-native lookup-miss silent-skip into Diagnose
- 0.B status contract:reuse Check 4 statuses;`failure_kind` only for `failed.no_candidate` / `failed.atom_localized`;evidence lookup miss maps to `status="unsupported"` with `ErrorDTO(code="EVIDENCE_LOOKUP_MISS")`
- 0.B payload contract:`DiagnoseAtomLocator(branch_index, failed_atom_index, attempted_binding)` is Diagnose-owned capability-output,not an engine-native payload;§6.5 is not engaged and `EvidenceEnvelope.engine_payload` remains unchanged
- 0.B representability:locally hardcoded per engine;native atom-localized,non-native coarse-only;§3.6 pressure confirmed. Post-ship §6.6 later resolved §3.6 as locally-hardcoded working hypothesis with migration triggers.
- 0.C algorithm:Sibling dispatch;native two-phase pass/fail then atom-localization;native localizer uses `_extend_env_with_atom` enumeration primitive to avoid `_ground_terms` silent-false at atom-index layer;non-native three-bucket classification(match / lookup-miss / no-match) with lookup-miss precedence
- 0.C drift prevention:§7-Diagnose-1..7 frozen,including evidence-miss-as-unsupported,no `DiagnoseAtomLocator` in `EvidenceEnvelope`,no Check-call/import invariant,non-native never atom-localized,status enum exact 4 values
- 0.D lift:§5 Proposed Shape covers D1-D12 + C1-C8 + Q1 supersede + D8.note;§7 Acceptance contains 7 §7-Diagnose anti-regression gates;§8 has 8 ordered implementation steps
- §8 Step 1 complete:`src/kernel/application/protocol/derivation_diagnose.py` + `src/kernel/tests/test_application_diagnose_protocol.py`;42 protocol tests landed,§7-Diagnose-1/2/7 partly enforced at DTO layer
- §8 Step 2 complete:`src/kernel/application/diagnose_runtime.py` + `src/kernel/tests/test_application_diagnose_runtime_native.py`;native MVP covers pass,atom-localized fail,no_candidate fallback,unknown var / RuleRef invalid_request preflight,branch-aware primary,`_extend_env_with_atom` enumeration primitive;non-native intentionally left for §8 Step 4-6
- §8 Step 3 complete:`7092bdf`;fixed native localizer to keep the candidate frontier instead of collapsing to a single primary env after each atom;added RuleRef happy-path test;added §7-Diagnose-4 anti-regression that failed localization does not call support-capture `_atom_satisfies`
- §8 Step 4 complete:`b011757`;added Diagnose-owned `_request_diagnostic_representability_precheck` (no Check helper import) and non-native representability tests. `problog`/`pyreason` return `unsupported` before dispatch for entity-targeted plans and body-only requested variables; `souffle` remains representable for body-only/head-only bindings and is left to Step 5 dispatch. Unsupported representability results carry `failure_kind=None` / `diagnostic_payload=None`, partially enforcing §7-Diagnose-5 until actual non-native dispatch lands.
- §8 Step 5 complete:`8a6c449`;added `_diagnose_souffle` with evaluate → `SupportArtifact` lookup → match / lookup-miss / no-match buckets; lookup-miss outranks `no_candidate`, match wins over lookup-miss; primary sort follows Check C4 `(branch_index, binding_items, candidate_key)`; §7-Diagnose-5/6 souffle-path tests landed. Diagnose result still does not expose branch_index; branch sort is internal deterministic primary selection only.
- §8 Step 6 complete:`267b0a7`;added `_diagnose_problog_pyreason` with evaluate → `ProvenanceEnvelope` lookup → match / lookup-miss / no-match buckets; binding extraction uses head-var payload-term positional alignment and skips `candidate_ref` terms; lookup-miss surfaces `EVIDENCE_LOOKUP_MISS`; primary sort `(candidate_key, binding_items)`. ProbLog/PyReason tests cover pass, failed.no_candidate, zero candidates, lookup-miss-only, lookup-miss outranks no-match, match wins over lookup-miss, primary sort, and non-atom-localized invariant.
- §8 Step 7 complete:`86351bc`;added `src/kernel/tests/test_application_diagnose_sibling_invariant.py` AST static checks for Q1 Sibling no-Check-call invariant;added problog / pyreason parity tests for §7-Diagnose-5/6. All seven §7-Diagnose gates now have explicit named coverage.
- §8 Step 8 complete;application docs list Diagnose;blueprint §10 Outcome / Deviations filled;conformance audit recorded;status `implemented`;blueprint archived to `docs/blueprints/archive/`. Step 8 refinements recorded:Step 3 candidate frontier,Step 4 souffle request-gate vs dispatch-layer representability,Step 5 branch_index ordering internal-only.
- Verification at Step 8 checkpoint:`python -m unittest discover -s src/kernel/tests` => 866 OK / 1 skip;`python -m ruff check src/kernel` => all checks passed
- Post-ship direction selected:engine-extension §6.6 capability declaration round on `v0.1-engine-capability-declaration-2026-05-04`. Release base / master still untouched.

**Branch state** `v0.1-redesign-2026-05-03`:pushed to `origin/v0.1-redesign-2026-05-03` @ `422ffcf` and treated as frozen reference. Current work continues on `v0.1-engine-capability-declaration-2026-05-04`;release base sacred 不动。

---

## 历史 (pre-2026-05-03 RESET) — master 时刻状态,作历史参考

下方内容是 reset 前 master 分支的 memory 状态,描述 v0.1 onboarding hardening 完成后的形势。redesign 不依赖这段,但保留作 framing 历史:

## 当前阶段

**v0.1 onboarding hardening 已 implemented + merged + pushed**:`oss-prep-v0.1` 现在包含 release-surface cleanup 与 onboarding hardening。`kernel.application` 是 canonical Python runtime authority,`kernel.sdk` 保持 Python product surface / authoring DSL / outward facade。

- 当前分支:`oss-prep-v0.1`
- 当前最新工作:v0.1 onboarding hardening blueprint 已 implemented,并通过 `--no-ff` merge 进入 `oss-prep-v0.1`。merge commit:`962f087`;hardening reference branch:`v0.1-onboarding-hardening` @ `62e68a1`。后续 follow-up 已追加并 push 到 `origin/oss-prep-v0.1` @ `8d7e339`:D7 journey notebook、audit package read-back、native candidate evidence-tree rendering、field-sugar docs、Layer 1/2 signposting、public write/read API docstrings。OS-prep v0.1 readiness、RC verification、source projection gate、onboarding hardening 均已完成;公开源码面通过 sanitized projection script 验证,长期管理方式已写入 `docs/architecture_principles.md`;但仍未创建 public repo、未 upload、未 tag。
- 当前 kernel release 基线:709 tests OK / 1 skip;`python -m ruff check src/kernel` clean;`scripts/project_release_surface.sh` 通过(261 projected files)。历史 5 段基线在 hardening 前为 1097 tests / 3 skips;hardening close-out 未重跑 agent/service/domains/benchmarks 全段。
- runtime cleanup blueprint:[2026-04-28_runtime-authority-cleanup.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md),status `implemented`,暂不归档
- OS-prep blueprint 仍在 active,但 status 已 implemented。用户明确 OSS v0.1 仅包含 kernel 主体,所以 #1/#2/#3/#4/#7/#11/#12 已按 kernel-only surface 收口。#4 默认名锁为 `factpy-kernel`,但真实 PyPI reservation 仍需 release day upload / trusted publishing。剩余工作主要是 release-day checklist 与 staged CI gate 后续提升。

## 当前 namespace

```
src/
  kernel/
    core/ sdk/ adapters/ audit/ authoring/ application/ tests/
  agent/
    extraction/ documents/ tools/ framework/ orchestrator/ session/ service/ tests/
  service/
    app_v1.py runtime_v1.py rules_v1.py registry_v1.py auth.py static_ui.py tests/
  domains/
    ecss/
      vcd.py temporal.py uncertainty.py sdk_helpers.py compliance.py tests/
tools/
  benchmarks/tests/
```

## 当前 layer truth

| Layer | 当前职责 |
|---|---|
| `kernel.core` | ledger/store/rules/evidence 等低层语义内核 |
| `kernel.application` | canonical Python runtime authority;拥有 read/write/query/ingest/compiled derivation runtime DTO + executor |
| `kernel.sdk` | Python product surface;拥有 schema/DSL authoring、`SDKStore` facade、snapshot/editor/batch outward objects、compatibility errors |
| `service` / `agent` | delivery / product consumers;production runtime code 不新增 SDK runtime import |
| `domains.ecss` | ECSS domain bundle;仍有 SDK ergonomic helper,属 domain facade 范围 |

## Runtime-authority cleanup 落地摘要

- commit 1:application protocol / executor surface pure add(query / ingest / derivation)
- commit 2a:application parity fixes(no SDK changes)
- commit 2b:derivation SDK adapter switch + batch delegate test rewrite
- commit 2c:query SDK adapter switch + SDK query policy tests
- commit 2d:ingest SDK adapter switch with identity-cache fallback + SDK ingest delegate tests
- commit 3:service/agent production SDK import boundary guard
- commit 4:docs alignment + blueprint implemented status close-out

完成后 application snapshot:

- 15 files / 3399 LOC
- `kernel.application.__all__`:29 symbols
- SDK runtime files:query adapter shrank(`query_runtime.py` 357 -> 297),ingest grew to 800 due cache/fallback adapter plus hardening fallback reroute;`store.py` / `batch.py` / `facade.py` 仍为 large facade files,物理拆分 deferred

## 已验证的对外接口

| 入口 | 用途 | 状态 |
|---|---|---|
| `from kernel.sdk import Entity, Field, Identity, ...` | Python SDK product surface | 已验证 |
| `from kernel.application import *` | Python runtime authority surface | 已验证 |
| `from agent.extraction import extract_document` | Python 产品 API | 已验证 |
| `from agent.extraction import extract_document_from_ir` | pre-compiled schema IR 入口 | 已验证 |
| `agent.service.app:app` | extraction HTTP `/v1/extraction/documents` | 已验证 + tests |
| `service.app_v1:app` | kernel runtime / rules / registry HTTP routes | 已验证 |
| `from service.static_ui import render_audit_static_site` | 审计 HTML 渲染 | 已验证 |
| `from domains.ecss.compliance import ...` | ECSS 合规矩阵 + VCD predicates | 已验证 |

## 当前 active 蓝图状态

- Runtime-authority cleanup:implemented,留在 active,暂不 archive。
- OS-prep v0.1:implemented,仍留 active;#2 packaging hardening / #11 README / #12 optional-domain handling / #8 kernel Ruff gate 已落地。
- Audit-delivery contract:implemented,仍留 active;`kernel.audit` query package / `service.static_ui` rendered static site / `domains.ecss.compliance` row assembly 三方交付边界已拆清。
- v0.1 release-candidate verification:implemented;verdict = `conditional pass`(`bf652a1`)。Hard gate 1.2 由 `e9dd311` inline fix(`src/kernel/tests/__init__.py`)解决。post-fix repository state 后续 RC 跑可期 `pass`。留 active,等真实 publish + 短期稳定窗口后归档。
- v0.1 onboarding hardening:implemented;已合入并 push 到 `origin/oss-prep-v0.1`(`962f087`),后续文档/example polish 已 push 至 `8d7e339`。落地内容包括 `Identity(primary_key=True)` 强制规则、application write cardinality、SDK `set/add` application write-plan adapter、D7 user journey probe、SDK error/repr polish、kernel-only docs boundary polish、D7 notebook mirror + audit read-back/evidence-tree inspection、field-sugar semantics docs、Layer 1/2 signposting、public write/read API docstrings。留 active,等真实 publish + 短期稳定窗口后与其他 v0.1 蓝图一起归档。
- 早期 active 蓝图仍需后续 triage,不要把 memory 当成当前实现真相。

## 下一步方向

**优先级 1:OS-prep release close-out**

- v0.1 onboarding hardening:已完成并 push。当前 release-onboarding path 已由 `test_v01_onboarding_journey.py` 锁定:`ref → set/add → get → query → evaluate(native) → accept → export audit package`。同一 journey 已镜像为可运行 notebook:`examples/10_v01_onboarding_journey.ipynb`,并扩展 audit package read-back + native candidate evidence-tree inspection;native path 不产生 `EvidenceGraph`,`EvidenceGraph` 仍是 PyReason/ProbLog/Souffle adapter provenance artifact。该 notebook 仍不进入 release projection allowlist。`SDKStore.set/add` 现在走 application write-plan,会 materialize identity / exists;unmanaged e_ref 会抛 `SDKStoreError(code="UNRESOLVABLE_E_REF")`;set→multi / add→single 会抛 `CardinalityError`;Entity 必须至少有一个 `Identity(primary_key=True)`。SDK docs 现在明确 `u.field == value` 是 single/multi schema field 的推荐 where sugar,`Pred(...)` 是低层 escape hatch;root README / SDK guide / application docs 已加 Layer 1(`kernel.sdk`) vs Layer 2(`kernel.application`) 路标。
- v0.1 RC verification:已完成,verdict = `conditional pass`(`bf652a1`,2026-04-28)。dist artifact 已清除,release-day 时重新 build。
- release-surface cleanup:implemented。`scripts/project_release_surface.sh` + `scripts/release_surface_allowlist.txt` 生成 261-file sanitized projection,projection-built wheel 161 entries / 156 `kernel/` / 0 deny hits,clean venv quickstart 输出 `Alice`;v0.1 仍 wheel-only(no sdist),未 public repo push / 未 upload / 未 tag。
- release management model:私有 monorepo 是 source of truth;public `factpy-kernel` repo 是 projection artifact,不反向开发;PyPI wheel / public source release 从 verified projection tree 构建。长期规则见 `docs/architecture_principles.md` 的 `Release surface governance`。
- #4 package name:默认锁 `factpy-kernel`;2026-04-28 exact-name check 当前可用,但 publish time 仍需重跑并通过首次 upload / trusted publishing 完成 reservation
- #8 CI gate follow-up:`src/kernel` Ruff 已 blocking;service/tools Ruff(62 errors)与 mypy(`src/kernel`:385 errors / 73 files,tests 占 280)仍需逐步清 baseline 后升 blocking
- release validation:按 README 的 kernel-only install path 和 `test_wheel_kernel_only_packaging.py` 做 wheel inspection
- #2/#11/#12 已落地:package discovery `kernel*` only;README kernel-first;`AuditQuery.list_compliance_matrix(...)` 缺少 `domains.ecss` 时抛 `AuditOptionalDomainError`
- #7 OpenAPI yaml 已因 kernel-only OSS surface closed: v0.1 不发布 HTTP/OpenAPI artifact

**优先级 2:primitive-contract follow-up**

- K traps:Query id/version asymmetry,where validation timing,Derivation head/target/head_vars 三形态
- pyreason adapter 当前仍 import SDK DSL primitives;后续可通过下沉 DSL primitive 或抽 runtime protocol 解耦

**不该在本阶段偷做**

- 不在 runtime cleanup 里改 OS-prep blueprint 决策项
- 不为行数目标强拆 `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py`
- 不重写全局 exception hierarchy
- 不把 SDK docs 中 application internal DTO 包装成 SDK public API

## 工程踩坑记录

- **Bash tool 实际是 zsh**:`for f in $VAR` 不 word-split,用 `while IFS= read -r f; do ... done <<< "$VAR"`
- **macOS BSD sed 不支持 `\b` word boundary**:bare-string token 替换用具体上下文
- **跨包搬迁文件相对 import 必须改绝对**:所有跨包搬迁 `.py` 都要扫
- **__init__.py re-exports 必须扫**:搬迁 `.py` 文件时检查原 package `__init__.py`
- **模块级跨包 import 可能引入加载耦合**:必要时使用 lazy import,但要记录边界

## 启动阅读顺序(新 session 用)

1. [本文件](/Users/zhenzhili/hnsm-backend/memory/current.md)
2. [runtime-authority cleanup blueprint](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md)
3. [AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) + [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md)
4. [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
5. [src/kernel/application/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/application/docs/README.md)
6. [src/kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/sdk/docs/README.md)
7. [docs/blueprints/active/2026-04-27_oss-prep-v0.1.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-27_oss-prep-v0.1.md)
8. [docs/blueprints/active/2026-04-29_v0.1-onboarding-hardening.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-29_v0.1-onboarding-hardening.md)
