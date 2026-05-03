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

## 6. Discussion log(可选,讨论中累积)

(空 — 每次讨论后追加 timestamp + 该次决议变更 + reasoning summary,便于后续 trace)
