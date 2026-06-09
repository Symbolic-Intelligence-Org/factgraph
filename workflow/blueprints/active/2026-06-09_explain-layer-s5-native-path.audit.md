# Audit Log: S5 — native path wiring + old flat-DAG removal

Paired with [2026-06-09_explain-layer-s5-native-path.md](./2026-06-09_explain-layer-s5-native-path.md).

---

## A. Preflight (2026-06-09)

- `_explain_live_row`(:719):row_not_in_result(:732)/stale_row(:743)当前 → `failed`/None;builder(:755)默认 `_build_passed_row_evidence_graph`(旧 flat-DAG);ValueError → unsupported。只处理存在 row(passed)。
- closed_head_false:sdk/store:2524-2532(`first is None`)→ failed/None,无 probe。
- 不变式 :286-287 = `passed iff evidence`。
- 旧 flat-DAG:`EvidenceNode/Edge` imports(:25/27)+ helpers(:955/990/1002/1019/1027/1047)。
- prober 需 view_facts(store ledger)+ plan —— 协议层够不到。

## B. Codex S5 预判(全采纳)

1. **graph_builder 注入是正确接缝**:协议层纯装配器;view_facts/plan/store 留 sdk/store,经注入 builder 传入。
2. **旧 flat-DAG 整片删除,无双轨**:`_row_shell_*`/`_row_*_node`/EvidenceNode/Edge 归零;acceptance 加 grep。

## C. Locked decisions

- 不变式放宽 `{passed,failed} ↔ evidence`(§9.0)。
- row_not_in_result / stale_row → `unsupported`(否则违反新不变式)。
- passed 经 SDK 注入 prober graph_builder(result 私有字段,类比 `_row_close_builder`);closed_head_false 经 sdk/store 直调 probe_native。
- `Explanation.evidence` = 新 paths-model `EvidenceGraph`(application/explain)。
- 默认 builder(无注入)→ minimal paths-model(非 flat-DAG)。

## D. Open items for Codex

- 注入机制:`result._row_graph_builder` 私有字段 vs 其他;`row.explain()`(:118)如何取到它(协议层从 result 读注入 builder)。你定形态,但协议层不得 import store。
- `audit/evidence_graph.py` 是否本片改 thin re-export,还是留 S6/docs —— 建议 S5 只切 evaluate_result 引用,audit re-export 留后续(避免 S5 过大)。
- closed_head_false 的 plan/view_facts 来源(复用 evaluate 路径的 lower + project_view_facts)。

## E. Gate result / Deviations

impl + gate 后填写。
