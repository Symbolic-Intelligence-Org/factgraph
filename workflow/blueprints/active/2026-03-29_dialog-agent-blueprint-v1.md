# Blueprint: 对话式知识录入 Agent (v1)

- Status: draft
- Created: 2026-03-29
- Last Updated: 2026-03-30
- Related Modules:
  - `src/factpy_kernel/agent/` (新建，尚不存在)
  - `src/factpy_kernel/core/evidence/write_protocol.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/evidence_graph.py`
- Audit Log:
  - [2026-03-29_dialog-agent-blueprint-v1.audit.md](./2026-03-29_dialog-agent-blueprint-v1.audit.md)

---

## 1. 概述与动机

### 动机

当前系统的知识录入入口（`write_runtime_fact` / `set_field` / `add_field`）要求调用方了解谓词结构（`pred_id`、`arg_specs`）、实体引用规范（`e_ref`）以及置信度语义。这对技术用户合理，但对领域专家构成认知门槛。

本 blueprint 设计一个**对话式知识录入 agent**，支持三种面向非技术用户的知识录入模式：

1. **对话录入**：多轮自然语言对话，逐条录入事实和规则
2. **文档提取**：从现有文档（法规、政策、合同、技术规范）中提取规则和事实，经混合管道处理后批量审核录入
3. **智能路由**：自动推荐最适合的推理引擎（Souffle / ProbLog / PyReason / Native），用户可覆盖

三种模式共享同一套 `FactDraft` / `RuleDraft` 中间表示和确认流程，最终通过 `BatchCommitEndpoint` 写入系统。

### 定位

- 目标用户：领域专家、非技术 SME（Subject Matter Expert）
- 交互方式：多轮渐进式对话（chatbot 风格）；文档批量审核
- 核心价值：降低录入门槛，同时保证知识质量和可审计性
- 不替代：批量 ETL、规则编辑 IDE、现有 API 直接调用路径

### 设计约束

| 约束 | 决策 |
|------|------|
| LLM 选型 | 通过 **LiteLLM** 路由多 LLM provider（OpenAI/Anthropic 等），系统本身不内嵌 LLM 能力 |
| 引擎耦合 | Agent 层**不直接选择**推理引擎；通过 `EngineRoutingHint` 推荐，用户可覆盖 |
| 写入权限 | 所有写操作需**用户显式确认**，agent 不能自主提交 |
| 对话状态 | 多轮渐进式；agent 主动追问直到 draft 完整度满足阈值 |
| 可视化辅助 | 生成初版候选时可结合 `EvidenceGraph` renderer 展示图形化预览 |
| 文档提取方法 | **混合提取**，非纯 AI：确定性预处理 + 受约束 LLM 精炼 + 人工逐条确认 |
| 可审计性 | 每条提取结果必须携带文档来源 provenance（文档 ID、章节、字符偏移量） |

---

## 2. 架构分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Agent 层                                    │
│  (OpenAI SDK · 对话状态 · 意图识别 · slot filling · 确认流程)          │
│  AgentSession · DraftManager · ConversationOrchestrator               │
│  DocumentPipelineOrchestrator · EngineRouter                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ FactDraft / RuleDraft (引擎无关 IR)
                               │ ExtractionBatch / EngineRoutingHint
┌──────────────────────────────▼──────────────────────────────────────┐
│                          系统适配层                                    │
│  SchemaDiscoveryAPI · AgentScopeGuard · BatchCommitEndpoint           │
│  DraftPreviewRenderer · DocumentParser · ExtractionRefiner            │
│  EngineRoutingAdvisor · ConsistencyChecker · SchemaRegistryAdapter    │
│  [复用基础组件] LiteLLM · DSPy · NetworkX                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ 现有内部接口
┌──────────────────────────────▼──────────────────────────────────────┐
│                       逻辑基底（现有系统）                              │
│  推理引擎(problog/pyreason/souffle/native) · Ledger · AnnotationStore │
│  EvidenceGraph · CandidateSet · WriteProtocol · SchemaIR              │
│  RuntimeSession · compile_authoring_rule_v1                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 各层职责

**Agent 层**（新建，位于 `src/factpy_kernel/agent/`）
- 调用 OpenAI SDK 进行 NL 理解与意图分类
- 管理对话状态机（`AgentSession`）：slot 收集 → draft 构建 → 确认 → 提交
- 维护 `DraftManager`：in-memory staging area，存放待确认的 `FactDraft`/`RuleDraft`
- `DocumentPipelineOrchestrator`：协调文档提取三阶段流程
- `EngineRouter`：根据 draft 特征和用户语言线索推荐引擎
- 不持有任何 `Ledger` 或 `Store` 引用

**系统适配层**（新建，位于 `src/factpy_kernel/agent/adapters/`）
- `SchemaDiscoveryAPI`：包装现有 `SchemaIR`，将谓词/实体类型翻译成 NL 友好描述
- `AgentScopeGuard`：实施 agent 权限约束（允许写入的谓词白名单、实体类型白名单）
- `BatchCommitEndpoint`：将已确认的 draft 列表事务性提交，调用 `write_runtime_fact`
- `DraftPreviewRenderer`：为 `FactDraft` 生成可读摘要 + 可选 `EvidenceGraph` 预览
- `DocumentParser`：确定性文档预处理（PDF/DOCX 解析、分段、结构识别）
- `ExtractionRefiner`：受约束的 LLM 精炼（在预处理结构上做语义消歧，非自由生成）；使用 **DSPy** 强制输出符合 SchemaIR 的结构化 JSON
- `EngineRoutingAdvisor`：语言线索分析 + draft 结构特征分析
- `ConsistencyChecker`：检查建议引擎与知识库中已有记录的一致性
- `SchemaRegistryAdapter`：将 `SchemaDraft` 提交到 authoring registry（Phase 3）
- **复用基础组件**：
  - `LiteLLM`：多 LLM provider 统一路由（OpenAI / Anthropic / 本地模型），替代直接依赖 OpenAI SDK
  - `DSPy`：结构化输出约束，保证 LLM 输出严格符合 SchemaIR 字段格式
  - `NetworkX`：图结构操作（文档内实体关系图、可视化辅助）

**逻辑基底**（现有，零改动原则）
- `write_protocol.set_field` / `add_field` / `retract_by_asrt`：实际写入
- `EvidenceGraph` + `render_evidence_graph_html`：可视化
- `CandidateSet`：derivation 结果表示
- `SchemaIR`（`schema_ir.py`）：谓词/实体类型注册表
- `RuntimeSession`（`runtime_v1.py`）：会话与存储上下文
- `compile_authoring_rule_v1`：规则编译（Phase 2）

---

## 3. 对话流程设计

### 3.1 状态机

```
IDLE
  │ 用户发起意图
  ▼
INTENT_IDENTIFIED     (意图分类：录入事实 / 录入规则 / 文档提取 / 查询 / 撤销)
  │
  ├─[对话模式]─ 分配 DraftSlots
  │               ▼
  │           SLOT_FILLING      (主动追问：实体、谓词、值、置信度、来源)
  │               │ 所有必填 slot 满足（含 EngineRoutingHint）
  │               ▼
  │           DRAFT_PREVIEW     (展示草稿 + 引擎推荐 + 可选图形化预览)
  │
  └─[文档模式]─ DOCUMENT_PROCESSING
                  │ 三阶段提取完成
                  ▼
              BATCH_REVIEW      (用户逐条 approve/reject/edit)
                  │ 用户确认批次
                  ▼
              DRAFT_PREVIEW     (汇总预览，同对话模式)

DRAFT_PREVIEW
  │ 用户确认
  ├─ 否 → SLOT_FILLING / BATCH_REVIEW (修改)
  ├─ 是 → COMMITTING
  └─ 中止 → IDLE
COMMITTING    (调用 BatchCommitEndpoint，记录 audit trail)
  │ 成功
  ▼
COMMITTED     (返回 asrt_id 列表，展示确认摘要)
  │
  ▼
IDLE
```

### 3.2 意图识别

Agent 使用 OpenAI function calling，分类为以下意图类型：

| 意图 | 触发示例 | 后续流程 |
|------|---------|---------|
| `ingest_fact` | "张三的风险等级是高" | FactDraft slot filling |
| `ingest_rule` | "如果A且B，则C成立" | RuleDraft slot filling（Phase 2） |
| `ingest_from_document` | "从这份合同里提取规则" / 上传文件 | 文档提取三阶段管道（Phase 2） |
| `retract_fact` | "撤销刚才录入的张三风险" | 查找 asrt_id → 确认 → retract |
| `query_schema` | "系统里有哪些实体类型" | `SchemaDiscoveryAPI` 查询，不写入 |
| `query_fact` | "张三现在的风险等级是什么" | 调用 `list_runtime_claims`，不写入 |
| `ambiguous` | 意图不明确 | LLM 发出澄清追问 |

### 3.3 Slot Filling 策略

对于 `ingest_fact`，需收集以下 slot：

| Slot | 必填 | 来源 | 追问策略 |
|------|------|------|---------|
| `entity_type` | 是 | 用户 NL 或枚举选择 | 展示可用实体类型列表 |
| `entity_identity` | 是 | 用户 NL | 追问标识字段（来自 `SchemaIR.entities[].identity_fields`） |
| `pred_id` | 是 | 用户 NL 语义匹配 | 展示候选谓词，要求确认 |
| `field_value` | 是 | 用户 NL | 根据 `arg_specs[].type_domain` 类型约束解析 |
| `engine_routing_hint` | 自动 | `EngineRouter.route()` | 展示引擎推荐 + 解释，用户可覆盖 |
| `confidence` | 否 | 用户 NL | 追问置信度（0~1 浮点，或 "高/中/低" 映射） |
| `source` | 否 | 用户 NL | 追问知识来源描述 |
| `note` | 否 | 用户 NL | 追问备注 |

**置信度追问策略**：若用户使用模糊表达（"我很确定"），agent 映射到区间（0.85~0.95），并告知用户具体数值请求确认。

### 3.4 多轮渐进示例（对话模式）

```
用户: 把李四的信用评分录为 720
Agent: 好的。请确认：
       - 实体类型: Person (李四)
       - 谓词: credit_score
       - 值: 720 (int)
       这条记录的置信度是多少？（可填 0~1，或跳过使用默认值 1.0）

用户: 0.9，来源是 2026年Q1报告
Agent: [展示草稿预览]
       ┌─ 待录入事实 ─────────────────────────────────────┐
       │ 实体: person:李四                               │
       │ 谓词: credit_score                              │
       │ 值: 720                                         │
       │ 置信度: 0.9                                     │
       │ 来源: 2026年Q1报告                              │
       │ 推荐引擎: ProbLog（置信度 < 1.0，含不确定性）   │
       └─────────────────────────────────────────────────┘
       确认录入？（是/否/修改）

用户: 是
Agent: 已录入。断言 ID: a3f2b1... ✓
```

---

## 4. 中间表示层设计

Agent 层与系统适配层之间通过引擎无关的 IR 通信，避免 agent 层直接依赖底层存储结构。所有三种录入模式（对话、文档、路由）都生成相同的 `FactDraft`/`RuleDraft`，确保下游确认和提交流程统一。

### 4.1 FactDraft

```python
@dataclass
class FactDraft:
    """Agent 层构造的事实草稿，引擎无关。"""
    draft_id: str                              # 本次对话内的临时 ID
    entity_type: str                           # SchemaIR entity_type
    entity_identity: dict[str, Any]            # {field_name: value}，来自 identity_fields
    pred_id: str                               # SchemaIR predicate pred_id
    field_values: list[tuple[str, Any]]        # [(type_domain, value), ...] 对应 arg_specs
    confidence: float | None                   # (0, 1]，None 表示未指定
    source: str | None
    source_loc: str | None
    note: str | None
    created_at: int                            # epoch_nanos
    status: Literal["pending", "confirmed", "committed", "rejected"]
    session_id: str                            # 所属 AgentSession
    conversation_turn: int                     # 对话轮次，用于审计
    # 智能路由（Phase 2）
    engine_routing_hint: EngineRoutingHint | None = None
    # 文档提取溯源（Phase 2）
    extraction_provenance: ExtractionProvenance | None = None
```

**映射到写协议**：
- `entity_identity` → `e_ref`（通过 `AgentScopeGuard` 调用现有 entity resolution）
- `pred_id` → `pred_id`
- `field_values` → `rest_terms`（`list[tuple[str, Any]]`）
- `confidence` / `source` / `note` → `meta` dict（`write_protocol._normalize_meta` 兼容）
- `extraction_provenance` → `meta.source`（文档名+章节）+ `meta.source_loc`（字符偏移范围）
- `engine_routing_hint.suggested_engine` → 影响 `confidence_kind` 选择（ProbLog → `"probability"`，PyReason → `"certainty"`，其余 → `"none"`）

### 4.2 RuleDraft（Phase 2）

```python
@dataclass
class RuleDraft:
    """Agent 层构造的规则草稿，引擎无关（Phase 2）。"""
    draft_id: str
    rule_label: str                            # 用户友好名称
    head_pred_id: str
    head_vars: list[str]
    conditions: list[RuleCondition]            # 前件列表
    confidence: float | None
    note: str | None
    status: Literal["pending", "confirmed", "committed", "rejected"]
    session_id: str
    # 智能路由（Phase 2）
    engine_routing_hint: EngineRoutingHint | None = None
    # 文档提取溯源（Phase 2）
    extraction_provenance: ExtractionProvenance | None = None
```

`RuleDraft` 在 Phase 2 通过 `compile_authoring_rule_v1` 翻译为系统规则。`engine_routing_hint.suggested_engine` 决定编译目标引擎。

### 4.3 DraftBundle

```python
@dataclass
class DraftBundle:
    """一次用户确认提交的草稿集合（支持批量）。"""
    bundle_id: str
    facts: list[FactDraft]
    rules: list[RuleDraft]
    confirmed_at: int
    confirmed_by: str                          # 用户标识（由外层身份层注入）
    source_document_id: str | None             # 文档模式下的源文档 ID
```

### 4.4 SchemaDraft（补充机制，Phase 3）

`SchemaDraft` 是一个**可选的补充路径**，不是核心录入流程。当文档提取或对话录入过程中出现 schema 中找不到匹配的实体类型或谓词时，系统不报错丢弃，而是生成 `SchemaDraft`，允许用户"边用边定义"地扩展 schema。

**触发条件**：`ExtractionRefiner` 或 slot filling 阶段无法将用户描述映射到任何已知 `entity_type` 或 `pred_id` 时。

```python
@dataclass
class SchemaDraft:
    """
    建议的 schema 扩展草稿。补充能力，非核心流程。
    用户确认后通过 SchemaRegistryAdapter 注册到 authoring registry。
    """
    draft_id: str
    schema_kind: Literal["entity_type", "predicate"]

    # entity_type 类型
    proposed_entity_type: str | None         # 建议的实体类型名
    proposed_identity_fields: list[dict[str, str]] | None
    # [{"name": "contract_id", "type_domain": "string"}, ...]

    # predicate 类型
    proposed_pred_id: str | None             # 建议的谓词名
    proposed_arg_specs: list[dict[str, str]] | None
    # [{"name": "amount", "type_domain": "float64"}, ...]

    user_description: str                    # 用户原始描述，作为 schema 注释
    example_data: list[dict[str, Any]]       # 触发 SchemaDraft 的示例数据
    origin_draft_id: str | None              # 触发此 SchemaDraft 的 FactDraft/RuleDraft ID
    status: Literal["pending", "confirmed", "committed", "rejected"]
    session_id: str
    created_at: int
```

**流程说明**：
1. 提取/录入阶段发现无匹配 schema → 暂存为 `SchemaDraft`（`status=pending`）
2. 对应的 `FactDraft`/`RuleDraft` 被标记为 `status="blocked_by_schema"`，不进入确认流程
3. 用户审核 `SchemaDraft`，可调整建议的字段定义后确认
4. `SchemaRegistryAdapter.register(schema_draft)` 将其提交到 authoring registry（复用现有 `schema_compile`/`schema_dsl_parse` 路径）
5. schema 注册成功后，对应的 `FactDraft`/`RuleDraft` 解除阻塞，重新进入 slot filling 流程

**与核心流程的边界**：
- `SchemaDraft` 不影响已有断言和规则
- schema 变更属于高权限操作，`AgentScope` 中单独控制（`allow_schema_draft: bool`，默认 `False`）
- Phase 1/2 中此能力不开放；Phase 3 评估是否启用

---

## 5. 与现有系统的接口映射

### 5.1 直接复用的现有接口

| 功能 | 现有接口 | 位置 |
|------|---------|------|
| 单条事实写入 | `write_protocol.set_field(ledger, pred_id, e_ref, rest_terms, meta)` | `core/evidence/write_protocol.py` |
| 批量追加 | `write_protocol.add_field(...)` | 同上 |
| 撤销 | `write_protocol.retract_by_asrt(ledger, revoked_asrt_id, meta)` | 同上 |
| 查询已有断言 | `list_runtime_claims(session_id, dto)` | `service/runtime_v1.py:257` |
| 证据图渲染 | `render_evidence_graph_html(graph)` | `audit/evidence_graph.py:96` |
| 证据图序列化 | `evidence_graph_to_dict(graph)` | `audit/evidence_graph.py:105` |
| Schema 加载 | `load_schema_ir(path)` / `ensure_schema_ir(data)` | `core/schema/schema_ir.py` |
| 会话管理 | `open_runtime_session` / `get_runtime_session` | `service/runtime_v1.py:166` |
| 规则编译 | `compile_authoring_rule_v1` | `authoring/rule_compile.py` |

### 5.2 需要新增的映射逻辑

| 需求 | 现有能力 | 缺口 | 处理层 |
|------|---------|------|------|
| 谓词 NL 搜索 | SchemaIR 有结构化谓词列表 | 无 NL 语义匹配 | 适配层：构造 LLM prompt 含谓词描述列表 |
| 实体引用解析 | 现有 entity resolution 路径 | 无 NL → e_ref 映射 | 适配层：`AgentScopeGuard.resolve_entity_ref` |
| 批量事务提交 | `set_field` 逐条调用 | 无原子批量端点 | 适配层：`BatchCommitEndpoint`（逐条调用 + 回滚日志） |
| Meta 置信度映射 | `_normalize_meta` 接受 `confidence` float | 无模糊语言映射 | 适配层：fuzzy confidence mapper |
| 引擎一致性检查 | `list_runtime_claims` 可查已有断言 meta | 无 pred_id → 已用引擎的聚合查询 | 适配层：`ConsistencyChecker`（扫描 meta.derivation_id） |
| 文档解析 | 无 | 需要 PDF/DOCX 解析能力 | 适配层：`DocumentParser`（第三方库封装） |

---

## 6. 权限与确认机制

### 6.1 AgentScope 设计

```python
@dataclass
class AgentScope:
    """注入到 AgentSession 的权限约束。"""
    allowed_entity_types: frozenset[str] | None  # None = 全部允许
    allowed_pred_ids: frozenset[str] | None       # None = 全部允许
    max_batch_size: int                            # 单次确认最大条数，默认 10
    require_source: bool                           # 是否强制要求 source 字段
    min_confidence: float                          # 允许录入的最低置信度，默认 0.0
    agent_id: str                                  # 当前 agent 实例标识（写入 meta.approved_by）
    allow_document_ingest: bool                    # 是否允许文档提取模式，默认 True
    allowed_engines: frozenset[str] | None         # 可用引擎白名单，None = 全部允许
```

### 6.2 确认流程

```
FactDraft (status=pending)
  │
  ├─ AgentScopeGuard.validate(draft, scope)
  │    ├─ pred_id 在白名单？
  │    ├─ entity_type 在白名单？
  │    ├─ confidence >= min_confidence？
  │    ├─ source 若 require_source=True 则非空？
  │    └─ engine_routing_hint.suggested_engine 在 allowed_engines？
  │
  ├─ 验证通过 → 展示 DraftPreview 给用户
  │
  └─ 用户确认 → status=confirmed
       │
       └─ BatchCommitEndpoint.commit(bundle)
            │
            └─ 调用 write_protocol.set_field，写入 meta={
                   "approved_by":  scope.agent_id,
                   "source":       draft.source,          ← 对话来源 或 文档名+章节
                   "source_loc":   draft.source_loc,      ← 文档字符偏移（文档模式）
                   "confidence":   draft.confidence,
                   "note":         draft.note,
                   "trace_id":     bundle.bundle_id,      ← 对话/文档批次溯源
               }
```

### 6.3 操作审计

每次 commit 在 meta 中写入：
- `approved_by`：agent_id（可追溯哪个 agent 会话写入）
- `trace_id`：bundle_id（可关联一次对话或一次文档提取的批量操作）
- `source` / `source_loc`：知识来源（文档模式下自动填入提取溯源）
- `note`：用户提供的备注

审计信息通过现有 `_SHARED_ANNOTATION_WHITELIST` 中的 `approved_by`、`source`、`note` 字段自动落入 `AnnotationRow`，无需额外存储层。

---

## 7. 系统需要新增的适配接口

### 7.1 SchemaDiscoveryAPI

**目的**：将 `SchemaIR` 中的机器友好结构翻译成 LLM prompt 可用的 NL 描述。

```python
class SchemaDiscoveryAPI:
    def list_entity_types(self) -> list[EntityTypeSummary]:
        """返回 entity_type + identity_fields 的可读摘要。"""

    def list_predicates(self, entity_type: str | None = None) -> list[PredicateSummary]:
        """返回谓词列表，含 pred_id、参数名称和类型描述。"""

    def describe_predicate(self, pred_id: str) -> PredicateDetail:
        """返回单个谓词的完整 arg_specs、group_key_indexes 描述。"""
```

输入：`schema_ir` dict（由 `load_schema_ir` 加载）

### 7.2 BatchCommitEndpoint

**目的**：将 `DraftBundle` 中已确认的 `FactDraft` 列表事务性地提交到 `Ledger`。

```python
class BatchCommitEndpoint:
    def commit(
        self,
        bundle: DraftBundle,
        *,
        ledger: Ledger,
        scope: AgentScope,
    ) -> BatchCommitResult:
        """
        逐条调用 write_protocol.set_field。
        任一条失败时记录部分提交状态（不回滚已成功条目，但标记失败条目）。
        返回 {committed: [asrt_id, ...], failed: [(draft_id, error), ...]}.
        """
```

注意：当前 `Ledger` 不支持分布式事务。`BatchCommitEndpoint` 采用"尽力提交 + 失败日志"语义，而非严格原子性。Phase 3 可引入真正的事务支持。

### 7.3 DraftPreviewRenderer

```python
class DraftPreviewRenderer:
    def render_text(self, draft: FactDraft) -> str:
        """返回 Markdown 格式的草稿摘要，用于终端/聊天界面。"""

    def render_html(self, draft: FactDraft) -> str:
        """
        返回 HTML 预览片段，含 EvidenceGraph 上下文。
        对于文档提取的 draft，额外展示原文段落高亮。
        """

    def render_batch_review_html(self, batch: ExtractionBatch) -> str:
        """
        渲染批量审核表格（文档提取模式）。
        每行含：来源段落、提取类型、实体、谓词、置信度、引擎推荐、操作按钮。
        """
```

### 7.4 AgentScopeGuard

```python
class AgentScopeGuard:
    def validate(self, draft: FactDraft, scope: AgentScope) -> None:
        """违反 scope 约束时抛出 AgentScopeViolation。"""

    def resolve_entity_ref(
        self,
        entity_type: str,
        identity: dict[str, Any],
        *,
        session: RuntimeSession,
    ) -> str:
        """
        将 {entity_type, identity_fields} 解析为系统 e_ref。
        Phase 1 使用简单拼接（entity_type:name），Phase 2 接入正式 entity resolution。
        """
```

### 7.5 DocumentParser（Phase 2）

```python
class DocumentParser:
    """第一阶段：确定性文档预处理。无 LLM 调用。"""

    def parse(self, source: DocumentSource) -> list[DocumentSegment]:
        """
        解析文档，返回结构化文本段列表。
        每段含原文、章节标签、页码、字符偏移、结构清晰度评分。
        """
```

### 7.6 ExtractionRefiner（Phase 2）

```python
class ExtractionRefiner:
    """第二阶段：受约束的 LLM 精炼。输入是预处理结果，非自由生成。"""

    def refine(
        self,
        segments: list[DocumentSegment],
        *,
        schema: SchemaDiscoveryAPI,
        scope: AgentScope,
    ) -> ExtractionBatch:
        """
        对每个 DocumentSegment，在 schema 约束上下文中调用 LLM：
        - 将文本实体映射到 entity_type + identity_fields
        - 将谓语动词映射到 pred_id
        - 补全隐含条件
        - 生成 LLM 自评置信度
        返回待审核的 FactDraft / RuleDraft 列表。
        """
```

### 7.7 EngineRoutingAdvisor（Phase 2）

```python
class EngineRoutingAdvisor:
    def route(
        self,
        draft: FactDraft | RuleDraft,
        *,
        user_text: str,
        session: RuntimeSession,
    ) -> EngineRoutingHint:
        """分析 draft 结构 + 用户原始文本，返回引擎推荐及解释。"""

    def check_consistency(
        self,
        pred_id: str,
        suggested_engine: str,
        *,
        session: RuntimeSession,
    ) -> ConsistencyWarning | None:
        """
        检查建议引擎是否与该 pred_id 在知识库中已有记录的引擎一致。
        通过扫描 list_runtime_claims 中的 meta.derivation_id 推断已用引擎。
        """
```

---

## 8. 可视化辅助

### 8.1 现有能力

- `EvidenceGraph` + `render_evidence_graph_html`：tree / timeline 双布局，HTML 片段输出
- `evidence_graph_to_dict` / `evidence_graph_from_dict`：序列化/反序列化
- `render_candidate_evidence_html`：候选证据树 HTML
- `render_rule_trace_detail_html`：规则追踪 HTML

### 8.2 Draft Preview 与上下文图

在 `DRAFT_PREVIEW` 阶段，`DraftPreviewRenderer.render_html` 执行：

1. 用 `list_runtime_claims` 查询目标实体的已有断言
2. 将已有断言 + 新 draft 共同构造为一个轻量 `EvidenceGraph`（draft 节点标注为 `node_kind=premise`）
3. 调用 `render_evidence_graph_html` 渲染，供用户在确认前直观看到新知识与现有知识的关系

**EvidenceGraph 节点对应关系**：

| 草稿内容 | EvidenceNode.node_kind | 说明 |
|---------|----------------------|------|
| 待录入事实 | `premise` | 草稿状态，未提交 |
| 已有断言（正活跃） | `seed` | 现有知识基础 |
| 关联规则推导结论 | `conclusion` | （如有 derivation 结果） |

### 8.3 文档提取批量审核界面

`render_batch_review_html` 生成如下概念表格：

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 文档提取审核：法规XYZ.pdf（共 23 条）  置信度过滤: [>0.7 ▼]                        │
├───┬──────────┬────────┬────────────┬──────────────┬──────┬───────────┬──────────┤
│ # │ 来源段落  │ 类型   │ 实体        │ 谓词         │ 置信度│ 推荐引擎  │ 操作     │
├───┼──────────┼────────┼────────────┼──────────────┼──────┼───────────┼──────────┤
│ 1 │ Art.3.1  │ Fact   │ 员工:张三   │ risk_level   │ 0.92 │ Souffle   │ ✓ ✗ ✎  │
│ 2 │ Art.3.2  │ Rule   │ —          │ must_report  │ 0.75 │ ProbLog   │ ✓ ✗ ✎  │
│ 3 │ Art.4.1  │ Fact   │ 合同:C-001 │ valid_until  │ 0.88 │ PyReason  │ ✓ ✗ ✎  │
│...│          │        │            │              │      │           │          │
├───┴──────────┴────────┴────────────┴──────────────┴──────┴───────────┴──────────┤
│ [全部通过]  [全部拒绝]  [通过置信度>0.8]                            [提交确认 →] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 分期路线图

### Phase 1：最小可用（MVP）

**目标**：支持单条事实录入的完整对话流程。

- [ ] `AgentSession` 状态机基础框架
- [ ] `SchemaDiscoveryAPI`（基于现有 `SchemaIR`）
- [ ] `FactDraft` 数据结构 + `DraftManager`
- [ ] OpenAI SDK 集成：意图识别（`ingest_fact` / `query_schema`）
- [ ] Slot filling：entity_type、pred_id、field_value（必填），confidence/source（可选）
- [ ] `AgentScopeGuard.validate` + 简单 e_ref 解析
- [ ] `BatchCommitEndpoint`（单条提交）
- [ ] `DraftPreviewRenderer.render_text`（Markdown 摘要）
- [ ] 确认流程 + `approved_by` / `trace_id` 写入 meta
- [ ] 基本单测覆盖

**不在 Phase 1 范围**：规则录入 / HTML 可视化 / 撤销流程 / 批量录入 / 文档提取 / 引擎路由 / SchemaDraft

---

### Phase 2：规则生成 + 引擎路由 + 文档提取 MVP

**目标**：覆盖完整知识类型（规则）、智能引擎推荐、基础文档提取能力。

**规则生成**：
- [ ] `RuleDraft` 数据结构（含 `engine_routing_hint`）
- [ ] OpenAI function calling：意图扩展（`ingest_rule`、`retract_fact`）
- [ ] 规则 slot filling：head、conditions、置信度
- [ ] `RuleDraft → compile_authoring_rule_v1` 翻译层
- [ ] `BatchCommitEndpoint` 支持 `DraftBundle`（多条）
- [ ] `DraftPreviewRenderer.render_html` + EvidenceGraph 上下文预览
- [ ] `retract_fact` 对话流程

**智能引擎路由**：
- [ ] `EngineRoutingHint` 数据结构
- [ ] `EngineRoutingAdvisor.route()`：语言线索分析（确定性/概率性/时序词汇识别）
- [ ] `EngineRoutingAdvisor.check_consistency()`：与已有记录引擎一致性检查
- [ ] Slot filling 中集成引擎推荐展示与用户覆盖流程
- [ ] `engine_routing_hint → confidence_kind` 映射（ProbLog→probability，PyReason→certainty）
- [ ] `AgentScope.allowed_engines` 约束

**文档提取 MVP**：
- [ ] `DocumentSource` + `DocumentSegment` + `ExtractionProvenance` + `ExtractionBatch` 数据结构
- [ ] `DocumentParser`：PDF 解析（pdfminer/pdfplumber）+ DOCX 解析（python-docx）
- [ ] `DocumentParser`：分段、章节边界检测、结构清晰度评分
- [ ] `DocumentParser`：if-then 模式识别（regex + 简单语法规则）
- [ ] `ExtractionRefiner`：集成 **DSPy** 强制 LLM 输出 schema-conformant JSON；集成 **LiteLLM** 替代直接 OpenAI SDK 调用
- [ ] `ExtractionBatch` + 文本模式批量审核流程（approve/reject/edit）
- [ ] `extraction_provenance → meta.source` / `meta.source_loc` 写入
- [ ] `ingest_from_document` 意图识别 + 文档上传处理
- [ ] **NetworkX** 集成：文档内实体关系图构建（为 Phase 3 可视化打基础）

---

### Phase 3：高级特性

**对话与规则**：
- [ ] 多实体批量录入（单次对话录入多个实体的关联事实）
- [ ] 对话历史持久化（跨会话恢复 draft）
- [ ] 置信度冲突检测（agent 主动提示与现有知识的冲突）
- [ ] `AgentScope` 动态配置 API（管理员 UI）
- [ ] Batch 原子性保证（Ledger 层事务支持）
- [ ] 多 LLM 后端支持已由 LiteLLM 覆盖，此项改为：LiteLLM 路由策略可配置（成本优化、fallback 链）

**SchemaDraft（补充能力）**：
- [ ] `SchemaDraft` 数据结构 + `SchemaRegistryAdapter`
- [ ] 文档提取/对话 slot filling 中的 schema miss 检测逻辑
- [ ] `AgentScope.allow_schema_draft` 权限控制
- [ ] `SchemaDraft` 审核界面（与批量审核界面统一入口）
- [ ] `SchemaRegistryAdapter.register()` → 调用现有 `schema_compile`/`schema_dsl_parse` 路径
- [ ] `FactDraft.status="blocked_by_schema"` 流转恢复机制

**文档提取高级**：
- [ ] `DraftPreviewRenderer.render_batch_review_html`：完整 HTML 批量审核界面（含原文高亮）
- [ ] NER + dependency parsing 增强实体/关系提取精度
- [ ] 语义向量检索（embedding-based predicate matching，解决大 schema 枚举爆炸）
- [ ] 提取结果缓存（相同文档 + 相同 schema → 复用预处理输出）
- [ ] 跨文档去重检测（新提取内容与已有断言的语义重叠提示）

**引擎路由高级**：
- [ ] PyReason 时序/图结构特征自动检测（时间戳字段、实体-实体关系边）
- [ ] 引擎路由决策历史记录（供用户复盘、供系统学习路由偏好）
- [ ] 混合引擎场景提示（同一 pred_id 部分断言需 ProbLog、部分 Souffle 时的协调策略）

---

## 10. 已知约束与开放问题

### 已知约束

1. **Ledger 无原子批量事务**：`BatchCommitEndpoint` 在多条提交时，若中途失败只能记录部分提交，无法回滚已成功条目。Phase 1 限制单条提交规避此问题。

2. **e_ref 解析依赖 entity resolution**：Phase 1 使用简单拼接策略（`entity_type:identity_value`）。若系统有复杂的 entity 去重逻辑，Phase 2 需接入正式 entity resolution 路径。

3. **OpenAI API 延迟**：每轮对话涉及 LLM 调用，延迟约 1~3s。适配层应为同步调用，调用方（API 层）负责异步封装。

4. **谓词枚举爆炸**：若 schema 包含大量谓词（>50），直接列举给 LLM 效果下降。Phase 3 引入语义向量检索。

5. **写协议 meta 字段约束**：`_SYSTEM_MANAGED_META_KEYS`（`ingested_at`、`ingest_key`、`revoked_asrt_id`）不可由 agent 写入，已在 `_normalize_meta` 中拦截。Agent 层不应尝试绕过。

6. **文档提取不保证完整性**：预处理阶段仅能识别明确的条件-结论结构；隐含规则（需要领域知识才能推断的约束）依赖 LLM 精炼，但 LLM 精炼有遗漏风险。批量审核由人工兜底。

7. **引擎路由不改变存储**：事实存储是引擎无关的（写入 `Ledger` 后对所有引擎可见）。引擎路由影响的是 `confidence_kind` 元数据和规则编译目标，不影响事实本身的物理存储路径。

8. **引擎一致性检查依赖 meta 可查性**：`ConsistencyChecker` 通过扫描 `list_runtime_claims` 中的 `meta.derivation_id` 推断已用引擎。若 derivation_id 未写入或格式不规范，一致性检查会降级为"无法判断"。

### 开放问题

| 问题 | 当前立场 | 待决策 |
|------|---------|------|
| Agent 会话与 RuntimeSession 的生命周期绑定方式 | 松耦合：`AgentSession` 持有 `session_id` 字符串，需要时获取 `RuntimeSession` | Phase 1 实现时确认 |
| 置信度模糊语言映射表（"很确定" → 0.9？）应固定还是可配置 | 先固定内置映射，后期可配置 | Phase 2 配置化 |
| 对话历史是否需要持久化到 Ledger | Phase 1 不持久化，仅 in-memory | Phase 3 评估 |
| 是否支持图形化 Web 前端（非纯聊天界面） | 不在本 blueprint 范围 | 独立 blueprint |
| `AgentScope` 的身份验证来源（谁能创建 scope？） | 外部调用方注入，agent 层信任传入的 scope | 与系统身份层对齐 |
| 规则草稿的可视化方式（RuleDraft） | 复用 `render_rule_trace_detail_html` 或新建 | Phase 2 决策 |
| 文档提取的 LLM 精炼是否需要 fine-tuning | Phase 2 用 prompt engineering + few-shot；若效果不达预期再评估 fine-tuning | Phase 2 评估 |
| 引擎路由冲突时的仲裁策略（用户倾向 Souffle，但 draft 有 confidence < 1.0）| 展示警告，用户仍可强制覆盖；不阻止提交 | Phase 2 实现时确认 |
| 文档提取的结果缓存粒度（按文档 + schema 哈希？） | Phase 2 不缓存；Phase 3 按 doc_id + schema_digest 缓存预处理输出 | Phase 3 设计 |
| `SchemaDraft` 注册后现有 blocked draft 如何自动恢复 | 重新触发 slot filling，不自动提交 | Phase 3 实现时确认 |
| `SchemaDraft` 是否应限制为管理员操作 | 默认关闭（`allow_schema_draft=False`），管理员显式开放 | 与系统身份层对齐 |

---

## 11. 文档规则提取管道（Document-to-Rules Pipeline）

### 11.1 设计理由：为什么不能纯 AI

文档提取采用**混合方法**，而非端到端 LLM，原因如下：

| 关注点 | 纯 LLM 方案的问题 | 混合方案的保证 |
|--------|------------------|---------------|
| **可审计性** | LLM 生成的规则难以追溯到源文本具体段落 | 每条 draft 携带 `ExtractionProvenance`，指向字符偏移级别的原文 |
| **可靠性** | LLM 对长文档容易幻觉，自由生成的谓词可能不存在于 schema | 预处理在 schema 约束下锁定候选谓词，LLM 只做消歧 |
| **可复现性** | 相同文档两次提取结果可能不同 | 预处理阶段（Stage 1）是确定性的；LLM 精炼输入固定，输出可缓存 |
| **成本** | 全文档送入 LLM 成本高 | 只将预处理筛选出的结构化段落送入 LLM，token 消耗可控 |

### 11.2 三阶段架构

```
文档输入（PDF / DOCX / TXT）
  │
  ▼ Stage 1: 预处理（确定性，无 LLM）
┌─────────────────────────────────────────────────┐
│ DocumentParser                                   │
│  ① 文档解析：PDF→文本（pdfminer/pdfplumber）      │
│              DOCX→文本（python-docx）             │
│  ② 分段：章节边界检测，段落切分                   │
│  ③ 结构识别：if-then 模式匹配（regex）            │
│             NER：识别实体提及                     │
│             关系抽取：主谓宾结构                  │
│  ④ 评分：每段计算 structural_clarity（0~1）       │
│          高分 = 明确的条件-结论结构               │
│          低分 = 叙述性、无明确逻辑结构            │
└────────────────────┬────────────────────────────┘
                     │ list[DocumentSegment]
  ▼ Stage 2: LLM 精炼（受约束，非自由生成）
┌─────────────────────────────────────────────────┐
│ ExtractionRefiner                                │
│  输入：DocumentSegment + SchemaIR 上下文          │
│  任务（每个 segment 独立 prompt）：              │
│    - 将实体提及映射到 entity_type + identity     │
│    - 将谓语动词映射到候选 pred_id（从 schema 中选）│
│    - 补全隐含前件（"员工必须" → subject=Employee）│
│    - 生成自评置信度（0~1）                        │
│  输出：FactDraft / RuleDraft（status=pending）    │
│  注意：LLM 只在预处理提供的结构上精炼，            │
│        不允许 LLM 引入 schema 外的新谓词           │
└────────────────────┬────────────────────────────┘
                     │ ExtractionBatch
  ▼ Stage 3: 人工审核（必须，不可绕过）
┌─────────────────────────────────────────────────┐
│ BATCH_REVIEW 状态                                │
│  - 用户逐条 approve / reject / edit              │
│  - 可按置信度阈值批量过滤（如"仅通过>0.8"）      │
│  - 每条均展示：原文段落、提取结果、引擎推荐       │
│  - 审核完成 → 生成 DraftBundle → 进入 COMMITTING │
└─────────────────────────────────────────────────┘
```

### 11.3 关键数据结构

```python
@dataclass
class DocumentSource:
    """文档来源登记。"""
    doc_id: str                    # SHA-256(文档内容)，用于去重和缓存
    doc_name: str                  # 原始文件名
    doc_type: Literal["pdf", "docx", "txt"]
    ingested_at: int               # epoch_nanos


@dataclass
class DocumentSegment:
    """预处理阶段输出的结构化文本段。"""
    segment_id: str
    doc_id: str
    section_label: str | None      # "Article 3.2"、"第五条"等章节标签
    page_number: int | None        # PDF 页码
    char_offset_start: int         # 在全文提取文本中的字符起始偏移
    char_offset_end: int
    raw_text: str                  # 对应的原始文本
    structural_clarity: float      # 预处理评分（0~1）
    pattern_type: Literal[
        "if_then",                 # 明确的条件-结论结构
        "entity_relation",         # 实体关系陈述
        "definition",              # 定义句
        "narrative",               # 叙述性，结构不明确
    ]


@dataclass
class ExtractionProvenance:
    """附在 FactDraft/RuleDraft 上的提取溯源。"""
    doc_id: str                    # references DocumentSource.doc_id
    doc_name: str                  # 便于展示，冗余存储
    section_label: str | None
    page_number: int | None
    char_offset_start: int
    char_offset_end: int
    raw_text: str                  # 提取来源的精确原文片段
    structural_clarity: float      # 预处理给出的结构清晰度
    llm_confidence: float | None   # LLM 精炼阶段的自评置信度
    extraction_method: Literal[
        "pattern_match",           # 纯预处理正则识别
        "ner_relation",            # NER + 关系抽取
        "llm_refinement",          # LLM 精炼生成
    ]


@dataclass
class ExtractionBatch:
    """一次文档提取产出的待审核草稿集合。"""
    batch_id: str
    doc_id: str
    facts: list[FactDraft]
    rules: list[RuleDraft]
    total_segments_processed: int
    high_clarity_count: int        # structural_clarity >= 0.7 的段数
    created_at: int
```

### 11.4 Provenance 到 meta 的映射

`ExtractionProvenance` 在 `BatchCommitEndpoint.commit()` 时写入 `meta`：

```python
meta = {
    # 文档名 + 章节标签，用于 AnnotationRow（_SHARED_ANNOTATION_WHITELIST.source）
    "source":     f"{provenance.doc_name} § {provenance.section_label or 'unknown'}",
    # 字符偏移范围，供精确回溯
    "source_loc": f"chars:{provenance.char_offset_start}-{provenance.char_offset_end}",
    "note":       f"[doc:{provenance.doc_id[:8]}] {provenance.raw_text[:120]}...",
    "confidence": draft.confidence,     # LLM 自评 × 结构清晰度的综合值
    "approved_by": scope.agent_id,
    "trace_id":   bundle.bundle_id,
}
```

这样通过现有 `_SHARED_ANNOTATION_WHITELIST` 的 `source` 字段，每条写入断言天然携带文档级溯源，在 `EvidenceGraph` 中可见。

### 11.5 置信度合并策略

文档提取的最终 `FactDraft.confidence` 由两个信号合并：

```
final_confidence = structural_clarity × 0.4 + llm_confidence × 0.6
```

- `structural_clarity`（0~1）：预处理阶段，越高表示文本结构越明确（if-then 清晰）
- `llm_confidence`（0~1）：LLM 精炼阶段自评，越高表示映射到 schema 越确信

用户在批量审核界面可看到两个分量，判断是否需要手动修改置信度。

### 11.6 技术策略：自建 Pipeline + 复用基础组件

#### 为什么不直接使用 kggen

我们参考了 kggen 验证过的三阶段 pipeline 架构（实体提取 → 关系提取 → 去重聚类），但**不直接集成 kggen**，原因如下：

| 差异点 | kggen 的做法 | 我们的需求 |
|--------|------------|-----------|
| **输出格式** | 通用三元组 `(subject, predicate, object)` | schema-aware：`(pred_id, entity_ref, typed fields)`，与 SchemaIR 严格对应 |
| **置信度** | 无置信度概念 | `FactDraft.confidence`，含结构清晰度 + LLM 自评双分量 |
| **Provenance** | 无字符级来源追踪 | `ExtractionProvenance` 精确到 `char_offset`，必须可回溯 |
| **去重策略** | 基于文本语义相似度（embedding cosine） | 基于 `pred_id + e_ref` 的结构化去重（与 `ingest_key` 幂等机制对齐） |
| **引擎路由** | 无推理引擎概念 | `EngineRoutingHint` 需贯穿提取 → 审核 → 提交全流程 |
| **Schema 约束** | 开放世界，LLM 自由生成谓词 | 封闭世界，LLM 只能从 `SchemaIR.predicates` 中选择 |

如果强行适配 kggen，适配层会越来越厚，最终比自建更难维护。

#### 架构借鉴 kggen 的部分

虽然不直接使用 kggen，我们的 `DocumentParser`（Stage 1）和 `ExtractionRefiner`（Stage 2）借鉴了 kggen 验证过的以下决策：

- **分段优先**：不整文档送入 LLM，先分段再按段独立处理（控制 context window，降低幻觉）
- **实体先于关系**：先识别实体提及，再做关系抽取（减少 LLM 需要推断的上下文量）
- **多次精炼优于单次完整提取**：迭代式精炼比一次性生成质量更稳定

#### 复用 kggen 的基础组件

| 组件 | 作用 | 在本 pipeline 中的用途 |
|------|------|----------------------|
| **LiteLLM** | 多 LLM provider 路由（OpenAI / Anthropic / 本地模型） | 替代直接 OpenAI SDK；统一管理 API key、fallback、成本限额 |
| **DSPy** | 结构化输出约束（Declarative Self-improving Language Programs） | 强制 `ExtractionRefiner` 输出严格符合 SchemaIR 格式的 JSON，减少 LLM 格式幻觉 |
| **NetworkX** | Python 图结构库 | 文档内实体关系图构建；Phase 3 可视化辅助；引擎路由的图结构检测 |

#### 自建部分的差异化实现

```
DocumentParser（Stage 1）—— 自建，无法复用 kggen
  ├─ schema-guided 实体提取：优先匹配 SchemaIR.entities[].entity_type
  │   而非通用 NER（减少后续消歧工作量）
  └─ structural_clarity 评分：基于 if-then 模式覆盖度，非 kggen 的置信度

ExtractionRefiner（Stage 2）—— 自建逻辑，工具层使用 DSPy + LiteLLM
  ├─ schema-constrained 关系提取：字段类型必须符合 SchemaIR.arg_specs[].type_domain
  └─ 输出验证：DSPy signature 定义输出 schema，不符合则重试（最多 3 次）

去重阶段（Stage 3 前置）—— 自建，基于断言级去重
  └─ 利用 write_protocol._compute_ingest_key 的幂等机制：
     相同 (pred_id, e_ref, rest_terms, source) → 相同 ingest_key → Ledger 自动 skip
     而非 kggen 的 embedding cosine 相似度去重
```

---

## 12. 智能引擎路由（Intelligent Engine Routing）

### 12.1 路由策略

Agent 根据知识特征自动推荐最适合的推理引擎，避免用户手动选择。

| 知识特征 | 推荐引擎 | 路由依据 |
|---------|---------|---------|
| 确定性事实/规则，无概率，无时序 | **Souffle** | Datalog 推理；明确因果/分类规则；语言无模糊词 |
| 含不确定性/概率 | **ProbLog** | `confidence < 1.0`；或语言线索含概率性词汇 |
| 时序变化/传播效应/图关系 | **PyReason** | 涉及时间步、图传播、演化规律 |
| 快速验证/原型/纯事实查询 | **Native** | 无规则推理需求；简单事实存储 |

### 12.2 三类决策依据

#### 依据 1：语言线索（Linguistic Cues）

从用户原始文本中识别触发词：

```python
CERTAINTY_CUES = {
    # 中文
    "一定", "必须", "必然", "肯定", "确定", "是", "事实上",
    # 英文
    "must", "always", "certainly", "is", "exactly",
}

PROBABILITY_CUES = {
    # 中文
    "可能", "大约", "估计", "大概率", "不确定", "约", "左右",
    "有X%的概率", "据估计", "倾向于", "通常",
    # 英文
    "probably", "likely", "approximately", "around", "uncertain",
    "roughly", "tends to",
}

TEMPORAL_CUES = {
    # 中文
    "随时间", "在第T步", "传播", "随着...变化", "最终", "逐渐",
    "扩散", "演化", "在时刻", "t步后",
    # 英文
    "over time", "at timestep", "propagates", "evolves", "eventually",
    "spreads", "at time t",
}
```

#### 依据 2：Draft 结构特征

```python
def _infer_from_draft(draft: FactDraft | RuleDraft) -> str:
    # ProbLog 信号：置信度 < 1.0
    if draft.confidence is not None and draft.confidence < 1.0:
        return "problog"

    # PyReason 信号：规则前件中含时间步变量或图传播结构
    if isinstance(draft, RuleDraft):
        if _has_temporal_conditions(draft.conditions):
            return "pyreason"
        if _has_graph_propagation(draft.conditions):
            return "pyreason"

    # 默认：Souffle（确定性 Datalog）
    return "souffle"
```

#### 依据 3：现有知识库引擎一致性

通过 `ConsistencyChecker.check_consistency(pred_id, suggested_engine, session)` 实现：

```python
# 伪代码：扫描 list_runtime_claims 中 pred_id 已有断言的 meta
existing_derivation_ids = [
    meta["derivation_id"]
    for claim in list_runtime_claims(pred_id=pred_id)
    if "derivation_id" in claim.meta
]
# 从 derivation_id 推断已用引擎（约定：derivation_id 前缀编码引擎类型）
existing_engines = {infer_engine_from_derivation_id(d) for d in existing_derivation_ids}

if suggested_engine not in existing_engines and existing_engines:
    return ConsistencyWarning(
        pred_id=pred_id,
        suggested_engine=suggested_engine,
        existing_engines=existing_engines,
        message=f"该谓词已有 {existing_engines} 引擎的记录，混用可能导致查询时需指定引擎",
    )
```

### 12.3 EngineRoutingHint 数据结构

```python
@dataclass
class EngineRoutingHint:
    suggested_engine: Literal["souffle", "problog", "pyreason", "native"]
    routing_confidence: float              # 路由决策自信度（0~1）
    reasoning: str                         # 向用户展示的中文解释
    linguistic_cues: list[str]             # 触发路由决策的关键词/短语
    structure_signals: list[str]           # 触发路由的 draft 结构特征描述
    consistency_warning: ConsistencyWarning | None   # 若与已有记录不一致
    can_override: bool = True              # 始终允许用户覆盖
    override_warning: str | None = None   # 用户强制覆盖时额外展示的风险提示
```

### 12.4 用户交互流程

引擎推荐在 `DRAFT_PREVIEW` 阶段展示，用户可接受或覆盖：

```
Agent: 我分析了您的描述，推荐使用以下引擎：

       推荐引擎: ProbLog（概率推理）
       路由依据:
         • 置信度 0.75 < 1.0，含有不确定性
         • 描述中检测到"大概率"等概率性表达
       一致性检查: ✓ 该谓词（risk_level）已有 ProbLog 记录，一致

       如需更改：
         [1] Souffle — 确定性推理（如确定不需要概率建模）
         [2] PyReason — 时序/图推理（如涉及时序传播）
         [3] Native — 快速验证，无推理规则
       直接回车接受推荐的 ProbLog
```

若用户输入 `[1]` 覆盖：

```
Agent: 注意：您选择了 Souffle，但该谓词有置信度 0.75 < 1.0。
       Souffle 不支持概率推理，置信度信息将作为 meta 存储但不会参与推理计算。
       是否继续？（是/否）
```

### 12.5 引擎路由与写协议的集成

`engine_routing_hint.suggested_engine` 在提交时影响 `confidence_kind` 字段：

| 推荐引擎 | `confidence_kind` | 说明 |
|---------|-----------------|------|
| `problog` | `"probability"` | 置信度参与 ProbLog 概率推理计算 |
| `pyreason` | `"certainty"` | 置信度解释为 certainty interval 的下界 |
| `souffle` | `"none"` | 置信度仅作 meta 存储，不参与 Datalog 推理 |
| `native` | `"none"` | 同 Souffle |

对于 `RuleDraft`，`suggested_engine` 决定 `compile_authoring_rule_v1` 的目标引擎扩展（通过 `_resolve_runtime_derivation_engine_ext` 在 `runtime_v1.py:820` 处理）。

---

## 13. 运维与可靠性 **[待展开]**

> **注意**：本章节为占位框架，列出已识别的关键风险点和初步缓解思路。完整的运维设计将在后续专题讨论中展开，届时更新为独立的 ops blueprint 或本文档的详细子节。

### 13.1 已识别风险

**风险 1：LLM 依赖风险**
- 延迟不可控（P99 可达 10s+），影响对话流畅性和文档提取吞吐
- 成本随提取文档量线性增长，大批量文档处理成本不可预估
- API 限流/变更（provider 修改接口或下线模型版本）
- 模型版本漂移：同一 prompt，新版本模型的提取质量与旧版本不一致

**风险 2：多阶段错误传播**
- Stage 1 分段错误（如 PDF 解析丢失段落）会静默传播到 Stage 2/3，用户只看到少了几条提取结果
- Stage 2 LLM 输出格式违规（DSPy 重试耗尽后）导致整批失败，无法部分恢复
- 排查需要每阶段的中间结果完整日志，否则无法定位错误在哪个阶段引入

**风险 3：Draft 生命周期管理**
- `DraftManager` 是 in-memory staging area，进程重启后 pending draft 丢失
- 用户长时间不操作（小时级），draft 可能因 schema 变更而失效（`pred_id` 被删除或字段类型变更）
- 文档提取产生大量 draft（数百条），staging area 内存占用需要上限

**风险 4：LLM 输出质量监控**
- 提取准确率随模型版本、schema 复杂度、文档风格变化而漂移
- 无监控机制时，质量下降只有用户审核时才能发现，存在滞后
- 用户 approve/reject 行为本身是质量信号，但未设计反馈收集机制

### 13.2 初步缓解思路（待展开为完整设计）

| 风险 | 初步缓解方向 |
|------|------------|
| LLM 延迟/成本 | LiteLLM 缓存层（相同输入 → 缓存输出，避免重复调用）；文档提取异步化（后台任务，不阻塞对话） |
| LLM 不可用 | Graceful degradation：LLM 不可用时退回纯 Stage 1 结构化结果 + 提示用户手动补全 |
| 错误传播排查 | 每阶段输出完整 provenance 日志，含输入摘要、处理耗时、输出计数；失败时保留中间状态供调试 |
| Draft 丢失 | Draft TTL 策略（超时后标记 `status="expired"`）；Phase 3 评估持久化到 Ledger 的必要性 |
| Schema 变更失效 | Draft 携带创建时的 `schema_digest`；提交前校验当前 schema digest，不一致则提示用户重新确认 |
| 质量监控 | 收集用户 approve/reject/edit 比例作为质量指标；阈值告警（如 reject 率 > 30%） |

### 13.3 待专题展开的议题

以下议题在本 blueprint 范围内不做完整设计，标记为后续专题：

- [ ] **LLM 成本预算与限额设计**：per-session 和 per-document 的 token 上限机制
- [ ] **Draft 持久化方案**：是否写入 Ledger 作为特殊断言类型，还是独立存储
- [ ] **质量反馈闭环**：用户 reject 数据如何反哺 DSPy prompt 优化
- [ ] **LiteLLM fallback 链配置**：主 provider 不可用时的降级顺序和质量权衡
- [ ] **多阶段分布式追踪**：trace_id 跨 Stage 1/2/3 的传播设计（与现有 `meta.trace_id` 对齐）

---

## 附录 A：关键现有接口速查

### write_protocol.py 核心函数签名

```python
# 写入/覆盖一个字段断言（幂等）
set_field(ledger, pred_id, e_ref, rest_terms, meta=None) -> str  # 返回 asrt_id

# 追加一个字段断言（与 set_field 相同实现，语义标注不同）
add_field(ledger, pred_id, e_ref, rest_terms, meta=None) -> str

# 撤销一个断言
retract_by_asrt(ledger, revoked_asrt_id, meta=None) -> str | None

# meta 关键字段（由 Agent 层填充）
meta = {
    "source":     str,           # 知识来源描述（或文档名+章节）
    "source_loc": str,           # 来源定位（文档模式：字符偏移范围）
    "trace_id":   str,           # 对话 bundle_id 或文档提取 batch_id
    "confidence": float,         # (0, 1]
    "probability": float,        # (0, 1]（ProbLog 场景）
    "approved_by": str,          # agent_id
    "note":       str,           # 备注（文档模式：含原文摘要）
}
```

### SchemaIR 结构概览

```json
{
  "schema_ir_version": "v1",
  "entities": [
    {
      "entity_type": "Person",
      "identity_fields": [
        {"name": "name", "type_domain": "string"}
      ]
    }
  ],
  "predicates": [
    {
      "pred_id": "credit_score",
      "arg_specs": [
        {"name": "score", "type_domain": "int"}
      ],
      "group_key_indexes": []
    }
  ],
  "projection": {"entities": [...], "predicates": [...]}
}
```

### EvidenceGraph 数据结构概览

```python
EvidenceGraph(
    graph_id="...",
    engine="agent_draft",       # agent 生成的预览图使用此 engine 标识
    root_node_id="...",
    nodes=(
        EvidenceNode(node_id="n1", node_kind="seed",    ...),  # 现有知识
        EvidenceNode(node_id="n2", node_kind="premise", ...),  # 待录入草稿
    ),
    edges=(
        EvidenceEdge(edge_id="e1", from_node_id="n1", to_node_id="n2",
                     edge_kind="supports"),
    ),
    support_kind="agent_draft",
    layout_hint="tree",
)
```

### CandidateSet.confidence_kind 可选值

```python
CONFIDENCE_KINDS = frozenset({"none", "probability", "certainty"})
# "none"        → Souffle / Native：置信度不参与推理
# "probability" → ProbLog：置信度作为概率权重
# "certainty"   → PyReason：置信度作为 certainty interval
```

---

### AgentScope 完整字段速查

```python
@dataclass
class AgentScope:
    agent_id: str
    allowed_entity_types: frozenset[str] | None   # None = 全部允许
    allowed_pred_ids: frozenset[str] | None        # None = 全部允许
    allowed_engines: frozenset[str] | None         # None = 全部允许
    max_batch_size: int                            # 默认 10
    require_source: bool                           # 默认 False
    min_confidence: float                          # 默认 0.0
    allow_document_ingest: bool                    # 默认 True
    allow_schema_draft: bool                       # 默认 False（高权限，需显式开放）
```

---

*Blueprint 状态: draft — 实现前需经过 scoped 评审确认接口边界。*
