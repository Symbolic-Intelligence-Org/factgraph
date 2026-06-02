# Schema mutation:additive-only(当前模式)

- Status: working / **current mode locked**(additive-only)/ **future direction open**(destructive surface 未定)
- Authority: candidate design / non-authoritative reference;现状描述属实,未来方向属设计空间
- First draft: 2026-06-02
- Last updated: 2026-06-02
- Scope: `fg.schema.register / extend / apply` 当前 mutation surface;7 类 rejection 的来源(`SchemaNonAdditiveError`);workspace 不变式约束;destructive schema 变更的未来设计空间
- Parent: 与 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md) + [`factgraph-storage-architecture-evolution.zh.md`](factgraph-storage-architecture-evolution.zh.md) 配套
- Design intent: 把 "schema 只能增不能减" 这件事从用户面文档(`docs/quickstart/schema_definition.md`)抽出来,作为设计空间记录;未来若做 destructive surface,此 doc 是起点

---

## §1 当前模式:additive-only

`fg.schema.*` 当前只暴露三个 mutation 方法:`register(EntityCls)` / `extend(EntityCls)` / `apply(EntityCls)`。这三者只做两件事:

- 注册新的 entity type
- 给已注册 entity 加新的非 identity field

任何**破坏性**(destructive)动作 —— 删 entity、删 field、改 field shape、改 identity、迁移 —— 都不在当前 surface 上,且在 mutation runtime(`src/factgraph/application/schema_mutation_runtime.py`)被显式拒绝。

## §2 7 类拒绝(`SchemaNonAdditiveError`,code `SCHEMA_NON_ADDITIVE`)

| 类别 | 例 | 源码位置(`application/schema_mutation_runtime.py`)|
|---|---|---|
| 移除已注册 entity type | declaring fewer entity types than the workspace has | L61-62 |
| 改 identity field | 重命名 / 类型变 / 顺序变 | L63-64 |
| 给已注册 entity 加 identity field | 新增 `Identity()` 声明 | L94-95 |
| 移除 field | 删 `Field()` 声明 | L78-79 |
| 改 field shape | type domain / cardinality / pattern 变 | L80-81 |
| Predicate id 碰撞 | 两声明编译到同一 pred_id,或与已存在冲突 | L71-72 |
| 给已存在 entity 加 `:exists` predicate | 内部 entity-exists predicate 仅在首次 register 时生成 | L96-97 |

(实现层面还有 2 类与 Relationship 相关的拒绝项,Relationship 在 quickstart 不暴露,这里不展开。)

所有拒绝在状态变更之前发生 —— 即使一个 `extend` 调用中混合了"加新 field + 改旧 field"两类操作,**整个调用整体失败**,不会出现部分应用的 schema。

## §3 为什么是 additive-only(当前的设计约束)

### §3.1 Workspace 不变式

每个 workspace 在创建时锚定一个 `schema_digest`(规范化 schema IR 的 SHA-256)。这个 digest 是 workspace 身份的一部分,被多处依赖:

- `factgraph_workspace.json` 清单写入(`db.schema_digest` for Mode B,manifest `schema_digest` for Mode A)
- ledger meta `schema_digest`
- `FactGraph.attach` / `FactGraph.load_workspace` 的 strong correspondence check
- 跨 process 共享 workspace 时的身份对比

若允许破坏性变更,这个 digest **必然**要变化(否则等同改了字段但 digest 还是旧的,signed/replicated 系统会读到不一致)。digest 变意味着:旧 workspace 与新 schema 的关系需要显式建模 —— 这就把"破坏性 schema 变更"问题升级为"workspace 版本迁移"问题。

### §3.2 No-backfill 保证

Ledger 是 append-only。已写入的 assertion 不会被 schema 变更"回填"。这意味着:

- 加新 field → 旧 entity 上读新 field 得 `None`(single)或 `()`(multi),与未写值的语义一致;不破坏既有读契约
- 删 field → 历史 assertion 关联的 pred_id 仍在 ledger 里,但被 schema 移除后,这些 assertion 变成"孤儿":既不能通过 SDK 读取,也不能保证 retract 路径还合法

也就是说,additive 操作天然兼容 append-only ledger;destructive 操作需要单独定义"孤儿 assertion 怎么处理"。

### §3.3 Identity 锁定

Identity 字段在 entity reference(`idref_v1`)的内容寻址中参与计算。改 identity 等同于改 entity 的身份 —— 旧的 `idref_v1` 引用全部失效。当前 runtime 把 identity 改动归到"必须删 entity 再 create"路径(`fg.entities.delete + fg.entities.create`),而非"`fg.schema.*` 在 schema 层动 identity"。

这与 ADR-IC §4.3.6 的 INV-7c(Identity 不可变契约)是同一根。

## §4 用户当下的 workaround

需要非加法性 schema 变更时,当前唯一支持的路径是:

1. 在新位置创建新 workspace(用新 schema)
2. 从旧 workspace 读 assertion(`fg.assertions.*` / `fg.entities.where(...)`)
3. 把读到的 fact 重新写入新 workspace(`fg.entities.create / fg.fields.set/add` 或 Mode B 的 `fg.commit_assertions`)

这条路径的成本随数据量线性增加,且没有原子性保证(中途失败需要业务层处理)。**没有 in-place 迁移工具,没有跨 workspace 数据导入命令**。

`python -m factgraph migrate-workspace` CLI 处理的是 workspace **布局**迁移(旧 registry 目录 → 新 layout),不是 schema 演化。

## §5 未来设计空间(开放问题,无结论)

### §5.1 Destructive operations 的具体语义

如果未来要支持 `fg.schema.delete` / `fg.schema.update` / `fg.schema.deprecate`,有几个待定:

- **删 field**:是真删除(ledger 中 pred_id 的所有 assertion 全部 retract)还是软删除(schema 层下线,assertion 保留作为历史)?
- **删 entity**:连带其上所有 field assertion 全部 retract,还是只下线 entity 而保留 field assertion 作为孤儿?
- **改 field type**:是允许显式类型迁移(转换函数 + 重写 ledger)还是要求新建 field?
- **改 identity**:几乎确定要求 entity 身份变;问题是怎么映射旧 `idref_v1` → 新

### §5.2 Schema 迁移的路径选项

| 选项 | 含义 | 成本 |
|---|---|---|
| A. 保留当前"新 workspace + 重新 ingest" | 不动 `fg.schema.*`;鼓励 backup-friendly workflow | 0;但运维成本高 |
| B. 加 `fg.schema.migrate(plan)` API | 显式 migration plan;runtime 应用并产出新 workspace | 中;需定义 plan 语言 |
| C. 真 in-place mutation | `fg.schema.delete_field(...)` 等;直接改 schema + retract 孤儿 assertion | 高;append-only ledger 上的 destructive 操作语义复杂 |
| D. 多 schema 并存(versioning) | 同 workspace 内多个 schema digest;旧 assertion 关联旧 schema,新 assertion 关联新 | 极高;workspace 身份模型重设计 |

A 是现状;B 是最小增量;C 是工程重负;D 是最雄心但牵涉 ledger schema 重设计。

### §5.3 与其他设计的耦合

- 若 Identity 机制重设计(`identity-mechanism-redesign.zh.md`)支持 alternative lookup keys,destructive identity 变更可能变得可行
- 若 storage architecture(`factgraph-storage-architecture-evolution.zh.md`)分离 ledger 与 view layer,可在 view 层做软删除而不动 ledger
- 若 ledger schema 演化(`ledger-schema-specification.zh.md`)增加 schema-digest 版本链,选项 D 可行性增加

## §6 当前位置的边界

| 属于本 design-point | 不属于 |
|---|---|
| `fg.schema.*` mutation surface 的 additive-only 契约 | 用户面 schema 声明语法(在 `docs/quickstart/schema_definition.md`)|
| 7 类拒绝来源 | 单条 `SchemaNonAdditiveError` 的运行时上下文(应用层 docstring)|
| 为什么 additive(workspace 不变式、no-backfill、identity 锁定)| Identity 机制本身的设计(在 `identity-mechanism-redesign.zh.md`)|
| destructive 未来设计空间(§5)| 任何具体设计决策 — 那是另一份 design-decision / blueprint 的工作 |

## §7 关联代码锚点

- `src/factgraph/application/schema_mutation_runtime.py:21-100` — `_validate_additive_schema_extension` + 9 类(含 Relationship 2 类)rejection raise 站点
- `src/factgraph/sdk/store.py:622-670` — `_SDKSchemaManager`(register / extend / apply / ingest / validate_provenance)
- `src/factgraph/sdk/store.py:1950-1971` — application 层 `SDKStoreError` → `SchemaConflictError` / `SchemaNonAdditiveError` 的边界包装
- `src/factgraph/sdk/store.py:3104-3107` — 超出本 design-point scope 的 superseded class 检测路径
- `src/factgraph/application/workspace_runtime.py:101` — `validate_workspace_manifest` 强制 `components.ledger == "ledger.db"`,Mode A workspace digest 校验路径

## §8 关联文档

- 用户面 schema 声明 + 当前 mutation surface 文档:[`docs/quickstart/schema_definition.md`](../../../../docs/quickstart/schema_definition.md)
- workspace 双模式 + 持久化文档:[`docs/quickstart/load_and_save.md`](../../../../docs/quickstart/load_and_save.md)
- Identity 机制设计:[`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md)
- Storage 架构演化:[`factgraph-storage-architecture-evolution.zh.md`](factgraph-storage-architecture-evolution.zh.md)
- Ledger schema 规范:[`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md)
