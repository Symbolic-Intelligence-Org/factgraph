# Task Blueprint: ProbLog SemanticsProfile Migration

- Status: draft
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

## 5. Proposed Shape

### 5.1 Profile-to-ProbLog projection

Candidate normalized profile shape:

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

Candidate adapter-local normalization:

```text
SemanticsProfile.rule_projection.problog
  -> validate profile.engine == "problog"
  -> validate kind == "branch_probability"
  -> parse target "branch:{index}"
  -> validate branch index against compiled where branch count
  -> validate probability in (0, 1]
  -> materialize ProbLogRuleExt(branch_probabilities=(...))
```

Open question for G0: whether branch entries must cover every branch or
whether omitted branches default to `1.0`. The latter is more ergonomic and
matches existing `ProbLogRuleExt(None)` deterministic defaults, but it must
be explicit.

### 5.2 Conflict rules

C must define precedence when multiple carriers exist:

| Carrier | Status |
| --- | --- |
| `SemanticsProfile.rule_projection.problog` | New preferred source after C. |
| `ProbLogRuleExt.branch_probabilities` | Internal adapter bridge retained. |
| `legacy_body_confidences` | Temporary internal bridge retained until E/C follow-up removes it. |

Recommended conflict rule for G0:

- If only one carrier is present, use it.
- If multiple carriers are present and materialize the same tuple, allow.
- If multiple carriers materialize different tuples, reject with a stable
  conflict message naming all involved carrier families.

### 5.3 Runtime entry options

G0 must choose one path:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| C1 adapter helper only | Add `resolve_problog_engine_ext(..., semantics_profile=...)` and tests, but no runtime call-site. | Minimal; keeps E untouched. | Profile cannot affect normal evaluation until E. |
| C2 core advanced call-site | Add `Store.evaluate(..., semantics_profile=...)` and forward to ProbLog evaluator; SDK/service still reject. | Real adapter consumption without public SDK/service call-site. | Expands advanced core API before E. |
| C3 defer C until E | Do not implement C now; start E first. | Avoids unused adapter hook. | Delays validating profile-to-adapter design. |

Draft recommendation: **C2** if the project wants observable adapter
consumption before E, otherwise **C1** if preserving the B boundary is more
important. C2 is still narrower than E because SDK/service public profile
kwargs remain rejected.

## 6. Boundaries And Invariants

- `SemanticsProfile` remains in `kernel.core.semantics`; ProbLog may import
  it only if G0 chooses C1/C2.
- PyReason adapter must not import or consume `SemanticsProfile` in C.
- SDK `evaluate(..., semantics=...)` and `evaluate(..., semantics_profile=...)`
  remain rejected unless G0 explicitly expands C into E.
- Service runtime top-level and derivation-level `semantics` /
  `semantics_profile` remain rejected unless G0 explicitly expands C into E.
- Existing `ProbLogRuleExt` behavior remains green.
- Existing `legacy_body_confidences` behavior remains green.
- Existing ProbLog `engine_options.timeout` behavior remains green.
- ProbLog exporter should continue to consume `ProbLogRuleExt`, not profile
  dicts directly.
- No profile-derived values are written to stored assertion data.

## 7. Acceptance

- [ ] G0 locks C1/C2/C3 and records the rationale.
- [ ] G1 red baseline covers profile-derived branch probability behavior.
- [ ] G1 guard tests preserve existing `ProbLogRuleExt`,
  `legacy_body_confidences`, and conflict behavior.
- [ ] Invalid ProbLog profile `kind` rejects.
- [ ] Invalid ProbLog profile `target` rejects.
- [ ] Out-of-range branch index rejects.
- [ ] Out-of-range branch probability rejects.
- [ ] Duplicate branch targets reject.
- [ ] Profile engine mismatch rejects.
- [ ] Profile-derived branch probabilities drive exported ProbLog program
  probability annotations once the scoped runtime entry is used.
- [ ] If multiple carriers are scoped, matching carriers are allowed and
  conflicting carriers reject.
- [ ] SDK/service public profile rejection remains green if E is out of
  scope.
- [ ] PyReason B guard remains green: no PyReason `SemanticsProfile`
  consumption in C.
- [ ] Docs classify C as ProbLog consumption only; D/E remain deferred.

## 8. Implementation Plan

1. G0 scope-freeze:
   - choose C1/C2/C3;
   - lock branch coverage/default behavior;
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

Task completion will fill:

- Final landed behavior:
- Deviations from blueprint:
- Rationale for deviations:
- Archive notes:
