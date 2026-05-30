# Q-EXISTS Decision: Step 2+ `:exists` removal scope + legacy handling + Q-PR1 boundary

- Status: proposed
- Created: 2026-05-30
- Last Updated: 2026-05-30
- Authority: design constraint;locks the next Step 2+ `:exists` cleanup slice scope before blueprint drafting.
- Inputs:
  - `workflow/audit/active/2026-05-30_exists-removal-vs-shipped.md` (`bd3ab5c3`) §4 answers, §5 five-bucket triage, §6 OQ list.
  - Reviewer Stage 1 audit pass on `bd3ab5c3`, with P2-1 user-vs-derived split and P2-2 legacy ledger data handling requirements.
  - ADR-IC `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` §4.4 Step 2+ forward pointer.
  - ADR-API `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` §4.1/§4.5 namespace and schema-extension locks.
- Outputs / Downstream:
  - Next blueprint candidate for a narrow `:exists` co-emission + legacy guard-compat cleanup slice.
  - Carry-forward entries for rule-level virtual existence, shadow-store removal, and Q-PR1 derivation accept alignment.
- Related:
  - Slice 2 Identity-as-Claim implementation and shipped-alignment audit.
  - Slice 3a API namespace refactor.
  - Slice 4 docs polish.
- Branch: `v0.2.0-exists-removal-q-decision-2026-05-30`
- Depends on:
  - Slice 4 archive head `4cc577dc`.
  - Stage 1 audit head `bd3ab5c3`.

> ADR 4-state lifecycle (per Q2 §4.5): `proposed` → `adopted` (current binding constraint, stays in `active/`) → `superseded` or `withdrawn` (moves to `archive/`). This draft is **not adopted** until reviewer/user acceptance.

## 1. Inputs

### 1.1 Stage 1 audit ground truth

The audit found that `<EntityType>:exists` is currently used across more than one layer:

| Surface | Current role | Audit evidence |
|---|---|---|
| Schema index | `exists_predicate_id`, `exists_pred_ids`, and `protected_anchor_pred_ids` | audit §2 rows 1/3 |
| Entity create/write | `record_exists` planned op writes one `:exists` Claim | audit §2 rows 2/3 |
| Entity visibility | `_entity_visible(...)` first checks `:exists`, then fields | audit §2 row 3 |
| `fg.entities.exists` | direct active `:exists` scan | audit §2 row 4 |
| Retract guard | `exists_pred_ids` raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` | audit §2 row 6 |
| Rule/query | DSL and protocol use `Entity:exists` to bind entity variables | audit §2 rows 7/8 |
| Q-PR1 derivation accept | writes `exists_pred_id` claims for derived entity materialization | audit §2 row 9 |
| Shadow store | legacy lazy-materialization identity bundle cache | audit §2 row 10 |

### 1.2 Reviewer-required additions

Reviewer pass on `bd3ab5c3` accepted the audit but required Stage 2 to explicitly handle:

| ID | Requirement | Why it matters |
|---|---|---|
| P2-1 | User-vs-derived split | If user create stops emitting `:exists` while Q-PR1 derivation accept keeps emitting it, entity existence semantics split by source path. |
| P2-2 | Legacy ledger data | Existing ledgers may contain active `:exists` Claims from Slice 2/3a; guard/read behavior must be specified after removal. |

## 2. Scope

This decision locks:

1. What "Step 2+ `:exists` removal" means for the next slice.
2. Whether rule-level `Entity:exists` syntax remains.
3. Replacement semantics for `fg.entities.exists(...)`.
4. Legacy `:exists` Claim handling.
5. Q-PR1 sacred derivation accept boundary.
6. Whether to combine shadow-store removal.
7. Which implementation work is blueprint-eligible immediately.

## 3. Non-scope

This decision does **not** lock:

| Non-scope | Reason / downstream owner |
|---|---|
| Full rule-language removal of `Entity:exists` | Requires a broader rule/query design slice. |
| Q-PR1 derivation accept rewrite | Sacred path; requires explicit future authorization. |
| Shadow-store removal | Adjacent but separable; future cleanup slice. |
| SQLite/ledger schema migration | Slice 3b / ADR-SYS-B lineage. |
| Historical docs rewrite | Future docs pass only after runtime implementation lands. |
| Migration of existing persisted ledgers | Needs a separate data-migration policy if ever required. |

## 4. Decision

### 4.1 OQ1 — Meaning of "`:exists` removal" for the next slice

**Decision**: The next slice targets **user-facing co-emission and transitional guard cleanup**, not full removal of every `Entity:exists` concept.

Blueprint-eligible work:

- Stop user-facing entity materialization paths from emitting new `<EntityType>:exists` Claims where those paths can be changed without Q-PR1 scope expansion.
- Replace `fg.entities.exists(...)` with Identity-Claim-bundle visibility semantics.
- Keep `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` under its current name for legacy direct-retract protection, while narrowing new user-path behavior after §§4.5-4.8 are explicitly handled.
- Update tests and current docs for the chosen narrow semantics.

Not blueprint-eligible in the next narrow slice:

- Removing all `Entity:exists` rule syntax.
- Editing Q-PR1 sacred derivation accept.
- Removing shadow store.

### 4.2 OQ2 — Rule DSL / query semantics

**Decision**: Keep `Entity:exists` as **virtual rule syntax** for now.

The next slice must not attempt to delete rule DSL support for `ExistsAtom`, implicit attribute binding via `Entity:exists`, or rule protocol entity-ref inference. Instead, it should treat rule-level existence as a virtual/read-model concern that can be lowered or evaluated independently in a future rule/query slice.

Consequence:

- `src/factgraph/sdk/dsl/expr.py`, `src/factgraph/application/protocol/rule.py`, and `src/factgraph/core/rules/where_eval.py` are **not** automatic deletion targets for the narrow slice.
- Any runtime change that would make current rule bodies fail must be rejected or moved to a larger rule semantics slice.

### 4.3 OQ3 — Replacement for `fg.entities.exists(...)`

**Decision**: `fg.entities.exists(EntityCls, **identity)` should use **complete active Identity Claim bundle visibility** for the deterministic e_ref.

Default semantics:

1. Compute deterministic e_ref from the full Form I identity bundle.
2. Resolve the Entity schema identity predicate set.
3. Return true only if every Identity predicate in the bundle has at least one active Claim for that e_ref and expected identity value.
4. Return false for no active complete bundle.

Rationale:

- INV-7c makes Identity Claims immutable once emitted, so complete-bundle semantics are stable.
- "Any Identity Claim active" would be too weak for composite identity entities and could report partially-materialized entities as visible.

### 4.4 OQ4 — Entity delete counts and revocation target

**Decision**: After narrow removal, `fg.entities.delete(...)` should revoke Identity Claims and Field Claims. It should no longer count a newly-emitted user-path `:exists` Claim because user-path co-emission is removed.

For legacy `:exists` Claims, see §4.5.

Blueprint consequence:

- Existing emission-contract test files (e.g. `tests/test_sdk_entities_delete.py`, `tests/test_emission_contract.py`) currently encode "N Identity + 1 `:exists` + Field" count semantics for user-facing materialization paths. The next blueprint must identify the complete set during Stage 4 audit and update them to "N Identity + Field" semantics.
- Delete implementation must avoid failing if no active `:exists` Claim exists.

### 4.5 OQ5 / P2-2 — Legacy `:exists` Claims in existing ledger data

**Decision**: Existing `:exists` Claims become **read-only legacy Claims**. They are not migrated, bulk-revoked, or rewritten in the next narrow slice.

Rules:

- Legacy active `:exists` Claims may remain in ledgers created by Slice 2/3a-era code.
- Direct user/API retract of a legacy `:exists` Claim remains protected unless and until a dedicated legacy-data migration policy exists.
- `fg.entities.exists(...)` should not depend on legacy `:exists` for truth once Identity-bundle visibility is implemented. Legacy `:exists` may be ignored by that API.
- Docs must describe legacy `:exists` as historical/internal substrate, not current user-facing visibility source.

Consequence:

- `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` is **kept under its current name** by the narrow slice. Legacy direct-retract protection still uses this code; renaming to e.g. `EXISTENCE_CLAIM_LEGACY_GUARD` is deferred to a future legacy-data migration slice to keep blueprint diff narrow and avoid touching every raise/test site.
- No destructive ledger migration is in scope.

### 4.6 OQ6 — `exists_pred_ids` lifecycle

**Decision**: Lock **option (1)** for the narrow slice: keep `exists_pred_ids` only for legacy guard classification and schema compatibility, since taxonomy sources (a) and (b) in §4.10 both depend on it.

Required invariant:

- `identity_pred_ids` remains independent and continues to be the INV-7c source of truth.

Future carry-forward options (not in narrow slice):

2. Empty `exists_pred_ids` once no legacy Claim or derivation-path emission needs it (requires Q-PR1 scope expansion + legacy data migration policy).
3. Replace with a named legacy/virtual predicate registry if it improves clarity (requires a separate registry-design slice).

### 4.7 OQ7 — Shadow store removal

**Decision**: Do **not** combine shadow-store removal with the narrow `:exists` cleanup slice.

Rationale:

- Shadow store governs legacy e_ref-to-identity-bundle recovery and lazy materialization.
- `:exists` governs current visibility and transitional guard semantics.
- Combining both would make failures hard to attribute and would expand the slice from S-M to M-L.

Carry-forward:

- Shadow store removal remains a separate Step 2+ cleanup candidate after Identity-bundle visibility has shipped.

### 4.8 OQ8 / P2-1 — Q-PR1 derivation accept and user-vs-derived split

**Decision**: Do **not** expand Q-PR1 scope in the next narrow slice.

This means `src/factgraph/core/derivation/accept.py` remains untouched by default, even though it currently writes `exists_pred_id` Claims for derived entity materialization.

To avoid an unacknowledged user-vs-derived split, the next blueprint must explicitly classify Q-PR1 emitted `:exists` Claims as **derived-path legacy/virtual existence markers** and must not make `fg.entities.exists(...)` rely on them for user-facing truth.

Required blueprint language:

- User-facing entity existence = complete active Identity Claim bundle (§4.3).
- Q-PR1 derivation accept `:exists` writes = out-of-scope legacy/derived marker until a future Q-PR1-authorized slice.
- Any test or doc that compares user-created and derived-created entities must acknowledge this temporary split.

Rejected for the next slice:

- Editing `core/derivation/accept.py` to stop emitting `:exists`.
- Rewriting derivation accept to emit Identity Claims.
- Redefining `:exists` as a first-class "derived entity marker" public API.

### 4.9 OQ9 — ADR-IC update

**Decision**: The next blueprint must update ADR-IC §4.4 only after implementation semantics are verified.

Minimum doc update at close:

- Mark user-facing `:exists` co-emission retired.
- Mark legacy `:exists` Claims as protected historical data.
- Record rule-level `Entity:exists` as retained virtual syntax.
- Record Q-PR1 derivation accept as carry-forward, not accidentally aligned.

### 4.10 Post-narrow-slice `:exists` Claim Taxonomy

After the narrow slice lands, three distinct sources of `:exists` Claims (or references) will coexist in the system. Blueprint design must treat them as three separate concerns:

| Source | Origin | Handling |
|---|---|---|
| (a) Legacy user-path Claims | Emitted by Slice 2 / Slice 3a user-create paths before this slice | Read-only legacy data; preserved and protected per §4.5; not migrated. |
| (b) Derivation-path Claims | Emitted by Q-PR1 sacred `core/derivation/accept.py` for derived entity materialization; not user-facing | Out-of-scope legacy/derived markers per §4.8; user-facing `fg.entities.exists` ignores them. |
| (c) Rule DSL virtual references | `Entity:exists` syntax in rule bodies; does not emit ledger Claims | Retained as virtual rule syntax per §4.2; lowered/evaluated through Identity Claims or active field evidence in a future rule/query slice. |

**Implication for `exists_pred_ids`**: the schema-index frozenset must remain populated because both (a) and (b) require schema-level identification for guard classification and predicate dispatch. See §4.6 option (1) above.

## 5. Rejected Alternatives

### Option A: Full repo-wide `:exists` deletion in one slice

- **Why rejected**: It combines schema, rule DSL, where planning, entity APIs, Q-PR1 derivation accept, tests, docs, and historical records. This is too broad for the next step and violates the Stage 1 audit ER-A1 rejection.

### Option B: Remove guard first and let tests reveal the rest

- **Why rejected**: This weakens a shipped protection path without replacement semantics and repeats the anti-pattern rejected by audit ER-A2.

### Option C: Expand Q-PR1 now and rewrite derivation accept

- **Why rejected**: Q-PR1 is a sacred carve-out preserved through Slice 1/2/3a/4. Touching it requires explicit future authorization and likely belongs with adapter/derivation work, not a medium cleanup slice.

### Option D: Combine shadow-store removal and `:exists` removal

- **Why rejected**: The overlap is real but not sufficient. Shadow store removal changes lazy materialization/e_ref resolution behavior, while `:exists` removal changes visibility and guard behavior. Combining them would obscure regression attribution.

### Option E: Treat legacy `:exists` Claims as automatically removable

- **Why rejected**: It implies destructive ledger mutation or silent interpretation changes for existing data. No migration policy exists in this decision.

## 6. Supporting Evidence

| Evidence | Why it matters |
|---|---|
| `src/factgraph/application/schema_runtime.py:55-74` | `identity_pred_ids` and `exists_pred_ids` are separate; INV-7c survives without `exists_pred_ids`. |
| `src/factgraph/application/entity_write.py:698-708` | User/application create currently writes `record_exists`. |
| `src/factgraph/application/entity_write.py:860-875` | Visibility currently checks `:exists` first. |
| `src/factgraph/sdk/store.py:1234-1253` | `fg.entities.exists` currently depends on active `:exists`. |
| `src/factgraph/application/retract_guard.py:75-140` | Transitional guard is implemented by `exists_pred_ids` classification. |
| `src/factgraph/sdk/dsl/expr.py:397-400`, `:521-548` | Rule DSL emits `Entity:exists` for explicit and implicit entity binding. |
| `src/factgraph/application/protocol/rule.py:519-535` | Rule protocol infers entity-ref ports from `:exists`. |
| `src/factgraph/core/rules/where_eval.py:1024-1030` | Rule planner knows `:exists` specially. |
| `src/factgraph/core/derivation/accept.py:667-725`, `:1006-1015` | Q-PR1 sacred derivation accept writes `exists_pred_id`. |
| `tests/test_emission_contract.py`, `tests/test_sdk_entities_create.py`, `tests/test_sdk_entities_delete.py`, `tests/test_sdk_entities_exists.py` | Current regression suite encodes the transitional contract that the next slice must consciously rewrite. |

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks a narrow blueprint for:

- User-facing `:exists` co-emission removal.
- `fg.entities.exists(...)` Identity-bundle rewrite.
- Guard behavior narrowing for non-legacy paths while preserving the legacy guard code name.
- Test migration away from "N Identity + one `:exists`" user-path expectations.

### 7.2 Required blueprint scope locks

The next blueprint must include scope-freeze locks for:

1. Q-PR1 sacred paths remain 0 diff.
2. Shadow store remains in scope only for read/compat validation, not removal.
3. Rule DSL `Entity:exists` remains virtual syntax.
4. Legacy `:exists` Claims are preserved and protected.
5. `fg.entities.exists` uses complete Identity Claim bundle semantics.
6. No destructive ledger migration.

### 7.3 Required implementation tests

The blueprint must plan tests for:

- `fg.entities.create` no longer emits user-path `:exists`.
- Lazy materialization behavior remains explicit and does not regress shadow-store guarantees unless separately scoped.
- `fg.entities.exists` returns true from complete Identity Claim bundle and false for incomplete/no bundle.
- Composite identity requires complete bundle.
- `fg.entities.delete` succeeds when no `:exists` Claim exists.
- Legacy `:exists` direct retract remains protected or is otherwise explicitly classified.
- Q-PR1 derivation accept remains untouched and tests document the carry-forward split.

### 7.4 Required documentation updates

At implementation close, current docs must state:

- `:exists` user-facing co-emission is retired.
- `Entity:exists` in rules remains virtual/internal syntax.
- Legacy `:exists` Claims may exist in old ledgers and remain protected.
- Q-PR1 derivation accept alignment is carry-forward.
- Shadow store removal remains separate.

## 8. Acceptance Criteria

- [ ] Decision is adopted before any `:exists` removal blueprint is scoped.
- [ ] Blueprint cites this decision §4.1-§4.10.
- [ ] Blueprint explicitly records Q-PR1 no-touch unless user authorizes an exception.
- [ ] Blueprint explicitly records legacy `:exists` handling.
- [ ] Blueprint does not combine shadow-store removal unless this decision is superseded.
- [ ] Post-implementation tests verify complete Identity Claim bundle visibility.
- [ ] Post-implementation docs distinguish retired user co-emission from virtual/rule and legacy/derived behavior.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | proposed | Decision drafted | Drafted from Stage 1 audit `bd3ab5c3`; incorporates reviewer P2-1 user-vs-derived split and P2-2 legacy ledger data handling as §§4.5/4.8. |
