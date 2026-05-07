# 50 — A+B Migration Path

> See [README.md](README.md) for context. Cross-references: [30_recommendation.md "Plausible follow-ons"](30_recommendation.md), [40_walker-mechanism-design-sketch.md §5](40_walker-mechanism-design-sketch.md), [41_application-builders-design-sketch.md §5](41_application-builders-design-sketch.md).

---

## Status framing (READ FIRST)

This document is **not** an implementation plan and **not** a mandate to rewrite demos during A or B implementation.

It is a **reference migration sketch** for A and B implementations + downstream consumers (demo notebooks, automation scripts, future SDK / L shells). It captures migration constraints so:

- A blueprint and B blueprint can cite a shared migration contract instead of inventing their own
- Demo / example follow-up work happens **after** A and B archive, not as part of A/B blueprint scope
- Future L SDK shell migration appends to this file rather than spawning a parallel doc

A and B are Tier 2 advanced importable additions. They do not change Tier 1 SDK surface. Migration of existing consumers is opt-in incremental.

---

## 1. Migration principles

| Principle | Locked by |
|---|---|
| **Additive only** — no existing import path breaks; no method removed; no DTO field renamed or retyped | `#1` application-first authority + `#6` no outward compat |
| **Old direct DTO construction continues to work** — manual `CheckRequest(plan=..., binding=..., engine=...)` instantiation remains valid forever | `#1` |
| **No SDK surface change in A or B** — `kernel.sdk.__all__` not modified; SDK quickstart unchanged; SDK user guide unchanged | `#6` + Round 6 D2 acceptance gate |
| **No protocol DTO field type changes** — A wraps inputs into existing DTOs; does NOT mutate the DTO definitions themselves | `#1` |
| **Walker views are wrappers, not replacements** — raw tuple field access on existing DTOs (e.g. `support.pred_witnesses[0].asrt_ids`) continues to work; walker views are an additional optional access path | `#8` + 2026-05-07 Round 6 wrapper-view design |
| **Migration is opt-in, incremental** — consumers may adopt builders / walker views family-by-family; partial migration is supported | derived from above |

---

## 2. Existing consumer classes

| Class | Examples | Migration disposition |
|---|---|---|
| Demo notebooks | `examples/01_sdk_check_diagnose.ipynb` ... `examples/04_round_persistence_diff.ipynb` | Opt-in incremental;follow-up work after A/B archive |
| Integrated demo script | `examples/round_story_full_demo.py` | Same;optionally maintained in two-form (verbose + ergonomic) for teaching |
| Tests | `src/kernel/tests/test_examples_*` etc. | Continue to test the canonical script;new builder/walker tests added separately |
| Future SDK / L shells | not yet implemented | Will reuse A's builders + B's walker views internally;A and B are L's prerequisites per [Direction A — Input shape lock](30_recommendation.md) bridging clause |
| Future agent / service / custom integration | not yet in repo | Will import A and B directly from `kernel.application` (per `#5` parallel architecture, [Batch 8 §5.5.1](../../../blueprints/archive/2026-05-06_public-surface.md) Tier 2) |
| Audit / automation scripts | not yet in repo | Same as above |

---

## 3. Direction A migration preview

Per-capability family migration sketch. Detailed line-level migration is deferred to follow-up demo PRs.

| Family | Current pattern | Post-A helper | Expected benefit | Migration risk |
|---|---|---|---|---|
| Q1 Check | `CheckRequest(plan=..., binding=tuple(sorted([...])), engine="native")` | `build_check_request(plan, binding={...}, engine="native")` | Saves ~3 lines + binding sort boilerplate | None;DTO output equals manual construction (per [Gap ε contract test](41_application-builders-design-sketch.md)) |
| Q2 Diagnose | Similar to Q1 with `DiagnoseRequest(...)` | `build_diagnose_request(...)` | Same | Same |
| Batch 4 ProofFrame Recheck | Manual `ProofFrameRecheckRequest(support_artifact=..., overlay=...)` + manual `EvaluationOverlay()` for baseline | `build_proof_frame_recheck_request(support, overlay=None)` | Default `overlay` simplifies baseline call | None |
| Batch 5 rule overlays (3 sub) | Manual `RuleDisableRequest(rule_spec=..., support_artifact=..., overlay=...)` etc. | 3 sub-builders with branch/atom indices keyword-only | Reduces argument noise | None;heterogeneity preserved per `#3` |
| Batch 6 round events | 5 separate `project_<kind>_event_payload(...)` imports | Single `build_round_event_payload(kind=..., request=..., result=...)` | Reduces import surface 5 → 1 | `kind` literal must match request/result pair shape (caught by helper at construction) |

**Demo impact (preview only):** `examples/round_story_full_demo.py` and 4 chaptered notebooks: estimate ~30–50 lines simplified, ~5–8 imports removed across the integrated demo. **Migration is follow-up work, not A blueprint scope.**

---

## 4. Direction B migration preview

Per-sub-batch migration sketch.

| Sub-batch | Current pattern | Post-B view / helper | Expected benefit | Migration risk |
|---|---|---|---|---|
| **B1 IR walker + collection protocol** | Raw `for atom_tuple in rule_spec.where:` then manual `kind, *args = atom_tuple` unpacking | `IRBodyWalker(rule_spec.where)` with `for atom in walker:` exposing `atom.kind` / `atom.pred_id` / `atom.args` / `atom.branch_index` / `atom.atom_index` | Eliminates raw tuple unpacking | None;raw tuple access continues to work on `rule_spec.where` |
| **B1 frozen tuple wrapper** | Direct iteration on `support.pred_witnesses` | `SupportArtifactView(support).pred_witnesses` (FrozenTupleView) supports `.filter` / `.find` / `.first` / `.require_*` | Per-DTO ergonomic without DTO mutation | None;direct tuple access on `support.pred_witnesses` continues to work |
| **B2 evidence cross-reference** | Manual `pred_atom_key.split(":")` parsing + manual ledger `get_claim(asrt_id)` | `parse_atom_key(key) -> AtomKeyView`;`SupportArtifactView.lookup_assertion(asrt_id, frozen_index) -> AssertionView` | Eliminates atom-key string parsing + ledger boilerplate | Caller must provide `frozen_claim_index` at view construction (per Gap β) |
| **B2 ProofFrameDiffView** (Round 7 addition) | Nested loops over `diff.frame_deltas` filtering by `frame_status_change` kind, then nested over `atom_deltas` | `ProofFrameDiffView(diff)` with `.frame_deltas_with_status_change()` / `.all_atom_deltas_flattened()` (sketch names) | Eliminates nested-loop filter boilerplate | None |
| **B3 audit walker** | Direct iteration on `package.round_events` | (deferred / future-only) | (n/a — B3 not in current scope) | n/a |

**Demo impact (preview only):** chapter 03 (ProofFrame + rule overlays) and chapter 04 (round persistence + diff) see the most simplification when ProofFrameDiffView and SupportArtifactView land. **Migration is follow-up work, not B blueprint scope.**

---

## 5. Incremental migration order

| Order | Notes |
|---|---|
| **A and B independent** | Either may ship first;both are Tier 2 advanced importable additive |
| **B1 → B2 strict** | B2 (cross-reference helpers) depends on B1 (frozen-tuple wrapper protocol) |
| **B3 deferred** | Not in v0.1 scope per `#14` + Round 6/7 audit;reactivation requires real audit/store stream consumer |
| **Demos partial migrate** | A lands first → demo cells switch to builders, still iterate raw tuples in result wrapping. B lands first → demo cells walk via views, still construct request DTOs manually. Either order works |
| **Tests unchanged during migration** | Canonical demo unittest (`test_examples_round_story_full_demo`) tests the script's `EXPECTED_PHASE_SUMMARY`;migration of demo internals does not change assertions |

---

## 6. Backward compatibility guarantees

A and B both honor:

- **No removal:** every existing `kernel.application` / `kernel.audit` / `kernel.core` public function and DTO continues to be importable and callable
- **No retype:** existing protocol DTO field types (e.g., `tuple[PredWitness, ...]` on `SupportArtifact.pred_witnesses`) are not changed; walker views are an alternative access path, not a replacement
- **No SDK quickstart rewrite:** `README.md` quickstart code block continues to print `Alice` (per Round 6 D2 verification gate)
- **No SDK user guide migration:** `kernel.sdk.docs.00_user_guide.en.md` text describing `sdk.batch()` / `sdk.evaluate()` / etc. is unchanged
- **No protocol DTO addition unless required:** A wraps to existing DTOs; B wraps existing tuples in views. New DTO types (e.g., `AtomKeyView`, `WalkerStats`) live in `kernel.application` / `kernel.audit` but are advanced importable, not in `kernel.sdk.__all__`
- **Examples migration is opt-in:** archive notebooks (`examples/archive/*`) remain unchanged; current `examples/0[1-4]_*.ipynb` may migrate in follow-up PRs after A/B archive

---

## 7. Out of scope

This file does **not** cover:

- **v0.1 publish migration** — that is Direction E (release publish), user-gated
- **Cross-engine adapter migration** — ProbLog / PyReason adapter walker is separate trigger per [evidence-ecosystem audit Lane 5](README.md)
- **L SDK shell migration** — when L (Direction L, post-A+B v1-ready roadmap target per [30_recommendation.md "Plausible follow-ons"](30_recommendation.md)) lands, L's per-family migration appends to this file as new sections
- **Service / dialog agent migration** — Direction D, deferred to v0.2+
- **Internal core/audit module reorgs** — out of A+B scope

---

## 8. Blueprint handoff checklist

The following items must appear in A blueprint and B blueprint acceptance / non-goals sections, citing this file by reference.

### A blueprint must cite / check

- A's acceptance lists: "A does not rewrite demos in the same blueprint scope. Demo migration is follow-up doc work, optionally tracked in a separate PR after A archive."
- A's acceptance lists: "A does not modify `kernel.sdk.__all__` or any SDK examples / quickstart / user guide."
- A's non-goals lists: "No SDK Rule lowering inside A; bridging is L's responsibility per [Gap β resolution](30_recommendation.md)."
- A's `§6 Boundaries-and-Invariants` references `#1`, `#5`, `#6`, plus Batch 2 §6 helper-layer constraints (no sibling runtime call, no frontier import, no ledger writes).
- A's acceptance includes contract test items per [41_ §6](41_application-builders-design-sketch.md).

### B blueprint must cite / check

- B's acceptance lists: "B does not remove direct tuple access on existing DTOs. `support.pred_witnesses[0].asrt_ids` continues to work after B archives."
- B's acceptance lists: "B does not modify `kernel.sdk.__all__` or any SDK examples / quickstart / user guide."
- B's acceptance lists: "B does not rewrite demos in the same blueprint scope. Demo migration is follow-up doc work."
- B's `§6 Boundaries-and-Invariants` references all walker invariants `#7–#19` operationalized in [40_ §4](40_walker-mechanism-design-sketch.md).
- B's acceptance includes contract test items per [40_ §6](40_walker-mechanism-design-sketch.md), including the future-B3-only sketches as reserved (not implemented).
- B's non-goals: "B3 audit / store stream walker is not implemented; only documented as reserved future contract."

### Demo follow-up (post-A and post-B archive) must decide

- Which chaptered notebook migrates first;migration order independent or coordinated with `round_story_full_demo.py`
- Whether `round_story_full_demo.py` migrates in a single PR or staged per family
- Whether the old verbose form is preserved alongside the new ergonomic form (two-form demos for teaching) or replaced
- Whether `examples/README.md` chapter index updates immediately or after all chapters migrate
- Whether `test_examples_round_story_full_demo` assertion contract changes (default expectation: unchanged — assertions are on `EXPECTED_PHASE_SUMMARY` outcome, not internal call shape)
