# Symir 蓝图提炼到 FactPy 的工作文档

## 目标

本文件用于持续整理 `docs_old/symir_logs/` 中遗留的 Symir 蓝图文档，并只保留对当前 `factpy_kernel` 代码仍然有价值的信息。

整理原则：

- 不复述整篇历史文档，只保留可落到当前代码的有效结论。
- 每条结论都必须显式关联当前代码中的模块、边界或潜在改造点。
- 优先记录能指导重构、API 收口、语义澄清、测试补强和文档统一的信息。
- 若某个历史设计已经被当前实现否定，也要记录为“已不适用”，避免后续重复讨论。

## 当前 FactPy 模块对照

在提炼时，优先把历史设计映射到以下模块：

- `src/factpy_kernel/core`: 运行时语义内核，包含 schema / store / rules / derivation / policy / view。
- `src/factpy_kernel/authoring`: schema/rule/derivation 的编译、预检、发布与 registry 工作流。
- `src/factpy_kernel/application`: 面向上层编排的中间运行层。
- `src/factpy_kernel/sdk`: Python 侧用户 API、DSL、读写 facade、query/rule/derivation 调用入口。
- `src/factpy_kernel/adapters`: Souffle / ProbLog 等后端适配。
- `src/factpy_kernel/service`: 服务层接口与对外交付面。
- `src/factpy_kernel/audit`: 审计与辅助输出能力。

## 待整理文档清单

状态说明：

- `pending`: 尚未整理
- `done`: 已提炼并写入下方记录
- `skip`: 与当前项目关联极弱，明确跳过

| 状态 | 源文档 |
| --- | --- |
| pending | `docs_old/symir_logs/0. 生成langda提示词.md` |
| done | `docs_old/symir_logs/1. Fact Rel.md` |
| pending | `docs_old/symir_logs/2. ArgSpec 语法糖.md` |
| pending | `docs_old/symir_logs/3. Fact Rel schema调整.md` |
| pending | `docs_old/symir_logs/4. FactLayer and Registry.md` |
| pending | `docs_old/symir_logs/5. fact rel和llm的兼容.md` |
| pending | `docs_old/symir_logs/6. Instances.md` |
| pending | `docs_old/symir_logs/7. rel语法讨论.md` |
| pending | `docs_old/symir_logs/8. CSV.md` |
| pending | `docs_old/symir_logs/9. rel CSV.md` |
| pending | `docs_old/symir_logs/10. Instance Keys.md` |
| pending | `docs_old/symir_logs/11. Rel 的滞后性.md` |
| pending | `docs_old/symir_logs/12. instance merge and meta.md` |
| pending | `docs_old/symir_logs/13. CSV.md` |
| pending | `docs_old/symir_logs/14.Rule.md` |
| pending | `docs_old/symir_logs/15. Rule convention.md` |
| pending | `docs_old/symir_logs/16. schema and rule.md` |
| pending | `docs_old/symir_logs/17. rule 数据验证.md` |
| pending | `docs_old/symir_logs/18. 从持久化数据创建.md` |
| pending | `docs_old/symir_logs/19. schema ID 更改.md` |
| pending | `docs_old/symir_logs/20. Ledger SQLite 持久化.md` |
| pending | `docs_old/symir_logs/ME CODEX.md` |
| pending | `docs_old/symir_logs/er.md` |
| pending | `docs_old/symir_logs/er_recipes.md` |

## 提炼记录模板

后续每篇文档按以下结构追加：

### 文档：`docs_old/symir_logs/<文件名>`

**1. 原始关注点**

- 历史文档试图解决的问题。

**2. 对当前 FactPy 仍然有效的思想**

- 保留真正可迁移的设计要点。

**3. 与当前代码的对应位置**

- 明确关联的模块、文件或 API。

**4. 可执行优化建议**

- 只写可以转化为代码、测试、接口或文档工作的事项。

**5. 结论**

- `adopt`: 建议尽快吸收
- `consider`: 值得保留为后续演进方向
- `reject`: 已被当前实现否定或不再适用

## 提炼记录

### 文档：`docs_old/symir_logs/1. Fact Rel.md`

**1. 原始关注点**

- 试图把 schema 分成两类一等公民：`Fact` 表示任意 arity 的事实，`Rel` 表示固定 `sub/obj` 的二元关系。
- 希望通过 `ArgSpec` 的命名、`role`、`namespace` 让参数名、主键选择和图数据库映射更稳定。
- 希望关系实例可以引用先前实例，而不是只靠常量 terms 拼接。
- 很早就提出实例级元数据需求：`source / timestamp / confidence / status`，目标是支撑回滚、重摄取、冲突处理和时间切片。
- 希望 rule 层能直接表达面向关系的 head 结构，便于类 Cypher 的关系生成与图后端协作。

**2. 对当前 FactPy 仍然有效的思想**

- “关系建模”确实需要显式设计，而不能只停留在字段层拼接。这个问题在当前项目里仍未完全收口。
- 关系引用必须是稳定、可序列化、可跨进程恢复的引用，而不是内存对象引用。这个方向与当前 `idref_v1` 完全一致。
- 证据级元数据应该和业务 identity 解耦，放在写入 meta / ledger 层，而不是塞进实体主键。这一点当前实现已经验证是正确方向。
- 关系与实体可以共享底层存储模型，但上层最好有额外的“语义标注”来表达端点、方向和图投影用途。
- Neo4j / 图投影兼容性真正需要的是稳定的端点语义、属性映射和导出约定，而不一定需要在 core schema 里重新引入 `Rel` 类型。

**3. 与当前代码的对应位置**

- 当前关系建模口径已经落在 reified record 模式：`src/factpy_kernel/sdk/docs/00_user_guide.md` 明确说明“关系节点只是一种用法约定”。
- `src/factpy_kernel/sdk/schema.py` 把 `Entity` 子类字段统一编译成 `entity_ref`，这已经覆盖了“关系端点引用”的底层能力。
- `src/factpy_kernel/authoring/schema_compile.py` 会把每个 `Entity` 展开为 `<T>:exists`、identity predicates、field predicates；现有编译链路没有 `Fact/Rel` 分叉。
- `src/factpy_kernel/core/protocol/idref_v1.py` 和 `src/factpy_kernel/application/schema_runtime.py` 已提供稳定实体引用编码，等价于旧文想要的可序列化 `InstanceRef` 方向。
- `src/factpy_kernel/core/evidence/write_protocol.py`、`src/factpy_kernel/core/store/ledger.py`、`src/factpy_kernel/sdk/ingest.py`、`src/factpy_kernel/core/view/confidence.py` 已经承接了旧文提出的大部分实例级元数据需求。
- `src/factpy_kernel/application/docs/01_overview.md` 仍明确写着 `graph projection / relationship family / binding` 尚未完整实现，这正是旧文今天最值得继续推进的部分。

**4. 可执行优化建议**

- 在当前 `Entity + entity_ref` 主模型不变的前提下，补一份“关系建模约定”文档，明确 reified relationship entity 的推荐写法：两个端点字段、方向、可选关系属性、推荐 meta。
- 在 `authoring` 或 `application` 层增加可选的非语义关系标注，而不是改动 core schema 结构。例如给 entity/field 增加 tags 或 metadata，用来声明哪个字段是 `src`、哪个字段是 `dst`、是否用于 graph projection。
- 为未来的 `graph projection / relationship family / binding` 设计直接复用这些标注，避免再引入一套新的 `Rel` 存储类型。
- 在 SDK 文档和测试里进一步强调：关系引用应使用同一事务内 handle 或 `idref_v1`，不要抽象成内存对象引用语义。
- 若后续确实需要 Neo4j 导出，优先在 adapter / projection 层定义 label、edge type、property 映射规则，不要把 Neo4j 风格的 `Fact/Rel` 分型下沉到 `schema_ir` v1。
- 不建议回退实现旧文中的 `Fact/Rel` 双类型、`ArgSpec("City:string")` 语法糖或 schema 级 `sub/obj` 专用结构；这些设计会直接冲击当前 `Entity -> predicates -> SchemaIndex` 的稳定编译链路，收益小于迁移成本。

**5. 结论**

- `consider`：这篇文档提出的问题今天仍然成立，但应吸收到“关系建模约定、关系标注、图投影/导出层”中，而不是回到 core schema 做 `Fact/Rel` 双轨重构。
