# Post-L SDK Ergonomics Redesign

- **Status:** draft
- **Created:** 2026-05-09
- **Last Updated:** 2026-05-09
- **Parent:** Post-L (closes the L Direction sequence G1→G4→G2→G3→G5; this blueprint evaluates the SDK ergonomic shape now that the L surface is settled)
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g5-round-events-proofframe-diff (archived)](../archive/2026-05-08_l-direction-g5-round-events-proofframe-diff.md) — G5 ProofFrame Diff; closed L Direction
  - [2026-05-08_l-direction-g3-rule-overlays (archived)](../archive/2026-05-08_l-direction-g3-rule-overlays.md)
  - [2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck (archived)](../archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md)
  - [2026-05-08_l-direction-g4-why-not-frontier (archived)](../archive/2026-05-08_l-direction-g4-why-not-frontier.md)
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md)
- **Audit Log:** [2026-05-09_post-l-sdk-ergonomics-redesign.audit.md](./2026-05-09_post-l-sdk-ergonomics-redesign.audit.md)
- **Baseline:** Post-G5-publish topic tip `1752372` (G5 published HEAD `d4ceb3e` + G5 publish memory sync `a64045e` + G5 post-publish doc polish `1752372`). Forward-only inheritance — does NOT alter any G1/G4/G2/G3/G5 published refs.

> **Design-only first.** This blueprint is **explicitly design-only at the draft stage**. No SDK code change, no `kernel.sdk.__all__` change, no migration path commitment until §5 reaches `scoped`. The first Step 0 question (§5.1) is purely an inventory + option-evaluation pass; subsequent §5.x questions add decisions one at a time per `feedback_iterative_gap_design`. Per `feedback_sdk_ergonomics_redesign_target`: **OpenAI-style ergonomics is a direction input from the user, not an automatic migration target** — falsifier passes must source-ground every choice.

## 0. Core Thesis

> **Core thesis:** The redesign should make the SDK namespace teach FactPy's conceptual model at first contact. Compatibility is a hard constraint, and industry SDK shapes are evidence, not templates.

**Why this thesis (and not "do nothing" or "match OpenAI"):**

The current 30-method flat surface on `SDKStore` is the **accumulated artifact** of 9 incremental L Direction shipments (G1 + G4 + G2 + G3 + G5) layered onto the pre-L schema/read/write/eval surface. It is technically complete (every capability has a method) but pedagogically opaque (a new user reading `dir(sdk)` cannot derive the conceptual layering — schema authoring / single-fact CRUD / evaluation / what-if / overlay / diff — without reading every docstring). L Direction itself recognized this: every G1-G5 archive blueprint cited "post-L SDK ergonomics redesign blueprint is the right venue" because no individual L milestone could decide aggregate shape. Now that L is closed, **the SDK surface has accumulated enough material to be reorganized into a "concept map"** — and the redesign's goal is to do exactly that, without breaking what shipped.

### 0.1 What this thesis implies for §5.x

Every §5.x question becomes a falsifier against the thesis:

- **§5.1 (shape evaluation):** the first question for any candidate shape is **"does `dir(client)` / IDE autocomplete express the conceptual layering?"** — not "does it look like OpenAI / Anthropic / Stripe?". Industry shapes are inputs to consider; legibility is the yardstick.
- **§5.3 (top-level client class naming):** the question is whether a fresh name (e.g., `FactPyClient`) **resets the user's mental model** more cleanly than overloading `SDKStore` — not whether it matches naming conventions in other SDKs.
- **§5.4 / §5.7 (compat strategy):** **the default is to never break the flat `SDKStore.<method>` surface** that 5 immutable Path B snapshots already shipped. Any replacement / deprecation / hard cutover requires its **own dedicated falsifier pass** — it cannot be implied by the namespace decision.
- **OpenAI-style `client.<namespace>.<method>` is a strong candidate, not a preset answer.** §5.1 must source-ground whether FactPy's underlying conceptual model is closer to "client over resources" (OpenAI / Stripe) or "session over a unit of work" (SQLAlchemy `Session`). The shape follows the model, not the other way around.

### 0.2 Rejected alternative theses (with reasons)

The §5.1 falsifier pass evaluated three alternative theses against the situation; all are rejected:

- **A — "Conservatism first" (overly conservative):** *"Default is do nothing; redesign must clear a very high bar."* Rejected because the L Direction blueprints already established that "post-L is the venue" — the bar was implicitly cleared by L's shipment. Refusing to engage now leaves the post-L gap permanent.
- **B — "Compatibility purity" (overly compat-bound):** *"Only add nested aliases; never replace the flat surface."* Rejected as a *thesis* (kept as a strategy under §5.4 / §5.7). Compatibility is a hard constraint, but the thesis must be the *teaching goal*; treating compatibility itself as the goal collapses the redesign into a no-op overlay with no design judgment.
- **C — "Conformance-driven" (overly templated):** *"Match OpenAI shape because it's what Python SDK users expect."* Rejected because conformance is not the goal. FactPy is a knowledge-graph reasoning system — the right shape may inherit from `Session over unit of work` (SQLAlchemy) more than `Client over resources` (OpenAI). Copying a shape that doesn't match the underlying model produces a surface that misleads users about what FactPy is.

### 0.3 What this thesis does NOT do

- **Does not pre-commit to nesting.** The conclusion may be "the flat shape *is* the most legible shape for this codebase, with documentation bundling instead of namespace bundling." That is a valid scoped outcome.
- **Does not pre-commit to a `Client` class.** `SDKStore` may stay as the entrypoint; the question is whether its dir-shape teaches.
- **Does not authorize any migration.** Migration is a §5.4 / §5.7 question, evaluated separately, with its own cost/benefit falsifier.
- **Does not relitigate L Direction shells.** The 9 L methods stay shipped + frozen; the redesign decides how they're surfaced (flat vs nested vs alias-overlay), not their signatures.
- **The §5.2 teaching taxonomy lock (2026-05-09) is conceptual, NOT a shipping commitment.** The 8-namespace taxonomy + 2 sub-namespaces under `what_if` describe how the redesign *teaches* the conceptual model. Whether the taxonomy materializes as runtime attributes (Shape 2/3) or stays as a documentation artifact (Shape 1) is decided at §5.4 / §5.7. The taxonomy lock and the shipping-shape lock are deliberately separate.

## 1. Problem

L Direction is closed. The SDK surface now exposes the full evidence-product round story through 9 narrow shell methods (G1 + G4 + G2 + G3 + G5) plus the schema/read/write/eval surface that predates L. The "completeness" goal that motivated L Direction has been met.

But **the resulting surface shape is the artifact of "narrow shells over existing capabilities", not the artifact of "what a user actually types when they're learning the library"**. Concretely:

- All 30 user-facing methods sit flat on `SDKStore`. There is no grouping by family — `check_rule_disable` and `check_rule_literal_replace` live next to `find` / `get` / `accept_many`. A reader of `dir(sdk)` sees a 30-method namespace with no signposting.
- Method names follow verb-first L-Direction convention (`check_*`, `recheck_*`, `why_not`, `diff_*`) but mix with shorter pre-L verbs (`get`, `find`, `edit`, `set`, `add`, `retract`, `run`, `accept`). The vocabulary isn't uniform.
- There is one nested namespace already (`SDKStore.views`, exposing `create / update / delete / get / list`). It exists as a precedent for nesting but is not used as a guideline anywhere else.
- Industry-standard SDK ergonomics for Python (OpenAI, Anthropic, Stripe, Google's GenAI client) use a top-level client object with nested namespaces grouping operations by resource: `client.chat.completions.create(...)`, `client.assistants.threads.runs.create(...)`. New users learn the namespace shape first, the methods second. This pattern reduces the learning surface from "what's the right name?" to "what family am I in?".

The user has flagged a preference for OpenAI-style shape since 2026-05-07 (recorded in `feedback_sdk_ergonomics_redesign_target`). The L Direction blueprints deliberately deferred any redesign — every G1-G5 lock cited "post-L SDK ergonomics redesign blueprint is the right venue". With L closed, that venue is now active.

**The redesign blueprint must answer: what (if anything) changes about the user-facing SDK shape?** Possibilities span "nothing — the flat surface is fine" through "alias-only namespace overlay" through "full namespace migration with deprecation grace period" through "hard cutover at v0.2". This blueprint scopes the question; it does not pre-commit any direction.

## 2. Goals

- **Design-only deliverable at scope-freeze.** Reach `scoped` with a fully-specified outward shape decision (or explicit "no change") + compatibility strategy + docs/migration impact assessment. **No SDK code lands until status is `scoped`.**
- **Source-ground every choice.** Same falsifier discipline as G1-G5: each §5.x question gets a read-only research pass against the current codebase + industry references + user-facing examples (notebooks, READMEs, downstream consumers if any) before locking.
- **Preserve current flat `SDKStore.<method>` compatibility unless scoped explicitly decides otherwise.** L Direction shipped a published surface across 5 immutable Path B snapshots; downstream consumers may already depend on the flat shape. The redesign must explicitly choose how (or whether) to handle compatibility, with the conservative default being "additive aliases, never break the flat surface".
- **Decide all 9 main design questions** (§5.1 inventory through §5.9 — see §5 below) before scope-freeze. Some may resolve to "no change"; that's a valid answer.
- **Produce a migration assessment** if §5 lands a non-no-change answer. What docs change? What examples change? What error messages change? What version stamp does this constitute (v0.1 minor, v0.2)?

## 3. Non-Goals

- **No SDK code changes during draft.** Status `draft → scoped` requires §5 fully resolved; only after that do any phases ship. The first commit on this blueprint is just the draft seed.
- **No L-Direction shell relitigation.** The 9 L shells (`check`, `diagnose`, `why_not`, `check_fact_overlay`, `recheck_proof_frame`, `check_rule_disable`, `check_rule_literal_replace`, `check_rule_add_condition`, `diff_proof_frames`) are shipped + frozen on origin. The redesign decides how they're surfaced (flat vs nested vs alias-overlay) but does not change their signatures, error paths, or §5.x locks.
- **No `kernel.application` / `kernel.audit` / `kernel.core` changes.** The redesign is purely a `kernel.sdk` outward-ergonomic reshaping. The cross-cutting precedent layer rule from G5 §5.3 ("frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary") stays in force; no DTO surface migrations.
- **No Frontier promotion.** G4 §5.4 evaluator drift gate stays in force. Any namespace decision that surfaces Frontier on the SDK requires a separate scoped blueprint.
- **No round-events recorder promotion.** G5 §5.1 defer stands. Capture-side stays at `kernel.audit.round_events` advanced importable.
- **No Path B published-snapshot modification.** All 5 published L milestone refs and prior Path B combined snapshots are immutable. The redesign produces a new snapshot only at its own publish time.
- **No automatic OpenAI-style migration.** Per `feedback_sdk_ergonomics_redesign_target`, OpenAI-style is a direction input the user has flagged — falsifier passes must source-ground whether the migration costs are justified, whether the shape actually fits this codebase, and what compatibility commitments the migration entails.
- **No SDK code change on the design branch.** This blueprint branch (`codex/v0.1-post-l-sdk-ergonomics-redesign-2026-05-09`) holds **design / blueprint commits only**. All implementation work post-scope-freeze happens on the dedicated implementation branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` (created at design HEAD `59a5694` on 2026-05-09). This isolation prevents implementation regressions from polluting the design source-of-truth and keeps sacred branches (`master` / `v0.1-oss-prep`) and 5 Path B published L snapshots fully untouched even if implementation experiments break.

## 4. Current Context

### 4.1 Inventory of the current SDK surface (post-G5, post-publish)

Source of truth: `src/kernel/sdk/store.py` at HEAD `1752372`. **30 unique public method names** on `SDKStore` (excluding `_`-prefixed internals + properties + classmethods). One nested namespace `SDKStore.views` exposes 5 sub-methods. Total user-facing callables: **35**.

**Grouped by capability family** (as one possible namespace lens; not yet a locked grouping):

| Family | Methods | Provenance |
|---|---|---|
| **Schema authoring (constructor)** | `from_schema_classes(...)` (classmethod) | pre-L; entrypoint. |
| **Schema authoring (instance)** | `ingest(...)`, `validate_provenance(...)` | pre-L. |
| **Read / lookup** | `get(...)` (entity read), `find(...)`, `ref(...)` | pre-L. |
| **Write (single-fact)** | `set(...)`, `add(...)`, `retract(...)`, `edit(...)` | pre-L. |
| **Write (batch)** | `batch(...)` (context manager → `BatchTx`) | pre-L. |
| **Rule / Derivation evaluation** | `run(...)`, `evaluate(...)`, `evaluate_compiled(...)` | pre-L. |
| **Candidate acceptance** | `accept(...)`, `accept_compiled(...)`, `accept_many(...)` | pre-L. |
| **L Direction — what-if (G1)** | `check(...)`, `diagnose(...)` | G1, published `d6716a0`. |
| **L Direction — Why-not (G4)** | `why_not(...)` | G4, published `acb5a6e`. |
| **L Direction — Fact Overlay + ProofFrame Recheck (G2)** | `check_fact_overlay(...)`, `recheck_proof_frame(...)` | G2, published `d658390`. |
| **L Direction — Rule overlays (G3)** | `check_rule_disable(...)`, `check_rule_literal_replace(...)`, `check_rule_add_condition(...)` | G3, published `cb6d3bd`. |
| **L Direction — ProofFrame Diff (G5)** | `diff_proof_frames(...)` | G5, published `d4ceb3e`. |
| **Audit / explain** | `validate_provenance(...)` (also schema), `explain_fact(...)`, `conflicts(...)` | pre-L. |
| **Packaging** | `export_package(...)`, `run_package(...)` | pre-L. |
| **Views (existing namespace precedent)** | `views.create(...)`, `views.update(...)`, `views.delete(...)`, `views.get(...)`, `views.list(...)` | pre-L. |
| **Properties / accessors** | `store`, `ledger`, `schema_ir`, `views` | pre-L. |

Notable observations:

- **9 L methods, 21 pre-L methods, 5 views sub-methods.** The L methods land in one cluster but are not grouped — they're alphabetized into the flat namespace.
- **Verb-first naming is consistent within L Direction** (`check_*`, `recheck_*`, `why_not`, `diff_*`) but inconsistent with pre-L names (`get`, `find`, `edit`, `set`, `add`, `retract`, `run`, `accept`).
- **`SDKStore.views` is the only existing nested namespace.** Established at pre-L for view CRUD operations. Sets a precedent that nesting is OK for "multi-action over single resource" — not yet generalized.
- **`kernel.sdk.__all__` length is 34** and unchanged across G1-G5. None of the 9 L return DTOs or method names are exported; users access them via `SDKStore.<method>`.

### 4.2 Industry references (read-only research; not yet committed direction)

The OpenAI-style hint from `feedback_sdk_ergonomics_redesign_target` references the Python SDK shape:

```python
client = OpenAI()
client.chat.completions.create(...)
client.assistants.create(...)
client.assistants.threads.runs.create(...)
```

Pattern characteristics:
- Top-level `Client` object (capitalized class name; instantiated per session/credential).
- Resource-named namespaces (`chat`, `assistants`, `embeddings`, etc.) attached as attributes.
- Verb at the leaf (`create`, `retrieve`, `list`, `delete`, `update`).
- Multiple levels of nesting where resources are hierarchical (`assistants.threads.runs`).

Other Python SDKs with similar patterns (Anthropic, Google's GenAI, Stripe, AWS boto3) — common shape but not uniform; some use snake_case attributes, some PascalCase. Boto3 in particular has gone the OPPOSITE direction (flat clients per service, methods on the client) and is widely used.

**Counter-pattern reference:** SQLAlchemy's `Session` is a flat object with many methods (`add`, `commit`, `query`, `rollback`, `flush`, `merge`, ...). It's a "session of mixed operations on a unit of work", not a "client over resources". `SDKStore` is closer to this pattern than to OpenAI's resource-per-namespace pattern, since most pre-L methods operate on a unit of work (one schema, one ledger) rather than independent resources.

**Question this raises**: is FactPy's `SDKStore` a "Session over a knowledge graph" (SQLAlchemy-shaped) or a "Client over capabilities" (OpenAI-shaped)? The answer informs whether nesting helps or hurts. §5.1 will source-ground.

### 4.3 User-facing examples and notebooks

`examples/` directory (read-only inspection; not yet a constraint):

- `examples/01_sdk_check_diagnose.ipynb` — demonstrates `sdk.check(...)` / `sdk.diagnose(...)` (G1 methods).
- `examples/02_overlay_why_not_frontier.ipynb` — demonstrates `sdk.check_fact_overlay(...)` (G2) / `sdk.why_not(...)` (G4).
- `examples/03_proofframe_rule_overlays.ipynb` — demonstrates `sdk.recheck_proof_frame(...)` (G2) / `sdk.check_rule_*(...)` (G3).
- `examples/04_round_persistence_diff.ipynb` — demonstrates `kernel.audit.round_events.start_round(...)` + `sdk.diff_proof_frames(...)` (G5).
- `examples/round_story_full_demo.py` — end-to-end script using flat SDK + `kernel.audit.round_events` directly.

Notebooks 01-04 implicitly assume the flat surface shape. Any redesign that changes method paths impacts all 4 notebooks + the round-story demo + READMEs (CN/EN). This is the rough migration cost surface for §5.

### 4.4 Inheritance from L Direction (constraints the redesign must honor)

- **L cross-boundary DTO layer rule (G5 §5.3 / §6 invariant):** "frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary". Redesign cannot relax this — even if a namespace move surfaces audit DTOs differently.
- **Recorder lifecycle stays advanced importable (G5 §5.1).** No promotion, even if a namespace would suggest one.
- **Frontier stays advanced importable (G4 §5.4).** Same.
- **Sibling discipline at 9-shell scope.** Forward-only convention from G3+G5: prior shells' tests stay frozen at their publication moment. If the redesign adds more shells (or refactors), the new tests work against the new scope; published tests stay frozen.
- **Path B per-milestone immutable snapshot strategy.** 5 immutable Path B snapshots exist (G1 / G4 / G2 / G3 / G5). The redesign produces a new combined snapshot only at its own publish time.
- **`kernel.sdk.__all__` length 34** is asserted by 5 invariant test files. Any redesign that adds top-level exports must update all 5 invariant files in lockstep.
- **Sacred branches `master` and `v0.1-oss-prep` untouched.** The redesign branch is a topic forward; no merge back without explicit user authorization.
- **Design / implementation branch isolation.** Design / blueprint work lives on `codex/v0.1-post-l-sdk-ergonomics-redesign-2026-05-09` (current branch). When status flips `draft → scoped` and implementation is authorized, code changes happen on the parallel branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` (created at design HEAD `59a5694` on 2026-05-09). The impl branch is rebased onto design HEAD at scope-freeze time before implementation begins. This enforces "design-only first" structurally — even if implementation breaks every test, the blueprint source-of-truth and sacred branches are isolated.

### 4.5 Memory inputs

- `feedback_sdk_ergonomics_redesign_target` — user prefers OpenAI-style SDK shape (top-level client / nested namespaces / short names) as post-L target. **Direction input only**, not automatic migration. Falsifier must source-ground.
- `project_g{1,2,3,4,5}_published.md` — full L Direction shipped state. Each G's archived blueprint flagged "post-L redesign blueprint" as the venue for namespace questions.
- `project_release_branch_invariants` — sacred branches untouched; publish decisions user-authorized.
- `feedback_iterative_gap_design` — one §5.x lock at a time (or low-suspense batches); falsifier required before each lock.
- `feedback_audit_cadence_per_phase` — strict per-phase audit gate.
- `feedback_worktree_parallel_implementation` — topic branches use `codex/` prefix; published refs drop it.
- `feedback_narrow_public_api` — in OSS preview lines, default to internal/contained mechanisms; expand public SDK surface only when current scope explicitly requires user-facing access.

### 4.6 Reference bundle inputs

[2026-05-07 post-routemap direction selection input bundle](../../references/working/post-routemap-direction-selection-input/) (8 files, 2231 lines, 9 verification rounds, design-complete). Most relevant findings for redesign:

- **`SDK*` family is established**: `SDKStore` + `SDKBatchTx` (with `SDK*` prefix) + descriptive siblings `EntitySnapshot` / `FieldAssertions` / `AssertionNamespace` / `EntityEditor` / `AssertionRecord` (per [30_recommendation.md:570-577](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)). Renaming `SDKStore` has cascade effects on the SDK* family.
- **`EntitySnapshot.assertions` namespace pattern is established prior art** at [src/kernel/sdk/facade.py:102-217](../../../src/kernel/sdk/facade.py) — `__getattr__` + `FrozenSnapshotError`-on-mutation. Pattern: `snap.assertions.field.active` / `.history` / `.at(t)` / `.version(v)`. **Redesign sub-namespacing should reuse this pattern, not invent.**
- **`EvidenceGraph` is the audit substrate** unified cross-engine explainability DTO (durable as `audit/evidence_graphs.jsonl`; queryable via `AuditQuery.get_candidate_evidence_graph()`). Lives in `kernel.audit` advanced importable, NOT in `factpy.__all__`. Adjacent name only — not a §5.3 collision.
- **L-Full follow-on already anticipated this redesign blueprint** ([30_recommendation.md:600+](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)). L Direction (G1-G5) shipped per Batch 8 §5.5.5 reactivation discipline. `sdk.universe()` → `sdk.why_not()` naming correction shipped at G4. G3 three-sister naming chosen with explicit justification at G3 §5.7.
- **`#6 — No outward compat without user signal`** ([60_lessons-learned.md §2.3](../../references/working/rule-replay-line-redesign-input/60_lessons-learned.md)) cited via §95 lessons quote: user has historically rejected SDK surface expansion "for consistency"; redesign trigger is explicit user signal (per `feedback_sdk_ergonomics_redesign_target`).
- **`import naming (factpy vs kernel.sdk)` deferred** ([README.md Round 9 close](../../references/working/post-routemap-direction-selection-input/README.md)) — separate parallel question to §5.3 class name. Out of §5.3 scope.

## 5. Design — Step 0 Questions

**Convention:** Each §5.x question lists what must be source-grounded by a falsifier pass before locking. **No question below has a final decision yet.** Per `feedback_iterative_gap_design`, decisions land one at a time (or in low-suspense batches), each in its own commit, with a fresh falsifier scan against the codebase HEAD.

The §5.1 inventory is the **first deliverable**. It does not commit to any direction; it just enumerates the current surface and the candidate alternative shapes. §5.2 onward then answer specific questions one at a time.

### 5.1 Inventory the current 30-method flat surface + evaluate alternative shapes

**Question:** What is the actual current SDK surface, and what are the candidate alternative shapes that could replace or overlay it?

**Sub-questions to answer in the falsifier pass:**

- **F0 (thesis-primary, per §0) — Legibility test.** For each candidate shape, can a new user reading `dir(client)` / IDE autocomplete derive the conceptual layering documented in §4.1 (schema authoring / single-fact CRUD / evaluation / what-if / overlay / diff / packaging) **without reading method docstrings**? This is the **first question** every shape must answer; only after F0 do migration cost (F4) and industry conformance comparisons matter. A shape that ranks high on F4 (low migration cost) but fails F0 is rejected per thesis.
- F1 — Confirm the 30-method count + family grouping in §4.1 by exhaustively enumerating `def ` definitions in `kernel/sdk/store.py`. Capture line numbers for every public method.
- F2 — For each method, classify: (a) what resource is the primary subject? (b) what verb describes the action? (c) does the method belong to a "session over knowledge graph" model or a "client over capabilities" model?
- F3 — Inventory candidate alternative shapes (read-only enumeration, not yet a recommendation):
  - **(A) Status quo — flat `SDKStore.<method>`, 30 methods**, no namespace structure. Zero migration cost. Reader sees an unstructured 30-method namespace.
  - **(B) Alias-only namespace overlay** — keep all flat methods AND add nested namespace attribute groups (`sdk.what_if.check(...)`, `sdk.write.add(...)`, etc.) that delegate to the flat methods 1:1. Migration cost = additive surface only; zero breakage. Reader sees both shapes.
  - **(C) Full nested namespace migration with grace period** — flat methods become deprecated aliases; new shape is canonical (`sdk.what_if.check(...)` etc.); deprecation warnings on flat-method use; flat methods removed at a later version. Migration cost = significant; users must update.
  - **(D) Hard cutover** — flat methods removed at the redesign release; new shape is the only shape. Highest migration cost.
  - **(E) New top-level `Client` class with namespace structure** — `SDKStore` stays for backwards-compatible flat use; new `Client` class is the recommended entry point with nested namespaces. Both coexist permanently. Migration cost = additive new class.
  - **(F) Hybrid** — top-level keeps `SDKStore` flat; rename or restructure ONLY the L Direction methods into a sub-namespace (`sdk.l.check(...)` or `sdk.evidence.check(...)`); pre-L methods stay flat. Lower migration cost than full nested.
  - **(G) Other** — any pattern surfaced by user research, downstream consumer signal, or codebase reflection.
- F4 — For each candidate, capture the **rough migration cost surface**: how many notebooks change? How many docs change? How many examples change? How many test files reference flat methods directly?
- F5 — For each candidate, capture the **conceptual fit** with FactPy's actual usage pattern (Session-over-graph vs Client-over-capabilities per §4.2).
- F6 — Source-ground whether the SQLAlchemy precedent (flat session) or the OpenAI precedent (resource-namespace client) better matches FactPy's usage. Not "which is more popular" — "which actually fits the unit-of-work model SDKStore enforces today".

**Conservative default:** option (A) status quo. The flat surface ships, is documented, has 5 immutable published refs depending on it, and has not surfaced consumer complaints in any recorded blueprint or memory. The burden of proof is on alternatives.

**This question deliberately does not propose locking a direction.** §5.1 is a **research deliverable**: enumerate options, source-ground costs, set up the subsequent §5.x questions. Lock here is "the inventory is complete and we have N candidates with documented costs".

#### 5.1 Deliverable (locked 2026-05-09 read-only research at HEAD `60af8bc`)

**5.1.1 Inventory verified.** Source-grounded against `src/kernel/sdk/store.py`:

- **30 user-facing methods on `SDKStore`** (1 classmethod `from_schema_classes` + 29 instance methods); confirms §4.1 count exactly.
- **4 properties** (`store`, `ledger`, `schema_ir`, `views`) — `views` is a property returning `_SDKViewsManager` (private nested class at `store.py:66-104`).
- **1 nested namespace `SDKStore.views`** with 5 sub-methods (`create`, `update`, `delete`, `get`, `list`) — sole existing namespace precedent on `SDKStore`.
- **Total user-facing callables = 35** (30 methods + 5 views sub-methods); + 4 properties as accessors.
- `kernel.sdk.__all__` length **34** (verified by reading `kernel/sdk/__init__.py:30-65` exports list).

**14 conceptual families** (consolidated from §4.1 table):

| # | Family | Methods | Count |
|---|---|---|---|
| 1 | Schema authoring (cls + instance) | `from_schema_classes`, `ingest`, `validate_provenance` | 3 |
| 2 | Read / lookup | `get`, `find`, `ref` | 3 |
| 3 | Write (single-fact) | `set`, `add`, `retract`, `edit` | 4 |
| 4 | Write (batch) | `batch` | 1 |
| 5 | Rule / Derivation evaluation | `run`, `evaluate`, `evaluate_compiled` | 3 |
| 6 | Candidate acceptance | `accept`, `accept_compiled`, `accept_many` | 3 |
| 7 | L — what-if (G1) | `check`, `diagnose` | 2 |
| 8 | L — Why-not (G4) | `why_not` | 1 |
| 9 | L — Fact Overlay (G2) | `check_fact_overlay`, `recheck_proof_frame` | 2 |
| 10 | L — Rule overlays (G3) | `check_rule_disable`, `check_rule_literal_replace`, `check_rule_add_condition` | 3 |
| 11 | L — ProofFrame Diff (G5) | `diff_proof_frames` | 1 |
| 12 | Audit / explain | `explain_fact`, `conflicts` | 2 |
| 13 | Packaging | `export_package`, `run_package` | 2 |
| 14 | Views | `views.create`, `views.update`, `views.delete`, `views.get`, `views.list` | 5 (nested) |

Consolidation possibilities for namespace shape (§5.2 territory): families 1+ → `schema`, 2 → `read`, 3+4 → `write`, 5+6 → `eval`, 7+8+9+10+11 → `what_if` (or split sub-namespaces), 12 → `audit`, 13 → `package`, 14 → `views` (existing). Yields **8 top-level concepts** under one consolidation; could split `what_if` into 5 sub-namespaces under another.

**5.1.2 Migration cost surface (source-grounded, read-only).**

| Surface | Files | SDKStore method-call count | Migration cost |
|---|---|---|---|
| `kernel/tests/test_sdk_*.py` | 23 files | ~150+ method-call mentions (sample top: `diff_proof_frames` 7×, `why_not` 6×, `recheck_proof_frame` 4×, each rule-overlay 4×, `check_fact_overlay` 4×, `check`/`diagnose` 3× each per-file across multiple files) | **HIGH** — primary impact surface |
| `examples/0[1-4]_*.ipynb` (4 notebooks) | 4 files | **1 mention total** (only `diff_proof_frames` in 04 notebook) | **NEGLIGIBLE** — notebooks bypass `SDKStore` and call `kernel.application` / `kernel.core` directly (Tier 2 advanced importable) |
| `examples/round_story_full_demo.py` | 1 file | **0 SDKStore mentions** (uses `kernel.application` / `kernel.core` directly) | **NONE** |
| `kernel/sdk/docs/04_api_surface.md` + `.en.md` | 2 files | extensive `SDKStore.<method>` references | **MEDIUM** — doc rewrite |
| `kernel/application/docs/01_overview.md` + `_en.md` | 2 files | mention SDK shells but not as primary surface | **LOW** |
| `README.md` (CN/EN) quickstart | 2 files | minimal SDK method demo | **LOW** |
| Path B published L snapshots (5 immutable refs) | n/a (frozen) | n/a | **N/A** — never modified |

**Critical insight:** notebooks were authored Tier-2-style (advanced importable, predating L Direction); the L methods on `SDKStore` are not yet demonstrated in chaptered notebooks. **Migration cost is concentrated in tests + API docs, NOT in user-facing examples.** This bounds the practical migration cost more than the §4.3 impact-surface initial estimate suggested.

**5.1.3 Five-shape evaluation (per user §5.1 instruction; mapped to original A-G enumeration where applicable).**

The user-listed 5 shapes mapped to the original A-G candidate set:

| User-listed shape | Maps to | Description |
|---|---|---|
| Status quo flat | A | `FactGraph = SDKStore` literal alias; no nested namespace; `dir()` = current 30 methods + 4 properties |
| Additive nested aliases | B | Both flat and nested coexist; nested namespaces are thin proxies delegating to flat methods; `dir()` shows BOTH |
| Canonical nested + flat compat | (B/C variant) | Nested is canonical via docs/quickstart lever; flat methods stay callable but de-emphasized; runtime same as B but editorial framing different |
| Replacement / deprecation | C/D | Flat methods get `DeprecationWarning`; eventually removed; nested becomes only shape |
| Hybrid / staged | F | Some methods nested, others flat (e.g., L methods nested, pre-L flat); or phased rollout |

(Shape E "new top-level Client class" is moot post-§5.3 lock — `FactGraph` IS the new top-level name; whether it has nested structure is now §5.1/§5.2.)

**Per-shape evaluation under §0 thesis F0 (`dir(FactGraph)` legibility), F4 (migration cost), F5 (Session-vs-Client conceptual fit):**

##### Shape 1 — Status quo flat (`FactGraph = SDKStore` literal alias)

```python
fg = FactGraph.from_schema_classes([Person])
fg.check(...)
fg.add(...)
fg.diff_proof_frames(...)
```

`dir(fg)` (alphabetical): `accept`, `accept_compiled`, `accept_many`, `add`, `batch`, `check`, `check_fact_overlay`, `check_rule_add_condition`, `check_rule_disable`, `check_rule_literal_replace`, `conflicts`, `diagnose`, `diff_proof_frames`, `edit`, `evaluate`, `evaluate_compiled`, `explain_fact`, `export_package`, `find`, `from_schema_classes`, `get`, `ingest`, `ledger`, `recheck_proof_frame`, `ref`, `retract`, `run`, `run_package`, `schema_ir`, `set`, `store`, `validate_provenance`, `views`, `why_not`.

- **F0 (legibility):** ❌ **FAILS.** A new user reading `dir()` cannot derive the 14 conceptual families. `check_fact_overlay` and `recheck_proof_frame` are alphabetically interleaved with `explain_fact` and `conflicts`. The L-prefix `check_*` is mixed with bare `check`. No grouping signal.
- **F4 (migration cost):** ✅ **ZERO** — literal alias; existing SDKStore tests + callsites unchanged.
- **F5 (conceptual fit):** matches "Session over knowledge graph" (SQLAlchemy precedent) — flat surface where you mutate the session with discrete operations.
- **Verdict:** lowest-cost shape but fails thesis F0. Conservative default per §0.3 ("does not pre-commit to nesting"). Falls to thesis unless §5.7 explicitly carves out "no change is the right answer".

##### Shape 2 — Additive nested aliases (overlay)

```python
fg = FactGraph.from_schema_classes([Person])
fg.check(...)              # flat (still works)
fg.what_if.check(...)      # nested (new alias, delegates to flat)
fg.write.add(...)          # nested (delegates to fg.add)
fg.read.get(...)           # nested (delegates to fg.get)
```

`dir(fg)` shows ALL flat methods + new namespace attributes (`schema`, `read`, `write`, `eval`, `what_if`, `audit`, `package`, plus existing `views`).

- **F0 (legibility):** **MIXED-PARTIAL.** Namespaces ARE informative — a user can `tab` into `fg.what_if.<TAB>` and see `check` / `diagnose` / `why_not` / etc. But `dir(fg)` is now cluttered: namespaces compete with flat methods for attention. Discoverability improves; raw `dir()` still doesn't visibly TEACH layering because flat methods drown out namespaces.
- **F4 (migration cost):** ✅ **NEAR-ZERO** at runtime. Tests stay valid (call flat methods). New tests added for nested-form parity. Docs add nested examples.
- **F5 (conceptual fit):** hybrid — flat (Session) + nested (Client) coexist. Conceptually messy but honest about the dual identity.
- **Verdict:** adds learning surface without taking away. F0 partial — namespaces help IDE/autocomplete but raw `dir()` still mixed. Most defensible under `#6 — no outward compat without user signal` (additive only).

##### Shape 3 — Canonical nested + flat compat (docs lever)

Same runtime as Shape 2, but documentation/quickstart only show nested form. Flat methods stay callable as undocumented compat. Optional: `__dir__` override could de-emphasize flat methods.

```python
# Quickstart (canonical):
fg = FactGraph.from_schema_classes([Person])
fg.write.add(...)
fg.what_if.check(...)
fg.what_if.diff(...)

# Still works (compat, undocumented):
fg.add(...)
fg.check(...)
```

`dir(fg)`: same as Shape 2 unless `__dir__` is overridden.

- **F0 (legibility):** **BETTER THAN SHAPE 2** if quickstart + IDE autocomplete favor nested. Editorial pressure makes nested the "obvious" path even though flat works. With `__dir__` override, `dir()` could show only namespaces (advanced users still call flat directly). HOWEVER `__dir__` override has subtle compatibility costs (REPL surprise, debugger inspection).
- **F4 (migration cost):** **MEDIUM.** Runtime same as Shape 2. Documentation cost is high — every flat-method callsite in docs (04_api_surface.md, README quickstart, application overview) needs nested equivalent. Tests stay valid; new nested-form parity tests added.
- **F5 (conceptual fit):** reframes toward "Client over capabilities" with namespaces; keeps Session-over-graph compat.
- **Verdict:** documentation lever pulls F0 up over Shape 2. The "canonical" framing is editorial, not structural. Risk: if users still write `fg.add(...)` because that's what they typed before, the editorial lever fails.

##### Shape 4 — Replacement / deprecation

```python
fg.add(...)  # DeprecationWarning: use fg.write.add(...) instead
fg.write.add(...)  # canonical
# Eventually (next major): fg.add removed entirely
```

- **F0 (legibility):** ✅ **STRONG (eventually).** Once flat is deprecated/removed, `dir(fg)` shows only namespaces. Layering is visible. Conceptual model is taught.
- **F4 (migration cost):** ❌ **HIGH.** Breaks `#6` "no outward compat without user signal" — flat surface is shipped; removing it is breaking change. All 23 `test_sdk_*.py` files update method calls. All docs update. Path B published snapshots stay frozen but stop matching current shape (audit confusion).
- **F5 (conceptual fit):** "Client over capabilities" replaces "Session over graph".
- **Verdict:** **violates §0 thesis hard-constraint** (compat is hard constraint). Per §5.4 thesis-derived default, Shape 4 candidates require **standalone falsifier pass** justifying the break. Current evidence basis is no stronger than Batch 8's falsifier #18 PARTIAL ("not now") — no concrete consumer signal demanding flat removal. Rejected unless §5.4 standalone falsifier surfaces specific user-pain that nested+flat-compat does not solve.

##### Shape 5 — Hybrid / staged

Variant 5a: L methods nested only (`fg.what_if.check(...)`); pre-L methods stay flat (`fg.add(...)`).
Variant 5b: New methods (post-redesign) only get nested; existing 30 stay flat.
Variant 5c: Phased rollout — Phase 1 = L methods nested + flat alias; Phase 2 = pre-L verbs nested + flat alias; etc.

- **F0 (legibility):** **VARIES, generally weaker than Shape 3.** Variant 5a has split-personality `dir()`: nested for L, flat for pre-L. Variant 5b is even more confusing (depends on when method was added). Variant 5c is cleaner if explicit phase markers, but adds blueprint discipline cost.
- **F4 (migration cost):** **MODERATE to HIGH.** Variant 5a needs migration of L methods only in tests (still 9 methods × ~4 mentions each = ~36 callsites). Variant 5c needs phase-by-phase migration discipline.
- **F5 (conceptual fit):** mixed.
- **Verdict:** hybrid variants tend to muddle without clear win unless 5c is paired with a specific phased rollout justification (e.g., "first phase deferred until consumer feedback"). Less defensible than Shape 2 or Shape 3 unless specifically motivated.

**5.1.4 Conclusion / setup for §5.2.**

Under §0 thesis F0 (legibility-first) + flat-compat hard-constraint (§5.4 default-no-break):

| Shape | F0 verdict | F4 cost | Compat-honoring | Status under thesis |
|---|---|---|---|---|
| 1 — Status quo flat | FAILS | ZERO | YES | conservative default; rejected by thesis unless §5.7 carves out "no change" |
| 2 — Additive nested aliases | PARTIAL | NEAR-ZERO | YES | most defensible additive under `#6` |
| 3 — Canonical nested + flat compat | BETTER (docs lever) | MEDIUM (docs) | YES | leading candidate under thesis |
| 4 — Replacement / deprecation | STRONG (eventually) | HIGH | NO | requires §5.4 standalone falsifier; current evidence does not justify |
| 5 — Hybrid / staged | VARIES | MODERATE-HIGH | YES | weaker than Shape 3 unless specifically motivated |

**§5.1 lock outcome:** inventory complete; 5 shapes evaluated with F0 / F4 / F5 source-grounded; **Shape 3 (canonical nested + flat compat) is the leading candidate under thesis**, with Shape 2 (additive aliases) as the conservative-additive fallback, Shape 1 (status quo) as the §5.7 "no change" fallback, and Shape 4 (replacement) requiring standalone §5.4 falsifier the current evidence does not yet support. Shape 5 (hybrid) is weaker than Shape 3 unless a specific phased motivation surfaces.

**§5.2 (namespace grouping) is now the substantive next decision.** The 14 conceptual families consolidated into ~8 top-level concepts (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`) under one consolidation; alternative consolidations split `what_if` into 5 sub-namespaces (G1/G2/G3/G4/G5 family structure) or use round-story-flow ordering. §5.2 picks the grouping under F0 conceptual-layer-legibility + F1 verb→namespace-inference + F4 layer-rule preservation.

**§5.1 is research-only; no direction locked.** Shape decision (1 vs 2 vs 3 vs 5) is deferred to §5.7 (the "ship at all" meta-question), which weighs the F0 legibility gain (Shape 3 > Shape 2 > Shape 1) against the migration cost (Shape 3 > Shape 2 > Shape 1) and §5.4-determined compat strategy.

### 5.2 Namespace shape — if non-flat, what is the grouping?

**Question:** If §5.1 surfaces non-(A) options worth pursuing, what is the actual namespace grouping?

Candidate groupings (provisional; finalized at §5.2 lock):

- **By capability family** (matches §4.1 grouping table): `sdk.schema.*` / `sdk.read.*` / `sdk.write.*` / `sdk.eval.*` / `sdk.accept.*` / `sdk.what_if.*` (G1+G2+G3+G4) / `sdk.diff.*` (G5) / `sdk.audit.*` / `sdk.package.*` / `sdk.views.*` (existing).
- **By tier** (Tier 1 SDK shells vs pre-L): `sdk.l.*` (everything from G1-G5) / `sdk.write.*` / `sdk.read.*` / `sdk.eval.*` / etc.
- **By resource** (closest to OpenAI shape): `sdk.derivations.*` / `sdk.rules.*` / `sdk.entities.*` / `sdk.proof_frames.*` / `sdk.rounds.*`.
- **Round-story-flow** (matches the user-facing notebook progression): `sdk.check.*` / `sdk.overlay.*` / `sdk.recheck.*` / `sdk.diff.*` / etc.

**Falsifiers required:**

- **F0 (thesis-primary, per §0) — Conceptual-layer legibility.** Does the grouping make the §4.1 conceptual layering legible at `dir(client)` time? Specifically: does each top-level namespace name (`schema`, `read`, `write`, `eval`, `what_if`, `diff`, etc.) immediately convey what's inside, or does it require docstring lookup? A grouping that scores high on F1 (verb→namespace inference) but fragments the conceptual layering (e.g., splits "what-if analysis" across `check`, `overlay`, `diff` namespaces) fails F0 and is rejected per thesis.
- F1 — Which grouping minimizes the "method-name search problem" (user knows verb but doesn't know namespace)? Test by asking: given a verb, can a user infer the namespace?
- F2 — Which grouping aligns with the existing notebook progression (01 / 02 / 03 / 04)?
- F3 — Which grouping survives the addition of a hypothetical 10th L family without restructuring?
- F4 — Does any grouping accidentally promote `kernel.audit` or `kernel.core` concepts into the SDK surface? The G5 §5.3 layer rule must hold.
- F5 — Existing `views` namespace precedent — does it fit the chosen grouping or stay an outlier?

#### 5.2 Deliverable (research-only at HEAD `d581703`; no lock yet — recommendation pending user confirmation)

§5.2 evaluates namespace grouping **independently from rollout shape** (§5.1 deferred shape choice to §5.7). The grouping decision is the conceptual taxonomy; whether it ships as additive aliases (Shape 2), canonical nested + flat compat (Shape 3), or not at all (Shape 1) is a separate §5.4/§5.7 question.

##### 5.2.1 Top-level 8-concept evaluation

Starting candidate from §5.1 inventory:

`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`

**F0 (does `dir(FactGraph)` teach the model?):** ✅ **STRONG.** A new user reading `dir(fg)` would see `schema`, `read`, `write`, `eval`, `what_if`, `audit`, `package`, `views` (8 namespaces) plus 1 classmethod (`from_schema_classes`), 1 method (`batch`), 4 properties (`store`, `ledger`, `schema_ir`, `views`). The 8 namespace names form a coherent mental model: declare data shape (`schema`), look at data (`read`), modify data (`write`), run rules (`eval`), hypothetical analysis (`what_if`), post-hoc inspection (`audit`), export/import (`package`), saved queries (`views`). No docstring lookup required to derive the layering.

**F1 (each method placeable unambiguously):** ✅ **MOSTLY UNAMBIGUOUS** — three methods need explicit decisions:

| Method | Candidate placements | Recommendation | Rationale |
|---|---|---|---|
| `validate_provenance` | `schema` vs `audit` | **`schema`** | Pre-ingest validation of provenance documents; structurally schema-validation-adjacent; `audit` is post-hoc inspection. |
| `diff_proof_frames` (G5) | `what_if` vs `audit` | **`audit`** | Source-grounded at `store.py:719-795`: takes `tuple[RoundEvent, ...]` from `kernel.audit.round_events` (PERSISTED rounds), returns frozen `ProofFrameDiff` from `kernel.audit`. Compares two real rounds — not a hypothetical scenario. Semantic fit: post-hoc comparison alongside `explain_fact` / `conflicts`. |
| `accept` / `accept_compiled` / `accept_many` | `eval` vs `write` | **`eval`** | Conceptually mutating (commits candidates as facts), but workflow-paired with `evaluate*` (eval → accept). Splitting separates a unit-of-work pair. Documented as "evaluation closure" within `eval` group. |

All 30 methods placeable post-decision. F1 PASS.

**F-layer (mix `kernel.audit` vs `kernel.application.protocol` vs SDK write APIs?):** ✅ **CLEAN at top level**, mild heterogeneity at `audit` group:

| Group | Layers touched | Verdict |
|---|---|---|
| `schema` | SDK Entity classes + `kernel.application.compile` + `IngestResult`/`ValidationReport` | clean |
| `read` | SDK-level (Entity instances, refs) | clean |
| `write` | SDK Entity + `kernel.core.store` (ledger writes) | clean (write APIs are inherently substrate-touching by design) |
| `eval` | SDK Query/Derivation + `kernel.application` `CandidateSet` | clean |
| `what_if` | SDK Rule + `kernel.application.protocol` frozen DTOs (CheckResult, DiagnoseResult, FactOverlayCheckResult, ProofFrameRecheckResult, RuleDisableResult, etc.) | clean — all G5 layer-rule-compliant |
| `audit` | `explain_fact` / `conflicts` return shallow `dict[str, Any]`; `diff_proof_frames` returns frozen `kernel.audit.ProofFrameDiff` | **mild heterogeneity** — same group has shallow + DTO returns. Documented but not a layer violation. |
| `package` | `ExportOptions` + path I/O | clean |
| `views` | SDK ViewSpec | clean (existing precedent) |

The `audit` group's heterogeneous return shapes (dict vs DTO) is structurally OK per G5 §5.3 layer rule (which says **frozen DTO above kernel.core**, not "all returns must be DTO"). Documentation should note that `diff_proof_frames` is the typed-return outlier in `audit`.

**F-DTO-rule (preserves G5 cross-cutting precedent + G3 substrate-IR exclusion?):** ✅ **PRESERVED.** Grouping doesn't change method signatures. SDK methods continue to take/return either `kernel.application.protocol` frozen DTOs or `kernel.audit` frozen DTOs (G5 §5.3 verbatim invariant); SDK `Rule` objects still get compiled internally via `_compile_rule_input`, so `RuleSpec` substrate IR stays out of SDK boundary (G3 §5.2 verbatim).

**F-anti-resource (avoids OpenAI/Stripe resource-API model?):** ✅ **AVOIDED at top level.** The 8-concept consolidation is **operation-mode-leaning** (`schema` = "schema operations", `read` = "read operations", `what_if` = "what-if operations") — closer to SQLAlchemy `Session.<operation>` than OpenAI `client.<resource>.<verb>`. Resource-model would look like `fg.entities.add(...)` / `fg.derivations.run(...)` / `fg.proof_frames.diff(...)` — explicitly NOT what this proposes. Mild resource-flavor appears in sub-namespaces where natural (`views.<verb>` is the existing precedent; `what_if.rule.<verb>` and `what_if.fact_overlay.<verb>` if §5.2.2 splits — see below). Top-level stays operation-mode.

##### 5.2.2 The `what_if` question — split vs unified

`what_if` group has 8 methods after `diff_proof_frames` moves to `audit`:

```
check, diagnose, why_not, check_fact_overlay, recheck_proof_frame,
check_rule_disable, check_rule_literal_replace, check_rule_add_condition
```

**Option A — Unified (8 methods directly under `what_if`):**

```python
fg.what_if.check(...)
fg.what_if.diagnose(...)
fg.what_if.why_not(...)
fg.what_if.check_fact_overlay(...)
fg.what_if.recheck_proof_frame(...)
fg.what_if.check_rule_disable(...)
fg.what_if.check_rule_literal_replace(...)
fg.what_if.check_rule_add_condition(...)
```

`dir(fg.what_if)` (alphabetical): `check`, `check_fact_overlay`, `check_rule_add_condition`, `check_rule_disable`, `check_rule_literal_replace`, `diagnose`, `recheck_proof_frame`, `why_not` — 8 methods.

- **F0 (sub-legibility):** PARTIAL. `check_*` prefix appears 5 times, structurally informative but visually noisy. User reads 8 methods, needs to scan prefixes to derive sub-grouping (G1 vs G2 vs G3).
- **F1 (placement):** unambiguous (all 8 methods are direct).
- **Migration cost:** ZERO renames; nested namespace just adds `what_if.` prefix to existing flat names.
- **Compatibility:** clean — exact flat-method names preserved.

**Option B — Split (G1+G4 direct under `what_if`; G2 under `what_if.fact_overlay`; G3 under `what_if.rule`):**

```python
# G1 + G4 direct (3 methods, naturally verb-named)
fg.what_if.check(...)              # G1
fg.what_if.diagnose(...)           # G1
fg.what_if.why_not(...)            # G4

# G2 sub-namespace (2 methods)
fg.what_if.fact_overlay.check(...)               # was check_fact_overlay
fg.what_if.fact_overlay.recheck_proof_frame(...) # was recheck_proof_frame (verb retained)

# G3 sub-namespace (3 methods)
fg.what_if.rule.disable(...)         # was check_rule_disable
fg.what_if.rule.literal_replace(...) # was check_rule_literal_replace
fg.what_if.rule.add_condition(...)   # was check_rule_add_condition
```

`dir(fg.what_if)`: `check`, `diagnose`, `why_not`, `fact_overlay`, `rule` — **5 entries** (3 methods + 2 sub-namespaces).
`dir(fg.what_if.fact_overlay)`: `check`, `recheck_proof_frame` — 2 methods.
`dir(fg.what_if.rule)`: `disable`, `literal_replace`, `add_condition` — 3 methods.

- **F0 (sub-legibility):** ✅ **STRONGER.** 5 entries instead of 8; sub-namespaces cleanly reflect G1+G4 / G2 / G3 family structure. Sub-namespace verb names lose `check_*` prefix collision (5 of 8 methods drop their `check_` prefix because at sub-namespace level there's no naming collision with bare `check`).
- **F1 (placement):** unambiguous; 5 methods get short names (`fact_overlay.check`, `rule.disable`, `rule.literal_replace`, `rule.add_condition`).
- **Migration cost:** **5 renames as additive aliases under Shape 2** (flat methods stay; new aliased nested-short paths added). No flat-method removal.
- **Compatibility:** clean — flat methods stay callable verbatim; new nested paths are additive aliases. Shape 3 (canonical nested + flat compat) is the natural rollout for Option B.
- **F-anti-resource subtle concern:** `what_if.rule.<verb>` and `what_if.fact_overlay.<verb>` ARE mildly resource-shaped at the sub-namespace level (resource = rule / fact_overlay; verb = action). HOWEVER the resource-flavor here is local to the sub-namespace (where it's natural for "operations on a rule overlay") and doesn't propagate to top-level. Distinct from OpenAI-style `client.resource.verb` where every method follows the pattern.

**Recommendation: Option B (split)** under §0 thesis F0:

| Axis | Option A (unified) | Option B (split) | Winner |
|---|---|---|---|
| F0 sub-legibility | 8 alphabetized methods | 5 entries; sub-namespaces reflect L family | **B** |
| F1 placement | unambiguous | unambiguous | tie |
| Migration cost (additive) | 0 renames | 5 alias paths added | A (cheaper) |
| Naming clarity | `check_*` prefix collision noise | clean short names at sub-level | **B** |
| Future extensibility | adding 10th L method bloats unified namespace | sub-namespaces accommodate naturally | **B** |
| Anti-resource | clean | mild local resource-flavor | A (slightly cleaner) |

Option B wins on F0, naming clarity, and future extensibility; loses on migration cost (5 alias paths) and mild local resource-flavor. Under thesis (legibility-first), Option B is the recommended split.

##### 5.2.3 Resulting full grouping skeleton (recommended; lock pending user confirmation)

```
fg
├── from_schema_classes (classmethod)        # entrypoint
├── batch (context manager)                   # heavy use; stays top-level
├── store, ledger, schema_ir (properties)     # low-level access
├── views (property → namespace)              # existing precedent
│   ├── create
│   ├── update
│   ├── delete
│   ├── get
│   └── list
├── schema
│   ├── ingest
│   └── validate_provenance
├── read
│   ├── get
│   ├── find
│   └── ref
├── write
│   ├── set
│   ├── add
│   ├── retract
│   └── edit
├── eval
│   ├── run
│   ├── evaluate
│   ├── evaluate_compiled
│   ├── accept
│   ├── accept_compiled
│   └── accept_many
├── what_if                                   # G1+G4 direct + G2/G3 sub-namespaced
│   ├── check                                  # G1
│   ├── diagnose                               # G1
│   ├── why_not                                # G4
│   ├── fact_overlay
│   │   ├── check                              # was check_fact_overlay
│   │   └── recheck_proof_frame                # G2
│   └── rule
│       ├── disable                            # was check_rule_disable
│       ├── literal_replace                    # was check_rule_literal_replace
│       └── add_condition                      # was check_rule_add_condition
├── audit
│   ├── explain_fact
│   ├── conflicts
│   └── diff_proof_frames                      # G5 — moved here from what_if
└── package
    ├── export_package
    └── run_package
```

**Counts:** 8 top-level namespaces + 2 sub-namespaces (`what_if.fact_overlay`, `what_if.rule`) + existing `views` (5 sub-methods). 30 user-facing methods preserved verbatim at flat level under Shape 2/3 compat default; 5 nested-short alias paths added under what_if split (`what_if.fact_overlay.check`, `what_if.rule.disable`, `what_if.rule.literal_replace`, `what_if.rule.add_condition`, plus `what_if.fact_overlay.recheck_proof_frame` which keeps verb name verbatim).

##### 5.2.4 Falsifier outcomes summary

| Falsifier axis | Verdict | Evidence |
|---|---|---|
| F0 — `dir(FactGraph)` teaches the model | ✅ STRONG | 8 top-level namespace names form coherent mental model without docstring lookup |
| F1 — methods placeable unambiguously | ✅ PASS (with 3 documented placements: `validate_provenance` → schema; `diff_proof_frames` → audit; `accept*` → eval) | All 30 methods placed; ambiguity explicitly resolved |
| F-layer — no improper mix of `kernel.audit` / protocol / SDK write | ✅ CLEAN at top level; mild dict-vs-DTO heterogeneity in `audit` (documented) | Not a layer violation per G5 §5.3 invariant |
| F-DTO-rule — G5 boundary + G3 substrate-IR exclusion preserved | ✅ PRESERVED | Grouping doesn't change signatures; method-level invariants intact |
| F-anti-resource — avoids OpenAI/Stripe resource model | ✅ AVOIDED at top level; mild local resource-flavor in `what_if.rule.*` / `what_if.fact_overlay.*` (Option B); top-level stays operation-mode-leaning per Session-over-graph thesis | `views` is the existing precedent for local resource-flavor at sub-namespace |

##### 5.2.5 Decision (locked 2026-05-09 per user direction): teaching taxonomy

**Critical framing per user direction:** §5.2 lock is the **teaching taxonomy** — the locked conceptual model that the redesign uses to organize `dir(FactGraph)` legibility. **It is NOT the shipping shape.** Whether the taxonomy materializes as additive aliases (Shape 2), canonical nested surface + flat compat (Shape 3), docs-only with no runtime aliases (Shape 1), or some §5.7-resolved variant is a separate decision deferred to §5.4 (compat strategy) and §5.7 (ship-at-all meta-question). This separation prevents accidentally pre-locking the rollout shape via the taxonomy lock.

**5 placements locked:**

1. **`what_if` adopts Option B (split).** G1+G4 direct (`check`, `diagnose`, `why_not`); G2 sub-namespaced as `what_if.fact_overlay.check` + `what_if.fact_overlay.recheck_proof_frame`; G3 sub-namespaced as `what_if.rule.disable` + `what_if.rule.literal_replace` + `what_if.rule.add_condition`. **Rationale (per user):** "Option B is the right teaching shape. It keeps the top-level concept small while exposing the internal structure of what-if work: direct check/diagnose/why-not, plus fact overlay and rule overlay subfamilies."

2. **`diff_proof_frames` → `audit`.** Removed from L-Direction `what_if` cluster, placed alongside `explain_fact` and `conflicts`. **Rationale (per user):** "It consumes recorded round events and compares persisted proof-frame outcomes; it is post-hoc audit, not hypothetical evaluation." Source-grounded at `store.py:719-795` — takes `tuple[RoundEvent, ...]` from `kernel.audit.round_events` (PERSISTED rounds), returns frozen `kernel.audit.ProofFrameDiff`.

3. **`validate_provenance` → `schema`.** Placed alongside `ingest`. **Rationale (per user):** "It validates package/schema/provenance before ingest rather than auditing runtime behavior."

4. **`accept` / `accept_compiled` / `accept_many` stay in `eval`** (despite being mutating operations). **Rationale (per user):** "The mental workflow is evaluation lifecycle: evaluate candidates, then accept them. Splitting to `write` would hide the evaluate→accept flow."

5. **`from_schema_classes` (classmethod) + `batch` (context manager) stay top-level** on `FactGraph`, NOT moved to `schema.from_classes` or `write.batch`. **Rationale (per user):** "They are entrypoint/context-construction APIs, not ordinary methods inside conceptual namespaces."

**Locked teaching taxonomy structure:**

```
FactGraph                                       # locked at §5.3
├── from_schema_classes (classmethod)          # entrypoint, top-level
├── batch (context manager)                     # context-construction, top-level
├── store, ledger, schema_ir (properties)       # low-level access
├── views (property → namespace)                # existing precedent (5 sub-methods)
├── schema                                      # 2 methods
│   ├── ingest
│   └── validate_provenance
├── read                                        # 3 methods
│   ├── get
│   ├── find
│   └── ref
├── write                                       # 4 methods
│   ├── set
│   ├── add
│   ├── retract
│   └── edit
├── eval                                        # 6 methods (evaluate→accept lifecycle)
│   ├── run
│   ├── evaluate
│   ├── evaluate_compiled
│   ├── accept
│   ├── accept_compiled
│   └── accept_many
├── what_if                                     # G1+G4 direct + G2/G3 sub-namespaced
│   ├── check                                   # G1
│   ├── diagnose                                # G1
│   ├── why_not                                 # G4
│   ├── fact_overlay
│   │   ├── check                               # was check_fact_overlay
│   │   └── recheck_proof_frame                 # G2 (verb retained)
│   └── rule
│       ├── disable                             # was check_rule_disable
│       ├── literal_replace                     # was check_rule_literal_replace
│       └── add_condition                       # was check_rule_add_condition
├── audit                                       # 3 methods (post-hoc inspection)
│   ├── explain_fact
│   ├── conflicts
│   └── diff_proof_frames                       # G5 — moved here
└── package                                     # 2 methods
    ├── export_package
    └── run_package
```

**Lock outcome counts:**
- 8 top-level namespaces (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`)
- 2 sub-namespaces under `what_if` (`fact_overlay`, `rule`)
- Top-level direct surface: `from_schema_classes` (cls) + `batch` (cm) + 4 properties (`store`, `ledger`, `schema_ir`, `views`)
- 30 user-facing methods preserved verbatim at flat `SDKStore.<method>` level (per §0 thesis hard-constraint)
- 5 nested-short alias paths surface in the taxonomy (`what_if.fact_overlay.check`, `what_if.fact_overlay.recheck_proof_frame`, `what_if.rule.disable`, `what_if.rule.literal_replace`, `what_if.rule.add_condition`)

**What this lock does NOT decide:**

- **Whether the taxonomy ships at all** — §5.7 ship-at-all meta-question.
- **How the taxonomy materializes** — §5.4 compat strategy (Shape 1 docs-only / Shape 2 additive aliases / Shape 3 canonical nested + flat compat / Shape 5 hybrid).
- **Whether the 5 nested-short alias names are exposed at runtime** — depends on §5.4/§5.7. Under Shape 1, the taxonomy is a documentation artifact; the 5 alias paths exist only in docs. Under Shape 2/3, the alias paths materialize as runtime attributes via property/`__getattr__` namespace pattern (per `EntitySnapshot.assertions` prior art at `kernel/sdk/facade.py:102-217`).

**Cross-references encoded in §6 invariants:** locked teaching taxonomy + "teaching taxonomy ≠ shipping shape" separation rule. Cross-references encoded in §0.3 thesis non-pre-commitments (does not pre-commit migration).

### 5.3 Top-level entrypoint class naming

**Question:** What is the user-facing top-level entrypoint class name? Keep `SDKStore`, or introduce a new name (and if new, what)?

**Candidates evaluated** (4-round chat-driven falsifier pass on 2026-05-09):

| Candidate | Repetition with package | Python precedent | F0 mental-model-reset (thesis primary) | 信达雅 | Verdict |
|---|---|---|---|---|---|
| `keep SDKStore` | n/a (current) | — | **Fails F0** — "SDK" tells you HOW (channel), "Store" collides mentally with substrate `kernel.core.store.Store` | low | rejected as canonical (kept callable per §5.4 compat) |
| `FactPy` | full repetition (eponymous) | `flask.Flask`, `openai.OpenAI`, `anthropic.Anthropic` | **Fails F0** — eponymous teaches identity not model; sends wrong category signal (eponymous in Python = hosted-service SDK or web framework; FactPy is neither); no natural variable-name convention (no `app`/`client` equivalent); forecloses future top-level types | medium | rejected (wrong category signal) |
| `Client` | none | `cohere.Client`, `genai.Client` | Fails F0 + F2 — wrong category signal; FactPy is not a hosted service | low | rejected (wrong category signal) |
| `FactPyClient` | partial (Fact+Py) | — | Compounds two rejections (Fact-prefix + Client) | low | rejected |
| `Kernel` | full collision with internal `kernel.*` package | `genai.Client` (in google.generativeai) | Fails F1 — package namespace collision | n/a | rejected (collision) |
| `Store` | bare | — | Fails F2 — substrate `kernel.core.store.Store` ambiguity | n/a | rejected (substrate collision) |
| `Session` | none | `sqlalchemy.Session`, `requests.Session`, `pyspark.sql.SparkSession` | Mixed F0 — teaches pattern (transactional unit-of-work) but not domain; FactPy has no commit/rollback semantics so SQLAlchemy migration knowledge would partially mislead | high (Pythonic) | rejected (teaches pattern not domain; partial mislead) |
| `KnowledgeBase` | none | `pydantic.BaseModel`, AI/Prolog tradition | Strong F0 — teaches full domain ("you're holding a knowledge base"); `kb` standard variable abbrev | medium-high (13 chars, classical) | strong runner-up |
| **`FactGraph`** | partial ("Fact") | **`tensorflow.Tensor`, `pyspark.sql.SparkSession`, `pyparsing.ParserElement`** — major Python libraries explicitly use same-morpheme repetition where the repeated morpheme strengthens domain abstraction | **Strong F0** — teaches domain ("Fact") + structure ("Graph"); user reading `from factpy import FactGraph` learns at first contact "this is a graph of facts" | high (9 chars; both axes covered) | **chosen** |

**Decision (locked 2026-05-09 via 4-round chat-driven falsifier pass): `FactGraph`.**

**Falsifier evidence:**

- **F0 (mental-model-reset, thesis-primary, per §0):** `factpy.FactGraph` teaches users at first contact that they're holding a "fact graph" — both domain ("Fact") and structure ("Graph"). `factpy.FactPy()` (eponymous) only teaches identity. `factpy.SDKStore()` (current) tells users HOW they encounter it (the SDK), not WHAT it is.
- **F1 (collision in `kernel.sdk`):** clean. `grep -rn "FactGraph" src/ docs/ examples/` returned zero hits at HEAD `f04d25d`. `kernel.sdk.__all__` length 34 unchanged.
- **F2 (substrate ambiguity):** clean for top-level user-facing surface. Adjacent name `kernel.audit.evidence_graph.EvidenceGraph` (audit substrate; durable as `audit/evidence_graphs.jsonl`; queryable via `AuditQuery.get_candidate_evidence_graph()`) is **not** in `factpy.__all__` — lives in `kernel.audit` advanced-importable surface only. Different word ("Fact" vs "Evidence"), different package, different concept (`EvidenceGraph` is per-candidate audit DTO; `FactGraph` is top-level user-facing entrypoint to the knowledge graph). Users encountering `from factpy import FactGraph` do not naturally encounter `EvidenceGraph`.
- **F3 (industry alignment, recategorized as evidence per §0, NOT template):** Convention 3 (descriptive class name distinct from package name) is the dominant Python pattern for non-hosted-service libraries (`networkx.Graph`, `sqlalchemy.Session`, `pandas.DataFrame`, `pydantic.BaseModel`, `requests.Session`). **The mild Fact-prefix overlap with `factpy` package name is NOT a Python-ecosystem convention violation.** Go's "avoid stutter" rule (effective_go + Google Go Style Guide) is formally documented; Python has no equivalent PEP. Major Python libraries explicitly use same-morpheme repetition: `tensorflow.Tensor`, `pyspark.sql.SparkSession`, `pyspark.SparkContext`, `pyparsing.ParserElement`. In these patterns the repeated morpheme strengthens (rather than dilutes) the abstraction's identity — `Tensor` IS the core abstraction of `tensorflow`; `SparkSession` IS the core abstraction of `pyspark`. `FactGraph` follows the same pattern.
- **F4 (backwards-compat, defers to §5.4):** `SDKStore` callable surface stays per §0 thesis hard-constraint. The relationship between `FactGraph` and `SDKStore` (literal alias `FactGraph = SDKStore`, subclass, wrapper, or replacement-with-deprecation) is determined at §5.4. The §5.3 lock only commits to the user-facing class name — not to how it integrates with the existing `SDKStore` class.

**Implications for §5.4 + §5.1 (recorded; not pre-locking):**

- **§5.4 (compat strategy):** since `SDKStore` is part of an established `SDK*` family (also `SDKBatchTx`, plus descriptive siblings `EntitySnapshot` / `FieldAssertions` / `AssertionNamespace` / `EntityEditor` per `kernel.sdk.facade`), wholesale rename is high-cost. §5.4 likely lands on permanent dual surface: `FactGraph` as canonical user-facing name; `SDKStore` callable for back-compat. §5.4 falsifier confirms.
- **§5.1 (shape evaluation):** subsequent shape evaluation uses `FactGraph` as the new top-level entrypoint name. Candidate shape D (replacement) and shape F (hybrid) become more naturally framed under `FactGraph`. Candidate shape A (status quo) trivially applies if `FactGraph` is a literal alias of `SDKStore`. Candidate shape B (alias-only namespace overlay) and E (new `Client` class) are now more sharply distinguished — E is essentially "new top-level name + nested namespaces", which under §5.3 lock becomes "FactGraph with nested namespaces".
- **`EntitySnapshot.assertions` prior art** (`src/kernel/sdk/facade.py:102-217`) demonstrates that nested namespace under a top-level class is an established pattern in SDK using `__getattr__` + `FrozenSnapshotError`. Sub-namespacing for `FactGraph` (if §5.1 elects) can reuse this pattern rather than invent.

**Rejected industry-alignment framings:**

- "Match OpenAI eponymous (`factpy.FactPy()`)" — wrong category signal per F0; eponymous in Python is reserved for hosted-service SDKs and web frameworks.
- "Match Stripe / boto3 module-level functions (`factpy.from_classes(...)`)" — pushes the class-name question down without resolving it; user still ends up holding some class instance.
- "Match SQLAlchemy `Session`" — teaches pattern not domain; FactPy has no commit/rollback semantics so the migration knowledge partially misleads.

**Package-import naming (`factpy` vs `kernel.sdk`):**

The reference bundle ([README §Verification log Round 9](../../references/working/post-routemap-direction-selection-input/README.md)) explicitly defers `import naming (factpy vs kernel.sdk)` as a separate parallel question. §5.3 commits **only** to the class name `FactGraph`. The package-import side is its own decision (out of §5.3 scope; may surface in §5.5 docs/quickstart impact or §5.8 version stamping).

### 5.4 Compatibility / deprecation strategy

**Question:** How are existing flat-method users handled?

**Thesis-derived default (per §0):** **Never break the flat `SDKStore.<method>` surface that 5 immutable Path B snapshots already shipped.** Compatibility is a hard constraint, not a goal. Any candidate that breaks the flat surface (B / C / D below) requires its **own dedicated falsifier pass** justifying the break — the namespace decision in §5.2 cannot imply it.

Candidates:

- **(A) Permanent dual surface** — flat methods stay forever, new shape is additive. Zero breakage; surface area grows. **Default under thesis** unless §5.7 falsifier explicitly argues otherwise.
- **(B) Deprecation warnings + grace period** — flat methods emit `DeprecationWarning` for N versions, then removed. Predictable breakage path. **Requires standalone falsifier per thesis.**
- **(C) Hard cutover at v0.2** — flat methods removed at next major; redesign is the canonical shape. Highest breakage. **Requires standalone falsifier per thesis.**
- **(D) Tier-based** — flat L methods stay (since they're newest and in published refs); pre-L flat methods get deprecated/removed. Mixed strategy. **Requires standalone falsifier per thesis.**

**Falsifiers required:**

- F1 — Inventory of flat-method callsites in (a) `examples/`, (b) `kernel/tests/test_sdk_*.py`, (c) any external user code we know about. Counts inform breakage surface.
- F2 — `feedback_narrow_public_api` says expand surface only when scope requires it. Does adding deprecation infrastructure (warnings, version stamps, removal schedules) qualify as "scoped"?
- F3 — Path B immutability constraint: published L milestone snapshots' callsites are in their archived test files; those don't move. The compatibility question is purely about NEW user code post-redesign.

#### 5.4 Decision (locked 2026-05-09): Option 2 — Permanent additive aliases + docs prefer new taxonomy

**Default hypothesis (per user direction):** Flat `SDKStore.<method>` remains permanently callable; `FactGraph` + teaching taxonomy can only be additive unless a falsifier proves a breaking migration is necessary.

**5 strategies evaluated** (per user instruction):

| # | Strategy | Compat-honoring | F0 lever (taxonomy teaching gain) | Migration cost | User signal needed | Verdict |
|---|---|---|---|---|---|---|
| 1 | Permanent additive aliases, **no deprecation, no docs preference** | ✅ | ⚠️ Weak — no editorial preference; flat + taxonomy compete equally in docs | Zero | Already met for additive | Underdelivers thesis F0 |
| 2 | **Additive aliases + docs prefer new taxonomy** (this lock) | ✅ | ✅ Strong — quickstart + notebooks + API surface lead with taxonomy; flat documented as foundational/supported | Medium (docs rewrite is the teaching investment) | Already met (per `feedback_sdk_ergonomics_redesign_target`) | **Locked** |
| 3 | Soft deprecation in docs only ("deprecated; use taxonomy") | ⚠️ Implies removal | Stronger editorial signal | Same as Option 2 | None for "deprecated" framing | Rejected — see falsifier F-no-removal-plan |
| 4 | Runtime `DeprecationWarning` (per existing `row_format='tuple'` precedent at `store.py:2133-2141`) | ⚠️ Adds noise | Strong (forces user attention) | High — every flat-method callsite emits warnings; tests/notebooks/downstream consumers all noisy; Path B published L tests don't expect warnings | None for flat removal | Rejected — see falsifier F-noise-cost |
| 5 | Replacement / hard deprecation (flat removed at v0.2) | ❌ Violates §0 thesis hard-constraint | Strongest eventually | Highest — 23 test files + Path B audit confusion | Per `#6`, none — Batch 8 falsifier #18 PARTIAL ("not now") still holds | Rejected — violates compat hard-constraint without standalone falsifier |

**Falsifier evidence per rejected option:**

- **F-no-removal-plan (rejects Option 3):** "Deprecated" semantically implies "will be removed someday". Per `#6 — no outward compat without user signal` (cited 30_recommendation.md:95 lessons quote: "v0.1.3 disable_condition 实现时, 我推荐扩 SDKStore.evaluate(disabled_locators=...) kwarg 'for consistency'; 用户改成内部 _evaluate_with_overlay-style 路径") and Batch 8 §5.5.5 falsifier #18 PARTIAL ("not now"), there is no concrete user signal demanding flat-method removal. Marking flat methods "deprecated" without a removal plan misleads users who reasonably ask "when will this break?" and creates a worse contract than honest "supported foundational API".

- **F-noise-cost (rejects Option 4):** The existing `row_format='tuple'` `DeprecationWarning` at `store.py:2133-2141` was justified because tuple-mode and dict-mode produced **different return shapes** — runtime warning steered users away from a behaviorally distinct legacy mode. Flat-method-vs-nested-method is **NOT that case**: both produce identical results (per Shape 2 alias semantics). Adding `DeprecationWarning` to every flat method:
  - Makes 23 `test_sdk_*.py` files emit warnings on every call (hundreds of warnings per test run); tests using `pytest.filterwarnings('error')` start failing.
  - Path B published L snapshot tests (immutable refs at `d6716a0` / `acb5a6e` / `d658390` / `cb6d3bd` / `d4ceb3e`) were authored without warning expectations — their test invariants assume clean stdout/stderr; runtime warnings retroactively complicate test review.
  - Notebook execution emits warnings at every cell that calls flat methods.
  - User direction explicit: "Runtime warnings are likely too noisy for a library whose flat surface is already valid and published." Source-grounded — confirmed by the runtime-noise cost above.

- **F-compat-violation (rejects Option 5):** Per §0 thesis hard-constraint, "compat is a hard constraint". Per §5.4 thesis-derived default, options that break flat surface require standalone falsifier. No such falsifier surfaces — the user's signal is for the redesign to teach, not for flat removal. Path B published snapshots ship the flat surface; their immutability means flat removal would break retroactive auditability.

**Falsifier check on locked Option 2:**

- **Compat hard-constraint:** ✅ Preserved. Flat methods stay permanently callable; no DeprecationWarning, no removal plan. 23 `test_sdk_*.py` files unchanged. Path B published snapshots' tests stay green retroactively.
- **`#6 — no outward compat without user signal`:** ✅ Honored. The new surface (taxonomy aliases) is additive only, triggered by explicit user signal (`feedback_sdk_ergonomics_redesign_target`). Flat surface is not modified.
- **F0 thesis legibility:** ✅ Achieved via docs lever — quickstart + notebooks + API surface docs lead with `FactGraph.<namespace>.<method>`; new users encounter the teaching taxonomy first; existing users on flat methods continue working without surprise.
- **Path B immutability:** ✅ Preserved. The 5 published L snapshots ship at `d6716a0` / `acb5a6e` / `d658390` / `cb6d3bd` / `d4ceb3e` with flat-only docs; under Option 2, current docs evolve forward to lead with taxonomy, but published snapshots stay frozen with their original flat-only framing.
- **Maintenance liability check:** taxonomy aliases delegate to flat methods via attribute-access pattern (per `EntitySnapshot.assertions` prior art at `kernel/sdk/facade.py:102-217`); maintenance cost is near-zero per added namespace because there's no separate implementation. Tests stay on flat methods (no test churn). New parity tests for nested-form aliases are additive.
- **§5.7 ship-at-all preserved:** Option 2 lock is conditional on shipping. If §5.7 elects "no change" (Shape 1), Option 2's docs preparation doesn't ship; flat surface stays as-is.

**Decision rationale (per user):** "I expect option 2 to be strongest: it gives the redesign teaching value without breaking published L surfaces or turning current tests into migration churn. Runtime warnings are likely too noisy for a library whose flat surface is already valid and published." Confirmed by source-grounded falsifier evidence above.

**Locked compatibility strategy:**

- Flat `SDKStore.<method>` callable permanently; **no deprecation, no removal plan, no runtime warnings**.
- `FactGraph` + teaching taxonomy materializes as **additive** runtime aliases (under §5.7-conditional Shape 2 or Shape 3 rollout).
- Aliases delegate to flat methods via property/`__getattr__` namespace pattern (per `EntitySnapshot.assertions` prior art).
- **Docs / quickstart / notebooks lead with new taxonomy** as the preferred form for new code; flat methods documented as "supported foundational API" (NOT "deprecated").
- API surface docs (`kernel/sdk/docs/04_api_surface.md` + `.en.md`) reorganize to present taxonomy first, with cross-reference to flat-method foundations.
- Tests: existing flat-method tests stay verbatim (no churn); new nested-form parity tests added under §5.9 (each alias's result equals flat-method result).
- Path B published L snapshots stay immutable with their original flat-only docs framing — current/future docs evolution is forward-only on this design branch and downstream rollouts.

**Alias implementation pattern (locked):** sub-namespace attributes use the existing `views` precedent — property returning a private namespace class (e.g., `_SDKWhatIfManager`, `_SDKWriteManager`) with read-only methods that delegate to flat `SDKStore.<method>`. No `__getattr__` magic; explicit attribute methods for static analyzability + IDE autocomplete. Same pattern G2 used to build `kernel/sdk/shells/` subpackage at G2 §5.5 lock.

**Implications for downstream §5.x:**

- **§5.5 (docs/quickstart impact):** SUBSTANTIAL — docs rewrite is the F0 teaching investment. README quickstart, 4 chaptered notebooks, 04_api_surface.md (CN/EN), application overview docs all evolve to lead with `FactGraph.<namespace>.<method>` taxonomy. Flat-method documentation becomes the "foundational API reference" section.
- **§5.6 (aliases vs replacement):** RESOLVED implicitly by §5.4 lock — aliases. Section becomes residual cleanup or absorbed into §5.4.
- **§5.7 (ship-at-all):** the question becomes "is the docs rewrite + alias surface investment worth the F0 legibility gain?" — F0 (Shape 3 strong) vs F4 (medium docs cost) weighed against `feedback_narrow_public_api` "default to internal/contained mechanisms". §5.7 still has authority to elect Shape 1 (no change).
- **§5.9 (tests + invariants):** existing tests stay; new alias-form parity tests added (each alias path computes identical result to flat); sub-namespace property invariants (read-only enforcement, alias-vs-flat parity, no `__all__` length change).

### 5.5 Docs / quickstart impact

**Framing (per user direction):** Documentation is the **primary delivery vehicle** for the teaching taxonomy. Since §5.4 rejects deprecation/warnings, docs must make the new shape canonical without calling the flat shape obsolete. Key decision: which docs become taxonomy-first, and which simply record alias parity.

**Question:** What docs change at redesign release?

Candidate scope:

- README CN + EN (top-level + module-level)
- `kernel/sdk/docs/04_api_surface.md` + `.en.md`
- `kernel/sdk/docs/00_user_guide.md` + `.en.md`
- `kernel/sdk/docs/01_alignment_matrix.md` + `.en.md`
- `kernel/sdk/docs/02_readwrite_and_ingest.md` + `.en.md`
- `kernel/sdk/docs/03_rules_and_derivations.md` + `.en.md`
- `kernel/sdk/docs/05_cn_en_consistency_checklist.md`
- `kernel/application/docs/01_overview.md` + `_en.md`
- 4 notebooks under `examples/`
- `examples/round_story_full_demo.py`
- Any consumer-facing migration guide (new file?)

**Falsifiers required:**

- F1 — Total doc + example file count touched per candidate redesign shape.
- F2 — Whether a separate "v0.1 → v0.2 migration guide" file is warranted, or whether release notes suffice.
- F3 — Whether L Direction archive blueprints need any retroactive note (probably not — they're immutable historical record; but check).

#### 5.5 Decision (locked 2026-05-09): per-surface treatment with taxonomy-first SDK docs

**Source-grounded inventory** (HEAD `0ff394f`; `grep -cE "(SDKStore|sdk\.[a-z_]+)"`):

| Surface | Refs (CN+EN) | Treatment | Rewrite cost |
|---|---|---|---|
| `README.md` + `.en.md` | ~14 (4 quickstart calls + ~10 overview) | **Taxonomy-first** quickstart + overview update; flat compat acknowledged | SMALL |
| `kernel/sdk/docs/00_user_guide.md` + `.en.md` | **319** (162+157, largest single rewrite surface) | **Taxonomy-first** primary teaching walk-through; section structure already aligns naturally with §5.2 taxonomy (schema/read/write/eval); flat compat noted at section headers | LARGE — primary F0 teaching investment |
| `kernel/sdk/docs/04_api_surface.md` + `.en.md` | 38 (19+19) | **Taxonomy-canonical reference** + flat-method reference as compatibility section (NOT "deprecated") | MEDIUM |
| `kernel/sdk/docs/02_readwrite_and_ingest.md` + `.en.md` | 72 (36+36) | **Taxonomy-first** examples (`fg.write.set/add`, `fg.schema.ingest`); flat compat noted | MEDIUM |
| `kernel/sdk/docs/03_rules_and_derivations.md` + `.en.md` | 47 (25+22) | **Taxonomy-first** examples (`fg.eval.run/evaluate`, `fg.what_if.check`); flat compat noted | MEDIUM |
| `kernel/sdk/docs/01_alignment_matrix.md` + `.en.md` | 24 (12+12) | Add taxonomy-path column or note alongside existing flat-path matrix | SMALL |
| `kernel/sdk/docs/05_cn_en_consistency_checklist.md` | 2 | Update parity checklist to verify CN+EN both adopt taxonomy | SMALL |
| `kernel/application/docs/01_overview.md` + `_en.md` | 18 (9+9) | **SDK-presentation note only** — brief paragraph noting `FactGraph.<namespace>.<method>` taxonomy as SDK ergonomic surface; cross-ref to SDK docs; application content unchanged (per user: "records the taxonomy as SDK presentation, not application truth") | SMALL |
| `examples/0[1-4]_*.ipynb` (4 notebooks) | **1** (only `diff_proof_frames` in 04) | **Mostly unchanged** per user direction; conditional 1-line update in 04 if Shape 2/3 ships (`fg.audit.diff_proof_frames(...)`) | NEGLIGIBLE |
| `examples/round_story_full_demo.py` | 0 (uses `kernel.application` directly) | **Unchanged** | ZERO |
| `examples/README.md` | n/a (chapter index) | Possibly minor update to chapter descriptions if notebooks change | SMALL |
| Path B published L snapshots (5 immutable refs) | n/a (frozen) | **Untouched** — published snapshots stay with original flat-only docs framing; current/future docs evolution is forward-only on design branch | N/A |
| L archive blueprints (G1-G5) | n/a | **No retroactive notes** — historical record stays as-shipped per Path B immutability + F3 verdict | N/A |

**Migration guide decision:** **NO separate v0.1 → v0.2 migration guide file.** Per §5.4 lock there's no breaking migration; flat surface stays callable. The taxonomy-first docs IS the migration guidance — users see new examples and discover the taxonomy organically. Release notes (or commit message at publish time) suffice for the transition note.

**3-tier doc surface classification (codified):**

1. **Taxonomy-first surfaces** (lead with `FactGraph.<namespace>.<method>`): README, 00_user_guide, 04_api_surface, 02_readwrite_and_ingest, 03_rules_and_derivations, 01_alignment_matrix.
2. **SDK-presentation surfaces** (record taxonomy as SDK presentation, not own truth): application/01_overview.
3. **Compatibility/reference surfaces** (preserve flat as primary content; note taxonomy as alternative): within taxonomy-first docs, the "Compatibility reference" or "Foundational API" sections; NOT separate "deprecated" labels.

**Untouched surfaces:**

- Notebooks 01-04 (Tier-2 advanced importable usage; bypass `SDKStore`); conditional 1-line update in 04 only.
- `round_story_full_demo.py` (uses `kernel.application` directly; no SDK methods).
- Path B published L snapshots (immutable per `project_release_branch_invariants`).
- L archive blueprints (historical record per Path B immutability).
- All `kernel.application` / `kernel.audit` / `kernel.core` runtime + module docs — taxonomy is purely SDK-outward; no application/audit/core narrative changes.

**Falsifier verdicts:**

- **F1 (total doc + example file count touched):** under Option 2 Shape 2/3 rollout, ~12 doc files (CN/EN pairs of README + 5 SDK docs + 1 application overview + 1 checklist) become taxonomy-aware; 0 notebooks structurally rewritten (only 1-line in 04 if shipping); 0 application/audit/core docs modified beyond SDK-presentation note. Total surface bounded.
- **F2 (separate migration guide?):** **NO** — §5.4 has no breaking migration; taxonomy-first docs ARE the guide; release notes at publish suffice.
- **F3 (retroactive note on L archive blueprints?):** **NO** — Path B immutability + L archive blueprints are historical records of as-shipped state; current docs evolution is forward-only; future Path B combined snapshot picks up new docs naturally.

**§0 thesis F0 alignment check:**

- New users land on README → see taxonomy-first quickstart → form correct mental model from line 1.
- New users drill into 00_user_guide → see section-by-section taxonomy walk-through aligned with conceptual layers.
- API reference users → 04_api_surface gives taxonomy-canonical view + flat compat reference; both forms remain documented.
- Existing users on flat methods → encounter unchanged compatibility/reference sections; no surprise.
- F0 teaching achieved without runtime cost; flat-method users not penalized.

**§5.4 alignment check:**

- "Flat as foundational, NOT deprecated" framing materializes in every doc surface: compat sections labeled "Foundational API" / "Compatibility reference", not "Deprecated".
- No `DeprecationWarning` references in any doc (per §5.4 F-noise-cost).
- Taxonomy is the **preferred** form for new code; flat is **supported foundational** API.

##### 5.5.6 Module-internal docs with peripheral SDK references (extension 2026-05-09)

Per user observation "every module has a docs/ directory; some content may be affected", a thorough survey via `find src/kernel -type d -name docs` surfaced 9 docs directories (vs the 2 covered in original §5.5 lock). Re-grep `(SDKStore|sdk\.[a-z_]+|kernel\.sdk)` across all 9 found 5 additional surfaces with peripheral SDK references missed in the original lock:

| Surface | Refs | Nature | Treatment | Rewrite cost |
|---|---|---|---|---|
| `kernel/application/docs/README.md` | 1 (line 7) | Routing note: "如果你是在写普通 Python product code... 优先阅读 `src/kernel/sdk/docs/` 并从 `kernel.sdk` 开始" | **UNCHANGED** — pointer survives because SDK docs (now taxonomy-first) is the right destination | ZERO |
| `kernel/application/walker/docs/README.md` | 1 (line 126) | Negative assertion: "No SDK shell or `kernel.sdk` import" | **UNCHANGED** — affirms walker is Tier 2 advanced-importable; assertion stays valid | ZERO |
| `kernel/adapters/docs/02_problog_adapter.md` | 1 (line 195) | Adapter usage example: `sdk.evaluate(..., mode="problog", engine_options={"timeout": 15})` | **CONDITIONAL** — flat-form OK as foundational; if Shape 2/3 ships, optionally show alongside `fg.eval.evaluate(..., mode="problog", ...)` form. Not load-bearing teaching surface. | NEGLIGIBLE (1 line) |
| `kernel/adapters/docs/03_pyreason_adapter.md` | 6 (mixed) | (a) DSL imports `from kernel.sdk.dsl.expr import LogicVar, Pred` + `kernel.sdk.dsl.rule import Rule` (lines 149-150) — **taxonomy doesn't change DSL imports**; (b) prose mechanism descriptions `SDKStore.evaluate` (lines 9, 237) — describes underlying contract; (c) usage examples `sdk.evaluate(...)` (lines 221, 261) — adapter integration demos | **MOSTLY UNCHANGED**: DSL imports stay (orthogonal to redesign); prose mechanism descriptions stay flat (describe foundational contract per §5.4 lock); 1-2 usage examples conditionally taxonomy-form if Shape 2/3 ships | SMALL (1-2 lines) |
| `kernel/core/docs/04_public_contract_v1.md` | 3 (lines 33-36) | **Public contract anchor**: `SDKStore.run(...)`, `SDKStore.evaluate(...)`, `SDKStoreError` listed as v1 public contract surface | **STAYS FLAT + ADD TAXONOMY CROSS-REF NOTE** — flat `SDKStore.<method>` IS the permanent contract per §5.4 lock; contract document correctly anchors flat as foundational; adds brief "and now also reachable as `FactGraph.eval.run/evaluate` per §5.5 SDK taxonomy" cross-ref. The contract document is one of the few places where flat-form is NOT just compatibility-reference — it's the canonical contract anchor. | SMALL (1 line cross-ref note) |

**4th treatment tier added to §5.5 classification:**

4. **Module-internal docs with peripheral SDK references** (mostly unchanged; flat refs in mechanism prose stay as foundational; usage examples may update conditionally; **public contract anchor stays flat + adds taxonomy cross-ref**).

**Refinement to original §5.5 lock for `application/docs/01_overview`:** the original lock said "brief paragraph noting taxonomy + cross-ref; own content unchanged". Verified at `01_overview.md:175-180` — the L methods enumeration paragraph (line 177, ~1300 chars) is dense and references all 9 L methods by their flat `sdk.<method>` form to describe each shell's underlying mechanism. Refined treatment: enumeration **stays flat** (it's describing the foundational contract / mechanism; flat form correctly anchors what the application runtime is consumed by); brief introductory sentence added: "Under §5.5 SDK taxonomy, these are also reachable as `FactGraph.what_if.check` / `FactGraph.what_if.fact_overlay.check` / `FactGraph.what_if.rule.disable` / `FactGraph.audit.diff_proof_frames` etc.; flat `SDKStore.<method>` form retained below as the foundational contract." Effectively SDK-presentation-only (bridge note), but with taxonomy enumeration appended once for completeness.

**Source-grounded falsifier verdict for §5.5.6 extension:** total additional surface = 5 files but **4 are zero-or-negligible-cost** (routing note + negative assertion + 1 adapter example line + 1 contract cross-ref note); the 5th (`pyreason_adapter`) is small (1-2 example lines). The original §5.5 lock's 12-doc-files-become-taxonomy-aware count was concentrated in actual SDK teaching surfaces; module-internal docs reach the user via routing/contract paths and stay primarily flat-form correct.

**Updated total rewrite cost surface (post-§5.5.6 extension):**

```
TAXONOMY-FIRST (primary teaching investment, ~12 files):
  - README.md + .en.md
  - kernel/sdk/docs/00_user_guide.md + .en.md          [319 refs]
  - kernel/sdk/docs/04_api_surface.md + .en.md
  - kernel/sdk/docs/02_readwrite_and_ingest.md + .en.md
  - kernel/sdk/docs/03_rules_and_derivations.md + .en.md
  - kernel/sdk/docs/01_alignment_matrix.md + .en.md

SDK-PRESENTATION-ONLY (brief note + cross-ref):
  - kernel/application/docs/01_overview.md + _en.md    [enumeration stays flat; brief taxonomy intro added]

PUBLIC-CONTRACT ANCHOR (stays flat + adds taxonomy cross-ref):
  - kernel/core/docs/04_public_contract_v1.md          [+1 cross-ref line]

CONSISTENCY MAINTENANCE:
  - kernel/sdk/docs/05_cn_en_consistency_checklist.md  [verify CN+EN parity]

CONDITIONAL UPDATES (only if Shape 2/3 ships):
  - examples/04_round_persistence_diff.ipynb           [1 line: diff_proof_frames]
  - kernel/adapters/docs/02_problog_adapter.md         [1 example line, optional]
  - kernel/adapters/docs/03_pyreason_adapter.md        [1-2 example lines, optional]

UNCHANGED:
  - notebooks 01/02/03 (Tier-2 advanced importable usage)
  - examples/round_story_full_demo.py
  - examples/README.md (possibly minor)
  - kernel/application/docs/README.md (routing note survives)
  - kernel/application/walker/docs/README.md (negative assertion stays valid)
  - kernel/audit/docs/* (0 SDK refs)
  - kernel/authoring/docs/* (0 SDK refs)
  - kernel/core/docs/* except 04_public_contract_v1 (architecture/quality/roadmap have 0 refs)
  - kernel/core/annotation/docs/README.md (0 SDK refs)
  - kernel/adapters/pyreason/docs/README.md (0 SDK refs)
  - L archive blueprints (G1-G5)
  - Path B published L snapshots (immutable)
  - Sacred branches (master, v0.1-oss-prep)

NOT CREATED:
  - Separate v0.1 → v0.2 migration guide file (no breaking migration; release notes suffice)
```

**Locked per-surface treatment (codified, post-extension):**

```
TAXONOMY-FIRST (lead with FactGraph.<namespace>.<method>):
  - README.md + README.en.md
  - kernel/sdk/docs/00_user_guide.md + .en.md          [LARGEST: 319 refs]
  - kernel/sdk/docs/04_api_surface.md + .en.md         [API ref: taxonomy-canonical + flat-compat reference]
  - kernel/sdk/docs/02_readwrite_and_ingest.md + .en.md
  - kernel/sdk/docs/03_rules_and_derivations.md + .en.md
  - kernel/sdk/docs/01_alignment_matrix.md + .en.md    [add taxonomy column/note]

SDK-PRESENTATION-ONLY (brief note + cross-ref; own content unchanged):
  - kernel/application/docs/01_overview.md + _en.md

CONSISTENCY MAINTENANCE:
  - kernel/sdk/docs/05_cn_en_consistency_checklist.md  [verify CN+EN parity]

CONDITIONAL UPDATES (only if Shape 2/3 materializes):
  - examples/04_round_persistence_diff.ipynb           [1 line: diff_proof_frames]

UNCHANGED:
  - notebooks 01/02/03 (Tier-2 advanced importable usage)
  - examples/round_story_full_demo.py
  - examples/README.md (possibly minor)
  - All kernel.application / kernel.audit / kernel.core runtime docs
  - L archive blueprints (G1-G5)
  - Path B published L snapshots (immutable)
  - Sacred branches (master, v0.1-oss-prep)

NOT CREATED:
  - Separate v0.1 → v0.2 migration guide file (no breaking migration; release notes suffice)
```

**Implications for downstream §5.x:**

- **§5.6 (aliases vs replacement):** RESOLVED implicitly by §5.4 + §5.5 — aliases (delegate to flat methods); flat is canonical implementation; new taxonomy is editorial canonical via docs lever. Section can be marked resolved/absorbed.
- **§5.7 (ship-at-all):** weighs the docs rewrite cost (concentrated in `00_user_guide` 319 refs + 5 other taxonomy-first docs) against F0 legibility gain. Notebook impact is now confirmed as NEGLIGIBLE per §5.5 inventory; primary cost is doc rewrite. §5.7 still has authority to elect Shape 1 (no change) which would void the §5.5 rewrite — that voiding is acceptable since §5.5's lock is contingent on shipping the redesign.
- **§5.9 (tests + invariants):** docs don't have tests in the runtime sense, but the §5.5-locked structure can be enforced by:
  - Doc-rewrite parity test (CN/EN both lead with taxonomy in same sections)
  - Lint check that taxonomy-first docs don't accidentally introduce "deprecated" labels on flat methods
  - 04_api_surface taxonomy-canonical + flat-compat-reference structural check

### 5.6 Aliases vs replacement

**Question:** When the redesign ships, is the new shape an **alias overlay** (calls flat methods underneath) or a **replacement implementation** (flat methods become aliases that call the new shape)?

This is essentially a "where does the canonical implementation live" question:

- **Alias overlay**: namespace methods are thin wrappers calling flat `SDKStore.<method>`. Zero behavior change. Easy to prove correctness (same code path).
- **Replacement**: canonical implementation moves to the namespace methods; flat methods become wrappers calling the namespace. Same eventual behavior but redirected internals.

**Falsifiers required:**

- F1 — Internal-test impact: how many `kernel/tests/test_sdk_*.py` files reference flat method internals (e.g., `from kernel.sdk.shells.check import sdk_check` for runtime patches)? If many, replacement requires test updates; alias overlay does not.
- F2 — Sibling discipline at 9-shell scope: does the new shape introduce 9-shell-Sibling violations? (e.g., does `sdk.what_if.diagnose(...)` end up calling `sdk_check` indirectly through the namespace? It shouldn't, but verify.)
- F3 — `kernel.sdk.__all__` impact: does either approach affect the length-34 invariant?

### 5.7 Whether redesign ships at all

**Question:** Given the falsifier outcomes from §5.1-§5.6, is the redesign actually worth shipping?

This is the **honest meta-question**. **Under §0 thesis, the test is: does the chosen shape produce a measurable legibility gain over the flat surface, large enough to justify the migration cost?** The user has flagged a direction; the falsifier may surface that:

- The flat surface is conceptually fine for FactPy's "session over knowledge graph" model (per SQLAlchemy precedent), and **F0-legibility on the flat surface is acceptable** when paired with grouped documentation.
- Migration cost is high relative to the ergonomic win.
- No consumer signal exists (no recorded user complaint, no notebook friction beyond what the user noted in `feedback_sdk_ergonomics_redesign_target`).
- The post-L moment is better spent on a different post-L blueprint (publish-line hygiene, post-publish verification on G1-G4 not yet done, dialog agent, etc.).

**Falsifiers required:**

- F1 — Recap §5.1-§5.6 falsifier outcomes; sum up the costs vs benefits **using F0-legibility as the primary axis** per §0.
- F2 — Source-ground "no" path: under what conditions would "ship nothing" be correct? Document this honestly.
- F3 — If "ship something", what is the smallest version (alias overlay only, no flat-method changes, no docs touched beyond brief mention)?

A **legitimate `scoped` outcome** for this blueprint is "no SDK surface change; record findings + close" — explicitly preserved by §0.3 ("does not pre-commit to nesting"). `feedback_narrow_public_api` is the standing principle.

#### 5.7 Decision (locked 2026-05-09): SHIP additive redesign

**Binary decision (per user direction):** Does the teaching value justify shipping additive `FactGraph` + taxonomy aliases now, or should the blueprint close as research-only?

**Verdict: SHIP additive redesign.**

##### 5.7.1 F0 vs F4 weighing (source-grounded recap of §5.1-§5.5 + §5.5.6)

| Axis | Evidence | Verdict |
|---|---|---|
| **F0 (legibility gain)** — does the redesign produce measurable `dir(FactGraph)` legibility improvement vs flat surface? | §5.2 locks 8 top-level + 2 sub-namespaces (`schema` / `read` / `write` / `eval` / `what_if`+`fact_overlay`+`rule` / `audit` / `package` / `views`); each namespace name immediately conveys conceptual layer; new user reads `dir(fg)` and forms accurate model from first contact, no docstring lookup; `FactGraph` (§5.3) resets mental model from "SDK store" to "fact graph"; user-facing teaching surfaces (`00_user_guide` + 5 SDK docs + README) lead with taxonomy under §5.5 lock | **STRONG GAIN** — coherent taxonomy + bridge name + docs lever |
| **F4 (migration cost)** — what's the actual rewrite cost under §5.4 + §5.5 + §5.5.6 locks? | Runtime: additive only (property + manager class pattern per `views` precedent at `store.py:198-200`); zero flat-method changes; zero test churn (existing `test_sdk_*.py` 23 files unchanged; new alias-form parity tests added per §5.9); zero `kernel.application` / `kernel.audit` / `kernel.core` runtime changes; zero Path B published L snapshot modifications. Docs: ~12 SDK doc files become taxonomy-aware (concentrated in `00_user_guide` 319 refs as primary teaching investment); 1 SDK-presentation bridge note (application overview); 1 cross-ref note (public contract anchor); 0-3 conditional adapter/notebook example edits. No separate migration guide file. No `factpy` package rename (deferred to separate scoping if needed). | **BOUNDED** — primary cost is the `00_user_guide` rewrite (which IS the F0 teaching investment) |
| **Compat hard-constraint** | §5.4 Option 2 lock: flat `SDKStore.<method>` callable permanently; no deprecation, no removal plan, no runtime warning; aliases delegate via property/manager pattern | **PRESERVED** |
| **`#6 — no outward compat without user signal`** | User explicit signal per `feedback_sdk_ergonomics_redesign_target`; blueprint exists at user direction; redesign trigger met | **HONORED** |
| **Path B immutability** | 5 published L snapshots (`d6716a0` / `acb5a6e` / `d658390` / `cb6d3bd` / `d4ceb3e`) untouched; current docs evolve forward; impl branch isolation in force | **PRESERVED** |
| **Sacred branches** | `master` + `v0.1-oss-prep` untouched throughout | **PRESERVED** |

##### 5.7.2 "Ship nothing" path falsified (F2)

The "no change" path requires the F0 gain to be illusory or the F4 cost to be exhausting. Both fail:

- **F0 gain is real, not illusory.** The §5.2 falsifier verified that the 8-concept consolidation + Option B `what_if` split produces a strictly stronger `dir(fg)` legibility model than alphabetized 30 flat methods (`check_fact_overlay` interleaved with `explain_fact` / `conflicts` does not teach; `fg.what_if.fact_overlay.check` does). The `FactGraph` name reset (§5.3) eliminates the "SDK store" mental-model misdirection that `SDKStore` carries. These are concrete legibility gains, not aspirational ones.
- **F4 cost is bounded, not exhausting.** §5.5 source-grounded inventory: notebooks barely use SDK methods (1 mention total in 4 notebooks); `round_story_full_demo.py` has zero refs; module-internal docs mostly unchanged per §5.5.6 extension. Real rewrite is concentrated in `00_user_guide` (319 refs) — and that rewrite IS the F0 teaching investment, not an externality. Tests: zero churn under §5.4 lock. Runtime: additive aliases via established `views` precedent.

The "post-L moment is better spent on a different blueprint" framing also fails: the redesign is design-only on its own branch, sequential to L Direction's close-out, and the impl branch is isolated. It does not block other post-L work (publish-line hygiene, dialog agent, etc.) — those can run in parallel on their own branches.

##### 5.7.3 "Smallest shipping version" (F3)

The smallest defensible shipping version under current locks is **§5.5 Tier 1 (Taxonomy-first SDK docs) + minimal runtime aliases**:

- Runtime: `FactGraph` top-level class + 8 manager classes (one per top-level namespace) + 2 sub-manager classes (`fact_overlay`, `rule`) — all per `views` precedent property pattern
- Docs: 12 SDK doc files become taxonomy-aware (per §5.5 Tier 1)
- Tests: alias-form parity tests + sub-namespace property invariants (per §5.9 expected scope)
- Module-internal docs (`application/01_overview` bridge note + `core/04_public_contract` cross-ref + `adapters/03_pyreason` 1-2 example lines) — minimum-viable updates

The "ship nothing larger than this" question is answered: the shipping version IS this minimum-viable scope. There's no further compression available without sacrificing F0 teaching.

##### 5.7.4 Explicit non-commitments (per user direction)

The §5.7 lock is precise about what the redesign IS NOT, to prevent scope creep at impl time:

1. **NOT a replacement of `SDKStore`.** `SDKStore` class remains the canonical implementation behind the `FactGraph` taxonomy. `FactGraph` is the new top-level user-facing entrypoint name; whether it is a literal alias (`FactGraph = SDKStore`), thin subclass, or wrapper is an impl-time decision but is bounded by §5.4 lock (flat `SDKStore.<method>` callable permanently from both `SDKStore.foo()` and `FactGraph.foo()` semantics).
2. **NOT a deprecation of flat methods.** Per §5.4 lock: no `DeprecationWarning`, no removal plan, no "deprecated" labels in any doc. Flat methods are documented as **supported foundational API** in compatibility/reference sections within taxonomy-first docs.
3. **NOT a package rename to `factpy`.** Current import path `from kernel.sdk import ...` stays. The README:189 `import naming (factpy vs kernel.sdk)` question is **deferred to §5.8** (or a separate scoped blueprint). The §5.7 lock ships taxonomy under existing `kernel.sdk` package; if §5.8 elects a `factpy` rename, that is its own scoped decision with its own falsifier.
4. **NOT immediate implementation on the design branch.** Implementation work happens on the dedicated impl branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` (created at design HEAD per §6 design/impl branch isolation invariant). Workflow: scope-freeze (status `draft → scoped`) → impl branch rebases onto design HEAD → implementation phases land on impl branch only → publish authorization separate per `project_release_branch_invariants`.

##### 5.7.5 Implications for §5.8 + §5.9

- **§5.8 (version stamping):** the redesign ships additive surface in v0.1 line per `feedback_narrow_public_api` (additive surface in preview line is fine); whether to stamp with a v0.2 marker for branding signal is the §5.8 falsifier question. §5.7 ship verdict does not pre-decide §5.8.
- **§5.9 (tests + invariants):** alias-form parity tests (each `FactGraph.<namespace>.<method>(...)` result equals `SDKStore.<method>(...)` result); sub-namespace property invariants (read-only enforcement via `__setattr__` raising `FrozenSnapshotError` per `EntitySnapshot.assertions` precedent at `kernel/sdk/facade.py:102-217`); `kernel.sdk.__all__` length **stays 34** (taxonomy materializes as runtime attributes, not new top-level exports — `FactGraph` is a new export but only one entry; manager classes are private `_SDK*Manager` per `views` precedent and don't reach `__all__`); structural test that taxonomy-first docs don't accidentally introduce "deprecated" labels on flat methods (per §5.5 + §5.4 locks).

##### 5.7.6 Workflow advance

§5.7 lock advances workflow toward **scope-freeze (status `draft → scoped`)** after §5.8 + §5.9 lock. At scope-freeze:

1. Status flipped `draft → scoped` in blueprint header.
2. Impl branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` rebased onto design branch HEAD.
3. Implementation phases plan locked in §8.
4. Implementation work begins on impl branch only.
5. Publish authorization remains user-explicit per `project_release_branch_invariants`; sacred branches `master` + `v0.1-oss-prep` continue untouched.

### 5.8 Roadmap / version stamping

**Question:** If the redesign ships, what version number does it represent? Same `v0.1` preview line, or a `v0.2` minor / major bump?

**Falsifiers required:**

- F1 — Existing version conventions in this codebase: `v0.1-oss-prep`, `v0.1-l-g{1-5}-...`, `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-2026-05-08`. The pattern is `v0.1-<scope>-<date>`.
- F2 — Whether the redesign is "L hygiene continuation" (still v0.1 line) or "post-L major refactor" (v0.2 line).
- F3 — Path B 5th immutable snapshot is at v0.1; would a redesign produce a 6th v0.1 snapshot or start a v0.2 line?

#### 5.8 Decision (locked 2026-05-09): stay on v0.1 line; no v0.2 marker

**Default hypothesis (per user direction):** stay on v0.1 line; no v0.2 marker yet. Source-grounded against actual version metadata + branch convention + §5.7 ship-verdict's 4 non-commitments — all confirm.

**5.8.1 Source-grounded verification:**

- `pyproject.toml:7` — `version = "0.1.0"`. No `__version__` defined in any `kernel/__init__.py`, `kernel/sdk/__init__.py`, or other module init.
- No `CHANGELOG.md` / `RELEASES.md` / `HISTORY.md` file in the repo (verified `ls CHANGELOG* RELEASES* HISTORY*` returns no matches).
- Branch convention verified via `git branch -r`: 5 published L milestone snapshots all use `v0.1-l-g{N}-...-2026-05-08` pattern; 5 progressive Path B combined snapshots all use `v0.1-public-surface-helpers-walker-l-g1-...-l-g5-2026-05-08` pattern.

**5.8.2 Four key decisions locked (per user enumeration):**

##### (1) Does `FactGraph` enter `kernel.sdk.__all__`? **YES** — `__all__` length 34 → 35

**Rationale:** `FactGraph` is the canonical user-facing entrypoint per §5.3 lock. The §5.5-locked teaching surfaces (README quickstart, `00_user_guide`, `04_api_surface`, etc.) all use the form `from kernel.sdk import FactGraph`. Not exporting `FactGraph` would force users to use full path `kernel.sdk.store.FactGraph` (or wherever it lands), which contradicts the F0 teaching goal — the import line is the first thing a user sees.

`SDKStore` already in `__all__` (entry 30 of 34). Adding `FactGraph` alongside is purely additive — both names are exported; flat-call semantics work via either name (per §5.4 lock + §5.7 non-commitment #1 "NOT a replacement of `SDKStore`").

`__all__` semantic: 34 → **35**. Whether `FactGraph` is a literal alias (`FactGraph = SDKStore`), thin subclass, or wrapper is impl-time decision per §5.7 non-commitment #1 — but in all cases both names live in `__all__`.

**Manager classes (`_SDKWhatIfManager`, etc.) do NOT enter `__all__`.** Per `views` precedent at `store.py:66-104`, the existing `_SDKViewsManager` is private (underscore prefix) and is exposed only via `SDKStore.views` property. The 8 top-level managers + 2 sub-managers under `what_if` follow the same convention: private classes, not exported. Users reach them only through `FactGraph.<namespace>` attribute access.

**`__all__` length invariant update:** the 5 invariant files that currently assert length 34 (per `project_g{1,2,3,4,5}_published.md` memory + cumulative §6 invariants) need an update to assert length 35 at scope-freeze. The single-line increment is the additive-only acknowledgement that §5.8 stays on v0.1.

##### (2) Does any `__version__` or package metadata change? **NO**

**Rationale:** `pyproject.toml:7` stays at `version = "0.1.0"` (or whatever current point release is when impl lands). The redesign is additive surface within v0.1 line:

- No breaking change → no major/minor bump needed
- No bug fix that warrants point release
- Per `feedback_narrow_public_api`: additive surface in preview v0.1 is normal; not every additive landing demands a version stamp
- Project hasn't published any tagged release yet (verified — no CHANGELOG; current version `0.1.0` has been stable through L Direction's 5 milestone shipments)

**Decision:** no `__version__` definition added; no `pyproject.toml` version bump at redesign impl. If/when the project decides to publish a tagged release, that's a separate decision orthogonal to §5.8.

##### (3) Do docs call this v0.2? **NO** — call it "post-L SDK ergonomics redesign" within v0.1

**Rationale:** Branch naming pattern verified: project uses `v0.1-<scope>-<date>` for all post-L work (this design branch is `codex/v0.1-post-l-sdk-ergonomics-redesign-2026-05-09` — already follows convention). Calling it "v0.2" would imply breaking change or major shift; neither applies under §5.4 + §5.7 locks.

**Decision:** docs refer to this redesign as **"post-L SDK ergonomics redesign"** (or shorthand: "FactGraph taxonomy") — within v0.1 line. No "v0.2" framing in any user-facing surface.

##### (4) Does it need a release note entry? **YES** — in blueprint/docs only, not package version metadata

**Rationale:** No `CHANGELOG.md` / `RELEASES.md` exists in the repo. The blueprint itself + audit log + archived blueprint inventory (`docs/blueprints/archive/README.md`) ARE the canonical release record convention. Plus brief notes in:

- README.md / .en.md — "post-L SDK ergonomics redesign" line in the public boundary table
- `kernel/sdk/docs/04_api_surface.md` / `.en.md` — already documents L milestones; adds a redesign entry describing the taxonomy addition (in line with §5.5 taxonomy-first treatment)
- `kernel/core/docs/04_public_contract_v1.md` — already gets a taxonomy cross-ref note per §5.5.6 extension

**Decision:** release note materializes as:
1. The blueprint + audit log themselves (canonical record)
2. Archive inventory row at `docs/blueprints/archive/README.md` post-archive
3. Brief mention in README quickstart-section header + 04_api_surface intro + public_contract_v1 cross-ref note

NO standalone CHANGELOG.md created. NO `pyproject.toml` version metadata change. NO additional release-tracking infrastructure introduced — the blueprint+audit-log convention IS the release record.

**5.8.3 Path B snapshot naming (locked):**

Following the established convention verified above, the redesign snapshots will be:

- **Standalone:** `v0.1-post-l-sdk-ergonomics-redesign-<DATE>` (drop `codex/` prefix at publish; `<DATE>` is publish date in `YYYY-MM-DD` format).
- **Path B 6th immutable combined snapshot:** `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-post-l-redesign-<DATE>` — extends the 5th snapshot at `d4ceb3e` per Path B convention (6th immutable snapshot in the lineage).

Both names use `v0.1-` prefix consistent with the version-stamping decision. No `v0.2-` snapshot created.

**5.8.4 Falsifier verdicts:**

- **F1 (existing version conventions):** ✅ matches — `v0.1-<scope>-<date>` pattern continues; new snapshots follow exactly.
- **F2 (L hygiene continuation vs post-L major refactor):** the redesign is **L hygiene continuation** under §5.7 ship-verdict — additive surface only, no behavior change, no breaking change. Not a "post-L major refactor" because per §5.7 non-commitment #1 it is NOT a replacement of `SDKStore`, per #2 NOT a deprecation, per #3 NOT a package rename. v0.1 line stays.
- **F3 (Path B 6th snapshot vs v0.2 line):** **6th v0.1 snapshot** under existing Path B convention. No v0.2 line opened. The 5 prior Path B snapshots' immutability is preserved; the 6th is additive.

**5.8.5 What this lock does NOT decide:**

- **The eventual published version when the project tags a release.** That's a separate decision; redesign impl doesn't force the issue. Project may tag `0.1.0` or `0.1.1` or stay on `0.1.0` indefinitely; §5.8 only locks "the redesign itself doesn't bump version metadata".
- **The `factpy` vs `kernel.sdk` import naming question** (per §5.7 non-commitment #3 + README:189 reference bundle deferred question). If a future scoped blueprint elects a `factpy` package rename, that IS a v0.2-line decision and would be a separate version-stamping evaluation. §5.8 ships under existing `kernel.sdk` only.
- **Whether the §5.5 docs update to v0.2 framing if/when the package eventually bumps.** Future doc updates follow the project's actual published-version state at the time; §5.8 only fixes the redesign-impl version stamping at v0.1.

### 5.9 Tests + invariants

**Question:** What invariant / test changes does the redesign require?

If §5.1-§5.7 lands a no-change outcome: zero test/invariant changes (this blueprint produces only docs/research artifacts).

If §5.1-§5.7 lands an alias overlay (option B / E): need new tests asserting alias behavior parity with flat methods; need invariant updates for any namespace addition (5 invariant files all assert `__all__` length 34 — must hold).

If §5.1-§5.7 lands a replacement (option C / D): substantially more — every G1-G5 contract test that patches `kernel.sdk.shells.<x>.<y>` needs review for whether the patch path still resolves; thin-delegate invariants need updates.

**Falsifiers required:**

- F1 — Inventory of patch paths in existing G1-G5 contract tests. Count files affected per redesign option.
- F2 — Any `#P1` carve-outs needed for old invariant text that asserts "method exists at flat path"?
- F3 — Sibling discipline test pattern updates: 9-shell scope test patches all 8 prior sister `sdk_*` functions; does the redesign change function reference paths?

## 6. Boundaries and Invariants

(Provisional — finalized at scope-freeze. Inherited from L Direction.)

- **Core thesis (verbatim, per §0):** "The redesign should make the SDK namespace teach FactPy's conceptual model at first contact. Compatibility is a hard constraint, and industry SDK shapes are evidence, not templates." Every §5.x falsifier and every implementation-stage choice must be reducible to this thesis.
- **F0-legibility primacy.** `dir(client)` / IDE-autocomplete legibility against the §4.1 conceptual layering is the **first** falsifier axis for every shape candidate (§5.1, §5.2, §5.3). Migration cost (F4) and industry alignment (F3 in §5.3) are downstream weights, not entry gates.
- **Compat is a hard constraint, not a goal.** The flat `SDKStore.<method>` surface across 5 immutable Path B snapshots stays callable; any candidate that breaks it requires a standalone falsifier per §5.4 thesis-derived default.
- **§5.3 locked: top-level entrypoint class name is `FactGraph`** (sourced from chat-driven 4-round falsifier pass on 2026-05-09; `tensorflow.Tensor` / `pyspark.sql.SparkSession` / `pyparsing.ParserElement` Python precedent for Fact-overlap; `EvidenceGraph` substrate-audit name does NOT collide because it's not in `factpy.__all__`). Relationship with existing `SDKStore` class is §5.4 territory.
- **§5.2 locked: teaching taxonomy** — 8 top-level namespaces (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`) + 2 sub-namespaces (`what_if.fact_overlay`, `what_if.rule`); `from_schema_classes` (cls) + `batch` (cm) + 4 properties at top-level. Locked 2026-05-09 per user direction with all 5 placement decisions: `what_if` Option B split / `diff_proof_frames` → `audit` / `validate_provenance` → `schema` / `accept*` stays in `eval` / `from_schema_classes` + `batch` stay top-level. **Teaching-taxonomy lock is conceptual only — does NOT pre-decide rollout shape (Shape 1 docs-only vs Shape 2 additive aliases vs Shape 3 canonical nested + flat compat vs Shape 5 hybrid).** Shipping shape decision deferred to §5.4 / §5.7.
- **§5.8 locked: stay on v0.1 line; no v0.2 marker.** 4 decisions locked: (1) `FactGraph` enters `kernel.sdk.__all__` — length **34 → 35** (manager classes `_SDK*Manager` stay private per `views` precedent at `store.py:66-104`); (2) NO `__version__` definition added; NO `pyproject.toml` version bump at redesign impl (`version = "0.1.0"` stays); (3) docs call this **"post-L SDK ergonomics redesign"** (or "FactGraph taxonomy") within v0.1; NO "v0.2" framing in user-facing surfaces; (4) release note materializes as blueprint + audit log + archive inventory row + brief mentions in README/04_api_surface intro/public_contract_v1 cross-ref note (per §5.5/§5.5.6 locks); NO standalone `CHANGELOG.md` created. **Path B 6th immutable snapshot naming locked:** standalone `v0.1-post-l-sdk-ergonomics-redesign-<DATE>` + combined `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-post-l-redesign-<DATE>` (extends 5th at `d4ceb3e`). Source-grounded against `pyproject.toml:7` (`version = "0.1.0"`), absent CHANGELOG, and 5 published L milestone snapshot patterns. F1/F2/F3 all confirm v0.1 continuation. NOT a replacement / deprecation / package rename per §5.7 non-commitments — therefore not a v0.2 trigger.
- **§5.7 locked: SHIP additive redesign.** F0 vs F4 weighing source-grounded against §5.1-§5.5 + §5.5.6 locks: F0 strong gain (coherent taxonomy + bridge name + docs lever); F4 bounded (concentrated in `00_user_guide` 319-ref rewrite which IS the teaching investment; runtime additive only; zero test churn; module-internal docs mostly unchanged). "Ship nothing" path falsified — F0 gain real not illusory; F4 cost bounded not exhausting. **4 explicit non-commitments locked:** (1) NOT a replacement of `SDKStore` — class remains canonical implementation behind `FactGraph` taxonomy; (2) NOT a deprecation of flat methods — no `DeprecationWarning`, no removal, no "deprecated" labels per §5.4 lock; (3) NOT a package rename to `factpy` — current `from kernel.sdk import ...` import path stays; rename question deferred to §5.8 or separate blueprint; (4) NOT immediate implementation on design branch — impl work happens on `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` after scope-freeze + rebase. Smallest shipping version (F3) = §5.5 Tier 1 (12 SDK doc files taxonomy-aware) + minimum-viable runtime (1 `FactGraph` top-level class + 8 manager classes + 2 sub-manager classes via property pattern per `views` precedent). Workflow advances toward scope-freeze (status `draft → scoped`) after §5.8 + §5.9 lock.
- **§5.5 locked: per-surface doc treatment.** **4-tier classification (post-§5.5.6 extension):** (a) **Taxonomy-first** (lead with `FactGraph.<namespace>.<method>`) — README CN/EN + 6 SDK doc files (`00_user_guide`, `04_api_surface`, `02_readwrite_and_ingest`, `03_rules_and_derivations`, `01_alignment_matrix`, `05_cn_en_consistency_checklist`); (b) **SDK-presentation-only** (brief note + cross-ref; own content unchanged) — `kernel/application/docs/01_overview` CN/EN (enumeration stays flat; intro adds taxonomy bridge note); (c) **Public-contract anchor** (stays flat + adds taxonomy cross-ref) — `kernel/core/docs/04_public_contract_v1.md` (per §5.4 flat IS permanent contract); (d) **Compatibility/reference** sections within taxonomy-first docs (NOT separate "deprecated" labels) — flat-method documentation absorbed as "Foundational API" / "Compatibility reference" sections. **Module-internal docs with peripheral SDK references mostly UNCHANGED:** `application/docs/README.md` (routing note survives — points to taxonomy-first SDK docs), `application/walker/docs/README.md` (negative assertion "No SDK shell" stays valid), `adapters/docs/02_problog_adapter.md` + `03_pyreason_adapter.md` (DSL imports unchanged; prose mechanism descriptions stay flat as foundational; 1-2 usage examples conditionally taxonomy if Shape 2/3 ships); other module docs zero SDK refs (audit/authoring/core-architecture/annotation). Notebooks 01-04 + `round_story_full_demo.py` UNCHANGED (Tier-2 advanced importable bypass; only conditional 1-line update in notebook 04 if Shape 2/3 ships). NO separate migration guide file (no breaking migration; release notes suffice). L archive blueprints + Path B published snapshots untouched (Path B immutability). Total rewrite surface: ~12 doc files become taxonomy-aware (taxonomy-first tier), 1 SDK-presentation bridge note (application overview), 1 cross-ref note (public contract), 0 application/audit/core narrative changes, 0-3 conditional notebook/adapter example edits. Locked 2026-05-09 per user direction with default per-surface treatment + 2026-05-09 §5.5.6 extension covering 5 module-internal doc surfaces missed in original lock.
- **§5.4 locked: Option 2 — Permanent additive aliases + docs prefer new taxonomy.** Flat `SDKStore.<method>` callable permanently with NO deprecation, NO removal plan, NO runtime `DeprecationWarning`; `FactGraph` + teaching taxonomy materializes as additive runtime aliases under §5.7-conditional Shape 2/3 rollout. Aliases delegate to flat methods via property/private-manager-class pattern (per `views` precedent at `kernel/sdk/store.py:198-200` + `EntitySnapshot.assertions` precedent at `kernel/sdk/facade.py:102-217`). Docs / quickstart / notebooks lead with new taxonomy; flat methods documented as "supported foundational API" (NOT "deprecated"). Existing flat-method tests stay verbatim; new alias-form parity tests added under §5.9. Path B published L snapshots stay immutable with original flat-only docs framing — docs evolution is forward-only on design branch. **Rejected options recorded with falsifier evidence:** Option 3 (soft "deprecated" docs) misleads without removal plan; Option 4 (runtime `DeprecationWarning`) creates noise (flat ↔ nested produce identical results, unlike `row_format='tuple'` precedent which marked behaviorally distinct legacy mode); Option 5 (hard removal) violates §0 thesis hard-constraint without standalone falsifier.
- **Design / implementation branch isolation in force.** Design branch (this branch, `codex/v0.1-post-l-sdk-ergonomics-redesign-2026-05-09`) accepts blueprint / docs / audit-log commits only. Implementation branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` (created 2026-05-09 at design HEAD `59a5694`) is the only authorized location for code changes post-scope-freeze. Cross-contamination is a structural invariant violation.
- `kernel.sdk.__all__` length stays at **34** unless §5.x explicitly justifies an addition with falsifier pass.
- Sacred branches `master` and `v0.1-oss-prep` untouched throughout.
- All 5 published L milestone refs (G1 `d6716a0` / G4 `acb5a6e` / G2 `d658390` / G3 `cb6d3bd` / G5 `d4ceb3e`) and their Path B combined snapshots remain immutable.
- L cross-boundary DTO layer rule from G5 §5.3 / §6 stays in force ("frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary").
- Frontier stays advanced importable per G4 §5.4.
- Round events recorder lifecycle stays advanced importable per G5 §5.1.
- 9-shell Sibling discipline scope active forward-only.
- No L-Direction shell signature, error path, or test changes — redesign reshapes outer surface only.
- No `kernel.application` / `kernel.audit` / `kernel.core` changes — redesign is purely `kernel.sdk`-outward.
- **No SDK code change while status is `draft`.** First implementation phase happens only after status `scoped`.

## 7. Acceptance Criteria

Draft-stage acceptance:

- [x] Blueprint draft seeded under `docs/blueprints/active/` with §1-§4 source-grounded against HEAD `1752372`.
- [x] §5 enumerates 9 questions; no falsifier locks yet; design-only framing explicit.
- [x] §6-§9 placeholders.
- [x] Audit log seeded with "Draft seeded" entry.
- [x] **§0 Core Thesis locked** — thesis D ("namespace teaches the conceptual model; compat is hard constraint; industry shapes are evidence not templates") encoded verbatim; A/B/C alternatives recorded as rejected; thesis-derived primary falsifiers added to §5.1 (F0 legibility), §5.3 (F0 mental-model-reset), §5.4 (default-no-break), §5.7 (legibility-as-primary-axis); §6 invariants extended with thesis verbatim + F0-primacy + compat-hard-constraint rules.

Scoped-stage acceptance (filled after §5 falsifier passes):

- [x] §5.1 deliverable — inventory verified at HEAD `60af8bc` (30 methods + 4 properties + 1 nested `views` namespace; 14 conceptual families consolidated to ~8 top-level concepts); migration cost surface source-grounded (~150+ method-call mentions across 23 test files; notebooks negligible because they bypass SDKStore for kernel.application Tier 2 direct usage); 5-shape evaluation under F0/F4/F5 with verdicts: Shape 1 (status quo flat) fails F0 + zero cost; Shape 2 (additive nested aliases) F0 partial + near-zero cost; Shape 3 (canonical nested + flat compat) F0 better via docs lever + medium docs cost; Shape 4 (replacement) F0 strong but violates thesis hard-constraint; Shape 5 (hybrid/staged) varies + moderate-high cost. Leading candidate Shape 3 under thesis; Shape 2 most defensible additive; Shape 1 conservative default; Shape 4 requires §5.4 standalone falsifier; Shape 5 weaker than Shape 3 unless specifically motivated. §5.1 research-only; shape direction deferred to §5.7.
- [x] §5.2 locked — **teaching taxonomy** locked 2026-05-09 per user direction: 8 top-level namespaces (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`) + 2 sub-namespaces (`what_if.fact_overlay`, `what_if.rule`); `from_schema_classes` (cls) + `batch` (cm) + 4 properties at top-level. All 5 placements locked: Option B split for `what_if` / `diff_proof_frames` → `audit` / `validate_provenance` → `schema` / `accept*` stays in `eval` / `from_schema_classes` + `batch` stay top-level. **Teaching taxonomy ≠ shipping shape** — rollout decision (Shape 1 docs-only vs Shape 2 additive aliases vs Shape 3 canonical nested vs Shape 5 hybrid) deferred to §5.4 / §5.7.
- [x] §5.3 locked — top-level entrypoint class name is **`FactGraph`** (4-round chat-driven falsifier pass 2026-05-09; sources: TF/PySpark/pyparsing Python precedent for Fact-overlap; `EvidenceGraph` substrate F2-clean — not in `factpy.__all__`; SDK* family pattern preserved by keeping `SDKStore` callable per §5.4).
- [x] §5.4 locked — **Option 2: permanent additive aliases + docs prefer new taxonomy** (locked 2026-05-09 per user direction with default hypothesis "flat callable permanently; taxonomy additive only unless falsifier proves migration necessary"). Flat `SDKStore.<method>` permanently callable; NO deprecation, NO removal plan, NO runtime `DeprecationWarning`. Aliases delegate via property/manager-class pattern (per `views` + `EntitySnapshot.assertions` precedent). Docs lead with taxonomy; flat documented as foundational. Rejected options 3/4/5 with source-grounded falsifier evidence. Implications: §5.5 substantial docs rewrite (the F0 teaching investment); §5.6 implicitly resolved (aliases); §5.7 still has authority to elect Shape 1.
- [x] §5.5 locked — **per-surface doc treatment with taxonomy-first SDK docs** (locked 2026-05-09 per user direction with default per-surface treatment). 3-tier classification: taxonomy-first (README + 5 SDK doc CN/EN pairs + checklist); SDK-presentation-only (application overview brief note + cross-ref); compatibility/reference (within taxonomy-first docs as "Foundational API" sections, NOT separate "deprecated" labels). Source-grounded cost: ~12 doc files become taxonomy-aware (319 refs in `00_user_guide` largest); 0-1 notebook edits (only `diff_proof_frames` in 04 if Shape 2/3 ships); 0 application/audit/core narrative changes. NO separate migration guide file (no breaking migration; release notes suffice). L archive blueprints + Path B published snapshots untouched (Path B immutability). §5.6 implicitly resolved by §5.4 + §5.5 (aliases delegate to flat; new taxonomy is editorial canonical via docs lever).
- [ ] §5.6 locked — aliases vs replacement decision (if non-no-change outcome).
- [x] §5.7 locked — **SHIP additive redesign** (locked 2026-05-09 per user binary decision direction). F0 vs F4 weighing source-grounded against all prior §5.x locks: F0 strong gain (coherent taxonomy + bridge name + docs lever); F4 bounded (`00_user_guide` 319-ref rewrite IS the teaching investment; runtime additive; zero test churn). 4 explicit non-commitments locked: (1) NOT replacement of `SDKStore`; (2) NOT deprecation of flat methods; (3) NOT package rename to `factpy` (deferred to §5.8); (4) NOT immediate impl on design branch (impl branch `codex/v0.1-post-l-sdk-ergonomics-redesign-impl-2026-05-09` post-scope-freeze + rebase). Smallest shipping version = §5.5 Tier 1 (12 SDK docs taxonomy-aware) + 1 `FactGraph` top-level class + 8+2 manager classes via `views` property precedent. Workflow advances to §5.8 + §5.9 locks before scope-freeze.
- [x] §5.8 locked — **stay on v0.1 line; no v0.2 marker** (locked 2026-05-09 per user default hypothesis). 4 decisions locked: `FactGraph` enters `kernel.sdk.__all__` 34 → 35 (manager classes private per `views` precedent); no `__version__` / `pyproject.toml` version bump (stays `0.1.0`); docs call it "post-L SDK ergonomics redesign" within v0.1; release note in blueprint+audit-log+archive-inventory + brief mentions in 3 docs (NO standalone CHANGELOG). Path B 6th snapshot naming locked: `v0.1-post-l-sdk-ergonomics-redesign-<DATE>` standalone + `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-post-l-redesign-<DATE>` combined Path B (extends 5th at `d4ceb3e`). Source-grounded against `pyproject.toml`, absent CHANGELOG, and 5 published L milestone snapshot patterns.
- [ ] §5.9 locked — test + invariant impact assessment.
- [ ] §8 implementation plan filled with N phases (or "no implementation; close as research-only" if §5.7 lands no-change).
- [ ] Status moves from `draft` to `scoped`.

Implementation-stage acceptance: TBD post-§5.7 (depends on whether the redesign ships; if §5.7 = no-change, this entire stage is empty and the blueprint closes at `scoped → implemented` with §9 documenting "research-only outcome").

## 8. Implementation Plan

(Filled at scope-freeze. Plan shape depends on §5.7 outcome:

- **No-change outcome**: zero implementation phases; close-out commit moves blueprint to archive with §9 documenting the falsifier outcomes that justified no change.
- **Alias overlay outcome**: 1-2 implementation phases (add nested namespace + tests; update docs).
- **Replacement outcome**: 3-5 implementation phases including deprecation warnings, test patch-path updates, doc/notebook migration, possibly version-bump branch strategy.

Per `feedback_audit_cadence_per_phase`, every phase has a strict per-phase audit gate. Per `project_release_branch_invariants`, any publish step at the end is user-authorized.)

## 9. Outcome / Deviations

To be filled at close-out.
