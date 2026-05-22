# Audit Log: Agent Layer 4A — Native-first Rule Authoring

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.2 (W3 native-first 定义) + §5.5 (Layer 4 拆分) + 用户指导（先做 4A，不做 4B/4C）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4A-01 | 只做 native ephemeral 执行 | v1.1-delta §4.2 + 用户 2026-04-10 指导 |
| L4A-02 | 规则先走 validate + compile-preview，再允许 register | 用户 2026-04-10 指导 |
| L4A-03 | review 默认还是 steps-first | delta D-05 |
| L4A-04 | 非 native 规则只允许导出/预览，不在 session 内执行 | v1.1-delta §4.2 Level 3 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4A-05 | 不用 DraftManager 管理规则 | 规则不写 ledger、不产生 assertion_id、无 append-only 语义 |
| L4A-06 | register_and_evaluate_rule 一站式方法 | 减少 agent 调用轮数；validate→register→evaluate 是最常见的组合 |
| L4A-07 | EvaluateRequest 中 mode 固定为 "native" | 对齐 L4A-01；ephemeral rules 仅 native 可消费 |
| L4A-08 | tool registry 继续扩展 build_layer3a_tool_registry() | 与 W2a 累进模式一致 |
| L4A-09 | register_ephemeral 内置 defensive validate | validate→register 不是原子的；schema 可能在中间变更 |

## 2026-04-10 — 实现前收口修订 (5 处)

### 修订来源

用户 code review 发现 4 处 P1 + 1 处 P2。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4A-10 | **冻结** evaluate 失败语义：捕获 AgentRuntimeError，返回 (RegisterResult, EvaluateOutcome(status="error"))；未请求时返回 EvaluateOutcome(status="not_requested")；register 失败时返回 EvaluateOutcome(status="skipped") | EvaluateTools.evaluate() 内部 raise；四态 EvaluateOutcome 消除歧义（L4A-15 修订） |
| L4A-11 | **冻结** cold restart 后 ephemeral rules 全丢，不做 rehydrate | ephemeral 是实验性的；rehydrate 引入 schema 漂移风险；与 kernel 语义一致 |
| L4A-12 | **冻结** validate/compile-preview 是 souffle preflight，不是 native validation | rules_v1.py _SUPPORTED_MODES = {"souffle"}；与 native execute 是不同层面 |
| L4A-13 | **冻结** HttpRuntimeAPI 新增 _delete_json() helper | clear_ephemeral_rules 需要 DELETE；仿照现有 close_session 模式 |
| L4A-14 | 修正 derivation IR：target（非 target_pred_id）+ ruleref atom 格式 | 对齐 test_agent_layer2_workflow.py 和 runtime_v1.py 真实合同 |
| L4A-15 | 引入 EvaluateOutcome 四态（not_requested/ok/error/skipped）替代 EvaluateResult|None | 消除"未请求 evaluate"vs"evaluate 失败"的返回歧义 |
| L4A-16 | 修正章节编号（§6-§11 连续） | 新增 §6/§7 后漏更新后续编号 |

### 合同对齐验证

确认以下 runtime API 在 Layer 4A 中正确引用：
- `rules_v1.validate_rule(dto) → {ok, meta: {profile_effective, mode}}` ✓
- `rules_v1.compile_rule_preview(dto) → {ok, preview: {compiled_payload}}` ✓
- `runtime_v1.register_ephemeral_rule(sid, dto) → {ok, result: {rule_id, version, status, total_ephemeral}}` ✓
- `runtime_v1.list_ephemeral_rules(sid) → {ok, result: {ephemeral_rules, total}}` ✓
- `runtime_v1.clear_ephemeral_rules(sid) → {ok, result: {cleared}}` ✓
- `EvaluateTools.evaluate(request) → EvaluateResult` (Layer 2) ✓
- `ReadReviewOrchestrator._checkpoint()` ✓

## 2026-04-10 — Implementation closeout

### 结果

- 新建 `src/factpy_kernel/agent/tools/rules.py`，实现 Layer 4A 规则 authoring 数据模型与 `RuleTools`
- `src/factpy_kernel/agent/orchestrator.py` 接入 validate/preview/register/evaluate/list/clear 规则流，并维持 steps-first review + Layer 2 accept 复用
- `src/factpy_kernel/agent/framework.py` 在 `build_layer3a_tool_registry()` 上累进扩到 27 tools
- 新增 `test_agent_l4a_runtime_api.py` / `test_agent_l4a_rules.py` / `test_agent_l4a_workflow.py`

### 验证

- 定向：Layer 2/3A/W2a/4A 相关回归 54 tests 通过
- 全量：`python -m unittest discover -s src/factpy_kernel/tests` 通过

### 偏差记录

- `_runtime_api.py` 的 5 个 rule methods 与 `_delete_json()` helper 在实现前已存在于分支中，因此 Layer 4A 对 adapter 代码的实际改动小于 blueprint 初始估算；主要补的是 dedicated tests 和上层消费逻辑。
