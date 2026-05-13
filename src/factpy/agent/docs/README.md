# FactPy Agent 文档

本目录记录 `src/agent` 的当前实现口径，覆盖对话式 agent 的控制面、read-first review loop、结构化最小写入、精确撤回、native-first 规则 authoring、保守版引擎路由、确定性 document staging、文档 fact draft 的 bundle review/approval、single-segment / batch LLM extraction、单文档 entity resolution，以及 extraction 三层的 Langfuse 最小 observability。

## 1. Scope

- `AgentSession` / `RuntimeBootstrapSpec` / `AgentScope`
- `DraftManager` / `FactDraft`
- `CandidatePayloadCache`
- `BundleManager` / `DraftBundle` / `FactDraftSpec`
- `ExtractionAgent` / `BatchExtractor` / `EntityResolver`
- `ExtractionConfig` / `BatchExtractionConfig` / `ResolutionConfig`
- `AgentTracer` / `NoOpTracer` / `LangfuseTracer`
- `KGReadTools` / `ExplainTools`
- `EvaluateTools` / `WriteTools` / `RuleTools` / `ReadReviewOrchestrator`
- `Layer1AgentSkeleton` / tool registry / optional dependency probes
- `AgentCheckpointStore` / `recover_agent_session`

## 2. Responsibilities

- 管理 agent 侧会话状态，并与 kernel `RuntimeSession` 保持松耦合绑定
- 维护 draft 生命周期与 checkpoint/restore
- 持久化 evaluate 返回的 candidate payload，支撑 accept 前的恢复
- 以 adapter 方式组合现有 `runtime_v1` surface，向上层 agent 提供 schema / claims / rules / candidates / explain 读取能力
- 提供 evaluate → cache → review → accept 的 read-first agent loop
- 提供 confirmed `FactDraft` → `write_runtime_fact` 的结构化最小写入路径
- 提供 `asrt_id` 精确撤回：preview → explicit confirm → `retract_runtime_fact` → checkpoint
- 提供 native-first 规则 authoring：validate → compile-preview → ephemeral register → native evaluate → steps review → accept
- 提供保守版引擎路由：显式 hint / tag / 极简 heuristic → recommendation only，不做自动 dispatch
- 提供 Layer 4C1 文档 staging：单文档 → 确定性 segments + provenance，不触碰 runtime/ledger
- 提供 Layer 4C2 文档 bundle review：`FactDraftSpec[]` → `DraftBundle` → review/approval → per-item best-effort commit
- 提供 Layer 4C3-a single-segment extraction：`DocumentSegment` → LLM proposal → deterministic validation → `FactDraftSpec[]`
- 提供 Layer 4C3-b batch extraction：单文档 `segments[]` 顺序驱动 4C3-a，聚合 mixed `segment_results` / `aggregated_specs` / metrics
- 提供 Layer 4C3-c entity resolution：对 `aggregated_specs` 做严格 dedupe / merge，保留多 segment provenance，并产出可直接送 4C2 bundle 的 `resolved_specs`
- 提供 extraction 三层的最小 observability：single-segment / batch / resolution 稳定字段 trace，默认 no-op，可选 Langfuse backend
- 通过 orchestrator 隐藏 runtime session 细节，并在 evaluate / accept / commit 后自动 checkpoint
- 在规则层显式区分 `souffle` authoring preflight 与 `native` runtime execution
- 提供 warm / cold recovery 控制流
- 提供 Layer 1/2/3A/W2a/4A/4B 级别的 framework skeleton：状态序列、tool registry、可选 Burr/PydanticAI/Langfuse 可用性探测

## 3. Non-responsibilities

- 不做语义撤回、文档提取、NL→Rule IR 自由生成
- 不做跨文档 entity resolution、跨文档 extraction queue
- 不做意图识别、slot filling、自然语言生成
- 不统一底层多引擎 explain DTO 语义，只做 raw-first adapter
- 不改动 kernel `runtime_v1` 的现有 HTTP / facade 合同

## 4. Limitations & Compatibility

- 当前 Layer 1 不依赖真实 Burr / PydanticAI；checkpoint 与工具骨架先以纯 Python 可测实现落地，后续可替换为框架集成
- `Layer1AgentSkeleton` 当前不发起 model call；它只固定控制面状态序列、tool registry 与可选依赖状态
- `accept_runtime_derivation()` 仍要求完整 candidate object，因此 `CandidatePayloadCache` 是当前恢复链路的必要前提
- cold restart 后旧 runtime session 的 cached candidates 只保留为 stale 诊断信息，不能直接 accept
- `ExplainTools.get_summary()` 采用 raw-first envelope；不同引擎的 `summary/detail` 深度不同
- `KGReadTools.list_rules()` 只暴露 runtime inventory 的稳定字段；更丰富语义需上层额外推断
- `EvaluateTools` 只接受结构化 derivation IR，不负责 NL→IR 翻译
- `WriteTools` 只接受结构化 `FactDraft`，不负责 NL→Draft 生成；所有写入都必须经过 confirmed draft
- exact retract 只支持指定 `asrt_id`；不做 dependency scan、impact analysis 或 cascade marking
- `RuleTools` 当前只支持 native ephemeral 执行；`validate/compile-preview` 走 `souffle` preflight，非 native 规则只支持预检/导出，不在 session 内执行
- `EngineRoutingAdvisor` 只给建议，不自动执行；非 native recommendation 下不会注册 ephemeral rule，因此 session state 不会被污染
- cold restart 后 ephemeral rules 全部丢失；Layer 4A 不做 rehydrate，调用方需重新注册
- 实体 `e_ref` 编码现在通过共享 helper `agent/tools/_entity_ref.py` 复用读写同一套 `encode_idref_v1` 逻辑
- stale / missing candidate 一律返回结构化 recovery outcome，不做隐式重算
- `register_and_evaluate_rule()` 通过 `EvaluateOutcome(status=not_requested|ok|error|skipped)` 区分未请求执行、执行成功、执行失败与前置阶段跳过
- `register_and_evaluate_rule_with_routing()` 在 non-native recommendation 下返回 `(None, EvaluateOutcome(status=\"skipped\"), hint)`；如需 preview 由调用方单独调 `preview_rule(spec)`
- `HttpRuntimeAPI` 现在可选接收 `api_key` / `api_key_header`，用于访问启用 API key 认证的 kernel service；`LocalRuntimeAPI` 不受该层影响
- `DocumentStaging` 不依赖 `AgentSession`；orchestrator 只是提供门面和 tool registry 暴露
- `DraftBundle` 是 agent-side carrier，不对应任何 runtime endpoint；bundle commit 复用 Layer 3A `confirm_and_commit_many()`，不提供原子事务
- bundle review 使用 `approved_draft_ids` 跟踪通过项；approved drafts 保持 `pending`，由 commit 时统一走 Layer 3A `pending -> confirmed -> committed`
- `AgentCheckpointStore` 现在持久化 `(session, draft_manager, bundle_manager)` 三元组；旧 checkpoint 缺失 `bundle_manager_json` 时按空 manager 兼容恢复
- cold restart 后 document bundle 会恢复，但仍不跨 `AgentSession` 迁移
- `ExtractionAgent` 是纯函数式组件：不 checkpoint、不触碰 DraftManager/BundleManager/ledger
- `BatchExtractor` 同样是纯函数式组件：不 checkpoint、不直接创建 bundle；只做顺序驱动、失败捕获、batch cap 与 metrics 聚合
- `EntityResolver` 也是纯函数式组件：不 checkpoint、不触碰 DraftManager/BundleManager/runtime/ledger；只处理单文档 `FactDraftSpec[]`
- Langfuse observability 只覆盖 extraction 三层；read/write/rule/retract 路径不发 trace
- observability 默认是 `NoOpTracer`；只有显式注入 `LangfuseTracer` 时才真正发 trace
- Langfuse trace 只发送稳定聚合字段，不上传 raw_text、entity_identity、field_values 或 rejection detail
- 4C3-a 以 `session.bootstrap_spec.open_dto["schema_ir"]` 为优先 schema source，runtime raw schema fetch 为 fallback；不以 `KGReadTools.get_schema_summary()` 作为 canonical schema source
- `ExtractionProvenance.raw_text` 保存完整 `segment.raw_text`；送给模型的 prompt text 可能被 `max_text_chars` 截断
- extraction optional dependencies (`instructor` / `litellm`) 只在 extraction 模块内做 local import 检查，不扩展 skeleton 级 `OptionalDependencyStatus`
- 4C3-b 扩展了 `ExtractionError.error_kind`，新增 `unexpected` 与 `batch_cap_reached`；batch truncation 的聚合 rejection 使用 `proposal_index == -1` 作为 batch-local sentinel
- 4C3-c 扩展了 `ExtractionProvenance.merged_from`；`all_sources()` / `source_segment_ids()` 递归展开并按 `segment_id` 去重，支持对已 resolved 的 specs 再次调用 resolution
- 4C3-c 的 `fact_key` 对 `field_values` **保留原始顺序**；这与 4C3-a validation 的 schema 参数位次对齐保持一致，因此 `related_to(a,b)` 与 `related_to(b,a)` 不合并
- merged provenance 写入 draft 时会把 `source` 规范化为 `doc:<name>:seg:<primary>:merged_from:<N>`，并把全部 segment 列表写入 `source_loc`

## 5. Test Entry Points

- `src/agent/tests/test_agent_layer1_models.py`
- `src/agent/tests/test_agent_layer1_tools.py`
- `src/agent/tests/test_agent_layer2_runtime_api.py`
- `src/agent/tests/test_agent_layer2_workflow.py`
- `src/agent/tests/test_agent_layer3a_runtime_api.py`
- `src/agent/tests/test_agent_layer3a_write.py`
- `src/agent/tests/test_agent_w2a_runtime_api.py`
- `src/agent/tests/test_agent_w2a_retract.py`
- `src/agent/tests/test_agent_l4a_runtime_api.py`
- `src/agent/tests/test_agent_l4a_rules.py`
- `src/agent/tests/test_agent_l4a_workflow.py`
- `src/agent/tests/test_agent_l4b_routing.py`
- `src/agent/tests/test_agent_l4b_workflow.py`
- `src/agent/tests/test_agent_l4c1_models.py`
- `src/agent/tests/test_agent_l4c1_clarity.py`
- `src/agent/tests/test_agent_l4c1_txt_parser.py`
- `src/agent/tests/test_agent_l4c1_pdf_parser.py`
- `src/agent/tests/test_agent_l4c1_docx_parser.py`
- `src/agent/tests/test_agent_l4c1_staging.py`
- `src/agent/tests/test_agent_l4c2_models.py`
- `src/agent/tests/test_agent_l4c2_bundle_manager.py`
- `src/agent/tests/test_agent_l4c2_workflow.py`
- `src/agent/tests/test_agent_l4c3a_models.py`
- `src/agent/tests/test_agent_l4c3a_validation.py`
- `src/agent/tests/test_agent_l4c3a_prompts.py`
- `src/agent/tests/test_agent_l4c3a_extractor.py`
- `src/agent/tests/test_agent_l4c3a_workflow.py`
- `src/agent/tests/test_agent_l4c3b_models.py`
- `src/agent/tests/test_agent_l4c3b_batch_extractor.py`
- `src/agent/tests/test_agent_l4c3b_workflow.py`
- `src/agent/tests/test_agent_l4c3c_provenance.py`
- `src/agent/tests/test_agent_l4c3c_resolver.py`
- `src/agent/tests/test_agent_l4c3c_merge_meta.py`
- `src/agent/tests/test_agent_l4c3c_workflow.py`
- `src/agent/tests/test_agent_observability_noop.py`
- `src/agent/tests/test_agent_observability_build_tracer.py`
- `src/agent/tests/test_agent_observability_langfuse.py`
- `src/agent/tests/test_agent_observability_extraction_hooks.py`

## 6. Related Historical Blueprints

- `docs/blueprints/active/2026-03-29_dialog-agent-blueprint-v1.md`
- `docs/blueprints/active/2026-04-09_dialog-agent-blueprint-v1.1-delta.md`
- `docs/blueprints/archive/2026-04-09_agent-layer1-control-plane-mvp.md`
- `docs/blueprints/archive/2026-04-09_agent-layer2-read-first-agent.md`
- `docs/blueprints/archive/2026-04-10_agent-layer3a-structured-write.md`
- `docs/blueprints/archive/2026-04-10_agent-w2a-exact-retract.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4a-native-rule-authoring.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4b-conservative-engine-routing.md`
- `src/agent/documents/docs/README.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4c1-document-staging.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4c2-draft-bundle-review.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4c3a-single-segment-extraction.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4c3b-batch-extraction.md`
- `docs/blueprints/archive/2026-04-10_agent-layer4c3c-entity-resolution.md`
- `docs/blueprints/archive/2026-04-10_agent-langfuse-minimal-observability.md`
- `src/agent/extraction/docs/README.md`
- `src/agent/observability/docs/README.md`
