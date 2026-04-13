# Audit Log: Agent Layer 1 — 控制面 MVP

## 2026-04-09 — 初始设计

### 设计依据

基于 v1.1-delta 蓝图 §5.2 (Layer 1 定义) + 用户提出的 4 点收紧 + 6 小节设计框架要求。

### 用户指定的 6 小节结构

1. AgentSession 数据模型
2. RuntimeBootstrapSpec
3. DraftManager 最小合同
4. CandidatePayloadCache 表结构
5. KGReadTools / ExplainTools 方法签名
6. Warm/Cold Recovery 两条时序

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L1-01 | AgentSession 不持有 RuntimeSession 对象引用 | 松耦合；RuntimeSession 是进程内 dict，可能消失 |
| L1-02 | RuntimeBootstrapSpec 完整存储 schema_ir | 简化 cold restart；大 schema 优化留后续 |
| L1-03 | DraftManager 不做持久化 I/O | 纯内存 + checkpoint 序列化；持久化由 Burr 负责 |
| L1-04 | CandidatePayloadCache 共用 Burr SQLite | 减少连接管理复杂度；用独立表隔离 |
| L1-05 | Cold restart 后旧 candidate 标记 stale 不删除 | 保留供诊断；agent 需重新 evaluate |
| L1-06 | 实现顺序：数据模型 → cache → draft → tools → recovery → burr | 依赖链从底向上 |
| L1-07 | KGReadTools 是 adapter 组合层 | 当前 runtime API 无 query_entity endpoint |
| L1-08 | ExplainTools 按引擎分支返回 tree/timeline | 不做统一——引擎差异是设计选择（ADR v2） |

## 2026-04-09 — 实现前收口修订 (4 处)

### 修订来源

用户 code review 发现 4 处 contract 与真实 runtime API surface 不匹配。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L1-09 | CandidatePayloadCache 主键改为 `(agent_session_id, runtime_session_id, candidate_id)` | 解决 cold restart 后 stale 保留 vs session close 清理的语义冲突；`evict_agent_session()` 一次清整个 agent 生命周期 |
| L1-10 | RuleSummary 降为 `rule_id/version/source` + optional spec | `GET /sessions/{id}/rules` 真实返回只有这些字段；rule_label/head_pred_id/engine 不在 inventory 中 |
| L1-11 | ExplainSummary 改为 raw-first `{kind, summary: dict, certainty_summary: dict|None}` | runtime 有两种 summary 合同（tree 12-field vs timeline 6-field）；过早统一会造成伪统一 adapter |
| L1-12 | RuntimeBootstrapSpec 改为保存完整 `open_dto: dict` | 对齐真实 `open_runtime_session(dto: dict)` → `resp["session"]["session_id"]`；避免伪代码误导实现 |

## 2026-04-09 — 进入 implementing

### 本轮实现顺序

1. `session.py` / `draft.py` / `candidate_cache.py`
2. `tools/kg_read.py` / `tools/explain.py`
3. `recovery.py`
4. `agent/docs/README.md` + 仓库 docs index
5. Layer 1 单测与回归

### 实施约束

- Layer 1 不引入真实 LLM model call；`PydanticAI` / `Burr` 只保留 skeleton 对接点或可选集成边界。
- 现有 runtime/service 代码保持只读依赖；Layer 1 先以 adapter 组合现有 API 为主。
- 若实现中发现需要 kernel-side 新 endpoint 或新 DTO，必须先回蓝图补 scope，再继续编码。

## 2026-04-09 — 实施完成

### 交付文件

- `src/factpy_kernel/agent/__init__.py`
- `src/factpy_kernel/agent/errors.py`
- `src/factpy_kernel/agent/session.py`
- `src/factpy_kernel/agent/draft.py`
- `src/factpy_kernel/agent/candidate_cache.py`
- `src/factpy_kernel/agent/recovery.py`
- `src/factpy_kernel/agent/framework.py`
- `src/factpy_kernel/agent/tools/__init__.py`
- `src/factpy_kernel/agent/tools/_runtime_api.py`
- `src/factpy_kernel/agent/tools/kg_read.py`
- `src/factpy_kernel/agent/tools/explain.py`
- `src/factpy_kernel/agent/docs/README.md`
- `src/factpy_kernel/tests/test_agent_layer1_models.py`
- `src/factpy_kernel/tests/test_agent_layer1_tools.py`
- `docs/README.md`

### 结果摘要

| # | 实现结果 | 说明 |
|---|----------|------|
| L1-R1 | `AgentSession` / `RuntimeBootstrapSpec` / `AgentScope` 落地 | 含 checkpoint roundtrip、warm/cold 绑定语义 |
| L1-R2 | `DraftManager` 落地 | 纯内存 CRUD + 状态流转 + checkpoint/restore |
| L1-R3 | `CandidatePayloadCache` 落地 | SQLite 三段主键 `(agent_session_id, runtime_session_id, candidate_id)` |
| L1-R4 | `KGReadTools` / `ExplainTools` 落地 | 组合现有 runtime surface，遵循 raw-first explain contract |
| L1-R5 | `AgentCheckpointStore` + `recover_agent_session()` 落地 | 实现 warm rebind / cold reopen + stale candidate 保留 |
| L1-R6 | `Layer1AgentSkeleton` 落地 | 只做 tool registry / dependency probe / tracing plumbing，不发 model call |

### 偏差与收口

| # | 偏差 | 结论 |
|---|------|------|
| L1-D1 | 未接真实 Burr/PydanticAI/Langfuse | 保持为 optional dependency probe + pure-Python fallback；符合 Layer 1 “无 model call”边界 |
| L1-D2 | `query_claims()` 放宽为 `pred_id` 可选 | 采纳；与 runtime `list_runtime_claims(pred_id=None)` 合同一致，并简化 `get_entity_snapshot()` |
| L1-D3 | `get_entity_snapshot()` 未做 predicate fan-out | 采纳；改为 `encode_idref_v1 + query by e_ref`，更贴当前 runtime surface |
| L1-D4 | `ExplainTools.get_timeline()` 增加 adapter fallback | 采纳；用于兼容当前 runtime 在非 timeline 候选上的伪 unsupported 异常 |

### 验证

- `python -m py_compile` 覆盖新增 agent 文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer1_models src.factpy_kernel.tests.test_agent_layer1_tools`：通过（17 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（771 tests）
