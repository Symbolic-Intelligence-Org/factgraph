# Audit Log: Agent Layer 3A — 结构化最小写入

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §5.4 (Layer 3 定义) + 用户指导的 4 条冻结决策 + Layer 1/2 已实现代码的精确合同。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L3A-01 | 先做 structured commit，不做 free-form NL extraction | 用户 2026-04-10 指导 |
| L3A-02 | 所有写入必须经过 confirmed draft，agent 不可直接落盘 | 用户 2026-04-10 指导 |
| L3A-03 | 提交成功后必须把 assertion_id 回写到 draft 并 checkpoint | 用户 2026-04-10 指导 |
| L3A-04 | 写入只覆盖 fact set/add，不碰 retract/rule/doc | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L3A-05 | 不继承 ReadReviewOrchestrator，直接追加方法 | 写入方法需要访问 _draft_manager/_checkpoint_store；继承引入不必要层次 |
| L3A-06 | WriteTools.commit_draft 不调用 mark_committed | 职责分离：WriteTools 只做 "API call + result parse"，状态流转由 orchestrator 协调 |
| L3A-07 | 写入失败时 draft 回退到 rejected | 不让 confirmed draft 悬空；调用方可检查 WriteError 决定是否重建新 draft |
| L3A-08 | confirm_and_commit_many 单次末尾 checkpoint | 逐条 checkpoint 太贵；末尾一次性持久化 |
| L3A-09 | e_ref 使用简单拼接（Phase 1） | 快速可用；升级路径清晰（draft_to_write_request 是唯一改点） |
| L3A-10 | EvaluateTools session 绑定模式复用（持有 AgentSession 引用） | 与 L2-14 冻结决策一致 |

### Layer 2 → Layer 3A 合同对齐验证

确认以下已实现合同在 Layer 3A 中正确引用：
- `DraftManager.create_draft(session_id, **kwargs) → FactDraft` ✓
- `DraftManager.confirm_draft(draft_id) → FactDraft` ✓
- `DraftManager.mark_committed(draft_id, asrt_id) → FactDraft` ✓
- `DraftManager.reject_draft(draft_id) → FactDraft` ✓
- `AgentScopeGuard().validate(draft, scope) → None | raise AgentScopeViolation` ✓
- `ReadReviewOrchestrator._checkpoint() → None` ✓
- `write_runtime_fact(session_id, dto, kind=kind) → {ok, write: {kind, assertion_id}}` ✓
- `kg_read._encode_entity_ref(schema_ir, entity_type, identity) → str` (encode_idref_v1) ✓

## 2026-04-10 — 实现前收口修订 (4 处)

### 修订来源

用户 code review 发现 4 处合同问题。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L3A-11 | e_ref 改为复用 kg_read._encode_entity_ref + encode_idref_v1，不用字符串拼接 | 读路径已使用 schema-aware 编码；写路径如果用拼接会产生不兼容 e_ref |
| L3A-12 | prepare_draft 改为先校验后入 manager；confirm_and_commit 追加 defensive re-check | scope 违规 draft 不应进入 DraftManager；消除绕过风险 |
| L3A-13 | approved_by 区分 agent_executor 和 confirmed_by（人类确认者） | 审计链需区分"谁执行"和"谁批准"；原方案把两者混为一体 |
| L3A-14 | confirm_and_commit_many 冻结为"内部变体不逐条 checkpoint + 末尾单次 checkpoint" | 消除与 confirm_and_commit 自带 checkpoint 的矛盾；明确崩溃恢复权衡 |
| L3A-15 | 抽取 `agent/tools/_entity_ref.py` 共享 helper，读写共用 schema-aware idref 编码 | Layer 3A 实现时顺手消化 residual，避免 write.py 依赖 `kg_read` 私有函数 |

## 2026-04-10 — 实施完成

### 交付文件

- `src/factpy_kernel/agent/tools/_runtime_api.py`
- `src/factpy_kernel/agent/tools/_entity_ref.py`
- `src/factpy_kernel/agent/tools/write.py`
- `src/factpy_kernel/agent/orchestrator.py`
- `src/factpy_kernel/agent/framework.py`
- `src/factpy_kernel/agent/tools/__init__.py`
- `src/factpy_kernel/agent/__init__.py`
- `src/factpy_kernel/agent/docs/README.md`
- `src/factpy_kernel/tests/test_agent_layer3a_runtime_api.py`
- `src/factpy_kernel/tests/test_agent_layer3a_write.py`

### 结果摘要

| # | 实现结果 | 说明 |
|---|----------|------|
| L3A-R1 | RuntimeAPI 写入扩展落地 | Local/HTTP 两个实现均支持 `write_fact()` |
| L3A-R2 | `WriteTools` 落地 | confirmed draft → schema-aware e_ref → runtime write → `WriteResult/WriteError` |
| L3A-R3 | Orchestrator 写入流落地 | `prepare_draft` / `confirm_and_commit` / `confirm_and_commit_many` / `list_committed_drafts` 完整 |
| L3A-R4 | Layer 3A tool registry 落地 | 工具数从 16 扩到 20 |
| L3A-R5 | 审计链字段落地 | `approved_by` / `agent_executor` / `trace_id` 在写入 meta 中可见 |

### 偏差与收口

| # | 偏差 | 结论 |
|---|------|------|
| L3A-D1 | 共享 entity_ref helper 直接实现，而不是延后 | 采纳；读写统一复用 `agent/tools/_entity_ref.py` |
| L3A-D2 | `confirm_and_commit_many()` 对 per-item contract/scope 失败也降为 `WriteError` | 采纳；保持 batch best-effort，不因单条异常中断 |
| L3A-D3 | 单条 commit 的 scope re-check 失败也 checkpoint rejected 状态 | 采纳；保证 DraftManager 与 checkpoint 一致 |

### 验证

- `python -m py_compile` 覆盖 Layer 3A 变更文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer2_runtime_api src.factpy_kernel.tests.test_agent_layer2_workflow src.factpy_kernel.tests.test_agent_layer3a_runtime_api src.factpy_kernel.tests.test_agent_layer3a_write`：通过（24 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（795 tests）
