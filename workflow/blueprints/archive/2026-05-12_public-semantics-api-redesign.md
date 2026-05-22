# Task Blueprint: Track 2 Public Semantics API Redesign

- Status: implemented
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

## 5. Scope Freeze Decisions

G0 locks Track 2 as a bounded SDK public-wrapper slice. It does **not** absorb the PyReason branch-bound carrier reshape; that remains Track 3-post.

### 5.1 D1: Public type names and placement

Options:

- **T1a** `ProbLogSemantics` / `PyReasonSemantics` exported from `kernel.sdk`
- **T1b** `ProbLogProjection` / `PyReasonProjection`
- **T1c** keep `SemanticsProfile` only, no new public types

Locked: **T1a**. Track 2 introduces `ProbLogSemantics` and `PyReasonSemantics`, exported from `kernel.sdk`. The names match the public `semantics=` kwarg and avoid reusing `*Ext`, which remains adapter-internal bridge naming.

### 5.2 D2: SemanticsProfile fate

Options:

- **T2a** Keep `SemanticsProfile` public as advanced/canonical; add lighter wrappers as preferred API.
- **T2b** Keep `SemanticsProfile` internal only; remove SDK export.
- **T2c** Deprecate `SemanticsProfile` in docs but keep runtime compatibility.

Locked: **T2a**. `SemanticsProfile` remains public as the advanced/canonical shape in Track 2. New wrappers become the preferred ergonomic SDK authoring shape, but Track 3 public compatibility is preserved.

### 5.3 D3: Lowering boundary for branch-id public semantics

Options:

- **T3a SDK object only**: branch-id wrappers are accepted only when evaluating SDK `Rule` / `Derivation` objects. Compiled dicts and service JSON continue requiring `SemanticsProfile`.
- **T3b Fallback positional for compiled**: compiled evaluate accepts wrapper ids only if keys are fallback ids (`b0`, `b1`, ...).
- **T3c Persist branch ids into compiled payloads**: expand Track 1 P1a boundary.

Locked: **T3a**. Branch-id wrappers are SDK-object-only. They are accepted only when evaluating SDK `Rule` / `Derivation` objects, where branch ids are still inspectable. Compiled dicts and service JSON continue requiring `SemanticsProfile`.

### 5.4 D4: Engine auto-derivation

Options:

- **T4a** Derive `engine` from `ProbLogSemantics` / `PyReasonSemantics` when `engine` is omitted; also derive from `SemanticsProfile.engine`.
- **T4b** Derive only from new wrappers; `SemanticsProfile` still requires explicit `engine`.
- **T4c** Do not auto-derive; require explicit `engine=`.

Locked: **T4a**. SDK `evaluate(...)` derives `engine` from `ProbLogSemantics`, `PyReasonSemantics`, and `SemanticsProfile` when `engine=` is omitted. Explicit `engine=` remains accepted as a guard and rejects mismatches.

Proposed behavior table:

| Inputs | Behavior |
|---|---|
| no `engine`, no `semantics` | default `engine="native"` |
| `engine="X"`, no `semantics` | use `X` |
| no `engine`, semantics object with engine `X` | use `X` |
| `engine="X"`, semantics engine `X` | accept |
| `engine="X"`, semantics engine `Y` | reject mismatch |

### 5.5 D5: ProbLogSemantics shape

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

Locked shape:

- `name` is optional. The SDK generates a stable default if omitted.
- `branch_probabilities` is dict-only and maps branch ids to probabilities.
- Keys may be explicit branch ids or fallback ids (`b0`, `b1`, ...).
- Omitted branches default to `1.0`, matching C.
- Sequence form is not accepted in Track 2; compiled/evaluate_compiled paths keep using `SemanticsProfile`.

### 5.6 D6: PyReasonSemantics shape and branch_bounds scope

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

Locked: **T6a**. Track 2 supports only currently lowerable PyReason lanes: `timestep_delay`, global `head_bound`, `temporal_projection`, `uncertainty_projection`, and `fallback`. `branch_bounds` is not a Track 2 constructor field; passing it should fail as an unsupported kwarg / TypeError. Track 3-post owns adding `branch_bounds` plus the PyReason per-branch carrier and compile reshape.

### 5.7 D7: Service JSON shape

Options:

- **T7a Service remains canonical**: top-level `semantics` JSON remains `SemanticsProfile` shape only.
- **T7b Service accepts discriminated light shape**: e.g. `{"type": "pyreason", ...}` or `{"engine": "pyreason", ...}`.
- **T7c Service accepts the same SDK wrapper names via JSON keys**: e.g. `{"pyreason": {...}}`.

Locked: **T7a**. Service top-level `semantics` JSON remains canonical `SemanticsProfile` shape only. Service does not accept `ProbLogSemantics` / `PyReasonSemantics` light JSON in Track 2 because branch ids are not carried in service derivation payloads.

### 5.8 D8: evaluate_compiled behavior

Options:

- **T8a** `evaluate_compiled(..., semantics=ProbLogSemantics/PyReasonSemantics)` rejects because branch ids cannot resolve from compiled dicts.
- **T8b** accepts wrappers only when they do not reference branch ids.
- **T8c** allows fallback positional ids for compiled paths.

Locked: **T8a**. `evaluate_compiled(..., semantics=ProbLogSemantics/PyReasonSemantics)` rejects because branch ids cannot resolve from compiled dicts. `SemanticsProfile` remains accepted for compiled paths.

### 5.9 D9: Inspect helpers

Options:

- **T9a** Extend `fg.eval.inspect_semantics(...)` to support new wrappers and show lowered canonical profile preview.
- **T9b** Add `to_semantics_profile(...)` public method on wrappers.
- **T9c** No new inspect support.

Locked: **T9a**. `fg.eval.inspect_semantics(...)` accepts the new wrappers and returns wrapper metadata plus a lowered canonical profile preview. No public `to_semantics_profile(...)` method is introduced in Track 2.

### 5.10 D10: SDK shells

Options:

- **T10a** Keep E behavior: Check / Diagnose / Fact Overlay / Why-not reject `semantics=`.
- **T10b** Allow new wrappers in shells.
- **T10c** Allow only wrappers that can derive engine without profile payloads.

Locked: **T10a**. Check / Diagnose / Fact Overlay / Why-not shells continue rejecting `semantics=`. Shell profile flow remains a separate follow-up from E archive notes.

### 5.11 D11: Backward compatibility for `semantics=SemanticsProfile`

Options:

- **T11a** Continue accepting `SemanticsProfile`.
- **T11b** Warn/deprecate in docs but continue accepting.
- **T11c** Reject `SemanticsProfile` in public SDK.

Locked: **T11a**. Public SDK `semantics=SemanticsProfile(...)` remains accepted. Track 2 adds wrappers without breaking the Track 3 public call-site.

### 5.12 D12: Where new types live internally

Options:

- **T12a** SDK-local dataclasses in `src/kernel/sdk/semantics.py` that lower to core `SemanticsProfile`.
- **T12b** Core dataclasses in `src/kernel/core/semantics/public.py`.
- **T12c** Put wrappers in existing `core/semantics/profile.py`.

Locked: **T12a**. New wrappers live in `src/kernel/sdk/semantics.py` and lower to core `SemanticsProfile`. Core/application protocol stays typed around `SemanticsProfile`.

### 5.13 D13: Rejection text contracts

G1 tests should lock these anchored substrings:

- `engine='X' does not match semantics.engine='Y'` for wrapper/profile mismatch.
- `evaluate_compiled() requires SemanticsProfile, not ProbLogSemantics/PyReasonSemantics` for compiled wrapper rejection.
- `service semantics accepts SemanticsProfile shape only in Track 2` for service light-shape rejection if a wrapper-shaped JSON is provided.
- `PyReasonSemantics branch_bounds is Track 3-post` for docs and any accidental kwarg-handling path. Constructor-level unsupported kwarg TypeError is acceptable, but docs/tests must not imply branch_bounds is usable in Track 2.

### 5.14 D14: SDK exports and invariant test migration

`kernel.sdk.__all__` gains `ProbLogSemantics` and `PyReasonSemantics`. The SDK `__all__` invariant tests updated in `ef13343a` must be migrated again to include both new public types.

### 5.15 D15: Track 3-post forward commitment

If Track 2 lands with D6/T6a, the archive notes and memory must state that PyReason `branch_bounds` is deferred to Track 3-post and becomes the next available semantics slice after Track 2.

### 5.16 Locked D-Decision Table

| ID | Decision |
|---|---|
| D1 | Add SDK public `ProbLogSemantics` and `PyReasonSemantics`. |
| D2 | Keep `SemanticsProfile` public as advanced/canonical. |
| D3 | Branch-id wrappers are SDK-object-only; compiled/service paths keep `SemanticsProfile`. |
| D4 | Derive engine from wrappers and `SemanticsProfile` when `engine=` is omitted; explicit mismatch rejects. |
| D5 | `ProbLogSemantics`: optional name, dict-only branch probabilities, explicit/fallback branch ids, omitted branches default to `1.0`. |
| D6 | `PyReasonSemantics`: lowerable lanes only; `branch_bounds` is not supported until Track 3-post. |
| D7 | Service JSON remains canonical `SemanticsProfile` shape only. |
| D8 | `evaluate_compiled()` rejects wrappers and still accepts `SemanticsProfile`. |
| D9 | `fg.eval.inspect_semantics(...)` supports wrappers and exposes lowered profile preview. |
| D10 | SDK what-if shells continue rejecting `semantics=`. |
| D11 | `semantics=SemanticsProfile(...)` stays accepted. |
| D12 | Wrappers live in SDK-local `src/kernel/sdk/semantics.py`. |
| D13 | Rejection text anchors are locked for G1. |
| D14 | `kernel.sdk.__all__` and invariant tests add two wrapper types. |
| D15 | Archive/memory record Track 3-post `branch_bounds` as next-up. |

### 5.17 Resolved G0 Questions Map

| Draft question | Locked decision |
|---|---|
| Q1 public type names | D1 |
| Q2 `SemanticsProfile` fate | D2 / D11 |
| Q3 lowering boundary | D3 |
| Q4 engine derivation | D4 |
| Q5 `ProbLogSemantics` shape | D5 |
| Q6 `PyReasonSemantics.branch_bounds` scope | D6 / D15 |
| Q7 service JSON | D7 |
| Q8 `evaluate_compiled` | D8 |
| Q9 inspection helper | D9 |
| Q10 shells | D10 |
| Q11 `SemanticsProfile` compatibility | D11 |
| Q12 type placement | D12 |
| Reviewer Q13 rejection anchors | D13 |
| Reviewer Q14 `__all__` invariants | D14 |
| Reviewer Q15 Track 3-post commitment | D15 |

## 6. Boundaries And Invariants

- `Rule` and `Derivation` remain logical templates.
- `Branch` remains structure + optional identity only; no confidence/probability/engine kwargs.
- Adapter-specific validation remains at adapter consumption time.
- `SemanticsProfile` remains the canonical internal runtime shape and public advanced SDK shape.
- C/D adapter consumption must remain green.
- E public `engine=` + `semantics=` call-site remains green.
- Track 1 `Branch(id=...)` and `fg.rules.inspect(...)` remain green.
- Service derivation-level `semantics` remains rejected.
- Service top-level `semantics` remains canonical `SemanticsProfile` JSON only.
- Shells remain profile-free unless G0 explicitly changes D6/E behavior.
- No profile-derived or wrapper-derived values are stored as facts, registry state, or compiled plan metadata.

## 7. Acceptance

- [x] G0 locks Q1-Q15 decisions and records them in the audit.
- [x] G1 red baseline covers selected public wrapper types, engine auto-derivation, mismatch rejection, and preservation guards.
- [x] New public SDK type exports are reflected in `kernel.sdk.__all__` invariants.
- [x] `fg.eval.evaluate(...)` behavior matches the locked engine-derivation table.
- [x] `semantics=SemanticsProfile` compatibility behavior matches G0.
- [x] Branch-id maps resolve only at SDK object boundaries where branch ids are available.
- [x] `evaluate_compiled(...)` behavior matches G0.
- [x] Service JSON behavior matches G0.
- [x] Shell behavior matches G0.
- [x] C/D/E/Track 1 preservation suites remain green.
- [x] Release-facing docs present wrappers as preferred public authoring shape while keeping `SemanticsProfile` as advanced/canonical.
- [x] `PyReasonSemantics(branch_bounds=...)` is not accepted or documented as usable in Track 2.
- [x] Track 3-post `branch_bounds` follow-up is captured in archive notes and memory.

## 8. Implementation Plan

1. G0: freeze wrapper names, lowering boundary, engine derivation, `SemanticsProfile` compatibility, and PyReason `branch_bounds` scope. Completed with D1-D15.
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

### 10.1 Final Landed Behavior

Track 2 implemented the bounded SDK public-wrapper slice locked at G0:

1. `kernel.sdk.ProbLogSemantics` and `kernel.sdk.PyReasonSemantics` are public SDK exports.
2. `SemanticsProfile` remains public and accepted as the advanced/canonical profile shape.
3. Public wrappers are SDK-local objects in `src/kernel/sdk/semantics.py`; they do not enter application protocol, service JSON, compiled plans, registries, or adapters.
4. `fg.eval.evaluate(...)` can derive `engine=` from `ProbLogSemantics`, `PyReasonSemantics`, or `SemanticsProfile`.
5. Explicit `engine=` remains a mismatch guard and rejects when it conflicts with `semantics.engine`.
6. `ProbLogSemantics(branch_probabilities={...})` accepts dict-only branch probability maps keyed by explicit branch ids or fallback `b0` / `b1` ids. Omitted branches continue to default to `1.0` after lowering.
7. `PyReasonSemantics(...)` supports only currently lowerable lanes: `timestep_delay`, global `head_bound`, `temporal_projection`, `uncertainty_projection`, and `fallback`.
8. `PyReasonSemantics` intentionally has no `branch_bounds` field in Track 2; PyReason per-branch head-bound carrier work remains Track 3-post.
9. Wrapper lowering resolves branch ids only while SDK `Rule` / `Derivation` objects are available, then produces canonical `SemanticsProfile`.
10. `fg.eval.evaluate_compiled(..., semantics=ProbLogSemantics(...))` and `PyReasonSemantics(...)` reject because compiled plans do not carry branch ids; `SemanticsProfile` remains accepted.
11. Service top-level `semantics` JSON remains canonical `SemanticsProfile` shape only. Wrapper-shaped service JSON rejects.
12. `fg.eval.inspect_semantics(...)` accepts wrappers and returns wrapper metadata plus a lowered canonical profile preview.
13. Check / Diagnose / Fact Overlay / Why-not shells remain profile-free and continue rejecting `semantics=`.
14. SDK `__all__` invariants now include the two new public wrapper types.
15. Track 1 and Track 3 public/runtime compatibility remains intact.

### 10.2 Validation

- G1 red + guard baseline: `test_public_semantics_api_redesign.py` added 17 tests with expected 13 errors + 2 failures + 2 guard passes before implementation.
- Track 2 target suite after G2: 17/17 OK.
- Track 1 + B/C/D/E preservation suite: 103/103 OK.
- SDK `__all__` invariant suite after D14 migration: 81/81 OK.
- Combined focused suite: 201/201 OK.
- G3 docs sync grep gates:
  - `ProbLogSemantics` / `PyReasonSemantics` appear as preferred SDK public wrappers.
  - `SemanticsProfile` remains described as advanced/canonical.
  - service and compiled paths remain canonical `SemanticsProfile` surfaces.
  - `branch_bounds` is documented as Track 3-post, not Track 2.
- `git diff --check` clean.

### 10.3 Commit Lineage

G4 closes the following landed lineage:

```text
441650a6 docs(sdk): document public semantics wrappers          ← G3
dff5836e feat(sdk): add public semantics wrappers                ← G2
1eaa69e6 test(sdk): add public semantics api baseline            ← G1
32565b43 docs(blueprints): scope public semantics api redesign   ← G0
3069beb3 docs(blueprints): draft public semantics api redesign   ← draft seed
```

### 10.4 Deviations

1. D14 `__all__` invariant migration was bundled into G2 instead of using a separate mid-cycle cleanup commit. Unlike Track 1's `ef13343a`, this migration was directly part of Track 2's public export change, so keeping it in the implementation commit was cleaner.
2. G2 production code was larger than the draft estimate. The SDK store changes grew because one implementation had to cover the 5-row engine derivation table, wrapper-to-profile lowering for two engines, branch-id lookup, compiled-path rejection, and polymorphic `inspect_semantics(...)`.
3. G3 touched `src/kernel/sdk/docs/01_concepts.en.md` and `src/kernel/sdk/docs/06_what_if_and_proof.en.md` in addition to the core §9 list. The concepts doc needed a durable wrapper concept anchor, and the what-if/proof doc needed to preserve the shell rejection boundary while pointing users to the new wrapper form.

### 10.5 Archive Notes

Track 2 completes the ergonomic public semantics authoring layer that Track 3 deliberately did not absorb. The final public guidance is:

- Use `ProbLogSemantics(...)` or `PyReasonSemantics(...)` for normal SDK authoring.
- Omit `engine=` when it can be derived from `semantics=...`; keep explicit `engine=` only as a guard.
- Use `SemanticsProfile` when callers need the advanced/canonical profile shape, service JSON compatibility, compiled evaluation, or lower-level core/application boundaries.

The remaining post-Track-3 plan has one immediately available slice:

- **Track 3-post**: add PyReason `branch_bounds` by introducing an adapter-local per-branch head-bound carrier and compiling per-branch head annotations. Track 2 intentionally did not add the constructor field, so this future slice can introduce it cleanly once the carrier shape is locked.

No archive or release refs were rewritten. `release/0.1.x` and `v0.1.0-rc.1` remain untouched.
