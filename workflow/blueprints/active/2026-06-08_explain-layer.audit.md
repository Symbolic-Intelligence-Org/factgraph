# Audit Log: Explain + EvaluateResult Layer — Program Blueprint

- Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md)
- Status: draft

---

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-06-08 | blueprint created (draft) | Program blueprint created on `v0.2.0-blueprint-explain-layer-2026-06-08`. Design docs consolidated across 3 sessions into `explain-layer-complete-design.zh.md`. |
| 2026-06-08 | Q-D closed: Option A | User confirmed: matched schema predicate + wrong arity → reject; free-form head → query-style. Backward-compatible, prevents typo-silent widening. |
| 2026-06-08 | design docs committed @ `32c91983` | 8 files: `explain-layer-complete-design.zh.md` (new), `explanation-completion-roadmap.zh.md` (modified), 3 archived design-points (new/renamed), `rejected-alternatives-2026-06-08.md` (new), blueprint pair (new). Branch: `v0.2.0-blueprint-explain-layer-2026-06-08`. master unchanged @ `562c7419`. |
| 2026-06-08 | §10.0 lineage correction | source-read confirmed α/β/γ/ζ/δ all pre-blueprint shipped. Corrected §10.0 to reflect actual state; added Cleanup-β + Certainty as real remaining DTO items; Q-A re-opened (ClaimKind still has `fact_triple`), Q-B closed (δ already live), Q-C partially resolved. |
| 2026-06-08 | S2 child blueprint draft | Created `2026-06-08_explain-layer-s2-schema-ir-entity-repr.md` after source-read of schema compile, Schema IR validation, and runtime index code. S2 scope = canonical repr persistence + `render_entity_repr(...)`; atom rendering remains S4. |
| 2026-06-08 | S2 implemented | S2 implemented at `f13841b1`, then closed as implemented. Parent §10.1 updated to mark S2 complete; S3 is now unblocked on S2. |

---

## Decision Notes

### D-1: Parent blueprint pattern
**Decision**: This program blueprint is intentionally a parent/program-level blueprint. It does NOT go to `scoped` or `implementing`. Each child slice (`α/β/γ/ζ/δ` and `S0-S7`) requires its own separate child blueprint under `v0.2.0-blueprint-<slice>-<date>`.

**Rationale**: Single-blueprint multi-slice designs compound drift (see `feedback_smaller_batch_design_blueprints.md`). The parent locks the slice program and cross-cutting invariants; child blueprints lock per-slice scope and acceptance individually.

### D-2: Q-D Option A confirmed
**Decision**: δ slice query-style head semantics = Option A.
- `head.id` matches a known schema predicate but port count is wrong → reject (same behavior as today)
- `head.id` does not match any schema predicate (free-form) → query-style path (no arity check)

**Rationale**: Backward-compatible. Prevents a typo'd predicate name from silently entering query-style. Confirmed by user 2026-06-08.

### D-3: S0 as first implementable slice
**Decision**: `S0` (Rule.desc → Rule.repr alias migration) is the recommended first implementable slice.

**Rationale**: Zero dependency on DTO questions (Q-A/B/C) or query-style work (Q-D). Minimal blast radius. Can fork immediately from `v0.2.0-blueprint-explain-layer-2026-06-08` or directly from master.

### D-4: Program-level open questions gating
**Mapping**:
- **Q-A** (RowKind adjustment) must be resolved before α/γ child blueprints reach `scoped`
- **Q-B** (:exists auto-prepend behavior) must be resolved before δ child blueprint reaches `scoped`
- **Q-C** (deprecated alias lifetime) must be resolved before α/β/γ/ζ child blueprints reach `scoped`
- **Q-D** already resolved (Option A) — δ slice may proceed once γ is mature

### D-5: Design consolidation as program acceptance item
**Decision**: The program-level acceptance item "设计文档已 stage/commit" is the immediate next commit action. All other acceptances are per-slice.

**Files to stage**:
- `workflow/design/design-points/active/explain-layer-complete-design.zh.md`
- `workflow/design/design-points/active/explanation-completion-roadmap.zh.md`
- `workflow/design/design-points/archive/evidence-proof-model.zh.md`
- `workflow/design/design-points/archive/entity-repr-templates-and-inspect.zh.md`
- `workflow/design/design-points/archive/evaluate-result-flatten-and-query-style.zh.md`
- `workflow/design/design-points/archive/explain-layer-rejected-alternatives-2026-06-08.md`
- `workflow/blueprints/active/2026-06-08_explain-layer.md` (this blueprint)
- `workflow/blueprints/active/2026-06-08_explain-layer.audit.md` (this audit log)
