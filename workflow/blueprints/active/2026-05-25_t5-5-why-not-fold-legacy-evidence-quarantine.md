# Task Blueprint: T5.5 Why-Not Fold + Legacy Evidence Quarantine

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted; split if hard-cut deletion or service/docs migration leaks in)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- Predecessor slices:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.
  - T5.3 Explanation Envelope + Live Row Resolver archived at `ba5e5c26`; feature anchor `53551cb6`.
  - T5.4 Row Close + Manual Explain Closed-Head Gate archived at `7464c3e3`; feature anchor `c820f102`.

## 0. Scope Locks

### In scope

- Lock failed `Explanation(status="failed")` as the T5 v1 why-not envelope.
- Add narrow tests proving that row/manual explain failure surfaces use `Explanation`, not shipped WhyNot DTOs.
- Add narrow tests proving no public T5 `.eval.why_not(...)`, `why_not_v2`, `why_not_result`, `EvaluateResult.why_not(...)`, or `counterfactuals` surface exists.
- Classify shipped why-not DTOs/runtime/shells as legacy or internal relative to T5:
  - `WhyNotUniverseRequest`;
  - `WhyNotUniverseResult`;
  - `WhyNotRedRow`;
  - `WhyNotRowDiagnostic`;
  - `WhyNotAtomLocator`;
  - `WhyNotStatus`, `WhyNotEngine`, `WhyNotRowStatus`, `WhyNotFailureKind`, and `WhyNotRowGranularity`;
  - `check_why_not_universe(...)`;
  - `SDKStore.why_not(...)`;
  - `sdk.shells.why_not.sdk_why_not(...)`.
- Add small quarantine markers where useful:
  - docstrings or comments may state "legacy / D23 hard-cut target";
  - tests may assert these are not part of the new T5 public eval evidence path.
- Verify implementation does not convert `WhyNotUniverseResult.red[0].diagnostic` into `Explanation.failure_class`.
- Preserve D20 failed Explanation behavior:
  - `evidence is None`;
  - `failure_class` uses the five-class enum;
  - `errors=()` for business failure envelopes.
- Preserve D22 future door:
  - future why-not requires a new D-doc, non-lossy algorithm, evidence-tree support, and explicit user demand.

### Out of scope

- Full D23 legacy deletion or public shell removal.
- Removing `SDKStore.why_not(...)` or `fg.what_if.why_not(...)`.
- Service route changes.
- OpenAPI changes.
- Broad docs/examples migration.
- SDK final `Rule` flip.
- New public why-not DTOs.
- New atom-locator public surface.
- Evidence-tree failed-node schema implementation.
- Top-down goal-regression algorithm.
- Adapter production edits or C73-C78 semantics work.
- Changing T5.1-T5.4 DTO/evaluate/explain/close behavior.
- Changing the five D20 failure classes.

### M-to-L triggers

Pause and amend/split if implementation requires:

- deleting old why-not protocol/runtime/shells;
- modifying service routes, OpenAPI, agent tools, or broad docs;
- adding a public `.eval.why_not(...)` or batch counterfactual API;
- embedding `WhyNotAtomLocator`, `WhyNotRowDiagnostic`, or `DiagnoseResult` into `Explanation`;
- redesigning `Explanation.failure_class`;
- changing row/manual explain failure semantics from D20/T5.3/T5.4;
- changing T5.7 hard-cut scope or order;
- changing evidence-tree internal schema.

## 1. Inputs

T5.5 consumes D22 and makes the why-not fold visible in code/tests before the broad D23/T5.7 hard-cut.

D22 locks:

- T5 does not add a public `fg.eval.why_not(...)`;
- failed `Explanation` is the v1 why-not envelope;
- explicit candidate-universe why-not is deferred, not migrated;
- shipped why-not DTOs/runtime/shells are legacy/internal until D23 hard-cut;
- docs must not teach why-not as the T5 evidence path;
- shipped why-not statuses do not map one-to-one into D20 `Explanation`;
- future why-not remains possible only under explicit post-T5 triggers.

D20 locks failed Explanation shape:

- `status="failed"`;
- `evidence=None`;
- a five-class `failure_class`;
- `checked_scope`;
- `suggested_next_steps`;
- no `EvidenceGraph`, Diagnose payload, or atom locator.

D23 locks later hard-cut mechanics:

- old why-not shells and DTOs are hard-cut targets;
- service/OpenAPI/docs migration belongs to T5.7;
- mixed public states are local-only.

Pre-draft shipped-source reads found:

- `src/factgraph/application/protocol/derivation_why_not.py` defines the full legacy WhyNot DTO family and atom locator.
- `src/factgraph/application/why_not_runtime.py` builds green/red candidate-universe boards and composes Diagnose for red rows.
- `src/factgraph/sdk/store.py` still exposes `SDKStore.why_not(...)` as a legacy public method.
- `src/factgraph/sdk/shells/why_not.py` returns `WhyNotUniverseResult` directly and does not wrap into `Explanation`.
- T5.3/T5.4 `Explanation` paths already provide row/manual failed envelopes through `Explanation.failure_class`.

## 2. Plan

### 2.1 Keep T5 public evidence surface narrow

T5.5 must not add any of these surfaces:

```python
fg.eval.why_not(...)
fg.why_not(...)
fg.eval.why_not_v2(...)
fg.eval.why_not_result(...)
EvaluateResult.why_not(...)
result.counterfactuals(...)
```

The only T5 evidence path remains:

```python
row.explain() -> Explanation
fg.eval.explain(expr, head=closed_head, ...) -> Explanation
```

### 2.2 Treat failed Explanation as the v1 why-not envelope

T5.5 should add focused tests and narrow comments/docstrings proving:

- row/manual explain business failures return `Explanation(status="failed")`;
- failed explanations have `evidence=None`;
- failed explanations use D20 `failure_class`;
- failed explanations do not embed `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, `WhyNotAtomLocator`, or `DiagnoseResult`.

Likely failure path to test:

- T5.4 manual closed-head explain with a closed head that is false in the current view returns `Explanation(status="failed", failure_class="closed_head_false")`.

### 2.3 Quarantine shipped why-not as legacy/internal

T5.5 may add narrow docstrings/comments around shipped why-not modules stating that they are:

- legacy SDK/application capability;
- D22-folded relative to T5 evidence;
- D23/T5.7 hard-cut targets;
- not a T5 public evidence API.

Acceptable locations:

- `src/factgraph/application/protocol/derivation_why_not.py` module docstring;
- `src/factgraph/application/why_not_runtime.py` module docstring;
- `src/factgraph/sdk/shells/why_not.py` module docstring;
- `SDKStore.why_not(...)` docstring.

Do not change behavior or signatures in these locations during T5.5.

### 2.4 Avoid lossy conversion

T5.5 must not create any adapter that maps:

```python
WhyNotUniverseResult.red[0].diagnostic -> Explanation.failure_class
WhyNotAtomLocator -> Explanation
DiagnoseResult -> Explanation(status="failed")
```

Tests should assert at least one of:

- no conversion helper exists in the touched T5 code path;
- failed Explanation payloads contain no why-not DTO/atom-locator fields;
- shipped why-not still returns `WhyNotUniverseResult` only on the legacy path until T5.7.

### 2.5 Preserve legacy code until T5.7

T5.5 must not delete old why-not code.

Allowed state after T5.5:

- `SDKStore.why_not(...)` still exists;
- `sdk.shells.why_not.sdk_why_not(...)` still exists;
- application protocol WhyNot DTOs still exist;
- application runtime `check_why_not_universe(...)` still exists;
- tests may mark these as legacy/quarantined but not T5 evidence.

D23/T5.7 owns removal and docs migration.

### 2.6 Narrow docs only

T5.5 may update narrow internal/reference docs or comments if needed for local coherence.

Do not perform broad docs/examples/OpenAPI migration. That remains T5.7.

## 3. Code Changes

Likely production/doc files:

- `src/factgraph/application/protocol/derivation_why_not.py`
  - optional module docstring update marking DTOs legacy/internal relative to T5.
- `src/factgraph/application/why_not_runtime.py`
  - optional module docstring update marking runtime legacy/internal relative to T5.
- `src/factgraph/sdk/shells/why_not.py`
  - optional module docstring update marking shell a D23 hard-cut target.
- `src/factgraph/sdk/store.py`
  - optional docstring note in `SDKStore.why_not(...)`; no behavior/signature change.
- `tests/sdk/test_rule_expr_evaluate.py` or a new `tests/sdk/test_why_not_quarantine.py`
  - assert failed Explanation is the v1 why-not envelope.
- `tests/application/protocol/test_evaluate_result_dtos.py`
  - optionally strengthen failed Explanation no-evidence/no-why-not fields.

Files explicitly out of target scope unless amended:

- `src/service/`;
- `docs/api/openapi.yaml`;
- broad docs/examples/notebooks;
- adapters;
- SDK final `Rule` namespace files;
- evidence-tree internals.

## 4. Tests

Minimum focused tests:

1. Failed manual explain for a closed but false head returns `Explanation(status="failed")`.
2. That failed Explanation has `failure_class="closed_head_false"`.
3. That failed Explanation has `evidence is None`.
4. That failed Explanation has no `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, `WhyNotAtomLocator`, or Diagnose payload attributes.
5. `fg.eval` still has no `why_not` method.
6. `EvaluateResult` has no `why_not` method.
7. `SDKStore.why_not(...)` remains legacy until T5.7 and still returns `WhyNotUniverseResult` on the legacy path if covered by existing tests.
8. No new `why_not_v2`, `why_not_result`, `counterfactuals`, or `result.why_not` symbols appear in production.
9. D20 status/evidence matrix remains green.
10. T5.4 manual explain open-head gate remains green.
11. T5.2 evaluate return-shape tests remain green.
12. Touched-file ruff clean.

G7 preservation baseline before feat:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected inherited baseline: 170 tests OK from T5.4 archive.

## 5. Risks

| Risk | Mitigation |
|---|---|
| T5.5 drifts into D23 deletion. | Keep all behavior/signatures intact; only classify/quarantine and test T5 failed Explanation path. |
| A public why-not alias appears for convenience. | Explicit negative tests for `fg.eval.why_not`, `EvaluateResult.why_not`, `why_not_v2`, `why_not_result`, and `counterfactuals`. |
| Failed Explanation starts carrying atom locator data. | Tests assert no why-not DTO/locator payload is embedded. |
| Legacy why-not tests break due to over-eager quarantine. | T5.5 must not delete or change legacy runtime behavior. |
| Broad docs migration leaks in. | T5.7 owns full docs/examples/OpenAPI migration. |
| Future why-not becomes impossible. | Keep D22 future-door note intact; do not delete design references. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates T5.5 stays quarantine/fold, not hard-cut deletion.
- Reviewer validates failed Explanation is sufficient as v1 why-not envelope for T5.
- Reviewer validates broad service/docs migration stays deferred to T5.7.

### Step 4.6 grep gate

Before scoped:

- search why-not surfaces and aliases;
- search WhyNot DTOs/runtime/shell references;
- search `Explanation.failure_class` and failed Explanation tests;
- search for forbidden conversion helpers;
- search service/docs/OpenAPI/agent blast radius;
- record classification and decide whether T5.5 remains M-class minimal.

### G7 baseline gate

After scoped:

- run inherited G7 preservation command;
- expected baseline is 170 tests OK;
- record pytest deferred and `tests.test_public_inference_factgraph_create` exclusion.

### Feature gate

Run:

- focused T5.5 failed Explanation / why-not quarantine tests;
- T5.4 row-close/manual explain focused tests;
- T5.2/T5.3 evaluate/explain preservation tests;
- updated G7 preservation suite;
- touched-file ruff.

Pytest remains deferred per existing SIGSEGV environment lock unless environment constraints change.

## 7. Rollback

Rollback must preserve T5.1-T5.4 substrates:

- If quarantine docstrings are too broad, revert docstring/comment edits only.
- If failed Explanation tests are too coupled to current implementation, adjust tests without changing D20/D22 contracts.
- Do not remove or alter legacy why-not behavior during rollback.
- Do not revert T5.4 row-close/manual explain.
- Do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.5 may add narrow comments/docstrings only.

Deferred:

- full user-facing docs/examples/OpenAPI migration remains T5.7;
- final SDK `Rule` naming docs remain T5.6/T5.7;
- future why-not product docs require a new post-T5 D-doc.

## 9. Reviewer Focus

- Does the draft keep T5.5 lightweight and avoid D23 hard-cut deletion?
- Are shipped WhyNot DTOs classified without changing behavior?
- Do tests prove failed Explanation is the v1 why-not envelope?
- Are lossy atom-locator conversions explicitly forbidden?
- Are service/docs/SDK Rule/adapter boundaries preserved?

## 10. Outcome

Pending implementation.
