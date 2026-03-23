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

最后更新：2026-03-22

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
