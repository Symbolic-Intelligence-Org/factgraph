# Preflight: Slice 3a — API namespace refactor(Q10-Q14 cluster)

- Status: complete(hand-off ready for reviewer review)
- Created: 2026-05-30
- Last Updated: 2026-05-30
- Authority: pre-blueprint code-audit triage per `feedback_preflight_code_audit_required.md`(Phase C 2026-05-20 incident 根因)。**Does NOT lock implementation**;findings 输入即将起草的 Slice 3a blueprint(draft → scoped pipeline)。
- Inputs:
  - ADR-API(`workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted `66434490`)— §4.1 Q10 / §4.2 Q11 / §4.3 Q12 / §4.4 Q13 / §4.5 Q14 + §4.6 cross-Q summary
  - meta-ADR(`workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted `ebafdb0c`)§4.2 grouping(Q10-Q14 同 ADR 锁)+ §4.4 Q-PR1 separation contract(Step 1 zero Q-PR1 dependency)
  - ADR-IE(`workflow/design/decisions/active/2026-05-29_q-ie-entity-editor-decision.md`)— EntityEditor 公开 contract 跟 ADR-API §4.1 `fg.entities.edit` 衔接
  - ADR-IC(`workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted `2d0866ed`)— §4.3.6 explicit contract(`fg.schema.extend` Identity↔Field swap reject + `<EntityType>:exists` predicate protect)
  - 现有 Stage 1 audit `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q10-Q14 rows(`audit:524-528`)
  - Slice 1 close `9cef674b`(`v0.2.0-blueprint-slice-1-form-i-schema-2026-05-29` pushed)+ Slice 2 close `c927d41f`(`v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` pushed,fork from Slice 1 close)
  - Shipped SDK 源码(`src/factgraph/sdk/store.py` + `src/factgraph/sdk/facade.py` + `src/factgraph/sdk/batch.py`)read at preflight-row-drafting time
- Outputs / Downstream:
  - Slice 3a blueprint draft(NEW `workflow/blueprints/active/2026-05-30_slice-3a-api-namespace.md` + paired audit log)
- Branch:暂未起 Slice 3a branch — preflight 在 Slice 2 close 后的 HEAD(`c927d41f` push tip)上 read-only,fork point 待 Slice 3a blueprint scope 锁后 from `c927d41f`

> 触发 preflight 必要性:Slice 3a 满足 CADENCE Q3 §4.4 触发条件 — **subtractive removal**(`fg.read.*` / `fg.write.*` namespace 整删,无 alias)+ **cross-module protocol change**(SDK shell ↔ application + ledger ↔ tests + docs + examples 跨多 module 改 surface)+ **namespace migration**(Q10 主体)。

## 1. Preflight scope + 触发条件

Re-read at preflight-row-drafting time(2026-05-30):

- ADR-API §4.1-§4.6(adopted wording 全 5 个 sub-decisions)
- meta-ADR §4.2 grouping + §4.4 Q-PR1 separation contract + §4.4.1 INV-9 layer boundary
- ADR-IE §4.4 Identity Layer 1 reject + §4.8 sdk_edit factory + §4.9 cross-Q summary
- ADR-IC §4.3.6 explicit contract part 1 + part 2(Identity↔Field swap reject + `:exists` predicate protect)
- `src/factgraph/sdk/store.py` 4 namespace manager classes + 8 flat top-level methods on `SDKStore`
- `src/factgraph/sdk/facade.py` `AssertionRecordSet` + `FieldAssertions` + `AssertionNamespace` 类 + `EntityEditor` + `IdentityEditor` + `FieldEditor` + `sdk_edit` factory
- `src/factgraph/sdk/batch.py` `SDKBatchTx` + `ManagedEntityHandle` + `_StagedFieldOp`(批量 staging — Q10 影响 `tx.entity(...).field.set(...)` 写入路径)
- Grep blast radius across `tests/` + `src/factgraph/sdk/docs/` + `docs/` + `examples/`

触发条件 verified:
- **subtractive**:Q10 alpha 直接 breaking rename + 无 alias(per ADR-API §4.1.3 lock — 无双轨期)
- **cross-module**:SDK shell + application + tests + docs + examples 5 个面同步改
- **namespace migration**:Q10 主体 + Q14 `fg.schema.add` 三分

## 2. ADR baseline 验证(no drift discovered)

### 2.1 ADR-API + meta-ADR + ADR-IE + ADR-IC 互锁状态

| ADR | Adopted commit | 跟 Slice 3a 的关系 |
|---|---|---|
| ADR-API | `66434490` | **本 slice 主源** — Q10-Q14 全 5 个 sub-decisions |
| meta-ADR | `ebafdb0c` | §4.2 grouping 锁 Q10-Q14 必须同 ADR(已满足);§4.4 锁 Step 1 zero-Q-PR1 dependency(Slice 3a 直接继承) |
| ADR-IE | (adopted) | §4.4 Identity Layer 1 reject 由 `IdentityEditor` 实现(Slice 2 Step 6 已更新文案);§4.8 sdk_edit factory edit-existing-only contract(Slice 3a rename 不破)|
| ADR-IC | `2d0866ed` | §4.3.6 explicit contract 由 Slice 3a Q14 `fg.schema.extend` 实施;Slice 2 已 ship SchemaIndex frozensets 给 cache 提供基础(`73993ebd`)|
| ADR-DOCS | `bb6a2c90` | §4.2.2 load-bearing docs Slice 3a 范围 = `04_api_surface.en.md` + `02_readwrite_and_ingest.en.md` + `01_concepts.en.md` 等(具体待 Slice 3a §9 锁定)|

**Q-PR1 carve-out 继承**:Slice 3a 继续遵守 Slice 1/2 同款 0-diff(`core/evidence/write_protocol.py` / `core/store/ledger.py` / `core/store/_builders.py` / `adapters/pyreason/*` / `core/derivation/accept.py`);per meta-ADR §4.4 + Slice 2 SF5 + SF11。

### 2.2 Stage 1 audit doc §7.3 Q10-Q14 baseline spot-check(Slice 1+2 close 后)

| Q | §7.3 baseline 语义 | Slice 1+2 close 后状态 |
|---|---|---|
| Q10 | `fg.read.*` / `fg.write.*` shipped baseline | ✓ 仍准确 — Slice 1 改 Form I descriptors,Slice 2 加 retract guard 不动 namespace 形态;managers + methods 跟 §7.3 描述一致 |
| Q11 | `FieldAssertions` + `AssertionNamespace` shipped baseline | ✓ 仍准确 — Slice 2 不动这两个类(只动 IdentityEditor + plan_write_command 文案)|
| Q12 | `AssertionRecordSet.version(v)` / `FieldAssertions.version(v)` shipped | ✓ 仍准确 — Slice 2 不动 view 一等方法 |
| Q13 | `AssertionRecordSet.where(source=, trace_id=, version=, meta=)` flat kwargs shipped | ✓ 仍准确 — Slice 1+2 不动 where signature |
| Q14 | `fg.schema.add(*classes)` shipped 混杂 register/extend 语义 | ✓ 仍准确 — Slice 1+2 不动 `_SDKSchemaManager.add`(Slice 1 Form I 改 descriptors 通过 schema_compile,不动 add 入口形态)|

**Conclusion**:Stage 1 audit doc §7.3 baseline 经 Slice 1+2 close 仍 accurate,Slice 3a 直接 inherit。**无 drift,无 re-audit 必要**。

### 2.3 Slice 2 carry-forward 跟 Slice 3a in-scope 项映射

Slice 2 §10.9 listed 4 carry-forward;Slice 3a 接住其中 3 项:

| Slice 2 carry-forward | Slice 3a in-scope? | 落地位置 |
|---|---|---|
| **ADR-API Q14 schema-evolution hook**(`fg.schema.register/extend/apply`)| ✓ in scope | Q14 §4.5 + ADR-IC §4.3.6 enforcement at `_SDKSchemaManager.extend` |
| **ADR-API Q10 `fg.entities.create/delete/exists` namespace migration**(Slice 3a)| ✓ in scope | Q10 §4.1.2 migration mapping 新增项 |
| **Step 2+ `:exists` removal**(per ADR-IC §4.4.4)| ✗ NOT in Slice 3a | Step 2+ 独立 cycle |
| **Step 2+ shadow store removal**(per ADR-IC §4.2.4)| ✗ NOT in Slice 3a | Step 2+ 独立 cycle(Slice 3a 加 `fg.entities.create` 但不立即 remove shadow store)|

## 3. Shipped surface inventory(read at preflight-row-drafting time)

### 3.1 SDK property accessors(`fg.<namespace>` → manager class)

| 行号 | Property | Manager 类型 | Q10 target |
|---|---|---|---|
| `sdk/store.py:1192` | `fg.schema_ir` | `dict[str, Any]` | 保留(read-only IR access) |
| `sdk/store.py:1200` | `fg.assertions` | `_SDKAssertionsManager` | **Q10 rename + Q11 type-split** → `AssertionsManager` |
| `sdk/store.py:1204` | `fg.schema` | `_SDKSchemaManager` | **Q14 `add` 拆三分**(同 manager,extend method set)|
| `sdk/store.py:1213` | `fg.read` | `_SDKReadManager` | **Q10 删除** → `fg.entities` |
| `sdk/store.py:1218` | `fg.write` | `_SDKWriteManager` | **Q10 删除** → `fg.fields` + 部分挪 `fg.assertions` / `fg.entities` |

### 3.2 SDK flat top-level shortcuts on `SDKStore` / `FactGraph`

shipped flat shortcuts(coexist with namespaced managers):

| 行号 | Method | 当前形态 | Q10 target |
|---|---|---|---|
| `sdk/store.py:1888` | `fg.ref(EC, **id)` | shadow store populate | **挪 fg.entities.ref**;flat shortcut 是否保留待 Slice 3a §6 锁定(ADR-API 未显式锁 flat 是否消失) |
| `sdk/store.py:1266` | `fg.get(EC, **id)` | sdk_get factory | 同上 — 挪 fg.entities.get 还是 flat 留 |
| `sdk/store.py:1291` | `fg.find(EC, ...)` | sdk_find | **find → where 动词统一**;flat 是否保留 + 是否 rename → fg.entities.where |
| `sdk/store.py:1314` | `fg.match(EC, ...)` | sdk_match | 挪 fg.entities.match |
| `sdk/store.py:1332` | `fg.edit(EC, **id)` | sdk_edit factory(EntityEditor)| **挪 fg.entities.edit**(per ADR-API §4.1.2 + ADR-IE §4.8)|
| `sdk/store.py:1935` | `fg.set(F, e_ref, v)` | `_apply_field_mutation` | 挪 fg.fields.set;flat 保留? |
| `sdk/store.py:1978` | `fg.add(F, e_ref, v)` | `_apply_field_mutation` | 挪 fg.fields.add;flat 保留? |
| `sdk/store.py:2124` | `fg.retract(asrt_id)` | retract guard(Slice 2 Step 3 wrap)| **挪 fg.assertions.retract**(Layer 3);flat 保留? |

**Open Q for blueprint scope**(见 §8 PF-S1):flat top-level shortcuts(`fg.set` / `fg.add` / `fg.get` / `fg.ref` / `fg.retract` / `fg.edit`)Slice 3a 内是否消失?ADR-API §4.1.4 删除清单只列 `fg.read.*` / `fg.write.*` namespace 整删,没显式说 flat 同步删。文案 wording 倾向 ADR-API 是 namespace-only refactor,flat 保留作为 user ergonomic shortcut(Slice 2 emission contract tests 也大量用 `fg.ref + fg.set`)。需 reviewer 明确。

### 3.3 `_SDKReadManager` methods(Q10 → 删除整 namespace)

`sdk/store.py:533-555`(class definition + 4 methods):

| Method | Signature | ADR-API target |
|---|---|---|
| `get(*args, **kwargs)` | 委托 `sdk_get` | `fg.entities.get` |
| `find(*args, **kwargs)` | 委托 `sdk_find` | `fg.entities.where`(rename + verb 统一)|
| `match(*args, **kwargs)` | 委托 `sdk_match` | `fg.entities.match` |
| `ref(*args, **kwargs)` | 委托 `fg.ref`(shadow store) | `fg.entities.ref` |

### 3.4 `_SDKWriteManager` methods(Q10 → 删除整 namespace + 部分挪层)

`sdk/store.py:572-613`(class definition + 4 methods):

| Method | Signature | ADR-API target | Layer 移动 |
|---|---|---|---|
| `set(*args, **kwargs)` | 委托 `fg.set` | `fg.fields.set` | same Layer 2 |
| `add(*args, **kwargs)` | 委托 `fg.add` | `fg.fields.add` | same Layer 2 |
| `retract(*args, **kwargs)` | 委托 `fg.retract` | `fg.assertions.retract` | **Layer 2 → Layer 3**(asrt_id 是 Layer 3 nav key)|
| `edit(*args, **kwargs)` | 委托 `fg.edit` | `fg.entities.edit` | **Layer 2 → Layer 1**(EC + identity 是 Layer 1 nav key) |

### 3.5 `_SDKAssertionsManager` methods(Q10 rename + Q11 type-split)

`sdk/store.py:431-499`(class definition + 7 methods):

| Method | Signature | ADR-API target |
|---|---|---|
| `by_id(asrt_id)` | Layer 3 navigation | 保留 `fg.assertions.by_id` |
| `by_ids(asrt_ids)` | Layer 3 batch nav | 保留 `fg.assertions.by_ids` |
| `active` property | scope ledger | 保留 `fg.assertions.active`(委托内部 `_ledger_view: AssertionView`)|
| `all` property | scope ledger | 保留 `fg.assertions.all` |
| `field(F)` | 窄化到 field scope | 保留;返回类型 `FieldAssertions` → **改 `AssertionView`**(Q11)|
| **NEW** `where(field=, e_ref=, value=, value_tag=, _meta=)` | — | **新增** canonical filter(per ADR-API §4.1.2 + §4.4) |
| **NEW** `retract(asrt_id, *, meta=None)` | — | **新增**(从 fg.write.retract 挪过来,Slice 2 Step 3 wrap 跟着挪)|

Q11 内部 contract:`AssertionsManager` 内部持 `_ledger_view: AssertionView`,read shortcuts 全委托;type-level 防 user 在 view 上调 retract。

### 3.6 `_SDKSchemaManager` methods(Q14 → `add` 拆三分)

`sdk/store.py:502-530`(class definition + 3 methods):

| Method | Signature | ADR-API target |
|---|---|---|
| `ingest(*args, **kwargs)` | 委托 sdk_ingest | 保留 `fg.schema.ingest` |
| `validate_provenance(*args, **kwargs)` | 委托 sdk_validate_provenance | 保留 `fg.schema.validate_provenance` |
| `add(*schema_classes, **kwargs)` | shipped 混杂 register/extend 语义 | **Q14 删除** → 拆 `register / extend / apply` 三分 |
| **NEW** `register(EC)` | — | 新 entity_type 注册 + SchemaIndex cache build(per ADR-IC §4.3.1 union update)|
| **NEW** `extend(EC)` | — | additive Field 扩展 + **ADR-IC §4.3.6 enforce**(Identity↔Field swap reject + `:exists` predicate protect)|
| **NEW** `apply(EC)` | — | safe diff convenience(per ADR-API §4.5.4 algorithm)|

### 3.7 AssertionRecordSet + FieldAssertions + AssertionNamespace(Q11 + Q12 + Q13)

`sdk/facade.py:91-200`(`AssertionRecordSet`):

| 行号 | Member | Q target |
|---|---|---|
| `facade.py:133-160` | `where(*, value, source, trace_id, version, meta)` flat kwargs signature | **Q13** flat kwargs 删 → `where(*field_filters, value, value_tag, _meta=None)` |
| `facade.py:162-172` | `at(t)` | 保留 — 有特殊语义(per ADR-API §4.2.2 + design-point §12.5 Rule 4)|
| `facade.py:174-183` | `version(v)` | **Q12 删除** → 用 `where(_meta={"version": v})` |
| `facade.py:185-188` | `by_id(asrt_id)` | 保留 |
| `facade.py:190-202` | `one()` / `all()` / `first()` | 保留 |

`sdk/facade.py:205-255`(`FieldAssertions`):

| 行号 | Member | Q target |
|---|---|---|
| `facade.py:219-221` | `active` property | **Q11 合并入** `AssertionView`(scope = entity + field)|
| `facade.py:223-225` | `history` property | 保留(per ADR-API §4.2.4 deprecated alias of `.all`;**不默认发 DeprecationWarning** 防测试失败;env opt-in)|
| `facade.py:227-229` | `all` property | 保留 |
| `facade.py:231-244` | `at(t)` | 保留 |
| `facade.py:246-255` | `version(v)` | **Q12 删除** |

`sdk/facade.py:258-300`(`AssertionNamespace`):

| 行号 | Member | Q target |
|---|---|---|
| `facade.py:263-269` | `field(field)` 返回 `FieldAssertions` | **Q11 改返回** `AssertionView`(scope = entity + field)|
| `facade.py:271-277` | `active()` | 合并入 AssertionView |
| `facade.py:279-…` | `all()` | 合并入 AssertionView |

### 3.8 EntityEditor + IdentityEditor + FieldEditor + sdk_edit(per ADR-IE)

`sdk/facade.py:390-486 + 490-554 + 678-686`:

| Class / Function | Q3a target |
|---|---|
| `FieldEditor`(line 390)| 保留 — ADR-IE §4.5 cardinality enforcement |
| `IdentityEditor`(line 449)| 保留 — Slice 2 Step 6 已更新文案;ADR-IE §4.4 + ADR-IC §4.1 Layer 1 reject |
| `EntityEditor`(line 490)| 保留 — ADR-IE §4.1 lifecycle + §4.2 commit/rollback + §4.3 context manager + §4.7 EditorClosedError |
| `sdk_edit(sdk, EC, **id)`(line 678)| 保留 — ADR-IE §4.8 edit-existing-only contract;Slice 3a 通过 `fg.entities.edit` 重新暴露(替代 `fg.write.edit`)|

**ADR-IE 衔接锁**:Slice 3a 只动 `fg.write.edit` → `fg.entities.edit` rename + 重新暴露;EntityEditor 公开 contract 不改。

## 4. 三层 navigation key 排他边界 enforcement(per ADR-API §4.1.1)

Slice 3a 必须实施的 排他原则 — type signature 层 enforcement:

| Layer | Manager | 不接受 input | enforcement 模式 |
|---|---|---|---|
| **Layer 1 `fg.entities.*`** | `EntitiesManager` | `asrt_id` 参数 / `(Field, e_ref)` value 写入 | runtime type check + raise `SDKStoreError` 含正确 layer 提示 |
| **Layer 2 `fg.fields.*`** | `FieldsManager` | `asrt_id` 参数(per ADR-IC §4.1 P2-1)/ `EntityClass + identity` 形态 | 同上 |
| **Layer 3 `fg.assertions.*`** | `AssertionsManager` | `EntityClass` 类型参数(用 `field=EntityCls.field` 走 Field descriptor) | 同上;`AssertionsManager` 唯一 `retract(asrt_id)` 入口 |

跨 layer 参数形态用错(如 `fg.fields.set(asrt_id, value)`)→ raise `SDKStoreError`,error message 含正确 layer + ADR-API §4.1.1 pointer。

## 5. 三层 + 5 个 sub-decision 综合 triage 表

| ADR-API ref | shipped surface(file:line) | 当前形态 | ADR target 形态 | 落地动作 | 失败模式 |
|---|---|---|---|---|---|
| **Q10 §4.1** | `sdk/store.py:533` `_SDKReadManager` + `sdk/store.py:1213` `fg.read` property | shipped 4 methods(`get/find/match/ref`)| **删除** | namespace 整删 + 替换 `_SDKEntitiesManager` + `fg.entities` property | 测试 `tests/test_schema_field_add_lifecycle.py:261/281/293/302/312` 用 `fg.read.get` — Slice 3a impl 必须 migrate(Step grep + sed)|
| **Q10 §4.1** | `sdk/store.py:572` `_SDKWriteManager` + `sdk/store.py:1218` `fg.write` property | shipped 4 methods(`set/add/retract/edit`)| **删除** | namespace 整删 + 替换 `_SDKFieldsManager`(`set/add` Layer 2)+ retract 挪 `fg.assertions.retract`(Layer 3 nav key)+ edit 挪 `fg.entities.edit`(Layer 1 nav key)| 测试 `tests/test_schema_field_add_lifecycle.py:271/280/311` + `tests/test_schema_mutation_lifecycle.py:226/254` 用 `fg.write.set/add` — Slice 3a impl migrate |
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.entities.create(EC, **id, meta=...)` | NEW method on `_SDKEntitiesManager` — 走 `_materialization_ops` shipped 路径(per ADR-IC §4.2)+ 加 `EntityAlreadyExistsError` 防重复(per design-point §13.1)| Slice 2 error wording 已引用该 API(`sdk/facade.py:478`)— Slice 3a 落地后 wording 实际 actionable |
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.entities.delete(e_ref)` 或 `fg.entities.delete(EC, **id)` | NEW method — 整批 retract 该 e_ref 下所有 Active Claim(Identity + `:exists` + Field)atomic(per ADR-IC §4.1 强制点 3)| Slice 2 error wording 已引用(`sdk/facade.py:477`)|
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.entities.exists(EC, **id)` | NEW method — 比 `get(...) is None` cheap;读 `<EntityType>:exists` Active set | — |
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.fields.retract(F, e_ref, value)` value-oriented | NEW method on Layer 2 — value-based retract(per ADR-IC §4.1 P2-1)| — |
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.fields.delete(F, e_ref)` | NEW method — clear all values for (F, e_ref) | — |
| **Q10 §4.1** | **新增**(无 shipped)| — | `fg.fields.get(F, e_ref)` | NEW method — 物化当前 value | — |
| **Q11 §4.2** | `sdk/facade.py:205-255` `FieldAssertions` class | shipped per-field assertion view(active/history/all/at/version)| **删除** | 合并入 `AssertionView`(scope = entity + field)— `snap.field(F)` 返回类型从 `FieldAssertions` 改 `AssertionView` | 测试 `tests/test_sdk_assertion_record_set.py:85` + `tests/test_sdk_assertion_record_set_view_filters.py:93-130` 用 `snap.field(...).version(...)` — Slice 3a impl migrate(version 用法跟 Q12 同步删)|
| **Q11 §4.2** | `sdk/facade.py:258-300` `AssertionNamespace` class | shipped entity-scoped assertion view(field/active/all)| **删除** | 合并入 `AssertionView`(scope = entity)— `snap.assertions` 返回类型改 `AssertionView` | — |
| **Q11 §4.2** | `sdk/store.py:431` `_SDKAssertionsManager` class | shipped 7 methods(`by_id/by_ids/active/all/field` + Slice 2 Step 3 retract wrap)| **rename + type-split** | rename → `AssertionsManager`(public);内部委托 `_ledger_view: AssertionView`;Q10 加 `where(...)` + `retract(asrt_id)` mutation method | Slice 2 Step 3 retract guard wrap 跟 retract 一起挪 `AssertionsManager.retract` — wrap 内部不变,只是入口换 |
| **Q12 §4.3** | `sdk/facade.py:174-183` `AssertionRecordSet.version(v)` | shipped first-class method | **删除** | 用 `where(_meta={"version": v})` 替代;**无 alias / 无 DeprecationWarning** | 测试 `tests/test_sdk_assertion_record_set_view_filters.py:93/110/130/131` + `tests/test_sdk_assertion_record_set.py:85` — Slice 3a impl migrate(grep + sed:`\.version\(` → `.where(_meta={"version": ...})`)|
| **Q12 §4.3** | `sdk/facade.py:246-255` `FieldAssertions.version(v)` | shipped first-class method | **删除** + 跟 Q11 FieldAssertions 删一起 | 同上 | 同上 |
| **Q13 §4.4** | `sdk/facade.py:133-160` `AssertionRecordSet.where(*, value, source, trace_id, version, meta)` flat kwargs | shipped signature with 4 flat kwargs | **签名 breaking change** | 改 `where(*field_filters, value=_MISSING, value_tag=_MISSING, _meta: dict | None = None)`;flat `source/trace_id/version/meta` 全删 | 测试 `tests/*` 用 `where(source=...)` / `where(trace_id=...)` / `where(version=...)` — 3 file 测试 — Slice 3a impl migrate;docs 163 处需 update |
| **Q14 §4.5** | `sdk/store.py:502` `_SDKSchemaManager.add(*schema_classes, **kwargs)` | shipped 混杂 register/extend 语义 | **拆三分** | `register(EC)` / `extend(EC)` / `apply(EC)` 三个独立 method;`add` 整删 | 测试 `tests/*` + examples + docs 用 `fg.schema.add(...)` 13 处需 migrate |
| **Q14 §4.5** | `sdk/store.py:_SDKSchemaManager` | shipped 无 `extend` method | **新增** `extend(EC)` | 实施 ADR-IC §4.3.6 enforce part 1(Identity↔Field swap reject)+ part 2(`:exists` predicate protect)+ 同步 SchemaIndex cache union update | Slice 2 Step 1 已 ship SchemaIndex frozensets(基础)— Slice 3a 加 extend 时 wire cache rebuild hook(per Slice 2 §10.9 carry-forward)|

## 6. Blast radius assessment

`grep -rln <pattern>` counts at preflight time(2026-05-30 on `c927d41f` HEAD):

| Pattern | tests/ | src/factgraph/sdk/docs/ + docs/ | examples/ | 备注 |
|---|---|---|---|---|
| `fg\.read\.` | 4 files | 163 hits | 8 hits | tests:`test_schema_field_add_lifecycle.py`(5 occurrences)+ 3 其他 file;docs 主要在 `04_api_surface.en.md` / `02_readwrite_and_ingest.en.md` |
| `fg\.write\.` | 3 files | 147 hits | 5 hits | tests:`test_schema_field_add_lifecycle.py` + `test_schema_mutation_lifecycle.py` + 1 其他 |
| `fg\.assertions\.` | 1 file | 43 hits | 9 hits | shipped 用得少 — 主要存在于 docs + examples |
| `fg\.schema\.add` | 3 files | 13 hits | 0 hits | examples 不依赖 |
| `\.version\(` | 2 files | 27 hits | 5 hits | 主要测试:`test_sdk_assertion_record_set_view_filters.py` + `test_sdk_assertion_record_set.py` |
| `\.find\(` | many files mixed | 35 hits | 5 hits | **注意**:`find` 含 entity find + dict/set find 等非 ADR-API 用法;Slice 3a impl preflight grep 需 disambiguate |
| where flat kwargs(`source=` / `trace_id=` / `version=`) | 3 occurrences | 多处 | — | docs 占主要量 |

**结论 — 测试 blast radius surprisingly small**:全部 Q10-Q14 相关 test files 不超过 ~10 个,大部分 occurrences 集中在 `test_schema_*` 系列;**docs blast radius 大**(主要 `04_api_surface.en.md` + `02_readwrite_and_ingest.en.md` + `00_user_guide.en.md`)。Slice 3a impl Step plan 必然 dedicated grep-and-migrate steps,docs 全面 rewrite。

## 7. 依赖 + 顺序 + 跨 slice 契约

### 7.1 与 Slice 2 close 状态的关系

- Slice 2 SchemaIndex frozensets cache(`73993ebd`)— Slice 3a `fg.schema.extend` 实施时 wire `extend` hook 触发 cache union rebuild(per Slice 2 SF4 carry-forward)
- Slice 2 三层 INV-7c retract guard(`187a2918` / `12475859` / `16aeff69` / `a4853a0a`)— Slice 3a retract 挪 `fg.assertions.retract` 入口,**guard 不动**(只动入口名)
- Slice 2 Step 6 IdentityEditor + plan_write_command 文案(`c2d659c1`)已用 ADR-IC §4.1 wording — Slice 3a 落地 `fg.entities.delete/create` 后 user 实际可调,wording actionable
- Slice 2 shadow store legacy 注释(`d46b9fe7`)— Slice 3a 加 `fg.entities.create` 走 eager emission 路径,**但 Slice 3a 显式 NOT remove shadow store**(per ADR-IC §4.2.4 — Step 2+);两路径 coexist(eager `fg.entities.create` + lazy `fg.set` first-write)
- Slice 2 emission contract tests(`ab168063`)11 tests 用 `fg.ref + fg.set` / `SDKBatchTx` / `EntityEditor.commit` 三 shipped paths — Slice 3a rename 后 tests 同步 migrate

### 7.2 与 ADR-IE / ADR-IC 的 enforcement boundary

- ADR-IE §4.8 sdk_edit factory edit-existing-only — Slice 3a `fg.entities.edit` 暴露 `sdk_edit` 不动 contract
- ADR-IC §4.3.6 explicit contract — Slice 3a Q14 `fg.schema.extend` 必须 enforce 两项(Identity↔Field swap reject + `:exists` predicate protect);Slice 2 SchemaIndex cache 已 ship `is_entity_exists` flag,Slice 3a extend 可直接用
- ADR-IC §4.1 Layer 2 reject — Slice 3a `fg.fields.*` 改入口名后 reject 逻辑不变(plan_write_command:is_identity_field check 已 ship — Slice 2 Step 6)
- ADR-IC §4.2 emission contract — Slice 3a `fg.entities.create` 必须 carry 完整 identity bundle(per SF8);shadow store 现 fallback,eager path 主线

### 7.3 Q-PR1 carve-out 继承

per meta-ADR §4.4 Step 1 zero-Q-PR1 dependency + Slice 2 SF5/SF11:

| 文件 | Slice 3a 期望 0 diff |
|---|---|
| `src/factgraph/core/evidence/write_protocol.py` | ✓ |
| `src/factgraph/core/store/ledger.py` | ✓ |
| `src/factgraph/core/store/_builders.py` | ✓ |
| `src/factgraph/adapters/pyreason/*` | ✓ |
| `src/factgraph/core/derivation/accept.py:401` | ✓(SF11 internal-rollback intentionally unguarded)|

Slice 3a 是 SDK shell + application 层 refactor;**不下沉到 protocol / ledger / pyreason / derivation**。

### 7.4 Sacred branches + dirty baseline 继承

- Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` 不动
- Sacred `v0.1-oss-prep` 不动
- Dirty baseline(4 M + 1 D + 2 untracked)继续保留
- Branch fork point:Slice 2 close `c927d41f`(`v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` push tip)
- 建议 Slice 3a branch:`v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30`

## 8. 5-bucket findings

### 8.1 Required amendment before scoped(PF-R*)

**(无)** — ADR-API + meta-ADR + ADR-IE + ADR-IC 4 ADR baseline 互锁状态 verified;Stage 1 audit doc §7.3 Q10-Q14 baseline post-Slice-1/2 仍 accurate(per §2.2);Slice 1+2 carry-forward 跟 Slice 3a in-scope 项 mapping clean(per §2.3)。无 ADR amend 必要。

### 8.2 Recommended amendment before scoped(PF-Rec*)

**(无)** — 直接进 blueprint draft 即可。所有 sub-decision target form 已 fully locked in ADR-API §4.1-§4.5。

### 8.3 Verified assumptions(PF-V*)

- **PF-V1**:ADR-API + meta-ADR + ADR-IE + ADR-IC 4 ADR adopted commit lineage 全 ancestor of `c927d41f` Slice 2 close HEAD — `git merge-base --is-ancestor` 已 verify
- **PF-V2**:Q-PR1 carve-out 0 diff against Slice 1 close `9cef674b..c927d41f` — Slice 3a 继承 SF5/SF11 lock
- **PF-V3**:Stage 1 audit doc §7.3 Q10-Q14 baseline 仍 accurate(per §2.2 spot-check)
- **PF-V4**:Slice 2 §10.9 4 项 carry-forward 中 ADR-API Q14 + Q10 fg.entities.* 由 Slice 3a 接住;Step 2+ `:exists` removal + shadow store removal 留 Step 2+(per §2.3 mapping)

### 8.4 Scoped-detail items(PF-S*)

以下 items 在 Slice 3a blueprint draft 阶段 锁定,**不在本 preflight 解决**:

- **PF-S1**:**flat top-level shortcuts**(`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.get` / `fg.ref` / `fg.find` / `fg.match`)Slice 3a 内是否保留?ADR-API §4.1.4 删除清单只列 `fg.read.*` / `fg.write.*` namespace 整删,**没显式说 flat 同步删**。文案 wording 倾向 ADR-API 是 namespace-only refactor — 但 flat 跟 namespace 同方法名 + 同 signature 是双轨,违反 ADR §4.1.3 "no alias" lock。**需 blueprint §6 Scope Freeze 锁定**:option A 保留 flat 作为 ergonomic shortcut(双轨期不算 alias 因为不是 deprecation);option B flat 全删 + 用户被迫走 namespace;option C 保留部分(`fg.ref` / `fg.set` / `fg.add`)删其他(`fg.retract` / `fg.edit` / `fg.find`)。

- **PF-S2**:**`fg.entities.delete(e_ref)` vs `fg.entities.delete(EC, **id)` overload**:ADR-API §4.1.2 写 "或" — 两种形态都 accept?signature overload 还是 single signature with type detection?建议 blueprint §5 锁定 signature(推荐 `fg.entities.delete(e_ref_or_selector: str | tuple[type, dict])` 或 keyword-only `fg.entities.delete(e_ref=None, *, entity_cls=None, **identity)`)。

- **PF-S3**:**`fg.entities.delete(...)` 整批撤销 implementation site**:走 application layer NEW `delete_entity_command` DTO + planner + executor(per `project_application_first_runtime_authority.md`)还是 inline 在 SDK shell?推荐 application layer for INV-6 compliance + future API consistency。需 blueprint §5 锁定路径。

- **PF-S4**:**`fg.entities.create(...)` shadow store interaction**:eager emission path 跟 shipped lazy materialization 共存 — `fg.entities.create(EC, **id)` 应该:(a)直接 emit Identity + `:exists` Claims 到 ledger 同时 populate shadow store;(b)仅 populate shadow store 等 first Field write;(c)别的?ADR-IC §4.2.4 forward-pointer 说 Step 2+ shadow store removal,但 Slice 3a 不 remove。**推荐 (a)**:eager emission to ledger + shadow store population(legacy compat 保留 lazy 路径给 `fg.ref + fg.set` 用户)。需 blueprint §5 + §6 锁定行为。

- **PF-S5**:**Q11 `view.history` deprecated alias 边界**:per ADR-API §4.2.4 — 保留为 alias of `.all`;不默认 DeprecationWarning,env var opt-in `FACTGRAPH_WARN_DEPRECATED=1`。Slice 3a blueprint §5 需明确 env var 名 + 触发位置。

- **PF-S6**:**`AssertionsManager.where` canonical filter signature 细节**:`where(*, field=_MISSING, e_ref=_MISSING, value=_MISSING, value_tag=_MISSING, _meta=_MISSING)` — `_MISSING` sentinel 是 `_ASSERTION_FILTER_MISSING`(已 ship `sdk/facade.py:18`)还是新 sentinel?复用已 ship 即可。需 blueprint §5 确认。

- **PF-S7**:**docs migration scope** Slice 3a vs Slice 4 分工:`04_api_surface.en.md`(Slice 2 §7 新增的 Identity Claim Emission and Reject Semantics 已 lockup ADR-API §4.1 terminology — 部分已用 `fg.entities.delete` 引用)+ `02_readwrite_and_ingest.en.md` + `00_user_guide.en.md` 是 load-bearing — Slice 3a 内同 slice 落地?还是 Slice 4 wider polish?per ADR-DOCS §4.2.2 + Slice 2 SF6 precedent 推荐 load-bearing 同 slice。其他 docs(`01_concepts.en.md` / `03_rules_and_inferences.en.md` / `07_walker_and_advanced.en.md`)Slice 3a 还是 Slice 4?

- **PF-S8**:**Step plan slicing within Slice 3a**:Q10-Q14 5 个 sub-decision 一个 Step 一个还是更细分?推荐(per Slice 2 10-Step precedent):
  - Step 0 pre-impl grep(read-only)
  - Step 1 `_SDKEntitiesManager` 新 class + 4 base methods(get/where/match/ref)
  - Step 2 `fg.entities.create/delete/exists` 3 个 NEW methods(application layer DTO + planner + executor)
  - Step 3 `_SDKFieldsManager` 新 class + set/add/retract/delete/get
  - Step 4 `_SDKAssertionsManager` rename → `AssertionsManager` + 新 `where` + retract 挪过来(Slice 2 Step 3 wrap 跟着挪)
  - Step 5 `fg.entities.edit` 挪层(ADR-IE 衔接 — sdk_edit factory 不动)
  - Step 6 `fg.read.*` + `fg.write.*` namespace 删除 + property accessor 改 `fg.entities` / `fg.fields`
  - Step 7 `AssertionView` 类型合并(Q11)+ FieldAssertions / AssertionNamespace 删除
  - Step 8 `version(v)` hard remove(Q12)+ `where` flat kwargs hard remove(Q13)
  - Step 9 `fg.schema.add` 删 + `register/extend/apply` 三分(Q14)+ ADR-IC §4.3.6 enforce
  - Step 10 tests / docs / examples migration grep + sed 全 sweep
  - Step 11 final acceptance + §10 Outcome + Status implemented
  - Step 12 archive

12 Steps 比 Slice 2 10 Step 稍大但 sub-decision split 干净。需 blueprint §8 锁定具体切分。

### 8.5 Abandonment blockers

**(无)** — 无 abandonment 必要。

### 8.6 Healthy distribution check

Per template line 39 "Healthy distribution: 1-4 Required, 1-2 Recommended, 0-3 Verified, 0-2 Scoped-detail, 0 Abandonment":

| Bucket | 实际 | Healthy 范围 | 评价 |
|---|---|---|---|
| Required | 0 | 1-4 | **下界外**(健康 — 表示 ADR baseline rock-solid)|
| Recommended | 0 | 1-2 | 下界外(同上)|
| Verified | 4 | 0-3 | 上界外少量(健康 — 表示 cross-ADR + cross-slice lineage 都 verified)|
| Scoped-detail | 8 | 0-2 | **显著上界外** — Slice 3a 是 multi-sub-decision refactor,scoped-detail 不可避免 |
| Abandonment | 0 | 0 | 健康 |

**结论**:分布偏向 Verified + Scoped-detail,无 Required/Recommended/Abandonment — 表示 ADR baseline 干净,Slice 3a blueprint draft 可直接进入,**8 个 scoped-detail items 是 blueprint draft 时回答的 scope questions(不是 blockers)**。

## 9. Cross-slice contract preservation

| Contract | Slice 3a 保留? | 验证方式 |
|---|---|---|
| Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` 不动 | ✓ | Per-commit `git rev-parse master` check(per Slice 2 §7.12 G8 sustained)|
| Sacred `v0.1-oss-prep` 不动 | ✓ | 同上 |
| Q-PR1 carve-out 5 sacred paths 0 diff | ✓ | `git diff --name-only 9cef674b..HEAD --` 5 sacred paths returns empty(累计 Slice 1+2+3a)|
| INV-9 unary fact(per ADR-IC §4.2 emission contract — Layer 2 fields API NEVER an emission path) | ✓ | `fg.fields.set/add/retract/delete/get` 不接受 N-ary value;`fg.entities.create` 必须 carry 完整 identity bundle |
| INV-7a/b/c(Identity 三层 immutability) | ✓ | Slice 2 三层 enforcement(application source-of-truth + SDK shell + 2 application 写入路径)retract guard 在 `fg.assertions.retract` 入口下继续 wrap |
| ADR-IC §4.3.6 explicit contract(part 1 + part 2)| ✓ + 主动满足 | Slice 3a Q14 `fg.schema.extend` 实施(part 1 Identity↔Field swap reject + part 2 `:exists` predicate protect) |
| ADR-IE §4.8 sdk_edit factory edit-existing-only | ✓ | Slice 3a `fg.entities.edit` 暴露 sdk_edit,contract 不改 |
| ADR-FI Form I descriptors stable | ✓ | Slice 1 close 已 ship;Slice 3a 不动 descriptor signatures |

## 10. Findings summary table

| Bucket | Count | Items |
|---|---|---|
| Required | 0 | — |
| Recommended | 0 | — |
| Verified | 4 | PF-V1(4 ADR lineage)/ PF-V2(Q-PR1 carve-out 0 diff)/ PF-V3(§7.3 baseline post-Slice-1/2 accurate)/ PF-V4(Slice 2 carry-forward 映射 clean)|
| Scoped-detail | 8 | PF-S1(flat top-level)/ PF-S2(delete signature overload)/ PF-S3(delete impl site)/ PF-S4(create shadow store interaction)/ PF-S5(history alias env var)/ PF-S6(where signature sentinel)/ PF-S7(docs migration scope)/ PF-S8(Step plan slicing)|
| Abandonment | 0 | — |

## 11. Recommended next actions

per `feedback_preflight_code_audit_required.md` + Slice 2 cadence:

1. **Hand off this preflight audit doc to reviewer for review** — verify §2 ADR baseline + §3 shipped surface + §5 triage table + §8 5-bucket findings + §10 summary
2. **Reviewer 回 verdict**:8 个 PF-S items(scope questions)的 lock-in decisions — 之后 Slice 3a blueprint draft 直接 inherit
3. **Reviewer 授权后起 Slice 3a branch** `v0.2.0-blueprint-slice-3a-api-namespace-2026-05-30` from Slice 2 close `c927d41f`
4. **Draft Slice 3a blueprint** 在新 branch 上 — 用 `workflow/templates/blueprints/task_blueprint.md` + paired audit log;blueprint §5 Scope Freeze 直接 lock §8 PF-S1-S8 + §5 triage table + §7 cross-slice contract
5. **Slice 3a blueprint review** by reviewer — 验证 SF 跟本 preflight findings 一致
6. **进 implementing**(Step 0 pre-impl grep + Step 1-12)

## 12. Acceptance for this preflight

- [x] All ADR-API + meta-ADR + ADR-IE + ADR-IC sub-decisions re-read at preflight-row-drafting time(per Rule 1)
- [x] Stage 1 audit doc §7.3 Q10-Q14 baseline spot-checked post-Slice-1/2 close
- [x] Shipped surface inventory(4 manager classes + 8 flat shortcuts + AssertionRecordSet/FieldAssertions/AssertionNamespace + EntityEditor + sdk_edit)所有 referenced 行号 re-read
- [x] Findings classified into 5 buckets
- [x] At least 2 critical findings spot-checked independently(ADR-IC §4.3.6 contract part 1+2 by extracting wording from ADR + verifying SchemaIndex flag `is_entity_exists` shipped;Q-PR1 carve-out 0 diff by `git diff --name-only 9cef674b..HEAD`)
- [x] No abandonment blocker surfaced
- [x] Cross-slice contract preservation verified(§9)
- [x] Blast radius assessed across tests + sdk docs + docs + examples(§6)
- [x] Q-PR1 carve-out 继承 explicit lock(§7.3)
- [x] Sequencing + dependency notes complete(§7)
- [x] 8 scoped-detail items articulated as scope questions for blueprint(§8.4)

---

Lifecycle:本 preflight stay in `workflow/audit/active/` 直到 Slice 3a blueprint archive(per CADENCE Q3 §4.6;blueprint archive 时同 batch 移到 `workflow/audit/archive/`)。
