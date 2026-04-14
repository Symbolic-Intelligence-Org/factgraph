# Blueprint: Document Extraction HTTP API

- Status: implemented with deviations
- Created: 2026-04-14
- Kind: **service layer endpoint** (HTTP API for document extraction)
- Trigger: 需要给前端(Streamlit/React)提供 HTTP 接口来调用 `extract_document()`;Python 函数 API 不能直接暴露给前端
- Related Modules:
  - `src/factpy_kernel/service/app_v1.py` (新 endpoint)
  - `src/factpy_kernel/service/extraction_v1.py` (**新文件** — endpoint handler)
  - `src/factpy_kernel/agent/extraction/api.py` (已有 `extract_document()`)
- Audit Log:
  - [2026-04-14_document-extraction-http-api.audit.md](./2026-04-14_document-extraction-http-api.audit.md)

---

## 0. Scope

在现有 FastAPI `app_v1.py` 上新增一个 sync extraction endpoint。前端上传文档 + schema 配置,后端调 `extract_document()`,返回结构化结果。

**做什么**:
- `app_v1.py`: 新增 `POST /v1/extraction/documents` route — 负责接收 multipart(`file` + `options` str),解析 JSON(`json.loads`),拦截 JSON 格式错误(422)
- `extraction_v1.py`: 新文件 — endpoint handler,接收已解析的 `file_bytes: bytes` + `doc_name: str` + `options: dict`,调用 `extract_document_from_ir()`,拦截业务校验错误(422) + pipeline 错误(500)
- `extraction/api.py`: 重构为共享 helper `_run_extraction_pipeline()` + 新增 `extract_document_from_ir()`
- `pyproject.toml`: service extras 追加 `python-multipart>=0.0.5`
- 测试

**不做什么**:
- 不做前端 demo (下一个蓝图)
- 不做 async job system
- 不做 schema class 热注册(用 `schema_ir` 直接传)
- 不改 `extract_document()` 的**公开签名和行为** — 但会重构其内部实现为共享 helper `_run_extraction_pipeline()`,并新增 `extract_document_from_ir()` 公开函数(见 §3.2 + HA-08)

---

## 1. HTTP Contract

### `POST /v1/extraction/documents`

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | UploadFile | ✅ | 文档文件 (PDF/DOCX/MD/TXT) |
| `options` | str (JSON) | ✅ | 提取配置 JSON string |

**`options` JSON schema**:

```json
{
  "schema_ir": { ... },                          // 必填: 编译后的 schema IR (和 registry/schema/read 的输出格式一致)
  "model": "mistral/mistral-small-latest",       // 可选: 覆盖默认模型
  "entity_descriptions": {"Module": "..."},      // 可选: entity type descriptions
  "enable_gleaning": true,                       // 可选: 默认 true
  "enable_alias_merge": true,                    // 可选: 默认 true
  "max_batch_size": 1000,                        // 可选: 默认 1000
  "require_source": true                         // 可选: 默认 true
}
```

**Response 200** (和 `ok_response` shape 完全一致 — 始终带 `errors: []` 和 `meta: {}`):

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "doc_name": "readme.pdf",
    "doc_id": "a1b2c3d4",
    "model": "mistral/mistral-small-latest",
    "staging_segments": 6,
    "gleaning_segments_reexamined": 2,
    "entities": [
      {"entity_type": "Module", "identity": {"name": "ingest"}, "fact_count": 3}
    ],
    "facts": [
      {
        "entity_type": "Module",
        "entity_identity": {"name": "ingest"},
        "pred_id": "module:owner",
        "field_values": [["string", "data-infra team"]],
        "confidence": 0.9
      }
    ],
    "metrics": { ... },
    "merge_events": [ ... ]
  }
}
```

**Error Responses**:

错误格式统一使用现有 `{kind, path, details}` shape(和 `_common.exception_to_error` 一致):

| Status | Condition | Error shape |
|---|---|---|
| 422 | 缺 `file` 或 `options`(FastAPI 原生参数校验) | FastAPI 默认 422 body — **不拦截,不自定义** |
| 422 | `options` 不是合法 JSON(route 层拦截) | `{"ok": false, "errors": [{"kind": "validation", "path": "options", "details": {"message": "options is not valid JSON: ..."}}], "meta": {}}` |
| 422 | `options` 合法 JSON 但缺 `schema_ir`(handler 层拦截) | `{"ok": false, "errors": [{"kind": "validation", "path": "options.schema_ir", "details": {"message": "options.schema_ir is required"}}], "meta": {}}` |
| 500 | `ExtractionDocumentError` | `{"ok": false, "errors": [{"kind": "extraction", "path": "$", "details": {"stage": "staging\|extraction\|resolution", "message": "..."}}], "meta": {}}` |

注意: 缺 `file`/`options` 走 **FastAPI 原生 422**（`File(...)` / `Form(...)` 是 required），不手动拦截。只有进入 handler 后的业务校验走自定义 error_response。

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| HA-01 | **HTTP contract 不暴露 `schema_classes`**,只接受 `schema_ir` (编译后 JSON) | `schema_classes` 是 Python 进程内接口,不可序列化;前端传 `schema_ir` 与现有 `/v1/registry/schema/read` 输出对齐 |
| HA-02 | Sync endpoint,不做 async job | 当前 benchmark 和 product API 都是同步链路;async 等遇到长文档超时再单开蓝图 |
| HA-03 | Response 格式和现有 service 一致: `{"ok": true/false, "errors": [...]}` + `ok_response`/`error_response` | 和 `_common.py` 的 `ok_response`/`error_response` 完全一致 |
| HA-04 | Error shape 统一用 `{kind, path, details}` — `ExtractionDocumentError.stage` 放进 `details.stage` | 和 `exception_to_error()` 的现有格式对齐;前端只需解析一种 error shape |
| HA-05 | 缺 `file`/`options` 走 **FastAPI 原生 422**(不手动拦截),业务校验走自定义 `error_response` | 不和 framework 抢参数校验;进入 handler 后的错误才是我们的 |
| HA-06 | Auth: 和其他 endpoint 一样走 `require_api_key` middleware | 不做额外的 auth 差异化 |
| HA-07 | `FactDraftSpec` 序列化: `entity_identity` 展开为 `dict`,`field_values` 展开为 `list[list]` | JSON-friendly;前端不需要理解 tuple |
| HA-08 | `extract_document_from_ir()` 和 `extract_document()` **共享一个私有 helper** `_run_extraction_pipeline()`,不复制 pipeline 逻辑 | 避免双维护;entity_descriptions / model 优先级 / gleaning 等演进只改一处 |
| HA-09 | `pyproject.toml` service extras 加 `python-multipart` | FastAPI multipart 上传依赖;clean env 下不装会 runtime error |

---

## 3. Implementation

### 3.1 `extraction_v1.py` — 新文件 (~80 行)

Endpoint handler — 显式返回 `JSONResponse` 并设置 HTTP status code:

```python
from fastapi.responses import JSONResponse

def extract_document_endpoint(file_bytes: bytes, doc_name: str, options: dict) -> JSONResponse:
    """Handle POST /v1/extraction/documents."""
    schema_ir = options.get("schema_ir")
    if not schema_ir:
        return JSONResponse(
            status_code=422,
            content=error_response([{
                "kind": "validation",
                "path": "options.schema_ir",
                "details": {"message": "options.schema_ir is required"},
            }]),
        )
    
    try:
        result = extract_document_from_ir(
            content=file_bytes,
            doc_name=doc_name,
            schema_ir=schema_ir,
            model=options.get("model"),
            entity_descriptions=options.get("entity_descriptions"),
            enable_gleaning=options.get("enable_gleaning", True),
            enable_alias_merge=options.get("enable_alias_merge", True),
            max_batch_size=options.get("max_batch_size", 1000),
            require_source=options.get("require_source", True),
        )
    except ExtractionDocumentError as exc:
        return JSONResponse(
            status_code=500,
            content=error_response([{
                "kind": "extraction",
                "path": "$",
                "details": {"stage": exc.stage, "message": str(exc)},
            }]),
        )
    
    return JSONResponse(
        status_code=200,
        content=ok_response(result=serialize_extraction_result(result)),
    )
```

**Status code 责任在 handler 层**(`extraction_v1.py`),不在 `_common.py`。`ok_response`/`error_response` 只负责 body shape。

### 3.2 `extraction/api.py` — 重构为共享 helper + 新增 `extract_document_from_ir()`

将现有 `extract_document()` 的 pipeline 逻辑抽到 `_run_extraction_pipeline(schema_ir, content, doc_name, **kwargs)` 私有函数:

```python
def _run_extraction_pipeline(
    *,
    schema_ir: dict[str, Any],
    content: bytes,
    doc_name: str,
    model: str | None = None,
    # ... 所有其他 kwargs ...
) -> ExtractionDocumentResult:
    """Shared pipeline: staging → extraction → resolution."""
    # (现有的全部 pipeline 逻辑移到这里)

def extract_document(*, content, doc_name, schema_classes, **kwargs):
    """Public API — accepts Python Entity classes."""
    schema_ir = compile_schema_from_classes(schema_classes)
    return _run_extraction_pipeline(schema_ir=schema_ir, content=content, doc_name=doc_name, **kwargs)

def extract_document_from_ir(*, content, doc_name, schema_ir, **kwargs):
    """Public API — accepts pre-compiled schema_ir (for HTTP endpoint)."""
    return _run_extraction_pipeline(schema_ir=schema_ir, content=content, doc_name=doc_name, **kwargs)
```

**零逻辑重复**: 两个公开函数都委托给同一个 `_run_extraction_pipeline`。

### 3.3 `app_v1.py` — 新增 route (+15 行)

```python
import json
from fastapi import File, Form, UploadFile
from fastapi.responses import JSONResponse
from factpy_kernel.service.extraction_v1 import extract_document_endpoint
from factpy_kernel.service._common import error_response

@app.post("/v1/extraction/documents", dependencies=AUTH_DEPENDENCIES)
async def post_extract_document(
    file: UploadFile = File(...),
    options: str = Form(...),
):
    # Route 层负责 JSON 解析 — 失败时显式返回 422
    try:
        options_dict = json.loads(options)
    except (json.JSONDecodeError, TypeError) as exc:
        return JSONResponse(
            status_code=422,
            content=error_response([{
                "kind": "validation",
                "path": "options",
                "details": {"message": f"options is not valid JSON: {exc}"},
            }]),
        )
    
    file_bytes = await file.read()
    return extract_document_endpoint(
        file_bytes=file_bytes,
        doc_name=file.filename or "unknown",
        options=options_dict,
    )
```

**JSON 解析责任明确在 route 层 (`app_v1.py`)**,不在 handler 层。`extract_document_endpoint` 接收已解析的 `dict`,不做 JSON parsing。

### 3.4 `pyproject.toml` — 增量修改 service extras

当前 `service` extra (line 14):
```toml
service = ["fastapi>=0.110,<1", "uvicorn>=0.29,<1", "httpx>=0.27,<1"]
```

**只追加** `python-multipart>=0.0.5`,保留现有项和版本约束不变:
```toml
service = ["fastapi>=0.110,<1", "uvicorn>=0.29,<1", "httpx>=0.27,<1", "python-multipart>=0.0.5"]
```

### 3.5 测试

- `test_extraction_http_api.py` (新文件):
  - `test_extract_document_endpoint_success` — mock LLM,验证 200 + result 结构
  - `test_extract_document_endpoint_invalid_json_options` — 验证 options 非法 JSON → 422 + `path=options`
  - `test_extract_document_endpoint_missing_schema_ir` — 验证 options 合法但缺 schema_ir → 422 + `path=options.schema_ir`
  - `test_extract_document_endpoint_staging_failure` — 验证 500 + `details.stage`
  - `test_extract_document_endpoint_requires_auth` — 验证 401

---

## 4. Non-goals

- 不做前端 demo
- 不做 async extraction job queue
- 不做 websocket streaming
- 不做 schema class 动态注册
- 不做文件大小限制(留给部署层 nginx/gateway)

---

## 5. Acceptance Criteria

1. `POST /v1/extraction/documents` with file + `{"schema_ir": ...}` → 200 + entities + facts
2. 缺 `schema_ir` → 422
3. 文档 staging 失败 → 500 + `"stage": "staging"`
4. Auth 拦截 → 401
5. 和 GPT-4.1 / Mistral Small 都能跑通
6. Regression: 1015+ tests green

---

## 6. Outcome / Deviations

### Result
- **Regression**: 1020 passed, 3 skipped
- **Implementation**: `extraction_v1.py` (handler) + `app_v1.py` (route) + `api.py` (重构为共享 helper) + `__init__.py` (导出) + `pyproject.toml` (python-multipart)
- **Contract tests**: 200/422/500/401 全覆盖

### Deviation
- **未执行 real-provider HTTP smoke**(GPT-4.1 / Mistral 通过 HTTP endpoint 做 multipart 请求)
- Provider 行为已由 Python extraction benchmark 充分验证(Mistral 10/10 F1=78%, GPT-4.1 10/10 F1=68%)
- HTTP wrapper 由 contract tests 覆盖(mock LLM + FastAPI TestClient)
- 如果下一步接前端,建议补两次最小 smoke(GPT-4.1 + Mistral 各一次 multipart 请求)

### Final status: **implemented with deviations**
