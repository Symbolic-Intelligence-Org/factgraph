# Q20 Decision: FactGraph product authoring, semantic Scenario, and Explain interface

- Status: adopted
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Authority: the user's 2026-08-14 explicit authorization to implement the
  agreed FactGraph product-interface design continuously, followed by one
  review. This locks only FactGraph and the thin Agent ingress bridge; it does
  not authorize Meander source custody, Agent business logic, actions, or a
  policy registry.
- Inputs:
  - [Q20 versus-shipped audit](../../../audit/active/2026-08-14_factgraph-product-interface-vs-shipped.md)
  - [Q18 final closure](2026-08-14_q18-factgraph-final-closure-contract.md)
  - [Q19 Policy authoring](2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
  - 2026-08-10 Meander product-design session export, as rationale only
- Outputs / Downstream:
  - [Q20 implementation blueprint](../../../blueprints/archive/2026-08-14_factgraph-product-interface.md)
- Branch: `codex/v0.3.0-impl-factgraph-product-interface-2026-08-14`
- Depends on: Q18, Q19

> Q20 is additive. It preserves Q18 V1 deterministic artifacts and Q19's
> typed Policy façade. It supersedes only the stated Q18 V1 restriction against
> a configuration-bearing *parallel V2* profile. It does not retrofit changing
> fields into V0/V1 identities or claim that probabilistic execution is
> portable across Native, Soufflé and ProbLog.

## 1. Problem

FactGraph now has the hard logical substrate: typed Query compilation, immutable
Policies, a deterministic Scenario effective world, sealed run/replay, native
policy evidence, and a narrow cross-engine deterministic profile. Its product
surface remains uneven:

- authoring metadata and direct builders are not symmetric for Rules and
  Policies;
- a Scenario cannot truthfully carry evaluator-visible probability semantics
  and safe provenance under the user-friendly `meta=` spelling;
- old engine configuration is tied to unstable lowered branch identifiers;
- V1 Explain is correct but protocol-shaped rather than a stable business data
  surface; and
- Agent extraction provenance has no neutral, durable handoff shape.

The solution must make the intended AgentPlan/Meander consumer expressive
without converting FactGraph into a catalog, source-record service, policy
decision point, or a second evaluator.

## 2. Scope

This decision locks five coordinated, additive product contracts:

1. symmetric Rule/Policy builder and asset metadata surface;
2. explicit policy-level weighted exclusive choice semantics;
3. Scenario V2 typed metadata/provenance and execution semantics profiles;
4. structured result/Explain presentation data; and
5. a safe provenance-reference boundary and Agent write compatibility bridge.

## 3. Non-scope

- Policy registration, `query("policy-id")`, policy assignment or publication.
- Rule/Policy mutation, AST patching, `without_rule`, or mutable what-if state.
- General engine callback dictionaries, arbitrary extension code or silent
  native fallback.
- General probabilistic intervals, possibilistic semantics, PyReason V2,
  generic probability threshold truth, or portable probability parity.
- A global closed world, general NAF/why-not proof, bags, recursive language
  extensions, Action/PEP execution, or SourceRecord lifecycle/ACL/retention.
- Meander's authority/admission policy or AgentPlan translation/product UI.

## 4. Decision

### 4.1 Symmetric SDK authoring, distinct compilation responsibilities

FactGraph exposes both direct and staged authoring forms:

```python
rule = fg.build_rule(id="eligible", version="1", meta=AssetMeta(...), ...)
rule_draft = fg.rule_builder(id="eligible", version="1", meta=AssetMeta(...))

policy = fg.build_policy(id="ranked_people", version="1", meta=AssetMeta(...), build=...)
policy_draft = fg.policy_builder(id="ranked_people", version="1", meta=AssetMeta(...))
```

`fg.policy(...)` and Q19's `PolicyDraft` remain concise compatibility aliases.
An `AssetMeta` is descriptive and presentation-oriented: a non-empty bounded
name, optional bounded description, and canonical deduplicated tags. It has a
strict canonical descriptor codec/digest and never silently changes a
Rule/Policy logical digest. Product Rule/Policy wrappers carry it separately;
raw values have the explicit `asset_meta=absent` state. Each side uses an
`asset_binding_digest = target logical identity + descriptor digest/absent`
so a descriptor from target B cannot be spliced onto target A. V2 runs capture
the complete descriptor snapshot, binding digest and descriptor digest for each
primary/candidate side, rather than relying on an ambient lookup.

The two builders deliberately do not collapse into a generic compiler:

- Rule builder owns SDK Rule construction and graph/schema resolution into a
  resolved Rule bundle.
- Policy builder owns local, typed composition of already-resolved Rules.

`build_rule` returns a product Rule wrapper containing a fully resolved Rule
bundle plus its asset descriptor; it is immediately valid for `.use(...)` and
`fg.query(...)`. Its direct form accepts the established SDK Rule body and a
complete semantic-port declaration, and its staged builder produces exactly the
same wrapper. `build_policy(build=...)` creates one builder and invokes the
callback on that *same* builder; it cannot accept foreign handles or construct
a second address space.

`draft.use(rule, as_="alias")` stays the primary local occurrence syntax. It
declares a typed local occurrence, not a global registration; graph scope is
trusted schema/contract resolution only. Convenience `occurrence(...)` may be
an alias but an `occurrences={...}` configuration bag is not the primary API.

### 4.2 Logic topology versus stochastic semantic topology

`all(...)` and `any(...)` remain pure, deterministic logical nodes. They carry
no generic engine settings, probability, or timeout kwargs. An authored
`WeightedChoice` is instead a distinct immutable semantic node:

- one container has a stable node id and a non-empty ordered-canonical arm
  inventory; each arm has a unique stable arm id, a positive exact probability,
  and one nested logical condition;
- one grounded selection key is an ordered tuple of resolved semantic addresses
  which must be branch-total in every arm; the key defines the categorical
  random-variable scope;
- the initial kind is `exclusive`: exact probabilities use one canonical
  bounded finite decimal-string codec (not binary float), permit no zero-weight
  arm, and sum exactly to one; this lowers as a ProbLog
  annotated disjunction, not a set of independent weighted clauses;
- the node has a stable structural id, policy digest contribution, compiler
  lineage and Explain projection;
- it is initially meaningful only under the V2 ProbLog profile; Native and
  Soufflé receive a typed unsupported result; and
- ordinary `Any` must never be reinterpreted as a stochastic choice.

`StochasticChoice` names the later family. Independent causes/noisy-OR,
interval probabilities, correlations and priority/first-match are not hidden
variants of the initial `WeightedChoice` and remain out of scope.

An authored product Policy that contains a choice is a V2 target. Its V2 query
terminal compiles the deterministic logical skeleton plus the sealed choice
topology only under an explicit compatible V2 profile. Legacy `.compile()`,
`.evaluate()` and V1 deterministic `.plan()` reject such a target before
execution; they never discard a choice sidecar to obtain an ordinary Policy.

### 4.3 Scenario metadata: one ergonomic spelling, three typed lanes

The principal SDK form may be concise:

```python
scenario.set(Person.risk_flag, alice, True, meta={
    "raw_kind": "probabilistic",
    "bound": [0.8, 0.8],
    "source": {"ref": "meander:source:…", "locator": {...},
               "content_digest": "sha256:…", "origin_role": "scenario_hypothesis"},
    "note": "operator supplied counterfactual",
})
```

This is not a free JSON bag and is never passed through to ledger `meta`.
The SDK immediately and fail-closed lowers it into:

1. **Fact semantics** — `raw_kind` and canonical `bound`, the only lane visible
   to engine materialization. It contributes to the semantic effective-world
   digest and must reach result certainty, replay and Explain.
2. **Provenance** — ordered `ProvenanceRefV1` values (source reference, bounded
   typed locator, content digest, origin role and optional neutral admission
   reference). This is opaque/safe metadata for Explain/audit and does not
   become an engine fact or authority decision.
3. **Display annotation** — bounded note/labels for presentation only.

The initial probabilistic semantic lane accepts only
`raw_kind="probabilistic"` with a finite exact point bound `[p, p]` in the
same canonical decimal codec as the V2 profile. Intervals, possibilistic bounds,
unconfigured raw kinds, boolean coercion and extraction-quality confidence
reject. A deterministic V2 or portable V1 profile rejects any non-empty fact
semantics before an engine is called.

Caller-provided `run_id`, witness identity, source-kind, lifecycle, authority,
admission decision, raw content, ACL/tenant data, arbitrary nested payloads,
and `confidence` reject. The resolver itself adds non-overridable
`run_local`/`scenario_synthetic`/support-or-mask classifications.

`ProvenanceRefV1` and its locator are closed tagged unions with bounded field
length, depth and cardinality; source refs are canonicalized/deduplicated by
their full wire identity and `origin_role` is an enum. A single `source` is
ergonomic shorthand for a one-item `sources` tuple. Fact semantics apply only
to a synthetic fact-producing operation. `without_*` may carry provenance and
display annotations but no fact semantics; a multi-member operation must use
per-member metadata or reject a semantic metadata request. Two statements that
would produce the same effective synthetic tuple with different semantics
conflict. Same semantics may merge only canonical provenance/display lanes;
that merge never changes witness identity or the semantic relation digest.
Baseline raw semantics/provenance are captured with the selected view too, not
only on Scenario synthetic facts.

The run must seal both lanes:

- `semantic_world_digest`: effective tuples plus fact semantics;
- `resolution_evidence_digest`: normalized premises, provenance/display
  metadata, synthetic/masked witness mapping and closure information.

Changing a probability changes evaluation semantics. Changing source/provenance
does not claim to change logical rows, but produces a distinct traceable run
and Explain identity. Baseline support never becomes a scenario source merely
because it was masked by an effective-world operation.

Display annotations follow the provenance/evidence lane: they do not change a
logical row anchor, semantic-world digest or an already computed certainty, but
they do change the resolved-trace, run and product-explanation identity. A
result may reuse a sealed semantic observation only when its separately sealed
resolution-evidence lane is also supplied; it may not relabel a prior run.

This is a parallel `ScenarioSpecV2` / `EffectiveWorldV2` / replay family.
V1 remains readable and behaviorally frozen.

### 4.4 Execution-semantics profile and stable attachments

`EvaluationExecutionProfileV2` is an immutable, strict codec that pins engine,
adapter/compiler versions, a typed semantic model, resource/capture policy and
all target attachments. It replaces neither V1 deterministic profiles nor the
legacy V0 `ProbLogConfig`/`PyReasonConfig` compatibility surface.

The profile itself is captured as canonical bytes in replay, with strict
decode/reseal, depth/size caps and no live profile registry, callback or opaque
dict. Any profile-body, engine pin or attachment splice rejects before replay
or engine execution.

The SDK form is compact but stable:

```python
profile = (
    fg.execution.problog(name="risk-v1")
      .fact_semantics(identity_probability=True)
      .for_occurrence(older, fg.problog.occurrence_semantics(...))
      .for_rule(eligible_rule, fg.problog.rule_semantics(...))
      .for_choice(source_choice, fg.problog.choice_semantics(...))
      .build()
)
```

Bindings use target/Rule pins and authored occurrence/node ids, never lowered
`c0`/`c1` branch names. Repeated `for_rule`/`for_occurrence` calls form a
canonical set; conflicting duplicate attachments reject. `use/all/any` do not
grow `engine_params` kwargs. An optional `handle.with_execution(...)` may be a
syntax helper only if it produces the same detached profile binding rather than
mutating the Policy.

The initial V2 models are:

- `DeterministicSemanticsV2`, preserving V1-style behavior; and
- `ProbLogPointSemanticsV2`, an explicit `independent_bernoulli_v1` model for
  canonically declared point-probability facts and explicit weighted choices.

Only the latter accepts probabilistic Scenario facts or choice models. A
`for_choice(...)` attachment may validate/activate an already-authored choice
model but never overrides a choice's authored arm weights. `for_rule(...)` and
`for_occurrence(...)` are independent, canonical attachment sets; any one
lowered occurrence matching both is a typed overlap conflict, not implicit
precedence. Attachments are a closed union: explicit Rule pin, exact Policy
digest + authored occurrence alias + Rule pin, or exact Policy structural node
id. Candidate attachments name the candidate target explicitly; matching an
alias such as `older` on the other side never inherits a setting. One authored
occurrence may expand to multiple lowering aliases only by total verified
lineage expansion, never by exposing those aliases publicly.

It is ProbLog-only. Native/Soufflé return typed unsupported results. The
portable three-engine profile remains deterministic and cannot be used to
silently project a probability into a boolean result.

ProbLog V2 has its own canonical result frame with `canonical_engine=problog`.
Each row retains a value-only selected-row identity and a separately sealed
point-probability observation/certainty. V2 point-probability initially exposes
only `rows` plus certainty and comparison of those observations. It rejects
`exists`, `count`, `set_equals`, boolean expectations and an implicit `p > 0`
truth conversion until a separately typed probability expectation is adopted.
Zero rows mean no observed supported row, not a probability/boolean proof.
Native/Soufflé frames are typed `unsupported`, not fabricated canonical frames.

The declared point decimal is exact at the Scenario/profile boundary, but the
current ProbLog adapter has an explicit `problog_float64_v1` materialization
boundary. Every successful frame seals the declared decimal, float64 hex and
rendered export text (or `omitted_zero`); Result/Explain expose that capture.
An observed row probability is therefore an engine observation, not a claim
that ProbLog evaluated arbitrary-precision decimal arithmetic.

`EvaluationRunV2` is a new strict tagged run/replay carrier, never a sidecar
inside `EvaluationRunV1`. It seals the V2 plan/target and asset bindings,
baseline/effective/candidate V2 worlds, full V2 profile bytes, resolved
attachments, per-engine frames, selected-row observations, expectation support
state and a replay payload. Its digest binds all of those objects. V1 may be
opened through a read-only V2 view adapter with an explicit source-protocol
discriminator and `not_captured` V2 fields; it is not rewritten or resealed as
V2.

### 4.5 Scenario what-if and immutable program variants

Scenario continues to change only grounded extensional run-local effective
facts. It supports set/add/exact-set/without/entity/relation operations under
the existing resolver rules, now with V2 typed metadata where appropriate. It
does not remove or patch Rules/Policies.

A Rule/Policy what-if is still `candidate=<independently compiled target>`.
Base/candidate run against the same sealed effective V2 world, semantic model
and environment pins. Target-specific attachments and asset descriptors resolve
and seal separately for the primary and candidate sides; a pin that does not
belong to its exact side rejects. The result exposes input/program/result/
evidence differences without claiming causality or policy authorization.

### 4.6 Structured Result and Explain presentation contract

V0 `EvaluateResult`, `EvaluateRow`, `.close()`, and outer
`Explanation.repr`/`.narrate()` remain untouched.

V2 adds a product-facing, immutable read facade over a sealed V1/V2 run:

- `ResultViewV2`, `RowViewV2`, `SummaryViewV2`, and `ExpectationViewV2` make
  side/mode/completeness/anchors explicit while retaining set semantics;
- a row view may turn its own explicit anchor into an Explain target, but never
  selects an implicit first row; it has no fabricated V0 `.close()`;
- `EvaluationExplanationDataV2` is the machine contract with identity,
  canonical `query_descriptor` (target/bind/select/scenario, never raw Agent
  prompt), outcome, execution/profile, policy topology/projection, Scenario
  premises, EvidenceGraph, safe provenance, comparison/diff and boundary
  sections; and
- `repr`, `narrate`, and optional HTML/text renderers are pure consumers of the
  structured data. Business UI and Agent logic consume the data, never parse
  rendered prose.

An explicit positive-row native recomputation against the sealed captured world
may produce EvidenceGraph and Policy overlay only for deterministic V2 runs.
For a portable deterministic run it is labeled native inner evidence with
`proof_parity=not_claimed`. A ProbLog-only probabilistic run has a separate
typed evidence-support state and must never fabricate native deterministic
EvidenceGraph. Summary or zero-row Explain has no fabricated negative
graph/proof. Ambiguous projected rows, pin mismatch, unavailable engine context
and replay mismatch fail closed.

The evidence-support union is closed: `native_detached_recomputed`,
`portable_native_inner_not_parity`, `problog_trace_captured`, `not_captured`,
`not_available`, and `unsupported`. The latter three carry a typed reason and
no fake graph. A choice topology/projection may be present without an engine
proof, but must say so. Product data exposes only a sanitized source/evidence
view: raw generic `EvidenceTree.Source.meta` is never reclassified as
provenance or returned without an allowlist. Safe provenance joins through
sealed premise/operation/ref identities, not guessed strings.

When a V2 product view opens an older V1 run, every V2-only field is explicitly
`not_captured` or `not_applicable`; absence is never synthesized as empty asset
metadata, deterministic semantics, baseline provenance, or an engine proof.

### 4.7 Provenance boundary and Agent compatibility bridge

`ProvenanceRefV1` is the only new FactGraph cross-boundary source value. It
holds safe opaque identity/locator/digest/role references, not source content,
trust, ACL, tenant or retention policy. Meander remains the owner of
`SourceRecord`, admission, authority, source resolution and privacy controls.

Its strict wire includes an opaque source id, a tagged bounded locator,
optional sha256 content pin, closed origin role, and optional opaque admission
reference. It never carries raw text (including extraction raw text), free
source metadata, credentials or access policy. Product Explain keeps baseline
captured support separate from effective synthetic premise provenance; a masked
baseline witness cannot be reclassified as a Scenario source.

The Agent draft/write seam gains a compatibility projection from rich extraction
provenance to `ProvenanceRefV1` and legacy `source/source_loc` mirror fields.
It must stop emitting unsupported user-authored `confidence` into core write
metadata; extraction confidence remains workflow-only and is never
automatically translated into a probabilistic premise. A rich reference is not
written as generic ledger meta or treated as persistence. Existing ledger input
identity and annotation behavior stay stable;
one-to-many FactBinding/SourceRecord storage is a Meander follow-up, not hidden
in a FactGraph JSON metadata field.

## 5. Rejected alternatives

### Generic `meta` passthrough

Rejected because ledger metadata includes ingest/approval semantics and would
either be ignored by execution or falsely claim persistence/authority.

### Engine kwargs on `use`, `all` or `any`

Rejected because occurrence/topology do not map one-to-one to lowered DNF
branches; such arguments would bind silently to compiler accidents.

### Treat every `Any` as weighted choice

Rejected because existential OR has neither exclusivity nor an event model.

### One source DTO shared by EvidenceGraph and SourceRecord

Rejected because Evidence `Source` is engine proof support and SourceRecord is
external custody/authority. Conflating them leaks authority into logic.

### Replace legacy result/explain objects

Rejected because live row closing and sealed run replay have deliberately
different safety properties. A facade preserves both rather than lies about
their equivalence.

## 6. Consequences

1. New V2 contracts must have strict canonical codecs, caps and splice tests;
   old V0/V1 bytes stay valid and unchanged.
2. Every Scenario semantic must travel end-to-end through resolver, isolated
   relation, engine, result, replay and Explain before its SDK `meta` spelling
   is public.
3. Every V2 engine attachment must resolve against a pinned authored target;
   no generated branch-id API is public.
4. Docs/examples must distinguish deterministic portable parity from ProbLog
   probabilistic execution and label Explain evidence honestly.
5. Agent code changes are limited to a non-authoritative compatibility adapter
   and validation; no Agent product behavior is introduced.

## 7. Acceptance criteria

- [x] Rule and Policy have symmetric builder/direct SDK entry points with
  AssetMeta, while raw compatibility APIs remain valid.
- [x] Policy use/occurrence remains local, typed and graph-schema-resolved;
  no registry/string lookup appears.
- [x] WeightedChoice has stable topology/digest/Explain representation and a
  typed engine support matrix.
- [x] Scenario `meta` strictly lowers into semantic/provenance/display lanes;
  semantic and resolution-evidence digest lanes are independently verifiable.
- [x] Exact-point probabilistic premises execute and replay under the sealed
  ProbLog V2 profile, while Native/Soufflé/portable reject them explicitly.
- [x] Stable Rule/occurrence/choice execution attachments work without lowered
  branch IDs, with duplicate/conflict/splice rejection.
- [x] V2 product views and structured explanation data render policy,
  Scenario, EvidenceGraph and provenance without prose parsing or false
  negative proof.
- [x] Agent/source bridge preserves legacy write compatibility and does not
  submit rejected `confidence` metadata.
- [x] Existing V0/V1 and deterministic Native/Soufflé/ProbLog regression
  suites remain green.

## 8. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | adopted | User locked product-interface direction | Symmetric authoring, strict Scenario meta, stable execution profile, weighted choice, structured Explain and safe provenance were accepted together. |
| 2026-08-14 | implemented | Q20 implementation and independent review complete | The sealed V2 product surface, strict source bridge and public executable tutorial satisfy the acceptance criteria; support limits remain explicit in module docs. |
