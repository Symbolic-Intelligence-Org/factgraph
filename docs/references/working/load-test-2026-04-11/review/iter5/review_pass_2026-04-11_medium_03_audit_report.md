# Review Pass 2026-04-11 — medium_03_audit_report

## Header

- sample_id: `medium_03_audit_report`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/medium/medium_03_audit_report.md`
- doc_id: `1c1cbf45fa645003`
- total_segments: 81
- total_proposal_count (regen): 38
- total_valid_count (regen): 26
- total_rejection_count (regen): 12
- generated_at: 2026-04-11T12:50:41.627668+00:00

### β.1 context (NEW sample, no iter 4 baseline)

This sample was **added in β.1** (2026-04-11) and has **no iter 4 baseline**. It was introduced specifically for the iter 5 → iter 6 decision process to cross-validate F-03 (Module routing breadth regression).

- **β.1 F-03 control role**: **GRADIENT test**. `medium_03_audit_report` is the FactPy Kernel production readiness audit, a mixed-content reference document with market-comparison tables (competitor products: `Neo4j`, `Stardog`, `RDFox`, `AllegroGraph`, `ReasoningLayer`), engine names (`Souffle`, `ProbLog`, `PyReason`), project class names (`ArtifactSidecar`, `CandidateSet`, `EvidenceGraph`, `AnnotationRow`), file paths, and substantive narrative. Expected to show F-03 at lower intensity than the positive control.
- **iter 5 canonical run record**: `run_records/b3_20260411T124044Z_medium_03_audit_report.json` (canonical: 29 proposals / 16 valid / 13 rejected)
- **This packet vs canonical**: regen produced 38 proposals / 26 valid / 12 rejected (+9 proposals, **+10 valid**, −1 rejection). **This is the largest regen-vs-canonical drift observed in β.1** — the valid count swing (16 → 26) is at the high end of OBS-01's variance envelope. Reviewer should note that the 26 drafts in this packet represent a "high-end sample" from the iter 5 distribution on this sample; a different run could have produced fewer drafts, and the proportional approval rate (`yes / total`) matters more than the absolute count here.
- **Pipeline state**: iter 5 `SYSTEM_PROMPT_TEMPLATE` with Semantic Examples block (implemented with deviations, archived). Same prompt state as all other iter 5 packets in this directory.

**Key F-03 probe question**: the audit report contains many **competitor product names** (`Neo4j`, `Stardog`, `RDFox`, `AllegroGraph`, `ReasoningLayer`) and **engine library names** (`Souffle`, `ProbLog`, `PyReason`). These are clearly NOT project modules. If the LLM routes them to `Module` entity with `mod_name=Neo4j`, that is a **new F-03 failure shape** specific to this sample: competitor name leakage as Module identity. Reviewer should tag any such drafts as `WRONG_ENTITY` with a note identifying the pattern. This would be a decisive F-03 generalization signal — if even clearly-external product names get routed to Module, the fix is needed broadly.

**Canonical rejection sample observed**: the first 3 sampled rejections were all Pattern A (`document:mentions`: `got 2, expected 1`). 13 total rejections in canonical / 12 in regen. Whether any are Pattern B crossover or other shapes beyond the sampled 3 is unknown from run_record alone.

**Review purpose**: measure the **F-03 gradient signal**. Specifically:
- Count of `Module` drafts and distribution of identity values
- Distribution of `Module` identity categories: project class names (expected correct), competitor products (expected WRONG_ENTITY, new F-03 shape), engine names (ambiguous — are these "modules"?), file paths, function names
- Count of `Document` drafts and title grounding quality
- Reason code distribution relative to `short_03_architecture` and `medium_02_blueprint_backref`

**Do NOT backfill into any run_record.** Same reason as iter 5 packets: run_records carry pipeline metrics, not per-draft review decisions. Results will be aggregated into a new β.1 summary artifact after all 3 new packets are reviewed.

## Review instructions

For each draft below, fill in the `REVIEW` block at the bottom:

- `approve`: one of `yes` | `no` | `partial`
  - `yes` — the extracted fact is supported by `raw_text` and semantically correct
  - `no` — the fact is wrong, hallucinated, or unsupported by `raw_text`
  - `partial` — the fact is partially correct but needs rewording, scoping, or a different predicate
- `reason_code`: one of
  - `CORRECT` — no issue (use with `approve: yes`)
  - `HALLUCINATED` — fact is not present in raw_text at all
  - `OVERGENERAL` — fact is in raw_text but the object is too broad / too vague
  - `WRONG_ENTITY` — subject entity is mis-identified
  - `WRONG_PREDICATE` — relation should use a different pred_id
  - `WRONG_ARG` — the object/field_values value is factually wrong
  - `DUPLICATE` — same fact as another approved draft in this packet
  - `AMBIGUOUS` — raw_text is genuinely ambiguous; cannot judge
  - `OTHER` — fill in notes
- `notes`: free-text, optional

Summary metrics will be backfilled into the run_record `review` block after the pass is complete. This packet is the source of truth for per-draft decisions.

---

## Drafts

### Draft 001

```yaml
draft_index: 0
entity_type: "Document"
entity_identity:
  title: "知识图谱市场规模"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "$1.07B (2024) → $6.94B (2030), CAGR 36.6%"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0005"
  char_offset_start: 154
  char_offset_end: 238
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    知识图谱市场规模：$1.07B (2024) → $6.94B (2030), CAGR 36.6%。
    可审计性和可解释性正从差异化卖点变为 table-stakes。
```

**Summary**: `Document(title=知识图谱市场规模) -- document:mentions --> string=$1.07B (2024) → $6.94B (2030), CAGR 36.…`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`知识图谱市场规模` is a verbatim heading in the source text, and the quantitative market-size statement is directly supported."
```

---

### Draft 002

```yaml
draft_index: 1
entity_type: "Document"
entity_identity:
  title: "知识图谱市场规模"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "可审计性和可解释性正从差异化卖点变为 table-stakes"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0005"
  char_offset_start: 154
  char_offset_end: 238
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    知识图谱市场规模：$1.07B (2024) → $6.94B (2030), CAGR 36.6%。
    可审计性和可解释性正从差异化卖点变为 table-stakes。
```

**Summary**: `Document(title=知识图谱市场规模) -- document:mentions --> string=可审计性和可解释性正从差异化卖点变为 table-stakes`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`知识图谱市场规模` is a verbatim heading in the source text, and the statement about auditability/explainability becoming table-stakes is directly supported."
```

---

### Draft 003

```yaml
draft_index: 2
entity_type: "Module"
entity_identity:
  module_name: "FactPy Kernel"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "是目前市场上唯一将演绎/概率/时序三种推理范式统一在单一 Python 运行时中、并为每个推导结果生成跨引擎证据树的可审计推理框架。"
confidence: 1.0
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0009"
  char_offset_start: 904
  char_offset_end: 988
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **FactPy Kernel 是目前市场上唯一将演绎/概率/时序三种推理范式统一在单一 Python 运行时中、并为每个推导结果生成跨引擎证据树的可审计推理框架。**
```

**Summary**: `Module(module_name=FactPy Kernel) -- module:description --> string=是目前市场上唯一将演绎/概率/时序三种推理范式统一在单一 Python 运行时…`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`FactPy Kernel` is explicitly named in the source text, and the extracted sentence is a direct declarative description of what it is."
```

---

### Draft 004

```yaml
draft_index: 3
entity_type: "Module"
entity_identity:
  module_name: "Append-only 事实账本 (SQLite)"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=Append-only 事实账本 (SQLite)) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`Append-only 事实账本 (SQLite)` is a plausible architecture-layer identity, but `完整` is status metadata from the comparison table, not a declarative description of what it is or does."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Module"
entity_identity:
  module_name: "多引擎推理调度 (Souffle/ProbLog/PyReason/Native)"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=多引擎推理调度 (Souffle/ProbLog/PyReason/Nativ…) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`多引擎推理调度 (Souffle/ProbLog/PyReason/Native)` is a plausible architecture-layer identity, but `完整` is implementation-status metadata, not a module description."
```

---

### Draft 006

```yaml
draft_index: 5
entity_type: "Module"
entity_identity:
  module_name: "证据树溯源 (tree + narrative + timeline + NL + steps)"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=证据树溯源 (tree + narrative + timeline + NL…) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`证据树溯源 (tree + narrative + timeline + NL + steps)` is a plausible architecture-layer identity, but `完整` is status metadata rather than a declarative description."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Module"
entity_identity:
  module_name: "Schema IR + 类型系统"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=Schema IR + 类型系统) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`Schema IR + 类型系统` is a plausible architecture-layer identity, but `完整` is status metadata rather than a description of the component."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Module"
entity_identity:
  module_name: "候选集生命周期 (generated/accepted/rejected)"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=候选集生命周期 (generated/accepted/rejected)) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`候选集生命周期 (generated/accepted/rejected)` is a plausible architecture-layer identity, but `完整` is implementation-status metadata, not a declarative module description."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Module"
entity_identity:
  module_name: "REST API 服务层 (40+ 端点)"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=REST API 服务层 (40+ 端点)) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`REST API 服务层 (40+ 端点)` is a plausible architecture-layer identity, but `完整` is status metadata rather than a description of the service layer."
```

---

### Draft 010

```yaml
draft_index: 9
entity_type: "Module"
entity_identity:
  module_name: "审计查询接口"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=审计查询接口) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`审计查询接口` is a plausible architecture-layer identity, but `完整` is status metadata, not a declarative description."
```

---

### Draft 011

```yaml
draft_index: 10
entity_type: "Module"
entity_identity:
  module_name: "SDK Facade"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "完整"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0014"
  char_offset_start: 1186
  char_offset_end: 1744
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    | 架构层 | 实现状态 | 行业对标 |
    |--------|---------|---------|
    | Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
    | 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
    | 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
    | Schema IR + 类型系统 | 完整 | canonical type tags |
    | 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
    | REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
    | 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
    | SDK Facade | 完整 | Python SDK: batch/entity/schema |
```

**Summary**: `Module(module_name=SDK Facade) -- module:description --> string=完整`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`SDK Facade` is a plausible architecture-layer identity, but `完整` is implementation-status metadata rather than a description of what the component is or does."
```

---

### Draft 012

```yaml
draft_index: 11
entity_type: "Module"
entity_identity:
  module_name: "ledger"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "多线程并发写入 → 死锁/库损坏；多 worker 部署不可用（session 跨 worker 不可达）"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0036"
  char_offset_start: 3482
  char_offset_end: 3701
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/ledger.py:266-277`
    - **代码**: `sqlite3.connect(path, check_same_thread=False, isolation_level=None)`
    - **风险**: 多线程并发写入 → 死锁/库损坏；多 worker 部署不可用（session 跨 worker 不可达）
    - **影响**: 无法使用标准 ASGI 多 worker 部署
```

**Summary**: `Module(module_name=ledger) -- module:description --> string=多线程并发写入 → 死锁/库损坏；多 worker 部署不可用（session…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`ledger` is a plausible module identity, but the extracted value is a risk/impact statement, not a declarative description of the module itself."
```

---

### Draft 013

```yaml
draft_index: 12
entity_type: "Module"
entity_identity:
  module_name: "ledger"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "无法使用标准 ASGI 多 worker 部署"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0036"
  char_offset_start: 3482
  char_offset_end: 3701
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/ledger.py:266-277`
    - **代码**: `sqlite3.connect(path, check_same_thread=False, isolation_level=None)`
    - **风险**: 多线程并发写入 → 死锁/库损坏；多 worker 部署不可用（session 跨 worker 不可达）
    - **影响**: 无法使用标准 ASGI 多 worker 部署
```

**Summary**: `Module(module_name=ledger) -- module:description --> string=无法使用标准 ASGI 多 worker 部署`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`ledger` is a plausible module identity, but `无法使用标准 ASGI 多 worker 部署` is an operational consequence, not a declarative module description."
```

---

### Draft 014

```yaml
draft_index: 13
entity_type: "Document"
entity_identity:
  title: "/hnsm-backend/.env"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "OPENAI_API_KEY, NEO4J_PASSWORD 明文存储"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0038"
  char_offset_start: 3725
  char_offset_end: 3826
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `/hnsm-backend/.env`
    - **内容**: OPENAI_API_KEY, NEO4J_PASSWORD 明文存储
    - **影响**: 若仓库推送过远端则密钥已泄露
```

**Summary**: `Document(title=/hnsm-backend/.env) -- document:mentions --> string=OPENAI_API_KEY, NEO4J_PASSWORD 明文存储`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`/hnsm-backend/.env` is a verbatim file identifier in the source text, and the statement about cleartext secret storage is directly supported."
```

---

### Draft 015

```yaml
draft_index: 14
entity_type: "Document"
entity_identity:
  title: "/hnsm-backend/.env"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "若仓库推送过远端则密钥已泄露"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0038"
  char_offset_start: 3725
  char_offset_end: 3826
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `/hnsm-backend/.env`
    - **内容**: OPENAI_API_KEY, NEO4J_PASSWORD 明文存储
    - **影响**: 若仓库推送过远端则密钥已泄露
```

**Summary**: `Document(title=/hnsm-backend/.env) -- document:mentions --> string=若仓库推送过远端则密钥已泄露`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`/hnsm-backend/.env` is a verbatim file identifier in the source text, and the leakage risk statement is directly supported."
```

---

### Draft 016

```yaml
draft_index: 15
entity_type: "Document"
entity_identity:
  title: "1c1cbf45fa645003"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "gc_rule_trace() 仅清理 rule_trace，support 文件无 GC；GC 需手动调用"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0045"
  char_offset_start: 4469
  char_offset_end: 4599
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/_artifact_sidecar.py`
    - **问题**: `gc_rule_trace()` 仅清理 rule_trace，support 文件无 GC；GC 需手动调用
    - **影响**: 运行数月后磁盘写满
```

**Summary**: `Document(title=1c1cbf45fa645003) -- document:mentions --> string=gc_rule_trace() 仅清理 rule_trace，support …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`1c1cbf45fa645003` is an internal identifier/hash, not a stable document identifier grounded in the source text."
```

---

### Draft 017

```yaml
draft_index: 16
entity_type: "Document"
entity_identity:
  title: "1c1cbf45fa645003"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "运行数月后磁盘写满"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0045"
  char_offset_start: 4469
  char_offset_end: 4599
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/_artifact_sidecar.py`
    - **问题**: `gc_rule_trace()` 仅清理 rule_trace，support 文件无 GC；GC 需手动调用
    - **影响**: 运行数月后磁盘写满
```

**Summary**: `Document(title=1c1cbf45fa645003) -- document:mentions --> string=运行数月后磁盘写满`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`1c1cbf45fa645003` is an internal identifier/hash rather than a valid document title or stable file identifier from the source text."
```

---

### Draft 018

```yaml
draft_index: 17
entity_type: "Document"
entity_identity:
  title: "1c1cbf45fa645003"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "retract_by_asrt() 仅记录 Revokes 关系，不检查/标记依赖的派生事实"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0047"
  char_offset_start: 4641
  char_offset_end: 4841
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/evidence/write_protocol.py:169-207`
    - **行为**: `retract_by_asrt()` 仅记录 Revokes 关系，不检查/标记依赖的派生事实
    - **影响**: 被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性
    - **注意**: 证据树查询时检查 revocation，但 ledger 层面无保障
```

**Summary**: `Document(title=1c1cbf45fa645003) -- document:mentions --> string=retract_by_asrt() 仅记录 Revokes 关系，不检查/标记…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`1c1cbf45fa645003` is an internal identifier/hash, not a grounded `Document` subject; the behavior statement is supported but attached to the wrong entity."
```

---

### Draft 019

```yaml
draft_index: 18
entity_type: "Document"
entity_identity:
  title: "1c1cbf45fa645003"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0047"
  char_offset_start: 4641
  char_offset_end: 4841
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/evidence/write_protocol.py:169-207`
    - **行为**: `retract_by_asrt()` 仅记录 Revokes 关系，不检查/标记依赖的派生事实
    - **影响**: 被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性
    - **注意**: 证据树查询时检查 revocation，但 ledger 层面无保障
```

**Summary**: `Document(title=1c1cbf45fa645003) -- document:mentions --> string=被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`1c1cbf45fa645003` is an internal identifier/hash, not a stable document identifier for the extracted impact statement."
```

---

### Draft 020

```yaml
draft_index: 19
entity_type: "Document"
entity_identity:
  title: "1c1cbf45fa645003"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "证据树查询时检查 revocation，但 ledger 层面无保障"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0047"
  char_offset_start: 4641
  char_offset_end: 4841
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/evidence/write_protocol.py:169-207`
    - **行为**: `retract_by_asrt()` 仅记录 Revokes 关系，不检查/标记依赖的派生事实
    - **影响**: 被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性
    - **注意**: 证据树查询时检查 revocation，但 ledger 层面无保障
```

**Summary**: `Document(title=1c1cbf45fa645003) -- document:mentions --> string=证据树查询时检查 revocation，但 ledger 层面无保障`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`1c1cbf45fa645003` is an internal identifier/hash, not a grounded document title; the note about ledger-level guarantees is supported but misbound."
```

---

### Draft 021

```yaml
draft_index: 20
entity_type: "Module"
entity_identity:
  module_name: "find_revoker"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "在 BEGIN IMMEDIATE 事务外执行"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0049"
  char_offset_start: 4878
  char_offset_end: 5011
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/evidence/write_protocol.py:181`
    - **代码**: `find_revoker()` 在 `BEGIN IMMEDIATE` 事务外执行
    - **风险**: 两个线程同时判断"未撤回" → 重复撤回记录
```

**Summary**: `Module(module_name=find_revoker) -- module:description --> string=在 BEGIN IMMEDIATE 事务外执行`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`find_revoker` is a function name, not the intended `Module` subject type in this schema even though the transaction-ordering statement is supported."
```

---

### Draft 022

```yaml
draft_index: 21
entity_type: "Module"
entity_identity:
  module_name: "find_revoker"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "两个线程同时判断未撤回 → 重复撤回记录"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0049"
  char_offset_start: 4878
  char_offset_end: 5011
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/evidence/write_protocol.py:181`
    - **代码**: `find_revoker()` 在 `BEGIN IMMEDIATE` 事务外执行
    - **风险**: 两个线程同时判断"未撤回" → 重复撤回记录
```

**Summary**: `Module(module_name=find_revoker) -- module:description --> string=两个线程同时判断未撤回 → 重复撤回记录`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`find_revoker` is a function name, not the intended `Module` subject type; the race-condition statement is supported but routed too broadly."
```

---

### Draft 023

```yaml
draft_index: 22
entity_type: "Document"
entity_identity:
  title: "core/store/_candidate_evidence_tree.py"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "递归构建过程中回调读取 ledger，无原子快照"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0058"
  char_offset_start: 5538
  char_offset_end: 5653
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/_candidate_evidence_tree.py`
    - **行为**: 递归构建过程中回调读取 ledger，无原子快照
    - **影响**: 并发修改下树的不同分支反映不同时刻状态
```

**Summary**: `Document(title=core/store/_candidate_evidence_tree.py) -- document:mentions --> string=递归构建过程中回调读取 ledger，无原子快照`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`core/store/_candidate_evidence_tree.py` is a code file path, not a grounded `Document` subject type in this schema."
```

---

### Draft 024

```yaml
draft_index: 23
entity_type: "Document"
entity_identity:
  title: "core/store/_candidate_evidence_tree.py"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "并发修改下树的不同分支反映不同时刻状态"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0058"
  char_offset_start: 5538
  char_offset_end: 5653
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `core/store/_candidate_evidence_tree.py`
    - **行为**: 递归构建过程中回调读取 ledger，无原子快照
    - **影响**: 并发修改下树的不同分支反映不同时刻状态
```

**Summary**: `Document(title=core/store/_candidate_evidence_tree.py) -- document:mentions --> string=并发修改下树的不同分支反映不同时刻状态`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`core/store/_candidate_evidence_tree.py` is a code file path rather than the intended `Document` subject type, even though the impact statement is supported."
```

---

### Draft 025

```yaml
draft_index: 24
entity_type: "Document"
entity_identity:
  title: "service/_common.py"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "完整异常含路径/SQL/schema"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0060"
  char_offset_start: 5678
  char_offset_end: 5797
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `service/_common.py`
    - **代码**: `details = {"message": str(exc)}` — 完整异常含路径/SQL/schema
    - **影响**: 向客户端暴露服务器内部状态
```

**Summary**: `Document(title=service/_common.py) -- document:mentions --> string=完整异常含路径/SQL/schema`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`service/_common.py` is a code file path, not the intended `Document` subject type in this schema even though the exception-detail statement is supported."
```

---

### Draft 026

```yaml
draft_index: 25
entity_type: "Document"
entity_identity:
  title: "service/_common.py"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "向客户端暴露服务器内部状态"
confidence: 0.9
note: null

provenance:
  source_document_id: "1c1cbf45fa645003"
  segment_id: "1c1cbf45_0060"
  char_offset_start: 5678
  char_offset_end: 5797
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **位置**: `service/_common.py`
    - **代码**: `details = {"message": str(exc)}` — 完整异常含路径/SQL/schema
    - **影响**: 向客户端暴露服务器内部状态
```

**Summary**: `Document(title=service/_common.py) -- document:mentions --> string=向客户端暴露服务器内部状态`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`service/_common.py` is a code file path rather than a grounded `Document` subject type; the client-exposure statement is supported but misbound."
```

---
