# Service 层现状核验（factpy_kernel）

- 范围：`src/factpy_kernel/service`
- 核验日期：2026-02-28
- 结论：**仓库内已存在可供前端对接的 HTTP 服务层（FastAPI）**。当前已覆盖 rules validate/preview、runtime session + facts write/query + rule run + package export、registry 读取接口；derivation evaluate/accept 仍未暴露为 HTTP 端点。

## 1. 入口与依赖

- 服务入口模块：`factpy_kernel.service.app_v1`
- ASGI app 对象：`factpy_kernel.service.app_v1:app`
- 可选依赖（`pyproject.toml`）：`[project.optional-dependencies].service`
  - `fastapi`
  - `uvicorn`
  - `httpx`

建议启动方式（仓库根目录）：

```bash
pip install -e '.[service]'
python -m uvicorn factpy_kernel.service.app_v1:app --reload
```

## 2. 当前端点（v1）

文件：`src/factpy_kernel/service/app_v1.py`

- `POST /v1/rules/validate`
  - 调用 `factpy_kernel.service.rules_v1.validate_rule(...)`
- `POST /v1/rules/compile-preview`
  - 调用 `factpy_kernel.service.rules_v1.compile_rule_preview(...)`
- `GET /v1/profiles`
  - 调用 `factpy_kernel.service.rules_v1.list_profiles(...)`
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

补充：

- 当前 `service v1` 已从 rules-only 薄层扩展为前端/BFF 第一批接口。
- 尚未提供：
  - `derivations evaluate/accept`
  - `explain_fact / conflicts / resolve_mapping`
  - `project_view_facts / project_view_facts_with_audit`

## 3. 异常返回形态（当前实现）

`app_v1` 注册了全局异常处理器，会把未捕获异常包装为统一 envelope（HTTP 200）：

- `ok = false`
- `errors[0].kind = "runtime"`
- `errors[0].path = "$"`
- `errors[0].details.message = str(exc)`

这与 `service.rules_v1` 的 `{ok, errors, meta}` 风格保持一致，但**并不等价于 core 的 `AcceptResult.diagnostics` contract**（后者见 `04_public_contract_v1.md`）。

## 4. 测试与可复现性

- 路由回归测试：`src/factpy_kernel/tests/test_service_v1_routes.py`
  - 当未安装 `service` 额外依赖时会跳过（`skipUnless`）。
- runtime/registry 路由回归测试：`src/factpy_kernel/tests/test_service_runtime_v1_routes.py`
- 当前测试覆盖点：
  - 路由结果与 facade 结果一致
  - 错误响应透传
  - `/v1/profiles` 包含 `souffle_strict`
  - runtime session 打开/关闭、持久化 ledger、facts 写入/查询、package 导出
  - registry schema/manifest/rule 读取
  - runtime `RuleRef` 经 registry_root 解析

## 5. 对后续 SDK/API thin-slice 的影响

- **不需要新建 HTTP 服务层框架**（已有 `FastAPI app_v1` 可持续扩展）。
- 当前后续重点不再是“先建服务”，而是：
  - 补 `derivation evaluate/accept` 的服务接口
  - 补面向 UI 的 explain/conflicts/audit summary 接口
  - 收敛请求/响应 DTO 文档与前后端契约
