# Audit Log: T1.1 — Additive 新 Rule 类(application protocol layer + unified atom canonical)

- Blueprint: [2026-05-22_t1-1-rule-class-additive.md](./2026-05-22_t1-1-rule-class-additive.md)
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Initial scope recorded.T1.1 是 5-Track 实施分解的第 1 个 sub-slice,foundation 角色;additive 引入新 `Rule` 类到 `factgraph.application.protocol.rule`,与旧 `factgraph.sdk.Rule` 共存。Parent essay 真源 §3.1-§3.14(C1-C21 + C45-C48,共 25 commitments)。轻量 cadence 模式:跳过 Stage 1 audit / Stage 2 Q / Stage 3 synthesis,blueprint draft → scoped → impl → closure → archive 主路径保留(per Track plan §1.2)。 |

## Decision Notes

### 2026-05-22 — Initial scope freeze (draft)

**TPQ-1 partial lock**:新 Rule 类路径 = `factgraph.application.protocol.rule:Rule`(类名 `Rule`,无 V2 / Atomic 等后缀)。

理由:
- Application-first(`feedback_application_first_runtime_authority`)— DTO + pure function 在 `kernel.application` 先落地,SDK 只作 ergonomic shell。本 slice 引入的新 Rule 必须先在 application protocol 模块落地。
- 在 `factgraph.application.protocol` 命名空间,无 `Rule` 命名冲突(SDK `Rule` 在 `factgraph.sdk.dsl`,模块路径不同)。
- 不需 `V2` / `Atomic` 等装饰后缀 — parent essay §3.10 已承诺"新 user 看到 `Rule` 就是 atomic AND-only"。
- SDK re-export(让 `factgraph.sdk.Rule` 指向新类)deferred 到 **T1.3**(命名冲突方案锁定时);本 slice 不动 SDK 表面。

**Cadence 模式 lock**:本 slice 与本 Track 内所有 sub-slice 走 **轻量手动模式**:
- 跳过 Stage 1 vs-shipped audit(parent essay 已锁 commitments,无需额外 audit doc)
- 跳过 Stage 2 per-Q decision docs(parent essay PENDING 项进 Non-goals;真正出现 load-bearing 歧义才回退 decision doc)
- 跳过 Stage 3 post-Q synthesis(Track plan §3 已给 ordering)
- 保留 Step 4.1 draft / Step 4.2 review tightening / Step 4.6 scoped / Step 4.7 impl / Step 4.8 closure / Step 4.9 archive
- 保留 sacred branch isolation + dirty 集保留 + per-commit verification ritual + 可以推进 mutual authorization

**Scope boundary lock**:
- 包含:新 Rule 类引入 + unified atom canonical normalization(~50-75 LOC lowering 扩展)+ ports 类型推断 + desc rendering + immutability + atom_id positional
- 排除:旧 SDK Rule hard-cut(T1.2)、SDK re-export(T1.3)、port + alias 完整锁定(T1.4)、atom kind canonical 9-list 文档化(T2.1)、RuleExpr(T3)、head(T4)、.eval(T5)
