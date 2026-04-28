# Current Operational Memory

最后更新:2026-04-28

## 当前阶段

**Runtime-authority cleanup 已 implemented**:`kernel.application` 已扶正为 canonical Python runtime authority,`kernel.sdk` 保持 Python product surface / authoring DSL / outward facade。

- 当前分支:`oss-prep-v0.1`
- 当前最新工作:OS-prep v0.1 readiness blueprint 已 implemented;新建 v0.1 release-candidate verification blueprint(draft,no-publish)。v0.1 OSS surface = kernel-only,PyPI metadata 只暴露 kernel package,README 已 kernel-first,`src/kernel` Ruff 已 blocking
- 当前测试基线:1097 tests 全绿,3 skips(5 段:kernel 685 skipped 1 / agent 255 skipped 2 / service 42 / domains/ecss 99 / benchmarks 16)
- runtime cleanup blueprint:[2026-04-28_runtime-authority-cleanup.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md),status `implemented`,暂不归档
- OS-prep blueprint 仍在 active,但 status 已 implemented。用户明确 OSS v0.1 仅包含 kernel 主体,所以 #1/#2/#3/#4/#7/#11/#12 已按 kernel-only surface 收口。#4 默认名锁为 `factpy-kernel`,但真实 PyPI reservation 仍需 release day upload / trusted publishing。剩余工作主要是 release-day checklist 与 staged CI gate 后续提升。

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
- OS-prep v0.1:implemented,仍留 active;#2 packaging hardening / #11 README / #12 optional-domain handling / #8 kernel Ruff gate 已落地。
- v0.1 release-candidate verification:draft;用于判定代码和 wheel artifact 是否可进入 release-day workflow,不发布、不 tag、不 reserve PyPI name。
- 早期 active 蓝图仍需后续 triage,不要把 memory 当成当前实现真相。

## 下一步方向

**优先级 1:OS-prep release close-out**

- v0.1 RC verification:先跑 no-publish wheel build/inspect/clean install/README quickstart/audit optional-domain smoke,再给 pass/conditional pass/block verdict
- #4 package name:默认锁 `factpy-kernel`;2026-04-28 exact-name check 当前可用,但 publish time 仍需重跑并通过首次 upload / trusted publishing 完成 reservation
- #8 CI gate follow-up:`src/kernel` Ruff 已 blocking;service/tools Ruff(62 errors)与 mypy(`src/kernel`:385 errors / 73 files,tests 占 280)仍需逐步清 baseline 后升 blocking
- release validation:按 README 的 kernel-only install path 和 `test_wheel_kernel_only_packaging.py` 做 wheel inspection
- #2/#11/#12 已落地:package discovery `kernel*` only;README kernel-first;`AuditQuery.list_compliance_matrix(...)` 缺少 `domains.ecss` 时抛 `AuditOptionalDomainError`
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
