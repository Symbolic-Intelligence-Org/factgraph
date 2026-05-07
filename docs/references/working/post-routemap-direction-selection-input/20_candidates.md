# 20 — Candidate Next-Layer Directions

> See [README.md](README.md) for context. Cross-references: [00_inventory.md](00_inventory.md), [10_implicit-gaps.md](10_implicit-gaps.md).

Nine candidates surfaced during the 2026-05-07 review. Ordered alphabetically (A through I), not by recommendation rank — the rank is in [30_recommendation.md](30_recommendation.md).

---

## A — Application-layer ergonomic helpers (extend Batch 2 pattern)

**Goal:** Cover the rest of the capability set with builder helpers in `kernel.application`, mirroring Batch 2's `build_fact_value_override` / `build_why_not_candidate_universe` / `build_frontier_view_facts`.

**Specifically:** Q1 Check, Q2 Diagnose, Batch 4 ProofFrame, Batch 5a/b/c rule overlays, Batch 6 round events. (See [10_implicit-gaps.md §3](10_implicit-gaps.md) for the table.)

**Inputs needed:** Each builder takes intent-shaped arguments (e.g. `rule_or_derivation`, `binding_dict`, `support`, `store`) and returns the corresponding protocol DTO ready for the runtime function.

**Effort:** ~1-2 weeks (8 helpers × focused tests + module docs update). Pure additions to `kernel.application/capability_helpers.py` (or one new file per family). No public surface change.

**Triggers / blockers:** None — fully internal to application layer. Aligned with Batch 2 precedent. Doesn't need any §5.5.5 reactivation.

**Trade-offs:**

| Pro | Con |
|---|---|
| No public-API commitment | Doesn't change SDK surface — power users still need to import from `kernel.application` |
| Doesn't break Decision 1 (no SDK substrate, no SDK shell) | Helpers don't help non-Python users |
| Fixes implicit debt (Gap 3 in [10_implicit-gaps.md](10_implicit-gaps.md)) | Some helpers may be premature without real call-site signal |
| Demos / automation / future SDK shells all benefit | If we later add SDK shell, helpers may need refactoring to match SDK shape |

---

## B — Walker mechanism (lift §6 *draft* design exploration into actual scoping)

**Status framing (REVISED 2026-05-07 after verification):** The walker direction comes from [check-operation-conceptual-interaction.md §6](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md), which the document itself marks as **draft discussion** (per its own §1.0 ordering rule, §6 loses to §1-§5 if conflict). B is **not** "implement an already-settled principle" — B is **lift the draft exploration into actual scoping** and validate it through implementation. The blueprint must explicitly state this status framing in §1 Problem.

**Goal:** Add walker / view abstractions in `kernel.application` (and optionally `kernel.audit` for B3) so users can iterate IR-tuple bodies, follow `asrt_id → assertion fact tuple` cross-references, and use wrapper-view `.filter` / `.find` / `.first` protocol over already-frozen DTO tuples — instead of reinventing this glue in every consumer (audit tool, automation script, demo notebook).

**Aligned with prior art:** [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py) `EntitySnapshot` / `AssertionNamespace` / `FieldAssertions` already implements namespace-walker pattern in SDK layer (`snap.assertions.field.active` / `.history` / `.at(t)` / `.version(v)`), with read-only enforced via `__setattr__` raising `FrozenSnapshotError`. New walker mechanism aligns naming/conventions with this prior art rather than reinventing.

**Refined scope (verification 2026-05-07 found most DTOs already structured):** Only ~4-5 raw-tuple objects truly need walker classes. See [10_implicit-gaps.md Gap 2](10_implicit-gaps.md) for the full per-object table. Sub-batched into:

| Sub-batch | Status | Scope |
|---|---|---|
| **B1 IR walker + common find/filter protocol** | mandatory | Walker over `RuleSpec.where` and `CompiledDerivationPlan.body_ir` (raw `list[Any]` IR); `FrozenTupleView` / `frozen_collection(...)` building block plus per-DTO wrapper views for already-frozen DTO tuples (SupportArtifact members, ProofFrameRecheckResult.atom_verdicts, etc.); no methods are added to existing tuple fields; aligns naming with EntitySnapshot prior art |
| **B2 evidence cross-reference helpers** | mandatory | `SupportArtifactView(...).lookup_assertion(asrt_id) → AssertionView(asrt_id, frozen_claim_index, frozen_meta_index=None)`; SupportArtifact atom-key parser (`b{branch}.a{index}:{pred_id}` format helper); generic `BindingView` / `BindingsView` wrapping for raw `BindingItems` tuples (first slice: DiagnoseAtomLocator.attempted_binding, WhyNotUniverseResult.green elements) |
| **B3 audit walker** | **OPTIONAL** | RoundEvents stream-style filter/group, audit ledger walkers — **only if AuditQuery / RoundEvents prove to be the first real consumer**. Not bundled with B1+B2 by default to respect heterogeneity (#3) and layer isolation (#5). |

**Effort:** ~2-3 weeks total. B1 ~1 week, B2 ~1 week, B3 ~1 week if triggered.

**Triggers / blockers:**

- **Reconciliation completed (verification 2026-05-07):** `EvidenceGraph` is the audit layer's unified cross-engine explainability DTO. It normalizes engine-native provenance (Souffle/ProbLog/PyReason) into a shared node-edge-layout representation, durable as `audit/evidence_graphs.jsonl`, queryable via `AuditQuery.get_candidate_evidence_graph(candidate_id)`, and rendered via `render_evidence_graph_html()`. It is frozen and immutable; not a traversal abstraction. The walker mechanism operates on raw protocol data before EvidenceGraph construction. Walkers and EvidenceGraph are complementary, not overlapping.
- Native engine first slice; PyReason / ProbLog adapter walker coverage deferred (separate trigger).
- B1 blocks on agreeing the IR walker shape (Rule.where + Plan.body_ir share the same IR vocabulary, so one walker class fits both); ~half-day Step 0 design.
- B2 defaults to frozen-index-backed `AssertionView(asrt_id, frozen_claim_index, frozen_meta_index=None)`, using existing `Claim` and optional `MetaRow` data. A store-backed `LiveAssertionView(asrt_id, store)` is B3/future scope and must declare its live nature explicitly per #10.
- B3 trigger: explicit user statement that audit consumer is high-frequency. Not auto-triggered by B1/B2.

**Walker design invariants (per principles in [30_recommendation.md](30_recommendation.md)):**

- Read-only by structural design (#8) — no `.set` / `.append` / `.delete` / `.mutate` on any walker view
- Determinism per #10 — DTO-backed walker trivially deterministic; if any walker is store-backed live (e.g. an EntityWalker B3 candidate), MUST declare snapshot semantics in API name or docs
- Per-layer isolation (#7 + #5) — application walker types not imported by audit walker, and vice versa
- Heterogeneous output, uniform access pattern (#3 + #7) — no `Walker[T]` generic base class enforcing common shape
- Lazy traversal (#9) — view construction O(1), data computed on demand

**Trade-offs:**

| Pro | Con |
|---|---|
| Lifts long-standing §6 draft exploration into actual implementation | Smaller scope than originally framed (most DTOs already structured); some reviewers may say "is this even worth a blueprint?" — answer: yes, IR walker + cross-ref helpers eliminate copy-pasted glue across all consumers |
| Pure ergonomic add, no public-API commitment | If we later add SDK walking on top, walker may need re-shape |
| Aligns with already-shipped EntitySnapshot prior art (no architectural debate) | B3 (audit walker) requires consumer signal we don't have yet — must keep B3 strictly optional |
| Demos / automation / future SDK shells all benefit | Determinism (#10) requires careful API naming for any store-backed walker |
| Closes "advanced importable feels primitive" critique for the actually-raw objects | None of the existing capability runtimes change — pure additive layer above protocol |

---

## C — Scenario-level SDK shell first slice (Check + Diagnose)

**Goal:** Reactivate [Batch 8 §5.5.5 row 1](../../../blueprints/archive/2026-05-06_public-surface.md) by shipping a narrow SDK wrapper for Check + Diagnose only — the highest-traffic / most-cohesive family per the falsifier analysis.

**Hypothetical shape:**

```python
# Today
result = check_derivation_binding(
    CheckRequest(plan=CompiledDerivationPlan(...), binding=..., engine='native'),
    store=store,
)
if result.status == 'failed':
    diag = diagnose_derivation_binding(
        DiagnoseRequest(plan=..., binding=..., engine='native'),
        store=store,
    )

# After Direction C
explain = sdk.explain(rule=eligible_rule, binding={'$p': alice}, store=store)
# explain.passed: bool
# explain.evidence: EvidenceWalker (depends on Direction B!)
# explain.failure: FailureExplanation (combines Diagnose + a friendly attempted_binding view)
```

**Effort:** ~2-3 weeks (Step 0 spike + outward DTO design + SDK shell module + delegate tests + outward-compat docs). Triggers a §5.5.5 reactivation, so it gets its own scoped blueprint with falsifiers.

**Triggers / blockers:**

- **Strongly benefits from Direction B already shipped** (otherwise `explain.evidence` is just a `SupportArtifact` and the SDK shell exposes its raw shape).
- Requires Step 0 spike per Batch 8 §5.5.5 — confirm outward shape doesn't leak `kernel.application.protocol` DTOs.
- Adds outward-compatibility commitment: once shipped, the `sdk.explain` shape is locked.

**Trade-offs:**

| Pro | Con |
|---|---|
| Genuine product surface improvement; first SDK shell since reset | Outward compat commitment locks shape |
| Scenario-level (not single-capability) wrapper is more useful than family-by-family | Only solves Check + Diagnose; other families still need their own §5.5.5 trigger |
| Demonstrates the §5.5.5 reactivation mechanism actually works | If shipped without B, exposes raw evidence shape (regret) |
| Aligned with Decision 1 strangler migration ("SDK wrapper 推到第二步") | Falsifier #18 was PARTIAL — evidence said "later, not now" |

---

## D — Dialog agent revival (non-technical SME entry point)

**Goal:** Ship the original product-public layer per [2026-03-29_dialog-agent-blueprint-v1.md](../../../blueprints/active/2026-03-29_dialog-agent-blueprint-v1.md) + delta. Multi-turn dialogue, document extraction, engine routing, NLU layer.

**Effort:** **Weeks to months**. Requires service layer decision (not done), multi-LLM provider integration (LiteLLM or equivalent), NLU pipeline, batch commit orchestration, state machine, etc.

**Triggers / blockers:**

- Service routes (Batch 8 §5.5.5 row 3) are also deferred — dialog agent likely depends on that.
- Multi-LLM integration is a new dependency surface entirely.
- Currently zero user signals demanding this (per Gap 1, this is the original vision but was implicitly de-prioritized).
- Almost certainly v0.2+ scope.

**Trade-offs:**

| Pro | Con |
|---|---|
| Resolves Gap 1 (the strategic narrowing) | Multi-week to multi-month effort |
| Returns to the original product vision | Requires v0.2 scope commitment |
| Genuinely opens product to non-technical users | Heavy new dependencies |
| Pre-existing blueprint (v1 + v1.1-delta) reduces design cost | No demand signal yet |

---

## E — Release-day workflow (publish v0.1 to PyPI / public repo)

**Goal:** Execute the publish workflow that the RC blueprint and Batch 8 prepared but did not run. Per memory, `v0.1-oss-prep` and `master` are sacred; this is **strictly user-gated**.

**Effort:** Hours — all technical gates passed. Just walk through publish script + tag + push.

**Triggers / blockers:**

- **Explicit user authorization required** (sacred branches).
- No technical blocker.

**Trade-offs:**

| Pro | Con |
|---|---|
| All RC work pays off | Locks v0.1 surface publicly — outward compat starts ticking |
| Real user feedback can begin | Currently no user feedback signal demanded by the project — could wait |
| Doesn't conflict with any other direction | Once published, v0.1 surface changes get harder |

---

## F — Demo refresh (this session's leftover framing)

**Goal:** Either rewrite the 4 chaptered notebooks per the SDK-product / Advanced-importable framing discussed mid-session, or accept current inline form.

**Effort:** Half-day to 1 day depending on framing choice.

**Triggers / blockers:** Downstream of which layer ships next. If A/B land, "advanced" chapters become less advanced naturally. If C lands, 01+02 expand and 03+04 may consolidate.

**Trade-offs:** Defer until layer choice is made.

---

## G — Batch 4 ProofFrame `rule_refs` hardening

**Goal:** [Batch 8 §5.5.5 row 7](../../../blueprints/archive/2026-05-06_public-surface.md) — independent post-archive hardening of legacy-field rejection in ProofFrame `rule_refs`.

**Effort:** ~1 week (focused gate + tests + docs). Pure hardening, no new surface.

**Triggers / blockers:** None — explicitly carved out and ready to start.

**Trade-offs:**

| Pro | Con |
|---|---|
| Narrow, well-defined, low-risk | Pure hardening — no user-facing improvement |
| Closes a known §5.5.5 deferral | Doesn't help current direction-selection question |
| Could run in parallel with A/B | Pure interruption if not relevant to current focus |

---

## H — Direction D unified status vocabulary

**Goal:** [Round Story Plan §10.4](../../../blueprints/active/2026-05-05_round-story-completion-plan.md) — unify `passed/failed/unsupported/invalid_request` status vocabulary across capabilities.

**Effort:** ~1-2 weeks (audit current per-capability enums + cross-reference + transition + tests).

**Triggers / blockers:** Reactivation trigger = cross-capability single-vocabulary consumer need. **No such consumer currently exists** — this is investigation-style rather than need-driven.

**Trade-offs:** Premature without consumer signal. Skip unless a concrete consumer surfaces.

---

## I — New engine onboarding (§3.5 / §6.7 trigger)

**Goal:** Onboard a new reasoning engine (e.g. SAT solver, Z3, custom rule engine), which would force `§6.7 Declarative engine capability schema` to fire.

**Effort:** **Weeks** — depends on engine. Plus the §6.7 schema design that becomes mandatory.

**Triggers / blockers:** No concrete engine candidate identified. Speculative.

**Trade-offs:** Skip unless you have a specific engine in mind.

---

## Summary trade-off matrix

| # | Direction | Effort | Public-API risk | Triggers? | Resolves Gap | Recommendation rank (see §30) |
|---|---|---|---|---|---|---|
| A | App ergonomic helpers | 1-2w | None | None | Gap 3 | **#1** |
| B | Walker mechanism (B1+B2 mandatory, B3 optional) | 2-3w (B1: 1w, B2: 1w, B3: 1w if triggered) | None | Reconcile w/ Evidence Graph (verified: no overlap); B3 needs consumer signal | Gap 2 | **#2** |
| C | Check+Diagnose SDK shell | 2-3w | Locks outward shape | §5.5.5 row 1; needs B1+B2 landed first | partial Gap 2/3 | **#3 (after A+B1+B2)** |
| D | Dialog agent revival | weeks-months | New surfaces | Service blueprint + LLM deps | Gap 1 | **deferred to v0.2+** |
| E | Release publish | hours | Locks v0.1 surface | User authorization | none | **on user call** |
| F | Demo refresh | <1 day | None | Downstream of A/B/C | Gap 4 | **after layer choice** |
| G | Batch 4 hardening | 1w | None | None | none | **parallel-safe** |
| H | Unified status vocab | 1-2w | None | Cross-capability consumer | none | **defer (no signal)** |
| I | New engine onboarding | weeks | New surfaces | Concrete engine candidate | none | **defer (no candidate)** |
