# Audit: T11.2.9 Match Runtime Implementation

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t11-2-9-match-runtime-implementation.md`
- Stage: draft
- Class: M/L (runtime + tests + user docs; may narrow after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T11.2.9 blueprint pair drafted | Triggered by user selecting N9 after T11.2.7 match design and T6 evidence design were published. |

## 2. Pre-Draft Source Scan

Read-only draft scan findings:

- `match-api-design.zh.md` commitments M1-M21 lock the target runtime shape:
  `fg.read.match(EntityCls, template, **kwargs) -> tuple[EntityCls snapshot, ...]`.
- `_SDKReadManager` currently exposes `get`, `find`, and `ref`, but no `match`
  method (`src/factgraph/sdk/store.py` read namespace).
- `SDKStore.find(...)` rejects method-level `view=` with the T11.1 attach hint
  and delegates to `sdk_find(...)`; match should mirror that rejection style.
- `sdk_find(...)` and snapshot hydration live in `src/factgraph/sdk/facade.py`;
  Step 4.6 must decide whether match reuses those helpers or lower-level
  entity-view DTO helpers.
- Application `Rule` carries `ports` and inferred `_port_types`; legacy `Query`
  still exists but is not the v0.2 match template.
- RuleExpr has existing join/lowering/inspect substrate, but draft did not yet
  verify whether it is enough for direct read-side matching.

## 3. Step 4.6 Inventory Results

Pending. The scoped pass must fill the table below with file:line references.

| # | Item | Result |
|---|---|---|
| 1 | SDK read namespace call chain | pending |
| 2 | Snapshot hydration path | pending |
| 3 | Rule ports / `_port_types` projection data | pending |
| 4 | RuleExpr lowering / inspect support | pending |
| 5 | SDK Field descriptor validation path | pending |
| 6 | Legacy Query runtime reuse / non-reuse | pending |
| 7 | Pattern connectivity algorithm data sources | pending |
| 8 | View-scoped attach read path | pending |
| 9 | Error taxonomy and message lock | pending |
| 10 | Test matrix | pending |
| 11 | User docs update set | pending |
| 12 | Release-facing docs/deferred language update set | pending |
| 13 | Stop-amend findings and final class | pending |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| RuleExpr matching needs broad new runtime | Could escalate from M/L to L | Inspect existing lowering/join data before implementation. |
| Connectivity check cannot see all effective vars | M21 safety invariant would be under-specified | Prototype/check data sources before coding. |
| F-expression kwargs cannot be represented without mutating Rule | Violates M15 | Confirm synthetic constraint strategy. |
| View-scoped match reads current head by accident | Violates T11.1 | Use attach-view tests and source inspection. |
| Docs overclaim witness/query persistence | User-facing confusion | Keep docs scoped to shipped tuple snapshots. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Runtime scope accepted or amended.
- [ ] Test matrix accepted.
- [ ] Docs update scope accepted.
- [ ] Implementation reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending.
