# Service 层现状核验（factpy_kernel）

- 范围：`src/factpy_kernel/service`
- 核验日期：2026-02-24
- 结论：**仓库内已存在 HTTP 服务层（FastAPI）**，当前是规则校验/预览的薄接口，不包含 derivation/evaluate/accept/view 投影端点。

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
  - 调用 `factpy_kernel.facade.rules_v1.validate_rule(...)`
- `POST /v1/rules/compile-preview`
  - 调用 `factpy_kernel.facade.rules_v1.compile_rule_preview(...)`
- `GET /v1/profiles`
  - 调用 `factpy_kernel.facade.rules_v1.list_profiles(...)`

补充：

- 当前 `service v1` 主要服务于 **rules facade**（规则 DTO 校验/编译预览）。
- 尚未提供：
  - `schema compile`
  - `derivations evaluate/accept`
  - `project_view_facts / project_view_facts_with_audit`

## 3. 异常返回形态（当前实现）

`app_v1` 注册了全局异常处理器，会把未捕获异常包装为统一 envelope（HTTP 200）：

- `ok = false`
- `errors[0].kind = "runtime"`
- `errors[0].path = "$"`
- `errors[0].details.message = str(exc)`

这与 facade v1 的 `{ok, errors, meta}` 风格保持一致，但**并不等价于 core 的 `AcceptResult.diagnostics` contract**（后者见 `04_public_contract_v1.md`）。

## 4. 测试与可复现性

- 路由回归测试：`src/factpy_kernel/tests/test_service_v1_routes.py`
  - 当未安装 `service` 额外依赖时会跳过（`skipUnless`）。
- 当前测试覆盖点：
  - 路由结果与 facade 结果一致
  - 错误响应透传
  - `/v1/profiles` 包含 `souffle_strict`

## 5. 对后续 SDK/API thin-slice 的影响

- **不需要新建 HTTP 服务层框架**（已有 `FastAPI` 入口可扩展）。
- 后续可在现有 `app_v1` 上增量增加 derivation/view 端点，但建议先完成：
  - `Public Contract v1` 固化（文档 + 测试）
  - compat import 禁新增规则
  - SDK thin-slice 闭环验证
