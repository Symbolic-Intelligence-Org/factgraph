# Audit Log: Agent W2a — 精确撤回

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.1 (W2a 定义) + 用户指导（先补完变更闭环，再进 Layer 4）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| W2a-01 | 只做 exact asrt_id retract | v1.1-delta §4.1 |
| W2a-02 | retract 必须 explicit confirm | 用户 2026-04-10 指导 |
| W2a-03 | 不做下游影响评估 | v1.1-delta §4.1 |
| W2a-04 | retract 前展示目标 assertion 全貌 | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| W2a-05 | 不使用 DraftManager 管理 retract | FactDraft 的字段（entity_type, pred_id, field_values）不适配 retract 的语义（只需 asrt_id）；确认链通过 preview→confirm 调用时序保证 |
| W2a-06 | 幂等处理：重复撤回返回 RetractResult 不报错 | 对齐 runtime 的 retract_by_asrt 幂等语义 |
| W2a-07 | approved_by 语义与 Layer 3A 一致（confirmed_by + agent_executor 分离） | 审计链一致性 |
| W2a-08 | preview_retract 对已撤回 assertion 仍返回结果（is_revoked=True） | 让调用方知道目标已被撤回，自行决定是否继续 |
| W2a-09 | **冻结**：preview_retract 用 adapter 层全量扫描 claims，不新增 runtime endpoint | query_claims 不支持 asrt_id 过滤；全量扫描是当前代码现实下的唯一路径；按 asrt_id 查询留后续优化 |
| W2a-10 | **冻结**：tool registry 扩展 build_layer3a_tool_registry()，不新建独立 builder | 与 Layer 1/2/3A 的累进 registry 模式一致 |

## 2026-04-10 — 实现前收口修订 (3 处)

### 修订来源

用户 code review 发现 2 处实现分叉未冻结 + 1 处文档不一致。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| W2a-09 | preview_retract 冻结为 adapter 全量扫描 | 消除"全量扫描 or 新增 endpoint"的分叉 |
| W2a-10 | tool registry 冻结为扩展 build_layer3a_tool_registry | 消除"新建 builder or 扩展现有"的分叉 |
| W2a-11 | retract DTO 文档补齐 approved_by / agent_executor 字段 | 消除第 1 节和第 2 节的文档矛盾 |

### Layer 3A → W2a 合同对齐验证

确认以下已实现合同在 W2a 中正确引用：
- `retract_runtime_fact(session_id, {"asrt_id": str, "meta": {...}}) → {ok, write: {kind, assertion_id}}` ✓
- `ReadReviewOrchestrator._checkpoint()` ✓
- `KGReadTools.query_claims(session_id, pred_id, e_ref)` ✓
- `ClaimResult.is_revoked` ✓
- `AgentSession.scope.agent_id` ✓

## 2026-04-10 — 实现完成

### 实现摘要

- RuntimeAPI 新增 `retract_fact()`，Local/HTTP 两条 adapter 均接入现有 `writes/retract`
- `WriteTools` 新增 `RetractRequest` / `RetractResult` / `RetractError` 与 `retract()`
- `ReadReviewOrchestrator` 新增 `preview_retract()` / `confirm_and_retract()`
- `build_layer3a_tool_registry()` 扩展到 22 tools
- W2a 新增两组测试：runtime API dispatch + exact retract workflow

### 结果

- W2a-01 / 02 / 03 / 04 全部兑现
- W2a-09 / 10 的冻结路径按原样落地
- 无新增 runtime endpoint、无 semantic retract、无 dependency scan
