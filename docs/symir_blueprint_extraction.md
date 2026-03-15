# Symir 蓝图提炼到 FactPy 的工作文档

## 目标

本文件用于持续整理 `docs_old/symir_logs/` 中遗留的 Symir 蓝图文档，并只保留对当前 `factpy_kernel` 代码仍然有价值的信息。

整理原则：

- 不复述整篇历史文档，只保留可落到当前代码的有效结论。
- 每条结论都必须显式关联当前代码中的模块、边界或潜在改造点。
- 优先记录能指导重构、API 收口、语义澄清、测试补强和文档统一的信息。
- 若某个历史设计已经被当前实现否定，也要记录为"已不适用"，避免后续重复讨论。

## 当前 FactPy 模块对照

在提炼时，优先把历史设计映射到以下模块：

| 模块路径 | 职责 |
| --- | --- |
| `src/factpy_kernel/core` | 运行时语义内核，包含 schema / store / rules / derivation / policy / view |
| `src/factpy_kernel/authoring` | schema/rule/derivation 的编译、预检、发布与 registry 工作流 |
| `src/factpy_kernel/application` | 面向上层编排的中间运行层（entity-centric runtime） |
| `src/factpy_kernel/sdk` | Python 侧用户 API、DSL、读写 facade、query/rule/derivation 调用入口 |
| `src/factpy_kernel/adapters` | Souffle / ProbLog 等后端适配 |
| `src/factpy_kernel/service` | 服务层接口与对外交付面 |
| `src/factpy_kernel/audit` | 审计与辅助输出能力 |

## 待整理文档清单

状态说明：

- `pending`: 尚未整理
- `done`: 已提炼并写入下方记录
- `skip`: 与当前项目关联极弱，明确跳过

| 状态 | 源文档 |
| --- | --- |
| pending | `docs_old/symir_logs/0. 生成langda提示词.md` |
| done | `docs_old/symir_logs/1. Fact Rel.md` |
| done | `docs_old/symir_logs/2. ArgSpec 语法糖.md` |
| done | `docs_old/symir_logs/3. Fact Rel schema调整.md` |
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

---

## 提炼记录

---

### 文档：`docs_old/symir_logs/1. Fact Rel.md`

#### 1. 原始关注点

symir 早期尝试在 schema 层区分两类一等公民：

- **Fact**：任意 arity 的事实（例如 `Person(name, age, city)`）
- **Rel**：固定 `sub/obj` 的二元关系（例如 `LivesIn(person, city)`）

文档核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| ArgSpec 命名与角色 | 希望通过 `ArgSpec` 的 `role`、`namespace` 让参数名、主键选择和图数据库映射更稳定 |
| 关系实例引用 | 希望关系实例可以引用先前实例，而不是只靠常量 terms 拼接 |
| 实例级元数据 | 很早就提出 `source / timestamp / confidence / status` 需求，用于回滚、重摄取、冲突处理和时间切片 |
| Rule 层关系表达 | 希望 rule 层能直接表达面向关系的 head 结构，便于类 Cypher 的关系生成与图后端协作 |
| Neo4j 兼容 | 希望 schema 能直接映射到 Neo4j 的节点/边模型 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| 关系引用必须是稳定、可序列化、可跨进程恢复的引用 | `idref_v1` 协议已实现，完全满足此需求 |
| 证据级元数据应与业务 identity 解耦 | 当前 `meta` / `ledger` 层设计已验证正确 |
| 关系与实体可共享底层存储模型 | 当前 `Entity` 统一模型已验证可行 |

**◐ 部分实现，仍需完善：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 关系建模需要显式设计 | 当前只有 reified record 约定，无显式语义标注 | 缺少 `src/dst` 端点标注 |
| 上层需要语义标注表达端点、方向和图投影用途 | `Entity.Meta` 目前只支持 `version/description/tags` | 未支持 `relationship_role` 等标注 |
| 图投影/导出需要稳定的端点语义和属性映射 | `application` 层的 `graph_projection.py` 尚未实现 | 待实现 |

**✗ 不建议采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| `Fact/Rel` 双类型在 core schema 层分叉 | 会冲击当前 `Entity -> predicates -> SchemaIndex` 稳定编译链路 |
| `ArgSpec("City:string")` 语法糖 | 收益小于迁移成本，且当前 `Identity/Field` 已足够清晰 |
| schema 级 `sub/obj` 专用结构 | 应通过标注实现，而非改动 schema_ir 结构 |

#### 3. 与当前代码的对应位置

**3.1 关系建模的当前实现口径**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| Reified Record 约定 | `src/factpy_kernel/sdk/docs/00_user_guide.en.md` § 2.4 | 明确说明"关系节点只是一种用法约定" |
| Entity 子类字段编译 | `src/factpy_kernel/sdk/schema.py` | 把 `Entity` 子类字段统一编译成 `entity_ref` |
| 谓词展开 | `src/factpy_kernel/authoring/schema_compile.py` | 每个 `Entity` 展开为 `<T>:exists`、identity predicates、field predicates |

**3.2 稳定实体引用**

| 关注点 | 当前代码位置 |
| --- | --- |
| `idref_v1` 编码协议 | `src/factpy_kernel/core/protocol/idref_v1.py` |
| Schema 运行时索引 | `src/factpy_kernel/application/schema_runtime.py` |
| 运行时测试覆盖 | `src/factpy_kernel/tests/test_application_schema_runtime.py` |

**3.3 实例级元数据**

| 关注点 | 当前代码位置 |
| --- | --- |
| 写入协议 | `src/factpy_kernel/core/evidence/write_protocol.py` |
| Ledger 存储 | `src/factpy_kernel/core/store/ledger.py` |
| SDK Ingest | `src/factpy_kernel/sdk/ingest.py`（包含 `CONVENTION_META_KEYS`、`SENSITIVE_SEMANTIC_META_KEYS`） |
| Confidence 聚合 | `src/factpy_kernel/core/view/confidence.py` |
| Meta 类型分类 | Souffle adapter 的 `meta_str/meta_int/meta_float/meta_bool/meta_time.facts` |

**3.4 尚未完成的部分**

根据 `src/factpy_kernel/application/docs/01_overview.md`，以下能力仍属于 blueprint 中声明但尚未落地的能力；当前仓库里还没有对应模块文件：

- `query_view.py`
- `authoring_normalize.py`
- `graph_projection.py` ← **与旧文直接相关**
- `binding.py` ← **与旧文直接相关**

#### 4. 可执行优化建议

**4.1 文档层（低风险，可立即执行）**

| 建议 | 预期产出 | 关联文件 |
| --- | --- | --- |
| 补充"关系建模约定"文档 | 明确 reified relationship entity 的推荐写法 | 新建 `src/factpy_kernel/sdk/docs/04_relationship_modeling.md` |
| 在约定文档中明确：两个端点字段、方向、可选关系属性、推荐 meta | 统一关系写法 | 同上 |
| 强调关系引用应使用 `idref_v1` 而非内存对象引用 | 避免误用 | 更新 `00_user_guide.en.md` |

**4.2 标注层（中等风险，需设计评审）**

| 建议 | 实现方式 | 关联模块 |
| --- | --- | --- |
| 在 `Entity.Meta` 中支持可选的关系标注 | 扩展 `Meta` 支持 `relationship_config` | `sdk/schema.py`、`authoring/schema_compile.py` |
| 标注内容：`src_field`、`dst_field`、`direction`、`graph_projection_enabled` | 非语义标注，不影响 core schema 结构 | 同上 |
| 在 `Field` 中支持可选的角色标注 | 扩展 `Field` 支持 `role="src"` / `role="dst"` | 同上 |

示例设计：

```python
class LivesIn(Entity):
    class Meta:
        version = "v1"
        relationship_config = {
            "src_field": "user",
            "dst_field": "country",
            "direction": "outgoing",
        }
    
    uid: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single", role="src")
    country: Country = Field(cardinality="single", role="dst")
    since: int = Field(cardinality="single")
```

**4.3 Graph Projection 层（较高风险，需分阶段实现）**

| 建议 | 实现位置 | 依赖 |
| --- | --- | --- |
| 在 `application` 层实现 `graph_projection.py` | `src/factpy_kernel/application/graph_projection.py` | 依赖标注层 |
| 图投影输出格式：Neo4j-compatible JSON / CSV | 同上 | 无 |
| Adapter 层定义 label、edge type、property 映射规则 | `src/factpy_kernel/adapters/neo4j/` (新建) | 依赖 graph_projection |

**4.4 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 回退实现 `Fact/Rel` 双类型 | 冲击 `Entity -> predicates -> SchemaIndex` 编译链路 |
| 把 `sub/obj` 专用结构下沉到 `schema_ir` | 应通过标注实现，保持 schema_ir 简洁 |
| 在 core 层引入 Neo4j 风格分型 | 应在 adapter/projection 层处理 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| Schema 编译 | 关系标注正确传递到 `schema_ir` | `authoring/schema_compile.py` |
| SDK 写入 | 关系实体的端点字段正确写入 | `sdk/ingest.py` |
| 图投影 | 从 `schema_ir` + `ledger` 正确生成图结构 | `application/graph_projection.py` |
| 适配器导出 | 图结构正确导出为 Neo4j 格式 | `adapters/neo4j/` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档提出的问题今天仍然成立 |

**吸收路径：**

1. **短期**：补充"关系建模约定"文档，统一当前 reified record 写法
2. **中期**：在 `Entity.Meta` / `Field` 中增加可选的关系标注，不改动 core schema 结构
3. **长期**：实现 `graph_projection.py` 和 `binding.py`，复用标注信息

**不建议的路径：**

- 回到 core schema 做 `Fact/Rel` 双轨重构
- 在 `schema_ir` 中引入 `sub/obj` 专用字段

---

### 文档：`docs_old/symir_logs/2. ArgSpec 语法糖.md`

#### 1. 原始关注点

这篇文档的核心提议很集中：

- 把 `ArgSpec` 的输入参数从显式 `datatype` 改成 `spec`
- 允许用类似 `"Name:type"` 的单字符串同时表达“参数名 + 数据类型”
- 在输入阶段把 `spec` 解析成标准化的 `name` 和 `datatype`

本质上，它想解决的是"schema 声明太啰嗦，名称和类型分开写不够顺手"的问题。

附带改动：旧文同时把内部字段名从 `arg_name` 统一为 `name`——这一命名统一思路在当前 FactPy 中已体现为 `identity_fields[].name` 与 `fields[].py_name` 的分层命名约定。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 输入层应尽早把“字段名”和“类型”拆成 canonical 结构 | 当前 SDK 和 schema DSL 都已经这样做，只是通过 Python 标注而不是字符串 spec |
| schema 声明需要稳定的 name/type 规范化结果 | `sdk/schema.py` 与 `authoring/schema_dsl_parse.py` 都会把声明降成 `name/py_name + type_domain` |

**◐ 仍有参考价值的部分：**

| 思想 | 当前状态 | 可借鉴之处 |
| --- | --- | --- |
| 面向文本输入或 LLM authoring 的 schema 书写需要更短的表示法 | 当前 authoring DSL 仍要求标准 Python 风格类定义 | 若以后做 prompt/UI 输入层，可考虑提供 `"field:type"` 级别的预归一化 sugar |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在 `Identity(...)` / `Field(...)` 里增加 `spec=\"Name:type\"` 位置参数或字符串语法糖 | 当前 schema 声明已经把“名字”交给 Python 字段名、把“类型”交给注解；再引入一套字符串 spec 只会制造双轨语法 |
| 把 `ArgSpec` 风格字符串下沉为 runtime/schema_ir 的一部分 | `schema_ir` 当前只接受规范化后的 `name/py_name/type_domain`，没有必要再保存原始 sugar |

#### 3. 与当前代码的对应位置

**3.1 名称和类型的分离方式**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SDK 声明路径 | `src/factpy_kernel/sdk/schema.py` | 字段名来自类属性名，类型来自 Python 注解；`_annotation_to_type_domain_runtime()`（≈L294）负责把 `str/int/bool/datetime/UUID` 等 Python 类型映射到 canonical `type_domain` |
| Authoring schema DSL | `src/factpy_kernel/authoring/schema_dsl_parse.py` | `field_name: type = Identity(...) / Field(...)` 是 canonical 入口 |
| Schema 编译 | `src/factpy_kernel/authoring/schema_compile.py` | `_compile_identity_field()` 输出 `{name, type_domain}`；`_compile_field()` 输出 `{py_name, type_domain, cardinality}` |

**3.2 当前 DSL 为什么不需要 `ArgSpec("Name:type")`**

| 当前机制 | 代码位置 |
| --- | --- |
| Python 注解到 `type_domain` 的映射 | `sdk/schema.py: _annotation_to_type_domain_runtime()`、`authoring/schema_dsl_parse.py` |
| 显式禁止位置参数 | `authoring/schema_dsl_parse.py: _parse_call_kwargs()`（≈L246，遇到 `call.args` 非空时直接报错） |
| 文档中的推荐写法 | `src/factpy_kernel/sdk/docs/00_user_guide.md`、`src/factpy_kernel/authoring/docs/01_overview.md` |

当前口径下，下面这种写法已经等价表达了旧文想要的“名字 + 类型”：

```python
class EmploymentEvent(Entity):
    event_id: str = Identity(primary_key=True)
    company: str = Field(cardinality="single")
```

这里：

- `event_id` / `company` 已经承担“name”
- `str` 已经承担“datatype”
- `Identity(...)` / `Field(...)` 只保留行为参数

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 不要给 `Identity` / `Field` 增加 `spec` 字符串参数 | 会和当前 Python 注解声明形成双轨入口 |
| 不要让 authoring schema DSL 接受位置参数 | 当前 parser 已明确拒绝位置参数，错误模型更稳定 |

**4.2 可考虑吸收的窄范围优化**

| 建议 | 适用层 | 说明 |
| --- | --- | --- |
| 若未来做 LLM/schema 文本输入，可增加一个"输入归一化器" | `authoring` 外围或 DSL bridge 前置层 | 只把 `"age:int"` 之类短写法展开成标准 authoring payload，不改 `sdk/schema.py`、`authoring/schema_dsl_parse.py` 或 `schema_ir` |
| 在 authoring 文档补一句设计说明 | 文档层 | 明确当前系统为什么选择"字段名 + Python 注解"，而不是 `ArgSpec spec` |

**4.3 更适合当前项目的等价优化方向**

| 方向 | 理由 |
| --- | --- |
| 保持声明语义单一：字段名来自 Python 标识符，类型来自注解，行为来自 `Identity/Field` 参数 | 这比字符串 spec 更利于 AST 解析、静态检查和错误定位 |
| 若要降低 authoring 门槛，优先做 schema 输入的预处理工具，而不是改 core authoring contract | 风险更低，也不会污染 `schema_ir` 与 SDK surface |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **reject** | 作为当前 FactPy 核心 schema API 设计，这篇文档的 `ArgSpec spec` 方案已被更清晰的“Python 字段名 + 类型注解”模式替代；仅在未来的 LLM/UI 输入预处理层保留参考价值 |

---

### 文档：`docs_old/symir_logs/3. Fact Rel schema调整.md`

#### 1. 原始关注点

这篇文档开始把 `Fact/Rel` 从“声明形式”进一步推进到“freeze 后的 canonical schema 结构”。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| 单个 schema 的稳定指纹 | 为每个 `Fact` / `Rel` 生成独立 `schema_id`，且只由结构字段参与 hash，不受 `description` 影响 |
| 显式 key 定义 | 为 `Fact` 固化 `key_fields`，复合键顺序按 signature 出现顺序固定 |
| 关系端点 freeze | `Rel` 在用户侧可用对象引用声明，但 freeze 后只能保留 `sub_schema_id` / `obj_schema_id` |
| 派生签名 | `Rel.signature` 不手写，而是在 freeze 时由端点 key + props 自动生成 `derived_signature` |
| 运行时脱离对象引用 | 避免循环引用、序列化困难和 session 内对象依赖 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 结构指纹应建立在 canonical schema 上，而不是文案字段上 | 当前已有整份 `schema_ir` 级别的 `schema_digest(...)` |
| 运行时不能依赖对象引用，必须落到稳定可序列化标识 | 当前已经统一到 `idref_v1`、registry JSON、compiled `schema_ir` |
| key / identity 的顺序必须稳定 | `SchemaIndex.identity_fields` 保留声明顺序，`encode_idref_v1(...)` 依赖有序 identity tuples |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| “字段级/实体级的局部结构摘要”有时比全局 `schema_digest` 更适合 diff、映射和导出 | 当前只有全局 `schema_digest`，没有 entity/predicate 粒度的签名摘要 | 可作为 authoring/registry 的派生元数据 |
| 关系 schema 的“派生扁平签名”适合做 graph/export 视图 | 当前关系仍以普通 `Entity` + `entity_ref` 字段表达 | 若未来做 graph projection，可在 projection 层生成 derived relationship signature |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在 `Entity.Meta` 或 schema DSL 中重新引入显式 `schema_id` | 当前文档和实现都明确：`entity_type` 由类名推导，`schema_id` 不属于声明 contract |
| 用 `schema_id` 取代 `entity_type` / `pred_id` 成为核心运行时标识 | 当前 `SchemaIndex`、query/rule lowering、service/API 全部围绕可读的 `entity_type` / `pred_id` 工作 |
| 为 core `schema_ir` 增加 `Fact/Rel/endpoints/derived_signature` 新结构 | 会打破当前稳定的 `entities + predicates + projection` canonical 形态 |

#### 3. 与当前代码的对应位置

**3.1 当前项目如何表达“结构身份”**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 全局 schema 指纹 | `src/factpy_kernel/core/schema/schema_ir.py` 中的 `schema_digest(...)` | 基于 canonicalized `schema_ir` 计算，不依赖 description 文案 |
| SchemaIndex 持有指纹 | `src/factpy_kernel/application/schema_runtime.py` 中的 `build_schema_index(...)` | 运行时只缓存全局 `schema_digest`，不缓存 entity/predicate 级局部 digest |
| registry / runtime 使用 digest | `src/factpy_kernel/authoring/registry_fs.py`、`src/factpy_kernel/sdk/store.py` | digest 已用于 registry 与 wire/runtime 校验 |

**3.2 当前项目如何表达“key_fields”**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 声明期主键语义 | `src/factpy_kernel/sdk/schema.py` 中 `Identity(primary_key=True)` | 当前没有单独 `key_fields` 列表，而是把 key 语义挂在 identity 字段上 |
| 编译期保留主键标记 | `src/factpy_kernel/authoring/schema_compile.py` 中 `_compile_identity_field()` / `_compile_identity_predicate()` | `primary_key=True` 会进入 compiled entity 与 predicate |
| Rule 侧 key 使用 | `src/factpy_kernel/authoring/where_schema_lowering.py` | 跨坐标比较只允许使用 `primary_key` 字段 |

**3.3 当前项目如何避免对象引用进入运行时**

| 关注点 | 当前代码位置 |
| --- | --- |
| 稳定实体引用协议 | `src/factpy_kernel/core/protocol/idref_v1.py` |
| 应用层实体引用物化 | `src/factpy_kernel/application/schema_runtime.py` |
| SDK 文档中的显式边界 | `src/factpy_kernel/sdk/docs/00_user_guide.md` |

**3.4 与旧文直接相关的一个当前细节**

| 观察 | 当前代码位置 | 影响 |
| --- | --- | --- |
| 复合 `primary_key` 的列表目前在 `_build_record_meta()` 中经过 `sorted(set(primary_keys))` | `src/factpy_kernel/authoring/where_schema_lowering.py` | 现在仍然确定性，但不再严格保留声明顺序；若未来要做复合 key 的 digest / graph export，这一点需要收口 |

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 继续把 `entity_type` / `pred_id` 作为核心可读标识 | 这是当前 API、编译器和 service 协议的公共语言 |
| 把结构指纹控制在“派生元数据”层，而不是“声明必填字段”层 | 避免把 hash 驱动的 opaque id 推进主 authoring contract |

**4.2 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若确实需要局部 schema 指纹，增加 `entity_signature_digest` / `predicate_signature_digest` 这类派生元数据 | `authoring` / `registry` 层 | 从 canonical compiled rows 计算，不进入 `Entity.Meta`，不替代 `entity_type` / `pred_id` |
| 为关系导出/图投影定义“derived relationship signature” | 未来的 `application` graph projection 或 adapter 层 | 从端点标注 + props 派生，不改 `schema_ir` 顶层结构 |
| 收口复合 `primary_key` 顺序语义 | `src/factpy_kernel/authoring/where_schema_lowering.py` | 若项目要支持复合 key 的稳定映射，建议从 `sorted(set(...))` 改为“按声明顺序去重” |

**4.3 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 在当前 SDK schema API 中暴露 `schema_id=hash(...)` | 用户需要记忆更多内部机制，且与类名/字段名双重标识重复 |
| 让 `Rel` 在 core schema 中拥有专属 `endpoints/props/derived_signature` 结构 | 当前 `entities/predicates` 双表结构已经稳定，专属结构会放大迁移面 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| Schema digest 稳定性 | 修改 `description/tags` 是否按预期影响或不影响指纹 | `core/schema/schema_ir.py`、`authoring/registry_fs.py` |
| 主键顺序稳定性 | 多 `primary_key` 字段是否按声明顺序保留 | `authoring/where_schema_lowering.py`、`application/schema_runtime.py` |
| 局部签名派生 | 若新增 entity/predicate digest，字段重排/文案改动的影响是否符合设计 | `authoring` / `registry` 新增逻辑 |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档真正有价值的是“canonical freeze、局部结构摘要、复合 key 顺序”这些工程原则，而不是把 `schema_id` 推成当前核心 schema API |

**更适合当前项目的吸收路径：**

1. 保持 `entity_type` / `pred_id` / `primary_key` 主模型不变。
2. 若确有 registry diff、graph export、局部缓存需求，再在 authoring/registry 层补充派生签名摘要。
3. 在做 relationship projection 前，先把复合 key 的顺序语义收口成“声明顺序稳定”。

---

## 附录：术语对照

| Symir 术语 | FactPy 当前对应 |
| --- | --- |
| `Fact` | `Entity`（任意字段） |
| `Rel` | `Entity`（reified relationship，包含两个 `entity_ref` 端点字段） |
| `ArgSpec` | `Identity` / `Field` |
| `InstanceRef` | `idref_v1` token |
| `instance meta` | `meta` / `ledger` 层 |
| `sub/obj` | 通过标注 `role="src"` / `role="dst"` 表达（待实现） |
