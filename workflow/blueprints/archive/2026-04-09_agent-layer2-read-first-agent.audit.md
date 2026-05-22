# Audit Log: Agent Layer 2 — Read-first Agent

## 2026-04-09 — 初始设计

### 设计依据

基于 v1.1-delta §5.3 (Layer 2 定义) + 用户指导的 4 条冻结决策 + Layer 1 已实现代码的精确合同。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L2-01 | accept 只接受当前 runtime_session 的 active cached candidate | 用户 2026-04-09 指导 |
| L2-02 | review 默认载体是 steps | delta D-05 + 用户确认 |
| L2-03 | evaluate 后由 agent 侧自动写入 CandidatePayloadCache | delta D-06 |
| L2-04 | cache miss / stale 返回结构化 recovery outcome，不隐式重算 | 用户 2026-04-09 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L2-05 | RuntimeAPI Protocol 扩展（追加 evaluate/accept），不新建 Protocol | 保持单一 Protocol，避免多 Protocol 组合复杂度 |
| L2-06 | EvaluateTools 作为独立 Tool 层（不合并到 KGReadTools） | evaluate/accept 是写操作语义，与 read tools 分离 |
| L2-07 | ReadReviewOrchestrator 隐藏 session_id | Layer 3 LLM agent 不应知道 runtime_session_id |
| L2-08 | accept_many 是逐条循环，不是原子批量 | runtime_v1 无原子批量 accept；逐条允许 mixed results |
| L2-09 | review_all 默认 summary-only（不含 steps） | 批量拉 steps 开销大；单个深入 review 时再加 |
| L2-10 | Orchestrator evaluate/accept 后自动 checkpoint | 状态变更后必须持久化，防止丢失 |

### Layer 1 → Layer 2 合同对齐验证

确认以下 Layer 1 合同在 Layer 2 中正确引用：
- `CandidatePayloadCache.store(agent_session_id, runtime_session_id, candidates)` ✓
- `CandidatePayloadCache.lookup_active(runtime_session_id, candidate_id)` ✓
- `CandidatePayloadCache.list_stale(agent_session_id, current_runtime_session_id)` ✓
- `ExplainTools.get_summary() → ExplainSummary(kind, summary, certainty_summary)` ✓
- `ExplainTools.get_steps() → list[ExplainStep]` ✓
- `AgentCheckpointStore.save(session, draft_manager)` ✓
- `RecoveryResult(mode="warm"|"cold", stale_candidates=[...])` ✓

## 2026-04-09 — 实现前收口修订 (3 处)

### 修订来源

用户 code review 发现 3 处合同与真实 runtime API / Layer 1 实现不匹配。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L2-11 | EvaluateRequest 改为 request-body model: `derivation: dict + limit: int|None + to_dto()` | 真实 DTO 是 `{"derivation": {...}, "limit": ...}`，不是扁平结构；where 是结构化 IR 不是 `list[dict]` |
| L2-12 | ReadReviewOrchestrator 显式注入 DraftManager | `AgentCheckpointStore.save()` 强制需要 `session + draft_manager`；无 DraftManager 则 checkpoint 合同不成立 |
| L2-13 | EvaluateTools 从 AgentSession 动态读 runtime_session_id，不构造时快照 | cold restart 后 `session.runtime_session_id` 会变；快照会把新 cache 写到旧 runtime 分区 |
| L2-14 | **冻结**：EvaluateTools session binding = 持有 `AgentSession` 引用 + `_runtime_session_id` property 动态读取 | 防止实现时退化为构造时快照；这是与 Layer 1 cold-restart 语义兼容的唯一正确方式 |

## 2026-04-09 — 实施完成

### 交付文件

- `src/factpy_kernel/agent/tools/_runtime_api.py`
- `src/factpy_kernel/agent/tools/evaluate.py`
- `src/factpy_kernel/agent/orchestrator.py`
- `src/factpy_kernel/agent/framework.py`
- `src/factpy_kernel/agent/__init__.py`
- `src/factpy_kernel/agent/tools/__init__.py`
- `src/factpy_kernel/agent/docs/README.md`
- `src/factpy_kernel/tests/test_agent_layer2_runtime_api.py`
- `src/factpy_kernel/tests/test_agent_layer2_workflow.py`

### 结果摘要

| # | 实现结果 | 说明 |
|---|----------|------|
| L2-R1 | RuntimeAPI 扩展落地 | Local/HTTP 两个实现均支持 `evaluate_derivation` / `accept_derivation` |
| L2-R2 | `EvaluateTools` 落地 | evaluate→cache→review→accept loop 完整，遵守 active-only accept 合同 |
| L2-R3 | `ReadReviewOrchestrator` 落地 | 隐藏 runtime_session_id，统一 schema/read/explain/evaluate/review/accept surface |
| L2-R4 | Layer 2 tool registry 落地 | 工具数从 9 扩到 16 |
| L2-R5 | stale/missing contract 落地 | 统一返回 `CacheRecoveryOutcome`，不做隐式重算 |

### 偏差与收口

| # | 偏差 | 结论 |
|---|------|------|
| L2-D1 | `EvaluateRequest.derivation` 保持 raw runtime IR | 采纳；Layer 2 不承担 authoring normalization |
| L2-D2 | `review_all()` 不混入 stale outcomes | 采纳；stale 统一通过 `get_stale_candidates()` 暴露 |
| L2-D3 | 未引入单独 Layer 2 skeleton carrier | 采纳；只扩展 `framework.py` 的 tool registry，`ReadReviewOrchestrator` 即 Layer 2 基座 |

### 验证

- `python -m py_compile` 覆盖 Layer 2 变更文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer2_runtime_api src.factpy_kernel.tests.test_agent_layer2_workflow`：通过（12 tests）
- `python -m unittest src.factpy_kernel.tests.test_agent_layer1_models src.factpy_kernel.tests.test_agent_layer1_tools`：通过（17 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（783 tests）

## 2026-04-09 — 进入 implementing

### 本轮实现顺序

1. `tools/_runtime_api.py` 扩展 evaluate/accept
2. `tools/evaluate.py` 数据模型 + EvaluateTools
3. `orchestrator.py` ReadReviewOrchestrator + 自动 checkpoint
4. `framework.py` Layer 2 tool registry 扩展
5. Layer 2 单测与模块文档更新

### 实施约束

- 不新增 kernel-side endpoint；仅消费现有 runtime/service surface。
- `accept` 只允许当前 runtime session 的 active cached candidate。
- stale/missing candidate 统一返回结构化 recovery outcome，不做隐式重算。
