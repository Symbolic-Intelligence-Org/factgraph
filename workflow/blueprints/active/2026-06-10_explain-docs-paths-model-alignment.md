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

**改写**:
- `docs/quickstart/evaluate_and_evidence.md`(§4 flat-DAG → paths-model;不变式 `{passed,failed}↔evidence`;desc→repr;import)— ✅ done `3381fafd`
- `docs/quickstart/schema_definition.md`(**gap-fill**:补 §1.8 repr DSL 语法 —— 占位符矩阵 + 例子;原只提"repr= 存在")— ✅ done `142ae405`

**核实为非-stale(跳过,假阳性)**:
- `docs/quickstart/data_model.md` / `engines_and_configs.md` —— 命中的 `raw_kind`/`bound` 是**当前写侧 meta keys**(shipped write protocol 仍持久化 `shared/semantic/raw_kind`+`bound`;只有**读侧** `EvaluateRow` 合并为 `certainty`)。非 explain-stale。

**待定**:
- `docs/api/openapi.yaml` —— 无 EvidenceGraph/Node/Edge schema;提及 `claim`/`evidence_ref` compat wire dicts 属 **HTTP API wire 层**(与 SDK explain paths-model 是两个表面)。是否纳入待用户定。

**不改**:
- `docs/official/*` —— **已弃用目录**(用户确认 2026-06-10)。
- `docs/references/working/*` —— external-only 历史(同 heritage)。

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
