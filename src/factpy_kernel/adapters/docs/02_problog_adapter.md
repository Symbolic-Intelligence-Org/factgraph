# ProbLog Adapter 总览（factpy_kernel）

- 范围：`src/factpy_kernel/adapters/problog`
- 最后更新：2026-03-18
- 目标读者：需要理解 ProbLog 导出、执行、结果回读链路的开发者

## 1. 模块职责

`adapters.problog` 是外部引擎适配层，负责把 `Store + derivation/query where` 转为 ProbLog 程序，执行并回读为 `CandidateSet`。

它主要负责：

- `Store.evaluate(mode="problog")` 的 evaluator 注册与实现
- where IR 到 ProbLog 子句的导出
- 调用 ProbLog CLI 执行
- 把 CLI 输出解析回 bindings，再构造成候选集
- 将概率写回 `CandidateSet.confidence`

它不负责：

- core 规则语义定义
- runtime session / HTTP 编排
- Deontic 规范执行语义

## 2. 当前模块结构

- `__init__.py`
  - 定义 `evaluate_problog(...)`
  - import 时注册：`register_engine_evaluator(evaluate_problog, "problog")`
- `problog_export.py`
  - `export_problog(...)`：导出 `.pl`
- `problog_engine.py`
  - `run_problog(...)`：调用 ProbLog CLI
- `problog_import.py`
  - `parse_problog_output(...)`：解析输出并构造 `CandidateSet`

## 3. 与 core 的边界

和 Souffle 适配器一致，Problog 通过 mode 注册到 `Store`：

1. 导入 `factpy_kernel.adapters.problog`
2. `__init__` 注册 evaluator 名称 `problog`
3. 调用 `Store.evaluate(mode="problog")` 时进入 `evaluate_problog(...)`

## 4. 典型工作流

`evaluate_problog(...)` 主流程：

1. 校验目标和变量绑定（entity head / fact head）
2. 组装 rule_spec（包含 `where/head/head_vars/query_vars/body_confidences`）
3. `export_problog(...)` 生成临时 `query.pl`
4. `run_problog(...)` 调用 ProbLog CLI
5. `parse_problog_output(...)` 解析结果并映射为 `CandidateSet`
6. 将推导概率写入 `candidate.confidence`

explainability 补充：

- 当前 ProbLog adapter 只回读概率结果，不输出 derivation witness / proof tree。
- 因此由该适配器生成的 candidates 第一轮会显式标记：
  - `support_kind="engine_no_witness_v1"`
  - `support_digest="sha256:000...0"`（兼容占位符）
- service `explain_ref(kind="candidate")` 对这类 candidate 返回 `ok=true` + `witness_status="degraded"`，表示 candidate 有效，但当前没有可解引用的 witness artifact。

## 5. 导出口径（`problog_export.py`）

- EDB 来源：ledger 当前 active claims
- 每条 claim 概率：
  - 默认 `1.0`
  - 可从 `meta.confidence` 读取
- where 分支可配置 `body_confidences`（分支概率）
- 输出程序包含：
  - `edb_fact(...)` 事实
  - `rule_body_i` 分支规则
  - `answer(...)` 聚合规则
  - `query(answer(...)).`

where 支持的原子子集：

- `pred`（当前仅支持 1 或 2 个 term）
- `eq`
- `gt/ge/lt/le`
- `in`
- `not`（支持 not-body 的 OR 分支）

## 6. 执行口径（`problog_engine.py`）

CLI 二进制：

- 默认命令：`problog`
- 可由环境变量 `PROBLOG_BIN` 覆盖

错误处理：

- 缺少 CLI：`ProbLogEngineError`
- 超时：`ProbLogEngineError`
- 非零退出码：`ProbLogEngineError`

## 7. 输出解析口径（`problog_import.py`）

- 支持 `tab` 或 `:` 概率结果行
- 按 `query_pred`（默认 `answer`）过滤
- 同一 binding 取最大概率
- 再按候选键聚合概率，回填 `CandidateSet.confidence`
- 最终候选构造仍复用 `store_builders`（与 native/souffle 路径一致）

## 8. 当前限制

- 依赖外部 ProbLog CLI
- `pred` 原子当前只支持 1/2 元参数映射
- 主要服务 derivation query 执行，不覆盖 Deontic 规范执行
- 当前不输出 derivation/proof witness；第一轮只保证显式 degraded explain 语义
