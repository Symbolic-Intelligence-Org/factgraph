# Audit 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/audit`
- 最后更新：2026-03-28
- 目标读者：需要消费 audit package、做离线审计查询或静态展示的开发者

## 1. 模块职责

`audit` 是 **审计消费层**。它读取已经导出的 audit package，并提供查询、DTO 和静态站点渲染能力。

它主要负责：

- audit package 读取
- run / candidate / materialization / decision / failure 查询
- requirement-scoped compliance matrix 查询
- authoring apply events 查询
- 审计 DTO 构建
- 静态审计页面生成
- 跨引擎 explainability 的共享表示层（in-memory DTO）

它不负责：

- live runtime facts 查询
- registry 资产版本管理
- package 导出
- engine-native provenance 生成

## 2. 当前公共入口

- `load_audit_package(...)`
  - 从 audit package 目录读取数据
- `AuditQuery`
  - 结构化查询入口
  - 当前也提供 rule trace artifact 的离线查询
  - 当前也提供 witness-bearing candidate evidence tree 的离线查询
- `extend_schema_ir_with_ecss_vcd_predicates(...)`
  - 为 `ECSS-M-ST-10` 风格 requirement/compliance facts 提供最小 predicate schema helper
  - 当前由 `factpy_kernel.ecss.vcd` 拥有，`audit` 侧仅保留兼容 re-export
- `render_audit_static_site(...)`
  - 生成静态审计站点
- `load_authoring_apply_events(...)`
  - 读取 authoring apply event 日志
- `EvidenceGraph` / `EvidenceNode` / `EvidenceEdge`
  - audit 层统一 explainability DTO
  - `render_evidence_graph_html(...)` standalone HTML fragment renderer
  - `evidence_graphs.jsonl` export in audit package (Souffle/PyReason/ProbLog)
  - `AuditQuery.get_candidate_evidence_graph()` query-layer access
  - static candidate evidence page renders durable `EvidenceGraph` with Souffle fallback

对应模块：

- `reader.py`
- `query.py`
- `dto.py`
- `static_ui.py`
- `authoring_events.py`
- `assertions.py`
- `compliance.py`
- `evidence_graph.py`

## 3. 典型工作流

### 3.1 读取 audit package

1. 先通过 adapter/runtime 导出 `package_kind="audit"` 的 package
2. 调用 `load_audit_package(package_dir)`
3. 得到 `AuditPackageData`

### 3.2 结构化查询

1. 创建 `AuditQuery(package)`
2. 调用：
   - `list_runs()`
   - `get_run_bundle(run_id)`
   - `list_candidates(...)`
   - `get_candidate_evidence_tree(candidate_id)`
   - `get_candidate_certainty_summary(candidate_id)`
   - `list_decisions(...)`
   - `list_failures(...)`
   - `list_compliance_matrix(...)`
   - `list_rule_traces(...)`
   - `get_rule_trace(rule_run_id)`
   - `list_rule_trace_summaries(...)`
   - `get_rule_trace_summary(rule_run_id)`
   - `get_rule_trace_narrative(rule_run_id)`
   - `get_mapping_resolution(...)`
   - `list_authoring_apply_events(...)`

### 3.3 Requirement / Compliance Matrix

当 audit package 中包含 requirement-scoped assertions 时，当前 `audit` 层可以离线组装 ECSS VCD / compliance matrix：

1. 在写入侧使用 requirement/compliance predicates，例如：
   - `ecss:requirement`
   - `ecss:verification_method`
   - `ecss:compliance_status`
   - `ecss:requirement_rid`
   - `ecss:review_milestone`
2. export 仍使用现有 `package_kind="audit"`，不新增专用 raw matrix artifact
3. consumer 通过：
   - `AuditQuery.list_compliance_matrix(...)`
   - `build_compliance_matrix_dto(...)`
4. query 实现会下探到 package 内已有的 assertion/fact 文件，而不是只消费 JSONL audit ledgers

### 3.4 静态审计页面

1. 准备 `AuditPackageData`
2. 调用 `render_audit_static_site(...)`
3. 输出静态 HTML/资源

当前静态站点的 page filenames / hrefs 使用 filesystem-safe reversible slug，而不是原始 percent-encoded id。
这样生成的站点可直接通过常见静态文件服务器浏览，不依赖服务器对 `%xx` 路径的特殊处理。

当 package 中存在 requirement/compliance facts 时，当前静态站点也会额外生成：

- `compliance_matrix.html`
  - 以离线 compliance matrix 表格形式展示 requirement、status、milestone、verification methods、RID links
  - 每一行通过 assertion id 链接到既有 assertion detail 页面
- `rule_traces.html`
  - 作为 `rule_run_id` proof-entry index
- `rule_traces/{rule_run_id}.html`
  - 作为单条 rule trace 的 shareable detail page
  - 页面顶部包含从 `rule_run_summary` 纯派生的 deterministic narrative block
  - 页面会展示 root rule、invocations、`pred_witnesses`、`non_fact_steps`
  - witness assertion 仍下钻到既有 assertion detail 页面

与 static HTML 并行，当前 audit 侧也已经提供 machine-readable `rule_run_summary` derived surface：

- `AuditQuery.get_rule_trace_summary(rule_run_id)`
- `AuditQuery.list_rule_trace_summaries(...)`
- `build_rule_trace_summary_dto(...)`
- `build_rule_trace_summary_list_dto(...)`

在此基础上，当前 audit 侧也已提供 machine-readable `rule_run_narrative` surface：

- `AuditQuery.get_rule_trace_narrative(rule_run_id)`
- `build_rule_trace_narrative_dto(...)`

在此基础上，当前 audit 侧也已提供 machine-readable `candidate_evidence_tree` surface：

- `AuditQuery.get_candidate_evidence_tree(candidate_id)`
- `build_candidate_evidence_tree_dto(...)`

在此基础上，当前 audit 侧也已提供 machine-readable candidate derived surfaces：

- `AuditQuery.get_candidate_evidence_tree_summary(candidate_id)`
- `AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)`
- `build_candidate_evidence_tree_summary_dto(...)`
- `build_candidate_evidence_tree_narrative_dto(...)`

若 package 中存在 candidate rows，当前静态站点也会额外生成：

- `candidate_evidence.html`
  - candidate evidence tree index
- `candidate_evidence/{candidate_id}.html`
  - node-kind-aware nested tree page
  - 页面顶部包含从 `candidate_evidence_tree_summary` 纯派生的 deterministic narrative block
  - assertion leaves 继续下钻到既有 assertion detail 页面
  - 若 candidate 具有 `rule_ref_edges` 或 legacy `rule_refs`，页面会按需展示 `rule_ref_section`
  - 当前也支持 recursive child proof node：
    - `referenced_support`
    - `unresolved_support`
    - `recursion_boundary`
  - 当前也支持 engine degraded candidate tree：
    - `candidate_result`
    - `support_section`
    - `degraded_support`
  - audit 在 candidate tree 上消费与 runtime 相同的 terminal taxonomy contract：
    - `unresolved_support`
      - `child_support_unavailable`
      - `artifact_missing`
    - `recursion_boundary`
      - `cycle`
      - `depth_limit`
  - audit 不发明新的 reason enum；summary/query/static 都继续消费同一组 raw node-kind 与 reason 字段
  - audit 也消费与 runtime 相同的 `node_kind` provenance-role taxonomy（冻结 contract）：
    - **structural**：`candidate_result`, `support_section`, `rule_ref_section`
    - **witness**：`predicate_witness_group`, `assertion_fact`
    - **constraint**：`non_fact_check`
    - **rule_chain**：`rule_ref`, `referenced_support`
    - **terminal**：`unresolved_support`, `recursion_boundary`
    - **degraded**：`degraded_support`
  - first-round 不新增 `source_kind` / `provenance_kind`；`node_kind` 即为 provenance-role carrier
  - deeper assertion-origin taxonomy deferred
  - 只有 structured `rule_ref_edges` path 会进入 recursive terminal taxonomy；legacy `rule_refs` fallback 仍保持 flat `rule_ref` 节点
  - audit 也消费与 runtime 相同的 engine degraded tree contract：
    - `degraded_support`
      - `support_kind`
      - `witness_status="degraded"`
      - `children=[]`
    - `degraded_support` 不复用 native recursive terminal taxonomy
  - legacy `"none"` 与 `engine_no_witness_v1` 在 tree surface 上同构

这组 summary 与 runtime `rule_run_summary` 保持同构，且只从现有 raw trace payload 派生。
这组 narrative 与 runtime `rule_run_narrative` 保持同构，且只从既有 `rule_run_summary` 纯派生。
这组 candidate tree 与 runtime `candidate_evidence_tree` 保持同构，且从：
- witness-bearing path：`candidate_ledger + support_artifacts + assertion detail`
- engine degraded path：`candidate_ledger`
纯派生。
这组 candidate summary 与 runtime `candidate_evidence_tree_summary` 保持同构，且只从既有 raw tree 纯派生。
这组 candidate narrative 与 runtime `candidate_evidence_tree_narrative` 保持同构，且只从既有 candidate summary 纯派生。
当 audit package 包含 `certainty_summaries.jsonl` 时，candidate narrative 也会含 additive `certainty_lines` section，与 runtime 产出一致。
candidate NL explain 当前不在 audit first-round scope；静态页只消费 narrative block，不发明单独 NL DTO。

## 4. 与其他层的边界

- `adapters`
  - audit package 由 adapter 导出，audit 负责读取和消费
- `core`
  - audit 不直接查询 live `Ledger`
- `authoring`
  - audit 可消费 package 中携带的 authoring apply events，但不直接管理 registry
- `ecss`
  - requirement/compliance predicates 的 canonical preset owner 在 `factpy_kernel.ecss.vcd`
  - audit 复用这组 shared constants/helper，但 matrix row 组装仍留在 `audit`
- `explainability`
  - compliance matrix 只负责 requirement-level delivery；更细的 assertion/support 证据下钻仍由 assertion detail / explainability substrate 承担
  - rule trace static delivery 只消费 package 内已有 `RuleTraceArtifact`，不新增 live explain endpoint
  - runtime live permalink 若存在，也应优先复用本模块已有的 page renderers 与 data shape，而不是新建第二套 HTML 模板

## 5. 当前限制

- audit 主要面向离线快照，不是实时审计接口
- 没有直接把 live runtime store 映射成 audit query 的入口
- 审计能力依赖导出的 package 是否完整包含所需 ledger / decision / authoring event 信息
- requirement/compliance matrix 当前是 offline-query-first 形态，不提供 live service endpoint
- static UI 当前同时支持：
  - `rule_run_id` proof-entry page
  - witness-bearing candidate evidence tree page
- 但仍不支持 graph UI、salience breakdown 或更细 provenance contract
- static UI 对 compliance matrix 的支持当前仍是单页总览，不包含 per-requirement detail page 或额外搜索 facet
- live permalink 若由 runtime service 提供，当前也只是对既有 rule-trace / candidate page renderers 的在线复用；audit export 仍是 durable shareable surface

## 6. Audit Package Artifact Files

当 package 以 `package_kind="audit"` 导出时，当前 package 除了 ledger / decision 相关文件外，也会附带 explain artifact dump：

- `audit/support_artifacts.jsonl`
  - 以 `support_digest` 为 key 的 flat JSONL rows
  - payload 复用 `SupportArtifact` 的 JSON-friendly shape
- `audit/rule_trace_artifacts.jsonl`
  - 以 `rule_run_id` 为 key 的 flat JSONL rows
  - payload 复用 `RuleTraceArtifact` 的 JSON-friendly shape
- `audit/certainty_summaries.jsonl`（可选）
  - 以 `candidate_id` 为 key 的 flat JSONL rows
  - 每行格式：`{"candidate_id": "...", "certainty_summary": {...}}`
  - 只在 export time 有 `registry_root` 且 candidate 的 certainty 可派生时写入
  - `certainty_summary` payload 与 runtime `explain-summary` 的 `certainty_summary` 字段同构
  - 旧 package 不含该文件时，reader 返回空 dict（向后兼容）
- `audit/provenance_trees.jsonl`（可选）
  - 以 `candidate_id` 为 key 的 flat JSONL rows
  - 每行格式：`{"candidate_id": "...", "provenance_tree": {...}}`
  - 只在 export time 既有 accepted candidate、又能用 session-scoped derivation recipe replay 成 query-bearing Souffle package 时写入
  - `provenance_tree` payload 复用 adapter-local `SouffleProofTreeV0` dict shape（`query` / `root` / `rules`）
  - 旧 package 不含该文件时，reader 返回空 dict（向后兼容）
- `audit/provenance_statuses.jsonl`（可选）
  - 以 `candidate_id` 为 key 的 flat JSONL rows
  - 每行格式：`{"candidate_id": "...", "status": "...", "engine": "souffle", "truncated": false, "reason": "..."?}`
  - 记录 provenance 是否可用、为什么不可用，以及 proof tree 是否含 `subproof` depth truncation
  - 与 `provenance_trees.jsonl` 一样在 export time 物化；旧 package 不含该文件时，reader 返回空 dict（向后兼容）

这些文件当前是全量导出，不做引用子集裁剪；它们的职责是让离线 audit consumer 能读取 explain carrier，而不是提供 online durable readback。

当前 `audit.reader` / `AuditQuery` / static UI 已统一消费 `rule_trace_artifacts.jsonl`：

- reader 读取 JSONL rows（旧 package 若没有该文件则返回空集）
- query 可按 `rule_run_id` 离线查询
- query / dto 也可从同一份 raw rows 派生 `rule_run_summary`
- query / dto 也可从同一份 summary surface 继续派生 `rule_run_narrative`
- static site 可把 `rule_run_id` 渲染成可分享 proof-entry page，并通过 audit narrative DTO 在页面顶部附加 deterministic rule-run narrative

当前 `audit.reader` / `AuditQuery` / static UI 也已统一消费 `support_artifacts.jsonl`：

- reader 读取 JSONL rows（旧 package 若没有该文件则返回空集）
- query 可按 `candidate_id -> support_digest` 离线重建 witness-bearing candidate evidence tree（当前包括 `native_binding_v1` 与 `souffle_witness_v1`）
- query 会优先消费 `SupportArtifact.rule_ref_edges`，并按 `child_support_digest` 继续离线解引用 child support artifact；若 package 只有 legacy `rule_refs`，则保持 minimal fallback tree
- dto 可直接返回与 runtime 同构的 `candidate_evidence_tree`
- static site 可把 `candidate_id` 渲染成 recursive sectioned tree page，并继续下钻到既有 assertion detail 页面

当前 `audit.reader` / `AuditQuery` / static UI 也已统一消费 `certainty_summaries.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: certainty_summary_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询物化的 certainty_summary
- query 的 `get_candidate_evidence_tree_narrative(candidate_id)` 会将物化的 certainty_summary 传入 narrative renderer，产出含 additive `certainty_lines` 的 narrative
- static site candidate evidence page 在 narrative block 末尾渲染 certainty section（当 certainty_lines 存在时）
- certainty_summary 在 export time 由 runtime service 预计算（通过 core `materialize_certainty_summary` helper），audit 侧不做 query-time 计算（因为 `condition_weights` 离线不可用）

当前 `audit.reader` / `AuditQuery` / static UI 也已统一消费 `provenance_trees.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: provenance_tree_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询物化的 engine-native provenance tree
- static site candidate evidence page 在 certainty section 后渲染 additive `Engine Provenance` section（当 provenance_tree 存在时）
- provenance_tree 在 export time 由 runtime service 通过 query-bearing Souffle package replay 物化；audit 侧不做 query-time Souffle 执行

当前 `audit.reader` / `AuditQuery` / static UI 也已统一消费 `provenance_statuses.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: provenance_status_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询单个 provenance status，也可做 package-level coverage summary
- `list_candidates_with_provenance()` / `list_candidates_without_provenance()` / `summarize_provenance_coverage()` 都按唯一 `candidate_id` 统计，而不是按 `candidate_ledger` 原始行数统计
- static site candidate evidence page 会渲染 provenance availability badge；当 `truncated=true` 时追加 depth-truncation warning
- static site landing page 会在 package 含 `provenance_statuses.jsonl` 时显示 provenance coverage / truncated proof metric cards

当前不会新增 `rule_trace_summary` 专用 artifact 文件；summary 是 read/query 层的纯派生面，不是新的 durable package contract。
当前也不会新增 `candidate_evidence_tree` 专用 artifact 文件；candidate tree 同样是 read/query 层的纯派生面，不是新的 durable package contract。
