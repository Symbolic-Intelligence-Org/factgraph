# Task Blueprint: Historical Blueprint Status Backfill

- Status: archived
- Created: 2026-03-15
- Last Updated: 2026-03-15
- Related Modules:
  - `docs/blueprint_history/`
  - `docs/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprint_history/README.md](../../blueprint_history/README.md)
- Audit Log:
  - [2026-03-15_historical-blueprint-status-backfill.audit.md](./2026-03-15_historical-blueprint-status-backfill.audit.md)

## 1. Problem

`docs/blueprint_history/` 中的历史蓝图存在零散状态标注，但整体不统一。  
这会导致后续引用历史蓝图时，难以快速区分“已实现 / 部分实现 / 讨论中 / 历史讨论”。

## 2. Goals

- 为选定的历史蓝图补齐统一状态头
- 保持状态判断保守，不夸大实现程度
- 不改写历史正文，不把历史蓝图改造成当前实现文档

## 3. Non-goals

- 不一次性整理所有历史蓝图
- 不重写正文结构
- 不创建 reconstructed archive 条目
- 不修改模块 docs

## 4. Current Context

- `docs/blueprint_history/README.md` 已经定义了推荐状态类型
- 当前只有少数历史蓝图显式写了状态
- 有一批被频繁引用的历史蓝图仍没有统一状态头

## 5. Proposed Shape

对选定历史蓝图统一补三行头部信息：

- `状态：...`
- `类型：...`
- `说明：...`

状态只使用 README 中已经定义的口径：

- `已实现`
- `部分实现`
- `讨论中 · 尚未实现`
- `历史讨论`

## 6. Boundaries And Invariants

- 不改正文论证与技术结论
- 不把无法验证的蓝图标成已实现
- 当前实现真相仍以模块 docs 为准
- fixture / checklist / README 这类附件不强行补状态

## 7. Acceptance

- [x] 目标历史蓝图都已补齐统一状态头
- [x] 未处理 fixture / checklist / README 这类非蓝图正文
- [x] 没有把历史蓝图误写成当前实现真相
- [x] 本次 blueprint 已补 Outcome / Deviations 并归档

## 8. Implementation Plan

1. [docs/blueprint_history/] 先对照清单确认本次要补的文件范围，只处理真正的蓝图正文
2. [docs/blueprint_history/*.md] 为第一批和第二批目标文件统一补 `状态 / 类型 / 说明` 头部，保持正文不动
3. [verification] 检查所有目标文件都已补齐状态头，并将本次任务归档

## 9. Docs To Update

- `docs/blueprint_history/*.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 已为 17 篇历史蓝图正文补齐统一的 `状态 / 类型 / 说明` 头部。
  - `已实现 / 部分实现 / 讨论中 · 尚未实现 / 历史讨论` 四类状态现在已能覆盖主要历史蓝图。
- 与 blueprint 不同的地方：
  - 没有新增第三批文件处理范围；仍保持只处理本次清单中的蓝图正文。
- 为什么会有这些调整：
  - 当前目标是先让高频引用与核心历史蓝图具备可读的状态语义，再决定是否继续扩大覆盖面。
- 归档说明：
  - 本次任务仅做状态回填，不改写历史正文，现已按标准流程归档。
