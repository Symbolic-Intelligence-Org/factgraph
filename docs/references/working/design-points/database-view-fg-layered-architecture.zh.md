# Database / View / FG Layered Architecture — Minimum Implementable Design

- Status: working / minimum implementable blueprint
- Authority: non-authoritative reference note; not current implementation truth
- Rewritten: 2026-05-19
- Scope: 收敛 FactGraph 的最小可实现分层架构: `Database` / `DatabaseValue` / `SubsetView` / `FactGraph runtime`
- Parent: `rule-expression-and-proof-attempt.zh.md`
- Design intent: 先让 snapshot 与 scope 可验证,再谈 branch / clone / sub-fg / remote database

## 目录

```text
§1   设计目标
§2   非目标
§3   核心抽象
§4   不变量
§5   最小数据结构
§6   Database 层
§7   DatabaseValue(snapshot)层
§8   SubsetView 层
§9   FactGraph runtime 层
§10  Workspace File Layout
§11  最小 API
§12  view= 作为 read/evaluate/explain scope
§13  stale / scope 校验
§14  Evidence / Evaluate metadata 接缝
§15  与现有 v1 subset view 的关系
§16  实施路线
§17  显式 deferred 项
§18  设计承诺 Commitments
§19  与 rule-expression-and-proof-attempt.zh.md 的接缝
```

---

## 1. 设计目标

当前 `FactGraph` 一体化承载 schema、ledger、view、runtime API。长期看,这会阻碍:

- 多个 runtime 共享同一底层事实库
- view 作为可复现 scope 被 evaluate / explain 使用
- evidence 对数据库版本与 view scope 做 stale 检测
- 未来引入 persistent view、branch、sub-fg、remote database

本设计的最小目标是拆出 4 个清晰概念:

```text
Database
  持久 assertion store + transaction log

DatabaseValue
  某个 tx_id 下的不可变数据库快照

SubsetView / FrozenAssertionView
  在某个 DatabaseValue 上的一组 assertion ids

FactGraph
  attach 到 DatabaseValue 或 SubsetView 的 runtime
```

核心判断:不要一开始实现 Datomic / Git / Dolt 全量能力。先锁住 transaction/version anchor 与 assertion scope,让 Phase 1 evaluate、Phase 2 explain、evidence metadata 都能稳定复现。

## 2. 非目标

以下能力在本设计中明确不做:

| 非目标 | 原因 |
|---|---|
| branch / tag | 需要完整 ref model、merge/rebase 语义;超出最小版本 |
| writable sub-fg / view 写回 | 写入目标、隔离级别、冲突处理未定;先只做 read-only scoped runtime |
| multi-db join | 会引入跨 database transaction / schema 一致性问题 |
| remote database service | 先定义本地语义;transport 后置 |
| Rule persistence / SavedRule registry | Rules 先保持 code artifact;Database 只持事实和 schema anchor |
| dynamic view | 会破坏 evidence reproducibility;v1/v2 只做 immutable subset view |
| materialized derived view | 需要 derived fact lifecycle;后置 |
| assertion retract / update | 最小版本只 append assertions;retraction 作为 tx 扩展后置 |

## 3. 核心抽象

### 3.1 Database

Database 是唯一持久写入点。

职责:
- 保存 assertion records
- 维护 append-only transaction log
- 维护 current head tx
- 提供 `head()` / `as_of(tx_id)` 生成 immutable `DatabaseValue`
- 提供 schema digest / data digest

非职责:
- 不执行 Rule / RuleExpr
- 不保存 runtime working set
- 不持有 evidence tree
- 不保存 Python rule object

### 3.2 DatabaseValue

DatabaseValue 是某个 `db_id + tx_id` 下的不可变 snapshot。

职责:
- 给 evaluate / explain 提供稳定 assertion universe
- 提供 `schema_digest` / `data_digest` 用于 stale 检测
- materialize assertion ids 到 records

非职责:
- 不允许写入
- 不表达 subset;subset 由 `SubsetView` 表达

### 3.3 SubsetView / FrozenAssertionView

`SubsetView` 是语义名:在某个 DatabaseValue 上冻结的一组 assertion ids。

`FrozenAssertionView` 是 v1 concrete DTO / Python 类型名。本文档后续约定:
- 讨论架构语义时用 `SubsetView`
- 讨论数据结构 / API 返回值时用 `FrozenAssertionView`
- 两者不是两个不同概念;`FrozenAssertionView` implements `SubsetView`

职责:
- 表达 Phase 1 / Phase 2 的可见数据宇宙
- 作为 `view=` 参数传给 read / evaluate / explain
- 通过 `db_id + base_tx_id + schema_digest + view_digest` 参与 reproducibility

非职责:
- 不是 database version
- 不是 branch
- 不是 working copy
- 不自动包含后续 derived assertions

### 3.4 FactGraph

FactGraph 是 runtime / connection。

职责:
- attach 到 Database head / DatabaseValue / SubsetView
- 暴露现有 API 表面:`read` / `eval` / `views` 等
- 在运行时把当前 snapshot + optional view scope 传给 engines

非职责:
- 不作为唯一持久数据 owner
- 不隐式复制整份 database
- 不在 scoped view runtime 中写回 base database
- 不感知 / 不持有 rule set;rules 在 `Expr` / `Inference` / `Rule` 对象内部引用,`rule_set_digest` 由 evaluate 时计算并写入 EvaluateResult metadata

## 4. 不变量

| # | Invariant |
|---|---|
| I1 | `Database` 是唯一持久写入点 |
| I2 | `DatabaseValue` immutable;由稳定 `db_id` + content-addressed `tx_id` 唯一定位 |
| I3 | `SubsetView`/`FrozenAssertionView` immutable;由 `db_id + base_tx_id + asrt_ids + schema_digest` 派生 `view_digest` |
| I4 | `FactGraph.attach(db)` attach 当前 head,默认 writable |
| I5 | `FactGraph.attach(db.as_of(tx_id))` attach snapshot,read-only |
| I6 | `FactGraph.attach(db, view=view)` attach view scope,read-only |
| I7 | `view=` 指定时,read/evaluate/explain 只能看见 `view.asrt_ids` 内 assertions |
| I8 | `view=` 省略时,read/evaluate/explain 使用 attached snapshot 的 full assertion universe |
| I9 | scoped runtime 不 silent fallback 到 full universe |
| I10 | evidence / evaluate metadata 必须记录 `db_id` / `tx_id` / `schema_digest` / optional `view_digest` |
| I11 | `db_id` 是 database identity,持久存储;`tx_id` 是 transaction content identity,跨进程可复现 |
| I12 | `FactGraph.attach(...)` 签名不包含 `rules=`;rule set 通过 `Expr` / `Inference` 内部引用承载,evaluate 时计算 `rule_set_digest`;rules 不进 Database transaction、不进 workspace v1 |
| I13 | Workspace 物理布局:`db/objects/` content-addressed write-once + `db/refs/` 唯一 mutable pointers + `db/assertions.db` SQLite index layer;views 同模式 |

## 5. 最小数据结构

### 5.1 Identity 生成规则

#### `db_id`

`db_id` 是 database identity,不是 path digest。

规则:
- `Database.create(path)` 生成 `db:<uuid4>` 并写入 database metadata
- `Database.open(path)` 必须读取 metadata 中已有 `db_id`;同一路径多次打开得到同一 id
- database 被移动路径后 `db_id` 不变
- database 被文件级复制后 `db_id` 也保留;这是 restore / replica 语义,不是 new database 语义
- 用户若需要从同内容创建独立 database,必须走 explicit clone / re-id API(本设计 deferred)
- in-memory default database 使用 `mem:<uuid4>`;不承诺跨进程 / 跨 session 复现

#### `tx_id`

`tx_id` 是 transaction content identity,必须跨进程可复现。

最小版本锁定:

```text
tx_id = "tx:" + sha256(canonical_tx_payload)
```

`canonical_tx_payload` 包含:
- `parent_tx_id`
- `schema_digest`
- sorted `added_assertion_digest`
- resulting `data_digest`

`canonical_tx_payload` **不包含**:
- `created_at`
- local path
- process id
- host info

因此,同一 parent + 同一 assertion payload + 同一 schema 得到相同 `tx_id`。`created_at` 是 audit metadata,不是 identity 输入。

#### `asrt_id`

最小版本锁定:

```text
asrt_id = "asrt:" + sha256(canonical_assertion_payload)
```

`canonical_assertion_payload` 包含:
- `pred_id`
- `fact_tuple`
- `schema_digest`
- canonical `meta`

若两个事实值相同但 provenance / meta 不同,它们是不同 assertion。若 payload 完全相同,它们得到同一 `asrt_id`。

### 5.2 DatabaseValue

```python
@dataclass(frozen=True)
class DatabaseValue:
    db_id: str
    tx_id: str
    schema_digest: str
    data_digest: str
    created_at: datetime
```

### 5.3 FrozenAssertionView

```python
@dataclass(frozen=True)
class FrozenAssertionView:
    name: str
    db_id: str
    base_tx_id: str
    schema_digest: str
    asrt_ids: frozenset[str]
    view_digest: str
```

`view_digest` 计算建议:

```text
sha256(
  "subset-view-v1" +
  db_id +
  base_tx_id +
  schema_digest +
  sorted(asrt_ids)
)
```

### 5.4 AssertionRecord

`AssertionRecord` 是 Database commit / snapshot materialization 的最小 record shape。

```python
@dataclass(frozen=True)
class AssertionRecord:
    asrt_id: str
    pred_id: str
    fact_tuple: tuple[Any, ...]
    schema_digest: str
    assertion_digest: str
    tx_id: str
    meta: Mapping[str, Any]
```

字段规则:
- `asrt_id == "asrt:" + assertion_digest`
- `tx_id` 是首次引入该 assertion 的 transaction id
- `meta` 必须 JSON-canonicalizable;参与 `assertion_digest`
- `pred_id + fact_tuple` 是 engine / evidence 消费的最小 fact payload

本 shape 不试图表达完整 entity/field projection。entity materialization 属于 read layer,必须从 assertion records 投影出来。

### 5.5 DatabaseTx

```python
@dataclass(frozen=True)
class DatabaseTx:
    tx_id: str
    parent_tx_id: str | None
    created_at: datetime
    added_asrt_ids: tuple[str, ...]
    schema_digest: str
    data_digest: str
```

最小版本只记录 additions。retract / update / schema migration 是后续 tx model 扩展。

`tx_id` 必须按 §5.1 content-addressed 规则生成;不得使用 in-process counter 作为 durable tx identity。

### 5.6 Runtime attachment

```python
@dataclass(frozen=True)
class RuntimeAttachment:
    db_value: DatabaseValue
    view: FrozenAssertionView | None
    writable: bool
```

## 6. Database 层

### 6.1 最小职责

Database 层提供:

```python
db = Database.create(path)
db = Database.open(path)

db_value = db.head()
old_value = db.as_of(tx_id)

tx = db.commit_assertions(assertions)
```

### 6.2 写入模型

最小版本只允许 append assertions:

```text
current head tx
  + new assertions
  -> new tx
  -> new head
```

写入必须产生新的 `data_digest`,并按 §5.1 content-addressed 规则产生 `tx_id`。实现不得用自增序号 / UUID 作为 durable `tx_id`,否则 `view_digest` 无法跨进程复现。

### 6.3 Schema 模型

最小版本不设计完整 schema migration,但每个 tx 必须携带 `schema_digest`。

规则:
- assertion 写入时必须满足当前 schema
- `DatabaseValue.schema_digest` 是 evaluate / explain 的 schema anchor
- `SubsetView.schema_digest` 必须等于 `base_tx_id` snapshot 的 schema digest
- schema migration 后旧 view 仍指向旧 tx 的 schema digest

## 7. DatabaseValue(snapshot)层

`DatabaseValue` 是 read/evaluate/explain 的真正数据版本 anchor。

需要支持的最小操作:

```python
db_value.assertion_ids() -> frozenset[str]
db_value.assertions_by_ids(ids: Iterable[str]) -> tuple[AssertionRecord, ...]
db_value.contains_assertion(asrt_id: str) -> bool
```

实现上可以仍复用当前 ledger store。架构上必须把 snapshot identity 暴露出来。

`assertions_by_ids(...)` 返回的 record 必须满足 §5.4 `AssertionRecord` shape。不得返回 runtime-only proxy object 作为 durable API payload。

## 8. SubsetView 层

### 8.1 创建

```python
fg = FactGraph.attach(db)

records = fg.read.find(User, status="active")
view = fg.views.create("active_users", asrt_ids=[r.asrt_id for r in records])
```

创建 view 时,从当前 attachment 读取:
- `db_id`
- `base_tx_id`
- `schema_digest`

并冻结 `asrt_ids`。

### 8.2 校验

创建时必须校验:
- `asrt_ids` 全部存在于 attached `DatabaseValue`
- `asrt_ids` 不跨 database
- `name` 在当前 runtime 内不冲突

### 8.3 持久化

最小版本 view 可以继续不进入 `fg.save(...)`。但结构中已经包含 `db_id/base_tx_id/schema_digest/view_digest`,允许用户自行序列化后恢复。

持久 named view 作为 Database 资源 deferred。

## 9. FactGraph runtime 层

### 9.1 attach 模式

```python
fg = FactGraph.attach(db)
```

attach 到 current head,`writable=True`。

```python
fg_ro = FactGraph.attach(db.as_of(tx_id))
```

attach 到 immutable snapshot,`writable=False`。

```python
fg_view = FactGraph.attach(db, view=view)
```

materialize `view.base_tx_id` 对应 snapshot,并 attach scoped read-only runtime。

### 9.2 写入规则

| Attachment | writable | 写入行为 |
|---|---:|---|
| `FactGraph.attach(db)` | yes | commit 到 db current head |
| `FactGraph.attach(db.as_of(tx))` | no | raise `ReadOnlyAttachmentError` |
| `FactGraph.attach(db, view=view)` | no | raise `ReadOnlyAttachmentError` |

这条限制是设计安全阀。writable sub-fg 必须等 fork/merge/write-back 语义单独落定后再开放。

## 10. Workspace File Layout

### 10.1 三层 governance 分离

Workspace 是本地项目目录,承载三类正交概念:

```text
Database = facts + schema snapshot + tx history   (data governance)
Rules    = code artifact / deployment artifact     (code governance,v1 不进 workspace)
Workspace= 本地项目目录                              (file system 容器)
```

三者不混入同一个治理模型。本文档锁定 Database / View 在 workspace 内的物理布局;rules 在 v1 留在用户 Python 代码中,workspace 不持有 rule artifact。

### 10.2 Schema 的 code/snapshot 双层划分

```text
Python schema classes / authoring schema
  = code (用户代码 / git 治理)

db/objects/schema/<schema_digest>.json
  = compiled schema snapshot (data governance,immutable,Database 必存)
```

Database 必须保存它实际用过的 compiled schema snapshot,用于 assertion validation 与 evidence replay。schema 的 authoring source 不属于 Database。

### 10.3 推荐目录形态(Git-style objects + refs)

```text
<workspace>/
├── factgraph_workspace.json        # 顶层 manifest:version + components + timestamps
├── db/                             # Database 内聚子树
│   ├── meta.json                  #   db_id + creation info
│   ├── refs/
│   │   └── head.txt              #   ★ 唯一 mutable ref file:current tx_id pointer
│   ├── objects/                    #   content-addressed write-once
│   │   ├── tx/<tx_id>.json       #     每个 DatabaseTx 一个 JSON,parent_tx_id 串链
│   │   └── schema/<schema_digest>.json
│   └── assertions.db               #   SQLite,mutable index layer(不在 objects/ 内)
└── views/                          # SubsetView 持久化
    └── objects/<view_digest>.json  #   content-addressed view content
    # views/refs/<view_name>.json   #   named view registry,deferred 到 v2
```

### 10.4 不变量

| # | 规则 |
|---|---|
| L1 | `db/objects/` 下文件全部 content-addressed write-once;不可覆盖、不可删除(GC 单独治理) |
| L2 | `db/refs/head.txt` 是 Database 内唯一 mutable ref file;原子写,内容是当前 head `tx_id` |
| L3 | `db/assertions.db` 是 mutable index layer,可从 `db/objects/tx/` 回放重建;不参与 cross-process identity |
| L4 | `db/objects/schema/<schema_digest>.json` 在首次有 tx 引用某 `schema_digest` 时写入;已存在则不覆盖(content-addressed 天然幂等) |
| L5 | `views/objects/<view_digest>.json` content-addressed write-once;v1 仅匿名 view,不维护 name→digest 映射 |
| L6 | `factgraph_workspace.json` 顶层 manifest 收缩到最小:`{workspace_version, components.{db, views}, created_at, last_saved_at}`;不重复 `db_id` / `schema_digest`(已在 `db/` 子树内) |
| L7 | rule artifact 不进 workspace v1;如未来需要,新增 `rule-pack/` top-level 子树,不动 `db/` / `views/` |

### 10.5 与现状 Blueprint 2/3 layout 的 delta

| 项 | 现状 | 目标 |
|---|---|---|
| `registry/schema/schema_ir.json` | 单文件 | 迁到 `db/objects/schema/<schema_digest>.json`(多 snapshot 支持) |
| `registry/rules/`, `registry/inferences/` | 工作中 | 移除,rules-as-code in user Python |
| `registry/registry_manifest.json` | 工作中 | 移除 |
| `registry/authoring_apply_events.jsonl` | 可选 | 移除(git log 已覆盖,不重复) |
| `ledger.db` | top-level | 迁到 `db/assertions.db` |
| 无 tx log | — | 新增 `db/objects/tx/<tx_id>.json` append-only |
| 无 head pointer | 隐含在 SQLite head row | 显式 `db/refs/head.txt` |
| 无 view 持久化 | — | 新增 `views/objects/<view_digest>.json` |
| `factgraph_workspace.json` 含 `schema_digest` + `components` | — | 收缩为 minimal manifest,`schema_digest` 下沉到 db/ |

此 layout 是 Blueprint 2/3 的**实质修订**,不是叠加,需要专门 blueprint 承接。

## 11. 最小 API

### 11.1 Database API

```python
db = Database.create("path/to/db")
db = Database.open("path/to/db")

db.head() -> DatabaseValue
db.as_of(tx_id: str) -> DatabaseValue
db.commit_assertions(assertions: Iterable[AssertionRecord]) -> DatabaseTx
```

### 11.2 FactGraph attach API

```python
fg = FactGraph.attach(db)
fg_ro = FactGraph.attach(db.as_of(tx_id))
fg_view = FactGraph.attach(db, view=view)
```

签名锁定:`FactGraph.attach(db, view=None)`,**不包含 `rules=` 参数**。rules 通过 `Expr` / `Inference` / `Rule` 对象内部引用承载,evaluate 时计算 `rule_set_digest` 并写入 EvaluateResult metadata。该决策与 I12 一致。

### 11.3 View API

保持当前两个创建入口,但补齐 anchor fields:

```python
view = fg.views.create(name, asrt_ids=[...])
view = fg.views.create(name, asrts=[...])
```

暂不新增:
- `from_query`
- `to_view`
- view union / intersect / diff 方法
- persistent named view registry

## 12. `view=` 作为 read/evaluate/explain scope

### 12.1 默认全集

```python
fg.read.find(User)
fg.eval.evaluate(expr, head=head)
```

未指定 view 时,使用 attached `DatabaseValue` 的 full assertion universe。

### 12.2 指定 view

```python
fg.read.find(User, view=view)
result = fg.eval.evaluate(expr, head=head, view=view)
explanation = result.explain(row)
```

指定 view 时:
- engine 只看到 `view.asrt_ids`
- Phase 2 atom replay 只在 `view.asrt_ids` 内求值
- NAF / absence reason 的 `search_scope` 必须标识为该 view scope
- evidence metadata 记录 `view_digest`

### 12.3 Runtime-attached view 与 method-level view

两种写法语义等价:

```python
fg.eval.evaluate(expr, head=head, view=view)
```

```python
fg_view = FactGraph.attach(db, view=view)
fg_view.eval.evaluate(expr, head=head)
```

若 runtime 已 attach 到 view,再传另一个 `view=`:
- v1 直接 raise `ViewScopeConflictError`
- 不做 view nesting / intersect

## 13. stale / scope 校验

使用 view 前必须校验:

| 校验 | 失败 |
|---|---|
| `view.db_id == db.db_id` | `ViewDatabaseMismatchError` |
| `view.base_tx_id` 可 materialize | `StaleViewError` |
| `view.schema_digest == db.as_of(view.base_tx_id).schema_digest` | `ViewSchemaMismatchError` |
| `view.asrt_ids` 全部存在于 base snapshot | `ViewAssertionMissingError` |
| runtime-attached view 与 method-level view 不冲突 | `ViewScopeConflictError` |

禁止 silent fallback 到 full universe。

对 `result.explain(row)`:
- 若 row 的 `view_digest` 与当前 runtime view 不一致,返回 / raise stale scope error
- failure envelope 可使用 `failure_class="stale_evidence_ref"` 或 `out_of_scope_evidence_ref` 对接主文档 C125

## 14. Evidence / Evaluate metadata 接缝

EvaluateResult 应增加或继承以下 context:

```python
db_id: str | None
tx_id: str | None
schema_digest: str | None
data_digest: str | None
view_digest: str | None
view_name: str | None
```

EvidenceGraph.metadata 必须 durable copy:

```python
metadata = {
    "db_id": "...",
    "tx_id": "...",
    "schema_digest": "...",
    "data_digest": "...",
    "view_digest": "...",   # None for full universe
    "view_name": "...",     # optional rendering hint
}
```

原因:
- evidence 离开 runtime 后仍能判断是否 stale
- `view=` scope 是 proof semantics 的一部分,不能只存在于 API 调用栈
- NAF / absence reason 必须区分 full universe vs subset view

## 15. 与现有 v1 subset view 的关系

当前实现:

```python
FrozenAssertionView(name: str, asrt_ids: frozenset[str])
```

最小升级:

```python
FrozenAssertionView(
    name=name,
    db_id=current_db_value.db_id,
    base_tx_id=current_db_value.tx_id,
    schema_digest=current_db_value.schema_digest,
    asrt_ids=frozenset(asrt_ids),
    view_digest=compute_view_digest(...),
)
```

保留:
- immutable
- snapshot
- `asrt_ids` / `asrts` 两个创建入口
- 不自动包含 derived assertions
- 不提供 set algebra API

改变:
- view 有 database/version anchor
- view 可作为 read/evaluate/explain scope
- view stale 可检测

## 16. 实施路线

### Step 1: 给 view 补 anchor fields

- 增加 `db_id`
- 增加 `base_tx_id`
- 增加 `schema_digest`
- 增加 `view_digest`
- 创建时校验 ids 存在

### Step 2: 打通 `view=` consumer

- `fg.read.find(..., view=view)`
- `fg.eval.evaluate(..., view=view)`
- Phase 2 explain / evidence replay 传入同一 scope

### Step 3: Evaluate / Evidence metadata 写入 db/view context

- `EvaluateResult` 写 `db_id/tx_id/schema_digest/data_digest/view_digest`
- `EvidenceGraph.metadata` durable copy 同字段

### Step 4: 引入 `DatabaseValue`

- 即使底层仍是当前 ledger,也先暴露 `head()` / `as_of(tx_id)` snapshot identity
- 当前单 workspace 可映射为一个 default local database

### Step 5: 引入 `Database.open/create` 与 `FactGraph.attach`

- `FactGraph()` 可在过渡期继续创建 in-memory default database
- 新 API 作为 advanced / v2 path
- `FactGraph.attach(db, view=view)`
- `FactGraph.attach(db.as_of(tx_id))`
- read-only enforcement

**ship gate**:`FactGraph.attach(db, view=view)` 与 `FactGraph.attach(db.as_of(tx_id))` 不能早于 read-only enforcement 发布。若 attach API 先出现,这两个 attach form 必须默认 `writable=False` 且所有 write path raise `ReadOnlyAttachmentError`。

### Step 6: harden scoped runtime

- 增加 write-path regression tests
- 增加 stale / mismatch error tests
- 增加 EvaluateResult / EvidenceGraph metadata consistency tests

## 17. 显式 deferred 项

| 项 | 触发条件 |
|---|---|
| persistent named views in Database | 用户需要跨 session view registry |
| branch / tag / refs | 需要 long-lived alternative heads |
| writable sub-fg | fork / merge / write-back 语义单独落定 |
| assertion retract / update | 需要 deletion / correction semantics |
| schema migration tx | schema 演进需求明确 |
| materialized derived views | derived fact lifecycle 明确 |
| remote database | 本地 database semantics 稳定 |
| multi-db join | 单 db snapshot + view scope 稳定后 |
| Rule persistence / SavedRule | 需要 rule registry / deployment governance |
| view set algebra API | Python set op 成为高频痛点 |

## 18. 设计承诺 Commitments

| # | 承诺 |
|---|---|
| A1 | 最小架构只引入 `Database` / `DatabaseValue` / `SubsetView`(concrete DTO:`FrozenAssertionView`) / `FactGraph runtime` 四个核心概念 |
| A2 | `Database` 是唯一持久写入点;最小版本只 append assertions |
| A3 | `DatabaseValue` immutable,由稳定 `db_id` + content-addressed `tx_id` 定位;`tx_id` 不得由 UUID / 自增序号充当 durable identity |
| A4 | `SubsetView`/`FrozenAssertionView` 是 subset scope,不是 version / branch / working copy |
| A5 | `FrozenAssertionView` 必带 `db_id / base_tx_id / schema_digest / view_digest` |
| A6 | attach 到 `DatabaseValue` 或 `FrozenAssertionView` 的 runtime 第一版 read-only |
| A7 | `view=` 省略时使用 full assertion universe;指定时只看 `view.asrt_ids` |
| A8 | runtime-attached view 与 method-level view 冲突时 raise,不做 nesting |
| A9 | stale / mismatch 必须显式报错,禁止 fallback 到 full universe |
| A10 | EvaluateResult / EvidenceGraph metadata 必须记录 db snapshot + optional view context |
| A11 | branch / writable sub-fg / remote / multi-db / Rule persistence 全部 deferred |
| A12 | `db_id` 由 `Database.create` 生成并持久化;`Database.open(path)` 必须读回同一 `db_id`;in-memory default db 使用非 durable `mem:<uuid4>` |
| A13 | `AssertionRecord` 最小 shape 锁定为 `asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta`;`asrt_id` content-addressed |
| A14 | attach-to-view / attach-to-snapshot 与 read-only enforcement 必须同 ship;禁止出现 scoped runtime 可写的 transient release |
| A15 | rules 是 code artifact,v1 不进 workspace、不进 Database transaction;`FactGraph.attach(...)` 签名不含 `rules=`;rules 通过 `Expr` / `Inference` / `Rule` 内部引用承载,`rule_set_digest` 在 evaluate 时计算并写入 EvaluateResult metadata |
| A16 | schema 分两层:authoring source 属于用户代码(git 治理);compiled snapshot 由 Database 持久化为 `db/objects/schema/<schema_digest>.json`(data 治理,content-addressed) |
| A17 | Database 物理布局 Git-style:`db/objects/` 全部 content-addressed write-once(tx + schema);`db/refs/head.txt` 是唯一 mutable ref file,内容是当前 head `tx_id`;`db/assertions.db` 是 mutable SQLite index layer,可从 `db/objects/tx/` 回放重建,不参与 cross-process identity |
| A18 | SubsetView 物理布局:`views/objects/<view_digest>.json` content-addressed write-once;named view registry(`views/refs/<name>.json`)deferred 到 v2,与 persistent named view 同时落地 |
| A19 | `factgraph_workspace.json` 收缩为最小 manifest:`{workspace_version, components.{db, views}, created_at, last_saved_at}`;`db_id` / `schema_digest` / `data_digest` 不在顶层 manifest 重复 |
| A20 | 现 `registry/` 全部不迁移到新 layout:`registry/rules/` / `registry/inferences/` / `registry/registry_manifest.json` / `registry/authoring_apply_events.jsonl` 移除;`registry/schema/schema_ir.json` 迁到 `db/objects/schema/<schema_digest>.json`;rules 留在用户 Python 代码 |

## 19. 与 `rule-expression-and-proof-attempt.zh.md` 的接缝

主文档继续持有:
- Rule / RuleExpr 设计承诺(C1-C35)
- EvaluateResult / EvaluateRow / EvidenceRef / Explanation contract
- Evidence Phase 1 / Phase 2 API 语义

本文档持有:
- database snapshot identity
- subset view anchor fields
- `view=` scope semantics
- attach runtime read/write boundary
- workspace 物理布局(`db/objects/` + `db/refs/` + `views/objects/`)
- rules 治理边界:rules 不进 Database transaction、不进 workspace v1

需要同步标注到主文档的点:
- `fg.eval.evaluate(..., view=...)` 从 reject 改为 supported
- `fg.read.find(..., view=...)` 从 reject 改为 supported
- EvaluateResult context 增加 `db_id/tx_id/schema_digest/data_digest/view_digest`
- EvidenceGraph.metadata durable copy 同字段
- failure envelope 中 stale / out-of-scope evidence ref 对应本文档 §13
- `rule_set_digest` 仍由 expr 内引用的 rules 在 evaluate 时计算,本文档 attach API 不改变此契约(A15)

---

**一句话总结**:本设计不把 `View` 设计成万能概念。`DatabaseValue` 负责版本,snapshot;`SubsetView` 负责可见 assertion 集合;`FactGraph` 只是 attach 后的 runtime。这个最小边界足够支撑当前 evaluate / explain scope,也不会堵死未来 branch / sub-fg / remote database。
