# Blueprint: Document Extraction Streamlit Demo

- Status: abandoned
- Created: 2026-04-14
- Kind: **demo / validation** (验通 HTTP API 产品接缝,不是产品前端)
- Trigger: `POST /v1/extraction/documents` 已实现并通过 contract tests;需要一个可交互的 demo 验证端到端链路
- Related Modules:
  - `demo/extraction_demo.py` (**新文件**)
  - `POST /v1/extraction/documents` (已实现)
- Audit Log:
  - [2026-04-14_document-extraction-streamlit-demo.audit.md](./2026-04-14_document-extraction-streamlit-demo.audit.md)

---

## 0. Scope

单页 Streamlit app,通过 HTTP 调用 `POST /v1/extraction/documents`,上传文档 + 配置 schema,展示提取结果。

**做什么**:
- `demo/extraction_demo.py`: 单文件 Streamlit app (~150 行)
- 上传文档 (PDF/DOCX/MD/TXT)
- 提供 schema_ir (textarea 粘贴 JSON 或 file upload)
- 选择模型 (固定列表: Mistral Small / GPT-4.1 / GPT-4.1 Mini)
- 可选: enable_gleaning / enable_alias_merge toggle
- 展示: entities 表格 + facts 列表 + metrics 摘要 + errors 透传
- `demo/README.md`: 启动说明

**不做什么**:
- 不做登录态 / auth UI (demo 直接传 API key header)
- 不做 async job / progress bar
- 不做 schema builder (用户自己准备 schema_ir JSON)
- 不做 polished 产品 UI (functional demo, not production frontend)
- 不做复杂状态管理 / session persistence
- 不直接 import `extract_document()` — **只调 HTTP API**

---

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| SD-01 | Demo 只通过 HTTP 调 `/v1/extraction/documents`,不直接 import Python API | 验通产品接缝;demo 和 backend 可以跑在不同进程 |
| SD-02 | `schema_ir` 输入方式: textarea 粘贴 JSON **或** file upload,二选一 | MVP 最小;不做 schema builder |
| SD-03 | API base URL 从 env var `FACTPY_API_BASE` 读取,默认 `http://localhost:8000` | 本地开发友好;部署时可配 |
| SD-04 | API key 从 env var `FACTPY_API_KEY` 读取,放进 request header `X-FactPy-API-Key` | 和现有 `require_api_key` middleware 对齐;不在 UI 上暴露 key |
| SD-05 | 错误展示直接透传 `{kind, path, details}` JSON,不做美化 | 开发者 demo;能看到完整 error shape 比美观更有用 |
| SD-06 | 不做 `pip install streamlit` 到 pyproject.toml | demo 是独立运行的,不是 factpy_kernel 的 dependency |

---

## 2. UI Layout

```
┌─────────────────────────────────────────────┐
│  📄 FactPy Document Extraction Demo         │
├─────────────────────────────────────────────┤
│                                             │
│  ── Input ──                                │
│  [Upload Document]  📄 readme.pdf           │
│                                             │
│  Schema IR:                                 │
│  ○ Paste JSON  ○ Upload .json file          │
│  ┌─────────────────────────────────┐        │
│  │ {"entities": [...], ...}        │        │
│  └─────────────────────────────────┘        │
│                                             │
│  Model: [mistral/mistral-small-latest ▾]    │
│  ☑ Enable Gleaning  ☑ Enable Alias Merge    │
│                                             │
│  [🚀 Extract]                               │
│                                             │
├─────────────────────────────────────────────┤
│  ── Results ──                              │
│                                             │
│  Status: ✅ 200 OK  |  Model: mistral/...  │
│  ⏱ 11.5s  |  📄 6 segments  |  🔄 2 glean │
│                                             │
│  Entities (4):                              │
│  ┌──────────┬───────────┬───────────┐       │
│  │ Type     │ Identity  │ Facts     │       │
│  ├──────────┼───────────┼───────────┤       │
│  │ Module   │ ingest    │ 3         │       │
│  │ Module   │ resolve   │ 2         │       │
│  │ ...      │           │           │       │
│  └──────────┴───────────┴───────────┘       │
│                                             │
│  Facts (9):                                 │
│  ┌──────────┬──────────┬────────────┐       │
│  │ Entity   │ Predicate│ Value      │       │
│  ├──────────┼──────────┼────────────┤       │
│  │ ingest   │ owner    │ data-infra │       │
│  │ ...      │          │            │       │
│  └──────────┴──────────┴────────────┘       │
│                                             │
│  Metrics:                                   │
│  proposals=8 valid=7 rejections=1 dur=11s   │
│                                             │
│  (Error 时: 红色 JSON block 透传 errors)    │
└─────────────────────────────────────────────┘
```

---

## 3. Implementation

### 3.1 `demo/extraction_demo.py` (~150 行)

```python
import streamlit as st
import requests
import json
import os

API_BASE = os.environ.get("FACTPY_API_BASE", "http://localhost:8000")
API_KEY = os.environ.get("FACTPY_API_KEY", "")

st.title("📄 FactPy Document Extraction Demo")

# ── Input ──
uploaded_file = st.file_uploader("Upload document", type=["pdf", "docx", "md", "txt"])

schema_mode = st.radio("Schema IR input", ["Paste JSON", "Upload .json file"])
if schema_mode == "Paste JSON":
    schema_text = st.text_area("Schema IR (JSON)", height=150)
else:
    schema_file = st.file_uploader("Upload schema_ir.json", type=["json"])
    schema_text = schema_file.read().decode() if schema_file else ""

model = st.selectbox("Model", [
    "mistral/mistral-small-latest",
    "gpt-4.1",
    "gpt-4.1-mini",
])

col1, col2 = st.columns(2)
enable_gleaning = col1.checkbox("Enable Gleaning", value=True)
enable_alias_merge = col2.checkbox("Enable Alias Merge", value=True)

if st.button("🚀 Extract"):
    # Validate inputs
    if not uploaded_file:
        st.error("Please upload a document.")
    elif not schema_text.strip():
        st.error("Please provide a Schema IR.")
    else:
        try:
            schema_ir = json.loads(schema_text)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
            schema_ir = None

        if schema_ir is not None:  # {} is valid JSON — let backend validate and return 422 if empty
            options = json.dumps({
                "schema_ir": schema_ir,
                "model": model,
                "enable_gleaning": enable_gleaning,
                "enable_alias_merge": enable_alias_merge,
            })

            with st.spinner("Extracting..."):
                resp = requests.post(
                    f"{API_BASE}/v1/extraction/documents",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                    data={"options": options},
                    headers={"X-FactPy-API-Key": API_KEY} if API_KEY else {},
                )

            data = resp.json()
            if resp.status_code == 200 and data.get("ok") is True:
                result = data.get("result", {})
                
                # Status bar
                st.success(f"✅ {resp.status_code} | Model: {result.get('model')} | "
                          f"⏱ {result.get('metrics', {}).get('batch_duration_ms', 0)}ms | "
                          f"📄 {result.get('staging_segments')} segments | "
                          f"🔄 {result.get('gleaning_segments_reexamined')} gleaned")

                # Entities table
                st.subheader(f"Entities ({len(result.get('entities', []))})")
                st.table(result.get("entities", []))

                # Facts table — show full field_values, not just first slot
                st.subheader(f"Facts ({len(result.get('facts', []))})")
                st.table([
                    {
                        "entity": f.get("entity_type"),
                        "identity": str(f.get("entity_identity")),
                        "predicate": f.get("pred_id"),
                        "field_values": json.dumps(f.get("field_values", []), ensure_ascii=False),
                    }
                    for f in result.get("facts", [])
                ])

                # Metrics
                st.subheader("Metrics")
                st.json(result.get("metrics", {}))
            else:
                st.error(f"❌ {resp.status_code} | ok={data.get('ok')}")
                st.json(data)
```

### 3.2 `demo/README.md`

```markdown
# Extraction Demo

## Prerequisites
pip install streamlit requests

## Run
# Terminal 1: Start backend (FACTPY_KERNEL_API_KEYS configures server-side allowed keys)
FACTPY_KERNEL_API_KEYS=dev uvicorn factpy_kernel.service.app_v1:app --port 8000

# Terminal 2: Start demo (FACTPY_API_KEY is the client-side key sent in X-FactPy-API-Key header)
FACTPY_API_BASE=http://localhost:8000 FACTPY_API_KEY=dev streamlit run demo/extraction_demo.py
```

### 3.3 内置示例 schema_ir

在 `demo/` 下放一个 `example_schema_ir.json`:
```json
{
  "entities": [...],
  "predicates": [...]
}
```
用户可以直接 upload 它,不需要自己写。从 `compile_schema_from_classes([Person, Location, MiscEntity])` 导出一次即可。

---

## 4. Acceptance Criteria

1. `streamlit run demo/extraction_demo.py` 启动无报错
2. 上传文档 + 粘贴 schema_ir + 点 Extract → 看到 entities + facts + metrics
3. 缺 schema_ir → 页面显示错误(不 crash)
4. Backend 返回 422/500 → 页面显示红色 error JSON
5. Mistral Small + GPT-4.1 都能跑通

---

## 5. Outcome / Deviations

**Abandoned on 2026-04-14.** Streamlit path was implemented (`demo/extraction_demo.py` + `demo/example_schema_ir.json` + `demo/README.md`) and proved the HTTP contract works end-to-end, but in practice it was blocked by auth friction (Streamlit process missing `FACTPY_API_KEY` env var on every demo run) and produced a worse feedback loop than a notebook that calls `extract_document()` directly.

The demo value was redirected into `examples/09_dora_document_extraction.ipynb` (notebook, in-process Python API) and `examples/dora_pdf_extract.py` (CLI for real PDFs). Streamlit-specific files (`demo/extraction_demo.py`, `demo/example_schema_ir.json`, `demo/README.md`) and the ad-hoc `demo/` directory were removed. The HTTP API itself (the real product contract this blueprint was meant to validate) is validated by `tests/test_extraction_http_api.py`.

No code or docs remain referencing the Streamlit demo path after archival.
