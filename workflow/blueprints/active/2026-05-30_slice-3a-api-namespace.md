# Slice 3a — API namespace refactor(Q10-Q14 cluster:三层 namespace rename + AssertionView 统一 + `version(v)` / flat kwargs 删 + `fg.schema.add` 三分)

- Status: draft
- Created: 2026-05-30
- Last Updated: 2026-05-30
- Branch: `v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30` @ `b17750c8`(preflight + amend);fork from Slice 2 close `c927d41f`
- Related Modules:
  - `src/factgraph/sdk/store.py`(4 namespace manager classes + 8 flat top-level methods)
  - `src/factgraph/sdk/facade.py`(`AssertionRecordSet` + `FieldAssertions` + `AssertionNamespace` + `EntityEditor` + `IdentityEditor` + `FieldEditor` + `sdk_edit`)
  - `src/factgraph/sdk/batch.py`(`SDKBatchTx` + `ManagedEntityHandle` — read/migrate `tx.entity(...).field.set(...)` 路径 alignment)
  - `src/factgraph/application/entity_write.py`(NEW `delete_entity_command` DTO + planner + executor for `fg.entities.delete` per PF-S3)
  - `src/factgraph/application/schema_runtime.py`(SchemaIndex cache rebuild hook on `fg.schema.extend` per Slice 2 §10.9 carry-forward)
- Related Docs:
  - [Slice 3a preflight audit](../../audit/active/2026-05-30_slice-3a-api-namespace-preflight.md) — pre-blueprint code audit + 8 PF-S verdicts inherited into §6 Scope Freeze
  - [ADR-API](../../design/decisions/active/2026-05-29_q-api-namespace-decision.md) adopted `66434490` — Q10-Q14 主源
  - [meta-ADR](../../design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md) adopted `ebafdb0c` — §4.2 grouping lock + §4.4 Q-PR1 separation contract
  - [ADR-IE](../../design/decisions/active/2026-05-29_q-ie-entity-editor-decision.md) adopted `9fd0ffb5` — EntityEditor public contract 衔接
  - [ADR-IC](../../design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md) adopted `2d0866ed` — §4.3.6 explicit contract part 1+2 implemented at `fg.schema.extend`
  - [ADR-DOCS](../../design/decisions/active/2026-05-29_q-docs-sync-decision.md) adopted `bb6a2c90` — §4.2.2 load-bearing docs invariant
  - [identity-mechanism-redesign.zh.md](../../design/design-points/active/identity-mechanism-redesign.zh.md) §12/§13 — Slice 3a load-bearing per PF-S7
- Audit Log:
  - [2026-05-30_slice-3a-api-namespace.audit.md](./2026-05-30_slice-3a-api-namespace.audit.md)

## 1. Problem

Slice 2 close 之后,**ADR-API Q10-Q14 cluster(`66434490` adopted 2026-05-29)是 Slice 2 §10.9 列出的最大 carry-forward dependency**:

- Slice 2 Step 6 IdentityEditor + plan_write_command 错误文案已用 ADR-IC §4.1 adopted wording 引用 `fg.entities.delete(e_ref) + fg.entities.create(EntityCls, **new_identity_kwargs)` 作为 user migration guidance,但这两个 API **未 shipped**(per P1 #3 amend);user 实际无法执行该 migration。Slice 3a 必须把这两个 API 落地,让 Slice 2 错误文案 actionable。
- shipped `fg.read.*` / `fg.write.*` / `fg.assertions.*` / `fg.schema.add` 4 个 namespace 形态跟 ADR-API §4.1.1 三层排他边界 navigation key 模型不一致(`fg.write.retract(asrt_id)` 用 Layer 3 nav key 在 Layer 2 namespace;`fg.write.edit(EC, **id)` 用 Layer 1 nav key 在 Layer 2 namespace)— 三层 navigation key 排他原则不能 enforce。
- ADR-IC §4.3.6 explicit contract(`fg.schema.extend` 拒绝 Identity↔Field swap + `<EntityType>:exists` predicate protect)是 Slice 2 SchemaIndex frozensets cache(`73993ebd`)的**前提**;Slice 2 SF4 NO-stub 决策必须由 Slice 3a 落地。
- shipped `AssertionRecordSet.where(*, value, source, trace_id, version, meta)` flat kwargs signature 跟 ADR-API §4.4 `_meta` 统一签名不一致;`version(v)` 一等方法跟 §4.3 招纳原则不一致。

Slice 3a 完成后 Step 1 Slice 1 + 2 + 3a + 3b(后续)+ 4 链上 Slice 3a 部分 close,Slice 3b(ledger migration)可独立平行启动(per Stage 1 audit §10.2 dep 图)。

## 2. Goals

| G | 目标 | Source |
|---|---|---|
| **G1** | **三层 namespace rename + 排他 navigation key**:`fg.read.*` / `fg.write.*` namespace 整删(alpha 直接 breaking + 无 alias 无双轨);新增 `fg.entities.*`(Layer 1,EntityClass + identity 或 e_ref nav key)+ `fg.fields.*`(Layer 2,Field + e_ref + value nav key);`retract(asrt_id)` 挪 `fg.assertions.*`(Layer 3,asrt_id nav key);`edit(EC, **id)` 挪 `fg.entities.edit`(Layer 1) | ADR-API §4.1 Q10 |
| **G2** | **`fg.entities.create/delete/exists` 三个 NEW Layer 1 method**:`create` 走 application layer eager emission(per ADR-IC §4.2);`delete` 走 application layer 全实体 revoke planner+executor(per ADR-IC §4.1 强制点 3);`exists` 比 `get(...) is None` cheap | ADR-API §4.1.2 + ADR-IC §4.1/§4.2 + Slice 2 §10.9 carry-forward |
| **G3** | **`fg.fields.*` 5 个 method**:`set/add` 从 `fg.write` rename;NEW `retract(F, e_ref, value)` value-oriented + `delete(F, e_ref)` clear-all + `get(F, e_ref)` materialize-current | ADR-API §4.1.2 |
| **G4** | **`AssertionView` 统一类型 + `AssertionsManager` 显式分离**:`FieldAssertions` + `AssertionNamespace` 整删合并入 `AssertionView`(scope-aware 纯读 view);`_SDKAssertionsManager` rename → `AssertionsManager`(Layer 3 namespace manager,承载 `retract(asrt_id)` mutation);NEW `where(*, field=, e_ref=, value=, value_tag=, _meta=)` canonical filter | ADR-API §4.2 Q11 |
| **G5** | **`version(v)` 一等方法 hard remove + flat kwargs hard remove**:`AssertionRecordSet.version(v)` / `FieldAssertions.version(v)` 整删(用 `where(_meta={"version": v})` 替代);`AssertionRecordSet.where(*, value, source, trace_id, version, meta)` flat kwargs(`source/trace_id/version/meta`)整删(替换为 `where(*, field_filters, value, value_tag, _meta)` 签名)| ADR-API §4.3 Q12 + §4.4 Q13 |
| **G6** | **`fg.schema.add` 删除 + 拆三分**:`register(EC)`(新 entity_type 注册 + SchemaIndex cache union update)+ `extend(EC)`(additive Field 扩展 + **ADR-IC §4.3.6 enforce part 1+2**:Identity↔Field swap reject + `<EntityType>:exists` predicate protect)+ `apply(EC)`(safe diff convenience)| ADR-API §4.5 Q14 + ADR-IC §4.3.6 |
| **G7** | **flat top-level shortcuts 全删**(per PF-S1 lock):`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.get` / `fg.ref` / `fg.find` / `fg.match` 8 个 SDKStore 顶层方法全删 — 用户被迫走 `fg.entities.*` / `fg.fields.*` / `fg.assertions.*` namespace 入口;**无 alias 无双轨期** | PF-S1 verdict + ADR-API §4.1.3 |
| **G8** | **Load-bearing docs migration**:同 slice 落地 `04_api_surface.en.md` + `02_readwrite_and_ingest.en.md` + `00_user_guide.en.md` + `identity-mechanism-redesign.zh.md §12/§13`(per PF-S7 lock);wider docs polish + 其他 quickstart files 留 Slice 4 | PF-S7 + ADR-DOCS §4.2.2 |

## 3. Non-goals

- ❌ **shadow store `_identity_values_by_e_ref` removal** — Slice 3a 显式 NOT remove(per ADR-IC §4.2.4 Step 2+ direction);`fg.entities.create` eager emission 路径 + shadow store lazy `fg.ref + fg.set` 路径**共存**(per PF-S4 lock)
- ❌ **`<EntityType>:exists` emission removal** — Step 2+ 评估 per ADR-IC §4.4.4 forward-pointer;Slice 3a `fg.entities.exists` 读 shipped `:exists` Active set
- ❌ **Q-PR1 PyReason adapter rewrite** — per meta-ADR §4.4 Step 1 zero Q-PR1 dependency
- ❌ **INV-9 runtime strict enforcement at protocol layer** — Slice 5+ per meta-ADR §4.4.1
- ❌ **Slice 3b ledger migration**(`__system__.revokes` / claims `value+value_tag` 双列)— 独立 ADR-SYS-B + Slice 3b
- ❌ **Wider docs polish + cross-doc consistency**(`01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md` / public quickstarts / examples deep migration)— Slice 4 per PF-S7
- ❌ **`AssertionView.during(time_range)` / `at(t)` 扩展时间维度方法** — Step 2+ per ADR-API §4.2.2 comment;Slice 3a 只动 `at(t)` 维持 shipped 形态
- ❌ **`fg.schema.extend` 允许 metadata-only diff**(`description` / `pattern` 等)— Step 2+ per ADR-API §4.5.2 last row
- ❌ **`_DataMember` 扩展位**(`validators` / `constraints` / `alias` / `deprecated` / `examples` 共通参数)— Step 2+ per ADR-FI §13.2

## 4. Current Context

### 4.1 Branch + fork point

- Branch:`v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30` @ `b17750c8`(preflight + amend)
- Fork from:Slice 2 close `c927d41f`(`v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` push tip + archive cadence complete)
- Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` 不动;dirty baseline(4 M + 1 D + 2 untracked)preserved
- 4 ADR + Slice 1+2 close 全是 HEAD ancestor

### 4.2 Shipped surface inventory(verified at preflight)

详见 preflight audit doc §3 全 inventory + 行号。摘要:

- **SDK property accessors**:`fg.schema` / `fg.assertions` / `fg.read` / `fg.write`(Slice 3a 改造目标 — 4 个 namespace 中 `read` + `write` 整删,`assertions` rename + type-split,`schema` 加 register/extend/apply)
- **SDK flat top-level shortcuts(8 个)**:`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.get` / `fg.ref` / `fg.find` / `fg.match`(Slice 3a **全删** per PF-S1)
- **AssertionView/FieldAssertions/AssertionNamespace** — Q11 type-split 目标
- **`AssertionRecordSet.where` + `version(v)`** — Q12 + Q13 hard remove 目标
- **`_SDKSchemaManager.add`** — Q14 拆三分目标
- **EntityEditor + IdentityEditor + FieldEditor + sdk_edit** — 公开 contract 不改(per ADR-IE §4.8)

### 4.3 Known constraints

- ADR-API §4.1.3 锁 **alpha 直接 breaking + 无 alias**(`fg.read.*` / `fg.write.*` namespace 整删,无双轨期)
- ADR-IE §4.8 锁 `sdk_edit` factory edit-existing-only contract(EntityEditor 公开 contract 不改)
- ADR-IC §4.3.6 explicit contract part 1(Identity↔Field swap reject)+ part 2(`<EntityType>:exists` predicate protect)由 Slice 3a Q14 `fg.schema.extend` 实施
- meta-ADR §4.4 zero Q-PR1 dependency — Slice 3a 不动 `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py`
- Slice 2 SchemaIndex frozensets cache(`73993ebd`)是 `fg.schema.extend` cache rebuild hook 的基础
- Slice 2 三层 INV-7c retract guard(`187a2918`+`12475859`+`16aeff69`+`a4853a0a`)在 `fg.assertions.retract` 新入口下继续 wrap,**guard 逻辑不动**

### 4.4 Recent blueprint history

- Slice 1 close `9cef674b`(Form I schema refactor)— 提供 stable Identity()/Field() descriptors + SchemaIndex 基础
- Slice 2 close `c927d41f`(Identity-as-Claim core)— SchemaIndex frozensets + 三层 INV-7c enforcement + existence-claim transitional guard + shadow store legacy 文档化 + emission contract tests + load-bearing docs sync

## 5. Proposed Shape

### 5.1 三层 namespace + manager class topology

```python
# Layer 1: fg.entities.* — EntityClass + identity 或 e_ref nav key
class EntitiesManager:
    # 现有(rename from _SDKReadManager + 部分 _SDKWriteManager)
    def get(self, entity_cls, **identity) -> EntitySnapshot | None: ...
    def where(self, entity_cls, *filters, _meta=None) -> EntityCollection: ...     # 原 find
    def match(self, entity_cls, template, ...) -> EntityCollection: ...
    def ref(self, entity_cls, **identity) -> str: ...                              # 维持 shadow store populate
    def edit(self, entity_cls, **identity) -> EntityEditor: ...                    # 挪自 fg.write.edit;sdk_edit factory 不动
    # NEW
    def create(self, entity_cls, *, meta=None, **identity) -> str: ...             # eager emission per ADR-IC §4.2 + PF-S4
    def delete(self, e_ref_or_cls, *, meta=None, **identity) -> int: ...           # 全实体 revoke per ADR-IC §4.1 + PF-S2 discriminated signature
    def exists(self, entity_cls, **identity) -> bool: ...                          # 比 get(...) is None cheap

# Layer 2: fg.fields.* — (Field, e_ref, value) nav key
class FieldsManager:
    # 现有(rename from _SDKWriteManager)
    def set(self, field, e_ref, value, *, meta=None) -> str: ...
    def add(self, field, e_ref, value, *, meta=None) -> str: ...
    # NEW
    def retract(self, field, e_ref, value, *, meta=None) -> str: ...               # value-oriented per ADR-IC §4.1 P2-1
    def delete(self, field, e_ref, *, meta=None) -> int: ...                       # clear all values for (F, e_ref)
    def get(self, field, e_ref) -> Any: ...                                        # materialize current value

# Layer 3: fg.assertions.* — asrt_id 或 canonical filter nav key
class AssertionsManager:                                                           # rename from _SDKAssertionsManager
    # ─ Mutation(唯一 Layer 3 mutation 入口)─
    def retract(self, asrt_id: str, *, meta=None) -> str: ...                      # 挪自 fg.write.retract;Slice 2 retract guard wrap 跟着挪
    # ─ Read shortcuts(委托 _ledger_view: AssertionView)─
    @property
    def active(self) -> AssertionRecordSet: ...
    @property
    def all(self) -> AssertionRecordSet: ...
    def by_id(self, asrt_id) -> AssertionRecord | None: ...
    def by_ids(self, ids, *, strict=True) -> AssertionRecordSet: ...
    def field(self, f: Field) -> AssertionView: ...                                # 返回 AssertionView(scope = ledger + field)
    def where(self, *, field=_ASSERTION_FILTER_MISSING,
              e_ref=_ASSERTION_FILTER_MISSING, value=_ASSERTION_FILTER_MISSING,
              value_tag=_ASSERTION_FILTER_MISSING,
              _meta=_ASSERTION_FILTER_MISSING) -> AssertionRecordSet: ...           # NEW canonical filter
```

### 5.2 三层 navigation key 排他边界 enforcement

跨 layer 用错参数 raise `SDKStoreError`:

| 错用 | error message |
|---|---|
| `fg.fields.set(asrt_id_str, "value")` | `"fg.fields.* requires Field descriptor + e_ref string; pass asrt_id to fg.assertions.* (Layer 3) instead. See ADR-API §4.1.1."` |
| `fg.entities.get(asrt_id_str)` | `"fg.entities.* requires EntityClass + identity_kwargs or e_ref string; pass asrt_id to fg.assertions.by_id(asrt_id). See ADR-API §4.1.1."` |
| `fg.assertions.retract(EntityCls, **identity)` | `"fg.assertions.retract requires asrt_id (Layer 3); pass EntityCls + identity to fg.entities.delete(...). See ADR-API §4.1.1."` |

Enforcement 模式:Python runtime type check(parameter signature 第一个 positional 类型检测)+ raise 含 layer pointer。

### 5.3 `fg.entities.create` shape(per ADR-IC §4.2 + PF-S4)

走 application layer **eager emission**(NEW DTO + planner + executor):

```python
# SDK shell
def fg.entities.create(self, entity_cls, *, meta=None, **identity) -> str:
    # 1. 参数归一化 — validate identity_kwargs 完整
    # 2. 计算 e_ref = idref_v1(entity_type, identity bundle)
    # 3. populate shadow store[e_ref] = identity dict(legacy compat)
    # 4. application layer call:
    command = EntityCreateCommand(
        entity_type=entity_cls.__name__,
        identity=identity,
        command_meta=dict(meta) if meta else {},
    )
    plan = plan_create_command(command, store=self._store, index=self._application_schema_index)
    if not plan.can_apply:
        self._raise_from_application_error(plan.errors[0], op="create")
    result = apply_create_plan(plan, store=self._store, index=self._application_schema_index)
    # 5. 返回 e_ref
    return e_ref
```

**Application layer** — NEW DTOs + functions in `application/entity_write.py`:
- `EntityCreateCommand`(frozen dataclass — entity_type + identity dict + command_meta)
- `plan_create_command`:check entity 不 visible(否则 raise `EntityAlreadyExistsError`)+ build planned_ops via existing `_materialization_ops` 路径(N Identity + 1 `:exists`)
- `apply_create_plan`:execute planned_ops + collect AppliedOpResultDTO

**关键**:`fg.entities.create` 走 `_materialization_ops` 已 shipped 路径(Slice 2 emission contract tests 已验证 atomic;Slice 3a 加入口不动 emission 逻辑)。

### 5.4 `fg.entities.delete` shape(per ADR-IC §4.1 + PF-S2 + PF-S3)

**PF-S2 discriminated signature**:

```python
# Form A: e_ref-based
def fg.entities.delete(self, e_ref: str, *, meta=None) -> int: ...

# Form B: EntityClass + identity_kwargs
def fg.entities.delete(self, entity_cls: type[Entity], *, meta=None, **identity) -> int: ...
```

Runtime overload selection:第一个 positional 参数 `isinstance(arg, str)` → Form A;`isinstance(arg, type) and issubclass(arg, Entity)` → Form B;其他 raise `"fg.entities.delete requires e_ref string OR EntityClass + full identity bundle; see ADR-API §4.1.2"`(per PF-S2 explicit error wording lock)。**Tuple selector 显式 forbidden**。

走 application layer **NEW DTO + planner + executor**(per PF-S3 — SDK manager 只归一化):

```python
# Application layer DTOs (NEW in application/entity_write.py)
@dataclass(frozen=True)
class EntityDeleteCommand:
    target: EntityRef        # e_ref + identity dict
    command_meta: dict

@dataclass(frozen=True)
class EntityDeletePlan:
    command: EntityDeleteCommand
    resolved_target: EntityRef | None
    planned_retracts: tuple[PlannedOpDTO, ...]   # retract ops for all Active Claims (Identity + :exists + Field)
    can_apply: bool
    errors: tuple[ErrorDTO, ...] = ()

def plan_delete_command(command, *, store, index) -> EntityDeletePlan:
    # 1. resolve target(check :exists Active);若不存在 → ErrorDTO(ENTITY_NOT_FOUND)
    # 2. enumerate Active Claims under target.e_ref via ledger.find_claims(e_ref=)
    # 3. build retract PlannedOpDTOs for each(全 Active Claim — Identity + :exists + Field)
    # 4. **关键**:plan_delete 内部直接 build retract PlannedOpDTO,**绕过** Slice 2 retract guard
    #    (because 整批 delete 是 ADR-IC §4.1 唯一合法整批撤销路径 — guard 设计就允许 delete-path 整批 retract Identity Claims)
    # 5. 返回 plan

def apply_delete_plan(plan, *, store, index) -> EntityDeleteResult:
    # atomic execute — 全 retracts 在同 _write_session 内 commit
    # 任一 retract 失败 → rollback session + EntityDeleteResult with errors
```

**关键 enforcement**:`plan_delete_command` 内部 build retract PlannedOpDTOs 时设特殊 marker(e.g. `meta["__delete_via_entities_delete__"] = True`)— `_apply_op` retract branch 见到该 marker 时**跳过** `check_retract_allowed` guard,直接 `retract_by_asrt`(全实体 delete 是合法整批 retract Identity Claim 唯一路径)。Slice 2 retract guard 不动逻辑,但 Slice 3a 在 `_apply_op` 加 marker check 跳过 guard for entity-delete-internal ops。

**SDK manager 只做参数归一化**(per PF-S3 INV-6 application-first):

```python
def fg.entities.delete(self, e_ref_or_cls, *, meta=None, **identity) -> int:
    if isinstance(e_ref_or_cls, str):
        e_ref = e_ref_or_cls
        # validate e_ref managed
    elif isinstance(e_ref_or_cls, type) and issubclass(e_ref_or_cls, Entity):
        e_ref = self.entities.ref(e_ref_or_cls, **identity)
    else:
        raise SDKStoreError("fg.entities.delete requires e_ref string OR EntityClass + full identity bundle; see ADR-API §4.1.2")

    command = EntityDeleteCommand(target=..., command_meta=...)
    plan = plan_delete_command(command, store=self._store, index=self._application_schema_index)
    if not plan.can_apply:
        self._raise_from_application_error(plan.errors[0], op="delete")
    result = apply_delete_plan(plan, store=self._store, index=self._application_schema_index)
    return len(result.applied)
```

### 5.5 `fg.entities.exists` shape

读 shipped `<EntityType>:exists` Active Claim set — cheap check:

```python
def fg.entities.exists(self, entity_cls, **identity) -> bool:
    e_ref = self.entities.ref(entity_cls, **identity)
    info = entity_info(self._application_schema_index, entity_cls.__name__)
    claims = self._store.ledger.find_claims(pred_id=info.exists_predicate_id, e_ref=e_ref)
    return any(not self._store.ledger.has_active_revocation(c.asrt_id) for c in claims)
```

### 5.6 `fg.fields.*` 新方法 shape(per ADR-API §4.1.2)

```python
# value-oriented retract — 找 active asrt_id matching (F, e_ref, value) then retract
def fg.fields.retract(self, field, e_ref, value, *, meta=None) -> str:
    pred_info = field_predicate(self._application_schema_index, field.entity_type, field.field_name)
    claims = self._store.ledger.find_claims(pred_id=pred_info.pred_id, e_ref=e_ref)
    matches = [c for c in claims if not self._store.ledger.has_active_revocation(c.asrt_id)
                                  and _rest_value(c.rest_terms) == value]
    if not matches:
        raise SDKStoreError(f"no active assertion matching field={field}, e_ref={e_ref}, value={value!r}")
    if len(matches) > 1:
        raise SDKStoreError(f"multiple active assertions matching; ambiguous;pass asrt_id to fg.assertions.retract instead")
    return self.assertions.retract(matches[0].asrt_id, meta=meta)

# clear-all values
def fg.fields.delete(self, field, e_ref, *, meta=None) -> int:
    # find all active (F, e_ref) Claims → retract each via fg.assertions.retract
    # 注:走 fg.assertions.retract 时 Slice 2 retract guard 会 enforce(Identity field 不可走这条路径 — INV-7c)
    ...

# materialize current value(single)or value list(multi)
def fg.fields.get(self, field, e_ref) -> Any:
    # 读 ledger Active set + 按 cardinality 返回
    ...
```

**Layer 2 排他**:`fg.fields.retract` 内部 build asrt_id 后委托 `fg.assertions.retract` → Slice 2 Step 6 wording + guard 继续 enforce(Identity field retract 走该 path 还是被 INV-7c 拒绝);Layer 2 entry 只是 value-oriented sugar over Layer 3。

### 5.7 `AssertionsManager` + `AssertionView` 统一(per ADR-API §4.2 + PF-S5)

`_SDKAssertionsManager` rename → `AssertionsManager`(public)+ 加 `where` + `retract`(挪自 `fg.write.retract`,Slice 2 Step 3 wrap 跟着挪):

```python
class AssertionsManager:
    def __init__(self, sdk):
        self._sdk = sdk
        self._ledger_view = AssertionView(sdk._store, scope="ledger")   # 内部 read view

    # Mutation
    def retract(self, asrt_id: str, *, meta=None) -> str:
        # Slice 2 Step 3 wrap 内容(check_retract_allowed + RetractGuardError mapping)
        # 完整 inline 进来,不动 guard 逻辑
        ...

    # Read shortcuts → 委托 _ledger_view
    @property
    def active(self): return self._ledger_view.active
    @property
    def all(self): return self._ledger_view.all
    def by_id(self, asrt_id): return self._ledger_view.by_id(asrt_id)
    def by_ids(self, ids, *, strict=True): return self._ledger_view.by_ids(ids, strict=strict)
    def field(self, f): return self._ledger_view.field(f)
    def where(self, *, field=_ASSERTION_FILTER_MISSING, e_ref=_ASSERTION_FILTER_MISSING,
              value=_ASSERTION_FILTER_MISSING, value_tag=_ASSERTION_FILTER_MISSING,
              _meta=_ASSERTION_FILTER_MISSING) -> AssertionRecordSet:
        return self._ledger_view.where(
            field=field, e_ref=e_ref, value=value, value_tag=value_tag, _meta=_meta,
        )
```

`AssertionView` — unified pure-read view(合并 `FieldAssertions` + `AssertionNamespace`):

```python
class AssertionView:
    """Scope-aware pure-read view. Scope = ledger / entity / field 组合."""
    # 窄化(scope chain)
    def field(self, f: Field) -> "AssertionView": ...

    # 时间维度终结
    def at(self, t: datetime) -> AssertionRecordSet: ...

    # Property 终结
    @property
    def active(self) -> AssertionRecordSet: ...
    @property
    def all(self) -> AssertionRecordSet: ...
    @property
    def history(self) -> AssertionRecordSet:                # PF-S5 alias of .all
        if os.environ.get("FACTGRAPH_WARN_DEPRECATED") == "1":
            warnings.warn("history is deprecated; use .all", DeprecationWarning, stacklevel=2)
        return self.all

    # ID-based 终结
    def by_id(self, asrt_id) -> AssertionRecord | None: ...   # Rule 5: 查 .all 不是 .active
    def by_ids(self, ids, *, strict=True) -> AssertionRecordSet: ...

    # Canonical filter 终结
    def where(self, *, field=_ASSERTION_FILTER_MISSING, e_ref=_ASSERTION_FILTER_MISSING,
              value=_ASSERTION_FILTER_MISSING, value_tag=_ASSERTION_FILTER_MISSING,
              _meta=_ASSERTION_FILTER_MISSING) -> AssertionRecordSet: ...

    # 显式 NOT in AssertionView
    # def retract(...) — 不存在;type-level guarantee
    # def set / add / delete — 不存在
    # def version(v) — 不存在(per Q12)
```

`snap.field(name)` 返回类型从 `FieldAssertions` → `AssertionView(scope=entity+field)`;`snap.assertions` 从 `AssertionNamespace` → `AssertionView(scope=entity)`。

### 5.8 `AssertionRecordSet.where` 新签名(per ADR-API §4.4 + PF-S6)

shipped `where(*, value, source, trace_id, version, meta)` 整删 → 改 ADR-API §4.4.2 canonical:

```python
def where(self, *,
          value=_ASSERTION_FILTER_MISSING,
          value_tag=_ASSERTION_FILTER_MISSING,
          _meta: dict | None | type[_ASSERTION_FILTER_MISSING] = _ASSERTION_FILTER_MISSING,
          ) -> "AssertionRecordSet":
    """Filter records by canonical signature.

    Removed (per ADR-API §4.4 + Q13):
    - source= → use _meta={"source": ...}
    - trace_id= → use _meta={"trace_id": ...}
    - version= → use _meta={"version": ...}
    - meta= → renamed to _meta=
    """
```

**Sentinel reuse**(per PF-S6):`_ASSERTION_FILTER_MISSING` 已 shipped(`sdk/facade.py:18`)— 不引入新 sentinel。

### 5.9 `version(v)` hard remove(per ADR-API §4.3 + PF-S6)

`AssertionRecordSet.version(v)`(`facade.py:174-183`)+ `FieldAssertions.version(v)`(`facade.py:246-255`)整删。**无 alias 无 DeprecationWarning**(per ADR-API §4.3.3)。User migration:`view.version(v)` → `view.where(_meta={"version": v})`。

### 5.10 `fg.schema.*` 三分 + ADR-IC §4.3.6 enforce(per ADR-API §4.5 + SF12)

`_SDKSchemaManager.add(*classes)` 整删 → 拆三分:

```python
class _SDKSchemaManager:
    def register(self, entity_cls):
        """注册新 entity_type — compile schema + update SchemaIndex frozensets."""
        if entity_cls.__name__ in self._sdk._schema_ir.get("entities", {}):
            raise SchemaConflictError(f"entity_type already registered: {entity_cls.__name__}")
        # ... compile + add + rebuild SchemaIndex (cache hook per Slice 2 §10.9 carry-forward)

    def extend(self, entity_cls):
        """已注册 entity 加 additive Field — ADR-IC §4.3.6 part 1 + part 2 enforce."""
        if entity_cls.__name__ not in self._sdk._schema_ir.get("entities", {}):
            raise SchemaNotFoundError(f"entity_type not registered: {entity_cls.__name__}")
        diff = self._compute_diff(entity_cls)

        # Part 1: Identity↔Field swap reject + Identity add reject + 删字段 reject + cardinality/type 改 reject
        for change in diff.changes:
            if change.kind == "identity_to_field":
                raise SchemaNonAdditiveError(
                    f"cannot demote Identity field to Field: {change.field}. "
                    f"Identity Claim immutability per INV-7c requires entity-type migration."
                )
            if change.kind == "field_to_identity":
                raise SchemaNonAdditiveError(...)
            if change.kind == "identity_added":
                raise SchemaNonAdditiveError(...)
            if change.kind == "field_removed" or change.kind == "identity_removed":
                raise SchemaNonAdditiveError(...)
            if change.kind == "cardinality_changed" or change.kind == "type_changed":
                raise SchemaNonAdditiveError(...)

        # Part 2: <EntityType>:exists predicate protect
        for change in diff.exists_changes:
            if change.kind == "exists_removed" or change.kind == "exists_owner_changed" \
              or change.kind == "exists_arity_changed":
                raise SchemaNonAdditiveError(
                    f"<EntityType>:exists predicate is immutable: {change}. "
                    f"Per ADR-IC §4.3.6 part 2, transitional :exists guard requires structural preservation."
                )

        # Apply additive Field — rebuild SchemaIndex cache(union update)
        ...

    def apply(self, entity_cls):
        """Safe diff — auto register OR extend."""
        if entity_cls.__name__ not in self._sdk._schema_ir.get("entities", {}):
            return self.register(entity_cls)
        try:
            return self.extend(entity_cls)
        except SchemaNonAdditiveError as e:
            raise  # apply 不掩盖 non-additive 错;user 必须显式 migrate
```

### 5.11 `_SDKReadManager` + `_SDKWriteManager` 整删 + flat shortcuts 全删

Step 6:`_SDKReadManager`(`sdk/store.py:533-555`)+ `_SDKWriteManager`(`sdk/store.py:572-613`)整删;`fg.read` + `fg.write` property accessors(lines 1213/1218)删;同 step 删 8 个 flat top-level shortcuts(per PF-S1 + G7):

| 删除 | shipped 位置 |
|---|---|
| `fg.set` | `sdk/store.py:1935` |
| `fg.add` | `sdk/store.py:1978` |
| `fg.retract` | `sdk/store.py:2124`(Slice 2 Step 3 wrap 跟着搬到 `fg.assertions.retract`)|
| `fg.edit` | `sdk/store.py:1332` |
| `fg.get` | `sdk/store.py:1266` |
| `fg.ref` | `sdk/store.py:1888`(shadow store populate 逻辑 → 挪 `fg.entities.ref`)|
| `fg.find` | `sdk/store.py:1291`(挪 `fg.entities.where`,verb find→where)|
| `fg.match` | `sdk/store.py:1314`(挪 `fg.entities.match`)|

**User migration**(blueprint error message hints):
- `fg.set(F, e_ref, v)` → `fg.fields.set(F, e_ref, v)`
- `fg.add(F, e_ref, v)` → `fg.fields.add(F, e_ref, v)`
- `fg.retract(asrt_id)` → `fg.assertions.retract(asrt_id)`
- `fg.edit(EC, **id)` → `fg.entities.edit(EC, **id)`
- `fg.get(EC, **id)` → `fg.entities.get(EC, **id)`
- `fg.ref(EC, **id)` → `fg.entities.ref(EC, **id)`
- `fg.find(EC, **filter)` → `fg.entities.where(EC, **filter)`
- `fg.match(EC, t)` → `fg.entities.match(EC, t)`

### 5.12 Load-bearing docs scope(per PF-S7 lock)

Same-slice migration(4 docs):

1. `src/factgraph/sdk/docs/04_api_surface.en.md` — Namespace Map + 三层 manager 接口 + 新 API methods(create/delete/exists + fields.retract/delete/get + assertions.where)+ 删除 flat shortcuts + version(v) hard remove migration note + where signature update + register/extend/apply 三分 + ADR-IC §4.3.6 contract note
2. `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md` — read/write 章节按 entities/fields/assertions 三层重组
3. `src/factgraph/sdk/docs/00_user_guide.en.md` — quickstart code examples migration 到 fg.entities/fg.fields/fg.assertions(+ create/delete examples)
4. `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §12/§13` — §12 API 表面分层 + §13 Slice 3a landed status note(per Slice 2 §13.4 precedent)

**Slice 4 carry-forward**(non-load-bearing wider polish):`01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md` / public quickstarts in `docs/official/kernel/quickstart/` / examples deep polish。

## 6. Boundaries And Invariants

### 6.1 Scope Freeze(LOCKED — must remain through implementation)

| # | Lock | Source |
|---|---|---|
| **SF1** | **flat top-level shortcuts 全删**(PF-S1 verdict — Option B):`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.get` / `fg.ref` / `fg.find` / `fg.match` 8 个 SDKStore 顶层方法完全删除;**无 alias 无双轨期**;Slice 2 emission contract tests + 其他 shipped tests 全 migrate 到 namespace 入口 | PF-S1 verdict + ADR-API §4.1.3 |
| **SF2** | **`fg.entities.delete` discriminated signature**(PF-S2 verdict):`fg.entities.delete(e_ref: str, *, meta=None)` 跟 `fg.entities.delete(EntityCls, **identity_kwargs)` 两入口;tuple selector **显式 forbidden**;参数类型错 raise `"fg.entities.delete requires e_ref string OR EntityClass + full identity bundle; see ADR-API §4.1.2"` | PF-S2 verdict |
| **SF3** | **`fg.entities.delete` implementation site at application layer**(PF-S3 verdict — INV-6 application-first):NEW `EntityDeleteCommand` DTO + `plan_delete_command` + `apply_delete_plan` in `application/entity_write.py`;SDK manager 只做参数归一化 + 调 application path;`_apply_op` retract branch 见 `meta["__delete_via_entities_delete__"]` marker 跳过 Slice 2 retract guard(整批 delete 是 ADR-IC §4.1 唯一合法 Identity Claim 整批 retract 路径)| PF-S3 verdict + ADR-IC §4.1 + INV-6 |
| **SF4** | **`fg.entities.create` eager emission + populate shadow store**(PF-S4 verdict — Option (a)):`fg.entities.create(EC, **id)` 直接 emit Identity Claims + `:exists` 到 ledger via `_materialization_ops` shipped path + populate shadow store for compatibility;`fg.ref + fg.set` lazy path 继续保留 co-existing;**Slice 3a 显式 NOT remove shadow store**(per ADR-IC §4.2.4 Step 2+ direction)| PF-S4 verdict + ADR-IC §4.2 + §4.2.4 |
| **SF5** | **`AssertionView.history` deprecated alias**(PF-S5 verdict per ADR-API §4.2.4):保留 alias of `.all`;**默认不发** `DeprecationWarning`(防测试失败);env var **固定** `FACTGRAPH_WARN_DEPRECATED=1` 触发 warning;blueprint §5.7 显式 model `os.environ.get(...)` check | PF-S5 verdict |
| **SF6** | **`_ASSERTION_FILTER_MISSING` sentinel reuse**(PF-S6 verdict):shipped sentinel `sdk/facade.py:18`;不引入新 sentinel for 新的 `AssertionView.where` / `AssertionsManager.where` / `AssertionRecordSet.where`(post-Q13 删 flat) | PF-S6 verdict |
| **SF7** | **Slice 3a load-bearing docs scope**(PF-S7 verdict):**4 docs same-slice landing** — `src/factgraph/sdk/docs/04_api_surface.en.md` + `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md` + `src/factgraph/sdk/docs/00_user_guide.en.md` + `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §12/§13`。**Slice 4 留**:`01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md` / public quickstarts / examples deep polish。**Exception**:若 Slice 3a 实施期发现 test 或 current docs hard-reference 新 API 造成断裂,可加 narrow patch(Slice 3a §10 Outcome 记录) | PF-S7 verdict + ADR-DOCS §4.2.2 |
| **SF8** | **12-step plan + docs as standalone close-time step**(PF-S8 verdict):Step 0(pre-impl grep,uncounted)+ Step 1-12(numbered);Step 0 必须**先 grep actual callsites** 再进入 manager/code changes;**docs migration(Step 11)显式独立于 tests/examples migration(Step 10)**,不混合 | PF-S8 verdict |
| **SF9** | **Q-PR1 carve-out + SF11-style internal-rollback 继承**(Slice 1+2 lineage):0 diff against Slice 2 close `c927d41f..HEAD` 在 `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py`(含 `:401` 内部 rollback path,SF11 classification 继承)| meta-ADR §4.4 + Slice 2 SF5 + SF11 + N11 |
| **SF10** | **Sacred branches + dirty baseline preservation**:`master` `562c74195df43e933bed92a3ff25de94dd8ce666` 不动;`v0.1-oss-prep` 不动;dirty baseline(4 M + 1 D + 2 untracked)preserved through all commits | Slice 2 SF (sustained) |
| **SF11** | **ADR-IE EntityEditor compatibility**:`sdk_edit` factory edit-existing-only contract(per ADR-IE §4.8)+ EntityEditor lifecycle(per ADR-IE §4.1-§4.7)+ IdentityEditor Layer 1 reject 文案(Slice 2 Step 6 已 ship — 不动)+ FieldEditor cardinality enforcement(per ADR-IE §4.5)— **全 contract 不改**;Slice 3a 只动 `fg.write.edit` → `fg.entities.edit` 入口名(per ADR-API §4.1.2 + ADR-IE §4.8)| ADR-IE §4.8 |
| **SF12** | **ADR-IC §4.3.6 explicit contract part 1+2 enforce at `fg.schema.extend`**(per G6 + 4.5):part 1 — Identity↔Field swap reject(Identity→Field demote + Field→Identity upgrade)+ Identity field add reject + 删字段 reject + cardinality/type 改 reject;part 2 — `<EntityType>:exists` predicate immutability(删/owner_type 改/arity 改全 reject)| ADR-IC §4.3.6 + ADR-API §4.5.2 + §4.5.3 |
| **SF13** | **No flat shortcut re-introduction rule**(corollary of SF1):Slice 3a close 后 future slice 不应在 SDKStore / FactGraph 顶层加 `fg.<verb>(...)` 直接 method(verb-on-fg 形态);所有 user-facing operations 必须走 namespace manager(`fg.entities.*` / `fg.fields.*` / `fg.assertions.*` / `fg.schema.*`)| SF1 corollary + ADR-API §4.1 排他原则 |

### 6.2 Compatibility constraints + dirty baseline guard

- Sacred `master` `562c74195df43e933bed92a3ff25de94dd8ce666` 不动
- Sacred `v0.1-oss-prep` 不动
- Dirty baseline(4 M + 1 D + 2 untracked,unrelated to API namespace refactor)preserved through all commits
- Branch lineage:每次 commit verify HEAD ancestor includes ADR-API `66434490` + meta-ADR `ebafdb0c` + ADR-IE `9fd0ffb5` + ADR-IC `2d0866ed` + ADR-DOCS `bb6a2c90` + Slice 1 close `9cef674b` + Slice 2 close `c927d41f`

### 6.3 Q-PR1 carve-out + internal-rollback classification(SF11-style)

**Q-PR1 carve-out — zero diff(Slice 3a enforcement gate)**:
- `src/factgraph/core/evidence/write_protocol.py` 0 diff
- `src/factgraph/core/store/ledger.py` 0 diff
- `src/factgraph/core/store/_builders.py` 0 diff
- `src/factgraph/adapters/pyreason/*` 0 diff
- `claims.rest_terms` 0 diff
- No INV-9 runtime strict assertion added

**Internal-rollback classification(SF11-style explicit)**:
- `src/factgraph/core/derivation/accept.py:401` `retract_by_asrt` direct call — **internal derivation rollback,intentionally unguarded**(继承 Slice 2 SF11 classification)
- Rationale:derivation rollback 不 touch Identity Claims(by definition);若 derivation engine 错误产生 Identity Claim → engine bug,留 Step 2+ ADR fix derivation engine
- Slice 3a §10 Outcome 必须显式 record this classification 继承

### 6.4 ADR-DOCS §4.2.2 load-bearing docs invariant

Slice 3a may NOT mark `implemented` unless these 4 docs land in the same slice(per SF7):

- `src/factgraph/sdk/docs/04_api_surface.en.md` — full namespace + new API surface
- `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md` — 三层 entities/fields/assertions 重组
- `src/factgraph/sdk/docs/00_user_guide.en.md` — quickstart code examples migration
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §12/§13` — §12 API 表面分层 + §13.5 Slice 3a landed status note

Per ADR-DOCS §4.1.2 Dimension B:design-point sync IS load-bearing in this slice。

## 7. Acceptance

### 7.1 三层 namespace + 排他 navigation key(G1 + SF1)

- [ ] `fg.entities` property returns `EntitiesManager`(NEW class in `sdk/store.py`)
- [ ] `fg.fields` property returns `FieldsManager`(NEW class)
- [ ] `fg.assertions` property returns `AssertionsManager`(rename + public + 加 where + retract)
- [ ] `fg.read` + `fg.write` properties **删除** — `AttributeError` raise(NOT alias)
- [ ] Flat top-level methods(`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.get` / `fg.ref` / `fg.find` / `fg.match`)**删除** — `AttributeError` raise
- [ ] Test:`fg.fields.set(asrt_id_str, "value")` raises `SDKStoreError` 含 `"Layer 3"` + `"ADR-API §4.1.1"` pointer
- [ ] Test:`fg.entities.get(asrt_id_str)` raises `SDKStoreError` 含 layer hint
- [ ] Test:`fg.assertions.retract(EntityCls, **identity)` raises `SDKStoreError` 含 layer hint

### 7.2 `fg.entities.create/delete/exists`(G2 + SF2 + SF3 + SF4)

- [ ] `fg.entities.create(EntityCls, **identity, meta=...)`:eager emit N Identity + 1 `:exists` Claims atomic + populate shadow store + return e_ref
- [ ] Test:`fg.entities.create + ledger.find_claims(e_ref=)` Active set 立即含 N Identity + 1 `:exists`(eager 验证)
- [ ] Test:`fg.entities.create + fg.entities.exists(EC, **identity)` returns True 不需 first field write
- [ ] Test:`fg.entities.create(EC, **id)` 重复同 identity → raise `EntityAlreadyExistsError`
- [ ] `fg.entities.delete(e_ref: str)` Form A:整批 retract Active Claims(Identity + `:exists` + Field)
- [ ] `fg.entities.delete(EntityCls, **identity)` Form B:同 Form A but identity-based
- [ ] Test:`fg.entities.delete(tuple_selector)` raises `SDKStoreError` 含 `"requires e_ref string OR EntityClass + full identity bundle"`(PF-S2)
- [ ] Test:`fg.entities.delete(e_ref) + fg.entities.exists(...)` returns False after
- [ ] Test:`fg.entities.delete(e_ref) + fg.assertions.by_id(identity_asrt_id).revoked == True`(Slice 2 retract guard 不阻止 delete-path 整批 revoke per SF3 marker)
- [ ] `fg.entities.exists(EC, **identity)` returns bool(check `<EntityType>:exists` Active Claim presence + has_active_revocation)
- [ ] Application layer:`EntityCreateCommand` + `plan_create_command` + `apply_create_plan` shipped in `application/entity_write.py`
- [ ] Application layer:`EntityDeleteCommand` + `plan_delete_command` + `apply_delete_plan` shipped
- [ ] SDK manager `fg.entities.create / delete` 只归一化参数 + 调 application path(no inline planner logic per PF-S3)

### 7.3 `fg.fields.*` 5 methods(G3)

- [ ] `fg.fields.set/add/retract/delete/get` 5 methods shipped on `FieldsManager`
- [ ] Test:`fg.fields.set(F, e_ref, v)` 等价 shipped `fg.set` 行为(rename + retract guard 仍 enforce)
- [ ] Test:`fg.fields.retract(F, e_ref, value)` value-oriented:找 active asrt matching → 委托 `fg.assertions.retract`;ambiguous raise SDKStoreError;Identity field 走该路径仍 INV-7c rejected
- [ ] Test:`fg.fields.delete(F, e_ref)` clear-all:全 active Claims for (F, e_ref) → retract sequence

### 7.4 `AssertionsManager` + `AssertionView` 统一(G4 + SF5 + SF6)

- [ ] `AssertionsManager` class public(rename from `_SDKAssertionsManager`)+ 内部 `_ledger_view: AssertionView`
- [ ] `AssertionsManager.retract(asrt_id)` 是唯一 asrt_id-based mutation 入口(Slice 2 Step 3 guard wrap 内容完整搬过来)
- [ ] `AssertionsManager.where(*, field, e_ref, value, value_tag, _meta)` NEW canonical filter — sentinel `_ASSERTION_FILTER_MISSING` reuse per SF6
- [ ] `FieldAssertions` class **删除** + `AssertionNamespace` class **删除**
- [ ] `snap.field(name)` returns `AssertionView(scope=entity+field)` NOT `FieldAssertions`
- [ ] `snap.assertions` returns `AssertionView(scope=entity)` NOT `AssertionNamespace`
- [ ] `AssertionView.history` property — alias of `.all`;default no warning;env `FACTGRAPH_WARN_DEPRECATED=1` triggers DeprecationWarning(per SF5)
- [ ] Test:`AssertionView` 类**根本不存在** `retract` method(`hasattr(AssertionView, 'retract') is False`)— type-level pure-read guarantee
- [ ] Test:env `FACTGRAPH_WARN_DEPRECATED=1` + `view.history` triggers `pytest.warns(DeprecationWarning)`;不设 env 时 no warning

### 7.5 `version(v)` + flat kwargs hard remove(G5)

- [ ] `AssertionRecordSet.version(v)` **删除** — `AttributeError` raise
- [ ] `FieldAssertions.version(v)` 跟 FieldAssertions 一起删
- [ ] `AssertionRecordSet.where(*, value, source, trace_id, version, meta)` flat kwargs **删除**
- [ ] `AssertionRecordSet.where(*, value, value_tag, _meta)` NEW signature shipped
- [ ] Test:`recordset.version("v1")` raises `AttributeError`
- [ ] Test:`recordset.where(source="seed")` raises `TypeError`(`unexpected keyword argument 'source'`)
- [ ] Test:`recordset.where(_meta={"version": "v1"})` returns filtered set(per Q12 替代路径)

### 7.6 `fg.schema.*` 三分 + ADR-IC §4.3.6 enforce(G6 + SF12)

- [ ] `fg.schema.add(*classes)` **删除** — `AttributeError` raise
- [ ] `fg.schema.register(EC)` shipped — 新 entity_type 注册 + SchemaIndex frozensets cache union update
- [ ] `fg.schema.extend(EC)` shipped — additive Field 扩展 + **ADR-IC §4.3.6 part 1 + part 2 enforce**
- [ ] `fg.schema.apply(EC)` shipped — safe diff convenience
- [ ] Test:`fg.schema.extend` reject Identity field add → `SchemaNonAdditiveError` 含 "Identity bundle redesign requires entity-type migration"
- [ ] Test:`fg.schema.extend` reject Identity→Field demote → `SchemaNonAdditiveError`
- [ ] Test:`fg.schema.extend` reject Field→Identity upgrade → `SchemaNonAdditiveError`
- [ ] Test:`fg.schema.extend` reject 删字段 → `SchemaNonAdditiveError`
- [ ] Test:`fg.schema.extend` reject cardinality/type 改 → `SchemaNonAdditiveError`
- [ ] Test:`fg.schema.extend` 模拟试图删 `<EntityType>:exists` predicate → `SchemaNonAdditiveError`(part 2)
- [ ] Test:`fg.schema.register(EC)` + `SchemaIndex.identity_pred_ids` 立即包含新 entity 的 identity preds(cache rebuild hook 触发)

### 7.7 Q-PR1 carve-out preservation(SF9)

- [ ] Final grep:`git diff --name-only c927d41f..HEAD -- src/factgraph/core/evidence/write_protocol.py src/factgraph/core/store/ledger.py src/factgraph/core/store/_builders.py src/factgraph/adapters/pyreason/ src/factgraph/core/derivation/accept.py` returns 0 results
- [ ] `claims.rest_terms` 0 diff
- [ ] No INV-9 runtime strict assertion added

### 7.8 Sacred branches + dirty baseline(SF10)

- [ ] Every commit:`git rev-parse master == 562c74195df43e933bed92a3ff25de94dd8ce666`
- [ ] Every commit:dirty baseline(4 M + 1 D + 2 untracked)preserved
- [ ] Every commit:branch lineage ancestor 含 ADR-API `66434490` + meta-ADR `ebafdb0c` + ADR-IE `9fd0ffb5` + ADR-IC `2d0866ed` + ADR-DOCS `bb6a2c90` + Slice 1 close `9cef674b` + Slice 2 close `c927d41f`

### 7.9 ADR-IE EntityEditor compatibility(SF11)

- [ ] `sdk_edit` factory function 保留 edit-existing-only contract(`sdk/facade.py:678`)
- [ ] `EntityEditor` class 保留 lifecycle methods(open/preview/commit/rollback/__enter__/__exit__/EditorClosedError)
- [ ] `IdentityEditor.set/add/retract` 文案不动(Slice 2 Step 6 `c2d659c1` already shipped per ADR-IC §4.1 wording)
- [ ] `FieldEditor` cardinality enforcement 不动
- [ ] `fg.entities.edit(EC, **identity)` 调用 `sdk_edit(...)` factory(rename 不破 contract)

### 7.10 Internal-rollback classification(SF9 continuation per Slice 2 SF11)

- [ ] `src/factgraph/core/derivation/accept.py:401` 0 diff confirmed
- [ ] Slice 3a §10 Outcome 显式 record SF11-style classification inheritance

### 7.11 Tests + examples migration(Step 10)

- [ ] All Slice 1+2 cumulative test files(59 tests baseline + Slice 2 carry-forward usage of `fg.ref + fg.set` etc.)migrated to `fg.entities.* / fg.fields.* / fg.assertions.*` namespace
- [ ] Pre-existing `fg.read.*` test files(4 files)+ `fg.write.*` test files(3 files)+ `fg.assertions.*` test files(1 file)+ `fg.schema.add` test files(3 files)+ `version(v)` test files(2 files)全 migrate
- [ ] Examples(`examples/` directory)— small surface migration per PF-S7 boundary
- [ ] **No** wider docs polish(`01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md` / public quickstarts)— 留 Slice 4(per SF7)
- [ ] Cumulative Slice 1+2+3a test suite full green

### 7.12 Load-bearing docs migration(Step 11 — SF7)

- [ ] `src/factgraph/sdk/docs/04_api_surface.en.md`:
  - Namespace Map 改 4 个 namespaces(entities / fields / assertions / schema)
  - 删 flat shortcuts 章节 + 加 migration table(8 flat → namespace)
  - 加 `fg.entities.create/delete/exists` 章节
  - 加 `fg.fields.retract/delete/get` 章节
  - 加 `fg.assertions.where` canonical filter signature
  - 加 `fg.schema.register/extend/apply` 三分 + ADR-IC §4.3.6 enforcement note
  - 删 `version(v)` 章节 + 加 migration note(per ADR-API §4.3.4)
  - 改 `where` signature 章节(flat kwargs → `_meta=`)
  - 改 `AssertionView` 章节(scope-aware unified type;FieldAssertions/AssertionNamespace 移除)
- [ ] `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`:三层重组 + 新 API 例
- [ ] `src/factgraph/sdk/docs/00_user_guide.en.md`:quickstart code examples migration
- [ ] `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`:
  - §12 API 表面分层 update 跟 ADR-API §4.1-§4.5 adopted wording 对齐
  - §13 加 §13.5 Slice 3a landed status note(per Slice 2 §13.4 precedent)— commit lineage table + carry-forward 项(剩余 4 项)

### 7.13 Per-commit verification ritual

- [ ] Every commit:`git rev-parse master == 562c74195df43e933bed92a3ff25de94dd8ce666`
- [ ] Every commit:dirty baseline(4 M + 1 D + 2 untracked)preserved
- [ ] Every commit:Q-PR1 carve-out 5 sacred paths 0 diff against `c927d41f`
- [ ] Every commit:branch lineage ancestor verified

## 8. Implementation Plan

Per PF-S8 lock:**12 numbered steps + Step 0 grep**;docs migration **独立 close 前 step**(Step 11)— **不** 混在 tests/examples sweep(Step 10)。

### Step 0 — Pre-impl grep gate(read-only,uncounted)

- 0.1 Verify shipped `fg.read.*` / `fg.write.*` / `fg.assertions.*` / `fg.schema.add` / `version(v)` / flat `where(source=)` actual callsites match preflight §3 inventory(no drift since preflight)
- 0.2 Verify all ADR adopted commits ancestor of HEAD via `git merge-base --is-ancestor`
- 0.3 Verify Q-PR1 carve-out 5 sacred paths 0 diff against `c927d41f`
- 0.4 Verify Slice 2 cumulative test suite(59 tests)still passing on `c927d41f..HEAD` HEAD baseline
- 0.5 **No commit**(read-only verification — outcome recorded in audit row only)

### Step 1 — `_SDKEntitiesManager` class + 4 base methods + property accessor

- 1.1 NEW `_SDKEntitiesManager`(or `EntitiesManager` if public) class in `sdk/store.py` with:
  - `get(entity_cls, **identity_kwargs)` — delegate `sdk_get` factory
  - `where(entity_cls, *filters, _meta=None)` — delegate `sdk_find`(rename find→where + _meta signature)
  - `match(entity_cls, template, ...)` — delegate `sdk_match`
  - `ref(entity_cls, **identity_kwargs)` — delegate shadow store populate(从 flat `fg.ref` 挪过来)
- 1.2 `fg.entities` property accessor on `SDKStore`
- 1.3 NEW tests `tests/test_sdk_entities_namespace.py`(N tests):4 method behavior 等价 shipped + 排他 enforcement(non-Entity-class params raise)
- 1.4 — commit boundary

### Step 2 — `fg.entities.create` application layer planner + executor + SDK normalize

- 2.1 NEW `EntityCreateCommand`(frozen dataclass)in `application/protocol/entity_write.py`
- 2.2 NEW `plan_create_command(command, *, store, index) -> EntityCreatePlan` in `application/entity_write.py`
- 2.3 NEW `apply_create_plan(plan, *, store, index) -> EntityCreateResult`
- 2.4 NEW `EntityAlreadyExistsError`(`_sdk_errors.py`)— code="ENTITY_ALREADY_EXISTS"
- 2.5 SDK `fg.entities.create(entity_cls, *, meta=None, **identity)` 只归一化 + 调 application path(per PF-S3)
- 2.6 NEW tests `tests/test_sdk_entities_create.py`:eager emit N Identity + 1 `:exists` atomic + shadow store populate + 重复 raise EntityAlreadyExistsError + Identity bundle 完整性 check
- 2.7 — commit boundary

### Step 3 — `fg.entities.delete` application layer planner + executor + SDK normalize

- 3.1 NEW `EntityDeleteCommand`(frozen dataclass)+ `EntityDeletePlan` + `EntityDeleteResult`
- 3.2 NEW `plan_delete_command` + `apply_delete_plan`
- 3.3 `_apply_op` retract branch 加 marker check:`if op.meta.get("__delete_via_entities_delete__"): skip check_retract_allowed`(per SF3 — delete-internal retracts 绕过 guard)
- 3.4 SDK `fg.entities.delete(e_ref_or_cls, *, meta=None, **identity)` 归一化两 form + 显式 reject tuple(per PF-S2)+ 调 application path
- 3.5 NEW tests `tests/test_sdk_entities_delete.py`:Form A e_ref / Form B EC+identity / tuple reject / atomic revoke all Active Claims / Slice 2 retract guard 不 block delete-internal
- 3.6 — commit boundary

### Step 4 — `fg.entities.exists`

- 4.1 SDK `fg.entities.exists(entity_cls, **identity) -> bool` — check `<EntityType>:exists` Active Claim presence + `has_active_revocation`
- 4.2 NEW tests `tests/test_sdk_entities_exists.py`:returns True after materialize(create or `fg.fields.set` first write)/ False after delete / False for ref-only(non-materialized — `:exists` not yet emitted)
- 4.3 — commit boundary

### Step 5 — `_SDKFieldsManager` class + 5 methods + property accessor

- 5.1 NEW `_SDKFieldsManager`(or `FieldsManager`)class + 5 methods:
  - `set(F, e_ref, v)` / `add(F, e_ref, v)` — delegate shipped `_apply_field_mutation` 路径
  - NEW `retract(F, e_ref, value)` value-oriented — 找 active asrt → 委托 `fg.assertions.retract`(Slice 2 guard 继续 enforce)
  - NEW `delete(F, e_ref)` clear-all — 全 active (F, e_ref) Claims → retract sequence
  - NEW `get(F, e_ref)` materialize-current — 读 ledger Active set
- 5.2 `fg.fields` property accessor on `SDKStore`
- 5.3 NEW tests `tests/test_sdk_fields_namespace.py`:5 method behavior + 排他 enforcement(asrt_id 参数 raise)+ Identity field retract via `fg.fields.retract` 仍 INV-7c rejected
- 5.4 — commit boundary

### Step 6 — `_SDKAssertionsManager` rename → `AssertionsManager` + `where` + retract 挪 + Slice 2 wrap

- 6.1 Class rename `_SDKAssertionsManager` → `AssertionsManager`(public — drop underscore prefix)
- 6.2 加 NEW `where(*, field=_ASSERTION_FILTER_MISSING, e_ref=_ASSERTION_FILTER_MISSING, value=_ASSERTION_FILTER_MISSING, value_tag=_ASSERTION_FILTER_MISSING, _meta=_ASSERTION_FILTER_MISSING)` canonical filter — sentinel reuse per SF6
- 6.3 加 NEW `retract(asrt_id, *, meta=None)` mutation method:Slice 2 Step 3 wrap 内容(check_retract_allowed + RetractGuardError mapping)完整搬过来,不动 guard 逻辑
- 6.4 内部 `_ledger_view: AssertionView` — read shortcuts(active/all/by_id/by_ids/field/where)delegate
- 6.5 NEW tests `tests/test_sdk_assertions_namespace.py`:retract 行为等价 shipped fg.write.retract + where canonical filter + 排他 enforcement(EntityClass 参数 raise)
- 6.6 — commit boundary

### Step 7 — `fg.entities.edit` 挪层 + namespace 整删 + flat shortcuts 全删

- 7.1 SDK `fg.entities.edit(entity_cls, **identity)` delegate `sdk_edit` factory(rename 不破 contract per SF11)
- 7.2 **删除** `_SDKReadManager` class + `fg.read` property accessor — `AttributeError` raise
- 7.3 **删除** `_SDKWriteManager` class + `fg.write` property accessor — `AttributeError` raise
- 7.4 **删除** 8 个 flat top-level methods on `SDKStore`(per SF1 + G7):`set / add / retract / edit / get / ref / find / match` — `AttributeError` raise
- 7.5 SDK 内部 callsites 全 migrate(`SDKStore` 内部 helper methods 改用 namespace managers)
- 7.6 NEW tests `tests/test_sdk_namespace_removal.py`:`fg.read` / `fg.write` 8 flat shortcuts 全 raise `AttributeError`
- 7.7 — commit boundary

### Step 8 — `AssertionView` 类型合并 + history alias env var

- 8.1 NEW `AssertionView` unified class in `sdk/facade.py` — scope-aware(ledger / entity / field 组合)+ `field(f) / at(t) / active / all / history / by_id / by_ids / where`
- 8.2 `AssertionView.history` alias of `.all` + env var `FACTGRAPH_WARN_DEPRECATED=1` triggers `warnings.warn(...)` per SF5
- 8.3 **删除** `FieldAssertions` class
- 8.4 **删除** `AssertionNamespace` class
- 8.5 `snap.field(name)` 改返回 `AssertionView(scope=entity+field)`(原 `FieldAssertions`)
- 8.6 `snap.assertions` 改返回 `AssertionView(scope=entity)`(原 `AssertionNamespace`)
- 8.7 NEW tests `tests/test_sdk_assertion_view_unified.py`:`AssertionView` 无 retract method(type-level)/ scope chain / history alias env var behavior
- 8.8 — commit boundary

### Step 9 — `version(v)` hard remove + `where` flat kwargs hard remove

- 9.1 **删除** `AssertionRecordSet.version(v)`(`facade.py:174-183`)
- 9.2 **删除** `FieldAssertions.version(v)`(随 Step 8 FieldAssertions 删一起)
- 9.3 **删除** `AssertionRecordSet.where(*, value, source, trace_id, version, meta)` flat kwargs(`facade.py:133-160`)
- 9.4 NEW `AssertionRecordSet.where(*, value, value_tag, _meta)` — sentinel `_ASSERTION_FILTER_MISSING` reuse per SF6
- 9.5 NEW tests `tests/test_sdk_where_version_hard_remove.py`:`version(v)` 调用 `AttributeError` / `where(source=)` 调用 `TypeError` / `where(_meta={"version": "v1"})` 行为等价 shipped `version("v1")` 替代路径
- 9.6 — commit boundary

### Step 10 — `fg.schema.add` 删 + register/extend/apply 三分 + ADR-IC §4.3.6 enforce

- 10.1 **删除** `_SDKSchemaManager.add(*classes, **kwargs)`(`sdk/store.py:522`)
- 10.2 NEW `_SDKSchemaManager.register(entity_cls)` + SchemaIndex cache union update hook
- 10.3 NEW `_SDKSchemaManager.extend(entity_cls)` + ADR-IC §4.3.6 part 1 enforce(Identity↔Field swap reject / Identity field add reject / 删字段 reject / cardinality/type 改 reject)
- 10.4 `extend` 加 part 2 enforce(`<EntityType>:exists` predicate immutability — 删/owner_type 改/arity 改 reject)
- 10.5 NEW `_SDKSchemaManager.apply(entity_cls)` safe-diff convenience
- 10.6 NEW `SchemaConflictError` + `SchemaNotFoundError` + `SchemaNonAdditiveError` in `_sdk_errors.py`
- 10.7 NEW tests `tests/test_sdk_schema_three_split.py`:6+ tests covering register / extend additive Field / extend reject Identity↔Field swap / extend reject Identity add / extend reject 删字段 / extend reject :exists touch / apply auto-route / SchemaIndex cache rebuild on register/extend
- 10.8 — commit boundary

### Step 11 — Tests + examples migration grep + sed sweep

**Code-side migration only**(docs 显式独立 Step 12 per SF8):

- 11.1 grep `fg\.read\.` / `fg\.write\.` / `fg\.set\|fg\.add\|fg\.retract\|fg\.edit\|fg\.get\|fg\.ref\|fg\.find\|fg\.match` / `fg\.schema\.add` / `\.version\(` / `where\(source=\|trace_id=\|version=` 全 callsites(per preflight §6 blast radius)
- 11.2 Test files migrate:
  - `tests/test_schema_field_add_lifecycle.py` 5 occurrences `fg.read.get` + 3 occurrences `fg.write.set/add`
  - `tests/test_schema_mutation_lifecycle.py` 2 occurrences `fg.write.set`
  - `tests/test_sdk_assertion_record_set_view_filters.py` 4 occurrences `snap.field(...).version(...)` / `set.version(...)`
  - `tests/test_sdk_assertion_record_set.py` 1 occurrence `snap.field(...).version(...)`
  - `tests/test_schema_*.py` 3 occurrences `fg.schema.add`
  - Slice 2 emission tests `tests/test_emission_contract.py` + 其他 Slice 2 test files — 大量 `fg.ref + fg.set` 改 `fg.entities.ref + fg.fields.set`(或者用 `fg.entities.create` shortcut)
  - 4 个 `fg.read.*` test files + 3 个 `fg.write.*` test files + 1 个 `fg.assertions.*` test file + 2 个 `version(v)` test files + 3 个 where flat kwargs test files 全 migrate
- 11.3 Examples migrate:`examples/` directory small surface(8 `fg.read.*` + 5 `fg.write.*` + 9 `fg.assertions.*` + 5 `.version(` + 5 `.find(` hits per preflight §6)
- 11.4 Cumulative Slice 1+2+3a test suite full green
- 11.5 — commit boundary

### Step 12 — Load-bearing docs migration + final acceptance + §10 Outcome + Status implemented

**Docs migration**(4 docs per SF7):

- 12.1 `src/factgraph/sdk/docs/04_api_surface.en.md` — full namespace + new API surface + migration tables(per §7.12 acceptance)
- 12.2 `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md` — 三层 entities/fields/assertions 重组
- 12.3 `src/factgraph/sdk/docs/00_user_guide.en.md` — quickstart code examples migration
- 12.4 `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §12/§13.5` — §12 API 表面分层 update + §13.5 Slice 3a landed status

**Final acceptance**:

- 12.5 Run all §7 acceptance checks
- 12.6 Verify §6.1 Scope Freeze 13 items(SF1-SF13)still locked
- 12.7 Verify §6.3 Q-PR1 carve-out 0 diff via grep against `c927d41f..HEAD`
- 12.8 Verify §6.3 internal-rollback `core/derivation/accept.py:401` 0 diff + SF11-style classification 继承
- 12.9 Fill §10 Outcome:final landing(commit lineage)+ deviations + Step 0 verification results + 6 verification subsections + Slice 3a carry-forward dependencies(剩余:Step 2+ `:exists` removal + Step 2+ shadow store removal + Slice 3b ledger migration + Slice 4 wider docs polish + Slice 5+ Q-PR1)
- 12.10 Mark `Status: implemented` + audit log final row
- 12.11 — commit boundary(Slice 3a close)

## 9. Docs To Update

### 9.1 Slice 3a load-bearing(per ADR-DOCS §4.2.2 + SF7 — MUST land in this slice)

- `src/factgraph/sdk/docs/04_api_surface.en.md`(see §7.12 detail)
- `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/factgraph/sdk/docs/00_user_guide.en.md`
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §12 + §13(加 §13.5 Slice 3a landed status note)

### 9.2 Module docs

- `src/factgraph/application/docs/`(if exists)— `entity_write.py` 新增 EntityCreateCommand + EntityDeleteCommand DTOs + planner + executor 简介

### 9.3 Out-of-slice docs(Slice 4 Phase 2 or downstream)

- `src/factgraph/sdk/docs/01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md` — namespace migration consistency
- `docs/official/kernel/quickstart/*.md` public quickstart files
- `docs/README.md`(若 Slice 4 加新 quickstart entry)
- Examples deep polish(`examples/` directory broader migration)
- Module-wide migration note placement consolidation

### 9.4 Excluded(per SF7 + SF9 — Q-PR1 carve-out)

- `workflow/heritage/` / `workflow/blueprints/archive/` / `workflow/design/design-points/archive/` — historical
- `docs/references/working/` / `docs/references/bridges/` / `workflow/audit/active/`(except Slice 3a preflight)— non-load-bearing
- `examples/archive/` — archived
- `src/factgraph/core/evidence/write_protocol.py` / `src/factgraph/core/store/ledger.py` / `src/factgraph/core/store/_builders.py` / `src/factgraph/adapters/pyreason/` / `src/factgraph/core/derivation/accept.py` — Q-PR1 carve-out + SF11 classification

## 10. Outcome / Deviations

任务完成后填写(per Slice 2 §10 precedent — 10 subsections):

- **§10.1 最终落地结果**:Step lineage table(Step 0 + Step 1-12 + audit backfills)+ commit SHAs
- **§10.2 与 blueprint 不同地方**:direction deviations(应为 0)+ amend records(if any)+ historical discrepancies acknowledged
- **§10.3 Step 0 pre-impl verification results**
- **§10.4 三层 namespace topology verification**(SF1 全删 + 3 个 NEW manager + 排他 enforcement)
- **§10.5 fg.entities.create/delete/exists verification**(SF2 + SF3 + SF4 application layer planner + eager emission + discriminated signature)
- **§10.6 Q-PR1 carve-out preservation confirmation**(`git diff --name-only c927d41f..HEAD --` 5 sacred paths returns empty)
- **§10.7 Internal-rollback classification confirmation**(SF11-style 继承)
- **§10.8 Slice 3a load-bearing docs landed confirmation**(4 docs per SF7)
- **§10.9 Carry-forward dependencies recorded**:
  - Step 2+ `:exists` removal(per ADR-IC §4.4.4)— existence-claim transitional guard 同步退役
  - Step 2+ shadow store removal(per ADR-IC §4.2.4)— eager-emission `fg.entities.create` 已 ship,shadow store 可 Step 2+ retire
  - Slice 3b ledger migration(`__system__.revokes` + claims `value+value_tag` 双列)— 独立 ADR-SYS-B + Slice 3b
  - Slice 4 wider docs polish + cross-doc consistency(per SF7 boundary)
  - Slice 5+ Q-PR1 PyReason adapter rewrite + INV-9 runtime strict enforcement
- **§10.10 归档说明**:6-step archive cadence(blueprint + audit → `workflow/blueprints/archive/` + INVENTORY.md update + push branch to origin + 等用户授权)
