# Decisions(ADR 决策)

ADR 风格的离散决策记录。每个 decision 锁定一个 load-bearing 设计问题,在下游 blueprint / 实现工作开始之前。

## ADR 4-state 生命周期(per Q2 §4.5)

| Status | 含义 | 目录 |
|---|---|---|
| `proposed` | 审议中,尚非约束 | `active/` |
| `adopted` | **当前约束**;下游必须遵守 | `active/` |
| `superseded` | 被新 decision 替代 | `archive/` |
| `withdrawn` | 撤回;需写明理由 | `archive/` |

**`adopted` decisions 留在 `active/`**,因为它们仍是**当前约束**。只有 `superseded` / `withdrawn` 进 `archive/`。这与 `workflow/blueprints/` 不同 — blueprint `implemented` 后立即归档(blueprint 是历史 rationale;adopted decision 是当前规则)。

## 当前 adopted decisions 索引

(decisions 落地后填充)

## 相关

- [`workflow/design/README.md`](../README.md) — 完整状态机、允许转换、跨边界 mv 约定
- `workflow/templates/design/decision.md` — 新 decision 的权威起点
- [`workflow/CADENCE.md`](../../CADENCE.md) Stage 2 — audit → Q → synthesis → blueprint 流程中的 Q-resolution 阶段
