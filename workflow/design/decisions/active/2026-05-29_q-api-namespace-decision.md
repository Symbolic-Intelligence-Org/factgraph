# Q-API Decision: API namespace 3-layer + AssertionView unification + version removal + `_meta` unification + schema.add 三分

- Status: adopted
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Slice 3a API surface refactor 的 5 个 sub-decisions(audit Q10/Q11/Q12/Q13/Q14 per meta-ADR §4.2 grouping)before Slice 3a blueprint 起草。**满足 ADR-IC §4.3.6 explicit contract requirement**(schema.extend 拒绝 Identity↔Field swap + `<EntityType>:exists` predicate protection)。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q10/Q11/Q12/Q13/Q14 rows(`audit:524-528`)+ §5.3 A11/A12/A13/A14/A17/A18 + §5.4 N2 + §6 baseline
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`(ADR-IC)adopted `2d0866ed` — §4.3.6 **要求**本 ADR Q14 锁 schema.extend 拒绝 Identity↔Field swap + `:exists` predicate declaration 不可删除或改 owner_type
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md`(ADR-FI)adopted `b288ea9e` — §4.3 / §4.3-bis Field / Identity descriptor signature 锁(影响 Q14 schema diff 算法的输入 shape)
  - Identity-mechanism-redesign design-point §12 API 表面分层 + AssertionView 统一(`:833-1431`)
  - User reviewer 2026-05-29 ADR-API directional 5 项 review focus:三层边界清楚 / AssertionView 纯 read / version() no alias / `_meta` 统一 / Q14 满足 ADR-IC §4.3.6
- Outputs / Downstream:
  - Slice 3a API surface refactor blueprint(`workflow/blueprints/active/2026-05-29_slice-3a-api-namespace.md` 起草前置)
  - 后续 ADR-IE(EntityEditor 不可变性)依赖本 ADR §4.1 `fg.entities.edit` 三层归属定位
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-INV9 / ADR-SYS-A / ADR-SYS-B / ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-api-namespace-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping 锁 Q10/Q11/Q12/Q13/Q14 同 ADR + §4.4 Step 1 zero-Q-PR1 dependency)
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`(ADR-FI §4.3 / §4.3-bis 锁的 Field/Identity descriptor signature 是 §4.5 Q14 schema diff 算法的输入 shape)
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`(ADR-IC §4.3.6 explicit contract:本 ADR §4.5 Q14 **必须**实施;ADR-IC §4.2 emission contract / §4.1 双路径 reject 是本 ADR §4.1 三层边界划分的语义依据)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q10/Q11/Q12/Q13/Q14 — 全部 Slice 3a / API namespace cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q10 | API namespace 3-layer migration strategy | `audit:524` | API namespace |
| Q11 | AssertionView 类型合并时机 | `audit:525` | API namespace |
| Q12 | `version(v)` 招纳原则 enforcement strategy | `audit:526` | API namespace |
| Q13 | `_meta` 统一 — flat kwargs 删除策略 | `audit:527` | API namespace |
| Q14 | `fg.schema.add` 3-way split + schema evolution constraint slice grouping | `audit:528` | API namespace |

### 1.2 Meta-ADR locked constraints relevant to API namespace

- **§4.2 grouping**:Q10/Q11/Q12/Q13/Q14 必须**同一 ADR**(本 ADR);拆分会 force "三层 namespace + AssertionView 合并 + meta 统一 + schema 三分" 跨 5 个 ADR 反复协调
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / Slice 5+ adapter rewrite — confirmed
- **§4.4 4-layer enforcement**:本 ADR §4.5 Q14 schema.extend 拒绝路径在 SDK shell + application 层(strict)— 跟 ADR-IC §4.3 cache lifecycle 一致

### 1.3 ADR-IC §4.3.6 explicit contract(本 ADR 必须满足)

ADR-IC adopted `2d0866ed` §4.3.6 要求本 ADR(Q14)锁定:

> 本 ADR(ADR-IC)**要求**(requires)ADR-API Q14 锁 `fg.schema.extend` 拒绝 Identity↔Field swap(per design-point §5.2.3 配套不变量)— 该 explicit contract 是 §4.3.3 "union update 即可,无需 invalidation" 行为的**前置条件**。同样的 dependency 关系适用 `_exists_pred_ids`:ADR-API Q14 必须 enforce `<EntityType>:exists` predicate 的 declaration 不可在 schema.extend 中删除或改 owner_type。

本 ADR §4.5 Q14 Decision **必须**显式满足这两个 enforcement points;否则触发 ADR-IC §7.4 no-retroactive 路径(supersede ADR-IC)。

### 1.4 ADR-FI 已锁的输入(Q14 schema diff 算法)

- ADR-FI §4.3 `Field(...)` signature = `Field(*, description, pattern)`(无 cardinality)→ Q14 schema diff 算法对 Field 字段的 "类型 diff" = type annotation diff,非 kwarg diff
- ADR-FI §4.3-bis `Identity(...)` signature = `Identity(*, description, pattern)`(无 primary_key/default/default_factory)→ Q14 schema diff 算法对 Identity 字段的 "属性 diff" 不包含旧 kwarg
- ADR-FI §4.2 `_DataMember` internal base → Q14 schema diff 不暴露 `_DataMember` 形态给 user

### 1.5 User reviewer 2026-05-29 5 项 review focus

| 项 | User guidance | 影响本 ADR |
|---|---|---|
| 1 | `fg.entities / fg.fields / fg.assertions` 三层边界是否仍然清楚 | §4.1 Q10 必须显式列出三层 navigation key 边界 + 排他规则 |
| 2 | `AssertionView` 是否保持 read view,不把 mutation 混进去 | §4.2 Q11 必须显式 reject `AssertionView.retract` / 其他 mutation method;`fg.assertions.retract` 挂在 namespace manager 不在 view |
| 3 | `version()` 删除是否只保留为 migration note,不作为 alias 回流 | §4.3 Q12 必须明确 "no alias retention",删除时不留 deprecated method |
| 4 | `_meta={...}` 是否统一替代 `source/trace_id/version` flat kwargs | §4.4 Q13 必须显式 reject 双轨支持;flat kwargs 直接 breaking 删除 |
| 5 | Q14 必须满足 ADR-IC §4.3.6:schema.extend 拒绝 Identity↔Field swap + `:exists` predicate owner/type 不可改 | §4.5 Q14 必须显式 enumerate 两项 enforcement |

### 1.6 Shipped baseline(audit §5.3 / §5.4)

**已 shipped namespace managers**(`src/factgraph/sdk/store.py`):
- `_SDKReadManager`(line 529)— `fg.read.get/find/match/ref`
- `_SDKWriteManager`(line 568)— `fg.write.set/add/retract/edit`
- `_SDKAssertionsManager`(line 427)— `fg.assertions.by_id/by_ids/active/all/field`
- `_SDKSchemaManager`(line 498)— `fg.schema.add(*classes)` 单一方法混 register/extend 语义(line 518)

**已 shipped 但本 ADR 将 deprecate/rename 的类型**:
- `FieldAssertions`(`sdk/facade.py:482`)— 当前 `snap.field(...)` / `fg.assertions.field(...)` 返回值
- `AssertionNamespace`(`sdk/facade.py`)— 当前 `snap.assertions` 返回值
- 两者跟设计目标 `AssertionView` scope-aware 统一类型不一致

**已 shipped 但本 ADR 将 breaking 删除的签名**:
- `AssertionRecordSet.where(source=, trace_id=, version=, meta=)`(`sdk/facade.py:136-139`)— flat kwargs 混杂 + `meta=` dict 不统一(Q13 target)
- `view.version(v)`(`sdk/facade.py` 一等方法)— Q12 target
- `find` 动词(任何层)— 统一为 `where`(Q10 cleanup)

## 2. Scope

本 ADR **锁**以下 5 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q10** | 三层 namespace migration — alpha 直接 breaking rename;`fg.read.*` → `fg.entities.*` + `fg.write.*` → `fg.fields.*`;`retract(asrt_id)` 挪 Layer 3;**无 deprecated alias**;三层 navigation key 排他边界 |
| **§4.2 Q11** | `AssertionView` 统一类型 — Step 1 直接合并 `FieldAssertions` + `AssertionNamespace`;**无 transitional period**;**`AssertionView` 是纯读 view**(无 mutation method;`retract` 挂 namespace manager) |
| **§4.3 Q12** | `version(v)` 一等方法 hard remove(no alias);改 `where(_meta={"version": v})`;**仅保留 migration note,不留 deprecated method** |
| **§4.4 Q13** | `_meta` 统一 — `where(source=, trace_id=, version=, meta=)` flat kwargs 直接 breaking 删除;**无双轨支持**;统一签名 `where(*field_filters, _meta={...})` |
| **§4.5 Q14** | `fg.schema.add` 三分 `register/extend/apply` + schema evolution enforcement(extend 拒绝 7 种 non-additive diff)+ **ADR-IC §4.3.6 contract 满足**(Identity↔Field swap reject + `<EntityType>:exists` predicate owner/type 保护) |

## 3. Non-scope

本 ADR **不**锁:

| 不锁 | 留给谁 |
|---|---|
| `Identity()` / `Field()` descriptor public signature | ADR-FI §4.3 / §4.3-bis(已 adopted)|
| Identity Claim emission / `:exists` co-emission / INV-7c cache lifecycle | ADR-IC(已 adopted)|
| `__system__.revokes` namespace + payload shape | ADR-SYS-A(Q5a)+ ADR-SYS-B(Q5b/Q15)|
| INV-9 strict adapter enforcement | ADR-INV9(Q4)+ Slice 5+ adapter rewrite |
| EntityEditor 不可变性 / commit 路径 | ADR-IE |
| Rule compiler / inspect 路径 | Step 2+ rule-layer follow-up |
| `during(...)` 时间区间查询 | Step 2+ time-dimension ADR |
| docs sync timing(`04_api_surface.en.md` / `assertions.md`)| ADR-DOCS(Q17)|
| Slice 3a 落地的 blueprint slicing | Slice 3a blueprint |

## 4. Decision

### 4.1 Q10 — 三层 namespace migration:**alpha 直接 breaking rename + 无 alias**

**锁定**:Step 1 直接 breaking rename — `fg.read.*` / `fg.write.*` namespace 完全删除,新增 `fg.entities.*` / `fg.fields.*`;`retract(asrt_id)` 从 `fg.write` 挪到 `fg.assertions`;`edit` 从 `fg.write` 挪到 `fg.entities`。

#### 4.1.1 三层 navigation key 排他边界

| Layer | namespace | Manager / View 类型 | navigation key | 语义 | 排他原则 |
|---|---|---|---|---|---|
| **Layer 1** | `fg.entities.*` | `EntitiesManager`(新)| `EntityClass + identity` 或 `e_ref` | 实体宏观(create/get/where/delete/edit/exists/ref/match)| **不接受** `asrt_id` 参数;**不接受** `(Field, e_ref)` value 写入(写 Identity Claim 走 `create`,写 Field 走 Layer 2)|
| **Layer 2** | `fg.fields.*` | `FieldsManager`(新)| `(Field, e_ref)` + value | per-cell 操作(set/add/retract/delete/get)| **不接受** `asrt_id` 参数(per ADR-IC §4.1 P2-1 fix);**不接受** `EntityClass + identity` 形态(用 `fg.entities.ref(...)` 先算 e_ref)|
| **Layer 3** | `fg.assertions.*` | `AssertionsManager`(per §4.2.1 — **非** `AssertionView`)| `asrt_id` 或 canonical filter(field/e_ref/value/value_tag/_meta)| 原子 assertion(by_id/by_ids/active/all/field/where/retract)| **不接受** `EntityClass` 类型参数(用 `field=EntityCls.field` 走 Field descriptor);`fg.assertions.retract(asrt_id)` 是唯一 asrt_id-based mutation entry(挂在 manager 不在 view)|

**排他原则的 enforcement**:type signature 层(Python type hints + runtime type check);跨 layer 参数形态用错(如 `fg.fields.set(asrt_id, value)`)raise `SDKStoreError`,error message 含正确 layer 提示。

#### 4.1.2 Migration mapping(完整迁移表)

| 当前 shipped | 新位置 | 备注 |
|---|---|---|
| `fg.read.get(EC, **id)` | `fg.entities.get(EC, **id)` | rename |
| `fg.read.find(EC, **filter)` | `fg.entities.where(EC, **filter, _meta=...)` | rename + 动词统一(find → where) + `_meta` 入口(per §4.4)|
| `fg.read.match(EC, template, ...)` | `fg.entities.match(EC, template, ...)` | rename |
| `fg.read.ref(EC, **id)` | `fg.entities.ref(EC, **id)` | rename |
| `fg.write.set(F, e_ref, v)` | `fg.fields.set(F, e_ref, v)` | rename |
| `fg.write.add(F, e_ref, v)` | `fg.fields.add(F, e_ref, v)` | rename |
| `fg.write.retract(asrt_id)` | `fg.assertions.retract(asrt_id)` | **挪层** — Layer 3(asrt_id 是 Layer 3 navigation key) |
| `fg.write.edit(EC, **id)` | `fg.entities.edit(EC, **id)` | **挪层** — Layer 1(EntityClass + identity 是 Layer 1 navigation key) |
| **新增** | `fg.entities.create(EC, **id, meta=...)` | per ADR-IC §4.2 emission entry point |
| **新增** | `fg.entities.delete(e_ref)` 或 `fg.entities.delete(EC, **id)` | per ADR-IC §4.1 唯一合法整批撤销 |
| **新增** | `fg.entities.exists(EC, **id)` | 比 `get(...) is None` cheap |
| **新增** | `fg.fields.retract(F, e_ref, value)` | value-oriented;非 asrt_id-based(per ADR-IC §4.1 P2-1)|
| **新增** | `fg.fields.delete(F, e_ref)` | clear all values for (F, e_ref) |
| **新增** | `fg.fields.get(F, e_ref)` | 物化当前值 |
| **新增** | `fg.assertions.where(field=, e_ref=, value=, value_tag=, _meta=)` | canonical filter API |

#### 4.1.3 为什么 alpha 直接 breaking 不留 alias

- **user §17 lock-in "no alias"**:本项目 alpha 阶段无 API 用户兼容承诺,`fg.read.*` / `fg.write.*` 是 internal previewer 用法
- **alias 维护成本不 worth**:`fg.read.find` → `fg.entities.where` 涉及参数 signature 转换(flat → `_meta`,per §4.4),双轨支持每个方法 N 个 corner case
- **跟 ADR-FI §4.3 / ADR-IC §4.1 alpha breaking 模式一致**:同 batch 内 cleanup 比 deprecation cycle 累积复杂度低
- **Slice 3a impl 包含 grep + migrate**(per §7.2 follow-up):shipped 代码 / tests / docs 的 `fg.read.*` / `fg.write.*` 用法全 migrate

#### 4.1.4 删除清单 + 边界拒绝

| 删除 | 替代 |
|---|---|
| `fg.read.*` namespace 整个 | `fg.entities.*` |
| `fg.write.*` namespace 整个 | `fg.fields.*` + `fg.assertions.retract` + `fg.entities.edit` |
| `find` 动词(任何层)| 统一为 `where` |
| `fg.fields.where` / `fg.fields.history` / `fg.fields.scan` / `fg.fields.find` | 用 `fg.assertions.where(field=F, ...)` 替代(per design-point §12.2;输入语言一致,无独特价值)|

### 4.2 Q11 — `AssertionView` 统一类型 + `AssertionsManager` 分离:**Step 1 直接合并 + 纯 read view + namespace manager 显式分离**

**锁定**:**两个独立类型**:
- `AssertionsManager` — **仅一个实例 `fg.assertions`**;Layer 3 namespace manager;承载 `retract(asrt_id)` mutation
- `AssertionView` — scope-aware 统一类型;**纯读 view 无 mutation**;Step 1 直接合并 `FieldAssertions` + `AssertionNamespace`;**无** transitional alias 期

#### 4.2.1 对象身份模型(P1 critical)

**`fg.assertions` 是 `AssertionsManager`(不是 `AssertionView`)**:

```python
class AssertionsManager:
    """Layer 3 namespace manager — entry point for assertion-level operations.

    NOT an AssertionView. Has mutation method (retract) AND read shortcuts.
    Internally delegates read operations to a ledger-scope AssertionView.
    """
    # ─── Mutation(唯一 Layer 3 mutation 入口)───
    def retract(self, asrt_id: str, *, meta: dict[str, Any] | None = None) -> str: ...

    # ─── Read shortcuts — 委托到内部 ledger-scope AssertionView ───
    @property
    def active(self) -> AssertionRecordSet:
        return self._ledger_view.active
    @property
    def all(self) -> AssertionRecordSet:
        return self._ledger_view.all
    def by_id(self, asrt_id: str) -> AssertionRecord | None:
        return self._ledger_view.by_id(asrt_id)
    def by_ids(self, ids: list[str], *, strict: bool = True) -> AssertionRecordSet:
        return self._ledger_view.by_ids(ids, strict=strict)
    def field(self, f: Field) -> "AssertionView":          # Rule 6: ledger scope 必须 Field descriptor
        return self._ledger_view.field(f)
    def where(self, *, field=_MISSING, e_ref=_MISSING,
              value=_MISSING, value_tag=_MISSING,
              _meta: dict[str, Any] | None | type[_MISSING] = _MISSING) -> AssertionRecordSet:
        return self._ledger_view.where(
            field=field, e_ref=e_ref, value=value, value_tag=value_tag, _meta=_meta,
        )
```

**`snap.assertions` / `snap.field(...)` / `fg.assertions.field(F)` 返回 `AssertionView`(纯读)**。

#### 4.2.2 `AssertionView` 类型契约(纯读)

```python
class AssertionView:
    """Scope-aware pure-read view into assertions.

    Scope axes (internal): ledger / entity / field 组合。
    窄化操作返回 AssertionView;终结操作返回 AssertionRecordSet / AssertionRecord。
    NOT a mutation entry — retract 走 fg.assertions.retract(asrt_id) (AssertionsManager)
    或 fg.fields.retract(F, e_ref, value) (Layer 2)。
    """
    # ─── 窄化操作(scope chain)— 返回新 AssertionView ───
    def field(self, f: Field) -> "AssertionView": ...        # Rule 6: ledger scope 必须 Field descriptor

    # ─── 时间维度终结 — 返回 RecordSet(per Rule 4: view.at(t) == view.active.at(t)) ───
    def at(self, t: datetime) -> AssertionRecordSet: ...
    # Step 2+: def during(self, range) -> AssertionRecordSet: ...

    # ─── Property 终结 — 返回 RecordSet ─────
    @property
    def active(self) -> AssertionRecordSet: ...
    @property
    def all(self) -> AssertionRecordSet: ...

    # ─── ID-based 终结 ─────
    def by_id(self, asrt_id: str) -> AssertionRecord | None: ...     # Rule 5: 查 .all 不是 .active
    def by_ids(self, ids: list[str], *, strict: bool = True) -> AssertionRecordSet: ...

    # ─── Canonical filter 终结 — 返回 RecordSet ─────
    def where(self, *, field=_MISSING, e_ref=_MISSING,
              value=_MISSING, value_tag=_MISSING,
              _meta: dict[str, Any] | None | type[_MISSING] = _MISSING) -> AssertionRecordSet: ...

    # ─── 显式 NOT in AssertionView ─────
    # def retract(...) — 不存在;走 fg.assertions.retract(asrt_id) (AssertionsManager) 或 fg.fields.retract(F, e_ref, value) (Layer 2)
    # def set / add / delete — 不存在;Layer 2 mutation 走 fg.fields.*
    # def version(v) — 不存在(per §4.3 Q12);改 where(_meta={"version": v})
```

**Read shortcut return types**(per design-point §12.5 Rule 4 + Rule 5):
- `view.at(t)` **不**返回 narrowed view;**返回 `AssertionRecordSet`**(等价于 `view.active.at(t)` 的 sugar — 含 revoke 边界处理后的 active set);要含 revoke 历史走 `view.all.at(t)` 显式
- `view.by_id(asrt_id)` 默认查 `.all`(per Rule 5 — 审计 / 重放需要按 id 拿 revoked record)

#### 4.2.3 为什么必须区分 `AssertionsManager` 和 `AssertionView`

- **纯读约束的 type-level 保证**:`AssertionView` 类**根本不存在** `retract` method → user 无法误调;若 `fg.assertions` 本身是 `AssertionView`,要么 view 必须有 retract(破坏纯读)要么 `fg.assertions.retract` 不存在(破坏三层 mutation 入口集中原则)— 不可调和。namespace manager 单独类型是唯一一致路径
- **`snap.assertions` / `snap.field(...)` 的归属清晰**:它们必须是 view(无 entity/field scope 内的独立 mutation 入口 — entity 内 mutation 走 `fg.fields.*`);`AssertionView` 类型 → IDE / type checker 直接 enforce
- **Read shortcuts 委托模式**:`AssertionsManager` 的 `active/all/by_id/by_ids/where/field` 全部委托到内部 `_ledger_view: AssertionView` — manager 不重复实现,view 是 source of truth
- **跟 ADR-IC §4.1 双路径 reject 模式一致**:mutation 路径只有两个 — Layer 2 value-oriented + Layer 3 asrt_id-based(后者唯一住所是 `AssertionsManager.retract`)
- **per design-point §12.5 补充约束**:`fg.assertions.retract(asrt_id)` 挂 namespace manager,`snap.assertions.retract(...)` 不存在;本 ADR §4.2.1 显式 model 这一约束

#### 4.2.4 合并范围

| 当前 shipped | 合并后 |
|---|---|
| `FieldAssertions`(`sdk/facade.py:482`)| 删除 — 合并进 `AssertionView` |
| `AssertionNamespace`(`sdk/facade.py`)| 删除 — 合并进 `AssertionView` |
| `_SDKAssertionsManager`(`sdk/store.py:427`)| rename → `AssertionsManager`;扩 `where/retract` + 内部委托到 `_ledger_view: AssertionView` |
| `snap.field(name)` 返回 `FieldAssertions` | 返回 `AssertionView`(scope = entity + field)|
| `snap.assertions` 返回 `AssertionNamespace` | 返回 `AssertionView`(scope = entity)|
| `fg.assertions.field(F)` 返回 `AssertionRecordSet` | 返回 `AssertionView`(scope = ledger + field)|
| `fg.assertions` 自身 | 返回 `AssertionsManager`(Layer 3 namespace manager — 唯一 instance;**非** AssertionView)|
| `view.history` deprecated alias | 保留为 alias of `.all`;**不**默认发 DeprecationWarning(防测试失败);env var opt-in `FACTGRAPH_WARN_DEPRECATED=1`(per design-point §12.5 补充)|

#### 4.2.5 为什么 Step 1 直接合并不留 transitional alias

- 双类型同时存在(`FieldAssertions` + `AssertionView`)— user 不知道用哪个;internal helper 需要 `isinstance` check;type union 蔓延
- alpha 阶段无 API 用户兼容承诺(同 §4.1.3 rationale)
- 合并是一次性 refactor;后续不再有 "AssertionView vs FieldAssertions" 选择题

### 4.3 Q12 — `version(v)` 招纳原则:**hard remove + no alias + migration note only**

**锁定**:`view.version(v)` / `set.version(v)` 一等方法 **完全删除**;改用 `where(_meta={"version": v})`;**不保留 deprecated method,不保留 DeprecationWarning,不保留 alias method**。

#### 4.3.1 删除内容 + 替代

| 删除 | 替代 |
|---|---|
| `AssertionView.version(v)` | `view.where(_meta={"version": v})` |
| `AssertionRecordSet.version(v)` | `set.where(_meta={"version": v})` |
| `snap.field("x").version(v)` | `snap.field("x").where(_meta={"version": v})` |

#### 4.3.2 招纳原则(per design-point §12.4 / §12.7)

> `version(v)` 是普通 meta equality(无特殊语义 — 等价于 `_meta["version"] == v` 过滤)。**普通 meta equality 不应在 view 一等接口**;升级为一等 method 会让 API 充满 `source(v)` / `trace_id(v)` / `priority(v)` 等等无止境 sugar。

**招纳原则**:view 一等方法仅给 **有特殊语义** 的操作(如 `at(t)` 含 revoke 边界处理 + 默认基于 active per Rule 4)。普通 meta equality 走 `_meta` dict 统一接口。

#### 4.3.3 为什么 no alias / 不留 deprecated method

- alias 一旦留就会被 user 用 → 永远不能真正删除;比"直接 breaking"反而 stickier
- per user §17 lock-in "no alias" 立场(同 §4.1.3 / §4.2.4 rationale)
- migration cost: `view.version(v)` → `view.where(_meta={"version": v})` 是机械替换,grep + sed 可完成(Slice 3a impl preflight 工作)

#### 4.3.4 docs migration note(per Slice 4 docs sync — ADR-DOCS scope)

仅在 docs 中保留一段 **migration note**(不是 alias):

> **Migration**:`view.version(v)` 已删除(Step 1 alpha breaking)。改用 `view.where(_meta={"version": v})` — 行为等价(`_meta["version"] == v` filter)。view 一等方法仅给有特殊语义的操作(如 `at(t)`);普通 meta equality 走 `_meta` 入口。

### 4.4 Q13 — `_meta` 统一:**flat kwargs hard remove + 无双轨支持**

**锁定**:`AssertionRecordSet.where(source=, trace_id=, version=, meta=)` flat kwargs **完全删除**;统一签名 `where(*field_filters, value=_MISSING, value_tag=_MISSING, _meta: dict | None = None)`;**无** "flat 和 _meta 双向接受" 双轨期。

#### 4.4.1 删除的 flat kwargs(shipped `sdk/facade.py:136-139`)

| 删除 flat kwarg | 替代 |
|---|---|
| `source="seed"` | `_meta={"source": "seed"}` |
| `trace_id="t-001"` | `_meta={"trace_id": "t-001"}` |
| `version="v1"` | `_meta={"version": "v1"}` |
| `meta={"x": "y"}` | `_meta={"x": "y"}`(顶层 rename;`meta` → `_meta` per pydantic-style namespace 保留)|

#### 4.4.2 `_meta` 统一签名(per design-point §12.4)

```python
# Layer 1 — entities.where (schema-aware fields + unified meta)
fg.entities.where(User,
    tenant_id="t1",                              # Identity 字段(per ADR-IC §4.2 emission 后可反查)
    user_id="U001",
    status="active",                             # Field
    _meta={"source": "seed", "trace_id": "t-001"},
)

# Layer 3 — assertions.where (canonical)
fg.assertions.where(
    field=User.email,
    value="a@b",
    value_tag="string",                          # 可选(per Rule 2 推断阶梯)
    _meta={"source": "seed"},
)

# Collection — set.where (in-set filter)
record_set.where(value="a@b", _meta={"source": "seed"})
```

#### 4.4.3 `_meta` per-assertion AND 语义(per design-point §12.4 Rule 1)

- `entities.where` 的多个 field filter 共享同一个 `_meta` 时,要求**所有命中的 assertion 都各自满足 `_meta`**(AND)
- meta-only 模式(无 field filter)— 存在**任意一条** assertion 满足 `_meta` 即命中(`entities.where(User, _meta={"source":"seed"})`)
- 复杂关联用 `match` 不用 `where`

#### 4.4.4 为什么 hard remove 不留 flat kwarg deprecated alias

- 双轨支持需要每个 flat kwarg + `_meta[key]` 一致性 verification:`where(source="x", _meta={"source": "y"})` 应该报错 / 以谁为准 / 静默?— 任何选择都引入新 corner case
- per user §17 lock-in "no alias"(同 §4.1.3 / §4.2.4 / §4.3.3 rationale)
- migration:Slice 3a impl preflight grep `\.where\(.*source=` / `trace_id=` / `version=` / `meta=` 全 rewrite

### 4.5 Q14 — `fg.schema.add` 三分 + schema evolution enforcement:**满足 ADR-IC §4.3.6 contract**

**锁定**:`fg.schema.add(*classes)` 当前混杂 register / extend 语义,**完全删除**;拆为三个语义清晰的 method:`register` / `extend` / `apply`;**schema.extend 实施 ADR-IC §4.3.6 explicit contract 的两项 enforcement**。

#### 4.5.1 三分 API

```python
fg.schema.register(EntityClass)       # 注册新 entity 类型
fg.schema.extend(EntityClass)         # 扩展已注册类型(仅 additive Field)
fg.schema.apply(EntityClass)          # 便利包装 — 自动判断 register vs extend (safe diff)
fg.schema.ingest(data)                # 保持(不变)
fg.schema.validate_provenance(obj)    # 保持(不变)
```

| 方法 | 语义 | 失败条件 |
|---|---|---|
| `register(EntityClass)` | 新 entity 类型注册(创建 schema entry + 同步 build ADR-IC §4.3.1 cache entries:`_identity_pred_ids` + `_exists_pred_ids` increment)| entity_type 已注册 → `SchemaConflictError` |
| `extend(EntityClass)` | 已注册类型 additive Field 扩展 + 同步 cache union update | entity_type 未注册 → `SchemaNotFoundError`;非 additive diff → `SchemaNonAdditiveError`(per §4.5.2 + §4.5.3)|
| `apply(EntityClass)` | 便利包装 — 自动 safe diff 决策(per §4.5.4)| 仅在 register 和 extend 都失败时报错 |

#### 4.5.2 `extend` enforcement — ADR-IC §4.3.6 contract part 1(Identity↔Field swap reject)

**锁定**(满足 ADR-IC §4.3.6 explicit requirement #1):

| diff 类型 | extend 行为 | rationale |
|---|---|---|
| 新增 Field 字段 | ✅ 允许(纯 additive)| Field 是 mutable,可后加 |
| **新增 Identity 字段** | ✗ 拒绝 → `SchemaNonAdditiveError` | 改 Identity bundle = 改 idref_v1 hash 输入 = 改 e_ref → 全部 entity 迁移(违反 ADR-IC INV-7a anchor immutability)|
| 删除字段(Identity 或 Field)| ✗ 拒绝 → `SchemaNonAdditiveError` | 非 additive;打破 INV-7c(旧 active Identity / Field Claim 跟 schema 不对齐)|
| **Identity → Field 降级** | ✗ 拒绝 → `SchemaNonAdditiveError` | 旧 Identity Claim 会变得可单独 retract(`is_identity_field` flag 翻转)→ ADR-IC `_identity_pred_ids` cache 失去保护对象 → 打破 INV-7c |
| **Field → Identity 升级** | ✗ 拒绝 → `SchemaNonAdditiveError` | 旧 Field Claim 缺乏 "原子写所有 Identity Claim" 语义 + 缺乏 `EntityAlreadyExistsError` 防重复 → 一致性无法溯及既往 |
| 字段类型 / cardinality 改 | ✗ 拒绝 → `SchemaNonAdditiveError` | 非 additive;旧 Claim value 跟新 type_domain 不一致 |
| `description` / `pattern` 等元数据改 | ⏳ Step 2+ 评估 | metadata 改不影响 ledger / cache,Step 2+ 可以允许 |

**ADR-IC §4.3.6 contract part 1 满足**:Identity↔Field swap(行 4 + 行 5)被显式拒绝 → ADR-IC `_identity_pred_ids` cache 的 "union update 即可,无需 invalidation" 假设成立。

#### 4.5.3 `extend` enforcement — ADR-IC §4.3.6 contract part 2(`<EntityType>:exists` predicate protection)

**锁定**(满足 ADR-IC §4.3.6 explicit requirement #2):`<EntityType>:exists` predicate(per shipped `authoring/schema_compile.py:140-150`,`is_entity_exists: True`)在 `fg.schema.extend` 中:

| 操作 | extend 行为 |
|---|---|
| 删除 `<EntityType>:exists` predicate declaration | ✗ 拒绝 → `SchemaNonAdditiveError` |
| 改 `<EntityType>:exists` 的 `owner_type`(从 EntityType 改成别的)| ✗ 拒绝 → `SchemaNonAdditiveError` |
| 改 `<EntityType>:exists` 的 `arity` / `arg_specs` / `cardinality` | ✗ 拒绝 → `SchemaNonAdditiveError`(non-additive structural change)|

**为什么**:`<EntityType>:exists` 是 entity_type 注册的**必备产物**(per shipped schema_compile 路径自动 declare)— user 不通过 schema diff 显式 touch 这个 predicate,但若 future schema authoring tool 试图修改,**必须**被 enforcement 拒绝以保持 ADR-IC `_exists_pred_ids` cache 的 union-only 假设。

**ADR-IC §4.3.6 contract part 2 满足**:`<EntityType>:exists` predicate declaration 不可在 schema.extend 中删除或改 owner_type → ADR-IC `_exists_pred_ids` cache 的 "Step 2+ 移除 `:exists` 时 cache 退役不动 INV-7c" 假设成立。

#### 4.5.4 `apply` safe diff 算法

```python
def apply(EntityClass):
    spec = EntityClass.__sdk_entity_spec__
    if spec.entity_type not in schema_ir:
        return register(EntityClass)        # 新类型 — register
    diff = compute_diff(schema_ir[spec.entity_type], spec)
    if diff.is_purely_additive_field_only():  # per §4.5.2 + §4.5.3 enforcement
        return extend(EntityClass)
    raise SchemaNonAdditiveError(
        f"Cannot apply {spec.entity_type}: schema diff is non-additive.\n"
        f"Diff: {diff.summary()}\n"
        f"Non-additive changes require explicit entity-type migration "
        f"(new EntityType registration + data migration tool, see Step 2+).\n"
        f"Per ADR-IC INV-7a/c, Identity bundle redesign cannot go through "
        f"in-place schema diff."
    )
```

#### 4.5.5 schema diff 算法对 ADR-FI signature 的依赖

- ADR-FI §4.3-bis `Identity()` 无 `primary_key/default` → diff 算法对 Identity 字段的 "属性 diff" 只检查 `type_domain` + `description` + `pattern`,不检查旧 kwarg
- ADR-FI §4.3 `Field()` 无 `cardinality` → diff 算法对 Field 字段的 "cardinality diff" 从 type annotation 推断对比(per ADR-FI §4.3 类型推断表)
- ADR-FI §4.2 `_DataMember` internal base → diff 算法不暴露 `_DataMember` 形态给 user

#### 4.5.6 删除清单

| 删除 | 替代 |
|---|---|
| `fg.schema.add(*classes)` 混杂语义 | 拆为 `register` / `extend` / `apply` |
| "replacement class via schema.add" 隐式语义 | `extend` 显式 additive-only;非 additive 必须报错或显式 migration |
| `extend` 允许 Identity / Field 互转 / 新增 Identity / 删字段 | 全 reject(per §4.5.2 + §4.5.3)|

### 4.6 Cross-Q decision summary

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q10 | 三层 alpha 直接 breaking rename + 排他 navigation key + no alias | `sdk/store.py` 4 namespace manager + 2 个新 manager(`_SDKEntitiesManager` / `_SDKFieldsManager`)+ shipped 路径 migrate | Slice 3a |
| Q11 | `AssertionView` 统一 + 纯 read view + 删 `FieldAssertions` / `AssertionNamespace`;**`AssertionsManager` 类型分离**(`fg.assertions` 是 manager 不是 view;承载 `retract`)| `sdk/facade.py` 类合并 + scope-aware 实现 + mutation method 显式 absent;`sdk/store.py:_SDKAssertionsManager` rename → `AssertionsManager` + 委托 `_ledger_view: AssertionView` | Slice 3a |
| Q12 | `version(v)` hard remove + migration note only | `sdk/facade.py` 删 `version(v)` method;docs Slice 4 加 migration note | Slice 3a + 4 |
| Q13 | `_meta` 统一 + flat kwargs hard remove + 无双轨 | `sdk/facade.py:136-139` signature 改 `where(_meta=...)`;Layer 1 / Layer 3 `where` 同步 | Slice 3a + 4 |
| Q14 | `schema.add` → `register/extend/apply` + 7 种 non-additive diff reject + `:exists` predicate protection(**ADR-IC §4.3.6 contract 满足**)| `sdk/store.py:_SDKSchemaManager` 重写 + `authoring/schema_compile.py` diff 算法 + ADR-IC cache hook 集成 | Slice 3a |

**整体**:Slice 3a API surface refactor 实施范围 ≈ 400-600 行代码改动:
- §4.1 Q10:2 个新 manager + 4 个 namespace 删除/挪;`SDKStore` 入口 property rewire
- §4.2 Q11:`AssertionView` 类 + `FieldAssertions` / `AssertionNamespace` 删除 + 所有 caller migrate
- §4.3 Q12 + §4.4 Q13:`AssertionRecordSet.where` signature 重写(主要影响 `facade.py:127-180` 区域)
- §4.5 Q14:`_SDKSchemaManager` 重写 + diff 算法 + ADR-IC cache hook
- shipped 路径 grep + migrate(Slice 3a Step 4.6.5)

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q10 alternative — namespace 并行(新加 entities/fields,留 read/write deprecated alias 一周期)

- **Why rejected**:per user §17 lock-in "no alias";双轨期 maintenance 成本不 worth alpha-stage 兼容性;跟 ADR-FI §4.3 alpha breaking 模式不一致

#### Q10 alternative — `fg.read.retract(asrt_id)` 留在 read namespace 不挪到 assertions

- **Why rejected**:跟三层 navigation key 排他原则冲突(asrt_id 是 Layer 3 key,不应在 Layer 1 read namespace);跟 ADR-IC §4.1 P2-1 的"asrt_id 导航属 Layer 3"决策不一致

#### Q11 alternative — Step 1 引入 `AssertionView` + 保留 `FieldAssertions` / `AssertionNamespace` 一周期 deprecated alias

- **Why rejected**:双类型并存让 caller 不知道用哪个;internal helper 需要 `isinstance` check;type union 蔓延;alpha 阶段不 worth

#### Q11 alternative — `AssertionView` 加 `.retract(...)` mutation method 便利

- **Why rejected**:per user reviewer 第 2 项 review focus("不把 mutation 混进去");三层 mutation entry point 集中原则(per ADR-IC §4.1 双路径);scope-aware view 加 mutation 引入歧义(entity-scope retract 应该 retract 整 entity?该 entity 该 field?);跟 design-point §12.5 补充约束冲突

#### Q11 alternative — `fg.assertions` 自身是 `AssertionView` 且承载 `.retract`

- **Why rejected**:**让 view 类型同时承载 mutation 和纯读**会让 Q11 的"纯读约束"在 type level 失效;`snap.assertions` 是同 type → 必须同样有 `.retract`(违反 entity scope view 拒绝 mutation 原则 per design-point §12.5);或 `snap.assertions` 是 subtype 且 override 掉 retract → type 多态地 violate LSP。**两个独立类型**(`AssertionsManager` for `fg.assertions` + `AssertionView` for `snap.assertions` / `snap.field(...)` / `fg.assertions.field(F)`)是唯一一致路径(per §4.2.3 rationale 第 1 条)。

#### Q11 alternative — `AssertionView.at(t)` 返回 narrowed `AssertionView`(支持后续 chain)

- **Why rejected**:per design-point §12.5 Rule 4 — `view.at(t) == view.active.at(t)` 是 sugar **on top of `.active` RecordSet**,语义上是终结操作(应用 revoke 边界处理后 active set at 时间点 t)。返回 narrowed view 会:(i) 让 `view.at(t).at(t')` 二次 narrow 语义模糊(intersection? override?);(ii) 跟 `.active` property 的 RecordSet 返回类型不对齐(用户可能写 `view.at(t).where(...)` 期望 RecordSet 行为);(iii) `during(...)` step 2+ 同 pattern 应同样返回 RecordSet。终结返回 RecordSet 保 Rule 4 + Rule 5(`.by_id` 查 `.all`)语义一致。

#### Q12 alternative — `version(v)` 留作 deprecated alias of `where(_meta={"version": v})`

- **Why rejected**:per user reviewer 第 3 项 review focus("不作为 alias 回流");alias 一旦留就会被 user 用 → 永远不能真正删除;招纳原则要求"普通 meta equality 不上 view 一等接口"

#### Q12 alternative — `version(v)` `DeprecationWarning` 一周期 then remove

- **Why rejected**:跟 ADR-FI Q8 / ADR-IC §4.1 alpha breaking 模式不一致;`DeprecationWarning` 路径需要 silently 接受调用同时把 user 引向新写法,跟 hard breaking 等价复杂

#### Q13 alternative — flat kwargs + `_meta` 双向接受(both `source="x"` flat 和 `_meta={"source": "x"}`)一周期

- **Why rejected**:per user reviewer 第 4 项 review focus("统一替代");双轨支持需要 collision 处理(`source="a", _meta={"source": "b"}` 应该 raise / 以谁为准 / 静默?)— 任何选择都引入新 corner case;实施成本不 worth alpha-stage 兼容性

#### Q13 alternative — 仅删 `meta=` dict kwarg,留 `source/trace_id/version` flat

- **Why rejected**:留 3 个 flat kwarg 等于鼓励 user 继续使用 flat;招纳原则失效("普通 meta equality 不应特殊化");统一性诉求未达成

#### Q14 alternative — `schema.add` 三分 + extend 仍允许 Identity↔Field swap

- **Why rejected**:**违反 ADR-IC §4.3.6 explicit contract** → 触发 ADR-IC §7.4 no-retroactive 路径(supersede ADR-IC);也违反 INV-7c 配套 — 旧 Identity Claim 变可单独 retract 打破 anchor immutability

#### Q14 alternative — extend 允许 `<EntityType>:exists` predicate 修改

- **Why rejected**:**违反 ADR-IC §4.3.6 explicit contract part 2** → 同上 supersede 路径;`:exists` predicate 是 entity_type 注册必备产物,user 不应通过 schema diff 显式 touch

#### Q14 alternative — `apply` 不存在,只有 `register` / `extend`(强制 user 显式选)

- **Why rejected**:user 不一定知道当前 EntityType 是否已注册(尤其 test fixture / migration script);`apply` safe diff 是 ergonomic shortcut;不存在 `apply` 会逼 user 写 try/except 包装,跟"safe diff 是 framework 责任"原则冲突

### 5.2 Cross-Q rejected combinations

#### Option `API-deprecation-cycle`:Q10/Q11/Q12/Q13 全留 deprecated alias 一周期 then breaking

- **Why rejected**:5 个 sub-decisions 同时上 deprecation cycle = 双轨 API 维护 5 套 corner case + DeprecationWarning 路径在 alpha 阶段无 release cycle commitment;跟 user §17 lock-in 立场冲突;跟 ADR-FI / ADR-IC 已确立的 alpha breaking 模式不一致

#### Option `API-shipper-friendly`:Q11 `AssertionView` 加 `.retract` + Q12 `.version` 留 alias

- **Why rejected**:综合 §5.1 Q11 + Q12 alternative 个别 rejected 理由;让 view 类型既 mutation 又 alias,破坏三层 separation 同时引入 deprecated method 永久 sticker

#### Option `API-Q14-strictness-soft`:Q14 extend 不实施 ADR-IC §4.3.6 contract,推到 Slice 2+

- **Why rejected**:ADR-IC adopted `2d0866ed` §4.3.6 已锁本 ADR 的 explicit contract 要求;不实施 = 违反 cross-ADR contract = 触发 ADR-IC §7.4 supersede 路径;也违反 design-point §5.2.3 配套不变量 + INV-7c 配套要求;此外 Q14 schema.extend hook 路径跟 ADR-IC §4.3.3 cache lifecycle 集成,推后会 force Slice 2 implementer 选 fallback 策略,后续切策略 C 是 destabilizing refactor

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q10/Q11/Q12/Q13/Q14 rows(`audit:524-528`)
- audit §5.3 A11 row(三层 namespace 边界 — design-point §12.2)— Q10 source
- audit §5.3 A12 row(AssertionView 统一类型)— Q11 source
- audit §5.3 A13 row(`version(v)` 招纳原则)+ §5.3 D5 docs — Q12 source
- audit §5.3 A14 row(`_meta` 统一)+ §5.3 D6 docs — Q13 source
- audit §5.3 A17 row(`fg.schema.add` 三分)+ §5.3 A18 row(schema evolution Identity↔Field reject)— Q14 source
- audit §5.4 N2 row(Identity 已 declared in schema_ir)— §4.5.2 / §4.5.3 cache update 输入路径已 baseline

### 6.2 Shipped code citations

- `src/factgraph/sdk/store.py:427-528` 4 个 namespace manager 当前形态(`_SDKReadManager` / `_SDKWriteManager` / `_SDKAssertionsManager` / `_SDKSchemaManager`)
- `src/factgraph/sdk/store.py:427` `_SDKAssertionsManager` rename target → `AssertionsManager`(per §4.2.4;扩 `where/retract`)
- `src/factgraph/sdk/store.py:518` `_SDKSchemaManager.add(*classes)` 当前混杂 register / extend(Q14 拆三 target)
- `src/factgraph/sdk/facade.py:127-180` `AssertionRecordSet.where(...)` 当前 flat kwargs signature(Q13 target)
- `src/factgraph/sdk/facade.py:482-...` `FieldAssertions` class 当前形态(Q11 删除 target — 合并进 `AssertionView`)
- `src/factgraph/sdk/facade.py:1928-1932` `set_field` docstring 中的 "auto-materialize on first write" 说明(per ADR-IC §4.2.3 legacy 定位)
- `src/factgraph/authoring/schema_compile.py:140-150` `<EntityType>:exists` predicate declaration 路径(§4.5.3 protection 输入)
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` `is_identity_field: True` 路径(§4.5.2 swap reject 输入)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-API grouping(Q10/Q11/Q12/Q13/Q14 同 ADR)— justifies 本 ADR 不拆 5 个 sub-ADR
- meta-ADR §4.4 4-layer enforcement(SDK shell + application strict)— justifies §4.5 Q14 schema.extend reject 在 SDK + application 层
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency — 本 ADR §6.5 显式 confirm

### 6.4 Design-point citations

- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §12 API 表面分层 + AssertionView 统一(`:833-1431`)— 总体 source
- identity §12.2 三层分层(`:890-974`)— §4.1 Q10 排他原则 source
- identity §12.3 AssertionView 统一类型(`:976-1152`)— §4.2 Q11 source
- identity §12.4 `_meta` 统一输入(`:1153-1214`)+ §12.5 6 条硬定义(`:1215-1287`)— §4.3 Q12 + §4.4 Q13 source
- identity §12.5 补充约束 `retract` 不在 `AssertionView` 本体(`:1276-1281`)— §4.2 Q11 pure-read view source
- identity §12.6 类型迁移映射(`:1289-1314`)— §4.1.2 migration mapping source
- identity §12.7 删除清单(`:1316-1335`)— §4.1.4 / §4.2.3 / §4.3.1 / §4.4.1 删除清单 source
- identity §12.9 Schema namespace operations(`:1367-1428`)— §4.5 Q14 source

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / adapter rewrite — confirmed Step 1 zero-blocker 合规。

**澄清**:§4.5.2 提到 "Step 2+ 评估" `description` / `pattern` 元数据改 — 那是**前向 carve-out**(本 ADR 不锁的范围交给未来),**不是 dependency**。Slice 3a 实施可在 Step 2+ ADR 起草前完成,不会被 block。

### 6.6 ADR-FI / ADR-IC 兼容性 + contract satisfaction

#### 6.6.1 ADR-FI 兼容(b288ea9e)
- ADR-FI §4.3 Field signature(无 cardinality)→ 本 ADR §4.5.5 schema diff 算法对 cardinality 走 type annotation 推断,跟 ADR-FI 一致
- ADR-FI §4.3-bis Identity signature(无 primary_key/default)→ 本 ADR §4.5.2 / §4.5.5 schema diff 算法不检查旧 kwarg,跟 ADR-FI 一致
- ADR-FI §4.2 `_DataMember` internal base → 本 ADR §4.5 schema diff 不暴露 `_DataMember` 形态

#### 6.6.2 ADR-IC §4.3.6 contract satisfaction(2d0866ed)— 本 ADR 的核心责任
- **Part 1**(Identity↔Field swap reject):**已满足** in §4.5.2 行 4(Identity → Field 降级 ✗ 拒绝)+ 行 5(Field → Identity 升级 ✗ 拒绝);新增 Identity(行 2)+ 删字段(行 3)同步 reject 保 INV-7c 配套
- **Part 2**(`<EntityType>:exists` predicate protection):**已满足** in §4.5.3(删除 / 改 owner_type / 改 arity 全 reject)
- **依赖关系兑现**:ADR-IC §4.3.6 "本 ADR 要求 ADR-API Q14 锁..." → 本 ADR §4.5.2 + §4.5.3 实施 → ADR-IC §4.3.3 "union update 即可,无需 invalidation" 假设成立 → ADR-IC `_identity_pred_ids` + `_exists_pred_ids` cache lifecycle 正确

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 3a API surface refactor blueprint**(`workflow/blueprints/active/2026-05-29_slice-3a-api-namespace.md`)可起草 — Q10/Q11/Q12/Q13/Q14 全部 locked
- **ADR-IE**(EntityEditor 不可变性)可起草 — 本 ADR §4.1 `fg.entities.edit` 三层归属已定(Layer 1 入口);ADR-IE 锁 EntityEditor 内部 lifecycle
- **ADR-DOCS**(Q17 docs sync timing)可起草 — 本 ADR §4.3.4 / §4.4.1 等已识别 docs migration note 项
- **Slice 2 implementation**(per ADR-IC):本 ADR §4.5 schema.extend hook 路径明确,ADR-IC §4.3.3 cache lifecycle 集成路径清晰
- **ADR-SYS-A / ADR-SYS-B** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 3a blueprint draft(`workflow/blueprints/active/2026-05-29_slice-3a-api-namespace.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-API adopt 后 |
| Slice 3a pre-impl grep:扫所有 `fg.read.*` / `fg.write.*` / `find` 动词 / `version(v)` / `source=` / `trace_id=` / `meta=` 用法 — 全部 migrate | Slice 3a blueprint preflight(Step 4.6.5)| Slice 3a blueprint scoped 后 |
| Slice 3a pre-impl grep:扫所有 `FieldAssertions` / `AssertionNamespace` import / isinstance — 全 migrate 到 `AssertionView` | Slice 3a blueprint preflight | Slice 3a blueprint scoped 后 |
| Slice 3a pre-impl grep:扫所有 `fg.schema.add(...)` 用法 — 全 migrate 到 `register` / `extend` / `apply` | Slice 3a blueprint preflight | Slice 3a blueprint scoped 后 |
| Slice 3a implementation:ADR-IC §4.3.3 cache hook 集成 — `register` 触发 `_identity_pred_ids` + `_exists_pred_ids` increment;`extend` 触发 union update | Slice 3a implementation | Slice 3a Step 4.7 |
| docs sync(Slice 4)— `04_api_surface.en.md` 全面更新三层 + AssertionView + `_meta` + schema 三分 + Q12 migration note;`assertions.md` 同步删 `version(v)` 章 | Slice 4 docs sync | Slice 3a 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-IE 起草时 Header `Depends on:` 引用本 ADR(§4.1 `fg.entities.edit` 归属);ADR-DOCS 起草时引用本 ADR(§4.3.4 / §4.4.1 docs migration notes)
- **Blueprint pillar**:Slice 3a blueprint preflight(Step 4.3)必须 re-read 本 ADR §4 Decision;Slice 2 blueprint implementation 时必须 wire 进 §4.5 schema.extend hook
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q10/Q11/Q12/Q13/Q14 行 status 仍是 "待 ADR 决策" — 实际 ADR-API 已 lock;**不**触发 audit doc post-stage sync(跟 ADR-FI / ADR-IC 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3a blueprint 不可单方面 override Q10/Q11/Q12/Q13/Q14 决策;若需要 override,走"本 ADR superseded by 新 ADR-API-v2"路径
- §4.1 三层 navigation key 排他原则:carry-forward 到任何 future namespace 修订 — Layer 1 不接 asrt_id / Layer 2 不接 EntityClass / Layer 3 不接 EntityClass
- §4.2 AssertionView 纯读 view + AssertionsManager 类型分离:carry-forward — `AssertionView` 不可添加 mutation method(违反三层 separation);`fg.assertions` 永远是 `AssertionsManager` 不是 `AssertionView`;`AssertionsManager.retract` 是 Layer 3 唯一 asrt_id-based mutation 入口;不可让 `fg.assertions` 同时承担两种身份(per §4.2.3 type-level 一致性 rationale)
- §4.3 `version(v)` hard remove:carry-forward — 不可重新作为 deprecated alias 加回;招纳原则永久有效(普通 meta equality 不上 view 一等接口)
- §4.4 `_meta` 统一:carry-forward — flat kwarg `source/trace_id/version/meta` 永远不可加回;`_meta` dict 是唯一 meta 输入路径
- §4.5 schema.extend enforcement:carry-forward;**ADR-IC §4.3.6 contract 是永久 cross-ADR 依赖**,本 ADR 7 种 non-additive diff reject 不可单独放松;若 future 需要支持某 diff(如 description metadata 改),走 supersede 路径

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.5 5 Qs 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥1 per Q;Q14 ≥2)+ cross-Q rejected combinations(≥2)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / ADR-FI+ADR-IC 兼容性 6 类 evidence
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR + ADR-FI + ADR-IC adopted commits
- [x] §1.6 含 shipped baseline pointer + 已 shipped / 将删除 划分清晰
- [x] §4.5.2 + §4.5.3 显式满足 ADR-IC §4.3.6 contract 两个 enforcement points(Identity↔Field swap reject + `:exists` predicate protection)
- [x] §6.6.2 显式列出 ADR-IC §4.3.6 contract satisfaction 路径(每项 part 对应到 §4.5.2 / §4.5.3 具体行)
- [x] §1.5 含 user reviewer 5 项 review focus 每项落点
- [x] §4.2.1 显式区分 `AssertionsManager`(`fg.assertions`,含 `retract` mutation)vs `AssertionView`(纯读)— 对象身份不冲突
- [x] §4.2.2 `AssertionView.at(t)` / `during` 返回 `AssertionRecordSet`(per Rule 4 终结操作)
- [x] §4.2.2 `AssertionView.where(...)` 含完整 canonical filter signature(`field` / `e_ref` / `value` / `value_tag` / `_meta`)

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 3a blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 3a implementation:`fg.read.get(...)` raise `AttributeError`(`_SDKReadManager` 已删)(per §4.1)
- [ ] Slice 3a implementation:`fg.entities.get(User, id="u1")` work(per §4.1.2 migration)
- [ ] Slice 3a implementation:`fg.entities.where(User, status="active", _meta={"source": "seed"})` work + per-assertion AND 语义 verify(per §4.4.3)
- [ ] Slice 3a implementation:`fg.fields.set(asrt_id, value)` raise `SDKStoreError` 含 layer hint(per §4.1.1 排他)
- [ ] Slice 3a implementation:`fg.assertions.retract(asrt_id)` work(挪自 `fg.write.retract`)(per §4.1.2)
- [ ] Slice 3a implementation:`AssertionView` 类型存在;`FieldAssertions` / `AssertionNamespace` 已删(import 报 ImportError)(per §4.2.4)
- [ ] Slice 3a implementation:`AssertionsManager` 类型存在(rename 自 `_SDKAssertionsManager`)+ `fg.assertions` instance 是 `AssertionsManager` 类型(`isinstance(fg.assertions, AssertionsManager) is True`;`isinstance(fg.assertions, AssertionView) is False`)(per §4.2.1)
- [ ] Slice 3a implementation:`snap.assertions` / `snap.field("name")` / `fg.assertions.field(F)` 返回 `AssertionView` 类型(`isinstance(snap.assertions, AssertionView) is True`)(per §4.2.4)
- [ ] Slice 3a implementation:`snap.assertions.retract(...)` raise `AttributeError`(`AssertionView` 无 mutation method)(per §4.2.2)
- [ ] Slice 3a implementation:`fg.assertions.retract(asrt_id)` work(`AssertionsManager.retract` 是 Layer 3 唯一 asrt_id-based mutation 入口)(per §4.2.1)
- [ ] Slice 3a implementation:`AssertionView` 仅暴露 `field/at/active/all/by_id/by_ids/where`(无 `retract` / `set` / `add` / `delete` / `version`)(per §4.2.2 contract)
- [ ] Slice 3a implementation:`view.at(t)` 返回 `AssertionRecordSet` 类型(`isinstance(view.at(t), AssertionRecordSet)`)— 终结操作 per Rule 4(per §4.2.2)
- [ ] Slice 3a implementation:`AssertionsManager.where(field=F, e_ref=R, value=v, value_tag=t, _meta={...})` + `AssertionView.where(field=F, e_ref=R, value=v, value_tag=t, _meta={...})` signature 一致(per §4.2.1 委托模式)
- [ ] Slice 3a implementation:`view.version("v1")` raise `AttributeError`(method 已删)(per §4.3.1)
- [ ] Slice 3a implementation:`view.where(_meta={"version": "v1"})` work(per §4.3.1 替代)
- [ ] Slice 3a implementation:`record_set.where(source="x")` raise `TypeError`(flat kwarg 已删)(per §4.4.1)
- [ ] Slice 3a implementation:`record_set.where(_meta={"source": "x"})` work(per §4.4.2)
- [ ] Slice 3a implementation:`fg.schema.add(User)` raise `AttributeError`(method 已删)(per §4.5)
- [ ] Slice 3a implementation:`fg.schema.register(User)` work + 同步 build ADR-IC `_identity_pred_ids` / `_exists_pred_ids` cache entries(per §4.5.1 + ADR-IC §4.3.3)
- [ ] Slice 3a implementation:`fg.schema.extend(NewSchemaWithIdentityFieldSwap)` raise `SchemaNonAdditiveError`(per §4.5.2 行 4 + 行 5)— **ADR-IC §4.3.6 contract part 1**
- [ ] Slice 3a implementation:`fg.schema.extend(NewSchemaWithoutExistsPredicate)` raise `SchemaNonAdditiveError`(per §4.5.3)— **ADR-IC §4.3.6 contract part 2**
- [ ] Slice 3a implementation:`fg.schema.extend(NewSchemaWithAdditiveField)` work + 同步 ADR-IC cache union update(per §4.5.1 + ADR-IC §4.3.3)
- [ ] Slice 3a implementation:`fg.schema.apply(...)` safe diff 决策 work(per §4.5.4)
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 全面更新三层 + AssertionView + `_meta` + schema 三分;`assertions.md` 同步删 `version(v)` 章节 + 加 migration note;`identity-mechanism-redesign §12` 跟 ADR-API 对齐

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-API drafted | 5 Qs(Q10 三层 alpha breaking rename / Q11 AssertionView 统一 + 纯 read / Q12 version() hard remove / Q13 `_meta` 统一 / Q14 schema 三分 + ADR-IC §4.3.6 contract 满足)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-FI adopted @ `b288ea9e` + ADR-IC adopted @ `2d0866ed` + user reviewer 2026-05-29 ADR-API 5 项 directional review focus。Branch: `v0.2.0-q-api-namespace-decision-2026-05-29`。Commit: `a4bd94a5` |
| 2026-05-29 | proposed | ADR-API amended(P1/P2 fixes,still proposed)| User reviewer post-draft review(同日)返回 3 findings:**(P1-1)** `fg.assertions` 对象身份 vs `AssertionView` 纯读冲突 — 若 `fg.assertions` 本身是 `AssertionView`,则 view 必须有 retract(破坏纯读)或 fg.assertions 无 retract(破坏三层 mutation 集中)。重构 §4.2 为 5 子节:§4.2.1 `AssertionsManager` 类型(`fg.assertions` 唯一 instance;承载 `retract` + 委托 read shortcuts 到内部 `_ledger_view: AssertionView`)+ §4.2.2 `AssertionView` 类型(纯读)+ §4.2.3 rationale 5 条 type-level 一致性 + §4.2.4 合并范围(加 `_SDKAssertionsManager` rename → `AssertionsManager`)+ §4.2.5 Step 1 直接合并 rationale。**(P1-2)** `AssertionView.at(t)` 返回类型错(原 `→ AssertionView`)— per Rule 4 `view.at(t) == view.active.at(t)` 是终结操作 → 改为 `→ AssertionRecordSet`;`during` 同改。**(P2)** `AssertionView.where(...)` signature 缺 `field/e_ref`(原仅 `value/value_tag/_meta`)— 跟 §4.1.2 / §4.4.2 canonical filter 不一致 → 补全 5 参数 signature(`field/e_ref/value/value_tag/_meta`)。同步 cascade:§4.1.1 表加 "Manager / View 类型" 列(`EntitiesManager` / `FieldsManager` / `AssertionsManager`)+ Layer 3 行明确 `AssertionsManager` 非 `AssertionView`/ §4.6 cross-Q summary Q11 row update / §5.1 加 2 项 Q11 alternative reject(fg.assertions 是 view + at(t) 返回 view)/ §6.2 shipped citation 加 `_SDKAssertionsManager` rename target / §7.4 no-retroactive boundary §4.2 row 扩 type 分离 carry-forward / §8 Acceptance Criteria 加 3 项 proposed-stage check + 5 项 post-adoption verification(含 isinstance 类型 check + signature 一致性 check)。Commit: `2ae8e1ac` |
| 2026-05-29 | **adopted** | User reviewer 第 2 轮 review 通过 → adopt | 第 2 轮 review 结论:三处 P1/P2 全部 resolved 且 Q14 对 ADR-IC §4.3.6 contract 未被本次修正破坏。`AssertionsManager` vs `AssertionView` 类型分离让 Q11 纯读约束跟 `retract(asrt_id)` 不再冲突;`view.at(t)` / future `during(...)` 终结返回 `AssertionRecordSet` 跟 Rule 4 一致;canonical filter signature(`field/e_ref/value/value_tag/_meta`)跟 §4.1 / §4.4 对齐。验收项 9 项 proposed ✓ + 25 项 post-adoption ☐(含 isinstance 类型 check + signature 一致性 + view.at(t) 返回 RecordSet 类型 + ADR-IC §4.3.6 contract 两条 verify)。本 ADR 现 binding constraint;Slice 3a API surface refactor blueprint 可起草;ADR-IE / ADR-DOCS 起草时 Header `Depends on:` 须引用本 ADR adopt commit;Slice 2 implementation(per ADR-IC)的 schema.extend hook 路径明确,ADR-IC §4.3.3 cache lifecycle 集成 unblocked。blueprints / 后续 ADR 不可单方面 override §4.1-§4.5(含 AssertionsManager / AssertionView 类型分离 + Q14 7 种 non-additive diff reject),override 需走"superseded by ADR-API-v2"路径。Commit: TBD post-stage |
