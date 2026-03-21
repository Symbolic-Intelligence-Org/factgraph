# certainty-additive-aggregation-v1

- Status: implemented
- Created: 2026-03-21
- Parent: certainty delivery chain (fact-confidence-to-evidence-tree → ...)

## 1. Problem

当前 certainty lane 只有一种聚合策略：**bottleneck（min weighted impact）**。
这适合"最弱环节决定整体强度"的场景，但不适合"所有条件按权重贡献加总"的场景。

许多推理系统（如 Rainbird）使用 **加权加和（weighted additive）** 模型，更适合
表达"每个条件独立贡献一部分 certainty"的语义。

当前架构已具备所有前置：
- `condition_weights` 在 rule metadata 中
- `condition_confidence` 在 evidence tree 中（fact-confidence-to-evidence-tree 已打通）
- `derive_certainty_summary()` 是聚合计算的唯一入口
- 下游 delivery chain（narrative/NL/audit/static）消费 `CertaintySummary`，不关心聚合方式

## 2. Goal

新增 **weighted additive contribution** 作为第二种 certainty aggregation strategy，
与现有 bottleneck/min 并存。

## 3. Non-Goals

- 不改 raw evidence tree shape
- 不改 `condition_weights` / `condition_confidence` 语义
- 不做 rule-level certainty cap
- 不做 minimum certainty threshold
- 不做 optional conditions（unmet → 0%）
- 不做 recursive / chain propagation
- 不碰 probability lane
- 不改 `CandidateSet` / `SupportArtifact` 结构

## 4. Design

### 4.1 Additive 公式

```
contribution_i = (weight_i / sum(all_weights)) × condition_confidence_i
aggregate_certainty = sum(all_contributions)
```

当 `condition_confidence` 为 `None`（fact 未声明 confidence）时，该条件贡献按 `confidence=1.0` 处理（与 bottleneck 一致的 fallback）。

值域：`[0.0, 1.0]`。当所有 confidence 为 1.0 时，additive aggregate = 1.0。

### 4.2 Strategy 枚举

`_certainty.py` 新增 aggregation strategy 参数：

```python
AGGREGATION_STRATEGIES = ("bottleneck", "additive")

def derive_certainty_summary(
    tree_dict,
    condition_weights,
    confidence_kind,
    *,
    aggregation: str = "bottleneck",   # ← NEW keyword-only
) -> CertaintySummary | None:
```

- `"bottleneck"` — 现有行为，`min(weighted_impacts)`
- `"additive"` — 新行为，`sum(normalized_weight_i × confidence_i)`

`CertaintySummary` 新增 `aggregation: str` 字段，让下游知道用了哪种策略。

### 4.3 ConditionImpact 扩展

当 aggregation="additive" 时，`ConditionImpact.impact` 的语义变为 **normalized contribution**：

```
impact = (weight / sum_weights) × confidence
```

这与 bottleneck 的 `impact = weight × confidence` 不同。narrative/NL 消费 `impact` 字段，不需要知道计算方式——它只排序和标注。

但 additive 不存在 bottleneck 概念。`aggregate_certainty` 是 sum，不是 min。
`rank_certainty_conditions` 仍按 impact 升序排列，但 `is_bottleneck` 在 additive 模式下全部为 `False`。

### 4.4 Strategy surface：explain-side query option

Service layer 接受 strategy 选项：

```python
explain_runtime_summary(session_id, {
    "kind": "candidate",
    "id": candidate_id,
    "certainty_aggregation": "additive",  # ← optional, default "bottleneck"
})
```

- 不传 → 默认 `"bottleneck"`（完全向后兼容）
- 传 `"additive"` → 使用 additive aggregation
- 传无效值 → 报错

`explain_runtime_narrative` 和 `explain_runtime_nl` 也接受相同 option，透传到 certainty derivation。

### 4.5 影响范围

| 组件 | 改动 |
|------|------|
| `_certainty.py` | `derive_certainty_summary` 加 `aggregation` 参数；新增 additive 计算；`CertaintySummary` 加 `aggregation` 字段 |
| `_certainty_materializer.py` | `materialize_certainty_summary` 透传 `aggregation` |
| `_certainty_service.py` | `_compute_certainty_summary_from_tree` 透传 `aggregation` |
| `runtime_v1.py` | explain endpoints 解析 `dto.get("certainty_aggregation")` 并透传 |
| `_candidate_evidence_tree_narrative.py` | narrative 的 `certainty_lines` 第一行标注 aggregation 类型 |
| `rank_certainty_conditions` | additive 模式下 `is_bottleneck=False` |
| 测试 | 新增 additive unit tests + e2e |

### 4.6 不改的部分

- raw evidence tree — 不受影响
- audit export — 现有 `certainty_summaries.jsonl` 使用默认 bottleneck，本轮不改
- static site — 消费 narrative，自动继承
- SDK — 不改

## 5. Implementation Plan

### Phase 1：Core 聚合

1. `_certainty.py` — `derive_certainty_summary` 加 `aggregation` 参数，实现 additive 路径
2. `CertaintySummary` 加 `aggregation: str` 字段
3. `rank_certainty_conditions` — additive 模式下 `is_bottleneck=False`

### Phase 2：Service wiring

4. `_certainty_service.py` / `_certainty_materializer.py` 透传 `aggregation`
5. `runtime_v1.py` explain endpoints 解析 `certainty_aggregation` option
6. narrative 第一行标注 aggregation 类型

### Phase 3：Tests + Docs

7. Unit tests：additive 计算、normalized weights、fallback confidence
8. E2e test：explain-summary with `certainty_aggregation="additive"`
9. 更新 annotation docs + service docs

## 6. Acceptance Criteria

1. `derive_certainty_summary(..., aggregation="additive")` 返回 additive aggregate
2. `aggregate_certainty = sum(normalized_weight_i × confidence_i)`
3. 默认 `aggregation="bottleneck"` 行为完全不变
4. `CertaintySummary.aggregation` 字段反映使用的策略
5. explain endpoints 接受 `certainty_aggregation` option
6. narrative 第一行显示 aggregation 类型
7. 现有 227 tests 通过 + 新增 additive 覆盖
8. additive 模式下无 bottleneck 标注

## 7. Outcome

任务完成后填写：

- 最终落地结果：
  - `_certainty.py` — dual strategy: bottleneck + additive, `CertaintySummary.aggregation` field
  - `_certainty_materializer.py` / `_certainty_service.py` — aggregation parameter threading
  - `runtime_v1.py` — explain endpoints accept `certainty_aggregation` option
  - `_candidate_evidence_tree_narrative.py` — first line shows aggregation type
  - 6 unit tests + 1 e2e test (234 total)
  - 4 docs synced
- 与 blueprint 不同的地方：无偏差
- 归档说明：可归档
