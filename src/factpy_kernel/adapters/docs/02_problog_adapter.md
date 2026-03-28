# ProbLog Adapter 总览（factpy_kernel）

- 范围：`src/factpy_kernel/adapters/problog`
- 最后更新：2026-03-28
- 目标读者：需要理解 ProbLog 导出、执行、结果回读链路的开发者

## 1. 模块职责

`adapters.problog` 是外部引擎适配层，负责把 `Store + derivation/query where` 转为 ProbLog 程序，执行并回读为 `CandidateSet`。

它主要负责：

- `Store.evaluate(mode="problog")` 的 evaluator 注册与实现
- where IR 到 ProbLog 子句的导出
- 调用 ProbLog CLI 执行
- 把 CLI 输出解析回 bindings，再构造成候选集
- 将概率写回 `CandidateSet.confidence`，并写 `confidence_kind="probability"`
- 将 accepted ProbLog 候选的概率以 `problog/semantic/probability` 写入 Annotation Store（通过 post-accept binder）

它不负责：

- core 规则语义定义
- runtime session / HTTP 编排
- Deontic 规范执行语义

## 2. 当前模块结构

- `__init__.py`
  - import 时注册：`register_engine_evaluator(evaluate_problog, "problog")`
  - re-export `persist_problog_annotations(...)` 等公开入口
- `engine_eval.py`
  - `evaluate_problog(...)`
  - `resolve_problog_timeout(...)`：shared `engine_options` 归一化
  - `_remember_pending_probability_annotations(...)`
- `provenance.py`
  - `ProbLogTraceV0` / `ProbLogTraceEventV0` / `parse_problog_trace(...)`
- `problog_export.py`
  - `export_problog(...)`：导出 `.pl`
- `problog_engine.py`
  - `run_problog(...)`：调用 ProbLog CLI（当前 shared evaluate path 默认带 `--trace`）
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
2. 用 `resolve_problog_timeout(engine_options)` 归一化运行超时
3. 组装 rule_spec（包含 `where/head/head_vars/query_vars/body_confidences`）
4. `export_problog(...)` 生成临时 `query.pl`
5. `run_problog(...)` 调用 ProbLog CLI
6. `parse_problog_output(...)` 解析结果并映射为 `CandidateSet`
7. `parse_problog_trace(...)` 把同一份 `--trace` 输出解析成 adapter-local proof trace
8. 将推导概率写入 `candidate.confidence`，并标注 `candidate.confidence_kind="probability"`
9. 若 trace 非空，则把每个 candidate 升级成：
   - `support_kind="problog_provenance_v1"`
   - `support_digest=<ProvenanceEnvelope digest>`
   - runtime `explain_ref(kind="candidate")` 可直接读回 `payload_type="proof_trace"` 的 provenance envelope
10. `evaluate_problog(...)` 把待持久化的 `problog/semantic/probability` 模板缓存到 store pending state
11. caller 在 `accept` 后调用 `persist_problog_annotations(...)`，将真实 `asrt_id` 绑定到 Annotation Store

explainability 补充：

- 当前 ProbLog adapter 已能把 CLI `--trace` 输出接到 runtime candidate explain：
  - `support_kind="problog_provenance_v1"`
  - `support_digest=<ProvenanceEnvelope digest>`
  - runtime `explain_ref(kind="candidate")` 返回 engine-native provenance envelope
- 当前不会把这条 provenance 强制转成 `SupportArtifact` 或 candidate evidence tree：
  - `explain-tree`
  - `explain-summary`
  - `explain-narrative`
  - `explain-nl`
  仍不支持 `problog_provenance_v1`
- 若 future engine path 没有 trace，则仍会回落到：
  - `support_kind="engine_no_witness_v1"`
  - `support_digest="sha256:000...0"`

semantic-delivery 补充：

- shared compatibility lane:
  - `accept` 仍会把 `candidate.confidence` 写入 `meta.confidence`
  - `confidence_kind="probability"` 也继续保留在 meta
- engine-native semantic lane:
  - `persist_problog_annotations(...)` 会把 accepted fact candidate 的概率写成 `problog/semantic/probability`
  - L2 已完成的 audit export / reader / static annotation panel 会自动消费该 annotation

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
- shared evaluate surface 当前可通过 `engine_options={"timeout": 15}` 覆盖 CLI timeout；缺省 `timeout=30`
- shared evaluate path 当前默认追加 `--trace`，以便生成 runtime candidate provenance

错误处理：

- 缺少 CLI：`ProbLogEngineError`
- 超时：`ProbLogEngineError`
- 非零退出码：`ProbLogEngineError`

### 6A. Shared Runtime Options

ProbLog 当前对 shared evaluate surface 公开的 run-time 选项只有一个：

- `timeout: int`

约束：

- `sdk.evaluate(..., mode="problog", engine_options={"timeout": 15})` 会生效
- 缺省时使用 adapter 默认值 `timeout=30`
- unknown keys 直接报 `ValueError`
- 非正整数直接报 `ValueError`
- `engine_options` 是 call-time only，不进入 `Derivation`、`to_authoring_payload()` 或 Ledger

## 7. 输出解析口径（`problog_import.py`）

- 支持 `tab` 或 `:` 概率结果行
- 按 `query_pred`（默认 `answer`）过滤
- 同一 binding 取最大概率
- 再按候选键聚合概率，回填 `CandidateSet.confidence`
- 同时把 `CandidateSet.confidence_kind` 标注为 `"probability"`
- 最终候选构造仍复用 `store_builders`（与 native/souffle 路径一致）

## 8. 当前限制

- 依赖外部 ProbLog CLI
- `pred` 原子当前只支持 1/2 元参数映射
- 主要服务 derivation query 执行，不覆盖 Deontic 规范执行
- 当前只承诺 runtime `explain_ref(kind="candidate")` flat provenance envelope；不会自动生成 candidate evidence tree / summary / narrative / NL
- 当前不提供 ProbLog session API 或 `engine_ext`；shared runtime options 当前只开放 `timeout`
