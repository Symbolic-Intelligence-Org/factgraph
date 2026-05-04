# Task Blueprint: Diagnose Operation

- Status: draft
- Created: 2026-05-04
- Last Updated: 2026-05-04
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
  - `src/kernel/sdk/` (optional thin shell only; no substrate)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md](../../references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../archive/2026-05-03_check-operation.md)
- Audit Log:
  - [2026-05-04_diagnose-operation.audit.md](./2026-05-04_diagnose-operation.audit.md)

## 1. Problem

Check operation answers whether a requested binding passes, fails, is unsupported, or is invalid. It intentionally does not explain why a failed / unsupported / evidence-unavailable outcome happened.

The redesign line now needs a second explanatory application capability to test whether the engine-extension decisions are usable outside Check. Diagnose is the candidate second consumer: it should inspect a Check-like question and return bounded diagnostic information without becoming full Explain, Why-not, UI projection, or fact-overlay replay.

This blueprint is opened in `draft` to run Step 0. No implementation may start until Step 0 freezes an application DTO shape and this blueprint moves to `scoped`.

## 2. Goals

- Run a source-backed Step 0 for an application-first Diagnose capability.
- Decide whether Diagnose is a sibling of Check, a wrapper around Check, or a narrower post-Check diagnostic operation.
- Freeze an application protocol shape before implementation:
  - request DTO fields;
  - result status vocabulary;
  - diagnostic evidence / payload shape;
  - error and warning policy;
  - engine representability boundaries.
- Use Diagnose as the second explanatory consumer that may pressure `engine-extension-surface-architecture.md` §3.6, without prematurely introducing an engine capability declaration system.
- Fill baseline P1/P2 anchors only where Diagnose actually needs them.

## 3. Non-goals

- No code implementation while status is `draft`.
- No fact overlay, fact replacement, or what-if mutation.
- No broad Explain surface, natural-language narrative, UI tree, or audit report renderer.
- No exhaustive Why-not / counterfactual search.
- No shared branch/atom projection contract unless Step 0 proves Diagnose cannot work without it.
- No request-level `engine_options` unless §6.4 promotion criteria are met.
- No new `EnginePayload`, payload registry, or JSON envelope unless §6.5 migration triggers are met.
- No engine capability declaration matrix unless Diagnose creates concrete second-consumer pressure and the topic doc is updated first.
- No SDK substrate. Any SDK shell, if ever added, must be a thin delegate after application runtime exists.
- No release-base, `v0.1-oss-prep`, `master`, publish, or projection action.

## 4. Current Context

### Application-first baseline

- New runtime capabilities must start in `kernel.application.protocol` and `kernel.application`.
- Check established the current template:
  - intent-only request DTO;
  - runtime side-channel `store` / `registry`;
  - status vocabulary owned by application;
  - engine-native evidence preserved as typed payload;
  - no SDK shell by default.

### Check anchors

- `CheckRequest(plan, binding, engine)` is the closest existing request shape.
- `CheckResult.status` distinguishes:
  - `passed`
  - `failed`
  - `unsupported`
  - `invalid_request`
- Check intentionally has no fail localization, first-failing atom, all matches list, or branch/atom projection.
- Check MVP currently skips lookup-to-`None` evidence misses; engine-extension §6.3 records that future changes touching that path must surface the miss observably.

### Engine-extension anchors

- §6.3 resolved the minimum engine adapter contract:
  - normalized `CandidateSet`;
  - truthful support/provenance references;
  - capability-specific binding extractability;
  - observable evidence miss policy.
- §6.4 resolved engine options placement lightly:
  - plan-level by default;
  - request-level options require the promotion criterion.
- §6.5 resolved payload typing as a working hypothesis:
  - typed Union remains default;
  - migration requires a concrete trigger.
- §3.6 engine capability declaration remains deferred. Diagnose may become the second consumer that grounds it, but that decision must be made explicitly in the topic doc before implementation depends on it.

## 5. Proposed Shape

This section is intentionally provisional until Step 0 completes.

Working hypothesis:

- Diagnose is an application-level sibling capability to Check.
- It accepts a Check-like intent:
  - one `CompiledDerivationPlan`;
  - one normalized binding;
  - one engine;
  - runtime `store` and optional `registry` side channels.
- It returns an application-owned result that separates:
  - request/shape invalidity;
  - engine/request representability;
  - evaluated-but-no-match diagnostics;
  - evidence availability problems;
  - optional bounded diagnostic observations.

Open Step 0 questions:

1. Is Diagnose allowed to call `check_derivation_binding(...)` internally, or must it share lower-level primitives to avoid double evaluation?
2. Is the request DTO exactly Check-shaped, or does Diagnose need a diagnostic target / mode field?
3. What status vocabulary is needed beyond Check's four statuses?
4. Does Diagnose return branch/atom-level observations in MVP, or only coarse diagnostic reasons?
5. For non-native engines, is Diagnose limited to existing candidate payload / provenance envelopes, or does it need a new extraction seam?
6. Does Diagnose trigger §3.6 engine capability declaration, or can MVP remain locally hardcoded like Check?

Step 0 must answer the DTO shape before this blueprint can move to `scoped`.

## 6. Boundaries And Invariants

- **Application-first:** no runtime substrate in `kernel.sdk`.
- **No implementation before Step 0:** this blueprint remains `draft` until request/result DTO shape is frozen.
- **No hidden engine abstraction:** do not introduce §3.6 capability declaration by accident.
- **No semantic flattening:** engine-native payloads remain inspectable and typed per §6.5.
- **No silent evidence miss:** if Diagnose touches evidence lookup, missing payload must be observable per §6.3.
- **No request-level engine options by symmetry:** §6.4 promotion criteria must be met first.
- **No Explain / Why-not scope creep:** Diagnose MVP must stay bounded to source-backed diagnostic classification.

## 7. Acceptance

- [ ] Step 0.A source pass is recorded in the audit log.
- [ ] Step 0.B freezes request/result DTO shape before implementation.
- [ ] Step 0.C freezes algorithm and engine representability boundaries.
- [ ] Step 0.D lifts Step 0 decisions into this blueprint and moves status to `scoped`.
- [ ] Protocol DTO(s) live under `kernel.application.protocol`.
- [ ] Runtime function lives under `kernel.application` and takes runtime dependencies through side-channel parameters.
- [ ] Tests cover protocol shape, status semantics, evidence miss behavior, and engine representability boundaries.
- [ ] Engine-extension topic is updated first if Diagnose promotes §3.6 from deferred.
- [ ] Affected application module docs are updated after implementation.
- [ ] No SDK shell is added unless explicitly kept in scope after Step 0.

## 8. Implementation Plan

1. **Step 0.A — Source pass**
   - Read Check protocol/runtime and archived Check blueprint/audit.
   - Read engine-extension §6.3 / §6.4 / §6.5.
   - Fill only Diagnose-relevant baseline P1/P2 anchors.
   - Record initial structural decisions and open questions in the audit log.

2. **Step 0.B — DTO contract freeze**
   - Freeze request DTO shape.
   - Freeze result DTO shape and status vocabulary.
   - Freeze evidence / diagnostic payload fields.
   - Decide whether Diagnose reuses Check binding validation or defines its own protocol validator.

3. **Step 0.C — Algorithm and engine boundaries**
   - Decide native algorithm source.
   - Decide non-native representability boundaries.
   - Decide evidence miss classification.
   - Decide whether Diagnose triggers §3.6 engine capability declaration.

4. **Step 0.D — Lift and scope**
   - Update this blueprint §5 / §7 / §8 from Step 0 decisions.
   - Move status from `draft` to `scoped` only when DTO shape is answerable.

5. **Implementation steps**
   - Deferred until after Step 0.D.

## 9. Docs To Update

Expected if implementation proceeds:

- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` if §3.6 is promoted or revised
- SDK docs only if a future SDK shell is explicitly scoped

## 10. Outcome / Deviations

Task is in draft. Outcome is pending Step 0 and implementation.
