# Rule Replay With Evidence Diff

- Status: implemented
- Created: 2026-05-01
- Last Updated: 2026-05-01
- Branch: `evidence-tree-operational-overlay`
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/application/`
  - `src/kernel/authoring/`
  - `src/kernel/core/`
  - `src/kernel/audit/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [rule-replay working reference bundle](../../references/working/rule-replay/README.md)
- Audit Log:
  - [2026-05-01_rule-replay-with-evidence-diff.audit.md](./2026-05-01_rule-replay-with-evidence-diff.audit.md)

## 1. Problem

Current evidence surfaces explain successful inference paths, but they do not support a disciplined review workflow for "what if this rule or derivation were different?" The product goal is not to mutate evidence trees. The goal is to let users create explicit rule/derivation variants, re-run normal inference, and compare candidate/evidence outcomes.

The synthesis in the rule-replay reference bundle resolves the previous design haze:

- Evidence trees are run-derived analysis views, not mutable proof objects.
- The operable object is a rule, derivation, or rule reference target represented through an explicit patch/variant.
- Authoritative truth comes from compile/validate/evaluate, not from local proof-path mutation.
- Red/green why-not review requires an explicit candidate universe and is not part of the first scoped implementation unless separately proven.

This blueprint exists to turn that design into a source-backed implementation scope. It must not copy the older office-hours implementation sketch directly; that sketch contained incorrect assumptions about branch base, audit writes, compiled-plan rewrites, and stale example paths.

## 2. Goals

- Define a safe first preview for rule/derivation replay with evidence diff.
- Lock the first patch target with source-backed evidence before implementation.
- Preserve runtime authority boundaries: SDK wraps, application owns runtime protocol, audit consumes exported packages.
- Ensure every patched variant is compiled/validated before evaluation.
- Provide a review surface that compares rule/derivation structure changes separately from candidate/evidence changes.
- Keep future compatibility with Parameter Handle, fact-level what-if, candidate universe, lazy why-not carriers, rich status vocabulary, and shared condition identity.

## 3. Non-goals

- No mutable evidence tree API.
- No global failed-attempt trace.
- No lazy red/green why-not board until candidate universe and check semantics are explicitly designed.
- No red/green review UI or "all failed cases" product claim in the first preview.
- No direct application-runtime writes to audit package JSONL files.
- No patch semantics defined as in-place mutation of `CompiledDerivationPlan.body_ir`.
- No new `condition_id` / `branch_id` addressing scheme without resolving compatibility with existing `b{branch}.a{atom}` locators.
- No full Parameter Handle UX unless compiler/SDK support is explicitly included in scope.
- No fact-level non-committing what-if unless an explicit scenario mechanism is included in scope.
- No multi-engine parity claim for PyReason / ProbLog / Souffle in the first preview.

## 4. Current Context

- Current branch: `evidence-tree-operational-overlay`.
- Internal baseline has already been merged back into local `master`; this work should not be based on `oss-prep-v0.1`.
- Confirmed kernel baseline on current branch:

```text
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
Ran 709 tests in 5.620s
OK (skipped=1)
```

- `kernel.sdk` currently lowers SDK `Derivation` objects / authoring payloads into compiled derivation dictionaries.
- `kernel.application.protocol.derivation.CompiledDerivationPlan` carries derivation evaluation data. It is not a mutable `Rule` object and does not carry registry state.
- Existing condition addressing uses atom-position forms:
  - prefix locators such as `b{branch}.a{atom}` for `condition_weights`;
  - suffixed support/evidence keys such as `b{branch}.a{atom}:{kind_or_pred_id}` that can be normalized back to the prefix.
- Current examples do not include `examples/03_dora_minimal_evidence_tree.ipynb`; `examples/10_v01_onboarding_journey.ipynb` is the likely starting point if a notebook/demo is in scope.
- The rule-replay working reference bundle is the canonical reference entry for this blueprint. Start with its synthesis document; treat the bundled predecessor drafts as historical inputs.

## 5. Proposed Shape

First scoped preview:

```text
top-level SDK/authoring Derivation
  -> explicit temporary authoring variant
  -> compile / validate
  -> evaluate through the existing SDK/application runtime
  -> compare candidate sets and read-only evidence views
```

The first implementation should patch only a top-level derivation body. It should not patch a compiled plan in place and should not patch a referenced registry rule. Referenced `RuleRef` variants are design-reserved because the current runtime builds a `RuleRegistry` from dependency rules during SDK lowering, and registry-level variants need a separate ownership model.

The patch target is an authoring-level derivation payload or SDK `Derivation` shape. A patch produces a temporary variant of that authoring object, then sends the variant through the same compile/validate path used by `SDKStore.evaluate(...)`. The generated `CompiledDerivationPlan` is an output of that path, not the object users operate on.

Condition addressing in this preview should reuse existing atom-position locators:

- `b{branch}.a{atom}` as the canonical patch locator;
- suffixed support/evidence keys such as `b{branch}.a{atom}:{kind_or_pred_id}` normalized back to the prefix for comparison.

Replay records are transient in v0.1.1 unless a separate engine-neutral export owner is introduced. `kernel.audit` may later consume exported replay material, but it should not become the live write owner.

The public review shape is:

```text
before = evaluate(original_derivation)
after = evaluate(temporary_variant)
diff = compare(before, after)
```

The first diff should distinguish candidate-level changes from evidence-view changes. It must not claim complete failed-case coverage or a red/green board without an explicit candidate universe.

## 6. Boundaries And Invariants

- Evidence remains read-only and run-derived.
- Public evidence APIs should expose immutable snapshots / value-like DTOs; annotations, notes, or decisions must live outside evidence-tree mutation.
- Patch semantics must be explicit and auditable at the event/carrier level if persistence is in scope.
- Patched variants must pass compile/validation before evaluation.
- Candidate diff and evidence diff remain separate concepts.
- Rule/derivation diff and evidence diff remain separate concepts.
- `kernel.audit` reads exported audit packages; it is not the live write owner.
- Any locator work must account for both prefix and suffixed atom-position forms.
- Any status schema introduced in this work must leave room for future statuses beyond `derived` / `not_derived`.

## 7. Acceptance

Draft-stage acceptance:

- [x] Step 0 answers all seven questions in §8 with source-backed notes.
- [x] §5 Proposed Shape is updated from `BLOCKED ON STEP 0` to a concrete scoped design.
- [x] §8 Implementation Plan is updated from investigation tasks to implementation steps.
- [x] The audit log records the scope decision that moves this blueprint from `draft` to `scoped`.

Implementation-stage acceptance:

- [x] Code behavior supports replay of a temporary top-level derivation variant through the existing compile/validate/evaluate path.
- [x] The implementation includes at least one source-backed condition operation on a derivation body and rejects invalid locators before evaluation.
- [x] No mutable evidence tree API is introduced.
- [x] Patched variants use compile/validation before evaluation.
- [x] Candidate/evidence comparison does not claim red/green completeness without candidate universe.
- [x] Audit/package behavior respects module ownership boundaries.
- [x] Targeted tests and the confirmed kernel unittest baseline pass.
- [x] `python -m ruff check src/kernel` passes.
- [x] Affected module docs are synchronized.

## 8. Implementation Plan

### Step 0 — Source-Backed Feasibility And Scope Lock

Completed on 2026-05-01.

1. Patch target taxonomy:
   - Decision: first preview patches a top-level derivation body by producing a temporary authoring variant.
   - Out of scope: direct referenced registry rule patches, global RuleRef variants, and compiled-plan patch targets.
   - Source basis: `src/kernel/sdk/dsl/rule.py` exposes immutable SDK `Derivation` / `Rule` objects and `dependency_rules`; `src/kernel/sdk/store.py` resolves dependency rules into a runtime `RuleRegistry`; `src/kernel/application/protocol/derivation.py` defines `CompiledDerivationPlan` as a frozen evaluation DTO with `body_ir`, not a rule authoring object.

2. Compile path:
   - Decision: apply patches before compile, then use the existing SDK/authoring compile path.
   - Source basis: `SDKStore._compile_derivation_input(...)` normalizes SDK/authoring derivations and calls `compile_authoring_derivation_v1(...)`; `_compiled_derivation_plan_to_application(...)` maps compiled dicts to `CompiledDerivationPlan` after validation. `compile_authoring_derivation_v1(...)` performs schema-aware head/where validation.

3. Locator strategy:
   - Decision: use `b{branch}.a{atom}` for first-preview patch locators.
   - Source basis: `compile_authoring_rule_v1(...)` validates `condition_weights` against keys produced by `_collect_condition_keys(...)`; `make_pred_atom_key(...)` and `make_non_fact_step_key(...)` produce suffixed support keys; `_extract_condition_key(...)` in certainty annotation normalizes suffixed keys by splitting at `:`.
   - Reserved: generated stable ids and cross-rule `shared_id` / library conditions.

4. Runtime event / audit carrier:
   - Decision: keep replay records transient for v0.1.1 unless implementation explicitly creates an engine-neutral export owner.
   - Source basis: audit JSONL materialization is currently concentrated in `src/kernel/adapters/souffle/package.py::export_package(...)`; `src/kernel/audit/reader.py` reads packages. There is no current rule-replay carrier or engine-neutral audit export module.

5. Demo/example vehicle:
   - Decision: if a public notebook is included, create a new example or extend `examples/10_v01_onboarding_journey.ipynb`.
   - Source basis: current examples are `01`, `02`, `05`, `06`, and `10`; there is no `examples/03_dora_minimal_evidence_tree.ipynb`.

6. Test baseline:
   - Decision: use the current kernel unittest command as the baseline gate before and after implementation:

```text
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
```

   - Current confirmed baseline: `Ran 709 tests ... OK (skipped=1)`.

7. Scope split:
   - In scope: temporary top-level derivation variant replay, compile/validate/evaluate through existing runtime, candidate diff, read-only evidence comparison where evidence is available.
   - Design-reserved: Parameter Handle, fact-level non-committing what-if, lazy why-not carrier, explicit candidate universe, rich status vocabulary, shared condition identity, local proof-path recheck, persistent replay event export.

### Step 1 — Derivation Variant Patch Substrate

Add a small internal substrate for creating temporary derivation authoring variants. It should:

1. Accept an SDK `Derivation` or authoring derivation payload.
2. Address body atoms by `b{branch}.a{atom}`.
3. Produce a new authoring payload without mutating the original object.
4. Reject missing branches/atoms with explicit SDK/application errors before evaluation.

### Step 2 — Replay Evaluation Wrapper

Add a narrow SDK-facing entry point that evaluates original and variant derivations through the existing `SDKStore.evaluate(...)` / application path. The wrapper should not introduce a new engine-specific evaluation path.

### Step 3 — Candidate And Evidence Diff

Add comparison helpers that separate:

1. Candidate set changes: added, removed, retained.
2. Evidence-view changes for retained candidates when support/evidence artifacts exist.
3. Explicit degraded/unsupported states when evidence is unavailable.

### Step 4 — Tests

Add focused tests for:

1. Valid derivation atom patch creates a variant and evaluates through compile/validate.
2. Invalid locator fails before evaluation.
3. Original derivation object/payload is unchanged.
4. Candidate diff does not imply complete failed-case coverage.
5. No audit JSONL persistence is introduced by the preview path.

### Step 5 — Docs / Example

Update affected module docs. If a notebook is added, prefer a new narrowly named example or extend `examples/10_v01_onboarding_journey.ipynb` without referencing removed `examples/03` material.

## 9. Docs To Update

- `src/kernel/sdk/docs/`
- `src/kernel/application/docs/` if a protocol/runtime DTO is added
- `src/kernel/audit/docs/` only if audit package consumption changes
- `examples/README.md` if a notebook/example is added
- `docs/README.md` only if a new durable docs entry is introduced

## 10. Outcome / Deviations

Implemented on 2026-05-01.

### Final Landed Result

- 5 implementation commits on `evidence-tree-operational-overlay`:
  - Step 1 `98c0138` — patch substrate (`kernel.sdk.replay`)
  - Step 2 `0fa2404` — replay wrapper (`SDKStore.replay_with_patch`)
  - Step 3 `bdcceb6` — candidate diff (`compare_candidates`, `CandidateDiff`)
  - Step 4 `e943657` — evidence comparison (`compare_evidence`, `EvidenceComparison`)
  - Step 5 — journey test, SDK user guide chapter, and blueprint close-out
- Public surface:
  - `SDKStore.replay_with_patch(derivation, *, locator, new_atom) -> ReplayResult`
  - DTOs: `ReplayResult`, `CandidateDiff`, `EvidenceComparison`
  - Helpers: `compare_candidates`, `compare_evidence`
  - Methods: `ReplayResult.diff()`, `CandidateDiff.evidence_comparisons()`
- Test baseline: 709 pre-blueprint tests -> 777 OK / 1 skip after Step 5.
- Module docs synced:
  - `src/kernel/sdk/docs/00_user_guide.md` section 15
  - `src/kernel/sdk/docs/00_user_guide.en.md` section 15

### Deviations From Scoped Blueprint

- `candidate_key` instead of `candidate_id` for diff identity. Step 3 initially proposed `candidate_id`, but pre-implementation review caught that `candidate_id` includes `run_id` and is not cross-run stable. `candidate_key` is the correct content identity for replay diff.
- Positive atom-shape detection in the Step 1 patch substrate. The initial sketch used list-vs-non-list branch detection, which would misclassify JSON list-form atoms such as `["pred", "p", []]` as branches. The implementation now detects atoms by string head and supports both tuple-form and list-form atoms.
- `where` / `body` coexistence is handled explicitly. The compiler requires matching `where` and `body` when both are present, so `replace_atom(...)` patches both fields only after validating that they are equal.
- Step 5 notebook example was deferred. The user guide and journey test provide the required preview documentation and acceptance gate; a notebook can be added as a follow-up without changing the implementation contract.

### Why Deviations Were Accepted

The deviations were correctness fixes or scope controls discovered by source-backed pre-implementation review. They did not expand the public contract. They tightened the scoped boundaries: native engine only, no compiled-plan rewrite, no audit JSONL persistence, no mutable evidence tree API, and no red/green completeness claim without a candidate universe.

### Tests And Docs Completed

- New focused tests cover patch substrate, replay runtime, candidate diff, evidence comparison, and one end-to-end v0.1.1 journey.
- Final verification:
  - `PYTHONPATH=src python -m unittest kernel.tests.test_v01_rule_replay_journey -v`
  - `PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"`
  - `python -m ruff check src/kernel`
  - `git diff --check`
- SDK module docs updated in both Chinese and English user guides.

### Archive Plan

Keep this blueprint in `active/` until the v0.1.1 release path finishes. After release and a short stability window, archive it under `docs/blueprints/archive/` with the rule-replay reference bundle preserved under `docs/references/working/rule-replay/` or moved to the matching references archive.
