# Task Blueprint: Support Artifact Native Capture

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/_support.py` (新增 internal module)
  - `src/factpy_kernel/core/view/projector.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/derivation/candidates.py`
  - `src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-17_support-artifact-native-capture.audit.md](./2026-03-17_support-artifact-native-capture.audit.md)

## 1. Problem

当前 runtime traceability / explainability 讨论已经收口到一个更具体的阻塞点：对于 `Store.evaluate(..., mode="native")` 产出的 derivation candidate，系统已经有 `candidate_id`、`candidate_key`、`support_digest`、`support_kind` 这些 identity / support 槽位，但其中最关键的 `support_*` 仍然是哑值。

更根本的问题不是“缺一个 proof entry id”，而是 native evaluate 路径目前没有在执行当时捕获真实 proof witness：

- `project_view_facts(...)` 在投影时剥除了 `asrt_id`
- `evaluate_where(...)` 只返回变量绑定值，不返回 claim 身份
- `_builders.py` 在构建 candidate 时只能写入 `support_kind="none"` 和零 digest

如果不先解决这一层，后续的 `explain_ref`、proof tree、candidate-level explain handle、audit proof linking 都会停留在空壳状态。

## 2. Goals

- 为 native derivation 路径定义一个最小可用的 `SupportArtifact` 内部 schema。
- 引入 witness-capable projection / evaluation 通道，使 native where 匹配在执行当时能够保留 `pred` 原子对应的 assertion 身份。
- 让 native 路径产出的 `CandidateSet.support_digest` / `support_kind` 不再是哑值。
- 保持 `CandidateSet` 既有 identity 设计不变，即继续使用 `candidate_id` 作为 per-run handle，而不是新增 `proof_entry_id` 字段。
- 为后续 `rule_run trace`、service `explain_ref`、Top-K / multi-support 留出扩展边界。

## 3. Non-goals

- 不处理 `run_rule(...)` / `RuleRef` 的 execution trace；这应进入单独子蓝图。
- 不定义 service 层 `GET /explain/...` 端点或统一 `explain_ref` contract。
- 不引入 Rainbird-style certainty evaluator、condition weight、optional missing condition 语义。
- 不在本轮实现中打通 `souffle` / `problog` engine witness output。
- 不把 annotation prototype 并入正式 runtime contract。

## 4. Current Context

- 当前实现入口：
  - `Store.evaluate(...)` 通过 [src/factpy_kernel/core/store/_evaluate.py](../../../src/factpy_kernel/core/store/_evaluate.py) 的 native path 调用 `project_view_facts(...) -> evaluate_where(...) -> candidates_from_bindings(...)`。
  - [src/factpy_kernel/core/view/projector.py](../../../src/factpy_kernel/core/view/projector.py) 当前只投影 value tuple，不保留 `asrt_id`。
  - [src/factpy_kernel/core/store/_builders.py](../../../src/factpy_kernel/core/store/_builders.py) 当前在所有 native candidate 构建点写入哑值 `support_digest` / `support_kind`。
- 当前已知约束：
  - `CandidateSet` v2 identity 已经稳定，见 [src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md](../../../src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md)。
  - 当前 active blueprint 已明确：长期方向应是“现有结果 ID 解引用到真实 support artifact”，而不是先新增统一 proof id。
  - 当前 `evaluate_where(...)` 只能看见 value，不知道 claim 身份；因此“存 bindings 即可”不是充分方案。
- 当前相关历史蓝图：
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)

## 5. Proposed Shape

### 5.1 New Internal Module: `_support.py`

**不把 `SupportArtifact` 放进 `store/types.py`**——`types.py` 当前是轻量 type alias / TypedDict 层，`SupportArtifact` 是内部 carrier，应单独放：

```
src/factpy_kernel/core/store/_support.py
```

该 module 包含：

```python
@dataclass(frozen=True)
class ProjectedFact:
    asrt_id: str
    fact_tuple: tuple

@dataclass(frozen=True)
class BindingSupportCapture:
    binding: dict[str, Any]
    support_digest: str
    support_kind: str           # "native_binding_v1"

@dataclass(frozen=True)
class SupportArtifact:
    kind: str                   # "native_binding_v1"
    root_result_kind: str       # "fact" | "entity"
    binding: dict[str, Any]
    pred_witnesses: dict[str, list[str]]   # pred_atom_key -> [asrt_id, ...]
    non_fact_steps: list[dict]             # not/eq/ne/in/cmp/arithmetic 满足说明
    rule_refs: list                        # 本轮留空 []
```

以及规范化序列化 / digest helper（sha256 over canonical JSON, fields sorted）。

### 5.2 Witness-capable Projection (`projector.py`)

**不替换现有 `project_view_facts(...)`**，新增并行入口：

```python
def project_view_facts_with_witness(
    ledger, schema, pred_ids, ...
) -> dict[str, list[ProjectedFact]]:
    # pred_id -> [ProjectedFact(asrt_id, fact_tuple), ...]
```

- 只保留 `asrt_id`，不过早扩展 meta（本轮不加 `confidence`、`run_id` 等）
- 现有 `project_view_facts(...)` 调用面完全不动

### 5.3 Native Support Capture (`_evaluate.py`)

**第一轮不复制整套 join evaluator**；更稳的做法是"先求解，再 ground-back"：

1. 用现有 `evaluate_where(bindings_dict, where)` 得到 final bindings（纯值，现有接口）
2. 同时调用 `project_view_facts_with_witness(...)` 得到 witness projection
3. 对每个 final binding，**重新 ground** 每个正向 `pred` atom：用 binding 值去 witness projection 里反查 `asrt_id`
4. 收集 `pred_witnesses`（每个 pred atom 对应的 `asrt_id` 列表）
5. 对 `eq/ne/in/gt/ge/lt/le/not/arithmetic` atoms 生成最小 `non_fact_steps` 记录
6. 组装 `SupportArtifact`，调用 digest helper

这是"binding-grounded support summary"，**不是逐步 join trace**——但对 derivation candidate explain 已经足够，而且不侵入 `evaluate_where` 内部结构。

### 5.4 Candidate Construction And Dedup Policy (`_builders.py`)

**`_builders.py` 从"吃 binding"升级到"吃 `BindingSupportCapture`"**：

```python
# before:
candidates_from_bindings(bindings: list[dict], ...) -> list[CandidateSet]

# after:
candidates_from_bindings(rows: list[BindingSupportCapture], ...) -> list[CandidateSet]
```

- 构建 candidate 时直接写入真实 `support_digest`/`support_kind`

**单-support dedup policy（第一轮）**：
- 同一 `candidate_key` 可能由多个 binding 导出
- 先为每个 binding 生成规范化 `SupportArtifact`
- 按 `(candidate_key, support_digest)` 排序——每个 `candidate_key` 保留 `support_digest` 字典序最小的那条
- 这是 deterministic 且 audit-friendly 的策略，不是最终 multi-support 方案

**entity derivation 的特殊处理**：
- 一个 binding 会同时生成一个 entity candidate 和多个 role fact candidates
- 第一轮让它们共享同一个 `SupportArtifact`（因为它们本来就是同一次 binding 的不同 root result）

### 5.5 Internal Artifact Registry (`runtime.py`)

**`support_digest` 如果只算出来不存，仍然是半空壳**。

在 `Store` 上新增内部 registry：

```python
class Store:
    _support_artifacts: dict[str, SupportArtifact]  # digest -> artifact
```

- `evaluate(...)` 时把生成的 `SupportArtifact` 写入 `_support_artifacts`，key 是 digest
- 同一 session 内可解引用（`store._support_artifacts[digest]`）
- 第一轮不做：跨进程 durable storage、audit export、cross-process dereference

这先解决"同一 store/session 内可解引用"，后续 explain / audit 子蓝图再处理持久化。

### 5.6 Public Contract Position

本轮不新增 `CandidateSet.proof_entry_id`。

native derivation 路径继续沿用：

- `candidate_id` 作为 per-run explain handle
- `support_digest/support_kind` 作为 support artifact pointer（本轮真实化）

若后续要引入统一 `explain_ref`，应在 service 层完成，而不是先改 core candidate schema。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `CandidateSet` 的 `candidate_id/candidate_key` 语义不变。
  - 现有 `project_view_facts(...)` 纯值调用面不被破坏；新的 witness-capable 路径应并行引入。
  - native 路径先行；`souffle` / `problog` 不因本轮被重构。
  - 这一轮不把 proof tree、Top-K support、rule-run trace 混在一起。
- 明确不做的内容：
  - 不把 `support_digest` 直接解释成完整 proof tree snapshot。
  - 不在本轮把 assertion-level explain 统一成 `asrt_id` direct API。
  - 不引入 UI、shareable evidence page、NL explain。
- 兼容性约束：
  - evaluate / accept 的现有 round-trip 结构应继续成立。
  - service 文档若展示 `support_kind="none"` 示例，需要在实现时同步更新。

## 7. Acceptance

- [ ] native derivation 路径能在执行当时生成最小 `SupportArtifact`
- [ ] native `CandidateSet.support_digest` / `support_kind` 不再是哑值
- [ ] 没有新增 `CandidateSet` 的 proof id 字段
- [ ] `project_view_facts(...)` 现有纯值路径未被破坏
- [ ] 受影响模块 docs 已同步
- [ ] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

第一轮真实代码顺序：

1. **`src/factpy_kernel/core/store/_support.py`（新建）**
   - 定义 `ProjectedFact`、`BindingSupportCapture`、`SupportArtifact` dataclass
   - 实现规范化序列化 + digest helper（sha256 over canonical JSON with sorted fields）
   - 无外部依赖，可单独测试

2. **`src/factpy_kernel/core/view/projector.py`**
   - 新增 `project_view_facts_with_witness(...)` 返回 `dict[str, list[ProjectedFact]]`
   - 不改动现有 `project_view_facts(...)` 的签名或行为

3. **`src/factpy_kernel/core/store/_evaluate.py`**
   - 在 native derivation 路径新增 support capture helper
   - 策略：先跑现有 `evaluate_where(...)` 得 final bindings，再对每个 binding 用 witness projection ground-back 每个正向 `pred` atom，收集 `pred_witnesses` + `non_fact_steps`，组装 `SupportArtifact`
   - 现有 `evaluate_where(...)` 调用面不动

4. **`src/factpy_kernel/core/store/_builders.py`**
   - `candidates_from_bindings(...)` 从接收 `list[dict]` 改为接收 `list[BindingSupportCapture]`
   - 写入真实 `support_digest`/`support_kind`
   - 实现 single-support dedup policy：按 `(candidate_key, support_digest)` 排序，每个 `candidate_key` 保留最小 digest
   - entity derivation：entity candidate 和 role fact candidates 共享同一 `SupportArtifact`

5. **`src/factpy_kernel/core/store/runtime.py`**
   - `Store` 上新增 `_support_artifacts: dict[str, SupportArtifact]`
   - `evaluate(...)` 完成后把本次产出的 `SupportArtifact` 按 digest 写入 registry

6. **文档同步**
   - `src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md`：更新 `support_kind` 语义，说明 `"native_binding_v1"` 含义
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`：移除/更新展示 `support_kind="none"` 的示例

**第一轮明确不做：**
- 不碰 `run_rule` / `RuleRef`
- 不碰 `souffle` / `problog` witness output
- 不上 Top-K / multi-support
- 不定义 service `/explain/...` 端点
- 不做 Rainbird-style salience / optional missing condition
- 不做 durable cross-process artifact storage

## 9. Docs To Update

- `src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md`（`support_kind` 语义更新）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（移除 `support_kind="none"` 示例）
- 相关模块 `docs/README.md`（如果本轮新增模块级说明）
- `docs/README.md`（仅在新增持久 docs 入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `src/factpy_kernel/core/store/_support.py`，定义 `SupportArtifact` / `BindingSupportCapture` / `ProjectedFact` 与稳定 digest helper
  - `src/factpy_kernel/core/view/projector.py` 新增 `project_view_facts_with_witness(...)`，在保留原纯值 projection 的同时补上 `asrt_id` 级 witness 投影
  - native `Store.evaluate(..., mode="native")` 现已捕获 evaluate-time support summary，产出真实 `support_digest` 并写入 `support_kind="native_binding_v1"`
  - `_builders.py` 已升级为优先消费 `BindingSupportCapture`，为 native rows 写入真实 `support_digest` / `support_kind`，同时保留 `bindings=` 兼容入口
  - `Store` 已新增 in-process `_support_artifacts` registry，为后续 readback 提供 support dereference 基座
  - `CANDIDATE_PROTOCOL_V2.md` 与 `service/docs/03_runtime_queries_views.md` 已同步更新 `native_binding_v1` 语义与 `mode="native"` 示例
- 与 blueprint 不同的地方：
  - capture slice 本身没有直接暴露 public explain/query surface；`Store.explain_support(...)` 被拆到后续 `support-artifact-readback` 子蓝图处理
  - 第一轮明确接受了双重 projection 和 OR-of-AND 空 witness 的已知限制，没有在本蓝图内继续扩大 scope 去追求单遍精确 trace
- 为什么会有这些调整：
  - 将 readback 单独拆出后，capture blueprint 可以保持“执行期捕获 + digest 写入 + registry 基座”这一更窄、更稳定的实现边界
  - 现有 `evaluate_where(...)` 和 projection 调用面需要保持兼容，先接受保守 capture 方案比同步重写 evaluator 更稳
- 归档说明：
  - 后续的 `support-artifact-readback`、`run-rule-trace-capture` 与 `runtime-service-explain-readback` 已分别落地，native capture 这一切片本身已完成并适合归档；后续若继续推进 durability，应转入独立蓝图而不是在本文件中扩写
