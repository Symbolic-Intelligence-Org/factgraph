# Q-IC Decision: Identity-as-Claim core — Layer 2 schema-aware rejection + emission layer + INV-7c cache lifecycle + `:exists` transitional contract

- Status: adopted
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Slice 2 Identity-as-Claim 的 4 个 sub-decisions(audit Q1/Q2/Q3/Q16 per meta-ADR §4.2 grouping)before Slice 2 blueprint 起草。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q1/Q2/Q3/Q16 rows(`audit:514-516, 530`)+ §5.2 A2/A4/A16/A18/A20 rows + §5.4 N2/N3 + §6 A1 baseline
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md`(ADR-FI)adopted `b288ea9e` — §4.2 `_DataMember` + §4.3-bis Identity descriptor surface 已锁,Identity descriptor 走 `Identity()` 形态
  - Identity-mechanism-redesign design-point §5.2 INV-7a/b/c(`:244-339`)+ §4.1 4 条硬定义(`:162-198`)
- Outputs / Downstream:
  - Slice 2 Identity-as-Claim refactor blueprint(`workflow/blueprints/active/2026-05-29_slice-2-identity-as-claim.md` 起草前置)
  - 后续 ADR-API(Q14 schema.extend evolution 三分)依赖本 ADR §4.3 cache lifecycle 跟 schema-evolution hook 的对齐
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-API / ADR-INV9 / ADR-SYS-A / ADR-SYS-B / ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-ic-identity-as-claim-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping 锁 Q1/Q2/Q3/Q16 同 ADR + §4.4 Step 1 zero-Q-PR1 dependency)
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`(ADR-FI §4.3-bis Identity descriptor 已 settled,本 ADR §4.2 emission 输入是 `Identity()` 形态产出的 schema_ir Identity 字段)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q1/Q2/Q3/Q16 — 全部 Slice 2 / Identity-as-Claim cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q1 | `fg.fields.set(IdentityField, ...)` schema-aware rejection at Layer 2 | `audit:514` | Identity-as-Claim |
| Q2 | Identity Claim emission layer(SDK `create` 内 vs application 层 derive) | `audit:515` | Identity-as-Claim |
| Q3 | INV-7c 策略 C cache lifecycle(init/lazy/schema-evolution hook) | `audit:516` | Identity-as-Claim |
| Q16 | `:exists` Claim emission removal timing | `audit:530` | Identity-as-Claim |

### 1.2 Meta-ADR locked constraints relevant to Identity-as-Claim

- **§4.2 grouping**:Q1/Q2/Q3/Q16 必须**同一 ADR**(本 ADR);拆分会 force "emission layer + cache lifecycle + Layer 2 boundary check + `:exists` co-emission" 跨 4 个 ADR 协调
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / PyReason adapter rewrite — confirmed,本 ADR 与 adapter 无关
- **§4.4 4-layer enforcement**:Layer 2 schema-aware rejection 在 application 层(strict)+ SDK shell 层(strict)— 跟 ADR-FI §4.4.2 caller contract 一致

### 1.3 ADR-FI 已锁的输入

- ADR-FI §4.3-bis:Identity descriptor public signature = `Identity(*, description=None, pattern=None)`;本 ADR §4.2 emission 路径输入的 schema_ir Identity 字段 来自 ADR-FI 锁定的 descriptor 形态
- ADR-FI §4.2:`_DataMember` internal base — 本 ADR 不重复讨论 descriptor extension
- ADR-FI §4.4:Layer 4 enum/pattern dual-layer validation — Identity Claim 的 value validation(per identity §8.4 enum-on-Identity-field)走 §4.4.2 application 层 write-path 路径,跟本 ADR §4.2 emission layer 兼容

### 1.4 Shipped baseline(audit §5.2 / §5.4)

**已 shipped 的 Identity Claim emission 路径**:
- `application/entity_write.py:323-348` `_materialization_ops`:为每个未实例化 entity append `PlannedOp(op="set", field=<identity_field>, value=ref.identity[name])` Identity Claim ops + `PlannedOp(op="record_exists")` `:exists` Claim op
- `application/entity_write.py:389-391` `_apply_op` 把 `record_exists` 转成 `set_field(store.ledger, info.exists_predicate_id, target_e_ref, [], meta)`(empty rest_terms = boolean indicator)
- `authoring/schema_compile.py:152-159` for each identity_field 调用 `_compile_identity_predicate` → 产 `is_identity_field: True` 的 predicate dict
- `authoring/schema_compile.py:140-150` `<EntityType>:exists` predicate 同步 declared with `is_entity_exists: True`
- `core/protocol/idref_v1.py:67-73` `encode_idref_v1(EntityType, tuples)` 已 shipped(audit A1 / N5,**baseline 状态**,本 ADR 不 re-lock)

**已 shipped 的 IdentityEditor 拒绝路径**:
- `sdk/facade.py:448-479` IdentityEditor 的 `set/add/retract` raise `SDKStoreError`(EntityEditor 子路径)— 但**入口** `fg.fields.set(IdentityField, ...)` 是否 schema-aware reject 未在 baseline 完整覆盖

**未 shipped 的 protected-anchor enforcement 路径**:
- `fg.assertions.retract(asrt_id)` 路径:**未** schema-aware check Identity Claim **也未** check `<EntityType>:exists` Claim(per design-point §5.2.3 强制点 4 仅 Identity;`:exists` 守护属本 ADR §4.4 transitional guard,新增)— 需要 application 层 in-memory caches + lookup
- `fg.fields.set/add/retract/delete` 直接路径 vs IdentityEditor 子路径:确认两个入口都 reject Identity 是本 ADR §4.1 的 Q
- shipped `sdk/store.py:1917` `_identity_values_by_e_ref` shadow store:本 ADR §4.2.3 定位为 **legacy/internal 兼容路径**(非 contract);Step 2+ eager-emission 演化方向可移除

## 2. Scope

本 ADR **锁**以下 4 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q1** | Layer 2 schema-aware rejection 路径(value-oriented `fg.fields.*` 入口 + Layer 3 `fg.assertions.retract(asrt_id)` 入口 双路径硬拒绝;Identity → INV-7c,`:exists` → existence-claim transitional guard) |
| **§4.2 Q2** | Identity Claim emission 在 application 层(已 shipped 路径 formalize,SDK shell 不直接 emit);**emission input contract** = 必须携带完整 identity bundle;**Layer 2 fields API 永不作为 emission path**;shipped lazy materialization via shadow store 定位为 legacy/internal |
| **§4.3 Q3** | 策略 C cache lifecycle(application 层 in-memory **两个独立 frozenset**:`_identity_pred_ids`(INV-7c)+ `_exists_pred_ids`(transitional guard);hybrid init + schema-evolution hook) |
| **§4.4 Q16** | `:exists` Claim emission Step 1 保留为 co-emission + **existence-claim transitional guard**(命名独立于 INV-7c);Step 2+ 评估移除(transitional contract) |

## 3. Non-scope

本 ADR **不**锁:

| 不锁 | 留给谁 |
|---|---|
| `Identity()` descriptor public signature | ADR-FI §4.3-bis(已 adopted)|
| `_DataMember` 共通基类 extension(`validators` / `constraints` / `alias`)| Step 2+ extension ADR |
| `idref_v1` typed content-derived hash 编码细节 | shipped baseline(audit A1 / N5,**no Q**)|
| `fg.schema.register / extend / apply` 三分 + schema evolution 拒绝 Identity↔Field swap | ADR-API(Q14)|
| `__system__.revokes` namespace + payload shape | ADR-SYS-A(Q5a)+ ADR-SYS-B(Q5b/Q15)|
| INV-9 strict adapter enforcement(`len(rest_terms) <= 1`)| ADR-INV9(Q4)+ Slice 5+ adapter rewrite |
| Rule compiler 移除 `:exists` 依赖路径重写 | Step 2+ rule-layer follow-up(本 ADR §4.4 仅 transitional contract,移除时机不锁) |
| Slice 2 落地的 blueprint slicing | Slice 2 blueprint |

## 4. Decision

### 4.1 Q1 — Layer 2 schema-aware rejection:**双路径硬拒绝**

**锁定**:Identity Claim 受 INV-7c 保护,**不允许**通过以下任一路径单独修改:

| 路径 | 行为 | 拒绝依据 | 已 shipped? |
|---|---|---|---|
| `fg.fields.set(Identity_descriptor, e_ref, value)` | raise `SDKStoreError(INV-7c)` | INV-7c | 部分(`IdentityEditor` 子路径 shipped;入口路径需补)|
| `fg.fields.add(Identity_descriptor, e_ref, value)` | raise `SDKStoreError(INV-7c)` | INV-7c | 同上 |
| `fg.fields.retract(Identity_descriptor, e_ref[, value])` | raise `SDKStoreError(INV-7c)` | INV-7c | 同上 |
| `fg.fields.delete(Identity_descriptor, e_ref)` | raise `SDKStoreError(INV-7c)` | INV-7c | 同上 |
| `fg.assertions.retract(asrt_id)`(asrt 指向 Identity Claim)| raise `SDKStoreError(INV-7c)` | INV-7c | **未 shipped** |
| `fg.assertions.retract(asrt_id)`(asrt 指向 `<EntityType>:exists` Claim)| raise `SDKStoreError(existence-claim transitional guard)` | §4.4 transitional contract(**非** INV-7c)| **未 shipped** |

**API 形态说明**(避免 layer 越界):
- Layer 2 `fg.fields.*` 是 **value-oriented**(Field descriptor + e_ref + value);**不接受** asrt_id 参数
- asrt_id 导航属于 Layer 3 `fg.assertions.*`;`fg.assertions.retract(asrt_id)` 才是 asrt_id-based retract
- 本 §4.1 reject 列表覆盖两个 layer 的所有 Identity-touching 入口点;`fg.fields.retract(Field, e_ref[, value])` 具体 signature 由 ADR-API Q10 锁

**唯一合法的 Identity Claim 生成 / 撤销路径**:
- **生成**:`fg.entities.create(EntityCls, **identity_kwargs)` — **携带完整 identity bundle 的 entity materialization path**(per §4.2 materialization input contract)
- **整批撤销**:`fg.entities.delete(e_ref)` — 撤销该 e_ref 下所有 Identity + `:exists` + Field Claim,atomic(per design-point §5.2.3 强制点 3)

**注意**:Layer 2 fields API(`fg.fields.set/add/...`)即使针对 non-Identity Field 也**不**作为 Identity Claim 生成路径 — 见 §4.2 emission input contract。

**实施位置**:
- application 层 write protocol 的 entry point(`apply_write_plan` 之前的 pre-validation)
- SDK shell 层 `fg.fields.*` / `fg.assertions.retract` 在调 application 之前先做 schema-aware Identity / `:exists` check
- 双层 check(SDK shell + application)跟 ADR-FI §4.4 4-layer enforcement 模式一致 — defense-in-depth,但 application 层是 source of truth(SDK shell check 是 fail-fast 优化)

**check 实现依赖**:application 层 in-memory `protected_anchor_pred_ids = identity_pred_ids ∪ exists_pred_ids`(§4.3 锁定)— retract 路径先 ledger lookup pred_id by asrt_id,然后 O(1) membership check;若命中 `identity_pred_ids` raise INV-7c,若命中 `exists_pred_ids` raise existence-claim transitional guard。

**Error messages**:

```python
# Identity Claim path (INV-7c):
raise SDKStoreError(
    f"Identity Claim {asrt_id} (pred_id={pred_id}) is immutable per INV-7c.\n"
    f"Identity Claims can only be:\n"
    f"  - created via fg.entities.create(EntityCls, **identity_kwargs)\n"
    f"  - removed as part of fg.entities.delete(e_ref) (atomic full-entity revoke)\n"
    f"To modify the identity bundle of an entity, delete the old entity and "
    f"create a new one with the new identity values (Identity is immutable per INV-7a)."
)

# `:exists` Claim path (transitional guard, see §4.4):
raise SDKStoreError(
    f"<EntityType>:exists Claim {asrt_id} (pred_id={pred_id}) cannot be retracted "
    f"independently. The :exists Claim is co-emitted atomically with Identity Claims "
    f"and can only be removed via fg.entities.delete(e_ref) (atomic full-entity revoke). "
    f"This guard is transitional — Step 2+ may remove :exists emission entirely "
    f"(see ADR-IC §4.4)."
)
```

### 4.2 Q2 — Identity Claim emission layer:**application 层 derive**(formalize already-shipped)

**锁定**:Identity Claim emission 在 **application 层 write-plan adapter**(`application/entity_write.py:_materialization_ops`),不在 SDK shell。

**为什么 application 层而非 SDK shell**:
- INV-6 application-first runtime authority:任何"语义上的写入决策"(emit X Claim that is implied by Y operation)必须在 application 层 derive,SDK shell 仅做 DTO/protocol 翻译
- 已 shipped pattern(`_materialization_ops`)— Identity Claim emission 已经走 `PlannedOpDTO` 抽象,跟 Field write 共享同一 op pipeline + ledger append path
- SDK shell 内 emit 会 force SDK 层进 ledger 写知识 — 违反 §5 / §6 既定 layering

#### 4.2.1 Emission input contract — 必须携带完整 identity bundle

**核心锁定**:Identity Claim emission **只能**接受**携带完整 identity bundle** 的输入:

```python
# emission input shape (application layer):
EntityRef(
    entity_type="User",
    identity={"tenant_id": "t1", "user_id": "u1"},   # ★ 完整 identity bundle
)
```

- emission 路径(`_materialization_ops`)**不接受** 仅 encoded `e_ref` 字符串作为输入 — 因 encoded string 无法 reverse-derive identity 字段值,无法生成 Identity Claim 的 `value`
- 任何 caller 调用 emission 路径必须**已经持有** 完整 identity bundle(从 user 直接传入 OR 从其他来源恢复)

#### 4.2.2 Public 入口的分类(carries-bundle vs encoded-only)

| 入口 | 携带 identity bundle? | 能触发 Identity Claim emission? |
|---|---|---|
| `fg.entities.create(EntityCls, **identity_kwargs)` | ✅ 直接携带 | ✅ **是**(authoritative path)|
| `fg.edit(EntityCls, **identity_kwargs)` → `EntityEditor` | ✅ 直接携带 | ✅ 是(等价于 create + field writes 的 atomic 形态)|
| `fg.fields.set(Field, e_ref_string, value)` | ❌ 仅 encoded e_ref | ❌ **否**(per emission input contract)|
| `fg.fields.add/retract/delete(Field, e_ref_string, ...)` | ❌ 仅 encoded e_ref | ❌ 否 |
| `fg.assertions.write(...)` | (per ADR-SYS-A 决策)| (per ADR-SYS-A 决策)|

**核心 contract**:Layer 2 fields API(`fg.fields.*`)**永远不**作为 Identity Claim 生成路径 — 即使是 first-write-against-this-e_ref。

#### 4.2.3 Shipped lazy materialization 路径(legacy / internal 兼容)

shipped 代码中 `fg.fields.set(Field, e_ref_string, value)` 调用 first-write-against-this-e_ref 时,**确实**会触发 `_materialization_ops` 生成 Identity Claims — 这是通过 **SDK shell legacy shadow store** 路径实现的:

```text
shipped 路径(Slice 2 不破坏):
fg.fields.set(Field, e_ref_string, value)
  → SDK shell lookup `_identity_values_by_e_ref[e_ref_string]`(legacy shadow store)
  → 恢复出 identity bundle dict
  → 构造 EntityRef(entity_type, identity={...})
  → 传入 application 层 apply_write_plan
  → _materialization_ops 看到该 e_ref 未在 materialized_refs 集合中
  → emit Identity Claims + :exists Claim(原子)
```

**`_identity_values_by_e_ref` 是 legacy in-memory shadow store**(`sdk/store.py:923/1917`),由 `sdk.ref(EntityCls, **identity)` / `fg.entities.create(...)` populate。它是兼容性细节,**不**是 Layer 2 public API 设计的一部分:

- 本 ADR 的 contract:**Layer 2 fields API 在概念上不持有 identity bundle**;它们 work 是因为 SDK shell 借助 legacy shadow store 恢复 bundle
- shadow store 只对**当前 process 内已调过 `sdk.ref(...)` 的 e_ref** 有效;跨 process / 持久化场景下 shadow store 缺失 → fields.set 在 first-write 时无法恢复 identity bundle → 应**fail-fast** raise(具体 error path 由 Slice 2 blueprint 决定)
- 这跟 design-point §5.2.3 强制点 1 "Identity Claim 只能由 `fg.entities.create` 内部生成" 在**契约层面**一致;shipped lazy path 是兼容性实施细节而非违反契约

#### 4.2.4 Step 2+ 演化方向(forward carve-out,not lock)

- **Eager emission @ create**:`fg.entities.create(...)` 改为直接 emit Identity Claims 到 ledger(不等 first-Field-write)— `_materialization_ops` lazy 路径变 dead code
- **Shadow store 删除**:`_identity_values_by_e_ref` 删除,`fg.fields.set(Field, e_ref_string, value)` 若 e_ref 未 materialized → raise EntityNotInitializedError(显式 contract)
- 本 ADR **不**承诺 Step 2+ 一定走该方向;只声明 shadow store 是 legacy 而非 contract-bearing

**触发器 atomic 保证**:不论 eager 还是 lazy 路径,所有 Identity Claim ops 跟 first-Field-write atomic(同 transaction)— per `_write_session` context manager(per audit N6 — `ledger.py:430-451`)。

#### 4.2.5 ADR-FI §4.3-bis 衔接

- ADR-FI 锁 `Identity()` descriptor 无 default → application 层 `_materialization_ops` 不再做 `default_factory` materialize(对应 shipped `schema_runtime.py:329` 路径在 Slice 1 完成后会简化)
- ADR-FI 锁 `Identity()` 无 `primary_key` → schema_compile `:258-259` `if identity_field.get("primary_key") is True: predicate["primary_key"] = True` 路径在 Slice 1 完成后变 dead code,Slice 2 可一并清理(non-load-bearing follow-up)

### 4.3 Q3 — INV-7c 策略 C cache lifecycle:**hybrid init + schema-evolution hook**

**锁定**:application 层 in-memory protected-anchor pred_id set cache 实施策略:

#### 4.3.1 Cache scope — 两个独立 frozenset + 统一 union

本 ADR 锁定 **两个** application 层 in-memory caches(同时 build,同时 hook,概念分开):

```python
# application 层 state 字段(具体 attribute path 由 Slice 2 决定):
self._identity_pred_ids: frozenset[str]      # filter is_identity_field == True
self._exists_pred_ids:   frozenset[str]      # filter is_entity_exists  == True

# 统一 read API(避免 caller 重复 check 两个):
@property
def _protected_anchor_pred_ids(self) -> frozenset[str]:
    return self._identity_pred_ids | self._exists_pred_ids
```

**为什么两个独立 frozenset**:
- `_identity_pred_ids` 是 **INV-7c 的本体**(per design-point §5.2 INV-7c)— Identity Claim 受 immutable anchor 保护;membership 命中 → raise INV-7c
- `_exists_pred_ids` 是 **§4.4 transitional guard 的本体** — `<EntityType>:exists` Claim 受 §4.4 co-emission contract 保护(**非** INV-7c);membership 命中 → raise existence-claim transitional guard
- Step 2+ 若移除 `:exists` co-emission(per §4.4),`_exists_pred_ids` 变 empty frozenset → `_protected_anchor_pred_ids = _identity_pred_ids`;`_identity_pred_ids` 不动 → INV-7c 保持
- 同 schema_compile 路径下 build(per `is_identity_field` / `is_entity_exists` flag 已 declared in schema_ir per audit N3)— marginal implementation cost = 1 个 extra filter pass

**Reject 路径 routing**:

```python
# Slice 2 implementation sketch (application 层 retract entry):
def _check_retract_allowed(self, asrt_id: str) -> None:
    pred_id = self.ledger.lookup_pred_id(asrt_id)
    if pred_id is None:
        return  # asrt_id 不存在,let downstream raise
    if pred_id in self._identity_pred_ids:
        raise SDKStoreError(f"... per INV-7c ...")   # per §4.1 Identity error message
    if pred_id in self._exists_pred_ids:
        raise SDKStoreError(f"... existence-claim transitional guard ...")  # per §4.1 :exists error message
```

#### 4.3.2 Layer 锁定

策略 **C**(per design-point §5.2.3 table)— application 层 in-memory `frozenset[str]` caches,**拒绝**策略 B(Claim meta tag — 违背 claim_meta 语义)。

#### 4.3.3 Lifecycle — Hybrid init + schema-evolution hook

| 时机 | 触发器 | 行为(同时 update 两个 frozenset)|
|---|---|---|
| **Init** | `Store.__init__` / `fg.schema.register(EntityCls)` 第一次 attach schema | 扫 `schema_ir` 所有 predicate;filter `is_identity_field == True` → `_identity_pred_ids`;filter `is_entity_exists == True` → `_exists_pred_ids`;两个 frozenset 同 transaction build |
| **Schema evolution hook** | `fg.schema.extend(EntityCls)` / `fg.schema.register(new EntityCls)` | 增量 union update 两个 cache(append 新 entity 的 Identity pred_ids + `:exists` pred_id);per §4.3.5 union 假设依赖 ADR-API Q14 lock |
| **不 lazy** | — | first-retract 时建 cache 会让首次 retract path 慢 + 并发场景 race condition(同时多个 retract 触发 build → 重复扫 schema_ir) |
| **不 invalidate-on-write** | — | protected anchor pred_id set 跟单条 Claim 写入无关(只跟 schema 形态有关),无需 write-time invalidate |

#### 4.3.4 Concurrency 行为

- caches 都是 `frozenset[str]` — immutable;rebuild 时 atomic replace(`self._identity_pred_ids = frozenset(new_set)` + `self._exists_pred_ids = frozenset(new_set)`)
- read path(`pred_id in self._identity_pred_ids` / `pred_id in self._exists_pred_ids` lookup)是 O(1) lock-free
- write path(schema.extend 触发的增量更新)走 `self._schema_lock`(已 shipped per `_write_session` + `schema_runtime` 路径)

#### 4.3.5 Cache 存储位置

`application/schema_runtime.SchemaIndex` 或 `application/state` 新字段(具体 Slice 2 blueprint 决定;本 ADR 锁 layer + lifecycle + scope 不锁 exact attribute path)

#### 4.3.6 Schema evolution 衔接(留给 ADR-API Q14)

- 本 ADR **要求**(requires)ADR-API Q14 锁 `fg.schema.extend` 拒绝 Identity↔Field swap(per design-point §5.2.3 配套不变量)
- 该 explicit contract 是 §4.3.3 "union update 即可,无需 invalidation" 行为的 **前置条件**
- 若 ADR-API Q14 改变(允许 Identity↔Field swap),本 §4.3 cache lifecycle 的 union-only 假设破裂 → 触发本 ADR §7.4 no-retroactive 路径,必须 supersede 本 ADR
- 同样的 dependency 关系适用 `_exists_pred_ids`:ADR-API Q14 必须 enforce `<EntityType>:exists` predicate 的 declaration 不可在 schema.extend 中删除或改 owner_type

### 4.4 Q16 — `:exists` Claim emission timing:**Step 1 保留 co-emission + existence-claim transitional guard;Step 2+ 评估移除**

**锁定**:`:exists` Claim emission **Step 1 保留 + 独立的 transitional guard**;**不**在本 ADR 锁移除时机。

#### 4.4.1 Step 1 保留契约

- `:exists` 是 **co-emission**(跟 Identity Claims 一起 emit at `_materialization_ops`,per §4.2)— 不是独立 emission 路径
- `:exists` Claim 永远跟 Identity Claims 的 active set 同生同灭 — 通过 **existence-claim transitional guard**(per §4.1 / §4.3.1)拒绝单独 retract,**非** INV-7c
- Rule layer 继续依赖 `<EntityType>:exists` 作为 unified field shape(per shipped `application/protocol/rule.py:528-530`)— 不强制 rule compiler rewrite

#### 4.4.2 为什么不复用 INV-7c 命名 `:exists` 保护

- INV-7c 的 conceptual 范围(per identity §5.2 INV-7c):**Identity** Claim 与 e_ref hash 输入一致;`<EntityType>:exists` Claim 不在 idref_v1 hash 输入中,也不是 Identity bundle 的一部分 — 概念上**不属于** INV-7c
- 若把 `:exists` 保护写成 INV-7c,会让 INV-7c 跨越其本体定义(per design-point §5.2.3 强制点 1-4 仅列 Identity Claim)— 在 Step 2+ 移除 `:exists` 时,INV-7c 范围会"无故收窄",制造伪 supersede
- 命名 **existence-claim transitional guard** 让两个保护机制 lifecycle 独立:Identity guard(INV-7c)永久;`:exists` guard 跟随 §4.4 transitional contract 生死

#### 4.4.3 为什么 Step 1 不移除

- Rule layer 移除 `:exists` 依赖需要重写 rule compiler 的 `<EntityType>:exists` 替代为 `<EntityType>:<any_identity_field>` 检测路径 — scope 超出 Slice 2 Identity-as-Claim cluster
- `:exists` co-emission 跟 Identity Claims atomic;不引入额外 INV-7c 失败模式
- Step 2+ 评估移除时,Identity Claims 已 Active 在 ledger → rule layer 可以学会从 Identity Claims 推断 entity existence(无需 `<EntityType>:exists` predicate)

#### 4.4.4 Step 2+ 移除前置条件(本 ADR forward-pointer,not lock)

- Rule compiler / inspect 路径完整覆盖"用 Identity Claim 推 entity existence"语义
- 现有 `<EntityType>:exists` Claim 历史数据迁移路径(re-emit 为 Identity Claims?或保留为 legacy?)— 留 Step 2+ ADR
- Rule body 兼容性:用户写过 `User:exists(u)` 的 rule 是否破坏
- existence-claim transitional guard 同步移除:`_exists_pred_ids` 变 empty,reject 路径 dead code 清理(per §4.3.1 union shape)

#### 4.4.5 Transitional contract clarity

- 本 ADR §4.4 **不**承诺 `:exists` 永久保留;也**不**承诺 Step 2+ 一定移除
- 唯一锁定:
  1. Step 1 内 `:exists` 是 Identity Claim co-emission 的一部分;不允许独立 retract `<EntityType>:exists` Claim(通过 §4.3.1 `_exists_pred_ids` cache + §4.1 existence-claim transitional guard 实施)
  2. existence-claim transitional guard 的 lifecycle 跟 `:exists` co-emission 绑定;Step 2+ 移除 `:exists` 时 guard 同步退役

#### 4.4.6 Slice 5 implemented update — user-path co-emission retired, legacy/virtual surfaces retained

Slice 5 (2026-05-30, Q-EXISTS `870e1f1f`) implemented the Step 2+ narrow
cleanup path. Current status after Slice 5:

- User-facing materialization paths (`fg.entities.create`, lazy
  SDK-field materialization, and SDK batch user planners) no longer emit new
  `<EntityType>:exists` Claims.
- `fg.entities.exists(EntityCls, **identity)` now uses complete active Identity
  Claim bundle visibility for the deterministic e_ref, not active `:exists`
  Claims.
- `fg.entities.delete(...)` revokes Identity + Field Claims for newly
  materialized entities and tolerates the absence of active `:exists` Claims;
  legacy `:exists` Claims, when present, are handled by the same path-bound
  whole-entity delete path.
- Existing legacy `:exists` Claims remain protected under the unchanged
  `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` code. They are not migrated,
  bulk-revoked, or rewritten by Slice 5.
- `exists_pred_ids` remains populated for legacy guard classification and
  schema compatibility.
- Rule DSL `Entity:exists` remains virtual/internal syntax, Q-PR1 derivation
  accept remains out of scope, and shadow-store removal remains a separate
  carry-forward.

### 4.5 Cross-Q decision summary

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q1 | 双路径硬拒绝 — Layer 2 `fg.fields.*`(value-oriented,Identity descriptor)+ Layer 3 `fg.assertions.retract(asrt_id)`(Identity asrt OR `:exists` asrt) | application 层 entry pre-validation + SDK shell fail-fast check;Identity error → INV-7c,`:exists` error → existence-claim transitional guard(§4.4) | Slice 2 |
| Q2 | application 层 derive;emission input contract = `EntityRef(entity_type, identity={...})`;Layer 2 fields API **不**作为 emission path | `entity_write.py:_materialization_ops`(已 ship);Slice 2 主要做 contract test 覆盖 + 明确 shipped shadow store legacy 定位 | Slice 2 |
| Q3 | 策略 C + hybrid init/schema-evolution hook;**两个独立 frozenset**(`_identity_pred_ids` ∪ `_exists_pred_ids` = `_protected_anchor_pred_ids`)| `application/state` 新 2 个 frozenset fields + `Store.__init__` build + `fg.schema.extend/register` hook + statement routing(Identity vs `:exists` 分别 error message)| Slice 2 |
| Q16 | Step 1 保留 co-emission;`:exists` 单独 retract 由 **existence-claim transitional guard**(**非** INV-7c)守门;Step 2+ 评估移除 | `entity_write.py:_materialization_ops` 已 ship `record_exists` op;本 ADR 锁 transitional contract + guard lifecycle | Slice 2 |

**整体**:Slice 2 Identity-as-Claim 实施范围 ≈ 150-300 行代码改动:
- §4.1 Q1 schema-aware reject 双路径:`application` write-protocol entry + `sdk/facade` reject hook + 两个独立 error message path(Identity / `:exists`)(+测试覆盖)
- §4.3 Q3 cache 初始化:`application/state` 2 个 frozenset fields + `Store.__init__` build + `fg.schema.extend` hook
- §4.2 Q2 + §4.4 Q16 主要是 **contract test 覆盖**(已 ship 行为 formalize 为 ADR-anchored assertion)+ shadow store legacy 定位文档化 — 代码改动小

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q1 alternative — 仅 `fg.assertions.retract` 路径 reject,`fg.fields.*` 不补 check

- **Why rejected**:`fg.fields.set(Identity_descriptor, ...)` 入口路径若不 schema-aware reject,user 可能绕过 IdentityEditor 子路径(EntityEditor 已 shipped reject)直接调 fields.set + 拿到 Identity descriptor → 写入污染 Identity bundle。双路径 reject 是 INV-7c defense-in-depth。

#### Q1 alternative — 仅 SDK shell reject,application 层不重复

- **Why rejected**:application 层是 source of truth(per INV-6);SDK shell reject 是 fail-fast 优化。绕过 SDK shell(测试 / migration / internal writer)直接调 application 层 write protocol 时,application 层无 INV-7c guard 会破坏一致性。defense-in-depth 跟 ADR-FI §4.4 4-layer enforcement 一致。

#### Q1 alternative — `fg.fields.retract(asrt_id)` 接受 asrt_id 参数

- **Why rejected**:Layer 2 fields API 在分层设计上是 **value-oriented**(Field descriptor + e_ref + value);asrt_id 导航属于 Layer 3 `fg.assertions.*`。若让 `fg.fields.retract(asrt_id)` 存在,会让 fields API 跨 Layer 2/3 界限,鼓励 user 在 Layer 2 view 内做 asrt-level 操作,跟 design-point §12 三层分层冲突。Identity asrt-by-id reject 走 `fg.assertions.retract(asrt_id)` 路径(per §4.1 reject table 第 5/6 行)。`fg.fields.retract` 的具体 signature(value-oriented)留 ADR-API Q10 锁。

#### Q2 alternative — SDK shell 内 emit Identity Claim

- **Why rejected**:违反 INV-6(application-first runtime authority);SDK shell 需要进 ledger.append_assertion 调用 → SDK 层穿透协议层;跟 G1-G5 / Track 3 已确立的 SDK-as-ergonomic-shell 模式冲突。已 shipped pattern(`_materialization_ops`)也已在 application 层,本 ADR 仅 formalize。

#### Q2 alternative — protocol 层 `set_field` 内自动 emit(implicit)

- **Why rejected**:protocol 层 schema-agnostic(per meta-ADR §4.4)— 不应感知 Identity vs Field;若 protocol 层 emit Identity Claim,需要 protocol 层 import schema_runtime → 跨 layer 依赖反向;跟 meta-ADR §4.4 4-layer enforcement 冲突。

#### Q2 alternative — Layer 2 `fg.fields.*` 入口作为 Identity Claim emission path(隐式 create)

- **Why rejected**:Layer 2 fields API 输入是 `(Field, e_ref_string, value)` — encoded e_ref 无法 reverse-derive identity 字段值(per §4.2.1 emission input contract);若 fields API 隐式触发 emission,会:(i) 让 user 不知道 "fields.set" 也能创建 entity → 模糊 `fg.entities.create` 跟 `fg.fields.set` 的语义边界;(ii) 强迫 SDK shell 永久维护 `_identity_values_by_e_ref` shadow store(否则 fields.set 拿不到 identity bundle);(iii) 阻止 Step 2+ 演化(eager-emission + shadow store 删除)。本 ADR §4.2.2 锁定 Layer 2 fields API **永远不**作为 emission path;shipped lazy materialization 通过 shadow store 实现是 legacy 兼容细节(per §4.2.3),不进 design contract。

#### Q3 alternative — 策略 A(每次完整链 — 每次 retract 查 schema)

- **Why rejected**:simple but 每次 retract 2 次 query(ledger + schema lookup);schema cache 命中率高时实际开销小,但 retract 是热路径(audit/explain workflows),开销累积。策略 C 是 0-cost lookup(O(1) `in frozenset`),implementation cost 增量是初始化 5-15 行。

#### Q3 alternative — 策略 B(Claim meta tag — `_meta["is_identity"]`)

- **Why rejected**:per design-point §5.2.3 table 已明 reject — 把 structural truth 写进 `claim_meta`(audit/provenance 业务 meta 字段)违背 claim_meta 语义;增大 ledger 存储;无 schema-evolution 路径(改 schema 之后旧 Claim 的 meta tag 不变,跟新 schema_ir 分裂)。

#### Q3 alternative — Lazy init(first retract 时 build cache)

- **Why rejected**:first-retract 慢(scan 全 schema_ir);并发场景下 race condition(多个并发 retract 同时检测 cache 未建 → 同时 build → 重复扫);init 路径成本 < 0.1ms,无收益。

#### Q3 alternative — Init-only(不响应 schema.extend)

- **Why rejected**:Step 2+ schema extension 工作流必然触发 schema.extend → cache stale → 新 Entity 的 Identity Claim 不被 INV-7c 保护。Step 1 即使无 user-visible schema.extend,也要为 Step 2+ ready。union semantics(per §4.3.6 ADR-API Q14 contract 要求)让 hook 路径轻量。

#### Q3 alternative — 单 frozenset(`_protected_anchor_pred_ids` 直接合 Identity + `:exists`)

- **Why rejected**:把 Identity guard + `:exists` guard 合并成同一 set 后,reject 路径无法区分 Identity Claim violation(INV-7c)vs `:exists` Claim violation(existence-claim transitional guard)— 两种 violation 的 error message / migration hint / lifecycle 不同(per §4.4.2):INV-7c 是**永久** structural invariant;`:exists` guard 跟 `:exists` co-emission 同生死(Step 2+ 移除 `:exists` 时 guard 退役)。合并 set 后 Step 2+ 移除 `:exists` 需要单独 enumerate 哪些 pred_id 退役 — 跟两个独立 set 的设计 marginal cost 几乎相等。两个独立 set + `_protected_anchor_pred_ids` union property 是最干净的分层。

#### Q16 alternative — Step 1 移除 `:exists` Claim emission

- **Why rejected**:rule layer 当前依赖 `<EntityType>:exists` predicate(`application/protocol/rule.py:528-530` + 多处 inspect 路径);移除会 force rule compiler rewrite — scope 不属于 Slice 2 Identity-as-Claim cluster。Step 1 保留 co-emission 是 safe 路径。

#### Q16 alternative — Step 1 双写一段时间(同时 emit `:exists` 和 Identity Claims 但保留 read fallback)

- **Why rejected**:实际上 Step 1 就是双写形态(Identity Claims + `:exists` 同 atomic emit);"双写一段时间"暗示 Step 2+ 会移除,这跟本 ADR §4.4 "Step 2+ 评估移除,不承诺" 不一致。Step 1 保留 = 正常 co-emission,不附加 deprecation timeline。

#### Q16 alternative — 永久保留 `:exists`(legacy emission,无强制)

- **Why rejected**:留路径但不承诺移除会形成 dead-weight,跟 Identity-as-Claim 设计目标(Identity Claim 已经能 indicate entity existence)目标冲突;**也**不应承诺永不移除 — Step 2+ rule layer rewrite 是合理路径。"Step 1 保留 + Step 2+ 评估" 留足够灵活度。

### 5.2 Cross-Q rejected combinations

#### Option `IC-shell-first`:Q2 SDK shell 内 emit + Q3 cache 在 SDK shell 层

- **Why rejected**:整套向 SDK shell 倾斜违反 INV-6 + ADR-FI §4.4 enforcement 层级;SDK shell 承担 schema-aware 责任会让 SDK 重新变厚(post-L redesign 已经把 SDK shell 收窄到 ergonomic 翻译层)。

#### Option `IC-protocol-strict`:Q1 reject 下沉到 protocol 层 + Q3 cache 在 protocol 层

- **Why rejected**:protocol 层 schema-agnostic(per meta-ADR §4.4 + 本 ADR §5.1 Q2 alternative rationale);protocol 层 strict enforcement 是 Step 2+ Slice 5+ ADR 范畴(adapter rewrite + INV-9 strict);Step 1 强行下沉会跟 ADR-INV9 / Q4 separation contract 冲突。

#### Option `IC-defer-cache-to-step2`:Q3 cache lifecycle 延后到 Step 2+

- **Why rejected**:Q1 reject 路径**实现依赖** §4.3 cache(retract 路径需要 `asrt_id → pred_id → identity check` O(1));不锁 cache lifecycle 会 force Slice 2 blueprint 选 fallback 策略(naive every-retract scan)— 实施完成后再切策略 C 是 destabilizing refactor。Q1 + Q3 必须同 Slice 落地。

#### Option `IC-eager-exists-removal`:Q16 Step 1 移除 `:exists`

- **Why rejected**:跟 §5.1 Q16 alternative 同理由;此外 cluster 整体 cohesion — Q1/Q2/Q3 是 Identity Claim mechanism 建设,Q16 移除是 rule layer rewrite — 不同 codebase area,不该同 Slice。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q1/Q2/Q3/Q16 rows(`audit:514-516, 530`)
- audit §5.2 A2 row(Layer 2 Identity reject)— Q1 source
- audit §5.2 A4 row(Identity Claim emission 半 shipped)— Q2 source;baseline 已 ship 在 application 层 `_materialization_ops`
- audit §5.2 A16 row(INV-7c 检测链)+ A18 row(schema-evolution hook)— Q3 source
- audit §5.2 A20 row(`:exists` co-emission)— Q16 source
- audit §5.4 N2 row(Identity 已 declared in schema_ir)— §4.2 emission 输入路径已 baseline
- audit §5.4 N3 row(`is_identity_field` flag)— §4.3 cache build 输入路径已 baseline
- audit §6 A1 row(`encode_idref_v1` Q1-design-point shipped)— **baseline,本 ADR 不 lock**

### 6.2 Shipped code citations

- `src/factgraph/application/entity_write.py:323-348` `_materialization_ops` — Q2 emission 路径(已 ship,本 ADR formalize)
- `src/factgraph/application/entity_write.py:382-402` `_apply_op` — `record_exists` 转 `set_field(info.exists_predicate_id, ...)` 实施
- `src/factgraph/authoring/schema_compile.py:140-150` `<EntityType>:exists` predicate declaration + `is_entity_exists: True`
- `src/factgraph/authoring/schema_compile.py:152-159` `_compile_identity_predicate` 循环调用
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` — produces predicate with `is_identity_field: True`(Q3 cache build 输入路径)
- `src/factgraph/core/protocol/idref_v1.py:67-73` `encode_idref_v1` — baseline reference(本 ADR §1.4 标注为 **no Q**)
- `src/factgraph/sdk/store.py:1916-1917` `encode_idref_v1` SDK 调用 + `_identity_values_by_e_ref` shadow store(将随 Identity Claim ledger emission 在 Slice 2 后可简化,non-load-bearing follow-up)
- `src/factgraph/sdk/facade.py:448-479` IdentityEditor reject(已 ship 子路径;§4.1 Q1 入口路径补完)
- `src/factgraph/application/protocol/rule.py:528-530` rule layer 当前依赖 `:exists` — §4.4 Q16 不移除依据
- `src/factgraph/core/store/ledger.py:430-451` `_write_session` atomic context — §4.2 emission atomic 保证

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-IC grouping(Q1/Q2/Q3/Q16 同 ADR)— justifies 本 ADR 不拆 4 个 sub-ADR
- meta-ADR §4.4 4-layer enforcement(SDK shell + application strict;protocol/ledger delayed)— justifies §4.1 双路径 reject 在 SDK + application 层,不在 protocol 层;§4.3 cache 在 application 层
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency — 本 ADR §6.5 显式 confirm

### 6.4 Design-point citations

- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §4.1 4 条硬定义(`:162-198`)— INV-7a/b/c source
- identity §5.2 INV-7a Identity Anchor(`:250-258`)— §4.1 immutable 依据
- identity §5.2 INV-7b Identity-as-Claim mirrored(`:259-276`)— §4.2 emission 必要性依据
- identity §5.2 INV-7c Identity Claim ↔ e_ref 一致性(`:278-300`)— §4.1 Identity reject 路径 + §4.3 `_identity_pred_ids` cache 依据;**强制点 1-4 明确仅列 Identity Claim**(`:282-286`)— §4.4.2 "`:exists` 不属于 INV-7c" 的依据
- identity §5.2.3 INV-7c 实施 策略表 + Schema evolution 配套不变量(`:302-338`)— §4.3 策略 C + schema-extend 假设
- identity §13(Step 1 in-scope / Step 2+ 延后)— §4.4 Q16 Step 2+ 评估依据

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / adapter rewrite — confirmed Step 1 zero-blocker 合规。

**澄清**:§4.3 / §6.3 出现 "Step 2+" / "Slice 5+" 标识 — 那是**前向 carve-out**(本 ADR 不锁的范围交给未来哪个 Slice),**不是 dependency**。Slice 2 实施可在 Step 2+ ADR 起草前完成,不会被 block。

### 6.6 ADR-FI 兼容性 confirmation

- ADR-FI §4.3-bis(`b288ea9e`)锁 `Identity()` 无 `primary_key/default/default_factory` → 本 ADR §4.2 emission 路径 input shape 跟 ADR-FI 一致
- ADR-FI §4.4 dual-layer enum/pattern validation → 本 ADR §4.2 emission 路径触发的 Identity Claim value 通过同一 application 层 write-path `validate_field_value`(per ADR-FI §4.4.2)— **无冲突**
- ADR-FI §4.4.2 caller contract(protocol/ledger direct path 不覆盖)→ 本 ADR §4.1 双路径 reject 同遵守(protocol 层不动)— **layer 模式一致**

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 2 Identity-as-Claim refactor blueprint**(`workflow/blueprints/active/2026-05-29_slice-2-identity-as-claim.md`)可起草 — Q1/Q2/Q3/Q16 全部 locked
- **ADR-API**(Q14 schema.extend 三分)可起草 — 本 ADR §4.3 cache lifecycle 跟 ADR-API 的 explicit contract 已锁(schema.extend 不允许 Identity↔Field swap)
- **ADR-SYS-A / ADR-SYS-B** 可独立起草 — 跟本 ADR 无 Q dependency(System namespace vs Identity-as-Claim disjoint;两者都遵守 application-layer Identity pred_id set 路径但 cluster 边界清晰)

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 2 blueprint draft(`workflow/blueprints/active/2026-05-29_slice-2-identity-as-claim.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-IC adopt 后 |
| Slice 2 pre-impl grep:扫所有 `IdentityEditor` reject + `fg.fields.set/add/retract/delete` 入口 + `fg.assertions.retract` 入口的 reject 路径 — confirm 双路径 reject 实施完整 | Slice 2 blueprint preflight(Step 4.6.5)| Slice 2 blueprint scoped 后 |
| `application/state` Identity pred_id set cache 初始化(per Q3)+ `Store.__init__` build + `fg.schema.extend/register` hook | Slice 2 implementation | Slice 2 Step 4.7 |
| Contract test 覆盖:Q2 emission already-shipped path + Q16 `:exists` co-emission 同 atomic | Slice 2 implementation | Slice 2 Step 4.7 |
| `sdk/store.py:1917` `_identity_values_by_e_ref` shadow store 是否仍需要(Identity Claim 已在 ledger,可能可移除)— **non-load-bearing follow-up**,不阻塞 Slice 2 | Slice 2 cleanup OR Slice 3a | Slice 2 完成后 |
| `schema_compile.py:258-259` `primary_key` dead code 清理(ADR-FI §4.3-bis 衔接)— **non-load-bearing follow-up** | Slice 1 OR Slice 2 | Slice 1 完成后 |
| docs sync(Slice 4)— `04_api_surface.en.md` 加 INV-7c reject 行为 + Identity Claim emission 说明 | Slice 4 docs sync | Slice 2 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-API 起草时 Header `Depends on:` 引用本 ADR(§4.3 cache lifecycle 跟 schema.extend hook 衔接);ADR-SYS-A / ADR-SYS-B 起草时不必依赖本 ADR(独立 cluster)
- **Blueprint pillar**:Slice 2 blueprint preflight(Step 4.3)必须 re-read 本 ADR 的 §4 Decision,作为 scoped-blueprint §5 Proposed Shape 的输入
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q1/Q2/Q3/Q16 行 status 仍是 "待 ADR 决策"— 实际 ADR-IC 已 lock;**不**触发 audit doc post-stage sync(跟 ADR-FI 相同处理 — Q1/Q2/Q3/Q16 lock 不变 Q list structure)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 2 blueprint 不可单方面 override Q1/Q2/Q3/Q16 决策;若需要 override,走"本 ADR superseded by 新 ADR-IC-v2"路径
- §4.1 双路径 reject(Layer 2 value-oriented + Layer 3 asrt_id-based):carry-forward 到任何 future Identity-as-Claim 修订 — 不可单路径化(削弱 INV-7c defense);**也**不可让 Layer 2 fields API 接受 asrt_id(跨 layer)
- §4.2 application 层 emission + emission input contract(必须携带完整 identity bundle):carry-forward — 不可下沉到 protocol 层或上移到 SDK shell 层;**也**不可让 Layer 2 fields API 隐式作为 emission path(Step 2+ shadow store 演化方向跟该 contract 兼容,反之不成立)
- §4.3 策略 C + hybrid lifecycle + 两个独立 frozenset:carry-forward;**若 ADR-API Q14 改 schema.extend 允许 Identity↔Field swap**,本 §4.3 cache lifecycle 的 "无需 invalidation,只需 union" 假设破裂 → 必须 supersede 本 ADR
- §4.4 `:exists` co-emission Step 1 保留 + existence-claim transitional guard:carry-forward — Step 2+ 移除时机由 Step 2+ ADR 锁;本 ADR 不承诺移除也不承诺永久保留;guard 命名是 **non-INV-7c**(per §4.4.2),Step 2+ 移除 `:exists` 时 guard 同步退役不会动 INV-7c 范围

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.4 4 Qs 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥1 per Q)+ cross-Q rejected combinations(≥2)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / ADR-FI 兼容性 6 类 evidence
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR + ADR-FI adopted commits
- [x] §1.4 含 shipped baseline pointer + 已 shipped / 未 shipped 划分清晰
- [x] §4.2 含 emission input contract + Layer 2 fields API NOT-emission-path 锁定 + shipped shadow store legacy 定位
- [x] §4.3 含 两个独立 frozenset(`_identity_pred_ids` / `_exists_pred_ids`)+ ADR-API Q14 explicit contract(schema.extend 不允许 Identity↔Field swap)
- [x] §4.4 含 transitional contract clarity(Step 1 保留 ≠ Step 2+ 承诺保留 OR 移除)+ existence-claim transitional guard 命名(**非** INV-7c)

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 2 blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 2 implementation:`fg.fields.set(User.id_field, ref, value)` raise `SDKStoreError(INV-7c)` 含 migration hint(per §4.1)
- [ ] Slice 2 implementation:`fg.fields.add(User.id_field, ref, value)` raise `SDKStoreError(INV-7c)`(per §4.1)
- [ ] Slice 2 implementation:`fg.fields.retract(User.id_field, ref[, value])` raise `SDKStoreError(INV-7c)`(per §4.1,value-oriented signature)
- [ ] Slice 2 implementation:`fg.fields.delete(User.id_field, ref)` raise `SDKStoreError(INV-7c)`(per §4.1)
- [ ] Slice 2 implementation:`fg.assertions.retract(identity_claim_asrt_id)` raise `SDKStoreError(INV-7c)`(per §4.1)
- [ ] Slice 2 implementation:`fg.assertions.retract(exists_claim_asrt_id)` raise `SDKStoreError(existence-claim transitional guard)`(per §4.1 / §4.4,**非** INV-7c)
- [ ] Slice 2 implementation:Layer 2 fields API signature 不含 asrt_id 参数形态(per §4.1 reject table 末段)
- [ ] Slice 2 implementation:`fg.fields.set(non_identity_field, e_ref_string_never_seen_by_shadow_store, value)` 在 first-write materialization path **必须 raise**(fail-fast per §4.2.1 emission input contract — shadow store 未见过该 e_ref 即无法合法恢复完整 identity bundle,no lazy fallback 路径)
- [ ] Slice 2 implementation:`fg.fields.set(non_identity_field, e_ref_string_seen_by_shadow_store, value)` 可走 shipped lazy compatibility path(从 `_identity_values_by_e_ref` 恢复 bundle → materialize)— 但**仅作为 legacy / internal 兼容**,**非** Layer 2 public contract;Slice 2 implementation 必须在代码注释 + Slice 4 docs sync 中显式标 legacy 定位(per §4.2.3)
- [ ] Slice 2 implementation:`fg.entities.create(User, id="u1")` atomic emit Identity Claim(s) + `:exists` Claim(per §4.2 + §4.4)
- [ ] Slice 2 implementation:`application/state` 含 `_identity_pred_ids: frozenset[str]` + `_exists_pred_ids: frozenset[str]` 两个 fields(per §4.3.1)
- [ ] Slice 2 implementation:`Store.__init__` 同时 build 两个 caches from `schema_ir`(per §4.3.3 init trigger)
- [ ] Slice 2 implementation:`fg.schema.extend(NewEntityCls)` triggers 两个 cache 的 union update(per §4.3.3 schema-evolution hook)
- [ ] Slice 2 implementation:contract test 覆盖 — `fg.entities.create` 后 ledger Active Claims 含 N+1 Claims(N Identity + 1 `:exists`)
- [ ] Slice 2 implementation:contract test 覆盖 — `fg.entities.delete(ref)` 后 ledger Active Claims 不含该 e_ref 的任何 Identity / `:exists` / Field Claim(atomic full revoke)
- [ ] Slice 2 implementation:contract test 覆盖 — Identity vs `:exists` reject 路径产 **不同** error message + 不同 exception classification(可由 caller 区分)
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 加 INV-7c reject 行为表 + existence-claim transitional guard 说明 + Identity Claim emission 说明 + Layer 2 fields API value-oriented signature notes;`identity-mechanism-redesign §5.2` 跟 ADR-IC 对齐

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-IC drafted | 4 Qs(Q1 双路径 reject / Q2 application 层 emission formalize / Q3 策略 C + hybrid lifecycle / Q16 Step 1 保留 co-emission)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-FI adopted @ `b288ea9e` + identity design-point §5.2 INV-7a/b/c + shipped baseline `entity_write.py:_materialization_ops`。Branch: `v0.2.0-q-ic-identity-as-claim-decision-2026-05-29`。Commit: `95e57e8e` |
| 2026-05-29 | proposed | ADR-IC amended(P1/P2 fixes,still proposed)| User reviewer post-draft review(同日)返回 4 findings:**(P1-1)** §4.1 唯一合法路径 vs §4.2 lazy materialization 冲突 — 改为 §4.2.1 emission input contract(必须携带完整 identity bundle)+ §4.2.2 公共入口分类(carries-bundle vs encoded-only)+ §4.2.3 shipped lazy materialization 通过 `_identity_values_by_e_ref` shadow store 实施定位为 **legacy / internal 兼容路径**(非 contract);Layer 2 fields API **永远不**作为 Identity Claim emission path。**(P1-2)** §4.4 `:exists` 被说成受 INV-7c 覆盖但 §4.3 cache 仅 `is_identity_field` — 引入 **两个独立 frozenset**(`_identity_pred_ids` + `_exists_pred_ids`)+ union property `_protected_anchor_pred_ids`;`:exists` retract reject 命名为 **existence-claim transitional guard**(**非** INV-7c);per §4.4.2 论证 `:exists` 概念上不属于 INV-7c(per design-point §5.2.3 强制点 1-4 仅列 Identity Claim)。**(P2-1)** `fg.fields.retract(asrt_id)` API 形态不稳(跨 Layer 2/3 界限)— §4.1 reject table 改为 **value-oriented Layer 2** signatures(`fg.fields.retract(Field, e_ref[, value])`)+ asrt_id 导航留 Layer 3 `fg.assertions.retract`;新增 Q1 alternative entry 显式 reject "fg.fields.retract(asrt_id)" 路径。**(P2-2)** §4.3 line 159 "ADR-API Q14 已锁" 错误 framing — 改为 §4.3.6 "本 ADR 要求 ADR-API Q14 锁定..."(跟 §7.4 / cross-pillar contract 一致)。同步 cascade:§4.5 cross-Q summary(Q1/Q2/Q3/Q16 4 行全 update)/ §5.1 新增 3 entries(Q1 asrt_id reject / Q2 Layer 2 implicit emission reject / Q3 单 frozenset reject)/ §6.4 design-point citation 强化(`:282-286` 强制点 1-4 仅 Identity)/ §7.4 no-retroactive boundary 扩(双路径 + emission input contract + 两个 frozenset + transitional guard naming)/ §8 Acceptance Criteria 重写(8 项 proposed-stage ✓ + 18 项 post-adoption ☐,含双 error message classification check 和 shadow store legacy fallback test)。Commit: `4e16f164` |
| 2026-05-29 | **adopted** | User reviewer 第 2 轮 review 通过 → adopt | 第 2 轮 review 结论:P1-1/P1-2/P2-1/P2-2 全部 resolved。一个小 P2 修正已采纳:**§8 shadow-store fallback 验收拆分** — 原 "fg.fields.set(non_identity_field, e_ref_string_never_seen_by_shadow_store, value)... raise OR shipped lazy fallback OK" 写得太松(OR 留 wiggle room 与 §4.2.1 emission input contract 不一致),按 reviewer 建议拆为两条 explicit 验收:(a)`e_ref_never_seen_by_shadow_store` 在 first-write materialization path **必须 raise**(fail-fast — shadow store 未见过即无法合法恢复 bundle,no lazy fallback)+ (b)`e_ref_seen_by_shadow_store` 可走 shipped lazy compatibility path 但**仅作为 legacy/internal 兼容**(非 Layer 2 public contract;代码注释 + Slice 4 docs 必须显式标 legacy 定位)。本 ADR 现 binding constraint;Slice 2 Identity-as-Claim blueprint 可起草;ADR-API 起草时 Header `Depends on:` 须引用本 ADR adopt commit + ADR-API Q14 **必须**锁 schema.extend 拒绝 Identity↔Field swap(本 ADR §4.3.6 explicit contract requirement)。blueprints / 后续 ADR 不可单方面 override §4.1-§4.4 + 双 frozenset + transitional guard + emission input contract,override 需走"superseded by ADR-IC-v2"路径。Commit: TBD post-stage |
