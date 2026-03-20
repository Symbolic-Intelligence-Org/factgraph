# Task Blueprint: Engine Partial Witness — Adapter Contract

- Status: scoped
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/__init__.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/types.py`
  - `src/factpy_kernel/service/runtime_v1.py`
- Related Docs:
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_engine-witness-parity.md](../archive/2026-03-18_engine-witness-parity.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-20_engine-partial-witness-adapter-contract.audit.md](./2026-03-20_engine-partial-witness-adapter-contract.audit.md)

## 1. Problem

Engine witness parity 的第一轮（[2026-03-18 归档](../archive/2026-03-18_engine-witness-parity.md)）已经把 engine candidate 从"静默伪装"提升到"显式 degraded explain"。当前 engine candidate 具备：

- `support_kind="engine_no_witness_v1"`
- `witness_status="degraded"` 在 explain 和 tree surface 上
- degraded tree 是合法 surface，不是错误

但 degraded explain 本质上仍是"有效 candidate，零 witness"——consumer 知道结论存在，但无法看到任何支撑证据。

下一步自然要问：**engine 能否从"零 witness"推进到"partial witness"？**

这个问题的关键阻塞点不在 carrier 或 service 层，而在 **adapter 层**：

- Souffle adapter 当前通过 TSV output 只返回 binding tuples，丢弃了所有 provenance
- ProbLog adapter 当前只返回概率结果，无 derivation 路径
- `EngineEvaluatorFn: TypeAlias = Callable[..., list[CandidateSet]]` 返回类型中没有 witness 通道

信息在 adapter 出口处就消失了——这不是下游消费层能补回来的。

因此本蓝图的问题是 **adapter / evaluator contract 层面的**：engine 是否能、以及应如何把 partial witness 信息传递出来。

## 2. Goals

- 判断哪个 engine（souffle / problog / 两者皆不）最 feasible 作为 first-round partial witness 候选
- 明确最小 witness carrier 是 native `SupportArtifact` 的子集还是平行 schema
- 明确 `EngineEvaluatorFn` 返回 contract 是否需要扩展
- 明确 first-round consumer surface 覆盖范围
- 明确 unsupported engines 如何保持现有 degraded contract

## 3. Non-goals

- 不承诺 full native parity（完整 `pred_witnesses` + `non_fact_steps` + recursive proof edges）
- 不重做 ProbLog proof tree 集成
- 不把 salience / impact / optional conditions 混进来
- 不要求 first-round 覆盖所有 engine
- 不重开 native `SupportArtifact` schema
- 不在本轮讨论 engine witness 对 tree NL explain / narrative 的影响

## 4. Current Context

### 4.1 Engine adapter 当前输出

**Souffle** (`adapters/souffle/engine_eval.py`):

```
evaluate_store_engine(store, ...) -> list[CandidateSet]
  -> _run_query_and_read_bindings(...)
    -> Souffle CLI 执行 → TSV stdout
    -> _read_query_bindings(...)
    -> 返回 list[dict[str, Any]] binding rows
```

- Souffle engine **内部知道**哪些 input tuples 匹配了哪些 rules
- 但 TSV binding output 只保留最终 variable→value mapping
- Provenance 在 TSV 序列化时全部丢弃

**ProbLog** (`adapters/problog/__init__.py`):

```
evaluate_problog(store, ...) -> list[CandidateSet]
  -> ProbLog CLI 执行 → raw stdout
  -> parse_problog_output(...)
  -> 返回概率结果，重建 CandidateSet
```

- ProbLog 本身有 proof tree 能力（`problog` library 支持 `explain` mode）
- 但当前 adapter 只消费概率输出，不请求 derivation path
- 集成 proof tree 需要更深的 ProbLog API 调用

### 4.2 `EngineEvaluatorFn` 当前 contract

```python
# src/factpy_kernel/core/store/types.py
EngineEvaluatorFn: TypeAlias = Callable[..., list[CandidateSet]]
```

- 返回类型只有 `list[CandidateSet]`
- 没有 witness / provenance sidecar 通道
- `CandidateSet` 本身也不携带 witness payload——witness 是通过 `SupportArtifact` 在 `Store` 侧独立注册的

### 4.3 Native witness 的对照

Native path（`evaluate_store` → `_evaluate.py`）的 witness capture 流程：

1. `project_view_facts_with_witness()` 保留 `asrt_id` 与 value 元组的对应关系
2. where evaluator 在匹配时记录 `pred_witnesses` + `non_fact_steps`
3. `SupportArtifact` 被构建并注册到 `Store`
4. `support_digest` + `support_kind="native_binding_v1"` 写入 candidate backref

Engine 若要 partial witness，至少需要把步骤 1-3 的某个子集在 adapter 侧实现。

### 4.4 已归档的 engine witness parity 第一轮

[2026-03-18_engine-witness-parity.md](../archive/2026-03-18_engine-witness-parity.md) 完成了：

- `ENGINE_NO_WITNESS_KIND` + `_DEGRADED_SUPPORT_KINDS`
- `Store.get_candidate_support_kind()` 索引
- Service 层 degraded explain 语义
- `build_degraded_candidate_evidence_tree()` tree surface
- 所有 acceptance criteria 已勾掉

当前蓝图是第一轮的自然延续。

## 5. Proposed Shape

### 5.1 Positioning

本蓝图是 **scoping / adapter-contract decision draft**，不是 implementation blueprint。

它要回答的核心问题是 adapter / evaluator contract 层面的可行性和最小变更，而不是 tree surface 或 UI。

### 5.2 Feasibility Assessment: Three Approaches

在冻结方向之前，评估了三种 Souffle witness 接入方案：

| 方案 | 原理 | 可行性 | 风险 |
|---|---|---|---|
| **A: `-t explain` 交互模式** | 启动 Souffle REPL，per-tuple 发 `explain` 命令，`format json` 输出 | ⚠️ 勉强可行 | REPL 交互无批量模式；interpreted-only（无 `-c`）；per-tuple 慢；stdin piping 脆弱 |
| **B: `-t none` 注解模式** | 内部标注 tuple（rule number + proof height），不暴露完整 proof tree | ❌ 不够用 | 只拿到 rule 编号，拿不到 input tuple identity |
| **C: Datalog rule rewriting** | 修改 view 生成，在 head 中额外投射 `asrt_id`，输出自带 witness | ✅ 最可行 | 需改 view gen + where compile；witness 列数随 fact atom 数增长 |

**选定方案 C — Datalog Rule Rewriting。** 核心思路：

当前 view rule（丢弃 asrt_id）：
```
.decl p_user_name(E:symbol, V0:symbol)
p_user_name(E, V0) :- claim(A,"user:name",E,_), active(A), claim_arg(A,"0",V0,_).
```

witness-aware view rule（保留 asrt_id）：
```
.decl p_user_name_w(E:symbol, V0:symbol, WA:symbol)
p_user_name_w(E, V0, A) :- claim(A,"user:name",E,_), active(A), claim_arg(A,"0",V0,_).
```

query rule 穿透 witness 列：
```
.decl query__xxx(C0:symbol, C1:symbol, WA0:symbol, WA1:symbol)
query__xxx(C0, C1, WA0, WA1) :- p_user_name_w("e1", C0, WA0), p_user_status_w("e1", C1, WA1).
```

方案 C 的优势：
- 继续用 `subprocess.run()` — 不需要 REPL 交互
- 兼容 compiled 模式 — 不受 interpreted-only 限制
- asrt_id 映射直接 — 在 TSV 输出中，不需要反查
- 性能与当前持平 — 只多几列输出

**重要命名澄清**：这不是接 Soufflé 官方 provenance proof tree，而是 adapter-level witness sidecar via rule rewriting。不应混淆 "proof tree provenance" 与 "witness-bearing query rows"。

### 5.3 Freeze Decisions

**Q1: first-round 先做哪个 engine → Souffle-only**

Souffle 通过 Datalog rule rewriting 可以在不依赖 `-t explain` 交互模式的前提下产出 assertion witness。ProbLog 需要 CLI→library API 迁移，成本更高，deferred。

**Q2: 最小 witness carrier → native `SupportArtifact` 受限子集**

| SupportArtifact 字段 | Souffle 能否提供 | 说明 |
|---|---|---|
| `binding` | ✅ | 已有 |
| `pred_witnesses` | ✅ | 通过 `_w` 变体的 witness 列 |
| `non_fact_steps` | ⚠️ minimal | Souffle 输出只含满足的 tuple，可标记 `all_satisfied` |
| `rule_ref_edges` | ❌ | engine 路径不适用，空 |
| `root_result_kind` | ✅ | 从 schema 已知 |

`support_kind` 必须是新的 witness-bearing engine kind：**`souffle_witness_v1`**。不伪装成 `native_binding_v1`。后续 runtime/audit/tree 消费侧应改为"支持一组 witness-bearing support kinds"，而不是硬编码只接受 `native_binding_v1`。

**Q3: `EngineEvaluatorFn` 返回 contract → prefer unchanged, subject to registration viability**

倾向不扩展 `EngineEvaluatorFn` 返回类型。adapter 内部在构建 `CandidateSet` 之前，先注册 witness 到 Store。

但这意味着 adapter 需要直接调用 `store._remember_support_artifact(...)` 或等价 API——这是有意的内部耦合。blueprint 显式承认此 tradeoff：如果 adapter-side Store registration 在实现时被证明不可维护，则应回到扩展返回类型方案。

**Q4: first-round consumer surface → runtime-only**

first-round 只覆盖 runtime live path：
- `POST /queries/explain`（`explain_ref(kind="candidate")`）
- `POST /queries/explain-tree`（`explain_tree(kind="candidate")`）

audit / static deferred。理由：
- 最大风险在 adapter contract，不在离线消费面
- runtime 最快验证 witness 列穿透稳定性、support_digest 注册、tree shape
- audit/static 在 runtime 稳定后可顺水推舟补上

**Q5: unsupported engines → ProbLog 继续 `engine_no_witness_v1`**

ProbLog 和其他未支持 engine 继续返回 `engine_no_witness_v1` + degraded tree。不需要新的 `support_kind` 来区分"从未支持"与"支持但未捕获"——当前只有两种状态：witness-bearing 或 degraded。

### 5.4 Implementation Scope

变更范围估算：

| 文件 | 变更 |
|---|---|
| `souffle_view_gen.py` | 新增 `_w` witness 变体 view rules；SINGLE cardinality 链穿透 asrt_id |
| `where_compile.py` | query rule 中 fact atoms 使用 `_w` 变体，穿透 witness 列 |
| `engine_eval.py` | TSV 解析分离 binding columns / witness columns；构建 `SupportArtifact` |
| `_builders.py` | Souffle witness path 不再走 `_coerce_binding_rows(bindings=...)`degraded fallback |
| `_evaluate.py` | Souffle 返回后注册真实 `SupportArtifact` |
| `_support.py` | `souffle_witness_v1` 加入 known support kinds（不在 `_DEGRADED_SUPPORT_KINDS` 中） |
| `runtime_v1.py` | explain / tree 路由改为按"witness-bearing support kinds"判定，不硬编码 `native_binding_v1` |

复杂度注意点：
- SINGLE cardinality preds 有 `cand__` → `max_ts__` → `chosen_asrt__` 链，asrt_id 需穿透
- witness 列数 = WHERE 中 fact atom 数，对典型查询（2-5 个）可控
- `in` / `not` / comparison atoms 无 asrt_id，与 native 的 `non_fact_steps` 对应

### 5.5 ProbLog Deferral

ProbLog partial witness deferred 到后续轮次。原因：
- 当前 adapter 使用 CLI 调用，不是 library API
- ProbLog 的 proof tree 需要通过 Python API 的 `explain` mode
- 从 CLI → library API 的迁移本身是独立工作项

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 现有 degraded explain contract 不回退
  - native witness path 不受影响
  - unsupported engine 继续返回 `engine_no_witness_v1`
- 明确不做的内容：
  - 不重设计 native `SupportArtifact` schema 来适配 engine
  - 不把 ProbLog proof tree 集成作为 first-round 目标
  - 不把 tree NL explain / narrative 的 engine 适配混进来
- 兼容性约束：
  - 若扩展 `EngineEvaluatorFn`，必须向后兼容（不破坏现有 adapter 注册）
  - 若引入新 `support_kind`，必须与 `_DEGRADED_SUPPORT_KINDS` 和现有 service 降级逻辑兼容

## 7. Acceptance

- [x] 已判断 first-round feasible → Souffle-only via Datalog rule rewriting（方案 C）
- [x] 已冻结最小 witness carrier → native `SupportArtifact` 受限子集，`support_kind="souffle_witness_v1"`
- [x] 已明确 `EngineEvaluatorFn` → prefer unchanged, subject to Store registration viability
- [x] 已明确 first-round consumer surface → runtime-only（explain + explain-tree）
- [x] 已明确 unsupported engine → ProbLog 继续 `engine_no_witness_v1`
- [x] 已明确下一步 → 可开 implementation blueprint

## 8. Implementation Plan

1. `souffle_view_gen.py`：生成 `_w` witness 变体 view rules
2. `where_compile.py`：query rule 穿透 witness 列
3. `engine_eval.py`：TSV 解析分离 binding / witness 列
4. `_builders.py` / `_evaluate.py`：Souffle witness path 构建并注册 `SupportArtifact`
5. `_support.py`：`souffle_witness_v1` 加入 known support kinds
6. `runtime_v1.py`：explain / tree 路由改为 witness-bearing kind set 判定
7. targeted tests：Souffle witness capture + runtime explain/tree shape
8. docs sync
9. 归档

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（若 engine witness contract 成为正式方向）
- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`（若 souffle witness 进入 first-round）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若 runtime explain surface 变化）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
