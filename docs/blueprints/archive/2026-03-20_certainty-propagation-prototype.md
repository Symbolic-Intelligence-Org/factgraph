# Task Blueprint: Certainty Propagation Prototype

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Parent: [2026-03-20_certainty-weight-vocabulary.md](./2026-03-20_certainty-weight-vocabulary.md)
- Prerequisites:
  - Child 1: [candidate-confidence-kind](./2026-03-20_candidate-confidence-kind.md) ✅
  - Child 2: [rule-condition-weight-metadata](./2026-03-20_rule-condition-weight-metadata.md) ✅
- Related Modules:
  - `src/factpy_kernel/core/annotation/`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_summary.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
- Related Docs:
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-20_certainty-propagation-prototype.audit.md](./2026-03-20_certainty-propagation-prototype.audit.md)

## 1. Problem

Child 1 (`confidence_kind`) 和 Child 2 (`condition_weights`) 已落地为 contract-level vocabulary，但尚未被任何语义消费方验证。当前状态：

- `CandidateSet.confidence_kind` 已存在，但没有消费方根据它改变行为
- `condition_weights` 已进入 rule metadata，但没有运行时或 query-time 路径读取和使用它们
- annotation prototype（`core/annotation`）是 parent blueprint 指定的 first consumer，但它目前不感知这两个 vocabulary

如果不验证 vocabulary 的 end-to-end 可用性，后续 salience / impact 开实现线时，核心风险仍在：condition_weights 和 confidence_kind 到底能不能形成可用的语义产物，未被证明。

## 2. Goals

- 在 `core/annotation` 中新增一个 **certainty derivation** prototype 路径
- 消费 `confidence_kind="certainty"` + `condition_weights` + 证据树结构
- 对 winning branch / adopted proof body 的每个条件，派生 per-condition weighted impact
- 产出 **candidate-level certainty summary**（additive 扩展块），验证 vocabulary end-to-end 可用性
- 为后续 salience / impact breakdown 提供已验证的语义基础

## 3. Non-goals

- **不升级 annotation prototype 为 public contract owner** — 保持 internal / prototype
- **不做 `probability` 或 `none` lane** — 只验证 `certainty` lane；其他 lane 不做伪映射
- **不改现有 evidence tree summary 12 字段 core set** — certainty summary 作为可选扩展块
- **不做 full cross-branch reasoning** — 只处理 winning branch / adopted proof body
- **不做 rule-level certainty cap** — parent blueprint §5.3 已 deferred
- **不把结果写回 `CandidateSet`、`SupportArtifact` 或执行路径** — prototype 产物是 query-time / read-time 的派生视图
- **不是 salience / impact 的完整落地** — 这是 prototype-first、summary-second 的最小验证

## 4. Current Context

### 4.1 Vocabulary 已就绪

| Vocabulary | 位置 | 状态 |
|---|---|---|
| `CandidateSet.confidence_kind` | `core/derivation/candidates.py` | ✅ `"none" \| "probability" \| "certainty"` |
| `CONFIDENCE_KINDS` | `core/derivation/candidates.py` | ✅ `frozenset` |
| `condition_weights` | rule metadata (authoring compile) | ✅ `{atom_key: positive_float}` |
| atom key format | `b{branch}.a{atom}` | ✅ 冻结 |

### 4.2 Evidence Tree 结构已就绪

- `candidate_evidence_tree` 递归树：node_kind taxonomy 6 类，winning branch narrowing
- `SupportArtifact`：`pred_witnesses` + `non_fact_steps` + `rule_ref_edges`
- tree summary：12 字段 core set（结构性统计，无数值权重）

### 4.3 Annotation Prototype 当前能力

| 模块 | 能力 | 与本 child 的关系 |
|---|---|---|
| `_min_max.py` | widest-path confidence propagation | 算法参考（bottleneck propagation），但本 child 不复用 |
| `_evidence.py` | evidence aggregation + max provenance | 结构参考，但本 child 不复用 |
| `types.py` | 最小共享类型 | 可扩展 |

## 5. Design

### 5.1 输入

certainty derivation 需要三个输入：

1. **candidate evidence tree**（dict 形式，已有 `build_candidate_evidence_tree` 产出）
2. **condition_weights**（从 rule metadata 读取，`{atom_key: float}`）
3. **confidence_kind**（从 `CandidateSet.confidence_kind` 读取）

### 5.2 处理逻辑

只在 `confidence_kind == "certainty"` 时执行；其他 lane 直接返回 `None`。

遍历 evidence tree 的 winning branch proof body：

1. 收集所有 `predicate_witness_group` 和 `non_fact_check` 节点（这些对应 where 中的条件）
2. 对每个条件节点，通过其 atom key（`b{branch}.a{atom}` 格式）查找 `condition_weights` 中的 weight
3. 如果条件有 weight 且有 confidence 值：`impact = weight * confidence`
4. 如果条件有 weight 但无 confidence（deterministic 条件）：`impact = weight`（满足 = full contribution）
5. 无 weight 的条件：`impact = None`（unweighted）

### 5.3 输出：Certainty Summary

```python
@dataclass(frozen=True)
class CertaintySummary:
    confidence_kind: str                           # "certainty"
    condition_count: int                           # 总条件数
    weighted_condition_count: int                  # 有 weight 的条件数
    conditions: tuple[ConditionImpact, ...]        # per-condition breakdown
    aggregate_certainty: float | None              # 聚合值（加权最小值或 None）

@dataclass(frozen=True)
class ConditionImpact:
    atom_key: str                                  # "b0.a1"
    node_kind: str                                 # "predicate_witness_group" | "non_fact_check"
    weight: float | None                           # from condition_weights
    impact: float | None                           # weight * condition_confidence
```

### 5.4 与 Evidence Tree Summary 的关系

- 不修改现有 12 字段 core set
- `CertaintySummary` 作为 **可选扩展块** 挂在 summary 外部
- 调用方式：`derive_certainty_summary(tree_dict, condition_weights, confidence_kind)` → `CertaintySummary | None`
- 返回 `None` 当 `confidence_kind != "certainty"`

### 5.5 aggregate_certainty 语义

第一轮采用最简方式：加权条件中的 **最小 impact**（bottleneck）。

理由：与 annotation prototype 的 `_min_max.py` widest-path 语义一致；certainty 传播的常见语义是"链条中最弱环节决定整体强度"。

不做 weighted sum / weighted mean — 这些需要更多设计讨论，属于 salience / impact 的完整落地范围。

## 6. Implementation Plan

### Phase 1: Core derivation

1. `core/annotation/_certainty.py`：新增 `CertaintySummary`、`ConditionImpact` dataclass
2. `core/annotation/_certainty.py`：新增 `derive_certainty_summary(tree_dict, condition_weights, confidence_kind)` 函数
3. `core/annotation/__init__.py`：导出新增类型和函数

### Phase 2: Evidence tree summary 扩展入口

4. `core/store/_candidate_evidence_tree_summary.py`：新增可选 `certainty_summary` 扩展调用入口（不改 12 字段 core set）
5. 或者：扩展入口仅在 service / runtime 层组合（summary + certainty_summary 并列返回），不修改 core summary 函数

### Phase 3: Tests

6. 新增 `test_core_annotation_certainty.py`：
   - certainty lane 产出正确 summary
   - probability lane 返回 None
   - none lane 返回 None
   - unweighted 条件 impact = None
   - aggregate_certainty = bottleneck 最小值
   - 空 condition_weights → 全部 unweighted

### Phase 4: Docs

7. 更新 `core/annotation/docs/README.md`：新增 §2.3 certainty derivation 描述
8. 更新 parent blueprint：标记 Child 3 completed

## 7. Boundaries And Invariants

- annotation prototype 保持 internal / prototype — 不进入 `Store.evaluate()` public contract
- `CertaintySummary` 不进入 `CandidateSet` 或 `SupportArtifact`
- 不修改 evidence tree summary 的 12 字段 core set
- 不修改 where evaluator 执行语义
- 只处理 `confidence_kind="certainty"`；其他 lane 不做伪映射
- `aggregate_certainty` 第一轮仅为 bottleneck（最小 weighted impact），不做 weighted sum

## 8. Acceptance

- [x] `core/annotation/_certainty.py` 新增 `derive_certainty_summary` 函数
- [x] 函数消费 `confidence_kind` + `condition_weights` + evidence tree dict
- [x] 只在 `certainty` lane 产出 summary；其他 lane 返回 None
- [x] per-condition impact 基于 atom_key 关联 condition_weights
- [x] aggregate_certainty = bottleneck（最小 weighted impact）
- [x] 新增测试覆盖所有 lane 和边界情况
- [x] annotation docs 更新
- [x] 全量测试通过

## 9. Outcome / Deviations

- 最终落地结果：新增 `core/annotation/_certainty.py`，提供 `ConditionImpact`、`CertaintySummary` 和 `derive_certainty_summary(...)`。prototype 现可消费 `confidence_kind="certainty"`、rule metadata `condition_weights` 与 candidate evidence tree，按 condition key 产出 per-condition weighted impact，并用最小 weighted impact 作为 `aggregate_certainty`。annotation docs 与 core architecture docs 已同步，新增 14 个 certainty prototype tests；全量回归 `194` tests pass。
- 与 blueprint 不同的地方：第一轮没有把 certainty summary 继续并入 runtime / audit 的稳定 `candidate_evidence_tree_summary` DTO，而是保留为 annotation 层导出的 internal summary object。
- 为什么会有这些调整：当前 runtime / audit summary surface 仍以 12 字段 core set 为稳定 contract；在同一 slice 内继续把 `condition_weights` / `confidence_kind` 线程化到外层 DTO，会越过“prototype first consumer、不扩 stable contract”的边界。annotation 层先作为 first consumer 已足够验证 vocabulary 的 end-to-end 可用性。
- 归档说明：2026-03-20 实现完成并归档到 `docs/blueprints/archive/`。
