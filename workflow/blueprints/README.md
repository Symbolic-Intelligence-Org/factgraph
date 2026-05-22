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

# Detailed Governance Rules

以下是 blueprint pillar 的正式 governance 规则(原 `AGENTS.md` 内容,已合并到此 README 内)。

## Role

- `active/` contains live task blueprints and audit logs.
- `archive/` contains completed blueprints that still matter as rationale, plus explicitly marked reconstructed legacy archive entries.
- Templates live at `workflow/templates/blueprints/` (centralized per Q4).

## Required Practice

- Create both the blueprint file and the sibling audit file together.
- Use the same basename for the pair.
- Keep status in one of: `draft`, `scoped`, `implementing`, `implemented`, `blocked`, `abandoned`, `archived`, `superseded`.
- Blueprints describe problem, scope, constraints, acceptance, docs impact, and deviations.
- Audit files record decision events, scope changes, and implementation checkpoints in chronological order.
- Reconstructed legacy archive entries must use the dedicated legacy templates and must state their provenance explicitly.

## State Rules

- `draft`: exploration and open questions are still allowed.
- `scoped`: boundaries are frozen enough for implementation to begin.
- `implementing`: code generation or refactoring is in progress.
- `implemented`: code and module docs are updated; archive is still pending.
- `archived`: blueprint moved to `archive/` with final outcome recorded.
- `blocked`: stalled on an external dependency; record reason in audit, resume to `implementing` when unblocked.
- `abandoned`: explicitly cancelled; record reason in audit, move to `archive/`.
- `superseded`: replaced by a newer blueprint; record the successor link in audit, move to `archive/`.

## Valid State Transitions

Forward path:
- `draft` → `scoped` → `implementing` → `implemented` → `archived`

Allowed deviations:
- `implementing` → `scoped`: scope needs re-freezing; update blueprint and audit before resuming.
- `implementing` ↔ `blocked`: pause on external dependency; resume to `implementing` when resolved.
- any active state → `abandoned`: decision to cancel; must record reason in audit before archiving.
- any active state → `superseded`: replaced by a new blueprint; record successor link in audit before archiving.

Not allowed:
- Skipping `implementing` between `scoped` and `implemented`.
- Transitioning out of `archived` back to any active state (open a new blueprint instead).

Exception:
- A legacy reconstructed archive entry may be created directly in `archive/` only when its source document already lives in `workflow/heritage/blueprint_history/` and the entry is explicitly marked `Archive Mode: reconstructed`.

## Archive Rules

- Do not archive until affected module docs are updated.
- Do not archive until `docs/README.md` is updated when a new durable docs entry was introduced.
- Before archiving, complete the blueprint's `Outcome / Deviations` section.
- Archive by moving both files from `active/` to `archive/` without changing the basename.

## Reconstructed Archive Rules

- Use [legacy_reconstructed_archive.md](../templates/blueprints/legacy_reconstructed_archive.md) and [legacy_reconstructed_archive.audit.md](../templates/blueprints/legacy_reconstructed_archive.audit.md).
- Required metadata fields:
  - `Archive Mode: reconstructed`
  - `Migration Date`
  - `Git First Seen`
  - `Historical Source`
- Reconstructed entries may mirror the standard 10-section shape, but they must describe historical context honestly.
- Do not invent a fake `draft -> scoped -> implementing -> implemented` chain for the past.
- In the audit file, separate reconstructed historical notes from verified migration events.
- If current module docs or current code cannot verify an intended outcome, leave the acceptance item unchecked or explain the uncertainty in `Outcome / Deviations`.

## Legacy Boundary

- `workflow/heritage/blueprint_history/` is not the active blueprint area.
- Legacy files may be cited as rationale, but new tasks should not be opened there.

## Paired vs standalone audit (per Q3 §4.2)

The word "audit" in this repo refers to two distinct concepts:

- **Paired blueprint audit log** (`<basename>.audit.md` sibling, governed by this file) — per-blueprint event log of state transitions + decision notes. Authority: `paired blueprint audit log`. Lives next to the blueprint it pairs with.
- **Standalone audit record** (in `workflow/audit/`, governed by `workflow/audit/README.md`) — cross-cutting drift triage (`vs-shipped`), pre-implementation safety check (`preflight`), or post-Q re-bucketing (`synthesis`). Authority: `working triage document`.

These are NOT interchangeable. See [`workflow/audit/README.md`](../audit/README.md) for the standalone-audit conventions.
