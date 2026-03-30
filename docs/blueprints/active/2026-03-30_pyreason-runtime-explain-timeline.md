# Implementation Blueprint: PyReason Runtime Explain — CandidateProvenanceTimeline

- Status: implemented
- Created: 2026-03-30
- Last Updated: 2026-03-30
- Parent:
  - [2026-03-28_evidence-graph-unified-explain.md](./2026-03-28_evidence-graph-unified-explain.md) (landed)
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` — 现有 tree contract（不动）
  - `src/factpy_kernel/core/store/_support.py` — ProvenanceEnvelope, support kind 常量
  - `src/factpy_kernel/adapters/pyreason/provenance.py` — PyReasonTraceV0, event log
  - `src/factpy_kernel/service/runtime_v1.py` — explain dispatch
  - `src/factpy_kernel/audit/evidence_graph.py` — EvidenceGraph（不动）
- Audit Log:
  - [2026-03-30_pyreason-runtime-explain-timeline.audit.md](./2026-03-30_pyreason-runtime-explain-timeline.audit.md)

## 1. Problem

当前 runtime explain API 对 provenance-bearing support kind 直接报错：

```
_get_candidate_tree(candidate_id)
  → support_kind == "pyreason_provenance_v1"
  → raise runtime_explain_not_supported
```

PyReason 的 `PyReasonTraceV0` 已经在 store 的 `_provenance_envelopes` 里了，但 runtime explain 没有能消费它的 contract。用户调 `explain_runtime_tree/summary/narrative` 对 PyReason candidate 全部返回错误。

这不是"缺了实现"，而是**缺了合同**。PyReason 的 event log 不是 tree，不应该强塞进 `CandidateEvidenceTree`。

## 2. Design Fork Declaration

Parent 蓝图 D-EG1 预留了一条路："等到 runtime explain API 确定要直接返回 EvidenceGraph，再开单独蓝图提升到 `core/`"。

本蓝图选择**另一条路**：不提升 EvidenceGraph 到 runtime，而是为 PyReason 在 `core/` 新建独立的 runtime explain contract。

**原因：** PyReason 的 runtime explain 需要 `time / fixpoint_op / old_bound / new_bound / groundings` 这些 EvidenceGraph 有意不携带的 engine-specific 细节。提升 EvidenceGraph 到 runtime 会违反其"最小共享抽象"定位（parent 蓝图 §2 principle: "EvidenceGraph is NOT unified evidence tree"）。

正确分层：
- `CandidateProvenanceTimeline` — runtime explain contract（`core/`，新建）
- `EvidenceGraph` — audit/static 消费层（`audit/`，不动）

## 3. Frozen Decisions

### D-PT1: 新合同名为 `CandidateProvenanceTimeline`，放 `core/store/`

和 `_candidate_evidence_tree.py` 同层，都是 runtime explain contract。

路径：`src/factpy_kernel/core/store/_candidate_provenance_timeline.py`

### D-PT2: Shape 从 PyReasonTraceV0 诚实归一化，不伪装成 tree

核心结构是"按 component+label 分组的传播链"，每条链记录该组合的 bound 变化历史。

**Chains 排序规则冻结为 `(component_type, component, label)` 字典序。**

**Root chain 用 `root_chain_key` 标识，不用 index。** `root_chain_key` 是 `(component_type, component, label)` 三元组，由 candidate payload 推算。这避免了 chain 排序变化导致的 index 漂移。

```python
{
    "kind": "candidate_provenance_timeline",
    "candidate_id": "...",
    "engine": "pyreason",
    "timesteps": 3,
    "chains": [
        {
            "component": "ACME_CLOUD",
            "component_type": "node",
            "label": "at_risk_signal",
            "events": [
                {
                    "time": 0,
                    "fixpoint_op": 1,
                    "old_bound": [0.0, 1.0],
                    "new_bound": [1.0, 1.0],
                    "trigger": "seed_fact",
                    "groundings": []
                }
            ]
        },
        {
            "component": "PAYMENTS_GATEWAY",
            "component_type": "node",
            "label": "at_risk_signal",
            "events": [
                {
                    "time": 1,
                    "fixpoint_op": 2,
                    "old_bound": [0.0, 1.0],
                    "new_bound": [1.0, 1.0],
                    "trigger": "vendor_risk_propagation",
                    "groundings": ["[ACME_CLOUD]", "[(PAYMENTS_GATEWAY, ACME_CLOUD)]"]
                }
            ]
        }
    ],
    "root_chain_key": ["node", "PAYMENTS_GATEWAY", "at_risk_signal"]
}
```

**因果关系边界：** `groundings` 原样保留自 `PyReasonTraceV0.clause_groundings`。合同**不保证** `groundings` 可被解析为稳定的 cross-chain dependency edges。当前 adapter 文档明确禁止把 `clause_groundings` 强行解释为统一 body-atom dependency edge（缺少稳定锚点）。消费者应将 `groundings` 视为不透明的调试信息，不作为因果推断的输入。

### D-PT3: 不复用 CandidateEvidenceTree 的 certainty pipeline

CandidateEvidenceTree 的 certainty 依赖 `rule_ref_edges` + `condition_weights`，PyReason event log 没有这些。

PyReason 的"不确定性"语义是 bound interval 本身，不是 condition_weights × fact_confidence。Timeline summary 中提供 `final_bound`，如果需要 scalar confidence 由 adapter 从 bound 派生，不走 certainty pipeline。

### D-PT4: `explain_runtime_tree` 不改，新增独立 `explain_runtime_timeline` 端点

**不改现有 `explain-tree` / `explain-summary` / `explain-narrative` 的 DTO shape。** 这些端点对 native/souffle 行为完全不变，对 pyreason/problog 继续返回 `runtime_explain_not_supported` 错误。

新增独立端点，**冻结 top-level `kind` 字段**（与现有 explain 端点约定一致）：

| 新端点 | top-level `kind` | payload key | 消费合同 |
|--------|------------------|-------------|---------|
| `explain_runtime_timeline` | `"candidate_provenance_timeline"` | `"timeline"` | pyreason only |
| `explain_runtime_timeline_summary` | `"candidate_provenance_timeline_summary"` | `"summary"` | pyreason only |
| `explain_runtime_timeline_narrative` | `"candidate_provenance_timeline_narrative"` | `"narrative"` | pyreason only |

Response envelope 示例：

```python
# explain_runtime_timeline
{"ok": True, "kind": "candidate_provenance_timeline", "timeline": {...}}

# explain_runtime_timeline_summary
{"ok": True, "kind": "candidate_provenance_timeline_summary", "summary": {...}}

# explain_runtime_timeline_narrative
{"ok": True, "kind": "candidate_provenance_timeline_narrative", "narrative": {...}}
```

对非 pyreason candidate 调这些新端点返回 `runtime_explain_not_supported`。

这避免了把 service v1 的固定 DTO 打碎。消费者通过 `support_kind` 决定调哪组端点。

**内部 dispatch 仍可共享 `_get_candidate_explain()` helper**，但外部端点保持分离。

### D-PT5: `explain_runtime_nl` 对 PyReason 已接入 timeline NL

~~V1 不实现 timeline NL explain。~~ **已撤回。**

`explain_runtime_nl(kind="candidate")` 现在对 PyReason candidate 做 early dispatch：
1. 检测 `support_kind == PYREASON_PROVENANCE_KIND`
2. 走 timeline → summary → narrative → NL 管线
3. 返回 `kind="candidate_provenance_timeline_nl_explain"`

NL 函数 `render_candidate_provenance_timeline_nl_explain(summary, narrative)` 放在 `_candidate_provenance_timeline.py`，与 tree NL 完全对称，输出 `{"headline": str, "paragraphs": [str, ...]}`。

### D-PT6: ProbLog deferred

ProbLog 的 trace 更接近 tree（call frame），将来可以：
- 建 `CandidateProvenanceTrace`（call-frame tree 合同）
- 或尝试 bridge 到 CandidateEvidenceTree

不在本蓝图 scope。新端点对 problog 返回 `runtime_explain_not_supported`。

### D-PT7: Audit package 新增 `provenance_timelines.jsonl`

当前 `ProvenanceEnvelope` 是 session-scoped，不进 audit package。`evidence_graphs.jsonl` 是 EvidenceGraph 级别的低保真输出，不能替代高保真 timeline。

新增 durable artifact：

```
audit_package/
  ...
  evidence_graphs.jsonl           # (现有) EvidenceGraph 统一可视化
  provenance_timelines.jsonl      # (新) CandidateProvenanceTimeline 高保真 timeline
```

行格式与现有 audit package 约定一致（固定字段行，非 key-value 嵌套）：

```jsonl
{"candidate_id": "abc123", "provenance_timeline": { ... full CandidateProvenanceTimeline dict ... }}
{"candidate_id": "def456", "provenance_timeline": { ... }}
```

**需同步更新：**
- `manifest.paths.audit_files` — 新增 `provenance_timelines` optional key
- `audit/reader.py` — optional key 列表新增 `provenance_timelines`，parse 逻辑与 `evidence_graphs.jsonl` 对齐

`AuditPackageData` 新增字段：
```python
provenance_timelines: dict[str, dict[str, Any]]  # candidate_id → timeline dict
```

`AuditQuery` 新增：
```python
def get_candidate_provenance_timeline(self, candidate_id: str) -> dict | None:
    return self._data.provenance_timelines.get(candidate_id)

def get_candidate_timeline_summary(self, candidate_id: str) -> dict | None:
    timeline = self.get_candidate_provenance_timeline(candidate_id)
    if timeline is None:
        return None
    return summarize_candidate_provenance_timeline(timeline)
```

## 4. Existing Architecture (不动)

### 4.1 Runtime Explain Dispatch (现状，不改)

```
explain_runtime_tree/summary/narrative/nl
    ↓
_get_candidate_tree(candidate_id)
    ↓
get_candidate_support_kind(candidate_id)
    ├─ WITNESS_BEARING (native_binding_v1, souffle_witness_v1)
    │  └─→ build_candidate_evidence_tree()     ✓ 完整 tree
    ├─ DEGRADED (none, engine_no_witness_v1)
    │  └─→ build_degraded_candidate_evidence_tree() ✓ 最小 tree
    └─ PROVENANCE (pyreason_provenance_v1, problog_provenance_v1)
       └─→ raise runtime_explain_not_supported  ✗ 保持报错
```

### 4.2 Store Parallel Lookups

- `_support_artifacts` — SupportArtifact (witness-bearing)
- `_provenance_envelopes` — ProvenanceEnvelope (provenance-bearing)
- `_candidate_support_kind_index` — candidate_id → support_kind

### 4.3 EvidenceGraph (不动)

`audit/evidence_graph.py` 的 `EvidenceGraph` + renderer + converter 全部不动。
`CandidateProvenanceTimeline` 和 `EvidenceGraph` 是平行的两个消费面：

- `CandidateProvenanceTimeline` → runtime explain（高保真，engine-specific）
- `EvidenceGraph` → audit/static 可视化（统一，最小共享抽象）

## 5. Proposed Changes

### 5.1 `CandidateProvenanceTimeline` Data Model

```python
# core/store/_candidate_provenance_timeline.py

@dataclass(frozen=True)
class TimelineEvent:
    time: int
    fixpoint_op: int
    old_bound: tuple[float, float]
    new_bound: tuple[float, float]
    trigger: str                        # rule label or "seed_fact"
    groundings: tuple[str, ...]         # opaque clause grounding strings

@dataclass(frozen=True)
class TimelineChain:
    component: str                      # node/edge identifier
    component_type: str                 # "node" or "edge"
    label: str                          # predicate short name
    events: tuple[TimelineEvent, ...]   # ordered by (time, fixpoint_op)

@dataclass(frozen=True)
class CandidateProvenanceTimeline:
    candidate_id: str
    engine: str                         # "pyreason"
    timesteps: int
    chains: tuple[TimelineChain, ...]   # sorted by (component_type, component, label)
    root_chain_key: tuple[str, str, str]  # (component_type, component, label)
```

### 5.2 Builder

```python
# core/store/_candidate_provenance_timeline.py

def build_candidate_provenance_timeline(
    candidate_id: str,
    envelope: ProvenanceEnvelope,
    candidate_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build CandidateProvenanceTimeline from PyReasonTraceV0.

    - Groups events by (component_type, component, label)
    - Sorts chains by (component_type, component, label) lexicographic
    - Finds root chain key from candidate payload
    - Returns dict with kind="candidate_provenance_timeline"
    """
```

### 5.3 Timeline Summary

```python
def summarize_candidate_provenance_timeline(timeline: dict) -> dict:
    return {
        "explain_kind": "timeline",
        "timesteps": timeline["timesteps"],
        "chain_count": len(timeline["chains"]),
        "seed_count": ...,              # chains where first event trigger is "seed_fact"
        "derived_count": ...,           # chains where first event trigger is a rule
        "trigger_rules": [...],         # unique rule labels
        "final_bound": [...],           # root chain's last event new_bound
    }
```

### 5.4 Timeline Narrative

V1 narrative 保持 **chain-local**，不从 groundings 推断跨链因果。

```python
def render_candidate_provenance_timeline_narrative(timeline: dict) -> dict:
    # Each propagation line describes ONE chain's events,
    # NOT cross-chain causal inference.
    # groundings are echoed as-is for debugging, not parsed.
    return {
        "headline": "at_risk_signal: 3 chains, 2 timesteps, converged at t=2",
        "propagation_lines": [
            "t=0: ACME_CLOUD.at_risk_signal seeded [1.0, 1.0]",
            "t=1: PAYMENTS_GATEWAY.at_risk_signal updated to [1.0, 1.0] by vendor_risk_propagation",
            "t=2: MOBILE_BANKING_APP.at_risk_signal updated to [1.0, 1.0] by vendor_risk_propagation",
        ],
        "seed_summary": "1 seed chain",
        "convergence": "Fixed point at t=2",
    }
```

注意：`propagation_lines` 里不出现 `← rule(SOURCE)` 这种跨链因果推断。每行只描述该 chain 自己的 bound 变化和 trigger rule label。

### 5.5 New Runtime Endpoints (runtime_v1.py)

```python
def explain_runtime_timeline(session_id, params):
    """New endpoint — returns CandidateProvenanceTimeline for pyreason candidates."""
    candidate_id = params["id"]
    support_kind = _lookup_candidate_support_kind(session, candidate_id)
    if support_kind != PYREASON_PROVENANCE_KIND:
        raise _runtime_explain_not_supported(
            f"explain-timeline requires pyreason provenance, got {support_kind}")
    envelope = session.store.explain_provenance(support_digest)
    timeline = build_candidate_provenance_timeline(candidate_id, envelope, payload)
    return {"ok": True, "kind": "candidate_provenance_timeline", "timeline": timeline}

def explain_runtime_timeline_summary(session_id, params):
    """New endpoint — returns timeline summary for pyreason candidates."""
    timeline_resp = explain_runtime_timeline(session_id, params)
    summary = summarize_candidate_provenance_timeline(timeline_resp["timeline"])
    return {"ok": True, "kind": "candidate_provenance_timeline_summary", "summary": summary}

def explain_runtime_timeline_narrative(session_id, params):
    """New endpoint — returns timeline narrative for pyreason candidates."""
    timeline_resp = explain_runtime_timeline(session_id, params)
    narrative = render_candidate_provenance_timeline_narrative(timeline_resp["timeline"])
    return {"ok": True, "kind": "candidate_provenance_timeline_narrative", "narrative": narrative}
```

现有 `explain_runtime_tree/summary/narrative/nl` **完全不改**。

### 5.6 Audit Package Extension

Export 增加 `provenance_timelines.jsonl`：

```python
# In audit package export:
provenance_timelines = {}
for cid, support_kind in candidate_support_kinds.items():
    if support_kind == PYREASON_PROVENANCE_KIND:
        envelope = session.store.explain_provenance(support_digests[cid])
        timeline = build_candidate_provenance_timeline(cid, envelope, payloads[cid])
        provenance_timelines[cid] = timeline

# Write provenance_timelines.jsonl — one line per candidate:
# {"candidate_id": "abc123", "provenance_timeline": { ... }}
for cid, tl in provenance_timelines.items():
    jsonl_line = {"candidate_id": cid, "provenance_timeline": tl}
    # write to provenance_timelines.jsonl
```

`AuditPackageData` 新增：
```python
provenance_timelines: dict[str, dict[str, Any]]  # candidate_id → timeline dict
```

`AuditQuery` 新增：
```python
def get_candidate_provenance_timeline(self, candidate_id: str) -> dict | None:
    return self._data.provenance_timelines.get(candidate_id)

def get_candidate_timeline_summary(self, candidate_id: str) -> dict | None:
    timeline = self.get_candidate_provenance_timeline(candidate_id)
    if timeline is None:
        return None
    return summarize_candidate_provenance_timeline(timeline)
```

## 6. Three-Layer Explain Surface (最终状态)

```
                    native/souffle         pyreason              problog
                    ──────────────         ────────              ───────
Engine carrier:     SupportArtifact        PyReasonTraceV0       ProbLogTraceV0
                         │                      │                     │
Runtime contract:   CandidateEvidence    CandidateProvenance    (deferred)
                    Tree                 Timeline
                         │                      │                     │
                    ┌────┴────┐           ┌─────┴─────┐               │
Runtime endpoints:  │explain- │           │explain-    │               │
                    │tree     │           │timeline    │               │
                    │summary  │           │timeline-   │               │
                    │narrative│           │summary     │               │
                    │NL       │           │timeline-   │               │
                    │certainty│           │narrative   │               │
                    └────┬────┘           └─────┬─────┘               │
                         │                      │                     │
Audit durable:      support_artifacts     provenance_timelines        │
                    certainty_summaries   .jsonl                      │
                    provenance_trees                                  │
                         │                      │                     │
Audit visualization:     └─────── EvidenceGraph ─────────────────────┘
                                 (tree / timeline / tree)
```

## 7. Non-goals

- 不动 CandidateEvidenceTree 和现有 `explain-tree/summary/narrative/nl` 端点
- 不动 EvidenceGraph 数据模型和 renderer
- 不实现 ProbLog runtime explain
- ~~不实现 NL explain for timeline（第一轮）~~ → **已实现**
- 不实现 certainty for timeline（PyReason 的"certainty"是 bound interval，不是 condition_weights 体系）
- 不做 cross-chain causal edges（和 parent 蓝图一致：不伪造 cross-fact causal edges）
- 不从 `groundings` 推断跨链因果到 narrative（V1 narrative chain-local only）

## 8. Implementation Plan

| Step | 内容 | 碰现有 explain？ |
|------|------|-----------------|
| 1 | `CandidateProvenanceTimeline` dataclasses + builder | ❌ 新文件 |
| 2 | `summarize_candidate_provenance_timeline()` | ❌ 新文件 |
| 3 | `render_candidate_provenance_timeline_narrative()` | ❌ 新文件 |
| 4 | `explain_runtime_timeline/summary/narrative` 新端点 | ✅ 新增到 runtime_v1.py（不改现有） |
| 5 | Audit export: `provenance_timelines.jsonl` | ✅ 改 package.py |
| 6 | `AuditPackageData` + `AuditQuery` 扩展 | ✅ 改 reader.py + query.py |
| 7 | Tests | — |

Step 1-3 完全不碰现有代码。Step 4 只新增端点，不改现有端点。Step 5-6 是 additive change。

## 9. Acceptance Criteria

- [ ] `build_candidate_provenance_timeline()` 从 PyReasonTraceV0 正确构建 timeline
- [ ] chains 按 `(component_type, component, label)` 字典序排列
- [ ] `root_chain_key` 正确匹配 candidate payload
- [ ] `explain_runtime_timeline()` 对 pyreason candidate 返回完整 timeline
- [ ] `explain_runtime_timeline()` 对非 pyreason candidate 返回 `runtime_explain_not_supported`
- [ ] `explain_runtime_timeline_summary()` 返回 timeline summary
- [ ] `explain_runtime_timeline_narrative()` 返回 chain-local narrative（无跨链因果推断）
- [ ] 现有 `explain_runtime_tree/summary/narrative/nl` 行为**完全不变**（回归测试）
- [x] `explain_runtime_nl()` 对 pyreason 走 timeline NL 管线，返回 `candidate_provenance_timeline_nl_explain`
- [ ] Audit package 包含 `provenance_timelines.jsonl`
- [ ] `AuditQuery.get_candidate_provenance_timeline()` 可正确读回
- [ ] `AuditQuery.get_candidate_timeline_summary()` 可正确读回
- [ ] 605+ tests green
