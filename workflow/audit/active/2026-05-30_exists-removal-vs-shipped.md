# Audit: Step 2+ `:exists` Removal vs Shipped Runtime

- Status: complete
- Created: 2026-05-30
- Last Updated: 2026-05-30
- Authority: working triage document; informs but does not lock implementation
- Source intent:
  - ADR-IC §4.4.4 forward pointer: future Step 2+ removes `<EntityType>:exists` co-emission and retires the existence-claim transitional guard.
  - Slice 2 §10.9 and Slice 3a §10.9 carry-forward: evaluate `:exists` removal after Identity-as-Claim emission and Layer 1/2/3 namespace surfaces have shipped.
- Branch: `v0.2.0-exists-removal-audit-2026-05-30`
- Base: Slice 4 archive head `4cc577dc` (includes Slice 3a archive, Slice 4 docs polish, and N1 docstring fix `722595ba`)
- Downstream: Stage 4 blueprint candidate for Step 2+ `:exists` removal, subject to the Open Questions in §6.

## 1. Purpose

This audit answers whether the next implementation slice can safely remove the shipped `<EntityType>:exists` transitional substrate, and whether that cleanup should be combined with shadow-store removal.

The answer is nuanced:

- `:exists` is not only an emitted Claim. It is also used as an entity visibility marker, SDK existence-check substrate, retract-guard classification, schema-index predicate class, rule/query entity-binding predicate, and derivation accept write target.
- Shadow store removal is related through the legacy lazy-materialization path, but it is not the same problem. Combining both removals by default would expand blast radius and obscure which invariant failed.
- A small slice is still plausible if the implementation target is **co-emission + guard cleanup only**, while preserving a virtual/rule-level existence predicate or deferring rule-language removal.

## 2. Shipped Surface Inventory

| Area | Current shipped behavior | Evidence |
|---|---|---|
| Schema index | `EntityTypeInfo.exists_predicate_id` and `SchemaIndex.exists_pred_ids` are built from generated `is_entity_exists` predicates; `protected_anchor_pred_ids` is `identity_pred_ids | exists_pred_ids`. | `src/factgraph/application/schema_runtime.py:40-74`, `:206-250` |
| Entity create | `fg.entities.create(...)` delegates to application create, which plans Identity Claims plus one `record_exists` op. | `src/factgraph/sdk/store.py:1016-1092`, `src/factgraph/application/entity_write.py:698-708` |
| Entity visibility | `_entity_visible(...)` first checks active `<EntityType>:exists`, then falls back to any active field predicate for that e_ref. | `src/factgraph/application/entity_write.py:860-875` |
| Entity exists API | `fg.entities.exists(...)` directly scans active claims for `info.exists_predicate_id`. | `src/factgraph/sdk/store.py:1234-1253` |
| Entity delete | `fg.entities.delete(...)` is documented as whole-entity revoke for Identity Claims, `:exists`, and Field Claims. | `src/factgraph/sdk/store.py:1117-1232` |
| Retract guard | `check_retract_allowed(...)` raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` when target pred_id is in `exists_pred_ids`. | `src/factgraph/application/retract_guard.py:75-140` |
| Rule DSL | SDK rule lowering emits `("<EntityType>:exists", var)` for `ExistsAtom` and implicit attr binding. | `src/factgraph/sdk/dsl/expr.py:397-400`, `:521-548` |
| Rule protocol / where planner | Rule protocol infers entity-ref ports from `pred_id.endswith(":exists")`; where planner special-cases `:exists` ordering. | `src/factgraph/application/protocol/rule.py:519-535`, `src/factgraph/core/rules/where_eval.py:1024-1030` |
| Derivation accept | Internal accept writes `exists_pred_id` claims for derived entity materialization. This path is part of the Q-PR1 sacred carve-out. | `src/factgraph/core/derivation/accept.py:667-725`, `:1006-1015` |
| Shadow store | `_identity_values_by_e_ref` is still the legacy lazy-materialization compatibility path. | `src/factgraph/sdk/store.py:1005-1014`, `:1023-1050`, `:1169-1193` |

## 3. Audit Method

Commands were run from branch `v0.2.0-exists-removal-audit-2026-05-30` at base `4cc577dc`.

```bash
rg -n ":exists|exists_pred|EXISTENCE_CLAIM_TRANSITIONAL_GUARD|exists_predicate|exists\\(" src tests docs workflow examples --glob '!examples/archive/01_sdk_basics.ipynb'
rg -n "_identity_values_by_e_ref|shadow store|shadow-store|UNRESOLVABLE_E_REF|materialized_refs|_materialization_ops|entity_visible" src tests workflow docs examples --glob '!examples/archive/01_sdk_basics.ipynb'
rg -n "class SchemaIndex|exists_pred_ids|protected_anchor_pred_ids|identity_pred_ids|exists_predicate_id" src tests workflow docs
rg -n "exists_predicate_id|EXISTENCE_CLAIM_TRANSITIONAL_GUARD|:exists|entities\\.exists|record_exists|_identity_values_by_e_ref|shadow store|shadow-store" tests/test_emission_contract.py tests/test_sdk_entities_create.py tests/test_sdk_entities_delete.py tests/test_sdk_entities_exists.py tests/test_application_retract_guard.py tests/test_application_entity_write_retract_guard.py tests/test_application_ingest_retract_guard.py tests/test_sdk_assertions_namespace.py tests/test_application_schema_runtime_cache.py tests/test_sdk_retract_guard_integration.py
```

The audit intentionally used tracked paths and did not edit dirty notebooks or archived examples.

## 4. Answers To The 8 Audit Questions

| # | Question | Answer |
|---|---|---|
| 1 | `:exists` current use surface | Broad. It is emitted by application entity-write, read by entity visibility and `fg.entities.exists`, protected by retract guard, generated in schema index, used by rule DSL/protocol/planner, and written by Q-PR1 derivation accept. |
| 2 | Guard trigger surface | SDK `fg.assertions.retract`, flat compatibility paths already removed in Slice 3a, application ingest retract, and application entity_write retract all map `exists_pred_ids` to `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`. |
| 3 | `exists_pred_ids` use surface | Built in `schema_runtime.py`, read by `retract_guard.py`, included in `protected_anchor_pred_ids`, and asserted by schema-runtime tests. It is separate from `identity_pred_ids`, so INV-7c can survive without it. |
| 4 | Co-emission lifecycle | Current create/lazy materialization tests require N Identity + one `:exists` + Field atomicity. If co-emission is removed, visibility and duplicate checks must be redefined over Identity Claims or a virtual predicate before tests can change. |
| 5 | Shadow store coupling | Coupled but separable. Shadow store feeds legacy lazy materialization and e_ref resolution; `:exists` is the current visibility marker. Removing both together increases blast radius. |
| 6 | Combined slice? | Recommended default: separate. First decide/implement `:exists` removal semantics; then evaluate shadow store removal in its own slice unless Stage 2 chooses a combined "Slice 2 Phase 2 cleanup" explicitly. |
| 7 | Test impact | At least 10 shipped test files directly assert `:exists`, `exists_pred_ids`, `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`, or `fg.entities.exists` behavior. Rule/application tests also encode `Entity:exists` in rule bodies. |
| 8 | ADR impact | ADR-IC §4.4 needs an amendment or Q decision before implementation, because "remove `:exists`" has multiple meanings: stop Claim co-emission, remove schema predicate, remove rule syntax, or retire only the guard. |

## 5. Five-Bucket Triage

### 5.1 Required Before Blueprint

| ID | Finding | Required decision / action |
|---|---|---|
| ER-R1 | "`:exists` removal" is ambiguous. The shipped system uses `:exists` as a Claim, schema predicate, rule predicate, guard class, and visibility marker. | Stage 2 must define exact removal target: co-emission only, runtime predicate removal, rule syntax removal, or phased combination. |
| ER-R2 | Entity visibility and `fg.entities.exists(...)` currently read active `:exists` Claims. | Blueprint must choose replacement semantics, likely active Identity Claim bundle visibility, before removing `record_exists` emission. |
| ER-R3 | Rule/query layers use `:exists` for entity-variable binding and planning. | Blueprint must either keep `Entity:exists` as virtual rule syntax, lower it to Identity Claims, or explicitly mark rule-language removal out of scope. |
| ER-R4 | Transitional guard cleanup spans SDK shell, application ingest, application entity_write, schema index, and tests. | Blueprint must include all guard mapping surfaces if retiring `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`. |
| ER-R5 | Q-PR1 sacred `src/factgraph/core/derivation/accept.py` still writes `exists_pred_id`. | Any implementation touching this file requires explicit Q-PR1 scope authorization; otherwise the next slice must leave this path alone or treat it as a carry-forward. |

### 5.2 Recommended

| ID | Finding | Recommendation |
|---|---|---|
| ER-REC1 | Shadow store removal is adjacent but not identical. | Do not combine by default. Keep a separate OQ and combine only if the blueprint can prove the replacement visibility path also eliminates lazy materialization safely. |
| ER-REC2 | `exists_pred_ids` can be emptied only if generated `:exists` predicates disappear. | If rule syntax remains virtual, keep a narrow schema-level representation or introduce a new virtual-predicate registry instead of blindly deleting the frozenset. |
| ER-REC3 | Test migration is broad but well localized. | Start implementation from test inventory: create/delete/existence/retract-guard/schema-cache/rule-body tests, then docs. |
| ER-REC4 | Documentation has explicit Step 2+ removal notes. | Treat docs as implementation-close scope, not Stage 1 scope; update ADR-IC/current docs only after Q decisions land. |

### 5.3 Verified

| ID | Verified aligned fact | Evidence |
|---|---|---|
| ER-V1 | `identity_pred_ids` and `exists_pred_ids` are independent frozensets. Removing `exists_pred_ids` does not inherently weaken INV-7c. | `src/factgraph/application/schema_runtime.py:55-74` |
| ER-V2 | `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` is explicitly not INV-7c and is documented as retire-able with Step 2+ `:exists` removal. | `src/factgraph/application/retract_guard.py:19-23` |
| ER-V3 | `fg.entities.create(...)` eager path shipped, and shadow store remains legacy compatibility rather than contract. | `src/factgraph/sdk/store.py:1023-1050` |
| ER-V4 | There is strong regression coverage around current `:exists` semantics. | `tests/test_emission_contract.py`, `tests/test_sdk_entities_create.py`, `tests/test_sdk_entities_delete.py`, `tests/test_sdk_entities_exists.py`, guard test files listed in §3. |

### 5.4 Scoped Detail

| ID | Detail | Scope implication |
|---|---|---|
| ER-S1 | Historical docs and archived blueprints mention `:exists` extensively. | Future implementation grep gates must distinguish current-truth docs from historical migration records. |
| ER-S2 | Dirty notebooks are preserved user workspace state. | Do not overwrite them in a runtime cleanup slice unless user authorizes per file. |
| ER-S3 | Q-PR1 sacred files are read for audit but remain 0-diff protected. | If future slice needs `core/derivation/accept.py`, scope freeze must explicitly name and authorize the exception. |

### 5.5 Abandonment

| ID | Candidate path | Reason to abandon for next slice |
|---|---|---|
| ER-A1 | "Remove every `<EntityType>:exists` reference repo-wide in one small cleanup." | Too broad. It would combine schema, rule language, application visibility, Q-PR1 derivation accept, tests, docs, and archived historical records. |
| ER-A2 | "Delete `exists_pred_ids` first and let failures reveal replacement work." | Violates cadence and Rule 2; it would silently weaken guard classification without a replacement visibility/rule model. |

## 6. Open Questions For Stage 2 / Blueprint Lock

| OQ | Question | Audit recommendation |
|---|---|---|
| OQ1 | What exactly does "remove `:exists`" mean for the next slice? | Define as **co-emission + guard cleanup** unless Stage 2 explicitly authorizes broader rule/schema removal. |
| OQ2 | Should `Entity:exists` remain as rule DSL syntax? | Prefer keeping it as virtual syntax for now, then lower/evaluate through Identity Claims or existing active field evidence. |
| OQ3 | What is the replacement for `fg.entities.exists(...)`? | Likely active complete Identity Claim bundle for the deterministic e_ref; decide all-vs-any identity predicate semantics. |
| OQ4 | Should `fg.entities.delete(...)` revoke Identity Claims only, or still count/revoke virtual existence markers? | Prefer Identity + Field Claims only if co-emission is removed; adjust count assertions explicitly. |
| OQ5 | When does `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` retire? | Same slice if no emitted `:exists` Claims remain; later slice if legacy claims must remain readable/protected. |
| OQ6 | Should `exists_pred_ids` be removed, emptied, or replaced by a virtual predicate registry? | Decide after OQ2. Emptying is safe only if generated `:exists` predicates are fully removed from schema/runtime. |
| OQ7 | Combine shadow store removal? | Default no. Combine only if replacement visibility semantics make lazy materialization obsolete and tests can be migrated without touching Q-PR1. |
| OQ8 | Is Q-PR1 sacred derivation accept in scope? | Default no. If yes, this is not a small cleanup; it needs explicit scope freeze and likely a larger slice. |

## 7. Proposed Next Slice Shape

Recommended next cadence:

1. Stage 2 decision doc for OQ1-OQ8, especially OQ1/OQ2/OQ7/OQ8.
2. If Stage 2 chooses narrow scope, draft a blueprint for **`:exists` co-emission + guard retirement**:
   - Replace `fg.entities.exists(...)` substrate.
   - Stop `record_exists` emission in SDK/application create/lazy materialization paths that are in scope.
   - Remove or gate `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` only after proving no user-facing emitted `:exists` claims remain.
   - Preserve Q-PR1 sacred derivation accept unless explicitly authorized.
   - Leave shadow store removal as carry-forward.
3. If Stage 2 chooses broad scope, split into at least two slices:
   - Slice A: rule/schema virtual existence semantics.
   - Slice B: claim co-emission + guard/test/docs cleanup.

## 8. Verification Commands

```bash
git branch --show-current
git rev-parse master
git status --short
git diff --name-only 722595ba..HEAD -- src/factgraph/core/evidence/write_protocol.py src/factgraph/core/store/ledger.py src/factgraph/core/store/_builders.py src/factgraph/adapters/pyreason src/factgraph/core/derivation/accept.py
python -m compileall -q src
```

Expected invariants for this audit commit:

- Branch is `v0.2.0-exists-removal-audit-2026-05-30`.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Q-PR1 sacred path diff is empty.
- Dirty baseline remains unchanged.
- No push is performed.

## 9. Completion Checklist

- [x] `:exists` emit/read/guard/schema/rule/test surfaces inventoried.
- [x] Shadow store coupling evaluated separately from `:exists`.
- [x] Combined-vs-split slice question surfaced.
- [x] Test impact surface documented.
- [x] ADR impact documented.
- [x] Q-PR1 sacred-path risk documented.
- [x] Five-bucket triage complete.
- [x] OQ list ready for Stage 2 / blueprint lock.
