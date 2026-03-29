# Task Blueprint: Timeline Renderer Edge Visualization

- Status: implemented
- Created: 2026-03-30
- Last Updated: 2026-03-30
- Related Modules:
  - `src/factpy_kernel/audit/evidence_graph.py`
- Audit Log:
  - [2026-03-30_evidence-graph-timeline-edges.audit.md](./2026-03-30_evidence-graph-timeline-edges.audit.md)

## 1. Problem

F-EG-2：Timeline renderer 只展示 node cards 在 timestep × component grid 中的分布，不渲染 edges。PyReason converter 产出的 `EDGE_UPDATES` 链在 timeline 中不可见。

## 2. Goals

- 在 timeline card 下方渲染 incoming edge 注释
- 复用 tree renderer 的 `_render_edge_note` 风格
- 无 edge 时什么也不渲染（退化行为明确）

## 3. Non-goals

- 不引入 SVG overlay 或 CSS connector
- 不重做 grid 布局结构
- 不改 EvidenceGraph 数据模型
- 不改 tree renderer

## 4. Acceptance

- [x] `edge_kind="updates"` 在 timeline HTML 中可见
- [x] edge 跨 timestep / 跨 component 时退化行为稳定
- [x] 无 edge 时不产出 edge-note div
- [x] 1 个新测试 + 1 个扩展测试（增加 edge 断言）
- [x] 全量回归绿（605 passed）

## 5. Implementation Plan

1. `_render_timeline_layout` — 构建 incoming_edges + node_by_id
2. `_render_timeline_card` — 接收并渲染 incoming edge 注释
3. 调用点传参
4. 补测试
5. 更新 `02_evidence_graph.md`
