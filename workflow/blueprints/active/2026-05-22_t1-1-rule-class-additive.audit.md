# Audit Log: T1.1 — Additive 新 Rule 类(application protocol DTO,storing core AST)

- Blueprint: [2026-05-22_t1-1-rule-class-additive.md](./2026-05-22_t1-1-rule-class-additive.md)
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Initial scope recorded.T1.1 是 5-Track 实施分解的第 1 个 sub-slice,foundation 角色;additive 引入新 `Rule` 类到 `factgraph.application.protocol.rule`,与旧 `factgraph.sdk.Rule` 共存。Parent essay 真源 §3.1-§3.14(C1-C21 + C45-C48,共 25 commitments)。轻量 cadence 模式:跳过 Stage 1 audit / Stage 2 Q / Stage 3 synthesis,blueprint draft → scoped → impl → closure → archive 主路径保留(per Track plan §1.2)。 |
| 2026-05-22 | draft | Step 4.2 review tightening applied | User-driven review surfaced P1+P2 blockers + P3+P4 minors;blueprint restructured to Option A1 (scope degrade).P1+P2 → drop unified canonical authoring + SDK DSL extensions from T1.1;`Rule.where` storage 改为 core AST atoms;deferred 项 absorbed by T1.2 (Track plan §2 同步更新).P3 → docs path corrected to `application/docs/`.P4 → §5.3 wording fixed.Blueprint stays `Status: draft` pending next reviewer pass. |
| 2026-05-22 | draft | Step 4.2 v2 tightening applied | Second user review pass surfaced 3 findings.P1 (Blocker) — `frozen=True` Rule + tuple where + MappingProxyType ports gives only **shallow** immutability;core AST atom internals (`PredAtom.terms` / `InAtom.values` / `BuiltinAtom.args`) remain mutable lists per shipped `core/rules/where_ast.py`.`feedback_invariant_defense_in_depth` violation acknowledged.User chose downgrade (Option a) over deep-freeze (Option b) to keep slice atomic — recursive immutability hardening deferred to later slice.Blueprint §6 invariants + §7 acceptance + §10 outcome updated.P2 (Required) — audit log "Scope boundary lock" section had stale initial scope referring to "unified atom canonical normalization (~50-75 LOC lowering 扩展)";fixed to reflect post-tightening scope (DTO + core AST storage + validation + desc + atom_id/content_digest).P3 (Required) — Track plan §2 T1.1 row still asserted old scope ("unified atom canonical IR + lowering 复用 ExistsAtom/AttrRef/CompareExpr");rewritten to match Option A1 (additive application Rule DTO storing core AST atoms only). After this commit blueprint ready for Step 4.6 scoped anchor pending user confirmation. |
| 2026-05-22 | draft | Step 4.2 v3 tightening applied | Third user review pass surfaced 2 remaining stale-scope residuals after v2.P1 (Required) — Blueprint §2 Goals line 59 + §4.2 Current Context line 107 both still asserted "recursively immutable",contradicting §6 Invariants' "Shallow immutability only" paragraph added in v2.Both lines rewritten to shallow/container immutability with cross-reference to §6 for recursive deferral.P2 (Required) — Audit log H1 title still read "application protocol layer + unified atom canonical";updated to match blueprint title "application protocol DTO, storing core AST" for consistency.After this commit blueprint + audit log title + audit log scope assertions + Track plan T1.1 row all converged on post-tightening Option A1 scope.Ready for Step 4.6 scoped anchor on user "可以推进". |

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

**Scope boundary lock**(post Step 4.2 v2 tightening,2026-05-22):
- 包含:application Rule DTO + core AST atom storage(`PredAtom`/`CmpAtom`/`InAtom`/`BuiltinAtom`/`NotAtom`,reject `RuleRefAtom`)+ construction validation(atom kind allowlist + port var reachability + desc template)+ desc rendering(`%port_name` 插值)+ atom_ids positional property + content_digest deterministic property + shallow Rule immutability(frozen + tuple where + MappingProxyType ports)
- 排除:SDK DSL ergonomic syntax / unified canonical authoring `User(u).field == value` / DSL→core normalization / Ellipsis anonymous Var / cross-entity ref / atom dedup(全部 T1.2);旧 SDK Rule hard-cut(T1.2);SDK re-export(T1.3);port + alias 完整锁定(T1.4);**recursive immutability hardening**(deferred per Step 4.2 v2 P1 — `feedback_invariant_defense_in_depth` 已知 trade-off);atom kind canonical 9-list 文档化(T2.1);RuleExpr(T3);head(T4);.eval(T5)

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

### 2026-05-22 — Step 4.2 v2 tightening (P1+P2+P3 applied)

Second user review pass after Step 4.2 v1 tightening landed (`58ed1742`).Surfaced 3 findings — all valid.

**P1 (Blocker)** — Recursive immutability claim was false:Step 4.2 v1 §6 invariant said `frozen=True` + tuple where + MappingProxyType ports gives "recursively immutable",但实际上 core AST atom 内部 list 字段(`PredAtom.terms` / `RuleRefAtom.terms` / `InAtom.values` / `BuiltinAtom.args` / `AndExpr.atoms` / `OrExpr.branches`)全部是 `list[...]`,frozen dataclass 不冻结 list 内容。这是 `feedback_invariant_defense_in_depth` 所谓 "freezing theatre"。User 给二选:**(a)** downgrade invariant claim 为 "shallow Rule container immutable;atom internals per shipped" 或 **(b)** deep-freeze / canonical-clone atoms inside Rule 构造期。**User 选 (a) downgrade** 以保 T1.1 atomic(不需修改 shipped core AST types)。Blueprint §6 加 explicit "Shallow immutability only" paragraph + recursive hardening deferred 触发条件;§7 acceptance immutability test 改 phrasing 强调 shallow only;§10 outcome placeholder 加 deferred 条目。

**P2 (Required)** — Audit log Decision Notes 中 "Scope boundary lock (initial draft, 2026-05-22)" 区块的 "包含:" 行仍写旧 scope(`unified atom canonical normalization (~50-75 LOC lowering 扩展)`)— Step 4.2 v1 tightening 已经 degrade,这行 stale。**Adopted**:rewrite 该行为 post-tightening 当前 scope("application Rule DTO + core AST atom storage + validation + desc rendering + atom_ids/content_digest properties + shallow immutability");"排除:" 行同步加 "DSL ergonomic syntax / unified canonical authoring / DSL→core normalization (T1.2)" + "recursive immutability hardening (deferred per Step 4.2 v2 P1)";section heading 改为 "Scope boundary lock (post Step 4.2 v2 tightening, 2026-05-22)" 标明 supersede 关系。

**P3 (Required)** — Track plan §2 T1.1 row 仍写旧 scope("unified atom canonical IR + lowering 复用 `ExistsAtom`/`AttrRef`/`CompareExpr`")— Step 4.2 v1 tightening 只更新了 T1.2 row,T1.1 row 漏改。**Adopted**:rewrite T1.1 row 为 Option A1 scope("引入新 application Rule DTO + core AST atom storage + DTO validation + desc rendering + atom_id positional + content_digest;**不**触 SDK DSL;**不**实现 unified canonical authoring [T1.2]");性质标 Additive(unchanged)。

**After this tightening commit**:Blueprint + audit log + Track plan T1.1 row 三处 scope assertion 一致;user 表态 "comfortable moving to scoped" 即可走 Step 4.6 scoped anchor。

### 2026-05-22 — Step 4.2 v3 tightening (final residual fixes)

Third user review pass surfaced 2 remaining stale-scope residuals after v2 landed (`a46cec45`).Both 'Required' severity (not blockers — narrow fix-up).

**P1 (Required)** — Blueprint **still** asserted "recursively immutable" in two places that v2 missed:
- `blueprint:59` (§2 Goals **Immutability** bullet):"frozen dataclass + `where: tuple[Atom, ...]`(tuple,非 list)+ `ports` 用 `MappingProxyType` 或等价 frozen mapping;**recursively immutable**"
- `blueprint:107` (§4.2 Current Context **Invariant defense in depth** bullet):"frozen Rule + tuple where + frozen mapping ports;**recursively immutable**"

Both conflict with §6 Invariants "Shallow immutability only" paragraph that v2 added.**Adopted**:rewrite both bullets to shallow/container immutability language;§2 Goals bullet 加 explicit "Rule container 与 outer where/ports 不可变;内部 core AST atom 的 list 字段仍 mutable per shipped 现状" + cross-ref §6 deferred;§4.2 bullet 加 explicit `feedback_invariant_defense_in_depth` "freezing theatre" 已知 trade-off + user 显式选择 + cross-ref §6/§10。

**P2 (Required)** — Audit log H1 title 仍写 "application protocol layer + unified atom canonical" — 不对齐 blueprint title 与 post-tightening scope。**Adopted**:title 改为 "application protocol DTO,storing core AST",与 blueprint H1 一致。

**Convergence achieved**:Blueprint title + Blueprint §2/§4.2/§5/§6/§7/§9/§10 + Audit log title + Audit log Decision Notes (initial scope + v1 + v2 + v3) + Track plan §2 T1.1 row + Track plan §2 T1.2 row — 所有 scope assertion 现在一致表述 Option A1(application Rule DTO + core AST storage + DTO validation + desc + atom_ids + content_digest + shallow container immutability;无 SDK DSL touch;无 unified authoring;无 recursive imm hardening)。

**Ready for Step 4.6 scoped anchor**:本 commit 后等用户 "可以推进" 即走 `Status: draft → scoped` 单 small commit。
