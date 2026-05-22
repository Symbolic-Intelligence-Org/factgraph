# Workflow

`workflow/` 目录承载本仓库的 **canonical 工作流治理** — design / audit / decision / blueprint 生命周期、operational memory、heritage 归档。

## 入口指引

- **[AGENTS.md](./AGENTS.md)** — workflow pillar 总图 + 主要工作模式 lock-in + governance 冲突优先级
- **[CADENCE.md](./CADENCE.md)** — Audit-to-Archive Cadence(大型工作流任务的 canonical 方法论)

## Pillar 布局

| 子目录 | 角色 |
|---|---|
| `foundations/` | 稳定架构原则 + 模块文档约定 |
| `templates/` | 集中的文档模板库存(blueprints / design / audit 子树) |
| `design/` | Design-points(概念性 essays)+ Decisions(ADR-style 离散决策) |
| `audit/` | Drift / anti-drift 记录(vs-shipped / preflight / synthesis 三种 sub-type) |
| `blueprints/` | 任务级实现蓝图(8 状态生命周期) |
| `memory/` | Operational memory、session continuity、handoff archive |
| `working/` | 临时工作区(gitignored) |
| `heritage/` | 已闭合 / 历史归档 |

每个 pillar 自带 `README.md`(SC-1 后合并了原 AGENTS 内容),说明本 pillar 的 scope + 状态机 + 模板指针。

## 起源

本 `workflow/` 结构于 2026-05-22 由 workflow-governance-promotion slice 引入,把 Audit-to-Archive Cadence(原本只在 Claude auto-memory 中)提升为 canonical、team-visible、git-tracked 治理。

`docs/` 下的已有治理材料(architecture principles、blueprints、decisions、audit、memory)在同一 slice 中迁移到本树。Stage 1 audit 见 [`audit/active/2026-05-22_workflow-governance-vs-shipped.md`](./audit/active/2026-05-22_workflow-governance-vs-shipped.md)。
