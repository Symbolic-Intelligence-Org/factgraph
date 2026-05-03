# Reference Note: Operational Evidence Tree via Rule Replay

- Status: working
- Type: internal working reference
- Authority: non-authoritative design notes for future blueprint work; this document is not current implementation truth.
- Source / Provenance:
  - Design discussion on May 1, 2026 about operable evidence trees, rule variants, replay, lazy why-not traces, and candidate universes.
- Usage:
  - Blueprint authors may cite this as rationale when scoping the evidence-tree / rule-replay feature.
  - This document must not be used as an API contract, module contract, or proof that behavior exists in the current implementation.
- Related Docs:
  - `docs/architecture_principles.md`
  - `docs/blueprints/active/`
  - `src/kernel/sdk/docs/`
  - `src/kernel/application/docs/`
  - `src/kernel/audit/docs/`

## Summary

The design direction is to stop treating evidence trees as mutable proof objects. The object that can be operated on is the rule. Evidence trees are run-derived views that can be compared, aligned, and summarized, but they should not modify rules or generate rule changes implicitly.

The proposed product model is:

```text
Rule definition
  -> Rule patch / rule variant
  -> Rule diff
  -> Evaluation / check / replay
  -> Evidence tree or failed check report
  -> Evidence diff / explanation / summary
```

This preserves the user's intuition of a visual, interactive evidence tree while keeping the authoritative semantics in the rule and evaluation layers.

## Design Thesis

### Rule Is The Operable Object

Rule operations are the source of counterfactual change. A user can create a temporary scenario, save it as a rule variant, or eventually promote it to a new rule version. The default operation should be session-local what-if analysis.

Rule-level operations may include:

- replacing a condition;
- disabling a condition;
- overriding a parameter;
- adding a condition to a specific branch;
- comparing an original rule and a changed rule as a static rule diff.

The rule operation layer should exist before evidence comparison. Evidence comparison explains the effect of the rule change, not the cause of the change.

### Evidence Is A Run-Derived View

An evidence tree is not a mutable logic circuit and should not be treated as a place where old inference can be locally reactivated.

Evidence is a materialized view of a specific evaluation or check:

```text
rule module + concrete binding + observed values + status + support metadata
```

Evidence tree nodes can be interactive in UI, but their operations should be evidence operations:

- align this node with the corresponding node in another tree;
- compare before/after status;
- summarize which rule diff caused this evidence-state change;
- expand or collapse proof detail;
- materialize a lazy why-not report for a selected binding.

Evidence boxes should not directly create rule patches. The user may separately edit the rule, then use evidence diff to understand the effect.

### Two Diff Layers

The design needs two different diff concepts.

Rule diff answers:

```text
What changed in the rule structure?
```

Examples:

- `temperature > 20` became `temperature > 30`;
- condition `comfort.temperature_threshold` was disabled;
- a condition was appended to branch `b1`;
- parameter `threshold` was overridden for this scenario.

Evidence diff answers:

```text
What changed in the observed inference result or proof path after evaluation?
```

Examples:

- candidate `comfort_ok(room_a)` changed from derived to not derived;
- the same candidate is still derived, but through a different support path;
- a condition frame changed from true to false for binding `room=room_a`;
- a rule no longer fired because one branch failed.

Run-level candidate diff and path-level evidence diff should remain separate:

- Run diff compares candidate sets across evaluation runs.
- Evidence diff compares proof/check paths for a specific candidate or binding.

## Rule Module Model

### Minimal Condition Modules

The rule layer should compile user-facing syntax into a lower-level module form. The useful minimum unit is a condition module: a small, typed object with an id, kind, expression, parameters, and source metadata.

Examples of module kinds:

- comparison condition;
- predicate condition;
- rule reference condition;
- branch;
- parameter;
- opaque condition for unsupported custom logic.

The user syntax can be simple, but the compiled layer should preserve enough structure for diff, replay, and UI alignment.

### Condition Ids And Shared Identity

Every condition should have a uniform wrapper and an id. The id can be generated or user-supplied.

There should be two identity levels:

- `condition_id`: identifies a condition within a rule version or rule module graph.
- `shared_id` or library reference: explicitly declares that multiple rules share the same conceptual condition.

Default rule changes should affect only the current rule module. Cross-rule changes should require an explicit shared identity or library condition reference. This avoids surprising global edits.

Generated ids may be UUIDs, source-span-based ids, or compiler-generated stable ids. They are acceptable for local review. User-specified ids are better for durable UI handles, audit review, and stable diffs across larger edits.

### Branches Instead Of Exposed `and`

The user-facing rule syntax may treat a branch as a sequence of conditions joined by AND, with OR represented as multiple branches.

The lower-level form should still represent branches explicitly:

```text
RuleIR
  Branch b1
    Condition c1
    Condition c2
  Branch b2
    Condition c3
    Condition c4
```

This keeps add/replace/disable operations precise:

```text
append condition to branch b1
replace condition c2
disable condition c3
```

### Adding Conditions And New Variables

Adding a condition to a branch should be allowed in principle, including conditions that introduce new variables, but this should be solved by recompilation rather than by local patch wiring.

The rule variant should be recompiled after a patch. The compiler or planner is responsible for producing a binding plan. If the new variable cannot be bound from the rule head, branch sources, prior conditions, or declared enumerators, compilation should fail with a clear unbound-variable error.

This avoids a fragile patch-time rule like "new conditions may only reference existing variables" while still keeping semantics explicit.

The core boundary:

```text
RulePatch may add new variables.
Rule compilation must prove how each variable is bound.
Evaluation must not guess missing bindings at runtime.
```

## Evaluation, Check, And Replay

### Evaluate

Evaluate asks:

```text
Which candidates can this rule derive?
```

It produces candidate sets and success evidence for derived candidates. Traditional evidence trees should remain success-oriented unless a specific check or why-not path is requested.

### Check

Check asks:

```text
Does this specific binding satisfy this rule?
```

This is the practical meaning of the earlier "temporary head-parameter replacement" intuition. Instead of enumerating all candidates, the system fixes the head/select variables to concrete values and runs a boolean-style diagnostic.

Check can support:

- success evidence for a binding that satisfies the rule;
- failed check reports for a binding that does not satisfy the rule;
- why-not explanations for a concrete target.

Check is the safer MVP path for red/green review because it avoids recording a full engine execution trace for every possible failed attempt.

### Replay

Replay is a review-time operation that reruns a rule or rule variant for a specific carrier:

```text
rule id + rule version + optional variant + binding + engine/mode metadata
```

Replay should be treated as fresh evaluation/check work, not as partial recomputation of a previous evidence tree.

## Lazy Why-Not Trace

### Problem

Users may want a review screen that shows green items for derived candidates and red items for cases that did not derive. Recording full failed traces for every possible case is likely too expensive and may exceed what the inference engines naturally expose.

### Proposed Shape

Use lazy failed carriers instead of eagerly materialized failed evidence trees.

The system first defines a candidate universe. It then runs normal evaluation:

```text
green = candidates produced by evaluate
red carriers = candidate universe - green
```

Each red item stores only a replay carrier:

```text
rule id
rule version
variant id, if any
head binding
source run id
mode = boolean check
```

When the user opens a red item, the system runs check/replay for that concrete binding and materializes a failed check report or why-not tree.

This moves cost from storage and eager tracing to on-demand explanation.

### Candidate Universe Boundary

Lazy red traces are only meaningful when the candidate universe is explicit, finite, and aligned with the rule head/select identity.

Possible universe sources:

- an explicit list of bindings supplied by the user;
- all entities of a declared type;
- a query-defined set;
- a bounded cartesian product with a maximum size;
- a paginated source controlled by the application.

If no universe is provided, the system should not claim to know all red cases. It may still support manual check for a user-specified binding.

This boundary is central:

```text
No explicit candidate universe -> no full red/green board.
Manual check remains available.
```

### Status Vocabulary

Red should not mean only `false`. Different engines and domains may require richer statuses:

- not derived;
- failed check;
- below probability threshold;
- temporally unsatisfied;
- unknown;
- unsupported;
- not materialized yet.

The UI can color these states, but the data model should preserve the distinction.

## Evidence Comparison

Evidence analysis starts after at least one evaluation/check has been run.

Useful evidence-level operations:

- compare two evidence trees for the same binding;
- compare success evidence with a failed check report;
- align frames by condition id, branch id, rule id, binding, and engine support metadata;
- summarize the smallest observed change responsible for a status change;
- group many run-level changes by changed condition or branch;
- distinguish "candidate changed" from "proof path changed but candidate remained stable".

Evidence comparison may refer back to a rule diff, but it does not create that rule diff.

## Engine Compatibility

The user operation model should be unified. The proof semantics should not be forced into a single engine-independent shape.

Native rule evaluation, ProbLog, PyReason, and Datalog-like adapters may differ significantly in what they can expose:

- native rule evaluation may support strong condition/frame alignment;
- ProbLog may expose probabilistic proof/provenance rather than simple boolean proof frames;
- PyReason may expose temporal graph annotations rather than static rule branches;
- external engines may only support candidate output and limited provenance.

Therefore adapters should declare capabilities:

- supports success evidence;
- supports check for concrete binding;
- supports failed check explanation;
- supports lazy carrier replay;
- supports frame-level evidence diff;
- supports probability or temporal diff only.

The product should keep the user workflow similar while allowing engine-specific degradation.

## What Is Already Converging

The following design points are relatively stable:

- Rule is the operable object.
- Evidence is a run-derived view, not a mutable proof object.
- Evidence boxes do not generate rule patches.
- Rule diff and evidence diff are different layers.
- Candidate diff and proof-path diff are different layers.
- Generated condition ids are acceptable for local use; explicit ids are better for durable handles.
- Cross-rule shared condition changes require explicit shared identity.
- Branches are the lower-level representation of OR alternatives; conditions inside a branch are AND-connected.
- Adding conditions should trigger recompilation and binding planning.
- Lazy red/green review requires an explicit candidate universe.
- Failed why-not reports should be materialized on demand through check/replay.

## Remaining Open Questions

These should be resolved in a future active blueprint before implementation:

1. What exact rule module kinds are in the MVP?
2. Which generated id strategy is stable enough for first implementation: UUID, source span, structural hash, or a hybrid?
3. What is the minimum binding planner needed to support new variables in added conditions?
4. Should MVP include add-condition, or only replace/disable/parameter override?
5. What is the first-class representation of candidate universe?
6. Which engine gets first support for concrete binding check?
7. How much failed-check explanation can native evaluation produce without building a full execution trace system?
8. What statuses are required for ProbLog and PyReason so red/green UI does not misrepresent probabilistic or temporal semantics?
9. How should rule variants be stored if the user promotes a what-if scenario into a saved variant or new rule version?
10. What audit records are required for rule patch, rule variant, evaluate, check, replay, and evidence diff?

## Suggested Blueprint Scope

A conservative first implementation could target:

- rule module ids and branch ids;
- rule patch and rule diff for replace/disable/parameter override;
- optional add-condition if binding planning is clear;
- native evaluate with success evidence alignment;
- native check for explicit binding;
- lazy why-not carrier for explicit candidate universe only;
- run diff and evidence diff as separate review surfaces;
- no global failed-attempt trace;
- no partial recomputation of evidence trees;
- engine capability declarations for degraded modes.

The product phrasing should be:

```text
Rule Variant + Evidence Replay
```

or:

```text
Rule Replay With Operational Evidence Views
```

Avoid calling the system "mutable evidence tree"; that name suggests incorrect semantics.
