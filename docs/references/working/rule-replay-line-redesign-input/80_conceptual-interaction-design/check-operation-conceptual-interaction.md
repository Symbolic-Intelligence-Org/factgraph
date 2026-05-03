# Check Operation: Conceptual + Interaction Design

- **Status:** draft
- **Authority:** source-of-truth for Check operation conceptual + interaction design until cited by blueprint
- **Created:** 2026-05-03
- **关联 baseline section:** `70_codebase-baseline-2026-05-03.md` §P0-1 + §P0-2 + §P0-3
- **关联 design input:**
  - `40_design-discussion-A-with-decision-1.md` 的 A 段(round 1+2 + 锁定 shape)
  - `00_brainstorm-original.md` 命题 4("要支持 boolean check 一个具体 binding 是否符合规则")
  - `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Check"
- **关联 blueprint:** 暂无(blueprint 在本 doc 进入 `resolved` 后由 `docs/blueprints/active/` 起)
- **形态:** 这是一个**讨论 scaffold**,不是 finished concept。各 section 在讨论中累积内容;每项决议必须带 source(回引 baseline / input bundle / 讨论中明确达成共识的论据)。**不写任何具体 file/class 命名**(那是 blueprint 阶段)。

---

## 0. Why this topic exists

Baseline P0-3 揭示:Check 是 P0 三个 capability 中最 ready-to-go 的 — core primitives(`_branch_satisfies` / `_atom_satisfies` / `_ground_terms`)已存在,evaluate / check 是 8-atom mirror,application 层只需薄包装。

但 application DTO 形态 — 输入是什么、输出是什么、status 词汇怎么定 — **完全 open**。这些必须在概念 + 交互层面收敛后才能决定具体代码。

本 doc 的任务:把"Check 概念上是什么 / 消费者怎么交互"讨论到 `resolved` 状态,让 blueprint 可以直接 cite。

---

## 1. 概念定义(待讨论)

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

### 1.3 待回答

- **选哪个?为什么?** — 用户需要的语义是什么(input bundle 用户原话:"结果不合要求可以重新改变条件、facts,重新得到新的合规的结果";Check 的角色是这条链条中的哪一环?)
- **选定后,与 B'' 的连接如何具体表达?** — 不仅 high-level "符合 rule operable"够,要落到具体的"evaluate 不可变 / candidate 不可变 / evidence 不可变"哪一项?

---

## 2. 交互定义(待讨论)

> **概念定义后才能定。** 这层回答"消费者给什么、拿什么"。

### 2.1 最小输入 set(待讨论)

从 baseline §P0-3 的 `_branch_satisfies` 参数集倒推,core 必需 5 项:`branch / binding / witness_facts / view_facts / resolution_by_key`。

application 层应**派生**它们,不直接暴露。可能的最小用户输入:

- rule/derivation plan-like input(具体 DTO 形态留给 blueprint;此处只讨论消费者概念)
- `binding: ?(形态待决,见下)`
- `engine: Literal[...]?`(看 §3.5 决议)
- `(optional)facts overlay?`(看 §3.1 决议)

待决:
- binding 形态:`dict[str, value]` 还是 `tuple[tuple[str, value], ...]`(后者与 `BindingItems` typedef 一致)?
- 是否需要 `query_id` / `version` 类的 idempotency / replay 字段?

### 2.2 最小输出 set(待讨论)

从 baseline §P0-3 已知的可能字段:

- `satisfied: bool`(最小)
- + status(从 status vocabulary 取,见 §3.3)
- + reason(哪个 atom failed,需 §3.8 改 short-circuit 逻辑)
- + winning_branch_index(OR-of-AND 时,见 §3.6)
- + SupportArtifact(完整证据,evidence-bearing)
- + errors / warnings(consistent with existing application pattern)

待决:
- 哪些必有?哪些可选?
- partial / streaming 需求?(若批量 check 多 binding,如何返结果)

---

## 3. 边界决议(8 项 open questions,从 baseline §P0-3 抽出)

> 按依赖顺序排,后面的 question 依赖前面的决议。

### 3.1 input 边界

用户提供 "binding" 还是 "事实集 + binding"?
- **A.** 仅 binding:view_facts/witness_facts 从当前 store 投影(读时点)
- **B.** binding + 事实集 overlay:事实集是 overlay(进一步触发 fact-overlay 设计)
- **C.** binding + 事实集替换:完全替换 store 视图

**决议:** _待讨论_  
**Source:** _待补_

### 3.2 output 最小 set

仅 boolean / + reason / + winning_branch_index / + SupportArtifact?这决定 Check 是 lightweight verify 还是 full evidence-bearing。

**决议:** _待讨论_  
**Source:** _待补_

### 3.3 status 词汇与现有 support_kind 关系

Check 的 status 词汇(input bundle 提到:`derived` / `failed_check` / `below_threshold` / `temporally_unsatisfied` / `unknown` / `unsupported`)是:
- **A.** 独立词汇(application 层全新 Literal)
- **B.** 与 `SupportArtifact.kind`(`native_binding_v1` 等)mapping
- **C.** 与 `_DEGRADED_SUPPORT_KINDS` / `_WITNESS_BEARING_SUPPORT_KINDS` / `_PROVENANCE_BEARING_SUPPORT_KINDS` 三个分类 set 对齐

**决议:** _待讨论_  
**Source:** _待补_

### 3.4 ruleref 的输入语义

Check 处理 ruleref atom 时,`rule_ref_resolutions`:
- **A.** caller 预先解析(传入 Check)— Check 完全 stateless
- **B.** Check 自己解析(需要 registry)— Check 不能完全 stateless

**决议:** _待讨论_  
**Source:** _待补_

### 3.5 engine 边界

4 engines 中,native 已有 primitives;非 native engine 有自己 provenance(`SupportArtifact` vs `ProvenanceEnvelope`)。
- **A.** Check MVP 仅 native;非 native 返 status `unsupported`
- **B.** Check 镜像同样 4-engine Literal,非 native 走 evaluate-then-match 退化路径
- **C.** Check 完全不暴露 engine(implicit `native`)

**决议:** _待讨论_  
**Source:** _待补_

### 3.6 OR-of-AND 多 branch 都满足时的语义

`find_winning_branch_index` 返第一个满足的 branch;Check 是否需要:
- **A.** 仅返第一个(语义同 primitive)
- **B.** 列出所有满足 branches
- **C.** 明确 branch ambiguity 信号(如 status `ambiguous`)

**决议:** _待讨论_  
**Source:** _待补_

### 3.7 不完整 binding 的语义

现 primitive 是"silent false"(`_ground_terms` 任一变量不在 binding → 返 None → atom False → branch False)。Check 是否要在 application 层区分:
- **A.** 不区分(silent false 直接返 `satisfied=False`)
- **B.** 区分 "false because unsatisfied"(`failed_check`)vs "false because binding incomplete"(`unknown`)
- **C.** 不完整 binding 直接 raise `BindingShapeError`(认为是 caller bug)

**决议:** _待讨论_  
**Source:** _待补_

### 3.8 fail localization 的成本-收益

`_branch_satisfies` 当前任一 atom false 即 short-circuit 返 false。若 Check 要给"first failing atom"信息:
- **A.** 不给(返 boolean only)
- **B.** application 层包装:call primitives 多次定位(N atoms 时 N calls,O(N²) 单 binding cost)
- **C.** 改 core `_branch_satisfies` 返 `(bool, failing_atom_index | None)`(侵入修改,但成本 O(N))

**决议:** _待讨论_  
**Source:** _待补_

---

## 4. 未决项(讨论中累积)

(空)

---

## 5. 与 baseline / blueprint 对接说明

- **baseline § 已 cite:** §P0-1(application substrate template)+ §P0-2(evaluate flow + status vocabulary 归属)+ §P0-3(check primitives + ruleref + witness 区分)
- **resolved 后回填的 baseline anchor:** §P0-3 的 8 项 "Open conceptual + interaction questions" → 在本 doc resolved 后,baseline §P0-3 对应段落改成"已由 80_/check-operation-... 决议为 X(详见 topic doc §3.X)"
- **blueprint 起步条件:** 本 doc 至少 §1 概念定义 + §2 交互定义 + §3 全部 8 项决议 进入 `resolved`,blueprint 在 `docs/blueprints/active/` 起,§4 Current Context cite 本 doc + baseline §P0-1/P0-2/P0-3
- **不进入 blueprint 的内容:** 本 doc 的"候选讨论"过程(只有最终决议进 blueprint;过程留在本 doc 作为决议的 source)

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
