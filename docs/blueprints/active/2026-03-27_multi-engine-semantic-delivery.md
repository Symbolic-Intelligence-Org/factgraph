# Mother Blueprint: Multi-Engine Semantic Delivery

- Status: scoped
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Supersedes: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md) (implemented)
- Related ADR: [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
- Related Decisions:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md) (6 decisions)
  - [2026-03-27_multi-engine-execution-surface-decision.md](./2026-03-27_multi-engine-execution-surface-decision.md) (9 decisions)
- Audit Log:
  - [2026-03-27_multi-engine-semantic-delivery.audit.md](./2026-03-27_multi-engine-semantic-delivery.audit.md)

## §1. Narrative

**无论底层推理引擎是什么，框架都能接纳它，并统一管理 schema、事实元数据与审计交付。**

同一套 schema 定义可以被不同引擎各自消费，用户不需要为换引擎重写 schema。审计与交付面提供统一出口，但按引擎 provenance 原生形态分派渲染。引擎特有能力（时间步、区间值、概率语义）由各自 adapter 负责，用户在需要这些能力时显式进入对应引擎面。

**一句话版**：统一的是 schema 边界与审计出口；不统一的是写入路径与引擎内部语义。

### 关于事实语义属性的澄清

`probability`、`bound`、`active_from` 等值不是"引擎的运行参数"——它们是**事实本身的语义属性**。一条断言以 `probability=0.3` 成立，概率是这条事实的性质，不是 ProbLog 的配置项。`bound=[0.6, 0.9]` 是断言的模糊隶属度区间，不是 PyReason 的内部状态。

框架对此的分层处理是：
- **事实语义属性**（probability, bound, active_from）→ `Annotation Store`（`{engine}/semantic/*`）
- **规则语义扩展**（timestep_delay, bound_threshold）→ `engine_ext`
- **运行时执行配置**（timesteps, convergence）→ run config（执行层）

Namespace 中的引擎名（`pyreason/semantic/bound_lower`）记录的是**谁计算了这个值**，不是"这个值只属于这个引擎"。`category=semantic` 标记了它是事实语义，框架在消费和交付时应以事实语义的地位对待它，不应因计算来源不同而降级。

**本阶段的核心转变**：

从"多引擎可以跑"进入"多引擎语义被 framework 正式消费和交付"。

前一阶段（旧母蓝图）回答的问题是：
- Souffle provenance 能不能消费？→ 能
- ECSS 规则能不能表达？→ 能
- PyReason 能不能接入？→ 能（完整 execution surface）

本阶段要回答的问题是：
- 引擎产出的语义（annotation、provenance、derived facts）能不能被框架正式消费和交付？
- 审计面、静态交付、UI 能不能无差别地展示多引擎结果？
- 框架的通用性是否经得起第三个引擎的验证？

## §2. Current Baseline

### 已落地能力

| Subsystem | Status | Frozen Contracts |
|-----------|--------|-----------------|
| Certainty v1 | FROZEN | #1-#16 |
| Souffle Provenance | complete | — |
| Provenance Coverage + Bridge | complete | — |
| Assertion Annotation Store | complete | #28-#37 |
| PyReason Adapter (full vertical slice) | complete | #38-#42 |
| Multi-Engine Execution Surface | complete | #43-#51 |

**467 tests 全绿。101 条归档蓝图（非 audit）。51 条冻结契约。**

### PyReason 当前可用路径

```
Schema → Session (batch API) → Runner (typed rules)
  → Evaluate (Store.evaluate(mode="pyreason"))
  → Accept (Store.accept → Ledger)
  → Post-accept annotations (persist_pyreason_annotations)
```

### 已验证但仅通过 mock

- `run_pyreason()` 在 e2e 测试中被 mock
- 真实 PyReason 引擎从未在 execution surface 上跑通
- 本机 `pyreason` import 因 `numba` cache 问题失败

### 已知的已关闭缺口

- `wrong engine_ext type → ValueError`（closeout `aac13c9`）
- `persist_pyreason_annotations` helper（closeout `9b78ec6`）

## §3. Phase Goals

**本阶段的目标不是继续堆 adapter feature，而是让 framework 的消费面和交付面真正支持多引擎语义。**

### 3.1 真实引擎验证 + 环境问题解决

**目标**：PyReason execution surface 在真实引擎上跑通，不只是 mock。

- 解决 `pyreason`/`numba` 安装环境问题
- 在真实引擎上跑通 `Store.evaluate(mode="pyreason")` → `accept` → `annotations` 完整链路
- 至少一个真实 derivation（不是 mock）产出有意义的 derived facts

**Gate**：真实引擎 e2e 通过 → 才能开始下面的消费面工作。否则我们在给一个未验证的 pipeline 建 UI。

### 3.2 Annotation 消费面迁移

**目标**：审计 UI / static HTML 开始读 `pyreason/semantic/*` annotation，`meta_rows` 正式退化。

- Static HTML 增加引擎语义面板（bound interval、timestep range）
- Audit package 导出包含 `assertion_annotations.jsonl`
- 至少一个 downstream consumer 优先读 `annotation_rows` 而非 `meta_rows`
- `meta_rows` 标记为 legacy compatibility layer，新写入仍双写

### 3.3 Rule compile 扩展（decision-first）

本方向分两段，不在母蓝图中直接承诺实现。

**L3a: Decision-only** — 冻结值携带谓词（value-carrying predicates）v1 语义模型。
- 这需要一个独立的 decision blueprint
- 通过后会 supersede D7（attribute-existence model）
- 必须先走 decision blueprint 流程，不能在实现蓝图中默默绕过

**L3b: Implementation** — 只有在 L3a 的 decision blueprint 通过后才开。
- WhereIR compiler 支持 `CompareExpr`（带值比较）
- Rule registry 集成（PyReason rules 可注册、可引用）

**关于 D7 supersede 的澄清**：本母蓝图继承所有 51 条冻结契约作为默认边界。子蓝图可以通过 decision-only blueprint 流程 supersede 特定契约（如 D7），但必须：(1) 开显式的 decision blueprint，(2) 获得审批，(3) 在新 decision blueprint 中标注 "supersedes D7"。不允许在实现蓝图中隐式绕过冻结契约。

### 3.4 ProbLog semantic-delivery parity

**目标**：让 ProbLog 的引擎语义进入框架的消费面和交付面，验证框架通用性。

ProbLog 已经有基本的 `Store.evaluate(mode="problog")` 能力（`adapters/problog/__init__.py` 已注册）。本方向不是"让它能跑"——而是补齐 semantic-delivery parity：

- `problog/semantic/probability` 进入 Annotation Store
- 复用现有 audit package / assertion detail / static HTML annotation panel 消费该 annotation
- 继续保留 shared compatibility lane：`meta.confidence` + `confidence_kind="probability"`

本方向的实现范围刻意保持窄：

- 不在 L4 内引入 `ProbLogExt(EngineExtBase)`
- 不在 L4 内承诺 provenance carrier
- 不在 L4 内新增 `engine_options`

这些如果后续需要，应该各自开新的 spike / decision / implementation blueprint，而不是混入 semantic-delivery parity 主线。

L4 已由子蓝图实现并归档：

- [2026-03-27_problog-semantic-annotation-parity-l4.md](../archive/2026-03-27_problog-semantic-annotation-parity-l4.md)

**Gate**：PyReason 真实验证通过（Gate 1）→ 才开始 ProbLog parity。否则可能在不成熟的框架上重复犯设计错误。

## §4. Direction Lines (子蓝图方向)

| Line | Description | Pre-requisite |
|------|-------------|---------------|
| **L1** | PyReason 真实引擎验证 | 环境问题解决 |
| **L2** | Annotation 消费面（static HTML + audit export） | L1 通过 |
| **L3a** | Value-carrying semantics v1 decision | L1 通过 |
| **L3b** | Rule compile v1 implementation（CompareExpr + 值携带） | L3a 通过 |
| **L4** | ProbLog semantic-delivery parity | L1 + L2 通过 |

**推荐执行顺序**：L1 → L2 → L3a → L3b → L4

每条线应该开独立的子蓝图，不在母蓝图中承诺实现细节。

**编号澄清**：`engine_options` 不属于上述方向线编号。它作为 future design branch 单独跟踪于 [2026-03-27_engine-options-runtime-dispatch-decision.md](./2026-03-27_engine-options-runtime-dispatch-decision.md)；主线 **L4** 仍然是 ProbLog semantic-delivery parity。

### Future design branches（不在本阶段主线内）

- `engine_options` 透传到 `Store.evaluate()` core 签名 — 已单独开 [2026-03-27_engine-options-runtime-dispatch-decision.md](./2026-03-27_engine-options-runtime-dispatch-decision.md) 做 decision-only 收口；仍不计入主线方向线编号
- `Query.engine_ext` — 等有真实 consumer 再开

## §5. Non-goals

- 不在本母蓝图中承诺统一 ProofNode 设计（等 3 个引擎样本都有 provenance 后再审视）
- 不做 `meta_rows` 全面删除（只退化为 legacy，不做 breaking migration）
- 不做多引擎 execution planner（引擎选择仍由用户通过 `mode=` 显式指定）
- 不做 Query 统一（`Query.engine_ext` 等有真实 consumer 再开）
- 不做 narrative/NL 扩展
- 不重开 certainty v1

## §6. Decision Gates

### Gate 1: Real Engine Validation

**问题**：PyReason execution surface 能不能在真实引擎上跑通？

**成功标准**：
- `pyreason` import 成功
- `Store.evaluate(mode="pyreason")` 产出非 mock 的 CandidateSet
- `accept` + `persist_pyreason_annotations` 写入 Ledger
- 至少一条 derived fact 有意义的 bound != [1.0, 1.0]

**如果失败**：暂停 L2/L3a/L3b/L4，先解决环境/兼容性问题。

### Gate 2: Annotation Consumer Validation

**问题**：`pyreason/semantic/*` annotation 能不能被审计面正式消费？

**成功标准**：
- Static HTML 展示 bound interval
- Audit package 包含 `assertion_annotations.jsonl`
- 至少一个 consumer 不依赖 `meta_rows.confidence`

**如果失败**：Annotation Store 的设计需要修正。

### Gate 3: Third Engine Semantic-Delivery Parity

**问题**：ProbLog 的引擎语义能不能在不引入新的 semantic-delivery 相关 core 扩展的情况下进入消费面？

**成功标准**：
- `ProbLogExt(EngineExtBase)` 走现有 `engine_ext` 路径
- `problog/semantic/probability` 进入 Annotation Store
- Static HTML / audit package 能展示 ProbLog 语义面板
- 不需要新增与 engine semantic delivery 无关的 core 签名扩展

**澄清**：这里不排斥必要的 core 改动（如 `engine_options` 如果被证明是 semantic delivery 的必需品）。排斥的是"因为 ProbLog 接入而被迫做不相关的 core 膨胀"。

**如果失败**：framework 的通用性假设需要修正——可能需要回到 decision-only blueprint 重新审视 `EngineExtBase` 或 `Annotation Store` 的设计。

## §7. Frozen Contract Inheritance

本母蓝图继承所有 51 条冻结契约作为默认边界。

**Supersede 机制**：子蓝图可以通过 decision-only blueprint 流程 supersede 特定契约，但必须满足：
1. 开显式的 decision blueprint
2. 获得审批
3. 在新 decision blueprint 中标注 "supersedes #N"
4. 不允许在实现蓝图中隐式绕过冻结契约

**已知可能被 supersede 的契约**：
- `#49 (D7)`: PyReason v0 attribute-existence model — 如果 L3a 的 value-carrying semantics decision 通过

新的冻结决策将在子蓝图中产生，不在母蓝图层面预设。

## §8. Collaboration Protocol

沿用现有工作流：
1. Blueprint-driven (draft → scoped → implementing → implemented → archived)
2. Hook restriction on `src/factpy_kernel/`
3. Contract-first: freeze decisions before implementation
4. Decision-only blueprints for cross-cutting concerns
5. Docs sync at implementation close
6. Archive inventory updated at each archive
7. Annotation ≠ meta: engine truth semantics → Annotation Store
