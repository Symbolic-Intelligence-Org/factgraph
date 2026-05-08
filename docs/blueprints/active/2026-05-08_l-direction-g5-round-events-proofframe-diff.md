# L Direction G5 — Round Events + ProofFrame Diff SDK Shell

- **Status:** draft
- **Created:** 2026-05-08
- **Last Updated:** 2026-05-08
- **Parent:** L Direction (final group; closes the 5-group SDK shell rollout G1→G4→G2→G3→G5 per [post-routemap-direction-selection-input/30_recommendation.md:600](../../references/working/post-routemap-direction-selection-input/30_recommendation.md))
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g3-rule-overlays (archived)](../archive/2026-05-08_l-direction-g3-rule-overlays.md) — Rule overlays; established §5.1+§5.2 substrate-IR-out clarification + shared `resolve_runtime_registry` boundary normalizer
  - [2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck (archived)](../archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md) — established §5.1+§5.2 raw-application-DTO-at-SDK-boundary precedent
  - [2026-05-08_l-direction-g4-why-not-frontier (archived)](../archive/2026-05-08_l-direction-g4-why-not-frontier.md) — Frontier explicitly kept advanced importable per §5.4 (continues to apply for G5 — Frontier still NOT in scope)
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md) — established SDK shell template + Q1 Sibling discipline
  - [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md)
  - [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md) — provides `ProofFrameDiffView` advanced-importable Tier 2 view, already in use
- **Audit Log:** [2026-05-08_l-direction-g5-round-events-proofframe-diff.audit.md](./2026-05-08_l-direction-g5-round-events-proofframe-diff.audit.md)
- **Baseline:** G3 topic tip `112401a` (G3 published HEAD `cb6d3bd` + post-publish polish: shared helper test sibling-symmetry + dropped unreachable `ValueError` + structural-lag note). Forward-only inheritance — does NOT advance any G3 published ref. Path B combined published snapshot at G5 close-out will be `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-2026-05-08`.

## 1. Problem

L Direction has shipped four SDK shell groups so far (G1 Check + Diagnose, G4 Why-not + Frontier-defer, G2 Fact Overlay + ProofFrame Recheck, G3 three rule overlays). The fifth and final group — Round events + ProofFrame Diff — is the **only remaining capability that an SDK consumer cannot reach without dropping to advanced importable**. As long as that gap exists, the round-story coverage claim ("a SDK consumer can run the full round story without reaching for `kernel.audit`") is incomplete, and the post-L SDK ergonomics redesign blueprint cannot frame "narrow SDK surface" as a stable starting point.

Concretely:

- The application / audit layers already have everything: `kernel.audit.round_events` ships `RoundRecorder` + `start_round` + `record_round_event` + `finalize_round` + 5 `project_*_event_payload(...)` projection helpers + `write_round_events_atomic(...)` persistence + 7 frozen DTOs (`RoundEvent`, `RoundSummary`, etc.); `kernel.audit.proof_frame_diff` ships pure `build_proof_frame_diff(...) -> ProofFrameDiff` (frozen) + 6 supporting frozen DTOs; and `kernel.application.walker.ProofFrameDiffView` ships a Tier 2 walker view over the diff. Verified at `src/kernel/audit/round_events.py:99-228` and `src/kernel/audit/proof_frame_diff.py:160-191`.
- `kernel/sdk/` references **none** of these names (verified by `grep -rn "ProofFrameDiff\|build_proof_frame_diff\|round_events\|RoundRecorder\|start_round" src/kernel/sdk/` — zero hits at `112401a`). So a SDK consumer who wants to record a round or diff two rounds today must `from kernel.audit import ...` directly.
- The Round 8 SDK conventions audit ([post-routemap bundle/30_recommendation.md:610](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)) already flagged G5 as **mismatch — pending Step 0 shape decision**:
  > G5 Round events + Diff: pending Step 0 shape decision — recorder lifecycle (raises) mixes with query API (typed DTO returns) inconsistently; SDK boundary may keep round recorder as `kernel.audit` advanced-importable and surface only `diff_proof_frames(...)` on the SDK facade.

  That hint is one candidate answer to §5.1, not a conclusion — the blueprint's §5 falsifier passes will source-ground it.

## 2. Goals

- **Close the L Direction sequence** by shipping the final group of SDK shells. After G5, every L-Direction L-Full slot from the 2026-05-07 round-story-completion target is reachable through `SDKStore.<method>(...)` without dropping to advanced importable.
- **Decide the recorder lifecycle question** — does the stateful `RoundRecorder` API (`start` / `record` / `finalize` raising `RoundEventError`) cross the SDK boundary, or does it stay advanced importable while only the pure-function diff query gets a SDK shell? Round 8 leans toward the latter; §5.1 must source-ground.
- **Decide the ProofFrame Diff input shape** — does the SDK accept raw `tuple[RoundEvent, ...]` directly (extending G2's precedent to `kernel.audit` DTOs), or does it accept a recorded-package path that the SDK reads internally, or some combination?
- **Preserve every prior L invariant**: `kernel.sdk.__all__` length stays at **34**; no SDK-side wrapping of frozen application/audit DTOs; raw passthrough returns; per-method `$.<method>.<arg>` error remap; Sibling discipline (no SDK shell calls another SDK shell at runtime); 8-shell layout in `kernel/sdk/shells/` continues with 1-3 new shell files.
- **Inherit the G3 verification-round shared helper** — any new dependency-resolution boundary in G5 (probably none — Round events / Diff don't lower derivations or rules) must use `resolve_runtime_registry` if it appears.
- **Settle the cross-cutting precedent layer question** — G2 §5.1+§5.2 said "raw application protocol DTOs are OK"; G3 said "but substrate IR is NOT". G5 brings a third layer (`kernel.audit`) into scope — §5.1 / §5.3 must extend the precedent or carve `kernel.audit` out.

## 3. Non-Goals

- **No Frontier resurrection.** G4 §5.4 explicitly kept Frontier as advanced importable per the evaluator drift gate; G5 does not reopen that.
- **No `kernel.audit` redesign.** Recorder lifecycle, persistence file format, schema version, event kinds — all out of scope. G5 only decides whether a thin SDK shell wraps existing audit-layer entry points.
- **No new application-layer DTO.** `RoundEvent` / `RoundSummary` / `ProofFrameDiff` / `FrameDelta` / `AtomDelta` / `FrameIdentity` / `FrameStatusChange` etc. are already frozen at `kernel.audit`; G5 does NOT add wrappers, normalizers, or intermediate DTOs.
- **No `RoundRecorder` re-implementation.** If §5.1 lands "ship recorder", the SDK shell delegates to `kernel.audit.start_round` / `record_round_event` / `finalize_round` 1:1, just like G3 delegates to `build_rule_disable_request` / `check_rule_disable_action`.
- **No event-projection helper resurfacing.** The 5 `project_*_event_payload(...)` helpers stay at `kernel.audit` advanced importable; G5 does not surface them through the SDK facade — those helpers consume request+result objects callers already have, so SDK callers can use them directly via `kernel.audit` if needed.
- **No diff persistence side effects.** `kernel.audit.proof_frame_diff.build_proof_frame_diff` is a pure function returning a frozen DTO; SDK shell preserves that purity (no ledger writes, no audit-package writes).
- **No round-package-reading helper on SDK.** `write_round_events_atomic(package_dir, events) -> Path` and any future read-side counterpart stay at `kernel.audit`. G5 may take raw `tuple[RoundEvent, ...]` as input but does not own file IO.
- **No post-L SDK ergonomics redesign.** Per `feedback_sdk_ergonomics_redesign_target`, OpenAI-style `Client.round.*` namespace migration is post-L. G5 stays on the `SDKStore.<method>` flat pattern with verb-first naming. After G5 closes, the redesign blueprint can revisit the entire SDK shape.
- **No `store.py:1024 / store.py:1154` (`run` / `evaluate`) hygiene.** That out-of-scope flag from G3's post-publish verification round addendum stays out-of-scope here too — they pre-date L Direction shells and have different upstream callers. Tracked for separate hygiene blueprint.

## 4. Current Context

### 4.1 Round events application surface (`kernel.audit.round_events`)

Verified at `src/kernel/audit/round_events.py` (HEAD `112401a`):

- **Stateful API** — `RoundRecorder` `@dataclass` with three lifecycle methods:
  - `RoundRecorder.start(*, event_ts=None) -> RoundEvent` — must be called once; `RoundEventError("round already started")` on second call.
  - `RoundRecorder.record(*, kind, payload, event_ts=None) -> RoundEvent` — appends a non-lifecycle event; raises `RoundEventError` for invalid kind.
  - `RoundRecorder.finalize(*, event_ts=None) -> RoundEvent` — must be called once after start; `RoundEventError` on second call or unfinalized then finalize.
- **Free-function wrappers** — `start_round(round_id, *, event_ts) -> RoundRecorder`, `record_round_event(recorder, *, kind, payload, event_ts)`, `finalize_round(recorder, *, event_ts)`. These delegate to the recorder methods and add `RoundEventError("recorder must be RoundRecorder")` type guards (`round_events.py:175-187`).
- **5 projection helpers** — `project_check_event_payload(request, result) -> dict[str, JSONValue]`, plus `project_diagnose_event_payload`, `project_fact_overlay_event_payload`, `project_why_not_event_payload`, `project_proof_frame_event_payload`. Pure functions, no side effects, no SDK dependency.
- **2 lifecycle event constructors** — `make_round_started_event(round_id, *, event_ts)`, `make_round_finalized_event(round_id, *, sequence, event_ts)`.
- **Persistence** — `write_round_events_atomic(package_dir, events) -> Path` writes `audit/round_events.jsonl` atomically. Read-side: `round_event_from_row(row) -> RoundEvent` for round-trip via `round_event_to_row(event)`. Audit package loader exists at `kernel.audit.reader.load_audit_package`.
- **7 frozen DTOs** — `RoundEvent`, `RoundSummary` (both `@dataclass(frozen=True)` at `round_events.py:39`, `:65`). `ROUND_EVENT_KINDS` is `frozenset` of 7 strings. `RoundEventError(ValueError)` for misuse.
- **No SDK consumer.** Verified zero hits in `kernel/sdk/`.

### 4.2 ProofFrame Diff application surface (`kernel.audit.proof_frame_diff`)

Verified at `src/kernel/audit/proof_frame_diff.py` (HEAD `112401a`):

- **Pure function** — `build_proof_frame_diff(*, round_a_id, round_b_id, round_a_events, round_b_events, warnings=(), include_unchanged=False) -> ProofFrameDiff` (`proof_frame_diff.py:160-191`). Takes two `tuple[RoundEvent, ...]` and produces a frozen `ProofFrameDiff`. No side effects.
- **6 frozen DTOs** — `ProofFrameDiff` (root), `FrameDelta`, `AtomDelta`, `FrameIdentity`, `FrameStatusChange`, `EventReference` — all `@dataclass(frozen=True)`. `ProofFrameDiffError(ValueError)` for misuse.
- **Walker view available** — `kernel.application.walker.ProofFrameDiffView(diff)` already exists as Tier 2 advanced-importable view (`walker/views.py:376-415`). Read-only frozen wrapper. SDK callers who want ergonomic traversal can opt in directly without G5 surfacing it.
- **No SDK consumer.** Verified zero hits in `kernel/sdk/`.

### 4.3 Round 8 SDK conventions audit verdict for G5

[post-routemap bundle / 30_recommendation.md:610](../../references/working/post-routemap-direction-selection-input/30_recommendation.md): "G5 Round events + Diff: pending Step 0 shape decision — recorder lifecycle (raises) mixes with query API (typed DTO returns) inconsistently; SDK boundary may keep round recorder as `kernel.audit` advanced-importable and surface only `diff_proof_frames(...)` on the SDK facade."

[README.md:148](../../references/working/post-routemap-direction-selection-input/README.md): "G5 Round + Diff: mismatch (recorder lifecycle raises mixed with query DTO returns)."

**These are hints, not conclusions.** §5.1 falsifier must source-ground.

### 4.4 Inheritance from G1-G4

Active substrate / patterns G5 inherits without re-deciding:

- **`kernel/sdk/shells/` subpackage** — currently 8 modules (G1: check, diagnose; G4: why_not; G2: fact_overlay, proof_frame; G3: rule_disable, rule_literal_replace, rule_add_condition; plus shared `_validation.py`). G5 adds 1-3 new shell files depending on §5.1 outcome.
- **`kernel/sdk/shells/_validation.py` shared helpers** — 6 input validators + 1 boundary normalizer (`resolve_runtime_registry`). G5 may add new shared validators if 2+ G5 shells need them; otherwise inline-validate.
- **Sibling discipline at 8-shell scope** — each new shell tests against all 8 sister shells (runtime patch + static source scan). Becomes 9-11 if G5 adds 1-3 shells.
- **§5.1+§5.2 cross-cutting precedent (G2 + G3)** — raw frozen application protocol DTOs (e.g., `EvaluationOverlay`, `SupportArtifact`, `RuleLiteralPath`, `RuleAddedAtom`) are OK at SDK boundary; substrate IR (`RuleSpec` at `kernel.core.rules.rule_ir`) is NOT. G5 brings a third candidate layer — `kernel.audit` (`RoundEvent`, `ProofFrameDiff`, etc.) — into the question. §5.1 / §5.3 must extend or carve.
- **Documented passthrough returns** — every L method returns the raw application DTO; nothing in `kernel.sdk.__all__` (length stays at 34).
- **Per-method 6-path remap** — `$.<method>.<input>` for each input boundary; `$.<method>.request` for DTO `__post_init__`; base `$.<method>` for defensive runtime exception. G5 will need fewer remap paths if recorder defers (no dependency-registry call, no derivation lowering).
- **Per-phase strict audit** + iterative gap-design (one §5.x lock at a time, except low-suspense batches).
- **`#P1` carve-out pattern** — if a pre-G5 application-runtime test asserts "no SDK surface for round events / diff", retrofit in-place per `#P1` (mirrors G2 Phase 0 retrofitting G1+G4 invariants and G3 retrofitting Rule * boundary tests).
- **Path B combined snapshot strategy** — at G5 close-out + publish, create `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-l-g5-2026-05-08` as the 5th immutable Path B snapshot; G3 combined snapshot `...-l-g1-l-g4-l-g2-l-g3-2026-05-08` @ `cb6d3bd` stays frozen.
- **Frontier still advanced importable** per G4 §5.4 evaluator drift gate.
- **`feedback_sdk_ergonomics_redesign_target`** — post-L; G5 stays on `SDKStore.<method>` flat pattern.

## 5. Design — Step 0 Questions

**Convention:** Each §5.x question lists what must be source-grounded by a falsifier pass before locking. **No question below has a final decision yet.** Per `feedback_iterative_gap_design`, decisions land one at a time (or in low-suspense batches), each in its own commit, with a fresh falsifier scan against the codebase HEAD.

### 5.1 Does Round events ship as a SDK shell at all?

**Question:** Three options:
- **(A) Defer entirely** — Round events stays `kernel.audit` advanced importable. SDK gains no recorder shell. Round 8's hint.
- **(B) Ship recorder lifecycle** — SDK gets `start_round` / `record_round_event` / `finalize_round` as 3 thin delegates. Recorder is stateful; the SDK shell would expose an instance to callers (returning a `RoundRecorder`-like handle) which is a new pattern (no other L method returns a mutable object).
- **(C) Ship event-builder shell only** — SDK gets `make_round_event(*, kind, payload, ...)` style pure-function shells, but recorder lifecycle stays at `kernel.audit`. Hybrid.

**Conservative default:** option (A) — defer entirely, per Round 8 hint and the principle that mutable-state-returning methods are a new category for `SDKStore`.

**Decision (2026-05-08):** Lock **option (A) — defer Round events from SDK entirely**. G5 narrows to a single SDK shell on the pure query side: ProofFrame Diff. Recorder capture stays at `kernel.audit` advanced importable, where it has been stable since Batch 6. The downstream call shapes are:

```python
# G5 ships (the pure query side):
SDKStore.diff_proof_frames(...) -> ProofFrameDiff
```

```python
# G5 deliberately does NOT ship (capture stays advanced importable):
from kernel.audit.round_events import (
    start_round,
    record_round_event,
    finalize_round,
)
```

This matches the event-sourcing-style split (capture is an external, stateful, persistence-adjacent concern; query is pure and SDK-friendly) and preserves every prior L invariant.

**Falsifier outcomes (all 4 PASS for defer):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | All existing L methods return frozen DTOs and never mutable objects | Verified 8 L methods at `src/kernel/sdk/store.py`: `check` → `CheckResult`; `diagnose` → `DiagnoseResult`; `why_not` → `WhyNotUniverseResult`; `check_fact_overlay` → `FactOverlayCheckResult`; `recheck_proof_frame` → `ProofFrameRecheckResult`; `check_rule_disable` → `RuleDisableResult`; `check_rule_literal_replace` → `RuleLiteralReplaceResult`; `check_rule_add_condition` → `RuleAddConditionResult`. All eight return DTOs are `@dataclass(frozen=True)`. `RoundRecorder` at `src/kernel/audit/round_events.py:99` is `@dataclass` **without** `frozen=True`, with mutable `_events: list[RoundEvent]` + `_started: bool` + `_finalized: bool` state. Shipping it would be the first L method returning a mutable object — a category split with no precedent. | PASS — defer preserves the all-frozen-DTO L category invariant. |
| F2 | Genuine consumer signal for SDK-side recorder ergonomics | `grep -rn "SDKStore\.\(start\|record\|finalize\)_round" docs/ src/` — zero hits. Round 8 audit at `docs/references/working/post-routemap-direction-selection-input/30_recommendation.md:610` explicitly hints "may keep round recorder as `kernel.audit` advanced-importable". The Batch 6 round-persistence blueprint at `docs/blueprints/archive/2026-05-05_round-persistence.md:470` declared "external buffered recorder APIs ... No application capability runtime imports `kernel.audit`" — recorder was always designed as orthogonal/external. The canonical user-facing example `examples/round_story_full_demo.py` already imports `start_round` / `record_round_event` / `finalize_round` directly from `kernel.audit.round_events`. Defer breaks zero UX expectations — users already do exactly this. | PASS — `#6` (no outward compat without user signal) supports defer. Ship would create new outward surface without signal. |
| F3 | Recorder API can be compressed into a single pure call | Examined `RoundRecorder.start/record/finalize` (`src/kernel/audit/round_events.py:108-160`): accumulates `_events: list[RoundEvent]` across N calls; `sequence` numbering = `len(self._events)` order-sensitive; `finalize()` writes JSONL via `write_round_events_atomic(package_dir, events)` — file IO, not pure. Typical usage interleaves `recorder.record(...)` between capability calls (e.g., `sdk.check(...)` → record → `sdk.diagnose(...)` → record → finalize). Cannot reasonably collapse to `record_round(round_id, events) -> tuple[RoundEvent, ...]` — that would force callers to construct `RoundEvent` instances themselves with manual sequence numbering, which is exactly the state the recorder owns. | NOT compressible — option (D) rejected. Defer is cleaner. |
| F4 | Deferring breaks any existing test asserting "SDK exposes the full round story" | `grep -rn "test_no_sdk_round_events\|test_no_sdk_proof_frame_diff" src/kernel/tests/` — zero hits. `test_sdk_consumer_boundary.py` has zero references to `round_events` / `proof_frame_diff` / `RoundRecorder`. No pre-G5 boundary test asserts "no SDK round" — defer is the natural state, no `#P1` retrofit needed for the recorder side. (Diff side: see §5.9 — `test_audit_proof_frame_diff.py` exists but tests audit-layer pure function only; no "no SDK surface" assertion.) | PASS — defer breaks zero existing tests. |

**Forward implications:**

- G5 becomes a **1-method shell**. §5.5 / §5.6 / §5.7 simplify to single-file decisions; phase count drops to **3-4 phases** (vs G3's 5+1 polish): Phase 0 hygiene if §5.5 surfaces shared validators (likely none) + Phase 1 impl + Phase 2 invariants/docs/cumulative audit + Phase 3 close-out + Phase 4 publish.
- Sibling discipline scope after G5 publishes: **9 shells** (current 8 + new diff shell).
- The "complete round story through SDK" goal becomes more honest: G5 ships the *query* side (diff). Capture side stays at `kernel.audit` — matches the event-sourcing pattern split. Users follow the same import path as today's `examples/round_story_full_demo.py`.
- §5.2 is now nearly settled by §5.1 (since at least the diff side ships); falsifier remains for source-grounded confirmation that `build_proof_frame_diff` matches the L SDK shape.
- §5.3 (Diff input shape + cross-cutting precedent layer scope) becomes the next critical decision: with recorder deferred, the question reduces to whether raw `RoundEvent` (frozen `kernel.audit` DTO, two tuples of) can cross the SDK boundary as input. F1+F3 of §5.3 already lean toward "yes — extend the G2 precedent to `kernel.audit` for this one frozen DTO"; falsifier will source-ground.
- No SDK shell file for round events; no new shared validator for `RoundRecorder`; no `#P1` retrofit on the recorder side.

### 5.2 Does ProofFrame Diff ship as a SDK shell?

**Question:** Almost certainly **yes** (Round 8 hinted that direction; `build_proof_frame_diff` is a pure function returning a frozen DTO that fits every L precedent). The real sub-question is: do we ship 1 SDK shell (just diff) or 0 shells (defer everything to advanced importable)?

**Conservative default:** ship 1 SDK method `SDKStore.diff_proof_frames(...)`. Falsifier confirms the pattern matches G2 ProofFrame Recheck precedent (frozen-DTO-in, frozen-DTO-out, no derivation/rule lowering).

**Falsifiers required:**
- F1: `build_proof_frame_diff` signature aligns with the L SDK shape (pure function, frozen-DTO output, no `Store` parameter). Verified at `proof_frame_diff.py:160-191`.
- F2: All input DTOs (`RoundEvent`) are frozen application-canonical and have no SDK alternative. Verified at `round_events.py:39`.
- F3: The output DTO `ProofFrameDiff` is frozen and has no SDK wrapper today. Walker view `ProofFrameDiffView` exists but is Tier 2 — does not require SDK to surface.

### 5.3 ProofFrame Diff input shape

**Question:** What does the SDK shell accept?
- **(A)** Raw `tuple[RoundEvent, ...]` × 2 (matching `build_proof_frame_diff` 1:1) — extends G2 precedent to `kernel.audit` layer.
- **(B)** Audit package directory path × 2 — SDK reads events internally via `kernel.audit.reader`; SDK owns IO.
- **(C)** A `(round_id, events)` pair object — slight abstraction over (A).
- **(D)** Hybrid — accept events OR path; auto-dispatch.

**Conservative default:** (A) raw tuples. Direct mirror of A-side function signature; keeps SDK pure (no IO); leaves persistence to `kernel.audit.write_round_events_atomic` and reading to `kernel.audit.reader`.

**Falsifiers required:**
- F1: The G2 §5.1+§5.2 cross-cutting precedent ("raw application protocol DTOs at SDK boundary when frozen application-canonical AND no SDK alternative without inventing new outward surface") was scoped to `kernel.application.protocol`. Does it extend to `kernel.audit`? Source-grounded answer: `RoundEvent` is `@dataclass(frozen=True)` with canonical sorted fields and `__post_init__` validation; it is application-canonical in spirit (the audit module imports `kernel.application.protocol.common.JSONValue` for its payload type). Either accept the extension (raw tuples OK) or carve `kernel.audit` out (would force option B/C/D).
- F2: G3 §5.1+§5.2 said substrate IR is NOT in scope. `kernel.audit` is neither substrate IR nor application protocol — it's a top-level sibling layer. Need a principled call: does "frozen + canonical" generalize, or does "lives under `kernel.application.protocol`" matter?
- F3: Any SDK alternative without inventing surface? Currently no SDK-side alternative. Adding one (option C: pair object) creates new outward surface under `#6`.

### 5.4 ProofFrame Diff return shape

**Question:** Documented passthrough of raw `ProofFrameDiff`? Or wrap with `ProofFrameDiffView` (already in `kernel.application.walker`)?

**Conservative default:** documented passthrough of raw `ProofFrameDiff`. Mirrors G2 ProofFrame Recheck (returns raw `ProofFrameRecheckResult`, walker view available but not auto-applied) and every other L return.

**Falsifiers required:**
- F1: Verify `ProofFrameDiff` is `@dataclass(frozen=True)` with canonical fields and no audit-store / persistence state. Confirmed at `proof_frame_diff.py:123-148`.
- F2: Verify `ProofFrameDiffView` is opt-in (caller imports walker explicitly), not auto-wrapped anywhere. Confirmed at `walker/views.py:376-415`.
- F3: `kernel.sdk.__all__` length must remain 34; `ProofFrameDiff` and supporting DTOs not exported.

### 5.5 Module placement + sub-question on shared validators

**Question:** New shell file(s) under `kernel/sdk/shells/`. Does §5.1 outcome affect the file count?
- If §5.1 = (A) defer recorder: 1 new file `proof_frame_diff.py` → `sdk_diff_proof_frames`.
- If §5.1 = (B) ship recorder: 2-4 new files (`round_events.py` for the 3 lifecycle methods + `proof_frame_diff.py`, OR 4 separate files mirroring G3's three-sibling pattern).
- If §5.1 = (C) hybrid: 2 files.

Also: does G5 need new shared validators?
- If shipping recorder: probably need `validate_round_recorder` (rejects non-`RoundRecorder` for record/finalize calls).
- If just diff: probably not — input is `tuple[RoundEvent, ...]`, validation can be inline.

**Falsifiers required:**
- F1: If §5.1 defers, only 1 file is needed and no new shared validator. Confirmed by precedent (G4 had only 1 method = 1 file).
- F2: Shell file count after G5: 8 (current) + N where N depends on §5.1.

### 5.6 Module file naming

**Question:** Final filename(s).
- §5.1 = (A): `kernel/sdk/shells/proof_frame_diff.py` (verb-first inside the file: `sdk_diff_proof_frames`).
- §5.1 = (B): see §5.5.

**Conservative default:** `proof_frame_diff.py` (matches `kernel.audit.proof_frame_diff` 1:1).

### 5.7 SDKStore method names

**Question:** Final method name (verb-first per L convention).
- Diff: candidates `diff_proof_frames(...)`, `proof_frame_diff(...)` (noun-verb collision with G2 `recheck_proof_frame`), `compare_proof_frames(...)`. Round 8 hint: `diff_proof_frames`.
- If recorder ships: `start_round` / `record_round_event` / `finalize_round` mirror audit-layer 1:1, OR `record_round(round_id, events) -> tuple[RoundEvent, ...]` if §5.1 option D.

**Falsifiers required:**
- F1: Method name uniqueness — no existing `SDKStore` method starts with `diff_*`, `proof_frame_*` (G2 has `recheck_proof_frame`), `start_*`, `record_*`, or `finalize_*`. Verify at `store.py`.
- F2: Verb-first consistency with G1 (`check`, `diagnose`), G4 (`why_not`), G2 (`check_fact_overlay`, `recheck_proof_frame`), G3 (`check_rule_*`).
- F3: Group A (`diff_proof_frames`) vs Group B (`proof_frame_diff`) — Group A reads as action; Group B reads as noun and collides semantically with the DTO name `ProofFrameDiff`. Strong preference for Group A.

### 5.8 Error mapping + Sibling discipline at 9+ shell scope

**Question:** Per-method `$.<method>.<input>` paths + Sibling discipline.
- Diff has fewer error sources than rule-overlay (no derivation lowering, no rule registry, no A helper that raises `CapabilityHelperError`). Likely 4-5 paths: `$.diff_proof_frames.{round_a_id, round_b_id, round_a_events, round_b_events, request, }` + base.
- Sibling at 9-shell scope: G5 shell(s) must not call any of the 8 prior shells. Existing G3 sibling pattern (runtime patch + static source scan) extends naturally; just one extra forbidden-import pattern per G5 module.

**Falsifiers required:**
- F1: Enumerate every exception type from `build_proof_frame_diff`. Source: `proof_frame_diff.py` raises `ProofFrameDiffError(ValueError)` for invalid event payloads (`_proof_frame_record_from_event` at `:209`); `_require_non_empty_str` raises `ValueError` for empty round_ids. Need to verify these are the ONLY raise paths; everything else returns the DTO.
- F2: Confirm `build_proof_frame_diff` is the only entry point — no helper between it and `kernel.audit.round_events` that adds new raise paths.
- F3: `kernel.sdk.__all__` length must remain 34 even with new G5 SDKStore method(s). G3 invariant test pattern extends to G5 invariant.

### 5.9 Tests + invariants

**Question:** Test file structure.
- 1 contract test file per shell module: `test_sdk_proof_frame_diff.py` (and `test_sdk_round_events.py` if §5.1 ships recorder).
- 1 invariant file: `test_sdk_g5_invariants.py` (6-class mirror of G1+G4+G2+G3 invariants).
- Possible `#P1` retrofit: any existing test asserting "no SDK surface for round events / proof_frame_diff"? `grep -rn "no_sdk.*round\|no_sdk.*proof_frame_diff" src/kernel/tests/` to confirm.

**Falsifiers required:**
- F1: Per-method test count expectation — G2 ProofFrame Recheck had 11 tests (similar shape); G5 diff likely 12-14 (one extra for `include_unchanged=True/False` parameterization, one for empty events, one for cross-round-id mismatch handling).
- F2: `#P1` retrofit count — depends on what pre-G5 boundary tests exist.

## 6. Boundaries and Invariants

(Provisional — finalized at scope-freeze. Inherited from G1-G4 + G3 verification-round addendum.)

- `kernel.sdk.__all__` length stays at **34**.
- New shells live under `kernel/sdk/shells/`. No flat-layout reintroduction.
- Sibling discipline at 9+ shell scope (depending on §5.1 / §5.5).
- No SDK shell calls another SDK shell at runtime; verified via runtime patch + static source scan.
- Frontier remains advanced importable per G4 §5.4.
- Sacred branches `master` and `v0.1-oss-prep` untouched throughout.
- G1 + G4 + G2 + G3 published snapshot branches untouched (`d6716a0` / `acb5a6e` / `d658390` / `cb6d3bd`). G5 publishes new G5-only ref + new Path B combined ref, leaves prior 4 immutable.
- Shared `resolve_runtime_registry` boundary normalizer is available; G5 uses it if and only if a G5 shell resolves a dependency registry (likely not needed).
- §5.1+§5.2 cross-cutting precedent layer scope decided in §5.3 falsifier (extend to `kernel.audit` or carve out).

## 7. Acceptance Criteria

Draft-stage acceptance:

- [x] Blueprint draft seeded under `docs/blueprints/active/` with §1-§4 source-grounded against HEAD `112401a`.
- [x] §5 enumerates 9 questions; no falsifier locks yet.
- [x] §6-§9 placeholders.
- [x] Audit log seeded with "Draft seeded" entry.

Scoped-stage acceptance (filled after §5 falsifier passes):

- [ ] §5.1 locked — Round events SDK shape (defer / ship recorder / hybrid).
- [ ] §5.2 locked — ProofFrame Diff SDK shipped.
- [ ] §5.3 locked — Diff input shape + cross-cutting precedent extension/carve.
- [ ] §5.4 locked — Diff return shape (passthrough).
- [ ] §5.5 locked — Module placement + shared-validator decision.
- [ ] §5.6 locked — Module file naming.
- [ ] §5.7 locked — SDKStore method names.
- [ ] §5.8 locked — Error mapping + Sibling discipline at G5-final scope.
- [ ] §5.9 locked — Tests + invariants + `#P1` retrofit count.
- [ ] §8 implementation plan filled with N phases (N depends on §5.1).
- [ ] Status moves from `draft` to `scoped`.

Implementation-stage acceptance (per phase, gated by phase-end audit):

- [ ] Phase 0 — shared-validator additions (if §5.5 adds any) + any pre-G5 boundary-test retrofits.
- [ ] Phase 1+ — one phase per new SDK shell file.
- [ ] Phase N-2 — G5 invariants + docs CN/EN + cumulative audit.
- [ ] Phase N-1 — close-out + archive.
- [ ] Phase N — publish G5-only + Path B combined snapshots.

## 8. Implementation Plan

(Filled at scope-freeze.)

## 9. Outcome / Deviations

To be filled at close-out.
