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

Decision: unresolved.

### 3.2 Engine Options Placement

Current state:

- `CompiledDerivationPlan.engine_options` exists and is honored by evaluate.
- Check intentionally did not add request-level `engine_options`.

Open questions:

- When a capability delegates to evaluate, should it only honor plan-level engine options?
- Should capability-specific runtime requests ever carry engine options?
- If yes, how do request-level options compose with plan-level options?
- Which options are engine configuration versus capability interaction?

Decision: unresolved.

### 3.3 Package / Directory Architecture

Current state:

- Existing adapters live under `kernel.adapters.{souffle,problog,pyreason}`.
- Check runtime imports common store/support types, not adapter modules.

Open questions:

- Is `kernel.adapters.*` still the right home for engine-specific runtime extensions?
- Should there be `kernel.engines.*` as a new extension layer?
- If both exist, what is the difference between adapter, engine extension, and application integration?

Decision: unresolved.

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

Decision: unresolved.

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

- First concrete scenario to analyze.
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

### 6.1 (pending) First Scenario

Pending user-provided scenario. Good candidates:

- "Add a new engine" walkthrough.
- "Diagnose capability wants to reuse engine evidence" walkthrough.
- "A UI wants to render engine-specific evidence without flattening" walkthrough.

