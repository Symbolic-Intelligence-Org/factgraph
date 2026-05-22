# Task Blueprint: PyReason Graph-Fact Materialization Fix

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py`
  - `src/factpy_kernel/tests/test_pyreason_runner.py`
  - `src/factpy_kernel/tests/test_pyreason_engine_eval.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-27_value-carrying-semantics-v1-decision.md](./2026-03-27_value-carrying-semantics-v1-decision.md)
- Audit Log:
  - [2026-03-28_pyreason-graph-fact-materialization-fix.audit.md](./2026-03-28_pyreason-graph-fact-materialization-fix.audit.md)

## 1. Problem

真实 PyReason 端到端验证表明，当前 adapter 把 `PyReasonSession` 中的 label facts 全部编码为 graph attributes，再调用 `pr.load_graph(graph)`，会阻止规则传播。对照实验显示：

- graph attribute only：不触发规则
- `add_fact(...)` only：规则正常传播
- 同一 label 同时出现在 graph attribute + `add_fact(...)`：冲突，规则仍不传播

这说明当前 factpy PyReason adapter 的 EDB materialization strategy 与真实引擎行为不兼容。

## 2. Goals

- 把 PyReason graph 构建收窄为结构载体：只保留 node / edge 拓扑
- 把 `PyReasonSession` 中的 node/edge label facts 统一经 `pr.add_fact(...)` 注册
- 保持 bounded fact 的 interval 语义与时间窗编码不变
- 更新测试和文档，使 shared evaluate path 与 reusable runner path 都覆盖新策略

## 3. Non-goals

- 不修改 core evaluate surface
- 不重做 PyReason WHERE compiler
- 不扩展新的 rule syntax / value-variable 语义
- 不处理 upstream PyReason 其他潜在 JIT/平台问题

## 4. Current Context

- 当前实现入口：
  - `engine_eval._materialize_edb_session(...)` 把 Ledger facts 映射成 `PyReasonSession`
  - `runner.build_pyreason_graph(...)` 把 session facts 编码为 graph attributes
  - `runner.run_pyreason(...)` 只对显式 `fact_defs` / legacy `facts` 调 `pr.add_fact(...)`
- 当前已知约束：
  - PyReason `Fact(...)` 支持 interval text：`pred(node) : [lo, hi]`
  - edge predicates 仍需要 graph 中存在对应 edge 结构
  - bounded value-carrying 语义仍应通过 fact interval 保留
- 当前相关历史蓝图：
  - `2026-03-27_value-carrying-semantics-v1-decision.md`

## 5. Proposed Shape

- `build_pyreason_graph(...)` 只构建 nodes + edges，不再写任何 predicate label attribute
- 新增 session fact -> fact text lowering helper，把 node / edge facts 转成 PyReason initial facts
- `run_pyreason(...)` 在 `pr.load_graph(graph)` 后，先注册 session facts，再注册显式 `fact_defs` / legacy `facts`
- `engine_eval._materialize_edb_session(...)` 继续负责从 Ledger 形成 session，不改 shared surface

## 6. Boundaries And Invariants

- 必须保持的边界：
  - graph 继续是 PyReason 的结构输入
  - initial facts 继续通过 adapter-local session 组织，不把 fact text 组装逻辑泄漏到 core
  - bounded facts 仍保持 `[lo, hi]` interval 语义，不退回 binary truth
- 明确不做的内容：
  - 不在 schema 上引入静态 EDB/IDB 标注
  - 不尝试自动分析某个 predicate 是否“会被推导”来决定 graph/fact 路由
- 兼容性约束：
  - `run_pyreason(..., fact_defs=...)` 和 legacy `facts=` 继续可用
  - session API 不变

## 7. Acceptance

- [x] reusable runner 改为 structure-only graph + session facts via `add_fact`
- [x] engine_eval shared path 复用该策略，不再把 label facts写入 graph attributes
- [x] bounded facts / edge facts / legacy facts 的测试覆盖更新
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 在 runner 中拆出 session fact lowering helper，并把 graph build 改成结构-only
2. 更新 engine_eval / runner tests，使行为围绕 fact registration 而不是 graph attrs
3. 更新 PyReason adapter docs，补 Outcome / Deviations，并归档 blueprint

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `build_pyreason_graph(...)` 现在只构建 nodes / edges 结构，不再写 predicate labels 为 graph attributes
  - `run_pyreason(...)` 现在会把 `PyReasonSession` 中的 node/edge facts lower 为 explicit `Fact(...)` text，并在 `load_graph(...)` 后统一 `add_fact(...)`
  - shared engine path 无需改 surface；`engine_eval._materialize_edb_session(...)` 继续产出 session，runner 内部消费策略已切换
  - runner/rule_ext tests 已从 graph-attr 断言改为 structure-only graph + fact registration 断言
- 与 blueprint 不同的地方：
  - 没有新增 schema 级 EDB/IDB 区分，也没有在 engine_eval 上添加额外 routing 开关
- 为什么会有这些调整：
  - 真实问题不在静态 predicate 分类，而在“结构输入”和“初始 label facts”混用同一 graph-attribute 载体
- 归档说明：
  - blueprint 与 audit 在 targeted validation 完成后移入 `docs/blueprints/archive/`
