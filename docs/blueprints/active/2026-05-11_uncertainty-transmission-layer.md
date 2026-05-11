# Task Blueprint: Uncertainty Transmission Layer

- Status: scoped
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/core`
  - `src/kernel/adapters/problog`
  - `src/kernel/adapters/pyreason`
  - `src/kernel/sdk`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [src/kernel/core/docs/01_architecture.en.md](../../../src/kernel/core/docs/01_architecture.en.md)
  - [src/kernel/adapters/docs/02_problog_adapter.md](../../../src/kernel/adapters/docs/02_problog_adapter.md)
  - [src/kernel/adapters/docs/03_pyreason_adapter.md](../../../src/kernel/adapters/docs/03_pyreason_adapter.md)
- Audit Log:
  - [2026-05-11_uncertainty-transmission-layer.audit.md](./2026-05-11_uncertainty-transmission-layer.audit.md)

## 1. Problem

FactPy currently carries uncertainty through several adapter-specific and compatibility lanes:

- ProbLog fact-level probability annotations.
- PyReason lower/upper bound annotations.
- shared probability annotations from write metadata.
- compatibility confidence values on meta rows and candidates.

These lanes are useful, but the system does not yet expose a single raw uncertainty contract that distinguishes probabilistic semantics from possibilistic / certainty-compatible semantics before engine projection. This creates a risk that the same numeric interval or scalar can be interpreted differently by different engines without an explicit policy boundary.

The target issue is "formal unification is not semantic unification." A shared numeric shape such as `[0.35, 0.70]` is useful only if the system also preserves what kind of uncertainty it represents and which projection policy, if any, is allowed to reinterpret it for an engine.

## 2. Goals

- Define a minimal raw uncertainty contract with `raw_kind`, `bound`, and provenance.
- Solve semantic-boundary preservation, not universal uncertainty normalization.
- Replace user-facing engine-specific uncertainty meta with project-level `raw_kind` / `bound` annotations.
- Phase 1: land only the data contract for `raw_kind` / `bound` as writeable assertion meta plus canonical shared annotations.
- Later phase: define `SemanticsProfile` as the runtime carrier for engine-specific parameters, transmission policy, and temporal projection.
- Preserve one source of raw uncertainty; do not persist runtime projection outputs as canonical facts.
- Define where transmission / projection policy lives for ProbLog and PyReason.
- Make ProbLog projection conservative by default: reject non-probabilistic inputs unless a policy explicitly allows conversion.
- Clarify that PyReason bounds, ProbLog probability, and candidate `confidence` are different semantic surfaces.
- Update module docs after implementation so current truth does not remain only in the reference note or blueprint.

## 3. Non-goals

- No full possibility theory implementation.
- No calibrated projection model implementation in the first scope unless a real calibration artifact is provided.
- No wholesale adoption of any external report's taxonomy or transformation rules.
- No attempt to make probabilistic, possibilistic, certainty, and hard-constraint semantics identical under one algebra.
- No SMT adapter implementation in this task.
- No compatibility migration for historical uncertainty meta; the project is not online yet, so this blueprint may choose the clean contract directly.
- No new user-facing writes through `probability`, `bound_lower`, or `bound_upper`.
- No change to ProbLog or PyReason external engine semantics.
- No public API expansion beyond the Phase 1 data contract before runtime projection behavior is scoped.
- No code changes until this blueprint section is reviewed and moved from draft to scoped.

## 4. Current Context

- Current implementation entry points:
  - `src/kernel/adapters/problog/problog_export.py`
  - `src/kernel/adapters/pyreason/session.py`
  - `src/kernel/core/evidence/write_protocol.py`
  - `src/kernel/core/store/ledger.py`
  - `src/kernel/core/derivation/candidates.py`
- Current docs:
  - `src/kernel/core/docs/01_architecture.en.md`
  - `src/kernel/adapters/docs/02_problog_adapter.md`
  - `src/kernel/adapters/docs/03_pyreason_adapter.md`
  - `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
  - `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- Current known constraints:
  - `AnnotationRow` is the canonical assertion-level annotation carrier.
  - `AnnotationRow.kind` already supports `json`, so `bound` can remain one atomic annotation value instead of being split into lower/upper engine fields.
  - `meta_rows` are a legacy compatibility layer; canonical semantic consumers should read the Annotation Store.
  - ProbLog export currently falls back from engine-native probability to shared probability to `meta.confidence`.
  - PyReason session writes `pyreason/semantic/bound_lower` and `bound_upper`, then derives shared compatibility confidence from the lower bound.
  - SDK / write protocol already carry business valid-time metadata as `valid_from` / `valid_to`.
  - PyReason adapter-local write/session APIs carry engine timesteps as `active_from` / `active_to`.
  - `CandidateSet.confidence_kind` is output-oriented and currently limited to `none|probability|certainty`.
- Related historical / active material:
  - Active ProbLog and PyReason provenance / explainability blueprints.
  - Core annotation certainty docs mark probability explainability and engine parity as deferred.

## 5. Proposed Shape

Introduce an explicit raw uncertainty layer as assertion annotations or a closely related typed carrier, shaped around the current project rather than an imported taxonomy:

```text
raw_kind = probabilistic | possibilistic
bound = [lower, upper]  # one logical field; likely stored as AnnotationRow(kind="json")
provenance = source / method / calibration reference / derivation metadata
valid_from / valid_to = optional business valid-time interval
```

Project-specific adjustments:

- Use the existing Annotation Store as the likely persistence substrate instead of introducing a new uncertainty database.
- Phase 1 should dual-write raw uncertainty:
  - `meta_rows` mirrors `raw_kind` and `bound` for `AssertionRecordSet.where(meta=...)`, assertion review, and selection ergonomics;
  - Annotation Store keeps the canonical semantic copy for engine projection and audit semantics.
- Store canonical raw uncertainty as annotations:
  - `shared/semantic/raw_kind` with `kind="str"` and value `probabilistic` or `possibilistic`;
  - `shared/semantic/bound` with `kind="json"` and value `[lower, upper]`.
- SDK write APIs may accept these through `meta` or a future typed argument for ergonomics, but persistence should project them into the Annotation Store.
- Treat `confidence` and `confidence_kind` as candidate-output / compatibility summaries, not as the canonical raw uncertainty carrier.
- Treat `raw_kind` / `bound` as the data-layer replacement for `probability`, `bound_lower`, and `bound_upper`.
- Because the project is not online, new uncertainty authoring should use `raw_kind` / `bound` directly rather than preserving parallel public write paths.
- Engine-native lanes may still exist internally as adapter projection outputs, but they should not be the user-facing data contract.
- Add transmission as an adapter-side interpretation layer, not a cross-engine promise that one score means the same thing everywhere.
- Require policy names to reveal semantic loss when a projection is heuristic, for example `probability_as_certainty` or `possibility_to_probability:midpoint`.

### 5.0 Scope-Freeze Decisions

The first implementation slice is scoped to Track 1, the uncertainty transmission data contract. Track 2 from `rule-policy-function-tree-and-syntax.zh.md` remains design input for a separate blueprint.

Locked decisions:

- **D1 — Legacy uncertainty write keys**: `probability`, `bound_lower`, and `bound_upper` are hard-rejected as user-authored raw uncertainty meta in this Phase 1 contract. They may remain internal adapter projection / output lanes until a later adapter migration replaces them.
- **D2 — `confidence`**: user-authored `confidence` remains supported as the existing compatibility / summary lane. Phase 1 does not rename or remove it. The broader `confidence` terminology cleanup belongs to Track 2 or a later blueprint.
- **D3 — Validation placement**: validation for `raw_kind`, `bound`, and the legacy-key rejection belongs in `src/kernel/core/evidence/write_protocol.py`, at meta normalization / preflight time, before ledger mutation or retract side effects.
- **D4 — Selection semantics**: `AssertionRecordSet.where(meta={"bound": [...]})` uses exact JSON-value matching against the mirrored `meta_rows` value. Phase 1 does not introduce interval containment, overlap, tolerance, or uncertainty-aware query semantics.
- **D5 — Sequencing**: Track 1 ships first. Track 2 namespace / DSL / policy-layer work stays in the working design note until a separate blueprint scopes it.

### 5.1 Phase 1 Data Contract Scope

This first implementation slice should stay deliberately small:

- Add `raw_kind` as a recognized user-writeable meta key:
  - kind: `str`
  - allowed values: `probabilistic`, `possibilistic`
  - persisted to `meta_rows`
  - projected to `shared/semantic/raw_kind`
- Add `bound` as a recognized user-writeable meta key:
  - kind: `json`
  - allowed value: a two-element JSON list `[lower, upper]`
  - validation: numeric `int` or `float` elements are accepted; bools and numeric strings are rejected; `0.0 <= lower <= upper <= 1.0`
  - normalization: persisted value is a two-element float list, for example `[0.0, 1.0]`
  - persisted to `meta_rows`
  - projected to `shared/semantic/bound`
- Require `raw_kind` and `bound` to be written together. A write with exactly one of the two keys is invalid.
- Stop treating `probability`, `bound_lower`, and `bound_upper` as accepted user-facing raw uncertainty inputs in this Phase 1 contract; user writes containing these keys fail validation instead of being silently treated as custom metadata.
- Keep `confidence` as candidate-output / compatibility summary, not raw uncertainty truth.
- Do not change ProbLog export, PyReason materialization, or candidate confidence in Phase 1.
- Add tests only for write validation, `meta_rows`, annotation projection, assertion filtering, and unchanged behavior fences for existing adapter/runtime paths.

Storage contract after Phase 1:

```text
meta_rows:
  raw_kind = probabilistic | possibilistic
  bound = [lower, upper]

annotation_rows:
  shared/semantic/raw_kind
  shared/semantic/bound
```

Projection policy should be runtime-owned by a `SemanticsProfile` or a small adapter-local policy resolver:

```text
Stored annotation -> SemanticsProfile -> engine-specific input
```

`SemanticsProfile` should carry:

- target engine name and version constraints;
- uncertainty transmission policy, including reject / lower / midpoint / calibrated / custom behavior;
- engine-specific parameters, such as ProbLog branch probabilities or PyReason timestep options;
- temporal transmission policy, including how `valid_from` / `valid_to` become engine-native time coordinates;
- output readback policy, including how engine outputs are mapped back to candidate confidence, annotations, and valid-time intervals.

Initial adapter behavior:

- ProbLog
  - Directly consume probabilistic point bounds.
  - Require explicit policy for probabilistic intervals.
  - Reject possibilistic bounds unless an explicit policy is configured.
  - `problog/semantic/probability` becomes an engine projection/output lane, not a user-facing raw uncertainty input.
- PyReason
  - Consume possibilistic bounds as PyReason-compatible bounds.
  - Allow probabilistic bounds only through a named heuristic projection.
  - Convert business `valid_from` / `valid_to` into engine-local `active_from` / `active_to` timesteps at runtime.
  - Convert derived timestep outputs back into business valid-time intervals after execution.
  - `bound_lower` / `bound_upper` and `active_from` / `active_to` become adapter-local projection/output lanes, not user-facing raw uncertainty or time inputs.
- Shared / SDK docs
  - Explain that `confidence` remains a compatibility / output summary, not raw uncertainty truth.

### 5.2 PyReason Temporal Projection Candidate

PyReason should not receive wall-clock time directly from the data layer. Instead, a PyReason `SemanticsProfile` can build a run-local timeline:

1. Collect all relevant `valid_from` / `valid_to` boundaries from active input facts and query / run horizon.
2. Sort unique boundaries into a timeline: `t0 < t1 < ... < tn`.
3. Define timestep `i` as the half-open business interval `[ti, t(i+1))`.
4. Project an input fact to PyReason timestep `i` when its business interval covers that segment.
5. Emit PyReason `active_from=i` and `active_to=j` as adapter-local coordinates only.
6. After inference, map a derived result at timestep `i` back to `[ti, t(i+1))`, or to an explicit horizon interval for the final open segment.

This keeps the data-layer contract in business time while still using PyReason's integer timestep model naturally. The profile must declare whether timestep delay means "next segment" or a fixed wall-clock duration. The first implementation should prefer "next segment" because the boundary-derived segments may be irregular.

## 6. Boundaries And Invariants

- **Storage authority**: Annotation Store rows under `shared/semantic/raw_kind` and `shared/semantic/bound` are the canonical raw uncertainty copy. `meta_rows` are a mirror for SDK assertion selection, review, and ergonomic filtering.
- **Pair invariant**: `raw_kind` and `bound` have uncertainty semantics only as a pair. User writes with only one of the two keys are invalid.
- **Kind invariant**: valid `raw_kind` values are exactly lowercase `probabilistic` and `possibilistic`.
- **Bound invariant**: valid `bound` values are exactly two-element JSON lists normalized to float values with `0.0 <= lower <= upper <= 1.0`; bools, numeric strings, non-lists, and wrong-length lists are invalid.
- **Legacy-key invariant**: user-authored `probability`, `bound_lower`, and `bound_upper` meta are invalid in Phase 1. Engine-native annotation lanes with those names may remain internal adapter output/projection lanes.
- **Confidence invariant**: `confidence` remains the existing compatibility / output summary lane. It is not the canonical raw uncertainty carrier and is not renamed or removed in this blueprint.
- **Selection invariant**: `AssertionRecordSet.where(meta=...)` matches `bound` by exact normalized JSON value. No interval query semantics are introduced.
- **Adapter invariant**: ProbLog export, PyReason materialization, candidate confidence, `confidence_kind`, and runtime `SemanticsProfile` behavior are unchanged in Phase 1.
- **Temporal invariant**: `valid_from` / `valid_to` are data-layer business time; PyReason `active_from` / `active_to` remain adapter-local timestep coordinates.
- **Projection invariant**: any future `SemanticsProfile` projection is runtime-owned and must not write projection outputs back as the canonical raw uncertainty source.
- **Track separation invariant**: Rule / Policy namespace cleanup, `Body -> Branch`, `Branch.probability`, engine call-site placement, and Policy/PolicyFinding are deferred to a separate Track 2 blueprint.

## 7. Acceptance

- [ ] Valid `meta={"raw_kind": "probabilistic", "bound": [0.2, 0.8]}` and `possibilistic` writes succeed.
- [ ] Invalid `raw_kind`, missing pair member, malformed `bound`, bool elements, numeric-string elements, out-of-range bounds, and `lower > upper` are rejected before ledger mutation.
- [ ] User-authored `probability`, `bound_lower`, and `bound_upper` meta are rejected with clear validation errors.
- [ ] Valid writes persist normalized `raw_kind` and `bound` to `meta_rows`.
- [ ] Valid writes project `raw_kind` and `bound` to `shared/semantic/raw_kind` and `shared/semantic/bound` annotation rows.
- [ ] `AssertionRecordSet.where(meta={"raw_kind": ...})` and exact `where(meta={"bound": [...]})` can select the written assertions.
- [ ] Replace/edit validation failures do not retract or mutate the previously active assertion.
- [ ] Existing `confidence` behavior remains supported and unchanged.
- [ ] ProbLog export, PyReason materialization, candidate confidence, and valid-time assertion filtering remain unchanged.
- [ ] New uncertainty examples and docs use `raw_kind` / `bound`, not `probability`, `bound_lower`, or `bound_upper`.
- [ ] Affected module docs are synchronized.
- [ ] Track 2 rule/policy/function-tree work is not implemented in this blueprint.

## 8. Implementation Plan

1. Add focused tests for validation, legacy-key rejection, `meta_rows`, annotation projection, exact assertion filtering, and replace/edit atomicity.
2. Add write-protocol support for `raw_kind` and normalized `bound` as recognized meta keys.
3. Add shared annotation projection for `raw_kind` and `bound`.
4. Keep ProbLog export, PyReason materialization, candidate confidence, valid-time filtering, and Track 2 rule/policy syntax behavior unchanged.
5. Update SDK / core / adapter docs to make `raw_kind` / `bound` the preferred uncertainty authoring contract and distinguish it from candidate confidence and engine-native projection outputs.
6. Run focused uncertainty tests plus relevant write-protocol, annotation, SDK assertion selection, ProbLog, and PyReason regression tests.
7. Fill Outcome / Deviations, mark implemented, and archive when code and docs are aligned.

## 9. Docs To Update

- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/README.md` if a durable top-level docs entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Deviations from the blueprint:
- Rationale for adjustments:
- Archive status:
