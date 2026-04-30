# Current Operational Memory

最后更新:2026-04-30

## 当前阶段

**v0.1 onboarding hardening 已 implemented + merged + pushed**:`oss-prep-v0.1` 现在包含 release-surface cleanup 与 onboarding hardening。`kernel.application` 是 canonical Python runtime authority,`kernel.sdk` 保持 Python product surface / authoring DSL / outward facade。

- 当前分支:`oss-prep-v0.1`
- 当前最新工作:v0.1 onboarding hardening blueprint 已 implemented,并通过 `--no-ff` merge 进入 `oss-prep-v0.1`。merge commit:`962f087`;hardening reference branch:`v0.1-onboarding-hardening` @ `62e68a1`。OS-prep v0.1 readiness、RC verification、source projection gate、onboarding hardening 均已完成;公开源码面通过 sanitized projection script 验证,长期管理方式已写入 `docs/architecture_principles.md`;但仍未创建 public repo、未 upload、未 tag。
- 当前 kernel release 基线:709 tests OK / 1 skip;`python -m ruff check src/kernel` clean;`scripts/project_release_surface.sh` 通过(261 projected files)。历史 5 段基线在 hardening 前为 1097 tests / 3 skips;hardening close-out 未重跑 agent/service/domains/benchmarks 全段。
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

- 15 files / 3399 LOC
- `kernel.application.__all__`:29 symbols
- SDK runtime files:query adapter shrank(`query_runtime.py` 357 -> 297),ingest grew to 800 due cache/fallback adapter plus hardening fallback reroute;`store.py` / `batch.py` / `facade.py` 仍为 large facade files,物理拆分 deferred

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
- Audit-delivery contract:implemented,仍留 active;`kernel.audit` query package / `service.static_ui` rendered static site / `domains.ecss.compliance` row assembly 三方交付边界已拆清。
- v0.1 release-candidate verification:implemented;verdict = `conditional pass`(`bf652a1`)。Hard gate 1.2 由 `e9dd311` inline fix(`src/kernel/tests/__init__.py`)解决。post-fix repository state 后续 RC 跑可期 `pass`。留 active,等真实 publish + 短期稳定窗口后归档。
- v0.1 onboarding hardening:implemented;已合入并 push 到 `origin/oss-prep-v0.1`(`962f087`)。落地内容包括 `Identity(primary_key=True)` 强制规则、application write cardinality、SDK `set/add` application write-plan adapter、D7 user journey probe、SDK error/repr polish、kernel-only docs boundary polish。留 active,等真实 publish + 短期稳定窗口后与其他 v0.1 蓝图一起归档。
- 早期 active 蓝图仍需后续 triage,不要把 memory 当成当前实现真相。

## 下一步方向

**优先级 1:OS-prep release close-out**

- v0.1 onboarding hardening:已完成并 push。当前 release-onboarding path 已由 `test_v01_onboarding_journey.py` 锁定:`ref → set/add → get → query → evaluate(native) → accept → export audit package`。`SDKStore.set/add` 现在走 application write-plan,会 materialize identity / exists;unmanaged e_ref 会抛 `SDKStoreError(code="UNRESOLVABLE_E_REF")`;set→multi / add→single 会抛 `CardinalityError`;Entity 必须至少有一个 `Identity(primary_key=True)`。
- v0.1 RC verification:已完成,verdict = `conditional pass`(`bf652a1`,2026-04-28)。dist artifact 已清除,release-day 时重新 build。
- release-surface cleanup:implemented。`scripts/project_release_surface.sh` + `scripts/release_surface_allowlist.txt` 生成 261-file sanitized projection,projection-built wheel 161 entries / 156 `kernel/` / 0 deny hits,clean venv quickstart 输出 `Alice`;v0.1 仍 wheel-only(no sdist),未 public repo push / 未 upload / 未 tag。
- release management model:私有 monorepo 是 source of truth;public `factpy-kernel` repo 是 projection artifact,不反向开发;PyPI wheel / public source release 从 verified projection tree 构建。长期规则见 `docs/architecture_principles.md` 的 `Release surface governance`。
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
8. [docs/blueprints/active/2026-04-29_v0.1-onboarding-hardening.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-29_v0.1-onboarding-hardening.md)
