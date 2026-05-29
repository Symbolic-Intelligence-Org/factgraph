# Synthesis: Identity-as-Claim Post-Q Bucketing

- Status: complete
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in implementing blueprints per CADENCE Stage 3.
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-sys-a-system-namespace-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-sys-b-revokes-migration-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-inv9-adapter-enforcement-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-ie-entity-editor-decision.md`
  - `workflow/design/decisions/active/2026-05-29_q-docs-sync-decision.md`
- Outputs / Downstream:
  - Slice 1 Form I blueprint.
  - Slice 2 Identity-as-Claim blueprint.
  - Slice 3a API surface blueprint.
  - Slice 3b ledger migration blueprint.
  - Slice 4 docs sync blueprint skeleton, with implementation gated by Slice 1-3b docs landing.
  - Slice 5 Step 2+ PyReason adapter / INV-9 strict blueprint.
- Related:
  - `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
  - `workflow/design/design-points/active/ledger-schema-specification.zh.md`
  - `workflow/CADENCE.md`
- Source audit: `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md`
- Closed Q decisions:
  - meta-ADR `ebafdb0c`, cross-check wording amendment `7fc11e81`
  - ADR-FI `b288ea9e`
  - ADR-IC `2d0866ed`
  - ADR-API `66434490`
  - ADR-SYS-A `75f1c8bc`
  - ADR-SYS-B `6b0ac349`
  - ADR-INV9 `c03e435d`
  - ADR-IE `9fd0ffb5`
  - ADR-DOCS `bb6a2c90`
- Branch: `v0.2.0-identity-as-claim-synthesis-2026-05-29`

> This synthesis follows the Stage 2 cross-check performed after ADR-DOCS adoption. The only cross-check amendment was the meta-ADR INV-9 wording sync at `7fc11e81`; it changed wording only and did not alter grouping, dependencies, or slice boundaries.

## 1. Purpose

Stage 1 produced the identity-as-claim vs shipped audit and surfaced Q1-Q17. Stage 2 closed the full question set through one meta-ADR plus eight normal ADRs. This synthesis converts those decisions into a blueprint ladder and re-buckets the audit drift inventory under closed-Q state.

This document does not implement FactGraph changes and does not supersede any adopted ADR. It is the Stage 3 bridge into the blueprint pillar.

## 2. Adopted Decision Summary

| ADR | Qs / scope | Final lock | Implementation slice |
|---|---|---|---|
| meta-ADR | grouping + slice boundaries | 8 normal ADRs; Q5 split into Q5a/Q5b; Q4/Q-PR1 separation; Slice 3b boundary questions delegated to ADR-SYS-B | Stage 2 governance |
| ADR-FI | Q6/Q7/Q8/Q9 | Form I descriptor surface; `_DataMember` internal; `Field(cardinality=...)` removed; `Identity(primary_key/default/default_factory)` removed; enum/pattern dual-layer validation | Slice 1 |
| ADR-IC | Q1/Q2/Q3/Q16 | Identity Claim emission is application-layer, carries-bundle only; Layer 2/3 Identity mutation reject; `_identity_pred_ids` + `_exists_pred_ids`; `:exists` remains transitional in Step 1 | Slice 2 |
| ADR-API | Q10/Q11/Q12/Q13/Q14 | Three manager namespaces; `AssertionsManager` vs pure-read `AssertionView`; `version()` hard remove; `_meta` only; `register/extend/apply` and evolution rejects | Slice 3a |
| ADR-SYS-A | Q5a | G1 raw pred_id guard + G2 schema owner guard; entity and relationship schema declarations covered; wire batch transitive G2 coverage | Slice 3a |
| ADR-SYS-B | Q5b/Q15 | Internal `__system__.revokes` emission path; value/value_tag dual-coexistence; claim_meta replacement; ingest_keys deletion; set dedup / add multiset; INV-15 filter; rest_terms drop deferred | Slice 3b |
| ADR-INV9 | Q4/Q-PR1 | Slice 3b has no runtime INV-9 strict check; Slice 5 binds adapter rewrite + rest_terms drop + write_protocol ingress strict + DTO/SQL type-level enforce | Slice 5 |
| ADR-IE | EntityEditor contract | EntityEditor lifecycle / commit / rollback / Identity reject / cardinality / closed behavior / edit-existing-only | Slice 3a |
| ADR-DOCS | Q17/D1-D11 | Hybrid docs sync:per-slice load-bearing plus Slice 4 consolidated; Slice 4 implementation waits for Slice 1-3b docs landed | Slice 1-5 docs gates + Slice 4 |

## 3. 5-Bucket Classification

### 3.1 Blueprint-Eligible

These rows are gated only by adopted ADRs and are ready to enter scoped blueprints.

| Bucket item | Audit origin | ADR closure | Blueprint owner |
|---|---|---|---|
| Form I descriptor refactor | Q6-Q9; A6-A10; PDF A1/A2/A7/A9 | ADR-FI | Slice 1 |
| Identity Claim emission + INV-7c protection | Q1-Q3/Q16; INV-7a/b/c; A4/A16/A18/A20; D11 | ADR-IC + ADR-API Q14 contract | Slice 2 |
| API namespace three-layer migration | Q10-Q14; A11-A17; D1-D3/D5-D7 | ADR-API + ADR-SYS-A + ADR-IE | Slice 3a |
| System namespace reservation | Q5a; INV-10 boundary; relationship schema path; wire replay classification | ADR-SYS-A | Slice 3a |
| EntityEditor public contract | shipped `EntityEditor` baseline + ADR-IE follow-ups | ADR-IE | Slice 3a |
| Ledger partial migration | Q5b/Q15; INV-11/12/13/14/15; A19/A21; D10 | ADR-SYS-B | Slice 3b |
| Per-slice load-bearing docs | D1-D7/D10/D11 and ADR follow-ups | ADR-DOCS | Each Slice 1/2/3a/3b |

### 3.2 Cross-Doc Blocked

These are not independent design blockers. They require docs or reference sync after the implementing slice lands.

| Item | Blocking condition | Owner |
|---|---|---|
| SDK API surface docs drift | Slice 3a code surface must land first | Slice 3a load-bearing docs + Slice 4 consolidated |
| Assertions quickstart drift (`version`, `_meta`, `fg.assertions.where`) | Slice 3a code surface must land first | Slice 3a load-bearing docs + Slice 4 consolidated |
| Ledger spec §9 migration markers | Slice 3b schema migration must land first | Slice 3b load-bearing docs + Slice 4 consolidated |
| Identity design-point INV-7 / Form I sections | Slice 1/2 decisions must be reflected as authoritative references | Slice 1/2 load-bearing docs |
| Slice 4 consolidated docs work | Must wait for Slice 1 + Slice 2 + Slice 3a + Slice 3b load-bearing docs landed | Slice 4 Phase 2 only |

### 3.3 No Independent Action

These rows fold into parent blueprints and should not become standalone implementation work.

| Item | Disposition |
|---|---|
| meta-ADR grouping decisions | Already consumed by Stage 2. No implementation slice; used as governance reference. |
| D1-D7 docs rows | Fold into Slice 3a docs acceptance, not separate docs-only work before code lands. |
| D10 cleanup | Fold into Slice 3b ledger migration. |
| D11 flag/comment cleanup | Fold into Slice 2 cache/emission implementation. |
| `fg.entities.ref` read-filter discussion | No runtime filter work; deterministic constructor does not read ledger. |
| `:exists` removal | Step 1 retains transitional co-emission / guard; full removal is not a standalone Step 1 slice. |

### 3.4 Already Aligned

Shipped behavior already honors the design enough to serve as implementation substrate.

| Item | Evidence / use |
|---|---|
| INV-3 SQLite transaction atomicity | `append_assertion` and `append_revocation` use one write session; rely on this for Identity Claim + revokes atomic writes. |
| idref_v1 typed content-derived hash | Q1 settled as keep current `idref_v1:<EntityType>:<digest>` shape; no implementation work besides preserving. |
| schema_ir `is_identity_field` flag | Reuse for Identity Claim emission and `_identity_pred_ids`. |
| shipped `:exists` declaration + emission | Reused as transitional existence guard; not treated as new work. |
| IdentityEditor mutation rejection | Formalized by ADR-IE; only error wording / namespace relocation follow-up remains. |

### 3.5 Deferred / Step 2+

These are explicitly out of Step 1 blueprints.

| Item | Trigger / owner |
|---|---|
| Slice 5 PyReason adapter rewrite | ADR-INV9 locks multi-Claim Relationship lowering; Step 2+ blueprint only. |
| Drop `claims.rest_terms` column | Bound to Slice 5 with adapter rewrite and strict INV-9 enforcement. |
| `FrozenAssertionView` / `fg.views` renames | PDF C5/C6; Step 2+ docs/API cleanup, not Step 1. |
| `during((t1,t2))` / richer temporal APIs | Step 2+ temporal extension. |
| Alternative keys / InternalIdentity / advanced identity migration tools | Step 2+ identity evolution track. |

## 4. Recommended Blueprint Ladder

### Slice 1 — Schema / Form I Refactor

**Predicted class**: M.

**Depends on**: ADR-FI.

**Must include**:
- internal `_DataMember(_DeclaredMember)` with `description` and `pattern`;
- `Field()` signature with cardinality inferred from annotations;
- `Identity()` signature with `description` and `pattern` only;
- removal errors for `Field(cardinality=...)`, `Identity(primary_key=...)`, `Identity(default=...)`, and `Identity(default_factory=...)`;
- compile-time schema_ir extension for enum/pattern;
- write-time application-layer validation for enum/pattern through the application / SDK write path;
- Slice 1 load-bearing docs from ADR-DOCS §4.2.1.

**Must not include**:
- Identity Claim emission;
- namespace migration;
- ledger schema migration;
- PyReason adapter rewrite.

### Slice 2 — Identity Claim Emission + INV-7c

**Predicted class**: M/L depending on tests around lazy materialization and cache lifecycle.

**Depends on**: Slice 1, ADR-IC, ADR-API Q14 contract.

**Must include**:
- application-layer Identity Claim emission from complete identity bundle;
- no public Layer 2 Identity emission path;
- `_identity_pred_ids`, `_exists_pred_ids`, and `_protected_anchor_pred_ids`;
- Layer 2 value-oriented Identity mutation rejects;
- Layer 3 `fg.assertions.retract(asrt_id)` Identity / existence guard;
- schema register / extend hook integration for pred_id cache lifecycle;
- `:exists` co-emission retained as transitional guard;
- Slice 2 load-bearing docs from ADR-DOCS §4.2.2.

**Must not include**:
- removing `:exists`;
- rewriting API namespace surface;
- ledger `__system__.revokes` migration.

### Slice 3a — API Namespace + Assertion Surface

**Predicted class**: L.

**Depends on**: Slice 1 + Slice 2; ADR-API; ADR-SYS-A; ADR-IE.

**Must include**:
- `fg.entities`, `fg.fields`, `fg.assertions`, `fg.schema` manager surface;
- hard removal of `fg.read` / `fg.write` aliases in alpha;
- `AssertionsManager` vs pure-read `AssertionView` split;
- `AssertionView.where(field/e_ref/value/value_tag/_meta)` and terminal `at(t)` returning `AssertionRecordSet`;
- hard removal of `version(v)`;
- `_meta` only, with flat kwargs removed;
- `fg.schema.register/extend/apply`;
- schema evolution rejects including Identity↔Field changes and `:exists` predicate protection;
- G1/G2 `__system__` reservation checks for entity and relationship schema declarations;
- EntityEditor lifecycle/closed behavior/error wording per ADR-IE;
- Slice 3a load-bearing docs from ADR-DOCS §4.2.3.

**Must not include**:
- ledger schema migration;
- internal `__system__.revokes` emission;
- PyReason adapter rewrite.

### Slice 3b — Ledger Schema Partial Migration

**Predicted class**: L.

**Depends on**: ADR-SYS-B. Code dependency on Slice 3a should be evaluated during blueprint preflight; implementation can be planned after Slice 3a because SYS-A user-facing guards and API docs shape are part of Step 1 surface.

**Must include**:
- value + value_tag columns and canonical mapping;
- internal `__system__.revokes` emission through write_protocol, not a new ledger raw method;
- INV-12 part 2:reject revoke-of-revoke;
- claim_meta replacement and composite PK;
- removal of ingest_keys and replacement set/add semantics;
- set dedup active projection SQL;
- `Ledger.find_claim_args` compatibility wrapper preserving shipped signature and val_atom semantics;
- INV-15 default read filter with by_id/by_ids bypass;
- Slice 3b load-bearing docs from ADR-DOCS §4.2.4.

**Must not include**:
- blanket INV-9 runtime enforcement;
- PyReason adapter rewrite;
- dropping `claims.rest_terms`;
- changing `fg.entities.ref` filtering semantics.

### Slice 4 — Docs Sync

**Predicted class**: M docs-only.

**Depends on**: ADR-DOCS. Phase 1 skeleton can be drafted immediately; Phase 2 implementation waits until Slice 1 + Slice 2 + Slice 3a + Slice 3b load-bearing docs all landed.

**Must include**:
- five consolidated passes:terminology, cross-ref, examples, migration note placement, stale reference cleanup;
- check against all adopted ADR docs commitments;
- no code changes.

### Slice 5 — Step 2+ PyReason Adapter + INV-9 Strict

**Predicted class**: L.

**Depends on**: ADR-INV9 + ADR-SYS-B Slice 5 carry-forward.

**Must include**:
- drop `claims.rest_terms`;
- rewrite PyReason edge lowering to multi-Claim Relationship lowering;
- write_protocol ingress strict check;
- Claim DTO / SQL type-level enforce;
- cleanup `find_claim_args` compatibility wrapper after rest_terms removal.

**Must not block** Slice 1-4.

## 5. Cadence Reminders for Blueprints

- Each implementation slice needs a blueprint + paired audit log in `workflow/blueprints/active/`.
- Preflight must re-read shipped source at row-drafting time; do not rely on this synthesis as source-code truth.
- Slice 1/2/3a/3b blueprints must include ADR-DOCS per-slice load-bearing docs in acceptance.
- Slice 4 blueprint has two phases: skeleton/scoping immediately, implementation only after Slice 1-3b docs landed.
- Any override of an adopted ADR requires a superseding ADR, not a blueprint-local deviation.
- Preserve the unrelated dirty baseline; do not stage notebook/docs-reference changes unless a future user request explicitly scopes them.
- Sacred `master` and `v0.1-oss-prep` remain untouched.

## 6. Stage 2 Closure Trail

| Step | Commit | Notes |
|---|---|---|
| Stage 1 audit complete | `aa50332d` | audit cleanup after Phase 1-4 |
| meta-ADR adopted | `ebafdb0c` | grouping + slice boundary lock |
| Q5 split sync | `4830070a` | audit Q5 → Q5a/Q5b sync |
| ADR-FI adopted | `b288ea9e` | Form I |
| ADR-IC adopted | `2d0866ed` | Identity-as-Claim |
| ADR-API adopted | `66434490` | API namespace |
| ADR-SYS-A adopted | `75f1c8bc` | system namespace reservation |
| ADR-SYS-B adopted | `6b0ac349` | revokes + ledger migration |
| ADR-INV9 adopted | `c03e435d` | INV-9 + adapter rewrite |
| ADR-IE adopted | `9fd0ffb5` | EntityEditor |
| ADR-DOCS adopted | `bb6a2c90` | docs sync timing |
| Stage 2 cross-check cleanup | `7fc11e81` | meta-ADR INV-9 wording sync only |

## 7. Acceptance

- [x] All Stage 1 Qs Q1-Q17 map to adopted ADRs.
- [x] Audit drift inventory is re-bucketed into blueprint-eligible / cross-doc blocked / no independent action / already aligned / deferred.
- [x] Blueprint ladder includes Slice 1 / 2 / 3a / 3b / 4 / 5 and dependency notes.
- [x] CADENCE constraints and docs-sync gates are carried into blueprint reminders.
- [x] Stage 2 closure trail includes all adopted ADR commits plus cross-check amendment.

## 8. Recommended Next Action

Start **Slice 1 — Schema / Form I Refactor** as the first Stage 4 blueprint:

- branch:`v0.2.0-blueprint-form-i-schema-2026-05-29`
- blueprint:`workflow/blueprints/active/2026-05-29_form-i-schema.md`
- audit log:`workflow/blueprints/active/2026-05-29_form-i-schema.audit.md`

Slice 4 docs sync skeleton may be drafted in parallel after Slice 1 blueprint draft, but should not become the primary implementation lane before Slice 1-3b load-bearing docs land.
