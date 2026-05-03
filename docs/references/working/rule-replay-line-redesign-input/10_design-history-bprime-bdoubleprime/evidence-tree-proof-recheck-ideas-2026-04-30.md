# Operational Evidence Tree / Evaluation Overlay 设计备忘

最后更新: 2026-04-30

> 本文是设计 ideas / context 记录,不是当前实现 contract。
> 若进入实现,按仓库规则应先创建 active blueprint,并在实现后更新相关 module docs。

## 0. 一句话结论

目标不是“编辑 evidence tree”,而是:

```text
用 evidence tree 定位旧证明路径上的可操作支撑点,
生成 EvaluationOverlay 或 commit command,
在 overlay 下重新运行权威推理,
同时用旧 evidence tree 的 proof frames 做局部复核,
最后输出 before/after diff 和失效解释。
```

更精确地说:

```text
evidence tree 是结果快照;
overlay 是新的推理上下文;
proof-frame rechecker 是旧证明路径的局部诊断器;
full evaluate 是新结论的唯一权威来源;
diff 是用户真正消费的产品输出。
```

## 1. 设计定位

### 1.1 产品定位

这套设计更适合定位为:

```text
Decision Assurance / 可审计决策推理工作台
```

而不是:

- 又一个 explainability dashboard
- 又一个规则引擎
- 又一个 notebook helper
- 通用知识图谱编辑器

核心价值:

- 高风险决策可解释、可质询、可模拟。
- expert 可以从 evidence path 上定位问题支撑点。
- what-if 能显示旧证明哪里失效,以及新结论是否仍成立。
- expert override / correction / rejection 能结构化记录。
- audit package 能导出完整决策证据。

适合场景:

- 金融授信、AML、fraud review、模型风险审查。
- 保险理赔、核保、反欺诈。
- 医疗 prior authorization、支付审核。
- 政府福利资格、风险评分。
- 供应商风险、合规例外审批。
- AI strategy threshold / model policy review。

### 1.2 与原 B 的关系

原 B 是 protocol-first intervention design:

```text
RuleIntervention
IntervenedDerivationEvaluateRequest
apply_intervention_request
```

本设计是 B':

```text
OperationalEvidenceTree
EvidenceNodeHandle
ActionRef
EvaluationOverlay
ProofFrameRechecker
CandidateDiff
ReviewRecord
```

B 是工程骨架;B' 是产品化形态。

继承 B 的原则:

- protocol-first
- application 是 runtime authority
- SDK 只是 ergonomic facade
- future engine 不应各自发明 `excluded_rules` 协议

超越 B 的部分:

- evidence tree 成为 user-facing review object
- tree node 可导出 typed handle
- overlay 成为复合 scenario/action 容器
- proof-frame recheck 利用旧推理路径解释“旧证明如何失效”
- DORA / regulatory demo 比抽象 admin/audit demo 更适合 headliner

## 2. 基本语义: Evidence Tree 不能被原地修改

Evidence tree 是一次已完成推理的结果快照。它表达:

```text
在原事实、原规则、原参数、原绑定下,
为什么 candidate 成立。
```

因此,当用户修改事实、规则、参数或条件时,不是“修改这棵 tree 后继续成立”,而是:

```text
old facts/rules/params + derivation
  -> evaluate
  -> candidate A
  -> evidence tree A

expert operation
  -> EvaluationOverlay

old facts/rules/params + overlay + same derivation
  -> re-evaluate
  -> candidate set B
  -> evidence tree B

compare A vs B
```

不要做:

```text
edit tree in place
patch proof node
mutate candidate by hand
```

推荐表述:

```text
Evidence-guided re-evaluation
Evidence-guided intervention
Operational evidence review
```

如果继续使用 `OperationalEvidenceTree` 这个名字,必须明确:

```text
OperationalEvidenceTree 不是可变 proof tree,
而是带 action targets / typed handles 的 immutable evidence tree wrapper。
```

## 3. 三个核心运行层

### 3.1 权威推理层

职责:

```text
facts + rules + overlay + derivation -> authoritative candidate set
```

它决定新世界里哪些 candidates 成立。任何新结论都必须来自这一层。

当前仓库语义中,这对应:

- `SDKStore.evaluate(...)`
- application `evaluate_derivation_plans(...)`
- core/native `evaluate_store(...)`
- future engine adapters

### 3.2 局部 proof-frame recheck 层

职责:

```text
old evidence tree + old bindings + overlay -> old proof path validity report
```

它只回答:

```text
旧证明路径在新 overlay 下还站得住吗?
如果站不住,最早/最关键失败点在哪里?
```

它不回答:

```text
新世界里所有 candidates 是什么?
是否存在替代 proof path?
是否有新 candidate 出现?
OR branch 是否换了一条?
RuleRef 递归是否产生新链路?
```

### 3.3 Diff / review 层

职责:

```text
before candidate/tree
+ local proof recheck report
+ after candidate/tree
-> review diff
```

它区分两件事:

```text
旧证明失效
结论失效
```

例子:

```text
Local recheck:
  old support path failed at temperature_threshold

Full re-evaluation:
  no replacement candidate found

Diff:
  candidate removed
```

另一种情况:

```text
Local recheck:
  old support path failed at temperature_threshold

Full re-evaluation:
  same candidate still exists via rule.manual_override

Diff:
  candidate unchanged, support path changed
```

这是产品价值很高的区别。

## 4. ProofFrame: “推理树余热”的实际载体

“推理树余热”不是神秘状态,而是上一轮推理已经记录好的:

- variable bindings
- fact witnesses
- condition expressions
- condition results
- rule call chain
- support digest / support kind
- assertion ids
- rule id / version / call-site key
- selected branch / atom key

这些信息可以被整理成 `ProofFrame`。

### 4.1 ProofFrame 示例

事实 frame:

```python
ProofFrame(
    frame_id="fact.temperature.room_a",
    kind="assertion_fact",
    pred_id="room:temperature",
    e_ref="idref_v1:room:...",
    value=24,
    asrt_id="asrt_123",
    result=True,
    dependencies=(),
)
```

条件 frame:

```python
ProofFrame(
    frame_id="cond.temperature_threshold",
    kind="non_fact_check",
    expr=("gt", "$t", 20),
    binding={"$room": "room_a", "$t": 24},
    result=True,
    dependencies=("fact.temperature.room_a",),
    action_refs=(...),
)
```

RuleRef frame:

```python
ProofFrame(
    frame_id="rule_ref.warm_occupied_room.b0.a0",
    kind="rule_ref",
    rule_id="rule.warm_occupied_room",
    version="1.0.0",
    call_site_key="b0.a0:ruleref",
    result=True,
    dependencies=("cond.temperature_threshold", "fact.occupied.room_a"),
)
```

Candidate frame:

```python
ProofFrame(
    frame_id="candidate.room_a.status.comfortable",
    kind="candidate_result",
    candidate_id="...",
    candidate_key="...",
    result=True,
    dependencies=("rule_ref.warm_occupied_room.b0.a0",),
)
```

### 4.2 ProofFrame 与 raw evidence tree 的关系

当前 raw tree 仍应保持为 evidence DTO。

ProofFrame 可以是:

- raw tree node 的 normalized wrapper
- derived view
- SDK wrapper 内部结构
- recheck runtime 的输入结构

不要强行把所有 proof-frame 字段塞进 raw DTO 的 public contract,除非 blueprint 明确冻结。

## 5. ProofFrameRechecker: 局部复核器

### 5.1 它是什么

`ProofFrameRechecker` 是一个小型解释复核器:

```text
old proof frames + overlay -> RecheckReport
```

它不是原推理引擎。
它也不是新的完整推理引擎。

它不做:

- join
- variable binding search
- rule recursion discovery
- candidate generation
- fixed-point evaluation
- OR branch discovery
- engine-native provenance replay

它只做:

- fact frame recheck
- condition frame re-evaluation
- rule frame disabled check
- children validity aggregation
- invalidation reason generation

一句话:

```text
解释用小解释器,不是推理用大引擎。
```

更准确的专业命名:

```text
proof-frame rechecker
proof checker
justification rechecker
dependency invalidation checker
```

不要把它定位成:

```text
secondary inference engine
```

因为它不能、也不应该决定新世界里的 truth。它只能复核旧证明路径。

专业边界:

```text
主推理引擎:
  facts + rules + overlay + derivation -> authoritative candidates

ProofFrameRechecker:
  old evidence tree + old bindings + overlay -> old proof path validity report
```

如果 rechecker 开始输出新 candidate set、replacement proof 或全局 truth,它就变成了第二套推理引擎,会和主引擎发生语义漂移。

### 5.2 为什么不用原推理引擎

原推理引擎做全局搜索:

```text
找所有事实组合
匹配所有 rule body
处理 RuleRef / OR branch / recursion
生成 candidates
```

ProofFrameRechecker 已经有旧推理留下的 binding:

```text
$room = room_a
$t = 24
```

它只需要算:

```text
24 > 30 ?
occupied(room_a) 仍然 true ?
asrt_id 是否被 overlay 替换/撤销 ?
rule_id@version 是否被 overlay disable ?
```

所以调用完整推理引擎过重,而且会改变语义:完整引擎可能找到替代路径;局部复核只关心旧路径是否仍有效。

### 5.3 伪代码

```python
class ProofFrameRechecker:
    def recheck(self, tree, overlay) -> RecheckReport:
        results = {}

        for frame in tree.post_order():
            if frame.kind == "assertion_fact":
                results[frame.frame_id] = self._recheck_fact(frame, overlay)

            elif frame.kind == "non_fact_check":
                results[frame.frame_id] = self._recheck_condition(frame, overlay, results)

            elif frame.kind == "rule_ref":
                results[frame.frame_id] = self._recheck_rule_ref(frame, overlay, results)

            elif frame.kind == "candidate_result":
                results[frame.frame_id] = self._aggregate(frame, results)

            else:
                results[frame.frame_id] = UnknownRequiresFullEval(...)

        return RecheckReport(results)
```

Fact recheck:

```python
def _recheck_fact(frame, overlay):
    override = overlay.find_fact_override(frame.asrt_id)

    if override is None:
        return StillValid(reason="same assertion witness")

    if override.new_value == frame.value:
        return StillValid(reason="override keeps same value")

    return Invalidated(
        reason="fact value overridden",
        old_value=frame.value,
        new_value=override.new_value,
    )
```

Condition recheck:

```python
def _recheck_condition(frame, overlay, child_results):
    if any(not child_results[d].valid for d in frame.dependencies):
        return Invalidated(
            reason="dependency invalidated",
            dependencies=[
                d for d in frame.dependencies
                if not child_results[d].valid
            ],
        )

    expr = overlay.rewrite_expr(frame.expr)
    binding = overlay.rewrite_binding(frame.binding)

    new_result = eval_condition(expr, binding)

    if new_result == frame.result:
        return StillValid(
            reason="condition result unchanged",
            old_result=frame.result,
            new_result=new_result,
        )

    return Invalidated(
        reason="condition result changed",
        old_expr=frame.expr,
        new_expr=expr,
        old_result=frame.result,
        new_result=new_result,
    )
```

RuleRef recheck:

```python
def _recheck_rule_ref(frame, overlay, child_results):
    if overlay.disables_rule(frame.rule_id, frame.version):
        return Invalidated(
            reason="rule disabled by overlay",
            rule_id=frame.rule_id,
            version=frame.version,
        )

    return aggregate_children(frame, child_results)
```

### 5.4 RecheckResult 状态

建议最小状态:

```text
still_valid
invalidated
unknown_requires_full_eval
unsupported
```

不要把 unknown 当 false。

unknown 的含义:

```text
局部复核器无法判断旧 frame 是否仍成立,
需要 full evaluate 的结果来解释。
```

常见 unknown:

- engine-native proof leaf
- ProbLog / PyReason provenance node
- unsupported expression type
- missing binding
- rule recursion boundary
- overlay operation not supported by rechecker

### 5.5 专业先例与设计依据

这个模式不是随意增加一套“次级推理引擎”。专业系统里常见的做法是:

```text
复杂 solver / engine 负责搜索和生成结果;
更小、更保守、更容易审计的 checker 负责检查 proof / justification。
```

相近先例:

1. SAT / SMT proof checking
   - SAT/SMT solver 负责搜索、求解、生成 proof certificate。
   - proof checker 负责验证 certificate 是否成立。
   - Alethe / LFSC / SMTCoq / DRAT checker 这类生态都体现了 solver 与 checker 分离。

2. Truth Maintenance System / Justification Network
   - 系统维护 belief 与 justification 的依赖关系。
   - 当假设或支撑变化时,沿 justification graph 标记哪些 belief 失效。
   - Drools TMS 的 logical insertion / justification 也有类似思想:支持条件不再成立时,logical fact 会被撤回或重新判定。

3. Build systems / incremental invalidation
   - build graph 不等同于 compiler。
   - dependency graph 可以判断哪些旧 artifact 失效,但最终 artifact 仍要由 compiler/build action 重新生成。

对应到本设计:

```text
evaluate_store / engine
  = solver / compiler / authoritative inference engine

candidate_evidence_tree + ProofFrame
  = proof certificate / justification graph / dependency graph

ProofFrameRechecker
  = proof checker / invalidation checker / diagnostic verifier
```

关键原则:

```text
checker 可以解释旧证明为什么失效;
checker 不能决定新结论是否成立。
```

### 5.6 严肃失败模式

局部 recheck 的失败通常来自把它误当权威推理。必须在设计和 UI 中防止这些误读。

#### 5.6.1 旧证明失效,但结论仍成立

旧路径:

```text
comfort_ok(room_a)
└─ rule.warm_if_temperature
   └─ temperature > 20 => true
```

overlay 后:

```text
temperature > 30 => false
```

local recheck 只能说:

```text
old support path invalidated
```

full evaluate 可能发现:

```text
comfort_ok(room_a)
└─ rule.manual_override_room
   └─ expert_override(room_a) = true
```

正确输出:

```text
old support path invalidated
candidate still exists via alternate support
```

错误输出:

```text
candidate removed
```

#### 5.6.2 Evidence tree 只记录成功路径

当前 candidate evidence tree 是 candidate-first / support-path-first。它解释为什么某个 candidate 成立,不是完整记录所有失败路径。

它不能直接回答:

```text
改了参数后是否有另一个 OR branch 成立?
是否有另一个 fact witness 可用?
是否另一个 RuleRef child path 可用?
```

#### 5.6.3 OR branch / source-order wins

旧 tree 可能记录 adopted branch:

```text
branch 0 satisfied, selected by source-order wins
```

overlay 后:

```text
branch 0 invalidated
branch 1 satisfied
```

local recheck 只能说:

```text
old selected branch invalidated
```

不能说:

```text
rule output invalidated
```

#### 5.6.4 RuleRef / recursive support 不完整

遇到以下情况必须返回 `unknown_requires_full_eval`:

- legacy flat `rule_refs`
- `child_support_unavailable`
- `artifact_missing`
- `recursion_boundary`
- depth limit
- cycle boundary

#### 5.6.5 Fact override 与 active/chosen view

事实节点通常指向旧 witness 的 `asrt_id`,但推理使用 active projected facts / chosen view。

因此:

```text
override asrt_id=a1
```

不一定等同于:

```text
override active value for pred/e_ref
```

MVP 必须锁清楚 fact overlay 语义:

```text
override old witness only
```

或:

```text
override active predicate value for this evaluation
```

如果不锁,what-if 会不可信。

#### 5.6.6 Negation / absence / missing facts

如果规则依赖:

```text
Not(...)
absence of incident
no_recent_default
```

旧 success tree 不一定包含足够信息证明 absence。新增一个 fact 可能让旧证明失效,但 local recheck 未必能发现。

这类情况第一版应返回:

```text
unsupported_for_local_recheck
```

#### 5.6.7 Engine-specific provenance

native tree、Souffle witness、ProbLog provenance、PyReason timeline 不是同一个 carrier。

MVP 建议:

```text
native_binding_v1:
  local recheck eligible

souffle_witness_v1:
  partial / deferred

problog_provenance_v1, pyreason_provenance_v1:
  no local boolean recheck in v0.1.1

degraded support:
  no local recheck
```

#### 5.6.8 Candidate identity / support identity

re-evaluate 后可能:

- `candidate_id` 变了
- `candidate_key` 相同
- support_digest 变了
- payload 相同但 support path 不同
- confidence/probability 变了

diff 应尽量按 `candidate_key`,不是 `candidate_id`。

#### 5.6.9 Rule disable scope

`RuleDisable(rule_id, version)` 应在本次 overlay evaluation 中禁用该 rule version 的所有 call sites,不是只禁用当前 tree 上可见的单个节点。

UI / notebook 必须明确:

```text
This overlay disables rule.x@1.0.0 for this evaluation across all call sites.
```

### 5.7 工程防线

必须锁定:

```text
local recheck never decides candidate existence
unknown is not false
unsupported is not invalidated
full evaluate is mandatory before final diff
diff uses candidate_key where possible
local recheck report and full evaluation result are displayed separately
```

推荐输出结构:

```text
Local proof recheck:
  old support path invalidated at condition X

Full re-evaluation:
  candidate still exists via alternate support

Decision diff:
  candidate unchanged, support path changed
```

## 6. EvaluationOverlay

### 6.1 它是什么

`EvaluationOverlay` 是一次非持久 scenario / what-if / review execution context。

它不应:

- 直接写 ledger
- 改变原 rule asset
- 把假设伪装成事实
- 成为 audit package live action owner

它应该:

- 被 application runtime 识别
- 可由 SDK wrapper 生成
- 可序列化
- 可记录 actor / reason
- 可传给 full evaluate
- 可传给 ProofFrameRechecker

### 6.2 建议形态

```python
EvaluationOverlay(
    actions=(
        FactValueOverride(...),
        RuleDisable(...),
        RuleParameterOverride(...),  # deferred
        ConditionOverride(...),      # deferred / high risk
    ),
    actor="expert@example.com",
    reason="manual review before approval",
)
```

### 6.3 v0.1.1 action set

建议 v0.1.1 只支持:

```text
FactValueOverride
RuleDisable
```

理由:

- fact-only 的 headliner 偏弱。
- rule disable 是最小 reasoning-path challenge。
- rule disable 不需要 condition AST replacement。
- parameter override 需要 Rule DSL 新字段,应 deferred。

### 6.4 FactValueOverride

语义:

```text
在 overlay 下,某个 assertion_fact 的值被假设为新值。
不写 ledger。
```

最小字段:

```python
FactValueOverride(
    asrt_id="asrt_123",
    pred_id="room:temperature",
    e_ref="idref_v1:room:...",
    old_value=24,
    new_value=30,
    note="expert correction",
)
```

注意:

- overlay 应该可以按 `asrt_id` 定位旧 witness。
- full evaluate 层要定义如何把 fact override 投影到 active facts。
- 正式 commit 走 separate command: retract + set/add。

### 6.5 RuleDisable

语义:

```text
在 overlay 下,某个 rule_id@version 不参与 RuleRef 解析/执行。
不改变 registry。
```

最小字段:

```python
RuleDisable(
    rule_id="rule.warm_occupied_room",
    version="1.0.0",
    note="not applicable in this review",
)
```

规则:

- 必须带 `version`。
- disable 后无 candidate 是合法结果。
- rule 存在但本次未触达时,可返回 `unused_overlay` metadata。
- unknown rule_id@version 应 hard error,避免用户以为 disable 生效。

### 6.6 多个修改的语义

多个条件或支撑点同时修改是正常场景,应通过同一个 `EvaluationOverlay` 表达。

推荐语义:

```text
EvaluationOverlay 是一组无序、声明式、同时生效的 actions。
Local recheck 在整个 overlay 下复核旧 proof path。
Full evaluate 在整个 overlay 下重新推理。
Diff 比较 before 和 after。
```

示例:

```python
overlay = EvaluationOverlay(
    actions=(
        FactValueOverride(asrt_id="a1", new_value=30),
        RuleDisable(rule_id="rule.risk_score", version="1.0.0"),
        FactValueOverride(asrt_id="a2", new_value=False),
    ),
    actor="expert@example.com",
    reason="committee scenario review",
)
```

不要默认按 action 顺序逐步应用。overlay 不是脚本。

MVP 只做 combined effect:

```text
所有 actions 同时生效后,旧 proof path 哪里失效?
所有 actions 同时生效后,full evaluate 的 after candidate set 是什么?
```

不要在 MVP 做 marginal attribution:

```text
每个 action 单独贡献多少?
哪个 action 是最小致因集?
```

这属于后续 sensitivity analysis / attribution。

### 6.7 多修改冲突检测

overlay validate 阶段需要发现冲突。

MVP 支持 fact override + rule disable 时,至少检查:

- 同一个 `asrt_id` 出现多个不同 override。
- 同一个 `rule_id@version` 出现重复/冲突 action。
- action target 缺少必要字段。
- action target 与当前 support/registry 完全不匹配。

后续加入 parameter / condition 后再扩展:

- 同一个 parameter 多个不同 value。
- condition override 与 parameter override 作用到同一 condition。
- disable rule 与 force-enable rule 冲突。

### 6.8 为什么仍用 EvaluationOverlay,而不是直接改 tree

即使 SDK 体验上写成:

```python
tree.find_fact(Room.temperature, room_a).replace_value(30)
tree.find_rule("rule.warm", version="1.0.0").disable()
```

底层仍应生成 overlay actions。

原因:

1. 多个修改需要统一 scenario 容器。

   ```text
   同一组 actions 同时生效;
   尚未写入 ledger;
   可撤销、可比较、可记录。
   ```

2. evidence tree 是旧结果,不是新输入。

   原 tree 中的:

   ```text
   temperature > 20 => true
   ```

   不应被原地改成:

   ```text
   temperature > 30 => false
   ```

   正确模型是:

   ```text
   old tree remains immutable
   overlay records proposed changes
   local recheck reports old proof invalidation
   full evaluate produces new result/tree
   ```

3. overlay 是可序列化、可审计的 review intent。

   audit / ReviewRecord 应记录:

   ```text
   old evidence tree
   overlay
   local recheck report
   after evaluate result
   decision
   ```

   而不是记录“某个 Python tree object 被改过”。

4. overlay 是 rechecker 和 full evaluate 的共同输入。

   ```text
   ProofFrameRechecker consumes overlay
   authoritative inference consumes overlay
   CandidateDiff consumes overlay metadata
   ```

5. raw evidence tree 的审计完整性必须保持。

推荐 mental model:

```text
tree = old proof
overlay = proposed changes
recheck = old proof under proposed changes
evaluate = new candidates / new proof
diff = product answer
```

### 6.9 RuleParameterOverride deferred

不要在 v0.1.1 ship。

原因:

- 需要 Rule DSL 支持显式 parameter declaration。
- 需要 compiled payload 支持 parameter metadata。
- 需要 tree 将 condition frame 映射到 parameter handle。
- 需要 overlay value type validation。

详见第 8 节。

## 7. Full evaluate 在 overlay 下如何执行

### 7.1 v0.1.1 推荐执行模型

不要做 pre-rewrite store。
不要做 audit package sandbox fork。
不要引入通用 engine hook 框架。

建议 v0.1.1 native-only narrow hooks:

```text
FactValueOverride:
  evaluation-time projected fact overlay

RuleDisable:
  RuleRef substrate 在 resolve/evaluate rule_id@version 前检查 overlay
```

即:

```text
native evaluate_store
  -> project active facts
  -> apply overlay fact projection for evaluation only
  -> evaluate where / RuleRef
  -> RuleRef substrate checks overlay disabled rules
  -> produce candidate set
```

### 7.2 为什么不是 plan-time patch

“plan-time patch”听起来干净,但当前 native 的关键执行点不只是 compiled derivation plan:

- RuleRef 是在 `ruleref_substrate` 中递归展开。
- disable rule 的真实目标是 RuleRef resolve/evaluate 链路。
- OR branch、nested RuleRef、memo/cycle 都在 substrate 层。

因此 rule disable 不能只 patch derivation plan。

### 7.3 为什么不是 pre-rewrite store

pre-rewrite store 接近 sandbox fork:

- 容易滑向 C。
- 要模拟 chosen view / retract / identity materialization。
- 大 store 成本高。
- 很容易让用户误解 overlay 写入了 ledger。

### 7.4 future engines

v0.1.1 不承诺 full cross-engine parity。

未来:

- native: first-class overlay support
- Souffle: 可以在 package/export rewrite 或 adapter 层过滤
- ProbLog/PyReason: 可能需要 engine-specific overlay adapter
- unsupported engine: overlay evaluate 明确 unsupported,或只提供 local recheck / candidate-level actions

### 7.5 跨引擎 proof-frame recheck 策略

不同引擎不应被迫共享同一种内部 `ProofFrame`。

推荐分层:

```text
Engine-native provenance / support carrier
  -> Engine-specific ProofFrameAdapter
  -> common RecheckReport
```

不要做:

```text
native / Souffle / ProbLog / PyReason 全部强行转成同一种 ProofFrame
```

这会磨平 ProbLog / PyReason 的语义,导致不准确或只能输出假的 tree。

统一的应该是外层 report:

```python
RecheckReport(
    candidate_key="...",
    support_kind="native_binding_v1",
    engine="native",
    overall_status="still_valid | invalidated | unknown | unsupported | engine_specific",
    frame_results=(...),
    limitations=(...),
    engine_report=None,
)
```

每个 frame result 只表达可共用的最低语义:

```python
FrameRecheckResult(
    frame_ref="...",
    frame_kind="condition | fact | rule_ref | proof_leaf | temporal_event | ...",
    status="still_valid | invalidated | unknown | unsupported",
    old_value=...,
    new_value=...,
    reason="...",
)
```

推荐 adapter:

```text
NativeProofFrameAdapter
SouffleWitnessAdapter
ProbLogProvenanceAdapter
PyReasonTimelineAdapter
```

v0.1.1 推荐支持矩阵:

```text
native_binding_v1:
  real proof-frame recheck

souffle_witness_v1:
  best-effort if support artifact is native-compatible;
  otherwise unsupported

problog_provenance_v1:
  unsupported for local boolean recheck;
  full evaluate / probability diff only

pyreason_provenance_v1:
  unsupported for local boolean recheck;
  full evaluate / temporal annotation diff only

engine_no_witness_v1 / degraded:
  unsupported
```

### 7.6 用户层统一手感

用户不应学习四套流程。应统一成:

```python
candidates = sdk.evaluate(derivation, mode=...)

review = sdk.review(candidates[0])
tree = review.evidence_tree()

print(tree.to_text())
print(review.capabilities())

scenario = review.scenario(
    actor="expert@example.com",
    reason="what-if review",
)

scenario.replace_fact(...)
scenario.disable_rule("rule.x", version="1.0.0")

result = scenario.evaluate(derivation)

print(result.local_recheck.to_text())
print(result.diff.to_text())
```

一致的是 workflow:

```text
review -> inspect -> scenario -> evaluate -> diff
```

一致的是 objects:

```text
CandidateReview
EvidenceView / OperationalEvidenceTree
Scenario
EvaluationOverlay
ReviewResult
RecheckReport
CandidateDiff
```

不强行一致的是 internals:

```text
Native ProofFrame
Souffle tuple provenance
ProbLog mutually exclusive proofs / weighted formula provenance
PyReason temporal graph annotations
```

每个 review object 应提供 capability matrix:

```python
review.capabilities()
```

示例:

```python
{
    "evidence_view": "full",
    "local_recheck": "supported",
    "fact_override": "supported",
    "rule_disable": "supported",
    "parameter_override": "deferred",
}
```

ProbLog / PyReason 可返回:

```python
{
    "evidence_view": "provenance|timeline",
    "local_recheck": "unsupported",
    "fact_override": "full_evaluate_only",
    "rule_disable": "full_evaluate_only",
    "probability_or_temporal_diff": "supported",
}
```

如果用户尝试 unsupported action,错误必须明确:

```text
Local condition recheck is not supported for pyreason_provenance_v1.
Use scenario.evaluate(...) for full re-evaluation and temporal diff.
```

## 8. Parameter Handle 的更好设计

### 8.1 不推荐 `parameter_bindings={"condition": "b0.a2"}`

用户 API 不应暴露:

```python
parameters={"temperature_threshold": 20},
parameter_bindings={
    "temperature_threshold": {"condition": "b0.a2", "operator": ">"}
}
```

问题:

- `b0.a2` 是 compiler/debug 坐标,不是用户心智。
- 用户不知道从哪里获取。
- rule 重排后容易显得不稳定。
- 部分 rule 特殊定义会很扎眼。

### 8.2 推荐 Param object in expression

更好的用户 API:

```python
from kernel.sdk import Param

threshold = Param.int(
    "temperature_threshold",
    default=20,
    label="Comfort temperature threshold",
)

with vars("r", "t") as (r, t):
    warm_rule = Rule(
        id="rule.warm_occupied_room",
        version="1.0.0",
        select=[r],
        where=[
            Room(r),
            r.temperature == t,
            t > threshold,
            r.occupied == True,
        ],
        expose=True,
    )
```

用户只声明 parameter,不声明 binding。

compiler 自动生成:

```python
{
    "parameters": {
        "temperature_threshold": {
            "type": "int",
            "default": 20,
            "label": "Comfort temperature threshold",
        }
    },
    "parameter_uses": [
        {
            "parameter": "temperature_threshold",
            "atom_key": "b0.a2",
            "operator": ">",
            "value_role": "rhs",
            "internal_path": "$.where[2].rhs",
        }
    ],
}
```

这些是 compiled metadata,不是用户手写 API。

### 8.3 所有 Param 都必须自动绑定

推荐规则:

```text
Param 放进 where/head 表达式 -> compiler 自动绑定。
Param 声明了但未使用 -> compile error。
同名 Param 类型/default 不一致 -> compile error。
overlay override value 类型不匹配 -> evaluate error。
```

不推荐:

```text
自动把所有 literal 都变成 parameter。
```

原因:

- tree 会很吵。
- 用户不知道哪些是可调旋钮。
- 有些 literal 只是 rule constant,不应被 review UI 暴露。

原则:

```text
所有 Param 都自动绑定;
但不是所有 literal 都自动变 Param。
```

### 8.4 Optional Condition label

如果用户想给 condition 更业务化的名称,可以引入可选 `Condition` wrapper:

```python
from kernel.sdk import Condition

where=[
    Room(r),
    r.temperature == t,
    Condition(
        "warm_enough",
        t > threshold,
        label="Room is warm enough",
    ),
    r.occupied == True,
]
```

tree 显示:

```text
condition: Room is warm enough
expression: temperature > 20
parameter: temperature_threshold
```

这属于 Phase 3+。

## 9. SDK Product Surface

### 9.1 CandidateReview

MVP 语义:

```text
sdk.review(candidate)
  = pure view wrapper over candidate + sdk/store context
  != workflow session
  != persistent review record
  != scenario stack
```

推荐:

```python
candidates = sdk.evaluate(derivation)

review = sdk.review(candidates[0])
tree = review.evidence_tree()
summary = review.summary()
steps = review.steps()
```

`review.accept(...)` 可以是 `sdk.accept(candidate, ...)` 的糖。

`review.reject(...)` 不建议 v0.1.1 做持久语义;没有 ReviewRecord 前容易误导。

### 9.2 OperationalEvidenceTree Wrapper

raw tree 仍是 dict/DTO。

SDK wrapper:

```python
tree.facts()
tree.rules()
tree.conditions()
tree.parameters()
tree.find_fact(...)
tree.find_rule(...)
tree.find_condition(...)
tree.find_parameter(...)  # deferred until Param exists
tree.to_text()
tree.to_dict()
```

### 9.3 Node Handles

推荐:

```python
node.as_fact_handle()
node.as_rule_handle()
node.as_condition_handle()
node.as_parameter_handle()  # deferred
```

Fact handle:

```python
fact = tree.find_fact(Room.temperature, room_a)
overlay = fact.replace_value(30, mode="what_if").to_overlay()
new_asrt = fact.commit_replace(30, approved_by="expert")
```

Rule handle:

```python
rule = tree.find_rule("rule.warm_occupied_room", version="1.0.0")
overlay = rule.disable(mode="what_if").to_overlay()
```

Condition handle first version:

```python
condition = tree.conditions()[0]
condition.to_text()
condition.as_condition_handle()
```

No condition override in v0.1.1.

### 9.4 Evaluate with overlay

```python
overlay = fact.replace_value(30, mode="what_if").to_overlay()
local = tree.recheck_with_overlay(overlay)
after = sdk.evaluate_with_overlay(derivation, overlay=overlay)
diff = sdk.compare_review(before=review, local=local, after=after)
```

Potential convenience:

```python
scenario = fact.replace_value(30, mode="what_if")
result = scenario.evaluate(derivation)
```

But MVP should keep explicit primitives clear before adding fluent chains.

## 10. Diff Model

### 10.1 CandidateDiff

Compare by `candidate_key`, not just `candidate_id`.

Possible categories:

```text
added
removed
unchanged_same_support
unchanged_changed_support
changed_payload
unsupported_compare
```

### 10.2 ReviewDiff

Inputs:

```python
ReviewDiff(
    before_candidate=...,
    before_tree=...,
    local_recheck=...,
    after_candidates=...,
    after_trees=...,
)
```

Important product lines:

```text
old support path invalidated at condition X
candidate removed
candidate still exists via alternate support
candidate unchanged but support path changed
new candidate added
```

### 10.3 Example output

```text
Local recheck:
- old support path invalidated at condition temperature_threshold
- old: 24 > 20 => true
- new: 24 > 30 => false

Full re-evaluation:
- no replacement candidate found

Decision diff:
- removed room_a.status += "comfortable"
```

Alternate:

```text
Local recheck:
- old support path invalidated at condition temperature_threshold

Full re-evaluation:
- room_a.status += "comfortable" still exists
- new support uses rule.manual_override_room@1.0.0

Decision diff:
- candidate unchanged
- support path changed
```

## 11. MVP Scope Lock

### 11.1 v0.1.1 recommended

```text
CandidateReview pure wrapper
OperationalEvidenceTree SDK wrapper
typed handles for fact/rule/condition read-only
fact what-if overlay
fact commit_replace via existing retract + set/add
rule disable what-if overlay
local proof-frame recheck for supported frames
candidate/review diff
DORA demo extension
```

### 11.2 Explicitly deferred

```text
Rule parameter declaration
Parameter override
Condition override
Persistent ReviewRecord
audit-of-audit package
sandbox fork
full non-native parity
fluent scenario stack
workflow reject/shelve state
```

### 11.3 Why fact + rule disable

Fact-only is technically clean but product-thin.

Rule disable adds the minimum reasoning-path challenge:

```text
expert can say:
  this rule should not participate in this review
and immediately see:
  which candidates disappear or change support
```

This makes “operable evidence tree” credible without entering condition/parameter complexity.

## 12. Demo Recommendation

Do not create an abstract admin/audit demo as the primary narrative.

Extend:

```text
examples/03_dora_minimal_evidence_tree.ipynb
```

Proposed story:

```text
1. Define source-backed regulatory facts.
2. Define rule chain with RuleRef.
3. Define derivation that creates a candidate review finding.
4. Run evaluate.
5. Open CandidateReview and OperationalEvidenceTree before accept.
6. Expert identifies a source-backed fact issue.
7. Run fact what-if replacement.
8. Local proof recheck explains old proof invalidation.
9. Full re-evaluation gives authoritative after candidates.
10. Diff shows candidate removed/changed/unchanged support.
11. Optional commit_replace or accept.
12. Export audit package.
13. Read back evidence tree from audit package.
```

Add rule disable scenario:

```text
Expert disables one rule version in overlay.
Local recheck marks old RuleRef frame invalidated.
Full re-evaluate shows affected candidates.
```

## 13. Rejected Alternatives

### 13.1 SDK-only `excluded_rules`

Rejected:

```python
sdk.evaluate(derivation, excluded_rules=[...])
```

Reasons:

- SDK hook, not runtime contract.
- service / agent / RPC would need separate design.
- future engines would each invent parameter semantics.
- hides the broader overlay/action model.

### 13.2 Editing raw tree nodes

Rejected:

```python
tree_node.commit()
tree_node.disable_rule()
```

Reasons:

- raw tree must stay immutable explain DTO.
- audit/static must consume it offline.
- actions need Store/session/registry/permission context.

### 13.3 Audit package sandbox fork as MVP

Rejected as first live workflow:

- audit facts may not reconstruct Store fully.
- support artifacts / backrefs / provenance envelopes may be incomplete.
- memory cost high.
- commit_back needs audit-of-audit schema.

Can be revisited for post-hoc audit lab later.

### 13.4 Direct condition AST replacement

Rejected for early phases:

- high semantic risk
- hard to audit
- easy to bypass rule intent
- requires stable condition identity and expression compatibility

Prefer Param object + parameter override later.

## 14. Open Technical Questions

These should be locked in blueprint before implementation.

1. Exact DTO location:
   - `kernel.application.protocol.review`?
   - `kernel.application.protocol.overlay`?
   - separate `kernel.application.review_runtime`?

2. SDK review module shape:
   - `kernel.sdk.review`?
   - methods on `SDKStore` only?

3. Raw tree action refs:
   - add `action_refs` into raw tree nodes now?
   - or keep raw tree unchanged and let SDK wrapper derive handles?

4. Fact overlay semantics:
   - override by `asrt_id` only?
   - or by `(pred_id, e_ref, value args)`?
   - how to simulate chosen-view replacement?

5. Rule disable existence validation:
   - validate against runtime registry before evaluate?
   - validate lazily when RuleRef is encountered?
   - how to report unused disable?

6. Local recheck support matrix:
   - exact supported node kinds
   - exact supported comparison ops
   - behavior for OR branch / Body confidence

7. Candidate diff identity:
   - rely on `candidate_key`
   - define fallback for missing/invalid candidate_key

8. Audit export:
   - v0.1.1 no review_records?
   - if no ReviewRecord, do not expose persistent reject/shelve.

## 15. Implementation Guardrails

If implemented:

- Create active blueprint first.
- Keep blueprint in draft while exploring.
- Move to scoped before multi-file implementation.
- Update affected module docs after implementation:
  - `src/kernel/sdk/docs/`
  - `src/kernel/application/docs/`
  - `src/kernel/core/docs/`
  - `src/kernel/audit/docs/` if export/readback changes.
- Do not treat this file as current implementation truth.
- Do not archive related blueprint until code/docs/tests are aligned.

## 16. Final Design Statement

The design should be described as:

```text
Operational Evidence Review:

An immutable candidate evidence tree exposes typed proof frames and action targets.
SDK wrappers turn those targets into ergonomic handles.
Handles produce EvaluationOverlay actions or explicit commit commands.
Overlay evaluation re-runs the authoritative inference engine.
A small proof-frame rechecker uses the old tree's bindings and witnesses to explain
which parts of the old proof path were invalidated.
The product output is a review diff that separates old-proof invalidation from
new-world conclusion changes.
```

This preserves the integrity of evidence trees while making them practically operable for expert review.
