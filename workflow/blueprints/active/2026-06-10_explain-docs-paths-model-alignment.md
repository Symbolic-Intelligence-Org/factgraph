# Task Blueprint: Explain Docs — paths-model + new-DTO alignment (public docs)

- Status: scoped
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: docs cleanup slice(`feedback_cleanup_slice_cadence` 轻量;narrative scope-freeze + 通用验收)
- Predecessor: archived [2026-06-09_explain-layer-v2] + [2026-06-10_explain-conformance-rework](实现已收官归档)
- Design Authority: `workflow/design/design-points/active/explain-layer-complete-design.zh.md`(已对齐 shipped)+ `src/factgraph/*/docs/`(current truth)
- Audit Log:
  - [2026-06-10_explain-docs-paths-model-alignment.audit.md](./2026-06-10_explain-docs-paths-model-alignment.audit.md)

---

## 1. Problem

explain 层 v2 + conformance rework 已收官,但**公开文档(docs/)仍残留旧 flat-DAG（`EvidenceNode/Edge`、`root_node_id`、4-tier walk）与旧 DTO（`Claim`/`EvidenceRef`/`raw_kind`/`winning_path_only`）措辞**。需对齐 paths-model（`EvidenceGraph(paths=tuple[EvidenceTree|EvidenceTimeline])` + 三态 verdict + repr）+ 新 DTO(扁平 `EvaluateRow.bindings` + `Certainty` + `ResultFingerprint`)。

## 2. Scope(scope-freeze)

**改写(当前真相·公开文档,~9)**:
- `docs/quickstart/evaluate_and_evidence.md`(重:§5.1 flat-DAG 全段)
- `docs/official/kernel/quickstart/evidence.md`(重:官方 evidence 篇)
- `docs/api/openapi.yaml`(重:explain/evidence schema)
- `docs/quickstart/data_model.md`(中:旧 DTO)
- `docs/quickstart/engines_and_configs.md`(中:旧 DTO/引擎)
- `docs/official/kernel/quickstart/semantics.md`(中)
- `docs/official/kernel/quickstart/assertions.md`(中-轻)
- `docs/official/kernel/quickstart/read-write.md`(中-轻)
- `docs/official/kernel/quickstart/namespace-map.md`(轻:术语)

**不改(历史/工作参考,external-only)**:`docs/references/working/*`(product-readiness-audit / rule-replay-line-redesign-input / load-test 等)—— 历史 material,不重写历史(同 heritage 原则)。

## 3. Non-goals

- 不改 src 代码 / src 模块 docs(已 current truth)。
- 不改 `docs/references/working/*`(历史)。
- 不引入新行为;纯文档对齐 shipped。

## 4. Approach

- **逐份顺序改写**,每份用户 review(用户选定)。
- 基准:已对齐的设计文档 + src 模块 docs + 实际 `row.explain()` 输出(demo 可参照)。
- 顺序:重→中→轻(先 evaluate_and_evidence → official evidence → openapi → data_model/engines → semantics/assertions/read-write/namespace-map)。

## 5. Acceptance(通用 gate)

- [ ] 每份:旧 flat-DAG(`EvidenceNode/Edge`/`root_node_id`/`nodes-edges`/4-tier)与旧 DTO(`Claim`/`EvidenceRef`/`raw_kind`/`winning_path`)措辞清零或更新为 paths-model/新 DTO。
- [ ] 文档示例与 shipped `row.explain()` / EvaluateResult 形态一致(可对 demo / 模块 docs 验证)。
- [ ] openapi schema 与实际 DTO 对齐。
- [ ] `docs/references/working/*` 未改(历史保留)。
- [ ] 全 9 份改写完成后 INVENTORY/归档收尾。

## 6. Outcome / Deviations

逐份完成后累计填写。
