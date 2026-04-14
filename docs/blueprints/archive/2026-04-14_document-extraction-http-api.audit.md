# Audit Log: Document Extraction HTTP API

## 2026-04-14 — draft

### Trigger

需要给前端提供 HTTP 接口调用 extraction pipeline。当前只有 Python 函数 API (`extract_document()`)。

### Key design decisions (from reviewer)

- HTTP contract 不暴露 `schema_classes`,只接受 `schema_ir` (编译后 JSON)
- Sync endpoint,不做 async job system
- Error 映射保留 `ExtractionDocumentError.stage`
- `extract_document()` 需要新增一个 `extract_document_from_ir()` 变体接受 schema_ir 而非 schema_classes

### Status transitions

- 2026-04-14 — **draft v1** (7 HA decisions)
- 2026-04-14 — **scope check v1**: 2× P1 + 2× P2:
  1. P1: `python-multipart` 未声明 → HA-09 加依赖
  2. P1: error shape `{kind, message}` 和现有 `{kind, path, details}` 不一致 → HA-04 统一
  3. P2: 400/422 和 FastAPI 原生校验冲突 → HA-05 缺 file/options 走 FastAPI 原生 422
  4. P2: `extract_document_from_ir()` 复制 pipeline → HA-08 共享私有 helper
- 2026-04-14 — **draft v2** (9 HA decisions, all 4 findings addressed)
- 2026-04-14 — **scope check v2**: 2× P1 + 1× P2:
  1. P1: handler 返回 error_response dict 不设 HTTP status → 显式 JSONResponse(status_code=422/500)
  2. P1: "不改 extract_document() 内部" 和 §3.2 共享 helper 矛盾 → 改为"不改公开签名和行为"
  3. P2: pyproject.toml 草图写成替换 → 改为增量追加 python-multipart
- 2026-04-14 — **draft v3** (9 HA decisions, all findings addressed)
- 2026-04-14 — **scope check v3**: 1× P1 + 1× P2:
  1. P1: invalid JSON → 422 路径未冻结到具体实现层 → route 层负责 json.loads + JSONDecodeError → 422
  2. P2: response 示例缺 `errors: []` / `meta: {}` → 全部示例对齐 ok_response/error_response shape
- 2026-04-14 — **draft v4** (9 HA decisions, all findings addressed)
- 2026-04-14 — **scope check v4**: 2× P2:
  1. 422 contract 两种错误合并成一行 → 拆成 `path=options` (JSON 格式) + `path=options.schema_ir` (缺字段) 两行
  2. scope 顶部 handler 职责描述是旧版 → 更新为 route 层(multipart+JSON解析) + handler 层(业务校验+pipeline调用) 分工
- 2026-04-14 — **draft v5** (9 HA decisions, all findings addressed)
- 2026-04-14 — **scope check v5**: no new findings
- 2026-04-14 — **scoped** (9 HA decisions frozen, all contracts consistent)
- 2026-04-14 — **implemented with deviations** (1020 tests green, contract tests pass, deviation: no real-provider HTTP smoke)
