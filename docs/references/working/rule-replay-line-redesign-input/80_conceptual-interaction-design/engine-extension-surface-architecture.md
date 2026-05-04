# Engine Extension Surface Architecture

- **Status:** draft
- **Authority:** working conceptual / architectural reference. This topic does **not** define current implementation truth and does **not** itself authorize code changes.
- **Created:** 2026-05-04
- **关联 baseline sections:**
  - `70_codebase-baseline-2026-05-03.md` §P0-2(evaluate flow / engine dispatch)
  - `70_codebase-baseline-2026-05-03.md` §P0-3(Check hook / evidence shape)
- **关联 implemented blueprint:**
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../../../../blueprints/archive/2026-05-03_check-operation.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.audit.md](../../../../blueprints/archive/2026-05-03_check-operation.audit.md)
- **关联 design input:**
  - `check-operation-conceptual-interaction.md` §6.5(engine-respectful evidence)
  - `check-operation-conceptual-interaction.md` §6.9(reserve slot, defer cross-capability abstraction)
  - Check audit Step 0.B B9(`engine_payload`) and Step 0.C C3(per-engine matching boundary)
- **形态:** 这是 architectural reference work, not a blueprint. It may be cited by future blueprints once specific decisions are resolved.

---

## 0. Why This Topic Exists

Check operation shipped the first application-first capability on the redesign branch. Its implementation proved that one common application protocol can support multiple engines **only** when the protocol preserves each engine's native evidence shape and uses explicit representability boundaries.

That unlocked Check, but it also surfaced broader questions that should not be smuggled into a single capability:

- how engine-native payloads should be typed and serialized across capabilities;
- whether engine options belong at plan, request, or capability level;
- where engine-specific extension code should live;
- which adapter behavior is implicit convention versus formal contract;
- how a new engine is supposed to join the system without copying Check-specific glue;
- whether engine capabilities should be declared and consumed instead of hardcoded.

This topic records those questions and iterates toward reusable architectural conventions. It does not commit an implementation.

---

## 1. Scope

### 1.1 In Scope

- Application-facing engine extension architecture.
- Engine-native evidence payload typing and ownership.
- Relationship between common application DTOs and engine-specific extensions.
- Engine capability declaration / discovery patterns.
- How future capabilities should reuse or avoid Check's per-engine seams.

### 1.2 Out Of Scope

- Renaming packages or moving adapter code.
- Adding a new engine.
- Changing Check operation behavior.
- Defining shared branch/atom evidence projection. That remains deferred to `shared-evidence-projection-venue.md` or its successor once a second consumer appears.
- Release, projection, PyPI, or public repo work.

### 1.3 Working Discipline

- Do not flatten PyReason / ProbLog / Souffle differences into a lowest-common-denominator meta object.
- Do not create an abstraction only because Check needed a local seam once.
- Prefer concrete user / implementer scenarios over taxonomy-first architecture.
- If a question requires a second consumer to answer responsibly, mark it deferred instead of forcing a premature convention.

---

## 2. Current Anchors

### 2.1 Baseline Anchors

Baseline §P0-2 records the current evaluate path:

- `evaluate_store(...)` is the core 2x2 dispatch by target kind and engine mode.
- `evaluate_derivation_plans(request, *, store, registry)` is the application evaluate executor.
- `Store.register_engine_evaluator(...)` injects engine evaluators.
- application sees `request.engine` as a string and does not import adapter internals directly.

Baseline §P0-3 records current evidence shape:

- native / souffle can carry witness-bearing `SupportArtifact` data.
- problog / pyreason carry `ProvenanceEnvelope` data.
- support/provenance kinds are semi-structured strings with helper categories, not a full typed capability system.

### 2.2 Check Operation Anchors

Check shipped one concrete application-level pattern:

- common result wrapper: `EvidenceEnvelope`
- engine-specific payload slot: `engine_payload: SupportArtifact | ProvenanceEnvelope`
- native: final bindings from `evaluate_native_where`
- souffle: `SupportArtifact.binding_items`
- problog / pyreason: candidate payload head-var extraction + typed `ProvenanceEnvelope`
- request-level representability gate before non-native evaluation
- `unsupported` means "not representable for this engine/output shape", not "engine failed"

This is a useful precedent, but it is **not automatically the general engine extension architecture**.

---

## 3. Core Questions

### 3.1 Engine-Native Payload DTO Shape

Check MVP uses a typed union:

```python
engine_payload: SupportArtifact | ProvenanceEnvelope
```

Open question: should future capabilities keep this shape or move to a different extension model?

Candidate directions:

| Candidate | Shape | Upside | Risk |
|---|---|---|---|
| A. Typed union | `SupportArtifact | ProvenanceEnvelope | NewEnginePayload` | low ceremony, Python-friendly, matches Check | every new engine/capability may widen unions |
| B. ABC / protocol | `EnginePayload` base + concrete engine payloads | explicit extensibility | boilerplate and premature hierarchy risk |
| C. JSON-compatible envelope | `{engine, payload_type, payload}` | serialization-friendly | weak typing, easy semantic compression |
| D. Hybrid | typed in-process payload + explicit render/serialize function | preserves types and wire compatibility | more moving parts |

Decision: unresolved. §6.2 keeps typed Union as the working hypothesis and defines migration criteria; no `EnginePayload` / protocol / registry abstraction is introduced by this topic yet.

### 3.2 Engine Options Placement

Current state:

- `CompiledDerivationPlan.engine_options` exists and is honored by evaluate.
- Check intentionally did not add request-level `engine_options`.

Open questions:

- When a capability delegates to evaluate, should it only honor plan-level engine options?
- Should capability-specific runtime requests ever carry engine options?
- If yes, how do request-level options compose with plan-level options?
- Which options are engine configuration versus capability interaction?

Decision: resolved lightly in §6.4. Engine options remain plan-level by default; request-level engine options require the §6.4 promotion criterion and are not added for symmetry.

### 3.3 Package / Directory Architecture

Current state:

- Existing adapters live under `kernel.adapters.{souffle,problog,pyreason}`.
- Check runtime imports common store/support types, not adapter modules.

Open questions:

- Is `kernel.adapters.*` still the right home for engine-specific runtime extensions?
- Should there be `kernel.engines.*` as a new extension layer?
- If both exist, what is the difference between adapter, engine extension, and application integration?

Decision: unresolved. §6.2 leaves this as light convention or defer; §6.3 does not decide package / directory architecture.

### 3.4 Engine Adapter Contract

Current state:

- `Store.register_engine_evaluator(...)` registers an evaluator callable.
- Adapter outputs candidates and may populate store-side support/provenance artifacts.
- The artifact-writing side effects are essential for Check, but the contract is mostly implicit.

Open questions:

- What must an engine evaluator produce for application capabilities to consume it?
- Is storing support/provenance artifacts mandatory, optional, or capability-dependent?
- How should missing artifacts be surfaced: skip, warning, runtime error, or degraded projection?
- Which part of the contract belongs to core store, application runtime, or adapter package?

Decision: resolved in §6.3 as a minimum evaluator contract: result shape, evidence reference truthfulness, binding extractability, and observable evidence availability. The resolution does not introduce a new engine abstraction or change Check behavior by itself.

### 3.5 New Engine Onboarding Workflow

Scenario to evaluate later:

> A developer wants to add a new Datalog / ASP / custom probabilistic engine. What files, payload DTOs, evaluator registration, evidence renderer, capability declarations, and tests must they add?

Open questions:

- Where does the new engine payload type live?
- How does the new engine declare support for Check / Diagnose / Explain / other capabilities?
- How does the new engine avoid copying per-capability glue?
- What minimum tests prove it participates correctly?

Decision: unresolved.

### 3.6 Engine Capability Declaration

Check hardcoded representability rules:

- native / souffle can answer body bindings when their output exposes final bindings;
- problog / pyreason MVP only answer payload-representable head-var bindings;
- entity-targeted non-native Check is unsupported until a reliable mapping exists.

Open questions:

- Should these become declarative engine capabilities?
- If yes, are they static per engine, per plan, or per candidate/evidence kind?
- Should a capability ask "can you answer this request?" through an engine capability interface rather than local hardcoded checks?
- How do temporal/probabilistic capabilities express richer support without being flattened?

Decision: unresolved.

---

## 4. Unresolved Items

- Whether the ASP/custom Datalog scenario in §6.1 should become the primary reference scenario or remain one example among several.
- Whether this topic should aim for full resolution or only reusable guardrails.
- Whether the next consumer should be Diagnose / Explain / per-frame diff / another capability.
- Whether engine-extension architecture should remain a reference convention or eventually become its own blueprint.

---

## 5. Interfaces With Future Work

Future blueprints may cite this topic when they need:

- engine-native payload typing decisions;
- engine capability declarations;
- non-native representability gates;
- engine-specific evidence preservation;
- adapter onboarding conventions.

Future work should **not** cite this topic as current behavior until its relevant decisions are explicitly resolved and adopted into a blueprint / module docs.

Potential future consumers:

- Diagnose / failed-check explanation
- per-frame proof diff
- shared branch/atom evidence projection
- audit JSONL replay persistence
- new engine onboarding

---

## 6. Discussion Log

### 6.1 (2026-05-04) Scenario Demo — Add An ASP / Custom Datalog Engine

This is a paper demo, not an implementation plan. It exists to make the six open questions concrete.

#### Scenario

A developer wants to add an engine named `asp`:

- It evaluates the same compiled derivation plans as other engines.
- It can return multiple stable models / answer sets.
- Its native proof payload is not a branch/atom evidence tree; it is closer to an answer-set proof summary:

```python
AspProofPayload(
    answer_set_id="as:01",
    selected_atoms=(...),
    justification_graph={...},
    solver_stats={...},
)
```

The developer wants `asp` to participate in:

- `evaluate_derivation_plans(...)`
- Check operation
- a future Diagnose / Explain capability
- future UI rendering that can show ASP-native proof details without flattening them into native-style support frames

#### Desired Developer Experience

The ideal onboarding should answer:

1. **Where do I put my evaluator?**
   - Current baseline answer: register an engine evaluator through `Store.register_engine_evaluator(...)`.
   - Open architecture question: whether additional engine extension code stays near `kernel.adapters.asp` or moves to a future `kernel.engines.asp`.

2. **What must my evaluator return?**
   - It must return normalized `CandidateSet` objects compatible with application evaluate.
   - It must provide enough binding information for capabilities that need final-result matching.
   - It should store typed proof/provenance payloads somewhere the application runtime can retrieve.

3. **What is my engine-native payload type?**
   - Candidate A: widen `EvidenceEnvelope.engine_payload` to include `AspProofPayload`.
   - Candidate B: make `AspProofPayload` implement a future `EnginePayload` protocol.
   - Candidate C: render it into a JSON envelope.
   - The demo immediately exposes the tension in §3.1: typed Python ergonomics versus extension friction.

4. **How does Check know whether a request is representable?**
   - For head-only binding, `CandidateSet.payload["terms"]` may be enough, as in ProbLog / PyReason.
   - For body-only binding, `asp` must either expose final bindings or declare the request unsupported.
   - If an ASP answer set can prove a body variable only inside a solver-specific proof graph, Check should not guess. It needs an explicit extraction capability or a declared unsupported boundary.

5. **How does Diagnose reuse the same engine work without copying Check glue?**
   - Check only needs "does requested binding match an engine result?"
   - Diagnose may need "why did this binding fail / which constraints ruled it out?"
   - If both capabilities need ASP proof extraction, a local Check-only helper is insufficient. This is where §3.4(adapter contract) and §3.6(capability declaration) become real.

6. **What does UI render?**
   - Common wrapper:
     - engine=`"asp"`
     - support_kind or payload_type identifies ASP proof flavor
     - digest/ref for lookup
   - Native payload:
     - `AspProofPayload`, not flattened into `SupportArtifact`
   - Optional projection:
     - only if a separate shared evidence projection capability can map answer-set proof pieces to branch/atom-ish views without lying

#### Minimal Demo Flow

```text
1. Compile derivation plan
2. Register asp evaluator
3. Evaluate:
   DerivationEvaluateRequest(engine="asp", plans=(plan,))
   -> list[CandidateSet]
   -> store remembers AspProofPayload under support_digest / provenance_digest equivalent

4. Check:
   CheckRequest(plan=plan, binding=(("$doc", "d-1"),), engine="asp")
   -> request-level representability gate:
      - if "$doc" is available from candidate payload terms: evaluate-then-match
      - if requested var exists only inside ASP proof internals: unsupported unless ASP declares safe extractor
   -> CheckResult(status="passed" | "failed" | "unsupported")
   -> EvidenceEnvelope(engine="asp", engine_payload=AspProofPayload, branch_atom_projection=None)

5. Future Diagnose:
   DiagnoseRequest(..., engine="asp")
   -> asks engine capability layer for diagnostic support
   -> may consume AspProofPayload directly
   -> must not pretend ASP proof is a native SupportArtifact unless a projection layer explicitly supports that mapping
```

#### What This Demo Teaches

**1. A fifth engine immediately stresses typed union.**

Check's `SupportArtifact | ProvenanceEnvelope` union is acceptable for MVP, but the ASP demo makes the extension cost visible. Every new engine that has a distinct proof type either widens every consumer union or pushes the system toward an engine payload protocol / registry.

**2. Representability is not just per engine; it is per capability + request shape.**

For Check, head-variable matching might be representable from candidate payload. For Diagnose, the same engine may need a different extractor. A static "asp supports Check" boolean is too coarse.

**3. Engine-native payload preservation is non-negotiable.**

ASP answer-set proofs are not SupportArtifacts. Flattening them would repeat the PyReason/ProbLog mistake identified in Check §6.5.

**4. Adapter contract needs an explicit artifact/provenance obligation.**

If `asp` returns CandidateSet but stores no retrievable proof payload, Check can still pass/fail for head bindings, but evidence-bearing results degrade at the application boundary. The current "silent skip when artifact missing" Check behavior is tolerable for MVP tests, but a real engine onboarding story needs a clearer obligation or warning policy.

**5. `engine_options` placement becomes concrete.**

ASP may need options like solver mode, optimization strategy, or max answer sets. Some options belong in the compiled plan; others may be per-request interaction knobs. The demo shows why §3.2 cannot be answered abstractly.

#### Questions Promoted By The Demo

- Should engine payload extensibility be type-driven (`EnginePayload` protocol) or registry-driven (`engine + payload_type -> renderer/parser`)?
- Should engine evaluators return typed evidence payloads directly, or only store them by digest?
- Should capability-specific representability be declared through a common interface?
- Should missing engine-native payload be a warning, runtime error, or simply a non-match for Check?
- Should engine options have a two-level model: plan-level stable options plus request-level interaction options?

#### Non-Decisions

This scenario does **not** decide:

- to add an ASP engine;
- to create `kernel.engines.*`;
- to replace `kernel.adapters.*`;
- to define `EnginePayload`;
- to change Check's current `EvidenceEnvelope` type;
- to implement branch/atom projection for ASP.

It only gives the topic a concrete reference case for future discussion.

### 6.2 (2026-05-04) Strategic Framing — Readiness And Wave Ordering

This round does **not** resolve any specific §3 question. It catalogs the six §3 questions by readiness so that subsequent §6.X rounds resolve in the right order without any single round silently committing decisions that belong to other questions. Per topic §1.3, "if a question requires a second consumer to answer responsibly, mark it deferred instead of forcing premature convention."

§6.1 surfaced concrete tensions across all six questions through a single ASP onboarding scenario. That demo is enough to triage readiness, but not enough to resolve the questions individually. Resolution happens one question at a time starting from §6.3.

#### Readiness Matrix

| § | Question | Readiness | Action this topic | Reason |
|---|---|---|---|---|
| 3.4 | Engine adapter contract obligation | **Now-ready** | Resolved formally in §6.3 | §6.1.4 directly surfaces what an evaluator must produce / store / signal when artifact is missing. Decidable independently of §3.1 / §3.6 because the contract is about evaluator output shape, not payload typing |
| 3.2 | Engine options placement | **Now-ready, light commit** | Light commit only; no exhaustive option taxonomy | §6.1.5 hints at a two-level model (plan vs request). Check already chose "no request-level"; we can lock the principle without enumerating options |
| 3.1 | Engine-native payload DTO shape | **Working hypothesis** | Keep typed Union as MVP; document migration criterion; do **not** introduce ABC / protocol / registry now | §6.1.1 shows the union widens but does not break. Protocol / registry alternatives all create new abstractions that need a second consumer (or third engine) to validate |
| 3.3 | Package / directory architecture | **Light convention or defer** | At most: state where new engine code lands today; do not move existing code | No concrete pressure from any current capability. ASP demo can register through `kernel.adapters.*` without rename |
| 3.6 | Engine capability declaration | **Defer** | No decision this topic | Requires a second consumer (Diagnose / Explain / Why-not) to validate the declarative shape. Hardcoded Check rules plus future-capability rules are both needed before a declarative form is grounded |
| 3.5 | New engine onboarding workflow | **Derive later** | No procedure template this topic | Workflow falls out of §3.1 / §3.2 / §3.4 once those settle. Writing it earlier is template-first taxonomy, banned by §1.3 |

#### Wave Ordering

**Wave 1 (independent, resolved or hypothesized in this topic):**

1. **§3.4 engine adapter contract** — resolved in §6.3.
2. **§3.2 engine options placement** — light commit, follows §3.4.
3. **§3.1 engine-native payload DTO shape** — working hypothesis lock, follows §3.2.

Independence claim: resolving §3.4 first does not retroactively constrain §3.2 or §3.1, because §3.4 governs evaluator output obligations while §3.2 governs request/plan composition and §3.1 governs typed payload extensibility. Pressure between them only appears if a future engine introduces a payload kind that demands changes simultaneously to all three; that pressure is recorded but not preempted.

**Wave 2 (light or deferred):**

4. **§3.3 package / directory architecture** — light-convention round if pressure exists by then; otherwise deferred until first concrete rename / move requirement.
5. **§3.6 engine capability declaration** — explicitly deferred until a second consumer (Diagnose / Explain / Why-not) appears.
6. **§3.5 new engine onboarding workflow** — derived from Wave 1 once §3.4 / §3.2 / §3.1 are at their committed states.

Wave 2 may slide entirely past this topic. That is acceptable per §1.3: a topic is allowed to resolve only the questions whose pressure has been concretely surfaced.

#### Discipline Check

Three §1.3 rules govern this framing:

- **Don't flatten.** Marking §3.1 as "working hypothesis" instead of "resolve now" prevents typed Union from being either over-committed or replaced by a premature abstraction without a second consumer.
- **Don't taxonomy-first.** Refusing to write §3.5 onboarding workflow before §3.4 / §3.2 / §3.1 settle keeps the workflow derived rather than prescribed.
- **Defer when a question needs a second consumer.** §3.6 stays deferred until Diagnose / Explain / Why-not provides the second concrete pressure that grounds a declarative capability shape.

#### What This Round Decides Vs Does Not Decide

**Decides (this round):**

- Wave ordering: §3.4 → §3.2 → §3.1, then §3.3 / §3.6 / §3.5.
- §3.6 stays deferred this topic.
- §3.5 is derived from Wave 1, not written first.
- §3.1 stays at "working hypothesis" until at least one of: a second engine outside `{native, souffle, problog, pyreason}` lands in tree, or a second capability surfaces a payload-typing requirement Check did not have.

**Does not decide:**

- Any specific answer to §3.1 – §3.6.
- Whether §3.3 will eventually receive a light convention or stay deferred entirely.
- Whether §3.4 obligation will be store-side, runtime-side, or adapter-side.
- Whether §3.2 commit will be pure principle or include any concrete option name.

Subsequent §6.X rounds carry those decisions individually.

#### Cross-References

- §3.4 obligation pressure: §6.1.4 (artifact-writing convention; missing-artifact policy).
- §3.2 placement pressure: §6.1.5 (`engine_options` two-level model hint).
- §3.1 union pressure: §6.1.1 (every new engine widens unions; protocol / registry alternatives carry their own abstraction risk).
- §3.6 deferral basis: topic §1.3 second-consumer rule plus §6.1.2 / §6.1.5 (representability is per-capability, not per-engine; declarative form needs a second capability to ground).
- §3.5 derivation basis: §1.3 anti-taxonomy rule; workflow content depends on §3.4 evaluator obligation + §3.2 options model + §3.1 payload typing.

#### Non-Decisions

This framing round does **not**:

- resolve any §3 question;
- commit §6.4+ to specific question numbers (only §6.3 is committed to §3.4);
- change Check operation behavior, package layout, or any current code;
- foreclose later promotion of §3.6 / §3.3 to "now-ready" if a concrete second consumer surfaces inside this topic's lifetime.

### 6.3 (2026-05-04) Resolve §3.4 — Minimum Engine Adapter Contract

This round resolves §3.4 only. It defines the minimum contract an engine evaluator must satisfy for application capabilities to consume its output responsibly.

It does **not** define a new `EnginePayload` abstraction, capability declaration system, package layout, or onboarding workflow. Those remain governed by §6.2 wave ordering.

#### Contract Layers

The engine adapter contract has four layers:

| Layer | Obligation | Owner | Consumer |
|---|---|---|---|
| Result shape | Return normalized `CandidateSet` objects compatible with application evaluate | adapter | `evaluate_derivation_plans`, accept path, post-evaluate capabilities |
| Evidence reference | Make `support_kind` + `support_digest` truthful about whether retrievable evidence exists | adapter + store | Check / Diagnose / Explain / audit readback |
| Binding extractability | Expose enough final-result binding information for a capability's request shape, or let the capability return `unsupported` | adapter output shape + application runtime | Check-like verify-given operations |
| Evidence availability policy | Surface missing evidence as an observable contract problem, not as silent semantic failure or fake degraded evidence | application runtime | capability result DTO |

The contract is intentionally layered. An engine can participate in evaluate with only the result-shape layer. Evidence-bearing capabilities impose the evidence-reference and binding-extractability layers. A future Diagnose / Explain capability may impose additional extraction obligations, but those are not part of §3.4.

#### 1. Result Shape Is Mandatory For Evaluation

Any registered evaluator must return `list[CandidateSet]` where each candidate is normalized enough for existing application evaluate and accept paths:

- `candidate_kind` remains one of the existing core-supported kinds unless a separate core change explicitly adds another kind.
- `payload` follows the shape expected for that candidate kind.
- `candidate_key` / `candidate_id` semantics remain deterministic and run-scoped as currently defined by core.
- `support_kind` and `support_digest` must be internally consistent with the evidence-reference layer below.

This keeps `Store.register_engine_evaluator(...)` as the current extension point. The contract does not require application code to import adapter modules.

#### 2. Evidence Reference Must Be Truthful

An evaluator has two valid evidence postures:

1. **Evidence-bearing.** The candidate's `support_kind` declares a retrievable support / provenance payload, and `support_digest` resolves through the corresponding typed store lookup.
2. **Explicit no-witness.** The candidate uses an explicit no-witness / degraded support kind such as `engine_no_witness_v1` or legacy `"none"`, making the absence of evidence intentional rather than accidental.

Invalid posture:

- A candidate advertises an evidence-bearing `support_kind` and non-placeholder digest, but the store cannot retrieve the corresponding typed payload.

That invalid posture is a contract violation at the application boundary. It must not be normalized into `branch_atom_projection=None`, because `None` in Check's envelope means "projection intentionally not supplied", not "engine evidence is missing." It must not be flattened into a fake `SupportArtifact`.

#### 3. Binding Extractability Is Capability-Specific

An engine does not have to expose every possible variable binding for every capability. It does have to make the boundary explicit.

For Check-like operations, a requested binding is representable only when the application runtime can extract the relevant final-result values from one of these sources:

- native / support artifact binding rows, e.g. `SupportArtifact.binding_items`;
- candidate head payload positional alignment, e.g. `candidate.payload["terms"]` aligned to `$`-prefixed `head_var_names`;
- a future explicit extractor introduced by a later capability or engine extension decision.

If none of those sources can answer the requested binding shape, the capability returns `unsupported`. It must not infer body-only variables from opaque engine proof internals unless a later extractor contract explicitly says that is valid.

This preserves Check's representability-gated pattern without promoting Check's local helpers into a global capability declaration system.

#### 4. Missing Evidence Must Be Observable

Current Check MVP silently skips candidates whose typed support / provenance lookup returns `None`. That behavior was acceptable as a narrow MVP implementation detail, but it is not the future adapter contract.

For new capabilities, or for any future change that adopts this §6.3 resolution, missing evidence must be observable:

- If an evidence-bearing candidate cannot be dereferenced, the application runtime should attach a warning or error in the capability's own DTO vocabulary.
- If a capability requires evidence to produce a `passed` / explanatory result, it must not return that result with empty or fabricated evidence.
- If missing evidence prevents the capability from answering the request, the result should be classified as unsupported / evidence-unavailable rather than semantic `failed`.

Exact status names remain capability-owned. §3.4 only commits the architectural boundary: evidence lookup miss is not proof of non-satisfaction and not a degraded projection.

Tracked follow-up: any future change to Check's lookup-to-`None` paths in `derivation_check_runtime.py` re-enters this §6.3 decision and should replace MVP silent-skip behavior with observable warning / error signaling before claiming conformance.

#### Ownership Boundary

| Layer | Owns | Does Not Own |
|---|---|---|
| Core store | evaluator registration; typed remember / lookup registries; digest collision invariants | capability status vocabulary; per-engine semantic policy |
| Adapter | producing normalized candidates; writing evidence-bearing payloads when it advertises them; using explicit no-witness kinds when it cannot provide evidence | deciding Check / Diagnose / Explain status semantics |
| Application runtime | request representability gates; selecting typed lookup path; surfacing missing evidence through capability DTOs | importing adapter internals; inventing engine proof structure; flattening native payloads |

This keeps the application layer as the coordination point without turning it into an engine-specific implementation layer.

#### Decision

§3.4 is resolved as follows:

1. The evaluator contract remains `register_engine_evaluator(...) -> list[CandidateSet]`.
2. Evidence-bearing candidates must have truthful `support_kind` + `support_digest` references to typed store payloads.
3. Engines without evidence must say so explicitly through no-witness / degraded support kinds.
4. Binding extractability is per capability and per request shape; unsupported is the correct answer when the binding source is not available.
5. Evidence lookup miss is an observable contract problem, not semantic failure and not degraded projection.
6. Core / adapter / application ownership stays split as above; no new `kernel.engines.*` or `EnginePayload` abstraction is introduced by this decision.

#### Non-Decisions

This round does **not**:

- change Check's current silent-skip MVP behavior;
- define new error codes for Check or any future capability;
- introduce an engine capability declaration matrix;
- decide §3.1 payload typing beyond preserving current typed payloads;
- decide §3.2 engine options placement;
- move adapter code or create `kernel.engines.*`;
- write a new engine onboarding checklist.

### 6.4 (2026-05-04) Resolve §3.2 — Engine Options Placement (Light Commit)

This round resolves §3.2 lightly. It locks the architectural principle for engine options placement without enumerating any specific options or extending current data shapes.

It does **not** introduce a request-level `engine_options` field on any capability DTO, change `CompiledDerivationPlan.engine_options`, or define option semantics for any specific engine.

#### Current State

- `CompiledDerivationPlan.engine_options` exists and is honored by `evaluate_derivation_plans(...)` and downstream adapters.
- Check intentionally added no request-level `engine_options`; `CheckRequest` carries no engine knobs at all (per Check audit Step 0.B B5).
- Adapters consume plan-level options as needed; application capabilities do not surface them as first-class DTO fields.

#### Default Posture

Engine options live at plan level as the default. Concretely:

- A new application capability does **not** add request-level `engine_options` for symmetry with the plan.
- A capability that delegates to evaluate honors plan-level options through the existing executor seam; it does not reinterpret them.
- "Capability needs no request-level options" is the assumed answer until the promotion criterion below is met.

#### Promotion Criterion

A capability may add a request-level engine option only when **all** of the following hold:

1. The option changes the capability's answer shape or coverage, not the underlying evaluator's plan-level semantics.
2. The option cannot be expressed as a different `CompiledDerivationPlan`, because it concerns the capability's interaction with the same plan, not a different plan.
3. A concrete consumer (capability + scenario) demonstrates the option is needed; speculative or symmetry-driven additions do not qualify.

If any of (1)-(3) is unclear or speculative, the capability stays at "plan-level only" until those concerns are resolved.

#### Two-Level Model And Composition Rule (Forward Hypothesis)

§6.1.5 ASP demo hinted at a two-level model:

- **Plan-level (stable):** options that determine the compiled plan's evaluation semantics, e.g., solver mode, optimization strategy, max answer sets when those affect what counts as a candidate.
- **Request-level (interaction):** options that adjust *how* a single capability call answers, without changing what counts as a valid candidate, e.g., a future Diagnose explanation depth, an Explain proof verbosity, a Why-not exhaustiveness toggle.

The assumed composition rule, the day a capability earns request-level options:

- Plan-level options are authoritative for evaluator semantics.
- Request-level options layer on top for capability interaction; they cannot redefine evaluator semantics.
- Conflicts between the two levels surface explicitly: the capability runtime classifies the request as `invalid_request` with an explicit error code, or normalizes through documented rules.

This two-level model and composition rule are **working hypotheses**. They are not committed to any DTO, code path, or convention by this light commit. They become convention only when the first concrete capability triggers §3.2 promotion.

#### Decision

§3.2 is resolved as a light commit:

1. Engine options remain at plan level by default; capability DTOs do not carry symmetric `engine_options` fields.
2. The promotion criterion above governs when a capability earns request-level options.
3. The two-level model and composition rule are working hypotheses; they will be committed to convention only when triggered by a concrete capability.
4. No current data shape, evaluator API, or capability DTO is changed by this resolution.

#### Non-Decisions

This round does **not**:

- enumerate specific engine option names;
- change `CompiledDerivationPlan.engine_options` shape, validation, or semantics;
- add `engine_options` to `CheckRequest`, `DerivationEvaluateRequest`, or any other capability DTO;
- define option composition rules in code or types;
- decide whether engine options eventually become a typed system or remain a string-keyed dict;
- preempt §3.1 typed payload decisions; engine options and engine payloads are independent typing questions.
