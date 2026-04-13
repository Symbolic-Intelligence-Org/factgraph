# Blueprint: Agent Layer 3A — 结构化最小写入

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: Layer 2 Read-first Agent (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/tools/_runtime_api.py` (扩展)
  - `src/factpy_kernel/agent/tools/write.py` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)
  - `src/factpy_kernel/agent/draft.py` (只读依赖)
  - `src/factpy_kernel/agent/session.py` (只读依赖: AgentScopeGuard)

---

## 0. 目标与边界

**交付目标**：给定结构化 FactDraft，经 scope 校验 + 用户确认后写入 ledger，成功后回写 assertion_id 并 checkpoint。

**冻结决策**：

| # | 决策 | 理由 |
|---|------|------|
| L3A-01 | 先做 structured commit，不做 free-form NL extraction | NL→FactDraft 是 Layer 4 的事；本层输入已经是结构化 draft |
| L3A-02 | 所有写入都必须经过 confirmed draft，agent 不可直接落盘 | draft confirm 是审计链的锚点；无 confirmed draft = 无 approved_by |
| L3A-03 | 提交成功后必须把 assertion_id 回写到 draft 并 checkpoint | mark_committed(draft_id, asrt_id) + _checkpoint()；断线后可追溯 |
| L3A-04 | 写入只覆盖 fact set/add 的最小路径，不碰 retract/rule/doc ingest | retract 是 v1.1-delta 的 W2a（独立交付），规则/文档是 Layer 4+ |

**明确排除**：
- NL→FactDraft 自由生成 / 意图识别 / slot filling
- retract（W2a，独立蓝图）
- 规则创建 / 文档提取
- batch 原子性（当前 ledger 不支持分布式事务）

---

## 1. RuntimeAPI Protocol 扩展

Layer 2 已追加 evaluate/accept。Layer 3A 追加 write_fact：

```python
# 追加到 RuntimeAPI Protocol
class RuntimeAPI(Protocol):
    # ... Layer 1 + Layer 2 existing methods ...

    def write_fact(
        self, session_id: str, dto: dict[str, Any], *, kind: str,
    ) -> dict[str, Any]:
        """
        对齐 write_runtime_fact(session_id, dto, kind=kind)。

        kind: "set" | "add"
          - "set": 单值谓词写入（覆盖语义）
          - "add": 多值谓词追加

        dto 结构 (runtime_v1.py:234):
        {
            "pred_id": str,           # 必填
            "e_ref": str,             # 必填（idref_v1 编码的实体引用）
            "rest_terms": [           # 必填
                [tag: str, value],    # 每项是 [tag, value] 二元组
                ...
            ],
            "meta": {                 # 可选
                "source": str,
                "source_loc": str,
                "trace_id": str,
                "confidence": float,  # (0, 1]
                "approved_by": str,
                "note": str,
            }
        }

        返回: ok_response(write={kind, assertion_id})
        错误: error_response([{kind, path, details}])
        """
        ...
```

### 1.1 LocalRuntimeAPI / HttpRuntimeAPI 扩展

```python
# LocalRuntimeAPI
def write_fact(self, session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]:
    return runtime_v1.write_runtime_fact(session_id, dto, kind=kind)

# HttpRuntimeAPI
def write_fact(self, session_id: str, dto: dict[str, Any], *, kind: str) -> dict[str, Any]:
    return self._post_json(f"/sessions/{session_id}/writes/{kind}", dto)
```

---

## 2. WriteTools — 新增 Tool 层

### 2.1 数据模型

```python
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class WriteRequest:
    """
    从 confirmed FactDraft 构造的写入请求。

    Layer 3A 不负责构造 FactDraft（那是 NL 层或调用方的事）。
    Layer 3A 负责：confirmed draft → WriteRequest → runtime API → 结果回写。
    """
    draft_id: str                               # 关联的 FactDraft.draft_id
    kind: Literal["set", "add"] = "set"         # 写入类型
    pred_id: str = ""
    e_ref: str = ""                             # idref_v1 编码
    rest_terms: list[list[Any]] = None          # [[tag, value], ...]
    meta: dict[str, Any] = None                 # source, confidence, approved_by, trace_id, ...

    def to_dto(self) -> dict[str, Any]:
        """生成传给 RuntimeAPI.write_fact 的 DTO。"""
        dto: dict[str, Any] = {
            "pred_id": self.pred_id,
            "e_ref": self.e_ref,
            "rest_terms": self.rest_terms or [],
        }
        if self.meta:
            dto["meta"] = self.meta
        return dto


@dataclass
class WriteResult:
    """写入成功的结构化返回。"""
    draft_id: str                               # 关联的 FactDraft.draft_id
    kind: str                                   # "set" | "add"
    assertion_id: str                           # 新 assertion 的 ID


@dataclass
class WriteError:
    """写入失败的结构化返回（不抛异常，允许 batch 场景混合结果）。"""
    draft_id: str
    kind: str
    error_kind: str                             # runtime error kind
    error_path: str                             # JSONPath
    error_message: str
```

### 2.2 FactDraft → WriteRequest 映射

```python
def draft_to_write_request(
    draft: FactDraft,
    *,
    schema_ir: dict[str, Any],
    kind: Literal["set", "add"] = "set",
    agent_id: str,
    confirmed_by: str | None = None,
    bundle_id: str | None = None,
) -> WriteRequest:
    """
    将 confirmed FactDraft 映射为 WriteRequest。

    映射规则（对齐 v1 蓝图 §4.1）：
    - entity_identity → e_ref: 复用共享 helper `agent/tools/_entity_ref.py`
      使用 encode_idref_v1 编码，与读路径完全一致
    - field_values → rest_terms: [(tag, value), ...] → [[tag, value], ...]
    - confidence → meta.confidence
    - source → meta.source
    - source_loc → meta.source_loc
    - note → meta.note
    - agent_id → meta.agent_executor（记录执行 agent）
    - confirmed_by → meta.approved_by（记录人类确认者，审计链关键字段）
    - bundle_id → meta.trace_id（可选，batch 场景用）

    注意 schema_ir 是必填参数——e_ref 编码需要 schema 中的
    identity_fields 定义来确定字段顺序和类型。
    """
    from ._entity_ref import encode_entity_ref

    e_ref = encode_entity_ref(schema_ir, entity_type=draft.entity_type, identity=draft.entity_identity)

    meta: dict[str, Any] = {}
    # 审计链：区分 agent executor 和 human confirmer
    meta["approved_by"] = confirmed_by or agent_id
    if confirmed_by and confirmed_by != agent_id:
        meta["agent_executor"] = agent_id
    if draft.confidence is not None:
        meta["confidence"] = draft.confidence
    if draft.source:
        meta["source"] = draft.source
    if draft.source_loc:
        meta["source_loc"] = draft.source_loc
    if draft.note:
        meta["note"] = draft.note
    if bundle_id:
        meta["trace_id"] = bundle_id

    return WriteRequest(
        draft_id=draft.draft_id,
        kind=kind,
        pred_id=draft.pred_id,
        e_ref=e_ref,
        rest_terms=[[tag, val] for tag, val in draft.field_values],
        meta=meta,
    )
```

### 2.3 WriteTools 接口

```python
class WriteTools:
    """
    结构化最小写入 tool 层。

    输入：已 confirmed 的 FactDraft。
    输出：WriteResult（成功）或 WriteError（失败）。

    不负责 NL 解析、draft 构造、scope 校验、confirm 流程。
    这些是 orchestrator 层或更上层的事。
    """

    def __init__(self, *, runtime_api: RuntimeAPI, session: AgentSession) -> None:
        """
        session 绑定策略：与 EvaluateTools 一致，持有 AgentSession 引用，
        动态读取 runtime_session_id（L2-14 冻结决策）。
        """
        ...

    def commit_draft(
        self,
        draft: FactDraft,
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> WriteResult | WriteError:
        """
        将 confirmed draft 提交到 ledger。

        前置条件（由调用方保证，此方法做 defensive check）：
        - draft.status == "confirmed"
        - session.scope 校验已通过

        步骤：
        1. Defensive check: draft.status == "confirmed"
        2. 获取 schema_ir（从 runtime API 的 get_schema 或 orchestrator 缓存）
        3. draft_to_write_request(draft, schema_ir=schema_ir,
               agent_id=session.scope.agent_id, confirmed_by=confirmed_by,
               bundle_id=bundle_id)
        4. runtime_api.write_fact(runtime_session_id, request.to_dto(), kind=kind)
        5. 检查 response["ok"]
           - True: 返回 WriteResult(draft_id, kind, assertion_id)
           - False: 返回 WriteError(draft_id, kind, error_kind, error_path, error_message)

        注意：此方法不调用 mark_committed。mark_committed 由 orchestrator 层负责
        （因为需要配合 checkpoint）。
        """
        ...

    def commit_many(
        self,
        drafts: list[FactDraft],
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
    ) -> list[WriteResult | WriteError]:
        """
        批量提交。逐条调用 commit_draft。

        当前 ledger 不支持分布式事务，所以这是"尽力提交"语义：
        - 任一条失败不阻塞其余
        - 返回 mixed list（WriteResult + WriteError 混合）
        - 调用方需检查每条结果
        """
        ...
```

---

## 3. Orchestrator 扩展

### 3.1 扩展策略

**不继承，直接在 ReadReviewOrchestrator 上追加方法。**

理由：Layer 3A 的写入方法需要访问 orchestrator 已有的 `_draft_manager`、`_checkpoint_store`、`session`。如果另建子类，会引入不必要的层次。保持单一 orchestrator 类，按 Layer 分方法组即可。

### 3.2 新增方法

```python
class ReadReviewOrchestrator:
    # ... Layer 2 existing methods ...

    # ── Layer 3A: Structured Write ──

    def prepare_draft(
        self,
        *,
        entity_type: str,
        entity_identity: dict[str, Any],
        pred_id: str,
        field_values: list[tuple[str, Any]],
        confidence: float | None = None,
        source: str | None = None,
        source_loc: str | None = None,
        note: str | None = None,
        conversation_turn: int = 0,
    ) -> FactDraft:
        """
        Scope 前置校验 + 创建 pending draft。

        1. 先构造临时 FactDraft 做 scope 校验（不入 manager）
        2. AgentScopeGuard().validate(temp_draft, session.scope)
           - 违反: raise AgentScopeViolation（manager 中无残留）
        3. 校验通过后才 draft_manager.create_draft(session_id=agent_session_id, ...)
        4. 返回 draft (status=pending)

        scope 违规的 draft 永远不会进入 DraftManager——消除绕过风险。
        """
        ...

    def confirm_and_commit(
        self,
        draft_id: str,
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> WriteResult | WriteError:
        """
        确认 + 提交 + 回写 assertion_id + checkpoint。

        完整时序：
        1. draft = draft_manager.get_draft(draft_id)
           - 不存在: raise AgentContractError
           - status != "pending": raise AgentContractError

        2. Defensive scope re-check:
           AgentScopeGuard().validate(draft, session.scope)
           - 违反: reject_draft + raise AgentScopeViolation
           （防止 prepare_draft 之后 scope 变更或 draft 被外部修改的绕过场景）

        3. draft_manager.confirm_draft(draft_id)
           → status: pending → confirmed

        4. write_tools.commit_draft(draft, kind=kind, bundle_id=bundle_id,
                                     confirmed_by=confirmed_by)

        5a. 如果 WriteResult:
            - draft_manager.mark_committed(draft_id, result.assertion_id)
            - _checkpoint()
            - 返回 WriteResult

        5b. 如果 WriteError:
            - draft_manager.reject_draft(draft_id)
              （写入失败的 draft 回退到 rejected，不留在 confirmed 状态）
            - _checkpoint()
            - 返回 WriteError

        L3A-02 保证：所有写入必须经过 confirmed draft。
        L3A-03 保证：成功后 assertion_id 回写到 draft 并 checkpoint。
        """
        ...

    def confirm_and_commit_many(
        self,
        draft_ids: list[str],
        *,
        kind: Literal["set", "add"] = "set",
        bundle_id: str | None = None,
        confirmed_by: str | None = None,
    ) -> list[WriteResult | WriteError]:
        """
        批量确认+提交。

        checkpoint 语义冻结：
        - 不逐条调用 confirm_and_commit（那会逐条 checkpoint）
        - 而是逐条调用内部 _confirm_and_commit_no_checkpoint() 变体
        - 全部完成后单次 _checkpoint()

        这意味着如果中途进程崩溃：
        - 已写入 ledger 的 assertion 存在（ledger 是持久化的）
        - 但 draft 的 committed 状态可能未持久化（checkpoint 未执行）
        - 恢复后需要对比 ledger 和 draft 状态来修复不一致
        - 这是可接受的权衡：checkpoint 开销 vs 崩溃恢复复杂度

        尽力提交语义：任一条失败不阻塞其余。
        bundle_id 相同——所有成功条目共享同一 trace_id，便于审计追溯。
        """
        ...

    def list_committed_drafts(self) -> list[FactDraft]:
        """查询当前 session 所有已 committed 的 draft（含 assertion_id）。"""
        return self._draft_manager.list_drafts(
            self.session.agent_session_id, status="committed",
        )
```

### 3.3 时序图

```
调用方（Layer 4 LLM agent 或测试）
  │
  ├─ 1. orchestrator.prepare_draft(entity_type=..., pred_id=..., ...)
  │     → FactDraft (status=pending)
  │     → 如果 scope 违反: raise AgentScopeViolation
  │
  ├─ 2. [展示 draft 给用户，获取确认]
  │     （Layer 3A 不负责这步——由调用方实现 UI/对话确认）
  │
  ├─ 3. orchestrator.confirm_and_commit(draft_id, kind="set")
  │     → pending → confirmed → write_runtime_fact → committed + checkpoint
  │     → 返回 WriteResult(assertion_id=...) 或 WriteError(...)
  │
  └─ 4. [向用户报告结果]
```

---

## 4. Tool Registry 扩展

Layer 2 注册了 16 个 tool。Layer 3A 追加写入 tools：

```python
LAYER3A_TOOLS = {
    "prepare_draft":            → orchestrator.prepare_draft
    "confirm_and_commit":       → orchestrator.confirm_and_commit
    "confirm_and_commit_many":  → orchestrator.confirm_and_commit_many
    "list_committed_drafts":    → orchestrator.list_committed_drafts
}
```

Layer 3A 总计 20 个 tool（16 Layer 2 + 4 Layer 3A）。

---

## 5. e_ref 构造策略

### 5.1 复用 kg_read 的 schema-aware 编码

Layer 3A 的 e_ref 构造复用共享 helper `agent/tools/_entity_ref.py` 中的 `encode_entity_ref(schema_ir, ...)`，该函数内部调用 `encode_idref_v1(entity_type, tuples)`。Layer 1 读路径与 Layer 3A 写路径都使用这同一 helper。

```python
from ._entity_ref import encode_entity_ref
e_ref = encode_entity_ref(schema_ir, entity_type=draft.entity_type, identity=draft.entity_identity)
```

**编码过程**：
1. 从 schema_ir.entities 中查找 entity_type 的 identity_fields 定义
2. 按 identity_fields 声明顺序提取 identity 值
3. 调用 `encode_idref_v1(entity_type, [(field_name, value), ...])` 生成标准 e_ref

**保证**：写入的 e_ref 与读路径完全一致——同一个 entity 的读写使用相同编码。

### 5.2 schema_ir 获取

`draft_to_write_request` 需要 `schema_ir` 参数。获取方式：
- Orchestrator / WriteTools 可直接调用 runtime schema endpoint 获取 `schema_ir`
- 或从 `AgentSession.bootstrap_spec.open_dto["schema_ir"]` 获取（如果使用内联 schema）

### 5.3 已解决的读写一致性问题

此前 Layer 1 读路径使用 `encode_idref_v1`，Layer 3A 写路径如果使用简单拼接，会产生不兼容的 e_ref。现在读写共用同一编码函数，彻底消除此风险。

---

## 6. 错误处理策略

### 6.1 scope 违反

`prepare_draft` 阶段 raise `AgentScopeViolation`。scope 违规 draft 不进入 manager；调用方需修正输入后重新创建 draft。

### 6.2 runtime 写入失败

`confirm_and_commit` 中 runtime 返回 `ok=False`：
- Draft 回退到 `rejected`（不留在 confirmed 状态）
- 返回 `WriteError`（不抛异常）
- 调用方可检查 error_kind/error_message 决定是否重试

### 6.3 写入失败后不回滚已成功条目

`confirm_and_commit_many` 的尽力提交语义：前面成功的 draft 已经 committed（assertion 已在 ledger 中），后面失败的 draft rejected。这与 v1 蓝图 §7.2 的设计一致。

---

## 7. 实现顺序

```
Step 1: RuntimeAPI Protocol 扩展
        → 追加 write_fact
        → LocalRuntimeAPI / HttpRuntimeAPI 实现
        → 单测

Step 2: WriteTools 数据模型 + draft_to_write_request
        → WriteRequest / WriteResult / WriteError
        → 映射函数
        → 纯数据模型 + 映射逻辑单测

Step 3: WriteTools.commit_draft / commit_many
        → 调用 RuntimeAPI + 解析 response
        → mock RuntimeAPI 单测

Step 4: Orchestrator 扩展
        → prepare_draft + confirm_and_commit + confirm_and_commit_many
        → scope 校验 + draft 状态流转 + checkpoint
        → 集成测试（真实 runtime_v1 + in-memory ledger）

Step 5: Tool Registry 扩展
        → build_layer3a_tool_registry
        → 20 tool 全量注册验证
```

---

## 8. 目录结构增量

```
src/factpy_kernel/agent/
  ├── tools/
  │   ├── _entity_ref.py        # (新建) 读写共用的 schema-aware e_ref helper
  │   ├── write.py              # (新建) WriteTools + 数据模型 + draft_to_write_request
  │   └── _runtime_api.py       # (扩展) +write_fact
  ├── orchestrator.py            # (扩展) +prepare_draft +confirm_and_commit +confirm_and_commit_many
  ├── framework.py               # (扩展) build_layer3a_tool_registry

src/factpy_kernel/tests/
  ├── test_agent_layer3a_runtime_api.py
  └── test_agent_layer3a_write.py
```

---

## 9. 验收标准

1. **RuntimeAPI 扩展**：write_fact 在 LocalRuntimeAPI 和 HttpRuntimeAPI 上均可调用
2. **draft_to_write_request**：FactDraft 到 WriteRequest 的映射正确（schema-aware e_ref 编码、meta 组装）
3. **commit_draft**：confirmed draft → write_runtime_fact → WriteResult/WriteError，不改 draft status
4. **prepare_draft**：创建 pending draft + scope 校验通过/拒绝
5. **confirm_and_commit**：pending → confirmed → write → committed + checkpoint（成功路径）
6. **confirm_and_commit 失败路径**：write 失败 → draft rejected + checkpoint + 返回 WriteError
7. **confirm_and_commit_many**：mixed results，单次末尾 checkpoint
8. **审计完整**：committed draft 的 assertion_id 非空；meta 含 approved_by + trace_id
9. **L3A-02 保证**：无法绕过 confirmed draft 直接写入（WriteTools.commit_draft 做 defensive check）
10. **单测 + 集成测试**覆盖全部新增组件

---

## 10. 已知约束

1. **batch 非原子**：confirm_and_commit_many 是逐条提交。前面成功后面失败不会回滚前面。与 v1 蓝图 §7.2 一致。
2. **WriteTools 不负责 mark_committed**：mark_committed + checkpoint 由 orchestrator 层协调。WriteTools 只做 "confirmed draft → runtime API → 结果" 这一步。
3. **不支持 retract**：retract 是 W2a（独立交付），不在 Layer 3A 范围。
4. **confirm_and_commit_many 崩溃恢复**：批量提交中途崩溃时，ledger 中已有 assertion 但 draft 状态未 checkpoint。恢复后需对比修复。这是单次末尾 checkpoint 的可接受权衡。
5. **schema_ir 缓存策略**：draft_to_write_request 需要 schema_ir 做 e_ref 编码。当前每次 commit 从 runtime API 获取或从 bootstrap_spec 读取。如果 schema 极大且高频写入，可在 orchestrator 层缓存 schema_ir。
6. **共享 entity_ref helper**：读写都经 `agent/tools/_entity_ref.py` 做 schema-aware 编码；避免 write.py 依赖 kg_read 私有函数。

---

## 11. Outcome / Deviations

### Delivered

- `src/factpy_kernel/agent/tools/_runtime_api.py`
  - 扩展 `RuntimeAPI` / `LocalRuntimeAPI` / `HttpRuntimeAPI`
  - 新增 `write_fact()`
- `src/factpy_kernel/agent/tools/_entity_ref.py`
  - 新增共享 `encode_entity_ref(schema_ir, ...)`
  - 读写两侧统一复用 `encode_idref_v1`
- `src/factpy_kernel/agent/tools/write.py`
  - 新增 `WriteRequest` / `WriteResult` / `WriteError`
  - 新增 `draft_to_write_request()`
  - 新增 `WriteTools`
- `src/factpy_kernel/agent/orchestrator.py`
  - 新增 `prepare_draft()`
  - 新增 `confirm_and_commit()`
  - 新增 `confirm_and_commit_many()`
  - 新增 `list_committed_drafts()`
- `src/factpy_kernel/agent/framework.py`
  - 新增 `build_layer3a_tool_registry()`
  - Layer 3A tool 总数扩到 20
- `src/factpy_kernel/agent/docs/README.md`
  - 更新 Layer 3A structured write 的当前实现文档
- 新增测试：
  - `src/factpy_kernel/tests/test_agent_layer3a_runtime_api.py`
  - `src/factpy_kernel/tests/test_agent_layer3a_write.py`

### Key Deviations

1. **共享 helper 提前落地**
   - blueprint 评审阶段把“抽共享 entity_ref helper”记成 residual
   - 实现时直接消化为 `agent/tools/_entity_ref.py`
   - 结论：采纳；减少 `write.py` 对 `kg_read` 私有函数的耦合

2. **`confirm_and_commit_many()` 对 contract/scope 失败也返回 `WriteError`**
   - blueprint 只明确了 runtime 写失败的 mixed result
   - 实现中 batch 为了保持“尽力提交”语义，对 per-item 的 contract/scope 失败也降为结构化 `WriteError`
   - 结论：采纳；这样 batch 不会因单条无效 draft 中断整批

3. **scope re-check 失败时也 checkpoint rejected 状态**
   - 单条 `confirm_and_commit()` 在 defensive scope re-check 失败时，会先 reject draft，再 checkpoint，然后重新抛出 `AgentScopeViolation`
   - 结论：采纳；保证 DraftManager 与 checkpoint 不漂移

### Validation

- `python -m py_compile` 覆盖 Layer 3A 变更文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer2_runtime_api src.factpy_kernel.tests.test_agent_layer2_workflow src.factpy_kernel.tests.test_agent_layer3a_runtime_api src.factpy_kernel.tests.test_agent_layer3a_write`：通过（24 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（795 tests）
