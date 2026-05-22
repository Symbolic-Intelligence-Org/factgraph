# fact-confidence-to-evidence-tree

- Status: implemented
- Created: 2026-03-21
- Parent: certainty delivery chain (certainty-propagation-prototype → certainty-summary-explain-delivery → ... → confidence-kind-certainty-routing)

## 1. Problem

`write_protocol.py` 已支持 `meta={"confidence": 0.9}` 写入，值存入 ledger `meta_rows` 表。
`_certainty.py` 的 `_condition_confidence(node)` 已准备好从树节点读取 `condition_confidence` / `confidence`。
但中间 3 个接线点断了：

1. `_runtime_assertion_detail_for_tree()` (runtime_v1.py) 读 assertion 时跳过所有 meta
2. `_build_assertion_leaf()` (_candidate_evidence_tree.py) 构建节点时无 confidence 字段
3. `predicate_witness_group` 节点上没有 `condition_confidence`

结果：production path 下所有 condition confidence 均为隐含 `1.0`，impact 退化为纯 weight。

## 2. Goal

接通 native evidence tree 的 fact-level confidence carrier，使 certainty lane 真实消费实例 confidence。

## 3. Non-Goals

- 不改 `derive_certainty_summary()` 算法（已正确消费 confidence 字段）
- 不开 probability lane
- 不做 recursive / chain certainty propagation
- 不做 weighted mean / leaf mean 聚合
- 不改 `condition_weights` 语义
- 不改 SDK batch API 签名（`meta` 参数已存在）
- 不改 `write_runtime_fact` DTO schema（confidence 通过 meta 传入，不新增顶级字段）

## 4. Current Context

### 写入侧（已就绪）

- `write_protocol.py:54` — `"confidence"` 是合法的 convention meta key
- `write_protocol.py:365-367` — 验证 confidence 值 `(0.0, 1.0]`
- `sdk/store.py:264-292` — `set()` / `add()` 接受 `meta` 参数
- `ledger.py:80-86` — MetaRow 表存储 `(asrt_id, key="confidence", kind="float", value)`

### 消费侧（已就绪）

- `_certainty.py:133-140` — `_condition_confidence(node)` 读 `node.get("condition_confidence", node.get("confidence"))`
- `_certainty.py:69` — `impact = weight * confidence if confidence is not None else weight`
- `test_core_annotation_certainty.py:53` — 测试已使用手工 `condition_confidence` 字段

### 断点侧（需修复）

- `runtime_v1.py:1195-1216` — `_runtime_assertion_detail_for_tree()` 只读 claim + claim_args，跳过 meta_rows
- `_candidate_evidence_tree.py:202-221` — `_build_assertion_leaf()` 不输出 confidence 字段
- `_candidate_evidence_tree.py` — `predicate_witness_group` 构建时不从子 assertion 聚合 confidence

## 5. Design

### 5.1 断点 1：`_runtime_assertion_detail_for_tree()` 读取 confidence meta

**位置**：`src/factpy_kernel/service/runtime_v1.py`

在现有函数中，从 ledger 读取 assertion 的 meta_rows，提取 `key="confidence"` 的值，加入返回的 dict：

```python
def _runtime_assertion_detail_for_tree(ledger, asrt_id):
    ...
    result = {
        "asrt_id": asrt_id,
        "claim": {...},
        "claim_args": claim_args,
    }
    # NEW: read confidence from meta
    confidence = _read_assertion_confidence(ledger, asrt_id)
    if confidence is not None:
        result["confidence"] = confidence
    return result
```

`_read_assertion_confidence` 从 `ledger.find_meta_rows(asrt_id=asrt_id)` 中提取 `key="confidence"` 的 float 值。

**多 assertion 的 predicate_witness_group**：当一个 predicate 匹配了多条 assertion 时，每条 assertion 各自携带自己的 confidence。聚合到 `condition_confidence` 的策略在断点 3 处理。

### 5.2 断点 2：`_build_assertion_leaf()` 输出 confidence

**位置**：`src/factpy_kernel/core/store/_candidate_evidence_tree.py`

在 `_build_assertion_leaf()` 中，如果 `assertion_detail` 包含 `confidence` 字段，则透传到 `assertion_fact` 节点：

```python
node = {
    "node_kind": "assertion_fact",
    ...
    "children": [],
}
confidence = detail.get("confidence")
if confidence is not None:
    node["confidence"] = confidence
return node
```

只有显式写入了 confidence 的 assertion 才携带该字段。未写入 confidence 的 assertion 不输出该字段（不默认 1.0），保持现有 tree shape 的向后兼容。

### 5.3 断点 3：`predicate_witness_group` 派生 `condition_confidence`

**位置**：`src/factpy_kernel/core/store/_candidate_evidence_tree.py`

在 `_build_predicate_witness_group()` 构建完子 assertion 节点后，从子节点聚合 `condition_confidence`：

聚合策略：**max of children confidences**。

```
witness_group 有 3 条 assertion:
  assertion A: confidence=0.9
  assertion B: confidence=0.6
  assertion C: (no confidence)

→ 只聚合有值的: max(0.9, 0.6) = 0.9
→ condition_confidence = 0.9

如果所有 children 都没有 confidence:
→ 不设 condition_confidence 字段（保持现有行为，impact 退化为 weight）
```

**为什么是 max 不是 min**：evidence tree 是 carrier，不是 scoring tree。`max` 表达"这个条件有多强的证据支撑"（局部证据强度）；全局 bottleneck（min）留给 `derive_certainty_summary()` 在 summary 层做。如果把 min 提前固化到 tree 节点，后续切换 aggregation 策略（如 weighted additive）时必须改 tree shape。

这与 `_condition_confidence(node)` 的消费逻辑对齐：返回 `None` 时 impact 退化为 `weight`。

### 5.4 Audit path

Audit evidence tree 通过 `AuditQuery.get_candidate_evidence_tree()` 离线重建。树构建使用与 runtime 相同的 `build_candidate_evidence_tree()`，但 `assertion_lookup` 来自 audit package 而非 live ledger。

当前 audit assertion detail 来自 `support_artifacts.jsonl` 中的 `SupportArtifact`，其 witness_entries 不包含 per-assertion confidence。

**本轮不动 audit path**：audit 的 confidence 依赖 `certainty_summaries.jsonl` 的 export-time 物化（已接通），不依赖 audit tree 上的 assertion confidence。这与 `condition_weights` 离线不可用的设计一致——certainty 信息在 export time 预计算。

### 5.5 `write_runtime_fact` 的 confidence 传入

当前 `write_runtime_fact` DTO 接受 `meta` dict。用户已可通过 `meta={"confidence": 0.9}` 传入。但 `write_runtime_fact` 的 DTO 文档没有提及 confidence。

**本轮只补文档**，不改 DTO schema。confidence 通过 `meta` 传入是已有 convention，不需要新增顶级字段。

## 6. Implementation Plan

### Phase 1: 接通 3 个断点

1. `runtime_v1.py` — `_runtime_assertion_detail_for_tree()` 读取 confidence meta
2. `_candidate_evidence_tree.py` — `_build_assertion_leaf()` 透传 confidence
3. `_candidate_evidence_tree.py` — `_build_predicate_witness_group()` 聚合 condition_confidence

### Phase 2: 测试

4. 新增 e2e test：`sdk.set(meta={"confidence": 0.9})` → evaluate → tree → certainty_summary 全链路
5. 确认 assertion_fact 节点可见 confidence
6. 确认 predicate_witness_group 可见 condition_confidence
7. 确认 derive_certainty_summary 计算 impact = weight × confidence（不再是 × 1.0）
8. 确认现有 225 tests 通过（向后兼容：无 confidence 的 assertion 不影响现有行为）

### Phase 3: Demo + Docs

9. 更新 `examples/certainty_evidence_tree.ipynb`：改为写入带 confidence 的 facts，展示 weight × confidence 传播
10. 更新 `service/docs/03_runtime_queries_views.md` 补 write_runtime_fact 的 confidence convention 文档
11. 归档 blueprint

## 7. Acceptance Criteria

1. `sdk.set(..., meta={"confidence": 0.9})` 写入的值能进入 candidate evidence tree
2. `assertion_fact` 节点可见 `confidence` 字段（仅当写入时提供）
3. `predicate_witness_group` 能派生 `condition_confidence`（min of children）
4. `derive_certainty_summary()` 在真实 runtime tree 上不再默认全按 `1.0`
5. 现有 certainty summary / ranking / narrative / NL tests 保持通过
6. 新增至少 1 个 e2e test 验证 confidence propagation
7. notebook 展示 weight × confidence 传播

## 8. Outcome

任务完成后填写：

- 最终落地结果：
  - `runtime_v1.py` — `_runtime_assertion_detail_for_tree()` 读取 `meta.confidence` (+6 lines)
  - `_candidate_evidence_tree.py` — `_build_assertion_leaf()` 透传 confidence，`_build_predicate_witness_group()` 聚合 `condition_confidence=max(children)` (+8 lines)
  - 2 new tests: tree carrier shape + e2e confidence propagation (227 total)
  - Notebook 更新：facts 写入 confidence，展示 `weight × confidence` 传播
  - Architecture docs known gap 已记录（CN/EN + annotation README）
- 与 blueprint 不同的地方：无偏差
- 归档说明：可归档
