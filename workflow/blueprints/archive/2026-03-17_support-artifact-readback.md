# Task Blueprint: Support Artifact Readback

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_explain_support.py` (新增 internal helper module)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_support-artifact-native-capture.md](./2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
- Audit Log:
  - [2026-03-17_support-artifact-readback.audit.md](./2026-03-17_support-artifact-readback.audit.md)

## 1. Problem

父蓝图 `support-artifact-native-capture` 完成后，`Store._support_artifacts` registry 已经可以在同一 session 内保存真实的 `SupportArtifact`，`CandidateSet` 也携带了真实的 `support_digest` 和 `support_kind="native_binding_v1"`。

然而，从调用者视角来看，这条链路仍然是断的：

- `store.evaluate(...)` 返回的 `CandidateSet` 含有 `support_digest`
- 但目前没有任何公开方法或 query helper 允许调用者把 `support_digest` 解引用成可读的 support breakdown
- `store._support_artifacts` 是内部 dict，调用者不应直接访问私有属性
- 因此 `candidate_id → support_digest → SupportArtifact` 的"闭环"在 query/explain 层面仍然未被打通

这意味着即使 native derivation 路径已经捕获了真实 witness，外部调用者仍然无法观察它。

## 2. Goals

- 新增一个内部 query helper，接受 `(store, support_digest: str)` 并返回 `SupportArtifact` 的结构化 dict 表示。
- 在 `Store` 上新增公开方法 `explain_support(support_digest: str) -> dict | None`，作为调用者的唯一解引用入口。
- 打通调用者侧的完整观察路径：`evaluate(...)` → 拿到 `CandidateSet.support_digest` → 调用 `store.explain_support(support_digest)` → 得到 witness / binding breakdown。
- 保持 `SupportArtifact` 内部 schema 不变；readback 层只负责序列化为 dict，不重新定义 support 结构。

## 3. Non-goals

- 不修改 service 层的 `explain_ref` contract 或任何 HTTP / API 接口。
- 不处理 `run_rule / RuleRef` 的 execution trace。
- 不引入 `souffle` / `problog` engine witness output。
- 不实现 Multi-support / Top-K provenance 的聚合视图。
- 不做 durable cross-process artifact storage 或 audit export。
- 不在本轮定义 `candidate_id` → `support_digest` 的反向查找；调用者应从 `CandidateSet` 直接取 `support_digest`。

## 4. Current Context

- 当前实现入口：
  - 父蓝图完成后，`Store._support_artifacts: dict[str, SupportArtifact]` 已在 `src/factpy_kernel/core/store/runtime.py` 中存在，键为 `support_digest`。
  - `Store._lookup_support_artifact(support_digest: str) -> SupportArtifact | None` 已作为内部 lookup 方法实现。
  - `CandidateSet` 在 native derivation 路径下携带真实 `support_digest` 和 `support_kind="native_binding_v1"`。
  - `SupportArtifact` 的 schema 定义位于 `src/factpy_kernel/core/store/_support.py`，包含 `kind`、`root_result_kind`、`binding`、`pred_witnesses`、`non_fact_steps`、`rule_refs` 字段。
- 当前已知约束：
  - `_support_artifacts` 是私有 dict，外部不应直接访问。
  - `_lookup_support_artifact` 是内部方法，不是公开 API；需要在其之上建立公开接口。
  - 当前没有任何 `Store` 公开方法接受 `support_digest` 作为参数。
  - `SupportArtifact` 是 frozen dataclass，需要序列化逻辑才能变成调用者可用的 dict。
- 当前相关历史蓝图：
  - [2026-03-17_support-artifact-native-capture.md](./2026-03-17_support-artifact-native-capture.md)（父蓝图，已完成 registry 和 digest 写入）
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)

## 5. Proposed Shape

### 5.1 New Internal Helper: `_explain_support.py`

新建 `src/factpy_kernel/core/store/_explain_support.py`，职责单一：把 `SupportArtifact` 实例序列化为调用者可使用的 dict。

该 module 应包含一个 helper 函数，签名形如：

```python
def render_support_artifact(artifact: SupportArtifact) -> dict:
    ...
```

返回的 dict 结构应直接复用 `_support.py` 中现有的 JSON-friendly 形状，不在 readback 层再定义第二套 schema。

```python
{
    "kind": "native_binding_v1",
    "root_result_kind": "fact" | "entity",
    "binding": [["$x", "Alice"], ["$y", 42]],
    "pred_witnesses": [
        {"pred_atom_key": "<pred_atom_key>", "asrt_ids": ["<asrt_id>", ...]}
    ],
    "non_fact_steps": [ ... ],       # 原样返回 non-fact 满足说明
    "rule_refs": []                  # 本轮为空列表
}
```

`binding` 保持 `list-of-pairs`，与 `support_artifact_to_dict(...)` 的 canonical/JSON-friendly 形状一致；第一轮不在 `render_support_artifact(...)` 里额外转成 `dict`。

### 5.2 Public Method: `Store.explain_support`

在 `src/factpy_kernel/core/store/runtime.py` 的 `Store` 类上新增：

```python
def explain_support(self, support_digest: str) -> dict | None:
    artifact = self._lookup_support_artifact(support_digest)
    if artifact is None:
        return None
    return render_support_artifact(artifact)
```

- 若 digest 在 registry 中不存在（例如 `support_kind="none"` 的旧候选，或跨 session 的 digest），返回 `None`。
- 不抛出异常；未找到视为合法的"未知"状态，由调用者决定如何处理。
- 方法应是纯读取操作，不修改任何 store 状态。

### 5.3 Caller Usage Pattern（规范性说明，非代码）

完整闭环的调用侧使用模式：

```
candidate_set = store.evaluate(subject, spec, ...)
for candidate in candidate_set.candidates:
    digest = candidate.support_digest
    breakdown = store.explain_support(digest)
    # breakdown 为 None 表示无 support（如 support_kind="none" 的候选）
    # breakdown 为 dict 表示可观察的 witness breakdown
```

这是本 blueprint 要达成的目标状态，不是已实现行为。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `_support_artifacts` 和 `_lookup_support_artifact` 继续保持内部私有；`explain_support` 是唯一对外入口。
  - `SupportArtifact` dataclass schema 在本轮不得改动；readback 层只做序列化。
  - `CandidateSet` 的 `candidate_id` / `candidate_key` / `support_digest` / `support_kind` 字段语义不变。
  - `evaluate(...)` 的返回类型和行为不变；`explain_support` 是独立的后续调用，不嵌入 evaluate 返回值。
- 明确不做的内容：
  - 不把 `explain_support` 的结果内联进 `CandidateSet` 或 candidate 对象。
  - 不新增 `candidate_id → support_digest` 反向索引；调用者从 `CandidateSet` 直接取 digest。
  - 不在本轮处理 `support_kind` 不是 `"native_binding_v1"` 的情况（直接返回 `None` 即可）。
  - 不在本轮做 readback 结果的 validation / schema enforcement。
- 兼容性约束：
  - `evaluate / accept` 的现有 round-trip 结构应继续成立。
  - `explain_support` 对 non-native candidate（`support_kind="none"`）必须返回 `None`，不得抛出异常，以保持向前兼容。

## 7. Acceptance

- [ ] `Store.explain_support(support_digest)` 公开方法存在且可被外部调用
- [ ] 对 native derivation 产出的真实 `support_digest`，`explain_support` 返回非 None 的 dict，包含 `kind`、`binding`、`pred_witnesses`、`non_fact_steps` 字段
- [ ] 对不存在的 digest 或 `support_kind="none"` 的旧候选，`explain_support` 返回 `None` 而非抛出异常
- [ ] `Store._support_artifacts` 和 `_lookup_support_artifact` 仍为内部私有，未被公开导出
- [ ] `SupportArtifact` dataclass 定义未被修改
- [ ] `evaluate(...)` 的现有返回类型和行为未被改变
- [ ] 受影响模块 docs 已同步
- [ ] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. **`src/factpy_kernel/core/store/_explain_support.py`（新建）**
   - 实现 `render_support_artifact(artifact: SupportArtifact) -> dict`
   - 第一轮直接委托给 `_support.py` 中已有的 `support_artifact_to_dict(...)`
   - 保持 `binding` 为 `list-of-pairs`，不在 readback 层新增第二套 dict shape
   - 无外部依赖，只依赖 `_support.py` 中的 `SupportArtifact`，可单独测试

2. **`src/factpy_kernel/core/store/runtime.py`**
   - 在 `Store` 类上新增 `explain_support(self, support_digest: str) -> dict | None`
   - 内部调用 `self._lookup_support_artifact(support_digest)` 再调用 `render_support_artifact(...)`
   - 确认 `None` 返回路径覆盖：digest 不存在、artifact 为 None 两种情况均返回 `None`

3. **文档同步**
   - `src/factpy_kernel/core/store/` 模块级 docs（如果存在）：更新说明 `explain_support` 的作用和调用模式
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（如适用）：补充 `explain_support` 的调用侧使用示例
   - 新增 `_explain_support.py` 的模块说明（如模块目录有 README）

**本轮明确不做：**
- 不碰 `run_rule` / `RuleRef`
- 不碰 `souffle` / `problog` witness output
- 不上 Multi-support / Top-K
- 不定义 service `/explain/...` 端点
- 不做 durable cross-process artifact storage

## 9. Docs To Update

- `src/factpy_kernel/core/store/` 模块级 docs（如存在，补充 `explain_support` 说明）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（如适用，补充调用侧示例）
- `docs/README.md`（仅在新增持久 docs 入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `src/factpy_kernel/core/store/_explain_support.py`，其中 `render_support_artifact(...)` 作为 readback thin wrapper 直接复用 `support_artifact_to_dict(...)`
  - `Store` 新增 `explain_support(support_digest: str) -> dict[str, Any] | None`
  - readback shape 明确保持 canonical JSON-friendly 形状，其中 `binding` 为 `list-of-pairs`，`pred_witnesses` 为 `list[dict]`
- 与 blueprint 不同的地方：
  - 无功能性偏移；仅将 §5.1 中原本尚未完全收口的 shape 示例同步为实际实现格式
- 为什么会有这些调整：
  - 需要避免 readback 文档继续保留与 `_support.py` 真实输出不一致的 shape 示例
- 归档说明：
  - 本轮已实现并完成最小验证；其职责边界已被后续 service/readback 与 durable-storage 蓝图继续引用，因此本文件现作为已完成切片归档保存，而不再留在 active 目录
