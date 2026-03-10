# Core 质量评估（代码快照）

- 评估范围：`src/factpy_kernel/core`
- 最后更新：2026-03-10
- 评估基线：基于当前源码结构与公开入口（非历史版本）

## 1. 结论摘要

`core` 当前处于“语义边界清晰、可持续演进”的状态，主要优势在于：

- `Store` 入口清晰（`runtime/evaluation/queries/builders`）
- `Ledger` 写入原子、持久化明确（SQLite 真相 + 内存读缓存）
- `evaluate` 模式约束明确（`native|souffle|problog`）
- `accept_many` 提供批处理语义（`atomic` / `best_effort`）
- `where` 具备 AST gate 与 validator 双层护栏
- 与上层声明元数据边界清楚：`version / description / tags` 属于 authoring/sdk 资产层，不污染 core 执行语义

## 2. 维度评分（当前快照）

| 维度 | 评分 | 说明 |
|---|---:|---|
| 架构边界清晰度 | 9.2 | core 与 adapters 通过注册机制解耦，入口收口明确 |
| 语义完整性 | 8.7 | 写入/投影/规则/派生/accept/mapping 已闭环 |
| 可维护性 | 8.8 | 公共入口与实现层拆分合理，兼容层集中可控 |
| 正确性护栏 | 9.0 | SchemaIR 校验、where gate、写协议输入约束较完整 |
| 可扩展性 | 8.3 | engine 可插拔，但兼容层与历史入口仍需逐步清理 |
| 性能基础 | 8.2 | ledger 热路径已有索引缓存，后续主要在导出/大批量路径优化 |
| 综合 | 8.7 | 已具备稳定迭代基础，下一步重心应转向兼容面收敛与可观测性 |

## 3. 模块观察

### 3.1 `store.runtime/evaluation/queries/builders`

优点：

- 对外职责分离清楚，`Store` API 保持稳定
- `evaluate(mode=...)` 行为明确，历史别名已显式报错
- 查询入口（`explain/conflicts/resolve_mapping`）与构建入口解耦

风险：

- 仍保留 `_*.py` 实现层与 `store.api` shim，增加阅读成本

### 3.2 `store.ledger`

优点：

- append-only + revocation 语义稳定
- SQLite 持久化与读缓存并行，接口形态一致
- `append_assertion/append_revocation` 原子边界清晰

风险：

- 文件型 ledger 仍按单进程缓存模型设计

### 3.3 `view.projector`

优点：

- `single/multi` 语义清晰
- `project_view_facts_with_audit` 提供轻量审计统计
- `project_display_facts` 提供展示聚合能力

风险：

- 目前 audit 仅返回结构，不自带长期观测管道

### 3.4 `derivation.accept`

优点：

- `AcceptResult` 字段稳定
- `accept_many` 具备拓扑排序、循环检测、原子回滚
- entity/fact 两类候选路径已收敛

风险：

- 错误码部分依赖异常消息前缀，长期建议继续结构化

### 3.5 `rules.where_*`

优点：

- AST parse/validate 与 evaluator 分层清晰
- gate 开关可控（`FACTPY_WHERE_AST_VALIDATE`）

风险：

- 新增 where 能力仍需同步 native 与 adapter 编译语义

## 4. 主要风险与优先项

### P1：兼容面仍偏大

表现：

- `Store.evaluate_dummy(...)` 仍在
- `store.api` 与 `_*.py` 兼容层仍在

建议：

- 明确 deprecation 时间线，逐步迁移调用方

### P1：accept_many 契约的外部文档与回归需继续增强

表现：

- 当前实现语义完整，但批处理状态流对新调用方理解成本较高

建议：

- 补最小可复用示例（atomic 回滚、blocked dependency、duplicate）

### P1：多进程共享 ledger 的一致性边界尚未定义

建议：

- 若有多进程需求，先定义缓存失效/刷新协议，再扩展实现

## 5. 建议的下一阶段目标

1. 收敛兼容入口（优先 `evaluate_dummy` 与旧导入 shim）。
2. 加强批处理 accept_many 的契约样例与错误码文档。
3. 在固定基准场景下建立性能回归记录（评估导出与大批量写入路径）。
