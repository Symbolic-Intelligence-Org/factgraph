# Blueprint: Agent Layer 4C2 — Draft Bundle + Review/Approval

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on:
  - Layer 3A 结构化最小写入 (archived)
  - Layer 4C1 确定性文档 staging (archived)
- Related Modules:
  - `src/factpy_kernel/agent/documents/bundle.py` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：agent 能将文档 staging 产出的 segment 和调用方提供的 `FactDraftSpec` 组合成 `DraftBundle`，经批量 review/approval 后，通过 Layer 3A 现有 commit path 逐条写入 ledger。每条 draft 携带 segment-level provenance。

**冻结决策**（本轮锁定，正文围绕这 5 条展开）：

| # | 决策 | 理由 |
|---|------|------|
| L4C2-01 | 4C2 只处理 FactDraft bundle，不处理 RuleDraft | rule 提取是更大的问题，留给 4C3 或后续 layer |
| L4C2-02 | DraftBundle 是 agent-side staging/review carrier，不直接写 ledger | bundle 是审批载体；commit 走 per-draft ledger write，不侵入 kernel |
| L4C2-03 | bundle commit 复用 Layer 3A 的 `confirm_and_commit_many()`，不发明新的批量 kernel API | kernel 已有稳定的 per-draft commit 语义；4C2 不造双合同 |
| L4C2-04 | 每个 draft 必须带 `source_document_id + segment_id + offsets` 级 provenance | 审计链必须到字符偏移粒度；只保留 doc_id 不够 |
| L4C2-05 | review/approval 是 bundle-level workflow，但 commit 仍是 per-item best-effort，保留 per-item result | 与 Layer 3A `confirm_and_commit_many()` 的尽力提交语义一致；避免伪事务 |

**明确排除**：
- RuleDraft 生成和提取
- LLM schema-constrained 提取（是 4C3）
- 审批 UI 前端实现（蓝图只定义 contract）
- 跨 bundle 去重
- bundle 原子性 / ledger 事务

---

## 1. 5 条冻结决策的展开

### 1.1 L4C2-01：只处理 FactDraft bundle

**范围**：
- `DraftBundle.draft_ids: list[str]` — 引用 DraftManager 中的 FactDraft（L4C2-14）
- `DraftBundle.approved_draft_ids: list[str]` — review 通过的子集（L4C2-13）
- 不存在 `rules` 字段
- Bundle 创建输入是 `FactDraftSpec`（由 BundleManager 注册为 managed FactDraft）
- 所有 orchestrator 方法只接受/返回 fact draft 相关类型（FactDraftSpec / DraftBundle / FactDraft）

**不涉及**：
- RuleDraft 数据结构设计（如果需要，由后续 layer 新增）
- 规则 extraction pipeline
- bundle 内混合 fact + rule 的提交顺序问题

### 1.2 L4C2-02：DraftBundle 是 agent-side carrier

**数据归属**：
- 运行时：DraftBundle 存在于 BundleManager 的进程内存
- 持久化：BundleManager 纳入 AgentCheckpointStore 三元组（L4C2-16）
  `save(session, draft_manager, bundle_manager)` / `load → (session, draft_manager, bundle_manager)`
- 不写入 ledger：bundle 本身没有 kernel 对应物
- 不新增 runtime API：kernel 不知道"bundle"概念

**生命周期**：
```
created → under_review → (approved → committing → committed) / rejected / abandoned
```

### 1.3 L4C2-03：commit 复用 Layer 3A

**实施路径**：
```python
# bundle commit 的底层实现
def commit_bundle(bundle: DraftBundle, ...) -> BundleCommitResult:
    # 1. 直接读取 bundle 跟踪的 approved draft IDs
    #    这些 draft 仍是 pending 状态（L4C2-13），由 confirm_and_commit_many
    #    内部处理 pending → confirmed → committed
    draft_ids = list(bundle.approved_draft_ids)

    # 2. 调用 Layer 3A 已有方法
    per_item_results = orchestrator.confirm_and_commit_many(
        draft_ids=draft_ids,
        kind="set",  # or "add", by bundle config
        bundle_id=bundle.bundle_id,  # 作为 trace_id 注入 meta
        confirmed_by=bundle.confirmed_by,
    )

    # 3. 包装为 BundleCommitResult
    return BundleCommitResult(bundle_id=..., per_item_results=per_item_results, ...)
```

**不做**：
- 新增 `/bundles/commit` runtime endpoint
- 在 WriteTools 中新增 batch write
- bundle-level ledger transaction

### 1.4 L4C2-04：segment-level provenance 必填

**强制字段**（所有 bundle 内 draft）：
```python
draft.extraction_provenance = ExtractionProvenance(
    source_document_id="doc_abc123",        # 必填
    segment_id="doc_abc1_00042",            # 必填
    page_number=3,                           # 可空（非 PDF 为 None）
    char_offset_start=1024,                  # 必填
    char_offset_end=1156,                    # 必填
    raw_text="原文片段...",                  # 必填
    extraction_method="manual",              # 4C2 阶段所有 draft 都是 manual
)
```

**校验**：DraftBundle 构造时强制校验每个 draft 的 `extraction_provenance` 非空且字段完整。缺字段直接抛 `AgentContractError`，不入 bundle。

**Provenance → source/source_loc 注入点**（L4C2-17 冻结）：

Layer 3A 的 write path (`write.py:draft_to_write_request`) 只读 `FactDraft.source` 和 `FactDraft.source_loc`。4C2 的 `extraction_provenance` 必须在 **create_bundle 时** 自动规范化写入 draft 的 source/source_loc 字段：

```python
def _provenance_to_draft_source(prov: ExtractionProvenance, doc_name: str) -> tuple[str, str]:
    """L4C2-17 冻结的规范化格式。"""
    source = f"doc:{doc_name}:seg:{prov.segment_id}"
    source_loc = f"chars:{prov.char_offset_start}-{prov.char_offset_end}"
    return source, source_loc
```

在 `BundleManager.create_bundle()` 中，对每个 FactDraftSpec：
1. 计算 `source, source_loc = _provenance_to_draft_source(spec.extraction_provenance, source_document_name)`
2. 调用 `draft_manager.create_draft(source=source, source_loc=source_loc, ...)` 创建 draft
3. draft 的 `extraction_provenance` 字段同时保留原始对象（供审批 UI 展示用）
4. commit 时 Layer 3A write path 自然从 `draft.source`/`draft.source_loc` 读取并写入 assertion meta

**为什么在 create_bundle 而不是 commit_bundle**：
- Layer 3A 的 commit path 是"零感知"的——它不知道 provenance 概念
- 如果在 commit 时注入，需要改 write_tools.commit_draft 的调用路径，违反 L4C2-03（零 kernel 改动）
- 在 create 时规范化一次，draft 整个生命周期都一致

**不依赖** schema-constrained extraction：4C2 的 draft 可以由人工构造（从 segment 复制文本 → 手动填 FactDraftSpec），也可以由后续 4C3 自动构造。4C2 不关心来源。

### 1.5 L4C2-05：bundle-level review，per-item commit

**两层语义**：

| 层 | 粒度 | 行为 |
|---|------|------|
| review/approval | bundle-level | 用户一次性审查整个 bundle，分别标记每条 approve/reject |
| commit | per-item | 逐条调用 Layer 3A write；任一条失败不阻塞其余 |

**per-item result**：
```python
@dataclass
class BundleCommitResult:
    bundle_id: str
    total: int
    committed_count: int                         # 成功写入数
    rejected_count: int                          # 被用户 reject 的数
    failed_count: int                            # commit 失败数
    per_item_results: list[WriteResult | WriteError]  # 对齐 Layer 3A 语义
```

**不承诺**：bundle 原子性。前面 commit 成功后面失败不会回滚。

---

## 2. 数据模型

### 2.1 ExtractionProvenance

```python
@dataclass(frozen=True)
class ExtractionProvenance:
    """
    附在 FactDraft 上的文档提取溯源（L4C2-04）。

    所有字段除 page_number 外必填。
    与 Layer 4C1 的 DocumentSegment 对齐。
    """
    source_document_id: str                  # DocumentSource.doc_id
    segment_id: str                          # DocumentSegment.segment_id
    char_offset_start: int                   # DocumentSegment.char_offset_start
    char_offset_end: int                     # DocumentSegment.char_offset_end
    raw_text: str                            # 完整原文片段（或截断版本）
    page_number: int | None = None           # PDF 页码；非 PDF None
    extraction_method: Literal["manual", "llm_refined"] = "manual"
```

**为什么独立定义而不是复用 v1 蓝图 §11.3**：
- v1 蓝图的 `ExtractionProvenance` 包含 `structural_clarity` 和 `llm_confidence`，这两个字段是 4C3 的关注点
- 4C2 只需要最小审计字段
- 4C3 可以通过继承或扩展字段补充

### 2.2 FactDraft 扩展

Layer 3A 的 FactDraft 已经有可选的 `source`/`source_loc`/`note` 字段。4C2 追加显式 `extraction_provenance`：

```python
@dataclass
class FactDraft:
    # ... existing Layer 3A fields ...
    extraction_provenance: ExtractionProvenance | None = None  # 新增
```

**兼容性**：
- 默认 None → 非文档来源的 draft（Layer 3A 手工构造）不受影响
- 只有进入 DraftBundle 的 draft 才强制非空（在 bundle 构造时校验）

### 2.2a FactDraftSpec

```python
@dataclass(frozen=True)
class FactDraftSpec:
    """
    创建 bundle 时的 draft 规格（L4C2-14）。

    FactDraftSpec → BundleManager.create_bundle → DraftManager.create_draft
                 → 新 FactDraft (with fresh draft_id)
                 → bundle.draft_ids 引用新 ID

    调用方不持有 FactDraft 对象；只提供字段，由 BundleManager 统一注册。
    """
    entity_type: str
    entity_identity: dict[str, Any]
    pred_id: str
    field_values: list[tuple[str, Any]]
    extraction_provenance: ExtractionProvenance      # 必填（L4C2-04）
    confidence: float | None = None
    note: str | None = None
    conversation_turn: int = 0
    # 注意：source / source_loc 不在这里——由 create_bundle 从 extraction_provenance
    # 自动规范化写入（L4C2-17）
```

### 2.3 DraftBundle

```python
@dataclass
class DraftBundle:
    """
    文档 fact draft 的批量审批 carrier（L4C2-02）。

    生命周期：created → under_review → (approved|rejected|abandoned)
                         → committing → committed
    """
    bundle_id: str                           # "bundle_" + uuid4 hex prefix
    source_document_id: str                  # 关联的 DocumentSource.doc_id
    source_document_name: str                # 冗余，便于展示
    draft_ids: list[str]                     # bundle 内 draft 的 ID 列表（L4C2-14）
                                             # 实际 FactDraft 对象存在 DraftManager 中
    approved_draft_ids: list[str]            # review 通过的 draft ID（L4C2-13）
                                             # approved draft 保持 pending 状态
    created_at: int                          # epoch_nanos
    created_by: str                          # agent_id
    status: Literal[
        "created",
        "under_review",
        "approved",
        "rejected",
        "abandoned",
        "committing",
        "committed",
    ] = "created"
    confirmed_by: str | None = None          # 人类确认者（bundle-level）
    confirmed_at: int | None = None
    committed_at: int | None = None

    def __post_init__(self) -> None:
        """
        构造时校验：
        - draft_ids 非空
        - approved_draft_ids ⊆ draft_ids
        - source_document_id 非空
        """
        ...

    def to_checkpoint(self) -> dict[str, Any]:
        """序列化 bundle 结构（不含 FactDraft 本体——那些在 DraftManager 中）。"""
        ...

    @classmethod
    def from_checkpoint(cls, data: dict[str, Any]) -> "DraftBundle": ...
```

### 2.4 BundleReviewAction

```python
@dataclass(frozen=True)
class BundleReviewAction:
    """对 bundle 内单条 draft 的 review 决策。"""
    draft_id: str
    action: Literal["approve", "reject"]
    note: str | None = None                  # review 备注，可选


@dataclass
class BundleCommitResult:
    """bundle commit 的结构化返回（L4C2-05）。"""
    bundle_id: str
    total: int                               # bundle 内 approved draft 总数
    committed_count: int
    failed_count: int
    per_item_results: list["WriteResult | WriteError"]  # 对齐 Layer 3A
    committed_at: int
```

---

## 3. BundleManager

### 3.1 职责

管理 agent session 内的 DraftBundle 集合。CRUD + review 状态流转 + commit orchestration。

**持久化**（L4C2-16）：BundleManager 作为 AgentCheckpointStore 的第三个持久化对象，与 session 和 draft_manager 并列。通过 `to_checkpoint()` / `from_checkpoint()` 序列化，存入 SQLite 新增的 `bundle_manager_json` 列。

### 3.2 接口

```python
class BundleManager:
    """
    DraftBundle 生命周期管理。

    与 DraftManager 的关系：
    - DraftManager 管理 FactDraft（含非 bundle 的 draft）
    - BundleManager 管理 DraftBundle（聚合 FactDraft 到 bundle）
    - bundle 内的 draft 仍然在 DraftManager 中存在（共享存储）
    - BundleManager 只维护 bundle_id → draft_ids 的映射 + bundle-level 元数据
    """

    def __init__(self, *, draft_manager: DraftManager) -> None: ...

    def create_bundle(
        self,
        *,
        source_document_id: str,
        source_document_name: str,
        facts: list[FactDraftSpec],
        created_by: str,
    ) -> DraftBundle:
        """
        创建新 bundle。

        L4C2-14 冻结的 draft 注册语义：
        - 输入是 FactDraftSpec（不是 FactDraft 对象），表示"想要的 draft 字段"
        - BundleManager 对每个 spec 调用 draft_manager.create_draft(...)
          创建新的 managed draft，获得新 draft_id
        - 调用方不需要预先注册 draft 到 DraftManager
        - bundle 返回后，调用方以 bundle.draft_ids 为准访问 draft

        为什么用 FactDraftSpec 而不是直接接受 FactDraft：
        - DraftManager.create_draft() 总是生成新 draft_id；接受已构造的
          FactDraft 对象会导致 draft_id 混乱
        - Spec → create_draft → new draft 是干净的单向流
        - 调用方不需要知道 DraftManager 的存在

        步骤：
        1. 校验所有 specs 的 extraction_provenance 非空（L4C2-04）
        2. 校验所有 specs 的 provenance.source_document_id == source_document_id
        3. 对每个 spec：
           a. 将 extraction_provenance 规范化为 source / source_loc（L4C2-17）
           b. draft_manager.create_draft(session_id, **spec_fields)
           c. 收集返回的 draft_id
        4. 构造 DraftBundle(
               draft_ids=[...],
               approved_draft_ids=[],
               status="created",
           )
        5. 存入 self._bundles
        6. 返回 bundle（调用方通过 draft_ids 引用内部 drafts）
        """
        ...

    def get_bundle(self, bundle_id: str) -> DraftBundle | None: ...

    def list_bundles(
        self,
        *,
        status: str | None = None,
    ) -> list[DraftBundle]: ...

    def open_review(self, bundle_id: str) -> DraftBundle:
        """status: created → under_review。"""
        ...

    def apply_review(
        self,
        bundle_id: str,
        actions: list[BundleReviewAction],
    ) -> DraftBundle:
        """
        批量应用 review 决策。

        对每个 action（L4C2-13 冻结）：
        - approve: **不** 转换 draft 状态，approved draft 保持 pending
                   （bundle 内跟踪 approved_draft_ids，由 commit_bundle 统一 confirm+write）
        - reject:  draft_manager.reject_draft(action.draft_id)

        为什么 approved 保持 pending：Layer 3A 的 confirm_and_commit_many()
        内部 _confirm_and_commit_no_checkpoint() 要求 draft.status == "pending"
        才会走 confirm_draft → write → mark_committed 流程。如果 apply_review
        先 confirm，commit_bundle 再复用 confirm_and_commit_many 会立即
        contract error。

        BundleManager 通过 bundle.approved_draft_ids: list[str] 字段跟踪审批状态，
        不侵入 FactDraft.status。

        所有决策应用完成后：
        - approved_draft_ids 非空 → bundle.status = "approved"
        - approved_draft_ids 为空 且 所有 draft 都被 reject → bundle.status = "rejected"
        - 无 action 应用 → status 不变

        Defensive：只能在 status in {"created", "under_review"} 时调用。
        """
        ...

    def abandon_bundle(self, bundle_id: str, *, reason: str | None = None) -> DraftBundle:
        """status: * → abandoned。bundle 内 draft 对应 reject。"""
        ...

    def to_checkpoint(self) -> dict[str, Any]: ...

    @classmethod
    def from_checkpoint(
        cls, data: dict[str, Any], *, draft_manager: DraftManager,
    ) -> "BundleManager": ...
```

### 3.3 为什么不把 BundleManager 合进 DraftManager

- DraftManager 的职责是"单 draft 生命周期"
- BundleManager 的职责是"bundle-level 聚合 + 审批"
- 合并会让 DraftManager 出现两种视图（单 draft / bundle）
- 分开后，Layer 3A 的 DraftManager 保持零侵入

---

## 4. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4C2: Document Draft Bundle ──

    def create_document_bundle(
        self,
        *,
        source_document_id: str,
        source_document_name: str,
        facts: list[FactDraftSpec],
    ) -> DraftBundle:
        """
        从文档提取的 FactDraftSpec 列表创建 bundle（L4C2-14）。
        委托 bundle_manager.create_bundle()。

        前置：facts 由调用方手工或 4C3 自动构造 FactDraftSpec，
        每条都有完整的 extraction_provenance。BundleManager 负责
        将 specs 注册为 managed drafts（分配 draft_id）。

        调用后立即 _checkpoint()（L4C2-15）——bundle 创建必须持久化。
        """
        ...

    def list_document_bundles(
        self, *, status: str | None = None,
    ) -> list[DraftBundle]:
        """列出当前 session 的 bundle。"""
        ...

    def open_bundle_review(self, bundle_id: str) -> DraftBundle:
        """打开 review 模式。status: created → under_review。"""
        ...

    def apply_bundle_review(
        self,
        bundle_id: str,
        actions: list[BundleReviewAction],
    ) -> DraftBundle:
        """批量应用 review 决策。每条 draft 对应 confirm/reject。"""
        ...

    def commit_bundle(
        self,
        bundle_id: str,
        *,
        kind: Literal["set", "add"] = "set",
        confirmed_by: str | None = None,
    ) -> BundleCommitResult:
        """
        提交 bundle 中所有 approved draft 到 ledger（L4C2-03）。

        时序：
        1. bundle = bundle_manager.get_bundle(bundle_id)
           - status 必须 == "approved"（not under_review、not created）

        2. bundle.status = "committing"

        3. 从 bundle 直接读取 approved draft IDs：
           draft_ids = list(bundle.approved_draft_ids)
           # 这些 draft 仍然是 pending 状态（L4C2-13）；
           # confirm_and_commit_many 会处理 pending → confirmed → committed

        4. per_item_results = self.confirm_and_commit_many(
               draft_ids=draft_ids,
               kind=kind,
               bundle_id=bundle.bundle_id,   # 注入 meta.trace_id
               confirmed_by=confirmed_by or bundle.confirmed_by,
           )
           # ↑ 复用 Layer 3A 已有方法，不新增路径
           # ↑ draft 的 source/source_loc 在 create_bundle 时已从 provenance
           #   规范化写入，Layer 3A write path 直接读取

        5. 统计 committed_count / failed_count

        6. bundle.status = "committed"
           bundle.committed_at = time_ns

        7. _checkpoint()（Layer 3A 的 confirm_and_commit_many 末尾已 checkpoint；
           此处再次 checkpoint 保证 bundle.status 也持久化）

        8. 返回 BundleCommitResult
        """
        ...

    def abandon_bundle(
        self, bundle_id: str, *, reason: str | None = None,
    ) -> DraftBundle:
        """放弃整个 bundle。所有 pending/confirmed draft reject。"""
        ...
```

### 4.1 自动 checkpoint 点（L4C2-15 冻结）

| 操作 | 是否 checkpoint |
|---|---|
| create_document_bundle | ✓（bundle 创建必须持久化，否则进程退出后整包丢失） |
| list / get | ✗ |
| open_bundle_review | ✓（status 变更） |
| apply_bundle_review | ✓（approved_draft_ids + draft reject 状态变更） |
| commit_bundle | ✓（间接经由 confirm_and_commit_many + 末尾显式 checkpoint） |
| abandon_bundle | ✓（状态变更） |

**checkpoint 合同扩展**（L4C2-16 冻结）：

当前 `AgentCheckpointStore.save(session, draft_manager)` 只保存两个对象。Layer 4C2 必须扩展为：

```python
AgentCheckpointStore.save(session, draft_manager, bundle_manager=None)
AgentCheckpointStore.load(agent_session_id) → (session, draft_manager, bundle_manager)
```

**向后兼容策略**：
- `bundle_manager` 参数可选，默认 None
- `load()` 返回的第三项在旧 checkpoint 中为 BundleManager 空实例
- 旧 checkpoint 反序列化时如果没有 bundle_manager 字段，构造空 BundleManager
- `recover_agent_session()` 更新为三元组返回，调用方需适配

**SQLite schema 变更**：
- 新增列 `bundle_manager_json TEXT`（nullable）
- 迁移策略：`ALTER TABLE agent_checkpoint ADD COLUMN bundle_manager_json TEXT` 在 `_ensure_table()` 中执行
- 旧数据 bundle_manager_json = NULL → load 时构造空 BundleManager

---

## 5. Tool Registry 扩展

Layer 4C1 注册了 33 个 tool。Layer 4C2 追加：

```python
# 扩展 build_layer3a_tool_registry()

"create_document_bundle":     → orchestrator.create_document_bundle
"list_document_bundles":      → orchestrator.list_document_bundles
"open_bundle_review":         → orchestrator.open_bundle_review
"apply_bundle_review":        → orchestrator.apply_bundle_review
"commit_bundle":              → orchestrator.commit_bundle
"abandon_bundle":             → orchestrator.abandon_bundle
```

Layer 4C2 总计 39 个 tool（33 Layer 4C1 + 6 Layer 4C2）。

---

## 6. 实现顺序

```
Step 1: 数据模型
        → ExtractionProvenance
        → FactDraft 扩展（+extraction_provenance）
        → DraftBundle + BundleReviewAction + BundleCommitResult
        → checkpoint 序列化
        → 单测

Step 2: BundleManager
        → create/get/list
        → open_review / apply_review / abandon
        → 与 DraftManager 的交互
        → checkpoint / restore
        → 单测：mock DraftManager

Step 3: Orchestrator 扩展
        → 6 个新方法
        → 重点测试 commit_bundle 委托给 confirm_and_commit_many
        → 集成测试：staging → bundle → review → commit 完整链路

Step 4: AgentSession / Recovery 集成
        → AgentCheckpointStore.save/load 追加 bundle_manager 参数（L4C2-16）
        → SQLite schema ALTER: +bundle_manager_json TEXT
        → recover_agent_session 返回带 bundle_manager 的 RecoveryResult
        → 旧 checkpoint 反序列化兼容（bundle_manager_json IS NULL → 空 BundleManager）
        → 单测 + 恢复时序测试

Step 5: Tool Registry 扩展
        → 39 tool 全量注册验证
```

---

## 7. 目录结构增量

```
src/factpy_kernel/agent/
  ├── documents/
  │   ├── bundle.py             # (新建) DraftBundle / BundleManager / BundleReviewAction / BundleCommitResult
  │   └── models.py             # (扩展) ExtractionProvenance
  ├── draft.py                  # (扩展) FactDraft +extraction_provenance
  ├── orchestrator.py            # (扩展) +6 bundle methods
  ├── framework.py               # (扩展) tool registry 39 tools
  └── recovery.py                # (扩展) BundleManager 恢复

src/factpy_kernel/tests/
  ├── test_agent_l4c2_models.py          # (新建)
  ├── test_agent_l4c2_bundle_manager.py  # (新建)
  └── test_agent_l4c2_workflow.py        # (新建) 端到端：stage → bundle → review → commit
```

---

## 8. 验收标准

1. **L4C2-01 边界**：DraftBundle 不含 rules 字段；create path 接受 `FactDraftSpec`，review/commit path 只处理 fact drafts
2. **L4C2-02 carrier 语义**：DraftBundle 不对应任何 runtime endpoint；只通过 checkpoint 持久化
3. **L4C2-03 commit 复用**：commit_bundle 最终调用 confirm_and_commit_many；bundle_id 作为 trace_id 写入每条 assertion 的 meta
4. **L4C2-04 provenance 必填**：create_document_bundle 校验所有 facts 的 extraction_provenance 非空且字段完整；缺字段抛 AgentContractError
5. **L4C2-05 per-item 结果**：BundleCommitResult.per_item_results 与 confirm_and_commit_many 返回一致（WriteResult|WriteError 混合）
6. **provenance → meta.source**：committed assertion 的 meta 含 `source="doc:<name>:seg:<segment_id>"` 或等价格式；`source_loc="chars:<start>-<end>"`
7. **bundle 生命周期**：create → open_review → apply_review → commit 状态转换正确
8. **abandon**：abandon_bundle 后所有 draft 变为 rejected
9. **checkpoint/恢复**：cold restart 后 bundle 状态完整恢复
10. **Tool 数量**：39 个
11. **单测 + 端到端测试**覆盖

---

## 9. 已知约束

1. **Bundle 非原子**（L4C2-05）：commit 过程中任一条失败不会回滚前面成功的条目。这与 Layer 3A `confirm_and_commit_many` 的尽力提交语义一致。
2. **Bundle 不跨 session**：cold restart 后 bundle 可恢复（via checkpoint），但不能在不同 AgentSession 之间迁移。
3. **ExtractionProvenance.raw_text 可能很大**：长 segment 的 raw_text 会让 checkpoint 文件膨胀。v1 不做截断；调用方应在构造 draft 时自行截断（建议 ≤ 512 字符）。
4. **4C2 不做 NL draft 构造**：orchestrator 接受已经结构化的 `FactDraftSpec`。如何把 `segment.raw_text` 转为 `(entity_type, pred_id, field_values)` 由 4C3（LLM）或调用方手工处理。
5. **source/source_loc meta 字段格式**：格式由 4C2 定义（`doc:<name>:seg:<segment_id>` / `chars:<start>-<end>`），kernel 不解析——作为人类可读字符串写入 meta.source。
6. **bundle_id 作为 trace_id**：多个 bundle 可能来自同一文档（如文档被分批 review）；trace_id 以 bundle 粒度区分，而非文档粒度。
7. **approved draft 保持 pending**（L4C2-13）：bundle 内被 approve 的 draft 在 commit_bundle 调用前仍是 pending 状态；bundle 通过 approved_draft_ids 字段独立跟踪。这允许 commit_bundle 直接复用 confirm_and_commit_many 的 pending→confirmed→committed 流水。
8. **FactDraftSpec vs FactDraft**（L4C2-14）：调用方提供 FactDraftSpec，BundleManager 负责注册为 managed FactDraft。调用方永远以 bundle.draft_ids 为准访问实际 draft，不持有 FactDraft 对象。
9. **Recovery 扩展**（L4C2-16）：`RecoveryResult` 新增 `bundle_manager` 字段；旧 checkpoint 数据 `bundle_manager_json` 为 NULL 时构造空 `BundleManager`。
10. **Provenance 规范化一次性**（L4C2-17）：create_bundle 时把 extraction_provenance 注入 draft.source / draft.source_loc；之后的所有 Layer 3A write path 自然消费这两个字段，零改动。

---

## 10. Outcome / Deviations

**实现结果**：Layer 4C2 已落地。agent 现在支持：
- `FactDraftSpec[] -> DraftBundle`
- `open_bundle_review / apply_bundle_review / commit_bundle / abandon_bundle`
- `ExtractionProvenance -> source/source_loc` 的一次性规范化注入
- `(session, draft_manager, bundle_manager)` checkpoint 持久化与 cold restart 恢复
- tool registry 从 33 扩到 39

**验证结果**：
- `python -m unittest src.factpy_kernel.tests.test_agent_l4c2_models src.factpy_kernel.tests.test_agent_l4c2_bundle_manager src.factpy_kernel.tests.test_agent_l4c2_workflow`
- Layer 1/2/3A/W2a/4A/4B/4C1 回归通过
- 全量 `python -m unittest discover -s src/factpy_kernel/tests` 通过

**主要偏差**：
1. `BundleManager.create_bundle()` 在实现里追加了私有 `session_id` 参数，用于调用 `DraftManager.create_draft(session_id, ...)` 注册 managed drafts。这个参数是 agent 内部接口，不影响对外 contract。
2. blueprint 原计划目录里列了 `test_agent_l4c2_orchestrator.py`；实际实现用 `test_agent_l4c2_workflow.py` 覆盖了 orchestrator 与 recovery 的端到端链路，没有再拆独立 orchestrator 测试文件。
3. `create_document_bundle()` 实现中补了一层 defensive scope 校验：在 bundle 创建前用规范化后的 `source/source_loc` 生成 preview draft 并走 `AgentScopeGuard`，避免 4C2 绕过 Layer 3A 的 scope 约束。
