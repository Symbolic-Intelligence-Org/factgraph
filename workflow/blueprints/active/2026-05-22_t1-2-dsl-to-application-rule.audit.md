# Audit Log: T1.2 — DSL ergonomic 扩展 + DSL→application Rule 桥接 + legacy reject

- Blueprint: [2026-05-22_t1-2-dsl-to-application-rule.md](./2026-05-22_t1-2-dsl-to-application-rule.md)
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | T1 Track 第 2 个 sub-slice;Track plan v1 expanded scope 锁定后第一个落地的 expanded slice。Scope:(a) SDK DSL ergonomic 扩展(`ExistsAtom.__getattr__` / `AttrRef.entity_type` / `User(...)` Ellipsis);(b) DSL→application Rule 桥接(新文件 `sdk/dsl/application_rule.py`,复用 shipped `lower_where` + `parse_where_ir_to_ast` 链);(c) legacy 形态 reject in 新 Rule path(bare AttrRef / 2-line / Pred / RuleRef)。轻量 cadence 模式:跳过 Stage 1 audit + Stage 2 Q + Stage 3 synthesis,blueprint draft → scoped → impl → closure → archive 主路径(per Track plan §1.2)。依赖方向 `sdk → application → core` 严格 forward — application 与 core 不被本 slice 修改。 |

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
