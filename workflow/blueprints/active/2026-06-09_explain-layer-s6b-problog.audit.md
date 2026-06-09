# Audit Log: S6b — ProbLog adapter → paths-model

Paired with [2026-06-09_explain-layer-s6b-problog.md](./2026-06-09_explain-layer-s6b-problog.md).

---

## A. Preflight (2026-06-09)

- `problog_trace_to_evidence_graph`(provenance.py:187,794 行)现 build call frames → nodes/edges(flat-DAG);import 自 `audit.evidence_graph`(:10/16-18)。
- `ProbLogTraceV0.answers`(:59)= 多 proof。
- SDK:`_row_graph_builder_for_engine`(store.py:2815,S6a 建)+ `_row_provenance_envelopes`(:2808;`PROBLOG_PROVENANCE_KIND`:94)。

## B. Locked decisions(复用 S6a pattern)

- problog converter → paths-model;每 answer 一棵 EvidenceTree;`tree.certainty=Certainty(p,p,"probabilistic")`;聚合 → `EvidenceGraph.certainty`(design §6:433/457)。
- dispatch via `_row_provenance_envelopes`(per-engine builder,S6a 的 `_row_graph_builder_for_engine` 加 problog 分支)。
- Q-S6-A fallback:失败 → minimal(保不变式)。
- scope 限 problog;不碰 pyreason/souffle/audit。

## C. Open items for Codex

- envelope → ProbLogTraceV0 提取(`problog_trace_from_dict`);answer→EvidenceTree 的 head/body 映射(结构同 souffle/native)。
- 聚合概率 → `EvidenceGraph.certainty` 的算法(多 answer 时取何值;design §6 "聚合存 EvidenceGraph.certainty",具体聚合你定/记录)。
- repr_text 最小(schema 烘焙非重点)。

## D. Gate result / Deviations

impl + gate 后填写。
