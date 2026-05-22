# Task Blueprint: Live Evidence URL — Runtime Permalink

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/query.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-20_live-evidence-url-runtime-permalink.audit.md](./2026-03-20_live-evidence-url-runtime-permalink.audit.md)

## 1. Problem

当前 proof-entry 的离线形态已经完整：

- static audit site 可为每个对象生成稳定页面路径
  - `candidate_evidence/{slug_id}.html`
  - `rule_traces/{slug_id}.html`
  - 以及 assertion / run / decision detail pages
- 这些页面可分享、可托管、可离线浏览

但 live runtime service 仍只有 POST JSON endpoints：

- `POST /queries/explain`
- `POST /queries/explain-tree`
- `POST /queries/explain-summary`
- `POST /queries/explain-narrative`

因此当前仍缺少一类用户可直接分享的 live URL：

- 无法从 `candidate_id` 直接得到一条浏览器可打开的 permalink
- 无法从 `rule_run_id` 直接得到一条 live proof-entry link
- 当前 static 页面必须先跑 `render_audit_static_site()` 再由外部 file server 托管，不是 on-demand

这条线讨论的不是 proof carrier，而是：**runtime service 是否要提供 live evidence permalink**。

## 2. Goals

- 明确 first-round live evidence URL 是否应进入 runtime service
- 冻结 permalink first-round 的对象范围
- 冻结 GET route 的 delivery shape（直接 HTML / redirect / 其他）
- 冻结与现有 static audit 渲染的复用关系

## 3. Non-goals

- 不重开 candidate/tree/rule-trace 的 carrier contract
- 不新增第二套 proof-entry HTML 渲染体系
- 不顺手扩到 assertion/run/decision 的全部 live permalink
- 不讨论 access control、鉴权或公网部署策略
- 不把 visual URL 问题扩成 graph UI 或 richer navigation

## 4. Current Context

- runtime service 当前是 session-based，主要暴露 POST JSON endpoints
- audit/static 已有稳定的 proof-entry HTML page shape，但属于离线导出消费面
- mother blueprint 当前把 “Visual evidence URL (live)” 记为部分完成：离线页面已存在，live shareable URL 仍缺
- proof-entry 里最像 first-round live permalink 候选的是：
  - `candidate_id`
  - `rule_run_id`

## 5. Proposed Shape

### 5.1 Positioning

本蓝图是一条窄 capability decision：

- 目标不是再造 explainability 数据面
- 目标是决定 live proof-entry URL 是否存在，以及以什么 delivery shape 存在

### 5.2 Freeze Questions

1. first-round live URL 应挂在哪些对象上？
   - `candidate_id`
   - `rule_run_id`
   - 或更宽的 assertion / run / decision
2. URL 形式应是什么？
   - runtime GET route 直接返回 HTML
   - runtime GET route redirect 到 static/audit page
   - 或其他 permalink contract
3. 是否需要 session-bound live URL？
   - 当前 runtime store 是 session-based
   - permalink 是否显式绑定 `session_id`
4. 与 static audit 如何复用？
   - 直接复用 static 渲染函数
   - 复用 DTO 层 + 新 HTML shell
   - 或其他复用边界

### 5.3 Frozen Positions

**Q1: First-round permalink 对象范围**
- **`candidate_id` + `rule_run_id` only**
- 不扩到 assertion / run / decision
- 这两个对应当前 proof-entry 的两个主面（evidence tree + rule trace）

**Q2: GET route delivery shape**
- **Runtime GET route 直接返回 HTML**
- 不做 redirect 到 static site（避免外部部署依赖）
- Route shape:
  - `GET /v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}` → HTML
  - `GET /v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}` → HTML

**Q3: Session-binding 立场**
- **First-round 明确是 session-bound ephemeral permalink**
- 不承诺 durable live URL
- 与 static audit export 的长期可分享页面边界清晰：
  - live permalink = ephemeral, session-scoped
  - static export = durable, file-based

**Q4: 与 static/audit 渲染的复用边界**
- **复用层级：static HTML page renderers + 既有 data shapes**
- **不要求 runtime 伪装成 `AuditQuery`**
- Runtime route 优先使用已有 runtime explain/query helper 产出的 tree/detail/narrative 数据
- 只有在某个页面确实缺少 runtime-side DTO 组装能力时，才补一个很薄的 data adapter
- 不先冻结为 AuditQuery-compatible adapter layer

## 6. Boundaries And Invariants

- 必须保持的边界：
  - live URL 不应要求重做 proof carrier
  - candidate / rule trace 页面内容应继续与当前 static proof-entry 高度同构
- 明确不做的内容：
  - assertion-origin taxonomy
  - salience / impact
  - engine parity 扩展
- 兼容性约束：
  - 现有 POST JSON explain endpoints 保持不变
  - 现有 static audit export 路径保持不变

## 7. Acceptance

- [x] first-round permalink 对象范围已冻结
- [x] GET route delivery shape 已冻结
- [x] session-binding stance 已冻结
- [x] 与 static/audit 渲染复用边界已冻结
- [x] blueprint outcome 已填写并归档

## 8. Implementation Plan

1. 验证 runtime 侧现有 helper 能否直接组出 static renderers 需要的 data shape
   - candidate evidence page: 需要 `tree + narrative`
   - rule trace detail page: 需要 `detail + assertion_index + narrative`
2. 若 data shape 对齐，在 runtime_v1.py 添加 2 个 GET route handlers
3. 复用 static_ui.py 的 page render functions
4. 添加 targeted tests（GET route 返回 HTML + 正确 content-type）
5. 同步 service/audit docs
6. 归档 blueprint

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - runtime 现已提供 2 条 session-bound live HTML permalink：
    - `GET /v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}`
    - `GET /v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}`
  - candidate page 直接复用 runtime tree + narrative 与 static candidate renderer
  - rule-trace page 通过一个纯 `detail payload` helper 复用 static rule-trace renderer
- 与 blueprint 不同的地方：
  - 实现里额外抽出了 `build_rule_trace_detail_payload(...)` 纯 helper，供 audit DTO 与 runtime permalink 共用
- 为什么会有这些调整：
  - rule-trace renderer 需要 DTO-enriched payload；抽纯 helper 比引入 `AuditQuery` adapter 更窄，也更符合 freeze 的复用边界
- 归档说明：
  - 本蓝图为小型 implementation slice，已完成并归档到 `docs/blueprints/archive/`
