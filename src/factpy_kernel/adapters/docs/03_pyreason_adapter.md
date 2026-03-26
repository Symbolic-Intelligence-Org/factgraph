# PyReason Adapter（factpy_kernel）

- 范围：`src/factpy_kernel/adapters/pyreason`
- 最后更新：2026-03-26
- 状态：adapter-local V0 spike（非正式集成）

## 1. 概述

PyReason adapter 是 factpy 对 [PyReason](https://github.com/lab-v2/pyreason) 图推理引擎的最小接入验证。当前只实现了 provenance trace 提取，不包含完整的 schema/fact/rule/evaluate 集成。

PyReason 使用 Generalized Annotated Logic Programs (GAPs) 在 NetworkX 图上做区间值时序推理，与 Souffle（确定性 Datalog）和 ProbLog（概率逻辑）都有本质差异。

## 2. 环境要求

- `pyreason==3.0.0`（3.4.0 在 ARM64 macOS 上 import 失败）
- Python 3.10
- 手动安装：`pip install 'pyreason==3.0.0'`（不在 `pyproject.toml` 中，spike-only dependency）
- 首次 Numba JIT 编译约 `85s`（ARM64 macOS），缓存后约 `8.7s`

## 3. 当前模块内容

| 文件 | 角色 |
|------|------|
| `provenance.py` | `PyReasonTraceEventV0` / `PyReasonTraceV0` / `parse_pyreason_trace` / `pyreason_trace_to_dict` |
| `__init__.py` | 空模块入口 |

## 4. PyReason 推理模型

```text
输入：NetworkX DiGraph + 规则 + 初始事实
规则语法：head(x) <-T body(y), edge(x,y)   （T = 时间步延迟）
值域：[lower, upper] 区间，不是 true/false 或概率
世界假设：开放世界（缺失事实 = [0,1] 未知，不是 false）
输出：Interpretation（每时间步每节点的谓词区间值）+ Rule Trace（事件日志）
```

## 5. Trace 数据形态

PyReason 的 `pr.get_rule_trace(interpretation)` 返回两个 pandas DataFrame。

**nodes_trace 列：**

| 列 | 含义 |
|----|------|
| Time | 时间步 |
| Fixed-Point-Operation / Fixed-Point-Op | 固定点迭代编号 |
| Node | 图节点标识 |
| Label | 谓词名 |
| Old Bound | 变化前的区间 `[lo, hi]` |
| New Bound | 变化后的区间 `[lo, hi]` |
| Occurred Due To | 规则名或 `fact` |
| Clause-1, Clause-2, ... | 具体的 clause grounding（哪些节点/边匹配了规则体原子） |

**这是事件日志（event log），不是证明树（proof tree）。**

## 6. Souffle vs PyReason Provenance 对比

### 6.1 形态

| 维度 | Souffle | PyReason |
|------|---------|----------|
| **数据结构** | JSON proof tree（per-conclusion） | pandas DataFrame event log（per-change） |
| **粒度** | 一棵树解释一个结论 | 所有变化的扁平日志 |
| **时间维度** | 无 | 内建 timestep，可追踪传播 |
| **值域** | Boolean（true/false） | 区间 `[lower, upper]` |
| **世界假设** | 封闭（CWA） | 开放（OWA，缺失 = `[0,1]`） |
| **获取方式** | `-t explain` + stdin pipe（subprocess） | `pr.get_rule_trace()`（in-process Python） |
| **序列化** | JSON（天然） | DataFrame → 需转换为 JSON |

### 6.2 可统一字段

| 字段 | Souffle | PyReason | 可统一？ |
|------|---------|----------|---------|
| 结论标识 | `relation(args)` | `Node + Label` | ✅ 映射 |
| 规则标识 | `rule-number (R1)` | `Occurred Due To`（rule name） | ✅ 语义一致 |
| 叶子事实 | `axiom` nodes | `Occurred Due To = "fact"` rows | ✅ 语义一致 |
| 时间 | 无 | `Time` 列 | ❌ Souffle 无此维度 |
| 区间值 | 无 | `Old Bound / New Bound` | ❌ Souffle 无此维度 |
| 否定 | `!relation` negation leaf | 不适用（OWA 下无显式否定） | ❌ 语义不同 |
| 子证明截断 | `subproof` marker | 不适用 | ❌ Souffle 特有 |
| Clause grounding | 无（隐含在树结构中） | `Clause-1, Clause-2, ...` 显式列 | ⚠️ 形态不同但语义可桥接 |

### 6.3 ProofNode v1 更新建议

基于 Souffle + PyReason 两个真实样本的结论：

1. **不能假设所有引擎产出 tree。** Souffle 是 tree，PyReason 是 event log。统一抽象不能是 `ProofTree`。
2. **候选方案 A：per-candidate payload with engine-specific shape。** 每个 candidate 携带一个 `provenance_payload`，其 `engine` 字段指示形态（`souffle_proof_tree` / `pyreason_event_log`），consumer 按 engine 分发渲染。
3. **候选方案 B：统一为 event sequence。** 把 Souffle proof tree 展平为事件序列（DFS），再与 PyReason 的 event log 对齐。代价是丢失 Souffle 的树结构。
4. **当前建议：选 A。** 保留引擎原生形态更诚实，也更符合 ADR 的 adapter-local before core 原则。
5. **ProofNode v1 开启门槛**：至少有 2 个引擎的真实 provenance 通过 adapter → audit → static 完整管道验证后，再冻结统一抽象。当前 Souffle 已完整，PyReason 仍是 spike，不足以冻结。

## 7. 当前限制

- 不是完整的 factpy adapter（无 schema/fact/rule/evaluate 集成）
- 只有 provenance trace 提取
- 依赖 `pyreason==3.0.0`（非 repo-managed dependency）
- ARM64 macOS 首次 JIT 约 `85s`
- `PyReasonTraceEventV0` 字段未冻结
