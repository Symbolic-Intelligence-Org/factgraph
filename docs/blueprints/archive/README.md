# Archived Blueprints

本目录存放两类条目：

- 按当前工作流正常归档的任务蓝图
- 从 `docs/blueprint_history/` 回填而来的 reconstructed archive 条目

它们用于保留：

- 任务为什么这样设计
- 实现过程中有哪些边界决策
- 最终落地与初始蓝图有哪些偏差

对 reconstructed 条目，还必须额外保留：

- 原始历史来源
- 可验证的 git 首次出现时间
- 当前迁移发生的日期与范围

reconstructed 条目可以与标准 archive 共享 10 节结构，但必须显式标注 `Archive Mode: reconstructed`，不得伪造自己曾真实走过现代 active blueprint workflow。

当前仓库中更早的历史蓝图仍保留在 [docs/blueprint_history/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/README.md)。

## Inventory

最后更新：2026-05-06

| Date | Blueprint | Status | Summary |
|------|-----------|--------|---------|
| 2026-03-15 | blueprint-workflow-foundation | archived | 建立可持续、可审计的 blueprint 工作流 |
| 2026-03-15 | historical-blueprint-status-backfill | archived | 回填 blueprint_history/ 的状态一致性 |
| 2026-03-15 | legacy-reconstructed-archive-rules | archived (reconstructed) | 定义 reconstructed archive 迁移规则 |
| 2026-03-15 | overall-system-blueprint | superseded | 早期跨层总蓝图；已由 2026-03-22 阶段母图接替当前 framing 角色 |
| 2026-03-16 | souffle-annotation-benchmark-spec | archived | Souffle annotation benchmark 规格 |
| 2026-03-16 | souffle-backed-annotation-kernel-spike | implemented | Souffle-backed reasoning kernel spike |
| 2026-03-16 | temporal-hybrid-reasoning-blueprint | superseded | 早期 temporal/hybrid 母蓝图；当前阶段已收敛到 ECSS fit 与 provenance feasibility |
| 2026-03-17 | artifact-sidecar-store | implemented | File-backed durable explain carrier |
| 2026-03-17 | audit-package-artifact-export | implemented | Explain artifact audit package 导出 |
| 2026-03-17 | candidate-id-support-backref | implemented | Candidate→support backref 补齐 |
| 2026-03-17 | durable-artifact-storage | implemented | Durable artifact 存储方案 |
| 2026-03-17 | explain-ref-service-unification | implemented | Service explain handle 统一 |
| 2026-03-17 | reference-docs-workflow | archived | Reference docs 工作流定义 |
| 2026-03-17 | rule-run-trace-schema-contract | implemented | Rule run trace schema contract |
| 2026-03-17 | run-rule-trace-capture | implemented | Rule trace capture at evaluate time |
| 2026-03-17 | runtime-service-explain-readback | implemented | Service 层 explain readback |
| 2026-03-17 | runtime-traceability-explainability-blueprint | superseded | Traceability/explainability 母蓝图；子实现已落地，当前方向改为 domain validation + engine provenance |
| 2026-03-17 | sidecar-retention-gc | implemented | Sidecar retention + TTL GC |
| 2026-03-17 | souffle-annotation-kernel-prototype | implemented | Souffle annotation kernel prototype |
| 2026-03-17 | support-artifact-native-capture | implemented | Native derivation support artifact capture |
| 2026-03-17 | support-artifact-readback | implemented | Support artifact readback 接口 |
| 2026-03-18 | aml-aggregation-materialization-walkthrough | implemented | AML event aggregation materialization walkthrough |
| 2026-03-18 | aml-case-review-walkthrough | implemented | AML case review walkthrough |
| 2026-03-18 | aml-event-aggregation-semantics | implemented | AML event aggregation semantics |
| 2026-03-18 | aml-obligation-trigger-semantics | implemented | AML obligation trigger semantics |
| 2026-03-18 | aml-suspicious-account-anchoring | implemented | AML suspicious account anchoring |
| 2026-03-18 | aml-transaction-feed-materialization-walkthrough | implemented | AML transaction feed materialization walkthrough |
| 2026-03-18 | aml-transaction-feed-normalization-anchoring | implemented | AML transaction feed normalization anchoring |
| 2026-03-18 | aml-trigger-walkthrough | implemented | AML trigger walkthrough |
| 2026-03-18 | audit-compliance-matrix-ui | implemented | Audit compliance matrix static UI |
| 2026-03-18 | audit-rule-run-explain-summary-export | implemented | Audit rule run explain summary export |
| 2026-03-18 | clinical-deterioration-uncertainty-anchoring | implemented | Clinical deterioration uncertainty anchoring |
| 2026-03-18 | clinical-weak-signal-walkthrough | implemented | Clinical weak signal walkthrough |
| 2026-03-18 | conflicting-multi-note-evidence-walkthrough | implemented | Conflicting multi-note evidence walkthrough |
| 2026-03-18 | conflicting-narrative-evidence-anchoring | implemented | Conflicting narrative evidence anchoring |
| 2026-03-18 | correlated-multi-note-review-walkthrough | implemented | Correlated multi-note review walkthrough |
| 2026-03-18 | cross-domain-validation-stage-handoff-refresh | implemented | Cross-domain validation handoff refresh |
| 2026-03-18 | document-evidence-extraction-anchoring | implemented | Document evidence extraction anchoring |
| 2026-03-18 | ecss-requirement-authoring-surface | implemented | ECSS requirement authoring surface |
| 2026-03-18 | ecss-scenario-anchoring | implemented | ECSS scenario anchoring |
| 2026-03-18 | ecss-vcd-compliance-delivery | implemented | ECSS VCD compliance delivery |
| 2026-03-18 | engine-witness-parity | implemented | Engine witness parity |
| 2026-03-18 | form-document-extraction-walkthrough | implemented | Form document extraction walkthrough |
| 2026-03-18 | free-text-narrative-evidence-anchoring | implemented | Free-text narrative evidence anchoring |
| 2026-03-18 | mixed-source-case-pack-anchoring | implemented | Mixed-source case pack anchoring |
| 2026-03-18 | mixed-source-case-pack-walkthrough | implemented | Mixed-source case pack walkthrough |
| 2026-03-18 | multi-note-narrative-synthesis-anchoring | implemented | Multi-note narrative synthesis anchoring |
| 2026-03-18 | native-candidate-evidence-tree-v1 | implemented | Candidate evidence tree v1 |
| 2026-03-18 | process-safety-shutdown-anchoring | implemented | Process safety shutdown anchoring |
| 2026-03-18 | process-safety-shutdown-walkthrough | implemented | Process safety shutdown walkthrough |
| 2026-03-18 | rule-run-explain-narrative | implemented | Rule run explain narrative |
| 2026-03-18 | rule-run-explain-narrative-parity | implemented | Rule run explain narrative parity |
| 2026-03-18 | rule-run-nl-explain | implemented | Rule run NL explain |
| 2026-03-18 | runtime-rule-run-explain-summary-api | implemented | Runtime rule run explain summary API |
| 2026-03-18 | runtime-structured-json-explain-api | scoped | Runtime structured JSON explain API |
| 2026-03-18 | runtime-traceability-evidence-tree-realignment | implemented | Traceability evidence tree realignment |
| 2026-03-18 | scenario-a-audit-delivery-shape | scoped | Scenario A audit delivery shape |
| 2026-03-18 | scenario-a-composite-reference-check | implemented | Scenario A composite reference check |
| 2026-03-18 | scenario-a-temporal-semantics | implemented | Scenario A temporal semantics |
| 2026-03-18 | scenario-a-uncertainty-and-confidence | implemented | Scenario A uncertainty and confidence |
| 2026-03-18 | session-handoff-refresh | implemented | Session handoff state refresh |
| 2026-03-18 | single-note-narrative-extraction-walkthrough | implemented | Single-note narrative extraction walkthrough |
| 2026-03-19 | blueprint-workflow-active-archive-cleanup | implemented | Blueprint active→archive cleanup |
| 2026-03-19 | candidate-evidence-tree-provenance-source-taxonomy | implemented | Evidence tree provenance/source taxonomy |
| 2026-03-19 | engine-candidate-explain-tree-degraded-node-shape | implemented | Engine degraded tree node shape |
| 2026-03-19 | evidence-tree-stage-handoff-refresh | implemented | Evidence tree stage handoff refresh |
| 2026-03-19 | native-candidate-evidence-tree-recursive-proof-semantics | implemented | Recursive proof semantics |
| 2026-03-19 | native-candidate-evidence-tree-richer-unresolved-taxonomy | implemented | Richer unresolved taxonomy |
| 2026-03-19 | native-candidate-evidence-tree-v2 | implemented | Evidence tree v2 |
| 2026-03-19 | native-candidate-evidence-tree-winning-branch-narrowing | implemented | Winning branch narrowing |
| 2026-03-19 | native-candidate-evidence-tree-winning-branch-semantics | implemented | Winning branch semantics |
| 2026-03-19 | native-derivation-ruleref-execution-decision | implemented | RuleRef execution decision |
| 2026-03-19 | native-where-ruleref-execution-substrate | implemented | Where RuleRef execution substrate |
| 2026-03-20 | candidate-confidence-kind | implemented | Candidate confidence_kind 语义化 |
| 2026-03-20 | candidate-evidence-tree-nl-explain | implemented | Candidate evidence tree NL explain |
| 2026-03-20 | candidate-evidence-tree-salience-impact | scoped | Candidate evidence tree salience/impact |
| 2026-03-20 | certainty-propagation-prototype | implemented | Certainty propagation prototype |
| 2026-03-20 | certainty-weight-vocabulary | implemented | Certainty weight vocabulary |
| 2026-03-20 | engine-partial-witness-adapter-contract | implemented | Engine partial witness adapter contract |
| 2026-03-20 | engine-partial-witness-audit-static-surface | implemented | Engine partial witness audit+static surface |
| 2026-03-20 | live-evidence-url-runtime-permalink | implemented | Live evidence URL runtime permalink |
| 2026-03-20 | rule-condition-weight-metadata | implemented | Rule condition weight metadata |
| 2026-03-21 | certainty-audit-static-delivery | implemented | Certainty audit+static export-time materialization |
| 2026-03-21 | certainty-aware-narrative-nl-delivery | implemented | Certainty-aware narrative/NL delivery |
| 2026-03-21 | certainty-summary-explain-delivery | implemented | Certainty summary explain delivery |
| 2026-03-21 | confidence-kind-certainty-routing | implemented | Resolver protocol + create-time certainty routing |
| 2026-03-21 | certainty-runtime-boundary-cleanup | implemented | Certainty helper extraction + archive inventory |
| 2026-03-21 | certainty-salience-ranking-v1 | implemented | Salience ranking: impact 升序 + bottleneck 标注 + NL weakest-condition |
| 2026-03-21 | phase3-test-decomposition | implemented | 10K-line test monolith → 7 capability files |
| 2026-03-21 | fact-confidence-to-evidence-tree | implemented | Fact-level confidence carrier: meta.confidence → assertion_fact → condition_confidence=max(children) |
| 2026-03-21 | certainty-additive-aggregation-v1 | implemented | Second aggregation strategy: weighted additive contribution alongside bottleneck/min |
| 2026-03-22 | docs-memory-and-blueprint-realignment | archived | design→active mother blueprint、handoff→memory、旧 active 母蓝图 superseded 归档 |
| 2026-03-22 | souffle-provenance-adapter-v0 | implemented | Adapter-local Souffle `-t explain` parser/runner helper；验证递归链、否定叶子与规则编号，不触碰 core/service/audit 契约 |
| 2026-03-23 | ruleref-souffle-query-export | implemented | 为 query-bearing package export 增加 registry-backed `ruleref` 编译；真实 ECSS top-level compliance 已可产出 Souffle proof tree |
| 2026-03-23 | provenance-audit-consumer-surface | implemented | Souffle provenance 进入正式 audit pipeline：`provenance_trees.jsonl` 物化、AuditQuery 读取、candidate static page 渲染 `Engine Provenance` section |
| 2026-03-23 | provenance-coverage-and-bridge | implemented | Provenance consumer surface 收口：`provenance_statuses.jsonl`、candidate badge / truncation UX、package-level coverage summary 与 landing page coverage metrics |
| 2026-03-23 | esa-demo-packaging | implemented | Standalone ESA demo script + static HTML polish + positioning doc + walkthrough doc; 9 ECSS rules, 2 missions, provenance, 26-page audit site |
| 2026-03-26 | pyreason-provenance-adapter-v0-spike | implemented | PyReason adapter-local provenance carrier (event log, not proof tree); `PyReasonTraceEventV0` / `PyReasonTraceV0`; verified on pyreason==3.0.0 |
| 2026-03-26 | pyreason-rule-ext-v0 | implemented | Adapter-local `PyReasonRuleDef` / `PyReasonRuleExt` / `PyReasonFactDef` + minimal WHERE→PyReason compile helper; runner and demo now accept typed defs while preserving legacy tuples |
| 2026-03-26 | pyreason-runner-v0 | implemented | Reusable runner helper: session -> graph -> reason -> trace -> derived_session; integration demo now delegates to runner |
| 2026-03-26 | pyreason-session-batch-api-and-annotations | implemented | `PyReasonSession.batch()` entity-level API + annotation template generation + batch-based integration demo refresh |
| 2026-03-26 | pyreason-session-annotation-accept-v0 | implemented | Adapter-local accept helper that persists `PyReasonSession` facts to Ledger and materializes `pyreason/semantic/*` annotations via real assertion `asrt_id` binding |
| 2026-03-26 | unified-fact-write-and-edge-api | implemented | Relationship SDK type + schema_ir compilation + PyReason engine-specific write session (Phase 1) |
| 2026-03-26 | annotation-store-v0-schema-and-ledger | implemented | Assertion Annotation Store: `AnnotationRow` + `annotation_rows` DDL + shared whitelist dual-write in `write_protocol` + legacy `meta_rows` projection; 51 new tests |
| 2026-03-27 | pyreason-execution-surface-v0-decision | superseded | Original 4 decisions (D1-D4) for PyReason execution surface; superseded by `multi-engine-execution-surface-decision` after office hours redesign revealed shadow pipeline problem |
| 2026-03-27 | multi-engine-execution-surface-impl | implemented | PyReason joined the shared evaluate/accept surface via `engine_ext` passthrough, WhereIR compiler, engine evaluator, pending annotation side-channel, and SDK end-to-end coverage |
| 2026-03-27 | pyreason-execution-surface-closeout | implemented | Closed the remaining `engine_ext` type-guard gap and formalized reusable post-accept PyReason annotation persistence |
| 2026-03-27 | pyreason-real-engine-validation | implemented | L1 gate passed: root cause was stale numba cache (144 files), not version incompatibility. Full real-engine chain validated: evaluate (166.6s first JIT) → 2 CandidateSet → accept → 6 annotations persisted |
| 2026-03-27 | engine-options-impl | implemented | Shared evaluate dispatch now accepts call-time `engine_options`; SDK keeps it out of authored payloads, native rejects non-empty options, and PyReason exposes `timesteps`-only runtime config with adapter-local validation |
| 2026-03-27 | annotation-consumer-migration-l2 | implemented | Assertion annotation consumer lane: export + reader + query index + static UI panel |
| 2026-03-27 | problog-semantic-annotation-parity-l4 | implemented | L4: ProbLog results write `problog/semantic/probability` annotations; enters unified audit/static consumer pipeline |
| 2026-03-27 | multi-engine-semantic-delivery | implemented | Mother blueprint: all gates (1-3) closed, all direction lines (L1-L4) complete, engine_options future branch also done. 499 tests green |
| 2026-03-28 | engine-provenance-surface-spike | implemented | Shared provenance envelope lane for PyReason/ProbLog runtime candidate explain; Store/runtime now records and reads back engine-native provenance carriers |
| 2026-03-28 | problog-timeout-eval-surface | implemented | ProbLog eval split + runtime `engine_options.timeout` support + parser fix for tab-format CLI output |
| 2026-03-28 | pyreason-graph-fact-materialization-fix | implemented | Real-engine fix: graph build becomes structure-only and node facts lower through explicit `add_fact(...)` registration |
| 2026-03-28 | pyreason-node-edge-channel-split | implemented | PyReason runner now splits node facts and edge labels into different engine channels to match real propagation semantics |
| 2026-03-28 | pyreason-threshold-aware-clause-bounds | implemented | Added `body_predicate_bounds` compile surface so bounded seeds can participate through explicit clause intervals |
| 2026-03-28 | pyreason-static-head-bounds | implemented | Added static `head_bound` support for compiled PyReason rule heads |
| 2026-03-28 | pyreason-seed-warning-and-demo-reframe | implemented | Narrowed bounded-seed warning to threshold semantics and reframed demo/docs around the real engine boundary |
| 2026-03-28 | pyreason-annotation-gap-remediation | implemented | Closed annotation/design audit gaps around bounded materialization, revocation dual-write, accept validation, and static UI derivation display |
| 2026-03-28 | rule-engine-ext-alignment | implemented | Shared `Rule.engine_ext` became the preferred PyReason rule carrier; adapter compilation/runner/tests/docs aligned to it |
| 2026-03-28 | examples-sdk-schema-cleanup | implemented | Examples and notebooks refreshed to current SDK/schema usage and low-signal legacy scaffolding removed |
| 2026-03-28 | evidence-graph-unified-explain | implemented | Unified `EvidenceGraph` DTO + converters + renderer + candidate-page integration landed across Souffle/PyReason/ProbLog |
| 2026-03-28 | design-branch-closeout | implemented | Final branch closeout: durable `EvidenceGraph` audit delivery, `PyReasonRuleDef` removal, explicit deferred-backlog closure, and archive inventory sync |
| 2026-03-29 | problog-rule-ext-branch-probabilities | implemented | ProbLog branch weighting moved from shared `body_confidences` routing into typed `ProbLogRuleExt`, with SDK/runtime bridge and shared-core signature cleanup |
| 2026-03-29 | problog-fact-probability-canonical-lane | implemented | ProbLog export now prefers `problog/semantic/probability` for fact-level probability and only falls back to `meta.confidence` for legacy data |
| 2026-03-29 | problog-probability-write-lane | implemented | `probability` as first-class `write_protocol` key: `shared/semantic/probability` annotation, auto-derives confidence, ProbLog export reads shared lane |
| 2026-03-29 | pyreason-global-state-isolation | implemented | F-PR-1 fix: `threading.Lock` + `try/finally` for PyReason global singleton isolation and exception-safe cleanup in `run_pyreason()` |
| 2026-03-29 | replace-field-atomicity | implemented | F-CORE-1 fix: preflight validation in `replace_field()` ensures old assertion stays active if new assertion validation fails |
| 2026-03-29 | candidate-support-digest-collision | implemented | F-CORE-2 fix: `_remember_candidate_support()` now raises on same `candidate_id` with different `support_digest` while preserving idempotent same-digest re-registration |
| 2026-03-29 | certainty-child-artifact-eligibility | implemented | F-CORE-3 fix: `check_certainty_artifact_eligibility()` now rejects missing child support artifacts instead of treating them as eligible leaf children |
| 2026-03-29 | core-audit-batch | implemented | Batch closeout for F-CORE-4/5 and F-EG-1/3/4: certainty routing notes, EvidenceGraph cycle/duplicate checks, narrowed static UI exception handling |
| 2026-03-29 | pyreason-adapter-batch | implemented | Batch closeout for F-PR-2/3/4/5/6: bound bool guard, `confidence=0.0` parity, safer pred name parsing, correct annotation binding, shared helper extraction |
| 2026-03-29 | problog-adapter-batch | implemented | Batch closeout for F-PL-1/2/3/4/5: per-candidate trace payload copies, safer result parsing notes, correct annotation binding, bool-confidence fallback, shared parsing extraction |
| 2026-03-30 | evidence-graph-timeline-edges | implemented | F-EG-2 fix: timeline layout now surfaces incoming edge annotations on cards so EvidenceGraph edges remain visible outside tree layout |
| 2026-03-31 | evidence-explain-depth | implemented | Phase 1: fact_meta 嵌入 assertion_fact + source_lines narrative/NL/HTML；Phase 2: explain-steps 端点（三引擎 flat step list）+ render_evidence_steps_html helper；709 tests green |
| 2026-03-31 | 07-explain-steps-demo | implemented | 07 notebook：加 explain_runtime_steps import + source meta for Alice + §2.5/§3.4/§4.3 steps cells + source provenance cells；34→41 cells | Phase 1: fact_meta 嵌入 assertion_fact + source_lines narrative/NL/HTML；Phase 2: explain-steps 端点（三引擎 flat step list）+ render_evidence_steps_html helper；709 tests green |
| 2026-03-31 | rule-label-in-steps | implemented | `support_section.rule_ref_ids` 注入到 evidence tree；`rule_apply` steps 现在输出 `detail.rule_ref_ids` 并使用规则名描述；715 tests green |
| 2026-03-31 | ephemeral-rule-authoring | implemented | `RuntimeSession.ephemeral_rules` + register/list/clear handlers/routes + native evaluate-time registry merge；FS 优先 skip；`evaluate -> accept -> explain-steps` 端到端覆盖；731 tests green |
| 2026-03-31 | llm-integration-surface | implemented | 母蓝图收口：Milestone A（named rule_apply）+ Milestone B（session-scoped ephemeral rules）均关闭；G2 保留为可选增强，G3 继续 deferred |
| 2026-03-31 | runtime-session-schema-readback | implemented | 新增 `GET /v1/runtime/sessions/{session_id}/schema`，返回 `schema_digest + schema_ir`；`GET /sessions/{id}` 保持轻量；735 tests green |
| 2026-04-01 | ephemeral-rule-hardening | implemented | D1 upsert replace、D2 register-time unknown predicate fail、D3 stable `details.error_code/remediation_hint`；`run/evaluate` 错误更适合 agent 恢复；743 tests green |
| 2026-04-01 | session-agent-inventory | implemented | 新增 `GET /sessions/{id}/rules` 与 `GET /sessions/{id}/candidates`；session 级 rule inventory + candidate rediscovery readback 落地；754 tests green |
| 2026-04-09 | agent-layer1-control-plane-mvp | implemented | 新建 `src/factpy_kernel/agent/` Layer 1 控制面：AgentSession/DraftManager/CandidatePayloadCache/KGReadTools/ExplainTools/recovery/framework skeleton；771 tests green |
| 2026-04-09 | agent-layer2-read-first-agent | implemented | RuntimeAPI evaluate/accept 扩展 + EvaluateTools + ReadReviewOrchestrator + 16-tool registry；evaluate→cache→review→accept loop 落地；783 tests green |
| 2026-04-10 | agent-layer3a-structured-write | implemented | RuntimeAPI write_fact 扩展 + WriteTools + ReadReviewOrchestrator structured commit methods + 20-tool registry；confirmed FactDraft → write → committed/checkpoint 落地；795 tests green |
| 2026-04-10 | agent-w2a-exact-retract | implemented | RuntimeAPI retract_fact 扩展 + WriteTools/ReadReviewOrchestrator exact retract 路径 + 22-tool registry；preview→confirm→retract→checkpoint 落地；807 tests green |
| 2026-04-10 | agent-layer4a-native-rule-authoring | implemented | `RuleTools` + orchestrator rule flow + 27-tool registry；validate/compile-preview → ephemeral register → native evaluate → steps review → accept 落地 |
| 2026-04-10 | agent-layer4b-conservative-engine-routing | implemented | `EngineRoutingAdvisor` + `RuleSpec.routing_hint` + orchestrator routing wrapper + 31-tool registry；non-native recommendation 不注册 ephemeral，native override 继续走 Layer 4A；825 tests green |
| 2026-04-10 | agent-layer4c1-document-staging | implemented | 新增 `agent/documents/` 子包 + deterministic staging DTO/parsers/clarity + orchestrator facade + 33-tool registry；4C1 文档 staging 与 runtime 完全解耦；852 tests green |
| 2026-04-10 | agent-layer4c2-draft-bundle-review | implemented | `DraftBundle` / `BundleManager` / `FactDraftSpec` + checkpoint 三元组 + orchestrator bundle review/commit + 39-tool registry；document fact draft 的 batch review/approval 落地；867 tests green |
| 2026-04-10 | agent-layer4c3a-single-segment-extraction | implemented | 新增 `agent/extraction/` 子包 + single-segment LLM extraction + deterministic validation + orchestrator convenience path + 41-tool registry；`DocumentSegment -> FactDraftSpec[] -> bundle` 路径落地；884 tests green |
| 2026-04-10 | agent-layer4c3b-batch-extraction | implemented | `BatchExtractor` + batch metrics / errors + orchestrator batch convenience path + 43-tool registry；单文档 multi-segment extraction → bundle 聚合链路落地；898 tests green |
| 2026-04-10 | agent-layer4c3c-entity-resolution | implemented | `EntityResolver` + merged provenance carrier + orchestrator resolve/bundle convenience path + 45-tool registry；单文档 extraction 去重合并与 multi-segment provenance 保留落地；911 tests green |
| 2026-04-10 | agent-langfuse-minimal-observability | implemented | 新增 `agent/observability/` 子包 + extraction 三层 Langfuse/no-op tracer hook；默认零开销、依赖感知降级、稳定字段 trace；911+ tests green |
| 2026-04-11 | kernel-p0-production-readiness | implemented | H-01 API key auth、H-02 ledger thread-local SQLite + post-commit hooks + shared read lock、H-03 secret hygiene templates/docs/scripts；942 tests green |
| 2026-04-11 | kernel-extraction-response-model-openai-strict-fix | implemented | 4C3-a strict-schema blocker fix：`entity_identity` / `field_values` 改为 typed entry sub-models，validation 正规化回 canonical shapes，新增 OpenAI strict-schema guard tests；959 tests green，B3 real extraction 离开 `Invalid schema` |
| 2026-04-11 | agent-extraction-prompt-schema-alignment-fix | implemented | 4C3-a prompt/schema alignment fix：predicate schema summary 改为 `subject=... field_values=[...]`、predicate arg positional fallback、system prompt 明确 `entity_identity`/`field_values` contract、length mismatch detail 丰富化；967 tests green，B3 rerun 首次产出 valid specs |
| 2026-04-11 | agent-extraction-prompt-residual-patterns-fix | implemented | 4C3-a prompt examples fix：新增两组 WRONG/RIGHT examples 直接打掉 residual `subject leakage` / `multi-entry overpacking` 模式；972 tests green，B3 combined valid rate 57%→76% |
| 2026-03-22 | ecss-domain-validation-and-souffle-provenance-poc | implemented | ECSS domain validation POC with Souffle provenance integration |
| 2026-03-26 | assertion-annotation-store-decision | decision-closed | Froze annotation data model: AnnotationRow schema, shared/adapter namespaces, confidence_kind routing, meta normalization |
| 2026-03-27 | engine-options-runtime-dispatch-decision | decision-closed | Froze engine_options runtime dispatch: timeout/timesteps normalization, per-engine option validation |
| 2026-03-27 | multi-engine-execution-surface-decision | decision-closed | Froze multi-engine execution surface: shared evaluate() entry, mode-based dispatch, CandidateSet normalization |
| 2026-03-27 | multi-engine-execution-surface-design-rationale | decision-closed | Design rationale companion for multi-engine execution surface decision |
| 2026-03-27 | value-carrying-semantics-v1-decision | decision-closed | Froze value-carrying semantics: bounded numeric predicates, PyReason interval model, existence vs value distinction |
| 2026-05-03 | check-operation | implemented | Application-first Check operation; native via `evaluate_native_where` + non-native via evaluate-then-match (souffle SupportArtifact / problog+pyreason ProvenanceEnvelope); Option IV representability gate; `branch_atom_projection=None` reserved slot; first capability shipped on `v0.1-redesign-2026-05-03`; 73 focused + 782 total tests green |
| 2026-05-04 | diagnose-operation | implemented | Application-first Diagnose operation; native pass/fail plus atom-localized failure payload; souffle/problog/pyreason coarse dispatch with observable `EVIDENCE_LOOKUP_MISS`; Q1 Sibling no-Check-call invariant; all 7 §7-Diagnose gates covered; 84 focused + 866 total tests green |
| 2026-05-04 | fact-overlay-capability | implemented | Application-first Fact Overlay Check; native baseline + overlay-applied double-run over projected facts; assertion-scoped `FactValueOverride`; non-native `ENGINE_OVERLAY_NOT_SUPPORTED`; no ledger writes / no live cache contamination / Sibling no-Check-call gates; 72 focused + 944 total tests green |
| 2026-05-05 | why-not-universe-diagnose-capability | implemented | Application-first Why-not Universe Diagnose; explicit finite candidate universe → ordered green/red partition; red rows map Diagnose into Why-not-owned diagnostics; native atom-localized, non-native coarse/unavailable when representable; no evaluator hook / no Check delegation / no ledger write; 99 focused + 1043 total tests green |
| 2026-05-05 | evaluator-frontier-trace-capability | implemented | Native-only evaluator substrate for aggregate failed-frontier tracing; separate `evaluate_native_where_frontier(...)` entrypoint with success parity, sparse per-branch frontier rows, no env dump / trace kwargs / application back-dependency; 36 focused + 1079 total tests green |
| 2026-05-05 | capabilities-e2e-demo | implemented | Deterministic assertion-bearing script composing Check, Diagnose, Fact Overlay Check, Why-not Universe Diagnose, and Evaluator Frontier Trace on one `Person` fixture; smoke test imports and runs demo; 1 demo smoke + 143 related capability tests green |
| 2026-05-05 | canonical-round-story | implemented | Batch 1 round-story wording alignment: Q1-Q5 canonical questions now appear across demo script, notebook markdown, examples README, evidence tutorial §1/§7/§8, and a short capability decision tree; no `src/` changes; focused demo/unit/ruff checks green |
| 2026-05-05 | capability-ergonomics | implemented | Batch 2 application-layer helpers: Fact Overlay override builder, Why-not candidate-universe normalizer, and Store-to-frontier `view_facts` projection helper; demo consumes helpers; no SDK/protocol/runtime algorithm changes; 1088 kernel tests green |
| 2026-05-05 | evaluation-overlay | implemented | Batch 3 EvaluationOverlay core narrowed by Step 0.A to replace/remove; added `EvaluationOverlay` + `FactRemoveAction`, legacy `FactValueOverride` compatibility, projected-row remove runtime, and application-layer remove/overlay helpers; no SDK changes; full kernel 1111 OK / 1 skipped |
| 2026-05-05 | proofframe-rechecker | implemented | Batch 4 ProofFrame Rechecker narrowed by Step 0.A/0.B: Shape B DTOs, native `recheck_proof_frame(...)`, deterministic narrative renderer, strict `not`→`unknown`, no helpers, no SDK/service/agent or shipped capability runtime drift; 33 focused + 1151 full kernel tests OK / 1 skipped |
| 2026-05-05 | rule-disable | implemented | Batch 5a Rule Disable: Shape A `EvaluationOverlay.rule_actions`,single-action native `check_rule_disable_action(...)`,variant rows plus original-frame ProofFrame,Fact Overlay/ProofFrame rule-action rejection guards,no variant support capture,no SDK/service/agent drift; post-archive hardening verified with 145 focused + 1194 full kernel tests OK / 1 skipped |
| 2026-05-05 | rule-condition-replace | implemented | Batch 5b Rule Literal Replace: narrow Const-to-Const native `RuleLiteralReplaceAction`,separate `RuleLiteralReplaceRequest/Result`,single-action `check_rule_literal_replace_action(...)`,variant rows plus original-frame ProofFrame,lower-level `evaluate_where(..., literal_replacements=...)`,Rule Disable non-disable guard,no SDK/service/agent or frontier drift; 194 focused + 1228 full kernel tests OK / 1 skipped |
