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

## D. Gate result / Deviations

impl + gate 后填写。
