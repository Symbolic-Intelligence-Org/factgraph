# Q-SYS-A Decision: `__system__.*` user-facing namespace reservation

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Q5a — `__system__.*` user-facing pred_id namespace reservation。**仅锁 user-facing reservation 拒绝点**;**不**锁 `__system__.revokes` payload shape / internal emission exception / read-path default filter(全留 ADR-SYS-B per meta-ADR §4.2 grouping)。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5a row(`audit:518`)+ §5.3 A19 row + §6 INV-10 row(`audit:284`)+ §5.4 shipped baseline confirmation(zero `__system__` hits in source)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md`(ADR-API)adopted `66434490` — §4.1 三层 namespace + §4.5 schema 三分(register/extend/apply)定义本 ADR enforcement 路径的入口
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`(ADR-IC)adopted `2d0866ed` — §4.3.1 `protected_anchor_pred_ids = identity ∪ exists` cache 跟本 ADR 的 `__system__.*` namespace **概念正交**(本 ADR §4.4 cross-ADR compat 显式 confirm)
  - ledger-schema-specification design-point §4.7 INV-10(`:290-300`)+ §3.1 命名空间边界 + §4.12 INV-15 / §4.8-4.11 INV-11/12/13(后三者**不**在本 ADR scope)
  - User reviewer 2026-05-29 ADR-SYS-A directional 4 项 review focus:仅锁 reservation 不锁 revokes payload / 拒绝点覆盖 `fg.fields.*` + 未来 `fg.assertions.write` + schema register/extend/apply / internal emission exception 留 SYS-B / 不冲突 ADR-API 三层 + ADR-IC protected_anchor cache
- Outputs / Downstream:
  - **ADR-SYS-B**(Q5b/Q15 — `__system__.revokes` emission + ledger migration)— 起草前置;ADR-SYS-B Header `Depends on:` 须引用本 ADR adopt commit
  - Slice 3b implementation:本 ADR §4.2 reject 路径跟 ADR-SYS-B 的 internal emission exception(per Q5b)同 slice 落地
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-INV9(Q4)/ ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-sys-a-system-namespace-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping Q5a 单独 ADR-SYS-A;§4.4 Step 1 zero-Q-PR1 dependency)
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`(ADR-FI Form I descriptor 跟本 ADR namespace 正交,§4.4 cross-ADR compat confirm)
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`(ADR-IC `protected_anchor_pred_ids` cache 跟本 ADR `__system__.*` namespace 概念正交,§4.4 显式 confirm)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted @ `66434490`(ADR-API §4.1 三层入口 + §4.5 schema 三分 是本 ADR reject 路径 enumeration 的入口语义依据)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q5a — System namespace cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q5a | `__system__.*` user-facing pred_id reservation check | `audit:518` | System namespace |

**Q5b 在本 ADR 之外**(audit:519):Internal `__system__.revokes` emission exception path → ADR-SYS-B。

### 1.2 Meta-ADR locked constraints relevant to ADR-SYS-A

- **§4.2 grouping**:Q5a 单独 ADR-SYS-A;Q5b + Q15(ledger migration)合 ADR-SYS-B(per meta-ADR §4.2 splitting rationale — Q5a 只锁 user-facing 边界,跟 emission / migration 解耦)
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / PyReason adapter rewrite — confirmed
- **§4.4 4-layer enforcement**:本 ADR §4.2 reject 路径在 SDK shell + application 层(strict)— 跟 ADR-FI §4.4 / ADR-IC §4.1 模式一致

### 1.3 User reviewer 2026-05-29 directional 4 项 review focus

ADR-SYS-A draft 启动前 user reviewer 给出 4 项 directional guidance:

| 项 | User guidance | 影响本 ADR |
|---|---|---|
| 1 | 只锁 user-facing `pred_id` reservation,不锁 revokes payload | §4.1 Scope 明确 user-facing reservation;§3 Non-scope 显式列出 revokes payload 留 ADR-SYS-B |
| 2 | 拒绝点覆盖 `fg.fields.*`、未来 `fg.assertions.write`、schema/register/extend/apply 中能声明 pred_id 的路径 | §4.2 reject 路径 enumeration 显式覆盖 4 个 layer |
| 3 | Internal/system emission exception 留给 ADR-SYS-B,不在 SYS-A 偷偷定义 | §3 Non-scope 显式 reject "internal emission 在 SYS-A" + §5.1 alt 显式 reject |
| 4 | 与 ADR-API 三层入口、ADR-IC protected anchor cache 不冲突 | §4.4 cross-ADR compat 显式 confirm 两项独立性 |

### 1.4 Shipped baseline(audit §5.4 / §6)

**Greenfield state**:
- **zero hits for `__system__` in shipped source**(per audit §6 INV-10 row `:284` — `sdk/store.py` / `sdk/facade.py` / `authoring/` / `core/` 全部 grep 无命中)
- `set_field`(`evidence/write_protocol.py:231-249`)`_validate_write_inputs` 仅类型检查,无 namespace check
- shipped `revokes` 走独立表(`ledger.py:106-110`)— **不**通过 `__system__.revokes` Claim 路径(per audit INV-11 row)

**5+1 state classification**(per audit §6):
- INV-10 `__system__.*` namespace reservation 是 **(f) target-gap / pending migration** — shipped 当前不存在该概念前提;Step 1 实施时建立 load-bearing boundary

**已 shipped 但本 ADR enforcement 路径必须 wire in 的入口**:
- `authoring/schema_compile.py:79-83` `entity_type` 字符串校验(当前仅 non-empty;将加 `__system__` prefix reject per §4.2 Layer A)
- `authoring/schema_compile.py:142` `f"{entity_type}:exists"` 拼接路径(将加 prefix reject defense in depth per §4.2 Layer B)
- ADR-API §4.5 `register/extend/apply` 三分 hook(将集成 §4.2 Layer A reject)

## 2. Scope

本 ADR **锁**以下 sub-decisions(单 Q):

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q5a-1** | `__system__.` prefix 是 ledger reserved namespace;**user-facing** API 入口任何路径 不允许声明 / 创建 / 写入 pred_id 以 `__system__.` 开头 |
| **§4.2 Q5a-2** | Reject 路径 enumeration — 覆盖 4 layer:Layer A(`fg.schema.register/extend/apply`)+ Layer B(`schema_compile.py` defense in depth)+ Layer C(未来 `fg.assertions.write` 若 Step 2+ 引入)+ Layer D(`fg.fields.*` 自动安全 derive)|

## 3. Non-scope

本 ADR **不**锁(per user reviewer §1.3 第 1+3 项 + meta-ADR §4.2 grouping):

| 不锁 | 留给谁 |
|---|---|
| `__system__.revokes` Claim payload shape(pred_id / e_ref / value / value_tag / claim_meta encoding)| **ADR-SYS-B**(Q5b/Q15.2)|
| Internal / system emission exception path(internal writer API / `retract_by_asrt` lowering / protocol-layer 绕过 mechanism)| **ADR-SYS-B**(Q5b)|
| INV-11 revoke payload shape | **ADR-SYS-B** + ledger migration |
| INV-12 revoke target 约束(part 2 — revoke target 不可是 system claim)| **ADR-SYS-B**(跟 emission 同步实施)|
| INV-13 active projection 单一公式 + INV-15 read path default filter(`pred_id NOT LIKE '__system__.%'`)| **ADR-SYS-B**(跟 emission 时序耦合 — read filter 仅 after emission 存在才必要)|
| 7 数据精简 ledger migration 切片 | **ADR-SYS-B**(Q15)|
| 其他可能未来 reserved prefix(`__internal__` / `__admin__` / etc.)| Step 2+ |
| `<EntityType>:exists` 是否仍属合法 user-facing pred_id(per ADR-IC §4.4 Step 1 保留)| **ADR-IC**(已 adopted)— 不属本 ADR 范畴 |
| Slice 3b 落地的 blueprint slicing | Slice 3b blueprint |

## 4. Decision

### 4.1 Q5a-1 — `__system__.` 命名空间预留:**ledger reserved**

**锁定**:`__system__.` prefix(注意:**双下划线** + `system` + **双下划线** + 点)在 ledger 中是 **reserved system namespace**。user-facing API 入口任何路径**不允许**:
- 注册 / 扩展 entity_type 以 `__system__` 开头(如 `class MySchema(Entity): entity_type = "__system__"`)
- 经 schema 编译产生的 pred_id 以 `__system__.` 开头(如 `<EntityType>:<field_name>` 等价 `__system__:<field>`,被 §4.2 Layer B defense in depth 捕获)
- 未来若引入 `fg.assertions.write(pred_id=...)` 接受 user-supplied raw pred_id 路径,reject 以 `__system__.` 开头(per §4.2 Layer C forward-looking)

**Pattern 精确性**(per design-point ledger-spec §4.7 INV-10):
- 拒绝 pattern:`pred_id.startswith("__system__.")`(精确双下划线 + system + 双下划线 + 点)
- **不**拒绝近似变种(如 `__sys__` / `__system_` 单下划线 / `_system_` 单下划线)— 用户若刻意命名近似形式自行承担歧义;本 ADR 不做 fuzzy match(per §5.1 alt rejected)
- entity_type 启用 `__system__` 自身(无点跟在 `__system__` 后)也被拒绝 — schema_compile 会产生 `__system__:exists` 等形态,§4.2 Layer A 入口侧 reject 即可

### 4.2 Q5a-2 — Reject 路径 enumeration:**4 layer enforcement**

**锁定**:4 个 layer 各自的 reject 责任(per meta-ADR §4.4 4-layer enforcement 模式):

#### 4.2.1 Layer A — `fg.schema.register/extend/apply(EntityClass)` 入口侧 reject(strict)

**位置**:ADR-API §4.5.1 锁的 `register/extend/apply` 三分 method 入口。

**实施**:每个 method 在 dispatch 前 check `EntityClass.entity_type` 是否以 `__system__` 开头;若是,raise `SDKStoreError`:

```python
def _check_user_facing_entity_type(entity_class: type[Entity]) -> None:
    entity_type = getattr(entity_class, "entity_type", None) or entity_class.__name__
    if entity_type.startswith("__system__"):
        raise SDKStoreError(
            f"entity_type {entity_type!r} uses reserved system namespace.\n"
            f"  `__system__.*` is reserved for ledger internal mechanisms\n"
            f"  (see ADR-SYS-A §4.1). User-facing schema registration cannot\n"
            f"  declare entity_type starting with '__system__'.\n"
            f"  Choose a different entity_type (e.g., 'MyEntity' instead of\n"
            f"  '__system__MyEntity')."
        )
```

**为什么 strict 在 SDK shell**:fail-fast — 在 schema 声明早期 catch,user 立刻收到 error;不浪费 schema_compile 路径资源。

#### 4.2.2 Layer B — `authoring/schema_compile.py` defense in depth(strict)

**位置**:`authoring/schema_compile.py:79-83` `entity_type` 字符串校验路径 + `_compile_field` / `_compile_identity_predicate` 路径(每个产 pred_id 的位置)。

**实施**:`_compile_entity` 入口加 prefix check;此外 `_owner_prefix(entity_type)` 路径产生的 pred_id 在拼接时 sanity check(若 entity_type 已通过 Layer A,本 layer 应 never raise — defense in depth):

```python
def _compile_entity(entity_raw, entity_index, ...):
    entity_type = entity_raw.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error(...)
    # 新增 — defense in depth (Layer A 通常已 catch):
    if entity_type.startswith("__system__"):
        raise _compile_error(
            f"entity_type {entity_type!r} uses reserved system namespace `__system__.*` "
            f"per ADR-SYS-A §4.1. Should have been rejected at SDK shell layer (Layer A) — "
            f"reaching schema_compile suggests internal API bypass; check caller path.",
            path=f"$.entities[{entity_index}].entity_type",
        )
    # ... rest of _compile_entity
```

**为什么 defense in depth**:caller 直接调 `compile_schema(spec_dict)` 路径(bypass SDK shell `fg.schema.register/extend/apply`)— 如 internal migration tool / test fixture — 仍然 enforce;跟 ADR-FI §4.4 4-layer enforcement 一致(SDK shell + application 双层 strict)。

#### 4.2.3 Layer C — 未来 `fg.assertions.write(pred_id=...)` 入口 reject(forward-looking 规约,本 ADR **不**锁该 API 是否引入)

**位置**:per design-point §12.2 line 974,**Step 1 不引入** `fg.assertions.write(pred_id, e_ref, value)` 这类绕开 schema 的写入路径。

**Forward-looking 规约**:若 Step 2+ 引入该 API,**必须** reject user-supplied `pred_id.startswith("__system__.")`:

```python
# Step 2+ 假设引入时:
def write(self, *, pred_id: str, e_ref: str, value: Any, ...) -> str:
    if pred_id.startswith("__system__."):
        raise SDKStoreError(
            f"pred_id {pred_id!r} uses reserved system namespace per ADR-SYS-A §4.1. "
            f"User-facing assertions.write cannot supply system pred_ids. "
            f"System claims are emitted by internal mechanisms only (see ADR-SYS-B)."
        )
```

**本 ADR 不锁是否引入该 API**;只锁 **若**引入 **必须**包含此 reject。该 forward-looking 规约 carry-forward(per §7.4)。

#### 4.2.4 Layer D — `fg.fields.*` 自动安全 derive(no independent enforcement needed)

**位置**:ADR-API §4.1 Layer 2 `fg.fields.set/add/retract/delete(Field, e_ref, value)`。

**Derive 安全**:Layer 2 fields API 输入是 `Field` descriptor(来自 schema-declared)+ encoded e_ref string + value;**不接受** raw pred_id。Field descriptor 的 `pred_id` 在 `_compile_field` 路径产生(per `authoring/schema_compile.py:227-260`)— 已经过 Layer A + Layer B reject。

**结论**:Layer 2 入口**无独立 reject 路径**;reject 责任全部 dispatch 到 Layer A + B。这跟 ADR-API §4.1 排他原则(Layer 2 不接 `asrt_id` 或 raw pred_id)一致。

#### 4.2.5 Enforcement 层级总结

| Layer | 入口 | Reject 路径 | enforcement 模式 |
|---|---|---|---|
| **A** | `fg.schema.register/extend/apply` | 检查 `EntityClass.entity_type.startswith("__system__")` raise `SDKStoreError` | SDK shell strict |
| **B** | `authoring/schema_compile.py:_compile_entity` | defense in depth — 同样 reject `entity_type.startswith("__system__")` raise `_compile_error` | application strict |
| **C** | 未来 `fg.assertions.write`(若 Step 2+ 引入)| reject user-supplied `pred_id.startswith("__system__.")` raise `SDKStoreError` | SDK shell strict(forward-looking)|
| **D** | `fg.fields.*` | **N/A** — derive 安全;Field descriptor 来自 schema(已 Layer A+B reject)| 自动安全 |

**跟 meta-ADR §4.4 4-layer enforcement 一致**:SDK shell + application 层 strict;protocol / ledger 层 delayed(per §3 Non-scope — internal emission path 走 ADR-SYS-B 决策)。

### 4.3 Cross-Q decision summary(单 Q,纯 lock)

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q5a-1 | `__system__.` prefix reserved namespace;exact pattern(双下划线 + system + 双下划线 + 点)| 文档化 + Layer A/B error messages | Slice 3a + Slice 4 docs |
| Q5a-2 | 4 layer reject — Layer A(SDK shell schema 三分入口)+ Layer B(schema_compile defense)+ Layer C(forward-looking 假设)+ Layer D(自动安全)| `sdk/store.py:_SDKSchemaManager`(ADR-API §4.5 新 manager)+ `authoring/schema_compile.py:_compile_entity` | Slice 3a |

**整体**:Slice 3a 实施增量 ≈ 30-60 行代码:
- Layer A:3 个 method(`register/extend/apply`)各 + 5 行 prefix check(可抽 `_check_user_facing_entity_type` helper)
- Layer B:`_compile_entity` + 5 行 prefix check(defense in depth)
- error message + docs(Slice 4)

### 4.4 Cross-ADR 不冲突 confirmation(per user reviewer §1.3 第 4 项)

#### 4.4.1 跟 ADR-API §4.1 三层入口 不冲突

- Layer 1 `fg.entities.create(EntityClass, **identity)`:依赖 `EntityClass` 必须已通过 `fg.schema.register/extend/apply`(per ADR-API §4.5);若 EntityClass.entity_type 以 `__system__` 开头,schema 阶段已 reject — Layer 1 不会看到 system entity
- Layer 2 `fg.fields.*`:输入 Field descriptor 来自 schema-declared,自动安全(per §4.2.4)
- Layer 3 `fg.assertions.retract(asrt_id)`:asrt_id-based,不涉及 pred_id 命名;**read** path filter 是 ADR-SYS-B INV-15 范畴,不在本 ADR
- **结论**:三层入口 + 本 ADR `__system__.*` reject **互不冲突** — 本 ADR 把 reject 责任 dispatch 到 schema 入口(Layer A)与 schema_compile(Layer B),三层运行时入口无需独立 enforce

#### 4.4.2 跟 ADR-IC §4.3.1 `protected_anchor_pred_ids` cache 不冲突

- ADR-IC §4.3.1 `_identity_pred_ids` ∪ `_exists_pred_ids` cache 来自 schema_ir 的 `is_identity_field == True` + `is_entity_exists == True` filter
- 本 ADR §4.2 Layer A + B reject 保证 `entity_type` 不以 `__system__` 开头 → schema_ir 中不会出现 `__system__.*` pred_id → ADR-IC cache **自然不含** `__system__.*` entries
- 反向也成立:`__system__.*` system claims(若 ADR-SYS-B 决策走 Claim emission path,per Q5b)由 internal emission path 产生,**不**经 `is_identity_field` / `is_entity_exists` flag → cache 自然不收
- **结论**:两个 namespace **概念正交**;cache 跟 reservation 互不依赖、互不污染

#### 4.4.3 跟 ADR-FI Identity / Field descriptor 不冲突

- ADR-FI §4.3 / §4.3-bis Identity / Field descriptor signature(`description` / `pattern`)跟 pred_id 命名空间正交 — descriptor signature 不涉及 pred_id 拼接
- 本 ADR reject 是 entity_type / pred_id 字符串 prefix check,跟 descriptor 内部字段无关
- **结论**:descriptor surface(ADR-FI)+ namespace reservation(本 ADR)正交独立

## 5. Rejected Alternatives

### 5.1 Q5a 单 Q rejected options

#### Q5a alternative — 仅在 protocol 层 `set_field` reject,不在 SDK shell + application 层

- **Why rejected**:跟 meta-ADR §4.4 4-layer enforcement 模式不一致(meta-ADR 锁 SDK shell + application strict;protocol delayed);protocol 层 reject 让 user 等到运行时才看到 error,反馈环慢;此外 protocol 层 schema-agnostic,加 namespace 字符串 check 会让 protocol 层 leak schema 知识

#### Q5a alternative — 仅在 SDK shell(Layer A)reject,不在 schema_compile(Layer B)defense in depth

- **Why rejected**:caller 直接调 `compile_schema(spec_dict)` 路径(bypass SDK shell)— 如 internal migration tool / test fixture / future programmatic schema construction — 仍然需要 enforce;defense in depth 是 marginal 5 行 cost,但防止后续 schema_compile-only call site 产生 `__system__.*` predicates 污染 ledger

#### Q5a alternative — Fuzzy match(reject `__sys__` / `__system_` / `_system_` 等近似变种)

- **Why rejected**:fuzzy match 边界永远画不清(`__sys_v2__`?`system__`?`__sys__system__`?);用户若刻意命名近似形式自行承担歧义责任;**精确 pattern**(`__system__.` exact prefix)语义清晰,Layer A error message 给出明确推荐(用 `MyEntity` 代替 `__system__MyEntity`);跟 design-point ledger-spec §4.7 INV-10 一致

#### Q5a alternative — 锁 `__system__.revokes` payload shape 在 SYS-A 同 ADR

- **Why rejected**:**违反 user reviewer §1.3 第 1+3 项 directional guidance**("只锁 user-facing pred_id reservation,不锁 revokes payload" + "Internal/system emission exception 留给 ADR-SYS-B");此外 revokes payload + emission exception 涉及 ledger migration(per Q15)+ INV-11/12/13/15 整套 — 跟 user-facing reservation 是不同 concern,cluster 一起 ship 但 ADR 分开锁(per meta-ADR §4.2 grouping)

#### Q5a alternative — 同 ADR 锁 INV-15 read path default filter(`pred_id NOT LIKE '__system__.%'`)

- **Why rejected**:read path filter 时序上 **仅 after system claim emission 存在才必要** — 当前 shipped 无 system claim(per §1.4 baseline)→ INV-15 filter vacuously 满足;emission path 由 ADR-SYS-B 锁,filter 跟 emission 时序耦合;本 ADR 锁 filter 会强行 force ADR-SYS-B 同时 ship,违反 cluster sub-ADR 解耦原则

#### Q5a alternative — 多 reserved prefix 一起锁(`__system__` + `__internal__` + `__admin__` ...)

- **Why rejected**:scope creep — 未来 reserved prefix 是 Step 2+ design 问题(可能涉及多 tenant / multi-environment / capability 分级);Step 1 only `__system__` 已覆盖 INV-10/11/12/13/14/15 整套 invariant 的 namespace 需求;额外 prefix 留 future ADR

### 5.2 Cross-Q rejected combinations(本 ADR 单 Q,无 cross-Q)

N/A — 本 ADR 仅 Q5a 单 Q;cross-Q 组合不适用。**注**:跟 Q5b / Q15(ADR-SYS-B)的 cross-ADR 组合在 ADR-SYS-B 内 reject 与否(如 "把 Q5a + Q5b + Q15 全合并成单 ADR")已在 meta-ADR §4.2 grouping decision 锁。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5a row(`audit:518`)
- audit §6 INV-10 row(`audit:284`)— `__system__.*` namespace classification (f) target-gap + shipped baseline zero hits
- audit §5.3 A19 row — System namespace cluster source(跟 Q5a/Q5b 同 cluster)
- audit §5.4 N6 row — `_write_session` atomic context(per §4.2 reject 在 transaction 外 fail-fast,不影响 atomic 保证)

### 6.2 Shipped code citations

- `src/factgraph/authoring/schema_compile.py:79-83` `entity_type` 字符串校验当前(将加 §4.2 Layer B prefix check)
- `src/factgraph/authoring/schema_compile.py:142` `f"{entity_type}:exists"` 拼接路径
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` 产 pred_id 路径
- `src/factgraph/core/evidence/write_protocol.py:231-249` `_validate_write_inputs` 当前仅类型 check(不含 namespace check — per meta-ADR §4.4 protocol 层 delayed)
- `src/factgraph/sdk/store.py:518` `_SDKSchemaManager.add(*classes)` 当前混杂 register/extend(将被 ADR-API §4.5 拆三 + §4.2 Layer A hook 集成)
- shipped zero hits for `__system__` confirmed per audit §6 row 284

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-SYS-A grouping(Q5a 单独 ADR;Q5b/Q15 → ADR-SYS-B)— justifies §3 Non-scope 拒绝 emission path
- meta-ADR §4.4 4-layer enforcement(SDK shell + application strict)— justifies §4.2 Layer A + B strict;Layer C forward-looking;Layer D 自动安全
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency — 本 ADR §6.5 显式 confirm

### 6.4 Design-point citations

- `workflow/design/design-points/active/ledger-schema-specification.zh.md` §4.7 INV-10(`:290-300`)— `__system__.*` namespace reservation source
- ledger-spec §3.1 命名空间边界表(`:149-151`)— `__system__.*` 顶级 system namespace + INV-10 reject + INV-15 default filter classification
- ledger-spec §4.7 "适用范围:`fg.write.set` / `fg.write.add` / `fg.schema.ingest` / application 层写入门面"(`:294`)— Layer A / B enforcement positions
- ledger-spec §4.7 "internal API(如 `retract_by_asrt`)走分离路径绕开 namespace check"(`:294`)— 本 ADR §3 Non-scope internal emission exception 留 ADR-SYS-B 的 design-point rationale
- ledger-spec §4.7 / §4.12 `<EntityType>:exists` 跟 `__system__.*` 边界区分(`:296-298` / `:355`)— §4.4.2 cache compat confirm 的 design-point 依据
- identity-mechanism-redesign §12.2 line 974 — "Step 1 不引入 `fg.assertions.write` 这类绕开 schema 的写入路径" — §4.2.3 Layer C 不锁是否引入的 design-point 依据

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / adapter rewrite — confirmed Step 1 zero-blocker 合规。

**澄清**:§4.2.3 Layer C 提到 "Step 2+ 引入" — 那是**前向 carve-out**(本 ADR 不锁是否引入,只锁 **若**引入 必须含 reject),**不是 dependency**。Slice 3a 实施可在 Step 2+ 假设之前完成,不会被 block。

### 6.6 ADR-API + ADR-IC + ADR-FI 兼容性 confirmation(per §4.4)

- **ADR-API**(`66434490`):§4.1 三层入口 + §4.5 schema 三分 不冲突 — 本 ADR §4.4.1 详 confirm
- **ADR-IC**(`2d0866ed`):§4.3.1 `protected_anchor_pred_ids` cache 概念正交 — 本 ADR §4.4.2 详 confirm
- **ADR-FI**(`b288ea9e`):descriptor signature 正交 namespace — 本 ADR §4.4.3 详 confirm

**关键观察**:三个前置 ADR 都跟本 ADR `__system__.*` namespace reservation **正交**(各自管不同的 concern:ADR-API 管 namespace 层级 / ADR-IC 管 Identity Claim 保护 / ADR-FI 管 descriptor signature);本 ADR 是 system namespace 边界的独立 dimension,不污染、不被污染。

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **ADR-SYS-B**(Q5b/Q15 — `__system__.revokes` emission + ledger migration)可起草 — `__system__.*` namespace 在本 ADR 已锁,ADR-SYS-B 可基于此设计 internal emission path(`retract_by_asrt` lowering / internal writer API / 等)without ambiguity
- **Slice 3a implementation** Layer A 集成:`_SDKSchemaManager.register/extend/apply`(per ADR-API §4.5)+ `_check_user_facing_entity_type` helper
- **Slice 3a implementation** Layer B 集成:`schema_compile.py:_compile_entity` defense in depth
- **ADR-INV9 / ADR-IE / ADR-DOCS** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| ADR-SYS-B draft(`__system__.revokes` emission + ledger migration Q5b/Q15)| TBD | ADR-SYS-A adopt 后 |
| Slice 3a implementation:Layer A reject 集成(`_SDKSchemaManager.register/extend/apply` per ADR-API §4.5)| Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 3a implementation:Layer B reject 集成(`schema_compile.py:_compile_entity` defense in depth)| Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 3a pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `__system__` 字符串 — confirm zero hits(per audit §6 baseline)+ 加 contract test | Slice 3a blueprint preflight(Step 4.6.5)| Slice 3a blueprint scoped 后 |
| docs sync(Slice 4)— `04_api_surface.en.md` 加 `__system__.*` reserved namespace 说明 + Layer A/B error message + Layer C forward-looking 规约 docs;`identity-mechanism-redesign §10` 跟 ADR-SYS-A 对齐 | Slice 4 docs sync | Slice 3a 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-SYS-B 起草时 Header `Depends on:` 引用本 ADR(emission path 设计基于本 ADR namespace lock)
- **Blueprint pillar**:Slice 3a blueprint preflight(Step 4.3)必须 re-read 本 ADR §4.2 — Layer A 跟 ADR-API §4.5 register/extend/apply 同 codebase area,**两个 ADR 同 Slice 3a 落地**
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q5a 行 status 仍是 "待 ADR 决策" — 实际 ADR-SYS-A 已 lock;**不**触发 audit doc post-stage sync(跟 ADR-FI / ADR-IC / ADR-API 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3a blueprint 不可单方面 override Q5a 决策;若需要 override,走"本 ADR superseded by 新 ADR-SYS-A-v2"路径
- §4.1 `__system__.` exact prefix:carry-forward — 不可改 pattern 形态(双下划线 + system + 双下划线 + 点 永久 fixed);近似变种 reject 模式不可加(per §5.1 fuzzy match 已 reject)
- §4.2 4 layer reject 路径:carry-forward — Layer A + B strict 不可降级;Layer C forward-looking 规约 carry-forward 到任何未来引入 `fg.assertions.write` 的 ADR(必须含 reject);Layer D 自动安全 derive 不可改成 independent enforcement(违反 ADR-API §4.1 排他原则)
- 跟 ADR-SYS-B 的 explicit contract:**本 ADR §3 Non-scope 列出的 emission exception / payload / INV-11/13/15 / migration 全由 ADR-SYS-B 锁**;ADR-SYS-B 不可在本 ADR `__system__.*` namespace 之外引入新 system prefix(若需要新 prefix,走本 ADR superseded 路径)

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.2 Q5a 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥4 项)+ cross-Q N/A 说明
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / ADR-API+ADR-IC+ADR-FI 兼容性 6 类 evidence
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR + ADR-FI + ADR-IC + ADR-API adopted commits
- [x] §1.4 含 shipped baseline pointer + greenfield(zero `__system__` hits)confirmation
- [x] §3 显式 enumerate 不锁的 7 项(per user reviewer §1.3 第 1+3 项 directional guidance)
- [x] §4.4 显式 confirm 跟 ADR-API 三层入口 / ADR-IC `protected_anchor_pred_ids` cache / ADR-FI descriptor 三项正交不冲突(per user reviewer §1.3 第 4 项)
- [x] §1.3 含 user reviewer 4 项 directional guidance 每项落点

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 3a blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 3a implementation:`fg.schema.register(SomeCls with entity_type="__system__X")` raise `SDKStoreError` 含 migration hint(per §4.2.1 Layer A)
- [ ] Slice 3a implementation:`fg.schema.extend(SomeCls with entity_type="__system__X")` raise `SDKStoreError`(per §4.2.1 Layer A)
- [ ] Slice 3a implementation:`fg.schema.apply(SomeCls with entity_type="__system__X")` raise `SDKStoreError`(per §4.2.1 Layer A)
- [ ] Slice 3a implementation:bypass SDK shell 直接调 `compile_schema(spec_dict_with_system_entity_type)` raise `_compile_error`(per §4.2.2 Layer B defense in depth)
- [ ] Slice 3a implementation:`entity_type="__system__"` 自身(无点跟在后)同样被 Layer A + B reject — schema_compile 会产 `__system__:exists` 形态,被 Layer A 入口侧 catch
- [ ] Slice 3a implementation:`entity_type="__sys__"` / `"__system_"` / `"_system_"` 等**近似变种** **不**被 reject(per §4.1 精确 pattern 不做 fuzzy);user 若使用承担歧义责任
- [ ] Slice 3a implementation:`fg.entities.create(EntityWithSystemName, **id)` 不会执行到 — schema 阶段已 reject(per §4.4.1 cross-ADR 不冲突)
- [ ] Slice 3a implementation:`fg.fields.set/add/retract/delete(Field, e_ref, value)` 无独立 namespace reject 路径(per §4.2.4 Layer D 自动安全)
- [ ] Slice 3a implementation:ADR-IC `_identity_pred_ids` / `_exists_pred_ids` cache 不含 `__system__.*` entries(自然分离 per §4.4.2)
- [ ] Slice 3a implementation:contract test 覆盖 Layer A + B reject 路径的 error message 含 ADR-SYS-A §4.1 reference 跟 user-facing recommendation
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 加 `__system__.*` reserved namespace 说明 + Layer C forward-looking 规约;`identity-mechanism-redesign §10 / §13` 跟 ADR-SYS-A 对齐;`ledger-schema-specification §4.7` 不需改(本 ADR 直接 cite design-point 形态)

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-SYS-A drafted | 1 Q(Q5a `__system__.*` user-facing namespace reservation;**仅锁 reservation**,不锁 emission / payload / INV-11/13/15 / migration — 全留 ADR-SYS-B per user reviewer §1.3 directional guidance)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-FI adopted @ `b288ea9e` + ADR-IC adopted @ `2d0866ed` + ADR-API adopted @ `66434490` + user reviewer 2026-05-29 ADR-SYS-A 4 项 directional review focus + ledger-spec §4.7 INV-10 design-point。Branch: `v0.2.0-q-sys-a-system-namespace-decision-2026-05-29`。Commit: TBD post-stage |
