# Task Blueprint: Frontend API Documentation

- Status: archived
- Created: 2026-04-14
- Last Updated: 2026-04-14
- Related Modules:
  - `src/factpy_kernel/service/` (HTTP API)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/service/docs/01_overview.md](../../../src/factpy_kernel/service/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/02_runtime_sessions.md](../../../src/factpy_kernel/service/docs/02_runtime_sessions.md) / `03_runtime_queries_views.md` / `04_rules_registry.md` / `05_extraction.md`
- Audit Log:
  - [2026-04-14_frontend-api-documentation.audit.md](./2026-04-14_frontend-api-documentation.audit.md)

## 1. Problem

上一轮 `2026-04-14_consumer-usage-handoff`(已归档)交付了 `extract_document()` 使用手册 + HTTP 端点 DTO 契约,已经够一个前端开发者"摸着 05_extraction.md 发请求"。但同事明确说需要**完整的 API 文档**。

当前实际状况:

- 48 个 `/v1/*` 路由分散在 5 份 DTO 文档里(01 overview + 02/03/04/05)
- **没有单一的"前端集成入口"页** — 前端要先读 01 再下钻 02-05,再自己拼 envelope 语义 + auth flow + 典型调用顺序
- **没有 checked-in OpenAPI spec** — 虽然 FastAPI 运行时提供 `/docs`(Swagger UI)和 `/openapi.json`,但:
  - 要先启后端才看得到
  - `/openapi.json` 是 auto-generated,很多 handler 返回 `dict[str, Any]` → schema 退化成 `additionalProperties: true`,对 frontend 几乎无价值
  - 无法走 CI / 静态托管 / Postman import 链路
- **Envelope 类型无公开 schema 定义** — `{ok, errors, meta, result}` 每次要前端自己重推 TS interface
- Multipart + JSON-string-in-form(extraction 端点)这种形态 FastAPI auto-spec 表达不精确

"够用"和"前端能直接对着干活"之间的 gap 是明确的,就是本蓝图要补。

## 2. Goals

- 前端同事**读一份文档就能搞懂 envelope 结构、auth 流程、典型调用链路**
- 有一份**可被工具消费的机读 OpenAPI spec**(yaml,checked-in,git 里能看到 diff)
- 所有 48 个 `/v1/*` 路由在机读 spec 和 human guide 里都**精确出现且语义一致**
- 生成 / 校验机读 spec 的流程是**可复现的**(有脚本、有 CI 可用钩子)

## 3. Non-goals

- **不生成 TypeScript types** — 前端技术栈未定,且 TS 生成工具链是前端侧的选择(`openapi-typescript` 等);提供 OpenAPI yaml 已足以让前端自己跑生成
- **不建静态文档站(MkDocs / ReDoc / Docusaurus)** — 本轮交付 yaml + guide,站点是后续可选工作
- **不写 Postman collection** — 导出为 json 不增加实质价值,前端工具一般能直接 import OpenAPI
- **不改 handler 签名**(不给 `dict[str, Any]` 加 pydantic response model)—— 这是独立的大项工作(48 个路由全覆盖),属于"让 FastAPI auto-spec 变好"的方向,和本轮"手写精确 spec"的方向并行,scope 分开
- **不修 envelope 契约** — 当前 `{ok, errors, meta, result}` 就是契约;本轮只是把它显式化
- **不改 CORS / auth 边界** — 运行时配置不在本轮
- **不翻译英文**
- **不加 rate limit / versioning / deprecation 元信息** — 现在没有这些策略,不要凭空编造
- **不做 runtime session 之外的跨请求状态管理文档**(已经由 02 覆盖)

## 4. Current Context

- 当前路由集中点:`src/factpy_kernel/service/app_v1.py`(48 条 `@app.{get,post,delete,put}`)
- 当前 FastAPI auto-spec:运行时 `GET /openapi.json` 可拿,但未 checked-in
- 当前 DTO 真相源:`service/docs/02-05_*.md`,形状说明齐全但不是机读格式
- 当前 auth:`require_api_key` middleware + `X-FactPy-API-Key` header + `FACTPY_KERNEL_API_KEYS` env + `FACTPY_KERNEL_AUTH_DISABLED` 开关
- 当前 envelope:`{ok: bool, errors: [{kind, path, details}], meta: {}, ...}`;extraction 端点 额外用 `HTTP 422 / 500` 状态码(02-04 全 200)

## 5. Proposed Shape

**七份交付物,三个层级:**

### 内容层(service/docs/)

- `src/factpy_kernel/service/docs/06_frontend_integration.md`(新增):面向前端开发者的集成指南。组织方式:
  - 0 前置:base URL / env / 认证 header / envelope 结构 / 错误 kinds 清单
  - 1 典型调用链路(3-4 个):
    - (a) 抽取文档:单次 `POST /v1/extraction/documents`
    - (b) 打开 session + 写 facts + 查 claims
    - (c) 打开 session + 跑 rule + evaluate/accept candidate
    - (d) registry 只读查询
  - 2 envelope 解包的前端代码片段(fetch + 错误分支)
  - 3 状态码速查表(200 / 401 / 422 / 500 / 503 各自触发条件)
  - 4 对照 `docs/api/openapi.yaml`:spec 是权威契约,本文档是"怎么用 spec"
  - 5 已知限制 / 前端侧陷阱(multipart + JSON-string-in-form、不同端点 HTTP status code 不一致)

### 机读层(docs/api/)

- `docs/api/openapi.yaml`(新增):手写 OpenAPI 3.0 spec
  - 48 个路由全部列出,按 01_overview 的分组组织(rules / runtime session / runtime queries / runtime views / runtime rule-derivation-package / registry / extraction)
  - 定义可复用的 schema components:`Envelope`(success / error 两个变体)、`Error`、`RuntimeSession`、`FactDraftSpec`、`ExtractionResult` 等
  - Security scheme:`ApiKeyAuth` (in: header, name: X-FactPy-API-Key),所有 `/v1/*` 引用
  - **定义可复用的 response components `UnauthorizedError`(401)和 `AuthNotConfiguredError`(503),并在每个 `/v1/*` operation 的 `responses` 里显式引用这两条**(因为这是所有受认证路由的稳定契约,不是 per-endpoint 行为)
  - Multipart 端点(extraction)精确表达 file + options(JSON string 但语义是 object)

### 工具 + 索引层

- `scripts/export_openapi.py`(新增):**校验** checked-in yaml 的小工具;从 `app_v1.app` 拉 live spec 和 checked-in yaml 做 diff 提示。**比较粒度必须是 `(path, method)` 集合,不能只比 path** — 因为 service 里存在同 path 多 method 的路由(如 `/v1/runtime/sessions/{session_id}` 同时有 `GET` 和 `DELETE`),path-only diff 会漏掉 method 漂移。**不自动覆盖** yaml(因为我们手写的版本精度高于 auto-generated,不想被覆盖)
- `src/factpy_kernel/service/docs/README.md`(更新):"当前文档"列表加 `06_frontend_integration.md`
- `src/factpy_kernel/service/docs/01_overview.md`(更新):§3 详细 DTO 文档列表加 06;在文首补一句"前端/机读 API 参考见 `06_frontend_integration.md` + `docs/api/openapi.yaml`"
- `docs/README.md`(更新):"当前实现文档"列表新增 06;新建或复用"API 机读规约"小节指向 `docs/api/openapi.yaml`
- `README.md`(根,更新):HTTP 服务章节(§C)末尾加"完整 API 文档:`docs/api/openapi.yaml` + `src/factpy_kernel/service/docs/06_frontend_integration.md`"

## 6. Boundaries And Invariants

- **必须保持**:
  - 现有 02-05 的 DTO 描述不被降级 / 删除;06 是上层 guide,spec 是机读契约,两者都指向同一份 handler 行为真相
  - 01 overview 的路由清单继续作为 navigation 而非 DTO 来源
  - `/openapi.json`(FastAPI auto)继续保留为运行时 debug 工具,不删,但不作为权威
  - `.gitignore` 不放 `/docs/` 进去(要 docs/api/openapi.yaml 可被提交)
- **明确不做**:
  - 不为了 spec 精度去改 handler 签名
  - 不为了前端便利去改变 envelope 结构
  - 不承诺 spec 会在每次 handler 改动后自动刷新;维护靠人 + `export_openapi.py` 的 diff 提示
- **兼容性**:
  - 零代码行为改动 = 1023 tests 仍绿(`scripts/export_openapi.py` 不在 test discovery path,且不导入测试模块)

## 7. Acceptance

- [ ] `docs/api/openapi.yaml` 覆盖全部 48 个 `/v1/*` 路由,且 `(path, method)` 对与 `app_v1.app.openapi()` live spec 完全一致
- [ ] openapi.yaml 通过 OpenAPI 3.0 validator(`openapi-spec-validator docs/api/openapi.yaml` 或等价工具)
- [ ] 每个 `/v1/*` operation 的 `responses` 都显式引用可复用的 `UnauthorizedError`(401) 与 `AuthNotConfiguredError`(503) components
- [ ] `06_frontend_integration.md` 含 ≥3 个完整调用链路示例 + envelope 解包代码片段 + HTTP 状态码速查表
- [ ] `scripts/export_openapi.py` 在 `(path, method)` 粒度比较 live spec 与 checked-in yaml;一致时 exit 0,漂移时打印漏/多的 `(path, method)` 对并 exit 1;**不**自动覆盖 yaml
- [ ] `service/docs/README.md` 登记 06;`01_overview.md` §3 / 文首补充指向 06 + openapi.yaml
- [ ] `docs/README.md` 和 `README.md`(根)都加了指向 openapi.yaml 的一行
- [ ] `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests` 仍 1023 绿

## 8. Implementation Plan

1. **`docs/api/openapi.yaml`(手写,最底层)**:以 01_overview 的 §4 路由表为骨架,逐组写 path 条目;schema components 参考 02-05 现有示例 + extraction_v1.py 实际返回形状。routes 写完后在文末补 `securitySchemes`,在 `components.responses` 下定义 `UnauthorizedError`(401)和 `AuthNotConfiguredError`(503),每条 operation 的 `responses` 字段显式引用这两条。
2. **`scripts/export_openapi.py`(新增)**:bootstrap `factpy_kernel.service.app_v1.app`,调 `app.openapi()` 拿 live dict;从 live spec 抽 `{(path, method.upper()) for path, ops in paths.items() for method in ops if method in ALLOWED_METHODS}`,从 checked-in yaml 抽同形集合;双向 diff。一致 → exit 0;漂移 → 分类打印 "missing in yaml" / "extra in yaml" 的 `(path, method)` 对并 exit 1。不写入文件。
3. **本地跑 diff**:用上一步脚本对 48 个路由 × method 维度对账;补漏的 `(path, method)` 对,修掉 typo。
4. **`06_frontend_integration.md`(新增)**:按 §5 的 6 小节结构写;代码片段用 `fetch(...)` 伪代码 + envelope 解包;状态码速查表参照 02-05 里分散记载的情况整合。
5. **`service/docs/01_overview.md`(更新)**:§3 列表加 06;文首认证边界段落下方加一行指向 `docs/api/openapi.yaml`。
6. **`service/docs/README.md`(更新)**:"当前文档"列表增 06。
7. **`docs/README.md`(更新)**:"当前实现文档"加 06;在顶层"入口"下加一行"`docs/api/openapi.yaml` — HTTP API 机读契约(OpenAPI 3.0)"。
8. **`README.md`(根,更新)**:§C HTTP 服务块末尾追加"完整 API 契约:`docs/api/openapi.yaml` + `src/factpy_kernel/service/docs/06_frontend_integration.md`"。
9. **最终验收**:
   - `python scripts/export_openapi.py` 无 diff(路由 48 个 `(path, method)` 对完全对齐)
   - 通读 yaml 确认每个 operation 都挂上了 `UnauthorizedError` / `AuthNotConfiguredError` 两条 response refs
   - `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"` → 1023 绿
   - `grep -rn "/v1/extraction/documents" docs/ README.md src/factpy_kernel/*/docs/` 一致
   - 用 `openapi-spec-validator`(如有) 或手动验一下 yaml 格式合法

## 9. Docs To Update

- `docs/api/openapi.yaml`(新增)
- `scripts/export_openapi.py`(新增 — 不算 docs 但算交付物)
- `src/factpy_kernel/service/docs/06_frontend_integration.md`(新增)
- `src/factpy_kernel/service/docs/README.md`(更新)
- `src/factpy_kernel/service/docs/01_overview.md`(更新)
- `docs/README.md`(更新)
- `README.md`(根,更新 HTTP 章节尾部一行)

共 7 份交付物(3 新增 + 4 更新)。

## 10. Outcome / Deviations

**Implemented + archived 2026-04-14 per draft v2 scope(7 交付物,3 层,零产品代码改动)。**

落地文件:

- `docs/api/openapi.yaml`(新增,~720 行):手写 OpenAPI 3.0 spec,45 个 unique path × 48 个 `(path, method)` operation。定义 3 条可复用 response components(`Envelope200` / `UnauthorizedError` / `AuthNotConfiguredError`)+ 11 个 schema components(`Envelope` / `Error` / `ErrorEnvelope` / `WriteRequest` / `OpenSessionEnvelope` / `SessionSummaryEnvelope` / `ExtractionResult` / `ExtractionEntity` / `FactDraftSpec` / `MergeEvent` / `ExtractionResultEnvelope`)+ 1 个 SessionId path parameter。每个 `/v1/*` operation 显式列出 401 + 503 refs。
- `scripts/export_openapi.py`(新增,~100 行):`(path, method)` 粒度双向 diff。bootstrap `app_v1.app.openapi()` 抽 live 集合,读 yaml 抽 checked-in 集合,比较后分类打印 missing / extra。exit 0 当前对齐 / exit 1 漂移 / exit 2 runtime 异常。不自动覆盖 yaml。
- `src/factpy_kernel/service/docs/06_frontend_integration.md`(新增,~230 行):6 章(前置 / 典型调用链路 / 错误处理模板 / 前端陷阱 / TS 生成指引 / 漂移守卫)。含 4 个完整调用链路示例(extraction / session+writes / rules run+derivations accept / registry)+ envelope 解包代码 + HTTP 状态码速查表 + 常见 `kind` 表。
- `src/factpy_kernel/service/docs/README.md`(更新):"当前文档"列表新增 06。
- `src/factpy_kernel/service/docs/01_overview.md`(更新):文首添加前端/机读 API 参考指引,§3 详细 DTO 文档列表新增 06,"最后更新"日期推进到 2026-04-14。
- `docs/README.md`(更新):"当前实现文档"列表加 06 + `docs/api/openapi.yaml`。
- `README.md`(根,更新):§C HTTP 章节末尾新增"完整 API 文档"小段,指向 openapi.yaml + 06 + 漂移守卫脚本。

验收结果(§7):

- [x] `docs/api/openapi.yaml` 覆盖全部 48 个 `(path, method)` 对,与 live FastAPI spec 完全一致(`python scripts/export_openapi.py` exit 0)
- [x] openapi.yaml 通过 `openapi-spec-validator` 3.0 校验
- [x] 48/48 operations 显式引用 `UnauthorizedError`(401) + `AuthNotConfiguredError`(503)(programmatic 交叉验证)
- [x] `06_frontend_integration.md` 含 4 个调用链路(>3 要求)+ envelope 解包 + 状态码速查表
- [x] `scripts/export_openapi.py` (path, method) 粒度 diff,不覆盖 yaml,exit 码正确
- [x] 两个索引 `service/docs/README.md` + `01_overview.md` §3 + 文首指引齐备
- [x] `docs/README.md` + `README.md` 根指向 `docs/api/openapi.yaml` + 06
- [x] `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests` → **1023 tests 全绿**(零 regression,与 blueprint "零代码改动" 边界一致)

与 blueprint 的差异:无实质 scope 偏离。唯一小调整是 `rest_terms` / `field_values` 的 items schema 从原设计的 `oneOf: [string, number, boolean, null]` 改为 `nullable: true` + `oneOf: [string, number, boolean]`——因为 OpenAPI 3.0 不支持 `type: null`,`nullable` 是该版本的 idiomatic 表达;语义等价,spec validator 接受。

归档说明:blueprint + audit 同时从 `active/` 迁到 `archive/`,basename 保留。
