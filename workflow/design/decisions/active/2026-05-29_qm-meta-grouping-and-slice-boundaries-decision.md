# Q-meta Decision: Stage 2 Q grouping + slice boundaries + cross-cluster separation contracts

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: meta-cadence constraint;locks Stage 2 Q-batch grouping + slice acceptance boundary granularity + cross-cluster separation contracts **before** any per-Q ADR work begins.
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3(17 Q list)+ §10(recommended slice order)
  - User reviewer 2026-05-29 P1/P2 feedback (codex-equivalent independent review on Stage 1 audit)
    - P2-1:Q5 跨 enforcement site,需 split(`__system__.*` user reservation vs internal `__system__.revokes` emission exception)
    - P2-2:Slice 3b "partial migration" acceptance boundary 需定义粒度,但不需要在本 ADR 锁技术细节(留 Q15 ADR 本体)
  - CADENCE Q-delta-decision multi-sub-issue lock pattern(Slice 7C precedent — Q6-A 锁 6 sub-issues 同 ADR)
- Outputs / Downstream:
  - Stage 2 正式 Q-batches(按本 ADR §4.2 锁定的 grouping)
  - 后续 ADR docs / branches 数 + 边界
- Related:
  - 后续 Q1-Q17(本 ADR 锁 grouping,不锁具体决策)
- Branch: `v0.2.0-qm-meta-grouping-and-slice-boundaries-decision-2026-05-29`
- Depends on: Stage 1 audit complete(`workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` Status: complete @ `aa50332d`)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Stage 1 audit deliverable

Audit `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` 在 5 commits (Phase 1 → Phase 4 + cleanup) 内 land:
- 48 finding triage(5+1 state taxonomy:a/b/c/d/e/f)
- 17 Q candidates(Q1-Q17)with skeleton ADR fields
- 5 migration clusters 识别
- §10 recommended slice order:Slice 1 Form I → Slice 2 Identity Claim emission → Slice 3a API surface + Slice 3b ledger partial migration(parallel-eligible)→ Slice 4 docs sync → Slice 5+(Step 2+)PyReason adapter rewrite

### 1.2 User reviewer P2 findings(2026-05-29 post-audit independent review)

**P2-1**:Audit §7.3 Q5 表述为单一 "`__system__.*` rejection enforcement layer" Q,但实际跨两个 enforcement site:
- user-facing pred_id reservation check(可随 API surface Slice 3a)
- internal `__system__.revokes` emission exception 路径(必须随 ledger revokes migration Slice 3b)

**P2-2**:Audit §10.1 Slice 3b "partial migration" 描述含糊:
- claims.rest_terms 保留 vs 删除?
- revoke-as-claim 在 n-ary rest_terms schema 上怎么编码?
- claim_meta 是否完全替代 meta_rows/annotation_rows 还是仅重命名?

User reviewer 要求 meta-ADR 锁 acceptance boundary **粒度**(即"Slice 3b ADR 必须回答哪几个 Q"),**不**锁具体技术答案 — 那些是 Q15 ADR 本体的工作。

### 1.3 Per-user "preserve granularity, no premature merge" guidance(2026-05-29 Phase 4)

User Phase 4 review 明确:**不急合并 Qs**。本 ADR 沿用此原则 — grouping 决策遵循"语义紧耦合 ↔ 同 ADR;否则独立"标准。

## 2. Scope

本 ADR **锁**以下 4 sub-issues:

| Sub-issue | 锁的内容 |
|---|---|
| **§4.1 Q5 split** | Q5 拆分为 Q5a / Q5b 的具体形态(user-facing vs internal exception) |
| **§4.2 Q grouping strategy** | 17 Qs → 具体 ADR docs 数 + 每个 ADR 涵盖的 Q 列表 |
| **§4.3 Slice 3b boundary granularity** | Slice 3b ADR(即 Q15 ADR)必须回答的 N 个 acceptance boundary 问题清单 |
| **§4.4 Q4 + Q-PR1 separation contract** | Step 1 INV-9 enforcement scope + PyReason adapter rewrite 时机隔离的硬约定 |

## 3. Non-scope

本 ADR **不**锁:

| 不锁 | 留给谁 |
|---|---|
| Q5a 的具体 enforcement layer 选择(application 层 SDK shell vs protocol 层 set_field)| Q5a ADR 本体 |
| Q5b 的具体 emission exception 路径设计(internal-only API vs special pred_id whitelist 等) | Q5b ADR 本体 |
| Slice 3b 各 Q 的具体技术答案(claims.rest_terms 是否保留;revoke-as-claim 编码;claim_meta 替代深度)| Q15 ADR 本体(per user reviewer P2 收紧) |
| Q4 在 Step 1 内 INV-9 "weak" enforcement 的具体实施(set_field 是否加 warning?是否记录 known-exception list?)| Q4 ADR 本体 |
| Q1-Q17 任何 Q 的具体技术决策 | 各 Q 的 ADR 本体 |
| Stage 3 synthesis 内容 + Stage 4 blueprint slice design | Stage 3 / Stage 4 |

## 4. Decision

### 4.1 Sub-issue 1 — Q5 split

**锁定**:Q5 拆分为两个独立 Q:

| 新 Q | Title | Enforcement site | Slice 归属 |
|---|---|---|---|
| **Q5a** | `__system__.*` user-facing pred_id reservation check | application 层 SDK write shell(`fg.fields.set` / `fg.fields.add` / `fg.assertions.write` 拒绝 user-supplied `pred_id` 以 `__system__.` 开头);**仅保留 namespace,不定义 `__system__.revokes` 的 payload shape / rest_terms / value+value_tag 编码方案**(后者属于 Q5b + Q15.2 工作面) | Slice 3a(API surface) |
| **Q5b** | Internal `__system__.revokes` emission exception path | ADR-SYS-B 必须决定 internal-only emission path;可能通过 `retract_by_asrt` lowering、internal writer API、或 protocol-layer exception 等机制实现。**本 meta-ADR 不锁具体机制**;留 ADR-SYS-B §4 Decision 展开 | Slice 3b(ledger revokes migration) |

**Q5a + Q5b 同 cluster**(System namespace cluster),但**独立 ADR** — 因为:
- Q5a 决策跟 SDK shell API design 紧耦合(Q-Cluster-API)
- Q5b 决策跟 ledger revokes migration 深度耦合(跟 Q15)
- 两者 acceptance criteria 不同

**Q17 cross-doc 影响**:Q5a 涉及 docs §11.5 `__system__.*` namespace rejection 文档化(Slice 4 docs sync 时同步)。

### 4.2 Sub-issue 2 — Q grouping strategy

**锁定**:**Option B Moderate Grouping** — 17 Qs(实际 18 after Q5 split)归并为 **8 个 ADR docs**(本 meta-ADR 外)。

**Grouping rationale**:语义紧耦合的 Qs 合并;独立 acceptance criteria 的保持独立。

| ADR | 涵盖 Qs | Cluster | Rationale |
|---|---|---|---|
| **ADR-FI**(Form I)| Q6 / Q7 / Q8 / Q9 | Form I cluster | 4 Qs 都改 `_DataMember` + descriptor 形态;acceptance criteria 紧耦合(`_DataMember` public exposure 决策 + cardinality 推断 + Literal 枚举 + pattern 规约 4 项必须协同) |
| **ADR-IC**(Identity-as-Claim core)| Q1 / Q2 / Q3 | Identity-as-Claim cluster | 3 Qs 形成 implementation chain:Q2(emission layer)→ Q3(pred_id set cache)→ Q1(Layer 2 boundary check);分离会让 INV-7c 实施 split-brain |
| **ADR-INV9**(Q4 — INV-9 weak enforcement)| Q4 | System namespace cluster(part)| 独立 — INV-9 enforcement scope 跟 PyReason adapter rewrite 时机绑定(per §4.4),独立 ADR 锁 Step 1 wood line |
| **ADR-SYS-A**(Q5a — user-facing reservation)| Q5a(新拆)| System namespace cluster | 独立 — Q5a 跟 ADR-API 的 namespace migration 深度耦合,但 acceptance criteria 独立(rejection check 是 protocol concern not namespace concern) |
| **ADR-SYS-B**(Q5b + Q15 — internal revokes + ledger migration)| Q5b(新拆)+ Q15 | System namespace cluster + Ledger migration cluster | **合并** — Q5b 的 internal `__system__.revokes` emission 是 Q15 ledger migration 不可分割的一部分;`__system__.revokes` 编码在 n-ary vs unary rest_terms 上的选择就是 Q15 核心议题 |
| **ADR-API**(API surface migration)| Q10 / Q11 / Q12 / Q13 / Q14 | API namespace cluster | 5 Qs 都是 API surface 重组;acceptance criteria 集中在 backward-compat strategy 和 breaking timing,同 slice + 同 ADR 高效 |
| **ADR-IE**(Q16 — `:exists` Claim removal timing)| Q16 | Identity-as-Claim cluster | 独立 — `:exists` removal 跟 Q1/Q2/Q3 的 Identity Claim emission 有时序依赖,但语义独立(Q16 是 cleanup,Q1-Q3 是 enabling),分离 ADR 让 cleanup 可独立 ship |
| **ADR-DOCS**(Q17 — docs sync timing)| Q17 | Docs cluster | 独立 — Q17 决定 docs slice 4 何时启动 + 启动时一次性 sync 还是分阶段 sync;跟具体技术决策无关 |

**总计**:1 meta-ADR(本)+ 8 normal ADRs = **9 个 Stage 2 ADR docs**。

**Alternative options 已 rejected**(详见 §5):
- Option A(aggressive 5 ADRs):合并过度,Q4/Q5 跨 cluster 混在同 ADR 会让 acceptance criteria 互相绑架
- Option C(one Q per ADR,17 ADRs):粒度过细,Q6/Q7/Q8/Q9 紧耦合的 Form I 决策分 4 doc 没必要

### 4.3 Sub-issue 3 — Slice 3b boundary granularity(per user reviewer P2-2 收紧)

**锁定**:Slice 3b ADR(ADR-SYS-B,涵盖 Q5b + Q15)**必须**回答以下 **5 个 acceptance boundary 问题**,**但本 meta-ADR 不锁具体答案**:

| Q15-sub | Acceptance boundary 问题 | 决策落在 |
|---|---|---|
| **Q15.1** | claims 表 `rest_terms` 列是否在 Slice 3b 内删除?vs 留到 Step 2+ adapter rewrite slice(per §4.4 Q4 隔离)| ADR-SYS-B §4 |
| **Q15.2** | `__system__.revokes` Claim 在当前 n-ary `rest_terms` schema 上如何编码?(临时 1-elem rest_terms 包装 vs Slice 3b 同步引入 value+value_tag 双列 + INV-9 weak enforce)| ADR-SYS-B §4 |
| **Q15.3** | `claim_meta` 跟 shipped `meta_rows` / `annotation_rows` 关系?(纯重命名;合并 annotation_rows 进 claim_meta + 加 namespace/category 字段;完全替代 + annotation_rows 删)| ADR-SYS-B §4 |
| **Q15.4** | `ingest_keys` 表在 Slice 3b 内是否删除?vs 留到 cleanup slice | ADR-SYS-B §4 |
| **Q15.5** | Slice 3b 的 Stage 4 blueprint acceptance criteria 的"完成"定义:(a)所有 Q15.1-Q15.4 落地;(b)子集落地 + 剩余明确 Step 2+ 转;(c)其他形态 | ADR-SYS-B §4 + Slice 3b blueprint |

**为什么 meta-ADR 不锁这 5 个的具体答案**(per user reviewer P2-2):
- 答案需要技术 trade-off 分析(性能 / migration 复杂度 / read path 兼容性);meta-ADR 是 cadence 决策,不应承担技术 trade-off
- meta-ADR 内嵌技术细节会膨胀成 Q15 本体的 mini-version,违反 ADR 单一职责
- 留 Q15 ADR 本体的 §4 Decision 章节进行实质决策 + §5 Rejected Alternatives 展开 trade-off

**Slice 3b blueprint 启动前置**:ADR-SYS-B 必须 adopt(Q15.1-Q15.5 全部 locked)才能起 Slice 3b blueprint。

### 4.4 Sub-issue 4 — Q4 + Q-PR1 separation contract

**锁定**:Step 1(Slice 1 + Slice 2 + Slice 3a + Slice 3b + Slice 4)**不**被 PyReason adapter rewrite(Q-PR1 / Slice 5+)阻塞。具体 separation contract:

#### 4.4.1 Step 1 INV-9 enforcement scope:**layered weak enforcement**

**关键 framing**:Step 1 unary 约束**由 SDK/application 层新入口保证**;ledger/protocol 层 strict assertion **延后到 Slice 5+**(adapter rewrite 后)。两层分工避免 ledger 层为现存 PyReason adapter n-ary 写入立即报错。

| Layer | Step 1 内 INV-9 enforcement |
|---|---|
| **SDK shell layer** — `fg.fields.set` / `fg.fields.add` / `fg.entities.create` / `fg.assertions.write` 等 Slice 3a 引入的 user-facing write paths | **必须 enforce(strict at this layer)** — 写入前 check `len(rest_terms) <= 1` 或等价 value-single 形态约束;违反时 raise `SDKStoreError` |
| **Application layer write protocol** — application 层调用 ledger 路径的中间层(若 Slice 3a/3b 引入)| **必须 enforce(strict at this layer)** — 跟 SDK shell 同步,防 internal mis-routing 写 n-ary |
| **Ledger / protocol layer** — `set_field` / `add_field` / `ledger.append_assertion` | **不 enforce strict**(Step 1)— 接受 n-ary rest_terms 不报错;Slice 5+ adapter rewrite 完成后才加 strict `assert len(rest_terms) <= 1` |
| **PyReason adapter** — `_edge_rest_terms` n-ary 输出 | **adapter-only known temporary exception** — 唯一 authorized n-ary writer 直到 Slice 5+ |

**Slice 3b 同步引入**:claims 表的 value + value_tag 双列(Q15.2 决策决定时序);schema 形态上准备好接收 unary Claim,但**不**在 protocol 层加 strict assertion。

**Step 1 内不存在 layer-conflict**:任何**新增**的 user-facing 路径(Slice 3a 引入)在 SDK shell 层强制 unary;**现存** PyReason adapter 的 n-ary 写入路径继续工作,因为 ledger/protocol 层不 strict。两层分工不冲突。

#### 4.4.2 Slice 5+(Step 2+)PyReason adapter rewrite 触发的 strict enforcement

- Q-PR1 PyReason adapter rewrite 完成(`_edge_rest_terms` 重写为 unary Relationship Claim lowering)
- 完成后:`set_field` / `add_field` 加 strict enforcement `assert len(rest_terms) <= 1`
- 同步:删除"adapter-only known exception"标记

#### 4.4.3 隔离硬约定

| 项 | Step 1 内允许 | Step 2+ 必须 |
|---|---|---|
| n-ary rest_terms 写入 | ✅ PyReason adapter only;documented exception | ✗ 删除 exception |
| INV-9 strict enforcement | ✗ weak only | ✅ strict assert |
| user-facing n-ary write paths | ✗ 禁止 | — |
| Q-PR1 adapter rewrite | ✗ Step 1 不做 | ✅ Slice 5+ 主体 |
| Step 1 任何 ADR 等 Q-PR1 | ✗ **零 ADR 等 Q-PR1**(本约定保证) | — |

**Acceptance**:任何 Step 1 ADR 的 §1 Inputs / §6 Supporting Evidence **不可**列出 Q-PR1 / Slice 5+ adapter rewrite 作为前置依赖。违反者 Stage 2 ADR review 阶段必须重写。

## 5. Rejected Alternatives

### Option (A-aggressive): 5-ADR grouping(Form I / Identity-as-Claim / API / Ledger / Docs 5 大 cluster 各一 ADR)

- **形态**:每个 cluster 一个 ADR doc;17 Qs(18 after Q5 split)合并到 5 ADRs
- **Why rejected**:
  - Q4(INV-9 enforcement)跨 System + Ledger 两 cluster,合到 Ledger ADR 会绑架 Slice 3a/3b separation
  - Q5a(API user-facing)+ Q5b(internal exception)合到 System cluster 一个 ADR 会让 Slice 3a(待 Q5a)+ Slice 3b(待 Q5b)失去独立 ship 能力
  - acceptance criteria 跨越多 Q 时同 ADR 互相绑架,违反 ADR 单一职责
  - 跟 user "preserve granularity" guidance 冲突

### Option (C-fine-grained):One Q per ADR(17 ADR docs)

- **形态**:每个 Q 独立 ADR,branch + doc 各 17 套
- **Why rejected**:
  - Q6/Q7/Q8/Q9(Form I 4 Qs)技术上**必须**协同决策(`_DataMember` public exposure 影响 cardinality 推断的 Backward-compat 选项,后者又影响 Literal 枚举的 enforcement layer 选择)— 拆 4 ADR 会反复跨 ADR 协调
  - Q1/Q2/Q3 同理 — Identity Claim emission layer 决策(Q2)直接决定 Q3 cache 的 init/lazy 策略,然后影响 Q1 boundary check 的 invocation 路径
  - 17 ADR 的 process overhead 高(17 branches + 17 review cycles + 17 closure)远超 cadence cost
  - 跟 user "preserve granularity" 不矛盾 — granularity 指"不强制合并独立 Qs",**不**要求 4-Q-coupled 决策也拆

### Option (B-prime):同 Option B grouping 但 Q5a + Q5b 合 ADR-SYS

- **形态**:8 ADRs,但 Q5a + Q5b 合成 ADR-SYS(单一 system namespace ADR)
- **Why rejected**:
  - Q5b 跟 Q15 的耦合度(ledger revokes encoding)**远高于** Q5b 跟 Q5a 的耦合(后者只是同 namespace prefix)
  - 合 Q5a + Q5b 会让 ADR-SYS 跨 Slice 3a + Slice 3b,违反"一 ADR 一 slice"原则
  - Q5b + Q15 同 ADR 让 Slice 3b blueprint 启动门槛清晰(单 ADR 锁全部 Q15.1-Q15.5)

### Option (3-tech-detail):meta-ADR 在 Sub-issue 3 锁 Slice 3b 技术细节

- **形态**:本 ADR §4.3 直接锁 claims.rest_terms 保留 / 删除 / revoke 编码等
- **Why rejected**(per user reviewer P2-2):
  - 锁技术细节让本 meta-ADR 膨胀成 Q15 mini-version,违反 ADR 单一职责
  - 技术 trade-off(性能 / migration 复杂度 / read path)需要专题分析,不应该在 cadence 决策 ADR 内承担
  - 留 Q15 ADR 本体的 §4 + §5 充分展开是 cleaner separation

### Option (4-no-separation):Step 1 INV-9 strict 同步 + 同 slice rewrite PyReason adapter

- **形态**:Slice 3b 同步落 INV-9 strict + 同 slice rewrite PyReason adapter(无 Slice 5+ 独立)
- **Why rejected**(per user critical guidance):
  - 让 Step 1 被 PyReason adapter rewrite 阻塞 — adapter rewrite 是 multi-week 的复杂工作,会让整个 Step 1 拖延
  - PyReason adapter rewrite 涉及 PyReason native model → ledger Claim 的 lowering 路径设计,跟 Step 1 identity-as-claim 实质无关
  - 用 §4.4 weak enforcement + adapter-only exception 是 well-defined 妥协,既保护 Step 1 进度又锁定 Step 2+ strict 目标

## 6. Supporting Evidence

### 6.1 Stage 1 audit citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 17 Q list(`:466-518`)
- audit §10 recommended slice order(`:580-660`)
- audit §10.3 sequencing rationale 中 "Slice 5+ separated:严格阻止 Step 1 被 adapter rewrite 阻塞"(`:650`)
- audit §8 Reviewer focus item 2:"Q4 vs Q-PR1 cluster 分离 — Step 1 不能被 adapter rewrite 阻塞"
- audit §5.1 I-series row INV-9(`:170`):`set_field` 接受 multi-arg rest_terms 是 current shipped pre-migration baseline,标 (f) target-gap
- audit §5.4 N1:INV-3 single SQLite transaction verified — Slice 3b ledger migration 有 atomicity baseline confidence

### 6.2 Shipped code citations

- `src/factgraph/core/store/ledger.py:82-88` claims 表 shipped DDL(无 value/value_tag 列,rest_terms 多 arg list)
- `src/factgraph/core/evidence/write_protocol.py:128-156` `set_field` 多 arg 接受
- `src/factgraph/adapters/pyreason/accept.py:187-205` `_edge_rest_terms` 2-elem 返回(唯一 n-ary writer)
- `src/factgraph/core/evidence/write_protocol.py:170-208` `retract_by_asrt`(internal-only 调用 ledger.append_revocation 写 Revokes 表,而非 `__system__.revokes` Claim)

### 6.3 User reviewer P2 feedback citations

- User 2026-05-29 codex-equivalent independent review post-audit:
  - P2-1:Q5 split 必要性
  - P2-2:Slice 3b boundary granularity 收紧(meta-ADR 不锁技术细节)

### 6.4 CADENCE precedent

- Slice 7C Q6-A 6-sub-issue lock pattern(CADENCE.md "Q-delta-decision multi-sub-issue lock pattern"段):多 sub-issue 同 ADR 是 validated pattern;本 meta-ADR 4 sub-issue 在同 ADR 锁是合规

## 7. Consequences

### 7.1 Downstream unblocking

本 meta-ADR adopted 后,以下 unblocked:
- Stage 2 进入正式 ADR-by-ADR 阶段 — 按 §4.2 grouping 起 8 个 normal ADRs
- ADR-FI(Form I)可立即起草 — Slice 1 是 foundational,无前置 ADR 依赖
- ADR-API / ADR-SYS-A / ADR-IC 可同步起草(三者无 Q dependency)
- ADR-SYS-B / ADR-IE / ADR-DOCS 需要等其他 ADR 部分 lock 后起草(per dependency graph)

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Audit doc §7.3 Q list 更新 — Q5 split 为 Q5a + Q5b;增 18th Q row | Claude(audit doc maintainer)| meta-ADR adopt 后立即 |
| 8 个 ADR docs 起草顺序与 dependency graph 确认 | User + Claude(Stage 2 启动 review)| meta-ADR adopt 后启动 Stage 2 之前 |
| Slice 3b blueprint **不可**在 ADR-SYS-B adopt 前启动 | Stage 4 blueprint draft 时 enforce | Slice 3b blueprint 起草时 |
| Step 1 任何 ADR §1 Inputs / §6 不可列 Q-PR1 作为依赖 | Stage 2 ADR review 时 enforce | 每个 Step 1 ADR review 时 |
| PyReason adapter `_edge_rest_terms` 添加 "adapter-only known temporary exception until Step 2+" 注释 | 待 Slice 3b adopt 后 — 由 Slice 3b blueprint 执行 | Slice 3b blueprint |
| Q-PR1 ADR(若 Step 2+ 启动时还没 adopted)在本 meta-ADR 引用本 §4.4 separation contract | Step 2+ Q-PR1 ADR 起草时 | Step 2+ |

### 7.3 Cross-pillar interaction

- **Design pillar**:本 meta-ADR adopted 后,17 Qs(18 after split)的 ADR docs 分别独立 lifecycle,跟本 ADR 关系是"depends on"(在各 ADR Header 的 `Depends on:` 字段引用)
- **Audit pillar**:audit doc §7.3 Q list 必须 sync update(Q5 split)— 但 audit Status 仍 `complete`(本 meta-ADR 是 Stage 2 work,不回头改 Stage 1 audit triage,只更新 Q list table row)
- **Blueprint pillar**:Slice 3b blueprint 启动门槛 = ADR-SYS-B adopted(§7.2 已记录);其他 slices 跟其对应 ADR 1-to-1
- **Memory pillar**:本 meta-ADR adopt 是 milestone — `workflow/memory/current.md` 在 Stage 2 全部 closed 时 batch update(per CADENCE "Never auto-update memory mid-session" rule);本 ADR commit **不**触发 memory update

### 7.4 No-retroactive boundary

- 本 meta-ADR 锁的 4 sub-issues 在 adopted 后是 **下游 ADR 的硬前置**;下游 ADR 不可 override(若需要,走"本 ADR superseded by 新 meta-ADR"路径,不可在 normal ADR 单方面改)
- §4.4 Q4 + Q-PR1 separation contract 是 Step 1 implementation-wide 约束,任何 Step 1 blueprint(Slice 1-4)+ 任何 Step 1 ADR 受其约束
- §4.3 Slice 3b boundary granularity 的 Q15.1-Q15.5 清单是 ADR-SYS-B §4 Decision 必须覆盖的 minimum coverage,**不**限制 ADR-SYS-B 加额外 sub-decisions(只是不允许遗漏这 5 个)

## 8. Acceptance Criteria

本 ADR adopted 时:

- [x] §4.1 Q5 → Q5a + Q5b split 表清晰描述
- [x] §4.2 8 个 ADR docs grouping table 完整(每行有 涵盖 Qs / Cluster / Rationale)
- [x] §4.3 Slice 3b 5 个 Q15.1-Q15.5 acceptance boundary 问题列出,且明确不锁具体答案
- [x] §4.4 Q4 + Q-PR1 separation contract 含 weak/strict enforcement + adapter-only exception + Step 1 zero-blocker hard rule
- [x] §5 至少 4 个 Rejected alternatives 含 Option A / Option C / Option B-prime / Option 3-tech-detail / Option 4-no-separation(实际 5 个)
- [x] §6 audit + shipped code + CADENCE precedent + user reviewer feedback citations 完整

post-adoption verification:

- [ ] audit doc §7.3 Q list table 更新(Q5 split 落地)— PR/commit
- [ ] 后续 8 个 ADR docs 的 Header `Depends on:` 字段引用本 ADR(Stage 2 启动时 check)
- [ ] 每个 Step 1 ADR 的 §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / Slice 5+ — Stage 2 ADR review checklist 加该条
- [ ] Slice 3b blueprint 启动前 ADR-SYS-B Status: adopted 验证 — Slice 3b blueprint Step 4.1 前置 check

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | Meta-ADR drafted | Sub-issues 1-4 锁定;基于 audit Status: complete @ `aa50332d` + user reviewer P2 findings;Q grouping = Option B Moderate(8 ADRs);Slice 3b boundary granularity 不锁技术细节(留 Q15 ADR);Q4 + Q-PR1 separation contract Step 1 zero-blocker hard rule |
