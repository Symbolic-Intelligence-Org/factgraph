# Blueprint: Agent Layer 2 — Read-first Agent

- Status: implemented
- Created: 2026-04-09
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: Layer 1 控制面 MVP (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/tools/_runtime_api.py` (扩展)
  - `src/factpy_kernel/agent/tools/kg_read.py` (只读依赖)
  - `src/factpy_kernel/agent/tools/explain.py` (只读依赖)
  - `src/factpy_kernel/agent/tools/evaluate.py` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (新建)
  - `src/factpy_kernel/agent/framework.py` (扩展)
  - `src/factpy_kernel/agent/candidate_cache.py` (只读依赖)
  - `src/factpy_kernel/agent/recovery.py` (只读依赖)
  - `src/factpy_kernel/agent/docs/README.md` (更新)

---

## 0. 目标与边界

**交付目标**：agent 能读取 KG 状态、消费 explain surface、跑通 evaluate→cache→review→accept 完整 loop。

**冻结决策**（来自用户指导）：

| # | 决策 | 理由 |
|---|------|------|
| L2-01 | accept 只接受当前 runtime_session 的 active cached candidate | 防止 stale candidate 误 accept；cold restart 后必须重新 evaluate |
| L2-02 | review 默认载体是 steps，不是 narrative/NL | steps 已线性化三引擎，最适合 agent 中间推理（delta D-05） |
| L2-03 | evaluate 后由 agent 侧自动写入 CandidatePayloadCache | 这是 accept 恢复链路的真实底座（delta D-06） |
| L2-04 | cache miss / stale candidate 返回结构化 recovery outcome，不做隐式重算 | agent 不应隐式替用户做决策；stale 必须显式提示"需重新 evaluate" |

**明确排除**：
- 事实生成 / 规则生成 / 文档提取
- semantic retract / impact analysis
- kernel-side candidate readback 新端点
- 任何 LLM 驱动的意图识别或 NL 生成（Layer 3）

---

## 1. 需要扩展的 Layer 1 合同

### 1.1 RuntimeAPI Protocol 扩展

Layer 1 的 `RuntimeAPI` 缺少 evaluate 和 accept 方法。Layer 2 需追加：

```python
# 追加到 RuntimeAPI Protocol
class RuntimeAPI(Protocol):
    # ... Layer 1 existing methods ...

    def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        """
        对齐 evaluate_runtime_derivation(session_id, dto)。

        真实 DTO 结构（runtime_v1.py:1438 _compile_runtime_derivation）:
        {
            "derivation": {              # 结构化 derivation IR（非 DSL 字符串）
                "derivation_id": str,
                "version": str,
                "target_pred_id": str,
                "head_vars": list[str],
                "where": list[...],      # 结构化 where IR（非字符串 DSL）
                "mode": "native" | "souffle" | "problog" | "pyreason",
                "head": dict | None,
                "engine_ext": dict | None,
            },
            "limit": int | None,         # 顶层，不在 derivation 内
        }

        返回: ok_response(meta={mode, candidate_count, returned_count, truncated},
                         evaluation={derivation_id, version, target_pred_id, candidates: [...]})
        """
        ...

    def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        """
        对齐 accept_runtime_derivation(session_id, dto)。
        dto 结构: {
            "candidate": dict,       # 完整 candidate payload（_candidate_to_dict 输出）
            "options": {             # 可选
                "dry_run": bool,
                "skip_accept_writes": bool,
            } | None,
        }
        返回: ok_response(meta={dry_run, terminal}, accept={...})
        """
        ...
```

### 1.2 LocalRuntimeAPI / HttpRuntimeAPI 扩展

```python
# LocalRuntimeAPI 追加
def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return runtime_v1.evaluate_runtime_derivation(session_id, dto)

def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return runtime_v1.accept_runtime_derivation(session_id, dto)

# HttpRuntimeAPI 追加
def evaluate_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return self._post_json(f"/sessions/{session_id}/derivations/evaluate", dto)

def accept_derivation(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return self._post_json(f"/sessions/{session_id}/derivations/accept", dto)
```

---

## 2. EvaluateTools — 新增 Tool 层

### 2.1 数据模型

```python
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class EvaluateRequest:
    """
    Agent 构造的 evaluate 请求。

    对齐真实 DTO 结构：顶层 {"derivation": {...}, "limit": ...}。
    derivation 内部是结构化 IR，不是 DSL 字符串。
    where IR 由 Layer 3/4 构造（NL→IR 翻译），Layer 2 不负责。

    见 runtime_v1.py:1438 _compile_runtime_derivation。
    """
    derivation: dict[str, Any]                  # 结构化 derivation IR（原样传给 runtime）
    limit: int | None = None

    def to_dto(self) -> dict[str, Any]:
        """生成传给 RuntimeAPI.evaluate_derivation 的完整 DTO。"""
        dto: dict[str, Any] = {"derivation": self.derivation}
        if self.limit is not None:
            dto["limit"] = self.limit
        return dto


@dataclass
class EvaluateResult:
    """Evaluate 的结构化返回。"""
    derivation_id: str
    version: str
    target_pred_id: str
    mode: str
    candidate_count: int                        # 总候选数
    returned_count: int                         # 截断后返回数
    truncated: bool
    candidates: list[dict[str, Any]]            # 完整 candidate payloads


@dataclass
class CandidateReviewItem:
    """单个 candidate 的 review 视图。"""
    candidate_id: str
    pred_id: str
    payload: dict[str, Any]                     # 完整 candidate payload
    summary: dict[str, Any] | None = None       # ExplainSummary.summary (raw)
    steps: list[dict[str, Any]] | None = None   # ExplainStep dicts
    cache_status: Literal["active", "stale", "missing"] = "active"


@dataclass
class AcceptRequest:
    """Agent 构造的 accept 请求。"""
    candidate: dict[str, Any]                   # 完整 candidate payload
    dry_run: bool = False


@dataclass
class AcceptResult:
    """Accept 的结构化返回。"""
    candidate_id: str
    dry_run: bool
    terminal: bool                              # accept 是否完成（vs 需要更多步骤）
    accept_detail: dict[str, Any]               # runtime 原始 accept response


@dataclass
class CacheRecoveryOutcome:
    """
    Cache miss 或 stale 时的结构化返回。
    不做隐式重算（L2-04）。
    """
    candidate_id: str
    status: Literal["stale", "missing"]
    message: str                                # 人类可读描述
    stale_runtime_session_id: str | None = None # stale 时的旧 session ID
    action_required: str = "re-evaluate"        # 固定为 "re-evaluate"
```

### 2.2 EvaluateTools 接口

```python
class EvaluateTools:
    """
    Evaluate → Cache → Review → Accept 完整 loop 的 tool 层。

    依赖：
    - RuntimeAPI（扩展后含 evaluate_derivation / accept_derivation）
    - CandidatePayloadCache（Layer 1）
    - ExplainTools（Layer 1，用于 review 时拉取 steps）
    """

    def __init__(
        self,
        *,
        runtime_api: RuntimeAPI,
        candidate_cache: CandidatePayloadCache,
        explain_tools: ExplainTools,
        session: AgentSession,
    ) -> None:
        """
        session 绑定策略：持有 AgentSession 引用（非快照）。
        每次 evaluate/review/accept 从 session.runtime_session_id 动态读取当前值。
        cold restart 后 session.runtime_session_id 会变更，EvaluateTools 自动跟随。
        """
        ...

    @property
    def _runtime_session_id(self) -> str:
        """动态读取，不快照。cold restart 后自动指向新 runtime session。"""
        rid = self._session.runtime_session_id
        if rid is None:
            raise AgentRuntimeError("AgentSession not bound to runtime session")
        return rid

    @property
    def _agent_session_id(self) -> str:
        return self._session.agent_session_id

    def evaluate(self, request: EvaluateRequest) -> EvaluateResult:
        """
        1. 调用 runtime_api.evaluate_derivation(self._runtime_session_id, request.to_dto())
        2. 解析 response → EvaluateResult
        3. 自动写入 CandidatePayloadCache（L2-03）:
           cache.store(self._agent_session_id, self._runtime_session_id, result.candidates)
        4. 返回 EvaluateResult

        session_id 从 self._runtime_session_id 动态获取。
        失败时 raise AgentRuntimeError。
        """
        ...

    def review_candidate(
        self,
        candidate_id: str,
        *,
        include_steps: bool = True,
        include_summary: bool = True,
    ) -> CandidateReviewItem | CacheRecoveryOutcome:
        """
        1. 从 CandidatePayloadCache 查找 candidate payload
           - lookup_active(self._runtime_session_id, candidate_id)
           - 如果 miss → 检查是否 stale（list_stale）
           - 如果 stale → 返回 CacheRecoveryOutcome(status="stale")
           - 如果完全 miss → 返回 CacheRecoveryOutcome(status="missing")

        2. 如果 active：构造 CandidateReviewItem
           - 从 cache 取 payload
           - 如果 include_summary: 调用 explain_tools.get_summary()
           - 如果 include_steps: 调用 explain_tools.get_steps()（L2-02 默认载体）
           - cache_status = "active"

        3. 返回 CandidateReviewItem
        """
        ...

    def review_all(
        self,
        *,
        include_steps: bool = False,
        include_summary: bool = True,
    ) -> list[CandidateReviewItem | CacheRecoveryOutcome]:
        """
        批量 review 当前 runtime session 的所有 cached candidates。
        用于 evaluate 后一次性展示所有候选。

        注意：include_steps 默认 False（批量时逐个拉 steps 开销大）。
        单个深入 review 时再调 review_candidate(..., include_steps=True)。
        """
        ...

    def accept_candidate(
        self,
        candidate_id: str,
        *,
        dry_run: bool = False,
    ) -> AcceptResult | CacheRecoveryOutcome:
        """
        1. 从 CandidatePayloadCache 查找 candidate payload（必须是 active）
           - 如果 stale/missing → 返回 CacheRecoveryOutcome（L2-04，不隐式重算）

        2. 构造 accept DTO: {"candidate": payload, "options": {"dry_run": dry_run}}

        3. 调用 runtime_api.accept_derivation(self._runtime_session_id, dto)

        4. 返回 AcceptResult

        L2-01 保证：只接受当前 runtime_session 的 active cached candidate。
        """
        ...

    def accept_many(
        self,
        candidate_ids: list[str],
        *,
        dry_run: bool = False,
    ) -> list[AcceptResult | CacheRecoveryOutcome]:
        """
        批量 accept。逐个调用 accept_candidate。
        任一条 stale/missing 不阻塞其余——返回混合列表。
        """
        ...
```

---

## 3. ReadReviewOrchestrator — 编排层

### 3.1 职责

将 Layer 1 的 tools 和 Layer 2 的 EvaluateTools 组合成完整的 read→review→accept 工作流。这是 Layer 3 (LLM 驱动 agent) 的直接调用基座。

```python
class ReadReviewOrchestrator:
    """
    Read-first / Review-first 工作流编排。

    不含 LLM 调用。不含事实/规则写入。
    纯粹是 tool 组合 + 状态协调 + recovery 处理。

    Layer 3 的 LLM agent 将通过此 orchestrator 的方法作为 tool 调用入口。
    """

    def __init__(
        self,
        *,
        session: AgentSession,
        draft_manager: DraftManager,
        kg_read_tools: KGReadTools,
        explain_tools: ExplainTools,
        evaluate_tools: EvaluateTools,
        candidate_cache: CandidatePayloadCache,
        checkpoint_store: AgentCheckpointStore,
    ) -> None: ...

    # ── Schema & Fact Read ──

    def get_schema(self) -> dict[str, Any]:
        """包装 kg_read_tools.get_schema_summary(session_id)。"""
        ...

    def query_claims(self, pred_id: str, e_ref: str | None = None) -> list[ClaimResult]:
        """包装 kg_read_tools.query_claims(session_id, pred_id, e_ref)。"""
        ...

    def get_entity(self, entity_type: str, identity: dict[str, object]) -> EntitySnapshot:
        """包装 kg_read_tools.get_entity_snapshot(session_id, ...)。"""
        ...

    def list_candidates(self, pred_id: str | None = None) -> list[CandidateSummary]:
        """包装 kg_read_tools.list_candidates(session_id, ...)。"""
        ...

    def list_rules(self, include_spec: bool = False) -> list[RuleSummary]:
        """包装 kg_read_tools.list_rules(session_id, ...)。"""
        ...

    # ── Explain (steps-first) ──

    def explain_summary(self, candidate_id: str) -> ExplainSummary:
        """包装 explain_tools.get_summary(session_id, candidate_id)。"""
        ...

    def explain_steps(self, candidate_id: str) -> list[ExplainStep]:
        """默认 explain 载体（L2-02）。"""
        ...

    def explain_tree(self, candidate_id: str) -> EvidenceTreeResult | None:
        """按需。Souffle/ProbLog/Native 支持。"""
        ...

    def explain_timeline(self, candidate_id: str) -> TimelineResult | None:
        """按需。PyReason 支持。"""
        ...

    # ── Evaluate → Review → Accept loop ──

    def evaluate(self, request: EvaluateRequest) -> EvaluateResult:
        """
        执行 evaluate + 自动缓存。
        调用后自动 checkpoint（save session + draft state）。
        """
        ...

    def review_candidate(
        self, candidate_id: str, *, include_steps: bool = True,
    ) -> CandidateReviewItem | CacheRecoveryOutcome:
        """
        Review 单个 candidate。默认含 steps（L2-02）。
        如果 stale/missing 返回 CacheRecoveryOutcome（L2-04）。
        """
        ...

    def review_all(self) -> list[CandidateReviewItem | CacheRecoveryOutcome]:
        """批量 review，summary only（steps 单个拉取时再加）。"""
        ...

    def accept(
        self, candidate_id: str, *, dry_run: bool = False,
    ) -> AcceptResult | CacheRecoveryOutcome:
        """
        Accept candidate。仅 active cached（L2-01）。
        调用后自动 checkpoint。
        """
        ...

    def accept_many(
        self, candidate_ids: list[str], *, dry_run: bool = False,
    ) -> list[AcceptResult | CacheRecoveryOutcome]:
        """批量 accept。逐个执行，mixed results。"""
        ...

    # ── Recovery ──

    def check_session_health(self) -> Literal["healthy", "runtime_lost"]:
        """
        探测 runtime_session 是否存活。
        如果失效，不自动恢复——返回 "runtime_lost" 让调用方决策。
        """
        ...

    def get_stale_candidates(self) -> list[dict[str, Any]]:
        """查询当前 agent session 的所有 stale candidates。"""
        ...
```

### 3.2 session_id 隐藏

Orchestrator 内部持有 `session.runtime_session_id`，所有方法不需要调用方传 session_id。这是刻意的——Layer 3 的 LLM agent 不应该知道 runtime_session_id 的存在。

### 3.3 自动 checkpoint

以下操作后自动调用 `checkpoint_store.save(self._session, self._draft_manager)`：
- `evaluate()`（新 candidates 缓存后）
- `accept()` / `accept_many()`（状态变更后）

Orchestrator 持有 `self._session: AgentSession` 和 `self._draft_manager: DraftManager`，
两者均为构造时注入的可变引用。checkpoint 时序列化当前状态。

读操作不 checkpoint。

---

## 4. Tool Registry 扩展

Layer 1 注册了 9 个 tool（读 + explain）。Layer 2 追加 evaluate/review/accept tools：

```python
# 追加到 build_tool_registry 或新建 build_layer2_tool_registry

LAYER2_TOOLS = {
    # ── Evaluate / Review / Accept ──
    "evaluate":          → orchestrator.evaluate
    "review_candidate":  → orchestrator.review_candidate
    "review_all":        → orchestrator.review_all
    "accept_candidate":  → orchestrator.accept
    "accept_many":       → orchestrator.accept_many

    # ── Recovery ──
    "check_session_health": → orchestrator.check_session_health
    "get_stale_candidates": → orchestrator.get_stale_candidates
}
```

Layer 2 总计 16 个 tool（9 Layer 1 + 7 Layer 2）。

---

## 5. Cold Restart 后的 Candidate 处理

### 5.1 行为定义

```
Cold restart 发生
  │
  ├─ recover_agent_session() 返回 RecoveryResult(mode="cold", stale_candidates=[...])
  │
  ├─ 旧 runtime_session_id 的 cached candidates 全部成为 stale
  │
  ├─ review_candidate(old_candidate_id)
  │   → CacheRecoveryOutcome(status="stale", action_required="re-evaluate")
  │
  ├─ accept_candidate(old_candidate_id)
  │   → CacheRecoveryOutcome(status="stale", action_required="re-evaluate")
  │   → 不执行 accept，不抛异常
  │
  └─ 恢复路径：
      1. 调用方检查 RecoveryResult.stale_candidates
      2. 对需要的 derivation 重新 evaluate
      3. 新 evaluate → 新 candidates → 新 cache entries (active)
      4. 对新 candidates 正常 review → accept
```

### 5.2 不做的事

- **不隐式重算**：cache miss 不触发 evaluate
- **不迁移 stale**：不把旧 payload 挪到新 session
- **不假装可 accept**：stale candidate 直接返回 CacheRecoveryOutcome

---

## 6. 实现顺序

```
Step 1: RuntimeAPI Protocol 扩展
        → 追加 evaluate_derivation / accept_derivation
        → LocalRuntimeAPI / HttpRuntimeAPI 实现
        → 单测：直接调用 runtime_v1 函数验证

Step 2: EvaluateTools 数据模型
        → EvaluateRequest / EvaluateResult / CandidateReviewItem
        → AcceptRequest / AcceptResult / CacheRecoveryOutcome
        → 纯数据模型，无逻辑

Step 3: EvaluateTools 实现
        → evaluate() + 自动缓存
        → review_candidate() + cache lookup + stale 检测
        → accept_candidate() + active-only 校验
        → review_all() / accept_many()
        → 单测：mock RuntimeAPI + 真实 CandidatePayloadCache

Step 4: ReadReviewOrchestrator
        → 组合 KGReadTools + ExplainTools + EvaluateTools
        → session_id 隐藏
        → 自动 checkpoint
        → 集成测试：真实 runtime_v1 + in-memory ledger

Step 5: Tool Registry 扩展
        → build_layer2_tool_registry
        → 16 tool 全量注册
        → 验证所有 tool binding 可调用
```

---

## 7. 目录结构增量

```
src/factpy_kernel/agent/
  ├── tools/
  │   ├── evaluate.py           # (新建) EvaluateTools + 数据模型
  │   └── _runtime_api.py       # (扩展) +evaluate_derivation +accept_derivation
  ├── orchestrator.py            # (新建) ReadReviewOrchestrator
  ├── framework.py               # (扩展) build_layer2_tool_registry
  └── tests/
      ├── test_evaluate_tools.py      # (新建)
      ├── test_orchestrator.py        # (新建)
      └── test_runtime_api_ext.py     # (新建)
```

---

## 8. 验收标准

1. **RuntimeAPI 扩展**：evaluate_derivation / accept_derivation 在 LocalRuntimeAPI 和 HttpRuntimeAPI 上均可调用
2. **Evaluate → Cache**：evaluate 后 CandidatePayloadCache 自动包含所有返回的 candidate
3. **Review**：review_candidate 默认返回 steps（L2-02），active candidate 可正常 review
4. **Accept**：只接受当前 runtime_session 的 active cached candidate（L2-01）
5. **Stale 处理**：cold restart 后，review/accept stale candidate 返回 CacheRecoveryOutcome（L2-04），不抛异常不隐式重算
6. **Orchestrator**：session_id 对调用方透明；evaluate/accept 后自动 checkpoint
7. **Tool 数量**：16 个（9 Layer 1 + 7 Layer 2）
8. **单测**：全部新增组件有单测覆盖
9. **集成测试**：至少一个 end-to-end 测试覆盖 evaluate→cache→review→accept→checkpoint 完整链路

---

## 9. 已知约束

1. **evaluate DTO 构造**：Layer 2 不负责从自然语言构造 EvaluateRequest——这是 Layer 3 的事。Layer 2 只接受结构化的 EvaluateRequest。
2. **accept 是逐个调用**：当前 runtime_v1 的 accept_runtime_derivation 是逐条 API。accept_many 是 agent 侧的循环，不是原子批量。
3. **explain 对未 accept 的 candidate**：explain_steps / explain_summary 对刚 evaluate 但未 accept 的 candidate 可能有限制（取决于 runtime 实现）。需要集成测试验证。
4. **dry_run accept**：dry_run=True 时 runtime 不写入 ledger，但仍需 candidate payload。用于用户预览 accept 效果。
5. **HttpRuntimeAPI 路由路径**：evaluate 和 accept 的真实 HTTP 路由需要与 app_v1.py 的 route 注册对齐——当前伪代码中的路径是推断值，实现时需验证。

---

## 10. Outcome / Deviations

### Delivered

- `src/factpy_kernel/agent/tools/_runtime_api.py`
  - 扩展 `RuntimeAPI` / `LocalRuntimeAPI` / `HttpRuntimeAPI`
  - 新增 `evaluate_derivation()` / `accept_derivation()`
- `src/factpy_kernel/agent/tools/evaluate.py`
  - 新增 `EvaluateRequest`
  - 新增 `EvaluateResult`
  - 新增 `CandidateReviewItem`
  - 新增 `AcceptRequest`
  - 新增 `AcceptResult`
  - 新增 `CacheRecoveryOutcome`
  - 新增 `EvaluateTools`
- `src/factpy_kernel/agent/orchestrator.py`
  - 新增 `ReadReviewOrchestrator`
- `src/factpy_kernel/agent/framework.py`
  - 新增 `build_layer2_tool_registry()`，tool 总数扩到 16
- `src/factpy_kernel/agent/docs/README.md`
  - 更新 Layer 2 read-first loop 的当前实现文档
- 新增测试：
  - `src/factpy_kernel/tests/test_agent_layer2_runtime_api.py`
  - `src/factpy_kernel/tests/test_agent_layer2_workflow.py`

### Key Deviations

1. **`EvaluateRequest.derivation` 保持 raw runtime IR**
   - Layer 2 不对 `target` / `target_pred_id` 做二次规范化
   - 直接把结构化 derivation object 透传给 runtime 编译面
   - 这是刻意选择：Layer 2 只负责 loop，不负责 authoring normalization

2. **`review_all()` 只覆盖当前 runtime session 的 active cached candidates**
   - stale candidates 不混在 `review_all()` 返回里
   - 统一通过 `get_stale_candidates()` 暴露
   - 这样避免把“当前可 review”与“历史诊断残留”混在一组列表里

3. **不引入新的 Layer 2 skeleton dataclass**
   - 本轮仅扩展 `framework.py` 的 tool registry
   - `ReadReviewOrchestrator` 作为 Layer 2 直接基座
   - 不额外发明第二套 agent skeleton carrier

### Validation

- `python -m py_compile` 覆盖 Layer 2 变更文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer2_runtime_api src.factpy_kernel.tests.test_agent_layer2_workflow`：通过（12 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（783 tests）
