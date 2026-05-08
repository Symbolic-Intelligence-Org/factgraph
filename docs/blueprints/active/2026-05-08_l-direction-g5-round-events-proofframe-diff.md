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

**Decision (2026-05-08):** Lock **ship 1 SDK shell — `SDKStore.diff_proof_frames(...) -> ProofFrameDiff`**. This was structurally implied by §5.1 (defer recorder, ship only diff); the falsifier here is structural confirmation.

**Falsifier outcomes (3/3 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `build_proof_frame_diff` matches L SDK shape | Pure function (no `Store` parameter), frozen-DTO output, deterministic. Signature `(*, round_a_id, round_b_id, round_a_events, round_b_events, warnings=(), include_unchanged=False) -> ProofFrameDiff` at `src/kernel/audit/proof_frame_diff.py:160-191`. Same shape as G2 ProofFrame Recheck (frozen-DTO-in, frozen-DTO-out, no derivation/rule lowering). | PASS. |
| F2 | All input DTOs are frozen application-canonical with no SDK alternative | `RoundEvent` confirmed frozen + canonical at §5.3 (`round_events.py:38-61`). No SDK alternative. Covered by §5.3 layer rule. | PASS. |
| F3 | Output `ProofFrameDiff` is frozen with no SDK wrapper | `@dataclass(frozen=True)` at `proof_frame_diff.py:123-148`. Walker view `ProofFrameDiffView` exists at `kernel.application.walker.views.py:376-415` but is Tier 2 advanced-importable — see §5.4 lock. | PASS. |

### 5.3 ProofFrame Diff input shape

**Question:** What does the SDK shell accept?
- **(A)** Raw `tuple[RoundEvent, ...]` × 2 (matching `build_proof_frame_diff` 1:1) — extends G2 precedent to `kernel.audit` layer.
- **(B)** Audit package directory path × 2 — SDK reads events internally via `kernel.audit.reader`; SDK owns IO.
- **(C)** A `(round_id, events)` pair object — slight abstraction over (A).
- **(D)** Hybrid — accept events OR path; auto-dispatch.

**Conservative default:** (A) raw tuples. Direct mirror of A-side function signature; keeps SDK pure (no IO); leaves persistence to `kernel.audit.write_round_events_atomic` and reading to `kernel.audit.reader`.

**Decision (2026-05-08):** Lock **option (A) — raw `tuple[RoundEvent, ...]` × 2 at the SDK boundary**, mirroring `kernel.audit.proof_frame_diff.build_proof_frame_diff(...)` 1:1. SDK shell signature shape (final method name pending §5.7):

```python
SDKStore.diff_proof_frames(
    round_a_id: str,
    round_b_id: str,
    round_a_events: tuple[RoundEvent, ...],
    round_b_events: tuple[RoundEvent, ...],
    *,
    warnings: tuple[WarningDTO, ...] = (),
    include_unchanged: bool = False,
) -> ProofFrameDiff
```

The SDK shell does no IO; users load events through `kernel.audit.load_audit_package` (or hold them from a fresh recorder), then pass the tuples in — same pattern as G2 ProofFrame Recheck which takes already-captured `SupportArtifact`.

**Cross-cutting precedent layer clarification (key explicit rule):**

The G2 §5.1+§5.2 precedent (raw frozen DTOs OK at SDK boundary) was originally scoped to `kernel.application.protocol`. G3 §5.2 then carved substrate IR (`RuleSpec` at `kernel.core.rules.rule_ir`) OUT. With G5 §5.3, the layer line is now stated explicitly:

> **The boundary is NOT "only `kernel.application.protocol`". It is "frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary".** `RoundEvent` and the supporting `kernel.audit` frozen DTOs (`ProofFrameDiff`, `FrameDelta`, `AtomDelta`, `FrameIdentity`, `FrameStatusChange`, `EventReference`) all qualify. `kernel.core.rules.rule_ir.RuleSpec` is excluded by the "above `kernel.core`" criterion (substrate IR), which preserves the G3 carve-out.

This rule will appear in §6 invariants verbatim once scope-freezes.

**Falsifier outcomes (3/3 PASS for option A):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Cross-cutting precedent extension to `kernel.audit` | `RoundEvent` at `src/kernel/audit/round_events.py:38-61` is `@dataclass(frozen=True)` with 6 canonical sorted fields and full `__post_init__` validation — same structural shape as `EvaluationOverlay` / `SupportArtifact` / `RuleLiteralPath` / `RuleAddedAtom` which already cross the SDK boundary per G2/G3. Imports `JSONValue` + `WarningDTO` from `kernel.application.protocol.common` (`round_events.py:11`) — uses protocol vocabulary directly. Same applies to `ProofFrameDiff` and supporting DTOs at `kernel.audit.proof_frame_diff` (also frozen, also import protocol vocabulary at `proof_frame_diff.py:7-8`). | PASS — extends the G2 precedent cleanly under the layer clarification. |
| F2 | Layer position of `kernel.audit` and principled rule | Import-DAG inspection: `kernel.core.*` (substrate IR) sits at the bottom; `kernel.application.protocol` sits above core; `kernel.audit` imports protocol (`proof_frame_diff.py:7-8`) AND core (`audit/query.py:6-19`); `kernel.application.capability_helpers` and `kernel.application.walker` import `kernel.audit` (`capability_helpers/round_events.py:21`, `walker/views.py:34`); `kernel.sdk` sits at the top. So `kernel.audit` is sibling-DTO above protocol vocabulary, NOT substrate IR. The principled rule "frozen canonical DTO above `kernel.core` using protocol vocabulary" cleanly captures G2 + G3 + G5: G3's `RuleSpec` exclusion is preserved (substrate IR = below the line); `EvaluationOverlay` / `SupportArtifact` / `RuleLiteralPath` / `RuleAddedAtom` (G2/G3) and `RoundEvent` / `ProofFrameDiff` (G5) all clear the line. | PASS — no carve-out warranted; rule generalizes. |
| F3 | Any SDK alternative without inventing outward surface | SDK input-pattern audit verified by grepping `def ...(self, ...)` in `src/kernel/sdk/store.py`: all 8 existing L methods take Python objects (frozen DTOs / SDK DSL objects / mappings); zero take a filesystem path as a method-level input. Path arguments appear only at constructor level (`from_schema_classes(..., ledger_path=None)` at `store.py`). Option (B) "SDK takes audit-package paths" would create a new method-level SDK input pattern under `#6` (no outward compat without consumer signal); plus it forces SDK to own file IO, depend on `kernel.audit.reader`, handle missing-file errors, and duplicate the loader's responsibility. Option (C) "SDK pair object `(round_id, events)`" would invent a new outward DTO type under `#6` without consumer signal. | PASS — options B/C add new outward surface; option A reuses the L pattern. |

**Forward implications:**

- §5.4 (return shape) is now nearly trivial — `ProofFrameDiff` is also a `kernel.audit` frozen DTO covered by the same precedent extension. Documented passthrough confirmed; not in `kernel.sdk.__all__`.
- §5.5 (module placement + shared-validator decision) — only one G5 shell consuming `RoundEvent` tuples; inline-validate at the boundary; no new shared validator needed.
- §5.6 (file naming) — single shell file `kernel/sdk/shells/proof_frame_diff.py`.
- §5.7 (SDKStore method name) — `diff_proof_frames` (Group A from the §5.7 sub-question; verb-first, action-shape, no semantic collision with the DTO `ProofFrameDiff`).
- §5.8 (error mapping) input paths land as: `$.diff_proof_frames.{round_a_id, round_b_id, round_a_events, round_b_events, warnings, request,}` + base. `ProofFrameDiffError` (a `ValueError` subclass at `proof_frame_diff.py:22`) remaps to `$.diff_proof_frames.request`; `ValueError` from `_require_non_empty_str` remaps to the corresponding `.<id>` path.
- §6 invariants will encode the layer clarification verbatim so future SDK shells over audit / protocol DTOs inherit the rule without re-deriving it.

### 5.4 ProofFrame Diff return shape

**Question:** Documented passthrough of raw `ProofFrameDiff`? Or wrap with `ProofFrameDiffView` (already in `kernel.application.walker`)?

**Conservative default:** documented passthrough of raw `ProofFrameDiff`. Mirrors G2 ProofFrame Recheck (returns raw `ProofFrameRecheckResult`, walker view available but not auto-applied) and every other L return.

**Decision (2026-05-08):** Lock **documented passthrough of raw `ProofFrameDiff`**. No SDK wrapper. Walker view `kernel.application.walker.ProofFrameDiffView` stays advanced importable, opt-in for callers who want ergonomic traversal — exactly mirrors G2's relationship between `recheck_proof_frame` and `ProofFrameView`.

**Falsifier outcomes (3/3 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `ProofFrameDiff` is frozen + canonical with no audit-store / persistence state | `@dataclass(frozen=True)` at `proof_frame_diff.py:123-148` with 4 fields (`round_a_id: str`, `round_b_id: str`, `frame_deltas: tuple[FrameDelta, ...]`, `warnings: tuple[WarningDTO, ...]`) + `__post_init__` validation. No mutable state, no IO, no store reference. | PASS — qualifies for raw passthrough under the §5.3 layer rule. |
| F2 | `ProofFrameDiffView` is opt-in, not auto-wrapped anywhere | `grep` for `ProofFrameDiffView(` shows usage only in (a) `kernel/tests/test_walker_invariants.py:122`, (b) `kernel/tests/test_walker_views_proof_frame_diff.py` (multiple), and (c) `kernel/application/walker/views.py:376` (the definition site). **Zero call sites in `kernel.sdk` or `kernel.application` runtime code.** Users import explicitly via `from kernel.application.walker import ProofFrameDiffView`. Same opt-in pattern as G2's relationship to `ProofFrameView` over `ProofFrameRecheckResult`. | PASS — walker view stays opt-in; SDK shell does not auto-wrap. |
| F3 | `kernel.sdk.__all__` length stays 34 | Verified at HEAD `75f2826`: `len(kernel.sdk.__all__) == 34`. `ProofFrameDiff` and supporting DTOs (`FrameDelta`, `AtomDelta`, `FrameIdentity`, `FrameStatusChange`, `EventReference`) NOT exported. | PASS — boundary unchanged. |

**Forward implications (§5.2 + §5.4 combined):**

- Final SDK signature shape now fully bounded by §5.1 + §5.2 + §5.3 + §5.4:

  ```python
  SDKStore.diff_proof_frames(
      round_a_id: str,
      round_b_id: str,
      round_a_events: tuple[RoundEvent, ...],
      round_b_events: tuple[RoundEvent, ...],
      *,
      warnings: tuple[WarningDTO, ...] = (),
      include_unchanged: bool = False,
  ) -> ProofFrameDiff   # raw passthrough; not in kernel.sdk.__all__
  ```
- §5.5 (module placement + shared-validator) becomes mechanical — single shell file, inline validation.
- §5.6 (file naming) → `kernel/sdk/shells/proof_frame_diff.py`.
- §5.7 (method name) → `SDKStore.diff_proof_frames` (Group A).
- §5.8 + §5.9 remain as the final substantive batch (error paths + tests/invariants/`#P1` retrofit count).

### 5.5 Module placement + sub-question on shared validators

**Question:** New shell file(s) under `kernel/sdk/shells/`. Does §5.1 outcome affect the file count?
- If §5.1 = (A) defer recorder: 1 new file `proof_frame_diff.py` → `sdk_diff_proof_frames`.
- If §5.1 = (B) ship recorder: 2-4 new files.
- If §5.1 = (C) hybrid: 2 files.

Also: does G5 need new shared validators?

**Decision (2026-05-08):** Lock **single shell file under `kernel/sdk/shells/` + inline validation (no new shared validator)**. Total `kernel/sdk/shells/` module count after G5 publishes: **9** (current 8 + new `proof_frame_diff.py`). The G3 verification-round shared `resolve_runtime_registry` boundary normalizer remains at 1; G5 adds 0.

**Falsifier outcomes (2/2 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Single-file pattern with §5.1 deferred | G4 precedent: only `why_not.py` shipped under `shells/` for the single-method `SDKStore.why_not(...)`. With §5.1 deferring recorder, G5 has the same single-method shape. | PASS — single file is the L precedent for single-method shells. |
| F2 | No 2nd consumer of `RoundEvent` / `kernel.audit` DTOs in shells | `grep -rn "RoundEvent\|kernel\.audit" src/kernel/sdk/shells/` returned zero hits. Inline `isinstance(events, tuple)` + per-element `isinstance(e, RoundEvent)` + `_require_non_empty_str` for ids in the new shell is sufficient; extraction to `_validation.py` only fires if a 2nd shell needs it (per the validator-extraction trigger established at G3 Phase 0). | PASS — extraction trigger does not fire; inline validation. |

### 5.6 Module file naming

**Question:** Final filename.

**Decision (2026-05-08):** Lock **`kernel/sdk/shells/proof_frame_diff.py`** with module function `sdk_diff_proof_frames(...)`.

**Falsifier outcomes (2/2 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | File-name collision check | `ls src/kernel/sdk/shells/` returns 8 files (`__init__.py`, `_validation.py`, `check.py`, `diagnose.py`, `fact_overlay.py`, `proof_frame.py`, `rule_add_condition.py`, `rule_disable.py`, `rule_literal_replace.py`, `why_not.py`). `proof_frame_diff.py` does NOT exist. Adding it keeps clear separation from G2's `proof_frame.py` (which holds `sdk_proof_frame_recheck` — the *recheck* shell). | PASS — collision-free. |
| F2 | Naming mirrors A-side module | `kernel.audit.proof_frame_diff` is the A-side module hosting `build_proof_frame_diff(...)`. SDK shell `kernel.sdk.shells.proof_frame_diff` mirrors 1:1, matching the G1+G4+G2+G3 pattern (each shell file shares its A-side module name when one exists). | PASS — naming mirrors A. |

### 5.7 SDKStore method names

**Question:** Final method name (verb-first per L convention). Group A (`diff_proof_frames`) vs Group B (`proof_frame_diff`).

**Decision (2026-05-08):** Lock **`SDKStore.diff_proof_frames(...)`** (Group A — verb-first action shape; no semantic collision with the DTO name `ProofFrameDiff`).

**Falsifier outcomes (3/3 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Method-name collision check | `grep -E "^    def (diff_\|proof_frame_)" src/kernel/sdk/store.py` returns zero hits. No existing `SDKStore` method starts with `diff_*` or `proof_frame_*` (G2's `recheck_proof_frame` starts with `recheck_*`). | PASS — collision-free. |
| F2 | Verb-first consistency | All L-Direction methods are verb-first: G1 (`check`, `diagnose`), G4 (`why_not`), G2 (`check_fact_overlay`, `recheck_proof_frame`), G3 (`check_rule_disable`, `check_rule_literal_replace`, `check_rule_add_condition`). `diff_proof_frames` follows the same shape (verb + object). | PASS — consistent. |
| F3 | Group A vs Group B | Group A `diff_proof_frames` reads as action ("diff these proof frames"); Group B `proof_frame_diff` reads as noun and would semantically collide with the DTO name `ProofFrameDiff` (i.e., the method would be named the same as what it returns, which is the G3 §5.7 anti-pattern that rejected `disable_rule` because it collided with persistent-write `add` family). Group A is also the Round 8 hint at `30_recommendation.md:610`. | PASS — Group A clearly preferable. |

**Forward implications (§5.5 + §5.6 + §5.7 combined):**

- After G5 publishes: `kernel/sdk/shells/` has **9 modules** (8 + `proof_frame_diff.py`); `SDKStore` has **40 methods** (39 + `diff_proof_frames`); `kernel.sdk.__all__` length stays at **34**.
- Sibling discipline scope after G5 = **9 shells** (each existing shell tests against all 8 sister shells; new shell tests against all 8 prior).
- The shell function name is `sdk_diff_proof_frames(sdk, round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False) -> ProofFrameDiff`.
- §5.8 (error mapping) and §5.9 (tests + invariants) are the only remaining substantive locks before scope-freeze.

### 5.8 Error mapping + Sibling discipline at 9-shell scope

**Question:** Per-method `$.<method>.<input>` paths + Sibling discipline.

**Decision (2026-05-08):** Lock **7-path remap** (5 input paths + 1 request path + 1 base path) with `ProofFrameDiffError` covering the `.request` boundary; inline pre-validation for input paths; defensive `Exception` for the base path. Sibling discipline at 9-shell scope tests the new G5 shell against all 8 prior shells.

**7-path remap (locked execution order in `sdk_diff_proof_frames`):**

| # | SDK boundary check | Path | Source / Outcome |
|---|---|---|---|
| 1 | `isinstance(round_a_id, str) and round_a_id` | `$.diff_proof_frames.round_a_id` | inline validation; raises `SDKStoreError("round_a_id must be non-empty str", path=...)` |
| 2 | `isinstance(round_b_id, str) and round_b_id` | `$.diff_proof_frames.round_b_id` | inline validation; raises `SDKStoreError("round_b_id must be non-empty str", path=...)` |
| 3 | `isinstance(events, tuple) and all(isinstance(e, RoundEvent))` for round_a_events | `$.diff_proof_frames.round_a_events` | inline validation; raises `SDKStoreError("round_a_events must be tuple[RoundEvent, ...]", path=...)` — protects against `TypeError` / `AttributeError` leaks from `sorted(events, key=...)` and `event.kind`/`event.sequence` access in `_proof_frame_records` |
| 4 | Same for round_b_events | `$.diff_proof_frames.round_b_events` | inline validation; same shape |
| 5 | `isinstance(warnings, tuple) and all(isinstance(w, WarningDTO))` | `$.diff_proof_frames.warnings` | inline validation; same shape |
| 6 | `try: build_proof_frame_diff(...)` | `$.diff_proof_frames.request` | catches `ProofFrameDiffError` (covers helper-internal validation in `_require_non_empty_str` / `_require_mapping` / `_validate_binding_json` / `_validate_proof_frame_status` / `_validate_literal` / `_validate_tuple_items` for payload parse errors at `_proof_frame_record_from_event`; covers frame-identity duplicate check at `_proof_frame_records:201`; covers `ProofFrameDiff.__post_init__` `_validate_tuple_items(frame_deltas)` and `_validate_tuple_items(warnings)`); raises `SDKStoreError(..., path=...) from exc` with `__cause__` chain |
| 7 | `try:` (defensive) | base `$.diff_proof_frames` | catches forward-compat `Exception`; raises `SDKStoreError(..., path=...) from exc` |

**No `ProtocolShapeError` path needed** — `build_proof_frame_diff` returns the result directly without an intermediate request DTO. **No `.dependencies` path** — no derivation lowering, no rule registry, no A helper that resolves dependencies. **No `CapabilityHelperError` path** — diff is a pure function in `kernel.audit`, not a `kernel.application.capability_helpers` builder.

**Falsifier outcomes (3/3 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Every internal-helper exception from `build_proof_frame_diff` | All 6 helpers (`_require_non_empty_str` / `_require_mapping` / `_validate_binding_json` / `_validate_proof_frame_status` / `_validate_literal` / `_validate_tuple_items`) raise `ProofFrameDiffError` (a `ValueError` subclass at `proof_frame_diff.py:22`). `_proof_frame_records` raises `ProofFrameDiffError("duplicate proof_frame_result frame identity ...")` at `:201`. `ProofFrameDiff.__post_init__` raises `ProofFrameDiffError` via `_validate_tuple_items` for both `frame_deltas` and `warnings`. **All internal raises are `ProofFrameDiffError`**; single catch covers the boundary. | PASS — `.request` path catches one type cleanly. |
| F2 | Hidden non-`ProofFrameDiffError` raise paths | `_proof_frame_records` calls `sorted(events, key=lambda item: item.sequence)` — if `events` isn't iterable, raises `TypeError`; if items lack `.sequence` / `.kind`, raises `AttributeError`. **These are exactly why SDK pre-validation must verify `tuple[RoundEvent, ...]` BEFORE calling `build_proof_frame_diff`.** Inline pre-validation at boundary check #3 / #4 prevents these from leaking as base-path errors. | PASS — pre-validation at SDK boundary closes the gap. |
| F3 | `kernel.sdk.__all__` length stays 34 | Verified at HEAD `150d740`: `len(kernel.sdk.__all__) == 34`. G5 invariant will assert this; new SDKStore method does not add any export. | PASS — boundary unchanged. |

**Sibling discipline at 9-shell scope (forward-only convention):**

The new G5 shell tests against all **8 prior** sister shells (G1 `sdk_check` + `sdk_diagnose`, G4 `sdk_why_not`, G2 `sdk_fact_overlay_check` + `sdk_proof_frame_recheck`, G3 `sdk_rule_disable` + `sdk_rule_literal_replace` + `sdk_rule_add_condition`). The 8 prior shells' contract tests **are NOT retrofit** to add a new `sdk_diff_proof_frames` patch — same forward-only convention G3 used (each new shell tests against all prior; prior shells' Sibling tests stay frozen at their publication moment). This avoids post-hoc churn in already-published groups (G1 @ `d6716a0`, G4 @ `acb5a6e`, G2 @ `d658390`, G3 @ `cb6d3bd`) and keeps Path B immutable.

Test pattern in `test_sdk_proof_frame_diff.py`:
- `test_sibling_diff_proof_frames_does_not_call_other_sdk_shells_at_runtime` — runtime-patches all 8 sister `sdk_*` functions, calls `sdk.diff_proof_frames(...)`, asserts each `mock.assert_not_called()`.
- `test_sibling_diff_proof_frames_module_does_not_import_sibling_sdk_shells` — static source scan with 16 forbidden patterns (8 sister shells × 2 patterns each: `from kernel.sdk.shells.<name>` + `sdk_<name>(`).

### 5.9 Tests + invariants

**Question:** Test file structure + `#P1` retrofit count.

**Decision (2026-05-08):** Lock **1 contract test file (~13 tests) + 1 invariant file (6-class mirror)**. **Zero `#P1` retrofits**. Phase-end test count target: ~1681 OK / 1 skipped (was 1661 at G3 published HEAD `cb6d3bd` + topic `112401a`; +~20 new G5 tests).

**Locked test plan:**

| File | Coverage |
|---|---|
| `src/kernel/tests/test_sdk_proof_frame_diff.py` | ~13 contract tests: (1) happy path with seeded events; (2) non-str / empty round_a_id rejected at `$.diff_proof_frames.round_a_id`; (3) non-str / empty round_b_id rejected at `$.diff_proof_frames.round_b_id`; (4) non-tuple round_a_events rejected at `$.diff_proof_frames.round_a_events`; (5) non-`RoundEvent` element rejected at same path; (6) non-tuple round_b_events rejected; (7) non-`RoundEvent` element rejected; (8) non-tuple warnings rejected at `$.diff_proof_frames.warnings`; (9) non-`WarningDTO` element rejected at same path; (10) `ProofFrameDiffError` from malformed payload remaps to `$.diff_proof_frames.request` with `__cause__`; (11) defensive `Exception` from runtime remaps to base `$.diff_proof_frames` with `__cause__`; (12) result + supporting DTOs not in `kernel.sdk.__all__`; (13) Sibling discipline runtime patch (8 sister `sdk_*` patches + `assert_not_called`) + static source scan (16 forbidden patterns). May split (13) into two methods if cleaner. |
| `src/kernel/tests/test_sdk_g5_invariants.py` | 6-class mirror of G1+G4+G2+G3 invariants: (1) `test_sdk_all_unchanged_and_g5_result_types_not_exported` — `__all__` length 34, no `ProofFrameDiff` / `FrameDelta` / `AtomDelta` / `FrameIdentity` / `FrameStatusChange` / `EventReference` / `RoundEvent` / `RoundSummary` / `diff_proof_frames` / `sdk_diff_proof_frames` exported; (2) `test_g5_method_is_instance_method_and_no_scenario_method_shipped` — `SDKStore.diff_proof_frames` callable; reserved scenario names (`proof_frame_diff`, `compare_proof_frames`) absent; (3) `test_g5_module_lives_in_shells_subpackage` — `kernel/sdk/shells/proof_frame_diff.py` exists; flat path absent; (4) `test_g5_module_does_not_import_internal_or_walker_layers` — `FORBIDDEN_PRODUCTION_IMPORT_TEXT` set as G1+G4+G2+G3 (capability_helpers private `_binding`, `_reject_sdk_origin`, walker, frontier; **note: `kernel.audit.proof_frame_diff` IS allowed** as the explicit A-side dependency, distinct from the broader `kernel.audit` private internals); (5) `test_store_method_remains_thin_delegate` — pattern-based assertion (delegate-only; no `RoundEvent(` / `ProofFrameDiff(` / `build_proof_frame_diff(` / inline-validate calls in delegate source); (6) `test_store_method_docstring_records_boundary_contract` — docstring includes `Rule Round events / RoundEvent`, `ProofFrameDiff`, `SDKStoreError`, all 7 path strings. |

**Falsifier outcomes (2/2 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Pre-G5 "no SDK surface" boundary test scan | `grep -rn "no_sdk\|test_no_sdk" src/kernel/tests/test_audit_proof_frame_diff.py test_audit_round_events.py test_capability_helpers_round_events.py` returned zero hits. `grep "kernel\.sdk"` in those files — zero hits. The audit-layer tests never made the "no SDK surface" assertion that G3's rule-overlay application-runtime tests did. | PASS — zero `#P1` retrofits required for G5. |
| F2 | Test count expectation | G2 ProofFrame Recheck has 11 tests with similar shape (frozen-DTO-in, frozen-DTO-out, no derivation lowering); G5 has 5 input boundaries (vs G2's 2: `support_artifact` + `overlay`) so naturally more rejection tests. Estimate ~13 contract tests covers all 7 paths + DTO non-export + Sibling. | PASS — bounded expectation. |

**Forward implications (§5.8 + §5.9 combined):**

- G5 implementation surface is fully bounded. Ready for scope-freeze.
- Phase 1 implementation work is purely additive: 1 new shell file, 1 new SDKStore method (thin delegate), 1 contract test file, 1 invariant file. No refactor, no shared validator extraction, no `#P1` retrofits.
- Phase 2 scope is fixed: 6-class invariant mirror + SDK API docs CN/EN + application overview docs CN/EN updates + cumulative audit gate.
- Phase 3 (close-out + archive + publish) follows the G3 close-out template exactly.

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
