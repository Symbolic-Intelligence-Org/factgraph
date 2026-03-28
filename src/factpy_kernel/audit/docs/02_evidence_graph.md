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
- 写入 audit package durable artifact
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

当前 `EvidenceGraph` 仍是内存内 DTO：

- 还没有进 `AuditQuery`
- 还没有写入 audit package
- 还没有接入 `static_ui.py` 的 candidate evidence page
- Souffle converter 还没有
- PyReason converter 已在 `src/factpy_kernel/adapters/pyreason/provenance.py` 实现，但当前只产出 candidate-anchored timeline graph，不接 audit query / static UI
- ProbLog converter 已在 `src/factpy_kernel/adapters/problog/provenance.py` 实现，但当前只产出 candidate-anchored call-frame tree，不接 audit query / static UI

当前已确认的静态页插入 seam 是：

- `src/factpy_kernel/audit/static_ui.py`
  - `_render_candidate_evidence_page(...)` 内部的 `provenance_block`

也就是说，Step 4 已冻结 renderer contract；Step 6 再把这个 fragment 接到 candidate evidence page。

也就是说，当前实现只冻结共享表示层，不冻结 render contract 或 package contract。
