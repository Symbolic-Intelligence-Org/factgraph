# Task Blueprint: ProbLog Timeout Eval Surface

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/problog/__init__.py`
  - `src/factpy_kernel/adapters/problog/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/problog_engine.py`
  - `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
  - `src/factpy_kernel/tests/test_problog_engine_eval.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-27_engine-options-runtime-dispatch-decision.md](../active/2026-03-27_engine-options-runtime-dispatch-decision.md)
  - [2026-03-27_multi-engine-execution-surface-decision.md](../active/2026-03-27_multi-engine-execution-surface-decision.md)
- Audit Log:
  - [2026-03-28_problog-timeout-eval-surface.audit.md](./2026-03-28_problog-timeout-eval-surface.audit.md)

## 1. Problem

ProbLog 在仓内已经有一条可运行的 shared evaluate path，但它仍处于较早期的结构形态：

- evaluator 逻辑仍直接放在 adapter `__init__.py`
- shared `engine_options` 对 ProbLog 没有正式 surface
- 实际存在的 runtime knob `run_problog(..., timeout=30)` 还不能通过 `sdk.evaluate(..., mode="problog", engine_options=...)` 消费

这意味着 ProbLog 当前虽然“能跑”，但在 execution-surface 设计上没有和 PyReason/Souffle 一样形成清晰的 evaluator module / runtime-options boundary。

## 2. Goals

- 将 ProbLog evaluator 从 `__init__.py` 拆到独立 `engine_eval.py`
- 为 shared `engine_options` 正式开放一个真实存在的 ProbLog runtime 参数：`timeout`
- 保持现有 `body_confidences`、annotation persistence、candidate shaping 行为不变
- 补 focused tests，覆盖 dispatch、option normalization、pending annotations
- 用真实 ProbLog CLI 做一轮 smoke validation，并同步模块文档

## 3. Non-goals

- 不引入 `ProbLogRuleExt` 或 `engine_ext`
- 不处理 provenance / explanation carrier
- 不处理 `body_confidences` shared-core debt
- 不扩展 ProbLog DSL / export atom capability

## 4. Current Context

- 当前实现入口：
  - `adapters/problog/__init__.py` 中直接定义 `evaluate_problog(...)`
  - `problog_engine.py` 已支持 `timeout` 参数，但只有 adapter-internal caller 能用
- 当前已知约束：
  - core `evaluate_store(...)` 已能把 `engine_options` 透传给 engine adapter
  - ProbLog adapter docs 当前明确写着“不提供 `engine_options`”
- 当前相关历史蓝图：
  - `2026-03-27_engine-options-runtime-dispatch-decision`
  - `2026-03-27_multi-engine-execution-surface-decision`

## 5. Proposed Shape

新增 `adapters/problog/engine_eval.py`，承载：

- `evaluate_problog(...)`
- `resolve_problog_run_config(...)` 或等价的轻量 option normalizer
- `_remember_pending_probability_annotations(...)`

shared runtime surface 只接受：

- `engine_options={"timeout": <positive int seconds>}`

行为约束：

- 缺省 `timeout=30`
- unknown key 直接 `ValueError`
- 非正整数直接 `ValueError`

`__init__.py` 只保留 import/export 与注册，不再承载主要 evaluator 实现。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `timeout` 是 call-time only runtime option，不进入 `Derivation` payload
  - `body_confidences` 继续作为 ProbLog 的当前 definition/compile 输入
  - `persist_problog_annotations(...)` 行为不变
- 明确不做的内容：
  - 不新增 `EngineExtBase` 子类
  - 不把 CLI 细节扩成一整套 adapter config dataclass，除非代码需要最小 normalization helper
  - 不修改 core evaluate 签名
- 兼容性约束：
  - 不传 `engine_options` 时行为保持和现在一致
  - 现有 `import factpy_kernel.adapters.problog` 注册路径保持不变

## 7. Acceptance

- [x] 代码行为满足任务目标
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步
- [x] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. 抽出 ProbLog evaluator 到 `engine_eval.py`，保持 `__init__.py` 只做注册与 re-export。
2. 增加 `timeout` runtime option normalization，并把它传递到 `run_problog(...)`。
3. 增加 focused tests，覆盖 evaluate dispatch、default/override timeout、bad options、annotation pending state。
4. 同步 ProbLog adapter docs，跑 targeted + full regression，并做本机真实 ProbLog CLI smoke。

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - ProbLog evaluator 已从 adapter `__init__.py` 抽到独立 [engine_eval.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/adapters/problog/engine_eval.py)
  - shared `engine_options` 现在正式支持 `timeout`
  - adapter docs 已同步，明确 `engine_ext` 仍不支持、`timeout` 是唯一公开 runtime option
  - 新增 focused tests 覆盖 timeout default/override、bad options、registration、engine_ext rejection
- 与 blueprint 不同的地方：
  - 为了完成真实 CLI 验证，顺带修了一个既有 importer 漏洞：ProbLog 实际输出的 `answer(...):\t0.42` tab-format 之前无法被 parser 接受
  - 没有更新独立 demo 文件
- 为什么会有这些调整：
  - tab-format parser 漏洞直接阻塞 real-engine E2E，属于本任务 acceptance 的必要修复
  - repo 当前没有独立 ProbLog demo 文件，adapter docs 已承担本轮 public behavior closeout
- 归档说明：
  - 2026-03-28 实现完成后归档；验证包括 targeted unittest、全量 unittest，以及本机真实 ProbLog CLI smoke
