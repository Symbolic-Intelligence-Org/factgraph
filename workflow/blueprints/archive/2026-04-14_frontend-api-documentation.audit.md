# Task Blueprint Audit: Frontend API Documentation

- Blueprint: [2026-04-14_frontend-api-documentation.md](./2026-04-14_frontend-api-documentation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-14 | draft | Blueprint created | User asked for 完整的 API 文档 for frontend. Current state:48 /v1 routes covered by 01-05 DTO docs but no single frontend entry page, no checked-in OpenAPI spec, no envelope schema definitions. Proposed scope: hand-written `docs/api/openapi.yaml` + `service/docs/06_frontend_integration.md` + `scripts/export_openapi.py` diff tool + 4 index/overview updates. 共 7 个交付物。Non-goals:TypeScript、docs site、Postman、handler 签名改动。 |
| 2026-04-14 | draft | Scope review v1 | User flagged 3 findings: P1 — `scripts/export_openapi.py` 在 path-only 粒度下会漏掉同 path 多 method 的漂移(例:`/v1/runtime/sessions/{session_id}` 同时有 GET+DELETE),必须提升到 `(path, method)` 粒度;P1 — `openapi.yaml` 需要显式覆盖通用 401 / 503 auth 响应,靠 `ApiKeyAuth` security scheme 本身不够,前端要把这俩 failure 当稳定契约消费;P2 — `§5 Proposed Shape` 头部"四份文件"与正文 7 个交付物矛盾。全部修复。User 同意手写 yaml 路线 + diff-only 脚本,不提前上 ReDoc/MkDocs。 |

## Decision Notes

- 2026-04-14 — **draft v2**(scope review v1 回应)
  - **P1 diff 粒度**:`§5` 工具层描述、`§7` 验收条目、`§8` step 2+3+9 全部从"path-level diff"升级为 "`(path, method)` 集合 diff"。明确双向 diff + 分类输出 "missing in yaml" / "extra in yaml"
  - **P1 401/503 覆盖**:`§5` 机读层新增一条"定义 `UnauthorizedError`(401) / `AuthNotConfiguredError`(503) response components,并在每个 operation 的 `responses` 里显式引用";`§7` 新增对应 acceptance 条目;`§8` step 1 补充"components.responses 定义 + per-operation 引用"子任务;step 9 验收新增通读 yaml 确认 operation-level 引用
  - **P2 头部数量一致**:`§5` 开头摘要从"四份文件,三个层级"改为"七份交付物,三个层级",与 `§9`、audit 里的 7 份对齐
  - 用户表态:同意手写 yaml 路线 / 同意 diff-only 脚本策略 / 不提前把 ReDoc/MkDocs 站点放进 scope

- 2026-04-14 — **scoped → implementing**:用户 approve draft v2,scope 冻结,切到 implementing。执行顺序按 `§8 Implementation Plan`:live spec dump → openapi.yaml → export_openapi.py → diff 对账 → 06 guide → 索引与 README 更新

- 2026-04-14 — **implementing → implemented → archived**:7 个交付物落地;3 项机读校验通过(`(path, method)` 对齐 48/48、OpenAPI 3.0 validator 通过、48/48 operation 显式 401+503 引用);1023 tests 仍绿。唯一偏离:`oneOf` list 里的 `{type: "null"}` 改成 `nullable: true` + 三类型 oneOf——原因是 OpenAPI 3.0 不支持 `type: null`,用 `nullable` 达成等价语义。Blueprint + audit 同步归档。

- 2026-04-14 — **draft v1**
  - **Why hand-write OpenAPI instead of relying on FastAPI auto-generated**:当前 handler 返回 `dict[str, Any]`,FastAPI auto-spec 退化成 `additionalProperties: true`,对 frontend 几乎无价值。给 48 个 handler 加 pydantic response model 是更大的独立工作;本轮选择手写精度高的 spec,把"auto-spec 改造"留给单独蓝图。
  - **Why checked-in yaml instead of runtime-only `/openapi.json`**:运行时 endpoint 依赖先启服务,不进 git,CI / static docs / Postman import 都用不上。Checked-in yaml 可被前端 CI、类型生成工具、文档站直接消费。
  - **Why diff tool (not auto-regenerate)**:手写 spec 精度高于 auto-generated;如果脚本自动覆盖,会每次把精度降回 auto-generated 水平。Diff 只提示差异让人手动修。
  - **不覆盖 TypeScript 生成**:前端栈未定;`openapi-typescript` 等工具前端侧自选即可。
  - **不做静态 docs 站**:ReDoc / MkDocs 是 rendering 选择,不在本轮 MVP scope;openapi.yaml 够前端直接 import 到 Swagger Editor / Stoplight 等工具。
  - **envelope status code 不一致是已知事实**:02-04 全 200 + ok=false 表达错误,05 用 401/422/500。Guide 要说清这个差异,但不收敛(改会动 handler)。
  - 测试基线必须保持 1023 绿:本轮无 code change 预期;`scripts/export_openapi.py` 不进 test path。
