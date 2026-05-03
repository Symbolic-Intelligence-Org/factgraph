# 设计方向讨论临时工作文档 (2026-05-02)

- **Status**: working / temporary
- **Authority**: NOT a blueprint, NOT a scope commitment, NOT a reference bundle. 仅作 session 内设计对话的工作底稿。
- **Lifecycle**: 讨论进行时持续更新;讨论结束后产出的具体决策应升级为正式 blueprint(进 `active/`)或 reference 摘要(进 `working/<feature>/`);本文档讨论收尾后可以删除或归档。
- **Trigger**: 用户提供 brainstorm 文档 + 明确新需求("结果不合要求可以重新改变条件、facts,重新得到新的合规的结果"),要求依次讨论 v0.1.x 设计未覆盖的方向。

---

## Part 1 — 检视结果摘要

### 1.1 Brainstorm ↔ B'' 设计材料对照

用户提供的 brainstorm 与 repo 内两份现有材料**高度同构**:
- `docs/references/working/rule-replay/evidence-tree-proof-recheck-ideas-2026-04-30.md`(B' 草案,1808 行)
- `docs/references/working/rule-replay/operational-evidence-tree-rule-replay-design-2026-05-01.md`(B'' 工作笔记,378 行)

| Brainstorm 概念 | B'' 工作笔记里对应 |
|---|---|
| 模块化(layer1 sugar / layer2 reliable) | "Minimal condition modules" + branch IR |
| 最小模块有 id/type/params,id 可生成或显式 | `condition_id`(generated)+ `shared_id`(explicit) |
| 同 id 同条件 → 同时改变(跨 rule) | "Cross-rule shared condition changes require explicit shared identity" |
| Evidence 同样最小模块组成,是 rule 子集 | "Evidence is run-derived view of evaluation/check" |
| 模块状态(true/false/unknown,有具体值) | "Status vocabulary: not_derived/failed_check/below_threshold/temporally_unsatisfied/unknown/unsupported/not_materialized" |
| 用户对 evidence 模块操作 → re-evaluate | EvaluationOverlay(`FactValueOverride` + `RuleDisable` + ...) |
| 不能"唤起余温的逻辑电路" | "Local proof-frame recheck only diagnoses; cannot decide new truth" |
| Replay-based / counterfactual proof analysis | B'' 工作笔记的核心命名 |
| Why-not provenance | "Lazy why-not carrier for explicit candidate universe" |
| Speaking evidence tree | "Smallest observed change responsible for status change" + status vocabulary |
| 最小 carrier + 解释时计算(成本从存储转计算) | "Lazy red carriers store only replay carrier; materialize on demand" |
| Head 参数替换(boolean compliance test) | "Check operation: Does this specific binding satisfy this rule?" |
| 模块在 branch 队列中表达 | "Branches Instead Of Exposed `and`":branch=OR,branch 内=AND 序列 |

`context.md` / `ideas.md` 在 repo 中不存在,但同期 master design 在 `~/.gstack/projects/hnsm-backend/zhenzhili-master-design-{20260321,20260427}*.md` 中(2026-04-27 已 pivot 到 "Challenge Layer for LLM-driven decisions",未在本讨论 scope 内)。

### 1.2 B'' "Suggested First Implementation"(11 项)vs v0.1.x 实际交付

| # | B'' suggest item | v0.1.x 状态 |
|---|---|---|
| 1 | rule module ids and branch ids | ✅ v0.1.2 |
| 2 | rule patch for replace | ✅ v0.1.1 |
| 3 | rule patch for disable | ✅ v0.1.3 |
| 4 | rule patch for parameter override | ❌ v0.1.4 abandoned(发现是 4 类语义) |
| 5 | optional add-condition | ❌ |
| 6 | native evaluate with success evidence | ✅ pre-v0.1 |
| 7 | **native check for explicit binding**(brainstorm "head 参数替换") | ❌ |
| 8 | **lazy why-not carrier for explicit candidate universe** | ❌ |
| 9 | run diff + evidence diff 分两层 | ✅ v0.1.1 |
| 10 | no global failed-attempt trace | ✅(正确未做) |
| 11 | engine capability declarations | ❌ |

完成度 **5/11 ≈ 45%**。v0.1.x 真正新做的是 1+2+3+9 四件,abandoned 4,未做 5/7/8/11。

### 1.3 用户新需求 vs 当前差距

需求:**"结果不合要求可以重新改变条件、facts,重新得到新的合规的结果"**

| 拆解动作 | 当前支持 | 缺口 |
|---|---|---|
| 改条件 | ✅ `replay_with_patch(action="replace"|"disable")` | atom-level 替换/禁用都有;**add-condition 缺** |
| **改 facts** | ❌ **完全没有** | 当前要改 fact 必须走正式 `retract + set/add` commit;**没有 in-memory `FactValueOverride` overlay** |
| 重新评估 | ✅ `SDKStore.evaluate(...)` | 已有 |
| **得到 boolean 合规结果** | ❌ **没有** | 当前 evaluate 返回 candidate set,不返回"特定 binding 是否合规";brainstorm 里你也提了"当前不能优雅地把 rule head/select 直接替换成实际值作为 boolean API" |

**核心 missing 一对:`FactValueOverride` overlay + `Check` operation**。两者结合才能完整支持工作流。

### 1.4 几个关键观察

**观察 1 — v0.1.x 实际是 B'' 设计的"前半段"**

我们做了 rule-side mechanics(replace/disable/module IR/locator stability),没做 scenario-level overlay(EvaluationOverlay + FactValueOverride + ProofFrameRechecker)和 Check operation。B'' 工作笔记里这些都不是 deferred,是 suggested first implementation 的一部分。意思是:我们以为做了一个完整 v0.1.x preview,实际做的是 **B'' 设计中"改 rule 的那一半"**,完全漏了"改 facts + 验证特定 binding"那一半。

**观察 2 — ProofFrameRechecker 不是"局部重算"**

brainstorm 里你 reject 了"部分重计算机制",B'' 也认同这条。但 B'' 提的 `ProofFrameRechecker` 是**"局部诊断"不是"局部重算"** —— 类比 SAT solver(求解)+ proof checker(验证 certificate),checker 不决定新真理,只回答"旧 proof path 在新 overlay 下还成不成立?"。输出三种状态:`still_valid` / `invalidated` / `unknown_requires_full_eval`,与 full re-evaluate **并列**展示。这个区别值得专门讨论。

**观察 3 — "L8 = 持久化"这个 framing 不准确**

我之前 evidence-vision synthesis 把 L8(audit JSONL replay persistence)说成"最高杠杆候选"。但 brainstorm 里你提的是"把成本从存储转移到解释时计算" —— 存 carrier (ID, version, ...) 而非完整 evidence tree,需要时再 recompute。**L8 的真正价值不是"持久化已有 evidence",而是"持久化 carrier 让后续 lazy recompute 成为可能"**。这与 B'' 的 lazy why-not carrier 是同一个机制。

**观察 4 — Brainstorm 的开放问题没在 v0.1.2 module IR Step 0 spike 中被覆盖**

- "rule 的条件可以在外边定义吗?" → 跨 rule 共享 / library identity
- "是否存在最小模块表达不了的条件?" → 表达边界
- "应该设定的语法边界?" → 哪些条件类型该接受
- "最小模块在 branch 队列中表达?" → branch IR 形态(B'' 已答 = 是)

v0.1.2 module IR Step 0 spike 覆盖的是"module IR 怎么实现",不是"module 系统的语义边界"。这些问题等价于"module 系统该长什么样",未被讨论。

---

## Part 2 — 待讨论的设计方向

每个方向独立编号。讨论顺序由用户决定。每个方向初始只列 **topic + 关键问题**,讨论展开时填 **discussion log + 临时结论**。

讨论收尾时,某些方向会:
- 升级为正式 blueprint draft(进 `docs/blueprints/active/`)
- 折叠进 evidence-vision synthesis(更新 L0-L11 status)
- 标记为"design-only,等真用户反馈再启动"
- 标记为 abandoned(像 v0.1.4 一样)

---

### A. Application-level explicit binding check, no fact override

**(Renamed from "FactValueOverride + Check operation" after round 1. FactOverride 拆出,见 H 方向。)**

**Source**:
- B'' §"Check"(operational-evidence-tree-rule-replay-design:189-205)
- Brainstorm: "head 参数替换" / "boolean compliance test"

**核心 topic**:在 `kernel.application` 加新 protocol 接 explicit binding check —— 给定 rule/derivation + 具体 binding,返回 passed/failed/unsupported + 成功时的 support。**不**改 fact;**不**注 initial env;**不**承诺 failed atom locator;native-only;committed ledger facts only。SDK wrapper 是第二步事(per Decision 1)。

**Discussion log**:

**Round 1 (2026-05-02):**

- 我提议:`SDKStore.check(...)` SDK 方法 + `replay_with_patch(..., fact_overrides=...)` kwarg 扩展,内部 `_evaluate_with_overlay`-style entry,FactValueOverride/Check 一起做
- 用户 5 条源码级修正:
  1. **Application 是设计中心** — `derivation_runtime.evaluate_derivation_plans()` 已是 canonical executor(`derivation_runtime.py:69`),`SDKStore` 只 forward(`store.py:735`);Check 应作 application protocol 新增,不应先在 SDK 加方法
  2. **不能 filter CandidateSet** — `_builders.py:39,90` 用 head_vars 构造 payload + 按 candidate_key dedupe,body-only var 检查不可靠;正确 hook 在 native where evaluation 的 final bindings / `BindingSupportCapture` rows,在 candidate 构造之前
  3. **不能 inject initial env** — `where_eval.py:181` 每 branch 从 `envs=[{}]` 起;inject 会让 branch "假装"产出 var;MVP 应 evaluate 完整 body 后过滤 final bindings
  4. **failed_atom_locator 不能作 MVP 硬承诺** — `evaluate_where()` 失败只返空 binding,无 atom-level diagnostic;先返 passed/failed/unsupported,失败诊断 best-effort 或单独"where diagnostic evaluator"
  5. **SDK replay 已有偏重,Check 不该再加深** — SDK 已背 locator parsing / replace / disable / module lowering / ReplayResult / CandidateDiff;新 check 进 SDK 会复制 core 语义制造 drift
- 我接受全部 5 条修正
- 用户进一步提出 strangler migration framing(见 Decision 1)— 当前 SDK replay surface freeze,新能力 application-first,后期内部下沉,**不**回撤
- A 重定为:**Application-level explicit binding check, no fact override**

**锁定 shape:**

```python
# kernel.application protocol 新增
@dataclass(frozen=True)
class CheckDerivationRequest:
    plan: CompiledDerivationPlan
    binding: dict[str, Any]   # 具体 var → value
    engine: str = "native"

@dataclass(frozen=True)
class CheckDerivationResult:
    status: Literal["passed", "failed", "unsupported"]
    binding: dict[str, Any]                # echo
    support_digest: str | None = None      # filled when passed
    support_kind: str | None = None        # filled when passed
    branch_index: int | None = None        # filled when passed
```

**锁定 boundaries:**
- native-only(其他 engine → unsupported)
- committed ledger facts only(no fact override;FactValueOverride 是 H 方向)
- no initial env injection(evaluate 完整 body 后过滤 final bindings)
- no failed locator guarantee(MVP 三态;rich diagnostic 后做)
- no RuleRef expansion unless explicitly accepted
- SDK wrapper deferred(Decision 1):先 application protocol,SDK 等真 UX 需求

**Internal flow(MVP):**
1. `application.check_derivation_plans(req)` 接 request
2. 调 native where evaluator,正常跑(无 env injection)
3. 收集所有成功 branch 的 final bindings + `BindingSupportCapture` rows
4. 过滤:user-provided check binding 是否被任一 final binding 完全包含?
5. 命中 → `passed` + 那条 binding 的 support_digest/kind/branch_index
6. 未命中 → `failed`(无 binding/support 字段)
7. 不支持 engine / 含 RuleRef 但未 accept → `unsupported`

**Round 2 待答 sub-questions:**
- A.x1 多 branch 都成立时,`branch_index` 报哪个?(Souffle witness 用 source-order wins;native 同模式?)
- A.x2 `support_digest` 在 `failed` 状态下确认 None,不是 zero-digest placeholder("sha256:000...0")?
- A.x3 `binding` 输入不完整(只指定 head 部分 var)是否合法?对应 partial check:"head $doc=X,$risk 任意" — 合法的话 returned binding 是哪个?
- A.x4 这条 application protocol 扩展走正式 blueprint 还是因为 additive entry 可以 lighter scope?

**临时结论**:

- shape 已锁(见上),仅余 4 个 sub-question 待 round 2 答完即可推 active blueprint
- FactValueOverride 拆出,新 H 方向单独讨论
- A round 1 同时确立 Decision 1(strangler migration),后续所有方向受影响

---

### B. EvaluationOverlay 作为多 action 容器

**Per Decision 1:** Overlay container 在 `kernel.application` 定义,SDK wrapper 推后。**不**继续给 `SDKStore.replay_with_patch` 加新 action 或 kwargs。

**Source**:
- B'' §6 `EvaluationOverlay`(proof-recheck-ideas:806-1043)
- B'' §6.6 多个修改的语义(combined effect,non-attribution)
- Brainstorm: "用户可以针对它们进行一些操作,例如去除某些条件,更改某些条件,增加某些条件,等操作"

**核心 topic**:在 application 层定义 EvaluationOverlay protocol(rule-side + fact-side actions 容器),支持多 action 同时 declarative apply。SDK 现 `replay_with_patch` 保现状(per Decision 1 freeze);新 application surface 通过将来的 SDK wrapper(或直接走 application)使用。

**关键问题**:
- B1. 多 action 同时生效 vs 顺序应用 —— B'' 明确推荐 "无序声明式 combined effect",不做 marginal attribution。同意吗?
- B2. 冲突检测(B'' §6.7):同 asrt_id 多 override / 同 rule disable 多次 / etc
- B3. v0.1.4 abandoned 的 ParameterOverride 是否在这个框架下重新评估?(brainstorm 里 condition 类型多样性的延伸)
- B4. API shape:`replay_with_patch(overlay: EvaluationOverlay)` 替代 `replay_with_patch(locator, new_atom, action)` 现有 surface?或并存?
- B5. EvaluationOverlay 跟 ReplayResult 的关系:`ReplayResult.applied_overlay` 还是分开
- B6. Actor / reason 字段是否 v0.1.x scope?B'' 写了 `actor=...; reason=...`

**Scope 估算**:中等;如果 A 已落地,B 主要是 API container 化,3-5 轮

**Discussion log**: (待填)

**临时结论**: (待填)

---

### C. ProofFrameRechecker — 局部诊断器(非局部重算)

**Per Decision 1:** Rechecker 是新 runtime capability → 在 `kernel.application`(或 `kernel.audit`)定义 protocol,不在 SDK 加新方法。

**Source**:
- B'' §5(proof-recheck-ideas:331-805,核心章节,也是 B'' 与单纯 replay 之间最大的产品差异点)
- Brainstorm 里被 reject 的"部分重算"的反向:不算新真理,只诊断旧路径

**核心 topic**:在 full re-evaluate 之外加一个**小型解释器**,接收 `(old_evidence_tree, evaluation_overlay) → RecheckReport`,只回答"旧 proof path 在新 overlay 下还成不成立?"。**不**搜索新 candidate,**不**生成新 proof,**不**做 fixed-point。它的输出与 full re-evaluate 并列展示,产生 B'' §5.7 推荐的三段式输出:

```
Local proof recheck:
  old support path invalidated at condition X
Full re-evaluation:
  candidate still exists via alternate support
Decision diff:
  candidate unchanged, support path changed
```

**关键问题**:
- C1. 这是 v0.1.x 必须有还是 v0.2 候选?B'' 把它列为核心,但 v0.1.x 至今完全没碰
- C2. B'' §5.6 列了 9 类失败模式(旧 proof 失效但结论成立 / source-order wins / RuleRef 递归不完整 / fact override active vs witness / negation / engine-specific provenance / candidate identity / rule disable scope / engine 边界)。这些处理需要重新设计 SupportArtifact 输出形态?
- C3. 与现在的 `EvidenceComparison` shallow metadata diff 的关系:rechecker 提供更细的 frame-level 信息,EvidenceComparison 是顶层 metadata —— 两者分层共存还是合并?
- C4. "ProofFrame" 作为 view layer 是否要新增?B'' §4.2 说 "raw tree node 的 normalized wrapper,不强行塞进 raw DTO public contract"
- C5. Native-only?Souffle witness / ProbLog provenance / PyReason timeline 能否复用同一 rechecker
- C6. 真正的 product 价值评估:用户面对一个 "old proof invalidated at cond X" + "candidate still exists via alt path" 的 UI,他们需要这个 distinction 吗,还是就要简单 "改了之后结果是 X"?

**Scope 估算**:大;需要先设计 ProofFrame 形态,才能设计 rechecker;7-10 轮

**Discussion log**: (待填)

**临时结论**: (待填)

---

### D. Status vocabulary + 最小因果识别(让 evidence diff "说话")

**Per Decision 1:** Status vocabulary + 最小因果是 result/diagnostic shape — 在 application protocol 层定义(可能影响 `EvidenceComparison` / `CheckDerivationResult` 等 DTO)。

**Source**:
- B'' §"Status Vocabulary"(operational-evidence-tree-rule-replay-design:271-281)
- B'' §"Evidence Comparison"(同 doc:285-296)"summarize the smallest observed change responsible for a status change"
- Brainstorm: "可以'说话'的 evidence tree,告诉用户什么地方的条件导致整体不成立/成立"

**核心 topic**:
- 把 evidence 状态从 binary(`derived`/`not_derived`)+ shallow metadata,升级为结构化 status vocabulary(`failed_check` / `below_threshold` / `temporally_unsatisfied` / `unknown` / `unsupported` / `not_materialized`)
- 在 diff 中识别"最小因果变化" —— 不只列 N 个差异,而是定位"最关键的一个差异是什么"

**关键问题**:
- D1. status vocabulary 的实际触发条件:每个状态对应哪些 engine 输出?(native 没有 below_threshold;PyReason 有 temporally_unsatisfied;ProbLog 有 below_threshold)
- D2. "最小因果"的算法:根据 dependency graph 找 minimal cut?还是根据 frame 顺序找最早失败点?
- D3. 输出形态:string narrative("temperature condition failed at room_a;all other conditions held")vs structured object(`MinimalCausalChange { frame_id, kind, before_state, after_state }`)?
- D4. 跟 ProofFrameRechecker(C)的关系:status vocabulary + minimal causal 是 rechecker 的 output shape?还是独立扩展?
- D5. UI / NL rendering 是否在 kernel scope?(应该不在,但需要给 service.static_ui 提供足够 hook)

**Scope 估算**:5-7 轮 if rechecker 已有,10+ 轮 if 从零开始

**Discussion log**: (待填)

**临时结论**: (待填)

---

### E. Lazy why-not carrier + candidate universe boundary

**Per Decision 1:** Carrier persistence + candidate universe orchestration 在 application 层(可能借助 `kernel.audit` 持久化机制);SDK 只负责消费 carrier,不负责生成。

**Source**:
- B'' §"Lazy Why-Not Trace"(operational-evidence-tree-rule-replay-design:217-267)
- Brainstorm: "为 rule 增加一些例如 why-not provenance 的机制"
- evidence-vision synthesis L6

**核心 topic**:不预先存所有失败 case 的完整 evidence tree(成本爆炸),而是:
- 用户先定义 candidate universe(显式 binding list / entity type 全集 / query / cartesian + 上限)
- 跑 evaluate → green = 成立,red carriers = universe - green
- red 只存最小 carrier `(rule_id, version, head_binding, source_run_id, mode=check)`
- 用户点开某个 red item → 调 check operation 重算 → 出 failed check report

**关键问题**:
- E1. candidate universe 的真实化:B'' 列了 5 类来源(显式 binding / entity type 全集 / query / bounded cartesian / paginated)。哪些 v0.1.x 能直接做,哪些需要新基础设施?
- E2. 与 A(Check operation)的依赖:Lazy why-not 完全建立在 Check 之上 → 必须 A 先做
- E3. 与 status vocabulary(D)的依赖:red 不只是 false,还要分 below_threshold / temporally_unsatisfied / unsupported / etc → 必须 D 先做
- E4. Cost model:B'' 说"成本从存储转到 explanation-time computation"。这是真的吗?如果用户点开很多 red items,explanation cost 累计会不会比预存还高?
- E5. UI implication(虽然 UI 不是目标,但 carrier 设计要为可能的 UI 留 hook)
- E6. 与 audit package 持久化(L8 in evidence-vision)的关系:carrier 持久化 = lazy why-not 的前提

**Scope 估算**:大;依赖 A 和 D;独立做需要 8-10 轮

**Discussion log**: (待填)

**临时结论**: (待填)

---

### F. shared_id / library identity 真实化

**Per Decision 1:** shared_id 生产/消费在 `kernel.authoring`(已是 module IR home)+ `kernel.application`(运行时跨 rule resolution),SDK 不参与 identity 决策。

**Source**:
- v0.1.2 `ConditionModule.shared_id` 字段(已存在,无生产者无消费者)
- B'' §"Condition Ids And Shared Identity"(operational-evidence-tree-rule-replay-design:124-134)
- Brainstorm 第一个 question: "rule 的条件可以在外边定义,然后再在定义 rule 时关联对应项吗?这种情况应该显式定义 id 吗?"

**核心 topic**:让多个 rule 显式声明共享某个 condition module(同一权重、同一审计点、改一处影响多处),通过 explicit `shared_id` 或 library reference 表达,**不**通过 atom 内容相同隐式 merge。

**关键问题**:
- F1. shared_id 的命名空间:UUID / source span / structural hash / 用户提供 string?B'' 说"用户提供更稳定";brainstorm 也偏向显式
- F2. Library 形态:condition library 是独立 asset 还是 rule 的 sub-asset?
- F3. 跨 rule 改动语义:改 shared condition 后,所有引用它的 rule 都被影响 —— 这个改动是否需要每个 rule 重新 compile?audit?
- F4. Replay 语义:disable 一个 shared condition,其他 rule 是否也受影响?如果是,是 feature 还是 bug?
- F5. v0.1.2 `ConditionModule.shared_id` 字段已留接口,谁来填?在 authoring 编译期还是 runtime?
- F6. Versioning:shared condition 自身的版本与 rule 版本如何关联?

**Scope 估算**:中等;关键设计问题是命名空间 + 跨 rule 影响语义;5-7 轮

**Discussion log**: (待填)

**临时结论**: (待填)

---

### G. Add-condition + binding planner

**Per Decision 1:** Add-condition 是新 rule patch action — 应在 application protocol(EvaluationOverlay 的 action set)定义,**不**继续给 `SDKStore.replay_with_patch` 加 `action="add"`(那会破 freeze)。

**Source**:
- B'' §"Adding Conditions And New Variables"(operational-evidence-tree-rule-replay-design:160-174)
- B'' §"Suggested Blueprint Scope" 把 add-condition 列为 "optional MVP"
- Brainstorm 提及 "增加某些条件" 操作

**核心 topic**:在 replay variant 里给 rule 加新 condition(可能引入新变量),由 compiler / planner 决定如何 bind 新变量,失败则 raise unbound-variable error。**不**在 patch-time 限制 "新条件不能引入新变量"。

**关键问题**:
- G1. patch-time 校验 vs compile-time 校验:B'' 明确说"compile 时由 planner 处理,patch 时不限制"。同意吗?
- G2. binding planner 的能力:能从 rule head / branch sources / prior conditions / declared enumerators 推导 binding。当前 compiler 有这个能力吗?
- G3. API shape:`replay_with_patch(action="add", branch_index, atom)` 还是 `replay_with_patch(action="add", branch_index, position, atom)`?
- G4. 与 disable 的对偶:disable 跳过 atom,add 插入 atom —— 都不动 module_id 但需要重新分配 locator(b0.a3 之后插入新 atom 会不会让原 b0.a4 变成 b0.a5?)
- G5. locator stability:如果 add 让下游 locator shift,等于回到 v0.1.3 disable Step 0 拒绝过的 drop-atom 模式。处理方案?
- G6. 与 EvaluationOverlay(B)结合:多 action 同时改 + add 时如何处理 locator 关系?

**Scope 估算**:5-7 轮 if binding planner 现成;10+ 轮 if 需要新建

**Discussion log**: (待填)

**临时结论**: (待填)

---

### H. Fact-level scenario overlay(从 A 拆出)

**Source**:
- B'' §6.4 `FactValueOverride` (proof-recheck-ideas:861-879)
- Brainstorm: "改 facts"
- 用户需求("改 facts → 重评 → 拿合规结果")的另一半

**核心 topic**:让 evaluation 能在 in-memory overlay 下"假装"看到不一样的 fact 值,**不写 ledger**,作为 what-if scenario;用户可以把 H + A 组合做"改完 facts 再 check 是否合规"。

**关键问题**(待 round 1 详谈):
- H1. Override 语义:`asrt_id`-level vs `(pred_id, e_ref)`-level vs active projected value
- H2. Multi-cardinality predicate 怎么处理(replace_all vs add_alongside)
- H3. Overlay 的 application DTO 形态(per Decision 1,先在 application 定义)
- H4. Negation / absence 边界(B'' §5.6.6:旧 success tree 不一定够证 absence)
- H5. Fact add / remove 是否要预留 API 形(MVP 只 override 还是统一 `FactSet(value|None)`)
- H6. Engine 边界:native-only(同 v0.1.x 模式)
- H7. Overlay 跟现 `replay_with_patch` 怎么组合(A + B + H combined scenario)— 或留 B 方向解决

**Scope 估算**:中-大(因为需要新建 overlay-aware projection layer);独立 5-7 轮 if 不含 add/remove

**Discussion log**: (待开 H 时填)

**临时结论**: (待开 H 时填)

---

### 待补充方向(讨论时随时新增)

讨论过程中如果发现新方向,在此追加 I/J ...

---

## Part 3 — Discussion Workflow

讨论一个方向时:
1. 在该方向的 `Discussion log` 段下追加 `[round N: ...]` 块
2. 关键决策(yes/no/defer/reframe)写入该方向的 `临时结论`
3. 如果讨论触及多方向,在被触及方向的 log 中加 cross-ref
4. 讨论结束后,该方向的"临时结论"决定最终去向:
   - **进 active blueprint**:启动 `/blueprint` 流程 + 移走相关讨论摘要
   - **进 evidence-vision synthesis**:更新 L0-L11 status / 候选 blueprint 列表
   - **deferred**:留在本文档,标 `defer to future strategic decision`
   - **abandoned**:像 v0.1.4 一样,记录原因 + 关闭

讨论收尾后,本文档可以:
- 整体 archive 到 `docs/blueprints/archive/`(如果讨论产出多个 blueprint)
- 整体 delete(如果讨论结论都是 defer / abandoned)
- 整体保留作 reference(如果讨论本身是 long-lived design context)

由用户决定。

---

## Part 4 — 决策日志(全局)

记录 cross-direction 决策、原则确认、新发现 invariants 等。

### Decision 1 (2026-05-02, A round 1) — Application-first for new runtime capabilities; strangler migration for SDK

**触发:** A round 1 讨论中,用户提出 SDK replay 当前形态不应回撤(会破坏 v0.1.x preview surface 且无真用户反馈),但也不应继续在 SDK 加深(会让 SDK 变 runtime authority)。

**决策:**
1. **Freeze 现 `SDKStore.replay_with_patch(...)` surface** — 只做 bug fix / compat polish,不加新操作
2. **新能力 application-first** — Check / EvaluationOverlay / replay persistence / rule variant execution / proof diagnostics / fact overlay 等,先在 `kernel.application` 定义 request/result DTO,SDK wrapper 推到第二步
3. **后期 strangler migration** — 把 `sdk_replay_with_patch` orchestration 下沉到 application,SDK wrapper 保 method signature 不变;不是 v0.1.x scope,是未来专项

**对本文档 A-H 方向的影响:** 所有方向的 discussion 现在都默认在 **application protocol 层**展开,SDK wrapper 是 deferred concern。

**已落 cross-session memory:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`(下次 session 自动生效)

---

(后续决策追加)
