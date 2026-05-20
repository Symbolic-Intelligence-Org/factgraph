# Post-Q DB/View Audit Synthesis

- Date: 2026-05-20
- Branch: `v0.1-post-q-db-view-synthesis-2026-05-20`
- Source audit: `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
- Source audit commit: `6231f0cc`
- Scope: reclassify the DB/view audit drift inventory after all audit Q decisions closed.
- Non-scope: no blueprint, no implementation plan, no sibling-doc redraft, no memory update.

## 1. Inputs

This synthesis consumes the audit's final recommendation buckets and the 8 closed Q decision records.

### 1.1 Audit inputs

- Audit §9.2 lists the main drift inventory: identity, boundary, view shape, rules governance, physical layout, and evidence/evaluate metadata (`docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md:820`).
- Audit §9.3 maps Q1-Q8 blockers to those drift rows (`docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md:872`).
- Audit §9.4 lists cross-doc blocked items that remain independent of Q closure (`docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md:889`).
- Audit §9.5 lists design-deferred v2+ items that require no DB/view action today (`docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md:909`).
- Audit §9.6 lists projection / future-gate / conditional items with no independent action surface (`docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md:921`).

### 1.2 Closed Q decisions

| Q | Commit | Decision consumed by this synthesis |
|---|---:|---|
| Q1 | `13dde310` | `Database` is a new boundary above `Ledger`;strict Database v1 append-only API (`docs/decisions/2026-05-20_q1-database-class-boundary-decision.md:167`). |
| Q3 | `4ba11428` | Dedicated Database identity protocols for tx/data identity;assertion payload details closed by Q7 (`docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md:192`). |
| Q8 | `8be96760` | SavedRule persistence gradual deprecation;FileAuthoringRegistry class survives for schema transition (`docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md:274`). |
| Q7 | `ed1fd3d9` | Canonical durable 7-field assertion record with shipped adapters (`docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md:235`). |
| Q2 | `9b659a4b` | `FactGraph.attach(...)` is a new lifecycle with per-form read/write semantics (`docs/decisions/2026-05-20_q2-attach-lifecycle-decision.md:217`). |
| Q4 | `b2a16bb3` | `FrozenAssertionView` upgrades to anchored 6-field design-target DTO (`docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md:234`). |
| Q5 | `b932e675` | View-replaces-active;`view=` scope universe is exactly `view.asrt_ids` (`docs/decisions/2026-05-20_q5-view-revocation-composition-decision.md:225`). |
| Q6 | `917ada19` | Phased registry exit under Q8;schema-only transition until A20(E) (`docs/decisions/2026-05-20_q6-registry-workspace-migration-decision.md:200`). |

## 2. Classification Policy

After Q1-Q8 closure, each audit row falls into exactly one synthesis bucket:

- **Blueprint-eligible**: all blockers were internal Q decisions and those Qs are now closed. These rows can feed a DB/view blueprint, subject to normal scoped-blueprint workflow.
- **Cross-doc blocked**: still requires rule-expression or evidence-tree redraft. Q closure is necessary but not sufficient.
- **No independent action**: projection, release gate, or conditional row that should be folded into the parent blueprint rather than get its own blueprint.
- **Already aligned / keep**: shipped already satisfies design intent.
- **Deferred / v2+**: design defers the item and shipped does not accidentally implement it.

This synthesis intentionally does not decide blueprint batching. It only determines eligibility.

## 3. Blueprint-Eligible Drift

These rows were blocked only by Q1-Q8. With Q1-Q8 closed, they are eligible to become one or more DB/view blueprints.

### 3.1 Identity and canonical record substrate

| Rows | Q decisions now closed | Eligibility |
|---|---|---|
| I2, I11, A3, A12 (A+B+C) | Q1 + Q3 | Eligible. DatabaseValue identity, db_id creation/open round-trip, tx_id/data_digest protocols, and cross-process identity can be specified from Q1/Q3. |
| A13 (A+B) | Q3 + Q7 | Eligible. Canonical assertion identity and 7-field durable assertion record shape are now specified. |

**Boundary**: this is DB/view substrate work. It does not require rule-expression or evidence-tree redraft unless the blueprint tries to wire evaluate/evidence metadata.

### 3.2 Database boundary and attach lifecycle

| Rows | Q decisions now closed | Eligibility |
|---|---|---|
| I1 / A2-A | Q1 | Eligible. Database is a new boundary above Ledger;Ledger remains storage / compatibility machinery. |
| I4, I5, I6, A6 (A+B), I12 (A) | Q1 + Q2 + Q3 + Q4 | Eligible for DB/view runtime lifecycle scoping. Q2 locks attach form semantics;Q4 supplies view DTO shape;Q3 supplies tx_id. |

**Boundary**: implementing `fg.read.find(view=...)` or `fg.eval.evaluate(view=...)` remains cross-doc blocked (S1/S2). A DB/view blueprint may create substrate/runtime attach mechanics but must not claim sibling API semantics without redraft.

### 3.3 View shape, view identity, and view persistence

| Rows | Q decisions now closed | Eligibility |
|---|---|---|
| I3, A5 | Q4 | Eligible. `FrozenAssertionView` target shape is closed as anchored 6-field DTO. |
| I7, I8 | Q4 + Q5 | Eligible for DB/view scope semantics. Q5 locks view-replaces-active at scope layer. |
| A18 (A) | Q4 + Q3 | Eligible. View object persistence can use `view_digest` and assertion ids from Q4/Q3. |

**Boundary**: post-scope projection/materialization policy remains blueprint-level. The public `view=` API surfaces for `fg.read.find(...)` / `fg.eval.evaluate(...)` remain cross-doc blocked by S1/S2;view evidence/explain behavior remains cross-doc blocked by S3-S5.

### 3.4 Rules/workspace governance and registry migration

| Rows | Q decisions now closed | Eligibility |
|---|---|---|
| I12 (E) / A15-B | Q6 + Q8 | Eligible. Workspace registry migration mechanics are now closed as phased registry exit. |
| A11 SavedRule, A15 A-persisted, A20 (A)(B)(C)(D)(F), D9 | Q8 + Q6 | Eligible for deprecation/migration blueprinting. Q8 decides gradual SavedRule deprecation;Q6 decides workspace registry exit phases. |

**Boundary**: this work is migration/release governance, not Database identity work. It should not be mixed into the first substrate blueprint unless intentionally scoped as a separate migration child.

### 3.5 Physical layout and schema persistence

| Rows | Q decisions now closed | Eligibility |
|---|---|---|
| I13, A16 (B), A17 (A+B+C), A19, A20 (E) | Q1 + Q3 + Q4 + Q6 + Q8 | Eligible. Database object/ref layout, schema object path, manifest reshape, registry/schema migration, and views layout all have upstream Q decisions closed. Per-row gates differ: A16(B)/A17 are primarily Q1+Q3;A19 needs Q6+Q8 timing for `components.registry`;A20(E) needs Q1+Q3 path semantics plus Q6 phase timing. |

**Boundary**: this is high-blast-radius migration work. It depends on identity and Database boundary substrate. It should not be treated as a small docs-only cleanup.

## 4. Cross-Doc Blocked After Q Closure

These remain blocked even though all Qs are closed. They require sibling-doc redraft before blueprinting or implementation.

| Rows / seams | Required redraft | Reason |
|---|---|---|
| S1, S2 | Rule-expression doc | `evaluate(view=)` and `read.find(view=)` API semantics belong to rule-expression / read API surface. |
| S3, I10, A10 | Rule-expression + evidence-tree docs | EvaluateResult/evidence metadata carrier shape needs consumer redraft. Q1/Q3/Q4 now provide identity sources, but not the carrier. |
| S4 | Evidence-tree doc | EvidenceGraph.metadata durable copy cannot be specified until S3 carrier exists. |
| S5 | Evidence-tree doc + this doc §13 finalization | Stale/out-of-scope failure envelope carrier remains evidence-tree territory. |
| S6, A15 (F) | Rule-expression doc | `rule_set_digest` formula and placement remain sibling-doc work. |

**Synthesis result**: Q closure removes the internal DB/view identity blockers for S1-S6, but does not make them blueprint-eligible inside DB/view alone.

## 5. No Independent Action

These rows should be folded into parent blueprint acceptance criteria or release gates.

| Rows | Parent surface |
|---|---|
| A1 | Parent is the DB/view substrate blueprint(s) covering I1-I4. |
| A2 (B), D4 | Parent is Q1/Database boundary blueprint. Strict Database v1 keeps retract/update out of Database v1;shipped compatibility paths remain below/around it. |
| A7 | Parent is I7/I8 view-scope behavior. |
| A8, A9, I9 | Parent is view-scoped runtime blueprint acceptance gates: conflict/no-nesting and no silent fallback. |
| A10 | Parent is cross-doc S3/I10, not a standalone DB/view item. |
| A14 | Parent is attach/view runtime release gate: read-only scoped forms must co-ship with enforcement. |
| A15 (D) | Parent is Q2 attach lifecycle: no `rules=` parameter. |
| D5 | Future schema migration tx task if required;not an immediate DB/view drift item. |

## 6. Already Aligned / Keep

No blueprint action needed for these rows unless touched by adjacent migration.

- I12 (B), I12 (D)
- A4
- A11 branch / writable sub-fg / remote / multi-db absence
- A15 (A-runtime), A15 (C), A15 (E)
- A16 (A)
- A18 (B)

## 7. Deferred / v2+

No current blueprint action. Keep as deferred unless product scope changes.

- D1 persistent named views in Database
- D2 branch / tag / refs
- D3 writable sub-fg
- D6 materialized derived views
- D7 remote database
- D8 multi-db join
- D10 view set algebra API

## 8. Blueprint Implications

This synthesis makes DB/view blueprinting possible, but not as a single implementation branch. The eligible set is too broad and crosses identity, workspace layout, runtime lifecycle, view persistence, and registry migration.

### 8.1 Recommended blueprint slices

Recommended order, derived from dependency structure:

1. **DB identity substrate**: Q1/Q3/Q7 rows: Database boundary, tx/data/asrt identity, 7-field durable assertion record. This is the foundation for other slices.
2. **Workspace physical layout**: I13/A16/A17/A19/A20(E), after identity substrate shape is scoped. This owns `db/objects/`, refs, manifest reshape, and schema object path.
3. **View shape and persistence**: Q4/Q5 rows: anchored `FrozenAssertionView`, `view_digest`, view object persistence, scope universe semantics.
4. **Attach lifecycle substrate**: Q2/Q4/Q5 rows: base/snapshot/view attach forms, read-only scoped enforcement, no `rules=`.
5. **Registry/SavedRule migration**: Q8/Q6 rows: gradual deprecation, registry exit phases, apply-log event-kind scoping.

The slices can be adjusted, but combining all five into one blueprint would repeat the Phase C failure mode: too many concepts introduced before the implementation surface is stable.

**Slice parallelism and reverse dependencies**:

- Slice 3 (view shape and persistence) can proceed in parallel with slice 2 where it only needs Q1/Q3 identity tokens;`view_digest` does not require the workspace physical layout to already exist.
- Slice 4 (attach lifecycle substrate) can split: writable `attach(db)` depends only on the Database boundary, while snapshot/view-scoped forms depend on slice 1 identity and slice 3 view DTOs.
- Slice 2's A19 manifest reshape cannot fully remove `components.registry` until slice 5 advances through Q8 Phase 2 and the A20(E) schema migration path is available.

### 8.2 What is still not blueprint-ready

Do not blueprint these under DB/view alone:

- `fg.eval.evaluate(view=...)`
- `fg.read.find(view=...)`
- EvaluateResult metadata carrier
- EvidenceGraph.metadata durable copy
- stale/out-of-scope failure envelope
- `rule_set_digest`

Those require rule-expression / evidence-tree redraft first.

## 9. Final Synthesis

All 8 audit Qs are closed. Therefore, the audit's internal DB/view blockers are resolved. The remaining distinction is:

- **Blueprint-eligible DB/view drift**: identity substrate, Database boundary, attach lifecycle substrate, view shape/persistence/scope semantics, workspace layout, schema object path, and registry/SavedRule migration.
- **Still blocked**: any row whose carrier or public semantics live in rule-expression or evidence-tree docs.

Implementation remains **not authorized** by this document. The next valid step is a scoped blueprint or blueprint set, starting with the DB identity substrate slice unless the user explicitly chooses a different dependency-aware slice.
