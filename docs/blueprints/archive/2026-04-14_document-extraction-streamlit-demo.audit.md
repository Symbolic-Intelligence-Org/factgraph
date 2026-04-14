# Audit Log: Document Extraction Streamlit Demo

## 2026-04-14 — draft

### Trigger

HTTP API (`POST /v1/extraction/documents`) 已实现。需要一个可交互的 demo 验证端到端链路(HTTP API → real LLM → structured results)。

### Key decisions

- Demo 只调 HTTP API,不直接 import Python API (SD-01)
- schema_ir 通过 textarea/file upload,不做 builder (SD-02)
- API base URL + API key 从 env var 读取 (SD-03/SD-04)

### Status transitions

- 2026-04-14 — **draft v1** (6 SD decisions)
- 2026-04-14 — **scope check v1**: 2× P1 + 2× P2:
  1. P1: auth header 写成 `X-API-Key`,后端是 `X-FactPy-API-Key` → 全部统一
  2. P1: README backend 启动用错 env var → 改为 `FACTPY_KERNEL_API_KEYS`
  3. P2: "自定义模型"和固定下拉矛盾 → 收紧为固定列表
  4. P2: facts 表只取 field_values[0] 丢信息 → 改为 JSON 完整展示
- 2026-04-14 — **draft v2** (6 SD decisions, all 4 findings addressed)
- 2026-04-14 — **scope check v2**: 1× P1 + 1× P2:
  1. P1: 200 + ok:false 误判成功 → 成功判定改为 `status_code == 200 且 body.ok is True`
  2. P2: 空 schema {} 静默 no-op → 改为 `schema_ir is not None`,让 backend 返回 422
- 2026-04-14 — **draft v3** (6 SD decisions, all findings addressed)
- 2026-04-14 — **scope check v3**: no new findings
- 2026-04-14 — **scoped** (6 SD decisions frozen, ready for implementation)
- 2026-04-14 — **implementing**: Streamlit app shipped (`demo/extraction_demo.py` ~170 lines + `demo/example_schema_ir.json` + `demo/README.md`) per SD-01..SD-06; HTTP contract end-to-end validated against real Mistral extraction
- 2026-04-14 — **abandoned**: auth friction (API key env var has to be set in both server and client Streamlit process; repeated `{"detail":"Invalid or missing API key"}`) made the Streamlit demo a worse feedback loop than a direct `extract_document()` notebook. User explicitly redirected demo value to `examples/09_dora_document_extraction.ipynb` (notebook, in-process) + `examples/dora_pdf_extract.py` (CLI). Streamlit artefacts removed. HTTP contract coverage shifts to `tests/test_extraction_http_api.py`.
