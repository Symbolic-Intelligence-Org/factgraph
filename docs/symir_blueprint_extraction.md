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
| done | `docs_old/symir_logs/4. FactLayer and Registry.md` |
| done | `docs_old/symir_logs/5. fact rel和llm的兼容.md` |
| done | `docs_old/symir_logs/6. Instances.md` |
| done | `docs_old/symir_logs/7. rel语法讨论.md` |
| done | `docs_old/symir_logs/8. CSV.md` |
| done | `docs_old/symir_logs/9. rel CSV.md` |
| done | `docs_old/symir_logs/10. Instance Keys.md` |
| done | `docs_old/symir_logs/11. Rel 的滞后性.md` |
| done | `docs_old/symir_logs/12. instance merge and meta.md` |
| done | `docs_old/symir_logs/13. CSV.md` |
| done | `docs_old/symir_logs/14.Rule.md` |
| done | `docs_old/symir_logs/15. Rule convention.md` |
| done | `docs_old/symir_logs/16. schema and rule.md` |
| done | `docs_old/symir_logs/17. rule 数据验证.md` |
| done | `docs_old/symir_logs/18. 从持久化数据创建.md` |
| done | `docs_old/symir_logs/19. schema ID 更改.md` |
| done | `docs_old/symir_logs/20. Ledger SQLite 持久化.md` |
| skip | `docs_old/symir_logs/ME CODEX.md` |
| done | `docs_old/symir_logs/er.md` |
| done | `docs_old/symir_logs/er_recipes.md` |

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
| 结构指纹应建立在 canonical schema 上 | 当前已有 `schema_digest(...)`，但注意它 hash 的是**整份** `schema_ir`（含 `generated_at`、entity/predicate 内的 `description`/`tags`），并非旧文所想的"只由结构字段参与 hash"——见下方 §3.1 详述 |
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
| 全局 schema 指纹 | `schema_ir.py: schema_digest(...)` (L76) → `canonicalize_schema_ir_jcs()` (L62) | hash 对象是**整份** validated `schema_ir`（JCS 序列化后 SHA-256）。`schema_ir` 包含 `generated_at`、entity/predicate 内可选的 `description`/`tags`，因此同一结构重新编译会产生不同 digest——这与旧文"只由结构字段参与 hash"的目标有偏差 |
| SchemaIndex 持有指纹 | `schema_runtime.py: build_schema_index(...)` (L82, digest 赋值 L218) | 运行时只缓存全局 `schema_digest`，不缓存 entity/predicate 级局部 digest |
| registry 使用 digest | `authoring/registry_fs.py: upsert_schema_ir()` (L44) | digest 作为 content-addressable 版本标识写入 manifest |
| SDK store 使用 digest | `sdk/store.py` (L99 缓存, L130 校验) | 初始化时缓存 digest，后续与 ledger 中存储的 digest 比对，不匹配则拒绝打开 |

**3.2 当前项目如何表达“key_fields”**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 声明期主键语义 | `sdk/schema.py` 中 `Identity(primary_key=True)` | 当前没有单独 `key_fields` 列表，而是把 key 语义挂在 identity 字段上 |
| 编译期保留主键标记 | `schema_compile.py: _compile_identity_field()` (≈L200) / `_compile_identity_predicate()` (L164, primary_key 标记 L195) | `primary_key=True` 会同时进入 compiled entity 的 `identity_fields` 与对应 predicate |
| Rule 侧 key 使用 | `where_schema_lowering.py: _build_record_meta()` (L31) / `_rewrite_attr_eq_atom()` (L217) | `attr_eq` 跨坐标比较只允许使用 `primary_key` 字段；主键列表提取逻辑在 L46-57 |

**3.3 当前项目如何避免对象引用进入运行时**

| 关注点 | 当前代码位置 |
| --- | --- |
| 稳定实体引用协议 | `src/factpy_kernel/core/protocol/idref_v1.py` |
| 应用层实体引用物化 | `src/factpy_kernel/application/schema_runtime.py` |
| SDK 文档中的显式边界 | `src/factpy_kernel/sdk/docs/00_user_guide.md` |

**3.4 与旧文直接相关的一个当前细节**

| 观察 | 当前代码位置 | 影响 |
| --- | --- | --- |
| 复合 `primary_key` 的列表在 `_build_record_meta()` L57 经过 `sorted(set(primary_keys))` | `where_schema_lowering.py` L57 | 确定性没问题，但不保留声明顺序；若未来做复合 key 的 digest / graph export，这里需收口为"按声明顺序去重"（`dict.fromkeys(primary_keys)` 即可） |

**3.5 当前 `schema_digest` 与旧文 `schema_id` 的关键差异**

旧文想要的 `schema_id` 是"纯结构指纹"：`hash(canonical_json({kind, name, signature, key_fields}))`，显式排除 `description`。

当前 `schema_digest` 的实际行为：

| 维度 | 旧文 `schema_id` | 当前 `schema_digest` |
| --- | --- | --- |
| hash 输入 | 只含结构字段（kind/name/signature/key_fields） | 整份 `schema_ir`（含 `generated_at`、entity/predicate 内可选的 `description`/`tags`） |
| 粒度 | 每个 `Fact` / `Rel` 各自独立 | 全局唯一（整份 schema 一个 digest） |
| 重编译稳定性 | 相同结构 → 相同 id | 相同结构重新编译 → `generated_at` 不同 → digest 不同 |

如果将来需要"纯结构指纹"（例如 registry diff 或 graph export 的缓存键），需要另做一个排除 `generated_at`/`description`/`tags` 的 structural digest，而非直接复用当前 `schema_digest`。

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 继续把 `entity_type` / `pred_id` 作为核心可读标识 | 这是当前 API、编译器和 service 协议的公共语言 |
| 把结构指纹控制在"派生元数据"层，而不是"声明必填字段"层 | 避免把 hash 驱动的 opaque id 推进主 authoring contract |

**4.2 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若确实需要局部 schema 指纹，增加 `entity_signature_digest` / `predicate_signature_digest` 这类派生元数据 | `authoring` / `registry` 层 | 从 canonical compiled rows 计算，排除 `generated_at`/`description`/`tags`；不进入 `Entity.Meta`，不替代 `entity_type` / `pred_id` |
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
2. 注意当前 `schema_digest` 并非"纯结构指纹"（含 `generated_at`/`description`/`tags`）；若需要 registry diff 或 graph export 的缓存键，应另做 structural digest。
3. 若确有局部缓存需求，在 authoring/registry 层补充 entity/predicate 粒度的派生签名摘要。
4. 在做 relationship projection 前，先把复合 key 的顺序语义收口成"声明顺序稳定"（`where_schema_lowering.py` L57 `sorted(set(...))` → `dict.fromkeys(...)`）。

---

### 文档：`docs_old/symir_logs/4. FactLayer and Registry.md`

#### 1. 原始关注点

这篇文档讨论的重点已经不是 `Fact/Rel` 自身格式，而是 registry 在“构造即冻结”之后应该承担什么职责。

旧文的核心诉求：

| 诉求 | 描述 |
| --- | --- |
| name-based 访问 | 用户和规则写法按 name 查 schema；底层回放仍按 `schema_id` |
| load 强校验 | 从 dict/load 重建时必须校验输入 `schema_id` 与重算值一致，避免 silently wrong |
| duplicate 检测简化 | 不再用“字段拼 key”判重，而是直接围绕 `schema_id` / `name` 唯一性 |
| registry 降级 | 在 eager-freeze 前提下，registry 只做索引、校验、导入导出 |
| 标准 bundle | 需要稳定的导出/落盘格式、manifest 和版本字段 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| registry 应该是薄层，不应再承担第二套 schema freeze 语义 | 当前 `FileAuthoringRegistry` 基本已经是“文件型 authoring 资产仓库” |
| registry 需要稳定的文件布局和 manifest | 当前已有 `registry_manifest.json`、`schema/schema_ir.json`、`rules/<id>/<version>.json`、`derivations/<id>/<version>.json` |
| version conflict 不能 silently overwrite | `register_rule_spec()` / `register_derivation_spec()` 已在同版本不同内容时显式报错 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 读取时也要做强一致性校验 | manifest 已记录 `schema_digest` / `bytes_digest`，但当前 SDK/service 读 schema 时尚未回验文件内容 | 仍存在 manifest 与 schema 文件不一致但读取成功的窗口 |
| registry 的读取入口应统一 | `SDKRegistry._read_registry_schema_ir()` 与 `service/_registry_io.py` 里各自实现了一遍 schema 文件读取 | 缺少 `FileAuthoringRegistry.read_schema_ir()` 这种单一入口 |
| name-based 查询确实重要，但应发生在正确层级 | 当前 registry 管的是 schema/rule/derivation 资产；schema 内部查询由 `schema_runtime.py` 的模块级函数（`entity_info()`、`field_predicate()` 等）+ `SchemaIndex` 承担 | 还缺一个更顺手的"从 registry 到 SchemaIndex"的 helper |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把当前 registry 改造成 Symir 风格的 `FactLayer([predicates...])` 内存对象集合 | 当前项目的 registry 已经是 authoring 资产仓库，不是运行时 schema object graph |
| 在 registry 层重建 `fact(name)` / `rel(name)` 来直接返回旧式 schema 对象 | 当前没有 `Fact/Rel` 运行时类型；对应语义应落在 `SchemaIndex` |
| 让 registry 重新负责 freeze / canonicalization | 当前 canonicalization 已在 SDK 声明、DSL parse、schema compile 阶段完成 |

#### 3. 与当前代码的对应位置

**3.1 当前 registry 的真实角色**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 文件型 registry 后端 | `registry_fs.py: FileAuthoringRegistry` (L32) | 负责写 schema/rule/derivation 文件、维护 manifest、记录 apply log |
| SDK facade | `sdk/registry.py: SDKRegistry` (L21) | 对外提供 Python 友好 API，本质委托 `FileAuthoringRegistry` |
| service 只读入口 | `service/_registry_io.py: load_registry_schema_ir()` (L12) | 从 registry root + manifest 读取 schema |

**3.2 当前已经具备的“薄 registry”特征**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| schema 写入入口 | `FileAuthoringRegistry.upsert_schema_ir()` (L44) | 接收的已经是 compiled `schema_ir`；registry 不做二次 schema 语义计算 |
| rule/derivation 注册 | `register_rule_spec()` (L80) / `register_derivation_spec()` (L142) | 接收 canonical payload，registry 只负责版本化落盘 |
| manifest 读写 | `_load_manifest()` (L405) / `_save_manifest()` (L425) | 当前 manifest 已经是标准 bundle 元数据 |
| 版本冲突保护 | `_write_if_changed(..., reject_on_conflict=True)` (L429) | 对 rule / derivation 已有显式冲突保护 |

**3.3 与旧文直接对应的当前缺口**

| 观察 | 当前代码位置 | 影响 |
| --- | --- | --- |
| schema 读取逻辑重复 | `SDKRegistry._read_registry_schema_ir()` (L135)、`service/_registry_io.py: load_registry_schema_ir()` (L12) | 两处都走 `get_schema_entry()` → 拼路径 → `json.loads()`；路径拼接、错误处理逻辑重复，后续加一致性校验容易漏改 |
| schema 读取未回验 manifest digest | 同上 | 若 manifest 里的 `schema_digest` 与实际 `schema_ir.json` 内容不一致，当前仍可读成功 |
| 缺少 registry 级 schema 读取正式 API | `FileAuthoringRegistry` 目前只有 `get_schema_entry()` (L274)，没有 `read_schema_ir()` | SDK/service 只能自己拼路径读取 |

**3.4 旧文“name-based 索引”在当前项目的正确落点**

| 旧文诉求 | 当前等价能力 | 说明 |
| --- | --- | --- |
| `fact(name)` / `rel(name)` | `entity_info(index, entity_type)` (L225) / `field_predicate(index, entity_type, field_name)` (L237) | 注意：这两个是 `schema_runtime.py` 的**模块级函数**，接收 `SchemaIndex` 作为第一参数，非实例方法 |
| `resolve(kind, name)` | `entity_type`、`pred_id` 本身就是公开稳定名称 | 当前没有必要在 registry 再造一层 schema object id 解析 |

#### 4. 可执行优化建议

**4.1 应优先做的收口**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 为 `FileAuthoringRegistry` 增加统一的 `read_schema_ir()` | `src/factpy_kernel/authoring/registry_fs.py` | 把 manifest 读取、路径解析、JSON 解析、错误归一化集中到 authoring 层 |
| 在 `read_schema_ir()` 中校验 manifest 中记录的 `schema_digest` 与实际文件重算值一致 | 同上 | 这是当前最贴近旧文“load 强校验”的吸收方式 |
| 让 `SDKRegistry` 和 `service/_registry_io.py` 共用这个新入口 | `src/factpy_kernel/sdk/registry.py`、`src/factpy_kernel/service/_registry_io.py` | 去掉重复 schema 文件读取逻辑，统一错误口径 |

**4.2 应维持的边界**

| 建议 | 原因 |
| --- | --- |
| 继续让 registry 只处理“authoring 资产”级对象 | 与当前架构一致，避免再造一个 schema 对象图系统 |
| schema 内部 name-based 查询统一走 `SchemaIndex` | 避免 registry 和 runtime index 维护两套不同查询语义 |

**4.3 可选增强**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 增加 `build_schema_index_from_registry(...)` 或等价 helper | SDK/application/service 辅助层 | 让“从 registry 到 runtime schema 查询”更直接，但不改变 registry 本体角色 |
| 为 schema digest mismatch 增加稳定错误 code | `registry_fs.py` | 方便 service/front-end 明确区分“缺文件”和“内容不一致” |

**4.4 旧文中值得留意但不直接照搬的细节**

| 旧文设计 | 当前项目对应 | 处理方式 |
| --- | --- | --- |
| 名称规范化 `strip().lower()` 保证大小写不敏感 | 当前 `entity_type` / `pred_id` 均为编译器生成的稳定标识符，已保证一致性 | 不需要在 registry/SchemaIndex 层做 normalize；若未来做 LLM 输入，在输入边界做 |
| registry `version` 字段用于格式兼容 | 当前 manifest 有 `schema_ir_version`（`schema_ir.py` L92 校验），`protocol_version` 也有显式校验 | 版本语义已覆盖，不需要再加一层 registry-level version |
| `describe(schema_id)` 调试工具 | 当前无等价能力 | 可在 SDK 或 CLI 层实现，不需要进 registry 本体 |
| `rels_by_triplet[(name, sub_id, obj_id)]` 三元组索引 | 当前无等价能力 | 若需要关系定位，应在 `SchemaIndex` 或未来 graph projection 层实现 |

**4.5 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 把 registry 改回"schema 元素容器 + by_name 索引"的主实现 | 当前 authoring registry 已经是文件仓库；再引入内存 registry 会造成双重抽象 |
| 把 entity/predicate 粒度索引冗余到 manifest | 这些信息可从 `schema_ir` 动态构建，无需在 registry 再存一份 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| registry 读写一致性 | `upsert_schema_ir()` 后 `read_schema_ir()` 返回内容与写入一致 | `authoring/registry_fs.py` |
| digest 回验 | manifest digest 与实际文件不一致时是否明确报错 | `authoring/registry_fs.py`、`sdk/registry.py`、`service/_registry_io.py` |
| SDK/service 共用入口 | SDK 与 service 读取同一个坏 registry 时，错误口径是否一致 | `sdk/registry.py`、`service/_registry_io.py` |
| 无 schema 场景 | manifest 无 schema entry 或 schema 文件缺失时，是否维持当前 `None`/错误合约 | 同上 |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **adopt** | 这篇文档关于“registry 应降级为索引+校验+导入导出”的原则，与当前 FactPy 架构高度一致，适合直接吸收 |

**更适合当前项目的吸收路径：**

1. 明确 registry 是 authoring 资产仓库，不是 `Fact/Rel` 的运行时对象集合。
2. 把 schema 读取和 digest 回验收口到 `FileAuthoringRegistry`，消除 SDK/service 的重复实现。
3. 若需要 schema 内部的 name-based 查询，新增基于 `SchemaIndex` 的 helper，而不是在 registry 本体里重建一套 `fact(name)` / `rel(name)` API。

---

### 文档：`docs_old/symir_logs/5. fact rel和llm的兼容.md`

#### 1. 原始关注点

这篇文档聚焦的问题很具体：`Fact/Rel` 这种 schema 形式是否适合作为 LLM 的输出目标，如果适合，LLM 应该输出到什么层级。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| LLM 可生成性 | schema 结构是否足够模板化，能稳定由 LLM 产出 |
| 实例引用问题 | 像 `Rel(..., sub=person, obj=city)` 这种 Python 对象引用，LLM 显然无法直接输出 |
| 生成后修复 | LLM 输出不能直接信任，必须经过校验、修复和再冻结 |
| 纯数据输出 | LLM 应只输出 name / payload / draft，而不输出运行时对象 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 面向 LLM 的 schema 声明应尽量结构化、模板化 | 当前 `Entity / Identity / Field`、authoring payload、schema DSL 都具备稳定结构 |
| `description` / `tags` 这类声明元数据主要服务于文档和 LLM，而不是 runtime 语义 | 当前 SDK 和 authoring 文档已明确如此 |
| LLM 生成后的内容必须经过 parse / compile / diagnostics，而不是直接入库 | 当前已有 `authoring` parse、compile、`dsl_bridge` safe DTO 路径 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| LLM 更适合输出"纯数据 draft"，由系统再解析成内部对象 | 当前 DSL bridge 主要支持 schema/rule/derivation DSL 文本；还没有专门的"LLM schema draft normalize"入口 | 若要做 agent/LLM authoring，可增加单独 draft contract |
| 旧文提出两种 LLM 输出格式：name-based（`sub_name: "person"`）和 schema_id-based | 对当前项目，name-based 映射到 `entity_type`，schema_id-based 不适用（当前无 per-entity hash） | LLM draft contract 应只使用 `entity_type` name 引用，与当前可读标识体系一致 |
| 需要一条"可修复"的安全入口，便于生成-诊断-修复循环 | `build_authoring_session_from_dsl_inputs_safe_dto()` (L102-218) 已能返回结构化 `parse_error_sections` | 还没有针对 schema drafting 的 repair helper |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 让 LLM 直接输出 Python 对象引用或实例关系 | 当前系统运行时对象不可序列化，LLM 也无法可靠生成这类引用 |
| 让 LLM 直接输出可执行 Python 类定义并默认视为可信 | 风险过高；应先 parse / validate，再进入 compile 或 apply |
| 在 `Entity.Meta` 中开放 `llm_hint`、`owner` 之类自由字段来“适配 LLM” | 当前声明元数据 contract 明确只允许 `version / description / tags` |

#### 3. 与当前代码的对应位置

**3.1 当前项目中已经存在的“LLM 友好”声明面**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| Entity 声明元数据 | `sdk/schema.py: _extract_entity_declaration_fields()` (L229) | `Meta` 允许字段白名单 `{"version", "description", "tags"}` (L232)；未知字段直接 raise (L239-242) |
| Field 说明文字 | `sdk/schema.py: Field(description=...)` (L81) | 字段级说明进入 authoring 输出 (L93-94)，但不改变运行时语义 |
| Rule / Derivation 描述字段 | `sdk/docs/00_user_guide.md`、`04_public_contract_v1.md` §2.2 | `description` / `tags` 会进入 compiler 输出，但不参与 where 校验、求值或 accept 语义 |

**3.2 当前项目中真正适合承接 LLM 输出的层**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| schema DSL 解析 | `authoring/schema_dsl_parse.py` | 把 DSL 文本降为 authoring schema payload |
| 统一 DSL bridge | `authoring/dsl_bridge.py` | 提供 schema/rule/derivation DSL 到 session/workflow DTO 的桥接 |
| 安全诊断入口 | `dsl_bridge.py: build_authoring_session_from_dsl_inputs_safe_dto()` (L102-218) | 结构化 parse 错误通过 `parse_error_sections` dict 返回（schema → `schema_preflight` L120, rule → `rule_preflight` L133, derivation → `derivation_preview` L146），适合生成-修复循环 |

**3.3 旧文担心的“对象引用”在当前项目中的对应边界**

| 旧文问题 | 当前项目的正确做法 | 说明 |
| --- | --- | --- |
| `Rel(..., sub=person, obj=city)` 里出现 Python 实例引用 | 当前项目关系建模通过 `Entity` 字段**类型注解**引用其他 `Entity` 子类（如 `user: User = Field(...)`） | 声明侧是**类型级**关系，非对象实例引用；LLM 只需输出类名字符串 |
| LLM 输出 `person` / `city` 这种对象 | 应改成输出纯文本 schema draft、authoring payload 或 DSL 文本 | 由 `schema_dsl_parse.py` 解析成 authoring payload → `schema_compile.py` 编译成 `schema_ir` |
| 运行时实体引用 | 统一使用 `idref_v1` | 对应运行时值层，不属于 schema authoring 输入 contract |

**3.4 当前 contract 里对“LLM 扩展字段”的硬边界**

| 观察 | 当前代码位置 | 影响 |
| --- | --- | --- |
| `Entity.Meta` 只允许 `version / description / tags` | `sdk/schema.py` L232 白名单 + L239-242 拒绝未知 key；`authoring/schema_dsl_parse.py` 对 DSL 侧做同等校验；`tests/test_declaration_metadata_v1.py` L68-76 (SDK) / L103-116 (DSL) 覆盖 | 当前不支持 `llm_hint` / `schema_id` / `owner` 等自由字段 |
| core 明确把 `version / description / tags` 视为非语义声明元数据 | `core/docs/01_architecture.md` L18-21（定性）+ L142-154（§6.3 列举不参与的决策路径）；`04_public_contract_v1.md` §2 L41-75（完整 contract） | 这些字段不改变 `where` 校验、`chosen/policy` 决策、candidate 生成或 `accept` 写语义 |

#### 4. 可执行优化建议

**4.1 应坚持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 不让 LLM 直接生成 Python 对象引用、实例句柄或运行时 token | 这些都不适合作为 authoring 输入 contract |
| LLM 输出进入系统前必须经过 parse / compile / diagnostics | 当前项目已经有这条 authoring 安全链路，应继续坚持 |

**4.2 更适合当前项目的吸收方式**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 定义一个专门面向 LLM 的"schema draft"输入 contract | `authoring` 外围或独立 helper | 输出纯 JSON-safe 结构，再转换成 authoring schema payload 或 schema DSL |
| LLM draft 应只含：`entity_type`（name）、字段列表（name/type/cardinality）、`description`/`tags` | 同上 | 不允许对象引用、`schema_digest`、`idref_v1`；关系端点通过 `entity_type` name 引用，不传实例 |
| 复用 `build_authoring_session_from_dsl_inputs_safe_dto()` 或等价 safe preflight 流程做修复回路 | `authoring/dsl_bridge.py` (L102-218) | 把 parse/compile 错误通过 `parse_error_sections` dict 结构化返给上层 agent/LLM |

**4.3 若后续真的要做 LLM-first authoring，优先顺序应该是**

| 优先项 | 理由 |
| --- | --- |
| 先做纯数据 draft -> authoring payload 的 normalize 层 | 比直接让 LLM 生成 Python 类定义更稳、更易诊断 |
| 再补 repair helper / diagnostics mapping | 让 agent 能根据结构化错误自动修复 |
| 最后再考虑更丰富的文档提示字段 | 在 contract 稳定前，不应贸然扩展元数据字段集 |

**4.4 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 为了 LLM 方便而放宽 `Entity.Meta` 的开放性 | 会冲击已经收口的声明元数据 contract |
| 让 LLM 直接输出可执行 Python 代码并跳过 preflight | 安全性和稳定性都不足 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| DSL safe preflight | 非法 schema 文本能否返回结构化 parse error section | `authoring/dsl_bridge.py` |
| 纯数据 draft normalize | 若新增 LLM draft helper，是否拒绝对象引用/未知字段 | 未来新增 helper |
| 描述字段边界 | `description` / `tags` 是否进入 compiler 输出但不影响 runtime 语义 | `sdk/schema.py`、`authoring/schema_compile.py`、`core/docs` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档关于“LLM 输出应是纯数据 draft，之后再 parse/validate/repair”的方向值得保留，但不应回到旧的 `Fact/Rel` 对象生成模型 |

**更适合当前项目的吸收路径：**

1. 继续使用当前 `Entity / Identity / Field` 与 authoring payload 作为 canonical schema contract。
2. 若要支持 LLM-first authoring，在 contract 外围增加“纯数据 draft -> authoring payload/DSL” 的 normalize 层。
3. 把 diagnostics 和 repair loop 建立在 `authoring` safe DTO 之上，而不是放宽 core authoring contract。

---

### 文档：`docs_old/symir_logs/6. Instances.md`

#### 1. 原始关注点

这篇文档试图把 Symir 中“最终事实载体”彻底统一到一个 `Instance` 类型上，核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| 单一事实载体 | 无论来自 CSV、数据库、用户输入还是规则生成，最终都落成逐条 `Instance` |
| 创建期可用 `schema` / `schema_id` | 创建时允许借助 schema 做解析、校验和 ID 计算，但序列化时只保留 `schema_id` |
| fact/rel 共用一个类型 | 不再拆成 `FactInstance` / `RelInstance` |
| strict canonicalize | 一旦给出 schema，就必须按 schema 对 `terms` 做严格解析和归一化 |
| 丰富实例元数据 | 希望内建 `source / observed_at / ingested_at / confidence / status / evidence_id / provenance / tags / merge_policy` |
| canonical JSON 输出 | fact / rel 都要有稳定、可序列化的输出形状 |
| CSV 行级映射 | 每一行只映射成 1..N 条实例，不存在“集合实例” |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| 外部输入最终应被降成逐条、可校验、可序列化的原子写单元，而不是隐式集合对象 | `sdk_ingest()` 只接受 `list/tuple` 的 normalized write items（`sdk/ingest.py` L148-173，其中 L161-162 做 `isinstance(data, (list, tuple))` 校验）；core 落盘单位是 `Claim + ClaimArg + MetaRow` |
| 运行时 / 持久化不应携带 schema 对象引用 | 当前写入和读取都围绕 `entity_type`、`pred_id`、`e_ref` 与全局 `schema_digest` 运行，而不是保留 schema object |
| 业务 identity 与证据 / provenance meta 必须解耦 | 当前 `EntityRef` / `idref_v1` 只编码 identity；断言级 meta 单独写入 ledger |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| strict 的 schema-guided normalization 很重要 | `materialize_identity()` (`application/schema_runtime.py` L278-352)、`resolve_selector()` (L370-385) 与 `plan_write_command()` (`application/entity_write.py` L65-125) 已做强校验 | 还没有一个面向外部导入的统一 `Instance.from_terms(...)` 或"row -> canonical write unit" helper |
| 读取侧需要稳定的"实例视图"对象 | `EntitySnapshotDTO` (`application/protocol/entity_read.py` L88-120) 与 `EntitySnapshot` (`sdk/facade.py` L166-218) 已存在 | 它们是读侧快照，不是统一的读写 / 持久化对象 |
| 查询可以直接返回“实例” | `row_format="instance"` 已实现 | 实际返回的是 `list[EntitySnapshot|None]`，并且只允许单个 `Entity(var)` head，不是旧文那种 canonical `Instance` JSON |
| 实例 meta 需要 richer contract | 当前 `AssertionMeta.from_raw()` (`sdk/facade.py` L52-91) 与 `sdk_validate_provenance()` (`sdk/ingest.py` L86-145) 已覆盖高频 provenance 字段；去重 meta 键集 `DEDUP_AFFECTING_META_KEYS` (L47) 明确把 `source/source_loc/trace_id` 纳入 ingest_key 计算 | `write_protocol` 对公开用户 meta 仍主要是标量；结构化 `provenance` / `tags` 还没有第一等写入入口 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 引入一个覆盖读写持久化的通用 `Instance` 类 | 当前项目已经刻意把“内存对象 / 写入句柄 / 稳定引用 / 读取快照 / 落盘单元”拆开；强行合并会让 API 角色混乱 |
| 把 fact/rel 差异重新塞回 `Instance.kind` 主模型 | 当前 runtime / persistence 以 `Entity + predicate + claim` 为中心，没有回到旧 `Fact/Rel` 双轨语义的必要 |
| 把 `schema_id` 作为每条实例的主公开坐标 | 当前只有整份 schema 的 `schema_digest`，不存在 entity 粒度的公开 schema hash |

#### 3. 与当前代码的对应位置

**3.1 当前“Instance”职责已经拆成五层**

| 角色 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 普通内存实体 | `sdk/schema.py: Entity.__init__()` (L172-177)、`_UnsetFieldValue` (L187-226) | 仅用于声明后的普通 Python 对象，不绑定 store |
| 写入侧托管句柄 | `sdk/batch.py: ManagedEntityHandle` (L1066-1131)、`SDKBatchTx.entity()` (L1150-1182) | 负责 `.set/.add/.retract/.bind()` 这类 write-only 能力 |
| 稳定引用 / 选择器 | `application/protocol/schema_runtime.py: EntitySelector` (L18-29)、`EntityRef` (L32-45)、`application/schema_runtime.py: encode_entity_ref()` (L355-367) | 负责 identity normalization 与 `idref_v1` 编码 |
| 读取侧快照 | `application/protocol/entity_read.py: EntitySnapshotDTO` (L88-120)、`sdk/facade.py: EntitySnapshot` (L166-218)、`_dto_to_sdk_snapshot()` (L650-678) | 表达当前视图值与 assertion history |
| 持久化原子单元 | `core/store/ledger.py: Claim` (L17-23)、`MetaRow` (L34-38)、`write_protocol.set_field()` (L103-130) | 真正落盘的是 claim/meta 行，而不是一个 unified instance object |

**3.2 旧文 strict canonicalize 诉求在当前代码中的落点**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| identity 补全与未知键拒绝 | `application/schema_runtime.py: materialize_identity()` (L278-352) | 对 identity 字段做 strict 校验，并处理 `default` / `default_factory` 物化 |
| 写入值必须符合 schema 期望类型 | `application/entity_write.py: _resolve_mutation_value()` (L236-295) | `entity_ref` 字段只接受 `EntitySelector` / `EntityRef`，拒绝随意对象或裸字符串 |
| Query 的 `"instance"` 返回被严格收口 | `sdk/query_lower.py: _validate_instance_return_contract()` (L143-158)、`sdk/query_runtime.py: _rows_to_instances()` (L226-252) | 明确说明 `"instance"` 只是读取格式，不是通用 `Instance` 模型 |

**3.3 实例级 meta / confidence / provenance 的当前边界**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 断言级常用 meta 读取视图 | `sdk/facade.py: AssertionMeta` (L37-91) | 已吸收 `source / trace_id / ingested_at / confidence / approved_by / note` 等高频字段 |
| ingest / provenance 入口 | `sdk/ingest.py`：`SENSITIVE_SEMANTIC_META_KEYS` (L18-34)、`CONVENTION_META_KEYS` (L36-45)、`sdk_validate_provenance()` (L86-145) | 说明当前系统已经承认“实例级 provenance/meta”是独立 contract |
| meta 真正落盘方式 | `core/evidence/write_protocol.py: _meta_rows_for_claim()` (L302-313)、`_user_meta_rows()` (L316-324) | meta 始终附着在 assertion 上，不进入 `e_ref` |
| 当前尚未覆盖的旧文需求 | `core/evidence/write_protocol.py: _infer_meta_kind_by_value()` (L335-348) | 用户自定义 meta 目前只支持 `bool/str/float/int`；结构化 `provenance`、`tags` 列表还不能直接走公开写入口 |

**3.4 旧文里 `keep_all / record_id` 的最近对应物**

| 旧文诉求 | 当前对应 | 差异 |
| --- | --- | --- |
| `record_id` 作为 keep-all 幂等标识 | `write_protocol._compute_ingest_key()` (L235-287) 会生成 `ingest_key` | 当前是断言写入幂等键，不是公开的实例 ID，也没有 `merge_policy="keep_all"` 的显式 API |
| `prob` 顶层字段 | 当前更接近断言 meta 中的 `confidence`，读取侧再由 `project_display_facts()` (`core/view/projector.py` L142) 做聚合 | 语义是证据置信度，不是单一 `Instance.prob` 字段 |

**3.5 旧文 `merge_policy` 与当前项目去重/冲突模型的差异**

旧文希望用户可选 `merge_policy ∈ {max, latest, noisy_or, overwrite, keep_all}`，并在 `Instance.meta` 中显式设置。

当前项目的实际模型：

| 维度 | 旧文 `merge_policy` | 当前项目 |
| --- | --- | --- |
| 控制粒度 | 每条 `Instance` 自选 | 写协议统一硬编码：`Idempotency(on_conflict="skip")` (`core/store/ledger.py` L48-50, L284-291) |
| 关键词 | `max / latest / noisy_or / overwrite / keep_all` | 只有 `skip`（默认，同 ingest_key 静默跳过）和 `error`（抛 `DuplicateIngestKeyError`） |
| 去重因子 | 由 `record_id = H(schema_id + entity_ids + evidence_id)` 驱动 | 由 `ingest_key = H(pred_id + e_ref + value + source + source_loc + trace_id + temporal)` 驱动 (`write_protocol.py` L235-287) |
| 去重 meta | `evidence_id` | `DEDUP_AFFECTING_META_KEYS = {source, source_loc, trace_id}` (`sdk/ingest.py` L47) |
| 时间版本 | 旧文未明确 | `valid_from / valid_to / version` 参与 ingest_key 计算，不同时间版本各自独立写入 |

当前项目不存在 `keep_all / overwrite / noisy_or / latest / max` 任何关键词。若未来需要多证据合并策略，应在 `write_protocol` / `policy` 层扩展，不应在 SDK 表面暴露一个 `Instance.merge_policy` 字段。

**3.6 旧文 CSV 行映射诉求与当前项目的状况**

旧文要求"每行映射成 1..N 条 Instance"，并提出 CSV 列到 sub/obj/props 的映射规则。

当前项目状况：

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| CSV 解析 | `adapters/souffle/runner.py` L233-269 | 仅用于读取 Souffle 引擎输出的 TSV/CSV 文件，不是用户侧数据导入 |
| 用户侧 ingest 入口 | `sdk/ingest.py: sdk_ingest()` L148-173 | 只接受 `list[dict]` 的 normalized write items；**不提供 CSV row -> ingest item 的自动映射** |
| 外部 CSV 导入 | 无 | 用户必须在 SDK 外部自行把 CSV 行转成 normalized ingest item 列表 |

若要落实旧文"CSV 行级映射"的想法，应在 SDK 外围（如未来 `application/authoring_normalize.py`）实现"schema-guided CSV row -> ingest items"的 helper，而不是在 `Instance` 类里内建 CSV 解析。

**3.7 旧文里值得留意的 API 设计细节（来自 ME/CODEX 后续交互）**

旧文在后续讨论中反复强调了一个设计约束：

> **`Instance` 只有 `terms`，不接受与 `terms` 并列的 `props` 参数。所有数据必须进入 `terms`。**

这一"单入口"原则在当前 FactPy 中的映射：

| 旧文约束 | 当前项目对应 |
| --- | --- |
| `Instance(schema=..., terms=...)` 只有一个数据入口 | `sdk.set(field, ref, value)` / `sdk.add(field, ref, value)` / `tx.entity(T, **identity).set(field, value)` 把数据拆到每个 field 写调用 |
| 不允许 `Instance(terms=..., props=...)` 双入口 | 当前每次写只操作一个 field，天然避免了旧文所担心的"并列入口歧义" |
| `terms` 可以是 list/tuple/dict | 当前 ingest item 始终是 `dict` 格式 |

#### 4. 可执行优化建议

**4.1 文档层应先收口当前分层**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 增加一节“当前 Instance 模型其实是五层分工” | `sdk/docs/00_user_guide.md` 或新文档 | 明确 `Entity / handle / EntityRef / EntitySnapshot / Claim+MetaRow` 的职责，避免后续反复把它们混成一个对象 |
| 在 Query 文档里明确 `"instance"` 返回的是 `EntitySnapshot` | 同上 | 避免误以为它等价于旧文的 canonical `Instance` 载体 |

**4.2 更适合当前项目的吸收方式**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若需要外部导入统一入口，新增窄范围 normalize helper：`draft row -> normalized ingest items` 或 `EntityWriteCommand` | `sdk/ingest.py` 附近，或未来 `application/authoring_normalize.py` | 解决旧文真正关心的“统一输入规范化”问题，但不引入新的万能 `Instance` 类 |
| helper 保持 strict，拒绝启发式猜端点 / 猜 identity | 同上 | 延续旧文里正确的“默认 strict”原则 |
| 如果确实需要 richer instance meta，显式扩展 JSON meta contract | `core/evidence/write_protocol.py`、`sdk/ingest.py` | 例如把 `dict/list` 安全地下沉为 `MetaRow(kind="json")`，而不是在 SDK 表面重造 `Instance.meta` |

**4.3 `keep_all` 语义若要引入，应放在写协议层**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 把"保留多证据版本"的语义设计成 idempotency / dedup policy，而不是 top-level `Instance` 标识 | `core/evidence/write_protocol.py` | 当前最近似的是 `ingest_key`（L235-287）+ `Idempotency(on_conflict="skip")` (`ledger.py` L48-50)；若将来需要 `record_id`，也应作为写层 contract 设计 |
| 明确 `confidence`、`evidence_id`、`trace_id` 等字段对去重和保留策略的作用 | 同上 + `sdk/ingest.py` | 当前 `trace_id` 已参与 ingest_key hash（`DEDUP_AFFECTING_META_KEYS` L47），但 `confidence` 不参与；先把这些规则文档化，再决定是否暴露更高层 API |

**4.4 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 用一个 `Instance` 类同时承担“in-memory object / write command / query result / persistent row”四种角色 | 会把当前已经清晰的层边界重新打乱 |
| 为了兼容旧文而让 batch / query / ledger 共用一个 JSON shape | 不同层的职责不同，强行统一只会引入大量空字段和语义歧义 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| 文档 / 示例一致性 | plain `Entity`、`tx.entity(...)`、`EntitySnapshot` 的职责边界是否表达清楚 | `sdk/docs/00_user_guide.md` |
| normalize helper（若新增） | 是否拒绝不完整 identity、歧义端点、未知字段、非 JSON-safe meta | `sdk/ingest.py` 或未来 helper |
| Query `"instance"` 语义 | 仍然只允许单个 `Entity(var)` head，且返回 `EntitySnapshot` 而不是其他对象 | `sdk/query_lower.py`、`sdk/query_runtime.py` |
| JSON meta 扩展（若新增） | `dict/list` meta 能否稳定写入 `MetaRow(kind="json")` 并正确读回 | `core/evidence/write_protocol.py`、`core/store/ledger.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档关于“所有外部事实最终都应降为 strict、可序列化、可携带 meta 的单元”的原则值得吸收，但当前 FactPy 不应回退成统一 `Instance` 类 |

**更适合当前项目的吸收路径：**

1. 先把当前五层分工文档化，澄清 `Entity`、write handle、`EntityRef`、`EntitySnapshot`、ledger claim 的边界。
2. 如果确实需要外部 row / CSV / LLM 导入统一入口，新增“draft -> normalized ingest items / EntityWriteCommand” helper，而不是新增 `Instance` core 类型。
3. 若未来需要 richer provenance / `tags` / `keep_all` 能力，优先在 write protocol 和 meta contract 层扩展，而不是把这些诉求重新绑定到一个万能对象上。

---

### 文档：`docs_old/symir_logs/7. rel语法讨论.md`

#### 1. 原始关注点

这篇文档并不是在讨论“关系要不要存在”，而是在反复确认**关系实例输入语法**该支持哪些形态、每种形态的边界是什么，以及报错和 README 是否足够清楚。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| `terms` dict 的多形态支持 | 讨论 `{"sub_key": ..., "obj_key": ..., "props": ...}`、扁平 dict、`{"sub_ref": ..., "obj_ref": ..., "props": ...}` 是否都应支持 |
| 端点引用的显式区分 | 旧文明确区分 `sub_key/obj_key`（key dict）与 `sub_ref/obj_ref`（实例引用） |
| props 命名严格校验 | 报错 `Unknown rel props` 暴露出“传入字段名”和 schema `props` 名称必须一一匹配 |
| list/tuple 关系语法 | 讨论 `[sub, obj, ...props]` 这种位置式输入是否应保留 |
| README / 文档完备性 | 用户希望 README 清楚列出所有支持形态，否则难以知道该怎么写 |
| merge 与语法解耦 | 最后明确：本次更新主要是语法/输入形态，不等于 merge 逻辑已经实现 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| 关系输入必须显式区分“端点引用”与“关系属性” | 当前 FactPy 通过 `entity_ref` 字段与普通标量字段天然完成了这层分离 |
| 允许的输入形态必须有清晰文档和示例 | 当前项目已有零散说明，但旧文暴露的问题今天仍然成立：关系写法若文档不集中，用户会困惑 |
| 报错应尽量告诉用户“允许什么、不允许什么” | 当前不同层已经有明确错误，但口径分散，仍可收口 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 多种“外部输入形态”在导入边界有价值 | 当前 `sdk.batch`、`sdk.set/add`、application write path 都各自有严格输入 contract | 还没有一个统一 normalize helper 去承接旧文里的 `sub_ref/sub_key/props` 或扁平 dict 形态 |
| 关系语法可以保留少量 blueprint sugar | `where_schema_lowering.py` 仍支持 `LivesIn:exists`、`livesin:person` 这类 compile-time sugar | 这是编译期兼容层，不是当前 SDK 公共写入语法 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在当前 SDK 核心写入 API 中恢复 `Instance(schema=rel, terms=...)` 小语言 | 当前项目已经用“reified `Entity` + field-by-field write”替代这套语法，类型边界更清楚 |
| 让 `sub_key` / `obj_key` 同时接受 key dict 和实例对象 | 会重新制造旧文里正试图澄清的歧义；当前应继续把“identity 选择”和“稳定引用”分开表达 |
| 把 list/tuple / nested props / 扁平 dict 都作为同一层公共 runtime 语法 | 这些更适合放到导入 normalize 层，而不是 SDK 核心 API |

#### 3. 与当前代码的对应位置

**3.1 当前项目里的关系语法已经改成“reified Entity + typed fields”**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 关系声明方式 | `sdk/docs/00_user_guide.md` §2.4 (L161-173) | 关系节点只是普通 `Entity`；不存在单独 `Rel(...)` public syntax |
| `Entity` 子类字段自动变成 `entity_ref` | `sdk/schema.py: _annotation_to_type_domain_runtime()` (L316-318) | 其他 `Entity` 子类注解会编译成 `entity_ref` 类型域 |

**3.2 当前 public write 语法对“关系端点”是显式、分层的**

| 层 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SDK batch 推荐写法 | `sdk/docs/00_user_guide.md` L223、L254 | `entity_ref` 字段可传“同 tx 句柄”或 canonical `idref_v1` token；这就是当前最接近旧文 `sub_ref/obj_ref` 的公共写法 |
| batch 对错误对象类型的拒绝 | `sdk/batch.py: _stage_field_op()` (L1658-1666) | 明确拒绝 plain `Entity` 实例：`plain Entity instance is not supported; use tx.entity(...) handle or entity_ref` |
| SDK 直接写入的最底层 contract | `sdk/store.py: _coerce_sdk_value_to_tag()` (L963-967) | `entity_ref` 值必须是 canonical `idref_v1` token |
| application 写路径 | `application/entity_write.py: _resolve_mutation_value()` (L251-259) | 中层只接受 `EntitySelector` / `EntityRef`，不接受旧式 nested dict/list 语法 |

**3.3 当前项目对旧文几种语法形态的直接对应**

| 旧文形态 | 当前 FactPy 对应 | 备注 |
| --- | --- | --- |
| `sub_ref/obj_ref` | `sdk.batch` 里的“同 tx handle 引用”，或 application 层的 `EntityRef` / `EntitySelector` | 当前最接近、也最清晰 |
| `sub_key/obj_key` | `tx.entity(T, **identity)` / `handle.bind(...)` / `EntitySelector(identity=...)` | key dict 不再塞进一个关系 `terms` dict，而是用于实体 identity 选择 |
| `props={...}` | 对关系实体的普通字段逐个 `.set(...)` / `.add(...)` | 不再保留单独的 nested `props` bucket public syntax |
| `[sub, obj, ...props]` | 无 direct public 对应 | 当前项目明确偏向命名字段和 typed write，不鼓励位置式关系语法 |

**3.4 compile-side 仍保留了一点 blueprint sugar，但只在编译器里**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| schema-aware where sugar lowering 入口 | `authoring/where_schema_lowering.py: lower_blueprint_where_sugar_with_schema_v1()` (L12-28) | 仍保留 blueprint 到 canonical predicate 的重写层 |
| `Type:exists` sugar | `where_schema_lowering.py` L184-198 | 例如 `LivesIn:exists` 会被重写到 canonical exists predicate |
| `type:field` sugar | `where_schema_lowering.py` L200-208 | 例如 `livesin:person` 会被重写到对应 field predicate |

这说明旧文里“关系语法糖”并没有完全消失，但它今天只存在于**编译期兼容层**，不是 SDK 主写入语法。

**3.5 当前项目的文档和错误边界，正对应旧文暴露出的困惑点**

| 观察 | 当前代码位置 | 影响 |
| --- | --- | --- |
| 关系写入文档存在，但分散在多个位置 | `sdk/docs/00_user_guide.md` L223/L254/L289，`sdk/docs/02_readwrite_and_ingest.md` L101/L130 | 用户需要自己拼接“handle / idref / snapshot / wire plan”几个局部说明 |
| query 的 `"instance"` 容易被误解成旧式关系实例语法 | `sdk/docs/03_rules_and_derivations.md` L111-118 | 当前它只是 `EntitySnapshot` 返回格式，不是关系写入语法 |
| 各层错误都比较明确，但不统一 | `sdk/batch.py` L1662、`application/entity_write.py` L254、`sdk/store.py` L965-966 | 同一个“关系端点怎么传”问题，在不同层会看到不同措辞，容易放大理解成本 |

#### 4. 可执行优化建议

**4.1 先把“关系写法矩阵”文档化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 增加一节专门的 relationship write syntax 文档 | `sdk/docs/00_user_guide.md` 或独立 `04_relationship_modeling.md` | 集中写清：声明语法、batch 写法、direct set/add 写法、application 层 `EntitySelector/EntityRef`、不支持的旧式 nested dict/list |
| 在文档中明确给出“旧文形态 -> 当前写法”对照表 | 同上 | 这样能直接消掉 `sub_ref/sub_key/props` 迁移期困惑 |

**4.2 收口错误提示**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| `entity_ref` 类型错误时，把“允许值形态”写进报错 | `sdk/batch.py`、`sdk/store.py`、`application/entity_write.py` | 例如明确提示“batch 用 handle 或 idref；application 用 EntitySelector/EntityRef” |
| 对 plain `Entity` 误传关系端点的错误，补充“为什么不支持” | `sdk/batch.py` | 直接指出 plain 对象没有稳定 ref，避免用户误以为只是语法没写对 |

**4.3 如果将来要兼容旧式 rel `terms` 语法，应只放在 normalize 层**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若未来确实要支持 `sub_ref/sub_key/props`、扁平 dict 或 list/tuple 导入，新增边界 helper | `application/authoring_normalize.py` 或 `sdk/ingest.py` 外围 | 只负责把旧式输入降成当前 canonical write commands |
| normalize 后的 canonical 目标仍应是 field-wise writes / `EntityWriteCommand` | 同上 | 不把旧语法重新推回 SDK 主 API |

**4.4 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 在当前 SDK 上重新开放多套关系 runtime 语法 | 会冲击已经稳定的 typed field write contract |
| 把 compile-time sugar 当成 public 写入语法来宣传 | `where_schema_lowering` 的 sugar 是兼容层，公开承诺会扩大维护面 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| relationship write contract | `entity_ref` 字段是否继续接受“同 tx handle / canonical idref”，并拒绝 plain `Entity` | `sdk/batch.py`、`sdk/store.py` |
| application write contract | `entity_ref` 字段是否继续只接受 `EntitySelector` / `EntityRef` | `application/entity_write.py` |
| compile-side sugar | `LivesIn:exists`、`livesin:person` 这类 sugar 是否仍能 schema-aware lowering 到 canonical predicate | `authoring/where_schema_lowering.py` |
| 文档一致性 | relationship write 文档是否清楚区分 batch、SDK 直接写、application 三层 contract | `sdk/docs/*` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档真正值得吸收的是“关系输入语法必须显式、文档必须集中、错误必须告诉用户允许什么”；但当前 FactPy 不应回退到旧 `Instance(terms=...)` 关系小语言 |

**更适合当前项目的吸收路径：**

1. 继续以 `reified Entity + entity_ref fields + field-wise writes` 作为关系主语法。
2. 把旧文里的 `sub_ref/sub_key/props` 讨论转化为一份清晰的 relationship write matrix 文档。
3. 如果未来真的要兼容这些旧式输入形态，只在导入 normalize helper 层支持，不进入 SDK 核心写入 API。

---

### 文档：`docs_old/symir_logs/8. CSV.md`

#### 1. 原始关注点

这篇文档通过 ME/CODEX 连续对话，逐步落实了旧 Symir 系统的 CSV 导入能力。核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| CSVProvider / CSVSource 封装 | 希望有专用类统一管理"CSV 文件 → Instance"的映射，包括列名顺序、schema_id 绑定 |
| columns 与 schema signature 对齐 | Fact 按 `signature` 顺序，Rel 按 `derived_signature` 顺序（`sub_*` / `obj_*` + props） |
| FactView 与 FactLayer 接口对齐 | CSVProvider 应能同时接受 `FactLayer`（全量 registry）或 `FactView`（子集视图）作为 schema 参数 |
| prob_column 支持 | 每个 CSVSource 可选指定概率列 |
| datatype_cast 选项 | 支持 `"none"` / `"coerce"` / `"strict"` 三级类型转换策略 |
| 错误信息改进 | 报错应包含 schema name，不能只给 opaque `schema_id` |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 数据导入最终必须过 schema 校验和类型转换 | 当前 `_coerce_sdk_value_to_tag()` (`sdk/store.py` L963-1009) 已实现 schema-driven 类型强转：`string/int/float64/bool/time/uuid/bytes/entity_ref` |
| 概率/置信度是 meta 层而非业务值 | 当前 `confidence` 作为 convention meta key (`sdk/ingest.py` L41, `write_protocol.py` L26)，验证 `(0,1]` (`write_protocol.py` L360-366) |
| 报错应包含足够的上下文（schema 名称/类型/期望值） | 当前 ingest error path 会携带 `items[i].field` / `items[i].value` 路径 (`sdk/ingest.py` L303-456) |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 需要 CSV → ingest item 的专用 helper | 当前**无** CSV 导入能力；用户必须在 SDK 外部自行转换 | 旧文的 `CSVProvider` 概念仍有参考价值，但应实现为 normalize helper 而非 core 类 |
| schema 子集视图应能传入导入/查询接口 | 当前 `ViewSpec` (`core/store/types.py` L38-50) 是置信度/活跃过滤器，非 schema 子集过滤 | 若要做 schema-level 过滤，应在 `SchemaIndex` 或 application 层新增，不在 ingest 入口 |
| coerce/strict 两种模式 | `_coerce_sdk_value_to_tag()` 行为接近 `strict`（类型不匹配直接报错） | 没有"尽力转换"的 coerce 模式（例如 CSV 里 `"123"` → `int(123)` 的自动转换） |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在 core/sdk 层引入 `CSVProvider` 和 `CSVSource` 类 | 当前项目以 `sdk.ingest(data=[...])` 作为唯一 canonical ingest 入口；CSV 解析属于外围职责 |
| 让 `FactView` 与 `FactLayer` 合并或暴露相同 API | 当前项目没有 `FactLayer/FactView`；schema 过滤应在更适合的层（`SchemaIndex` 或 application）处理 |
| 把 `prob_column` 作为 ingest item 顶层字段 | 当前 `confidence` 已经是 meta 级字段，不应提升为 ingest item schema 字段 |

#### 3. 与当前代码的对应位置

**3.1 当前项目如何做类型转换（旧文 `datatype_cast` 的等价物）**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 写入值类型转换 | `sdk/store.py: _coerce_sdk_value_to_tag()` (L963-1009) | 按 `type_domain` 标签（`string/int/float64/bool/time/uuid/bytes/entity_ref`）做强类型校验和转换 |
| 字段值到 write terms 的分发 | `sdk/store.py: _rest_terms_for_field()` (L743-755) | 从 schema predicate 的 `arg_specs[1]` 提取 `type_domain`，调用 `_coerce_sdk_value_to_tag()` |
| 类型转换不支持 "coerce from string" | 同上 | 当前行为更接近旧文 `"strict"`：例如 `int` 域不接受字符串 `"123"`；若从 CSV 读取，用户需自行转换 |

**3.2 当前项目如何处理 confidence / prob（旧文 `prob_column` 的等价物）**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| confidence 作为 convention meta key | `sdk/ingest.py` L41 (`CONVENTION_META_KEYS`)、`write_protocol.py` L26 | 非必填，但有特殊校验 |
| confidence 值验证 | `write_protocol.py: _validate_meta_value_for_kind()` (L360-366) | 必须是 `float`，范围 `(0, 1]` |
| ingest meta 合并 | `sdk/ingest.py` L341-342 | 批次级 `meta` 与每条 item 级 `meta` 合并，item 级优先 |

**3.3 当前项目的 schema 字段映射（旧文 `columns` 的等价物）**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 字段名到 predicate 的映射 | `application/schema_runtime.py: SchemaIndex.field_predicates` (L113-171) | `dict[tuple[str, str], PredicateInfo]`，key = `(owner_type, py_field_name)` |
| PredicateInfo 含 `py_field_name` | `application/schema_runtime.py: PredicateInfo` (L24-31) | 提供外部字段名 → 内部 predicate 的稳定映射 |
| 字段查询 | `application/schema_runtime.py: field_predicate(index, entity_type, field_name)` (L237-247) | 按 `(entity_type, field_name)` 查 predicate |
| SDK 级字段到 predicate 缓存 | `sdk/store.py: _schema_pred_for_field()` (L733-741) | 由 `Field` 描述符查 schema predicate，缓存在 `_field_pred_by_descriptor` (L730) |

**3.4 当前项目如何处理 CSV（仅 Souffle adapter 输出，非用户导入）**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| TSV 单元编解码 | `adapters/souffle/tsv_v1.py: tsv_cell_v1_encode()` (L6) / `tsv_cell_v1_decode()` (L12) | 转义 `\`, `\t`, `\n` |
| TSV 写入 | `adapters/souffle/tsv_v1.py: write_tsv()` (L42) | 输出标准化 `.facts` 文件 |
| Souffle 输出解析 | `adapters/souffle/runner.py: _parse_souffle_line()` (L251-269) | 自动识别 TSV/CSV 格式，用 `csv.reader` 解析 CSV 部分 |
| Souffle 输出转换 | `adapters/souffle/runner.py: _convert_raw_outputs()` (L233-248) | 把引擎输出从 CSV/TSV 统一转为 `.out.facts` TSV |

**3.5 当前 `ViewSpec` 与旧文 `FactView` 的差异**

| 维度 | 旧文 `FactView` | 当前 `ViewSpec` |
| --- | --- | --- |
| 过滤对象 | schema 子集（按 `schema_id` 集合选择允许的 predicates） | 事实活跃度/置信度过滤（`active: bool`, `confidence_strategy: str`） |
| 粒度 | predicate / entity 级别 | 全局 view 级别（应用到所有查询） |
| 存储 | 内存对象 | `ViewManager` (`sdk/store.py` L40-76) 管理的命名 view |
| API 兼容性 | 旧文要求与 `FactLayer` 同 API | 当前 `ViewSpec` 是独立 dataclass，不与 `SchemaIndex` 共享接口 |

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 继续让 `sdk.ingest(data=[...])` 作为唯一 canonical ingest 入口 | CSV 解析、列映射、类型转换都是外围职责，不应下沉到 core ingest API |
| `confidence` 继续作为 meta 级字段 | 概率/置信度不是业务 schema 字段，当前定位正确 |

**4.2 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 新增 CSV row normalize helper | `sdk/ingest.py` 附近或 `application/authoring_normalize.py` | 给定 schema + CSV 行 dict → normalized ingest items；不需要 `CSVProvider` 类，一个函数即可 |
| 在 normalize helper 中实现 `coerce` 模式 | 同上 | `"123"` → `int(123)` 等字符串到 `type_domain` 的宽松转换；当前 `_coerce_sdk_value_to_tag()` 只做严格转换 |
| 为 normalize helper 明确三级策略 | 同上 | `none`（全部字符串传入，类型由 SDK 层处理）/ `coerce`（尽力转换）/ `strict`（转换失败报错）——延续旧文的三级设计 |
| 错误信息包含 entity_type name | `sdk/ingest.py`、`sdk/store.py` | 当 ingest 报错时，尽量带上可读的 `entity_type` 和 `field_name`，而不是只给 `pred_id` |

**4.3 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 在 core/sdk 引入 `CSVProvider` / `CSVSource` 类 | CSV 是特定格式，不值得在 kernel 里专门建类；一个 normalize 函数 + 外部 `csv.DictReader` 即可 |
| 让 `ViewSpec` 承担 schema 子集过滤 | `ViewSpec` 的语义是活跃度/置信度过滤，不是 schema predicate 过滤；两者不应混 |
| 在 `_coerce_sdk_value_to_tag()` 中加 coerce 模式 | 这是 core 层的严格转换函数，coerce 应在 normalize helper 层完成，转换后再传给 core |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| 类型转换 | `_coerce_sdk_value_to_tag()` 对各 type_domain 的边界输入是否正确拒绝/转换 | `sdk/store.py` |
| confidence 校验 | `(0,1]` 范围、非 float 类型拒绝、meta 合并优先级 | `write_protocol.py`、`sdk/ingest.py` |
| normalize helper（若新增） | CSV 行 dict → ingest items 的映射是否正确处理 identity/field 分离、类型转换、缺失字段 | 未来 helper |
| 错误可读性 | ingest 报错是否包含 `entity_type`、`field_name` 而非仅 `pred_id` | `sdk/ingest.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档关于"CSV 导入需要 schema-driven 列映射和分级类型转换"的工程原则仍然有价值，但不应在 kernel 里引入 `CSVProvider` / `CSVSource` 专用类 |

**更适合当前项目的吸收路径：**

1. 当前项目无用户侧 CSV 导入能力——若确实需要，以 normalize helper 函数形式提供，不新增 core 类。
2. 旧文的三级 `datatype_cast`（`none/coerce/strict`）思路正确，但 `coerce` 应在 normalize 层实现，不修改 core `_coerce_sdk_value_to_tag()`。
3. 旧文的 `FactView` 与当前 `ViewSpec` 概念不同——前者是 schema 子集，后者是置信度/活跃过滤；若需要 schema 子集能力，应在 `SchemaIndex` 或 application 层新增。
4. `prob_column` 的诉求已被 `confidence` meta key 更好地解决——概率是 meta 级信息，不是 schema 字段。

---

### 文档：`docs_old/symir_logs/9. rel CSV.md`

#### 1. 原始关注点

这篇文档是 doc 8 的延续，聚焦于 Rel 类型数据如何通过 CSV 读入。核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| Rel CSV 列映射机制 | columns 不按列名匹配，而是**按 `Rel.derived_signature` 顺序位置映射** |
| derived_signature 构成 | `sub_key_fields`（`sub_` 前缀）+ `obj_key_fields`（`obj_` 前缀）+ `props` |
| 复合端点 key | 若 sub 端有多个 `role="key"` 字段，derived_signature 自动扩展（如 `sub_Name, sub_address`） |
| 端点 key 覆盖 | `Rel` 支持通过 `endpoints={"sub_key_fields": [...]}` 覆盖从 sub/obj 继承的 key |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 复合 identity 字段是有序的，序列化时顺序必须稳定 | 当前 `encode_entity_ref()` (`application/schema_runtime.py` L355-367) 按 `info.identity_fields` 顺序构建 `(name, type_domain, value)` tuple 列表；`idref_v1` 编码 (`core/protocol/idref_v1.py` L26-64) 显式存储字段数量和每个字段的 name/type/value |
| 每个 identity 字段独立编译 | `_compile_identity_predicate()` (`schema_compile.py` L164-197) 为每个 identity 字段各生成一个 predicate；`primary_key` 标记是 per-field 的 (L195-196) |
| 关系端点引用本质上是 entity_ref 类型 | `_annotation_to_type_domain_runtime()` (`sdk/schema.py` L316-318)：Entity 子类注解自动编译为 `"entity_ref"` type_domain |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 外部导入时需要"列位置 → 字段名"的映射 | 当前 ingest 全部基于名称映射（`dict` with field name keys），不支持位置映射 | 若要支持 CSV 位置映射，应在 normalize helper 层实现 |
| "derived signature"概念对 CSV/graph export 有用 | 当前没有 `derived_signature`；关系是普通 Entity + `entity_ref` 字段 | 若未来做 graph projection / CSV export，可在 projection 层从 schema 自动派生扁平 signature |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在 core schema 层引入 `derived_signature` / `sub_key_fields` / `obj_key_fields` | 当前 `schema_ir` 不区分 Fact/Rel，关系只是带 `entity_ref` 字段的普通 Entity |
| 位置映射作为 core ingest 默认行为 | 位置映射脆弱且难以检错；名称映射更安全，应继续作为 canonical 入口 |

#### 3. 与当前代码的对应位置

**3.1 当前复合 identity 的编译与序列化**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 多 Identity 字段声明 | `sdk/schema.py: EntityMeta.__new__()` (L128-169) | `identity_fields` 作为有序列表存储，支持多字段 |
| 单个 identity field 编译 | `schema_compile.py: _compile_identity_field()` (L200-225) | 每个 identity 各自成为 predicate；L223-224 标记 `primary_key` |
| identity 物化与缺省填充 | `application/schema_runtime.py: materialize_identity()` (L278-352) | 逐字段迭代 (L305)，处理 default / default_factory |
| idref_v1 编码 | `core/protocol/idref_v1.py: canonical_bytes_idref_v1()` (L26-64) | 先写字段数量 (L38)，再逐字段写 `(name_len, name, tag_code, value_len, value)` |
| entity_ref 编码 | `application/schema_runtime.py: encode_entity_ref()` (L355-367) | 按 `info.identity_fields` 顺序收集 tuples |

**3.2 当前 entity_ref 字段的编译方式（旧文 `Rel.sub/obj` 的等价物）**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| Entity 注解 → entity_ref 类型域 | `sdk/schema.py: _annotation_to_type_domain_runtime()` (L316-318) | 若字段类型注解是 Entity 子类，自动返回 `"entity_ref"` |
| entity_ref 字段编译成 predicate | `schema_compile.py: _compile_field()` (L228-300) | 生成 arity-2 predicate：`(entity_ref owner, entity_ref value)` (L277-289) |
| 写入时只接受 EntitySelector / EntityRef | `application/entity_write.py: _resolve_mutation_value()` (L236-295) | entity_ref 值必须已解析为稳定引用 |

**3.3 当前 ingest 路径为什么是名称映射而非位置映射**

| 观察 | 当前代码位置 | 说明 |
| --- | --- | --- |
| ingest item 是 dict 结构 | `sdk/ingest.py` L49-55 | `{"kind": "set", "field": <Field>, "e_ref": str, "value": Any}` |
| 字段访问全部 by name | `sdk/ingest.py` L343-378 | `raw_item.get("field")` / `raw_item.get("value")` |
| 内部 mapping 有位置映射但不暴露 | `core/mapping/canon.py` L69-76, L153-158, L172-186 | 仅用于 compiled mapping predicates 的参数位置提取，不是 ingest 公开 API |

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 继续用名称映射作为 canonical ingest 入口 | 比位置映射更安全、更易检错 |
| 不在 `schema_ir` 中引入 `derived_signature` / `sub_key_fields` | 保持 Entity + predicate 统一模型 |

**4.2 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若新增 CSV normalize helper，支持可选的位置映射模式 | `sdk/ingest.py` 外围 | 用户指定 `columns=["Name", "addr"]` + schema → helper 按 identity_fields/field_predicates 顺序做位置到名称的桥接 |
| 为 graph projection / CSV export 提供"derived flat signature"工具函数 | 未来 `application/graph_projection.py` | 从 SchemaIndex 的 `entity_info()`+`field_predicates` 自动派生扁平字段列表（identity fields + regular fields），等价于旧文 `derived_signature` 但不进入 `schema_ir` |

**4.3 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 位置映射作为 core ingest 默认行为 | 名称映射更安全，位置映射应只在 normalize helper 层可选启用 |
| 在 Rel schema 层增加 `endpoints` override 机制 | 当前关系就是 Entity + 字段；端点是哪个 Entity 的哪些 identity 字段，由类型注解 + schema 编译决定，不需要额外 override |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| 复合 identity 编译 | 多 `Identity(primary_key=True)` 字段的声明顺序是否在 schema_ir、SchemaIndex、idref_v1 中一致保留 | `sdk/schema.py`、`schema_compile.py`、`idref_v1.py` |
| entity_ref 类型推断 | Entity 子类注解是否正确编译为 `entity_ref` type_domain | `sdk/schema.py`、`schema_compile.py` |
| idref_v1 编码/解码对称性 | 复合 key 的编码后解码是否返回相同 identity dict | `core/protocol/idref_v1.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档主要是 doc 8 的细节补充；旧文关于位置映射和 derived_signature 的思路对 CSV/export 场景仍有参考价值，但不应下沉到 core schema 层 |

**更适合当前项目的吸收路径：**

1. 复合 identity 支持已经完整：声明 → 编译 → 物化 → idref_v1 编码全链路支持多字段。
2. 若需要 CSV 位置映射，在 normalize helper 层实现"columns + schema → 名称映射"的桥接，不改 core ingest API。
3. 若需要 derived flat signature（关系扁平字段列表），在 graph projection / export 层从 `SchemaIndex` 派生，不在 `schema_ir` 中新增结构。

---

### 文档：`docs_old/symir_logs/10. Instance Keys.md`

#### 1. 原始关注点

这篇文档通过 ME/CODEX Q&A 逐步澄清了 entity_id / record_id 的计算规则。核心讨论包括：

| 诉求 | 描述 |
| --- | --- |
| sub_key / obj_key 只含端点主键 | 不含 props；props 必须放到单独的 `props` dict 或使用扁平 dict |
| entity_id 计算公式 | `H(schema_id + canonical_json(ordered(key_fields values)))`——key_fields 的值参与，props 不参与 |
| schema_id 间接影响 entity_id | datatype/namespace/role 影响 schema_id，schema_id 影响 entity_id |
| 同端点不同 props 的 rel 有相同端点 id | 这是有意设计，不是 bug；区分多条记录要用 `record_id`（`keep_all`） |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| entity_id 只由 identity 字段决定，非 identity 字段不参与 | `encode_entity_ref()` (`schema_runtime.py` L355-367) 只遍历 `info.identity_fields`；`idref_v1` 编码 (`idref_v1.py` L26-64) 只包含 identity field 的 name/type/value |
| 关系实体的 identity 与其 entity_ref 字段值无关 | 关系 Entity 的 entity_ref 字段值作为普通 claim 写入 (`entity_write.py: _rest_term_for_value()` L391-405)，不参与关系实体自身的 idref_v1 |
| 同端点不同属性值应可共存 | 当前每条 field write 各有独立 `ingest_key`（含 value）；不同属性值天然产生不同 ingest_key |

**◐ 当前实现与旧文的重要差异：**

| 维度 | 旧文 | 当前 FactPy |
| --- | --- | --- |
| entity_id hash 输入 | `H(schema_id + canonical_json(key_fields values))` | `H(entity_type + identity_fields(name, type_domain, value))`——不含 `schema_id`/`schema_digest` |
| schema 变化对 entity_id 的影响 | schema_id 变 → entity_id 变（间接耦合） | entity_type 不变 + identity 字段名/类型/值不变 → entity_id 不变（与 schema 其他变化解耦） |
| namespace/role 对 id 的影响 | 通过 schema_id 间接影响 | 无直接影响——当前 idref_v1 不包含 namespace/role |

这是一个**重要的设计差异**：当前 FactPy 的 `idref_v1` 编码**不含 `schema_digest`**（`idref_v1.py` L26-64 没有引入任何 schema hash），这意味着：
- 只要 `entity_type` 名称和 identity 字段定义不变，entity_id 是稳定的
- schema 的其他变化（新增字段、修改 description、重新编译等）不会影响已有实体的 id
- 旧文的"schema 变化导致 entity_id 跟着变"在当前项目中**不成立**

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把 `schema_id` 纳入 entity_id hash | 会导致 schema 重编译时所有实体 id 失效 |
| 为 rel 增加 `rel_id = H(schema_id + sub_id + obj_id + props)` | 当前 write protocol 的 ingest_key 已覆盖此需求（每条 field write 含 value） |

#### 3. 与当前代码的对应位置

**3.1 entity_id (idref_v1) 的精确 hash 输入**

| 元素 | 是否参与 idref_v1 hash | 代码位置 |
| --- | --- | --- |
| `entity_type` 名称 | ✓ 参与 | `idref_v1.py` L36-37 |
| identity field 名称 | ✓ 参与 | `idref_v1.py` L58-59 |
| identity field 值 | ✓ 参与 | `idref_v1.py` L62 via `encode_value_bytes()` |
| identity field 的 type_domain | ✓ 参与（tag_code） | `idref_v1.py` L56 via `TAG_CODE_BY_NAME` |
| `schema_digest` / `schema_id` | ✗ 不参与 | 不在 `canonical_bytes_idref_v1()` 中 |
| 非 identity 字段值（props） | ✗ 不参与 | `encode_entity_ref()` (L356-366) 只遍历 `identity_fields` |
| `namespace` / `role` | ✗ 不参与 | idref_v1 不含 schema 级元数据 |

**3.2 关系实体的 entity_ref 字段如何写入**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| entity_ref 值判定 | `entity_write.py: field_value_type()` (L250-281) | 判断字段是否是 entity_ref 类型 |
| entity_ref 值作为 claim 写入 | `entity_write.py: _rest_term_for_value()` (L391-405) | entity_ref 值以 `("entity_ref", encoded_ref)` 形式进入 claim 的 rest_terms |
| 关系实体的自身 identity | `schema_runtime.py: encode_entity_ref()` (L355-367) | 只看关系实体自己的 identity fields，不看它的 entity_ref 字段值 |

**3.3 ingest_key 如何区分"同字段不同值"**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| ingest_key hash 输入 | `write_protocol.py: _compute_ingest_key()` (L235-287) | 包含 `pred_id + e_ref + *rest_terms + source_material + temporal_material` |
| rest_terms 含 value | L282 `*rest_terms` | 每个 rest_term 是 `(type_domain, value)` tuple，所以同字段不同值 → 不同 ingest_key |
| source 幂等因子 | L265-270 | `{source, source_loc, trace_id}` 的 JSON bytes |
| temporal 幂等因子 | L271-276 | `{valid_from, valid_to, version}` 的 JSON bytes |

#### 4. 可执行优化建议

**4.1 应维持的当前边界**

| 建议 | 原因 |
| --- | --- |
| 继续让 idref_v1 不含 schema_digest | 保证 schema 非破坏性变更（新增字段/修改 description）不影响已有实体 id |
| 继续让 entity_ref 字段值不参与关系实体的 identity | 与 entity_id 只由 identity 字段决定的原则一致 |

**4.2 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 文档化"idref_v1 不含 schema_digest"这一重要设计决策 | `core/protocol/` docs 或 `sdk/docs/` | 旧文假设 schema_id 间接影响 entity_id——当前这不成立，应显式记录 |
| 文档化"关系实体 identity 与其 entity_ref 字段值无关" | `sdk/docs/04_relationship_modeling.md`（待建） | 避免用户误以为改变关系端点会改变关系实体自身 id |

**4.3 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 把 `schema_digest` 加入 idref_v1 | 重编译 schema 会导致所有 entity id 失效 |
| 引入独立 `rel_id = H(sub_id + obj_id + props)` | 当前 ingest_key 已包含 value，无需额外 rel_id |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| idref_v1 稳定性 | schema 重编译（增删非 identity 字段）后，同 identity 的实体 id 是否不变 | `core/protocol/idref_v1.py` |
| 关系实体 identity 隔离 | 关系实体的 entity_ref 字段值变化是否不影响实体自身 id | `application/schema_runtime.py`、`entity_write.py` |
| ingest_key 区分度 | 同 field 同 entity 不同 value 是否产生不同 ingest_key | `write_protocol.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **adopt** | 旧文关于"entity_id 只由 key 决定，props 不参与"的原则已被当前项目完全吸收，且当前实现更进一步——idref_v1 不含 schema_id，比旧文设计更稳定 |

**关键差异需要文档化：**

1. 旧文假设 `entity_id = H(schema_id + key_values)`——当前 FactPy 的 `idref_v1` **不含 `schema_digest`**，只含 `entity_type + identity_fields(name, type, value)`。
2. 这意味着当前系统比旧文设计更稳定：schema 非破坏性变更不会影响已有实体 id。
3. 旧文的"同端点不同 props 共存"通过当前 ingest_key（含 value）+ 断言级存储已天然支持，不需要额外 `record_id`。

---

### 文档：`docs_old/symir_logs/11. Rel 的滞后性.md`

#### 1. 原始关注点

这篇文档讨论了 rel 类型实例的一个体验问题：fact 实例自包含，直接可读；rel 实例只存端点 ID + props，读取完整信息需要回查端点 fact。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| rel 读取的"滞后感" | rel 只有 `sub_entity_id / obj_entity_id + props`，端点的完整属性需要二次查询 |
| `include_keys` 选项 | 希望 `to_dict(include_keys=True)` 把端点 key 属性也写入输出 |
| 关系持久化形式 | 默认轻量（只存 ID），可选可读（附带 key 快照） |
| key_fields 可靠性 | 讨论 key_fields 是否真的能区分实体——name-only 场景容易冲突 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 关系只存端点引用，不冗余端点属性 | 当前 entity_ref 字段值在 `EntitySnapshot` 中只存 idref_v1 编码字符串（`sdk/facade.py: _dto_ref_to_sdk_ref()` L714-717），不包含被引用实体的任何属性 |
| 读取完整关系信息需要额外查询 | 当前无自动 join/dereference 机制；`_batch_hydrate()` (`sdk/query_runtime.py` L76-148) 只水合实体自身字段，不递归解引用 entity_ref |
| key_fields 作为 identity 是合理默认但非绝对可靠 | 当前 `Identity(primary_key=True)` 模型等价于"候选主键"，系统不保证唯一 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 需要"可读关系输出"选项 | 当前无 `include_keys` 或等价机制 | `hydrate_entity()` (`entity_view.py` L68-85) 只有 `include_assertions` / `include_history`，没有 `include_referenced_keys` |
| 端点 key 快照对 export/debug 有用 | 当前 entity_ref 字段值是 opaque idref_v1 token | 在 debug/export 场景下不易阅读 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 默认在 rel 持久化中附带端点属性快照 | 会引入冗余和一致性问题 |
| 在 `EntitySnapshot` 中自动解引用所有 entity_ref | 会引发 N+1 查询或循环引用风险 |

#### 3. 与当前代码的对应位置

**3.1 当前关系实体的读取路径：entity_ref 字段值是 opaque string**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| entity_ref 值在 application 层 | `entity_view.py: _hydrate_value()` (L354-371) | entity_ref 字段被恢复为 `EntityRef` 对象（含 entity_type + identity + encoded_ref） |
| entity_ref 值在 SDK 层 | `facade.py: _dto_value_to_sdk_value()` (L706-711) → `_dto_ref_to_sdk_ref()` (L714-717) | `EntityRef` 对象被降为 idref_v1 编码字符串传给用户 |
| EntitySnapshot.fields 内容 | `facade.py: EntitySnapshot` (L166-218) | `_field_values` dict 中 entity_ref 字段的值是 `str`（idref_v1 token），不是对象 |

**3.2 当前无 join/dereference 机制**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 查询水合 | `query_runtime.py: _batch_hydrate()` (L76-148) | 只水合实体自身字段，不递归解引用 entity_ref 值 |
| instance 返回格式 | `query_runtime.py: _rows_to_instances()` (L226-252) | 对 entity_ref 字段无特殊处理 |
| hydrate_entity 参数 | `entity_view.py: hydrate_entity()` (L68-85) | 只有 `include_assertions` / `include_history`，无 `include_keys` |

**3.3 旧文关于 key_fields 可靠性的讨论在当前项目中的映射**

| 旧文建议 | 当前项目对应 | 说明 |
| --- | --- | --- |
| 优先用外部稳定 ID | `Identity(primary_key=True, default_factory="uuid4")` | 支持 UUID 自动生成作为 identity 字段 |
| 复合键更稳 | 多 Identity 字段支持（`EntityMeta.__new__()` L128-169） | 可声明多个 identity 字段组合成复合键 |
| 来源隔离 | `DEDUP_AFFECTING_META_KEYS` (`sdk/ingest.py` L47) | `source/source_loc/trace_id` 参与 ingest_key，但**不参与 entity_id** |
| keep_all 避免误合并 | 当前 `Idempotency(on_conflict="skip")` | 同 ingest_key 跳过；不同 value 天然不同 ingest_key |

#### 4. 可执行优化建议

**4.1 可吸收的具体优化**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 在 export/debug 路径增加"entity_ref 解码为可读 identity dict"的工具函数 | `sdk/facade.py` 或 `application/schema_runtime.py` | 把 idref_v1 token 解码回 `{entity_type, identity}` 供 debug/export 使用 |
| 考虑在 `hydrate_entity()` 增加 `resolve_refs=True` 选项 | `application/entity_view.py` | 可选地为 entity_ref 字段附带被引用实体的 identity 值（不是完整快照，只是 key 字段） |

**4.2 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 默认在持久化中附带端点属性 | 冗余、一致性风险 |
| 自动递归解引用所有 entity_ref | N+1 / 循环引用风险 |
| 把 `source` 纳入 entity_id hash | 会让同一实体在不同来源下产生不同 id，阻碍实体消歧 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| entity_ref 读取 | `EntitySnapshot` 中 entity_ref 字段是否返回 idref_v1 string | `sdk/facade.py` |
| 无递归解引用 | 读取包含 entity_ref 字段的实体时，不触发额外查询 | `sdk/query_runtime.py`、`entity_view.py` |
| idref_v1 解码 | 编码后解码是否能恢复 entity_type + identity dict | `core/protocol/idref_v1.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 旧文指出的 rel "滞后感"在当前项目中仍然存在（entity_ref 字段值是 opaque idref_v1 token）；可考虑增加可选的 ref 解码/解引用工具，但不应默认在持久化中冗余端点属性 |

**更适合当前项目的吸收路径：**

1. 当前"关系只存 entity_ref 引用"的设计是正确的——保持一致性，避免冗余。
2. 旧文真正的痛点是"可读性"——可通过 export/debug 工具函数（idref_v1 decode → identity dict）改善，不需要改持久化模型。
3. key_fields 可靠性讨论中的建议（外部 ID、复合键、keep_all）在当前项目中都已有对应机制支持。

---

### 文档：`docs_old/symir_logs/12. instance merge and meta.md`

#### 1. 原始关注点

这篇文档集中讨论两个问题：instance 的“合并”到底在哪里发生，以及 `meta` 应该是自由字典还是严格 contract。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| merge 是否真正实现 | 旧文很早就意识到 `merge_policy` 只是意图标记，缺少真正的执行器 |
| fact / rel 的合并分组键 | 希望 fact 按 `(schema_id, entity_id)` 分组，rel 按 `(schema_id, sub_entity_id, obj_entity_id)` 分组 |
| rel 是否需要自己的 ID | 讨论过给 rel 增加 `entity_id/rel_id`，以便统一 merge 分组口径 |
| meta 是否应严格化 | 希望 `source / observed_at / ingested_at / confidence / status / evidence_id / provenance / tags` 等字段有明确边界 |
| schema 选项与 instance 证据字段分离 | 旧文倾向把 `merge_policy` 这类策略项移到 `Fact/Rel` schema，而不是继续挂在 instance `meta` 上 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| “合并/共存”语义需要单独设计，不能假装靠 metadata 名字自然发生 | 当前 `write_protocol.set_field()` (`core/evidence/write_protocol.py` L103-130) 只有 `Idempotency(on_conflict="skip")`，并不存在 `max/latest/noisy_or/overwrite` 执行器 |
| 声明元数据与断言写入元数据必须分层 | `Entity.Meta` 只允许 `version/description/tags`（`sdk/schema.py` L229-265）；架构文档也明确声明元数据不参与写入语义（`core/docs/01_architecture.md` L142-154） |
| rel 不必为了 merge 再额外发明一个公开 `rel_id` | 当前最接近的去重主键其实是 `ingest_key`，它已经把 `pred_id + e_ref + rest_terms + source/source_loc/trace_id + temporal` 编进去（`write_protocol.py` L235-287） |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| meta 需要“有边界的开放性” | `sdk_ingest()` 在 `_normalize_user_meta()` (`sdk/ingest.py` L475-487) 只禁止 system-managed key；`_sensitive_meta_warnings()` (L510-527) 对敏感语义 key 发 warning | 还缺一份面向用户的正式 meta contract 文档 |
| 常见 provenance / evidence 字段值得提供 helper | `sdk_validate_provenance()` (`sdk/ingest.py` L86-145) 已覆盖 derivation provenance 的校验 | 仍缺通用的 evidence/meta helper，用户容易把“推荐键”和“系统键”混在一起 |
| meta 值类型需要更明确的支持范围 | `_KEY_KIND_MAP` (`write_protocol.py` L45-77) + `_infer_meta_kind_by_value()` (L335-348) 已约束标量写入 | 用户侧结构化 `dict/list` meta 仍不是公开一等 contract |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把 `merge_policy` 直接加进当前 `Entity.Meta` | 当前 `Entity.Meta` 明确只支持 `version/description/tags`；把写入策略塞回声明层会混淆资产说明与断言语义 |
| 把用户 `meta` 收紧成 closed schema | 这会过早冻结扩展面；当前更合理的是“开放字典 + 保留键禁止 + 敏感键告警 + 类型约束” |
| 为了统一 merge 口径强行公开 `rel_id` | 当前写粒度是 assertion/claim，不是一个统一 `Instance` 对象；公开 `rel_id` 会重新引入“关系记录身份”语义负担 |

#### 3. 与当前代码的对应位置

**3.1 当前 assertion meta contract：开放，但有保留键和类型边界**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SDK 侧用户 meta 归一化 | `sdk/ingest.py: _normalize_user_meta()` (L475-487) | 只要求 dict + 非空字符串 key，并拒绝 `HARD_RESERVED_META_KEYS` (`ingested_at/ingest_key/revoked_asrt_id`) |
| 敏感语义 key 告警 | `sdk/ingest.py: _sensitive_meta_warnings()` (L510-527) | `schema_digest/policy_digest/derived_rule_id/...` 允许出现，但默认发 warning |
| Core 写协议保留键检查 | `core/evidence/write_protocol.py: _normalize_meta()` (L222-232) | 再次拒绝 system-managed key，形成最终写入门槛 |
| MetaRow kind 推断 | `write_protocol.py: _KEY_KIND_MAP` (L45-77)、`_infer_meta_kind_by_value()` (L335-348) | 未命中的 key 仍可写，但值必须是 `bool/str/float/int` 之一 |
| Ledger 落盘形态 | `core/store/ledger.py: MetaRow` (L33-38)、`META_KINDS` (L13) | 存储层支持 `json` kind，但当前公开写入路径并未给用户暴露结构化 meta 键 |

**3.2 当前“merge”最接近的实现其实是 ingest 去重**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 固定写入冲突策略 | `write_protocol.py: set_field()` (L103-130) | 内部写死 `Idempotency(on_conflict="skip")` |
| ingest 去重主键 | `write_protocol.py: _compute_ingest_key()` (L235-287) | 同断言内容 + 同 dedup-affecting meta 才会命中同一个 ingest_key |
| SDK 侧重复统计 | `sdk/ingest.py: sdk_ingest()` (L148-240) | 重复写入会被记为 `duplicate_count/skipped_count`，不是执行 merge 算法 |
| 显式替换语义 | `write_protocol.py: replace_field()` (L181-198) | 当前“更新”是 `retract + set`，不是按 policy 合并多条证据 |

**3.3 当前声明元数据边界：不接受 schema 级 merge 选项**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| `Entity.Meta` 白名单 | `sdk/schema.py: _extract_entity_declaration_fields()` (L229-265) | 仅支持 `version/description/tags`；传入 `merge_policy` 会报错 |
| declaration → spec 编译 | `sdk/schema.py: EntityMeta.__new__()` (L147-167) | 只有上述三类声明元数据会进入 `sdk_entity_spec` |
| 架构口径 | `core/docs/01_architecture.md` §6.3 (L142-154) | 声明元数据不参与 where / candidate / accept 写入语义 |

**3.4 当前缺口：没有旧文设想的 merge executor**

旧文想要的 `max/latest/noisy_or/overwrite/keep_all` 在当前仓库里都没有真正实现。当前系统只有：

- 去重：`ingest_key` + `Idempotency(on_conflict="skip")`
- 替换：`replace_field()` 的 `retract + set`
- 聚合显示：view/projector 层对 `confidence` 等 meta 做投影，但这不是写时 merge

这意味着旧文提出的问题仍然有效，但正确落点应是 **write protocol / policy 设计**，而不是恢复一个顶层 `Instance.merge_policy` API。

#### 4. 可执行优化建议

**4.1 文档层（低风险，可立即执行）**

| 建议 | 预期产出 | 关联文件 |
| --- | --- | --- |
| 补一节“assertion meta contract”文档 | 明确保留键、敏感键、推荐键、dedup-affecting 键的分类 | `src/factpy_kernel/sdk/docs/00_user_guide.en.md` 或新建 `05_assertion_meta.md` |
| 明确 `Entity.Meta` 与 assertion `meta` 的职责边界 | 避免用户继续把 `merge_policy`、`source`、`provenance` 混到声明层 | 同上 |

**4.2 Helper 层（中风险，可逐步收口）**

| 建议 | 实现方式 | 关联模块 |
| --- | --- | --- |
| 提供 `known_meta` / `provenance` helper | 在 SDK 边界提供可选 typed helper，但底层仍写入普通 dict meta | `sdk/ingest.py`、`sdk/store.py` |
| 增加“推荐键校验”而不是“未知键报错”模式 | 保持开放扩展面，同时让常见错误更早暴露 | 同上 |
| 若要支持结构化 meta，显式增加公开 JSON contract | 例如受控地下沉到 `MetaRow(kind="json")`，不要依赖隐式 dict/list 推断 | `core/evidence/write_protocol.py`、`core/store/ledger.py` |

**4.3 Merge 语义层（较高风险，需单独设计）**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若将来真的支持 `latest/max/noisy_or/keep_all` | 放到 `write_protocol` / `policy` 层单独设计 | 不应伪装成 `meta["merge_policy"]` 的字符串约定 |
| 若需要 relation 级“同端点多记录”策略 | 先定义 group key 和冲突规则，再决定是否要公开 `rel_id` | 优先保持内部 group key，而非新增用户可见 ID |

**4.4 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 扩展 `Entity.Meta` 支持 `merge_policy` / `status` / `source` | 会打破当前 declaration metadata 的清晰边界 |
| 把 unknown meta key 全部视为错误 | 当前项目还在演进阶段，开放扩展面比 closed schema 更务实 |
| 把 dedup/merge 语义寄托在 rel/fact 的公开 ID 命名上 | 真正决定行为的是 write contract，不是字段名字 |

#### 5. 验证与测试建议

| 测试类型 | 测试点 | 相关模块 |
| --- | --- | --- |
| meta 保留键校验 | `ingested_at/ingest_key/revoked_asrt_id` 是否在 SDK/core 两层都被拒绝 | `sdk/ingest.py`、`core/evidence/write_protocol.py` |
| 敏感键告警 | `schema_digest/policy_digest/derived_rule_id` 等是否发 warning 而非直接拒绝 | `sdk/ingest.py` |
| ingest 去重 | `source/source_loc/trace_id/valid_from/valid_to/version` 变化是否改变 ingest_key | `core/evidence/write_protocol.py` |
| declaration metadata 白名单 | `Entity.Meta.merge_policy = "latest"` 是否正确抛错 | `sdk/schema.py` |
| 结构化 meta 扩展（若新增） | `dict/list` 是否稳定写成 `MetaRow(kind="json")` 并正确读回 | `core/evidence/write_protocol.py`、`core/store/ledger.py` |

#### 6. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 旧文对“merge 还没真正实现”和“meta 需要 contract”这两个判断今天仍然成立，但当前项目更适合沿着 `ingest_key/idempotency + open meta contract + declaration/assertion 分层` 继续演进，而不是回到 strict meta 或 schema-level `merge_policy` 设计 |

**更适合当前项目的吸收路径：**

1. 短期先把 assertion `meta` 的分类和边界文档化，让用户知道哪些键是推荐的、哪些键会影响 dedup、哪些键是系统保留。
2. 中期若要改善体验，应增加 typed helper / validator，而不是把 open meta 改成 closed schema。
3. 长期若确实需要“多证据合并策略”，应在 `write_protocol` / `policy` 层设计真正的 merge contract，再决定是否需要公开新的策略字段。

---

### 文档：`docs_old/symir_logs/13. CSV.md`

#### 1. 原始关注点

这篇文档不是在讨论“CSV 列如何映射字段”，而是在追问另一层问题：对 rel 类型来说，CSV 行往往不是直接落盘的事实，而是基于既有 fact 索引 join/匹配后“构造出来”的关系。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| rel CSV 是二阶段构造 | 先有 fact，再按 key/过滤条件匹配端点，最后生成关系 |
| 部分 key 匹配 | 允许 key 不完整，用剩余条件做过滤 |
| 多匹配策略 | 多个端点候选时，是否报错、取第一条，还是做笛卡尔积 |
| props 是否参与过滤 | 借鉴 Neo4j 风格，讨论属性参与匹配还是仅用于新关系属性 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| rel CSV 构造本质上是一个“join / normalize”阶段，而不是 write protocol 本身 | 当前 `sdk.ingest(...)` 只接受 normalized write items（`sdk/ingest.py` L148-173；SDK 文档 `02_readwrite_and_ingest.en.md` L171-177），没有任何“先查 fact 再构造 rel”的内置流程 |
| 多匹配策略必须显式，不应隐式做笛卡尔积 | 当前系统完全没有自动 rel builder，这反而保留了行为边界的清晰性 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 应提供独立的输入规范化/构造层 | `application/docs/01_overview.md` L156-163 已把 `authoring_normalize.py` 列为尚未落地能力 | 目前还没有用户侧 CSV → ingest items / rel builder helper |
| props 参与过滤应是显式策略，不应默认发生 | 当前没有任何内建 rel CSV builder，因此也没有错误的默认策略 | 后续若实现，需要把 `match_fields` / `prop_filter` 明确成参数 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 在 core `sdk.ingest` / `write_protocol` 中塞入 Neo4j 风格 rel 构造 | 这会把“匹配/搜索”语义和“断言写入”语义混到一起 |
| 继续沿用旧的 `facts: Iterable[Instance] -> rel Instance` API | 当前项目没有统一 `Instance` 类，正确的输出应是 normalized ingest items / `EntityWriteCommand` 一类中间结果 |

#### 3. 与当前代码的对应位置

**3.1 当前没有用户侧 CSV 导入或 rel builder**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| `sdk.ingest` 支持的输入形状 | `sdk/ingest.py` L148-173；`sdk/docs/02_readwrite_and_ingest.en.md` L171-177 | 只接受 `set/add/retract` item，不接受 CSV 行或 rel build spec |
| 仓库里唯一明确的 CSV 解析 | `adapters/souffle/runner.py: _parse_souffle_line()` (L251-269) | 这里只是解析 Souffle 输出，不是用户数据导入 |
| normalize helper 缺位 | `application/docs/01_overview.md` L156-163 | `authoring_normalize.py` 仍未实现 |

**3.2 当前 rel 写入前提：端点已经被解析成 entity_ref**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 关系端点最终都要变成 `entity_ref` 值 | `sdk/schema.py` / `authoring/schema_compile.py`（前文已覆盖） | 当前模型没有“按 key 临时匹配端点”的公开写语法 |
| 去重与写入 | `core/evidence/write_protocol.py` L103-130, L235-287 | 只关心 `pred_id/e_ref/rest_terms/meta`，不负责查找端点候选 |

#### 4. 可执行优化建议

**4.1 更适合当前项目的落点**

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 新增窄范围 rel CSV normalize helper | 未来 `application/authoring_normalize.py` | 输入 `rows + schema/runtime resolver`，输出 normalized ingest items |
| 把匹配策略显式成参数 | 同上 | 例如 `mode="strict|partial"`、`multi="error|cartesian"` |
| 明确 props 是否参与过滤 | 同上 | 默认不参与；若参与，必须显式声明 |

**4.2 不建议的方向**

| 不建议 | 原因 |
| --- | --- |
| 默认按“部分 key + props + 多匹配”自动推断 | 容易生成不可预测的关系爆炸 |
| 把 CSV/Neo4j 语义写死进核心 SDK | 当前核心 SDK 应继续保持“只吃 canonical write items” |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档真正值得保留的是：rel CSV 导入本质上是一个独立的 join/normalize 阶段。若未来要支持，应新增外围 helper，而不是修改 `sdk.ingest` 或 `write_protocol` 的核心 contract |

---

### 文档：`docs_old/symir_logs/14.Rule.md`

#### 1. 原始关注点

这篇文档试图把旧的 rule 设计重做成更统一的“schema-aware object DSL”：head 直接引用 `Fact/Rel`，body 用 `Ref/Expr`，变量/常量类型由 schema 自动补足，而不是用户显式填写 datatype。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| 规则层与 schema 层统一 | 直接复用 `Fact/Rel` 作为 head/body 里的 schema |
| `Var/Const` 去 datatype 化 | 类型由 schema 驱动，而不是用户重复填写 |
| 用更直观的表达式接口 | 希望弱化 `Call(...)`，改成更自然的数学/比较表达 |
| 支持结构化引用 | 例如 `Sub = person(SubName, SubAddr)` 这类 compound 端点写法 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 规则 authoring 应优先走对象 DSL，而不是字符串 DSL | service/SDK v1 都明确拒绝字符串 DSL（`core/docs/04_public_contract_v1.md` L9-39；`service/rules_v1.py` L133-157） |
| 变量不应暴露 datatype 接口 | SDK 侧 `LogicVar` (`sdk/dsl/expr.py` L35-97) 和 core AST `Var/Const` (`core/rules/where_ast.py` L19-31) 都不携带 datatype |
| 数学/比较表达应比 `Call("add", ...)` 更自然 | 当前对象 DSL 用 Python 运算符生成 `CompareExpr/BinaryExpr`，再下沉成 `eq/gt/add/addc/mulc/...`（`sdk/dsl/expr.py` L60-97, L368-415） |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| schema-aware rule DSL 很重要 | 当前 `Rule` / `Derivation` 都走结构化对象 DSL + compile gate | 但 `where` 的常量类型还没有做全面 schema-aware 校验 |
| “head 直接与 schema 对齐”的诉求是对的 | 当前更接近体现在 `Derivation.head` 的 `HeadCall` 上（`sdk/dsl/rule.py` L115-167） | 当前 `Rule` 仍是 `select + where` 的 query 规则，不是 `head + bodies` 结构 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把当前 `Rule` 改成旧文的 `Rule(head, bodies)` | 当前架构已明确区分 `Rule(select, where)` 与 `Derivation(head, where)`；直接合并会破坏 v1 public contract |
| 在未扩展 core term IR 前，把结构化 `person(...)` 复合项塞进规则 head/body | 当前 core term 只有 `Var|Const`，没有 compound term 节点；直接加语法糖会让后端/校验不一致 |
| 仅通过命名约定模拟 `Sub/Obj` 结构化引用 | 语义过隐式，编译和调试成本高 |

#### 3. 与当前代码的对应位置

**3.1 当前规则/派生 DSL 的职责分层**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| Query-style `Rule` | `sdk/dsl/rule.py: Rule` (L45-112) | `select + where`，用于 `sdk.run(rule)` |
| Head-producing `Derivation` | `sdk/dsl/rule.py: Derivation` (L115-167) | `head + where`，用于 candidate 生成 |
| `head` 的结构化表示 | `sdk/dsl/expr.py: HeadCall` (L206-222) | 当前 head 只在 derivation/query 相关路径使用 |

**3.2 当前表达式层已经回答了旧文对 `Var/Const/Call` 的一部分问题**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 无 datatype 的逻辑变量 | `sdk/dsl/expr.py: LogicVar` (L35-97) | 用户只声明变量标签；不写 datatype |
| 运算符 sugar | `sdk/dsl/expr.py` L60-97, L368-415 | `==, >, +, -, *` 被降到 core where IR |
| 裸谓词引用 | `sdk/dsl/expr.py: Pred(...)` (L269-274) | 当前是 `pred_id` 级 atom，不是 `Ref(schema=...)` 对象 |

**3.3 当前编译和公开 contract 已经稳定，不适合大改 DSL 主形状**

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| authoring 规则编译入口 | `authoring/rule_compile.py` L27-71 | 编译目标仍是 `rule_id/version/select_vars/where/expose` |
| object-rule-only 契约 | `service/rules_v1.py` L133-157 | 只接受结构化 rule object，不接受 string DSL |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 保持 `Rule` 与 `Derivation` 分离 | 文档层 | 把“旧文里的 head 规则”明确映射到今天的 `Derivation`，避免重复讨论 |
| 若未来需要结构化端点项，先扩展 core term IR | `core/rules/where_ast.py`、各 backend validator/exporter | 先有显式 AST，再谈 SDK 语法糖 |
| 若只想提升易用性，继续增加对象 DSL sugar，而不是重命名成 `Ref/Expr/Call` 新族谱 | `sdk/dsl/expr.py` | 当前运算符 sugar 已经比旧文设计更接近 Python 用户习惯 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 旧文关于“schema-aware object DSL、无 datatype 变量、自然表达式 sugar”的判断今天基本成立，但其核心 `Rule(head, bodies)` 形状不应直接迁移；当前更合理的映射是继续保持 `Rule`/`Derivation` 分层，并把 head-producing 能力留在 `Derivation` |

---

### 文档：`docs_old/symir_logs/15. Rule convention.md`

#### 1. 原始关注点

这篇文档进一步讨论规则里的“命名约定”和“渲染期自动展开”：是否可以只保存 `Sub/Obj/SubName/...` 这类约定，而把 `Unify(Sub, person(...))` 之类机械逻辑延后到 render 阶段自动补出。

核心诉求包括：

| 诉求 | 描述 |
| --- | --- |
| 规则数据模板尽量干净 | 只存用户真正写的部分，不把机械补全逻辑持久化 |
| compound / flattened 两种端点展开 policy | 前者保留 `Sub/Obj` 结构化端点，后者直接扁平化为 `SubName/SubAddr/...` |
| 渲染阶段根据后端补全 | 不同后端可用不同展开方式 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 值得保留的工程原则：**

| 思想 | 当前项目对应 |
| --- | --- |
| “规范数据模板”与“后端渲染策略”应分层 | 当前 `Rule/Derivation -> authoring payload -> core AST -> backend profile` 已经是分层架构 |
| 纯机械展开若确实存在，优先做成 exporter/renderer policy | 这比把自动补出的逻辑持久化进主 RuleSpec 更干净 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 后端 profile 可以驱动不同规则约束 | `validate_query_rule_ast(..., profile=...)` 已存在（`authoring/rule_compile.py` L59-65） | 目前 profile 只控制校验能力，不控制 compound/flattened 这类渲染策略 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把 `compound/flattened` 作为当前 `RuleSpec` v1 的核心字段 | 当前 v1 public contract 已稳定，不应为尚未存在的结构化 term 能力扩面 |
| 以变量命名约定承载语义 | 名字本身不应成为 backend 级语义源 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| 当前 core term 模型 | `core/rules/where_ast.py` L19-31 | 只有 `Var/Const`，没有 compound/struct term |
| 当前 builtin / not / ruleref 能力边界 | `core/rules/where_ast_validate.py` L31-37, L181-239 | 支持集是显式白名单，不包含结构化 `Unify/Struct` |
| 当前对象 DSL 的 where lowering | `sdk/dsl/expr.py` L277-447 | 也没有结构化项或统一展开 policy |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若未来确实要支持 `compound/flattened`，先把它定义成 exporter/render profile | backend/export 层 | 例如仅在 ProbLog/Prolog 导出器里增加可选端点展开模式 |
| 在主文档里明确“变量命名不是语义 contract” | `sdk/docs/03_rules_and_derivations*.md` | 防止用户把 `SubName` 之类误当作系统保留协议 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档最有价值的不是命名约定本身，而是“模板层与渲染层应分离”的原则。若未来要支持 compound/flattened，应把它放在 exporter/render policy，而不是当前 RuleSpec v1 主 contract |

---

### 文档：`docs_old/symir_logs/16. schema and rule.md`

#### 1. 原始关注点

这篇文档讨论了两个问题：规则是否也应该像 `FactLayer.from_dict(payload)` 那样可重建、可持久化；以及面对 LLM 只产出部分 payload 的场景，是否需要一个 `RuleLayer` 来管理规则集合和重建流程。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| rule 应该是纯数据资产，可导出、注册、版本化 | `Rule.to_authoring_payload()` (`sdk/dsl/rule.py` L68-84) + `SDKRegistry.register_rule()` (`sdk/registry.py` L99-107) + `FileAuthoringRegistry.register_rule_spec()` (`authoring/registry_fs.py` L80-115) 已形成完整链路 |
| 规则集合管理应有独立资产层 | 当前已经由 `SDKRegistry` / `FileAuthoringRegistry` / runtime `RuleRegistry` 分层承担 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| payload -> SDK Rule 的 round-trip helper 有价值 | 当前已有 `to_authoring_payload()`，但没有对称的 `Rule.from_authoring_payload()` | 若上层确实频繁要从 payload 回构对象，可补一个窄 helper |
| LLM 产出的 partial payload 需要外部上下文拼装 | service v1 只接受完整 structured rule object（`service/rules_v1.py` L133-157） | 仓库里还没有正式的“LLM rule draft -> authoring payload” normalize helper |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 新造一个与现有 registry 并列的 `RuleLayer` | 当前 registry/authoring/runtime 三层已经覆盖“注册、持久化、依赖解析”的职责，重复抽象会增加心智负担 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SDK 对象序列化 | `sdk/dsl/rule.py: Rule.to_authoring_payload()` (L68-84) | 将 SDK Rule 变成 authoring payload |
| SDK 规则注册 | `sdk/registry.py: register_rule()` (L99-107) | 统一走 compile + registry write |
| registry 持久化 | `authoring/registry_fs.py: register_rule_spec()` (L80-115) | canonical JSON + manifest digest |
| runtime 依赖解析 | `core/rules/rule_ir.py: RuleRegistry` (L37-53) | 只管运行时 `RuleRef` 解析，不负责资产持久化 |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若确有上层需求，新增 `Rule.from_authoring_payload()` 或 `sdk.rule_from_payload()` | `sdk/dsl/rule.py` 或 `sdk/store.py` | 形成对象层 round-trip，对称于 `to_authoring_payload()` |
| 针对 LLM 场景增加窄 normalize helper | `authoring` 外围 | 输入 partial draft + 外部 head/context，输出完整 authoring payload |
| 继续复用现有 registry，而不是新增 `RuleLayer` | 文档层 | 把“规则集合管理”的正确入口说清楚 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **adopt** | 旧文关于“rule 应是可持久化数据资产”的判断与当前架构完全一致；需要吸收的不是 `RuleLayer` 这个名字，而是继续沿用现有 `Rule -> authoring payload -> registry` 链路，并在需要时补 round-trip helper |

---

### 文档：`docs_old/symir_logs/17. rule 数据验证.md`

#### 1. 原始关注点

这篇文档围绕 rule 的数据验证展开，重点强调两点：

| 诉求 | 描述 |
| --- | --- |
| `Var/Const` 不应让用户填写 datatype | datatype 应由导入的 schema / signature 来验证 |
| LLM / JSON schema 输出要和当前 Rule 结构对齐 | 结构化 payload 应能被校验并回构 |

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| term 节点应保持去 datatype 化 | core AST `Var/Const` (`where_ast.py` L19-31) 和 SDK `LogicVar` (`sdk/dsl/expr.py` L35-97) 都不暴露 datatype |
| rule 验证应是单独的 compile/AST gate，而不是散落在 term 构造器里 | 当前 `compile_authoring_rule_v1()` (`authoring/rule_compile.py` L27-71) + `validate_query_rule_ast()` (`rule_compile.py` L59-65) 已建立主校验栈 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| schema-aware validation 是正确方向 | `where_schema_lowering.py` 会做 exists/path sugar 重写，并校验 cross-coordinate primary_key 比较（L12-28, L217-291） | 但普通 `PredAtom` 的 const 仍没有全面按 `schema_ir.arg_specs.type_domain` 校验 |
| 结构化 JSON rule payload 应有稳定 object contract | service v1 已明确 `rule` / `where` 必须是结构化对象，不接受 string DSL（`service/rules_v1.py` L133-157） | 仓库里还没有官方的 JSON Schema / Pydantic contract 导出能力 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把旧文的 `Ref(schema_id=...)` / `predicate_id` 体系整体搬回 | 当前 v1 public contract 已经围绕 `pred_id`、`entity_type`、`RuleRef`、structured where IR 稳定下来 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| core term AST | `core/rules/where_ast.py` L19-31 | `Var/Const` 只存名字和值，不存 datatype |
| AST 形状/数据流校验 | `core/rules/where_ast_validate.py` L54-70, L132-239 | 校验 focus 在 shape、builtin、not/ruleref policy、dataflow |
| schema-aware sugar lowering | `authoring/where_schema_lowering.py` L12-28, L217-291 | 目前只做很窄的一层 schema-aware 检查 |
| string DSL 拒绝 | `core/docs/04_public_contract_v1.md` L9-39；`service/rules_v1.py` L133-157 | 对外 contract 已经固定为 structured object |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 为普通 `PredAtom` 增加可选 schema-aware const 类型校验 | `authoring/rule_compile.py` 或新 helper | 基于 `schema_ir.predicates[].arg_specs[].type_domain` 对常量做静态检查 |
| 若要承接 LLM/外部系统，补官方 JSON Schema 导出 | `service/rules_v1.py` 或 `authoring` 辅助模块 | 让外部 structured payload 有正式 contract，而不是仅靠文档描述 |
| 保持 datatype 不进入 `Var/Const` 用户接口 | 文档层 | 继续强化“datatype 是 schema 责任，不是 term 构造责任” |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 旧文关于“term 去 datatype 化、验证应由 schema/compile 驱动”的判断是正确的；当前已做对一半，但还缺一层更普遍的 schema-aware constant validation 与正式的外部 rule JSON contract |

---

### 文档：`docs_old/symir_logs/18. 从持久化数据创建.md`

#### 1. 原始关注点

这篇文档讨论的是 schema 资产恢复后的再组合问题：如果节点/fact schema 已经本地持久化，后续想继续定义新的关系/rel schema，是否必须先把被引用的 fact schema 恢复成对象，而不能只靠 `schema_id`。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已验证正确的方向：**

| 思想 | 当前实现状态 |
| --- | --- |
| 关系/引用型 schema 的 authoring 应依赖“完整 schema 对象信息”，而不是裸字符串 ID | 当前 SDK schema 直接依赖 Python `Entity` 类和字段注解；编译时据此生成 `entity_ref` 字段与 predicates（`sdk/schema.py` L147-166） |
| “先有实体定义，再有关系定义”是合理工程顺序 | 当前作者态 schema 仍是整份 `schema_ir` 资产统一编译，不支持脱离实体定义单独拼装关系类型 |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 持久化 schema 资产恢复后继续 authoring 是合理需求 | 现有 registry / service 可以读取 `schema_ir`（如 runtime session 从 `registry_root` 载入 schema） | 但没有 `Entity.from_schema_ir(...)` 或“从已持久化 schema 资产回构 SDK 类”这类高层 API |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 复刻旧式 `FactLayer.from_dict(...) -> 再拼新 Rel` 运行时工厂 | 当前 FactPy 的 schema authoring 主路径是 `Entity` 类 / authoring payload -> compile，不是运行时拼接 schema 对象图 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SDK schema 编译依赖类对象与注解 | `sdk/schema.py` L147-166 | `identity_fields/fields` 从类和注解编译而来，不接受裸 `schema_id` 拼装关系 |
| 基于 classes 恢复 store | `sdk/store.py: from_schema_classes()` (L111-144) | 当前恢复入口是“已知 Entity classes + 可选 ledger_path” |
| 基于 registry/schema_ir 恢复 runtime | `service/runtime_v1.py: open_runtime_session()` (L121-143) | 当前服务层可用 `schema_ir` / `registry_root` 恢复运行时，但这不是 SDK 类回构 |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若未来确有需求，提供 authoring 级“读 schema_ir 后继续编辑”的 helper | `authoring` 外围 | 输出 authoring payload patch / schema editor state，而不是试图动态生成新的 `Entity` 类 |
| 继续保持“对象/类优先，ID 内部化” | 文档层 | 把这条原则写清楚，避免后续重提“只靠 schema_id 拼 schema” |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 旧文的核心判断是对的：schema 组合必须依赖完整 schema 信息，不应靠裸 ID 硬拼。当前 FactPy 已在 SDK authoring 层贯彻这一点，但还没有“从持久化 schema 资产继续 authoring”的高层 helper |

---

### 文档：`docs_old/symir_logs/19. schema ID 更改.md`

#### 1. 原始关注点

这篇文档集中强调一个边界：用户侧 API 应尽量使用 schema 对象本身进行校验与构造，`schema_id`/`predicate_id` 只能作为内部索引、序列化和缓存键；否则无法即时做 arity/type validation，也容易在内部集合里踩到可哈希性问题。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 用户 authoring 入口应优先使用 schema 对象/类，而不是 ID 字符串 | 当前 SDK 以 `Entity` 类、字段描述符、`Rule/Derivation` 对象 DSL 为主；`from_schema_classes(...)` 也是 class-first（`sdk/store.py` L111-144） |
| digest / pred_id / schema_id 更适合作为内部契约 | 当前 `schema_digest` 用于 registry/runtime/ledger 绑定与校验，不暴露为日常 authoring API（`sdk/store.py` L123-138；`service/runtime_v1.py` L612-623） |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 内部索引应统一降成稳定字符串键 | 当前 registry manifest、ledger meta、pred_id 路径都已是字符串键 | 但在部分低层 IR/service payload 中仍会直接出现 `pred_id`；这是编译后 contract，不是用户友好层 |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把所有内部 `pred_id/schema_digest` 也一并禁掉 | registry、runtime、service payload、ledger 绑定都需要稳定字符串标识；应区分“用户 authoring 面”和“编译后内部 contract” |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| class-first SDK 入口 | `sdk/store.py: from_schema_classes()` (L111-144) | 用 `Entity` 类恢复 SDKStore |
| Schema digest 内部绑定 | `sdk/store.py` L123-138；`service/runtime_v1.py` L612-623 | digest 用于 schema 一致性校验 |
| 编译后规则内部标识 | `sdk/dsl/expr.py: Pred(...)` (L269-274) | object DSL 最终会降成 `pred_id` 级 IR，这是内部/编译后 contract |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 继续保持“authoring object-first / compiled IR id-first”的分层说明 | `sdk/docs/*`、`core/docs/04_public_contract_v1.md` | 把两层 contract 写清楚，避免误把内部 `pred_id` 当成用户主 API |
| 若新增上层 helper，默认接受对象/类，再在内部统一降成字符串键 | 新 helper 层 | 防止未来重复走回 schema_id-first 设计 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **adopt** | 旧文关于“用户侧对象优先、ID 内部化”的判断与当前 FactPy 完全一致。需要保留的是这条 API 分层原则，而不是把内部 `pred_id/schema_digest` 也错误地从编译后 contract 中移除 |

---

### 文档：`docs_old/symir_logs/20. Ledger SQLite 持久化.md`

#### 1. 原始关注点

这篇文档已经不是“蓝图讨论”，而是在记录一套明确的实现落地：Ledger 迁移到 SQLite 持久化、原子写入口收口到 `append_assertion/append_revocation`、`ingest_key` 独立表、以及 SDK/runtime 的 `ledger_path + schema_digest` 恢复机制。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现完整吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| SQLite 作为真相源，内存索引作为读缓存 | `Ledger` 现在就是 SQLite write-through cache（`core/store/ledger.py` L210-243, L651-679） |
| 写入必须通过原子入口 | `append_assertion()` / `append_revocation()` 已是标准入口（`ledger.py` L268-390），`write_protocol` 也已经切过去（前文 doc12 已覆盖） |
| ingest_key 应有独立索引表并支持 lazy backfill | `ingest_keys` 表与 `_find_ingest_key()` / `_backfill_ingest_key()` 已实现（`ledger.py` L94-98, L684-713） |
| `ledger_path` 恢复必须绑定 schema digest | SDK 和 service 都会在打开 ledger 时校验/写入 `schema_digest`（`sdk/store.py` L123-138；`service/runtime_v1.py` L604-623） |

**◐ 仍需持续注意的边界：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| 多进程写入不是当前目标 | 当前实现使用 SQLite + 进程内缓存，没有缓存失效协议 | 文档上应继续明确“单进程/单 writer”假设 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| SQLite DDL 与索引 | `core/store/ledger.py` L63-122 | `claims/claim_args/meta_rows/revokes/ingest_keys/ledger_meta` 全部在此定义 |
| Ledger 初始化与 WAL 模式 | `ledger.py` L218-243 | 文件型 SQLite 使用 `WAL`；`:memory:` 仍保留 |
| 原子 assertion 写入 | `ledger.py: append_assertion()` (L268-334) | 事务提交后再刷新内存索引 |
| 原子 revocation 写入 | `ledger.py: append_revocation()` (L336-390) | 与 assertion 路径一致 |
| DB -> 内存索引回放 | `ledger.py: _load_from_db()` (L651-679) | 进程重启后可恢复 |
| SDK 恢复工厂 | `sdk/store.py: from_schema_classes()` (L111-144) | `ledger_path` 与 `schema_digest` 绑定 |
| service 恢复工厂 | `service/runtime_v1.py` L121-143, L604-623 | runtime session 打开/创建 file-backed ledger |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 在用户文档里继续强调单进程缓存假设 | `sdk/docs/00_user_guide*.md`、`service/docs/01_overview.md` | 避免用户误把 file-backed ledger 当成多进程共享缓存 |
| 未来若彻底移除 legacy `append_*`，补一次对外迁移说明 | `core/store/ledger.py`、迁移文档 | 当前这些旧入口仍属兼容层 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **adopt** | 这篇文档记录的核心方案今天已经实装完成，且与当前代码完全一致。后续更多是文档澄清和兼容接口收尾，不再是架构方向问题 |

---

### 文档：`docs_old/symir_logs/ME CODEX.md`

| 结论 | 说明 |
| --- | --- |
| **skip** | 源文件当前为空，没有可提炼的设计信息 |

---

### 文档：`docs_old/symir_logs/er.md`

#### 1. 原始关注点

这篇文档提出了一整套高层 ER（Entity Resolution）建模：`Mention/Canonical` 双层实体、`canon_of` 单值映射、外部 bridge key、以及 `canon_policy`/`policy_mode` 驱动的确定化 tie-break。

#### 2. 对当前 FactPy 仍然有效的思想

**✓ 已被当前实现吸收的部分：**

| 思想 | 当前实现状态 |
| --- | --- |
| 单值映射冲突需要显式解析，而不是静默选择 | `core/mapping/canon.py` 已实现 `resolve_mapping_predicate()`，默认冲突即报错（L50-147, L189-247） |
| tie-break 必须确定且可审计 | 当前已支持 `error / latest_by_ingested_at_then_min_assertion_id / prefer_source / max_confidence`（`canon.py` L189-247） |
| mapping 解析应是单独查询入口 | architecture 明确有 `mapping/` 模块与 `resolve_mapping` 查询（`core/docs/01_architecture.md` L36, L55, L58）；service 也有 `/queries/resolve-mapping`（`service/runtime_v1.py` L280-296；`service/docs/01_overview.md` L61-64） |

**◐ 部分实现，仍可继续吸收：**

| 思想 | 当前状态 | 差距 |
| --- | --- | --- |
| Mention/Canonical 分层对某些业务确实有价值 | 当前可以用普通 `Entity` + `is_mapping=true` 谓词手工建模 | 但还没有 `MentionMixin / CanonicalMixin / canon_of` 这套一等 SDK surface |
| bridge key 可逆编码是合理需求 | 当前 core 已有 `protocol.tup_v1` 作为 typed tuple 编码底座（见 architecture 文档 L43） | 但没有 `ERCompiler` / `key_to_mention` 一类高层 helper |

**✗ 不建议直接采纳的设计：**

| 设计 | 不采纳原因 |
| --- | --- |
| 把 `MentionMixin / CanonicalMixin / CanonPolicyConfig / export(...)` 这整套 API 直接当成现状写进当前文档 | 当前仓库并没有这些公开类型；只有更底层的 mapping resolver 和 query 入口 |

#### 3. 与当前代码的对应位置

| 关注点 | 当前代码位置 | 说明 |
| --- | --- | --- |
| mapping 冲突解析 | `core/mapping/canon.py` L50-247 | 当前 ER 最接近的内核能力 |
| `policy_mode='idb'` 对 tie-break 的限制 | `core/store/_queries.py: resolve_mapping()` (L76-99) | tie-break 需要 `policy_mode='edb'` |
| service 查询入口 | `service/runtime_v1.py: resolve_runtime_mapping()` (L280-296) | 返回 chosen map / candidates / decisions / conflicts |

#### 4. 可执行优化建议

| 建议 | 实现位置 | 说明 |
| --- | --- | --- |
| 若未来正式开放 ER surface，直接基于现有 mapping substrate 封装 | `sdk` / `authoring` 外围 | 把 `canon_of` 落成 `is_mapping=true` 的受限 schema 模板，而不是另起一套存储语义 |
| 在文档里先把“当前只有 mapping substrate，没有 Mention/Canonical SDK API”写清楚 | 新建 `docs/er_notes.md` 或补到本文件 | 避免把路线图误写成现状 |

#### 5. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇文档提出的 ER 高层建模思路有价值，但当前 FactPy 只实现了底层 mapping 解析内核，还没有相应的公开 SDK surface。若未来推进，应建立在现有 `is_mapping=true + resolve_mapping` 基础上 |

---

### 文档：`docs_old/symir_logs/er_recipes.md`

#### 1. 原始关注点

这篇文档是 `er.md` 的操作化版本，强调默认安全模式、稳定 tie-break、桥接键可逆、以及“ER 规则不应污染普通 functional/multi 字段 chosen 语义”。

#### 2. 对当前 FactPy 仍然有效的思想

| 思想 | 当前实现状态 |
| --- | --- |
| 默认安全模式应是冲突即报错 | 当前 mapping tie-break 默认就是 `error`（`core/mapping/canon.py` L189-203） |
| `prefer_source / max_confidence / latest` 这类 tie-break 要显式配置 | 当前 `prefer_source / max_confidence / latest_by_ingested_at_then_min_assertion_id` 已实现（`canon.py` L201-247） |
| tie-break 需要稳定兜底 | 当前实现的 tie-break 都带有确定性次级排序（例如 assertion id） |
| mapping 策略应只作用于 mapping predicates | `resolve_mapping()` 明确只接受 `is_mapping=true` 谓词（`core/store/_queries.py` L76-99；`service/runtime_v1.py` L943-959） |

#### 3. 不宜误读为现状的部分

| 旧文写法 | 当前实际情况 |
| --- | --- |
| `PersonMention` / `CanonicalPerson` / `canon_of` 示例类已可直接使用 | 当前并无对应 SDK mixin / helper |
| `CanonPolicyConfig` / `ERCompiler` / `export(..., canon_policy=...)` 已存在 | 当前并无这些公开类型；只有更底层的 mapping 解析接口 |

#### 4. 结论

| 结论 | 说明 |
| --- | --- |
| **consider** | 这篇 recipe 文档的“默认报错、稳定 tie-break、mapping 与普通谓词隔离”三条操作原则是正确的；但示例 API 目前尚未在当前项目中落地，应当被视为未来高层封装设想 |

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
| `schema_id` (per-entity hash) | `schema_digest`（全局，整份 `schema_ir`）；entity 粒度的 structural digest 尚无 |
| `key_fields` | `Identity(primary_key=True)` 标记的字段集合 |
| `freeze()` | `schema_compile.py` 编译 + `schema_ir` 序列化 |
| `derived_signature` | 无直接对应；未来 graph projection 层可派生 |
| `FactLayer` / `FactSchema` (registry) | `FileAuthoringRegistry`（authoring 资产仓库）+ `SDKRegistry`（SDK facade） |
| `FactView` | 无直接对应；schema 子集过滤应在 `SchemaIndex` 或 query/view 层实现 |
| `fact(name)` / `rel(name)` | `entity_info(index, entity_type)` / `field_predicate(index, entity_type, field_name)`（模块级函数） |
| `from_draft()` / `load_llm_schema()` | 无直接对应；最接近的是 `dsl_bridge.py: build_authoring_session_from_dsl_inputs_safe_dto()` (L102) |
| `validate_and_repair_schema(draft)` | 无直接对应；`parse_error_sections` 提供诊断，但尚无自动 repair helper |
| `Instance` | 无单一直接对应；写侧更接近 `Claim + MetaRow`，读侧更接近 `EntitySnapshot`，引用侧更接近 `EntityRef` |
| `record_id` (`keep_all`) | 无公开直接对应；最接近 `ingest_key` / `asrt_id`，但语义不同 |
| `terms` | 写协议里的 `rest_terms`，以及 SDK ingest item 里的 `value` |
| `prob` | 当前更接近断言 meta 的 `confidence`（以及 view 层 `project_display_facts()` (`core/view/projector.py` L142) 聚合后的 confidence） |
| `merge_policy` | 无直接对应；当前去重由 `Idempotency(on_conflict="skip"\|"error")` (`ledger.py` L48-50) 硬编码控制 |
| `strict meta` | 无直接对应；当前 `sdk_ingest` / `write_protocol` 采用“开放字典 + 保留键禁止 + 敏感键告警 + 标量类型约束” |
| `schema-level merge_policy` | 无直接对应；当前 `Entity.Meta` 明确只支持 `version/description/tags`（`sdk/schema.py` L229-265） |
| `Idempotency` | `core/store/ledger.py` L48-50：`on_conflict="skip"` 静默跳过 / `"error"` 抛异常 |
| `ingest_key` | `write_protocol._compute_ingest_key()` L235-287：SHA256 of `pred_id + e_ref + value + source + source_loc + trace_id + temporal` |
| `DEDUP_AFFECTING_META_KEYS` | `sdk/ingest.py` L47：`{source, source_loc, trace_id}`——这三个 meta 字段参与 ingest_key 计算 |
| `evidence_id` | 旧文期望的顶层幂等标识；当前最接近 `asrt_id`（系统生成），但语义不同 |
| `sub_ref` / `obj_ref` | 当前更接近 batch 同 tx handle，或 application 层 `EntityRef` / `EntitySelector` |
| `sub_key` / `obj_key` | 当前更接近实体 identity kwargs / `EntitySelector.identity`，不再作为关系 `terms` 的 public 语法 |
| `props`（嵌套 rel dict） | 当前更接近关系实体普通字段的逐 field 写入，不再保留单独 nested bucket |
| `LivesIn:exists` / `livesin:person` 语法糖 | `where_schema_lowering.py` 中的 compile-time sugar，不是 SDK 主写入语法 |
| `CSVProvider` | 无直接对应；当前项目无用户侧 CSV 导入；最接近的是 `sdk.ingest(data=[...])` + 用户自行 `csv.DictReader` |
| `CSVSource` | 无直接对应；列→字段映射可通过 `PredicateInfo.py_field_name` (`schema_runtime.py` L24-31) 驱动 |
| `datatype_cast` | 无直接对应；当前 `_coerce_sdk_value_to_tag()` (`sdk/store.py` L963-1009) 只做 strict 转换，缺 coerce 模式 |
| `prob_column` | 当前更接近 `confidence` meta key（`sdk/ingest.py` L41，`write_protocol.py` L26），验证 `(0,1]` |
| `ViewSpec` (当前) | `core/store/types.py` L38-50：置信度/活跃过滤器，非 schema 子集视图 |
| `derived_signature` (Rel) | 无直接对应；可从 `SchemaIndex` 的 identity_fields + field_predicates 在 projection 层派生 |
| `sub_key_fields` / `obj_key_fields` | 无直接对应；当前关系端点通过 `entity_ref` 类型字段指向 Entity，其 identity_fields 由目标 Entity 定义 |
| 位置映射（columns 顺序） | 无直接对应；当前 ingest 全部名称映射（dict with field name keys）；`core/mapping/canon.py` 的位置映射仅用于 compiled mapping predicates 内部 |
| `entity_id = H(schema_id + key_values)` | 当前 idref_v1 **不含 `schema_digest`**：`H(entity_type + identity_fields(name, type_domain, value))`（`idref_v1.py` L26-64） |
| `rel_id`（旧文提议但未采纳） | 无直接对应；当前 ingest_key 已包含 field value，同端点不同 props 天然产生不同 ingest_key |
| `include_keys` (rel 可读输出) | 无直接对应；当前 `hydrate_entity()` (`entity_view.py` L68-85) 只有 `include_assertions/include_history`，无 ref 解引用选项 |
| rel "滞后性" | 当前仍存在：`EntitySnapshot` 的 entity_ref 字段值是 opaque idref_v1 string (`facade.py` L714-717)，需额外查询才能获得端点属性 |
| `compound` / `flattened` rule policy | 无直接对应；若未来需要，更适合作为 exporter/render profile，而不是 RuleSpec v1 主字段 |
| `RuleLayer` | 当前拆成 `Rule`（SDK object）+ `RuleSpec`（core compiled form）+ `SDKRegistry/FileAuthoringRegistry`（资产管理）+ `RuleRegistry`（runtime 依赖解析） |
| `Var/Const.datatype` | 当前无用户接口；`LogicVar` / core `Var|Const` 不携带 datatype，schema-aware 类型验证仅部分实现 |
| `Mention` | 当前无 first-class SDK mixin；若手工建模，只能用普通 `Entity` + 稳定外部 identity 字段 |
| `Canonical` | 当前无 `CanonicalMixin`；仍是普通 `Entity` 建模问题 |
| `canon_of` | 当前最接近 `is_mapping=true` 且 `mapping_kind="single_valued"` 的 mapping predicate，由 `core/mapping/canon.py` 解析 |
| `canon_policy` | 当前最接近 mapping predicate 的 `tie_break` + `Store.resolve_mapping(policy_mode=...)`；无顶层 `CanonPolicyConfig` |
