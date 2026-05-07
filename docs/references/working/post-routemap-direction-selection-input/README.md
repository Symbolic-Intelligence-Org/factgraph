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
| [30_recommendation.md](30_recommendation.md) | Recommended path (A+B), the finalized 21-principle inventory (#1-#19 + #P0/#P1) grounding subsequent scoping, rationale, and "what scoping next looks like" |
| [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) | Walker mechanism scoping artifact — lifts §6 *draft* exploration into structured proposal; aligns with EntitySnapshot prior art and SDK syntax; operationalizes walker contracts; sub-batches B1+B2 mandatory + B3 optional/future-only |

## Lifecycle

- **Active:** While the post-routemap direction is being decided.
- **Cited from blueprints:** When candidate directions become real blueprints, they should `Related Docs:` cite this bundle.
- **Archive:** When all referenced directions have either landed as implemented blueprints or been explicitly abandoned (with reactivation triggers if revisited).

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
- Walker scope refined: B1 (IR walker + protocol mixin) + B2 (cross-reference helpers) mandatory; B3 (audit walker) optional based on consumer signal
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
