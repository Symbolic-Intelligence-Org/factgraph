# Task Blueprint Audit: Slice 3a — API namespace refactor(Q10-Q14 cluster)

- Blueprint: [2026-05-30_slice-3a-api-namespace.md](./2026-05-30_slice-3a-api-namespace.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted on Slice 3a branch `v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30 @ b17750c8`(post-preflight + amend),forked from Slice 2 close `c927d41f`。**Inputs**:ADR-API(`66434490` adopted 2026-05-29 — Q10 三层 namespace rename + Q11 AssertionView 统一 + Q12 version(v) hard remove + Q13 _meta 统一 flat kwargs hard remove + Q14 fg.schema.add 三分)+ meta-ADR(`ebafdb0c` §4.2 grouping lock + §4.4 Q-PR1 separation contract)+ ADR-IE(`9fd0ffb5` EntityEditor 公开 contract)+ ADR-IC(`2d0866ed` §4.3.6 explicit contract part 1+2)+ ADR-DOCS(`bb6a2c90` §4.2.2 load-bearing docs)+ Slice 3a preflight audit doc(`workflow/audit/active/2026-05-30_slice-3a-api-namespace-preflight.md` @ `70aee8a5` + amend `b17750c8`)。**§6 Scope Freeze 13 items(SF1-SF13)直接 inherit reviewer PF-S verdicts**:**SF1** flat top-level shortcuts 全删(PF-S1 Option B — fg.set/add/retract/edit/get/ref/find/match 8 个删 + 无 alias 无双轨;Slice 2 emission tests + Slice 1+2 cumulative tests 全 migrate)+ ADR §4.1 排他原则;**SF2** fg.entities.delete discriminated signature(PF-S2 — Form A e_ref:str + Form B EntityCls+identity_kwargs;tuple selector forbidden + 错误 message "requires e_ref string OR EntityClass + full identity bundle");**SF3** fg.entities.delete implementation site at application layer planner+executor(PF-S3 INV-6 — NEW EntityDeleteCommand + plan_delete_command + apply_delete_plan in application/entity_write.py;SDK manager 只归一化;`_apply_op` retract branch 加 marker `__delete_via_entities_delete__` 跳过 Slice 2 retract guard 因 ADR-IC §4.1 整批 delete 是 Identity Claim 唯一合法整批 retract 路径);**SF4** fg.entities.create eager emission + populate shadow store(PF-S4 Option (a)— 直接 emit Identity Claims + :exists via `_materialization_ops` shipped path + populate shadow store for legacy compat;`fg.ref + fg.fields.set` lazy path 继续 co-exist;Slice 3a 显式 NOT remove shadow store per ADR-IC §4.2.4);**SF5** AssertionView.history deprecated alias 行为(PF-S5 — alias of .all + 默认不发 DeprecationWarning + env var 固定 FACTGRAPH_WARN_DEPRECATED=1 触发);**SF6** `_ASSERTION_FILTER_MISSING` sentinel reuse(PF-S6 — 不引入新 sentinel for AssertionView/AssertionsManager/AssertionRecordSet 三处 where signature);**SF7** Slice 3a load-bearing docs scope(PF-S7 — 4 docs same-slice landing:04_api_surface.en.md + 02_readwrite_and_ingest.en.md + 00_user_guide.en.md + identity-mechanism-redesign.zh.md §12/§13;Slice 4 留 01_concepts.en.md + 03_rules_and_inferences.en.md + 07_walker_and_advanced.en.md + public quickstarts + examples deep polish;narrow patch exception 若 test/current docs hard-reference 新 API 造成断裂);**SF8** 12-step plan + docs as standalone close-time step(PF-S8 — Step 0 grep first + Step 1-9 manager/code changes + Step 10 tests/examples migration + Step 11 load-bearing docs + Step 12 final acceptance + close);**SF9** Q-PR1 carve-out + SF11-style internal-rollback 继承(继承 Slice 1+2 — 5 sacred paths `core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py` 含 `:401` 内部 rollback path 全 0 diff against c927d41f..HEAD);**SF10** sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` 不动 + dirty baseline 保留 + branch lineage 全 7 ancestors verified;**SF11** ADR-IE EntityEditor 公开 contract 不改(sdk_edit factory edit-existing-only + lifecycle methods + IdentityEditor Slice 2 Step 6 文案 + FieldEditor cardinality enforcement 全保留;Slice 3a 只动 `fg.write.edit` → `fg.entities.edit` 入口名);**SF12** ADR-IC §4.3.6 explicit contract part 1+2 enforce at `fg.schema.extend`(part 1 Identity↔Field swap reject + Identity add reject + 删字段 reject + cardinality/type 改 reject;part 2 `<EntityType>:exists` predicate immutability — 删/owner_type 改/arity 改 reject);**SF13** No flat shortcut re-introduction rule(SF1 corollary — future slice 不应加 verb-on-fg shortcuts;所有 user-facing operations 必须走 namespace manager)。**Implementation Plan §8 split into Step 0 grep + Step 1-12**(per SF8 — Step 1 EntitiesManager 4 base methods / Step 2 fg.entities.create / Step 3 fg.entities.delete / Step 4 fg.entities.exists / Step 5 FieldsManager 5 methods / Step 6 AssertionsManager rename + where + retract 挪 + Slice 2 wrap / Step 7 fg.entities.edit 挪层 + read/write namespace 删 + flat shortcuts 全删 / Step 8 AssertionView 类型合并 + history env var / Step 9 version(v) + where flat kwargs hard remove / Step 10 fg.schema 三分 + ADR-IC §4.3.6 enforce / Step 11 tests + examples migration / Step 12 load-bearing docs + final acceptance + close)。**Step 11 + Step 12 显式分离** per SF8 reviewer guidance(docs as standalone close-time step,不混 implementation sweep)。**Acceptance §7 split into 13 sub-sections**:§7.1 三层 namespace + 排他 / §7.2 fg.entities.create/delete/exists / §7.3 fg.fields.* 5 methods / §7.4 AssertionsManager + AssertionView 统一 + history alias env var / §7.5 version(v) + flat kwargs hard remove / §7.6 fg.schema 三分 + ADR-IC §4.3.6 / §7.7 Q-PR1 carve-out / §7.8 sacred branches / §7.9 ADR-IE compat / §7.10 internal-rollback / §7.11 tests+examples migration / §7.12 load-bearing docs migration / §7.13 per-commit ritual。**Q-PR1 zero-dependency confirmed**(per §6.3 + meta-ADR §4.4 + Slice 1+2 lineage):0 diff target list 跟 Slice 2 SF5 完全一致 + SF11 internal-rollback `core/derivation/accept.py:401` 继承。**Branch fork from Slice 2 close `c927d41f`,not pushed to origin**(per `feedback_push_master_gate` — 等 reviewer scoped + 授权后推)。Commit: TBD post-stage |

## Decision Notes

### 2026-05-30 — Preflight findings inheritance

Slice 3a preflight audit doc(`workflow/audit/active/2026-05-30_slice-3a-api-namespace-preflight.md` @ `70aee8a5` + amend `b17750c8`)5-bucket findings 全 inherit:

- **0 Required / 0 Recommended**:ADR-API + meta-ADR + ADR-IE + ADR-IC + ADR-DOCS 5 ADR baseline 互锁状态 verified;无 ADR amend 必要
- **4 Verified**(PF-V1 ADR lineage / PF-V2 Q-PR1 0 diff against Slice 1 close 9cef674b..c927d41f / PF-V3 Stage 1 audit §7.3 baseline post-Slice-1/2 accurate / PF-V4 Slice 2 §10.9 carry-forward 4 项 mapping clean)— blueprint §4 + §6 直接引用
- **8 Scoped-detail(PF-S1-S8)**:reviewer verdict 2026-05-30 全 8 项 lock 直接进 §6 Scope Freeze SF1-SF8(blueprint scope freeze 跟 PF-S 编号一对一)
- **0 Abandonment**:无 abandon

### 2026-05-30 — Reviewer 2 non-blocking precision points on preflight(amend `b17750c8`)

User reviewer review pass 时 surface 2 个非阻塞 precision 点(amend in preflight,不影响 blueprint draft):

1. **Branch fork status precision**:preflight §1 header 原 "暂未起 Slice 3a branch — fork point 待 blueprint scope 锁后 from c927d41f";amend 改 "Branch: `v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30` @ `70aee8a5`(preflight commit)— fork from Slice 2 close `c927d41f`(post-amend at preflight review pass);blueprint draft + audit log 直接落本 branch"
2. **ADR-IE commit SHA backfill**:preflight §1 Inputs ADR-IE row 原 "(adopted)" bare;amend 加 `9fd0ffb5`

两点都是文档 precision,no PF finding class change,reviewer verdict pass stands。

### 2026-05-30 — `fg.entities.delete` 跳过 Slice 2 retract guard 的 SF3 lock rationale

PF-S3 lock(application layer planner + executor for `fg.entities.delete`)需要 build retract PlannedOpDTOs for Identity Claims + `:exists` Claim 同 atomic 整批 retract Field Claims。**问题**:Slice 2 三层 retract guard(`retract_guard.py:check_retract_allowed`)会 enforce INV-7c on Identity Claim retracts + existence-claim transitional guard on `:exists` retracts — 通用路径会被 guard 阻止。

**Lock decision**:`plan_delete_command` 内部 build retract PlannedOpDTOs 时设特殊 marker `meta["__delete_via_entities_delete__"] = True`;Slice 3a 在 `_apply_op` retract branch 加 marker check(`if op.meta.get("__delete_via_entities_delete__"): skip check_retract_allowed`),跳过 guard for delete-internal retracts。

**Rationale**:
- 这跟 ADR-IC §4.1 强制点 3 完全一致 — "Identity Claim 的整批撤销**只能**作为 `fg.entities.delete` 的一部分"。delete-path 是 Identity Claim 唯一合法整批 retract 路径。
- Guard 设计本身就允许该 path bypass — Slice 2 SF2 三层 enforcement model 的 "intentionally unguarded" 边界包含 `fg.entities.delete` 全实体 revoke(将 future shipped)
- 不是 "bypassing security" — 是 "applying the correct path for atomic entity revoke";non-delete paths 仍走 guard
- Marker 在 `meta` 不在新 field 上 — 没改 PlannedOpDTO shape(Q-PR1 carve-out friendly)

Audit row 显式记录这条 lock + rationale 防 reviewer 误判 SF3 为 "bypass guard"。

### 2026-05-30 — `version(v)` + flat kwargs hard remove 跟 PF-S6 sentinel reuse 衔接

PF-S6 lock 是 `_ASSERTION_FILTER_MISSING` sentinel reuse,but 这 affects 3 处不同 `where` signature:
1. `AssertionRecordSet.where(*, value, value_tag, _meta)` — Q13 flat kwargs 删 + Q12 version 删后剩 3 个 kwargs
2. `AssertionView.where(*, field, e_ref, value, value_tag, _meta)` — Q10 NEW canonical filter
3. `AssertionsManager.where(*, field, e_ref, value, value_tag, _meta)` — Q10 NEW canonical filter on Layer 3 manager

三处 signature 都用同 sentinel `_ASSERTION_FILTER_MISSING`(shipped `sdk/facade.py:18`)— 不新增 sentinel。Step 6(AssertionsManager.where)+ Step 8(AssertionView.where)+ Step 9(AssertionRecordSet.where post-flat-kwargs-delete)都 reuse。Audit row 显式 link 三处 + 防 future reviewer 误以为需要新 sentinel for AssertionView。
