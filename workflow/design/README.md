# Design Pillar(设计层)

概念性设计 essays(`design-points/`)与 ADR 风格的离散决策(`decisions/`)。本 pillar 由 Q2 锁定(commit `ae375ce5`)。

总入口治理见 [`workflow/AGENTS.md`](../AGENTS.md);canonical 方法论见 [`workflow/CADENCE.md`](../CADENCE.md)。

## 布局

```
workflow/design/
├── README.md             (本文件 — pillar 治理 + 导航)
├── design-points/
│   ├── README.md
│   ├── active/           (迭代演进中的 essays)
│   └── archive/          (满足 3 条件归档准则的 essays)
└── decisions/
    ├── README.md
    ├── active/           (proposed + adopted 的 ADR 记录)
    └── archive/          (superseded + withdrawn 的 ADR 记录)
```

## design-points 子层

### 角色

迭代写就的概念性设计 essays,跨越数周到数月。**权威性:候选设计 / 非权威参考。不是当前行为。** 一个 design-point 仅当被以下任一引用时才成为约束:

- 一个 adopted decision,或
- 一个 implemented blueprint,或
- 当前模块 docs(`src/factgraph/*/docs/`),或
- `workflow/foundations/architecture_principles.md`

design-point **不能直接覆盖 shipped 行为**。实现必须通过下游消费链(decision → blueprint → impl)到达代码,不可绕过。

### 生命周期(per Q2 §4.3)

`active/` — essay 还在迭代,仍可能产生新问题 / decisions / blueprints。

`archive/` — **同时满足以下三条**时归档:

1. 该 design-point 提出的所有 load-bearing 问题已写成 `workflow/design/decisions/` 中的正式 decision,**且**这些 decisions 已到达 closed ADR 状态(`adopted` / `superseded` / `withdrawn`)。
2. 该 design-point 衍生的实现-eligible 内容已 ship(被 `implemented` 状态的 blueprint 引用,该 blueprint 在 `workflow/blueprints/archive/`),或已被显式延期 / 被更新版的 design-point superseded。
3. 没有 `active` 状态的 blueprint 仍把该 design-point 当作进行中的设计依据。

也可通过 **被新 essay supersede** 归档(后继在 `Inputs` 引用前者,前者进 archive,即便上述三条未全部满足)。

design-points **不要求 Status 字段切换** — active essay 的迭代是常态。active/archive 目录归属是 canonical 生命周期信号;`Status` 字段(若存在)只是 `working` / `mature` / `n/a` 这类便利标记。

### Header 约定

每个 design-point 文件采用 Q4 §4.3 的 7-field metadata header,关键字段:

- `Authority: candidate design / non-authoritative reference`
- adoption-status 声明(重复上面的"成为约束需经..."链)

## decisions 子层(ADR 4-state,per Q2 §4.5)

### 状态

| Status | 含义 | 目录 |
|---|---|---|
| `proposed` | 审议中,尚非约束 | `active/` |
| `adopted` | **当前约束**;下游 blueprint 必须遵守 | `active/` |
| `superseded` | 被新 decision 替代(后继在 Inputs 引用) | `archive/` |
| `withdrawn` | 撤回(adoption 前或后均可);需写明理由 | `archive/` |

**关键**:`adopted` decisions 留在 `active/`,因为它们是**当前约束**。把它们移到 `archive/` 会暗示"不再约束当前行为",语义错误。这与 `blueprints/` 不同 — blueprint `implemented` 后立即 archive(blueprint 是历史 rationale,非当前约束)。

### 允许的状态转换

```
proposed → adopted      (审议结束)
proposed → withdrawn    (adoption 前取消)
adopted  → superseded   (被替代;引用后继)
adopted  → withdrawn    (罕见;需写明理由)
```

### 不允许的转换

- `adopted → proposed`(重开 closed decision;改为写新 decision 来 supersede)
- `superseded → adopted` / `withdrawn → adopted`(改为写新 decision 恢复约束)
- `proposed → superseded`(从未 adopted 的 decision 应 `withdrawn`,不可 supersede)

### 跨 active/archive 边界的 mv 规则

一个跨边界的 Status 切换(`adopted` → `superseded` 或 `adopted` → `withdrawn`)需在**同一 commit** 内 `git mv` 文件从 `active/` 到 `archive/`,并更新 `Status:` 字段。

## design-point vs decision 触发边界(per Q2 §4.7)

- **design-point** — 阐述一个概念区域、探索 tradeoffs、记录迭代推理。多步骤;迭代;可能历经数周。
- **decision** — 锁定一个 load-bearing question,在下游工作开始之前。离散;闭合;`adopted` 后即约束。

一个 decision 可以**无需 preceding design-point** 起草,如果问题足够窄、可直接从 audit findings 起草(例如 Slice 7C 的 Q-delta-decision 模式)。

## 模板(per Q4 §4.4)

权威起点位于 `workflow/templates/design/`:

- [design-point.md](../templates/design/design-point.md) — design-point essay 模板(含 authority 声明)
- [decision.md](../templates/design/decision.md) — ADR decision 模板(含 4-state 记录)

不鼓励手工起草(不用模板);见 [`workflow/templates/README.md`](../templates/README.md) §customization policy。

## 相关

- [`workflow/CADENCE.md`](../CADENCE.md) Stage 2(Q-resolution phase)— decisions 在 audit → Q → synthesis → blueprint 流程中的位置
- [`workflow/audit/README.md`](../audit/README.md) — audit pillar 的 synthesis sub-type 如何对 decisions 重分桶
