# FactPy SDK 文档（实现对齐，v1）

本目录是 `src/kernel/sdk` 的代码对齐文档。SDK 是 Python product surface：负责 schema/DSL authoring、ergonomic facade、outward compatibility 与用户可见错误/结果对象。Canonical Python runtime authority 位于 `src/kernel/application`。

SDK 公开 API 仍以当前实现行为为准；runtime delegation 是实现事实，不改变用户调用方式。旧版英文快照原位于 `docs_old/sdk_old`，现已从工作树清理。

## 中文文档

- `src/kernel/sdk/docs/00_user_guide.md`
  - 面向用户的主指南（建议先读这个）。
- `src/kernel/sdk/docs/01_alignment_matrix.md`
  - 能力矩阵、SDK vs application ownership、当前边界、延期项。
- `src/kernel/sdk/docs/02_readwrite_and_ingest.md`
  - 读写与 ingest 专项参考。
- `src/kernel/sdk/docs/03_rules_and_derivations.md`
  - Rule/Query/Derivation DSL 专项参考。
- `src/kernel/sdk/docs/04_api_surface.md`
  - 顶层导出与 API surface 索引。
- `src/kernel/sdk/docs/05_cn_en_consistency_checklist.md`
  - 中英文档一致性检查表与同步规则。

## English Docs

- `src/kernel/sdk/docs/00_user_guide.en.md`
  - Main end-user guide (recommended first read).
- `src/kernel/sdk/docs/01_alignment_matrix.en.md`
  - Capability matrix, SDK vs application ownership, boundaries, deferred items.
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
  - Read/write and ingest reference.
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
  - Rule/Query/Derivation DSL reference.
- `src/kernel/sdk/docs/04_api_surface.en.md`
  - Public export and API surface index.

## 使用约定

- 本目录文档以 SDK v1 当前行为为准；行为变更应与文档同 PR 更新。
- SDK docs 描述 user-facing surface；runtime contract 细节应链接到 `src/kernel/application/docs/`，不要把 application internal DTO 当成 SDK public API。
- `kernel/sdk/__init__.py` 的 `__all__` 是 SDK product-surface 导出面，不 re-export application internals。
- 文档中的 “限制/未实现” 仅描述当前实现状态，不等同长期设计承诺。
