# Task Blueprint: PyReason SemanticsProfile Migration

- Status: scoped
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/core/semantics/`
  - `src/kernel/core/store/`
  - `src/kernel/adapters/pyreason/`
  - `src/kernel/adapters/problog/`
  - `src/kernel/sdk/`
  - `src/service/`
- Related Docs:
  - [docs/blueprints/archive/2026-05-12_semantics-profile-scaffolding.md](../archive/2026-05-12_semantics-profile-scaffolding.md)
  - [docs/blueprints/archive/2026-05-12_problog-semantics-profile-migration.md](../archive/2026-05-12_problog-semantics-profile-migration.md)
  - [docs/blueprints/archive/2026-05-11_engine-ext-decomposition.md](../archive/2026-05-11_engine-ext-decomposition.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
- Audit Log:
  - [2026-05-12_pyreason-semantics-profile-migration.audit.md](./2026-05-12_pyreason-semantics-profile-migration.audit.md)

## 1. Problem

Track 3 / B introduced `SemanticsProfile` as the durable runtime projection
shape. Track 3 / C proved the first adapter-consumption pattern by mapping
`SemanticsProfile.rule_projection.problog` into ProbLog's internal
`ProbLogRuleExt` bridge through a core-only call-site:

```python
Store.evaluate(..., mode="problog", semantics_profile=profile)
```

PyReason still consumes adapter-local internals only:

```python
PyReasonRuleExt(
    timestep_delay=...,
    body_predicate_bounds={...},
    head_bound=(lo, hi),
)
engine_options={"timesteps": ...}
```

That leaves Track 3 in a half-consumed state: ProbLog can consume
`SemanticsProfile`, while PyReason still requires the internal bridge. E's
public call-site design (`evaluate(semantics=...)`, and the future
`engine=` naming preference recorded in B) should not be designed against
that asymmetric adapter state. D should therefore migrate PyReason next,
using C's consumption-time validation pattern and keeping SDK/service
profile kwargs rejected until E.

## 2. Goals

- Make PyReason the second `SemanticsProfile`-consuming adapter after
  ProbLog.
- Define how `SemanticsProfile.rule_projection.pyreason` normalizes into
  `PyReasonRuleExt`:
  - body atom interval thresholds;
  - head interval bounds;
  - rule delay.
- Activate only the locked minimal PyReason temporal projection modes:
  `fixed_timesteps` and `valid_time_boundaries`; all other temporal modes
  remain future work.
- Preserve C's pattern: generic `SemanticsProfile` validation remains in
  core; PyReason-specific target and interval validation happens at adapter
  consumption time.
- Preserve SDK and service rejection of profile payloads until E.
- Preserve existing `PyReasonRuleExt` and `engine_options.timesteps`
  behavior for internal callers and regression tests.

## 3. Non-goals

- Do not add SDK or service acceptance for `semantics=` /
  `semantics_profile=`; E owns the durable public call-site.
- Do not rename public `mode=` to `engine=` in D; E owns the call-site
  naming decision.
- Do not remove `PyReasonRuleExt` in D; it remains the adapter-local
  normalized target.
- Do not remove `engine_options.timesteps`; temporal projection must
  interoperate with it or remain separately validated.
- Do not migrate ProbLog behavior again; C's ProbLog profile consumption
  must remain unchanged.
- Do not implement broad temporal semantics, fact timeline rewriting, or
  stored valid-time projection tables.
- Do not change PyReason output parsing, candidate confidence readback, or
  pending annotation behavior.
- Do not modify `condition_weights` certainty-summary behavior.

## 4. Source Audit

### 4.1 Existing PyReason rule-extension path

| Layer | Current shape | D relevance |
| --- | --- | --- |
| Adapter ext | `PyReasonRuleExt(timestep_delay=0, body_predicate_bounds={}, head_bound=None)`. | This is the internal target D should normalize into, mirroring C's `ProbLogRuleExt` target. |
| Ext validation | Bounds must be numeric `(lo, hi)` with `0 <= lo <= hi <= 1`; delay must be non-negative int. | D can reuse this validation by materializing `PyReasonRuleExt`, while adding profile target validation before construction. |
| SDK Rule compiler | `compile_pyreason_rule(rule, engine_ext=...)` reads `PyReasonRuleExt` directly. | Internal tests can keep using this path; D should not remove it. |
| WhereIR compiler | `compile_where_ir_to_pyreason(..., engine_ext=...)` duck-types `timestep_delay`, `body_predicate_bounds`, and `head_bound`. | Main runtime evaluation path for lowered derivations. D can normalize profile into a `PyReasonRuleExt` before this compiler runs. |
| Engine eval | `pyreason_engine_eval(..., engine_ext=None, engine_options=None)` type-checks `engine_ext` and compiles rules. | Natural adapter-local entry for `semantics_profile`. |
| Core store | C added `Store.evaluate(..., semantics_profile=...)` but currently gates it to `mode="problog"`. | D must extend the core gate to allow `mode="pyreason"` when `profile.engine == "pyreason"`. |

### 4.2 Existing temporal and engine-option path

| Surface | Current fact | D relevance |
| --- | --- | --- |
| `SemanticsProfile.temporal_projection` | B accepts only `{"mode": "none"}` and rejects non-`none` with Track 3 / D redirect. | D is the first slice allowed to add PyReason temporal modes. |
| PyReason run config | `engine_options={"timesteps": positive_int}` is the only supported runtime option. | D must decide whether minimal temporal projection feeds this option, conflicts with it, or stays validation-only. |
| Fact materialization | `_materialize_edb_session(...)` maps active ledger facts to PyReason EDB facts; bounded predicates can read numeric fact values. | D should not rewrite fact timelines unless G0 explicitly scopes it. |
| Rule delay | `PyReasonRuleExt.timestep_delay` is rendered as `<-{delay}` in generated rules. | This is rule-level delay, not the same as runtime timesteps. G0 must decide whether profile covers it now. |

### 4.3 Current PyReason adapter behavior

The current adapter supports four time- or interval-adjacent knobs. D should
surface existing behavior before adding new PyReason capabilities:

| Existing adapter behavior | Current entry | Meaning |
| --- | --- | --- |
| Runtime step count | `engine_options.timesteps` | Number of PyReason execution timesteps. |
| Rule delay | `PyReasonRuleExt.timestep_delay` | Rule-local delay rendered as `<-n`; not a timestep-partition source. |
| Body predicate interval | `PyReasonRuleExt.body_predicate_bounds` | Predicate-level lower/upper interval used when compiling body atoms. |
| Head interval | `PyReasonRuleExt.head_bound` | Lower/upper interval rendered on the rule head. |

The adapter already has integer execution coordinates (`active_from` /
`active_to`) on materialized PyReason facts, but it does not currently map
business `valid_from` / `valid_to` values into those coordinates. Any D
implementation of `valid_time_boundaries` must therefore define the mapping
explicitly rather than assuming existing hidden behavior.

### 4.4 Temporal taxonomy

Locked temporal modes for D:

| Mode | Source | D scope |
| --- | --- | --- |
| `none` | No temporal projection. | Existing B behavior; keep. |
| `fixed_timesteps` | Explicit positive integer `timesteps`. | D implementation; 1:1 profile surface for existing `engine_options.timesteps`. |
| `valid_time_boundaries` | Caller-provided universe plus assertion `valid_from` / `valid_to` boundary timestamps. | D implementation with the boundary algorithm below. |
| `custom_timeline` | Caller-provided arbitrary mapping / labels. | Record as future; do not implement or lock detailed shape in D. |

The proposed `valid_time_boundaries` algorithm is:

```text
1. Caller supplies temporal_projection.universe = [start, end].
2. Collect universe start/end plus all assertion valid_from / valid_to values.
3. Sort and deduplicate boundary values.
4. Assign ordinal PyReason steps by sorted order.
5. For each assertion:
   - valid_from=None maps to universe start.
   - valid_to=None maps to open-ended active_to=None.
   - both missing means active over the full universe.
```

D assumes each assertion has at most one continuous valid interval. Recurring
or multi-interval validity is out of scope and should be represented by
application-level materialization into multiple single-interval assertions,
or by a future Uncertainty Phase 2 data-contract extension.

### 4.5 Existing tests

- `test_pyreason_rule_ext.py` covers `PyReasonRuleExt` validation and
  SDK-rule compilation.
- `test_pyreason_engine_eval.py` covers EDB materialization, runtime
  `engine_options.timesteps`, compiled body/head bounds, and wrong-ext type
  guards.
- `test_pyreason_e2e.py` covers core/SDK evaluation paths with internal
  `engine_ext` and `engine_options`.
- `test_semantics_profile_scaffolding.py` currently asserts:
  - ProbLog imports `SemanticsProfile` after C;
  - PyReason still does not import `SemanticsProfile` after C.

### 4.6 Key finding

D has two lanes, but only one should carry most of the complexity:

```text
rule_projection.pyreason:
  adapter-specific interval and delay projection into PyReasonRuleExt

temporal_projection:
  fixed_timesteps plus valid_time_boundaries; all other modes reject
```

This keeps D aligned with C's adapter-consumption pattern while avoiding a
full recurrence / multi-interval validity redesign.

## 5. Proposed Shape

### 5.1 Path option

Locked path: mirror C's core advanced call-site.

```python
Store.evaluate(..., mode="pyreason", semantics_profile=profile)
```

SDK and service `semantics=` / `semantics_profile=` kwargs continue to
reject until E. This lets D validate profile-to-adapter consumption without
shipping the durable user-facing call-site prematurely.

### 5.2 PyReason rule projection

Candidate profile shape:

```python
SemanticsProfile(
    name="pyreason.intervals",
    engine="pyreason",
    rule_projection={
        "pyreason": [
            {"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]},
            {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]},
            {"target": "rule", "kind": "timestep_delay", "value": 1},
        ],
    },
)
```

Locked choice: **path-style body atom targets**. They preserve the
SemanticsProfile projection model introduced in B and avoid exposing
PyReason's internal predicate-bound dictionary as the profile surface. The
adapter can resolve each path target against the lowered `where` and then
materialize the existing `body_predicate_bounds` map. If two body atom
targets resolve to the same predicate with different intervals, D should
reject as conflicting.

Locked choice: include `timestep_delay` as `{"target": "rule", "kind":
"timestep_delay", "value": non_negative_int}` because it is already part of
`PyReasonRuleExt` and is rule-level projection rather than runtime temporal
projection.

### 5.3 Temporal projection

Candidate fixed-step temporal shape:

```python
SemanticsProfile(
    name="pyreason.fixed",
    engine="pyreason",
    temporal_projection={
        "mode": "fixed_timesteps",
        "timesteps": 3,
    },
)
```

Candidate boundary-derived temporal shape:

```python
SemanticsProfile(
    name="pyreason.valid-time",
    engine="pyreason",
    temporal_projection={
        "mode": "valid_time_boundaries",
        "universe": ["2026-01-01", "2026-12-31"],
    },
)
```

G0 locks both scoped modes:

- implement `fixed_timesteps` as a direct profile surface for existing
  `engine_options.timesteps`;
- implement `valid_time_boundaries` using the explicit-universe boundary
  algorithm in §4.4;
- keep `custom_timeline` and recurrence / multi-interval validity out of D.

### 5.4 Carrier and conflict rules

Potential carriers in D:

| Carrier | Materialized target |
| --- | --- |
| `SemanticsProfile.rule_projection.pyreason` | `PyReasonRuleExt` fields |
| `PyReasonRuleExt(...)` | `PyReasonRuleExt` fields |
| `SemanticsProfile.temporal_projection.fixed_timesteps` | PyReason run config `timesteps` |
| `SemanticsProfile.temporal_projection.valid_time_boundaries` | PyReason fact `active_from` / `active_to` coordinates |
| `engine_options.timesteps` | PyReason run config `timesteps` |

Locked rule:

- Matching profile-derived and explicit internal values are allowed.
- Conflicting values reject with messages naming the carrier families.
- Existing internal-only behavior remains unchanged when no profile is
  supplied.

### 5.5 Scope Freeze Decisions

| ID | Decision |
| --- | --- |
| D1 | Use the C2 pattern: core `Store.evaluate(..., mode="pyreason", semantics_profile=...)` becomes the scoped runtime entry; SDK/service remain rejected until E. |
| D2 | PyReason consumption strictly requires `SemanticsProfile.engine == "pyreason"` at runtime consumption, not at profile construction. |
| D3 | `rule_projection.pyreason` validates at adapter consumption time, not in the generic profile module. |
| D4 | Body interval projection uses path-style `body_atom:{branch}:{atom}` targets. The adapter resolves the target against the lowered `where`; non-`pred` atoms and out-of-range paths reject. |
| D5 | Head interval projection uses `target="head:0"` and `kind="interval"`. |
| D6 | Rule delay projection is included in D as `target="rule"`, `kind="timestep_delay"`, `value=<non-negative int>`. |
| D7 | Temporal projection accepts only `none`, `fixed_timesteps`, and `valid_time_boundaries` in D; all other modes, including `custom_timeline`, continue to reject. |
| D8 | `fixed_timesteps` requires positive integer `timesteps` and maps to PyReason run config `timesteps`; matching `engine_options.timesteps` is allowed and conflicting values reject. |
| D9 | `valid_time_boundaries` requires caller-provided `universe=[start,end]` strings. It collects universe boundaries plus selected assertion `valid_from` / `valid_to` strings from the current PyReason EDB materialization scope, sorts/deduplicates them, and maps them to ordinal `active_from` / `active_to`. |
| D10 | `valid_time_boundaries` treats missing `valid_from` as universe start, missing `valid_to` as open-ended `active_to=None`, and both missing as active for the full universe. Each assertion is a single continuous interval; recurrence and multi-interval validity remain out of scope. |
| D11 | `valid_time_boundaries` derives PyReason run config `timesteps` as the highest ordinal boundary index. Matching `engine_options.timesteps` is allowed and conflicting values reject. |
| D12 | Carrier conflicts between profile-derived PyReason settings and explicit `PyReasonRuleExt` / `engine_options` reject with carrier-family names; matching carriers are allowed. |
| D13 | `PyReasonRuleExt` and `engine_options.timesteps` remain supported internal bridges. |
| D14 | Adapter import guards update: ProbLog and PyReason may import `SemanticsProfile`; native/Souffle adapters must not begin consuming it in D. |
| D15 | ProbLog profile consumption from C remains unchanged. SDK/service profile rejection from B remains unchanged; E owns public call-site acceptance and the `engine=` naming decision. |

### 5.6 Resolved G0 Questions Map

| Draft question | Resolution |
| --- | --- |
| D path vs E-first | D1 locks the C2-style core advanced call-site before E. |
| Body target spelling | D4 locks path-style `body_atom:{branch}:{atom}`. |
| Head target spelling | D5 locks `head:0`. |
| Rule delay inclusion | D6 includes `timestep_delay` in D. |
| Temporal modes | D7 locks `fixed_timesteps` and `valid_time_boundaries`; other modes reject. |
| Fixed-step carrier conflict | D8 and D11 lock matching-allowed / conflict-rejected behavior against `engine_options.timesteps`. |
| Valid-time collection scope | D9 locks the scope to selected assertions materialized into the current PyReason EDB session, not per-rule collection. |
| Missing valid-time values | D10 locks universe fallback and open-ended semantics. |
| Multi-interval validity | D10 defers recurrence and multi-interval data modeling. |
| Adapter guard update | D14 locks ProbLog + PyReason positive import allowance and native/Souffle non-consumption. |

## 6. Boundaries And Invariants

- `SemanticsProfile` remains core-only; D does not add SDK namespace export.
- Generic `SemanticsProfile.rule_projection` validation remains shape-only;
  PyReason target resolution happens in the adapter.
- Core profile temporal validation accepts only `none`, `fixed_timesteps`,
  and `valid_time_boundaries`; `custom_timeline` and unknown modes reject.
- `Store.evaluate(..., mode="pyreason", semantics_profile=profile)` is the
  only scoped runtime profile-consumption entry added by D.
- `Store.evaluate(..., semantics_profile=profile)` rejects when selected
  mode and `profile.engine` do not match.
- SDK and service `semantics` / `semantics_profile` payloads continue to
  reject with Track 3 / E redirect text.
- `body_atom:{branch}:{atom}` targets resolve against lowered `where` and
  reject invalid shape, non-`pred` atoms, and out-of-range indexes.
- `head:0` interval projection materializes to `PyReasonRuleExt.head_bound`.
- `rule` / `timestep_delay` projection materializes to
  `PyReasonRuleExt.timestep_delay`.
- `fixed_timesteps` and `engine_options.timesteps` matching values are
  allowed; conflicts reject with carrier-family names.
- `valid_time_boundaries` reads `valid_from` / `valid_to` from selected
  assertion metadata in the current PyReason EDB materialization scope.
- `valid_time_boundaries` can require the PyReason EDB materializer to use
  witness-preserving projection so assertion metadata remains available.
- Missing `valid_from` maps to universe start; missing `valid_to` maps to
  open-ended `active_to=None`; both missing means full-universe validity.
- Each assertion is one continuous interval. Periodic or multi-interval
  validity must be materialized by the caller into multiple assertions or
  deferred to future data-contract work.
- Existing `PyReasonRuleExt` direct construction, SDK-rule compilation, and
  core `engine_ext` behavior stay green.
- Existing `engine_options.timesteps` behavior stays green when no temporal
  projection is supplied.
- ProbLog's `SemanticsProfile.rule_projection.problog` behavior from C stays
  green.
- PyReason output readback, candidate confidence, and pending annotation
  behavior do not change.
- No stored profile-derived values are written back into facts, registry
  entries, or assertion metadata.

## 7. Acceptance

- [ ] G0 locks D1-D15 and records the valid-time boundary collection scope.
- [ ] G1 red baseline proves PyReason does not yet consume
  `SemanticsProfile`.
- [ ] G1 guard baseline proves C's ProbLog profile consumption remains
  green.
- [ ] `Store.evaluate(..., mode="pyreason", semantics_profile=profile)`
  drives generated PyReason rule intervals after G2.
- [ ] `Store.evaluate(..., mode="native", semantics_profile=pyreason_profile)`
  rejects with mode/engine mismatch text.
- [ ] Profile engine mismatch rejects when `mode="pyreason"` receives a
  non-PyReason profile.
- [ ] Invalid PyReason rule-projection kind rejects with stable error text.
- [ ] Invalid body atom target shape rejects with stable error text.
- [ ] Out-of-range body atom path rejects with stable error text.
- [ ] Non-`pred` body atom target rejects with stable error text.
- [ ] Invalid interval values reject with stable error text.
- [ ] Duplicate or conflicting profile interval targets reject with stable
  error text.
- [ ] Profile-derived body interval threshold materializes into generated
  PyReason rule syntax.
- [ ] Profile-derived head interval materializes into generated PyReason rule
  syntax.
- [ ] Profile-derived `timestep_delay` materializes into generated PyReason
  rule syntax.
- [ ] `fixed_timesteps` is accepted by `SemanticsProfile` and maps to
  PyReason run config timesteps.
- [ ] `fixed_timesteps` conflicts with mismatched
  `engine_options.timesteps`.
- [ ] `valid_time_boundaries` explicit universe boundaries plus assertion
  `valid_from` / `valid_to` values map to ordinal PyReason `active_from` /
  `active_to`.
- [ ] `valid_time_boundaries` handles missing `valid_from`, missing
  `valid_to`, and both missing according to D10.
- [ ] `valid_time_boundaries` conflicts with mismatched
  `engine_options.timesteps`.
- [ ] Unsupported temporal modes still reject with Track 3 / D or future
  redirect text.
- [ ] Existing `PyReasonRuleExt` tests remain green.
- [ ] Existing PyReason `engine_options.timesteps` tests remain green.
- [ ] B's SDK/service profile rejection tests remain green.
- [ ] C's ProbLog focused tests remain green.
- [ ] Adapter import guards show ProbLog and PyReason may import
  `SemanticsProfile`, while native/Souffle do not consume it.
- [ ] Docs classify D as PyReason consumption, not public SDK/service
  call-site completion.

## 8. Implementation Plan

1. G0 scope-freeze: locked path target spelling, rule-delay inclusion,
   temporal mode shape, carrier conflict rules, and guard updates.
2. G1 red + guard baseline: add PyReason profile-consumption tests and update
   adapter import guards.
3. G2 implementation: extend core profile temporal validation, PyReason
   resolver/engine evaluation, and core `Store.evaluate` profile gate.
4. G3 docs sync: update PyReason adapter docs, core semantics docs, SDK and
   service rejection notes, and transmission reference.
5. G4 close-out: fill Outcome / Deviations, archive blueprint pair, update
   archive inventory, then push + milestone after review.

## 9. Docs To Update

- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/kernel/core/semantics/docs/README.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `docs/references/working/design-points/possibility-probability-transmission.zh.md`
- `docs/README.md` only if a new durable entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Validation:
- Commit lineage:
- Deviations:
- Archive notes:
