# Audit Log: T1.2 — DSL ergonomic 扩展 + DSL→application Rule 桥接 + legacy reject

- Blueprint: [2026-05-22_t1-2-dsl-to-application-rule.md](./2026-05-22_t1-2-dsl-to-application-rule.md)
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | T1 Track 第 2 个 sub-slice;Track plan v1 expanded scope 锁定后第一个落地的 expanded slice。Scope:(a) SDK DSL ergonomic 扩展(`ExistsAtom.__getattr__` / `AttrRef.entity_type` / `User(...)` Ellipsis);(b) DSL→application Rule 桥接(新文件 `sdk/dsl/application_rule.py`,复用 shipped `lower_where` + `parse_where_ir_to_ast` 链);(c) legacy 形态 reject in 新 Rule path(bare AttrRef / 2-line / Pred / RuleRef)。轻量 cadence 模式:跳过 Stage 1 audit + Stage 2 Q + Stage 3 synthesis,blueprint draft → scoped → impl → closure → archive 主路径(per Track plan §1.2)。依赖方向 `sdk → application → core` 严格 forward — application 与 core 不被本 slice 修改。 |
| 2026-05-22 | draft | Step 4.2 v1 tightening applied | User read-only review surfaced 4 findings(2 Blockers + 2 Required)。P1: 不动 `_is_sdk_dsl_value` 全局语义(防 head-call kwargs 路径误判) — Ellipsis special-case 只在 `_looks_like_sdk_dsl_entity_call` positional arg 分支。P2: `_lower_compare` MUST emit existence pred when AttrRef.entity_type known + handle CompareExpr 一端为 ExistsAtom(cross-entity ref)— 缺少 existence emit 会让 unified syntax 产生语义假阳性。P3: drop test 计划中 `User(u), User(u).field == "x"` mixed form,7 unified forms 保持 pure。P4: `_convert_ports` 添加 `lv.label is None` 检查 — anonymous LogicVar 有 auto token 但 label=None,`not lv.token` 不会捕获。Blueprint §2.1 + §2.5 + §4.1 + §5.3 + §5.4b(new) + §5.6 + §7 + audit Decision Notes 全部更新。等用户复核 v1。 |
| 2026-05-22 | draft | Step 4.2 v2 tightening applied | User 复核 v1 后 surfaced 3 residuals(1 Blocker + 2 Required)。P1: form 4 `User(u).score > 0.5` 与 shipped lowering 不对齐 — shipped `_lower_compare` 仅支持 `==` for AttrRef paths。**User-locked deferral**:drop form 4,unified canonical 降为 **6 pure forms**(all equality only / bare existence);non-eq AttrRef compare 加 explicit Non-goals bullet。P2: 3 处 stale "_is_sdk_dsl_value 接受 Ellipsis" 残留(Related Modules / §5.1 file structure / Implementation Plan)全部 rewrite + test `TestEllipsisAsDslValue` rename 为 `TestEllipsisNotInDslValue`。P3: `User(..., ...)` multi-Ellipsis 测试语言残留改为 "两个独立 User(...) 调用生成不同 anonymous tokens";不测试 multi-arg 形态。Blueprint Related Modules + §2.5(forms 7→6)+ §3(加 non-eq deferred bullet)+ §5.1 + §5.7 + §7 + §8 全部更新。等用户复核 v2。 |
| 2026-05-22 | draft | Step 4.2 v3 final wording cleanup | Branch-discipline review confirmed T1.2 must stay on blueprint branch until scoped,then continue on a dedicated impl branch. During final read-only sweep,2 stale wording issues remained:§2.5 schema test still mentioned `User(..., ...)` multi-arg ambiguity;§9 docs update still said "7 形态" after v2 lowered canonical scope to 6 forms. Both were corrected before scoped anchor. |
| 2026-05-22 | scoped | Step 4.6 scoped anchor | Blueprint status moved `draft` → `scoped`; implementation must continue from this commit on a dedicated implementation branch,not on the blueprint branch. |

## Decision Notes

### 2026-05-22 — Initial scope freeze (draft)

**T1.2 scope per Track plan v1 expanded**(post T1.1 Step 4.2 review locked):
- (a) **SDK DSL ergonomic 扩展** — additive
  - `AttrRef` 加 optional `entity_type: str | None = None` 字段(default 保 None,legacy AttrRef 路径不变)
  - `ExistsAtom.__getattr__(field) → AttrRef(record_var, field, entity_type=self.entity_type)` — 新方法
  - `_is_sdk_dsl_value(Ellipsis)` returns True
  - `build_entity_dsl_call` 处理 `single Ellipsis arg → ExistsAtom(entity_type, anon_var)`
  - **不动** `LogicVar.__getattr__`(legacy 路径)
- (b) **DSL→application Rule 桥接** — additive 新文件
  - `src/factgraph/sdk/dsl/application_rule.py` 新建,~200-280 LOC
  - 函数 `build_application_rule(*, id, where, ports, version=None, desc=None) → ApplicationRule`
  - 实施步骤:pre-lowering reject → `lower_where` → `parse_where_ir_to_ast` → flatten AndExpr → ApplicationRule
  - 错误:`DSLToApplicationRuleError`(继承 `Exception`,domain-specific);区分 application 层 `RuleValidationError`
- (c) **Legacy 形态 reject in 新 Rule path** — 桥接 pre-lowering walk
  - reject:bare AttrRef compare(`u.field == "x"`)— 通过 `AttrRef.entity_type is None` 精确检测
  - reject:2-line form(`User(u), u.field == "x"`)— 同样 `entity_type is None` 检测
  - reject:`Pred(...)` raw atom — `isinstance(atom, DSLPredAtom)`
  - reject:`RuleRefAtom` — `isinstance(atom, DSLRuleRefAtom)`(per parent C9)
  - reject:OR-shape where(`[[a1], [a2]]`)— application Rule AND-only

**关键设计点**:
- AttrRef.entity_type 作为 legacy form 检测**精确标记**(非启发式)— 通过 unified syntax 来的 AttrRef 一定带 entity_type;通过 LogicVar.__getattr__ 来的不带
- 桥接复用 shipped `lower_where`(expr.py:290)+ `parse_where_ir_to_ast`(where_ast.py:99)— 无需重写 lowering 主干
- 依赖方向严格 `sdk → application → core`:application.protocol.rule.py 不导入 sdk;`sdk.dsl.application_rule` 导入 application + core

**非目标**:
- 不动 `factgraph.application.protocol.Rule`(T1.1 frozen)
- 不动 `factgraph.sdk.Rule`(legacy,T1.3)
- 不进 SDK 顶层 `__all__`(T1.3)
- 不实现 atom dedup(parent §3.5 F6 提到,但 lower_where 已通过 bindings 表确保 — 不需要桥接显式 pass)
- 不实现 RuleExpr 组合 / head / `.eval`(T3 / T4 / T5)
- 不实现 recursive immutability hardening(继承 T1.1 deferred trade-off)
- 不扩 ArithExpr / AggregateExpr 语义(T2.2 / T2.3)

**Scope boundary lock**(initial draft, 2026-05-22):
- 包含:SDK DSL ergonomic 扩展(`ExistsAtom.__getattr__` + `AttrRef.entity_type` + `User(...)` Ellipsis 路径)+ DSL→application Rule 桥接(`build_application_rule` 新函数 + `DSLToApplicationRuleError`)+ legacy 形态 4 reject + OR-shape reject + anonymous-not-as-port reject + tests(~510-690 LOC)+ application Rule docs 更新(unified-syntax + bridge usage)
- 排除:legacy SDK Rule path hard-cut(T1.3)、SDK 顶层 `__all__` migration(T1.3)、新 Rule SDK 顶层 Re-export(T1.3)、RuleExpr 组合(T3)、head(T4)、`.eval`(T5)、ArithExpr / AggregateExpr 扩展(T2.2 / T2.3)、atom kind 9-list 文档化(T2.1)、recursive immutability hardening(deferred)、atom dedup pass(由 lower_where bindings 表覆盖,本 slice 不显式实现)

**Blueprint 仍 Status: draft**;等用户 Step 4.2 review。

### 2026-05-22 — Step 4.2 v1 tightening (P1+P2+P3+P4 applied)

User Step 4.2 read-only review surfaced 4 findings — 2 Blockers + 2 Required。All valid。Applied per finding:

**P1 (Blocker)** — `_is_sdk_dsl_value` 共用于 `Field.__call__` kwargs + `EntityMeta.__call__` kwargs;全局接 Ellipsis 让 `User(field=...)` head-call 路径生成坏 HeadCall payload(lower 时炸)。**Adopted**:Ellipsis special-case **只在** `_looks_like_sdk_dsl_entity_call` 的 positional `len(args)==1 and args[0] is Ellipsis` 分支处理;`_is_sdk_dsl_value` 全局**不动**。§2.1 bullet 改写;§5.3 完整改写为新 Ellipsis 实施伪代码;§7 acceptance 加 `_is_sdk_dsl_value(Ellipsis) returns False` 防回归 test + kwarg Ellipsis 不被识别为 DSL call test。

**P2 (Blocker)** — Unified syntax `User(u).field == "x"` 的 where list 仅含 `[CompareExpr(AttrRef(...,entity_type="User"), "==", "x")]`,**ExistsAtom 不在 list**。若 `_lower_compare` 只用 `entity_type` 短路 bindings lookup 而不 emit existence pred → 缺少 `User:exists(u)`,违反 parent §3.5 unified canonical 的 "existence + field predicate" 语义。Cross-entity ref `LivesIn(li).user == User(u)` 同理需要双 existence emit。**Adopted**:`_lower_compare` 扩展为 emit existence pred 当 AttrRef.entity_type known + handle CompareExpr 一端为 ExistsAtom(cross-entity ref)。Bindings 表共享自然 dedup。§2.1 bullet 改写为 explicit emit requirement;§4.1 表格加 `lower_term` 行说明不需扩展(ExistsAtom 在 `_lower_compare` 内消费);新增 §5.4b `_lower_compare` 扩展 详细伪代码 + 3 关键性质;§7 acceptance 加 3 个 existence emit verification tests。

**P3 (Required)** — Test 计划列了 `User(u), User(u).field == "x"` 重复 ExistsAtom 形态 + "dedup 或不 dedup" 的模糊文字;与 §3 Non-goals 中"不实现 atom dedup" 矛盾。**Adopted**:7 unified canonical forms 重写为 **pure** unified syntax(无 explicit ExistsAtom + unified compare 混合);drop "重复 ExistsAtom" 形态;§2.5 改为列 7 显式 pure forms;§7 acceptance 加 "无 mixed 形态" 注解。Bindings dedup 仍 verify(natural,via bindings 表)— 不是 explicit dedup pass。

**P4 (Required)** — `_convert_ports` 当前伪代码只检查 `isinstance(lv, LogicVar)` 和 `not lv.token`;anonymous LogicVar(`label=None`)有 auto-generated token(非空),`not lv.token` 不会 trip → anonymous 通过桥接成为 port → 违反 parent C45(anonymous 不可为 port)。**Adopted**:`_convert_ports` 添加 `if lv.label is None: raise DSLToApplicationRuleError(...)` 显式检测;§5.6 改写;§7 acceptance test 改为用 `User(...).var` 或 `LogicVar()` 验证 label=None 反应,**非** token-emptiness 验证。

**Cross-cutting**:P2 修复让 unified syntax 在 legacy SDK Rule path **也能 work**(legacy 用户传 `factgraph.sdk.Rule(where=[User(u).status == "active"])` 现在不再 raise "variable not bound") — additive benefit,not breaking。

**Blueprint 仍 Status: draft**;等用户复核本 tightening 通过。

### 2026-05-22 — Step 4.2 v2 tightening (P1 form 4 deferral + P2 stale residuals + P3 multi-Ellipsis)

User 复核 v1 后 surfaced 3 residual findings(1 Blocker + 2 Required)。

**P1 (Blocker)** — `User(u).score > 0.5`(form 4)与 shipped lowering 不对齐:shipped `_lower_compare`(`expr.py:348` + line 372)对 AttrRef 路径**仅支持 `==`**,非等值 raise `SDKDSLError("entity attribute comparison sugar currently supports only '==' in SDK object DSL v1")`。若 T1.2 不扩展非等值 AttrRef lowering(涉及 temp var 生成 + CmpAtom IR 接入),form 4 acceptance 实施期会 fail。User 二选一:(A) 扩展 _lower_compare 支持 non-eq AttrRef compare / (B) T1.2 降级 equality only,`>`/`<` 等留后续。**Drafter 选 B(deferral)**— 理由:T1.2 已有较大 scope(DSL ergonomic + bridge + legacy reject + existence emit + 6 forms);non-eq AttrRef compare 是独立扩展需要 temp var 机制;保持 T1.2 atomic。Drop form 4 → unified canonical **6 pure forms**;§3 Non-goals 加 explicit deferred bullet(含 trigger 条件与受影响 syntax);§7 acceptance 改 "6 unit tests pass" + 标注 "non-eq AttrRef deferred"。

**P2 (Required)** — `_is_sdk_dsl_value accepts Ellipsis` 当前真相残留(v1 已 lock false 但蓝图 3 处 scope/implementation 文本仍写"接受 Ellipsis"):
- Line 9(Related Modules):`schema.py — _looks_like_sdk_dsl_entity_call 识别 Ellipsis;_is_sdk_dsl_value 接受 Ellipsis` → 改为 `_looks_like_sdk_dsl_entity_call positional Ellipsis special-case;_is_sdk_dsl_value 不动`
- Line 241(§5.1 file structure):`├── _is_sdk_dsl_value + 接受 Ellipsis(value is Ellipsis)` → 改为 `_is_sdk_dsl_value UNCHANGED (shared by head-call kwargs path)` + `_looks_like_sdk_dsl_entity_call + positional single-Ellipsis arg special-case`
- Line 600(Implementation Plan):`修改 schema.py(_is_sdk_dsl_value Ellipsis)` → 改为 `仅 _looks_like_sdk_dsl_entity_call positional 特判;_is_sdk_dsl_value 不动`

此外 test 结构中 `TestEllipsisAsDslValue # _is_sdk_dsl_value(Ellipsis) returns True` 也是 stale → 改为 `TestEllipsisNotInDslValue # returns False(P1 regression guard)` + 新 test `TestEllipsisInPositionalEntityCall` 验证 `_looks_like_sdk_dsl_entity_call((...,), {})` returns True / `((), {"f": Ellipsis})` returns False。

**P3 (Required)** — `User(..., ...)` 多 Ellipsis 测试语言残留(line 525 `TestMultipleEllipsis # User(...) * 2 不同 anon Var(? 当前 build_entity_dsl_call 只接 1 arg)`):当前 design 是 single positional Ellipsis special-case,`build_entity_dsl_call` 本身只接 1 positional arg。误导实现去处理多参数匿名 var。**Adopted**:rename + 改文字 → `TestEllipsisIndependence # 两个独立 User(...) 调用生成不同 anonymous tokens(不测试 multi-arg User(..., ...) 形态;build_entity_dsl_call 只接 1 positional arg)`;`TestEllipsisAnonymous` 同样 wording 改为强调"两个独立 User(...) 调用产生不同 tokens"。

**Convergence**:Blueprint Related Modules + §2.5 unified forms list + §3 Non-goals(加 non-eq AttrRef deferred bullet)+ §5.1 file structure + §5.7 test structure + §7 acceptance + §8 Implementation Plan 全部更新对齐;audit log 同步记录。

**Blueprint 仍 Status: draft**;等用户复核 v2 通过后走 Step 4.6 scoped anchor。
