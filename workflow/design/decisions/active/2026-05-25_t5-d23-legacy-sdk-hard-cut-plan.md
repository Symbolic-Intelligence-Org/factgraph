# D23 Decision: T5 Legacy SDK Hard-Cut Plan

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks T5 legacy surface removal targets, blast-radius inventory, and implementation ordering for the public hard-cut.
- Implementation Anchors: T5.7 service/OpenAPI migration feat `41f7e60f`, docs migration feat `63718d09`, legacy hard-cut feat `62279515`, archive `8173c715`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q10, Q13, F3, F4, F5, F12, and section 6 C61-C63 and C71 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.4, 4.5, 4.7, and 4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.1, 4.2, 4.7, and 4.9.
  - D18 `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md` sections 4.1-4.8.
  - D20 `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md` sections 4.7 and 7.3.
  - D22 `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md` sections 4.1-4.6.
  - Shipped `src/factgraph/sdk/store.py:518-545`, `:1168-1288`, `:2211-2384`, and `:2392-2410`.
  - Shipped `src/factgraph/sdk/shells/why_not.py:1-119`, `src/factgraph/application/protocol/derivation_why_not.py:1-346`, and `src/factgraph/application/why_not_runtime.py:1-190`.
  - Shipped service routes and docs `src/service/app_v1.py:212-219`, `src/service/runtime_v1.py:920-1045`, `docs/api/openapi.yaml:601-621`, and `src/service/docs/03_runtime_queries_policy.md:1001-1238`.
- Outputs / Downstream:
  - D24 T1.3 final SDK `Rule` flip.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and hard-cut implementation blueprint(s).
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16-D22 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

D18 locks the public return-shape hard-cut: `fg.eval.evaluate(...) -> EvaluateResult`, with no `evaluate_v2`, `result_shape=`, or long-lived CandidateSet compatibility mode. D22 locks why-not as folded into failed `Explanation`, not a migrated public `.eval.why_not(...)`.

That leaves a broad shipped surface still present:

- SDK `evaluate(...)` returns `list[CandidateSet]`;
- SDK `accept(...)` and `accept_many(...)` consume `CandidateSet`;
- SDK direct `check(...)`, `diagnose(...)`, and `why_not(...)` return application DTOs;
- `fg.what_if.*` mirrors check / diagnose / why-not and fact-overlay shells;
- `evaluate(...)` still accepts `engine_options=` and `registry=`;
- service v1 exposes `inferences/evaluate` returning CandidateSet and `inferences/accept` round-tripping candidates;
- docs and examples teach CandidateSet / accept / what-if / why-not workflows.

D23 decides the target hard-cut plan and required inventory. It does not implement the cut and does not choose final SDK `Rule` naming; D24 owns naming.

## 2. Scope

This decision locks:

- which legacy SDK / application / service surfaces are T5 hard-cut targets;
- service-route blast-radius inventory requirements;
- application protocol DTO retention versus public export policy;
- implementation ordering constraints for DTO foundation, evaluate flip, legacy shell deletion, docs, and service routes;
- whether intermediate mixed states may exist locally;
- public docs migration direction;
- test and grep gates that Stage 3 / implementation blueprints must include.

## 3. Non-Scope

This decision does not lock:

- final SDK public `Rule` naming; D24 owns it;
- exact code deletion commits or file-level diffs; implementation blueprints own them;
- `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, or `Explanation` fields; D17 and D20 own them;
- digest formulas; D19 owns them;
- `row.close()` and manual explain closed-head gate; D21 owns them;
- why-not product disposition; D22 owns it;
- evaluate/explain semantics mismatch behavior; D25 owns it;
- C73-C78 semantics adapter implementation; D26 owns it;
- database/session storage redesign beyond service route payload changes;
- future evidence-tree internal schema implementation.

## 4. Decision

### 4.1 T5 hard-cuts legacy public evaluation surfaces

D23 locks the target public API after the T5 Core implementation:

- `fg.eval.evaluate(...)` returns `EvaluateResult`;
- `fg.eval.evaluate(...)` does not return `list[CandidateSet]`;
- public docs and examples do not teach `CandidateSet` as the user-facing evaluation result;
- `CandidateSet` remains importable only from core/application internals for runtime tests and adapter substrate, not as an SDK result DTO.

The following public SDK surfaces are hard-cut targets:

| Surface | Target state | Owner |
|---|---|---|
| `fg.eval.accept(...)` | removed from public eval namespace | D23 / implementation |
| `fg.eval.accept_many(...)` | removed from public eval namespace | D23 / implementation |
| `SDKStore.accept(...)` as public CandidateSet accept shell | removed or made non-public/internal; no docs | D23 / implementation |
| `SDKStore.accept_many(...)` as public CandidateSet accept shell | removed or made non-public/internal; no docs | D23 / implementation |
| `SDKStore.check(...)` | removed as public shell; functionality folded into `fg.eval.explain(...)` | D23, D20 |
| `SDKStore.diagnose(...)` | removed as public shell; no public DiagnoseResult path | D23, D20 |
| `SDKStore.why_not(...)` | removed as public shell | D23, D22 |
| `fg.what_if.check(...)` | removed as public shell | D23 |
| `fg.what_if.diagnose(...)` | removed as public shell | D23 |
| `fg.what_if.why_not(...)` | removed as public shell | D23, D22 |
| `fg.what_if.fact_overlay.*` | hard-cut target unless Stage 3 isolates it as a non-T5 future track | D23 |
| `fg.what_if.rule.*` | hard-cut target unless Stage 3 isolates it as a non-T5 future track | D23 |

Stage 3 may split the implementation into more than one slice, but the final T5 public surface must not leave these as user-facing compatibility paths.

### 4.2 `engine_options=` and `registry=` are rejected at public evaluate and old shell boundaries

D18 already locks public `evaluate(...)` parameter cleanup. D23 extends the hard-cut target to old shells:

- public `evaluate(..., engine_options=...)` raises `SDKStoreError`;
- public `evaluate(..., registry=...)` raises `SDKStoreError`;
- old `check`, `diagnose`, and `why_not` shells do not survive as the way to pass `registry=`;
- service routes must not preserve `registry` / `engine_options` escape hatches under a new payload name.

Internal runtime functions may still accept registry-like resolver state if implementation needs it. The hard-cut is about public SDK/service call shape, not every private helper signature.

### 4.3 Legacy `Inference` and derivation dict inputs must not preserve old return shape

D18 rejects input-type-dependent return shapes. D23 makes the legacy blast radius explicit:

- legacy SDK `Inference` input to `evaluate(...)` must return `EvaluateResult`, not `list[CandidateSet]`;
- structured derivation dict input to `evaluate(...)` must return `EvaluateResult`, not `list[CandidateSet]`;
- application RuleExpr / head Rule input must also return `EvaluateResult`;
- no input class may keep CandidateSet output as a compatibility lane.

D24 may rename public SDK `Rule` / `ApplicationRule` aliases, but D23's return-shape hard-cut applies regardless of final naming.

### 4.4 Application protocol DTOs can remain internal if they are needed by private runtime

D23 distinguishes public SDK surface from internal application substrate.

Application protocol DTOs may remain temporarily or permanently internal when they serve runtime/test needs:

- `CandidateSet`;
- `CheckResult`;
- `DiagnoseResult`;
- `WhyNotUniverseRequest`;
- `WhyNotUniverseResult`;
- `WhyNotRedRow`;
- `WhyNotRowDiagnostic`;
- `WhyNotAtomLocator`;
- `SupportArtifact` / `EvidenceEnvelope` / provenance carriers.

But they must not be re-exported or documented as the T5 public result/evidence API unless a later decision explicitly adopts them. D17/D20 public DTOs become the T5 surface.

If implementation removes internal DTOs entirely, that is allowed only after replacing runtime/test users. D23 does not require internal deletion for adoption; it requires public hard-cut and docs cleanup.

### 4.5 Service route blast-radius inventory is mandatory before implementation

D16 requires service-route blast-radius review before hard-cut. D23 locks the inventory.

Before any implementation slice changes public return shape or deletes old shells, the blueprint must grep at least:

```text
src/service
src/agent
docs/api/openapi.yaml
src/service/docs
src/factgraph/sdk/docs
docs/official
examples
tests
```

for:

```text
CandidateSet
inferences/evaluate
inferences/accept
accept_many
accept(
fg.check
fg.diagnose
why_not
what_if
engine_options
registry=
SDKStore.check
SDKStore.diagnose
SDKStore.why_not
```

Each hit must be classified into exactly one bucket:

1. **T5 hard-cut update**: must change in the T5 implementation;
2. **internal runtime preservation**: may keep old substrate privately;
3. **future-track deferred**: e.g. non-T5 what-if/fact-overlay work explicitly deferred by Stage 3;
4. **unrelated / false positive**: documented and ignored.

If service routes still expose CandidateSet/accept round-trip after the hard-cut implementation, the T5 implementation is incomplete.

### 4.6 HTTP service target state follows `EvaluateResult`, not CandidateSet round-trip

Service v1 currently has:

- `POST /v1/runtime/sessions/{session_id}/inferences/evaluate`;
- `POST /v1/runtime/sessions/{session_id}/inferences/accept`.

After the T5 hard-cut:

- `inferences/evaluate` must return a service representation of `EvaluateResult`;
- `inferences/evaluate` must not describe or require CandidateSet round-trip for normal use;
- `inferences/accept` is a removal or redesign target because public evaluation no longer returns CandidateSet for users to accept;
- OpenAPI must stop summarizing inference evaluate as "return a CandidateSet";
- service docs must stop instructing clients to echo complete candidate payloads as the main inference flow.

D23 does not decide whether service keeps a compatibility endpoint under a deprecated path during a local implementation split. It only locks the final T5 pushed state: no public service route depends on CandidateSet as the user result object.

### 4.7 Intermediate mixed states may exist locally but must not be pushed as a milestone

The implementation may need multiple local commits:

1. define D17/D20 DTOs and converters;
2. build private CandidateSet-to-EvaluateResult conversion;
3. flip SDK `evaluate(...)`;
4. update service routes;
5. delete or hide old shells;
6. update docs/examples/tests.

Mixed states are allowed only inside an implementation branch before closure. A scoped/archive/push milestone must not expose:

- `evaluate(...) -> EvaluateResult` while public `accept(CandidateSet)` is still documented as normal;
- `.eval.why_not` or direct `why_not` as a recommended T5 evidence path;
- service `inferences/evaluate` returning CandidateSet while SDK docs advertise EvaluateResult;
- D24-inconsistent SDK naming in final docs.

Stage 3 may choose one L-class implementation slice or several M-class slices. If split, each intermediate slice must be clearly marked local-only until the public surface is coherent.

### 4.8 Docs migration waits for D24 naming but inventory starts before D24

D16 locks that concrete SDK public names appear after D24 reviewed clean. D23 therefore separates two activities:

- **Inventory now**: identify all docs/examples/OpenAPI references to legacy surfaces;
- **Final rewrite later**: update user-facing text after D24 decides final SDK `Rule` naming.

D23 does not block D24. It requires the Stage 3 synthesis to place final docs migration after D24 or in a slice that consumes D24.

Docs must remove or rewrite:

- CandidateSet as public result object;
- `accept` / `accept_many` as normal inference consumption;
- `check` / `diagnose` direct SDK methods as public evidence entrypoints;
- `why_not` / `what_if.why_not` as public evidence entrypoints;
- `engine_options=` and `registry=` call-site examples.

## 5. Rejected Alternatives

### Option A: Keep old shells as deprecated aliases for one release

- **Rejected because**: D18 hard-cuts the alpha public API and the project has repeatedly favored narrow public surfaces over long-lived compatibility paths.

### Option B: Flip only RuleExpr evaluation and leave legacy `Inference` returning CandidateSet

- **Rejected because**: D18 rejects input-type-dependent return shape. Users should not have to know which input family returns which result object.

### Option C: Keep service routes CandidateSet-based while SDK flips

- **Rejected because**: D16 requires service blast-radius handling before the hard-cut is complete. SDK/service divergence would create a split public contract.

### Option D: Delete all application protocol legacy DTOs immediately

- **Rejected because**: runtime and tests may still need internal carriers during conversion. Public hard-cut does not require immediate internal DTO deletion.

### Option E: Leave `accept` public as a write convenience for EvaluateRows

- **Rejected because**: D17/D18 shift evaluation to result/explain; accepting inferred facts into the ledger is a separate product decision and not part of T5 Core's narrow result/evidence surface.

### Option F: Keep `what_if` as an advanced namespace

- **Rejected because**: shipped `what_if` teaches check/diagnose/why-not/fact-overlay shells that conflict with D20/D22's explanation-centered target. A future what-if redesign needs a separate track.

### Option G: Hide old docs but keep public methods callable

- **Rejected because**: unadvertised public methods still become compatibility obligations and still affect users through introspection/autocomplete.

### Option H: Defer service routes to after T5

- **Rejected because**: D16 explicitly makes service-route blast radius mandatory before hard-cut completion.

## 6. Supporting Evidence

| Evidence | Source | D23 use |
|---|---|---|
| D18 hard-cuts `evaluate(...) -> EvaluateResult` and rejects parallel return-shape surfaces. | D18 sections 4.1-4.8 | Sets public transition target |
| D22 classifies shipped why-not as D23 legacy hard-cut target. | D22 sections 4.4 and 7.3 | Adds why-not to deletion/inventory scope |
| SDK store still exposes what-if direct methods. | `sdk/store.py:518-545` | Identifies namespace blast radius |
| SDK store still exposes `check`, `diagnose`, and `why_not`. | `sdk/store.py:1168-1288` | Identifies legacy evidence shells |
| SDK `evaluate` still returns `list[CandidateSet]` and accepts `registry` / `engine_options`. | `sdk/store.py:2211-2384` | Identifies return-shape and param cleanup work |
| SDK `accept` still consumes CandidateSet. | `sdk/store.py:2392-2410` | Identifies accept hard-cut target |
| Why-not protocol/runtime/shell remains shipped. | `derivation_why_not.py`, `why_not_runtime.py`, `sdk/shells/why_not.py` | Identifies D22/D23 hard-cut payload |
| Service route docs and OpenAPI still describe CandidateSet evaluate/accept round-trip. | `app_v1.py:212-219`, `runtime_v1.py:920-1045`, `openapi.yaml:601-621`, service docs | Requires service blast-radius handling |

## 7. Consequences

### 7.1 User-visible consequences

T5 is a breaking public API change. Users consume:

- `EvaluateResult`;
- `EvaluateRow`;
- `row.explain()`;
- `row.close()` for manual replay;
- `fg.eval.explain(...)`.

Users no longer consume public CandidateSet lists, `accept` shells, direct check/diagnose shells, direct why-not shells, or what-if helper shells as the documented path.

### 7.2 Implementation consequences

The implementation must include a broad grep/audit stage before edits. It must update SDK, service routes, OpenAPI, docs, examples, and tests as one coherent hard-cut plan.

The hardest part is not only code replacement; it is avoiding a partially migrated public surface. Stage 3 should likely classify the implementation as L-class or split into tightly ordered M-class slices with local-only intermediate states.

### 7.3 Downstream consequences

D24 final SDK Rule naming must happen before final docs migration.

D25 semantics consistency can assume the public explain/evaluate pair is the T5 target and does not need to account for legacy why-not semantics.

D26 may defer adapter-touching semantics work, but it must preserve D23's hard-cut target if T5 Core implementation proceeds first.

## 8. Acceptance Criteria

- [ ] D23 identifies all legacy public SDK evaluation/evidence shells targeted by T5 hard-cut.
- [ ] D23 classifies CandidateSet as internal after T5 public return-shape flip.
- [ ] D23 requires service-route and OpenAPI blast-radius inventory before implementation.
- [ ] D23 requires final service state to stop returning CandidateSet as the normal inference evaluate payload.
- [ ] D23 requires docs/examples to stop teaching CandidateSet/accept/check/diagnose/why-not as T5 public evidence paths.
- [ ] D23 permits internal DTO/runtime retention only when not publicly exported or documented.
- [ ] D23 allows local mixed implementation states but forbids pushing them as milestones.
- [ ] D23 preserves D24 naming authority and defers final docs naming until after D24.

## 9. Decision Record

| Date | Stage | Decision | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Adopt a T5 hard-cut target for legacy SDK evaluate/evidence shells, CandidateSet public output, accept round-trip, why-not, and service CandidateSet routes. | Drafted after D22 reviewed clean v1; D24 final SDK Rule flip unblocked after review. |
