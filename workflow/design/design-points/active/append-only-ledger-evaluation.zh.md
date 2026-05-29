# Append-Only Ledger 范式评估

- Status: working / reference evaluation（非 implementation-driving）
- Authority: candidate evaluation / non-authoritative reference; not current implementation truth
- First draft: 2026-05-27
- Last updated: 2026-05-27
- Scope: FactGraph 当前 mono-temporal append-only + revocation ledger 模式对照行业 best practice 的 10 维度评估；识别已实现的强项 + 未来 gap；不驱动当前 design 任务，作为 future design-point 起点的参考
- Parent: [`identity-and-data-model-redesign.zh.md`](identity-and-data-model-redesign.zh.md)（评估起源于该 essay §5 讨论）
- Design intent: 把当前 ledger 范式选型的合理性显式记录；标注已识别的 bitemporal / GDPR / compaction / upcaster 等扩展面，作为未来 design-point 的入口；当前**不展开实现路径**

## 目录

```text
§1   目的与边界
§2   Source-grep 现状（事实层）
§3   评估框架（10 维度）
§4   10 维度评估表
§5   强项与弱项总结
§6   已识别的未来 gap（按优先级）
§7   与 identity-and-data-model-redesign essay 的关系
§8   行业 reference（best practice 摘要）
§9   关联文档与代码锚点
```

---

## §1 目的与边界

### §1.1 这份 doc 是什么

- FactGraph 当前 ledger 范式选型的**专业评估**（mono-temporal append-only with revocation）
- 对照行业 best practice（Datomic / XTDB / SQL:2011 Temporal / Event Sourcing / Kafka / RocksDB）的 10 维度评分
- 识别已实现的强项 + 已知 gap + 未来扩展面
- 作为 future design-point 的入口点（任一 gap 真要做时，从这里出发独立开 doc）

### §1.2 这份 doc 不是什么

- ❌ 不是 implementation 驱动文档（不规定要做什么、何时做、谁做）
- ❌ 不是 architecture principles 升级（这是评估，不是约束）
- ❌ 不是当前实现真相（实现真相在模块 docs `src/factgraph/*/docs/`）
- ❌ 不替代 `identity-and-data-model-redesign.zh.md` 的工作 — 该 essay 处理 schema 重设计；本 doc 处理范式评估，**独立议题**

### §1.3 何时该回到这份 doc

当出现以下场景之一时，本 doc 是相关讨论的起点：

| 场景 | 触发 doc 的哪部分 |
|---|---|
| 用户/合规方要求 "右被遗忘"（GDPR / 类似法规）| §4 维度 6 + §6 高优先级 gap |
| 业务出现"effective date 改错了"类需求 | §4 维度 2 + §6 中优先级 gap |
| ledger 体量超过 ~10GB，启动时间或读延迟成为问题 | §4 维度 4/5/9 + §6 中优先级 gap |
| 需要 schema 非 additive 变更（删字段、改字段类型）| §4 维度 7 + §6 中优先级 gap |
| 跨节点/分布式部署需求出现 | §4 维度 10 |

---

## §2 Source-grep 现状（事实层）

### §2.1 ingest_keys 的实际作用

[`src/factgraph/core/store/ledger.py:112-116`](../../../../src/factgraph/core/store/ledger.py)：

```sql
CREATE TABLE ingest_keys (
  ingest_key TEXT PRIMARY KEY,
  asrt_id    TEXT NOT NULL,
  kind       TEXT NOT NULL    -- 'assertion' | 'revocation'
);
```

实际写入路径（同一文件 line 438 / 500）：
- `append_assertion(...)` 写入 `kind='assertion'`
- `append_revocation(...)` 写入 `kind='revocation'`

**`ingest_keys` 的两个职责**：
1. **幂等性**：同 (pred_id, e_ref, value, value_tag, meta) 组合 hash 已存在时跳过重复写入；`on_conflict="skip"`
2. **Row-type tag**：`kind` 列区分 idempotency 项的来源类型

**`ingest_keys` 不参与 active 判定**。active = NOT revoked 的判定是通过 `revokes` 表（精简 3 后通过特殊 pred Claim）+ in-memory `_revoked_asrt_ids` set 实现。

### §2.2 时态维度（temporal dimensions）

`valid_time_boundaries` 在代码中出现在两处：
- [`src/factgraph/core/semantics/profile.py:161-179`](../../../../src/factgraph/core/semantics/profile.py)
- [`src/factgraph/adapters/pyreason/engine_eval.py:309-406`](../../../../src/factgraph/adapters/pyreason/engine_eval.py)

但这是 **PyReason adapter 的时态推理参数**（PyReason 引擎内部用 timestep 离散时态），**不是 ledger 层的 valid time 概念**。

ledger 层时态信息：
- `claims.seq`：物理写入序（INTEGER PRIMARY KEY AUTOINCREMENT）— transaction time 的近似载体
- `fact_meta` 中 `ingested_at` meta key：epoch nanos 写入时间
- **无 valid_time / business_time 一等概念**

**结论：FactGraph 是 mono-temporal append-only ledger**（仅 transaction time 一等公民）。bitemporal（同时 system_time + valid_time）**未实现**。

### §2.3 撤销（revocation）路径

当前：
- `revokes` 表存 (revoker_asrt_id → revoked_asrt_id) 边
- in-memory `_revoked_asrt_ids` set 缓存
- reader 过滤 active = NOT in revoked set

精简 3 后：
- revokes 表删除
- 撤销 = claims 表中 `pred_id="__system__.revokes"` 的特殊 Claim
- in-memory set 从该特殊 pred 投影

两阶段都符合"撤销 = 新 assertion，不可 update 原 row"的 Datomic 风格 best practice（详见 §4 维度 3 + §8 §3）。

### §2.4 as-of / time-travel 查询 API surface

SDK 层有：
- `AssertionRecordSet.history.at(time)` — per-field 历史时点查询
- `AssertionRecordSet.history.version(version)` — version meta 过滤
- `AssertionRecordSet.history.by_id(asrt_id)` — exact assertion lookup

**没有的**：
- ❌ Graph-wide `db.as_of(T)` / `fg.as_of(T)` — 即"把整个 ledger 视作 T 时刻的快照"的查询入口
- ❌ SQL:2011 风格的 `FOR SYSTEM_TIME AS OF` 语法支持
- ❌ Bitemporal 双时态查询（`FOR SYSTEM_TIME AS OF d2 FOR VALID_TIME AS OF d1`）

### §2.5 GDPR / 硬删除 / 压缩

```bash
$ grep -rnE "purge|hard_delete|hard_purge|GDPR|forget|compact" src/factgraph/ \
    --include="*.py" | grep -v __pycache__
# 删除/purge 语义零匹配；compact 出现但仅在 "compact json" / "compact representation" 上下文
```

**零实现**：
- ❌ No GDPR escape hatch（用户授权的硬删除接口）
- ❌ No log compaction（删除超过保留期的旧 assertion）
- ❌ No tiered storage（hot/cold 分层）
- ❌ No crypto-shredding 框架（per-subject 加密 + drop key）

用户 2026-05-27 表述："让用户自己通过手段来清理数据" — 即承认这是个未设计的 escape hatch。

### §2.6 Schema 演化

- ✅ `fg.schema.add(EntityCls)` 支持 entity-add（schema 加新 Entity 类型）— 详见 [`src/factgraph/sdk/docs/04_api_surface.en.md §2.2`](../../../../src/factgraph/sdk/docs/04_api_surface.en.md)
- ✅ `fg.schema.add(SameNameReplacementCls)` 支持 non-identity field-add（同名类替换 + 新增字段）— 同上
- ✅ Schema digest lock 防止漂移（ledger 记 schema 数字签名）
- ❌ 非 additive 变更（删字段、改字段类型、identity 字段变更）显式 reject — **无 upcaster 链**；同 SDK doc 注明 "Destructive schema operations are not public: `fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, `fg.schema.deprecate` are deferred to future migration-planning work"

---

## §3 评估框架（10 维度）

来自 §8 行业 reference 提炼的评估框架：

1. **Identity 模型** — 事实的标识方案
2. **时态维度** — mono / bi / tri-temporal
3. **撤销语义** — 撤销如何表达
4. **Snapshot / checkpoint** — 状态快照策略
5. **Compaction 策略** — log vs storage compaction
6. **GDPR / 右被遗忘** — 与 append-only 的协调
7. **Schema 演化** — 历史 assertion 如何在新 schema 下存活
8. **As-of / time-travel API** — 时态查询入口设计
9. **Storage 效率** — tombstone、列存、热冷分层
10. **复制与冲突** — 多节点 ordering 与 retraction 因果

---

## §4 10 维度评估表

符号：🟢 完美对齐 / 🟡 半实现或当前规模够用 / 🟠 已知未来扩展面 / 🔴 真实 gap

| # | 维度 | 行业 consensus（详见 §8） | FactGraph 现状 | 评价 |
|---|---|---|---|---|
| 1 | Identity 模型 | 不可变 opaque ID + content-hash 仅作 dedup；纯 hash = anti-pattern | 当前 `idref_v1 = idref_v1:{type}:{sha256-of-identity-tuple}` 纯 content-hash | 🔴 **正在修复**（`identity-and-data-model-redesign.zh.md` §7 的核心议题）|
| 2 | 时态维度 | mono = 审计底线；矫正/回填密集域 default = bitemporal | mono-temporal（仅 transaction time via `seq` + `ingested_at`）；`valid_time_boundaries` 是 PyReason adapter 局部概念 | 🟡 **审计底线达成**；bitemporal 升级 = 应用域决定的扩展面 |
| 3 | 撤销语义 | 撤销 = 新 assertion；retract-of-retract = re-assertion；soft flag 劣选 | 撤销 = Revokes 边（精简后 = 特殊 pred Claim）；INV-1 严格守 append-only | 🟢 **完美对齐 Datomic 模式** |
| 4 | Snapshot / checkpoint | 是优化层不是 truth；版本化 schema、错配丢弃重建 | in-memory `_revoked_asrt_ids` set + 索引；启动从 ledger 重建（INV-5）；**无 disk snapshot** | 🟡 **当前规模够用**；超大 ledger 时启动 rebuild 时间会成瓶颈 |
| 5 | Compaction 策略 | 区分 log compaction（损坏 audit）vs storage compaction（必要的物理合并） | 两类**都没有**。SQLite VACUUM 是 raw 文件碎片整理，不属于 log/storage compaction 任一类 | 🟠 **未来扩展面**。长生产期 storage 单调增长 |
| 6 | GDPR / 右被遗忘 | crypto-shredding（默认）+ PII-by-reference（最干净）+ excision（法律刚性兜底）| **零 escape hatch**；用户层口头约定"自己清理" | 🔴 **明确 gap**。合规场景上线前必须设计 |
| 7 | Schema 演化 | schema-as-data + upcaster 链；in-place rewriting 是最后兜底 | additive 演化已支持（entity-add + field-add via class replacement）；non-additive **无 upcaster** | 🟡 **基础合规**；非 additive 演化未来要补 |
| 8 | As-of / time-travel API | first-class 查询 modifier；`FOR SYSTEM_TIME AS OF T` / `db.as-of(T)` / XTDB bitemporal | `AssertionRecordSet.history.at(time)` per-field 有；**graph-wide `fg.as_of(T)` 没有** | 🟡 **半实现**；底层数据足以支撑（seq 给 ordering），缺公开 API surface |
| 9 | Storage 效率 | columnar + dictionary encoding（Parquet, XTDB）冷存比 row-based 小 5-50×；tombstone 生命周期管理 | SQLite row-based + UTF-8 text；无 columnar 冷归档；无 tombstone GC | 🟠 **当前规模够用**（SQLite 单机性能 OK）；规模化（百 GB+）需补列存归档 |
| 10 | 复制 / 冲突 | append-only 让 fact replication 易（events 不可变 + 幂等）；难点在 ordering + retraction 因果 | **当前单机 SQLite**，无复制；`ingest_keys` 幂等机制是未来 replication 的基础 | 🟡 **未实现但有底子**。单机阶段不是问题 |

---

## §5 强项与弱项总结

### §5.1 强项（与 audit-first ledger 范式完美对齐）

| # | 强项 | 状态 |
|---|---|---|
| 1 | 撤销语义 = 新 assertion（Datomic 级别正确）| 🟢 已实现 |
| 2 | INV-1 append-only 上升为不变量（杜绝软删除）| 🟢 已实现 |
| 3 | ledger 是 truth，derived state 可重建（INV-5）| 🟢 已实现 |
| 4 | identity ≠ content-hash 的修正方向已启动 | 🟡 在做（`identity-and-data-model-redesign.zh.md` §7） |
| 5 | 基础 schema 演化（additive + digest lock）| 🟢 已实现 |
| 6 | mono-temporal 守住审计底线 | 🟢 已实现 |
| 7 | 4-tuple 数据模型与 Datomic / EAVT 同构 | 🟡 精简后达成（`identity-and-data-model-redesign.zh.md` §5）|

### §5.2 弱项 / Gap

| # | Gap | 类型 | 紧迫度 |
|---|---|---|---|
| G1 | Identity = content hash anti-pattern | 已知 anti-pattern 修复 | 🔴 高（当前 essay 在做）|
| G2 | GDPR escape hatch 零实现 | 合规 gap | 🔴 高（合规场景上线前必须）|
| G3 | Bitemporal valid time 未升一等公民 | 域决定的扩展 | 🟡 中（取决于应用域）|
| G4 | Compaction 策略缺失 | 规模化扩展 | 🟠 低（当前体量不痛）|
| G5 | Graph-wide `as_of` API 未一等公民化 | UX 扩展 | 🟡 中 |
| G6 | Non-additive schema 演化无 upcaster | 演化扩展 | 🟡 中 |
| G7 | Storage 不是冷热分层 | 规模化扩展 | 🟠 低 |
| G8 | 跨节点复制未实现 | 分布式扩展 | 🟠 低（取决于部署形态）|

---

## §6 已识别的未来 gap（按优先级）

### §6.1 高优先级（合规/正确性 gap，不补会出真实问题）

#### G1 — Identity = content-hash anti-pattern

- **现象**：`idref_v1` 把 identity 值 hash 进 entity_ref；string 变 → entity 变（违反 "Things not Strings"）
- **影响**：rename 不可能、identity 字段不可查询、与 GNF 哲学冲突
- **处置**：**正在做** — `identity-and-data-model-redesign.zh.md` §7 Identity 重设计
- **建议**：本 doc 不展开；交给 parent essay

#### G2 — GDPR / 右被遗忘 escape hatch

- **现象**：无任何 hard-delete / crypto-shred / PII-by-reference 框架
- **影响**：合规场景（任何处理 EU/CA/巴西/中国个人数据的部署）上线即违法
- **三个 viable 方向**（来自 §8 §6）：
  - **(a) Crypto-shredding**（默认 production 答案）：fact_meta 中 PII key 用 per-subject DEK 加密，user 要求删除 = drop 该 DEK，ciphertext 变 unreadable noise；ledger topology + asrt_id + timestamp 全部存活
  - **(b) PII-by-reference**：PII 不进 ledger，进 mutable side-store；ledger 只持有 opaque ref；删除 = 删 side-store row（ledger 不变）
  - **(c) Excision**（Datomic `:db.fn/excise` 类）：受权 hard-delete + 留 excision audit event；昂贵但合规
- **未来 design-point 建议名**：`gdpr-escape-hatch-design.zh.md`
- **建议**：本 doc 不展开实现；若合规需求确定后单独开 design-point

### §6.2 中优先级（应用域决定，但不补会被业务推着补）

#### G3 — Bitemporal valid time 升一等

- **现象**：仅 transaction time first-class；valid time 只在 PyReason adapter 局部
- **触发条件**：业务出现 "effective date 改错了"、"backfill 历史数据"、"法律生效日 ≠ 录入日" 类需求
- **方向**：参考 XTDB / SQL:2011 — `valid_time_start`/`valid_time_end` 作为 fact_meta 一等字段；查询语法加 `FOR VALID_TIME AS OF T` modifier
- **代价**：所有 reader path 要重新审视，查询语义复杂度 ×2
- **未来 design-point 建议名**：`bitemporal-upgrade-design.zh.md`

#### G5 — Graph-wide as-of API

- **现象**：`history.at(time)` 是 per-field 局部 API；缺 `fg.as_of(T)` 之类 graph-wide 入口
- **方向**：参考 Datomic `db.as-of(T)` — 返回一个 graph snapshot view，普通查询在 view 上执行
- **代价**：相对较小（底层数据已支持，只是缺 API surface）
- **建议**：与 G3 一起做更经济

#### G6 — Non-additive schema 演化 upcaster

- **现象**：删字段 / 改字段类型 / identity 变更**显式 reject**
- **触发条件**：业务要求 schema 实质性变更
- **方向**：参考 Axon / Marten — versioned event + upcaster 链；老 schema fact 读时由 `vN → vN+1` upcaster 链 lift
- **未来 design-point 建议名**：`schema-upcaster-design.zh.md`

### §6.3 低优先级（规模化扩展面，单机/中等体量不痛）

| # | Gap | 触发体量/场景 |
|---|---|---|
| G4 | Compaction（log 与 storage 分开） | ledger > ~10GB 或合规归档窗口要求 |
| G7 | Tiered storage / 列存归档 | ledger > ~100GB |
| G8 | 跨节点复制 | 分布式部署 / HA 需求 |

低优先级不意味着不重要 — 而是当前 SQLite 单机 + ~GB 级 ledger 还没触发瓶颈。规模到了再开 design-point。

---

## §7 与 identity-and-data-model-redesign essay 的关系

### §7.1 边界

| 议题 | 归属 |
|---|---|
| Claim 4-tuple schema 设计 | `identity-and-data-model-redesign.zh.md` §5 |
| 数据精简（meta_rows / annotation_rows / namespace/category / revokes / claim_args） | `identity-and-data-model-redesign.zh.md` §6 |
| Entity_ref opaque token 重设计（Identity = hash anti-pattern 的修复） | `identity-and-data-model-redesign.zh.md` §7 = **本 doc 的 G1** |
| Append-only INV / 撤销 = 新 assertion / mono-temporal 现状评估 | **本 doc** §4-§5 |
| Bitemporal upgrade / GDPR / Compaction / Upcaster / 跨节点复制 | **本 doc** §6 已识别但**不属于任一 essay scope** |

### §7.2 cross-link

- `identity-and-data-model-redesign.zh.md` 处理的是 G1（Identity anti-pattern 修复）+ schema 精简
- 本 doc 处理范式评估 + G2-G8 的识别
- 两者**互补不重叠**

### §7.3 当前任务焦点

按 2026-05-27 用户表述："目前还应聚焦于我们当前的任务"。本 doc 完成后：
- ✅ 当前任务（`identity-and-data-model-redesign.zh.md` §6 数据精简 / §7 Identity 重设计 / §9 迁移）继续推进
- ⏸ 本 doc 不阻塞当前任务，作为 future 入口点静默存在

---

## §8 行业 reference（best practice 摘要）

来自 2026-05-27 dispatch 的 general-purpose agent 调研，覆盖 Datomic / XTDB / SQL:2011 Temporal / Event Sourcing / Kafka / RocksDB 等系统。完整出处见 §9.

### §8.1 Identity 模型

**Consensus**：不可变 opaque ID + content-hash 仅作 dedup 层；纯 content-hash identity 是已知 anti-pattern。

**Production patterns**：
- Datomic 64-bit 顺序 entity ID + 可选 `:db.unique/identity` 属性（常为 v7/squuid UUID）
- Event sourcing：aggregate ID（UUID/v7）+ monotonic stream position + event UUID for 幂等键
- Content-addressed dedup 作为独立层：hash 标 `unique/identity`，但 entity identity 仍 opaque
- Time-ordered UUID（squuid / UUIDv7）改善索引 locality

**Pitfalls**：纯 content hash → 不相关 entity 因 shape 相同被合并；sequence number 作跨副本 identity → 多 master 冲突。

### §8.2 时态维度

**Consensus**：mono-temporal（transaction time）是审计最低线；矫正/回填密集域 default = bitemporal；tritemporal 罕见。

**Production patterns**：
- Datomic = mono-temporal；valid time 自建用户属性
- XTDB / SQL:2011 = first-class bitemporal：`SYSTEM_TIME`（不可变）+ `VALID_TIME` / `APPLICATION_TIME`（可变）
- 区间使用半开 `[start, end)`（SQL:2011 强制）

**Pitfalls**：mono-temporal 装 valid time → 查询不能用时态操作符；闭区间 → off-by-one；允许用户写过去的 transaction time → 审计被破坏（XTDB 显式禁止）。

### §8.3 撤销语义

**Consensus**：撤销 = 新 assertion（retraction event），永不 in-place mutate；原 row 永留；retract-of-retract = re-assertion。

**Production patterns**：
- Datomic `[:db/retract entity attribute value]` 写新 datom（`added=false`）；原 datom 保留在 history index
- Event sourcing：发 domain event `OrderCancelled` / `ClaimRevoked`，永不改 `OrderPlaced`
- Soft flag (`is_active`, `revoked_at`) 是 SQL:2011 history table 常见，但混淆"从未断言"和"曾断言后撤销"
- 独立 revocation table / topic 当撤销有自己的 provenance schema 时使用

**Pitfalls**：撤销时硬删原 row → 失去"T 时刻我们相信什么"；NULL end-timestamp 不用 sentinel → 区间叠加查询失败。

### §8.4 Snapshot / checkpoint

**Consensus**：snapshot 是 optimization 层而非 truth；版本化 schema；错配丢弃重建。

**Production patterns**：
- 每 N events snapshot（典型 N=50-1000）
- 后台 snapshot writer 与写路径解耦
- CQRS read-side：连续消费 event stream，维护查询形状 state
- Tiered snapshot（hot + cold archived intervals）

**Pitfalls**：snapshot 作 canonical state → projection 改后静默 drift；同步 snapshot-on-write → tail latency；不版本化 snapshot → domain logic 改后老 snapshot 产生错状态。

### §8.5 Compaction

**Consensus**：区分 "log compaction"（损坏语义）vs "storage compaction"（保留语义）。前者对 audit 危险；后者必要。

**Production patterns**：
- Kafka `cleanup.policy=compact`：只保留每 key 最新值；适合 state-store topic，**不适合**音频 topic
- Tiered storage（Kafka KIP-405, XTDB object-store tier）
- LSM compaction（RocksDB）：leveled vs universal vs FIFO
- Append-segment merging：超级 SSTable 合并，drop superseded tombstone

**Pitfalls**：audit topic 开 Kafka log compaction → audit promise 静默破坏；`compact` + tiered 没设 `local.retention.ms` → segment 在 compaction 完成前 tier；LSM tombstone "deleted" 短暂复现 → 测试要容忍。

### §8.6 GDPR / 右被遗忘

**Consensus**：default = **crypto-shredding**（per-subject 加密 + drop key）；excision 仅在法律强制时用且记录 excision event。

**Production patterns**：
- Crypto-shredding (Kafka, EventStore, 多数 ES 系统)：per-subject DEK 在独立 key store；删除 = drop DEK；ciphertext 变 noise；log shape / ID / timestamp 全保留
- PII-by-reference (Datomic 常见 GDPR pattern)：PII 不进 ledger，进 mutable side-store
- Datomic `:db.fn/excise`：硬删 + 留 excision audit event；昂贵
- Tombstone with content scrubbing：替换 payload 为 tombstone marker

**Pitfalls**：纯 crypto-shred 在某些司法管辖未必算 "实际删除"；excision 不留 audit event → audit gap；derived store（fulltext, analytics warehouse, backup）忘了 → 主库 shred 后 derivative 仍有 plaintext。

### §8.7 Schema 演化

**Consensus**：schema-as-data + 显式版本化 + upcaster 链；in-place rewriting 是 last resort。

**Production patterns**：
- Datomic schema-as-data：schema 本身是 datom，普通 transaction 演化
- Versioned event + upcaster (Axon, Marten)：每 event 带 `schema_version`，反序列化时 `vN → vN+1` upcaster 链
- Weak schema (JSON / Avro 默认值)：additive 自动兼容
- Copy-and-transform：核选项，重写整 log

**Pitfalls**：改历史 event → 破 audit / hash chain / 过去 projection 复现；多版本无 upcaster → consumer 代码组合爆炸；忘 snapshot schema version → 静默错答案。

### §8.8 As-of / time-travel API

**Consensus**：时态作为 first-class 查询 modifier，不是 per-table 列约定；fix transaction time / valid time / 双 / 默认 now。

**Production patterns**：
- SQL:2011: `FOR SYSTEM_TIME AS OF T` / `FOR PORTION OF VALID_TIME FROM ... TO ...`
- Datomic: `db.as-of(t)` / `db.history()`
- XTDB bitemporal: `FOR VALID_TIME AS OF d1 FOR SYSTEM_TIME AS OF d2`
- Range: `BETWEEN`, `OVERLAPS`, `CONTAINS`

**Pitfalls**：把时态作为 app-side filter → 索引不配合；audit-table schema 与 base 不同 → 查询发散；valid-time-in-past 不做 ACL → 用户改历史。

### §8.9 Storage 效率

**Consensus**：append-only 用 storage size 换写吞吐 + audit。冷存用 columnar + dictionary encoding；tombstone 生命周期管理；index 与 raw log 分离。

**Production patterns**：
- Tombstone lifecycle (RocksDB / Cassandra)：delete 写 marker；tombstone 在 bottom level + 所有 older version 确认压完后才删
- Columnar + dictionary (Parquet, XTDB column store)：枚举式属性大幅缩 5-50× 冷存大小
- Tiered hot/cold：hot RocksDB/LMDB + cold columnar object store；Datomic = index segments in S3 + memcached
- Index vs log 分离：Datomic 4-5 个 covering index；XTDB 不可变 log + 可重建 index

**Pitfalls**：大 blob 内联 log → 复制爆炸；tombstone 累积 → scan amplification 慢但无明显 cause；过早建多索引 → 写放大随索引数线性。

### §8.10 复制与冲突

**Consensus**：append-only 让 fact replication 简单（不可变 + 幂等）；难点是 retraction 因果一致。

**Production patterns**：
- Single-writer + read replica（Datomic, classic Kafka）：transactor 是 linearizer
- Replicated ES + version vector（Akka/Pekko, Eventuate）：每副本独立 log + vector clock + causal delivery
- Op-based CRDT：每 operation 带 vector clock；commutativity + idempotency + causal order → convergent state
- Kafka MirrorMaker：byte-for-byte 分区复制

**Pitfalls**：把 retraction 视为可交换 → "assert + retract" 重排后错；用 wall-clock 作冲突解决 → clock skew 致 retraction 输给后到的 assert；multi-master 无显式冲突模型 → 静默 diverge。

### §8.11 Cross-cutting 总结

| Take-away | 影响 |
|---|---|
| Identity ≠ content-hash（known anti-pattern）| FactGraph §7 在修 |
| Retraction is an assertion | FactGraph 已经是 |
| 矫正密集域 mono-temporal 早晚要升 bitemporal | FactGraph 取决于应用域 |
| GDPR 仅 crypto-shredding 或 PII-by-reference 两条 viable | FactGraph 尚无 |
| Schema-as-data + upcasters 是主流；rewrite 是 last resort | FactGraph 部分（additive 有，upcaster 没）|
| Compaction-of-log vs compaction-of-storage 易混淆 | FactGraph 都没有 |

---

## §9 关联文档与代码锚点

### §9.1 关联 workflow 工件

- [`workflow/foundations/architecture_principles.md`](../../../foundations/architecture_principles.md) — Layer authority + release surface governance
- [`workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`](identity-and-data-model-redesign.zh.md) — Parent essay；G1 Identity anti-pattern 修复在这里展开
- [`src/factgraph/core/docs/01_architecture.en.md`](../../../../src/factgraph/core/docs/01_architecture.en.md) — 四层数据架构权威说明

### §9.2 代码锚点

- [`src/factgraph/core/store/ledger.py`](../../../../src/factgraph/core/store/ledger.py) — ledger schema + 写入路径 + revoke 处理
- [`src/factgraph/core/protocol/idref_v1.py`](../../../../src/factgraph/core/protocol/idref_v1.py) — entity_ref 编码（G1 anti-pattern 所在）
- [`src/factgraph/core/protocol/tup_v1.py`](../../../../src/factgraph/core/protocol/tup_v1.py) — value 类型编码
- [`src/factgraph/core/evidence/write_protocol.py`](../../../../src/factgraph/core/evidence/write_protocol.py) — append-only 写入路径
- [`src/factgraph/core/semantics/profile.py`](../../../../src/factgraph/core/semantics/profile.py) — valid_time_boundaries（PyReason 局部，非 ledger 层）

### §9.3 行业 reference（agent 调研出处）

agent 2026-05-27 调研引用的关键 reference：

- [Datomic and Content Addressable Techniques (Latacora, 2024)](https://latacora.github.io/blog/2024/09/13/datomic-and-content-addressable-techniques/) — Identity ≠ content-hash anti-pattern 权威 write-up
- [Datomic Schema Identity](https://docs.datomic.com/schema/identity.html)
- [Datomic Excision](https://docs.datomic.com/operation/excision.html)
- [Making a Datomic system GDPR-compliant (Val Waeselynck)](https://vvvvalvalval.github.io/posts/2018-05-01-making-a-datomic-system-gdpr-compliant.html)
- [XTDB Bitemporality](https://v1-docs.xtdb.com/concepts/bitemporality/)
- [JUXT: The Value of Bitemporality](https://www.juxt.pro/blog/value-of-bitemporality/)
- [SQL:2011 (Wikipedia)](https://en.wikipedia.org/wiki/SQL:2011)
- [Kafka, GDPR and Event Sourcing (Dan Lebrero)](https://danlebrero.com/2018/04/11/kafka-gdpr-event-sourcing/)
- [Kafka Log Compaction (Confluent)](https://docs.confluent.io/kafka/design/log_compaction.html)
- [RocksDB Compaction (Wiki)](https://github.com/facebook/rocksdb/wiki/Compaction)
- [Snapshot Strategies (Kurrent / EventStore)](https://developers.eventstore.com/resources/articles/snapshotting-strategies)
- [Replicated Event Sourcing (Akka)](https://doc.akka.io/libraries/akka-core/current/typed/replicated-eventsourcing.html)
- [Upcasting Deep Dive (Artium)](https://artium.ai/insights/event-sourcing-what-is-upcasting-a-deep-dive)

---

## §10 当前批次完成状态

- [x] 单文件 design-point 创建于 `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
- [x] 6-field metadata header
- [x] §1 目的与边界 / §2 source-grep 现状 / §3 评估框架
- [x] §4 10 维度评估表
- [x] §5 强项与弱项总结
- [x] §6 8 条 gap 识别（按优先级分层）
- [x] §7 与 parent essay 的关系
- [x] §8 行业 best practice 摘要（agent 调研）
- [x] §9 关联文档与代码锚点
- [ ] cross-link from parent essay → 本 doc（待加在 identity-and-data-model-redesign.zh.md §10）
