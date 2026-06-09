# Audit Log: S6c — PyReason adapter → paths-model timeline

Paired with [2026-06-09_explain-layer-s6c-pyreason.md](./2026-06-09_explain-layer-s6c-pyreason.md).

---

## A. Preflight (2026-06-09)

- `pyreason_trace_to_evidence_graph`(provenance.py:113,387 行)现 build nodes/edges(flat-DAG);import 自 `audit.evidence_graph`(:17/23-25);trace 有 `timesteps`(:55)。
- 目标:`EvidenceTimeline`(evidence_tree.py:141)+ `EvidenceAtom.timestep`(:103);`LAYOUT_TIMELINE`。
- SDK:`_row_graph_builder_for_engine`(store.py:2818,S6a/b 建)+ `_row_provenance_envelopes`(`PYREASON_PROVENANCE_KIND`)。

## B. Locked decisions(复用 S6a/b pattern + design §6 R5)

- pyreason converter → `EvidenceTimeline`(events = `EvidenceAtom(timestep=...)`);`Certainty(lo,hi,"possibilistic")`;`layout_hint=LAYOUT_TIMELINE`。
- **Clause-N 解析不足 → conservative timeline shell**(Codex S6c note:不猜语义)。
- dispatch via `_row_provenance_envelopes`(per-engine builder)。
- Q-S6-A fallback:失败 → minimal。
- scope 限 pyreason;不碰 souffle/problog/audit。
- 真区间 branch_bounds 完整语义 = Track 3-post(本片 possibilistic point/保守)。

## C. Open items for Codex

- Clause-N grounding 文本解析的具体保守边界(能解析的入 event,解析不出的降级到结构 shell,不臆造 timestep/语义)—— 你定具体形态,记 audit。
- envelope → PyReasonTraceV0(`pyreason_trace_from_dict`)。
- possibilistic certainty 取值(lo/hi 来源;point vs interval)。

## D. Gate result (Claude 独立验证 2026-06-09)

impl `0ba7a900`(parent = S6c 蓝图 `b4ddebc5`,线性栈)。**PASS**:
- scope:8 文件(pyreason provenance + evaluate_result +6[provenance 校验加 pyreason] + sdk/store + docs + 3 tests);souffle/problog/audit 未碰。
- converter → `EvidenceTimeline`(import application.explain:21/24;无 audit);possibilistic;LAYOUT_TIMELINE;Clause-N grounding 存 Source.meta(无因果臆造)。
- SDK pyreason dispatch(store:2834)via `_row_provenance_envelopes`;校验扩 `("pyreason","event_log")`(evaluate_result:1069)。
- cohort 60 OK(独立;souffle+problog+pyreason+prober 全回归)/ Codex 76+96+204。

裁决:**PASS**。

## E. 里程碑 + S6d

三 adapter 全 paths-model(souffle tree / problog 多 tree / pyreason timeline)。
**剩 S6d**:无 adapter 再 import `audit.evidence_graph`(souffle/problog/pyreason 全迁)+ evaluate_result(S5)亦不用 → audit.evidence_graph **无 active producer**,可安全改 thin re-export + 全树终清旧 flat-DAG symbols。
