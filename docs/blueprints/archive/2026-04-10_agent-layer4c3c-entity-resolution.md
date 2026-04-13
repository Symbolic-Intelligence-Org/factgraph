# Blueprint: Agent Layer 4C3-c — Single-Document Entity Resolution

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on:
  - Layer 4C1 确定性文档 staging (archived)
  - Layer 4C2 DraftBundle review/approval (archived)
  - Layer 4C3-a single-segment LLM extraction (archived)
  - Layer 4C3-b batch extraction orchestration (archived)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/resolution.py` (新建)
  - `src/factpy_kernel/agent/documents/models.py` (扩展: ExtractionProvenance 加 merged_from)
  - `src/factpy_kernel/agent/extraction/batch.py` (只读依赖)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：在单文档 batch extraction 结果之上，对 `FactDraftSpec[]` 做 dedupe + merge，把"同一实体同一事实"的多 segment 来源合并为单条，同时**完整保留所有来源的 segment-level provenance**。

**核心问题**（来自 4C3-b 已知约束 #4）：
> 同一 entity 在多个 segments 中出现会产生多条 FactDraftSpec。送 bundle 后 kernel 的 ingest_key 幂等机制会把 identical (pred_id, e_ref, rest_terms, source) 折叠。但 `source` 中包含 `segment_id`，所以不同 segment 来源的"同一事实"会产生不同 assertion。

4C3-c 的任务是在 **agent 层送入 bundle 之前** 完成这一步合并，确保 bundle 内每条 spec 代表一个"去重后的事实"，但 provenance 仍能回溯到全部来源 segment。

**冻结决策**（本轮锁定，正文围绕这 4 条展开）：

| # | 决策 | 理由 |
|---|------|------|
| L4C3c-01 | 只做单文档 / 单 bundle resolution | 跨文档 entity linking 需要全局状态、外部 KB 对齐，是另一条产品线 |
| L4C3c-02 | 只对 FactDraftSpec[] 做 dedupe / merge，不改 4C1/4C3-a 原始产物 | Resolution 是 agent 层的纯函数式 pipeline 步骤；不回写 staging 结果、不改 LLM proposal |
| L4C3c-03 | Provenance 必须保留"多 segment 来源集合"，不能因为 merge 丢证据 | 审计链是核心约束；merge 不能降级审计 |
| L4C3c-04 | v1 不做跨文档 entity linking，不做外部 KB 对齐 | 明确排除 global KB 对齐 / Wikidata / 外部 entity resolver |

**明确排除**：
- 跨文档 entity resolution（同一实体出现在不同文档）
- 外部 KB 对齐（Wikidata / 企业主数据 / 图数据库）
- 引用消解（"上述条款" / "前一段提到的人" 这类 anaphora resolution）——需要 LLM 二次调用
- Fuzzy entity matching（"李四" vs "Li Si" 的跨语言匹配）
- 语义级别的 field_values 合并（"年龄 25" vs "出生于 1999 年"）
- Resolution 结果写入 ledger / audit trail（纯 in-memory pipeline 步骤）
- LLM 辅助的合并决策（v1 纯 deterministic）

---

## 1. 4 条冻结决策的展开

### 1.1 L4C3c-01：只做单文档 / 单 bundle resolution

**范围**：
- 输入：`BatchExtractionResult.aggregated_specs`（来自 4C3-b，保证同一 `doc_id`）
- 输出：`ResolutionResult`，含 dedupe 后的 `list[FactDraftSpec]` + 统计信息
- 调用时机：在 `create_document_bundle` 之前，对 aggregated_specs 先 resolve 再送 bundle

**不处理**：
- 跨文档聚合（多个 bundle 的 resolution）
- 全局 entity registry
- Session-level 跨 bundle 状态

**为什么限定单文档**：
- 跨文档需要持久化的 entity index，涉及新的数据结构和生命周期
- 外部 KB 对齐是独立的产品决策（选 Wikidata / 企业 MDM / 自建）
- 单文档 dedupe 已经解决 4C3-b 的最大痛点（同文档重复）

### 1.2 L4C3c-02：只改 FactDraftSpec[]，不回写上游

**纯函数式 pipeline**：

```
BatchExtractionResult.aggregated_specs    (input, 只读)
          │
          ▼
EntityResolver.resolve_batch(specs, config)
          │
          ▼
ResolutionResult(
    resolved_specs=list[FactDraftSpec],       # dedupe 后的结果
    merge_events=list[MergeEvent],            # merge 详情
    stats=ResolutionStats,
)
          │
          ▼
create_document_bundle(facts=resolved_specs)  (下游)
```

**注意**：resolver 不依赖 schema_ir 或 scope——dedupe 是纯数据结构操作，不涉及 schema validation（那是 4C3-a 的事）或 scope 权限检查（已在 4C3-a validation pipeline 中完成）。

**不做**：
- 不改 4C1 的 DocumentSegment（staging 产出不可变）
- 不改 4C3-a 的 ExtractionResult（per-segment 提取结果不可变）
- 不改 4C3-b 的 BatchExtractionResult（batch 结果不可变）
- 不调用 DraftManager / BundleManager
- 不触发 checkpoint

### 1.3 L4C3c-03：Provenance 必须保留所有来源

**核心约束**：merge 后的 FactDraftSpec 必须能回溯到每一个原始 segment。

**数据结构扩展**：

当前 `ExtractionProvenance` 是单 segment 结构：

```python
@dataclass(frozen=True)
class ExtractionProvenance:
    source_document_id: str
    segment_id: str
    char_offset_start: int
    char_offset_end: int
    raw_text: str
    page_number: int | None = None
    extraction_method: Literal["manual", "llm_refined"] = "manual"
```

4C3-c 扩展追加 `merged_from` 字段（L4C3c-05 冻结）：

```python
@dataclass(frozen=True)
class ExtractionProvenance:
    # ... existing fields ...
    merged_from: tuple["ExtractionProvenance", ...] = ()
    # 语义：
    # - 空 tuple（默认）: 单来源 provenance，自身即 canonical
    # - 非空:            merged provenance，self 是 "primary"（保留用于
    #                    kernel write path 的 source/source_loc 注入），
    #                    merged_from 包含所有其他贡献来源
    # - primary 选择规则: merge 时按 (segment_index, char_offset_start) 排序取最小值
    #                    ——即文档中最早出现的那一条
```

**为什么用 primary + merged_from 而不是纯 tuple**：
- Layer 3A 的 write path (`write.py:draft_to_write_request`) 需要**单个** `source` / `source_loc` 值写入 meta
- 保留 primary 作为 kernel-facing 字段，merged_from 作为 agent-side 审计扩展
- 对 Layer 3A 零侵入（write path 只读 primary 字段）

**前向兼容性**：
- 默认值 `()` 保证现有代码构造 `ExtractionProvenance(...)` 不受影响
- 4C1 / 4C3-a / 4C3-b 产出的 provenance `merged_from == ()`
- 4C3-c 产出的 merged provenance `merged_from != ()`

### 1.4 L4C3c-04：不做跨文档 / 外部 KB

**硬边界**：
- Resolver 的输入 specs 必须来自同一 doc_id（前置校验）
- 不调用任何外部服务 / 数据库 / KB API
- 不做 embedding similarity / vector search
- 不做 LLM 辅助的合并判断（v1 纯 deterministic 规则）

---

## 2. Dedupe 策略

### 2.1 Entity Key 构造

**L4C3c-06 冻结**：entity key 是 `(entity_type, canonical_identity)` 的结构化元组。

```python
def _compute_entity_key(spec: FactDraftSpec) -> tuple[str, tuple[tuple[str, Any], ...]]:
    """
    entity key 由 (entity_type, sorted identity pairs) 组成。
    identity 按 key 排序，保证 {"a": 1, "b": 2} 和 {"b": 2, "a": 1} 等价。
    """
    identity_items = tuple(sorted(spec.entity_identity.items(), key=lambda x: x[0]))
    return (spec.entity_type, identity_items)
```

### 2.2 Fact Key 构造

**L4C3c-07 冻结**：fact key 是 `(entity_key, pred_id, field_values_tuple)` 的元组，`field_values` **保留原始顺序**。

```python
def _compute_fact_key(spec: FactDraftSpec) -> tuple[Any, str, tuple[tuple[str, Any], ...]]:
    """
    fact key 由 (entity_key, pred_id, field_values in original order) 组成。

    field_values 保留原始顺序（L4C3c-16 冻结），不按 tag 排序。

    原因（详见 L4C3c-16）：
    - 4C3-a validation 使用 zip(field_values, arg_specs, strict=True) 逐位置对齐 schema 参数
      (validation.py:172, :195)
    - 对有重复 type_domain 的 predicate（如 `related_to(entity_ref, entity_ref)`），
      field 顺序本身就是语义的一部分
    - 按 tag 排序会把语义不同的 spec 误判为相同
    """
    entity_key = _compute_entity_key(spec)
    # 保持原始 tuple 顺序；不排序
    field_items = tuple((tag, value) for tag, value in spec.field_values)
    return (entity_key, spec.pred_id, field_items)
```

### 2.3 v1 Dedupe 规则

**L4C3c-08 冻结**：两条 FactDraftSpec 被认为"相同"当且仅当它们的 `fact_key` 严格相等（含 field_values 的原始顺序相等）。

**Entity identity 仍然顺序无关**：
- `entity_identity` 是 dict（键集合无序），entity_key 通过 `sorted(...)` 规范化
- 这与 field_values 不同——identity 的键在 schema 中是"identity_fields 集合"而非"按位置对齐的参数"

**不做**（v1 明确排除）：
- `entity_identity` 值的 fuzzy matching（大小写 / 空格 / unicode 规范化）
- `field_values` 值的 semantic matching（"高" vs "0.9"）
- `pred_id` 的别名识别
- Entity-level merge（只有 pred_id 不同的同一 entity 的 facts 合并到一起）
- 基于 schema arg_specs 的 canonicalization（未来可选增强）

**为什么先做严格匹配**：
- 消除"同一 LLM 提议在多 segment 重复出现"这个最常见场景
- fuzzy matching 的规则需要真实数据才能确定
- 严格匹配是 fuzzy matching 的正确子集，未来扩展不会破坏现有行为

### 2.4 Merge 行为

当两条 specs 被判定为相同时：

```python
def _merge_specs(primary: FactDraftSpec, other: FactDraftSpec) -> FactDraftSpec:
    """
    将 other 合并到 primary。primary 是 canonical（first seen in input order）。

    provenance 合并规则（L4C3c-17 / L4C3c-18）：
    - primary.merged_from 保持原顺序
    - other 整体追加（other 自身 + other.merged_from 扁平展开）
    - 按 segment_id 去重（已在 merged_from 中的 segment 不重复添加）
    - 最终 all_sources() 会递归展开所有贡献 segment，保证完整回溯

    field_values: 保持 primary 的（两者按 fact_key 相等，所以一致）
    confidence:   取两者中 max（保守上限）
    note:         保持 primary 的
    """
    primary_prov = primary.extraction_provenance
    other_prov = other.extraction_provenance

    # 构造新的 merged_from：
    # 1. 保留 primary.merged_from（已经包含 primary 之前合并的来源）
    # 2. 追加 other 整体（other 自己 + other.merged_from 扁平展开）
    # 3. 按 segment_id 去重（primary 自身 segment + primary.merged_from 已覆盖的 segment 不再追加）
    existing_segment_ids = {primary_prov.segment_id} | {
        p.segment_id for p in primary_prov.merged_from
    }

    additions: list[ExtractionProvenance] = []
    for candidate in (other_prov, *other_prov.merged_from):
        if candidate.segment_id in existing_segment_ids:
            continue
        existing_segment_ids.add(candidate.segment_id)
        additions.append(candidate)

    new_merged_from = (*primary_prov.merged_from, *additions)
    new_provenance = replace(primary_prov, merged_from=new_merged_from)

    new_confidence: float | None
    if primary.confidence is None:
        new_confidence = other.confidence
    elif other.confidence is None:
        new_confidence = primary.confidence
    else:
        new_confidence = max(primary.confidence, other.confidence)

    return replace(
        primary,
        extraction_provenance=new_provenance,
        confidence=new_confidence,
    )
```

**幂等性保证**：
- 同一 segment_id 永远不会出现在 merged_from 两次
- 对已 resolved 的 specs 再跑 resolution，segment_id 集合不变
- `resolve_batch(resolve_batch(X).resolved_specs).stats.merge_count == 0`

**primary 的选择规则**（L4C3c-09 冻结）：
- 第一次出现的 spec 成为 primary
- "第一次" 按 `aggregated_specs` 的输入顺序判定（已经是 segment order + within-segment proposal order）
- 后续相同 fact_key 的 specs 合并到 primary
- 这保证 primary 来自文档中最早的 segment

### 2.5 Confidence 合并策略

**L4C3c-10 冻结**：合并后 confidence 取 max（两者都非 None 时）。

**备选方案**（不采用）：
- 取 min：过于保守，失去高置信 signal
- 取平均：两个来源不意味着可信度翻倍
- 加权：缺乏权重的合理依据
- 贝叶斯组合：需要假设独立性，实际未必成立

Max 是最简单、语义清晰的选择：至少有一个 segment 以 X 的置信度支持这个 fact。

---

## 3. 数据模型

### 3.1 ExtractionProvenance 扩展

见 §1.3。追加 `merged_from: tuple[ExtractionProvenance, ...] = ()`。

**辅助方法**（L4C3c-17 冻结递归展开语义）：

```python
@dataclass(frozen=True)
class ExtractionProvenance:
    # ... existing fields + merged_from ...

    def all_sources(self) -> tuple["ExtractionProvenance", ...]:
        """
        递归展开所有贡献来源的扁平 tuple（含 self）。
        对已合并过的 provenance（内部 merged_from 含自身 merged 的 provenance）
        会递归 flatten。

        去重规则：按 segment_id 去重；同一 segment_id 只保留第一次出现的 provenance。
        顺序：self → merged_from[0] 的扁平展开 → merged_from[1] 的扁平展开 → ...

        实现（伪代码）：
          result = []
          seen = set()
          def _walk(prov):
              if prov.segment_id in seen: return
              seen.add(prov.segment_id)
              result.append(prov)
              for sub in prov.merged_from:
                  _walk(sub)
          _walk(self)
          return tuple(result)
        """
        ...

    def source_segment_ids(self) -> tuple[str, ...]:
        """返回所有贡献 segment 的 ID（递归 + 去重，用于审计/展示）。"""
        return tuple(prov.segment_id for prov in self.all_sources())

    def is_merged(self) -> bool:
        """是否是 merge 结果。"""
        return len(self.merged_from) > 0
```

**L4C3c-18 冻结**：EntityResolver 的输入边界

`resolve_batch(specs)` 的输入 specs **不要求** merged_from 为空——即支持对已 resolved 的 specs 再次跑 resolution（幂等）。

理由：
- 递归 `all_sources()` 保证 segment_id 集合完整
- merge 逻辑中已经正确处理 `*other_prov.merged_from`（现有 _merge_specs 代码）
- 幂等是好性质：多次 resolve 与单次 resolve 产出相同 segment_id 集合
- 不限制输入边界，调用方更灵活（例如"先 resolve doc A，再与 doc B 合并 resolve"——虽然跨文档在 L4C3c-01 范围外，但数据结构支持）

**幂等性测试**：`resolve_batch(specs)` 与 `resolve_batch(resolve_batch(specs).resolved_specs)` 产出的 `source_segment_ids()` 必须相等（忽略顺序/包含所有原始 segment）。

### 3.2 MergeEvent

```python
@dataclass(frozen=True)
class MergeEvent:
    """
    单次 merge 事件的审计记录。

    用于展示 "哪两条被合并了、为什么"，不影响业务逻辑。
    """
    fact_key_repr: str                       # fact key 的 string 表示（调试用）
    primary_segment_id: str                  # primary spec 来源
    merged_segment_id: str                   # 被合并的 segment 来源
    entity_type: str
    pred_id: str
```

### 3.3 ResolutionStats

```python
@dataclass(frozen=True)
class ResolutionStats:
    """Resolution 统计。"""
    input_spec_count: int                    # 输入 specs 数量
    output_spec_count: int                   # dedupe 后 specs 数量
    merge_count: int                         # 发生 merge 的次数
    unique_entity_count: int                 # 去重后的 entity 数
    unique_fact_count: int                   # 去重后的 fact 数（= output_spec_count）
    resolution_duration_ms: int
```

### 3.4 ResolutionResult

```python
@dataclass(frozen=True)
class ResolutionResult:
    """
    单文档 resolution 的结构化返回。
    """
    doc_id: str
    resolved_specs: tuple[FactDraftSpec, ...]
    merge_events: tuple[MergeEvent, ...]
    stats: ResolutionStats

    def has_merges(self) -> bool:
        return self.stats.merge_count > 0
```

### 3.5 ResolutionError

```python
@dataclass(frozen=True)
class ResolutionError:
    """
    Resolution 前置失败（doc_id 不一致 / specs 为空 / config 非法）。
    不用于单条 spec 的合并失败（那不存在——合并是 best-effort deterministic）。
    """
    doc_id: str | None
    error_kind: Literal[
        "empty_specs",
        "doc_id_mismatch",
        "config_invalid",
    ]
    error_message: str
```

**注意**：没有 `ResolutionError(kind="merge_failure")`。Deterministic merge 不会在 runtime 失败——任何异常都是 bug，应该抛出而不是降级。

### 3.6 ResolutionConfig

```python
@dataclass(frozen=True)
class ResolutionConfig:
    """Resolution 配置。v1 只有最小配置项。"""
    enable_dedupe: bool = True               # 可关闭（便于 A/B 对比）
    max_input_specs: int = 10000             # 防止意外大输入
    # v1 不做 fuzzy matching 配置、confidence 合并策略配置等
```

---

## 4. EntityResolver

### 4.1 职责

对单文档的 `list[FactDraftSpec]` 执行 dedupe + merge，返回 `ResolutionResult`。

**不做**：
- 不持有 AgentSession / state
- 不 checkpoint
- 不调用 RuntimeAPI
- 不调用 LLM

### 4.2 接口

```python
class EntityResolver:
    """
    单文档 entity/fact resolution（L4C3c-01）。

    纯函数式：输入 FactDraftSpec[] + config，输出 ResolutionResult。
    """

    def __init__(self, *, config: ResolutionConfig | None = None) -> None: ...

    def resolve_batch(
        self,
        specs: list[FactDraftSpec],
        *,
        config: ResolutionConfig | None = None,
    ) -> ResolutionResult | ResolutionError:
        """
        对 specs 做 dedupe + merge。

        步骤：
        1. 前置校验（返回 ResolutionError，永不 raise）：
           - specs 非空
           - 所有 specs 的 provenance.source_document_id 一致
           - len(specs) <= config.max_input_specs

        2. 如果 config.enable_dedupe is False：
           直接返回 ResolutionResult(resolved_specs=tuple(specs), merge_events=(), ...)

        3. 遍历 specs（保持输入顺序）：
           - 计算 fact_key
           - 如果 fact_key 已存在于 key_to_spec map：
             - 合并：merged = _merge_specs(key_to_spec[fact_key], current_spec)
             - 更新 key_to_spec[fact_key] = merged
             - 记录 MergeEvent
           - 否则：
             - key_to_spec[fact_key] = current_spec

        4. 构造 ResolutionStats

        5. 返回 ResolutionResult(
               doc_id=first_spec.extraction_provenance.source_document_id,
               resolved_specs=tuple(key_to_spec.values()),  # 保持首次出现顺序
               merge_events=tuple(merge_events),
               stats=stats,
           )

        注意：
        - resolved_specs 的顺序 = 每个 fact_key 第一次出现时的顺序
        - 这保证了 primary 仍然是"文档中最早出现的那一条"
        """
        ...
```

### 4.3 顺序稳定性

Python 3.7+ 的 dict 保持插入顺序。key_to_spec map 的遍历顺序 = 每个 fact_key 首次插入的顺序 = 每个 primary 在输入中出现的位置。这保证了 resolved_specs 对同一输入的输出顺序是确定的。

---

## 5. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4C3-c: Entity Resolution ──

    def resolve_batch_extraction(
        self,
        batch_result: BatchExtractionResult,
        *,
        config: ResolutionConfig | None = None,
    ) -> ResolutionResult | ResolutionError:
        """
        对 BatchExtractionResult 的 aggregated_specs 执行 resolution。

        前置：
        - entity_resolver 已注入（None 时方法不可用）
        - batch_result.aggregated_specs 非空（否则返回 ResolutionError(empty_specs)）

        委托：
        - entity_resolver.resolve_batch(
              specs=list(batch_result.aggregated_specs),
              config=config,
          )

        不 checkpoint（纯函数式）。
        """
        ...

    def extract_resolve_and_create_document_bundle(
        self,
        *,
        segments: list[DocumentSegment],
        source_document_name: str,
        batch_config: BatchExtractionConfig | None = None,
        resolution_config: ResolutionConfig | None = None,
    ) -> tuple[
        BatchExtractionResult | BatchExtractionError,
        ResolutionResult | ResolutionError | None,
        DraftBundle | None,
    ]:
        """
        完整的一站式方法：batch extract → resolve → create bundle。

        时序：
        1. batch_result = extract_from_segments(segments, batch_config)
           - BatchExtractionError: 返回 (error, None, None)

        2. 如果 batch_result.aggregated_specs 为空:
           返回 (batch_result, None, None)

        3. resolution = resolve_batch_extraction(batch_result, config=resolution_config)
           - ResolutionError: 返回 (batch_result, error, None)

        4. bundle = create_document_bundle(
               source_document_id=resolution.doc_id,
               source_document_name=source_document_name,
               facts=list(resolution.resolved_specs),
           )
           → 自动 checkpoint (Layer 4C2)

        5. 返回 (batch_result, resolution, bundle)

        这是三层一站式：4C3-b → 4C3-c → 4C2。
        调用方也可以分步走，保留中间结果用于调试。
        """
        ...
```

### 5.1 与 `extract_and_create_document_bundle` 的关系

两者并存：

| 方法 | 是否 resolve | 用例 |
|------|-------------|------|
| `extract_and_create_document_bundle` | 不 resolve | 需要看原始 per-segment 提议（审计 / 调试） |
| `extract_resolve_and_create_document_bundle` | resolve | 生产路径，减少 bundle 中的重复 |

**默认推荐**：生产使用 resolve 版本。

---

## 6. Tool Registry 扩展

Layer 4C3-b 注册了 43 个 tool。Layer 4C3-c 追加：

```python
"resolve_batch_extraction":                        → orchestrator.resolve_batch_extraction
"extract_resolve_and_create_document_bundle":     → orchestrator.extract_resolve_and_create_document_bundle
```

Layer 4C3-c 总计 45 个 tool（43 Layer 4C3-b + 2 Layer 4C3-c）。

---

## 7. Provenance 到 Meta 的映射

### 7.1 Kernel write path 的行为

Layer 3A 的 `write.py:draft_to_write_request` 从 `draft.source` 和 `draft.source_loc` 读取值写入 assertion meta。这两个字段来自 Layer 4C2 的 bundle 创建时从 `extraction_provenance` 规范化的结果。

### 7.2 Merged provenance 的规范化规则

**L4C3c-11 冻结**：bundle 创建时，从 merged provenance 生成 `source` / `source_loc` 的规则：

```python
def _merged_provenance_to_draft_source(
    prov: ExtractionProvenance, doc_name: str,
) -> tuple[str, str]:
    if not prov.is_merged():
        # 单来源，走 Layer 4C2 原有规则
        return (
            f"doc:{doc_name}:seg:{prov.segment_id}",
            f"chars:{prov.char_offset_start}-{prov.char_offset_end}",
        )

    # Merged: primary 信息 + 来源数量
    all_segment_ids = prov.source_segment_ids()
    source = (
        f"doc:{doc_name}:seg:{prov.segment_id}"
        f":merged_from:{len(prov.merged_from)}"
    )
    source_loc = (
        f"chars:{prov.char_offset_start}-{prov.char_offset_end}"
        f":segments:{','.join(all_segment_ids)}"
    )
    return (source, source_loc)
```

**语义**：
- 单来源 assertion 的 meta.source 保持不变（L4C2 行为）
- Merged assertion 的 meta.source 包含"merged_from: N"标记 + 所有贡献 segment ID
- kernel 只把这两个字段作为字符串存储；不解析
- 审计场景下可以按 `:merged_from:` 子串搜索 merged facts

**ledger ingest_key 的影响**：
- ingest_key 包含 source 的一部分
- 两条 merged FactDraftSpec 会得到**不同的 source 字符串**（贡献 segments 不同）
- 所以 dedupe 后的 specs 在 ledger 层仍然是唯一的（由 agent 层保证而不是 kernel 幂等）

### 7.3 为什么不把 merged_from 展开为多条 assertion

**备选方案**（不采用）：在 commit 时对 merged spec 写入多条 assertion，每条对应一个贡献 segment。

**不采用的原因**：
- 违反 L4C3c-03 的语义（dedupe 的目的是减少 assertion 数量）
- ledger 会出现同一 fact 的多条 assertion，与 dedupe 矛盾
- 审计追溯通过 meta.source 中的 segment 列表实现，已经足够

---

## 8. 实现顺序

```
Step 1: ExtractionProvenance 扩展
        → 追加 merged_from 字段（默认 ()）
        → 追加 all_sources / source_segment_ids / is_merged 辅助方法
        → 更新 to_checkpoint / from_checkpoint 的序列化
        → 单测：默认值、merged 构造、checkpoint 往返

Step 2: Resolution 数据模型
        → MergeEvent / ResolutionStats / ResolutionResult / ResolutionError
        → ResolutionConfig
        → 纯 dataclass 单测

Step 3: Dedupe 辅助函数
        → _compute_entity_key / _compute_fact_key
        → _merge_specs
        → 单测：顺序无关、identity 排序、confidence max 等

Step 4: EntityResolver
        → 前置校验（3 种 ResolutionError）
        → 主 dedupe 循环
        → 统计聚合
        → 单测：
          - 无重复 → resolved_specs == input
          - 全重复 → 单条 spec with merged_from
          - 混合 → 正确分组
          - enable_dedupe=False → passthrough
          - doc_id_mismatch / empty_specs / oversize → ResolutionError

Step 5: Layer 4C2 BundleManager 适配
        → _provenance_to_draft_source 支持 merged provenance（L4C3c-11）
        → 单测：merged vs 单来源的 source/source_loc 生成

Step 6: Orchestrator 扩展
        → resolve_batch_extraction
        → extract_resolve_and_create_document_bundle
        → 集成测试：segments → batch → resolve → bundle → review → commit

Step 7: Tool Registry 扩展
        → 45 tool 全量注册验证
```

---

## 9. 目录结构增量

```
src/factpy_kernel/agent/
  ├── extraction/
  │   ├── resolution.py           # (新建) EntityResolver + 数据模型
  │   ├── models.py               # (扩展) export ResolutionResult/Error
  │   └── __init__.py             # (扩展) export new symbols
  ├── documents/
  │   ├── models.py               # (扩展) ExtractionProvenance +merged_from +辅助方法
  │   └── bundle.py               # (扩展) _provenance_to_draft_source 支持 merged
  ├── orchestrator.py             # (扩展) +resolve_batch_extraction +extract_resolve_and_create_document_bundle
  └── framework.py                # (扩展) tool registry 45 tools

src/factpy_kernel/tests/
  ├── test_agent_l4c3c_provenance.py       # (新建) ExtractionProvenance 扩展
  ├── test_agent_l4c3c_resolver.py         # (新建) EntityResolver
  ├── test_agent_l4c3c_merge_meta.py       # (新建) merged provenance → source/source_loc
  └── test_agent_l4c3c_workflow.py         # (新建) 端到端：extract → resolve → bundle → commit
```

---

## 10. 验收标准

1. **L4C3c-01 单文档约束**：specs 来自不同 doc_id → ResolutionError(doc_id_mismatch)；空 → empty_specs
2. **L4C3c-02 纯函数式**：resolve_batch_extraction 不改 input batch_result；不 checkpoint；不调 DraftManager
3. **L4C3c-03 provenance 完整保留**：merged FactDraftSpec 的 extraction_provenance.all_sources() 返回所有贡献 segment 的 provenance
4. **L4C3c-04 无跨文档**：不调用任何外部服务；Resolver 不持有全局状态
5. **严格 fact_key 匹配**（L4C3c-16）：
   - `entity_identity` 顺序无关（`{"a":1,"b":2}` 等价于 `{"b":2,"a":1}`）
   - `field_values` **保留原始顺序、位置敏感**，不按 tag 排序
   - 具体例子：`related_to([entity, alice], [entity, bob])` 与 `related_to([entity, bob], [entity, alice])` **不合并**，因为 4C3-a validation 按 schema arg_specs 位置对齐，两者是语义不同的 fact
5a. **幂等性**（L4C3c-18）：对已 resolved 的 specs 再次调用 resolve_batch，segment_id 集合不丢失；merge_count 降为 0
6. **Primary 选择**：merged spec 的 extraction_provenance 主字段来自输入中首次出现的 spec
7. **Confidence max**：两个非 None confidence merge 后取 max；一 None 一非 None 取非 None
8. **enable_dedupe=False**：passthrough，resolved_specs == tuple(input_specs)，merge_count == 0
9. **Meta 规范化**：merged provenance → meta.source 含 `:merged_from:N` 标记；源单来源 → 保持 L4C2 原格式
10. **前向兼容**：Layer 4C1/4C3-a/4C3-b 现有测试不受 ExtractionProvenance 扩展影响
11. **Tool 数量**：45 个
12. **端到端测试**：extract → resolve → bundle → commit 链路完整，committed assertion 的 meta 含完整 segment list

---

## 11. 已知约束

1. **v1 只做严格匹配**：`entity_identity`（顺序无关）和 `field_values`（原始顺序相等）必须字面一致。"李四" 和 "Li Si" 不会合并。留给 v2。
1a. **field_values 对位置敏感**（L4C3c-16）：`related_to([entity, alice], [entity, bob])` 和 `related_to([entity, bob], [entity, alice])` 不会被合并——因为 4C3-a validation 按位置对齐 schema 参数，两者是语义不同的 fact。
1b. **Resolution 是幂等的**（L4C3c-18）：对已 resolved 的 specs 再次调用 resolve_batch 不会丢失 segment_id；merge_count 会降为 0。
2. **Confidence max 可能过于乐观**：如果 LLM 对同一 fact 两次给出不同置信度（一高一低），max 会采用高的。v1 接受此 trade-off。
3. **Merged provenance 占空间**：一个被合并 N 次的 fact 的 provenance tuple 会包含 N 个 ExtractionProvenance 对象，每个含 raw_text。大文档的大规模合并会让 checkpoint 膨胀。v1 不做 raw_text 截断。
4. **ledger 不知道 merge**：kernel 只看到一条 assertion + 字符串 meta.source。agent 层的 merge 语义不可从 ledger 自省。要查 merge 详情必须通过 BundleCommitResult + ResolutionResult（都不持久化）。
5. **Resolution 不可逆**：一旦 resolved_specs 送入 bundle 并 commit，无法从 ledger 恢复"原始 per-segment specs"。调试需要在送 bundle 之前保留 ResolutionResult。
6. **不做 anaphora resolution**：文档中的"上述条款"、"前一段提到的人"不会被识别为对前文实体的引用。这需要 LLM 二次调用，是 4C3-d 或后续的事。
7. **Max resolution batch size**：`config.max_input_specs = 10000` 是硬上限。大文档如果产生超过 1 万条 specs，必须先拆 batch 再 resolve（调用方责任）。
8. **Provenance 扩展影响序列化大小**：`to_checkpoint` 序列化 merged provenance 时会递归展开 merged_from。大合并会让 AgentCheckpointStore 的 draft_manager_json 列膨胀。

---

## 12. Outcome / Deviations

### Outcome

- 新建 `src/factpy_kernel/agent/extraction/resolution.py`
  - `EntityResolver`
  - `MergeEvent`
  - `ResolutionConfig`
  - `ResolutionStats`
  - `ResolutionResult`
  - `ResolutionError`
- 扩展 `src/factpy_kernel/agent/documents/models.py`
  - `ExtractionProvenance.merged_from`
  - `all_sources()` / `source_segment_ids()` / `is_merged()`
  - `to_checkpoint()` / `from_checkpoint()` 递归处理 merged provenance
- 扩展 `src/factpy_kernel/agent/documents/bundle.py`
  - `_provenance_to_draft_source()` 支持 merged provenance 的 `source/source_loc` 规范化
- 扩展 `src/factpy_kernel/agent/orchestrator.py`
  - `resolve_batch_extraction(...)`
  - `extract_resolve_and_create_document_bundle(...)`
- 扩展 `src/factpy_kernel/agent/framework.py`
  - tool registry 43 → 45
- 扩展导出：
  - `src/factpy_kernel/agent/extraction/__init__.py`
  - `src/factpy_kernel/agent/__init__.py`
- 新增测试：
  - `src/factpy_kernel/tests/test_agent_l4c3c_provenance.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_resolver.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_merge_meta.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_workflow.py`
- 更新模块文档：
  - `src/factpy_kernel/agent/docs/README.md`
  - `src/factpy_kernel/agent/documents/docs/README.md`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
  - `docs/README.md`
- 全量验证通过：`python -m unittest discover -s src/factpy_kernel/tests` → `911 tests`, `1 skipped`

### Deviations

1. `:merged_from:N` 的 `N` 采用 **递归去重后的总额外来源数**，而不是直接 `len(prov.merged_from)`
   - blueprint 早期示例使用了直接 `len(prov.merged_from)` 的写法。
   - 实现改为 `len(prov.source_segment_ids()) - 1`，这样在 4C3-c 支持幂等 re-resolution 后，`N` 仍然反映真实 merged 来源数量。
   - 这不改变字符串格式，只是让计数在嵌套 merged provenance 场景下保持诚实。
