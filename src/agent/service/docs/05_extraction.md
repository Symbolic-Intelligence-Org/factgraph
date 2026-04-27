# Extraction DTO（service v1）

范围:

- `POST /v1/extraction/documents`

本文记录 service v1 文档抽取端点的 DTO 契约。agent 层的 Python 产品 API(`extract_document(...)` / `extract_document_from_ir(...)`)见 [../../agent/extraction/docs/USAGE.md](../../agent/extraction/docs/USAGE.md);extraction 管道本身的实现口径见 [../../agent/extraction/docs/README.md](../../agent/extraction/docs/README.md)。

## 通用约定

- 该端点默认要求 `X-FactPy-API-Key`。
- 缺失或错误 key 返回 `HTTP 401`,且不会进入 JSON envelope。
- 认证启用但未配置 `FACTPY_KERNEL_API_KEYS` 时返回 `HTTP 503`,且不会进入 JSON envelope。
- 只有通过认证后,应用层成功/失败才继续使用 JSON envelope。
- 本端点的 application-layer 成功状态码是 `HTTP 200`;校验失败是 `HTTP 422`;抽取管道失败是 `HTTP 500`。这与 `02/03/04_*.md` 的"全 200 envelope"不同,是该端点**刻意**的设计差异,因为抽取失败通常不是客户端可修的输入问题。
- 成功:`ok=true`;失败:`ok=false` 且 `errors[]` 非空。

## 1. `POST /v1/extraction/documents`

上传文档并同步抽取结构化 facts。

### 请求

`multipart/form-data`,两个字段:

| 字段 | 类型 | 说明 |
|---|---|---|
| `file` | file upload(必填) | 待抽取文档。当前支持 `pdf` / `docx` / `md` / `txt`;staging 具体能力见 [../../agent/documents/docs/README.md](../../agent/documents/docs/README.md) |
| `options` | string(JSON,必填) | 抽取选项,形状见下 |

`options` JSON 字段:

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `schema_ir` | object | 是 | — | 预编译后的 Schema IR;可由 agent 层 `compile_schema_from_classes(...)` 产出,也可由调用方直接持有 |
| `model` | string | 否 | `gpt-4.1`(或 `FACTPY_EXTRACTION_MODEL` 环境变量) | LLM 模型 ID。已验证:`mistral/mistral-small-latest`(默认推荐)、`gpt-4.1`、`gpt-4.1-mini` |
| `entity_descriptions` | object(`str → str`)| 否 | `null` | 为 entity type 注入简短语义描述,帮助 LLM 做 identity grounding |
| `enable_gleaning` | boolean | 否 | `true` | 低 yield segment 二次扫描 |
| `enable_alias_merge` | boolean | 否 | `true` | resolver 阶段做 token-subset alias canonicalization |
| `max_batch_size` | integer | 否 | `1000` | 跨 segment 的 spec 硬上限 |
| `require_source` | boolean | 否 | `true` | 强制每条 proposal 带 source provenance |

### 成功响应(`HTTP 200`)

```json
{
  "ok": true,
  "errors": [],
  "meta": {},
  "result": {
    "doc_name": "dora-regulation-rts.pdf",
    "doc_id": "914093e7",
    "model": "mistral/mistral-small-latest",
    "staging_segments": 80,
    "gleaning_segments_reexamined": 0,
    "entities": [
      {
        "entity_type": "Regulation",
        "identity": {"title": "Regulation (EU) 2022/2554"},
        "fact_count": 9
      }
    ],
    "facts": [
      {
        "entity_type": "Regulation",
        "entity_identity": {"title": "Regulation (EU) 2022/2554"},
        "pred_id": "Regulation:summary",
        "field_values": [["string", "Sets out uniform requirements for ..."]],
        "confidence": 0.95
      }
    ],
    "metrics": {
      "total_segments": 80,
      "success_segment_count": 80,
      "error_segment_count": 0,
      "total_proposal_count": 149,
      "total_valid_count": 128,
      "total_rejection_count": 21,
      "batch_duration_ms": 249900
    },
    "merge_events": [
      {
        "fact_key_repr": "Regulation|title=Regulation (EU) 2022/2554|Regulation:summary",
        "primary_segment_id": "914093e7_0011",
        "merged_segment_id": "914093e7_0042",
        "entity_type": "Regulation",
        "pred_id": "Regulation:summary",
        "alias_merge": false
      }
    ]
  }
}
```

字段语义:

- `doc_id` 是 staging 层基于文档内容 hash 派生的稳定 id;`doc_name` 是请求上传时的文件名(F1 passthrough)。
- `entities[]` 是按 `(entity_type, entity_identity)` 聚合后的去重 census,`fact_count` 指向该 entity 总共产生了多少条 facts。
- `facts[]` 是 resolver 输出的去重/合并后 FactDraftSpec:
  - `entity_identity` 是解构后的 identity 键值 map(不是 `idref_v1:` 字符串)
  - `field_values` 保留原始类型标签:`[[type_domain, value], ...]`
  - `confidence` 为 `null` 或 `0.0-1.0`,由 LLM 自报;后端做运行时 normalize
- `metrics` 全部来自 pass 1;gleaning 新增的 facts 体现在 `gleaning_segments_reexamined` 和 `facts[]` 长度,但不回写 `total_valid_count`。
- `merge_events[]`:
  - `alias_merge=false`:exact duplicate merge
  - `alias_merge=true`:token-subset alias canonicalization 触发

### 校验失败(`HTTP 422`)

当 `options` 不是合法 JSON、或 `options.schema_ir` 缺失/为空对象时,端点在进入抽取管道前返回 422:

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "validation",
      "path": "options.schema_ir",
      "details": {
        "message": "options.schema_ir is required and must be a non-empty object"
      }
    }
  ],
  "meta": {}
}
```

其他 422 场景:

| `errors[0].path` | 触发条件 |
|---|---|
| `options` | `options` form 字段不是合法 JSON(`{not-json` 之类) |
| `options` | `options` 可以解析但不是 object(例如传了 JSON array) |
| `options.schema_ir` | `schema_ir` 缺失、不是 object、或是空 `{}` |

### 抽取管道失败(`HTTP 500`)

当 staging / extraction / resolution 任一阶段抛 `ExtractionDocumentError`:

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "extraction",
      "path": "$",
      "details": {
        "stage": "resolution",
        "message": "Resolution failed: specs must be non-empty list"
      }
    }
  ],
  "meta": {}
}
```

`details.stage` 可取值:

- `"staging"`:文档解析失败(格式不支持、PDF 破损、空文档)
- `"extraction"`:LLM 侧失败(认证失败、超限、instructor retry 耗尽)
- `"resolution"`:抽取产生 0 条 valid proposal 时,resolver 拒绝空输入 → 常见于 LLM 一条都没抽到

诊断建议:

- `stage=extraction` + `message` 里有 `Unauthorized` → 检查 `OPENAI_API_KEY` / `MISTRAL_API_KEY` 是否正确注入到 kernel 进程
- `stage=resolution` + message 里 `specs must be non-empty list` → 文档内容与 `schema_ir` 不匹配,或 LLM 在免费 tier 被限速;先用短样本验证、或换 `gpt-4.1`
- `stage=staging` → 文件本身问题,用 `examples/dora_pdf_extract.py` 做小范围冒烟

### curl 示例

准备一个 `options.json`:

```json
{
  "schema_ir": {"schema_ir_version": "v1", "entities": [...], "predicates": [...]},
  "model": "mistral/mistral-small-latest",
  "entity_descriptions": {"Regulation": "A specific article or provision"},
  "enable_gleaning": true,
  "enable_alias_merge": true
}
```

发请求:

```bash
curl -X POST http://localhost:8000/v1/extraction/documents \
  -H "X-FactPy-API-Key: $FACTPY_API_KEY" \
  -F "file=@dora.pdf" \
  -F "options=$(cat options.json)"
```

### 错误 kinds

- `validation`(HTTP 422):请求形状问题
- `extraction`(HTTP 500):抽取管道内部失败

## 相关文档

- `01_overview.md`:service 模块总览 + 路由目录
- `../../agent/extraction/docs/USAGE.md`:Python 产品 API `extract_document(...)` 使用手册
- `../../agent/extraction/docs/README.md`:extraction 管道实现口径
- `../../agent/documents/docs/README.md`:staging 层支持的文档格式与 segmentation 策略
