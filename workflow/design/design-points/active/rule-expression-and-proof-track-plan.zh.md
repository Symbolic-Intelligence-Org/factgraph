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

### 1.2 Size-class-based cadence policy(post-reflection 2026-05-23)

**Evolution rationale**:T1.1 + T1.2 + T2.1 + ProbLog hygiene 4 slice 完成后的反思暴露:

- **Lightweight 在 additive small slice 上 catch 力度足够** — 5/5 design-vs-shipped 偏差(D1-D5)全部 catch,no slip-through。
- **但 Stage 1 audit 跳过导致 slice 范围外的 commitments 未 triage** — T3 RuleExpr / T5 .eval 启动时 shipped surface 跨度太大,lightweight 不够。
- **结论**:不是 "lightweight 失败,改用 full",而是 **"按 slice size class 分配 cadence overhead"** — additive small 保持 lightweight,redesign-scale 升级到 full。

#### 1.2.1 Slice size class 定义

| Class | Sub-slice scope | Public API impact | Cross-commitment 复杂度 | 代表 |
|---|---|---|---|---|
| **S — additive 或 subtractive 小 slice** | ≤ ~300 LOC impl + tests | None / 仅 internal namespace | 单点变更,不触发 cross-commitment 决策 | T1.1 / T1.2 / T2.1 / ProbLog hygiene |
| **M — 单 load-bearing 决策 slice** | ~300-800 LOC | 单 facade entry 改名 / 命名冲突 / 单 PENDING resolve | 1-3 个 commitments 相互绑定需要 lock | T1.3 命名冲突 / T5.10 `why_not` PENDING |
| **L — redesign-scale slice** | ≥ ~800 LOC,or 跨多 sub-slice 集合 | Public API 多面改 / DTO 全套替换 | 多 commitments 同时演进,有相互冲突或依赖 | T3 RuleExpr 整体 / T4 Head / T5.1-T5.5 EvaluateResult DTO 群 / T5.9 旧 API hard-cut |

#### 1.2.2 Per-class cadence overhead

| Cadence 元素 | S(lightweight)| M(midweight)| L(full cadence)|
|---|---|---|---|
| Stage 1 audit doc(`audit/active/...vs-shipped.md`)| ✗ skip | ✗ skip | ✓ **required**(scope = 该 slice cluster commitments)|
| Stage 2 decision doc(per Q)| ✗ skip(inline in blueprint Non-goals / audit log Decision Notes)| ✓ **required**(load-bearing Q lock,即便单 Q)| ✓ required(per Q) |
| Stage 3 synthesis doc | ✗ skip | ✗ skip(blueprint §10 inline 足够)| ✓ required(post-Q reclassify + slice ordering) |
| Per-sub-slice 8-state blueprint | ✓ required | ✓ required | ✓ required |
| Per-commit verification ritual | ✓ required | ✓ required | ✓ required |
| 可以推进 mutual authorization | ✓ required | ✓ required | ✓ required |
| Sacred branch + dirty set isolation | ✓ required | ✓ required | ✓ required |
| Independent impl branch from scoped anchor | ✓ required(post T1.1 lesson)| ✓ required | ✓ required |
| Pre-impl precondition check(P2 from hygiene)| ✓ **required for boundary-sensitive slices** | ✓ required | ✓ required |
| Step 4.6.5 pre-impl grep(per Slice 6 lesson)| ✓ required for subtractive slices | ✓ required | ✓ required |

#### 1.2.3 设计严格遵照 gates(G1-G7,所有 class 不可豁免)

无论 S / M / L,以下 gates **是 design 遵照的 baseline**,lightweight 不豁免任何一项 — 这是 lightweight 模式能 catch D1-D5 全部偏差的真实机制:

- **G1 — Parent essay §-cite required**:每个 blueprint §1 Problem + §2 Goals 必须显式 cite parent essay `§<section>` + `C<N>` commitment;missing cite → Step 4.2 reviewer block scoped anchor。
- **G2 — Per Rule 1 source-grep audit before drafting**:drafter 在写 blueprint 前 read shipped 相关文件**完整**(non-snippet),per `feedback_preflight_code_audit_required` Rule 1。**Lightweight 不 skip 这一步** — 只是 audit 结果不写成单独 audit doc,而是落在 blueprint §4 Current Context + audit log Decision Notes。
- **G3 — File:line precision in §4 Current Context**:所有 cite shipped 的 file 必须带 `:line` 或 `:line-range` 精度;粗 cite → Step 4.2 reviewer P-finding。
- **G4 — Commitment ↔ slice mapping**:blueprint §2 Goals 中每条 commitment 必须可追溯到 parent essay 的 `C<N>`;无 trace 的 Goal → reviewer 提问 "这个 Goal 对应哪条 commitment?可能 scope creep"。
- **G5 — Deviation 必须 documented**:任何 shipped vs design 偏离必须 record:
  - In-blueprint refinement(scope 缩减 / form deferral)→ §3 Non-goals + §10 Outcome
  - Impl-time 偏离(precondition fail / (A-fallback))→ amendment commit + §10
  - Load-bearing 偏离 → **自动升级 S → M**,开 Stage 2 decision doc
- **G6 — Step 4.2 reviewer pass 必须 spot-check shipped source**:reviewer 在 surface P-findings 前,至少独立 verify blueprint 中**关键 commitment cite** 与实际源码 align;cite drift → P-finding,block scoped anchor。
- **G7 — Pre-impl precondition check for boundary-sensitive slices**(per ProbLog hygiene §8 step 1.5 lesson):若 blueprint §5 选定 fix boundary 依赖某个 shipped 模块的特定 import / call 行为,impl 前必须独立 verify 该行为;失败 → amend blueprint(不进 impl)。

**Lightweight 路径的可靠性 = G1-G7 + per-slice blueprint(8-state)+ Step 4.2 review + Step 4.7 reviewer pass + Step 4.6.5(if subtractive)+ G7 precondition check(if boundary-sensitive)。** Full cadence 上叠加 Stage 1 audit doc 集中 triage 是 risk-coverage 升级,但 G1-G7 是底线,任何 class 都不能豁免。

#### 1.2.4 升级 trigger conditions(refined)

Sub-slice impl 期间任一发生 → **当前 slice 升级到下一 class**(per G5 / `feedback_smaller_batch_design_blueprints`):

| Trigger | 升级方向 | 触发 artifact |
|---|---|---|
| 发现 commitment ↔ shipped 跨 ≥ 2 file 集合的 mismatch,需跨 file 协调 | S → M | open Stage 2 decision doc |
| Parent essay PENDING 项必须先决再实施(`why_not` / §6 / §9 / TPQ-2 等)| 触发 PENDING 升 M | decision doc for that PENDING |
| Sub-slice 数超 Track plan §2 预估 2 倍以上 | S/M → L | open Stage 3 mini-synthesis |
| Public API 重命名 / 替换涉及 ≥ 3 caller sites | S → M | decision doc lock 替换策略 |
| 设计 vs shipped 同时 ≥ 3 commitments 冲突 | S/M → L | Stage 1 mini-audit triage |
| Reviewer Step 4.2 spot-check 发现 cite drift > 30% | 当前 slice 暂停 | drafter re-do G2 source-grep |

#### 1.2.5 已 ship slice 的 retroactive class 归属

| Slice | Class | 归属理由 |
|---|---|---|
| T1.1 additive Rule DTO | S | additive only,internal namespace,~250 LOC,no public API |
| T1.2 DSL→bridge | S | additive + 4 行 legacy reject,~300 LOC,no public API rename |
| T2.1 ne adapter dispatch | S | adapter-only,~100 LOC,no API |
| ProbLog import cycle hygiene | S | single-boundary fix,~50 LOC,no API |
| T2.2 ArithExpr substrate | S | adapter-level ProbLog parity over shipped arithmetic builtin substrate,no new public API |
| ProbLog `meta[confidence]` fixture cleanup | S | test-only hygiene,production source 0-touch |
| T2.3a AggregateExpr substrate | S | larger substrate-only slice,public SDK/API 0-touch,SDK/adapters deferred to T2.3b/T2.3c/T2.3d |

**7 slice 的 D1-D5 偏差全部在 S class 的 G1-G7 + Step 4.2 + Step 4.7 组合下 catch**,验证 S class lightweight 模式在 small additive slice 上**力度足够**。T2.3a 进一步验证 larger-but-contained substrate slice 也可保持 S class,前提是 public SDK/API 与 adapters 明确拆出后续 slice。

#### 1.2.6 未来 slice class 预判 + cadence 升级 trigger

| Slice | 预判 class | cadence 行动项 |
|---|---|---|
| **T2.2 ArithExpr** | S — shipped `b17a62c1` | lightweight + G1-G7;ProbLog adapter parity for shipped arithmetic builtins;no div / AttrRef arithmetic |
| **T2.3a AggregateExpr substrate** | S — shipped `477fcccb` | C99-C105 substrate landed without public SDK/API or adapter wires;G7 did not trigger S→M escalation |
| **T2.3b AggregateExpr SDK ergonomic + bridge** | S → 可能 M | Adds user-facing helpers / bridge support / public docs;upgrade to M if exported naming or caller-facing API choice becomes load-bearing |
| **T2.3c/T2.3d AggregateExpr adapters** | S(each,if narrow) | Souffle aggregate body wire and ProbLog `findall/3`/list predicates;keep separate unless cross-engine semantic decision appears |
| **T1.3 SDK 顶层 Rule 命名** | **M** | TPQ-2 三选一(A/B/C)+ public API rename ≥ 3 caller sites → 必须 Stage 2 decision doc |
| **T1.4 alias / port contract** | S | scope 已收窄 |
| **T3 RuleExpr 组合** | **L** | C23-C35 + C49-C51 + C58 + C59 = **18 commitments/seams**;Stage 1 audit + 5 Stage 2 decisions complete;Stage 3 synthesis splits T3.1-T3.6 + later execution tranche |
| **T4 Head + closed-head** | **L**(可能与 T3 合并 L cluster)| C52-C60 = 9 commitments,与 T3 紧耦合 |
| **T5.1-T5.5 EvaluateResult DTO 群** | **L** | C61-C67 = 7 commitments 同步 ship;最大 redesign 区,**先跑 Stage 1 audit triage shipped `SDKStore.evaluate/check/diagnose/why_not/run` vs Wave 1 row-centric model** |
| **T5.6-T5.7 Semantics wrappers** | M(each)| per-engine wrapper 单点 lock,decision doc per wrapper |
| **T5.8 T6 ProbLog raw_kind/bound 投影** | S | adapter-level |
| **T5.9 旧 API hard-cut** | **L** | subtractive 大 scope,Stage 1 audit triage caller blast radius |
| **T5.10 `fg.eval.why_not` PENDING resolve** | **M** | TPQ-5 lock,decision doc |

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
| **T2.1** | **Implemented + archived 2026-05-22**(`575d48d7` impl / `1ca39726` archive):9 IR atom kinds 名单 + ir_arity + tuple shape 文档化 + Souffle `ne` dispatch + ProbLog `ne` dispatch(term inequality `\=`)| Additive(adapter)| 完成 |
| **T2.2** | **Implemented + archived 2026-05-23**(`04ac0cb9` impl / `b17a62c1` archive):ProbLog dispatch for existing arithmetic builtins `add` / `sub` / `neg` / `addc` / `mulc` via `is/2`;SDK bridge tests prove existing `BinaryExpr` lower path;**no div / AttrRef arithmetic / float literals** | Additive(adapter parity)| 完成 |
| **T2.3a** | **Implemented + archived 2026-05-23**(`b94576f5` impl / `477fcccb` archive):Core `AggregateAtom` substrate + validation + Python eval + `AggregateNoValue` + application Rule serialization/var collection;**SDK ergonomic / bridge / public docs / adapters deferred** | Additive(substrate-only)| 完成;large S-class validated |
| **T2.3b** | AggregateExpr SDK ergonomic helpers + DSL bridge aggregate passthrough + public docs/export policy | Additive(public SDK surface)| Next T2 follow-up;may upgrade to M if helper naming/export policy becomes load-bearing |
| **T2.3c/T2.3d** | Souffle native aggregate body wire + ProbLog `findall/3` + list predicates | Additive(adapter)| Keep engine slices separate unless cross-engine semantic coupling appears |

**依赖**:T2.1 与 T1.1 可并行;T2.2/T2.3a 在 T1.2 hard-cut 落定后串行完成。T2.3b depends on T2.3a substrate + T1.2 bridge;T2.3c/T2.3d depend on T2.3a substrate and can run independently from T1.4.

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

**Scope**:parent essay §4.1-§4.11 + §5.9-§5.10 seams;C23-C35 + C49-C51 + C58 + C59(共 18 commitments/seams)

**核心交付**:`RuleExpr` 作为 `&` / `|` / `.join()` / `.as_()` 组合体 + `fg.rules.inspect()` rich 表面。

**Sub-slices**:

| ID | 范围 | 性质 | 备注 |
|---|---|---|---|
| **T3.1** | Base RuleExpr value + bool guards:`RuleExpr` / `RuleExprError` / `ExplicitBoolError` SDK exports;internal `_RuleExpr` / `_AndGroup` / `_OrGroup`;`&` / `|`;`RuleExpr.all/any`;AND/OR flattening;immutability;join-free equality/hash;application Rule + RuleExpr operands;legacy SDK Rule rejection;`RuleExpr.__bool__` + application `Rule.__bool__` raise;**must not** change legacy SDK `Rule.__bool__`;**must not** introduce direct `application_rule == rule_expr` cross-type equality | Additive(public SDK surface + application Rule method) | D1/D4/D5 governed;RuleExpr internals not public(C26);T3.1 blueprint must cite synthesis negative-action gates |
| **T3.2** | Expression-scope occurrence validation only:alias uniqueness within RuleExpr;repeated same Rule requires explicit aliases;default alias behavior when Rule appears once;diagnostics for duplicate aliases/repeated unaliased Rules | Additive | Scope narrowed: T1.4 already shipped `.as_`, `RuleOccurrence`, `RulePortRef`, and alias regex validation |
| **T3.3** | `.join(...)` over AND groups + `RulePortRef.eq(...) -> RuleJoinConstraint` + Every-Proof-Path Reach Rule + self-join semantics + join constraint symmetry / duplicate normalization | Additive | D2 locks `.eq(...)` as initial syntax;D4 locks structural equality/hash;`.join_by_ports` excluded unless synthesis re-scopes |
| **T3.4** | `.join_by_ports(*names)` explicit-name expansion + missing/fewer-than-two/ambiguous diagnostics | Additive | C58;separate slice per D2/D5,uses T3.3 join mechanics |
| **T3.5** | `fg.rules.inspect(application_rule|rule_expr)` rich `RuleExprInspect`;legacy SDK Rule / Inference dict inspect preserved;minimum fields + render helpers;may split into T3.5a core inspect and T3.5b C49/C50/C51/C59 rich descriptors / ports if preflight shows scope risk | Additive | D3 governed;must preserve current legacy inspect dict behavior |
| **T3.6** | Docs + examples for staged import path,`.eq(...)` joins,`&` / `|` precedence and parentheses,bool guards,same-name ports no auto-join,inspect return-shape differences | Additive(docs) | Added by Stage 3 synthesis;track plan formerly stopped at T3.5 |
| **T3 later Stage 1-3** | RuleExpr execution lowering decision ladder:Stage 1 audit `2026-05-25_t3-later-execution-vs-shipped.md` + D6-D10 reviewed + Stage 3 synthesis `2026-05-25_post-q-t3-later-execution-synthesis.md` | L cluster | Resolves D5 §4.8 deferral after T3.1-T3.6 archive;blueprint ladder split into T3L.1-T3L.3 |
| **T3L.1** | Internal RuleExpr lowering core + native execution:private `RuleExprLoweringPlan`,C35 app Rule coercion,D7 branch model,D8 equality atom joins,D10 trace sidecar,native branch-list materialization | Additive(private lowering + native path) | No public SDK dispatch yet;no public result DTO;preemptive locks from D6-D10 |
| **T3L.2** | Adapter matrix parity:Souffle + ProbLog branch-list/equality/aggregate preservation within shipped grammar;internal PyReason pred-only classifier + non-pred rejection classification | Additive(adapter parity) | No adapter grammar upgrades;preserve T2.3 aggregate semantics;PyReason Form 2 remains deferred |
| **T3L.3** | Public SDK dispatch + diagnostics + docs:`fg.eval.evaluate(application_rule|rule_expr, head=...)`,D9 `SDKStoreError` preflight message contract,public success `list[CandidateSet]`,user-facing docs | Additive(public SDK behavior + docs) | No `CandidateSet`/`EvidenceEnvelope` shape change;no `EvaluateResult`;full T4/T5 remains deferred |

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
| **T4 Stage 1-3** | Head + closed-head decision ladder:Stage 1 audit `2026-05-25_t4-head-closed-head-vs-shipped.md` + D11-D15 reviewed + Stage 3 synthesis `2026-05-25_post-q-t4-head-closed-head-synthesis.md` | L cluster | Resolves C52-C60+C72 after T3 later archive;implementation ladder split into T4.1-T4.3 |
| **T4.1** | Head identity + declared-port foundation:D11 existing-head id/digest/version warning;D12 private branch-total declared-port helper;head port namespace validation;shared `RuleExprError` buckets | Additive(private validation + public error/warning behavior) | No external-head body concat yet;no projection sugar;no closed-head inspect;preserve T3L.3 public success `list[CandidateSet]` |
| **T4.2** | External + projection head execution:D13 external head body branch-wise concat + head-port link atoms;D14 `Rule.projection(*port_names)` same-name sugar + private recognizable projection-head shape | Additive(public head behavior + private materialization) | No rename syntax;no public projection DTO;adapter grammar unchanged;projection placeholder atoms never materialize |
| **T4.3** | Closed-head validator + inspect utilities:D15 strict C72 v1 closedness;`inspect.is_closed`/`unbound_ports`;private reusable validator;docs for head/projection/closed-head behavior | Additive(inspect surface + docs) | No `EvaluateResult`, `row.close()`, `fg.eval.explain`, Explanation, or WhyNot;T5 owns evidence/result surfaces |

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
5. T2.2 (ArithExpr)               ── DONE / archived 2026-05-23
6. T2.3a (Aggregate substrate)     ── DONE / archived 2026-05-23
7. T2.3b/c/d (Aggregate SDK + adapters) ── follow-up;split per public API / engine scope
8. T1.4 (port + alias)
9. T3.1-T3.5 (RuleExpr,内部部分并行)
10. T4.1-T4.5 (Head)
11. T5.1-T5.10 (.eval namespace,strict sequential)
12. T1.3 (Rule naming conflict)   ── 可在 T5 中段插入,因为 T5 完成时旧 API 已删,新 Rule 自然成为 canonical
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
