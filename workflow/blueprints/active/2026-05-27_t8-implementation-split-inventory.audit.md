# Audit: T8 Implementation Split Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-implementation-split-inventory.md`
- Stage: draft
- Class: S/M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8 split inventory blueprint pair drafted | Triggered after T7 evidence audit/rendering bridge shipped and user selected T8 planning before T8-A runtime. |

## 2. Draft Source Scan

Read-only draft scan findings:

- `evidence-tree-rainbird-style-v1.zh.md` §15.2 already proposes four T8
  slices: T8-A Validator + metadata foundation, T8-B Native/Souffle success
  topology, T8-C Engine enrichment, and T8-D Product/docs alignment.
- §15.3 recommends the first T8 implementation blueprint be T8-A only.
- T7 archived blueprint records a contract matrix and explicitly deferred T8-A
  central metadata sufficiency, T8-B topology, T8-C enrichment, and T8-D product
  docs.
- Current runtime has evidence DTOs, metadata writer, renderer, docs, and tests,
  so Step 4.6 must quantify boundaries against shipped code rather than
  redesigning the split from scratch.

This draft scan is not a Step 4.6 answer. It intentionally avoids answering
Q1-Q9 before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Does §15.2's four-slice proposal still hold after T7? | Pending Step 4.6. |
| Q2 | How do T7 §4.2 contract rows map to T8 slices? | Pending Step 4.6. |
| Q3 | What is T8-A's real code boundary? | Pending Step 4.6. |
| Q4 | Does T8-A need to split? | Pending Step 4.6. |
| Q5 | What is T8-B's real code boundary? | Pending Step 4.6. |
| Q6 | How does T8-C depend on T10? | Pending Step 4.6. |
| Q7 | What is the dependency graph? | Pending Step 4.6. |
| Q8 | Which D1-D20 items are triggered by each slice? | Pending Step 4.6. |
| Q9 | What durable output shape should this cycle produce? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| T8 split cycle starts implementation | Scope drift | Confirm no runtime/test/doc edits and choose planning-only output. |
| §15 proposal is treated as binding without re-inventory | Wrong implementation starting point | Re-map against T7 contract matrix and current runtime. |
| T8-A is too large for one cycle | Future cycle stalls | Quantify the four T8-A sub-items and split if needed. |
| T8-C starts before adapter semantics are ready | Adapter churn | Resolve T10 dependency shape. |
| D-series triggers are missed | Hidden future blockers | Map D1-D20 per slice. |
| Dirty baseline is accidentally edited | Workflow violation | Preserve baseline in status checks. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] Output shape selected.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / closure.
