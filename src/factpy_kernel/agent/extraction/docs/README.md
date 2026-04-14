# Agent Extraction 文档

本目录记录 `src/factpy_kernel/agent/extraction` 的当前实现口径，覆盖 Layer 4C3-a 的 single-segment LLM extraction、Layer 4C3-b 的 batch extraction orchestration、Layer 4C3-c 的单文档 entity resolution，以及三层 extraction hook 的最小 observability 集成点。

## Scope

- `ExtractionConfig`
- `ExtractionRejection` / `ExtractionResult` / `ExtractionError`
- `BatchExtractionConfig` / `BatchExtractionResult` / `BatchExtractionError`
- `SegmentMetric` / `BatchExtractionMetrics`
- `ResolutionConfig` / `ResolutionResult` / `ResolutionError` / `ResolutionStats`
- `MergeEvent`
- `ExtractionDocumentResult` / `ExtractionDocumentError`
- 动态 `build_response_model(schema_ir)` 约束模型
- prompt 构造：schema summary + segment user prompt
- `validate_proposal(...)`
- `ExtractionAgent.extract_from_segment(...)`
- `BatchExtractor.extract_batch(...)`
- `EntityResolver.resolve_batch(...)`
- `extract_document(...)`
- 三层 observability hook：single-segment / batch / resolution

## Responsibilities

- 对单个 `DocumentSegment` 发起一次受 schema 约束的 LLM 提取调用
- 对单文档的多个 `DocumentSegment` 顺序驱动 single-segment extraction，并聚合 mixed `segment_results` / `aggregated_specs` / `metrics`
- `BatchExtractionConfig.enable_entity_context` 默认开启；batch loop 会把前序 `valid_specs` 累积成结构化 entity context header，并注入到后续 segment 的 user prompt
- `ExtractionAgent.extract_from_segment(...)` 与 `BatchExtractor.extract_batch(...)` 都支持可选 `source_doc_name: str | None`；当调用方提供人类可读文件名时，prompt 中的 `Document: ...` 使用该值而不是 opaque `doc_id`
- entity context 只会在前序 segments 已经产生至少一个有效 entity 时出现；error segments 和 rejected proposals 不进入累积上下文
- `BatchExtractionConfig.enable_gleaning` 默认关闭；开启后，batch loop 会在 pass 1 结束后对低 yield success segments 做 second-pass re-examination
- gleaning second pass 通过 `GLEANING PASS:` 前缀 + 完整 entity context header 复用同一个 `ExtractionAgent.extract_from_segment(...)` 路径
- `aggregated_specs` 包含 pass 1 + gleaning 的全部新增 valid specs；`gleaning_segments_reexamined` 记录 second-pass 覆盖的 segment 数
- 对单文档的 `FactDraftSpec[]` 执行严格 dedupe / merge，并保留完整多 segment provenance
- `ResolutionConfig.enable_alias_merge` 默认关闭；开启后，resolver 会在 exact dedupe 之前先做一层保守 alias canonicalization：仅对同 `entity_type`、单字符串 identity field、且较短 token 集是较长 token 集子集的 entity key 生效
- alias canonicalization 的 canonical key 采用 first-seen 规则；若命中 alias，结果中的 `FactDraftSpec.entity_identity` 会被重写为 canonical key
- `MergeEvent.alias_merge` 区分 exact duplicate merge 与 alias canonicalization 触发的 merge event
- `ExtractionConfig.model` 默认值为 `gpt-4.1`
- `extract_document(...)` 提供产品级入口：在一个函数内完成 schema compile → staging → batch extraction → resolution
- `extract_document(...)` 对 `model` / `temperature` / `timeout_seconds` 采用 call-time 优先级链：显式 scalar > `extraction_config` > env > hardcoded default，并支持 `FACTPY_EXTRACTION_MODEL` / `FACTPY_EXTRACTION_TEMPERATURE` / `FACTPY_EXTRACTION_TIMEOUT`
- `extract_document(...)` 自动从 compiled `schema_ir` 推导 `allowed_entity_types` / `allowed_pred_ids`，默认启用 `enable_gleaning=True`、`enable_alias_merge=True`，并使用产品安全默认值 `max_batch_size=1000` / `require_source=True`
- `extract_document(...)` 始终向 batch path 透传 `source_doc_name=doc_name`，避免 prompt 回退到 opaque `doc_id` hash；若 caller 传 `entity_descriptions`，也会继续透传到 schema summary
- `extract_document(...)` 成功时返回 `ExtractionDocumentResult`，其中 `entities` 是按 `(entity_type, entity_identity)` 聚合后的去重 census，`facts` 是 resolved specs，`merge_events` 直接暴露 resolver merge 结果
- 在 single-segment / batch / resolution 三层产出稳定 trace 字段，默认由 `NoOpTracer` 吞掉，可选由 Langfuse backend 消费
- 通过动态 `Literal[...]` response model 将 `entity_type` / `pred_id` 约束到当前 schema
- 在 OpenAI strict-compatible response model 中，把 `entity_identity` / `field_values` 表达为私有 typed entry 列表；`validate_proposal(...)` 再将其规范化回 `dict[str, Any]` / `list[tuple[str, Any]]`
- prompt schema summary 对 predicate 使用 `subject=... field_values=[...]` 语法；当非 canonical 输入缺少 arg name 时，predicate args 以 `arg{i}:type_domain` 的 positional fallback 渲染
- `build_schema_summary(...)` 支持可选 `entity_descriptions` 参数；调用方可为特定 entity type 注入简短语义描述，帮助 LLM 在 identity grounding 时区分软件组件、文档、人员、团队等概念
- prompt 只对 predicate args 做 positional fallback；`identity_fields[]` 若缺 canonical `name` 会被静默跳过，不教模型生成 synthetic identity keys
- system prompt 明确教授 `entity_identity` / `field_values` 的边界：subject 不进入 `field_values`，`field_values` 长度必须等于非 subject arg 数，且每个 `tag` 必须等于对应 slot 的 `type_domain`
- system prompt 额外包含两个 wrong/right examples，分别针对 residual `subject leakage`（把 subject 误塞进 `field_values`）和 `multi-entry overpacking`（把多个 facts 横向塞进一个 unary proposal）模式
- system prompt 进一步追加独立的 `Semantic Examples` 区块：一组示例约束 `Document.title` 必须是 source text 中逐字出现的稳定标识，否则按 entity-type 维度 abstain；另一组示例约束 `module:description` 必须是 declarative description，而不是 checklist / acceptance / coverage 文本；第三组示例约束 `Module.name` 必须是软件组件标识，不得把 team / org / role / process 名称错提为模块 identity
- 在代码侧注入 `ExtractionProvenance`，不让模型生成 offsets/doc identifiers
- 对 LLM 提议执行 deterministic validation：
  - schema entity/predicate existence
  - identity/field typing
  - `AgentScope` whitelist / `min_confidence`
  - `FactDraftSpec.__post_init__`
- 把超出 `scope.max_batch_size` 的有效提议转成 `scope_max_batch_size` rejection
- 以 `ExtractionResult` / `ExtractionError` 返回，不直接操作 DraftManager、BundleManager 或 ledger
- 在 batch 层把 `scope.max_batch_size` 作为跨 segment 硬上限处理，并通过 `proposal_index == -1` 的聚合 rejection 标记 batch truncation

## Non-responsibilities

- 不做跨文档 batch / queue orchestration
- 不做 RuleDraft 提取
- 不做 SchemaDraft
- 不 checkpoint
- 不直接创建 bundle；`extract_and_create_bundle` convenience path 由 orchestrator 提供
- 不做跨文档 entity resolution、fuzzy matching、外部 KB 对齐或引用消解
- 不负责 tracer wiring；调用方应在构造 `ExtractionAgent / BatchExtractor / EntityResolver` 时直接注入共享 tracer

## Limitations

- `ExtractionAgent` 在默认路径上依赖 optional `instructor` + `litellm`
- observability 默认 no-op；只有显式注入 tracer 时才发 trace
- observability 不上传 raw_text、entity_identity、field_values 或 rejection detail
- 依赖检查局部化在 extraction 模块内，不扩展 agent skeleton 的 global optional probe
- `extract_document(...)` 自身不吞掉 stage failures；staging / extraction / resolution 任一失败都会 raise `ExtractionDocumentError(stage, detail, message)`
- 由于 resolver 当前拒绝空输入，若上游 extraction 产生 0 valid specs，`extract_document(...)` 会以 `stage=\"resolution\"` 抛出 `ExtractionDocumentError`，而不是返回空成功结果
- `provenance.raw_text` 保存完整 `segment.raw_text`；prompt text 可能被 `max_text_chars` 截断
- 大 schema 只做 deterministic summary truncation，不做智能筛选
- `entity_descriptions` 完全由 caller 提供，默认关闭；未提供时 schema summary 的输出格式与早期实现保持兼容
- prompt 层对非 canonical schema 输入具备有限鲁棒性，但 canonical SchemaIR 校验规则本身没有放宽；prompt fallback 只是为了 B3 / dry-run / pre-validation 输入不至于静默丢失 predicate arg 语义
- prompt examples 能显著降低 residual `field_values` shape noise，但不能保证 100% elimination；真实长文档运行里仍可能保留少量 `schema_field_type_mismatch` 作为下一轮 prompt / schema tuning 信号
- 单测使用 mock LLM client；不要求真实 API key
- 额外有一组离线 strict-schema guard tests 直接检查 `openai.pydantic_function_tool(...)["function"]["parameters"]`，用于防止 permissive object schema 回归
- 4C3-b 只做顺序执行与返回值级 metrics；不做 Langfuse/OTel 持久化或 batch-level retry
- 4C3-b 的 entity context header 最大 2000 chars，按完整 entity 行截断；context fact 展示只保留每条 spec 的第一个 `field_value`
- 4C3-b 的 context onset 取决于“前序是否已有 valid entity”，而不是固定从 `segment_index == 1` 开始
- 4C3-b 的 gleaning loop 只会重查 pass 1 成功且 `valid_specs <= gleaning_yield_threshold` 的 segments；error segments 不参与 second pass
- 4C3-b 的 `segment_results` / `per_segment_metrics` / `metrics.total_valid_count` 仍然是 pass 1 only；当 gleaning 命中新事实时，`len(aggregated_specs)` 可以大于 `metrics.total_valid_count`
- 4C3-b 的 gleaning 异常是 non-fatal best-effort：异常 segment 会记入 `gleaning_segments_reexamined`，但不会中断整个 batch
- 当 `source_doc_name` 缺省时，prompt 仍然回退到 `segment.doc_id`；若 `Doc.title` 规则要求 verbatim stable identifier，则仅靠 hash 可能导致 Document proposal 按规则 abstain
- 4C3-c 只做严格 fact-key 匹配：`entity_identity` 键顺序无关，但 `field_values` 原始顺序敏感
- 4C3-c 的 alias merge v1 只覆盖单字段字符串 identity；多字段 identity、跨 entity_type matching、edit-distance / embedding similarity 仍不在 scope
- 真实 LLM notebook 验证未必总能触发 alias merge 路径，因为上游 extraction 有时会先把 alias 直接归一；resolver-level alias 行为的稳定保障来自确定性单测，而不是单次 notebook run
- 4C3-c 的 merge provenance 通过 `ExtractionProvenance.merged_from` 表达；最终 assertion 仍然是单条，merge 语义不会回写 kernel 内部索引
