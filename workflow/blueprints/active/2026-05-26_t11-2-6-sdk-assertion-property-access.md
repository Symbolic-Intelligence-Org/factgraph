# Task Blueprint: T11.2.6 SDK Assertion Property Access

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: S/M (predicted narrow SDK ergonomics slice)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t11-2-6-sdk-assertion-property-access.audit.md`
- Trigger: T11.2.5 classified the dirty `src/factgraph/sdk/facade.py` +
  `tests/test_sdk_assertion_record_set_view_filters.py` pair as release-relevant;
  T11.2.7 then decoupled match API design from `AssertionRecordSet`, leaving this
  pair as an independent SDK assertion ergonomics decision.

## 0. Scope Locks

### In scope

T11.2.6 decides and, if accepted after scoped review, lands the existing dirty
SDK assertion ergonomics pair as a deliberate v0.2 user-facing behavior:

1. **Property-style field assertion access**:
   - `snapshot.field("name").active` returns active `AssertionRecordSet`;
   - `snapshot.field("name").history` returns active + revoked history;
   - `snapshot.field("name").all` remains a history alias if accepted.
2. **Backward-compatible call form**:
   - `AssertionRecordSet.__call__() -> self` preserves
     `snapshot.field("name").active()` and `.all()` call sites.
3. **Assertion namespace field proxy**:
   - `snapshot.assertions.name` resolves to `snapshot.assertions.field("name")`
     when `name` is a schema field.
4. **Graph-level assertion helpers remain unchanged**:
   - `fg.assertions.by_id(...)`, `by_ids(...)`, `active()`, and `all()` retain
     their current shapes unless Step 4.6 explicitly scopes a docs-only wording
     clarification.
5. **Tests and docs**:
   - lock compatibility coverage for property + legacy call forms;
   - update narrow docs that teach assertion field access, if scoped inventory
     shows stale examples.

### Out of scope

- Match API implementation or any `fg.read.match(...)` runtime work.
- Any change to T11.2.7 `match-api-design.zh.md`.
- Release machinery / `scripts/release.sh`.
- Notebook namespace cleanup.
- Untracked `rainbird-ai sdk code/`.
- Broad quickstart rewrite outside assertion-access wording.
- New public DTOs.
- Service / OpenAPI changes.
- Changing assertion storage, ledger, view, read, or evaluate semantics.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

- `.active()` / `.all()` backward compatibility cannot be preserved;
- `AssertionNamespace.__getattr__` collides with manager methods or Python
  dunder/private attributes in a way that changes existing behavior;
- graph-level `fg.assertions.active()` / `.all()` would need property conversion
  to keep the API coherent;
- docs sync expands beyond assertion-access wording;
- any file outside the scoped pair + narrow docs must be edited;
- any dirty-baseline file other than the `facade.py` + companion test pair would
  be touched.

## 1. Problem

The SDK already exposes assertion-history helpers, but the surface is mixed:

- some newer docs and examples already show property-style access
  (`snap.field("name").active`);
- older docs still show method-style access (`.active()` / `.all()`);
- `snapshot.assertions.field("name")` is explicit but noisier than
  `snapshot.assertions.name` for common field names.

The standing dirty diff implements a small ergonomic move:

- make `FieldAssertions.active`, `.history`, and `.all` properties;
- preserve legacy call forms by making `AssertionRecordSet` callable and
  returning itself;
- add `AssertionNamespace.__getattr__` as a field-name proxy.

T11.2.7 confirmed this is independent of match API. T11.2.6 should therefore
decide whether to land it as a deliberate v0.2 assertion ergonomics feature, or
recommend user stash/revert before release.

## 2. Inputs

| Source | Role |
|---|---|
| `src/factgraph/sdk/facade.py` dirty diff | Candidate production behavior. |
| `tests/test_sdk_assertion_record_set_view_filters.py` dirty diff | Candidate compatibility test. |
| `workflow/blueprints/archive/2026-05-26_t11-2-5-dirty-baseline-triage.md` | Verdict source: facade/test pair is release-relevant and must land together or be stashed/reverted. |
| `workflow/design/design-points/active/match-api-design.zh.md` | Confirms match no longer returns `AssertionRecordSet`; facade ergonomics are independent. |
| `workflow/blueprints/archive/2026-05-10_assertion-selection-crud-ergonomics.md` | Precedent for `AssertionRecordSet` tuple-compatible helper surface. |
| `docs/official/kernel/quickstart/assertions.md` and `src/factgraph/sdk/docs/*.en.md` | Public docs that may need property/call-form sync. |

## 3. Draft Decisions To Lock

| # | Decision | Draft leaning |
|---|---|---|
| D1 | Property vs method final shape | Land property-style `.active`, `.history`, `.all`; preserve method call forms through callable `AssertionRecordSet`. |
| D2 | `.all` vs `.history` naming | Keep `.all` as history alias for compatibility; document `.history` as the clearer preferred name. |
| D3 | `AssertionRecordSet.__call__` lifetime | Treat as compatibility shim with no planned removal before v0.2 release; Step 4.6 should decide whether to call it permanent or deprecation-targeted. |
| D4 | `AssertionNamespace.__getattr__` proxy | Allow field-name attribute proxy only for schema fields present in `_field_map`; normal attributes and methods keep precedence. |
| D5 | Reserved / collision behavior | Existing methods (`field`, `active`, `all`, `by_id`, `by_ids`) win over same-named fields; users can always call `.field("...")`. Dunder/private names must not proxy. |
| D6 | Docs | Update only assertion-access docs: property preferred, legacy call form still accepted. |
| D7 | Release notes | Record as backward-compatible SDK assertion ergonomics: no storage, ledger, or matching semantic change. |

## 4. Expected Step 4.6 Inventory

The scoped commit must record:

1. exact dirty diff for `facade.py` and companion test;
2. current `FieldAssertions` / `AssertionRecordSet` / `AssertionNamespace`
   method/property shapes;
3. current graph-level `fg.assertions` manager shape and whether it should stay
   method-based;
4. reserved-name / collision list for `AssertionNamespace.__getattr__`;
5. docs grep for `.active()`, `.all()`, `.active`, `.history`, and
   `snapshot.assertions.field(...)`;
6. focused tests that already cover assertion record sets;
7. whether companion test is sufficient or needs more edge cases;
8. final verdict: land feature vs user stash/revert;
9. exact file set for implementation;
10. release-note wording and T11.3 handoff.

## 5. Expected Implementation Shape

If Step 4.6 confirms the draft leaning:

1. stage the existing `facade.py` + companion test changes;
2. add any missing focused tests for collision / compatibility behavior;
3. update narrow SDK / quickstart docs if stale call-form teaching remains;
4. run focused assertion tests;
5. record release-note language in blueprint closure, not necessarily in a
   changelog unless T11.3 owns release notes.

## 6. Verification Gates

- Focused tests for `tests/test_sdk_assertion_record_set_view_filters.py`.
- Any existing assertion-record-set suite identified during Step 4.6.
- Touched-file ruff clean for `src/factgraph/sdk/facade.py`.
- `git diff --check` clean.
- Dirty baseline: only `facade.py` and companion test are consumed by this
  cycle; remaining docs/notebooks/untracked reference stay untouched.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.

## 7. Acceptance

- [ ] Step 4.6 inventory completed with collision and docs-surface checks.
- [ ] Land/stash/revert verdict recorded.
- [ ] Backward compatibility for `.active()` / `.all()` verified.
- [ ] `AssertionNamespace.__getattr__` collision behavior verified.
- [ ] Narrow docs sync completed or explicitly not needed.
- [ ] Focused tests pass.
- [ ] No release machinery, match API, service, OpenAPI, notebook, or unrelated
      dirty-baseline files touched.
