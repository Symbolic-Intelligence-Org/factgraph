# Task Blueprint: S6a — Souffle adapter → paths-model + dispatch

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/adapters/souffle/provenance.py`(迁 converter 到 paths-model)
  - `src/factgraph/sdk/store.py`(souffle engine graph_builder dispatch via `_row_support_artifacts`)
  - `src/factgraph/application/explain/`(EvidenceGraph/Tree/Rule 目标类型)
- Related Docs:
  - Design spec §6(souffle→tree): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s6a-souffle.audit.md](./2026-06-09_explain-layer-s6a-souffle.audit.md)

---

## 1. Problem

S5 把 native explain 接到 prober(paths-model),但 adapter converter 还是旧 flat-DAG。S6a(S6 第一片,最简,验证 adapter dispatch 模式):迁 souffle converter 到 paths-model + 接 dispatch,使 souffle row 不再走 minimal fallback。逐引擎拆(S6a→d),adapter 各自先改 import,audit re-export 留 S6d。

## 2. Goals

1. `souffle_proof_tree_to_evidence_graph(...)` 返回 **`application.explain.EvidenceGraph(paths=(EvidenceTree,...))`**(非旧 nodes/edges);import 改 `application.explain`,**不再** import `factgraph.audit.evidence_graph`。
2. proof tree → EvidenceTree:root(conclusion)→ `EvidenceRule(role="head")`;rule applications → body `EvidenceRule`;axiom/seed → `EvidenceAtom`(Holds + Source)。
3. SDK `_row_graph_builder` 扩 `engine=="souffle"` 分支:经 `_row_support_artifacts`(ProofReceipt → SouffleProofTreeV0)调 converter。
4. **Q-S6-A fallback**:converter 失败 → minimal paths graph(`_build_minimal_row_evidence_graph`),仍满足 `{passed,failed}↔evidence`,**不返回 unsupported**。

## 3. Non-goals

- ProbLog(S6b)/ PyReason(S6c)。
- `audit/evidence_graph.py` re-export / 旧 flat-DAG 终清(S6d)。
- prober(native)逻辑(S5 已定)。
- 改 souffle 执行/runner(只动 provenance converter + dispatch)。

## 4. Current Context(preflight 已完成)

- `souffle_proof_tree_to_evidence_graph`(provenance.py:48)现 build `nodes: list[EvidenceNode]` + `edges`(flat-DAG;`NODE_CONCLUSION`/`NODE_SEED`);import 自 `factgraph.audit.evidence_graph`(:11)。
- SDK:`_row_support_artifacts_for_candidates`(store.py:2840)→ `Mapping[str, ProofReceipt]`(`_lookup_support_artifact(candidate.support_digest)`,:2849);注入 :2790。
- S5 dispatch:`_row_graph_builder`(:2785)仅 `engine=="native"`;souffle row 当前落 minimal fallback。
- 目标类型:`EvidenceGraph`(:153)/`EvidenceTree`(:128)/`EvidenceRule`(:115)/`EvidenceAtom`/`Source`(application/explain)。
- v1 曾做过 souffle paths 迁移(结构可参考;v1 问题在别处)。

## 5. Proposed Shape

- converter:遍历 SouffleProofTreeV0 节点 → 一条(或多条)`EvidenceTree`;root → head rule;内部 rule node → body rule(occurrence/rule_number);axiom → `EvidenceAtom(form=Fact, verdict=Holds(BOOLEAN_CERTAINTY, support=(Source(...),)))`;`repr_text` 可由 atom_text 给最小值(schema 烘焙非本片重点)。
- SDK:新 `_row_graph_builder_for_souffle(...)`(类比 native),engine==souffle 时注入;per row 从 `_row_support_artifacts` 取 ProofReceipt → SouffleProofTreeV0 → converter;失败 → minimal。
- dispatch 选择:`_row_graph_builder` 按 engine 注入对应 builder。

## 6. Boundaries And Invariants

- converter 产 **paths-model**;souffle/provenance.py **不再 import audit.evidence_graph**。
- **Q-S6-A**:converter 失败回 minimal paths(保 `{passed,failed}↔evidence`)。
- **scope 限定 souffle**:不碰 problog/pyreason/audit facade(避免扩面)。
- 协议层不变(S5 的 `_row_graph_builder` 接缝复用)。
- INV-6;单线性栈(S5 之上)。

## 7. Acceptance(Codex 提案,已锁)

- [ ] Souffle converter 返回 `application.explain.EvidenceGraph(paths=...)`
- [ ] SDK explain on Souffle row **不走 minimal fallback**(正常情况产 converter 树)
- [ ] `EvidenceTree.rules` 至少含 head/body rule,atoms 非空
- [ ] converter failure fallback 仍满足 `{passed,failed} ↔ evidence`
- [ ] `souffle/provenance.py` **不再 import** `factgraph.audit.evidence_graph`
- [ ] **不碰** ProbLog/PyReason/audit facade
- [ ] 受影响 souffle docs/test 更新

## 8. Implementation Plan

1. `souffle/provenance.py`:converter 改 import `application.explain` + build EvidenceTree(head/body/atoms);删 nodes/edges 路径。
2. `sdk/store.py`:`_row_graph_builder_for_souffle`;engine==souffle 注入;per-row ProofReceipt→SouffleProofTree→converter;失败 minimal。
3. 测试:souffle row explain 产 paths(head/body/atoms 非空)+ fallback 不变式 + import grep 归零;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/adapters/docs/01_souffle_adapter.md`(若述及 evidence 形态)。

## 10. Outcome / Deviations

**落地**:impl `d40538fc`(线性栈 `… → 869934f3(S6a蓝图) → d40538fc(S6a code)`);master 未动,未 push。

**结果**:
- `souffle_proof_tree_to_evidence_graph` 迁 paths-model(import `application.explain.evidence_tree`:11,产 `paths=(EvidenceTree...)`:80);不再 import `audit.evidence_graph`。
- SDK dispatch 重构 per-engine:`_row_graph_builder_for_engine`(store.py:2815;native→plan、souffle→`_souffle_row_graph_builder(row_support_artifacts)`)。
- souffle row 产 head/body rules + witness atoms;converter/support 失败 → minimal paths(保不变式)。

**实现说明(Codex,合理)**:runtime souffle 存 `ProofReceipt`(非 raw `SouffleProofTreeV0`),故 SDK dispatch 从 ProofReceipt 直接产 paths;adapter 的 `SouffleProofTreeV0` converter 也迁移+测试(供直接 `souffle -t explain` JSON proof stream)。→ S6a open item(ProofReceipt→SouffleProofTree)以"两路并存、都 paths"收口。

**Gate(我独立验证)**:
- ★scope-limit:problog/pyreason/audit **未碰**(commit stat 确认)。
- souffle converter → paths,无 audit/nodes/edges import。
- `test_converter_builds_tree_from_recursive_proof`:paths 1、`{role}=={head,body}`、head atom + 4 body atoms + negation —— souffle row 真 paths 非 minimal。
- per-engine dispatch 重构(S6b/c 可复用)。
- cohort 71 OK(独立)/ Codex 99 OK。

**归档**:暂留 active/,随里程碑批量归档。
