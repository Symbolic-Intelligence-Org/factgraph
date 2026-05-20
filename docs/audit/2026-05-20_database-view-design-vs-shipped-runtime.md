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
| I12 | `FactGraph.attach(...)` 签名不包含 `rules=`;rule set 通过 `Expr / Inference` 内部引用承载,evaluate 时计算 `rule_set_digest`;rules 不进 Database transaction、不进 workspace v1 | Five sub-assertions, verified separately. **(A) attach signature has no `rules=`**: `FactGraph.attach(...)` does not exist (per I4 (c)). No shipped function has `rules=` in any constructor parameter list — verified by §7.12 reading of `SDKStore.__init__` (`sdk/store.py:722-733`) / `create` (`:783-833`) / `from_schema_classes` (`:837-857`) / `load` (`:860-895`). Vacuously aligned by absence of `attach()`. **(B) rule set carried via `Expr / Inference` internal references**: SDK has `Rule` / `Inference` objects (§7.12 referenced via `_compile_rule_input` / `_compile_derivation_input`). Dependency mechanism shipped: `_register_rule_dependencies` (§7.12 `sdk/store.py:2421-2451`) iterates `rule.dependency_rules()` and registers them into a `RuleRegistry` (imported from `core.rules.rule_ir`); `_resolve_runtime_registry` (`:2453-2468`) builds the registry from object dependencies. Detailed Rule / RuleRef shape lives in `rule-expression-and-proof-attempt.zh.md` — **secondary surface per §1, not audited in this round**. **(C) evaluate-time `rule_set_digest` computation**: **grep `src/factgraph/` for `rule_set_digest` returns 0 matches** (verified during Batch 3 prep). No shipped code computes or stores `rule_set_digest`. `_KEY_KIND_MAP` (§7.17 `write_protocol.py:57-91`) and `_SENSITIVE_SEMANTIC_META_KEYS` (§7.17 `write_protocol.py:41-56`) include `schema_digest` and `policy_digest` but NOT `rule_set_digest`. **(D) rules not in Database transaction**: shipped rules are persisted via `FileAuthoringRegistry` (§7.12 `sdk/store.py:save_rule:2092` / `load_rule:2105` / `list_rules:2113` / `get_rule:2120`), which calls `app_save_rule / app_load_rule` from `application.authoring_runtime`. Rules are NOT written via `Ledger.append_assertion / append_revocation / append_*` — verified by reading §7.5 `Ledger` API. **(E) rules not in workspace v1**: **partially false on default behavior**. `_resolve_workspace_constructor_paths` (§7.12 `sdk/store.py:667-695`) auto-derives `registry_root = workspace_path / "registry/"` when `path=` is set without explicit `registry_root=` (lines 678-679 + 692-693). `save_workspace` (§7.8 `workspace_runtime.py:160-177`) calls `sync_registry_to_workspace` which **copies rules into `<workspace>/registry/`** by default. The CAPABILITY for decoupled registry exists (caller passes explicit `registry_root=`), but **default behavior couples rules to workspace tree**. | Split classification by sub-assertion. **(A) (e) deferred-aligned vacuously** — depends on I4. **(B) (a) shipped covers in spirit** — RuleRegistry + `dependency_rules()` mechanism carries rule references through SDK Rule/Inference objects;exact-shape comparison vs design wording requires rule-expression doc audit (secondary surface, not in this round). **(C) (d) genuinely new** — `rule_set_digest` literally absent from shipped (grep-verified). **(D) (a) shipped covers** — rules path goes to FileAuthoringRegistry, never to Ledger; rules-not-in-ledger is a behavioral fact shipped today. **(E) (c) shape conflict on default** + **(a) capability exists** — `registry_root=` can decouple, but default auto-couples. | medium (mostly aligned; (C) is new but constrained to evidence/evaluate seam already deferred via I10; (E) is a default-behavior decision, not an architectural gap) | split: **(A)** confirm in I4 / Q2 acceptance gate. **(B)** confirm against rule-expression doc when that doc is audited (out of scope this round). **(C)** defer — `rule_set_digest` is a new metadata field whose placement is part of evidence service redraft (cross-cuts I10). **(D)** accept as **(a)** — shipped aligned. **(E)** doc revision needed: clarify whether "rules 不进 workspace v1" is (a) capability-only (shipped already covers) or (b) default-must-not-couple (shipped default would need change) or (c) strict prohibition. See §8 Q6. |
| I13 | Workspace 物理布局:`db/objects/` content-addressed write-once + `db/refs/` 唯一 mutable pointers + `db/assertions.db` SQLite index layer;views 同模式 | **Current shipped workspace layout** (per §7.8 `workspace_runtime.py:15-19` constants + `:27-32` `WorkspacePaths` + `:160-177` `save_workspace` + §7.12 `sdk/store.py:667-695` `_resolve_workspace_constructor_paths`): top-level `<workspace>/factgraph_workspace.json` (6-field manifest: `factgraph_workspace_version="1"`, `save_scope="level_4"`, `schema_digest`, `components`, `created_at`, `last_saved_at`) + `<workspace>/ledger.db` (SQLite primary storage) + `<workspace>/registry/` (FileAuthoringRegistry: rules + inferences + schema). **No `db/` subdirectory** anywhere in shipped layout. **No `objects/` content-addressed write-once** subdirectory. **No `refs/` mutable pointers** subdirectory. **`ledger.db` is the primary source-of-truth**, not a rebuildable index layer — there is no `tx/` log from which `ledger.db` could be reconstructed because no transaction object directory exists. **Views layout**: `FrozenAssertionView` (§7.12 `sdk/store.py:88-92`) is **in-memory only**, stored in `_SDKViewsManager._views` dict (`sdk/store.py:101-179`); explicit code comment at `sdk/store.py:132` documents views "not included in `fg.save(...)` workspace persistence". **No views directory in shipped workspace**. | **(c) shape conflict** for workspace top-level layout — fundamentally different organization (`db/` Git-style content-addressed vs current `ledger.db` + `registry/` flat). **(d) genuinely new** for `db/objects/` content-addressed write-once + `db/refs/` mutable pointers — semantics absent in shipped. **(d) genuinely new** for `db/assertions.db` as rebuildable index layer — shipped `ledger.db` is primary source not derivable from any object log. **(d) genuinely new** for views persistence — shipped views are in-memory dict only, with explicit "not persisted" code comment. | high (entire physical layout reorganization;cross-cuts save/load contract;needs migration story for existing workspaces) | defer — blocked on Q1 (Database class boundary determines if `db/` subdirectory exists at all), Q3 (`tx_id` formula determines what goes in `db/objects/tx/<tx_id>.json`), Q4 (view shape determines if/how `views/objects/<view_digest>.json` is keyed). Migration path from current `level_4` layout to Git-style layout is a separate design phase, not part of this audit. **Per audit guardrail, NOT citing rolled-back DB.1 implementation as evidence** — DB.1 attempted this layout, was abandoned in Phase C rollback (2026-05-20), is not in the audit branch's worktree, and would not be evidence for shipped state regardless. |

**I1-I5 cross-cutting observation** (informational, not a triage decision):

I1-I5 are not 5 independent invariants — they form a coherent "missing Database / Snapshot / Attach layer" stack. I1 introduces the `Database` class concept; I2 introduces `DatabaseValue` immutable snapshot identified by `db_id + tx_id`; I3 anchors `FrozenAssertionView` to `db_id + base_tx_id + schema_digest + view_digest` (3 of 4 anchors flow from I1+I2); I4 introduces `attach()` lifecycle that binds runtime to `Database`; I5 introduces `as_of(tx_id)` snapshot read on top of I2+I4. Of the 5 rows: **2 are (d) genuinely new** (I2, I5) and **3 are (c) shape conflict** (I1, I3, I4). Implementation order is forced: I2 must land before I3 / I5; I4 must land before I5 / I6.

**I6-I9 cross-cutting observation** (informational, not a triage decision):

I6-I9 form the "view scope behavior" sub-stack on top of I3-I5's "Database / Snapshot / Attach" stack. I6 = attach-with-view lifecycle; I7 = view filter semantics on read/eval/explain; I8 = absent-view full-universe routing; I9 = no-silent-fallback acceptance guarantee. Of the 4 rows: **2 are (d) genuinely new** (I6, I7) and **2 are (e) deferred-aligned** (I8, I9 — vacuously satisfied today because the scoped runtime substrate doesn't exist). I9 is specifically a future acceptance gate, not an implementable invariant; it can only be exercised after I6 lands. The shipped adjacency `is_active(ledger, asrt_id)` (§7.16) is the closest universe-selector mechanism but it has different semantics (revocation-aware) than design's view.asrt_ids filter; the composition between the two is unspecified in design (see Q5). The pattern across I3-I9 is consistent: shipped has neither the substrate (Database / DatabaseValue / Attach) nor the surface (view= filter) for the design's view-scoped runtime model.

**I10 cross-cutting observation** (informational, not a triage decision):

I10 was deliberately split into its own batch (2b, separate from I6-I9 in batch 2a) because it is a **cross-doc seam**, not a view-scope behavior. The contract spans two sources: DB/view runtime (producer of `db_id` / `tx_id` / `schema_digest` / `view_digest`) and evidence/evaluate service (consumer of these fields as result-level metadata). DB/view runtime cannot resolve I10 unilaterally: the **consumer side is itself undefined** today — the evidence service blueprint was deleted during Phase C rollback (2026-05-20) and is pending fresh redraft based on current Rule design. The 4 shipped evaluate-result / evidence-graph shapes (`CandidateSet`, `SupportArtifact`, `ProvenanceEnvelope`, plus per-assertion `meta_rows`) carry none of the 4 design-required fields at the evaluate-result level; `schema_digest` is the only one shipped, but at 4 other anchors (ledger_meta + workspace manifest + registry + per-assertion meta), not at the evaluate-result location. I10 is the audit-row that most clearly demonstrates the I-series limitation: design specifies a multi-party contract whose other party (evidence service) is currently not represented by any binding artifact in the repository. Until the evidence service is redrafted with explicit metadata-consumer shape, I10 cannot move past **(c)/(d)** classification regardless of how Q1-Q5 are resolved.

**I11-I13 cross-cutting observation** (informational, not a triage decision):

I11-I13 are not concept-level claims (those were I1-I10) but **specific behavioral / placement / physical layout assertions**. Pattern across the three rows: shipped frequently has **adjacent mechanisms or partial alignment** that are NOT partial implementations: `ledger_meta` for I11 (storage shape exists, no `db_id` usage); `sha256_token` + `canonical_bytes_tup_v1` + `_compute_ingest_key` for I11 (cross-process sha256 primitives exist, no `tx_id` formula); `FileAuthoringRegistry` for I12 (D) (rules persistence path exists and is decoupled from ledger);`_resolve_workspace_constructor_paths` for I12 (E) (decoupled-registry capability exists, default behavior couples). I12 is the most heterogeneous row in Phase 2 — its 5 sub-assertions span all classifications: (A) (e), (B) (a), (C) (d), (D) (a), (E) (c)+(a). I13 is the row most clearly affected by the abandoned Phase C work — but per audit guardrail, **rolled-back implementation work is NOT cited as shipped evidence**; only the current Phase B baseline + master state counts.

## 4. A-series Commitments Triage (A1-A20)

| # | Doc commitment | Shipped equivalent (file:line) | Classification | Risk | Recommendation |
|---|---|---|---|---|---|
| A1 | 最小架构只引入 `Database` / `DatabaseValue` / `SubsetView` / `FactGraph runtime` 四个核心概念 | A1 is a **design-side scope claim** ("design introduces only these 4 concepts at the public conceptual surface"), not a behavioral assertion about shipped. Verification: design doc §3 / §5-§9 indeed restricts itself to these 4 concepts at the conceptual layer (cross-doc seams §14 / §19 acknowledge evidence and rule docs separately). Mapping to shipped: **`Database` → no class, role played by `Ledger`** (per I1 (c)); **`DatabaseValue` → no equivalent** (per I2 (d)); **`SubsetView`/`FrozenAssertionView` → `FrozenAssertionView` shipped at §7.12 `sdk/store.py:88-92` with 2 fields** (per I3 (c)); **`FactGraph runtime` → `FactGraph = SDKStore`** alias at §7.12 `sdk/store.py:3432` (per I4 (c)). Shipped also exposes many **implementation-layer concepts** not in the 4-concept list (`Store`, `Claim`, `ClaimArg`, `MetaRow`, `AnnotationRow`, `Revokes`, `Idempotency`, `RuleRegistry`, `FileAuthoringRegistry`, `_SDKViewsManager`, `SupportArtifact`, `ProvenanceEnvelope`, `ProjectorAudit`, ...) — but these are below the public conceptual surface. | **(c) shape conflict** on the 4-concept mapping (all 4 mismatch per I1-I4); the scope claim itself is satisfied at the public-surface level — design does NOT introduce additional public concepts beyond the 4. Implementation will require the implementation-layer concepts shipped today to remain (Claim, ClaimArg, etc.), which is consistent with A1's "minimum public surface" intent. | low (A1 itself is informational); each of the 4 concepts carries individual risk per I1-I4 | confirm during Q1 + Q2 + Q4 resolution that the 4 public concepts remain stable post-resolution; do NOT treat A1 as requiring implementation surgery — the per-concept work is in I1-I4 + A2-A5. |
| A2 | `Database` 是唯一持久写入点;最小版本只 append assertions | Two sub-assertions, verified separately. **(A) `Database` sole-writer**: mirrors I1 — Ledger is primary high-level write boundary but exposes multiple write methods (high-level `append_assertion / append_revocation`, low-level deprecated `append_claim / append_claim_args / append_meta / append_revokes`, lifecycle-meta `set_ledger_meta / replace_ledger_meta`, annotation-only `append_annotations`); not a single `commit_assertions(...)` boundary. **(B) "minimum version only append assertions"**: **shipped already exposes retract**. `retract_by_asrt` (§7.17 `write_protocol.py:170-208`) appends a revocation row via `Ledger.append_revocation` (§7.5 `ledger.py:453`); `replace_field` (§7.17 `write_protocol.py:211-228`) = retract-old + append-new. SDK `fg.retract(asrt_id, meta)` (§7.12 `sdk/store.py:1886-1909`) routes to `retract_by_asrt`. At SQL level revocation IS append (new `revokes` row added), but at API level it is a distinct **retraction operation** with its own entry point. | Split classification. **(A) (c) shape conflict** via I1. **(B) ambiguous**: depends on whether design's "只 append assertions" is (i) **strict at API level** (no retract method; only `commit_assertions`-equivalent) — then shipped exceeds minimum scope; or (ii) **loose at SQL level** (any append-only write including revocation rows) — then shipped aligns. Design doesn't disambiguate. | medium | clarify A2 (B) intent: (i) strict means shipped's `retract_by_asrt` / `replace_field` exceed "minimum version" and the question becomes whether to remove them when implementing `Database` (likely undesirable — they are shipped SDK contract); (ii) loose means shipped aligns with A2 (B) as-is. Folds into Q1 (Database class boundary): the boundary decision implicitly defines what's "in the minimum version". |
| A3 | `DatabaseValue` immutable,由稳定 `db_id` + content-addressed `tx_id` 定位;`tx_id` 不得由 UUID / 自增序号充当 durable identity | Mirrors I2 + adds **explicit `tx_id` prohibition**: must NOT be UUID, must NOT be auto-increment. Shipped state: no `DatabaseValue` (per I2 (d)); no `db_id` (per I2 (d)); no `tx_id` (per I2 (d)). **Shipped's anti-pattern uses are present**: `asrt_id` uses `uuid.uuid4().hex` (§7.5 `ledger.py:1066` + §7.17 `write_protocol.py:120-121` — both call sites); SQLite `claims` table uses `seq INTEGER PRIMARY KEY AUTOINCREMENT` (§7.5 `ledger.py:81-88`, line 83). The prohibition explicitly rules out these two patterns as `tx_id` templates. | **(d) genuinely new** mirroring I2 + adds **explicit no-shortcut prohibition**. The prohibition strengthens Q3 framing: shipped's UUID-based `asrt_id` is NOT a candidate `tx_id` template (already excluded by Q3 (a)/(b) framing per Batch 1 fix). Shipped's AUTOINCREMENT `seq` is similarly excluded. | high (cross-process identity contract per I2 + I11) | defer — blocked on Q3 (`tx_id` formula). Reinforces Q3 resolution: both options (a) primitives-only with domain separation and (b) separate `tx_v1` protocol satisfy A3 prohibition; UUID/auto-increment shortcuts are off the table by design. |
| A4 | `SubsetView`/`FrozenAssertionView` 是 subset scope,不是 version / branch / working copy | Negative claim — view is NOT version / branch / working-copy. Shipped state: `FrozenAssertionView(name, asrt_ids)` (§7.12 `sdk/store.py:88-92`) is a named assertion-id subset stored in `_SDKViewsManager._views` dict (§7.12 `sdk/store.py:101-179`). **Shipped has no version-control semantics anywhere**: no merge / parent-ref / clone / fork. **Shipped has no write semantics on views**: `_SDKViewsManager.create/update/delete/get/list` operate on the asrt_id set itself (per `sdk/store.py:121-179`); the view is not a write target. Per design `§17` deferred list, `branch / tag / refs` and `writable sub-fg` are explicitly future-deferred, consistent with A4's negative claim. | **(a) shipped covers** — semantically aligned: shipped views are subset scope, NOT version/branch/working-copy. Important caveat: this alignment is partly **trivial-by-absence** (shipped has no version/branch concept anywhere to confuse with). If design later introduces branch/version (per §17 deferred), shipped's view would need to remain explicitly differentiated; today no conflict exists. | low | confirm in Q4 (FrozenAssertionView shape resolution) that whichever shape is chosen (2-field reuse / 6-field new / breaking migration) preserves A4's "not version/branch/working-copy" semantic. Independent of the field-count decision in Q4. |
| A5 | `FrozenAssertionView` 必带 `db_id / base_tx_id / schema_digest / view_digest` | Direct specification of the 4 anchor fields. Mirrors I3 exactly. Shipped state: `FrozenAssertionView(name, asrt_ids: frozenset[str])` (§7.12 `sdk/store.py:88-92`) has **only 2 fields**; **all 4 design-required anchors are absent**: no `db_id` (depends on I2 (d)), no `base_tx_id` (depends on I2 (d)), no `schema_digest` (shipped at 4 other anchors per cross-cutting finding #6 but NOT on `FrozenAssertionView`), no `view_digest` (no derivation formula shipped, per cross-cutting finding #7). `_SDKViewsManager` stores entries by `name` only in an in-memory dict (`sdk/store.py:101-179`); no anchor-field validation exists. | **(c) shape conflict** mirroring I3. The conflict is concrete: design requires 4 specific anchor fields; shipped has 0 of 4 on the view. 3 of 4 anchor sources (`db_id`, `base_tx_id`, `view_digest`) depend on I2 (d); 1 of 4 (`schema_digest`) exists at 4 other anchor points but not on the view. | medium-high | doc revision via Q4. Per Q4 resolution: (a) reuse 2-field shape requires design doc revision to drop the 4-anchor requirement;(b) rename design's shape allows shipped 2-field to coexist;(c) breaking migration requires implementing the 4-field shape (blocked on I2). A5 cannot stand independent of Q4 — its 4 required fields ARE the Q4 (c) shape. |
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

**A1-A5 cross-cutting observation** (informational, not a triage decision):

A1-A5 cover the **foundation-layer commitments** (Database / DatabaseValue / view shape). They mostly mirror Phase 2 I-rows but with **commitment-specific extensions**:

- **A1** is meta — the "only 4 concepts" scope claim itself is satisfied by design wording; the per-concept mapping all maps to I1-I4 conflicts.
- **A2** is the most heterogeneous A-row in this batch: (A) inherits I1's (c); (B) raises a **design ambiguity** about whether "minimum version only append assertions" is strict-API or loose-SQL. If strict, shipped exceeds minimum scope (already has `retract_by_asrt` / `replace_field`); the disambiguation folds into Q1.
- **A3** adds an **explicit prohibition** beyond I2: tx_id MUST NOT be UUID or auto-increment. This reinforces Q3 (a)/(b) framing — UUID-based `asrt_id` (shipped) is ruled out as tx_id template by design fiat.
- **A4** is the rare **(a) shipped covers** row — alignment is partly trivial-by-absence (no version/branch concept to confuse with) but the negative claim does hold today.
- **A5** is the concrete spelling-out of I3's 4 anchor fields; cannot be evaluated independently of Q4.

Batch 1 classification distribution: **(a) shipped covers: 1** (A4); **(c) shape conflict: 3** (A1, A2-A, A5); **(d) genuinely new: 1** (A3); **ambiguous-pending-Q: 1** (A2-B folds into Q1). All 5 rows defer / doc-revise / confirm-during-Qx;no implementation paths proposed.

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

### Q6 — Default registry placement: workspace-coupled or decoupled? (raised by I12)

Shipped `_resolve_workspace_constructor_paths` (§7.12 `sdk/store.py:667-695`) auto-derives `registry_root = workspace_path / "registry/"` when only `path=` is set without explicit `registry_root=`. `save_workspace` (§7.8 `workspace_runtime.py:160-177`) then calls `sync_registry_to_workspace` which copies rules into `<workspace>/registry/`. The CAPABILITY for decoupled registry exists (caller passes explicit `registry_root=` to a path outside workspace), but the **default behavior couples rules to workspace tree**.

Design I12 (E) asserts "rules 不进 workspace v1". Three resolution options:

- (a) **Capability-only interpretation** — design's "rules 不进 workspace v1" means "the registry CAN live outside the workspace; design does not require workspace-coupling". Shipped already covers this via `registry_root=` parameter. **No default behavior change required.**
- (b) **Default-decoupled interpretation** — design requires the DEFAULT behavior to place rules outside the workspace tree. Shipped current default (auto-derive `<workspace>/registry/`) would need to change. Side-effect: `FactGraph.create(path=...)` ergonomics change — users would have to pass `registry_root=` explicitly to persist rules.
- (c) **Strict prohibition** — rules NEVER inside workspace tree regardless of caller intent. `registry_root=` would need to validate it doesn't point inside `path=`. Most restrictive.

Cross-cuts I12 (E) + I13 (physical layout) + future workspace migration path. **Q6 is independent of Q1-Q5** — it touches a separate sub-system (rule persistence governance vs db/view substrate). Its resolution can proceed in parallel with Q1-Q5.

### Cross-cutting observation (not a question)

Q1-Q5 form a coherent dependency stack rather than 5 independent decisions. Resolution order is forced by data dependency: **Q1 (Database class) → Q3 (tx_id primitives) → Q2 (attach lifecycle) → Q4 (FrozenAssertionView shape) → Q5 (view ↔ is_active composition)**. **Q6 (registry placement) is parallel** and independent of this chain. Until Q1-Q6 are answered, I1-I13 cannot move past **(c) shape conflict** / **(d) genuinely new** / **(e) deferred-aligned** classification into concrete implementation recommendations.

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
