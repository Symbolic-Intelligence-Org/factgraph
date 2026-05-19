# Audit: `database-view-fg-layered-architecture.zh.md` Design vs Shipped Runtime

- Status: skeleton (rows empty, ready for per-commitment fill-in)
- Created: 2026-05-20
- Branch: `v0.1-db-view-audit-2026-05-20` (off Phase B baseline `93f18701`)
- Design doc: `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md` (766 lines, self-declared "non-authoritative reference; not current implementation truth")
- Authority of this audit: working triage document; informs but does not lock implementation. Implementation decisions follow only after user reviews completed audit rows.

## 1. Scope

**First-round audit**: full A1-A20 commitments + I1-I13 invariants triage, with implementation-depth split between primary shipped audit and secondary dependency-only enumeration.

Per user scope discovery 2026-05-20: section-subset framing (`§3-§7 + §10`) was rejected because it would miss shipped equivalents in `§8 SubsetView`, `§9 FactGraph runtime`, `§11 API`, `§12 view=`, `§15 existing v1 subset view`. A1-A20 commitments triage is the more reliable organizing principle since it pins on binding statements rather than section boundaries.

### Primary shipped-code audit surface

Files read completely (not grep snippets) as the audit ground truth:

| Layer | File | Path |
|---|---|---|
| core store | ledger | [src/factgraph/core/store/ledger.py](../../src/factgraph/core/store/ledger.py) |
| core store | runtime / Store facade | [src/factgraph/core/store/runtime.py](../../src/factgraph/core/store/runtime.py) |
| core schema | schema_ir + canonicalization + digest | [src/factgraph/core/schema/schema_ir.py](../../src/factgraph/core/schema/schema_ir.py) |
| core view | view projector | [src/factgraph/core/view/projector.py](../../src/factgraph/core/view/projector.py) |
| core protocol | digests / sha256 helpers | [src/factgraph/core/protocol/digests.py](../../src/factgraph/core/protocol/digests.py) |
| core protocol | idref_v1 | [src/factgraph/core/protocol/idref_v1.py](../../src/factgraph/core/protocol/idref_v1.py) |
| core protocol | tup_v1 | [src/factgraph/core/protocol/tup_v1.py](../../src/factgraph/core/protocol/tup_v1.py) |
| application | workspace runtime | [src/factgraph/application/workspace_runtime.py](../../src/factgraph/application/workspace_runtime.py) |
| application | entity view | [src/factgraph/application/entity_view.py](../../src/factgraph/application/entity_view.py) |
| application | query runtime | [src/factgraph/application/query_runtime.py](../../src/factgraph/application/query_runtime.py) |
| application | AssertionRecordDTO | [src/factgraph/application/protocol/entity_read.py](../../src/factgraph/application/protocol/entity_read.py) |
| SDK | SDKStore / views / read / evaluate / save / load | [src/factgraph/sdk/store.py](../../src/factgraph/sdk/store.py) |
| SDK | facade DTOs (AssertionRecord SDK shape) | [src/factgraph/sdk/facade.py](../../src/factgraph/sdk/facade.py) |
| SDK | query runtime adapter | [src/factgraph/sdk/query_runtime.py](../../src/factgraph/sdk/query_runtime.py) |

### Secondary / dependency-only surface

Enumerated, NOT deeply audited in this round:

- `§14 Evidence / Evaluate metadata 接缝` — only seam-level enumeration. Evidence service v1 itself is out of scope (separate doc, separate audit if needed).
- `§19 与 rule-expression-and-proof-attempt.zh.md 接缝` — only listed as dependency. Rule / RuleExpr / Head / eval API audit is a separate prerequisite if the user wants to expand scope later.
- `evidence-tree-rainbird-style-v1.zh.md` — not audited.
- `rule-expression-and-proof-attempt.zh.md` — not audited.

## 2. Methodology

### 2.1 Per-row classification

For each commitment / invariant row:

1. Quote design statement verbatim (or close paraphrase with line ref to design doc).
2. List shipped equivalent(s) with `file:line` precision; if none, state explicitly (see §2.2).
3. Classify gap:
   - **(a) shipped covers** — implementation matches commitment;no work needed
   - **(b) small gap** — shipped close but missing specific detail;targeted patch viable
   - **(c) shape conflict** — shipped has equivalent but with different shape/name/encoding; doc revision OR shipped revision needed before implementation; cannot just "implement" the doc statement
   - **(d) genuinely new** — no shipped equivalent + commitment is concrete and implementable
   - **(e) deferred-aligned** — commitment explicitly defers something; verify shipped doesn't accidentally implement it
4. Risk: low / medium / high (re-implementation cost, blast radius, cross-cut impact).
5. Recommendation: skip / targeted patch / doc revision / implement / defer further.

No code is changed during this audit. Audit output is doc-only.

### 2.2 Provenance protocol (信源协议)

This protocol is a guardrail against audit drift; it is not optional. It is the operationalization of `feedback_preflight_code_audit_required` for this specific audit.

**Rules**:

1. **Every shipped equivalent citation MUST include `file:line` precision.** Bare module names (e.g., "in `ledger.py`"), unqualified function references, or "I think shipped has X" are not acceptable. Each cell of §3 / §4 / §5 either has a `file:line` reference or an explicit "no shipped equivalent found".

2. **The cited file MUST have been read completely (line 1 to EOF) before any row referencing it is filled.** Grep-only verification is insufficient. The shared reference for "what each file actually contains" lives in §7; rows in §3 / §4 / §5 may cite back to §7 entries, but §7 itself is built from full reads.

3. **Uncertainty MUST be recorded as `unknown` or `no shipped equivalent found`, never guessed.** If a commitment talks about behavior that could plausibly be in multiple shipped places but unverified, mark `unknown` and add to §8 Open Questions. Guessing produced two Phase C failures already.

4. **`docs/references/working/design-points/` content is design INPUT under audit, NOT current truth.** When the design doc and shipped code disagree, shipped wins for descriptive claims (what IS) and the disagreement is recorded as a classification (b)/(c). The design doc only binds prescriptively (what SHOULD BE) and even then is "non-authoritative reference" per its own header.

5. **Files added to the primary audit surface during reading MUST be justified.** §1 lists 14 primary files. If reading surfaces additional shipped files load-bearing for some commitment, add them to §7 with a one-line "why included" note. The count is not load-bearing; the justification is.

6. **No commitment row can be filled before its supporting §7 inventory entry exists.** Phase 1 (build §7) must complete before Phase 2 (I-series) starts. Within Phase 2/3/4, individual rows may still surface new shipped files (per rule 5); when they do, append §7 entry first, then fill the triage row.

**Why this exists**: Phase C 2026-05-19 / 2026-05-20 failure root cause was reasoning from design doc + memory + grep snippets without verifying shipped reality. `fact_tuple` was proposed as new when shipped had `e_ref + rest_terms`. `canonical_json` was duplicated 4 times. `canonical_meta` shipped with bytes encoding that conflicts with shipped `_to_jsonable`. None of these would have survived a strict provenance protocol applied at design time.

## 3. I-series Invariants Triage (I1-I13)

| # | Doc invariant | Shipped state (file:line) | Gap | Risk | Recommendation |
|---|---|---|---|---|---|
| I1 | `Database` 是唯一持久写入点 |  |  |  |  |
| I2 | `DatabaseValue` immutable;由稳定 `db_id` + content-addressed `tx_id` 唯一定位 |  |  |  |  |
| I3 | `SubsetView`/`FrozenAssertionView` immutable;由 `db_id + base_tx_id + asrt_ids + schema_digest` 派生 `view_digest` |  |  |  |  |
| I4 | `FactGraph.attach(db)` attach 当前 head,默认 writable |  |  |  |  |
| I5 | `FactGraph.attach(db.as_of(tx_id))` attach snapshot,read-only |  |  |  |  |
| I6 | `FactGraph.attach(db, view=view)` attach view scope,read-only |  |  |  |  |
| I7 | `view=` 指定时,read/evaluate/explain 只能看见 `view.asrt_ids` 内 assertions |  |  |  |  |
| I8 | `view=` 省略时,read/evaluate/explain 使用 attached snapshot 的 full assertion universe |  |  |  |  |
| I9 | scoped runtime 不 silent fallback 到 full universe |  |  |  |  |
| I10 | evidence / evaluate metadata 必须记录 `db_id` / `tx_id` / `schema_digest` / optional `view_digest` |  |  |  |  |
| I11 | `db_id` 是 database identity,持久存储;`tx_id` 是 transaction content identity,跨进程可复现 |  |  |  |  |
| I12 | `FactGraph.attach(...)` 签名不包含 `rules=`;rules 不进 Database transaction、不进 workspace v1 |  |  |  |  |
| I13 | Workspace 物理布局:`db/objects/` + `db/refs/` + `db/assertions.db`;views 同模式 |  |  |  |  |

## 4. A-series Commitments Triage (A1-A20)

| # | Doc commitment | Shipped equivalent (file:line) | Classification | Risk | Recommendation |
|---|---|---|---|---|---|
| A1 | 最小架构只引入 `Database` / `DatabaseValue` / `SubsetView` / `FactGraph runtime` 四个核心概念 |  |  |  |  |
| A2 | `Database` 是唯一持久写入点;最小版本只 append assertions |  |  |  |  |
| A3 | `DatabaseValue` immutable,由稳定 `db_id` + content-addressed `tx_id` 定位;`tx_id` 不得由 UUID / 自增序号充当 durable identity |  |  |  |  |
| A4 | `SubsetView`/`FrozenAssertionView` 是 subset scope,不是 version / branch / working copy |  |  |  |  |
| A5 | `FrozenAssertionView` 必带 `db_id / base_tx_id / schema_digest / view_digest` |  |  |  |  |
| A6 | attach 到 `DatabaseValue` 或 `FrozenAssertionView` 的 runtime 第一版 read-only |  |  |  |  |
| A7 | `view=` 省略时使用 full assertion universe;指定时只看 `view.asrt_ids` |  |  |  |  |
| A8 | runtime-attached view 与 method-level view 冲突时 raise,不做 nesting |  |  |  |  |
| A9 | stale / mismatch 必须显式报错,禁止 fallback 到 full universe |  |  |  |  |
| A10 | EvaluateResult / EvidenceGraph metadata 必须记录 db snapshot + optional view context |  |  |  |  |
| A11 | branch / writable sub-fg / remote / multi-db / Rule persistence 全部 deferred |  |  |  |  |
| A12 | `db_id` 由 `Database.create` 生成并持久化;`Database.open(path)` 必须读回同一 `db_id`;in-memory default db 使用非 durable `mem:<uuid4>` |  |  |  |  |
| A13 | `AssertionRecord` 最小 shape 锁定为 `asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta`;`asrt_id` content-addressed |  |  |  |  |
| A14 | attach-to-view / attach-to-snapshot 与 read-only enforcement 必须同 ship;禁止 scoped runtime 可写 |  |  |  |  |
| A15 | rules 不进 workspace、不进 Database transaction;`FactGraph.attach(...)` 签名不含 `rules=`;`rule_set_digest` 在 evaluate 时计算 |  |  |  |  |
| A16 | schema 分两层:authoring source 属于用户代码;compiled snapshot 由 Database 持久化为 `db/objects/schema/<schema_digest>.json` content-addressed |  |  |  |  |
| A17 | Database 物理布局 Git-style:`db/objects/` content-addressed write-once + `db/refs/head.txt` 唯一 mutable + `db/assertions.db` SQLite index |  |  |  |  |
| A18 | SubsetView 物理布局:`views/objects/<view_digest>.json` content-addressed;named view registry deferred to v2 |  |  |  |  |
| A19 | `factgraph_workspace.json` 收缩为最小 manifest:`{workspace_version, components.{db, views}, created_at, last_saved_at}` |  |  |  |  |
| A20 | 现 `registry/` 全部不迁移:rules/inferences/manifest/events 移除;`registry/schema/schema_ir.json` 迁到 `db/objects/schema/<schema_digest>.json` |  |  |  |  |

## 5. D-series Deferred Items — Confirmation Shipped Doesn't Accidentally Implement (D1-D10)

Per design doc §17. Audit each: does shipped have anything resembling this that should be flagged?

| # | Deferred item | Shipped accidental implementation? (file:line if any) | Confirm deferred? |
|---|---|---|---|
| D1 | persistent named views in Database |  |  |
| D2 | branch / tag / refs |  |  |
| D3 | writable sub-fg |  |  |
| D4 | assertion retract / update |  |  |
| D5 | schema migration tx |  |  |
| D6 | materialized derived views |  |  |
| D7 | remote database |  |  |
| D8 | multi-db join |  |  |
| D9 | Rule persistence / SavedRule |  |  |
| D10 | view set algebra API |  |  |

## 6. Cross-doc Seams (§19) — Dependency-Only Enumeration

Listed for awareness; **not audited** in this round.

| # | Seam item | Main doc owner | Notes |
|---|---|---|---|
| S1 | `fg.eval.evaluate(..., view=...)` from reject → supported | `rule-expression-and-proof-attempt.zh.md` |  |
| S2 | `fg.read.find(..., view=...)` from reject → supported | `rule-expression-and-proof-attempt.zh.md` |  |
| S3 | EvaluateResult context adds `db_id/tx_id/schema_digest/data_digest/view_digest` | `rule-expression-and-proof-attempt.zh.md` |  |
| S4 | EvidenceGraph.metadata durable copy of S3 fields | `evidence-tree-rainbird-style-v1.zh.md` |  |
| S5 | failure envelope stale / out-of-scope evidence ref → §13 | `evidence-tree-rainbird-style-v1.zh.md` |  |
| S6 | `rule_set_digest` evaluate-time computation, attach API unchanged | `rule-expression-and-proof-attempt.zh.md` |  |

## 7. Shipped Code Surface Inventory (populated during audit)

Brief summary of what each primary audit file actually exports + key shapes. Populated as audit proceeds; serves as shared reference for triage rows in §3 + §4.

### 7.1 `core/store/ledger.py`
*(to populate)*

### 7.2 `core/store/runtime.py`
*(to populate)*

### 7.3 `core/schema/schema_ir.py`
*(to populate)*

### 7.4 `core/view/projector.py`
*(to populate)*

### 7.5 `core/protocol/digests.py + idref_v1.py + tup_v1.py`
*(to populate)*

### 7.6 `application/workspace_runtime.py`
*(to populate)*

### 7.7 `application/entity_view.py + query_runtime.py + protocol/entity_read.py`
*(to populate)*

### 7.8 `sdk/store.py` — views / read / evaluate / save / load
*(to populate)*

### 7.9 `sdk/facade.py + sdk/query_runtime.py`
*(to populate)*

## 8. Open Questions for User

*(populated during audit when ambiguity surfaces)*

## 9. Next-step Recommendations

*(populated at end of audit; categorizes A1-A20 by post-audit action)*

### 9.1 Skip — shipped already covers
*(empty)*

### 9.2 Targeted patch — small gap
*(empty)*

### 9.3 Doc revision needed — shape conflict
*(empty)*

### 9.4 Implementable — genuinely new
*(empty)*

### 9.5 Defer further — risk too high or context missing
*(empty)*
