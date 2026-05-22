# Task Blueprint Audit: Consumer Usage Handoff — extract_document + HTTP API

- Blueprint: [2026-04-14_consumer-usage-handoff.md](./2026-04-14_consumer-usage-handoff.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-14 | draft | Blueprint created | Goal: package extraction pipeline as a handoff to colleagues. 5 docs identified (1 root README rewrite, 2 new under src/.../docs/, 1 update, 1 index update). Non-goal explicitly includes "no code changes". |
| 2026-04-14 | draft | Scope review v1 | User flagged 2 findings: P1 — scope was missing the two module `docs/README.md` index updates (`agent/extraction/docs/README.md` + `service/docs/README.md`) required by `module_docs_convention.md` so new files don't become half-orphans; P2 — Current Context misnamed the HTTP handler. Both fixed: scope expanded 5 → 7 docs, handler renamed to `extract_document_endpoint`. |
| 2026-04-14 | draft | Scope review v2 | User flagged 1 P2 finding: `§5 Proposed Shape` header still said "五份文档,两个层级" while the body had already been restructured to 7 docs / 3 layers in v2. Fixed — header now reads "七份文档,三个层级". |
| 2026-04-14 | scoped | Scope frozen | User approved draft v3; boundaries, doc split, and audit trail converged. |
| 2026-04-14 | implementing | Implementation started | Starting doc order: 05_extraction.md → service/docs/README.md → 01_overview.md → USAGE.md → agent/extraction/docs/README.md → root README.md → docs/README.md. |
| 2026-04-14 | implemented | All 7 docs shipped | 5 new + 2 major updates. 1023 tests still green (no code changes). Path consistency check passed. §10 Outcome filled. |
| 2026-04-14 | archived | Archive | Blueprint + audit moved to `archive/` with basename preserved. |

## Decision Notes

- 2026-04-14 — **draft v1**
  - Scope split into 3 layers: top-level (`README.md`) / module truth (`src/.../docs/USAGE.md` + `service/docs/05_extraction.md`) / index (`docs/README.md`)
  - Rationale for USAGE.md living under `agent/extraction/docs/` instead of `docs/`: AGENTS.md rule ("current implementation truth lives in that module's docs/ directory") — use手册属于 extraction 模块的对外表面,而不是跨仓库架构原则
  - Rationale for `05_extraction.md` numbering:接 `02_runtime_sessions.md` / `03_runtime_queries_views.md` / `04_rules_registry.md` 的既有序列
  - 本轮不 triage session 2 遗留的 active 蓝图(ontology / dialog-agent / market-alignment)——保持 scope 窄,后续一轮单独处理
  - 本轮不修 extraction schema 的 `.title` / `.exists` 语义陷阱 —— 记录到 USAGE.md "已知限制"章节,不动代码

- 2026-04-14 — **draft v2**(scope review v1 回应)
  - Scope expanded 5 → 7 docs: 加入两份模块 `docs/README.md` 的索引更新(`agent/extraction/docs/README.md` + `service/docs/README.md`)。理由:新增 `USAGE.md` / `05_extraction.md` 如果不在同级 README 里登记,会成为半孤岛,且违反 `module_docs_convention.md` 对模块 docs 入口的要求
  - `§4 Current Context` 中 HTTP handler 名称由 `handle_extraction_documents()` 更正为 `extract_document_endpoint(...)`(与 `src/factpy_kernel/service/extraction_v1.py:17` 实际符号一致)
  - `§7 Acceptance` 和 `§8 Implementation Plan` 同步扩展,新增两行验收 + 两个实施步骤(plan 现在 8 步)
  - `§9 Docs To Update` 同步到 7 份

- 2026-04-14 — **draft v3**(scope review v2 回应)
  - `§5 Proposed Shape` 开头摘要从"五份文档,两个层级"更正为"七份文档,三个层级",与 v2 已经实际分好的 top-level / 模块真相 / 索引三层一致;消除蓝图开头摘要与正文自相矛盾
