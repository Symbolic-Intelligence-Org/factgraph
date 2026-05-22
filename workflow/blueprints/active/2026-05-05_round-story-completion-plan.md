# Round Story Completion Plan(总控蓝图)

- Status: implemented
- Created: 2026-05-05
- Last Updated: 2026-05-06
- Scope: master plan,governs Batch 0..8 + 5a/5b/5c sub-batches
- Related Modules: ALL(meta)
- Related Docs:
  - `docs/architecture_principles.md`
  - `docs/references/working/rule-replay-line-redesign-input/README.md`
  - `docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md`
  - `docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md`
  - `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md`
  - `docs/blueprints/archive/2026-05-{03,04,05}_*.md`(5 capability + frontier + demo blueprints)
- Audit Log: [2026-05-05_round-story-completion-plan.audit.md](./2026-05-05_round-story-completion-plan.audit.md)

---

## 1. Problem

5 application capability(Check / Diagnose / Fact Overlay Check / Why-not Universe Diagnose)+ 1 evaluator-layer capability(Frontier Trace)已 shipped + archived,但用户层无法跑通**一个 coherent round story**:

- 没有统一的 scenario container —— Fact Overlay 是孤立的 single-action,无 multi-action overlay
- 没有 application-first 的 rule-side ops —— rule disable / replace / add-condition 在 reset 前 SDK substrate 里有,reset 后未重启
- 没有 explanation —— overlay 改 fact / rule 后,旧 proof path 是失效还是被替代,用户看不清
- 没有 durable round persistence —— audit package 是 snapshot,不是 round event log
- ergonomic 不齐 —— SDK 与 service 仍未暴露这些能力,demo 直调 application/core
- history 工具缺 —— L4 per-frame diff、L5 cross-run aggregation 未做

围绕"完成 round story"的剩余设计内容若无总控 plan,每批易复刻 v0.1.4 abandoned 时的 scope 漂移问题。本蓝图冻结路线、暂缓项、批次 entry/exit 与分支策略,**不写实现细节**;每批仍要 Step 0 + 各自蓝图。

## 2. Goals

- **冻结**剩余至 round-story-closure 的 9 大批 + 3 子批顺序 / 范围 / entry-exit。
- **冻结**暂缓项(本计划不做的设计内容),后续每批不再争论。
- **冻结** Batch 0 inventory 规则与未提交文件处置策略。
- **冻结**分支策略(何时新开 branch / 命名 / off 何处)。
- **不冻结**:批内具体实现 / DTO 字段细节 / 算法 / 测试矩阵 ——— 这些由各批自身蓝图 + Step 0 闭环决定。

## 3. Non-goals(本计划暂缓的设计内容)

| 项 | 暂缓理由 |
|---|---|
| **L7 cross-engine evidence translation** | 触动 souffle/problog/pyreason adapter evidence schema,与 round story 主线正交;无新引擎 trigger 不开 |
| **L9 Interactive UI / SPA tree visualization** | 独立 frontend product line,与 application protocol 正交 |
| **L10 Sidecar annotation system** | 无 product 需求 trigger |
| **L11 Mutable evidence tree** | 设计 reserved 至 v2.0,non-target |
| **§6.7 Declarative engine capability schema** | working hypothesis 仍 hold,trigger 未 fire |
| **新引擎 onboarding(§3.5)** | 等真新 engine 落地推动 |
| **新 substrate 在 `kernel.sdk`** | per `project_application_first_runtime_authority.md` hard constraint |
| **Direction D unified status vocabulary** | Post-routemap design-intent audit found the upstream 10-status unification proposal was not shipped. The routed decision is per-capability status enums plus localized narrative/diff surfaces. Reactivate only if a concrete cross-capability consumer requires one status vocabulary rather than per-capability DTO interpretation. |
| **Direction F shared condition identity / `shared_id` library resolution** | `ConditionModule.shared_id` exists as authoring metadata but the routemap did not ship producer / consumer / runtime resolution semantics. Reactivate with a separate blueprint if shared library condition reuse becomes product-critical. |
| **Broader L6 lazy why-not carrier / near-miss tracking** | Batch 2 shipped a narrow finite-universe Why-not capability. The broader lazy carrier / near-miss board concept remains deferred until a caller needs lazy candidate generation or UI-level near-miss exploration. |
| **Minimal cause identification for status flips** | ProofFrame atom verdicts provide inputs, but no shipped capability selects the minimal single condition / action responsible for a status change. Reactivate only with a concrete causal-analysis consumer. |
| **L5 cross-run aggregation as first-class master-plan deferred item** | Batch 7 explicitly deferred L5 aggregation because persisted events do not provide stable `module_id` grouping. Keep the reactivation trigger here as the master-plan-level reference: concrete module mapping + cross-run consumer, or a fresh first-slice aggregation scope that does not require module identity. |

任意 trigger 出现(eg. 用户实际需要 cross-engine evidence 统一 view),可单独开新蓝图;**本 plan 不预留 batch 槽位**。

## 4. Current Context

### 4.1 Shipped portfolio(2026-05-05 post)

| Capability | 层 | 实现位置 | Anchor |
|---|---|---|---|
| Check | application | `kernel.application.derivation_check_runtime` | `project_check_operation_shipped.md` |
| Diagnose | application | `kernel.application.diagnose_runtime` | `project_diagnose_operation_shipped.md` |
| Fact Overlay Check | application | `kernel.application.fact_overlay_runtime` | `project_fact_overlay_operation_shipped.md` |
| Why-not Universe Diagnose | application | `kernel.application.why_not_runtime` | `project_why_not_universe_diagnose_shipped.md` |
| Evaluator Frontier Trace | evaluator(substrate) | `kernel.core.rules.frontier` | `project_evaluator_frontier_trace_shipped.md` |

测试:1080+ kernel tests OK,5 个 capability + 1 demo blueprint 全 archived。

### 4.2 Hard constraints 不变

- **Application-first**:每新 capability DTO + pure function in `kernel.application/`;`kernel.sdk` 无 substrate
- **Q1 Sibling discipline**:capability 之间不互相 import 实现;protocol DTO 各自 owned
- **No ledger write from read paths**:本 plan 任何批次输出仍受此约束
- **Release branch invariants**:`v0.1-oss-prep` / `master` 无 explicit publish 决议不动

### 4.3 §6.6 working hypothesis 仍 hold

跨 3 application capability + 1 evaluator-layer capability 验证下,per-capability local engine gate 仍 readable;§6.7 declarative schema 未触发。本 plan 各批不预设破坏此 hypothesis。

## 5. Batch Catalog

### 5.0 Batch 0 — Branch State Freeze(0.5 session)

**目标:** 清点 demo branch 当前未提交内容,决定每个文件归宿,把工作树还原到只剩预期 lightweight sync 的状态。

**Entry criteria:**
- 本计划已 commit(本蓝图 + audit 进 `docs/blueprints/active/`)
- 工作树存在以下未追踪/已修改文件需处置:
  ```
  M examples/README.md
  M memory/current.md
  ?? examples/11_capabilities_e2e_demo.ipynb
  ?? examples/12_rule_replay_demo.ipynb
  ?? tutorials/
  ```

**Exit criteria:**
- `examples/11_capabilities_e2e_demo.ipynb` + `examples/README.md` 修改 commit(纳入 round-story 核心叙事)
- `examples/12_rule_replay_demo.ipynb` 先 inspect 当前内容,再**删除或迁出 examples/**(详 §8 inventory 规则)
- `tutorials/` 处置:或 commit 进 round-story 设计区,或显式标 design-only 留 worktree;decision 写进 audit
- `memory/current.md` 不 commit(沿用 lightweight sync 约定)
- `git status --short` 仅剩 `M memory/current.md` 与本计划 audit 增量

### 5.1 Batch 1 — Canonical Round Story(1 session)

**目标:** 让"5 个问题"成为稳定叙事,统一所有 user-facing 入口。

**5 个问题(canonical):**
1. *Does this binding pass?*(Check)
2. *Where does this failing binding fail?*(Diagnose)
3. *What if this fact were different?*(Fact Overlay Check)
4. *Given a finite candidate universe, who passes / who fails / why?*(Why-not Universe Diagnose)
5. *In native evaluation, where does the where-body collapse?*(Evaluator Frontier Trace)

**Entry criteria:**
- Batch 0 闭环
- 工作树干净

**Exit criteria:**
- `examples/11_capabilities_e2e_demo.{py,ipynb}` 一致呈现 5 问题
- `examples/README.md` 准确指向 ipynb 与 .py(smoke)分工
- `tutorials/evidence-pipeline.cn.md` 中 §1 / §7 / §8 narrative 与 5 问题表述一致(不增内容,只对齐文字)
- 新增 `tutorials/capability-decision-tree.cn.md` 或类似(简短文档,何时用 Check vs Diagnose vs Fact Overlay vs Why-not vs Frontier)
- `python -m unittest src.kernel.tests.test_examples_capabilities_demo` 仍过

### 5.2 Batch 2 — Capability Ergonomics(1-2 sessions)

**目标:** 不改语义,只降低使用门槛。

**范围内:**
- application-layer helper / normalizer:
  - Fact Overlay field override helper(从 entity ref + field path + new value 自动构造 `FactValueOverride`)
  - Why-not universe builder(从 entity 集合 + plan head var spec 自动构造 `candidate_universe`)
  - Frontier store-projection wrapper(把 `Store` 转成 `evaluate_native_where_frontier(...)` 期望的 `view_facts`)
- 这些 helper 全在 `kernel.application/` 内(per-capability 私有 module 或 `kernel.application._helpers`)

**范围外(明确禁):**
- ❌ SDK shell 任何 `SDKStore.{check, diagnose, fact_overlay, why_not}` ——— 推到 Batch 8
- ❌ 任何修改 capability protocol DTO 字段 / status enum
- ❌ 在 `kernel.sdk/` 加 substrate
- ❌ 改 capability runtime 算法

**Entry criteria:** Batch 1 闭环
**Exit criteria:**
- 3 类 helper shipped + 测试覆盖
- 各 capability 现有 tests 全过(无回归)
- 新写 1-2 个示例展示 helper 用法

### 5.3 Batch 3 — EvaluationOverlay + Fact Scenario Core(2-4 sessions)

**目标:** 从 Fact Overlay 单 action 推广为 multi-fact-action `EvaluationOverlay` container。

**范围内:**
- 设计 generic `EvaluationOverlay` DTO
- 实现 fact-side 三类 action:`replace` / `add` / `remove`
- Fact Overlay Check 通过 deprecation/compat path 接到新 container(原 `FactValueOverride` API 保留期或迁移)
- 不改 capability boundary(仍 native-only,仍不写 ledger,仍不 cache contamination)

**范围外(明确禁):**
- ❌ rule ops(disable / replace / add condition)—— 在 Batch 5
- ❌ overlay 跨 engine 行为变更
- ❌ overlay 持久化(audit JSONL)—— 在 Batch 6

**Entry criteria:** Batch 2 闭环
**Exit criteria:**
- `EvaluationOverlay` 协议 DTO 冻结(Step 0.D)
- Fact Overlay Check 兼容新 container(测试覆盖 migration path)
- §7-EvaluationOverlay-* drift gates inventory

### 5.4 Batch 4 — ProofFrame Rechecker(narrow)(3-5 sessions)

**目标:** 解释"旧 proof path 在 overlay 下是否仍成立 / 失效 / 被替代",**前置于 rule ops**。

**Narrow scope(关键边界,与 L4/L5/L8 区分):**
- **Input**:既有 `SupportArtifact`(Check 输出的 native evidence)+ `EvaluationOverlay`(Batch 3 输出)
- **First target**:native + fact-overlay path only
- **Output**:per-frame structured validity,statuses 限定为:
  - `still_valid` —— 旧 frame 在 overlay 下仍成立
  - `invalidated` —— 旧 frame 在 overlay 下失效
  - `unknown` —— 无足够 evidence 判断
  - `superseded_by_full_eval` —— 单 frame 检验不足,需 full re-eval
- **Statuses are ProofFrame-local**,**不动**已有 capability 的 status enum
- **Narrative renderer**:deterministic text rendering 消费上述 4 status,跨 capability 文字标准化

**范围外(明确禁):**
- ❌ unify Check / Diagnose / Fact Overlay / Why-not status enums(reframe 已确认:不该统一)
- ❌ L4 per-frame proof tree diff(在 Batch 7)
- ❌ L5 cross-run module aggregation(在 Batch 7)
- ❌ L8 audit JSONL persistence(在 Batch 6)
- ❌ cross-engine ProofFrame(L7 territory,non-target)

**Entry criteria:** Batch 3 闭环;`EvaluationOverlay` DTO 冻结
**Exit criteria:**
- `ProofFrameRecheckRequest / Result` DTO 冻结
- Narrow recheck algorithm 实现(native + fact-overlay path)
- Narrative renderer shipped + 多 capability narrative test
- §7-ProofFrame-* drift gates inventory

### 5.5 Batch 5 — Rule-Side Operations(总 5-8 sessions,split 三子批)

**总目标:** application-first 重新实现 rule-side overlay actions。继承 Batch 3 `EvaluationOverlay` container,扩展 rule action 类。

**总约束(贯穿 5a/5b/5c):**
- ❌ 不复活旧 SDK replay substrate
- ❌ 任何新 capability substrate 起步在 `kernel.application.protocol/` + `kernel.application/<runtime>.py`
- 所有 rule action runtime 必须输出 ProofFrame status(让 Batch 4 narrative 消费)
- v0.1.4 abandoned 教训:**真正的 trap 是 semantic decomposition**,不是 layer。Step 0 必须显式答 DTO 是否 crisp;不 crisp 即 abandon

#### 5.5a Rule Disable(1-2 sessions)

**目标:** application-first 重启 v0.1.3 disable-condition(rollup branch 上仍有完整 SDK substrate impl)。

**Entry criteria:** Batch 4 闭环
**Exit criteria:**
- `RuleDisable` action DTO 冻结(归入 `EvaluationOverlay`)
- Native overlay impl(不复用 v0.1.3 SDK code,仅借鉴 disable 语义)
- ProofFrame 输出"disabled atom causes which frame invalidated"
- §7-RuleDisable-* drift gates;不 sneak SDK substrate

#### 5.5b Rule Condition Replace(Step 0 + 决策)(2-3 sessions)

**目标:** Step 0 spike 决定 replace 是 ship 还是 abandon。

**Step 0 三选一**(必须显式 commit one):
- **Option A — Literal-only ship**:narrow `ReplaceConditionRequest(locator, new_literal)`;不碰 condition_weights / adapter param。Implementation 在 Step 0 后启动
- **Option B — Abandon**(同 v0.1.4):写 abandonment audit;decomposition 显形,确认无单一 crisp DTO;close 5b 不实施
- **Option C — 三 DTO 拆分**:literal replace / condition_weights override / adapter-specific param 各自独立 capability。implementation 量比 A 大 3x

**默认倾向**(per project owner directive):先问 DTO 是否 crisp;不 crisp 即 Option B abandon,**不硬做泛化 `param_override`**

**Entry criteria:** Batch 5a 闭环
**Exit criteria(三 path 之一):**
- Path A:literal-only impl shipped + 测试 + ProofFrame 集成
- Path B:abandonment audit recorded;blueprint close as abandoned;转 Batch 5c
- Path C:3 个独立 capability shipped(各自走 archive 流程)

#### 5.5c Add Condition + Binding Planner(2-3 sessions)

**目标:** Direction G 新 capability,在已有 rule body 添新条件 + 推断变量绑定。无 v0.1.x prior art。

**Entry criteria:** Batch 5b 闭环(无论 5b 走哪 path)
**Exit criteria:**
- `AddConditionRequest` 协议 DTO 冻结
- Binding planner contract 冻结(变量 scoping / shadowing 边界)
- ProofFrame 输出"new condition adds → previous frames superseded_by_full_eval"
- §7-AddCondition-* drift gates

### 5.6 Batch 6 — Durable Round Persistence(3-5 sessions)

**目标:** L8 capability-event JSONL audit trail,可从 audit package 读回 round。

**范围内:**
- capability-event JSONL schema(Check / Diagnose / Fact Overlay / Why-not / Frontier 输出 + ProofFrame status)
- audit package 序列化 + reload 一个 round
- 与现有 `AuditQuery` / `load_audit_package` 兼容

**范围外:**
- ❌ L4 per-frame diff(Batch 7)
- ❌ L5 cross-run aggregation(Batch 7)

**Entry criteria:** Batch 5c 闭环
**Exit criteria:**
- JSONL schema 冻结
- Round 序列化/反序列化双向通过 round-trip test
- AuditQuery 兼容新 event log

### 5.7 Batch 7 — Evidence Diff / Cross-Run(3-5 sessions)

**目标:** L4 per-frame proof tree diff + L5 cross-run module aggregation。**消费 Batch 4 ProofFrame 与 Batch 6 persistence**。

**Entry criteria:** Batch 6 闭环;ProofFrame schema 仍稳定
**Exit criteria:**
- per-frame diff 算法 shipped
- cross-run aggregation index shipped(per `module_id` 或等价 stable identity)
- 历史比较 demo 可跑

### 5.8 Batch 8 — Public Surface Decision(2-4 sessions)

**目标:** 全部 application protocol 已稳定,正式决议 SDK / service / release projection。

**范围内:**
- SDK shell 设计 + 5 capability 方法(`sdk.check / diagnose / fact_overlay / why_not` 等)
- service HTTP routes(若需要)
- release projection allowlist 更新
- README baseline

**Entry criteria:** Batch 7 闭环;application protocol 稳定无 breaking change
**Exit criteria:**
- SDK shell shipped + 测试
- public API surface freeze
- release-day checklist updated(不触发 publish,publish 仍需 explicit 决议)

## 6. Inter-batch Dependencies

```
Batch 0 (cleanup)
    ↓
Batch 1 (canonical narrative)
    ↓
Batch 2 (ergonomic helpers)
    ↓
Batch 3 (EvaluationOverlay fact-only)
    ↓
Batch 4 (ProofFrame narrow)  ←── 关键 pivot:rule ops 之前必须有
    ↓
Batch 5a (rule disable)
    ↓
Batch 5b (rule replace,Step 0 三选一)
    ↓
Batch 5c (add condition)
    ↓
Batch 6 (round persistence)
    ↓
Batch 7 (evidence diff cross-run)
    ↓
Batch 8 (public surface)
```

**严格顺序原因:**
- Batch 4 ProofFrame **必须**早于 Batch 5(rule ops 的解释力依赖 ProofFrame)
- Batch 5a → 5b → 5c 顺序固定:disable 最简单,replace 需 Step 0 决策,add-condition 复杂度最高
- Batch 6 persistence **必须**在 Batch 7 之前(diff/aggregation 消费持久化数据)
- Batch 8 在最末:application protocol 稳定后才暴露 public

**并行可能(非默认):**
- Batch 6 与 Batch 5c 部分内容可并行(不同 owner / 不同分支),但不推荐 first pass
- Batch 7 L4 与 L5 内部可并行

## 7. Branching Strategy

### 7.1 总原则

- **每批(或子批)新开 branch**,off 上一批 final state
- Branch 命名:`v0.1-<batch-handle>-2026-MM-DD`
- 各批自身蓝图(Step 0.A → 0.D + impl)在该 branch 上 commit
- 闭批(close-out)时 archive 蓝图;branch push origin 作 reference,**不 merge 入 release base**(per release branch invariant)

### 7.2 推荐 branch 列表

| Batch | Branch 名 | Off | 备注 |
|---|---|---|---|
| 本 master plan | `v0.1-round-story-plan-2026-05-05` | `v0.1-capabilities-e2e-demo-2026-05-05` @ `1ec314c` 之前 stable | master plan 自身的 branch |
| Batch 0 | (复用 master plan branch 或 demo branch)| 同上 | inventory 工作量小,可在 master plan branch 一起做 |
| Batch 1 | `v0.1-canonical-round-story-2026-MM-DD` | Batch 0 final | docs-heavy,可能与 0 合并一 branch |
| Batch 2 | `v0.1-capability-ergonomics-2026-MM-DD` | Batch 1 final | |
| Batch 3 | `v0.1-evaluation-overlay-2026-MM-DD` | Batch 2 final | |
| Batch 4 | `v0.1-proofframe-rechecker-2026-MM-DD` | Batch 3 final | |
| Batch 5a | `v0.1-rule-disable-2026-MM-DD` | Batch 4 final | |
| Batch 5b | `v0.1-rule-replace-step0-2026-MM-DD` | Batch 5a final | step0 后缀:abandonment 概率非零 |
| Batch 5c | `v0.1-add-condition-2026-MM-DD` | Batch 5b final | |
| Batch 6 | `v0.1-round-persistence-2026-MM-DD` | Batch 5c final | |
| Batch 7 | `v0.1-evidence-diff-2026-MM-DD` | Batch 6 final | |
| Batch 8 | `v0.1-public-surface-2026-MM-DD` | Batch 7 final | |

### 7.3 何时**不**新开 branch

- Batch 0 inventory 工作量极小,可在 master plan branch 上一起做(不强制独立 branch)
- 子批(5a/5b/5c)虽是独立 branch,但 5b abandonment path 不需要单独 ship,branch 仅 archive blueprint 即可

### 7.4 何时**必须**新开 branch

- 任何引入新 application protocol DTO 的批
- 任何引入新 runtime module 的批
- Batch 4 / 5a / 5b / 5c / 6 / 7 / 8 全 mandatory 新 branch

### 7.5 不动的 branch

- `v0.1-oss-prep` @ `f5ade36` —— release base,无 explicit publish 决议不动
- `master` —— 同上
- `v0.1-redesign-2026-05-03` @ `422ffcf` —— frozen reference

## 8. Batch 0 Inventory Rules

未提交文件处置规则(per Agent X 调研结论):

| 文件 | 决议 | 理由 |
|---|---|---|
| `examples/README.md` | **commit** 进 Batch 0 | 反映 11_capabilities ipynb 新增 |
| `examples/11_capabilities_e2e_demo.ipynb` | **commit** 进 Batch 0 | round-story 核心叙事承载,与 .py smoke target 并列 |
| `examples/12_rule_replay_demo.ipynb` | **先 inspect,再删除 OR 移 `docs/references/working/<sub>/`** | 引用 reset 前 SDK substrate(`kernel.sdk.CandidateDiff` 等),留 `examples/` 误导 reader。Batch 0 必须先确认是否含有可迁移 design note;**默认删除**;若保留历史则移到 references/ 下并显式标 "pre-reset design probe, not runnable on current API" |
| `tutorials/evidence-pipeline.cn.md` | **commit 进 Batch 0**(临时设计区) | 用户写过的临时参考。不入工作流 docs/,留 tutorials/ 即可 |
| `tutorials/` 目录其他文件(若有)| 同 evidence-pipeline 处置 | |
| `memory/current.md` | **不 commit**(继续 lightweight sync 约定)| 操作日志,git 历史不承载 |

**Batch 0 commit message 范例(若 inspect 后选择删除 12_rule_replay notebook):**

```
chore(repo): batch 0 inventory + round story canonical artifacts

- examples/11_capabilities_e2e_demo.ipynb: notebook form of demo
- examples/README.md: update entry to point at ipynb + .py
- tutorials/evidence-pipeline.cn.md: temporary reference doc
- examples/12_rule_replay_demo.ipynb: remove (refs reset substrate)
```

## 9. Suspension / Abandonment Protocol

### 9.1 任意批可以 suspend

- 任一批的任一 sub-step,若发现 scope 不清 / 设计 trap / 真实需求不存在,**显式 suspend** 而非硬推
- Suspension 必须 record 在该批 audit log + 本 master plan audit log
- 工作树留 clean checkpoint;branch push origin 作 reference

### 9.2 任意批可以 abandon

- 该批 Step 0 spike 发现 DTO not crisp / 设计 not fit / 需求 already covered → **valid abandonment**
- Per `project_application_first_runtime_authority.md`:abandon 是有效 Step 0 输出
- Abandonment audit 记 blocker 精确形式;后续不重启**除非 trigger 显式 fire**

### 9.3 Abandonment 不级联 default

- 一批 abandon 不强制后续批同时 abandon
- 唯一例外:依赖前批输出的批(eg. Batch 5a 依赖 Batch 4 ProofFrame 输出)abandon 时,后批应在 Step 0.A 重审 entry criteria
- Default:每批独立判断

## 10. Outcome / Deviations

Round story routemap closed on 2026-05-06 at Batch 8 close commit `6b32972`.

### 10.1 Final status

| Item | Result |
|---|---|
| Major batches | 9/9 complete:Batch 0 / 1 / 2 / 3 / 4 / 5 / 6 / 7 / 8 |
| Batch 5 sub-batches | 3/3 complete:5a Rule Disable / 5b Rule Condition Replace / 5c Add Condition |
| Archived deliverables | 12 archived blueprints |
| Post-archive hardening | Batch 4 / 5a / 6 / 7,plus tri-batch 5a/5b/5c RuleRef scan hardening |
| Final public-surface decision | Batch 8 chose a Path-B-equivalent closure:no SDK shell,service route,release projection,or allowlist expansion |

### 10.2 Closure semantics

The routemap is complete under the scoped meaning of "round story completion":all committed batches were either shipped or narrowed through recorded Step 0 decisions,and all non-shipped items are explicit deferred scope with reactivation conditions. This does **not** mean every upstream design idea from the rule replay redesign notes was implemented.

The canonical user story is now covered by application-first and audit-layer surfaces:

- five canonical questions are documented and backed by shipped application/evaluator capabilities;
- EvaluationOverlay fact replacement/removal,ProofFrame recheck,and the three first-slice rule actions are implemented in application-owned modules;
- durable round events and L4 ProofFrame diff are implemented in `kernel.audit`;
- the public boundary is documented as `kernel.sdk` product public,with `kernel.application` and `kernel.audit` advanced importable.

### 10.3 Intentional narrowing / deviations

| Area | Closure decision |
|---|---|
| Fact-side `add` | Deferred in Batch 3 because policy semantics were not crisp in Step 0. |
| `superseded_by_full_eval` | Collapsed in Batch 4;ProofFrame status remains `still_valid | invalidated | unknown`. |
| Rule replace | Narrowed in Batch 5b to Const-to-Const literal replacement. |
| Add condition / binding planner | Narrowed in Batch 5c to filter-only add condition;real binding planner deferred. |
| L5 cross-run aggregation | Deferred in Batch 7;module identity is not available from persisted first-slice fields. |
| Public SDK/service expansion | Deferred in Batch 8;current decision is docs/checklist-only public boundary. |

### 10.4 Post-routemap design-intent audit notes

A post-closure design-intent audit compared the shipped routemap against `docs/references/working/rule-replay-line-redesign-input/`. It found no blocker to the current closure claim,but it identified follow-up documentation / hardening candidates now recorded in §3:

- Direction D unified status vocabulary was not shipped;per-capability status enums are the actual design.
- Direction F shared condition identity is not shipped beyond existing authoring metadata.
- The broader L6 lazy why-not carrier / near-miss board is deferred beyond the finite-universe Why-not capability.
- Minimal cause identification is not owned by any shipped capability.
- L5 aggregation reactivation belongs in this master-plan deferred catalog,not only in the Batch 7 archive.

### 10.5 Archive notes

The individual batch blueprints remain the implementation truth for their scoped decisions. This master plan remains in `docs/blueprints/active/` as the routemap close-out reference because it is the cross-batch index and deferred-scope catalog for future sessions.
