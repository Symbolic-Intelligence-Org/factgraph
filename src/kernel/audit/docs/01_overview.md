# Audit 模块总览（kernel）

- 范围：`src/kernel/audit`
- 最后更新：2026-05-06
- 目标读者：需要消费 audit package、做离线审计查询或构建 audit DTO 的开发者

## 1. 模块职责

> **Boundary — v0.1 kernel-only wheel**
>
> 本文描述 `kernel.audit` 如何与下游 consumer 集成。下列模块会在文中被引用,但**不属于 v0.1 kernel-only wheel**:
>
> - `service.static_ui` — 完整 audit static-site rendering(monorepo / future deliverable)
> - `domains.ecss.compliance` — ECSS row assembly + compliance matrix(optional domain bundle)
> - `domains.ecss.vcd` — ECSS VCD predicate preset(optional domain bundle)
>
> kernel-only install 中直接调用这些模块会触发 `ModuleNotFoundError`。`AuditQuery.list_compliance_matrix(...)` 会抛 `AuditOptionalDomainError`,给出可操作信号,而不是让用户撞到裸 import failure。

`audit` 是 **审计消费层**。它读取已经导出的 audit package，并提供查询、DTO 与 evidence graph 消费能力。

它主要负责：

- audit package 读取
- run / candidate / materialization / decision / failure 查询
- requirement-scoped compliance matrix 查询
- authoring apply events 查询
- durable round event log 读取与查询
- 审计 DTO 构建
- 跨引擎 explainability 的共享表示层（in-memory DTO）

它不负责：

- live runtime facts 查询
- registry 资产版本管理
- package 导出
- engine-native provenance 生成
- 完整静态站点渲染（属于 `service.static_ui`）
- ECSS compliance row assembly 语义（属于 `domains.ecss.compliance`）

## 2. 当前公共入口

- `load_audit_package(...)`
  - 从 audit package 目录读取数据
- `AuditQuery`
  - 结构化查询入口
  - 当前也提供 rule trace artifact 的离线查询
  - 当前也提供 witness-bearing candidate evidence tree 的离线查询
  - 当前也提供 round event log 的离线查询
- `start_round(...)` / `record_round_event(...)` / `finalize_round(...)`
  - 外部 recorder API；调用方在 capability runtime 外部记录已经产生的结果
  - 写入 audit package 内可选 `audit/round_events.jsonl`
  - 默认 buffered，`finalize_round(...)` 通过 tempfile + `os.replace` 原子落盘
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
- `authoring_events.py`
- `assertions.py`
- `evidence_graph.py`
- `round_events.py`

相关 contract 文档：

- `src/kernel/audit/docs/03_audit_package_contract.md`
  - audit package 文件、reader/query 派生面、最小 provenance carrier mapping
- delivery-layer static site contract
  - rendered static site、`site_manifest.json`、`ui_index.json` 的交付 contract

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
   - `list_compliance_matrix(...)`（ECSS/domain-backed optional convenience）
   - `list_rule_traces(...)`
   - `get_rule_trace(rule_run_id)`
   - `list_rule_trace_summaries(...)`
   - `get_rule_trace_summary(rule_run_id)`
   - `get_rule_trace_narrative(rule_run_id)`
   - `get_mapping_resolution(...)`
   - `list_authoring_apply_events(...)`
   - `list_rounds()`
   - `list_round_events(round_id, kind=None)`
  - `get_round_event(round_id, sequence)`
  - `get_round_summary(round_id)`
  - `list_round_event_warnings()`
  - `diff_proof_frames(round_a, round_b, include_partial=False, include_unchanged=False)`

### 3.3 Round Event Log

Round event log 是 Batch 6 引入的可选 audit package 文件，用于持久化一轮 application capability 调用的结果摘要。它不重放 capability，也不改变 Store / ledger 语义。

当前 first slice 包含：

- lifecycle：`round_started`、`round_finalized`
- capability：`check_result`、`diagnose_result`、`fact_overlay_result`、`why_not_result`、`proof_frame_result`

明确 deferred：

- Frontier projection event family
- 5a/5b/5c rule action result event family
- Batch 7 diff / cross-run aggregation index

Recorder 使用调用方提供的 `round_id` 和每轮递增 `sequence`。Capability runtime 不 import `kernel.audit`，由调用方在 capability 返回后显式记录事件。

Reader 对 `round_events.jsonl` 使用 lenient 解析：

- malformed row：跳过并记录 `ROUND_EVENT_MALFORMED` warning
- duplicate `(round_id, sequence)`：保留第一条并记录 `ROUND_EVENT_DUPLICATE` warning
- unknown future kind：保留 raw payload，不 warning
- missing `round_finalized`：`RoundSummary.is_finalized=False`

### 3.4 ProofFrame Diff

Batch 7 在 audit 查询层新增只读 `ProofFrame` diff：

- 输入：两个显式 round id
- 数据源：Batch 6 `proof_frame_result` rows
- frame identity：`request.support_digest + result.binding_items`
- atom identity：同一 `support_digest` 内的 `atom_key`
- 输出：`ProofFrameDiff` / `FrameDelta` / `AtomDelta` dataclasses

默认行为：

- 只比较 finalized rounds；partial round 会抛 `AuditQueryError`
- `include_partial=True` 时允许 partial round，并返回 `DIFF_INCLUDES_PARTIAL_ROUND` warning
- `future:proof_frame_result` rows 会跳过，并返回 `DIFF_FUTURE_KIND_SKIPPED` warning
- unchanged frames 默认省略；`include_unchanged=True` 时包含
- RuleRef / unsupported-equivalent ProofFrame(`atom_verdicts=[]`)会标记 `rule_refs_unsupported`，不生成 per-atom delta

此 diff 不持久化新的 index，不重跑 capability，不比较跨 round 的 `affected_action_indices`，也不实现 Batch 7 L5 cross-run module aggregation。

### 3.5 Requirement / Compliance Matrix

当 audit package 中包含 requirement-scoped assertions 时，`AuditQuery` 提供离线 ECSS VCD / compliance matrix 查询入口。row assembly 语义由 `domains.ecss.compliance` 拥有，`audit` 侧只负责加载 package、构建 assertion index，并通过 lazy import 暴露 query convenience。

在 kernel-only v0.1 wheel 中，`domains.ecss` 不属于安装内容。此入口保留为 monorepo / optional-domain compatibility surface；如果缺少 `domains.ecss`，调用会抛出 `AuditOptionalDomainError`，而不是把 `domains` 当成 kernel 的必备依赖：

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

### 3.6 静态审计页面（service owner）

1. 准备 `AuditPackageData`
2. 调用 `service.static_ui.render_audit_static_site(package_dir, out_dir)`
3. 输出静态 HTML/资源

完整静态站点渲染不属于 `kernel.audit` 模块。`service.static_ui` 消费 `kernel.audit` reader/query/DTO 与 domain-backed compliance rows，并负责 `site_manifest.json` / `ui_index.json` 等 rendered-site contract。

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
  - requirement/compliance predicates 的 canonical preset owner 在 `domains.ecss.vcd`
  - ECSS compliance row assembly owner 在 `domains.ecss.compliance`
  - audit 通过 lazy import 暴露 `AuditQuery.list_compliance_matrix(...)`,但不拥有 ECSS row semantics；kernel-only wheel 缺少 `domains.ecss` 时该入口抛出 `AuditOptionalDomainError`
- `explainability`
  - compliance matrix 只负责 requirement-level delivery；更细的 assertion/support 证据下钻仍由 assertion detail / explainability substrate 承担
  - rule trace static delivery 只消费 package 内已有 `RuleTraceArtifact`，不新增 live explain endpoint
  - runtime live permalink 若存在，也应优先复用本模块已有的 page renderers 与 data shape，而不是新建第二套 HTML 模板

## 5. 当前限制

- audit 主要面向离线快照，不是实时审计接口
- 没有直接把 live runtime store 映射成 audit query 的入口
- 审计能力依赖导出的 package 是否完整包含所需 ledger / decision / authoring event 信息
- requirement/compliance matrix 当前是 offline-query-first 形态，不提供 live service endpoint
- `service.static_ui` 当前同时支持：
  - `rule_run_id` proof-entry page
  - witness-bearing candidate evidence tree page
- 但仍不支持 interactive graph UI、salience breakdown 或更细 provenance contract
- `service.static_ui` 对 compliance matrix 的支持当前仍是单页总览，不包含 per-requirement detail page 或额外搜索 facet
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

当前 `audit.reader` / `AuditQuery` / `service.static_ui` 已统一消费 `rule_trace_artifacts.jsonl`：

- reader 读取 JSONL rows（旧 package 若没有该文件则返回空集）
- query 可按 `rule_run_id` 离线查询
- query / dto 也可从同一份 raw rows 派生 `rule_run_summary`
- query / dto 也可从同一份 summary surface 继续派生 `rule_run_narrative`
- `service.static_ui` 可把 `rule_run_id` 渲染成可分享 proof-entry page，并通过 audit narrative DTO 在页面顶部附加 deterministic rule-run narrative

当前 `audit.reader` / `AuditQuery` / `service.static_ui` 也已统一消费 `support_artifacts.jsonl`：

- reader 读取 JSONL rows（旧 package 若没有该文件则返回空集）
- query 可按 `candidate_id -> support_digest` 离线重建 witness-bearing candidate evidence tree（当前包括 `native_binding_v1` 与 `souffle_witness_v1`）
- query 会优先消费 `SupportArtifact.rule_ref_edges`，并按 `child_support_digest` 继续离线解引用 child support artifact；若 package 只有 legacy `rule_refs`，则保持 minimal fallback tree
- dto 可直接返回与 runtime 同构的 `candidate_evidence_tree`
- `service.static_ui` 可把 `candidate_id` 渲染成 recursive sectioned tree page，并继续下钻到既有 assertion detail 页面

当前 `audit.reader` / `AuditQuery` / `service.static_ui` 也已统一消费 `certainty_summaries.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: certainty_summary_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询物化的 certainty_summary
- query 的 `get_candidate_evidence_tree_narrative(candidate_id)` 会将物化的 certainty_summary 传入 narrative renderer，产出含 additive `certainty_lines` 的 narrative
- `service.static_ui` candidate evidence page 在 narrative block 末尾渲染 certainty section（当 certainty_lines 存在时）
- certainty_summary 在 export time 由 runtime service 预计算（通过 core `materialize_certainty_summary` helper），audit 侧不做 query-time 计算（因为 `condition_weights` 离线不可用）

当前 `audit.reader` / `AuditQuery` / `service.static_ui` 也已统一消费 `provenance_trees.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: provenance_tree_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询物化的 engine-native provenance tree
- `service.static_ui` candidate evidence page 在 certainty section 后渲染 additive `Engine Provenance` section（当 provenance_tree 存在时）
- provenance_tree 在 export time 由 runtime service 通过 query-bearing Souffle package replay 物化；audit 侧不做 query-time Souffle 执行

当前 `audit.reader` / `AuditQuery` / `service.static_ui` 也已统一消费 `provenance_statuses.jsonl`：

- reader 读取 JSONL rows → 解析为 `{candidate_id: provenance_status_dict}` mapping（旧 package 若没有该文件则返回空 dict）
- query 可按 `candidate_id` 查询单个 provenance status，也可做 package-level coverage summary
- `list_candidates_with_provenance()` / `list_candidates_without_provenance()` / `summarize_provenance_coverage()` 都按唯一 `candidate_id` 统计，而不是按 `candidate_ledger` 原始行数统计
- `service.static_ui` candidate evidence page 会渲染 provenance availability badge；当 `truncated=true` 时追加 depth-truncation warning
- `service.static_ui` landing page 会在 package 含 `provenance_statuses.jsonl` 时显示 provenance coverage / truncated proof metric cards

当前不会新增 `rule_trace_summary` 专用 artifact 文件；summary 是 read/query 层的纯派生面，不是新的 durable package contract。
当前也不会新增 `candidate_evidence_tree` 专用 artifact 文件；candidate tree 同样是 read/query 层的纯派生面，不是新的 durable package contract。
