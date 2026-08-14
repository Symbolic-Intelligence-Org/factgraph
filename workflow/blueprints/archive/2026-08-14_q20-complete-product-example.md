# Task Blueprint: Q20 complete product example

- Status: archived
- Created: 2026-08-14
- Last Updated: 2026-08-15
- Related Modules:
  - `examples/`
  - `src/factgraph/sdk/`
  - `src/factgraph/application/`
- Related Docs:
  - [Q20 product-interface decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
  - [Q20 product-interface archive](../archive/2026-08-14_factgraph-product-interface.md)
- Audit Log:
  - [2026-08-14_q20-complete-product-example.audit.md](2026-08-14_q20-complete-product-example.audit.md)

## 1. Problem

The Q20 product-interface tutorial demonstrates the major surfaces, but the
current runnable example does not yet show the complete policy-variant
workflow in one business narrative.  A user needs one public-SDK-only notebook
that connects authored Rule/Policy assets, a deterministic Scenario, a
candidate Policy, structured Result/Explain data, a probabilistic Scenario,
an explicit WeightedChoice, and detached replay without presenting internal
compiler syntax as user API.

## 2. Goals

- Extend the current Q20 tutorial with a verified primary/candidate Policy
  comparison under a shared deterministic Scenario effective world.
- Demonstrate the complete supported Scenario V2 operation family relevant to
  business inputs (`set`, `add`, `set_exact` with aligned member metadata, and
  `without`) without implying that Scenario mutates Rule/Policy assets.
- Execute all three durable V2 attachment shapes across the tutorial:
  occurrence, Rule and WeightedChoice, while keeping their non-overlap rule
  explicit.
- Keep the existing Scenario metadata, ProbLog point-probability,
  WeightedChoice, structured Explain and replay demonstrations in one coherent
  public-SDK learning path.
- Make the examples index describe the tutorial as the complete current
  product workflow, with precise support boundaries.
- Correct the adjacent V2 SDK guide's distinction between an `EntityRef` used
  for a Query bind and the managed entity reference used for Scenario input.

## 3. Non-goals

- New Query, Policy, Scenario, profile, result or Explain behavior.
- An AgentPlan compiler, Meander SourceRecord service, or automatic Agent
  write-path migration.
- Inventing an EvidenceGraph for V2 engines that did not capture one.
- Claiming probabilistic Native/Souffle parity or generic engine configuration.

## 4. Current Context

- `examples/09_product_scenario_execution_v2.ipynb` already executes the
  public SDK Q20 paths, including builders, metadata lanes, probability
  materialization, WeightedChoice, views and replay.
- V2 supports a side-pinned candidate Product target via
  `profile.for_target(candidate, side='candidate')`; candidates must preserve
  the selected Query shape and run against the same sealed effective world.
- Q20 deliberately reports unavailable V2 EvidenceGraph support structurally,
  rather than synthesizing a proof graph.

## 5. Proposed Shape

Add coherent notebook sections that (a) build a stricter candidate Policy using
the same local public aliases, create a target-pinned Native deterministic
profile for both primary and candidate, run both against a deterministic
Scenario, and open named baseline/effective/candidate Result views; (b)
exercise every supported Scenario V2 mutation form with paired member metadata;
and (c) use a distinct Rule as a Rule-level ProbLog attachment alongside an
occurrence-level attachment, avoiding the prohibited same-Rule overlap.  The
sections will assert the intended policy delta and replay match.  The
surrounding notebook prose and examples index will make it clear that this is
a logical variant comparison, not a mutable Policy patch or causal claim.

## 6. Boundaries And Invariants

- Only `factgraph.sdk` imports appear in the tutorial.
- The candidate uses an independently authored immutable Policy; no target is
  registered or modified.
- A Scenario remains a run-local effective world and never changes the ledger.
- Candidate/primary share selected shape but have separately sealed target
  pins; the tutorial must not reuse unpinned internal compiler identifiers.
- Existing executed cells and their honest V2 evidence/probability boundaries
  remain intact.
- The example must never attach Rule- and occurrence-level semantics to the
  same Rule in one Policy target; it must name the resulting rejection rule.

## 7. Acceptance

- [x] The tutorial executes end-to-end under the `factpy` kernel with no error
  outputs.
- [x] It demonstrates a side-pinned candidate Policy over a shared Scenario
  world and a matched detached replay.
- [x] It executes every supported product Scenario operation and all three
  non-overlapping V2 attachment shapes in their appropriate profiles.
- [x] It retains public-SDK-only authoring, Scenario, profile, probability,
  WeightedChoice, Result/Explain and replay examples.
- [x] `examples/README.md` accurately indexes the complete tutorial.
- [x] Focused regressions and notebook structural checks pass.

## 8. Implementation Plan

1. Audit the existing notebook and V2 candidate contracts; freeze the example
   sequence and expected observations.
2. Extend the notebook and examples index using only supported public SDK
   APIs; execute it in the project kernel.
3. Run focused Q20 tests and notebook validation; record outcome and archive
   this documentation/example-only blueprint.

## 9. Docs To Update

- `examples/09_product_scenario_execution_v2.ipynb`
- `examples/README.md`
- `src/factgraph/sdk/docs/08_product_scenario_execution_v2.en.md`

## 10. Outcome / Deviations

Implemented the current complete Q20 user journey in the existing product
tutorial rather than splitting users between competing V1/V2 examples:

- Added public-SDK-only deterministic Scenario CRUD for `set`, `add`,
  `set_exact(member_meta=...)`, and `without`, including canonical
  value-to-metadata pairing. The final executed run uses distinct targets for
  the four operations: Alice receives `add`, Bob receives `set_exact`, and
  Carol's `obsolete` tag is actually resolved as `without_value` with one
  masked witness. It also asserts that the source ledger remains unchanged.
- Added an independently authored stricter candidate Policy, side-pinned it
  with `for_target(candidate, side='candidate')`, and ran it against the same
  deterministic Scenario world as the primary Policy.  The executed example
  records baseline `[30]`, primary effective `[35]`, candidate effective
  `[35]`, a shared semantic-world digest, and matched detached replay.
- Added actual occurrence-, distinct Rule-, and WeightedChoice-level profile
  attachment demonstrations, while documenting that Rule and occurrence
  attachment may not overlap for one Rule in one Policy target.
- Corrected the public documentation to distinguish managed entity references
  used by Scenario field operations from typed `EntityRef` values used by
  Query binds.

No runtime behavior or contract changed.  The notebook remains intentionally
honest about its V2 boundaries: point-probability execution is ProbLog-only;
Native/Soufflé probability frames are unsupported; un-captured EvidenceGraphs
remain structurally unavailable; and policy comparison is neither mutation nor
causal attribution.

Verification:

- Real `factpy` notebook execution: 28 cells / 13 code cells, every code cell
  executed, seven real outputs, no errors. The captured operation evidence
  records `set_effective_value`, `ensure_member`, `set_exact_members`, and
  `without_value`; the latter has one masked witness and no synthetic witness.
- Q20 focused regression: 55 passed, 7 subtests passed.
- `git diff --check`: clean.

The blueprint/audit pair is archived; current behavior remains in the SDK
guide, examples README, and notebook.
