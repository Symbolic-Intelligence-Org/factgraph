# Lessons Learned from v0.1.x Design Probe (2026-04-30 .. 2026-05-03)

- **Status:** working / consolidated lessons
- **Authority:** non-authoritative;canonical 经验记录在 cross-session memory 文件中,本 doc 是 in-tree 镜像 + 跨条目串联

42 小时的 design probe(v0.1.1 rule-replay → v0.1.2 module-IR → v0.1.3 disable-condition → v0.1.4 abandoned param-override → 2026-05-03 reset)产出的 cross-cutting 经验,按主题分组。

## 1. 设计哲学层(都 reset-survival,redesign 直接复用)

### 1.1 B'' pivot 是不可破的 invariant

**Lesson:** rule operable + evidence read-only。所有"用户对 evidence 做什么"的需求都要推到 rule 层(replay variant)而非 evidence 层。

**Source:** `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md`

**Why redesign matters:** 用户的"改条件 + 改 facts + 重评 + 拿合规结果"需求,**改 facts 部分**仍属 fact 层 overlay(不是 evidence mutation),仍 B'' 兼容;**改 evidence node** 是不允许的方向。

### 1.2 Identity = owner/path-scoped, NOT pure content hash

**Lesson:** `mod_v1:<sha>` 不能纯按 atom content hash;必须包含 owner kind/id/version + branch/atom position。否则两个不同 rule 中同形 atom 会被错误 merge 成同一 module identity。

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_identity_design.md`

**Why redesign matters:** 任何 module / condition / evidence node identity 设计都要应用这个原则。`shared_id` 字段是显式表达跨 rule 共享,默认不 implicit merge。

### 1.3 Invariant-sensitive state 必须递归 immutable + 跨边界硬化

**Lesson:** content-derived id 一旦计算,所有可达 mutation 路径都要封死。`@dataclass(frozen=True)` 只锁顶层赋值,inner list/dict 仍可 mutate。defense in depth:存储层 frozen + 跨 SDK 边界包 MappingProxyType + 跨边界后再次封锁。

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_invariant_defense_in_depth.md`

**v0.1.2 实例:** ConditionModule.atom 第一次 fix 只防 input/output 别名,P1 round-2 才意识到 `body.branches[X][Y].atom[Z].append(...)` 仍能直接 mutate。最终用 `_FrozenList(tuple)` marker subclass,递归 immutable,lowering 时 `_thaw` 还原。

**Why redesign matters:** 任何 protocol DTO 必须真的递归 immutable;不要被 frozen=True 的表面安全骗到。

## 2. 架构层(都 reset 后 supersede / 强化)

### 2.1 Application 是 runtime authority,SDK 是 ergonomic shell

**Lesson:** 新 capability 必须在 `kernel/application/protocol/` 起 DTO,纯函数 `(request, store) → result` 在 `kernel/application/<capability>_runtime.py`,SDK shell 只 wrapper。**不允许新 substrate 长在 `kernel/sdk/`**。

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`(reset 后已 hardened,无 strangler 退路)

**v0.1.x 实例:** rule-replay 整个 substrate 都长在 `src/kernel/sdk/replay.py`(203 行)+ `replay_runtime.py`,事后判断这是 layer 错位。Reset 选了重做不选迁移。

**Why redesign matters:** Step 0 spike 必须明确回答 "this capability 的 application DTO 形状是什么?"答不出 → 不 scope。

### 2.2 SDK 不应继续加深(在 OSS preview 没有用户承诺)

**Lesson:** "Preview" 按定义没承诺界面,可以推倒重来。"无真用户反馈信号"是支持推倒的论据,**不**是反对的论据。Strangler migration 框架在没用户的情况下不成立。

**Source:** `40_design-discussion-A-with-decision-1.md` Decision 1(原 framing)+ 2026-05-03 reset 决策(supersede)

**Why redesign matters:** 不要为了"已经投入"而保留错位 surface。reset 早做不晚做。

### 2.3 Public API surface 默认 narrow,不为 consistency 扩展

**Lesson:** OSS preview line 默认 contained;新机制走 internal/private 路径;只有当现有用户 UX 明确需要时才扩 SDK public surface。

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_narrow_public_api.md`

**v0.1.x 实例:** v0.1.3 disable_condition 实现时,我推荐扩 `SDKStore.evaluate(disabled_locators=...)` kwarg "for consistency";用户改成内部 `_evaluate_with_overlay`-style 路径,不出 public surface。事后证明用户的选择对 — 那个 kwarg 反正 reset 时也要 strip。

**Why redesign matters:** application protocol DTO 是 internal monorepo 接口,不是 OSS public surface;SDK shell 仅在用户 UX 真正需要时再加。

## 3. 实操陷阱层

### 3.1 Candidate 抽象会丢失 body-only 变量信息

**Lesson:** `_builders.py:39,90` 用 head_vars 构造 candidate payload + 按 candidate_key dedupe。**body-only 变量不在 candidate 里,过滤 CandidateSet 不可靠**。

**Source:** `40_design-discussion-A-with-decision-1.md` A round 1(用户源码 verify)

**Why redesign matters:** Check operation 实现必须 hook 在 native where evaluator 的 final bindings / `BindingSupportCapture` 层,在 candidate 构造之前。同样原则适用于任何"对 binding 做事"的 capability。

### 3.2 不要 inject initial environment

**Lesson:** `where_eval.py:181` 每 branch 从 `envs=[{}]` 起,变量由 atom 顺序自然绑定。inject `$x = some_value` 会让 branch 即使没产出 $x 也"假装"通过。MVP 必须 evaluate 完整 body 后过滤 final bindings。

**Source:** `40_design-discussion-A-with-decision-1.md` A round 1

**Why redesign matters:** 任何"给定 binding 做 boolean check"的 capability 不能用 env injection 实现;必须 enumerate final bindings 后做 subset match。

### 3.3 candidate_id ≠ candidate_key (cross-run identity 用 _key)

**Lesson:** `candidate_id = compute_candidate_id_v2(run_id, ...)` —— 包含 run_id,**不**跨 run 稳定。`candidate_key` 是 content key,基于 derivation_id / version / kind / target / payload,跨 run 稳定。replay diff 必须用 `candidate_key`。

**Source:** v0.1.1 review-driven fix(用户在 review 中 catch);archived blueprint `2026-05-01_rule-replay-with-evidence-diff.md` outcome §10

**Why redesign matters:** 任何"两次 evaluate 比对 candidate"的 capability 都要用 `candidate_key`,**不**用 `candidate_id`。

### 3.4 derivation 形态陷阱

**Lesson:** 
- compiler 接受 `target` + `head_vars` 二元 spec
- `head: {kind: select, vars: [...]}` 不是 compiler 接受的形态
- `where == body`(若都给)
- head_vars arity 必须与 target 的 pred arity 匹配,否则 WhereValidationError(unit test 难 catch,只有 end-to-end 跑出来)

**Source:** v0.1.1 review-driven fixes;archived blueprint outcome notes

**Why redesign matters:** 任何"造 derivation payload"的代码都要按 binary spec 走;demo notebook 必须 nbconvert --execute。

### 3.5 4 类 "param" 语义不可合并

**Lesson:** 用户最初想的"param_override"实际是 4 类不同 lane:
1. literal/term replace(本质是 constrained replace,等于现有 replace_atom)
2. condition_weights override(certainty/explain lane,非 where execution)
3. ProbLog branch probabilities(adapter-local)
4. PyReason interval bounds(adapter-local)

强行合一会造成假抽象。

**Source:** `50_archived-blueprints/2026-05-02_v0.1.4-param-override.md`(abandoned negative-result)

**Why redesign matters:** 看到"override"或"parameter"类的命名时先问"这是几类?",分别走 4 条 lane(或忽略其中无用的)。Step 0 spike 的 negative result 是合法 close-out,不是失败。

### 3.6 cross-engine evidence 不可统一

**Lesson:** Souffle (proof tree) / PyReason (event log) / ProbLog (probability trace) 在语义层面不可统一。早在 2026-03-28 evidence-graph blueprint 就基于 real engine sample 撤回过 unified ProofNode tree。

**Source:** `30_drift-analysis-2026-05-02.md` §6.5

**Why redesign matters:** 如果 redesign 路线触及 cross-engine evidence,必须降级目标到 "side-by-side rendering" 而非 "semantic translation"。

## 4. 流程层

### 4.1 Step 0 spike 是流程的核心

**Lesson:** 在 implementing 之前的 Step 0 source-backed feasibility spike 是 catch 设计错位的关键(v0.1.4 abandonment 在 Step 0 就被 catch,没浪费实施轮)。Step 0 spike 必须明确回答可验证的问题,不能空对空。

**Source:** archived blueprints + `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_blueprint_workflow.md`

**Why redesign matters:** redesign 第一个 capability 起 blueprint 时,Step 0 必答:"这个 capability 的 application DTO 形状是什么?"答不出就停。

### 4.2 macOS+zsh+BSD-sed 5 个执行陷阱

**Lesson:** 跨 Claude session 的 namespace split / package rename / cross-pkg edit 容易踩到:
1. zsh `for f in $VAR` 不 word-split
2. BSD sed 不支持 `\b` word boundary
3. 跨包搬迁的相对 import 必须扫
4. `__init__.py` re-exports 必须扫
5. 模块级跨包 import 引入加载耦合

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_refactor_execution_traps.md`

**Why redesign matters:** 大型 refactor 之前先扫这 5 个陷阱。

### 4.3 Release branches sacred

**Lesson:** `v0.1-oss-prep` + `master` 是 sacred,不主动 merge,等用户显式 publish 决策。强 merge 是事故级。

**Source:** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_release_branch_invariants.md`

**Why redesign matters:** redesign 整个流程在 internal preview line 完成,不向 release base 流入。

### 4.4 No-filler-work invariant

**Lesson:** 当 strategic 决策点(easy candidates 耗尽)出现时,继续 propose 维护 / 治理 / 设计 doc 会创造"还在前进"的假象。承认 strategic pause 比强行找 next patch 健康。

**Source:** Decision after design-landscape synthesis(2026-05-02 chat 段)

**Why redesign matters:** redesign 启动时也要诚实:不要为了"开始做事"立 blueprint;先确认目标 capability 真有客户/使用价值。

## 5. Cross-session memory pointer

完整 memory 在 `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/`(repo 外)。reset-survival 列表:

- `MEMORY.md`(索引)
- `feedback_blueprint_workflow.md`
- `feedback_hook_restriction.md`
- `feedback_identity_design.md`
- `feedback_invariant_defense_in_depth.md`
- `feedback_narrow_public_api.md`
- `feedback_refactor_execution_traps.md`
- `project_atom_key_format.md`
- `project_application_first_runtime_authority.md`(reset 后 hardened)
- `project_extraction_p0_p1_status.md`
- `project_release_branch_invariants.md`
- `user_profile.md`
