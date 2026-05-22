# Task Blueprint: Legacy Reconstructed Archive Rules

- Status: archived
- Created: 2026-03-15
- Last Updated: 2026-03-15
- Related Modules:
  - `docs/`
  - `docs/blueprints/`
  - `docs/blueprint_history/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/README.md](../README.md)
- Audit Log:
  - [2026-03-15_legacy-reconstructed-archive-rules.audit.md](./2026-03-15_legacy-reconstructed-archive-rules.audit.md)

## 1. Problem

当前新工作流已经定义了标准 blueprint archive 路径，但没有为 `docs/blueprint_history/` 提供一个安全、可追溯、不会伪造 provenance 的桥接方式。

## 2. Goals

- 在不破坏标准 archive 规则的前提下，为 legacy blueprint 提供进入 `docs/blueprints/archive/` 的明确路径
- 明确 reconstructed archive 与标准 archive 的区别
- 提供专用模板，避免后续用标准模板伪造历史流程

## 3. Non-goals

- 不批量迁移任何历史蓝图
- 不修改历史蓝图正文
- 不把 reconstructed archive 混同为标准 workflow 产物

## 4. Current Context

- 标准 archive 规则已存在，但默认要求从 `active/` 正常归档
- `docs/blueprint_history/` 已被定义为 legacy historical archive
- 当前缺少一个 repo-native 的 reconstructed archive 模板与规则

## 5. Proposed Shape

在现有 workflow 上增加一个窄范围补充：

- 只允许 `docs/blueprint_history/` 来源的旧蓝图创建 reconstructed archive 条目
- 这些条目直接落在 `docs/blueprints/archive/`
- 这些条目必须使用专用模板和 audit 模板
- 这些条目必须显式声明 `Archive Mode: reconstructed` 与 provenance 字段

## 6. Boundaries And Invariants

- 标准 archive 主路径不变
- reconstructed archive 不能伪造历史 workflow
- 当前实现真相仍以模块 docs 为准
- 原始历史文件继续保留在 `docs/blueprint_history/`

## 7. Acceptance

- [x] 已新增 reconstructed archive 的明确规则
- [x] 已新增专用模板与 audit 模板
- [x] 已在 docs 索引和历史说明中补充桥接语义
- [x] 未破坏标准 archive 规则的主路径

## 8. Implementation Plan

1. [docs/blueprints/AGENTS.md + README.md] 增加 reconstructed archive 的规则、边界和模板入口，先稳定规则面
2. [templates/] 增加专用 blueprint 与 audit 模板，避免后续误用标准模板
3. [docs/README.md + docs/blueprint_history/README.md] 补桥接说明，使新旧两套归档关系可被稳定引用

## 9. Docs To Update

- `docs/README.md`
- `docs/architecture_principles.md`
- `docs/blueprints/README.md`
- `docs/blueprints/AGENTS.md`
- `docs/blueprints/archive/README.md`
- `docs/blueprint_history/README.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 已为 legacy blueprint 回填建立正式、可追溯、非伪造式的 reconstructed archive 规则。
- 与 blueprint 不同的地方：
  - 本次只落了规则和模板，没有开始批量迁移历史蓝图。
- 为什么会有这些调整：
  - 先收口规则和 provenance，后续批量迁移才不会污染 archive 的可信度。
- 归档说明：
  - 本次任务已完成，可按标准流程归档。
