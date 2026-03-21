# Task Blueprint: Certainty Summary Explain Delivery

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Parent: None (follows certainty-weight-vocabulary lineage)
- Prerequisites:
  - [certainty-weight-vocabulary](../archive/2026-03-20_certainty-weight-vocabulary.md) ✅
  - [certainty-propagation-prototype](../archive/2026-03-20_certainty-propagation-prototype.md) ✅
- Related Modules:
  - `src/factpy_kernel/core/annotation/_certainty.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/authoring/registry_fs.py`
- Related Docs:
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-21_certainty-summary-explain-delivery.audit.md](./2026-03-21_certainty-summary-explain-delivery.audit.md)

## 1. Problem

`derive_certainty_summary` 已在 `core/annotation/_certainty.py` 中实现并通过测试，但目前 **零个 production caller**。它只被测试代码消费。

如果 vocabulary 的唯一验证停留在测试层，那么：
- 无法证明 certainty summary 在真实 explain delivery 中可用
- `condition_weights` 从 rule metadata 到 query-time 消费的完整链路未被验证
- 后续 salience / impact 开实现线时，仍需先解决 delivery surface 问题

## 2. Goals

- 给 `derive_certainty_summary` 建立 **第一个 production consumer**
- 在 `explain_runtime_summary` 的 `kind="candidate"` 响应中，附加可选 `certainty_summary` 字段
- 验证 `candidate_id → confidence_kind` 和 `candidate_id → condition_weights` 的完整 query-time 链路
- 为后续 salience / impact 提供已验证的 delivery surface

## 3. Non-goals

- **不动 audit / static / NL delivery** — 只走 runtime explain summary
- **不改 12-field core summary set** — `certainty_summary` 是 summary 响应中的并列扩展字段，不嵌入 `summary` dict 内部
- **不把 annotation prototype 提升为 contract owner** — 保持 internal / prototype
- **不开 full salience / impact** — 这是最窄的 delivery surface 验证
- **不在 evidence tree full response 中加 certainty** — 只在 summary response 中
- **不修改 evaluate / accept 执行路径**
- **不做多 rule / 递归 subtree 的 condition_weights 聚合** — 本轮只在单 rule_ref_edge + 无 nested referenced_support 时产出 certainty_summary；多 rule 场景 graceful degrade 为 null
- **不解决 rule/subtree ownership 问题** — atom key namespace (`b{branch}.a{atom}`) 是局部的，不携带 rule ownership；真正的多 rule 聚合需要先补 ownership，不在本 scope

## 4. Current Context

### 4.1 Explain Summary 当前响应结构

```python
# runtime_v1.py:340-345
return ok_response(
    meta={"candidate_id": id_},
    kind="candidate_evidence_tree_summary",
    summary=_get_candidate_tree_summary(session, id_),
)
```

`ok_response(**payload)` 接受任意 keyword，可以无破坏性地增加字段。

### 4.2 现有数据访问路径

| 数据 | 当前可达性 | 缺口 |
|---|---|---|
| evidence tree dict | ✅ `_get_candidate_tree(session, candidate_id)` | 无 |
| tree summary (12-field) | ✅ `summarize_candidate_evidence_tree_dict(tree)` | 无 |
| `confidence_kind` | ❌ Store 不索引 `candidate_id → confidence_kind` | 需新增索引 |
| `condition_weights` | ❌ 需要 `rule_ref_id + version` → `FileAuthoringRegistry.read_rule_spec()` → `payload["condition_weights"]` | 需新增访问辅助 |

### 4.3 数据来源链路

**confidence_kind:**
```
evaluate() → CandidateSet.confidence_kind
  → _remember_candidate_support(candidate_id, support_digest, support_kind)
  当前只索引 support_digest + support_kind，未索引 confidence_kind
```

**condition_weights:**
```
candidate_id
  → support_digest (via _candidate_support_index)
  → explain_support(support_digest) → support dict
  → support["rule_ref_edges"] → list[{rule_ref_id, rule_ref_version, ...}]
  前置校验：
    - rule_ref_edges 恰好 1 条 structured edge（排除多 rule sibling）
    - tree 无 nested referenced_support（排除递归 subtree）
    否则 → null（graceful degradation）
  → FileAuthoringRegistry(registry_root).read_rule_spec(rule_ref_id, version)
  → payload.get("condition_weights")
```

**registry_root 一致性:**
```
evaluate 时可能用 session.registry_root 或 dto.override_registry_root
explain summary 时需要同一个 registry_root 才能正确读取 rule payload
→ explain_runtime_summary dto 支持可选 override_registry_root 参数
→ 调用方必须传回 evaluate 时使用的同一个 root
→ 未传时 fallback 到 session.registry_root
```

## 5. Design

### 5.1 Phase 1: Store 索引扩展

在 `core/store/runtime.py` 的 `_remember_candidate_support()` 中，增加 `confidence_kind` 索引：

```python
# 新增索引
self._candidate_confidence_kind_index: dict[str, str] = {}

# _remember_candidate_support 增加 confidence_kind 参数
def _remember_candidate_support(
    self, candidate_id: str, support_digest: str, support_kind: str,
    confidence_kind: str = "none",
) -> None:
    ...
    self._candidate_confidence_kind_index.setdefault(candidate_id, confidence_kind)

# 新增 public getter
def get_candidate_confidence_kind(self, candidate_id: str) -> str | None:
    return self._candidate_confidence_kind_index.get(candidate_id)
```

在 `_evaluate.py` 的 `_remember_candidate_support_backrefs()` 中，传入 `confidence_kind`：

```python
store._remember_candidate_support(
    candidate.candidate_id, support_digest, support_kind,
    confidence_kind=candidate.confidence_kind,
)
```

### 5.2 Phase 2: condition_weights 查询辅助

在 `service/runtime_v1.py` 中新增辅助函数：

```python
def _lookup_condition_weights_for_candidate(
    session: RuntimeSession,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    override_registry_root: str | None = None,
) -> dict[str, float] | None:
    """从 candidate 的 support → rule_ref_edges → registry 读取 condition_weights。

    返回三态：
    - None：eligibility 不通过，或 registry_root / rule payload 链路不可用 → 调用方应产出 certainty_summary: null
    - {}：eligibility 通过，但 rule payload 没有 condition_weights → 调用方应产出 all-unweighted summary
    - {"b0.a0": 0.8, ...}：正常取到 weights → 调用方应产出 weighted summary
    """
    ...
```

逻辑：
1. `session.store.get_candidate_support_digest(candidate_id)` → support_digest；None → return `None`
2. `session.store.explain_support(support_digest)` → support dict；None → return `None`
3. **Eligibility guard**:
   - 从 support dict 读取 `rule_ref_edges`
   - 如果 structured edges（`child_support_digest` 非 None 或 `unresolved_reason` 非 None 的 edge）数量 ≠ 1 → return `None`
   - 递归检查 `tree_dict`：如果存在 `node_kind == "referenced_support"` 节点 → return `None`
4. 取唯一 structured edge 的 `rule_ref_id` + `rule_ref_version`
5. 确定 registry_root：`override_registry_root or session.registry_root`；如果都为 None → return `None`
6. `FileAuthoringRegistry(registry_root).read_rule_spec(rule_ref_id, version)` → payload；None → return `None`
7. `payload.get("condition_weights", {})` → condition_weights（可能是 `{}` 或有值的 dict）

总结：eligibility / 链路不可用 → `None`；链路可用但 rule 没写 weights → `{}`；正常 → 有值 dict。

### 5.3 Phase 3: explain_runtime_summary 扩展

修改 `explain_runtime_summary` 的 `kind="candidate"` 分支：

```python
if kind == "candidate":
    override_registry_root = _optional_str_or_none(
        dto.get("override_registry_root"), path="$.override_registry_root",
    )
    tree = _get_candidate_tree(session, id_)
    summary = summarize_candidate_evidence_tree_dict(tree)
    confidence_kind = session.store.get_candidate_confidence_kind(id_)
    certainty_summary = None
    if confidence_kind == "certainty":
        condition_weights = _lookup_condition_weights_for_candidate(
            session, id_, tree,
            override_registry_root=override_registry_root,
        )
        if condition_weights is not None:  # None = ineligible → skip
            raw = derive_certainty_summary(tree, condition_weights, confidence_kind)
            if raw is not None:
                certainty_summary = _certainty_summary_to_dict(raw)
    return ok_response(
        meta={"candidate_id": id_},
        kind="candidate_evidence_tree_summary",
        summary=summary,
        certainty_summary=certainty_summary,  # None 或 dict
    )
```

**override_registry_root 语义：** 调用方在 evaluate 时如果使用了 `override_registry_root`，explain summary 时必须传回同一个 root，否则 rule metadata lookup 可能读错 payload 或降级为 null。未传时 fallback 到 `session.registry_root`。

### 5.4 DTO 序列化

新增 `_certainty_summary_to_dict()`：

```python
def _certainty_summary_to_dict(s: CertaintySummary) -> dict[str, Any]:
    return {
        "confidence_kind": s.confidence_kind,
        "condition_count": s.condition_count,
        "weighted_condition_count": s.weighted_condition_count,
        "conditions": [
            {
                "atom_key": c.atom_key,
                "node_kind": c.node_kind,
                "weight": c.weight,
                "impact": c.impact,
            }
            for c in s.conditions
        ],
        "aggregate_certainty": s.aggregate_certainty,
    }
```

### 5.5 响应结构（扩展后）

```json
{
  "ok": true,
  "errors": [],
  "meta": {"candidate_id": "cand_v2:..."},
  "kind": "candidate_evidence_tree_summary",
  "summary": { ... 12-field core set ... },
  "certainty_summary": {
    "confidence_kind": "certainty",
    "condition_count": 3,
    "weighted_condition_count": 2,
    "conditions": [
      {"atom_key": "b0.a0", "node_kind": "predicate_witness_group", "weight": 0.8, "impact": 0.8},
      {"atom_key": "b0.a1", "node_kind": "non_fact_check", "weight": null, "impact": null},
      {"atom_key": "b0.a2", "node_kind": "predicate_witness_group", "weight": 0.5, "impact": 0.5}
    ],
    "aggregate_certainty": 0.5
  }
}
```

当 `confidence_kind != "certainty"` 时，`certainty_summary` 为 `null`。

## 6. Implementation Plan

### Phase 1: Store 索引扩展

1. `core/store/runtime.py`：新增 `_candidate_confidence_kind_index` 和 `get_candidate_confidence_kind()`
2. `core/store/runtime.py`：`_remember_candidate_support()` 增加 `confidence_kind` 参数
3. `core/store/_evaluate.py`：`_remember_candidate_support_backrefs()` 传入 `candidate.confidence_kind`

### Phase 2: Service 层集成

4. `service/runtime_v1.py`：新增 `_lookup_condition_weights_for_candidate()`
5. `service/runtime_v1.py`：新增 `_certainty_summary_to_dict()`
6. `service/runtime_v1.py`：修改 `explain_runtime_summary()` 的 candidate 分支，附加 `certainty_summary`
7. `service/runtime_v1.py`：修改 `_get_candidate_tree_summary()` 不再独立调用（或保持不变，在 `explain_runtime_summary` 中直接组合）

### Phase 3: Tests

8. 新增 `test_certainty_summary_explain_delivery.py`（或在 `test_phase3_contracts_v1.py` 中新增 section）：
   - certainty lane + 单 rule + 无 nested support → summary response 包含 `certainty_summary` dict
   - probability lane candidate → `certainty_summary` 为 null
   - none lane candidate → `certainty_summary` 为 null
   - 多 rule_ref_edges → `certainty_summary` 为 null（eligibility guard）
   - 有 nested referenced_support → `certainty_summary` 为 null（eligibility guard）
   - 无 registry_root（session 和 dto 都无） → `certainty_summary` 为 null
   - override_registry_root 传入时使用该 root（不用 session.registry_root）
   - condition_weights 为空 → `certainty_summary` 全部 unweighted
   - Store `get_candidate_confidence_kind()` round-trip

### Phase 4: Docs

9. 更新 `core/annotation/docs/README.md`：§2.3 增加 delivery surface 描述
10. 更新 `core/docs/01_architecture.md`：§8.1 增加 explain delivery 入口描述
11. 更新 `service/docs/03_runtime_queries_views.md`：explain summary candidate 响应新增 `certainty_summary` 字段 + `override_registry_root` 参数

## 7. Boundaries And Invariants

- 12-field core summary set 不变
- `certainty_summary` 是 response-level 并列字段，不嵌入 `summary` dict
- annotation prototype 保持 internal — 不进入 `Store.evaluate()` public contract
- `CertaintySummary` 不进入 `CandidateSet` 或 `SupportArtifact`
- `_lookup_condition_weights_for_candidate` 是 service-level 查询辅助，不进入 core
- graceful degradation：任何环节缺失 → `certainty_summary: null`，不报错
- `_remember_candidate_support` 新增参数向后兼容（`confidence_kind="none"` default）
- **单 rule eligibility guard**：只在 support 恰好 1 条 structured rule_ref_edge 且 tree 无 nested referenced_support 时产出 certainty_summary；多 rule / 递归 subtree → null
- **registry_root 一致性**：explain summary 支持可选 `override_registry_root`；调用方必须传回 evaluate 时使用的同一个 root；未传时 fallback 到 session.registry_root
- atom key namespace 是 per-rule 局部的（`b{branch}.a{atom}`），不携带 rule ownership；本轮不补 ownership

## 8. Acceptance

- [x] Store 索引 `candidate_id → confidence_kind`，public getter 可用
- [x] `_remember_candidate_support_backrefs` 传入 `confidence_kind`
- [x] `explain_runtime_summary` candidate 响应包含 `certainty_summary` 字段
- [x] certainty lane → dict；非 certainty lane → null
- [x] condition_weights 通过 support → rule_ref_edges → registry 链路获取
- [x] 单 rule eligibility guard：多 rule_ref_edges 或 nested referenced_support → null
- [x] explain summary dto 支持可选 `override_registry_root`
- [x] 链路任何环节缺失时 graceful degradation
- [x] 新增测试覆盖所有 lane、eligibility guard 和 degradation 场景
- [x] 全量测试通过
- [x] 文档更新（core annotation docs + core architecture docs + service docs）

## 9. Outcome / Deviations

- 最终落地结果：
  - runtime `queries/explain-summary` 的 candidate 响应现在会附加 response-level `certainty_summary`
  - Store 新增 `candidate_id -> confidence_kind` backref lookup
  - service 已打通 `candidate -> support -> rule_ref_edges -> registry rule payload -> condition_weights -> derive_certainty_summary(...)` 的第一条 production chain
  - 新增 contract tests 覆盖 certainty lane、non-certainty lanes、multi-rule guard、nested subtree guard、override registry root、unweighted 与 unresolved degrade
- 与 blueprint 不同的地方：
  - 最终 certainty derivation 不是直接对整棵 candidate tree 求值，而是只对单条 structured `rule_ref_edge` 指向的唯一 `referenced_support` subtree 求值
  - 单条 unresolved `rule_ref_edge` 当前也会降级为 `certainty_summary=null`
- 为什么会有这些调整：
  - `condition_weights` 属于 child rule metadata；直接对整棵 candidate tree 求值会把 parent/local node 与 child rule namespace 混在一起
  - 只消费唯一 `referenced_support` subtree 才能让 `b{branch}.a{atom}` 与 child rule metadata 对齐；unresolved child support 则没有可对齐的 subtree
- 归档说明：
  - blueprint 与 audit 在代码、测试、模块文档同步后归档到 `docs/blueprints/archive/`
