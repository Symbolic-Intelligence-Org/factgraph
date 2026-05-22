# Decision + Implementation Blueprint: Evidence Graph — Unified Explain Representation

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Parent:
  - [2026-03-28_engine-provenance-surface-spike.md](./2026-03-28_engine-provenance-surface-spike.md)
- Related Modules:
  - `src/factpy_kernel/core/store/_support.py` — ProvenanceEnvelope, SupportArtifact
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` — existing Souffle tree
  - `src/factpy_kernel/adapters/pyreason/provenance.py` — PyReasonTraceV0
  - `src/factpy_kernel/adapters/problog/provenance.py` — ProbLogTraceV0
  - `src/factpy_kernel/audit/static_ui.py` — HTML rendering
  - `src/factpy_kernel/service/runtime_v1.py` — explain pipeline
- Audit Log:
  - [2026-03-28_evidence-graph-unified-explain.audit.md](./2026-03-28_evidence-graph-unified-explain.audit.md)

## 1. Problem

三个引擎（Souffle, PyReason, ProbLog）各有 provenance carrier，但 explainability surface 不统一：

- **Souffle**: 完整的 `CandidateEvidenceTree` → tree/summary/narrative/NL/HTML 全链路
- **PyReason**: `PyReasonTraceV0` → flat explain only（envelope dump）
- **ProbLog**: `ProbLogTraceV0` → flat explain only（envelope dump）

审计员看到的是三种完全不同的 explain 体验。需要一个统一的抽象层让所有引擎的 provenance 能以一致的格式被消费和渲染。

## 2. Design Principles

### Wrap, don't replace

Souffle 的 `CandidateEvidenceTree` 是项目里最成熟的 explain surface，有完整的测试覆盖和真实消费者。EvidenceGraph 不替代它，而是作为新的统一层并行存在。

### EvidenceGraph is NOT "unified evidence tree"

**EvidenceGraph is the shared cross-engine explainability representation; tree is only one rendering mode, not the universal semantic shape.**

- Souffle / ProbLog 的 provenance 是树结构 → `layout_hint = "tree"`
- PyReason 的 provenance 是时序事件日志 → `layout_hint = "timeline"`
- 未来引擎可能是 DAG → `layout_hint = "dag"`

不要把所有引擎硬塞进 tree 模型。EvidenceGraph 是"证据图"，不是"证据树"。

```
Engine carrier (raw)     → Engine-specific converter → EvidenceGraph (unified)
                                                            ↓
                                                    Unified renderer
                                                    (tree / timeline / dag)

Souffle 额外保留:
SouffleProofTreeV0 → SupportArtifact → CandidateEvidenceTree → 现有 tree viewer
```

## 3. Frozen Decisions

### D-EG1: EvidenceGraph 放 `audit/`，不放 `core/`

当前 EvidenceGraph 是消费层 DTO，不是语义内核抽象。Provenance truth 已经在各 adapter 的 carrier + `core/store/runtime.py` 的 ProvenanceEnvelope 里。EvidenceGraph 是统一 viewer DTO。

路径：`src/factpy_kernel/audit/evidence_graph.py`（或 `audit/evidence_graph/` 子包）

等到 runtime explain API 确定要直接返回 EvidenceGraph，再开单独蓝图提升到 `core/`。

### D-EG2: Timeline renderer 用 CSS grid

- 不用 `<table>`：cell 内多条 event/badge/rule note 时会变丑
- 不用 SVG：文本换行、复制、可访问性、链接都困难
- CSS grid：`div` + grid layout + sticky header，cell 内用 stacked HTML cards

第一轮不做画线，靠列/行定位表达时间因果。

### D-EG3: Souffle converter 从 `SouffleProofTreeV0` 转

从 engine-native carrier 转，不从 `CandidateEvidenceTree` 转。原因：
- 和 PyReason / ProbLog 的输入层级一致（都是 engine-native carrier）
- 能保留 negation、subproof、rule_number 等 engine 细节
- 不会把"已有 presentation tree"再转成"另一个 presentation graph"

### D-EG4: 第一轮不做 JSON 序列化

- 格式还没冻结
- 一旦进 audit package 就变成 durable artifact，要维护兼容
- 当前可以在 read/render 时由原始 carrier 即时转换
- 最多加 `to_dict()` 供测试断言

等出现第二个稳定消费者时再决定是否持久化。

### D-EG5: Integration point 是 candidate evidence page，不是 assertion detail page

Provenance/status 当前按 `candidate_id` 组织（`query.py` + `static_ui.py`）。挂 assertion page 需要额外的 assertion → candidate 反向索引，会扩 scope。

第一轮：在 `_render_candidate_evidence_page()` 里增加 unified provenance section。Souffle 的现有 tree viewer 保留作为 primary；EvidenceGraph renderer 作为 secondary（或替代 non-Souffle 引擎的 provenance 展示）。

## 4. Existing Architecture (不动)

### 4.1 Souffle 两层结构

```
Layer 1: SouffleProofNodeV0
  node_type: "axiom" | "negation" | "derived" | "subproof"
  relation: str
  args: tuple[str, ...]
  rule_number: str | None
  children: tuple[SouffleProofNodeV0, ...]

Layer 2: CandidateEvidenceTree (normalized)
  node_kind: "candidate_result" | "support_section" | "predicate_witness_group" | ...
  title: str
  children: list[dict]
  + kind-specific fields
```

### 4.2 Current Rendering (保留不动)

```
static_ui.py:
  _render_candidate_evidence_page()   ← reads CandidateEvidenceTree
  _render_provenance_node_html()      ← reads SouffleProofTreeV0 directly
  _render_candidate_evidence_node()   ← reads evidence tree nodes recursively

runtime_v1.py:
  explain_runtime_tree()              ← returns CandidateEvidenceTree
  explain_runtime_summary()           ← summarizes tree
  explain_runtime_narrative()         ← generates NL narrative
```

## 5. Proposed: EvidenceGraph Data Model

```python
from types import MappingProxyType
from typing import Any, Mapping


LAYOUT_TREE = "tree"
LAYOUT_TIMELINE = "timeline"

NODE_CONCLUSION = "conclusion"
NODE_PREMISE = "premise"
NODE_SEED = "seed"

EDGE_SUPPORTS = "supports"
EDGE_DERIVES = "derives"
EDGE_UPDATES = "updates"


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    node_kind: str
    component: str                        # renderer-facing subject key, not guaranteed unary identity
    label: str
    value_summary: str
    timestamp: int | None = None
    engine_meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine_meta", MappingProxyType(dict(self.engine_meta)))
        if self.node_kind not in (NODE_CONCLUSION, NODE_PREMISE, NODE_SEED):
            raise ValueError(f"unsupported node_kind: {self.node_kind}")

@dataclass(frozen=True)
class EvidenceEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_kind: str
    rule_label: str | None = None
    engine_meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine_meta", MappingProxyType(dict(self.engine_meta)))
        if self.edge_kind not in (EDGE_SUPPORTS, EDGE_DERIVES, EDGE_UPDATES):
            raise ValueError(f"unsupported edge_kind: {self.edge_kind}")

@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str                           # "souffle" | "pyreason" | "problog"
    root_node_id: str
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    support_kind: str                     # aligned with CandidateSet.support_kind
    layout_hint: str = LAYOUT_TREE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.layout_hint not in (LAYOUT_TREE, LAYOUT_TIMELINE):
            raise ValueError(f"unsupported layout_hint: {self.layout_hint}")

        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node_id in EvidenceGraph.nodes")

        edge_ids = [edge.edge_id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate edge_id in EvidenceGraph.edges")

        node_id_set = set(node_ids)
        if self.root_node_id not in node_id_set:
            raise ValueError(f"root_node_id '{self.root_node_id}' not in nodes")

        for edge in self.edges:
            if edge.from_node_id not in node_id_set:
                raise ValueError(f"edge from_node_id '{edge.from_node_id}' not in nodes")
            if edge.to_node_id not in node_id_set:
                raise ValueError(f"edge to_node_id '{edge.to_node_id}' not in nodes")
```

## 6. Converters

Each adapter provides a pure function:

```python
# adapters/souffle/provenance.py
def souffle_proof_tree_to_evidence_graph(
    proof_tree: SouffleProofTreeV0, candidate_id: str,
) -> EvidenceGraph: ...   # layout_hint="tree"

# adapters/pyreason/provenance.py
def pyreason_trace_to_evidence_graph(
    trace: PyReasonTraceV0, *, candidate_id: str, candidate_payload: Mapping[str, Any],
) -> EvidenceGraph: ...   # layout_hint="timeline"

# adapters/problog/provenance.py
def problog_trace_to_evidence_graph(
    trace: ProbLogTraceV0, *, candidate_id: str, candidate_payload: Mapping[str, Any],
) -> EvidenceGraph: ...   # layout_hint="tree"
```

## 7. Rendering

### 7.1 Unified Renderer

```python
# audit/evidence_graph.py
def render_evidence_graph_html(graph: EvidenceGraph) -> str:
    if graph.layout_hint == "tree":
        return _render_tree_layout(graph)
    if graph.layout_hint == "timeline":
        return _render_timeline_layout(graph)
    raise ValueError(f"unsupported layout_hint: {graph.layout_hint}")
```

### 7.2 Tree Layout (Souffle + ProbLog)

- Root at top, indented children
- Similar to existing `_render_provenance_node_html()` but consuming `EvidenceNode`
- Step 5 当前的 Souffle converter 直接消费 `SouffleProofTreeV0`，按 `root=conclusion`、`axiom=seed`、`derived/negation/subproof=premise` 映射；所有 child branch 都以 `edge_kind="supports"` 指向 parent proof node，`rule-number` / `rule text` 保留在 `rule_label + engine_meta`
- Step 3 当前的 ProbLog converter 以 call frame 为 node，不把 `result/complete/fail` 单独提升成 node
- candidate root 优先匹配 final answer/query line 的 exact goal；若 query vars 含 body-only vars，则允许 payload term subset matching

### 7.3 Timeline Layout (PyReason)

- CSS grid: columns = timesteps, rows = components
- Sticky header for timestep labels
- Cell content: stacked event cards (label + bound change + rule annotation)
- No connecting lines in v1
- Step 2 当前只保证同一 `(component_type, component, label)` 链上的 `updates` edges
- `clause_groundings` 先保留在 `engine_meta`，不伪造 cross-fact causal edges

### 7.4 Integration (candidate evidence page)

插入点已冻结为：

- `src/factpy_kernel/audit/static_ui.py`
  - `_render_candidate_evidence_page(...)` 内部的 `provenance_block`

Step 4 只产出 standalone fragment renderer；Step 6 再把它接到 candidate evidence page。

In `_render_candidate_evidence_page()`:

```python
# For PyReason / ProbLog candidates:
if evidence_graph is not None:
    html += render_evidence_graph_html(evidence_graph)

# For Souffle candidates: existing tree viewer continues to work
elif provenance_tree is not None:
    html += _render_provenance_node_html(provenance_tree["root"])
```

## 8. Non-goals

- 不替代 Souffle 的 `CandidateEvidenceTree`
- 不替代 Souffle 的现有 tree viewer / summary / narrative / NL pipeline
- 不做 EvidenceGraph → SupportArtifact 的反向映射
- 不做 cross-engine evidence merging
- 不做实时 explain
- 不序列化到 audit package（第一轮）
- 不在 assertion detail page 集成（先做 candidate evidence page）

## 9. Implementation Plan

| Step | 内容 | 碰 Souffle？ |
|------|------|-------------|
| 1 | `EvidenceGraph` data model（`audit/evidence_graph.py`） | ❌ |
| 2 | `pyreason_trace_to_evidence_graph()` converter | ❌ |
| 3 | `problog_trace_to_evidence_graph()` converter | ❌ |
| 4 | `render_evidence_graph_html()` — tree + timeline renderers | ❌ |
| 5 | `souffle_proof_tree_to_evidence_graph()` converter | 只加 converter |
| 6 | `static_ui.py` integration — candidate evidence page | 添加，不改现有 |
| 7 | Tests + docs | — |

## 10. Acceptance Criteria

- [x] EvidenceGraph data model 定义清晰（frozen dataclasses in `audit/`）
- [x] 三个 converter 各产出正确的 graph（layout_hint 正确）
- [x] Tree renderer 能渲染 Souffle + ProbLog 的 evidence
- [x] Timeline renderer（CSS grid）能渲染 PyReason 的 evidence
- [ ] Candidate evidence page 显示 unified provenance section（non-Souffle 引擎）
- [ ] Candidate evidence page 显示 unified provenance section（non-Souffle 引擎）
- [x] Souffle 现有 explain pipeline 完全不受影响
- [ ] Tests 覆盖 converter + renderer + integration

## 11. Outcome / Deviations

- 最终落地结果：
  - `audit/evidence_graph.py` 已冻结 `EvidenceNode` / `EvidenceEdge` / `EvidenceGraph` 数据模型，并提供 tree / timeline HTML renderer。
  - 三个 adapter 现在都有 converter：
    - `pyreason_trace_to_evidence_graph(...)`
    - `problog_trace_to_evidence_graph(...)`
    - `souffle_proof_tree_to_evidence_graph(...)`
  - `static_ui.py` 的 candidate evidence page 现在支持可选 `evidence_graph`，并在现有 provenance block 后追加 unified section。
  - Souffle 现有 provenance tree viewer 与 `candidate_evidence_tree` 全链路保持原样，不做替换。
- 与 blueprint 不同的地方：
  - static site generation 当前是通过 audit package 中已有的 Souffle `provenance_tree` best-effort 重建 `EvidenceGraph`；`PyReason` / `ProbLog` 的 audit package delivery 还没有直接接到同一页面。
  - Step 6 的实际落地点是“page renderer 支持统一 section + static site 对 Souffle 做重建桥接”，而不是“audit package 已能为所有引擎直接供给 EvidenceGraph”。
- 为什么会有这些调整：
  - D-EG4 明确冻结了第一轮不做 `EvidenceGraph` durable serialization；audit reader 也没有直接消费 provenance envelope 的新通道。
  - 先保持 Souffle 旧页面完全不动，只把 unified section 作为追加层，可以显著降低 static UI 的回归风险。
- 归档说明：
  - 本 blueprint 已实现并归档到 `docs/blueprints/archive/`。如果后续要让 `PyReason` / `ProbLog` 在 audit package / static site 上直接出 unified section，需要单独蓝图来定义 EvidenceGraph 的 package delivery 或 envelope-to-graph 读取通道。
