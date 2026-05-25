# Task Blueprint: T5.1 DTO Foundation + Digest Harness

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-1-dto-foundation-digest-harness.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`

## 0. Scope Locks

### In scope

- Add application-protocol DTOs for `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, and `DetachedRowError` per D17 sections 4.1-4.8.
- Add SDK re-exports for those DTOs per D17 section 4.1.
- Add an internal CandidateSet-to-row conversion harness per D17 section 4.7 and D18 section 4.3, without wiring it into public `evaluate(...)`.
- Add D19 digest helpers for:
  - `run_id`, `result_id`, and `row_id`;
  - `Claim.digest`;
  - `EvidenceRef.ref_id`;
  - `EvidenceRef.closed_head_digest`;
  - `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, and `semantics_digest`;
  - private row digest and public `EvaluateResult.result_digest`.
- Add mandatory `view_snapshot_digest` substrate. T5.1 must not return a placeholder, wall-clock-derived value, schema-only fallback, or empty string.
- Add focused tests for DTO validation, SDK exports, digest determinism, row-id duplicate handling, `EvidenceRef.fact_digest == EvaluateRow.claim.digest`, and detached-row plumbing.

### Out of scope

- Public `evaluate(...)->EvaluateResult` return-shape flip; T5.2 owns that.
- Public `row.explain()` behavior or `Explanation`; T5.3 owns that.
- Public `row.close()` behavior or manual `fg.eval.explain(expr, head=closed_head, ...)`; T5.4 owns that.
- Public `.eval.why_not(...)` or why-not migration; T5.5 / D22 own that, and T5 Core intentionally adds no public why-not surface.
- SDK top-level `Rule` naming flip; T5.6 / D24 own that.
- Legacy SDK hard-cut, service routes, OpenAPI, and final docs migration; T5.7 / D23 own that.
- C73-C78 semantics implementation and adapter edits; T5.8 / D26 or a post-T5 cycle owns that.
- New public evidence, support, trace, or renderer DTOs beyond D17.
- Public `CandidateSet` compatibility surface, `evaluate_v2`, `result_shape=`, `return_candidates=`, or `as_candidates=`.

### M-to-L triggers

Escalate or split before implementation if T5.1 requires:

- broad store/runtime redesign to compute `view_snapshot_digest`;
- database migration or persistent schema changes;
- public `evaluate(...)` return-shape mutation;
- service-route, OpenAPI, or docs migration;
- adapter production edits;
- new public evidence graph schema;
- final SDK `Rule` flip;
- changing existing `Rule.content_digest` format or formula.

## 1. Inputs

T5 Stage 1 and Stage 2 closed the public result/evidence design layer. T5 Stage 3 synthesis assigns T5.1 as the first implementation slice: DTO Foundation + Digest Harness.

T5.1 consumes these locks:

- D17 owns DTO location, public field surfaces, live/detached row boundary, `CandidateSet` internal classification, and `EvidenceRef.fact_digest == EvaluateRow.claim.digest`.
- D18 owns the hard-cut policy but explicitly requires DTO and digest foundation before public return-shape flip.
- D19 owns digest formats, ID formulas, context digest separation, mandatory `view_snapshot_digest`, result digest acyclicity, and missing-source error behavior.
- D20/D21 reserve later `Explanation`, `row.explain()`, `row.close()`, and manual replay. T5.1 only provides detached resolver plumbing and digest anchors.
- D24 owns final SDK `Rule` naming. T5.1 must keep generic application head Rule terminology and must not change SDK top-level `Rule`.
- D25 owns semantics mismatch policy. T5.1 only adds `semantics_digest` helper using normalized `SemanticsProfile`.
- D26 keeps adapter-touching semantics work out of T5 Core by default.

Pre-draft shipped-source reads found:

- `src/factgraph/core/derivation/candidates.py` defines internal `CandidateSet` fields and candidate identifiers.
- `src/factgraph/core/protocol/digests.py` already provides `sha256_hex(...)` and `sha256_token(...)`.
- `src/factgraph/application/protocol/__init__.py` is the current application-protocol export index.
- `src/factgraph/sdk/__init__.py` is the current SDK export index and still owns pre-D24 `Rule` / `LegacyRule` / `ApplicationRule` behavior.
- `src/factgraph/core/store/database.py` already has `view_digest_for(...)` and database view-digest substrate.
- `src/factgraph/core/semantics/profile.py` defines the normalized `SemanticsProfile` fields required by D19.
- `src/factgraph/sdk/store.py` has public semantics lowering helpers that can provide normalized profiles for future evaluation paths.

## 2. Plan

### 2.1 Add application-protocol DTO module

Implement the DTOs in the application protocol layer, likely as a new focused module such as:

- `src/factgraph/application/protocol/evaluate_result.py`

The exact module name is implementation-owned, but exports must be available from:

```python
from factgraph.application.protocol import EvaluateResult, EvaluateRow, Claim, EvidenceRef, DetachedRowError
from factgraph.sdk import EvaluateResult, EvaluateRow, Claim, EvidenceRef, DetachedRowError
```

No new top-level `factgraph.eval` package is introduced in T5.1.

### 2.2 DTO field contracts

`Claim`:

- fields: `kind`, `name`, `arguments`, `repr`, `digest`;
- distinct from `src/factgraph/core/store/ledger.py` storage-layer `Claim`;
- `digest` produced by D19 helper:
  - `sha256_token(canonical("evaluate_claim_v1", kind, name, arguments))`.

`EvidenceRef`:

- fields: `ref_id`, `result_id`, `row_id`, `fact_digest`, `closed_head_digest`;
- invariant:
  - `row.evidence_ref.fact_digest == row.claim.digest`;
  - `row.evidence_ref.row_id == row.row_id`;
  - `row.evidence_ref.result_id == result.result_id` once attached to a result.

`EvaluateRow`:

- fields:
  - `row_id`;
  - `bindings`;
  - `claim`;
  - `raw_kind`;
  - `bound`;
  - `evidence_ref`;
  - private `_result_resolver`;
- no `status` field;
- no direct row-lineage field;
- `_result_resolver` is non-data plumbing and must be excluded from equality, hashing, repr, serialization, and digests;
- T5.1 must not add public `row.explain()` or `row.close()` methods. It may add a private live-result helper used by later slices:
  - detached helper calls raise `DetachedRowError`;
  - live helper calls return the owning result through `_result_resolver`.

`EvaluateResult`:

- fields:
  - `result_id`;
  - `run_id`;
  - `rows`;
  - `head`;
  - `engine`;
  - `engine_version`;
  - `adapter_version`;
  - `expr_digest`;
  - `rule_set_digest`;
  - `view_snapshot_digest`;
  - `semantics_digest`;
  - `evaluated_at`;
  - `result_digest`;
- container behavior:
  - `__iter__`;
  - `__len__`;
  - `__getitem__`;
  - `first()`;
  - `exists()`;
  - `count()`;
- result construction must bind row resolvers so rows obtained from the result are live.

`DetachedRowError`:

- public DTO-layer exception for detached row method calls;
- no new closed-head or explanation-specific error subclass in T5.1.

### 2.3 Digest harness

Add central helpers for the D19 formulas. The implementation may place them in the new DTO module or a private protocol helper module, but there must be one authoritative helper path for each formula.

Required helpers:

- canonical serialization helper for deterministic bytes;
- `new_run_id()` or equivalent public-evaluation invocation id helper;
- `result_id_for(...)`;
- `row_id_for(run_id, bindings)`;
- `claim_digest_for(kind, name, arguments)`;
- `closed_head_digest_for(closed_head)` or `closed_head_digest_for_parts(id, content_digest)`;
- `evidence_ref_id_for(result_id, row_id, fact_digest, closed_head_digest)`;
- private `row_digest_for(row)`;
- `result_digest_for(result fields, row_digests)`;
- `semantics_digest_for(profile_or_none)`;
- `view_snapshot_digest` helper or adapter over shipped store/database substrate.

Digest requirements:

- all new public `*_digest` fields use `sha256:<64 hex>` token format;
- public object ids use D19 prefixes such as `evalr_v1:` and `evref_v1:`;
- shipped `Rule.content_digest` remains bare hex and is embedded as named payload data, not reformatted;
- `evaluated_at`, live resolver state, Python object identity, `EvidenceRef.ref_id`, and private support artifacts do not enter `result_digest`;
- duplicate public `row_id` values in one `EvaluateResult` must collapse deterministically or raise before returning the result. T5.1 should choose the simpler deterministic behavior and test it.

### 2.4 Context digest helpers

`expr_digest`:

- for RuleExpr, digest lowered expression structure and source rule identity pairs `(rule.id, rule.content_digest)`;
- for legacy `Inference` / derivation dict, digest normalized compiled derivation plan shape;
- no rendered-expression string digest.

`rule_set_digest`:

- aggregate authoring rules by `(rule.id, rule.content_digest)`;
- `Rule.version` remains warning/documentation metadata and does not enter the digest;
- legacy inputs use pseudo-entry normalized compiled plan data.

`view_snapshot_digest`:

- mandatory for every future public `EvaluateResult`;
- database-backed views should use `view_digest_for(...)` substrate when available;
- in-memory SDK stores must compute a deterministic digest over visible facts plus schema context or raise an SDK/runtime boundary error;
- no placeholder fallback.

`semantics_digest`:

- `None` when no semantics profile participates;
- otherwise digest normalized core `SemanticsProfile` fields:
  - `name`;
  - `engine`;
  - `version`;
  - `engine_options`;
  - `uncertainty_projection`;
  - `temporal_projection`;
  - `rule_projection`;
  - `certainty_projection`;
  - `output_readback`;
  - `fallback`;
- compare profile content, not wrapper identity.

### 2.5 CandidateSet conversion harness

Add private conversion helpers that can map internal `CandidateSet` data into DTO building blocks without changing public evaluate output in T5.1.

The helper should encode D17 mapping principles:

- `CandidateSet.payload` becomes public `EvaluateRow.bindings` under application head Rule output column names;
- `CandidateSet.target`, derivation id/version, and head metadata may inform `Claim.kind`, `Claim.name`, and `Claim.arguments`;
- `CandidateSet.confidence` / `confidence_kind` may inform `raw_kind` / `bound`;
- support digest/kind and candidate identifiers stay private resolver/evidence lookup inputs;
- `CandidateSet.state` does not become `EvaluateRow.status`.

This helper remains internal and testable. Public `evaluate(...)` still returns the shipped shape until T5.2.

### 2.6 SDK re-export

Update SDK exports for the new DTOs only.

T5.1 must not:

- make SDK top-level `Rule` point to application protocol `Rule`;
- remove `LegacyRule`;
- remove legacy shells;
- rewrite final docs.

### 2.7 Error boundaries

T5.1 should use existing protocol validation patterns for malformed DTO field types and values.

Digest-source failures should be classified as SDK/runtime integration failures when they happen during conversion/harness use. T5.1 should not add a new public error subclass except `DetachedRowError`.

## 3. Code Changes

Expected production files:

- `src/factgraph/application/protocol/evaluate_result.py` or equivalent new module;
- `src/factgraph/application/protocol/__init__.py`;
- `src/factgraph/sdk/__init__.py`;
- possibly `src/factgraph/sdk/store.py` only for private digest substrate helpers, not public evaluate return shape;
- possibly a private helper module under `src/factgraph/application/protocol/` for canonical serialization / conversion helpers.

Expected tests:

- `tests/application/protocol/test_evaluate_result_dtos.py` or equivalent;
- `tests/application/protocol/test_evaluate_result_digests.py` or equivalent;
- optional SDK export test in `tests/sdk/`.

Files explicitly out of target scope:

- adapter production modules;
- service routes and OpenAPI;
- final docs migration;
- legacy hard-cut files;
- T4.3 inspect helper implementation, except for importing existing Rule data when computing closed-head digest helper inputs.

## 4. Tests

Minimum focused tests:

1. DTO validation rejects malformed `Claim`, `EvidenceRef`, `EvaluateRow`, and `EvaluateResult` field values.
2. SDK re-exports point at the application-protocol DTO classes.
3. `Claim.digest` is deterministic and uses `sha256:` token format.
4. `EvidenceRef.fact_digest == EvaluateRow.claim.digest` is enforced.
5. `EvidenceRef.ref_id` is deterministic and changes when row/result/fact/closed-head anchors change.
6. `row_id` is deterministic from `(run_id, bindings)` and excludes private support/resolver data.
7. Duplicate row ids in one `EvaluateResult` raise or collapse according to the chosen T5.1 behavior; public duplicate ids must not be returned.
8. `result_digest` is deterministic, acyclic, and unaffected by `evaluated_at` or live resolver state.
9. `semantics_digest_for(None) is None`; equivalent normalized `SemanticsProfile` values produce the same digest.
10. `view_snapshot_digest` helper uses real substrate or raises; it never emits placeholder / empty / wall-clock-only value.
11. Detached rows keep data fields readable and raise `DetachedRowError` through the private live-result helper; public `row.explain()` / `row.close()` remain absent until T5.3/T5.4.
12. Private CandidateSet conversion helper maps payload/bindings and keeps CandidateSet identifiers out of public row fields.

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

Expected inherited baseline: 163 tests OK from T4.3 final preservation gate.

## 5. Risks

| Risk | Mitigation |
|---|---|
| `view_snapshot_digest` substrate is broader than expected. | Keep T5.1 M only if a deterministic digest can be built from existing store/database substrates; otherwise amend/split before feat. |
| DTO helper accidentally flips public evaluate output. | Step 4.6 grep public evaluate callers; keep conversion helper private until T5.2. |
| `CandidateSet` leaks into public DTO fields. | Tests inspect bindings/claim/evidence fields and forbid candidate ids/support artifacts as public values. |
| Digest formulas duplicate across modules. | Centralize helper path; tests import the intended helper path. |
| T5.1 preempts D20/D21 by adding real row methods. | Only detached/live plumbing is allowed; real explanation and close behavior remain later slices. |
| T5.1 preempts D24 naming. | Keep SDK `Rule` exports untouched; add only DTO re-exports. |
| Evidence-tree internal schema leaks into public DTOs. | T5.1 only uses D17/D19 DTO/digest contracts; internal EvidenceGraph schema is D20/future cycle. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates T5.1 scope against D17/D19 and Stage 3 synthesis.
- Reviewer validates no T5.2/T5.3/T5.4/T5.6/T5.7/T5.8 work is planned.

### Step 4.6 grep gate

Completed in the paired audit. Results were clean / expected; no A-fallback amendment was required.

### G7 baseline gate

After scoped, run the inherited G7 preservation command and record the 163 OK baseline before feature code.

### Feature gate

Run:

- G7 preservation command;
- focused DTO/digest tests;
- SDK export tests;
- touched-file ruff for production and tests.

Pytest remains deferred per existing SIGSEGV environment lock unless the environment constraint changes. `tests.test_public_inference_factgraph_create` remains excluded from the G7 command per prior preservation gates.

## 7. Rollback

Rollback is documentation-first until feat:

- draft / scoped / baseline commits can be amended by follow-up blueprint commits;
- feature rollback should revert only T5.1 DTO/digest files and tests, leaving T5 Stage 1-3 design artifacts intact;
- do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.1 does not perform final public docs migration.

Allowed docs changes in feat:

- narrow API reference or inline comments only if needed for DTO test clarity.

Deferred docs:

- public evaluate return-shape docs to T5.2;
- Explanation docs to T5.3/T5.4;
- final SDK Rule naming docs to T5.6;
- hard-cut docs/service/OpenAPI migration to T5.7.

## 9. Reviewer Focus

- Is `view_snapshot_digest` scoped tightly enough to remain T5.1 M-class?
- Are DTO fields aligned with D17 and not overfitted to current `CandidateSet` internals?
- Do digest helpers follow D19 without reformatting shipped `Rule.content_digest`?
- Does the CandidateSet conversion helper remain internal and non-public?
- Are row resolver / detached semantics sufficient for T5.1 without implementing T5.3/T5.4?
- Are SDK exports limited to DTOs and not D24 Rule naming?
- Are adapter/service/docs/hard-cut changes fully locked out?

## 10. Outcome

Pending implementation.
