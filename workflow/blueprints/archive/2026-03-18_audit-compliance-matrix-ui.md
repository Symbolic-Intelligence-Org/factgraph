# Task Blueprint: Audit Compliance Matrix UI

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/compliance.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)
  - [2026-03-18_ecss-vcd-compliance-delivery.md](../archive/2026-03-18_ecss-vcd-compliance-delivery.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-18_audit-compliance-matrix-ui.audit.md](./2026-03-18_audit-compliance-matrix-ui.audit.md)

## 1. Problem

`ecss-vcd-compliance-delivery` 已经完成了 requirement/compliance facts 的最小 schema 和 offline query/DTO 能力：

- `AuditQuery.list_compliance_matrix(...)`
- `build_compliance_matrix_dto(...)`
- package wire format 保持不变

但静态 audit 站点仍然只暴露：

- runs
- decisions
- assertions
- authoring apply
- filter index pages

这意味着 Scenario B 已经“可查询”，但还没有真正进入 static audit delivery surface。对近期开会/演示而言，这仍然缺少一个直接可见的 VCD / compliance-matrix 页面。

## 2. Goals

- 在 static audit site 中新增一个最小可用的 compliance matrix 页面。
- 让首页和 site manifest / ui index 明确暴露该页面。
- 让 matrix row 能直接下钻到已存在的 assertion detail 页面，而不是重复发明 explain surface。
- 保持当前 `offline-query-first` 边界：页面完全基于 `AuditQuery.list_compliance_matrix(...)` 渲染。

## 3. Non-goals

- 不新增 live service endpoint。
- 不新增 raw package artifact，例如 `compliance_matrix.jsonl`。
- 不在本切片中设计 requirement authoring / data-entry surface。
- 不在本切片中引入新的 search facet 或复杂前端交互。
- 不在本切片中改变 compliance matrix 的 data model 或 DTO shape。

## 4. Current Context

- `render_audit_static_site(...)` 当前会生成：
  - `index.html`
  - `search.html`
  - `ui_index.json`
  - `site_manifest.json`
  - `runs/`
  - `decisions/`
  - `assertions/`
  - `authoring_apply_runs/`
  - `indexes/`
- static site 首页当前只有 runs、authoring apply 和 filter index 导航。
- `ui_index.json` 当前只包含 run/decision/assertion/authoring/filter 相关 lookup 与 counts，不含 compliance matrix。
- `ecss-vcd-compliance-delivery` 已明确：
  - compliance matrix 是 audit-side derived delivery object
  - `AuditQuery` 是主要读取边界
  - `explain_ref` 仅做更深的 evidence drill-down

## 5. Proposed Shape

### 5.1 UI Surface

第一轮新增单页：

- `compliance_matrix.html`

页面内容保持最小：

- requirement 行表格
- 列至少包含：
  - `req_id`
  - `title`
  - `standard_ref`
  - `status`
  - `review_milestone`
  - verification methods
  - RID links
  - assertion/evidence links

adopted conclusion：

- 第一轮不做每 requirement 单独详情页
- 只做一个总览 matrix 页面

### 5.2 Navigation And Manifest

第一轮需要同步更新：

- `index.html`
  - 增加 compliance matrix 入口
- `site_manifest.json`
  - 增加 `compliance_matrix` page path
- `ui_index.json`
  - 增加 compliance matrix summary/count 与页面链接

adopted conclusion：

- compliance matrix 进入 static site 顶层导航
- 但不强行并入现有 search facet

### 5.3 Evidence Drill-down

matrix 行不直接嵌入 explain payload，而是复用现有 assertion 页面：

- `requirement_asrt_id`
- `status_asrt_id`
- verification method `asrt_ids`
- RID link `asrt_ids`

这些 assertion id 在页面中渲染成到 `assertions/{slug}.html` 的链接。

adopted conclusion：

- matrix 是 summary/delivery layer
- assertion detail page 是下钻 layer
- 第一轮不额外接 `explain_ref`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 页面数据来源于 `AuditQuery.list_compliance_matrix(...)`
  - 不改变 audit package wire format
  - 不重复发明 assertion/explain detail page
- 明确不做的内容：
  - 不新增 compliance matrix search facet
  - 不新增 per-requirement detail page
  - 不新增 JS-heavy filtering UI
- 兼容性约束：
  - 原有 static site 页面和 manifest 字段保持兼容
  - 新页面是 additive change

## 7. Acceptance

- [x] `render_audit_static_site(...)` 会生成 `compliance_matrix.html`
- [x] 首页新增 compliance matrix 入口
- [x] `site_manifest.json` 与 `ui_index.json` 暴露 compliance matrix 页面和基础计数
- [x] matrix 页面至少渲染 `req_id/title/status/milestone/methods/RIDs` 并提供 assertion detail 链接
- [x] 现有 static site 页面不回归

## 8. Implementation Plan

1. 先在 `static_ui.py` 中新增 compliance matrix page renderer。
2. 把页面接入首页、site manifest、ui index。
3. 在 phase-3 contracts 中补 package-level static UI 回归测试。
4. 更新 `audit` 模块文档，并在完成后归档本蓝图。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-18_audit-compliance-matrix-ui.md`
- `docs/blueprints/active/2026-03-18_audit-compliance-matrix-ui.audit.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `static_ui.py` 新增 `compliance_matrix.html` 页面渲染，并把页面接入首页导航、`site_manifest.json`、`ui_index.json`。
  - matrix 页面以 `AuditQuery.list_compliance_matrix(...)` 为唯一数据来源，展示 requirement/status/milestone/method/RID 信息，并通过 assertion id 链接下钻到既有 assertion detail 页面。
  - `audit/docs/01_overview.md` 已同步记录 static site 现可生成 compliance matrix 页面。
- 与 blueprint 不同的地方：
  - 无实质偏差。第一轮仍保持单页总览，不新增 search facet 或 per-requirement detail page。
- 为什么会有这些调整：
  - additive 静态页面足以把 Scenario B 从“可查询 DTO”推进到“可演示 artifact”，同时避免把 scope 扩大到更重的 UI/search 设计。
- 归档说明：
  - 本切片不改变 package/export wire format，也不新增 live service endpoint。
  - 验证命令：`PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`，结果 `48 tests` 全部通过。
