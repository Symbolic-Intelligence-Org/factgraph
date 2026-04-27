# Core 开发进度与路线图

- 范围：`src/kernel/core`
- 最后更新：2026-03-10
- 基线：以当前源码行为为准（非历史版本）

## 1. 当前状态快照

已完成的结构性工作：

- `Store` 公共入口已收口到 `runtime/evaluation/queries/builders`
- `Store.evaluate` 模式统一为 `native|souffle|problog`
- `mode='python'|'engine'` 已移除并提供明确报错
- `core` 与 `adapters` 通过 `register_engine_evaluator` 解耦
- `Ledger` 采用 SQLite 真相 + 内存读缓存的 write-through 模式
- `project_view_facts_with_audit` 使用 `ProjectorAudit(contract_version=2)`
- `accept_many` 支持 `atomic` / `best_effort` 与候选依赖拓扑排序
- where AST gate 已接入（`FACTPY_WHERE_AST_VALIDATE`）
- 上层声明元数据已统一为 `version / description / tags`；core 明确保持非语义边界

## 2. 已完成里程碑

### M1. Store 边界收口（完成）

结果：

- `runtime.py` 管门面
- `evaluation.py` 管 evaluate 主流程
- `queries.py` 管查询 facade
- `builders.py` 管 candidate 构建

### M2. Engine 注入解耦（完成）

结果：

- core 无需静态 import adapter
- `souffle/problog/pyreason` 在适配器 import 时自注册 evaluator

### M3. Ledger 持久化（完成）

结果：

- SQLite 持久化表 + 索引建立
- append 事务写入与读缓存同步
- 账本可内存模式或文件模式运行

### M4. Accept 批处理能力（完成）

结果：

- 引入 `accept_many_candidate_sets(...)`
- 支持依赖拓扑排序、循环检测、atomic 回滚

### M5. Projector 审计接口（完成）

结果：

- `project_view_facts_with_audit(...)` 返回审计结构
- 审计字段聚焦 active/selected/policy-drop 统计

## 3. 当前主要风险

1. 兼容层仍较多：`store.api`、`Store.evaluate_dummy`、`store/_*.py`。
2. `accept_many` 的状态机复杂度已上升，但文档示例仍不够系统。
3. 文件型 ledger 的多进程一致性边界未定义。

## 4. 下一阶段优先级

### P1. 兼容入口收敛

目标：

- 对 `evaluate_dummy` 给出明确下线计划
- 将新代码路径完全收敛到 `runtime/evaluation/queries/builders`

### P1. accept_many 契约强化

目标：

- 明确各 `state/error.code` 的调用方建议
- 增加 atomic 回滚与 blocked dependency 的固定示例

### P1. ledger 运行边界定义

目标：

- 明确单进程缓存模型是当前保证范围
- 若扩展多进程，先给出刷新/失效协议

### P2. 规则与引擎语义一致性治理

目标：

- 新 where 能力保持 native 与 adapter 行为一致
- 对关键路径补 parity 回归样例

### P2. 性能基线制度化

目标：

- 固定 benchmark 场景与记录格式
- 让性能改动具备可追踪前后对比

## 5. 执行原则

1. 先稳语义，再做性能。
2. 先收敛兼容面，再扩 API 面。
3. 对外契约变更必须先改文档，再改实现，再补回归。
