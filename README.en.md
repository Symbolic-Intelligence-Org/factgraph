# factpy-kernel

**Auditable reasoning framework with LLM document extraction.**

> 🌏 Language: [中文](README.md) | **English**

Four independent top-level packages in this monorepo (same repo, but namespaces are separated):

1. **`kernel`** — append-only fact store + deterministic reasoning (core + adapters for Soufflé / ProbLog / PyReason) + audit / provenance
2. **`agent`** — LLM document extraction pipeline; extracts structured entities + facts from PDF / DOCX / Markdown / TXT; ships its own HTTP surface (`agent.service.app`)
3. **`service`** — kernel's HTTP delivery layer (runtime / rules / registry routes + auth + envelope contract)
4. **`domains`** — domain-specific bundles (currently: ECSS aerospace-compliance schemas + helpers)

> **Scope boundary.** The LLM pipeline (`agent`) only extracts **facts** (entity + predicate + field_values). It does **NOT** extract rules. Rules must be authored by humans via the `kernel.authoring` layer (`POST /v1/rules/validate` / `compile-preview` / session `ephemeral-rules`) — this is a deliberate choice of the auditable-reasoning positioning; non-deterministic LLM output is not trusted to decide which rules run. If you expect "read a regulation → auto-generate Datalog rules", the current system does **not** do that, nor is it on any active or archived blueprint.

This README only covers **how to use it**. For architecture principles see [docs/architecture_principles.md](docs/architecture_principles.md), for the docs index see [docs/README.md](docs/README.md), for the contributor workflow see [AGENTS.md](AGENTS.md). Internal module docs are primarily in Chinese.

## Three paths — I want to …

### A. Try the extraction interactively

Open the notebook:

```bash
pip install -e ".[extraction,documents]"
pip install jupyter        # jupyter is not in any extras — install once
jupyter notebook examples/09_dora_document_extraction.ipynb
```

The notebook runs a real-LLM extraction on a built-in DORA sample (~1 minute). Full notebook index: [examples/README.md](examples/README.md).

### B. Call the Python API from my script

```python
from kernel.sdk import Entity, Field, Identity
from agent.extraction import extract_document

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

Full parameter reference, return-value structure, failure diagnostics, and known limitations: [src/agent/extraction/docs/USAGE.md](src/agent/extraction/docs/USAGE.md).

Run on a real PDF end-to-end: `python examples/dora_pdf_extract.py path/to/your.pdf`

### C. Deploy the HTTP service for frontend / other services

`kernel`'s HTTP routes (runtime / rules / registry) and `agent`'s extraction route are **two independent FastAPI apps**.

Run kernel runtime / rules / registry only:

```bash
pip install -e ".[service]"
FACTPY_KERNEL_API_KEYS=dev \
  uvicorn service.app_v1:app --port 8000
```

Run extraction (separate port, or mount in the same process):

```bash
pip install -e ".[service,extraction,documents]"
FACTPY_KERNEL_API_KEYS=dev \
MISTRAL_API_KEY="..." \
  uvicorn agent.service.app:app --port 8001
```

Extraction call example:

```bash
curl -X POST http://localhost:8001/v1/extraction/documents \
  -H "X-FactPy-API-Key: dev" \
  -F "file=@doc.pdf" \
  -F 'options={"schema_ir":{...},"model":"mistral/mistral-small-latest"}'
```

Full DTO contract (request / 200 / 422 / 500 envelope): [src/agent/service/docs/05_extraction.md](src/agent/service/docs/05_extraction.md)
kernel's `/v1/*` routes overview: [src/service/docs/01_overview.md](src/service/docs/01_overview.md)

**API documentation:**
- Frontend integration guide (runtime / rules / registry): [src/service/docs/06_frontend_integration.md](src/service/docs/06_frontend_integration.md)
- Extraction HTTP integration: [src/agent/service/docs/README.md](src/agent/service/docs/README.md)
- (Note: `docs/api/openapi.yaml` ownership is TBD after the service split — see the OS-prep blueprint.)

## Install

### Prerequisites

- Python ≥ 3.10
- `git`
- `jupyter` (required for Path A; install once via `pip install jupyter` — not included in any extras)
- **At least one LLM provider key** (needed for all three paths A/B/C) — see the "Environment variables" table below for signup links.

### Extras

| Need | Extras |
|---|---|
| kernel only (append-only store + native rules + audit) | `pip install -e .` |
| LLM extraction | `pip install -e ".[extraction,documents]"` |
| HTTP service (kernel runtime + extraction) | `pip install -e ".[service,extraction,documents]"` |
| Langfuse observability | `pip install -e ".[observability]"` |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `MISTRAL_API_KEY` | `*` | Mistral provider (**default recommendation**, free tier does not require a credit card). Sign up: [console.mistral.ai](https://console.mistral.ai) → register → API Keys → Create new key. Models with the `mistral/` prefix automatically use the native SDK. |
| `OPENAI_API_KEY` | `*` | OpenAI provider (GPT-4.1 / GPT-4.1-mini). Sign up: [platform.openai.com/api-keys](https://platform.openai.com/api-keys). |
| `FACTPY_KERNEL_API_KEYS` | Required server-side | Comma-separated list of accepted server-side API keys (**you pick these**, unrelated to any third-party provider key). Missing → every authenticated endpoint returns 503. Clients echo one of these in the `X-FactPy-API-Key` header. |
| `FACTPY_KERNEL_AUTH_DISABLED` | No | Set to `true` to skip API key checks (local development only). |
| `FACTPY_EXTRACTION_MODEL` | No | Global default model; lower priority than explicit arguments. Default: `gpt-4.1`. |
| `FACTPY_EXTRACTION_TEMPERATURE` | No | Default: `0.0`. |
| `FACTPY_EXTRACTION_TIMEOUT` | No | Seconds. Default: `30.0`. |

`*` = at least one of `MISTRAL_API_KEY` / `OPENAI_API_KEY` must be set (depending on which model you use). Both are **third-party LLM provider keys** — you sign up on their respective sites, not in this project.

## Verified LLM models

2026-04-13 Re-DocRED benchmark (10 docs, entity-with-facts F1):

| Model | F1 | Precision | Recall | Docs OK | Cost | Best for |
|---|---|---|---|---|---|---|
| **`mistral/mistral-small-latest`** | **78%** | 82% | 74% | 10/10 | **Free** | Default recommendation |
| `gpt-4.1` | 68% | 90% | 54% | 10/10 | $0.002 / 1K tok | Precision-first / zero-hallucination scenarios |
| `gpt-4.1-mini` | 40% | 92% | 28% | 10/10 | $0.0004 / 1K tok | Cost-sensitive |

Full comparison report: [docs/references/cross-provider-entity-benchmark-report.md](docs/references/cross-provider-entity-benchmark-report.md)

## Troubleshooting

### Keys in `.env` are not picked up

A common `.env` form `KEY = "value"` (with spaces around `=`) is **not valid POSIX shell syntax**; `source .env` reports `command not found`. Parse it with awk instead:

```bash
eval $(awk -F ' = ' 'NF==2 {gsub(/"/, "", $2); printf "export %s=%s\n", $1, $2}' .env)
echo "MISTRAL=${#MISTRAL_API_KEY} OPENAI=${#OPENAI_API_KEY}"  # should not be 0
```

### HTTP 401 `{"detail":"Invalid or missing API key"}`

The client did not send `X-FactPy-API-Key`, or the key is not in `FACTPY_KERNEL_API_KEYS`. For local development you can temporarily set `FACTPY_KERNEL_AUTH_DISABLED=true`.

### HTTP 500 `stage=resolution` + `specs must be non-empty list`

Extraction produced zero valid proposals. Common causes: the document does not match the schema, the LLM free tier is rate-limited, or the model is simply not strong enough. Sanity-check with `examples/dora_pdf_extract.py --max-segments 2` first. Details in [USAGE.md §5](src/agent/extraction/docs/USAGE.md).

### Staging splits PDFs into tiny segments

Staging uses line-level segmentation; a well-formatted PDF (e.g. an EU RTS) produces 800+ segments over 22 pages averaging ~150 characters — too thin per segment for the LLM. Fix at the caller layer: filter by `min_chars` before dispatching to extraction. See `examples/dora_pdf_extract.py` for the pattern.

## Tests

After the namespace split, tests live across 5 directories — run each:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/agent/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/service/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/domains/ecss/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s tools/benchmarks/tests -p "test_*.py"
```

Total across the 5 segments — current baseline: 1023 tests.

## 📚 Deeper dive

This README covers "onboarding + three paths" only. Five common next directions:

| You want | Go to |
|---|---|
| The full 8-notebook learning path (SDK → rules → compliance → probabilistic → multi-engine → agent end-to-end) | [examples/README.md](examples/README.md) |
| Agent-layer capabilities beyond extraction (session, bundle review/commit, rule routing, read-review orchestrator) | [src/agent/docs/README.md](src/agent/docs/README.md) + [examples/08_agent_document_workflow.ipynb](examples/08_agent_document_workflow.ipynb) |
| Use kernel for pure auditable reasoning without LLMs | [src/kernel/core/docs/01_architecture.md](src/kernel/core/docs/01_architecture.md) |
| SDK complete reference (Entity / Field / Store / CRUD / Batch) | [src/kernel/sdk/docs/04_api_surface.md](src/kernel/sdk/docs/04_api_surface.md) |
| **Master index of all module docs** (adapters / authoring / audit / application / service, etc.) | [docs/README.md](docs/README.md) |

Other pointers:
- [docs/architecture_principles.md](docs/architecture_principles.md) — project philosophy and long-term boundaries
- [AGENTS.md](AGENTS.md) — contributor workflow (blueprint-driven)
- [docs/blueprints/archive/](docs/blueprints/archive/) — historical decision rationale (not current truth)

## License & security

This project is licensed under the Apache License 2.0; see [LICENSE](LICENSE).

Secret handling and API key rotation: [docs/SECURITY.md](docs/SECURITY.md).
