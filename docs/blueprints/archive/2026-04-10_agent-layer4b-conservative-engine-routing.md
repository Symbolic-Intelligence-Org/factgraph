# Blueprint: Agent Layer 4B — Conservative Engine Routing

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: Layer 4A Native Rule Authoring (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/tools/routing.py` (新建)
  - `src/factpy_kernel/agent/tools/rules.py` (扩展: RuleSpec 加 routing hint)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：agent 能对规则/推导请求给出引擎推荐（recommended_engine + reason），调用方可覆盖。

**冻结决策**：

| # | 决策 | 理由 |
|---|------|------|
| L4B-01 | Advisor 只给建议，不自动执行 | agent 不应隐式替用户选引擎；推荐 + 覆盖 |
| L4B-02 | 新规则优先看显式 metadata/hint，缺失时才用 heuristics | 显式优先于推断 |
| L4B-03 | 需要定义最小 routing metadata carrier | 当前 rule inventory / RuleSpec 无任何 engine 信息 |
| L4B-04 | 不碰文档提取，不碰多引擎实际执行闭环 | Layer 4C / Layer 5 的事 |

**明确排除**：
- 自动引擎 dispatch（advisor 推荐后自动切换 mode 执行）
- 文档提取的引擎路由
- 多引擎并行执行 + 结果合并
- NL 语言线索分析（v1 蓝图 §12 的 CERTAINTY_CUES / PROBABILITY_CUES / TEMPORAL_CUES 留给 Layer 5+）

---

## 1. 当前 Engine Metadata 现状

### 1.1 完全缺失的

| 数据结构 | 缺失内容 |
|---------|---------|
| `RuleSummary` (kg_read.py) | 无 engine / mode / routing_hint 字段 |
| `RuleSpec` (rules.py) | 无 engine_routing_hint |
| `EvaluateRequest` (evaluate.py) | mode 内嵌在 derivation dict 中，无显式参数 |
| session rule inventory (runtime_v1.py) | 返回值不含 engine 信息 |

### 1.2 已存在可用的

| 数据 | 位置 | 可消费方式 |
|------|------|-----------|
| `EvaluateResult.mode` | evaluate.py:33 | evaluate 后可知实际用了哪个引擎 |
| `derivation.mode` | 内嵌在 derivation dict | 调用方构造 evaluate request 时指定 |
| `RuleSpec.tags` | rules.py:28 | 可约定 tag 携带 routing hint；但仅 agent-side RuleSpec 可用，runtime inventory 不返回 tags |
| `ExplainSummary.kind` | explain.py:16 | 间接反映引擎类型 |
| ephemeral rule = native-only | 02_runtime_sessions.md | 硬约束 |

---

## 2. Routing Metadata Carrier

### 2.1 EngineRoutingHint

Agent 层的 routing 元数据载体。**不改 kernel**——纯 agent 层数据结构。

```python
@dataclass(frozen=True)
class EngineRoutingHint:
    """
    引擎路由提示。附加在规则/推导请求上，供 advisor 消费。

    来源优先级（L4B-02）：
    1. 显式指定（调用方直接设置 suggested_engine）
    2. 规则 tags 约定（如 tags=["engine:problog"]）
    3. Advisor heuristics（draft 结构分析）
    """
    suggested_engine: str | None = None       # "native" | "souffle" | "problog" | "pyreason" | None
    reason: str = ""                          # 人类可读推荐理由
    source: str = "unspecified"               # "explicit" | "tag" | "heuristic" | "unspecified"
    overrideable: bool = True                 # 是否可被调用方覆盖
    confidence: float = 0.0                   # advisor 的推荐置信度 [0, 1]
```

### 2.2 RuleSpec 扩展

```python
@dataclass
class RuleSpec:
    # ... existing fields ...
    routing_hint: EngineRoutingHint | None = None   # 新增
```

`routing_hint` 是可选的。Layer 4A 的所有现有调用不受影响（默认 None）。

### 2.3 Tag 约定

当 `RuleSpec.tags` 包含 `engine:<name>` 格式的 tag 时，advisor 可从中提取 routing hint：

```python
tags=["engine:problog", "domain:risk"]
# → advisor 提取 engine:problog → EngineRoutingHint(suggested_engine="problog", source="tag")
```

这是零 kernel 改动的方案——利用已有的 `tags` 字段做约定，不新增 runtime API。

---

## 3. EngineRoutingAdvisor

### 3.1 设计原则

```
输入：RuleSpec / EvaluateRequest / FactDraft + session context
输出：EngineRoutingHint（推荐 + 理由 + 可覆盖标志）
行为：纯函数，不执行任何写入/evaluate 操作
```

### 3.2 接口

```python
class EngineRoutingAdvisor:
    """
    保守版引擎路由 advisor。

    三级推荐策略（L4B-02 优先级）：
    1. 显式 hint：调用方已设置 routing_hint.suggested_engine → 直接返回
    2. Tag 推断：RuleSpec.tags 含 "engine:<name>" → 提取
    3. Heuristic：分析 spec 结构 → 保守推荐

    不做：NL 语言线索分析、自动 dispatch、多引擎并行
    """

    def __init__(self, *, runtime_api: RuntimeAPI, session: AgentSession) -> None: ...

    def recommend_for_rule(
        self, spec: RuleSpec,
    ) -> EngineRoutingHint:
        """
        为规则推荐引擎。

        策略：
        1. spec.routing_hint 非 None 且 suggested_engine 非 None
           → 返回原 hint（source="explicit"）

        2. spec.tags 含 "engine:<name>"
           → EngineRoutingHint(suggested_engine=name, source="tag", reason="tag engine:...")

        3. Heuristic 分析：
           a. spec 是 ephemeral + session 内注册
              → 推荐 "native"（ephemeral rules 仅 native 可消费）
              → reason = "ephemeral rules only work with native evaluate"
              → confidence = 1.0, overrideable = False

           b. 其他
              → 推荐 "native"（保守默认）
              → reason = "no routing signal detected; defaulting to native"
              → confidence = 0.3

        注意：v1 不使用 condition_weights 作为路由信号。
        condition_weights 是 certainty metadata（用于 native certainty summary），
        不是概率语义。使用它推荐 ProbLog 会系统性误导。

        返回 EngineRoutingHint
        """
        ...

    def recommend_for_evaluate(
        self, derivation: dict[str, Any],
    ) -> EngineRoutingHint:
        """
        为 evaluate request 推荐引擎。

        v1 策略（收窄到可实现合同）：
        1. derivation 已含 "mode" 字段
           → 返回 EngineRoutingHint(suggested_engine=mode, source="explicit")

        2. derivation.where 含 ["ruleref", ...] atom
           → 检查 ruleref 引用的 rule 是否是当前 session 的 ephemeral rule
           → 如果是 → 推荐 "native"（ephemeral 限制）
             reason = "ruleref references ephemeral rule; native only"
             confidence = 1.0, overrideable = False

        3. 其他
           → 推荐 "native"（保守默认）
           → reason = "no routing signal; defaulting to native"
           → confidence = 0.3

        v1 不做：temporal atom 检测、probabilistic annotation 检测、
        graph propagation 结构分析。这些留给 Layer 5+（需要稳定的
        where IR tag 定义，当前未冻结）。

        返回 EngineRoutingHint
        """
        ...

    def check_consistency(
        self,
        pred_id: str,
        suggested_engine: str,
    ) -> ConsistencyWarning | None:
        """
        检查推荐引擎与该 pred_id 已有 evaluation history 的一致性。

        策略：
        1. 查询 session 中该 pred_id 的已有 candidates
           → list_candidates(pred_id=pred_id)
        2. 从 candidates 的 support_kind 推断历史使用的引擎
        3. 如果 suggested_engine 与历史引擎不一致
           → 返回 ConsistencyWarning(message, historical_engine, suggested_engine)
        4. 一致或无历史
           → 返回 None
        """
        ...
```

### 3.3 ConsistencyWarning

```python
@dataclass
class ConsistencyWarning:
    """引擎一致性警告。仅提示，不阻止。"""
    message: str
    pred_id: str
    historical_engine: str          # 从 support_kind 推断
    suggested_engine: str
```

### 3.4 support_kind → engine 映射

```python
SUPPORT_KIND_TO_ENGINE = {
    # 真实值，见 03_runtime_queries_views.md:1079, 1110
    "native_binding_v1": "native",
    "souffle_witness_v1": "souffle",
    "problog_provenance_v1": "problog",
    "pyreason_provenance_v1": "pyreason",
    # 降级分支：引擎执行了但未产生 witness/provenance
    "engine_no_witness_v1": None,               # 映射为 None = 无法判断引擎
}
```

**engine_no_witness_v1 处理策略**：一致性检查遇到此值时跳过（视为"无法判断"），不产生 warning 也不作为历史引擎记录。

---

## 4. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4B: Engine Routing ──

    def recommend_engine_for_rule(self, spec: RuleSpec) -> EngineRoutingHint:
        """为规则推荐引擎。委托 advisor.recommend_for_rule(spec)。"""
        ...

    def recommend_engine_for_evaluate(
        self, derivation: dict[str, Any],
    ) -> EngineRoutingHint:
        """为 evaluate 推荐引擎。委托 advisor.recommend_for_evaluate(derivation)。"""
        ...

    def check_engine_consistency(
        self, pred_id: str, suggested_engine: str,
    ) -> ConsistencyWarning | None:
        """检查引擎一致性。委托 advisor.check_consistency(...)。"""
        ...

    def register_and_evaluate_rule_with_routing(
        self,
        spec: RuleSpec,
        *,
        evaluate_target_pred_id: str | None = None,
        evaluate_limit: int | None = None,
        override_engine: str | None = None,
    ) -> tuple[RegisterResult | RegisterError | None, EvaluateOutcome, EngineRoutingHint]:
        """
        带路由建议的 register + evaluate。

        时序：
        1. hint = recommend_engine_for_rule(spec)
        2. consistency = check_engine_consistency(target_pred_id, hint.suggested_engine)
           → 如果有 warning，附加到 hint.reason

        3. 确定实际 engine：
           a. override_engine 非 None → 使用 override（用户覆盖）
           b. hint.suggested_engine 非 None → 使用推荐
           c. 默认 "native"

        4. 如果实际 engine == "native"：
           → register_and_evaluate_rule(spec, target_pred_id, limit)
           （复用 Layer 4A 现有方法）

        5. 如果实际 engine != "native"（L4B-11 冻结）：
           → **不注册 ephemeral**（ephemeral 仅 native 可消费，注册是无用状态污染）
           → **不返回 preview**（调用方可自行调 preview_rule(spec) 获取）
           → 第一项返回 None
           → EvaluateOutcome(status="skipped",
               error_message="non-native engine '{engine}' selected; "
                             "register rule to FS registry via authoring pipeline, "
                             "then evaluate with target engine")
           → 调用方拿到 hint，可选择：
             a. 改为 native 执行（override_engine="native"）
             b. 走 authoring pipeline 注册到 FS registry
             c. 调 preview_rule(spec) 预览编译产物

        6. 返回 (None, EvaluateOutcome(status="skipped"), hint)

        L4B-01 保证：advisor 只给建议；override_engine 允许覆盖。
        """
        ...
```

### 4.1 与 Layer 4A 的关系

Layer 4B 不替换 Layer 4A 的 `register_and_evaluate_rule()`——那个方法继续存在，用于"已知要 native evaluate"的场景。

`register_and_evaluate_rule_with_routing()` 是增量方法，在 Layer 4A 基础上加一层 routing recommendation。

---

## 5. Tool Registry 扩展

Layer 4A 注册了 27 个 tool。Layer 4B 追加：

```python
# 扩展 build_layer3a_tool_registry()

"recommend_engine_for_rule":               → orchestrator.recommend_engine_for_rule
"recommend_engine_for_evaluate":           → orchestrator.recommend_engine_for_evaluate
"check_engine_consistency":                → orchestrator.check_engine_consistency
"register_and_evaluate_rule_with_routing": → orchestrator.register_and_evaluate_rule_with_routing
```

Layer 4B 总计 31 个 tool（27 Layer 4A + 4 Layer 4B）。

---

## 6. 实现顺序

```
Step 1: EngineRoutingHint + ConsistencyWarning 数据模型
        → 纯 dataclass
        → 单测

Step 2: RuleSpec 扩展
        → +routing_hint: EngineRoutingHint | None
        → 确认 Layer 4A 现有调用不受影响（默认 None）

Step 3: EngineRoutingAdvisor 实现
        → recommend_for_rule（三级策略）
        → recommend_for_evaluate（heuristic）
        → check_consistency（support_kind 映射）
        → mock RuntimeAPI 单测

Step 4: Orchestrator 扩展
        → recommend_engine_for_rule / recommend_engine_for_evaluate / check_engine_consistency
        → register_and_evaluate_rule_with_routing
        → 集成测试

Step 5: Tool Registry 扩展
        → 31 tool 全量注册验证
```

---

## 7. 目录结构增量

```
src/factpy_kernel/agent/
  ├── tools/
  │   ├── routing.py            # (新建) EngineRoutingHint, ConsistencyWarning, EngineRoutingAdvisor
  │   └── rules.py              # (扩展) RuleSpec +routing_hint
  ├── orchestrator.py            # (扩展) +4 methods
  └── framework.py               # (扩展) tool registry 31 tools

src/factpy_kernel/tests/
  ├── test_agent_l4b_routing.py        # (新建)
  └── test_agent_l4b_workflow.py       # (新建) 端到端：recommend → register → evaluate with routing
```

---

## 8. 验收标准

1. **显式 hint**：RuleSpec.routing_hint.suggested_engine 非 None 时，advisor 直接返回（source="explicit"）
2. **Tag 推断**：tags=["engine:problog"] → hint.suggested_engine="problog", source="tag"
3. **Ephemeral = native**：ephemeral rule 推荐 native，confidence=1.0, overrideable=False
4. **保守默认**：无信号时推荐 native，confidence=0.3
5. **一致性检查**：已有 candidates 使用 souffle，推荐 problog → 返回 ConsistencyWarning
6. **override_engine**：调用方可覆盖推荐
7. **非 native engine + ephemeral**：不注册 ephemeral rule（session state 不污染）；第一项返回 None；EvaluateOutcome(status="skipped") + 明确原因；list_ephemeral_rules() 不含该规则
8. **L4B-01**：advisor 不自动执行
9. **L4B-04**：不涉及文档提取
10. **Tool 数量**：31 个
11. **单测 + 集成测试**覆盖

---

## 9. 已知约束

1. **Heuristics 极度保守**：v1 不做 NL 语言线索分析、不做 temporal/probabilistic 结构检测。唯一的 heuristic 是 ephemeral→native 和 ruleref→native。其他情况默认 native。
2. **condition_weights 不作为路由信号**（L4B-13）：condition_weights 是 certainty metadata（用于 native certainty summary），不是概率语义。
3. **Tag-based routing 只覆盖 agent-side RuleSpec**（L4B-15）：runtime session rule inventory（include_spec=true）不返回 tags。对 list_rules() 回来的现有 inventory 无法做 tag-based routing。
4. **Tag 约定无强制**：`engine:<name>` 是 agent 层约定，kernel 不校验。advisor 需自行验证 engine name 合法性。
5. **一致性检查是 best-effort**：基于 candidates 的 support_kind 推断历史引擎。engine_no_witness_v1 视为"无法判断"，不产生 warning。session 中无 candidates 时无法判断。
6. **非 native route 不注册 ephemeral**（L4B-11）：推荐 problog/pyreason/souffle 时不注册规则，只返回 skipped + 建议走 authoring pipeline；如需 preview 由调用方单独调 `preview_rule(spec)`。
7. **recommend_for_evaluate v1 极简**（L4B-14）：只看显式 mode + ruleref 到 ephemeral + 默认 native。temporal/probabilistic where IR 分析缺少稳定 tag 定义，留给 Layer 5+。

---

## 10. Outcome / Deviations

### Outcome

- 新增 `agent/tools/routing.py`，落地 `EngineRoutingHint` / `ConsistencyWarning` / `SUPPORT_KIND_TO_ENGINE` / `EngineRoutingAdvisor`
- `RuleSpec` 扩展了可选 `routing_hint`，同时保持 `to_rule_dict()` 不把 agent-only routing carrier 泄露到 kernel runtime 合同
- `ReadReviewOrchestrator` 扩展了 `recommend_engine_for_rule` / `recommend_engine_for_evaluate` / `check_engine_consistency` / `register_and_evaluate_rule_with_routing`
- `build_layer3a_tool_registry()` 从 27 tools 扩到 31 tools，Layer 4B routing recommendation 与现有 read/write/retract/rule flow 收敛到同一个 registry
- 新增 Layer 4B 定向测试：纯 advisor contract + end-to-end workflow；并同步更新 Layer 3A/W2a/4A registry 断言

### Deviations

1. `EngineRoutingAdvisor.recommend_for_rule()` 中的 “ephemeral = native” 落地为“同 `(rule_id, version)` 已存在于当前 session ephemeral registry 时强制 native”，而不是对所有新 RuleSpec 一律视为 ephemeral；这让 tag/explicit hint 仍有机会把新规则导向非 native authoring path。
2. `register_and_evaluate_rule_with_routing()` 在 non-native recommendation 下不会自动调用 `preview_rule(spec)`；preview 被保留为显式的独立调用，避免把 3-tuple 返回合同重新膨胀。
