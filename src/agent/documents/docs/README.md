# Agent Documents 文档

本目录记录 `src/agent/documents` 的当前实现口径，覆盖 Layer 4C1 的确定性 document staging、Layer 4C2 的 document draft bundle review/approval carrier，以及 Layer 4C3-c 引入的 merged provenance carrier。

## Scope

- `DocumentSource` / `DocumentSegment` / `StagingResult` / `StagingError`
- `ExtractionProvenance`（含 `merged_from` / `all_sources()` / `source_segment_ids()` / `to_factgraph_provenance_refs()`）
- `compute_structural_clarity()` / `detect_section_label()`
- `DocumentParser` Protocol / `ParseError`
- `PlainTextParser` / `PythonDocxParser` / `PyMuPDFParser`
- `DocumentStaging`
- `FactDraftSpec` / `DraftBundle` / `BundleReviewAction` / `BundleCommitResult`
- `BundleManager`

## Responsibilities

- 将单文档输入转为可审计的确定性 segment 列表
- 为每个 segment 产出 `doc_id / segment_id / offsets / raw_text / structural_clarity / pattern_type`
- 根据 optional dependency 可用性做 parser 注册
- 对缺依赖格式返回 `StagingError(error_kind="unsupported_format")`
- 将 `FactDraftSpec` 注册为 managed `FactDraft`，并规范化 document provenance 为 `source/source_loc`
- 支持将 merged provenance 规范化为单条 assertion 可承载的 `source/source_loc` 字符串，同时保留多 segment 来源集合
- 可按需将 `ExtractionProvenance` 转为 `tuple[ProvenanceRefV1, ...]`，供 FactGraph Scenario / Run / Explain 的结构化来源字段使用；merged segment 逐条展开、保留既有 first-seen 顺序
- 提供 bundle-level review/approval carrier，但最终 commit 仍复用 Layer 3A per-item write path
- 为 document fact draft 提供 checkpoint 可恢复的 `DraftBundle` 生命周期管理

## FactGraph-neutral provenance bridge

`ExtractionProvenance.to_factgraph_provenance_refs()` 是一个惰性、只读的
转换入口。每个 contributing segment 变为一条
`ProvenanceRefV1(origin_role="agent_extraction")`：

- `source_ref` 是由 document/segment ID 派生的稳定 opaque hash，不暴露文档名或原始 ID；
- locator 只描述 page/character range，不携带文本；
- `content_digest` 是 `raw_text` UTF-8 的 SHA-256 token，供外部持有源内容的一方进行一致性比对；
- 输出不包含 `raw_text`、SourceRecord、ACL、tenant、admission decision 或授权信息。

这不会修改 `ExtractionProvenance`、draft checkpoint，或现有 durable write
的 `source/source_loc` meta。后者仍是 Agent Layer 4C 的兼容镜像；将 bridge
结果纳入 Scenario/Explain 是调用方显式选择的行为。

## Non-responsibilities

- 不做 LLM 调用
- 不产出 `RuleDraft`
- 不写 ledger
- 不提供 SourceRecord / 来源注册 / ACL / admission service
- 不做 bundle 原子事务、OCR、跨文档去重、审批 UI

## Determinism

- 同一 `(content, parser_version)` 输入必须产出相同 `DocumentSegment` 序列
- `staged_at` / `ingested_at` 仅作时间戳，不计入结构等价判断
- `parser_version` 是确定性合同的一部分

## Limitations

- PDF parser 只有在 `pymupdf`/`fitz` 与 `pymupdf4llm` 都可用时才注册
- 扫描件 PDF/OCR 不支持
- DOCX 表格当前做扁平化行文本
- structural_clarity 是启发式粗筛，不是语义理解
- `ExtractionProvenance.raw_text` 会进入 draft checkpoint；长 segment 或大规模 merged provenance 都可能膨胀 checkpoint 文件
- `BundleManager.create_bundle()` 需要 `session_id` 以注册 managed drafts；这是内部实现级接口，不暴露为 kernel contract
- bundle review 使用 `approved_draft_ids` 跟踪通过项；approved drafts 本身保持 `pending`
- merged provenance 写入 draft 时使用 primary segment 生成 `source` 前缀，并把全部贡献 segment 列表写入 `source_loc`
