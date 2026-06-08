# Audit Log: explain-layer-s6-adapter-wiring

| Field | Value |
|---|---|
| **Blueprint** | `2026-06-08_explain-layer-s6-adapter-wiring.md` |
| **Audit type** | preflight (vs-shipped) |
| **Date** | 2026-06-08 |
| **Author** | Claude |

---

## Preflight Read Log

| 文件 | 读取内容 | 关键发现 |
|---|---|---|
| `adapters/souffle/provenance.py` @ S5 | 函数列表 + 返回值 | `souffle_proof_tree_to_evidence_graph` 返回 `EvidenceGraph(paths=(tree,), ...)` ✓ |
| `adapters/problog/provenance.py` @ S5 | 函数签名 + 返回值 | `problog_trace_to_evidence_graph` 返回 `EvidenceGraph(paths=(EvidenceTree,), ...)` ✓ |
| `adapters/pyreason/provenance.py` @ S5 | 函数签名 + 返回值 | `pyreason_trace_to_evidence_graph` 返回 `EvidenceGraph(paths=(EvidenceTimeline,), ...)` ✓ |
| `evaluate_result.py` @ S5 — grep dead code | 所有 `_build_*/NODE_*/EDGE_*` 引用 | 11 个函数完全 dead，使用未导入符号 ✓ |
| `evaluate_result.py` @ S5 — 顶层 imports | 行 19-40 | `EvidenceNode`/`EvidenceEdge`/`NODE_*`/`EDGE_*` 均未导入 ✓ |
| `evaluate_result.py` @ S5 — dispatch 路径 | 行 ~763 | 完全不使用 `_row_provenance_envelopes`；所有 row 走 minimal placeholder ✓ |
| `evaluate_result.py` @ S5 — `_build_passed_row_evidence_graph` | 行 1056-1100 | 构建最小 head-atom EvidenceTree，已符合 S5 schema ✓ |
| `evaluate_result.py` @ S5 — `_build_problog_provenance_row_evidence_graph` | 行 1101-1193 | 调用 `.nodes`/`.edges`（旧 API）+ `EvidenceNode`（未导入）→ NameError ✓ |
| `evaluate_result.py` @ S5 — `_build_form1_evidence_graph` | 行 1245-1357 | 使用 `EvidenceNode`/`NODE_ATOM`/`NODE_SEED` + `EvidenceEdge`（全部未导入）→ NameError ✓ |
| `evaluate_result.py` @ S5 — `_legacy_candidate_payload_for_row_result` | 行 482-500 | 产生 `{"pred_id": ..., "terms": [...]}` — problog adapter 所需 payload 格式 ✓ |
| `sdk/store.py` — `_row_provenance_envelopes_for_candidates` | 行 ~2868 | `if candidate.support_kind != PROBLOG_PROVENANCE_KIND: continue` — PyReason 被漏掉 ✓ |
| `core/store/_support.py` — 常量定义 | 行 13-19 | `PYREASON_PROVENANCE_KIND`, `_PROVENANCE_BEARING_SUPPORT_KINDS` 均存在且在 `__all__` ✓ |
| `problog/provenance.py` — `_resolve_candidate_info` | 行 490+ | 从 `candidate_payload` 取 `pred_id` + `terms`；与 `_legacy_candidate_payload_for_row_result` 产出完全匹配 ✓ |
| `prober.py` @ S5 — `probe_native` | 行 1-120 | ProbeResult 从 `CompiledDerivationPlan` 构建，不存储在 EvaluateResult 中——Form1 无法复用 prober ✓ |

---

## Triage Table: shipped vs. design

| 条目 | 现状（S5 shipped） | 设计目标（S6） | delta |
|---|---|---|---|
| ProbLog rich evidence | 走 minimal placeholder | 走 `_build_problog_passed_evidence_graph` | 新增 builder + dispatch |
| PyReason rich evidence | 走 minimal placeholder + envelope 甚至不被收集 | 走 `_build_pyreason_passed_evidence_graph` | 新增 builder + envelope 收集修复 |
| Form 1 (native / souffle) evidence | 走 minimal placeholder（ProofReceipt 存在但被忽略） | 继续 minimal placeholder（不变） | 无变化（defer） |
| `_build_problog_provenance_row_evidence_graph` | Dead/broken（NameError 如被调用） | 删除 | 删除 |
| `_build_form1_evidence_graph` | Dead/broken（NameError 如被调用） | 删除 | 删除 |
| `_row_shell_nodes/edges/_conclusion_node/etc` | Dead/broken | 删除 | 删除（9个函数） |
| `_legacy_candidate_payload_for_row_result` | 被 dead code 引用 | 重命名后被新 ProbLog builder 引用 | 重命名 |
| `_row_provenance_envelopes_for_candidates` | 只收集 ProbLog | 收集 ProbLog + PyReason | 1行条件修改 |

---

## Q-S6-A 确认

**LOCKED: Option B** — adapter 转换失败时在 `_build_problog_passed_evidence_graph(...)` / `_build_pyreason_passed_evidence_graph(...)` 内部回退到 minimal placeholder。

理由:
- 保持 S5 invariant：`status="passed"` 的 row explanation 必须有 evidence。
- 与 S5 `closed_head_false` prober fallback 策略一致。
- Adapter payload/trace 兼容问题不应把已通过的 row 降级为 `unsupported + evidence=None`。

---

## Scope Freeze Event

| Stage | Event | Notes |
|---|---|---|
| scoped | Q-S6-A locked + scope freeze | User clarified local implementation does not need repeated authorization; Q-S6-A locked to Option B. Scope is now two shipped files: `evaluate_result.py` dead-code/rich-dispatch cleanup and `sdk/store.py` PyReason envelope collection. |
| implemented | S6 implementation verified | Impl `57a86304` deletes old flat-DAG dead code, dispatches ProbLog/PyReason passed-row provenance to paths-model adapter graphs, collects PyReason envelopes, and preserves Option B fallback. Focused tests OK; full discover has only known unrelated `service.app_v1` import failure. |
