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

### Supplemental shipped-code audit surface

Added during Phase 1 inventory because primary files cite these helpers directly. These files were also read completely before use.

| Layer | File | Why included |
|---|---|---|
| core store | [src/factgraph/core/store/_support.py](../../src/factgraph/core/store/_support.py) | `project_view_facts_with_witness(...)` returns `ProjectedFact`; support/provenance digest shapes affect evidence/evaluate seam wording |
| core policy | [src/factgraph/core/policy/active.py](../../src/factgraph/core/policy/active.py) | `project_view_facts(...)` and read hydration use `is_active(...)`; active universe depends on revocation state |
| core write protocol | [src/factgraph/core/evidence/write_protocol.py](../../src/factgraph/core/evidence/write_protocol.py) | SDK write/retract path delegates here; required for D4 and append-only/retraction triage |

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
| I1 | `Database` 是唯一持久写入点 | No `Database` class shipped. **Primary / current high-level persistent write boundary is `Ledger`**: assertion / revocation high-level writes route through `Ledger.append_assertion / append_revocation` (§7.5 `ledger.py:363 / :453`); `write_protocol.set_field / retract_by_asrt / replace_field` (§7.17 `write_protocol.py:128 / :170 / :211`) all route through these. SDK `fg.set / add / retract` via `_apply_field_mutation` → `apply_write_plan` → `set_field` → ledger (§7.12 `sdk/store.py:1782-1839 / :1886-1909`). **However `Ledger` is NOT a single `commit_assertions` boundary** — it also exposes (i) **low-level / deprecated write methods** kept for compatibility: `append_claim`, `append_claim_args`, `append_meta`, `append_revokes` (§7.5 `ledger.py:512 / :531 / :553 / :598`, all 4 marked deprecated in docstrings); (ii) `append_annotations` (§7.5 `ledger.py:576`) for annotation-only writes; (iii) `set_ledger_meta / replace_ledger_meta` (§7.5 `ledger.py:780 / :788`) for lifecycle metadata writes that bypass the assertion path. SQL writer is `sqlite3.Connection.execute(...)` invoked from any of these methods (DDL at §7.5 `ledger.py:81-159`). | **(c) shape conflict** — shipped `Ledger` is the primary high-level write boundary at the SQL layer, but no `Database` class concept exists. Approximation is incomplete: (i) `Ledger` lacks `db_id` / `tx_id` / `commit_assertions(...)` API; (ii) `Ledger` exposes **multiple high-level + low-level write methods** rather than a single `commit_assertions(...)` boundary; (iii) deprecated paths (`append_claim*`, `append_meta`, `append_revokes`) coexist with the current `append_assertion / append_revocation` boundary;(iv) lifecycle-meta writes (`set_ledger_meta` / `replace_ledger_meta`) sit outside the assertion model entirely. | medium-high | doc revision needed before any implementation: decide whether `Database` is (a) a new layer above shipped `Ledger`, (b) **doc revision maps the `Database` concept to the existing `Ledger` boundary** (not a code rename), or (c) a design term dropped in favor of `Ledger`. Implementation cost depends entirely on this choice. See §8 Q1. |
| I2 | `DatabaseValue` immutable;由稳定 `db_id` + content-addressed `tx_id` 唯一定位 | No `DatabaseValue` class shipped. `ledger_meta` (§7.5 `ledger.py:118-121`) is a **generic key/value table** — its DDL constrains only `(key PRIMARY KEY, value TEXT NOT NULL)` and does not enforce or reserve any specific keys at the SQL layer. A grep over the shipped code surface surfaces **no `db_id` / `tx_id` concept anywhere**. Current shipped lifecycle uses `SDKStore` to write+verify `schema_digest` into `ledger_meta`: `_from_schema_classes_impl` writes / checks on construction (`sdk/store.py:920-925`), `_preflight_schema_digest_anchors` checks pre-mutation (`sdk/store.py:2588-2607`), `_update_schema_digest_anchors` writes post-mutation (`sdk/store.py:2610-2623`). `_compute_ingest_key` (§7.17 `write_protocol.py:318`) is sha256-based via `canonical_bytes_tup_v1` but serves **idempotency dedup**, not snapshot identity. | **(d) genuinely new** — `DatabaseValue` DTO + `db_id` identity + `tx_id` identity all absent. Foundational primitives DO exist (`sha256_token` §7.1, `canonical_bytes_tup_v1` §7.3) so a `tx_id` formula could be built on top — but no shipped equivalent today. | high | defer until shipped uuid-based `asrt_id` model (§7.5 `ledger.py:1066` `_new_asrt_id`, §7.17 `write_protocol.py:120-121` `new_assertion_id`) is reconciled with content-addressed identity proposal. Implementation touches storage identity model, not just a new DTO. See §8 Q3. |
| I3 | `SubsetView`/`FrozenAssertionView` immutable;由 `db_id + base_tx_id + asrt_ids + schema_digest` 派生 `view_digest` | `FrozenAssertionView` **shipped at §7.12 `sdk/store.py:88-92`** with only 2 fields: `(name: str, asrt_ids: frozenset[str])`. Stored in `_SDKViewsManager._views` dict (`sdk/store.py:101-179`); **explicitly NOT persisted to workspace** (`sdk/store.py:132` comment). No `db_id`, no `base_tx_id`, no `schema_digest`, no `view_digest` field. No view_digest derivation formula shipped. | **(c) shape conflict** — same name `FrozenAssertionView` collides between shipped (2 fields) and design (6 fields). 4 of 6 design anchor fields (`db_id` / `base_tx_id` / `schema_digest` / `view_digest`) are missing. The design's 4 missing anchors presuppose I2's identity model which is itself **(d)** genuinely new. | medium-high | doc revision needed: (a) reuse shipped 2-field shape + drop anchor fields from design, or (b) rename design's view (e.g., `AnchoredAssertionView`) to avoid name collision, or (c) breaking migration of shipped 2-field shape to 6-field shape (would invalidate existing `fg.views.create/update/get/list` API contracts). Decision blocked on I2. See §8 Q4. |
| I4 | `FactGraph.attach(db)` attach 当前 head,默认 writable | **No `FactGraph.attach(db)` method shipped.** `FactGraph = SDKStore` literal alias (§7.12 `sdk/store.py:3432`). Constructors only: `SDKStore.create(...)` (`sdk/store.py:783`), `SDKStore.from_schema_classes(...)` (`sdk/store.py:837`), `SDKStore.load(...)` (`sdk/store.py:860`). No "attach" lifecycle method exists. `Ledger(path)` constructor at §7.5 `ledger.py:255` opens / creates SQLite. `Store(schema_ir, ledger, ...)` constructor at §7.6 `runtime.py:67`. Default-writable: shipped is **writable by absence of read-only mechanism**, not by attach semantics — no shipped read-only mode exists anywhere in `Ledger` / `Store` / `SDKStore`. | **(c) shape conflict** on the API surface — `attach()` lifecycle method is genuinely absent. The closest shipped API `SDKStore.load(path, schema_classes)` approximates "bind a runtime to existing storage" but: (i) named `load` not `attach`, (ii) requires `schema_classes` argument, (iii) has no "current head" semantics (depends on I2 `tx_id` which is **(d)**). The "default writable" subclause is satisfied **trivially by the absence of a read-only enforcement mechanism**, not by attach semantics — design's intent that attach decides writability cannot be evaluated against shipped because shipped has no writability decision point. Per user caution: constructor ≠ attach. | medium | doc revision needed: clarify whether `attach(db)` is a (a) **new lifecycle method distinct from constructors**, or (b) **rename of `SDKStore.load(...)`**. Until I2's `db_id` / `tx_id` model lands, "attach the current head" semantics have no foundation. See §8 Q2. |
| I5 | `FactGraph.attach(db.as_of(tx_id))` attach snapshot,read-only | **No `as_of(tx_id)` method shipped** (depends on `tx_id` per I2, which is **(d)**). **No `attach(...)` method shipped** (per I4, which is **(c)**). **No "read-only attachment" lifecycle** anywhere in shipped runtime. Closest adjacencies: (i) application read layer **rejects** `at_time_ns` / `version` request params at execute time with `TEMPORAL_READ_NOT_IMPLEMENTED` / `VERSIONED_READ_NOT_IMPLEMENTED` (§7.9 `entity_view.py:524-537`); (ii) SDK has per-assertion `.at(t)` / `.version(v)` filters on `FieldAssertions` and `AssertionRecordSet` (§7.13 `facade.py:_is_assertion_visible_at` / `_read_assertion_version`) — but these filter **per-row via `meta.raw["valid_from"]` / `meta.raw["valid_to"]` / `meta.raw["version"]`**, NOT via a db-snapshot read-only scope. | **(d) genuinely new** at db level — `as_of(tx_id)` + `attach(...)` lifecycle + db-snapshot read-only enforcement infrastructure all absent. SDK per-assertion temporal/version filter is a different feature (per-row meta-based) and cannot be treated as a shipped equivalent for db-snapshot read. | high | defer — blocked on I2 (`db_id` / `tx_id` model) + I4 (`attach()` lifecycle decision) + new read-only enforcement infrastructure. No foundation to implement as designed until I2 + I4 resolved. |
| I6 | `FactGraph.attach(db, view=view)` attach view scope,read-only | **No `FactGraph.attach(...)` method shipped** (per I4). **No `view=` scope filtering shipped** at any layer: `fg.read.find(..., view=...)` rejected (§7.12 `sdk/store.py:1049-1050`); `fg.run(..., view=...)` rejected (`sdk/store.py:1923-1924`); `fg.eval.evaluate(..., view=...)` rejected (`sdk/store.py:2241-2244`). `_SDKViewsManager` (§7.12 `sdk/store.py:101-179`) holds named `FrozenAssertionView(name, asrt_ids)` entries (per I3 (c) shape conflict) but they are **not consumed by any read/eval path** — they exist as standalone named asrt_id sets. No read-only enforcement mechanism shipped (per I4). | **(d) genuinely new** — depends on I3 (view shape) + I4 (attach lifecycle) + I5 (read-only enforcement). All 3 dependencies are unresolved ((c)/(d)). The view-with-attach lifecycle requires the entire stack from I3 + I4 + I5 to land first. | high | defer — blocked on I3 + I4 + I5 + Q1 + Q2 + Q4. No implementable foundation today. |
| I7 | `view=` 指定时,read/evaluate/explain 只能看见 `view.asrt_ids` 内 assertions | `view=` argument rejected at 3 SDK boundaries (see I6 cites). No view-asrt_ids-restricted universe filter shipped at any layer. **Closest adjacent mechanism**: shipped read/evaluate paths use `project_view_facts(ledger, schema_ir)` (§7.7 `core/view/projector.py:117-125`) which filters claims via `is_active(ledger, claim.asrt_id)` (§7.16 `core/policy/active.py:6-11`). This is a **revocation-aware active universe**, NOT a view.asrt_ids-restricted universe — different selection criterion, different purpose. | **(d) genuinely new** — the "view= scope filter on read/eval/explain" mechanism is absent at every layer. Shipped `is_active` filter is structurally adjacent (both are universe selectors over ledger claims) but semantically orthogonal (revocation policy vs caller-specified asrt_id subset). Implementing I7 introduces a NEW filter layer that must compose with existing `is_active` filter — see Q5 for the composition question. | high | defer — blocked on I3 (view shape) + I6 (attach with view) + Q4 (view shape resolution) + Q5 (view ↔ is_active composition). Cannot land before Q4 + Q5 are answered. |
| I8 | `view=` 省略时,read/evaluate/explain 使用 attached snapshot 的 full assertion universe | Shipped has **no `view=` mechanism**, so "view= omitted" is the universal case (always). Read/evaluate routes through `project_view_facts(ledger, schema_ir)` → `is_active`-filtered claims (§7.7 `core/view/projector.py:117-125`, §7.16 `core/policy/active.py`). No "attached snapshot" concept (per I2 (d)). **"Full assertion universe" semantic is underspecified by design**: shipped's no-view path uses **revocation-active universe** (excludes revoked); design's "full assertion universe" could mean (a) revocation-active = matches shipped, or (b) all-asrt-in-snapshot including revoked = unspecified. | **(e) deferred-aligned** on the routing portion: shipped has no `view=` mechanism, so the "view= omitted → no view filter" intent is trivially satisfied by absence. **(c) shape conflict** on the universe-definition portion: shipped uses revocation-active universe; design's "full universe" is underspecified w.r.t. revocation. The conflict is latent — it only surfaces if Q5 resolution makes "full universe" semantically distinct from "active universe". | low-medium | confirm "full universe" definition during Q5 resolution. If design intends revocation-active (= matches shipped) then I8 routing+definition are both (a). If design intends all-asrt-in-snapshot then I8 universe-definition becomes a new mechanism. |
| I9 | scoped runtime 不 silent fallback 到 full universe | **No scoped runtime exists** in shipped (per I6 (d)). No `view=` scope filter exists (per I7). Therefore **no opportunity for silent fallback** to occur today. The invariant is a behavioral guarantee for **future** scoped runtime that doesn't yet exist. | **(e) deferred-aligned** — vacuously satisfied today by absence of scoped runtime. When I6 lands, this becomes a non-trivial acceptance criterion: scoped runtime must raise `StaleViewError` / `ViewScopeError` / similar rather than degrading to full-universe read. Today there is no scoped-runtime code path that could fall back. | low (today) / depends on I6 implementation choice (future) | confirm in I6 / I7 acceptance gate when implementing scoped runtime. No standalone action today; design intent preserved as future behavioral lock. |
| I10 | evidence / evaluate metadata 必须记录 `db_id` / `tx_id` / `schema_digest` / optional `view_digest` | **The 4 required fields map to shipped state as follows.** `db_id`: not shipped (per I2 (d) — no concept anywhere). `tx_id`: not shipped (per I2 (d) — no concept anywhere). `schema_digest`: **shipped at multiple anchor points BUT NOT at the evaluate-result / evidence-graph level**: (i) `ledger.ledger_meta` table (§7.5 `ledger.py:118-121`) via `SDKStore._from_schema_classes_impl` (`sdk/store.py:920-925`) + `_preflight_schema_digest_anchors` (`sdk/store.py:2588-2607`) + `_update_schema_digest_anchors` (`sdk/store.py:2610-2623`); (ii) workspace manifest `factgraph_workspace.json` (§7.8 `workspace_runtime.py:46-65`); (iii) `FileAuthoringRegistry` schema entry (referenced from `sdk/store.py:_preflight_schema_digest_anchors`); (iv) per-assertion `meta_rows` as key when caller passes it (§7.17 `write_protocol.py:41-56` `_SENSITIVE_SEMANTIC_META_KEYS` includes `schema_digest`; `_KEY_KIND_MAP` line 83 maps it to `"str"` kind). `view_digest`: not shipped (per I3 (c) — `FrozenAssertionView(name, asrt_ids)` has no `view_digest` field/derivation). **Evidence/evaluate-result metadata shapes shipped today**: `Store.evaluate(...)` returns `list[CandidateSet]` (§7.6 `runtime.py:254-284`) — `CandidateSet` shape lives in `core/derivation/candidates` which is secondary surface per §1, not deeply mapped here. `SupportArtifact` (§7.15 `_support.py:97-126`) has fields `kind / root_result_kind / binding_items / pred_witnesses / non_fact_steps / rule_refs / rule_ref_edges` + 2 digests (`support_digest`, `provenance_digest` — `_support.py:311-312` / `:347-348`). `ProvenanceEnvelope` (§7.15 `_support.py:147-162`) has `candidate_id / engine / payload_type / payload`. **None of `SupportArtifact` / `ProvenanceEnvelope` / `CandidateSet` carries `db_id` / `tx_id` / `schema_digest` / `view_digest` at the evaluate-result or evidence-graph level.** | **(d) genuinely new** for 3 of 4 fields (`db_id`, `tx_id`, `view_digest`) — no shipped concept anywhere. **(c) shape conflict** for `schema_digest` portion — exists at 4 shipped anchors (ledger_meta + workspace manifest + registry + per-assertion meta) but NOT at the evaluate-result / evidence-graph location design specifies. **Cross-doc contract context**: the evidence service blueprint has been **deleted (Phase C rollback)** and is **pending fresh redraft** based on current Rule design. The **consumer side of the I10 metadata contract is itself undefined** today: `SupportArtifact` / `ProvenanceEnvelope` / `CandidateSet` are shipped as-is with no metadata fields for `db_id` / `tx_id` / `view_digest`; the evidence service that would extend these shapes to carry I10 metadata is not currently designed. DB/view runtime cannot unilaterally implement I10 — it is a cross-doc metadata contract requiring both sides (DB/view metadata source + evidence service metadata consumer) to agree on field placement, contents, and semantics. | high (cross-doc dependency + blocked on deleted evidence service blueprint redraft + dependency on I2/I3/Q1-Q5) | defer entirely — **I10 is NOT a DB/view runtime issue that can be independently fixed**. Implementation cannot start until: (1) evidence service is redrafted (pending fresh Rule design survey per project state) to define metadata consumer shape, AND (2) Q1-Q5 are resolved to provide `db_id` / `tx_id` / `view_digest` sources. Both prerequisites are unresolved. Note: existing `schema_digest` already lives at 4 anchors (cross-cutting finding #6); design adding a 5th at evaluate-result level should be revisited during evidence service redraft (unify storage vs add another anchor). Additional questions about metadata placement (per-result vs per-graph vs per-assertion vs unified) will emerge during evidence service redraft;they are not actionable today. |
| I11 | `db_id` 是 database identity,持久存储;`tx_id` 是 transaction content identity,跨进程可复现 | Two specific behavioral assertions, verified separately (not a restatement of I2). **(A) `db_id` durable storage**: no `db_id` concept shipped (per I2). The **structurally adjacent storage mechanism** is `ledger.ledger_meta` table (§7.5 `ledger.py:118-121`, generic `(key TEXT PK, value TEXT NOT NULL)`) which currently stores `schema_digest` and similar lifecycle entries via `SDKStore` (§7.12 `sdk/store.py:920-925` + `:2588-2607` + `:2610-2623`). **`ledger_meta` is a generic k/v adjacency, not a db_id repository** — no shipped code writes anything resembling `db_id` to it. **(B) `tx_id` cross-process content-addressed reproducibility**: no `tx_id` concept shipped (per I2). However, the **primitives for cross-process content-addressed identity DO exist**: `sha256_token` (§7.1 `digests.py:11`), `canonical_bytes_tup_v1` (§7.3 `tup_v1.py:156-168`), `canonical_bytes_idref_v1` (§7.2 `idref_v1.py:26-64`). Shipped uses these in `_compute_ingest_key` (§7.17 `write_protocol.py:318-370`) to produce a cross-process reproducible `"sha256:<hex>"` token — but for **ingest idempotency dedup, not transaction identity** (per Q3 semantic mismatch). `asrt_id` is uuid-based (§7.5 `ledger.py:1066`, §7.17 `write_protocol.py:120-121`), **explicitly NOT cross-process reproducible**. | **(d) genuinely new** for both (A) and (B). I11 is **not a restatement of I2** — it adds two specific behavioral assertions: (A) durability + storage location;(B) cross-process reproducibility guarantee. (A) has a storage-shape adjacency in `ledger_meta` but no `db_id` usage today; (B) has all primitive adjacencies (sha256_token + tup_v1 + idref_v1) but no `tx_id` formula. Adjacencies are **informational, not partial implementations**. | high (cross-process identity contract is fundamental to view_digest immutability and to I10 cross-doc metadata seam) | defer — blocked on Q1 (`db_id` placement) + Q3 (`tx_id` formula). Shipped adjacencies should NOT be counted as partial implementations during Phase 4 recommendations. |
| I12 | `FactGraph.attach(...)` 签名不包含 `rules=`;rule set 通过 `Expr / Inference` 内部引用承载,evaluate 时计算 `rule_set_digest`;rules 不进 Database transaction、不进 workspace v1 | Five sub-assertions, verified separately. **(A) attach signature has no `rules=`**: `FactGraph.attach(...)` does not exist (per I4 (c)). No shipped function has `rules=` in any constructor parameter list — verified by §7.12 reading of `SDKStore.__init__` (`sdk/store.py:722-733`) / `create` (`:783-833`) / `from_schema_classes` (`:837-857`) / `load` (`:860-895`). Vacuously aligned by absence of `attach()`. **(B) rule set carried via `Expr / Inference` internal references**: SDK has `Rule` / `Inference` objects (§7.12 referenced via `_compile_rule_input` / `_compile_derivation_input`). Dependency mechanism shipped: `_register_rule_dependencies` (§7.12 `sdk/store.py:2421-2451`) iterates `rule.dependency_rules()` and registers them into a `RuleRegistry` (imported from `core.rules.rule_ir`); `_resolve_runtime_registry` (`:2453-2468`) builds the registry from object dependencies. Detailed Rule / RuleRef shape lives in `rule-expression-and-proof-attempt.zh.md` — **secondary surface per §1, not audited in this round**. **(C) evaluate-time `rule_set_digest` computation**: **grep `src/factgraph/` for `rule_set_digest` returns 0 matches** (verified during Batch 3 prep). No shipped code computes or stores `rule_set_digest`. `_KEY_KIND_MAP` (§7.17 `write_protocol.py:57-91`) and `_SENSITIVE_SEMANTIC_META_KEYS` (§7.17 `write_protocol.py:41-56`) include `schema_digest` and `policy_digest` but NOT `rule_set_digest`. **(D) rules not in Database transaction**: shipped rules are persisted via `FileAuthoringRegistry` (§7.12 `sdk/store.py:save_rule:2092` / `load_rule:2105` / `list_rules:2113` / `get_rule:2120`), which calls `app_save_rule / app_load_rule` from `application.authoring_runtime`. Rules are NOT written via `Ledger.append_assertion / append_revocation / append_*` — verified by reading §7.5 `Ledger` API. **(E) rules not in workspace v1**: **shipped default violates the design strict prohibition**. Design A15 states "rules 是 code artifact, v1 不进 workspace" — this is a **strict claim**, not "optional decoupling". Shipped state: `_resolve_workspace_constructor_paths` (§7.12 `sdk/store.py:667-695`) auto-derives `registry_root = workspace_path / "registry/"` when `path=` is set without explicit `registry_root=` (lines 678-679 + 692-693). `save_workspace` (§7.8 `workspace_runtime.py:160-177`) calls `sync_registry_to_workspace` which **copies rules into `<workspace>/registry/`** by default. Per §7.12 `sdk/store.py:2063-2090` `save()` rebinds `_authoring_registry = FileAuthoringRegistry(paths.registry)` after save, treating the in-workspace registry as the authoritative rule store after persistence. The `registry_root=` parameter provides a **workaround for individual callers** (point registry elsewhere) but **does NOT satisfy the design constraint** at the default-behavior level — the design says rules are NOT in workspace AT ALL, not "rules optionally not in workspace via explicit caller action". | Split classification by sub-assertion. **(A) (e) deferred-aligned vacuously** — depends on I4. **(B) (a) shipped covers in spirit** — RuleRegistry + `dependency_rules()` mechanism carries rule references through SDK Rule/Inference objects;exact-shape comparison vs design wording requires rule-expression doc audit (secondary surface, not in this round). **(C) (d) genuinely new** — `rule_set_digest` literally absent from shipped (grep-verified). **(D) (a) shipped covers** — rules path goes to FileAuthoringRegistry, never to Ledger; rules-not-in-ledger is a behavioral fact shipped today. **(E) (c) shape conflict** — shipped default behavior **violates the design boundary** stated in A15 (strict prohibition: "rules 是 code artifact, v1 不进 workspace"). The `registry_root=` capability is a per-caller workaround, NOT compliance with the design constraint. "Capability exists for callers" does not satisfy a design that says "rules MUST NOT be in workspace". | medium-high — **(E) re-classified** from "default-behavior decision" to "shipped-default-violates-design-boundary" requiring migration; (C) is new but constrained to evidence/evaluate seam (deferred via I10) | split: **(A)** confirm in I4 / Q2 acceptance gate. **(B)** confirm against rule-expression doc when that doc is audited (out of scope this round). **(C)** defer — `rule_set_digest` is a new metadata field whose placement is part of evidence service redraft (cross-cuts I10). **(D)** accept as **(a)** — shipped aligned. **(E)** **design constraint is established (A15 strict prohibition); audit-side question is now migration strategy, not whether to prohibit**. See revised §8 Q6. |
| I13 | Workspace 物理布局:`db/objects/` content-addressed write-once + `db/refs/` 唯一 mutable pointers + `db/assertions.db` SQLite index layer;views 同模式 | **Current shipped workspace layout** (per §7.8 `workspace_runtime.py:15-19` constants + `:27-32` `WorkspacePaths` + `:160-177` `save_workspace` + §7.12 `sdk/store.py:667-695` `_resolve_workspace_constructor_paths`): top-level `<workspace>/factgraph_workspace.json` (6-field manifest: `factgraph_workspace_version="1"`, `save_scope="level_4"`, `schema_digest`, `components`, `created_at`, `last_saved_at`) + `<workspace>/ledger.db` (SQLite primary storage) + `<workspace>/registry/` (FileAuthoringRegistry: rules + inferences + schema). **No `db/` subdirectory** anywhere in shipped layout. **No `objects/` content-addressed write-once** subdirectory. **No `refs/` mutable pointers** subdirectory. **`ledger.db` is the primary source-of-truth**, not a rebuildable index layer — there is no `tx/` log from which `ledger.db` could be reconstructed because no transaction object directory exists. **Views layout**: `FrozenAssertionView` (§7.12 `sdk/store.py:88-92`) is **in-memory only**, stored in `_SDKViewsManager._views` dict (`sdk/store.py:101-179`); explicit code comment at `sdk/store.py:132` documents views "not included in `fg.save(...)` workspace persistence". **No views directory in shipped workspace**. | **(c) shape conflict** for workspace top-level layout — fundamentally different organization (`db/` Git-style content-addressed vs current `ledger.db` + `registry/` flat). **(d) genuinely new** for `db/objects/` content-addressed write-once + `db/refs/` mutable pointers — semantics absent in shipped. **(d) genuinely new** for `db/assertions.db` as rebuildable index layer — shipped `ledger.db` is primary source not derivable from any object log. **(d) genuinely new** for views persistence — shipped views are in-memory dict only, with explicit "not persisted" code comment. | high (entire physical layout reorganization;cross-cuts save/load contract;needs migration story for existing workspaces) | defer — blocked on Q1 (Database class boundary determines if `db/` subdirectory exists at all), Q3 (`tx_id` formula determines what goes in `db/objects/tx/<tx_id>.json`), Q4 (view shape determines if/how `views/objects/<view_digest>.json` is keyed). Migration path from current `level_4` layout to Git-style layout is a separate design phase, not part of this audit. **Per audit guardrail, NOT citing rolled-back DB.1 implementation as evidence** — DB.1 attempted this layout, was abandoned in Phase C rollback (2026-05-20), is not in the audit branch's worktree, and would not be evidence for shipped state regardless. |

**I1-I5 cross-cutting observation** (informational, not a triage decision):

I1-I5 are not 5 independent invariants — they form a coherent "missing Database / Snapshot / Attach layer" stack. I1 introduces the `Database` class concept; I2 introduces `DatabaseValue` immutable snapshot identified by `db_id + tx_id`; I3 anchors `FrozenAssertionView` to `db_id + base_tx_id + schema_digest + view_digest` (3 of 4 anchors flow from I1+I2); I4 introduces `attach()` lifecycle that binds runtime to `Database`; I5 introduces `as_of(tx_id)` snapshot read on top of I2+I4. Of the 5 rows: **2 are (d) genuinely new** (I2, I5) and **3 are (c) shape conflict** (I1, I3, I4). Implementation order is forced: I2 must land before I3 / I5; I4 must land before I5 / I6.

**I6-I9 cross-cutting observation** (informational, not a triage decision):

I6-I9 form the "view scope behavior" sub-stack on top of I3-I5's "Database / Snapshot / Attach" stack. I6 = attach-with-view lifecycle; I7 = view filter semantics on read/eval/explain; I8 = absent-view full-universe routing; I9 = no-silent-fallback acceptance guarantee. Of the 4 rows: **2 are (d) genuinely new** (I6, I7) and **2 are (e) deferred-aligned** (I8, I9 — vacuously satisfied today because the scoped runtime substrate doesn't exist). I9 is specifically a future acceptance gate, not an implementable invariant; it can only be exercised after I6 lands. The shipped adjacency `is_active(ledger, asrt_id)` (§7.16) is the closest universe-selector mechanism but it has different semantics (revocation-aware) than design's view.asrt_ids filter; the composition between the two is unspecified in design (see Q5). The pattern across I3-I9 is consistent: shipped has neither the substrate (Database / DatabaseValue / Attach) nor the surface (view= filter) for the design's view-scoped runtime model.

**I10 cross-cutting observation** (informational, not a triage decision):

I10 was deliberately split into its own batch (2b, separate from I6-I9 in batch 2a) because it is a **cross-doc seam**, not a view-scope behavior. The contract spans two sources: DB/view runtime (producer of `db_id` / `tx_id` / `schema_digest` / `view_digest`) and evidence/evaluate service (consumer of these fields as result-level metadata). DB/view runtime cannot resolve I10 unilaterally: the **consumer side is itself undefined** today — the evidence service blueprint was deleted during Phase C rollback (2026-05-20) and is pending fresh redraft based on current Rule design. The 4 shipped evaluate-result / evidence-graph shapes (`CandidateSet`, `SupportArtifact`, `ProvenanceEnvelope`, plus per-assertion `meta_rows`) carry none of the 4 design-required fields at the evaluate-result level; `schema_digest` is the only one shipped, but at 4 other anchors (ledger_meta + workspace manifest + registry + per-assertion meta), not at the evaluate-result location. I10 is the audit-row that most clearly demonstrates the I-series limitation: design specifies a multi-party contract whose other party (evidence service) is currently not represented by any binding artifact in the repository. Until the evidence service is redrafted with explicit metadata-consumer shape, I10 cannot move past **(c)/(d)** classification regardless of how Q1-Q5 are resolved.

**I11-I13 cross-cutting observation** (informational, not a triage decision):

I11-I13 are not concept-level claims (those were I1-I10) but **specific behavioral / placement / physical layout assertions**. Pattern across the three rows: shipped frequently has **adjacent mechanisms or partial alignment** that are NOT partial implementations: `ledger_meta` for I11 (storage shape exists, no `db_id` usage); `sha256_token` + `canonical_bytes_tup_v1` + `_compute_ingest_key` for I11 (cross-process sha256 primitives exist, no `tx_id` formula); `FileAuthoringRegistry` for I12 (D) (rules persistence path exists and is decoupled from ledger). **I12 (E) is special**: shipped `_resolve_workspace_constructor_paths` default behavior **violates** design A15's strict prohibition ("rules 是 code artifact, v1 不进 workspace") by auto-coupling registry to workspace; the `registry_root=` parameter is a per-caller workaround, NOT compliance with the design constraint at the default-behavior level. I12 is the most heterogeneous row in Phase 2 — its 5 sub-assertions span: (A) (e), (B) (a), (C) (d), (D) (a), (E) (c) [tightened from previous (c)+(a) framing per audit revision 2026-05-20 after user-identified design strictness]. I13 is the row most clearly affected by the abandoned Phase C work — but per audit guardrail, **rolled-back implementation work is NOT cited as shipped evidence**; only the current Phase B baseline + master state counts.

## 4. A-series Commitments Triage (A1-A20)

| # | Doc commitment | Shipped equivalent (file:line) | Classification | Risk | Recommendation |
|---|---|---|---|---|---|
| A1 | 最小架构只引入 `Database` / `DatabaseValue` / `SubsetView` / `FactGraph runtime` 四个核心概念 | A1 is a **design-side scope claim** ("design introduces only these 4 concepts at the public conceptual surface"), not a behavioral assertion about shipped. Verification: design doc §3 / §5-§9 indeed restricts itself to these 4 concepts at the conceptual layer (cross-doc seams §14 / §19 acknowledge evidence and rule docs separately). Mapping to shipped: **`Database` → no class, role played by `Ledger`** (per I1 (c)); **`DatabaseValue` → no equivalent** (per I2 (d)); **`SubsetView`/`FrozenAssertionView` → `FrozenAssertionView` shipped at §7.12 `sdk/store.py:88-92` with 2 fields** (per I3 (c)); **`FactGraph runtime` → `FactGraph = SDKStore`** alias at §7.12 `sdk/store.py:3432` (per I4 (c)). Shipped also exposes many **implementation-layer concepts** not in the 4-concept list (`Store`, `Claim`, `ClaimArg`, `MetaRow`, `AnnotationRow`, `Revokes`, `Idempotency`, `RuleRegistry`, `FileAuthoringRegistry`, `_SDKViewsManager`, `SupportArtifact`, `ProvenanceEnvelope`, `ProjectorAudit`, ...) — but these are below the public conceptual surface. | **(c) shape conflict** on the 4-concept mapping (all 4 mismatch per I1-I4); the scope claim itself is satisfied at the public-surface level — design does NOT introduce additional public concepts beyond the 4. Implementation will require the implementation-layer concepts shipped today to remain (Claim, ClaimArg, etc.), which is consistent with A1's "minimum public surface" intent. | low (A1 itself is informational); each of the 4 concepts carries individual risk per I1-I4 | confirm during Q1 + Q2 + Q4 resolution that the 4 public concepts remain stable post-resolution; do NOT treat A1 as requiring implementation surgery — the per-concept work is in I1-I4 + A2-A5. |
| A2 | `Database` 是唯一持久写入点;最小版本只 append assertions | Two sub-assertions, verified separately. **(A) `Database` sole-writer**: mirrors I1 — Ledger is primary high-level write boundary but exposes multiple write methods (high-level `append_assertion / append_revocation`, low-level deprecated `append_claim / append_claim_args / append_meta / append_revokes`, lifecycle-meta `set_ledger_meta / replace_ledger_meta`, annotation-only `append_annotations`); not a single `commit_assertions(...)` boundary. **(B) "minimum version only append assertions"**: **shipped already exposes retract**. `retract_by_asrt` (§7.17 `write_protocol.py:170-208`) appends a revocation row via `Ledger.append_revocation` (§7.5 `ledger.py:453`); `replace_field` (§7.17 `write_protocol.py:211-228`) = retract-old + append-new. SDK `fg.retract(asrt_id, meta)` (§7.12 `sdk/store.py:1886-1909`) routes to `retract_by_asrt`. At SQL level revocation IS append (new `revokes` row added), but at API level it is a distinct **retraction operation** with its own entry point. | Split classification. **(A) (c) shape conflict** via I1. **(B) ambiguous**: depends on whether design's "只 append assertions" is (i) **strict at API level** (no retract method; only `commit_assertions`-equivalent) — then shipped exceeds minimum scope; or (ii) **loose at SQL level** (any append-only write including revocation rows) — then shipped aligns. Design doesn't disambiguate. | medium | clarify A2 (B) intent: (i) strict means shipped's `retract_by_asrt` / `replace_field` exceed "minimum version" and the question becomes whether to remove them when implementing `Database` (likely undesirable — they are shipped SDK contract); (ii) loose means shipped aligns with A2 (B) as-is. Folds into Q1 (Database class boundary): the boundary decision implicitly defines what's "in the minimum version". |
| A3 | `DatabaseValue` immutable,由稳定 `db_id` + content-addressed `tx_id` 定位;`tx_id` 不得由 UUID / 自增序号充当 durable identity | Mirrors I2 + adds **explicit `tx_id` prohibition**: must NOT be UUID, must NOT be auto-increment. Shipped state: no `DatabaseValue` (per I2 (d)); no `db_id` (per I2 (d)); no `tx_id` (per I2 (d)). **Shipped's anti-pattern uses are present**: `asrt_id` uses `uuid.uuid4().hex` (§7.5 `ledger.py:1066` + §7.17 `write_protocol.py:120-121` — both call sites); SQLite `claims` table uses `seq INTEGER PRIMARY KEY AUTOINCREMENT` (§7.5 `ledger.py:81-88`, line 83). The prohibition explicitly rules out these two patterns as `tx_id` templates. | **(d) genuinely new** mirroring I2 + adds **explicit no-shortcut prohibition**. The prohibition strengthens Q3 framing: shipped's UUID-based `asrt_id` is NOT a candidate `tx_id` template (already excluded by Q3 (a)/(b) framing per Batch 1 fix). Shipped's AUTOINCREMENT `seq` is similarly excluded. | high (cross-process identity contract per I2 + I11) | defer — blocked on Q3 (`tx_id` formula). Reinforces Q3 resolution: both options (a) primitives-only with domain separation and (b) separate `tx_v1` protocol satisfy A3 prohibition; UUID/auto-increment shortcuts are off the table by design. |
| A4 | `SubsetView`/`FrozenAssertionView` 是 subset scope,不是 version / branch / working copy | Negative claim — view is NOT version / branch / working-copy. Shipped state: `FrozenAssertionView(name, asrt_ids)` (§7.12 `sdk/store.py:88-92`) is a named assertion-id subset stored in `_SDKViewsManager._views` dict (§7.12 `sdk/store.py:101-179`). **Shipped has no version-control semantics anywhere**: no merge / parent-ref / clone / fork. **Shipped has no write semantics on views**: `_SDKViewsManager.create/update/delete/get/list` operate on the asrt_id set itself (per `sdk/store.py:121-179`); the view is not a write target. Per design `§17` deferred list, `branch / tag / refs` and `writable sub-fg` are explicitly future-deferred, consistent with A4's negative claim. | **(a) shipped covers** — semantically aligned: shipped views are subset scope, NOT version/branch/working-copy. Important caveat: this alignment is partly **trivial-by-absence** (shipped has no version/branch concept anywhere to confuse with). If design later introduces branch/version (per §17 deferred), shipped's view would need to remain explicitly differentiated; today no conflict exists. | low | confirm in Q4 (FrozenAssertionView shape resolution) that whichever shape is chosen (2-field reuse / 6-field new / breaking migration) preserves A4's "not version/branch/working-copy" semantic. Independent of the field-count decision in Q4. |
| A5 | `FrozenAssertionView` 必带 `db_id / base_tx_id / schema_digest / view_digest` | Direct specification of the 4 anchor fields. Mirrors I3 exactly. Shipped state: `FrozenAssertionView(name, asrt_ids: frozenset[str])` (§7.12 `sdk/store.py:88-92`) has **only 2 fields**; **all 4 design-required anchors are absent**: no `db_id` (depends on I2 (d)), no `base_tx_id` (depends on I2 (d)), no `schema_digest` (shipped at 4 other anchors per cross-cutting finding #6 but NOT on `FrozenAssertionView`), no `view_digest` (no derivation formula shipped, per cross-cutting finding #7). `_SDKViewsManager` stores entries by `name` only in an in-memory dict (`sdk/store.py:101-179`); no anchor-field validation exists. | **(c) shape conflict** mirroring I3. The conflict is concrete: design requires 4 specific anchor fields; shipped has 0 of 4 on the view. 3 of 4 anchor sources (`db_id`, `base_tx_id`, `view_digest`) depend on I2 (d); 1 of 4 (`schema_digest`) exists at 4 other anchor points but not on the view. | medium-high | doc revision via Q4. Per Q4 resolution: (a) reuse 2-field shape requires design doc revision to drop the 4-anchor requirement;(b) rename design's shape allows shipped 2-field to coexist;(c) breaking migration requires implementing the 4-field shape (blocked on I2). A5 cannot stand independent of Q4 — its 4 required fields ARE the Q4 (c) shape. |
| A6 | attach 到 `DatabaseValue` 或 `FrozenAssertionView` 的 runtime 第一版 read-only | Two attach-targets with **different dependency chains**, verified separately. **(A) attach to `DatabaseValue` read-only**: depends on I5 (which itself depends on I2 + I4). Shipped state: no `DatabaseValue` (per I2 (d)); no `attach()` method (per I4 (c)); no read-only enforcement (per I4 — "writable by absence of read-only mechanism"). Note A6 (A) is broader than I5: I5 was specifically `attach(db.as_of(tx_id))`; A6 (A) covers attaching ANY `DatabaseValue` (head or snapshot). **(B) attach to `FrozenAssertionView` read-only**: depends on **I3 (view shape, (c))** + **I6 (attach-with-view, (d))** + **I4 (attach lifecycle, (c))**. Shipped `FrozenAssertionView` (§7.12 `sdk/store.py:88-92`) exists as a 2-field in-memory dict entry, but is **never attached to a runtime** — `_SDKViewsManager` (`sdk/store.py:101-179`) holds entries by name only; no shipped code path consumes them at attach time. | **(d) genuinely new** on both sub-assertions, **with distinct dependency chains**: (A) depends on I2 + I4 + I5; (B) depends on I3 + I4 + I6. The two sub-assertions are NOT a single missing point — they require different design resolutions. (A) needs DatabaseValue + Database identity (Q1 + Q3) + attach lifecycle (Q2); (B) ALSO needs view shape (Q4). | high (both;cross-cuts multiple I-rows) | defer — split blocking conditions: (A) blocked on Q1 + Q2 + Q3; (B) blocked on Q1 + Q2 + Q3 + Q4. Implementation cannot start either sub-assertion until its specific dependency chain is resolved. |
| A7 | `view=` 省略时使用 full assertion universe;指定时只看 `view.asrt_ids` | Direct commitment-level restatement of I7 + I8 combined. Shipped state: `view=` rejected at 3 SDK boundaries (`sdk/store.py:1049-1050 / :1923-1924 / :2241-2244`); no view= scope filter at any layer; "view= omitted" is the universal case (always) because no view= mechanism exists; routing trivially aligned. **Universe definition for "view= omitted" case**: shipped uses **revocation-active universe** via `project_view_facts` → `is_active` filter (§7.7 `core/view/projector.py:117-125` + §7.16 `core/policy/active.py:6-11`). Design's "full assertion universe" is underspecified w.r.t. revocation — see Q5. | Mirrors I7 + I8 combined. **(d) genuinely new** on "view= specified → view.asrt_ids filter" portion (the view scope filter mechanism is absent). **(e) deferred-aligned** on "view= omitted → no view filter" routing portion (trivially satisfied by absence of view= mechanism). **(c) latent shape conflict** on "full assertion universe" definition portion (active-only vs all-asrt-in-snapshot ambiguity — only surfaces post-Q5). | high (3-part split) | defer — blocked on Q4 (view shape) + Q5 (view ↔ is_active composition + "full universe" definition). A7 cannot be implemented independent of Q5 resolution because the universe-definition decision determines what "full assertion universe" means concretely. |
| A8 | runtime-attached view 与 method-level view 冲突时 raise,不做 nesting | **Verified absence** of dual-layer mechanism. Shipped has NEITHER runtime-attached view NOR method-level view scope: `grep src/factgraph` for `attach` lifecycle and `attached.view / method.*view / attached_view` returns 0 matches (verified Batch 2 prep). No `FactGraph.attach(...)` method (per I4); no `view=` parameter accepted on read/eval methods (rejected at 3 SDK boundaries per cross-cutting finding #3). Therefore **no opportunity for the two layers to conflict** today — neither layer exists. A8's two behavioral rules (i) "raise on conflict" and (ii) "don't do nesting" are **future acceptance gates** for when the scoped runtime substrate from I6 lands. | **(e) deferred-aligned vacuously** — same pattern as I9. Both behavioral rules are well-defined design decisions (raise + no nesting) but cannot be exercised today because the substrate doesn't exist. A8 is **a future acceptance gate**, not an implementable invariant. **Per user guidance: not a shipped conflict** — Q-worthy only as a narrow "what counts as conflict" implementation-detail question (e.g., same view_digest? same asrt_id set? different view names?), which is deferred to I6 implementation time, not raised as a Phase 3 design question. | low (today) / future acceptance gate when I6 lands | confirm in I6 acceptance gate when implementing scoped runtime; A8's stated design rules (raise + no nesting) become non-trivial test cases at that point. No new Q raised — implementation detail of "what counts as conflict" defers to I6 implementation time. |
| A9 | stale / mismatch 必须显式报错,禁止 fallback 到 full universe | Direct commitment-level restatement of I9. Shipped state: no scoped runtime substrate exists (per I6 (d)); no `view=` scope filter (per I7 (d)); therefore no opportunity for silent fallback to occur. A9's behavioral rule (raise rather than degrade) is a future acceptance gate. | Mirrors I9 — **(e) deferred-aligned vacuously**. Identical to I9 framing: vacuously satisfied today by absence of scoped runtime; becomes non-trivial acceptance criterion when I6 lands. | low (today) / depends on I6 implementation choice (future) | confirm in I6 / I7 acceptance gate when implementing scoped runtime. Identical to I9 recommendation. |
| A10 | EvaluateResult / EvidenceGraph metadata 必须记录 db snapshot + optional view context | **Commitment-level projection of I10**; per audit guardrail (Batch 2b + user reaffirmation), this row does NOT re-expand the evidence service design or cite deleted evidence service blueprints. Shipped state and gap analysis are fully covered by I10 (see §3 I10 row + I10 cross-cutting observation). A10-specific wording elements: (i) "must record" — strong requirement (not optional); (ii) "optional view_digest" — explicit optionality marker (view_digest is None when no `view=` attached, consistent with I8 routing + Q5 dependency). The 4 metadata fields (db snapshot anchors + optional view context) are NOT carried at evaluate-result / evidence-graph level today: `CandidateSet` shape lives in `core/derivation/candidates` (secondary surface per §1); `SupportArtifact` (§7.15 `_support.py:97-126`) and `ProvenanceEnvelope` (§7.15 `_support.py:147-162`) carry no `db_id` / `tx_id` / `view_digest`; `schema_digest` lives at 4 other anchors (cross-cutting finding #6) but not at evaluate-result level. | Mirrors I10 — split classification: **(d) genuinely new** for 3 of 4 fields (`db_id`, `tx_id`, `view_digest`); **(c) shape conflict** for `schema_digest` location. Cross-doc contract status: consumer side (evidence service) **deleted, redraft pending** — DB/view runtime cannot resolve A10 unilaterally. | high (cross-doc dependency + blocked on evidence service blueprint redraft + dependency on I2/I3/Q1-Q5) | defer entirely — A10 is the commitment-level statement; I10 has the canonical shipped-state analysis. Per audit guardrail this row does NOT propose implementation paths, does NOT cite deleted evidence service blueprints, and does NOT expand new evidence design. Resolution path is the same as I10: blocked on (1) evidence service redraft to define metadata consumer shape + (2) Q1-Q5 to provide identity sources. |
| A11 | branch / writable sub-fg / remote / multi-db / Rule persistence 全部 deferred | A11 is a **deferred-items meta-row**. Cross-references to anchor design strictness: design §3 cross-cut table (line 73) "Rule persistence / SavedRule registry → Rules 先保持 code artifact;Database 只持事实和 schema anchor"; design §17 D9 (line 713) "Rule persistence / SavedRule → 需要 rule registry / deployment governance" (deferred-trigger condition); design §18 A20 (line 739) "rules 留在用户 Python 代码" (literal reading: NO file-backed SavedRule layer). Five items verified separately. **branch / writable sub-fg / remote / multi-db**: no shipped concept anywhere (verified by §7 inventory absence — none of these surface in any of the 17 read files). **Rule persistence / SavedRule**: **shipped HAS full SavedRule persistence layer**. Concrete shipped surface: `fg.rules.save(...)` (§7.12 `sdk/store.py:2092-2103`) → `application.authoring_runtime.save_rule(registry, payload, schema_ir=...)` (`application/authoring_runtime.py:54-65`) → `FileAuthoringRegistry.register_rule_spec(payload)` (file-backed). Returned handle `SavedRuleRef(rule_id, version)` (`application/authoring_runtime.py:20-34`) IS literally the "SavedRule" the design defers. Parallel inference path via `fg.inferences.save(...)` (§7.12 `sdk/store.py:2127`) → `app_save_inference` (`application/authoring_runtime.py:68-79`) → `SavedInferenceRef`. Plus `load_rule` / `list_rules` / `get_rule` / `delete_rule` SDK surface. Per literal reading of A11 + A20 + D9 jointly, this shipped surface **directly conflicts** with the design prohibition — A20 says "rules 留在用户 Python 代码", not "rules live in FileAuthoringRegistry but outside Database substrate". | **Split classification.** **branch / writable sub-fg / remote / multi-db: (a) shipped covers** — absent everywhere, deferred-aligned. **Rule persistence / SavedRule: (c) shape conflict** — shipped has the full SavedRule layer (`fg.rules.save/load/list/get` + `SavedRuleRef` + `FileAuthoringRegistry.register_rule_spec`); design A11+A20+D9 jointly require it absent in v1. This is NOT merely a Q6 location-migration concern (where the registry lives); it is an **existence** concern (whether the registry should exist at all per A20). Previous framing (audit pre-revision) called this (a) on the basis that `FileAuthoringRegistry` is "outside Database substrate" — that framing was too soft: A20's literal reading does not exempt the SDK authoring layer either. | low (for 4 absent items) / **medium for SavedRule** (real conflict touching shipped SDK surface) | Per-item: **branch / writable sub-fg / remote / multi-db** → confirm deferred-alignment in §5 D-series rows. **Rule persistence / SavedRule** → defer to new **Q8** (SavedRule persistence governance). Q8 is independent of Q6 (Q6 = where the registry lives, contingent on Q8 keeping it; Q8 = whether the registry should exist at all). |
| A12 | `db_id` 由 `Database.create` 生成并持久化;`Database.open(path)` 必须读回同一 `db_id`;in-memory default db 使用非 durable `mem:<uuid4>` | Three behavioral assertions, verified separately. **(A) `db_id` generated by `Database.create` + persistently stored**: depends on I1 ((c)) + I11-A ((d)). No shipped `Database.create` method, no `db_id` concept. **(B) `Database.open(path)` returns same `db_id`** (cross-process reproducibility / round-trip identity): depends on I2 + I11-A. No `Database.open` shipped (per I1/I4). **(C) in-memory default uses `mem:<uuid4>` prefix-typed identity**: design specifies a **prefix-typed identity** pattern (`mem:` for non-durable in-memory, `db:` implied for durable). Shipped state: `Ledger(":memory:")` (§7.5 `ledger.py:255-279`) opens in-memory SQLite without any db identity (no `db_id`, no `mem:`-prefix anywhere). Shipped uses prefix-typed identity in adjacent contexts (`idref_v1:<EntityType>:<base32>` at §7.2 `idref_v1.py:73`; `sha256:<hex>` at §7.1 `digests.py:11`) but NOT for db identity. | **(d) genuinely new** on all 3 sub-assertions. The `Database.create` / `Database.open` lifecycle, durable storage round-trip for `db_id`, and `mem:<uuid4>` prefix-typed identity are all absent. Shipped's prefix-typed identity patterns (`idref_v1:`, `sha256:`) are precedent for the `mem:` / `db:` prefix style but do NOT constitute partial implementation. | high (depends on I1 + I2 + I11 cluster) | defer — blocked on Q1 (Database class) + Q3 (identity formula primitives). The `mem:<uuid4>` sub-assertion is **conceptually distinct from durable `db_id`**: design separates non-durable (in-memory, uuid-based) from durable (file-backed, content-addressed); shipped doesn't make this distinction today (no db identity at all). |
| A13 | `AssertionRecord` 最小 shape 锁定为 `asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta`;`asrt_id` content-addressed | This is the **commitment-level expression of cross-cutting finding #1** (4 `AssertionRecord`-like shapes coexist in shipped + design). Two sub-assertions. **(A) shape lock to 7 specific fields**: design specifies `asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta`. Shipped has **3 distinct shapes, NONE matching design 7-field**: `Claim(asrt_id, pred_id, e_ref, rest_terms)` (§7.5 `ledger.py:21-26`, 4 fields); `AssertionRecordDTO(assertion_id, value, active, meta)` (§7.11 `application/protocol/entity_read.py:60-72`, 4 fields, field name `assertion_id` not `asrt_id`); SDK `AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta)` (§7.13 `sdk/facade.py:87-96`, 8 fields). Design's `fact_tuple` is a flat positional tuple combining shipped's `e_ref + rest_terms`; design's `schema_digest / assertion_digest / tx_id` all depend on I2 + I11 (all (d)). **(B) `asrt_id` content-addressed**: shipped uses `uuid.uuid4().hex` at §7.5 `ledger.py:1066` + §7.17 `write_protocol.py:120-121` — explicitly ruled out as content-addressed identity template by A3 prohibition. | Split classification. **(A) (c) shape conflict** — 3 shipped shapes coexist, none matches design 7-field; this is a **multi-shape reconciliation question**, see new §8 Q7. **(B) (d) genuinely new** + reinforces A3 prohibition — shipped uuid-based `asrt_id` is incompatible with content-addressing requirement. | high (touches storage row shape + 3 SDK layers + Phase 2 cross-cutting finding #1) | defer — (A) blocked on Q7 (shape reconciliation) + Q3 (`asrt_id` content-addressing primitives). (B) blocked on Q3 + A3 prohibition. Phase 2 cross-cutting finding #1 surfaced this gap qualitatively;A13 is its commitment-level expression. |
| A14 | attach-to-view / attach-to-snapshot 与 read-only enforcement 必须同 ship;禁止 scoped runtime 可写 | **Release-engineering acceptance gate**, not a behavioral invariant for current shipped. Shipped state: no attach lifecycle (per I4 (c)); no scoped runtime (per I6 (d)); no read-only enforcement mechanism (per I4 — "writable by absence"). No transient release exists today because none of the scoped-runtime substrate exists. A14's behavioral guarantee — that scoped runtime cannot exist in a writable transient state — is **enforceable only when I5 + I6 land**. | **(e) deferred-aligned vacuously** — same pattern as I9 / A8 / A9. Vacuously satisfied today (no substrate to release); becomes a non-trivial release-engineering constraint when I5 + I6 are implemented. A14 is a **shipping discipline rule**, distinct from feature acceptance criteria. | low (today) / release-engineering constraint when scoped runtime substrate lands (future) | confirm in I5 + I6 acceptance gate that read-only enforcement ships in the same release; no standalone action today. No new Q raised — A14 is a procedural commitment about release sequencing, not a design question. |
| A15 | rules 不进 workspace、不进 Database transaction;`FactGraph.attach(...)` 签名不含 `rules=`;`rule_set_digest` 在 evaluate 时计算 | This is the **design's authoritative anchor for rules-as-code governance** — referenced by revised Q6 (per commit `682f23eb`) and by I12. The audit-row text uses the design doc abbreviation; full design wording (§18 A15 of `database-view-fg-layered-architecture.zh.md:734`) reads: "rules 是 code artifact,v1 不进 workspace、不进 Database transaction;`FactGraph.attach(...)` 签名不含 `rules=`;rules 通过 `Expr / Inference / Rule` 内部引用承载,`rule_set_digest` 在 evaluate 时计算并写入 EvaluateResult metadata". Six sub-assertions verified separately. **(A) rules 是 code artifact**: split into two sub-paths. **(A-runtime)** SDK `Rule` / `Inference` objects are constructed in user code (§7.12 referenced via `_compile_rule_input` / `_compile_derivation_input`); `RuleRegistry` is an **in-memory dependency tracker only** — these portions align with rules-as-code philosophy. **(A-persisted)** shipped also exposes `FileAuthoringRegistry` + `SavedRuleRef` via `fg.rules.save/load/list/get` (§7.12 `sdk/store.py:2092-2125`) — this **persistence layer is the SavedRule design defers** (per A11 (c) + A20 literal reading "rules 留在用户 Python 代码" + D9 trigger condition). A-persisted is NOT support evidence for rules-as-code; it is a conflict, handled at A11(c) / Q8. Audit-row scope: **only A-runtime is classified here**; A-persisted classification lives at A11(c) and is not double-counted at A15. **(B) v1 不进 workspace**: **per revised Q6 + I12 (E) (commit `682f23eb`), shipped default violates strict prohibition** by auto-coupling `registry_root = workspace_path / "registry/"` (§7.12 `sdk/store.py:667-695`); `SDKStore.save()` rebinds `_authoring_registry` to `paths.registry` (§7.12 `sdk/store.py:2063-2090`). **(C) v1 不进 Database transaction**: per I12 (D) — rules go to `FileAuthoringRegistry`, never to `Ledger.append_*`. **(D) `FactGraph.attach(...)` 不含 `rules=`**: per I12 (A) — `attach()` doesn't exist; vacuously aligned. **(E) rules 通过 `Expr / Inference / Rule` 内部引用承载**: per I12 (B) — `_register_rule_dependencies` (§7.12 `sdk/store.py:2421-2451`) + `RuleRegistry` mechanism carries dependency references. **(F) `rule_set_digest` 在 evaluate 时计算 + 写入 `EvaluateResult` metadata**: per I12 (C) + I10 — `rule_set_digest` literally absent from shipped (grep-verified, 0 matches); `EvaluateResult` metadata seam is part of evidence service redraft (deferred, do NOT re-expand here). | Six-way split classification (A split into A-runtime + A-persisted with A-persisted cross-referred). **(A-runtime) (a) shipped covers** — SDK Rule/Inference user-code construction + RuleRegistry in-memory dependency tracker aligned with rules-as-code. **(A-persisted) cross-ref A11 (c)** — `FileAuthoringRegistry` / `SavedRuleRef` persistence layer is the SavedRule A11+A20+D9 defer; classified at A11(c), Q8 handles governance; not double-counted at A15. **(B) (c) shape conflict** [tightened 2026-05-20 per commit `682f23eb`; previously (c)+(a) split] — shipped default behavior violates design strict prohibition; migration mechanics per revised Q6 (contingent on Q8). **(C) (a) shipped covers** — verified via I12 (D). **(D) (e) deferred-aligned vacuously** — attach lifecycle absent. **(E) (a) shipped covers in spirit** — exact-shape comparison vs design wording requires rule-expression doc audit (secondary surface, out of scope). **(F) (d) genuinely new + cross-doc seam** — `rule_set_digest` absent; metadata placement part of evidence service redraft per I10. | medium-to-high (A-runtime / C / E aligned; **A-persisted** is the load-bearing conflict surfaced through A11(c); (B) is the workspace-coupling conflict requiring Q6 migration contingent on Q8; (F) is cross-doc deferred per I10) | split recommendations: **(A-runtime) (C) (E)** accept **(a)** — shipped aligned. **(A-persisted)** defer to A11(c) / Q8 — SavedRule existence governance is the load-bearing decision. **(B)** design prohibition established; migration mechanics per revised Q6 (contingent on Q8: if Q8 = remove SavedRule, Q6 becomes vacuous). **(D)** confirm in I4 / Q2 acceptance gate. **(F)** defer per I10 — cross-doc seam blocked on evidence service redraft + Q1-Q5. A15 is the most heterogeneous A-row in Phase 3 — sub-assertion distribution (A-runtime / B / C / D / E / F): (a) × 3 + (c) × 1 + (d) × 1 + (e) × 1 (A-persisted cross-refs A11, not counted here). |
| A16 | schema 分两层:authoring source 属于用户代码;compiled snapshot 由 Database 持久化为 `db/objects/schema/<schema_digest>.json` content-addressed | Full design wording (§18 line 735): "schema 分两层:authoring source 属于用户代码(git 治理);compiled snapshot 由 Database 持久化为 `db/objects/schema/<schema_digest>.json`(data 治理,content-addressed)". **Per audit guardrail: distinguish 3 distinct concepts — schema authoring source / compiled schema snapshot / registry schema entry. Do NOT treat shipped `registry/schema/schema_ir.json` as design's `db/objects/schema/<digest>.json`** — they share content but differ in path, content-addressing, and governance layer. Two sub-assertions verified separately. **(A) authoring source IS user code (git 治理)**: shipped uses `@entity` decorator + Python entity classes; `SDKStore.from_schema_classes(*classes)` derives `schema_ir` at construction time (§7.12 `sdk/store.py:752`). Schema authoring source IS user Python code under user's own version control. **(B) compiled snapshot persisted as `db/objects/schema/<schema_digest>.json` content-addressed**: shipped persists compiled schema_ir at **3 distinct anchor points**, none matching design layout: (i) `ledger_meta` row `schema_digest=<value>` via `set_ledger_meta("schema_digest", digest)` (§7.5 `ledger.py:780-786` + `sdk/store.py:920-922`) — stores the DIGEST, not the IR; (ii) `registry/schema/schema_ir.json` via `FileAuthoringRegistry.upsert_schema_ir` (`authoring/registry_fs.py:47-67`) — stores the FULL IR at fixed path under `registry/`, NOT content-addressed (path is literally `schema/schema_ir.json` for any digest); (iii) `factgraph_workspace.json` manifest field `schema_digest` (§7.8 `workspace_runtime.py:46-65`) — stores the DIGEST as top-level manifest field (which design A19 explicitly removes). Per Phase 2 cross-cutting finding #6, `schema_digest` already has 4 anchors shipped (lifecycle, validation, persistence, manifest); A16 adds a 5th canonical location at `db/objects/schema/<digest>.json` content-addressed. | **Split classification.** **(A) (a) shipped covers** — schema authoring source IS user Python code via `@entity` + `from_schema_classes`. **(B) (c) shape conflict** — compiled schema persistence exists in shipped at 3 anchors but **none at `db/objects/schema/<digest>.json` content-addressed path**. The content-addressed scheme + the canonical-location uniqueness (one path per digest, content-addressed) are both design-additive. Note interaction with A20(E): A20(E) commits to migrating shipped `registry/schema/schema_ir.json` → `db/objects/schema/<digest>.json` AS the resolution mechanism for A16(B); A16(B) is the architectural claim, A20(E) is the migration commitment. | high (touches A17 db/ layout + A19 manifest reshape + A20(E) migration + I13 workspace layout + multi-anchor reconciliation) | defer — blocked on Q1 (Database boundary) + A17 / A19 / A20 workspace layout decisions. **Per audit guardrail**: this row maintains the 3-way distinction strictly — shipped `registry/schema/schema_ir.json` is **NOT** design's `db/objects/schema/<digest>.json`. Resolution requires deciding: (i) is `db/objects/schema/<digest>.json` the unique canonical compiled-schema path (or are some shipped anchors retained as caches/indexes);(ii) which of the 3 shipped anchors are deduplicated when canonical location is chosen;(iii) how shipped multi-anchor consistency invariants (cross-cutting finding #6) translate post-migration. |
| A17 | Database 物理布局 Git-style:`db/objects/` content-addressed write-once + `db/refs/head.txt` 唯一 mutable + `db/assertions.db` SQLite index | Full design wording (§18 line 736): "`db/objects/` 全部 content-addressed write-once(tx + schema);`db/refs/head.txt` 是唯一 mutable ref file,内容是当前 head `tx_id`;`db/assertions.db` 是 mutable SQLite index layer,可从 `db/objects/tx/` 回放重建,不参与 cross-process identity". Three sub-assertions verified against **current workspace runtime only** (per audit guardrail). **(A) `db/objects/` content-addressed write-once for tx + schema**: shipped has NO `db/objects/` directory anywhere (verified §7.8 inventory + `workspace_runtime.py:14-19` constants list only `ledger.db` + `registry/`). No content-addressed tx storage exists — depends on I2 (d) `tx_id` absent + I11 (d) tx-objects layout. Schema persistence exists but at 3 non-design anchors (per A16(B)), none under `db/objects/`. **(B) `db/refs/head.txt` 唯一 mutable ref (content = current head `tx_id`)**: shipped has NO `db/refs/` directory, NO `head.txt` file, NO "head tx_id" concept (depends on I2 (d) `tx_id` absent). Shipped workspace layout is flat under root with no refs layer — mutable state lives entirely inside SQLite tables. **(C) `db/assertions.db` SQLite as INDEX (replayable from `db/objects/tx/`, not identity-bearing)**: shipped SQLite file is `ledger.db` at workspace root (§7.8 `workspace_runtime.py:18` `WORKSPACE_LEDGER = "ledger.db"`), NOT under `db/`. Crucially, **shipped SQLite IS identity-bearing**: assertion data lives ONLY in SQLite tables (`claims / claim_args / meta_rows / annotation_rows / revokes / ingest_keys / ledger_meta` per §7.5 inventory);`_to_jsonable` envelope + canonical encoding live inside SQLite rows;no replay log exists outside SQLite. Design's "replayable from `db/objects/tx/`" architecture inverts this — SQLite becomes a derived index layer over the tx-objects log. | **(d) genuinely new × 3 sub-assertions**, with (C) carrying a **semantic inversion** beyond layout absence. (A) + (B) are pure absence (no directories, no files);(C) is absence PLUS architectural inversion (design treats SQLite as derived index, shipped treats SQLite as authoritative storage). The inversion is non-trivial: design's `db/objects/tx/` replay log is the source of truth, SQLite is rebuildable from it;shipped has no such log, so SQLite IS the source of truth. | high — cascades on Q1 (Database boundary) + Q3 (`tx_id` formula) + I2 + I11 (tx-objects shape) + I13 (workspace layout migration). Architectural inversion adds: whether the design's replay-log model is even desirable given shipped's existing SQLite-authoritative assumption | defer — blocked on Q1 + Q3 + I2 + I11. **Per audit guardrail**: this row references only **current workspace runtime** (`workspace_runtime.py:14-19, 46-65, 160-187`);NO references to rolled-back DB.1 work. Resolution requires upstream identity decisions (Q1 + Q3) before physical layout can be specified. The architectural inversion in (C) — SQLite as derived index vs SQLite as authoritative storage — is itself a **design discussion point** that may surface a new Q if user wants to question whether the design's replay-log model is required for v1, but **NOT escalated this batch** (the design as written commits to the inversion;questioning it would be a design revision, outside audit scope). |
| A18 | SubsetView 物理布局:`views/objects/<view_digest>.json` content-addressed;named view registry deferred to v2 | Full design wording (§18 line 737): "`views/objects/<view_digest>.json` content-addressed write-once;named view registry(`views/refs/<name>.json`)deferred 到 v2,与 persistent named view 同时落地". Two sub-assertions verified separately. **(A) `views/objects/<view_digest>.json` content-addressed write-once**: shipped has NO `views/` directory anywhere. Views live as in-memory dict entries in `_SDKViewsManager._views: dict[str, FrozenAssertionView]` (§7.12 `sdk/store.py:101-179`); no persistence layer at any path. Depends on I3 (c) `view_digest` absent — design's content-addressed scheme requires `view_digest` formula. **(B) named view registry `views/refs/<name>.json` deferred to v2**: shipped HAS in-memory named view registry via `_SDKViewsManager` — `fg.views.create(name, asrt_ids)` / `update` / `delete` / `get` / `list` (`sdk/store.py:121-179`); registry is **in-memory only, not persisted to any filesystem path**. Interpretation: design's "named view registry deferred 到 v2" refers to PERSISTED named view registry at `views/refs/<name>.json`; shipped's in-memory name → asrt_ids mapping does not persist beyond `SDKStore` lifetime, consistent with "deferred persistent named view registry". Caveat: a stricter reading of design "deferred 到 v2,与 persistent named view 同时落地" could be read as "any named view registry (including in-memory) is deferred to v2", in which case shipped's `fg.views.create(name, ...)` SDK surface conflicts — but the more natural reading is "PERSISTED registry deferred", since design's bracketed example is the filesystem path `views/refs/<name>.json`. | **Split classification.** **(A) (d) genuinely new** — no `views/objects/<digest>.json` persistence layer exists in shipped; depends on Q4 (view shape resolution providing `view_digest` formula). **(B) (a) shipped covers under natural reading** — in-memory named view registry is consistent with "persistent named view registry deferred"; shipped does NOT persist. Caveat (per stricter reading): a clarification micro-question exists — is design "deferred 到 v2" about persistence specifically, or about the in-memory registry surface too? **Not escalated as new Q this batch** per user batch guidance (clarification-only, not load-bearing). | medium-to-high (depends on Q4 view shape + Q8 SavedRule existence governance, since if Q8 = remove FileAuthoringRegistry, design should not grow a parallel view persistence either; the "view persistence" question is structurally parallel to "rule persistence") | defer — blocked on Q4 (view shape with `view_digest`) + Q8 (whether view persistence layer should exist at all, parallel to SavedRule existence question). **Per audit guardrail**: no implementation path proposed for `views/objects/` directory. The (B) caveat is **noted but not escalated** to a new Q — it is a clarification of design wording, not a load-bearing architectural decision;deferred to user judgment if/when Q4 reaches resolution. |
| A19 | `factgraph_workspace.json` 收缩为最小 manifest:`{workspace_version, components.{db, views}, created_at, last_saved_at}` | Full design wording (§18 line 738): "`factgraph_workspace.json` 收缩为最小 manifest:`{workspace_version, components.{db, views}, created_at, last_saved_at}`;`db_id` / `schema_digest` / `data_digest` 不在顶层 manifest 重复". Direct field-by-field comparison against shipped (§7.8 `workspace_runtime.py:46-65 workspace_manifest_payload`). Shipped 6-field manifest vs design 4-field manifest. **Per-field reconciliation** (against **current workspace runtime only** per audit guardrail): (i) `factgraph_workspace_version` (shipped, `workspace_runtime.py:56`) vs `workspace_version` (design) — **field name conflict**, design drops `factgraph_` prefix. (ii) `save_scope: "level_4"` (shipped, `workspace_runtime.py:57`) — **extra field absent in design**; serves Blueprint 3 layout versioning but not in design's minimum manifest set. (iii) `schema_digest` top-level (shipped, `workspace_runtime.py:58`) — **explicitly removed by design A19**: design says "`db_id` / `schema_digest` / `data_digest` 不在顶层 manifest 重复"; canonical location moves to `db/objects/schema/<digest>.json` per A16(B) + A20(E). (iv) `components.{ledger, registry}` (shipped, `workspace_runtime.py:59-62`) vs `components.{db, views}` (design) — **component naming + structure conflict**: shipped's `ledger` → design's `db` is a rename (shipped's `ledger.db` file becomes design's `db/` directory containing objects/refs/assertions.db per A17); shipped's `registry` component is **removed entirely** per A20 + Q8 (SavedRule existence governance); design's `views` component is **new** per A18 (views/ directory layout). (v) `created_at` + `last_saved_at` (shipped, `workspace_runtime.py:63-64`) — **aligned** with design (both manifests carry these). **Validator side-effect**: shipped's `validate_workspace_manifest` (§7.8 `workspace_runtime.py:87-116`) enforces all 6 shipped fields strictly; migration to design shape requires validator rewrite, not just data-field rename. **Migration impact**: existing shipped workspaces on disk would fail validation under design manifest shape — needs upgrade-on-load path. | **(c) shape conflict — manifest reshape across multiple fields**. Field-by-field: 1 rename (`factgraph_workspace_version` → `workspace_version`), 2 removals (`save_scope`, `schema_digest` top-level), 2 component changes (`ledger` → `db` rename, `registry` → removed per Q8, `views` added per A18), 2 unchanged (`created_at`, `last_saved_at`). Internal consistency check: design's removal of top-level `schema_digest` is consistent with A16+A20(E) placing canonical schema at `db/objects/schema/<digest>.json` (no duplicate). The `components.registry` removal is consistent with A11+A20+Q8 (SavedRule existence governance) — if Q8 = (a) hard remove, this manifest field becomes trivially absent;if Q8 = (b)/(c) keep, the manifest field stays but design says it shouldn't (creating a residual design-shipped tension). | medium-to-high (depends on A16/A17/A18 layout decisions + Q8 SavedRule outcome; validator rewrite needed; migration path for existing shipped manifests affects all on-disk workspaces) | defer — blocked on A16(B) (compiled-schema placement) + A17 (db/ layout) + A18 (views/ layout) + Q8 (SavedRule existence determines whether `components.registry` retains). **Per audit guardrail**: shipped references are to **current workspace runtime** (`workspace_runtime.py:14-19, 46-65, 87-116, 160-177`); **NO references to rolled-back DB.1**. Resolution requires deciding migration path for existing shipped manifests (e.g., upgrade-on-load transforming 6-field → 4-field, with `components.ledger.db` → `components.db/assertions.db` move). |
| A20 | 现 `registry/` 全部不迁移:rules/inferences/manifest/events 移除;`registry/schema/schema_ir.json` 迁到 `db/objects/schema/<schema_digest>.json` | Full design wording (§18 line 739): "现 `registry/` 全部不迁移到新 layout:`registry/rules/` / `registry/inferences/` / `registry/registry_manifest.json` / `registry/authoring_apply_events.jsonl` 移除;`registry/schema/schema_ir.json` 迁到 `db/objects/schema/<schema_digest>.json`;rules 留在用户 Python 代码". **Per audit guardrail (Q8 strict framing): items (A)-(D) + (F) are part of SavedRule existence governance under Q8, NOT a simple location migration.** Five sub-items + 1 governance statement. **(A) `registry/rules/` removed**: shipped writes via `FileAuthoringRegistry.register_rule_spec` to `rules/<rule_id>/<version>.json` (`authoring/registry_fs.py:83-118`); design A20 commits to entire removal. **(B) `registry/inferences/` removed**: shipped writes via `register_inference_spec` to `inferences/<inference_id>/<version>.json` (parallel structure to (A)); design removes entirely. **(C) `registry/registry_manifest.json` removed**: shipped's central index tracking schema entry + rules list + inferences list (`authoring/registry_fs.py:40-41 manifest_path` + `:55-61 schema entry write` + `:100-110 rules manifest update`); design removes entirely. **(D) `registry/authoring_apply_events.jsonl` removed**: shipped's authoring apply log (`authoring/registry_fs.py:43-45 apply_log_path`); design removes entirely. **(E) `registry/schema/schema_ir.json` → `db/objects/schema/<schema_digest>.json` (MIGRATION, not removal)**: shipped writes via `upsert_schema_ir` to fixed path `schema/schema_ir.json` under `registry/` (`authoring/registry_fs.py:47-67`); design relocates to content-addressed `db/objects/schema/<digest>.json` per A16(B). Note: (E) is the **schema persistence path migration**, distinct concern from (A)-(D)(F). **(F) rules 留在用户 Python 代码**: governance statement matching A11(c) Rule persistence + A15(A-persisted) + Q8 literal reading. | **Split classification per Q8 strict framing.** **(A) (B) (C) (D) (F): all (c) shape conflict, all defer to Q8** — these constitute the SavedRule persistence layer (rules + inferences + manifest + apply log) that Q8 governs. Per A11(c) revision: shipped has full layer; design A20 commits to removing it. Per Q8 enumeration: (Q8-a) hard remove → A20(A)-(D)(F) align; (Q8-b) keep shipped + mark deferred → A20(A)-(D)(F) stay in conflict (design-shipped tension persists); (Q8-c) deprecation → A20(A)-(D)(F) align after grace period. **(E) (c) shape conflict, defers to A16(B)** — schema entry migration is a SEPARATE concern from SavedRule existence; it requires deciding the canonical compiled-schema path (per A16(B): shipped has 3 anchors, design picks `db/objects/schema/<digest>.json`). A20(E) commits to the path migration AS the resolution mechanism for A16(B). **Key audit point**: A20(E) is **independent of Q8** — even if Q8 = (b) keep shipped, A20(E) is still a workspace-layout migration question (schema entry can move to `db/objects/schema/` without removing the rest of `registry/`). | high — (A)-(D)(F) load-bearing on Q8 decision; (E) load-bearing on A16(B) + I13 workspace layout decisions | defer — split blocking conditions: **(A)(B)(C)(D)(F)** → Q8 (SavedRule existence governance); **(E)** → A16(B) + A17 (db/objects layout) + I13 (workspace layout migration). **Per audit guardrail**: this row uses **Q8 strict framing** — `registry/rules/` / `registry/inferences/` / `registry_manifest.json` / `authoring_apply_events.jsonl` removal is governance-driven (does the SavedRule persistence layer exist at all per A11+A20 literal "rules 留在用户 Python 代码"), NOT a simple location migration. The shipping discipline of (A)-(D)(F) removal depends entirely on Q8 resolution. (E) is the only sub-item that is "pure layout migration" independent of Q8. No implementation paths proposed. |

**A1-A5 cross-cutting observation** (informational, not a triage decision):

A1-A5 cover the **foundation-layer commitments** (Database / DatabaseValue / view shape). They mostly mirror Phase 2 I-rows but with **commitment-specific extensions**:

- **A1** is meta — the "only 4 concepts" scope claim itself is satisfied by design wording; the per-concept mapping all maps to I1-I4 conflicts.
- **A2** is the most heterogeneous A-row in this batch: (A) inherits I1's (c); (B) raises a **design ambiguity** about whether "minimum version only append assertions" is strict-API or loose-SQL. If strict, shipped exceeds minimum scope (already has `retract_by_asrt` / `replace_field`); the disambiguation folds into Q1.
- **A3** adds an **explicit prohibition** beyond I2: tx_id MUST NOT be UUID or auto-increment. This reinforces Q3 (a)/(b) framing — UUID-based `asrt_id` (shipped) is ruled out as tx_id template by design fiat.
- **A4** is the rare **(a) shipped covers** row — alignment is partly trivial-by-absence (no version/branch concept to confuse with) but the negative claim does hold today.
- **A5** is the concrete spelling-out of I3's 4 anchor fields; cannot be evaluated independently of Q4.

Batch 1 classification distribution: **(a) shipped covers: 1** (A4); **(c) shape conflict: 3** (A1, A2-A, A5); **(d) genuinely new: 1** (A3); **ambiguous-pending-Q: 1** (A2-B folds into Q1). All 5 rows defer / doc-revise / confirm-during-Qx;no implementation paths proposed.

**A6-A10 cross-cutting observation** (informational, not a triage decision):

A6-A10 cover the **runtime view-scope layer** (attach / view= consumer / no-fallback / evidence seam). They are **dominantly Phase 2 mirrors** with commitment-level specifics:

- **A6** is the most carefully split row in this batch — per user guidance, the two attach-targets (`DatabaseValue` vs `FrozenAssertionView`) have **different dependency chains** and are NOT a single missing point. (A) DatabaseValue attach depends on Q1 + Q2 + Q3 (via I2 + I4 + I5); (B) FrozenAssertionView attach depends on Q1 + Q2 + Q3 + Q4 (via I3 + I4 + I6). A6 (A) is also **broader than I5**: I5 was the snapshot-specific `attach(db.as_of(tx_id))` form, A6 (A) covers attaching ANY DatabaseValue including current head.
- **A7** is a direct I7+I8 projection with the same 3-part split.
- **A8** was a candidate for a new Q but **per user guidance, shipped's absence of dual-layer mechanism makes the conflict-policy question a future design detail, not a shipped conflict**. Grep verified 0 hits for `attach` lifecycle + 0 hits for runtime/method-level view dual-layer concepts. A8's stated design rules (raise on conflict + no nesting) are well-defined design decisions; they become acceptance gates when I6 lands.
- **A9** is a direct I9 mirror.
- **A10** sticks to I10's cross-doc seam framing per Batch 2b precedent + user reaffirmation. **Does NOT re-expand evidence design, does NOT cite deleted evidence service blueprints, does NOT propose implementation path.** It is commitment-level projection of I10, not a new analysis.

Batch 2 classification distribution: **(a) shipped covers: 0**; **(c) shape conflict: 0 primary + 2 partial** (A7 universe-def, A10 schema_digest); **(d) genuinely new: 5 sub-assertions** (A6-A, A6-B, A7 view scope filter, A10 db_id/tx_id/view_digest); **(e) deferred-aligned vacuously: 3 + 1 partial** (A8, A9, A10 cross-doc, A7 routing). **0 new Qs raised** — A6 reuses Q1-Q4; A7 reuses Q4+Q5; A8 explicitly does NOT raise a new Q per user guidance; A9 reuses no Q (acceptance gate); A10 reuses Q1-Q5 + evidence service redraft dependency. All 5 rows defer / confirm-during-Qx / confirm-in-I6-acceptance-gate;no implementation paths proposed.

**A11-A15 cross-cutting observation** (informational, not a triage decision; revised 2026-05-20 alongside A11 + A15(A) tightening + Q8 addition):

A11-A15 cover the **identity / shape / rules-governance commitments** — the most heterogeneous batch in Phase 3. Per-row character:

- **A11** is a **deferred-items meta-row** with a **split classification**. 4 of 5 listed items (branch / writable sub-fg / remote / multi-db) absent everywhere → `(a)`. The 5th (Rule persistence / SavedRule) is **a real shape conflict** — shipped has full `fg.rules.save/load/list/get` + `SavedRuleRef` + `FileAuthoringRegistry.register_rule_spec` (`sdk/store.py:2092-2125` + `authoring_runtime.py:54-79` + `:20-51`); design §3 / §17 D9 / §18 A11 / §18 A20 jointly require it absent ("rules 留在用户 Python 代码" literal). Pre-revision framing "outside Database substrate → (a)" was too soft (the design does not exempt the SDK authoring layer either). Raises **new Q8** (SavedRule existence governance).
- **A12** is the **first commitment to spell out `Database.create / Database.open` lifecycle** + introduces a **non-durable identity convention** (`mem:<uuid4>` prefix-typed). Shipped's adjacent prefix-typed identity patterns (`idref_v1:<entity_type>:<base32>`, `sha256:<hex>`) are stylistic precedent but NOT partial implementation. Sub-assertion (C) `mem:<uuid4>` is **conceptually distinct from durable `db_id`** — design separates non-durable from durable identity, shipped doesn't distinguish today.
- **A13** is the **commitment-level expression of Phase 2 cross-cutting finding #1** (4 `AssertionRecord`-like shapes coexist). Shipped has 3 distinct shapes (`Claim` 4f / `AssertionRecordDTO` 4f / SDK `AssertionRecord` 8f); design adds a 4th 7-field shape. Per user-guided guardrail, this batch raises **new Q7** (shape reconciliation) rather than embedding a resolution proposal in the row.
- **A14** is a **release-engineering acceptance gate** — same `(e) deferred-aligned vacuously` pattern as I9 / A8 / A9, but its content is a shipping-discipline rule (read-only enforcement must ship in same release as attach-lifecycle / scoped runtime), not a feature acceptance criterion. Distinct kind of commitment from I-series invariants.
- **A15** is the **most heterogeneous A-row in Phase 3** — sub-assertion (A) is **split into (A-runtime) + (A-persisted)** post-revision. (A-runtime) Rule/Inference user-code construction + `RuleRegistry` in-memory tracker → `(a)`. (A-persisted) `FileAuthoringRegistry`-backed `SavedRule` layer → cross-refs A11 (c) / Q8, not double-counted at A15. Distribution at A15 itself: (a) × 3 [A-runtime, C, E] + (c) × 1 [B workspace coupling] + (d) × 1 [F `rule_set_digest`] + (e) × 1 [D attach lifecycle].

Batch 3 classification distribution (revised): **(a) shipped covers: 0 standalone + 4 sub-assertions** (A11 (a) 4 items + A15 A-runtime / C / E count as A15 sub-rows); **(c) shape conflict: 1 standalone + 2 sub-assertions** (A11 SavedRule, A13-A, A15-B; A15 A-persisted cross-refs A11 not double-counted); **(d) genuinely new: 3 sub-assertions + 1 reinforcement + 1 sub-assertion** (A12 A/B/C, A13-B reinforces A3, A15-F); **(e) deferred-aligned vacuously: 2 + 1 sub-assertion** (A14, A15-D). **2 new Qs raised**: **Q7 (AssertionRecord shape reconciliation)** + **Q8 (SavedRule existence governance)**. Q-state: Q1-Q5 dependency stack;Q6 + Q7 + Q8 parallel to chain;**Q6 contingent on Q8** (Q6 vacuous if Q8 = remove). A11/A14 confirm-during-Qx;A12 defers to Q1+Q3;A13 defers to Q7;A15 split — A-runtime/C/E accept, A-persisted defers to A11/Q8, B migration via Q6 contingent on Q8, D confirm in Q2, F cross-doc seam deferred per I10. No implementation paths proposed.

**A16-A20 cross-cutting observation** (informational, not a triage decision):

A16-A20 cover the **physical layout + workspace manifest commitments** — the most architecturally cohesive batch in Phase 3. All 5 rows touch workspace storage layout (where things live on disk) and form an **internally consistent design block**: A16(B) picks `db/objects/schema/<digest>.json` for compiled schema → A17 picks Git-style `db/objects/` + `db/refs/head.txt` + `db/assertions.db` for Database physical layout → A18 picks `views/objects/<view_digest>.json` for view persistence → A19 reshapes `factgraph_workspace.json` to reflect the new components `{db, views}` (dropping `registry`, dropping `schema_digest` top-level since A16(B) places it under `db/objects/schema/`) → A20 specifies the migration path from shipped `registry/` (removal + schema entry migration to db/objects).

**Per-row character**:

- **A16** is the **schema persistence anchor** — establishes that compiled schema lives at `db/objects/schema/<digest>.json` content-addressed. Shipped has 3 non-design anchors (ledger_meta value, registry/schema/schema_ir.json file, manifest top-level field) — none at the design path. The audit-guardrail 3-way distinction (authoring source / compiled snapshot / registry schema entry) is honored: shipped `registry/schema/schema_ir.json` is NOT the design `db/objects/schema/<digest>.json` despite content overlap.
- **A17** is the **Database physical layout commitment** — Git-style `db/objects/` + `db/refs/head.txt` + `db/assertions.db`. Shipped has none of the directory structure;notably (C) carries an **architectural inversion** (SQLite as derived index in design vs SQLite as authoritative storage in shipped). All 3 sub-assertions (d) genuinely new. **Audit guardrail satisfied**: references only `workspace_runtime.py` for shipped state, no DB.1 citations.
- **A18** is the **SubsetView physical layout commitment**. (A) `views/objects/<view_digest>.json` (d) genuinely new (no `views/` directory shipped); (B) named view registry deferred → (a) under natural reading (shipped's in-memory `_SDKViewsManager` is not persisted, consistent with "PERSISTED registry deferred"). A stricter caveat noted but not escalated to a new Q (clarification-only, deferred to user judgment).
- **A19** is the **manifest reshape** — 6-field shipped → 4-field design. Field-by-field reconciliation: 1 rename, 2 removals, 2 component changes, 2 unchanged. Internal consistency confirmed: design removal of top-level `schema_digest` is consistent with A16+A20(E) placing it under `db/objects/schema/`;design removal of `components.registry` is consistent with Q8 = (a). **Audit guardrail satisfied**: references only `workspace_runtime.py` for shipped state, no DB.1 citations.
- **A20** is the **migration commitment** with **two distinct concern threads**: (A)(B)(C)(D)(F) → SavedRule existence governance per Q8 strict framing (per audit guardrail);(E) → schema persistence path migration per A16(B). Important separation: A20(E) is independent of Q8 — even if Q8 = (b) keep shipped, A20(E) is still a workspace-layout migration question.

Batch 4 classification distribution: **(a) shipped covers: 1 sub-assertion** (A16-A authoring source); **(c) shape conflict: 3 + 6 sub-items** (A16-B compiled schema 3-anchor coexistence, A19 manifest reshape, A20(A)(B)(C)(D)(E)(F) — A20(F) is governance statement classified with (A)-(D)); **(d) genuinely new: 3 (A17) + 1 sub-assertion (A18-A) = 4 sub-assertions**; **(a) under natural reading**: 1 sub-assertion (A18-B). **No new Qs raised** — Batch 4 reuses Q1 (Database boundary), Q3 (tx_id), Q4 (view shape), Q8 (SavedRule existence), and dependencies on I2 / I11 / I13. **All 5 rows defer**; resolution depends on the layout-decision cluster (A16-A20 internally consistent) being decided as a block, with Q1+Q3+Q8 providing the prerequisite identity + governance decisions. **No implementation paths proposed; current workspace runtime only;Q8 strict framing for A20**. Per audit guardrails all satisfied.

**Phase 3 status after Batch 4**: A1-A20 complete (4 batches × 5 rows). Total Phase 3 distribution (across all 4 batches):
- (a) shipped covers: A4 + A11 (a-items 4/5) + A15 A-runtime/C/E + A16-A + A18-B = 1 row + 8 sub-assertions
- (c) shape conflict: A1, A2-A, A5, A11 (SavedRule), A13-A, A15-B, A16-B, A19, A20 (all 6 sub-items) = 5 rows + 10 sub-assertions
- (d) genuinely new: A3, A6 (A+B), A7 (view filter), A10 (3 fields), A12 (A+B+C), A13-B, A15-F, A17 (A+B+C), A18-A = 1 row + 14 sub-assertions
- (e) deferred-aligned vacuously: A8, A9, A14, A15-D, A7 (routing), A10 (cross-doc) = 4 rows + 2 sub-assertions
- ambiguous-pending-Q: A2-B (folds into Q1)

**8 questions raised across Phase 3 (Q1-Q8)** with structure: Q1-Q5 coherent dependency stack;Q6 + Q7 + Q8 parallel;Q6 contingent on Q8. **No implementation paths anywhere in Phase 3.**

## 5. D-series Deferred Items — Confirmation Shipped Doesn't Accidentally Implement (D1-D10)

Per design doc §17. Audit each: does shipped have anything resembling this that should be flagged?

Trigger conditions verified from design §17 (lines 705-714). Each row confirms whether shipped has an accidental implementation that would violate the deferral.

| # | Deferred item (trigger) | Shipped accidental implementation? (file:line if any) | Confirm deferred? |
|---|---|---|---|
| D1 | persistent named views in Database (用户需要跨 session view registry) | **No** — `_SDKViewsManager` is **in-memory only** (`sdk/store.py:101-179`); explicit code comment at `sdk/store.py:132` documents "not included in `fg.save(...)` workspace persistence". Per A18 (B): in-memory named registry consistent with "PERSISTED registry deferred". | **YES deferred-aligned** — shipped has named view registry but no cross-session persistence. (Note: A18 (B) caveat — a stricter reading of design might consider even in-memory named registry as deferred; not escalated this audit.) |
| D2 | branch / tag / refs (需要 long-lived alternative heads) | **No** — no branch/tag/refs concept anywhere (verified §7 inventory absence across 17 read files;`grep src/factgraph -e "branch\\|tag\\|refs" -r` returns no semantically relevant hits). Per A4 audit: "shipped has no version-control semantics anywhere: no merge / parent-ref / clone / fork." | **YES deferred-aligned** — trivially absent. |
| D3 | writable sub-fg (fork / merge / write-back 语义单独落定) | **No** — no fork/merge/write-back concept anywhere. Per A4: shipped views are subset scope only, not version/branch/working-copy semantics. | **YES deferred-aligned** — trivially absent. |
| D4 | assertion retract / update (需要 deletion / correction semantics) | **PARTIAL — shipped has retract / update at API level**. `retract_by_asrt` (§7.17 `core/evidence/write_protocol.py:170-208`) appends a revocation row via `Ledger.append_revocation`; `replace_field` (`:211-228`) implements retract-old + append-new (correction semantics); SDK `fg.retract(asrt_id, meta)` (§7.12 `sdk/store.py:1886-1909`). Plus revocation-aware read filter `is_active` (§7.16 `core/policy/active.py:6-11`) + `has_active_revocation` (§7.5 `ledger.py`). | **AMBIGUOUS** per A2 (B) split: (i) **strict reading** of D4 (no retract API exists) → shipped EXCEEDS deferral, real conflict; (ii) **loose reading** (no breaking deletion;append-only at SQL level) → shipped ALIGNS (revocation IS append). Disambiguation **folds into Q1** (Database boundary determines whether shipped's `retract_by_asrt` / `replace_field` API stays in the "minimum version" per A2 (B)). |
| D5 | schema migration tx (schema 演进需求明确) | **PARTIAL — shipped has additive schema evolution, NOT migration tx**. `SDKStore.add_schema_classes(*classes)` (`sdk/store.py:1080-1127`) allows incremental entity/field addition with anchor preflight (`_preflight_schema_digest_anchors:2588`) + update (`_update_schema_digest_anchors:2610`); updates `schema_digest`. **Not transactional in Database sense** (no `tx_id` involvement;happens outside any tx envelope). **Additive only**: no breaking-change migration (no field rename, type change, removal). | **YES deferred-aligned for "migration tx"** — shipped's additive evolution is a strict subset of full schema migration semantics; transactional migration with breaking-change support remains deferred. Note: shipped's `add_schema_classes` itself depends on Q1 (tx_id) if the design later requires schema changes to participate in tx envelopes. |
| D6 | materialized derived views (derived fact lifecycle 明确) | **No** — no derived-view materialization anywhere in `core/view/` or `application/`. Distinguish from same-name uses in shipped: `materialize_id` (`core/derivation/accept.py:29`, `core/evidence/write_protocol.py:90`) is **derivation fact provenance**, not view materialization;`materialize_certainty_summary` (`core/store/_certainty_materializer.py:82`) is **audit precompute**, not derived-view persistence;`_materialize_edb_session` (`adapters/pyreason/engine_eval.py:82`) is **PyReason adapter session setup**, not view materialization. None are "materialized derived views" in the database sense. | **YES deferred-aligned** — no derived-view materialization layer in shipped Database/view substrate. |
| D7 | remote database (本地 database semantics 稳定) | **No** — no remote/network concept;`Ledger(path)` accepts only `":memory:"` or local file path (§7.5 `ledger.py:255-279`). No HTTP/RPC/networked storage anywhere. | **YES deferred-aligned** — trivially absent. |
| D8 | multi-db join (单 db snapshot + view scope 稳定后) | **No** — single `SDKStore` per process; no cross-db semantics (no `Ledger.attach_external` or similar); `FactGraph = SDKStore` (§7.12 `sdk/store.py:3432`) instantiates exactly one ledger per instance. | **YES deferred-aligned** — trivially absent. |
| D9 | Rule persistence / SavedRule (需要 rule registry / deployment governance) | **YES — shipped has full SavedRule layer**. Per A11 (c) + A15 (A-persisted) + Q8: `fg.rules.save/load/list/get` (§7.12 `sdk/store.py:2092-2125`) → `application/authoring_runtime.save_rule:54-65` / `save_inference:68-79` → `FileAuthoringRegistry.register_rule_spec` / `register_inference_spec` (`authoring/registry_fs.py:83-118+`). Returned handles `SavedRuleRef(rule_id, version)` (`authoring_runtime.py:20-34`) + `SavedInferenceRef` (`:37-51`) ARE literally the "SavedRule" D9 defers. | **NO — shipped EXCEEDS D9 scope**. Per audit guardrail Q8 strict framing: this is governance-driven, not location-driven. **Defers to Q8** (SavedRule existence governance: hard remove / mark deferred / gradual deprecation). Matches A11 (c) + A20 (A)(B)(C)(D)(F) split. |
| D10 | view set algebra API (Python set op 成为高频痛点) | **No** — no set algebra API on views (no union / intersect / difference / symmetric_difference on `FrozenAssertionView` or `_SDKViewsManager`). Shipped views support: create / update / delete / get / list operations on name → asrt_id set, but NO algebra between views. Users can do Python `set` operations on `view.asrt_ids` externally, but no first-class API. | **YES deferred-aligned** — no view set algebra API surface. Python-side `set` ops on `asrt_ids` are user-level, not a shipped API extension. |

**D-series summary** (10 items):

- **8 items confirmed deferred-aligned** (no shipped accidental implementation): D1, D2, D3, D6, D7, D8, D10. D5 partial (additive-only schema evolution is a strict subset of "schema migration tx"; aligned for the deferred portion).
- **1 item ambiguous, folds into Q1**: D4 (assertion retract / update). Shipped has retract / update at API level (`retract_by_asrt`, `replace_field`, `fg.retract`) but at SQL level revocation IS append-only. Strict vs loose reading of D4 disambiguates via A2 (B) / Q1.
- **1 item exceeds deferral, defers to Q8**: D9 (Rule persistence / SavedRule). Shipped has full SavedRule layer; per audit guardrail Q8 strict framing, this is governance-driven not location-driven. Matches A11 (c) + A15 (A-persisted) + A20 (A)(B)(C)(D)(F).

**No new Qs raised in §5**. D4 reuses Q1;D9 reuses Q8;all other D-items are clean deferred-aligned. Q-state unchanged from Phase 3 closure (8 questions: Q1-Q5 chain + Q6/Q7/Q8 parallel; Q6 contingent on Q8).

**Cross-cutting observation**: the 2 non-clean rows (D4, D9) are both **already known** from Phase 2-3 — they surface here as commitment-level confirmations of A2 (B) ambiguity + A11 (c) / Q8 framing. §5 introduces no new audit findings; it serves as the deferred-list integrity check.

## 6. Cross-doc Seams (§19) — Migration-Blocker Enumeration

Each seam lists: (i) **current shipped status** w.r.t. seam (does it currently work / reject / lack carrier);(ii) **open Qs blocking** (this audit's Q1-Q8);(iii) **upstream design redraft required** in sibling doc before the seam can be specified. **This section does NOT expand evidence-tree or rule-expression design content per audit guardrail**;the sibling-doc redraft references are pointers, not content commitments.

| # | Seam item | Main doc owner | Current shipped status | Blocked-by Q-cluster | Required upstream design closure |
|---|---|---|---|---|---|
| S1 | `fg.eval.evaluate(..., view=...)` from reject → supported | `rule-expression-and-proof-attempt.zh.md` | **Rejected at SDK boundary**: `evaluate()` raises `SDKStoreError("evaluate() does not accept view=; ...")` at `sdk/store.py:2240-2244`. (`fg.run()` also rejects `view=` at `sdk/store.py:1923-1924`, but `fg.run` is an adjacent dispatch surface, not the `evaluate` API itself — included for awareness, not as S1 primary evidence.) No view-scope filter wired below the SDK boundary. | **Q1** (Database boundary determines call-site shape) + **Q4** (FrozenAssertionView shape resolution provides `view=` parameter type) + **Q5** (view ↔ `is_active` composition determines runtime semantics). I7 (d) is the substrate-side mirror. | **Rule-expression doc** evaluate API redraft to incorporate `view=` parameter (existence + type + behavior). Not specified by this audit's scope. |
| S2 | `fg.read.find(..., view=...)` from reject → supported | `rule-expression-and-proof-attempt.zh.md` | **Rejected at SDK boundary**: `fg.read.find()` raises `SDKStoreError("view= is not supported by fg.read.find()")` at `sdk/store.py:1049-1050` (inside `find` defined at `:1039-1057`). No view-scope filter wired below the SDK boundary. | Same as S1 (Q1 + Q4 + Q5). | Same upstream design as S1 — read API redraft (or `application/protocol/entity_read.py` DTO redraft) in sibling doc. Not specified by this audit's scope. |
| S3 | EvaluateResult context adds `db_id/tx_id/schema_digest/data_digest/view_digest` | `rule-expression-and-proof-attempt.zh.md` | **None of the 5 fields exist at evaluate-result level**: per I10 + A10, shipped `SupportArtifact` (§7.15 `_support.py:97-126`) and `ProvenanceEnvelope` (§7.15 `_support.py:147-162`) carry no `db_id` / `tx_id` / `data_digest` / `view_digest`; `schema_digest` exists at 4 other anchors (cross-cutting finding #6) but not at evaluate-result level. **`data_digest`** is a 5th design-side identity field (per design §3 line 103 / §5 line 227 / §6 line 334) — distinct from `tx_id`, derived from assertion-set state. | **Q1** (`db_id`) + **Q3** (`tx_id` formula primitives;`data_digest` formula derives from same DatabaseValue mechanism, currently absent from I-series as standalone but folded into I2 DatabaseValue absence) + **Q4** (`view_digest` formula) + cross-doc dependency on evidence service redraft. | **Rule-expression doc** + **evidence-tree doc** joint redraft of `EvaluateResult` metadata schema. Per Phase B closure memory: evidence service redraft was attempted in Phase C and **deleted** (M-EV 18-file deletion `e9506e42`). **Future redraft must close Q1+Q3+Q4 before specifying `EvaluateResult` metadata shape** — otherwise the metadata fields lack identity sources. |
| S4 | EvidenceGraph.metadata durable copy of S3 fields | `evidence-tree-rainbird-style-v1.zh.md` | **No durable copy mechanism**: shipped has `SupportArtifact` + `ProvenanceEnvelope` in audit/evidence machinery (see §7.15 inventory) but neither carries the 5 S3 fields. Per I10: durable-copy carrier is part of evidence service redraft. | Transitively blocked: S4 depends on S3 closure (cannot durable-copy fields that aren't defined at source). Same Q-cluster (Q1+Q3+Q4) + evidence service redraft. | **Evidence-tree doc** redraft to define EvidenceGraph.metadata field set + durable-copy lifecycle from `EvaluateResult`. Same cross-doc dependency as S3;**S4 cannot be specified before S3 lands**. |
| S5 | failure envelope stale / out-of-scope evidence ref → §13 | `evidence-tree-rainbird-style-v1.zh.md` | **No stale-detection at evidence-ref level**: shipped has no `tx_id` to detect stale-evidence against (per I2 (d));no view scope to detect out-of-scope ref against (per I7 (d)). Failure envelope carrier itself sits in evidence service surface — Phase C implementation attempt was deleted (per Phase B closure record);no shipped carrier exists in current code. | Q1 + Q3 (`tx_id` for stale-detection) + Q4 (`view_digest` for out-of-scope check). Plus this doc's **§13 finalization** (stale / scope 校验 rules) — §13 is in the DB-view doc itself and is referenced by the rule-expression / evidence-tree docs from outside. | **Evidence-tree doc** failure-envelope redraft (carrier shape + the cases §13 specifies) + this doc's §13 finalization. §13 currently describes scope-check intent but doesn't specify the carrier shape — that's an evidence-service-side decision. Per audit guardrail: this row does NOT expand the deleted evidence-tree blueprint content. |
| S6 | `rule_set_digest` evaluate-time computation, attach API unchanged (per A15) | `rule-expression-and-proof-attempt.zh.md` | **`rule_set_digest` literally absent in shipped**: grep-verified 0 hits across `src/factgraph/` (per I12 (C)). **`attach()` API absent**: per I4 (c) + Q2. The seam asserts attach API does NOT change the rule_set_digest contract — but attach API itself is new, so "contract preservation" is forward-looking, not backward. | **Q2** (attach lifecycle: per A15 (D), attach signature contains no `rules=`, but attach itself doesn't exist) + **cross-doc** rule-expression doc `rule_set_digest` formula + this doc's A15 commitment alignment with I12 (C). | **Rule-expression doc** `rule_set_digest` formula specification (which rules participate, what canonicalization, what bytes encoding). Folded with this doc's A15 implementation post-Q2. **S6 cannot ship without both** (i) attach API landing per Q2 + (ii) rule_set_digest formula in sibling doc. |

**S-series summary** (6 seams):

**By Q-cluster dependency** (this audit's open Qs):
- S1 + S2: blocked on **Q1 + Q4 + Q5** (read/eval `view=` parameter)
- S3 + S4: blocked on **Q1 + Q3 + Q4** + evidence service redraft
- S5: blocked on **Q1 + Q3 + Q4** + evidence service redraft + this doc's §13 finalization
- S6: blocked on **Q2** + rule-expression doc rule_set_digest formula + A15 alignment

**By upstream design redraft required**:
- **Rule-expression doc redraft**: S1, S2, S3, S6 (4 of 6 seams). Touches eval API, read API, EvaluateResult metadata, `rule_set_digest` formula. Last-known state: Phase B design closed 2026-05-19; not currently being redrafted.
- **Evidence-tree doc redraft**: S3, S4, S5 (3 of 6 seams). Touches EvaluateResult ↔ EvidenceGraph durable-copy seam, failure envelope. Last-known state per Phase B closure memory: Phase C implementation attempt **deleted** (M-EV 18-file deletion `e9506e42`). Not currently being redrafted.
- **This doc's §13 finalization**: S5 only (stale/scope check rules at carrier level).

**Cross-cutting observation**: **all 6 seams are blocked** — none can be specified without (i) closing Q1-Q8 inside this audit + (ii) at least one sibling-doc redraft. This is not a "stitch the seams" picture;it is a "seams depend on multi-doc redraft alignment" picture. Per audit guardrail: this section does NOT expand evidence-tree or rule-expression design content;the redraft references are pointers, not content commitments.

**Implication for Phase 4c**: S1-S6 will appear in §9 under the **cross-doc blocked** bucket (per Phase 4 reframing). They are not implementable independently of upstream design redraft, regardless of how Q1-Q8 close.

## 7. Shipped Code Surface Inventory

High-density summary of what each primary audit file actually exports + key shapes. Built from full reads (per §2.2 provenance protocol rule 2). Shared reference for §3 / §4 / §5 triage rows.

### 7.1 `core/protocol/digests.py` (17 lines)

Foundational hash helpers used everywhere identity is computed.

- `sha256_hex(data: bytes) -> str` — hex digest
- `sha256_token(data: bytes) -> str` — `"sha256:<hex>"` token form
- `b32_nopad_lower(data: bytes) -> str` — base32 lowercase no-padding, used by idref_v1 encoder

### 7.2 `core/protocol/idref_v1.py` (74 lines)

Canonical entity-ref encoding protocol. Produces opaque idref strings used throughout the SDK + ledger.

- `IDREF_V1_PREFIX = b"factpy\x00idref_v1\x00"` — magic prefix
- `ENTITY_TYPE_RE = r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$"` — entity_type validation
- `canonical_bytes_idref_v1(entity_type, identity_fields: list[(name, type_domain, value)]) -> bytes` — byte-level canonical encoder
- `encode_idref_v1(entity_type, identity_fields) -> str` — returns `"idref_v1:<entity_type>:<base32-sha256>"`
- Uses tup_v1 `encode_value_bytes` + `TAG_CODE_BY_NAME` for per-tag value bytes

### 7.3 `core/protocol/tup_v1.py` (211 lines)

Canonical tuple-encoding protocol — **the authoritative shipped canonicalization for fact terms**.

- `TUP_V1_PREFIX = b"factpy\x00tup_v1\x00"` — magic prefix
- **`CANONICAL_TAGS = ("entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid")`** — 8 tags (the authoritative set; schema_ir.py mirrors)
- `TAG_CODE_BY_NAME` — per-tag byte codes 0x01-0x08
- Per-tag strict encoders (byte form for hashing):
  - `entity_ref` — UTF-8 bytes;must start with `idref_v1:`
  - `string` — UTF-8 bytes
  - `int` — int64 range-checked;canonical ASCII text repr
  - `float64` — 8-byte big-endian IEEE 754;rejects non-finite;normalizes -0.0 → 0.0
  - `bool` — 1-byte 0x00 / 0x01
  - `bytes` — raw bytes(accepts bytes/bytearray/memoryview)
  - `time` — int64 epoch nanos,8-byte BE signed
  - `uuid` — 16-byte from canonical lowercase 8-4-4-4-12 hex
- `canonical_bytes_tup_v1(rest_terms: list[(tag, value)]) -> bytes` — byte encoder for fact tuples
- `claim_args_from_rest_terms(rest_terms) -> list[(idx, val_atom, tag)]` — SQLite storage form (different encoding from hash form):
  - `entity_ref` / `string` → UTF-8 str
  - `int` → int
  - `float64` → `"0x<16hex>"` string(canonical bit form)
  - `bool` → bool
  - `bytes` → **urlsafe base64 nopad str**(different from canonical_meta `_to_jsonable` envelope)
  - `time` → int (epoch nanos)
  - `uuid` → canonical 8-4-4-4-12 str

### 7.4 `core/schema/schema_ir.py` (229 lines)

Schema IR validation + canonical schema digest.

- `CANONICAL_TAGS = {"entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"}` — mirror of tup_v1 CANONICAL_TAGS (set form)
- `REQUIRED_TOP_LEVEL_KEYS = ("schema_ir_version", "entities", "predicates", "projection", "protocol_version", "generated_at")`
- `REQUIRED_PROTOCOL_KEYS = ("idref_v1", "tup_v1", "export_v1")`
- `load_schema_ir(path) -> dict` — file read + validate
- `ensure_schema_ir(schema_ir) -> dict` — full schema validator
- `canonicalize_schema_ir_jcs(schema_ir) -> bytes` — JCS-style canonical bytes(sort_keys + compact separators + ensure_ascii=False);rejects floats anywhere in payload
- **`schema_digest(schema_ir) -> str`** — returns `sha256:<hex>` token form
- Internal validators per top-level key (entities / predicates / projection / protocol_version)

### 7.5 `core/store/ledger.py` (1164 lines)

The shipped persistence layer. SQLite-backed + write-through in-memory indexes.

**5 frozen dataclasses (storage row shapes)**:
- `Claim(asrt_id, pred_id, e_ref, rest_terms: list[(tag, value)])` — **the fact assertion shape**
- `ClaimArg(asrt_id, idx, val_atom, tag)` — per-position decomposition for indexing
- `MetaRow(asrt_id, key, kind, value)` — per-key meta decomposition
- `AnnotationRow(asrt_id, namespace, category, key, kind, value, origin, derivation)` — extended annotations
- `Revokes(revoker_asrt_id, revoked_asrt_id)` — revocation pair
- Plus `Idempotency(ingest_key, on_conflict)` + `AppendResult(asrt_id, written)`

**Constants**:
- `META_KINDS = {"str", "int", "float", "bool", "time", "json"}` — 6 kinds (DIFFERENT from tup_v1 CANONICAL_TAGS;`bytes` is NOT a meta kind — encoded as "json" via `_to_jsonable` envelope)
- `ANNOTATION_ORIGINS = {"observed", "derived"}`
- `ANNOTATION_CATEGORIES = {"source", "semantic", "derived", "operational"}`
- `_JSON_BYTES_KEY = "__factpy_bytes_b64__"` — envelope sentinel

**SQLite tables (6 + 1)**:
- `claims(seq AUTOINCREMENT PK, asrt_id UNIQUE, pred_id, e_ref, rest_terms TEXT)` — rest_terms stored as JSON list of [tag, value]
- `claim_args(id AUTOINCREMENT PK, asrt_id, idx, val_atom TEXT, tag)` — per-position decomposition (redundant with claims.rest_terms;optimized for query)
- `meta_rows(id AUTOINCREMENT PK, asrt_id, key, kind, value TEXT)` — per-key meta
- `revokes(id AUTOINCREMENT PK, revoker_asrt_id, revoked_asrt_id)`
- `ingest_keys(ingest_key PK, asrt_id, kind)` — idempotency dedupe
- `ledger_meta(key PK, value TEXT)` — **lifecycle metadata** (e.g., shipped `schema_digest` lives here)
- `annotation_rows(id AUTOINCREMENT PK, asrt_id, namespace, category, key, kind, value, origin, derivation, UNIQUE(asrt_id, ns, cat, key))`

**Persistence helpers**:
- `_to_jsonable(value)` (line 204) — bytes → `{__factpy_bytes_b64__: <base64>}` envelope;tuple → list;dict → dict;passthrough scalars
- `_from_jsonable(value)` — inverse
- `_enc / _dec` — JSON encode/decode wrappers using `_to_jsonable`
- `_enc_rest_terms / _dec_rest_terms` — list of [tag, jsonable(value)]

**Ledger class API (main entry: `Ledger(path=":memory:")`)**:
- `append_assertion(claim, claim_args, meta_rows, annotation_rows, idempotency, asrt_id)` — main write;**`asrt_id` parameter optional → falls back to `_new_asrt_id() = uuid.uuid4().hex`** (line 1066 — NOT content-addressed)
- `append_revocation(revokes, meta_rows, idempotency, revoker_asrt_id)` — revoke another asrt
- 4 deprecated methods (`append_claim` / `append_claim_args` / `append_meta` / `append_revokes`) — kept for compatibility
- `append_annotations(rows)` — separate annotation path
- `get_claim` / `find_claims(pred_id, e_ref)` / `find_claim_args` / `find_meta` / `find_annotations` / `has_active_revocation` / `find_revoker`
- Properties: `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes`
- **`get_ledger_meta(key) / set_ledger_meta(key, value) / replace_ledger_meta(key, value)`** — for `ledger_meta` table (this is where shipped stashes per-ledger lifecycle metadata,including `schema_digest`)
- Connection management: per-thread for file ledgers (WAL mode), single conn for `:memory:`
- `_write_session()` context manager — `BEGIN IMMEDIATE` + post-commit hooks

**Validation functions (lines 1074-1156)**:
- `_validate_claim_identity`: asrt_id (optional) / pred_id / e_ref must be non-empty str
- `_validate_meta_rows`: kind in META_KINDS (6), key non-empty, asrt_id non-empty
- `_validate_annotation_rows`: origin in ANNOTATION_ORIGINS, category in ANNOTATION_CATEGORIES, kind in META_KINDS, derivation rules
- `_normalize_term(term)`: validates (tag: str, value) tuple — **does NOT validate tag is in CANONICAL_TAGS** (compatibility laxness)

### 7.6 `core/store/runtime.py` (436 lines)

`Store` is the runtime hub. Owns `(schema_ir, ledger)` + per-process engine evaluator registry.

- `register_engine_evaluator(evaluator, name)` / `get_engine_evaluator(name)` — global registry per-engine (`"souffle"`, `"problog"`, `"pyreason"`, `"native"`)
- `Store(schema_ir, ledger, engine_evaluator, artifact_sidecar)`:
  - owns `schema_ir`, `ledger`
  - 6 in-memory indexes: `_support_artifacts / _provenance_envelopes / _candidate_support_index / _candidate_support_kind_index / _candidate_confidence_kind_index / _candidate_pred_index / _rule_trace_artifacts`
  - `_engine_overrides: {mode: evaluator_fn}` — per-Store override
- `evaluate(derivation_id, version, target_pred_id, head_vars, where, mode="native", head, registry, confidence_kind_resolver, engine_ext, engine_options, semantics_profile)` — delegates to `evaluate_store`
- `evaluate_engine(...)` — internal adapter entry (dispatches via `_engine_overrides` → global registry)
- `accept / accept_many` — candidate acceptance into ledger
- `explain_support(support_digest)` / `explain_provenance(support_digest)` / `explain_rule_trace(rule_run_id)` — artifact-based explain readback
- `explain_fact(pred_id, e_ref, *val_atoms)` / `conflicts(pred_id, e_ref)` / `resolve_mapping(pred_id, policy_mode)`
- **No `db_id` / `tx_id` / `view_digest` concept** — Store is process-scoped, not durable identity
- **`evaluate()` signature has no `view=` parameter** — view scope is not a Store-level concept
- Uses `canonical_bytes_tup_v1` + `sha256_token` for `tup_digest` in `evaluate_dummy` (deprecated)
- Support digest validation: `assert support_digest.startswith("sha256:")` throughout

### 7.7 `core/view/projector.py` (200 lines)

**Name-collision warning**: this is **engine fact projection**, NOT design doc's `SubsetView`.

- `ViewProjectionError` exception
- `ProjectorAudit` dataclass — projection statistics (predicate_count / active_claim_count / selected_claim_count / dropped_by_policy_count)
- `_project_view_facts_impl(ledger, schema_ir, audit)` — main projection helper
- `build_args_for_claim(ledger, claim) -> tuple` — **constructs `(e_ref, *val_atoms)` flat tuple** from `Claim.e_ref` + sorted `ClaimArg.val_atom` rows. **This IS the "fact_tuple" shape — just constructed at projection time, not stored as a single shape.**
- `project_view_facts(ledger, schema_ir) -> dict[pred_id, list[tuple]]` — main entry;cardinality-aware:
  - single — uses `compute_chosen_for_predicate` (policy chosen value)
  - multi — uses all active claims
- `project_view_facts_with_witness(ledger, schema_ir) -> dict[pred_id, list[ProjectedFact]]` — projection with asrt_id witness (uses `ProjectedFact(asrt_id, fact_tuple)` from `_support.py`)
- `project_view_facts_with_audit(ledger, schema_ir) -> tuple[..., ProjectorAudit]` — with audit stats
- Active filter: `is_active(ledger, claim.asrt_id)` from `core.policy.active`

### 7.8 `application/workspace_runtime.py` (232 lines)

The shipped workspace persistence layer — Blueprint 3 `level_4` layout.

**Constants**:
- `WORKSPACE_MANIFEST_NAME = "factgraph_workspace.json"`
- `WORKSPACE_VERSION = "1"` (string)
- `WORKSPACE_SAVE_SCOPE = "level_4"`
- `WORKSPACE_LEDGER = "ledger.db"`
- `WORKSPACE_REGISTRY = "registry/"`

**Current shipped layout** (top-level under workspace root):
```
<workspace>/
├── factgraph_workspace.json        # 6-field manifest
├── ledger.db                       # SQLite
└── registry/                       # FileAuthoringRegistry (rules + inferences + schema)
```

**API**:
- `WorkspacePaths(root, manifest, ledger, registry)` — frozen dataclass
- `resolve_workspace_paths(path) -> WorkspacePaths`
- `workspace_manifest_payload(schema_digest, created_at, last_saved_at) -> dict` — 6-field manifest:`{factgraph_workspace_version, save_scope, schema_digest, components.{ledger, registry}, created_at, last_saved_at}`
- `save_workspace_manifest(path, schema_digest) -> dict`
- `validate_workspace_manifest(path, schema_digest=None) -> dict` — checks all 6 fields strictly
- `copy_ledger_to_workspace(ledger, target_path)` — SQLite backup (in-memory checkpoint OR `.backup()` for file)
- `sync_registry_to_workspace(source_registry, target_registry, schema_ir)` — copytree
- `save_workspace(path, schema_digest, ledger, source_registry, schema_ir) -> WorkspacePaths` — main save entry
- `load_workspace(path, schema_digest) -> WorkspacePaths` — main load entry;requires both ledger + registry to exist
- `_load_manifest / _checkpoint_ledger / _now_iso` — helpers

### 7.9 `application/entity_view.py` (569 lines)

Application-layer entity hydration.

- `EntityViewError(ValueError)` — typed error with code/path/details DTO conversion
- `hydrate_entity(e_ref, store, index, include_assertions, include_history) -> EntitySnapshotDTO` — single entity
- `hydrate_entities(e_refs, store, index, ...) -> list[EntitySnapshotDTO]` — batch
- **`execute_read_request(request, store, index) -> EntityReadResponse`** — main read entry (mode="get" / "find")
- Uses `project_view_facts(store.ledger, store.schema_ir)` to materialize fact universe
- `at_time_ns` + `version` request params → **rejected** at execute time:`TEMPORAL_READ_NOT_IMPLEMENTED` / `VERSIONED_READ_NOT_IMPLEMENTED` (line 524-537)
- Internal: `_hydrate_entity_snapshot` / `_recover_entity_ref` / `_recover_identity_from_predicates` / `_rows_to_field_value` / `_hydrate_value` / `_build_field_assertions` / `_assertion_record_from_claim` / `_entity_visible` / `_enumerate_entity_refs` / `_snapshot_matches_filters` / `_validate_filter_paths` (rejects identity-field filters)
- **No `view=` parameter at this layer**

### 7.10 `application/query_runtime.py` (241 lines)

Application-layer query executor.

- `QueryRuntimeError(ValueError)` — typed error
- `execute_query(request, store, index, registry) -> QueryRuntimeResponse` — main entry
- Uses `project_view_facts(store.ledger, store.schema_ir)` + `evaluate_native_where(view_facts, where_ir, registry)` from `core.rules.ruleref_substrate`
- 2 return slot kinds:`"entity"` (hydrates EntitySnapshotDTO via `hydrate_entity`) / `"scalar"` (value passthrough); other kinds → `QUERY_UNSUPPORTED_SLOT`
- Policy handlers: `on_missing` / `on_type_mismatch` ∈ `{"error", "skip", "null"}`
- **No `view=` parameter**

### 7.11 `application/protocol/entity_read.py` (202 lines)

Application protocol DTOs (frozen dataclasses with __post_init__ validation).

- `FieldValue: TypeAlias = JSONValue | EntityRef`
- `FieldValueDTO(field, value_kind ∈ {"scalar", "entity_ref"}, cardinality ∈ {"single", "multi"}, value)`
- **`AssertionRecordDTO(assertion_id, value, active=True, meta={})`** — 4 fields (note: `assertion_id` not `asrt_id`)
- `FieldAssertionsDTO(field, active, history)`
- `EntitySnapshotDTO(ref, fields, assertions, identity_available=True, warnings=())`
- `EntityReadRequest(mode ∈ {"get", "find"}, entity_type, selector, field_filters, limit, include_assertions=False, include_history=False, at_time_ns, version)` — `at_time_ns` and `version` are mutually exclusive but BOTH rejected at execute time
- `EntityReadResponse(mode, entity_type, items, errors, warnings)`

### 7.12 `sdk/store.py` (3432 lines) — `FactGraph = SDKStore`

The user-facing SDK class. Many namespace managers + capability methods. **All `view=` parameters explicitly rejected at SDK boundary**.

**Key shapes**:
- **`FrozenAssertionView(name: str, asrt_ids: frozenset[str])`** (line 88-92) — **only 2 fields**. NOT the 6-anchor design shape (`name / db_id / base_tx_id / schema_digest / asrt_ids / view_digest`).
- 11 namespace managers (all read-only via `FrozenSnapshotError` on `__setattr__`):
  - `_SDKViewsManager`(line 101) — `create / update / delete / get / list`;views stored in dict, **NOT persisted** to workspace (line 132)
  - `_SDKAssertionsManager`(line 182) — graph-scoped assertion access
  - `_SDKSchemaManager` / `_SDKReadManager` / `_SDKWriteManager` / `_SDKRulesManager` / `_SDKInferencesManager` / `_SDKEvalManager` / `_SDKWhatIfManager` (+ 2 sub-managers `_SDKWhatIfFactOverlayManager` / `_SDKWhatIfRuleManager`) / `_SDKAuditManager` / `_SDKPackageManager`

**Constructor / persistence (lines 722-938)**:
- `SDKStore.__init__(classes, store, schema_ir, artifact_store_root, registry_root, registry, workspace_path, default_row_format)`
- `SDKStore.create(schema_classes, ledger, ledger_path, path, artifact_store_root, registry_root, registry, default_row_format)` — main user constructor
- `SDKStore.from_schema_classes(classes, ledger, ledger_path, artifact_store_root, registry_root, registry, default_row_format)` — lower-level
- **`SDKStore.load(path, schema_classes, default_row_format)`**(line 860-895) — validates registry schema digest match (current shipped pattern uses registry digest validation, not pure file)
- `SDKStore.save(path)`(line 2063-2090) — calls `app_save_workspace(workspace_path, schema_digest, ledger, source_registry, schema_ir)`;rebinds `_authoring_registry` to workspace registry path after save (line 2089)

**Public reads / writes**:
- `get(entity_cls, **identity_kwargs)` — delegates to `sdk_get` → `execute_read_request`
- **`find(entity_cls, *, policy, limit, **filter_kwargs)`**(line 1039-1057) — **rejects `view=`** (line 1049-1050:`"view= is not supported by fg.read.find()"`);delegates to `sdk_find`
- `edit(entity_cls, **identity_kwargs)` — delegates to `sdk_edit`
- `ref(entity_cls, **identity_values) -> str` — managed e_ref creation (caches identity in `_identity_values_by_e_ref`)
- `set(field, e_ref, value, meta)` / `add(field, e_ref, value, meta)` — single-cardinality set / multi-cardinality append;both route through `_apply_field_mutation` → `plan_write_command` + `apply_write_plan` (application layer)
- `retract(asrt_id, meta) -> str | None` — delegates to `core.evidence.write_protocol.retract_by_asrt`

**Capability shells (rule-overlay / fact-overlay / proof-frame / why-not / diff)**:
- `check / diagnose / why_not` — direct on `_what_if`
- `check_fact_overlay / recheck_proof_frame` — G2
- `check_rule_disable / check_rule_literal_replace / check_rule_add_condition` — G3
- `diff_proof_frames` — G5 (in `audit` namespace per §5.2.1 placement)

**Run / evaluate / accept**:
- **`run(obj, row_format, policy, view, return_display_meta, registry)`**(line 1911-1938) — **rejects `view=`** (line 1923-1924);dispatch by obj type: Query / Inference (rejected — use evaluate) / Rule
- **`evaluate(*args, **kwargs)`**(line 2240-2307) — **rejects `view=`**(line 2241-2244);rejects `semantics_profile=` in SDK (use `semantics=`);rejects `mode=` in E (use `engine=`);rejects `temporal_view`;handles SDK Inference / authoring derivation dict / compiled plan dict
- `accept(candidate_set, **kwargs) -> AcceptResult` / `accept_many(requests, mode, idempotent_duplicate_ok)`

**Schema lifecycle**:
- `add_schema_classes(*schema_class_args, schema_classes) -> SchemaAddResult` — additive schema mutation;updates ledger_meta `schema_digest` + registry schema entry

**Rule / Inference persistence**:
- `save_rule(rule) -> SavedRuleRef` / `load_rule(rule, version) -> Rule` / `list_rules() -> list[SavedRuleRef]` / `get_rule(rule_id) -> SavedRuleRef`
- `save_inference / load_inference / list_inferences / get_inference`
- All require `_authoring_registry`(`_require_authoring_registry()` raises otherwise)

**Internal helpers**:
- `_compile_rule_input` / `_compile_derivation_input` — author payload normalization
- `_index_schema` / `_refresh_schema_state` / `_preflight_schema_digest_anchors` / `_update_schema_digest_anchors` — schema digest sync across ledger + registry
- `_resolve_public_engine / _resolve_public_semantics / _resolve_public_engine_and_semantics` — engine + semantics dispatch
- `_coerce_sdk_value_to_tag(tag, value)` — strict per-tag value coercion (entity_ref / string / int / bool / bytes / time / uuid / float64)
- `_default_uuid4_for_tag(tag)` — uuid4 factory for uuid / string identity defaults
- `_normalize_view_name / _build_view_entry / _normalize_asrt_ids / _normalize_asrt_ids_from_records` — views helpers
- `_assertion_record_by_id(sdk, asrt_id)` — SDK AssertionRecord lookup
- `_schema_pred_by_pred_id / _schema_pred_for_field / _raise_if_superseded_entity_class / _active_entity_class_for_type`

**Public type alias**: `FactGraph = SDKStore`(line 3432)

### 7.13 `sdk/facade.py` (1150 lines)

SDK-facing entity / assertion / field-editor wrappers.

**Key shapes**:
- `AssertionMeta(source, trace_id, ingested_at, approved_by, note, derived_rule_id, derived_rule_version, candidate_id, candidate_key, candidate_kind, raw)` — typed meta wrapper
- **`AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta: AssertionMeta)`** — **8 fields**;**SDK-level shape**(distinct from `Claim` / `AssertionRecordDTO`)
- `AssertionRecordSet(tuple)` — filter methods: `where(...) / at(t) / version(v) / by_id(asrt_id) / one() / all() / first()`
- `FieldAssertions(field_name, cardinality, active_records, history_records)` — `.active() / .all() / .at(t) / .version(v)`
- `AssertionNamespace(field_map, entity_type)` — `.field(...) / .active() / .all() / .by_id / .by_ids`;`FrozenSnapshotError` on __setattr__
- `EntitySnapshot(ref, entity_type, _field_values, _identity_values, identity_available, assertions: AssertionNamespace)` — `FrozenSnapshotError` on __setattr__
- `FieldEditor / IdentityEditor / EntityEditor` — write-side editor wrappers

**Top-level functions** (used by SDKStore):
- `sdk_get(sdk, entity_cls, **identity_kwargs) -> EntitySnapshot | None` — `execute_read_request` with mode="get"
- `sdk_find(sdk, entity_cls, limit, **filter_kwargs) -> list[EntitySnapshot]`
- `sdk_edit(sdk, entity_cls, **identity_kwargs) -> EntityEditor`

**DTO ↔ SDK converters**:
- `_dto_to_sdk_snapshot(dto, sdk, entity_cls, known_identity_values) -> EntitySnapshot`
- `_dto_assertions_to_sdk(dto, sdk, entity_cls, e_ref) -> FieldAssertions`
- `_dto_assertion_record_to_sdk(dto, sdk, entity_type, field_name, pred_id, e_ref) -> AssertionRecord`
- `_assertion_record_from_claim(sdk, claim, schema_pred) -> AssertionRecord` (line 988-1003) — bridges shipped `Claim` → SDK `AssertionRecord`

**Time / version helpers** (SDK-level, NOT supported in application layer):
- `_validate_iso8601_text / _is_valid_iso8601_text / _validate_version_selector`
- `_is_assertion_visible_at / _read_assertion_time_meta / _read_assertion_version` — uses `meta.raw["valid_from"]` / `meta.raw["valid_to"]` / `meta.raw["version"]`

### 7.14 `sdk/query_runtime.py` (297 lines)

SDK-level query plan executor.

- `execute_query_plan(sdk, plan, registry) -> list[Any]` — main entry
- Lowers via `core.rules.rule_ast.lower_query_rule_ast_to_ir`
- Delegates to `application.query_runtime.execute_query`
- Maps application `QueryRuntimeResponse.rows` → SDK row format (dict / instance mode);uses `_dto_to_sdk_snapshot` from facade
- Internal: `_build_app_slot` / `_parse_field_path` / `_primary_entity_type` / `_sdk_error_from_app_dto` / `_sdk_path_from_app_path` / `_map_app_row_to_sdk_row` / `_ensure_query_field_assertions` / `_dedup_rows` / `_rows_to_instances` / `_row_dedup_key` / `_to_hashable` / `_entity_cls_for_type` / `_entity_field_specs_for_type`
- **No `view=` parameter**

### 7.15 `core/store/_support.py` (424 lines)

Support/provenance DTOs and digest helpers used by evaluate/explain support artifacts.

- `ProjectedFact(asrt_id, fact_tuple)` — witness row shape returned by `project_view_facts_with_witness(...)`; validates non-empty `asrt_id` + tuple `fact_tuple`
- `PredWitness(pred_atom_key, asrt_ids)` — sorted unique assertion ids for a predicate atom
- `NonFactStep(step_key, kind, status, details)` — non-fact support steps
- `RuleRefEdge(...)` — rule-ref edge support with `child_support_digest` or unresolved reason
- `SupportArtifact(kind, root_result_kind, binding_items, pred_witnesses, non_fact_steps, rule_refs, rule_ref_edges)` — canonical support artifact
- `BindingSupportCapture(binding_items, support_digest, support_kind)` — binding/digest capture
- `ProvenanceEnvelope(candidate_id, engine, payload_type, payload)` — engine provenance wrapper
- `support_artifact_to_dict/from_dict`, `support_artifact_bytes`, `compute_support_digest`
- `provenance_envelope_to_dict/from_dict`, `provenance_envelope_bytes`, `compute_provenance_digest`
- Bytes encoding here is **hex envelope**: `_to_jsonable(bytes) -> {"__bytes_hex__": value.hex()}`. This is distinct from ledger meta bytes envelope and tup_v1 raw/urlsafe bytes paths.

### 7.16 `core/policy/active.py` (11 lines)

Tiny policy helper defining shipped "active assertion" semantics.

- `is_active(ledger, asrt_id) -> bool` — validates `Ledger` + non-empty `asrt_id`, then returns `not ledger.has_active_revocation(asrt_id)`
- Active universe is therefore revocation-aware. It is not a database snapshot/version concept.

### 7.17 `core/evidence/write_protocol.py` (526 lines)

Shipped write protocol used by SDK `set` / `add` / `retract`. Despite module name `core.evidence`, this is the current application write substrate.

- `new_assertion_id() -> str` — `uuid4().hex`; another shipped non-content-addressed assertion-id generator
- `now_epoch_nanos() -> int`
- `set_field(ledger, pred_id, e_ref, rest_terms, meta) -> str` — validates inputs, computes an `ingest_key`, then writes a new assertion through `Ledger.append_assertion(...)`
- `add_field(...) -> str` — alias to `set_field`
- `retract_by_asrt(ledger, revoked_asrt_id, meta) -> str | None` — append-only retraction path. If a revoker already exists, returns it; otherwise creates a revocation row via `Ledger.append_revocation(...)`
- `replace_field(...) -> tuple[str | None, str]` — retract old active matching claim, then write new assertion
- `_validate_write_inputs(...)` — validates `pred_id`, `e_ref`, and `rest_terms` using `canonical_bytes_tup_v1(rest_terms)`, so fact-term validation is already based on shipped tup_v1
- `_compute_ingest_key(...) -> sha256:<hex>` — content-addressed idempotency key over `"ingest_key_v2"`, pred_id, e_ref, rest_terms, source material, and temporal material. **This is not `asrt_id`**.
- `_KEY_KIND_MAP` + `_infer_meta_kind` define user/system meta kind handling; user meta values are limited to str/int/float/bool/time/json-like paths depending on key/value

---

### Cross-cutting findings

**1. Four `AssertionRecord`-like shapes coexist**:
| Layer | File | Shape | Fields |
|---|---|---|---|
| Storage row | ledger.py | `Claim` | 4: asrt_id / pred_id / e_ref / rest_terms |
| Application DTO | application/protocol/entity_read.py | `AssertionRecordDTO` | 4: assertion_id / value / active / meta |
| SDK ergonomic | sdk/facade.py | `AssertionRecord` | 8: asrt_id / value / is_active / entity_type / field_name / pred_id / e_ref / meta |
| Design doc §5.4 | (design doc only) | `AssertionRecord` | 7: asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta |

Field naming inconsistent: `asrt_id` vs `assertion_id`, `active` vs `is_active`.

**2. Four bytes encodings coexist**:
| Encoding | Used by | Form |
|---|---|---|
| Raw bytes (for hashing) | `tup_v1.encode_value_bytes(tag="bytes", v)` | passthrough bytes |
| Urlsafe base64 nopad | `tup_v1._val_atom_for_claim_arg(tag="bytes", v)` (SQLite storage) | str |
| Envelope `{__factpy_bytes_b64__: <std-base64>}` | `ledger._to_jsonable` (meta_rows storage) | dict |
| Envelope `{__bytes_hex__: <hex>}` | `_support._to_jsonable` (support/provenance artifacts) | dict |

**3. `view=` rejected at 3 SDK boundaries**:
- `find()` line 1049 — `view= is not supported by fg.read.find()`
- `run()` line 1923 — `view= is not supported by fg.run()`
- `evaluate()` line 2241 — `evaluate() does not accept view=`

Design doc §12 wants `view=` supported at these sites. This is a (c) shape conflict at API surface.

**4. "view" name collision**:
- `core/view/projector.py` `view` = engine fact projection (`project_view_facts`)
- `sdk/store.py` `FrozenAssertionView` + `_SDKViewsManager` = named asrt_id subsets
- Design `SubsetView` / `FrozenAssertionView` = 6-field anchored view with view_digest

Three distinct meanings of "view" in shipped + design.

**5. `asrt_id` generation is uuid-based, not content-addressed**:
- `_new_asrt_id() = uuid.uuid4().hex` (ledger.py line 1066) — fallback when caller doesn't provide
- No content-addressed `asrt_id` formula shipped
- No `db_id` / `tx_id` concept

**6. `schema_digest` lives in `ledger_meta(key="schema_digest", value=...)` SQLite table**:
- Shipped pattern uses `ledger.set_ledger_meta / replace_ledger_meta` for schema digest persistence
- Workspace manifest also carries schema_digest as a 2nd anchor (double-write)
- Registry also carries schema digest (3rd anchor) — `_preflight_schema_digest_anchors` checks all 3 match before schema mutation

**7. `FrozenAssertionView` shipped vs design — 2 fields vs 6 fields**:
- Shipped: `(name, asrt_ids)`
- Design: `(name, db_id, base_tx_id, schema_digest, asrt_ids, view_digest)`
- Major shape conflict;design adds 4 identity anchors absent in shipped

## 8. Open Questions for User

Questions surface here as audit rows are filled. Each one blocks (or constrains) downstream triage and ultimately Phase 4 recommendations.

### Q1 — `Database` class concept: new layer, rename, or drop? (raised by I1)

Shipped `Ledger` (§7.5) is the primary high-level write boundary at the SQLite layer (with additional low-level / deprecated entries + lifecycle-meta writes — see I1). No `Database` class concept exists. Three resolution options visible from I1 triage:

- (a) **`Database` is a new layer above `Ledger`** — adds `db_id` / `tx_id` / `commit_assertions(...)` API on top of existing ledger. Implementation cost: significant (new API surface + identity wiring + boundary tightening from current multi-method shape to single-commit shape).
- (b) **Doc revision maps the `Database` concept to the existing `Ledger` boundary** — keep shipped `Ledger` code as-is (no code rename), accept that `Ledger` is the boundary the design called `Database`. Add `db_id` / `tx_id` on top if needed by other commitments. Avoids implying a code rename of `Ledger`; only the design vocabulary is reconciled.
- (c) **Drop `Database` from design** — accept shipped `Ledger` boundary + multi-path write surface as final; revise design doc to remove the `Database` term and revise I1 / I2 / I4 accordingly.

This question blocks Phase 4 recommendations for I1 + I2 + I4.

### Q2 — `FactGraph.attach(db)`: new lifecycle or rename of `SDKStore.load(...)`? (raised by I4)

Shipped has `SDKStore.create / from_schema_classes / load`. No `attach(db)`. Two resolution options:

- (a) **`attach(db)` is a new lifecycle distinct from constructors** — caller first creates / opens a `Database`, then calls `fg.attach(db)` to bind runtime. Lifecycle: `Database` is decoupled from runtime; multiple `FactGraph` instances can attach to the same `db`.
- (b) **`attach(db)` is a rename of `SDKStore.load(path, schema_classes)`** — same lifecycle, different name. `Database` is just storage; `attach` just opens it.

Choice (a) requires solving the question of when/how a `Database` is created independently of `FactGraph`, and what "same db" semantics across multiple FactGraph instances means. Choice (b) is simpler but loses the design intent of separating `Database` from runtime.

This question blocks Phase 4 recommendations for I4 + I5 + I6.

### Q3 — Where does `tx_id` content-addressed formula get its primitives? (raised by I2)

Shipped has `sha256_token` (§7.1) + `canonical_bytes_tup_v1` (§7.3) as **foundational primitives** that a `tx_id` formula could reuse.

**Crucially, `_compute_ingest_key` (§7.17 `write_protocol.py:318`) is NOT a candidate template for `tx_id`** — its canonical payload includes ingest-side idempotency material (`source`, `source_loc`, `trace_id`, `valid_from`, `valid_to`, `version` — `write_protocol.py:324-368`), not transaction-snapshot material. Treating `ingest_key` as a `tx_id` template would conflate two distinct semantics (ingest dedup vs snapshot identity).

Two design-level decisions:

- (a) **Reuse shipped primitives only** — build `tx_id` from `sha256_token(canonical_bytes_tup_v1(...))` with a domain-separation marker (e.g., first term `("string", "tx_v1")` as sentinel inside the tuple, or a fresh `tx_v1` prefix string-prepended to the canonical bytes). Tx payload would carry tx-relevant material (e.g., `parent_tx_id + sorted(asrt_id_set) + schema_digest`). Reuses primitives, **does NOT reuse `_compute_ingest_key`'s payload shape**.
- (b) **Define a separate `tx_v1` canonical byte protocol** — analogous to `tup_v1_PREFIX = b"factpy\x00tup_v1\x00"` (§7.3) / `IDREF_V1_PREFIX = b"factpy\x00idref_v1\x00"` (§7.2), introduce `tx_v1_PREFIX = b"factpy\x00tx_v1\x00"` with its own byte encoding rules. Cleanest separation but adds a new protocol module in `core/protocol/`.

Both options explicitly **reject reusing `_compute_ingest_key` as-is** because of payload-semantics mismatch. Cross-cuts I2 + I10 + I11.

### Q4 — `FrozenAssertionView` collision: how to resolve 2-field vs 6-field? (raised by I3)

Shipped `FrozenAssertionView(name, asrt_ids)` is a working SDK feature with shipped `fg.views.create/update/delete/get/list` API (§7.12 `_SDKViewsManager:101-179`). Design wants 6-field `(name, db_id, base_tx_id, schema_digest, asrt_ids, view_digest)`. Three options:

- (a) **Reuse shipped 2-field shape** — drop `db_id / base_tx_id / schema_digest / view_digest` from design. Lowest cost; loses the view-anchor integrity check.
- (b) **Rename design's shape** (e.g., `AnchoredAssertionView`) — both shipped and design coexist. Cost: term proliferation; users see two view types.
- (c) **Breaking migration of shipped** — shipped 2-field shape is upgraded to 6-field. Cost: invalidates existing `fg.views.create(name, asrt_ids=...)` callers + needs `db_id / base_tx_id / schema_digest` to be populated (which depends on I2).

Cross-cuts I3 + I6 + I7. Decision blocked on I2.

### Q5 — How does `view=` scope filter compose with `is_active` revocation filter? (raised by I7, reinforced by I8)

Shipped `is_active(ledger, asrt_id)` (§7.16 `core/policy/active.py:6-11`) is a revocation-aware universe selector used by `project_view_facts` (§7.7 `core/view/projector.py:55-58`). Design's `view=` scope adds a caller-specified `view.asrt_ids` subset filter on top. Their composition is unspecified in design:

- (a) **Intersection** — visible = `view.asrt_ids ∩ is_active(...)`. Revoked assertions in `view.asrt_ids` become invisible at read time. Side effect: same view can produce different visible sets at different times (revocation state mutates) — clashes with `view_digest` immutability intent in I3.
- (b) **View-replaces-active** — visible = `view.asrt_ids` as-is, regardless of current revocation state. Caller is responsible for revocation policy at view-creation time. Consistent with `view_digest` immutability (the view captures a frozen snapshot of intended visibility).
- (c) **Caller-side responsibility** — `view.asrt_ids` is taken as-is at runtime; runtime intersects with the asrt_id set without consulting `is_active`. Indistinguishable from (b) at runtime; differs only in whose responsibility it is to pre-filter for revocation.

Option (b) is most consistent with the "view_digest immutable" intent in I3 — view_digest stability requires the visible set to be stable, which (a) violates by re-evaluating `is_active` at read time. Option (a) is most consistent with the shipped revocation model. Option (c) defers the design question rather than answering it.

Cross-cuts I3 + I7 + I8 + I10. Affects whether `view_digest` depends on as-of revocation state at view-creation time, or whether revocation is an orthogonal read-time concern.

### Q6 — Migration strategy: how to remove registry-in-workspace coupling while preserving existing authoring APIs? (raised by I12; reinforced by A15)

**The design prohibition is established, not in question.** Design A15 (§18 of `database-view-fg-layered-architecture.zh.md`) states: "rules 是 code artifact, v1 不进 workspace" — this is a strict prohibition (rules-as-code), not "optional decoupling". I12 (E) confirmed shipped default behavior violates this constraint: `_resolve_workspace_constructor_paths` (§7.12 `sdk/store.py:667-695`) auto-derives `registry_root = workspace_path / "registry/"` when only `path=` is set; `save_workspace` (§7.8 `workspace_runtime.py:160-177`) copies rules into `<workspace>/registry/`;`SDKStore.save()` rebinds `_authoring_registry` to `paths.registry` after persistence (§7.12 `sdk/store.py:2063-2090`). The `registry_root=` parameter is a per-caller workaround, NOT compliance.

**Audit-side resolution is therefore about MIGRATION STRATEGY** (how to bring shipped behavior into compliance), not whether to prohibit:

- (a) **Hard cutover** — next release removes `_resolve_workspace_constructor_paths` auto-derivation; `FactGraph.create(path=...)` no longer creates `<workspace>/registry/`; existing callers who relied on default registry persistence must pass explicit `registry_root=`. Cleanest semantic result; **breaks existing callers** who rely on workspace-as-bundle semantics; needs release-note migration guidance.
- (b) **Gradual deprecation** — emit `DeprecationWarning` when auto-derivation triggers; preserve current behavior for grace period (one or two releases); remove auto-derivation after deprecation window. Lower disruption, longer cleanup tail.
- (c) **Stratified storage** — workspace continues to hold non-rule data (`db/`, `views/` per design layout I13) but explicitly excludes `registry/`; legacy `workspace/registry/` becomes migration-on-load (rules read from existing location at load time, but new saves route to external `registry_root=`). Preserves backward compatibility for read; new writes comply.

These are migration mechanics options. The design constraint (strict prohibition) is NOT in question; only the path to compliance is.

Cross-cuts I12 (E) + I13 (workspace layout migration overall). **Q6 is independent of Q1-Q5** — it touches rule persistence governance, not db/view substrate. Its resolution can proceed in parallel with Q1-Q5.

**Q6 is contingent on Q8** (added 2026-05-20 alongside A11 revision): Q6 asks where the authoring registry lives **assuming the registry exists**. Q8 (below) asks whether `FileAuthoringRegistry` / `SavedRule` should exist at all per A20's literal "rules 留在用户 Python 代码". If Q8 resolution removes `SavedRule`, Q6 becomes vacuous (no registry to relocate); if Q8 resolution keeps `SavedRule`, Q6 still applies (where the registry root sits).

### Q7 — `AssertionRecord` shape reconciliation: 4 shapes coexist (raised by A13, surfaces Phase 2 cross-cutting finding #1)

Shipped has **3 distinct `AssertionRecord`-like shapes**, none matching design's 7-field spec:

- `Claim(asrt_id, pred_id, e_ref, rest_terms)` — §7.5 `ledger.py:21-26`, 4 fields, storage row shape
- `AssertionRecordDTO(assertion_id, value, active, meta)` — §7.11 `application/protocol/entity_read.py:60-72`, 4 fields, application read DTO (note: field name `assertion_id`, not `asrt_id`)
- SDK `AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta)` — §7.13 `sdk/facade.py:87-96`, 8 fields, public SDK return shape

Design (A13): `AssertionRecord(asrt_id, pred_id, fact_tuple, schema_digest, assertion_digest, tx_id, meta)` — 7 fields. The design `fact_tuple` is a flat positional tuple combining shipped's `e_ref + rest_terms`; design `schema_digest / assertion_digest / tx_id` all depend on I2 + I11 (all currently (d) genuinely new).

Three resolution options:

- (a) **Adopt design 7-field shape across all 3 layers** — replace `Claim` storage row + `AssertionRecordDTO` + SDK `AssertionRecord` with design shape. Cost: breaking change at 3 layers; need to flatten `e_ref + rest_terms` → `fact_tuple` semantics; depends on Q3 (`assertion_digest` / `tx_id` formula) + I2 resolution. Cleanest semantic result;largest implementation surface.
- (b) **Keep shipped 3-layer separation, revise design to acknowledge layers** — design doc revised so `AssertionRecord` is understood as a **layered concept**: storage row = `Claim`, app DTO = `AssertionRecordDTO`, SDK surface = `AssertionRecord`. Each layer carries the appropriate field subset. Design's 7-field spec becomes a logical view rather than a single physical shape. Cost: design doc revision;preserves shipped surface;loses single-shape simplicity.
- (c) **Add design 7-field shape as a new fourth layer (logical/durable record)** — shipped 3 layers remain;design `AssertionRecord` becomes a new derivation (e.g., logical durable record materialized at evidence/audit time) carrying the 4 anchor fields (`schema_digest / assertion_digest / tx_id / meta`) on top of shipped storage. Cost: additional layer + reconciliation rules between 4 layers; aligned with shipped + design but **risk of multi-shape proliferation** is exactly the pattern Phase C tried and failed (`fact_tuple` over-introduction).

Sub-question for any option: **what is the canonical bytes encoding for `fact_tuple`** (design intent) vs `claim_args_from_rest_terms` (shipped SQLite storage form, §7.3 `tup_v1.py:246`) vs `canonical_bytes_tup_v1` (shipped canonical bytes for hashing)? The design `fact_tuple` shape implicitly takes a position on which encoding is canonical; shipped maintains a deliberate split between hash-form (`canonical_bytes_tup_v1`) and storage-form (`claim_args_from_rest_terms`).

Cross-cuts A13 + Phase 2 cross-cutting finding #1 + Q3 (digest primitives). **Q7 is independent of Q1-Q5 chain** — like Q6, it touches a different concern (record-shape reconciliation, not db/view substrate identity). Q7 and Q6 can proceed in parallel.

### Q8 — `SavedRule` persistence governance: should `FileAuthoringRegistry` / `SavedRule` exist at all in v1? (raised by A11 (c) Rule persistence + A15 (A-persisted))

Shipped has a **full SavedRule persistence layer**:

- SDK surface: `fg.rules.save(...)` (§7.12 `sdk/store.py:2092-2103`), `load_rule` / `list_rules` / `get_rule` (`sdk/store.py:2105-2125`), parallel `fg.inferences.save/load/list/get` (`sdk/store.py:2127-2160`).
- Application boundary: `application/authoring_runtime.save_rule(registry, rule_payload, schema_ir=...)` (`authoring_runtime.py:54-65`) + `save_inference` (`authoring_runtime.py:68-79`).
- Persistence: `FileAuthoringRegistry.register_rule_spec(...)` / `register_inference_spec(...)` — file-backed registry at `paths.registry`.
- Returned handles: `SavedRuleRef(rule_id, version)` (`authoring_runtime.py:20-34`) + `SavedInferenceRef(inference_id, version)` (`authoring_runtime.py:37-51`) — these dataclasses ARE literally the "SavedRule" the design defers.

Design position (verified literal references):

- §3 cross-cut table (line 73): "Rule persistence / SavedRule registry → Rules 先保持 code artifact;Database 只持事实和 schema anchor"
- §17 D9 (line 713): "Rule persistence / SavedRule → 需要 rule registry / deployment governance" (deferred-trigger condition; absent in v1)
- §18 A11 (line 730): "Rule persistence 全部 deferred"
- §18 A20 (line 739): "rules 留在用户 Python 代码"

Joint literal reading: v1 should expose **no `SavedRule` / no `FileAuthoringRegistry` / no `fg.rules.save(...)` persistence surface**. Rules live in user-imported Python modules (constructed via SDK `Rule(...)` / `Inference(...)`), reach the runtime via `evaluate(...)` / `_register_rule_dependencies` (in-memory `RuleRegistry`), and are never persisted by the SDK itself.

Three resolution options:

- (a) **Hard remove `SavedRule` layer** — drop `fg.rules.save / load / list / get` + `fg.inferences.save / load / list / get` + `FileAuthoringRegistry` + `SavedRuleRef` / `SavedInferenceRef` from public SDK. Keep only runtime-construction path (`Rule(...)` / `Inference(...)` in user code → `evaluate(...)`). Cleanest semantic alignment with A20 literal reading; **breaks shipped SDK contract** at multiple surface points; needs release-note migration guide (callers must move rules into Python modules / source-control).
- (b) **Mark deferred + keep shipped API as-is** — keep `fg.rules.save/...` shipped, document in release notes "SavedRule exceeds v1 design intent per D9 — slated for removal in vNext"; no breaking change in current release. Preserves shipped contract; **defers the strictness mismatch** rather than resolving it; design doc and shipped surface remain divergent.
- (c) **Gradual deprecation** — emit `DeprecationWarning` from `fg.rules.save/...` calls; preserve current behavior for one or two releases; remove after deprecation window. Lower disruption than (a);longer cleanup tail;intermediate between (a) and (b).

Sub-question for any option: how does Q8 interact with shipped's `FileAuthoringRegistry`-backed `_authoring_apply_events.jsonl` audit log + `registry_manifest.json` snapshot (mentioned in A20 line 739 as items to remove)? These are downstream artifacts of the same persistence layer; their fate follows Q8 outcome.

Cross-cuts A11 (c) + A15 (A-persisted) + I12 + Q6 (Q6 is **contingent on Q8** — Q6 vacuous if Q8 = (a)). **Q8 is independent of Q1-Q5 chain + Q7** — it touches a separate governance concern. Q8 + Q6 + Q7 are all parallel to each other and to Q1-Q5.

### Cross-cutting observation (not a question)

Q1-Q5 form a coherent dependency stack rather than 5 independent decisions. Resolution order is forced by data dependency: **Q1 (Database class) → Q3 (tx_id primitives) → Q2 (attach lifecycle) → Q4 (FrozenAssertionView shape) → Q5 (view ↔ is_active composition)**. **Q6 + Q7 + Q8 are all parallel** to the Q1-Q5 chain and to each other, with one inter-Q dependency: **Q6 is contingent on Q8** (Q6 = where the authoring registry lives, assuming it exists; Q8 = whether the registry should exist at all). **Q6** (registry-in-workspace migration) — touches rules governance location, not db/view substrate; design prohibition established per A15 strict prohibition, only migration mechanics remain open; vacuous if Q8 = (a). **Q7** (AssertionRecord shape reconciliation) — touches record-shape layering, not db/view substrate identity or rules governance. **Q8** (SavedRule existence governance) — touches whether shipped's SavedRule persistence layer should exist at all per A11 + A20 + D9 joint literal reading; precedes Q6. Until Q1-Q5 are answered (Q6 + Q7 + Q8 separately, with Q6 contingent on Q8), I1-I13 cannot move past **(c) shape conflict** / **(d) genuinely new** / **(e) deferred-aligned** classification into concrete implementation recommendations.

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
