# Ledger 数据格式 Specification

- Status: working / specification v2（claim-first immutable payload model）
- Authority: candidate design / non-authoritative reference; not current implementation truth
- First draft: 2026-05-27
- Last updated: 2026-06-02(§10 联动节加入)
- Scope: FactGraph ledger 数据格式终态 — 表 schema、SQL canonical 编码契约、digest path 纪律、structural 不变量族、数据精简 migration 路径
- Parent: 取代 `identity-and-data-model-redesign.zh.md`(之前的 umbrella doc,已或即将归档);与 `append-only-ledger-evaluation.zh.md`(背景评估)配套
- Co-roadmap: [`factgraph-storage-architecture-evolution.zh.md`](factgraph-storage-architecture-evolution.zh.md) — lifecycle 收敛 + SQL 读路径 + lazy eval 演化路线;本 design-point 的 Slice 3b 实施 = 该 essay Stage A 完成后启动(详见 §10)
- Design intent: 锁定 ledger 数据格式终态,作为下游实现/测试/migration 的契约源头;与 Identity 重设计 doc 解耦

## 目录

```text
§1   目的与范围
§2   演化总览(current 7-table → claim-first 3-table)
§3   表结构(claims / claim_meta / ledger_meta)
§4   结构性不变量(12 条)
§5   SQL value 列 canonical 编码契约
§6   Digest path 纪律
§7   Implementation discipline
§8   写入 / 读取 / 撤销 / 更新 / 删除流程概览
§9   数据精简 migration 路径(7 条)
§10  与 storage-architecture-evolution 的联动 / migration 时机
§11  决策日志
§12  关联文档与代码锚点
§13  当前批次完成状态
```

---

## §1 目的与范围

### §1.1 这份 spec 是什么

- FactGraph ledger 数据格式的**单一权威 specification**
- 锁定 schema 终态、编码契约、digest path 纪律、structural 不变量族
- 数据精简 migration 1-7 的 delta 清单
- 下游实现(write protocol / SDK / adapters)必须遵循的契约源头

### §1.2 这份 spec 不是什么

- ❌ 不是 Identity 重设计文档(entity_ref 形态、Identity-as-Claim 镜像、GNF 落地、Field 反向查询等议题在 `identity-mechanism-redesign.zh.md`)
- ❌ 不是 append-only ledger 范式评估(10 维度 best practice 比较在 `append-only-ledger-evaluation.zh.md`)
- ❌ 不是当前实现真相(current behavior in `src/factgraph/*/docs/`;本 spec 是**目标**形态)
- ❌ 不规定具体 migration 工具实现(blueprint 期任务)

### §1.3 与姊妹 doc 的关系

| Doc | 角色 |
|---|---|
| **本 doc** | 数据格式终态 spec + structural 不变量 + migration 路径 |
| **`identity-mechanism-redesign.zh.md`** | entity_ref 形态(idref_v1 typed content-derived hash 锁定)+ Identity-as-Claim 镜像 + GNF 落地 + identity-specific 不变量(INV-6 / INV-7a/b/c;INV-8 消解)+ Field 反向查询设计 |
| **`append-only-ledger-evaluation.zh.md`** | append-only 范式 10 维度 evaluation + future gap 识别(GDPR / bitemporal / compaction 等) |

三 doc 互补不重叠。Identity doc 依赖本 doc 的 schema 终态;evaluation doc 是两者的 background context。

---

## §2 演化总览

### §2.1 当前形态(7 张表)

来源:[`src/factgraph/core/store/ledger.py`](../../../../src/factgraph/core/store/ledger.py) `_DDL` 常量 + [`src/factgraph/core/docs/01_architecture.en.md §4`](../../../../src/factgraph/core/docs/01_architecture.en.md)。

```text
[数据表 5 张]
  claims          (seq, asrt_id, pred_id, e_ref, rest_terms TEXT)
  claim_args      (id, asrt_id, idx, val_atom, tag)
  meta_rows       (id, asrt_id, key, kind, value)
  annotation_rows (id, asrt_id, namespace, category, key, kind, value, origin, derivation)
  revokes         (id, revoker_asrt_id, revoked_asrt_id)

[Infra 表 2 张]
  ingest_keys     (ingest_key, asrt_id, kind)
  ledger_meta     (key, value)
```

### §2.2 终态形态(claim-first,3 张表)

```text
[数据表 2 张]
  claims      (seq, asrt_id, pred_id, e_ref, value, value_tag)
  claim_meta  (asrt_id, key, value)                       ← 复合 PK (asrt_id, key); 3 列

[Infra 表 1 张]
  ledger_meta (key, value)
```

**7 → 3 张表**。变化通过 §9 中的 7 条数据精简实现。

### §2.3 关键设计承诺

> **Alpha 阶段说明**:FactGraph 当前处于 **alpha 版本状态**,**无生产数据 / 已发布版本的兼容性负担**。所有 schema 变更、migration、wire format 演化都按"代码 + schema 一次性重构"处理,不需要数据搬迁工具、跨版本 reader dispatch、view snapshot 兼容层等。下面所有承诺都在此前提下设计。

- **ledger 不承担 idempotency 责任**:write 不做 content dedup;同内容多次写入产生多个独立 asrt_id;idempotency 由上层 API/SDK policy 处理
- **Meta 是 claim 不可变 payload 的一部分**:`claim_meta` 行随 claim 一同写入;写入后**immutable**;meta 变更 = revoke 旧 claim + append 新 claim(含新 meta)— 不允许 in-place meta update
- **Ledger 仅有 2 个原语**:`append claim` + `append revoke claim`。SDK 暴露的 `update` / `delete` 是这两个原语的组合糖
- **撤销 = 特殊 pred Claim**(精简 3):`pred_id="__system__.revokes"` 进 claims,不再有独立 revokes 表
- **每条 Claim 是 unary fact**(INV-9):rest_terms list 退场,value + value_tag 双列 inline
- **claim_meta 复合 PK + 全 TEXT value**:`(asrt_id, key)` 是唯一身份;value 永远 TEXT,特殊 key 格式由 META_KEY_REGISTRY 规定(详见 §5.3)
- **`__system__.*` pred_id 命名空间预留**(INV-10):user-facing 写入路径必须拒绝
- **存在性断言**用 `<EntityType>:exists` 形态(per-entity-type 约定)— **不属于** `__system__.*` 命名空间;**Step 1 后实质冗余**(Identity 镜像 Claim 即"该 entity 存在"证据);保留为 **legacy / transitional emission**,Step 2+ 评估完整废除(详见 §3.1)

---

## §3 表结构

### §3.1 `claims` — 事实主表

```sql
CREATE TABLE claims (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  asrt_id    TEXT NOT NULL UNIQUE,
  pred_id    TEXT NOT NULL,
  e_ref      TEXT NOT NULL,
  value      TEXT,                  -- nullable: 0-arity 时 NULL(如 exists)
  value_tag  TEXT                    -- nullable: 同 value 同步
);

CREATE INDEX idx_claims_pred_eref ON claims(pred_id, e_ref);
CREATE INDEX idx_claims_e_ref     ON claims(e_ref);                 -- 跨 pred 按 entity 查
CREATE INDEX idx_claims_pred_value ON claims(pred_id, value);        -- identity lookup
CREATE INDEX idx_claims_revokes ON claims(value)
  WHERE pred_id = '__system__.revokes';                              -- 撤销查询优化
```

| 列 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `seq` | INTEGER | PRIMARY KEY AUTOINCREMENT | 物理写入序载体(SQLite rowid alias);`ORDER BY seq` = 按写入时间遍历 |
| `asrt_id` | TEXT | NOT NULL UNIQUE | **逻辑 PK** / 全 ledger join 根;UUID4 hex 形式(INV-2)|
| `pred_id` | TEXT | NOT NULL | 谓词标识;schema 层约定,`__system__.*` 前缀预留(INV-10)|
| `e_ref` | TEXT | NOT NULL | 主语 entity ref(详见 `identity-mechanism-redesign.zh.md`)|
| `value` | TEXT | NULLABLE | 事实 value 的 SQL canonical 编码;NULL = 0-arity(详见 §5.1)|
| `value_tag` | TEXT | NULLABLE | value 的 canonical 类型 tag(8 种之一);与 value 同步 NULL/非 NULL |

#### Claim 形态枚举

| 形态 | pred_id 形式 | value | value_tag | 备注 |
|---|---|---|---|---|
| 普通 value field | `<EntityType>:<field_name>` | 非 NULL canonical text | 8 种 tag 之一(非 `entity_ref`)| `("Alice", "string")` |
| Entity-ref field | `<EntityType>:<field_name>` | 非 NULL ref string | `"entity_ref"` | `("idref_v1:User:bob...", "entity_ref")` |
| Multi-cardinality 每一项 | `<EntityType>:<field_name>` | 同上 | 同上 | 多 row,相同 pred_id + e_ref;不同 asrt_id |
| Existence 断言(**legacy / transitional**) | `<EntityType>:exists`(per-entity-type) | NULL | NULL | **不是** `__system__.*`;Step 1 后实质冗余(Identity Claim 已是存在性证据) |
| Revoke claim | `__system__.revokes`(reserved system)| 被撤销 asrt_id 字符串 | `"string"` | e_ref = 被撤销 claim 的 e_ref |

#### 命名空间边界(重要)

ledger 中 pred_id 有 **两类预留约定**,作用范围不同:

| 预留 | 形态 | INV-10 拒绝? | INV-15 默认 filter? |
|---|---|---|---|
| `__system__.*`(顶级 system namespace)| `__system__.revokes`, `__system__.*` future | ✅ user 写入路径拒绝 | ✅ 普通 SDK 读取表面默认 filter |
| `<EntityType>:exists`(**legacy / transitional** per-entity-type 存在性)| `User:exists` 等 | ✅ user 不能直接构造;Step 1 后 `fg.entities.create` **optional transitional emission**(可继续 emit 兼容旧 reader,也可不 emit — Identity Claim 已替代) | ❌ 不 filter |
| `<EntityType>:<field_name>`(普通 field,**含 Identity 镜像 Claim**)| `User:name` / `User:tenant_id` 等 | 用户正常 path(Identity 字段写入受 [identity §5.2 INV-7c](identity-mechanism-redesign.zh.md) 限制 — 仅 entities.create 写、entities.delete 整批 retract,不允许单独修改) | ❌ 不 filter |

> **重要**(Step 1 后 `:exists` 的状态):[`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) §4.1 硬定义 4 + INV-7b 锁定后,Identity 字段在 `fg.entities.create` 时**强制**同时产生镜像 Claim — Identity Claim 本身即"该 entity 存在"的证据。`<EntityType>:exists` Claim 在 Step 1 后**实质冗余**;本 spec 当前保留 `:exists` 形态作为 **legacy compatibility / optional transitional emission**(不作为 Step 1 终态 truth)。Step 2+ 评估完整废除时机。

### §3.2 `claim_meta` — Claim 不可变 payload 中的 meta

```sql
CREATE TABLE claim_meta (
  asrt_id  TEXT NOT NULL,
  key      TEXT NOT NULL,
  value    TEXT NOT NULL,
  PRIMARY KEY (asrt_id, key)
);

CREATE INDEX idx_claim_meta_key_value ON claim_meta(key, value);     -- meta 过滤查询
CREATE INDEX idx_claim_meta_asrt      ON claim_meta(asrt_id);         -- 按 claim 取所有 meta
```

| 列 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `asrt_id` | TEXT | NOT NULL, 复合 PK 一半 | 关联到 `claims.asrt_id` — 这条 meta 所属的 claim |
| `key` | TEXT | NOT NULL, 复合 PK 一半 | meta key(如 `source`、`trace_id`、`bound`) |
| `value` | TEXT | NOT NULL | meta value 的 SQL canonical text 编码(格式由 META_KEY_REGISTRY 规定,见 §5.3)|

#### 关键设计点

- **复合 PK `(asrt_id, key)` 是 meta 行的真正身份**;不引入 surrogate `id` 列
- **没有 `value_tag` 列**:所有 value 都是 TEXT;特殊格式由 META_KEY_REGISTRY(§5.3)规定。默认(用户自定义 key)= string
- **没有 `origin` 列**(observed / derived):如未来需要区分 origin,encode 为额外 meta key(如 `meta_origin: "derived"`),不作为 schema 字段
- **写入语义**:claim_meta 行随 claim 一同写入(同一 SQLite transaction,INV-3);写入后 immutable。因为每条 claim 有独立 asrt_id(INV-2 全局唯一),`PRIMARY KEY (asrt_id, key)` 永远只被插入一次,不会触发 UPDATE/REPLACE 路径
- **变更 meta 不通过修改 claim_meta**:要"改 meta"必须 revoke 整个 claim + append 新 claim with 新 meta(详见 §8.5)

### §3.3 `ledger_meta` — 全局配置

```sql
CREATE TABLE ledger_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

存 ledger 全局配置(**非 per-assertion**):

- `schema_digest` — 当前 schema IR 的 digest
- `ledger_format_version` — ledger schema 版本号
- `migration_version` — 上次成功 migration 的版本
- `db_id` — ledger 实例唯一 ID(用于跨 ledger 区分)
- 等

### §3.4 与现有 7 张表的取消列表

完全消失的表:

- `claim_args`(数据精简 4)— rest_terms list 内联到 claims.value + value_tag 后,行展开冗余
- `meta_rows`(数据精简 1+5)— 与 annotation_rows 合并并改名为 `claim_meta`
- `annotation_rows`(数据精简 1+2+5)— 同上;连带 `namespace` / `category` / `derivation` / `origin` / `kind` 列消失
- `revokes`(数据精简 3)— 撤销变成特殊 pred Claim 进 claims
- `ingest_keys`(数据精简 6)— ledger 不做 idempotency;移到上层 API 责任

---

## §4 结构性不变量

12 条 ledger 数据格式的**必守约束**。这是本 spec 的核心契约层。

### §4.1 INV-1:Append-only ledger

> 任何"删除"或"修改"通过新 assertion 实现,原行永不就地修改。

**适用范围**:claims / claim_meta 两张数据表的写入路径。

**含义**:
- 撤销 = 写新的 `__system__.revokes` Claim(INV-11);不就地标记 active 列
- claim_meta 行写入后 immutable — 因为 `(asrt_id, key)` 复合 PK 上每个 asrt_id 都是全局唯一(INV-2),同一 (asrt_id, key) 在写入后永不会再 INSERT,不会触发 UPDATE/REPLACE 路径
- Meta 变更不是改 claim_meta,而是 **revoke + append 新 claim with 新 meta**(详见 §8.5)
- `ledger_meta` 是 infra 配置层(非 claim 数据),允许就地修改(如更新 schema_digest);与 INV-1 共存的合理例外

### §4.2 INV-2:asrt_id 全局唯一

> 每条 ledger 写入(包括撤销)对应一个 UUID4 hex 形式的 asrt_id;所有附加数据(claim_meta、未来 audit annotation 等)以 asrt_id 为关联键。

**适用范围**:claims / claim_meta 的 asrt_id 列。

**含义**:
- 同内容多次写入产生**多个不同 asrt_id**(ledger 不做 dedup);这是 audit 完整性的代价 / 收益
- asrt_id 是逻辑 PK;`seq INTEGER PRIMARY KEY` 是物理 SQL PK(性能优化)
- claim_meta 的 (asrt_id, key) 复合 PK 借力 INV-2 — 因为 asrt_id 唯一,复合 PK 永远只被 INSERT 一次,从根上排除 UPDATE 路径

### §4.3 INV-3:SQLite 单事务原子写

> 一个 user-level 写入(如 `fg.fields.set`)= 一个 SQLite transaction,原子跨表写入 claims + claim_meta。

**含义**:
- 不能出现"claims 写了但 claim_meta 没写"的部分态
- revoke claim 同样原子(写 1 行 claims with `__system__.revokes` + 0~N 行 claim_meta,单事务)
- SDK update 操作(revoke + append)必须在**单一 SQLite transaction** 内完成(详见 §8.5)
- 这是 INV-1 + INV-5 实施的底层保证

### §4.4 INV-4:协议层 tup_v1 字节级 canonical 设计稳定

> `tup_v1.py` 的 8 种 canonical tag(`string` / `int` / `float64` / `bool` / `bytes` / `time` / `uuid` / `entity_ref`)集合作为本设计周期内的稳定协议;在没有强力新需求的前提下,集合不增减、字节编码格式不变。

**适用范围**:[`canonical_bytes_tup_v1`](../../../../src/factgraph/core/protocol/tup_v1.py) 协议层。

**理由**:
- alpha 阶段虽然没有"已发布版本兼容"硬约束,但 tup_v1 作为跨语言字节级协议,稳定性本身就有工程价值(避免每次设计 iteration 都重做 encoder/decoder)
- 当前 8 个 tag 已经覆盖事实存储的所有常见类型需求 — 没有发现需要新 tag 的场景

**含义**:
- entity_ref 形态本轮锁定 `idref_v1`(详见 identity-mechanism-redesign §7);若未来评估其他 tag value 字符串格式,只是该 tag 的 value 字符串格式变化,不动 tag 集合
- claims/revokes 统一不破 INV-4:revoke Claim 的 value 用 `string` tag 承载 asrt_id,无需新 tag
- ledger 写入永远 length 0 或 1(INV-9),但协议保留 variable-length 编码能力 — ledger 比协议更严格
- claim_meta value 不走 tup_v1(claim_meta value 全 TEXT,格式由 META_KEY_REGISTRY 规定 — 与 protocol 层独立)
- alpha 阶段如果出现真实需要新 tag 的场景,可重新评估 — 不是不能动,而是默认不动

### §4.5 INV-5:Ledger 是 source of truth

> SQLite 表是 truth;in-memory indexes、active sets、derived state 都可在启动时从 ledger 重建。

**含义**:
- in-memory `_revoked_asrt_ids` set 是 INV-13 公式的投影 cache
- 任何"加 active flag" / "加 derived 状态表"违反 INV-5
- ledger 是灾难恢复的 anchor

### §4.6 INV-9:Ledger Claim 是 unary fact

> 每条 `claims` row 严格表达 `(asrt_id, pred_id, e_ref, value?, value_tag?)` 的 unary 关系。n-ary 计算(Rule head 派生多 arity 事实等)仅存在于 in-memory evaluate 阶段;写入 ledger 必经过 unary 投影。

**适用范围**:`claims` 表 + `set_field` / `add_field` / `retract_by_asrt` 写入路径。

**含义**:
- N-ary predicate(如 Datalog rule head `parent(alice, bob)`)必须 reify 为 entity-ref Field 或 Relationship 实例后再写入
- `tup_v1` 协议仍保留 length>1 编码能力(INV-4 不变),但 ledger 写入永远只产生 length 0 或 1
- 显式关闭 Datalog-style n-ary fact 作为 ledger 一等公民的留口

**Adapter 边界责任**:原生模型为 n-ary 的 adapter(如 PyReason edge 的 `(source, target)` 2-position 形态)必须在 adapter → ledger boundary reify 为 Relationship 实例或多个 unary Claim — 详见 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) Q-PR1。

### §4.7 INV-10:`__system__.*` pred_id 命名空间预留

> 任何 user-facing 写入路径必须拒绝 `pred_id` 以 `__system__.` 开头的写入。该命名空间仅 ledger 内部机制可使用。

**适用范围**:`fg.fields.set` / `fg.fields.add` / `fg.schema.ingest` / application 层写入门面。internal API(如 `retract_by_asrt`)走分离路径绕开 namespace check。

**与 `<EntityType>:exists` 的边界区分**:
- `__system__.*` 是**顶级 system namespace**(如 `__system__.revokes`),ledger 内部机制专用,INV-15 默认 filter
- `<EntityType>:exists` 是 **legacy / transitional** per-entity-type 存在性预留 suffix(Step 1 后实质被 Identity 镜像 Claim 替代);仍属于 entity 的真实属性,user 不能直接构造,`fg.entities.create` 可选择间接 emit(兼容旧 reader);INV-15 不 filter

详见 §3.1 命名空间边界表。

### §4.8 INV-11:Revoke claim payload shape 固定

> Revoke claim 在 ledger 中的形态严格为:
> - `pred_id` = `"__system__.revokes"`
> - `e_ref` = 被撤销 fact 的 e_ref(便于按 entity 查撤销)
> - `value` = revoked_asrt_id 字符串
> - `value_tag` = `"string"`
> - `claim_meta` 与普通 claim 同样支持(如 `source`、`trace_id`、`note` 等记录撤销原因)

### §4.9 INV-12:Revoke target 约束(v1 严格)

> Retract 操作的 target asrt_id 必须:
> 1. 存在于 ledger
> 2. target 必须是**非 system claim**(pred_id 不以 `__system__.` 开头)

**理由**:
- 禁止 revoke system claim 防止"revoke-of-revoke = 重新激活"语义
- 第一版严格;reactivation / correction-of-correction 是独立未来设计议题

**注**:存在性断言(`<EntityType>:exists`)**可以**被 revoke(撤销 = entity 被删除)— 因为它不是 `__system__.*` namespace。

### §4.10 INV-13:Active projection 单一公式

> active factual claims 计算遵循唯一公式:
>
> ```
> active factual claims =
>     {c ∈ claims : c.pred_id NOT LIKE '__system__.%'}
>   MINUS
>     {c.value : c ∈ claims AND c.pred_id = '__system__.revokes'}
> ```
>
> 不允许引入第二 active 信号(soft flag 列、独立 active 表等)。

**关键收紧**:公式严格 scope 到 **factual claims**(含 `<EntityType>:exists`);system claims 自身的 active 状态不混入事实语义。

### §4.11 INV-14:Revoke 幂等性行为契约

> 重复 `retract_by_asrt(target_asrt_id)` 同一 target 必须**返回既有 revoker_asrt_id**,不产生第二条 revoke 记录。

**实现机制**:given target X, 查找现有 active Claim 满足 `pred_id="__system__.revokes" AND value=X`;找到则返回该 asrt_id,否则创建新 revoke Claim。

**与 ledger 整体非幂等政策的协调**:
- ledger 不在 assertion 层做 content dedup(同内容多次写产生多个 asrt_id)
- 但 retract 因语义需要保留幂等 — 这是 retract-specific 行为契约,不矛盾
- 普通 set/add 由 caller / SDK / API 层管理 idempotency

### §4.12 INV-15:普通查询默认 filter system claims

> 普通 SDK 读取 API 默认查询结果不包含 system claims(`pred_id LIKE '__system__.%'` 者)。需要看 system claim 走 `fg.audit.*` 专用 API。

**SQL 实现**:`WHERE pred_id NOT LIKE '__system__.%'` 作为默认 filter(与 INV-13 公式左半边一致)。

**注**:`<EntityType>:exists` claims 不属于 system claims,**默认不被 filter**。存在性是 entity 的真实属性。

### §4.13 不变量分类

12 条不变量按性质:

| 类别 | INV |
|---|---|
| FactGraph 长期承诺(跨 spec 有效)| INV-1 / INV-2 / INV-3 / INV-5 |
| 当前实现版本约束(v0.3+ 可重评估)| INV-4 |
| 议题特异约束(claim-first immutable payload 终态特异) | INV-9 / INV-10 / INV-11 / INV-12 / INV-13 / INV-14 / INV-15 |

INV-6(application-first runtime authority)/ INV-7a/b/c(Identity = immutable Claim-mirrored anchor + Claim ↔ e_ref hash 一致性)/ ~~INV-8~~(原 idref_v1 兼容,2026-05-28 后因 idref_v1 锁定 Step 1 而消解)是 **identity-specific 不变量**,在 [`identity-mechanism-redesign.zh.md §5`](identity-mechanism-redesign.zh.md) 中。**INV-7c 对 ledger 层有直接约束** — Identity Claim 不允许通过 `fg.assertions.retract(asrt_id)` 单独撤销,只能走 `fg.entities.delete` 整批路径(详见 §11.5 上层 API 映射)。

---

## §5 SQL value 列 canonical 编码契约

### §5.1 `claims.value` 列编码(8 种 canonical tag)

`claims.value` 的编码由 `claims.value_tag` 决定。与 `tup_v1.py` 字节级 canonical 互可转换,但 SQL 层用人类可读 + 可计算的 text 形式:

| value_tag | SQL `value` 列编码 | 与 tup_v1 字节关系 |
|---|---|---|
| `string` | UTF-8 text 原文 | 相同形式(UTF-8 bytes)|
| `int` | normalized decimal text(如 `"42"`、`"-7"`) | 相同形式(decimal ASCII,与 `_int_to_canonical_text` 对齐)|
| `float64` | finite shortest round-trip decimal(详见 §5.4)| 不同形式(IEEE 754 raw 8 字节 big-endian),互可转换 |
| `bool` | `"true"` / `"false"` 全 lowercase | 不同形式(`\x01` / `\x00`)|
| `bytes` | base64url 无 padding | 不同形式(raw bytes)|
| `time` | epoch nanos decimal text(如 `"1738892400123456789"`) | 不同形式(int64 big-endian,`struct.pack(">q", ...)`),互可转换 |
| `uuid` | canonical lowercase UUID (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) | 不同形式(16 raw 字节)|
| `entity_ref` | 完整 ref 字符串(详见 identity 重设计 doc) | 相同形式(UTF-8 bytes)|

### §5.2 `claim_meta.value` 列编码

`claim_meta.value` 列**全部 TEXT**,没有 per-row `value_tag` 标识。格式约定如下:

| 类型 | 决定规则 |
|---|---|
| **系统已知 key**(如 `source`、`bound`、`ingested_at`) | 格式由 **META_KEY_REGISTRY**(§5.3)显式规定 |
| **用户自定义 key** | 默认 `string` — 直接 UTF-8 text。如需结构化 value,**用户负责自行序列化**(如 JSON 字符串)+ 自行管理 reader 端解码 |

**没有 value_tag 的理由**:
- 100% 用户 meta 是 string(source / trace_id / note 等)
- 少数 system key 有固定已知格式(registry 唯一来源)
- 加 value_tag 列对绝大多数行是 dead weight;用 registry 中心化更简洁

**reader 端解码协议**:
1. 看 `claim_meta.key`
2. 若 key 在 META_KEY_REGISTRY → 按 registry 格式解码
3. 否则 → 直接 return TEXT 字符串

### §5.3 META_KEY_REGISTRY

**Registry 是系统已知 meta key 的格式权威**。所有这些 key 都是 reserved(user 可以读取,但 user 自定义 key 不应与这些冲突)。

| key | 格式 | Role | 备注 |
|---|---|---|---|
| `source` | string | source-meta | 事实来源标识(user / import / inference / adapter:problog 等)|
| `source_loc` | string | source-meta | 源位置(file:line / URL / row index 等)|
| `trace_id` | string | source-meta | 追踪/关联 ID(cross-write 链路追踪)|
| `approved_by` | string | source-meta | 授权该 assertion 的 actor 标识 |
| `note` | string | source-meta | 自由文本备注 |
| `raw_kind` | string (enum) | semantic-meta | 不确定性种类;允许值:`"probabilistic"` / `"possibilistic"` |
| `bound` | json | semantic-meta | canonical JSON 数组 `[lower:float64, upper:float64]`;与 `raw_kind` 必须成对出现 |
| `ingested_at` | time | system-meta | 写入时 epoch nanos decimal text;由系统强制注入 |
| `valid_from` | time | future-bitemporal | epoch nanos decimal text;未来 bitemporal 扩展预留,当前未启用 |
| `valid_to` | time | future-bitemporal | 同上 |
| *(其他用户自定义 key)* | string (默认) | user-meta | 用户自由 key;默认 string;如需结构化 value 用户自行 JSON encode + 自行解码 |

#### 格式映射到 §5.1 的 8 种 tag

| Registry format | 对应 §5.1 tag | 编码规则 |
|---|---|---|
| `string` | `string` | UTF-8 text 原文(§5.1)|
| `int` | `int` | normalized decimal text(§5.1)|
| `float64` | `float64` | finite shortest round-trip decimal + normalization(§5.1 + §5.4)|
| `bool` | `bool` | `"true"` / `"false"` |
| `bytes` | `bytes` | base64url 无 padding |
| `time` | `time` | epoch nanos decimal text |
| `uuid` | `uuid` | canonical lowercase UUID |
| `entity_ref` | `entity_ref` | 完整 ref 字符串 |
| `json` | (claim_meta 专属) | canonical JSON:sorted keys + no whitespace + UTF-8;详见 §5.6 |

### §5.4 `float64` normalization(写入路径强制)

`float64` value 在写入 SQL 前必须 **reparse-then-format**:

1. **finite 检查**:拒绝 `NaN` / `±Inf`(与 `_float64_bits` 的 `math.isfinite` 对齐)
2. **`-0.0` normalize**:bits `0x8000000000000000` 转 `0.0`(与 `_float64_bits` 已实现的行为对齐)
3. **reparse-then-format**:parse incoming text/value 为 float64 → 用 canonical formatter 输出;**不接受** `"1.2400"` 原样存

适用于:
- `claims.value` 当 `value_tag = "float64"`
- `claim_meta.value` 当 key 在 META_KEY_REGISTRY 且 format = `float64`
- META_KEY_REGISTRY 中 format = `json` 的 key 的 value 内部嵌套 float(如 `bound` 内的 lower/upper)

Cross-language formatter(Python `repr(float)` / Rust `{:?}` / Go `strconv.FormatFloat(x, 'g', -1, 64)`)算法等价(Grisu / Ryu),但**边界 case 可能不一致**;必须 golden tests 锁住(详见 §7.1)。

### §5.5 `time` 编码

SQL canonical = **epoch nanos decimal text**。ISO 8601 留给 audit / UI 显示层。

适用于:
- `claims.value` 当 `value_tag = "time"`
- `claim_meta.value` 当 key 在 META_KEY_REGISTRY 且 format = `time`(如 `ingested_at`)

不在 SQL 存 ISO 8601 的理由:Python `datetime` 3.12 前只有 microsecond 精度;`timestamp() * 1e9` 经过 float 丢纳秒精度;ISO 多种合法表示 normalization 易错。

### §5.6 `json` 编码(META_KEY_REGISTRY format=json 专属)

`json` 仅用于 META_KEY_REGISTRY 中显式标注 `format=json` 的 key(如 `bound`)。**不出现在 `claims.value_tag`**(INV-9 不允许嵌套结构作为 fact value)。

Canonical JSON 编码规则:
- sorted keys + no whitespace + UTF-8(不 escape ASCII 之外字符)
- Python 写入:`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- 内部数字遵循 §5.4 float64 规则(finite + `-0.0` normalize + shortest round-trip decimal)
- 例:`bound = [0.7, 0.9]` → `claim_meta.value = "[0.7,0.9]"`

---

## §6 Digest path 纪律

### §6.1 Digest 输入范围

**Digest 仅对 claims 表的核心 fact 内容计算,不含 claim_meta**:

```
fact_digest_input = canonical_bytes_tup_v1([
    ("string", pred_id),
    ("entity_ref", e_ref),
    (value_tag, value)   if value is not None else ()  -- 0-arity 跳过
])
```

claim_meta 不参与 fact digest。理由:
- digest 表达"这是什么 fact"(事实内容指纹),不是"这是哪次 assertion 事件"
- claim_meta 是 provenance / annotation,不是 fact 身份
- 两次 write 内容相同但 meta 不同(如不同 source)应该有**相同 fact_digest**(同一 fact 重复 assertion)和**不同 asrt_id**(不同 event)

### §6.2 Digest 计算路径

**所有 digest / hash / 跨语言 wire 序列化必须经 `tup_v1` 字节层**,不允许走 SQL CAST 短路:

```text
SQL 行(pred_id, e_ref, value, value_tag)
    ↓ parse 到 Python/Rust/Go 原生 typed value
    ↓ encode_value_bytes(value_tag, typed_value) → tup_v1 canonical bytes
    ↓ sha256 / blake3 / 其他 hash → digest
```

### §6.3 禁止模式

```sql
-- ❌ 不要这样
SELECT sha256(value || value_tag) FROM claims;
-- ❌ 也不要这样
SELECT sha256(CAST(value AS REAL) || '') FROM claims;
```

理由:SQL CAST 结果跨数据库(SQLite / Postgres / ...)可能微妙差异;text concat 跨平台不稳。digest 的 bit-exact 跨平台稳定性只能由 `tup_v1` 协议保证。

SQL CAST 可以用于**性能 path**(范围查询、partial index、generated column),但 CAST 结果**不可参与** digest 计算。

---

## §7 Implementation discipline

### §7.1 Cross-language float formatter golden tests

`float64` 的 "shortest round-trip decimal" 跨语言实现算法等价(Grisu / Ryu),但**边界 case 可能不一致**(subnormal、`1e-323`、`-0.0`、`5e-324` 等)。

实现必须建立 **golden tests**:
- 输入:约 50-100 个 finite float64(含边界 case:max/min normal、min subnormal、`-0.0`、`1.0`、`0.1+0.2`、`1e-300`、`1e308` 等)
- 期望:所有目标语言 implementation 输出**完全相同**的 decimal text
- 任一语言 formatter 违反 → 不允许接入

### §7.2 asrt_id 生成

UUID4 hex 无 dashes,由 [`write_protocol.new_assertion_id`](../../../../src/factgraph/core/evidence/write_protocol.py) 生成。每次 ledger 原语调用都产生一个新 asrt_id(INV-2)。

**含义**:同内容多次写入产生**多个 asrt_id**;ledger 不做 content dedup(idempotency 是上层 API 责任)。

### §7.3 写入原子性

每次 user-level 操作 = **一个 SQLite transaction**(INV-3):
- 普通 set/add(含 append claim 原语):1 行 claims + 0~N 行 claim_meta,单事务
- 撤销(含 append revoke claim 原语):1 行 claims(pred_id="__system__.revokes")+ 0~N 行 claim_meta,单事务
- SDK update(revoke + append 组合糖):1 行 revoke claim + 1 行 new claim + 0~N 行 new claim_meta,**所有写入同一事务**

### §7.4 索引基线

索引清单见 §3.1(claims)+ §3.2(claim_meta)的 DDL 部分。具体性能调优在 blueprint 期定。

**核心索引族**:
- claims: `(pred_id, e_ref)` / `e_ref` / `(pred_id, value)` / partial on revokes
- claim_meta: `(key, value)` / `asrt_id`(复合 PK 自动提供 asrt_id-prefix 查询,但单列 asrt_id 索引保证按 claim 取全部 meta 的高效查询)

### §7.5 Idempotency 责任划分

| 层级 | 责任 |
|---|---|
| **Ledger 层(本 spec)** | **不做 idempotency**。同内容多次写产生多个 asrt_id;ledger 原语只有 append claim + append revoke claim |
| **SDK / API 层** | 如需 idempotency,自行实现:correlation_id 表、request hash store、HTTP idempotency-key header 等 |
| **Caller / 应用层** | 自行管理重试逻辑;ledger 不阻止重复 |

**唯一例外**:`retract_by_asrt` 通过 INV-14 行为契约保留幂等(语义需要),实现机制是查找现有 revoke claim 而非 content hash。

### §7.6 SDK update / delete 作为组合糖

ledger 原语只有 **append claim** 和 **append revoke claim** 两个。SDK 层暴露的 `update` / `delete` 是这两个原语的组合:

| SDK 操作 | Ledger 原语序列 | 原子性 |
|---|---|---|
| `fg.fields.set(field, ref, value, meta)`(single cardinality)| 1. 查找既存 active claim(同 pred_id, e_ref);若有,append revoke claim<br>2. append new claim with value + meta | 同事务 |
| `fg.fields.add(field, ref, value, meta)`(multi cardinality)| append new claim with value + meta | 同事务 |
| future assertion-level update(asrt_id, value=..., meta_updates=...) | 1. append revoke claim targeting old asrt_id<br>2. append new claim with merged meta + 新 value | 同事务 |
| `fg.assertions.retract(asrt_id, meta)` | append revoke claim targeting asrt_id | 同事务 |

ledger 视角看不到 "update" 概念;只看到 revoke + append 流。

---

## §8 写入 / 读取 / 撤销 / 更新 / 删除 流程概览

### §8.1 普通写入(append claim 原语)

```text
fg.fields.set(User.name, alice, "Alice", meta={"source": "import", "trace_id": "seed-001"})
    ↓
application/entity_write 层:
  - 解析 EntityRef alice → e_ref="idref_v1:User:abc..."
  - 解析 Field User.name → pred_id="User:name"
  - 解析 value "Alice" + Field.value_kind → ("Alice", "string")
    ↓
core/evidence/write_protocol.set_field(ledger, pred_id, e_ref, value, value_tag, meta):
  - 验证 pred_id 非 __system__.* 前缀(INV-10)
  - 生成 asrt_id(UUID4 hex)
  - 构造 Claim(asrt_id, pred_id, e_ref, value, value_tag)
  - 构造 claim_meta rows:
      ・ 系统强制注入: ingested_at = <现在的 epoch nanos>
      ・ 用户提供 meta: source, trace_id, ... (转 TEXT 编码)
    ↓
ledger.append_claim(单 SQLite transaction,INV-3):
  - INSERT claims
  - INSERT claim_meta rows
```

**系统强制注入的 meta**:仅 `ingested_at`(META_KEY_REGISTRY format=time)。其他历史上的 system meta(`ingest_key`、`revoked_asrt_id`、`raw_kind` 等):`ingest_key` 已退场;`revoked_asrt_id` 已搬到 revoke claim 的 value 列;`raw_kind` 是 user 提供的 semantic meta,不是系统注入。

### §8.2 撤销(append revoke claim 原语)

```text
fg.assertions.retract(asrt_id, meta={"source": "manual-fix"})
    ↓
core/evidence/write_protocol.retract_by_asrt(ledger, revoked_asrt_id, meta):
  - 检查 revoked_asrt_id 存在 + 非 system claim(INV-12)
  - 查找现有 active revoke claim 指向同 target(INV-14 幂等)
    - 如找到:返回既有 revoker_asrt_id(短路)
  - 生成 revoker_asrt_id(UUID4 hex)
  - 构造 revoke Claim(INV-11 shape):
      Claim(
        revoker_asrt_id,
        pred_id="__system__.revokes",
        e_ref=<被撤销 fact 的 e_ref>,
        value=revoked_asrt_id,
        value_tag="string"
      )
  - 构造 claim_meta rows(ingested_at 系统注入 + user meta 如 source/note)
  - internal API:绕开 INV-10 namespace check(INV-10 仅针对 user-facing path)
    ↓
ledger.append_claim(单事务):
  - INSERT claims(revoke claim)
  - INSERT claim_meta rows
```

### §8.3 读取(按 entity + field)

```text
snap = fg.entities.get(User, tenant_id="t1", user_id="U001"); snap.display_name
    ↓
1. e_ref = idref_v1(EntityType, identity_kwargs) — deterministic hash, 不走反向索引
   (详见 identity-mechanism-redesign.zh.md §4.1 硬定义 1 + §7)
2. SELECT * FROM claims
     WHERE pred_id="User:display_name" AND e_ref=?
       AND pred_id NOT LIKE '__system__.%'              -- INV-15 默认 filter
   → 候选 asrt_ids
3. SELECT value FROM claims
     WHERE pred_id="__system__.revokes" AND value IN (候选)
   → 已撤销集合
4. active asrt_ids = 候选 \ 已撤销   (INV-13 公式)
5. 按 cardinality 语义聚合:
   - single: 取 ORDER BY seq DESC 第一个 active 的 value
   - multi: 收集所有 active 的 value(**multiset 语义** — 同 (value, value_tag) 出现 N 次返回 N 次,
            每个对应独立 asrt_id;保留 audit / provenance 完整性)
6. 按 value_tag 反序列化 value → 原生 Python 类型
```

**Multi-cardinality multiset 语义说明**:若同一 (pred_id, e_ref, value, value_tag) 被 add 两次(产生两个独立 asrt_id),读取返回**两次**该 value。caller 如需 set 语义自行 dedup。这与 ledger "duplicate claims 可能有意义"的设计哲学一致。

### §8.4 读取(按 claim_meta 过滤)

```text
record = snap.field("display_name").active.where(_meta={"source": "import"}).one()
    ↓
1. 取该 field 的所有 active asrt_id(同 §8.3)
2. SELECT asrt_id FROM claim_meta
     WHERE asrt_id IN (...) AND key="source" AND value="import"
3. 返回对应 AssertionRecord
```

### §8.5 SDK update 流(revoke + append 组合糖)

```text
future assertion-level update(asrt_id, value="Alice'", meta_updates={"trace_id": "v2", "note": "renamed"})
    ↓
application 层:
  - 查询 asrt_id 对应 claim(必须存在 + active)
  - 合并 meta:
      new_meta = old_claim_meta keys + meta_updates (updates 覆盖同名 key)
      ingested_at 重新注入(新 claim 的写入时间)
  - 构造 new Claim payload:
      (pred_id 同旧, e_ref 同旧, value=provided 或同旧, value_tag=provided 或同旧)
    ↓
core/evidence/write_protocol 内部(**单一 SQLite transaction**):
  - append revoke claim targeting old asrt_id
  - append new claim with new payload
  - INSERT new claim_meta rows (含合并后的所有 meta keys)
    ↓
返回 new_asrt_id
```

**关键约束**:
- 整个 update 必须**单一 SQLite transaction**(INV-3)— 防止 revoke 写了但 new claim 没写的部分态
- 旧 claim 的 claim_meta 行**保留不动**(永远 immutable);新 claim 有自己的 claim_meta 行(不同 asrt_id key prefix)
- 历史 audit 显示:在 T1 时间点 old asrt_id 的 (value, meta) 是某个状态;在 T2 时间点 revoke + new asrt_id 是另一个状态
- ledger 视角只看到 2 个原子操作(revoke + append),没有 "update" 概念

### §8.6 SDK delete / retract 流

```text
fg.assertions.retract(asrt_id)
  = append revoke claim(详见 §8.2)
```

Field-level `delete` 是更高层的 cell-clearance 组合操作;assertion-level 删除语义统一表现为 append revoke claim。ledger 层依然是 append-only。

---

## §9 数据精简 migration 路径(7 条)

> **Alpha 阶段说明**:本章节描述从当前 7 表 schema 演化到目标 3 表 schema 的**逻辑分解**。在 alpha 状态下:
>
> - **无生产数据搬迁需求** — drop 旧表 + create 新表即可,不需要 ALTER TABLE 的数据 backfill 工具
> - **无跨版本兼容层** — 一次性 atomic schema flip + 代码同步重写
> - **migration 时序**(§9.8)是 blueprint 拆分时的逻辑参考,不是必须的分阶段实施

按 7 → 3 张表的演化分解:

### §9.1 数据精简 1:`meta_rows` ↔ `annotation_rows` 收一份

- **delta**:删除 `meta_rows` 和 `annotation_rows` 两张表;合并为 `claim_meta`(同时 rename 为 claim_meta)
- **dual-write 机制退场**:当前白名单 7 个 meta key 双写两表的逻辑全部删除;所有 user meta key 同等对待
- **影响**:SDK `AssertionRecordSet.where(_meta=...)` query path 改造 — 走 claim_meta 索引

### §9.2 数据精简 2:`namespace` / `category` / `derivation` / `origin` 列删除

- **delta**:claim_meta 不含这四列
- **背景**:accept / accept_many 退场后多 namespace 写入源消失(详见 [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) §4 维度 6)
- **`derivation` 列**:annotation_rows 时代零写入;未来若需要恢复以独立 derivation 链表设计
- **`origin` 列**:observed/derived 区分简化掉;如未来需要,encode 为 meta key 自身(如 `meta_origin: "derived"`)

### §9.3 数据精简 3:`claims` ↔ `revokes` 统一

- **delta**:删除 `revokes` 表;撤销改为特殊 pred Claim(INV-11 shape)
- **影响**:所有 revoke reader 改走 claims 表的 `pred_id="__system__.revokes"` 过滤;`find_revoker` 实现改写
- **专用索引**:`idx_claims_revokes` partial index 补回原 `revokes` 表的窄查询性能

### §9.4 数据精简 4:`rest_terms` / `claim_args` 收口

- **delta**:删除 `claim_args` 表;`claims.rest_terms` JSON 列内联为 `value` + `value_tag` 双列
- **触发**:INV-9 unary commitment 确立后 `claim_args` 行展开退化为冗余(每条 Claim 永远 0 或 1 args)
- **影响**:写入路径取消 JSON 序列化;读取路径取消 JSON parse;canonical_bytes_tup_v1 调用点 list 永远 length 0 或 1

### §9.5 数据精简 5:`fact_meta` → `claim_meta` 改名 + drop `value_tag` + drop `origin` + 引入 META_KEY_REGISTRY

- **delta**:
  - 表 rename: `fact_meta` → `claim_meta`(强调"claim 的 meta"而非"事实的 meta";与 claim 不可变 payload 一致)
  - 列 drop: `value_tag`(meta value 全 TEXT;特殊格式由 META_KEY_REGISTRY 规定)
  - 列 drop: `origin`(observed/derived 简化掉;如需要 encode 为 meta key 自身)
  - 中心化:META_KEY_REGISTRY(§5.3)显式文档化系统已知 key 的格式(source / bound / ingested_at / 等)
- **理由**:100% user meta 是 string;少数 system key 有固定已知格式;value_tag 列对绝大多数行是 dead weight;用 registry 中心化更简洁
- **影响**:reader 端解码协议改为"查 META_KEY_REGISTRY → 按 format 解码"

### §9.6 数据精简 6:`ingest_keys` 退场 + ledger 不做 dedup

- **delta**:完全删除 `ingest_keys` 表;不在 `claim_meta` 写 `key="ingest_key"` 副本;ledger 不承担 idempotency
- **影响重大**:
  - `_compute_ingest_key` 算法不需要从 ledger 调(可保留作 SDK 层 helper 供上层 caller 自主使用)
  - `Idempotency(...)` 参数从 `ledger.append_assertion` / `append_revocation` 移除
  - `_find_active_claim_by_ingest_key` 函数(write_protocol)移除
  - `replace_field` 的 preflight dedup 简化(直接基于已 active 的 claims 行查重,不查 claim_meta)
- **承担方变化**:
  - 旧:ledger 内部双轨幂等机制(ingest_keys 表 + meta_rows.ingest_key 副本)
  - 新:上层 API / SDK / caller 自主管理 idempotency;ledger 仅保证 INV-14(retract 幂等)
- **理由**:
  - Datomic-style "纯 event log" 模型;idempotency 是 projection/API policy 不是 schema 约束
  - 同内容多次写入可以有意义(不同来源、不同时间、不同 actor)— 不应被 schema 阻止
  - 消除现有双轨冗余(INV-5 合规)

### §9.7 数据精简 7:`claim_meta` 复合 PK,删除 surrogate `id`

- **delta**:`claim_meta` 表去掉 `id INTEGER PRIMARY KEY AUTOINCREMENT` 列;改为 `PRIMARY KEY (asrt_id, key)`
- **理由**:
  - 物理 surrogate 无语义价值(meta 行的真正身份是 `asrt_id + key`)
  - UNIQUE(asrt_id, key) 反正存在,复合 PK 是更准确表达
  - 与现实"按 asrt_id 查所有 meta"的查询模式直接对齐
  - 配合 INV-2(asrt_id 全局唯一),复合 PK 永远只被 INSERT 一次,从根上排除 UPDATE 路径,强化 INV-1 append-only

### §9.8 Migration 时序(blueprint 拆分参考)

**Alpha 阶段允许 atomic schema flip** — 一次性 drop 7 表 + create 3 表 + 重写代码。无需按以下顺序分阶段实施。

但如果 blueprint 期希望分拆成更小的 slice 做 incremental landing(降低单次 review/test 负担),以下逻辑分解可参考:

1. 精简 1+5(meta_rows + annotation_rows → claim_meta;同时 drop value_tag/origin/derivation/namespace/category 列;引入 META_KEY_REGISTRY) — schema 层基础重构
2. 精简 3(claims/revokes 统一) — 需要协调 accept 退场的 dead code 清理
3. 精简 4 + 精简 6 **同 slice**(rest_terms 内联 + ingest_keys 退场) — 二者都触动 write_protocol 的 idempotency / set_field 路径,必须协调
4. 精简 7(claim_meta 复合 PK + 删 surrogate id 列) — 列结构最终清理

精简 2 是精简 1 的一部分(drop 4 列),不单独成步。

每步只需要 SQLite DDL drop/create + 代码重写 + 测试覆盖 + 文档同步;**不需要 SQLite ALTER 的数据 backfill 工具或 cross-version reader dispatch**(alpha 无历史数据)。

---

## §10 与 storage-architecture-evolution 的联动 / migration 时机

本 design-point §9 描述 ledger 数据格式的 7 步迁移路径。但格式迁移不能孤立进行 —— 它依赖另一份 design-point [`factgraph-storage-architecture-evolution.zh.md`](factgraph-storage-architecture-evolution.zh.md)(2026-06-02 draft)所描述的 lifecycle 收敛先落地,否则会留下数据完整性漏洞。

### 10.1 与 storage-architecture-evolution 的关系

`storage-architecture-evolution` essay 提出 4 阶段演化路线(详该 essay §3):

- **Stage A** —— Lifecycle convergence(commit_assertions 收敛)
- **Stage B** —— Ledger 读路径迁 SQL prepared statement
- **Stage C** —— Eval engine lazy materialize
- **Stage D** —— 废弃 eager mode(可选)

本 design-point 的 Slice 3b(§9 7 步精简)在两条线的交叉点上:

- **必须**在 storage-architecture-evolution **Stage A 完成之后**实施(硬前提)
- **应**在 storage-architecture-evolution **Stage B 启动之前**完成(软前提)

### 10.2 为什么 Stage A 必须先做(硬前提)

Stage A 的目标是收敛所有 ergonomic 写入入口经 `commit_assertions` 路径(详 storage-architecture-evolution §3.1)。在 Stage A 完成前:

- `fg.entities.create` / `fg.entities.delete` 绕过 `Database.commit_assertions`,直接调 `Ledger.append_assertion`(storage-evolution essay §1 problem 3 的 silent data integrity 漏洞)
- 同一份 ledger 同时存在"经 tx 链写入"和"绕 tx 链写入"两类 Claim

若在此状态下把 ledger 切到本 design-point §3 终态(claim_meta + revokes-as-Claim):

- 旧的"绕 tx 链"写入仍在 leak,只是 leak 到新格式 ledger 里
- 数据完整性漏洞从"7 表 ledger"原样搬到"3 表 ledger"
- Slice 3b 的迁移投入没有 close 任何根本问题

**结论**:Stage A 完成 = Slice 3b 启动的硬前提。

### 10.3 为什么应在 Stage B 启动前完成(软前提)

Stage B 把 `Ledger.find_*` 系列迁到 SQL prepared statement(详 storage-architecture-evolution §3.2)。在 ledger 仍是 7 表布局时实施 Stage B 意味着:

- 为旧 schema 写大量 SQL prepared statement → Slice 3b 后所有 statement 重写
- 浪费 ~4-6 周工程量(storage-architecture-evolution §3.2 估算)

合理实施序列:Stage A → Slice 3b(本 design-point §9)→ Stage B → Stage C → (D)。

### 10.4 联合 update plan

| 顺序 | Track | 来源 | Scope |
|---|---|---|---|
| 1 | Lifecycle | storage-architecture-evolution §3.1 Stage A | 收敛 commit_assertions,删 entities.create/delete 漏洞,统一 tx 链 |
| 2 | Format | **本 design-point §9 Slice 3b** | 7 → 2 数据表 + revokes-as-Claim + claim_args/annotation_rows/ingest_keys drop |
| 3 | Read path | storage-architecture-evolution §3.2 Stage B | SQL prepared statement,内存索引降级 cache |
| 4 | Engine | storage-architecture-evolution §3.3 Stage C | eval bulk_load(pred_ids) + discard;4 engine 各适配 |
| 5(可选)| Deprecate | storage-architecture-evolution §3.4 Stage D | 仅当 lazy 性能 ≥ eager,废弃 eager mode |

5 个阶段,跨越两份 design-point;Slice 3b 是本 design-point 的实施切片,落在 Stage A 与 Stage B 之间。

### 10.5 待裁定问题(与 storage-architecture-evolution 共享)

- **Q-SAE-6**(storage-architecture-evolution §4 提的 release 节奏问题):Stage A 在 v0.2.0 release 内 vs 推到 v0.3?该问题的答案**直接决定 Slice 3b 的实施起点** — 若 Stage A 在 v0.2.0 内,Slice 3b 可能进入 v0.2.x patch line;若 Stage A 推到 v0.3,联合 update plan 整体推到 v0.3。
- 本 design-point §9.8 的"migration 时序 4 阶段"与 storage-architecture-evolution §3 的"4 阶段 A-D"**指代不同对象**;两者 ⊆ 上述联合 update plan 中的不同切片。下游 Slice 3b blueprint 起草时需在文中明示边界,避免读者混淆。

### 10.6 引用与本 design-point 其他章节的关系

- §2 演化总览 / §3 表结构 / §9 7 步精简 —— 不变,本 §10 只是给它们指定**实施时序坐标**(在 Stage A 之后,Stage B 之前)
- §4.1 INV-1 append-only / §4.5 INV-5 ledger 是 source of truth —— Slice 3b 实施期 dual-coexistence 阶段仍持守这两条不变量(详 ADR-SYS-B §4.2 选 (c))
- §10(本节)是 forward-looking material,**不**在任何已 adopted ADR(SYS-A / SYS-B / IC / API / INV-9)引用范围内 —— 本节内容可在 design-point 迭代中调整,不破坏 ADR 引用完整性

---

## §11 决策日志

每条决策按时间顺序追加。所有数据格式相关决策在此追踪(identity 相关决策见 `identity-mechanism-redesign.zh.md` §决策日志)。

| 日期 | 决策点 | 选项 | 当前状态 |
|---|---|---|---|
| 2026-05-27 | β' schema 终态(不含 ingest_keys、不含 content_hash)| 选 β'(ledger 不做 dedup;idempotency 上层 API 责任)| ✅ 已采纳 |
| 2026-05-27 | 数据精简 6:`ingest_keys` 完全退场 + ledger 不做 dedup | 接受 | ✅ 已采纳 |
| 2026-05-27 | 数据精简 7:`claim_meta` 复合 PK `(asrt_id, key)` | 接受 — 删除 surrogate `id` | ✅ 已采纳 |
| 2026-05-27 | INV-1 至 INV-15(除 INV-6/7/8 是 identity 议题)| 接受作硬不变量 | ✅ 已采纳 |
| 2026-05-27 | Q-CK:是否引入 `claim_kind` 列(Datomic `added` 同款)| 不引入 — 保持 system predicate + INV-10 至 INV-15 institutionalization | ✅ 已采纳 |
| 2026-05-27 | INV-14 措辞:撤销幂等是 retract-specific 契约,不依赖 ingest_keys | 接受 — INV-14 永远走 find_revoker 风格机制 | ✅ 已采纳 |
| 2026-05-27 | Q-time SQL canonical 编码 | β:epoch nanos decimal text | ✅ 已采纳(见 §5.5)|
| 2026-05-27 | SQL `claims.value` 列 canonical 编码契约(8 种 value_tag 编码规则)| 锁定 §5.1 表 | ✅ 已采纳 |
| 2026-05-27 | Digest path 纪律:禁止 SQL CAST 参与 digest 计算 | 锁定 | ✅ 已采纳(见 §6)|
| 2026-05-27 | `float64` 写入纪律:finite + `-0.0` normalize + reparse-then-format | 锁定 | ✅ 已采纳(见 §5.4)|
| 2026-05-27 | Cross-language float formatter 必须 golden tests 锁住 | 锁定 | ✅ 已采纳(见 §7.1)|
| 2026-05-27 | Q-RV1:撤销机制属于哪个工业系谱 | append-only correction event 系谱(与 Datomic / Event Sourcing 同系谱)| ✅ 已采纳 |
| 2026-05-28 | claim-first immutable payload 模型:meta 是 claim 不可变 payload 一部分;meta 变更 = revoke + append 新 claim | 接受(覆盖之前"fact_meta 可独立 upsert"心智模型)| ✅ 已采纳 |
| 2026-05-28 | `fact_meta` 表 rename 为 `claim_meta` | 接受 — 强调 claim-bound 语义 | ✅ 已采纳 |
| 2026-05-28 | `claim_meta` drop `value_tag` 列 | 接受 — 全 TEXT;特殊 key 格式 META_KEY_REGISTRY 中心化 | ✅ 已采纳 |
| 2026-05-28 | `claim_meta` drop `origin` 列 | 接受 — 如需要 encode 为 meta key 自身 | ✅ 已采纳 |
| 2026-05-28 | META_KEY_REGISTRY 必须文档化 | 接受 — 见 §5.3 | ✅ 已采纳 |
| 2026-05-28 | Ledger 仅 2 个原语(append claim / append revoke claim);SDK update / delete 是组合糖 | 接受 — ledger 不引入 update 概念 | ✅ 已采纳 |
| 2026-05-28 | Digest 输入范围:仅 claims 核心 4-tuple,不含 claim_meta | 接受 — meta 是 provenance 不参与 fact 身份 | ✅ 已采纳(见 §6.1)|
| 2026-05-28 | 存在性断言 pred_id 形态 | `<EntityType>:exists` per-entity-type;**不**属于 `__system__.*` namespace;INV-15 不 filter | ✅ 已采纳(见 §3.1 + §4.7)|
| 2026-05-28 | Multi-cardinality 读取语义 | multiset(保留独立 asrt_id;caller 自行 dedup 如需 set 语义)| ✅ 已采纳(见 §8.3)|
| 2026-05-28 | Alpha 状态:无生产数据兼容性负担 | 接受 — migration 是代码 + schema 重构,不是数据搬迁;Q-VD / Q-WF 消解;Q-DB / Q-TP1 简化 | ✅ 已采纳(见 §2.3 + §9 alpha 前言)|

**待裁定**(alpha 状态下大幅简化):

| Q | 描述 | 当前状态 |
|---|---|---|
| Q-PR1 | PyReason edge 2-position 与 INV-9 unary 的冲突;建议 pyreason 改 Relationship 模式 | 待裁定(在 identity-mechanism-redesign 中跟踪)— **alpha 不影响**:adapter 设计议题与历史兼容无关 |
| Q-DB | SQLite DB on-disk migration 工具设计 | **alpha 简化为**:drop old schema + create new schema;无数据搬迁工具需求;blueprint 期定具体 DDL drop/create 顺序 |
| Q-TP1 | tup_v1 协议解读(length 永远 0/1 是否构成协议变化)| **alpha 简化为**:length 永远 0/1 不算协议变化;ledger 比协议严格(INV-4);如未来真需要新 tag,在新 blueprint 中重评估 |

**已消解(alpha 状态)**:
- ~~Q-VD~~ View snapshot digest 跨版本兼容 — alpha 无已发布 snapshot 流通,新模型上线即新 digest 全套,无需兼容层
- ~~Q-WF~~ Audit package wire format v2 → v3 + reader 版本 dispatch — alpha 无已发布 audit package 在外流通,直接定 v1 格式即可,无需 reader 版本 dispatch

---

## §12 关联文档与代码锚点

### §11.1 关联 design-points

- [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) — entity_ref 形态(idref_v1 typed content-derived hash 锁定)/ Identity-as-Claim 镜像 / GNF 落地 / Schema 声明(Form I)/ SDK API 表面分层(§12 AssertionView 统一)/ identity-specific 不变量(INV-6 / INV-7a/b/c;INV-8 消解)
- [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) — append-only 范式 10 维度评估 + future gap 识别(GDPR / bitemporal / compaction)
- `archive/identity-and-data-model-redesign.zh.md` — 本 spec 的前身 umbrella doc ⏳ 计划下一批次归档

### §11.2 关联 workflow 工件

- [`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md) — application-first runtime authority(identity-mechanism-redesign 引用为 INV-6 来源)

### §11.3 代码锚点

- [`src/factgraph/core/store/ledger.py`](../../../../src/factgraph/core/store/ledger.py) — 当前 7-table ledger schema + DDL + 写入路径(将被本 spec 重写)
- [`src/factgraph/core/protocol/tup_v1.py`](../../../../src/factgraph/core/protocol/tup_v1.py) — `tup_v1` 字节级 canonical 编码(INV-4 锁定)
- [`src/factgraph/core/protocol/idref_v1.py`](../../../../src/factgraph/core/protocol/idref_v1.py) — 当前 entity_ref 编码协议(详见 identity 重设计)
- [`src/factgraph/core/evidence/write_protocol.py`](../../../../src/factgraph/core/evidence/write_protocol.py) — 写入/撤销路径(精简 6 后简化:取消 Idempotency 参数链;精简 5 后加 META_KEY_REGISTRY 校验)
- [`src/factgraph/core/docs/01_architecture.en.md §4`](../../../../src/factgraph/core/docs/01_architecture.en.md) — 当前四层数据架构权威说明(将被本 spec 内容取代)

### §11.4 外部启蒙 / cross-validation reference

claim-first immutable payload 模型经多源 cross-validation:

- **Event Sourcing**: events immutable; 状态由 projection 得出;update = new event
  - [Microsoft Azure — Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
  - [Martin Fowler — Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html)
- **Datomic / 不可变 DB**: add/retract 都是 transaction data;retract 不删除历史
  - [Datomic — Transaction Data Reference](https://docs.datomic.com/transactions/transaction-data-reference.html)
- **金融账本 / 监管**: posted entry 用 reversal/correction,不重写原 entry
  - [SEC Electronic Recordkeeping Amendments for Broker-Dealers](https://www.sec.gov/investment/amendments-electronic-recordkeeping-requirements-broker-dealers)
  - [Oracle GL — Journal Reversal](https://docs.oracle.com/cd/E26401_01/doc.122/e48748/T312864T451269.htm)
- **更详细 10 维度 ledger 范式 survey**:参见 [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) §8

### §11.5 上层 API 映射(SDK surface)

本 spec 描述 ledger 层(Layer 1-3:Event sourcing / SPO / Entity model)的数据格式 truth。上层 SDK API 表面(`fg.entities.*` / `fg.fields.*` / `fg.assertions.*` / `AssertionView` / 终结操作返回 `AssertionRecordSet`)在 [`identity-mechanism-redesign.zh.md §12`](identity-mechanism-redesign.zh.md) 描述。

ledger 层 ↔ API 层的核心映射:

| API 层操作 | ledger 层效果 |
|---|---|
| `fg.entities.create(EC, **identity, meta=...)` | 算 `e_ref = idref_v1(EC, identity)` + atomic append 所有 Identity 镜像 Claim(每个 Identity 字段一条;INV-7b/c 保证 Claim 与 hash 输入一致) + entity-level meta 行;若 e_ref 已有 active Identity Claim 抛 `EntityAlreadyExistsError`;**legacy/transitional**:可继续 emit `<EntityType>:exists` Claim 兼容旧 reader,Step 1 后实质冗余(详见 §3.1 :exists framing) |
| `fg.entities.delete(EC, **identity)` | atomic append revoke Claim(`pred_id="__system__.revokes"`)指向该 e_ref 下**所有** active Claim(含 Identity + Field + 可选 :exists);**整批撤销**是允许 retract Identity Claim 的唯一路径 |
| `fg.fields.set(F, e_ref, value)` | retract 当前 (pred_id, e_ref) 所有 active Claim + append 新 Claim;单次调用天然事务;**Identity 字段拒绝**(INV-7c) |
| `fg.fields.add(F, e_ref, value)` | append 新 Claim(multi 字段);**Identity 字段拒绝**(INV-7c;Identity 强制 single) |
| `fg.fields.retract(F, e_ref, value)` | append revoke Claim 指向值匹配的 active Claim;**Identity 字段拒绝**(INV-7c) |
| `fg.fields.delete(F, e_ref)` | append revoke Claim 指向该 (pred_id, e_ref) 所有 active Claim;**Identity 字段拒绝**(INV-7c) |
| `fg.fields.get(F, e_ref)` | 索引查 `(pred_id, e_ref)` + 应用 INV-13 active projection |
| `fg.assertions.where(field=, e_ref=, value=, _meta=)` | 索引查询 + `_meta` 过滤走 claim_meta 表 join + 应用 INV-13 active projection |
| `fg.assertions.retract(asrt_id)` | append `(asrt_id_new, pred_id="__system__.revokes", e_ref=<原 e_ref>, value=<被 revoke asrt_id>, value_tag="string")`;**检测到 asrt_id 是 Identity Claim 时拒绝**(INV-7c — 防 dual-truth split;Identity Claim 只能走 entities.delete 整批撤销) |

具体到每个 API 的 ledger 操作详情、value_tag 推断、`_meta` 命名空间保留、Identity 在三层的可见性、改 Identity 语义(=delete+create)等参见 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) §12 + §5.2 INV-7a/b/c。

**INV-7c 在 ledger spec 的对应约束**(Identity Claim ↔ e_ref hash 一致性):
- ledger 写入路径**必须**检查 retract 目标的 pred_id 是否是 Identity 字段(通过 schema lookup),是则**拒绝**单独 retract;只允许通过 entities.delete 整批撤销
- 该检查由 application 层(`factgraph.application`)负责,ledger 表层不参与 schema-aware 拒绝(保持 ledger 层 schema-agnostic)

**INV-7c 实施 — 推荐策略 C(详见 [identity-mechanism-redesign §5.2](identity-mechanism-redesign.zh.md))**:
- application 层维护 schema 派生的 **Identity pred_id set**(启动时算出,schema evolution 触发重建)
- retract 路径通过 `claim.pred_id ∈ Identity pred_id set` 判断是否拒绝
- **不得**通过 `claim_meta` 标记 Identity Claim(策略 B 拒绝;`claim_meta` 承载 audit / provenance 等业务 meta,不承载 structural classification)
- 配套约束:`fg.schema.extend` 拒绝 Identity↔Field 互转 / 新增 Identity / 删除字段,防止 Identity pred_id set 随 schema 演化漂移而让旧 Claim 判定失效

---

## §13 当前批次完成状态

- [x] 单文件 spec 创建于 `workflow/design/design-points/active/ledger-schema-specification.zh.md`
- [x] 6-field metadata header
- [x] §1 目的与范围 / §2 演化总览
- [x] §3 表结构(claim-first 3-table schema:claims / claim_meta / ledger_meta)
- [x] §4 12 条结构性不变量(含 adapter 边界、存在性 namespace、multiset 语义等收紧)
- [x] §5 SQL value canonical 编码契约(§5.1 claims 8-tag;§5.2 claim_meta 全 TEXT;§5.3 META_KEY_REGISTRY;§5.4 float64 / §5.5 time / §5.6 json)
- [x] §6 Digest path 纪律(限定 claims 4-tuple;meta 不参与 fact 身份)
- [x] §7 Implementation discipline(含 §7.5 idempotency 责任划分 + §7.6 SDK update/delete 组合糖)
- [x] §8 写入 / 读取 / 撤销 / 更新 / 删除流程概览(6 节,含 §8.5 update + §8.6 delete)
- [x] §9 数据精简 migration 7 条(§9.5 重定义为 rename + drop columns + META_KEY_REGISTRY)
- [x] §10 决策日志(含 9 条 2026-05-28 claim-first 模型采纳决策)
- [x] §11 关联文档与代码锚点(含 cross-validation reference)
- [x] 自审 issues 全部消化:Issue 1(INV-1 措辞)/ Issue 2(§5.4 broken ref)/ Issue 3(§9.2 §11.1 错引)/ Issue 4(存在性命名空间)/ Issue 5(multiset 语义)/ Issue 6(system meta 清单)/ Issue 7(§7.4 dup)/ Issue 8(e_ref 索引)/ Issue 9(INV-9 adapter 边界)/ Issue 10(§9.8 ordering wording)
- [x] 2026-05-28: 与 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) Step 1 锁定同步:`:__exists__` → `:exists`(命名对齐源码);§3.1 加 Step 1 implication 注;§11.5 加上层 API 映射 pointer 到 identity §12
- [x] 2026-05-29: X-style consistency pass — §8.3 `fg.read.snapshot` → `fg.entities.get` + `idref_v1` 算 e_ref;§8.4 `active_assertions.where(source=)` → `.active.where(_meta={})`;§3.1 `:exists` 标 **legacy / transitional**(非 Step 1 终态);§11.5 全面更新 — `entities.create` 写 Identity 镜像 Claim、`entities.delete` 整批撤销、`fields.set/add/retract/delete` 拒绝 Identity 字段、`assertions.retract` 拒绝 Identity Claim 单独撤销(INV-7c);§4 总览更新 — INV-7 → INV-7a/b/c、INV-8 消解
- [x] 2026-05-29: INV-7c 策略 C 实施同步 — §11.5 加 application 层 Identity pred_id set 推荐策略 + 拒绝 claim_meta tag 策略(B)+ schema evolution 不允许 Identity↔Field 互转的配套约束
