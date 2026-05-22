# Audit Pillar(审计层)

Drift / anti-drift 记录:设计文档 vs shipped runtime 漂移审计、实施前安全检查、Q 闭合后重分桶 synthesis。本 pillar 由 Q3 锁定(commit `ae375ce5`)。

总入口治理见 [`workflow/AGENTS.md`](../AGENTS.md);canonical 方法论见 [`workflow/CADENCE.md`](../CADENCE.md)。

## ⚠️ 两个 "audit" 概念,不要混淆(per Q3 §4.2)

本仓库的 "audit" 一词指**两件不同的事**:

| 概念 | 文件名 | 位置 | 角色 | 治理位置 |
|---|---|---|---|---|
| **Paired blueprint audit log**(配对蓝图审计日志)| `<basename>.audit.md`(与 blueprint 同 basename 配对)| `workflow/blueprints/{active,archive}/` | 每蓝图的状态转换事件日志 + 决策注释 | [`workflow/blueprints/README.md`](../blueprints/README.md) |
| **Standalone audit record**(独立审计记录)| `YYYY-MM-DD_<topic>-<subtype>.md` | `workflow/audit/{active,archive}/` | 跨切面漂移审计、preflight 安全检查、post-Q synthesis | 本文件 |

本文档治理 **standalone audit record**。配对蓝图审计日志见 [`workflow/blueprints/README.md`](../blueprints/README.md) §Paired vs standalone audit。

## 布局

```
workflow/audit/
├── README.md            (本文件 — pillar 治理 + 导航)
├── active/              (consuming blueprint 在 workflow/blueprints/active/ 期间)
└── archive/             (consuming blueprint 已归档后随之归档)
```

扁平 active/archive 切分 — 无 sub-type 子目录。Sub-type 由文件名后缀编码。

## 三种 standalone sub-types(per Q3 §4.3)

| Sub-type | 文件名后缀 | 用途 | CADENCE 阶段 |
|---|---|---|---|
| **`vs-shipped`** | `YYYY-MM-DD_<topic>-vs-shipped.md` | 把设计文档对照 shipped runtime 完整 re-read(不用 grep snippet),建 5-state 分类表 + 暴露 open questions。 | Stage 1 audit |
| **`preflight`** | `YYYY-MM-DD_<topic>-preflight.md` | 在 preflight-row 起草时重读 blueprint 引用的 shipped 文件。Surface 5-bucket 严重度 findings,在 scoped anchor 之前。 | Step 4.3 |
| **`synthesis`** | `YYYY-MM-DD_post-q-<topic>-synthesis.md`(有 Q chain 时带 `post-q-` 前缀)| Q decisions 闭合后对 audit drift 重新分桶。5-bucket 输出。 | Stage 3 |

没有其他 sub-types;新增需对 Q3 做 Q-delta-decision。

## Preflight 触发条件(per Q3 §4.4)

Standalone preflight **REQUIRED** when 任一适用:

1. **Subtractive removal** — slice 删除 shipped public symbol / method / route
2. **Cross-module protocol change** — DTO 形状 / ledger format / identity formula 跨 ≥2 模块
3. **Namespace migration** — 包重命名或结构调整
4. **Historical-design compatibility** — 实现必须精确匹配历史设计(例如 compatibility shim)
5. **Pre-release verification** — rc.N → release tag 或 PyPI publish

Standalone preflight **OPTIONAL** when:

1. 单模块内的纯 additive feature
2. 已建面内的 bug fix
3. 纯 refactor + 完整 test 覆盖 + 无可观察行为变化
4. cleanup-style slice(per [`workflow/blueprints/README.md`](../blueprints/README.md) cleanup-slice cadence 段)
5. Tiny local fix(per [`workflow/CADENCE.md`](../CADENCE.md) Scope-and-Applicability)

**自愿 preflight 允许** — 不必须时仍可做,前提是在 blueprint §6 或 §10 记录理由。**有疑问时默认 required**。

## Synthesis 触发条件(per Q3 §4.5)

Standalone synthesis **REQUIRED** when:

1. ≥3 Q decisions 在一条 audit chain 中闭合,**且**
2. Audit findings 跨 ≥2 个 5-bucket(blueprint-eligible / cross-doc blocked / no independent action / already aligned / deferred)

Standalone synthesis **OPTIONAL** when:
- 单 Q decision 闭合(Q1-only slice),或
- 所有 audit findings 显然单 bucket,或
- cleanup-style slice 无 Q-resolution chain

## 生命周期(per Q3 §4.6)

- `active/` — consuming blueprint 处于 `draft` / `scoped` / `implementing` / `implemented`(即在 `workflow/blueprints/active/`)期间
- `archive/` — 在 consuming blueprint Step 4.9 archive 的**同一 commit batch** 中归档
- 一个 audit 服务多个 consuming slices 时,等**最后一个** consumer 归档才移

可选 `Status:` header 字段:`skeleton` / `complete` / `superseded`,仅做起草可见性 — 目录归属(`active/` vs `archive/`)才是 canonical 信号。

## 跨 branch 可见性(per Q3 §4.7)

Standalone audit 文件是 **slice-scoped artifacts**,不是全局可见的参考文档:

- 一个 audit 存在于创建它的 branch(通常 audit-only branch 或 consuming blueprint branch)
- 在 consuming slice 生命周期内,audits 是 branch-local。跨 slice 引用需显式 branch checkout
- Slice 闭合(Step 4.9 archive)时,audit + decision + blueprint chain 在 slice branch 上完成。Archive 本身**不**集成到 `master` 或任何 release branch
- 集成到 `master` 是**独立、显式、用户授权的 push 或 merge**,受 CADENCE Sacred-branch isolation rule 管辖
- "Globally visible" 指**用户授权的 canonical branch 集成**,不是 archive commit 本身

## Header 约定(per Q3 §4.8)

每个 standalone audit 文件包含 Q4 §4.3 的 7-field metadata header,audit-specific 值:

- `Status: <skeleton | complete | superseded>`(可选;目录归属才是 canonical)
- `Authority: working triage document; informs but does not lock implementation`

加 sub-type-specific extensions:

- **vs-shipped**:`Source intent:`(链接到被审计的设计文档)
- **preflight**:`Blueprint:`(链接到 consuming blueprint)
- **synthesis**:`Source audit:`(链接到 vs-shipped)+ `Closed Q decisions:`(Q decision 链接列表)

## 模板(per Q4 §4.4)

权威起点位于 `workflow/templates/audit/`:

- [vs-shipped.md](../templates/audit/vs-shipped.md) — Stage 1 audit 模板
- [preflight.md](../templates/audit/preflight.md) — Step 4.3 preflight 模板(含触发条件 check)
- [synthesis.md](../templates/audit/synthesis.md) — Stage 3 synthesis 模板(含 5-bucket 结构)

不鼓励手工起草;见 [`workflow/templates/README.md`](../templates/README.md) §customization policy。

## 相关

- [`workflow/blueprints/README.md`](../blueprints/README.md) §Paired vs standalone audit — 另一个 "audit" 概念
- [`workflow/CADENCE.md`](../CADENCE.md) Stage 1 / Step 4.3 / Stage 3 — 3 sub-types 如何嵌入 cadence
