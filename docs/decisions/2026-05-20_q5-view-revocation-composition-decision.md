# Q5 Decision: View Scope vs Revocation Composition

- Status: proposed for user review
- Created: 2026-05-20
- Branch: `v0.1-q5-view-revocation-composition-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q2-attach-lifecycle-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md`
  - `docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_audit_execution_discipline.md`
- Scope: resolve audit Q5 — how `view=` scope composes with shipped `is_active(...)` / revocation filter. Cover both `view=` specified and `view=` omitted cases. Lock the visibility semantics that downstream evidence / evaluate work can rely on.
- Non-scope: Q4 view DTO shape (closed), `view=` API signature on read/eval/explain (cross-doc: rule-expression doc redraft S1/S2), evidence/evaluate metadata field encoding (cross-doc: S3/S4/I10), failure envelope shape (cross-doc: S5), Q6 registry migration.

## 1. Decision

Q5 chooses **option (b) — View-replaces-active**.

The composition rule is **case-split** by whether `view=` is specified, and is stated at the **scope universe** layer:

| Case | Scope universe | Revocation filter applied to scope universe? |
|---|---|---|
| `view=` specified | exactly `view.asrt_ids` (frozen at view creation) | **no** — revocation does NOT re-filter the scope universe at read time |
| `view=` omitted (default) | snapshot's active-only assertion universe | **yes** — shipped `is_active(...)` filter preserved |

Rationale in one sentence: Q4 locked `view_digest` immutability over `sorted(asrt_ids)`;option (a) "intersection at read time" would re-evaluate visibility against mutable revocation state and break that immutability;option (b) preserves it by treating `view.asrt_ids` as the caller's frozen visibility commitment.

The default (no `view=`) case retains shipped revocation semantics so that existing read paths continue to behave as today.

**Scope universe vs projection policies**: Q5 locks the scope universe rule above. It does NOT lock projection / materialization policies that operate WITHIN the scope (e.g., shipped single-cardinality chosen-claim policy via `compute_chosen_for_predicate`). Such post-scope policies are blueprint-level (see §2.4), MUST NOT modify `view_digest`, and MUST NOT redefine the scope universe.

## 2. Visibility Semantics Per Case

### 2.1 `view=` specified — scope universe is exactly `view.asrt_ids`

When a caller passes `view=view` to `fg.read.find(..., view=view)` / `fg.eval.evaluate(..., view=view)` OR has an attached view-scoped runtime per Q2 `FactGraph.attach(db, view=view)`, OR invokes an explain path that consumes a view-scoped `EvaluateResult` (e.g., `result.explain(row)` per design §12.2):

- The **scope universe** is exactly `view.asrt_ids`.
- Revocation state of any individual `asrt_id` in `view.asrt_ids` does NOT subtract it from the scope universe.
- Phase 2 atom replay (per design §12.2) only evaluates within `view.asrt_ids`.
- NAF / absence reasons (per design §12.2) get `search_scope` = the view scope, not the full active universe.

This honors Q4 §2.6 + criterion 8: `view_digest` is computed once from `sorted(asrt_ids)` and must remain stable;allowing revocation to subtract members from the scope universe at read time would mutate the effective scope across calls without changing `view_digest`, violating reproducibility.

(For projection / materialization policies that may operate WITHIN this scope universe — e.g., shipped single-cardinality chosen-claim policy — see §2.4.)

### 2.2 `view=` omitted — visible set is active-only snapshot universe

When no `view=` is specified and the runtime is attached via Q2 base form `FactGraph.attach(db)`:

- Visible = `{asrt_id ∈ snapshot_universe : is_active(ledger, asrt_id)}`.
- This preserves shipped behavior: `project_view_facts` (`src/factgraph/core/view/projector.py:55-58` and `:183-187`) already filters with `is_active` per shipped policy `core/policy/active.py:6-11`.
- `is_active(asrt_id) = not has_active_revocation(asrt_id)` per shipped `core/policy/active.py:11`.

This case is the design's "full assertion universe" (design §12.1 line 544) interpreted in the way that matches shipped runtime. The audit A7 row had flagged this universe definition as `(c) latent shape conflict`;Q5 closes that ambiguity by adopting the shipped active-only semantics for the default case.

### 2.3 Revoked assertion inside a specified `view`

If a caller-specified `view.asrt_ids` contains an `asrt_id` that becomes revoked after view creation:

- The asrt remains in the view's scope universe (per §2.1).
- Design §13 validation table at line 581-588 does NOT include a "all view asrts must be `is_active`" check. It only requires `view.asrt_ids` to **exist** in the base snapshot (`ViewAssertionMissingError`). The absence of an active-state check in §13 is design's implicit position;Q5 surfaces that implicit position as the explicit rule "view asrts may be revoked at runtime and remain in the scope universe". (The §13 absence is not itself an explicit prohibition;Q5 makes the boundary explicit by surfacing the implication.)
- Whether evidence / explain output should annotate the revocation state of asrts inside a view is **cross-doc work** (evidence-tree redraft territory, per audit S3 / S4 / S5 / I10). Q5 does not specify evidence annotation.
- The caller's view-creation-time decision (which asrts to freeze into the view) is the contract;runtime does not second-guess it.

This is the explicit "caller owns view semantics" interpretation. Combined with Q4's view_digest immutability, it produces the consistent picture: a view is a caller-pinned visibility commitment;revocation is a separate runtime concept that does NOT mutate that commitment.

### 2.4 Scope universe vs projection / materialization policies

Q5 locks the **scope universe** (which assertions are in-scope for the view-attached runtime, per §1 + §2.1). It does NOT lock projection / materialization policies that operate **within** the scope universe.

Shipped example: `compute_chosen_for_predicate` for `cardinality="single"` predicates (`src/factgraph/core/view/projector.py:64-74, :189-197`). Today this single-cardinality chosen-claim policy is applied AFTER active-filter universe selection — among active claims for a single-cardinality predicate, only one is "chosen" as the output fact.

Per-case behavior under Q5:

- For `view=` omitted: shipped behavior unchanged. Active-filter universe selection happens at the universe layer;single-cardinality chosen-claim policy applies as a post-universe projection. Q5 does not change this sequence.
- For `view=` specified: blueprint must decide whether single-cardinality chosen-claim policy applies WITHIN `view.asrt_ids` (subset projection that selects a subset of view asrts as output facts), OR is bypassed entirely (since the caller explicitly chose which asrts to include). **Q5 does not lock either path.**

**Invariants future blueprints must preserve when adding projection / materialization policies that operate within view scope**:

1. The scope universe for `view=` specified MUST remain exactly `view.asrt_ids`. Projection policies select output from this scope;they do not redefine it.
2. Projection / materialization policies MUST NOT modify `view_digest`. `view_digest` reflects scope (the input asrt_id set), not output (the materialized facts).
3. If a blueprint adds a policy that effectively narrows what asrts produce output facts, the blueprint must make explicit that this is a post-scope projection, NOT a change to the view's scope universe.

These invariants resolve the apparent tension between "engine sees the full view scope" (§2.1) and "engine may filter via cardinality policy before output" (this section): the cardinality policy is a projection LAYER on top of the scope universe, not a redefinition of it.

### 2.5 Read / eval / explain — same composition rule

The §2.1 + §2.2 rules apply uniformly to:

- `fg.read.find(..., view=view)` — read path
- `fg.eval.evaluate(..., view=view)` — evaluate path
- Explain paths that consume a view-scoped `EvaluateResult` — e.g., `result.explain(row)` per design §12.2. The explain SDK surface itself remains cross-doc redraft territory (audit S3 / S4 / S5);Q5 only commits to: whichever explain surface consumes a view-scoped `EvaluateResult` MUST use the same scope universe as the producing evaluate call.

This uniformity is required for evidence reproducibility: the same `view_digest` must produce the same scope universe across all surfaces that consume it.

## 3. Rejected Alternatives

### 3.1 Option (a) — Intersection at read time

Rejected.

Pattern: visible = `view.asrt_ids ∩ is_active(...)` evaluated at every read.

Reason: this violates Q4's `view_digest` immutability. `view_digest` is computed from `sorted(asrt_ids)` (per Q4 §2.6 + design §5.3 line 247-253). Under option (a), the effective visible set changes whenever any asrt in `view.asrt_ids` is revoked or un-revoked, but `view_digest` does NOT change because the input set is unchanged. The pair (`view_digest`, visible set) becomes non-deterministic across time, breaking reproducibility.

Per `feedback_audit_execution_discipline` Rule 2: Q5 must not soften Q4's strict `view_digest` immutability to accommodate shipped's revocation-aware reads. The `view_digest` immutability is a design invariant locked by Q4;Q5 cannot break it.

Audit §8 Q5 itself flagged this conflict: "Option (a) ... clashes with `view_digest` immutability intent in I3."

### 3.2 Option (c) — Caller-side responsibility (deferring the design question)

Rejected.

Pattern: `view.asrt_ids` is taken as-is at runtime;runtime does not consult `is_active`;caller is responsible for pre-filtering at view-creation time but the design says nothing about runtime semantics.

Reason: option (c) is **runtime-indistinguishable from option (b)**. The difference is only in whose responsibility it is to think about revocation at view-creation time. As a design decision, option (c) is a non-decision — it defers the question rather than answering it.

Q5 picks option (b) so the design has an explicit statement of runtime semantics: "view-specified visibility is exactly `view.asrt_ids`, revocation does not re-filter". Callers can then make informed decisions about whether to pre-filter at view-creation. Option (c)'s "defer the question" is incompatible with the audit's goal of closing Q5 as a load-bearing decision.

## 4. Supporting Evidence

### 4.1 Design references

- §12.1 lines 537-544 (默认全集): "未指定 view 时,使用 attached `DatabaseValue` 的 full assertion universe". Q5 §2.2 interprets "full assertion universe" as the shipped active-only universe to preserve runtime behavior.
- §12.2 lines 546-558 (指定 view): "engine 只看到 `view.asrt_ids`" (engine sees only `view.asrt_ids`) + "Phase 2 atom replay 只在 `view.asrt_ids` 内求值" + "NAF / absence reason 的 `search_scope` 必须标识为该 view scope" + "evidence metadata 记录 `view_digest`". This is the literal basis for §2.1.
- §13 lines 581-588 (校验表): 5 validation checks, NONE of which require `view.asrt_ids` to all be `is_active`. This is the design's implicit position that view asrts may be revoked. Q5 §2.3 makes this explicit.
- §13 line 589: "禁止 silent fallback 到 full universe" — Q5 honors this by NOT silently widening view scope on validation failure or revocation;the scope universe strictly remains `view.asrt_ids` regardless of post-creation revocation state.

### 4.2 Shipped revocation surface

- `core/policy/active.py:6-11`: `is_active(ledger, asrt_id) = not ledger.has_active_revocation(asrt_id)`. Pure function over ledger state.
- `core/store/ledger.py:704` `has_active_revocation(revoked_asrt_id)`: checks revoker rows.
- `core/view/projector.py:55-58` (within `project_view_facts`): filters claims by `is_active` before cardinality policy.
- `core/view/projector.py:183-187` (within `_select_view_claims`): same `is_active` filter pattern.

Shipped applies `is_active` at read time for the default (no-view) case. Q5 §2.2 keeps this behavior.

### 4.3 Q4 view_digest immutability constraint

- Q4 §2.6: `view_digest = sha256:<hex>` over `subset-view-v1 + db_id + base_tx_id + schema_digest + sorted(asrt_ids)`.
- Q4 §6.3: "Q4 locks the view identity set (`view.asrt_ids`) and its immutable `view_digest`. It does not decide how runtime read/evaluate/explain visibility composes `view.asrt_ids` with shipped `is_active(...)` / revocation behavior. That remains Q5."
- Q4 criterion 8: "Do keep Q5 open: do not decide active-only vs all-asserted visibility in Q4."

Q5 picks the option that preserves Q4's immutability — namely option (b).

### 4.4 Audit Q5 enumeration

Audit §8 Q5 (lines 714-724) enumerates 3 options. The audit itself notes: "Option (b) is most consistent with the 'view_digest immutable' intent in I3 — view_digest stability requires the visible set to be stable, which (a) violates by re-evaluating `is_active` at read time."

Q5 adopts the audit's own assessment.

## 5. Consequences

### 5.1 Q1 unaffected

Q1 governs Database boundary. Q5 governs view scope composition. Orthogonal.

### 5.2 Q2 view-scoped attach is consistent with Q5

Q2 §2.5 + §6.2 locked that `FactGraph.attach(db, view=view)` materializes `view.base_tx_id` and runs read-only. Q5 §2.1 specifies the scope universe inside that runtime: exactly `view.asrt_ids`, no `is_active` re-filtering at the scope layer. Q2 + Q5 jointly specify the view-scoped runtime scope semantics. Post-scope projection / materialization policies (§2.4) are blueprint-level and orthogonal to Q2.

### 5.3 Q3 unaffected

Q3 governs transaction / data identity primitives. Q5 governs view visibility runtime semantics. Orthogonal.

### 5.4 Q4 view_digest immutability preserved

Q5 explicitly honors Q4's `view_digest` immutability constraint as the primary reason for picking option (b). No Q4 reopen.

### 5.5 Q6 unaffected

Q6 governs registry-in-workspace migration. Q5 governs view runtime visibility. Orthogonal.

### 5.6 Q7 unaffected

Q7 governs assertion record shape. Q5 governs view visibility. Orthogonal. `view.asrt_ids` contains assertion ids whose canonical form is Q3/Q7 territory.

### 5.7 Q8 unaffected

Q8 governs SavedRule persistence. Q5 governs view visibility. Orthogonal.

### 5.8 Evidence / evaluate metadata cross-doc work clarified

Q5 specifies the visibility rule but leaves evidence handling of revoked-in-view assertions to cross-doc redraft (audit S3 / S4 / S5 / I10):

- Whether `EvaluateResult` / `EvidenceGraph.metadata` records per-assertion revocation state at evaluate time is **rule-expression + evidence-tree redraft territory**.
- Whether `failure_class="stale_evidence_ref"` or similar applies when a `result.explain(row)` references an asrt that was revoked after view creation is **evidence-tree failure envelope redraft territory** (per audit S5 + design §13 line 591-593).

Q5 commits to: runtime visibility = `view.asrt_ids`. Evidence-level annotation of revocation state is a separate concern.

### 5.9 A7 audit row partially resolved

Audit A7 row classified the "full assertion universe" definition as `(c) latent shape conflict`. Q5 §2.2 resolves: "full assertion universe" for the no-view case = shipped active-only universe (`is_active`-filtered). The latent conflict is closed.

### 5.10 §13 validation rules confirmed unchanged

Q5 does NOT modify design §13's 5-validation table. The composition rule operates AFTER §13 validation passes:

1. §13 validates view is structurally valid against the base snapshot (db_id / base_tx_id / schema_digest / asrt_ids existence / no scope conflict)
2. Q5 scope universe rule applies during read/eval/explain: scope universe = `view.asrt_ids` (no `is_active` re-filter at the scope layer);post-scope projection policies operate within that universe per §2.4

§13's "禁止 silent fallback" rule remains unchanged — failures raise typed errors per the table.

## 6. Acceptance Criteria For This Decision

Future Q5-dependent blueprints must obey:

1. Do treat `view=` specified **scope universe** as exactly `view.asrt_ids`. Do NOT subtract revoked assertions from the scope universe at read / eval / explain time.
2. Do preserve shipped `is_active(...)` filtering for the `view=` omitted (default) case at read / eval / explain time.
3. Do apply this scope universe rule uniformly across `fg.read.find(..., view=view)`, `fg.eval.evaluate(..., view=view)`, explain paths that consume a view-scoped `EvaluateResult` (e.g., `result.explain(row)`), AND `FactGraph.attach(db, view=view)`-rooted runtimes (per Q2). Do NOT lock a specific `fg.eval.explain(..., view=...)` SDK surface in Q5 — explain surface design is cross-doc redraft territory (S3/S4/S5).
4. Do NOT silently fall back to a wider universe on revocation OR on §13 validation failure. §13 failures raise typed errors;Q5 visibility rule applies AFTER §13 passes.
5. Do NOT reinterpret `view.asrt_ids` as "asrts currently active that the caller selected at view-creation". `view.asrt_ids` is a frozen identity-id set; revocation state at view-creation time is the caller's responsibility, not a runtime invariant.
6. Do NOT add an "all view asrts must be `is_active`" check to design §13. Design §13 does not include this check;Q5 does not add it.
7. Do leave evidence / evaluate annotation of revoked-in-view asrts to cross-doc redraft (S3 / S4 / S5 / I10). Q5 does not specify evidence-level revocation annotation.
8. Do leave the interaction between view scope and single-cardinality chosen-claim policy (`compute_chosen_for_predicate`) to blueprint-level work. Q5 only locks the active-filter composition.
9. Do NOT use Q5 as cover for design-time pre-filtering of revoked asrts during view creation. Q5 explicitly does not require this. Callers may choose to pre-filter at view creation, but design does not mandate it.
10. Do preserve Q4 `view_digest` immutability as the primary invariant — any future revision that introduces revocation-aware view visibility MUST be a Q4 + Q5 joint revision, not a Q5-only revision.

## 7. Decision Record

Q5 resolution: **View-replaces-active (option (b))**, case-split by `view=` presence.

| Case | Visible set | `is_active` applied? |
|---|---|---|
| `view=` specified | `view.asrt_ids` (frozen at creation) | no |
| `view=` omitted | snapshot active-only universe | yes (shipped behavior) |

Rationale: Q4 locked `view_digest` immutability over `sorted(asrt_ids)`. Option (a) intersection at read time mutates effective scope universe without mutating `view_digest`, breaking reproducibility. Option (b) preserves `view_digest` immutability and matches design §12 + §13 (whose validation table does NOT include an active-state check on view asrts;Q5 surfaces this absence as an explicit "view asrts may be revoked at runtime and remain in scope" rule). Option (c) is runtime-indistinguishable from (b) but defers the design question;Q5 picks (b) for explicitness.

Revoked-in-view asrts remain visible inside the view scope per the design's §13 validation table (which does NOT require `is_active`). Evidence-level annotation of revocation state is cross-doc redraft territory (S3 / S4 / S5 / I10).

Default-case "full assertion universe" interpreted as shipped active-only universe — closes audit A7 latent ambiguity.

Q1 / Q2 / Q3 / Q4 / Q6 / Q7 / Q8 consumed or unaffected per §5. Single-cardinality policy interaction with view scope is blueprint-level (Q5 does not lock).
