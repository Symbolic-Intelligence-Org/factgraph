# Audit Log: S6d — audit facade + final flat-DAG purge

Paired with [2026-06-09_explain-layer-s6d-audit-facade.md](./2026-06-09_explain-layer-s6d-audit-facade.md).

---

## A. Preflight (2026-06-09)

S6a–c 后 production 旧 flat-DAG 残留(实测):
- `audit/evidence_graph.py`(648 行)= 旧 flat-DAG 全套(EvidenceNode:36 / EvidenceEdge:54 / EvidenceGraph(nodes,edges):71 / render_evidence_graph_html:129 / flat 渲染器)。
- `explanation_render.py`:`walk_evidence`(:42)双轨 —— 旧 `graph.nodes/edges`(:55-57 **死**)+ 新 `_walk_paths_evidence`(:80);import 旧 EvidenceNode/Edge(:19/21);被 evaluate_result:334 用。
- `audit/__init__`:re-export 旧 symbols(:27-31)。
- `render_evidence_graph_html`:仅 audit/__init__ re-export,**无 production 消费者**。
- test_explanation_render.py 用旧 EvidenceNode/Edge。

→ 无 active producer 产旧 flat-DAG(adapter + evaluate_result 全迁),可安全清。

## B. Locked decisions

- `audit/evidence_graph.py` → thin re-export application.explain(单一定义来源);删旧定义/HTML 渲染器。
- `walk_evidence` paths-only(删死旧轨)。
- `audit/__init__` re-export 新 symbols,删 EvidenceNode/Edge/render_html。
- 全树 production 旧 flat-DAG symbol 归零。
- 不碰 audit query / package contract。

## C. Open items for Codex

- audit.evidence_graph re-export 的 `__all__` 范围(EvidenceGraph/Tree/Timeline/Rule/Atom/to_dict/from_dict;是否含 LAYOUT_* 等)—— 对齐 application.explain 公开面。
- `render_evidence_graph_html` 确认无外部/test 消费者后删(preflight 显示仅 audit/__init__ re-export)。
- walk_evidence 删旧轨后,确认 `_walk_paths_evidence` 覆盖所有 status(passed/failed)路径。

## D. Gate result (Claude 独立验证 2026-06-09)

impl `aa713d9b`(parent = S6d 蓝图 `dce5af78`,线性栈)。**PASS**:
- ★全树旧 flat-DAG symbol(EvidenceNode/EvidenceEdge/NodeKind/EdgeKind/root_node_id/render_evidence_graph_html)在 src/factgraph + tests **0 命中**。
- audit/evidence_graph.py = 61 行 thin re-export(`from factgraph.application.explain import` 全套)。
- walk_evidence paths-only(删死旧轨);audit/__init__ 导出新 DTO。
- **全 explain cohort 114 OK(独立)**:prober + evaluate_result + render + souffle/problog/pyreason + audit + rule_expr + schema / Codex 122。

裁决:**PASS**。v2 实现收官。

## E. 程序里程碑

S0–S6(S6 拆 a–d)+ cleanup 全部 implemented + gate-pass。旧 flat-DAG 模型彻底移除,EvidenceGraph 全走 paths-model。G1–G7 + INV-baseline-monorepo + 单线性栈 + 每片集成闸 全部满足。
