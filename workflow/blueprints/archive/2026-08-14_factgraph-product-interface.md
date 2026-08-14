# Task Blueprint: FactGraph product interface

- Status: archived
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Related Modules:
  - `src/factgraph/sdk/`
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/`
  - `src/factgraph/application/explain/`
  - `src/factgraph/core/evidence/`
  - `src/agent/`
- Related Docs:
  - [Q20 decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
  - [Q20 versus-shipped audit](../../audit/active/2026-08-14_factgraph-product-interface-vs-shipped.md)
  - [Q18 final closure](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
  - [Q19 policy authoring](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
- Audit Log:
  - [2026-08-14_factgraph-product-interface.audit.md](2026-08-14_factgraph-product-interface.audit.md)

## 1. Problem

Q18/Q19 made FactGraph's query/runtime substrate strong, sealed and cross-engine
honest, but its product-facing construction and presentation surfaces remain
fragmented. This slice turns those proven contracts into an ergonomic yet
strict SDK surface for the future AgentPlan/Meander layer. It also adds the
missing typed Scenario semantics/provenance and execution-profile route needed
to represent a run-local probabilistic premise without pretending it is a
portable deterministic fact.

## 2. Goals

1. Add symmetric Rule/Policy builder and direct-construction APIs with
   `AssetMeta`, preserving Q19 typed occurrence ownership and raw API
   compatibility.
2. Add a canonical authored `WeightedChoice` semantic node with a declared,
   initially ProbLog-only engine matrix.
3. Add Scenario V2 values, strict `meta=` lowering, semantic/provenance/display
   digest lanes, effective-world/replay capture and exact-point probabilistic
   materialization.
4. Add V2 execution semantics/profile codecs and stable Rule/occurrence/choice
   attachments; retain old V0 configs and V1 deterministic profiles unchanged.
5. Add structured, machine-readable result/explanation views and pure
   rendering helpers over sealed runs, without changing V0 live row behavior.
6. Add the minimal `ProvenanceRefV1` boundary and Agent write/draft bridge
   needed to prepare later Agent/Meander source work.
7. Document all support matrices and ship a runnable example/tutorial.

## 3. Non-goals

- Any policy catalog, string query lookup, registration/persistence or policy
  assignment.
- Any mutable Rule/Policy patch, global Scenario storage or ledger write.
- SourceRecord lifecycle, source content/ACL/tenant/retention, or Meander
  admission/authority logic.
- General probability intervals, arbitrary engine configuration, PyReason V2,
  probability-as-boolean, native fallback or probability portability.
- General negation/why-not proofs, Action execution, AgentPlan compiler or UI.

## 4. Current Context

- Q19 already supplies owner-bound Policy handles, literal compare and direct
  Query compilation; this slice must lower to it rather than fork it.
- Q18 already supplies sealed deterministic Scenario V1, GoalPlan, run/replay,
  explicit Explain targets and real deterministic Native/Soufflé/ProbLog row
  parity.
- Legacy `ProbLogConfig` remains consumed by old `fg.eval.evaluate`, but is
  keyed to lowered coordinates and cannot be promoted to V2 public semantics.
- Legacy `Explanation.repr` / `.narrate()` are V0 outer-renderer conveniences;
  `EvidenceGraph` remains a data DTO.

## 5. Proposed Shape

### 5.1 Authoring asset surface

Introduce an immutable `AssetMeta` and a thin common SDK builder/direct
surface. `build_rule` accepts the existing SDK Rule body plus complete semantic
port declarations, resolves it through the graph, and returns a product Rule
wrapper. A Policy builder composes those resolved product Rules via
`use(rule, as_=...)`; aliases stay local and typed. `build_policy(build=...)`
invokes its callback on one builder only, so owner-bound handles cannot cross
drafts. Direct forms are convenience wrappers around the corresponding
builders, not separate compiler paths. Each product wrapper has a canonical
asset descriptor and target+descriptor association seal; raw targets have an
explicit absent descriptor state.

### 5.2 Authored stochastic topology

Extend the parallel current Policy semantic topology with a canonical
exclusive `WeightedChoice` container: branch-total structured selection key,
unique arm ids, exact canonical decimal weights that sum to one, and nested
logical arm conditions. It must be present in target identity, lowering
lineage, replay codec and Explain data. Initial lowering is a ProbLog annotated
disjunction under a V2 semantic profile. Legacy compiler/evaluate/V1-plan
ingress rejects a choice target before it can discard the sidecar; portable,
Native and Soufflé return typed unsupported results rather than approximate it.

### 5.3 Scenario V2 and execution semantics

Create parallel versioned V2 protocol/runtime values. The SDK Scenario builder
accepts strict `meta=` and lowers it before resolution. Values, fact semantics,
safe provenance and display annotation have separate codecs and caps. The
resolved effective world carries evaluator-visible semantics through isolated
materialization, replay and Explain.

V2 profiles pin typed semantic model, engine/adapter/compiler details,
resources/capture policy, and Rule/occurrence/choice attachments. Every
attachment lowers from a durable target pin; rule/occurrence overlaps reject
rather than have precedence. Deterministic V2 is compatible in meaning with
Q18; ProbLog point semantics is exact-point only and explicit about its
`independent_bernoulli_v1` model. A choice attachment only validates/activates
its authored weights, never overrides them.

ProbLog V2 owns a distinct canonical result frame: rows retain logical selected
identity plus sealed point certainty/observation. Initial probabilistic runs
support `rows` and observation comparison only; boolean modes/expectations
reject until an explicit probability expectation contract exists. Native and
Soufflé are typed unsupported frames for this profile, never fabricated
canonical results.

`EvaluationRunV2` is the parallel tagged capture/replay/result carrier. It
binds complete profile bytes, resolved attachments, asset association seals,
semantic/evidence world lanes and engine frames. A V1 run can be read through a
view only with explicit `not_captured` V2 fields; it is never recast as V2.

### 5.4 Product result and Explain view

Layer V2 read views over sealed run values. They expose explicit result side,
rows, summary/mode/completeness, expectations and row anchors. An explicit row
view can request an Explain target. `EvaluationExplanationDataV2` composes
already-captured evidence/projection with Scenario/provenance/profile data;
rendering is pure and optional. The view does not pretend V1/V2 is a live V0
row or synthesize zero-row proof.

### 5.5 Safe provenance bridge

Add `ProvenanceRefV1` as a FactGraph-neutral reference. Agent draft/write code
may convert extraction provenance to it and mirror legacy source strings, but
does not decide admission or persist new SourceRecord state. The bridge removes
the invalid `confidence` write metadata path.

## 6. Boundaries And Invariants

- V0/V1 DTO fields, identity formulas, replay payloads and old engine config
  behavior remain byte/behavior compatible.
- There is one Query compiler/evaluator path per profile; no façade evaluator
  and no hidden fallback.
- `meta=` must completely lower or reject before a Scenario can resolve; it may
  never be silently dropped.
- Engine-visible semantics and non-engine provenance must use independent,
  sealed digest lanes.
- Any probabilistic Scenario or choice requires an explicit V2 ProbLog profile;
  portable runs reject it before executing an engine.
- V2 product targets carrying choice must reject at legacy/V1 terminals before
  lowering; no target is silently reduced to an ordinary Policy.
- Asset descriptor associations are sealed to the exact logical target, and
  candidate sides resolve their own descriptors and semantic attachments.
- Policy occurrence, rule and choice semantics attach only to stable authored
  pins, never compiler branch labels.
- A structured Explain consumer never parses rendered prose; all labels make
  captured-world/native-inner-evidence and parity boundaries explicit.
- `ProvenanceRefV1` carries no source content/authority/access policy and must
  not be confused with generic `EvidenceTree.Source`.
- New Agent changes are compatibility-only and must not change ledger ingest
  identity or add a SourceRecord service.
- `ProvenanceRefV1` and locator data are closed/capped and contain no raw
  extraction text; product data sanitizes generic EvidenceTree source metadata.
- Probability rows preserve a value selection identity and separately sealed
  certainty observation; they cannot be converted into V1 boolean modes.

## 7. Acceptance

- [x] Rule/Policy authoring APIs and AssetMeta obey Q20 §4.1 and Q19 ownership
  constraints, with full raw/legacy regression coverage.
- [x] WeightedChoice has deterministic canonical identity, typed failure matrix,
  ProbLog execution/replay/Explain coverage and no ordinary-Any reinterpretation.
- [x] Scenario V2 strict metadata reaches engine/replay/Explain, distinguishes
  semantic/provenance/display lanes and detects tamper/splice/conflict.
- [x] Deterministic and ProbLog V2 profiles reject unsupported combinations,
  pin every attachment, and never use lowered branch strings.
- [x] Product result/explanation data works from sealed runs only; V0 renderer
  behavior remains unchanged and zero/summary evidence is not fabricated.
- [x] Provenance bridge safely represents supported extraction refs, preserves
  legacy source fields, and no longer sends rejected `confidence` meta.
- [x] Baseline/effective paired Explain proves a masked captured witness remains
  captured support and only a synthetic effective witness carries Scenario
  provenance.
- [x] Profile/asset/choice/world/replay field splices and a same-row changed
  probability are fail-closed or represented as a certainty delta as specified.
- [x] Real Native/Soufflé/ProbLog deterministic tests and real ProbLog V2
  probabilistic tests pass; unavailable engine behavior is typed and tested.
- [x] Module docs, API docs and a runnable notebook reflect exact support
  boundaries.

## 8. Implementation Plan

1. Add shared asset metadata plus product Rule/Policy wrappers and symmetric
   entry points; test semantic-port resolution, direct/builder equivalence,
   descriptor association seals and no-registration rules.
2. Add the authored WeightedChoice topology/anchor codec and V2 query ingress;
   test arm/key/weight splice, legacy/V1 pre-execution rejection and no
   ordinary-Any reinterpretation.
3. Add strict provenance and V2 Scenario metadata protocol/resolver/effective
   relation; capture baseline and synthetic semantics/provenance, then test
   per-member/conflict/digest behavior and legacy V1 isolation.
4. Add `EvaluationRunV2` plus V2 execution semantic/profile codec, side-specific
   stable attachments, exact-point ProbLog materialization/result/replay, and
   the typed support matrix; test profile/attachment splice, observation deltas
   and no fallback.
5. Integrate WeightedChoice with the V2 ProbLog profile/replay/Explain support
   state and prove Native/Soufflé/portable fail before engine execution.
6. Add V2 result/explanation data/read/render facades, with explicit rows,
   policy/scenario/provenance sections, V1 `not_captured` states and legacy
   renderer preservation.
7. Add Agent draft/write provenance adapter and invalid-confidence remediation.
8. Update exports/docs/examples; run focused, integration, adversarial and
   compatibility verification; record outcome and final audit.

## 9. Docs To Update

- `src/factgraph/sdk/docs/`
- `src/factgraph/application/docs/`
- `src/factgraph/application/protocol/docs/`
- `src/factgraph/application/explain/docs/`
- `src/factgraph/core/docs/`
- `src/agent/docs/` and relevant write/module documentation
- `examples/README.md` and a new runnable tutorial notebook

## 10. Outcome / Deviations

Implemented as an additive V2 product surface. The main deliverables are:

- Symmetric `fg.rule_builder` / `fg.build_rule` and `fg.policy_builder` /
  `fg.build_policy` APIs, with separately sealed `AssetMeta`. Product Rule
  semantic ports accept public SDK descriptors such as
  `{"person": Person, "age": Person.age}`; no application protocol import is
  required for the ordinary path.
- Intrinsic `PolicyWeightedChoice` topology with sealed arm/key identity. It
  is only lowered by the controlled V2 ProbLog path; raw rewrapping and all
  legacy/V1 terminals reject it rather than reinterpret it as `Any`.
- Strict `ScenarioSpecV2` metadata lanes for fact semantics, opaque provenance
  and display annotations, plus sealed V2 profile/run/replay carriers. The
  ProbLog point profile records `problog_float64_v1` materialization—including
  `omitted_zero`—so a submitted Decimal is not confused with an engine row
  observation.
- Data-first V2 Result/Explain views and an SDK outcome facade. They expose
  captured Scenario/provenance, profile, probability materialization and
  choice topology; they do not fabricate a ProbLog EvidenceGraph or a
  negative proof. V0 `Explanation.repr`/`.narrate()` remain unchanged.
- A neutral Agent extraction-provenance bridge and removal of the invalid
  `confidence` write metadata. This deliberately does **not** migrate all
  legacy Agent writes into a Meander SourceRecord/FactBinding system.

Independent final verification on the implementation branch:

- `tests/application tests/sdk`: **749 passed, 182 subtests**;
- Q20 adversarial/protocol/source cohort: **57 passed, 7 subtests**;
- notebook `examples/09_product_scenario_execution_v2.ipynb`: **11/11** code
  cells executed by the real `factpy` kernel with no errors;
- `ruff check`, focused `ruff format --check`, focused mypy, and
  `git diff --check`: clean.

Intentional boundaries remain: deterministic three-engine parity stays in the
Q18 portable profile; V2 probability and `WeightedChoice` are ProbLog-only
with typed Native/Soufflé unsupported frames; V2 native/ProbLog Explain
reports an explicit unavailable EvidenceGraph when none was captured; full
SourceRecord custody/admission/retention remains a Meander responsibility.
