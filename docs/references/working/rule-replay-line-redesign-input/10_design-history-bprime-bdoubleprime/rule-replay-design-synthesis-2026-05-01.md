# Reference Note: Rule Replay Design Synthesis

- Status: working
- Type: internal working reference
- Authority: non-authoritative synthesis for future blueprint work; this document is not current implementation truth and is not an API contract.
- Source / Provenance:
  - `docs/references/working/rule-replay/evidence-tree-context-bprime-2026-04-30.md`: predecessor B' design centered on operational evidence-tree handles and EvaluationOverlay.
  - `docs/references/working/rule-replay/evidence-tree-proof-recheck-ideas-2026-04-30.md`: extended proof-frame / secondary-checker / overlay notes from earlier exploration.
  - `docs/references/working/rule-replay/operational-evidence-tree-rule-replay-design-2026-05-01.md`: B'' working note that pivots to rule-as-operable-object and evidence replay.
  - `/Users/zhenzhili/.gstack/projects/hnsm-backend/zhenzhili-oss-prep-v0.1-design-20260501-195238-rule-replay-preview.md`: office-hours preview design with useful framing but several implementation-path errors.
  - Local source review on `evidence-tree-operational-overlay` as of May 1, 2026.
- Usage:
  - Blueprint authors may cite this as the consolidated design input for a future evidence-tree / rule-replay task.
  - Blueprint authors should treat the source notes as historical working drafts and prefer this synthesis unless intentionally revisiting a rejected path.
  - This document must not be used as proof that rule replay, rule patches, lazy why-not carriers, or parameter handles exist in the current implementation.
- Related Docs:
  - `docs/architecture_principles.md`
  - `docs/blueprints/active/`
  - `src/kernel/application/docs/`
  - `src/kernel/sdk/docs/`
  - `src/kernel/audit/docs/`

## Summary

The stable design direction is:

```text
Rule / derivation authoring object
  -> explicit rule or derivation patch
  -> recompile / validate into an executable variant
  -> evaluate or check through the existing runtime authority
  -> produce fresh candidate results and evidence views
  -> compare runs, candidates, and evidence views
```

Evidence trees remain run-derived views. They are valuable because they expose support structure, status, bindings, and evidence alignment points. They are not mutable proof objects and should not directly generate rule changes.

The main correction to the office-hours preview is that it made several implementation-path assumptions that do not match the current codebase. In particular, the current `CompiledDerivationPlan` is not a rule registry object, application runtime does not directly write audit JSONL files, and patching a condition cannot bypass compile/validate just because the patch does not introduce a new variable.

## Current Ground Truth

These facts are current-context inputs for future blueprint work.

- Active feature branch: `evidence-tree-operational-overlay`.
- Internal baseline has already been merged back into local `master`; the evidence-tree work should not be based on `oss-prep-v0.1`.
- Kernel unit baseline was confirmed by the user on the current branch with:

```text
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
Ran 709 tests in 5.620s
OK (skipped=1)
```

- `kernel.application` is the canonical Python runtime authority.
- `kernel.sdk` is the product-facing wrapper layer.
- `kernel.audit` consumes audit packages. It does not own live runtime writes.
- Current SDK evaluation lowers `Derivation` into `CompiledDerivationPlan` and delegates to `evaluate_derivation_plans(...)`.
- `CompiledDerivationPlan` carries `derivation_id`, `version`, `body_ir`, `heads`, optional `body_confidence`, optional `head_spec`, optional `engine_ext`, and engine options. It does not carry a mutable `Rule` object or rule registry state.
- Existing condition addressing already uses atom-position keys such as `b{branch}.a{atom}` for `condition_weights` and evidence/support positioning.
- Current examples do not include `examples/03_dora_minimal_evidence_tree.ipynb`. Current candidates include `examples/10_v01_onboarding_journey.ipynb` or a new notebook.

## Stable Design Principles

### 1. Rule Is The Operable Object

The user changes rules, derivations, or rule references by creating an explicit patch or variant. The authoritative result comes only after the variant is compiled, validated, and evaluated.

This does not mean every implementation object is literally a `Rule` dataclass. Current code distinguishes:

- top-level `Derivation.where` / compiled derivation body;
- registry rules referenced through `RuleRef`;
- lower-level `CompiledDerivationPlan.body_ir`;
- native rule registry objects used by RuleRef execution.

Future blueprint work must define the patch target explicitly. "Patch the rule" is a product phrase, not a sufficient implementation target.

At minimum, the design needs a target taxonomy:

```text
PatchTarget.derivation_body
  Patch the top-level derivation body used for candidate generation.

PatchTarget.referenced_rule
  Patch a named registry rule referenced by RuleRef.

PatchTarget.rule_variant
  Create a temporary authoring-level rule/derivation variant and recompile it.
```

The most conservative implementation direction is to create a temporary authoring-level variant, then re-run existing compile/validate/evaluate paths. Direct mutation of `CompiledDerivationPlan.body_ir` should not be a patch target.

For this design line, compiled plans are evaluation inputs produced after authoring compile/validation. They are not the operable patch target. A future implementation may optimize how a validated variant becomes a compiled plan, but it should not define user-facing patch semantics as in-place mutation of `CompiledDerivationPlan`.

### 2. Evidence Is A Run-Derived Analysis Surface

Evidence trees should be read-only views over an evaluation or check result.

"Read-only" should be structural, not only presentational. Future public APIs should expose evidence as immutable snapshots or value-like DTOs with no setter/update method. Review notes, tags, redactions, or decisions should live in separate review/audit records rather than mutating an evidence tree in place.

Evidence-level operations are allowed, but they are analysis operations:

- align two evidence trees;
- compare before/after frame status;
- summarize which rule diff correlates with a proof-path change;
- group candidate changes by condition or branch;
- materialize an on-demand why-not report for a concrete binding.

Evidence boxes should not directly create `RulePatch` objects. The user may edit a rule or derivation elsewhere, then use evidence comparison to understand the effect.

This avoids the earlier B' contradiction: "evidence tree is immutable" and "evidence tree is the mutable object" cannot both be true.

### 3. Patch Means Recompile / Validate Before Evaluate

Replacing, disabling, or parameterizing a condition can break binding, type, arity, RuleRef dependency, or head/select guarantees. This is true even when the patch does not introduce new variables.

Therefore the safe semantic rule is:

```text
Patch -> compile/lower -> validate -> evaluate
```

Compiled-plan rewrite should not define patch semantics. The implementation should not rely on "no new variables" as a proof of safety.

### 4. Two Diff Layers Must Stay Separate

Rule diff answers:

```text
What changed in the rule or derivation structure?
```

Examples:

- a condition was replaced;
- a condition was disabled;
- a parameter value changed;
- a branch received a new condition.

Evidence diff answers:

```text
What changed in observed results or proof/check paths after evaluation?
```

Examples:

- a candidate disappeared;
- a candidate remained but support changed;
- a condition frame changed from true to false;
- a rule no longer fired.

Run-level candidate diff and path-level evidence diff are also distinct:

- Run diff compares candidate sets between evaluation runs.
- Evidence diff compares support paths or check reports for a selected candidate/binding.

### 5. Audit Events Are Runtime Carriers, Not Direct JSONL Writes

The office-hours preview incorrectly implied that `kernel.application.rule_patch_runtime` would directly emit `audit/rule_patch_events.jsonl`.

The corrected boundary is:

```text
application runtime
  -> produce structured rule-replay event / carrier

store or export/package layer
  -> persist or materialize the event into an audit package, if needed

kernel.audit
  -> read and query the already-exported package
```

If future work adds `rule_patch_events.jsonl`, the blueprint must define where events live before export, how they join to `run_id` / candidate evidence, and how the package manifest exposes them.

A metadata-only event with `patch_id`, actor, reason, timestamp, target, and actions is not enough for replay analysis unless it can be joined to an evaluation run or check invocation.

Current package materialization is not engine-neutral enough to assume rule replay events can simply be appended to one existing writer. If replay events are persisted/exported for native, ProbLog, PyReason, and Souffle paths, the prerequisite is an engine-neutral export owner or event materialization surface. Otherwise v0.1.1 should keep replay events out of durable audit package scope.

### 6. Candidate Universe Is The Boundary For Red/Green Review

The desired red/green review UI is feasible only when the system has a finite, explicit set of targets to check.

The lazy model is:

```text
candidate universe
  - green candidates from evaluate
  = red lazy carriers
```

Red items should not eagerly store failed evidence trees. They should store replay/check carriers:

```text
rule or derivation identity
variant identity, if any
binding / target
source run id, if any
mode = check
```

When the user opens a red item, the system runs a concrete check/replay for that binding and materializes a failed check report.

Hard boundary:

```text
No explicit finite candidate universe -> no full red/green board.
Manual check for a user-specified binding may still be available.
```

## Concepts To Preserve From Earlier Drafts

### Parameter Handle

`docs/references/working/rule-replay/evidence-tree-context-bprime-2026-04-30.md` contains an important product concept that the office-hours preview weakened: Parameter Handle.

The idea is that common expert edits such as:

```text
temperature > 20
temperature > 30
```

should not require users to rewrite condition AST. Instead, the rule declares a discoverable parameter, and UI/notebook controls can expose it as a first-class threshold or knob.

This has market and UX value:

- it maps naturally to sliders, numeric inputs, and scenario controls;
- it separates "change threshold value" from "rewrite logical condition";
- it is a clearer review operation for business or domain experts;
- it preserves a path toward safe parameter-only variants.

Current implementation does not have a parameter system in `Rule`, authoring payloads, or compiler support. Future blueprint work should not present `param_override` as a trivial optional action. It is a substantial design area.

Recommended positioning:

```text
Parameter Handle is a v0.1.x/v0.2 candidate feature.
v0.1.1 may reserve naming/shape, but should not imply full support unless the compiler and SDK actually implement it.
```

### Fact What-If Versus Commit

`docs/references/working/rule-replay/evidence-tree-context-bprime-2026-04-30.md` correctly distinguished non-committing fact what-if from ledger commit:

```text
fact what-if
  -> evaluate under a temporary scenario
  -> no ledger mutation

fact commit
  -> retract + set/add
  -> append-only ledger write
```

The rule-replay direction shifted focus to rule-level what-if, but expert review naturally needs fact-level what-if as well. Otherwise the UX becomes asymmetric:

```text
rule edits can be tested without commit
fact edits require commit
```

If v0.1.1 does not include fact what-if, the blueprint should say so explicitly:

```text
v0.1.1 what-if is rule/derivation variant only.
fact-level non-committing override is deferred.
fact commit continues through existing retract + set/add paths.
```

### Shared Condition Identity

The B'' note correctly distinguished local condition identity from shared condition identity:

```text
condition_id
  local locator within a rule/derivation/module graph

shared_id or library reference
  explicit cross-rule identity for a reusable conceptual condition
```

Future work should not make generated `condition_id` carry cross-rule semantics by accident. Cross-rule synchronized edits require explicit shared identity.

For v0.1.1, any locator strategy should preserve forward compatibility with later `shared_id` / library condition references.

### Rich Status Vocabulary

A future red/green review board should not collapse every non-green state into `false`.

Potential statuses include:

- derived;
- not derived;
- failed check;
- below probability threshold;
- temporally unsatisfied;
- unknown;
- unsupported;
- not materialized yet.

Native v0.1.1 work may use a simpler binary or ternary status, but schema choices should not preclude richer statuses for ProbLog, PyReason, or lazy why-not carriers.

### Local Proof-Path Recheck

`docs/references/working/rule-replay/evidence-tree-proof-recheck-ideas-2026-04-30.md` captured a useful diagnostic boundary even though the broader "secondary checker" framing should not become the central design.

Local proof-path recheck can answer:

```text
Does this old proof path still hold under a proposed change?
Where did the old proof path first fail?
```

It must not answer:

```text
What is the new truth?
Which new candidates now exist?
What replacement proof should be authoritative?
```

The authoritative result still comes from full evaluation or concrete check/replay. Local proof-path recheck is a future explanation aid for old evidence, not a substitute inference engine.

### CandidateReview Vocabulary

`CandidateReview` from B' remains a useful naming candidate even though the B' handle-based operation model was superseded.

Possible future meaning:

```text
CandidateReview
  a review session or view over one candidate/binding across one or more runs,
  with evidence comparison, rule diff references, notes, and final decision state.
```

This should be revisited during SDK/API naming, not treated as a current implementation concept.

### Market Positioning

The durable positioning is:

```text
Decision Assurance / 可审计决策推理工作台
```

This is not merely:

- another explainability dashboard;
- another business rules engine;
- an audit log viewer.

Relevant comparison categories from earlier notes:

- IBM ODM;
- FICO Blaze Advisor;
- Pega;
- Fiddler;
- Arize;
- Rainbird;
- Credo AI.

These comparisons should be used as launch and product framing, not as unverified implementation premises. Claims such as "no public OSS today combines X" should be softened or sourced before they appear in release notes.

Candidate verticals from earlier notes include credit decisioning, AML, fraud review, insurance claims, medical prior authorization, government benefits, vendor risk, and AI policy review. Treat these as design inputs and demo-search prompts, not as market claims unless separately validated.

## Corrected Preview Scope

A conservative first blueprint should avoid locking concrete API names too early. It should first run a feasibility spike around patch target and compile path.

Candidate preview scope:

- make rule/derivation patch target explicit;
- support a small set of patch operations only after compile/validate strategy is proven;
- evaluate patched variants through existing runtime authority;
- provide static rule/derivation diff;
- provide run-level candidate diff;
- keep evidence tree read-only;
- optionally align existing evidence by current atom-position keys;
- defer lazy why-not until candidate universe and check semantics are designed;
- defer red/green review-board product claims until lazy why-not and candidate universe exist;
- defer full Parameter Handle UX unless compiler support is included;
- defer fact-level non-committing what-if unless an explicit scenario mechanism is included.

The preview should not require:

- global failed-attempt trace;
- mutable evidence tree;
- direct application writes to audit JSONL;
- engine-specific replay event persistence that would silently drop non-Souffle/native adapter history;
- new top-level condition/branch fields without resolving existing `b{branch}.a{atom}` locators;
- bypassing compiler validation by rewriting plan internals;
- red/green review UI as a v0.1.1 product promise.

## Anti-Patterns To Avoid

### Anti-Pattern: Treating Evidence As The Mutable Object

Bad:

```text
tree_node.replace_condition(...)
```

This suggests evidence owns truth semantics. It should not.

Better:

```text
edit rule/derivation variant
evaluate
compare evidence from old and new runs
```

### Anti-Pattern: Rewriting `CompiledDerivationPlan` As If It Were A Rule

Current `CompiledDerivationPlan` is an application protocol DTO for evaluation. It is not a rule registry entry and does not by itself encode all authoring semantics.

Compiled plans should be treated as the output of compile/validation, not as patch inputs. The safe default is:

```text
authoring-level patch -> compile/validate -> evaluate
```

### Anti-Pattern: "No New Variables" Means Safe

Even patches that do not introduce new variables can break binding or validation. Every patched variant must pass equivalent compile/validate checks before evaluation.

### Anti-Pattern: Application Runtime Writes Audit Package Files

Application runtime may produce structured events. Package export or delivery layers should decide how those events become durable audit files. `kernel.audit` reads packages; it should not become the live write owner.

### Anti-Pattern: New `condition_id` Without Locator Migration

The current system already uses `b{branch}.a{atom}` locators. Adding `condition_id` / `branch_id` without a compatibility story creates two parallel addressing schemes.

Future work should decide whether to:

- reuse atom-position locators for the preview;
- add aliases only at SDK/UI level;
- introduce stable ids with a migration story;
- later add `shared_id` for cross-rule library conditions.

### Anti-Pattern: Red Means False Without Candidate Universe

A missing candidate is only interpretable relative to a target set. Without an explicit candidate universe, the system cannot show a complete red/green board.

## Blueprint Step 0

Before any implementation blueprint becomes `scoped`, it should answer these questions with source-backed evidence:

1. What is the first patch target?
   - derivation body;
   - referenced registry rule;
   - temporary authoring-level rule/derivation variant;
   - some combination, explicitly ordered by phase.
   - Source pointers: `src/kernel/authoring/rule_compile.py`, `src/kernel/authoring/derivation_compile.py`, `src/kernel/application/protocol/derivation.py`, and `src/kernel/sdk/dsl/rule.py`.

2. How does the implementation patch authoring objects and recompile?
   - Default recommendation: authoring-level variant + existing compile/validate.
   - Compiled DTOs may be regenerated after validation, but should not be the patch input.
   - Source pointers: `src/kernel/sdk/store.py` `_compile_derivation_input(...)` and `_compiled_derivation_plan_to_application(...)`, plus the authoring compile modules above.

3. What locator is used for condition-level operations?
   - existing `b{branch}.a{atom}` keys;
   - generated condition ids;
   - user-specified ids;
   - SDK aliases over existing keys;
   - future `shared_id` compatibility.
   - Existing code uses two related atom-position forms: prefix locators such as `b{branch}.a{atom}` for `condition_weights`, and suffixed support/evidence keys such as `b{branch}.a{atom}:{kind_or_pred_id}`. `src/kernel/core/annotation/_certainty.py` normalizes suffixed keys back to the prefix in `_extract_condition_key(...)`.

4. Where do replay events live before audit package export?
   - in store runtime memory;
   - in candidate/run metadata;
   - in an explicit event log;
   - not stored in v0.1.1.
   - Current gap: there is no established rule-replay carrier or engine-neutral replay-event export owner. A blueprint should either design one explicitly or keep replay events out of v0.1.1 persistence.

5. Which existing example should carry the demo?
   - current examples list does not include `examples/03_dora_minimal_evidence_tree.ipynb`;
   - `examples/10_v01_onboarding_journey.ipynb` is the likely starting point unless a new notebook is created.

6. What exact test command is the acceptance baseline?
   - current confirmed kernel unittest baseline is 709 OK / 1 skip.

7. Which pieces are truly v0.1.1 and which are design-reserved?
   - Parameter Handle;
   - fact-level non-committing what-if;
   - lazy why-not carrier;
   - candidate universe;
   - rich status vocabulary;
   - shared condition identity.

## Suggested Blueprint Framing

Working title:

```text
Rule Replay With Evidence Diff
```

or:

```text
Rule Variant + Evidence Replay
```

The title should not imply mutable evidence trees.

Recommended implementation claim:

```text
The feature lets users create temporary rule/derivation variants, re-evaluate them through the normal runtime, and compare candidate/evidence outcomes.
```

Do not claim, unless implemented:

- full operational evidence tree handles;
- full Parameter Handle UX;
- fact-level what-if;
- lazy red/green why-not board;
- red/green review UI or "all failed cases" coverage;
- multi-engine proof-frame parity;
- persistent rule variant promotion;
- direct audit package replay.

## Relationship To Source Drafts

### `docs/references/working/rule-replay/evidence-tree-context-bprime-2026-04-30.md`

Keep for:

- Parameter Handle product language;
- fact what-if versus commit distinction;
- market positioning and comparables;
- possible `CandidateReview` naming.

Superseded for:

- evidence-tree handles as operation sources;
- `EvaluationOverlay` as the central mental model;
- tree node mutation language.

### `docs/references/working/rule-replay/evidence-tree-proof-recheck-ideas-2026-04-30.md`

Keep for:

- proof-frame / checker exploration;
- failure-mode catalog;
- engine-family differences;
- overlay vocabulary history.

Superseded for:

- secondary checker as the central design;
- any implication that local proof invalidation can replace full re-evaluation.

### `docs/references/working/rule-replay/operational-evidence-tree-rule-replay-design-2026-05-01.md`

Keep for:

- rule-as-operable-object thesis;
- evidence as run-derived view;
- candidate universe boundary;
- lazy why-not carrier;
- rich status vocabulary;
- shared condition identity.

Needs blueprint refinement for:

- current codebase patch target;
- compile/validate path;
- SDK/API shape;
- audit export ownership.

### Office-Hours Preview Doc

Keep for:

- product narrative;
- two-diff-layer framing;
- scope discipline;
- risk list;
- Parameter Handle and market-positioning reminders.

Correct before reuse:

- branch base should not be `oss-prep-v0.1`;
- patching `CompiledDerivationPlan` is not proven safe;
- application runtime should not directly write audit JSONL;
- `RulePatchedDerivationEvaluateRequest` shape does not match current multi-plan request contract;
- example path `examples/03_dora_minimal_evidence_tree.ipynb` is stale;
- `condition_id` / `branch_id` additions must account for existing `b{branch}.a{atom}` locators;
- `parameters` are not a trivial optional field in the current compiler.

## Final Recommendation

Use this synthesis as the input to a new active blueprint. Do not use the office-hours preview doc directly as a blueprint seed.

The next blueprint should begin with a short feasibility phase, not with the file list from the office-hours preview. The first implementation decision is not API naming; it is the patch target and compile/validate path.
