# factpy-kernel

**Auditable reasoning framework with LLM document extraction.**

> 🌏 语言: **中文** | [English](README.en.md)

两层能力:

1. **append-only fact store + deterministic reasoning**(core + adapters to Soufflé / ProbLog / PyReason)
2. **LLM 文档抽取管道**(agent/extraction):从 PDF / DOCX / Markdown / TXT 抽结构化 entities + facts

> **能力边界**:LLM 管道只抽取**事实**(entity + predicate + field_values),**不抽取规则**。规则只能通过 authoring 层人工编写(`POST /v1/rules/validate` / `compile-preview` / session `ephemeral-rules`)——这是 auditable reasoning 定位的故意设计,非 LLM 确定性决定"哪条规则能跑"。如果你期待"读一份监管文档 → 自动生成 Datalog 规则",当前系统**不做**,也不在任何 active/archived 蓝图里。

本 README 只覆盖**如何使用**;架构原则见 [docs/architecture_principles.md](docs/architecture_principles.md),文档索引见 [docs/README.md](docs/README.md),工作流见 [AGENTS.md](AGENTS.md)。

## 三岔路:我想……

### A. 交互式体验一下 extraction

打开 notebook:

```bash
pip install -e ".[extraction,documents]"
pip install jupyter        # jupyter 不在 extras 里,单独装一次
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

### Prerequisites

- Python ≥ 3.10
- `git`
- `jupyter`(Path A 要用,单独 `pip install jupyter`,不在 extras 里)
- **至少一个 LLM provider key**(Path A/B/C 都需要)—— 见下面"环境变量"表格有申请入口

### Extras

| 需求 | extras |
|---|---|
| 只用 core(append-only store + native rules) | `pip install -e .` |
| LLM extraction | `pip install -e ".[extraction,documents]"` |
| HTTP 服务 | `pip install -e ".[service,extraction,documents]"` |
| Langfuse observability | `pip install -e ".[observability]"` |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `MISTRAL_API_KEY` | `*` | Mistral provider(**默认推荐**,免费 tier 无需信用卡)。申请:[console.mistral.ai](https://console.mistral.ai) → 注册 → API Keys → Create new key。带 `mistral/` 前缀的 model 会自动走原生 SDK。 |
| `OPENAI_API_KEY` | `*` | OpenAI provider(GPT-4.1 / GPT-4.1-mini)。申请:[platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `FACTPY_KERNEL_API_KEYS` | 服务端必填 | 逗号分隔的 server-side 允许密钥(**你自己定**,不是第三方 provider 的);未配置 → 所有认证端点 503。客户端在 `X-FactPy-API-Key` header 里回传其中任一。 |
| `FACTPY_KERNEL_AUTH_DISABLED` | 否 | `true` 时跳过 API key 检查(仅限本地开发) |
| `FACTPY_EXTRACTION_MODEL` | 否 | 全局默认 model,优先级低于显式传参。默认 `gpt-4.1` |
| `FACTPY_EXTRACTION_TEMPERATURE` | 否 | 默认 `0.0` |
| `FACTPY_EXTRACTION_TIMEOUT` | 否 | 秒;默认 `30.0` |

`*` = `MISTRAL_API_KEY` / `OPENAI_API_KEY` 至少要提供一个(取决于你用哪个 model)。两个都是**第三方 LLM provider 的 key**,注册在各自官网申请,不在本项目内配置。

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

## 📚 进一步探索

本 README 只覆盖"入门 + 三岔路"。想更深入 5 个高频方向:

| 你想 | 去哪 |
|---|---|
| 看 8 个 notebook 的完整学习路径(SDK → 规则 → 合规 → 概率 → 多引擎 → agent 端到端) | [examples/README.md](examples/README.md) |
| 了解 agent 层超出 extraction 的能力(session, bundle review/commit, rule routing, read-review orchestrator) | [src/factpy_kernel/agent/docs/README.md](src/factpy_kernel/agent/docs/README.md) + [examples/08_agent_document_workflow.ipynb](examples/08_agent_document_workflow.ipynb) |
| 只用 core 做纯 auditable reasoning,不碰 LLM | [src/factpy_kernel/core/docs/01_architecture.md](src/factpy_kernel/core/docs/01_architecture.md) |
| SDK(Entity / Field / Store / CRUD / Batch)完整参考 | [src/factpy_kernel/sdk/docs/04_api_surface.md](src/factpy_kernel/sdk/docs/04_api_surface.md) |
| **所有模块 docs 的总索引**(adapters / authoring / audit / application / service 等都在这里) | [docs/README.md](docs/README.md) |

其它入口:
- [docs/architecture_principles.md](docs/architecture_principles.md) — 项目哲学与长期边界
- [AGENTS.md](AGENTS.md) — 贡献者工作流(blueprint-driven)
- [docs/blueprints/archive/](docs/blueprints/archive/) — 历史决策的 rationale(不是当前真相)

## 许可与安全

Secret 处理、API key 轮换见 [docs/SECURITY.md](docs/SECURITY.md)。
