# Slice 2 — Identity-as-Claim Core(emission contract formalize + INV-7c reject + cache + `:exists` transitional guard)

- Status: draft
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Slice: 2 of identity-as-claim Step 1 ladder(per synthesis `d0036e1f`)
- Class: M(smaller than Slice 1 — more contract-formalization than semantic rewrite)
- Related Modules:
  - `src/factgraph/application/schema_runtime.py`(`SchemaIndex` cache extension)
  - `src/factgraph/application/retract_guard.py`(NEW — application source-of-truth guard helper)
  - `src/factgraph/sdk/store.py`(SDKStore.retract wrap + shadow store legacy comments)
  - `src/factgraph/application/ingest_runtime.py`(`_apply_retract` wrap)
  - `src/factgraph/application/entity_write.py`(`_apply_op` retract branch wrap + plan_write_command error message update)
  - `src/factgraph/sdk/facade.py`(IdentityEditor error message update)
- Related Docs:
  - [workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md](../../design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md) — ADR-IC adopted @ `2d0866ed`
  - [workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md](../../design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md) — meta-ADR adopted @ `ebafdb0c`(cross-check `7fc11e81`)
  - [workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md](../../design/decisions/active/2026-05-29_q-fi-form-i-decision.md) — ADR-FI adopted @ `b288ea9e`(Slice 1 baseline)
  - [workflow/design/decisions/active/2026-05-29_q-docs-sync-decision.md](../../design/decisions/active/2026-05-29_q-docs-sync-decision.md) — ADR-DOCS adopted @ `bb6a2c90`(§4.2.2 Slice 2 load-bearing docs)
  - [workflow/audit/active/2026-05-29_post-q-identity-as-claim-synthesis.md](../../audit/active/2026-05-29_post-q-identity-as-claim-synthesis.md) — Stage 3 synthesis
  - [workflow/design/design-points/active/identity-mechanism-redesign.zh.md](../../design/design-points/active/identity-mechanism-redesign.zh.md) — §5.2 INV-7a/b/c + §13(target authoritative)
  - [workflow/blueprints/active/2026-05-29_slice-1-form-i-schema.md](./2026-05-29_slice-1-form-i-schema.md) — Slice 1 Form I baseline(implemented @ `9cef674b`)
- Audit Log:
  - [2026-05-29_slice-2-identity-claim-emission.audit.md](./2026-05-29_slice-2-identity-claim-emission.audit.md)
- Branch: `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29`(forks from Slice 1 close `9cef674b`)

## 1. Problem

ADR-IC(`2d0866ed`)locks 4 sub-decisions(Q1 双路径 reject + Q2 emission contract + Q3 cache + Q16 `:exists` transitional guard)。Slice 2 converts these into shipped code:

Preflight code audit revealed:
- **Section A**(emission)+**Section B**(Layer 2 reject)— ALREADY shipped baseline;Slice 2 mainly **formalizes via contract tests + docs + error message updates**
- **Section C**(Layer 3 asrt_id reject)— **NOT shipped** main new work:user-facing `SDKStore.retract(asrt_id)` 没有 schema-aware check;application 层 `ingest_runtime._apply_retract` + `entity_write._apply_op` retract branch 也需要同样 guard(P1 reviewer finding — 否则 bulk ingest 绕过 INV-7c)
- **Section D**(cache)— `SchemaIndex` 需要扩展 `_identity_pred_ids` + `_exists_pred_ids` 两个独立 frozenset

Slice 2 不引入 PyReason adapter / claims.rest_terms / INV-9 runtime strict 任何修改(Q-PR1 carve-out)。

## 2. Goals

- G1 Land `SchemaIndex` cache extension(`_identity_pred_ids` + `_exists_pred_ids` + `_protected_anchor_pred_ids` union property per ADR-IC §4.3.1)
- G2 Land **application source-of-truth retract guard helper**(NEW `application/retract_guard.py`)classifying Identity vs `:exists` vs Field
- G3 Wrap **all 3 application-or-above retract entry points**(SDK shell + application ingest + application entity_write)with the shared guard helper
- G4 Update Layer 2 Identity reject error messages(IdentityEditor + plan_write_command)to ADR-IC §4.1 wording(含 delete+create migration hint)
- G5 Document shadow store(`_identity_values_by_e_ref`)as legacy/internal compatibility(per ADR-IC §4.2.3)
- G6 Slice 2 load-bearing docs per ADR-DOCS §4.2.2:`04_api_surface.en.md` + `identity-mechanism-redesign.zh.md §5.2/§13`
- G7 Preserve Q-PR1 carve-out:zero diff in `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / claims.rest_terms / INV-9 runtime strict / `core/derivation/accept.py:401`(internal rollback path — separately classified per §6.3)
- G8 Preserve sacred-master + dirty-baseline + branch lineage per CADENCE per-commit ritual

## 3. Non-goals

- N1 `fg.schema.register/extend/apply` namespace migration(ADR-API Q14 future scope)— NO stub creation per OQ3 verdict
- N2 `fg.fields.*` / `fg.assertions.*` namespace rename — Slice 3a / ADR-API Q10
- N3 `:exists` Claim emission removal — Step 2+(per ADR-IC §4.4.4 forward-pointer)
- N4 PyReason adapter rewrite / `claims.rest_terms` drop / INV-9 ingress strict — Slice 5 / ADR-INV9
- N5 Rule layer `:exists` dependency rewrite(`application/protocol/rule.py:528-532`)— Step 2+ rule-layer follow-up
- N6 Schema mutation in live ledger — ADR-API Q14 + Slice 3a
- N7 Wide docs polish across other quickstarts — Slice 4 Phase 2 per ADR-DOCS §4.3
- N8 Shadow store removal(`sdk/store.py:923` `_identity_values_by_e_ref`)— Step 2+ eager-emission演化 per ADR-IC §4.2.4
- N9 `schema_compile.py:258-259` `primary_key` dead-code(already cleaned in Slice 1)
- N10 IdentityEditor lifecycle refactor — Slice 3a / ADR-IE
- N11 `core/derivation/accept.py:401` `retract_by_asrt` direct rollback path — **internal rollback,not user-facing**;Slice 2 显式 classify 但 NOT touched

## 4. Current Context

### 4.1 Shipped baseline(preflight code audit completed)

**Section A — Identity Claim emission(已 shipped)**:
- `application/entity_write.py:324-349` `_materialization_ops`:emits `set` ops for each identity_field + `record_exists` op
- `application/entity_write.py:383-412` `_apply_op` `record_exists` routing → `set_field(store.ledger, info.exists_predicate_id, ...)` line 392
- `application/protocol/entity_write.py:77-104` `PlannedOpDTO` `record_exists` op kind
- `application/entity_write.py:331-334` `materialized_refs` deduplication
- `core/store/ledger.py:296-310` `_write_session` atomic context

**Section B — Layer 2 Identity reject(已 shipped — error message 更新)**:
- `sdk/facade.py:449-480` `IdentityEditor.set/add/retract` raise `SDKStoreError`(SDK shell fail-fast)
- `sdk/facade.py:507-511` `EntityEditor.__getattr__` routes identity fields to IdentityEditor
- `application/entity_write.py:186-192` `plan_write_command` `pred_info.is_identity_field` check + raise(application source-of-truth path for Layer 2)

**Section C — Layer 3 asrt_id reject 路径(NOT shipped — main new work)**:
- `sdk/store.py:2104-2128` `SDKStore.retract(asrt_id)` — **NO schema-aware check** ✗
- `application/ingest_runtime.py:169` `_apply_retract` direct `retract_by_asrt(store.ledger, item.assertion_id, ...)` — **NO schema-aware check** ✗(P1 reviewer finding — bulk ingest bypass risk)
- `application/entity_write.py:412` `_apply_op` retract branch direct `retract_by_asrt(store.ledger, op.assertion_id, ...)` — **NO schema-aware check** ✗

**Section D — Cache state(扩展 SchemaIndex)**:
- `application/schema_runtime.py:49-54` `SchemaIndex` — fields `entities/field_predicates/predicates_by_id`(extend with 2 frozensets)
- `application/schema_runtime.py:19-29` `PredicateInfo.is_identity_field` + `.is_entity_exists`(✓ extended in Slice 1)
- `application/schema_runtime.py:146-147` `build_schema_index` filter pass on flags(extend with frozenset accumulators)

**Section E — Shadow store legacy(文档化)**:
- `sdk/store.py:923` `_identity_values_by_e_ref` class field
- `sdk/store.py:1912` populate at `SDKStore.ref()`
- `sdk/store.py:2014` read at `_apply_field_mutation`
- `sdk/store.py:2069` read at `_build_application_write_value`
- `sdk/store.py:2016-2020` `UNRESOLVABLE_E_REF` raise for missing e_ref(fail-fast per §4.2.1 emission input contract — already matches ADR-IC contract)

**Section F — `:exists` co-emission(rule layer 不动)**:
- `authoring/schema_compile.py:140-150` `<EntityType>:exists` predicate declaration
- `entity_write.py:_materialization_ops` line 348 `record_exists` op co-emit
- `application/protocol/rule.py:528-532` rule layer `:exists` reference(read-only — Slice 2 NOT modified per N5)
- `application/protocol/rule_expr_inspect.py:383-384` same(read-only)

**Section G — Protocol/core direct paths(Q-PR1 carve-out + 内部 rollback classification)**:
- `core/evidence/write_protocol.py:170` `retract_by_asrt` definition — INTENTIONALLY UNGUARDED per ADR-FI §4.4.2 caller contract(Q-PR1 carve-out)
- `core/evidence/write_protocol.py:226` `replace_field` internal reuse — same
- `core/derivation/accept.py:401` derivation rollback `retract_by_asrt` — **internal rollback path,NOT user-facing**;intentionally unguarded(per §6.3 classification + N11)

### 4.2 Active design constraints

- ADR-IC §4.1-§4.4 + 4 sub-decisions binding
- ADR-IC §4.3.6 explicit contract requirement on ADR-API Q14:schema.extend MUST reject Identity↔Field swap;cache union semantics(§4.3.3)assumes this — Slice 2 hook stays carry-forward(no stub per OQ3)
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency
- ADR-DOCS §4.2.2 Slice 2 load-bearing docs

### 4.3 Historical context

- Slice 1 Form I baseline(`9cef674b`)— `_DataMember` + Identity()/Field() Form I + write-time validation + 8/8 primary_key removal sites
- Per ADR-IC §4.2.5 ADR-FI 衔接 — Slice 1 已 cleanup `schema_compile.py:258-259` primary_key dead code

## 5. Proposed Shape

### 5.1 SchemaIndex cache extension(`application/schema_runtime.py`)

Extend `SchemaIndex` frozen dataclass with two independent caches + union helper:

```python
@dataclass(frozen=True)
class SchemaIndex:
    schema_ir: dict[str, Any]
    schema_digest: str
    entities: dict[str, EntityTypeInfo]
    field_predicates: dict[tuple[str, str], PredicateInfo]
    predicates_by_id: dict[str, PredicateInfo]
    identity_pred_ids: frozenset[str]    # NEW — Identity Claim pred_ids (INV-7c)
    exists_pred_ids: frozenset[str]      # NEW — :exists Claim pred_ids (transitional guard)

    @property
    def protected_anchor_pred_ids(self) -> frozenset[str]:
        return self.identity_pred_ids | self.exists_pred_ids
```

**Build path**(`build_schema_index` extension):
```python
identity_pred_ids = frozenset(
    info.pred_id for info in predicates_by_id.values()
    if info.is_identity_field
)
exists_pred_ids = frozenset(
    info.pred_id for info in predicates_by_id.values()
    if info.is_entity_exists
)
```

**Per SF9** — 必须是两个**独立** frozenset。`_protected_anchor_pred_ids` 是读 helper,**不**作为 storage 单一 set。Step 2+ 移除 `:exists` 时 `exists_pred_ids` → empty,INV-7c 范围不受影响。

### 5.2 Application source-of-truth retract guard(`application/retract_guard.py` NEW)

```python
"""Application-layer retract guard for INV-7c + existence-claim transitional guard.

This is the SHARED retract validation surface — called by:
- SDK shell fail-fast path: SDKStore.retract
- Application ingest path: ingest_runtime._apply_retract
- Application entity_write path: entity_write._apply_op retract branch

NOT called from:
- Protocol direct path (core/evidence/write_protocol.retract_by_asrt) — per ADR-FI §4.4.2
  caller contract; protocol layer schema-agnostic per Q-PR1 carve-out
- Internal rollback path (core/derivation/accept.py:401) — internal derivation rollback,
  NOT user-facing; intentionally unguarded per ADR-IC §6.3 N11 classification
"""

class RetractGuardError(Exception):
    code: str        # "INV_7C_IDENTITY_PROTECTED" or "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
    pred_id: str
    asrt_id: str
    classification: Literal["identity", "exists"]

def classify_retract_target(
    asrt_id: str,
    *,
    ledger: Ledger,
    schema_index: SchemaIndex,
) -> Literal["identity", "exists", "field"]:
    """Classify what kind of Claim the asrt_id targets.

    Returns:
      "identity" — Identity Claim, INV-7c protected
      "exists"   — :exists Claim, existence-claim transitional guard
      "field"    — Field Claim, no Slice 2 guard (default allow)
    """
    pred_id = ledger.get_claim_pred_id(asrt_id)  # NEW Ledger helper, or use existing lookup
    if pred_id is None:
        return "field"  # unknown asrt: downstream handles
    if pred_id in schema_index.identity_pred_ids:
        return "identity"
    if pred_id in schema_index.exists_pred_ids:
        return "exists"
    return "field"

def check_retract_allowed(
    asrt_id: str,
    *,
    ledger: Ledger,
    schema_index: SchemaIndex,
) -> None:
    """Raise RetractGuardError if asrt_id is INV-7c-protected or :exists-protected.

    SDK shell catches and maps to SDKStoreError per ADR-IC §4.1 error messages.
    Application paths catch and produce ErrorDTO with appropriate code.
    """
    classification = classify_retract_target(asrt_id, ledger=ledger, schema_index=schema_index)
    if classification == "identity":
        raise RetractGuardError(
            code="INV_7C_IDENTITY_PROTECTED",
            asrt_id=asrt_id,
            pred_id=pred_id,
            classification="identity",
        )
    if classification == "exists":
        raise RetractGuardError(
            code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD",
            asrt_id=asrt_id,
            pred_id=pred_id,
            classification="exists",
        )
```

Per SF2(P2 wording precision)— this is **application source-of-truth**;SDK shell and application ingest/entity_write paths are **consumers**。

### 5.3 SDK shell fail-fast wrap(`sdk/store.py:SDKStore.retract`)

```python
def retract(self, asrt_id: str, *, meta: dict[str, Any] | None = None) -> str | None:
    self._reject_attached_write("fg.retract")
    try:
        check_retract_allowed(asrt_id, ledger=self._store.ledger, schema_index=self._application_schema_index)
    except RetractGuardError as exc:
        if exc.classification == "identity":
            raise SDKStoreError(
                f"Identity Claim {asrt_id} (pred_id={exc.pred_id}) is immutable per INV-7c.\n"
                f"Identity Claims can only be:\n"
                f"  - created via fg.entities.create(EntityCls, **identity_kwargs)\n"
                f"  - removed as part of fg.entities.delete(e_ref) (atomic full-entity revoke)\n"
                f"To modify the identity bundle of an entity, delete the old entity and "
                f"create a new one with the new identity values (Identity is immutable per INV-7a)."
            )
        if exc.classification == "exists":
            raise SDKStoreError(
                f"<EntityType>:exists Claim {asrt_id} (pred_id={exc.pred_id}) cannot be retracted "
                f"independently. The :exists Claim is co-emitted atomically with Identity Claims "
                f"and can only be removed via fg.entities.delete(e_ref) (atomic full-entity revoke). "
                f"This guard is transitional — Step 2+ may remove :exists emission entirely "
                f"(see ADR-IC §4.4)."
            )
    return retract_by_asrt(self._store.ledger, asrt_id, meta)
```

### 5.4 Application ingest path wrap(`application/ingest_runtime.py:_apply_retract`)— **P1 fix**

```python
def _apply_retract(idx, item, *, store):
    try:
        check_retract_allowed(item.assertion_id, ledger=store.ledger, schema_index=store.schema_index)
    except RetractGuardError as exc:
        return ([
            ErrorDTO(
                code=exc.code,  # "INV_7C_IDENTITY_PROTECTED" or "EXISTENCE_CLAIM_TRANSITIONAL_GUARD"
                message=...,    # per ADR-IC §4.1 wording
                path=("items", str(idx)),
                details={"assertion_id": item.assertion_id, "pred_id": exc.pred_id},
            )
        ], [], [], [])

    try:
        revoker_id = retract_by_asrt(store.ledger, item.assertion_id, dict(item.meta) or None)
        # ... existing success path
    except Exception as exc:
        # ... existing failure path (INGEST_RETRACT_FAILED)
```

### 5.5 Application entity_write path wrap(`application/entity_write.py:_apply_op` retract branch)

```python
# In _apply_op around line 412:
elif op.op == "retract":
    check_retract_allowed(op.assertion_id, ledger=store.ledger, schema_index=store.schema_index)
    return retract_by_asrt(store.ledger, op.assertion_id, dict(op.meta) if op.meta else None)
```

`RetractGuardError` 在 entity_write 路径 maps 到 `EntityWriteError`(same pattern as Slice 1 value validation,per ADR-FI §4.4.2 integration model)。

### 5.6 Protocol/core direct path classification(NOT modified — SF5 + N11)

| Path | Classification | Modification |
|---|---|---|
| `core/evidence/write_protocol.py:170` `retract_by_asrt` | Protocol layer schema-agnostic per ADR-FI §4.4.2 caller contract + Q-PR1 carve-out | **0 diff** |
| `core/evidence/write_protocol.py:226` `replace_field` internal reuse | Protocol-internal | **0 diff** |
| `core/derivation/accept.py:401` derivation rollback `retract_by_asrt` | **Internal derivation rollback,NOT user-facing**;Slice 2 不 guard 但 blueprint 显式 classify(per N11 — reviewer 不可误判为漏)| **0 diff** |

### 5.7 Error messages update(`sdk/facade.py:IdentityEditor` + `application/entity_write.py:plan_write_command`)

Per ADR-IC §4.1 wording:
```python
raise SDKStoreError(
    f"Identity field {field_name} is immutable per INV-7c. "
    f"To modify the identity bundle of an entity, delete the old entity "
    f"(fg.entities.delete(e_ref)) and create a new one with the new identity "
    f"values (Identity is immutable per INV-7a)."
)
```

Both `IdentityEditor.set/add/retract`(facade.py:469-479)和 `plan_write_command`(entity_write.py:186-192)更新 error message。

### 5.8 Shadow store legacy documentation(`sdk/store.py:923` + comments)

Add class-level comment:
```python
# _identity_values_by_e_ref: LEGACY / INTERNAL COMPATIBILITY only.
# Per ADR-IC §4.2.3, the SDK shell shadow store is NOT part of Layer 2 fields API contract;
# it exists as a compatibility detail to let `fg.set(Field, e_ref_string, value)` succeed
# when shadow store has previously seen this e_ref (via prior sdk.ref() call).
# - e_ref NOT in shadow store → fail-fast UNRESOLVABLE_E_REF (per §4.2.1 emission input contract)
# - e_ref in shadow store → lazy materialization through `_materialization_ops` (legacy compat)
# Step 2+ direction (per ADR-IC §4.2.4): eager emission at fg.entities.create + shadow store removal.
# Slice 2 does NOT remove shadow store (compatibility preservation).
self._identity_values_by_e_ref: dict[str, dict[str, Any]] = {}
```

### 5.9 `:exists` transitional guard naming(SF10 — explicit non-INV-7c)

Per ADR-IC §4.4.2:`:exists` Claim 保护**不**复用 INV-7c 命名。Reject 路径 / error code / docs 必须使用 `existence-claim transitional guard` 命名:
- `RetractGuardError.classification == "exists"`(NOT "identity")
- Error code `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`(NOT `INV_7C_*`)
- Docs 显式说明 transitional contract:Step 2+ 评估移除 `:exists` 时 guard 同步退役;INV-7c 范围不会因此收窄

### 5.10 Schema evolution hook(carry-forward to ADR-API Q14 — SF4)

Slice 2 **NOT** create `fg.schema.register/extend/apply` stub APIs。Cache build path stays at `build_schema_index`(called during `Store.__init__`/`FactGraph.create`)。ADR-API Q14 implementation slice will:
- Add `fg.schema.register/extend/apply` namespace
- Wire schema-evolution hook to rebuild `identity_pred_ids` + `exists_pred_ids` frozensets per ADR-IC §4.3.3

Slice 2 blueprint records this **carry-forward dependency** in §10 Outcome。

## 6. Boundaries And Invariants

### 6.1 Scope Freeze(LOCKED — must remain through implementation)

| # | Lock | Source |
|---|---|---|
| **SF1** | `SchemaIndex` hosts both `_identity_pred_ids` + `_exists_pred_ids` frozensets and `_protected_anchor_pred_ids` union property | OQ1 verdict 2026-05-29 |
| **SF2** | **Three-layer enforcement model**:(i)application source-of-truth = `application/retract_guard.py` shared helper;(ii)SDK shell fail-fast = `SDKStore.retract`;(iii)protocol/core direct path = schema-agnostic,intentionally unguarded per Q-PR1 carve-out + ADR-FI §4.4.2 | OQ2 + P2 verdict 2026-05-29 |
| **SF3** | **Application-layer retract guard MUST cover all 3 application-or-above entry points**:SDKStore.retract(SDK shell)+ ingest_runtime._apply_retract(application ingest)+ entity_write._apply_op retract branch(application entity_write)— bulk ingest bypass risk closed | P1 verdict 2026-05-29 |
| **SF4** | **NO `fg.schema.register/extend/apply` stub** in Slice 2;hook-ready contract documented but no empty API created;wiring deferred to ADR-API Q14 implementation slice | OQ3 verdict 2026-05-29 |
| **SF5** | Q-PR1 carve-out preserved:zero diff in `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `claims.rest_terms` / INV-9 runtime strict / **`core/derivation/accept.py:401` internal rollback path** | OQ4 verdict 2026-05-29 + N11 classification |
| **SF6** | Slice 2 load-bearing docs only:`04_api_surface.en.md`(INV-7c reject + existence-claim transitional guard + Identity Claim emission + shadow store legacy)+ `identity-mechanism-redesign.zh.md §5.2/§13`;wider docs polish 留 Slice 4 | OQ5 verdict + ADR-DOCS §4.2.2 |
| **SF7** | **Tests directory(`tests/`)IS in scope for Slice 2**(Slice 1 SF6 factgraph-only correction NOT inherited)— BUT only NEW Slice 2 test files for cache + guard + emission contract;legacy `Identity(primary_key=)` test fixtures from pre-Slice-1 remain as legacy carryover(out of Slice 2 scope) | OQ6 verdict 2026-05-29 |
| **SF8** | Identity Claim emission contract:**MUST carry complete identity bundle**(per ADR-IC §4.2.1);Layer 2 fields API(`fg.set/add/...`)is NOT and NEVER an emission path;shadow store is legacy compatibility,not contract | ADR-IC §4.2.1 + §4.2.2 + §4.2.3 |
| **SF9** | **Two independent frozensets**(NOT single set)— `_identity_pred_ids` 和 `_exists_pred_ids` 概念分离;`_protected_anchor_pred_ids` 仅是读 helper property;Step 2+ 移除 `:exists` 时 INV-7c 范围不收窄 | ADR-IC §4.3.1 |
| **SF10** | `:exists` guard 命名 = **existence-claim transitional guard**,**NOT** INV-7c;error code = `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`;`:exists` co-emission 跟 guard lifecycle 绑定,Step 2+ 移除 `:exists` 时 guard 同步退役不影响 INV-7c | ADR-IC §4.4.2 |
| **SF11** | `core/derivation/accept.py:401` derivation rollback path **intentionally unguarded** — internal rollback,NOT user-facing;Blueprint **MUST** explicitly classify in §6.3 to prevent reviewer 误判为漏 | N11 reviewer 2026-05-29 |
| **SF12** | Error message wording per ADR-IC §4.1:Identity reject 含 `INV-7c` reference + delete+create migration hint;`:exists` reject 含 `existence-claim transitional guard` reference + transitional contract note + ADR-IC §4.4 pointer | ADR-IC §4.1 |

### 6.2 Compatibility constraints + dirty baseline guard

- Sacred `master` `562c74195df43e933bed92a3ff25de94dd8ce666` 不动
- Sacred `v0.1-oss-prep` 不动
- Dirty baseline(4 M + 1 D + 2 untracked,unrelated to identity-as-claim)preserved through all commits
- Branch lineage:每次 commit verify HEAD ancestor includes ADR-IC `2d0866ed` + ADR-DOCS `bb6a2c90` + synthesis `d0036e1f` + Slice 1 close `9cef674b`

**Tests directory scope clarification**(SF7):
- `tests/` IN scope for Slice 2 — Slice 1 SF6 factgraph-only was a Slice 1 scope correction,NOT a slice-wide convention
- New Slice 2 test files exercise:cache build correctness + retract guard 3 classifications + Identity Claim emission atomic + shadow store legacy 2 paths
- Legacy `tests/` files using pre-Slice-1 `Identity(primary_key=)` etc. stay as legacy(out of Slice 2 scope per N11-style classification — NOT a Slice 2 obligation)

### 6.3 Q-PR1 carve-out invariant + internal-rollback classification

**Q-PR1 carve-out — zero diff(Slice 2 enforcement gate)**:
- `core/evidence/write_protocol.py` 0 diff(protocol layer schema-agnostic per ADR-FI §4.4.2)
- `core/store/ledger.py` 0 diff
- `core/store/_builders.py` 0 diff(D11 cleanup is Slice 2 ADR-IC §4.3.1 cache integration — actually that's the SchemaIndex cache build in `application/schema_runtime.py`,NOT `_builders.py`)
- `adapters/pyreason/*` 0 diff
- `claims.rest_terms` 0 diff
- No INV-9 runtime strict assertion added

**Internal-rollback classification(SF11 explicit)**:
- `core/derivation/accept.py:401` `retract_by_asrt` direct call — **internal derivation rollback,intentionally unguarded**
- Rationale:derivation rollback 在 derivation 失败时撤销已写入的 derived Claims;它不会 touch Identity Claims(只 touch derived field Claims by definition of derivation output);若 derivation engine 错误产生 Identity Claim,那是 derivation engine bug,需要 Step 2+ ADR fix derivation engine,not Slice 2 retract guard
- Slice 2 blueprint §6.3 + §10 Outcome 必须显式记录 this classification — 防 reviewer 误判为遗漏

**Q-PR1 carve-out + 内部 rollback 一起作为 Slice 2 close 前 grep verification gate**。

### 6.4 ADR-DOCS §4.2.2 load-bearing docs invariant

Slice 2 may NOT mark `implemented` unless these docs land in the same slice:

- `src/factgraph/sdk/docs/04_api_surface.en.md`:
  - INV-7c reject 行为表(包含 `fg.fields.*(Identity, ...)`(Layer 2)+ `fg.retract(asrt_id)`(Layer 3 asrt)双路径)
  - existence-claim transitional guard 说明(命名 + lifecycle + Step 2+ 评估移除 transitional contract)
  - Identity Claim emission 说明(application 层 derive + 必须携带完整 identity bundle + `_materialization_ops` shipped path)
  - Shadow store legacy 定位(`_identity_values_by_e_ref` is compatibility detail,NOT Layer 2 contract;e_ref-not-seen → fail-fast UNRESOLVABLE_E_REF)
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §5.2 + §13`:
  - §5.2 INV-7a/b/c 跟 ADR-IC §4.1-§4.4 adopted wording 对齐
  - §13(Step 1 in-scope / Step 2+ 延后)Slice 2 landed status note

Per ADR-DOCS §4.1.2 Dimension B:design-point sync IS load-bearing in this slice。

## 7. Acceptance

### 7.1 SchemaIndex cache extension(G1 + SF1/SF9)

- [ ] `SchemaIndex.identity_pred_ids: frozenset[str]` field exists
- [ ] `SchemaIndex.exists_pred_ids: frozenset[str]` field exists
- [ ] `SchemaIndex.protected_anchor_pred_ids` property returns union of two
- [ ] `build_schema_index` populates both frozensets from `PredicateInfo.is_identity_field` / `.is_entity_exists`
- [ ] Test:fixture schema with 2 entity types(User + Order),each with 2 identity fields → identity_pred_ids has 4 members;exists_pred_ids has 2 members
- [ ] Test:Empty schema_ir → both frozensets are `frozenset()` (empty);union property is also empty

### 7.2 Application retract guard helper(G2 + SF2)

- [ ] `application/retract_guard.py` module exists
- [ ] `RetractGuardError(Exception)` with `code`/`pred_id`/`asrt_id`/`classification` fields
- [ ] `classify_retract_target(asrt_id, *, ledger, schema_index)` returns one of `"identity"`/`"exists"`/`"field"`
- [ ] `check_retract_allowed(asrt_id, *, ledger, schema_index)`:
  - identity classification → raise `RetractGuardError(code="INV_7C_IDENTITY_PROTECTED", classification="identity")`
  - exists classification → raise `RetractGuardError(code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD", classification="exists")`
  - field classification(default)→ no raise(allow downstream `retract_by_asrt`)
- [ ] Test:Identity Claim asrt → identity classification → raise INV_7C
- [ ] Test:`:exists` Claim asrt → exists classification → raise EXISTENCE_CLAIM_TRANSITIONAL_GUARD
- [ ] Test:Field Claim asrt → field classification → no raise
- [ ] Test:Unknown asrt → field classification(downstream handles)→ no raise
- [ ] **Error code distinction**:Identity vs exists produce DIFFERENT codes(`INV_7C_IDENTITY_PROTECTED` vs `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`) — caller can distinguish per ADR-IC §8 acceptance

### 7.3 SDK shell fail-fast wrap(G3 + SF2 + SF12)

- [ ] `SDKStore.retract(asrt_id)` calls `check_retract_allowed` BEFORE `retract_by_asrt`
- [ ] Identity Claim asrt → `SDKStoreError` with INV-7c wording per ADR-IC §4.1(含 delete+create migration hint)
- [ ] `:exists` Claim asrt → `SDKStoreError` with existence-claim transitional guard wording + ADR-IC §4.4 pointer
- [ ] Field Claim asrt → passes through to `retract_by_asrt`(no guard)
- [ ] Test:`fg.retract(identity_claim_asrt_id)` raises `SDKStoreError` with INV-7c reference
- [ ] Test:`fg.retract(exists_claim_asrt_id)` raises `SDKStoreError` with existence-claim transitional guard reference
- [ ] Test:`fg.retract(field_claim_asrt_id)` succeeds
- [ ] **Error message classification**:Identity vs exists produce distinguishable error wording

### 7.4 Application ingest path wrap(G3 + SF3 — P1 fix)

- [ ] `application/ingest_runtime._apply_retract` calls `check_retract_allowed` BEFORE `retract_by_asrt`
- [ ] Identity Claim asrt → `ErrorDTO(code="INV_7C_IDENTITY_PROTECTED", ...)` in ingest result
- [ ] `:exists` Claim asrt → `ErrorDTO(code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD", ...)` in ingest result
- [ ] Field Claim asrt → passes through(existing `INGEST_RETRACT_FAILED` path on actual retract failure)
- [ ] Test:bulk ingest with Identity Claim retract item → ErrorDTO with INV-7c code

### 7.5 Application entity_write path wrap(G3 + SF3)

- [ ] `application/entity_write._apply_op` retract branch calls `check_retract_allowed` BEFORE `retract_by_asrt`(line 412)
- [ ] Identity Claim asrt → `EntityWriteError` mapped from `RetractGuardError`
- [ ] `:exists` Claim asrt → `EntityWriteError` mapped from `RetractGuardError`
- [ ] Field Claim asrt → passes through
- [ ] Test:entity write with retract op for Identity Claim asrt → `EntityWriteError`

### 7.6 Protocol/core direct path zero diff(G7 + SF5 + SF11)

- [ ] `core/evidence/write_protocol.py` 0 diff(grep verified)
- [ ] `core/store/ledger.py` 0 diff
- [ ] `core/store/_builders.py` 0 diff
- [ ] `adapters/pyreason/*` 0 diff
- [ ] `core/derivation/accept.py:401` `retract_by_asrt` direct call **0 diff**(internal rollback per SF11 classification)
- [ ] No INV-9 runtime strict assertion added

### 7.7 Error messages update(G4 + SF12)

- [ ] `sdk/facade.py:IdentityEditor.set/add/retract` error wording per ADR-IC §4.1(INV-7c reference + delete+create migration hint + ADR-IC §4.1 pointer)
- [ ] `application/entity_write.py:plan_write_command` `pred_info.is_identity_field` check error wording per ADR-IC §4.1
- [ ] Test:`IdentityEditor(...).set(value)` error message contains `INV-7c` literal + `fg.entities.delete` migration hint
- [ ] Test:`plan_write_command` `is_identity_field` path error message contains same

### 7.8 Shadow store legacy(G5)

- [ ] `sdk/store.py:923` class field has legacy comment per §5.8
- [ ] Test:e_ref never seen by shadow store + first write → `UNRESOLVABLE_E_REF` raise(existing behavior — verify carries forward)
- [ ] Test:e_ref seen by shadow store + first write → Identity Claims + `:exists` atomic emit(shipped lazy compatibility path)
- [ ] Identity Claims + `:exists` Claim atomic write in same `_write_session`

### 7.9 Form I + Identity Claim emission integration(G7 — cross-Slice contract)

- [ ] `fg.entities.create(EntityCls, **identity_kwargs)` atomic emit:N Identity Claims + 1 `:exists` Claim(N = identity field count)— in single `_write_session`
- [ ] `fg.entities.delete(e_ref)` atomic full revoke:all Identity Claims + `:exists` Claim + all Field Claims for that e_ref retracted
- [ ] Test:`fg.entities.create(User, user_id="u1", tenant_id="t1")` → ledger Active set increases by 3(2 Identity + 1 `:exists`)
- [ ] Test:`fg.entities.delete(e_ref)` followed by Active set query → 0 active Claims for that e_ref

### 7.10 Load-bearing docs(G6 + ADR-DOCS §4.2.2)

- [ ] `sdk/docs/04_api_surface.en.md`:
  - INV-7c reject 行为表(Layer 2 fields + Layer 3 asrt 双路径)— landed
  - existence-claim transitional guard 说明 — landed
  - Identity Claim emission 说明 — landed
  - Shadow store legacy 定位 — landed
- [ ] `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §5.2 + §13`:
  - §5.2 aligned with ADR-IC §4.1-§4.4 adopted wording — landed
  - §13 Slice 2 landed status note — landed
- [ ] §10 Outcome explicitly confirms load-bearing docs landed

### 7.11 Q-PR1 carve-out preservation(G7 + SF5)

- [ ] Final grep:`git diff --name-only HEAD~N..HEAD -- core/evidence/write_protocol.py core/store/ledger.py core/store/_builders.py adapters/pyreason/ core/derivation/accept.py` returns 0 results

### 7.12 Per-commit verification ritual(G8)

- [ ] Every commit:`git rev-parse master` = `562c74195df43e933bed92a3ff25de94dd8ce666`
- [ ] Every commit:dirty baseline(4 M + 1 D + 2 untracked)preserved
- [ ] Every commit:branch lineage ancestor includes ADR-IC `2d0866ed` + ADR-DOCS `bb6a2c90` + synthesis `d0036e1f` + Slice 1 close `9cef674b`

## 8. Implementation Plan

Per `feedback_smaller_batch_design_blueprints`,Slice 2 不是 rule-touching(Slice 9 那种)— 但仍 step-by-step commit。

### Step 0 — Pre-impl grep + verification(no code change)

- 0.1 Verify all `retract_by_asrt` call sites:5 sites confirmed(write_protocol.py:170/226,sdk/store.py:2125,ingest_runtime.py:169,entity_write.py:412,derivation/accept.py:401)— matches preflight
- 0.2 Verify `_materialization_ops` + `record_exists` op + `PlannedOpDTO` shipped baseline
- 0.3 Catalog any other unguarded asrt_id paths in application/ — if any new finding,blueprint amend before Step 1
- 0.4 Audit log "Step 0 verification" row;no commit if grep matches preflight

### Step 1 — SchemaIndex cache extension(`application/schema_runtime.py`)

- 1.1 Extend `SchemaIndex` dataclass with `identity_pred_ids` + `exists_pred_ids` frozenset fields + `protected_anchor_pred_ids` property
- 1.2 Extend `build_schema_index` to populate both from `PredicateInfo` iterations
- 1.3 Unit test:fixture schemas verify cache content + empty case + union property
- 1.4 — commit boundary

### Step 2 — Application retract guard helper(`application/retract_guard.py` NEW)

- 2.1 NEW module `application/retract_guard.py` with `RetractGuardError` + `classify_retract_target` + `check_retract_allowed` per §5.2
- 2.2 Identify `Ledger.get_claim_pred_id(asrt_id)` lookup primitive — either reuse existing or add minimal helper to Ledger(if needed,that's a question for Step 0 to verify)
- 2.3 Unit test:4 cases(identity / exists / field / unknown asrt)
- 2.4 — commit boundary

### Step 3 — SDK shell wrap(`sdk/store.py:SDKStore.retract`)

- 3.1 Add `check_retract_allowed` call before `retract_by_asrt`
- 3.2 Map `RetractGuardError` to `SDKStoreError` per §5.3 wording
- 3.3 Integration test through `fg.retract(asrt_id)` — Identity / exists / field 3 cases
- 3.4 — commit boundary

### Step 4 — Application ingest path wrap(`application/ingest_runtime.py:_apply_retract`)— **P1 fix**

- 4.1 Add `check_retract_allowed` call before `retract_by_asrt`
- 4.2 Map `RetractGuardError` to `ErrorDTO(code=..., message=..., path=("items", str(idx)), ...)`
- 4.3 Integration test through bulk ingest retract — Identity / exists / field 3 cases
- 4.4 — commit boundary

### Step 5 — Application entity_write path wrap(`application/entity_write.py:_apply_op`)

- 5.1 Add `check_retract_allowed` call before `retract_by_asrt` in retract branch
- 5.2 Map `RetractGuardError` to `EntityWriteError`
- 5.3 Unit test
- 5.4 — commit boundary

### Step 6 — Error messages update(`sdk/facade.py:IdentityEditor` + `application/entity_write.py:plan_write_command`)

- 6.1 Update `IdentityEditor.set/add/retract` error wording per ADR-IC §4.1
- 6.2 Update `plan_write_command` `is_identity_field` check error wording per ADR-IC §4.1
- 6.3 Test:error message contains `INV-7c` literal + migration hint
- 6.4 — commit boundary

### Step 7 — Shadow store legacy documentation(`sdk/store.py:923`)

- 7.1 Add class-level comment per §5.8
- 7.2 (No behavior change,doc-only)
- 7.3 — commit boundary

### Step 8 — Contract tests(emission atomic + Identity bundle + entity delete)

- 8.1 Test:`fg.entities.create(User, ...)` atomic emit N Identity Claims + 1 `:exists` Claim
- 8.2 Test:`fg.entities.delete(e_ref)` atomic full revoke
- 8.3 Test:Identity Claims atomic with first Field write(lazy materialization path)
- 8.4 Test:e_ref not in shadow store → UNRESOLVABLE_E_REF
- 8.5 — commit boundary

### Step 9 — Load-bearing docs sync

- 9.1 `sdk/docs/04_api_surface.en.md`:INV-7c reject 行为表 + existence-claim transitional guard + Identity Claim emission 说明 + shadow store legacy 定位
- 9.2 `identity-mechanism-redesign.zh.md §5.2 + §13`:跟 ADR-IC adopted wording 对齐 + §13 Slice 2 landed status note
- 9.3 — commit boundary

### Step 10 — Final acceptance + §10 Outcome

- 10.1 Run all §7 acceptance checks
- 10.2 Verify §6.1 Scope Freeze items still locked
- 10.3 Verify §6.3 Q-PR1 carve-out 0 diff via grep
- 10.4 Verify §6.3 internal-rollback `core/derivation/accept.py:401` 0 diff + classification preserved
- 10.5 Fill §10 Outcome:final landing + deviations + grep verification + carry-forward dependencies(ADR-API Q14 schema-evolution hook,Step 2+ `:exists` removal + shadow store removal eager-emission演化)
- 10.6 Mark `Status: implemented` + audit log final row
- 10.7 — commit boundary(Slice 2 close)

## 9. Docs To Update

### 9.1 Slice 2 load-bearing(per ADR-DOCS §4.2.2 — MUST land in this slice)

- `src/factgraph/sdk/docs/04_api_surface.en.md`:
  - INV-7c reject 行为表(Layer 2 fields-Identity + Layer 3 asrt-id 双路径)
  - existence-claim transitional guard 说明(命名 + lifecycle + transitional contract)
  - Identity Claim emission 说明(application 层 derive + 必须携带完整 identity bundle)
  - Shadow store legacy 定位 + UNRESOLVABLE_E_REF fail-fast behavior
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`:
  - §5.2 INV-7a/b/c aligned with ADR-IC §4.1-§4.4 adopted wording
  - §13 Step 1 status note:Slice 2 landed(Identity-as-Claim core implementation complete)

### 9.2 Module docs

- `src/factgraph/application/docs/`(if exists)— `retract_guard.py` 新 module + `SchemaIndex` cache extension 简介

### 9.3 Out-of-slice docs(Slice 4 Phase 2 or downstream)

- Public quickstarts outside `04_api_surface.en.md`(`first-factgraph.md` / `assertions.md` / etc.)terminology cross-doc consistency,5-pass polish per ADR-DOCS §4.3
- Module-wide migration note placement consolidation

### 9.4 Excluded(per SF6 + SF7)

- `workflow/heritage/` / `workflow/blueprints/archive/` / `workflow/design/design-points/archive/` — historical
- `docs/references/working/` / `docs/references/bridges/` / `workflow/audit/active/` — non-load-bearing
- `examples/archive/` — archived
- `tools/` — non-runtime per Slice 1 SF6(carry-forward classification — still no-runtime imports in Slice 2)
- Legacy `tests/` files using pre-Slice-1 `Identity(primary_key=)` etc. — NOT Slice 2 obligation per SF7

## 10. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- Step 0 pre-impl verification results:
- Cache build correctness verification(SchemaIndex.identity_pred_ids + exists_pred_ids):
- Retract guard 3-classification verification(SDKStore.retract + ingest_runtime + entity_write 3 paths):
- Q-PR1 carve-out preservation confirmation(write_protocol + ledger + adapter + _builders + claims.rest_terms 0 diff):
- Internal rollback classification confirmation(core/derivation/accept.py:401 0 diff per SF11):
- Slice 2 load-bearing docs landed confirmation:
- Carry-forward dependencies recorded:
  - ADR-API Q14 schema-evolution hook(`fg.schema.register/extend/apply` 实施时 wire cache hook per ADR-IC §4.3.3)
  - Step 2+ `:exists` removal(per ADR-IC §4.4.4 forward-pointer)— guard 同步退役不动 INV-7c
  - Step 2+ shadow store removal(per ADR-IC §4.2.4 eager-emission 演化方向)
- 归档说明:
