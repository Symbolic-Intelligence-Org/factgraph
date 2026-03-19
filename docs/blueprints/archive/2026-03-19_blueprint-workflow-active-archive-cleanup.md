# Task Blueprint: Blueprint Workflow Active/Archive Cleanup

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `docs/blueprints/README.md`
  - `docs/blueprints/active/README.md`
  - `docs/blueprints/archive/README.md`
  - `docs/session_handoff_2026-03-19.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/README.md](../../blueprints/README.md)
  - [docs/blueprints/AGENTS.md](../../blueprints/AGENTS.md)
- Audit Log:
  - [2026-03-19_blueprint-workflow-active-archive-cleanup.audit.md](./2026-03-19_blueprint-workflow-active-archive-cleanup.audit.md)

## 1. Problem

`docs/blueprints/active/` 当前混放了多份已经 `implemented` 且 archive 副本已存在的蓝图。这违反了当前 workflow 对 active/archive 的目录职责划分，也让 canonical handoff 和活动工作区入口继续指向已经完成的 active 路径。

此外，`2026-03-19_native-derivation-ruleref-execution-decision` 仍停留在 active，但没有 archive 对应项，说明 archive 补齐也不一致。

## 2. Goals

- 让 `docs/blueprints/active/` 只保留仍在推进的任务蓝图。
- 为仍在 active 的 `implemented` 蓝图补齐缺失的 archive 对应项。
- 修正 canonical handoff 中对这些已归档蓝图的 active 路径引用。

## 3. Non-goals

- 不重写历史 archive 蓝图的正文语义或状态体系。
- 不改动任何模块代码或模块真相 docs。
- 不顺手刷新 `session_handoff_2026-03-19.md` 的全部技术内容；只修正与 active/archive 清理直接相关的状态与路径。

## 4. Current Context

- `docs/blueprints/active/README.md` 已明确 active 目录只放当前仍在推进的任务蓝图。
- `docs/blueprints/AGENTS.md` 已明确：`implemented` 只是“archive still pending”，真正归档要移动到 `archive/`。
- 2026-03-19 这一轮已有多份 `implemented` 蓝图同时存在于 active 和 archive。
- `docs/session_handoff_2026-03-19.md` 仍引用若干将被清走的 active 路径。

## 5. Proposed Shape

- 在 active 中新增一份很窄的 cleanup blueprint 来追踪这次整理动作。
- 将已 `implemented` 且 archive 条目齐备的 2026-03-19 蓝图对从 active 中移除，仅保留 archive 版本。
- 对缺失 archive 的 `implemented` 蓝图先补 archive 对，再从 active 中移除。
- 最小修正 `docs/session_handoff_2026-03-19.md`，使其不再依赖这些已归档蓝图的 active 路径。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 只整理 blueprint workflow 入口，不改模块实现。
  - active 中仍处于 `draft` / `scoped` 的蓝图必须保留。
  - archive 中现有历史条目不得被大范围重写。
- 明确不做的内容：
  - 不把 archive 下所有旧条目的 `Status` 批量重写成 `archived`。
  - 不顺手更新与本次移动无关的历史 handoff 叙述。
- 兼容性约束：
  - canonical handoff 和 README 级入口不能留下失效的 active 链接。

## 7. Acceptance

- [x] `docs/blueprints/active/` 不再保留本轮已 `implemented` 且已归档的 2026-03-19 蓝图对。
- [x] `2026-03-19_native-derivation-ruleref-execution-decision` 补齐 archive 对应项并从 active 中移除。
- [x] `docs/session_handoff_2026-03-19.md` 中与本次整理直接相关的 blueprint 路径已改为 archive 或当前有效入口。
- [x] `docs/blueprints/active/README.md` / `docs/blueprints/README.md` 的目录职责仍与整理后的状态一致。

## 8. Implementation Plan

1. 新建 cleanup blueprint 和 audit，冻结本次整理范围。
2. 盘点 active 中所有 `implemented` 的 2026-03-19 蓝图，确认 archive 对应项是否存在。
3. 为缺失 archive 的 `native-derivation-ruleref-execution-decision` 补齐 archive 对应项。
4. 从 active 中移除这些已归档的 `implemented` 蓝图对。
5. 修正 canonical handoff 中对这些蓝图的 active 路径和状态描述。
6. 验证 active / archive 目录和 handoff 入口已一致，再补 Outcome 并归档本 cleanup blueprint。

## 9. Docs To Update

- `docs/session_handoff_2026-03-19.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 2026-03-19 这一轮已 `implemented` 的 blueprint / audit 对已从 `active/` 清出，仅保留 archive 版本。
  - 缺失 archive 的 `native-derivation-ruleref-execution-decision` 已补齐并归档。
  - `docs/session_handoff_2026-03-19.md` 已更新到当前真实状态，不再把 winning-branch 当作未开始的 open question，也不再依赖这些已归档蓝图的 active 路径。
- 与 blueprint 不同的地方：
  - 除了 handoff 以外，还修正了本次移动直接影响到的少数 archive 蓝图相对链接。
- 为什么会有这些调整：
  - 文件从 `active/` 移到 `archive/` 后，部分 `Related Docs` 相对路径会立即失效；修正这些链接属于本次移动的直接后处理。
  - 更广的 archive 链接标准化仍然没有展开，继续保持为独立后续清理项。
- 归档说明：
  - 本 cleanup blueprint 完成后归档到 `docs/blueprints/archive/`，不继续留在 active 工作区。
