# Task Blueprint: T5.8 Semantics Lite + Wrapper-Application Rule Path Fix

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M (predicted)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-26_t5-8-semantics-lite-wrapper-fix.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- Predecessor state:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.
  - T5.3 Explanation Envelope + Live Row Resolver archived at `ba5e5c26`; feature anchor `53551cb6`.
  - T5.4 Row Close + Manual Explain Closed-Head Gate archived at `7464c3e3`; feature anchor `c820f102`.
  - T5.5 Why-Not Fold + Legacy Evidence Quarantine archived at `ec45f12f`; feature anchor `5113e13d`.
  - T5.6 Final SDK Rule Flip archived at `7aa1c6a3`; feature anchor `ad810f4d`.
  - T5.7 Legacy Hard-Cut + Service/Docs Migration archived at `8173c715`; feature anchors `41f7e60f`, `63718d09`, and `62279515`.
  - T5 cycle memory consolidation anchored at `4130bad6`.
  - Post-T5 quickstart namespace cleanup anchored at `5ed165cc`.
  - Post-T5 docs cleanup commits through current local HEAD `fe4c2a73` are docs-only predecessors for this mandatory T5.8 continuation.

## 0. Scope Locks

### In scope

- Enable public SDK semantics wrappers with application `Rule` and `RuleExpr` evaluate inputs.
  - `fg.eval.evaluate(rule, head=rule, semantics=ProbLogSemantics())` must work.
  - `fg.eval.evaluate(rule, head=rule, semantics=PyReasonSemantics())` must work.
  - `fg.eval.evaluate(rule_expr, head=rule, semantics=ProbLogSemantics())` must work.
  - `fg.eval.evaluate(inference, semantics=ProbLogSemantics())` must continue to work as v0.2 compatibility.
  - `fg.eval.evaluate(rule, head=rule, semantics=SemanticsProfile(...))` must continue to work.
  - `fg.eval.evaluate(rule, head=rule, engine="problog")` must continue to work.
- Fix the current SDK public wrapper resolver gap:
  - relax the `derivation is None or not hasattr(derivation, "where")` guard for public wrappers;
  - pass a derivation/context value from `_evaluate_rule_expr_input(...)` into `_resolve_public_engine_and_semantics(...)`;
  - allow wrapper lowering for application `Rule`, `RuleExpr`, and legacy `Inference` without reintroducing legacy public result shapes.
- Define wrapper lowering behavior for application-rule contexts:
  - empty wrappers lower to deterministic defaults without requiring derivation branch ids;
  - wrapper plus `RuleExpr` maps branch-probability or branch-bound keys to RuleExpr branch ids;
  - wrapper plus single application `Rule` uses a single-branch fallback when no branch-specific config is provided;
  - wrapper plus single application `Rule` rejects branch-specific multi-branch config with a clear SDK boundary error;
  - messages use final SDK `Rule` naming from T5.6, not legacy SDK Rule wording.
- Implement the Semantics Lite portion of C73:
  - add wrapper-level `rule_params` shape keyed by application `Rule.id`;
  - validate unknown rule ids before adapter dispatch;
  - lower accepted values into `SemanticsProfile.rule_projection`;
  - do not require or add adapter consumption.
- Implement the Semantics Lite portion of C75:
  - keep `ProbLogSemantics` and `PyReasonSemantics` symmetric as public wrappers that normalize into core `SemanticsProfile`;
  - keep `raw_kind` / `bound` as carrier-only result fields, not semantics proof or adapter math;
  - document `raw_kind="probabilistic"` with `bound=(p, p)` as the point-probability carrier model when an adapter/runtime supplies such a value;
  - ensure wrapper defaults appear in the normalized profile and therefore affect D19 `semantics_digest`.
- Add focused tests for the six wrapper/application-rule matrix cases and for C73/C75 validation.
- Add narrow docs/docstring updates:
  - `docs/official/kernel/quickstart/semantics.md` teaches application `Rule` plus wrapper as the primary path;
  - legacy `Inference` plus wrapper is documented as compatibility, not the preferred path;
  - `ProbLogSemantics` and `PyReasonSemantics` docstrings mention application rule or inference inputs;
  - narrow SDK docs may be updated only where needed to avoid contradicting T5.8.

### Out of scope

- C74 PyReason adapter atom-bound execution.
- C76 ProbLog adapter raw_kind / bound consumption.
- C77 temporal projection runtime behavior.
- C78 PyReason `iteration_count` execution.
- D25 mismatch policy changes.
- T5.1-T5.7 public DTO, evaluate, explain, close, Rule, service, OpenAPI, or legacy hard-cut contract changes.
- New public DTOs.
- Adapter production edits under `src/factgraph/adapters/`.
- Service routes or OpenAPI changes.
- Full docs rewrite beyond the narrow semantics path.
- Database or persistent schema changes.

### M-to-L / stop-and-amend triggers

Pause and amend if implementation requires:

- edits to adapter production files;
- changing runtime evaluation behavior beyond SDK wrapper lowering and validation;
- adding a new public DTO;
- changing `EvaluateResult`, `EvaluateRow`, `Explanation`, `Rule`, `EvidenceRef`, `Claim`, or digest contracts;
- database or persistent schema changes;
- service/OpenAPI changes;
- broad docs migration that belongs to a separate docs cleanup;
- changing D25 semantics mismatch behavior or warning policy.

## 1. Inputs

D26 is the primary source. Section 4.2 permits a Semantics Lite lane after T5 Core when work remains M-class and does not edit adapter production files. Section 4.3 classifies C73 per-rule semantics params as Semantics Lite eligible when implemented as wrapper shape, validation, and `SemanticsProfile` lowering. Section 4.5 classifies C75 wrapper symmetry and carrier-model documentation as Semantics Lite eligible. Sections 4.6-4.9 defer adapter-touching C76/C77/C78 and broader adapter execution work.

D25 section 4.1 makes normalized `semantics_digest` content the comparison source. T5.8 may change wrapper lowering into `SemanticsProfile`, which changes the digest input by design, but it must not change D25 strict mismatch policy, warning policy, or row/manual checked-scope semantics.

D17 and D19 provide the result and digest substrate. `raw_kind` / `bound` remain nullable carriers copied from row/runtime context. `semantics_digest` comes from normalized core `SemanticsProfile`, not wrapper identity. T5.8 must preserve T5.1-T5.7 DTO and digest contracts.

User-found shipped gap:

- `src/factgraph/sdk/store.py:2142-2144` currently rejects public wrappers unless `derivation` exists and has `.where`.
- `_evaluate_rule_expr_input(...)` currently calls `_resolve_public_engine_and_semantics(..., derivation=None, api_path="evaluate(rule_expr)")`.
- This blocks public wrappers with application `Rule` and `RuleExpr` inputs even after T5.2/T5.6 made those paths primary.

Pre-draft shipped-source reads found:

- `src/factgraph/sdk/semantics.py` currently defines `ProbLogSemantics` and `PyReasonSemantics` as inference-oriented wrappers.
- `src/factgraph/sdk/store.py` has `_preview_public_semantics(...)`, `_lower_public_semantics(...)`, `_branch_id_index_for_derivation(...)`, and `_inspect_where_branches(...)` helpers that can be extended without adapter edits.
- RuleExpr lowering already produces branch ids (`b0`, `b1`, ...), and application `Rule` has a single AND body unless a `RuleExpr` is evaluated.
- Current docs still present semantics as primarily inference-oriented.

## 2. Plan

### 2.1 Run Step 4.6 inventory before implementation

Before scoped status, record:

- public wrapper definitions and docstrings;
- `_resolve_public_engine_and_semantics(...)` guard and all callers;
- `_evaluate_rule_expr_input(...)` call path and available source/head context;
- `_lower_public_semantics(...)` derivation assumptions;
- RuleExpr branch-id substrate;
- existing semantics tests and docs;
- adapter guard proving no T5.8 implementation owner under `src/factgraph/adapters/`.

### 2.2 Fix resolver context for application `Rule` and `RuleExpr`

Implementation should preserve one public resolver path:

- For `SemanticsProfile`, keep existing engine validation.
- For public wrappers, pass a context object that can resolve branches and rule ids:
  - legacy `Inference` remains supported;
  - application `Rule` uses single-rule context;
  - `RuleExpr` uses RuleExpr lowering branch ids.
- Keep explicit engine mismatch rejection.
- Keep public SDK errors as `SDKStoreError` unless an existing protocol validator raises before the SDK boundary wraps it.

### 2.3 Lower wrappers for single-rule and RuleExpr contexts

Expected behavior:

- Empty `ProbLogSemantics()` plus application `Rule` lowers to a valid `SemanticsProfile(engine="problog")`.
- Empty `PyReasonSemantics()` plus application `Rule` lowers to a valid `SemanticsProfile(engine="pyreason")`.
- Branch-specific config with a single application `Rule` is rejected unless the implementation defines one accepted single-branch key and tests it explicitly.
- RuleExpr config uses declared RuleExpr branch ids. Unknown branch ids raise before adapter dispatch.
- Existing legacy `Inference` branch-id lowering remains compatible.

### 2.4 Add wrapper-level C73 rule params without adapter consumption

Implementation may introduce small dataclasses or structured dictionaries for wrapper-level rule params, but must stay inside current public wrapper namespace.

Required behavior:

- Rule params are keyed by application `Rule.id`.
- Unknown ids are rejected before adapter dispatch.
- Lowered values are represented in `SemanticsProfile.rule_projection` in a stable, canonical shape.
- No adapter production file consumes the new entries in T5.8.
- If shape design becomes large or ambiguous, pause and amend instead of creating a broad public DTO.

### 2.5 Make C75 wrapper symmetry explicit

Implementation should align the two wrappers:

- both wrappers expose defaults that normalize deterministically;
- both wrappers lower to `SemanticsProfile` without requiring legacy `Inference`;
- both wrappers document the normalized profile as the digest source;
- carrier documentation clarifies that `raw_kind` / `bound` may reflect adapter/runtime output but are not used to prove semantics consistency.

### 2.6 Narrow docs and docstrings

Update only the docs needed for this fix:

- `docs/official/kernel/quickstart/semantics.md`;
- wrapper docstrings in `src/factgraph/sdk/semantics.py`;
- optionally `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` if the current text contradicts application-rule wrapper support.

Do not reopen broad docs migration completed in T5.7.

### 2.7 Ordering

Preferred implementation order:

1. Add tests for the current wrapper/application-rule failure and the six-matrix contract.
2. Extend wrapper/context lowering.
3. Add C73/C75 wrapper shape and normalization tests.
4. Update narrow docs/docstrings.
5. Run focused tests, G7 preservation, ruff, and diff check.

## 3. Expected Code Changes

Likely production files:

- `src/factgraph/sdk/store.py`
  - resolver context fix;
  - wrapper lowering for application `Rule` / `RuleExpr`;
  - C73 rule-id validation and lowering;
  - final SDK `Rule` naming in errors.
- `src/factgraph/sdk/semantics.py`
  - wrapper fields / validation;
  - docstring updates;
  - possible small internal helper types if needed.
- `docs/official/kernel/quickstart/semantics.md`
  - application `Rule` plus wrapper primary example.
- Optional narrow SDK docs:
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`;
  - `src/factgraph/sdk/docs/04_api_surface.en.md`.

Likely tests:

- `tests/sdk/test_rule_expr_evaluate.py` or a new focused SDK semantics test file.
- Existing semantics inspection tests if present.

Forbidden production files:

- `src/factgraph/adapters/**`
- `src/service/**`
- `docs/api/openapi.yaml`

## 4. Tests

Minimum focused test matrix:

- `evaluate(rule, head=rule, semantics=ProbLogSemantics())` returns `EvaluateResult`.
- `evaluate(rule, head=rule, semantics=PyReasonSemantics())` returns `EvaluateResult`.
- `evaluate(rule_expr, head=rule, semantics=ProbLogSemantics())` returns `EvaluateResult`.
- `evaluate(inference, semantics=ProbLogSemantics())` still returns `EvaluateResult`.
- `evaluate(rule, head=rule, semantics=SemanticsProfile(...))` still returns `EvaluateResult`.
- `evaluate(rule, head=rule, engine="problog")` still returns `EvaluateResult`.

Additional required tests:

- wrapper plus application `Rule` no longer raises "SDK public semantics require SDK Rule or Inference object input";
- wrapper plus `RuleExpr` accepts known branch ids and rejects unknown branch ids;
- wrapper plus single application `Rule` rejects multi-branch config or documents a tested single-branch fallback;
- `rule_params` accepts known `Rule.id` and rejects unknown ids;
- normalized wrapper defaults affect `semantics_digest`;
- D25 mismatch policy remains strict and unchanged in row/manual paths;
- no adapter production files are touched;
- T5.1-T5.7 focused preservation remains green.

G7 preservation command remains the inherited 10-module unittest suite. Expected baseline before implementation is 171 tests OK.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Wrapper lowering becomes adapter behavior | Keep all changes in SDK wrapper validation/lowering and `SemanticsProfile` construction; no adapter edits. |
| RuleExpr branch-id mapping diverges from lowering | Use existing RuleExpr lowering branch ids and focused tests. |
| Application `Rule` has no branch ids | Define empty-wrapper success and branch-specific rejection or a tested single-branch key. |
| C73 shape becomes a new public DTO | Keep shape inside existing wrappers or amend before adding broad public types. |
| D25 policy accidentally changes | Do not change mismatch/checked-scope code; add preservation tests if touched. |
| Docs reopen T5.7 migration | Limit docs changes to semantics wrapper examples and docstrings. |
| Existing legacy `Inference` wrapper users break | Include compatibility test for `Inference` plus wrapper. |
| Semantics digest changes unexpectedly | Tests should assert deterministic profile normalization and digest changes when defaults/rule params differ. |

## 6. Verification Gates

Draft review:

- Step 4.2 reviewer confirms scope, source decisions, test matrix, and stop triggers.

Scoped:

- Step 4.6 grep results recorded in audit.
- Blueprint and audit move from `draft` to `scoped`.
- No A-fallback triggered.

Baseline:

- G7 command records expected 171 tests OK at scoped anchor.

Feature:

- focused T5.8 wrapper matrix passes;
- C73/C75 focused tests pass;
- G7 preservation remains green;
- touched-file ruff clean;
- `git diff --check` clean;
- no adapter/service/OpenAPI edits;
- dirty baseline remains preserved.

Closure:

- Blueprint and audit move to `implemented`;
- outcome records feature commit, tests, deviations, and deferred adapter work;
- archive moves both files to `workflow/blueprints/archive/`.

## 7. Rollback / Containment

T5.8 must remain local until reviewed clean and archived. If implementation crosses into adapter execution or broad semantics behavior, stop and amend rather than partially landing.

Rollback should revert the T5.8 feature commit(s) and keep predecessor T5.1-T5.7 commits intact. Do not revert post-T5 docs cleanup commits or unrelated dirty baseline files.

## 8. Implementation Steps

1. Draft blueprint pair.
2. Step 4.2 review.
3. Step 4.6 grep and scoped commit.
4. G7 baseline commit.
5. Feature implementation.
6. Step 4.7 review and fix if needed.
7. Closure commit.
8. Archive commit.
9. Optional T5.8 push gate with milestone `milestone/t5-8-semantics-wrapper-fix-2026-05-26`.

## 9. Reviewer Focus

Reviewer should focus on:

- whether public wrappers now work with application `Rule` / `RuleExpr` without reopening adapter work;
- whether C73 rule params stay wrapper/profile-only;
- whether C75 wrapper symmetry is reflected in normalized profiles and docs;
- whether D25 strict semantics mismatch policy is unchanged;
- whether tests cover the six-matrix user-found gap;
- whether docs clearly prefer application `Rule` while preserving `Inference` as compatibility.

## 10. Outcome

Pending.
