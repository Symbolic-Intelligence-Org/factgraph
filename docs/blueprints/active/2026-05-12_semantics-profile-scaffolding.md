# Task Blueprint: SemanticsProfile Scaffolding

- Status: scoped
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/core/`
  - `src/kernel/application/protocol/`
  - `src/kernel/sdk/`
  - `src/kernel/adapters/problog/`
  - `src/kernel/adapters/pyreason/`
  - `src/service/`
- Related Docs:
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/blueprints/archive/2026-05-11_uncertainty-transmission-layer.md](../archive/2026-05-11_uncertainty-transmission-layer.md)
  - [docs/blueprints/archive/2026-05-11_derivation-mode-to-callsite.md](../archive/2026-05-11_derivation-mode-to-callsite.md)
  - [docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md](../archive/2026-05-11_branch-confidence-decomposition.md)
  - [docs/blueprints/archive/2026-05-11_engine-ext-decomposition.md](../archive/2026-05-11_engine-ext-decomposition.md)
  - [docs/blueprints/archive/2026-05-11_condition-weights-decomposition.md](../archive/2026-05-11_condition-weights-decomposition.md)
- Audit Log:
  - [2026-05-12_semantics-profile-scaffolding.audit.md](./2026-05-12_semantics-profile-scaffolding.audit.md)

## 1. Problem

Track 3 A1-A4 decomposed public rule / derivation surfaces that used to
carry engine semantics directly:

- A1 removed public `Derivation.mode`; engine selection is call-site
  runtime configuration.
- A2 made branch syntax structure-only and rejected public
  `body_confidences`.
- A3 removed public SDK and service `engine_ext`.
- A4 retained `condition_weights`, but reclassified it as
  certainty/explain projection input and pointed future runtime
  configuration at `SemanticsProfile.certainty_projection`.

The project now has a clean public rule template surface, but the durable
replacement surface does not exist yet. Current redirects and docs point to
future profile fields:

```text
SemanticsProfile.rule_projection
SemanticsProfile.rule_projection.problog
SemanticsProfile.certainty_projection
```

The uncertainty Phase 1 data contract also created fact-level
`raw_kind` / `bound`, but no runtime profile exists to project those raw
uncertainty values into engine-native views.

B must therefore introduce the `SemanticsProfile` scaffolding without
immediately migrating adapters. The goal is to make the future runtime
projection surface concrete enough for C/D/E, while avoiding another
large adapter rewrite inside the same slice.

## 2. Goals

- Define the initial `SemanticsProfile` data shape and validation rules.
- Make the field split explicit:
  - `engine`
  - `engine_options`
  - `uncertainty_projection`
  - `temporal_projection`
  - `rule_projection`
  - `certainty_projection`
  - `output_readback`
  - `fallback`
- Define normalized profile output suitable for later SDK, service, and
  adapter consumption.
- Provide inspection / dry-run scaffolding for projected semantics without
  writing projected values back into stored facts or public rule objects.
- Keep A1-A4 public-surface decisions intact.
- Keep this slice small enough that ProbLog and PyReason adapter migration
  can remain separate C/D work.

## 3. Non-goals

- Do not migrate ProbLog adapter execution to consume
  `SemanticsProfile.rule_projection`.
- Do not migrate PyReason adapter execution to consume
  `SemanticsProfile.rule_projection` or temporal projection.
- Do not remove internal `EngineExtBase`, `CompiledDerivationPlan.engine_ext`,
  `legacy_body_confidences`, `ProbLogRuleExt`, or `PyReasonRuleExt` bridges.
- Do not reintroduce public `Rule.engine_ext`, `Derivation.engine_ext`,
  `Branch(confidence=...)`, `Body`, or `Derivation.mode`.
- Do not change `evaluate(...)` candidate behavior, acceptance behavior, or
  persisted assertion data.
- Do not change certainty-summary math or `condition_weights` runtime
  behavior.
- Do not implement full PyReason valid-time to timestep projection in B.
- Do not add a stored projection result table or write profile-derived values
  into the canonical data layer.

## 4. Source Audit

### 4.1 Existing redirects and design sources

| Source | Current fact |
| --- | --- |
| Uncertainty Phase 1 archive | Data layer now owns `raw_kind` / `bound`; future runtime projection is deferred to `SemanticsProfile`. |
| A2 archive | Public `body_confidences` is rejected with redirect to temporary `ProbLogRuleExt.branch_probabilities` and future `SemanticsProfile.rule_projection.problog`. |
| A3 archive | Public `engine_ext` is rejected and redirects only to future `SemanticsProfile.rule_projection`; internal bridges remain. |
| A4 archive | `condition_weights` is retained and classified as certainty/explain projection input; future runtime configuration target is `SemanticsProfile.certainty_projection`. |
| Working reference | Recommended fields include `engine`, `engine_options`, `uncertainty_projection`, `temporal_projection`, `rule_projection`, `output_readback`, and `fallback`. |

### 4.2 Current code surfaces

| Layer | Current shape | B relevance |
| --- | --- | --- |
| Core types | `EngineExtBase`, `EngineOptionsIR`, `ReadPolicy`; no `SemanticsProfile`. | B needs a new profile type or module; `ReadPolicy` is a precedent for value-object validation but is read-path specific. |
| SDK evaluate | Current public API is `SDKStore.evaluate(..., mode=..., engine_options=...)`; rejects `view` / `policy` and removed `temporal_view`. | B stays shape-only. Future Track 3 / E should prefer `engine=` as the public engine-selection keyword because it names the selected inference backend more directly than historical `mode=`. |
| SDK compiled plan bridge | `_compiled_derivation_plan_to_application(...)` still resolves internal ProbLog bridge from `body_confidences` and returns `CompiledDerivationPlan(engine_ext, engine_options)`. | B should not break this bridge; later C/D can replace it with profile-derived internals. |
| Application protocol | `CompiledDerivationPlan.engine_ext`, `.engine_options`; `DerivationEvaluateRequest.engine`. | Natural downstream carrier exists, but adding `semantics_profile` here would affect application DTOs. |
| Service runtime | Rejects public `body_confidences` and `engine_ext`; then compiles derivation and passes internal `engine_ext` into `Store.evaluate`. | B must decide whether service accepts a top-level `semantics` / `semantics_profile` object now or later. |
| Core evaluate | `evaluate_store(..., engine_ext=..., engine_options=...)`. | Current evaluator can remain unchanged in B; profile can normalize into existing carriers later. |
| ProbLog adapter | `ProbLogRuleExt.branch_probabilities` and `resolve_problog_engine_ext(..., legacy_body_confidences=...)`. | C owns migration; B may define normalized `rule_projection.problog` shape and validators only. |
| PyReason rule projection | `PyReasonRuleExt(timestep_delay, body_predicate_bounds, head_bound)`; `compile_where_ir_to_pyreason(..., engine_ext=...)` reads these internals. | D owns migration; B may define normalized path-targeted interval shape. |
| PyReason runtime options | `engine_options.timesteps` is the only currently supported option. | B should represent `engine_options` and `temporal_projection`, but not yet derive timesteps from valid-time boundaries. |
| Certainty lane | `condition_weights` remains public and is consumed by confidence-kind resolver + certainty materializer. | B should give this lane a profile home (`certainty_projection`) without changing runtime behavior. |

### 4.3 Key finding

B is not an adapter migration slice. The current code still needs internal
bridge types to keep existing behavior alive. The safest B slice is:

```text
Introduce and validate SemanticsProfile shape
Normalize / inspect profile intent
Do not alter adapter execution
Do not alter stored facts or public rule constructors
```

## 5. Proposed Shape

### 5.0 Scope Freeze Decisions

| ID | Decision |
| --- | --- |
| D1 | Module placement is a new core subpackage: `src/kernel/core/semantics/profile.py`, with package exports from `src/kernel/core/semantics/__init__.py`. |
| D2 | Do not export `SemanticsProfile` from `kernel.sdk.__all__` in B. It is advanced importable through `kernel.core.semantics`. |
| D3 | Do not accept `semantics=` / `semantics_profile=` in `SDKStore.evaluate(...)`, service runtime derivation evaluation, or application evaluate requests in B. Runtime consumption is Track 3 / E. |
| D4 | `SemanticsProfile` is a frozen value object (`@dataclass(frozen=True)`) with no mutation helpers. |
| D5 | Profile schema `version` is locked to `"1.0"` in B. Other versions reject. |
| D6 | `rule_projection` validation is generic shape validation only: engine buckets map to a list of `{target, kind, value}` entries with non-empty string `target` / `kind`. Engine-specific kind semantics and target resolution are deferred to C/D. |
| D7 | `uncertainty_projection` policies are a locked enum in B. Initial accepted policies are `identity_probability`, `probability_interval`, `possibility_interval`, `lower`, `midpoint`, `upper`, and `reject`; the projection-level fallback accepts `reject_unconfigured`, `warn_default`, or `use_default`. |
| D8 | `temporal_projection` accepts only `{"mode": "none"}` or omission in B. Non-`none` temporal modes reject with a Track 3 / D redirect. |
| D9 | Inspection scope is core-only: `kernel.core.semantics.inspect_semantics_profile(profile)`. No SDK manager, SDK namespace, or service endpoint is added in B. |
| D10 | A1-A4 public-surface rejection gates and internal bridges remain intact: no adapter consumes `SemanticsProfile`; `CompiledDerivationPlan.engine_ext`, `engine_options`, `legacy_body_confidences`, `ProbLogRuleExt`, `PyReasonRuleExt`, and `condition_weights` behavior remain unchanged. |

### 5.1 Locked profile fields

Initial locked shape:

```python
SemanticsProfile(
    name="problog.default",
    engine="problog",
    version="1.0",
    engine_options={},
    uncertainty_projection={...},
    temporal_projection={...},
    rule_projection={...},
    certainty_projection={...},
    output_readback={...},
    fallback="reject_unconfigured",
)
```

Field intent:

| Field | Intent |
| --- | --- |
| `name` | Human-readable profile identifier for inspectability and logs. |
| `engine` | Target engine: `native`, `souffle`, `problog`, `pyreason`. |
| `version` | Profile schema version, not rule version. |
| `engine_options` | Existing call-time adapter options such as PyReason `timesteps`. |
| `uncertainty_projection` | How fact-level `raw_kind` / `bound` is interpreted for the engine view. |
| `temporal_projection` | How business valid time maps to engine time coordinates. |
| `rule_projection` | Path-targeted rule-shape projection such as ProbLog branch weights or PyReason intervals. |
| `certainty_projection` | Future runtime configuration for the retained `condition_weights` lane. |
| `output_readback` | How engine output is mapped back to candidate summaries, annotations, and business-time intervals. |
| `fallback` | Reject / default policy when a profile lacks required projection instructions. |

### 5.2 Locked normalized rule projection shape

The public profile should not expose adapter classes. It should use plain
structured data that can later normalize into adapter-local internals:

```json
{
  "rule_projection": {
    "problog": [
      {"target": "branch:0", "kind": "branch_probability", "value": 0.9}
    ],
    "pyreason": [
      {"target": "body_atom:0:1", "kind": "interval_threshold", "value": [0.5, 1.0]},
      {"target": "head:0", "kind": "interval", "value": [0.8, 0.9]}
    ]
  }
}
```

Per D6, B validates only the generic bucket and triplet shape. It does not
validate that `branch_probability` is a known ProbLog kind, that
`interval_threshold` is a known PyReason kind, or that targets resolve
against a concrete rule. C/D own engine-specific validation and target
resolution.

### 5.3 Locked uncertainty projection shape

The profile should preserve the semantic boundary introduced by Phase 1:

```json
{
  "uncertainty_projection": {
    "probabilistic": {"policy": "identity_probability"},
    "possibilistic": {"policy": "reject"},
    "fallback": "reject_unconfigured"
  }
}
```

Per D7, policy strings are locked enough to catch typos in B, but no engine
execution consumes them yet. C/D may extend the accepted enum when they add
adapter consumption.

### 5.4 Locked temporal projection shape

PyReason temporal projection remains design-only in B. Only no-op temporal
projection is accepted:

```json
{
  "temporal_projection": {
    "mode": "none"
  }
}
```

Future PyReason mode is documented but rejected in B:

```json
{
  "temporal_projection": {
    "mode": "valid_time_boundaries",
    "input_interval": "valid_from_valid_to",
    "engine_interval": "active_from_active_to",
    "delay_semantics": "next_segment"
  }
}
```

Per D8, `valid_time_boundaries`, `fixed_duration_bucket`, and any other
non-`none` mode reject in B with a Track 3 / D redirect.

### 5.5 Locked inspection scaffolding

B should provide a way to inspect a profile's normalized projection intent
without running an adapter or writing projected values:

```python
inspect_semantics_profile(profile)
```

or equivalent SDK/service helper later. The output should be JSON-like and
explicitly non-canonical:

```json
{
  "engine": "problog",
  "profile": "problog.default",
  "uses": {
    "engine_options": true,
    "rule_projection": true,
    "uncertainty_projection": true,
    "temporal_projection": false,
    "certainty_projection": false
  },
  "warnings": []
}
```

Per D9, B implements this only as a pure core helper. SDK and service wrappers
are deferred to E.

### 5.6 Resolved G0 Questions Map

| Draft question | Resolution |
| --- | --- |
| Module placement | D1: new `kernel.core.semantics` subpackage. |
| SDK export | D2: no SDK export in B. |
| `evaluate(semantics=...)` integration | D3: not accepted in B. |
| Future engine-selection keyword | B does not rename current APIs; Track 3 / E should evaluate `engine=` as the preferred public call-site name over historical `mode=`. |
| Rule projection strictness | D6: generic shape validation only. |
| Uncertainty projection policy strictness | D7: locked enum. |
| Temporal projection mode strictness | D8: `none` only. |
| Inspection helper scope | D9: core helper only. |
| Mutability | D4: frozen dataclass. |
| Profile schema version | D5: only `"1.0"`. |
| Internal bridge preservation | D10: all A1-A4 bridges and rejection gates remain intact. |

## 6. Boundaries And Invariants

Scope-freeze invariants:

- `SemanticsProfile.__module__` is `kernel.core.semantics.profile`.
- `SemanticsProfile` is a frozen dataclass.
- `SemanticsProfile.version` accepts only `"1.0"`.
- `SemanticsProfile.engine` accepts only `native`, `souffle`, `problog`,
  or `pyreason`.
- `SemanticsProfile` is not exported by `kernel.sdk.__all__` in B.
- `SDKStore.evaluate(..., semantics=...)` and
  `SDKStore.evaluate(..., semantics_profile=...)` reject rather than silently
  ignore the profile.
- Service runtime derivation evaluation rejects top-level `semantics` and
  `semantics_profile` in B.
- Application protocol `DerivationEvaluateRequest` does not gain a
  `semantics` / `semantics_profile` field in B.
- `rule_projection` accepts only mappings from engine bucket to lists of
  entries; each entry must contain non-empty string `target` and `kind`.
- `rule_projection` does not validate engine-specific kind names or resolve
  targets against a rule in B.
- `uncertainty_projection` rejects unknown policy strings.
- `temporal_projection` rejects any mode other than `none`.
- `inspect_semantics_profile(profile)` returns JSON-like data and does not
  mutate the profile or any rule/derivation/assertion object.
- No adapter module imports `SemanticsProfile` in B.
- Existing A1-A4 rejection gates remain intact.
- Existing `engine_options` behavior remains intact.
- Existing internal adapter bridges remain intact in B.
- `condition_weights` behavior and certainty-summary math remain unchanged.
- No profile-derived value is written into stored assertion data.

## 7. Acceptance

- [ ] G0 locks D1-D10 and records the rationale in the audit log.
- [ ] G1 red baseline asserts `kernel.core.semantics.profile.SemanticsProfile`
  and `inspect_semantics_profile` exist and currently fails before G2.
- [ ] G1 guard tests assert A1-A4 rejection behavior and internal bridges
  still work.
- [ ] `SemanticsProfile` is a frozen dataclass in
  `kernel.core.semantics.profile`.
- [ ] `kernel.core.semantics` exports `SemanticsProfile` and
  `inspect_semantics_profile`.
- [ ] `kernel.sdk.__all__` does not export `SemanticsProfile`.
- [ ] Invalid profile `version`, `engine`, and `fallback` values reject with
  stable messages.
- [ ] Invalid `rule_projection` bucket shape, missing `target`, missing
  `kind`, non-string `target`, and non-string `kind` reject.
- [ ] Engine-specific `rule_projection` kinds are not interpreted or resolved
  in B.
- [ ] Invalid `uncertainty_projection` policy strings reject.
- [ ] Non-`none` `temporal_projection.mode` rejects with Track 3 / D redirect.
- [ ] `inspect_semantics_profile(profile)` returns a JSON-like dict with
  `engine`, `profile`, `version`, `uses`, `fallback`, and `warnings`.
- [ ] Inspection is pure: it does not mutate the profile or require a rule,
  derivation, store, registry, or adapter.
- [ ] `SDKStore.evaluate(..., semantics=...)` and
  `SDKStore.evaluate(..., semantics_profile=...)` reject in B.
- [ ] Service runtime derivation evaluation rejects top-level `semantics` and
  `semantics_profile` in B.
- [ ] Application protocol does not gain a profile field in B.
- [ ] No adapter imports `SemanticsProfile`.
- [ ] A1-A4 focused suite remains green.
- [ ] Existing ProbLog/PyReason/condition_weights bridge tests remain green.
- [ ] Docs explain that B is scaffolding; C/D/E own adapter and SDK runtime
  consumption.
- [ ] No profile-derived value is written into stored assertion data.

## 8. Implementation Plan

Draft cadence:

1. G0 scope-freeze:
   - lock module location;
   - lock public export decision;
   - lock profile fields and validation strictness;
   - lock inspection helper scope;
   - lock non-goals around adapter consumption.
2. G1 red/guard baseline:
   - add tests for profile absence / future desired shape;
   - add guard tests for A1-A4 rejection behavior and existing bridges.
3. G2 implementation:
   - add `SemanticsProfile` data shape;
   - add validation / normalization;
   - add inspection helper if scoped.
4. G3 docs:
   - update SDK / core / service / adapter docs to describe profile
     scaffolding and defer C/D/E.
5. G4 close-out:
   - fill Outcome / Deviations;
   - mark implemented;
   - archive blueprint pair and update archive inventory.

## 9. Docs To Update

Expected docs to inspect:

- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `src/service/docs/04_rules_registry.md`
- `docs/references/working/design-points/possibility-probability-transmission.zh.md` only if draft conclusions materially change the reference.

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Deviations from blueprint:
- Rationale for deviations:
- Archive notes:
