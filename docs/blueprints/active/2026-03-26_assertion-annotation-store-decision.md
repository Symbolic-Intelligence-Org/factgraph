# Decision Blueprint: Assertion Annotation Store

- Status: scoped
- Type: architectural-decision (freezes data model decisions, not directly actionable)
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
- Related ADRs:
  - ADR-13 (provenance envelope) — unchanged, this blueprint does not touch provenance
  - ADR-14a (independent write paths) — unchanged
  - ADR-14c (confidence stays float) — **superseded by this blueprint**
- Related Docs:
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/store/ledger.py](../../../src/factpy_kernel/core/store/ledger.py)
  - [src/factpy_kernel/adapters/pyreason/session.py](../../../src/factpy_kernel/adapters/pyreason/session.py)
- Audit Log:
  - [2026-03-26_assertion-annotation-store-decision.audit.md](./2026-03-26_assertion-annotation-store-decision.audit.md)

## 1. Purpose

本蓝图是架构决策记录，冻结 **Assertion Annotation Store** 的数据模型和语义边界。它不包含实施计划——实施由后续子蓝图承载。

**触发原因**：PyReason 引擎接入过程中暴露了 `meta` 层的语义缺陷。`confidence`、`source`、`bound`、`active_from` 等概念混在同一个扁平 `meta dict` 里，既有来源信息，又有引擎真值语义，又有派生摘要。两个真实引擎样本（Souffle + PyReason）已验证此缺陷不是理论问题，而是导致了具体的信息损失（`bound=[0.6, 0.9] → confidence=0.6`）和语义含混。

**本蓝图冻结的不是**"怎么改代码"，而是 6 条架构判断。

## 2. Problem

### 2.1 当前 `meta` 的语义混乱

当前 `MetaRow` 表承载了至少 4 种不同概念：

| 概念 | 例子 | 本质 |
|------|------|------|
| 来源信息 | `source="ESA handbook"`, `analyst="reviewer_A"` | 关于这条事实的观测性描述 |
| 引擎真值语义 | `bound=[0.6, 0.9]`, `probability=0.3` | 事实在特定数学框架下的真值表示 |
| 派生摘要 | `confidence=0.6` | 面向 consumer 的统一排序/过滤维度 |
| 操作状态 | `truncated=true`, `export_failed=true` | 运行时标记 |

这 4 种概念混在同一个 key-value 空间里，导致：

1. **语义损失**：PyReason 的 `bound=[0.6, 0.9]` 被压成 `confidence=0.6`，丢失上界和区间语义
2. **概念冲突**：`confidence` 既被当作"可信度"（来源属性），又被当作"真值"（引擎语义），又被当作"排序分"（consumer 需要）
3. **consumer 无法分层读取**：UI 想读摘要、审计想读来源、专业用户想读原始语义——但它们全在同一个 dict 里，无法区分

### 2.2 当前 ADR-14c 的局限

ADR-14c 冻结了"confidence stays float, engine-specific params never enter shared meta"。这条决策的精神是正确的（共享层不因新引擎膨胀），但手段有问题：

- 它把引擎原生值（bound, probability）完全排斥在持久化之外
- 导致跨引擎消费时只能看到有损的 `confidence` 摘要
- 审计链无法追溯"这个 0.6 是怎么来的"

## 3. Decisions to Freeze

### Decision 1: 四层数据架构

将当前三层架构（Fact Store / Provenance Store / Evidence Tree View）扩展为四层：

```
┌──────────────────┐
│  Claim Store      │  事实本身：pred_id + args
│  (INPUT)          │  回答："什么事实"
└────────┬─────────┘
         │
┌────────┴─────────┐  ┌──────────────────────┐
│  Annotation Store │  │  Provenance Store     │
│  (METADATA)       │  │  (OUTPUT)             │
│                   │  │                       │
│  回答：           │  │  回答：               │
│  "关于这条事实的  │  │  "这个结论怎么        │
│   所有附加语义"   │  │   推出来的"           │
│                   │  │                       │
│  source / semantic│  │  proof tree /         │
│  derived / oper.  │  │  event log /          │
│                   │  │  prob. decomposition  │
└────────┬─────────┘  └──────────┬────────────┘
         │                       │
         │    READ               │    READ
         └──────────┐  ┌────────┘
                    ▼  ▼
           ┌─────────────────┐
           │  Evidence /      │
           │  Audit View      │
           │  (READ-ONLY)     │
           │                  │
           │  按 consumer     │
           │  需要投影        │
           └──────────────────┘
```

**与三层架构的关系**：Annotation Store 从原 Fact Store 的 `meta` 中分离出来。Claim Store + Annotation Store 合起来等于原来的 Fact Store，但语义更清晰。

### Decision 2: `confidence` 是 derived summary，不是统一真值语义

**冻结判断**：`confidence` 正式降级为面向 consumer 的派生摘要。

- 它的存在是为了给排序、过滤、badge、landing page 提供统一维度
- 它不代表任何引擎的原生真值语义
- 它的计算方式由 `confidence_source` 字段自文档化

```
annotation: shared / derived / confidence = 0.6
annotation: shared / derived / confidence_source = "pyreason:lower_bound"
```

consumer 分层读取：
- **简单 UI**：读 `shared/derived/confidence`，用于排序和 badge
- **审计页**：读 `shared/source/*` + 引擎 `semantic/*`
- **专业 consumer**：读完整 annotation，包含引擎原始值

**此决策 supersedes ADR-14c 中"confidence stays float"的表述。** `confidence` 仍然是 float，但其语义从"通用真值"降级为"派生摘要"。

### Decision 3: 引擎对事实真值的解释属于 semantic annotation，不属于 claim

**冻结判断**：Claim 只持有"什么事实"（`pred_id + args`），不持有"在什么数学框架下成立"。

引擎对事实的真值解释（bound / probability / boolean truth）归属于 Annotation Store 的 `semantic` 类别：

| 引擎 | Annotation | namespace / category |
|------|-----------|---------------------|
| PyReason | `bound_lower=0.6` | `pyreason / semantic` |
| PyReason | `bound_upper=0.9` | `pyreason / semantic` |
| PyReason | `active_from=3` | `pyreason / semantic` |
| PyReason | `active_to=5` | `pyreason / semantic` |
| ProbLog | `probability=0.3` | `problog / semantic` |
| Souffle | `truth=true` | `souffle / semantic` |

**注意**：一个引擎可能有多个不同作用域的原生语义词条。框架不假设"每个引擎只有一个特殊值"。

### Decision 4: 引擎原生词条的作用域分类

一个引擎的原生概念不全属于 assertion annotation。必须按作用域分类：

| 作用域 | 例子 | 存储位置 |
|--------|------|---------|
| **Assertion-level** | `pyreason:bound_lower/upper`, `problog:probability` | Annotation Store |
| **Run-level** | `pyreason:timesteps=5`, `souffle:explain_depth=4` | Run manifest / audit package metadata |
| **Rule-level** | `pyreason:delay=1`, `problog:annotated_disjunction=true` | Rule definition / compile artifact |
| **Provenance-level** | `truncated=true`, `trace_type=event_log` | Provenance envelope / provenance status |

**初版 Annotation Store 只覆盖 assertion-level。** Run/rule/provenance-level 继续留在各自已有载体中。

### Decision 5: 引擎特有语义的载体分工

不同类型的引擎特有语义使用不同的载体机制，不混用：

| 语义类型 | 载体 | 理由 |
|---------|------|------|
| **Assertion engine-specific semantics** | Annotation Store (`AnnotationRow`) | 运行时数据，审计面 / UI / 其他引擎消费 |
| **Rule engine-specific semantics** | Typed rule extension (`engine_ext`) | 编译时定义，只有编译器消费 |
| **Run engine-specific config** | Evaluate dispatch (`engine_options`) | 执行时配置，只影响单次 run |

**规则层不沿用 annotation 机制。** ADR-14d 已冻结的 engine-specific Rule subclass 方向是正确的，但实现形态收窄为 **typed extension payload**：

```python
# 正确：Layer 1/2 物理分离
Rule(
    id="popular_spread",
    where=[Pred("popular", y), Pred("friends", x, y)],
    engine_ext=PyReasonRuleExt(        # ← Layer 2，隔离在 ext 对象里
        timestep_delay=1,
        bound_threshold=[0.5, 1.0],
    ),
)

# 不做：Layer 1/2 混在同一类型
PyReasonRule(                          # ← 完整子类，blast radius 大
    id="popular_spread",
    where=[...],
    timestep_delay=1,
)
```

**`engine_ext` 的有无是规则对引擎扩展依赖的信号**：无 `engine_ext` 表示规则不依赖特定引擎扩展，具备跨引擎消费资格；但是否可运行仍取决于目标引擎的 capability gate 和 adapter 实现范围。有 `engine_ext` 的 Rule 被钉死在特定引擎。

`engine_ext` 初期适用于 `Rule` 与 `Derivation`。`Query` 默认不分裂，引擎特定执行配置走 `engine_options`（ADR-14e）。

### Decision 6: Rule 参数的 definition-time / run-time 分离

规则参数必须严格区分"规则定义的一部分"和"执行配置"：

| 分类 | 归属 | 例子 | 存储位置 |
|------|------|------|---------|
| **Definition-time** | Rule extension (`engine_ext`) | `timestep_delay`, `bound_threshold`, `probability`, `annotated_disjunction` | Rule 对象本身 |
| **Run-time** | Evaluate dispatch (`engine_options`) | `timesteps=5`, `convergence`, `explain_depth` | evaluate() 调用参数 |

**两者不能混。** Definition-time 参数影响编译产物（不同的 `timestep_delay` 生成不同的目标代码）；run-time 参数只影响单次执行行为（不同的 `timesteps` 不改变规则定义）。

```python
# 正确
Rule(..., engine_ext=PyReasonRuleExt(timestep_delay=1))  # definition-time
store.evaluate(..., engine_options={"timesteps": 5})      # run-time

# 错误：把 run-time 混进 rule definition
Rule(..., engine_ext=PyReasonRuleExt(timestep_delay=1, timesteps=5))
```

## 4. Annotation Data Model

### 4.1 AnnotationRow

```python
@dataclass
class AnnotationRow:
    asrt_id: str            # 关联的 assertion ID（初版唯一 subject type）
    namespace: str          # shared | pyreason | problog | souffle
    category: str           # source | semantic | derived | operational
    key: str                # 字段名
    kind: str               # str | int | float | bool | time | json
    value: Any              # 标量值
    origin: str             # observed | derived
    derivation: str | None  # 派生说明（origin=derived 时必填）
```

### 4.2 kind 类型系统

复用现有 `MetaRow.kind`，不引入新类型系统：

- `str`, `int`, `float`, `bool`, `time`, `json`

**约束**：
1. `kind` 只是存储类型，不是语义类型。语义由 `namespace + category + key + origin` 决定
2. 区间不新增 `interval` kind，拆成两条标量 annotation：`bound_lower` + `bound_upper`
3. `json` 只作兜底，核心语义优先拆为可查询的标量
4. 初版只支持 assertion subject，围绕 `asrt_id` 设计即可

### 4.3 category 枚举及语义

| category | 语义 | 例子 |
|----------|------|------|
| `source` | 事实的来源信息 | `source`, `analyst`, `method`, `timestamp` |
| `semantic` | 引擎对事实真值的解释 | `bound_lower`, `probability`, `truth` |
| `derived` | 框架计算的派生摘要 | `confidence`, `confidence_source`, `ranking_score` |
| `operational` | 运行时状态标记 | `truncated`, `export_failed` |

### 4.4 namespace 枚举

- `shared`：所有引擎通用的 annotation（source, derived, operational）
- `pyreason`：PyReason 引擎特有
- `problog`：ProbLog 引擎特有
- `souffle`：Souffle 引擎特有

**扩展规则**：新增引擎只新增 namespace，不改 shared namespace 的 schema。

## 5. 与现有系统的关系

### 5.1 `meta_rows` 表

保留为 legacy compatibility layer。

- 不删除，不迁移现有数据
- 旧 consumer（certainty v1、现有 audit pipeline、static HTML）继续读 `meta_rows`
- 新的真值语义只写 Annotation Store
- 当 consumer 逐步切换到读 annotation 后，`meta_rows` 自然退化

### 5.2 与 Provenance Store 的边界

- Provenance 回答"怎么推出来的"→ 不变，不混进 annotation
- Annotation 回答"这条 assertion 附带什么语义"→ 不侵入 provenance
- `ProvenanceEnvelope`（ADR-13）完全不受影响

### 5.3 与 ADR-14c 的关系

本决策 supersedes ADR-14c 的具体措施，但保留其精神：

| ADR-14c 原文 | 本决策 |
|-------------|--------|
| "confidence stays float" | 保留。confidence 仍是 float，但语义降级为 derived summary |
| "engine-specific params never enter shared meta" | **修订**。引擎原生值进入 Annotation Store（独立于 meta_rows），但在命名空间下隔离，不污染 shared namespace |

### 5.4 物理存储

直接在现有 Ledger SQLite 中新增 `annotation_rows` 表。不新建数据库，不做 `namespaced MetaRow` 过渡层。

```sql
CREATE TABLE annotation_rows (
    asrt_id    TEXT NOT NULL,
    namespace  TEXT NOT NULL,
    category   TEXT NOT NULL,
    key        TEXT NOT NULL,
    kind       TEXT NOT NULL,
    value      TEXT,            -- JSON-serialized scalar
    origin     TEXT NOT NULL,   -- 'observed' | 'derived'
    derivation TEXT,            -- nullable
    UNIQUE(asrt_id, namespace, category, key)
);

-- 查询索引
CREATE INDEX idx_anno_asrt ON annotation_rows(asrt_id);
CREATE INDEX idx_anno_ns_cat ON annotation_rows(namespace, category);
CREATE INDEX idx_anno_key ON annotation_rows(key);
```

## 6. Boundaries and Invariants

### 必须保持的边界

- Annotation Store 不替代 Provenance Store（推理过程 ≠ 事实语义）
- Annotation Store 初版只支持 assertion subject（不做 candidate / provenance_entry annotation）
- `meta_rows` 保留为 legacy layer，不在本轮删除或迁移
- Certainty v1 的 16 条冻结 contract 不受影响（它继续读 meta_rows 的 confidence）
- 新引擎接入只增加 namespace，不改 shared schema

### 明确不做的内容

- 不做"引擎到引擎"的通用值映射表（如 `pyreason → problog`）
- 不做 candidate-level 或 provenance-level annotation（初版）
- 不做 annotation 的版本化或时序追踪（初版）
- 不一次性重写所有 consumer

### 兼容性约束

- 旧 surface 需要的 `confidence/source/...` 由 annotation 向 `meta_rows` 投影
- 新增的 `annotation_rows` 表与 `meta_rows` 共存，不互相依赖
- `AnnotationRow.kind` 与 `MetaRow.kind` 使用相同类型系统

## 7. Acceptance

本蓝图的验收标准是**决策被引用且不产生矛盾**：

- [ ] ADR v2 的 §5.2.1 已更新引用本决策
- [ ] `confidence` 的语义降级已在 ADR v2 §12 Frozen Decisions 中记录
- [ ] 至少一个实施蓝图已创建并引用本决策
- [ ] 实施蓝图中的 AnnotationRow schema 与本决策一致

## 8. Implementation Guidance (non-binding)

本节不是实施计划，仅为后续实施蓝图提供方向建议。

### 建议的实施顺序

1. Ledger 新增 `annotation_rows` 表 + `AnnotationRow` dataclass
2. `PyReasonSession` 改写：写 semantic annotation（bound_lower/upper, active_from/to）+ derived annotation（confidence, confidence_source）
3. Audit export 新增 `assertion_annotations.jsonl`
4. 旧 consumer 保持不变（继续读 meta_rows）
5. 后续 consumer 切换到读 annotation

### 建议的 confidence 派生规则（初版默认）

| 来源引擎 | 默认映射 | confidence_source |
|---------|---------|------------------|
| PyReason | `lower_bound` | `"pyreason:lower_bound"` |
| ProbLog | `probability` | `"problog:probability"` |
| Souffle | `1.0`（事实存在即为真） | `"souffle:boolean_truth"` |

用户可在后续迭代中自定义映射规则。

## 9. Docs to Update

- ADR v2 (`2026-03-22_architectural-decisions-v2.md`): §3 四层架构、§5.2.1 confidence 语义、§12 Frozen Decisions
- `memory/current.md`: 反映四层架构变更

## 10. Outcome / Deviations

决策冻结后填写：

- 最终冻结结果：
- 与 draft 不同的地方：
- 为什么会有这些调整：
