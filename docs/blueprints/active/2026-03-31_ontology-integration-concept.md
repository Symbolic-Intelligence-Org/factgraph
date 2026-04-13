# ontology-integration-concept

- Status: draft
- Type: concept (探索阶段，约束后续子蓝图方向，本身不直接产出代码)
- Created: 2026-03-31
- Parent: (none; top-level)
- Depends On:
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) (产品定位与四层数据架构)
- Prior Art:
  - [2026-03-31_ontology-feasibility-analysis.md](./2026-03-31_ontology-feasibility-analysis.md) (代码调研结论)
- Audit Log:
  - [2026-03-31_ontology-integration-concept.audit.md](./2026-03-31_ontology-integration-concept.audit.md)

---

## 1. Problem

团队希望在现有框架内引入**本体论风格的建模能力**（类层次、属性约束、实例分类推理），用于组织和表达具体的业务逻辑。可行性调研（见 Prior Art）已确认现有架构可间接支持。

需要明确的是：本蓝图的方向是**在现有 Datalog/ProbLog/PyReason 引擎之上增加 ontology-flavored features**，而不是引入独立的本体推理引擎。OWL reasoner 适配器是一条完全不同的产品路线，不在本蓝图范围内。

## 2. Goals

- 在现有 SDK / schema_ir / 规则引擎之上，增加 **ontology-flavored 建模与推理能力**
- 定义这些能力与现有四层架构（Claim / Annotation / Provenance / View）的**交互边界**
- 提出**分阶段路线图**，每阶段有明确的输入/输出和验证标准
- 识别需要子蓝图解决的**关键设计决策**

## 3. Non-Goals

- **不引入 OWL reasoner 或独立本体推理引擎** — 那是另一条产品路线
- 不实现任何代码（本蓝图是概念对齐）
- 不引入外部依赖（rdflib、owlready2 等）
- 不改变现有 core 语义、authoring 协议或 service API 的契约
- 不追求 OWL DL/Full 的完整覆盖 — 目标是实用的 ontology-flavored 子集

## 4. Current Context

### 4.1 现有架构中的"准本体"基础设施

经过代码调研（两份独立报告交叉验证，173 个单元测试通过），项目已具备以下可复用结构：

**Entity/Relationship 声明 = 轻量级 TBox**

SDK 层的 Entity/Relationship 声明本质上是一个轻量级 TBox（术语层），定义了类和关系的结构：

```python
class User(Entity):
    class Meta:
        entity_type = "user"
    user_id: Identity[str]
    name: Field[str]

class LivesIn(Relationship):
    from_entity: User
    to_entity: Country
    strength: Field[float]
```

编译后每个 Entity 自动生成谓词：`{type}:exists`（存在性）、`{type}:{field}`（属性访问）。Relationship 生成 `(from_ref, to_ref, ...field_args)` 谓词，类似 RDF triple 的 `(subject, predicate, object)` 模式。

关键入口：`schema_compile.py`、`schema_ir.py`。

**Predicate 系统 = 结构化事实空间**

- 每个谓词有明确的 `arg_specs`（参数名 + 类型域）
- `cardinality: single | multi` 已有函数属性的约束基础
- `is_mapping`、`group_key_indexes` 提供额外的结构信息
- 类型域（canonical tags）：`entity_ref, string, int, float64, bool, bytes, time, uuid`

**多引擎推理 = ontology 规则的执行基础**

- Souffle: Datalog 前向链，天然支持**传递闭包**和**递归**，是类层次推理的理想引擎
- ProbLog: 概率逻辑，可处理不确定性场景下的本体风格推理
- PyReason: 区间传播 + 时间推理，可承载时序本体
- 引擎注册机制 (`register_engine_evaluator`) 已验证可扩展性（三个 adapter 已落地）

**ECSS 领域预设 = 可参照的扩展模式**

`src/factpy_kernel/domains/ecss/` 已有领域特定 schema 扩展：`extend_schema_ir_with_ecss_vcd_predicates()` 向 schema_ir 注入领域谓词。ontology features 可参照此模式。

### 4.2 现有能力 vs 本体论需求的精确对照

| 能力 | 现有实现 | 缺口 | 扩展难度 |
|------|---------|------|---------|
| 类定义 | `Entity` (SDK) → `schema_ir.entities` | 无继承/subClassOf | 低 — schema_ir 扩展字段 |
| 关系定义 | `Relationship` (SDK) → schema_ir predicates | 无属性特征（传递/对称/逆） | 低 — 元数据标注 |
| 实例断言 | `set_field` / `add_field` → Claim Store | 无 instance_of 推理 | 低 — 自动规则生成 |
| 函数属性 | `cardinality: single` | 已有 | 无需新增 |
| 类型约束 | canonical tags | 值类型，非语义类型；无 domain/range | 中 — 编译时校验 |
| 层次推理 | Souffle 传递闭包原生支持 | 无自动生成的层次规则 | 低 — 规则模板 |
| 属性链推理 | Souffle 递归规则支持 | 无声明式语法 | 中 — 新增 SDK 语法 |
| 概率本体 | ProbLog / PyReason | 可承载 | 低 — 现有能力 |

### 4.3 架构约束（继承自 architectural-decisions-v2）

1. **factpy 是 auditable reasoning framework，不是 reasoning engine** — 引擎可替换，审计层不可替换
2. **四层数据架构不可破坏**（Claim / Annotation / Provenance / View）
3. **引擎是可替换的计算后端**，框架是产品层
4. **Provenance 来自引擎，不在外部重建**
5. **新引擎应复用统一 schema、annotation 与 audit 出口**

### 4.4 关键技术事实

**core 的本质特征**（来自代码调研）：
- 强类型、append-only、closed-world 风格的事实/规则内核（`schema_ir.py`、`where_eval.py`、`idref_v1.py`）
- native 规则语义有明显的 Datalog/operational reasoning 特征：`not` 是 negation-as-failure（`where_eval.py`）
- 不是本体语义内核，也不应该变成本体语义内核

**authoring 的角色**：
- 已经负责 schema/rule/derivation 的编译和 registry 发布（`schema_compile.py`、`rule_compile.py`、`derivation_compile.py`）
- 天然适合作为 ontology feature 编译的落点
- `service` 和 `application` 已经能消费编译后的 schema/rule/derivation，所以 ontology features 编译成现有资产后，运行面直接复用

**Souffle 对层次推理的天然支持**：
```datalog
% 传递闭包 — Souffle 原生高效
subclass_of(X, Z) :- subclass_of(X, Y), subclass_of(Y, Z).

% 实例类型传播
instance_of(I, C) :- direct_instance(I, C).
instance_of(I, C) :- instance_of(I, C2), subclass_of(C2, C).

% 属性继承（子类实例继承父类属性约束）
has_property(I, P) :- instance_of(I, C), class_property(C, P).
```

### 4.5 已识别的缺口清单

来自两份独立调研报告的交叉确认：

| 缺口 | 说明 | 解决方式 |
|------|------|---------|
| 无 TBox/ABox 分层 | 没有 `subClassOf`、`inverseOf`、transitive/functionality 等本体 carrier | SDK + schema_ir 扩展 |
| 无类层次谓词 | 缺少 `subclass_of`、`instance_of` 等系统谓词 | schema_compile 自动生成 |
| 无属性特征标注 | Relationship/Field 缺少 transitive/symmetric/inverse 元数据 | SDK 声明扩展 |
| 无自动推理规则 | 需手写传递闭包/对称等规则 | rule_compile 自动生成模板 |
| 无 domain/range 校验 | 谓词参数类型是 canonical tag，无语义 domain/range | 编译时校验 |

### 4.6 "ontology-flavored features" vs "OWL reasoner" — 路线分析

本蓝图经过讨论后明确区分两条根本不同的路线：

**路线 A：ontology-flavored features（本蓝图）**
- 定位：现有引擎上的建模语法糖
- 方式：SDK 声明 → authoring 编译 → 现有引擎执行
- 语义：CWA（与现有一致）
- 依赖：无新增
- 能力范围：类层次 + 属性特征 + 实例分类 ≈ OWL Lite 实用子集
- 审计链：完全复用

**路线 B：OWL reasoner 适配器（独立产品方向，不在本蓝图范围）**
- 定位：新增推理引擎（与 Souffle/ProbLog/PyReason 同级）
- 方式：OWL 文件 → 外部 reasoner (HermiT/ELK/RDFox) → candidate pipeline
- 语义：OWA（与现有 CWA 根本不同）
- 依赖：外部 OWL reasoner + justification → SupportArtifact converter
- 能力范围：OWL DL（OWL Full 不可判定，任何 reasoner 都不完整支持）
- 审计链：需要 justification graph converter

**为什么是两条产品路线而非一条的两个阶段**：factpy 是框架层，不是推理层。它不"实现"Datalog（Souffle 实现），也不应该"实现"OWL（应由 HermiT/ELK 实现）。路线 A 是在现有引擎能力范围内增加建模便利；路线 B 是接入全新的推理范式。两者的用户、场景、技术栈完全不同。

## 5. Proposed Shape

### 5.1 架构定位：现有引擎上的 ontology-flavored 扩展

不新增引擎，不新增编译器。在现有三层（SDK → authoring → runtime）上自然扩展：

```
SDK 层（扩展）
  Entity 新增：parent_entity_type（类继承）
  Relationship / Field 新增：属性特征标注（transitive / symmetric / inverse）

    ↓  现有 schema_compile + rule_compile

authoring 层（扩展）
  schema_compile 自动生成 ontology 辅助谓词（subclass_of / instance_of）
  rule_compile 自动生成属性推理规则模板（传递闭包 / 对称 / 逆）

    ↓  现有 authoring pipeline

Runtime / Service / Audit（不改）
  Souffle / ProbLog / PyReason 执行生成的规则
  推理结果纳入现有 evidence tree
```

**核心思路**：不引入新概念层。ontology features 是 SDK 声明的语法糖，编译后变成现有架构已能消费的 schema_ir + Rule。

### 5.2 具体扩展点（概念级）

#### 5.2.1 类继承 (subClassOf)

**SDK 声明**：
```python
class Satellite(Entity):
    class Meta:
        entity_type = "satellite"
    norad_id: Identity[str]
    name: Field[str]

class DebrisSatellite(Entity):
    class Meta:
        entity_type = "debris_satellite"
        parent_entity_type = "satellite"  # ← 新增
    debris_class: Field[str]
```

**schema_ir 扩展**：
```json
{
  "entity_type": "debris_satellite",
  "parent_entity_type": "satellite",
  "identity_fields": [...]
}
```

**编译产物**（schema_compile 自动生成）：
- 辅助谓词 `ontology:subclass_of(child_type, parent_type)` — 事实注入
- 辅助谓词 `ontology:instance_of(entity_ref, class_type)` — 实例分类
- Souffle 规则：传递闭包 + 实例类型传播

#### 5.2.2 属性特征

**SDK 声明**：
```python
class PartOf(Relationship):
    class Meta:
        transitive = True        # ← 新增
    from_entity: Component
    to_entity: Assembly

class NearTo(Relationship):
    class Meta:
        symmetric = True         # ← 新增
    from_entity: Satellite
    to_entity: Satellite

class ContainedBy(Relationship):
    class Meta:
        inverse_of = "Contains"  # ← 新增
    from_entity: Part
    to_entity: Container
```

**编译产物**（rule_compile 自动生成）：
- transitive → `part_of(X,Z) :- part_of(X,Y), part_of(Y,Z).`
- symmetric → `near_to(Y,X) :- near_to(X,Y).`
- inverse_of → `contained_by(Y,X) :- contains(X,Y).`

#### 5.2.3 Domain / Range 约束

**处理方式**：
- 编译时：`schema_compile` 校验 Relationship 的 `from_entity` / `to_entity` 类型与 domain/range 一致
- 运行时（可选）：写入 Annotation，标注违反 domain/range 的事实

#### 5.2.4 完整扩展点汇总

| Ontology Feature | 扩展位置 | 编译产物 | 执行引擎 |
|------------------|---------|---------|---------|
| 类继承 (subClassOf) | SDK `Entity.Meta` + `schema_compile` | 辅助谓词 + 传递闭包规则 | Souffle |
| 实例分类 (instance_of) | `schema_compile` | 分类谓词 + 类型传播规则 | Souffle |
| 传递属性 (transitive) | SDK `Relationship.Meta` + `rule_compile` | `rel(X,Z) :- rel(X,Y), rel(Y,Z).` | Souffle |
| 对称属性 (symmetric) | SDK `Relationship.Meta` + `rule_compile` | `rel(Y,X) :- rel(X,Y).` | Souffle |
| 逆属性 (inverse) | SDK `Relationship.Meta` + `rule_compile` | `rel_inv(Y,X) :- rel(X,Y).` | Souffle |
| 函数属性 (functional) | 已有 `cardinality: single` | 不需要新增 | 已有 |
| 属性链 (property chain) | SDK + `rule_compile` | 组合规则 | Souffle |
| domain / range | `schema_compile` 校验 | 编译时报错 / 运行时 Annotation | N/A |

### 5.3 与现有审计链的集成

自动生成的 ontology 规则在 runtime 中与手写规则无差别：

```
ontology 规则执行
  → CandidateSet（标准产出）
  → SupportArtifact（标准 proof）
  → evidence tree（标准可视化）
  → explain_narrative / explain_nl（标准 NL 解释）
```

不需要任何 audit pipeline 改动。这是本方案的核心优势：**ontology features 是 authoring 层的语法糖，runtime 层完全无感知**。

### 5.4 明确排除的路线

| 路线 | 排除理由 |
|------|---------|
| **引入 OWL reasoner 适配器** | 完全不同的产品方向（OWA 语义、外部依赖、justification 转换）。如果未来有需求，应作为独立蓝图立项，不在本概念范围内 |
| **改造 core 为本体运行时** | `core` 是强类型 CWA 事实/规则内核。改造会冲击 store、view、accept、audit 全部契约，违反"引擎可替换、框架不可替换"的产品定位 |
| **新增独立的 ontology 编译器模块** | 过度工程化。SDK + authoring 扩展足够承载目标子集，不需要独立模块 |

## 6. Boundaries And Invariants

### 6.1 必须保持的边界

- 四层数据架构（Claim / Annotation / Provenance / View）不可打破
- core 语义保持 CWA + negation-as-failure，不注入 OWA 语义
- 本体编译产物必须通过现有 authoring pipeline 验证，不走特殊通道
- 所有本体推理结果必须纳入现有 audit pipeline（SupportArtifact → evidence tree）

### 6.2 设计约束

- ontology features 是 SDK/authoring 的扩展，不引入新的概念层或资产类型
- 自动生成的规则必须与手写规则在 runtime 中无差别（同一个 Rule pipeline）
- 所有推理结果经过现有 audit pipeline，不走特殊通道
- 扩展模式参照 ECSS domain preset（`extend_schema_ir_with_ecss_vcd_predicates` 模式）

### 6.3 语义说明

本框架在 CWA（Closed World Assumption）下运行。ontology-flavored features 采用相同语义：
- `not` 是 negation-as-failure，非经典否定
- 类层次推理是确定性的传递闭包，不是 OWA 下的开放推理
- 没有"未知"状态 — 实例要么属于某个类，要么不属于
- 文档需明确标注这一语义差异，避免与经典本体论混淆

### 6.4 能力边界 — 本方案能做什么，不能做什么

**能做的**（现有引擎可表达）：

| 能力 | 机制 |
|------|------|
| subClassOf 层次 + 传递闭包 | Souffle 递归规则 |
| instance_of 推理（实例属于哪些类） | Souffle 传递闭包 |
| 传递/对称/逆属性推理 | Souffle 自动规则 |
| 属性链推理 (hasFather ∘ hasBrother → hasUncle) | Souffle 组合规则 |
| functional 约束 | 现有 cardinality: single |
| domain/range 校验 | 编译时 + Annotation |
| 概率性类成员关系 | ProbLog 概率事实 |
| 时序性本体演化 | PyReason 时间步 |

**不能做的**（需要 OWL reasoner，属于独立产品方向）：

| 能力 | 原因 |
|------|------|
| 类表达式 (A ⊓ B, A ⊔ B, ¬A) | 无类表达式构造 |
| 存在/全称量化限制 (∃R.C, ∀R.C) | 超出 Datalog 表达力 |
| 精确 cardinality (≥n, ≤n, =n) | 只有 single/multi |
| equivalentClass / sameAs | 无等价推理 |
| disjointWith | CWA 下无意义（没声明的类默认不相交） |
| consistency checking | 需要 tableaux 算法 |
| 元类（class 同时是 instance） | entity/predicate 严格分离 |
| Open World 推理 | CWA 是基础假设 |

## 7. Phased Roadmap

### Phase 0 — 概念对齐（当前）

- 输出：本蓝图
- 验证标准：团队就架构定位和 ontology-flavored features 范围达成共识

### Phase 1 — schema 层类层次（子蓝图 TBD）

- 目标：`schema_ir` 支持 `parent_entity_type`，自动生成 `subclass_of` / `instance_of` 谓词
- 输入：Entity SDK 声明中新增 `Meta.parent_entity_type`
- 输出：
  - schema_ir 扩展 `parent_entity_type` 字段
  - schema_compile 自动注入 `ontology:subclass_of` / `ontology:instance_of` 谓词
  - Souffle 传递闭包 + 实例类型传播规则模板
- 验证：Souffle 引擎可执行 `instance_of` 查询并产出可审计 evidence tree
- 预估范围：schema_ir 扩展 + schema_compile + 规则模板 + 测试
- 改动侵入性：**低** — 主要在 schema 和 authoring 层，core store 无需变动
- 建议验证场景：ECSS 领域本体（已有 domain preset，天然适合）

### Phase 2 — 属性约束与推理规则（子蓝图 TBD）

- 目标：Property 元数据（transitive / symmetric / inverse / domain / range）
- 输入：Relationship / Field SDK 声明中新增 `Meta.transitive` / `Meta.symmetric` / `Meta.inverse_of`
- 输出：
  - rule_compile 自动生成对应 Souffle 规则
  - schema_compile 增加 domain/range 编译时校验
  - 违规事实可选写入 Annotation
- 验证：属性推理结果可审计，cardinality / domain 违规可检测
- 前置依赖：Phase 1
- 改动侵入性：**中** — 需要新增属性元数据定义、扩展 schema_ir、添加推理规则模板

## 8. Open Questions

| ID | 问题 | 影响范围 | 当前倾向 |
|----|------|---------|---------|
| Q1 | `subClassOf` 在 schema_ir 中的表示：`parent_entity_type` 单继承 vs `parents` 多继承？ | Phase 1 | 单继承起步，多继承延后 |
| Q2 | 自动生成的推理规则是编译时静态生成，还是运行时按需展开？ | Phase 1-2 | 编译时静态生成（确定性 + 可审计） |
| Q3 | 是否需要 ECSS 领域本体作为 Phase 1 的验证场景？ | Phase 1 | 是（ECSS 已有 domain preset，天然适合） |
| Q4 | 属性约束违规是编译时报错还是运行时 annotation？ | Phase 2 | 编译时报错 + 运行时 annotation 双保险 |
| Q5 | ontology 辅助谓词的命名空间：`ontology:subclass_of` 还是直接 `subclass_of`？ | Phase 1 | `ontology:` 前缀，避免与用户谓词冲突 |
| Q6 | 自动生成的规则是否需要在 evidence tree 中标注为 "auto-generated from ontology declaration"？ | Phase 1 | 是，通过 Annotation 标注来源 |

## 9. Acceptance Criteria

- [ ] AC1: 团队就 ontology-flavored features 的范围达成共识
- [ ] AC2: Open Questions Q1-Q6 有明确决策或延后理由
- [ ] AC3: Phase 1 子蓝图已拆出并进入 draft 状态
- [ ] AC4: 本蓝图不与 architectural-decisions-v2 的任何决策冲突

## 10. Outcome / Deviations

概念对齐完成后填写：

- 团队决策结论：
- 与本蓝图不同的地方：
- Phase 1 子蓝图链接：
- 归档说明：
