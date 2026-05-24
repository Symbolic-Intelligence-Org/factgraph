# D9 Decision: T3 Later Adapter Matrix And Rejection Policy

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks the T3 later engine support matrix, adapter grammar floor, aggregate preservation, and adapter rejection error policy for RuleExpr execution lowering.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md` Q6, Q7, Q7a, Q9, F5, F7, F8, F10, and §10 D9 mapping.
  - D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`.
  - D7 `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`.
  - D8 `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §8 and §10.6.3.
  - Shipped `src/factgraph/core/rules/where_eval.py:125-143`, `src/factgraph/core/rules/where_eval.py:364-426`, and `src/factgraph/core/rules/where_eval.py:429-470`.
  - Shipped `src/factgraph/core/rules/where_eval.py:526-563`.
  - Shipped `src/factgraph/adapters/souffle/where_compile.py:443-580`, `src/factgraph/adapters/souffle/where_compile.py:741-798`, and `src/factgraph/adapters/souffle/where_compile.py:832-848`.
  - Shipped `src/factgraph/adapters/problog/problog_export.py:97-121`, `src/factgraph/adapters/problog/problog_export.py:230-330`, and `src/factgraph/adapters/problog/problog_export.py:337-423`.
  - Shipped `src/factgraph/adapters/pyreason/where_compile.py:30-67`, `src/factgraph/adapters/pyreason/where_compile.py:113-154`, and `src/factgraph/adapters/pyreason/where_compile.py:207-230`.
  - Shipped `src/factgraph/application/docs/rule.md:114-135`.
- Outputs / Downstream:
  - D10 evaluation result / evidence boundary.
  - Stage 3 T3 later synthesis and per-slice blueprints.
- Related:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
- Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`
- Depends on: D6, D7, and D8 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

D7 chooses a private `RuleExprLoweringPlan` with deterministic branches. D8 chooses explicit equality atoms for joins.

D9 decides how that lowered body reaches engines:

- whether D7 branches become one branch-list runtime body or multiple compiled plans;
- which engines support D8 equality atoms;
- which engines support the current atom grammar and aggregate terms;
- how public RuleExpr evaluation rejects unsupported engine/grammar combinations;
- how Q9 error policy is completed for adapter rejection.

The shipped runtime already supports two-level OR-of-AND WhereIR in native evaluation, Souffle export, ProbLog export, and PyReason branch extraction. The shipped atom grammar differs sharply by engine: native/Souffle/ProbLog support broad Form 1-style WhereIR, while PyReason is pred-only.

## 2. Scope

This decision locks:

- branch-list vs multi-plan materialization for D7 branches;
- engine support matrix for native, Souffle, ProbLog, and PyReason;
- adapter grammar floor for T3 later;
- D8 equality atom support / rejection by engine;
- aggregate-in-RuleExpr preservation and rejection by engine;
- public adapter rejection error bucket and message requirements;
- which adapter behaviors are deliberately left to later Form 2 / T4 / T5 decisions.

## 3. Non-scope

This decision does not lock:

- public result/evidence DTO shape; D10 owns it;
- proof-frame / WhyNot / EvaluateResult integration; D10/T5 own it;
- new adapter grammar support beyond what already ships;
- PyReason Form 2 expansion;
- full T4 Head / closed-head behavior;
- join lowering semantics; D8 owns it;
- public debug/lower APIs.

## 4. Decision

### 4.1 D7 branches materialize as one branch-list `CompiledDerivationPlan` body

For supported engines, D9 chooses one compiled runtime body for the D7 branch set:

- one D7 branch materializes as a normal one-level AND `where` body;
- two or more D7 branches materialize as a two-level OR-of-AND branch-list `where` body;
- D7 branch order is preserved as runtime branch index order.

The semantic target is one branch-list body per supported engine; multi-plan materialization is not used (per Option D rejected).
Per D7 §4.3, the first implementation slice may still stop at the internal `RuleExprLoweringPlan`; D9 §4.1 locks the eventual materialization shape, not the slice that must first perform materialization.

Rationale:

- shipped native, Souffle, ProbLog, and PyReason paths all already recognize branch-list WhereIR shape;
- a single branch-list body preserves D7 branch ids as existing runtime branch indexes;
- D10 can reason about branch provenance without needing to merge multiple public evaluation calls;
- D8 `materialized_atom_index` remains meaningful within each branch body.

Stage 3 may still split implementation slices by engine, but the branch-list body shape is the semantic target for all supported engines.

### 4.2 T3 later uses an engine-specific existing grammar floor

D9 rejects a portable-lowest-common-denominator grammar floor.

The first T3 later execution tranche should preserve RuleExpr structure over each engine's existing shipped grammar:

- native uses the shipped native WhereIR evaluator grammar;
- Souffle uses the shipped Souffle WhereIR compiler grammar;
- ProbLog uses the shipped ProbLog exporter grammar;
- PyReason uses the shipped PyReason pred-only grammar.

T3 later does not upgrade adapter grammar as part of this decision. If an engine already rejects a source atom kind, T3 later either preflight-rejects that engine for the lowered RuleExpr or lets a supported adapter path surface its existing validation error after D9 preflight passes.

### 4.3 Native engine is supported for D7/D8 RuleExpr lowering

`engine="native"` supports:

- D7 branch-list bodies;
- D8 equality atoms;
- existing native WhereIR atom kinds: pred, eq, in, ne, comparisons, arithmetic, not;
- aggregate terms as already shipped.

Native remains the reference support target for the first implementation slice.

Native support is still bounded by existing WhereIR validation. D9 does not allow malformed branch lists, unsupported atom shapes, empty branches, or invalid aggregate terms.

### 4.4 Souffle is supported for D7/D8 RuleExpr lowering within shipped Souffle grammar

`engine="souffle"` supports:

- D7 branch-list bodies;
- D8 equality atoms;
- existing Souffle-supported WhereIR atom kinds;
- aggregate terms as already shipped by the T2.3 Souffle adapter.

Souffle support inherits existing Souffle validation:

- predicate arity and type-domain checks still apply;
- dataflow checks for equality/comparison/not still apply;
- aggregate empty-set guard behavior remains unchanged.

D9 does not add new Souffle grammar support beyond shipped behavior.

### 4.5 ProbLog is supported for D7/D8 RuleExpr lowering within shipped ProbLog grammar

`engine="problog"` supports:

- D7 branch-list bodies;
- D8 equality atoms;
- existing ProbLog-supported WhereIR atom kinds;
- aggregate terms as already shipped by the T2.3 ProbLog adapter.

ProbLog support inherits existing ProbLog validation:

- pred atoms with arity greater than 2 remain unsupported;
- unsupported aggregate filter atoms remain unsupported;
- nested aggregate-in-aggregate-filter remains unsupported;
- ProbLog probability / semantics machinery remains unchanged.

D9 does not add new ProbLog grammar support beyond shipped behavior.

### 4.6 PyReason is supported only for pred-only lowered RuleExpr branches

`engine="pyreason"` is a subset path.

PyReason supports RuleExpr execution only when every lowered branch contains only `("pred", pred_id, terms)` atoms that the shipped PyReason compiler accepts.

PyReason rejects before adapter invocation when the lowered RuleExpr contains any non-pred atom, including:

- D8 equality atoms from explicit joins;
- source-rule eq/ne/comparison/in/not/builtin atoms;
- aggregate-containing comparison or arithmetic atoms;
- ruleref atoms if any future path tries to introduce them.

This means joined RuleExprs are not supported under PyReason in this tranche because D8 joins lower to `eq` atoms and shipped PyReason explicitly rejects `eq`.
These public preflight rejections use `SDKStoreError` per §4.9.

PyReason branch-list shape remains usable for pred-only OR branches because the shipped compiler extracts branches and emits one rule per branch.

### 4.7 Aggregate-in-RuleExpr preservation follows existing engine support

D9 preserves aggregate semantics by not rewriting aggregate terms differently for RuleExpr.

Rules:

- aggregate-local variable isolation remains independent from D7 occurrence alias-local variable isolation;
- D7 alias-scoping applies to outer Rule body variables per D7 §4.5 alias-local namespacing;
- aggregate-filter-local variables remain in T2.3's per-aggregate scope and are not promoted to D7 `RuleExprPortBinding`;
- D8 joins may only reference declared ports, never aggregate-filter-local variables;
- native, Souffle, and ProbLog preserve existing aggregate behavior;
- PyReason rejects aggregate-containing lowered branches.

Empty-set guard semantics remain exactly the shipped T2.3 semantics:

- native uses the existing `AggregateNoValue` / no-env-pollution behavior;
- Souffle `min` / `max` / `mean` keep their guard behavior;
- ProbLog `min` / `max` / `mean` keep their non-empty list guard behavior;
- PyReason aggregate behavior remains out of scope unless a later Form 2 decision supersedes this D9 decision.

### 4.8 Entity-ref and value joins use the same engine support cell after D8 type checks

D8 already validates endpoint `PortType` compatibility before adapter selection.

After D8 succeeds:

- entity-ref joins lower to equality atoms over alias-local execution variables;
- value joins lower to the same equality atom shape;
- adapter support is decided by whether the engine supports `eq`, not by whether the original port kind was entity-ref or value.

D9 does not create separate adapter behavior for entity-ref vs value joins in this tranche. If a future value-subtype extension changes compatibility rules, it must supersede D8 and then update this D9 matrix if adapter behavior changes.

### 4.9 Public adapter preflight rejection uses `SDKStoreError`

D9 completes Q9 for adapter rejection:

- D6/D7/D8 semantic lowering errors use `RuleExprError`.
- Public engine/grammar support rejection uses `SDKStoreError`.
- D9 does not add a new public error subclass.

Examples of `SDKStoreError` matrix rejections:

- `engine="pyreason"` with any D8 join equality atom;
- `engine="pyreason"` with source-rule `not`, `in`, comparison, arithmetic, or aggregate-containing atom;
- `engine="problog"` with pred arity greater than 2;
- any engine selected for a lowered atom kind known to be unsupported before adapter invocation.

The public error message must identify:

- selected engine;
- unsupported lowered atom kind or feature;
- whether the rejection comes from D8 join equality, source-rule atom grammar, aggregate grammar, or branch shape;
- at least one supported alternative engine when one is known.

Unexpected adapter/runtime failures after a supported D9 preflight may continue to surface existing adapter/core exception types. D9 only locks known matrix rejection before adapter invocation.

### 4.10 No adapter silent downgrade

T3 later must not silently drop atoms, joins, OR branches, aggregate filters, or branch provenance to make an engine accept a RuleExpr.

If an engine cannot support the lowered body under this matrix, public evaluation rejects. It must not:

- remove D8 equality atoms;
- turn joins into same-name-port heuristics;
- collapse OR branches into a single AND body;
- ignore aggregate filters;
- convert value joins into entity-ref joins or vice versa;
- fall back from the requested engine to another engine without explicit caller choice.

### 4.11 Support matrix summary

| Engine | D7 branch-list | D8 eq joins | Current non-join atom grammar | Aggregates | D9 public behavior |
|---|---|---|---|---|---|
| `native` | Supported | Supported | Existing native WhereIR grammar | Supported | Run, subject to existing validation |
| `souffle` | Supported | Supported | Existing Souffle WhereIR grammar | Supported | Run, subject to existing validation |
| `problog` | Supported | Supported | Existing ProbLog grammar; pred arity >2 unsupported | Supported with shipped limits | Run or preflight reject known unsupported grammar |
| `pyreason` | Supported for pred-only branches | Rejected | Pred-only subset | Rejected | Preflight reject unsupported atom kinds with `SDKStoreError` |

## 5. Rejected Alternatives

### Option A: Require all engines to support the full native grammar before T3 later ships

- **Why rejected**: this would turn T3 later into a cross-adapter grammar expansion project and block useful native/Souffle/ProbLog execution on PyReason Form 2 work.

### Option B: Support only native engine in the public RuleExpr path

- **Why rejected**: Souffle and ProbLog already support the key D7/D8 shapes. Rejecting them would unnecessarily narrow the tranche and postpone adapter parity that is already mostly shipped.

### Option C: Treat PyReason as fully supported and let its adapter fail

- **Why rejected**: shipped PyReason intentionally rejects non-pred atoms. Public RuleExpr evaluation should reject known unsupported matrix cells with a clear SDK-level error before adapter invocation.

### Option D: Materialize one compiled plan per D7 branch

- **Why rejected**: it makes branch identity harder to align with existing runtime branch indexes and complicates D10 evidence ordering. Existing engines already understand branch-list bodies.

### Option E: Add new adapter features in D9

- **Why rejected**: D9 is a decision document for this tranche's matrix. New adapter grammar work must appear later as scoped implementation blueprints if Stage 3 chooses it, not as an implicit D9 expansion.

### Option F: Add a new public adapter rejection error subclass

- **Why rejected**: D6-D9 keep Q9 inside existing `SDKStoreError` / `RuleExprError` buckets. A new error subclass is not justified before T5 result/error redesign.

## 6. Supporting Evidence

- Native `evaluate_where(...)` normalizes one-level AND and two-level OR-of-AND branch lists.
- Native validation and evaluation support `eq` atoms and broad WhereIR atom kinds.
- Souffle compilation supports branch-list bodies, `eq` atoms, `not`, comparisons, arithmetic, and aggregate-aware comparison dispatch.
- ProbLog export supports branch-list bodies, `eq` atoms, comparisons, arithmetic, `not`, and aggregate lowering through `findall/3` / list predicates.
- ProbLog explicitly rejects pred arity greater than 2.
- PyReason extracts branch-list bodies but validates each atom as pred-only and explicitly rejects `eq`, `not`, `ruleref`, and other atom kinds.
- Application Rule docs record that native, Souffle, and ProbLog support aggregate terms while PyReason aggregates remain out of scope per parent §10.6.3.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- D10: can decide result/evidence behavior knowing which engines can run and which reject.
- Stage 3 synthesis: can split implementation slices by native/Souffle/ProbLog support and PyReason preflight rejection.
- Future blueprints: can implement deterministic preflight checks before adapter invocation.

### 7.2 Required D10 follow-up

D10 must decide:

- whether public RuleExpr evaluation returns existing `CandidateSet` values unchanged;
- whether SDKStoreError preflight rejections carry structured diagnostic details or only a string message;
- whether branch/occurrence/join provenance from D7/D8 remains internal or becomes result/evidence metadata;
- how to document preflight rejections relative to future T5 EvaluateResult / WhyNot.

### 7.3 Stage 3 split guidance

Stage 3 should consider slices such as:

- native RuleExpr execution path first;
- Souffle/ProbLog parity after native plan materialization is stable;
- PyReason explicit preflight rejection / pred-only subset tests;
- docs and diagnostics update after public behavior is finalized.

Stage 3 may choose a different split, but it must preserve this D9 matrix.

## 8. Acceptance Criteria

- [ ] D10 cites D9 and decides whether adapter preflight errors carry structured details.
- [ ] Future implementation blueprints materialize multi-branch RuleExprs as branch-list bodies, not multiple public evaluation calls.
- [ ] Future implementation blueprints support native D7/D8 RuleExpr execution.
- [ ] Future implementation blueprints support Souffle and ProbLog where the lowered body is inside existing shipped adapter grammar.
- [ ] Future implementation blueprints preflight-reject PyReason for any non-pred lowered atom, including D8 equality joins.
- [ ] Future implementation blueprints preserve aggregate-local variable isolation and empty-set guard semantics for native/Souffle/ProbLog.
- [ ] Future implementation blueprints reject unsupported engine/grammar matrix cells with `SDKStoreError`.
- [ ] Future implementation blueprints' `SDKStoreError` matrix rejection messages identify the §4.9 required fields: selected engine, unsupported lowered atom kind or feature, rejection source, and at least one supported alternative engine when known.
- [ ] Future implementation blueprints do not silently drop joins, OR branches, aggregate filters, or atom kinds to fit an engine.
- [ ] No new public error subclass is introduced by D9.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | D9 chooses branch-list materialization, native/Souffle/ProbLog support within shipped grammar, PyReason pred-only subset with preflight rejection for non-pred atoms, and `SDKStoreError` for public adapter matrix rejection. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Clarified eventual materialization vs first slice, PyReason `SDKStoreError` cross-reference, aggregate scope layering, and §4.9 message-contract acceptance. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1/WC2/WC4/WC5 and N1 addressed; aggregate scope layering and adapter rejection message contract reviewed clean; D10 unblocked. |
