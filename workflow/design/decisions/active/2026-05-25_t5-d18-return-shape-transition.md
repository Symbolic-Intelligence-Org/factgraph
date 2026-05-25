# D18 Decision: T5 Return-Shape Transition Strategy

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks public `evaluate(...)` return-shape transition policy before DTO implementation.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q3, F1, F3, F10, F12, and §6 C62-C63 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` §4.1, §4.4, §4.7, and §4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` §4.1-§4.9.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.8.1, §5.8.2, C61-C63, and C65.
  - Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:241-252` and `:256-261`.
  - Shipped `src/factgraph/sdk/store.py:420-475`, `:2211-2384`, and `:2388-2445`.
  - Shipped docs and tests grep showing public `list[CandidateSet]`, `engine_options`, `registry`, `accept`, and `accept_many` assumptions.
- Outputs / Downstream:
  - D19 digest source-of-truth.
  - D20 explanation envelope and row resolver behavior.
  - D23 legacy SDK hard-cut plan.
  - D24 final SDK `Rule` flip.
  - Stage 3 T5 synthesis and return-shape implementation blueprint(s).
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16 and D17 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C62 requires:

```python
fg.eval.evaluate(expr, head=Rule, engine=..., semantics=...) -> EvaluateResult
```

and deletes public `engine_options=`, `registry=`, `fg.eval.accept`, and `fg.eval.accept_many`.

Shipped SDK currently returns `list[CandidateSet]` from:

- RuleExpr / application head Rule path;
- legacy SDK `Inference` path;
- structured derivation dict path;
- fallback store evaluation path.

Shipped docs and tests rely on `list[CandidateSet]`, `CandidateSet` key fields, `engine_options`, `accept`, `accept_many`, and direct candidate acceptance. D17 already locks the final public target: `EvaluateResult` with `EvaluateRow` rows, while `CandidateSet` becomes an internal adapter/runtime artifact.

D18 decides the public migration mode. It does not decide digest formulas, Explanation, row.close, service-route hard-cut mechanics, or final SDK `Rule` naming.

## 2. Scope

This decision locks:

- whether public `fg.eval.evaluate(...)` is hard-cut to `EvaluateResult` or has an additive transitional surface;
- whether RuleExpr, application head Rule, legacy SDK `Inference`, and structured derivation dict evaluate paths flip together;
- whether `engine_options=` and `registry=` remain accepted at the public `evaluate(...)` surface during the return-shape flip;
- whether `accept` / `accept_many` are removed in the same implementation slice as the return-shape flip;
- whether any compatibility helper is allowed;
- the minimum pre-implementation blast-radius gates before a return-shape implementation blueprint.

## 3. Non-Scope

This decision does not lock:

- DTO fields; D17 owns them;
- digest formulas and source fields; D19 owns them;
- `Explanation` envelope and row resolver behavior; D20 owns them;
- `row.close()` behavior; D21 owns it;
- why-not disposition; D22 owns it;
- old API hard-cut mechanics and service-route update plan; D23 owns them;
- final SDK `Rule` naming; D24 owns it;
- semantics consistency and `semantics=` replay policy; D25 owns it;
- full C73-C78 semantics wrapper implementation; D26 owns it;
- docs wording; implementation blueprints own docs after D23/D24 decisions.

## 4. Decision

### 4.1 Public `fg.eval.evaluate(...)` hard-cuts to `EvaluateResult`

D18 adopts a hard-cut for the public SDK evaluate surface:

```python
fg.eval.evaluate(...) -> EvaluateResult
```

T5 does not introduce:

- `evaluate_v2`;
- `evaluate_result`;
- `evaluate(..., result_shape=...)`;
- `evaluate(..., return_candidates=True)`;
- a long-lived compatibility mode returning `list[CandidateSet]`.

Rationale:

- Parent §5.8 calls for alpha direct break with no transition for this API family.
- D17 already classifies `CandidateSet` as internal artifact.
- A parallel public surface would double docs, tests, and support burden.
- The project has consistently preferred narrow public API decisions over indefinite compatibility surfaces.

### 4.2 All public evaluate entry paths flip together

The hard-cut applies to all public SDK `evaluate(...)` entry paths:

- application Rule / RuleExpr with `head=application head Rule`;
- legacy SDK `Inference`;
- structured derivation dicts currently accepted by SDK evaluate;
- direct `fg.evaluate(...)` / `fg.eval.evaluate(...)` aliases if both remain public at the time of implementation.

Implementation may internally normalize every path through `CandidateSet` or lower-level runtime rows, but public callers see `EvaluateResult`.

D18 rejects a mixed state where RuleExpr returns `EvaluateResult` while legacy `Inference` still returns `list[CandidateSet]`, or vice versa. Mixed return shapes would make `fg.eval.evaluate(...)` depend on input kind in a way that undermines D17's public DTO foundation.

### 4.3 `CandidateSet` compatibility is internal-only after the flip

T5 may keep internal helpers that convert:

```text
CandidateSet -> EvaluateRow
tuple[CandidateSet, ...] -> EvaluateResult
```

Those helpers are implementation details and test fixtures. They are not public SDK methods.

Allowed internal names:

- `_candidate_set_to_evaluate_row(...)`;
- `_candidate_sets_to_evaluate_result(...)`;
- equivalent private helpers in application protocol or SDK implementation.

Disallowed public compatibility surfaces:

- `fg.eval.evaluate_candidates(...)`;
- `fg.eval.evaluate(..., as_candidates=True)`;
- SDK re-export of a new `CandidateSetResult`;
- docs recommending `CandidateSet` as the T5 public evaluation result.

Existing core/runtime tests may continue to import `CandidateSet` from `factgraph.core.derivation.candidates` where they directly test runtime internals.

### 4.4 `engine_options=` and `registry=` are removed from public evaluate with the return-shape flip

D18 aligns the return-shape flip with parent C62's public parameter cleanup:

- public `fg.eval.evaluate(...)` no longer accepts `engine_options=`;
- public `fg.eval.evaluate(...)` no longer accepts `registry=`.

Advanced/internal runtime code may keep equivalent lower-level parameters where needed, but those are not SDK public evaluate kwargs.

Implementation must reject these kwargs with `SDKStoreError`, not silently ignore them.

D23 owns full legacy hard-cut blast radius, but D18 locks that the return-shape flip cannot ship while keeping `engine_options=` / `registry=` as public evaluate kwargs. Otherwise the new `EvaluateResult` surface would launch with already-deprecated parameters.

### 4.5 `accept` and `accept_many` removal is coupled to hard-cut planning, not necessarily the same feat commit

Parent C62 deletes `fg.eval.accept` and `fg.eval.accept_many`.

D18 locks the target state: after the T5 hard-cut, public `fg.eval.accept` and `fg.eval.accept_many` are gone from the SDK eval namespace.

D18 does not require the same implementation commit that changes `evaluate(...)->EvaluateResult` to remove `accept` and `accept_many`. Stage 3 may choose either:

1. one larger hard-cut slice that flips return shape and removes `accept*`; or
2. a DTO/evaluate return-shape slice followed immediately by a D23 hard-cut slice that removes `accept*` and updates docs/tests.

If Stage 3 chooses the split approach, the intermediate state must remain local to the T5 branch and must not be pushed or archived as a stable cycle milestone.

### 4.6 `run`, `check`, `diagnose`, `why_not`, and `what_if.*` are D20-D23 territory

D18 does not decide removal timing for:

- `fg.eval.run`;
- direct `check`;
- direct `diagnose`;
- direct `why_not`;
- `what_if.*` shells.

Those are tied to D20 explanation behavior, D22 why-not disposition, and D23 hard-cut plan.

D18 only says: return-shape flip must not create a new compatibility burden that makes D23 harder. New docs should not promote old shells as the way to consume `EvaluateResult`.

### 4.7 Return-shape implementation requires DTO foundation first

No return-shape implementation blueprint may start before the D17 DTO foundation is implemented or included in the same reviewed blueprint.

Minimum implementation ordering:

1. define and export D17 DTOs;
2. build internal conversion from shipped runtime candidate artifacts to `EvaluateResult`;
3. change public `evaluate(...)` return shape;
4. update tests and docs for the new return type;
5. execute D23 hard-cut removals either in the same slice or immediately after, per Stage 3.

D19 digest formulas may be implemented in the same slice only if D19 is reviewed clean first.

### 4.8 Pre-implementation blast-radius inventory is mandatory

Before any return-shape feat commit:

- grep tests and docs for `list[CandidateSet]`, `CandidateSet`, `fg.eval.evaluate`, `sdk.evaluate`, `accept`, `accept_many`, `engine_options`, `registry=`, and `evaluate_derivation_plans`;
- grep `src/service/` for evaluate / check / diagnose / why_not caller assumptions per D16 §4.4;
- classify hits as public hard-cut update, internal runtime preservation, future D23 hard-cut, or unrelated;
- record baseline test count before changes.

This inventory may happen in a blueprint Step 4.6 grep, but it must be explicit before implementation.

## 5. Rejected Alternatives

### Option A: Add `evaluate_v2(...) -> EvaluateResult`

- **Why rejected**: Creates an indefinite parallel API and punts the hard-cut. Parent explicitly describes alpha direct break for this API family.

### Option B: Add `result_shape=` or `return_candidates=` option

- **Why rejected**: Keeps two public result models alive under one method, complicates typing and docs, and violates D17's final public target.

### Option C: Flip only RuleExpr / application head Rule path first

- **Why rejected**: Public `fg.eval.evaluate(...)` would return different shapes based on input type. That breaks a simple mental model and forces docs to preserve old `CandidateSet` semantics.

### Option D: Keep legacy `Inference` path returning `list[CandidateSet]`

- **Why rejected**: Legacy `Inference` is one of the highest-usage evaluate paths. Leaving it behind would make `EvaluateResult` feel like a niche RuleExpr feature rather than the T5 public result model.

### Option E: Keep `engine_options=` / `registry=` through the new result surface

- **Why rejected**: Parent C62 explicitly deletes them from SDK public evaluate. Launching `EvaluateResult` with deprecated parameters creates immediate debt.

### Option F: Remove `accept*`, `check`, `diagnose`, `why_not`, and `what_if.*` in D18 itself

- **Why rejected**: D18 is the return-shape transition decision. Explanation and why-not need D20/D22 before their legacy shells can be deleted coherently; D23 owns hard-cut mechanics.

### Option G: Expose a public CandidateSet conversion helper for compatibility

- **Why rejected**: It would turn `CandidateSet` into a supported public compatibility contract. Internal helpers are sufficient for implementation and test migration.

### Option H: Delay return-shape flip until all C73-C78 semantics work is complete

- **Why rejected**: D16 separates T5 Core and T5 Semantics. Semantics digest consistency must be decided, but full semantics implementation is not a prerequisite for public result shape.

## 6. Supporting Evidence

- Parent C62 requires `fg.eval.evaluate(...)->EvaluateResult` and deletes `engine_options=`, `registry=`, `accept`, and `accept_many`.
- D17 locks `EvaluateResult` as the final public result target and `CandidateSet` as internal artifact.
- Shipped `SDKStore.evaluate` currently returns `list[CandidateSet]` for all evaluate paths.
- Shipped `_SDKEvalManager` still exposes `accept` and `accept_many`.
- Docs and tests contain broad `list[CandidateSet]`, `CandidateSet`, `engine_options`, and `accept_many` assumptions.
- Track plan calls out SDK store, SDK shells, application protocol/runtime, service routes, docs, and tests as affected surfaces.
- D16 requires service-route blast-radius inventory before hard-cut implementation.

## 7. Consequences

### 7.1 Downstream unblocking

D18 unblocks:

- D19 digest decisions with a clear final public result target.
- D20 explanation design against `EvaluateResult` / `EvaluateRow` rather than `CandidateSet`.
- D23 hard-cut planning with `engine_options=`, `registry=`, and `accept*` target state already locked.
- Stage 3 implementation slice planning.

### 7.2 Implementation constraints

Future T5 implementation must:

- update all public `evaluate(...)` success-shape tests together;
- preserve internal runtime `CandidateSet` tests where they test runtime internals;
- reject public `engine_options=` and `registry=` at SDK evaluate boundary;
- avoid adding compatibility public methods that return candidates;
- update docs in the same tranche as the public return-shape flip;
- run service-route grep before any hard-cut implementation.

### 7.3 Stage 3 gating

Stage 3 synthesis must decide whether return-shape flip and `accept*` removal are one slice or two immediately adjacent local slices.

Stage 3 must not schedule a return-shape feat before D19 digest source-of-truth is reviewed if the feat intends to populate final digest fields. It may schedule a DTO scaffold before D19 only if digest fields use explicit temporary placeholders rejected from public use until D19 lands; this is discouraged.

## 8. Acceptance Criteria

- [ ] D19 cites D18 for final public `EvaluateResult` target.
- [ ] D20 does not design explanation around public `CandidateSet`.
- [ ] D23 includes public evaluate `engine_options=` / `registry=` removal in hard-cut plan.
- [ ] Stage 3 classifies docs/tests/service-route hits before return-shape implementation.
- [ ] No public `evaluate_v2`, `result_shape=`, or `return_candidates=` transition is introduced.
- [ ] RuleExpr, application head Rule, legacy SDK `Inference`, and structured derivation dict public evaluate paths converge on `EvaluateResult`.
- [ ] Internal runtime tests may still use `CandidateSet` where they are not SDK public result tests.
- [ ] Public docs stop presenting `list[CandidateSet]` as evaluate success shape after T5 return-shape implementation.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T5 Stage 1 audit Q3 mapped to D18. D18 locks hard-cut `fg.eval.evaluate(...)->EvaluateResult`, applies the flip to all public evaluate entry paths, classifies CandidateSet compatibility as internal-only, removes public evaluate `engine_options=` and `registry=` with the return-shape flip, couples `accept*` removal to D23 hard-cut planning, and requires docs/tests/service-route blast-radius inventory before implementation. |
