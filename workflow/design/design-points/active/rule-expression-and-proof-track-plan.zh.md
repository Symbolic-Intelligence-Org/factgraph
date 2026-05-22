# Rule × Proof 实现 — 5-Track 实施分解计划

- Status: working planning artifact
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: implementation decomposition / 设计调度。**Not authoritative for design semantics** — design 真源是 [`rule-expression-and-proof-attempt.zh.md`](rule-expression-and-proof-attempt.zh.md)(parent essay)。本文只锁定"如何把 parent essay 切成可实现单元 + 各单元落地顺序"。
- Inputs:
  - [`rule-expression-and-proof-attempt.zh.md`](rule-expression-and-proof-attempt.zh.md) — parent design essay(2066 行,~100 commitments)
  - [`workflow/CADENCE.md`](../../../CADENCE.md) — cadence governance baseline
  - [`workflow/AGENTS.md`](../../../AGENTS.md) — workflow umbrella governance
- Outputs / Downstream:
  - T1-T5 5 个 Track scope 定义 + ~25 个 sub-slice 蓝图候选
  - 每 sub-slice 一个独立 blueprint 在 `workflow/blueprints/active/`(命名 `2026-MM-DD_t<N>-<sub>-<topic>.md`)
- Related:
  - [`evidence-tree-rainbird-style-v1.zh.md`](evidence-tree-rainbird-style-v1.zh.md) — sibling design-point(§7 evidence detail);独立 cadence
  - [`database-view-fg-layered-architecture.zh.md`](database-view-fg-layered-architecture.zh.md) — sibling design-point(view 子系统);独立 cadence

> **Authority reminder**:本文不是 vs-shipped audit,也不是 synthesis;不能直接定义 design 语义,也不能直接锁定 acceptance criteria。Sub-slice blueprint **不能仅凭本文 cite**,必须回链 parent essay 的具体 commitment(`C<N>`)+ shipped source line cite。

## 1. 立场与轻量模式

### 1.1 为什么需要本文

parent essay 体量过大(2066 行 / ~100 commitments / §3-§10 跨越 Rule body / RuleExpr 组合 / Head / `.eval` API / 引擎适配 / atom 语言):

- 单次 Stage 1 audit 覆盖全部 commitments → 800-1000 行 audit doc,实际不可行
- 单一 blueprint 落 100 commitments → 违反 `feedback_smaller_batch_design_blueprints`(rule-touching blueprint 必须 1-at-a-time)
- 整体走 CADENCE 9-stage(audit + Q + synthesis + per-slice 8-state)× 5 Tracks → governance overhead 远超 implementation overhead

### 1.2 本轮选定的轻量模式

| Cadence 元素 | 全量模式 | 本轮采用模式 |
|---|---|---|
| Per-Track Stage 1 audit | 单独 audit doc(`audit/active/...vs-shipped.md`)| **跳过** — parent essay 内 commitments 已锁(`C<N>` 序号),直接进 blueprint |
| Per-Track Stage 2 Q-resolution | 单独 decision doc per Q + 单独分支 | **跳过 by default** — parent essay 内 PENDING 项(`fg.eval.why_not` / §6 task split / §9 joins 等)进 blueprint Non-goals;真正出现 load-bearing 歧义时才回退到 decision doc |
| Per-Track Stage 3 synthesis | 单独 synthesis doc | **跳过** — 本 track plan 自身充当 sub-slice ordering source |
| Per-sub-slice Stage 4 blueprint | 完整 8-state + 配对 audit log + preflight + scoped anchor + impl + closure + archive | **轻量保留** — blueprint 是实施粒度的真单元;每 sub-slice 一份;独立 preflight 仅在用户或风险触发时启用 |
| Per-commit verification ritual | 全量保留 | **保留** — sacred branch + dirty 集 + branch check |
| 可以推进 mutual authorization | 全量保留 | **保留** — 每 sub-slice 之间用户授权 |
| Pre-impl grep amendment (Step 4.6.5) | 大型 subtractive slice 触发 | **未来大型 subtractive slice 保留** — T1.2 已按轻量模式完成且 skipped independent pre-impl grep(closure deviation 已记录);T5.9 等大 hard-cut slice 仍应执行 |
| Sacred branch isolation | 全量保留 | **保留** |

**触发回退到 heavy cadence 的条件**(任一发生则当前 Track 升级):

- sub-slice impl 期间发现 cross-Track 矛盾,需要跨 Track 协调 → 启动 Stage 1 mini-audit
- 出现两个 commitment 显式冲突 / parent essay PENDING 项必须先决再实施 → 启动 Stage 2 decision doc
- sub-slice 数超出本文预估的 2 倍以上 → 启动 Stage 3 synthesis 重排

## 2. 5-Track 分解

### T1: Rule body 重塑(§3,foundation)

**Scope**:parent essay §3.1-§3.14;C1-C21 + C45-C48(共 25 commitments)

**核心交付**:新 `Rule(id, version, desc, where, ports)` user-facing 类,5 字段,AND-only,unified atom canonical(`EntityType(var).field == value`)。

**Sub-slices**:

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T1.1** | 引入新 application Rule DTO 在 `factgraph.application.protocol.rule:Rule`(additive;与旧 `factgraph.sdk.Rule` 共存,类名直接是 `Rule`,无 V2/Atomic 后缀)。`Rule.where` 内部存储 **core AST atoms**(`PredAtom`/`CmpAtom`/`InAtom`/`BuiltinAtom`/`NotAtom`,from `core/rules/where_ast.py`;**reject `RuleRefAtom`** per parent C9)。构造期 validation + desc rendering(`%port_name` 插值)+ atom_ids positional property + content_digest deterministic property + **shallow** Rule immutability(frozen + tuple where + MappingProxyType ports)。**不**触 SDK DSL;**不**实现 unified canonical authoring `User(u).field == value`(T1.2);**不**做 recursive immutability hardening(deferred per `feedback_invariant_defense_in_depth` trade-off 选择)| Additive | T2.x / T1.2 / T1.3 / T1.4 / T3.x / T4.x / T5.x 的 prerequisite |
| **T1.2** | **Implemented + archived 2026-05-22**(`3aa229c6` impl / `ca68103e` archive):(a) **SDK DSL ergonomic 扩展** — `ExistsAtom.__getattr__` 返回 `AttrRef(entity_type=...)`;`User(...)` positional Ellipsis → anonymous `LogicVar`;cross-entity ref `LivesIn(li).user == User(u)` 支持并 emit 双 existence pred;(b) **DSL → application Rule bridge** — `factgraph.sdk.dsl.build_application_rule(...)` 把 SDK DSL atoms lower 到 `core.rules.where_ast` Atom types 并构造 T1.1 `application.protocol.Rule`;bridge 内部按 core `Var.name` canonicalize 同名变量,避免 `Origin.path` 导致 ports 与 predicates object inequality;(c) **新 Rule path reject** legacy 2-line 形态 + `Pred(...)` + 裸 AttrRef 比较 + RuleRef + OR shape + anonymous port。**旧 SDK Rule 不动直到 T1.3**。Canonical forms 降为 **6 equality-only / bare-existence forms**;form 4 `User(u).score > 0.5` / non-eq AttrRef compare deferred(需要 temp var + CmpAtom IR 接入)。| Additive + Subtractive | 已按轻量手动模式完成;未跑独立 Step 4.6.5 pre-impl grep,作为 T1.2 closure deviation 记录在 archived blueprint。后续 T2.2/T2.3 处理 ArithExpr/AggregateExpr 时需重新审视 non-eq AttrRef compare |
| **T1.3** | 新旧 Rule 命名冲突方案锁定与执行(C14 deferred 项:A/B/C 三选一)— 涉及现行 `kernel.sdk.Rule` 的迁移 | 半 subtractive | 与 T5 协调:`.eval` API 完成前不能彻底替换旧 Rule;**可能 defer 到 T5 中段** |
| **T1.4** | **剩余 alias / port contract slice**:ports 显式声明的用户面语义 + `.as_(...)` template-stable alias + occurrence alias validation + RuleExpr `.as_()` 所需 alias 基础设施。**不再包含**:Rule shallow immutability / atom_id 位置语义 / basic desc rendering(T1.1 已落地),anonymous `User(...)` Var handling(T1.2 已落地)。| Additive | T3 RuleExpr `.as_()` 实施依赖此处的 alias 基础设施 |

**依赖**:无(foundation)

**Shipped 受影响 surface**(预估):
- `src/factgraph/core/rules/rule_ir.py`(494 LOC)、`rule_ast*.py`(505 LOC)、`where_eval.py`(1135 LOC)
- `src/factgraph/sdk/__init__.py` 导出
- `src/factgraph/sdk/dsl/` 完整目录(待查)
- tests/rules/* 全量(blast radius 评估留 T1.1 blueprint Step 4.3 preflight)

---

### T2: Atom 语言闭合 + adapter gap(§10 + §8)

**Scope**:parent essay §10.1-§10.6 + §8.1-§8.9;C97-C105 + C94-C96(共 11 commitments + 2 grammar 对照表)

**核心交付**:9 IR atom kinds(pred / eq / ne / gt / ge / lt / le / in / not)canonical;ArithExpr / AggregateExpr value-producing forms;Souffle / ProbLog adapter `ne` + ArithExpr + AggregateExpr dispatch 补齐。

**Sub-slices**:

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T2.1** | 9 IR atom kinds 名单 + ir_arity + tuple shape 文档化 + Souffle `ne` dispatch + ProbLog `ne` dispatch(~100 LOC 总)| Additive(adapter)| 与 T1.1 部分并行 OK — 若不引入新 Rule 类内部表示则无冲突 |
| **T2.2** | ArithExpr(`+` / `-` / `*` / `/`)IR shape + comparison LHS/RHS 嵌套 + Souffle ArithExpr lower wire(~50 LOC,复用既有 5 sub-kinds 的 dispatch)+ ProbLog dispatch via `is/2`(~100 LOC)+ div-by-zero 锁定语义 | Additive | 触及 `where_eval` / `where_ast`,与 T1.2 hard-cut 可能竞争同源,**先 T1.2 后 T2.2** |
| **T2.3** | AggregateExpr(count/sum/min/max/mean)IR shape + filter atoms + AggregateNoValue sentinel + variable scoping + numeric target type 校验 + Souffle native aggregate body wire(~150 LOC)+ ProbLog `findall/3` + list predicates(~150 LOC)| Additive | 同 T2.2,**T2.3 在 T2.2 后**(filter atoms 重用 ArithExpr 校验机制) |

**依赖**:T2.1 与 T1.1 可并行;T2.2/T2.3 在 T1.2 hard-cut 落定后串行(避免 atom canonical 半状态导致 lowering 冲突)。

**Shipped 受影响 surface**:
- `src/factgraph/adapters/souffle/where_compile.py`(1137 LOC)+ `package.py`(1181 LOC)
- `src/factgraph/adapters/problog/problog_export.py`(311 LOC)
- `src/factgraph/core/rules/where_eval.py`(1135 LOC)
- `src/factgraph/core/rules/where_ast*.py`(693 LOC)

**Explicit 不在 T2 范围**:
- PyReason adapter ne / arith / agg 支持(Form 2 独立设计,parent §8.4 / C95 显式 defer)
- 字符串 / 时间 / `mod` 等 v1.x deferred kinds

---

### T3: RuleExpr 组合表达(§4)

**Scope**:parent essay §4.1-§4.11;C23-C35 + C49-C51(共 14 commitments)

**核心交付**:`RuleExpr` 作为 `&` / `|` / `.join()` / `.as_()` 组合体 + `fg.rules.inspect()` rich 表面。

**Sub-slices**:

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T3.1** | `_AndGroup` / `_OrGroup` 内部 frozen 类型 + `&` / `|` 运算符 + `RuleExpr.all/any` 工厂 + 关联性平展 | Additive | RuleExpr 内部类型不暴露(C26) |
| **T3.2** | `.as_(rule)` occurrence alias + 同表达式 alias 唯一性构造期校验 + 多次出现强制 alias 检测 | Additive | 依赖 T1.4 的 Rule 端 alias 基础设施 |
| **T3.3** | `.join(*constraints)` AND-spine reachable 构造期验证 + 10 join 规则(§3.6 锁定 / §4.6 实施)+ `.join_by_ports(*names)` 公开方法 | Additive | every-proof-path reach rule 是 §3.6 / C10 锁定;违反 raise `RuleExprError` |
| **T3.4** | `Rule.__bool__` / `RuleExpr.__bool__` raise `ExplicitBoolError`(防误用)| Additive(small)| 可与 T3.1 合并,但作为独立 sub-slice 便于在 raise message + docs 上更细致 |
| **T3.5** | `fg.rules.inspect(expr)` 返回 rich `RuleExprInspect`(`ast` / `occurrences` / `joins` / `unjoined_same_name_ports` / `render()` / `render_compact()`)+ `OccurrenceInspect` + `AtomDescriptor`(structured fields + summary)+ `PortInspect` + convenience properties | Additive | **大 surface**:可能内部再分 T3.5a (top-level inspect API) / T3.5b (descriptors detail) |

**依赖**:T1.1(新 Rule 类必须先存在)+ T1.4(alias 基础设施);**T2 不 block T3**(RuleExpr 不直接消费 atom kinds)。

**Shipped 受影响 surface**:
- `src/factgraph/sdk/store.py`(3315 LOC)`SDKStore.inspect` 当前实现(line 379)
- `src/factgraph/sdk/__init__.py` 导出 RuleExpr.all/any 工厂
- 当前 Track 1 shipped `fg.rules.inspect()` 返回 `RuleInspect`(`branches: list[Branch]`)— 是否保留 / 重新定位由 T3.5 blueprint 决定

---

### T4: Head + closed-head + projection(§5.0-§5.7)

**Scope**:parent essay §5.0-§5.7;C52-C60(共 9 commitments)

**核心交付**:`head=Rule` first-class 接口 + closed-head 判定 + `Rule.projection()` sugar + `inspect.is_closed`/`unbound_ports`。

**Sub-slices**:

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T4.1** | head 是 first-class Rule + `head=` 参数只接受 Rule 对象(不接 atom list / spec / string)| Additive | T1 完成后才能稳定实施(head IS Rule) |
| **T4.2** | head=existing Rule 身份校验:`(id, content_digest)` 双匹配;digest 失配 raise / version 失配 warn | Additive | content_digest 计算来自 T1 锁定的 `content_digest` 公式 |
| **T4.3** | head=inline Rule:`ports` keys 严格 ⊆ `expr.declared_ports` + 内部 Var 名不参与对齐(C54 封装边界)| Additive | T3 必须完成才能稳定提供 `expr.declared_ports` |
| **T4.4** | `Rule.projection(*port_names)` sugar(v1 仅同名 projection,rename v2 deferred)| Additive | small surface |
| **T4.5** | `inspect.is_closed` / `inspect.unbound_ports` 派生 utility(2-form 锁定:value-port literal OR primary-identity-field literal;复合 primary identity 全字段绑定才算 closed)+ invariant 锚点(`is_closed=True` ⇔ explain head 必通过 closed-head 校验)| Additive | 依赖 T3.5 inspect 表面 |

**依赖**:T1 + T3(完整 RuleExpr surface)

**Shipped 受影响 surface**:
- 新增 closed-head 判定逻辑:`src/factgraph/core/rules/` 新文件或 `rule_ir.py` 扩展
- `inspect` 派生 utility:T3.5 已建立 inspect surface 之上扩展

---

### T5: `.eval` namespace + Semantics wrapper(§5.8-§5.10)

**Scope**:parent essay §5.8-§5.12;C61-C78(共 18 commitments)+ §5.8.4 `why_not` PENDING

**核心交付**:`fg.eval.evaluate` / `explain` 新表面 + `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` / `Explanation` Wave 1 row-centric DTOs + per-engine Semantics wrappers + 旧 API hard-cut。

**Sub-slices**(largest Track,~10 sub-slices):

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T5.1** | `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` 5 frozen DTO + Wave 1 row-centric shape + Claim 4 kinds(`fact_triple` / `rule_head` / `aggregate_result` / `projection`)| Additive | DTO foundation,无 behavior |
| **T5.2** | `fg.eval.evaluate(expr, head=Rule, engine=..., semantics=...)` 入口 + 输出 `EvaluateResult` | Additive | DTO → 第一条 evaluate path |
| **T5.3** | `row.explain()` / `result[i].explain()` Rainbird 主路径 + `_result_resolver` non-data plumbing + `DetachedRowError` | Additive | live/detached row 双状态 |
| **T5.4** | `row.close()` advanced introspection(返回 closed Rule)| Additive | small |
| **T5.5** | `fg.eval.explain(expr, head=closed_head)` advanced manual replay + 4-state `Explanation` envelope + Wave 2 `failure_class` 5-enum + `checked_scope` / `suggested_next_steps` | Additive | Explanation envelope is large |
| **T5.6** | `PyReasonSemantics` + `PyReasonRuleParams`(`derived_bound` / `atom_bounds` / `timestep_delay`)+ `iteration_count` top-level + `temporal_projection` 3 mode(none / `fact_boundaries` / `time_binned` + ISO 8601 `bin_size` 严格化)| Additive | 改名迁移:旧 `valid_time_boundaries` → `fact_boundaries`;旧 `fixed_timesteps` mode → 拆给 `iteration_count` |
| **T5.7** | `ProbLogSemantics` + `ProbLogRuleParams`(`derived_bound`)+ `uncertainty_projection`(`{<raw_kind>: {policy}, fallback}` schema + v1 保守 reject 默认)| Additive | UI 一致性:对称 PyReason wrapper |
| **T5.8** | **T6 ProbLog adapter 三段承诺第 3 段**:ProbLog adapter 实际消费 `raw_kind + bound`(meta 字段)按 policy 投影为点概率(C76 当前未实现的部分)| Additive(adapter)| 触及 `adapters/problog/`,大约 ~100-200 LOC |
| **T5.9** | 旧 API alpha hard-cut:`fg.check`(顶层)/ `fg.diagnose`(顶层)/ `fg.eval.accept` / `fg.eval.run`(Phase 3 删除条件触发后)+ `engine_options=` / `registry=` 参数 SDK 表面删除;`fg.what_if.*` 4 shells refactor 或废弃决策 | **Subtractive(大)** | **必走 Step 4.6.5 pre-impl grep**;blast radius 大(service v1 routes / tests / quickstart docs)— 是本 Track 风险最高的 sub-slice |
| **T5.10** | `fg.eval.why_not` PENDING 解决 — explain 失败分支已覆盖时,决定是否仍保留 first-class `why_not` API,或彻底删除 | **可能 subtractive** | parent essay 显式 PENDING;需用户场景验证后才能 lock;**作为 T5 最后 sub-slice**;若 lock 是"删除"则走 Step 4.6.5 |

**依赖**:T1 + T3 + T4(完整 head + RuleExpr 表面)+ T2.1/T2.2/T2.3 完成(因为 evaluate 路径需要 atom kinds 与 ArithExpr/AggregateExpr 落地)

**Shipped 受影响 surface**:
- `src/factgraph/sdk/store.py`(3315 LOC)`SDKStore.evaluate` / `check` / `diagnose` / `why_not` / `run` / `accept` 全表面
- `src/factgraph/sdk/shells/*.py`(1381 LOC)— `check.py` / `diagnose.py` / `why_not.py` / 4 `what_if` shells
- `src/factgraph/application/protocol/*` — derivation_check / derivation_diagnose / derivation_why_not / query DTO 全量
- `src/factgraph/application/*_runtime.py` — derivation_check_runtime(744)/ diagnose_runtime(812)/ why_not_runtime(582)/ derivation_runtime(215)/ query_runtime(241)
- `src/service/` — v1 HTTP routes(单独 src 顶层目录)

**Explicit 不在 T5 范围**:
- §6 task split(`match` / `evaluate` / `prove`)三任务划分 — parent essay 显式 pending,需先在 design pillar 推进
- §9 RuleExpr × Evidence joins / alias 执行语义 — parent essay 显式 pending
- §7 evidence detail — 已迁出 `evidence-tree-rainbird-style-v1.zh.md`,独立 cadence

---

## 3. 执行顺序

### 3.1 严格依赖图

```
T1.1 (additive 新 Rule) [DONE 2026-05-22]
 │
 ├── T2.1 (atom kinds ne dispatch) ───── parallel-OK after T1.1
 │
 ├── T1.2 (legacy hard-cut, subtractive) [DONE 2026-05-22; non-eq AttrRef deferred]
 │    │
 │    ├── T2.2 (ArithExpr)
 │    │    │
 │    │    └── T2.3 (AggregateExpr)
 │    │
 │    └── T1.4 (port + alias)
 │
 ├── T1.3 (Rule naming conflict)  ◀── 可能 defer 到 T5 中段
 │
 └── (T1.4 + T2.3 完成后)
      │
      ├── T3.1 → T3.2 → T3.3 → T3.4 → T3.5
      │
      └── (T3 完成后)
           │
           ├── T4.1 → T4.2 → T4.3 → T4.4 → T4.5
           │
           └── (T4 完成后)
                │
                └── T5.1 → T5.2 → T5.3 → ... → T5.10  (strictly sequential)
```

### 3.2 并行机会

| 并行对 | 可行性 | 前提 |
|---|---|---|
| T1.1 + T2.1 | OK | T2.1 不消费 new Rule 类型;仅 IR atom kinds + adapter dispatch |
| T1.4 + T2.2(part)| 看 atom canonical 影响 | 若 T2.2 ArithExpr lowering 触碰 T1.4 alias 基础设施同源文件 → 串行 |
| T3.x 内部 sub-slices | 部分 | T3.1 必须最先;T3.2/T3.3/T3.4 之间可并行;T3.5 最后 |
| T5 任何 sub-slice 并行 | **否** | T5 strictly sequential(`.eval` API 大 surface,中段 break 会污染回滚) |

### 3.3 推荐串行最小执行序

```
1. T1.1 (additive 新 Rule)        ── DONE / archived 2026-05-22
2. T2.1 (ne adapter dispatch)     ── parallel-OK with later T1
3. T1.2 (legacy hard-cut)         ── DONE / archived 2026-05-22;non-eq AttrRef deferred
4. T1.4 (port + alias)
5. T2.2 (ArithExpr)
6. T2.3 (AggregateExpr)
7. T3.1-T3.5 (RuleExpr,内部部分并行)
8. T4.1-T4.5 (Head)
9. T5.1-T5.10 (.eval namespace,strict sequential)
10. T1.3 (Rule naming conflict)   ── 可在 T5 中段插入,因为 T5 完成时旧 API 已删,新 Rule 自然成为 canonical
```

## 4. Cross-Track 预告 Q(不开 decision 文档,本文记录)

| Q-ID | 问题 | 触发的 Track | 预答 | 何时回到正式 decision |
|---|---|---|---|---|
| **TPQ-1** | 新 Rule 类名:`RuleV2` / `kernel.application.protocol.Rule` / 直接 `Rule`(替换旧)| T1.1 | 候选 `kernel.application.protocol.Rule`(application-first per 项目固定原则)+ SDK alias `kernel.sdk.Rule` | T1.1 blueprint 必须 lock(blueprint Step 4.1 draft 阶段) |
| **TPQ-2** | T1.3 旧 Rule 命名冲突方案 A/B/C(parent §3.10 deferred) | T1.3 / T5 中段 | 倾向 A(完全替换,旧 Rule → `LegacyRule` 过渡期后删除)| T5.9 hard-cut 决定时 |
| **TPQ-3** | shipped `Branch(id=...)` 是否在新 design 下保留 | T3.5 / T5.x | parent C13 已 lock 不重命名只重新定位 | T3.5 RuleExprInspect.occurrences 设计时验证 |
| **TPQ-4** | `fg.what_if.*` 4 shells refactor 还是废弃 | T5.9 | 倾向废弃(alpha,无 transition)| T5.9 blueprint Step 4.1 |
| **TPQ-5** | `fg.eval.why_not` 是否保留 first-class API | T5.10 | parent 显式 PENDING — 用户场景验证后决定 | T5.10 blueprint Step 4.1(可能升级为正式 decision doc)|
| **TPQ-6** | §6 task split(match/evaluate/prove)是否在本轮启动 | (T5 之后,独立)| 倾向先 ship T1-T5 然后回到 design-point 推进 §6 | 本轮不解决 |

## 5. Per-sub-slice blueprint 命名约定

```
workflow/blueprints/active/2026-MM-DD_t<TrackN>-<sub>-<topic>.md
workflow/blueprints/active/2026-MM-DD_t<TrackN>-<sub>-<topic>.audit.md
```

例子:
- `2026-05-22_t1-1-rule-class-additive.md` + `.audit.md`
- `2026-05-MM_t2-1-ne-adapter-dispatch.md` + `.audit.md`
- `2026-05-MM_t5-9-eval-namespace-hard-cut.md` + `.audit.md`

archive 时 basename 不变,从 `active/` git mv 到 `archive/`。

## 6. 本文生命周期

`active/` — 5-Track 中任一 Track 仍有未 ship 的 sub-slice。

`archive/`(满足以下任一):

- 所有 5 Track 的 sub-slice 全部 `implemented` 状态归档(理想终态)
- 被新 essay 显式 supersede(后继在 Inputs 引用本文)
- 本文不锁的 cross-Track Q(TPQ-1 到 TPQ-6)有正式 decision doc 覆盖且 design-point 中无未消化要点

**约束**:本文是 working planning artifact,**不切换 Status 字段进入 `mature`** — design-point 类型本身不要求 Status 切换(per `workflow/design/README.md` §design-points 子层)。`active/archive` 目录归属是 canonical 生命周期信号。

## 7. 与 parent essay 的关系

本文 **不复制 parent essay 内容**:

- commitment(C1-C105)真源在 parent
- atom canonical / RuleExpr / head / `.eval` 语义真源在 parent
- 本文 cite parent 时用 `§<section>` + `C<N>` 双锚

如果 parent essay 更新(新 commitment / commitment 调整):

- 本文 §2 Track scope 表需重新审视 sub-slice 命中范围
- 已实施完成的 sub-slice **不回溯**(implementation 是历史固定);只在未启动的 sub-slice 范围内吸纳变化

如果 parent essay PENDING 项有进展(§6 / §9 / `why_not`):

- 优先在 parent essay 内迭代
- 新 commitment 锁定后,在本文 §2 添加新 sub-slice candidate(或新 Track)
