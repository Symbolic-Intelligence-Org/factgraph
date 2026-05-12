# Task Blueprint: SDK / Service SemanticsProfile Call-Site

- Status: scoped
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

## 5. Scope Freeze Decisions

### 5.1 Locked Public SDK Keyword

| Option | Shape | Trade-off |
| --- | --- | --- |
| E1a | Accept only `semantics=` | Shorter public API; matches "runtime semantics" language. Hard-cuts B's `semantics_profile=` redirect. |
| E1b | Accept only `semantics_profile=` | Mirrors core `Store.evaluate(..., semantics_profile=...)` and class name; more verbose. |
| E1c | Accept both, one alias | More forgiving but creates two public names before v0.1 finalization. |

G0 lock: **E1a**. Use `semantics=` as the public SDK and service field.
Keep `semantics_profile=` core/internal and reject it publicly. Pre-release
allows the clean hard-cut.

### 5.2 Locked SDK Engine Selector

| Option | Shape | Trade-off |
| --- | --- | --- |
| E2a | Add `engine=`, keep `mode=` as alias | Least disruptive; two names remain. |
| E2b | Add `engine=`, hard-reject `mode=` | Clean final API; more test/doc churn. |
| E2c | Keep `mode=`, document `engine=` for later | Undercommits and leaves B's naming note unresolved. |

G0 lock: **E2b** for public SDK evaluation APIs. Service already uses
`engine`. Shells already use `engine`. The project is pre-release and A1-A3
used hard cuts to avoid stale public names.

Core `Store.evaluate(..., mode=...)` remains internal because C/D tests and
adapter internals already use it; E is about public SDK/service call-site.
SDK `evaluate(...)` and `evaluate_compiled(...)` should accept `engine=`
and reject `mode=`.

### 5.3 Locked SDK Export Of `SemanticsProfile`

| Option | Shape | Trade-off |
| --- | --- | --- |
| E3a | Export `SemanticsProfile` from `kernel.sdk` | Users can construct profiles without importing core internals. |
| E3b | Keep core-only import | Public SDK can accept profiles but users import from `kernel.core.semantics`; narrow public namespace preserved. |

G0 lock: **E3a**. Once SDK accepts `semantics=`, the profile type is a
public SDK value object. Exporting the value object keeps the API explicit
without exposing adapter helpers.

### 5.4 Locked Service Payload Placement

| Option | Shape | Trade-off |
| --- | --- | --- |
| E4a | Accept top-level `semantics` only | Preserves A1 rule: runtime engine semantics live at call-site, not derivation body. |
| E4b | Accept `derivation.semantics` only | Keeps profile near derivation payload but violates Track 3 template boundary. |
| E4c | Accept both | More permissive but blurs runtime vs definition semantics. |

G0 lock: **E4a**. Continue rejecting `derivation.semantics` and
`derivation.semantics_profile`; accept top-level `semantics` only.

### 5.5 Locked Service Profile Shape

| Option | Shape | Trade-off |
| --- | --- | --- |
| E5a | Service `semantics` is a dict that constructs `SemanticsProfile(**semantics)`. | Straightforward JSON shape, uses B validation. |
| E5b | Service accepts only a named profile reference. | Requires profile registry not scoped in B/C/D. |
| E5c | Service accepts both inline dict and reference. | Too large for E; introduces registry semantics. |

G0 lock: **E5a**. Inline dict only. Profile registry / named profile
catalogs can be future work.

### 5.6 Locked SDK Shell Profile Flow

| Option | Shape | Trade-off |
| --- | --- | --- |
| E6a | Add `semantics=` to Check / Diagnose / Fact Overlay / Why-not and forward through application requests. | Full public consistency; larger application protocol touch. |
| E6b | Keep shells profile-free and explicitly reject `semantics=` in shells. | Smaller and avoids unclear profile semantics for diagnostic shell behavior. |
| E6c | Add only to Check, defer Diagnose/Overlay/Why-not. | Uneven API; likely confusing. |

G0 lock: **E6b**. Check, Diagnose, Fact Overlay, and Why-not stay
profile-free in E and explicitly reject `semantics=` / `semantics_profile=`.
This is an intentional UX trade-off: `fg.eval.evaluate(...)` accepts
profiles first, while diagnostic shell profile flow remains a future slice
because those shells have their own proof/counterfactual semantics.

### 5.7 Locked Application Protocol Placement

| Option | Shape | Trade-off |
| --- | --- | --- |
| E7a | Add `semantics_profile` to `DerivationEvaluateRequest`. | Matches runtime call-site semantics and avoids plan-level profile storage. |
| E7b | Add `semantics_profile` to `CompiledDerivationPlan`. | Easier per-plan forwarding but violates "Derivation = template" boundary. |
| E7c | Do not change application protocol; SDK calls core store directly. | Bypasses application runtime authority and breaks pattern. |

G0 lock: **E7a**. Application request is the right runtime authority layer.
It should accept `SemanticsProfile | None` and
`evaluate_derivation_plans(...)` should forward it to `Store.evaluate`.

### 5.8 Locked Profile Inspection / Dry-Run

| Option | Shape | Trade-off |
| --- | --- | --- |
| E8a | Expose only `SemanticsProfile` construction and evaluation in E. | Keeps E small. |
| E8b | Add SDK inspection helper wrapping `inspect_semantics_profile`. | Gives users a way to inspect configured lanes; small if SDK export only. |
| E8c | Add service inspection endpoint. | Larger service API; not needed to close call-site. |

G0 lock: **E8b**. Add a small SDK helper,
`fg.eval.inspect_semantics(profile)`, that wraps core
`inspect_semantics_profile`. Defer service inspection endpoints.

### 5.9 Locked Native / Souffle Profile Behavior

Public SDK and service paths reject `semantics=` when `engine` is `native`
or `souffle`. This mirrors current core behavior and avoids silent no-op
profile handling. The rejection is a public-boundary check; native has no
`src/kernel/adapters/native/` package and Souffle remains profile-free.

### 5.10 Locked Rejection Text Contracts

G1 should anchor these public error fragments:

- `evaluate() does not accept mode= in E; use engine=`;
- `evaluate() does not accept semantics_profile= in SDK; use semantics=`;
- `engine='{engine}' does not consume SemanticsProfile`;
- `SemanticsProfile.engine='{profile_engine}' does not match engine='{engine}'`.

Service errors should use equivalent JSON error messages, but they do not
need to duplicate the SDK's exact `evaluate()` prefix.

### 5.11 Locked SDK Test Migration Scope

E includes the SDK public test/docs migration from `mode=` to `engine=`.
This covers `fg.eval.evaluate(...)`, `SDKStore.evaluate(...)`, and public
SDK `evaluate_compiled(...)`. Internal core `Store.evaluate(mode=...)`,
C/D adapter tests, and service-internal mode forwarding stay unchanged.

### 5.12 Locked Application Field Name

The public SDK keyword is `semantics=`, but the application protocol field
is `semantics_profile`. This keeps public call-site language short while
keeping the internal field type-aligned with `SemanticsProfile`.

### 5.13 D1-D12 Locked Decisions

| ID | Decision |
| --- | --- |
| D1 | Public SDK and service keyword is `semantics=`. Public SDK rejects `semantics_profile=`; core/internal code may keep `semantics_profile`. |
| D2 | Public SDK evaluation APIs use `engine=` and hard-reject `mode=`. Core `Store.evaluate(mode=...)` remains internal and unchanged. |
| D3 | Export `SemanticsProfile` from `kernel.sdk`. |
| D4 | Service accepts top-level `semantics` only and rejects derivation-level `semantics` / `semantics_profile`. |
| D5 | Service `semantics` is an inline JSON dict converted with `SemanticsProfile(**semantics)`. No profile registry in E. |
| D6 | Check / Diagnose / Fact Overlay / Why-not shells reject profile kwargs in E. The UX inconsistency is documented and future shell profile flow is deferred. |
| D7 | Add request-level profile support to `DerivationEvaluateRequest`, not to `CompiledDerivationPlan`. |
| D8 | Application protocol field is named `semantics_profile`. |
| D9 | SDK exposes `fg.eval.inspect_semantics(profile)` wrapping core profile inspection; no service inspection endpoint. |
| D10 | Public SDK/service reject profile use with non-consuming engines (`native`, `souffle`) and reject profile/engine mismatch. No silent ignore. |
| D11 | Public rejection anchors for `mode=`, `semantics_profile=`, unsupported engines, and profile/engine mismatch are locked for G1 tests. |
| D12 | G2 migrates public SDK tests/docs from `mode=` to `engine=` while keeping internal core `mode=` call-sites unchanged. |

### 5.14 Resolved G0 Questions Map

| Draft question | Locked decision |
| --- | --- |
| Q1 public SDK keyword | D1 |
| Q2 `engine=` vs `mode=` | D2 + D12 |
| Q3 SDK export | D3 |
| Q4 service placement | D4 |
| Q5 service shape | D5 |
| Q6 SDK shell flow | D6 |
| Q7 application protocol placement | D7 |
| Q8 inspection | D9 |
| Q9 native/souffle profile behavior | D10 |
| Q10 rejection text contracts | D11 |
| Q11 SDK test migration | D12 |
| Q12 application field name | D8 |

## 6. Boundaries And Invariants

- Public `Rule` and `Derivation` constructors remain profile-free.
- Public authoring payloads remain profile-free.
- SDK/service profiles are call-site inputs only.
- Core `Store.evaluate(..., mode=..., semantics_profile=...)` remains the
  adapter consumption entry; E should not duplicate adapter logic in SDK
  or service.
- Public SDK `semantics=` accepts only `SemanticsProfile` instances, not
  raw dicts.
- Service `semantics` accepts JSON dict and constructs
  `SemanticsProfile(**semantics)`.
- Public SDK/service reject profile use for `native` and `souffle`.
- `semantics_profile=` remains core/internal and is rejected publicly.
- `mode=` in public SDK evaluation APIs is a hard reject; use `engine=`.
- `DerivationEvaluateRequest` carries `semantics_profile` at request level;
  `CompiledDerivationPlan` remains profile-free.
- SDK shells stay profile-free in E and reject profile kwargs explicitly.
- `fg.eval.inspect_semantics(profile)` is pure and does not mutate the
  profile.
- Existing core C/D tests remain green.
- Existing B rejection tests must be updated or superseded by E tests.
- No profile-derived data is stored.
- No adapter-specific validation moves into SDK or service; SDK/service only
  check public boundary shape and engine/profile compatibility.

## 7. Acceptance Gates

- Gate 1: G0 locks D1-D12 and records shell UX trade-off explicitly.
- Gate 2: G1 red baseline proves SDK `evaluate(..., semantics=...)` is not
  yet accepted and `engine=` does not yet drive public evaluation.
- Gate 3: G1 guard baseline proves core C/D
  `Store.evaluate(..., mode=..., semantics_profile=...)` paths remain green.
- Gate 4: SDK exports `SemanticsProfile` from `kernel.sdk`.
- Gate 5: SDK exposes `fg.eval.inspect_semantics(profile)` and returns core
  inspection shape without mutation.
- Gate 6: SDK `evaluate(derivation, engine="problog", semantics=profile)`
  drives ProbLog profile branch probabilities.
- Gate 7: SDK `evaluate(derivation, engine="pyreason", semantics=profile)`
  drives PyReason rule/temporal profile behavior.
- Gate 8: SDK `evaluate_compiled(..., engine=..., semantics=profile)` follows
  the same public naming and profile rules as `evaluate(...)`.
- Gate 9: SDK rejects `mode=` with the locked `use engine=` anchor.
- Gate 10: SDK rejects `semantics_profile=` with the locked
  `use semantics=` anchor.
- Gate 11: SDK rejects profile use with `engine="native"` and
  `engine="souffle"` using the locked unsupported-engine anchor.
- Gate 12: SDK rejects profile/engine mismatch with the locked mismatch
  anchor.
- Gate 13: `DerivationEvaluateRequest` gains request-level
  `semantics_profile`; `CompiledDerivationPlan` remains profile-free.
- Gate 14: Application evaluation forwards request-level `semantics_profile`
  to core `Store.evaluate`.
- Gate 15: Service accepts top-level `semantics` dict and constructs
  `SemanticsProfile(**semantics)`.
- Gate 16: Service rejects top-level `semantics_profile`.
- Gate 17: Service rejects `derivation.semantics` and
  `derivation.semantics_profile`.
- Gate 18: Service rejects profile use with unsupported engines and
  profile/engine mismatch.
- Gate 19: Service preserves top-level `engine` and continues rejecting
  top-level `mode`.
- Gate 20: Check / Diagnose / Fact Overlay / Why-not shells reject
  `semantics=` and `semantics_profile=` in E.
- Gate 21: Public SDK tests/docs that previously used `mode=` are migrated
  to `engine=`; internal core `mode=` tests remain unchanged.
- Gate 22: B SDK/service rejection tests are updated or superseded by E
  acceptance/rejection tests.
- Gate 23: C ProbLog and D PyReason profile-consumption focused suites remain
  green.
- Gate 24: A1-A4 public-surface invariants remain green.
- Gate 25: No profile-derived data is stored in facts, registry state, or
  compiled plans.
- Gate 26: Docs no longer say SDK/service profile consumption is deferred to
  E.
- Gate 27: Docs present `engine=` as the final public SDK/service selector
  and document shell profile rejection as an intentional E boundary.

## 8. Implementation Plan

1. G0 scope-freeze: lock D1-D12 across public keyword, naming, SDK export,
   service placement, shell behavior, application protocol placement,
   inspection scope, unsupported-engine handling, rejection anchors, and
   migration scope.
2. G1 red + guard baseline: forward-assert public E behavior plus C/D
   profile-consumption guards.
3. G2 implementation: SDK evaluate/profile forwarding, application request
   profile field, service inline profile construction, SDK `engine=`
   migration, inspect helper, and shell rejection behavior per G0.
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
