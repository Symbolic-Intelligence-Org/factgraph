# Blueprint Workflow

本目录定义“蓝图起草 -> 边界收口 -> 多轮实现 -> 文档同步 -> 蓝图归档”的项目工作流。

## 文档分工

- `docs/architecture_principles.md`
  - 稳定设计哲学、系统边界、长期方向。
- `docs/references/`
  - 外部比较、历史桥接和工作参考材料；可作为 blueprint 输入，但不承担当前实现真相。
- `docs/blueprints/active/`
  - 正在推进的任务蓝图与审计记录。
- `memory/`
  - operational memory、session continuity 与 handoff archive；不承担当前实现真相，也不替代 active blueprint。
- `src/factpy_kernel/*/docs/`
  - 当前实现真相。
- `docs/blueprints/archive/`
  - 按新流程归档的蓝图，以及显式标注 provenance 的 legacy reconstructed archive 条目。
- `docs/blueprint_history/`
  - 历史遗留蓝图，不再作为活动工作区。

## 何时必须先建蓝图

以下任务在开始代码实现前必须先有蓝图：

- 跨模块特性开发
- 协议、契约、DTO、DSL 变更
- 架构收敛或分层调整
- 会引入新模块 docs 或新主文档入口的任务
- 需要多轮生成并防止 drift 的复杂任务

可以跳过蓝图的情况：

- 明显局部的 typo 修复
- 不影响行为的纯注释修复
- 范围极小、且不会引起文档漂移的测试修复

## 生命周期

### 1. Draft

- 记录问题、目标、非目标、涉及模块和待确认边界。
- 允许保留 open questions。

### 2. Scoped

- 问题边界、非目标、关键约束、验收标准已经明确。
- 从这个状态开始才适合进行多轮实现。

### 3. Implementing

- 实现中的每一轮生成都要对照 blueprint。
- 若发现需要扩边界，先更新 blueprint 和 audit，再继续。

### 4. Implemented

- 代码已完成。
- 相关模块 docs 已同步。
- `Outcome / Deviations` 已补齐。

### 5. Archived

- blueprint 与 audit 一起归档。
- 归档后的文档只承担历史 rationale，不承担当前真相。

### 6-8. Deviation states (per `AGENTS.md`)

Three additional states exist for non-linear paths:

- **`blocked`** — stalled on external dependency; record reason in audit log; resume to `implementing` when unblocked.
- **`abandoned`** — explicitly cancelled before completion; record reason in audit log; move to `archive/`.
- **`superseded`** — replaced by a newer blueprint; record successor link in audit log; move to `archive/`.

See [`AGENTS.md`](./AGENTS.md) §State Rules + §Valid State Transitions for the full 8-state machine.

## Legacy Reconstructed Archive

当 `docs/blueprint_history/` 中的旧蓝图需要进入新归档体系时，允许创建 reconstructed archive 条目，但这是一个窄范围桥接能力，不等价于标准归档流。

适用条件：

- 原始文档已经存在于 `docs/blueprint_history/`
- 目标是让历史 rationale 可以被 `docs/blueprints/archive/` 与 `docs/README.md` 稳定引用
- 不试图声称该文档当年真实经过了当前的 `active -> archive` 工作流

硬规则：

- reconstructed 条目必须直接标注：
  - `Archive Mode: reconstructed`
  - `Historical Source`
  - `Git First Seen`
  - `Migration Date`
- reconstructed 条目必须继续链接回原始历史文档
- reconstructed audit 必须区分“历史提炼内容”和“当前迁移事件”
- 不得伪造完整的现代状态流转或虚构当年的 audit
- `Section 7 Acceptance` 只能依据当前可验证证据打勾；不能证明的项应留空或在 `Outcome / Deviations` 中说明

## 命名规则

- blueprint: `YYYY-MM-DD_slug.md`
- audit: `YYYY-MM-DD_slug.audit.md`
- active 与 archive 保持相同 basename

## 最小执行清单

1. 在 `active/` 中创建 blueprint 和 audit。
2. 用 `templates/` 中的模板起草。
3. 收口范围后把状态改为 `scoped`。
4. 若任务依赖外部比较、历史桥接或工作参考材料，把这些输入放入 `docs/references/` 并在 blueprint 中明确引用。
5. 实现期间把关键决策和 scope 变化写入 audit。
6. 代码完成后更新受影响模块的 `docs/`。
7. 若新增持久文档入口，更新 [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)。
8. 若新增或调整 session continuity 机制，更新 `memory/README.md` 与 `memory/current.md`，不要把 handoff 再放回 `docs/` 根目录。
9. 补齐 `Outcome / Deviations`，再归档到 `archive/`。

## 模板

- [templates/task_blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/task_blueprint.md)
- [templates/task_blueprint.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/task_blueprint.audit.md)
- [templates/legacy_reconstructed_archive.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.md)
- [templates/legacy_reconstructed_archive.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.audit.md)

## 旧档案区

历史蓝图仍保存在 [docs/blueprint_history/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/README.md) 所说明的位置。  
它们可用于理解历史设计 rationale，但不能替代当前模块 docs，也不应用于开启新的活动任务。
