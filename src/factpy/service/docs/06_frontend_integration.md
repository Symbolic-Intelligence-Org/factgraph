# Frontend Integration Guide(service v1)

面向对接 kernel HTTP service 的前端/BFF 开发者。本文档把分散在 `01_overview.md` / `02_runtime_sessions.md` / `03_runtime_queries_policy.md` / `04_rules_registry.md` 里的信息,整合成"怎么真正调"。

> **范围**:本文档**只覆盖 kernel runtime / rules / registry 路由**(`service.app_v1`)。extraction HTTP integration(`POST /v1/extraction/documents`)在 namespace split 后归 agent.service,见 [`src/agent/service/docs/`](../../../agent/service/docs/)。

**机读契约**:`docs/api/openapi.yaml` 在 service 拆分后归属待定(见 OS-prep blueprint),当前文档与 live FastAPI spec 的同步状态以本目录文档为准。

## 0. 前置

### 0.1 Base URL + 认证 header

- 本地:`http://localhost:8000`
- 每个请求必须带 header:`X-FactPy-API-Key: <key>`
- 服务端从环境变量 `FACTPY_KERNEL_API_KEYS`(逗号分隔)读取允许的 keys
- 本地开发可设 `FACTPY_KERNEL_AUTH_DISABLED=true` 跳过认证

### 0.2 Envelope 结构

**绝大多数 `/v1/*` 操作返回 `HTTP 200`**,用 JSON envelope 表达 success / failure:

```ts
interface Envelope {
  ok: boolean;                 // true = 成功, false = 业务失败
  errors: ErrorEntry[];        // ok=true 时为 [];ok=false 时非空
  meta: Record<string, unknown>;
  // 操作特定字段(如 session / claims / result / write)与 ok/errors/meta 平级
  [key: string]: unknown;
}

interface ErrorEntry {
  kind: string;                // 错误类别:shape / validation / runtime 等
  path: string;                // JSON-pointer-like 路径,或 "$" 表示全局
  details?: Record<string, unknown>;
}
```

(注:`POST /v1/extraction/documents` 的 HTTP 状态码语义略有不同 — 详见 [`agent/service/docs/`](../../../agent/service/docs/)。)

### 0.3 认证失败不走 envelope

`HTTP 401` 和 `HTTP 503` 是 FastAPI 依赖层拦截,**不进 envelope**:

```json
{"detail": "Invalid or missing API key"}
{"detail": "API authentication not configured"}
```

OpenAPI spec 把这两种响应作为 `UnauthorizedError` / `AuthNotConfiguredError` 可复用 response component,挂在每个 operation 上。

### 0.4 当前 spec 的精度边界(重要)

`docs/api/openapi.yaml` 是**路由 / 认证 / envelope 覆盖完整**,但**不是字段级强类型完备**:

| 维度 | 状态 |
|---|---|
| 43 个 operation 全部可发现 | ✅ |
| 每个 op 标注 `ApiKeyAuth` + 401 + 503 | ✅ |
| `Envelope` / `Error` / `ExtractionResult` / `WriteRequest` 精确 schema | ✅ |
| **~40 个 op 的 request / response 仍是 `type: object`** | ⚠️ |

**这意味着**:

- 用 `openapi-typescript` 等工具生成 TS 类型时,~40 个 op 会拿到 `Record<string, unknown>` — 能发请求,但没强类型
- Swagger UI "try it out" 对这些 op 会给一个空 JSON 编辑器,需要照 `02_runtime_sessions.md` / `03_runtime_queries_policy.md` / `04_rules_registry.md` 里的 DTO 形状手拼 body
- **精确字段级契约现阶段在中文 DTO 文档里**,不在 yaml 里

**为什么不一上来就补全**:43 个 op 全部手写精确 schema(~3000 行 yaml 增量)或给 handler 加 pydantic response model(大范围代码改造 + 可能碰 1023 tests)都是独立的大项工作,ROI 要看真实消费者卡在哪。当前策略是**等前端真实使用反馈**后按用量优先级增量补齐。

**如果你是前端**,建议现在走混合模式:
- 拿 yaml 拉路由清单 + envelope 类型
- 其它 op 的 request/response 照 `02/03/04_*.md` 手拼 interface

### 0.5 HTTP 状态码速查

| 状态码 | 什么时候 | body 形状 |
|---|---|---|
| 200 | 几乎所有成功 + 大部分业务失败 | Envelope |
| 401 | 缺 / 错 `X-FactPy-API-Key` | `{detail: string}` |
| 503 | `FACTPY_KERNEL_API_KEYS` 未配置 | `{detail: string}` |

(extraction route 的 422/500 状态码语义在 agent.service.docs。)

## 1. 典型调用链路

### 1.1 Chain B:打开 session → 写入 facts → 查询

```ts
// 1. open session
let r = await post("/v1/runtime/sessions/open", {
  schema_ir: mySchemaIr,
  ledger_path: "/tmp/demo.db",
});
const sessionId = r.session.session_id;

// 2. 写一条 fact
await post(`/v1/runtime/sessions/${sessionId}/writes/set`, {
  pred_id: "person:country",
  e_ref: "idref_v1:Person:source_id=u1",
  rest_terms: [["string", "de"]],
  meta: { source: "user-form" },
});

// 3. 回读 claims
r = await get(`/v1/runtime/sessions/${sessionId}/claims?pred_id=person:country&include_args=true`);
const claims = r.claims;

// 4. 关闭 session
await del(`/v1/runtime/sessions/${sessionId}`);
```

完整 DTO:[`02_runtime_sessions.md`](./02_runtime_sessions.md)。

### 1.3 Chain C:跑规则 → 评估 inference → accept candidate

```ts
// 0. 假设 session 已开
// 1. 执行一条 filesystem-registered rule
let r = await post(`/v1/runtime/sessions/${sessionId}/rules/run`, {
  rule_id: "q_country_rows",
  version: "1.0.0",
});

// 2. evaluate 一条 inference
r = await post(`/v1/runtime/sessions/${sessionId}/inferences/evaluate`, {
  inference: {
    derivation_id: "drv.country_copy",
    version: "1.0.0",
    target: "person:country_copy",
    head_vars: ["$E", "$C"],
    where: [["pred", "person:country", ["$E", "$C"]]],
  },
});

// 3. accept 选中的 candidate —— 必须回传完整 payload
for (const candidate of r.result.candidates) {
  await post(`/v1/runtime/sessions/${sessionId}/inferences/accept`, {
    candidate,                    // 完整 echo,不要裁 terms / identity
  });
}
```

完整 DTO:[`02_runtime_sessions.md`](./02_runtime_sessions.md) §5.2 / [`03_runtime_queries_policy.md`](./03_runtime_queries_policy.md)。

### 1.4 Chain D:registry 只读查询

```ts
const manifest = (await post("/v1/registry/manifest", { root_dir: "/srv/registry" })).manifest;
const schema = (await post("/v1/registry/schema/read", { root_dir: "/srv/registry" })).schema;
const rule = (await post("/v1/registry/rules/read", {
  root_dir: "/srv/registry",
  rule_id: "q_country_rows",
  version: "1.0.0",
})).rule;
```

完整 DTO:[`04_rules_registry.md`](./04_rules_registry.md)。

## 2. 错误处理模板

```ts
interface ApiError extends Error {
  status: number;
  envelope?: Envelope;
  kind?: string;     // envelope.errors[0].kind,如果存在
}

async function call<T extends Envelope>(
  method: string, path: string, body?: unknown, isMultipart = false
): Promise<T> {
  const headers: Record<string, string> = { "X-FactPy-API-Key": apiKey };
  let init: RequestInit;
  if (isMultipart) {
    init = { method, headers, body: body as FormData };
  } else {
    headers["Content-Type"] = "application/json";
    init = { method, headers, body: body ? JSON.stringify(body) : undefined };
  }

  const resp = await fetch(`${BASE}${path}`, init);

  // 401/503:不走 envelope
  if (resp.status === 401 || resp.status === 503) {
    const detail = await resp.json().catch(() => ({ detail: "" }));
    const err = new Error(detail.detail || resp.statusText) as ApiError;
    err.status = resp.status;
    throw err;
  }

  // 200/422/500:都走 envelope
  const env = await resp.json() as Envelope;
  if (resp.status !== 200 || !env.ok) {
    const err = new Error(env.errors[0]?.details?.message as string || "request failed") as ApiError;
    err.status = resp.status;
    err.envelope = env;
    err.kind = env.errors[0]?.kind;
    throw err;
  }
  return env as T;
}
```

常见 `errors[0].kind`:

| kind | 出处 |
|---|---|
| `shape` | 请求缺字段 / 类型错 / JSON 不合法 |
| `runtime` | session 内部故障(ledger 等) |
| `runtime_session_not_found` | path 里 `session_id` 不存在 |
| `schema_mismatch` | 打开 session 时 schema digest 不匹配既有 ledger |
| `rule_ast_validate` | 注册 ephemeral rule 时 `pred_id` 不在 schema 中 |

(extraction 路由的 `validation` / `extraction` kind 见 agent.service.docs。)

## 3. 前端侧陷阱

### 3.1 同一 path 多 method

`/v1/runtime/sessions/{session_id}` 同时有 `GET`(读 summary)和 `DELETE`(关 session);`/v1/runtime/sessions/{session_id}/ephemeral-rules` 同时有 `POST` / `GET` / `DELETE`。写 fetch wrapper 时别把 path → handler 做成 1-1 映射。

### 3.2 状态码不对齐

不要用 `resp.ok` 作为业务成功判定。必须:
- `resp.status === 200 && envelope.ok === true` → 成功
- 其它组合 → 失败(具体 kind 在 envelope.errors[0].kind 或 detail)

(extraction 路由的状态码语义略有不同,见 agent.service.docs。)

### 3.3 `inferences/accept` 要完整 echo candidate

`POST /v1/runtime/sessions/{session_id}/inferences/accept` 的 request body **必须包含 evaluate 返回的完整 candidate payload**(含 `terms` / identity)。裁剪会触发 `shape` 错误。

### 3.5 `rest_terms` 是类型化二元组

写 facts 时 `rest_terms` 形状是 `[[type_domain, value], ...]`,不是平坦 array:

```json
// 正确
"rest_terms": [["string", "de"]]
// 错误
"rest_terms": ["de"]
```

## 4. 生成 TypeScript 客户端(可选)

`docs/api/openapi.yaml` 是机读 spec,可直接喂给前端生成工具:

```bash
# 示例:openapi-typescript
npx openapi-typescript docs/api/openapi.yaml -o src/api/types.ts

# 示例:orval / openapi-fetch / swagger-codegen 等
```

本仓库**不内置** TypeScript 类型生成 — 生成链路由前端自选。yaml 中的 schema 精度已经够支撑 typed envelope + typed request/response。

## 5. 与其它文档的关系

- [`01_overview.md`](./01_overview.md) — service 模块总览 + 完整路由清单
- [`02_runtime_sessions.md`](./02_runtime_sessions.md) — runtime session / writes / claims DTO 细节
- [`03_runtime_queries_policy.md`](./03_runtime_queries_policy.md) — runtime queries / inline policy DTO 细节
- [`04_rules_registry.md`](./04_rules_registry.md) — rules / registry DTO 细节
- [`../../../agent/service/docs/05_extraction.md`](../../../agent/service/docs/05_extraction.md) — `POST /v1/extraction/documents` DTO 细节(归属 agent.service)

## 6. 漂移守卫

`scripts/export_openapi.py` 会比较 checked-in yaml 和 live FastAPI spec 在 `(path, method)` 粒度是否一致;新增 / 删除路由后跑一次:

```bash
python scripts/export_openapi.py
```

exit 0 = 一致;exit 1 = 有漂移,会打印 `missing in yaml` / `extra in yaml` 的 `(path, method)` 对。脚本**不**自动覆盖 yaml(yaml 是人工维护的,精度高于 FastAPI auto-generated 输出)。
