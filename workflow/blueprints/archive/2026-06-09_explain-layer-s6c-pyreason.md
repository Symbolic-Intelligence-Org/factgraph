# Task Blueprint: S6c — PyReason adapter → paths-model timeline + dispatch

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/adapters/pyreason/provenance.py`(迁 converter 到 paths-model timeline)
  - `src/factgraph/sdk/store.py`(pyreason engine graph_builder dispatch via `_row_provenance_envelopes`)
- Related Docs:
  - Design spec §6(pyreason→timeline,R5): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s6c-pyreason.audit.md](./2026-06-09_explain-layer-s6c-pyreason.audit.md)

---

## 1. Problem

S6 第三片(复用 S6a/b dispatch + Q-S6-A pattern)。迁 pyreason converter 到 paths-model **`EvidenceTimeline`**(design §6 R5:timeline 形态),接 dispatch,使 pyreason row 不再走 minimal fallback。

## 2. Goals

1. `pyreason_trace_to_evidence_graph(...)` 返回 **`application.explain.EvidenceGraph(paths=(EvidenceTimeline,...), layout_hint=LAYOUT_TIMELINE)`**;import 改 `application.explain`,**不再** import `audit.evidence_graph`。
2. timeline:`EvidenceTimeline(events=tuple[EvidenceAtom(timestep=...)])`(design §6 R5:复用 EvidenceAtom 作 timeline 叶);certainty `Certainty(lo,hi,"possibilistic")`。
3. **Clause-N 解析不足 → conservative timeline shell**(Codex S6c note:**不猜语义**;能解析的 event 入 timeline,解析不出的保守降级,不臆造)。
4. SDK `_row_graph_builder_for_engine` 加 `engine=="pyreason"` 分支:经 `_row_provenance_envelopes`(PYREASON_PROVENANCE_KIND)调 converter。
5. **Q-S6-A fallback**:converter 失败 → minimal paths(保 `{passed,failed}↔evidence`)。

## 3. Non-goals

- Souffle(S6a)/ ProbLog(S6b)已完成。
- `audit/evidence_graph.py` re-export / 旧 flat-DAG 终清(S6d)。
- PyReason 真区间 branch_bounds 完整语义(Track 3-post;本片 possibilistic point/conservative)。
- 改 pyreason 执行/runner。

## 4. Current Context(preflight 已完成)

- `pyreason_trace_to_evidence_graph`(provenance.py:113,387 行)现 build nodes/edges(flat-DAG);import 自 `audit.evidence_graph`(:17/23-25)。
- pyreason trace 有 `timesteps`(:55)。
- 目标:`EvidenceTimeline`(evidence_tree.py:141:`timeline_id`/`status`/`events`/`certainty`)+ `EvidenceAtom.timestep`(:103);`LAYOUT_TIMELINE`。
- SDK:`_row_graph_builder_for_engine`(store.py:2818,S6a/b 建)+ `_row_provenance_envelopes`;pyreason engine path(:2702)。
- S6a/b pattern:per-engine builder + minimal fallback,直接复用。

## 5. Proposed Shape

- converter:trace 的 node/edge events 按 timestep 组织成 `EvidenceTimeline.events`(`EvidenceAtom(form, verdict, atom_id, timestep=...)`);`EvidenceGraph(paths=(timeline,), layout_hint=LAYOUT_TIMELINE, certainty=possibilistic)`。
- Clause-N:能解析的 grounding → event;不足 → conservative shell(timeline 结构在但 events 保守,不臆造语义)。
- SDK:新 `_pyreason_row_graph_builder(row_provenance_envelopes)`;engine==pyreason dispatch;per-row envelope → `pyreason_trace_from_dict` → converter;失败 minimal。

## 6. Boundaries And Invariants

- converter 产 **paths-model timeline**;pyreason/provenance.py **不再 import audit.evidence_graph**。
- **conservative:解析不足不臆造**(Codex);timeline shell 优于错误语义。
- **Q-S6-A**:converter 失败回 minimal(保不变式)。
- **scope 限 pyreason**:不碰 souffle/problog/audit facade。
- INV-6;单线性栈(S6b 之上)。

## 7. Acceptance

- [ ] PyReason converter 返回 `EvidenceGraph(paths=(EvidenceTimeline,...), layout_hint=LAYOUT_TIMELINE)`
- [ ] `EvidenceTimeline.events` 为 `EvidenceAtom`(带 `timestep`);certainty `possibilistic`
- [ ] Clause-N 解析不足 → conservative shell(不臆造;测试覆盖能解析 + 降级两路)
- [ ] SDK explain on PyReason row **不走 minimal fallback**(正常情况产 timeline)
- [ ] converter failure fallback 仍满足 `{passed,failed} ↔ evidence`
- [ ] `pyreason/provenance.py` **不再 import** `audit.evidence_graph`
- [ ] **不碰** Souffle/ProbLog/audit facade
- [ ] 受影响 pyreason docs/test 更新

## 8. Implementation Plan

1. `pyreason/provenance.py`:converter 改 import `application.explain` + build EvidenceTimeline(events by timestep)+ possibilistic certainty;Clause-N 保守解析;删 nodes/edges。
2. `sdk/store.py`:`_pyreason_row_graph_builder`;engine==pyreason dispatch;per-row envelope→converter;失败 minimal。
3. 测试:timeline events + timestep + possibilistic + 保守降级 + dispatch 非 minimal + fallback 不变式 + import grep 归零;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/adapters/docs/03_pyreason_adapter.md`(若述及 evidence 形态)。

## 10. Outcome / Deviations

**落地**:impl `0ba7a900`(线性栈 `… → b4ddebc5(S6c蓝图) → 0ba7a900(S6c code)`);master 未动,未 push。

**结果**:pyreason converter 迁 `EvidenceTimeline`(import `application.explain`:21/24;events=`EvidenceAtom(timestep)`;`Certainty(possibilistic)`;`LAYOUT_TIMELINE`);Clause-N grounding 存 `Source.meta`,**不臆造因果**(conservative)。SDK `engine=="pyreason"` dispatch(store.py:2834)via `_row_provenance_envelopes`;provenance 校验扩 `("pyreason","event_log")`(evaluate_result.py:1069)。失败 minimal。

**Gate(我独立验证)**:
- scope-limit:souffle/problog/audit **未碰**(evaluate_result +6 仅 provenance 校验加 pyreason,不改 problog 行为)。
- converter → timeline,无 audit import;test_pyreason_provenance_v0 用新 EvidenceTimeline/LAYOUT_TIMELINE;timeline+timestep+interval+roundtrip 测试。
- **60 tests OK(独立)**:souffle+problog+pyreason+prober 全 adapter 同跑回归绿 / Codex 76+96+204。

**里程碑**:**三个 adapter 全部 paths-model**(souffle tree / problog 多 tree / pyreason timeline)。

**归档**:暂留 active/,随里程碑批量归档。
