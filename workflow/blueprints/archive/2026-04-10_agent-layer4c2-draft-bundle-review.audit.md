# Audit Log: Agent Layer 4C2 — Draft Bundle + Review/Approval

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.4 (W4 文档提取管线 Stage 2/3) + Layer 4C1 已落地 + 用户指导（先冻结 5 条再写正文）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4C2-01 | 4C2 只处理 FactDraft bundle，不处理 RuleDraft | 用户 2026-04-10 指导 |
| L4C2-02 | DraftBundle 是 agent-side staging/review carrier，不直接写 ledger | 用户 2026-04-10 指导 |
| L4C2-03 | bundle commit 复用 Layer 3A 的 confirm_and_commit_many()，不发明新批量 kernel API | 用户 2026-04-10 指导（最重要） |
| L4C2-04 | 每个 draft 必须带 source_document_id + segment_id + offsets 级 provenance | 用户 2026-04-10 指导 |
| L4C2-05 | review/approval 是 bundle-level workflow，但 commit 仍是 per-item best-effort，保留 per-item result | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4C2-06 | BundleManager 与 DraftManager 分离 | 职责分离：DraftManager=单 draft 生命周期，BundleManager=聚合+审批；Layer 3A 零侵入 |
| L4C2-07 | bundle 内 draft 仍在 DraftManager 共享存储 | 避免状态双写；BundleManager 只维护 bundle_id → draft_ids 映射 |
| L4C2-08 | ExtractionProvenance 独立定义而非复用 v1 蓝图 §11.3 | 4C2 只需最小审计字段；structural_clarity 和 llm_confidence 是 4C3 关注点 |
| L4C2-09 | bundle_id 作为 trace_id 注入 meta | 与 Layer 3A 的 bundle_id → meta.trace_id 模式一致 |
| L4C2-10 | extraction_method 枚举在 4C2 只有 "manual" / "llm_refined" | "manual" 涵盖手工构造，"llm_refined" 为 4C3 预留 |
| L4C2-11 | commit_bundle 末尾显式 checkpoint（即使 confirm_and_commit_many 已做） | 保证 bundle.status 的变更被持久化 |
| L4C2-12 | source/source_loc 格式由 agent 层约定 | "doc:<name>:seg:<segment_id>" / "chars:<start>-<end>"；kernel 不解析 |

## 2026-04-10 — 实现前收口修订 (4 处)

### 修订来源

用户 code review 发现 4 处 P1 blocker：review/commit 合同冲突、checkpoint 缺失、draft 注册语义不定、provenance 注入点未冻结。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4C2-13 | **冻结** apply_review 中 approved draft **不预先 confirm**，保持 pending；bundle 用 approved_draft_ids: list[str] 跟踪审批；commit_bundle 直接复用 confirm_and_commit_many 处理 pending 转换 | Layer 3A _confirm_and_commit_no_checkpoint() 要求 draft.status == "pending"；预先 confirm 会立即 contract error |
| L4C2-14 | **冻结** draft 注册语义：输入是 FactDraftSpec（不是 FactDraft 对象），BundleManager 调用 DraftManager.create_draft 注册新 managed draft，分配新 draft_id | DraftManager.create_draft 总是生成新 draft_id；接受已构造 FactDraft 会导致 draft_id 混乱 |
| L4C2-15 | **冻结** create_document_bundle 必须 checkpoint；open_bundle_review / apply_bundle_review / abandon_bundle 均 checkpoint | 不 checkpoint 则 bundle 创建后进程退出直接丢失 |
| L4C2-16 | **扩展** AgentCheckpointStore.save/load 合同：追加 bundle_manager 参数；SQLite schema 新增 bundle_manager_json 列（向后兼容） | 当前 recovery.py 只存 session + draft_manager；BundleManager 必须纳入 checkpoint |
| L4C2-17 | **冻结** provenance 注入点：在 create_bundle 时将 extraction_provenance 规范化为 source/source_loc 写入 draft；draft 整个生命周期保持一致；Layer 3A write path 零改动 | 不在 create_bundle 注入则需要改 write_tools.commit_draft 调用路径，违反 L4C2-03 零 kernel 改动原则 |

### 合同对齐验证

确认以下已实现合同在 Layer 4C2 中正确引用：
- `DraftManager.create_draft() / confirm_draft() / reject_draft() / mark_committed()` ✓
- `ReadReviewOrchestrator.confirm_and_commit_many(draft_ids, kind, bundle_id, confirmed_by)` ✓
- `WriteResult / WriteError` (Layer 3A) ✓
- `AgentCheckpointStore.save(session, draft_manager, bundle_manager)` ✓（L4C2-16 扩展）
- `AgentCheckpointStore.load(agent_session_id) → (session, draft_manager, bundle_manager)` ✓（L4C2-16 扩展）
- Layer 4C1 `DocumentSource.doc_id` / `DocumentSegment.segment_id` / `char_offset_*` ✓
- `FactDraft` 已有 source/source_loc/note 可选字段（Layer 3A） ✓

### 边界声明

Layer 4C2 明确不涉及：
- `RuleDraft` 数据结构 / 规则提取
- LLM schema-constrained extraction（4C3）
- 审批 UI 前端
- kernel runtime API 扩展（零 runtime 改动）
- bundle 原子性 / ledger 事务
- 跨 bundle / 跨文档 entity 去重
- bundle 在不同 AgentSession 间迁移
