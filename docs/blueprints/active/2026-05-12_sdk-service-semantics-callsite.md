# Task Blueprint: SDK / Service SemanticsProfile Call-Site

- Status: draft
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/sdk/shells/`
  - `src/service/`
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/store/`
  - `src/kernel/core/semantics/`
  - `src/kernel/adapters/problog/`
  - `src/kernel/adapters/pyreason/`
- Related Docs:
  - [docs/blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md](../archive/2026-05-12_pyreason-semantics-profile-migration.md)
  - [docs/blueprints/archive/2026-05-12_problog-semantics-profile-migration.md](../archive/2026-05-12_problog-semantics-profile-migration.md)
  - [docs/blueprints/archive/2026-05-12_semantics-profile-scaffolding.md](../archive/2026-05-12_semantics-profile-scaffolding.md)
  - [docs/blueprints/archive/2026-05-11_engine-ext-decomposition.md](../archive/2026-05-11_engine-ext-decomposition.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
- Audit Log:
  - [2026-05-12_sdk-service-semantics-callsite.audit.md](./2026-05-12_sdk-service-semantics-callsite.audit.md)

## 1. Problem

Track 3 now has the runtime projection substrate:

- A1-A4 removed or reclassified public rule-definition engine semantics.
- B introduced `kernel.core.semantics.SemanticsProfile`.
- C made ProbLog consume `SemanticsProfile.rule_projection.problog` through
  core `Store.evaluate(..., mode="problog", semantics_profile=profile)`.
- D made PyReason consume `SemanticsProfile.rule_projection.pyreason` and
  `temporal_projection` through
  `Store.evaluate(..., mode="pyreason", semantics_profile=profile)`.

The remaining gap is public access. SDK and service runtime still reject
`semantics=` / `semantics_profile=` with Track 3 / E redirect text, and
SDK still exposes historical `mode=` as the user-facing engine selector.
E should make the adapter consumption visible to users while preserving
the central Track 3 boundary: `Rule` and `Derivation` remain logical
templates; engine semantics stay at the runtime call-site.

## 2. Goals

- Add a durable public SDK call-site for `SemanticsProfile` evaluation.
- Add the corresponding service runtime payload shape.
- Decide and implement the public engine selector naming:
  `engine=` vs historical `mode=`.
- Preserve A1-A4+B+C+D invariants:
  - no profile data on `Rule` / `Derivation`;
  - profile consumed at runtime only;
  - adapter-specific validation remains in adapters;
  - profile data is not written back into facts or registry state.
- Decide how Check / Diagnose / Fact Overlay / Why-not SDK shells interact
  with profiles.
- Update release-facing docs so Track 3 redirects no longer point to E as
  future work.

## 3. Non-goals

- Do not add new ProbLog or PyReason projection semantics beyond C/D.
- Do not redesign `SemanticsProfile` schema fields in E.
- Do not remove `PyReasonRuleExt`, `ProbLogRuleExt`, or internal bridge
  behavior in E.
- Do not add profile consumption to Souffle or native evaluation unless G0
  explicitly scopes validation-only rejection behavior.
- Do not introduce projection result storage or canonical projected facts.
- Do not solve multi-interval / recurrence validity; D explicitly deferred
  that to future uncertainty/data-contract work.
- Do not change candidate output readback semantics except through existing
  adapter behavior.

## 4. Source Audit

### 4.1 Core profile consumption is ready

| Layer | Current state | E relevance |
| --- | --- | --- |
| Core store | `evaluate_store(..., semantics_profile=...)` accepts profiles only for `mode="problog"` and `mode="pyreason"`, and rejects mode/profile engine mismatch. | E can reuse this path; SDK/service need to forward profiles rather than invent adapter-specific logic. |
| Store runtime | `Store.evaluate(..., semantics_profile=...)` and `Store.evaluate_engine(..., semantics_profile=...)` already forward to registered adapters. | Application protocol can carry the profile to this existing core entry. |
| ProbLog adapter | Consumes `SemanticsProfile.rule_projection.problog` and normalizes to `ProbLogRuleExt`. | Public call-site should make this reachable. |
| PyReason adapter | Consumes `rule_projection.pyreason` and `temporal_projection`, normalizing to `PyReasonRuleExt` and run config / EDB active coordinates. | Public call-site should make this reachable. |
| Souffle/native | Do not consume profiles. Core rejects non-Problog/PyReason profile use today. | E must decide whether public SDK/service reject profiles for these engines or allow no-op. A3/C/D precedent favors reject. |

### 4.2 SDK evaluate currently blocks E

`SDKStore.evaluate(...)` rejects both public profile keyword forms before
compilation:

```python
if "semantics" in kwargs:
    raise SDKStoreError("evaluate() does not accept semantics= in B; Track 3 / E owns runtime SemanticsProfile consumption")
if "semantics_profile" in kwargs:
    raise SDKStoreError("evaluate() does not accept semantics_profile= in B; Track 3 / E owns runtime SemanticsProfile consumption")
```

It then accepts `engine_options`, resolves a derivation object or
structured derivation dict into compiled plans, and calls
`_evaluate_compiled_derivation_plans(..., mode=..., engine_options=...)`.

Current compiled-plan conversion:

```python
CompiledDerivationPlan(
    ...,
    engine_ext=resolved_engine_ext,
    engine_options=dict(engine_options or {}),
)
```

There is no public SDK export for `SemanticsProfile` yet; B's guard tests
currently assert that `kernel.sdk.__all__` does not contain it.

### 4.3 Application protocol currently has no profile field

`CompiledDerivationPlan` carries:

- `body_ir`;
- `heads`;
- optional `head_spec`;
- internal `engine_ext`;
- `engine_options`.

`DerivationEvaluateRequest` carries:

- `plans`;
- optional `run_id`;
- `engine`.

B's guard tests currently assert that `DerivationEvaluateRequest` has no
`semantics` / `semantics_profile` field. E must decide whether profile
belongs on the request (call-site) or on each compiled plan. A1 and D
strongly imply request-level placement: profile is runtime projection
configuration, not derivation definition.

### 4.4 SDK shells already use `engine=`

Check, Diagnose, Fact Overlay, and Why-not SDK shells expose
`engine="native"` today, not `mode=`.

Each shell compiles one SDK `Derivation`, converts it to a
`CompiledDerivationPlan`, and builds application protocol requests:

- `sdk_check(...)` -> `build_check_request(plan, binding, engine=engine)`;
- `sdk_diagnose(...)` -> `build_diagnose_request(plan, binding, engine=engine)`;
- `sdk_why_not(...)` -> `WhyNotUniverseRequest(..., engine=engine)`;
- `sdk_check_fact_overlay(...)` -> `FactOverlayCheckRequest(..., engine=engine)`.

They pass `engine_options=None` and do not accept profiles. This is a
surface asymmetry: the high-level shells already use the naming E likely
wants, while `SDKStore.evaluate(...)` still uses `mode=`.

### 4.5 Service runtime blocks both top-level and derivation-level profiles

`evaluate_runtime_derivation(...)` currently rejects:

- top-level `semantics`;
- top-level `semantics_profile`;
- `derivation.semantics`;
- `derivation.semantics_profile`.

The service already uses top-level `engine` and rejects top-level `mode`
and `derivation.mode`, matching A1. It compiles a single structured
derivation payload, resolves internal engine bridges, then calls
`session.store.evaluate(..., mode=mode, engine_ext=runtime_engine_ext)`.

This creates a clean E design choice: accept runtime profile at the
top-level call-site and continue rejecting derivation-level profile fields.

### 4.6 Documentation state

Release-facing docs currently say:

- core `Store.evaluate(..., mode="problog", semantics_profile=...)` and
  `Store.evaluate(..., mode="pyreason", semantics_profile=...)` work;
- SDK `evaluate(..., semantics=...)` / `semantics_profile=...` still
  reject until E;
- service top-level / derivation-level `semantics` / `semantics_profile`
  still reject until E;
- B recorded a forward naming note: future public runtime call-site should
  prefer `engine=` over historical SDK `mode=`.

G3 will need to convert "E future" wording into the final public contract.

## 5. Open G0 Questions

### Q1. Public SDK keyword: `semantics=` vs `semantics_profile=`

| Option | Shape | Trade-off |
| --- | --- | --- |
| E1a | Accept only `semantics=` | Shorter public API; matches "runtime semantics" language. Hard-cuts B's `semantics_profile=` redirect. |
| E1b | Accept only `semantics_profile=` | Mirrors core `Store.evaluate(..., semantics_profile=...)` and class name; more verbose. |
| E1c | Accept both, one alias | More forgiving but creates two public names before v0.1 finalization. |

Recommendation for G0: **E1a**. Use `semantics=` as the public SDK and
service field. Keep `semantics_profile=` core/internal and either reject
it publicly or reserve it as implementation detail. Pre-release allows the
clean hard-cut.

### Q2. SDK engine selector: `engine=` vs `mode=`

| Option | Shape | Trade-off |
| --- | --- | --- |
| E2a | Add `engine=`, keep `mode=` as alias | Least disruptive; two names remain. |
| E2b | Add `engine=`, hard-reject `mode=` | Clean final API; more test/doc churn. |
| E2c | Keep `mode=`, document `engine=` for later | Undercommits and leaves B's naming note unresolved. |

Recommendation for G0: **E2b** for public SDK evaluate. Service already
uses `engine`. Shells already use `engine`. The project is pre-release and
A1-A3 used hard cuts to avoid stale public names.

Open nuance: core `Store.evaluate(..., mode=...)` can remain internal
because C/D tests and adapter internals already use it; E is about public
SDK/service call-site.

### Q3. SDK export of `SemanticsProfile`

| Option | Shape | Trade-off |
| --- | --- | --- |
| E3a | Export `SemanticsProfile` from `kernel.sdk` | Users can construct profiles without importing core internals. |
| E3b | Keep core-only import | Public SDK can accept profiles but users import from `kernel.core.semantics`; narrow public namespace preserved. |

Recommendation for G0: **E3a**. Once SDK accepts `semantics=`, the profile
type is a public SDK value object. Exporting only the value object, not
core helper internals, keeps the API explicit.

### Q4. Service payload placement

| Option | Shape | Trade-off |
| --- | --- | --- |
| E4a | Accept top-level `semantics` only | Preserves A1 rule: runtime engine semantics live at call-site, not derivation body. |
| E4b | Accept `derivation.semantics` only | Keeps profile near derivation payload but violates Track 3 template boundary. |
| E4c | Accept both | More permissive but blurs runtime vs definition semantics. |

Recommendation for G0: **E4a**. Continue rejecting
`derivation.semantics` / `derivation.semantics_profile`; accept top-level
`semantics` only.

### Q5. Service profile shape

| Option | Shape | Trade-off |
| --- | --- | --- |
| E5a | Service `semantics` is a dict that constructs `SemanticsProfile(**semantics)`. | Straightforward JSON shape, uses B validation. |
| E5b | Service accepts only a named profile reference. | Requires profile registry not scoped in B/C/D. |
| E5c | Service accepts both inline dict and reference. | Too large for E; introduces registry semantics. |

Recommendation for G0: **E5a**. Inline dict only. Profile registry /
named profile catalogs can be future work.

### Q6. SDK shell profile flow

| Option | Shape | Trade-off |
| --- | --- | --- |
| E6a | Add `semantics=` to Check / Diagnose / Fact Overlay / Why-not and forward through application requests. | Full public consistency; larger application protocol touch. |
| E6b | Keep shells profile-free and explicitly reject `semantics=` in shells. | Smaller and avoids unclear profile semantics for diagnostic shell behavior. |
| E6c | Add only to Check, defer Diagnose/Overlay/Why-not. | Uneven API; likely confusing. |

Recommendation for G0: **E6b** unless source audit finds a concrete
shell path that needs profiles now. The shells are application-level
diagnostic tools with engine support boundaries of their own; E can close
public evaluation first and document shell profile flow as future.

### Q7. Application protocol placement

| Option | Shape | Trade-off |
| --- | --- | --- |
| E7a | Add `semantics_profile` to `DerivationEvaluateRequest`. | Matches runtime call-site semantics and avoids plan-level profile storage. |
| E7b | Add `semantics_profile` to `CompiledDerivationPlan`. | Easier per-plan forwarding but violates "Derivation = template" boundary. |
| E7c | Do not change application protocol; SDK calls core store directly. | Bypasses application runtime authority and breaks pattern. |

Recommendation for G0: **E7a**. Application request is the right runtime
authority layer. It should accept `SemanticsProfile | None` and
`evaluate_derivation_plans(...)` should forward it to `Store.evaluate`.

### Q8. Profile inspection / dry-run

| Option | Shape | Trade-off |
| --- | --- | --- |
| E8a | Expose only `SemanticsProfile` construction and evaluation in E. | Keeps E small. |
| E8b | Add SDK inspection helper wrapping `inspect_semantics_profile`. | Gives users a way to inspect configured lanes; small if SDK export only. |
| E8c | Add service inspection endpoint. | Larger service API; not needed to close call-site. |

Recommendation for G0: **E8b** if limited to SDK re-export or a simple
`fg.eval.inspect_semantics(profile)` helper; defer service endpoint.

## 6. Draft Boundaries And Invariants

- Public `Rule` and `Derivation` constructors remain profile-free.
- Public authoring payloads remain profile-free.
- SDK/service profiles are call-site inputs only.
- Core `Store.evaluate(..., mode=..., semantics_profile=...)` remains the
  adapter consumption entry; E should not duplicate adapter logic in SDK
  or service.
- Public SDK `semantics=` accepts only `SemanticsProfile` instances, not
  raw dicts, unless G0 chooses otherwise.
- Service `semantics` accepts JSON dict and constructs
  `SemanticsProfile(**semantics)`.
- Public SDK/service reject profile use for `native` and `souffle` unless
  G0 explicitly scopes no-op semantics. Current core behavior rejects.
- `semantics_profile=` remains core/internal unless G0 accepts it as a
  public alias.
- `mode=` in SDK evaluate is either a hard reject or an alias; G0 must lock
  which.
- Existing core C/D tests remain green.
- Existing B rejection tests must be updated or superseded by E tests.
- No profile-derived data is stored.

## 7. Draft Acceptance Gates

- G0 locks Q1-Q8 and records the public naming decision.
- G1 red baseline proves SDK still rejects `semantics=` /
  `semantics_profile=` and still uses `mode=`.
- G1 guard baseline proves core ProbLog and PyReason profile consumption
  remains green.
- SDK exports `SemanticsProfile` if G0 chooses E3a.
- SDK `evaluate(derivation, engine="problog", semantics=profile)` drives
  ProbLog profile branch probabilities.
- SDK `evaluate(derivation, engine="pyreason", semantics=profile)` drives
  PyReason rule/temporal profile behavior.
- SDK rejects profile/engine mismatch with stable error text.
- SDK rejects profile use with `engine="native"` and `engine="souffle"` if
  G0 chooses strict adapter support.
- SDK `mode=` behavior matches G0 (hard reject or alias) with tests.
- SDK `semantics_profile=` behavior matches G0 (hard reject or alias) with
  tests.
- Application `DerivationEvaluateRequest` carries request-level profile if
  G0 chooses E7a.
- Service accepts top-level `semantics` and constructs a `SemanticsProfile`.
- Service rejects `derivation.semantics` and
  `derivation.semantics_profile`.
- Service rejects profile/engine mismatch with stable error shape.
- Service preserves top-level `engine` and continues rejecting top-level
  `mode`.
- Check / Diagnose / Fact Overlay / Why-not shell profile behavior matches
  G0.
- Docs no longer say SDK/service profile consumption is deferred to E.
- Docs present `engine=` as the final public SDK/service selector if G0
  chooses E2b.
- A1-A4+B+C+D focused suite remains green.

## 8. Draft Implementation Plan

1. G0 scope-freeze: lock public keyword, naming, SDK export, service
   placement, shell behavior, application protocol placement, and
   inspection scope.
2. G1 red + guard baseline: forward-assert public E behavior plus C/D
   profile-consumption guards.
3. G2 implementation: SDK evaluate/profile forwarding, application request
   profile field, service inline profile construction, and shell behavior
   per G0.
4. G3 docs sync: SDK/service/core semantics docs, adapter docs, user guide,
   and transmission reference.
5. G4 close-out: fill Outcome / Deviations, archive blueprint pair, update
   archive inventory, then publish + milestone after review.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/sdk/docs/06_what_if_and_proof.en.md` if shell behavior changes
- `src/kernel/core/semantics/docs/README.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `src/service/docs/04_rules_registry.md` if service payload examples change
- `docs/references/working/design-points/possibility-probability-transmission.zh.md`

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Validation:
- Commit lineage:
- Deviations:
- Archive notes:
