# Audit Log: T1.1 — Additive 新 Rule 类(application protocol layer + unified atom canonical)

- Blueprint: [2026-05-22_t1-1-rule-class-additive.md](./2026-05-22_t1-1-rule-class-additive.md)
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Initial scope recorded.T1.1 是 5-Track 实施分解的第 1 个 sub-slice,foundation 角色;additive 引入新 `Rule` 类到 `factgraph.application.protocol.rule`,与旧 `factgraph.sdk.Rule` 共存。Parent essay 真源 §3.1-§3.14(C1-C21 + C45-C48,共 25 commitments)。轻量 cadence 模式:跳过 Stage 1 audit / Stage 2 Q / Stage 3 synthesis,blueprint draft → scoped → impl → closure → archive 主路径保留(per Track plan §1.2)。 |
| 2026-05-22 | draft | Step 4.2 review tightening applied | User-driven review surfaced P1+P2 blockers + P3+P4 minors;blueprint restructured to Option A1 (scope degrade).P1+P2 → drop unified canonical authoring + SDK DSL extensions from T1.1;`Rule.where` storage 改为 core AST atoms;deferred 项 absorbed by T1.2 (Track plan §2 同步更新).P3 → docs path corrected to `application/docs/`.P4 → §5.3 wording fixed.Blueprint stays `Status: draft` pending next reviewer pass. |

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

**Scope boundary lock**(initial draft,2026-05-22):
- 包含:新 Rule 类引入 + unified atom canonical normalization(~50-75 LOC lowering 扩展)+ ports 类型推断 + desc rendering + immutability + atom_id positional
- 排除:旧 SDK Rule hard-cut(T1.2)、SDK re-export(T1.3)、port + alias 完整锁定(T1.4)、atom kind canonical 9-list 文档化(T2.1)、RuleExpr(T3)、head(T4)、.eval(T5)

### 2026-05-22 — Step 4.2 review tightening (P1-P4 applied)

User-driven Step 4.2 review surfaced 4 findings:

**P1 (Blocker)** — Boundary vs target API conflict:Blueprint promised `User(u).field == value` + `User(...)` unified authoring,但当前 shipped SDK DSL 不支持(`ExistsAtom` 无 `__getattr__`;`build_entity_dsl_call` Ellipsis raise)。要支持需改 `src/factgraph/sdk/schema.py` + `src/factgraph/sdk/dsl/expr.py`,与 §6 "不动 sdk/dsl/" 边界冲突。**User 给二选一**(A1 降级 vs A2 扩 SDK 改动)。**Drafter 选 A1**(降级)— 理由:依赖方向 `sdk → application → core` 单向、slice 原子性、blast radius 控制、对 `feedback_smaller_batch_design_blueprints` 一致。

**P2 (Blocker)** — Atom primitive 来源写错:Blueprint 说 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` 在 `core/rules/where_ast.py`,实际它们在 `sdk/dsl/expr.py`;`core/rules/where_ast.py` 的类型是 `PredAtom` / `CmpAtom` / `Var` / `Const` 等。User 建议 "T1.1 存 core-side AST/IR,SDK DSL 只作为输入 normalization 来源"。**Adopted**:T1.1 `Rule.where: tuple[Atom, ...]` 其中 `Atom = PredAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom`(`core.rules.where_ast` 已 ship 类型);`RuleRefAtom` 显式不允许(per parent C9);依赖方向 `application.protocol.rule → core.rules.where_ast`(forward only);无任何 `from factgraph.sdk` import。

**P3 (Minor)** — Docs 路径不存在:`src/factgraph/application/protocol/docs/` 不存在;现有应用层 docs 是 `src/factgraph/application/docs/`(README + 01_overview_en.md)。**Adopted**:新文档落 `src/factgraph/application/docs/rule.md`;`application/docs/README.md` 加入口;blueprint §9 + §1 + §4.1 path 全部修正。

**P4 (Minor)** — §5.3 标题自相矛盾:标题写 "本 slice 不 reject",正文写 "新 Rule 内构造时 raise"。**Adopted**:wording 改为 "旧 SDK 不 reject;新 Rule 构造期 reject";§5.3 表 wording 已修正,表格列名标明 T1.1 行为 vs Legacy 行为。

**Restructure summary**:
- §1 加 §1.1 "Step 4.2 review 发现的 scope refinement";§1.2 "T1.1 的角色"
- §2 Goals 去掉 "unified canonical 构造期 normalization" / "构造期 dedup" / "新增 lowering case" / "Anonymous `...` 处理" — 全部 T1.2;改为强调 "where 内部存储 core AST atoms"
- §3 Non-goals 加 "DSL ergonomic syntax(T1.2)" / "DSL → core normalization(T1.2)" / "Legacy 形态 hard-cut(T1.2)"
- §4 Current Context 表:核 IR primitives 行更正;新增 SDK DSL primitives 行(显式标 "完全不动");依赖方向显式
- §5 整体简化:DTO only,无 normalization 逻辑;新 §5.2 伪 API 锁定 `Rule.where: tuple[Atom, ...]` 形态
- §5.3 改写:接受 / 拒绝表,显式列出 5 allowed core atom kinds vs RuleRefAtom rejected vs SDK DSL types rejected
- §5.4 → "不在本 slice 实现的(留 T1.2)"
- §5.5 Ports 类型推断简化:entity_ref via pred `XYZ:exists` / 其他 → value
- §5.7 Tests 调整:5 atom kinds 允许 / RuleRefAtom + SDK DSL types 拒绝 / port reachability
- §6 Boundaries 加 "依赖方向 application.protocol.rule 不 import sdk.*"
- §7 Acceptance 加 "依赖方向静态可验证 — grep 'from factgraph.sdk' 在 application/protocol/rule.py 返空"
- §8 Implementation Plan 去掉 ~50-75 LOC lowering 扩展;预估 commits 调整
- §9 Docs 路径全部改为 `application/docs/`
- §10 Outcome 中预留 "Parent essay deviation"(core IR storage vs essay's SDK DSL primitive reuse — 高层意图保留,实现细节 deviation)

**Cascading**:Track plan §2 T1 row 同步更新 — T1.2 scope 从 "纯 subtractive(reject legacy)" 扩为 "additive(DSL ergonomic 扩展 + DSL→core normalization)+ subtractive(reject legacy in new Rule path)"。

**Blueprint 仍 Status: draft**;不进入 Step 4.6 scoped anchor 直到用户复核本 tightening 通过。
