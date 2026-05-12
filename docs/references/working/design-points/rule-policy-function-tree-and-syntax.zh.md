# Rule / Policy 功能树与语法边界设计点

Status: working / non-authoritative
Authority: Research note. 本文是后续 blueprint 与模块文档的设计输入，不是当前实现真相。当前实现真相仍以 `src/kernel/sdk/`、`src/kernel/application/`、`src/kernel/core/` 及其模块文档为准。若本文结论被采纳，需要迁移到对应模块 docs 或 architecture principles。

## Question

当前 rule 层已有 `Rule`、`Query`、`Derivation`，后续 evidence / proof / what-if / audit 机制也已经成形。问题是：

- 现有功能树是否应该调整？
- `Rule`、`Query`、`Derivation` 的职责边界是否合理？
- policy / theory 级验证语义应放在哪里？
- 从功能树到具体用户语法，推荐的新形态是什么？

## Current Behavior Snapshot

当前 SDK 面向用户的规则执行主干是：

```text
fg.eval.run(rule_or_query)
fg.eval.evaluate(derivation, mode=...)
fg.eval.accept(candidate)
fg.eval.accept_many(candidates)
```

当前 object 分工大致为：

| Object | Current role | Current execution |
|---|---|---|
| `Query` | Read-side projection over current store | `fg.eval.run(query)` -> rows |
| `Rule` | Named reusable inference relation (`select + where`) | `fg.eval.run(rule)` -> rows |
| `Derivation` | Candidate/materialization producer (`where + head`) | `fg.eval.evaluate(derivation, mode=...)` -> `CandidateSet[]` |

后续 explain / evidence / audit 能力当前挂在：

```text
fg.what_if.check(...)
fg.what_if.diagnose(...)
fg.what_if.why_not(...)
fg.what_if.fact_overlay.check(...)
fg.what_if.fact_overlay.recheck_proof_frame(...)
fg.what_if.rule.disable(...)
fg.what_if.rule.literal_replace(...)
fg.what_if.rule.add_condition(...)
fg.audit.diff_proof_frames(...)
```

这些能力已经能支撑 explainable rule execution：

- specific binding 是否推出；
- 为什么推出 / 为什么没推出；
- finite candidate universe 的 green / red board；
- fact overlay / rule overlay 反事实分析；
- `SupportArtifact` / `ProvenanceEnvelope` / `EvidenceGraph` / candidate evidence tree；
- round events 与 proof-frame diff。

当前缺口不是 evidence，而是 policy / theory 级语义：没有一等公民对象表达一组 rules / derivations / variables / invariants 的整体验证生命周期。

## Proposed Functional Tree

推荐将用户心智树调整为：

```text
FactGraph
├─ schema
│  ├─ compile / validate
│  └─ provenance validation
│
├─ data
│  ├─ read
│  ├─ write
│  ├─ assertions
│  └─ views
│
├─ rules
│  ├─ run(rule | query)
│  ├─ evaluate(derivation, engine=...)
│  ├─ accept(candidate)
│  └─ accept_many(candidates)
│
├─ policy
│  ├─ define(policy)
│  ├─ validate_claim(policy, claim, premises)
│  ├─ verify_invariant(policy, invariant)
│  ├─ generate_scenarios(policy)
│  ├─ find_counterexample(policy, property)
│  ├─ run_tests(policy)
│  └─ diff_versions(policy_a, policy_b)
│
├─ explain
│  ├─ check(derivation, binding)
│  ├─ diagnose(derivation, binding)
│  ├─ why_not(derivation, universe)
│  ├─ evidence(candidate | support_digest)
│  ├─ graph(candidate | support_digest)
│  └─ narrative(candidate | support_digest)
│
├─ simulate
│  ├─ fact_overlay.check(...)
│  ├─ proof_frame.recheck(...)
│  └─ rule_overlay.{disable, literal_replace, add_condition}
│
├─ audit
│  ├─ round recorder
│  ├─ diff_proof_frames
│  ├─ package load/query
│  └─ compliance/report surfaces
│
└─ registry
   ├─ schemas
   ├─ rules
   ├─ derivations
   └─ policies
```

Rationale:

- `rules` owns execution lifecycle.
- `policy` owns validation semantics.
- `explain` owns current/live proof explanation.
- `simulate` owns counterfactual mutation.
- `audit` owns persisted/offline/cross-round review.
- `registry` owns durable catalog / publication, not runtime explanation.

Because the project has not released yet, this note intentionally does not treat old `fg.eval.*` / `fg.what_if.*` names as compatibility constraints. They may still remain as implementation aliases, but the product taxonomy can prefer the cleaner tree.

## Object Boundary Decisions

### Query

Recommended boundary:

```text
Query = read-side projection
```

`Query` should stay pure read. It should not generate candidates, write ledger records, or carry policy validation semantics.

Good user mental model:

```python
q = Query(
    head=[User(u), User.name(name=nm)],
    where=[User(u), u.name == nm],
)

rows = fg.read.query(q)
# or accepted alias:
rows = fg.rules.run(q)
```

Design note: implementation may continue lowering `Query` into a temporary rule-like plan internally, but user-facing docs should not present `Query` as a materialization rule. It is a projection object.

### Rule

Recommended boundary:

```text
Rule = named reusable relation / inference fragment
```

`Rule` should represent a named relation over selected variables. It is appropriate for:

- direct row execution;
- `RuleRef` reuse;
- rule overlay experiments (`disable`, `literal_replace`, `add_condition`);
- policy membership.

Example:

```python
rule_user_has_language = Rule(
    id="rule.user_has_language",
    version="1.0.0",
    select=[u, lang],
    where=[User(u), u.lang_pref == lang],
    expose=True,
)

rows = fg.rules.run(rule_user_has_language)
```

Recommended constraint: `Rule.run` should be documented as deterministic row execution unless an explicit engine / semantics profile surface later says otherwise. Current fields such as `condition_weights`, `engine_ext`, and legacy `Body(..., confidence=...)` should be framed as implementation history or advanced internal annotations, not as ordinary `run(rule)` truth semantics.

### Derivation

Recommended boundary:

```text
Derivation = candidate/materialization producer
```

`Derivation` should mean: if `where` is satisfied, produce one or more accept-ready candidates described by `head`.

Example:

```python
drv_materialize_speaks = Derivation(
    id="drv.materialize_speaks",
    version="1.0.0",
    where=[RuleRef(rule_user_has_language)(u, lang)],
    head=Speaks(user=u, language=lang),
)

candidates = fg.rules.evaluate(drv_materialize_speaks, engine="native")
result = fg.rules.accept(candidates[0], approved_by="reviewer")
```

Design note: `Derivation` is not "a more advanced Rule"; it is a write-candidate producer. This separation is valuable and should remain:

```text
evaluate -> CandidateSet
accept   -> ledger assertions
```

This keeps approval, audit, batch handling, and evidence capture explicit.

## Branch Syntax Decision

Current public DSL has:

```python
Body([...], confidence=0.9)
```

This shape should not be kept as-is for the unreleased public API.

The current `Body` wrapper mixes two concepts:

1. branch structure: one conjunction of atoms inside an OR-shaped `where`;
2. branch probability / confidence: an engine-specific value currently bridged mainly toward ProbLog branch probabilities.

The uncertainty-transmission direction changes the recommendation from earlier drafts:

```text
Rule syntax should describe logical structure.
Uncertainty should live on data assertions as raw_kind + bound.
Engine-specific branch / rule weighting should live in SemanticsProfile or adapter-local engine configuration.
```

This is not only a naming cleanup. Engine-specific semantics currently attach to different structural locations:

```text
ProbLog branch probability
  -> branch
PyReason body interval threshold
  -> body predicate / atom
PyReason head interval
  -> head
PyReason runtime timesteps
  -> execution call
condition_weights / certainty
  -> rule condition / evidence summary
```

Putting all of these on public `Rule` / `Derivation` constructors would produce a fragmented API surface: some semantics on branches, some on atoms, some on heads, some in `engine_options`, some in rule metadata. The preferred design is to keep rule objects as standard business templates and let runtime `SemanticsProfile` carry the engine-specific projection.

An internal representation may still use path-targeted annotations:

```python
EngineAnnotation(
    engine="pyreason",
    target=Path.body_atom(0, 1),
    kind="interval_threshold",
    value=(0.5, 1.0),
)
```

But this should be an implementation shape under `SemanticsProfile.rule_projection`, not public rule syntax.

Recommended public structure syntax:

```python
Branch([A, B, C], id="business_path")
```

Example:

```python
rule_user_language = Rule(
    id="rule.user_language",
    version="1.0.0",
    select=[u, lang],
    where=[
        Branch([User(u), u.lang_pref == lang], id="declared_pref"),
        Branch([User(u), u.inferred_lang == lang], id="inferred_pref"),
    ],
    expose=True,
)
```

Rationale:

- `Branch` describes the actual shape: each wrapper is one OR branch whose atoms are ANDed.
- `id` is optional structural metadata for SDK inspection and future public semantics references.
- `Body` sounds like the whole rule body, but the current wrapper actually represents one branch.
- Public `Branch(probability=...)` would reintroduce an engine-specific uncertainty shortcut at the rule layer, conflicting with the raw uncertainty / transmission split.
- `confidence` is overloaded elsewhere in the system: fact metadata, candidate confidence, certainty summaries, and view aggregation all already use confidence-like concepts with different meanings.
- `probability` is not a generic rule-branch attribute. It is meaningful for ProbLog branch weighting, but not for PyReason certainty bounds, possibilistic facts, SMT constraints, or native row execution.

Recommended deterministic behavior:

```python
Rule(..., where=[Branch([...])])
fg.rules.run(rule)
```

should run as deterministic structure over the current projected fact view. If a user attempts to attach branch uncertainty in public rule syntax, the DSL should reject it and point to data-level `raw_kind` / `bound` or a `SemanticsProfile`.

Recommended uncertain-data behavior:

```python
fg.data.write(
    Risk.score,
    asset_ref,
    "risk_high",
    meta={
        "raw_kind": "possibilistic",
        "bound": [0.35, 0.70],
        "source": "expert_review",
    },
)

drv = Derivation(
    id="drv.risk_review",
    version="1.0.0",
    where=[
        Branch([Asset(a), Risk.score(a, "risk_high")]),
    ],
    head=ReviewRequired(asset=a),
)

profile = SemanticsProfile(
    engine="pyreason",
    uncertainty_projection={
        "possibilistic": "bound_as_certainty",
        "probabilistic": "probability_as_certainty",
        "fallback": "reject_unconfigured",
    },
)

candidates = fg.rules.evaluate(drv, profile=profile)
```

If ProbLog-specific branch weighting remains necessary, it should be scoped as an engine profile / adapter extension, not as general public `Branch` syntax:

```python
profile = SemanticsProfile(
    engine="problog",
    engine_options={"timeout": 15},
    rule_projection={
        "branch_weights": {
            "drv.risk_review": [0.9, 0.6],
        }
    },
    uncertainty_projection={
        "probabilistic": "point_or_policy",
        "possibilistic": "reject",
    },
)
```

Recommended non-goals:

- Do not use `Branch(probability=...)` as public syntax.
- Do not reuse `probability` for PyReason certainty, possibilistic uncertainty, SMT hard constraints, or rule-condition weights.
- Do not let `Query` consume `Branch(probability=...)`; `Query` remains read-side projection.
- Do not put possibility/probability transformation policy inside `Rule` or `Derivation` definitions.
- Do not require users to learn engine-specific structural attachment points just to author a standard business rule template.

Potential implementation cleanup:

```text
Body -> Branch
Body.confidence -> removed from public syntax
ProbLog branch probabilities -> SemanticsProfile / adapter-local extension
```

Because there is no release compatibility requirement, the preferred public API can remove `Body` entirely. If an internal bridge is still useful while cleaning call sites, `Body` should be kept as an internal alias or temporary shim only, not as documented public syntax.

## Execution Engine Placement

Recommended syntax:

```python
fg.rules.evaluate(derivation, engine="native")
```

Not recommended:

```python
Derivation(..., mode="native")
```

Reason:

`native` / `souffle` / `problog` / `pyreason` is execution-time selection, not rule definition semantics. The same `Derivation` may be evaluated through different engines:

```python
fg.rules.evaluate(drv, engine="native")
fg.rules.evaluate(drv, engine="problog", engine_options={"timeout": 15})
fg.rules.evaluate(drv, engine="pyreason", engine_options={"timesteps": 5})
```

Recommended layering:

```text
Derivation definition
  id / version / where / head as business logic

Execution call
  engine / engine_options / profile

Policy deployment
  optional default SemanticsProfile
```

Legacy or internal `engine_ext` fields should be treated as migration targets, not as the preferred public rule contract. If an engine needs path-specific rule parameters, the profile should own those parameters through `rule_projection`.

If a runtime profile abstraction is introduced, it should align with the uncertainty transmission design and be called `SemanticsProfile` rather than a narrower `ExecutionProfile`:

```python
native_profile = SemanticsProfile(engine="native")
pyreason_profile = SemanticsProfile(
    engine="pyreason",
    engine_options={"timesteps": 5},
    uncertainty_projection={"possibilistic": "bound_as_certainty"},
)

fg.rules.evaluate(drv, profile=native_profile)
```

Priority model:

```text
call-site engine/profile > policy default SemanticsProfile > system default native
```

Since there is no release compatibility requirement, the public `Derivation(mode=...)` field should be removed or renamed to an explicitly weaker `default_engine` / `default_profile` only if a default-on-definition use case survives design review. The cleaner default is no engine field on `Derivation`.

## Policy / Theory Layer

`Policy` / `Theory` should be a new layer over existing rules, not a replacement for them.

Recommended role:

```text
Policy = variables + types + rules + derivations + invariants + tests + source refs + versions
```

Sketch:

```python
policy = Policy(
    id="policy.language",
    version="1.0.0",
    rules=[rule_user_has_language],
    derivations=[drv_materialize_speaks],
    invariants=[
        Invariant(
            id="no_missing_language_for_required_country",
            forall=["user"],
            property=...,
        )
    ],
    default_profile=SemanticsProfile(engine="native"),
)
```

Policy operations should return validation findings, not candidates:

```python
finding = fg.policy.validate_claim(
    policy,
    claim=Speaks(user=alice_ref, language="French"),
    premises=[
        User(alice_ref),
        User.lang_pref(user=alice_ref, value="French"),
    ],
)
```

Recommended result shape:

```python
PolicyFinding(
    result="valid",  # valid | invalid | satisfiable | impossible | unknown
    claim=...,
    premises=...,
    supporting_rules=("rule.user_has_language",),
    evidence=(...),
    counterexample=None,
    diagnostics=(),
)
```

This result family should be distinct from:

- `CandidateSet` — proposed materialization output;
- `AcceptResult` — ledger write outcome;
- `CheckResult` / `DiagnoseResult` — binding-level proof diagnostics.

## Evidence Layer Relationship

Existing evidence mechanisms should be reused as policy verification evidence, not rewritten:

- `check` provides proof support for a concrete binding.
- `diagnose` localizes failed atoms.
- `why_not` partitions a finite universe.
- fact overlay injects hypothetical premises.
- rule overlay tests temporary rule edits.
- `SupportArtifact` / `ProvenanceEnvelope` / `EvidenceGraph` carry proof material.
- `round_events` / `diff_proof_frames` compare behavior across runs.

Policy-level validation can be implemented first as a finite / evidence-backed layer:

```python
def validate_claim(policy, claim, premises):
    overlay = build_overlay_from_premises(premises)
    derivation = policy.resolve_derivation_for_claim(claim)

    check = fg.simulate.fact_overlay.check(
        derivation,
        binding=claim.to_binding(),
        overlay=overlay,
        engine=policy.default_profile.engine,
    )

    if check.status == "passed":
        return PolicyFinding(
            result="valid",
            claim=claim,
            evidence=(check.evidence_envelope,),
        )

    contradiction = policy.resolve_contradiction_derivation(claim)
    if contradiction is not None:
        bad = fg.simulate.fact_overlay.check(
            contradiction,
            binding=claim.to_binding(),
            overlay=overlay,
            engine=policy.default_profile.engine,
        )
        if bad.status == "passed":
            return PolicyFinding(
                result="invalid",
                claim=claim,
                evidence=(bad.evidence_envelope,),
            )

    diag = fg.explain.diagnose(derivation, claim.to_binding())
    return PolicyFinding(
        result="unknown",
        claim=claim,
        diagnostics=(diag,),
    )
```

Later, the same `Policy` object can lower to an SMT / ImandraX / other formal backend for true universal verification.

## Current Gaps This Design Addresses

### Gap 1: No policy aggregate

Current system has rules, derivations, registry entries, and evidence, but no first-class object for the whole policy/theory.

### Gap 2: No validation-finding taxonomy

Current statuses are execution oriented: `passed`, `failed`, `unsupported`, `invalid_request`, `accepted`, `duplicate`. Policy validation needs:

```text
valid / invalid / satisfiable / impossible / unknown
```

Potential future additions:

```text
translation_ambiguous / too_complex / no_translation
```

if natural-language-to-logic policy workflows become product scope.

### Gap 3: No universal verification

Current `check` is binding-level and `why_not` requires an explicit finite universe. Policy layer needs:

```python
fg.policy.verify_invariant(policy, invariant)
fg.policy.find_counterexample(policy, property)
```

### Gap 4: No automatic scenario generation

`why_not` diagnoses a supplied universe. Policy layer should generate candidate scenarios from variable domains, boundary values, and source examples:

```python
scenarios = fg.policy.generate_scenarios(
    policy,
    variables={
        "$employment_status": ["full_time", "part_time"],
        "$tenure_months": [0, 6, 12, 13, 24],
    },
)
```

### Gap 5: Evidence carriers are not yet a unified user-facing proof API

Current carriers include `SupportArtifact`, `ProvenanceEnvelope`, `EvidenceGraph`, candidate evidence tree, and `RuleTraceArtifact`. They can remain internally distinct, but user-facing API should route through `fg.explain.evidence(...)`, `fg.explain.graph(...)`, and `fg.explain.narrative(...)`.

## Documentation / Design Actions

Recommended next design work:

1. Decide whether the public namespace should be `fg.rules.*` or `fg.rule.*`; this note uses plural `rules` because it owns a lifecycle, not only one rule object.
2. Remove `mode` from public `Derivation` design, or rename it only if a default-profile use case is accepted.
3. Define `SemanticsProfile` only after confirming repeated engine / transmission configuration is common enough; otherwise keep call-site `engine=...` plus explicit options.
4. Reframe docs:
   - `Query` under read/projection.
   - `Rule` under reusable relation.
   - `Derivation` under candidate/materialization producer.
5. Create a future blueprint for `Policy` / `PolicyFinding` MVP.
6. Keep evidence carriers internally distinct but design a unified `fg.explain.*` user surface.
7. Decide whether policy validation starts finite/evidence-backed only, or whether a formal backend spike is needed before public API freeze.

## Open Risks

- Naming risk: `Derivation` may continue to be confused with proof derivation. A product-level alias such as `Inference` or `Materialization` may be clearer, but changing the core class name may not be worth the churn.
- Engine semantics risk: existing `engine_ext`-style fields can blur definition-time business logic with runtime adapter projection. Future docs should move public guidance toward `SemanticsProfile.rule_projection` and keep any remaining definition-time extension points explicitly internal or transitional.
- Policy result risk: `valid` / `invalid` must be defined carefully. In a finite evidence-backed MVP, `valid` may mean "entailed by current engine over supplied premises," not full mathematical validity.
- Evidence durability risk: policy-level verification may need long-term replay of evidence. Current engine `ProvenanceEnvelope` durability is weaker than native `SupportArtifact` sidecar durability.
- Scope risk: ARC-style source-document fidelity and natural-language translation should not be implied unless explicitly designed.
