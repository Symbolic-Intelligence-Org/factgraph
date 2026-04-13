# Blueprint: Agent Layer 4A — Native-first Rule Authoring

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: W2a 精确撤回 (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/tools/_runtime_api.py` (扩展)
  - `src/factpy_kernel/agent/tools/rules.py` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)
  - `src/factpy_kernel/service/rules_v1.py` (只读依赖)
  - `src/factpy_kernel/service/runtime_v1.py` (只读依赖)

---

## 0. 目标与边界

**交付目标**：agent 能校验/预览/注册 ephemeral 规则，用 native evaluate 执行，并通过 steps-first explain 审查结果。

**冻结决策**：

| # | 决策 | 理由 |
|---|------|------|
| L4A-01 | 只做 native ephemeral 执行 | ephemeral rules 仅对 native evaluator 生效（02_runtime_sessions.md） |
| L4A-02 | 规则先走 validate + compile-preview，再允许 register | 防止无效规则注册到 session |
| L4A-03 | review 默认还是 steps-first | 与 Layer 2 explain 策略一致（delta D-05） |
| L4A-04 | 非 native 规则只允许导出/预览，不在 session 内执行 | v1.1-delta §4.2 Level 3，本层不涉及 |

**明确排除**：
- NL→Rule IR 自由生成（Layer 5+）
- Souffle / ProbLog / PyReason 规则执行
- 自动引擎路由
- 文档提取
- 规则模板库

---

## 1. RuntimeAPI Protocol 扩展

```python
class RuntimeAPI(Protocol):
    # ... existing methods ...

    def validate_rule(self, dto: dict[str, Any]) -> dict[str, Any]:
        """
        对齐 rules_v1.validate_rule(dto)。
        POST /v1/rules/validate

        dto: {
            "rule": {
                "rule_id": str,
                "version": str,           # 可选，默认 "v1"
                "select_vars": [str, ...],
                "where": list,            # 结构化 IR
                "expose": bool,           # 可选
                "description": str,       # 可选
                "tags": [str],            # 可选
                "condition_weights": dict, # 可选
            },
            "mode": str,                  # 可选，默认 "souffle"
            "strict": bool,              # 可选，默认 false
            "profile": {"name": str},    # 可选
        }

        返回: ok_response(meta={profile_effective, mode})
        错误: error_response([{kind: shape|rule_ast_validate|authoring_rule_compile, ...}])
        """
        ...

    def compile_rule_preview(self, dto: dict[str, Any]) -> dict[str, Any]:
        """
        对齐 rules_v1.compile_rule_preview(dto)。
        POST /v1/rules/compile-preview

        dto: 与 validate_rule 相同
        返回: ok_response(meta={...}, preview={compiled_payload: {...}})
        """
        ...

    def register_ephemeral_rule(
        self, session_id: str, dto: dict[str, Any],
    ) -> dict[str, Any]:
        """
        对齐 runtime_v1.register_ephemeral_rule(session_id, dto)。
        POST /v1/runtime/sessions/{id}/ephemeral-rules

        dto: {"rule": {rule_id, version, select_vars, where, expose, ...}}
        返回: ok_response(result={rule_id, version, status: "registered"|"replaced", total_ephemeral})
        错误: error_response([{kind: shape|rule_ast_validate|runtime, ...}])

        约束：
        - pred_id 在 where 中必须存在于 session schema
        - upsert 语义：相同 (rule_id, version) 替换，status="replaced"
        - FS 优先：若 FS registry 有同 (rule_id, version)，ephemeral 被静默遮蔽
        """
        ...

    def list_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        """
        对齐 runtime_v1.list_ephemeral_rules(session_id)。
        GET /v1/runtime/sessions/{id}/ephemeral-rules

        返回: ok_response(result={ephemeral_rules: [{rule_id, version}, ...], total})
        """
        ...

    def clear_ephemeral_rules(self, session_id: str) -> dict[str, Any]:
        """
        对齐 runtime_v1.clear_ephemeral_rules(session_id)。
        DELETE /v1/runtime/sessions/{id}/ephemeral-rules

        返回: ok_response(result={cleared: int})
        """
        ...
```

### 1.1 LocalRuntimeAPI / HttpRuntimeAPI 实现

```python
# LocalRuntimeAPI
def validate_rule(self, dto): return rules_v1.validate_rule(dto)
def compile_rule_preview(self, dto): return rules_v1.compile_rule_preview(dto)
def register_ephemeral_rule(self, sid, dto): return runtime_v1.register_ephemeral_rule(sid, dto)
def list_ephemeral_rules(self, sid): return runtime_v1.list_ephemeral_rules(sid)
def clear_ephemeral_rules(self, sid): return runtime_v1.clear_ephemeral_rules(sid)

# HttpRuntimeAPI
def validate_rule(self, dto): return self._post_json("/rules/validate", dto)
def compile_rule_preview(self, dto): return self._post_json("/rules/compile-preview", dto)
def register_ephemeral_rule(self, sid, dto): return self._post_json(f"/sessions/{sid}/ephemeral-rules", dto)
def list_ephemeral_rules(self, sid): return self._get_json(f"/sessions/{sid}/ephemeral-rules")
def clear_ephemeral_rules(self, sid): return self._delete_json(f"/sessions/{sid}/ephemeral-rules")
# 注意：需新增 _delete_json() helper（L4A-13 冻结），仿照 close_session 的 DELETE 实现
```

---

## 2. RuleTools — 新增 Tool 层

### 2.1 数据模型

```python
@dataclass
class RuleSpec:
    """Agent 构造的规则 spec。结构化 IR，非 DSL 字符串。"""
    rule_id: str
    select_vars: list[str]
    where: list                             # 结构化 where IR
    version: str = "v1"
    expose: bool = True
    description: str | None = None
    tags: list[str] | None = None
    condition_weights: dict[str, Any] | None = None

    def to_rule_dict(self) -> dict[str, Any]:
        """生成传给 runtime API 的 rule dict。"""
        d: dict[str, Any] = {
            "rule_id": self.rule_id,
            "version": self.version,
            "select_vars": self.select_vars,
            "where": self.where,
            "expose": self.expose,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.tags is not None:
            d["tags"] = self.tags
        if self.condition_weights is not None:
            d["condition_weights"] = self.condition_weights
        return d


@dataclass
class ValidateResult:
    """规则校验结果。"""
    valid: bool
    profile_effective: str
    mode: str
    errors: list[dict[str, Any]]            # 空 = valid


@dataclass
class CompilePreviewResult:
    """规则编译预览结果。"""
    valid: bool
    compiled_payload: dict[str, Any] | None  # None if invalid
    profile_effective: str
    mode: str
    errors: list[dict[str, Any]]


@dataclass
class RegisterResult:
    """Ephemeral 规则注册结果。"""
    rule_id: str
    version: str
    status: str                             # "registered" | "replaced"
    total_ephemeral: int


@dataclass
class RegisterError:
    """注册失败（不抛异常）。"""
    rule_id: str
    error_kind: str
    error_message: str


@dataclass
class EvaluateOutcome:
    """
    register_and_evaluate_rule 的 evaluate 部分结果。
    四种 status 消除"未请求"vs"请求失败"的歧义（L4A-10 修订）。
    """
    status: Literal["not_requested", "ok", "error", "skipped"]
    result: EvaluateResult | None = None        # 仅 status="ok" 时非 None
    error_message: str | None = None            # 仅 status="error" 时非 None


@dataclass
class EphemeralRuleSummary:
    """Ephemeral 规则清单条目。"""
    rule_id: str
    version: str
```

### 2.2 RuleTools 接口

```python
class RuleTools:
    """
    Native-first 规则 authoring tool 层。

    流程：validate → compile-preview → register → evaluate → review → accept。
    L4A-02 保证：register 前必须先 validate 通过。
    """

    def __init__(self, *, runtime_api: RuntimeAPI, session: AgentSession) -> None:
        """持有 AgentSession 引用，动态读取 runtime_session_id。"""
        ...

    def validate(self, spec: RuleSpec) -> ValidateResult:
        """
        校验规则 spec。不注册，不执行。

        调用 runtime_api.validate_rule({"rule": spec.to_rule_dict()})
        解析 response → ValidateResult
        """
        ...

    def compile_preview(self, spec: RuleSpec) -> CompilePreviewResult:
        """
        编译预览。不注册，不执行。
        展示编译后的 payload 供用户审查。

        调用 runtime_api.compile_rule_preview({"rule": spec.to_rule_dict()})
        """
        ...

    def register_ephemeral(self, spec: RuleSpec) -> RegisterResult | RegisterError:
        """
        注册 ephemeral 规则到当前 session。

        前置条件（由 orchestrator 保证）：validate 已通过。
        此方法做 defensive check：先调 validate，失败则返回 RegisterError。

        调用 runtime_api.register_ephemeral_rule(runtime_session_id, {"rule": spec.to_rule_dict()})

        注意：
        - 仅 native evaluate 可消费（L4A-01）
        - session close 时丢弃
        - FS registry 有同 (rule_id, version) 时被静默遮蔽
        """
        ...

    def list_ephemeral(self) -> list[EphemeralRuleSummary]:
        """列出当前 session 的 ephemeral 规则。"""
        ...

    def clear_ephemeral(self) -> int:
        """清除当前 session 所有 ephemeral 规则。返回清除数。"""
        ...
```

---

## 3. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... Layer 2 + 3A + W2a existing methods ...

    # ── Layer 4A: Native Rule Authoring ──

    def validate_rule(self, spec: RuleSpec) -> ValidateResult:
        """
        校验规则。不注册。
        直接委托 rule_tools.validate(spec)。
        """
        ...

    def preview_rule(self, spec: RuleSpec) -> CompilePreviewResult:
        """
        编译预览。不注册。
        直接委托 rule_tools.compile_preview(spec)。
        """
        ...

    def register_and_evaluate_rule(
        self,
        spec: RuleSpec,
        *,
        evaluate_target_pred_id: str | None = None,
        evaluate_limit: int | None = None,
    ) -> tuple[RegisterResult | RegisterError, EvaluateOutcome]:
        """
        完整的 validate → register → evaluate 流程。

        时序：
        1. rule_tools.validate(spec)
           - 不通过: 返回 (RegisterError(...), EvaluateOutcome(status="skipped"))

        2. rule_tools.register_ephemeral(spec)
           - RegisterError: 返回 (RegisterError(...), EvaluateOutcome(status="skipped"))

        3. 如果 evaluate_target_pred_id 未提供：
           - 返回 (RegisterResult, EvaluateOutcome(status="not_requested"))

        4. 如果 evaluate_target_pred_id 提供：
           自动构造 EvaluateRequest 并执行 evaluate
           → derivation 使用注册的规则（通过 ruleref atom）
           → evaluate_tools.evaluate(request)
           → 自动缓存 candidates（Layer 2 语义）

           成功：返回 (RegisterResult, EvaluateOutcome(status="ok", result=EvaluateResult))
           失败：捕获 AgentRuntimeError，返回 (RegisterResult, EvaluateOutcome(status="error", error_message=str))

        5. _checkpoint()

        EvaluateOutcome.status 三态语义（L4A-10 修订）：
        - "not_requested": evaluate_target_pred_id 未提供，不执行
        - "ok":            evaluate 成功，result 非 None
        - "error":         evaluate 失败（AgentRuntimeError），error_message 非 None
        - "skipped":       register 阶段就失败了，evaluate 未到达

        L4A-02 保证：register 前先 validate。
        L4A-01 保证：evaluate mode 固定为 "native"。
        """
        ...

    def list_ephemeral_rules(self) -> list[EphemeralRuleSummary]:
        """列出当前 session 的 ephemeral 规则。"""
        ...

    def clear_ephemeral_rules(self) -> int:
        """清除全部 ephemeral 规则 + checkpoint。"""
        ...
```

### 3.1 register_and_evaluate_rule 的 EvaluateRequest 构造

当 `evaluate_target_pred_id` 提供时，orchestrator 构造：

```python
EvaluateRequest(
    derivation={
        "derivation_id": f"agent_rule_eval_{spec.rule_id}",
        "version": spec.version,
        "target": evaluate_target_pred_id,       # 注意：字段名是 "target"，不是 "target_pred_id"
        "head_vars": spec.select_vars,
        "where": [
            ["ruleref", spec.rule_id, spec.version, spec.select_vars],
            # ruleref atom 格式：["ruleref", rule_id, version, vars]
        ],
        "mode": "native",                        # L4A-01 冻结
    },
    limit=evaluate_limit,
)
```

**IR 格式对齐说明**（见 test_agent_layer2_workflow.py:58）：
- 字段名：`target`（非 `target_pred_id`）
- RuleRef atom：`["ruleref", rule_id, version, select_vars]`（非 `["rule_ref", ...]`）
- `mode` 固定 `"native"`

### 3.2 Steps-first Review 无变更

evaluate 后的 review 路径与 Layer 2 完全相同：
- `orchestrator.review_candidate(candidate_id, include_steps=True)` → steps-first
- `orchestrator.accept(candidate_id)` → accept

无需 Layer 4A 特殊处理。

---

## 4. Tool Registry 扩展

W2a 注册了 22 个 tool。Layer 4A 追加：

```python
# 扩展 build_layer3a_tool_registry()

"validate_rule":                → orchestrator.validate_rule
"preview_rule":                 → orchestrator.preview_rule
"register_and_evaluate_rule":   → orchestrator.register_and_evaluate_rule
"list_ephemeral_rules":         → orchestrator.list_ephemeral_rules
"clear_ephemeral_rules":        → orchestrator.clear_ephemeral_rules
```

Layer 4A 总计 27 个 tool（22 W2a + 5 Layer 4A）。

扩展 `build_layer3a_tool_registry()`，与 W2a 的累进模式一致。

---

## 5. RuleTools 与 WriteTools 的关系

| 维度 | WriteTools | RuleTools |
|------|-----------|-----------|
| 操作对象 | 事实（assertion） | 规则（ephemeral rule） |
| 持久化 | 写入 ledger（持久） | 注册到 session 内存（session close 时丢弃） |
| 审计链 | meta.approved_by / meta.trace_id | 无（ephemeral 不入审计包） |
| 确认流程 | DraftManager confirm | validate + compile-preview（无 DraftManager） |
| 撤销 | retract_by_asrt | clear_ephemeral_rules |

**为什么规则不用 DraftManager**：
- 规则不写入 ledger，不产生 assertion_id
- 规则的 "确认" 是 validate + compile-preview，不是人工 approve
- 规则的 "撤销" 是 clear，不是 retract（无 append-only 语义）

---

## 6. Cold Restart 下的 Ephemeral Rules 恢复语义

### 6.1 明确接受的限制（L4A-11 冻结）

Cold restart 后 ephemeral rules **全部丢失**，Layer 4A **不做 rehydrate**。

**原因**：
- `RuntimeSession.ephemeral_rules` 是进程内 dict，不持久化
- `AgentCheckpointStore` 只保存 `AgentSession + DraftManager`，不保存规则
- `recover_agent_session()` 用 `bootstrap_spec.open_dto` 重建的是空 session

### 6.2 agent 的处理策略

```
Cold restart 发生
  │
  ├─ recover_agent_session() 返回 RecoveryResult(mode="cold")
  │
  ├─ orchestrator.list_ephemeral_rules() → []（空）
  │
  ├─ 调用方检测到 ephemeral rules 丢失
  │   → 向用户报告："cold restart 后 ephemeral 规则已丢失，需要重新注册"
  │
  └─ 调用方需重新 register_and_evaluate_rule(...)
```

### 6.3 为什么不做 agent-side rule cache/rehydrate

- 复杂度：需要序列化 where IR + 在恢复时重新注册，容易引入 schema 漂移问题
- 收益低：ephemeral rules 本就是实验性的；生产规则应通过 FS registry 持久注册
- 与 kernel 语义一致：kernel 自己也不持久化 ephemeral rules

### 6.4 checkpoint 的作用

`register`/`clear` 后仍然 `_checkpoint()`——这保存的是 AgentSession + DraftManager 状态，
不是 ephemeral rules 本身。checkpoint 的意义是保持其他状态（drafts、session binding）与当前时刻同步。

---

## 7. Validate/Compile-preview 的 Mode 说明

### 7.1 明确区分（L4A-12 冻结）

`validate_rule` 和 `compile_rule_preview` 是 **authoring preflight**，不是 native execution。

当前 `rules_v1.py` 只支持 `mode="souffle"`（`_SUPPORTED_MODES = {"souffle"}`）。
这与 Layer 4A 的 native ephemeral execution 不冲突——两者是不同层面：

```
Authoring preflight（validate / compile-preview）
  → mode = "souffle"（当前唯一支持值）
  → 检查规则语法、pred_id 存在性、编译产物
  → 不执行规则

Runtime execution（evaluate）
  → mode = "native"（L4A-01 冻结）
  → 通过 ephemeral rule + ruleref 执行
  → 产生 candidates
```

### 7.2 对 agent 调用方的影响

- `validate_rule(spec)` 和 `preview_rule(spec)` 默认 `mode="souffle"`，调用方无需指定
- 这意味着 validate 检查的是 "这条规则在 souffle 编译下是否合法"
- ephemeral rule 在 native evaluate 下的语义可能略有不同（如 Souffle 不支持的扩展特性）
- Layer 4A 接受此差异——validate 是 best-effort preflight，不是 native 语义完全保证

---

## 8. 实现顺序

```
Step 1: RuntimeAPI Protocol 扩展
        → +validate_rule +compile_rule_preview
        → +register_ephemeral_rule +list_ephemeral_rules +clear_ephemeral_rules
        → LocalRuntimeAPI / HttpRuntimeAPI 实现
        → 单测

Step 2: RuleTools 数据模型
        → RuleSpec / ValidateResult / CompilePreviewResult
        → RegisterResult / RegisterError / EphemeralRuleSummary
        → 纯数据模型单测

Step 3: RuleTools 实现
        → validate / compile_preview / register_ephemeral / list / clear
        → mock RuntimeAPI 单测

Step 4: Orchestrator 扩展
        → validate_rule / preview_rule / register_and_evaluate_rule
        → list_ephemeral_rules / clear_ephemeral_rules
        → 集成测试：register → evaluate → steps review → accept

Step 5: Tool Registry 扩展
        → 扩展 build_layer3a_tool_registry()
        → 27 tool 全量注册验证
```

---

## 9. 目录结构增量

```
src/factpy_kernel/agent/
  ├── tools/
  │   ├── rules.py              # (新建) RuleTools + 数据模型
  │   └── _runtime_api.py       # (扩展) +5 methods
  ├── orchestrator.py            # (扩展) +5 methods
  └── framework.py               # (扩展) tool registry 27 tools

src/factpy_kernel/tests/
  ├── test_agent_l4a_runtime_api.py    # (新建)
  ├── test_agent_l4a_rules.py          # (新建)
  └── test_agent_l4a_workflow.py       # (新建) 端到端：register → evaluate → review → accept
```

---

## 10. 验收标准

1. **validate_rule**：valid 规则返回 ValidateResult(valid=True)；invalid 规则返回 errors 列表
2. **preview_rule**：返回 compiled_payload 供审查
3. **register_ephemeral**：注册成功返回 RegisterResult(status="registered")；重复注册返回 status="replaced"
4. **register_and_evaluate_rule**：validate → register → evaluate 一站式完成；candidates 自动缓存
5. **L4A-01**：evaluate mode 固定为 "native"
6. **L4A-02**：register 前先 validate；validate 失败不注册
7. **steps review**：evaluate 后 review_candidate 返回 steps（L4A-03）
8. **list/clear ephemeral**：list 返回当前 session 的 ephemeral 清单；clear 清除并 checkpoint
9. **FS 遮蔽**：如果 FS registry 有同 (rule_id, version)，ephemeral 被遮蔽——register 成功但 evaluate 使用 FS 版本
10. **Tool 数量**：27 个
11. **端到端测试**：register → native evaluate → steps review → accept 完整流程

---

## 11. 已知约束

1. **Ephemeral 规则不入审计包**：session close 时丢弃，不写入审计产物。生产规则应通过 FS registry 持久注册。
2. **Cold restart 后 ephemeral rules 全丢**（L4A-11 冻结）：不做 rehydrate。调用方需重新注册。详见 §6。
3. **FS 遮蔽是静默的**：register 返回 `status="registered"` 但实际被 FS 版本遮蔽。agent 可通过 `list_rules(include_spec=True)` 检查 `source` 字段识别。
4. **validate/compile-preview 只支持 mode="souffle"**（L4A-12 冻结）：这是 authoring preflight，不是 native validation。详见 §7。
5. **validate 和 register 不是原子的**：validate 通过后 schema 可能变更。register_ephemeral 内置 defensive validate 兜底。
6. **规则 where IR 由调用方构造**：Layer 4A 不负责 NL→where IR 翻译。
7. **ruleref 要求 expose=true**：derivation 中使用 ruleref 引用规则时，规则必须 `expose=true`。RuleSpec 默认 `expose=True`。
8. **evaluate 失败不阻塞 register 成功**（L4A-10/L4A-15 冻结）：register_and_evaluate_rule 中，evaluate 失败时捕获 AgentRuntimeError，返回 `(RegisterResult, EvaluateOutcome(status="error"))`；未请求 evaluate 时返回 `EvaluateOutcome(status="not_requested")`；register 失败时返回 `EvaluateOutcome(status="skipped")`。详见 §3。

---

## 12. Outcome / Deviations

### Outcome

- 新增 `agent/tools/rules.py`，落地 `RuleSpec` / `ValidateResult` / `CompilePreviewResult` / `RegisterResult` / `RegisterError` / `EvaluateOutcome` / `EphemeralRuleSummary` / `RuleTools`
- `ReadReviewOrchestrator` 扩展了 `validate_rule` / `preview_rule` / `register_and_evaluate_rule` / `list_ephemeral_rules` / `clear_ephemeral_rules`
- `build_layer3a_tool_registry()` 从 22 tools 扩展到 27 tools，Layer 4A rule authoring 与现有 read/write/retract surface 收敛到同一个 registry
- 新增 Layer 4A 定向测试：runtime API / RuleTools / end-to-end workflow；相关 Layer 3A/W2a registry 断言同步更新

### Deviations

1. `_runtime_api.py` 中的 `validate_rule` / `compile_rule_preview` / ephemeral rule methods 与 `_delete_json()` helper 已在当前分支存在，因此本轮主要补的是 Layer 4A 测试覆盖，而不是 runtime adapter 逻辑新增。
