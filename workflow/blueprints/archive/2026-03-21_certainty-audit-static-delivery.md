# Task Blueprint: Certainty Audit And Static Delivery

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/audit/`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/core/store/_certainty_materializer.py` (NEW)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [docs/blueprints/archive/2026-03-21_certainty-aware-narrative-nl-delivery.md](../archive/2026-03-21_certainty-aware-narrative-nl-delivery.md)
- Audit Log:
  - [2026-03-21_certainty-audit-static-delivery.audit.md](./2026-03-21_certainty-audit-static-delivery.audit.md)

## 1. Problem

`certainty_summary` 目前只在 runtime delivery 可用（explain-summary / explain-narrative / explain-nl）。audit package 和 static site 完全不含 certainty 信息：

- `export_package()` 不导出 `condition_weights` 也不导出 `certainty_summary`
- `AuditQuery.get_candidate_evidence_tree_narrative()` 调用 `render_candidate_evidence_tree_narrative(summary)` 时不传 `certainty_summary`
- static site 的 narrative block 不渲染 `certainty_lines`

**关键约束**：`condition_weights` 只存在于 registry filesystem（`FileAuthoringRegistry`），不在 audit package 里。离线 audit 无法访问 registry，因此 **certainty_summary 不能在 audit query-time 纯派生**。必须在 export time（runtime session 仍活跃时）物化。

## 2. Goals

- audit package 在 export time 物化 `certainty_summary` dict
- `AuditQuery` 能回读物化的 `certainty_summary` 并传给 narrative renderer
- static site candidate evidence page 渲染 `certainty_lines` section
- runtime / audit / static 三面在 certainty 可用时产出一致的 narrative 内容

## 3. Non-goals

- 不修改 `CertaintySummary` dataclass 或 `derive_certainty_summary()` 逻辑
- 不实现 probability lane
- 不引入 salience ranking / 排序
- 不修改 core 12-field summary set
- 不修改 runtime delivery 行为
- 不修改 `SupportArtifact` canonical bytes（certainty_summary 是 sidecar 数据）
- 不把 condition_weights 导出到 audit package（只导出 certainty_summary 计算结果）

## 4. Current Context

### 4.1 Audit Package 当前结构

`export_package()` 输出：

```
audit_package/
  candidate_ledger.jsonl      # candidate_id -> support_digest, support_kind
  decision_log.jsonl
  run_ledger.jsonl
  accept_writes.jsonl
  support_artifacts/
    <support_digest>.json     # SupportArtifact dict
  rule_trace_artifacts/
    <rule_run_id>.json        # RuleTraceArtifact dict
```

### 4.2 AuditQuery 的 summary/narrative 派生链

```
AuditQuery.get_candidate_evidence_tree(candidate_id)
  → support_artifact → build_candidate_evidence_tree() → tree dict

AuditQuery.get_candidate_evidence_tree_summary(candidate_id)
  → tree → summarize_candidate_evidence_tree_dict(tree) → summary dict

AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)
  → summary → render_candidate_evidence_tree_narrative(summary, locale="en") → narrative dict
  注意：当前不传 certainty_summary
```

### 4.3 Static site 渲染

```python
# static_ui.py
candidate_tree = build_candidate_evidence_tree_dto(query, candidate_id)
candidate_narrative_dto = build_candidate_evidence_tree_narrative_dto(query, candidate_id)
page = _render_candidate_evidence_page(candidate_tree, narrative=narrative)
```

`_render_candidate_evidence_narrative_block(narrative)` 渲染 6 个 section（headline / overview / evidence / rule_chain / terminal / drilldown），但不渲染 `certainty_lines`。

### 4.4 为什么不能 query-time 派生

`certainty_summary` 的计算需要：
1. `confidence_kind` — 当前只存在 runtime `Store` 的 session-scoped backref index
2. `condition_weights` — 只存在于 `FileAuthoringRegistry` 的 registry filesystem
3. evidence tree — audit package 里有（通过 support artifact 重建）

离线 audit 缺少 1 和 2，因此必须在 export time 物化 certainty_summary。

## 5. Proposed Shape

### 5.1 Certainty 物化 Helper 提取（两层拆分）

`_compute_certainty_summary_from_tree` 当前在 `service/runtime_v1.py`，依赖 `RuntimeSession`（service-layer carrier）和 `FileAuthoringRegistry`（authoring 包）。由于当前 import 拓扑（`core → authoring` 不存在，`adapters → authoring` 不存在），不能将完整 materializer 放入 `core/store/` 或 `adapters/`。

**解法**：拆分为两层：

**A) `core/store/_certainty_materializer.py`（NEW，不碰 authoring）**：

```python
# 纯函数 — 只依赖 core 包
def extract_single_referenced_support_tree(tree_dict) -> dict | None
def certainty_summary_to_dict(summary: CertaintySummary) -> dict
def materialize_certainty_summary(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    condition_weights: dict[str, float] | None,  # 已解析的 weights，由 caller 提供
) -> dict[str, Any] | None:
    """Core-layer certainty materialization.

    Encapsulates: confidence_kind check → tree eligibility guard →
    derive_certainty_summary → dict.
    不做 condition_weights lookup（那需要 authoring 包）。
    """
```

**B) `service/runtime_v1.py`（留在 service 层，已有 authoring access）**：

- `_lookup_condition_weights_for_candidate` 改为接收 `store: Store`（而非 `session: RuntimeSession`）
- import `FileAuthoringRegistry` 从 `authoring.registry_fs`（窄 import 面）
- `_compute_certainty_summary_from_tree` → thin orchestrator：lookup weights → `materialize_certainty_summary(store, ...)`

**Import 拓扑不变**：
- `core/store/_certainty_materializer.py` → 只 import `core.annotation`、`core.store.runtime`（同包）
- `service/runtime_v1.py` → import `core.store._certainty_materializer`（已有 `service → core` 边）
- `adapters/souffle/package.py` → 不 import materializer（只接收预计算 dict）

### 5.2 Export Contract 扩展

当前 `export_package(store, out_dir, options, query=None)` 不做 certainty 计算。certainty 计算留在 service 层。

**解法**：`export_package` 接收预计算的 certainty dict：

```python
def export_package(
    store: Store,
    out_dir: Path,
    options: ExportOptions,
    query: dict[str, Any] | None = None,
    *,
    certainty_summaries: dict[str, dict[str, Any]] | None = None,  # NEW
) -> Path:
```

- `certainty_summaries` 为 `{candidate_id: certainty_summary_dict}` mapping
- `None` 或空 dict → 不写 `certainty_summaries.jsonl`，不写 manifest key
- 只在 `package_kind == "audit"` 时消费

调用侧变更：
- `export_runtime_package()` 在 `runtime_v1.py` 中预计算所有 candidate 的 certainty_summaries，传给 `export_package(..., certainty_summaries=computed)`
- 非 runtime 调用方不传，向后兼容

### 5.3 Export Time 物化

`export_runtime_package()` 在调用 `export_package` 前，对每个 candidate 预计算 `certainty_summary`：

```
audit_package/
  ...existing files...
  certainty_summaries.jsonl   # NEW — one line per candidate that has certainty_summary
```

每行格式：

```json
{"candidate_id": "cand-123", "certainty_summary": {...}}
```

计算链路（在 `export_runtime_package` 中）：
1. runtime session 仍活跃，`Store` + `registry_root` 都可用
2. 遍历 candidate ledger，对每个 candidate：lookup weights → `materialize_certainty_summary(store, candidate_id, tree_dict, condition_weights=weights)`
3. 收集非 None 结果为 `{candidate_id: dict}` mapping
4. 传给 `export_package(..., certainty_summaries=mapping)`

`export_package` 的写入逻辑（纯 writer）：
1. `certainty_summaries` 为 None 或空 dict → 跳过，不写文件，不写 manifest key
2. 有内容 → 写 `certainty_summaries.jsonl`，每行一个 candidate
3. 在 manifest `audit_files` 中记录 `certainty_summaries` key

### 5.4 Audit Package Loading

`load_audit_package()` 增加 `certainty_summaries.jsonl` 的读取，复用现有 `_read_optional_jsonl` pattern：

- manifest `audit_files` 中有 `certainty_summaries` key → 按路径读 JSONL → 解析为 `{candidate_id: certainty_summary_dict}` mapping
- key 不存在或文件不存在 → 空 dict（向后兼容旧包）

存储在 `AuditPackageData.certainty_summaries: dict[str, dict[str, Any]]`。

注：现有类型是 `AuditPackageData`（`reader.py` L15），不是 `AuditPackage`。

### 5.5 AuditQuery 扩展

```python
# query.py
def get_candidate_certainty_summary(self, candidate_id: str) -> dict[str, Any] | None:
    return self.package.certainty_summaries.get(candidate_id)

def get_candidate_evidence_tree_narrative(self, candidate_id: str) -> dict[str, Any]:
    summary = self.get_candidate_evidence_tree_summary(candidate_id)
    certainty_summary = self.get_candidate_certainty_summary(candidate_id)  # NEW
    return render_candidate_evidence_tree_narrative(
        summary, certainty_summary=certainty_summary, locale="en",
    )
```

### 5.6 Static Site 扩展

`_render_candidate_evidence_narrative_block(narrative)` 增加对 `certainty_lines` 的渲染：

```python
certainty_lines = narrative.get("certainty_lines")
if certainty_lines:
    sections.append(_render_narrative_section("Certainty", certainty_lines))
```

### 5.7 一致性保证

runtime / audit / static 三面的 certainty narrative 内容必须一致：
- 同一棵 tree + 同一组 condition_weights → 同一个 `certainty_summary` dict
- 同一个 `certainty_summary` → `render_candidate_evidence_tree_narrative(summary, certainty_summary=cs)` 产出相同 `certainty_lines`
- runtime 在 request time 计算，audit/static 在 export time 物化——但两者都调用同一个 service 层 lookup + core 层 `materialize_certainty_summary` → `derive_certainty_summary` 路径

## 6. Boundaries And Invariants

- **Export-time only**：certainty_summary 在 export 时物化，不在 audit query-time 计算
- **Additive file**：`certainty_summaries.jsonl` 是新增文件，不改已有 audit package 文件
- **Backward compatible**：旧 audit package（无 `certainty_summaries.jsonl`）加载后 certainty_summaries 为空 dict
- **不改 SupportArtifact**：certainty_summary 不进入 support artifact canonical bytes
- **不导出 condition_weights**：只导出计算结果
- **Eligibility guard 不变**：多 rule / nested / 无 registry → `certainty_summary` 不写入
- **不改 runtime 行为**：runtime 的 3 个 explain 端点完全不变

## 7. Acceptance

- [ ] certainty 物化逻辑提取到 core 层 `_certainty_materializer.py`，不依赖 `RuntimeSession` 或 `FileAuthoringRegistry`
- [ ] `runtime_v1.py` 改为 thin orchestrator（lookup + core materializer），现有 runtime 行为不变
- [ ] `export_package` 新增 `certainty_summaries` keyword-only 参数（预计算 dict，纯 writer）
- [ ] `export_runtime_package` 预计算 certainty_summaries 传给 `export_package`
- [ ] `export_package` 在 certainty 可派生时写入 `certainty_summaries.jsonl`
- [ ] `load_audit_package` 读取 `certainty_summaries.jsonl`（缺失时兼容），`AuditPackageData` 新增 field
- [ ] `AuditQuery.get_candidate_evidence_tree_narrative` 传入 certainty_summary，产出含 `certainty_lines` 的 narrative
- [ ] static site candidate evidence page 渲染 certainty section
- [ ] 旧 audit package（无 certainty 文件）加载和渲染正常
- [ ] runtime / audit / static 三面 certainty narrative 内容一致
- [ ] 受影响模块 docs 已同步

## 8. Implementation Plan

### Phase 1：Helper 提取 + Export Contract

1. **[core/store/_certainty_materializer.py]** 新建 core-layer helper（不碰 authoring）：
   - 从 `runtime_v1.py` 提取纯函数：`extract_single_referenced_support_tree`、`_collect_referenced_support_nodes`、`_node_has_nested_referenced_support`、`certainty_summary_to_dict`
   - 新增 `materialize_certainty_summary(store, candidate_id, tree_dict, *, condition_weights)` — 接收已解析 weights
   - 签名只依赖 `Store + candidate_id + tree_dict + condition_weights`，不依赖 `RuntimeSession` 或 `FileAuthoringRegistry`

2. **[service/runtime_v1.py]** 改为调用 core helper：
   - `_lookup_condition_weights_for_candidate` 改签名 `session → store`，import `FileAuthoringRegistry` 从 `authoring.registry_fs`（窄 import 面）
   - `_compute_certainty_summary_from_tree` → thin orchestrator：lookup → `materialize_certainty_summary(store, ..., condition_weights=weights)`
   - 删除已移入 core 的纯函数

3. **[adapters/souffle/package.py]** `export_package` 新增 `certainty_summaries: dict[str, dict[str, Any]] | None = None` keyword-only 参数

4. **[service/runtime_v1.py]** `export_runtime_package` 预计算 certainty_summaries dict，传给 `export_package`

### Phase 2：Export 物化

5. **[adapters/souffle/package.py]** `export_package` 增加 certainty_summaries.jsonl 写入：
   - `certainty_summaries` 为 None 或空 → 不写文件，不写 manifest key
   - 有内容 → 写 JSONL + manifest `audit_files.certainty_summaries` key
   - 只在 `package_kind == "audit"` 时消费

### Phase 3：Audit Loading + Query

6. **[audit/reader.py]** `load_audit_package` 读取 `certainty_summaries.jsonl`，`AuditPackageData` 新增 `certainty_summaries` field
7. **[audit/query.py]** `AuditQuery` 新增 `get_candidate_certainty_summary`，`get_candidate_evidence_tree_narrative` 传入 certainty_summary

### Phase 4：Static Site

8. **[audit/static_ui.py]** `_render_candidate_evidence_narrative_block` 渲染 `certainty_lines`

### Phase 5：Tests + Docs

9. **[tests/test_certainty_explain_contracts.py]** 新增 audit round-trip + static certainty 测试
10. **[docs]** 同步：`03_runtime_queries_views.md`、`audit/docs/`、`core/annotation/docs/README.md`

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/core/annotation/docs/README.md`
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `core/store/_certainty_materializer.py` — service-neutral certainty materialization helper（不依赖 authoring）
  - `runtime_v1.py` — thin orchestrator：`_lookup_condition_weights_for_candidate(store, ...)` + `materialize_certainty_summary`；`_compute_all_certainty_summaries` 预计算全量 candidate certainty
  - `package.py` — `export_package(..., *, certainty_summaries)` 纯 writer，写 `certainty_summaries.jsonl` + manifest key
  - `runtime.py` — `Store.list_candidate_ids()` 公共方法
  - `reader.py` — `AuditPackageData.certainty_summaries` field，`_read_certainty_summaries` helper
  - `query.py` — `AuditQuery.get_candidate_certainty_summary()`，narrative 传入 certainty_summary
  - `static_ui.py` — narrative block 渲染 certainty section
  - 3 new tests (212 total)：audit round-trip parity、backward compat、static site rendering
  - 5 docs synced
- 与 blueprint 不同的地方：
  - `export_package` 参数从 `registry_root: str | None` 改为 `certainty_summaries: dict | None`（预计算 dict 而非 export-internal 计算）
  - materializer 拆两层：core 接收 pre-resolved weights，service 做 condition_weights lookup — 因为 `core → authoring` 会形成 cycle
  - `FileAuthoringRegistry` import 窄化到 `authoring.registry_fs`
  - Phase 4 测试走真实 evaluate→accept→export 链路（非手工 `_remember_candidate_support`），因为 audit 路径依赖 `candidate_ledger`
- 为什么会有这些调整：
  - import 拓扑约束：`core → authoring` 和 `adapters → service` 都会引入 cycle edge
  - 关注点分离：`export_package` 应是纯 writer，certainty 计算属于 runtime orchestration
- 归档说明：可归档到 `docs/blueprints/archive/`
