# EvidenceGraph（audit）

- 范围：`src/factpy_kernel/audit/evidence_graph.py`
- 最后更新：2026-03-28
- 目标读者：需要在 audit 层实现跨引擎 explainability consumer 的开发者

## 1. 角色

`EvidenceGraph` 是 `audit` 层的统一 explainability DTO。

它的职责是：

- 接住 engine-native provenance carrier 经过 converter 之后的共享骨架
- 为后续 renderer 提供统一的 node / edge / layout 入口
- 在不改写 engine truth 的前提下，给 Souffle / ProbLog / PyReason 提供同一消费抽象

它当前不负责：

- 替代各引擎自己的 provenance carrier
- 替代 Souffle 现有 `CandidateEvidenceTree`
- 替代 `static_ui.py` 的整页模板

## 2. 当前数据模型

当前 v1 暴露三个 frozen dataclass：

- `EvidenceNode`
  - `node_id`
  - `node_kind`
  - `component`
  - `label`
  - `value_summary`
  - `timestamp`
  - `engine_meta`
- `EvidenceEdge`
  - `edge_id`
  - `from_node_id`
  - `to_node_id`
  - `edge_kind`
  - `rule_label`
  - `engine_meta`
- `EvidenceGraph`
  - `graph_id`
  - `engine`
  - `root_node_id`
  - `nodes`
  - `edges`
  - `support_kind`
  - `layout_hint`
  - `metadata`

`component` 是 renderer-facing subject key，不保证一定是单一实体 identity。像 `alice→bob` 这样的关系表达也允许作为 `component`。

## 3. 冻结枚举

当前只冻结最小共享枚举：

- `layout_hint`
  - `tree`
  - `timeline`
- `node_kind`
  - `conclusion`
  - `premise`
  - `seed`
- `edge_kind`
  - `supports`
  - `derives`
  - `updates`

`dag` layout 与 `rule_fire` node kind 还不在 v1 scope。

## 4. 校验与不变量

当前 `EvidenceGraph` 在 `__post_init__` 中执行最小结构校验：

- `layout_hint` 必须是 `tree` 或 `timeline`
- `root_node_id` 必须存在于 `nodes`
- `node_id` 必须唯一
- `edge_id` 必须唯一
- 每条 edge 的端点必须引用已有 node

当前 `engine_meta` / `metadata` 会做 `MappingProxyType` 浅冻结，避免 consumer 在渲染阶段原地改写共享 DTO。

## 5. 当前渲染器

当前 `audit/evidence_graph.py` 已实现：

- `render_evidence_graph_html(graph)`
  - 根据 `layout_hint` 分派到：
    - tree renderer
    - timeline renderer
- tree renderer
  - 以 `root_node_id` 为入口
  - 当前按 edge `from -> to` 的 child-to-parent 约定，把 incoming edges 渲染成子分支
- timeline renderer
  - 当前使用 CSS grid 形态：
    - 列 = timestep
    - 行 = component
    - cell = stacked event cards

当前 renderer 产出的是 **standalone HTML fragment**，不是整页 HTML。它的设计目标是后续被 `static_ui.py` 的 candidate evidence page 直接嵌入。

## 6. 当前边界

当前 `EvidenceGraph` 已不再只是内存内 DTO：

- `audit/evidence_graph.py` 现在提供：
  - frozen dataclass DTO
  - standalone HTML fragment renderer
  - `evidence_graph_to_dict(...)` / `evidence_graph_from_dict(...)` round-trip helper
- audit package 当前可选写出 `audit/evidence_graphs.jsonl`
  - 每行 `{candidate_id, evidence_graph}`
  - 当前由 runtime export 在 export-time materialize：
    - `souffle`：从 `provenance_trees.jsonl` 的 proof tree 重建
    - `pyreason`：从 `ProvenanceEnvelope.payload` 的 event log 转换
    - `problog`：从 `ProvenanceEnvelope.payload` 的 proof trace 转换
- `AuditQuery.get_candidate_evidence_graph(...)` 会读取 durable graph
- `static_ui.py` 的 candidate evidence page 现在优先渲染 durable `EvidenceGraph`，并仅对旧 package 保留 Souffle provenance-tree fallback

当前仍保持的边界：

- runtime live `explain-tree` / `explain-summary` / `explain-narrative` / `explain-nl` 仍不直接支持 `pyreason_provenance_v1` / `problog_provenance_v1`
- `EvidenceGraph` 仍不替代 engine-native provenance carrier；durable package 只是写 converter 结果，不抹平 engine truth
- candidate evidence page 仍保留既有 Souffle provenance tree section；`EvidenceGraph` 是新增统一 explain block，不替换旧 tree viewer

## 7. Known Issues（2026-03-29 walkthrough 确认）

### F-EG-1 构造时无环检测（严重：低）

`EvidenceGraph.__post_init__` 校验 node/edge uniqueness 与端点引用，但不检测是否存在环。环检测仅在 tree renderer 渲染阶段做 `if node_id in ancestry` 防御性截断。如果 consumer 直接遍历 `edges` 而非使用 renderer，可能遇到无限递归。

- 位置：`evidence_graph.py:72-93`（构造校验）、`evidence_graph.py:204`（渲染期截断）
- 影响：当前所有 converter（Souffle/PyReason/ProbLog）产出的图均为无环；仅影响手动构造的 graph

### F-EG-2 Timeline renderer 不渲染 edges（严重：低）

Timeline renderer 只展示 node cards 在 timestep × component grid 中的分布，不可视化 edges。如果 converter 产出的 `edge_kind="updates"` 有重要语义（如 PyReason intra-fact update chain），timeline 视觉上看不到 edge 关系。

- 位置：`evidence_graph.py:250-335`

### F-EG-3 `evidence_graphs.jsonl` 重复 candidate_id 静默覆盖（严重：低）

`reader._read_evidence_graphs()` 用 dict 赋值读取 JSONL，相同 `candidate_id` 的多行会 last-wins，无 warning。

- 位置：`reader.py:186`

### F-EG-4 `static_ui._try_build_evidence_graph_from_provenance` 裸 Exception 捕获（严重：低）

该函数用 `except Exception: return None` 吞掉所有错误（含 `ImportError`、`AttributeError` 等非预期异常），使 fallback 路径的诊断困难。

- 位置：`static_ui.py:948`
