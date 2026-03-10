# FactPy SDK 文档（实现对齐，v1）

本目录是 `src/factpy_kernel/sdk` 的代码对齐文档，默认以当前实现行为为准（不是设计草案）。
其中 `00_user_guide.md` 是语义基线；其余文档是专题切片，语义必须与 `00` 保持一致。

## 中文文档

- `src/factpy_kernel/sdk/docs/00_user_guide.md`
  - 面向用户的主指南（建议先读这个）。
- `src/factpy_kernel/sdk/docs/01_alignment_matrix.md`
  - 能力矩阵、当前边界、延期项。
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
  - 读写与 ingest 专项参考。
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
  - Rule/Derivation DSL 专项参考。
- `src/factpy_kernel/sdk/docs/04_api_surface.md`
  - 顶层导出与 API surface 索引。
- `src/factpy_kernel/sdk/docs/05_cn_en_consistency_checklist.md`
  - 中英文档一致性检查表与同步规则。

## English Docs

- `src/factpy_kernel/sdk/docs/00_user_guide.en.md`
  - Main end-user guide (recommended first read).
- `src/factpy_kernel/sdk/docs/01_alignment_matrix.en.md`
  - Capability matrix, boundaries, deferred items.
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.en.md`
  - Read/write and ingest reference.
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.en.md`
  - Rule/Derivation DSL reference.
- `src/factpy_kernel/sdk/docs/04_api_surface.en.md`
  - Public export and API surface index.
- `src/factpy_kernel/sdk/docs/06_realtime_execution_blueprint.en.md`
  - Zero-syntax-change execution/runtime optimization blueprint for real-time use cases.

## 使用约定

- 本目录文档以 SDK v1 当前行为为准；行为变更应与文档同 PR 更新。
- 先更新 `00_user_guide.md`，再联动 `01~06` 及对应英文文档，避免语义漂移。
- 文档中的 “限制/未实现” 仅描述当前实现状态，不等同长期设计承诺。
- 如需追踪公开导出面，请以 `factpy_kernel/sdk/__init__.py` 的 `__all__` 为准。
