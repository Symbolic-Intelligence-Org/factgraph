# 可操作 Evidence Tree 设计上下文

最后更新: 2026-04-30

## 1. 背景与目标

本文件记录关于“可操作证据树 / Operational Evidence Tree / Evaluation Overlay”的设计理念、产品判断与工程诊断。

当前讨论的目标不是单纯把推理过程可视化，而是让 expert 在推理结果产生后，可以顺着 evidence tree 直接定位事实、规则、条件、参数等支撑点，并对这些支撑点执行安全的 review / what-if / commit 操作。

核心用户心智:

```text
定义 schema / facts / rules / derivation
  -> evaluate 得到 candidate
  -> candidate 附带或可生成 evidence tree
  -> expert 从 tree 上定位问题节点
  -> 节点生成 typed handle / action ref
  -> action ref 生成 EvaluationOverlay 或正式 commit action
  -> re-evaluate / compare / accept / export audit
```

这套机制的产品定位更接近 **Decision Assurance / 可审计决策推理工作台**，而不是普通 explainability 工具或新的规则引擎。它要回答的问题是:

- 这个结论为什么成立?
- 哪些事实、规则、条件、参数支撑了它?
- expert 对某个支撑点提出异议后，结论如何变化?
- 哪些修改只是 what-if，哪些修改正式写入 ledger / registry?
- 最终决策能否被审计、复盘、质询?

## 2. 核心设计判断

### 2.1 Tree 是 review surface，不是 mutable truth

Evidence tree 应保持为不可变、可序列化、可审计的 explain surface。它表达“为什么产生这个 candidate”，不应直接承载副作用。

不推荐:

```python
tree_node.commit()
tree_node.disable_rule()
tree_node.write_to_ledger()
```

原因:

- raw evidence tree 需要在 runtime / audit / static / notebook 中同构消费。
- audit package 需要可离线读取，不能依赖 live Store、session、registry 或权限上下文。
- tree node 如果直接有行为，会把 explain DTO 变成状态ful runtime object，破坏边界。

推荐:

```text
raw evidence tree node
  -> node_ref / action_ref / typed handle
  -> SDK wrapper method
  -> EvaluationOverlay or commit command
```

也就是说，用户可以感觉自己在操作 tree；工程上实际执行的是结构化 action descriptor / overlay。

### 2.2 Raw DTO 与 SDK wrapper 分离

推荐分层:

```text
core:
  candidate_evidence_tree / summary / narrative / steps
  pure explain substrate

application:
  EvaluationOverlay protocol
  action descriptors
  runtime authority

sdk:
  CandidateReview / OperationalEvidenceTree wrapper
  typed node handles
  notebook-friendly methods and rendering

audit:
  read-only package consumption
  optional export-time review snapshot
```

raw tree node 可以包含纯数据:

```python
{
    "node_kind": "assertion_fact",
    "node_ref": "...",
    "action_refs": [
        {
            "target_kind": "fact_assertion",
            "asrt_id": "...",
            "pred_id": "room:temperature",
            "allowed_ops": ["what_if_replace", "commit_replace"],
        }
    ],
}
```

SDK wrapper 可以提供顺手方法:

```python
review = sdk.review(candidate)
tree = review.evidence_tree()

temp = tree.find_fact(Room.temperature, room_a)
scenario = temp.replace_value(30, mode="what_if")
after = scenario.evaluate(comfort_derivation)
```

这里 `temp.replace_value(...)` 不直接改 raw tree，也不直接写 ledger。它生成 overlay 或 command。

### 2.3 EvaluationOverlay 是 what-if execution context

`EvaluationOverlay` 表达一次非持久 review / scenario / what-if 推理上下文。

它不应直接写 ledger，不应改变原规则资产，不应把假设伪装成真实事实。

推荐心智:

```python
overlay = EvaluationOverlay(
    actions=[
        FactValueOverride(...),
        RuleDisable(...),
        RuleParameterOverride(...),
    ],
    actor="expert@example.com",
    reason="manual review before approval",
)

after = sdk.evaluate_with_overlay(derivation, overlay=overlay)
diff = sdk.compare_candidates(before, after)
```

overlay 的作用是让 expert 看到:

- 如果某个事实改成另一个值，结论是否变化?
- 如果某条规则不参与，哪些 candidates 消失?
- 如果某个阈值从 20 改成 30，哪些条件失败?
- 如果某个条件被人工 override，审计记录应该如何标注?

overlay 的输出应保持可解释: 重新 evaluate 后产生新的 candidate set、新的 evidence surface，以及 before / after diff。

## 3. 操作对象模型

可操作 evidence tree 的关键不是让节点“就是原始 Python object”，而是让节点能导出与用户定义对象兼容的 typed handle。

### 3.1 Candidate Handle

用于接受、拒绝、搁置、比较 candidate。

推荐 SDK:

```python
review = sdk.review(candidate)
review.accept(approved_by="alice", note="checked")
review.reject(reason="source mismatch")
```

底层应继续复用既有 candidate / accept 语义，不把 accept 行为塞进 raw tree。

### 3.2 Fact Handle

来源: `assertion_fact` 节点。

可支持:

- what-if 替换事实值
- 正式 retract + set / add
- 查看 assertion detail / source metadata

推荐 SDK:

```python
fact = tree.find_fact(Room.temperature, room_a)

overlay = fact.replace_value(30, mode="what_if").to_overlay()
after = sdk.evaluate_with_overlay(derivation, overlay=overlay)

new_asrt_id = fact.commit_replace(30, approved_by="expert")
```

必须区分:

```text
replace_value(..., mode="what_if")
  -> overlay, 不改 ledger

commit_replace(...)
  -> retract + set, 正式写 ledger
```

### 3.3 Rule Handle

来源: `rule_ref` / rule-chain node。

可支持:

- what-if 禁用 rule version
- registry / authoring 层禁用 rule version
- 查看 rule payload / condition summary

推荐对象 key:

```text
rule_id + version
```

不要只用 `rule_id`。当前 RuleRef substrate 的真实定位依赖 `(rule_id, version)`，且同一 rule 可能多次出现在不同 branch / call site。

推荐 SDK:

```python
rule = tree.find_rule("rule.warm_occupied_room", version="1.0.0")

overlay = rule.disable(mode="what_if", note="not applicable").to_overlay()
after = sdk.evaluate_with_overlay(derivation, overlay=overlay)
```

### 3.4 Condition Handle

来源: `non_fact_check` / condition node。

这是高风险层，因为 condition 通常是 DSL lowering 后的 atom，当前稳定定位多依赖 `b{branch}.a{atom}` 位置 key。

不推荐第一版直接让用户编辑 condition AST。

推荐第一版只支持:

- 查看 condition
- 显示其 rule/call-site/atom key
- 从 condition 进入已声明 parameter

后续若支持 condition override，必须要求:

- reviewer
- reason
- scope
- expiry 或 review context
- tree 中显式显示 override assumption，不能伪装成普通事实

### 3.5 Parameter Handle

最适合 `temperature > 20` 改成 `temperature > 30` 这种场景。

推荐把可调阈值声明为 rule parameter，而不是直接替换 condition AST。

示意:

```python
warm_rule = Rule(
    id="rule.warm_occupied_room",
    version="1.0.0",
    select=[r],
    where=[
        Room(r),
        r.temperature == t,
        t > 20,
        r.occupied == True,
    ],
    expose=True,
    parameters={
        "temperature_threshold": 20,
    },
    parameter_bindings={
        "temperature_threshold": {
            "condition": "b0.a2",
            "operator": ">",
        },
    },
)
```

expert 操作:

```python
threshold = tree.find_parameter(
    rule_id="rule.warm_occupied_room",
    version="1.0.0",
    parameter="temperature_threshold",
)

overlay = threshold.override(30, note="expert threshold").to_overlay()
after = sdk.evaluate_with_overlay(derivation, overlay=overlay)
```

优势:

- 比 condition AST replacement 更安全。
- 容易审计。
- 用户心智清楚: 这是规则参数，不是事实。
- 可做 UI control / notebook slider。

## 4. 推荐 SDK 用户体验

理想主流程:

```python
from kernel.sdk import Entity, Field, Identity, Rule, RuleRef, Derivation, SDKStore, vars

sdk = SDKStore([Room])

room_a = sdk.ref(Room, room_id="room_a")
sdk.set(Room.temperature, room_a, 24, meta={"source": "sensor"})
sdk.set(Room.occupied, room_a, True, meta={"source": "booking"})

with vars("r", "t", "status") as (r, t, status):
    warm_rule = Rule(
        id="rule.warm_occupied_room",
        version="1.0.0",
        select=[r],
        where=[
            Room(r),
            r.temperature == t,
            t > 20,
            r.occupied == True,
        ],
        expose=True,
        parameters={"temperature_threshold": 20},
        parameter_bindings={
            "temperature_threshold": {"condition": "b0.a2", "operator": ">"}
        },
    )

    comfort = Derivation(
        id="drv.room_comfort",
        version="1.0.0",
        where=[
            RuleRef(warm_rule)(r),
            status == "comfortable",
        ],
        head=Room.status(value=status),
    )

candidates = sdk.evaluate(comfort, mode="native")

review = sdk.review(candidates[0])
tree = review.evidence_tree()

print(tree.to_text())

threshold = tree.find_parameter(
    "rule.warm_occupied_room",
    "temperature_threshold",
)

scenario = threshold.override(30, note="expert threshold")
after = scenario.evaluate(comfort)

print(review.compare(after).to_text())
```

用户应看到:

```text
candidate: room_a.status += "comfortable"
└─ derivation: drv.room_comfort@1.0.0
   └─ rule_ref: rule.warm_occupied_room@1.0.0
      ├─ fact: Room.temperature(room_a) = 24
      ├─ condition: temperature > 20 [parameter: temperature_threshold]
      ├─ fact: Room.occupied(room_a) = true
      └─ condition: occupied == true
```

override 后:

```text
Removed:
- room_a.status += "comfortable"

Why:
- temperature_threshold changed from 20 to 30
- observed Room.temperature(room_a) = 24
- condition temperature > 30 failed
```

## 5. MVP 建议

第一版不要一次做完整 sandbox fork、condition AST replacement、audit-of-audit schema。

推荐 MVP:

### 5.1 CandidateReview

```python
review = sdk.review(candidate)
tree = review.evidence_tree()
summary = review.summary()
steps = review.steps()
```

目标: 把现有 private/core tree builder 封装成 SDK product API，用户不需要 import core 私有模块，也不需要理解 `support_digest`。

### 5.2 OperationalEvidenceTree Wrapper

raw tree 仍是 dict/DTO。

SDK wrapper 提供:

```python
tree.facts()
tree.rules()
tree.conditions()
tree.parameters()
tree.find_fact(...)
tree.find_rule(...)
tree.find_parameter(...)
tree.to_text()
tree.to_dict()
```

节点 wrapper 提供 typed handle:

```python
node.as_fact_handle()
node.as_rule_handle()
node.as_condition_handle()
node.as_parameter_handle()
```

### 5.3 Fact-level What-if + Commit

优先支持事实节点:

```python
fact.replace_value(value, mode="what_if")
fact.commit_replace(value, approved_by="...")
```

原因:

- 当前 `assertion_fact` 节点已有 `asrt_id` / `pred_id` / `e_ref` / `claim_args` 等可操作信息。
- fact 修正是 expert review 中最自然、最容易解释的动作。
- 正式 commit 可以复用既有 retract + set/add 路径。

### 5.4 Compare

```python
diff = sdk.compare_candidates(before, after)
print(diff.to_text())
```

MVP 的价值很大程度来自 before / after。

### 5.5 Demo

推荐扩展 `examples/03_dora_minimal_evidence_tree.ipynb`，而不是用过于抽象的 `admin -> audited`。

demo 主线:

```text
source-backed regulatory facts
  -> rule chain
  -> derivation creates candidate finding
  -> expert opens operational evidence tree
  -> expert corrects a source-backed fact as what-if
  -> re-evaluate and compare
  -> commit correction or accept candidate
  -> export audit package
  -> read back same evidence tree
```

## 6. 后续阶段

### Phase 2: Rule Disable

支持:

```python
rule = tree.find_rule("rule.x", version="1.0.0")
overlay = rule.disable(mode="what_if").to_overlay()
after = sdk.evaluate_with_overlay(derivation, overlay=overlay)
```

注意:

- disable 应针对 `rule_id + version`。
- disable 后无 candidate 是合法结果，不应抛错。
- rule 存在但本次 derivation 未触达时，可返回 unused overlay metadata。

### Phase 3: Named Parameter Override

支持 rule parameter:

```python
threshold.override(30)
```

前提:

- Rule DSL / compiled payload 有稳定 parameter declaration。
- evidence tree 能把 condition 节点关联到 parameter。
- overlay 明确标记 scenario assumption。

### Phase 4: Condition Override

只用于专家例外，不作为普通路径。

要求:

- reviewer
- reason
- scope
- expiry
- explicit tree annotation

不建议把 condition override 的结果直接 accept 成普通 derived fact，除非 review record 明确进入 audit package。

### Phase 5: Review Records / Audit Export

当 review 操作需要持久化时，新增 review record，而不是把 live overlay 混入 raw tree。

可能形态:

```text
review_records.jsonl
  - review_id
  - candidate_id
  - actor
  - reason
  - overlay
  - before_candidate_keys
  - after_candidate_keys
  - decision
  - timestamp
```

audit package 可以消费 export-time snapshot，但不拥有 live action semantics。

## 7. 设计边界与反模式

### 7.1 不要把 SDK-only hook 作为核心机制

不推荐:

```python
sdk.evaluate(derivation, excluded_rules=[...])
```

问题:

- 这是 SDK 层钩子，不是 runtime contract。
- service / agent / RPC 需要重复设计。
- future engine adapter 会出现多套协议。

推荐:

```python
sdk.evaluate_with_overlay(derivation, overlay=overlay)
```

底层走 application protocol。

### 7.2 不要把 audit package 当 live sandbox

Sandbox fork 很适合 post-hoc audit lab，但不是第一版 live expert review。

风险:

- audit package facts 未必足够重建完整 Store。
- support artifacts / candidate backrefs / provenance envelopes / rule trace / sidecar 状态不一定完整。
- 大 package 内存开销高。
- commit_back 需要 audit-of-audit schema。

第一版应服务 live workflow:

```text
current Store
  -> evaluate
  -> operational tree
  -> overlay
  -> re-evaluate
```

### 7.3 不要让 EvidenceGraph 与 native tree 混淆

当前边界:

- native candidate explain surface 是 `candidate_evidence_tree / summary / narrative`。
- `EvidenceGraph` 是 PyReason / ProbLog / Souffle adapter provenance artifact。
- 两者都可以被 operational wrapper 消费，但不要假装是同一个 raw carrier。

### 7.4 不要把 LLM 生成解释当成事实

如果未来用 LLM 辅助生成 tree labels、review suggestions 或 natural-language summaries，必须标注为 suggestion / narrative，不可作为 verified evidence。

审计语义必须来自 ledger、rule payload、support artifact、provenance envelope 或显式 review record。

## 8. 市场与产品定位

这个方向不应定位为:

- 又一个 explainability dashboard
- 又一个规则引擎
- 又一个 notebook helper
- 通用知识图谱编辑器

更强定位:

```text
Decision Assurance / 可审计决策推理工作台
```

核心价值:

- 高风险决策可解释、可质询、可模拟。
- expert override 有结构化记录。
- what-if 能直接显示结论变化。
- audit package 能导出完整决策证据。

适合场景:

- 金融授信 / AML / fraud review
- 保险理赔 / 核保 / 反欺诈
- 医疗 prior authorization / 支付审核
- 政府福利资格 / 风险评分
- 供应商风险 / 合规例外审批
- AI model risk / strategy threshold review

市场参照:

- IBM ODM / Decision Intelligence: 规则治理、仿真、可审计决策。
- FICO Blaze Advisor: 金融规则与决策管理。
- Pega Decision Hub: 实时 next-best-action。
- Fiddler / Arize: XAI、what-if、root cause、AI observability。
- Rainbird: evidence chain / explain endpoint。
- Credo AI / Holistic AI / Domino Governance: AI governance / audit evidence collection。

差异化:

```text
不是只收集证据，
而是让证据参与可交互推理、专家审阅和决策复盘。
```

## 9. 最终诊断

用户想要的“推理后直接获得一个可操作 evidence tree 对象”是合理且有价值的。

但必须精确定义:

```text
不现实的版本:
  tree node 就是原始 Python Rule / Fact object，并直接执行副作用。

现实且专业的版本:
  tree node 像用户定义对象；
  tree node 可提取 typed handle；
  typed handle 可生成 overlay/action；
  overlay/action 可重跑或提交；
  raw evidence tree 仍保持可审计、不可变、可序列化。
```

推荐主抽象:

```text
CandidateReview
OperationalEvidenceTree
EvidenceNodeHandle
ActionRef
EvaluationOverlay
CandidateDiff
ReviewRecord
```

推荐第一步:

```text
sdk.review(candidate)
  -> evidence_tree()
  -> typed handles
  -> fact-level what-if / commit
  -> compare before/after
```

该方向属于 protocol / SDK / core explain / audit 边界相关的非平凡变更。若进入实现，应先创建 active blueprint，并在实现后更新相关 module docs。
