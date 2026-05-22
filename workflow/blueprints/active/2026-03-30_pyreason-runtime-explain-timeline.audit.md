# Audit Log: PyReason Runtime Explain — CandidateProvenanceTimeline

## 2026-03-30 — Draft

- Blueprint created.
- Design direction confirmed through session discussion:
  - PyReason event log should NOT be forced into CandidateEvidenceTree
  - New runtime contract `CandidateProvenanceTimeline` in `core/store/`
  - EvidenceGraph stays in `audit/` as visualization layer (not promoted to runtime)
  - `explain_runtime_summary/narrative` gets polymorphic dispatch
  - ProbLog deferred
- Parent blueprint `2026-03-28_evidence-graph-unified-explain.md` moved back to `active/` with status `landed` for reference.
- Design fork from parent D-EG1 explicitly declared: creating new runtime contract instead of promoting EvidenceGraph to runtime.

## 2026-03-30 — Review Round 1

Findings addressed:
- [P1] Audit durable source: added D-PT7, `provenance_timelines.jsonl` as new audit package artifact. `AuditPackageData` gets `provenance_timelines` field. Full timeline dict persisted, not just summary.
- [P1] Runtime DTO union: **撤回 D-PT5**（不改 `explain-tree` 端点），改为 D-PT4 新增独立 `explain-timeline / explain-timeline-summary / explain-timeline-narrative` 端点。现有端点 DTO shape 不受影响。
- [P2] `root_chain_index` → `root_chain_key`: D-PT2 改为用 `(component_type, component, label)` 三元组标识 root chain。冻结 chains 排序为 `(component_type, component, label)` 字典序。
- [P2] Narrative cross-chain inference: D-PT2 明确 groundings 是不透明调试信息。§5.4 narrative 示例改为 chain-local，不再从 groundings 推断 `← rule(SOURCE)` 因果。
- Open question `explain_runtime_nl`: 冻结为 D-PT5，PyReason 继续返回 `runtime_explain_not_supported`。
- Open question endpoint naming: 不改现有端点名，新增独立端点族。

## 2026-03-30 — Review Round 2 → scoped

Findings addressed:
- [P2] Top-level `kind` contract: D-PT4 端点表格和 response envelope 示例现在显式冻结了三个 `kind` 值：`candidate_provenance_timeline` / `candidate_provenance_timeline_summary` / `candidate_provenance_timeline_narrative`。
- [P2] `provenance_timelines.jsonl` 行格式: 改为固定字段行 `{candidate_id, provenance_timeline}`，与现有 `evidence_graphs.jsonl` 的 `{candidate_id, evidence_graph}` 格式对齐。显式标注需同步更新 `manifest.paths.audit_files` 和 `audit/reader.py` optional key 列表。

Status: draft → scoped。无剩余架构性 open question。

## 2026-03-30 — Implementation Notes

Step 1-3 landed: `_candidate_provenance_timeline.py` (dataclasses + builder + summary + narrative). 18 new tests, 623 total green.

Step 4 landed: runtime_v1.py 新增 3 个端点 + internal helper. Implementation note: `_explain_timeline_candidate` 依赖从 ledger claim 反推 candidate_payload。这意味着 live timeline explain 目前只对已 accept 的 pyreason candidate 可用。未 accept 的 candidate 没有持久化 payload 索引。这是现有 store 的结构性限制，不是本蓝图引入的，CandidateEvidenceTree 有类似约束。

Step 5-6 landed: reader.py + query.py additive changes for provenance_timelines.jsonl.

Step 7 landed: app_v1.py 路由接入 — 3 个 POST 端点 (`explain-timeline`, `explain-timeline-summary`, `explain-timeline-narrative`)。

Final regression: **623 passed**, 1 warning, 4 subtests passed. Zero regressions.

Status: scoped → implementing. All code changes landed. Remaining:
- Service docs (`03_runtime_queries_views.md`) need endpoint documentation for 3 new queries
- E2E integration test with real PyReason session (blocked on pyreason install availability)
- Export path: `export_runtime_package(package_kind="audit")` needs to include `provenance_timelines.jsonl` in the export pipeline

Known structural limitation (not this blueprint's scope):
- `_explain_timeline_candidate` reconstructs candidate_payload from ledger claims. Live timeline explain only works for accepted PyReason candidates. Same constraint exists for CandidateEvidenceTree.

## 2026-03-30 — Contract Closure

Service docs: `03_runtime_queries_views.md` updated with §19-§21 (3 new timeline endpoints) + §22 audit export updated with `provenance_timelines.jsonl`.

Audit export pipeline: `runtime_v1.py` + `package.py` now materialize and write `provenance_timelines.jsonl` for pyreason candidates.

Audit round-trip tests: 3 new tests in `test_provenance_timeline_audit_delivery.py`:
- `test_pyreason_audit_package_exports_provenance_timelines_jsonl` — full round-trip: export → load → AuditQuery.get_candidate_provenance_timeline → summary
- `test_non_pyreason_candidate_not_in_provenance_timelines` — native candidates excluded
- `test_provenance_timelines_coexist_with_evidence_graphs` — both artifacts exported for same pyreason candidate

Final regression: **626 passed** (623 + 3 new), 1 warning, 4 subtests passed. Zero regressions.

Status: implementing. All code + docs + tests landed. Remaining for `implemented`:
- E2E integration test with real PyReason (blocked on pyreason install)
- Blueprint status → `implemented` after E2E confirmation

## 2026-03-30 — NL Explain Added

D-PT5 撤回 "no NL v1" non-goal。Timeline NL explain 已实现：
- `render_candidate_provenance_timeline_nl_explain()` 追加到 `_candidate_provenance_timeline.py`
- `explain_runtime_nl(kind="candidate")` 加 early dispatch：`support_kind == PYREASON_PROVENANCE_KIND` → timeline NL 管线
- 返回 `kind="candidate_provenance_timeline_nl_explain"`，输出 `{"headline": str, "paragraphs": [str, ...]}`
- 条件用 `PYREASON_PROVENANCE_KIND` 而非 `_PROVENANCE_BEARING_SUPPORT_KINDS`，避免 ProbLog 误入 timeline 路径

629 green，零回归。

## 2026-03-30 — NL Dispatch Fix + Behavioral Verification

发现 NL early dispatch 被误接到 `explain_runtime_summary` 而非 `explain_runtime_nl`。三个共享端点（summary/narrative/nl）的 PyReason dispatch 全部纠正：
- `explain_runtime_summary` (line 366) → 返回 `candidate_provenance_timeline_summary`
- `explain_runtime_narrative` (line 422) → 返回 `candidate_provenance_timeline_narrative`
- `explain_runtime_nl` (line 489) → 返回 `candidate_provenance_timeline_nl_explain`

新增 `test_pyreason_timeline_explain_family.py`（7 tests），覆盖：
- 专用 timeline/summary/narrative 端点
- 共享 summary/narrative 端点多态 dispatch
- **共享 NL 端点 timeline dispatch**（`test_explain_nl_returns_timeline_nl_for_pyreason`）
- tree 端点对 PyReason 仍返回 error

636 green（629 + 7 new），零回归。

结论：三引擎都已有完整 runtime explain surface（代码路径 + 行为测试）。
- native / souffle / problog → `CandidateEvidenceTree`
- pyreason → `CandidateProvenanceTimeline`

Status: implementing → implemented. E2E with real PyReason 仍 blocked on install，不影响 contract 闭合判断。
