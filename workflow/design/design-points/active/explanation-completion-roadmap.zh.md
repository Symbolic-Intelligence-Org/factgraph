# 用户面 Explanation Completion Roadmap

> **本文件状态**: draft (2026-05-28); 战略综合; 待 review / 多 session 修订
>
> **权威边界 (per `workflow/design/design-points/README.md`)**:
>
> 一个 design-point 是**候选设计 / 非权威参考**。它仅当被以下任一引用时才成为约束:
>
> - 一个 `workflow/design/decisions/` 中 adopted 的 decision,或
> - 一个 `workflow/blueprints/archive/` 中 implemented 的 blueprint,或
> - 当前模块 docs (`src/factgraph/*/docs/`),或
> - `workflow/foundations/architecture_principles.md`
>
> design-point **不能直接覆盖 shipped 行为**。实现必须通过下游消费链 (decision → blueprint → impl) 到达代码。

---

## 0. Inputs

| 来源 | 继承内容 |
|---|---|
| `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md` §14.1-§14.6 | deferred registry D1, D5, D6, D7, D11, D15, D18, D20 (primary essay supersede via README rule) |
| `workflow/design/design-points/archive/match-api-design.zh.md` | D20 witness API 形态边界 (`as_assertions()` / `.witnesses()` / `.to_view()`); AND+OR runtime shipped via module docs |
| `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` | §3.14 RuleExpr v1 deferred (8 项) + T3-later D6-D10 / T4 D11-D15 proposed ADR 状态 inheritance — 见 §10 legacy |
| `workflow/design/design-points/archive/database-view-fg-layered-architecture.zh.md` | §17 DB/view deferred (10 项) + Q1/Q2/Q4/Q5/Q6 `proposed for user review` ADR 状态 — 见 §11 legacy |
| `workflow/design/design-points/archive/post-t5-completion-roadmap.zh.md` | §7.3 Open Questions + T9/T11/T12/N6 未结 tracks — 见 §12 legacy |
| `workflow/blueprints/archive/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.md` | PyReason row evidence deferred-state 已被显式教学 (T8-D round 5 用户面契约) |
| `workflow/blueprints/archive/2026-05-28_adapter-module-docs-alignment.md` | Adapter module docs 与 shipped semantics + T8-D round 5 boundary 同步 |

注: 上面 5 个 `design-points/archive/` 路径在本文件 commit 时仍存于 `design-points/active/`. 本 cleanup cycle 后续 commit 通过 `git mv` 将其移到 `archive/`. 路径是 post-archive 状态的前向引用.

---

## 1. 目的与定位

把分散在 `evidence-tree-rainbird-style-v1.zh.md §14` 的 deferred items **收敛为完整 user-facing explainability stack**.

### 1.1 当前已 ship 的 explainability surface

- T8-A 14-key metadata + `run_id` envelope-only
- T8-B-1 native Form 1 + T8-B-2 Souffle Form 1
- T8-C-1 ProbLog row provenance graphs (`PROBLOG_PROVENANCE_KIND` / `EDGE_DERIVES` / `engine_meta["problog"]`)
- T10-1 ProbLog C76 `uncertainty_projection` (default reject + 4 point policies + interval reject)
- T10-2-A/2-B/3-A/3-B PyReason canonical semantics (C74/C77/C78)
- T8-D rounds 1-5 user quickstart 闭合
- Adapter module docs aligned

### 1.2 剩余 explainability gaps (5 维)

| 维度 | 当前状态 | 用户感知缺口 |
|---|---|---|
| **PyReason row evidence** | safe single-conclusion fallback | rich timeline (timestep / bound update) 未 ship |
| **Why-not** | failed `Explanation` envelope only | 无 path-level reasoning / 无 counterfactual |
| **Match witness** | `fg.entities.match(...)` returns snapshot only | 无 assertion ids / witness ids / view 创建 |
| **Attribution** | 无 | salience / impact decomposition 全缺 |
| **Aggregate visibility** | aggregate 只给 `count`, kinds 锁定 | 无 contributors 展开 / `any` / `all` / `isSubset` / `join` / 等扩展 |

本文件**收敛**这 5 维的设计入口, **不写**完整 schema, 留作未来多 cycle 的 design source.

---

## 2. 优先级 Tier 分类

按 **用户面价值 × 架构 unblock 力 × 实施成本** 三轴评估.

### 🥇 Tier S — 战略锚 (最高优先级)

| Item | 价值理由 | Unblocks |
|---|---|---|
| **D11 PyReason Form 2 evidence** | 已被多次明示为上游 blocker; timeline 基底 (`pyreason_trace_to_evidence_graph`) 已 ship; LAYOUT_TIMELINE 已定义 | T8-C-2 PyReason runtime evidence bridge |
| **D5 Why-not / counterfactual** | 用户最高频解释诉求 "为什么没推出"; 当前 v1 用户面感知最弱 | D1 公开后的实际语义价值 |
| **D20 Match witness output** | 用户 demand 多次; `fg.entities.match(...).as_assertions() / .witnesses() / .to_view()`; T11.2.7 明示 deferred | match → evidence/database/view 桥 |

### 🥈 Tier A — 高价值 / 自然伴随 Tier S

| Item | 价值理由 |
|---|---|
| **D1 fg.diagnose SDK 公开** | 内部已 shipped; SDK 面薄壳; 是 D5 / D2/D3/D4 的对外入口 |
| **D6 Salience carrier** | 跨 condition 权重; 也是 D7 attribution 的底层 |
| **D7 Impact decomposition (Shapley)** | 上层 attribution UI; 依赖 D6 |
| **D15 AggregateExpr 扩展** (`any` / `all` / `isSubset` / `join` / `first` / `last` / `sort` / `group_by`) | 直接扩展用户可写表达能力 |
| **D18 Aggregate matched_facts 展开** | 当前只给 `count`; 展开 contributors 是高频 demand |

### 🥉 Tier B — 中价值 / 防御性 / 正交完善

| Item | 价值理由 |
|---|---|
| D14 compound_comparison 完整 schema | RuleExpr 完整性补口; v1 envelope 已能用 |
| D16 ArithExpr operators (`%` / `**` / 位运算 / 字符串拼接) | 表达能力, 低 demand |
| D17 Overflow/NaN protection | 数值正确性; 等用户撞到 |
| D19 Aggregate target implicit cast | 类型转换便利性 |
| **D2 / D3 / D4** (top-down regression / SAT why-provenance / atom-complete probing) | **作为 D5 的 implementation hints, 不独立** |
| D12 Eager / Lazy switching | 性能优化; evidence > 10MB 触发 |

### ❌ Tier Z — 不重要 / 没价值做 / 明示拒绝

| Item | 拒绝理由 |
|---|---|
| **D8 session log channel** | **架构反向** — 当前 sessionless v1 是明示设计; D8 会回退到 Rainbird `/interactions/` 模型 |
| **D9 LLM NL explain** | 纯 cosmetic; renderer 已 deterministic; LLM 引入 prompt/version/audit 复杂性远超价值 |
| **D10 per-fact ACL** | 仅 multi-tenant 服务部署需要; 当前 local DTO; 等真有 multi-tenant 用例再激活 |
| **D13 Nemo backend opt-in** | 独立 engine path, 0 用户 demand; 与主线无关 |

### 不上设计链, 是 governance hygiene

- **rule-expression T3-later D6-D10 + T4 D11-D15 proposed**: 工作可能已 ship, 仅 status 滞后 — 不是新设计, 是 ADR 状态规范化
- **roadmap T9 / T11 / T12 / N6**: 各自独立 track, 与 explanation 主线无关
- **4 untracked ledger 设计文档**: 独立战略方向 (Claim-first append-only ledger), 完全不属本设计链

---

## 3. Design Chain (设计链路)

```
                ┌─────────────────────────────────────────────┐
                │  USER-FACING SURFACE                        │
                │  ┌─────────────────┐  ┌─────────────────┐  │
                │  │ D1 fg.diagnose  │  │ D20 match       │  │
                │  │ SDK shell       │  │ witness output  │  │
                │  └────────┬────────┘  └────────┬────────┘  │
                │           │                    │           │
                │  ┌────────▼────────────────────▼────────┐  │
                │  │  D5 Why-not / counterfactual        │  │
                │  │  (D2/D3/D4 作为 impl strategies)    │  │
                │  └──────────────────┬───────────────────┘  │
                └─────────────────────┼──────────────────────┘
                                      │
                ┌─────────────────────▼──────────────────────┐
                │  ATTRIBUTION                               │
                │  ┌──────────────┐    ┌──────────────────┐  │
                │  │ D6 Salience  │───▶│ D7 Impact decomp │  │
                │  │ carrier      │    │ (Shapley)        │  │
                │  └──────────────┘    └──────────────────┘  │
                └────────────────────────────────────────────┘
                                      │
                ┌─────────────────────▼──────────────────────┐
                │  EXPRESSION LAYER                          │
                │  ┌──────────────┐    ┌──────────────────┐  │
                │  │ D15 Aggregate│    │ D18 Aggregate    │  │
                │  │ extensions   │    │ matched_facts    │  │
                │  └──────────────┘    └──────────────────┘  │
                └────────────────────────────────────────────┘
                                      │
                ┌─────────────────────▼──────────────────────┐
                │  ENGINE / EVIDENCE INFRASTRUCTURE          │
                │  ┌────────────────────────────────────┐    │
                │  │ D11 PyReason Form 2 evidence       │    │
                │  │ (LAYOUT_TIMELINE / EDGE_DERIVES /  │    │
                │  │  EDGE_UPDATES / component identity)│    │
                │  └────────────────────────────────────┘    │
                └────────────────────────────────────────────┘
```

### 3.1 链路 reading

**自下而上 (实施依赖)**:
- D11 Form 2 evidence schema **先锁定** (timestep / bound update / LAYOUT_TIMELINE 等)
- 上面 D15/D18 (aggregate 扩展) 与 D11 并行 (表达层独立)
- D6 salience carrier 引入 (与 raw_kind/bound 并列的 quantitative carrier)
- D7 Shapley impact 在 D6 + 主 EvidenceGraph 上构建
- D5 Why-not 在 EvidenceGraph + diagnose 内部能力上构建
- D1 SDK 公开 (薄壳, 在内部 diagnose 稳定后做)
- D20 match witness 桥 (与 D11/D18 关联到 EvidenceRef 节点 identity)

**自上而下 (用户感知)**:
- 用户面 `fg.diagnose(...)` + `match(...).as_assertions()` + Why-not narrative
- 中层 attribution (这是多少, 各 condition 占多少)
- 表达层 aggregate 展开 (这个 count 是由哪些 contributors 来的)
- 底层 timeline / state update (PyReason 在哪个 timestep 完成的)

---

## 4. Inheritance Map

| §14 deferred item | 继承到 sub-design |
|---|---|
| §14.1 D1 | §6.2 Failure semantics (SDK 入口) |
| §14.1 D2 / D3 / D4 | §6.2 Failure semantics (implementation strategies, **不独立**) |
| §14.1 D5 | §6.2 Failure semantics (主入口) |
| §14.2 D6 | §6.3 Attribution (carrier) |
| §14.2 D7 | §6.3 Attribution (decomposition) |
| §14.4 D15 | §6.4 Aggregate completeness (kinds 扩展) |
| §14.4 D18 | §6.4 Aggregate completeness (contributors 展开) |
| §14.5 D11 | §6.1 Engine evidence richening |
| §14.6 D20 | §6.5 Match witness seam |

---

## 5. 明示 Rejection (Tier Z, 不进设计链)

| §14 item | 拒绝理由 (永久或长期) |
|---|---|
| D8 session log channel | 与 sessionless v1 架构矛盾 (per `evidence-tree-rainbird-style-v1.zh.md §1.1 v1 定位`) |
| D9 LLM NL explain | renderer 已 deterministic; LLM 引入 cost 与 audit trail 复杂性 |
| D10 per-fact ACL | 仅 multi-tenant 才有意义; 当前架构无此需求 |
| D13 Nemo backend | 独立 engine path; 0 demand |

**注**: 上面 4 项**保留在 evidence-tree §14 的 deferred registry**, 仅在本设计链中明示不消费. 未来用户场景出现可再激活.

---

## 6. Sub-Design 大纲 (待填实)

### 6.1 Engine evidence richening — D11 PyReason Form 2

**Scope**: PyReason row-level temporal evidence 桥接到 canonical `EvaluateRow.explain().evidence`

**Source-back 现状**:
- `pyreason_trace_to_evidence_graph(...)` shipped at `src/factgraph/adapters/pyreason/provenance.py:113-119`
- `LAYOUT_TIMELINE` / `EDGE_UPDATES` / `EDGE_DERIVES` 已在 EvidenceGraph DTO 定义
- 协议 gate `_validate_row_provenance_envelopes` 当前仅接 ProbLog (`src/factgraph/application/protocol/evaluate_result.py:1221-1240`)

**6 个未锁设计问题**:
1. timestep 语义 (PyReason iteration round vs internal fixpoint step)
2. time_window 语义 (Form 2 evidence 怎么 windowing)
3. bound update 跨 timestep state mutation contract
4. component identity (rule_id / atom_id) 跨 timestep dedup 策略
5. LAYOUT_TIMELINE producer/consumer contract
6. EDGE_DERIVES vs EDGE_UPDATES 语义区分

**下游 blueprint candidate**:
- `t8-c-2-pyreason-evidence-enrichment-runtime` (gated on 上述 6 问题)
- 协议 gate 放开接受 PyReason envelope
- 新增 `_build_pyreason_provenance_row_evidence_graph(...)` 对称 ProbLog

### 6.2 Failure semantics — D5 + D1 (+ D2/D3/D4 as impl strategies)

**Scope**: 用户面 "为什么没推出" 完整能力

**Layer 划分**:
- **D5 (语义层)**: failed graph / why-not / counterfactual 各自的 user-facing contract
- **D1 (接口层)**: `fg.diagnose(...)` SDK 公开 — 当前 application-layer 内部已 shipped, 仅 SDK 薄壳缺失
- **D2/D3/D4 (实现策略)**:
  - D2: top-down goal-regression (Bourhis-Lutz-Krötzsch 2024 / Elhalawati 2022)
  - D3: SAT-based why-provenance (minimal hitting set; research-grade)
  - D4: atom-complete eager probing (cost-aware)

**未锁设计问题**:
- Why-not 是否构造 failed EvidenceGraph, 还是只给 failure path narrative
- counterfactual 的 universe model (which alternative facts to consider)
- diagnose 的 cost / short-circuit policy

### 6.3 Attribution — D6 + D7

**Scope**: 引入 quantitative attribution 能力 (与 ProbLog probability / PyReason bound 平行)

**D6 Salience carrier**:
- 语义: condition 权重 (Rainbird `salience` 等价)
- 形态: `meta["salience"]` + adapter 是否消费
- 与 raw_kind/bound 的边界: salience **不是** uncertainty carrier; 是 weight
- 未锁: salience source / normalization / digest impact

**D7 Impact decomposition (Shapley)**:
- 语义: 每个 condition 对最终 derivation 的贡献 %
- 算法: Shapley value / weighted sum
- 输出形态: `quantitative_explanation.decomposition` field
- 未锁: cost policy (Shapley 计算成本指数), 与 D6 salience 的耦合

### 6.4 Aggregate completeness — D15 + D18

**D15 AggregateExpr 扩展 kinds**:
- 候选 kinds: `any` / `all` / `isSubset` / `join` / `first` / `last` / `sort` / `group_by`
- 锁定路径: 表达式 grammar + lowering + evidence reason + tests **同步扩展**
- 适配器影响: 各 engine 是否能 lower 每个 kind

**D18 Aggregate matched_facts 展开**:
- 当前: `contributors {mode, count, handle}` 已锁; `mode="omitted_v1"` 默认
- 未锁: handle format (lazy / embedded), view scoping, size policy
- 与 D20 关联: matched_facts 可作为 match witness 的特化

### 6.5 Match witness seam — D20

**Scope**: `fg.entities.match(...).as_assertions() / .witnesses() / .to_view()` API family

**v1 boundary** (T11.2.7 已明示):
- 当前 match 仅返 snapshot; 无 witness ids; 无 view 创建

**未锁设计问题** (per evidence-tree §14.6):
- EvidenceGraph node identity 与 EvidenceRef / assertion ids 的对齐
- view scoping (multi-attached Database 时哪个 view)
- API exact shape (Rule 与 Cross-entity tuple 输出形态)
- 与 D18 matched_facts 的关系 (witness 是否就是 contributors 的展开形式)

---

## 7. Out of Inheritance

明示**不在**本设计链, 但相关:

| 项 | 关系 |
|---|---|
| evidence-tree §14.4 D14 / D16 / D17 / D19 | "RuleExpr 完整性"独立子设计 (可未来另起) |
| evidence-tree §14.5 D12 | 性能优化, 与本链正交 (eager/lazy switching) |
| evidence-tree §1-§13 (Phase B Form 1 设计 / structural commitments) | evidence-tree v1 的 shipped 实现基础, 与本设计链上下游而非并列 |
| `match-api-design.zh.md` AND+OR runtime | shipped, 不在本设计 scope |
| `rule-expression-and-proof-attempt.zh.md` 全部 | Rule/RuleExpr/closed-head 设计源, 与 explanation completion 正交 |
| `post-t5-completion-roadmap.zh.md` T9/T11/T12/N6 | 独立 track |
| 4 untracked ledger design-points | 独立战略方向 (Claim-first append-only ledger) |
| Tier Z 项 (D8/D9/D10/D13) | 明示拒绝 (见 §5) |

---

## 8. Next Blueprint Candidates (按推荐优先级)

| 序 | 候选 | 依赖 | Class hint |
|---|---|---|---|
| 1 | **D11 PyReason Form 2 evidence schema design** | 无 (本设计链战略起点) | M (设计 + 多轮) |
| 2 | D11 → T8-C-2 PyReason evidence runtime | D11 schema 锁后 | L (runtime, 500-1000+ LOC) |
| 3 | D20 match witness API design | EvidenceGraph node identity 锁 (与 D11 协同) | M (设计 + 实施) |
| 4 | D1 fg.diagnose SDK shell | 内部 diagnose 已 ship | S (薄壳) |
| 5 | D5 + D2/D3/D4 Why-not 实现策略选型 | D1 shell 后 | M (策略选型 + impl) |
| 6 | D6 salience carrier 设计 | 独立 | M |
| 7 | D7 Shapley impact decomposition | D6 后 | M (含 cost policy) |
| 8 | D15 AggregateExpr 扩展 kinds | RuleExpr grammar review | M (grammar + impl) |
| 9 | D18 Aggregate matched_facts 展开 | D15 协同; view scoping | M |

---

## 9. Open Questions (待 review / 多 session 修订)

| ID | Question |
|---|---|
| Q1 | D11 Form 2 schema 是否应在独立 design-point 里详写, 还是留在本文件 §6.1? |
| Q2 | D2/D3/D4 是否完全收编为 D5 的 implementation hints, 还是各保留独立 D-id 在 evidence-tree §14.1? |
| Q3 | D7 Shapley 与 D6 salience 的 carrier 边界 — 是同一 carrier 还是两个独立 lane? |
| Q4 | D20 与 D18 matched_facts 的关系 — witness 是否 = contributors 的 lazy 展开? |
| Q5 | Tier Z 项 (D8/D9/D10/D13) 是否需要写专门 "rejection rationale" 文件, 还是本文件 §5 已足够? |
| Q6 | "RuleExpr 完整性" (§14.4 D14/D16/D17/D19) 是否值得独立 design-point, 还是直接 governance hygiene 关闭? |
| Q7 | 本 design-point 与 `evidence-tree-rainbird-style-v1.zh.md` 的关系: supersede §14 / 仅 inherit / 平行存在? |

---

## 10. Legacy backlog: RuleExpr v1 deferred items

> **本段状态**: 从 archived 设计文档继承的 backlog visibility. 本文件**不持有** active design ownership of these items; original SHIPPED design rationale (C1-C48 commitments) 见 archived 源文件. 任何 reactivation 需独立 cycle.
>
> **来源**:
> - `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §3.14
> - `workflow/design/decisions/active/2026-05-25_t3-later-d{6..10}-*.md` (T3-later D6-D10 `proposed` status)
> - `workflow/design/decisions/active/2026-05-25_t4-d{11..15}-*.md` (T4 D11-D15 `proposed` status)

### 10.1 §3.14 deferred 8 项

| 项目 | 触发条件 (blueprint 入口) |
|---|---|
| desc `private_vars` (renderable 但不可 join 的内部变量) | 出现明确"私有 desc 变量"需求 |
| atom-level desc | rule-level desc + 自动 atom narrative 不够用 |
| SavedRule / NamedRuleExpr | 跨进程共享 / UI 构造复合表达式需求 |
| Rule 命名冲突方案 (A/B/C) | new Rule 引入实际 API 时 |
| 现行 `Branch(id=...)` 类的最终归宿 | new Rule 替代现行 Rule 完成时 |
| `atom_id` 升级到 content-hash (v1 是 positional) | `Rule.atoms` 顺序稳定性出问题时 |
| 跨 entity multi-head | "一个 entity 推一组 fact + 另一 entity 也推 fact" 实际诉求 (v1b 只支持同 entity 多 field) |
| `join_by(...)` sugar | 用户社区反复出现 chain join 便利性诉求 |

### 10.2 T3-later D6-D10 + T4 D11-D15 ADR 状态

10 个 ADR 仍为 `proposed` 状态. 工作实现可能已 ship (T3-T5 全 complete, 见 archived `rule-expression-and-proof-track-plan.zh.md`). Status 升级到 `adopted` 需独立 governance hygiene cycle:

- T3-later D6 public entrypoint head dependency
- T3-later D7 lowering plan shape
- T3-later D8 join lowering semantics
- T3-later D9 adapter matrix
- T3-later D10 evaluation result evidence boundary (note: RuleExpr provenance **不进** EvidenceGraph; 与本文件 explanation 链反向)
- T4 D11 scope head identity boundary (note: 与 evidence-tree §14.5 D11 同名但**不同概念**, 见 §5 Caveat 注)
- T4 D12 declared port namespace
- T4 D13 external head body semantics
- T4 D14 rule projection sugar
- T4 D15 closed head inspect

---

## 11. Legacy backlog: Database/View deferred items

> **本段状态**: 从 archived 设计文档继承的 backlog visibility. 本文件**不持有** active design ownership of these items; original SHIPPED design rationale (A1-A20 commitments) 见 archived 源文件. 任何 reactivation 需独立 cycle.
>
> **来源**:
> - `workflow/design/design-points/archive/database-view-fg-layered-architecture.zh.md` §17
> - `workflow/design/design-points/archive/database-view-fg-layered-architecture.zh.md` Q1/Q2/Q4/Q5/Q6 (`proposed for user review`)
> - `workflow/design/design-points/archive/post-t5-completion-roadmap.zh.md` §6.3 (与 §17 部分 dedupe, 此处合并列出)

### 11.1 §17 + #2 §6.3 dedupe 后 deferred 项

| 项 | 触发条件 |
|---|---|
| persistent named views in Database | 跨 session view registry 需求 |
| branch / tag / refs | long-lived alternative heads 需求 |
| writable sub-fg | fork / merge / write-back 语义单独落定 |
| assertion retract / update | deletion / correction semantics 需求 |
| schema migration tx | schema 演进需求明确 |
| materialized derived views | derived fact lifecycle 明确 |
| remote database | 本地 database semantics 稳定 |
| multi-db join | 单 db snapshot + view scope 稳定后 |
| Rule persistence / SavedRule | rule registry / deployment governance 需求 |
| view set algebra API | Python set op 成为高频痛点 |
| method-level `view=` consumer (from #2 §6.3) | per-call view scoping 需求 |
| T11.1 schema class order canonicalization (from #2 §6.3) | repeated 用户 schema digest 困惑 |

### 11.2 Q1/Q2/Q4/Q5/Q6 `proposed for user review` 状态

5 个 db-view Qs 在 `workflow/design/decisions/active/2026-05-20_q{1,2,4,5,6}-*.md` 仍为 `proposed for user review` (非标准 README 4-state). Status 规范化需独立 governance cycle:

- Q1 Database Class Boundary
- Q2 FactGraph attach Lifecycle
- Q4 FrozenAssertionView Shape
- Q5 View Scope vs Revocation Composition
- Q6 Registry-In-Workspace Migration

### 11.3 与新文件 explanation 链的接缝 (view scoping cross-ref)

D18 (aggregate matched_facts 展开) 与 D20 (match witness output) 的 view scoping / handle format 引用上面 view 设计 (尤其 method-level `view=` 与 persistent named views). 本文件主链 §6.3 / §6.4 / §6.5 不重新定义 view API; 当任一 Tier S/A trigger 激活时, 应同时 reactivate 上面相关 view backlog 项. 详见 archived `database-view-fg-layered-architecture.zh.md` §14 "Evidence / Evaluate metadata 接缝".

---

## 12. Legacy backlog: Post-T5 roadmap residuals

> **本段状态**: 从 archived 设计文档继承的 scheduling backlog. 本文件**不接管** roadmap tracking ownership; original T6-T12 planning rationale 见 archived 源文件. 任何 reactivation 需独立 cycle.
>
> **来源**:
> - `workflow/design/design-points/archive/post-t5-completion-roadmap.zh.md` §7.3 Open Questions / Decision Gates
> - `workflow/design/design-points/archive/post-t5-completion-roadmap.zh.md` T9 / T11 / T12 / N6 未结 tracks
>
> **注**:
> - 原 §6.1 Parent Rule/Eval Deferred **已 obsoleted**: C74/C76/C77/C78 本 session 全 shipped via T10-1 / T10-2-A / T10-2-B / T10-3-A / T10-3-B; `fg.eval.why_not` 收编 §6.2 D5 (Tier S); `fg.eval.run` 已 deleted.
> - 原 §6.2 Evidence Deferred Items mirrors archived `evidence-tree-rainbird-style-v1.zh.md` §14, 已通过 §0 Inputs 继承.
> - 原 §6.3 Database/View Deferred Items 已合并到本文件 §11.

### 12.1 Roadmap §7.3 Open Questions

| Question | Default | Decision gate |
|---|---|---|
| Is T6 required before v0.2.0? | No | if release claims full evidence tree |
| Is T10 required before v0.2.0? | No | if release claims ProbLog/PyReason semantic execution beyond carrier-only wrappers (本 session: T10 已全 shipped) |
| Does T11.2 need code changes? | Unknown | Step 4.6 inventory of S1-S6 / I10-A10 shipped metadata |
| Should dirty baseline be triaged before release branch? | Yes | before T11.3 release machinery |
| Should `rule-expression-and-proof-track-plan.zh.md` archive now? | likely after minimal T12 | **本 cycle 直接 archive** (per supersede rule) |

### 12.2 未结 T-tracks

| Track | Status | Note |
|---|---|---|
| T9 docs / product boundary release alignment | future | 依赖 shipped behavior; 当 release claim 改变时起 blueprint |
| T11 DB/view release track | partial | Slice 1-7C shipped per project memory; cross-doc S1-S6 / I10-A10 unblock 仍 deferred (见 §11 DB/view legacy) |
| T12 Lifecycle / Design Housekeeping | future | governance debt cleanup track (含 §10 / §11 backlog 的 reactivation 决策) |
| N6 notebook namespace cleanup | future | dirty baseline `4 M` 中 3 notebook 文件处理 |

### 12.3 Lifecycle archive 自我说明

本 cleanup cycle (commits 实际落地 2026-05-29 早晨, session 起始 2026-05-28) 通过 supersede 规则一次性 archive 6 个 design-points 到 `workflow/design/design-points/archive/`:

| # | File | Supersede 路径 |
|---|---|---|
| 1 | `match-api-design.zh.md` | 本文件 §0 Inputs 引用 + D20 witness 收编 (§4 / §6.5) |
| 2 | `post-t5-completion-roadmap.zh.md` | 本文件 §12 legacy |
| 3 | `rule-expression-and-proof-attempt.zh.md` | 本文件 §10 legacy + Inputs 引用 |
| 4 | `rule-expression-and-proof-track-plan.zh.md` | README 自标 superseded by post-t5 (已成 archive chain) |
| 5 | `database-view-fg-layered-architecture.zh.md` | 本文件 §11 legacy + Inputs 引用 |
| 6 | `evidence-tree-rainbird-style-v1.zh.md` | 本文件 §0/§4/§5 主 supersede 路径 |

archive 后 `design-points/active/` 仅余本文件作为 tracked 唯一 design-point + 3 untracked ledger 设计文档 (`append-only-ledger-evaluation.zh.md` / `identity-mechanism-redesign.zh.md` / `ledger-schema-specification.zh.md`).

---

## 13. Status & Lifecycle

- **Status**: draft (2026-05-28); **non-authoritative reference** until adoption
- **Created during**: 2026-05-28 session, 在 14 个 cycle (T10 + T8-C-1 + T8-D rounds 3-5 + adapter docs alignment) push 完成后
- **Trigger**: user-directed strategic synthesis, 收敛 evidence-tree §14 deferred registry 中 8 个高价值项 + 同 cycle 通过 supersede 规则 archive 6 个老 design-points
- **Out of scope for this draft**: 完整 schema 细节, 任何 runtime / docs / blueprint 同步动作
- **Next expected**: user review, 然后 D11 schema cycle 作为最高优先级 strategic 起点

### 13.1 修订记录

| 日期 | 变更 |
|---|---|
| 2026-05-28 (初版) | §1-§9 explanation completion 主体创建 (session 内 Write 时刻) |
| 2026-05-29 (legacy 扩展 + 6-file archive batch) | §0 Inputs 扩展至 5 个 archive 源; 新增 §10/§11/§12 legacy backlog 段; §10/§11 → §13/§14; 同 cycle 通过 supersede 规则一次性 archive 6 design-points (commits `00eb28b5` / `27d49586` / `fc90eefe`) |
| 2026-05-29 (cross-ref cleanup) | 修复 archived 6 design-points 在 `docs/official/` / `workflow/audit/active/` / `workflow/design/decisions/active/` 中的 active→archive path 引用 (post-archive cross-reference hygiene); 同时精修本文件 + README 中的 commit-time date precision |

---

## 14. Open Tickets to Track

| Ticket | Owner | Trigger |
|---|---|---|
| memory/current.md Recommended Next Work 是否升级 D11/Form 2 + 引用本文件 | next cycle | 本文件 reviewed |
| design-points/README.md "当前 active design-points" 是否加本文件 + 删 6 个 archived | **本 cleanup cycle commit 3** | 即时 |
| §10 legacy 10 个 proposed ADR 是否独立 governance cycle 关闭 | future | 用户 demand |
| §11 legacy 5 个 db-view Q 是否独立 governance cycle 关闭 | future | DB/view release alignment 触发 |
| §12 未结 T9/T11/T12/N6 tracks 是否独立 future cycle | future | release claim 改变 / housekeeping demand |
| 4 untracked ledger 设计文档 (`append-only-ledger-evaluation` / `identity-mechanism-redesign` / `ledger-schema-specification` / `identity-and-data-model-redesign` 已 in archive) 的 intake 决策 | future | 独立战略 session |

---

*End of explanation-completion-roadmap.zh.md draft.*
