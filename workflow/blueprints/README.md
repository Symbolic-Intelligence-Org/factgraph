# Blueprint Workflow

本目录定义"蓝图起草 -> 边界收口 -> 多轮实现 -> 文档同步 -> 蓝图归档"的项目工作流。

## 文档分工

- `workflow/foundations/architecture_principles.md`
  - 稳定设计哲学、系统边界、长期方向。
- `workflow/design/`
  - design-points(概念性 essays)+ decisions(ADR 离散决策)。
- `workflow/audit/`
  - drift / anti-drift 审计记录(vs-shipped / preflight / synthesis)。
- `workflow/blueprints/active/`
  - 正在推进的任务蓝图与 paired audit log。
- `workflow/memory/`
  - operational memory、session continuity 与 handoff archive;不承担当前实现真相。
- `src/factgraph/*/docs/`
  - 当前实现真相。
- `workflow/blueprints/archive/`
  - 按新流程归档的蓝图,以及显式标注 provenance 的 legacy reconstructed archive 条目。
- `workflow/heritage/blueprint_history/`
  - 历史遗留蓝图,不再作为活动工作区。

## 何时必须先建蓝图

以下任务在开始代码实现前必须先有蓝图:

- 跨模块特性开发
- 协议、契约、DTO、DSL 变更
- 架构收敛或分层调整
- 会引入新模块 docs 或新主文档入口的任务
- 需要多轮生成并防止 drift 的复杂任务

可以跳过蓝图的情况:

- 明显局部的 typo 修复
- 不影响行为的纯注释修复
- 范围极小、且不会引起文档漂移的测试修复

## 生命周期(简介)

5 个主路径状态 + 3 个分支状态,共 8 状态。详见下方 [State Rules](#state-rules) 和 [Valid State Transitions](#valid-state-transitions)。

### 1. Draft
- 记录问题、目标、非目标、涉及模块和待确认边界。
- 允许保留 open questions。

### 2. Scoped
- 问题边界、非目标、关键约束、验收标准已经明确。
- 从这个状态开始才适合进行多轮实现。

### 3. Implementing
- 实现中的每一轮生成都要对照 blueprint。
- 若发现需要扩边界,先更新 blueprint 和 audit,再继续。

### 4. Implemented
- 代码已完成。
- 相关模块 docs 已同步。
- `Outcome / Deviations` 已补齐。

### 5. Archived
- blueprint 与 audit 一起归档。
- 归档后的文档只承担历史 rationale,不承担当前真相。

### 6-8. Deviation states

- **`blocked`** — stalled on external dependency; record reason in audit log; resume to `implementing` when unblocked.
- **`abandoned`** — explicitly cancelled before completion; record reason in audit log; move to `archive/`.
- **`superseded`** — replaced by a newer blueprint; record successor link in audit log; move to `archive/`.

## Legacy Reconstructed Archive

当 `workflow/heritage/blueprint_history/` 中的旧蓝图需要进入新归档体系时,允许创建 reconstructed archive 条目,但这是一个窄范围桥接能力,不等价于标准归档流。

适用条件:

- 原始文档已经存在于 `workflow/heritage/blueprint_history/`
- 目标是让历史 rationale 可以被 `workflow/blueprints/archive/` 与 `docs/README.md` 稳定引用
- 不试图声称该文档当年真实经过了当前的 `active -> archive` 工作流

硬规则:

- reconstructed 条目必须直接标注:
  - `Archive Mode: reconstructed`
  - `Historical Source`
  - `Git First Seen`
  - `Migration Date`
- reconstructed 条目必须继续链接回原始历史文档
- reconstructed audit 必须区分"历史提炼内容"和"当前迁移事件"
- 不得伪造完整的现代状态流转或虚构当年的 audit
- `Section 7 Acceptance` 只能依据当前可验证证据打勾;不能证明的项应留空或在 `Outcome / Deviations` 中说明

## 命名规则

- blueprint: `YYYY-MM-DD_slug.md`
- audit: `YYYY-MM-DD_slug.audit.md`
- active 与 archive 保持相同 basename

## 最小执行清单

1. 在 `active/` 中创建 blueprint 和 audit(配对)。
2. 用 `workflow/templates/blueprints/` 中的模板起草。
3. 收口范围后把状态改为 `scoped`。
4. 若任务依赖外部比较、历史桥接或工作参考材料,把这些输入放入相应位置(`workflow/design/design-points/` / 或 obsidian workspace)并在 blueprint 中明确引用。
5. 实现期间把关键决策和 scope 变化写入 audit。
6. 代码完成后更新受影响模块的 `docs/`。
7. 若新增持久文档入口,更新 [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)。
8. 若新增或调整 session continuity 机制,更新 `workflow/memory/README.md` 与 `workflow/memory/current.md`,不要把 handoff 再放回 `docs/` 根目录。
9. 补齐 `Outcome / Deviations`,再归档到 `archive/`。

## 模板(per Q4 §4.4)

Authoritative starting points for new blueprints live in `workflow/templates/blueprints/`:

- [task_blueprint.md](../templates/blueprints/task_blueprint.md) — standard task blueprint (8-state lifecycle)
- [task_blueprint.audit.md](../templates/blueprints/task_blueprint.audit.md) — sibling paired audit log
- [legacy_reconstructed_archive.md](../templates/blueprints/legacy_reconstructed_archive.md) — reconstructed legacy archive
- [legacy_reconstructed_archive.audit.md](../templates/blueprints/legacy_reconstructed_archive.audit.md) — reconstructed legacy audit log

Manual drafting (not from template) is discouraged; see [`workflow/templates/README.md`](../templates/README.md) §customization policy.

## 旧档案区

历史蓝图保存在 [`workflow/heritage/blueprint_history/`](../heritage/blueprint_history/)。
它们可用于理解历史设计 rationale,但不能替代当前模块 docs,也不应用于开启新的活动任务。

---

# 详细治理规则

以下是 blueprint pillar 的正式 governance 规则(原 `AGENTS.md` 内容,SC-1 合并后已纳入此 README)。

## 角色

- `active/` 容纳 live 任务蓝图与对应的 paired audit log。
- `archive/` 容纳已完成、仍作 rationale 引用的蓝图,以及显式标注的 reconstructed legacy 归档条目。
- 模板位于 `workflow/templates/blueprints/`(per Q4 集中)。

## Required Practice

- 蓝图和 sibling audit 文件**一起创建**。
- 配对使用同 basename。
- 状态值必须是其中之一:`draft`、`scoped`、`implementing`、`implemented`、`blocked`、`abandoned`、`archived`、`superseded`。
- 蓝图描述问题、scope、约束、验收、文档影响、偏差。
- audit 文件按时间顺序记录决策事件、scope 变更、实现检查点。
- Reconstructed legacy 归档条目必须使用 legacy 模板,并显式标注 provenance。

## 状态规则

- `draft` — 仍允许探索 + open questions
- `scoped` — 边界已冻结,可以开始实现
- `implementing` — 代码生成 / refactor 进行中
- `implemented` — 代码完成、模块 docs 已更新;归档待行
- `archived` — 蓝图已移到 `archive/`,outcome 已记录
- `blocked` — 受阻于外部依赖;在 audit 记录原因;依赖解除后回到 `implementing`
- `abandoned` — 显式取消;在 audit 记录原因后归档
- `superseded` — 被新蓝图替代;在 audit 记录后继 link 后归档

## 允许的状态转换

主路径:
- `draft` → `scoped` → `implementing` → `implemented` → `archived`

允许的偏离:
- `implementing` → `scoped` — scope 需要重锁;先更新蓝图和 audit 再恢复
- `implementing` ↔ `blocked` — 受阻于外部依赖;解除后恢复 `implementing`
- 任一 active 状态 → `abandoned` — 决定取消;归档前在 audit 记录原因
- 任一 active 状态 → `superseded` — 被新蓝图替代;归档前在 audit 记录后继 link

不允许:
- 从 `scoped` 跳过 `implementing` 到 `implemented`
- 从 `archived` 回到任一 active 状态(改为开新蓝图)

例外:
- legacy reconstructed 归档条目可直接在 `archive/` 创建,前提是源文件已在 `workflow/heritage/blueprint_history/` 且条目显式标 `Archive Mode: reconstructed`。

## 归档规则

- 受影响的模块 docs 未更新前不可归档。
- 引入新持久文档入口时,`docs/README.md` 未更新前不可归档。
- 归档前必须填齐 `Outcome / Deviations` 段。
- 归档动作:`active/` 和 `archive/` 之间 mv 配对,basename 不变。

## Reconstructed 归档规则

- 使用模板 [legacy_reconstructed_archive.md](../templates/blueprints/legacy_reconstructed_archive.md) 和 [legacy_reconstructed_archive.audit.md](../templates/blueprints/legacy_reconstructed_archive.audit.md)。
- 必填 metadata 字段:
  - `Archive Mode: reconstructed`
  - `Migration Date`
  - `Git First Seen`
  - `Historical Source`
- reconstructed 条目可镜像标准 10-section 形状,但必须如实描述历史 context。
- 不可伪造过去的 `draft -> scoped -> implementing -> implemented` 链。
- audit 文件中,reconstructed 历史摘录与现代迁移事件**分开**记录。
- 当前模块 docs 或代码无法验证某 acceptance 项时,留空或在 `Outcome / Deviations` 中说明不确定性。

## Legacy 边界

- `workflow/heritage/blueprint_history/` 不是 active blueprint 区。
- Legacy 文件可作 rationale 引用,但不应在那里开新任务。

## Paired vs standalone audit(per Q3 §4.2)

本仓库的 "audit" 指**两个不同概念**:

- **Paired blueprint audit log**(`<basename>.audit.md` sibling,由本文件治理)— 每蓝图的状态转换事件日志 + 决策注释。Authority:`paired blueprint audit log`。与配对蓝图同位置。
- **Standalone audit record**(位于 `workflow/audit/`,由 [`workflow/audit/README.md`](../audit/README.md) 治理)— 跨切面漂移审计(`vs-shipped`)、实施前安全检查(`preflight`)、Q 闭合后重分桶(`synthesis`)。Authority:`working triage document`。

两者**不可互换**。Standalone audit 约定见 [`workflow/audit/README.md`](../audit/README.md)。
