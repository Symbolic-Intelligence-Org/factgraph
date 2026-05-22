# Task Blueprint: Consumer Usage Handoff — extract_document + HTTP API

- Status: archived
- Created: 2026-04-14
- Last Updated: 2026-04-14
- Related Modules:
  - `src/factpy_kernel/agent/extraction/` (Python product API)
  - `src/factpy_kernel/service/` (HTTP API)
  - `examples/` (demo entry)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/agent/extraction/docs/README.md](../../../src/factpy_kernel/agent/extraction/docs/README.md)(current truth for extraction)
  - [src/factpy_kernel/service/docs/01_overview.md](../../../src/factpy_kernel/service/docs/01_overview.md)(current truth for service)
- Audit Log:
  - [2026-04-14_consumer-usage-handoff.audit.md](./2026-04-14_consumer-usage-handoff.audit.md)

## 1. Problem

Extraction/agent 管道的能力建设阶段已结束(`extract_document()` + `POST /v1/extraction/documents` 都通了,1023 tests 绿)。同事现在要试用这条管道,但当前仓库对外信息严重脱节:

- 仓库根 `README.md` 只有 3 行,把人直接扔进 `docs/README.md`(内部文档索引)
- `demo/README.md` 写的是已归档的 Streamlit 路径(今天清理后被删除了)
- `extract_document()` 的使用方式只存在于 notebook 和已归档蓝图里,没有独立的使用手册
- `POST /v1/extraction/documents` 路由**既没有在 `service/docs/01_overview.md` 的路由表里,也没有独立 DTO 契约文档** — 前端/同事拿不到 curl/schema/错误码
- 2026-04-14 真实 DORA PDF 跑的踩坑(`.env` 格式陷阱、staging 过细要过滤、Mistral 免费 tier 限速)目前只在 session 对话里,没沉淀

同事接手的 blast radius 是"读 30 分钟找不到入口、试 3 次报错放弃"。

## 2. Goals

- 同事 15 分钟内能跑通一次真实 PDF 抽取(Python 或 HTTP 二选一)
- `extract_document()` 有独立 USAGE 文档,涵盖最小示例、参数语义、返回值、常见失败模式
- `POST /v1/extraction/documents` 有独立 DTO 契约文档(请求 / 200 / 422 / 500 示例 + curl)
- `service/docs/01_overview.md` 路由表补齐 extraction 路由
- 仓库根 `README.md` 重写成三岔路(Python API / HTTP API / notebook)入口,含 install + env 配置 + 已验证模型表
- `docs/README.md` 索引同步新增条目

## 3. Non-goals

- **不新增代码** — 纯文档任务;发现接口不合理只记录,不改
- **不翻译英文** — 项目中文为主,保持一致
- **不写运维文档**(部署/监控/扩展性)——同事只是要"能本地跑通 + 能发 HTTP 请求"
- **不重写 notebook 08/09 / CLI 脚本** — 它们已经是可用 demo
- **不 triage session 2 遗留的 active 蓝图** — 不在本轮 scope,单独一轮
- **不修复 extraction schema 的 `.title` / `.exists` 语义陷阱** — 记录在 USAGE.md"已知限制"里,不改代码
- **不出英文版 SECURITY / CONTRIBUTING** — 本轮只管"使用"

## 4. Current Context

- 当前 extraction 入口:`extract_document()` / `extract_document_from_ir()` 在 `src/factpy_kernel/agent/extraction/api.py`
- 当前 HTTP handler:`extract_document_endpoint(...)` 在 `src/factpy_kernel/service/extraction_v1.py`,route 在 `app_v1.py`
- 当前模块真相 doc:`src/factpy_kernel/agent/extraction/docs/README.md`(scope/responsibilities,但不是使用手册)
- 当前 service overview:`src/factpy_kernel/service/docs/01_overview.md`(没列 `/v1/extraction/documents`)
- 当前 demo:`examples/09_dora_document_extraction.ipynb` + `examples/dora_pdf_extract.py`(已跑通)
- 已踩坑记录:Mistral `X-FactPy-API-Key` header、`.env` 解析(`KEY = "val"` 空格)、staging 801 段过细、免费 tier 限速、auth friction
- 已归档参考:`docs/references/cross-provider-entity-benchmark-report.md`(Mistral Small F1=78% 推荐依据)

## 5. Proposed Shape

七份文档,三个层级:

**Top-level 入口层(仓库根)**

- `README.md` 重写:项目一句话 + 三岔路导航 + install + env + 已验证模型矩阵 + troubleshooting(已踩过的坑)

**模块真相层(`src/factpy_kernel/*/docs/`)— 新增 + 更新**

- `src/factpy_kernel/agent/extraction/docs/USAGE.md`(新增):`extract_document()` 完整使用手册。**是面向 consumer 的手册,不替代 `README.md` 的 scope/responsibilities 口径**
- `src/factpy_kernel/agent/extraction/docs/README.md`(更新):在文档入口区增加 USAGE.md 条目,让模块 README 能索引到新加的使用手册
- `src/factpy_kernel/service/docs/05_extraction.md`(新增):`POST /v1/extraction/documents` 的 DTO 契约。**与同目录 `02_runtime_sessions.md` / `03_runtime_queries_views.md` / `04_rules_registry.md` 风格对齐**
- `src/factpy_kernel/service/docs/README.md`(更新):在"当前文档"列表中增加 `05_extraction.md` 条目
- `src/factpy_kernel/service/docs/01_overview.md`(更新):在 §4 路由分组下新增 "4.7 extraction" 条目;在 §2 模块结构下登记 `extraction_v1.py`

**索引层(`docs/`)— 更新**

- `docs/README.md`(更新):在"当前实现文档"列表中增加 `service/docs/05_extraction.md` 条目

## 6. Boundaries And Invariants

- **必须保持**:
  - 模块真相 doc(`agent/extraction/docs/README.md`)的 scope/responsibilities/non-responsibilities 口径不变;USAGE.md 是补充,不是替代
  - HTTP DTO 契约文档结构与现有 `02/03/04_*.md` 对齐
  - 仓库根 `README.md` 遵循 [AGENTS.md](../../../AGENTS.md) 允许的根文件清单(`README.md` 本身允许)
- **明确不做**:
  - 不生成 OpenAPI schema(不在 scope,HTTP handler 当前是手写 envelope)
  - 不重新定义 extraction 公开表面(`__all__`),沿用 `agent/extraction/__init__.py` 当前导出
  - 不承诺未实现的能力(例如 async job 接口、批量文件接口)
- **兼容性**:
  - 不改 API 签名 = 不影响 1023 tests
  - 所有新文档引用的路径必须是当前真实文件(不要引用移除中的 `demo/` 或未实现的 endpoint)

## 7. Acceptance

- [ ] `README.md`(仓库根)重写完成,三岔路 + install + env + 已验证模型 + troubleshooting 齐全
- [ ] `agent/extraction/docs/USAGE.md` 含最小示例 + 参数表 + 返回值结构 + 常见失败诊断 + 已知限制
- [ ] `agent/extraction/docs/README.md` 入口区登记 USAGE.md
- [ ] `service/docs/05_extraction.md` 含请求形状 + 200/422/500 示例 + curl 示例
- [ ] `service/docs/README.md` 文档列表登记 05_extraction.md
- [ ] `service/docs/01_overview.md` §2 结构表和 §4 路由表都加了 extraction 条目
- [ ] `docs/README.md` 增加新条目
- [ ] 没有新代码改动;`PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests` 仍然 1023 绿
- [ ] 新文档中的所有路径 / 命令 / 环境变量都真实可用(不虚构 endpoint、不误写 env var 名)

## 8. Implementation Plan

1. **`service/docs/05_extraction.md`(新建)**:最底层的契约文档,先写;参考 `02_runtime_sessions.md` 结构(请求 → 成功响应 → 错误响应 → 字段语义 → curl 示例)。此文件一写定,后面所有引用它的文档才稳。
2. **`service/docs/README.md`(更新)**:在"当前文档"列表加 `05_extraction.md` 条目。
3. **`service/docs/01_overview.md`(更新)**:§2 结构表加 `extraction_v1.py` 行;§4 加 "4.7 extraction" 小节引用 05。
4. **`agent/extraction/docs/USAGE.md`(新建)**:比契约文档更宽,面向产品用户;内容 ≈ `extract_document()` 签名详解 + 6 个参数的"何时用/不用" + 返回值字段对照 + 至少 2 个完整示例(基础 + 带 entity_descriptions) + 常见失败 3 类(Unauthorized / staging_error / resolution empty) + 已知限制(.title / .exists / Mistral 免费 tier 速率)。
5. **`agent/extraction/docs/README.md`(更新)**:文档入口区登记 USAGE.md。
6. **`README.md`(重写仓库根)**:一句话定位 + 三岔路(A. examples/09 notebook;B. Python `extract_document()`;C. HTTP 服务)+ install + env 配置(包含 `.env` 格式陷阱)+ 已验证模型表(Mistral Small 默认 + GPT-4.1 备选)+ troubleshooting 段落。保持简短,不超 ~200 行。
7. **`docs/README.md`(更新索引)**:在"当前实现文档"列表加 `service/docs/05_extraction.md` 条目;在"入口"附近不增加(USAGE.md 和 README.md 不进这个索引,它们通过各自的 README 链接到)。
8. **最后检查**:跑一次 `grep -rn "/v1/extraction/documents" docs/ src/factpy_kernel/*/docs/ README.md` 确保路径一致;跑一次 `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests` 确认没有误动代码。

## 9. Docs To Update

- `README.md`(仓库根,重写)
- `src/factpy_kernel/agent/extraction/docs/USAGE.md`(新增)
- `src/factpy_kernel/agent/extraction/docs/README.md`(更新 — 登记 USAGE.md)
- `src/factpy_kernel/service/docs/05_extraction.md`(新增)
- `src/factpy_kernel/service/docs/README.md`(更新 — 登记 05_extraction.md)
- `src/factpy_kernel/service/docs/01_overview.md`(更新 §2 + §4)
- `docs/README.md`(更新"当前实现文档"列表)

## 10. Outcome / Deviations

**Implemented 2026-04-14 per draft v3 scope(7 docs,3 层,零代码改动)。**

落地文件:

- `README.md`(仓库根,重写,~125 行):三岔路(notebook / Python API / HTTP 服务)+ install + env + 已验证模型表 + troubleshooting(`.env` 陷阱、401、500 resolution empty、PDF 切段过细)
- `src/factpy_kernel/agent/extraction/docs/USAGE.md`(新增,~180 行):产品使用者手册,含最小示例、参数表、返回值结构、3 类常见失败诊断、3 条已知限制(`.title` 冲突 / `.exists` 噪声 / staging 过细)
- `src/factpy_kernel/agent/extraction/docs/README.md`(更新):增加"文档入口"段,登记 USAGE.md 指向
- `src/factpy_kernel/service/docs/05_extraction.md`(新增,~120 行):HTTP DTO 契约,含 multipart 请求形状、options 字段表、200/422/500 envelope 示例、curl 示例、错误诊断
- `src/factpy_kernel/service/docs/README.md`(更新):"当前文档"列表新增 05_extraction.md
- `src/factpy_kernel/service/docs/01_overview.md`(更新):§2 结构表加 `extraction_v1.py`,§3 详细 DTO 文档列表加 `05_extraction.md`,§4 新增 "4.7 extraction" 小节
- `docs/README.md`(更新):"当前实现文档"列表加 `USAGE.md` + `05_extraction.md` 两个条目

验收检查:

- [x] 7 份文档全部落地
- [x] `PYTHONPATH=src python -m unittest` **1023 tests 全绿**(与预期一致,无代码改动 = 无 regression)
- [x] `grep /v1/extraction/documents` 跨 `docs/` + `src/.../docs/` + `README.md` 一致
- [x] 新文档中的命令 / env var / endpoint 路径都是真实可用(不含虚构 endpoint)

与 blueprint 的差异:无;按 §8 Implementation Plan 的 8 步顺序完整执行。

归档说明:blueprint 与 audit 一同从 `active/` 迁到 `archive/`,保持 basename 不变。
