# factpy-kernel

**Auditable reasoning framework with LLM document extraction.**

两层能力:

1. **append-only fact store + deterministic reasoning**(core + adapters to Soufflé / ProbLog / PyReason)
2. **LLM 文档抽取管道**(agent/extraction):从 PDF / DOCX / Markdown / TXT 抽结构化 entities + facts

本 README 只覆盖**如何使用**;架构原则见 [docs/architecture_principles.md](docs/architecture_principles.md),文档索引见 [docs/README.md](docs/README.md),工作流见 [AGENTS.md](AGENTS.md)。

## 三岔路:我想……

### A. 交互式体验一下 extraction

打开 notebook:

```bash
pip install -e ".[extraction,documents]"
jupyter notebook examples/09_dora_document_extraction.ipynb
```

Notebook 用内置 DORA 样本文本做 real-LLM 抽取,~1 分钟跑完。所有 notebooks 的索引见 [examples/README.md](examples/README.md)。

### B. 在我的脚本里直接调 Python API

```python
from factpy_kernel.sdk import Entity, Field, Identity
from factpy_kernel.agent.extraction import extract_document

class Module(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single")

with open("readme.md", "rb") as f:
    result = extract_document(
        content=f.read(),
        doc_name="readme.md",
        schema_classes=[Module],
        model="mistral/mistral-small-latest",
    )

for fact in result.facts:
    print(fact.entity_type, fact.entity_identity, fact.pred_id)
```

完整参数、返回值、失败诊断、已知限制:[src/factpy_kernel/agent/extraction/docs/USAGE.md](src/factpy_kernel/agent/extraction/docs/USAGE.md)。

真实 PDF 跑完整流程:`python examples/dora_pdf_extract.py path/to/your.pdf`

### C. 部署 HTTP 服务给前端/其他服务调用

```bash
pip install -e ".[service,extraction,documents]"
FACTPY_KERNEL_API_KEYS=dev \
MISTRAL_API_KEY="..." \
  uvicorn factpy_kernel.service.app_v1:app --port 8000
```

抽取端点:

```bash
curl -X POST http://localhost:8000/v1/extraction/documents \
  -H "X-FactPy-API-Key: dev" \
  -F "file=@doc.pdf" \
  -F 'options={"schema_ir":{...},"model":"mistral/mistral-small-latest"}'
```

完整 DTO 契约(请求 / 200 / 422 / 500 envelope):[src/factpy_kernel/service/docs/05_extraction.md](src/factpy_kernel/service/docs/05_extraction.md)
全部 `/v1/*` 路由总览:[src/factpy_kernel/service/docs/01_overview.md](src/factpy_kernel/service/docs/01_overview.md)

**完整 API 文档**:
- 机读契约:[docs/api/openapi.yaml](docs/api/openapi.yaml)(OpenAPI 3.0,48 个 operation,可直接喂 Swagger UI / `openapi-typescript` / Stoplight)
- 前端集成指南:[src/factpy_kernel/service/docs/06_frontend_integration.md](src/factpy_kernel/service/docs/06_frontend_integration.md)(envelope 解包、典型调用链路、状态码速查)
- 漂移守卫:`python scripts/export_openapi.py`(校验 yaml 与 live FastAPI spec 在 `(path, method)` 粒度一致)

## 安装

| 需求 | extras |
|---|---|
| 只用 core(append-only store + native rules) | `pip install -e .` |
| LLM extraction | `pip install -e ".[extraction,documents]"` |
| HTTP 服务 | `pip install -e ".[service,extraction,documents]"` |
| Langfuse observability | `pip install -e ".[observability]"` |

Python ≥ 3.10。

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `MISTRAL_API_KEY` | `*` | Mistral provider(默认推荐)。带 `mistral/` 前缀的 model 会自动走原生 SDK |
| `OPENAI_API_KEY` | `*` | OpenAI provider(GPT-4.1 / GPT-4.1-mini) |
| `FACTPY_KERNEL_API_KEYS` | 服务端必填 | 逗号分隔的 server-side 允许密钥;未配置 → 所有认证端点 503 |
| `FACTPY_KERNEL_AUTH_DISABLED` | 否 | `true` 时跳过 API key 检查(仅限本地开发) |
| `FACTPY_EXTRACTION_MODEL` | 否 | 全局默认 model,优先级低于显式传参。默认 `gpt-4.1` |
| `FACTPY_EXTRACTION_TEMPERATURE` | 否 | 默认 `0.0` |
| `FACTPY_EXTRACTION_TIMEOUT` | 否 | 秒;默认 `30.0` |

`*` = `MISTRAL_API_KEY` / `OPENAI_API_KEY` 至少要提供一个(取决于你用哪个 model)。

## 已验证的 LLM 模型

2026-04-13 Re-DocRED benchmark(10 docs,entity-with-facts F1):

| Model | F1 | Precision | Recall | Docs OK | 成本 | 推荐场景 |
|---|---|---|---|---|---|---|
| **`mistral/mistral-small-latest`** | **78%** | 82% | 74% | 10/10 | **免费** | 默认推荐 |
| `gpt-4.1` | 68% | 90% | 54% | 10/10 | $0.002/1K tok | precision 优先 / 零 hallucination |
| `gpt-4.1-mini` | 40% | 92% | 28% | 10/10 | $0.0004/1K tok | 成本敏感 |

完整比较报告:[docs/references/cross-provider-entity-benchmark-report.md](docs/references/cross-provider-entity-benchmark-report.md)

## Troubleshooting

### `.env` 里的 key 没被读到

`.env` 里常见写法 `KEY = "value"`(带空格等号)**不是 POSIX shell 语法**,`source .env` 会报 `command not found`。解析方法:

```bash
eval $(awk -F ' = ' 'NF==2 {gsub(/"/, "", $2); printf "export %s=%s\n", $1, $2}' .env)
echo "MISTRAL=${#MISTRAL_API_KEY} OPENAI=${#OPENAI_API_KEY}"  # 应该不是 0
```

### HTTP 401 `{"detail":"Invalid or missing API key"}`

客户端没在 header 里带 `X-FactPy-API-Key`,或 key 不在 `FACTPY_KERNEL_API_KEYS` 列表。本地开发可临时 `FACTPY_KERNEL_AUTH_DISABLED=true`。

### HTTP 500 `stage=resolution` + `specs must be non-empty list`

抽取 0 条有效 proposal。常见原因:文档和 schema 不匹配、LLM 免费 tier 被限速、或模型能力不足。先用 `examples/dora_pdf_extract.py --max-segments 2` 跑小样本确认链路。详见 [USAGE.md §5](src/factpy_kernel/agent/extraction/docs/USAGE.md)。

### PDF 被 staging 切得太碎

staging 是行级切段;规整 PDF(如 EU RTS)22 页会产出 800+ 段,均值 150 字符,对 LLM 每段信息量太少。解决:上层按 `min_chars` 过滤后再送 extraction,参考 `examples/dora_pdf_extract.py` 的实现。

## 测试

```bash
PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"
```

当前基线:1023 tests。

## 许可与安全

Secret 处理、API key 轮换见 [docs/SECURITY.md](docs/SECURITY.md)。
