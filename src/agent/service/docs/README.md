# Agent Service — Extraction HTTP Surface

承载 agent 层的 HTTP delivery surface,作为 agent package 内的独立 sub-package。

## 模块组成

- `app.py` — standalone FastAPI app,挂载 `POST /v1/extraction/documents` 路由
- `extraction_v1.py` — 路由 handler(从 service package 迁入,因为 owner 是 agent)
- `docs/05_extraction.md` — extraction DTO 契约

## 与 service package 的关系

- 跨包消费 `service._common.{error_response, ok_response}` 和
  `service.auth.require_api_key`
- 复制 `service.app_v1` 的全局 `@app.exception_handler(Exception)`,
  保持 envelope 一致(`{ok: false, errors: [...]}`)
- agent.service.app 是独立 FastAPI 实例,运行时与 service.app_v1 解耦

## 部署形态

- 独立:`uvicorn agent.service.app:app`
- 与 service.app_v1 并行:reverse proxy 把 `/v1/extraction/*` 路由到 agent app,
  其它 `/v1/*` 路由到 service app

## 文档索引

- [05_extraction.md](./05_extraction.md) — extraction DTO 契约
