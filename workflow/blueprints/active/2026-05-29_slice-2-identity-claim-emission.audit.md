# Task Blueprint Audit: Slice 2 — Identity-as-Claim Core(Identity Claim emission + INV-7c reject + cache + `:exists` transitional guard)

- Blueprint: [2026-05-29_slice-2-identity-claim-emission.md](./2026-05-29_slice-2-identity-claim-emission.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | draft | Blueprint created | Drafted after Slice 1 Form I close(`9cef674b` pushed to origin)+ ADR-IC(`2d0866ed`)+ ADR-DOCS(`bb6a2c90`)+ preflight code audit covering 5 retract_by_asrt call sites(write_protocol:170/226 protocol — Q-PR1 carve-out NOT touched;sdk/store.py:2125 SDK shell;ingest_runtime.py:169 application ingest;entity_write.py:412 application entity_write;derivation/accept.py:401 internal rollback — SF11 classification NOT touched)。Scope Freeze §6.1 captures 12 binding locks(SF1-SF12)。Implementation Plan §8 split into 11 steps each at commit boundary。Q-PR1 zero-dependency confirmed per §6.3 + §7.11。Branch `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` forked from Slice 1 close `9cef674b`. Sacred master `562c7419` and dirty baseline preserved per CADENCE ritual. Commit: `f9373eea` |
| 2026-05-29 | draft | Blueprint amended per reviewer P1×3 + P2×2(still draft)| User reviewer post-draft review 2026-05-29 返回 3 P1 + 2 P2 findings — 都是实质 gap,不改决策方向但需补 scope/integration/acceptance。**(P1 #1 Ledger helper vs Q-PR1 0-diff 冲突)** 原 §5.2 retract guard `classify_retract_target` 使用 `ledger.get_claim_pred_id(asrt_id)` 或 "add minimal helper to Ledger" — 违反 SF5 / `core/store/ledger.py` 0 diff。**修复**:用现有 `Ledger.get_claim(asrt_id)` API,读 `claim.pred_id`;NO new Ledger helper。同步 unknown asrt classification 改为 `"unprotected"`(而非 `"field"`)— 让 pass-through 语义明确,避免 acceptance 中 "unknown → field" 语义假阳性。Step 2.2 + §7.2 同步修。**(P1 #2 `store.schema_index` attr 不存在)** 原 §5.4 ingest + §5.5 entity_write pseudo-code 用 `store.schema_index`,shipped `Store` 没这个属性。**修复**:`_apply_retract` signature 加 `index: SchemaIndex` 参数,从上游 `_apply_item`(已持 index)pass-through;`entity_write._apply_op` 复用 Slice 1 Step 11 已添加的 `index` 参数(NO new parameter)。Step 4/5 + §7.4/§7.5 acceptance 同步改。**(P1 #3 `fg.entities.create/delete` API 未 shipped)** 原 §7.9 + Step 8 contract tests 要求 `fg.entities.create(User, ...)` 和 `fg.entities.delete(e_ref)` — 但这两个 API 是 Slice 3a ADR-API Q10 namespace migration scope,Slice 2 不应依赖 unshipped API。**修复**:Slice 2 tests 改用 shipped path —`fg.ref(...) + fg.set(...)` / `EntityEditor.commit()` / `SDKBatchTx.commit()`,verify N Identity Claims + `:exists` co-emission;`fg.entities.delete` full-entity revoke acceptance **移到 carry-forward**(标 "future whole-entity delete path once Slice 3a lands");error wording 保留对 `fg.entities.delete` 引用作为 user migration guidance,但 implementation/acceptance 不依赖 unshipped API。§10 Outcome carry-forward 显式加 ADR-API Q10 entry。**(P2 #1 cache field 命名统一)** 原 §5.1 mix `_identity_pred_ids` 和 `identity_pred_ids`(ADR-IC §4.3.1 `_...` 是 implementation sketch)。**修复**:Slice 2 SchemaIndex frozen dataclass 使用 **public 命名**(无下划线)— `identity_pred_ids` / `exists_pred_ids` / `protected_anchor_pred_ids` property;跟其他 SchemaIndex 公开字段(`entities` / `field_predicates` / `predicates_by_id`)命名风格一致;§5.1 加 explicit note about ADR vs implementation naming choice。**(P2 #2 tests scope 精确)** SF7 + §9.4 原表述未明确 legacy carryover boundary。**修复**:SF7 加补充 — Slice 2 close acceptance 只要求 **新增 / 相关 tests 通过**(Slice 2-relevant tests only);不要求 legacy `tests/` 全量 green;legacy pre-Slice-1 fixtures(`Identity(primary_key=)` 等)留 carryover technical debt,不在 Slice 2 清理范围(Slice 3a namespace migration 或 docstring-only legacy cleanup slice 处理)。**Cascade**:§5.1 cache naming + ADR sketch vs implementation note;§5.2 helper signature(use `ledger.get_claim` + `"unprotected"` classification)+ avoid double lookup note;§5.4 ingest signature 加 `index` parameter + caller chain update + Step 0.1 preflight verify gate;§5.5 entity_write reuse existing `index` parameter + EntityWriteError mapping with `code` propagation;§6.1 SF7 P2 #2 boundary clarification;§7.2 unknown asrt → unprotected pass-through;§7.4 ingest index parameter wiring;§7.5 entity_write existing index parameter;§7.9 重写为 shipped-path tests + `fg.entities.delete` carry-forward note;§10 Outcome carry-forward 加 ADR-API Q10 entry;Step 2.2 / Step 4 / Step 5 / Step 8 sub-step 同步改。No structural changes to §1/§2/§3 goals/non-goals(direction unchanged)。方向不动,scope/integration/acceptance 补全。Commit: `c7b2a041` |
| 2026-05-29 | draft | Blueprint amended round 2 — SF1/SF9 命名同步(still draft)| User reviewer round-2 review 2026-05-29 confirmed P1×3 fully resolved + P2 #2 OK;最后一个 P2 sync cleanup:§6.1 SF1 + SF9 表中仍 carry `_identity_pred_ids` / `_exists_pred_ids` / `_protected_anchor_pred_ids` underscore 命名(从 ADR-IC §4.3.1 sketch 残留),跟 §5.1 + §7.1 已锁定的 SchemaIndex public 命名(`identity_pred_ids` / `exists_pred_ids` / `protected_anchor_pred_ids`)冲突 — Scope Freeze 是 implementation binding,不能跟 implementation sections 冲突。**修复**:SF1 + SF9 改为 public names + 括号说明 ADR-IC sketch vs Slice 2 implementation naming choice。No structural / 设计方向 change — pure naming consistency cleanup。Commit: `16bd1439` |
| 2026-05-29 | scoped | Blueprint scoped after reviewer round-2 verification | Verified reviewer round-2 P2 SF1/SF9 naming sync fix landed at `16bd1439`. All findings from prior rounds(P1×3 + P2×2 from round 1;P2 SF1/SF9 sync from round 2)resolved。Reviewer round-2 verdict:"amend SF1/SF9 命名同步 + 可选回填 audit commit 后,可以 scoped。这次不需要再改设计方向"。No design direction change in transition;status advanced from `draft` to `scoped`。SchemaIndex public field names locked across all sections(§5.1 / §6.1 SF1+SF9 / §7.1)。Per-commit verification:sacred master `562c7419` 不动;dirty baseline 保留(4 M + 1 D + 2 untracked);branch `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` 接 round-2 commit `16bd1439`,fork from Slice 1 close `9cef674b`。Status `scoped` 后下一步 = Step 0 pre-impl grep gate(verify 5 retract_by_asrt call sites + verify `_apply_item` chain holds `index: SchemaIndex` parameter — per §5.4 P1 #2 amend Step 0.1 verify gate)。Commit: `a831fd00` |
| 2026-05-29 | scoped | **Step 0 pre-impl grep gate — matches preflight,read-only no commit** | User reviewer 执行 Step 0 read-only verification(no file change,no commit)。**0.1 retract_by_asrt 5 call sites verified**:application/entity_write.py:412(application entity_write wrap target)+ application/ingest_runtime.py:169(application ingest wrap target — P1 #2 amend)+ sdk/store.py:2125(SDK shell wrap target)+ core/evidence/write_protocol.py:170/226(protocol/core direct path,0 diff target — Q-PR1 carve-out)+ core/derivation/accept.py:401(internal rollback,0 diff target — SF11 classification)。**0.1 P1 #2 chain verification**:`_apply_item(..., index=index)` already holds `SchemaIndex`;`_apply_retract` can receive `index` by pass-through。P1 #2 implementation path 有效。**0.2 baseline shipped confirmed**:`_materialization_ops` / `record_exists` / `PlannedOpDTO` 全部 shipped per ADR-IC §6.2。**0.3 no additional unguarded retract_by_asrt application paths found** beyond entity_write + ingest_runtime;application `asrt_id` grep found 仅 read/view/overlay/proof-frame references,no additional write retract_by_asrt 入口。**0.4 docs-only mention noted**:`src/factgraph/core/docs/01_architecture.en.md` mentions `retract_by_asrt(...)` 是 docs-only,非 code path,跳过。**Verdict**:matches preflight,no blueprint amend needed,可以推进 Step 1。No commit(read-only verification per Slice 2 cadence variation — different from Slice 1 Step 0 which committed audit row)。Step 0 outcome recorded in this audit row。 |
| 2026-05-29 | implementing | **Step 1 SchemaIndex cache extension implemented** | Implemented blueprint Step 1 per §8 + SF1 + SF9。`application/schema_runtime.py`:**(1)** SchemaIndex 加 `identity_pred_ids: frozenset[str]` + `exists_pred_ids: frozenset[str]` 两个独立 frozenset fields + `protected_anchor_pred_ids` @property union helper(public 命名 per P2 #1 amend,跟现有 SchemaIndex 公开字段风格一致;ADR-IC §4.3.1 `_..._pred_ids` 是 sketch);docstrings 标 INV-7c 与 existence-claim transitional guard 边界。**(2)** `build_schema_index` 加单 pass over `predicates_by_id.values()` populate 两个 frozenset:`info.is_identity_field` → `identity_pred_ids`;`info.is_entity_exists` → `exists_pred_ids`。低开销:无需 schema_ir 重新遍历。**(3)** NEW test file `tests/test_application_schema_runtime_cache.py`(6 tests,per SF7 新 test file 在 scope):(a)SchemaIndex frozenset fields 存在 + protected_anchor 是 property 非 field;(b)identity_pred_ids 正确 populate from is_identity_field;(c)exists_pred_ids 正确 populate(注:exists predicate 用 capitalized EntityType per shipped schema_compile convention — User:exists,非 user:exists);(d)protected_anchor_pred_ids union 正确;(e)identity ∩ exists = ∅ disjoint(SF9 two independent sets);(f)O(1) membership lookup hit/miss 6 cases。**Verification**:`PYTHONPATH=src python -m pytest tests/test_application_schema_runtime_cache.py -v` → 6 passed in 0.14s;`PYTHONPATH=src python -m compileall -q src/factgraph` clean;downstream import smoke(schema_runtime + entity_view + entity_write + sdk.facade/batch/store)6 modules 全 import clean;Slice 1 Form I round-trip(`fg.ref + fg.set + fg.get`)smoke pass。Per-commit verification:sacred master `562c7419` 不动;dirty baseline 保留;branch HEAD on Step 1 implementation commit。No out-of-scope edits(只动 application/schema_runtime.py + 新 test file)。Q-PR1 carve-out preserved(no diff in core/evidence/write_protocol.py / core/store/ledger.py / adapters/pyreason/* / core/derivation/accept.py:401 / claims.rest_terms)。Commit: `73993ebd` |
| 2026-05-29 | implementing | **Step 2 retract guard helper implemented** | Implemented blueprint Step 2 per §8 + §5.2 + SF2 + SF11 + P1 #1。**NEW module** `src/factgraph/application/retract_guard.py`:**(1)** `RetractClassification = Literal["identity", "exists", "unprotected"]` type alias(per P1 #1 naming — `"unprotected"` 让 pass-through 语义明确)。**(2)** `RetractGuardError(Exception)` — **NOT** inheriting from any SDK-layer exception per SF2 three-layer model;fields `code` / `asrt_id` / `pred_id` / `classification`(`"identity"` 或 `"exists"`)。**(3)** `classify_retract_target(asrt_id, *, ledger, schema_index)` — uses ONLY existing `Ledger.get_claim(asrt_id)` API per P1 #1 + Q-PR1 carve-out;unknown asrt(`get_claim` returns None)→ `"unprotected"`;`identity_pred_ids` 命中 → `"identity"`;`exists_pred_ids` 命中 → `"exists"`;其他 → `"unprotected"`。**(4)** `check_retract_allowed(asrt_id, *, ledger, schema_index)` — single Ledger lookup(inline classification,no double `get_claim`)+ raise INV_7C_IDENTITY_PROTECTED / EXISTENCE_CLAIM_TRANSITIONAL_GUARD / pass-through;module docstring 标 三层 enforcement consumer 跟 Q-PR1 carve-out boundary。**(5)** NEW test file `tests/test_application_retract_guard.py`(11 tests,per SF7):4 classification cases × 2 functions(classify + check)+ distinguishable code distinction + RetractGuardError NOT inheriting SDK error MRO check + stub Ledger 只暴露 `get_claim` 来 verify helper 不调任何其他 Ledger API(P1 #1 enforcement test)。**Verification**:`PYTHONPATH=src python -m pytest tests/test_application_retract_guard.py -v` → 11 passed in 0.16s;`PYTHONPATH=src python -m compileall -q src/factgraph` clean;`git diff src/factgraph/core/store/ledger.py` 为空 — Q-PR1 carve-out preserved(P1 #1 锁的 ledger 0 diff)。Per-commit verification:sacred master `562c7419` 不动;dirty baseline 保留;branch HEAD on Step 2 implementation commit。No out-of-scope edits(只动 application/retract_guard.py NEW + 新 test file)。Q-PR1 carve-out preserved(`core/evidence/write_protocol.py` / `core/store/ledger.py` / `adapters/pyreason/*` / `core/derivation/accept.py:401` / `claims.rest_terms` 全 0 diff)。Commit: TBD post-stage |

## Decision Notes

### 2026-05-29 — Preflight code audit

Located all relevant sites per ADR-IC §6.2 citations + 2 new findings:
- **Section A**(emission)+**Section B**(Layer 2 reject)— ALREADY shipped baseline;Slice 2 mainly formalizes via contract tests + docs + error message updates
- **Section C**(Layer 3 asrt_id reject)— NOT shipped main new work
- **Section D**(cache)— `SchemaIndex` 需要扩展;PredicateInfo flags already extended in Slice 1
- **Section E**(shadow store legacy)— Already shipped fail-fast + lazy paths;Slice 2 documents legacy positioning
- **Section F**(`:exists` co-emission + rule layer)— Already shipped read paths;rule layer NOT modified per N5
- **Section G**(protocol/core direct paths)— Q-PR1 carve-out + internal rollback classification

### 2026-05-29 — Reviewer P1+P2 Scope Freeze verdict

**P1 finding**: `application/ingest_runtime.py:169 _apply_retract` direct `retract_by_asrt` call bypass risk — bulk ingest 可绕过 Identity/exists guard。

**P2 finding**: "Application source-of-truth" wording precision —
- application-layer source-of-truth = **shared retract guard helper**(NEW `application/retract_guard.py`)
- SDK shell fail-fast = `SDKStore.retract`(consumer)
- application ingest path = `ingest_runtime._apply_retract`(consumer)
- application entity_write path = `entity_write._apply_op` retract branch(consumer)
- protocol/core direct path = schema-agnostic,intentionally unguarded per Q-PR1 carve-out + ADR-FI §4.4.2

**N11 classification finding**:`core/derivation/accept.py:401` derivation rollback `retract_by_asrt` direct call — internal rollback path,NOT user-facing;Slice 2 不 guard 但 blueprint **MUST** explicitly classify(防 reviewer 误判为漏)。

**Resolution embedded in SF2 + SF3 + SF11**:
- SF2:三层 enforcement model(helper + SDK shell + intentionally-unguarded protocol/core)
- SF3:application-layer guard MUST cover all 3 application-or-above entry points
- SF11:`core/derivation/accept.py:401` 显式 classified as intentionally-unguarded internal rollback;blueprint §6.3 + §10 Outcome 必须记录

### 2026-05-29 — 6 OQ verdicts embedded

OQ1 ✓ SchemaIndex hosts caches(SF1)
OQ2 ✓ Three-layer enforcement(SF2 + P2 precision)
OQ3 ✓ NO stub for `fg.schema.register/extend/apply`;hook-ready contract documented;wiring deferred to ADR-API Q14(SF4)
OQ4 ✓ Q-PR1 carve-out preserved(SF5)
OQ5 ✓ Slice 2 load-bearing docs scope only(SF6)
OQ6 ✓ Tests directory IN scope for Slice 2;Slice 1 SF6 NOT inherited(SF7)

### 2026-05-29 — Class size estimate M

Initial scope per ADR-IC §4.5 was ~150-300 lines。After P1+P2 verdict expansion(application ingest guard + entity_write guard + shared helper):
- SchemaIndex cache extension(~30-50 lines)
- Application retract guard helper(~100-150 lines incl. tests)
- SDK shell wrap(~30 lines)
- Application ingest wrap(~30 lines)
- Application entity_write wrap(~20 lines)
- Error messages update(~30 lines)
- Shadow store comments(~20 lines)
- Contract tests(~150-250 lines)
- Load-bearing docs(~150-200 lines)

Total ≈ 250-400 lines code + 150-250 lines tests + 150-200 lines docs ≈ **M class**(smaller than Slice 1 M/L boundary — Slice 2 is more contract-formalization than semantic rewrite)。

### 2026-05-29 — Q-PR1 carve-out preservation strategy

Per meta-ADR §4.4 hard rule + ADR-INV9 §4.4 三项绑定 carve-out + ADR-SYS-B §4.7.2:
- §6.3 explicitly lists 6 files/paths that must show zero diff:`core/evidence/write_protocol.py`,`core/store/ledger.py`,`core/store/_builders.py`,`adapters/pyreason/*`,`claims.rest_terms`,INV-9 runtime strict
- **+1 additional path classified as intentionally-unguarded(SF11)**:`core/derivation/accept.py:401` derivation rollback `retract_by_asrt` direct call — NOT user-facing
- §7.11 acceptance criterion enforces zero-diff via grep at slice close

Slice 2 has zero PyReason / adapter / ledger / write_protocol / internal derivation rollback dependency by construction。

### 2026-05-29 — Carry-forward dependencies recorded

- **ADR-API Q14 schema-evolution hook**(SF4):cache hook is "hook-ready contract" documented in blueprint §5.10;ADR-API Q14 implementation slice wires `fg.schema.register/extend/apply` to trigger cache rebuild per ADR-IC §4.3.3
- **Step 2+ `:exists` removal**(per ADR-IC §4.4.4 forward-pointer):`exists_pred_ids` 变 empty frozenset 时,`protected_anchor_pred_ids` 退化为 `identity_pred_ids` only;INV-7c 范围不动;`existence-claim transitional guard` reject 路径 dead code 清理
- **Step 2+ shadow store removal**(per ADR-IC §4.2.4 eager-emission 演化方向):`_identity_values_by_e_ref` 删除 + `fg.fields.set(Field, e_ref_string)` 若 e_ref 未 materialized → raise EntityNotInitializedError(显式 contract)
