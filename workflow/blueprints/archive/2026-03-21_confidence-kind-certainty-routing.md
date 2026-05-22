# Task Blueprint: certainty-confidence-kind-resolver-v1

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_certainty_materializer.py`
  - `src/factpy_kernel/service/_certainty_service.py`
  - `src/factpy_kernel/service/runtime_v1.py`
- Related Docs:
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [test: e2e certainty compatibility (d5a9ca0)](../../../src/factpy_kernel/tests/test_certainty_explain_contracts.py)
- Audit Log:
  - [2026-03-21_confidence-kind-certainty-routing.audit.md](./2026-03-21_confidence-kind-certainty-routing.audit.md)

## 1. Problem

端到端测试 (`d5a9ca0`) 已证明真实 native evaluate 输出与 certainty 链路无 structural gap。但当前没有任何 production code path 把 candidate 标记为 `confidence_kind="certainty"`。所有 certainty 测试都依赖手工 patch `_candidate_confidence_kind_index`。

post-patch 方案（旧版 blueprint）被判定为权宜之计：
- builder 创建 `"none"` 后立刻 replace 成 `"certainty"` 不是好 pattern
- duck typing 替代 protocol 脆弱
- eligibility 逻辑重复（routing 和 materializer 各写一套）
- SDK/service 行为不一致长期会反咬

本 blueprint 建立 certainty lane 的 **producer contract**：resolver 架构 + 共享 eligibility。

## 2. Goals

- 建立 `ConfidenceKindResolver` protocol，可扩展到 probability 但本轮只实现 certainty
- builder 在创建 CandidateSet 时通过 resolver 确定 `confidence_kind`（不是创建后 patch）
- routing 和 materializer 共享同一份 eligibility helper
- service 注入 resolver（有 rule-spec reader），SDK 当前不注入（保持 `"none"`）——SDK parity deferred，不是因为 SDK 特殊，而是因为 SDK 当前没有 `RuleSpecReader` 实现。core 架构预留统一 seam，SDK 将来可接入
- 端到端测试零 patch 验证

## 3. Non-goals

- 不实现 `confidence_kind="probability"` 的 resolver（只预留 slot）
- 不改 `CertaintySummary` / ranking / narrative / NL / audit / static
- 不改 `confidence` scalar 本身
- 不改 Souffle / ProbLog adapter 的 confidence_kind 行为
- 不做通用 confidence 大框架

## 4. Current Context

- 当前调用链：
  - `runtime_v1.py::evaluate_runtime_derivation` 调用 `session.store.evaluate(..., registry=active_registry)`
  - `Store.evaluate()` in `runtime.py` line 211 直接委托 `evaluate_store(self, ..., registry=registry)`
  - `evaluate_store()` in `_evaluate.py` 调用 `candidates_from_bindings()`，`confidence_kind="none"` hardcoded
  - 当前传给 evaluate 的 `registry` 是 `RuleRegistry`（core rules），**不是** `FileAuthoringRegistry`（authoring）
  - `FileAuthoringRegistry` 只在 certainty service（`_certainty_service.py`）中使用，用于查 condition_weights
- 当前 candidate 创建：
  - `candidates_from_bindings()` / `entity_candidates_from_bindings()` in `_builders.py`
  - SupportArtifact 在 candidate 创建前已 remember（可通过 `store._lookup_support_artifact(digest)` 查回）
  - `SupportArtifact.rule_ref_edges: tuple[RuleRefEdge, ...]` 有完整的 child rule 信息
- 当前 eligibility 分散在两处：
  - `_certainty_service.py::_lookup_condition_weights_for_candidate` — 检查 support artifact level（rule_ref_edges）+ tree level（`extract_single_referenced_support_tree`）
  - `_certainty_materializer.py::materialize_certainty_summary` — 检查 tree level（`extract_single_referenced_support_tree`）
- SDK 调用链：
  - `SDKStore.evaluate()` 也调用 `evaluate_store(..., registry=None)`
  - SDK 当前没有 `RuleSpecReader` 实现

## 5. Proposed Shape

### 5.1 Protocol: `RuleSpecReader`

新建 `src/factpy_kernel/core/store/_confidence_kind_resolver.py`：

```python
from typing import Any, Protocol

class RuleSpecReader(Protocol):
    def read_rule_spec(self, rule_id: str, version: str) -> dict[str, Any] | None: ...
```

这是 resolver 依赖的最小接口。`FileAuthoringRegistry` 天然满足。SDK 若将来需要 certainty routing，只需让其 registry 实现此接口。

### 5.2 Shared eligibility: `check_certainty_artifact_eligibility`

同一文件中：

```python
def check_certainty_artifact_eligibility(
    artifact: SupportArtifact,
    child_artifact_lookup: Callable[[str], SupportArtifact | None],
) -> RuleRefEdge | None:
```

输入：top-level support artifact + child lookup callable。

逻辑：
1. `artifact.rule_ref_edges` 不恰好 1 条 → `None`
2. 该 edge 的 `child_support_digest is None`（unresolved） → `None`
3. child artifact 查回后，若 `child_artifact.rule_ref_edges` 非空 → `None`（nested，tree eligibility 不通过）
4. 全通过 → 返回该 `RuleRefEdge`

返回 `RuleRefEdge` 而非 bool，因为 caller 需要 `rule_ref_id` / `rule_ref_version` 来查 rule payload。

**Consumer 1**：routing resolver（§5.3）
**Consumer 2**：`_certainty_service.py::_lookup_condition_weights_for_candidate` 重构后使用此 helper，替换现有手写 eligibility 逻辑 + `extract_single_referenced_support_tree` 调用

### 5.3 Resolver: `CertaintyConfidenceKindResolver`

```python
class ConfidenceKindResolver(Protocol):
    def resolve(
        self,
        support_digest: str,
        support_kind: str,
        artifact_lookup: Callable[[str], SupportArtifact | None],
    ) -> str:
        """Return confidence_kind for this candidate's support."""
        ...

class CertaintyConfidenceKindResolver:
    def __init__(self, rule_spec_reader: RuleSpecReader) -> None:
        self._reader = rule_spec_reader

    def resolve(
        self,
        support_digest: str,
        support_kind: str,
        artifact_lookup: Callable[[str], SupportArtifact | None],
    ) -> str:
        artifact = artifact_lookup(support_digest)
        if artifact is None:
            return "none"
        edge = check_certainty_artifact_eligibility(artifact, artifact_lookup)
        if edge is None:
            return "none"
        payload = self._reader.read_rule_spec(edge.rule_ref_id, edge.rule_ref_version)
        if not isinstance(payload, dict):
            return "none"
        cw = payload.get("condition_weights")
        if not isinstance(cw, dict) or not cw:
            return "none"
        return "certainty"
```

### 5.4 Builder 接入

`candidates_from_bindings()` 和 `entity_candidates_from_bindings()` 新增 keyword-only 参数：

```python
def candidates_from_bindings(
    store: Any,
    *,
    ...,
    confidence_kind_resolver: ConfidenceKindResolver | None = None,
) -> list[CandidateSet]:
```

在创建 candidate 时：

```python
resolved_ck = "none"
if confidence_kind_resolver is not None:
    resolved_ck = confidence_kind_resolver.resolve(
        row.support_digest,
        row.support_kind,
        store._lookup_support_artifact,
    )

candidate = make_candidate(
    ...,
    confidence_kind=resolved_ck,
)
```

无 resolver 时行为完全不变（`"none"`）。

### 5.5 Evaluate 接入（三层传递）

注入链：`runtime_v1.py → Store.evaluate → evaluate_store → builders`

**`Store.evaluate()`** in `runtime.py` 新增 keyword-only：

```python
def evaluate(
    self,
    ...,
    confidence_kind_resolver: "ConfidenceKindResolver | None" = None,
) -> list[CandidateSet]:
    return evaluate_store(
        self, ...,
        confidence_kind_resolver=confidence_kind_resolver,
    )
```

**`evaluate_store()`** in `_evaluate.py` 新增 keyword-only：

```python
def evaluate_store(
    store: Any,
    *,
    ...,
    confidence_kind_resolver: Any | None = None,
) -> list[CandidateSet]:
```

传给 `candidates_from_bindings(..., confidence_kind_resolver=confidence_kind_resolver)`。

注意：`evaluate_store` 的 type hint 用 `Any | None` 而非 `ConfidenceKindResolver | None`，避免 `_evaluate.py` import `_confidence_kind_resolver.py`（保持现有 import 面不扩大）。实际类型由 caller 保证。

### 5.6 Service 注入

`runtime_v1.py::evaluate_runtime_derivation` 在调用 `session.store.evaluate(...)` 前构建 resolver：

```python
from factpy_kernel.core.store._confidence_kind_resolver import CertaintyConfidenceKindResolver

resolver = None
if registry_root is not None:
    resolver = CertaintyConfidenceKindResolver(
        FileAuthoringRegistry(registry_root),
    )
candidates = session.store.evaluate(
    ...,
    confidence_kind_resolver=resolver,
)
```

`FileAuthoringRegistry` 既满足 `RuleSpecReader` protocol（有 `read_rule_spec`），也是 certainty service 查 condition_weights 的同一类型。

### 5.7 SDK 路径

`SDKStore.evaluate()` 调用 `evaluate_store(..., confidence_kind_resolver=None)`，保持 `"none"`。SDK parity deferred：将来若 SDK 需要 certainty routing，只需让 SDK registry 实现 `RuleSpecReader` 并构建 resolver。

### 5.8 `_certainty_service.py` 重构

`_lookup_condition_weights_for_candidate` 的 eligibility 部分替换为调用 `check_certainty_artifact_eligibility`：

```python
from factpy_kernel.core.store._confidence_kind_resolver import check_certainty_artifact_eligibility

def _lookup_condition_weights_for_candidate(store, candidate_id, tree_dict, *, registry_root):
    support_digest = store.get_candidate_support_digest(candidate_id)
    if support_digest is None:
        return None
    artifact = store._lookup_support_artifact(support_digest)
    if artifact is None:
        return None
    edge = check_certainty_artifact_eligibility(artifact, store._lookup_support_artifact)
    if edge is None:
        return None
    # ... existing condition_weights lookup from registry ...
```

`extract_single_referenced_support_tree` 调用从此函数中移除——eligibility 已由共享 helper 保证。`materialize_certainty_summary` 保留其 tree-level `extract_single_referenced_support_tree` 调用作为 defense-in-depth。

### 5.9 Probability 预留

`ConfidenceKindResolver` protocol 的 `resolve` 返回 `str`（不是 `Literal["certainty"]`），天然支持 `"probability"` 返回值。将来只需：
- 新增 `ProbabilityConfidenceKindResolver` 实现
- 或组合多个 resolver 为 `CompositeResolver`

本轮不实现，只留 protocol slot。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 无 resolver 时 evaluate 行为完全不变（所有 candidate 保持 `"none"`）
  - `_confidence_kind_resolver.py` 在 core 层，只 import core 内部类型（`SupportArtifact`, `RuleRefEdge`）
  - `CertaintyConfidenceKindResolver` 接受 `RuleSpecReader` protocol，不绑定具体 registry 类型
  - builder 创建的 `CandidateSet.confidence_kind` 与 `store._candidate_confidence_kind_index` 一致（无分叉）
  - eligibility 只有一份实现（`check_certainty_artifact_eligibility`），routing 和 service lookup 共用
- 明确不做的内容：
  - 不实现 probability resolver
  - 不在 Souffle/ProbLog adapter 中做 certainty marking
  - 不改 `CertaintySummary` / ranking / narrative / NL / audit / static
- 兼容性约束：
  - 223 tests 全绿
  - 无 resolver 时等价于旧行为
  - 有 resolver 但不满足 eligibility 时 fallback 到 `"none"`

## 7. Acceptance

- [ ] `_confidence_kind_resolver.py` 新建：`RuleSpecReader` protocol + `ConfidenceKindResolver` protocol + `CertaintyConfidenceKindResolver` + `check_certainty_artifact_eligibility`
- [ ] `candidates_from_bindings` / `entity_candidates_from_bindings` 新增 optional `confidence_kind_resolver` 参数
- [ ] `evaluate_store` 新增 optional `confidence_kind_resolver` 参数并传给 builder
- [ ] `Store.evaluate` 新增 optional `confidence_kind_resolver` 参数并传给 `evaluate_store`
- [ ] builder 创建的 `CandidateSet.confidence_kind` 直接是 resolved 值（无 post-patch）
- [ ] service 注入 `CertaintyConfidenceKindResolver(FileAuthoringRegistry(registry_root))`
- [ ] `_certainty_service.py` eligibility 改为调用 `check_certainty_artifact_eligibility`
- [ ] e2e 测试零 patch 验证：evaluate 自动产出 `confidence_kind="certainty"`
- [ ] 新增负面用例：无 resolver / 无 condition_weights / 多 rule_ref_edges / nested child edges → `"none"`
- [ ] accept + export 持久化的 confidence_kind 与 evaluate 返回值一致
- [ ] `materialize_certainty_summary` 保留 `extract_single_referenced_support_tree` 作为 defense-in-depth
- [ ] 223+ tests 全绿
- [ ] 受影响 docs 同步

## 8. Implementation Plan

1. [core/store/_confidence_kind_resolver.py] 新建：`RuleSpecReader` protocol, `ConfidenceKindResolver` protocol, `check_certainty_artifact_eligibility`, `CertaintyConfidenceKindResolver`
2. [core/store/_builders.py] `candidates_from_bindings` + `entity_candidates_from_bindings` 新增 `confidence_kind_resolver` 参数
3. [core/store/_evaluate.py] `evaluate_store` 新增 `confidence_kind_resolver` 参数，传给 builder
4. [core/store/runtime.py] `Store.evaluate` 新增 `confidence_kind_resolver` 参数，传给 `evaluate_store`
5. [service/runtime_v1.py] `evaluate_runtime_derivation` 构建 `CertaintyConfidenceKindResolver(FileAuthoringRegistry(registry_root))` 并注入 `session.store.evaluate(..., confidence_kind_resolver=resolver)`
6. [service/_certainty_service.py] `_lookup_condition_weights_for_candidate` 重构：eligibility 改用 `check_certainty_artifact_eligibility`
7. [tests] e2e 测试去掉 patch + 新增负面用例
8. [docs] annotation docs + architecture docs 同步

## 9. Docs To Update

- `src/factpy_kernel/core/annotation/docs/README.md`
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（confidence_kind routing 说明）

## 10. Outcome / Deviations

- 最终落地结果：
  - `_confidence_kind_resolver.py` (NEW): `RuleSpecReader` protocol, `ConfidenceKindResolver` protocol, `CertaintyConfidenceKindResolver`, `check_certainty_artifact_eligibility`
  - `_builders.py`: `candidates_from_bindings` + `entity_candidates_from_bindings` 新增 `confidence_kind_resolver` 参数
  - `_evaluate.py`: `evaluate_store` 新增 `confidence_kind_resolver` 参数，传给 builder（仅 native path）
  - `runtime.py`: `Store.evaluate` 新增 `confidence_kind_resolver` 参数，传给 `evaluate_store`
  - `runtime_v1.py`: `evaluate_runtime_derivation` 构建 `CertaintyConfidenceKindResolver(FileAuthoringRegistry(...))` 并注入
  - `_certainty_service.py`: eligibility 改用共享 `check_certainty_artifact_eligibility`，移除 `extract_single_referenced_support_tree` 调用
  - 2 个 service-level 测试去掉手工 patch，改为断言 evaluate 自动产出 `"certainty"`
  - 2 个 negative test cases（无 registry / 无 condition_weights）
  - 4 docs synced（annotation README, architecture CN/EN, service runtime queries）
  - 225 tests green
- 与 blueprint 不同的地方：
  - `_resolve_confidence_kind` 不吞异常（用户决策：暴露真实 bug 而非静默降级）
  - negative test 的 where shape 改为 `["pred", ...]` 而非 `["bind", ...]`（测试失败域只落在 routing）
- 为什么会有这些调整：
  - 异常吞咽会把 wiring bug 隐藏为 `"none"` fallback
  - `bind` 不被当前 runtime derivation 编译路径接受
- 归档说明：可归档到 `docs/blueprints/archive/`
