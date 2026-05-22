# Task Blueprint Audit: Runtime Traceability And Explainability Blueprint

- Blueprint: [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a dedicated exploratory blueprint for runtime traceability/explainability carrying models without committing to support-graph-first or annotation-first as the chosen route. |
| 2026-03-17 | draft | Semantics discussion added | Extended the draft to note that a shared proof/provenance carrier might be separable from value semantics, and that certainty-style reasoning and probabilistic reasoning may need to be compared as parallel but non-identical evaluator directions. |
| 2026-03-17 | draft | Mapping-boundary discussion added | Added exploratory notes on how proof instances, proof-shape reuse, audit snapshots/references, and candidate-level versus proof-level annotation might need to be separated when comparing hybrid carrying models. |
| 2026-03-17 | draft | Cross-domain prompts added | Added a non-authoritative discussion section that treats `docs/references/working/cross-domain-compliance-framing.md` only as an unsourced internal prompt, extracting abstract capability framings such as time-window reasoning, obligation-state derivation, weak-signal combination, and audit-log to proof-tree progression. |
| 2026-03-17 | draft | Verified ESA anchors and reference scenarios added | Added official ESA SDM anchors for threshold-driven compliance state, probabilistic assessment, and SDMR compliance matrices, and introduced named ESA/AML reference scenarios to pressure-test carrying-model choices without freezing the route. |
| 2026-03-17 | draft | Hybrid framing refined | Adjusted the cross-domain prompt section to explicitly capture a three-layer hybrid candidate (`proof/provenance carrier` + `annotation/evaluator layer` + `audit/trace layer`) while keeping it non-decisive and exploratory. |
| 2026-03-17 | draft | Annotation extension candidates sorted | Added a discussion-only classification of which previously discussed annotation extensions still look worthwhile (`keep in view`), which should remain observational, and which are currently poor primary directions. |
| 2026-03-17 | draft | Delivery-shape constraints added | Extended the question about near-term demonstrations to explicitly compare API-only, shareable audit/evidence view, and NL-explain delivery shapes, noting that carrying-model choices may remain underconstrained until a likely consumer form is discussed. |
| 2026-03-17 | draft | Proof entry point added | Added an explicit discussion of whether each candidate needs a stable proof entry point identifier, using Rainbird's `factID` only as a comparison reference and keeping storage/return-shape questions open. |
| 2026-03-17 | draft | Carrier-boundary analysis added | Added a dedicated section to compare where `source taxonomy`, `missing optional conditions`, and `contribution / impact breakdown` may belong across proof carrier, annotation/value-semantics, and audit/trace layers. |
| 2026-03-17 | draft | Reference-doc links refreshed | Updated the blueprint to explicitly cite `docs/references/README.md`, `docs/references/working/cross-domain-compliance-framing.md`, and `docs/references/external/rainbird-evidence-chain-compare.md`, and corrected the stale self-reference from `§5.8` to `§5.9`. |
| 2026-03-17 | draft | Support-artifact framing refined | Corrected the proof-entry discussion to note that `evaluate_where` only returns value bindings, not assertion identities; reframed the long-term direction around a witness-capable projection layer plus a `SupportArtifact` carrier, and separated rule-run execution trace as its own follow-on concern. |
| 2026-03-17 | draft | Support-artifact child blueprint linked | Added a short bridge note from the parent blueprint to `2026-03-17_support-artifact-native-capture.md`, clarifying that native support capture now has its own implementation-facing child blueprint while the parent remains a discussion blueprint. |
| 2026-03-17 | draft | Explain-ref child blueprint linked | Added a short bridge note from the parent blueprint to `2026-03-17_explain-ref-service-unification.md` after the unified service-level explain contract landed and was archived as its own implementation slice. |
| 2026-03-17 | draft | Rule-run schema child blueprint linked | Added a short bridge note from the parent blueprint to `2026-03-17_rule-run-trace-schema-contract.md` so the remaining `rule_run` work tracks the current code reality: schema/contract freeze, not first-time trace capture. |
| 2026-03-17 | draft | Rule-run schema child blueprint archived | Updated the parent bridge note to point at the archived `2026-03-17_rule-run-trace-schema-contract.md` after the schema/contract slice landed. |
| 2026-03-18 | draft | Engine witness child blueprint linked | Added a short bridge note from the parent blueprint to `2026-03-18_engine-witness-parity.md` so the remaining engine explainability work is tracked as explicit degradation semantics first, not premature true-witness parity. |
| 2026-03-18 | draft | Engine witness child blueprint archived | Updated the parent bridge note to point at archived `2026-03-18_engine-witness-parity.md` after explicit degraded explain semantics landed for engine candidates. |
| 2026-03-18 | draft | Parent blueprint realigned to current baseline | Added an explicit current-position section noting that support capture, explain-ref handles, runtime `raw -> summary -> narrative -> NL`, and audit/static proof-entry are now implemented; clarified that evidence tree belongs to the parent blueprint's original `proof-tree / support-graph` next stage rather than a new mother plan. |
| 2026-03-20 | draft | Parent blueprint baseline refreshed | Updated the current-position section after provenance-role taxonomy and candidate tree NL explain landed; remaining open directions now start at salience / impact and stronger engine witness parity. |
| 2026-03-20 | draft | Salience / impact child blueprint frozen and archived | Salience / impact scoped as decision-only archive: owner = annotation/value-semantics, compute-time = query-time, blocked on certainty/weight vocabulary, no implementation slice. |
| 2026-03-22 | superseded | Successor designated | Replaced by `2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md` after the stage boundary shifted from framework-internal explainability expansion to domain validation plus engine provenance feasibility. |

## Decision Notes

- 2026-03-17: 该蓝图当前只作为讨论入口，不是实现型 blueprint。
- 2026-03-17: 新蓝图的默认立场是“比较多种承载模型”，而不是把 `support/proof graph + annotation + audit contract` 写成既定路线。
- 2026-03-17: 相关引用优先锚定三类材料：
  - 母蓝图（总形状与子蓝图拆分入口）
  - temporal/hybrid 蓝图（audit-log / proof-tree / graph-based 排序与引擎边界）
  - 已归档 annotation spike/prototype（已有证据与现有 prototype 真相）
- 2026-03-17: 草案现阶段也倾向于把“proof/provenance carrier”与“value semantics”分开讨论，但这仍只是待比较的 framing，不代表系统已经决定要同时支持 certainty evaluator 与 probabilistic evaluator。
- 2026-03-17: hybrid 方向下最难的边界之一，可能不是“是否有 annotation”，而是 proof carrier、annotation、audit trace 之间应如何映射；草案目前仅把几种拆分方式列为待比较选项。
- 2026-03-17: `docs/references/working/cross-domain-compliance-framing.md` 只被作为无来源的内部参考材料使用；草案仅提取其中可迁移的能力 framing，不把其中任何行业事实或策略判断写成外部依据。
- 2026-03-17: 官方 ESA SDM 文档现在已足以支撑一部分更具体的外部锚点，例如 requirement-scoped threshold state、probabilistic assessment、以及 SDMR compliance matrix；但这些锚点仍被用来比较承载模型，而不是直接决定实现方案。
- 2026-03-17: `audit-log-first` 目前看起来是较强的近期演示候选方向，但草案仍把它表述为 working inclination，而不是既定路线。
- 2026-03-17: 针对外部讨论中新提出的 `proof/provenance carrier -> annotation/evaluator -> audit/trace` 三层 hybrid 形状，草案只把它写成候选 framing，并明确不把它升级为默认路线。
- 2026-03-17: 先前关于 annotation 扩展项的讨论被重新整理为“近期保留 / 中期观察 / 当前不建议作为主方向”三档；该清单用于帮助后续收口 value-semantics 讨论，不构成实现承诺。
- 2026-03-17: `delivery shape` 现在被提升为会反过来约束 carrying-model 讨论的问题；草案倾向于把 visual artifact、structured API、NL explain 视为可比较的消费形态，而不是默认只讨论内部 carrier。
- 2026-03-17: Rainbird 的 `factID` 只被当作 proof entry point 的比较基线；草案当前并未决定本项目是否需要 candidate-level proof ID、audit-level proof ref，或两者并存。
- 2026-03-17: `source taxonomy`、`missing optional conditions`、`impact breakdown` 现在被明确当作 layer-boundary 问题优先讨论，而不是先默认它们都是 annotation 扩展项。
- 2026-03-17: 在引入 `docs/references/` 机制之后，相关 blueprint 应尽量显式引用 reference 文档，而不是继续依赖仓库根目录的临时文件名或隐式材料来源。
- 2026-03-17: 对 derivation 路径而言，`candidate_id` 更像 per-run explain handle，而不是 proof artifact 本身；若要让它真正成为 proof entry，底层仍需让 `support_digest/support_kind` 指向 evaluate 当时捕获的真实 `SupportArtifact`。
- 2026-03-17: 当前 native `evaluate_where` 只能看到 value tuples，原因是 `project_view_facts` 已在投影阶段剥除了 `asrt_id`；因此长期方向不是“存现有 bindings 即可”，而是引入 witness-capable projection / evaluator，使 `pred_witnesses`、`non_fact_steps` 等 support 信息能在执行当时被捕获。
- 2026-03-17: `run_rule` 路径的 explainability 问题不只是“缺一个 ID”，还包括 `memo_rows` 只保留 subrule result rows、不保留 bindings/witness；因此 rule-run trace 应作为独立子蓝图推进，不与 derivation 路径的 `SupportArtifact` 方案混合收口。
- 2026-03-17: 当某个 implementation slice 已足够清晰时，母蓝图应保留 framing 角色，而把具体落地切到子蓝图；`SupportArtifact + witness-capable projection` 已按这一原则拆到独立 active blueprint。
- 2026-03-17: `explain_ref` 的首轮 service contract 现已在独立子蓝图中落地；当前 parent blueprint 继续保留更高层的 carrying-model、delivery-shape 与后续 rule-run trace / engine witness framing。
- 2026-03-17: `rule_run` 的下一切口不应再以“缺少 trace capture”为 framing；当前代码已具备 `RuleTraceArtifact` capture/readback，剩余问题更准确地是 schema semantics 与 service contract 收口。
- 2026-03-18: engine witness parity 的第一轮不应直接承诺 `souffle/problog` 拥有 native 级 witness；当前更准确的剩余问题是 engine candidate 的显式降级语义、`support_kind` contract，以及 service explain surface 如何表达“无 witness”。
- 2026-03-18: 在当前实现基线下，evidence tree 不应被表述为新的计划线；它属于本母蓝图原本就预留的 `proof-tree / support-graph-oriented` 下一阶段，并且默认不被 `temporal-hybrid` 或 `durable-artifact-storage` 作为前置阻塞。
- 2026-03-20: provenance-role taxonomy 与 candidate tree NL explain 已完成后，母蓝图的剩余方向应从”proof-tree 是否存在”转向”proof-tree 还缺哪些 richer semantics / delivery layers”。
- 2026-03-20: salience / impact 归属冻结为 annotation / value-semantics 层，compute-time 冻结为 query-time / read-time；现有 tree/summary 结构信号不足以产出有意义的 salience；”structural salience proxy” 被否决。Implementation blocked on certainty / weight vocabulary。

- 2026-03-22
  - The blueprint remains historically important because many child slices landed under it, but it is no longer the right active parent: the next unresolved bottleneck is not richer framework delivery, but real ECSS rule complexity and engine-native provenance access.
