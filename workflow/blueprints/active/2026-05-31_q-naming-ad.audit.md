# Q-NAMING-AD Blueprint Audit: Assertions naming polish + Persistence rename

- Blueprint: [2026-05-31_q-naming-ad.md](./2026-05-31_q-naming-ad.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-31 | draft | Blueprint created | Initial scope recorded covering Q-NAMING decision §4.2 Batch A (5 items) + §4.5 Batch D (2 items) as Phase 1 sub-slice. Branch `v0.2.0-blueprint-q-naming-ad-2026-05-31` forked from Q-NAMING adopt commit `f1a017ec`. Sacred Q-PR1 5-path 0-diff preserved at draft commit; sacred master `562c74195df4...` unchanged; dirty baseline preserved. |
| 2026-05-31 | draft (amended) | Step 4.2 review tightening | Codex Step 4.2 review surfaced 2 Required + 2 Recommended findings; all 4 applied in single doc-only amend commit. (P2-1) Removed `sdk/batch.py:1189 BatchHandle.save` from G6 / §5.2 / §7 / Step 7.5 — verified as batch commit alias (`save(obj, *, include_deps, meta) → BatchCommitResult` forwarding to `self.commit(...)`), NOT workspace persistence. Added to §3 N-list, §5.2 out-of-scope note, §6 invariants, and Step 4.3 mandatory preflight 2.b. (P2-2) Locked AD scope: does NOT rename or delete flat `SDKStore.explain_fact` / `.conflicts` at `sdk/store.py:3470` / `:3473`; only `_SDKAuditManager` namespace surface changes. Manager body rewires to call `_queries.*` directly or via private helper, NOT through `self._sdk.explain_fact(...)`. Added to §4 current context, §5.1 out-of-scope note, §6 invariants, Step 7.4, and Step 4.3 mandatory preflight 2.e. (P3-1) Added `core/store/__init__.py:14` + `:40` export rows to §5.1 `FrozenAssertionSet` rename scope. SDK `__init__.py` export status deferred to Step 4.3 preflight 2.c per current grep showing no direct hit. (P3-2) Corrected mandatory preflight wording from `branch_index → case_id` to `branch_index → case_index` (field-level, per Q-NAMING §4.3.4); expanded preflight 2.a to clarify deferred-to-B2 cascade relationship with Batch D workspace methods. |

## Decision Notes

### 2026-05-31 — Initial scope freeze rationale

- **Combining Batch A + Batch D**: justified by audit §9 recommendation ("Q-NAMING-A/D = smallest useful slice") and Q-NAMING §4.9 Phase 1 explicit pairing. Both batches are Yellow risk, public SDK surface only, no wire/persistence behavior change beyond method names.
- **Mandatory preflight finding identified**: §4.5 `branch_index → case_id` persistence pre-lock check must be a Step 4.3 preflight finding before scope-freeze (per Q-NAMING §4.5 user requirement). If a persistence blocker surfaces, Q-NAMING-AD scope is re-examined before scope-freeze.
- **Layer authority preserved**: SDK boundary changes only; core query helpers (`_queries.explain_fact`, `_queries.conflicts`) retain existing names and signatures per Q-NAMING §4.2 explicit permission. Blueprint §6 invariant + §3 N7 lock this.
- **Hard-cut per §4.8.1**: no aliases, no dual-emit, old names removed in same commit as new names introduced. Alpha release; no historical user protection burden.
- **`FrozenAssertionSet` dual rename**: scope explicitly includes both `core/store/database.py:75` and `sdk/store.py:135` (audit §2 feasibility note acknowledged "wider scope" is feasible; Q-NAMING §4.2 adopts the wider scope).
- **`strict=True` on every by-ids surface**: G3 + §5.1 enumerate two surfaces (top-level `sdk/store.py:456` + facade `sdk/facade.py:263`); Step 4.3 preflight must verify no third surface exists per audit §2 blocker 5.

### Cross-flip role assignment (per user 2026-05-31 directive)

- Step 4.1 blueprint draft → Claude (this commit)
- Step 4.2 review → Codex
- Step 4.3 preflight drafter → TBD (Claude or Codex; decided after Step 4.2)
- Step 4.4 preflight amendment → drafter of Step 4.3
- Step 4.6 scoped anchor → drafter
- Step 4.6.5 pre-impl grep → Codex (承接 implementation prep)
- Step 4.7 implementation → Codex
- Step 4.7 review → Claude
- Step 4.8 closure → Codex or Claude (per CADENCE no strict assignment)
- Step 4.9 archive → Codex or Claude
