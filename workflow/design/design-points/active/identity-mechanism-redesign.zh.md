# Identity 机制重设计

- Status: working / Step 1 locked-in（Form I schema + API surface + AssertionView 统一锁定;Q3-Q6 + Q-PR1 延后到 Step 2+）
- Authority: candidate design / non-authoritative reference; not current implementation truth
- First draft: 2026-05-28
- Last updated: 2026-05-28
- Scope: FactGraph Identity 机制重设计 — entity_ref 形态(idref_v1 typed content-derived hash 锁定)、Identity-as-Claim 镜像、Schema 声明(Form I)、SDK API 表面分层(entities / fields / assertions)、AssertionView 类型统一、与 GNF "Things-not-Strings" / "Indivisibility" 原则的对齐
- Parent: 取代 `identity-and-data-model-redesign.zh.md` 的 identity 半边（已或即将归档）;与 `ledger-schema-specification.zh.md` / `append-only-ledger-evaluation.zh.md` 配套
- Design intent: 在新 ledger schema(claim-first immutable payload, INV-9 unary)上重设计 Identity 机制;Step 1 锁定 4 条硬定义(idref_v1 / immutable anchor / mutable Field / mirrored Claim) + Form I + API 三层 + AssertionView 统一;Step 2+ 推进 InternalIdentity、Field 唯一性、alternative lookup keys、Field 反向查询性能优化、bitemporal 历史查询

## 目录

```text
§1   目的与范围
§2   当前 Identity 机制现状（source-grep baseline）
§3   动机:三条不满 + GNF 启蒙
§4   设计承诺与心智模型
§5   Identity-specific 不变量
§6   设计空间总览（Q1-Q6）
§7   Q1:entity_ref 分配策略
§8   Q2:Schema 层 identity 字段声明                     ★ Step 1 Form I 锁定
§9   Q3 + Q4:唯一性约束 + 违反语义                     ⏳ Step 2+ 延后
§10  Q5 + Q6:Lookup 索引 + 历史查询                     ⏳ Step 2+ 延后
§11  Adapter 边界（Q-PR1）                              ⏳ Step 2+ 延后
§12  API 表面分层 + AssertionView 统一                  ★ Step 1 锁定
§13  Step 1 实现范围 + 延后清单
§14  与姊妹 doc 的关系
§15  决策日志
§16  关联文档与代码锚点
§17  当前批次完成状态
```

> **Alpha 阶段说明**:FactGraph 当前处于 alpha 版本状态。**无生产数据 / 已发布 entity_ref token 的兼容性负担**。所有 entity_ref 形态变更、Identity migration 都按"代码 + schema 一次性重构"处理。下面所有 Q 都在此前提下评估,不需要为已发布 idref_v1 token 设计兼容层。

---

## §1 目的与范围

### §1.1 这份 doc 是什么

- FactGraph Identity 机制重设计的**单一权威设计点**
- 锁定 entity_ref typed content-derived(`idref_v1`)、Identity-as-Claim 镜像、Identity 不可变 anchor、Field 反向查询、唯一性约束(Step 2+)的**方向与承诺**
- 列出 Q1-Q6 待裁定决策的候选方案与权衡

### §1.2 这份 doc 不是什么

- ❌ 不是 ledger 数据格式 spec（schema、INV-1 至 INV-15 等结构性议题在 `ledger-schema-specification.zh.md`）
- ❌ 不是 append-only ledger 范式评估（10 维度 best practice 在 `append-only-ledger-evaluation.zh.md`）
- ❌ 不是当前实现真相（current behavior in `src/factgraph/*/docs/`;本 doc 是**目标**形态）
- ❌ 不规定具体 migration 工具实现

### §1.3 与姊妹 doc 的关系

| Doc | 角色 |
|---|---|
| **本 doc** | Identity 机制重设计 + identity-specific 不变量 + Q1-Q6 设计空间 |
| **`ledger-schema-specification.zh.md`** | Ledger 数据格式终态 + structural 不变量（INV-1/2/3/4/5/9-15） |
| **`append-only-ledger-evaluation.zh.md`** | Append-only 范式 10 维度评估 + future gap |

本 doc 依赖 ledger spec 的 schema 终态（INV-9 unary fact + INV-10 system namespace + INV-13 active projection 等),在此底座上设计 Identity。

---

## §2 当前 Identity 机制现状（source-grep baseline）

### §2.1 entity_ref 编码

[`src/factgraph/core/protocol/idref_v1.py:67-73`](../../../../src/factgraph/core/protocol/idref_v1.py):

```python
def encode_idref_v1(entity_type: str, identity_fields: list[tuple[str, str, Any]]) -> str:
    canonical = canonical_bytes_idref_v1(entity_type, identity_fields)
    digest = hashlib.sha256(canonical).digest()
    digest_b32 = b32_nopad_lower(digest)
    return f"idref_v1:{entity_type}:{digest_b32}"
```

形态:`idref_v1:{entity_type}:{base32_lowercase_no_pad(sha256(canonical_identity_tuple))}`

### §2.2 Identity 字段的处理路径

- [`schema.py:50-79`](../../../../src/factgraph/sdk/schema.py) — `Identity` 描述符:`primary_key=False/True`、`default_factory="uuid4"` 等;**没有 `eref_pattern` 验证**
- [`schema.py:131-203`](../../../../src/factgraph/sdk/schema.py) — `EntityMeta` 仅要求至少一个 `Identity(primary_key=True)`
- 所有 `Identity` 字段(primary_key=True 或 False)**等同参与 hash**(`encode_idref_v1` 接受 list)

### §2.3 Lookup 路径

[`facade.py:549-582 sdk_get`](../../../../src/factgraph/sdk/facade.py) 路径:
- 把 `identity_kwargs` 包进 `AppEntitySelector`
- 调 `execute_read_request` 拿响应
- 返回 snapshot 时 `_dto_to_sdk_snapshot(..., known_identity_values=identity_kwargs)` — **identity 值从调用者参数 echo 回去,不从存储读出**
- 存在性判断走 `<EntityType>:__exists__` assertion,不走 identity-fact

**关键发现**:identity 值**不作为 fact 存储**,整个 lookup 是"用 identity_kwargs 重算 idref → 看 `<T>:__exists__` 是否存在"。

### §2.4 现状特征

- ✅ Hash-based identity:idref_v1 是 identity 元组的 sha256 digest
- ❌ ID 单向:无法从 idref 反推 identity 字段值
- ❌ Identity 值"一次性"用品:仅参与 hash 构造,之后不再作为 ledger fact 存在
- ❌ `Identity(primary_key=True)` vs `Identity`(非 primary)区分薄弱:在 ID 计算层面无差别

---

## §3 动机:三条不满 + GNF 启蒙

### §3.1 三条不满（2026-05-27 用户讨论提出,2026-05-28 重新审视）

| # | 不满 | 代码证实 | 2026-05-28 重新审视 |
|---|---|---|---|
| **#1** | ID 单向 — `HASH(I1, I2, ...) → ID` 不可反推 | sha256 + base32 不可逆 | **可接受** — typed content-derived hash 是 GNF Things-not-Strings 的合理实现;Identity → e_ref 是 deterministic 算出(不需要反推),Identity Claim 作为 queryable/auditable 镜像让 identity 不再"用完即扔";`get/ref` 走直接 hash,`where(User, identity_field=...)` 走 Claim 索引 |
| **#2** | Identity 字段"用完即扔" — 仅参与 ID 构建,之后不作为 fact 存在 ledger 中 | `sdk_get` 路径 echo identity 值,不从存储读 | **真痛点** — Step 1 核心增量 Identity → Claim 解决:identity 值同时存为 ledger Claim |
| **#3** | `Identity(primary_key=True)` / `Identity`(非 primary) / `Field` 三层划分薄弱 | encode_idref_v1 同等参与 hash,二者无差别 | **真痛点** — Step 1 Form I 解决:Identity 与 Field 二分,删除 `primary_key` 区分 |

**Step 1 真正解决的根因**:Identity 字段从"hash 输入,用完即扔"升级为"hash 输入 + first-class queryable Claim"。**不**改变 e_ref 的 typed content-derived 本质(详见 §4.1 + §7)。

### §3.2 GNF 启蒙

FactGraph 的 Identity 与 Entity 设计部分启蒙自 Relational.ai 的 Graph Normal Form(GNF)。GNF 的两条核心原则:

- **Things not Strings**:domain entities are first-class **typed values**, identified by **constructed values**(如 `Person['ssn-12345']` 是 Thing,不是 raw string `"ssn-12345"`)。重点是 typed constructor 应用 — Thing 的身份由其 content 构造而来,但表现为 typed value 而非 raw string。参见 [RelationalAI GNF docs](https://www.relational.ai/resources/graph-normal-form)。
- **Indivisibility of Facts**:一个关系模板最多一个 value column;多 value 应拆为多个一元关系。

#### 当前 FactGraph 的状态(Step 1 前后)

| 原则 | Step 1 前 | Step 1 后 |
|---|---|---|
| **Things not Strings**(typed constructor) | ✅ **已实现** — `idref_v1:<EntityType>:<digest>` 是 typed Thing,由 typed constructor 应用在 Identity content 上 | ✅ 保持 |
| **Indivisibility of Facts**(INV-9 unary) | ✅ ledger spec 已锁定 INV-9 一元关系 | ✅ 保持 |
| **Identity-as-facts**(queryable / auditable identity) | ❌ identity 值仅进 hash,不作为可查 Claim | ✅ Step 1 增量补全 |

#### Bombay → Mumbai 类用例的正确处理

GNF 期待 "Bombay → Mumbai 仍是同一 Thing" — 实现方式是:

**Schema 设计决定** — 把 `name` 放 `Field`(可改),把 stable 标识(如 `(country_code, region_code)`)放 `Identity`:

```python
class City(Entity):
    # —— Identity (immutable anchor,参与 e_ref) ——
    country_code: str = Identity()
    region_code:  str = Identity()       # 政府发的稳定 code
    
    # —— Field (可改的属性) ——
    name:         str = Field()          # "Bombay" / "Mumbai" — 改名不改 entity
```

`City(country="IN", region="MH-MUM")` 是一个 Thing,它的 `name` Field 可以从 "Bombay" 改成 "Mumbai" — e_ref 不变,因为 Identity (`country_code`, `region_code`) 没变。

**关键洞察**:GNF 的 mutable name 是靠 schema 选择(把 name 放 Field 不放 Identity)来实现的,**不是**靠"e_ref 跟 identity 解耦"。Things-not-Strings 不要求 e_ref 跨 identity 变化保持稳定;它要求 e_ref 是 typed Thing 而非 raw string。

#### 对 alternative 模型的非否定性引用

**Opaque allocated e_ref**(ULID / UUID4;surrogate identity / event-sourced 风格)是另一个 valid model — 那里 Identity 跟 e_ref 解耦,Identity 可变。FactGraph 本轮**不**选这个模型(详见 §4.1 / §7),但**不评判它"不符合 GNF"** — 它只是另一个哲学。

> 注:根据用户 obsidian 笔记 `symb-Intelli./case-studies/palantir/7_FactPy Kernel 启示.md`,"GNF" 一词**不作为对外营销词**使用;本 doc 引用 GNF 仅作为**内部设计纪律的启蒙**。

---

## §4 设计承诺与心智模型

### §4.1 核心心智模型 — 4 条硬定义

新 Identity 机制建立在四条**互锁的硬定义**上(2026-05-28 lock-in,详见 §15 决策日志):

```text
1. e_ref = deterministic typed constructor
   e_ref = idref_v1(EntityType, complete Identity bundle)
        = "idref_v1:<EntityType>:<sha256-base32(canonical(identity_fields))>"
   是 typed Thing,content-derived,跟 GNF Things-not-Strings 一致。

2. Identity = immutable anchor
   create 时必填、强制 single、参与 e_ref hash、产生镜像 Claim、不可修改。
   "改 Identity 值"语义 = 创建新 entity(新 e_ref);用 `delete + create` 表达。

3. Field = mutable attribute
   不参与 e_ref;改值走 revoke + append 走 ledger 生命周期;e_ref 跨 Field 变更稳定。

4. Identity-as-Claim = mirrored anchor facts
   Identity 字段值除了进 e_ref hash,还存为 Claim(Step 1 核心增量)。
   Claim 中的 Identity 只用于 query / rule / audit / snapshot,
   不是第二套可变 identity truth。
```

#### 边界规则(schema 建模指导)

> 如果某个值未来可能变,**不要建模为 Identity**;建模为 Field(或 future alias / external lookup key 概念)。
>
> 典型例:
> - `email` — 可能变,建模为 Field
> - `tenant_id` / `user_id`(business-stable code)— 建模为 Identity
> - 城市 `name`("Bombay" → "Mumbai")— Field;城市 `(country_code, region_code)`— Identity

#### 对 alternative 模型的说明(对 Y 的非否定性引用)

**Opaque allocated e_ref**(ULID / UUID4;surrogate key / event-sourced 风格;见 Datomic、SQL surrogate PK、event-sourced 系统)是另一个 valid alternative model — 在那里 Identity 是 schema-level lookup facts,e_ref 跟 identity 解耦,Identity 可变。

本轮 FactGraph 选 **typed content-derived hash**(X 方向)而非 opaque allocated,因为 Identity 在本设计里**定义**为 immutable anchor — typed hash 机械性地强制这个定义。Y 方向不是错误模型,只是不符合本轮设计目标。

### §4.2 4 条定义 → INV / Q 映射

| 硬定义 | 对应不变量 / Q |
|---|---|
| 定义 1(e_ref typed constructor)| **Q1 锁定 idref_v1**(本轮锁定,见 §7);ULID alternative 评估后不采纳 |
| 定义 2(Identity immutable anchor)| INV-7a(anchor)+ INV-7c(consistency, 详见 §5.2);Q2 Form I 锁定(见 §8) |
| 定义 3(Field mutable)| INV-7 之外;由 INV-9 unary + INV-12/13 retract 机制支撑 |
| 定义 4(Identity-as-Claim 镜像)| INV-7b(claim-mirrored)+ INV-9 unary(见 ledger spec) |

### §4.3 与 GNF 原则的对齐审查

| GNF 原则 | 在新设计下的实现 |
|---|---|
| **Things not Strings** | e_ref 是 typed Thing(`idref_v1:<EntityType>:<digest>`),由 typed constructor 应用在 Identity content 上;**满足 GNF 原文要求**(typed value,not raw string) |
| **Indivisibility of Facts** | 每个 Identity 字段是独立 unary Claim(INV-9 / Step 1 Identity → Claim);再没有"identity 元组打包"的聚合 |

**Bombay → Mumbai 类用例的处理**:由 schema 设计决定 — 把 `name` 放 Field(可改),把 `(country_code, region_code)` 之类稳定标识放 Identity。改 name 是 Field set,e_ref 不变。这跟 GNF 一致:Thing 是 typed constructor 应用在 *stable identifier content* 上;mutable display label 是 Thing 的属性。

**Step 1 在 GNF 维度的增量**:

| 原则 | 当前(Step 1 前) | Step 1 后 |
|---|---|---|
| Things not Strings(typed constructor) | ✅ 已实现(idref_v1 即 typed Thing) | ✅ 保持 |
| Indivisibility of Facts(INV-9 unary) | ✅ ledger spec 已锁定 | ✅ 保持 |
| Identity-as-facts(queryable / auditable identity) | ❌ identity 用完即扔(仅 hash 输入) | ✅ Step 1 增量补全(definition 4 镜像 Claim) |

---

## §5 Identity-specific 不变量

下面 2 条 INV 是 identity 议题专属（INV-1 至 INV-15 在 ledger-schema-specification 中,跨 spec 共享）。

### §5.1 INV-6:Application-first runtime authority

> 所有新增 runtime capability 先以 DTO + pure function 形式落在 `factgraph.application` 层;SDK 仅作为 product surface / ergonomic shell,不携带 substrate。

**适用范围**:本 doc 提出的任何 SDK 层 API 变更（`Entity` / `Field` / `Identity` 描述符的重设计、`fg.entities.*` namespace 等）。

**形式来源**:[`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md)。

**含义**:
- Identity 重设计的运行时实体（entity_ref 分配、identity-as-facts 写入、lookup 索引维护）必须先在 `factgraph.application` 层定义
- SDK 上的 `Entity` / `Identity` 描述符只是 application DTO 的语法糖

### §5.2 INV-7:Identity = immutable Claim-mirrored anchor

> Identity 是 entity 的 immutable anchor;Identity 字段值同时存为 Claim 但不允许 in-place 修改;Active Identity Claims 必须与 e_ref 的 idref_v1 hash 输入一致。

由 3 条互锁的子不变量构成:

#### INV-7a — Identity Anchor(immutable)

> Identity 字段值参与 e_ref 生成(`idref_v1(EntityType, Identity bundle)`);改 Identity 字段值 = 创建新 entity(新 e_ref);**不允许 in-place update**。

**含义**:
- 业务上想"修改 Identity"等于"创建新 entity + 显式数据迁移"(`fg.entities.delete(old_ref)` + `fg.entities.create(new_identity)` + 旧 Field 数据手工迁移)
- 旧 entity 的 Field history **不自动继承**到新 entity
- 若业务认为这是"同一现实对象的 rename",说明该字段**不应该建模为 Identity**(参见 §4.1 边界规则)

#### INV-7b — Identity-as-Claim(mirrored)

> Identity 字段值除了进 e_ref hash,**同时存为 ledger Claim**:
> ```
> pred_id  = "<EntityType>:<identity_field>"
> e_ref    = idref_v1(EntityType, Identity bundle)
> value    = <identity value>
> value_tag = <type tag>
> ```
> 这是 Step 1 核心增量。

**适用范围**:`fg.entities.create` 内部生成 Identity Claim 的写入路径。

**Step 1 增量带来的 4 项 ergonomic 收益**:
1. Identity 可被 rule 引用(rule body 能写 `User.tenant_id(u, "t1")`)
2. Identity 可被 `fg.entities.where(User, tenant_id="t1")` 反向查询
3. Identity Claim 有 asrt_id,可 audit / explain 指向
4. Snapshot 从 ledger 读 identity,不再"用完即扔"的 echo 参数模式

#### INV-7c — Identity Claim ↔ e_ref hash 一致性

> Active Identity Claims under 任意 e_ref 必须与 idref_v1 hash 出该 e_ref 的 Identity bundle 一致;任何路径都不允许产生"e_ref X 的 active Identity Claim 反推出 ≠ X 的 bundle"的状态(dual-truth split)。

**强制点**:
- Identity Claim **只能由 `fg.entities.create` 内部生成**(原子写入所有 Identity Claim)
- Identity Claim **不允许通过 `fg.fields.set / add / retract / delete` 修改**(Layer 2 schema-aware 层硬拒绝)
- Identity Claim 的 **整批撤销**只能作为 `fg.entities.delete` 的一部分;`delete` 必须撤销该 e_ref 下**完整** active Claim set(含全部 Identity Claim + 全部 Field Claim,atomic)
- Layer 3 `fg.assertions.retract(asrt_id)` 检测到该 asrt_id 是 Identity Claim 时**拒绝单独 retract**;只能走 entities.delete 整批路径

**理由**(dual-truth 失败模式举例):
```text
情景:某低层路径意外 retract 了一条 Identity Claim
e_ref     = idref_v1:User:hash(tenant_id="t1", user_id="u1")
active Identity Claims:
  - User:tenant_id = "t1"   (其余还在)
  - (User:user_id 已被 retract)
→ Identity Claim 集合 = {tenant_id="t1"} 反推不出原 e_ref;
→ Identity Claim 与 e_ref hash 输入分裂;
→ rule 引用 / where 反查 / audit 行为全部不可预测。
```

INV-7c 关闭这个失败模式 — Identity Claim 只允许跟 e_ref 同生同灭。

#### INV-7c 实施 — Identity 判定链 + 推荐策略

`fg.assertions.retract(asrt_id)` 需要识别 asrt_id 是否指向 Identity Claim。判定链:

```text
fg.assertions.retract(asrt_id)
  → application 层(INV-6 application-first runtime authority)
  → 1. ledger SELECT pred_id FROM claims WHERE asrt_id = ?
  → 2. parse pred_id = "<EntityType>:<field_name>"
  → 3. 查 schema registry → 取 EntityType 的 Identity 字段 pred_id 列表
  → 4. if field_name in Identity pred_id 列表 → 抛 SDKStoreError(INV-7c)
  → 5. 否则继续 retract 路径(append revoke Claim)
```

**实施策略评估**:

| 策略 | 描述 | 评价 |
|---|---|---|
| **A. 每次完整链(naive)** | 每次 retract 都查 Claim + schema | 简单;每次 retract 2 次 query;schema cache 命中率高时实际开销小 |
| **B. Claim meta tag** | `fg.entities.create` 写 Identity Claim 时加 `_meta["is_identity"] = "true"`;retract 直接查 meta | ❌ **不推荐** — 把 structural truth 写进 `claim_meta`,违背 claim_meta 语义(claim_meta 应承载 audit / provenance 等业务 meta,不应承载 structural classification) |
| **C. application 层 in-memory Identity pred_id set ★ 推荐** | 启动时把所有 Identity 字段的 pred_id 算出,放 application 层 in-memory set;retract 只需 ledger lookup pred_id + O(1) set membership 检查 | ✅ **推荐** — 干净分层(ledger 层 schema-agnostic,application 层 schema-aware);O(1) 检查;schema 变更时 cache 重建即可 |

**策略 C 的不变量配套**:

> **Schema evolution 不允许 Identity / Field 互转**:既有 Identity 字段**不能降级为 Field**;既有 Field **不能升级为 Identity**(`fg.schema.extend` 拒绝该 diff)。

原因:
- 若 Identity → Field:旧 Claim 已经在 active set 中,但新 Identity pred_id set 不再包含;旧 Identity Claim 退化为"普通 Field Claim",变得可单独 retract → 历史 entity 的 INV-7c 一致性被打破
- 若 Field → Identity:旧 Claim 是普通 Field 写入路径产生的,缺乏"原子写所有 Identity Claim"语义 + "EntityAlreadyExistsError 防重复"检查 → 一致性无法溯及既往
- **应对**:identity bundle 重设计必须走 entity-type 迁移(新 EntityType + 数据迁移工具),不允许 in-place schema diff

`fg.schema.extend(EntityClass)` 的额外 enforce:
- 新增 Identity 字段 ✗ 拒绝(改 Identity bundle = 改 e_ref,等于全部 entity 迁移)
- 新增 Field 字段 ✓ 允许(纯 additive)
- 删除字段 ✗ 拒绝(非 additive;Step 2+ 评估"deprecate field" 机制)
- Identity / Field role change ✗ 拒绝(如上)

#### Slice 2 ADR-IC 锁定 + 落地状态(2026-05-30)

**ADR-IC adopted**:[`2026-05-29_q-ic-identity-as-claim-decision.md`](../../decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md) @ `2d0866ed` 锁定 4 个子决策:

| ADR-IC sub-decision | 锁定内容 | 本 §5.2 对应段 |
|---|---|---|
| **§4.1 Q1** — Layer 2 schema-aware rejection 双路径硬拒绝 | Layer 2 fields(Identity descriptor)+ Layer 3 asrt 两入口都 reject;Identity → INV-7c;`<EntityType>:exists` → existence-claim transitional guard(**非** INV-7c) | INV-7c 强制点 1-4(已实施 — 三层 enforcement)|
| **§4.2 Q2** — Identity Claim emission 在 application 层 derive | `_materialization_ops`(已 shipped 基线);emission input contract = 完整 identity bundle;Layer 2 fields API 不作为 emission path | INV-7b mirrored Claim(已实施 — 通过 `_materialization_ops`)|
| **§4.3 Q3** — INV-7c 策略 C cache lifecycle = hybrid init + schema-evolution hook;**两个独立 frozenset** `identity_pred_ids` ∪ `exists_pred_ids` = `protected_anchor_pred_ids` | hybrid init = `SchemaIndex` 构造期 build frozensets;schema-evolution hook = `fg.schema.extend / register` 触发 cache rebuild(ADR 双层锁) | `SchemaIndex.identity_pred_ids` + `exists_pred_ids` + `protected_anchor_pred_ids` property 已实施(`application/schema_runtime.py` Slice 2 Step 1 @ `73993ebd`);schema-evolution hook **carry-forward 到 ADR-API Q14**(per Slice 2 SF4 + N1 — 当前 schema 已禁 Identity / Field 互转 + Identity 新增,immediate hook 暂不需要)|
| **§4.4 Q16** — `:exists` Step 1 保留 co-emission + existence-claim transitional guard(**非** INV-7c) | Rule layer 继续依赖 `<EntityType>:exists`;Step 2+ 评估移除时 guard 同步退役 | 本 §5.2 新增"existence-claim transitional guard" 概念(独立于 INV-7c lifecycle)|

**Slice 2 三层 enforcement landed**(2026-05-30 on `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29`):

1. **Application source-of-truth** — `application/retract_guard.py:check_retract_allowed`(commit `187a2918` Step 2)用 `Ledger.get_claim` + `identity_pred_ids` / `exists_pred_ids` O(1) membership 分类 + `RetractGuardError(classification=identity|exists|unprotected)`
2. **SDK shell fail-fast** — `sdk/store.py:SDKStore.retract` wrap(commit `12475859` Step 3)走 `check_retract_allowed` + `RetractGuardError` → `SDKStoreError(code="INV_7C_IDENTITY_PROTECTED")` / `code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD"`
3. **Application 2 个写入路径** — `application/ingest_runtime.py:_apply_retract`(commit `16aeff69` Step 4)+ `application/entity_write.py:_apply_op` retract branch(commit `a4853a0a` Step 5);两个路径都 propagate `code=guard_exc.code` directly,不被 wrap 为 generic `INGEST_RETRACT_FAILED` / `ENTITY_WRITE_FAILED`
4. **Layer 2 Identity field write 拒绝** — `IdentityEditor.set/add/retract`(commit `c2d659c1` Step 6 wording 更新)+ `plan_write_command:is_identity_field` check(同 commit Step 6 wording + code 同步)

**Q-PR1 carve-out**(Slice 2 SF5)保留:`core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py:401`(internal rollback per SF11)— 全 0 diff;协议 / 核心 / pyreason 直接路径 intentionally unguarded(三层 enforcement 的 defense-in-depth 边界在 application + SDK shell)。

**Error code 统一**:Layer 2 reject(IdentityEditor + plan_write_command)+ Layer 3 reject(retract guard)三个 enforcement 点全部 surface `code="INV_7C_IDENTITY_PROTECTED"` — single caller branching source-of-truth per ADR-IC §4.1。

**Error message 文案 markers**(per ADR-IC §4.1 adopted wording,Slice 2 Step 6 落地):INV-7c / INV-7a / `fg.entities.delete` / `fg.entities.create` / `ADR-IC §4.1`;`fg.entities.delete/create` 作为 user migration guidance(Slice 3a ADR-API Q10 future API),Slice 2 implementation 不依赖 unshipped。

**Shadow store legacy**(per ADR-IC §4.2.3 + Slice 2 Step 7):`SDKStore._identity_values_by_e_ref` 标 LEGACY / INTERNAL COMPATIBILITY only(commit `d46b9fe7`)— NOT part of Layer 2 fields API contract;两分支语义:e_ref ∉ shadow store → fail-fast `UNRESOLVABLE_E_REF`;e_ref ∈ shadow store → lazy materialization through `_materialization_ops`。Step 2+ 方向(per ADR-IC §4.2.4):`fg.entities.create` eager emission + shadow store removal(Slice 3a carry-forward,Slice 2 显式 NOT remove)。

### §5.3 ~~INV-8~~(alpha 状态下消解)

> **原 INV-8**:已发布 idref_v1 token 兼容路径 — alpha 无已发布 entity_ref token 流通,**取消该不变量**。
>
> 注:idref_v1 已经在本轮锁定为 Step 1 e_ref 形态(详见 §7 + §15 决策日志),所以这条不变量原本想说的"切换 idref_v1 → erf_v1"演化路径**在本轮设计里不发生**;条目保留作为历史 exploration 标记。

---

## §6 设计空间总览（Q1-Q6）

| Q | 议题 | 范围 | Step 1 状态 |
|---|---|---|---|
| **Q1** | entity_ref 分配策略 | typed content-derived hash(`idref_v1`)/ opaque allocated(UUID4 / ULID 等) | ✅ **本轮锁定 `idref_v1`**(§7);opaque alternative 评估后不采纳 |
| **Q2** | Schema 层 identity 字段声明 | `Identity` 描述符存废 / 改用 Field + role / 三层折叠为二 | ✅ **本轮锁定 Form I**(§8) |
| **Q3** | 唯一性约束形态 | per-field / composite / 多 alternative natural keys | ⏳ Step 2+ |
| **Q4** | 唯一性违反语义 | reject / auto-retract / 暂态允许 | ⏳ Step 2+ |
| **Q5** | Lookup 索引存储 | workspace 持久化 / 启动重建 / 混合 | ⏳ Step 2+(X-style 下仅适用 Field 反向查询,Identity → e_ref deterministic) |
| **Q6** | 历史 / as-of lookup 语义 | 仅当前 active / 可选 as-of T / 完整 bitemporal | ⏳ Step 2+ |

Q-PR1（PyReason edge 与 INV-9 unary 冲突）从 ledger spec 转入,详见 §11。

下面 §7 至 §10 逐 Q 展开候选 + 权衡。

---

## §7 Q1:entity_ref 分配策略

**Step 1 锁定**:**保留 idref_v1 typed content-derived hash**(已 shipped 形态)。

```text
e_ref = idref_v1(EntityType, complete Identity bundle)
      = "idref_v1:<EntityType>:<sha256-base32(canonical(identity_fields))>"
```

这是 X-style typed Thing,满足 GNF Things-not-Strings(typed constructor 应用在 Identity content 上,详见 §3.2 + §4)。

### §7.1 锁定 idref_v1 的理由

1. **Identity = immutable anchor**(§4.1 硬定义 2): typed hash 机械性强制这个定义 — 改 Identity 必然改 e_ref,系统行为一致
2. **Lookup deterministic**: `fg.entities.get(User, **identity)` 直接 `idref_v1(EntityType, identity)` 算 e_ref,**无需反向索引维护**
3. **shipped 现状**: alpha 阶段无需切换,降低 implementation risk
4. **跟 INV-7a/b/c 一致**(§5.2): Identity Claim 与 e_ref hash 输入同生同灭

### §7.2 评估的 alternative — opaque allocated(rejected)

下面 4 个候选都属于 **opaque allocated** 系(Y 方向),本轮**不采纳** — 但保留 rationale 作为决策来源:

| 候选 | 形态 | 评估 |
|---|---|---|
| **A. UUID4** | `erf_v1:User:b3e8c0d6-3f4a-...` | Valid surrogate model;但 Identity 失去 immutable anchor 的机械强制;lookup 需要反向索引维护 |
| **B. ULID**(曾经推荐) | `erf_v1:User:01HN3FYAQF8K2G7P9M3R5V8X2C` | Valid surrogate model + k-sortable;同 A 的 lookup / immutable anchor 问题 |
| **C. Content-addressed on creation meta** | `erf_v1:User:{sha256(creation_meta + nonce)}` | 既不是真 content-derived(含 nonce)也不是真 opaque;路线混乱 |
| **D. Composite UUID + ledger sequence** | `erf_v1:User:{seq}-{uuid4_hex}` | 过度工程;ULID 已经同时提供 sort + 随机 |

**Y 方向不采纳的根本原因**:本轮选择"Identity = immutable anchor"(§4.1 硬定义 2)— opaque allocated 让 Identity 跟 e_ref 解耦,Identity 可变,跟本轮设计目标不一致。**Y 不是错误模型,只是另一个哲学**(详见 §4.1 对 alternative 的说明)。

### §7.3 lock-in 状态

| 维度 | 状态 |
|---|---|
| Step 1 锁定 | ✅ `idref_v1(EntityType, Identity bundle)` |
| Step 2+ 是否重新评估 | ✗ 不在 Step 2+ 范围 — 改方向需重写 §4 4 条硬定义 |
| 替代模型(ULID 等) | 已评估 → 不采纳 |

---

## §8 Q2:Schema 层 identity 字段声明

**Step 1 锁定**:**Form I** — Identity 与 Field 保留为独立描述符;共通参数下沉至 `_DataMember` 基类;cardinality 从类型注解推断;支持 `Literal` 枚举;`primary_key` 区分删除。

### §8.1 当前形态（baseline）

```python
class User(Entity):
    user_id: str = Identity()
    tenant_id: str = Identity()
    name: str = Field()
```

Form I 之前的三层（旧 `src/factgraph/sdk/schema.py` baseline）:
- `Identity(primary_key=True)`
- `Identity()`（非 primary）
- `Field(cardinality=...)`

§3.1 不满 #3 指出前两类区分薄弱 — 实现上所有 `Identity` 字段同等参与 idref_v1 hash,`primary_key` 标记仅用于"至少一个 primary"校验,下游消费者不明确。

### §8.2 历史候选 A/B/C 的演化轨迹

最初设计空间收敛于三个候选（rationale 保留,作为 Form I 演化来源）:

| 候选 | 形态 | 退出理由 |
|---|---|---|
| **A** 保留三层 + 赋 `Identity` 实质语义 | `Identity(primary_key=True)` / `Identity()` / `Field()` | `primary_key=False` 的语义价值仍不强;只是"参与 hash 但不是主 key"的延续 |
| **B** 折叠 Identity 入 Field + `role="identity"` | 所有字段都是 `Field(..., role="identity")` | `role="..."` 字符串混杂 Layer 3 存储与 Layer 4 identity 概念;视觉上无 `Identity` / `Field` 物理区分,易误用;用户排斥 |
| **C** 保留 Identity 但去掉 `primary_key` 区分 | `Identity(cardinality=...)` / `Field(cardinality=...)` | 方向对,但 `cardinality=` kwarg 啰嗦;未覆盖 `Literal` 枚举;无共通参数下沉机制 |

**Form I 是候选 C 的演化扩展**:
- 保留候选 C 的"`Identity` / `Field` 二分 + 删 `primary_key`"基底
- 引入 pydantic 风格的类型注解驱动 cardinality 推断（类型即语义）
- 引入 `Literal[...]` 枚举类型支持（含 Layer 4 enum 约束）
- 抽出共通基类 `_DataMember` 承载共通参数（当前仅 `description`,扩展位 `validators` / `constraints` / `alias` 等）
- 配合 Step 1 增量（Identity → Claim）,`Identity` 字段在 ledger 层成为 first-class 数据

### §8.3 Form I 最终设计

#### 完整声明示例

```python
from typing import Literal
from factgraph.sdk import Entity, Identity, Field

class User(Entity):
    # —— Identity 字段（immutable anchor;必填、参与 e_ref、产生镜像 Claim、强制 single）——
    tenant_id: str = Identity(description="租户标识")
    user_id:   str = Identity(pattern=r"^[A-Z][A-Z0-9_-]*$")        # business-stable code, immutable

    # —— Field 字段（mutable;可分步 set/add、参与推理、cardinality 从类型推断）——
    # 注意:email 放 Field 不放 Identity — email 可能变(账户合并、域名迁移等);
    # 改 email 是 Field set,e_ref 不变。详见 §4.1 边界规则。
    email:        str       = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    status:       Literal["active", "inactive", "pending"]  = Field()             # single + enum
    role:         Literal["admin", "user", "guest"]         = Field()             # single + enum
    display_name: str       = Field(description="用户显示名")                      # single + 描述
    tags:         list[str] = Field()                                              # multi
    permissions:  list[Literal["read", "write", "admin"]]  = Field()              # multi + enum

    class Meta:
        version = "1.0"
```

#### 行为契约

| 字段类型 | create 时 | 参与 idref_v1 e_ref hash | 产生镜像 Claim | 可被 Rule 引用 | cardinality | 是否可修改 |
|---|---|---|---|---|---|---|
| `Identity` | **atomic 必填** | ✅(immutable anchor) | **✅ Step 1 后** | ✅ | 强制 single | ✗(改 = `delete + create`) |
| `Field` | 不必填 | ✗ | ✅ | ✅ | 从类型推断 | ✅(`set / add / retract / delete`) |

#### 关键变更点（对比 baseline）

| 点 | baseline | Form I | 性质 |
|---|---|---|---|
| `Identity(primary_key=True/False)` | 必须打 | **完全去除** — 所有 Identity 地位平等 | 简化 |
| `Field(cardinality="single"\|"multi")` | 必填 kwarg | **从类型推断** — `T` → single / `list[T]` → multi | pydantic-style |
| Identity 是否产 Claim | ✗ 只参与 idref_v1 hash 输入 | **✅ hash 输入 + 同时镜像存为 Claim** | **Step 1 核心增量** |
| Identity 是否可改 | 不强制 + 无 audit | **immutable**(改 = 新 entity);INV-7c 强制 hash 输入与 active Claim 一致 | 语义收紧 |
| `create` 时是否强制 Identity | 不强制 | **atomic 必填**;缺一报错 | 行为变更 |
| `Literal[...]` 枚举类型支持 | 不支持 | **支持**(含 Layer 4 enum 约束 + `list[Literal[...]]` multi 形态) | 新增 |
| `description=` 参数 | 仅在 `Identity` 上 | **提升到 `_DataMember` 共通基类** — `Identity` 和 `Field` 都可声明 | 重构 |
| `pattern=` 参数 | 不支持 | **新增**(regex 字段值校验,Layer 4;仅 `str` 字段;来源 PDF Change Request) | 新增 |
| 共通基类 | 无;各自定义参数 | **抽出 `_DataMember`** — 承载共通参数 + 预留 `validators` / `constraints` / `alias` / `deprecated` / `examples` 扩展位 | 重构 |

### §8.4 类型推断规则

| 类型注解 | `type_domain` | `cardinality` | `enum_values` (Layer 4) |
|---|---|---|---|
| `str` / `int` / `bool` / `bytes` / `float` | 基础映射（`string` / `int` / `bool` / `bytes` / `float64`） | single | — |
| `UUID` / `datetime` | `uuid` / `time` | single | — |
| Entity subclass | `entity_ref` | single | — |
| `list[T]` / `tuple[T, ...]` / `set[T]` / `frozenset[T]` | 同 `T` | **multi** | — |
| `Literal[v1, v2, ...]`（所有 v 同类型） | 从 v 类型推断 | single | `[v1, v2, ...]` |
| `list[Literal[...]]` | 从 Literal 元素推断 | multi | 从 Literal 提取 |
| `Optional[T]` / `T \| None` | — | — | **拒绝** — unset = None 已表达,不引入 Optional |
| `Union[A, B]`（非 Literal） | — | — | **拒绝** — 避免 union 数据语义 |
| `Literal[1, "a"]`（混类型） | — | — | **拒绝** |
| `dict[K, V]` | — | — | **Step 1 暂不支持**;延后（可能映射为 multi pair 或独立 KV entity） |

**enum 约束的层位**:
- Layer 3（Schema）: schema spec 携带 `enum_values: [...]` 元数据
- Layer 4（Constraint）: SDK 在 `create` / `set` / `add` 时校验值在 enum 范围内
- 底层 Claim: 仍存原始 value（如字符串 `"active"`）,不存 enum 索引（参见 [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) Claim 表结构）
- Rule 引用: rule 看到的就是普通字段,enum 约束对 rule 透明

### §8.5 共通基类 `_DataMember`

#### 类层次

```python
class _DeclaredMember:
    """descriptor 协议层（已存在）— __set_name__ / __get__ / __set__."""

class _DataMember(_DeclaredMember):
    """Identity / Field 共通基类 — 都是'数据'载体."""
    def __init__(
        self,
        *,
        description: str | None = None,
        pattern: str | None = None,    # ★ Step 1 — Layer 4 字段值正则校验
    ) -> None:
        super().__init__()
        self.description = description
        self.pattern = pattern
        # 扩展位 (Step 2+ 演化):
        # self.validators  = ...    # 自定义校验 callable
        # self.constraints = ...    # ge/le/min_length/multiple_of/...（非 regex 的约束）
        # self.alias       = ...    # 序列化别名
        # self.deprecated  = ...    # 字段弃用标记
        # self.examples    = ...    # 文档示例

class Identity(_DataMember):
    """必填、参与 e_ref、产生 Claim、强制 single."""

class Field(_DataMember):
    """可分步 set/add、cardinality 从类型推断."""
```

#### `pattern=` 的语义（Step 1 in-scope）

| 维度 | 行为 |
|---|---|
| 适用类型 | 仅对 `str` 值字段有意义;非 string `type_domain` 时 `pattern=` 被拒绝（`SDKSchemaError`） |
| 校验时机 | Layer 4 — `create` / `set` / `add` 时校验;不匹配抛 `SDKValueError("value does not match pattern '...'")` |
| 校验范围 | Identity 字段:`create` 时强制校验所有 Identity 值;Field 字段:`set` / `add` 时校验 |
| 底层 Claim | 仍存原始 value（未变换、未编码),pattern 不进 Claim 行;pattern 是 schema 描述,不是 ledger 数据 |
| Rule 引用 | rule 看到的就是普通字符串字段,pattern 约束对 rule 透明 |
| `pattern` 来源 | PDF Change Request 2026-05-28 "validated identity patterns"（旧名 `eref_pattern=`,重命名为 `pattern=` — `pattern` 校验的是 *字段值* 本身,不是 `idref_v1` token;e_ref 由 canonical Identity bundle hash 得出,token 形态不需要单独校验） |

#### Step 1 共通字段范围

| 字段 | Step 1 | 备注 |
|---|---|---|
| `description: str \| None` | ✅ | 文档说明,schema spec 携带 |
| `pattern: str \| None` | ✅ | regex 字段值校验,Layer 4;仅 `str` 字段;来源:PDF Change Request 2026-05-28 |
| `validators` / `constraints` / `alias` / `deprecated` / `examples` | ✗ 延后 | `_DataMember` 上预留扩展位,Step 2+ 统一加,自动同时作用于 Identity 与 Field |

#### 2026-05-29 implementation sync

Slice 1 已落地 Form I 的描述符与校验骨架:

- `Identity()` 仅接受 `description=` / `pattern=`,旧 `primary_key=` / `default=` / `default_factory=` 均在 SDK 层报迁移错误。
- `Field()` 仅接受 `description=` / `pattern=`,`cardinality=` 删除;`T` 推断 single,`list[T]` / `tuple[T, ...]` / `set[T]` / `frozenset[T]` 推断 multi。
- `Literal[...]` 写入 `enum_values`;`list[Literal[...]]` 等 multi enum 形态同样保留 enum 约束。
- `pattern=` 进入 schema truth,并在应用层写入集中路径执行 enum / pattern 校验;`evidence/write_protocol` / ingest / adapter direct paths 仍按 caller contract 不加此层校验。
- `Optional` / general `Union` / `dict[...]` / mixed-type `Literal` / float Literal enum 均拒绝;普通 `float64` 字段仍允许。

#### `default` 为什么不放入共通基类

| 字段类型 | `default` 的潜在语义 | 与 Step 1 契约的冲突 |
|---|---|---|
| `Identity` | "create 时未给入则用 default 填充" | 与"Identity 必填 atomic"冲突;若 default 是常量则多个 entity 撞 e_ref;若 default 是工厂（如 ulid）则进入 InternalIdentity 范畴 |
| `Field` | "未设置时读取的 fallback" | 与"未设置读 None / 空"语义冲突;建议查询层处理而非 schema 层 |

→ Step 1 不引入 `default`。如未来 Identity 需要 `default_factory="ulid"` 这类语义,作为 InternalIdentity 的演化点处理（§13 延后清单）。

### §8.6 Form I 与 Step 1 / Step 2+ 范围关联

| 项 | Step 1（本次） | Step 2+（延后） |
|---|---|---|
| Identity / Field 二分 | ✅ Form I 锁定 | — |
| `_DataMember` 共通基类（含 `description` + `pattern`） | ✅ | + `validators` / `constraints` / `alias` / `deprecated` / `examples` |
| `primary_key` 区分 | ✅ 删除 | — |
| `Literal` 枚举（含 Layer 4 enum 约束） | ✅ | — |
| cardinality 从类型推断 | ✅ `T` / `list[T]` / Literal | + `dict[K, V]` 等容器类型 |
| Identity 产 Claim | ✅ 核心增量 | — |
| `Identity(internal=True)` flag | ✗ | ✅ — SDK 层 Rule 编译时拒绝引用 |
| `InternalIdentity` 具体类型 | ✗ | ✅ — Fingerprint / ULID / ContentHash |
| 多 Identity 联合 Fingerprint | ✗ | ✅ — 如 `Fingerprint(of=("tenant_id", "email"))` |
| 备用自然键 / `alternative_key` | ✗ | ✅ — 视 Claim 反向索引 UX 是否足够再定 |
| `default` / `default_factory` | ✗ | ⏳ 仅作为未来 `InternalIdentity` / 系统派生 identity 设计点重新评估;不回到普通 `Identity` / `Field` 共通参数 |

→ 完整延后清单见 §13。

---

## §9 Q3 + Q4:唯一性约束 + 违反语义

> **⏳ Step 2+ deferred — not part of Step 1 implementation scope.**
>
> Step 1 仅落地 Identity → Claim 增量,**不**引入 schema-level uniqueness 强制。本节内容保留作为 Step 2+ 设计参考;实际唯一性强制实现等 Step 2+ 启动时再裁定推荐。

### §9.1 Q3:唯一性形态

**问题**:schema 怎么声明唯一性?

候选:

| 选项 | 形态 |
|---|---|
| **per-field uniqueness** | 每个 `role="identity"` 字段都独立唯一;`(tenant_id="t1") 唯一 AND (user_id="u1") 唯一` 各自约束 |
| **composite uniqueness**（**推荐**）| identity 字段集合作为整体唯一;`(tenant_id="t1", user_id="u1")` 元组唯一 |
| **多个 alternative natural keys** | 允许声明多组独立唯一的字段集合（如 user 既有 email 唯一,又有 phone 唯一） |

#### Per-field 的问题

如果每个 identity 字段独立唯一,则 multi-tenant 场景下没办法表达"同一 user_id 在不同 tenant 下可以重复":
```
Alice 在 tenant1, user_id="u-1"
Bob   在 tenant2, user_id="u-1"   ← per-field 模型下违反"user_id 唯一"
```

#### Composite 的常见性

绝大多数业务模型的 natural key 是 composite（如 `(tenant_id, user_id)`、`(country, postcode, street)` 等）。

#### Multiple alternative

少数场景需要多个独立 natural key:user 既可以用 email 找,也可以用 phone 找,且两者各自全局唯一。但这其实是"两个 different natural keys"而不是"一个 composite"。

#### 推荐

**Composite uniqueness 为默认**;**Multiple alternative 作为可选扩展**。

候选 schema syntax(已对齐 Form I,Step 2+ 时 `AlternativeKey` 形态化):

```python
from factgraph.sdk import Entity, Identity, Field
# Step 2+: from factgraph.sdk import AlternativeKey

class User(Entity):
    # —— 主 Identity bundle(immutable anchor,参与 idref_v1 hash;§4.1 硬定义 1+2) ——
    tenant_id: str = Identity()
    user_id:   str = Identity()
    
    # —— Step 2+ Alternative natural keys(不参与 e_ref;独立唯一性约束) ——
    # email: str = AlternativeKey(name="by_email")    # email 全局唯一,但 mutable
    # phone: str = AlternativeKey(name="by_phone")    # phone 全局唯一
    
    # —— 普通 Field(mutable;可分步 set) ——
    display_name: str = Field()
    status: str = Field()

    class Meta:
        version = "1.0"
        # 主 Identity bundle = Identity 字段列表(按声明顺序);
        # 不需要单独 primary_key=... 声明
```

**Form I 下,Identity 与 Field 是物理上分离的 descriptor 类**,不允许 `Field(role="identity")` 字符串混杂(候选 B 已 rejected;详见 §8.2)。`AlternativeKey` 作为独立 descriptor 类型在 Step 2+ 引入,**不会**回到 `Field(role=...)`。

**注意**:Form I 下 Identity 本身就是 "primary natural key";不需要 `primary_key=("tenant_id", "user_id")` 显式声明。alternative natural key 通过独立 descriptor 表达,跟 Identity 物理区分,避免子类型混淆(Identity / AlternativeKey / 未来 InternalIdentity / Fingerprint 等需要的不同行为)。

**状态**:推荐 Form I `Identity` + Step 2+ `AlternativeKey` 双支持;`AlternativeKey` 具体 syntax / 唯一性 enforcement / mutability 语义待 Step 2+ 收口。

### §9.2 Q4:违反唯一性的语义

**问题**:写入 identity Claim 时检测到现有 active 的相同 identity 元组,如何处理?

候选:

| 选项 | 语义 |
|---|---|
| **(a) reject write** | 抛 `UniquenessViolationError`;由 caller 决定如何处理 |
| **(b) auto-retract previous** | 默默 revoke 占用 identity 的旧 entity,允许新写入 |
| **(c) 允许暂态违反**（eventually consistent） | 暂时存两个共享 identity 的 entity,后续合并 |

#### Reject(a)的优势

- 最不"魔法":caller 看到 violation 后明确决定下一步（合并 / retract / 重命名）
- 与 [`feedback_audit_execution_discipline`](~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_audit_execution_discipline.md) 的"design strictness must not be softened"原则一致

#### Auto-retract(b)的风险

- 静默 revoke entity 是巨大的语义副作用,容易隐藏 bug
- 与 INV-7a/c(Identity 不可变 + Claim 一致性,§5.2)冲突:Identity 的"变更"语义是 caller 显式 `delete + create`,不允许系统静默处理 — auto-retract 会让系统行为不可预测

#### 暂态违反(c)的复杂度

- INV-13（active projection 单一公式）下两个 entity 同时 active,fg.read.get 不确定返回谁
- 复杂度跳一级,不值得

#### 推荐

**(a) reject write**:写入时拒绝,抛专用错误。caller 根据业务需要处理。

**状态**:推荐 (a) reject;待最终确认。

---

## §10 Q5 + Q6:Lookup 索引 + 历史查询

> **⏳ Step 2+ deferred — not part of Step 1 implementation scope.**
>
> **X-style 重要澄清**:在本 doc 锁定的 X-style(§4.1 硬定义 1)下,**Identity → e_ref 是 deterministic hash**,**不需要专用 lookup 索引**。`fg.entities.get(User, **identity)` / `fg.entities.ref(...)` 直接走 `idref_v1(EntityType, identity)` 算出 e_ref,然后按 e_ref 查 ledger;**不**走反向索引。
>
> 反向索引仅适用于:
> - **Field 反向查询**(`fg.entities.where(User, status="active")` 等)— 走 `idx_claims_pred_value`(已在 ledger-schema-specification 索引基线里)
> - **Identity 字段值反向查询**(`fg.entities.where(User, user_id="U001")` 等)— Identity 镜像 Claim 走同一索引;但这是 schema-aware filter,**不**是 lookup 替代(`get/ref` 仍走 hash)
> - **未来 alias / external lookup key**(Step 2+ Field-level unique / alternative keys)
>
> 本节 Q5/Q6 的"**专用** lookup 索引 / bitemporal as-of 历史"等议题仅适用于 Field-level 性能优化和 future bitemporal,不影响 Step 1 Identity lookup 路径(已 deterministic)。

### §10.1 Q5:Lookup 索引存储

**问题**(Step 2+ 范围):`fg.entities.where(User, user_id="u-1", tenant_id="t1")` 反向查询的性能优化 — 走 Claim 反向索引(`idx_claims_pred_value`)是否足够,还是需要专用 entity-type 索引?

> 注:此节问题**不**适用于 `fg.entities.get(User, ...)` / `fg.entities.ref(...)`,后者在 X-style 下 deterministic hash 算出 e_ref,无 lookup 开销。

candidates:

| 选项 | 形态 |
|---|---|
| **(a) 启动时从 ledger 重建,纯内存** | dict 索引 `(entity_type, identity_tuple) → entity_ref`;启动扫 active identity Claims 重建 |
| **(b) workspace 持久化为单独索引文件** | identity 索引作为 derived state 持久化在 workspace 中;启动直接 mmap/load |
| **(c) SQLite 内建索引（推荐）** | 在 claims 表 `(pred_id, value)` 索引上直接查 — 已经在 ledger-schema-specification §3.1 索引基线里 |

#### 候选 (c) 的工作机制

```sql
-- 查 (tenant_id="t1", user_id="u-1") 对应的 entity_ref:
SELECT c1.e_ref FROM claims c1
WHERE c1.pred_id="User:tenant_id" AND c1.value="t1"
  AND NOT EXISTS (
    SELECT 1 FROM claims r
    WHERE r.pred_id="__system__.revokes" AND r.value=c1.asrt_id
  )
INTERSECT
SELECT c2.e_ref FROM claims c2
WHERE c2.pred_id="User:user_id" AND c2.value="u-1"
  AND NOT EXISTS (
    SELECT 1 FROM claims r
    WHERE r.pred_id="__system__.revokes" AND r.value=c2.asrt_id
  );
```

性能由 `idx_claims_pred_value` 索引保证;INTERSECT 处理 composite key。

#### 推荐

**(c) SQLite 内建索引**:与 INV-5（ledger 是 source of truth）严格一致,无第二 truth 源;`idx_claims_pred_value` 已经支撑。

`_revoked_asrt_ids` in-memory cache（已存在）继续作为优化层,加速 "exclude revoked" 的过滤。

**状态**:推荐 (c);待确认。

### §10.2 Q6:历史 / as-of lookup 语义

**问题**:`fg.read.get(User, user_id="u-1")` 默认返回当前 active 的 entity;但用户问"昨天的 u-1 是谁?"怎么办?

candidates:

| 选项 | 形态 |
|---|---|
| **(a) 只暴露当前 active**（最简单） | 当前 active 的 entity_ref 返回;旧 entity 通过其他 API 找 |
| **(b) 可选 as-of T 查询**（推荐） | `fg.read.get(User, user_id="u-1", as_of="2026-05-27")` 返回该时刻 active 的 entity_ref |
| **(c) 完整 bitemporal** | system_time + valid_time 双维度;复杂度高 |

#### Alpha 视角

`append-only-ledger-evaluation.zh.md` §6 G3 已识别 bitemporal 是"未来扩展面",当前不在 scope。

#### 推荐

**(a) 当前 active 默认**:第一版只暴露 active;as-of T 在 future blueprint 加（与 ledger 整体 bitemporal 升级一起做）。

如果用户问"昨天的 u-1 是谁",目前通过 audit API 走 `fg.audit.explain_fact` 或 history walk 即可,不强求 as-of 顶层入口。

**状态**:推荐 (a) 第一版只暴露 active;as-of 留 future。

#### Future design preview — 时间维度 3 维 API(at / during / now,Step 2+)

当前 shipped `AssertionView` 已有 `.at(t)`(参见 `docs/official/kernel/quickstart/assertions.md`)。Step 2+ 完整 bitemporal 升级时,建议扩展为:

| 时间维度 | 输入 | 语义 | 状态 |
|---|---|---|---|
| `view.at(t)` | 单个 ISO 时间(str) | point-in-time valid-time filter:`valid_from <= t and (valid_to is None or valid_to > t)` | ✅ shipped |
| `view.during((t_start, t_end))` | 时间区间 tuple | half-open `[t_start, t_end)`;默认**任意重叠**语义 — fact 的 `[valid_from, valid_to)` 跟查询区间有交集即匹配 | ⏳ Step 2+ |
| `clock.now()` 配合 `view.at(clock.now())` | (隐式)当前时间 | future ergonomic alias;**不**进 Step 1/locked surface | ⏳ Step 2+ future alias |

**`during` 重叠语义可选**(默认 (a)):
- (a) **任意重叠**(default): `[a_from, a_to)` 跟 `[t_start, t_end)` 有交集 — 最直觉,跟 SQL TSRANGE `&&` 一致
- (b) `[a_from, a_to)` ⊂ `[t_start, t_end)`(完全包含于) — `view.during(..., mode="within")`
- (c) `[a_from, a_to)` ⊇ `[t_start, t_end)`(完全包含) — `view.during(..., mode="contains")`

**`now` 为什么不进 Step 1 / locked surface**:
- `now` 引入**非确定性** — 跟 `audit / replay` 不友好(同一段代码不同时间运行结果不同)
- Determinism 是 ledger 路线的核心承诺
- 用户需要"当前时间"语义时显式 `view.at(clock.now())`,把时钟读取动作放在外层(可被 mock / inject)
- 未来可能加 `view.now(clock=injected_clock)` 这种依赖注入形态,但**不是 Step 1 默认 API**

**对齐 `assertions.md` 文档**:Step 2+ 落地时同步更新 `docs/official/kernel/quickstart/assertions.md` 的 time semantics 章节。

**未来更扩展位**:`raw_kind` / `bound` 概率排名(`view.rank_by_bound()` 等)— Step 2+ 之外的设想,不影响本节预案。

---

## §11 Adapter 边界（Q-PR1)

> **⏳ Step 2+ deferred — not part of Step 1 implementation scope.**
>
> Step 1 不重写 PyReason adapter。Q-PR1 与 Identity Step 1 增量正交,延后到 Step 2+ adapter rewrite slice 处理。

来自 [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) §10 转入。

### §11.1 问题

PyReason adapter 的 `_edge_rest_terms`（[`adapters/pyreason/accept.py:174-187`](../../../../src/factgraph/adapters/pyreason/accept.py)）构造 2-position rest_terms（source, target 端点）— 因为 PyReason 模型里 edge 是天然二元的。

在 INV-9 unary fact 下,单 Claim 装不下 (source, target) 两个 entity_ref。

### §11.2 候选解法

| 方案 | 形态 | 评价 |
|---|---|---|
| **(A) PyReason adapter rewrite — Relationship Claim lowering** | adapter 内部把 PyReason edge 的 n-ary rest_terms **lower 成 ledger 已有的 unary Relationship Claim 形态**:`Claim(pred_id=<rel_type>, e_ref=<source>, value=<target_e_ref>, value_tag="entity_ref")`。**不改 ledger schema**(INV-9 unary 仍是 ledger 终态)、**不为 adapter 开 INV-9 例外**、Relationship Claim 是 ledger 已有形态(不引入新底层模型);adapter rewrite 范围仅限 PyReason model → ledger Claim 的 lowering 路径 | **推荐** — fits 既有 Relationship Claim 抽象,不破坏 INV-9 |
| **(B) 给 INV-9 开 "adapter 特例" 逃生窗** | 允许特定 pred_id 保留 n-ary | ❌ 破坏 INV-9 统一性 |
| **(C) Edge 拆 2 个 Claim + synthetic 共享 ID** | source 一条 + target 一条,meta 关联 | 复杂;ledger 多写一倍 |

### §11.3 推荐

**(A) PyReason adapter 改用 Relationship 模式**。这是 adapter rewrite 范围,与 identity 重设计同 slice 处理。

**状态**:推荐 (A);具体重写计划在 blueprint 期定。

---

## §12 API 表面分层 + AssertionView 统一

**Step 1 锁定**:三层 SDK API surface（`fg.entities.*` / `fg.fields.*` / `fg.assertions.*`）+ 统一类型 `AssertionView`（scope-aware）+ `_meta` 统一 meta 输入入口 + 6 条硬定义。

> Step 1 范围:不新增 schema-aware uniqueness 强制（§9 延后）。本节描述的 entity-level CRUD / field-level cell 操作 / assertion-level filter 均在 Step 1 范围内,完整覆盖 Identity → Claim 后用户的查询和写入需求。

### §12.1 当前 shipped surface（基线）

本节为事实陈述,基于 `src/factgraph/sdk/store.py` audit。

#### 顶层命名空间

| Namespace | 主要方法 | 文件锚点 |
|---|---|---|
| `fg.read` | `get(EC, **id)` / `find(EC, **filter)` / `match(EC, template, ...)` / `ref(EC, **id)` | `sdk/store.py:_SDKReadManager` |
| `fg.write` | `set(F, e_ref, value)` / `add(F, e_ref, value)` / `retract(asrt_id)` / `edit(EC, **id)` | `sdk/store.py:_SDKWriteManager` |
| `fg.assertions` | `by_id(asrt_id)` / `by_ids([...])` / `active()` / `all()` / `field(F)` | `sdk/store.py:_SDKAssertionsManager` |
| `fg.schema` | `add(*classes)` / `ingest(data)` / `validate_provenance(obj)` | `sdk/store.py:_SDKSchemaManager` |
| `fg.views` / `fg.eval` / `fg.audit` / `fg.rules` / `fg.inferences` / `fg.package` | 各自专用 | 详见 `sdk/docs/04_api_surface.en.md` |

#### Snapshot 内导航

```python
snap = fg.read.get(User, tenant_id="t1", user_id="U001")  # EntitySnapshot

snap.ref                            # str (e_ref)
snap.entity_type                    # str
snap.identity                       # property → dict
snap.<field_name>                   # dot-access (current 非 Identity only; Step 1 后含 Identity)
snap.assertions                     # AssertionNamespace
snap.field(name)                    # = snap.assertions.field(name) → FieldAssertions
snap.field(name).active             # AssertionRecordSet
snap.field(name).history            # AssertionRecordSet (alias for .all, deprecated)
snap.field(name).all                # AssertionRecordSet
snap.field(name).at(t)              # AssertionRecordSet
```

#### Collection-level fluent

```python
# 当前 shipped AssertionRecordSet 方法
.where(value=, source=, trace_id=, version=, meta=)  # 过滤(meta 入口混杂)
.at(t) / .version(v) / .by_id(asrt_id)
.one() / .first() / .all()
```

#### 当前不对称性

| 项 | 现象 |
|---|---|
| Layer 1 / Layer 2 / Layer 3 散落在 `fg.read` / `fg.write` / `fg.assertions` 三个 namespace | 语义边界不清晰 |
| `fg.assertions.field(F)` 返回 `AssertionRecordSet`,`snap.assertions.field(name)` 返回 `FieldAssertions` | 同样的"窄化到字段"操作返回不同类型 |
| `fg.assertions.active()` 是 method,`snap.field("x").active` 是 property | 同样的"取当前未 revoke"在不同 scope 行为不一致 |
| `where(...)` 的 meta 过滤混杂:`source` / `trace_id` / `version` 是 flat kwarg + 另有 `meta={...}` dict | 一半键 flat、一半键 nested,内部不统一 |
| `fg.write.retract(asrt_id)` 在 write namespace,但按 asrt_id 导航是 assertion 层 | 跨层污染 |
| `fg.read.find` 用 `find` 动词,collection 用 `.where`,语义相同动词不同 | 同概念多名 |

### §12.2 三层分层

**导航 key 即层边界**:

```text
Layer 1  fg.entities.*    navigate by  EntityClass + identity / e_ref    (实体宏观)
Layer 2  fg.fields.*      navigate by  (Field, e_ref)                    (per-cell 操作)
Layer 3  fg.assertions.*  navigate by  asrt_id                           (原子 assertion)
```

#### Layer 1 — `fg.entities.*`

```python
fg.entities.create(EntityClass, **identity, meta=...)        -> EntitySnapshot
fg.entities.get(EntityClass, **identity)                     -> EntitySnapshot | None
fg.entities.where(EntityClass, **field_kwargs, _meta=None)   -> list[EntitySnapshot]
fg.entities.match(EntityClass, template, **port_constraints) -> MatchResult
fg.entities.ref(EntityClass, **identity)                     -> str
fg.entities.exists(EntityClass, **identity)                  -> bool
fg.entities.delete(EntityClass, **identity)                  -> None
fg.entities.edit(EntityClass, **identity)                    -> EntityEditor (context manager)
```

| 方法 | 语义 |
|---|---|
| `create` | 算 `e_ref = idref_v1(EntityClass, identity)` + 原子写所有 Identity Claim(INV-7b 镜像 + INV-7c 一致性)+ 可选 entity-level meta;Identity 必填(atomic);**若该 e_ref 已有任意 active Identity Claim 则抛 `EntityAlreadyExistsError`**(防重复 create 写多套 Identity Claim 到同 e_ref;ledger 自身不做 idempotency,SDK 层负责) |
| `get` | 按 identity bundle 查 entity;返回 EntitySnapshot 或 None |
| `where` | 按字段值过滤;kwargs 为 schema-aware field name;`_meta` 为统一 meta 过滤 dict;返回 `list[EntitySnapshot]` |
| `match` | RuleExpr 模板匹配;**保留独立**,不归入 `where`（语义不同:`where` 是 SQL filter,`match` 是 pattern matching） |
| `ref` | **deterministic typed constructor** — `encode_idref_v1(EntityClass, identity)`;**不是 lookup**(不查 ledger,只算 hash);用于 caller 想获取 e_ref token 但不写 ledger。X-style 下 `ref` 总是返回值(给定 identity 必有唯一 e_ref),即使该 entity 还没 create |
| `exists` | 该 e_ref 下是否还有未 revoke 的 Claim（比 `get(...) is None` 便宜） |
| `delete` | retract 该 e_ref 下所有 Claim（含 Identity） |
| `edit` | 返回 `EntityEditor` context manager;在 with-block 内批量修改字段 |

#### Layer 2 — `fg.fields.*`

```python
# Write
fg.fields.set(Field, e_ref, value, meta=...)        -> asrt_id
fg.fields.add(Field, e_ref, value, meta=...)        -> asrt_id
fg.fields.retract(Field, e_ref, value, meta=...)    -> asrt_id
fg.fields.delete(Field, e_ref, meta=...)            -> None

# Read
fg.fields.get(Field, e_ref)                         -> value | list[value]
```

| 方法 | 语义 |
|---|---|
| `set` | 替换:retract 该 (Field, e_ref) 所有当前值 + append 新值;单值多值通用（多值 value 为标量或列表） |
| `add` | 追加（multi only）;single 字段调用报错 |
| `retract` | 按值 retract:retract 该 (Field, e_ref) 下值等于 value 的 Claim;multi 字段移除特定项,single 若匹配则 retract |
| `delete` | 清空该 (Field, e_ref) 所有 Claim（整字段维度）;跟 `retract` 的区别是不指定具体值 |
| `get` | 物化当前值（应用 revoke 后）;single 返回 value,multi 返回 `list[value]` |

**不存在**（有意删除/不新增）:
- `fg.fields.where` — 用 `fg.assertions.where(field=F, ...)` 替代（输入语言一致,无独特价值）
- `fg.fields.history` — 用 `fg.assertions.where(field=F, e_ref=R)` 替代
- `fg.fields.scan` — 用 `fg.assertions.where(field=F)` 替代
- `fg.fields.find` — 用 `where + .entities()` 替代

#### Layer 3 — `fg.assertions.*`

```python
fg.assertions.by_id(asrt_id)                        -> AssertionRecord
fg.assertions.by_ids([asrt_id, ...], strict=True)   -> AssertionRecordSet
fg.assertions.active                                -> AssertionRecordSet  (property)
fg.assertions.all                                   -> AssertionRecordSet  (property)
fg.assertions.field(Field)                          -> AssertionView (ledger+field scope)
fg.assertions.where(*, field=, e_ref=, value=,
                    value_tag=, _meta=)             -> AssertionRecordSet
fg.assertions.retract(asrt_id, meta=...)            -> asrt_id   # ← 从 fg.write 搬过来
```

| 方法 | 语义 |
|---|---|
| `by_id` | 按 asrt_id 取单条;返回 `AssertionRecord` 或 `None` |
| `by_ids` | 批量按 asrt_id 取;**`strict=True` 默认** — unknown asrt_id 抛 `SDKStoreError`;`strict=False` 静默跳过 missing(审计路径默认严格,来源 PDF Change Request 2026-05-28) |
| `active` | property — 全 ledger 未 revoke 的 Claim 集合 |
| `all` | property — 全 ledger 全部 Claim（含 revoke） |
| `field(F)` | 窄化到字段 scope;返回 `AssertionView`（详见 §12.3） |
| `where` | 全 ledger canonical 过滤;返回 `AssertionRecordSet`（详见 §12.4） |
| `retract` | append revoke assertion;返回新 revoke 的 asrt_id |

**没有 schema-free write API**:Step 1 不引入 `fg.assertions.write(pred_id, e_ref, value)` 这类绕开 schema 的写入路径。所有 write 必须走 schema-aware 的 `fg.fields.set/add/retract/delete` 或 `fg.entities.create/delete`。

### §12.3 AssertionView 统一类型

统一原本散落的 `AssertionNamespace` + `FieldAssertions` 为一个 scope-aware 类型 `AssertionView`,在任何 scope（ledger / entity / field / entity+field）下 API 形态完全一致。

#### 类型契约

```python
class AssertionView:
    """Scope-aware view into assertions.

    Scope axes (internal): ledger / entity / field 的组合。
    窄化操作返回 AssertionView;终结操作返回 AssertionRecordSet 或 AssertionRecord。
    """

    # ─── 窄化操作（scope chain）───
    def field(self, f: Field | str) -> AssertionView:
        """窄化到字段 scope。
        - ledger scope: f 必须是 Field descriptor（字符串拒绝）
        - entity / entity+field scope: f 可为 Field descriptor 或字符串（entity_type 已知）
        """

    # ─── 终结操作（无参 property）───
    @property
    def active(self) -> AssertionRecordSet: ...    # 当前 scope 内未 revoke

    @property
    def all(self) -> AssertionRecordSet: ...       # 当前 scope 内全部

    @property
    def history(self) -> AssertionRecordSet:
        """已弃用,等价于 .all;backward-compat alias,不主动发 DeprecationWarning。"""

    # ─── 终结操作（参数化）───
    def where(self, *, field=_MISSING, e_ref=_MISSING, value=_MISSING,
              value_tag=_MISSING, _meta=_MISSING) -> AssertionRecordSet: ...

    # —— 时间维度(有特殊 valid_from/valid_to 计算)——
    def at(self, t: str) -> AssertionRecordSet: ...
    # Step 2+ planned: def during(self, t_range: tuple[str, str], *,
    #                              mode: Literal["overlap", "within", "contains"] = "overlap")
    #                              -> AssertionRecordSet: ...
    # `now` 不进 surface:用 view.at(clock.now()) 显式表达,保留 determinism

    # —— asrt_id 维度(有特殊索引)——
    def by_id(self, asrt_id: str) -> AssertionRecord | None: ...
    def by_ids(self, asrt_ids: Iterable[str], *, strict: bool = True) -> AssertionRecordSet: ...

    # —— 不在 AssertionView 主接口的 meta 过滤(无特殊行为)——
    # version(v) 已删除 — 等价于 .where(_meta={"version": v});普通 meta 不上 view 主接口
```

#### AssertionView 方法的招纳原则(重要)

> **一等方法**只授予有"特殊行为"的能力 — 即不能仅靠 `value` / `_meta` 过滤等价表达的能力:
>
> - 有 **revoke 跟踪计算**(`.active` / `.all`)
> - 有 **时间维度计算**(`.at(t)` / 未来 `.during(...)`,使用 `valid_from`/`valid_to` meta)
> - 有 **asrt_id 索引导航**(`.by_id` / `.by_ids`)
> - 有 **scope 窄化**(`.field(F)`)
>
> **普通 meta equality** 走 `.where(_meta={...})`,**不上 view 一等方法**。
>
> 反例(从 Step 1 surface 中**剔除**):
> - `.version(v)` — 没有特殊行为,等价于 `.where(_meta={"version": v})`;删除
>
> 未来若加 `.rank_by_bound()` 这类按 `bound` meta 概率排序的方法,因为它有**特殊计算逻辑**(排序),才能列为一等方法。普通 meta 不会因为"常用"就升格一等方法。

#### scope 入口表

```python
# ─── Ledger scope ───
fg.assertions                            -> AssertionView (ledger)
fg.assertions.active                     -> AssertionRecordSet
fg.assertions.all                        -> AssertionRecordSet
fg.assertions.field(User.email)          -> AssertionView (ledger+field)
                                         #   ↑ Field descriptor 必填,字符串拒绝
fg.assertions.field(User.email).active   -> AssertionRecordSet
fg.assertions.where(field=User.email,
                    value="a@b",
                    _meta={"source":"seed"}) -> AssertionRecordSet

# ─── Entity scope (pre-fetched) ───
snap.assertions                          -> AssertionView (entity)
snap.assertions.active                   -> AssertionRecordSet
snap.assertions.field("email")           -> AssertionView (entity+field)
                                         #   ↑ 字符串 OK,entity_type 已知
snap.assertions.where(field=User.email,
                      _meta={"source":"seed"}) -> AssertionRecordSet
                                         # 自动约束 e_ref=snap.ref

# ─── Entity+Field scope ───
snap.field("email")                      -> AssertionView (entity+field)
                                         # = snap.assertions.field("email")
snap.field("email").active               -> AssertionRecordSet
snap.field("email").at(t)                -> AssertionRecordSet
```

#### Collection 层 AssertionRecordSet

`AssertionRecordSet` 是 immutable tuple subclass,在所有终结操作的返回值上。它自己也有 fluent filter:

```python
# Collection-level fluent (in-set filter)
set.where(*, value=_MISSING, value_tag=_MISSING, _meta=_MISSING)  -> AssertionRecordSet
set.at(t) / set.by_id(asrt_id)                                    -> AssertionRecordSet
# version(v) 已剔除 — 用 set.where(_meta={"version": v});Step 2+: set.during(...)
set.one() / set.first() / set.all()                               -> AssertionRecord / set
set.e_refs                                                         -> set[str]     # 新增 property
set.entities()                                                     -> list[EntitySnapshot]  # 新增
```

#### `.where(...)` vs scope 窄化的区别

- `.field(F)` 是 **scope 窄化**:返回新的 `AssertionView`（deferred query）
- `.where(...)` 是 **filter 执行**:返回 `AssertionRecordSet`（materialized result）

链式示意:

```python
fg.assertions \
    .field(User.email)                # AssertionView (ledger+field scope)
    .where(value="a@b", _meta={"source":"seed"})  # AssertionRecordSet (filter 执行)
    .at("2026-05-28T12:00:00Z")       # AssertionRecordSet (in-set 时间过滤)
    .one()                            # AssertionRecord
```

#### 旧类型的归宿

| 旧类型 | 新归宿 |
|---|---|
| `AssertionNamespace` | **合并进 `AssertionView`** — 删除独立类型 |
| `FieldAssertions` | **合并进 `AssertionView`** — 删除独立类型 |
| `AssertionRecordSet` | **保留** — 仍是 fluent filter 的承载类型 |
| `AssertionRecord` | **保留** — 单条 assertion 不变 |

#### 当前值 vs assertion records 的层次区分（重要）

这是 PDF Change Request 2026-05-28 提出的**最关键概念澄清**:必须让用户清楚区分**当前 computed value** 与**底层 assertion records**。

```python
snap = fg.entities.get(User, tenant_id="t1", user_id="U001")  # EntitySnapshot

# —— 当前 computed VALUE ——
snap.user_id           # str             — Identity 字段(immutable anchor 镜像 Claim)
snap.email             # str             — 单值 Field:当前值(可变)
snap.display_name      # str | None      — 单值 Field 未设置时为 None
snap.tags              # list[str]       — 多值 Field:当前值列表

# —— 底层 assertion RECORDS ——
snap.field("email").active                          # AssertionRecordSet — 未 revoke 的 records
snap.field("email").all                             # AssertionRecordSet — 含 revoked 的 records
snap.field("tags").active                           # AssertionRecordSet — multi 字段可能有多条
fg.assertions.field(User.email).where(value="a@b") # AssertionRecordSet — ledger 范围按值过滤
```

**关键不变量**:

| 概念 | 表达路径 | 返回类型 |
|---|---|---|
| **当前 computed value** | `snap.<field_name>` 直接 dot-access | `value` / `list[value]` / `None` |
| **该字段的 assertion records 集合** | `snap.field("<name>").active` 或 `.all` | `AssertionRecordSet` |
| **单条 assertion record** | `...active.where(...).one()` | `AssertionRecord` |
| **retract / explain 用的稳定句柄** | `record.asrt_id` | `str` |

#### 为什么没有 `.active_assertions` / `.all_assertions` 后缀

PDF 建议过 `.active` → `.active_assertions`、`.all` → `.all_assertions`,理由是 `active` 容易跟 "the active value" 混淆。**我们 reject 这个 rename**,理由:

- **AssertionView 类型本身已经在说"这是 assertion 视图"**:用户已通过 `.field("x")` 显式进入 assertion 维度,继续访问 `.active` 不会跟 value 混淆 — 维度切换在前一步已完成
- **dot-access vs `.field(...)` 路径区分清楚**:`snap.email`(value)vs `snap.field("email").active`(records)在路径上就分开,不靠名字后缀
- **`.active_assertions` 啰嗦且 redundant**:在 AssertionView 上,`assertions` 后缀是空气词
- **fluent property 风格统一**:我们的 6 条硬定义里 Rule 4 规定 `view.at(t)`(以及未来 `during`)默认基于 `.active`;property 一律短名,加后缀会破坏整体风格

**单字段可能有多条 active assertions** — 例如 multi 字段、或 single 字段在并发写入 / 冲突 set without retract 等场景下。`.active` 是 **AssertionRecordSet**(plural by design),**不是 "the active value"**。当前 value 永远走 `snap.<field>`。

**消歧靠类型,不靠名字**:IDE / 类型注解 / docs 三方协同标明返回类型;我们用短名优先,牺牲少量 cold-read 友好度换取 fluent API 一致性。

### §12.4 `_meta` 统一输入

#### 痛点

当前 `AssertionRecordSet.where(...)` 的 meta 输入分散:`source` / `trace_id` / `version` 是 top-level flat kwarg,**另外**还有 `meta={...}` 字典 — 一半键 flat、一半键 nested,本身就不统一。

#### 解决:`_meta` 保留 namespace

所有 meta 过滤统一走单个保留 kwarg `_meta`（pydantic `model_*` 风的命名空间保留）,把所有 meta 键都放进去:

```python
# 旧 shipped (半 flat 半 dict, 不统一):
record_set.where(value="a@b", source="seed", trace_id="t", version="v", meta={"x": "y"})

# 新统一形式:
record_set.where(value="a@b", _meta={
    "source": "seed",
    "trace_id": "t",
    "version": "v",
    "x": "y",
})
```

#### `_meta` 在每个层次的统一形态

```python
# Layer 1 — entities.where (schema-aware)
fg.entities.where(User,
    # entity 字段过滤 (kwargs;Identity 和 Field 都可作过滤入口)
    tenant_id="t1",          # Identity 字段（Step 1 后参与镜像 Claim 反查）
    user_id="U001",          # Identity 字段
    status="active",         # Field
    # meta 过滤 (统一 dict)
    _meta={"source": "seed", "trace_id": "t-001"},
)

# Layer 3 — assertions.where (canonical)
fg.assertions.where(
    field=User.email,
    value="a@b",
    value_tag="string",      # 可选,默认从 value 的 Python 类型推断
    _meta={"source": "seed"},
)

# Collection — set.where (in-set filter)
record_set.where(value="a@b", _meta={"source": "seed"})
```

#### `_meta` 的 per-assertion AND 语义（Rule 1）

> `_meta` 过滤跟随**每一个 field filter 命中的 assertion**。`entities.where` 的多个 field filter 共享同一个 `_meta` 时,要求**所有命中的 assertion 都各自满足 `_meta`**（AND）。如果需要"任意 assertion 满足"或更复杂的关联条件,使用 `match`。

边界情况:

| 调用 | 语义 |
|---|---|
| `entities.where(User, status="active", _meta={"source":"seed"})` | 存在一条 `User:status = active` assertion,且**该条** assertion 的 meta `source=seed` |
| `entities.where(User, status="active", email="a@b", _meta={"source":"seed"})` | `status` 命中的 assertion **和** `email` 命中的 assertion **都各自**满足 `source=seed`（AND） |
| `entities.where(User, _meta={"source":"seed"})` 仅 meta 无 field | 存在**任意一条** assertion 满足 `source=seed`（meta-only 模式） |
| `entities.where(User)` 都不给 | 返回全部 User 实体 |
| `entities.where(User, tags="ops")` tags 是 multi | 存在一条 `User:tags = "ops"` assertion（至少一条命中即可） |

### §12.5 6 条硬定义

#### Rule 1 — `_meta` per-assertion AND 语义

详见 §12.4。

#### Rule 2 — `value_tag` 推断阶梯

```text
有 field= ?
├─ 是 ──> 从 schema 推断（field 的 type_domain）
└─ 否
   ├─ Python 类型明确（str/int/bool/bytes/float/UUID/datetime）?
   │  ├─ 是 ──> 从 Python 类型推断
   │  └─ 否 ──> 默认 "string"（不发 warning, docs 明确）
   └─ 用户显式给 value_tag= ──> 永远以显式为准
```

#### Rule 3 — `where` 默认值用 sentinel

`where(...)` 签名所有过滤键默认 `_ASSERTION_FILTER_MISSING`（`facade.py:97` 已定义）。

```python
where()              # 没有 value 过滤 (_MISSING)
where(value=None)    # 显式查 value 为 None
```

→ 不可用 Python `None` 当默认值,会与"查 None"冲突。

#### Rule 4 — 时间维度方法默认基于 active

```python
view.at(t)            == view.active.at(t)            # 默认含 revoke 边界处理后的 active
# Step 2+: view.during(...) == view.active.during(...)
# 含 revoke 历史走:
view.all.at(t)
```

→ docs 明确这一边界,避免 `at` / 未来 `during` 与 `all` / `history` 的语义混在一起。

→ **`view.version(v)` 已剔除**(无特殊行为,等价于 `.where(_meta={"version": v})`;详见 §12.3 招纳原则)。

#### Rule 5 — `by_id` 查 `.all` 不是 `.active`

```python
view.by_id(asrt_id) == view.all.by_id(asrt_id).first()
```

→ 理由:审计 / 重放场景需要能按 id 拿到已 revoked 的 record;查的是"曾经存在",不是"当前可见"。

#### Rule 6 — ledger scope `field(str)` 硬拒绝

```python
fg.assertions.field("email")            # raises SDKStoreError
fg.assertions.field(User.email)         # OK
snap.assertions.field("email")          # OK (entity_type 已知)
snap.assertions.field(User.email)       # OK 也合法
```

→ ledger scope 下字符串"email"会跨多个 entity type 产生歧义,必须用 Field descriptor 明确指定。

#### 补充约束:`retract` 不在 `AssertionView` 本体

`fg.assertions.retract(asrt_id)` 挂在 namespace manager 上,**不是 `AssertionView` 的方法**。`AssertionView` 是纯读 view,无 mutation。
- `snap.assertions.retract(...)` **不存在**（entity-scoped view 拒绝 mutation）
- 想 revoke 走 `fg.assertions.retract(asrt_id)` 或 `fg.fields.retract(Field, e_ref, value)` 或 `fg.fields.delete(Field, e_ref)`

#### 补充约束:`history` deprecated 策略

- docs 仅记录 `view.history == view.all` 为 backward-compat alias
- **不**默认发 `DeprecationWarning`（防测试当失败）
- 可加 opt-in env var（如 `FACTGRAPH_WARN_DEPRECATED=1`）在需要时启用
- 正式移除时机另议

### §12.6 类型迁移映射

| 当前 shipped | 新位置 / 变更 |
|---|---|
| `fg.read.get(EC, **id)` | → `fg.entities.get(EC, **id)` |
| `fg.read.find(EC, **filter)` | → `fg.entities.where(EC, **filter, _meta=...)` |
| `fg.read.match(EC, template, ...)` | → `fg.entities.match(EC, template, ...)` |
| `fg.read.ref(EC, **id)` | → `fg.entities.ref(EC, **id)` |
| `fg.write.set(F, e_ref, v)` | → `fg.fields.set(F, e_ref, v)` |
| `fg.write.add(F, e_ref, v)` | → `fg.fields.add(F, e_ref, v)` |
| `fg.write.retract(asrt_id)` | → `fg.assertions.retract(asrt_id)` ← **挪层** |
| `fg.write.edit(EC, **id)` | → `fg.entities.edit(EC, **id)` |
| `fg.assertions.by_id/by_ids/active/all/field` | 保持,**新增 `.where()` + `.retract()`** |
| `fg.assertions.active()` (method) | → `fg.assertions.active` (property) |
| `fg.assertions.all()` (method) | → `fg.assertions.all` (property) |
| `fg.assertions.field(F)` 返回 `AssertionRecordSet` | → 返回 `AssertionView` |
| `record_set.where(value=, source=, trace_id=, version=, meta=)` | → `record_set.where(value=, _meta={"source":"...", "trace_id":"...", "version":"...", ...})` ← **折叠** |
| `view.version(v)` / `set.version(v)` | → **删除一等方法**;改用 `where(_meta={"version": v})`(无特殊行为,不应在 view 一等接口;详见 §12.3 招纳原则) |
| `FieldAssertions.history` | → `AssertionView.history`（deprecated alias of `.all`） |
| `AssertionNamespace` | → 合并进 `AssertionView` — **删除独立类型** |
| `FieldAssertions` | → 合并进 `AssertionView` — **删除独立类型** |
| **新增** | `fg.entities.create / where / exists / delete` |
| **新增** | `fg.fields.retract(Field, e_ref, value)` / `fg.fields.delete(Field, e_ref)` / `fg.fields.get(Field, e_ref)` |
| **新增** | `fg.assertions.where(...)` / `fg.assertions.retract(asrt_id)` |
| **新增** | `AssertionRecordSet.e_refs` / `.entities()` |
| **Step 2+ planned** | `view.during((t_start, t_end), mode="overlap")` — 时间区间查询(详见 §10.2 future preview);`now` 不进 surface |

### §12.7 删除清单 + 弃用清单

#### 完全删除（alpha 阶段无 alias）

| 删除 | 替代 |
|---|---|
| `fg.read.*` namespace | 拆到 `fg.entities.*` |
| `fg.write.*` namespace | 拆到 `fg.fields.*` 和 `fg.assertions.retract` 和 `fg.entities.edit` |
| `find` 动词（任何层） | 统一为 `where` |
| `AssertionNamespace` 类 | 合并进 `AssertionView` |
| `FieldAssertions` 类 | 合并进 `AssertionView` |
| `record_set.where(source=, trace_id=, version=)` flat kwargs | 折叠进 `_meta={...}` |
| `view.version(v)` / `set.version(v)` 一等方法 | 无特殊行为;改 `where(_meta={"version": v})`(招纳原则:普通 meta equality 不上 view 一等接口) |

#### 软弃用（保留为 alias,加文档标注）

| 弃用 | 替代 | DeprecationWarning |
|---|---|---|
| `FieldAssertions.history` / `AssertionView.history` | `.all` | **不**默认发（防测试失败）;env var opt-in |

### §12.8 Identity 字段在三层的可见性

Step 1 后 Identity 同时是 e_ref hash 输入 + 镜像 Claim,在三层都**可读不可写**:

| 层 | 能读 Identity 吗 | 能写 / 改 Identity 吗 |
|---|---|---|
| Layer 1 (entities) | ✅ `get(...).user_id` / `get(...).tenant_id` 等 dot-access | ✗ Identity 只能在 `create` 时整 bundle atomic 给;`edit` 中尝试改 Identity 报错;改身份语义 = `delete` 旧 entity + `create` 新 entity(详见下方"改 Identity 语义") |
| Layer 2 (fields) | ✅ `fg.fields.get(User.user_id, e_ref)` | ✗ `fg.fields.set/add/retract/delete` 应用于 Identity 字段时报错(schema-aware 层硬拒绝;Field 字段可写) |
| Layer 3 (assertions) | ✅ `fg.assertions.field(User.user_id).active` / `where(field=User.user_id)` | ✗ `fg.assertions.retract(asrt_id)` 检测到 asrt_id 是 Identity Claim 时报错(防 INV-7c 一致性破坏;Field Claim 可单独 retract) |

**Rationale (INV-7c 一致性强制)**:Identity Claim 只能通过 `fg.entities.create` 写入(原子)、`fg.entities.delete` 整批撤销(原子)。任何其他路径修改 Identity Claim 都会让 `active Identity Claim 集合`≠`e_ref hash 输入的 Identity bundle`,产生 dual-truth split(详见 §5.2 INV-7c)。

#### 改 Identity 语义(重要,防误解)

**改 Identity 字段值 = 创建新 entity**:

```python
# 用户 A 想"改 user_id"(实际是创建新 entity)
old_ref = fg.entities.ref(User, tenant_id="t1", user_id="U001")   # 旧 e_ref
fg.entities.delete(old_ref)                                          # 旧 entity 消失,所有 Claim 整批 retract
new_ref = fg.entities.create(User, tenant_id="t1", user_id="U002") # 新 entity
# ⚠️ 旧 entity 的 Field history(display_name / tags / permissions 等) 全部丢失
# 若需要保留,必须手工迁移:read 旧 entity 的 Field 值 → 写到新 entity
```

**业务上想"rename 同一现实对象"**? — 说明该字段**不应该建模为 Identity**(参见 §4.1 边界规则);改为 Field 或 future alias / external lookup key 概念。

#### 查询入口

`fg.entities.where(User, tenant_id="t1", user_id="U001")` 等查询自动覆盖 Identity 字段 — Step 1 后 Identity 字段(镜像 Claim)成为 `where` 的合法 filter 输入,跟 Field 反向查询一致。

### §12.9 Schema namespace operations（horizontal facet）

Schema namespace 不是 entities / fields / assertions 三层的一部分,而是配置三层的 **horizontal facet**。它管理 entity 类型注册和 schema 演化。

#### 当前 shipped 状态

```python
# 当前(混杂):
fg.schema.add(*classes)              # ← 既能 register 新类型,也能 extend 已有类型
fg.schema.ingest(data)
fg.schema.validate_provenance(obj)
```

`fg.schema.add` 当前混淆两个不同的语义,**来源 PDF Change Request 2026-05-28 指出的问题**。

#### Step 1 锁定:`fg.schema.add` 拆三

```python
fg.schema.register(EntityClass)       # 注册新 entity 类型
fg.schema.extend(EntityClass)         # 扩展已注册类型(仅 additive 字段)
fg.schema.apply(EntityClass)          # 便利方法 — 自动判断 register vs extend (safe diff)
fg.schema.ingest(data)                # 保持
fg.schema.validate_provenance(obj)    # 保持
```

| 方法 | 语义 | 失败条件 |
|---|---|---|
| `register(EntityClass)` | 注册新 entity 类型(创建 schema entry) | entity_type 已注册 → `SchemaConflictError` |
| `extend(EntityClass)` | 在已注册类型上添加字段(仅 additive Field;**不允许新增 Identity 字段**)| entity_type 未注册 → `SchemaNotFoundError`;字段删除 / 重命名 / 类型变更 / 新增 Identity / Identity↔Field 互转 等非 additive Field 变更 → `SchemaNonAdditiveError`(配套 §5.2 INV-7c 实施 — 详见下方约束) |
| `apply(EntityClass)` | 便利包装 — 自动判断 register vs extend;safe diff 决策 | 仅在 register 和 extend 都会失败时报错 |
| `ingest(data)` | 不变 | — |
| `validate_provenance(obj)` | 不变 | — |

**`apply` 的 safe diff 算法**:对比 in-memory `EntityClass.__sdk_entity_spec__` 与 ledger 已注册 schema:
- 若 entity_type 未注册 → 转 `register`
- 若 entity_type 已注册且变更 additive → 转 `extend`
- 若 entity_type 已注册且变更非 additive(删/改字段)→ 报 `SchemaNonAdditiveError`(不静默破坏)

#### `extend` 的 schema evolution 约束(配套 INV-7c)

`fg.schema.extend(EntityClass)` 的 enforce 行为(详细 rationale 见 §5.2 INV-7c 实施):

| diff 类型 | extend 行为 |
|---|---|
| 新增 Field 字段 | ✅ 允许(纯 additive) |
| 新增 Identity 字段 | ✗ 拒绝 — 改 Identity bundle = 改 e_ref 输入,等于全部 entity 迁移 |
| 删除字段 | ✗ 拒绝(非 additive) |
| Identity → Field 降级 | ✗ 拒绝 — 旧 Identity Claim 会变得可单独 retract,打破 INV-7c |
| Field → Identity 升级 | ✗ 拒绝 — 旧 Field Claim 缺乏原子写入语义,一致性无法溯及既往 |
| 字段类型 / cardinality 改 | ✗ 拒绝(非 additive) |
| `description` / `pattern` 等元数据改 | ⏳ Step 2+ 评估 |

**Identity bundle 重设计如何做**:不允许 in-place schema diff;走 entity-type 迁移(新 EntityType 注册 + 旧 entity 数据迁移工具)。这是 Step 2+ Identity 数据迁移工具的设计动机(§13.2 列项)。

#### 删除清单

| 删除 | 替代 |
|---|---|
| `fg.schema.add(*classes)` 混杂语义 | 拆为 `register` / `extend` / `apply` |
| "replacement class via `schema.add`" 隐式语义 | `extend` 显式 additive-only;非 additive 必须报错或显式 migration |
| `extend` 允许 Identity / Field 互转 | 拒绝(配套 INV-7c;详见上方 schema evolution 约束) |

### §12.10 与 ledger spec 的边界

底层 Claim / claim_meta / ledger_meta 表结构、INV-1 至 INV-15、`idx_claims_pred_value` 索引等 ledger schema truth 在 [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md);本节描述的 API 表面**不重复 ledger schema** — 所有 SDK 操作最终映射到 ledger spec 描述的 Claim append + claim_meta append + 索引查询。

---

## §13 Step 1 实现范围 + 延后清单

### §13.1 Step 1 in-scope

| 项 | 描述 |
|---|---|
| **§4.1 4 条硬定义** | (1) e_ref typed constructor / (2) Identity immutable anchor / (3) Field mutable / (4) Identity-as-Claim mirrored |
| **§4.1 边界规则** | "未来可能变的值不要建模为 Identity"作为 schema 设计指导 |
| **Q1 e_ref 形态锁定 idref_v1** | 不在 Step 2+ 延后 — content-derived typed hash;opaque alternative 评估后不采纳(§7) |
| **INV-7a Identity Anchor immutable** | 改 Identity = `delete + create` 新 entity;不允许 in-place(§5.2)|
| **INV-7b Identity-as-Claim 镜像** | identity 值同时存为 ledger Claim,产生 4 项 ergonomic 收益(§5.2)|
| **INV-7c Identity Claim ↔ e_ref hash 一致性** | Identity Claim 只能 create 写、delete 整批撤销;Layer 1/2/3 三层禁止单独修改 Identity Claim;防 dual-truth split(§5.2)|
| **Schema 声明** | Form I — Identity / Field 二分 + `_DataMember` 共通基类 + Literal 枚举 + 类型推断 cardinality + 去除 `primary_key` |
| **API 表面三层** | `fg.entities.*` / `fg.fields.*` / `fg.assertions.*` |
| **`AssertionView` 统一** | 替代 `AssertionNamespace` + `FieldAssertions` |
| **`_meta` 统一输入** | 所有 meta 过滤走 `_meta={...}` dict,折叠原 flat kwarg |
| **6 条硬定义**(§12.5) | sentinel / at-version 默认 / by_id 走 .all / history 弃用 / retract 位置 / ledger scope 拒字符串 |
| **`fg.entities.create`** | 算 e_ref + atomic Identity Claim 写 + 可选 meta;**e_ref 已有 active Identity Claim 抛 `EntityAlreadyExistsError`** |
| **`fg.entities.ref`** | **deterministic typed constructor**(不是 lookup);给定 identity 直接算 e_ref 不写 ledger |
| **`fg.entities.delete`** | 整批 retract 该 e_ref 所有 Claim(含 Identity 全部 + Field 全部) |
| **`fg.entities.exists`** | 便利存在性检查 |
| **`fg.assertions.retract`** | 从 `fg.write.retract` 挪过来;检测到 Identity Claim 时拒绝(INV-7c) |
| **`fg.assertions.by_ids(strict=True)` 默认** | 审计路径默认严格;unknown asrt_id 抛错(来源 PDF Change Request 2026-05-28) |
| **`AssertionRecordSet.e_refs` / `.entities()`** | fluent chain 终结的便利提取 |
| **`_DataMember.pattern`** | regex 字段值校验,Layer 4;仅 `str` 字段;来源 PDF Change Request 2026-05-28 |
| **`fg.schema.register / extend / apply` 三分** | 替代混杂的 `fg.schema.add`;register=新类型 / extend=additive 扩展 / apply=safe diff(来源 PDF Change Request 2026-05-28) |
| **"当前值 vs assertion records" 边界澄清** | docs 强调 `snap.<field>` 是 value、`snap.field(F).active` 是 records;详见 §12.3 |
| **改 Identity 语义文档化** | `delete + create + 显式数据迁移`;旧 entity Field history 不自动继承(§12.8) |
| **AssertionView 招纳原则** | `version()` 等普通 meta equality 不上 view 一等方法;走 `where(_meta={...})`;有特殊行为(revoke / 时间 / asrt_id 索引)的能力才上一等方法(§12.3) |
| **INV-7c 实施策略 C** | application 层 in-memory Identity pred_id set + O(1) membership 检查;策略 B(claim_meta tag)拒绝(§5.2) |
| **Schema evolution 约束** | `fg.schema.extend` 拒绝 Identity 新增 / 删除字段 / Identity↔Field 互转;Identity bundle 重设计走 entity-type 迁移(§5.2 + §12.9) |

### §13.2 Step 2+ 延后

| 项 | 来源 | 说明 |
|---|---|---|
| **`Identity(internal=True)` flag** | §8.6 | SDK 层 Rule 编译时拒绝引用 internal identity 字段 |
| **`InternalIdentity` 具体类型** | §8.6 | `Fingerprint(of=...)` / `ULID()` / `ContentHash()` 等;**注意**:这些都是 Identity 的派生形式,**不**改变 §4.1 硬定义 1(e_ref 仍是 typed content-derived hash)|
| **多 Identity 联合 Fingerprint** | §8.6 | 系统派生 identity |
| **备用自然键 / `alternative_key`** | §9.1 | Composite + Multiple alternative,视 Claim 反向索引 UX 是否足够再裁定 |
| **External alias / lookup key 概念** | §4.1 边界规则 + §8.6 | 给"未来可能变的字段"提供 alias / lookup 入口,不进 Identity bundle;视用户实际需求再裁定 |
| **唯一性强制 (uniqueness validation)** | §9 | schema-level uniqueness 写入时校验(X-style 下 Identity bundle 已唯一,Field 唯一性需要单独机制)|
| **唯一性违反语义** | §9.2 | reject / auto-retract / 暂态允许的选择 |
| **专用 Lookup 索引** | §10.1 | X-style 下 Identity → e_ref 直接算,**不需要**反向索引;Field 反向查询仍走 `idx_claims_pred_value`;Step 2+ 视性能加专用索引 |
| **as-of / bitemporal 历史查询** | §10.2 | Q6 视用户需求再定 |
| **PyReason adapter rewrite** | §11 | Q-PR1 |
| **`fg.tx()` 跨调用事务 context manager** | §12 隐含 | 当前每个调用天然事务,跨调用事务延后 |
| **`default` / `default_factory` 重新评估** | §8.5 | 仅配合 InternalIdentity / 系统派生 identity 重新设计;不作为普通 `_DataMember` 共通参数 |
| **`validators` / `constraints` / `alias` / `deprecated` / `examples` 共通参数** | §8.5 | `_DataMember` 扩展位 |
| **`dict[K, V]` 容器类型推断** | §8.4 | 可能映射为 multi pair 或独立 KV entity |
| **Schema-free escape hatch** | §12.2 Layer 3 | 当前不提供;视有无 migration / debug 场景需求再定 |
| **Identity 数据迁移工具** | §12.8 改 Identity 语义 | 帮用户从旧 entity 把 Field history 搬到新 entity 的便利方法;Step 2+ |

### §13.3 Step 1 → Step 2+ 演化路径

Step 1 落地的设计扩展点不会反过来推翻 Step 1 决策:

- `Identity(internal=True)` 是新增 kwarg,不改 Identity 默认语义
- `InternalIdentity` / 系统派生 identity 若需要 `default_factory` 语义,会以独立 descriptor 或派生类型新增,不回到普通 `Identity` / `Field` 的共通参数
- 唯一性强制是在 `create` / `set` 路径上加 validation,API 表面不变
- 专用 Lookup 索引是底层 SQLite 优化,API 表面不变
- bitemporal 历史查询是 `where` 的 `at=` / `as_of=` 扩展 kwarg,不冲突 Step 1 `where` 签名

### §13.4 Slice 1 + Slice 2 落地状态(2026-05-30)

§13.1 中标的 "Step 1" 是 ADR-IC adopt 之前的单批次范围(Form I + Identity-as-Claim 合并)。ADR-IC adopt 后(@ `2d0866ed`),Step 1 split 成两个独立 slice 各自完成 audit-to-archive cadence:

#### §13.4.1 Slice 1 — Form I schema refactor(landed 2026-05-29 @ `9cef674b`)

Branch:`v0.2.0-blueprint-slice-1-form-i-schema-2026-05-29` @ `9cef674b`(branch close + pushed to origin;sacred master `562c7419` 未动)

落地的 §13.1 in-scope 项(Form I 范畴):

| §13.1 项 | Slice 1 status |
|---|---|
| **Schema 声明** Form I — Identity / Field 二分 + `_DataMember` 共通基类 + 类型推断 cardinality + 去除 `primary_key` | ✅ shipped(Form I 完整 — Identity()/Field() 注解驱动,移除 primary_key kwarg)|
| **6 条硬定义**(§12.5)的部分 schema-相关项 | ✅ shipped 跟 Form I 同步落地的部分 |

未完成项滚到 Slice 2 + 后续 slice。

#### §13.4.2 Slice 2 — Identity-as-Claim core(landed 2026-05-30 on `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29`)

Blueprint:[`workflow/blueprints/active/2026-05-29_slice-2-identity-claim-emission.md`](../../../blueprints/active/2026-05-29_slice-2-identity-claim-emission.md)

落地的 §13.1 in-scope 项(Identity-as-Claim 范畴 + ADR-IC §4.1/§4.2/§4.3/§4.4):

| §13.1 项 | Slice 2 commit |
|---|---|
| **INV-7a Identity Anchor immutable** | 文案 + reject 路径 Step 6 落地 @ `c2d659c1`(IdentityEditor + plan_write_command 文案统一 ADR-IC §4.1 wording + `code="INV_7C_IDENTITY_PROTECTED"`)|
| **INV-7b Identity-as-Claim 镜像** | application 层 `_materialization_ops` 已 shipped 基线;Slice 2 Step 8 emission contract tests @ `ab168063` 实证覆盖 `fg.ref + fg.set` / `SDKBatchTx.commit` / `EntityEditor.commit` 三路径 atomic + dedup |
| **INV-7c Identity Claim ↔ e_ref hash 一致性** | 三层 enforcement Step 2-5 全部落地:application source-of-truth `retract_guard.py` @ `187a2918` Step 2;SDK shell `SDKStore.retract` wrap @ `12475859` Step 3;application ingest `_apply_retract` @ `16aeff69` Step 4;application entity_write `_apply_op` retract branch @ `a4853a0a` Step 5 |
| **INV-7c 实施策略 C**(application 层 in-memory Identity pred_id set + O(1) membership 检查)| `SchemaIndex.identity_pred_ids` + `exists_pred_ids` + `protected_anchor_pred_ids` property Step 1 落地 @ `73993ebd` |
| **Schema evolution 约束** Identity / Field 互转拒绝 + Identity 新增拒绝 | Slice 2 Step 1 cache 提供 enforce 基础;`fg.schema.extend` hook 留 ADR-API Q14 carry-forward(per Slice 2 SF4 + N1)|
| `<EntityType>:exists` co-emission + transitional guard | application + SDK shell 三层 enforcement 都识别 `:exists` classification 并 raise `code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD"`(NON INV-7c per ADR-IC §4.4)|
| Shadow store legacy 定位 | Step 7 落地 @ `d46b9fe7`(`sdk/store.py:_identity_values_by_e_ref` class-level 注释 — LEGACY / INTERNAL COMPATIBILITY only,NOT Layer 2 contract;两分支 fail-fast / lazy materialization 显式记录;forward direction = `fg.entities.create` eager emission + shadow store removal carry-forward)|
| Load-bearing docs sync | Step 9(本 commit)— `sdk/docs/04_api_surface.en.md` 新增 §7 Identity Claim Emission and Reject Semantics + §5.2 ADR-IC adopted wording 对齐 + 本 §13.4 Slice 2 landed status note |

**§13.1 carry-forward 项**(留 Slice 3a 或之后):

- `fg.entities.create / fg.entities.delete / fg.entities.exists` 三个 entities namespace 入口 — Slice 3a ADR-API Q10 namespace migration scope(Slice 2 error wording 引用 `fg.entities.delete + fg.entities.create` 作为 user migration guidance,implementation 不依赖 unshipped API)
- `fg.fields.* / fg.assertions.*` namespace 重组 — Slice 3a ADR-API Q10
- `AssertionView` 统一 / `_meta` 统一输入 / `fg.schema.register / extend / apply` 三分 — 留待后续 slice(注:`_DataMember.pattern` 已在 Slice 1 Form I 随 `Identity(..., pattern=)` / `Field(..., pattern=)` 落地,不属 carry-forward)
- 内部 rollback `core/derivation/accept.py:401` retract_by_asrt — 跟 Q-PR1 carve-out 一致 intentionally unguarded(Slice 2 SF11 锁定 — internal classification preserved,不走 retract guard)

#### §13.4.3 Slice 2 Q-PR1 carve-out preservation

Per Slice 2 SF5 + N11:`core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py:401`(internal rollback)— 全 0 diff,不被 Slice 2 三层 enforcement 触达;协议 / 核心 / pyreason 直接路径继续走原 shipped 行为。Slice 2 enforcement 边界严格落在 application(source-of-truth)+ SDK shell(fail-fast)— defense-in-depth 但不下沉到协议层。

### §13.5 Slice 3a — API namespace refactor landed status(2026-05-30)

Blueprint:`workflow/blueprints/active/2026-05-30_slice-3a-api-namespace.md`
(`v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30`,forked from Slice 2 close `c927d41f`)。

Slice 3a 落地 ADR-API Q10-Q14 cluster,把 §12 的 API 表面从设计锁定推进到 shipped implementation:

| §12 / ADR-API 项 | Slice 3a status |
|---|---|
| **Q10 三层 namespace** | ✅ shipped:`fg.entities.*` / `fg.fields.*` / `fg.assertions.*`;old `fg.read.*` / `fg.write.*` + 8 个 flat shortcut(`fg.set/add/retract/edit/get/ref/find/match`)hard removed |
| **Layer 1 entities** | ✅ shipped:`get` / `where` / `match` / `ref` / `create` / `delete` / `exists` / `edit`;`create` eager emits Identity Claims + `:exists`;`delete` 是 Identity Claim 唯一合法整批 revoke path;`exists` 读 active `:exists` Claim |
| **Layer 2 fields** | ✅ shipped:`set` / `add` / `retract` / `delete` / `get`;Identity fields 仍受 INV-7c guard 保护;`delete` fail-fast first-error |
| **Layer 3 assertions** | ✅ shipped:`where` / `by_id` / `by_ids` / `retract` / `active` / `all`;`retract` owns Slice 2 guard wrapper;Identity Claims raise `INV_7C_IDENTITY_PROTECTED`;`:exists` raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` |
| **Q11 AssertionView 统一** | ✅ shipped:`AssertionView` replaces `AssertionNamespace` + `FieldAssertions`;views are pure-read(no retract/set/add/delete methods);`.history` is deprecated alias of `.all`,warning only under `FACTGRAPH_WARN_DEPRECATED=1` |
| **Q12 `version(v)` hard remove** | ✅ shipped:`AssertionRecordSet.version` / `AssertionView.version` removed;use `.where(_meta={"version": v})` |
| **Q13 `_meta` canonical filter** | ✅ shipped:record sets, assertion views, and assertions manager all use `_meta={...}` + shared `_ASSERTION_FILTER_MISSING`;flat `source=` / `trace_id=` / `version=` / `meta=` kwargs removed |
| **Q14 schema namespace split** | ✅ shipped:`fg.schema.register` / `extend` / `apply`;`fg.schema.add` removed;ADR-IC §4.3.6 part 1+2 enforced with zero side effects on reject |
| **Slice 2 ADR-API Q14 carry-forward** | ✅ closed:SchemaIndex cache rebuild happens in `register` / `extend` / `apply`;Identity↔Field swaps, Identity additions, destructive field changes, and generated `:exists` predicate mutations reject before mutation |

Implementation lineage highlights:

| Step | Commit | Surface |
|---|---|---|
| Step 1 | `f63609ab` | `fg.entities` base manager |
| Step 2 | `c5c0e74d` + `691b766b` | `fg.entities.create` + public `EntityAlreadyExistsError` export |
| Step 3 | `e0e992da` | `fg.entities.delete` path-bound whole-entity revoke |
| Step 4 | `4db4d6de` | `fg.entities.exists` |
| Step 5 | `d24ddad1` | `fg.fields.*` |
| Step 6 | `985495f8` | `AssertionsManager` + Layer 3 retract ownership |
| Step 7 | `6136f257` | read/write namespace + flat shortcut deletion |
| Step 8 | `9e35685a` | `AssertionView` unification |
| Step 9 | `5fb93a18` | `version(v)` + flat `where` kwargs hard remove |
| Step 10 | `6954bb96` | `fg.schema.register/extend/apply` + ADR-IC §4.3.6 guard |
| Step 11 | `0d27dc85` | In-scope tests migrated to canonical namespaces |
| Step 12 | close commit | Load-bearing docs + §10 Outcome + `Status: implemented` |

Q-PR1 carve-out 继续继承:Slice 3a 不修改 `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py`。`core/derivation/accept.py:401` internal rollback path 保持 Slice 2 SF11 classification,intentionally unguarded。

Slice 3a close 后仍留的 carry-forward:

- Step 2+ `:exists` removal(per ADR-IC §4.4.4)— transitional guard 跟 `:exists` co-emission lifecycle 同步退役。
- Step 2+ shadow store removal(per ADR-IC §4.2.4)— `fg.entities.create` eager emission 已 shipped,legacy `fg.entities.ref + fg.fields.set` lazy compat 仍保留。
- Slice 3b ledger schema migration(`__system__.revokes` + claims `value`/`value_tag` 双列)。
- Slice 4 wider docs polish(public quickstarts / non-load-bearing SDK docs / examples notebooks / active design-points)— in progress on `v0.2.0-impl-slice-4-docs-polish-2026-05-30`。
- Slice 5+ Q-PR1 PyReason adapter rewrite + INV-9 runtime strict enforcement。

---

## §14 与姊妹 doc 的关系

### §14.1 与 `ledger-schema-specification.zh.md` 的关系

本 doc 在 ledger spec 的 schema 终态上设计 Identity 机制。具体借力:

| ledger spec | 本 doc 的应用 |
|---|---|
| INV-9 unary fact | Identity-as-Claim 自然落地:每个 identity 值是独立 unary Claim(镜像) |
| INV-10 system namespace | entity_ref 的 prefix(`idref_v1:`)与 system namespace 边界清晰 |
| INV-11 / 12 / 13 revoke 机制 | **Field 变更** = revoke + append 走 ledger 生命周期;**Identity 变更** = `entities.delete + entities.create`(新 entity, 新 e_ref;旧 entity 整批 revoke);两者复用同一 revoke 原语,但语义边界由 INV-7a/c 区分 |
| §3.1 索引基线(`idx_claims_pred_value`)| **Field 反向查询**直接借力(`fg.entities.where(User, status="active")` 等);**Identity 查询**走 `idref_v1(EntityType, identity)` deterministic hash,**不**走反向索引;详见 §10 status note |
| §8.5 SDK update 流 | Field 变更 SDK API 基于 update 原语;Identity 字段拒绝 update(INV-7c) |

### §14.2 与 `append-only-ledger-evaluation.zh.md` 的关系

evaluation doc 的 G1 标题"Identity = content hash anti-pattern"**需要重新措辞** — 本轮 FactGraph **选择**了 typed content-derived hash 作为 e_ref(`idref_v1(EntityType, Identity bundle)`),把它定性为 anti-pattern 不符合本轮设计选择。

修订建议(evaluation doc 同步时):
- G1 标题改为"Identity 用完即扔(only used as hash input,not stored as queryable Claim)"
- 本 doc Step 1 落地解决的是 **identity-as-facts 缺失**(Identity 值仅进 hash,不作为 first-class ledger Claim),**不**是"content-derived hash 本身"
- "content-derived hash"由 §4.1 硬定义 1 锁定,是本轮选择;Y-style opaque allocated 是 valid alternative model 但本轮不选(见 §3.2 / §4.1)

evaluation doc 的 G3(bitemporal upgrade)与本 doc Q6(as-of lookup)相关 — Q6 当前 Step 2+ 延后,完整 bitemporal 是 future doc 议题。

---

## §15 决策日志

每条决策按时间顺序追加。

| 日期 | 决策点 | 选项 | 当前状态 |
|---|---|---|---|
| 2026-05-28 | doc 创建 + 拆分:identity-mechanism-redesign 与 ledger-schema-specification 分立 | 接受 | ✅ 已采纳 |
| 2026-05-28 | Alpha 状态:无生产 entity_ref token 兼容性负担;INV-8 消解 | 接受 — entity_ref 可完全清洁切换 | ✅ 已采纳（详见 §5.3）|
| 2026-05-28 | 设计承诺 1-4(早期版本:opaque entity_ref / identity-as-facts / 变更走 retract+append / uniqueness schema-level)| 接受(后被重述) | ⚠️ **后续重述** — 见 2026-05-28 "e_ref 设计方向锁定 X-style typed content-derived hash" 条;§4.1 4 条硬定义已替换早期版本(typed constructor / immutable anchor / mutable Field / mirrored Claim) |
| 2026-05-28 | Q2 Schema 声明 — **Form I 锁定**（候选 C 演化扩展) | 接受 | ✅ 已采纳（详见 §8） |
| 2026-05-28 | API 表面三层分层（entities / fields / assertions） + AssertionView 统一 | 接受 | ✅ 已采纳（详见 §12） |
| 2026-05-28 | `_meta` 保留 namespace 统一 meta 过滤入口 | 接受 | ✅ 已采纳（详见 §12.4） |
| 2026-05-28 | 6 条硬定义（sentinel / at-version 默认 / by_id 走 .all / history 弃用 / retract 位置 / ledger scope 拒字符串） | 接受 | ✅ 已采纳（详见 §12.5） |
| 2026-05-28 | Identity → Claim（Step 1 核心增量） | 接受 | ✅ 已采纳（详见 §8.3 / §13） |
| 2026-05-28 | PDF Change Request triage — `Identity(pattern=r"...")` 字段值 regex 校验 | 接受 | ✅ 已采纳（详见 §8.5 — pattern 作为 `_DataMember` Step 1 共通字段） |
| 2026-05-28 | PDF Change Request triage — `fg.schema.add` 拆为 `register / extend / apply` | 接受 | ✅ 已采纳（详见 §12.9 — additive-only `extend`,safe diff `apply`） |
| 2026-05-28 | PDF Change Request triage — `fg.assertions.by_ids(strict=True)` 默认 | 接受 | ✅ 已采纳（详见 §12.2 Layer 3 — 审计路径默认严格,unknown asrt_id 抛错） |
| 2026-05-28 | PDF Change Request triage — `fg.entities.get` 改名 `snapshot` | **拒绝** | ❌ 不采纳 — `get` 已经清晰且跟 `create / where / exists / delete / edit` 统一;`snapshot` 过度暴露返回类型并跟 future `at(t)` snapshot 概念混 |
| 2026-05-28 | PDF Change Request triage — `fg.entities.resolve` get-or-create 便利方法 | **拒绝** | ❌ 不采纳 — `resolve` 语义模糊;真正需要时应叫 `get_or_create` 并定义并发 / 冲突 / `_on_create` 语义。当前 2 行用户层组合够用 |
| 2026-05-28 | PDF Change Request triage — `.active` / `.all` 改名 `.active_assertions` / `.all_assertions` | **拒绝** | ❌ 不采纳 — AssertionView 类型已经在说"这是 assertion 视图";靠类型 + dot-access vs `.field(...)` 路径区分,而非加 redundant 后缀(详见 §12.3 "当前值 vs assertion records 的层次区分") |
| 2026-05-28 | **e_ref 设计方向锁定 X-style typed content-derived hash**(idref_v1 保留)| 接受 | ✅ 已采纳(详见 §4.1 硬定义 1 + §7 + §3.2 GNF 对齐) — Identity 定义为 immutable anchor;typed hash 机械性强制;opaque allocated alternative(Y / ULID)是 valid alternative model 但本轮不选 |
| 2026-05-28 | **Q1 entity_ref 分配策略从 Step 2+ 拉回 Step 1** | 接受 | ✅ 锁定 idref_v1(本轮);ULID alternative 评估后不采纳 |
| 2026-05-28 | **§4.1 重写为 4 条硬定义**(typed constructor / immutable anchor / mutable Field / mirrored Claim)| 接受 | ✅ 已采纳(详见 §4.1)— 4 条互锁,加 1 条 schema 边界规则 |
| 2026-05-28 | **§5.2 INV-7 重写为 INV-7a / 7b / 7c 三子不变量** | 接受 | ✅ 已采纳(详见 §5.2)— anchor immutable + claim mirrored + hash 一致性 |
| 2026-05-28 | **INV-7c Identity Claim ↔ e_ref hash 一致性**(防 dual-truth split)| 接受 | ✅ 已采纳 — Identity Claim 只能 create 写、delete 整批撤销;Layer 1/2/3 全禁止单独改 Identity Claim |
| 2026-05-28 | **Schema 设计边界规则**:未来可能变的值(如 email)不要建模为 Identity | 接受 | ✅ 已采纳(§4.1 边界规则);文档示例 User 改用 `tenant_id` + `user_id` 作 Identity,`email` 放 Field |
| 2026-05-28 | **`fg.entities.ref` 语义**:deterministic typed constructor(不是 lookup)| 接受 | ✅ 已采纳(详见 §12.2 Layer 1 表)— `encode_idref_v1(EntityClass, identity)` 算 e_ref,不查 ledger |
| 2026-05-28 | **`fg.entities.create` 重复语义**:e_ref 已有 active Identity Claim 抛 `EntityAlreadyExistsError` | 接受 | ✅ 已采纳(详见 §12.2 Layer 1 表) — ledger 不做 idempotency,SDK 层负责 |
| 2026-05-28 | **改 Identity 语义**:= `delete + create + 显式数据迁移`;旧 entity Field 不自动继承 | 接受 | ✅ 已采纳(详见 §12.8 改 Identity 语义)— 业务想"rename" 说明该字段不应是 Identity |
| 2026-05-29 | e_ref token 保留 `<EntityType>` 前缀(Q1 token 形态) | 接受 | ✅ 已采纳 — 跟 GNF "typed Thing" 一致;支持 `entities.delete(ref)` 等无 schema 上下文的调用从 token 直接 dispatch 类型;debug 友好 |
| 2026-05-29 | §8.6 关键变更点表加 4 行:`description=` 共通基类提升 / `pattern=` 新增 / `Literal[...]` 枚举支持 / `_DataMember` 基类 | 接受 | ✅ 已采纳 — 补全 Form I 变更点 |
| 2026-05-29 | §9.1 候选 schema syntax 改 Form I + `AlternativeKey` 占位(去除 `Field(role="identity")`) | 接受 | ✅ 已采纳 — 候选 B 残留清除 |
| 2026-05-29 | 时间维度 3 维 future preview:`at(t)` shipped / `during((t_start, t_end))` Step 2+ 默认 overlap / `now` 不进 surface 仅 future alias(determinism 顾虑) | 接受 | ✅ 已采纳(详见 §10.2 future preview) |
| 2026-05-29 | §11.2 (A) PyReason adapter "Relationship 模式" → "Relationship Claim lowering";明确不改 ledger schema、不开 INV-9 例外 | 接受 | ✅ 已采纳 — 适配器措辞精确化 |
| 2026-05-29 | **AssertionView 招纳原则 + 删除 `version()`** | 接受 | ✅ 已采纳(§12.3 + §12.5 Rule 4 + §12.6 类型迁移)— 普通 meta equality 走 where,view 一等方法只授予有特殊行为的能力(revoke / 时间 / asrt_id 索引 / scope 窄化) |
| 2026-05-29 | INV-7c 实施 — 策略 C(application 层 in-memory Identity pred_id set)+ 策略 B(claim_meta tag)拒绝 | 接受 | ✅ 已采纳(§5.2 INV-7c 实施)— claim_meta 不承载 structural truth |
| 2026-05-29 | Schema evolution 不允许 Identity / Field 互转 + Identity 字段新增/删除拒绝 + Identity bundle 重设计走 entity-type 迁移 | 接受 | ✅ 已采纳(§5.2 + §12.9)— 配套 INV-7c 实施策略 C 的关键约束 |
| 2026-05-29 | ledger spec §11.5 同步 INV-7c 策略 C 实施细节(Identity pred_id set + 拒绝 claim_meta tag + schema evolution 配套约束) | 接受 | ✅ 已采纳 — 实现者只读 ledger spec 不会误选 meta tag 策略 |
| 2026-05-29 | `fg.entities.delete` 签名细节(by-identity vs by-ref) | 留 blueprint 决策 | ⏳ Blueprint 首个 API 决策点;不阻塞 pre-blueprint 设计闭合 |

**Step 2+ 待裁定**（Step 2+ 启动时处理）:

| Q | 议题 | 当前推荐参考 | 状态 |
|---|---|---|---|
| ~~Q1~~ | entity_ref 分配策略 | **idref_v1 typed hash 已锁定 Step 1**(详见 §7);ULID alternative 已评估后不采纳 | ✅ Step 1 已处理 — 不再 Step 2+ 待裁 |
| Q3 | 唯一性约束形态 | **Composite 默认 + Multiple alternative 可选** | ⏳ Step 2+ |
| Q4 | 违反唯一性语义 | **(a) reject write** | ⏳ Step 2+ |
| Q5 | Lookup 索引存储 | X-style 下 Identity → e_ref 直接算无需反向索引;Field 反向走 `idx_claims_pred_value`;**专用索引视 Step 2+ 性能需要再加** | ⏳ Step 2+ 视性能 |
| Q6 | 历史 / as-of lookup 语义 | **(a) 仅当前 active 默认**;as-of 留 future | ⏳ Step 2+ |
| Q-PR1 | PyReason edge n-ary 冲突 | **(A) Relationship 模式 rewrite** | ⏳ Step 2+ adapter rewrite slice |

---

## §16 关联文档与代码锚点

### §16.1 关联 design-points

- [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) — ledger 数据格式终态 + INV-1 至 INV-15 + 7 条数据精简 migration
- [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) — append-only 范式 10 维度评估;**G1 原标题"content-hash identity anti-pattern"需要重新措辞**(详见 §14.2)— 本轮选择 typed content-derived hash;本 doc 解决的是 identity 用完即扔问题(identity 不作为 first-class queryable Claim),不是 hash 机制本身
- `archive/identity-and-data-model-redesign.zh.md` — 本 doc 与 ledger spec 的前身 umbrella doc ⏳ 计划本批次归档

### §16.2 关联 workflow 工件

- [`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md) — INV-6 的形式来源

### §16.3 代码锚点

- [`src/factgraph/core/protocol/idref_v1.py`](../../../../src/factgraph/core/protocol/idref_v1.py) — entity_ref 编码协议(SHA-256 hash of canonical Identity bundle);**Step 1 锁定**(详见 §7);需扩展为 Identity-as-Claim 写入的 canonical 输入来源(§4.1 硬定义 1 + INV-7b/c 的实现承载)
- [`src/factgraph/sdk/schema.py`](../../../../src/factgraph/sdk/schema.py) — `Entity` / `Field` / `Identity` 描述符（Form I 锁定后将重构;详见 §8）
- [`src/factgraph/sdk/facade.py`](../../../../src/factgraph/sdk/facade.py) — `EntitySnapshot` / `AssertionNamespace` / `FieldAssertions` / `AssertionRecordSet`（AssertionView 统一后前两者删除;详见 §12.3）
- [`src/factgraph/sdk/store.py`](../../../../src/factgraph/sdk/store.py) — `_SDKReadManager` / `_SDKWriteManager` / `_SDKAssertionsManager`（三层分层重组后改名为 entities / fields / assertions managers;详见 §12.2）
- [`src/factgraph/adapters/pyreason/accept.py`](../../../../src/factgraph/adapters/pyreason/accept.py) `_edge_rest_terms` — Q-PR1 重写点（Step 2+）

### §16.4 外部启蒙

- Relational.ai Graph Normal Form（GNF）：Things-not-Strings + Indivisibility of Facts
  - 用户 obsidian 笔记 `symb-Intelli./design/06-基于Rel的语法调整.md`
  - 用户 obsidian 笔记 `wiki/pdfs/Data modeling - Graph Normal Form - RAI Documentation.pdf`
- ULID 规范:[ULID Spec](https://github.com/ulid/spec) — Q1 推荐方案的参考
- pydantic v2 `model_config` 命名空间保留模式 — `_meta` 设计的灵感
- **PDF Change Request for FactGraph 2026-05-28** — `docs/references/working/change-requests-2026-05-27/` 用户提供的 UX 改进建议;Rule 之前的 Schema / Read-write / Assertions 三章经 §15 决策日志中 PDF triage 6 项裁定;Rule 之后章节(Rules / Inferences / Semantics / Evidence / Persistence)Step 2+ 评估

---

## §17 当前批次完成状态

### Step 1 lock-in（本批次）

- [x] 单文件 design-point 创建于 `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
- [x] 6-field metadata header + alpha 状态说明
- [x] §1 目的与范围 / §2 当前现状 / §3 动机
- [x] §4 设计承诺与心智模型（4 条承诺 + 与 GNF 原则对齐审查）
- [x] §5 Identity-specific 不变量（INV-6, INV-7;INV-8 alpha 下消解）
- [x] §6 设计空间总览（Q1-Q6 + Q-PR1）
- [x] §7 Q1 entity_ref 分配策略(**idref_v1 typed content-derived hash 锁定**;opaque allocated alternative 评估后不采纳)
- [x] §8 Q2 Schema 声明 — **Form I 锁定**（Step 1）
- [x] §9 Q3 + Q4 唯一性 — Step 2+ 延后（保留为参考）
- [x] §10 Q5 + Q6 Lookup + 历史 — Step 2+ 延后（保留为参考）
- [x] §11 Q-PR1 Adapter — Step 2+ 延后（保留为参考）
- [x] §12 API 表面分层 + AssertionView 统一 — **Step 1 锁定**
- [x] §13 Step 1 范围 + 延后清单
- [x] §14 与姊妹 doc 的关系
- [x] §15 决策日志（Step 1 决策 8 条 + PDF triage 决策 6 条 + Step 2+ 待裁定 6 条）
- [x] §16 关联文档与代码锚点
- [x] §17 当前批次完成状态（本节）

### PDF Change Request 2026-05-28 triage（追加批次）

Rule 之前的 Schema / Read-write / Assertions 三章 PDF 建议逐项 triage 完成,采纳 3 项 + 拒绝 3 项,均记录于 §15 决策日志:

- [x] **采纳** `Identity(..., pattern=r"...")` → §8.5 `_DataMember.pattern`(Step 1 共通字段)
- [x] **采纳** `fg.schema.add` 拆 `register / extend / apply` → §12.9 Schema namespace operations
- [x] **采纳** `fg.assertions.by_ids(strict=True)` 默认 → §12.2 Layer 3 spec
- [x] **拒绝** `fg.entities.get` → `snapshot` rename(已锁定 `get`)
- [x] **拒绝** `fg.entities.resolve` get-or-create(用户层组合够用)
- [x] **拒绝** `.active` / `.all` → `_assertions` 后缀(类型本身已消歧;详见 §12.3)
- [x] PDF 中 Rules / Inferences / Semantics / Evidence / Persistence 章节(Rule 之后)**不纳入本批次** — 与本次 identity + API 表面 slice 正交;Step 2+ 评估

### X-style 锁定 + 4 条硬定义批次(2026-05-28)

针对 e_ref 方向的根冲突(§4 / §5 / §8 / §12.8 之间)做了系统性修订,锁定 X-style typed content-derived hash 路线;共 10 条决策记录于 §15:

- [x] **§3.1 三条不满重新审视** — #1 (hash 单向) 可接受为 GNF 合理实现;#2 #3 真痛点 Step 1 解决
- [x] **§3.2 GNF 启蒙重写** — Things-not-Strings 已实现(typed Thing);Step 1 增量是 identity-as-facts;Bombay → Mumbai 靠 schema 设计(name 放 Field)
- [x] **§4.1 重写为 4 条硬定义 + 边界规则**(typed constructor / immutable anchor / mutable Field / mirrored Claim)
- [x] **§4.1 对 alternative 模型的非否定性引用** — Opaque allocated(ULID 等)是 valid alternative,本轮不选,不评判"不符合 GNF"
- [x] **§4.2 / §4.3 同步更新** — 4 条定义 → INV / Q 映射 + GNF 对齐审查
- [x] **§5.2 INV-7 重写为 7a / 7b / 7c 三子不变量** — anchor immutable + claim mirrored + hash 一致性
- [x] **§7 Q1 锁定 idref_v1** — Step 2+ 不再延后;ULID alternative 评估后不采纳
- [x] **§8.3 schema 示例更正** — email 改为 Field(可变);user_id 作 Identity(immutable)
- [x] **§8.3 行为契约表** — Identity 列加"是否可修改"维度;描述清楚 immutable
- [x] **§12.2 Layer 1 表** — `create` `EntityAlreadyExistsError` 触发条件明确;`ref` 是 deterministic typed constructor 不是 lookup
- [x] **§12.8 重写** — Identity 三层全禁止修改;INV-7c rationale + 改 Identity 语义(delete+create+迁移)
- [x] **§13.1 Step 1 in-scope 扩展** — 加 Q1 锁定 / INV-7a/b/c / 边界规则 / 改 Identity 文档化
- [x] **§13.2 Step 2+ 调整** — Q1 移除;Lookup 索引说明改为"X-style 下不需要反向索引"
- [x] **§15 决策日志加 10 条 X-style 锁定决策**
- [x] **示例 sweep** — §12 内 `fg.read.get(User, email=...)` 等示例改为 `tenant_id + user_id`

### Consistency pass(2026-05-29 追加)

旁系章节残留扫除 — agent 评估抓到 9 处 identity doc 残留 + 5 处 ledger spec 不同步:

**Identity doc(9 处全部清理)**:
- [x] Header Scope / Design intent — 去"entity_ref opaque 化" / "lookup 索引";改为"typed content-derived (idref_v1)" / "Field 反向查询"
- [x] §3.1 #1 — "反向 lookup 通过反向索引"改为更精确措辞(get/ref 走 hash,where 走 Claim 索引)
- [x] §8.5 `pattern` 来源 — 去"我们的 e_ref 是 opaque ULID";改为 "校验字段值,不校验 idref_v1 token"
- [x] §9.2 INV-7 引用更新为 INV-7a/c
- [x] §10 Q5+Q6 — 加 X-style 重要澄清:Identity → e_ref deterministic hash,无需 lookup 索引;Field/alias 反向查询走 `idx_claims_pred_value`
- [x] §14.1 — `erf_v1:` → `idref_v1:`;"identity 变更 = revoke + append" 重写为 Field/Identity 分别走不同路径
- [x] §14.2 — G1 anti-pattern 措辞反转(本轮选择 content-derived,不是"解决"它)
- [x] §16.1 — G1 anti-pattern 同步反转
- [x] §16.3 — idref_v1.py 描述重写(Step 1 锁定,非"将被 ULID 替代")
- [x] §17 checklist — "ULID 推荐 Step 2+" → "idref_v1 锁定"

**Ledger spec(5 处全部同步)**:
- [x] §8.3 读取流程 — `fg.read.snapshot` → `fg.entities.get`;明确 `idref_v1(EntityType, identity)` 算 e_ref 不走反向索引
- [x] §8.4 — `active_assertions.where(source=)` → `.active.where(_meta={})` 新 API
- [x] §3.1 — `:exists` 标 **legacy / transitional**,non-Step-1-终态
- [x] §11.5 上层 API 映射 — 全面更新:create 含 INV-7c rationale;delete 是允许 retract Identity 的唯一路径;fields.* / assertions.retract 都加 Identity 字段拒绝注;末尾加 INV-7c ledger 层约束说明
- [x] §4 总览更新 — INV-7 改为 INV-7a/b/c;INV-8 消解状态明确

**Final keyword 检查** — 关键词 `opaque` / `ULID` / `erf_v1` / `active_assertions` / `fg.read.snapshot` / `identity 变更` / `:exists` / `anti-pattern` 全部检视:
- 残余出现位置均在 "alternative / legacy / rejected / transitional" 语境中
- 无主线论证残留

### Q1-Q7 用户审查批次(2026-05-29 追加)

用户 review 完 consistency pass 后提出 7 个深度问题,7 项全部 lock-in,落入 §15 决策日志 9 条:

- [x] **Q1** e_ref 保留 `<EntityType>` 前缀 — 跟 GNF typed Thing 一致;支持无 schema 上下文的 dispatch
- [x] **Q2** §8.6 关键变更点表加 4 行 — description/pattern/Literal/_DataMember
- [x] **Q3** §9.1 候选 schema syntax 去 `Field(role="identity")`;改 Form I + `AlternativeKey` 占位
- [x] **Q4** §10.2 加 at/during/now 3 维度 future preview;`during` 默认 overlap;`now` 仅 future alias 不进 surface(determinism 顾虑)
- [x] **Q5** §11.2 (A) PyReason adapter 措辞精确化 — "Relationship Claim lowering",不改 ledger schema
- [x] **Q6** AssertionView 招纳原则确立 + 删除 `version()` 一等方法;§12.3 / §12.5 / §12.6 / §12.7 同步
- [x] **Q7** INV-7c 实施策略 C(application 层 Identity pred_id set)+ schema evolution 不允许 Identity/Field 互转;§5.2 + §12.9 同步

**应用文档同步**(Step 2+ 时):
- [x] Slice 4 Step 2: `docs/official/kernel/quickstart/assertions.md` `.version(v)` 一等方法删除,改 `.where(_meta={"version": v})`
- [ ] `docs/official/kernel/quickstart/assertions.md` 时间维度章节加 `during` future preview

### 进入 blueprint 前的最后待决点(2026-05-29)

| 待决点 | 现状 | Blueprint 首个决策处理 |
|---|---|---|
| **`fg.entities.delete` 签名** | 本 doc §12.2 Layer 1 表 + ledger spec §11.5 均用 `delete(EntityClass, **identity)`;§12.8 改 Identity 语义示例用 `delete(old_ref)`(by e_ref token) | 是否同时支持 by-identity 和 by-ref 两种重载?推荐:`delete(EntityClass, **identity)` 主入口 + `delete_by_ref(e_ref)` 辅助入口(明确两种心智);或单一签名 + `EntityClass.from_ref(e_ref)` 解析。Blueprint 期裁定 |

**Pre-blueprint 状态**:
- 设计文档主线论证已闭合(§3-§13 全部一致)
- 旁系章节(§14-§16)已 consistency pass 清理
- 关键词 keyword scan 通过
- INV-7c 策略 C 在 identity doc + ledger spec 双向同步
- 剩余 ambiguity 仅在 `fg.entities.delete` 签名 — 留 blueprint 期决策

### Next steps（本批次外）

- [x] 同步 `ledger-schema-specification.zh.md`(修 `:__exists__` → `:exists`;末尾加上层 API 映射 pointer 到 §12)
- [x] 归档原 `identity-and-data-model-redesign.zh.md` 到 `archive/`
- [ ] Step 2+ 启动时回看 §9 / §10 / §11 推荐 + §13.2 延后清单 + §15 待裁定 Q1/Q3-Q6/Q-PR1
- [ ] PDF Rule 之后章节(Rules / Semantics / Evidence / Persistence)在 Step 2+ rule 重设计 slice 评估
