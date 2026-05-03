# Check Operation: Conceptual + Interaction Design

- **Status:** resolved (conceptual + interaction; protocol contract still belongs to blueprint Step 0)
- **Authority:** source-of-truth for Check operation conceptual + interaction design until cited by blueprint
- **Created:** 2026-05-03
- **关联 baseline section:** `70_codebase-baseline-2026-05-03.md` §P0-1 + §P0-2 + §P0-3
- **关联 design input:**
  - `40_design-discussion-A-with-decision-1.md` 的 A 段(round 1+2 + 锁定 shape)
  - `00_brainstorm-original.md` 命题 4("要支持 boolean check 一个具体 binding 是否符合规则")
  - `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Check"
- **关联 blueprint:** 暂无(blueprint 在本 doc 进入 `resolved` 后由 `docs/blueprints/active/` 起)
- **形态:** 这是一个 resolved conceptual / interaction reference。§1-§5 是当前决议;§6 是历史 discussion trace。若 §6 早期 iteration 与 §1-§5 冲突,以 §1-§5 为准。**不写任何具体 file/class 命名**(那是 blueprint 阶段)。本 doc 足以启动 draft blueprint,但 scoped implementation 前仍需在 blueprint Step 0 冻结 protocol contract。

---

## 0. Why this topic exists

Baseline P0-3 揭示:Check 是 P0 三个 capability 中最 ready-to-go 的 — core primitives(`_branch_satisfies` / `_atom_satisfies` / `_ground_terms`)已存在,evaluate / check 是 8-atom mirror,application 层可以薄包装现有能力。注意:这不等于 direct-primitive-only;partial binding 与 non-native engine 仍需按 §1.3 / §3.5 的 enumerate/evaluate-then-match 路径处理。

起草时 application DTO 形态 — 输入是什么、输出是什么、status 词汇怎么定 — **完全 open**。本 doc 现在记录这些问题的 resolved conceptual / interaction 决议,供后续 blueprint 直接 cite。

本 doc 的任务:把"Check 概念上是什么 / 消费者怎么交互"讨论到 `resolved` 状态,让 blueprint 可以直接 cite。

---

## 1. 概念定义

> **必须先回答这层,否则 §2 交互定义没法定。**

### 1.1 核心问题

Check 在 B'' framing("rule operable + evidence read-only")的位置是什么?

### 1.2 候选 framing(待选 / 待补充)

按 baseline §P0-2 列出的 "evaluate variant" 边界,4 个 candidate:

| Framing | 定义 | 与现有代码的连接 | 与 B'' invariant 的连接 |
|---|---|---|---|
| **A. evaluate 的 variant** | Check 是 evaluate 的"single-binding 模式";在 existing evaluate request 上表达 selected binding | 走 evaluate 全流程,加 binding-filter | rule 仍 operable;但会把 check 语义混进 evaluate request,可能违反 reset 后 application-first / no-hidden-overlay 约束 |
| **B. evaluate 的后处理** | Check 输入 `list[CandidateSet]`(已 evaluate 过),问"我感兴趣的 binding 是否在里面" | 不调 evaluate primitives;只 query candidate set | 完全不动 evaluate;evidence 仍 read-only |
| **C. evaluate 的旁路** | Check 跳过 evaluate_store,直接调 `_branch_satisfies` primitives,不产 candidates | 复用 `find_winning_branch_index` / `_branch_satisfies` / `_atom_satisfies` | 不通过 candidate 通道;evidence-bearing(可选 SupportArtifact)仍 read-only |
| **D. 新顶层动作** | Check 与 evaluate 平级,独立 capability | 自成 substrate | 与 B'' 完全平行 |

### 1.3 决议

**Check 是 evaluate 的 verify-given 对偶** — evaluate 给定规则问"哪些 binding 满足?",Check 给定 binding 问"这一个满足吗?"。两者按同一套 8 类 atom 语义,方向相反(enumerate-side vs verify-side)。

接受两类 binding 输入(per Discussion §6.4):
- **complete binding:** 验证一个完整结果是否满足规则
- **partial binding:** 验证是否存在某个完整结果扩展用户给的部分绑定 — 实现是完整 evaluate body → final bindings → subset match;**不是** initial-env injection(违反 baseline §3.2 invariant 的那种 envs=[user_binding] 起步),**不是**局部重算

implementation strategy 按引擎 + binding 完整度选(归 §3.5):
- native complete binding:可用 `_branch_satisfies` primitives 直接验证
- native partial binding:**必须**先枚举完整 final bindings,再 subset-match;选定 primary full binding 后,用该 full binding 构造 evidence。**禁止**直接把用户 partial binding 传给 `_branch_satisfies`,否则缺失变量会被 `_ground_terms` 当 false,造成 silent wrong `failed`
- souffle / problog / pyreason:走 evaluate-then-match,用户 binding 与产出 candidates / engine payload 可表达的 binding subset-match

**与 B'' invariant("rule operable + evidence read-only")的具体连接:**
- rule operable:Check 不修改 rule;rule body 是 lowered WhereIR(只读)
- candidate read-only:Check 不提交 candidate;non-native 路径下若依赖 evaluate-then-match 的 candidate,也是 evaluation-derived read-only 视图
- evidence read-only:Check 不提交 facts / candidates / assertions;可以且应为本次 Check 生成 derived SupportArtifact / EvidenceEnvelope。这里的 "read-only" 约束是"不改变系统事实或候选状态",不是"禁止构造本次结果的 evidence view"

**Source:** Discussion §6.1(scenario)+ §6.2(framing 修正)+ §6.4(partial binding 接受)+ §6.5(verify-given dual 概念稳定)+ §6.6(lift)

---

## 2. 交互定义

> **概念定义后才能定。** 这层回答"消费者给什么、拿什么"。

### 2.1 最小输入 set

application 层从 user 接受:

- **rule reference**(具体 DTO 形态留给 blueprint;此处只讨论消费者概念 — 可能是 CompiledDerivationPlan 或更轻 plan-like)
- **binding**(可 complete 可 partial,per §1.3;user-facing 形态留 blueprint 决定;application 内部归一到 `BindingItems` 语义一致的 sorted tuple-of-pairs)
- **engine:** `Literal["native", "souffle", "problog", "pyreason"]`(per §3.5)
- **不**含 facts overlay(per §3.1)

application 层从这些派生 core 必需的 5 项(`branch / binding / witness_facts / view_facts / resolution_by_key`),core primitives 不暴露给 user。

**留 blueprint 决定的细节(不在本 doc):**
- binding 字段类型 `tuple[tuple[str, value], ...]` typedef vs `dict[str, value]`(倾向 tuple,与 baseline §P0-3 `BindingItems` 一致)
- 是否需要 `query_id` / `version` 类 idempotency / replay 字段
- engine_options 字段(若需要,留 engine extension surface topic 决议)

**Source:** Discussion §6.1 / §6.4(partial binding)/ §6.5 / §6.6;baseline §P0-3

### 2.2 最小输出 set

**三层 layered output**(detailed 见 §3.2):

1. **Layer 1 — Core result(总有):**
   - `status: Literal["passed", "failed", "unsupported", "invalid_request"]`(per §3.3)
   - `requested_binding`(回显)
   - `matched_count: int`
   - `matched_binding: BindingItems | None`(只 status=passed 时有;partial binding 命中多个时取 primary)
   - `errors / warnings`(consistent with existing application pattern)

2. **Layer 2 — EvidenceEnvelope(Check result 的 optional evidence field,status=passed 时有):**
   - common envelope:`engine` / `support_kind` / `support_digest` / `branch_index` 等共同 metadata
   - `native_payload`:engine-specific 形态(SupportArtifact / PyReasonTimeline / ProbLogProofGraph / ...);**不抹平**(per §6.5);**必须 inspectable / serializable,不能是 opaque blob**(per §6.9)
   - `branch_atom_projection: BranchAtomProjection | None`(子字段,见 Layer 3;MVP 总是 `None`)

3. **Layer 3 — branch/atom projection(EvidenceEnvelope 的子字段;MVP=None,deferred 到独立 venue):**
   - **MVP 决议(per §6.9):** 字段 reserved(在 protocol 里保留),MVP 总是 `None`;walkable interface 不在 Check MVP 实施
   - **`None` 语义:** "projection 未实现",**不是** "evidence 未提供 / degraded"(evidence 通过 Layer 2 native_payload 仍完整可获取)
   - 字段形态(deferred 实施 / 协议 reserved):
     - `projection_status: Literal["available", "partial", "unsupported"]`(per §3.3)
     - `branches[]`(可遍历)+ 每 branch 的 `atoms[]`(可遍历)
     - 每 atom 字段:`locator`(`b0.a2` 形式) / `atom_kind` / `status`(satisfied / satisfied_by_absence / ...)/ `grounded_terms` / `witnesses` / `asrt_ids` / `details`
   - **后续启用条件(per §6.9):** 第二个 consumer 出现时(如 Diagnose / Explain / evidence UI / per-frame diff capability),在跨 capability 共享 venue topic 决定 walkable 形态,然后回填到 Check
   - 启用后**仅 `passed` 时可靠**约束保留(per §6.4.B.1):`failed` 时不假装给 per-atom 失败状态

**留 blueprint 决定的细节:** 具体 dataclass 命名 / engine-native payload union typing 形态 / partial-streaming 需求(若批量 check 多 binding 在未来扩)。Layer 3 MVP 已决议为 reserved slot + `None`(per §6.9);具体 shared projection shape 留后续 venue。Status-by-field nullable matrix 必须在 blueprint Step 0 冻结,不由本 conceptual doc 代替。

**Source:** Discussion §6.1 → §6.5 累积 + §6.6 lift

---

## 3. 边界决议(8 项,从 baseline §P0-3 抽出)

> 按依赖顺序排,后面的 question 依赖前面的决议。

### 3.1 input 边界

用户提供 "binding" 还是 "事实集 + binding"?
- **A.** 仅 binding:view_facts/witness_facts 从当前 store 投影(读时点)
- **B.** binding + 事实集 overlay:事实集是 overlay(进一步触发 fact-overlay 设计)
- **C.** binding + 事实集替换:完全替换 store 视图

**决议:** **A** — 仅 binding;view_facts / witness_facts 从当前 store 读时点投影
**Source:** Discussion §6.1 — scenario "一组已提交事实"显式排除 overlay/replace

### 3.2 output 最小 set

仅 boolean / + reason / + winning_branch_index / + SupportArtifact?这决定 Check 是 lightweight verify 还是 full evidence-bearing。

**决议:** **三层 layered output**(详细形态见 §2.2)
- Layer 1 Core result 必有(status + requested_binding + matched_count + matched_binding-if-passed + errors/warnings)
- Layer 2 EvidenceEnvelope 在 passed 时有(common envelope + engine-native payload)— **不**抹平 engine 特化能力;**必须 inspectable / serializable**(per §6.9)
- Layer 3 BranchAtomProjection 是 Layer 2 子字段,**MVP=None**(per §6.9 — slot reserved,实施 deferred 到独立 venue/共享 capability;`None` **不**解读为 evidence degraded)
- **不**含 reason / fail localization on failed(per §3.8)

**Source:** Discussion §6.1 + §6.4 + §6.5(三层模型 + projection 独立 enum 修正);§6.5 user 直接给的 final 提议

### 3.3 status 词汇与现有 support_kind 关系

Check 的 status 词汇(input bundle 提到:`derived` / `failed_check` / `below_threshold` / `temporally_unsatisfied` / `unknown` / `unsupported`)是:
- **A.** 独立词汇(application 层全新 Literal)
- **B.** 与 `SupportArtifact.kind`(`native_binding_v1` 等)mapping
- **C.** 与 `_DEGRADED_SUPPORT_KINDS` / `_WITNESS_BEARING_SUPPORT_KINDS` / `_PROVENANCE_BEARING_SUPPORT_KINDS` 三个分类 set 对齐

**决议:** **A** — 两个**独立** application Literal,不与 core support_kind 混

| Enum | 字段 | 取值 |
|---|---|---|
| Top-level outcome | `CheckResult.status` | `passed` / `failed` / `unsupported` / `invalid_request` |
| Projection 能力 | `BranchAtomProjection.projection_status` | `available` / `partial` / `unsupported` |

注意:`EvidenceEnvelope.support_kind` 是 string convention(已有 6 known constants + 3 frozenset 分类,baseline §P0-3 现成),**不属** Check application Literal — 它是 SupportArtifact 透传的 metadata。

**Runtime failure mapping:** `unsupported` 表示已知 capability boundary;`invalid_request` 表示 caller/request shape 错误。Engine/runtime unexpected failures **不**应被压进这两个 status。MVP 应沿用 existing application runtime error propagation(异常/上层错误通道),并在 blueprint Step 0 明确测试这一边界。

**Source:** Discussion §6.4(passed/failed/unsupported/invalid_request 词集);§6.5(`projection_status` 与 `status` 必须分离 — 避免把"能否投影"与"evidence 是否存在"混为一谈,大动脉级别 correction)

### 3.4 ruleref 的输入语义

Check 处理 ruleref atom 时,`rule_ref_resolutions`:
- **A.** caller 预先解析(传入 Check)— Check 完全 stateless
- **B.** Check 自己解析(需要 registry)— Check 不能完全 stateless

**决议:** **B'** — application runtime 接 `registry` side-channel 自己解析;**不**在 `CheckRequest` DTO 里带 registry

具体形态:

| 边界 | 形态 |
|---|---|
| DTO `CheckRequest` | intent-only(rule/plan + binding + engine 等);**不**含 registry / store |
| Runtime function | `check_..._runtime(request, *, store, registry)` — side-channel,与 `evaluate_derivation_plans(request, *, store, registry)` 模式一致 |

**行为:**
- 规则含 `ruleref` 但 `registry is None` 或无法解析 → `status="invalid_request"`(不让底层 primitive 泄出不清晰异常)
- 规则不含 `ruleref` → registry 可为 `None`

**为什么不 A:** A 的真正问题不是"多一步",而是 precomputed `rule_ref_resolutions` 是**新的一致性边界** — caller 可能传入与当前 rule version / registry / 时点不匹配的 resolutions,产生 **silent wrong result**(比"forgot registry → loud error"更隐蔽危险)。application-first 原则下,application runtime 应该是 resolution 的权威入口,不该把一致性责任外包给 caller。

**Caching:** MVP 不做。未来若做,应在 registry/runtime 内部,key 至少含 rule identity/version + registry snapshot/generation;**不**把 cache/resolution object 暴露成用户协议字段。

**与 §3.5 sub-decision 1 对齐:** native + non-native 都走同一 runtime boundary(都接 `registry` side-channel),不分裂。

**Source:** Discussion §6.7 — user 把 B 精确到 B'(side-channel,不在 DTO);user 给的 "precomputed resolutions 是一致性边界" 论据

### 3.5 engine 边界

4 engines 中,native 已有 primitives;非 native engine 有自己 provenance(`SupportArtifact` vs `ProvenanceEnvelope`)。

**决议:** 两个正交 sub-decision 都 resolved:

#### sub-decision 1: Check decision semantics

**B with boundary** — multi-engine via evaluate-then-match / primitive-check hybrid:
- native complete binding:用 `_branch_satisfies` primitives 直接判
- native partial binding:先枚举完整 final bindings,再 subset-match;primary full binding 选定后用该 full binding 构造 evidence
- souffle / problog / pyreason:engine 跑 evaluate(经 evaluate_store dispatch),用户 binding 与产出 candidates / engine payload 可表达的 binding subset-match

**能力边界(non-native engine 不假装 native-style 完整 check):**

| Engine | payload-representable head binding | body-only / mixed / payload-nonrepresentable binding |
|---|---|---|
| native | passed / failed | passed / failed |
| souffle | passed / failed | passed / failed **only if** engine output/support artifact exposes enough binding information;otherwise `unsupported` |
| problog / pyreason | passed / failed(via candidate payload 比对) | **`status=unsupported`**(engine 不暴露 body-only final bindings) |

纪律:Check 不假装 body-only binding 在 problog/pyreason 下能 verify;明确返 `unsupported`,不返 `failed`(后者会让用户误以为是数据问题而非能力边界)。

Blueprint Step 0 必须冻结 "requested binding → candidate payload / engine output" 的映射规则(尤其 multi-head / entity target / variable 同时出现在 head 与 body 的情况)。**Representability gates all non-native Check**,包括 Souffle;如果无法证明 user binding 可由 engine candidate payload / support output 表达,该 engine 下应返 `unsupported`,不能猜测。

#### sub-decision 2: Check evidence shape

**Engine-native first + optional projection**(per §6.5 三层 evidence 模型):
- common envelope(engine + support_kind + support_digest)— 共同 metadata
- engine-native payload — 各自保真,**不抹平**(native: SupportArtifact / pyreason: timeline / problog: proof graph)
- optional branch/atom projection — 带独立 `projection_status`(per §3.3)
- **`projection_status` 描述 projection,不描述 evidence**;非 native engine 即使 projection unavailable,evidence 本身仍在

**Source:** Discussion §6.2(initial multi-engine 倾向)+ §6.4(MVP 边界 first attempt)+ §6.5(engine-native first 修正,大动脉级别)+ §6.6(decision semantics B + 能力边界)

### 3.6 OR-of-AND 多 branch 都满足时的语义

`find_winning_branch_index` 返第一个满足的 branch;Check 是否需要:
- **A.** 仅返第一个(语义同 primitive)
- **B.** 列出所有满足 branches
- **C.** 明确 branch ambiguity 信号(如 status `ambiguous`)

**决议:** **A'** — primary-only with deterministic source-order selection

**核心规则:** Check 在至少一个 matched full binding 存在时返 `status="passed"`。`matched_count` 报告满足 requested binding 的 full bindings 总数。`matched_binding` 与 EvidenceEnvelope.`branch_index` 仅指代 deterministic primary match。多 branch 命中**不是** `ambiguous` status,**不**扩展 Layer 1/2。完整 enumeration 属 Evaluate / Diagnose / Layer 3 territory,**不**属 Check MVP。

#### 约束 1:Primary 必须 stable-sorted deterministic,不是 runtime 偶遇

| Engine | Primary 排序规则 |
|---|---|
| native / souffle | branch source order;同 branch 内按 binding materialization order |
| problog / pyreason | 按 candidate payload deterministic order;若 adapter 不保证 → application 层按 `candidate_key` 或 payload canonical order 兜底排序 |
| partial binding 下 | `matched_binding` 与 `branch_index` **必须**来自同一个 primary matched result(同一完成,不能 split) |

理由:replay / cross-run 比对的稳定性依赖此(否则同 input 不同 run 可能给不同 primary)。

#### 约束 2:Layer 1 只表达数量,不表达 topology

- 保留 `matched_count`
- **不**加 `branch_indices` / `branches_matched_count` / `ambiguous` 字段
- 多 branch 命中是 OR 规则的**正常**语义,不是异常状态

**为什么不 B:** B 会把 Check 从 verifier 推向 enumerator — 一旦返 per-binding/per-branch list,用户会要分页 / 排序 / 所有 evidence envelopes / 跨 engine parity,这就变成 Evaluate API 的第二套形态,Check 失去 distinctness。

**为什么不 C:** `ambiguous` 不应进入 `status` enum。`status` 维度是 outcome / capability / error(`passed` / `failed` / `unsupported` / `invalid_request`);多 branch 命中不是第四种 truth outcome,只是 `passed` 的内部结构,不该升级到 outcome 层。

**未来扩展口子(不污染当前 Layer 1/2):**
- 如 MVP 含 Layer 3 walkable view → Layer 3 只展示 primary evidence
- 未来 `all_matches` / diagnostic view 可能作为独立 capability(如 `Diagnose` / `Explain`),不并入 Check

**Source:** Discussion §6.8 — user 的 A' refinement(deterministic primary + Layer 1 不含 topology);两条强约束(stable sort + count-only)

### 3.7 不完整 binding 的语义

现 primitive 是"silent false"(`_ground_terms` 任一变量不在 binding → 返 None → atom False → branch False)。Check 是否要在 application 层区分:
- **A.** 不区分(silent false 直接返 `satisfied=False`)
- **B.** 区分 "false because unsatisfied"(`failed_check`)vs "false because binding incomplete"(`unknown`)
- **C.** 不完整 binding 直接 raise `BindingShapeError`(认为是 caller bug)

**决议:** **resolved — 由 partial binding 语义自然消解,不需要 `unknown` 状态**

partial binding 是合法输入(per §1.3),语义是 subset match(完整 evaluate body → final bindings → 用户 binding 是否被某 final binding 包含)。所以原本的"不完整 binding"问题分裂为两类:
- **partial binding 但确实没有 final binding 扩展它** → `status=failed`(matched_count=0)
- **binding 形状本身违法**(非法变量名 / 类型不对等)→ `status=invalid_request`

不再需要 `unknown` 区分 unsatisfied vs incomplete — 后者根本不存在(partial 是合法,不算 incomplete)。

**Source:** Discussion §6.4(user 反驳 §6.3 的"reject partial binding"倾向,引入 partial binding subset match 语义);§6.6(lift)

### 3.8 fail localization 的成本-收益

`_branch_satisfies` 当前任一 atom false 即 short-circuit 返 false。若 Check 要给"first failing atom"信息:
- **A.** 不给(返 boolean only)
- **B.** application 层包装:call primitives 多次定位(N atoms 时 N calls,O(N²) 单 binding cost)
- **C.** 改 core `_branch_satisfies` 返 `(bool, failing_atom_index | None)`(侵入修改,但成本 O(N))

**决议:** **A** — 不给 fail localization on `failed`

理由(per user §6.4.B.1):"MVP 里 walkable view 最自然只在 `passed` 时完整可靠。`failed` 时如果没有 diagnostic evaluator,不应假装能给每个 atom 的失败状态。"

evidence walkable view(Layer 3,见 §3.2)在 `passed` 时给完整 per-atom 信息;`failed` 时只给 Layer 1 core result(status + matched_count=0 + errors)。

未来若要 diagnostic-quality fail localization(reason / first-failing-atom 等),应作为独立 capability(可能命名 `Diagnose` 或 `Explain`),不并入 Check。

**Source:** Discussion §6.4.B.1(user 显式约束 walkable view 仅在 passed 时可靠);§6.6(lift)

---

## 4. 未决项(Check topic 外,不阻塞 resolution)

Check topic 内部所有 open items 已 resolved(per §6.9);以下两项是 **Check topic 之外** 的相关 broader question:

| 项 | 说明 |
|---|---|
| Engine extension surface architecture | 起独立 venue topic(候选名 `engine-extension-surface-architecture.md`);包含 engine-native payload DTO 形态 / engine_options 字段 / 各 engine payload schema 归属等 broader question |
| Shared evidence projection venue/capability | 由 Layer 3 deferral 引入(per §6.9);待第二个 consumer(Diagnose / Explain / evidence UI / per-frame diff)出现时启,决定 walkable 形态,回填到 Check Layer 3 |

---

## 5. 与 baseline / blueprint 对接说明

**本 doc 已进入 `resolved` 状态(2026-05-03)。** 所有 conceptual + interaction 决议落地;draft blueprint 可在 `docs/blueprints/active/` 起。进入 `scoped` implementation 前,blueprint 必须先冻结 protocol contract,不能把本 doc 的概念层字段直接当最终 DTO。

- **baseline § 已 cite:** §P0-1(application substrate template)+ §P0-2(evaluate flow + status vocabulary 归属)+ §P0-3(check primitives + ruleref + witness 区分)
- **resolved 后待回填的 baseline anchor:** baseline §P0-3 的 "Open conceptual + interaction questions" 8 项 → 后续 baseline 维护时,§P0-3 对应段落改成"已由 80_/check-operation-conceptual-interaction.md 决议为 X(详见 topic doc §3.X)"形式的 cross-reference
- **draft blueprint 起步条件已满足:**
  - §1 概念定义 ✓(verify-given dual)
  - §2 交互定义 ✓(三层 output;binding 接 complete + partial)
  - §3 全部 8 项 ✓(§3.1 仅 binding / §3.2 三层 / §3.3 两 enum / §3.4 B' side-channel registry / §3.5 B' multi-engine + engine-native first / §3.6 A' deterministic primary / §3.7 partial binding 自然消解 / §3.8 不给 fail localization on failed)
  - §4 内部项 ✓(MVP Layer 3 = A' reserve slot)
- **scoped implementation 前必须冻结的 Protocol Contract(由 blueprint Step 0 完成):**
  - request DTO:rule reference shape / binding wire shape(含 sort key + canonical encoding,partial 与 complete 等价)/ engine field / engine_options 是否存在 / query or run identity 是否存在
  - response DTO:status-by-field nullable matrix / errors-warnings convention / EvidenceEnvelope field name and nesting
  - engine-native payload contract:minimum inspectable + serializable shape;typed union vs JSON-compatible envelope;schema ownership;每 engine round-trip serialize/deserialize 测试
  - native partial algorithm:final-binding enumeration + subset-match + primary selection + evidence construction from primary full binding;banned-call assertion 防 `_branch_satisfies(partial)`(per §7.1)
  - non-native matching contract:BindingItems → candidate payload mapping;**representability test 的具体 predicate**(payload-nonrepresentable 必须可程序化判定,不能猜测);payload-nonrepresentable request → `unsupported`
  - non-native primary tiebreaker:problog/pyreason adapter 不保证 ordering 时,application 层用 `candidate_key` 或 payload canonical sort 兜底(per §3.6 约束 1);Step 0 必须明确兜底 sort 的具体 key
  - ruleref failure contract:missing registry / partial resolution / unresolved child rule exact `invalid_request` details
  - runtime failure contract:unexpected engine/runtime errors propagate through runtime error channel,not `unsupported` / `invalid_request`
  - replay/persistence non-decision:Check MVP result identity / snapshot semantics / audit persistence either explicitly out of scope or explicitly defined
  - drift-prevention(per §7):每条 §7.1-§7.6 trap 对应 Step 0 prevention/detection 决议(banned call assertions / DTO field rejection / round-trip tests)
  - test matrix:complete pass/fail,partial multi-match,deterministic primary,OR branch order,invalid binding,RuleRef with/without registry,native evidence envelope,non-native supported/unsupported boundary,**§7 trap 反测试**(banned partial-to-primitive call / opaque payload rejection / None ≠ degraded / DTO 拒 registry 字段)
- **blueprint 起步指引:** 在 `docs/blueprints/active/YYYY-MM-DD_check-operation.md` 创建,§4 Current Context cite:
  - 本 doc(80_/check-operation-conceptual-interaction.md)— 概念 + 交互决议
  - baseline §P0-1 / §P0-2 / §P0-3 — 现有代码 anchor
- **不进入 blueprint 的内容:** 本 doc §6 Discussion log 的"候选讨论 + iteration 过程"(只有最终决议进 blueprint;过程留在本 doc 作为决议 source 的 audit trail)
- **transition 到 `cited` 状态:** 当 blueprint 在 §4 Current Context 实际引用本 doc 时,Status 改 `resolved → cited`

---

## 6. Discussion log

### 6.1 (2026-05-03) User-scenario anchor + proposed implications

**User-supplied scenario sentence(锚点,讨论入口 C):**

> "我有一条规则和一组已提交事实;我想问某个具体 binding 是否满足这条规则,并在满足时拿到 evidence,在不满足时拿到清晰但浅层的失败/不支持信号。"

**Scenario unpack(组件分解):**

- **输入侧:**
  - "一条规则" → 单 rule(不是 plan-set / multi-rule)
  - "一组已提交事实" → 事实**已在 store**(无 overlay,无 fact 替换)
  - "某个具体 binding" → 单 binding(不是 batch / partial / streaming)
- **输出侧(satisfied):**
  - "拿到 evidence" → 包含 evidence(候选:`SupportArtifact`,因 baseline §P0-3 揭示 native_binding_v1 已是现成产物)
- **输出侧(unsatisfied):**
  - "清晰但浅层的失败/不支持信号" → status 至少区分"失败" vs "不支持";**不**深层 fail localization
- **隐含:**
  - 单步操作(不是 evaluate-then-check 两步)→ §1 candidate B 不符
  - 不产 candidate(只 verify)→ §1 candidate C 优于 A

**Proposed implications(待 user verify;签字后才 lift 到 §1/§2/§3):**

| 段 | Proposed 决议 | Reasoning source(scenario 直接 / 架构推导) |
|---|---|---|
| §1 概念 framing | **C(evaluate 的旁路)** | scenario 单步 + 不产 candidate;baseline §P0-3 揭示 primitives 已存在,C 直接复用 `_branch_satisfies` 等;C 比 D 更精准表达"check 是 evaluate 的 verify-mode mirror"(8-atom 对偶) |
| §2.1 最小输入 set | rule reference(具体寻址留给 blueprint)+ 单 binding;**不**含 facts overlay(per §3.1);engine 字段看 §3.5 | scenario 直接 |
| §2.2 最小输出 set | `satisfied: bool`(必有)+ `status` from vocabulary(必有,需 §3.3 确定词汇)+ `evidence`(satisfied 时有,unsatisfied 时无)+ `errors/warnings`(consistent with application pattern) | scenario "拿到 evidence" + "浅层信号" 两条 |
| §3.1 input 边界 | **A(仅 binding,view_facts/witness_facts 从 store 投影)** | scenario "一组已提交事实"显式排除 overlay/replace |
| §3.2 output 最小 set | satisfied + status + (conditional) evidence;**不**含 reason / fail-localization / winning_branch_index detail | scenario "浅层信号"显式排除深诊断 |
| §3.3 status 词汇关系 | **A(独立 application Literal)** — 候选 vocabulary 至少 `satisfied` / `failed` / `unsupported`,可能加 `unknown`(由 §3.7 决议) | 架构推导:status 是"binding 是否满足规则"的 application 概念;`SupportArtifact.kind` 是"evidence 来自哪种引擎"的 core 概念;两者语义不同,mapping 牵强。scenario 区分"失败 vs 不支持"两 status,与 application 独立 Literal 一致 |
| §3.5 engine 边界 | **A(MVP 仅 native;非 native 返 status `unsupported`)** | baseline §P0-3 揭示 non-native engines 没有 binding-level check primitives(它们有 ProvenanceEnvelope 但不是 satisfaction primitives);加 non-native check 需新 core 算法,不属 MVP。返 `unsupported` 与 §3.3 vocabulary 一致 |

**Scenario 不直接触及的 question(留后续讨论):**

- §3.4 ruleref resolution 由 caller 还是 Check 自己 — scenario 没明示 rule 是否含 ruleref
- §3.6 OR-of-AND 多 branch 都满足时语义 — scenario 没明示
- §3.7 不完整 binding 区分 — scenario "浅层信号"似偏向不区分,但 §3.3 candidate vocabulary 含 `unknown` 时又需要区分;**张力点,待 §3.7 单独讨论**
- §3.8 fail localization — scenario "浅层"显式排除,与 §3.2 一致(此项可视为 §3.2 决议的副产品)

**下一步:**

1. user verify 上面 7 项 proposed 决议(逐项 OK / 修正 / 反对);
2. 不 OK 的项,用户给出新方向后讨论修正;
3. OK 的项 lift 到对应 §1 / §2.X / §3.X section,在 "决议" 行写明,在 "Source" 行 cite "Discussion §6.1";
4. 完成 §1 / §2 / §3.1 / §3.2 / §3.3 / §3.5 后,再启动 §3.4 / §3.6 / §3.7 / §3.8 单独讨论。

### 6.2 (2026-05-03) Revision after user pushback on §3.5

**User feedback:**

> "针对 3.5,'native-only' 有些太窄了,adapt 其他的逻辑引擎是为了测试它的可拓展性,而不是仅适用于 native"

**核心矛盾:** §6.1 提的 §3.5 = A(MVP 仅 native)对应 baseline §P0-3 揭示的"non-native 没有 satisfaction primitives"事实,但**忽视了更上位的架构意图** — adapter 多引擎本身就是为了证明系统跨引擎可拓展。Check 作为 P0 第一个 capability,若退化成 native 专用功能,反而违背 adapter 架构存在的意义。

**§3.5 修正:** 改成"全部 4 引擎都支持,但 implementation strategy 按引擎分":

- **native:** 直接用 `_branch_satisfies` 等 primitives(P0-3 现成路径)
- **souffle / problog / pyreason:** "evaluate-then-match" — 调 engine adapter 跑 evaluate(经 evaluate_store dispatch),拿到 candidates,再看用户给的 binding 是否对应到结果中的 candidate

**Cascading 修正(§3.5 改了反过来要求 §1 和 §2.2 一起改):**

- **§1 概念 framing 修正:**
  - 旧 candidate C("evaluate 的旁路")是 native-specific implementation 描述,不能容纳非 native(后者必须经过 engine,无法"旁路 evaluate_store")
  - **新表述:Check 是 evaluate 的 "verify-given 对偶"** — evaluate 给定规则问"哪些 binding 满足?",Check 给定 binding 问"这一个满足吗?"。两者按同一套 8 类 atom 语义,方向相反(enumerate-side vs verify-side)。implementation strategy 按引擎挑(归 §3.5),不在 §1 概念定义层。
  - 这等于把 §1 candidate set 中 C 与 D 重新框定 — 不是 "C 旁路 vs D 完全独立",而是 "verify-given 对偶 + per-engine implementation"。
- **§2.2 evidence 形态修正:**
  - 旧表述假定 evidence 单一形态(`SupportArtifact`)
  - **新表述:evidence 是 union by engine support_kind**
    - native → `SupportArtifact`(`native_binding_v1`)
    - souffle → `SupportArtifact`(`souffle_witness_v1`)
    - problog / pyreason → 候选指针 + `ProvenanceEnvelope`(`problog_provenance_v1` / `pyreason_provenance_v1`)
  - 这正好对应 baseline §P0-3 的 3 frozenset 分类(witness-bearing / provenance-bearing / degraded)

**修正后的 7 项 proposal table(只动 §1 / §2.2 / §3.5,其他三项继承 §6.1):**

| 段 | Proposed 决议(post-§6.2) | Reasoning source |
|---|---|---|
| §1 | Check 是 evaluate 的 "verify-given 对偶"(同 8 类 atom 语义,反方向)— implementation per engine 在 §3.5 | scenario(单步 verify) + baseline §P0-3 的 8-atom mirror |
| §2.1 | 不变 | scenario 直接 |
| §2.2 | satisfied + status + (cond.) evidence(形态 union by engine support_kind)+ errors/warnings | scenario + §3.5 修正 |
| §3.1 | A(不变;仅 binding,view_facts/witness_facts 从 store 投影) | scenario |
| §3.2 | 不变(浅层输出) | scenario |
| §3.3 | A(独立 application Literal;词汇候选可能因 §3.5 多 engine 加 `engine_failed` 类) | 架构 + scenario + §3.5 修正 |
| §3.5 | **B'(支持全 4 engines;native 用 primitives;non-native 用 evaluate-then-match)** | user feedback + adapter 架构意图 |

**§3.5 修正引入的新派生 question(留 §4 待讨论):**

- 非 native engine 的 "evaluate-then-match" 怎么具体 match?用户 binding 含 body-only 变量(eval 中间产物),候选只有 head 变量(eval 最终产物),如何对齐?
  - 候选 1:仅 match head 变量(忽略用户给的 body-only)
  - 候选 2:partial match 后,根据 head 重跑 native primitives 验证 body-only 部分
  - 候选 3:不允许用户 binding 含 body-only 变量(增加 binding shape 校验)
- 跨引擎 evidence union 的 application DTO 形态 — `SupportArtifact | ProvenanceEnvelope | None` 还是 per-engine optional?
- 引擎运行失败(adapter 报错 / 超时)怎么 status?加 `engine_failed` 词汇还是走 errors 字段?

**下一步:** user verify 上面 revised 7 项 + 3 个新派生 question 的优先级(必答 / 推 §4)。

### 6.3 (2026-05-03) Iteration 3: atom 状态多值 + 可遍历心智模型

**User feedback(verbatim):**

> 关于输出深度(§3.2): 每个 atom 可能不仅有满足、不满足状态,还有"有特定值"的状态,尤其是有时候有的值不止一个(或者这是我的误解,实际上多个值的情况下应对应多个 evidence?),这种情况如何处理?
>
> 此外针对形态,我认为如果能符合用户的心智是很好的: rule 是多个 branch(OR 连接),每个 branch 是一串条件 atom(AND 连接),最好是定义后用户能够通过 for 等方法来遍历每个条件语句,例如第一层是 Branch,Branch 类由一连串的 Constrain 作为 atom 组成,然后 evidence 也可以做类似的设计。

#### A. Point 1 拆解 — atom 多值状态

把"atom 多值"分成 3 个相关但不同的问题:

**A.1 evidence 中每个 atom 已经携带的信息(数据层事实):**

baseline §P0-3 揭示 `SupportArtifact.pred_witnesses[i]` 已是 `PredWitness(pred_atom_key, asrt_ids: tuple[str, ...])` — `asrt_ids` **本来就是 tuple**,数据层已经支持"一个 atom 对应多个支持 assertion"的情况。所以"特定值"诉求在数据层已 native-supported。

**A.2 atom 多值实际出现的场景:**

| 场景 | 行为 | "多值"是哪种 |
|---|---|---|
| Evaluate(给规则,问哪些 binding 满足) | 一个 pred atom 匹配多 fact,展开成多个完整 binding | "多 binding 各自一个 evidence" — 不是"一个 binding 中一个 atom 多值" |
| Check + 完整 binding(verify 模式) | 变量全钉死,一个 pred atom 通常最多匹配一个 fact | 不出现"多值"(unique key 假设下) |
| 同一 fact tuple 多 assertion 支持 | `PredWitness.asrt_ids` tuple 多元素 | **数据层多值,不是逻辑层多值**;evidence 已经容纳 |

**A.3 用户提问的实际答案:**

> "或者这是我的误解,实际上多个值的情况下应对应多个 evidence?"

**大致是的**:
- 逻辑层多值(规则可生成多 binding)→ 多个完整 binding,各自一个 evidence
- 数据层多值(同 fact 多 assertion)→ 一个 evidence 里 atom-level 多 asrt_id
- 没有"一个 binding 内同 atom 真正多值"的情况(否则该 binding 自己就分裂成多个)

**A.4 partial binding 的张力:**

如果 Check 扩成接受**不完整 binding**(用户只给部分变量值),"剩下变量取多个值"就成为相关问题 — 但这把 Check 从纯 verify 扩成 constrained evaluate,语义边界模糊。

倾向 **不扩展**:Check 保持纯 verify(完整 binding 必填);partial binding 走 evaluate(可能未来加 partial-binding 入口,但不是 Check 的语义)。这是张力点,需要 user 判断。

#### B. Point 2 拆解 — 可遍历心智模型

用户希望 `for branch in rule: for atom in branch` 这种心智,evidence 同形态。

**B.1 Evidence 一侧:同意做可遍历**

- 用户读 evidence 是高频操作(check/evaluate 之后)
- 当前 SupportArtifact 数据**已按 branch.atom 索引**(`b{branch}.a{atom}:{kind}` step_key)— 数据层 walkable 已 ready
- application 层加一个 walkable wrapper 是合理 ergonomics 投资,与"用户能 for 遍历"心智完全匹配

**B.2 Rule 一侧:反对在 application 层引入新可遍历 Rule 类**

理由 3 条:
- **SDK 已有 authoring DSL** — `Rule` / `Body` / `Pred` / `Not` 等(baseline §A 模块结构 sdk/dsl/)。**用户写 rule 时已可遍历**(SDK class 就是 OO walkable)。
- **application 接收 lowered 形态** — `CompiledDerivationPlan + WhereIR = list[Any]` 是 SDK lower 后的结果,设计意图就是不再用 SDK class 形态(per baseline §P0-1 standard pattern + 应用 docs §6 保守边界:"application protocol 不接收 SDK facade objects")。
- **v0.1.2 ConditionModule 教训** — 之前 design probe 的 ConditionModule 就是想在 application 层做可遍历 rule,reset 部分原因是这种重抽象在 application-first 框架下无必要(input bundle §3.5)。

如果在 application 层再造一套 `Branch / Constraint` 类,会出现:
- SDK Rule class → application Branch class → core WhereIR list 的**三层 lower**(目前是两层)
- 双向同步的维护成本
- 与 input bundle B'' invariant("rule operable")的关系反而模糊化(因为有两层 rule 表达,哪层"operable"?)

**B.3 综合提议**

- **Rule 输入:** 不动。Check 接 lowered 形态(`CompiledDerivationPlan` 或类似)。**SDK 一侧的 Rule DSL 是用户写 rule 的可遍历入口**,application DTO 仅是 lower 后的承载。
- **Evidence 输出:** 引入 application-level walkable interface(从现有 SupportArtifact 派生薄包装):
  - 顶层 `Evidence`(对应一个 binding 的完整证据)
  - `evidence.branches`(可遍历;OR-of-AND 时多 branch,winning branch 标记)
  - `branch.atoms`(可遍历)
  - 每个 atom-evidence 携带:`kind`(`pred` / `not` / `eq` / ...)/ `status`(satisfied / unsatisfied / ...)/ `asrt_ids`(pred 满足时)/ `details`
  - 这个 walkable 形态从 SupportArtifact 派生(已有 step_key + branch_index 索引)

#### C. 由本轮引入的 §2.2 / §3.2 修正

**§3.2 修正(更细):** 之前提"浅层输出";修正为两 level:
- **Level 1(默认 / 浅):** `satisfied: bool` + `status` + 标准 errors/warnings
- **Level 2(满足时含 evidence):** walkable Evidence 对象(per B.3)— per-atom 信息从 SupportArtifact 派生,不需新核心数据

**§2.2 修正(evidence 形态):** 之前 §6.2 提"evidence 是 union by engine support_kind";本轮加 walkable interface 维度:
- 仍然是 union(native / souffle 给 SupportArtifact-derived;problog/pyreason 给 ProvenanceEnvelope-derived)
- 但**两边都包装成同一 walkable Evidence 接口**(具体内部数据不同,但 `evidence.branches[i].atoms[j]` API 一致)
- 这要求 ProvenanceEnvelope-side 也能投影出 branch/atom 视图(可能需要 engine adapter 配合,值得 §3.5 派生 question 中加一项)

#### D. 留待 user 判断的张力点

1. **Check 是否扩展到 partial binding?** 倾向不(保持 verify 纯洁);user 判断。
2. **Evidence walkable interface 的命名 / 形态:** `Evidence / Branch / AtomEvidence` 这层 OO 结构 OK 吗?(此处不写具体 class,但概念上是这种"三层迭代")
3. **是否同意 rule 一侧不引入新 application class?** 我反对引入(理由见 B.2);user 若不同意,需要更深讨论(可能要回到 §1 概念框架重审)。
4. **walkable Evidence 与 §3.5 多引擎 evidence union 的对接:** 非 native engine 的 ProvenanceEnvelope 是否能 / 应该投影出 branch/atom 视图?这是 §3.5 派生 question 的延伸。

#### E. 修正后的 proposal 表(增量于 §6.2)

只动 §2.2 / §3.2,其他继承 §6.2:

| 段 | 增量修正 | Source |
|---|---|---|
| §2.2 | evidence 形态加 walkable interface 维度(branches / atoms 三层迭代);union by engine 仍然成立 | user feedback Point 2(evidence 一侧)+ baseline §P0-3 现成 step_key 索引 |
| §3.2 | 输出分两 level:浅层默认 + 可选 walkable Evidence;per-atom 状态信息从现有 SupportArtifact 派生 | user feedback Point 1 + Point 2 综合 |

**Rule 一侧明确不修:** 不在 application 层引入 Branch / Constraint 类;SDK DSL 仍是用户写 rule 的可遍历入口。

**下一步:** user 对 D 的 4 个张力点逐项判断;判断完成后,§6.3 决议 lift 到 §1 / §2.2 / §3.2。

### 6.4 (2026-05-03) Iteration 4: user reversal — partial binding + atom multiplicity 重整 + non-native projection_status

**User feedback(verbatim 关键句):**

> "Check 不应接受 partial binding 我会反驳。更好的划分是:complete binding(验证一个完整结果是否满足规则)/ partial binding(验证是否存在某个完整结果扩展了用户给的部分绑定)。这不是 initial-env injection,也不是局部重算。正确实现语义仍然是:完整 evaluate body → 得到 final bindings → 用用户 binding 做 subset match → 命中后用完整 matched binding 生成 evidence。"
>
> "atom evidence 应该描述某个完整 matched binding 下这个 atom 如何被满足。多值属于多 binding 或多 witness,不属于单 atom 的状态分裂。"
>
> "Native 和 Souffle 因为有 b{branch}.a{atom}:suffix support key,比较容易投影成 branch/atom view。PyReason / ProbLog 的 provenance 不一定天然按 branch/atom 对齐。强行统一会制造假一致性。"
>
> "Application 层不引入新的 rule authoring class;如交互需要遍历 rule body,只提供 read-only normalized view,并保持 core body_ir 仍是 runtime authority。"

#### A. 我反转的 3 处(明确收回 §6.3 草案)

**A.1 Partial binding 接受(反转 §6.3.A.4 + §6.1 §3.7 倾向):**

之前我倾向"Check 仅 complete binding";user 反驳。修正后:

| Binding 类别 | 语义 | 实现路径 |
|---|---|---|
| complete binding | 验证一个完整结果是否满足规则 | evaluate body → final bindings → 找精确匹配 |
| partial binding | 验证**是否存在**某个完整结果扩展了用户的部分绑定 | evaluate body → final bindings → **subset match**(用户 binding ⊆ final binding 即命中) |

关键澄清:
- **不是** initial-env injection(违反 baseline §3.2 invariant 的那种 envs=[user_binding] 起步)
- **不是** 局部重算
- 实现仍是完整 evaluate body,然后 subset match;命中后用完整 matched binding 生成 evidence
- 用户体验论据:用户问"这个 document 是否合规"时通常只知道 `$doc=d1`,不该被迫提供 `$risk/$region/...` 等中间变量

**A.2 Atom 多值的三类清晰拆分(反转 §6.3.A.2 的不完整列表):**

之前我隐式假定 atom 可有多值状态;user 反驳。**正确模型:** 一个完整 matched binding 内,每个变量只有一个值;atom evidence 描述"在某个完整 matched binding 下这个 atom 如何被满足"。多值场景拆成 3 类不混淆:

| 情况 | 正确表达 | DTO 体现 |
|---|---|---|
| 同一 rule 可产生多个结果 | 多个 matched bindings,各自一个 evidence | 输出层 `matched_count` + primary `matched_binding`(MVP);未来可加分页/列表 |
| 同一 grounded pred atom 被多个 assertion 支持 | 一个 atom evidence,内含多个 witness/asrt_id | atom evidence 的 `witnesses / asrt_ids` 字段(已是 tuple) |
| 用户给 partial binding,系统补出多个完整 binding | `matched_count > 1`,返回 primary matched binding + count | 同第 1 类的输出层 |

**禁忌:** 不要在 atom 内部建模"多候选值状态" — atom evidence 始终描述"某个具体完整 binding 下"的 atom 满足情况。

**A.3 Non-native engine 边界 — 不承诺同等 walkable evidence(反转 §6.3.B.3 的 "two-side same walkable interface" 提议):**

之前我提"两边包装成同一 walkable Evidence interface";user 反驳"强行统一会制造假一致性"。修正:

- **Check MVP:native-only 最稳**(回到 §6.1 方向,但加一层 projection_status signal)
- Walkable evidence view 加 `projection_status: "available" | "degraded" | "unsupported"`
- native + souffle:`available`(因有 `b{branch}.a{atom}:suffix` support key,可投影 branch/atom view)
- pyreason / problog:`degraded` 或 `unsupported`(provenance 不天然按 branch/atom 对齐)
- **不承诺**所有 engine 都能得到同等 branch/atom evidence

注:此处与 §6.2 提的 "B'(全 4 engines)" 张力 — 实际是 "MVP native-only 实施 + DTO 多 engine 友好 + projection_status 显式信号"。**design 上多 engine,implementation 上 MVP native**。这才同时满足"adapter 架构展示可拓展性"与"MVP 不假装统一"两个约束。

#### B. 我确认的(user 验证我没错的部分)

**B.1 Evidence walkable read-only view:** 同意。形态 `Evidence → BranchEvidence → AtomEvidence`。每个 atom evidence 字段(per user):
- `locator`(`b0.a2` 形式)
- `atom_kind`(`pred` / `eq` / `not` / ...)
- `status`(satisfied / satisfied_by_absence / computed / unsupported / degraded 等;具体词汇待 §3.3 确定)
- `grounded_terms` 或相关 binding slice
- `witnesses` / `asrt_ids`
- `details`

**重要约束(per user):** "MVP 里这个 view 最自然只在 `passed` 时完整可靠。`failed` 时如果没有 diagnostic evaluator,不应假装能给每个 atom 的失败状态。"

**B.2 Application 层不引入 rule authoring class** — 同意,但 user 拆分得更清楚:

- ❌ application 不新增 authoring 用 `Rule / Branch / Constraint` 类(避免三层 lower:SDK DSL → application OO → core list)
- ✅ application 可以有 read-only `RuleBodyView / BranchView / AtomView`(为 inspection / UI / evidence 对齐)
- 关键边界:**view 不参与 authoring,不持有语义权威;core `body_ir` 仍是 runtime authority**

#### C. 修正后的 §3.2 输出形态(per user 直接给的 final 提议)

输出**分层**而不是一次塞满:

**Layer 1 — Core result(总是有):**
- `status: Literal["passed", "failed", "unsupported", "invalid_request"]`
- `requested_binding`(回显用户输入 binding)
- `matched_count: int`(0 时 status=failed)
- `matched_binding: BindingItems | None`(primary full matched binding;只 status=passed 时有)

**Layer 2 — Evidence summary(passed 且 evidence available 时有):**
- `support_digest: str`
- `support_kind: str`
- `branch_index: int`

**Layer 3 — Optional walkable evidence view(opt-in,非 MVP 必填):**
- `evidence: Evidence | None` — 顶层
- `evidence.branches`(可遍历)
- `branch.atoms`(可遍历;每 atom 字段见 §6.4.B.1)
- `evidence.projection_status: "available" | "degraded" | "unsupported"`(per §6.4.A.3)
- 不作 MVP 必填,**除非**明确要把 Check 做成 evidence-bearing 操作

#### D. 由本轮引发的 §1 / §2 / §3 各项最新状态

| 段 | 最新决议(post-§6.4) | Source |
|---|---|---|
| §1 概念 framing | Check 是 evaluate 的 verify-given 对偶,接受 complete binding(完整匹配)与 partial binding(subset match);两者实现都基于完整 evaluate body 后过滤 final bindings | §6.4.A.1 + §6.2 |
| §2.1 最小输入 set | rule reference + binding(可 complete 可 partial)+ engine?(看 §3.5)— 不含 facts overlay | §6.4 + §6.1 |
| §2.2 最小输出 set | 三层(core result / evidence summary / optional walkable view)— per §6.4.C | §6.4.C(user 直接 final 提议) |
| §3.1 input 边界 | A(不变;仅 binding,view_facts 从 store) | §6.1 |
| §3.2 output 形态 | 三层 layered output(per §6.4.C);浅层默认,evidence 可选 | §6.4.C |
| §3.3 status 词汇 | A(独立 application Literal);MVP 候选词汇 `passed / failed / unsupported / invalid_request`(替换 §6.1 提的 `satisfied / failed / unsupported`,因 `passed` 更贴 verify 语义,`invalid_request` 区分 caller bug) | §6.4.C(user 提议的 status 词集) |
| §3.5 engine 边界 | **revised:** Check MVP native-only;DTO 加 `projection_status`(`available / degraded / unsupported`)signal 多 engine 设计意图;不承诺 problog/pyreason 同等 walkable evidence | §6.4.A.3 |
| §3.7 incomplete binding 区分 | **resolved:** partial binding 不是"incomplete";它是合法输入,语义是 subset match。完整 binding 不命中 → `status=failed`;binding 形状本身违法(如非法变量名)→ `status=invalid_request`。**不需要 `unknown` 状态来区分 incomplete** | §6.4.A.1 |

#### E. 未决项 / 留 §3 单独后续讨论

- **§3.4 ruleref resolution 归属** — 本轮未触及
- **§3.6 OR-of-AND 多 branch 都满足** — partial binding 下更可能多 branch 命中,语义需要明确(返 primary branch_index + branches list?或 ambiguous 信号?)
- **§3.8 fail localization** — user §6.4.B.1 明确"failed 时不应假装给 per-atom 失败状态" → 答案接近 "A. 不给"(boolean only on failed),但 evidence walkable view 在 passed 时 OK
- **MVP 是否要 walkable evidence view(§6.4.C Layer 3)** — 决定 Check 是 lightweight verifier 还是 evidence-bearing 操作

#### F. 我之前判断错的地方(audit trail)

- §6.3.A.4:错倾向"Check 仅 complete binding";正确是双模式(complete + partial via subset match)
- §6.3.A 隐式假定:错以为 atom 可有"多值候选状态";正确是 atom evidence 始终描述某个具体 matched binding 内的状态,多值通过 multi-binding / multi-witness / partial-completion 三种正交方式表达
- §6.3.B.3:错提"non-native 包装成同 walkable interface";正确是 native-only MVP + projection_status signal 多 engine 设计意图(避免假统一)

**下一步:** user verify §6.4.D 的 7 项最新决议(尤其 §1 / §2.2 / §3.3 / §3.5 / §3.7 五项变了);verify 完成后 lift 到对应 §1 / §2 / §3.X section,Source cite §6.4。

### 6.5 (2026-05-03) Iteration 5: engine-respectful evidence — common envelope + engine-native payload + optional projection

**User feedback(verbatim 关键句):**

> "针对 pyreason / problog,虽然它们的 evidence 格式不一,难以统一,但各自都扮演重要角色,尤其是概率相关推算和时间推算,直接使用 degraded 或 unsupported 一刀切会伤及大动脉。"
>
> "common surface 最小统一,engine-native evidence 各自保真。"
>
> "degraded/unsupported 不应该描述整个 evidence。它只应该描述某个 projection 是否可用。"
>
> "common SDK 管共享语义...engine extension 管特化能力...不要用一套 meta 机制强行抹平差异。meta 可以做 transport/envelope,不能做 semantic compression。"
>
> "非 native engine evidence is engine-native first; common branch/atom projection may be unavailable or partial."

#### A. 我反转的 — §6.4 evidence layering 错位

§6.4 的 `projection_status: available | degraded | unsupported` 是**整个 evidence 的属性**。这把两件事混了:
- "能否投影成 branch/atom view"(projection 能力)
- "evidence 是否存在"(evidence 本身)

后果:PyReason 的 temporal timeline / interval / firing trace、ProbLog 的 probability proof / explanation graph 这些核心能力,如果不能投影成 branch/atom 就被打成 unsupported,evidence 本身就丢了。**这不是 degraded 那么简单,是切到大动脉**。

#### B. 修正:三层 evidence 模型(per user 直接形态)

EvidenceEnvelope 内部分三个**概念层**(具体 DTO 形态留 blueprint):

| 概念层 | 用途 | 各 engine 表达 |
|---|---|---|
| **Common envelope** | 上层知道结果来自哪个 engine、能否比较、能不能继续 inspect | `engine` / `support_kind` / `support_digest` / 必要的 metadata |
| **Engine-native payload** | 保留各 engine 真正能力,**不抹平** | native: SupportArtifact (`native_binding_v1`)<br>souffle: SupportArtifact (`souffle_witness_v1`)<br>pyreason: PyReasonTimeline / interval / firing trace<br>problog: probability proof / explanation graph / worlds |
| **Optional branch/atom projection** | 尽力投到 walkable view;**带独立的 projection status** | native + souffle:`available`(因有 `b{branch}.a{atom}` support key)<br>pyreason / problog:多数 `partial` 或 `unsupported`(provenance 不天然按 branch/atom 对齐) |

User 给的概念示例:

```
CheckResult.status = passed
EvidenceEnvelope.engine = "pyreason"
EvidenceEnvelope.native_payload = PyReasonTimeline(...)
EvidenceEnvelope.branch_atom_projection.status = "partial"
```

关键纪律:
- **`projection_status` 描述 projection,不描述 evidence** — `EvidenceEnvelope` 保留 engine-native evidence/metadata 的位置;若 engine 本身无 witness/provenance,payload 可以为空或降级,但这与 branch/atom projection 是否可用是两件事
- **engine-native payload 不抹平** — application 层不强制 PyReason 的时间推理变成"branch/atom 的特殊 case"

#### C. Engine extension surface 原则(broader than Check;记录此处供后续 venue topic)

User 提议的未来 architecture 形态:

- `kernel.sdk`:common authoring / store / application shell — 管共享语义(facts / schema / basic rule authoring / candidate identity / audit envelope)
- `kernel.engines.pyreason / problog / souffle`:engine-specific capabilities — 管特化能力(temporal reasoning / probability thresholds / explanation graph / Datalog witness)
- application protocol 层:`CheckRequest(engine="pyreason", engine_options=PyReasonCheckOptions(...))`(已有 `CompiledDerivationPlan.engine_options` 是雏形)

关键原则(完整,broader-architectural):

- common SDK 管共享语义
- engine extension 管特化能力
- **meta 只能做 transport/envelope,不能做 semantic compression**
- 不强行把 PyReason temporal / ProbLog probability 抹平成 native where 的 variant

User 的明确警告:**"当前 rule 使用一套 meta 机制强行统一了它们的格式"是张力点**;Check 不应在 evidence 一侧重蹈这个错误。

#### D. 范围划分:Check topic 该 commit 什么 / 不该 commit 什么

- **Check topic 内 commit 的:** 三层 evidence 模型(common envelope + engine-native payload + optional projection)用作 §3.2 / §2.2 evidence shape
- **Check topic 内 NOT commit 的:** engine-native payload 的具体 schema(PyReasonTimelinePayload / ProbLogProofPayload 等);engine extension surface 的具体目录架构(`kernel.engines.*`)
- **建议:起独立 venue topic** `engine-extension-surface-architecture.md`(命名待定),处理 broader 架构问题

理由:Check 只是第一个 capability,如果在 Check topic 内 fully decide engine extension surface,会让 Check 背负超出范围的设计责任,且决定可能不适用其他未来 capability。

#### E. 由本轮引入的 §1 / §2 / §3 修正

**§2.2 修正(取代 §6.4.C Layer 2 + Layer 3):**

`CheckResult` 顶层只有一个 `evidence_envelope: EvidenceEnvelope | None` 字段(passed 时有)。EvidenceEnvelope 内部按 §6.5.B 三概念层组织:

- common envelope fields:`engine` / `support_kind` / `support_digest` / branch_index 等
- `native_payload` 字段:engine-specific 形态(MVP 可能用 `dict[str, Any]` 或 typed by engine — 留 §3.5 派生 question)
- `branch_atom_projection: BranchAtomProjection | None` 字段:Layer 3 walkable view + 独立 `projection_status`

**§3.2 修正(取代 §6.4.C):**

输出仍是分层,但层次重新组织:

1. **Layer 1 — Core result(总有):** `status` + `requested_binding` + `matched_count` + `matched_binding`(只 passed 时)
2. **Layer 2 — EvidenceEnvelope(passed 时):** common envelope + engine-native payload(per §6.5.B)
3. **Layer 3 — branch/atom projection(EvidenceEnvelope 的子字段,opt-in):** walkable view + projection_status

注:Layer 3 是 EvidenceEnvelope 的 sub-field,不是 CheckResult 的独立顶层 field。

**§3.3 修正(两个独立 enum,不再混):**

| Enum | 字段 | 取值 |
|---|---|---|
| Top-level outcome | `CheckResult.status` | `passed` / `failed` / `unsupported` / `invalid_request` |
| Projection 能力 | `BranchAtomProjection.projection_status` | `available` / `partial` / `unsupported` |
| Support 来源(string convention) | `EvidenceEnvelope.support_kind` | 已有 6 known constants(native_binding_v1 等)+ 3 frozenset 分类 |

**§3.5 修正:拆成两个正交 sub-decision:**

| Sub-decision | 状态 |
|---|---|
| Check **decision semantics**(MVP 是否多 engine) | open;选 A. native-only / B. evaluate-then-match 多 engine,本轮**未定** |
| Check **evidence shape** | resolved(per §6.5.B):engine-native first + optional projection;不再用 §6.4 提的"全 evidence 标 degraded/unsupported" |
| `projection_status` 独立 enum | resolved:与 `status` 分离 |
| Engine extension surface 架构 | flagged:**不在 Check topic resolve**;待新 venue topic |

#### F. 新派生 question(可能跨 topic)

- **engine-native payload 的 application DTO 形态?** `dict[str, Any]` 松耦合 / discriminated union typed by engine / 保留 engine adapter object reference?
  - 影响:application 层是否要 import engine-specific types?(若是,违反 application-first hard constraint;若否,DTO 弱类型)
  - 与 baseline §P0-2 "engine adapter 是 application 不可见的 callable injection" 有张力
- **CheckRequest 是否应有 engine_options 字段?**(类比 `CompiledDerivationPlan.engine_options`)
- **PyReasonTimelinePayload / ProbLogProofPayload 的 schema 谁定义?** application 层 / engine adapter 包 / 完全 untyped?

这 3 个 question 推到独立 venue topic(`engine-extension-surface-architecture.md`)解决;Check topic 仅 commit "engine-native evidence first" 原则,不 commit 具体 schema。

#### G. 还 open 的 Check 内部 sub-question

- §3.5 sub-decision 1:Check decision semantics — A. native-only 还是 B. multi-engine via evaluate-then-match
  - 倾向 B(与 evidence shape 多 engine 一致;evaluate_store + subset match 实施成本低)
  - 但 B 需要 capability boundary:non-native evaluate-then-match 只能匹配 adapter/candidate payload 可表达的 binding;若用户请求 body-only binding 而该 engine 不暴露 final bindings,应返回 engine-specific unsupported/partial,不能伪装成完整 native-style check
  - A 也合理(MVP 边界更小,先验证 native 再扩)
- §3.6 OR-of-AND 多 branch 命中(partial binding 让这更可能)
- §3.4 ruleref resolution 归属

**下一步:** user verify §6.5.E 的修正(§2.2 / §3.2 / §3.3 / §3.5);确认 engine extension surface 起独立 venue topic;表态 §3.5 sub-decision 1 倾向。

### 6.6 (2026-05-03) Iteration 6: verification + §3.5 sub-decision 1 final + lift to formal sections

**User verification(5/5):**

1. ✅ §6.5 三层 evidence 模型 — 包括 BranchAtomProjection 是 EvidenceEnvelope 子字段,不是 CheckResult 顶层
2. ✅ 两个独立 enum(`status` + `projection_status`)
3. ✅ 同意起独立 venue topic 解决 engine extension surface architecture
4. ✅ 派生 3 question 推到 broader topic
5. ✅ §3.5 sub-decision 1 选 **B(multi-engine via evaluate-then-match)**

**§3.5 sub-decision 1 的能力边界(user 显式补充):**

> "non-native evaluate-then-match 只能匹配 adapter/candidate payload 可表达的 binding。若用户请求 body-only binding,而该 engine 不暴露 final bindings,就应该返回该 engine 下的 `unsupported` / `partial`,不能伪装成完整 native-style check。"

具体含义:

| Engine | head-only binding(用户只给 head 变量) | body-only / mixed binding(含 body-only 变量) |
|---|---|---|
| native | passed / failed(用 _branch_satisfies)+ available projection | passed / failed(用 _branch_satisfies)+ available projection |
| souffle | passed / failed(SupportArtifact 有 b{branch}.a{atom} 可投影)+ available projection | passed / failed(同 native)+ available projection |
| problog / pyreason | passed / failed(via candidate payload 比对)+ partial 或 unsupported projection | **`status=unsupported`(engine 不暴露 body-only bindings)** + 不进入 projection 层 |

**纪律:** Check 不假装 body-only binding 在 problog/pyreason 下能 verify;明确返 `unsupported`,而不是返 `failed`(后者会让用户误以为是数据问题而不是能力边界)。

**本轮决议:** §3.5 两个 sub-decision 都 resolved:
- decision semantics:**B with boundary**(per 上表)
- evidence shape:**three-layer engine-respectful**(per §6.5)

**Lift 行动:** §6.1-§6.5 累积的 resolved 决议本轮一次性 lift 到 §1 / §2 / §3 各 section 的"决议"行;§6 log 保留作 trace。Status 从 `draft` 升级到 `discussed`(因仍有 §3.4 / §3.6 / MVP walkable view inclusion 三项 open)。

**剩余 open(待后续讨论):**
- §3.4 ruleref resolution 归属(caller 预解析 / Check 自解析)
- §3.6 OR-of-AND 多 branch 命中语义(partial binding 让多 branch 命中更频繁)
- MVP 是否带 walkable evidence view(Layer 3 是否进 MVP;决定 Check 定位 lightweight 还是 evidence-bearing)
- engine extension surface architecture(独立 venue topic,候选 `engine-extension-surface-architecture.md`)

### 6.7 (2026-05-03) §3.4 ruleref resolution — B' refined to "side-channel registry"

**User refinement(B → B'):**

> "我选 B,但要把措辞精确成 B': application runtime 接 `registry` side-channel,不是 Check protocol DTO 里带 registry。"
>
> "我反对 A 的主要原因不是'多一步麻烦',而是 precomputed resolution 是一个新一致性边界:调用方可能传入与当前 rule/version/registry 不匹配的 resolutions。那会制造比'忘传 registry'更隐蔽的错误。既然 application runtime 已经是权威入口,让它负责解析更符合 application-first 的方向。"

**关键澄清:** 我之前的 B 没明确"registry 在 DTO 里 vs runtime side-channel"。user 把这个区分锁定:

| | 形态 |
|---|---|
| DTO `CheckRequest` | intent-only:rule/plan + binding + engine 等;**不**含 registry / store |
| Runtime function | `check_..._runtime(request, *, store, registry)` — side-channel,与 `evaluate_derivation_plans(request, *, store, registry)` 模式一致 |

**A 的真正问题(user 给的更深论据):**

precomputed `rule_ref_resolutions` 是**新的一致性边界**。caller 可能传入与当前 rule version / registry / 时点不匹配的 resolutions,产生 **silent wrong result** — 这比"forgot registry → loud error"更隐蔽危险。application-first 原则下,application runtime 应该是 resolution 的权威入口,不该把一致性责任外包给 caller。

**Caching 原则(per user):**

MVP **不做**。未来若做:
- 在 registry/runtime 内部做(不在 application protocol 边界)
- key 至少含 rule identity/version + registry snapshot/generation 等
- **永远不**把 cache/resolution object 暴露成用户要管理的协议字段

**与 §3.5 sub-decision 1 对齐:**

native + non-native 都走同一 application runtime boundary(都接 `registry` side-channel)。不会出现"native 要 pre-computed resolutions / non-native 要 registry"的双形态分裂。

**本轮决议:** §3.4 resolved as **B'**(side-channel registry,DTO intent-only)。Lift 见 §3.4 section。

**剩余 open(本轮后):**
- §3.6 OR-of-AND 多 branch 命中语义
- MVP 是否纳入 Layer 3 walkable view
- engine extension surface architecture(独立 venue topic)

### 6.8 (2026-05-03) §3.6 OR-of-AND multi-branch — A' refined to "deterministic primary-only"

**User refinement on §3.6 = A:**

> "我选 A': primary-only, source-order deterministic, no ambiguous status"

**两条 user 补充约束(避免实施时滑向不稳定语义):**

**1. Primary 必须 stable-sorted deterministic,不是 runtime 偶然最先拿到的:**

| Engine | Primary 排序规则 |
|---|---|
| native / souffle | branch source order;同 branch 内按 binding materialization order |
| problog / pyreason | 按 candidate payload deterministic order;若 adapter 不保证 → application 层按 `candidate_key` 或 payload canonical order 兜底排序 |
| partial binding 下 | `matched_binding` 与 `branch_index` **必须**来自同一个 primary matched result(同一完成,不能 split) |

**2. Layer 1 只表达数量,不表达 topology:**

- 保留 `matched_count`
- **不**加 `branch_indices` / `branches_matched_count` / `ambiguous` 等"多 branch"字段
- 理由:`ambiguous` 会把"多满足路径"误包装成异常,但它是 OR 规则的**正常**语义

**B 的更深反驳(user 给的 stronger 论据):**

我之前反 B 是"API 简单"理由;user 给的更深论据:**B 会把 Check 从 verifier 推向 enumerator**。一旦返 per-binding/per-branch list,用户自然要求:
- 完整分页(pagination)
- 排序(sorting)
- 所有 evidence envelopes(per-completion evidence)
- 跨 engine parity(各 engine 的 list 形态一致)

这就变成 **Evaluate API 的第二套形态** — Check 不再 distinct,与 Evaluate 重叠混乱。

**C 的更深反驳:**

我之前反 C 是"加 API 表面";user 给的论据:`ambiguous` **不应**进入 `status` enum,因为:
- `status` 当前维度是 **outcome / capability / error**(`passed` / `failed` / `unsupported` / `invalid_request`)
- 多 branch 命中**不是**第四种 truth outcome
- 它只是 `passed` 的**内部结构**(passed via multiple paths)
- 把内部结构升级到 status enum 会污染 outcome 维度的纯粹性

**未来扩展路径(不污染当前 Layer 1/2):**

- 如 MVP 决定含 Layer 3 walkable view → Layer 3 只展示 primary evidence
- 未来扩展提供 `all_matches` 或 diagnostic view(可能作为独立 capability `Diagnose` / `Explain`),**不**并入 Check

**Architectural patterns(generic-applicable,带进未来 capability 讨论):**
1. **Determinism via stable sort** — 任何"primary 选取"的 API 必须显式定 sort key,否则 replay/diff 不稳定
2. **Layer minimization / Outcome 维度纯粹性** — `status` 类 enum 是 outcome/capability/error 维度,不能被内部结构(如 multi-branch topology)污染

**本轮决议:** §3.6 resolved as **A'**(deterministic primary-only,Layer 1 不含 topology)。Lift 见 §3.6 section。

**剩余 open(本轮后):**
- MVP 是否纳入 Layer 3 walkable view(**Check topic 内 last open item**)
- engine extension surface architecture(独立 venue topic)

### 6.9 (2026-05-03) MVP Layer 3 inclusion — A' refined to "reserve slot + require inspectable native payload"

**User refinement on A:**

> "我选 A: MVP 不含 Layer 3, 但我会把它说成 A': reserve the slot, require native payload inspectability"
>
> "MVP Check does not implement BranchAtomProjection, but EvidenceEnvelope must expose common metadata and engine-native payload in an inspectable/serializable form. branch_atom_projection=None means 'projection not implemented', not 'evidence unavailable'."

**关键 refinement:** 我之前的 A 没明确"`None` 是否意味 evidence 缺失"。user 锁定:**`None` projection 是"投影未实现",不是"evidence degraded"** — 这个 semantic boundary 必须显式声明,否则后续 reader 容易误读。

**MVP 实施约束(per A'):**
1. `EvidenceEnvelope.branch_atom_projection` 字段在 protocol 里**保留**(reserve slot)
2. MVP 该字段总是 `None`
3. EvidenceEnvelope.common metadata + native_payload **必须**以 inspectable / serializable 形式 expose
4. native_payload **不能**是 opaque blob — 要保证 user 能 inspect / serialize 拿到 engine-native evidence 完整信息
5. 后续 from `None` to populated 是 backward-compatible(additive,只增字段值不改形态)

**B 的更深反驳(user 给的 stronger 论据):**

我之前反 B 是"MVP 范围最小化 + ergonomics 不是核心";user 给的更深论据:

1. **Walkable projection 是跨 capability 共享抽象** — 不只服务 Check,还服务 Diagnose / Explain / evidence UI / per-frame diff。在 Check MVP 内定死形态,**又会犯"single capability 先占公用抽象"的错**(v0.1.2 ConditionModule 教训重演)
2. **Layer 3 把 Check 从 verifier 拉向 evidence explorer** — Check 的最小用户价值是"binding 是否通过 + 通过时给 evidence envelope";walkable evidence 是 better UX,**不是 Check 成立的必要条件**
3. **engine-respectful evidence 刚刚锁定,不宜立刻再压一层统一投影** — PyReason / ProbLog 核心价值在 native payload;Layer 3 MVP 上很容易"为了 walkable 强行压平 engine 特性",违背 §6.5 决议
4. **None → populated 向后兼容** — 先保留 slot,等独立 venue 或第二个 consumer 出现时填;比先做错 walkable schema 再迁移成本低

**Architectural pattern(generic-applicable,带进未来 capability 讨论):**

> **"Reserve slot, defer cross-capability abstraction to shared venue"** — 任何"看起来是 cross-capability 共享但 first 出现于某个 capability"的抽象,**应在该 capability MVP 留 slot,不实施;等第二个 consumer 出现时在共享 venue 决定形态**。这避免 "single capability 先占公用抽象" trap。

**本轮决议:** **A'** — MVP reserves `branch_atom_projection` but leaves it `None`. Check MVP 是 Layer 1 + Layer 2。Layer 3 walkable evidence deferred 到 shared evidence projection venue/capability。EvidenceEnvelope 通过 common metadata + engine-native payload 仍是 evidence-bearing;`None` projection **不应**解读为 degraded evidence。

**Status transition:** **discussed → resolved**。Check topic 内部所有 open items 关闭(§1 概念 / §2 交互 / §3.1-§3.8 八项边界 / §4 内部 last item)。

**剩余(不阻塞 Check resolution,在外部 venue):**
- engine extension surface architecture(独立 venue topic;包含 engine-native payload schema / engine_options 等 broader question)
- shared evidence projection venue/capability(由 Layer 3 deferral 引入;待第二个 consumer 出现时启)

### 6.10 (2026-05-03) Blind review corrections before blueprint

**Blind-review method:** three reviewers were given only the bundle README,baseline 70_,venue README,and this topic doc. They reconstructed the design and looked for contradictions without conversation history.

**Result:** reviewers reconstructed the core Check design correctly,including verify-given dual,partial binding subset-match,engine-native evidence first,side-channel registry,deterministic primary,and Layer 3 reserved slot. However,they found several implementation-risk ambiguities. This section records the corrections lifted into §1-§5 and baseline §P0-3.

**Corrections applied:**

1. **Native partial binding contradiction fixed.** Earlier formal text said native uses `_branch_satisfies` directly,while partial binding semantics require final-binding enumeration + subset match. Final decision now says:
   - native complete binding may use `_branch_satisfies`
   - native partial binding must enumerate full final bindings first,subset-match,choose primary,then build evidence from that full binding
   - passing user partial binding directly to `_branch_satisfies` is forbidden because `_ground_terms` missing vars produce silent false
2. **Evidence read-only wording fixed.** "Read-only evidence" now means no facts / candidates / assertions are committed. Generating a derived SupportArtifact / EvidenceEnvelope for the Check result is allowed and expected.
3. **Baseline stale guidance patched.** Baseline §P0-3 now explicitly says direct primitives are only one ingredient,not the whole Check algorithm;its original eight conceptual questions are marked resolved by this topic doc.
4. **Blueprint readiness clarified.** This topic is resolved only at conceptual + interaction level. A draft blueprint may start,but before moving to scoped implementation the blueprint must freeze a concrete Protocol Contract(status-by-field matrix,request shape,response shape,engine payload contract,partial algorithm,ruleref failure contract,runtime error mapping,and test matrix).
5. **Engine matching boundary tightened.** Non-native "head-only" is now phrased as payload-representable binding. If the requested binding cannot be proven representable from candidate payload/engine output,the result is `unsupported`,not guessed `failed`.
6. **Runtime failure semantics clarified.** Unexpected engine/runtime failures are not `unsupported` and not `invalid_request`;they follow the application runtime error channel. `unsupported` is a known capability boundary;`invalid_request` is caller/request shape.

**Remaining work intentionally left to blueprint Step 0:**
- exact DTO / class names and file placement
- rule reference wire shape
- binding wire shape(`dict` vs tuple-of-pairs)
- `query_id` / run identity / replayability non-decision
- exact engine-native payload schema ownership
- status-by-field nullable matrix
- concrete test matrix

### 6.11 (2026-05-03) Second blind validation — pass,with non-native representability tightening

**Second blind validation:** after §6.10 corrections,two fresh reviewers read only the same four docs. Both confirmed:

- native partial binding rule is now clear:enumerate full bindings,do not call `_branch_satisfies` on partial input
- evidence read-only now clearly permits derived EvidenceEnvelope generation
- topic is conceptually resolved,while concrete protocol contract remains blueprint Step 0 work
- baseline §P0-3 no longer misleads authors into direct-primitive-only Check

**Remaining non-blocking caution:** one reviewer flagged Souffle body-only/mixed support wording as too absolute. The formal §3.5 table is now tightened: **representability gates all non-native Check**,including Souffle. If engine candidate payload / support output cannot prove the requested binding,return `unsupported`;do not guess `failed`.

**Final verdict:** no conceptual blocker remains for starting a **draft** Check blueprint. The blueprint must still run a Step 0 contract-freezing gate before `scoped` implementation,with special attention to protocol contract,non-native representability,runtime failure mapping,and tests.

---

## 7. Drift risks / implementation traps(blind validation 抓出 — 防止设计被误读)

本节由三轮 blind validation 抓出的高风险误读模式整理(§6.10 / §6.11 user 双盲 + 本轮 fresh blueprint Step 0 author 模拟 + cross-doc consistency auditor)。每条都对应 §1-§5 已有决议,但 reviewer 反映这些点容易在 Step 0 / impl 时滑回错误方向。**Step 0 author 应在 protocol contract 冻结前逐条 cross-check**,并把 banned-call 类的禁止 pattern 落成 assertion test。

### 7.1 NEVER 把 partial binding 直接喂给 `_branch_satisfies`

- **Trap:** 看到 partial binding 输入,直觉是"调 `_branch_satisfies(branch, binding=user_partial, ...)`"或"`envs=[user_partial]` 起步"
- **为什么错:** baseline §P0-3 揭示 `_ground_terms` 对未绑定变量返 None,触发 silent false → atom False → branch False → 整体 wrong `failed`。这是 silent-wrong-result 类 bug,无 loud failure
- **正确做法(per §1.3 + §3.5):** Native partial binding **必须**先 enumerate 完整 final bindings,再用用户 partial binding 做 subset match;选定 primary full binding 后,**用该 full binding 构造 evidence**(不是用 partial)
- **Step 0 obligation:** 写明禁用 call pattern;加 banned-call assertion test

### 7.2 NEVER 把 engine-native payload 设计成 opaque blob 或强行抹平

- **Trap A(opaque):** 把 `native_payload` 类型为 `bytes` 或不可 inspect 的 wrapped object
- **Trap B(flatten):** 为了 "uniform DTO" 把 PyReason temporal / ProbLog probability 压成 SupportArtifact-like 形态
- **为什么错:** §6.5 称 flatten 为"切到大动脉" — engine 各自核心能力(temporal reasoning / probability proof)在被压平的 payload 里丢失;opaque 同样违反 §6.9 "must be inspectable / serializable"
- **正确做法(per §2.2 + §6.5 + §6.9):** native_payload 按 engine 各自保真;**必须** inspectable / serializable;具体 typing(typed union / JSON-compatible envelope)留 Step 0 决,但**不能**牺牲 engine 特性
- **Step 0 obligation:** typed union vs envelope 的选择必须证明每 engine 的核心 evidence 不丢失;每 engine 加 round-trip serialize/deserialize 测试

### 7.3 NEVER 把 `branch_atom_projection=None` 解读为 "evidence missing / degraded"

- **Trap:** 看到 `None`,误以为 "evidence 不可用" / "engine 不支持"。可能后果:
  - 把 non-native engine 的 passed 结果错误降级
  - 在 status 上添加 "degraded" 等不存在的 outcome
  - 调用方弹出 "evidence unavailable" 误导信号
- **为什么错(per §6.9):** `branch_atom_projection` MVP **总是 None**(slot reserved,不实施);`None` 含义是 "projection 未实现",**不是** "evidence 未提供"。Evidence 通过 Layer 2 native_payload 仍**完整**可获取
- **正确做法:** UI / consumer 看到 `branch_atom_projection=None` 时应继续读 `native_payload`(passed 时总是有);**不**展示 "evidence missing" 信号
- **Step 0 obligation:** 在文档/test 里显式声明 "None ≠ degraded" 语义;加一个 test:passed 结果 + branch_atom_projection=None + native_payload 非空 应被识别为 fully evidence-bearing

### 7.4 NEVER 把 `registry` 加到 `CheckRequest` DTO

- **Trap:** 看到 Check 需要 registry(处理 ruleref),直觉是"那就在 request DTO 里加 registry 字段"
- **为什么错(per §3.4):** registry 是 application runtime side-channel(与 store 同级);若放进 DTO,caller 可能传入 stale / mismatched registry 与当前 rule version,产生 silent wrong result。`CheckRequest` 必须保持 intent-only
- **正确做法:** runtime function `check_..._runtime(request, *, store, registry)` 接 registry;DTO 只表达 user intent
- **Step 0 obligation:** request DTO schema 显式禁 registry 字段(写到 schema doc/test 里);runtime function signature 必须有 registry side-channel,与 `evaluate_derivation_plans(request, *, store, registry)` 模式一致

### 7.5 §6 是 historical trace,不是 current contract;§1-§5 始终 wins

- **Trap:** Implementer 读 §6.X iteration 早期内容(如 §6.1 的 `satisfied` field、§6.3 的 two-side walkable interface、§6.4 的 `degraded` projection_status)以为是 current contract
- **正确做法:** §1-§5 是 single source of truth for current decisions;§6 仅作 audit trail。如 §6 与 §1-§5 矛盾,以 §1-§5 为准(per doc 顶部 "形态" 规则)
- **特别提醒:** §3.5 Souffle 行(post-§6.11 representability tightening)**取代** §6.6 早期的 "Souffle 同 native passed/failed" 表述 — Step 0 应从 §3.5 拷贝 Souffle 契约,**不**从 §6.X
- **Step 0 obligation:** Step 0 sketch 不引用 §6.X 任一段;只引用 §1-§5。引用 §6.X 仅在 audit / 决议追溯时使用

### 7.6 表面看似"工程优化"但实际破坏 invariant 的 anti-patterns

整理几个容易被误判为优化的反模式(全部禁):

- **"为了 cache resolution 在 CheckRequest 加 resolutions 字段"** — 违反 §3.4 / 7.4;caching 应在 registry/runtime 内部
- **"为了 simplify API 把 EvidenceEnvelope common metadata 摊平进 Core result 字段"** — 违反 §2.2 三层结构;EvidenceEnvelope 是 Check result 的 optional evidence field,BranchAtomProjection 是 EvidenceEnvelope 子字段。保持这个嵌套是有意设计(便于 Layer 3 deferred 添加)
- **"为了 uniform 把 problog/pyreason 强行投到 branch/atom view"** — 违反 §6.5 engine-respectful;应返 projection_status="partial" 或 "unsupported"
- **"为了 helpful 在 status=failed 加 first_failing_atom 字段"** — 违反 §3.8;fail localization 是独立 capability(Diagnose/Explain),不在 Check
- **"为了 batch 在 CheckRequest 加 bindings: list 字段"** — 违反 §6.8 (Check 是 verifier 不是 enumerator);批量 check 是后续 capability,不在 MVP

### 7.7 Step 0 cross-check checklist(由 blind validation 推导)

Blueprint Step 0 author 在 freeze protocol contract 前,应针对每条 §7.1-§7.6 写一行 explicit "我们的 Step 0 决议如何 prevent / detect 这条 trap"。如某条无 prevention,Step 0 不能进入 `scoped`。
