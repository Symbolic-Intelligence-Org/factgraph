# FactPy Kernel Service (v1)

最小 HTTP 服务层（FastAPI），用于把 `factpy_kernel.service.rules_v1` 和 runtime/registry service facade 暴露给前端/产品团队使用。

## 安装

Core-only（不含服务依赖）：

```bash
pip install -e .
```

Service（含 FastAPI/uvicorn/httpx）：

```bash
pip install -e ".[service]"
```

## 启动

```bash
uvicorn factpy_kernel.service.app_v1:app --host 0.0.0.0 --port 8000
```

## API（v1）

- `POST /v1/rules/validate`
- `POST /v1/rules/compile-preview`
- `GET /v1/profiles`
- `POST /v1/runtime/sessions/open`
- `GET /v1/runtime/sessions/{session_id}`
- `DELETE /v1/runtime/sessions/{session_id}`
- `POST /v1/runtime/sessions/{session_id}/writes/set`
- `POST /v1/runtime/sessions/{session_id}/writes/add`
- `POST /v1/runtime/sessions/{session_id}/writes/retract`
- `GET /v1/runtime/sessions/{session_id}/claims`
- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/packages/export`
- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

说明：

- 当前 service 已是前端可用的第一批 BFF 接口，不再是 rules-only 薄层
- derivation evaluate/accept、explain/conflicts/audit summary 仍待补齐

## 响应约定

- 业务校验/编译错误统一返回 `HTTP 200`
- 使用 JSON envelope 表达结果：
  - 成功：`ok=true`
  - 失败：`ok=false` + `errors[]`

## Strict/Profile

- 可在请求 DTO 中使用 `strict=true` 或显式 `profile`
- 当前 strict 预设：`PROFILE_SOUFFLE_STRICT`
- 具体 strict/profile 语义与示例请见 `docs/语法.md`（Strict/profile 校验段落）
