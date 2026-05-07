# Post-Routemap Direction Selection — Input Bundle

- **Created:** 2026-05-07
- **Status:** non-authoritative strategic alignment input (NOT a blueprint, NOT a feasibility study, NOT a decision lock-in)
- **Authority level:** working reference, equivalent to `rule-replay-line-redesign-input/`
- **Audience:** product leads (alignment), blueprint authors (when designing A/B/C/etc., cite §30 rationale)

---

## Why this exists

The Round Story Completion Plan (Batches 0-8) closed at commit `6b32972` (2026-05-06). With v0.1 routemap finished, the project enters a post-routemap state where the next direction is genuinely open. A 2026-05-07 source-trace review surfaced a key tension: the v0.1 public surface (`kernel.sdk`) covers schema/read/write/rule/derivation but not evidence/proof/Q1-Q5/Batch 4-7, and that gap is intentional but creates real end-user friction. This bundle records:

1. The inventory of all loose ends (active blueprints, deferred-with-trigger items, branch state).
2. Implicit strategic gaps surfaced during the review — items that shape current product behavior but are not yet declared in any deferred-items catalog.
3. Nine candidate next-layer directions (A through I) with structured trade-off comparisons.
4. The recommendation that emerged (paths A + B), with rationale and "what scoping next looks like."

## Why an input bundle, not a blueprint

A blueprint commits to one direction and gates it with falsifiers. This bundle holds **multiple directions for review** so the choice is explicit. When a direction is selected, a real blueprint will be drafted in `docs/blueprints/active/` referencing this bundle for source.

## Contents

| File | Content |
|---|---|
| [00_inventory.md](00_inventory.md) | Active blueprints (5 truly in-flight + 26 parked governance), deferred items catalog from Batch 8 §5.5.5 + Round Story Plan §3/§10.4 (19 items total), branch state |
| [10_implicit-gaps.md](10_implicit-gaps.md) | Four implicit strategic gaps surfaced 2026-05-07 that no current deferred list tracks (Gap 2 refined post-verification: scope much smaller than initially estimated) |
| [20_candidates.md](20_candidates.md) | Nine candidate next-layer directions (A through I) with trade-off table (Candidate B revised post-verification: split into B1+B2 mandatory + B3 optional) |
| [30_recommendation.md](30_recommendation.md) | Recommended path (A+B), the finalized inventory (#1-#19 with #4 split into #4a/#4b, plus #P0/#P1) grounding subsequent scoping, rationale, and "what scoping next looks like" |
| [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) | Walker mechanism scoping artifact — lifts §6 *draft* exploration into structured proposal; aligns with EntitySnapshot prior art and SDK syntax; operationalizes walker contracts; sub-batches B1+B2 mandatory + B3 optional/future-only |

## Lifecycle

- **Active:** While the post-routemap direction is being decided.
- **Cited from blueprints:** When candidate directions become real blueprints, they should `Related Docs:` cite this bundle.
- **Archive:** When all referenced directions have either landed as implemented blueprints or been explicitly abandoned (with reactivation triggers if revisited).

## Design completeness criteria

This bundle is **ready as input for A and B implementation blueprints** when every item below is satisfied. Each item is testable; partial-completion is acceptable while the bundle is `Active`, but A/B blueprint work should not begin until all items are checked or explicitly carved out via `#P1`.

| Criterion | Status | Reference |
|---|---|---|
| 21 principles (`#1`–`#19` + `#P0` / `#P1`) all source-grounded; citations verified | ✓ done | Rounds 1–5 (verification log) |
| Walker mechanism scope locked: B1 mandatory, B2 mandatory, B3 optional/future-only; all 5 walker invariants (`#11`–`#14` + cross-cuts) operationalized | ✓ done | [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md), Round 6 |
| `ProofFrameDiffView` and per-DTO wrapper-view pattern locked into B2; no methods attached to existing tuple fields | ✓ done | Round 7 |
| L-Full recorded as long-term roadmap target without modifying primary recommendation; per-group clean / pending-Step-0 classification documented | ✓ done | Round 8 |
| Direction A input shape locked: application canonical types only; no SDK-exclusive DSL / facade / store / batch / editor / snapshot objects; per-builder canonical inputs documented; SDK→application lowering bridging is L's responsibility, not A's | ✓ done | [30_recommendation.md](30_recommendation.md) "Direction A — Input shape lock" |
| Direction A direction has its own design sketch document parallel to 40_ for B | ✓ done | [41_application-builders-design-sketch.md](41_application-builders-design-sketch.md) |
| Test contract concrete shape (per `#19` common-contract + behavior-specific) sketched for A and for B | ✓ done | [40_walker-mechanism-design-sketch.md §6](40_walker-mechanism-design-sketch.md), [41_application-builders-design-sketch.md §6](41_application-builders-design-sketch.md) |
| A+B migration path for current `examples/` and downstream consumers documented | ✓ done | [50_migration-path.md](50_migration-path.md) |
| Principle cross-references audited (every principle referenced in every relevant document; no orphaned dependencies); typed dependency map added to 30_ | ✓ done | [30_recommendation.md "Principle dependency map"](30_recommendation.md);41_ §4 patched to cite `#4a` / `#P0` / `#P1` (cross-ref audit fix) |
| Principle thematic grouping documented (no editing of `#N` numbering; thematic table only) | ✓ done | [30_recommendation.md "Principle thematic grouping (explanatory)"](30_recommendation.md) |

**Carve-out rule:** any item above can be deferred via explicit `#P1` carve-out in the implementation blueprint, provided the carve-out names the deferred principle / sketch / criterion and records reason + scope + reviewer ack. Carve-outs persist for as long as the implementation persists (per `#P1` item 10).

**"Ready" definition:** all rows checked or explicitly carved out. The bundle is currently **partial-ready**: items locked through Round 8 are sufficient for B blueprint to start (B's design is fully sketched); A blueprint cannot start until Gap α + β are resolved.

## Verification log

This bundle was hardened through a verification round on 2026-05-07 to ensure principles are source-grounded and walker scope is realistic.

**Round 1 — initial draft (2026-05-07 morning):** Recorded post-routemap discussion; nominated A+B+conditional-C; documented 9 design principles backed by various source citations.

**Round 2 — verification (2026-05-07 afternoon):** Three parallel Explore agents audited the bundle:

1. **Citation accuracy** — found Principle #4 was misattributed (cited §6.3.B.3 / §6.4.B.2 from a section the document declares draft and non-binding); Principle #3 attribution slightly off; Principle #5 conflated two source documents.
2. **Walker prior art search** — confirmed `EntitySnapshot` namespace walker pattern already exists in [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py); found that most application/audit DTOs are already structured frozen dataclasses, so walker scope is much smaller (~4-5 raw-tuple objects, not ~10).
3. **Internal consistency + completeness** — flagged tension between #3 (heterogeneity) and #7 (uniformity) needing reconciliation language; identified missing principle #10 (determinism with explicit walker-class distinction) as critical for lazy walker correctness.

**Round 3 — revision (2026-05-07 afternoon):**

- Principle #4 split into #4a (canonical input-minimal, retained) + #4b (walker direction acknowledged as draft-source design exploration, not settled principle)
- Principle #3 attribution corrected
- Principle #5 sources disaggregated
- Principle #7 clarified as "uniform access pattern, heterogeneous output shapes" with explicit per-layer scope; cites EntitySnapshot prior art
- Principle #10 added with user's precise wording on DTO-backed vs store-backed live walker, snapshot semantics, and explicit no-silent-race rule
- Walker scope refined: B1 (IR walker + wrapper-view protocol) + B2 (cross-reference helpers) mandatory; B3 (audit walker) optional based on consumer signal
- New file [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) created as the walker scoping artifact

**Round 4 — SDK syntax / current-code alignment (2026-05-07 evening):**

- Confirmed `SDKStore.get(...)` is None-on-miss and `FieldAssertions.at(t)` is a temporal filter, so walker exact-access APIs must not use raise-on-miss `get(...)` or positional `at(...)`
- Confirmed `source` is already provenance / reference vocabulary and `carrier` collides with evidence-carrier terminology around `SupportArtifact`
- Finalized walker escape hatch as `.underlying`, with no `.source`, `.carrier`, or `.raw` alias
- Finalized exact-access vocabulary as `find(...) -> View | None`, `require_key(...) -> View`, and `require_position(...) -> View`
- Confirmed `RuleSpec.where` and `CompiledDerivationPlan.body_ir` are mutable `list[Any]`; finalized construction-time immutable snapshot for mutable-source DTO walkers
- Confirmed B1/B2 should not enter `kernel.sdk`; the only accepted blueprint acceptance gate from this round is "no new export to `kernel.sdk.__all__`"

**Round 5 — A/B/C/D contract synthesis and minimal verification (2026-05-07 evening, this state):**

- Expanded the principle inventory from #1-#10 to #1-#19 plus #P0/#P1
- Added #11-#14 walker mechanism contracts: `.underlying`, error boundaries, observability isolation, and bounded future `StreamWalker` constraints
- Added #15-#19 implementation-facing contracts: single-thread walker instances, DTO-backed lifecycle, equality/hash, serialization, and tests
- Added #P0 conflict resolution with the 5-tier fallback heuristic and cross-tier dominance rule
- Added #P1 principle revision flow with context-specific carve-outs, mixed historical handling, rename/deprecation docs impact, and carve-out lifecycle
- Minimal verification found and fixed a cache cross-reference omission: #9 is the single source of truth for cache constraints, and #10/#12/#13/#16/#17 now cross-reference it; the five protected dimensions are equality, `.stats`, traversal result, error timing, and memory lifecycle
- Minimal verification found and fixed omitted visibility for #11/#12/#14 augmentations: `MappingProxyType(dict(...))` shallow mapping behavior, `WalkerError` hierarchy, nullable error fields, and at-least-one stream bound condition are now explicit
- Minimal verification removed three unsourced proposed gates; this bundle only records the finalized D2 gate (`kernel.sdk.__all__` must not receive B1/B2 exports). Static lint gates for logging or lifecycle conformance are not pre-committed here.

After Round 5, the bundle is internally consistent and source-grounded as reference/scoping input. It can be cited from implementation blueprints without further revision unless new evidence surfaces.

**Round 6 — audit patch planning / code-reality alignment (2026-05-07 evening):**

- Audited committed bundle `c5b97e8` against original March design docs, rule-replay references, current SDK/application/core/audit code, and module docs.
- Found and corrected one blocker in the walker sketch: existing frozen tuple DTO fields cannot grow `.filter(...)` / `.find(...)` methods in place. B2 now uses per-DTO wrapper views such as `SupportArtifactView` / `ProofFrameView`, with `FrozenTupleView` / `frozen_collection(...)` as the standalone tuple escape hatch.
- Reframed `Store.active_facts` as future live store/ledger walker scope; no such current API exists. Future B3 must first name a real store/ledger source API.
- Tightened `AssertionView`: B2 defaults to `AssertionView(asrt_id, frozen_claim_index, frozen_meta_index=None)` over existing `Claim` / `MetaRow` data. `LiveAssertionView(asrt_id, store)` is future/B3-only and must be explicitly live.
- Replaced the overly narrow EvidenceGraph wording. EvidenceGraph is now described as the audit layer's unified cross-engine explainability DTO, durable as `audit/evidence_graphs.jsonl`, queryable via `AuditQuery.get_candidate_evidence_graph(candidate_id)`, and rendered via `render_evidence_graph_html()`; it complements walker traversal rather than overlaps with it.
- Corrected count and terminology drift: Candidate A covers 8 missing helpers, the principle inventory is "#1-#19 with #4 split into #4a/#4b, plus #P0/#P1", and #11 uses "manual review check" rather than "manual review gate."
- Recorded EntitySnapshot caveats as walker-design lessons: do not expose `_underscore` mutable internals, do not import SDK private helpers, and preserve no-observable-cache behavior. `WalkerFrozenError` is a walker-layer error rather than an SDK `FrozenSnapshotError` reuse.

**Round 7 — evidence-ecosystem audit (2026-05-07 late evening):**

Single-round timeboxed audit asking only one question: "Does the current A+B bundle miss any evidence-adjacent candidate that would affect post-routemap direction selection?" Five parallel Explore lanes plus local text/scope synthesis. 17 findings classified into three categories per the user-defined rule:

1. **Lane 1 — EvidenceGraph + AuditQuery + render layer** — confirmed `AuditQuery` already exposes ~30 named query methods covering rounds, evidence graphs, provenance trees, decisions, failures, authoring apply events, compliance matrix, rule traces. Render layer is HTML-only via `render_evidence_graph_html()` plus `to_dict()` round-trip. 1 borderline challenge (render export formats: JSON / Markdown / CLI), 4 orthogonal (EvidenceGraph node/edge lookup, edge filter, batch query), 1 sufficient (layout view helpers intentionally deferred).
2. **Lane 2 — Output-side wrapper gaps** — most output DTOs (`FactOverlayCheckResult`, `frontier_rows`, rule-overlay `variant_rows`) are sufficiently ergonomic via direct attribute access on frozen dataclasses. **One firm challenge: `ProofFrameDiff.frame_deltas` / `atom_deltas` need a `ProofFrameDiffView` per-DTO wrapper view because filter-by-status_change-kind and flatten-atom-deltas-across-frames are real friction today.**
3. **Lane 3 — Provenance inspection + SDK explain_fact / conflicts** — 0 challenge to A+B; 3 orthogonal gaps (`FieldAssertions.active` filter by source/confidence, `sdk.conflicts()` returns IDs without metadata hydration, cross-`asrt_id` metadata comparison), 2 sufficient.
4. **Lane 4 — Application-layer pipeline composition (vs SDK shell C)** — 0 challenge / 0 orthogonal / 1 sufficient. Composition is trivial data threading in current usage; helper shapes feel premature or redundant. SDK shell C will absorb the surface naturally if it ships.
5. **Lane 5 — Adapter evidence (ProbLog / PyReason)** — confirmed B's "native first slice; adapter walker deferred (separate trigger)" framing is correct. Native adapters and converters ship in v0.1; the right pattern when triggered is a single cross-engine walker over `EvidenceGraph` (with `engine_meta` callbacks) rather than per-engine walkers.

**Round 7 patches landed:**

- `10_implicit-gaps.md` Gap 2 table: `ProofFrameDiff.frame_deltas` / `atom_deltas` row revised from "NO walker class needed" to "wrapper view via `ProofFrameDiffView` per B2; does not modify DTO and does not attach methods to its tuple fields."
- `40_walker-mechanism-design-sketch.md` §2: "Already structured" sub-section restructured as a per-row table assigning each DTO its wrapper-view treatment (`SupportArtifactView`, `ProofFrameView`, `ProofFrameDiffView`) or noting direct iteration adequacy.
- `40_walker-mechanism-design-sketch.md` §3 B2: `ProofFrameDiffView` added to mandatory B2 scope with three first-slice helper sketch names ("filter `frame_deltas` by `frame_status_change` kind / before / after status", "iterate all `atom_deltas` flattened across all frames", "iterate frames carrying any `atom_verdict_changed` delta"). Final method names locked in B blueprint Step 0.
- `30_recommendation.md` "what scoping next looks like": added a "Plausible follow-ons" sub-section listing render export formats (Lane 1 borderline) and the EvidenceGraph + AuditQuery ergonomics cluster (Lanes 1, 3, 5 cohesive orthogonal). These are markers, not new candidates; they do not modify A+B rank.
- This README log entry.

**Round 7 explicit non-actions:**

- No `evidence-ecosystem-audit-input/` companion bundle opened. The 7 cohesive orthogonal findings are recorded here only as a pointer; if the cluster becomes high-priority it warrants its own bundle, not direct injection into A or B.
- Render export formats are not added to B2 scope. They are post-A+B follow-on territory.
- Application-layer pipeline composition is not added as a candidate. SDK shell C is the right venue if such a shape becomes desirable.

After Round 7, the bundle scope is finalized for the purpose of unblocking Direction A and Direction B implementation blueprints. The `ProofFrameDiffView` addition is in-scope correction (not an `#P1` carve-out), so A/B blueprint work can proceed once these patches are committed.

**Round 8 — SDK conventions audit + L-Full long-term roadmap (2026-05-07 late evening):**

Triggered by a separate user observation: "before publish, the library layer must be able to do a complete round story, otherwise the user-facing perception is incomplete." The discussion surfaced an ambiguity in the bundle's earlier "developer-facing" framing: A+B is Tier 2 (advanced importable) work, not Tier 1 (SDK product public) work. To address the perception gap before v0.1 publish, an L-Full direction (5-group SDK shells covering Q1–Q5 + Batch 4–7) was proposed.

Before recording L-Full in the bundle, a single-round timeboxed SDK conventions audit ran 4 parallel lanes to verify the 5-group L-Full shape is actually compatible with existing `kernel.sdk` conventions, **and** to confirm that A+B builder/view shapes are not reverse-constrained by L-Full's eventual SDK shape:

1. **Lane 1 — SDK `__all__` / user guide / naming / return / errors conventions** — inventoried existing SDK exports and patterns: verb-first method names, primary positional + keyword-only options, frozen-dataclass DTOs vs `dict[str, Any]` for shallow audit, SDKError hierarchy, DSL → application lowering via `to_authoring_payload()`. All synchronous; no async API.
2. **Lane 2 — evidence-side SDK prior art** — `explain_fact()` and `conflicts()` return `dict[str, Any]`; `validate_provenance()` returns typed `ValidationReport` frozen dataclass. Existing audit-shallow methods take string IDs (`pred_id`, `e_ref`), NOT SDK DSL objects. Empty result on miss, not raise. Ingest precedent: normalized list-of-dicts, not raw class instances.
3. **Lane 3 — 5-group compatibility** — verdict per group: **G1 Check + Diagnose: clean**. **G4 Why-not + Frontier: clean** (with naming correction `universe` → `why_not`; frontier stays advanced importable). **G2 Fact Overlay + ProofFrame Recheck: mismatch** (raw protocol DTO `SupportArtifact` / `EvaluationOverlay` surfaced). **G3 Rule overlays: mismatch** (three-sister naming + raw `RuleSpec` exposure). **G5 Round + Diff: mismatch** (recorder lifecycle raises mixed with query DTO returns).
4. **Lane 4 — examples / quickstart migration impact** — migration feasible in ~9–12 hours total across all 4 chaptered notebooks; G4 (audit) ships independently; G1→G2→G3 strict dependency chain (G3 needs Check's `SupportArtifact`); README quickstart NOT a target for L-Full (Check is too heavy for top-level quickstart). No structural blockers identified.

**Round 8 verdict: Mixed (clean for G1+G4, mismatch identified-not-rushed for G2/G3/G5).**

**Round 8 patches landed:**

- `30_recommendation.md` "Plausible follow-ons" sub-section: added "Long-term SDK completion candidate: L-Full" entry. Documented as **post-A+B v1-ready roadmap target**, not immediate next; explicit Tier 1 outward compat commitment per `#6` tension; per-group clean/pending classification; explicit note that A+B builder and view shapes are **not reverse-constrained** by L-Full's eventual SDK shape.
- This README log entry.

**Round 8 explicit non-actions:**

- Primary recommendation NOT changed. A+B remains the immediate next direction; L-Full is long-term roadmap.
- Candidate ranks NOT changed in `20_candidates.md`.
- No companion bundle (`evidence-ecosystem-audit-input/` or `library-completion-input/`) opened.
- G2 / G3 / G5 SDK shape decisions NOT resolved. Each pending its own Batch 8 §5.5.5 family Step 0 when L-Full activates per group.
- A+B blueprint work is unblocked: Lane 3 confirmed builder/view shapes at Tier 2 are not reverse-constrained by L-Full's Tier 1 shape decisions. Future SDK shells can wrap A+B without modifying their shape.

After Round 8, the bundle scope is finalized for the purpose of unblocking A and B implementation blueprints, with L-Full recorded as a long-term roadmap target awaiting per-group Step 0 reactivation. A+B blueprints can proceed once these patches are committed.

**Round 9 — Design completeness sweep (Gap γ → Gap η, 2026-05-07):**

Triggered by user observation that bundle had design completeness criteria implicitly pending. Single-session iterative gap-by-gap completion of 7 gaps surfaced after Round 8. Workflow: per gap, propose → discuss design decisions if any → apply patch → mark ✓ done in acceptance checklist → next gap.

1. **Gap γ — Design completeness criteria** — added "Design completeness criteria" section to README.md as a 10-row checklist defining when the bundle is "ready as input for A and B implementation blueprints." Each row testable; carve-out rule per `#P1` documented.
2. **Gap β — Direction A input shape lock** — locked A's builders to accept application canonical types only; per-builder canonical input table; SDK-exclusive DSL / facade / store / batch / editor / snapshot objects forbidden by origin-package rule (not by name match). SDK→application lowering is L's responsibility. Section added to 30_.
3. **Gap α — Direction A design sketch** — created [41_application-builders-design-sketch.md](41_application-builders-design-sketch.md) parallel to 40_. 8-helper coverage target (3 shipped Batch 2 + 5 new families); per-family sketch for Check+Diagnose, ProofFrame Recheck, Rule Overlay (3 sub-builders), Round Event Payload; cross-cutting invariants per `#1` / `#4a` / `#5` / `#6` / `#9` / `#19` / `#P0` / `#P1` + Batch 2 §6.
4. **Gap ε — Test contract sketch** — added §6 "Contract test sketch" to both 40_ (walker tests) and 41_ (builder tests). Subsequent sections renumbered. B3 future contract tests reserved as NOT B1/B2 acceptance. Static / structural tests for A documented as blueprint acceptance candidates (grep / import-graph review), not dynamic lint.
5. **Gap δ — A+B migration path** — created [50_migration-path.md](50_migration-path.md). 8 sections covering migration principles (additive only, no SDK surface change, opt-in incremental), per-family migration preview tables, incremental order, backward compatibility guarantees, out-of-scope, and §8 Blueprint handoff checklist listing what A blueprint and B blueprint must cite / acknowledge.
6. **Gap ζ — Principle dependency map + cross-ref audit** — added typed dependency table to 30_ (8 rows). Cross-ref audit per user criteria found 3 orphaned principle citations in 41_ (`#4a`, `#P0`, `#P1` missing); patched 41_ §4 with 3 new bullets. 40_, 50_, README cross-refs passed clean.
7. **Gap η — Principle thematic grouping (explanatory)** — added thematic table to 30_ using "Lane" header rather than universal "Tier" (Cross-cutting and Meta lanes are not part of `#P0` priority). 8 lanes: Tier 1–5 + Cross-cutting × 2 + Meta. Notes clarify grouping is metadata-only; numbering `#1`–`#19` + `#P0` / `#P1` stays authoritative; conflict resolution still follows `#P0`.

**Round 9 verdict:** All 10 design completeness criteria rows ✓ done. Bundle internal consistency verified (acceptance checklist clean; bundle-internal cross-doc references intact; 21 principles all referenced; no unresolved TBDs except legitimate B3-future scope markers in 10_/40_).

**Round 9 explicit non-actions:**

- No A or B blueprint created yet. Bundle is pre-blueprint design input only.
- L-Full Direction not advanced beyond Round 8 follow-on note.
- `master` / `v0.1-oss-prep` sacred branches not touched.
- No commit of bundle yet — full Round 6+7+8+9 patches still in working tree.

After Round 9, the bundle is **design-complete as reference / scoping input for A+B blueprints**. A+B implementation can start after the blueprint Step 0 confirms local implementation details (module split, binding normalization exact behavior, error class layout, test fixture layout), without waiting on Tier 1 SDK / L-Full, `import` naming (`factpy` vs `kernel.sdk`), or dialog-agent decisions. Per [50_ §5](50_migration-path.md), A and B can ship in any order; B1 → B2 strict; B3 future-only.

## Primary sources cited throughout

Internal:
- [Batch 8 Public Surface Decision (archived)](../../../blueprints/archive/2026-05-06_public-surface.md)
- [Round Story Completion Plan (active)](../../../blueprints/active/2026-05-05_round-story-completion-plan.md)
- [Capability Ergonomics Batch 2 (archived)](../../../blueprints/archive/2026-05-05_capability-ergonomics.md)

Working references:
- [Lessons Learned — 2026-05-03 reset](../rule-replay-line-redesign-input/60_lessons-learned.md)
- [Drift Analysis 2026-05-02](../rule-replay-line-redesign-input/30_drift-analysis-2026-05-02.md)
- [Conceptual Interaction Design — Check](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md)
- [Decision 1 — rule-replay design discussion A](../rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
- [Capability Layering L0-L11](../rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
- [Brainstorm — original audience statement](../rule-replay-line-redesign-input/00_brainstorm-original.md)

Module docs:
- [SDK Alignment Matrix](../../../../src/kernel/sdk/docs/01_alignment_matrix.en.md)
- [SDK User Guide](../../../../src/kernel/sdk/docs/00_user_guide.en.md)
