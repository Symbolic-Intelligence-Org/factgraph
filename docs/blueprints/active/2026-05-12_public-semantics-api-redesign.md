# Task Blueprint: Track 2 Public Semantics API Redesign

- Status: draft
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/__init__.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/sdk/dsl/branch.py`
  - `src/kernel/core/semantics/profile.py`
  - `src/kernel/application/protocol/derivation.py`
  - `src/service/runtime_v1.py`
  - `src/kernel/adapters/problog/rule_ext.py`
  - `src/kernel/adapters/pyreason/rule_ext.py`
  - `src/kernel/adapters/pyreason/where_compile.py`
- Related Docs:
  - [docs/references/working/design-points/post-track3-semantics-public-api.zh.md](../../references/working/design-points/post-track3-semantics-public-api.zh.md)
  - [docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md](../archive/2026-05-12_branch-identity-rule-inspect.md)
  - [docs/blueprints/archive/2026-05-12_sdk-service-semantics-callsite.md](../archive/2026-05-12_sdk-service-semantics-callsite.md)
  - [docs/blueprints/archive/2026-05-12_problog-semantics-profile-migration.md](../archive/2026-05-12_problog-semantics-profile-migration.md)
  - [docs/blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md](../archive/2026-05-12_pyreason-semantics-profile-migration.md)
- Audit Log:
  - [2026-05-12_public-semantics-api-redesign.audit.md](./2026-05-12_public-semantics-api-redesign.audit.md)

## 1. Problem

Track 3 completed the canonical runtime profile path:

```python
fg.eval.evaluate(deriv, engine="pyreason", semantics=SemanticsProfile(...))
```

That call-site is correct but heavy for public authoring:

- `engine` appears twice: once as the public selector and once inside `SemanticsProfile.engine`.
- `SemanticsProfile` exposes all projection lanes even when the caller uses one engine.
- `rule_projection.problog` and `rule_projection.pyreason` require adapter-path dictionaries such as `branch:0` and `body_atom:0:0`.
- Track 1 has now landed `Branch(id=...)` and `fg.rules.inspect(...)`, so public semantics can reference branch ids instead of positional adapter paths.

Track 2 should decide whether to introduce lighter engine-specific public semantics objects, how those objects lower into the existing `SemanticsProfile` core path, and whether `engine=` can be derived from the semantics object.

## 2. Goals

- Define the post-Track-3 public semantics API shape.
- Decide whether to introduce `ProbLogSemantics` and `PyReasonSemantics` as SDK-exported public types.
- Decide engine auto-derivation rules for `fg.eval.evaluate(...)` and `evaluate_compiled(...)`.
- Preserve Track 3's core/application adapter path unless a scoped decision explicitly changes it.
- Use Track 1 branch identity for public branch references where branch metadata is available.
- Keep `Rule` and `Derivation` as logical templates; do not move engine semantics back into them.
- Produce G1 tests that lock the chosen public shape before implementation.

## 3. Non-goals

- Do not change Track 1 branch identity persistence. Branch ids remain inspect-only unless G0 explicitly expands scope.
- Do not change authoring payloads, compiled plans, registry state, or adapter state to carry branch ids in this slice unless G0 explicitly selects a larger path.
- Do not implement PyReason per-branch head-bound carrier unless G0 chooses to merge Track 3-post into Track 2.
- Do not add profile flow through Check / Diagnose / Fact Overlay / Why-not shells; E intentionally deferred that UX surface.
- Do not implement multi-interval validity or recurrence semantics.
- Do not alter `release/0.1.x` or `v0.1.0-rc.1`.

## 4. Current Context

### 4.1 Track 1 substrate is available but inspect-only

Track 1 added:

- `Branch([...], id="...")`
- fallback inspect ids `b0`, `b1`, ...
- `fg.rules.inspect(rule_or_derivation)`
- public single-head `Derivation`

However, Track 1 intentionally did **not** propagate branch ids into authoring payloads, compiled plans, registry state, or adapters. The relevant implementation is SDK-local:

- `src/kernel/sdk/dsl/branch.py` validates `Branch.id`.
- `src/kernel/sdk/store.py::_inspect_rule_or_derivation(...)` and `_inspect_where_branches(...)` expose ids.
- `Rule.to_authoring_payload()` and `Derivation.to_authoring_payload()` still lower through `lower_where(...)`, which erases `Branch` wrappers.

Implication: branch-id semantics can be resolved when an SDK `Rule` or `Derivation` object is still in hand. Compiled dicts and service JSON do not currently carry branch ids.

### 4.2 Public SDK call-site currently accepts only SemanticsProfile

`SDKStore.evaluate(...)` currently rejects `mode=` and accepts:

```python
fg.eval.evaluate(deriv, engine="problog", semantics=profile)
```

`src/kernel/sdk/store.py::_resolve_public_semantics(...)` currently requires:

- `semantics` is `SemanticsProfile | None`
- `engine in {"problog", "pyreason"}` when profile is present
- `semantics.engine == engine`

This is the Track 3 / E public/internal naming split:

- public SDK: `engine=` + `semantics=`
- core/application: `mode=` + `semantics_profile=`

### 4.3 SemanticsProfile is the current canonical internal profile

`src/kernel/core/semantics/profile.py` defines one frozen value object:

- `name`
- `engine`
- `version`
- `engine_options`
- `uncertainty_projection`
- `temporal_projection`
- `rule_projection`
- `certainty_projection`
- `output_readback`
- `fallback`

It already validates:

- supported engines: `native`, `souffle`, `problog`, `pyreason`
- `temporal_projection.mode in {"none", "fixed_timesteps", "valid_time_boundaries"}`
- generic `rule_projection` shape but not engine-specific target resolution

Implication: new public `*Semantics` objects can lower to `SemanticsProfile` without changing adapter contracts.

### 4.4 ProbLog adapter consumes positional branch projection

`src/kernel/adapters/problog/rule_ext.py` consumes:

```python
SemanticsProfile.rule_projection.problog = [
    {"target": "branch:0", "kind": "branch_probability", "value": 0.4}
]
```

The resolver materializes branch probabilities as a tuple, defaults omitted branches to `1.0`, and then creates adapter-local `ProbLogRuleExt`.

Implication: `ProbLogSemantics(branch_probabilities={"branch_id": 0.4})` can be lowered at the SDK object boundary by resolving `branch_id -> branch index -> "branch:{index}"`.

### 4.5 PyReason adapter consumes profile but lacks per-branch head-bound carrier

`src/kernel/adapters/pyreason/rule_ext.py` consumes:

- `target="body_atom:{branch}:{atom}", kind="interval_threshold"` into `body_predicate_bounds`
- `target="head:0", kind="interval"` into global `head_bound`
- `target="rule", kind="timestep_delay"` into `timestep_delay`

`src/kernel/adapters/pyreason/where_compile.py` compiles each OR branch into a separate PyReason rule:

```python
rule_name = base_name if len(branches) == 1 else f"{base_name}_b{branch_idx}"
```

That proves per-branch head annotations are mechanically feasible, but the current carrier is still global:

```python
PyReasonRuleExt.head_bound
```

There is no `branch_head_bounds` or equivalent field yet.

Implication: a public `PyReasonSemantics(branch_bounds={...})` cannot be fully implemented using today's adapter carrier unless Track 2 also includes the Track 3-post carrier reshape.

### 4.6 Service and application still speak SemanticsProfile

`DerivationEvaluateRequest.semantics_profile` is typed as `SemanticsProfile | None`.

`service/runtime_v1.py::_resolve_runtime_semantics_profile(...)` accepts top-level JSON:

```json
{
  "engine": "problog",
  "semantics": {
    "name": "...",
    "engine": "problog",
    "rule_projection": { "...": [] }
  }
}
```

and constructs `SemanticsProfile(**dict)`.

Implication: if Track 2 wants service JSON to support lighter shapes, it must decide a service-level discriminant and conversion rule. Otherwise Track 2 can be SDK-only and leave service JSON on the canonical `SemanticsProfile` shape.

### 4.7 Existing tests that Track 2 must preserve or migrate

Current important suites:

- `test_sdk_service_semantics_callsite.py` locks public `engine=` + `semantics=SemanticsProfile` and service top-level `semantics` dict.
- `test_problog_semantics_profile_migration.py` locks ProbLog profile consumption.
- `test_pyreason_semantics_profile_migration.py` locks PyReason profile consumption.
- `test_branch_identity_rule_inspect.py` locks `Branch(id=...)`, fallback ids, and `fg.rules.inspect(...)`.
- SDK `__all__` invariants include `SemanticsProfile`.

Track 2 G1 should add forward-failing tests without weakening these guards unless G0 explicitly chooses a migration.

## 5. Proposed Shape / Open Questions

This draft intentionally leaves the load-bearing choices open for G0.

### 5.1 Q1: Public type names and placement

Options:

- **T1a** `ProbLogSemantics` / `PyReasonSemantics` exported from `kernel.sdk`
- **T1b** `ProbLogProjection` / `PyReasonProjection`
- **T1c** keep `SemanticsProfile` only, no new public types

Draft recommendation: **T1a**. It matches the public `semantics=` kwarg and avoids reusing `*Ext`, which is already the adapter-internal bridge naming convention.

### 5.2 Q2: SemanticsProfile fate

Options:

- **T2a** Keep `SemanticsProfile` public as advanced/canonical; add lighter wrappers as preferred API.
- **T2b** Keep `SemanticsProfile` internal only; remove SDK export.
- **T2c** Deprecate `SemanticsProfile` in docs but keep runtime compatibility.

Draft recommendation: **T2a** for Track 2. Removing or hiding `SemanticsProfile` would churn the just-shipped Track 3 public call-site. A later release can deprecate it after wrappers are proven.

### 5.3 Q3: Lowering boundary for branch-id public semantics

Options:

- **T3a SDK object only**: branch-id wrappers are accepted only when evaluating SDK `Rule` / `Derivation` objects. Compiled dicts and service JSON continue requiring `SemanticsProfile`.
- **T3b Fallback positional for compiled**: compiled evaluate accepts wrapper ids only if keys are fallback ids (`b0`, `b1`, ...).
- **T3c Persist branch ids into compiled payloads**: expand Track 1 P1a boundary.

Draft recommendation: **T3a**. It keeps Track 1's inspect-only boundary intact. Compiled/service paths can keep using `SemanticsProfile` until a later payload design.

### 5.4 Q4: Engine auto-derivation

Options:

- **T4a** Derive `engine` from `ProbLogSemantics` / `PyReasonSemantics` when `engine` is omitted; also derive from `SemanticsProfile.engine`.
- **T4b** Derive only from new wrappers; `SemanticsProfile` still requires explicit `engine`.
- **T4c** Do not auto-derive; require explicit `engine=`.

Draft recommendation: **T4a**. It removes the current duplicate-engine UX while preserving explicit `engine=` as an optional mismatch guard.

Proposed behavior table:

| Inputs | Behavior |
|---|---|
| no `engine`, no `semantics` | default `engine="native"` |
| `engine="X"`, no `semantics` | use `X` |
| no `engine`, semantics object with engine `X` | use `X` |
| `engine="X"`, semantics engine `X` | accept |
| `engine="X"`, semantics engine `Y` | reject mismatch |

### 5.5 Q5: ProbLogSemantics shape

Draft candidate:

```python
ProbLogSemantics(
    name="optional-name",
    branch_probabilities={
        "sensor_path": 0.4,
        "b1": 0.8,
    },
    fallback="reject_unconfigured",
)
```

Open decisions:

- Is `name` required or generated?
- Are fallback ids `b0` / `b1` accepted in public branch maps?
- Do omitted branches default to `1.0` as C currently does?
- Does `branch_probabilities` accept sequence form for compiled/evaluate_compiled, or dict only?

Draft recommendation: optional name, dict only, accept explicit ids and fallback ids, omitted branches default to `1.0`.

### 5.6 Q6: PyReasonSemantics shape and branch_bounds scope

Draft candidate:

```python
PyReasonSemantics(
    name="optional-name",
    timestep_delay=2,
    head_bound=[0.8, 1.0],
    branch_bounds={
        "sensor_path": [0.8, 1.0],
        "obstacle_path": [0.2, 0.8],
    },
    temporal_projection={"mode": "fixed_timesteps", "timesteps": 4},
    uncertainty_projection={},
    fallback="reject_unconfigured",
)
```

Critical options:

- **T6a Lowerable lanes only**: Track 2 supports `timestep_delay`, global `head_bound`, `temporal_projection`, and `uncertainty_projection`; `branch_bounds` is deferred until Track 3-post.
- **T6b Public field now, reject when non-empty**: include `branch_bounds` in constructor but reject with a Track 3-post redirect.
- **T6c Merge Track 3-post**: implement `branch_bounds` end-to-end by adding a PyReason per-branch carrier in Track 2.

Draft recommendation: **T6a or T6c, not T6b**. T6b creates a public field that users cannot use. If we want Track 2 small, choose T6a and document branch_bounds as the next slice. If we want the public shape to match the design direction immediately, choose T6c and accept a larger G2.

### 5.7 Q7: Service JSON shape

Options:

- **T7a Service remains canonical**: top-level `semantics` JSON remains `SemanticsProfile` shape only.
- **T7b Service accepts discriminated light shape**: e.g. `{"type": "pyreason", ...}` or `{"engine": "pyreason", ...}`.
- **T7c Service accepts the same SDK wrapper names via JSON keys**: e.g. `{"pyreason": {...}}`.

Draft recommendation: **T7a** for Track 2 unless a service consumer explicitly needs the lighter shape now. Branch ids are not carried in service derivation payloads, so service branch-id maps would be ambiguous.

### 5.8 Q8: evaluate_compiled behavior

Options:

- **T8a** `evaluate_compiled(..., semantics=ProbLogSemantics/PyReasonSemantics)` rejects because branch ids cannot resolve from compiled dicts.
- **T8b** accepts wrappers only when they do not reference branch ids.
- **T8c** allows fallback positional ids for compiled paths.

Draft recommendation: **T8a** for branch-id wrappers; keep `SemanticsProfile` accepted for compiled paths.

### 5.9 Q9: Inspect helpers

Options:

- **T9a** Extend `fg.eval.inspect_semantics(...)` to support new wrappers and show lowered canonical profile preview.
- **T9b** Add `to_semantics_profile(...)` public method on wrappers.
- **T9c** No new inspect support.

Draft recommendation: **T9a**. It gives users a way to see what the wrapper means without making conversion methods part of the public data model.

### 5.10 Q10: SDK shells

Options:

- **T10a** Keep E behavior: Check / Diagnose / Fact Overlay / Why-not reject `semantics=`.
- **T10b** Allow new wrappers in shells.
- **T10c** Allow only wrappers that can derive engine without profile payloads.

Draft recommendation: **T10a**. Shell profile flow is a separate follow-up from E archive notes.

### 5.11 Q11: Backward compatibility for `semantics=SemanticsProfile`

Options:

- **T11a** Continue accepting `SemanticsProfile`.
- **T11b** Warn/deprecate in docs but continue accepting.
- **T11c** Reject `SemanticsProfile` in public SDK.

Draft recommendation: **T11a**. Track 2 can add wrappers without breaking Track 3's newly published API.

### 5.12 Q12: Where new types live internally

Options:

- **T12a** SDK-local dataclasses in `src/kernel/sdk/semantics.py` that lower to core `SemanticsProfile`.
- **T12b** Core dataclasses in `src/kernel/core/semantics/public.py`.
- **T12c** Put wrappers in existing `core/semantics/profile.py`.

Draft recommendation: **T12a**. These are ergonomic public SDK wrappers, not canonical core protocol objects. Core can remain on `SemanticsProfile`.

## 6. Boundaries And Invariants

- `Rule` and `Derivation` remain logical templates.
- `Branch` remains structure + optional identity only; no confidence/probability/engine kwargs.
- Adapter-specific validation remains at adapter consumption time.
- `SemanticsProfile` remains the canonical internal runtime shape unless G0 decides otherwise.
- C/D adapter consumption must remain green.
- E public `engine=` + `semantics=` call-site remains green.
- Track 1 `Branch(id=...)` and `fg.rules.inspect(...)` remain green.
- Service derivation-level `semantics` remains rejected.
- Shells remain profile-free unless G0 explicitly changes D6/E behavior.
- No profile-derived or wrapper-derived values are stored as facts, registry state, or compiled plan metadata.

## 7. Acceptance

- [ ] G0 locks Q1-Q12 decisions and records them in the audit.
- [ ] G1 red baseline covers selected public wrapper types, engine auto-derivation, mismatch rejection, and preservation guards.
- [ ] New public SDK type exports are reflected in `kernel.sdk.__all__` invariants.
- [ ] `fg.eval.evaluate(...)` behavior matches the locked engine-derivation table.
- [ ] `semantics=SemanticsProfile` compatibility behavior matches G0.
- [ ] Branch-id maps resolve only at boundaries where branch ids are available.
- [ ] `evaluate_compiled(...)` behavior matches G0.
- [ ] Service JSON behavior matches G0.
- [ ] Shell behavior matches G0.
- [ ] C/D/E/Track 1 preservation suites remain green.
- [ ] Release-facing docs no longer present `SemanticsProfile` as the only recommended public authoring shape if wrappers are added.

## 8. Implementation Plan

1. G0: freeze wrapper names, lowering boundary, engine derivation, `SemanticsProfile` compatibility, and PyReason `branch_bounds` scope.
2. G1: add forward-failing SDK tests and preservation guards.
3. G2: implement the selected public wrapper dataclasses, SDK lowering, engine derivation, and inspect support.
4. G3: sync SDK/core/service/adapter docs and update the working design point from proposal to current behavior for Track 2 landed parts.
5. G4: fill outcome/deviations, archive blueprint pair, and prepare publish decision.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/core/semantics/docs/README.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/service/docs/03_runtime_queries_policy.md` if service shape changes
- `docs/references/working/design-points/post-track3-semantics-public-api.zh.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
