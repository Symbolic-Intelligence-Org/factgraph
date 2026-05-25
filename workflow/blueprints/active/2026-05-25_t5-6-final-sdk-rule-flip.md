# Task Blueprint: T5.6 Final SDK Rule Flip

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted; escalate to L if service/agent/docs imports require broad migration)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-6-final-sdk-rule-flip.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- Predecessor slices:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.
  - T5.3 Explanation Envelope + Live Row Resolver archived at `ba5e5c26`; feature anchor `53551cb6`.
  - T5.4 Row Close + Manual Explain Closed-Head Gate archived at `7464c3e3`; feature anchor `c820f102`.
  - T5.5 Why-Not Fold + Legacy Evidence Quarantine archived at `ec45f12f`; feature anchor `5113e13d`.

## 0. Scope Locks

### In scope

- Flip SDK top-level `Rule` to the application protocol `Rule`:
  - `from factgraph.sdk import Rule`;
  - `sdk.Rule is factgraph.application.protocol.Rule`;
  - `isinstance(obj, factgraph.application.protocol.Rule)` remains the meaningful runtime check.
- Keep `ApplicationRule` as a transition alias:
  - `sdk.ApplicationRule is sdk.Rule`;
  - `ApplicationRule` remains only to ease T1-T4 migration;
  - new tests and narrow docs should prefer `Rule`.
- Remove `LegacyRule` from the SDK top-level public namespace:
  - no `LegacyRule` in `factgraph.sdk.__all__`;
  - no `hasattr(factgraph.sdk, "LegacyRule")` after the flip;
  - legacy DSL class may remain importable from `factgraph.sdk.dsl` until T5.7.
- Ensure legacy DSL `Rule` no longer owns SDK top-level `Rule`:
  - `factgraph.sdk.dsl.Rule` remains a legacy internal/transition implementation class;
  - top-level `sdk.Rule` is not `factgraph.sdk.dsl.Rule`;
  - tests assert legacy construction through top-level `Rule` no longer works as old DSL construction.
- Keep `Inference` named and exported as-is.
- Update runtime-facing error messages and tests that currently call the application protocol object `ApplicationRule` where D24 requires final `Rule` naming.
- Add focused import-identity and public namespace tests.
- Preserve all T5.1-T5.5 result/evidence/explain behavior.

### Out of scope

- Full D23 legacy shell deletion.
- Removing `Inference`.
- Removing `factgraph.sdk.dsl.Rule` from its module.
- Removing `build_application_rule(...)` or `DSLToApplicationRuleError`.
- Service route changes.
- OpenAPI changes.
- Broad public docs/examples migration.
- Final SDK docs rewrite; T5.7 owns broad docs migration after D23 hard-cut.
- T5.1-T5.5 DTO/evaluate/explain/close/why-not behavior changes.
- C73-C78 adapter or Semantics Lite work.
- Introducing `HeadRule`, `EvalRule`, or another public Rule class name.

### M-to-L triggers

Pause and amend/split if implementation requires:

- touching `src/service/`, `src/agent/`, OpenAPI, broad docs/examples, or notebooks;
- deleting legacy shells or `what_if.*` surfaces;
- changing T5 evaluate/explain runtime behavior rather than only import/name behavior;
- changing application protocol `Rule` validation, equality, hashing, content digest, projection, or closed-head behavior;
- changing `Inference` semantics;
- editing adapters or SemanticsProfile implementation;
- preserving top-level `LegacyRule` as a hidden compatibility lane.

## 1. Inputs

D24 locks the final naming contract:

- SDK top-level `Rule` becomes the application protocol `Rule`.
- `ApplicationRule` may survive only as a transition alias to the same class.
- Top-level `LegacyRule` is not a final public alias and is a D23 hard-cut target.
- Legacy DSL `Rule` may remain module-local during migration but must not own the SDK top-level name.
- `Inference` remains the derivation authoring class name unless D23 later deletes the legacy input path.
- Runtime checks compare application protocol `Rule` type identity, not alias names.
- Public docs migration consumes D24 and D23 together; T5.6 may add only narrow naming/docstring changes.

Stage 3 synthesis places T5.6 after T5.5 and before T5.7, so T5.7 can perform broad hard-cut/docs migration with final SDK names available.

Pre-draft shipped-source reads found:

- `src/factgraph/sdk/__init__.py` currently imports `Rule` from `.dsl`, aliases `.dsl.Rule` as `LegacyRule`, and aliases application protocol `Rule` as `ApplicationRule`.
- `tests/sdk/test_rule_naming.py` currently asserts the pre-D24 state: `sdk.Rule is dsl.Rule`, `sdk.LegacyRule is dsl.Rule`, and top-level legacy construction still works.
- T5 evaluate tests already reject legacy SDK Rule objects as `head=` values, so the runtime has mostly moved to application protocol `Rule`.
- T5.1-T5.5 public DTOs and evidence APIs already re-export from `factgraph.sdk` and must remain unchanged.

## 2. Plan

### 2.1 Flip SDK top-level imports

Update `src/factgraph/sdk/__init__.py` so:

```python
from factgraph.application.protocol import Rule
ApplicationRule = Rule
```

or equivalent identity-preserving imports.

The legacy DSL import block must not bind `.dsl.Rule` to top-level `Rule`.

Expected final public namespace:

```python
sdk.Rule is factgraph.application.protocol.Rule
sdk.ApplicationRule is sdk.Rule
sdk.Inference is factgraph.sdk.dsl.Inference
```

### 2.2 Remove top-level `LegacyRule`

Remove `LegacyRule` from `factgraph.sdk.__all__` and from top-level module attributes.

Keep these legal until T5.7:

```python
import factgraph.sdk.dsl as dsl
dsl.Rule
```

Do not delete the legacy class or its DSL module in T5.6.

### 2.3 Keep `Inference` stable

`Inference` remains exported from `factgraph.sdk` and still refers to `factgraph.sdk.dsl.Inference`.

T5.6 must not rename it and must not decide whether T5.7 keeps or removes the legacy Inference input path.

### 2.4 Update focused tests

Update or replace `tests/sdk/test_rule_naming.py` so it asserts:

- `sdk.Rule is factgraph.application.protocol.Rule`;
- `sdk.ApplicationRule is sdk.Rule`;
- `sdk.Rule is not factgraph.sdk.dsl.Rule`;
- `LegacyRule` is not in `sdk.__all__` and not available as a top-level SDK attribute;
- `dsl.Rule` remains available as the legacy class until T5.7;
- `Inference` remains exported;
- `build_application_rule(...)` still returns `sdk.Rule` / application protocol `Rule`;
- top-level legacy construction through `sdk.Rule(...)` rejects legacy DSL keyword shape instead of producing `.dsl.Rule`.

### 2.5 Update runtime messages only where local and necessary

If focused tests find user-facing messages that still say `ApplicationRule` for T5 public APIs, update narrow strings to "application Rule" or "Rule" per D24.

Do not perform broad docs/examples rewrite in T5.6.

### 2.6 Preserve T5.1-T5.5 behavior

Run focused preservation suites for:

- T5.1 DTO/digest/export tests;
- T5.2 evaluate return-shape tests;
- T5.3/T5.4 row/manual explain tests;
- T5.5 why-not quarantine tests;
- G7 preservation.

## 3. Code Changes

Likely files:

- `src/factgraph/sdk/__init__.py`
  - flip `Rule` binding;
  - keep `ApplicationRule` alias to the same object;
  - remove top-level `LegacyRule`;
  - keep `Inference`.
- `tests/sdk/test_rule_naming.py`
  - rewrite pre-D24 assertions to post-D24 expectations.

Potential narrow files if grep demands:

- `tests/sdk/test_rule_expr_evaluate.py`
  - update wording expectations if the final naming changes error messages.
- `tests/application/protocol/test_rule_expr.py`
  - only if import identity expectations need adjusting.

Files explicitly out of target scope unless amended:

- `src/service/`;
- `src/agent/`;
- `docs/api/openapi.yaml`;
- broad docs/examples/notebooks;
- adapters;
- application protocol Rule implementation;
- T5 DTO/evaluate/explain/why-not implementation files except import-facing tests.

## 4. Tests

Minimum focused tests:

1. `sdk.Rule is factgraph.application.protocol.Rule`.
2. `sdk.ApplicationRule is sdk.Rule`.
3. `sdk.Rule is not factgraph.sdk.dsl.Rule`.
4. `LegacyRule` is absent from `sdk.__all__`.
5. `factgraph.sdk.LegacyRule` is absent.
6. `factgraph.sdk.dsl.Rule` remains importable until T5.7.
7. `sdk.Inference is factgraph.sdk.dsl.Inference`.
8. `sdk.build_application_rule(...)` returns `sdk.Rule`.
9. Legacy DSL construction through top-level `sdk.Rule(...)` no longer creates a legacy DSL object.
10. T5 evaluate/explain tests remain green.
11. T5.5 why-not quarantine tests remain green.
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

Expected inherited baseline: 170 tests OK from T5.5 archive.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Existing tests still assume pre-D24 `sdk.Rule` legacy meaning. | Update tests to D24 final state and keep `dsl.Rule` as the explicit legacy path until T5.7. |
| Hidden code branches on top-level `sdk.Rule` for legacy detection. | Step 4.6 grep for `LegacyRule`, `ApplicationRule`, `sdk.Rule`, `.dsl.Rule`, and constructor shape. |
| `LegacyRule` removal leaks into D23 hard-cut deletion. | Remove only top-level export/attribute; keep `.dsl.Rule` and legacy shells intact. |
| Docs migration leaks into T5.6. | Limit to narrow comments or test docstrings; T5.7 owns broad docs. |
| Service/agent imports depend on top-level legacy `Rule`. | Step 4.6 classifies as possible L trigger and may amend/split. |
| Application protocol Rule behavior changes accidentally. | Do not edit protocol `Rule`; run G7 and focused T5 suites. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates T5.6 implements D24 only, not D23 deletion.
- Reviewer validates `ApplicationRule` transition alias survives.
- Reviewer validates `LegacyRule` removal is top-level only.

### Step 4.6 grep gate

Before scoped:

- search SDK namespace exports and `__all__`;
- search `LegacyRule`, `ApplicationRule`, `sdk.Rule`, `.dsl.Rule`;
- search service/agent/docs/OpenAPI dependencies;
- search error messages that mention `ApplicationRule`;
- record whether class remains M or escalates.

### G7 baseline gate

After scoped:

- run inherited G7 preservation command;
- expected baseline is 170 tests OK;
- record pytest deferred and `tests.test_public_inference_factgraph_create` exclusion.

### Feature gate

Run:

- focused SDK rule naming tests;
- T5.1-T5.5 focused preservation tests;
- G7 preservation;
- touched-file ruff;
- `git diff --check`.

Pytest remains deferred per existing SIGSEGV environment lock unless environment constraints change.

## 7. Rollback

Rollback must preserve T5.1-T5.5 behavior:

- If import flip breaks too much hidden code, revert `sdk/__init__.py` and naming tests together.
- Do not partially restore `LegacyRule` as a top-level alias while leaving `Rule` flipped.
- Do not touch service/docs/OpenAPI during rollback.
- Do not revert T5 evaluate/explain/why-not commits.
- Do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.6 may update narrow import-facing comments or test docstrings.

Deferred:

- broad public docs/examples/OpenAPI migration remains T5.7;
- final legacy shell deletion remains T5.7;
- optional Semantics Lite remains T5.8.

## 9. Reviewer Focus

- Does `Rule` now clearly mean application protocol Rule?
- Does `ApplicationRule` survive only as a transition alias?
- Is `LegacyRule` removed only from top-level SDK public namespace, not deleted from `.dsl`?
- Is `Inference` untouched?
- Are service/docs/adapter boundaries preserved?

## 10. Outcome

Pending implementation.
