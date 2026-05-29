# Q-DOCS Decision: Docs sync timing strategy + per-slice load-bearing vs Slice 4 consolidated + D1-D11 row treatment

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Q17 docs sync timing(per-slice load-bearing + Slice 4 consolidated 混合策略)+ D1-D11 row 落点分配 + 跨 doc 一致性 unification 形态。**Stage 2 收尾 ADR** — 关闭所有前置 ADR 的 docs sync follow-up commitments。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q17 row(`audit:531`)+ §5.3 D1-D11 rows(`audit:454-464`)+ §6 baseline shipped docs structure
  - **8 个 adopted Stage 2 ADRs 的 docs sync follow-up commitments**:
    - ADR-FI `b288ea9e` §4.1/§4.3-bis/§7.2 — Slice 4 docs sync(`04_api_surface.en.md` Form I overview + Field/Identity migration guides;`identity-mechanism-redesign §8` 对齐)
    - ADR-IC `2d0866ed` §7.2 — `identity-mechanism-redesign §5.2` 对齐 + `04_api_surface.en.md` INV-7c reject 行为表 + existence-claim transitional guard 说明
    - ADR-API `66434490` §4.3.4(Q12 migration note)+ §4.4.1(Q13 docs)+ §7.2 — Slice 4 docs sync 含 3-layer namespace + AssertionView + `_meta` + schema 三分 + `version(v)` 删除 migration note
    - ADR-SYS-A `75f1c8bc` §7.2 — `04_api_surface.en.md` G1/G2 guard 说明 + Layer C forward-looking 规约 + Layer E classification(wire-replay)
    - ADR-SYS-B `6b0ac349` §7.2 — `ledger-schema-specification §9` 时序对齐 + `04_api_surface.en.md` retract idempotency(find_revoker)+ `_meta` claim_meta path + INV-15 read filter + `add` multiset behavior change + Slice 3b dual-coexistence limitation
    - ADR-INV9 `c03e435d` §7.2 — `ledger-schema-specification §9.4` 对齐 + `identity-mechanism-redesign §11` 对齐(Slice 5 adapter rewrite docs)+ Slice 5 后 Claim DTO 终态说明
    - ADR-IE `9fd0ffb5` §7.2 — `04_api_surface.en.md` EntityEditor section + `identity-mechanism-redesign §12.8` Identity 三层 immutable boundary 对齐
- Outputs / Downstream:
  - Slice 4 docs sync blueprint(`workflow/blueprints/active/2026-05-29_slice-4-docs-sync.md` 起草前置)— 本 ADR §4.3 是 Stage 4 acceptance criteria outline
  - Per-slice docs sync acceptance criteria — 本 ADR §4.2 锁 Slice 1/2/3a/3b/5 各自的 load-bearing docs sync 必备项
- Related:
  - Peer ADRs:无(Stage 2 收尾)
- Branch: `v0.2.0-q-docs-sync-decision-2026-05-29`
- Depends on(cumulative — Stage 2 全部 adopted ADRs):
  - `2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`
  - `2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`
  - `2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`
  - `2026-05-29_q-api-namespace-decision.md` adopted @ `66434490`
  - `2026-05-29_q-sys-a-system-namespace-decision.md` adopted @ `75f1c8bc`
  - `2026-05-29_q-sys-b-revokes-migration-decision.md` adopted @ `6b0ac349`
  - `2026-05-29_q-inv9-adapter-enforcement-decision.md` adopted @ `c03e435d`
  - `2026-05-29_q-ie-entity-editor-decision.md` adopted @ `9fd0ffb5`

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q17 — Docs cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q17 | Cross-doc + public quickstart sync timing | `audit:531` | Docs |

audit Q17 question framing:
- option (a) Per-slice immediate sync — Step 1 各 slice 完成后立即同步;step-by-step shippable
- option (b) Consolidated Slice 4 docs sync — 合并到一个 docs sync slice 最后一起做;干净
- option (c) hybrid(本 ADR §4.1 选择)— per-slice load-bearing + Slice 4 consolidated

### 1.2 D1-D11 cumulative docs touchpoints(audit `:454-464`)

| Row | Touchpoint | Driver ADR | 5+1 state | 本 ADR 落点 |
|---|---|---|---|---|
| D1 | `04_api_surface.en.md` §0 Namespace Map `fg.read.get` / `fg.write.add` examples | ADR-API §4.1 三层 rename | (c) shape conflict | §4.4 Slice 3a |
| D2 | `04_api_surface.en.md` §2.3-§2.6 namespace tables | ADR-API §4.1 三层 + §4.5 schema 三分 | (c) shape conflict | §4.4 Slice 3a |
| D3 | `04_api_surface.en.md` §4 `FieldAssertions, AssertionRecordSet, ...` types section | ADR-API §4.2 AssertionView 统一 | (c) shape conflict | §4.4 Slice 3a |
| D4 | `assertions.md` line 145 `.at(t)` semantics | ADR-API §4.2 Rule 4 | (a) shipped covers + (e) Step 2+ deferred | §4.4 Slice 4 minor + Step 2+ |
| D5 | `assertions.md` lines 307-308 `.at(t)` / `.version(v)` shortcuts | ADR-API §4.3 Q12 version() hard remove | (c) shape conflict | §4.4 Slice 3a |
| D6 | `assertions.md` line 348 `.where(value=, source=, ...)` table row | ADR-API §4.4 Q13 `_meta` 统一 | (c) shape conflict | §4.4 Slice 3a |
| D7 | `assertions.md` lines 599-602 "fg.assertions.where NOT supported" 陈述 | ADR-API §4.1 三层 + §4.2 AssertionView | (c) shape conflict(关键!)| §4.4 Slice 3a |
| D8 | `04_api_surface.en.md` §2.14 `FrozenAssertionView` type 命名 | PDF triage C6(Step 2+) | (e) deferred-aligned | §4.4 Step 2+ |
| D9 | `04_api_surface.en.md` §2.14 + `fg.views` namespace | PDF triage C5(Step 2+) | (e) deferred-aligned | §4.4 Step 2+ |
| D10 | `core/store/ledger.py:512-580+` deprecated public methods | INV-1 + INV-3 + ADR-SYS-B 7-step migration | (b) small gap | §4.4 Slice 3b cleanup |
| D11 | `core/store/_builders.py:315-318` `is_entity_exists` / `is_identity_field` flag 使用点 | ADR-IC §4.2 emission + ADR-IC §4.3 cache | (f) target-gap | §4.4 Slice 2 |

### 1.3 Meta-ADR locked constraints relevant to Q17

- **§4.2 grouping**:Q17 单 Q 单 ADR(Docs cluster);不跨 cluster — 本 ADR 锁定 docs sync timing strategy + D1-D11 落点
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §4.4 Slice 5 docs sync 是 forward carve-out(per ADR-INV9 §4.4 三项绑定)— 不是 dep,Slice 3a / Slice 4 实施不被 block

### 1.4 Shipped docs structure baseline

**SDK 内部文档**(`src/factgraph/sdk/docs/`):
- `00_user_guide.en.md` / `01_concepts.en.md` / `02_readwrite_and_ingest.en.md` / `03_rules_and_inferences.en.md` / **`04_api_surface.en.md`**(核心 API 表面参考)/ `06_what_if_and_proof.en.md` / `07_walker_and_advanced.en.md` / `README.md`

**公开 quickstart**(`docs/official/kernel/quickstart/`):
- `index.md` / `first-factgraph.md` / `schema.md` / `read-write.md` / `database.md` / **`assertions.md`**(D4-D7 touchpoints)/ `semantics.md` / `evidence.md` / `rules-and-inferences.md` / `namespace-map.md` / `persistence.md`

**Design-point docs**(`workflow/design/design-points/active/`):
- `identity-mechanism-redesign.zh.md`(§5.2 / §8 / §10 / §11 / §12 跨多个 ADR 引用 sync)
- `ledger-schema-specification.zh.md`(§9 ledger migration + §4.6-§4.12 INV-9-15 sync)
- `explanation-completion-roadmap.zh.md`(out of scope — explainability stack)
- `append-only-ledger-evaluation.zh.md`(out of scope — alpha 范式评估)

**Module docs**(`src/factgraph/*/docs/`):
- 各 module docs README per `workflow/foundations/module_docs_convention.md`(Slice implementation 时各自 update)

## 2. Scope

本 ADR **锁**以下 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q17 strategy** | docs sync timing strategy = **hybrid (c)** — per-slice load-bearing(必做)+ Slice 4 consolidated(整体一致性) |
| **§4.2 Per-slice load-bearing acceptance** | 每个 Slice(1 / 2 / 3a / 3b / 5)blueprint 必须包含**该 slice 的 load-bearing docs sync**作为 Stage 4 acceptance criteria — shipped 之前 docs 跟 code 一致;否则该 slice 不可 mark `implemented` |
| **§4.3 Slice 4 consolidated docs sync content** | Slice 4 docs sync blueprint Stage 4 acceptance criteria — cross-doc 一致性 + 风格 unification + 残留 cleanup + migration note placement + 跨 ADR examples 统一 |
| **§4.4 D1-D11 row 落点分配** | D1-D11 各行明确分配到 Slice 1 / 2 / 3a / 3b / 4 / 5 / Step 2+ |
| **§4.5 Style / structural unification at Slice 4** | 终态 cross-doc 一致性 check — terminology(EntityEditor / Field / Identity / etc.)+ migration note placement + examples consistency + cross-reference 完整性 |

## 3. Non-scope

本 ADR **不**锁(per cross-ADR boundaries + meta-ADR §4.2 grouping):

| 不锁 | 留给谁 |
|---|---|
| 具体 docs 文本 wording / 详细 migration note 内容 | Slice X blueprint + Slice 4 docs sync blueprint implementation |
| Module docs(`src/factgraph/*/docs/`)update | Per-slice implementation per `workflow/foundations/module_docs_convention.md` |
| `explanation-completion-roadmap.zh.md` / `append-only-ledger-evaluation.zh.md` design-points update | 跟 explainability stack / alpha 评估 lane 独立;Stage 3+ ADR |
| Step 2+ docs items(D8 `FrozenAssertionView` rename / D9 `fg.views` rename)| Step 2+ ADR |
| Slice 5 adapter rewrite docs(ledger-spec §9.4 + identity §11 final align)| ADR-INV9 §4.4 三项绑定 carve-out;Slice 5 blueprint scope |
| `README.md`(repo root + module-level)maintenance | per slice implementation(non-load-bearing follow-up)|
| 各 slice blueprint 内部 slicing(具体 commit 顺序 / impl 顺序)| 各 slice blueprint |

## 4. Decision

### 4.1 Q17 docs sync timing strategy:**hybrid (c) — per-slice load-bearing + Slice 4 consolidated**

**锁定**:docs sync 走 **hybrid** 策略:
- **Per-slice load-bearing sync**(必做)— 每个 implementation slice 完成时,**必**包含该 slice 直接影响的 user-facing docs 更新;否则 slice 不可 mark `implemented`
- **Slice 4 consolidated sync**(整体)— 跨 doc 一致性 / 风格 unification / 残留 cleanup / migration note placement / 跨 ADR examples 统一

#### 4.1.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (a) per-slice immediate sync only | 每个 slice 完成立即同步 docs;无 Slice 4 consolidated | step-by-step shippable;但 cross-slice consistency 难保证(slice A 改 docs 形态可能跟 slice B 后改的形态冲突);跨 doc terminology drift 风险 | ✗ |
| (b) consolidated Slice 4 docs sync only | docs 留到 Slice 4 一次性同步;前面 slice 不动 docs | 干净;但 Slice 1-3b 完成期间 shipped docs 跟 code 不一致(user 看 docs 学旧 API 但 code 已是新 API)— violates user-visible consistency;single Slice 4 burden 大 | ✗ |
| **(c)** **hybrid — per-slice load-bearing + Slice 4 consolidated** | 每个 slice 必做该 slice 直接影响的 load-bearing docs;Slice 4 做整体一致性 + 风格 unification + 残留 cleanup | step-by-step shippable + 终态 cross-doc 一致;per-slice burden 小(仅 load-bearing 部分);Slice 4 是 polish 不是 from-scratch | ✅ |

**选 (c)**。

#### 4.1.2 "Load-bearing" 定义

某 doc change 在 slice X 是 **load-bearing** 若:
- 该 doc 描述的 API / 行为在 slice X 完成时实际被 shipped 改变
- 该 doc 不更新会让 user 看 docs 学到 wrong API / behavior
- 该 doc 在 slice X 后变成 "shape conflict"(per audit 5+1 state 分类 row D 标的 (c) shape conflict)

**Non-load-bearing** docs change(留 Slice 4):
- terminology consistency across docs(slice X 不直接 touch 的 doc 用 slice X 引入的术语)
- example unification(slice X examples 跟其他 doc examples 风格统一)
- migration note placement / cross-reference 完整性
- minor wording polish

#### 4.1.3 决策 rationale 三条

1. **user-visible consistency** — Slice 1 完成后 user 用 form I 描述符,docs 必须立即反映(不能让 docs 教旧 cardinality kwarg)— per-slice load-bearing 满足
2. **Slice 4 burden 不爆炸** — 大部分 docs change 在前面 slice 已落地;Slice 4 只做 polish + consistency check
3. **shippable per-slice** — 每个 slice 完成时 user 可立即获得 docs 跟 code 一致的体验;不需等到 Slice 4

### 4.2 Per-slice load-bearing docs sync acceptance(必做 — 每 slice blueprint Stage 4 必含)

**锁定**:每个 slice blueprint Stage 4 acceptance criteria **必含**该 slice 的 load-bearing docs sync 项目;否则该 slice 不可 mark `implemented`(per 本 ADR §7.4 no-retroactive)。

#### 4.2.1 Slice 1(Form I — ADR-FI)load-bearing docs

| Doc | Change |
|---|---|
| `sdk/docs/04_api_surface.en.md` Field/Identity descriptor section | Form I overview + `Field()` 无 cardinality kwarg + `Identity()` 无 primary_key/default/default_factory + migration guide(Old/New examples per ADR-FI §4.3) |
| `identity-mechanism-redesign.zh.md §8 Form I` | 跟 ADR-FI §4.3-bis adopted wording 对齐 |
| `docs/official/kernel/quickstart/schema.md` | Form I 类型推断 cardinality 形态;dual-layer enum/pattern validation 用法 |

#### 4.2.2 Slice 2(Identity-as-Claim — ADR-IC)load-bearing docs

| Doc | Change |
|---|---|
| `sdk/docs/04_api_surface.en.md` | INV-7c reject 行为表(`fg.fields.*` + `fg.assertions.retract` 双路径)+ existence-claim transitional guard 说明(per ADR-IC §4.4)+ Identity Claim emission 说明 + shadow store legacy 定位(per ADR-IC §4.2.3) |
| `identity-mechanism-redesign.zh.md §5.2 INV-7a/b/c + §13` | 跟 ADR-IC §4.1-§4.4 adopted wording 对齐 |
| `docs/official/kernel/quickstart/read-write.md` + `schema.md` | Identity immutable 行为 + delete+create migration pattern |
| **D11 cleanup** — `core/store/_builders.py` flag 使用点 doc | `is_entity_exists` / `is_identity_field` flag 走 ADR-IC §4.3.1 cache(comment update) |

#### 4.2.3 Slice 3a(API namespace — ADR-API + ADR-SYS-A + ADR-IE)load-bearing docs

| Doc | Change |
|---|---|
| `sdk/docs/04_api_surface.en.md` §0 Namespace Map + §2.3-§2.6 namespace tables | 三层 `fg.entities.*` / `fg.fields.*` / `fg.assertions.*` 重写;`fg.schema.register/extend/apply` 三分;`AssertionView` 统一类型(纯读)+ `AssertionsManager`(承载 retract)分离;`Field` value-oriented signature notes;G1/G2 reserved namespace guard 说明 + Layer C/E classification |
| `sdk/docs/04_api_surface.en.md` §4 types section | `FieldAssertions` / `AssertionNamespace` 删除;`AssertionView` + `AssertionsManager` 类型契约;EntityEditor section(lifecycle / commit / rollback / Identity reject / cardinality / `__getattr__` / EditorClosedError stable vs dynamic surfaces)|
| `docs/official/kernel/quickstart/assertions.md` | D5 `.version(v)` 删除 + migration note(改用 `where(_meta={"version": v})`);D6 `_meta` 统一签名(去 flat `source/trace_id/version` kwargs);D7 `fg.assertions.where(...)` 改 "shipped after Step 1" + `at(...)` 仍 NOT supported on assertions namespace |
| `docs/official/kernel/quickstart/read-write.md` + `schema.md` + `first-factgraph.md` | namespace 三层迁移示例 + `register/extend/apply` 调用 + EntityEditor 使用 |
| **D1-D3 + D5-D7 落点全在 Slice 3a** |
| **ADR-IE §4.4.2 IdentityEditor error message** | update shipped at `facade.py:470-472` 走 §4.4.2 target wording(含 INV-7a + delete+create migration hint + ADR-IC §4.1 reference;去 misleading "open new editor with different identity")|

#### 4.2.4 Slice 3b(Ledger migration — ADR-SYS-B)load-bearing docs

| Doc | Change |
|---|---|
| `sdk/docs/04_api_surface.en.md` | retract idempotency(find_revoker SQL)说明 + `_meta` claim_meta path + INV-15 read filter 行为 + `add` multiset behavior change + Slice 3b dual-coexistence limitation note |
| `ledger-schema-specification.zh.md §9` | Slice 3b 落地状态 markers(精简 1+5/3/4 partial/6/7 完成);跟 ADR-SYS-B §4.7 acceptance criteria 对齐 |
| **D10 cleanup** — `core/store/ledger.py:512-580+` deprecated public 方法 | Slice 3b 内 cleanup(per ADR-SYS-B §4.4 完全替代 claim_meta path)|

#### 4.2.5 Slice 5(Adapter rewrite — ADR-INV9)load-bearing docs(Step 2+)

| Doc | Change |
|---|---|
| `ledger-schema-specification.zh.md §9.4` | 精简 4 真正 drop rest_terms 列(Slice 5 完成)markers |
| `identity-mechanism-redesign.zh.md §11.3` | Q-PR1 解 — PyReason adapter multi-Claim Relationship lowering(per ADR-INV9 §4.4.2)实施完成 marker |
| `sdk/docs/04_api_surface.en.md` | Slice 5 后 Claim DTO 终态说明(unary;value+value_tag only;rest_terms 不存在)|

**注**:Slice 5 是 Step 2+ scope;本 ADR §4.2.5 是 forward-pointer,不进 Slice 4 consolidated。

### 4.3 Slice 4 consolidated docs sync content

**锁定**:Slice 4 docs sync blueprint Stage 4 acceptance criteria 涵盖以下整体一致性 work:

#### 4.3.1 Cross-doc terminology consistency

- **EntityEditor** / **FieldEditor** / **IdentityEditor** terminology 在所有 docs 中统一
- **AssertionView** / **AssertionsManager** 分离命名 — 所有 references 跟 ADR-API §4.2.1 一致
- **Identity Claim** / **`<EntityType>:exists` Claim** / **`__system__.revokes` Claim** namespace + emission terminology 一致
- **rest_terms / value+value_tag dual-coexistence** wording 一致(per ADR-SYS-B + ADR-INV9)
- **INV-7a** / **INV-7c** / **INV-12 part 2** / **INV-15** reference 完整性

#### 4.3.2 Migration note placement

- ADR-FI alpha breaking migration notes(`Field(cardinality=)` / `Identity(primary_key=)` 等)放 `04_api_surface.en.md` Form I section
- ADR-API `version(v)` migration note + `_meta` 统一 migration note 放 `assertions.md`
- ADR-SYS-B `add` multiset behavior change + Slice 3b dual-coexistence limitation 放 `04_api_surface.en.md` Layer 2 fields 章

#### 4.3.3 Cross-reference 完整性

- 所有 docs `04_api_surface.en.md` / `assertions.md` / `schema.md` / `read-write.md` / etc. 间的 cross-link 检查
- design-point `identity-mechanism-redesign.zh.md` + `ledger-schema-specification.zh.md` 引用 ADR-FI/IC/API/SYS-A/SYS-B/INV9/IE adopt commits 链 完整

#### 4.3.4 Examples consistency

- Examples 用统一形态(用 `User` / `User.name` / `User.tenant_id` 等 canonical 名;identity field 用 `id` / `tenant_id` 等)
- Examples 用 ADR-API 三层 namespace 形态(全 docs 不能混 `fg.read.*` 旧形态)
- Examples 跟 Slice 1-3b shipped behavior 一致

#### 4.3.5 残留 cleanup

- 删除 `fg.read.*` / `fg.write.*` / `find` 动词 / `version(v)` / flat `source=` kwargs 等所有 stale 引用(全 docs grep)
- 删除 `FieldAssertions` / `AssertionNamespace` 等已删类型的 references

### 4.4 D1-D11 row 落点分配

per §1.2 表已展示,本节系统化锁定:

| Row | Slice | 含义 |
|---|---|---|
| D1 | Slice 3a load-bearing | 04_api_surface.en.md namespace examples 重写 |
| D2 | Slice 3a load-bearing | 04_api_surface.en.md namespace tables 重写 |
| D3 | Slice 3a load-bearing | 04_api_surface.en.md FieldAssertions/AssertionNamespace 删除 + AssertionView/AssertionsManager 引入 |
| D4 | Slice 4 minor + Step 2+ during 扩展 | `.at(t)` 半开区间 valid_from/valid_to 文档;`during((t1, t2))` 留 Step 2+ |
| D5 | Slice 3a load-bearing | assertions.md `.version(v)` 删除 + migration note |
| D6 | Slice 3a load-bearing | assertions.md `_meta` 统一签名 |
| D7 | Slice 3a load-bearing(critical) | assertions.md "fg.assertions.where NOT supported" 陈述重写 |
| D8 | Step 2+(`FrozenAssertionView` → `FrozenAssertionSet` 重命名) | 不在本 ADR scope |
| D9 | Step 2+(`fg.views` → `fg.assertion_views` 重命名)| 不在本 ADR scope |
| D10 | Slice 3b cleanup(per ADR-SYS-B) | `core/store/ledger.py:512-580+` deprecated public 方法删除 |
| D11 | Slice 2 cleanup(per ADR-IC §4.3.1 cache) | `core/store/_builders.py:315-318` flag 使用点 comment update |

### 4.5 Style / structural unification at Slice 4

**锁定**:Slice 4 doc-sync blueprint 必须完成:

- **Terminology pass**:全 docs grep + verify 用统一术语(per §4.3.1 list)
- **Cross-ref pass**:全 docs cross-link verify;所有 §reference / ADR reference / Sliced naming 跟实际 anchors 对齐
- **Examples pass**:examples 风格 + canonical names + 形态全统一
- **Migration note placement pass**:per §4.3.2 锁定的 placement 检查
- **Stale reference cleanup pass**:per §4.3.5 grep + 删除残留

### 4.6 Cross-Q decision summary(单 Q,纯 lock)

| Sub-decision | Decision | Implementation surface | Slice |
|---|---|---|---|
| §4.1 strategy | hybrid (c) — per-slice load-bearing + Slice 4 consolidated | docs sync work 分散到 Slice 1/2/3a/3b 各 implementation + Slice 4 consolidated polish slice | All Step 1 slices + Slice 4 |
| §4.2 per-slice acceptance | 每个 slice blueprint Stage 4 必含 load-bearing docs sync | 每 slice blueprint Step 4.7 / §10 Outcome | All Step 1 slices |
| §4.3 Slice 4 content | cross-doc 一致性 + 风格 unification + 残留 cleanup + migration note placement + examples consistency | `workflow/blueprints/active/2026-05-29_slice-4-docs-sync.md`(起草前置 = 本 ADR + Slice 1-3b 完成)| Slice 4 |
| §4.4 D1-D11 落点 | D1-D3+D5-D7 → Slice 3a;D4 → Slice 4 minor + Step 2+;D8-D9 → Step 2+;D10 → Slice 3b;D11 → Slice 2 | per row migration | per row |
| §4.5 unification | 5 passes(terminology / cross-ref / examples / migration note placement / stale cleanup) | Slice 4 blueprint Stage 4 | Slice 4 |

**整体**:per-slice docs sync 范围(Slice 1+2+3a+3b 合计)≈ 200-400 行 docs 改动(分 4 slice 各自落地);Slice 4 consolidated polish ≈ 100-200 行(unification + cleanup + cross-ref);Slice 5 deferred docs ≈ 50-100 行(Step 2+)。

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q17 alternative — option (a) per-slice immediate sync only(无 Slice 4 consolidated)

- **Why rejected**:cross-slice consistency 难保证;Slice A 改 docs 形态可能跟 Slice B 后改的形态冲突;cross-doc terminology drift 风险(不同 slice 用不同 wording 形态);无 Slice 4 final polish 让 docs 残留不一致

#### Q17 alternative — option (b) consolidated Slice 4 docs sync only(无 per-slice)

- **Why rejected**:Slice 1-3b shipped 期间 docs 跟 code 不一致 → user 看 docs 学旧 API 但 code 已是新 API → user-visible drift;single Slice 4 burden 大(所有 docs change 集中一个 slice);不 step-by-step shippable

#### Q17 alternative — per-slice load-bearing + 每 slice 也做 consolidated(无 Slice 4 separate)

- **Why rejected**:每 slice burden 翻倍(load-bearing + consolidated);跨 slice consistency 不可能(slice A 完成时 slice B 还未实施,consistency check 跟谁 align);Slice 4 separate slice 是更干净的 polish/check 阶段

#### Per-slice acceptance alternative — load-bearing docs 是 Slice 4 责任而非 each slice 的 acceptance

- **Why rejected**:让 Slice 1-3b 各 slice 在 "docs 不同步" 状态 shipped → 违反 user-visible consistency;每 slice acceptance 含 load-bearing docs sync 是 step-by-step shippable 的必要条件

#### Slice 4 content alternative — 仅 polish 不做 cross-doc consistency / cleanup

- **Why rejected**:cross-doc consistency 是 docs sync 的核心 deliverable;polish-only Slice 4 不能 close docs cluster;stale references / cross-ref drift 留下会污染后续 ADR docs

#### Slice 4 content alternative — Slice 4 含所有 docs change(包括 load-bearing)— violates §4.1.1 (b) reject

- **Why rejected**:已 reject(per §5.1 Q17 alternative option (b))— consolidated-only 模式被否决;Slice 4 是 polish 阶段不是 from-scratch

#### D8/D9 落点 alternative — Step 1 Slice 4 内做 `FrozenAssertionView` rename / `fg.views` rename

- **Why rejected**:per audit D8/D9 标 (e) deferred-aligned(Step 2+);PDF triage C5/C6 已锁 Step 2+;Step 1 内 rename 是 scope creep;Step 2+ 独立 docs slice 处理

#### D11 落点 alternative — D11 落 Slice 4 而非 Slice 2

- **Why rejected**:D11(`is_entity_exists` / `is_identity_field` flag 使用点)是 Slice 2 ADR-IC §4.3.1 cache 实施直接相关;comment update 跟 cache 实施同 slice 落地更自然;Slice 4 polish 不应 carry per-slice load-bearing work

### 5.2 Cross-Q rejected combinations

#### Option `DOCS-defer-everything`:所有 docs sync 延后到 Step 2+

- **Why rejected**:违反 Step 1 完成 = user-facing API shipped 一致的目标;Step 1 完成后 shipped docs 跟 code 不一致是不可接受 user-visible state

#### Option `DOCS-merge-into-each-slice`:取消 Slice 4 separate;每 slice 都做该 slice 的所有 docs(load-bearing + consolidated cross-doc)

- **Why rejected**:每 slice burden 不合理;cross-doc consistency 在 Slice 4 之前不可能(后 slice 改动未实施);Slice 4 是必要的 consistency / polish 阶段

#### Option `DOCS-module-docs-included`:module docs(`src/factgraph/*/docs/`)也进本 ADR scope

- **Why rejected**:module docs update per `workflow/foundations/module_docs_convention.md` — 是各 slice implementation 内 inherent step(per `CLAUDE.md` workflow);本 ADR scope 限于 user-facing docs(SDK docs + public quickstart + design-points);module docs 维护 path 不重复锁

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q17 row(`audit:531`)
- audit §5.3 D1-D11 rows(`audit:454-464`)— 11 docs touchpoints + 5+1 state 分类 + driver Q reference

### 6.2 Shipped docs structure citations

- `src/factgraph/sdk/docs/` — 8 个 user-facing SDK docs(`00`-`07` + README)
- `docs/official/kernel/quickstart/` — 11 个 public quickstart docs
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` — §5.2/§8/§10/§11/§12 跨多个 ADR 引用 sync source
- `workflow/design/design-points/active/ledger-schema-specification.zh.md` — §4.6-§4.12 INV invariants + §9 migration 跨 ADR-SYS-B/INV9 引用 sync
- `workflow/foundations/module_docs_convention.md` — module docs convention(本 ADR §3 Non-scope:留各 slice implementation)

### 6.3 Meta-ADR + 8 cross-ADR docs sync commitments

#### 6.3.1 ADR-FI(`b288ea9e`)docs commitments
- §4.1 docs guideline source
- §4.3 Field signature change docs migration note
- §4.3-bis Identity signature change docs migration note
- §7.2 follow-up — `04_api_surface.en.md` Form I overview + migration guide;`identity-mechanism-redesign §8` 对齐

#### 6.3.2 ADR-IC(`2d0866ed`)docs commitments
- §4.1 INV-7c reject 行为表
- §4.4 existence-claim transitional guard 说明
- §7.2 follow-up — `04_api_surface.en.md` 加 INV-7c reject 表 + existence-claim guard;`identity-mechanism-redesign §5.2` 对齐

#### 6.3.3 ADR-API(`66434490`)docs commitments
- §4.3.4 Q12 migration note(`version(v)` → `where(_meta={"version": v})`)
- §4.4.1 Q13 `_meta` 统一文档化
- §7.2 follow-up — `04_api_surface.en.md` 三层 + AssertionView + `_meta` + schema 三分 + Q12 migration note;`assertions.md` 删 `version(v)` 章 + 加 migration note

#### 6.3.4 ADR-SYS-A(`75f1c8bc`)docs commitments
- §4.1 G1/G2 guard 说明
- §4.2.3 Layer C forward-looking 规约 docs
- §4.2.5 Layer E `WireBatchPlan` "schema-bound binding-validated" classification(防 reviewer 误判遗漏)
- §7.2 follow-up — `04_api_surface.en.md` 加 G1/G2 + Layer C + Layer E classification

#### 6.3.5 ADR-SYS-B(`6b0ac349`)docs commitments
- §4.4.2 SDK 影响 `_meta` claim_meta path
- §4.5.2 set/add dedup 语义 docs
- §4.6.2 INV-15 read filter 矩阵
- §4.7.3 acceptance Slice 4 docs sync 项
- §7.2 follow-up — `ledger-schema-specification §9` 时序对齐 + `04_api_surface.en.md` retract idempotency + `_meta` claim_meta + INV-15 read filter + `add` multiset behavior change + dual-coexistence limitation

#### 6.3.6 ADR-INV9(`c03e435d`)docs commitments
- §4.3.2 Slice 5 acceptance(Slice 4 docs sync 或 ADR-DOCS 范畴)
- §7.2 follow-up — `ledger-schema-specification §9.4` 对齐 + `identity-mechanism-redesign §11` 对齐 + `04_api_surface.en.md` Slice 5 后 Claim DTO 终态(Step 2+)

#### 6.3.7 ADR-IE(`9fd0ffb5`)docs commitments
- §4.4.2 IdentityEditor error message target wording(Slice 3a follow-up)
- §4.7.3 EditorClosedError error message hint 改善
- §7.2 follow-up — `04_api_surface.en.md` EntityEditor section + `identity-mechanism-redesign §12.8` 对齐

### 6.4 Design-point citations

- `identity-mechanism-redesign.zh.md` §8 / §5.2 / §12 — 多 ADR 引用 sync target
- `ledger-schema-specification.zh.md` §9 / §4.6-§4.12 — 多 ADR 引用 sync target

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:Q-PR1 / PyReason adapter / Slice 5 仅作为 **forward carve-out** 出现(§4.2.5 + §4.4 Slice 5 行 + §6.3.6 ADR-INV9 commitment)— **不是 Slice 1-4 implementation dependency**;Slice 3a / Slice 4 docs sync 可在 Slice 5 起草前完成,不会被 block。

### 6.6 Cross-ADR docs commitments closure

本 ADR §4.2 + §4.3 + §4.4 **集中关闭** 8 个 prior ADR 的 docs sync follow-up commitments — 不再有 docs sync 落点 ambiguity;Slice 4 blueprint 可基于本 ADR §4.3 起草。

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 4 docs sync blueprint**(`workflow/blueprints/active/2026-05-29_slice-4-docs-sync.md`)可起草 — §4.3 是 Stage 4 acceptance criteria outline
- **Slice 1/2/3a/3b 各 blueprint**:可在 Stage 4 §10 Outcome 加该 slice 的 load-bearing docs sync acceptance criterion(per 本 ADR §4.2 表)
- **Slice 5(Step 2+)docs**:本 ADR §4.2.5 是 forward-pointer;Slice 5 blueprint 起草时取得 docs scope
- **Stage 3 closure**:Stage 2 ADRs(9 个含 meta + 8 个 ADRs)全部 adopted;blueprint pillar 可全速启动

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 4 docs sync blueprint draft(`workflow/blueprints/active/2026-05-29_slice-4-docs-sync.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-DOCS adopt 后,Slice 3b 完成前后 |
| Slice 1/2/3a/3b 各 blueprint scoped 阶段:确认 Stage 4 §10 含本 ADR §4.2 锁定的 load-bearing docs sync acceptance | Per-slice blueprint preflight(Step 4.6.5)| 各 Slice blueprint scoped 后 |
| Slice 4 implementation:5 passes(terminology / cross-ref / examples / migration note placement / stale cleanup)per §4.5 | Slice 4 implementation | Slice 4 Step 4.7 |
| Slice 5(Step 2+)blueprint:取得 §4.2.5 docs scope(`ledger-spec §9.4` + `identity §11.3` + `04_api_surface §X` Slice 5 终态说明)| Slice 5 blueprint preflight | Step 2+ |
| Stage 3 closure pre-check:8 ADR docs commitments 全部进入 §4.2 / §4.3 / §4.4 — Audit pillar Q list 中 Q1-Q17 全部 closed | Audit / Design pillar maintainers | ADR-DOCS adopt 后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:Stage 2 ADRs 全部 adopted(9/9 含 meta);**Stage 2 全部 closed** — design constraint baseline 稳定
- **Blueprint pillar**:Slice 1 / 2 / 3a / 3b / 4 / 5 blueprints 各自起草路径已 unblocked;每 blueprint preflight 必须 re-read 相应 ADRs + 本 ADR §4.2 docs sync 项
- **Audit pillar**:audit doc §7.3 Q list Q1-Q17 全部已被 Stage 2 ADRs 锁定(实际);本 ADR 不触发 audit doc post-stage sync(跟其他 Stage 2 ADRs 相同处理)
- **Foundation pillar**:`workflow/foundations/module_docs_convention.md` 不动(per 本 ADR §3 Non-scope — module docs 留各 slice implementation per convention);未来若有 architectural 变化触发 foundation update,走独立 ADR

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,各 slice blueprint 不可单方面 override 本 ADR;若需要 override,走 "本 ADR superseded by 新 ADR-DOCS-v2" 路径
- §4.1 hybrid (c) strategy:carry-forward — 不可改回 per-slice-only / consolidated-only
- §4.2 per-slice load-bearing docs sync acceptance:**Slice 1/2/3a/3b 任一 blueprint 不可 mark `implemented` 若 load-bearing docs sync 未完成** — per blueprint pillar workflow 强制
- §4.3 Slice 4 consolidated docs sync content:carry-forward — 5 passes 不可单独跳过
- §4.4 D1-D11 落点:carry-forward — D11 必须 Slice 2;D10 必须 Slice 3b;D1-D3+D5-D7 必须 Slice 3a;D4 minor Slice 4 + Step 2+ during 扩展;D8/D9 Step 2+
- §4.5 5 passes Slice 4 unification:carry-forward — 任一 pass 缺失则 Slice 4 不可 mark `implemented`

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.5 Q17 + per-slice load-bearing + Slice 4 consolidated + D1-D11 落点 + 5 passes 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥7 项)+ cross-Q rejected combinations(≥3)
- [x] §6 含 audit / shipped docs structure / meta-ADR / 8 cross-ADR docs commitments / design-point / no-Q-PR1 confirmation / 跨 ADR docs commitments closure 7 类 evidence
- [x] §6.3 8 个 prior ADR 的 docs sync follow-up commitments 全部 enumerate
- [x] §6.6 显式 confirm 本 ADR 关闭 docs sync follow-up ambiguity(集中锁定 load-bearing + Slice 4 落点)
- [x] §1.2 D1-D11 行全部含 5+1 state + Driver ADR + 本 ADR 落点
- [x] §4.4 D1-D11 落点表 跟 §1.2 一致;无 row 遗漏 / 双重落点
- [x] Header `Depends on:` 引用 meta-ADR + 8 个 prior ADR 全部 adopted commits(cumulative)
- [x] §7.4 显式 no-retroactive carry-forward 5 项

Post-adoption verification(implementation 阶段验证 — Slice 1/2/3a/3b/4/5):

**Per-slice load-bearing docs sync verification**(§4.2):
- [ ] Slice 1 blueprint Stage 4 §10 Outcome 含 §4.2.1 docs items(`04_api_surface.en.md` Form I + `identity §8` 对齐 + `schema.md` Form I 类型推断)
- [ ] Slice 2 blueprint Stage 4 §10 Outcome 含 §4.2.2 docs items(`04_api_surface.en.md` INV-7c reject 表 + existence-claim transitional guard + Identity Claim emission + shadow store legacy 定位;`identity §5.2 + §13` 对齐;`read-write.md + schema.md` Identity immutable;D11 cleanup)
- [ ] Slice 3a blueprint Stage 4 §10 Outcome 含 §4.2.3 docs items(`04_api_surface.en.md` namespace + types + EntityEditor;`assertions.md` D5/D6/D7;`read-write.md/schema.md/first-factgraph.md` 三层迁移示例;IdentityEditor error message update per ADR-IE §4.4.2)
- [ ] Slice 3b blueprint Stage 4 §10 Outcome 含 §4.2.4 docs items(`04_api_surface.en.md` retract idempotency + `_meta` claim_meta + INV-15 + `add` multiset + dual-coexistence limitation;`ledger-spec §9` 状态 markers;D10 cleanup)
- [ ] Slice 5(Step 2+)blueprint Stage 4 §10 Outcome 含 §4.2.5 docs items(`ledger-spec §9.4` + `identity §11.3` + `04_api_surface` Claim DTO 终态)

**Slice 4 consolidated docs sync acceptance**(§4.3 + §4.5):
- [ ] Slice 4 blueprint Stage 4 acceptance criteria 含 5 passes — terminology / cross-ref / examples / migration note placement / stale cleanup
- [ ] Slice 4 implementation:terminology pass — grep verify 全 docs 用统一 EntityEditor / FieldEditor / IdentityEditor / AssertionView / AssertionsManager / Identity Claim / `:exists` Claim / `__system__.revokes` Claim / rest_terms-dual-coexistence / INV-* 等术语
- [ ] Slice 4 implementation:cross-ref pass — 全 docs cross-link verify;§ + ADR reference + Slice naming 跟 anchors 对齐
- [ ] Slice 4 implementation:examples pass — examples 用 canonical names + 三层 namespace 形态 + shipped behavior 一致
- [ ] Slice 4 implementation:migration note placement pass — ADR-FI / ADR-API / ADR-SYS-B migration notes 在 §4.3.2 锁定 placement
- [ ] Slice 4 implementation:stale reference cleanup pass — grep `fg.read.*` / `fg.write.*` / `find` 动词 / `version(v)` / flat `source=` kwargs / `FieldAssertions` / `AssertionNamespace` 等 stale references → 全 cleanup

**D1-D11 落点 verification**(§4.4):
- [ ] D1-D3 + D5-D7 in Slice 3a docs sync verified
- [ ] D4 minor in Slice 4 + Step 2+ during 扩展 carve-out verified
- [ ] D8/D9 留 Step 2+ verified(Slice 1-3b 不动)
- [ ] D10 in Slice 3b cleanup verified
- [ ] D11 in Slice 2 cleanup verified

**Stage 3 closure pre-check**:
- [ ] 8 prior ADR docs sync follow-up commitments 全部 trace 到本 ADR §4.2 / §4.3 / §4.4 — 无 docs commitment 漏点

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-DOCS drafted | Q17 docs sync timing — hybrid (c) per-slice load-bearing + Slice 4 consolidated;§4.2 锁 Slice 1/2/3a/3b/5 各 load-bearing docs items;§4.3 锁 Slice 4 consolidated 5 passes(terminology / cross-ref / examples / migration note placement / stale cleanup);§4.4 D1-D11 落点分配(D1-D3+D5-D7 → Slice 3a;D4 → Slice 4 minor + Step 2+;D8/D9 → Step 2+;D10 → Slice 3b;D11 → Slice 2);§4.5 Slice 4 unification 5 passes lock。基于 meta-ADR adopted @ `ebafdb0c` + 8 个 prior ADRs adopted commits(cumulative);8 个 ADR docs sync follow-up commitments 全部 closure。**Stage 2 收尾 ADR** — adopted 后 Stage 2 全部 closed(9/9 含 meta)。Branch: `v0.2.0-q-docs-sync-decision-2026-05-29`。Commit: TBD post-stage |
