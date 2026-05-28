# D22 Decision: T5 Why-Not Disposition

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks the fate of shipped why-not surfaces relative to T5 `Explanation`.
- Implementation Anchors: T5.5 why-not quarantine feat `5113e13d`, T5.7 legacy hard-cut feat `62279515`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q9, F5, section 6 C61 and C70 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.6, 4.7, and 4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.1, 4.2, and 4.8.
  - D18 `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md` sections 4.1, 4.3, 4.6, and 4.8.
  - D20 `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md` sections 4.2, 4.7, and 7.3.
  - D21 `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md` sections 4.1-4.7.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1265-1278`.
  - Sibling future-design note `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md:2282-2331` and `:2406-2432`.
  - Shipped `src/factgraph/application/protocol/derivation_why_not.py:1-346`, `src/factgraph/application/why_not_runtime.py:1-190`, `src/factgraph/application/why_not_runtime.py:300-380`, `src/factgraph/sdk/store.py:1243-1288`, and `src/factgraph/sdk/shells/why_not.py:1-119`.
- Outputs / Downstream:
  - D23 legacy SDK hard-cut plan.
  - D24 T1.3 final SDK `Rule` flip.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and implementation blueprint(s).
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16, D17, D18, D19, and D20 reviewed clean; consumes D21 draft-amend pending Step 4.2 v2 review.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent section 5.8.4 leaves `fg.eval.why_not(...)` pending. It notes that `Explanation(status="failed")` may already cover the core "why did this not hold" need, and it explicitly allows the old why-not surface to be discarded.

Shipped code is different from that target:

- `SDKStore.why_not(...)` is a direct SDK method;
- `sdk.shells.why_not.sdk_why_not(...)` accepts one legacy SDK `Inference` plus an explicit candidate universe;
- application protocol exports `WhyNotUniverseRequest`, `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, and `WhyNotAtomLocator`;
- application runtime evaluates the candidate universe into a green/red board and composes Diagnose for red rows;
- docs still describe `fg.what_if.why_not(...)` and `WhyNotUniverseResult`.

D20 decides that failed explanation is envelope-only: `status="failed"`, `evidence=None`, a five-class `failure_class`, `checked_scope`, and `suggested_next_steps`. D20 also rejects embedding `DiagnoseResult` or `DiagnoseAtomLocator` in failed explanations because the locator is lossy.

Evidence-tree v1 reinforces that direction: failed explanations do not return an evidence tree, atom-level why-not is explicitly deferred, and the user-facing v1 commitment is a diagnostic envelope rather than a lossy single-atom failure tree.

D22 decides whether shipped why-not migrates, folds, remains, or is deleted.

## 2. Scope

This decision locks:

- whether T5 adds a public `fg.eval.why_not(...)` API;
- whether shipped `SDKStore.why_not(...)` and `WhyNotUniverseResult` become part of the T5 public API;
- how the single-row "why did this not hold" use case is represented;
- how explicit candidate-universe why-not is handled in T5;
- whether shipped why-not DTOs / runtime may remain as internal or legacy implementation substrate until D23;
- docs and public API direction for why-not after T5.

## 3. Non-Scope

This decision does not lock:

- exact removal mechanics for old SDK methods, docs, service routes, or tests; D23 owns them;
- `Explanation` field surface or failure-class enum; D20 owns them;
- `row.close()` or manual closed-head construction; D21 owns them;
- final SDK public naming; D24 owns it;
- evaluate/explain semantics mismatch policy; D25 owns it;
- C73-C78 semantics implementation details; D26 owns them;
- a future top-down goal-regression why-not algorithm;
- evidence-tree internal node/edge schema or audit channel;
- implementation slice order beyond D23 owning the hard-cut mechanics.

## 4. Decision

### 4.1 T5 does not add public `fg.eval.why_not(...)`

D22 adopts the "fold" disposition for T5 Core:

- the single-row why-not use case folds into `Explanation(status="failed")`;
- no public `fg.eval.why_not(...)` is introduced in T5;
- no public `why_not_v2`, `why_not_result`, `counterfactuals`, or `result.why_not(...)` alias is introduced;
- old public why-not shells are not promoted as compatibility paths for T5.

This keeps the T5 public evidence surface narrow:

```python
row.explain() -> Explanation
fg.eval.explain(expr, head=closed_head, ...) -> Explanation
```

The user-facing answer to "why did this row or closed-head query not hold?" is a failed `Explanation` envelope, not a separate why-not DTO.

### 4.2 Failed `Explanation` is the v1 why-not envelope

For T5 v1, `Explanation(status="failed")` is the only public why-not-shaped answer.

It carries:

- `failure_class`;
- `checked_scope`;
- `suggested_next_steps`;
- `claim` when resolvable;
- `raw_kind` / `bound` when the evaluated context provides them;
- `errors=()` for business failures.

It does not carry:

- `EvidenceGraph`;
- `WhyNotUniverseResult`;
- `WhyNotRedRow`;
- `WhyNotRowDiagnostic`;
- `WhyNotAtomLocator`;
- Diagnose payloads;
- atom-level "failed atom" hints.

D22 relies on D20's five failure classes:

- `no_matching_row`;
- `closed_head_false`;
- `stale_row`;
- `row_not_in_result`;
- `insufficient_closed_bindings`.

If future users need atom-level why-not, that is a post-T5 evidence/why-not cycle with a real top-down goal-regression algorithm, not a reuse of shipped single-locator diagnostics.

### 4.3 Explicit candidate-universe why-not is deferred, not migrated

Shipped why-not answers a batch question: given an explicit finite candidate universe, partition it into green and red rows and diagnose red rows.

T5 Core does not migrate that batch surface to `.eval.why_not(...)`.

Rationale:

- the batch universe result is a different product shape from D20 `Explanation`;
- shipped red-row diagnostics rely on Diagnose and may emit atom-localized hints that evidence-tree v1 marks lossy for v1;
- D17/D20 public DTOs intentionally avoid green/red universe boards;
- D18 hard-cuts toward one T5 result/explain surface, not parallel compatibility APIs.

Users who need a small number of counterfactual checks can construct closed heads and call manual `fg.eval.explain(...)` per candidate. T5 does not promise that this loop is an efficient batch why-not replacement.

A future post-T5 why-not cycle may introduce a new batch API if user scenarios justify it. That future API must be based on top-down goal regression or another non-lossy algorithm, and it must not inherit shipped `WhyNotAtomLocator` as a public diagnostic contract.

### 4.4 Shipped why-not DTOs are legacy/internal until D23 hard-cut

D22 classifies shipped why-not protocol DTOs and runtime as legacy/internal relative to T5:

- `WhyNotUniverseRequest`;
- `WhyNotUniverseResult`;
- `WhyNotRedRow`;
- `WhyNotRowDiagnostic`;
- `WhyNotAtomLocator`;
- `WhyNotStatus`, `WhyNotEngine`, `WhyNotRowStatus`, `WhyNotFailureKind`, and `WhyNotRowGranularity`;
- `check_why_not_universe(...)`;
- `SDKStore.why_not(...)`;
- `sdk.shells.why_not.sdk_why_not(...)`.

They are not T5 public DTOs and must not be re-exported as part of the new `EvaluateResult` / `Explanation` surface.

D23 owns the exact hard-cut mechanics:

- whether to delete the SDK shell in the same implementation slice as other legacy shells;
- whether application protocol DTOs remain temporarily for old tests during an intermediate local commit;
- how docs and service routes are updated;
- how imports and compatibility references are removed.

D22 only locks the target state: shipped why-not does not survive as a public T5 API.

### 4.5 Docs must not teach why-not as the T5 evidence path

After the T5 hard-cut, user-facing docs should describe:

- `row.explain()` for live-row explanation;
- `fg.eval.explain(expr, head=closed_head, ...)` for manual replay;
- failed `Explanation` envelopes for "why did not hold" outcomes.

Docs must not promote:

- `fg.eval.why_not(...)`;
- `fg.why_not(...)`;
- `fg.what_if.why_not(...)`;
- `WhyNotUniverseResult`;
- `WhyNotAtomLocator`;
- Diagnose-style single failed atom hints.

D23 owns the mechanical docs sweep. D22 locks the content direction.

### 4.6 Why-not errors and statuses do not map one-to-one into D20

Shipped `WhyNotUniverseResult` has statuses `completed`, `unsupported`, and `invalid_request`, plus per-red-row `failed` / `unsupported` diagnostics. D20 `Explanation` has `passed`, `failed`, `unsupported`, and `invalid_request`.

D22 does not define a direct conversion adapter from `WhyNotUniverseResult` to `Explanation`.

Instead:

- row/manual explain computes an `Explanation` directly through the D20 pipeline;
- old why-not runtime, if still present during D23 implementation, remains a legacy path;
- implementation must not wrap `WhyNotUniverseResult.red[0].diagnostic` into `Explanation.failure_class`.

The two models have different units of analysis: one closed-head claim versus a candidate universe board.

### 4.7 T5 keeps the future why-not door open with explicit triggers

D22 does not permanently forbid why-not. It defers first-class why-not until all of these are true:

- user scenarios show repeated batch counterfactual demand that manual explain loops cannot serve;
- a non-lossy top-down goal-regression or equivalent algorithm is designed;
- evidence-tree internal schema can represent missing premises without misleading single-atom locators;
- a new D-doc defines the public DTO and its relationship to `Explanation`.

Until then, T5 Core treats why-not as covered by failed `Explanation` envelopes for single-row / single-closed-head questions.

## 5. Rejected Alternatives

### Option A: Migrate shipped `why_not` directly to `fg.eval.why_not(...)`

- **Rejected because**: it preserves the batch green/red universe product shape and shipped atom locator at the exact moment T5 is narrowing public evidence around `Explanation`.

### Option B: Keep `SDKStore.why_not(...)` as a long-lived compatibility API

- **Rejected because**: D18 hard-cuts public return shape and rejects long-lived compatibility surfaces. Keeping why-not public would leave a second evidence answer model alongside `Explanation`.

### Option C: Convert `WhyNotUniverseResult` into `Explanation`

- **Rejected because**: the unit of analysis differs. A universe result partitions many candidates; an `Explanation` explains one row or one closed-head manual replay.

### Option D: Embed `WhyNotAtomLocator` in failed explanations

- **Rejected because**: D20 and evidence-tree v1 reject the shipped single-atom locator as lossy and potentially misleading.

### Option E: Add `EvaluateResult.why_not(...)`

- **Rejected because**: it creates another public method on the result envelope before T5 proves a batch counterfactual API is needed.

### Option F: Keep why-not docs as an advanced what-if feature

- **Rejected because**: public docs would continue teaching a legacy green/red board after T5 adopts `Explanation` as the public evidence surface.

### Option G: Delete all why-not code in D22

- **Rejected because**: D22 is a decision doc. D23 owns hard-cut mechanics, service-route blast radius, and implementation sequencing.

### Option H: Permanently ban why-not

- **Rejected because**: evidence-tree v1 explicitly leaves atom-level why-not / top-down goal regression as a v2+ path when user demand and algorithms mature.

## 6. Supporting Evidence

| Evidence | Source | D22 use |
|---|---|---|
| Parent marks `fg.eval.why_not(...)` pending and allows full discard. | parent `rule-expression-and-proof-attempt.zh.md:1265-1278` | Confirms D22 must decide keep / migrate / fold / delete |
| Stage 1 audit found shipped raw SDK why-not plus parent-pending future surface. | Stage 1 audit F5 and Q9 | Frames D22 as disposition decision |
| Shipped protocol owns independent WhyNot DTOs and atom locator. | `derivation_why_not.py:1-346` | Identifies legacy DTO surface not adopted by T5 |
| Shipped runtime partitions explicit candidate universe into green/red rows. | `why_not_runtime.py:60-132` | Shows batch board differs from single Explanation |
| Shipped runtime composes Diagnose for red-row diagnostics. | `why_not_runtime.py:300-380` | Supports rejecting Diagnose locator as public T5 failure shape |
| Shipped SDK exposes direct `SDKStore.why_not(...)`. | `sdk/store.py:1243-1288` and `sdk/shells/why_not.py:1-119` | Assigns D23 hard-cut target |
| D20 failed explanations are envelope-only and do not embed Diagnose / atom locator. | D20 sections 4.2 and 4.7 | Establishes T5 failed-answer shape |
| Evidence-tree v1 says failed has no evidence tree and no atom-level why-not in v1. | evidence-tree v1 `:2282-2331`, `:2406-2432` | Supports fold/defer decision |

## 7. Consequences

### 7.1 User-visible consequences

T5 users learn one failed-answer model:

```python
explanation = row.explain()
if explanation.status == "failed":
    explanation.failure_class
    explanation.checked_scope
    explanation.suggested_next_steps
```

For manual checks:

```python
closed_head = row.close()
fg.eval.explain(expr, head=closed_head, ...)
```

There is no new `fg.eval.why_not(...)` in T5.

### 7.2 Implementation consequences

D23 must treat why-not as a legacy hard-cut target, not a surface to migrate.

Implementation may temporarily keep shipped why-not modules while updating tests and docs locally, but final T5 public surface must not export or recommend them.

The T5 explanation implementation must produce failed `Explanation` envelopes directly. It must not call shipped why-not runtime and wrap the result.

### 7.3 Downstream consequences

D23 must include why-not in the legacy blast-radius inventory alongside `accept`, `accept_many`, `run`, `check`, `diagnose`, `what_if`, `engine_options`, and `registry`.

D25 must evaluate semantics consistency for evaluate/explain only; it does not need to define semantics matching for `.eval.why_not`.

D26 may discuss future adapter/evidence algorithms, but it must not reintroduce T5 public why-not without superseding D22.

## 8. Acceptance Criteria

- [ ] T5 does not introduce public `fg.eval.why_not(...)`, `why_not_v2`, or `EvaluateResult.why_not(...)`.
- [ ] Single-row why-not needs are represented by `Explanation(status="failed")`.
- [ ] Failed explanations do not include `WhyNotUniverseResult`, `WhyNotRowDiagnostic`, `WhyNotAtomLocator`, Diagnose payloads, or partial EvidenceGraphs.
- [ ] Explicit candidate-universe why-not is deferred to a future post-T5 cycle.
- [ ] Shipped `SDKStore.why_not(...)` and `sdk.shells.why_not` are classified as D23 hard-cut targets.
- [ ] `WhyNotUniverseResult` and related DTOs are not adopted as T5 public DTOs.
- [ ] T5 docs do not promote old why-not shells as the public evidence path.
- [ ] D22 does not reopen D20 Explanation fields, D21 row.close, D23 hard-cut mechanics, or D26 semantics policy.

## 9. Decision Record

| Date | Stage | Decision | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Fold T5 why-not needs into failed `Explanation`; do not add `.eval.why_not`; classify shipped why-not as D23 legacy hard-cut target. | Drafted after D21 draft-amend; D23 legacy SDK hard-cut plan unblocked after D21/D22 review. |
