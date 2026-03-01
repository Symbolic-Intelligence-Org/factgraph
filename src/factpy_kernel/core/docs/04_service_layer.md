# Service 层现状核验（factpy_kernel）

- 范围：`src/factpy_kernel/service`
- 核验日期：2026-03-01
- 结论：**仓库内已存在可供前端对接的 HTTP 服务层（FastAPI）**。当前已覆盖 rules validate/preview、runtime session + facts write/query + query facade + rule run + derivation evaluate/accept + package export、registry 读取接口。

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

## 2. 边界判定

service 当前定位：

- 是对外 HTTP/BFF 层，负责 API、DTO、session 编排和统一错误 envelope。
- 不是 core 领域语义层，不拥有 rule/store/view/accept/mapping 的最终语义定义权。

service 应负责：

- HTTP/JSON 协议层与路由暴露
- DTO 规范化、别名兼容和 shape 校验
- runtime session 协调
- registry 只读 facade
- package export 这类最外层远程编排能力

service 不应负责：

- authoring/registry 写入工作流
- SDK 对象式 API
- 更高层 audit summary 聚合

## 3. 依赖分层

当前代码依赖关系可概括为：

- `app_v1`
  - 只依赖 `factpy_kernel.service.*`
- `rules_v1`
  - 依赖 `authoring.rules`
  - 依赖 `core.rules.backend_profile / rule_ast / rule_ast_validate`
- `runtime_v1`
  - 依赖 `authoring.rules / derivation_compile / FileAuthoringRegistry`
  - 依赖 `core.derivation / evidence.write_protocol / mapping / rules.rule_ir / schema / store / view.projector`
  - 在 package export 场景直接依赖 `adapters.souffle.package`
- `registry_v1`
  - 依赖 `authoring.FileAuthoringRegistry`
  - 依赖 service 内部 `_registry_io`

存储整合：

- runtime 通过 `core.store.ledger.Ledger` 接入存储；支持内存模式与 `ledger_path` 指定的 SQLite 文件模式
- registry 读取走文件系统目录，不经过数据库
- 当前 service 不直接依赖外部业务数据库、ORM、连接池或审计查询模块

## 4. 当前端点（v1）

文件：`src/factpy_kernel/service/app_v1.py`

详细 DTO 文档（当前已补齐 runtime session / query / rules-registry 部分）：

- `docs/api/runtime-session.md`
- `docs/api/runtime-queries.md`
- `docs/api/rules-registry.md`

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
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
- `POST /v1/runtime/sessions/{session_id}/queries/conflicts`
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping`
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts`
- `POST /v1/runtime/sessions/{session_id}/rules/run`
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/runtime/sessions/{session_id}/packages/export`
- `POST /v1/registry/manifest`
- `POST /v1/registry/schema/read`
- `POST /v1/registry/assets/list`
- `POST /v1/registry/rules/read`
- `POST /v1/registry/derivations/read`

补充：

- 当前 `service v1` 已从 rules-only 薄层扩展为前端/BFF 第一批接口。
- session 编排属于 `service` 自身的协调责任，不下沉到 `core`。
- `POST /v1/runtime/sessions/{session_id}/rules/run` 默认复用 session 打开时绑定的 `registry_root`；如需按请求覆盖，使用 `override_registry_root`。
- `POST /v1/runtime/sessions/{session_id}/queries/explain-fact` 和 `POST /v1/runtime/sessions/{session_id}/queries/conflicts` 统一走 `POST` body；`explain-fact.val_atoms` 放在请求体中。
- `POST /v1/runtime/sessions/{session_id}/queries/resolve-mapping` 只接受 `pred_id`，由 service 从 session schema 自行解析 `schema_pred`；`pred_id` 不存在或不是 mapping predicate 时返回 `shape`。
- `resolve-mapping` 成功时把 `chosen_map` 序列化为 `[{key_tuple, value_tuple}]`；发生多值冲突时返回 `ok=false` 且 `errors[].kind="mapping_conflict"`。
- `POST /v1/runtime/sessions/{session_id}/queries/view-facts` 用单端点同时覆盖 `project_view_facts` 和 `project_view_facts_with_audit`；`include_audit=true` 时在 `view.audit` 中返回 `ProjectorAudit`。
- `view-facts` 的外部 `temporal_view` 契约使用 `record | active`；service 内部把 `active` 归一到 core 的 `current`。
- `view-facts` 统一把 `facts: dict[str, list[tuple[Any, ...]]]` 序列化为 JSON `dict[str, list[list[Any]]]`，并在 `meta` 中返回 `pred_count / total_tuple_count`。
- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate` 返回完整 candidate 对象，供 `accept` 原样 round-trip。
- `POST /v1/runtime/sessions/{session_id}/derivations/accept` 要求客户端原样回传 `candidate`；尤其不要裁剪 record candidate 的 `roles / record_exists_pred_id / id_policy`。
- `POST /v1/runtime/sessions/{session_id}/derivations/accept` 在 `skipped_reason_counts.aborted > 0` 时返回 `meta.terminal=true`，表示结果已进入终止态且不应自动重试。

## 5. 异常返回形态（当前实现）

`app_v1` 注册了全局异常处理器，会把未捕获异常包装为统一 envelope（HTTP 200）：

- `ok = false`
- `errors[0].kind = "runtime"`
- `errors[0].path = "$"`
- `errors[0].details.message = str(exc)`

该约定适用于请求已进入 FastAPI app 之后的 service 级错误；进程崩溃、代理层超时、网络中断等传输/基础设施故障不在此 envelope 契约内。

这与 `service.rules_v1` 的 `{ok, errors, meta}` 风格保持一致，但**并不等价于 core 的 `AcceptResult.diagnostics` contract**（后者见 `04_public_contract_v1.md`）。

## 6. 测试与可复现性

- 路由回归测试：`src/factpy_kernel/tests/test_service_v1_routes.py`
  - 当未安装 `service` 额外依赖时会跳过（`skipUnless`）。
- runtime/registry 路由回归测试：`src/factpy_kernel/tests/test_service_runtime_v1_routes.py`
- 当前测试覆盖点：
  - 路由结果与 facade 结果一致
  - 错误响应透传
  - `/v1/profiles` 包含 `souffle_strict`
  - runtime session 打开/关闭、持久化 ledger、facts 写入/查询、package 导出
  - explain/conflicts/resolve_mapping 三个 query facade 的 route contract
  - resolve_mapping 的 tuple JSON 序列化、非 mapping pred shape error、mapping_conflict error
  - view-facts 的默认/带 audit 返回、`active` alias、非法 `legacy_record_visibility` shape error
  - derivation evaluate/accept 的 candidate round-trip、裁剪 candidate shape error、`terminal` 语义
  - registry schema/manifest/rule 读取
  - runtime `RuleRef` 经 session `registry_root` 或显式 `override_registry_root` 解析

## 7. 对后续 SDK/API thin-slice 的影响

- **不需要新建 HTTP 服务层框架**（已有 `FastAPI app_v1` 可持续扩展）。
- 当前后续重点不再是“先建服务”，而是：
  - 补面向 UI 的 audit summary 等更高层查询接口
  - 收敛请求/响应 DTO 文档与前后端契约
