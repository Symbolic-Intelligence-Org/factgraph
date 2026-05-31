# Q-NAMING-AD Blueprint Audit: Assertions naming polish + Persistence rename

- Blueprint: [2026-05-31_q-naming-ad.md](./2026-05-31_q-naming-ad.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-31 | draft | Blueprint created | Initial scope recorded covering Q-NAMING decision §4.2 Batch A (5 items) + §4.5 Batch D (2 items) as Phase 1 sub-slice. Branch `v0.2.0-blueprint-q-naming-ad-2026-05-31` forked from Q-NAMING adopt commit `f1a017ec`. Sacred Q-PR1 5-path 0-diff preserved at draft commit; sacred master `562c74195df4...` unchanged; dirty baseline preserved. |
| 2026-05-31 | draft (amended) | Step 4.2 review tightening | Codex Step 4.2 review surfaced 2 Required + 2 Recommended findings; all 4 applied in single doc-only amend commit. (P2-1) Removed `sdk/batch.py:1189 BatchHandle.save` from G6 / §5.2 / §7 / Step 7.5 — verified as batch commit alias (`save(obj, *, include_deps, meta) → BatchCommitResult` forwarding to `self.commit(...)`), NOT workspace persistence. Added to §3 N-list, §5.2 out-of-scope note, §6 invariants, and Step 4.3 mandatory preflight 2.b. (P2-2) Locked AD scope: does NOT rename or delete flat `SDKStore.explain_fact` / `.conflicts` at `sdk/store.py:3470` / `:3473`; only `_SDKAuditManager` namespace surface changes. Manager body rewires to call `_queries.*` directly or via private helper, NOT through `self._sdk.explain_fact(...)`. Added to §4 current context, §5.1 out-of-scope note, §6 invariants, Step 7.4, and Step 4.3 mandatory preflight 2.e. (P3-1) Added `core/store/__init__.py:14` + `:40` export rows to §5.1 `FrozenAssertionSet` rename scope. SDK `__init__.py` export status deferred to Step 4.3 preflight 2.c per current grep showing no direct hit. (P3-2) Corrected mandatory preflight wording from `branch_index → case_id` to `branch_index → case_index` (field-level, per Q-NAMING §4.3.4); expanded preflight 2.a to clarify deferred-to-B2 cascade relationship with Batch D workspace methods. |
| 2026-05-31 | draft (amended) | Step 4.4 preflight amendment | Step 4.3 preflight at `a0d2ba82` surfaced 1 Required + 2 Recommended findings (5 Verified + 1 Scoped-detail + 0 Abandonment within CADENCE healthy distribution); Codex Step 4.3 review pass at `a0d2ba82` with one PF-r2 wording 微修. All applied in single doc-only amend commit on blueprint branch (NOT preflight branch — per Slice 7B Option A learning). (PF-R1) Blueprint §5.4.1 added: asrt_id → (pred_id, e_ref, val_atoms) reverse-resolution mechanism specified as Option (a) private helper OR (b) `_queries.*` extension; choice is scoped-detail recorded at Step 4.7 closure §10; both options satisfy P2-2 and preserve `_queries` core signature per §4.2 + N7. (PF-r1) Blueprint §5.3.1 added: explicit pre-`set()` duplicate detection pattern with reference implementation. Applies to both `sdk/store.py:456` and `sdk/facade.py:263`. Default `strict=False` unchanged. (PF-r2) Blueprint §5.1 added SDK internal alias row: `DatabaseFrozenAssertionView` → `DatabaseFrozenAssertionSet` at `sdk/store.py:88` import alias **+ all internal references** (per Codex PF-r2 wording 微修, NOT a fixed-count specification; Step 4.6.5 pre-impl grep enumerates exact set). (P3 carry-forward) Decision Notes "Initial scope freeze rationale" stale `branch_index → case_id` corrected to `branch_index → case_index`; appended note that PF-v5 resolved the persistence pre-lock check positively. PF-v5 conclusion: workspace binary unaffected → B2 cascade does NOT block AD scope-freeze. Sacred Q-PR1 0-diff preserved through amend; master unchanged; dirty baseline preserved; preflight branch at `a0d2ba82` untouched. |
| 2026-05-31 | scoped | Preflight amendments and self-check passed | PF-R1 / PF-r1 / PF-r2 + P3 carry-forward covered by `18da88b9`. Step 4.5 self-check confirmed: PF coverage matrix (PF-R1=4 refs, PF-r1=2, PF-r2=2, PF-v2/v3/v5=1+, PF-s1=1; PF-v1/v4 content covered via P2-1/P2-2 references per CADENCE verified-findings convention); §5 节结构连续 (§5.1→§5.2→§5.3→§5.3.1→§5.4→§5.4.1→§5.5); no stale `case_id` outside historical-reference context; no fixed-count "5 uses" wording; sacred Q-PR1 5-path 0-diff preserved; sacred master untouched; dirty baseline preserved. Scope frozen; ready for Step 4.6.5 pre-impl grep (Codex承接) + Step 4.7 implementation on `v0.2.0-impl-q-naming-ad-2026-05-31`. |

## Decision Notes

### 2026-05-31 — Initial scope freeze rationale

- **Combining Batch A + Batch D**: justified by audit §9 recommendation ("Q-NAMING-A/D = smallest useful slice") and Q-NAMING §4.9 Phase 1 explicit pairing. Both batches are Yellow risk, public SDK surface only, no wire/persistence behavior change beyond method names.
- **Mandatory preflight finding identified**: §4.5 `branch_index → case_index` persistence pre-lock check must be a Step 4.3 preflight finding before scope-freeze (per Q-NAMING §4.5 user requirement). If a persistence blocker surfaces, Q-NAMING-AD scope is re-examined before scope-freeze. (Step 4.4 amend: corrected stale `case_id` wording from initial draft to match Q-NAMING §4.3.4 field-level rename `case_index`. Step 4.3 PF-v5 subsequently verified workspace binary does NOT serialize `branch_index`, so this preflight finding resolved positively — B2 cascade does NOT block AD scope-freeze.)
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
