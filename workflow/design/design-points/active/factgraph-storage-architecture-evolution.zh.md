# Design-Point: FactGraph 存储架构演化(Lifecycle 收敛 + Lazy SQL 迁移)

- Status: working
- Created: 2026-06-02
- Last Updated: 2026-06-02
- Authority: candidate design / non-authoritative reference. **Not current behavior.** Becomes a constraint only when cited by an adopted decision, an implemented blueprint, current module docs (`src/factgraph/*/docs/`), or `workflow/foundations/architecture_principles.md`.
- Inputs:
  - 2026-06-02 quickstart-vs-shipped 对话中对 `Database` / `SDKStore` / `Ledger` / `workspace` 的源码挖掘(本 essay §2 全部引用 file:line 出处)
  - `src/factgraph/sdk/store.py:1510-1514` SDKStore docstring 关于 `attach` 是 "Database-owned lifecycle for new DB/view substrate work" / `create / load_workspace` 是 "compatibility lifecycles" 的叙事
  - `ledger-schema-specification.zh.md`(claim-first 3-table ledger schema)
  - `identity-mechanism-redesign.zh.md`(Identity Claim + INV-7c)
  - `append-only-ledger-evaluation.zh.md`(append-only 范式 10 维度评估)
- Outputs / Downstream:
  - (none yet)
- Related:
  - [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) — ledger 表结构演化(7 → 2 数据表 + revokes-as-Claim)与本 essay 的 lifecycle / 读路径演化构成**联合 update plan**;详见 §7
  - `identity-mechanism-redesign.zh.md` — Identity Claim 写入路径在 lifecycle 收敛重构中需保持 INV-7a/b/c 不变量

> **Authority reminder** (per Q2 §4.4): a design-point cannot directly override shipped behavior. Implementation must reach the codebase via the downstream consumption chain (decision → blueprint → impl), not by direct reference to this essay.

## 1. Problem framing

FactGraph 当前存储架构在 2026-06-02 的源码挖掘中暴露出五个相互纠缠的结构性问题。它们都不属于"局部 bug",而是同一个底层架构选择的不同侧面 — 因此该作为**一个**演化目标来设计,而非零散修补。

**问题清单**:

1. **Workspace 双格式互斥**:`FactGraph.create(path=ws) + fg.save_workspace()` 产出的磁盘布局,与 `Database.create(ws, schema_ir=...)` 产出的布局,是**两套独立格式**,不是嵌套关系。两者只共享 `db/objects/schema/<digest>.json` 一个文件;其余文件(`ledger.db` 在前者,`db/{meta.json, assertions.db, refs/head.txt, objects/tx/}` 在后者)互不相交。同一个目录是合法的 SDK workspace 或合法的 Database workspace,**不可能同时是两者**。

2. **In-memory cache 架构**:所有读操作 (`Ledger.find_claims` / `get_claim` / `find_meta` / `find_annotations` / `has_active_revocation`)**全部从 Python `dict` / `list` 内存索引读取**,不碰 SQL。SQLite 的角色仅是 (a) append 时的 dual-write 持久化、(b) 冷启动时的全表 `SELECT * FROM ... ORDER BY id` 加载源、(c) WAL checkpoint。DDL 中定义的 `idx_claims_pred_id` 等 SQL 索引**在运行时从不被使用** — 它们既不参与查询规划,也不在冷启动 `ORDER BY seq` 扫描中加速。

3. **Attach asymmetry**:`FactGraph.attach(db, ...)` 路径上,公开写入入口的 reject 表非一致:
   - `fg.fields.set/add` — 显式 `_reject_attached_write`
   - `fg.fields.retract/delete` — 传递性拒绝(调 `fg.assertions.retract` 而后者被拒)
   - `fg.assertions.retract` — 显式拒绝
   - `fg.entities.edit` / `fg.batch` / `fg.ingest` / `fg.schema.*` / `fg.save_workspace` — 显式拒绝
   - `fg.commit_assertions` — 允许,经过 Database tx 链
   - **`fg.entities.create` / `fg.entities.delete` — 不拒绝,但直接走 `apply_create_plan` / `apply_delete_plan` → `Ledger.append_assertion`,绕过 `Database.commit_assertions`,因而绕过 tx 链**

   "attached runtime 上的所有写入必须走 `commit_assertions` 以维护 tx 链完整性" 这一设计意图(在 `_ATTACHED_WRITE_ERROR` 字面消息中明示)被 `entities.create/delete` 的**漏拒**破坏 — 这是 silent data integrity 漏洞:写入成功落库,但 `db/refs/head.txt` 未推进、`db/objects/tx/` 没有对应 tx 对象,`db.head()` 返回的版本号与 ledger 实际内容不一致。

4. **Storage layer 与命名不匹配**:`Database` 这个类型名暗示了 RDBMS 风格的 query capability(SQL filter / pagination / streaming / 多进程共享读),实际是"以 SQLite 为 WAL 介质的内存知识图谱"。所有 fancy 查询都是 Python 端 dict / list 操作。`commit_assertions` 看似是低层 substrate 入口,实际跟 `fields.set` 一样最终落到同一个 `Ledger.append_assertion` 函数,只多写两个 metadata 文件(tx 对象 + head 指针)。

5. **SDKStore docstring 叙事错位**:`store.py:1510-1514` 把 `attach` 称为 "the Database-owned lifecycle for new DB/view substrate work",`create / from_schema_classes / load_workspace` 称为 "compatibility lifecycles"。但实际上:
   - 两条 lifecycle 共用相同的内存 + SQLite WAL 存储模型
   - attach 不引入新的 storage / query 分层,仅在原模型外加 tx 链 + durable view 元数据
   - SDK lifecycle 的 ergonomic 写入入口(`fields.set/add` / `batch` / `entities.edit`)在 attach 路径上**不可用**,attach 实际是 ergonomic-poor subset
   - "forward-looking" / "compat" 这组标签不被实现层面支持

## 2. Context

### 2.1 关键代码事实(file:line 出处)

**Ledger 内存索引 + SQL WAL 双轨**([`src/factgraph/core/store/ledger.py`](../../../src/factgraph/core/store/ledger.py)):

- `_reset_indexes` 定义 `_claims` / `_claim_by_asrt_id` / `_claims_by_pred_id` / `_claims_by_e_ref` / `_claims_by_pred_e_ref` 等十余个内存 dict([line 818-870](../../../src/factgraph/core/store/ledger.py#L818))
- `find_claims` / `get_claim` 全部走内存([line 618-632](../../../src/factgraph/core/store/ledger.py#L618))
- `append_assertion` 在 SQL transaction commit 后通过 `post_commit` 同步更新内存([line 430-451](../../../src/factgraph/core/store/ledger.py#L430))
- `_load_from_db_via` 用全表 `SELECT ... ORDER BY seq/id` 一次性加载,无 WHERE / LIMIT([line 933-985](../../../src/factgraph/core/store/ledger.py#L933))

**Workspace 双格式**:

- SDK 路径 `ledger.db` 位置:[`application/workspace_runtime.py:13-17`](../../../src/factgraph/application/workspace_runtime.py#L13)、`save_workspace_manifest` ([line 64-80](../../../src/factgraph/application/workspace_runtime.py#L64))、`load_workspace` 验证 manifest + ledger 存在([line 146-151](../../../src/factgraph/application/workspace_runtime.py#L146))
- Database 路径 `db/` 子树:[`core/store/database.py`](../../../src/factgraph/core/store/database.py) `resolve_database_workspace_paths` ([line 556-573](../../../src/factgraph/core/store/database.py#L556))
- `views/` 同时在 root 级别(`root / "views"`,[`database.py:572`](../../../src/factgraph/core/store/database.py#L572)),不是 `db/` 子目录

**Reject 表完整清单**(`_reject_attached_write` 调用点,[store.py](../../../src/factgraph/sdk/store.py) grep):

- line 367 / 387 / 401 — `fg.assertion_views.create/update/delete`
- line 571 — `fg.assertions.retract`
- line 781 / 794 — `fg.fields.set/add`
- line 1243 — `fg.entities.edit`
- line 1901 — `fg.batch`
- line 1913 — `fg.ingest`
- line 1928 — `fg.add_schema_classes`
- line 1958 — `fg.schema.{register/extend/apply}`
- line 2293 — `fg.save_workspace`

**未在 reject 表中但实际绕过 tx 链的方法**:

- `fg.entities.create` ([store.py:1004-1080](../../../src/factgraph/sdk/store.py#L1004))调 `apply_create_plan` → `Ledger.append_assertion`
- `fg.entities.delete` ([store.py:1105-1219](../../../src/factgraph/sdk/store.py#L1105))调 `apply_delete_plan` → `Ledger.append_assertion`
- `fg.fields.retract` / `fg.fields.delete` 在传递层面被拒,因为内部转调 `fg.assertions.retract`

**Application planner 写入路径**(都不经过 `Database.commit_assertions`):

- `apply_write_plan` ([`application/entity_write.py:136-174`](../../../src/factgraph/application/entity_write.py#L136))调 `_apply_op` 直接到 `store.ledger`
- `_apply_op` ([line 697-761](../../../src/factgraph/application/entity_write.py#L697))调 `set_field` / `add_field` / `retract_by_asrt`,这些是 ledger 包装函数

### 2.2 涉及的业内 architecture 类比

| 系统 | 对应模式 |
|---|---|
| **Datomic** | Peer(全索引常驻内存,小到中规模图低延迟读)vs Client(lazy fetch),同集群可两种共存 |
| **SQLAlchemy / Hibernate** | Session-scoped identity_map + lazy query;`session.commit()` 是唯一持久化路径,porcelain 全部经过它 |
| **Git** | porcelain (`commit` / `add`) 总是合成自 plumbing (`write-tree` / `commit-tree` / `update-ref`),没有 bypass |
| **PostgreSQL / Neo4j / DuckDB** | Buffer cache + push-down filter + 按需 page 加载 |
| **Kafka producer** | 单一 log append 入口,所有高层 API 经过 |

业内的共识是:**single substrate write entry + 高层 ergonomic API 经过该 entry 的合成**。当前 factgraph 是 "双 write 入口 + 半拒绝 + 不变量漏洞" 三重组合,与业内 mature pattern 偏离。

## 3. Proposal / direction

四阶段演化路线,**严格按顺序**实施(每一阶段为下一阶段提供稳定的语义起点):

```
阶段 A:Lifecycle convergence(commit_assertions 统一)        ~2-3 周
   │   把"两种 workspace 格式 + entities.create/delete 漏洞 + reject 表不一致"全部收拢
   │   所有写都经过 tx 链
   │   存储模型仍是内存索引 + SQL WAL(未变)
   │   Database / SDK lifecycle 在实现层面合并(SDK 路径内部用 Database 作为内核)
   ▼
阶段 B:Ledger 读路径迁移到 SQL                              ~4-6 周
   │   保留内存写入索引(增量维护写入端)
   │   读 API 改为可选 SQL query mode(配置项)
   │   小图(< 100K assertions)依然 eager,大图切 lazy
   ▼
阶段 C:Eval engine 改为 lazy materialize                     ~4-6 周
   │   分析 rule 提取相关 predicate
   │   bulk_load(pred_ids) + run engine + discard
   │   4 个 engine 各自适配(native / Souffle / ProbLog / PyReason)
   ▼
阶段 D:废弃 eager mode(可选,远期)                          ~2-3 周
   │   仅当 lazy mode 在所有 benchmark 上达到 eager 的性能下限时
```

### 3.1 阶段 A — Lifecycle convergence

**目标**:Database 成为唯一存储 substrate,SDK lifecycle 内部基于 Database 实现,所有 ergonomic 写入入口都经过 `commit_assertions` 路径(因而都参与 tx 链)。

**步骤**:

1. **扩展 Database 写入入口**(添加 revocation 支持):

   ```python
   @dataclass(frozen=True)
   class RevocationInput:
       revoked_asrt_id: str
       meta: tuple[MetaEntry, ...] = ()

   # 在 Database 上新增
   def commit_changes(
       self,
       *,
       assertions: Sequence[AssertionInput] = (),
       revocations: Sequence[RevocationInput] = (),
   ) -> CommitResult:
       """统一 commit 入口:assertions 走 append,revocations 走 revoke,共享一个 tx_id。"""
   ```

2. **SDK 写入路径翻译器**:

   ```python
   def planned_ops_to_inputs(
       planned_ops: Sequence[PlannedOpDTO],
   ) -> tuple[list[AssertionInput], list[RevocationInput]]:
       """从 application planner 的结构化 op 翻译到 Database 输入 DTO。"""
   ```

3. **每个 ergonomic 方法的尾段改写**:`apply_write_plan` 不再直接调 `Ledger.append_assertion`;改为生成 plan → 翻译 → `db.commit_changes(...)`。

4. **拆除所有 11 处 `_reject_attached_write` 调用**:因为现在所有写都经过 tx 链,拒绝不再必要。

5. **SDK lifecycle 内部基于 Database**:
   - `FactGraph.create(path=ws)` 改为内部 `Database.create(ws, schema_ir=...) + FactGraph.attach(db, ...)`
   - `FactGraph.load_workspace(ws)` 改为内部 `Database.open(ws, schema_ir=...) + FactGraph.attach(db, ...)`
   - `fg.save_workspace()` 退化为可选的 metadata 时间戳更新

6. **Migration**:写一次性迁移 CLI,把现存 v0.2 SDK workspace 格式(`ledger.db` + `factgraph_workspace.json`)转换成 Database 格式(`db/{meta.json, assertions.db, refs/head.txt}`)。可以 lazy(首次 load 时迁)或 explicit(`python -m factgraph migrate-sdk-to-database <path>`)。

**收益**:
- 单一 substrate write entry
- tx 链完整性自动保证(所有写都有 tx_id)
- 删除 `entities.create/delete` 不变量漏洞
- 删除"两种 workspace 格式"的认知负担
- attach 真正成为 SDK lifecycle 的 superset(不再是 ergonomic-poor subset)

**未变**:内存索引 + SQLite WAL 模型;`O(总 assertion 数)` 内存;`O(总 assertion 数)` 启动时间。

### 3.2 阶段 B — Ledger 读路径迁移到 SQL

**目标**:`Ledger.find_*` 系列方法从"读内存 dict" 改为 SQL prepared statement + streaming cursor,内存索引降级为可选 cache。

**Tier 拆分**:

- **Tier 1 直接 SQL**:`exists` / `get(by id)` / `fields.get(by field+ref)` / `assertions.by_id`
- **Tier 2 SQL + session cache**:`entities.where(filter)` / `assertions.where(filter)` / EntitySnapshot 的 field lazy access — session 内可缓 identity_map
- **Tier 3 eval 时 bulk load**(留给阶段 C)

**配置项**:`FactGraph.attach(db, mode="eager"|"lazy")` 两种模式共存,默认按 workspace 大小自动选(< 100K assertions → eager,否则 lazy)。

**未变**:写入仍 dual-write(SQL INSERT + 写端内存索引);eval engine 仍 eager-load。

### 3.3 阶段 C — Eval engine lazy materialize

**目标**:rule evaluation 时不再依赖 "全部 facts 已在 Ledger 内存",而是 `bulk_load(pred_ids=referenced_in_rule)` 临时构造 working set,eval 完释放。

**步骤**:

1. 静态分析 rule body / RuleExpr,提取所涉及的 predicate id 集合
2. 在 Ledger 上加 `bulk_load_claims(pred_ids: set[str]) -> list[Claim]` 接口(走 SQL `WHERE pred_id IN (...)`)
3. 4 个 eval engine 适配:
   - **Souffle / ProbLog**:本来就是"喂 fact → 跑 → 出结果",顺理成章
   - **PyReason**:查其 fact-loading API
   - **Native engine**:需要查它是否依赖"全部 facts 在 Ledger 内存索引";若依赖,需要抽象出 fact-source interface

### 3.4 阶段 D — 废弃 eager mode(可选)

**触发条件**:lazy mode 在所有 benchmark 上(单点 get / where filter / eval throughput)达到 eager mode 性能下限。

若长期 lazy 性能不及 eager,则 D 不实施 — 保留双模作为永久配置。

## 4. Open questions (if any)

- **Q-SAE-1**:阶段 A 的 tx 颗粒度策略 — 每次 `fg.fields.set(...)` 是建一个新 tx,还是 SDK 隐式攒一个 session 在 `fg.save_workspace()` 时一次性 commit?前者实现简单但 tx 对象膨胀;后者需要"session boundary" 概念,改变写入的语义保证(commit 之前不可见 vs 写后立即可见)。
- **Q-SAE-2**:阶段 A 的 v0.2 在 wild 工作区数据迁移路径 — auto-migrate on first load,还是要求用户运行 CLI?auto-migrate 友好但有"首次 load 不可逆"的风险面;CLI explicit 安全但增加 release 负担。
- **Q-SAE-3**:阶段 B 的 eager / lazy mode 自动切换阈值(默认 100K assertions 是初步估算,需 benchmark 验证)。需要决定切换触发是 (a) 静态 workspace size,还是 (b) 运行时观测后切换。
- **Q-SAE-4**:阶段 C native engine fact-loading 抽象化的可行性 — 需要先做 native engine 代码 spike,确认能否在不重写 join algorithm 的前提下抽象出 fact-source 接口。
- **Q-SAE-5**:durable view 与 lazy mode 的相互作用 — view 当前定义为"asrt_ids 的固定集合",lazy mode 下 view-scoped read 是否预 load 全部 asrt_ids,还是按需 SQL 过滤?
- **Q-SAE-6**:阶段 A 是否在 v0.2.0 release 内?如果是,需要紧凑 cadence;如果是 v0.3 才做,当前 v0.2 alpha/rc 阶段需要在 quickstart / module docs 中如何如实呈现"双 lifecycle 存在但 attach 是 thin layer"的现状(避免误导用户)?

## 5. Consequences / downstream implications

### 5.1 实施顺序的硬约束

四阶段**不能跳序**:

- B 依赖 A:如果 tx 链不收敛,lazy 读路径无法定义"哪些 tx 内的 fact 可见"(因为有些写不在任何 tx 里)
- C 依赖 B:eval 的 bulk_load 接口要在 SQL query 已通的前提下加;否则又回到"全量内存"模式
- D 依赖 C:废弃 eager 必须在 lazy 已经能 cover 所有路径之后

### 5.2 Release 节奏

- **阶段 A** 可以独立成一个 blueprint cycle,在当前 v0.2.0 release 之后立刻开始(scope ~2-3 周,适合 v0.2.x patch 或 v0.3.0 minor)
- **阶段 B + C** 应该作为 v0.3 / v0.4 release 的明确目标,需要 design-point → decision → blueprint 的完整链路;不要塞进 patch release
- **阶段 D** 是 v1.0 级别的目标,只有当 lazy mode 在所有 benchmark 上稳赢才考虑

### 5.3 Decision 产生预期

预计本 essay 在迭代过程中会催生以下 decisions(`workflow/design/decisions/`):

- "Q-SAE-1 tx 颗粒度策略":决定 commit_assertions 是 per-call 还是 session-boundary
- "Q-SAE-2 v0.2 workspace migration policy":决定 auto vs explicit
- "Q-SAE-3 eager/lazy 自动切换阈值":benchmark 数据支撑下的阈值锁定
- "Q-SAE-4 native engine fact-loading abstraction":spike 后的 go/no-go

### 5.4 Blueprint 产生预期

每个阶段对应至少一个独立 blueprint:

- `YYYY-MM-DD_lifecycle-commit-assertions-convergence.md` — 阶段 A
- `YYYY-MM-DD_ledger-sql-read-path-migration.md` — 阶段 B
- `YYYY-MM-DD_eval-lazy-materialize.md` — 阶段 C
- `YYYY-MM-DD_eager-mode-deprecation.md` — 阶段 D(若触发)

### 5.5 短期 docs hygiene 影响

截至 v0.3 Stage A implementation branch,原先的双 lifecycle / 双 workspace
格式已经收敛。quickstart 与模块 docs 必须按以下事实叙述,不能继续沿用 v0.2
的 Mode A / Mode B 模型:

- `FactGraph.create(path=...)` / `load_workspace(...)` 内部拥有一个
  `Database`;`FactGraph.attach(db)` 绑定 caller-owned `Database`。两条入口
  使用同一 `db/assertions.db`、同一事务链与同一完整 ergonomic 写面,差异只在
  ownership。
- canonical 写调用返回时已经持久化;`save_workspace()` 只更新 lifecycle
  metadata,不是事务或 durability 边界,也不能把内存 runtime promotion/copy 到
  新路径。dry-run / sandbox 应复制一个已经关闭的 workspace 目录。
- durable open 在 v0.3 是 single-writer exclusive `flock`;没有只读并发打开
  通道。同一 workspace 双开(即使只读意图)会显式失败。
- v0.2 顶层 `ledger.db` workspace 只能通过显式
  `python -m factgraph migrate-workspace <path>` 迁移;不会在 load 时自动改写。
- `FactGraph.attach(db, view=view)` 是只读 snapshot 运行时;base attach 可使用
  canonical SDK 写面。`Database` 的低层 DTO commit 是机制面,不是另一种磁盘
  格式或唯一 attach 写入口。
- 仍然不能承诺 lazy load、并发多进程读或 SQL-first query。Stage A 收敛了
  lifecycle 与写链,没有实施 Stage B/C 的读路径和 engine materialization。

发布状态也必须诚实:v0.3.0 尚需按 Q-SAE-6 完成 meander pin-first 时序和用户
裁定的 RC 动作;implementation branch 落地不等于已经发布。

## 6. Status notes

- **2026-06-02 初稿**:从当时 quickstart-vs-shipped 对话中提炼。挖掘出的 5 个相互纠缠的事实(workspace 双格式 / 内存 cache 架构 / attach 半拒绝 / entities.create-delete 漏洞 / 命名错位)被收拢为单一演化叙事。
- **2026-06-02 §7 加入**:与 `ledger-schema-specification.zh.md` 显式关联为联合 update plan(5 阶段,跨两份 design-point);Slice 3b 被纳入 Stage A 与 Stage B 之间的实施切片。
- **下一步迭代触发**:
  - 任一 Q-SAE-* 进入正式 decision 流程
  - 阶段 A 开 blueprint(将引用本 essay + ledger-schema-specification §10 作为 audit-completed input)
  - 在 quickstart / module docs 中如何呈现现状的具体措辞决策

---

## 7. Combined roadmap with ledger-schema-specification

本 essay §3 描述 lifecycle / 读路径 / eval engine 的 4 阶段演化(A-D)。另一份 design-point [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) 描述 ledger 表结构演化(7 → 2 数据表 + revokes-as-Claim + claim_args / annotation_rows / ingest_keys drop)。两条线在实施层面交错,必须作为联合 update plan 看待。

### 7.1 依赖关系图

```
本 essay Stage A (lifecycle 收敛)
    │
    │  Slice 3b 启动 硬前提:此前 entities.create/delete 仍绕 tx 链,
    │  格式迁移会把数据完整性漏洞原样搬到新 ledger
    ▼
ledger-schema-specification Slice 3b (7 → 2 数据表 + revokes-as-Claim)
    │
    │  Stage B 启动 软前提:在新 schema 上写 SQL prepared statement,
    │  避免为 7 表布局重做一次
    ▼
本 essay Stage B (SQL 读路径)
    ▼
本 essay Stage C (lazy eval)
    ▼
本 essay Stage D (可选,废弃 eager)
```

### 7.2 联合 update plan

| 顺序 | Track | 来源 | Scope |
|---|---|---|---|
| 1 | Lifecycle | 本 essay §3.1 Stage A | commit_assertions 收敛 + 删 entities.create/delete 漏洞 + 统一 tx 链 |
| 2 | Format | [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) §9 Slice 3b | 7 表 → 2 数据表 + revokes-as-Claim + claim_args / annotation_rows / ingest_keys drop |
| 3 | Read path | 本 essay §3.2 Stage B | `Ledger.find_*` 走 SQL prepared statement;内存索引降级 cache |
| 4 | Engine | 本 essay §3.3 Stage C | eval 走 `bulk_load(pred_ids)` + discard;4 engine(native / Souffle / ProbLog / PyReason)各适配 |
| 5(可选)| Deprecate | 本 essay §3.4 Stage D | 仅当 lazy 性能 ≥ eager,可选废弃 eager mode |

5 阶段,跨越两份 design-point。Release 节奏建议(per §5.2 + ledger-spec §10.5):
- Stage A 落地 → v0.2.x patch 或 v0.3.0
- Slice 3b 落地 → 紧随 Stage A
- Stage B / C / D → v0.3 / v0.4 / 远期

### 7.3 已有 ADR 覆盖与 freeze 状态

[`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md) 已被 5 个 adopted ADR 引用其特定章节作为 binding constraint:

| ADR | 引用范围 |
|---|---|
| `q-ic-identity-as-claim-decision` | §3.1 部分(命名空间)|
| `q-api-namespace-decision` | §3.1 命名空间边界 |
| `q-sys-a-system-namespace-decision` | §3.1 命名空间 + §4.7 INV-10 |
| `q-sys-b-revokes-migration-decision` | §2.1 / §2.2 / §3.1-§3.3 / §3.4 / §4.9 INV-12 / §9.1-§9.7 / §9.8 |
| `q-inv9-decision` | §4.6 INV-9 + Q-PR1 PyReason adapter |

ledger-schema-specification 的核心章节(§2 / §3 / §9)已是 load-bearing;后续修改需 ADR amendment 流程。

本 essay 当前 **0 ADR 引用**(2026-06-02 起 working draft),仍可自由迭代。下游 decision 起草时,建议联合考虑两份 doc 的 trade-off,避免在某一份做出与另一份冲突的承诺。

### 7.4 Open question 联动

- **Q-SAE-6**(本 essay §4):Stage A 在 v0.2.0 release 内 vs 推到 v0.3?该问题直接决定 Slice 3b 的实施起点 — 同 ledger-schema-specification §10.5 关注的同一问题
- ledger-schema-specification §9.8 的"4 阶段 migration 时序"与本 essay §3 的"4 阶段 A-D"**指代不同对象**;两者都 ⊆ §7.2 联合 update plan 中的不同切片。下游 Slice 3b blueprint 起草时需在文中明示边界,避免读者混淆

### 7.5 下游 blueprint 命名约定

本 essay §5.4 已预期每阶段产生 1 个 blueprint。联合 update plan 下,blueprint 命名建议:

- `YYYY-MM-DD_stage-a-lifecycle-convergence.md` — 本 essay Stage A
- `YYYY-MM-DD_slice-3b-ledger-migration.md` — ledger-schema-specification Slice 3b(ADR-SYS-B Outputs 字段已预定此路径)
- `YYYY-MM-DD_stage-b-sql-read-path.md` — 本 essay Stage B
- `YYYY-MM-DD_stage-c-eval-lazy-materialize.md` — 本 essay Stage C
- `YYYY-MM-DD_stage-d-eager-mode-deprecation.md`(可选)— 本 essay Stage D
