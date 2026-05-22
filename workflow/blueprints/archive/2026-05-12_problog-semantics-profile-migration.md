# Task Blueprint: ProbLog SemanticsProfile Migration

- Status: implemented
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/core/semantics/`
  - `src/kernel/core/store/`
  - `src/kernel/sdk/`
  - `src/kernel/adapters/problog/`
  - `src/service/`
- Related Docs:
  - [docs/blueprints/archive/2026-05-12_semantics-profile-scaffolding.md](../archive/2026-05-12_semantics-profile-scaffolding.md)
  - [docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md](../archive/2026-05-11_branch-confidence-decomposition.md)
  - [docs/blueprints/archive/2026-05-11_engine-ext-decomposition.md](../archive/2026-05-11_engine-ext-decomposition.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
- Audit Log:
  - [2026-05-12_problog-semantics-profile-migration.audit.md](./2026-05-12_problog-semantics-profile-migration.audit.md)

## 1. Problem

Track 3 / B introduced `kernel.core.semantics.SemanticsProfile` as a
validated core value object, but no adapter consumes it yet. A2 and A3
redirected ProbLog branch probability semantics toward
`SemanticsProfile.rule_projection.problog`, while the executable path still
uses adapter-local and legacy bridges:

```text
compiled["body_confidences"]            -> legacy bridge
compiled["engine_ext"]                  -> ProbLogRuleExt
ProbLogRuleExt.branch_probabilities     -> export_problog(...)
```

C must make ProbLog the first adapter to consume the new profile shape,
without reopening public rule syntax or silently accepting SDK/service
runtime profile kwargs before E designs the durable call-site.

## 2. Goals

- Define how `SemanticsProfile.rule_projection.problog` maps to
  `ProbLogRuleExt.branch_probabilities`.
- Validate ProbLog-specific rule projection entries:
  - bucket: `problog`
  - `kind`: `branch_probability`
  - `target`: `branch:{index}`
  - `value`: numeric probability in `(0, 1]`
- Preserve B's generic `SemanticsProfile` shape and C/D separation.
- Preserve A2/A3 public-surface decisions:
  - no public `Branch(confidence=...)`
  - no public `body_confidences`
  - no public `Rule.engine_ext` / `Derivation.engine_ext`
- Preserve existing ProbLog execution behavior when no profile is supplied.
- Keep SDK/service `semantics=` / `semantics_profile=` rejection unless G0
  explicitly moves part of E into C.

## 3. Non-goals

- Do not migrate PyReason semantics; D owns PyReason intervals and temporal
  projection.
- Do not add SDK namespace export for `SemanticsProfile`.
- Do not reintroduce public rule/derivation engine parameters.
- Do not remove `ProbLogRuleExt` in C; it remains the adapter-local internal
  target.
- Do not remove `legacy_body_confidences` until a durable call-site exists
  and tests prove replacement coverage.
- Do not change ProbLog output parsing, provenance parsing, confidence
  readback, or acceptance behavior.
- Do not implement fact-level `raw_kind` / `bound` projection in C unless G0
  explicitly scopes it; this slice is about rule projection.

## 4. Source Audit

### 4.1 Existing code path

| Layer | Current shape | C relevance |
| --- | --- | --- |
| Core profile | `SemanticsProfile.rule_projection` is generic shape-validated only. | C can add ProbLog-specific interpretation outside core generic validation. |
| ProbLog rule ext | `ProbLogRuleExt(branch_probabilities=tuple[float, ...] | None)` validates `(0,1]`. | This should remain the adapter-local internal target. |
| ProbLog resolver | `resolve_problog_engine_ext(where, engine_ext, legacy_body_confidences)` merges explicit ext and legacy bridge. | Natural place to add a profile-derived branch-probability source. |
| ProbLog exporter | `export_problog(...)` consumes only `rule_spec["engine_ext"]` and materializes branch probabilities. | Ideally unchanged if C normalizes profile into `ProbLogRuleExt` before export. |
| ProbLog engine evaluator | `evaluate_problog(..., engine_ext=None, engine_options=None)` resolves ext before export. | Possible adapter-local entry if C adds `semantics_profile` to the evaluator. |
| Core evaluate | `evaluate_store(..., engine_ext=None, engine_options=None)` forwards only ext/options to engine evaluators. | Needed only if C exposes a core advanced call-site. |
| SDK evaluate | B rejects `semantics` and `semantics_profile`; compiled dict path can still carry internal `engine_ext` / `body_confidences`. | Should remain rejecting public profile kwargs unless C deliberately absorbs part of E. |
| Service runtime | B rejects top-level and derivation-level `semantics` / `semantics_profile`. | Should remain rejecting unless C deliberately absorbs part of E. |

### 4.2 Current tests

- `test_problog_rule_ext.py` covers:
  - normalization;
  - default deterministic branch probabilities;
  - legacy `body_confidences` bridge;
  - conflict with explicit `ProbLogRuleExt`.
- `test_problog_engine_eval.py` covers:
  - `ProbLogRuleExt` driving exported probability facts;
  - `legacy_body_confidences` driving exported probability facts;
  - conflicts between legacy and explicit ext.
- `test_semantics_profile_scaffolding.py` guards that adapters do not import
  `SemanticsProfile` in B. C will need to intentionally update or supersede
  that guard for ProbLog while keeping PyReason untouched.

### 4.3 Key finding

There are two different questions that must not be conflated:

```text
Adapter consumption:
  Can ProbLog normalize SemanticsProfile.rule_projection.problog into
  ProbLogRuleExt?

Runtime call-site:
  How do users pass a SemanticsProfile into SDK/service evaluate?
```

C should primarily answer the first question. E owns the second unless G0
explicitly pulls a narrow core-only call-site into C.

## 5. Scope Freeze Decisions

### 5.1 Profile-to-ProbLog projection

Locked normalized profile shape:

```python
SemanticsProfile(
    name="problog.branch-weighted",
    engine="problog",
    rule_projection={
        "problog": [
            {"target": "branch:0", "kind": "branch_probability", "value": 0.5},
            {"target": "branch:1", "kind": "branch_probability", "value": 0.8},
        ],
    },
)
```

Locked adapter-local normalization:

```text
SemanticsProfile.rule_projection.problog
  -> validate profile.engine == "problog"
  -> validate kind == "branch_probability"
  -> parse target "branch:{index}"
  -> validate branch index against compiled where branch count
  -> validate probability in (0, 1]
  -> materialize ProbLogRuleExt(branch_probabilities=(...))
```

Omitted branches default to `1.0`, matching existing
`ProbLogRuleExt(None)` deterministic defaults. Profile-defaulted values still
participate in carrier conflict checks.

### 5.2 Carrier conflict rules

C must define precedence when multiple carriers exist:

| Carrier | Status |
| --- | --- |
| `SemanticsProfile.rule_projection.problog` | New preferred source after C. |
| `ProbLogRuleExt.branch_probabilities` | Internal adapter bridge retained. |
| `legacy_body_confidences` | Temporary internal bridge retained until E/C follow-up removes it. |

- If only one carrier is present, use it.
- If multiple carriers are present and materialize the same tuple, allow.
- If multiple carriers materialize different tuples, reject with a stable
  conflict message naming all involved carrier families.

### 5.3 Runtime entry options considered

G0 considered three paths:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| C1 adapter helper only | Add `resolve_problog_engine_ext(..., semantics_profile=...)` and tests, but no runtime call-site. | Minimal; keeps E untouched. | Profile cannot affect normal evaluation until E. |
| C2 core advanced call-site | Add `Store.evaluate(..., semantics_profile=...)` and forward to ProbLog evaluator; SDK/service still reject. | Real adapter consumption without public SDK/service call-site. | Expands advanced core API before E. |
| C3 defer C until E | Do not implement C now; start E first. | Avoids unused adapter hook. | Delays validating profile-to-adapter design. |

Locked decision: **C2**. `Store.evaluate(..., semantics_profile=...)` becomes
the first observable ProbLog profile-consumption path. SDK and service
runtime profile kwargs remain rejected per B; E owns the durable user-facing
call-site.

### 5.4 Locked Decisions

| ID | Decision |
| --- | --- |
| D1 | Use C2: add a core advanced call-site by extending `Store.evaluate(..., semantics_profile=...)` and forwarding to ProbLog evaluation. |
| D2 | Omitted `rule_projection.problog` branch entries default to `1.0`, matching existing deterministic branch behavior. |
| D3 | Carrier conflict rules compare materialized tuples across `SemanticsProfile.rule_projection.problog`, `ProbLogRuleExt.branch_probabilities`, and `legacy_body_confidences`; matching tuples are allowed, conflicting tuples reject with carrier-family names. |
| D4 | ProbLog consumption strictly requires `SemanticsProfile.engine == "problog"` at runtime consumption, not at profile construction. |
| D5 | SDK `evaluate(..., semantics=...)` / `evaluate(..., semantics_profile=...)` and service top-level / derivation-level profile payloads continue to reject per B. |
| D6 | Branch index range validation lives in the ProbLog adapter resolver because it requires `where` branch count; B's generic profile validation remains unchanged. |
| D7 | Adapter import guards split: ProbLog is allowed and expected to consume `SemanticsProfile`; PyReason remains forbidden from importing or consuming it in C. |
| D8 | Existing `legacy_body_confidences` and `ProbLogRuleExt` behavior remains intact as internal bridges. |
| D9 | `export_problog(...)` continues consuming `ProbLogRuleExt`, not profile dictionaries; profile data is normalized before export. |
| D10 | PyReason adapter migration remains deferred to D; C must not touch PyReason interval or temporal semantics. |

### 5.5 Resolved G0 Questions Map

| Draft question | Resolution |
| --- | --- |
| C1/C2/C3 path | D1 chooses C2. |
| Branch coverage | D2 chooses omitted branches default to `1.0`. |
| Multi-carrier conflict | D3 locks matching-allowed / conflict-rejected materialized tuple comparison. |
| Engine match | D4 locks strict `engine="problog"` at consumption. |
| SDK/service boundary | D5 keeps B rejections until E. |
| Adapter guard update | D7 splits ProbLog-positive and PyReason-negative guards. |
| Branch index validation location | D6 keeps adapter-local validation with rule context. |

## 6. Boundaries And Invariants

- `SemanticsProfile` remains in `kernel.core.semantics`; C does not add an
  SDK export.
- ProbLog may import `SemanticsProfile`; PyReason must not import
  `SemanticsProfile` in C.
- `Store.evaluate(..., semantics_profile=profile)` is the only scoped runtime
  entry that consumes a profile.
- SDK `evaluate(..., semantics=...)` and `evaluate(..., semantics_profile=...)`
  continue to reject with B's Track 3 / E redirect.
- Service runtime top-level and derivation-level `semantics` /
  `semantics_profile` continue to reject with B's Track 3 / E redirect.
- `SemanticsProfile.engine != "problog"` rejects only when consumed by ProbLog;
  profile construction remains governed by B's generic engine whitelist.
- `rule_projection.problog[*].kind` must be `branch_probability` when consumed
  by ProbLog.
- `rule_projection.problog[*].target` must match `branch:{index}` and index
  must be in range for the evaluated `where` branches.
- `rule_projection.problog[*].value` must be a numeric probability in `(0, 1]`.
- Duplicate profile targets reject.
- Omitted profile branch targets materialize as `1.0`.
- Matching profile / `ProbLogRuleExt` / `legacy_body_confidences` tuples are
  accepted; conflicting tuples reject.
- Existing `ProbLogRuleExt` behavior remains green.
- Existing `legacy_body_confidences` behavior remains green.
- Existing ProbLog `engine_options.timeout` behavior remains green.
- `export_problog(...)` continues to consume `ProbLogRuleExt`, not profile
  dicts directly.
- No profile-derived values are written to stored assertion data.

## 7. Acceptance

- [ ] G0 locks D1-D10 and records the rationale.
- [ ] G1 red baseline covers profile-derived branch probability behavior
  through the C2 core entry.
- [ ] G1 guard tests preserve existing `ProbLogRuleExt`,
  `legacy_body_confidences`, and existing conflict behavior.
- [ ] `Store.evaluate(..., semantics_profile=profile)` reaches ProbLog in C;
  SDK and service still reject profile kwargs/payloads.
- [ ] Profile-derived branch probabilities drive exported ProbLog program
  probability annotations.
- [ ] Omitted profile branches default to deterministic probability `1.0`.
- [ ] Invalid ProbLog profile `kind` rejects.
- [ ] Invalid ProbLog profile `target` rejects.
- [ ] Out-of-range branch index rejects.
- [ ] Out-of-range branch probability rejects.
- [ ] Duplicate branch targets reject.
- [ ] Profile engine mismatch rejects.
- [ ] Matching profile / `ProbLogRuleExt` / `legacy_body_confidences` carriers
  are allowed.
- [ ] Conflicting profile / `ProbLogRuleExt` / `legacy_body_confidences`
  carriers reject with error text naming involved carrier families.
- [ ] ProbLog adapter import guard flips positive: ProbLog imports or consumes
  `SemanticsProfile` intentionally.
- [ ] PyReason guard remains negative: no PyReason `SemanticsProfile`
  consumption in C.
- [ ] `export_problog(...)` stays profile-agnostic and consumes
  `ProbLogRuleExt`.
- [ ] Existing ProbLog `engine_options.timeout` behavior remains green.
- [ ] B's SDK/service profile rejection tests remain green.
- [ ] Docs classify C as ProbLog consumption only; D/E remain deferred.

## 8. Implementation Plan

1. G0 scope-freeze:
   - choose C2;
   - lock branch default behavior;
   - lock conflict behavior;
   - lock SDK/service boundary.
2. G1 red + guard baseline:
   - add profile-to-ProbLog tests that fail before implementation;
   - keep existing bridge tests as guards.
3. G2 implementation:
   - add profile normalization helper;
   - integrate into the chosen runtime/internal entry;
   - keep exporter consuming `ProbLogRuleExt`.
4. G3 docs:
   - update ProbLog adapter docs;
   - update core semantics docs if new helper/API is added;
   - update SDK/service docs only to preserve rejection/defer-to-E wording.
5. G4 close-out:
   - fill outcome/deviations;
   - archive blueprint pair;
   - update archive inventory.

## 9. Docs To Update

- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/core/semantics/docs/README.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/sdk/docs/00_user_guide.en.md` if rejection/future wording changes.
- `src/kernel/sdk/docs/04_api_surface.en.md` if rejection/future wording changes.
- `src/service/docs/03_runtime_queries_policy.md` if service rejection/future
  wording changes.
- `docs/references/working/design-points/possibility-probability-transmission.zh.md`
  if C changes the durable projection shape.

## 10. Outcome / Deviations

### 10.1 Final Landed Behavior

- ProbLog is now the first adapter that consumes
  `kernel.core.semantics.SemanticsProfile`.
- The scoped core runtime entry is:
  `Store.evaluate(..., mode="problog", semantics_profile=profile)`.
- SDK `evaluate(..., semantics=...)` /
  `evaluate(..., semantics_profile=...)` still reject and point to Track 3 / E.
- Service top-level and derivation-level `semantics` /
  `semantics_profile` payloads still reject and point to Track 3 / E.
- `SemanticsProfile.rule_projection.problog` entries with
  `kind="branch_probability"` and `target="branch:{index}"` normalize into
  adapter-local `ProbLogRuleExt.branch_probabilities`.
- Omitted profile branches default to deterministic probability `1.0`.
- ProbLog consumption validates profile engine, kind, target shape, branch
  index range, numeric probability range, and duplicate branch targets.
- `SemanticsProfile.engine` remains generically validated by the core profile
  module; strict `engine="problog"` enforcement happens only at ProbLog
  consumption time.
- Profile / `ProbLogRuleExt` / legacy `body_confidences` carriers may coexist
  only when their materialized branch probability tuples match.
- `export_problog(...)` remains profile-agnostic and still consumes
  `ProbLogRuleExt`.
- PyReason remains untouched and does not import or consume
  `SemanticsProfile` in C.
- No profile-derived values are written into stored assertion data.

### 10.2 Validation

- G1 baseline before implementation:
  - `test_problog_semantics_profile_migration`: 14 tests, 11 expected errors.
  - `BridgeGuardTests`: 4 tests, 1 expected failure for the future ProbLog
    positive import guard.
- G2/G3 focused verification after implementation and docs:
  - C focused suite: 15/15 OK after the mode/profile guard hardening test.
  - B SemanticsProfile scaffolding suite: 24/24 OK.
  - Existing ProbLog rule extension + engine eval suite: 19/19 OK with the
    known `kernel.application` primer for audit/application import ordering.
  - Combined focused suite: 59/59 OK.
- G3 documentation grep gates:
  - no stale "ProbLog does not consume / C will decide / deferred to C"
    wording in release-facing C docs;
  - current C consumption mentions exist for
    `SemanticsProfile.rule_projection.problog`;
  - Track 3 / D and E remain explicitly deferred.
- `git diff --check` passed.

### 10.3 Commit Lineage

```text
938d4b86 docs(blueprints): draft problog semantics profile migration
0a0cb524 docs(blueprints): scope problog semantics profile migration
4b66c663 test(problog): add red baseline for semantics profile migration
6d900394 feat(problog): consume semantics profile rule projection
c4825e44 test(problog): cover semantics profile mode guard
01189804 docs(problog): document semantics profile consumption
```

### 10.4 Deviations

- C added a mid-cycle guard-hardening commit after G2. The implementation
  defensively rejected `Store.evaluate(..., mode="native",
  semantics_profile=...)` to prevent silent profile ignores; `c4825e44`
  added the focused test before G3 documented C2 as ProbLog-only.
- G3 updated the working transmission reference because C made
  `SemanticsProfile.rule_projection.problog` a current implementation fact,
  not just a conceptual future target.

### 10.5 Archive Notes

C is the first adapter-consumption slice after B. It proves that the generic
`SemanticsProfile.rule_projection` shape can be consumed by an adapter without
reopening public rule syntax or writing projected values back to stored facts.
The pattern for D is now clear: adapter-specific validation belongs at
consumption time, after the generic profile object has only validated shape.

C intentionally leaves the durable user-facing runtime call-site to E. E must
decide SDK/service `semantics=` acceptance, the `engine=` naming preference,
and whether `mode=` remains as an alias or is hard-cut in the pre-release
window.
