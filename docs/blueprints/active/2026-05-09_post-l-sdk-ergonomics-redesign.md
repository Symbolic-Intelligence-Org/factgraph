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

### 4.5 Memory inputs

- `feedback_sdk_ergonomics_redesign_target` — user prefers OpenAI-style SDK shape (top-level client / nested namespaces / short names) as post-L target. **Direction input only**, not automatic migration. Falsifier must source-ground.
- `project_g{1,2,3,4,5}_published.md` — full L Direction shipped state. Each G's archived blueprint flagged "post-L redesign blueprint" as the venue for namespace questions.
- `project_release_branch_invariants` — sacred branches untouched; publish decisions user-authorized.
- `feedback_iterative_gap_design` — one §5.x lock at a time (or low-suspense batches); falsifier required before each lock.
- `feedback_audit_cadence_per_phase` — strict per-phase audit gate.
- `feedback_worktree_parallel_implementation` — topic branches use `codex/` prefix; published refs drop it.
- `feedback_narrow_public_api` — in OSS preview lines, default to internal/contained mechanisms; expand public SDK surface only when current scope explicitly requires user-facing access.

## 5. Design — Step 0 Questions

**Convention:** Each §5.x question lists what must be source-grounded by a falsifier pass before locking. **No question below has a final decision yet.** Per `feedback_iterative_gap_design`, decisions land one at a time (or in low-suspense batches), each in its own commit, with a fresh falsifier scan against the codebase HEAD.

The §5.1 inventory is the **first deliverable**. It does not commit to any direction; it just enumerates the current surface and the candidate alternative shapes. §5.2 onward then answer specific questions one at a time.

### 5.1 Inventory the current 30-method flat surface + evaluate alternative shapes

**Question:** What is the actual current SDK surface, and what are the candidate alternative shapes that could replace or overlay it?

**Sub-questions to answer in the falsifier pass:**

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

### 5.2 Namespace shape — if non-flat, what is the grouping?

**Question:** If §5.1 surfaces non-(A) options worth pursuing, what is the actual namespace grouping?

Candidate groupings (provisional; finalized at §5.2 lock):

- **By capability family** (matches §4.1 grouping table): `sdk.schema.*` / `sdk.read.*` / `sdk.write.*` / `sdk.eval.*` / `sdk.accept.*` / `sdk.what_if.*` (G1+G2+G3+G4) / `sdk.diff.*` (G5) / `sdk.audit.*` / `sdk.package.*` / `sdk.views.*` (existing).
- **By tier** (Tier 1 SDK shells vs pre-L): `sdk.l.*` (everything from G1-G5) / `sdk.write.*` / `sdk.read.*` / `sdk.eval.*` / etc.
- **By resource** (closest to OpenAI shape): `sdk.derivations.*` / `sdk.rules.*` / `sdk.entities.*` / `sdk.proof_frames.*` / `sdk.rounds.*`.
- **Round-story-flow** (matches the user-facing notebook progression): `sdk.check.*` / `sdk.overlay.*` / `sdk.recheck.*` / `sdk.diff.*` / etc.

**Falsifiers required:**

- F1 — Which grouping minimizes the "method-name search problem" (user knows verb but doesn't know namespace)? Test by asking: given a verb, can a user infer the namespace?
- F2 — Which grouping aligns with the existing notebook progression (01 / 02 / 03 / 04)?
- F3 — Which grouping survives the addition of a hypothetical 10th L family without restructuring?
- F4 — Does any grouping accidentally promote `kernel.audit` or `kernel.core` concepts into the SDK surface? The G5 §5.3 layer rule must hold.
- F5 — Existing `views` namespace precedent — does it fit the chosen grouping or stay an outlier?

### 5.3 Top-level client class naming

**Question:** If the redesign introduces a top-level client (option E or rename), what is it called?

Candidates: `Client`, `FactPyClient`, `Store`, keep `SDKStore`, `Kernel`, other.

**Falsifiers required:**

- F1 — Naming must not collide with existing identifiers in `kernel.sdk.__all__` (length 34).
- F2 — Naming must not be ambiguous with `kernel.core.store.Store` (substrate-layer Store class).
- F3 — Industry alignment: OpenAI uses `OpenAI` (PascalCase namespace name); Anthropic uses `Anthropic`; Stripe uses `stripe.Stripe()`; Google's GenAI uses `genai.Client`. FactPy convention: TBD.
- F4 — Backwards-compat: if `SDKStore` stays, the new client name is purely additive; if `SDKStore` is renamed, all 5 immutable Path B snapshots' callsites in user code break.

### 5.4 Compatibility / deprecation strategy

**Question:** How are existing flat-method users handled?

Candidates:

- **(A) Permanent dual surface** — flat methods stay forever, new shape is additive. Zero breakage; surface area grows.
- **(B) Deprecation warnings + grace period** — flat methods emit `DeprecationWarning` for N versions, then removed. Predictable breakage path.
- **(C) Hard cutover at v0.2** — flat methods removed at next major; redesign is the canonical shape. Highest breakage.
- **(D) Tier-based** — flat L methods stay (since they're newest and in published refs); pre-L flat methods get deprecated/removed. Mixed strategy.

**Falsifiers required:**

- F1 — Inventory of flat-method callsites in (a) `examples/`, (b) `kernel/tests/test_sdk_*.py`, (c) any external user code we know about. Counts inform breakage surface.
- F2 — `feedback_narrow_public_api` says expand surface only when scope requires it. Does adding deprecation infrastructure (warnings, version stamps, removal schedules) qualify as "scoped"?
- F3 — Path B immutability constraint: published L milestone snapshots' callsites are in their archived test files; those don't move. The compatibility question is purely about NEW user code post-redesign.

### 5.5 Docs / quickstart impact

**Question:** What docs change at redesign release?

Candidate scope:

- README CN + EN (top-level + module-level)
- `kernel/sdk/docs/04_api_surface.md` + `.en.md`
- `kernel/application/docs/01_overview.md` + `_en.md`
- 4 notebooks under `examples/`
- `examples/round_story_full_demo.py`
- Any consumer-facing migration guide (new file?)

**Falsifiers required:**

- F1 — Total doc + example file count touched per candidate redesign shape.
- F2 — Whether a separate "v0.1 → v0.2 migration guide" file is warranted, or whether release notes suffice.
- F3 — Whether L Direction archive blueprints need any retroactive note (probably not — they're immutable historical record; but check).

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

This is the **honest meta-question**. The user has flagged a direction; the falsifier may surface that:

- The flat surface is conceptually fine for FactPy's "session over knowledge graph" model (per SQLAlchemy precedent).
- Migration cost is high relative to the ergonomic win.
- No consumer signal exists (no recorded user complaint, no notebook friction beyond what the user noted in `feedback_sdk_ergonomics_redesign_target`).
- The post-L moment is better spent on a different post-L blueprint (publish-line hygiene, post-publish verification on G1-G4 not yet done, dialog agent, etc.).

**Falsifiers required:**

- F1 — Recap §5.1-§5.6 falsifier outcomes; sum up the costs vs benefits.
- F2 — Source-ground "no" path: under what conditions would "ship nothing" be correct? Document this honestly.
- F3 — If "ship something", what is the smallest version (alias overlay only, no flat-method changes, no docs touched beyond brief mention)?

A **legitimate `scoped` outcome** for this blueprint is "no SDK surface change; record findings + close". `feedback_narrow_public_api` is the standing principle.

### 5.8 Roadmap / version stamping

**Question:** If the redesign ships, what version number does it represent? Same `v0.1` preview line, or a `v0.2` minor / major bump?

**Falsifiers required:**

- F1 — Existing version conventions in this codebase: `v0.1-oss-prep`, `v0.1-l-g{1-5}-...`, `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-2026-05-08`. The pattern is `v0.1-<scope>-<date>`.
- F2 — Whether the redesign is "L hygiene continuation" (still v0.1 line) or "post-L major refactor" (v0.2 line).
- F3 — Path B 5th immutable snapshot is at v0.1; would a redesign produce a 6th v0.1 snapshot or start a v0.2 line?

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

Scoped-stage acceptance (filled after §5 falsifier passes):

- [ ] §5.1 deliverable — full inventory of 30-method flat surface + N candidate alternative shapes with documented migration cost surfaces and conceptual-fit evaluation.
- [ ] §5.2 locked — namespace shape (or "no nesting").
- [ ] §5.3 locked — top-level client naming (or "keep `SDKStore`").
- [ ] §5.4 locked — compatibility / deprecation strategy.
- [ ] §5.5 locked — docs / quickstart impact assessment.
- [ ] §5.6 locked — aliases vs replacement decision (if non-no-change outcome).
- [ ] §5.7 locked — ship-or-not meta-decision.
- [ ] §5.8 locked — version stamp / roadmap timing.
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
