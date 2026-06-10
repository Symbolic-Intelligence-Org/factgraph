# Task Blueprint: S5 — native path wiring (G3) + old flat-DAG removal (S7)

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py`(Explanation 不变式 + dispatch + 删旧 flat-DAG;协议装配器)
  - `src/factgraph/sdk/store.py`(注入 prober graph_builder + closed_head_false probe;view_facts/plan 来源)
  - `src/factgraph/application/explain/`(probe_native + paths-model EvidenceGraph)
- Related Docs:
  - Design spec §9.0(不变式放宽)/§2(prober 是唯一解释路径): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s5-native-path.audit.md](./2026-06-09_explain-layer-s5-native-path.audit.md)

---

## 1. Problem

S3/S4 有了健全的 prober + 烘焙,但 `Explanation` 路径还没接上:passed 走旧 flat-DAG 占位 builder,failed(closed_head_false)无证据。S5 = **G3**:passed + failed **都走 prober** 产 paths-model 证据;放宽不变式到 `{passed,failed} ↔ evidence`;并**删除旧 flat-DAG dispatch**(S7 并入)。这是 v1 "passed 只给 minimal 占位" gap 的修复。

## 2. Goals

1. **不变式放宽**(§9.0):`Explanation` `(status ∈ {passed,failed}) ↔ (evidence is not None)`(当前是 `passed ↔ evidence`,:286-287)。
2. **passed 路径**:`row.explain()` 经 SDK 注入的 prober graph_builder 产 **paths-model EvidenceGraph**(prober 全树),非 minimal 占位。
3. **failed 路径**:closed_head_false(sdk/store:2524)接 `probe_native` 产失败证据(`evidence.paths` 非空)。
4. **重分类**:`row_not_in_result` / `stale_row` 从 `failed` 改判 **`unsupported`**(evidence None;否则违反新不变式)。
5. **删旧 flat-DAG**(S7):`EvidenceNode/EvidenceEdge` imports + `_row_*_node` + `_row_shell_*` + `_build_passed_row_evidence_graph`;`Explanation.evidence` 切到新 paths-model `EvidenceGraph`。

## 3. Non-goals

- adapters(problog/pyreason/souffle)dispatch(S6)。
- `audit/evidence_graph.py` 改 thin re-export(S6 或后续 docs;S5 只切 evaluate_result 的引用)。
- prober G1/G2 逻辑(S3 已定)。
- `narrate()`。

## 4. Current Context(preflight 已完成)

- `_explain_live_row`(:719):row_not_in_result(:732)→ **failed**/None;stale_row(:743)→ **failed**/None;builder(:755 默认 `_build_passed_row_evidence_graph`=旧 flat-DAG)→ passed;builder ValueError → unsupported。**只处理存在的 row(passed 语义)**。
- closed_head_false 在 **sdk/store:2524-2532**(`first is None`)→ failed/None,无 probe。
- 不变式 :286-287 当前 `passed iff evidence`。
- 旧 flat-DAG:`EvidenceNode/Edge` imports(:25/27)+ helpers(:955/990/1002/1019/1027/1047)。
- prober:`probe_native(plan, bindings, view_facts, schema_index)`(S3/S4);需 view_facts(store ledger)+ plan(lower rule)——**协议层够不到,必须 SDK 提供**。

## 5. Proposed Shape

### 接缝(Codex #1:graph_builder 注入,协议层纯)

- 协议层 `_explain_live_row` 保持装配器:只管不变式 + 状态 + 调 graph_builder + fallback。
- SDK 在 evaluate 时把一个 **prober graph_builder**(捕获 view_facts + lower plan)注入 `EvaluateResult` 私有字段(如 `_row_graph_builder`,类比现有 `_row_close_builder`);`row.explain()` → `_explain_live_row` 用该 builder。无则 minimal paths-model fallback。
- closed_head_false 路径(sdk/store)直接调 `probe_native` 产 failed `EvidenceGraph`。

### 不变式 + 重分类

- :286-287 改 `(status in {"passed","failed"}) != (evidence is not None)`。
- row_not_in_result / stale_row → `status="unsupported"`,evidence None。

### 删旧(Codex #2:整片删,无双轨)

- 删 `EvidenceNode/Edge` imports + `_row_conclusion_node`/`_row_rule_expr_node`/`_row_rule_node`/`_row_shell_nodes`/`_row_shell_edges`/`_build_passed_row_evidence_graph`。
- 默认 builder(无注入)→ minimal **paths-model**(单 head-atom EvidenceTree),非 flat-DAG。
- `Explanation.evidence` 类型 = `application/explain` 的 paths-model `EvidenceGraph`。

## 6. Boundaries And Invariants

- **★不变式**:`{passed,failed} ↔ evidence non-None`;`{unsupported,invalid_request} ↔ evidence None`。
- **协议层纯**:`evaluate_result.py` 不 import store / 不取 view_facts;事实/plan 经 SDK 注入(Codex #1)。
- **无双轨**:旧 flat-DAG helpers 整片删除;grep `EvidenceNode`/`EvidenceEdge`/`_row_shell_*`/`_row_*_node` 在 evaluate_result.py 归零(Codex #2)。
- passed + failed 证据都是 paths-model(prober 树);不回退 minimal 占位(除无注入的纯协议 fallback)。
- INV-6;单线性栈(S4 之上)。

## 7. Acceptance

- [ ] **passed native row**:`status=="passed"` 且 `evidence.paths` 非空,body atom 有 prober `repr_text`
- [ ] **closed_head_false**:`status=="failed"` 且 `evidence.paths` 非空(prober 失败树)
- [ ] **stale_row / row_not_in_result**:`status=="unsupported"` 且 `evidence is None`
- [ ] **不变式 test**:passed/failed 必有 evidence;unsupported/invalid_request 必无
- [ ] **regression grep**:`EvidenceNode`/`EvidenceEdge`/`_row_shell_*`/`_row_*_node`/`_build_passed_row_evidence_graph` 在 evaluate_result.py = 0
- [ ] 协议层不 import store(`evaluate_result.py` 无 store 依赖)
- [ ] 受影响 docs(protocol explain dispatch)同步

## 8. Implementation Plan

1. evaluate_result.py:不变式改 `{passed,failed}`;row_not_in_result/stale_row → unsupported;默认 builder → minimal paths-model;删旧 flat-DAG helpers + EvidenceNode/Edge imports;`Explanation.evidence` 用新 EvidenceGraph。
2. sdk/store.py:evaluate 时注入 prober graph_builder(view_facts + plan)到 result;`row.explain()` 用之;closed_head_false → probe_native 产 failed evidence。
3. 测试:passed/failed/unsupported 三态 + 不变式 + grep 归零 + 协议无 store 依赖;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md`(Explanation 不变式 + dispatch via prober graph_builder)。

## 10. Outcome / Deviations

**落地**:impl `89de4a6c`(线性栈 `… → b7a6e9ea(S5蓝图) → 89de4a6c(S5 code)`);master 未动,未 push。

**结果**:
- 不变式改 `(status in {passed,failed}) != (evidence is not None)`(evaluate_result.py:286)。
- prober 经 SDK 注入:`EvaluateResult._row_graph_builder`(:152,协议私有字段);`_explain_live_row` `builder = graph_builder or result._row_graph_builder or _build_minimal_row_evidence_graph`(:753)。SDK `_row_graph_builder_for_lowering_plan`(store.py:2798)调 `probe_native(view_facts=project_view_facts(ledger))`(:2820/2822)。
- closed_head_false(store.py:2535)→ failed + probe paths 证据。
- row_not_in_result/stale_row → `unsupported`(:720/737)。
- 删旧 flat-DAG(evaluate_result.py -495 net):EvidenceNode/Edge imports + `_row_*_node`/`_row_shell_*`/`_build_passed_row_evidence_graph` 全删。
- `Explanation.repr` walk evidence for passed+failed。

**Gate(我独立验证)**:
- ★G3 修复:`test_live_row_explain_returns_passed_explanation` 断言 passed native `evidence.paths` 非空(:651)+ `rules[0].role=="head"`(:685)—— v1 "minimal 占位" gap 修复。SDK 真调 probe_native(view_facts from ledger)。
- 不变式 :286 = `{passed,failed}↔evidence`;协议层无 store import;旧 flat-DAG grep **0**(无双轨)。
- closed_head_false → failed+paths;row_not_in_result/stale_row → unsupported(:925/973)。
- cohort 71 OK(独立)/ Codex 89 OK。

**Deviations(良性)**:`audit/evidence_graph.py` thin re-export 留 S6/docs(本片只切 evaluate_result 引用,符合 audit §D)。`_row_graph_builder` 私有字段是协议接缝(Codex #1)。

**归档**:暂留 active/,随里程碑批量归档。
