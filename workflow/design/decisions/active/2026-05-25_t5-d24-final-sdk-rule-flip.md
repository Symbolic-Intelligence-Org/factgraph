# D24 Decision: T5 Final SDK Rule Flip

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks T5 final SDK `Rule` naming, transition alias survival policy, and T1.3 public namespace closure.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` F8 and Q11.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.5 and 4.7.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` section 4.9.
  - D18 `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md` sections 4.1-4.3.
  - D23 `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md` sections 4.1, 4.3, 4.7, and 4.8.
  - Shipped `src/factgraph/sdk/__init__.py:28-56`, `src/factgraph/sdk/__init__.py:88-108`, and `src/factgraph/sdk/dsl/rule.py:53-170`.
  - Shipped application protocol `src/factgraph/application/protocol/rule.py:52-113`.
  - Shipped docs `src/factgraph/sdk/docs/04_api_surface.en.md:86-104`.
- Outputs / Downstream:
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and final public naming implementation blueprint(s).
  - D23 final docs migration and hard-cut implementation slices.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16-D23 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

- T5 Stage 1 audit F8 / Q11: SDK currently exposes a four-way naming surface: `Rule`, `LegacyRule`, `ApplicationRule`, and `Inference`.
- D16 section 4.5: T1.3 final SDK `Rule` flip belongs inside T5 Core and must be decided before final public docs migration.
- D17 section 4.9: D17-D23 use generic head Rule terminology until D24 chooses final SDK public names.
- D18: return-shape hard-cut makes `EvaluateResult` the public evaluation return object and makes `CandidateSet` internal.
- D23 section 4.8: final docs rewrite waits for D24 naming, while legacy hard-cut inventory can proceed earlier.
- Shipped SDK namespace: `src/factgraph/sdk/__init__.py:28-56`, `src/factgraph/sdk/__init__.py:88-108`.
- Shipped legacy DSL query class: `src/factgraph/sdk/dsl/rule.py:53-118`.
- Shipped legacy derivation authoring class: `src/factgraph/sdk/dsl/rule.py:119-170`.
- Application protocol `Rule`: `src/factgraph/application/protocol/rule.py:52-113`.
- Current API docs naming table: `src/factgraph/sdk/docs/04_api_surface.en.md:86-104`.

D24 is the naming decision that releases D17-D23 from generic terminology. It does not implement the rename and does not decide the D23 hard-cut mechanics.

## 2. Scope

D24 decides:

- what `from factgraph.sdk import Rule` means after T5;
- whether `ApplicationRule` survives and for how long;
- whether `LegacyRule` survives in the SDK top-level namespace;
- how `Inference` is named after T5;
- which import paths are canonical for public docs;
- how implementation slices should avoid type-check ambiguity during the flip;
- how docs and examples consume the final naming decision.

## 3. Non-Scope

D24 does not decide:

- `EvaluateResult` / `EvaluateRow` fields; D17 owns them;
- the hard-cut return-shape transition; D18 owns it;
- digest source formulas; D19 owns them;
- `Explanation` fields or EvidenceGraph integration; D20 owns them;
- `row.close()` construction; D21 owns it;
- why-not disposition; D22 owns it;
- exact D23 deletion / service-route migration mechanics;
- semantics commitments C73-C78; D26 owns them;
- changes to `factgraph.application.protocol.Rule` validation, digesting, projection sugar, or closed-head inspect semantics;
- parent section 6 task split (`match` / `evaluate` / `prove`) or parent section 9 RuleExpr x evidence joins.

## 4. Decision

### 4.1 SDK top-level `Rule` becomes the application protocol Rule

After the T5 final flip:

```python
from factgraph.sdk import Rule
```

must refer to the application protocol `Rule`, the same semantic type as `factgraph.application.protocol.Rule`.

This is the final T1.3 flip. User-facing T5 docs should use `Rule` for head Rules, projection Rules, closed heads, and RuleExpr head construction. They should not require users to import `ApplicationRule` for normal T5 authoring.

The application protocol import path remains stable:

```python
from factgraph.application.protocol import Rule
```

That path stays the authoritative lower-level protocol location. The SDK top-level `Rule` is a convenience export for the same class, not a wrapper class and not a renamed copy.

### 4.2 `ApplicationRule` survives only as a transition alias

`ApplicationRule` may remain in `factgraph.sdk` as a transition alias to the same application protocol `Rule` object during T5 implementation and one post-flip compatibility window.

Rules:

- `ApplicationRule is Rule` should be true in the SDK namespace after the flip if the alias remains.
- Docs and examples must prefer `Rule`.
- New T5 APIs must type and render this object as `Rule`, not `ApplicationRule`.
- Stage 3 may place `ApplicationRule` removal in the same implementation slice or in a later cleanup slice, but D24 rejects `ApplicationRule` as the permanent primary public name.

This preserves T1-T4 users who already imported `ApplicationRule` while avoiding a permanent two-name public story.

### 4.3 Top-level `LegacyRule` is a D23 hard-cut target, not a final public alias

`LegacyRule` currently aliases the legacy SDK DSL `Rule` class. D24 decides that top-level `factgraph.sdk.LegacyRule` is not part of the final T5 public SDK namespace.

D23 owns the exact hard-cut mechanics, but the target state is:

- no top-level SDK `LegacyRule` export in final public docs;
- no public `LegacyRule` recommendation as a compatibility route for old `fg.eval.run(...)` style usage;
- no `LegacyRule` accepted as a special public result-shape compatibility path;
- no `LegacyRule` based public evidence or explanation path.

If implementation needs the legacy DSL class internally while cutting old paths, it may remain in an internal or module-local location until D23 removes or quarantines it. D24 only rejects top-level public alias survival.

### 4.4 Legacy DSL `Rule` stops owning the SDK top-level name

The shipped legacy SDK DSL `Rule` is a query object documented around `fg.eval.run(rule)`. That meaning conflicts with T5's row-centric `fg.eval.evaluate(...) -> EvaluateResult` surface and with the T4 application `Rule` head model.

After D24:

- legacy DSL `Rule` must not be imported as top-level `factgraph.sdk.Rule`;
- legacy DSL query docs must be removed or rewritten by D23 docs migration;
- any remaining internal conversion helpers, such as `build_application_rule`, must describe their output as application `Rule`;
- implementation code must not branch on the public name `Rule` to detect legacy vs application behavior.

The class may exist temporarily under `factgraph.sdk.dsl` if Stage 3 needs a local migration bridge, but it is not a final SDK public surface.

### 4.5 `Inference` remains the derivation authoring class name

`Inference` remains a separate public authoring object for derivation input unless D23 later deletes the entire legacy derivation authoring path.

D24 does not rename `Inference` to `Rule`, `LegacyInference`, or `DerivationRule`.

Rationale:

- the current namespace already separates `Inference` from both legacy query `Rule` and application `Rule`;
- D18 requires the Inference evaluation path to return `EvaluateResult`, not to preserve old `CandidateSet` shape;
- D23 owns whether old `Inference` authoring survives as an accepted input form after hard-cut;
- renaming `Inference` in D24 would mix naming cleanup with hard-cut semantics.

If `Inference` survives, docs must position it as a derivation authoring input that evaluates into `EvaluateResult`, not as the preferred way to author head Rules.

### 4.6 Runtime checks use structural type identity, not public alias strings

Implementation slices must compare against the application protocol `Rule` type, not the string name chosen by SDK exports.

After the flip:

- `isinstance(obj, factgraph.application.protocol.Rule)` is the meaningful protocol check;
- `Rule` and `ApplicationRule` aliases, if both exist, must refer to the same class;
- error messages may say "Rule" after D24, but diagnostics should not mention current transitional alias names;
- internal legacy DSL detection must use the legacy class object or conversion protocol, not the public name `Rule`.

This prevents a temporary alias mix from causing ambiguous runtime behavior during Stage 3 implementation.

### 4.7 Public docs migration consumes D24 and D23 together

D24 unblocks concrete public naming in docs, but docs migration still must consume D23 hard-cut decisions.

Final public docs should:

- teach `from factgraph.sdk import Rule` for application head Rules;
- avoid `ApplicationRule` in primary examples;
- omit `LegacyRule` from the recommended API table;
- describe `Inference` only if D23 keeps it as an accepted authoring input;
- remove or rewrite old `fg.eval.run(...)`, `fg.eval.accept(...)`, and legacy CandidateSet flows per D23;
- avoid using T5 `Rule` naming to imply parent section 6 task split or parent section 9 RuleExpr x evidence joins.

Docs inventory may start before implementation, but user-facing final text must be written after D24 reviewed clean and after Stage 3 places D23/D24 implementation order.

### 4.8 Stage 3 implementation ordering

Stage 3 may implement D24 as:

- a standalone M-class naming flip slice; or
- part of a larger D23 hard-cut slice, if blast radius remains contained.

Regardless of slice shape, the public milestone must not expose:

- top-level SDK `Rule` as legacy DSL while T5 docs call it the application head Rule;
- top-level SDK `Rule` as application head Rule while docs still recommend `LegacyRule` for old query behavior;
- both `Rule` and `ApplicationRule` as equal primary names in new docs;
- D24-inconsistent OpenAPI or service docs.

If implementation finds widespread service or agent dependency on legacy SDK `Rule`, Stage 3 should classify the slice as L-class or split it, but intermediate mixed states remain local-only per D23.

## 5. Rejected Alternatives

### Option A: Keep SDK top-level `Rule` as the legacy DSL query class

Rejected. This would leave T1.3 unresolved, force T5 docs to keep using `ApplicationRule`, and preserve the exact naming ambiguity D16 pulled into T5 Core.

### Option B: Make `ApplicationRule` the permanent primary public name

Rejected. `ApplicationRule` was a transition name. Keeping it as primary would make the SDK surface verbose and would continue to imply two public Rule concepts after the legacy hard-cut.

### Option C: Keep `Rule` and `ApplicationRule` as equal permanent names

Rejected. Equal names create duplicate docs, duplicate error wording, and a permanent choice that users do not need. A short compatibility alias is acceptable; equal primary names are not.

### Option D: Keep top-level `LegacyRule` forever as the explicit old path

Rejected. D18 and D23 choose a hard-cut public API posture. Permanent `LegacyRule` would reintroduce a long-lived compatibility lane under a different name.

### Option E: Delete `ApplicationRule` immediately with no transition alias

Rejected as too sharp for T1-T4 users. D24 allows a temporary alias so existing application Rule users can migrate without blocking the public `Rule` flip.

### Option F: Rename `Inference` during D24

Rejected. `Inference` has separate semantics and D23 owns whether the legacy derivation authoring path survives. Renaming it here would expand D24 beyond the final `Rule` flip.

### Option G: Introduce a new `HeadRule` or `EvalRule` public class name

Rejected. A new name would avoid conflict only by adding another public concept. The purpose of T1.3 is to make `Rule` mean the application protocol Rule.

### Option H: Move the final naming choice to docs migration

Rejected. D23 requires docs migration to consume the D24 decision, not decide it. Delaying naming until docs would let implementation slices proceed with ambiguous imports.

## 6. Supporting Evidence

| Source | Evidence | D24 consequence |
|---|---|---|
| `src/factgraph/sdk/__init__.py:38-56`, `:88-92` | SDK currently exports `Rule`, `LegacyRule`, `ApplicationRule`, and `Inference`. | D24 must collapse or classify the four-way namespace. |
| `src/factgraph/sdk/dsl/rule.py:53-118` | Legacy DSL `Rule` is documented around `fg.eval.run(rule)`. | This meaning conflicts with D18 hard-cut and cannot keep top-level `Rule`. |
| `src/factgraph/sdk/dsl/rule.py:119-170` | `Inference` is a separate derivation authoring class. | D24 should not collapse `Inference` into `Rule`. |
| `src/factgraph/application/protocol/rule.py:52-113` | Application protocol `Rule` owns ports, where atoms, and content digest. | This is the class that should become SDK top-level `Rule`. |
| `src/factgraph/sdk/docs/04_api_surface.en.md:86-104` | Docs already describe current `Rule` as legacy-compatible and `ApplicationRule` as transitional. | D24 resolves the deferred replacement. |
| D16 section 4.5 | T1.3 final flip is a T5 Core blocker before docs migration. | D24 must be reviewed before final docs rewrite. |
| D23 section 4.8 | Docs migration waits for D24 naming. | D24 output feeds D23 docs hard-cut. |

## 7. Consequences

### 7.1 Positive consequences

- T5 gets one public SDK name for application head Rules: `Rule`.
- T1.3 final flip is no longer deferred.
- D23 docs migration can use concrete names instead of generic placeholders.
- T5 implementation can type-check application Rules structurally without alias ambiguity.
- `LegacyRule` cannot become a hidden long-lived compatibility surface.

### 7.2 Costs

- Existing users importing `Rule` for the legacy DSL query class must migrate.
- Docs, examples, tests, and service references that mention legacy `Rule` need inventory and rewrite.
- Stage 3 must coordinate D23 and D24 so final milestones do not expose mixed naming.
- `ApplicationRule` alias removal may need a staged cleanup after the initial flip.

### 7.3 Follow-up decisions

- D23 decides exact legacy deletion / service-route rewrite mechanics.
- Stage 3 synthesis decides whether D24 is standalone or bundled with D23.
- D24 does not decide whether `Inference` remains accepted long-term; D23 owns that hard-cut target.
- D26 semantics commitments do not change the D24 naming decision.

## 8. Acceptance Criteria

- [ ] SDK top-level `Rule` is decided as the application protocol Rule.
- [ ] `ApplicationRule` is classified as a transition alias, not the permanent primary name.
- [ ] Top-level `LegacyRule` is classified as a D23 hard-cut target, not a final public alias.
- [ ] Legacy DSL `Rule` no longer owns the SDK top-level `Rule` name in the T5 target surface.
- [ ] `Inference` naming is preserved unless D23 later cuts the authoring path.
- [ ] Runtime checks are specified in terms of application protocol `Rule` type identity, not public alias strings.
- [ ] D23 docs migration can consume concrete D24 names.
- [ ] D24 does not reopen D17-D23 decisions or T4 application Rule semantics.

## 9. Decision Record

| Date | Stage | Summary | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Flip SDK top-level `Rule` to the application protocol Rule. | Drafted after D23 reviewed clean v1. D24 resolves T1.3 by making `Rule` the application head Rule in the SDK, keeping `ApplicationRule` only as a transition alias, classifying top-level `LegacyRule` as a D23 hard-cut target, and preserving `Inference` naming pending D23 hard-cut mechanics. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 header normalization. | Rewrote the header to match D16-D23 ADR conventions, including authority, input/output lists, related documents, branch, dependency line, and ADR lifecycle wording. |
