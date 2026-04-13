# Audit Log: Agent Layer 4C3-a — Single-Segment LLM Extraction

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.4 (W4 Stage 2 LLM 精炼) + 4C1/4C2 已落地 + 用户指导（4C3 拆分，先做 4C3-a）。

**重要里程碑**：这是 agent 代码库第一次真正发 model call。之前所有 Layer 都是纯 tool orchestration。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4C3a-01 | 只做 single-segment → FactDraftSpec[] | 用户 2026-04-10 指导 |
| L4C3a-02 | LLM 只提议，不 commit，不直接写 DraftManager | 用户 2026-04-10 指导 |
| L4C3a-03 | 只能抽现有 schema 可表达的 facts | 用户 2026-04-10 指导 |
| L4C3a-04 | ExtractionProvenance 完全继承自 4C1 segment，不让模型生成 offsets | 用户 2026-04-10 指导 + delta D-09 |
| L4C3a-05 | 输出先过 deterministic validation：schema + scope + field typing | 用户 2026-04-10 指导 |
| L4C3a-06 | v1 不做 cross-segment dedupe / entity resolution | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4C3a-07 | Instructor + LiteLLM 作为 optional dependency；依赖感知注册 | 与 4C1 parser 依赖策略一致；base agent 不强制引入 LLM 栈 |
| L4C3a-08 | ExtractionAgent 纯函数式，不持有 AgentSession 或 state | 简化测试；无 state 漂移风险；与 DocumentStaging 设计模式一致 |
| L4C3a-09 | LLMFactProposal 分离 LLM 可生成字段 vs 代码注入字段 | 审计链锚点（provenance）必须确定性，不能让 LLM 动 |
| L4C3a-10 | Validation pipeline 分三层：schema / scope / FactDraftSpec.__post_init__ | LLM 是 untrusted source；必须过多重闸门 |
| L4C3a-11 | 拒绝不抛异常，聚合为 ExtractionResult.rejections | 与 Layer 3A/4C2 的 best-effort 语义一致 |
| L4C3a-12 | extract_from_segment 不 checkpoint | 纯函数调用，无 state 变更；checkpoint 由调用 create_document_bundle 时触发 |
| L4C3a-13 | extract_and_create_bundle 作为便利方法 | 常见路径一站式；调用方也可分步走 |
| L4C3a-14 | ExtractionConfig 每次调用传入而非构造时固定 | 不同 segment 可能需要不同 model；测试灵活 |
| L4C3a-15 | Prompt 中 schema_summary 硬编码，不做 schema 筛选（v1） | 4C3-a scope；大 schema 优化留给后续 |
| L4C3a-16 | Response model 动态构造 Literal[entity_type/pred_id] | Instructor 的正确用法；v1 每次重建，后续可缓存 |

## 2026-04-10 — 实现前收口修订 (5 处)

### 修订来源

用户 code review 发现 3 处 P1 blocker + 2 处 P2 ambiguity。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4C3a-17 | **冻结** schema source 解析链：优先 `session.bootstrap_spec.open_dto["schema_ir"]`，fallback 走 runtime_api.get_schema() 解析原始 schema_ir；不使用 kg_read.get_schema_summary | kg_read.get_schema_summary 只返回 digest + entity_types + predicates 三元组，无 schema_ir |
| L4C3a-18 | **冻结** max_batch_size 处理：按 LLM 原始顺序保留前 max_batch_size 条；超出部分记录为 scope_max_batch_size rejection；不阻断已接受条目 | AgentScope.max_batch_size 已存在；不定义行为会在第一个大 segment 上出现未定义行为 |
| L4C3a-19 | **冻结** provenance.raw_text = 完整 segment.raw_text，永远不截断；config.max_text_chars 只截断送给 LLM 的 prompt text；两者独立 | §1.4 和 AC4 说继承完整 segment；已知约束 4 又说截断；消除双真相 |
| L4C3a-20 | **冻结** 依赖检查单一来源：ExtractionAgent 内部 local import；不扩展 framework.probe_optional_dependencies() | OptionalDependencyStatus 是 skeleton 级 probe（pydantic_ai/burr/langfuse）；extraction 依赖局部化，避免每层新增都改 framework |
| L4C3a-21 | 新增 ExtractionRejection.reason 枚举值 "scope_max_batch_size" | 配合 L4C3a-18 |
| L4C3a-22 | Pydantic response model 示例代码改为 `build_response_model(schema_ir)` 动态构造，与 L4C3a-16 一致 | §3.2 示例代码还是静态 str 字段，与 audit 不一致 |

### 合同对齐验证

确认以下已实现合同在 Layer 4C3-a 中正确引用：
- `DocumentSegment` (Layer 4C1) ✓
- `FactDraftSpec` + `__post_init__` 校验 (Layer 4C2) ✓
- `ExtractionProvenance` (Layer 4C2) ✓
- `AgentScope` + scope 字段（entity_types / pred_ids / min_confidence / max_batch_size）(Layer 1) ✓
- `ReadReviewOrchestrator.create_document_bundle` (Layer 4C2) ✓
- `AgentSession.bootstrap_spec.open_dto["schema_ir"]` (Layer 1) ✓（L4C3a-17 冻结的 canonical schema source）
- `RuntimeAPI.get_schema(session_id)` (Layer 1) ✓（L4C3a-17 fallback）
- ~~`KGReadTools.get_schema_summary`~~ 不作为 canonical schema source（L4C3a-17 明确排除：只返回 digest + summary，无 schema_ir）

### 边界声明

Layer 4C3-a 明确不涉及：
- 多 segment 批量 / 速率控制 / retry 编排（4C3-b）
- 跨 segment entity resolution / 去重 / 合并（4C3-c）
- RuleDraft 提取
- SchemaDraft（LLM 提议新 pred_id 时）
- 开放式自由生成
- LLM 直接操作 Ledger / DraftManager / BundleManager
- Langfuse / 观测深度集成（Phase 5）
- Token counting / budget limit（4C3-b）
- 真实 LLM API 集成测试（由 mock 覆盖）

### 首次 LLM 依赖引入的审计意义

Layer 4C3-a 是 agent 代码库第一次引入 LLM 依赖。所有前置 Layer 建立的约束在这里汇合：

| 前置约束 | 如何在 4C3-a 体现 |
|---------|------------------|
| Layer 4C1 确定性底座 | Provenance 由代码注入，LLM 不能生成 offset |
| Layer 4C2 FactDraftSpec 必填 provenance | 代码从 segment 构造，确保字段完整 |
| Layer 1 AgentScope 权限约束 | Validation pipeline 第二层 |
| Layer 3A 最小写入 confirm 链 | LLM 只提议，bundle 创建仍由调用方/4C2 触发 |
| Layer 4C2 bundle 审批链 | extract_and_create_bundle 走完整 review 路径 |

这是产品叙事的关键节点：agent 从此拥有"文档 → 结构化 fact"的能力，但每一步都经过代码级审计约束。LLM 是提议者，不是决策者。

## 2026-04-10 — 实现完成 / 归档前收口

### 实现结果

- 新建 `src/factpy_kernel/agent/extraction/` 子包：
  - `models.py`
  - `llm.py`
  - `prompts.py`
  - `validation.py`
  - `extractor.py`
  - `docs/README.md`
- 扩展 `ReadReviewOrchestrator`：
  - `extract_from_segment`
  - `extract_and_create_bundle`
- 扩展 `build_layer3a_tool_registry()`：39 → 41 tools
- 更新：
  - `src/factpy_kernel/agent/__init__.py`
  - `src/factpy_kernel/agent/docs/README.md`
  - `docs/README.md`
  - `pyproject.toml`

### 验证

- `python -m py_compile` 覆盖 extraction/orchestrator/framework 通过
- 4C3-a 定向：17 tests 通过
- 相关回归：40 tests 通过
- 全量：`884 tests`, `1 skipped`

### 实现偏差

1. **Injected client 绕过默认依赖检查**
   - local import dependency check 仅在 `llm_client is None` 的默认路径触发。
   - 显式注入 mock/fake client 时允许无 `instructor` / `litellm` 环境运行。
   - 这是有意偏差，用于维持 blueprint 约束与可测试性的平衡。

2. **Prompt document label 取 `segment.doc_id`**
   - `DocumentSegment` 当前不携带 `doc_name`。
   - 因此 extraction prompt 中的 document label 使用 `segment.doc_id`，而不是 blueprint 示例中的 `doc_name`。
