# Audit Log: Agent Layer 4C1 — Deterministic Document Staging

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.4 (W4 Stage 1 保持确定性) + 用户指导（4C 拆成 4C1/4C2/4C3 三阶段，先做 4C1）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4C1-01 | Stage 1 只做确定性分段与 provenance，不做 LLM 提取 | 用户 2026-04-10 指导 + delta D-09 |
| L4C1-02 | v1 只产出文档 segment DTO，不直接产出 FactDraft | 用户 2026-04-10 指导 |
| L4C1-03 | v1 只支持单文档输入，不做跨文档去重/消歧 | 用户 2026-04-10 指导 |
| L4C1-04 | OCR、规则提取、多文档 bundle 明确排除 | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4C1-05 | structural_clarity 用正则+关键词启发式，不用 LLM / NLP 模型 | 部署简单；4C1 只是粗筛，4C3 LLM 精炼才决定最终质量 |
| L4C1-06 | 4C1 用 PyMuPDF，4C3 再引入 Docling | PyMuPDF 对原生 PDF 已够用；Docling 需要 GPU，留给复杂文档/表格场景 |
| L4C1-07 | DocumentStaging 不依赖 AgentSession | 纯 document processing 层；便于独立测试和复用 |
| L4C1-08 | stage_document 不 checkpoint、不写 ledger | staging 是纯函数输出；持久化是 4C2 的事 |
| L4C1-09 | parser 通过 Protocol + 注册列表插件化 | 便于后续扩展（HTML / Docling / OCR） |
| L4C1-10 | pymupdf/python-docx 作为 optional dependency | base agent 不强制引入重依赖 |
| L4C1-11 | parser_version 是 segment 确定性的一部分 | 升级 parser 需明确知道旧数据不再等价 |

## 2026-04-10 — 实现前收口修订 (2 处)

### 修订来源

用户 code review 发现 2 处 blocker。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4C1-12 | **冻结**：DocumentStaging 依赖感知注册；缺依赖的 parser 不注册；list_supported_document_formats 只返回可用格式；缺依赖输入返回 StagingError(unsupported_format)，不新增 error kind | 解决 optional dependency 缺失时的行为未冻结问题；避免 tool 合同歧义和测试分支爆炸 |
| L4C1-13 | optional deps 明确加入 pymupdf4llm（与实现描述对齐） | 正文依赖 pymupdf4llm 的 chunk/markdown 语义，但 optional deps 只有 pymupdf；依赖合同不一致 |

### 合同对齐验证

确认以下已实现合同在 Layer 4C1 中正确引用：
- `ReadReviewOrchestrator` 扩展模式与 Layer 4A/4B 一致 ✓
- `build_layer3a_tool_registry()` 累进扩展（31→33）✓
- 不触碰 `AgentSession` / `DraftManager` / `CandidatePayloadCache` ✓
- 不调用 `RuntimeAPI`（documents 完全与 runtime 解耦）✓

### Engine/Runtime 依赖审计

Layer 4C1 是 agent 层纯 document processing，与 runtime/engine 完全解耦：

| 依赖点 | 状态 |
|--------|------|
| RuntimeAPI | 不依赖 |
| Ledger | 不依赖 |
| SchemaIR | 不依赖 |
| AgentSession | 不依赖（orchestrator 门面层除外） |
| DraftManager | 不依赖 |
| CandidatePayloadCache | 不依赖 |

这是为什么 L4C1-07 把 DocumentStaging 抽成独立类——未来可以被其他上层模块复用，不必通过 orchestrator。
