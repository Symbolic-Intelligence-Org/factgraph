# Current Operational Memory

最后更新:2026-04-28

## 当前阶段

**Runtime-authority cleanup 已 implemented**:`kernel.application` 已扶正为 canonical Python runtime authority,`kernel.sdk` 保持 Python product surface / authoring DSL / outward facade。

- 当前分支:`oss-prep-v0.1`
- 当前最新工作:runtime-authority cleanup 已 merge 回 OS-prep baseline;OS-prep scope correction 记录 v0.1 OSS surface = kernel-only
- 当前测试基线:1093 tests 全绿(5 段:kernel 681 / agent 255 skipped 2 / service 42 / domains/ecss 99 / benchmarks 16)
- runtime cleanup blueprint:[2026-04-28_runtime-authority-cleanup.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md),status `implemented`,暂不归档
- OS-prep blueprint 仍 active/scoped;用户明确 OSS v0.1 仅包含 kernel 主体,所以 #1/#3/#7 已按 kernel-only surface 修正;#2 PyPI policy / #11 README OS framing / #12 optional-domain handling 可继续单独收口

## 当前 namespace

```
src/
  kernel/
    core/ sdk/ adapters/ audit/ authoring/ application/ tests/
  agent/
    extraction/ documents/ tools/ framework/ orchestrator/ session/ service/ tests/
  service/
    app_v1.py runtime_v1.py rules_v1.py registry_v1.py auth.py static_ui.py tests/
  domains/
    ecss/
      vcd.py temporal.py uncertainty.py sdk_helpers.py compliance.py tests/
tools/
  benchmarks/tests/
```

## 当前 layer truth

| Layer | 当前职责 |
|---|---|
| `kernel.core` | ledger/store/rules/evidence 等低层语义内核 |
| `kernel.application` | canonical Python runtime authority;拥有 read/write/query/ingest/compiled derivation runtime DTO + executor |
| `kernel.sdk` | Python product surface;拥有 schema/DSL authoring、`SDKStore` facade、snapshot/editor/batch outward objects、compatibility errors |
| `service` / `agent` | delivery / product consumers;production runtime code 不新增 SDK runtime import |
| `domains.ecss` | ECSS domain bundle;仍有 SDK ergonomic helper,属 domain facade 范围 |

## Runtime-authority cleanup 落地摘要

- commit 1:application protocol / executor surface pure add(query / ingest / derivation)
- commit 2a:application parity fixes(no SDK changes)
- commit 2b:derivation SDK adapter switch + batch delegate test rewrite
- commit 2c:query SDK adapter switch + SDK query policy tests
- commit 2d:ingest SDK adapter switch with identity-cache fallback + SDK ingest delegate tests
- commit 3:service/agent production SDK import boundary guard
- commit 4:docs alignment + blueprint implemented status close-out

完成后 application snapshot:

- 15 files / 3385 LOC
- `kernel.application.__all__`:29 symbols
- SDK runtime files:query adapter shrank(`query_runtime.py` 357 -> 297),ingest grew to 797 due cache/fallback adapter;`store.py` / `batch.py` / `facade.py` 仍为 large facade files,物理拆分 deferred

## 已验证的对外接口

| 入口 | 用途 | 状态 |
|---|---|---|
| `from kernel.sdk import Entity, Field, Identity, ...` | Python SDK product surface | 已验证 |
| `from kernel.application import *` | Python runtime authority surface | 已验证 |
| `from agent.extraction import extract_document` | Python 产品 API | 已验证 |
| `from agent.extraction import extract_document_from_ir` | pre-compiled schema IR 入口 | 已验证 |
| `agent.service.app:app` | extraction HTTP `/v1/extraction/documents` | 已验证 + tests |
| `service.app_v1:app` | kernel runtime / rules / registry HTTP routes | 已验证 |
| `from service.static_ui import render_audit_static_site` | 审计 HTML 渲染 | 已验证 |
| `from domains.ecss.compliance import ...` | ECSS 合规矩阵 + VCD predicates | 已验证 |

## 当前 active 蓝图状态

- Runtime-authority cleanup:implemented,留在 active,暂不 archive。
- OS-prep v0.1:scoped,已修正 OSS surface = kernel-only;下一步可继续 #2 PyPI policy / #11 README OS framing / #12 optional-domain handling。
- 早期 active 蓝图仍需后续 triage,不要把 memory 当成当前实现真相。

## 下一步方向

**优先级 1:OS-prep second unhold**

- #2 PyPI policy:决定 immediate / deferred / cadence-based,并把 `pyproject.toml` package discovery 收紧到 `kernel*` only;PyMuPDF / PyMuPDF4LLM 属 private agent surface,不得进入 kernel-only wheel metadata
- #11 README OS framing:改成 kernel-first external reader narrative;agent/service/domains 只能作为 private/future monorepo context
- #12 optional-domain handling:`AuditQuery.list_compliance_matrix(...)` 内部 owner split 仍成立,但 domains 不进 kernel-only wheel;需决定 hide / optional / private docs 处理
- #7 OpenAPI yaml 已因 kernel-only OSS surface closed: v0.1 不发布 HTTP/OpenAPI artifact

**优先级 2:primitive-contract follow-up**

- K traps:Query id/version asymmetry,where validation timing,Derivation head/target/head_vars 三形态
- pyreason adapter 当前仍 import SDK DSL primitives;后续可通过下沉 DSL primitive 或抽 runtime protocol 解耦

**不该在本阶段偷做**

- 不在 runtime cleanup 里改 OS-prep blueprint 决策项
- 不为行数目标强拆 `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py`
- 不重写全局 exception hierarchy
- 不把 SDK docs 中 application internal DTO 包装成 SDK public API

## 工程踩坑记录

- **Bash tool 实际是 zsh**:`for f in $VAR` 不 word-split,用 `while IFS= read -r f; do ... done <<< "$VAR"`
- **macOS BSD sed 不支持 `\b` word boundary**:bare-string token 替换用具体上下文
- **跨包搬迁文件相对 import 必须改绝对**:所有跨包搬迁 `.py` 都要扫
- **__init__.py re-exports 必须扫**:搬迁 `.py` 文件时检查原 package `__init__.py`
- **模块级跨包 import 可能引入加载耦合**:必要时使用 lazy import,但要记录边界

## 启动阅读顺序(新 session 用)

1. [本文件](/Users/zhenzhili/hnsm-backend/memory/current.md)
2. [runtime-authority cleanup blueprint](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md)
3. [AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) + [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md)
4. [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
5. [src/kernel/application/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/application/docs/README.md)
6. [src/kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/sdk/docs/README.md)
7. [docs/blueprints/active/2026-04-27_oss-prep-v0.1.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-27_oss-prep-v0.1.md)
