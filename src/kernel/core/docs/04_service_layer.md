# Service 层现状核验（kernel core 视角）

- 范围：HTTP/BFF delivery layer 与 `kernel.core` 的依赖关系
- 最后更新：2026-05-06(post Round Story Completion routemap closure @ `6b32972`)
- 视角：本文从 **core 角度** 描述 service 层 —— core 期望 service 如何调用、service 应遵守哪些 core invariant。Service 自身路由 / DTO 详细文档参考 [`src/service/docs/01_overview.md`](../../../service/docs/01_overview.md)。

## 1. 入口与依赖

- 服务入口：`service.app_v1`
- ASGI app：`service.app_v1:app`
- 可选依赖：`pip install -e '.[service]'`

建议启动：

```bash
python -m uvicorn service.app_v1:app --reload
```

## 2. 分层定位

service 在 `kernel.core` 上层,作为 HTTP / BFF delivery facade。

service 负责：

- HTTP 路由与 JSON DTO
- runtime session 生命周期与编排
- 统一错误 envelope（`ok / errors / meta`）
- registry 文件读取 facade
- API key 认证(`X-FactPy-API-Key`)

service 不负责(由 core 拥有)：

- core 语义定义(policy / chosen / where / evaluate / accept)
- live `Ledger` / `Store` 内部状态管理
- `accept_many_candidate_sets(...)` 的依赖排序与 atomic 回滚
- `register_engine_evaluator(...)` 的 adapter 注册(由 adapter 自己 import 时触发)
- ProjectorAudit contract 的字段语义
- Batch 3-7 application capabilities 的 HTTP 包装(per Batch 8 公开 surface 决议;走 advanced importable)

## 3. 当前 v1 路由概览

详细路由列表 + DTO 在 [`src/service/docs/01_overview.md`](../../../service/docs/01_overview.md) §4。本文不重复路由清单,只列类别:

- **rules**：validate / compile-preview / profiles
- **runtime session**：open / get / delete + writes(set / add / retract)+ claims
- **runtime queries**：explain-fact / conflicts / resolve-mapping / view-facts
- **runtime views**：create / update / delete / get / list
- **runtime rule/derivation/package**：rules.run / derivations.evaluate / derivations.accept / packages.export
- **registry**：manifest / schema.read / assets.list / rules.read / derivations.read

## 4. Service-to-Core Delegation Pattern

Service routes 走 `kernel.core` 的稳定 entry points;**service 不重新实现 core 语义**。典型 delegation:

| Service route | Core / application entry point |
|---|---|
| `POST /v1/runtime/sessions/open` | `Ledger(path=...)` 构造 |
| `POST /v1/runtime/sessions/{id}/writes/{set,add,retract}` | `kernel.core.write_protocol.{set,add,retract}_write(...)` |
| `POST /v1/runtime/sessions/{id}/queries/view-facts` | `kernel.core.store.queries.project_view_facts_with_audit(...)` |
| `POST /v1/runtime/sessions/{id}/rules/run` | `kernel.core.rules.run_rule(...)` |
| `POST /v1/runtime/sessions/{id}/derivations/evaluate` | `Store.evaluate(mode=...)` 走 `native | souffle | problog | pyreason` |
| `POST /v1/runtime/sessions/{id}/derivations/accept` | `Store.accept_many_candidate_sets(...)` |
| `POST /v1/runtime/sessions/{id}/packages/export` | adapter export(`package_kind="audit"` 等) |

Service 拒绝以下 anti-pattern(违反则会破坏 core invariant):

- 绕开 `write_protocol` 直接 mutate `Ledger` SQLite 表
- 重新实现 `evaluate_where(...)` 形参逻辑(rule action overlay 等扩展走 application runtime 而非 service)
- 在 service 层维护 schema digest 缓存(由 core `Store` 拥有)
- 直接消费 `kernel.application.protocol.*` 内部 dataclass(只通过 application runtime 入口)

## 5. DTO Adapter Responsibility

Service 在 HTTP 边界做 **DTO adapter**,把 JSON request/response 转换为 core / application protocol DTO:

- **入** —— request JSON → 严格构造 core / application protocol DTO(经 `__post_init__` 完整 validation),**不做半 DTO**(不 partial-fill 字段);
- **出** —— core / application result DTO → JSON envelope `{ok, data, errors, meta}`;**不暴露 core 内部 dataclass `repr`**;
- **不增减 DTO 字段** —— service 不可往 core / application DTO 加 service-only 字段;Service-only metadata 走 envelope `meta`。

DTO adapter 公共 helper:

- `kernel.application.protocol.common._validate_*`(协议 DTO 校验)
- `service._common.{ok, error}`(envelope 包装)

## 6. Error Propagation Across Layers

Core / application 抛出的错误按 specific → generic 顺序映射到 envelope。**Core / application 自身不关心 HTTP / envelope shape**,raw exception 由 service 包装:

| Core / application exception | Envelope shape | HTTP status |
|---|---|---|
| `ProtocolShapeError`(application protocol DTO 校验失败) | `errors[0].kind="shape"`,`path` 指字段路径 | 200 |
| `AuditQueryError`(audit 查询通用错误) | `errors[0].kind="audit"` | 200 |
| `AuditOptionalDomainError`(domain bundle 缺失,kernel-only wheel) | `errors[0].kind="audit_optional_domain"` | 200 |
| Authentication failure | (不进 envelope,直接 HTTP error) | 401 / 503 |
| 其他未捕获 exception | `app_v1` 全局 handler 包装为 `errors[0].kind="runtime"`,`details.message=str(exc)` | 200 |

**核心原则:** core / application 抛 raw exception(`ValueError` / `TypeError` / specific `*Error`);service 单向负责 envelope 包装,**不**反向把 envelope 概念渗入 core / application。

## 7. 关键行为契约（当前实现）

### 7.1 `view-facts`

- `include_audit=true` 时,`view.audit` 返回 `ProjectorAudit`(来自 core projector)
- `temporal_view` 已移除;传入会返回 shape error
- `view_name` 与 `view` 二选一;都不传则用 session 默认视图

### 7.2 derivation 与 rule runtime

- 运行链路也不接受 `temporal_view`(显式 shape error)
- `derivations/evaluate` 返回 candidate,供 `derivations/accept` 回传
- `derivations/accept` 返回 `AcceptResult` 的序列化结果(含 `diagnostics_contract_version`)
- `rules/compile-preview` 与 registry 读接口会保留已编译资产中的 `description / tags` 等声明元数据;service 不解释这些字段的运行语义

### 7.3 全局异常包络

未捕获异常由 `app_v1` 全局 handler 统一包装(HTTP 200):

- `ok=false`
- `errors[0].kind="runtime"`
- `errors[0].path="$"`
- `errors[0].details.message=str(exc)`

## 8. Cross-References

- Service 自身完整文档:[`src/service/docs/01_overview.md`](../../../service/docs/01_overview.md)
- Core 公共契约:[`04_public_contract_v1.md`](./04_public_contract_v1.md)
- Application 层 advanced importable surface:[`src/kernel/application/docs/01_overview.md`](../../application/docs/01_overview.md)
- Audit 包契约:[`src/kernel/audit/docs/03_audit_package_contract.md`](../../audit/docs/03_audit_package_contract.md)
- Batch 8 公开 surface 决议:[`docs/blueprints/archive/2026-05-06_public-surface.md`](../../../../docs/blueprints/archive/2026-05-06_public-surface.md)

## 9. 说明

- service v1 已不是 rules-only 薄层,而是 runtime / BFF 第一批可用接口。
- service 与 core 契约应同步维护:core contract 见 [`04_public_contract_v1.md`](./04_public_contract_v1.md)。
- Post-routemap state(2026-05-06):service 层未引入新 HTTP route 包装 Batch 3-7 application capabilities(per Batch 8 公开 surface 决议);Check / Diagnose / Fact Overlay / Why-not / ProofFrame / rule actions / round events / proof_frame_diff 全部走 advanced importable surface(Python in-process 调用 `kernel.application` / `kernel.audit`)。
