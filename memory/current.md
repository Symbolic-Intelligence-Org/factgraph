# Current Operational Memory

最后更新:2026-05-04(Check shipped + engine-extension Wave 1 closed through `44eefab`;Diagnose §8 Step 5 souffle dispatch at `8a6c449`;handoff baseline 见 [session_handoffs/2026-05-04.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-05-04.md))

## 当前阶段(2026-05-03 — REDESIGN BASE)

**本分支 `v0.1-redesign-2026-05-03` 是 active development 起点**,从 `master`(`8af9da9`)起,clean baseline:
- src 代码:pre-rule-replay 状态(无 `kernel.sdk.replay*`、无 `kernel.authoring.module_ir`、无 `disabled_locators` threading)
- memory + docs:master 状态(`v0.1 onboarding hardening implemented + merged` 时刻)

### 为什么有这个分支(2026-05-03 RESET 决定)

2026-05-01..02 共 ~42 小时窗口内试做了 v0.1.x rule-replay 设计实验(v0.1.1 rule-replay + v0.1.2 module-IR + v0.1.3 disable-condition + v0.1.4 abandoned param-override),但架构 review 发现 substrate 整体落 SDK,违反 application-first;Decision 1 当时提的 strangler migration 在"无真用户反馈信号"前提下不成立 —— preview line 按定义没承诺界面,可推倒。**作初步试错放弃,redesign 基于经验重起**。详细论证见 design-discussion 引用。

### Frozen design probe references(do NOT touch,可 git-access)

**唯一保留分支:** `v0.1.1-evidence-tree-operational-overlay` rollup,含 v0.1.1+v0.1.2+v0.1.3 全部 implemented impl + v0.1.4 abandoned blueprint + 全部 design 材料。

v0.1.2-rule-module-ir / v0.1.3-disable-condition / v0.1.4-param-override 单独分支已**删除**(local + remote,2026-05-03):
- v0.1.2 + v0.1.3 全部 commits 在 rollup `--no-ff` merge 历史里(无内容损失)
- v0.1.4 abandoned blueprint 在删分支前已 cherry 入 rollup `docs/blueprints/archive/`(commit `1f9eac9`)

| 资源 | 位置 | 角色 |
|---|---|---|
| `v0.1.1-evidence-tree-operational-overlay` 分支 | @ `d5c14a3` | **唯一 design probe rollup**(含全部 v0.1.x impl + design 材料 + v0.1.4 archived blueprint) |
| `v0.1.1-preview` tag | @ `b7c9169` | preview 试做 tag(rollup 历史里) |
| `v0.1.2-preview` tag | @ `98474a1` | preview 试做 tag(rollup 历史里) |
| `v0.1.3-preview` tag | @ rollup merge HEAD | preview 试做 tag(rollup 历史里) |

**Reference bundles**(在 rollup 分支上,通过 git access):
- `docs/references/working/rule-replay/`(B'/B'' 设计讨论历史)
- `docs/references/working/evidence-vision/`(L0-L11 能力分层)
- `docs/references/working/design-landscape/`(架构 drift 分析)
- `docs/references/working/design-discussion-2026-05-02/`(A 方向讨论 + Decision 1 历史 framing)

**Archived blueprints**(在 rollup 分支上,通过 git access):
- `docs/blueprints/archive/2026-05-01_rule-replay-with-evidence-diff.md`
- `docs/blueprints/archive/2026-05-02_v0.1.2-rule-module-ir.md`
- `docs/blueprints/archive/2026-05-02_v0.1.3-disable-condition.md`
- `docs/blueprints/archive/2026-05-02_v0.1.4-param-override.md`(abandoned)

**Git access 老 impl 范例:**
```
git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay.py
git show v0.1.1-evidence-tree-operational-overlay:src/kernel/authoring/module_ir.py
git show v0.1.1-evidence-tree-operational-overlay:docs/references/working/evidence-vision/evidence-vision-synthesis-2026-05-02.md
```

### 新 hard constraint(replaces 之前的 strangler migration)

每一个新 capability 必须:
1. 第一步在 `kernel/application/protocol/` 加 DTO
2. 第二步在 `kernel/application/<runtime>.py` 加纯函数 `(request, store) -> result`
3. 第三步(可选)SDK shell wrapper,**绝不带 substrate**
4. **不允许新 substrate 长在 `kernel/sdk/`**
5. Step 0 spike 必须明确回答:"这个 capability 的 application DTO 形状是什么?" — 答不出 → 不 scope

详见 `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`(在 reset 后已更新)。

### 已学经验保留作 redesign 输入

不重读 v0.1.x 代码也已学会的:
- B'' pivot(rule operable + evidence read-only)的设计正确性 — 仍生效
- candidate_key vs candidate_id(cross-run identity)— 用 `candidate_key`
- ConditionModule.atom 必须递归 immutable(`feedback_invariant_defense_in_depth.md`)
- Locator stability invariant — disable / replace 时 `b{branch}.a{atom}` 不位移
- macOS+zsh+BSD-sed 5 个执行陷阱(`feedback_refactor_execution_traps.md`)
- 4 类 "param" 语义不可合并(v0.1.4 abandonment 教训)
- L0-L11 evidence 能力分层是会议室 taxonomy,实施时 L4/L5 可能合并 / L7 必须降级 / L9 不应在 kernel
- Application 是设计中心(`derivation_runtime.evaluate_derivation_plans()` 是 canonical executor)
- Filter CandidateSet 不可靠(head_vars 投影 + dedupe 丢失 body-only var)
- 不 inject initial env(`where_eval` 每 branch `envs=[{}]` 起)
- failed_atom_locator 不是 native evaluator 的自然产物

### Release branch invariant(继续生效)

- `v0.1-oss-prep` @ `f5ade36` 是唯一 release base,**冻结**,无显式 publish 决策不动
- `master` 同样冻结,无显式决策不动
- 本 redesign 分支也是 internal preview line,不向 release base 流入

### 启动阅读顺序(新 session 用)

1. 本文件
2. 新 hard constraint:`~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`
3. Release branch invariant:`~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_release_branch_invariants.md`
4. **设计材料 consolidation**(in-tree,无需 git show 翻 rollup):**[docs/references/working/rule-replay-line-redesign-input/README.md](/Users/zhenzhili/hnsm-backend/docs/references/working/rule-replay-line-redesign-input/README.md)** —— 用户原始 brainstorm + B'/B'' 设计历史 + L0-L11 能力分层 + drift 分析 + A 段讨论 + 4 个 abandoned blueprint + lessons learned
5. AGENTS.md + docs/blueprints/AGENTS.md
6. docs/architecture_principles.md(four-layer data architecture + layer split + release governance)
7. src/kernel/application/docs/README.md(canonical runtime authority)
8. src/kernel/sdk/docs/README.md(product surface,**不再背 substrate**)
9. (可选,深度回溯老 impl)`git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay.py` 等

### 下一步方向(2026-05-04 起)

详情见 [`session_handoffs/2026-05-04.md`](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-05-04.md) §10,但该 handoff 写于 §6.2 前;当前 continuation 已到 `8a6c449`。摘要:

- engine-extension-surface topic Wave 1 已 closed:
  - §6.2 strategic framing:`1f084f8`
  - §6.3 §3.4 minimum engine adapter contract:`9c2d8e5`
  - §3.4 Check evidence-miss follow-up trace:`2c13470`
  - §6.4 §3.2 engine options placement light commit:`24bd22b`
  - §6.5 §3.1 typed payload working hypothesis / migration triggers:`44eefab`
- Diagnose operation Step 0 draft blueprint opened:`docs/blueprints/active/2026-05-04_diagnose-operation.md` + audit (`9b69178`)
- Diagnose Step 0.A source pass complete + conformance-aligned audit:`5aa261d`
- Diagnose Step 0.B DTO contract frozen:`e90835a`
- Diagnose Step 0.C algorithm + drift-prevention frozen:`815192d`
- Diagnose Step 0.D lift complete + blueprint moved `draft → scoped`:`e1dc6d4`
- Diagnose §8 Step 1 protocol DTOs complete:`ceb54bb`
- Diagnose §8 Step 2 native runtime MVP complete:`bf9abf6`
- Diagnose §8 Step 3 native hardening complete:`7092bdf`
- Diagnose §8 Step 4 non-native representability gate complete:`b011757`
- Diagnose §8 Step 5 souffle dispatch complete:`8a6c449`
- Next natural action:Diagnose §8 Step 6 problog/pyreason dispatch(C4 provenance lookup + head-var payload-term alignment + three-bucket classifier reuse; lookup-miss precedence)
- baseline P1/P2 仍待填,但应随 Diagnose source pass 从 consumer angle 补,不单独 abstract inventory

任何新工作必须满足 application-first hard constraint(per `project_application_first_runtime_authority.md`)+ release branch invariants(per `project_release_branch_invariants.md`)。

---

## 2026-05-04 update — Check shipped + engine-extension-surface topic opened

**Check operation 完整闭环 end-to-end(2026-05-04 完成):**

- Topic doc `cited`:`docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md`
- Blueprint archived:`docs/blueprints/archive/2026-05-03_check-operation.md` + audit
- Code:`src/kernel/application/protocol/derivation_check.py`(166 LOC, DTOs)+ `src/kernel/application/derivation_check_runtime.py`(795 LOC, runtime + per-engine paths)
- Tests:73 focused(22 protocol + 51 runtime),782 total kernel green + 1 skip
- 4 engines 全 covered:native (via `evaluate_native_where`)+ souffle (SupportArtifact path)+ problog/pyreason (ProvenanceEnvelope path)— Option IV representability-gated multi-engine
- Application-first hard constraint **100% 落实**;SDK shell 显式 skip per `feedback_narrow_public_api`

**Memory 新增** `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_check_operation_shipped.md` — Check archive 作为 reference template for future application capabilities

**Process patterns validated** (use as templates,详见 handoff §6):
- 4-sub-round Step 0(.A source pass / .B DTO freeze / .C algorithm freeze / .D lift)
- 3-round blind validation(by independent subagents reading only docs)
- §7 drift prevention(每 trap mapped to anti-regression test)
- Conformance audit before `scoped → implemented`
- Archive sequence(`git mv` + inventory + topic doc cross-ref rewire)

**engine-extension-surface-architecture topic opened**(Status: `draft`):

- 新 venue topic doc:`docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md`
- §6.1 ASP scenario demo committed(paper demo of adding 5th engine)
- §6.2 strategic framing committed:`1f084f8`
- §6.3 resolved §3.4 engine adapter contract:`9c2d8e5`
- §3.4 follow-up trace committed:`2c13470` — future Check lookup→None changes must replace MVP silent-skip with observable warning/error before claiming conformance
- §6.4 resolved §3.2 engine options placement(light commit):`24bd22b`
- §6.5 resolved §3.1 payload DTO shape as typed-Union working hypothesis:`44eefab`
- Wave 1 closed; still unresolved/deferred:§3.3 package architecture,§3.5 onboarding workflow,§3.6 capability declaration

**Diagnose operation Step 0 closed**(Status:`scoped`):

- Blueprint:`docs/blueprints/active/2026-05-04_diagnose-operation.md`
- Audit:`docs/blueprints/active/2026-05-04_diagnose-operation.audit.md`
- Commit:`9b69178`
- Step 0.A complete:`5aa261d`;Step 0.B frozen:`e90835a`;Step 0.C frozen:`815192d`
- Step 0.D lift complete:`e1dc6d4`;blueprint §5 / §7 / §8 now carry the frozen contract / acceptance / ordered implementation plan
- Scope now moves to implementation;Step 0 gate is closed and code may begin at §8 Step 1
- 0.B Q1 supersede:Hybrid → Sibling. Diagnose owns dispatch/representability/evidence lookup and does **not** call `check_derivation_binding(...)`,because Hybrid would launder Check's grandfathered non-native lookup-miss silent-skip into Diagnose
- 0.B status contract:reuse Check 4 statuses;`failure_kind` only for `failed.no_candidate` / `failed.atom_localized`;evidence lookup miss maps to `status="unsupported"` with `ErrorDTO(code="EVIDENCE_LOOKUP_MISS")`
- 0.B payload contract:`DiagnoseAtomLocator(branch_index, failed_atom_index, attempted_binding)` is Diagnose-owned capability-output,not an engine-native payload;§6.5 is not engaged and `EvidenceEnvelope.engine_payload` remains unchanged
- 0.B representability:locally hardcoded per engine;native atom-localized,non-native coarse-only;§3.6 pressure confirmed but topic state remains deferred pending a separate post-ship §6.6 decision
- 0.C algorithm:Sibling dispatch;native two-phase pass/fail then atom-localization;native localizer uses `_extend_env_with_atom` enumeration primitive to avoid `_ground_terms` silent-false at atom-index layer;non-native three-bucket classification(match / lookup-miss / no-match) with lookup-miss precedence
- 0.C drift prevention:§7-Diagnose-1..7 frozen,including evidence-miss-as-unsupported,no `DiagnoseAtomLocator` in `EvidenceEnvelope`,no Check-call/import invariant,non-native never atom-localized,status enum exact 4 values
- 0.D lift:§5 Proposed Shape covers D1-D12 + C1-C8 + Q1 supersede + D8.note;§7 Acceptance contains 7 §7-Diagnose anti-regression gates;§8 has 8 ordered implementation steps
- §8 Step 1 complete:`src/kernel/application/protocol/derivation_diagnose.py` + `src/kernel/tests/test_application_diagnose_protocol.py`;42 protocol tests landed,§7-Diagnose-1/2/7 partly enforced at DTO layer
- §8 Step 2 complete:`src/kernel/application/diagnose_runtime.py` + `src/kernel/tests/test_application_diagnose_runtime_native.py`;native MVP covers pass,atom-localized fail,no_candidate fallback,unknown var / RuleRef invalid_request preflight,branch-aware primary,`_extend_env_with_atom` enumeration primitive;non-native intentionally left for §8 Step 4-6
- §8 Step 3 complete:`7092bdf`;fixed native localizer to keep the candidate frontier instead of collapsing to a single primary env after each atom;added RuleRef happy-path test;added §7-Diagnose-4 anti-regression that failed localization does not call support-capture `_atom_satisfies`
- §8 Step 4 complete:`b011757`;added Diagnose-owned `_request_diagnostic_representability_precheck` (no Check helper import) and non-native representability tests. `problog`/`pyreason` return `unsupported` before dispatch for entity-targeted plans and body-only requested variables; `souffle` remains representable for body-only/head-only bindings and is left to Step 5 dispatch. Unsupported representability results carry `failure_kind=None` / `diagnostic_payload=None`, partially enforcing §7-Diagnose-5 until actual non-native dispatch lands.
- §8 Step 5 complete:`8a6c449`;added `_diagnose_souffle` with evaluate → `SupportArtifact` lookup → match / lookup-miss / no-match buckets; lookup-miss outranks `no_candidate`, match wins over lookup-miss; primary sort follows Check C4 `(branch_index, binding_items, candidate_key)`; §7-Diagnose-5/6 souffle-path tests landed. Diagnose result still does not expose branch_index; branch sort is internal deterministic primary selection only.
- Verification at Step 5 checkpoint:`python -m unittest discover -s src/kernel/tests` => 853 OK / 1 skip;`python -m ruff check src/kernel` => all checks passed
- Step 8 close-out refinements to remember:Step 3 frontier bug fix means C2 "first deterministic extension" needs Outcome / Deviations clarification;Step 4 souffle representability is request-gate-vs-dispatch-layer split;Step 5 branch_index sort is internal-only because `DiagnoseResult` exposes `matched_binding`, not branch_index.
- Next:§8 Step 6 problog/pyreason dispatch(C4: evaluate → provenance-envelope lookup → lookup-miss/match/no-match buckets; head-var payload-term binding extraction; lookup-miss outranks `no_candidate`; §7-Diagnose-6 problog/pyreason paths)

**Branch state** `v0.1-redesign-2026-05-03`:ahead origin ≈23 commits before handoff commit / ≈24 after handoff commit,**NOT pushed**。At handoff authoring the only dirty files are `memory/session_handoffs/2026-05-04.md` and `memory/current.md`;after committing handoff,expect clean working tree。release base sacred 不动。

---

## 历史 (pre-2026-05-03 RESET) — master 时刻状态,作历史参考

下方内容是 reset 前 master 分支的 memory 状态,描述 v0.1 onboarding hardening 完成后的形势。redesign 不依赖这段,但保留作 framing 历史:

## 当前阶段

**v0.1 onboarding hardening 已 implemented + merged + pushed**:`oss-prep-v0.1` 现在包含 release-surface cleanup 与 onboarding hardening。`kernel.application` 是 canonical Python runtime authority,`kernel.sdk` 保持 Python product surface / authoring DSL / outward facade。

- 当前分支:`oss-prep-v0.1`
- 当前最新工作:v0.1 onboarding hardening blueprint 已 implemented,并通过 `--no-ff` merge 进入 `oss-prep-v0.1`。merge commit:`962f087`;hardening reference branch:`v0.1-onboarding-hardening` @ `62e68a1`。后续 follow-up 已追加并 push 到 `origin/oss-prep-v0.1` @ `8d7e339`:D7 journey notebook、audit package read-back、native candidate evidence-tree rendering、field-sugar docs、Layer 1/2 signposting、public write/read API docstrings。OS-prep v0.1 readiness、RC verification、source projection gate、onboarding hardening 均已完成;公开源码面通过 sanitized projection script 验证,长期管理方式已写入 `docs/architecture_principles.md`;但仍未创建 public repo、未 upload、未 tag。
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
- v0.1 onboarding hardening:implemented;已合入并 push 到 `origin/oss-prep-v0.1`(`962f087`),后续文档/example polish 已 push 至 `8d7e339`。落地内容包括 `Identity(primary_key=True)` 强制规则、application write cardinality、SDK `set/add` application write-plan adapter、D7 user journey probe、SDK error/repr polish、kernel-only docs boundary polish、D7 notebook mirror + audit read-back/evidence-tree inspection、field-sugar semantics docs、Layer 1/2 signposting、public write/read API docstrings。留 active,等真实 publish + 短期稳定窗口后与其他 v0.1 蓝图一起归档。
- 早期 active 蓝图仍需后续 triage,不要把 memory 当成当前实现真相。

## 下一步方向

**优先级 1:OS-prep release close-out**

- v0.1 onboarding hardening:已完成并 push。当前 release-onboarding path 已由 `test_v01_onboarding_journey.py` 锁定:`ref → set/add → get → query → evaluate(native) → accept → export audit package`。同一 journey 已镜像为可运行 notebook:`examples/10_v01_onboarding_journey.ipynb`,并扩展 audit package read-back + native candidate evidence-tree inspection;native path 不产生 `EvidenceGraph`,`EvidenceGraph` 仍是 PyReason/ProbLog/Souffle adapter provenance artifact。该 notebook 仍不进入 release projection allowlist。`SDKStore.set/add` 现在走 application write-plan,会 materialize identity / exists;unmanaged e_ref 会抛 `SDKStoreError(code="UNRESOLVABLE_E_REF")`;set→multi / add→single 会抛 `CardinalityError`;Entity 必须至少有一个 `Identity(primary_key=True)`。SDK docs 现在明确 `u.field == value` 是 single/multi schema field 的推荐 where sugar,`Pred(...)` 是低层 escape hatch;root README / SDK guide / application docs 已加 Layer 1(`kernel.sdk`) vs Layer 2(`kernel.application`) 路标。
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
