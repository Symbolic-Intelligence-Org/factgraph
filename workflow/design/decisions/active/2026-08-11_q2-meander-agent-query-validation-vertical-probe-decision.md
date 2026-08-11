# Q2 Decision: 一次性 Agent→Meander→FactGraph Query/Validation 共享纵切架构验证例外

- Status: adopted
- Created: 2026-08-11
- Last Updated: 2026-08-11
- Authority: design constraint; if adopted, locks one separately named, budget-capped, disposable `P0/A0` Agent→Meander→FactGraph Query/Validation shared-seam vertical-probe envelope, its provisional contract ownership, evidence boundaries, and stop semantics before any consuming blueprint; it adopts no production API, ADR, implementation, or product direction.
- Inputs:
  - 2026-08-11 user direction: preserve the five-step validation sequence and absorb six hard corrections into Step 1 — correct §0.4 exception authority, no envelope proliferation, mandatory SC-01/SC-02 preregistration, coherent `expect`/zero-row/field-navigation coverage and ADR mapping, threshold-first dual-model testing, and graded replay claims
  - [`meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md`](../../design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md) §0.4, §1.2–§1.3, §6.1–§6.7, §11.1–§11.4, §14.3–§14.5, §17 Phase 0–1, §18.1, §18.3–§18.5, §20 D02–D11; 2235 lines; SHA-256 `750ced2141e9d8c20400c5ed59d6c439707b32fb363919ab7b1533918f2a9e1b`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md) §4.2 SC-01, §5.3 SC-01/SC-02, §6.3, §7.3; 382 lines; SHA-256 `7449dd6041bea639aeddecc6903e04b03ce0ead1c9ebd38a7052c67bc6eb45f2`
  - Archived shipped-alignment audit [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](../../../audit/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md) lines 127, 137–157, 173–175, 197–201; 394 lines; SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`
  - Adopted [`2026-08-11_q1-offline-feasibility-before-external-validation-decision.md`](2026-08-11_q1-offline-feasibility-before-external-validation-decision.md) §3, §4.2–§4.5, §4.8; 321 lines; SHA-256 `47e48838664328072dd6bda223832286fedc905a2c95283fa66b7a5f204fceec`
  - Parked draft [`2026-08-11_meander-case-bundle-feasibility.md`](../../../blueprints/active/2026-08-11_meander-case-bundle-feasibility.md) and its [`paired audit`](../../../blueprints/active/2026-08-11_meander-case-bundle-feasibility.audit.md), both pinned at parent commit `32093c98d39f21a61418314a5f7a685acc256d4a`
  - Current FactGraph construction/lowering evidence at parent commit `32093c98d39f21a61418314a5f7a685acc256d4a`: [`test_rule_expr.py`](../../../../tests/application/protocol/test_rule_expr.py) lines 329–338 and [`rule_expr_lowering.py`](../../../../src/factgraph/application/protocol/rule_expr_lowering.py) lines 764–829
  - [`workflow/CADENCE.md`](../../../CADENCE.md), [`workflow/blueprints/README.md`](../../../blueprints/README.md), and the decision template/lifecycle
- Outputs / Downstream:
  - Only after adoption and a separate user authorization: one paired vertical-probe blueprint/audit carrying Steps 2–5 as internal checkpoints
  - One immutable final evidence/disposition lineage reporting `PROCEED_TO_ADR_CANDIDATES`, `REVISE`, or `STOP`
  - Only after `PROCEED_TO_ADR_CANDIDATES` and further authorization: evidence-scoped D02–D07/D10–D11 decision proposals and cross-repository implementation planning
- Related:
  - Candidate D01 remains open; product authorization remains `STOP-except-discovery`
  - Candidate D02–D07 and D10–D11 are possible later decision subjects, not decisions made here
  - Q1 and its CB0 blueprint remain independent and unchanged
- Branch: `v0.3.0-q2-meander-agent-query-validation-vertical-probe-decision-2026-08-11`
- Depends on: adopted Q1 only as a non-reuse, evidence, and P-GATE-revisit constraint; Q1 is not this probe's authorization source

> ADR 4-state lifecycle: `proposed` → `adopted` (current binding constraint, stays in `active/`) → `superseded` or `withdrawn` (moves to `archive/`). This file is adopted and closes only Q2. Adoption does not authorize blueprint drafting, review, preflight, source changes, model calls, credential use, data egress, or execution.

## 1. Inputs

### 1.1 Why a narrow vertical probe is now the relevant question

The design lineage has enough internal coherence to state a testable chain:

```text
Agent typed invocation
  -> Meander fixed-profile resolution
  -> provisional FactGraph Policy/EvaluationQuery
  -> native compile/evaluate
  -> rows/expectation target
  -> selected result Explain
  -> Agent consumes the returned distinction
```

It does not yet have engineering evidence that the chain can preserve semantic identity, authority, row meaning, Explain targeting, and Agent fidelity at the same time. Continuing to refine the full architecture without exercising this seam risks turning syntax into an untested design commitment.

The smallest useful next question is therefore not “is Meander a validated product?” or “is the complete Query API ready?” It is:

> Can two separately assigned, server-fixed Query/Validation task profiles share one semantically explicit FactGraph EvaluationQuery seam, be evaluated and explained without authority drift or identity loss, and be used correctly by two pinned model families under a frozen open-fixture protocol?

### 1.2 Immediate authority and the §0.4 exception shape

The immediate authority for this file is the user's 2026-08-11 direction to draft the five-step vertical-probe decision with the six named corrections. The v0.1.1 candidate is explicitly non-authoritative. Its §0.4 does not grant permission; it supplies the guardrail shape for any separately authorized exception:

- separately named;
- numerically budget-capped before execution;
- disposable;
- not product approval;
- unable to force product continuation.

This decision applies that shape to a new, architecture-only exception. If adopted, it would make one downstream blueprint eligible to be requested. It would not itself authorize that blueprint or its execution.

### 1.3 Relationship to Q1 and parked CB0

Adopted Q1 authorized no Agent/Plan experiment. It defined one non-transferable `F-GATE` experiment envelope, and the current CB0 blueprint is its parked `draft` representation. Q1 also requires any later discovery to state why `P-GATE` is or is not next.

This Q2 answers that sequencing question narrowly: the proposed P0/A0 probe tests a distinct, still-unverified architecture risk — whether a constrained Agent declaration survives deterministic resolution, query compilation, evaluation, explanation, and return consumption. It is cheap enough to test before external product validation only if it remains one capped, disposable exception.

Accordingly:

- Q1 is not superseded, amended, renewed, or consumed;
- CB0 remains parked `draft` with all of its gates unchanged;
- no CB0 corpus, holdout, gold, custody role, arm, budget, artifact, or result may be used or relabeled by this probe;
- this probe produces neither `F-GATE` nor `P-GATE` evidence;
- `P-GATE` remains open, and product authorization remains `STOP-except-discovery`.

### 1.4 What existing evidence does and does not establish

The candidate and disposition establish testable hypotheses and known gaps, not shipped target capability. In particular:

- current construction tests allow an asymmetric `join × Any` expression, while its lowering meaning is not specified by a semantic golden;
- current lowering can generate branch aliases without retaining a sufficient authored→lowered public lineage contract;
- current `row.explain()` is a live convenience path, not proof of durable historical replay;
- the proposed semantic ports, Policy, PolicyQueryContract, EvaluationQuery, field navigation, and graded replay model remain target design.

The probe must preserve those distinctions. It may create evidence for later decisions; it may not use its own experimental syntax as proof that those decisions have already been made.

## 2. Scope

If adopted, this decision locks only:

1. one separately named, one-time architecture probe exception and its non-proliferation boundary;
2. the five-step validation order and the gate between deterministic and model-assisted work;
3. a strict `L1 tool transport / P0 Plan complexity / A0 policy authority / shadow-evaluate-only disposition` ownership profile;
4. the distinction between Agent-supplied task slots and Meander-resolved internal query fields;
5. the minimum open-fixture/oracle coverage, including `expect`, complete and incomplete zero-row behavior, and field navigation;
6. mandatory SC-01 and SC-02 preregistration and exit evidence;
7. threshold-first, per-model dual-model evaluation rules;
8. graded Explain/replay capability and artifact-availability reporting;
9. the permitted final disposition and the evidence-to-later-decision mapping;
10. stop, budget, compatibility, credential, and data-egress boundaries.

## 3. Non-scope

This decision does **not**:

- adopt a public Query, Validation, Plan, Policy, RuleContract, PolicyQueryContract, Explain, replay, or Agent SDK/API contract;
- choose Query versus post-hoc Validation as the final Meander product core;
- close D01–D18 or adopt any later ADR;
- pass, reopen, renew, replace, or consume Q1's `F-GATE`; pass `P-GATE`; or prove reviewer value, buyer, budget, workflow fit, lawful customer data access, or market demand;
- validate Translator, passive L0 observation, L2 repair, L3 native Plan, A1 Agent-selected Policy, A2 Agent-composed Policy, P1/P2 Plan complexity, Scenario/what-if, persistent Claim handling, Operator, Action/Decide, Package, learning, or product UI;
- validate cross-engine parity, Soufflé/ProbLog external operators, historical customer data, source truth/authority/freshness, or a production semantic layer;
- migrate Meander's FactGraph dependency, change database schemas, create production routes, publish an SDK/MCP tool, or modify shipped Plan v3 behavior;
- authorize source changes in FactGraph or Meander, model/API calls, BYOK use, data egress, external contact, or customer/private data;
- create a reusable prototype, renewable experiment platform, hidden-corpus Plan Lab, or statistical generalization claim;
- authorize formal implementation merely because the probe returns a favorable result.

## 4. Decision

### 4.1 One architecture-only §0.4 exception, not a product or Q1 envelope

If this decision is later adopted, it authorizes no execution. It makes exactly one paired blueprint/audit eligible for separate drafting authorization. That blueprint may request one architecture-only disposable experiment whose purpose is to decide whether the fixed-profile vertical chain deserves evidence-scoped ADR proposals.

The probe's public-facing statement must remain:

> This is an open-fixture engineering probe of a pinned P0/A0 vertical chain. It is not a production integration, a public contract, a hidden-corpus Agent benchmark, an F-GATE/P-GATE result, or product validation.

The probe remains worthwhile before `P-GATE` because it can cheaply falsify a load-bearing integration assumption that neither desk research nor CB0 answers. That sequencing exception ends with this one result. A favorable result does not justify another architecture slice before `P-GATE`; any successor requires a new decision that again explains whether `P-GATE` should precede it.

### 4.2 One envelope; the five steps are internal checkpoints

The experiment-content lineage is limited to:

```text
one adopted Q2 decision
  -> one separately authorized paired blueprint/audit
      -> one independent preflight artifact
         (governance check; not another experiment envelope or blueprint)
      -> Step 2 open fixtures/oracle
      -> Step 3 headless deterministic spike
      -> Step 4 bounded dual-model Agent probe
      -> Step 5 replay/compatibility synthesis
  -> one immutable final report/audit/disposition
```

The five steps must not create five decisions, five blueprints, nested discovery envelopes, or renewable gates. The future paired blueprint must freeze, before `scoped` or any execution:

- one cumulative calendar cap;
- one cumulative human-hours cap;
- one case/fixture cap;
- one local compute/cost cap;
- one external-model call/token/cost cap;
- one retry/repair cap, including provider failures;
- one disposable harness/facade lineage;
- one provisional contract version;
- two predeclared model configurations;
- one final evidence/disposition lineage.

The user must explicitly accept the numeric cap before execution. Exceeding any cap stops the envelope. `REVISE`, `STOP`, an incomplete model arm, or an invalidated score ends it; none silently grants a repaired corpus, new prompt, replacement model, extra calls, or second run. A successor requires a new decision.

The only permitted pre-score contract refinement is one change explicitly scheduled between Step 3 evidence and the Step 4 freeze. It must retain the original Step 2 fixture/oracle lineage and record the exact diff. After the first scored model call, schema, prompts, oracle, cases, normalization, denominators, models, thresholds, and exclusions are immutable.

The probe may cite Q1/CB0 as governance background but must not read, copy, modify, contaminate, or reuse its experimental assets. It uses only synthetic or otherwise explicitly authorized open fixtures and makes no holdout/generalization claim.

### 4.3 Ownership contract: P0/A0 stays P0/A0

The probe fixes four independent axes:

| Axis | Probe value | Meaning |
|---|---|---|
| transport/participation | `L1 explicit tool call` | Agent deliberately invokes a typed tool; no passive trace translation and no native full Plan requirement |
| Plan complexity | `P0` | Agent fills task-specific slots in one assigned server profile |
| Policy authority | `A0` | Meander/server chooses the fixed Policy/query, projection, expectations, premise rules, and execution profile |
| disposition | `shadow / evaluate-only` | no repair callback, write, authorization, or side effect |

The external Agent invocation may supply only:

- an assigned fixed-profile identifier when the route does not already imply it;
- typed target identities/roles;
- typed operand/value slots already declared by that profile.

The route/assignment fixes `request_kind` before each fixture exposes a tool. The Agent is never offered a free choice between Query and Validation inside one invocation. Value slots bind only preregistered query or expectation operands; they create no persistent Claim, Scenario premise, source admission, fact mutation, or Policy condition. Source/observation references are outside this probe rather than being accepted as ambiguous opaque inputs.

The Agent must not select or override:

- `policy_ref`, Policy version, Rule occurrence, or Policy AST;
- arbitrary ontology paths or free-form `bind` keys;
- `request_kind`, `select`, query mode, expectation template/operator, projection/path, polarity, quantifier, or operand-slot schema;
- mandatory evaluation units, premise policy, combining profile, engine/config, budget, or final assessment/verdict.

Meander's deterministic fixed-profile resolver owns those fields and records both the Agent submission and the resolved internal request plus their difference. If an external schema exposes free Policy/query-shape choice, the experiment has crossed into P1/A1 and must stop rather than relabel itself P0/A0.

All experimental wire shapes must be labeled:

```text
EXPERIMENTAL
NON-NORMATIVE
NON-PUBLIC
NON-COMPATIBLE
NO SEMVER COMMITMENT
```

They use an experiment-local identity such as `vertical_probe.p0a0.v0`, never a production-looking `meander.query.v1`. They must not enter OpenAPI, exported packages, a public SDK, MCP server, production route, migration, or user documentation.

### 4.4 Step 2 — open fixtures and human oracle

Step 2 must freeze the semantic problem before the compiler or models can optimize around implementation behavior. Every fixture records separate expected artifacts for:

1. ingress/schema and attempted authority;
2. deterministic fixed-profile resolution;
3. internal typed binding/path resolution;
4. Policy compile/lowering and authored→lowered lineage;
5. result rows, completeness, truncation, and error class;
6. server-owned expectation evaluation where applicable;
7. selected-row, expectation, or query-summary Explain target;
8. the Agent's permitted final interpretation of the returned result.

The minimum fixture matrix includes:

- one-row and multi-row results with explicit projection;
- complete zero-row and incomplete/truncated zero-row cases;
- `All`, `Any`, repeated occurrence aliases, and the SC-01 asymmetric `join × Any` pair;
- valid, missing, ambiguous, unbound-branch, and unauthorized field navigation;
- invalid request, resolution failure, engine failure, and unsupported capability;
- Agent attempts to inject Policy, occurrence, path, `select`, `expect`, config, or authority;
- a correct tool invocation followed by an incorrect Agent interpretation of zero rows, incompleteness, error, or expectation status.

Expected outcomes must be authored before implementation and independently reviewed before execution. This is a lightweight engineering oracle review, not CB0's custody/gold protocol and not a hidden benchmark.

#### 4.4.1 Query and expectation are distinct even when they share EvaluationQuery

The experiment may exercise two fixed-profile task kinds over one internal evaluation seam:

1. **Query fixture**: its assigned route/profile fixes `request_kind=query`, Policy, query mode, and `select`; the Agent supplies only preregistered typed target/operand slots. It returns rows or a Boolean query summary plus completeness and does not carry an expectation.
2. **Validation fixture**: its separately assigned route/profile fixes `request_kind=validation`, Policy, projection, expectation template/operator, polarity, quantifier, and operand-slot schema; the Agent only binds preregistered typed operand slots. It cannot submit an arbitrary row tuple, path, polarity, proposition, or expectation AST.

In Step 2/3, a `server_owned_expectation` is a real runtime object in the resolved internal EvaluationQuery. A separate `test_oracle_assertion` verifies the returned object but never enters EvaluationQuery, wire output, Explain anchors, or later D06 contract evidence. Neither object is an Agent-authored condition, Policy conclusion, authorization, or hidden filter. The first probe admits only these server-owned expectation kinds:

- `exists`;
- `contains_row` over a complete untruncated result or a sound early-stop proof.

It must cover `satisfied`, `not_satisfied`, `underdetermined`, and `unsupported`. `not_satisfied` is valid only when the completeness contract proves it. If budget, truncation, or missing capability prevents that proof, the result is `underdetermined`, never false.

`query.mode=exists` and `expectation.kind=exists` are different typed fields with different oracles. The first asks for a Boolean query summary and produces no `ExpectationResult`; the second observes a server-fixed proposition and returns an `ExpectationResult`. Sharing the lexical word `exists` must not collapse their result types or Explain targets.

#### 4.4.2 Zero rows are not denial or failure

A complete evaluation with no matching rows is:

```text
rows = []
completeness = complete
exists = false
```

It is not `denied`, `unsupported`, `underdetermined`, an execution error, or proof of an unrelated negated proposition. An incomplete/truncated zero-row result cannot establish `exists = false`; it remains `underdetermined`. With no row anchor, Explain must target the query summary or expectation diagnostic, never an implicit “first row.”

#### 4.4.3 Field navigation is intentionally in the probe

The probe includes one typed navigation such as `pair.person2.age`; D04 therefore cannot be silently deferred. Paired fixtures must test:

- an allowed visible field;
- a restricted field;
- missing or ambiguous resolution;
- a navigation that can be unbound in an `Any` branch;
- the explicit authored navigation → lookup/comparison → lowered node lineage.

No implicit lookup or field disclosure may be inferred merely because a path is syntactically valid. If the spike cannot give navigation an explicit typed resolution, permission decision, and lineage, the navigation leg fails and D04 remains `CONTRADICTED` or `UNRESOLVED`; all later contracts must omit field-navigation claims.

### 4.5 Step 3 — FactGraph-only headless compiler/query spike

Step 3 uses only manually authored canonical fixtures. No Agent output, Translator, product UI, external model, or mutable production service participates.

The isolated disposable spike may test only:

- semantic public ports and occurrence-qualified paths;
- `All`, `Any`, direct typed comparison, and explicit equality/unification;
- fixed-profile `bind`, `select`, and the two closed expectation kinds in §4.4.1;
- `rows` and `exists` modes, completeness, explicit failure, and no silent engine fallback;
- a synthetic projection head strictly as a lowering scaffold;
- native evaluation;
- run-local row identity and selected-row/expectation/query-summary Explain anchors.

Any experiment code must remain an isolated, blueprint-listed disposable facade/compiler/harness with no exported or production surface. It may not change shipped Plan v3 routing, persisted Inbox/decision/learning/current-evaluation state, or public behavior. If the probe requires a production-path or migration change to become testable, it stops and returns that need as later ADR/blueprint evidence.

#### 4.5.1 SC-01 is a preregistered semantic fork, not a bug fix

Before any compiler fixture runs, the blueprint must preregister two candidate meanings for:

```text
(a & (b | c)).join(a.x == b.x)
```

- `branch-scoped`: the join constrains only branches where both endpoints exist;
- `reject-on-partial`: compilation rejects a join that cannot address every possible branch.

Paired golden fixtures must make the `c` branch observably distinguish the candidates. Current lowering is an observed baseline only; it is neither the oracle nor a presumed bug. Step 3 may return one evidence-backed D03 recommendation or `UNRESOLVED`. It does not adopt D03 or modify shipped lowering.

If Step 3 leaves SC-01 unresolved, Step 4 must not contain the asymmetric construct, and the Policy-AST leg cannot be reported ready for ADR without that exclusion.

#### 4.5.2 SC-02 is an exit gate

Step 3 must emit a machine-checkable total authored→lowered lineage for every tested:

- occurrence and semantic path;
- join/unification and comparison;
- `All`/`Any` branch;
- field navigation and injected lookup;
- `select` column and expectation target;
- synthetic-head binding;
- generated branch/alias/node.

Every generated node must point back to its authored origin or an explicit compiler-created role, and every authored constraint must map to a lowered node or an explicit diagnostic. Generated aliases and position-based branch IDs remain compiler-private and cannot become public paths or compatibility aliases. `repr` strings and post-hoc path guessing do not satisfy this gate.

Failure to produce this lineage makes the compiler/Explain leg `FAIL`; cross-engine and cross-version identity remain `UNRESOLVED` even if native one-run lineage passes.

#### 4.5.3 Step 3 exit before model work

Step 4 is eligible only if Step 3 demonstrates, on the frozen fixtures:

- canonical request normalization or explicit rejection;
- expected native rows/completeness and expectation statuses;
- no projection-induced business condition;
- no silent constraint loss or engine fallback;
- explicit zero-row and failure-class distinctions;
- SC-02 lineage completeness;
- a recorded SC-01 recommendation or explicit exclusion from Step 4;
- no shipped-state write or Plan v3 behavior change.

Otherwise the envelope proceeds directly to Step 5 **only for synthesis/disposition** with `REVISE` or `STOP`. Replay levels that depend on the failed capability are `NOT_TESTED`; no additional implementation is constructed to repair them, and models may not be used to rescue a failed deterministic core.

### 4.6 Step 4 — threshold-first, dual-model P0/A0 Agent probe

Step 4 tests one bounded tool-use loop for each fixture:

```text
user-shaped task
  -> Agent fills fixed-profile typed slots
  -> Meander resolver creates internal EvaluationQuery
  -> pinned Step 3 evaluator returns typed result
  -> Agent receives that result once
  -> Agent answers or abstains under the frozen response contract
```

It measures assigned-tool/target/slot accuracy, attempted authority escalation, canonical resolved-request equivalence, evaluation-result equivalence, correct use of completeness/expectation/error distinctions, abstention, and final-answer faithfulness. It does **not** score Agent choice of request kind, Policy, `select`, expectation kind, or engine because P0/A0 grants no such choice.

Before the first scored model call, the paired blueprint must freeze:

- two materially independent model families/providers and exact model identifiers/versions;
- one frozen profile-specific tool-schema projection per assigned route/profile, byte-identical across both models for that profile, plus frozen system/task prompts, fixtures, oracle, normalization algorithm, and response contract; the shared envelope/version must not expose `request_kind` or the other profile's slots inside the current invocation;
- sampling settings, seed where supported, token/time limits, and per-case call count;
- repair/retry/provider-failure rules and their cumulative cap;
- risk classes, denominators, exclusions, per-metric thresholds, and invalidation rules;
- credential, logging, redaction, retention, and data-egress handling.

At minimum, each model must independently satisfy:

- accepted-but-semantically-wrong safety-critical request: `0`;
- accepted authority escalation: `0`;
- invalid or unauthorized path fails closed: every fixture;
- ambiguous cases abstain or route to review: every fixture;
- zero-row, incompleteness, error, and expectation-status misinterpretation: `0`;
- routine canonical-request and evaluation-result equivalence: `>= 90%` when the frozen denominator makes a percentage meaningful; otherwise every named routine fixture is a required invariant.

Results are reported per model and per risk class. They must not be pooled to hide one model's failure. One passing and one failing model is ordinarily `REVISE` with a model-dependence finding, but any model triggering a `STOP`-class kill makes the final disposition `STOP`. If only one model can run, its result is a single-model smoke test and Agent fidelity remains `UNRESOLVED`.

Model A must not be used to tune the prompt/schema before running Model B and then presented as an independent validation. Any scored-run change to prompt, schema, model set, fixtures, oracle, normalization, denominator, threshold, or exclusion invalidates the complete Agent score. The immutable record remains evidence; the envelope does not automatically rerun.

This decision neither selects providers nor authorizes keys or case egress. BYOK/credential use and the exact data sent to each provider require separate explicit authorization during the future blueprint/preflight flow. With no such authorization, Step 4 does not run and its dimension remains `UNRESOLVED`.

Passing both pinned models establishes only pinned-model × frozen-open-fixture feasibility. It does not close the candidate's hidden-corpus Plan Lab or establish generic Agent compatibility.

### 4.7 Step 5 — graded Explain/replay, compatibility, and synthesis

Step 5 must not return a scalar `replay = PASS`. It reports each capability level and artifact-availability state independently:

| Level | Required meaning | Maximum honest claim |
|---|---|---|
| `R0 live association` | same live Run/handle maps one row, expectation, or query summary to the correct Explain target | live linkage only; not replayable |
| `R1 captured-artifact explain` | a captured frozen proof/bundle can be reopened and explained without reading current/latest state | frozen artifact Explain for the tested bundle |
| `R2 pinned deterministic re-execution` | exact readable Policy/rules/lowering, facts/snapshot, config/profile, anchors, and provenance reproduce normalized results and declared fingerprints | deterministic re-execution on pinned artifacts/environment |
| `R3 detached reconstruction` | after process restart or in an isolated environment, the captured bundle alone reconstructs the declared result/Explain without source services or current ledger | detached replay for the captured contract only |
| `R4 historical product replay` | Meander CompletedRun retention, expiry, source handling, migrations, and historical UI Explain are demonstrated | production historical replay; outside this probe and therefore `NOT_TESTED` |

For every level, artifact availability is separately reported as `available`, `partial`, `unavailable`, or `expired/erased`. Missing inputs must produce an explicit `UNAVAILABLE`, `EXPIRED`, or `UNRESOLVED` result. The system must never consult current/latest Policy, ledger, facts, config, source, or model output to fill a historical gap.

Mutation is a child comparative Run, not replay. Step 5 mutates the available ledger/fact fixture, Policy, config, and source availability to verify either original pinned-material use or explicit unavailability. Silently explaining an old row with mutated current state is an immediate failure.

`row.explain()` success in one live process proves only R0. A digest proves integrity of an existing artifact, not its availability. A frozen eager proof does not by itself prove deterministic re-execution. Until the relevant detached/historical levels pass in later work, shipped eager proof snapshots remain the compatibility floor and no lazy historical Explain cutover is allowed.

The probe may return `PROCEED_TO_ADR_CANDIDATES` only if at least R0, R1, R2, mutation isolation, and explicit missing-artifact failure pass. R3 may remain `UNRESOLVED` only if the later decision proposal explicitly excludes detached/historical replay and preserves eager proof. R4 is necessarily `NOT_TESTED` here.

The compatibility leg also verifies that the disposable path produces no shipped Plan v3 routing or persistent Meander side effects. It does not claim full legacy parity or migration readiness.

### 4.8 Evidence-to-decision matrix; no automatic ADR adoption

Step 5 must report each candidate decision subject as one of:

```text
SUPPORTED_FOR_ADR
PARTIAL
UNRESOLVED
CONTRADICTED
NOT_TESTED
```

The minimum mapping is:

| Candidate | Probe evidence required | Consequence of missing evidence |
|---|---|---|
| D02 semantic-port descriptor/identity | typed public ports, digest inputs, occurrence/path fixtures | no semantic-port ADR proposal |
| D03 Policy AST v0 | `All`/`Any`, comparisons/unification, SC-01 recommendation, unsupported-capability failure | scope proposal to demonstrated operators or keep unresolved |
| D04 field navigation | typed resolution, authorization, ambiguity/unbound behavior, lineage | remove field navigation from proposed contract |
| D05 PolicyQueryContract | stable filtered server-owned paths/slots and P0/A0 ownership | no Agent-facing contract proposal |
| D06 query/expectation semantics | rows/completeness, complete/incomplete zero rows, `exists`/`contains_row`, budget/error distinctions | query/expectation proposal remains partial or unresolved |
| D07 minimum A0 assignment | server-fixed profile and failed escalation fixtures | no Agent probe promotion |
| D10 replay profile | only the individually passed R0–R3 levels and explicit unavailability behavior | unpassed level stays excluded/unresolved |
| D11 result/Explain anchors | row, expectation, and query-summary anchors with declared run-local/durable scope | no durable Explain target claim |

The probe does not close or adopt any D-number. It must not select a desired ADR list first and then treat the experiment as confirmation. Only `SUPPORTED_FOR_ADR` or explicitly narrowed `PARTIAL` rows may be requested as later proposed decisions.

The final envelope disposition is exactly one of:

- `PROCEED_TO_ADR_CANDIDATES`: the deterministic chain passes, both model arms meet the frozen gates, the minimum replay requirements in §4.7 pass, no kill criterion fires, and the evidence matrix supports a coherent minimal later decision set;
- `REVISE`: the hypothesis remains plausible but is model-dependent, semantically unresolved, below a required replay/lineage gate, or only partially supported; the envelope ends without a repair run;
- `STOP`: any `STOP`-class semantic, authority, safety, compatibility, data, or governance kill fires, including when the chain is falsified or can be made to work only by leaving the authorized scope. The final report separately records whether the architecture hypothesis is `CONTRADICTED` or remains `UNRESOLVED` because the experiment itself became invalid.

Disposition precedence is strict: `STOP`-class kill > invalidation or `REVISE`-class kill > ordinary threshold-driven `REVISE` > `PROCEED_TO_ADR_CANDIDATES`. Every terminal record contains the final envelope disposition, each affected dimension's status, and whether its evidence remains valid, invalidated, or not collected.

`PROCEED_TO_ADR_CANDIDATES` means only that the user may separately authorize drafting evidence-scoped D02–D07/D10–D11 proposals. It is not ADR adoption, production implementation, cross-repository migration, `F-GATE`, `P-GATE`, or product approval.

### 4.9 Kill criteria and invalidation

Any of the following stops or invalidates the probe as stated:

| ID | Condition | Disposition |
|---|---|---|
| `K-AUTHORITY` | Agent can override fixed Policy/projection/expectation/config/mandatory unit or obtain an unauthorized field | `STOP` |
| `K-SEMANTIC` | any safety-critical accepted-but-semantically-wrong request or response | `STOP` |
| `K-ZERO` | complete empty, incomplete empty, unsupported, underdetermined, error, deny, or support collapse into one another | `STOP` |
| `K-SELECT` | projection adds an unregistered business condition or silently changes the logical result set | `STOP` |
| `K-SC01` | a tested authored constraint silently disappears without the preregistered semantics or explicit diagnostic | `STOP` |
| `K-SC02` | complete authored→lowered lineage cannot be produced for the tested slice | `REVISE`; `STOP` if hidden loss is presented as Explain-ready |
| `K-REPLAY` | an old result is explained by silently reading current/latest state | `STOP` |
| `K-COMPAT` | the probe writes shipped Inbox/decision/learning/current-evaluation state or changes Plan v3 behavior | `STOP` |
| `K-SCHEMA` | experimental schema enters a public/production surface or gains a compatibility promise | `STOP` |
| `K-CB0` | CB0 authority, assets, budgets, or results are consumed or polluted | `STOP` |
| `K-THRESHOLD` | a scored call is followed by outcome-aware changes to schema/prompt/oracle/model/corpus/threshold/exclusion or selective retry | score `INVALIDATED`; envelope ends `REVISE` |
| `K-SCOPE` | Translator, A1/A2, Scenario, UI, Operator, Action, migration, or production code is required to rescue P0/A0 | `STOP` for this hypothesis |
| `K-BUDGET` | any cumulative numeric cap is exceeded | execution stops; final disposition `REVISE`, with affected dimensions `UNRESOLVED` |
| `K-DATA` | credential leakage or unapproved content egress occurs | immediate `STOP` and incident handling; no result promotion |

No kill may be repaired by shrinking a denominator, relabeling a fixture after results, selecting only one model, or hiding an unresolved replay tier in an aggregate score.

### 4.10 Governance sequence after this proposal

The only permitted sequence is:

1. review this proposed decision;
2. separately adopt, revise, or withdraw it;
3. only after adoption and explicit authorization, draft one paired vertical-probe blueprint/audit containing Steps 2–5 and numeric caps;
4. separately review that pair;
5. perform independent preflight and self-check;
6. obtain explicit `scoped` and execution authorization, including separate BYOK/data-egress authorization if Step 4 will run;
7. execute the one envelope and archive an immutable report/audit/disposition;
8. only after `PROCEED_TO_ADR_CANDIDATES` and new authorization, draft the supported ADR subset and cross-repository implementation plan.

There is no automatic transition at any numbered boundary. This decision does not create the downstream blueprint.

Because this is one Q decision over one tightly coupled evidence bucket, the standalone post-Q synthesis described by [`workflow/audit/README.md`](../../../audit/README.md) lines 59–69 is skipped. Step 5's synthesis is the experiment's result consolidation, not a substitute Stage-3 synthesis and not permission to skip blueprint review or independent preflight.

## 5. Rejected Alternatives

### Option (reuse-q1): Treat the vertical probe as another Q1/CB0 arm

- **Why rejected**: Q1's envelope is explicitly one-time and non-transferable, and it excludes Agent/Plan behavior. Reuse would violate the adopted decision and confuse architecture evidence with `F-GATE` evidence.

### Option (five-envelopes): Give each validation step its own decision, blueprint, and renewable budget

- **Why rejected**: it would turn one falsification question into an open-ended program and make `REVISE` function as an automatic retry license.

### Option (generic-agent-query): Let the Agent submit `policy_ref + arbitrary bind/select/expect`

- **Why rejected**: that is P1/A1 authority, not the declared P0/A0 probe. It would simultaneously test contract selection, Policy authority, field access, and result semantics, making failures uninterpretable.

### Option (query-with-hidden-validation): Call the surface Query while scoring Agent-authored expectations

- **Why rejected**: Query rows and Validation expectations are distinct product meanings. The probe keeps expectations server-owned and labels fixture kind explicitly.

### Option (direct-ports-only): Avoid field navigation so D04 can remain deferred

- **Why rejected**: the intended semantic-addressing design relies on paths such as `pair.person2.age`. A narrow paired navigation/authorization test is cheaper and more honest than pretending navigation is already solved.

### Option (current-lowering-oracle): Preserve current asymmetric join lowering because it is observable

- **Why rejected**: construction legality and observable implementation behavior do not establish intended semantics. Both SC-01 candidates must be preregistered.

### Option (single-model-smoke): Use whichever one model/key is readily available

- **Why rejected**: one model cannot expose model dependence. It may produce an explicitly labeled smoke result, but cannot pass the Agent-fidelity dimension.

### Option (aggregate-replay): Report replay as one Boolean derived from `row.explain()`

- **Why rejected**: live association, frozen artifact Explain, deterministic re-execution, detached reconstruction, mutation isolation, and historical product replay require different materials and support different claims.

### Option (production-spike): Add provisional schemas to public routes/SDKs and stabilize them later

- **Why rejected**: the experiment would create compatibility pressure before the semantic and authority contract survives evidence. Disposable scaffolding must remain isolated.

## 6. Supporting Evidence

1. **Exception boundary** — the candidate §0.4 (lines 80–91) and Phase 1 entry (lines 1805–1815) require a separately named, capped, disposable exception that is not product approval. Because the candidate is non-authoritative, the user's 2026-08-11 direction is the immediate drafting authority.
2. **Q1 non-reuse** — adopted Q1 §4.2 (lines 91–114) makes its envelope non-transferable/non-renewable and requires later discovery to revisit `P-GATE`; §4.3 (lines 116–129) leaves Agent/Translator out of CB0.
3. **Semantic paths and ownership** — candidate §6.1–§6.5 (lines 438–564) distinguishes semantic ports, authored and lowered identities, occurrence-qualified paths, generated contracts, and `bind/select/expect` meanings.
4. **Query versus Validation** — candidate §11.1–§11.3 (lines 1110–1168) preserves different product semantics over a shared EvaluationQuery seam; complete zero rows remain empty query results, not denial.
5. **Result completeness** — candidate §6.6 (lines 585–606) distinguishes complete/incomplete/unknown results and requires underdetermined expectations under truncation or insufficient proof.
6. **SC-01** — the disposition lines 85, 148, 261, and 318 establish that asymmetric `join × Any` is observable but semantically untested and must be preregistered in both forms. At the current code pin, `test_rule_expr.py:329–338` tests construction only; `rule_expr_lowering.py:764–799` filters joins whose endpoints are absent from a branch.
7. **SC-02** — the candidate lines 488–498 and compiler gate lines 1944–1957 require authored→lowered one-to-many lineage. At the current code pin, `rule_expr_lowering.py:801–829` creates a local alias map that is not itself a durable authored-lineage contract.
8. **Agent thresholds** — candidate Plan Lab lines 1893–1925 requires per-risk preregistration, zero accepted semantically wrong safety-critical requests, abstention/review for ambiguity, and a candidate routine equivalence threshold of at least 90%. Dual-model execution is an additional 2026-08-11 user lock, not a claim about prior design text.
9. **Replay honesty** — candidate lines 1267–1281 and 1963–1965 require exact pinned materials or explicit unavailability and forbid blending old result identity with new evidence. The disposition lines 194–200 and 289–295 require replay level × artifact availability to be explicit.
10. **Open decisions** — candidate §20 (lines 2050–2071) leaves D02–D11 open and describes D02–D06 plus minimum D10–D11 only as sequencing guidance, not authorization.
11. **Shipped/target boundary** — the archived shipped-alignment audit lines 137–157 pins the full-read evidence for current Meander/FactGraph statements; lines 197–201 keeps Policy compiler/evaluator contracts, Run/replay, L1/MCP, and cross-repository migration classified as future capability rather than shipped behavior.

## 7. Consequences

### 7.1 Downstream unblocking

If adopted, this decision would unblock only a request to draft one paired, numerically capped vertical-probe blueprint/audit. It does not unblock execution or production implementation.

### 7.2 Required blueprint obligations

The future blueprint must turn every §4 lock into a named preflight check and provide:

- exact branch/repository pins and an isolated artifact path;
- numeric cumulative caps and termination behavior;
- P0/A0 field-ownership matrix;
- experimental-schema marking and non-export verification;
- open fixture/oracle matrix and independent review record;
- SC-01 paired candidate fixtures and SC-02 lineage acceptance tests;
- Step 3 deterministic gate before model calls;
- two pinned model arms, frozen thresholds, retry/invalidation rules, and separate credential/egress approval points;
- R0–R4 replay reporting and availability states;
- compatibility/no-side-effect checks;
- evidence-to-D02–D07/D10–D11 matrix;
- one final `PROCEED_TO_ADR_CANDIDATES / REVISE / STOP` disposition.

### 7.3 Product and market consequence

No outcome changes `P-GATE`, `D01`, or `STOP-except-discovery`. Desk research remains research; this engineering probe remains architecture evidence. External workflow, source access, reviewer value, buyer, and budget evidence still require a later product-validation decision.

### 7.4 Implementation consequence

A favorable probe cannot be merged as production behavior. Formal landing still requires, in order:

1. separately proposed and adopted evidence-supported ADRs;
2. explicit cross-repository ownership and version contracts;
3. one or more implementation blueprints whose joint changes are reviewable and reversible;
4. independent preflight, scoped execution authorization, implementation, tests, and audit;
5. a separate product/pilot authorization where the work would move beyond internal architecture evidence.

### 7.5 Compatibility consequence

Shipped Plan v3 and eager proof behavior remain the compatibility floor throughout this probe. Experimental code cannot modify or write their state, and target behavior cannot be reported as shipped.

## 8. Acceptance Criteria

The decision is honored only if all applicable checks hold:

- [ ] The file is explicitly adopted before any downstream blueprint is drafted.
- [ ] Blueprint drafting, review, preflight, `scoped`, execution, BYOK, and data egress each receive the required separate authorization.
- [ ] Q1 and CB0 remain unchanged; CB0 assets and gate state are not consumed or reused.
- [ ] One decision, one paired blueprint/audit, one fixture lineage, one disposable harness lineage, and one final report/audit lineage cover the full probe.
- [ ] Numeric calendar, labor, fixture, compute, model-call/cost, retry, and repair caps are accepted before execution.
- [ ] The P0/A0 ownership matrix prevents Agent control of Policy, paths, projection, expectation kind, config, and verdict.
- [ ] Every experimental schema is non-public/non-normative and absent from production exports/routes/migrations/docs.
- [ ] Step 2 freezes Query and Validation fixture kinds, zero-row/incomplete/error distinctions, field navigation, oracle, and Agent-return interpretation.
- [ ] SC-01 preregisters both semantic candidates with paired observable fixtures before compiler execution.
- [ ] SC-02 machine-checkable authored→lowered lineage is a Step 3 exit gate.
- [ ] Step 3 passes before any scored model call; models do not rescue a failed deterministic core.
- [ ] Two materially independent model configurations, prompts/schema/cases/oracle/normalizer, thresholds, denominators, retry rules, and failure handling are frozen before the first scored call.
- [ ] Agent results are reported per model and risk class; no pooled score hides failure or unresolved status.
- [ ] Replay is reported independently at R0–R4 plus artifact availability; no aggregate replay pass is used.
- [ ] Current/latest state is never used to fill missing historical material; mutation creates a comparative Run.
- [ ] Every D02–D07/D10–D11 row is classified by actual evidence, and no D is adopted by this probe.
- [ ] Kill criteria, invalidation, and budget exhaustion end the envelope without automatic rerun.
- [ ] The final disposition is exactly `PROCEED_TO_ADR_CANDIDATES`, `REVISE`, or `STOP`, with independent contract/compiler/Agent/replay/compatibility/product dimensions.
- [ ] Any later ADR, source implementation, migration, or product work is separately authorized.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-11 | proposed | Decision drafted | Drafting authorized by the user's request to absorb six corrections into the five-step vertical-probe decision. Three pre-draft read-only checks covered source mapping, workflow authority, and red-team boundary attacks. No adoption, blueprint, experiment, model call, or source implementation is authorized. |
| 2026-08-11 | proposed | Independent draft review hardened the contract | Governance review found no authority blocker and added the independent-preflight/standalone-synthesis clarification. Red-team review's disposition-closure, P0/A0 operand ownership, Query/Validation scope, dual-model precedence, and replay/Step-3 findings were applied; follow-up found no blocker and its two remaining majors were applied. A separate final citation audit returned `CLEAR`. Status remains `proposed`. |
| 2026-08-11 | adopted | Decision adopted by user | Adopted without revision to the substantive decision contract. `OBL-Q2-BP-01..03` below become mandatory obligations for any separately authorized consuming blueprint. No blueprint, source change, model call, credential/data-egress use, or execution is authorized by adoption. |

Status transitions are appended as new rows when they happen.

### 9.1 Adoption-turn blueprint obligations

These obligations are non-blocking for adoption but mandatory in the gate checklist of any future consuming blueprint. Their durable proximate source is the user's 2026-08-11 adoption turn. The blueprint must map each ID to a concrete fixture/protocol/gate and its paired audit must verify the mapping.

| ID | Mandatory blueprint-stage obligation | Closure evidence |
|---|---|---|
| `OBL-Q2-BP-01` | Add two low-cost fixtures: **SC-12**, distinguishing whether DNF branch-limit overflow is a publication-time capability rejection or a request-time execution failure; and **AC-21**, exercising collision between the synthetic `__query__` head namespace and an authored predicate. | Named paired fixtures, expected failure owner/stage, diagnostics, and no silent fallback or namespace capture. |
| `OBL-Q2-BP-02` | Blind every human-scored judgment whose rubric includes semantic-intent match or final-answer faithfulness. The grader must not know the model identity or run identity while scoring; mechanical schema/canonical-equivalence checks remain mechanical. | Pre-registered blinding method plus retained per-case judgment and adjudication records. |
| `OBL-Q2-BP-03` | Prevent parked-envelope proliferation: while CB0 and this Q2 probe are both non-terminal, no third discovery-envelope proposal is admissible. At least one must first reach a terminal state through completed execution or formal withdrawal. | Blueprint entry gate records current CB0/Q2 state and rejects progression if both remain non-terminal. |
