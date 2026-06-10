# Task Blueprint: S6b — ProbLog adapter → paths-model + dispatch

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/adapters/problog/provenance.py`(迁 converter 到 paths-model)
  - `src/factgraph/sdk/store.py`(problog engine graph_builder dispatch via `_row_provenance_envelopes`)
- Related Docs:
  - Design spec §6(problog→tree,多 proof→多 tree): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s6b-problog.audit.md](./2026-06-09_explain-layer-s6b-problog.audit.md)

---

## 1. Problem

S6 第二片(复用 S6a 的 per-engine dispatch + Q-S6-A fallback pattern)。迁 problog converter 到 paths-model + 接 dispatch,使 problog row 不再走 minimal fallback。

## 2. Goals

1. `problog_trace_to_evidence_graph(...)` 返回 **`application.explain.EvidenceGraph(paths=(EvidenceTree,...))`**;import 改 `application.explain`,**不再** import `audit.evidence_graph`。
2. **多 proof → 多 EvidenceTree**(design §6:457:`ProbLogTraceV0.answers` 每 answer 一棵 tree);每 tree `certainty=Certainty(p,p,"probabilistic")`;聚合概率 → `EvidenceGraph.certainty`(§6:433)。
3. SDK `_row_graph_builder_for_engine` 加 `engine=="problog"` 分支:经 `_row_provenance_envelopes`(ProvenanceEnvelope, PROBLOG_PROVENANCE_KIND)调 converter。
4. **Q-S6-A fallback**:converter 失败 → minimal paths(保 `{passed,failed}↔evidence`,不返 unsupported)。

## 3. Non-goals

- PyReason(S6c)/ Souffle(S6a 已完成)。
- `audit/evidence_graph.py` re-export / 旧 flat-DAG 终清(S6d)。
- 内联派生 IDB 子图(design §6:434:v1 不产)。
- 改 problog 执行/runner(只动 provenance converter + dispatch)。

## 4. Current Context(preflight 已完成)

- `problog_trace_to_evidence_graph`(provenance.py:187,794 行)现 build call frames → nodes/edges(flat-DAG);import 自 `audit.evidence_graph`(:10/16-18)。
- `ProbLogTraceV0.answers: tuple[ProbLogAnswerV0,...]`(:59)= 多 proof。
- SDK:`_row_graph_builder_for_engine`(store.py:2815,S6a 建)+ `_row_provenance_envelopes`(:2808 注入,`PROBLOG_PROVENANCE_KIND`:94)。
- S6a pattern:per-engine builder + minimal fallback,可直接复用。
- v1 曾做 problog paths 迁移(结构参考)。

## 5. Proposed Shape

- converter:每 `answer` → 一棵 `EvidenceTree`(head/body rules + atoms,结构同 souffle/native);`tree.certainty=Certainty(p,p,"probabilistic")`;`EvidenceGraph.certainty` = 聚合概率;`EvidenceGraph(paths=tuple(trees), ...)`。
- SDK:新 `_problog_row_graph_builder(row_provenance_envelopes)`;engine==problog 时 dispatch;per-row 取 envelope → `problog_trace_from_dict` → converter;失败 minimal。

## 6. Boundaries And Invariants

- converter 产 **paths-model**;problog/provenance.py **不再 import audit.evidence_graph**。
- **多 proof → 多 tree**(不压平成单 tree)。
- **Q-S6-A**:converter 失败回 minimal(保 `{passed,failed}↔evidence`)。
- **scope 限 problog**:不碰 pyreason/souffle/audit facade。
- INV-6;单线性栈(S6a 之上)。

## 7. Acceptance

- [ ] ProbLog converter 返回 `application.explain.EvidenceGraph(paths=...)`
- [ ] **多 answer → 多 EvidenceTree**;每 tree `certainty.kind=="probabilistic"`(p,p);聚合 → `EvidenceGraph.certainty`
- [ ] SDK explain on ProbLog row **不走 minimal fallback**;`EvidenceTree.rules` 含 head/body,atoms 非空
- [ ] converter failure fallback 仍满足 `{passed,failed} ↔ evidence`
- [ ] `problog/provenance.py` **不再 import** `audit.evidence_graph`
- [ ] **不碰** PyReason/Souffle/audit facade
- [ ] 受影响 problog docs/test 更新

## 8. Implementation Plan

1. `problog/provenance.py`:converter 改 import `application.explain` + 每 answer build EvidenceTree(probabilistic certainty)+ 聚合 graph certainty;删 nodes/edges 路径。
2. `sdk/store.py`:`_problog_row_graph_builder`;engine==problog dispatch;per-row envelope→converter;失败 minimal。
3. 测试:problog 多 tree + probabilistic certainty + dispatch 非 minimal + fallback 不变式 + import grep 归零;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/adapters/docs/02_problog_adapter.md`(若述及 evidence 形态)。

## 10. Outcome / Deviations

**落地**:impl `0d48de22`(线性栈 `… → 3e28bcf3(S6b蓝图) → 0d48de22(S6b code)`);master 未动,未 push。

**结果**:problog converter 迁 paths(import `application.explain.evidence_tree`:10;`paths=trees`:239;per-answer EvidenceTree:288;`Certainty(probabilistic)`:385/398);多 answer→多 tree;聚合 → graph certainty。SDK `_problog_row_graph_builder`(store.py:2865)engine==problog dispatch via `_row_provenance_envelopes` + envelope→`problog_trace_from_dict`→converter;失败 minimal。

**Gate(我独立验证)**:
- scope-limit:pyreason/souffle/audit **未碰**。
- `test_converter_maps_multiple_answers_to_multiple_trees`:`len(paths)==2`(多 answer→多 tree);graph+tree `certainty.kind=="probabilistic"`(:72/77)。
- problog/provenance.py 不再 import audit;dispatch 非 minimal;fallback 不变式。
- cohort 49 OK(独立)/ Codex 41 + 105。

**归档**:暂留 active/,随里程碑批量归档。
