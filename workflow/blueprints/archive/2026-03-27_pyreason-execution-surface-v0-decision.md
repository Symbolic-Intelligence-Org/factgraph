# Decision Blueprint: PyReason Execution Surface v0

- Status: superseded (by 2026-03-27_multi-engine-execution-surface-decision.md)
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
- Related Modules:
  - `src/factpy_kernel/core/store/types.py` — `EvaluateMode` literal
  - `src/factpy_kernel/core/store/_evaluate.py` — mode dispatch gate
  - `src/factpy_kernel/core/store/runtime.py` — `register_engine_evaluator` + `Store.evaluate()`
  - `src/factpy_kernel/adapters/pyreason/` — session, runner, accept, rule_ext
- Audit Log:
  - [2026-03-27_pyreason-execution-surface-v0-decision.audit.md](./2026-03-27_pyreason-execution-surface-v0-decision.audit.md)

## 1. Problem

PyReason 目前有完整的 adapter-local vertical slice（schema → session → runner → accept → ledger），但没有正式的 execution surface。用户不能通过 `Store.evaluate(mode="pyreason")` 调用它。

接入 core dispatch 需要解决 4 个设计问题，如果不先冻结就直接写代码，会反复返工。

## 2. Context

### 2.1 现有 core dispatch 机制

```
Store.evaluate(mode="souffle")
  → evaluate_store()                [_evaluate.py:31]
    → mode gate: {"native", "souffle", "problog"}  [line 50]
    → engine_evaluate = get_engine_evaluator(mode)  [runtime.py:55]
    → engine_evaluate(store, derivation_id=..., where=..., head=...)
    → return list[CandidateSet]
```

Souffle 的接入是 1 行注册：`register_engine_evaluator(evaluate_store_engine, "souffle")`。

### 2.2 PyReason 接入的 4 个 blocking 问题

1. `EvaluateMode = Literal["native", "souffle", "problog"]` 是硬编码 gate，不含 `"pyreason"`
2. `evaluate_store()` 收到的 `where` 是 lowered WhereIR，不是 Rule DSL atoms；现有 `compile_pyreason_rule()` 无法消费 WhereIR
3. `engine_options`（run-time config 如 `timesteps`）在 core 签名中不存在
4. Generic `accept` 流程不写 `pyreason/semantic/*` annotation，annotation 没有入口

## 3. Decisions to Freeze

### Decision 1: Mode 扩展 — 接受最小 core 改动

**决策**：将 `EvaluateMode` 从 closed `Literal` 改为 open union，或直接加 `"pyreason"`。

两个选项：

**A. 加 `"pyreason"` 到 Literal（最小改动）**

```python
# types.py
EvaluateMode: TypeAlias = Literal["native", "souffle", "problog", "pyreason"]

# _evaluate.py:50
if mode not in {"native", "souffle", "problog", "pyreason"}:
    raise ValueError(...)
```

改动范围：`types.py` 1 行 + `_evaluate.py` 2 处 gate + `_evaluate.py` 新增 pyreason dispatch branch。

**B. 改成 open string + registry lookup（面向未来）**

```python
# types.py
EvaluateMode: TypeAlias = str  # any registered engine name

# _evaluate.py:50
if mode not in {"native"} and get_engine_evaluator(mode) is None:
    raise ValueError(f"{mode} evaluator not registered")
```

改动范围更大，但后续新引擎不再需要改 core。

**冻结推荐**：**A**。理由：
- 当前只有 3 个引擎（Souffle + ProbLog + PyReason），open string 带来的 marginal benefit 不值得
- A 的 blast radius 最小，和 ProbLog 加入时的模式一致
- 如果将来有第 4 个引擎，那时再做 B 也不晚

### Decision 2: v0 不开放 engine_options

**决策**：v0 的 `pyreason_engine_eval()` 内部使用默认 `PyReasonRunConfig(timesteps=2)`。不在 core `Store.evaluate()` 签名中增加 `engine_options` 参数。

**理由**：
- `engine_options` 贯穿需要改 `types.py` → `_evaluate.py` → `runtime.py` → `sdk/store.py` 四层签名
- v0 没有真实用例需要用户自定义 `timesteps`
- 如果 v1 需要 `engine_options`，仍需显式扩展 core/runtime/sdk 调用签名；当前不存在现成的 kwargs 透传入口（`runtime.py:239` 的 `evaluate_engine()` 不接受 `**kwargs`）

**冻结约束**：v0 `PyReasonRunConfig` 硬编码在 adapter 内部，不暴露到 core 签名。

### Decision 3: WhereIR → PyReason compiler 是 v0 的核心新增

**决策**：v0 必须实现 `WhereIR → PyReason rule syntax` compiler，不能复用现有 `compile_pyreason_rule()`（它服务 Rule DSL atoms，不服务 lowered WhereIR）。

**最小 v0 scope**：
- 只支持 lowered WhereIR 中的 `("pred", pred_id, terms)` atom
- `terms` 只支持 `$var` token 和 string/number literal
- `cmp` / `not` / `ruleref` / `branch-list` → raise `PyReasonCompileError`（capability gate）
- Head compilation：从 `head_vars` + `target_pred_id` 生成 PyReason output 规则

**不做**：
- 完整 WHERE atom 支持
- Rule registry / nested rule ref 解析
- 多 branch OR 编译

**文件位置**：`adapters/pyreason/where_compile.py`（独立于 `rule_ext.py`）

### Decision 4: Annotation 走 degraded support + adapter-local post-accept hook

**决策**：

**4a. Provenance / support**：v0 的 `CandidateSet.support_kind` 复用现有 `engine_no_witness_v1`（`_support.py:12`）。不引入新的 support kind，不接入 explain path，不接入 witness capture。

理由：
- `engine_no_witness_v1` 已在 `_DEGRADED_SUPPORT_KINDS` 中（`_support.py:14`），现有 summary/NL surface 和 docs 已覆盖
- 引入新的 `"pyreason_degraded"` 需要同时扩 `_DEGRADED_SUPPORT_KINDS`、相关 summary surface、docs，和"最小 core 改动"目标矛盾
- v0 先把 evaluate → candidate → accept 跑通，provenance 质量后续提升

**4b. Annotation**：v0 不在 generic accept 闭环内写 annotation。而是提供一个 **adapter-local post-accept helper**，调用方在 `Store.accept()` 后显式调用。

为什么不能走 C（accept 后手动调 `accept_pyreason_session()`）作为正式 surface：
- Generic evaluate → accept 流中调用方没有 `PyReasonSession`
- 但可以在 `pyreason_engine_eval()` 内部缓存 derived session 的 annotation templates
- Post-accept helper 消费这个缓存 + accept 返回的 `asrt_id` list → 写 annotation

具体形态：

```python
# pyreason_engine_eval() 返回 candidates，同时缓存 annotation templates
result = store.evaluate(mode="pyreason", ...)
accepted = store.accept(result[0], ...)

# Post-accept: 写 pyreason/semantic/* annotation
# accepted.written_assertions 是 list[dict]，每条含 "asrt_id"
asrt_ids = [wa["asrt_id"] for wa in accepted.written_assertions]
pyreason_post_accept(store.ledger, result_cache, asrt_ids)
```

**冻结约束**：
- `CandidateSet` 结构不扩展
- annotation 不进入 generic accept flow
- post-accept helper 是 adapter-local，不是 core contract

## 4. Non-goals

- 不做 `engine_options` core 签名扩展
- 不做完整 WhereIR compiler（only PredAtom + LogicVar v0）
- 不做 explain path / witness capture for PyReason
- 不做 Query 统一
- 不做 UI / audit consumer 切换
- 不做多引擎 execution abstraction 一次定型
- 不做 `DerivationExt`
- 不做 rule registry integration for PyReason rules

## 5. Core Changes Required (minimal)

| File | Change | Lines |
|------|--------|-------|
| `core/store/types.py:14` | Add `"pyreason"` to `EvaluateMode` | 1 line |
| `core/store/_evaluate.py:50` | Add `"pyreason"` to mode gate set | 1 line |
| `core/store/_evaluate.py:54,96` | Add `mode == "pyreason"` dispatch branch | ~5 lines |

Total core changes: **~7 lines**。

## 6. New Adapter Files

| File | Role |
|------|------|
| `adapters/pyreason/engine_eval.py` | `pyreason_engine_eval()` — registered via `__init__.py` |
| `adapters/pyreason/where_compile.py` | WhereIR → PyReason rule syntax compiler |
| `adapters/pyreason/__init__.py` | `register_engine_evaluator(pyreason_engine_eval, "pyreason")` |

## 7. Acceptance Criteria for Freezing

- [ ] 4 decisions explicitly reviewed and approved
- [ ] Core change scope confirmed as minimal (~7 lines)
- [ ] WhereIR compiler scope confirmed (lowered `("pred", pred_id, terms)` atoms only)
- [ ] `engine_no_witness_v1` reuse as support kind accepted
- [ ] Post-accept annotation helper accepted as v0 strategy
