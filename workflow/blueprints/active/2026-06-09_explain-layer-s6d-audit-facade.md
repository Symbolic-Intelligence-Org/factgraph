# Task Blueprint: S6d — audit.evidence_graph thin re-export + final flat-DAG purge

- Status: scoped
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Type: cleanup slice(`feedback_cleanup_slice_cadence` 轻量;subtractive + facade)
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/audit/evidence_graph.py`(→ thin re-export)
  - `src/factgraph/audit/__init__.py`(re-export 新 symbols)
  - `src/factgraph/application/protocol/explanation_render.py`(去死旧 flat-DAG walk)
- Audit Log:
  - [2026-06-09_explain-layer-s6d-audit-facade.audit.md](./2026-06-09_explain-layer-s6d-audit-facade.audit.md)

---

## 1. Problem

S6a–c 后**无 production producer 再产旧 flat-DAG**(三 adapter + evaluate_result 全 paths-model)。S6d = S6 收尾(也是整个 v2 实现收尾):把旧 flat-DAG `audit.evidence_graph` 改 thin re-export + 清残留死代码(`walk_evidence` 旧轨、`render_evidence_graph_html`),全树旧 symbol 归零。

## 2. Goals

1. `audit/evidence_graph.py` → **thin re-export** of `application.explain`(paths-model `EvidenceGraph`/`EvidenceTree`/... + `evidence_graph_to_dict`/`from_dict`);删旧 `EvidenceNode`/`EvidenceEdge`/flat `EvidenceGraph`/`render_evidence_graph_html`/flat 渲染器(:36/54/71/129/203…)。
2. `explanation_render.py`:`walk_evidence` **paths-only**(删死旧轨 `graph.nodes/edges`:55-77 + `_render_atom(EvidenceNode)` 等);去 `audit.evidence_graph` import。
3. `audit/__init__.py`:re-export 新 symbols;**删** `EvidenceNode`/`EvidenceEdge`/`render_evidence_graph_html`。
4. `tests/application/protocol/test_explanation_render.py`:迁 paths-model(删 EvidenceNode/Edge)。
5. **全树终清**:`EvidenceNode`/`EvidenceEdge`/`NodeKind`/`EdgeKind`/`root_node_id`/`edge_kind`/`render_evidence_graph_html` 在 production 归零。

## 3. Non-goals

- adapter converter(S6a–c 完成)。
- prober / Explanation 不变式(S3/S5)。
- 改 audit query / package contract(只动 evidence_graph façade)。

## 4. Current Context(preflight 已完成)

- `audit/evidence_graph.py`(648 行)= 旧 flat-DAG:`EvidenceNode`(:36)/`EvidenceEdge`(:54)/`EvidenceGraph(nodes,edges)`(:71)/`render_evidence_graph_html`(:129)/flat 渲染器。
- `explanation_render.py`:`walk_evidence`(:42)双轨 —— 旧 `graph.nodes/edges`(:55-57,**死**)+ 新 `_walk_paths_evidence`(:80,`graph.paths`);import 旧 EvidenceNode/Edge(:19/21)。`walk_evidence` 被 evaluate_result:334(Explanation.repr)用。
- `audit/__init__`(:10/27-31)re-export 旧 symbols。
- `render_evidence_graph_html` 仅 audit/__init__ re-export(无 production 消费者)。
- test_explanation_render.py 用旧 EvidenceNode/Edge。

## 5. Proposed Shape

- `audit/evidence_graph.py`:整体替为 `from factgraph.application.explain import (EvidenceGraph, EvidenceTree, EvidenceTimeline, EvidenceRule, EvidenceAtom, evidence_graph_to_dict, evidence_graph_from_dict, ...)` + `__all__`;旧 flat 定义/渲染器删除。
- `explanation_render.py`:`walk_evidence` 直接走 `_walk_paths_evidence`(graph.paths);删旧轨 + EvidenceNode/Edge import。
- `audit/__init__`:re-export 新 paths-model symbols;删 EvidenceNode/EvidenceEdge/render_html。
- test_explanation_render:用 paths-model 构造(EvidenceGraph(paths=...))。

## 6. Boundaries And Invariants

- thin re-export 保留 `audit.evidence_graph` namespace(向后兼容 audit docs / 外部),但定义单一来源 = `application.explain`(无双定义)。
- **全树旧 flat-DAG symbol 归零**(production)。
- `walk_evidence` 行为对 paths-model 不变(S5 测试仍绿)。
- 不碰 audit query/package contract。
- INV-6;单线性栈(S6c 之上)。

## 7. Acceptance(cleanup gates)

- [ ] `audit/evidence_graph.py` = thin re-export(无旧 `EvidenceNode`/`EvidenceEdge`/flat `EvidenceGraph`/`render_evidence_graph_html` 定义)
- [ ] `explanation_render.walk_evidence` paths-only;不再 import `audit.evidence_graph`
- [ ] `audit/__init__` 不再导出 `EvidenceNode`/`EvidenceEdge`/`render_evidence_graph_html`
- [ ] **全树 grep**:`EvidenceNode`/`EvidenceEdge`/`NodeKind`/`EdgeKind`/`root_node_id`/`render_evidence_graph_html` 在 `src/factgraph/**` production = 0
- [ ] test_explanation_render 迁 paths-model,全绿
- [ ] 全 explain cohort 回归绿(prober + 三 adapter + evaluate_result + render)
- [ ] audit docs(02_evidence_graph)更新为 paths-model re-export

## 8. Implementation Plan

1. `audit/evidence_graph.py` → re-export application.explain;删旧定义/渲染器。
2. `explanation_render.py`:walk_evidence paths-only;删死旧轨 + audit import。
3. `audit/__init__`:re-export 新 symbols。
4. test_explanation_render 迁 paths;audit docs 更新。
5. 全树 grep 归零验证;全 explain cohort 回归;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/audit/docs/02_evidence_graph.md`(thin re-export / paths-model)。

## 10. Outcome / Deviations

实施后填写。
