# Task Blueprint Audit: Slice 1 — Form I Schema Refactor

- Blueprint: [2026-05-29_slice-1-form-i-schema.md](./2026-05-29_slice-1-form-i-schema.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | draft | Blueprint created | Drafted after Stage 3 synthesis @ `d0036e1f` + reviewer L7-L11 lock-in choices + preflight code audit v2 covering descriptor / parser / schema compile / schema runtime / rule lowering / derivation compile / protocol / store.ref second default path / facade / batch / value validation / sdk export surfaces. Scope Freeze §6.1 captures 6 binding locks(SF1-SF6)from reviewer 2026-05-29. Class re-estimated as M/L boundary based on N6-N14 rule-lowering semantic rewrite + 325 test callsite migrations + load-bearing docs. Implementation Plan §8 split into 14 steps each at commit boundary per `feedback_smaller_batch_design_blueprints` rule-touching cadence. Q-PR1 zero-dependency confirmed per §6.3 + §7.12. Branch `v0.2.0-blueprint-slice-1-form-i-schema-2026-05-29` forked from synthesis `d0036e1f`. Sacred master `562c7419` and dirty baseline preserved per CADENCE ritual. Commit: `5d211efc` |
| 2026-05-29 | draft | Blueprint amended per reviewer P1×3 + P2 findings(still draft)| User reviewer 2026-05-29 post-draft review 返回 4 findings — 都是实质 gap,不改决策方向但需补 scope/integration/acceptance。**(P1 #1 write-time validation 覆盖面太窄)** 原 §5.13 / §7.9 / Step 11 只挂在 `FieldEditor.set/add`,但 shipped 主要写入路径(`SDKStore.set/add` @ `sdk/store.py:1920/1963` → `_apply_field_mutation` @ `2002` → `apply_write_plan` → `_apply_op` @ `application/entity_write.py:382` → `set_field/add_field`)在 facade 之下汇聚;`fg.write.set/add`(`_SDKWriteManager` @ `sdk/store.py:568-585`)是 SDKStore 别名;`WireBatchPlan.apply` @ `sdk/batch.py:418` 行 430-433 调 `sdk.set/add` 同路径;只挂 FieldEditor 会被 fg.set / fg.write.set / batch.apply 绕过。**修复**:§5.13 重写 integration 点为 `_apply_op` 中央应用层路径,FieldEditor 经 SDKStore 自然覆盖;§7.9 加 coverage validation 6 项(fg.set / fg.add / fg.write.set / fg.write.add / SDKBatchTx / FieldEditor)+ 显式不覆盖 5 项(write_protocol direct / ingest / batch materialization / derivation accept / pyreason adapter);Step 11 集成点同步改。**(P1 #2 Identity(pattern/description) 半死参数)** §5.1 接受 Identity(description, pattern)但 §5.4 只锁 `_compile_field` / `_compile_relationship_field` 写 enum_values/pattern;`_compile_identity_field` / `_compile_identity_predicate` 未锁,Identity(pattern=...)在 schema_ir 中丢失。**修复**:§5.4 加 Identity compile-time `description` + `pattern` 传递;Identity pattern compile-time regex syntax + pattern-on-non-string 校验也适用;Identity write-time enforcement 留 Slice 2(ADR-IC 写入路径成型后),但 Slice 1 必须产出 schema truth;§7.3 加 Identity pattern compile checks + SchemaIndex.PredicateInfo 携带 description/pattern。**(P1 #3 Literal[float] 与 schema canonicalization 冲突)** `schema_ir.canonicalize_schema_ir_jcs` 通过 `_reject_floats`(@ `core/schema/schema_ir.py:217-229`)拒绝任何 float;`enum_values` 含 float 会让 schema digest 崩。**修复**:§5.2 + §5.4 + Step 1.3 + Step 3.3/3.4 + §7.1 全加 float Literal enum reject;`float64` 普通字段仍允许,只是不允许 Literal[float] enum;Step 2+ 若需要 float enum 走单独 canonical encoding ADR。**(P2 step ordering 长红分支)** 原 Step 12 callsite migration 让 Step 1 commit 后 10 个 commit 期间 tests 在 import 阶段崩(`Field(cardinality=)` 在 Entity fixture class 定义里).无法 per-commit verification。**修复**:Step 1 重新框架为 "breaking-atomic commit" — descriptor signature change + 全部 test fixture 迁移 + 全部 Entity-using load-bearing doc example 迁移(NOT NEW Form I content)同一 commit 落地;Step 12 缩为 "NEW Form I docs content"(overview + 类型推断 + dual-layer usage 新内容)。Step 1.12 verify green branch 显式 gate。**Cascade**:§6.1 SF3 加 cross-entity-type same-name reject 负向(`User.id == Order.id`);§6.1 SF6 加 `workflow/audit/active/` 默认不迁移;§7.8 加 SF3 negative cases 5 项(同字段 accept + 4 reject cases 含 cross-entity);Step 0 加 pause-and-amend trigger 4 项(non-zero Identity-headed derivation / exotic allow_identity_defaults caller / bridges/ load-bearing reference / 意外 callsite directory);Step 0.4 加 explicit `docs/references/bridges/` status verification checklist;§9.4 重写为 unconditional + conditional exclude 形式 + Step 0.4 checklist 引用。No structural changes to §1/§2/§3/§4。方向不动,scope/integration/acceptance 补全。Commit: `b26febff` |
| 2026-05-29 | scoped | Blueprint scoped after reviewer amendment verification | Verified the reviewer P1×3 + P2 fixes are present in the blueprint:central write-time validation at `application/entity_write.py:_apply_op`,Identity `description/pattern` schema truth + compile checks,float Literal enum reject,breaking-atomic Step 1 ordering,cross-entity same-name Identity equality reject,and SF6 `workflow/audit/active/` exclusion. No further design changes added in this transition;status advanced from `draft` to `scoped`. Commit: TBD post-stage |

## Decision Notes

### 2026-05-29 — Preflight code audit v1(initial triage)

Identified 7 surface sections(A-G):descriptor signatures + annotation inference + parser kwargs + schema_compile + schema_ir validation + write-time validation + sdk `__all__`. Triage table built with shipped-vs-target rows. Reviewer feedback flagged 3 missing item categories prompting v2 expansion。

### 2026-05-29 — Preflight code audit v2(extended triage)

Added 3 sections(N/O/P):
- **N. Primary-key semantic consumers**:`IdentityFieldInfo` + `where_schema_lowering.py` (lines 36 / 46-57 / 90 / 247-282) + `derivation_compile.py` (lines 203 / 276 / 555-590 / 632) + 3 other sites(`sdk/store.py:2807`,`evaluate_result.py:793`,`rule_expr_inspect.py:232`)
- **O. Identity-default consumers**:`materialize_identity` + `_materialize_default_factory` + `SDKStore.ref` parallel default path at 1909-1912 + `EntitySelector.allow_identity_defaults` protocol field
- **P. Test + doc callsite migration burden**:Field(cardinality=) tests 202 + docs 65;Identity(primary_key=) tests 115 + docs 38;Identity(default=) tests 6 + docs 6;Identity(default_factory=) 0+0

Class re-estimated **M/L boundary**(not pure descriptor M)。

### 2026-05-29 — Reviewer Scope Freeze lock-ins(SF1-SF6)

User reviewer locked 6 scope-freeze items per response 2026-05-29:

- **SF1**:Form I removes primary/default/default_factory semantics completely — no zombie surface
- **SF2**:All Identity fields are immutable anchor-bundle members — no primary vs non-primary
- **SF3**:Cross-coordinate attribute equality may compare same Identity field only — no implicit full-bundle expansion(L7 lock;rejected default suggestion "anchor-bundle equivalence" as semantically too implicit)
- **SF4**:Derivation heads may not include any Identity field(Option A;L8 lock;requires pre-impl grep for shipped Identity-headed rules)
- **SF5**:Identity defaults removed end-to-end(L9 lock;reviewer added `SDKStore.ref` path beyond initial preflight)
- **SF6**:Historical/reference docs excluded with precise scope(L10 lock):must migrate `tests/` + `src/factgraph/sdk/docs/` + `docs/official/kernel/` + active design/decision/blueprint load-bearing;exclude `workflow/heritage/` + `workflow/blueprints/archive/` + `docs/references/working/` + `docs/references/bridges/`(if not current implementation truth)

Additional reviewer findings:
- `EntitySelector.allow_identity_defaults` is a frozen protocol field that needs explicit removal(initial preflight covered only `materialize_identity` kwarg)
- `SDKStore.ref` lines 1909-1912 has its OWN parallel default-materialization path independent of `materialize_identity` — bigger O-section gap

### 2026-05-29 — Class size re-estimate M/L boundary

Initial Slice 1 was estimated by ADR-FI §4.5 as "≈ 250-450 lines code" — pure descriptor refactor estimate。Preflight v2 revealed:
- Rule-lowering and derivation-compile semantic rewrite per SF3 + SF4(~110-180 lines)
- Two parallel default paths instead of one(SDKStore.ref + materialize_identity)— ~50 additional lines
- 325 test callsite migrations + ~110 doc migrations(per SF6 scope)— mechanical but high volume
- Load-bearing docs ~150-250 lines(per ADR-DOCS §4.2.1)

Final estimate ≈ 600-950 lines code change + 325 test migrations + 150-250 lines load-bearing docs。Class **M/L boundary**。Implementation Plan §8 splits into 14 steps(0-13)each at commit boundary to keep individual commits reviewable and rule-touching changes isolated。

### 2026-05-29 — Pre-impl grep(Step 0)is gating

Step 0 pre-impl grep produces:
- 0.1 Migration list for any shipped derivation rules where head body includes any Identity field — if 0,SF4 Option A is free lunch;if > 0,each rule becomes Step 10.5 migration item with no semantics change to that rule
- 0.2 Per-pattern callsite count baseline(used in §10 Outcome before/after comparison)
- 0.3 `EntitySelector(allow_identity_defaults=...)` exotic caller catalog(if any外 of core paths)

Step 0 lands as 第一 commit(audit log row update only,no code change)— ensures pre-impl preflight findings are recorded before any descriptor work begins。

### 2026-05-29 — Q-PR1 carve-out preservation re-verified

Per meta-ADR §4.4 hard rule + ADR-INV9 §4.4 三项绑定 carve-out + ADR-SYS-B §4.7.2:
- §6.3 explicitly lists 6 files / paths that must show zero diff:`core/evidence/write_protocol.py`,`core/store/ledger.py`,`core/store/_builders.py`,`adapters/pyreason/*`,`claims.rest_terms`,INV-9 runtime strict
- §7.12 acceptance criterion enforces this via diff inspection at slice close

This Slice 1 has zero PyReason / adapter / ledger / write_protocol dependency by construction。
