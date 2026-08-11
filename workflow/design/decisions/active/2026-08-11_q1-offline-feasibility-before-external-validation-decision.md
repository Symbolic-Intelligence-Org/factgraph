# Q1 Decision: 先做离线覆盖型可行性验证，后做外部产品验证

- Status: proposed
- Created: 2026-08-11
- Last Updated: 2026-08-11
- Authority: proposed design constraint; if adopted, locks the discovery-gate decomposition, evidence boundaries, and experiment ordering before any Meander case-bundle feasibility blueprint or execution.
- Inputs:
  - [`meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md`](../../design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md) §0.4, §17 Phase -1–1, §18.7, §20 D01; 2235 lines; SHA-256 `750ced2141e9d8c20400c5ed59d6c439707b32fb363919ab7b1533918f2a9e1b`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md) lines 34–35, 71–80, 95–107, 117–126; 382 lines; SHA-256 `7449dd6041bea639aeddecc6903e04b03ce0ead1c9ebd38a7052c67bc6eb45f2`
  - Archived Stage 1 audit [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](../../../audit/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md) lines 96, 127, 157, 173–175, 201–205; 394 lines; SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`
  - Archived Option 1 [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](../../../blueprints/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1.md) and its [`paired audit`](../../../blueprints/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1.audit.md)
  - Product research package, as research evidence rather than design authority:
    - [`01_执行摘要与最终判决.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/01_执行摘要与最终判决.md>) lines 154–168; 186 lines; SHA-256 `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d`
    - [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>) lines 17–30, 98–106, 124–132, 220–225; 227 lines; SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`
  - [`workflow/working/README.md`](../../../working/README.md) lifecycle boundary
  - 2026-08-11 user direction: prior research is sufficient to justify a bounded feasibility experiment; target-account outreach may be deferred; the next priority is a coverage-oriented case bundle and feasibility test; a model API key may be supplied later if an authorized model arm needs it
- Outputs / Downstream:
  - After adoption and a separate user authorization for the next phase: one narrowly scoped case-bundle feasibility blueprint, followed only through separately authorized review/preflight/execution transitions
  - A later, separate product-validation decision/blueprint for real workflow, buyer, access, and budget evidence
  - Future revision of the v0.1.1 candidate's monolithic Gate -1 wording; this decision does not edit that candidate
- Related:
  - Candidate D01 (product wedge and product-gate evidence); this Q1 only decides D01 sequencing and does not close the product-wedge question
  - Candidate §18.1–§18.7 experiments, metrics, comprehension gates, and kill criteria
- Branch: `v0.3.0-q1-meander-offline-feasibility-decision-2026-08-11`

> ADR 4-state lifecycle: `proposed` → `adopted` (current binding constraint, stays in `active/`) → `superseded` or `withdrawn` (moves to `archive/`). This file is currently a proposal. Adoption would close only Q1; it would not automatically authorize blueprint drafting, review, preflight, experiment, implementation, external contact, or use of credentials. Every transition requires separate explicit user authorization.

## 1. Inputs

### 1.1 Existing candidate boundary

The v0.1.1 review candidate preserves two independent questions:

1. whether a source-bound review/challenge mechanism is technically and semantically viable; and
2. whether a real workflow owner, buyer, lawful data path, recurring decision, and budget justify productization.

Its current Gate -1 bundles those questions into one entry condition. In §17 Phase -1 it places 8–10 target-account walkthroughs, a historical case bundle, baseline ablation, reviewer value, data access, and a cost-bearing pilot in one stage before Phase 0/1.

The adversarial verdict remains architecture `REVISE` and product authorization `STOP-except-discovery`. Nothing in this decision converts either verdict into `CONTINUE` for product construction.

### 1.2 New user lock and its evidentiary limit

On 2026-08-11 the user chose to treat the completed desk research and adversarial work as sufficient justification for a **bounded falsification experiment**, and chose the coverage-oriented case bundle as the next priority. Target-account outreach may therefore be deferred rather than block this experiment.

This is a sequencing and resource-allocation decision. It is not evidence that target users obtain value, that a buyer or budget exists, that customer data is legally accessible, or that a cost-bearing pilot is available. Those facts remain unresolved until tested externally.

### 1.3 Why the gate must be decomposed

Keeping external commercial validation as a prerequisite for every offline technical test delays the cheapest way to kill a semantically unsound design. Treating prior research as if it had already passed the commercial gate would make the opposite error: it would turn desk research into fabricated demand evidence.

The smallest honest resolution is to let offline feasibility proceed as discovery while retaining a separate, still-open product gate before productization.

## 2. Scope

This decision locks, if adopted:

1. the separation between an offline feasibility gate and an external product-validation gate;
2. which of those gates is required before each class of downstream work;
3. the order of case protocol, deterministic evaluation, baseline comparison, and optional model/Agent tests;
4. the difference between technical, semantic, reviewer, and market verdicts;
5. the lifecycle of scratch artifacts versus durable evidence;
6. the boundary for sensitive source material and any later BYOK/API-key use;
7. what a pass, partial result, or failure may and may not authorize.

## 3. Non-scope

This decision does **not** lock:

- a final product wedge, buyer, packaging, pricing, deployment model, or sales motion;
- the exact number of future target-account sessions or the method for recruiting them;
- the final CaseBundle schema, case count, domain mix, or durable repository path;
- a model provider, model version, Translator prompt, Agent framework, or credential mechanism beyond the secret-handling invariant in §4.7;
- Policy AST, semantic-port, Query/Scenario, Explain, replay, SourceRecord, Plan, Translator, UI, Package, learning, or Action/Decide production contracts;
- implementation in FactGraph or Meander, production data migration, or public SDK/API syntax;
- a claim that an offline corpus represents market prevalence or real reviewer value;
- closure of candidate D01 as a whole or any of candidate D02–D18.

## 4. Decision

### 4.1 Decompose the monolithic discovery gate

If adopted, the candidate's current Gate -1 is interpreted for downstream planning as two non-substitutable gates:

| Gate | Question | Minimum evidence | Status at adoption | What it may unlock |
|---|---|---|---|---|
| `F-GATE` — offline feasibility | Can the proposed source-bound challenge/replay mechanism conform to a declared semantic contract, remain inspectable, and show a corpus-local increment relative to enumerated baselines? | Pre-registered protocol, development corpus plus sealed holdout, frozen gold, pinned deterministic harness/arms, baseline ablation, replay tests, failure analysis, artifact manifest | Open; executable only after separately authorized blueprint, review, preflight, and execution transitions | Closes only the one non-transferable experiment envelope in §4.2; no automatic next slice |
| `P-GATE` — external product validation | Does a real workflow have an owner, recurring material decision, lawful source access, reviewer value, buyer/budget, and willingness to bear integration cost? | External workflow evidence under a pre-registered product-validation protocol | Open and deferred | Consideration of pilot/productization; never implied by `F-GATE` |

The fixed “8–10 target-account walkthroughs / ≥5 completed” requirement is removed as a prerequisite for `F-GATE`. It is not counted as completed, and the need for external validation is not removed. A future `P-GATE` blueprint must set its own sampling and saturation logic rather than inherit an unexplained count.

### 4.2 Adoption closes only Q1; the experiment envelope is one-time and non-transferable

Adopting this decision would make one `F-GATE` blueprint **eligible to be requested as a separately authorized drafting stage**. Adoption does not authorize that drafting stage, its review, preflight, or execution.

If later authorized through every required transition, this Q1 permits exactly one bounded experiment envelope:

1. one versioned coverage taxonomy and corpus lineage, split into development data and an untouched sealed holdout;
2. one disposable deterministic harness with pinned FactGraph and baseline commits/configuration;
3. the enumerated baseline arms and parity controls required by §4.3–§4.5;
4. one pre-registered final holdout evaluation and one report/audit lineage;
5. a numeric total calendar, labor, compute, and external-model budget fixed in the blueprint before execution.

This envelope is not transferable, renewable, or composable into successive “discovery” slices. It must not produce or depend on a production service, production dependency, customer connector, live workflow integration, public/product API, deployable Translator/Agent service, or product UI. A local disposable inspection surface is allowed only if the future blueprint proves it is necessary to score the named experiment and includes it within the same fixed envelope.

Adoption alone authorizes none of the following. A later blueprint may separately request only the case construction and disposable execution that fit the fixed envelope; every other item remains outside it:

- creation of the case bundle;
- execution of a harness or model;
- changes to FactGraph or Meander source code;
- target-account contact;
- use of private customer data or API credentials;
- Phase 2 or later production work.

Each transition remains separately authorized under repository governance: `decision adoption → blueprint drafting → blueprint review → independent preflight → execution → audit/archive`. Completion or any outcome grants no additional authorization. Any work after the one envelope requires a new decision that explicitly revisits whether `P-GATE` must precede it; `F-GATE PASS` is not a reusable authorization token.

### 4.3 Coverage corpus precedes integrated Agent behavior

The first proposed `F-GATE` blueprint must order work as follows:

1. define the CaseBundle contract, failure-class taxonomy, provenance requirements, perturbation rules, metrics, stop conditions, and machine-readable coverage matrix;
2. construct lawful synthetic, public, or explicitly authorized source-bound cases selected for semantic coverage rather than market-frequency claims, then partition them into a development corpus and an untouched sealed holdout;
3. create human-authored gold interpretation, source bindings, expected logic, ambiguity labels, and test-severity proxies through a role separated from harness/scorer implementation; retain disagreements and adjudication rather than forcing false certainty;
4. seal holdout cases/gold and freeze thresholds plus every scored arm's commit, configuration, contract, and tuning budget before any holdout execution, including deterministic arms;
5. iterate only on the development corpus, then run the pinned FactGraph arm and enumerated non-FactGraph baselines under the parity contract in §4.5;
6. exercise the replay subcontracts in §4.5 rather than infer replayability from stored digests;
7. report per-case, per-class, and coverage-cell results, including abstention, false support, false challenge, and unscorable gaps;
8. leave Translator, Agent Plan, and product UI outside this envelope; they require later decisions if the deterministic core survives.

The initial experiment must not require an Agent or Translator to prove the deterministic semantic chain. Agent Plan fidelity and Translator fidelity remain separate risks with separate verdicts. A generic LLM judge may appear only as a pre-declared comparison baseline inside the same envelope and only after separate credential and data-egress authorization; absence of that baseline limits the allowed conclusion under §4.4.

### 4.4 Verdict dimensions cannot be collapsed

Every experiment report must return independent statuses for at least:

| Dimension | Allowed conclusion from offline evidence |
|---|---|
| deterministic harness feasibility on the pinned corpus/contracts | `PASS`, `FAIL`, or `UNRESOLVED`; no claim beyond the tested versions |
| logical conformance on the sealed holdout and declared taxonomy | `PASS`, `FAIL`, or `UNRESOLVED`; uncovered cells stay `UNRESOLVED` |
| source-locator/integrity conformance | `PASS`, `FAIL`, or `UNRESOLVED` for the declared source contract; not a claim that a source is true or authoritative |
| real-world source authority, freshness, and workflow materiality | Always `UNRESOLVED` without the corresponding external/domain evidence |
| corpus-local increment against explicitly enumerated baselines | `PASS`, `FAIL`, or `UNRESOLVED` only for the baselines actually run |
| unique mechanism value versus relevant incumbent/native QA and a generic LLM judge | `UNRESOLVED` until those applicable arms run under parity; beating only source/checklist baselines is insufficient |
| replay subcontracts | Independently report deterministic re-execution, artifact reconstruction, mutation isolation, and unavailable-source behavior |
| artifact legibility for a named proxy population | Only if independently and blindly tested with a defined task/population; otherwise `UNRESOLVED` |
| real workflow utility | Always `UNRESOLVED` until `P-GATE` supplies representative workflow evidence |
| Translator fidelity | Only after a separately authorized Translator arm; otherwise `UNRESOLVED` |
| Agent Plan fidelity | Only after a separately authorized Agent arm; otherwise `UNRESOLVED` |
| product demand, buyer, budget, and data access | Always `UNRESOLVED` until `P-GATE` evidence exists |

Every `PASS` must be labeled “on the frozen corpus, declared taxonomy, and pinned versions.” No aggregate score may convert an unresolved or failed kill criterion into a pass. Offline proxy metrics must be labeled as proxies and may not be presented as customer evidence.

### 4.5 Baseline and anti-leak discipline

The later blueprint must require:

1. one frozen case identity and source snapshot per arm;
2. strict separation of the development corpus from an untouched holdout whose cases and gold are unavailable to harness/scorer implementers until the scored run;
3. gold authorship/adjudication operationally independent from scored-arm implementation, with disagreement, ambiguity, and exclusion reasons retained; if that independence cannot be achieved, the affected semantic verdict remains `UNRESOLVED`;
4. pre-registered metrics, thresholds, exclusions, commits/configuration, and mapping/tuning budgets before **any** scored holdout arm runs, learned or deterministic;
5. explicit coverage gaps rather than silently interpreting absent evidence as false/pass; the coverage matrix must state each class/cell denominator, positive/negative/unknown/abstain cases, paired perturbations where applicable, and unit of analysis;
6. at minimum source-only and simple deterministic/checklist baselines, plus every applicable native/incumbent QA arm that can accept the declared task contract; a generic LLM-judge baseline is required before any `unique mechanism value` claim;
7. arm parity: the same source snapshot and proposition/claim contract, comparable output contract, the same permitted manual mapping information, explicit tuning/engineering budgets, and versioned configuration; any unavoidable asymmetry is reported rather than hidden;
8. retained raw or per-case normalized results—or lawful durable references from which they can be retrieved—sufficient to recompute every aggregate; a digest verifies integrity of an existing artifact but cannot reconstruct it or recompute a result;
9. separate reporting of false `SUPPORTED`, false challenge, abstention, untranslated/unscorable coverage, latency, proxy reviewer effort where measured, and semantic setup cost;
10. replay tests reported independently:
    - deterministic re-execution with the same readable source/policy/config artifacts must reproduce result and trace fingerprints;
    - artifact reconstruction must prove every required input is readable and digest-matching, or return an explicit non-replayable state;
    - source, Policy, rule, config, or version mutation must create a new comparative Run and must not be presented as replay of the original;
    - deleted, unavailable, or legally non-retainable source material must fail explicitly rather than silently fall back to current state;
    - later model re-translation is a versioned comparison, not a promise of byte-identical replay.

Model-generated labels may be exploratory annotations, but they cannot be the sole gold authority for the same model or product path under test.

### 4.6 Scratch work is not durable evidence

`workflow/working/meander-case-feasibility/` may be used during an authorized execution for disposable scripts, notebook exploration, raw response captures, and temporary outputs. Per [`workflow/working/README.md`](../../../working/README.md), it is gitignored, short-lived, and has no governance metadata.

Therefore an experiment verdict must not depend solely on `workflow/working`. Before execution, the blueprint must assign tracked, durable homes for:

- the protocol and pre-registration;
- a sanitized manifest and case schema;
- reproducible non-sensitive development/holdout fixtures or lawful durable references, with gold access controls and integrity digests;
- the evaluation harness or deterministic test surface;
- per-case normalized results or lawful retrievable result references, run identity, environment/model/config versions, and aggregate/report artifacts;
- the audit and final disposition.

The blueprint may select an existing convention such as `tests/golden/` where appropriate, but this decision does not preselect a path before data sensitivity and module ownership are known.

### 4.7 Sensitive data and later API-key use

Private or regulated source content must not be copied into the repository or assumed safe merely because `workflow/working` is gitignored. If such data is later authorized, it must remain in an approved controlled location; the repository retains only the minimum lawful manifest, opaque locator, digest, and reproducibility metadata allowed by that authorization.

The deterministic first arm requires no API key. If a later Translator, LLM-judge, or Agent arm is separately authorized:

- the user may supply BYOK at runtime through an approved environment/secret mechanism;
- the key must never enter tracked files, notebooks, fixtures, prompts, command transcripts, captured responses, or experiment reports;
- provider, model, prompt, schema, and sampling configuration must be versioned in the run record without recording the secret;
- **credential use does not authorize data egress**: sending any case/source/prompt to a provider requires a separate explicit data-egress approval after source license/legal basis, classification/redaction allowlist, provider retention/training, region/residency, subprocessors or applicable DPA terms, deletion, cache/log, and derived-output handling are recorded;
- “publicly accessible” does not by itself prove that content may be copied, redistributed, or submitted to a model provider;
- source minimization and provider data-handling constraints must be settled in the corresponding blueprint/preflight; without that evidence and approval, the model arm does not run and its verdict remains `UNRESOLVED`.

### 4.8 Promotion, failure, and the existing product verdict

The product authorization remains `STOP-except-discovery`. `F-GATE` is one bounded discovery path within that verdict.

- `F-GATE PASS` means only that the mechanism survived this one pre-registered envelope on the frozen corpus and pinned versions. It closes no other gate, creates no reusable discovery authorization, does not pass `P-GATE`, and does not authorize production or prove a market.
- `F-GATE PARTIAL/UNRESOLVED` records the unresolved cells and ends this envelope. Any repair or narrowed hypothesis requires a new preregistration, a parent link to the immutable original outcome, an explicit diff of claims/thresholds/exclusions, a new untouched holdout, a new decision/authorization, and a fresh cumulative cap. It cannot overwrite or round the original result up to pass.
- `F-GATE FAIL` stops the challenged mechanism or narrows it to the surviving asset. Integrated Agent/Translator/UI work must not be used to rescue a failed deterministic core.
- `P-GATE` remains mandatory before a cost-bearing pilot is described as validated product direction and before horizontal or vertical product construction. Further discovery after this envelope requires a new decision that explicitly justifies why `P-GATE` is or is not yet the next step.

### 4.9 Candidate-lineage consequence

If this decision is adopted, the next authorized revision of the v0.1.1 design lineage must update at least §0.4, §17 Phase -1/Phase 0/Phase 1 entry language, and §20 D01 so that:

1. `F-GATE` and `P-GATE` are explicit and independent;
2. external outreach no longer blocks offline feasibility;
3. external demand/data/budget evidence remains open;
4. passing `F-GATE` cannot be read as general implementation authorization.

This proposal does not modify the current review candidate and does not silently supersede it.

## 5. Rejected Alternatives

### Option (a-monolithic-gate): Keep target-account validation as a prerequisite for every offline experiment

- **Why rejected**: It delays the cheapest semantic falsification and makes technical learning contingent on commercial coordination. The two evidence classes answer different questions and need not occur in that order.

### Option (b-market-passed): Treat prior desk research and adversarial review as completion of the product gate

- **Why rejected**: Research can justify what to test; it cannot establish a concrete workflow owner, lawful data access, buyer/budget, recurring decision, or willingness to pay.

### Option (c-agent-first): Start with Translator/Agent Plan generation and an end-to-end UI

- **Why rejected**: It combines the deterministic core, semantic translation, Plan fidelity, and presentation into one failure surface. A bad result would be uninterpretable, and a polished result could conceal a failed reasoning core.

### Option (d-working-is-record): Keep the corpus, gold labels, harness, and evidence only in `workflow/working`

- **Why rejected**: That directory is explicitly gitignored, ephemeral, and non-governed. It is appropriate for scratch execution but cannot support audit, replay, or a durable verdict.

### Option (e-model-as-gold): Use the same model family to create and judge the gold corpus

- **Why rejected**: It creates circular evidence and can reward the exact translation bias the experiment is meant to detect.

### Option (f-key-now): Require an API key before the deterministic protocol exists

- **Why rejected**: It adds cost, privacy, and model variance before the non-model semantic path and scoring contract are frozen.

## 6. Supporting Evidence

1. The pinned [v0.1.1 candidate](../../design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md) (`workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md:80-91`, SHA-256 `750ced2141e9d8c20400c5ed59d6c439707b32fb363919ab7b1533918f2a9e1b`) separates product and architecture gates, states that one cannot substitute for the other, and limits ungated work to pure design/audit or a separately named disposable exception.
2. The same candidate (`:1781-1813`) couples target-account walkthroughs and the case bundle in Phase -1 while Phase 0/1 depend on the combined gate. This is the sequencing ambiguity this decision resolves; it is not evidence that either gate passed.
3. Candidate `:1981-1999` keeps workflow ownership, baseline improvement, false support, comprehension, replay/privacy, and semantic customization as independent kill/promotion conditions; `:2046-2071` leaves D01 open and states that it controls whether the assets become a product.
4. The [adversarial disposition](../../design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md) (`workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md:34-35/:71-80/:95-107/:117-126`, SHA-256 `7449dd6041bea639aeddecc6903e04b03ce0ead1c9ebd38a7052c67bc6eb45f2`) directly preserves architecture `REVISE`, product `STOP-except-discovery`, separately authorized budget-capped discovery, baseline discipline, case coverage, and reviewer-value gaps.
5. The archived [Stage 1 audit](../../../audit/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md) (`workflow/audit/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md:96/:127/:157/:173-175/:201-205`, SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`) pins the research inputs, preserves the dual verdict, and states that future capabilities and preflight remain unauthorized.
6. The product research package—[`01_执行摘要与最终判决.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/01_执行摘要与最终判决.md>) (`:154-168`, 186 lines, SHA-256 `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d`) and [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>) (`:17-30/:98-106/:124-132/:220-225`, 227 lines, SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`)—supports source-bound review, ablation, falsification-first experiments, and explicit stop conditions. It remains non-authoritative research evidence, not proof of demand.
7. [`workflow/working/README.md`](../../../working/README.md) (`workflow/working/README.md:3-28`) defines working artifacts as gitignored, short-lived, and unsuitable for persistent truth, requiring valuable artifacts to be promoted through a formal slice.
8. [`workflow/CADENCE.md`](../../../CADENCE.md) (`workflow/CADENCE.md:87-94/:108-128`) keeps the user as decision-maker and makes Q closure, synthesis, and blueprint separate stages; adoption therefore cannot auto-authorize blueprint drafting.
9. The 2026-08-11 user direction is authority for choosing the next bounded decision path. It is not empirical product evidence; §1.2 and §4.4 preserve that distinction.

## 7. Consequences

### 7.1 Downstream unblocking

If adopted, this decision closes Q1 and makes one case-bundle feasibility blueprint **eligible for a separately authorized drafting request**. It does not itself start or authorize drafting, review, preflight, case construction, or execution. Any later blueprint must be narrow enough to preflight independently and must not include production implementation or external-product claims.

### 7.2 Required follow-up actions

The next blueprint must:

1. define the one-time envelope, experiment question, explicit claims/non-claims, numeric cumulative budget, owners, and termination condition;
2. define a coverage taxonomy, development/holdout split, CaseBundle schema, and machine-readable coverage matrix without claiming prevalence;
3. choose durable artifact locations, holdout access controls, and sensitive-data/data-egress controls;
4. pre-register independent gold creation/adjudication, arm commits/configs, parity budgets, baselines, metrics, thresholds, replay tests, and coverage-gap semantics;
5. identify the minimal disposable deterministic harness and prove that it creates none of the prohibited product artifacts in §4.2;
6. keep Translator, Agent Plan, product UI, and external product validation outside this envelope; treat a generic LLM judge only as a conditional baseline under §4.3/§4.7;
7. require separately authorized review and independent preflight before any case construction or execution;
8. end with a final audit and immutable `PASS / PARTIAL / FAIL / UNRESOLVED` disposition by dimension, plus per-case results sufficient to recompute aggregates.

### 7.3 No retroactive authority

Existing research, design candidates, notebooks, or ad-hoc tests do not become governed experiment evidence merely because this decision is later adopted. Evidence must satisfy the future blueprint's pre-registered protocol or be labeled contextual only.

### 7.4 Cross-repository boundary

No FactGraph or Meander repository change follows directly from this decision. If the blueprint later needs code in both projects, ownership, branch, pinned commit, sequencing, and atomic compatibility tests must be named before implementation authorization.

### 7.5 Single-Q synthesis disposition

[`workflow/audit/README.md`](../../../audit/README.md) lines 59–69 makes standalone synthesis optional for a Q1-only slice. This decision records that a standalone synthesis may be skipped because it closes only one sequencing question and points to one possible blueprint. Skipping synthesis does not authorize that blueprint, waive its review/preflight, or bypass the dependency and evidence map required in the blueprint itself.

## 8. Acceptance Criteria

- [ ] Status is explicitly adopted before a consuming blueprint treats any clause as binding.
- [ ] Adoption closes only Q1; blueprint drafting, review, preflight, and execution each have separate explicit user authorization.
- [ ] The consuming blueprint names `F-GATE` and does not claim `P-GATE` passed.
- [ ] `F-GATE` is one non-renewable envelope with a fixed numeric cumulative budget and no prohibited product artifact.
- [ ] Target-account outreach is absent as an `F-GATE` prerequisite but remains an unresolved product-evidence obligation.
- [ ] Case selection is described as coverage-driven, not market-frequency evidence.
- [ ] Development and untouched holdout corpora are separated; gold, thresholds, commits/configs, and tuning budgets are sealed before any scored holdout arm, including deterministic arms.
- [ ] Gold creation/adjudication is role-separated from implementation, and disagreement/ambiguity remains visible.
- [ ] Baseline arms use a parity contract; `unique mechanism value` stays unresolved without applicable incumbent/native QA and generic LLM-judge comparisons.
- [ ] Replay is tested by re-execution, reconstruction, mutation isolation, and unavailable-source behavior; digests are not treated as reconstructable outputs.
- [ ] Technical, semantic, reviewer, Translator, Agent, and product conclusions are reported separately.
- [ ] Every offline pass is scoped to the frozen corpus, declared taxonomy, and pinned versions; real source authority/materiality and workflow utility remain unresolved.
- [ ] A false `SUPPORTED`, silent coverage gap, or source-binding failure cannot be averaged away.
- [ ] Scratch artifacts in `workflow/working` are not the sole source for any final claim.
- [ ] Durable, replayable, non-sensitive evidence locations are assigned before execution.
- [ ] Private data and BYOK secrets remain outside repository artifacts and captured logs; credential authorization never substitutes for explicit data-egress authorization.
- [ ] A pass ends this envelope and authorizes no next slice, production work, or market claim.
- [ ] A partial/fail remains immutable; any repair/narrowing needs a new preregistration, untouched holdout, lineage link, decision, authorization, and cap.
- [ ] No FactGraph or Meander source change occurs under this decision alone.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-11 | proposed | Decision drafted | User authorized the next decision stage after choosing coverage-oriented feasibility as the immediate priority and deferring target-account outreach; no experiment or implementation authorized. |
| 2026-08-11 | proposed | Independent review amendments applied | Closed phase-auto-advance, branch naming, citation precision, renewable-discovery, holdout leakage, weak-baseline, replay, data-egress, and immutable-failure-lineage findings; status remains proposed. |

Status transitions are appended as new rows when they happen.
