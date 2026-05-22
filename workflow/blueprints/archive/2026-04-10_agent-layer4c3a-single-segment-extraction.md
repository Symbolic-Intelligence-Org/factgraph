# Blueprint: Agent Layer 4C3-a — Single-Segment LLM Extraction

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on:
  - Layer 4C1 确定性文档 staging (archived)
  - Layer 4C2 DraftBundle review/approval (archived)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/` (新建)
  - `src/factpy_kernel/agent/extraction/extractor.py` (新建)
  - `src/factpy_kernel/agent/extraction/validation.py` (新建)
  - `src/factpy_kernel/agent/extraction/llm.py` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：把单个 `DocumentSegment` 送入 LLM（通过 Instructor + LiteLLM），在 schema 约束下产出 `list[FactDraftSpec]`。输出经过 deterministic validation（schema + scope + field typing），然后交给 Layer 4C2 的 bundle 流程。

**这是 agent 代码库第一次真正发 model call**。所有之前的 Layer 都是纯 tool orchestration，不调 LLM。

**冻结决策**（本轮锁定，正文围绕这 6 条展开）：

| # | 决策 | 理由 |
|---|------|------|
| L4C3a-01 | 只做 single-segment → FactDraftSpec[] | 避免 scope 爆炸；批量/速率/消歧留给 4C3-b/c |
| L4C3a-02 | LLM 只提议，不 commit，不直接写 DraftManager | 输出是 FactDraftSpec[]；bundle 创建仍由调用方/4C2 触发 |
| L4C3a-03 | 只能抽现有 schema 可表达的 facts | 无法映射 schema 的提议必须被拒绝；SchemaDraft 不在范围 |
| L4C3a-04 | ExtractionProvenance 完全继承自 4C1 segment，不让模型生成 offsets | 模型不产出 doc_id/segment_id/offsets；这些由代码注入 |
| L4C3a-05 | 输出先过 deterministic validation：schema + scope + field typing | LLM 不是可信源；所有字段必须通过确定性校验 |
| L4C3a-06 | v1 不做 cross-segment dedupe / entity resolution | 跨 segment 问题是 4C3-c 的事 |

**明确排除**：
- 多 segment 批量 / 速率控制 / retry / partial failure
- 跨 segment entity resolution / 去重 / 合并
- RuleDraft 抽取
- SchemaDraft（当模型想提议新 pred_id 时）
- 自由生成（不受 schema 约束的开放式抽取）
- LLM 直接操作 DraftManager / BundleManager / ledger
- Langfuse 深度集成（Phase 5）

---

## 1. 6 条冻结决策的展开

### 1.1 L4C3a-01：只做 single-segment → FactDraftSpec[]

**范围**：
- 输入：**单个** `DocumentSegment`（从 Layer 4C1 staging 产出）
- 输出：`list[FactDraftSpec]`（0 到 `scope.max_batch_size` 条，受 AgentScope 限制）

**`max_batch_size` 处理**（L4C3a-18 冻结）：
- 从 `session.scope.max_batch_size` 读取上限
- LLM 返回的 proposals 数量 > max_batch_size 时：
  1. 按 LLM 原始顺序保留前 `max_batch_size` 条
  2. 超出部分逐条记录为 `ExtractionRejection(reason="scope_max_batch_size", proposal_index=...)`
  3. 不阻断已接受的条目
- 等价于把 max_batch_size 作为 LLM 输出的截断器 + scope 校验的一部分
- truncated 条目仍然经过前面所有 validation，只是在最终输出前被丢弃

**不做**：
- `list[DocumentSegment] → ...` 的批量 API
- 任何 retry / rate limiting / timeout 编排（Instructor 原生 retry 除外）
- partial failure 聚合

**调用方负责**：
- 遍历 segments 逐个调用
- 速率控制
- 错误处理

### 1.2 L4C3a-02：LLM 只提议，不 commit

**数据流**：
```
DocumentSegment
      │
      ▼
ExtractionAgent.extract_from_segment(segment, scope)
      │                    ↓ LLM call (Instructor + LiteLLM)
      ▼
list[FactDraftSpec]      ← LLM 提议
      │
      ▼ deterministic validation
list[FactDraftSpec]      ← validated 提议
      │
      ▼ 返回给调用方
    (调用方决定下一步：create_document_bundle / discard / 手动编辑)
```

**不做**：
- ExtractionAgent 不调 `draft_manager.create_draft()`
- ExtractionAgent 不构造 `DraftBundle`
- ExtractionAgent 不调 `orchestrator.create_document_bundle()`

**理由**：bundle 创建是 L4C2-14 的事（BundleManager 负责注册为 managed drafts）。ExtractionAgent 产出的 FactDraftSpec 是中间表示，等调用方决定 commit 路径。

### 1.3 L4C3a-03：只能抽现有 schema 可表达的 facts

**约束**：
- Instructor 的 Pydantic response model 的字段必须对应 schema 中已注册的 entity_type + pred_id
- LLM 提议 schema 外的 entity_type 或 pred_id → validation 拒绝 → 从输出中过滤
- 不生成 SchemaDraft（不在 4C3-a 范围）

**实施方式**：
- 在 prompt 中注入 schema 摘要（entity_types + pred_ids + 关键字段）
- Instructor response model 是 enum-like 结构：`entity_type` 必须 ∈ allowed set
- 后置 validation 再做一次 defensive 检查

### 1.4 L4C3a-04：ExtractionProvenance 由代码注入，不让模型生成

**LLM 只生成**：
- `entity_type: str` (必须在 allowed list 中)
- `entity_identity: dict`
- `pred_id: str` (必须在 allowed list 中)
- `field_values: list[tuple[str, Any]]`
- `confidence: float | None` (可选，LLM 自评)

**代码从 segment 注入**（L4C3a-19 冻结 raw_text 语义）：
```python
provenance = ExtractionProvenance(
    source_document_id=segment.doc_id,           # ← 从 segment 复制
    segment_id=segment.segment_id,               # ← 从 segment 复制
    page_number=segment.page_number,             # ← 从 segment 复制
    char_offset_start=segment.char_offset_start, # ← 从 segment 复制
    char_offset_end=segment.char_offset_end,     # ← 从 segment 复制
    raw_text=segment.raw_text,                   # ← 完整 segment.raw_text，不截断
    extraction_method="llm_refined",             # ← 固定值
)
```

**raw_text 语义（L4C3a-19 冻结）**：
- `ExtractionProvenance.raw_text` 永远是完整的 `segment.raw_text`
- 送给 LLM 的 prompt 中的 text 可能被 `config.max_text_chars` 截断
- 两者是独立字段：provenance 记录"实际原文"，LLM 输入记录"模型看到什么"
- 审计时以 provenance.raw_text 为准；LLM 输入不持久化
- char_offset_start/end 对应完整 raw_text 在文档中的偏移，不受截断影响

**为什么不让模型生成 provenance**：
- doc_id / segment_id / offsets 是审计链锚点，必须确定性
- LLM 如果生成错误的 offset，审计链就断了
- 这是 Layer 4C1 确定性底座原则的延续（delta D-09）

### 1.5 L4C3a-05：deterministic validation

**验证层级**：

1. **Instructor 层（LLM 输出阶段）**
   - Pydantic response model 约束字段类型
   - `entity_type: Literal[...]`、`pred_id: Literal[...]` 限定 allowed set
   - Instructor 失败时自动 retry（1-3 次）

2. **Schema 验证（post-LLM）**
   - 对每条 FactDraftSpec：
     - entity_type 在 schema.entities 中存在
     - pred_id 在 schema.predicates 中存在
     - field_values 的 tag 在 pred 的 arg_specs 中
     - field_values 的值类型匹配 type_domain

3. **Scope 验证（post-Schema）**
   - AgentScopeGuard 规则：
     - entity_type 在 scope.allowed_entity_types（如果非 None）
     - pred_id 在 scope.allowed_pred_ids（如果非 None）
     - confidence ≥ scope.min_confidence（如果 confidence 非 None）

4. **FactDraftSpec 构造时校验**
   - Layer 4C2 已有的 `FactDraftSpec.__post_init__`
   - 保证最终对象满足所有不变量

**失败处理**：
- 任一层失败 → 该 spec 从输出列表过滤掉
- 不 raise，不阻塞其他条目
- 返回 `ExtractionResult(valid_specs=[...], rejections=[ExtractionRejection, ...], total_proposals=int, ...)`
- 详见 §3.3 数据模型

### 1.6 L4C3a-06：不做跨 segment 处理

**明确**：
- ExtractionAgent 每次调用独立
- 不维护 cross-call state
- 不做 entity dedupe（可能同一实体从多个 segment 多次提出）
- 不做引用解析（如 "the above clause" 指向哪里）

**调用方/后续 layer 负责**：
- 跨 segment 聚合
- 去重
- 引用消解

---

## 2. 技术栈集成

### 2.1 依赖声明

```toml
# optional dependencies (pyproject.toml)
extraction = [
    "instructor>=1.6",
    "litellm>=1.50",
    "pydantic>=2",         # 已有
]
```

与 4C1 的 `documents` 组类似，作为 optional。不装则 extraction 不可用，其他 Layer 不受影响。

### 2.2 Instructor + LiteLLM 组合

```python
import instructor
from litellm import completion

# Instructor patches litellm
client = instructor.from_litellm(completion)

# 使用
response = client.chat.completions.create(
    model="gpt-4o-mini",   # via LiteLLM；可换 claude-3-5-sonnet-latest 等
    response_model=SegmentExtractionResponse,
    messages=[...],
    max_retries=2,
)
```

### 2.3 LLM 配置

```python
@dataclass(frozen=True)
class ExtractionConfig:
    """LLM 调用配置。"""
    model: str = "gpt-4o-mini"           # LiteLLM 兼容的 model 名
    max_retries: int = 2
    temperature: float = 0.0              # 确定性
    max_tokens: int | None = None
    timeout_seconds: float = 30.0
    max_text_chars: int = 4000            # segment.raw_text 截断阈值
```

---

## 3. 数据模型

### 3.1 ExtractionConfig

见 §2.3。

### 3.2 LLM Response Model (Pydantic)

Response model 在运行时基于 schema_ir 动态构造（L4C3a-16）。`entity_type` 和 `pred_id` 字段用 `Literal[...]` 约束到当前 schema 的允许值，强制 Instructor 在 LLM 输出阶段就拒绝 schema 外的提议。

```python
from pydantic import BaseModel, Field, create_model
from typing import Literal, Any


def build_response_model(schema_ir: dict[str, Any]) -> type[BaseModel]:
    """
    动态构造 SegmentExtractionResponse。

    entity_type 和 pred_id 用 Literal[...] 限定到 schema 允许值。
    Instructor 会将这些 Literal 作为 schema 约束发给 LLM，
    强制输出落在允许集内。
    """
    allowed_entity_types = tuple(
        e["entity_type"] for e in schema_ir.get("entities", [])
    )
    allowed_pred_ids = tuple(
        p["pred_id"] for p in schema_ir.get("predicates", [])
    )

    EntityTypeLiteral = Literal[allowed_entity_types]     # type: ignore[valid-type]
    PredIdLiteral = Literal[allowed_pred_ids]             # type: ignore[valid-type]

    LLMFactProposal = create_model(
        "LLMFactProposal",
        entity_type=(EntityTypeLiteral, Field(..., description="Entity type from allowed list")),
        entity_identity=(dict[str, Any], Field(..., description="Identity fields")),
        pred_id=(PredIdLiteral, Field(..., description="Predicate ID from allowed list")),
        field_values=(
            list[tuple[str, Any]],
            Field(..., description="List of (tag, value) pairs for predicate fields"),
        ),
        confidence=(float | None, Field(None, ge=0.0, le=1.0, description="LLM self-assessed confidence")),
        llm_note=(str | None, Field(None, description="Optional reasoning note")),
    )

    SegmentExtractionResponse = create_model(
        "SegmentExtractionResponse",
        proposals=(
            list[LLMFactProposal],
            Field(default_factory=list, description="Extracted fact proposals. Empty if no facts found."),
        ),
    )

    return SegmentExtractionResponse
```

**为什么不用静态类定义**：Instructor 需要将 `Literal[...]` 作为 schema 约束传递给 LLM，但 Literal 的允许值来自运行时的 schema_ir。静态定义 `entity_type: str` 会丢掉第一层约束，让 validation pipeline 承担更多压力。

**v1 不缓存**：每次 `extract_from_segment` 调用都重新构造。后续可按 `schema_digest` 缓存。

### 3.3 ExtractionResult

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ExtractionRejection:
    """单条 proposal 被拒绝的结构化描述。"""
    reason: Literal[
        "schema_entity_type_unknown",
        "schema_pred_id_unknown",
        "schema_field_type_mismatch",
        "scope_entity_type_denied",
        "scope_pred_id_denied",
        "scope_min_confidence",
        "scope_max_batch_size",           # L4C3a-18：超出 scope.max_batch_size 截断
        "spec_construction_failure",
    ]
    detail: str
    proposal_index: int                  # 在 LLM 原始输出中的索引


@dataclass
class ExtractionResult:
    """
    Single-segment extraction 的结构化返回。
    """
    segment_id: str                      # 对应的 DocumentSegment.segment_id
    valid_specs: list[FactDraftSpec]     # 通过所有验证的 specs
    total_proposals: int                 # LLM 原始提议数
    rejections: list[ExtractionRejection] # 被拒绝的条目详情
    model: str                           # 实际使用的 LLM 模型
    llm_latency_ms: int                  # LLM 调用耗时
```

### 3.4 ExtractionError

```python
@dataclass
class ExtractionError:
    """
    整个 extraction 调用失败（LLM 不可达 / 超时 / Instructor retry 耗尽）。
    不用于单条 proposal 拒绝（那是 ExtractionRejection）。
    """
    segment_id: str
    error_kind: Literal[
        "llm_unavailable",
        "llm_timeout",
        "instructor_retry_exhausted",
        "config_invalid",
        "dependency_missing",           # instructor/litellm 未安装
    ]
    error_message: str
```

---

## 4. ExtractionAgent

### 4.1 职责

单 segment → LLM → 验证 → FactDraftSpec[] 的完整链路。

**不做**：
- 不持有 AgentSession（解耦 session 状态）
- 不操作 DraftManager / BundleManager
- 不 checkpoint
- 不做 batch / retry 编排（除 Instructor 内置 retry）

### 4.2 接口

```python
class ExtractionAgent:
    """
    Single-segment LLM extraction agent（L4C3a-01）。

    纯函数式设计：输入 segment + schema + scope + config，
    输出 ExtractionResult 或 ExtractionError。不维护状态。
    """

    def __init__(
        self,
        *,
        config: ExtractionConfig,
        llm_client: Any | None = None,  # Instructor client; None = 延迟构造
    ) -> None:
        """
        config: LLM 调用配置
        llm_client: 可选，用于测试注入 mock
        """
        ...

    def extract_from_segment(
        self,
        *,
        segment: DocumentSegment,
        schema_ir: dict[str, Any],
        scope: AgentScope,
    ) -> ExtractionResult | ExtractionError:
        """
        从单个 segment 提取 FactDraftSpec 列表。

        完整时序：
        1. Defensive check：
           - instructor / litellm 已安装（L4C3a-07）
           - segment.raw_text 非空
           - schema_ir 可用

        2. 截断 segment.raw_text 到 config.max_text_chars

        3. 构造 Instructor response model:
           - 动态创建 Literal[...] 约束，限定 entity_type 和 pred_id 为 schema 允许值
           - 注入 schema 摘要到 system prompt

        4. 调用 LLM:
           response = client.chat.completions.create(
               model=config.model,
               response_model=SegmentExtractionResponse,
               messages=[system_prompt, user_prompt],
               max_retries=config.max_retries,
               temperature=config.temperature,
           )

        5. 对每个 LLMFactProposal 执行 validation pipeline:
           a. Schema validation（entity_type / pred_id / field typing）
           b. Scope validation（AgentScopeGuard rules）
           c. 从 segment 注入 ExtractionProvenance
           d. 构造 FactDraftSpec（触发 __post_init__ 校验）
           e. 任一失败 → 记录 ExtractionRejection，跳过

        6. 返回 ExtractionResult(valid_specs, rejections, ...)

        失败路径（不抛异常）：
        - 依赖缺失 → ExtractionError(kind="dependency_missing")
        - LLM 超时 → ExtractionError(kind="llm_timeout")
        - Instructor retry 耗尽 → ExtractionError(kind="instructor_retry_exhausted")
        - 其他 LLM 错误 → ExtractionError(kind="llm_unavailable")
        """
        ...
```

### 4.3 Prompt 模板

```python
SYSTEM_PROMPT = """You are a knowledge extraction assistant.
Your task is to extract structured facts from a text segment,
using ONLY the entity types and predicates defined in the provided schema.

Rules:
1. Only propose facts that can be expressed with the given schema.
2. Do not invent new entity types or predicates.
3. Only extract facts directly supported by the text.
4. If no valid facts can be extracted, return an empty proposals list.
5. Do not generate provenance fields (doc_id, segment_id, offsets) — those are injected by the system.
6. Assign a confidence score (0.0-1.0) based on how directly the text supports the fact.

Schema:
{schema_summary}
"""

USER_PROMPT_TEMPLATE = """Extract facts from the following text segment.

Document: {doc_name}
Section: {section_label}
Page: {page_number}
Pattern type: {pattern_type}
Structural clarity: {structural_clarity:.2f}

Text:
\"\"\"
{raw_text}
\"\"\"

Return a SegmentExtractionResponse with zero or more LLMFactProposal entries.
"""
```

**schema_summary 构造**：
- 列出每个 entity_type + identity_fields
- 列出每个 pred_id + arg_specs
- 限制在 ~2000 tokens 内（大 schema 需要筛选，4C3-a 暂不优化）

### 4.4 Validation Pipeline

```python
def validate_proposal(
    proposal: LLMFactProposal,
    proposal_index: int,
    *,
    segment: DocumentSegment,
    schema_ir: dict[str, Any],
    scope: AgentScope,
) -> tuple[FactDraftSpec | None, ExtractionRejection | None]:
    """
    对单条 proposal 执行完整验证。返回 (spec, None) 或 (None, rejection)。
    segment 用于在最后一步调用 _build_provenance_from_segment 注入 provenance。
    """
    # 1. Schema: entity_type 存在
    if not _schema_has_entity_type(schema_ir, proposal.entity_type):
        return None, ExtractionRejection(
            reason="schema_entity_type_unknown",
            detail=f"entity_type '{proposal.entity_type}' not in schema",
            proposal_index=proposal_index,
        )

    # 2. Schema: pred_id 存在
    if not _schema_has_pred_id(schema_ir, proposal.pred_id):
        return None, ExtractionRejection(
            reason="schema_pred_id_unknown",
            detail=f"pred_id '{proposal.pred_id}' not in schema",
            proposal_index=proposal_index,
        )

    # 3. Schema: field_values 类型匹配
    type_error = _validate_field_types(schema_ir, proposal.pred_id, proposal.field_values)
    if type_error is not None:
        return None, ExtractionRejection(
            reason="schema_field_type_mismatch",
            detail=type_error,
            proposal_index=proposal_index,
        )

    # 4. Scope: entity_type
    if scope.allowed_entity_types is not None and proposal.entity_type not in scope.allowed_entity_types:
        return None, ExtractionRejection(
            reason="scope_entity_type_denied",
            detail=f"entity_type '{proposal.entity_type}' not in scope whitelist",
            proposal_index=proposal_index,
        )

    # 5. Scope: pred_id
    if scope.allowed_pred_ids is not None and proposal.pred_id not in scope.allowed_pred_ids:
        return None, ExtractionRejection(
            reason="scope_pred_id_denied",
            detail=f"pred_id '{proposal.pred_id}' not in scope whitelist",
            proposal_index=proposal_index,
        )

    # 6. Scope: confidence
    if proposal.confidence is not None and proposal.confidence < scope.min_confidence:
        return None, ExtractionRejection(
            reason="scope_min_confidence",
            detail=f"confidence {proposal.confidence} < min {scope.min_confidence}",
            proposal_index=proposal_index,
        )

    # (max_batch_size 检查在 ExtractionAgent.extract_from_segment 中完成，
    #  在所有 proposals 通过 validate_proposal 之后，按 scope.max_batch_size 截断，
    #  超出部分记录为 scope_max_batch_size rejection)

    # 7. 构造 FactDraftSpec（注入 provenance）
    try:
        spec = FactDraftSpec(
            entity_type=proposal.entity_type,
            entity_identity=proposal.entity_identity,
            pred_id=proposal.pred_id,
            field_values=proposal.field_values,
            confidence=proposal.confidence,
            note=proposal.llm_note,
            extraction_provenance=_build_provenance_from_segment(segment),
        )
        return spec, None
    except AgentContractError as exc:
        return None, ExtractionRejection(
            reason="spec_construction_failure",
            detail=str(exc),
            proposal_index=proposal_index,
        )
```

---

## 5. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4C3-a: LLM Extraction ──

    def extract_from_segment(
        self,
        *,
        segment: DocumentSegment,
        config: ExtractionConfig | None = None,
    ) -> ExtractionResult | ExtractionError:
        """
        对单个 segment 执行 LLM extraction，返回验证后的 FactDraftSpec 列表。

        前置：
        - Orchestrator 构造时 extraction_agent 已注入（可选，None 时方法不可用）
        - session.scope 必须已设置

        Schema source 解析（L4C3a-17 冻结）：
        1. 优先：session.bootstrap_spec.open_dto["schema_ir"]（如果存在）
        2. Fallback：通过 runtime API 获取原始 schema_ir
           - 使用 runtime_api.get_schema(session_id)，解析 result.schema_ir
           - 不使用 kg_read_tools.get_schema_summary（后者返回精简摘要，无 schema_ir）
        3. 都不可用 → ExtractionError(kind="config_invalid", msg="no schema_ir available")

        委托：
        - extraction_agent.extract_from_segment(
              segment=segment,
              schema_ir=<resolved schema_ir>,
              scope=session.scope,
          )

        注意：
        - 不创建 bundle（L4C3a-02）
        - 不 checkpoint（纯函数式调用，无状态变更）
        - 失败不抛异常，返回 ExtractionError
        """
        ...

    def extract_and_create_bundle(
        self,
        *,
        segment: DocumentSegment,
        source_document_name: str,
        config: ExtractionConfig | None = None,
    ) -> tuple[ExtractionResult | ExtractionError, DraftBundle | None]:
        """
        便利方法：extract + create_document_bundle。

        时序：
        1. result = extract_from_segment(segment, config)
        2. 如果是 ExtractionError → 返回 (error, None)
        3. 如果 result.valid_specs 为空 → 返回 (result, None)
        4. bundle = create_document_bundle(
               source_document_id=segment.doc_id,
               source_document_name=source_document_name,
               facts=result.valid_specs,
           )
           → 自动 checkpoint（Layer 4C2 行为）
        5. 返回 (result, bundle)

        注意：这是便利方法；调用方也可以分两步走。
        """
        ...
```

### 5.1 为什么 extract_from_segment 不 checkpoint

纯函数调用，没有改 session/draft/bundle 任何状态。只有在 `extract_and_create_bundle` 调用 create_document_bundle 时才会 checkpoint（由 Layer 4C2 负责）。

### 5.2 为什么 config 是每次调用传而不是构造时固定

- 不同 segment 可能需要不同 model（cost/quality trade-off）
- 测试时需要快速切换
- 默认值通过 `orchestrator._default_extraction_config` 提供

---

## 6. Tool Registry 扩展

Layer 4C2 注册了 39 个 tool。Layer 4C3-a 追加：

```python
"extract_from_segment":         → orchestrator.extract_from_segment
"extract_and_create_bundle":    → orchestrator.extract_and_create_bundle
```

Layer 4C3-a 总计 41 个 tool（39 Layer 4C2 + 2 Layer 4C3-a）。

---

## 7. 实现顺序

```
Step 1: 数据模型
        → ExtractionConfig / LLMFactProposal / SegmentExtractionResponse
        → ExtractionRejection / ExtractionResult / ExtractionError
        → 纯 dataclass + Pydantic model
        → 单测

Step 2: Validation Pipeline
        → _schema_has_entity_type / _schema_has_pred_id
        → _validate_field_types
        → validate_proposal 完整流程
        → 单测：每种 rejection reason 至少一个 case

Step 3: Prompt 构造
        → schema_summary 生成
        → system/user prompt 模板
        → 单测：schema 摘要长度控制

Step 4: ExtractionAgent
        → LLM 调用（依赖感知注册，类似 4C1 parser）
        → Instructor + LiteLLM 集成
        → 失败路径（各种 ExtractionError）
        → mock LLM client 单测
        → 真实 LLM 集成测试（可选，需要 API key）

Step 5: Orchestrator 扩展
        → extract_from_segment / extract_and_create_bundle
        → 集成测试：segment → extract → create_bundle → review → commit

Step 6: Tool Registry 扩展
        → 41 tool 全量注册验证
```

---

## 8. 目录结构增量

```
src/factpy_kernel/agent/
  ├── extraction/                    # (新建) LLM extraction 子包
  │   ├── __init__.py
  │   ├── models.py                  # ExtractionConfig / Result / Error / Rejection
  │   ├── llm.py                     # LLMFactProposal / SegmentExtractionResponse
  │   ├── validation.py              # validate_proposal + helpers
  │   ├── prompts.py                 # SYSTEM_PROMPT / schema_summary 生成
  │   └── extractor.py               # ExtractionAgent 主类
  ├── orchestrator.py                # (扩展) +extract_from_segment +extract_and_create_bundle
  ├── framework.py                   # (扩展) tool registry 41 tools
  └── __init__.py                    # (扩展) export

src/factpy_kernel/tests/
  ├── test_agent_l4c3a_models.py          # (新建) 数据模型
  ├── test_agent_l4c3a_validation.py      # (新建) validation pipeline
  ├── test_agent_l4c3a_prompts.py         # (新建) prompt 构造
  ├── test_agent_l4c3a_extractor.py       # (新建) ExtractionAgent + mock LLM
  └── test_agent_l4c3a_workflow.py        # (新建) 端到端：extract → bundle → review → commit
```

### 8.1 pyproject.toml 变更

```toml
[project.optional-dependencies]
extraction = [
    "instructor>=1.6",
    "litellm>=1.50",
]
```

依赖感知注册（L4C3a-07 + L4C3a-20 冻结）：

**依赖检查单一来源**（L4C3a-20）：ExtractionAgent 内部做本地 import 检查，**不**扩展 `framework.probe_optional_dependencies()`。理由：
- `framework.OptionalDependencyStatus` 是 tool-registry 级别的 probe（pydantic_ai / burr / langfuse），用于整个 agent skeleton
- Extraction 是 4C3-a 新引入的子系统，依赖检查应局部化到 `extraction/` 模块
- 避免 framework.py 每次新增 Layer 都要扩展全局 probe
- 调用方可以通过 `try: import instructor, litellm` 自行预检

**行为**：
- `ExtractionAgent.__init__` 不 raise（延迟检查）
- `extract_from_segment` 第一步做 local import：
  ```python
  try:
      import instructor  # noqa: F401
      import litellm     # noqa: F401
  except ImportError as exc:
      return ExtractionError(
          segment_id=segment.segment_id,
          error_kind="dependency_missing",
          error_message=f"extraction requires instructor and litellm: {exc}",
      )
  ```
- Orchestrator 构造时 `extraction_agent: ExtractionAgent | None = None`
  - None 时 `extract_from_segment` 返回 `ExtractionError(dependency_missing)`
  - 非 None 时委托给 agent，由 agent 内部做 import 检查

---

## 9. 验收标准

1. **L4C3a-01**：ExtractionAgent 只接受单个 DocumentSegment；不存在 list[DocumentSegment] API
2. **L4C3a-02**：extract_from_segment 不调用 DraftManager / BundleManager / create_document_bundle
3. **L4C3a-03**：LLM 提议 schema 外 entity_type 或 pred_id → 被 validation 拒绝，不出现在 valid_specs
4. **L4C3a-04**：LLMFactProposal 不含 provenance 字段；FactDraftSpec.extraction_provenance 所有字段与输入 segment 一致
5. **L4C3a-05**：每条 valid_spec 通过 schema + scope + FactDraftSpec.__post_init__ 三层校验
6. **L4C3a-06**：两次独立调用不共享状态；不会基于前一次结果做去重
7. **Rejection 追踪**：rejected proposal 在 ExtractionResult.rejections 中有详细 reason + detail
8. **失败不抛异常**：LLM 不可达 / 超时 / 依赖缺失 → 返回 ExtractionError
9. **extract_and_create_bundle**：空 valid_specs 时不创建 bundle；非空时正确委托 create_document_bundle
10. **依赖感知注册**：未安装 instructor/litellm 时 extract_from_segment 返回 ExtractionError(dependency_missing)
11. **Tool 数量**：41 个
12. **单测 + mock LLM 集成测试**覆盖

---

## 10. 已知约束

1. **L4C3a-07 依赖感知**：instructor 和 litellm 作为 optional dependency。未安装时 extract_* 返回 ExtractionError(dependency_missing)，不抛异常。
2. **大 schema 的 prompt 爆炸**：schema_summary 在 prompt 中展开，大 schema（>100 predicates）会超过 context window。v1 不做 schema 筛选，由调用方负责控制 schema 规模或拆分 session。
3. **LLM 成本不在本层控制**：调用成本由 LiteLLM 层处理；ExtractionAgent 不做 token counting 或 budget limit。4C3-b 批量时再引入。
4. **Provenance.raw_text 与 LLM 输入分离**（L4C3a-19）：`ExtractionProvenance.raw_text` 永远是完整 segment.raw_text。`config.max_text_chars` 只截断送给 LLM 的 prompt text，不影响 provenance。审计时以 provenance.raw_text 为准。
5. **LLM 输出非确定性**：即使 temperature=0，不同 model version / provider 可能产出不同提议。这与 Layer 4C1 的"确定性 staging"形成对比——extraction 层不保证确定性，这是 LLM 的本质约束。
6. **Instructor response model 动态构造**：需要在运行时基于 schema_ir 构造 Literal[...]；v1 每次调用都重新构造，后续可缓存。
7. **不测试真实 LLM API**：单测全部用 mock LLM client。真实 API 集成测试是可选的，需要 API key 和环境配置。
8. **字段类型匹配是 best-effort**：_validate_field_types 检查类型大类（int/str/float/bool），不检查值约束（如 enum、range）。4C3-b 可考虑引入更严格的 Pydantic runtime validation。

---

## 11. Outcome / Deviations

### Outcome

- 新建 `src/factpy_kernel/agent/extraction/` 子包，落地：
  - `ExtractionConfig`
  - `ExtractionRejection` / `ExtractionResult` / `ExtractionError`
  - `build_response_model(schema_ir)`
  - prompt/schema summary helpers
  - `validate_proposal(...)`
  - `ExtractionAgent.extract_from_segment(...)`
- `ReadReviewOrchestrator` 新增：
  - `extract_from_segment(...)`
  - `extract_and_create_bundle(...)`
- `build_layer3a_tool_registry()` 从 39 tools 扩到 41
- 新增 extraction 模块文档：`src/factpy_kernel/agent/extraction/docs/README.md`
- 全量验证通过：`python -m unittest discover -s src/factpy_kernel/tests` → `884 tests`, `1 skipped`

### Deviations

1. **依赖感知短路在 injected mock client 下不会触发**
   - blueprint 默认表述为 `extract_from_segment()` 第一步总做 local import 检查。
   - 实现中只有在 `llm_client is None` 时才构造默认 Instructor/LiteLLM client 并触发依赖检查；显式注入 mock/fake client 时允许无依赖运行。
   - 理由：保持单测与本地开发环境不依赖真实 LLM 栈，同时不改变 production 默认路径。

2. **Prompt 中的 document label 使用 `segment.doc_id`**
   - blueprint 的 user prompt 示例写的是 `doc_name`。
   - 当前 `extract_from_segment()` 只接收 `DocumentSegment`，而 `DocumentSegment` 不携带 `doc_name`，因此实现中 prompt 使用 `segment.doc_id` 作为 document label。
   - `extract_and_create_bundle()` 仍要求调用方提供 `source_document_name`，所以 4C2 provenance/commit 路径不受影响。
