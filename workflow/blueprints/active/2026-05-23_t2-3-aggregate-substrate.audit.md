# Task Blueprint Audit: T2.3a — Core AggregateExpr substrate (IR + validation + Python eval + raw resolver)

> **Title superseded note (post Step 4.2 v1)**:original title was "T2.3 — AggregateExpr substrate (IR + Python eval + SDK ergonomic)"。Step 4.2 v1 split scope to T2.3a substrate-only;SDK ergonomic deferred to T2.3b。Title updated above。

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3-aggregate-substrate.md](./2026-05-23_t2-3-aggregate-substrate.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md)
  - Archived T1.1 [2026-05-22_t1-1-rule-class-additive.md](../archive/2026-05-22_t1-1-rule-class-additive.md)
- Blueprint: [2026-05-23_t2-3-aggregate-substrate.md](./2026-05-23_t2-3-aggregate-substrate.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | T2 Track 3rd sub-slice (after T2.1 ne adapter dispatch + T2.2 ArithExpr substrate). 100% genuinely new substrate (verified via G2 source-grep). Class assessment: S with documented size override. |

## Decision Notes

### 2026-05-23 — Initial scope lock (superseded by Step 4.2 v1 tightening — see below)

> **Superseded note**:original scope included SDK ergonomic helpers + bridge passthrough。Step 4.2 v1 surfaced P0(Public API impact contradiction)→ scope split。**Current scope is T2.3a substrate-only**(per Step 4.2 v1 + v2 tightening sections below)。Original Initial scope lock preserved here for historical context。

- T2.3 is the T2 Track closing slice (Atom 语言闭合 final piece) — adds AggregateExpr substrate net-new.
- G2 audit confirms shipped Aggregate substrate empty: `where_ast.py` no AggregateAtom, no `_AGGREGATE_KINDS`; `where_ast_validate.py` no aggregate validation; `where_eval.py` no aggregate eval; adapters no aggregate dispatch.
- Parent essay §10.6.3-§10.6.9 + §8.8 fully lock C99-C105 semantics — no load-bearing decision pending.
- Scope narrowed to **substrate + Python eval + SDK ergonomic + bridge passthrough**. Adapter wires (Souffle aggregate body / ProbLog findall) deferred to T2.3.b and T2.3.c follow-up sub-slices. — **SUPERSEDED by Step 4.2 v1**;current scope is substrate-only(no SDK ergonomic / no bridge passthrough);SDK + bridge → T2.3b。

### 2026-05-23 — S vs M class assessment (post Step 4.2 v1 corrections;v0 row "Public API impact None" was incorrect — see Step 4.2 v1 section below)

User explicitly flagged this slice as S → 可能 M during T2.2 review:
> "T2.3 AggregateExpr | S → 可能 M | C99-C105 7 commitments 紧耦合 + AggregateExpr 是 100% genuinely new;若 impl 期出现 cross-commitment 决策点 → 升 M"

Drafter v0 assessment for S-class with size override(**Public API impact row was WRONG at v0**;corrected in Step 4.2 v1 by removing SDK helpers from scope):

| Factor | T2.3 reality (v0) | Trigger fire? (v0) | Corrected (v1+) |
|---|---|---|---|
| Public API rename / replacement | None | No | None(unchanged)|
| Cross-commitment Q load-bearing | None — parent essay fully locks C99-C105 | No | None(unchanged)|
| Design vs shipped ≥ 3 commitments conflict | No conflict — 100% genuinely new additive | No | No(unchanged)|
| Sub-slice count vs Track plan §2 prediction | Track plan §2 listed T2.3 as one row | Within prediction | Within prediction(but slice split to T2.3a + T2.3b after v1)|
| **Public API impact** | **None / internal substrate (WRONG: agg_* helpers ARE public SDK API)** | No | **Now genuinely None** — SDK helpers removed from T2.3a scope |
| Cross-commitment 复杂度 | High (C99-C105 interrelated) — but no load-bearing decision needed | Triggers vs no decision needed = no fire | Unchanged |
| Size budget | ~1160 LOC est — 4x above ~300 LOC S guideline | Size flags concern, not a hard trigger | ~1280 LOC est in v1 (slightly increased due to scoping + raw resolver helpers); still S-class |

**Conclusion (v1+)**: §1.2.4 trigger conditions do not fire. Size is the only S-class concern. Drafter recommends S-class with size override + escalation contingency。**Public API impact row corrected — now genuinely None post-split**。

If reviewer disagrees on size, blueprint §5.10 prepares two-way split:
- T2.3.a: IR + validation + Python eval + tests (~400 LOC)
- T2.3.b: SDK ergonomic + bridge passthrough + tests (~250 LOC)

This split keeps each piece comfortably within S budget.

### 2026-05-23 — G1-G7 visible gate mapping

- **G1** — Blueprint §1 + §2 cite parent essay §10.6.3-§10.6.9 (C99-C105) + §8.8 explicitly. Every §2 sub-goal headers reference a C-number.
- **G2** — Blueprint §4 documents complete G2 source-grep audit across 6 files (where_ast / where_ast_validate / where_eval / sdk dsl expr / sdk dsl application_rule / application protocol rule). Verified all empty.
- **G3** — Blueprint §4 uses file:line citations (where_ast.py:31 / :77 / :95-96; where_ast_validate.py:33-34; where_eval.py:38; sdk/dsl/expr.py specific function locations; application/protocol/rule.py:_ALLOWED_ATOM_TYPES).
- **G4** — Blueprint §2 sub-goals 2.1-2.10 each labeled with C-number or specific responsibility (2.10 is bridge passthrough; 2.11 is allowlist verification).
- **G5** — Blueprint §3 Non-goals explicitly lists 10 deferred items with rationale and where each lands (T2.3.b / T2.3.c / parent essay extension candidate / parent §10.5 deferred).
- **G6** — Reviewer should independently spot-check: (1) `_BUILTIN_TAGS` contents at where_ast.py:96, (2) absence of AggregateAtom in where_ast.py, (3) absence of aggregate eval in where_eval.py, (4) T1.1 archived `_ALLOWED_ATOM_TYPES` unchanged by T2.3 scope, (5) parent essay §10.6.3-§10.6.9 semantic completeness (no ambiguity demanding decision doc).
- **G7** — Blueprint §5.8 lists 5 pre-impl precondition checks. Check #5 specifically gates S → M escalation if C99-C105 semantic ambiguity surfaces.

### 2026-05-23 — Cross-slice contract preservation

- T1.1 `_ALLOWED_ATOM_TYPES` MUST stay `(PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)` — AggregateAtom is Term-position, not top-level Atom. Verified by §2.11, §4.6, §5.7, §6 invariant, §7 acceptance.
- T1.2 bridge passthrough chain (`lower_where → parse_where_ir_to_ast → application Rule construction`) handles new IR kinds automatically. T2.3 only extends `_serialize_term` + `_collect_term_vars` for AggregateAtom (content_digest correctness). No behavioral change to existing bridge logic.
- T2.1 ne adapter dispatch unchanged (no adapter touched in T2.3).
- T2.2 ArithExpr substrate unchanged (`_ARITH_KINDS` not modified, `_BUILTIN_TAGS` not extended).
- ProbLog hygiene boundary unchanged (no `audit/round_events.py` touched).
- meta-confidence fixture cleanup unchanged (no test fixtures touched in T2.3 production code path).

### 2026-05-23 — Reviewer attention points

Per user's Step 4.2 review focus areas:

1. **C99-C105 拆为 S-class substrate vs 升 M with decision doc**: drafter chose S-class with size override. Reviewer should verify §1.2.4 triggers truly don't fire OR push for M / split if size-only concern warrants.
2. **三端语义一致性**: T2.3 scope intentionally excludes Souffle / ProbLog wires (deferred to T2.3.b / T2.3.c). Python eval is the only "end" landing in this slice. Reviewer should accept this split or push for inclusion.
3. **G7 gate verifying shipped substrate empty + semantic boundaries**: §5.8 5 checks. Verify check #5 is sufficient to catch C99-C105 ambiguity before impl.

### 2026-05-23 — Potential reviewer P-finding candidates

Drafter anticipates these as likely review points:

- **Size override**: 1160 LOC vs 300 LOC S guideline is real. Reviewer may P1 require split into T2.3.a + T2.3.b before scoped anchor.
- **NoValue propagation tests**: §5.9 lists tests but should explicitly include "NoValue inside ArithExpr operand → result NoValue" cross-T2.2 interaction test. Drafter included this in mental list but may not be explicit enough in §5.9 test outline.
- **C104 variable scoping algorithm specifics**: §5.3 shows skeleton but doesn't fully spec the algorithm. Reviewer may require tightening on "exactly when a Var is considered aggregate-local vs correlated".
- **AggregateAtom inside CmpAtom serialization for content_digest**: §5.6 covers `_serialize_term` extension but does not specify ordering/canonicalization for filter atoms within serialized aggregate. Reviewer may P1 require explicit canonical ordering.

### 2026-05-23 — Step 4.2 v1 tightening applied (P0+P1+P2+P3+P4+P5)

User Step 4.2 review surfaced 5 substantive findings + 1 Minor — drafter anticipated 4 of these in initial draft Decision Notes above; user surfaced 2 more (P1 per-env semantics + P2 raw tuple evaluator path) that drafter missed.

**P0 (Blocker) — Scope too thick;public API impact mis-stated**:
Initial draft claimed "Public API impact None / internal substrate" while including `agg_count/agg_sum/agg_min/agg_max/agg_mean` SDK helpers (which ARE public API). Self-contradiction. **Adopted**: scope split into:

- **T2.3a (this slice)**: core IR + validation + Python eval + raw aggregate term resolver (in cmp/arith paths) + application Rule serialization branches. NO SDK ergonomic. NO bridge ergonomic. NO public docs.
- **T2.3b (future slice)**: SDK ergonomic helpers + bridge ergonomic + DSL `_AggregateRef` + public docs + export policy.

Blueprint title renamed to "T2.3a — Core AggregateExpr substrate". §3 Non-goals explicitly enumerates SDK + bridge + DSL deferrals. §6 invariants gain SDK-deferral + bridge-deferral. §7 acceptance includes scope diff verifications (SDK files 0 lines + bridge files 0 lines).

**P1 (Blocker) — Per-env aggregate semantics (C104 correlated)**:
Initial draft §5.4 pseudocode: `_eval_aggregate_atom_value(aggregate, envs)` reduced over entire env-list globally. Per C104 (parent §10.6.8), aggregate MUST be computed per outer env so correlated vars provide seed for filter. Otherwise two users' order counts merge into one global count — semantic error.

**Adopted**: §5.5 rewritten with `_resolve_aggregate_term_for_env(env, aggregate_term, view_facts, ast_gate_on)` operating on **one env at a time**. Filter is evaluated starting from `[env]` initial env-list. §7 acceptance adds explicit per-env correlated test: two outer envs (u-1 + 3 orders / u-2 + 5 orders) produce count=3 / count=5 separately, NOT merged count=8. §6 adds "Per-env aggregation invariant".

**P2 (Required) — Raw tuple evaluator path vs AST execution**:
Initial draft §5.4 used `_eval_cmp_atom(env, atom: CmpAtom, ...)` style — treating atoms as AST dataclass instances. But `where_eval.evaluate_where` (line 41-88) parses AST only for **validation gating** (line 52). Actual execution flows through `_normalize_where` → `_eval_body` using **raw tuples** (line 78-79).

**Adopted**: §5.6 rewritten with raw tuple-aware design:

- `_is_aggregate_term(term)` recognizes aggregate tuples by `term[0] in _AGGREGATE_KINDS`.
- `_resolve_cmp_operand_for_env(env, operand, view_facts, ast_gate_on)` and `_resolve_arith_operand_for_env(...)` extend existing operand resolvers in raw evaluator path.
- §1 Problem section + §4.3 add explicit clarification of raw tuple evaluator path.
- §6 adds "Raw-tuple-evaluator invariant".
- §5.8 G7 precondition #2 explicitly verifies raw evaluator path.

**P3 (Required) — C104 scoping algorithm precise dataflow rule**:
Initial draft §5.3 had placeholder pseudocode (`filter_vars = ...`, `outer atoms after aggregate should not reference local_vars`). Adopted user-proposed precise dataflow:

- **`requires`**: `(target_vars ∪ filter_vars) ∩ outer_bound_vars` — correlated subset only.
- **`binds`**: `∅` — aggregate term binds nothing.
- **Result binding**: only via enclosing `CmpAtom("eq", outer_var, aggregate_term)`.

§5.4 rewritten with concrete helpers `_aggregate_correlated_requires` / `_aggregate_local_vars` / `_validate_aggregate_scoping`. §5.7 application Rule `_collect_aggregate_term_vars` documents reliance on validator pre-check. §6 adds "Filter-local var isolation invariant".

**P4 (Required) — C101 NoValue × ArithExpr resolved (Option a — implement)**:
Initial draft had §2.6 require NoValue propagation in ArithExpr operands + §5.9 tests for it BUT §3 Non-goal said no AggregateExpr ArithExpr coupling. Self-contradiction.

**Adopted Option (a)** — implement NoValue × ArithExpr via raw resolver. §3 Non-goal "No AggregateExpr ArithExpr coupling beyond what existing BuiltinAtom ArithExpr lowering handles naturally" REMOVED. §2.6 + §5.6 explicit: `_eval_arith_atom` operand resolver invokes `_resolve_arith_operand_for_env` which calls `_resolve_aggregate_term_for_env` if operand is aggregate tuple. NoValue causes the atom to be violated for that env (env excluded from output), no Python exception. §6 adds "NoValue × ArithExpr invariant". §7 adds explicit test (`agg_sum(empty_set) + 1 > 5` → atom violated, no exception).

**P5 (Minor/Required) — Term type alias forward-ref**:
Current `Term: TypeAlias = Var | Const` defined at `where_ast.py:31`, before `AggregateAtom` would exist. `AggregateAtom.filter: list[Atom]` also references `Atom` defined later.

**Adopted Strategy A (restructure)** — move `Term` and `Atom` type alias definitions to AFTER all dataclass definitions. §5.2 added documenting this. Strategy B (string forward-ref) noted as fallback if Strategy A causes test breakage during impl. §5.8 G7 precondition #4 verifies no existing code relies on current `Term` definition position.

**Summary of Step 4.2 v1 changes**:

| Section | Change |
|---|---|
| Title | T2.3 → T2.3a — Core AggregateExpr substrate (IR + validation + Python eval + raw resolver) |
| §1 Problem | Added explicit raw tuple evaluator path clarification |
| §2 Goals | Removed §2.9 SDK ergonomic + §2.10 bridge passthrough + §2.11 allowlist (latter folded into §6). Added §2.6 NoValue × ArithExpr explicit. Added §2.8 per-env semantics |
| §3 Non-goals | Explicit T2.3b deferrals (SDK helpers + DSL `_AggregateRef` + bridge ergonomic + public docs); removed "no AggregateExpr ArithExpr coupling" deferral (now in scope) |
| §4 Current Context | Added §4.3 raw evaluator path explicit; §4.4 application Rule serialization filter-local isolation note |
| §5 Proposed Shape | Rewrote: §5.2 Term restructure (Strategy A) / §5.3 precise filter validation / §5.4 precise scoping dataflow / §5.5 per-env evaluator / §5.6 raw resolver in cmp/arith / §5.7 application Rule branches with filter-local isolation / §5.8 G7 precondition extended |
| §6 Boundaries | Added per-env / NoValue isolation / NoValue × ArithExpr / Filter-local var isolation / Raw-tuple-evaluator / SDK-deferral invariants |
| §7 Acceptance | Per-env correlated test + NoValue × ArithExpr test + filter-local var isolation test + scope diff verifications for SDK 0-touch |
| §8 Implementation Plan | Step order revised: G7 precondition recorded BEFORE impl; raw resolver explicit in step 4 |
| §9 Docs | No SDK docs change (SDK 0-touch); application/docs internal note only; T2.3b carries public docs |
| Size estimate | ~1280 LOC (slightly increased due to scoping helpers + raw resolver additions); still S-class with size override; Public API impact NOW genuinely None |

**Blueprint stays `Status: draft`** pending user review of v1 tightening.

### 2026-05-23 — Step 4.2 v2 tightening applied (P1+P2+P3+P4+P5)

User Step 4.2 v1 re-review surfaced 4 Required + 1 Minor — all genuine implementation-contract holes that v1 did not close。Drafter applied all 5。

**P1 (Required) — Application Rule filter-local var two-pass algorithm**:
v1 §5.7 had `_collect_aggregate_term_vars(agg, ...)` iterate filter atoms calling `_validate_atom(...)` which **adds ALL filter vars to seen_vars**(including aggregate-local)。Self-contradicted with §4.4 "collect only correlated"。Punt to "trust constructor" was unacceptable。

**Adopted**:explicit **two-pass** algorithm in `Rule.__post_init__`:
- Pass 1:walk top-level atoms,treating AggregateAtom Term-position values as **opaque**(not recursed)。Builds `outer_seen_vars`。
- Pass 2:walk AggregateAtom Term-position values with `outer_seen_vars` context;collect ONLY correlated subset = `(target_vars ∪ filter_vars) ∩ outer_seen_vars`。Filter-local vars(`filter_vars - outer_seen_vars`)NEVER enter `seen_vars`。
- ports validation against `seen_vars` after pass 2 → ports cannot reference aggregate-local vars by construction。

§5.7 fully rewritten with `_collect_non_aggregate_atom_vars` + `_collect_aggregate_term_correlated_vars` + `_collect_correlated_from_aggregate` helpers。Application Rule's own algorithm is independently correct;does NOT rely on AST validator's pre-check。Validator at AST layer is additional defense,not only line。

§7 acceptance adds explicit application Rule filter-local isolation test。

**P2 (Required) — Target Var binding rule**:
v1 had no construct-time check that aggregate target Var has a binding source。`agg_sum("$unbound_amount", filter=[PredAtom("Order:exists", ["$o"])])` would surface only at runtime as unresolved。

**Adopted**:new §2.5b "Target Var binding rule"。For `kind in {"sum", "min", "max", "mean"}` with target Var:
- target Var MUST be in `outer_bound_vars ∪ filter_bound_vars`
- `filter_bound_vars` = vars bound BY filter atoms(`pred` new Var / `eq` Var-on-unbound / `in` declaration)
- Otherwise `AggregateVariableScopeError` raised construct-time
- §7 adds explicit test:`agg_sum(Var("$unbound"), filter=[PredAtom("Order:exists", [Var("$o")])])` → reject

Confirmed no conflict with parent C99-C105:parent essay examples implicitly assume target is filter-scoped or correlated;P2 is new construct-time validator for what was implicitly assumed,no semantic change。

**P3 (Required) — Full where_eval.py helper coverage**:
v1 §5.6 only mentioned `_eval_cmp_atom` + `_eval_arith_atom` operand resolvers。User cited 4 additional helpers:
- `_validate_atom` (`where_eval.py:355`)
- `_term_known_for_plan` (`where_eval.py:891`)
- `_atom_eval_score` (`where_eval.py:991`)
- `_vars_in_atoms` (`where_eval.py:1067`)

If aggregate term tuples pass through these without aggregate-awareness:
- `_validate_atom` may reject aggregate as unknown kind
- `_term_known_for_plan` may treat aggregate as never-known(plans don't fire)or always-known(plans fire prematurely)
- `_atom_eval_score` may score aggregate as 0-cost(planner orders catastrophically)
- `_vars_in_atoms` may drop aggregate-internal correlated vars(not-body correlation breaks)

**Adopted**:new §5.6b table enumerating ALL helpers requiring aggregate-term-aware extension。Each helper gains `_is_aggregate_term(term)` check + dedicated aggregate-handling branch。§7 acceptance adds explicit test:"All where_eval.py aggregate-aware helpers covered"。

**P4 (Required) — Bridge passthrough claim vs SDK 0-touch contradiction**:
v1 §3 Non-goal said "Raw IR tuples can still flow through `build_application_rule` if user constructs them directly"。But §7 required `sdk/dsl/application_rule.py` 0-touch。Bridge's `_collect_vars_from_term` (`:181`) and var canonicalization (`:250`) don't recognize `AggregateAtom`,so claim was false。

**Adopted**:**delete passthrough claim**。§3 rewritten explicit:
- T2.3a supports **direct application Rule construction** via `application/protocol/rule.py` with `AggregateAtom` Term-position arguments(YES)
- T2.3a does NOT support `build_application_rule` with aggregate IR(NO — `sdk/dsl/application_rule.py` 0-touch verified)
- End-to-end DSL ergonomic path → T2.3b

§7 acceptance adds explicit "bridge aggregate path NOT tested as supported"。

**P5 (Minor) — Audit log current-truth drift**:
v1 audit log header + Initial scope lock + S/M table still described v0 scope(SDK ergonomic + bridge passthrough + "Public API impact None")。User flagged historical entries OK to preserve but **current title / current scope** must explicitly say "superseded by Step 4.2 v1"。

**Adopted**:
- Audit log title updated to "T2.3a — Core AggregateExpr substrate (IR + validation + Python eval + raw resolver)" with "Title superseded note" pointing to v1
- "Initial scope lock" section gains "(superseded by Step 4.2 v1 tightening — see below)" marker + superseded line for the SDK/bridge scope assertion
- S/M assessment table:annotated "Public API impact" row both v0(WRONG)and v1+(corrected);table title gains "(post Step 4.2 v1 corrections)" prefix

**Summary of Step 4.2 v2 changes**:

| Section | Change |
|---|---|
| §3 Non-goals | Bridge passthrough claim deleted(P4);explicit "T2.3a supports direct construction NOT bridge ergonomic" |
| §2.5b NEW | Target Var binding rule(P2) |
| §5.6b NEW | Full where_eval.py helper coverage table(P3) — `_validate_atom` / `_term_known_for_plan` / `_atom_eval_score` / `_vars_in_atoms` |
| §5.7 | Rewritten with two-pass algorithm(P1) — outer_seen_vars + correlated-subset isolation;no "trust constructor" punt |
| §7 Acceptance | Added:application Rule filter-local isolation test(P1)/ target Var binding rule test(P2)/ all helpers covered test(P3)/ bridge aggregate path NOT tested(P4) |
| Audit log | Title updated(P5);Initial scope lock + S/M table marked superseded with v1 corrections |

**Blueprint stays `Status: draft`** pending user review of v2 tightening。Predict 0 P-findings if v2 holds — but if any new contract hole surfaces,further v3 tightening rather than skip to scoped。
