# Task Blueprint: T11.2 Cross-doc Metadata Unblock

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: L (predicted release-blocker documentation / tests / metadata decision slice; may narrow to M after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t11-2-cross-doc-metadata-unblock.audit.md`
- Roadmap source: `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` §3.7, §4.1, §5, §6, §7

## 0. Scope Locks

### In scope

T11.2 is the formal unblock slice for the Database/view cross-doc seams named by
the roadmap as "S1-S6 / I10-A10". The preliminary read-only inventory found that
the active design note does not use literal `S1`-`S6` markers; the relevant
source is `database-view-fg-layered-architecture.zh.md` §16 `Step 1` through
`Step 6`, plus invariant `I10` and acceptance `A10`.

This slice may include:

1. **Step 1-6 status classification** against shipped source:
   - Step 1 durable view anchor fields.
   - Step 2 view consumers.
   - Step 3 evaluate / evidence metadata.
   - Step 4 `DatabaseValue` / snapshot identity.
   - Step 5 `Database.open/create` and `FactGraph.attach`.
   - Step 6 scoped-runtime hardening.
2. **I10 / A10 metadata decision**:
   - decide whether shipped `view_snapshot_digest` is the v0.2 formal bridge for db/view metadata;
   - or decide that exact public fields (`db_id`, `tx_id`, `schema_digest`, `data_digest`, optional `view_digest`) are release-required.
3. **Release-required doc alignment**:
   - official Database quickstart contradictions;
   - core store docs stale "view-scoped attach is future" wording;
   - SDK docs stale "view-scoped attach is future" wording;
   - any evaluate/evidence doc wording that overclaims method-level `view=` or underclaims attach-based view scope.
4. **Tests only when needed to lock shipped invariants**:
   - view-scoped attach coverage already exists, but Step 4.6 must determine whether metadata tests need strengthening;
   - if no new behavior is implemented, tests should only prove currently shipped metadata contracts.
5. **Design-point updates**:
   - record which Step 1-6 items are shipped, partially shipped, or v2 deferred;
   - record the I10/A10 decision so release docs do not make inconsistent claims.

### Out of scope

- Method-level `view=` consumer implementation for `read`, `evaluate`, or `explain`.
- New production behavior unless Step 4.6 explicitly finds an already-shipped invariant lacks a test.
- Adding public metadata fields to `EvaluateResult`, `Explanation`, or `EvidenceGraph` without a Step 4.6 escalation / split decision.
- Service route or OpenAPI schema changes unless Step 4.6 decides exact I10/A10 public fields are release-required.
- `Database.as_of(...)` / snapshot attach.
- Schema migration / schema digest canonicalization.
- Adapter changes.
- Release machinery, changelog, packaging, CI, or publish flow (T11.3).
- Dirty-baseline files.
- Push; push requires a separate single-use authorization.

### Stop / amend triggers

Pause and amend if Step 4.6 finds:

- exact I10/A10 metadata fields must be added to public DTOs for v0.2 release;
- service/OpenAPI changes are required for release consistency;
- any required test cannot be written without production behavior changes;
- method-level `view=` must be implemented rather than documented as deferred;
- Database `as_of(...)` or snapshot attach is required to unblock release docs;
- any change touches dirty-baseline files.

## 1. Problem

T11.1 shipped attach-based view scope: durable `db.create_view(...)` objects can
be consumed through `FactGraph.attach(db, view=view)`, and view-attached runtimes
are read-only. That closed the main "view can be created but not consumed" gap.

The remaining release risk is cross-doc consistency:

- the database-view design still describes a broader Step 1-6 plan, including
  method-level `view=` and snapshot attach;
- I10/A10 require evaluate/evidence metadata to record database snapshot and
  optional view context;
- shipped public DTOs currently expose `view_snapshot_digest`, not the full
  five-field db/view tuple;
- some docs still claim view-scoped attach is future, while other docs now teach
  it as shipped.

T11.2 decides and records the v0.2 contract, fixes release-facing doc
contradictions, and adds only the tests needed to prove the final claim.

## 2. Inputs

| Source | Purpose |
|---|---|
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | Names T11.2 as release-blocker candidate and identifies S1-S6 / I10-A10 seam. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` | Primary design source: §16 Step 1-6, I10, A10, §12 method-level view, §13 stale/scope validation. |
| `workflow/blueprints/active/2026-05-26_t11-1-attach-view-scope.md` | Predecessor attach-view implementation blueprint, currently still active. |
| `src/factgraph/sdk/store.py` | Shipped attach(view=...), method-level view rejection, view ledger filtering, view snapshot digest plumbing. |
| `src/factgraph/application/protocol/evaluate_result.py` | Shipped `EvaluateResult.view_snapshot_digest`, EvidenceGraph metadata copy, digest helper. |
| `tests/test_db_attach_lifecycle.py` | Shipped attach-view lifecycle tests. |
| `tests/application/protocol/test_evaluate_result_dtos.py` | Evidence metadata and DTO tests using `view_snapshot_digest`. |
| `tests/application/protocol/test_evaluate_result_digests.py` | `view_snapshot_digest_for_parts(...)` tests. |
| `docs/official/kernel/quickstart/database.md` | Official Database quickstart; preliminary inventory found an internal contradiction. |
| `src/factgraph/core/store/docs/README.md` | Core store implementation docs; preliminary inventory found stale future wording. |
| `src/factgraph/sdk/docs/README.md` | SDK docs entrypoint; preliminary inventory found stale future wording. |

## 3. Preliminary Inventory from Read-only Audit

Parfit completed a read-only inventory before this draft. Key findings:

| Marker | Current status | Draft implication |
|---|---|---|
| Step 1 durable view anchors | Shipped for durable Database views; SDK in-memory `FrozenAssertionView` remains two-field/session-local. | Document split clearly; no production change expected. |
| Step 2 view consumers | Attach-based view scope shipped in T11.1; method-level `view=` still rejects with hint. | Formalize attach-based-only v0.2; method-level `view=` v2 deferred. |
| Step 3 / I10 / A10 metadata | Shipped bridge is `view_snapshot_digest`; exact `db_id/tx_id/schema_digest/data_digest/view_digest` fields are not public DTO fields. | Main Step 4.6 decision. |
| Step 4 DatabaseValue | `Database.head()` shipped; `Database.as_of(...)` absent. | `head()` shipped, `as_of` deferred unless explicitly activated. |
| Step 5 attach API | Base attach + view attach shipped; snapshot attach absent. | Satisfied for view attach; snapshot attach deferred. |
| Step 6 hardening | View read/evaluate, stale/mismatch, and view metadata tests exist; metadata tests only cover `view_snapshot_digest`. | Add/adjust tests only if final metadata decision requires it. |
| Official Database quickstart | Intro says page does not introduce view-scoped reads/evaluation, later page teaches view-scoped attach. | Release-required doc fix. |
| Core store docs | Still say view-scoped attach is future. | Release-required doc fix. |
| SDK docs README | Still says view-scoped attach is future. | Release-required doc fix. |
| Service/OpenAPI | Service serializes `view_snapshot_digest`; OpenAPI does not expose exact db/view tuple. | Only in scope if exact I10/A10 fields become release-required. |

## 4. Proposed Shape

### 4.1 T11.2a Docs Formal Unblock

Minimal release-required doc fixes:

- official Database quickstart should consistently say attach-based view scope is shipped;
- core store docs should distinguish shipped view-attached runtime from future snapshot attach / method-level `view=`;
- SDK docs README should list view-scoped attach as shipped and method-level `view=` as deferred;
- evaluate/evidence docs should not claim exact db/view tuple fields unless the DTOs expose them.

### 4.2 T11.2b Metadata Decision

Step 4.6 must choose one:

1. **Bridge decision**: `view_snapshot_digest` is the v0.2 public metadata bridge.
   - Design I10/A10 becomes "satisfied for v0.2 by digest bridge; exact tuple remains v2/internal."
   - T11.2 remains docs/tests focused.
2. **Exact-field decision**: release requires explicit public fields.
   - Pause and amend / split into a broader DTO + service/OpenAPI slice before implementation.

The draft does not assume exact-field implementation.

### 4.3 T11.2c Tests if Needed

If the bridge decision stands, tests should remain focused:

- preserve existing `view_snapshot_digest_for_parts(...)` behavior;
- prove `EvaluateResult.view_snapshot_digest == view.view_digest` for view-attached evaluation, if not already clear;
- prove EvidenceGraph metadata copies `view_snapshot_digest`;
- avoid changing public DTO shape.

If exact fields are required, this becomes L-class implementation and needs a
new acceptance table before coding.

## 5. Step 4.6 Inventory Plan

Before implementation, record:

1. Exact locations of database-view §16 Step 1-6, I10, and A10.
2. Per-step shipped status: shipped, partial, v2 deferred, or release-blocking.
3. Exact `EvaluateResult` / `EvidenceGraph` metadata fields and tests.
4. Whether `view_snapshot_digest` can be accepted as the v0.2 bridge for I10/A10.
5. Doc contradiction list with file/line anchors.
6. Whether service/OpenAPI docs must change under the chosen metadata decision.
7. Whether any production code is required; if yes, stop and amend.
8. Dirty baseline verification.

## 6. Verification Gates

- `git diff --check` clean.
- No dirty-baseline files touched.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- If tests are touched, run focused tests and G7 baseline as scoped by audit.
- If docs only, record why tests were not required or run focused metadata tests as smoke.
- Final docs must not simultaneously claim:
  - view-scoped attach is future; and
  - view-scoped attach is shipped.
- Final docs must not imply method-level `view=` is shipped.

## 7. Risks

| Risk | Mitigation |
|---|---|
| I10/A10 exact-field interpretation silently expands public DTOs | Step 4.6 metadata decision is mandatory before implementation. |
| Docs fix overclaims method-level `view=` | Keep attach-based-only v0.2 language and v2 deferred note. |
| Release docs hide service/OpenAPI inconsistency | Include service/OpenAPI inventory and only defer with explicit rationale. |
| Tests are added for behavior not shipped | Tests must lock shipped behavior or trigger amend. |
| T11.2 becomes release machinery | Defer packaging/changelog/CI to T11.3. |

## 8. Acceptance

- [ ] Step 4.6 inventory classifies Step 1-6, I10, and A10.
- [ ] Metadata decision recorded: bridge accepted or exact-field split triggered.
- [ ] Release-facing docs no longer contradict shipped attach-based view scope.
- [ ] Method-level `view=` and `Database.as_of(...)` remain explicitly deferred unless a later blueprint activates them.
- [ ] Any tests added are focused on shipped metadata/view-scope behavior.
- [ ] No production code changes unless Step 4.6 explicitly amends scope.
- [ ] Dirty baseline and sacred master preserved.

