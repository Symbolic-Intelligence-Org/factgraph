# Task Blueprint: Public Inference Naming And FactGraph Create

- Status: implemented
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/__init__.py`
  - `src/kernel/sdk/dsl/__init__.py`
  - `src/kernel/sdk/dsl/rule.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/sdk/registry.py`
  - `src/kernel/sdk/shells/check.py`
  - `src/kernel/sdk/shells/diagnose.py`
  - `src/kernel/sdk/shells/fact_overlay.py`
  - `src/kernel/sdk/shells/why_not.py`
  - `src/kernel/application/derivation_runtime.py`
  - `src/kernel/application/protocol/derivation.py`
  - `src/service/runtime_v1.py`
- Related Docs:
  - [docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md](../../references/working/design-points/factgraph-lifecycle-and-assets.zh.md)
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/references/working/design-points/post-track3-semantics-public-api.zh.md](../../references/working/design-points/post-track3-semantics-public-api.zh.md)
  - [docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md](../archive/2026-05-12_branch-identity-rule-inspect.md)
  - [docs/blueprints/archive/2026-05-12_public-semantics-api-redesign.md](../archive/2026-05-12_public-semantics-api-redesign.md)
  - [docs/blueprints/archive/2026-05-12_pyreason-branch-bounds-carrier.md](../archive/2026-05-12_pyreason-branch-bounds-carrier.md)
- Audit Log:
  - [2026-05-12_public-inference-factgraph-create.audit.md](./2026-05-12_public-inference-factgraph-create.audit.md)

## 1. Problem

The current public SDK still exposes the candidate-producing authoring object as `Derivation`:

```python
deriv = Derivation(...)
fg.eval.evaluate(deriv, semantics=PyReasonSemantics(...))
```

That name is overloaded. Existing design notes already flagged that `Derivation` can mean either:

- the SDK value object that proposes inferred facts (`where + head -> CandidateSet`);
- a proof/audit derivation trace explaining how a result was derived.

The product is still pre-release, so public SDK vocabulary can be cleaned up without preserving historical aliases. The lifecycle design-point recommends a public/internal split:

- public SDK: `Inference`, `fg.inferences.*`, future `InferenceRef`;
- internal/application/service/registry substrate: existing `derivation_*` names may remain until a dedicated wire/registry rename slice.

At the same time, `FactGraph.from_schema_classes(...)` is the only create-like public entrypoint. It compiles schema, binds ledger/artifact state, and writes/checks `schema_digest`, but the name describes one implementation source rather than graph lifecycle intent. The design-point recommends a first small slice that adds `FactGraph.create(...)` while keeping persistence (`load/save`) out of scope.

This blueprint starts that first slice.

## 2. Goals

- Decide whether public SDK hard-cuts `Derivation` to `Inference`.
- Decide whether public method parameter names also change from `derivation` to `inference`.
- Decide whether `FactGraph.create(...)` becomes the canonical graph construction entrypoint over the current `from_schema_classes(...)` substrate.
- Verify whether `fg.rules.inspect(...)` already provides enough structure inspection for `Inference`, avoiding an empty `fg.inferences` namespace.
- Keep runtime direct-use behavior intact: users can still evaluate unsaved value objects.
- Keep service routes, service JSON keys, registry manifest keys, and filesystem paths out of this first slice unless G0 explicitly expands scope.
- Preserve Track 3 and post-Track-3 semantics APIs: `ProbLogSemantics`, `PyReasonSemantics`, `SemanticsProfile`, engine auto-derivation, and PyReason branch bounds.

## 3. Non-goals

- Do not add `FactGraph.load(...)`.
- Do not add graph-level `fg.save(...)`.
- Do not add `fg.rules.save/load/list`.
- Do not add `fg.inferences.save/load/list`.
- Do not introduce `InferenceRef`.
- Do not rename service routes from `/derivations/*` to `/inferences/*`.
- Do not rename service payload keys from `"derivation"` to `"inference"`.
- Do not rename registry manifest keys or filesystem paths from `derivations/` to `inferences/`.
- Do not implement schema add/delete/update/migration.
- Do not implement query persistence or expose `fg.queries`.
- Do not migrate current audit/proof helpers into `fg.explain.*`; explain/evidence remains a dedicated future blueprint.
- Do not alter `release/0.1.x` or `v0.1.0-rc.1`.

## 4. Current Context

### 4.1 Current `Derivation` public surface

`src/kernel/sdk/dsl/rule.py` defines the public SDK value object currently named `Derivation`. It produces authoring payloads containing keys such as:

- `derivation_id`
- `version`
- `where`
- `head`

`src/kernel/sdk/__init__.py` and `src/kernel/sdk/dsl/__init__.py` export `Derivation`.

Quick source audit found no existing public `Inference` class/export/file namespace collision, but `Derivation` is widely used across:

- SDK DSL and tests;
- service runtime routes and JSON payload keys;
- application protocol names;
- registry manifest keys;
- filesystem paths such as `derivations/{id}/{version}.json`;
- docs and debug strings.

Implication: public SDK rename is feasible, but full-stack substrate rename is too large for this slice.

### 4.2 Current public naming inventory

The public naming surface is wider than the `Derivation` class export. G0 should explicitly lock the treatment for each of these surfaces before G1 writes forward-failing tests.

Current SDK public type/export surfaces:

- `kernel.sdk.Derivation`
- `kernel.sdk.dsl.Derivation`
- `src/kernel/sdk/dsl/rule.py::Derivation`

Current runtime call surface:

- `SDKStore.evaluate(...)` uses `*args, **kwargs`, but user-facing docs, errors, and helper code still refer to `derivation`.
- `_SDKEvalManager.evaluate(...)` forwards to `SDKStore.evaluate(...)`.
- `SDKStore.evaluate_compiled(...)` is compiled-dict oriented; it should stay on compiled derivation substrate unless G0 expands scope.

Current compiled-plan public surface:

- `_SDKEvalManager.evaluate_compiled(...)` exposes already-compiled derivation plan evaluation.
- `_SDKEvalManager.accept_compiled(...)` exposes core accept forwarding.
- `src/kernel/sdk/docs/04_api_surface.en.md` lists both methods under public `fg.eval`.
- `src/kernel/sdk/docs/07_walker_and_advanced.en.md` frames them as advanced compiled DTO usage.
- `CompiledDerivationPlan` itself is an application protocol DTO, not a normal SDK authoring object.

This is likely too low-level for the ordinary SDK surface. G0 should decide whether these methods remain advanced public escape hatches, move out of canonical docs, or are hard-cut from `fg.eval` while application-layer DTO APIs remain available internally.

Current `what_if` shell methods expose `derivation` as an explicit public parameter:

- `fg.what_if.check(derivation, ...)`
- `fg.what_if.diagnose(derivation, ...)`
- `fg.what_if.why_not(derivation, ...)`
- `fg.what_if.fact_overlay.check(derivation, ...)`

Current accept surface:

- `fg.eval.accept(candidate_set, ...)` consumes `CandidateSet.derivation_id` internally.
- `fg.eval.accept_compiled(...)` forwards to core accept.
- `fg.eval.accept_many(...)` accepts `AcceptRequest`, `CandidateSet`, or dict requests.
- These methods do not accept a public `derivation=` parameter, so they should generally remain out of the public parameter rename except for docs/error wording if surfaced.
- `fg.eval.accept_many(..., mode="atomic")` uses `mode` as accept transaction mode, not engine mode. This is a post-hoc SDK keyword polish issue and is not forced by the `Inference` rename; Blueprint 1 should defer it unless G0 explicitly expands scope.

Current public method returning substrate dict:

- `Derivation.to_authoring_payload()` returns keys such as `"derivation_id"`.

Current provenance validation standard:

- `fg.schema.validate_provenance(..., standard="derivation_v1")` exposes a public string standard whose name contains `derivation`.
- This is closer to a substrate/version identifier than a public class name. G0 should decide whether it follows the public `Inference` rename or remains decoupled.

If the public type becomes `Inference`, public parameter names should be scoped explicitly. Otherwise IDE autocomplete and signature inspection continue to expose the old vocabulary even if the class name changes.

### 4.3 Current structure inspection

Track 1 added `fg.rules.inspect(rule_or_derivation)`.

Current implementation:

- `_SDKRulesManager.inspect(...)` delegates to `SDKStore.inspect_rule(...)`.
- `SDKStore.inspect_rule(obj)` delegates to `_inspect_rule_or_derivation(obj)`.
- `_inspect_rule_or_derivation(...)` handles both rule-like and derivation-like SDK objects.

Implication: Blueprint 1 probably does not need a new `_SDKInferencesManager.inspect(...)`. G0 should decide whether `fg.rules.inspect(inference)` remains the canonical structure inspection path, or whether a thin `fg.inferences.inspect(...)` alias is worth adding.

### 4.4 Current `FactGraph` construction

`FactGraph` is an alias of `SDKStore`.

`SDKStore.from_schema_classes(...)` already acts as create-like entrypoint:

- compiles schema from Python `Entity` classes;
- computes `schema_digest`;
- optionally binds `Ledger(path=ledger_path)`;
- stores/checks ledger metadata;
- optionally binds artifact sidecar root;
- returns an `SDKStore`.

Implication: `FactGraph.create(schema_classes=[...])` can be additive and can wrap `from_schema_classes(...)` without solving class-less load or graph workspace save.

### 4.5 Current registry and persistence boundary

`SDKRegistry` persists schema/rule/derivation authoring assets through `FileAuthoringRegistry`. It returns raw manifest dictionaries today.

The lifecycle design-point recommends moving public durable asset operations toward future domain facades such as:

```python
fg.rules.save(rule)
fg.inferences.save(inf)
```

That is not this slice. Blueprint 1 should not create persistence APIs or reference types.

### 4.6 Current explain/evidence/audit boundary

The earlier function-tree note recommends:

- `explain` owns current/live proof explanation;
- `audit` owns persisted/offline/cross-round review;
- evidence carriers remain internally distinct.

The lifecycle design-point now records that `fg.explain.*` should be future user-facing proof explanation surface, but Blueprint 1 through Blueprint 3 should not migrate current `fg.audit.explain_fact(...)` or proof helpers.

Implication: Blueprint 1 should leave explain/evidence/audit untouched.

## 5. Scope Freeze Decisions

G0 locked the recommended batch path on 2026-05-12:

```text
Q1 I1a   Q2 I2a   Q3 I3a   Q4 I4a   Q5 I5a   Q6 I6a   Q7 I7a
Q8 I8a + I8a-2   Q9 I9a   Q10 I10a   Q11 I11a   Q12 I12a   Q13 I13a
```

The unifying rule is: public SDK vocabulary uses `Inference`; substrate vocabulary remains `derivation` where it names application protocols, authoring payload keys, registry/wire concepts, or version identifiers.

### 5.1 Q1: Public type rename

Options:

- **I1a** Hard-cut public `Derivation` to `Inference`.
- **I1b** Add `Inference` as alias while keeping `Derivation` public.
- **I1c** Keep `Derivation`; defer naming cleanup.

G0 decision (2026-05-12): **I1a locked**. The product is unreleased, the name conflation is real, and adding a public alias creates two names for one concept before release.

### 5.2 Q2: Internal substrate vocabulary

Options:

- **I2a** Public SDK only: `Inference`; internal/application/service/registry can keep `derivation_*` until a later wire/registry rename slice.
- **I2b** Full-stack rename in Blueprint 1.

G0 decision (2026-05-12): **I2a locked**. Source audit found broad service/wire/registry/filesystem reach. Full-stack rename would swamp the first slice.

### 5.3 Q3: Public parameter names

Options:

- **I3a** Rename public SDK parameter names from `derivation` to `inference` in `evaluate` docs/errors and `what_if` shells.
- **I3b** Rename only the class, leave public parameters as `derivation`.

G0 decision (2026-05-12): **I3a locked**. A class rename without parameter rename leaves IDE/signature UX inconsistent. Internal helpers may keep `derivation` names when they are not user-facing.

### 5.4 Q4: Public alias compatibility

Options:

- **I4a** No public `Derivation` alias after this slice.
- **I4b** Keep `Derivation = Inference` temporarily.

G0 decision (2026-05-12): **I4a locked**. Pre-release hard-cut is cleaner. Tests should lock that no new public `Derivation*` symbol is minted.

### 5.5 Q5: Public `to_authoring_payload()` dictionary keys

Options:

- **I5a** Keep `Inference.to_authoring_payload()` output on substrate keys such as `"derivation_id"` until the service/registry wire rename slice.
- **I5b** Change public payload output to `"inference_id"` in Blueprint 1 and translate back to `"derivation_id"` internally.

G0 decision (2026-05-12): **I5a locked**. `to_authoring_payload()` is a public method, but the dict it emits is already the authoring/registry substrate shape. Splitting this from the service/registry rename would create a third vocabulary layer. Keep substrate keys until the dedicated wire/registry rename slice.

### 5.6 Q6: `FactGraph.create(...)`

Options:

- **I6a** Add `FactGraph.create(schema_classes=[...], ...)` as canonical wrapper over `from_schema_classes(...)`; keep `from_schema_classes(...)` available for now.
- **I6b** Add `create(...)` and remove/hide `from_schema_classes(...)` in the same slice.
- **I6c** Defer lifecycle constructor cleanup.

G0 decision (2026-05-12): **I6a locked**. It improves lifecycle naming without forcing a class-less load or constructor hard-cut before workspace semantics are designed.

### 5.7 Q7: `fg.inferences` namespace in Blueprint 1

Options:

- **I7a** Do not add `fg.inferences` unless it has real behavior; rely on `fg.rules.inspect(inference)` for structure inspection.
- **I7b** Add `fg.inferences.inspect(...)` as a thin alias.
- **I7c** Add empty `fg.inferences` as future placeholder.

G0 decision (2026-05-12): **I7a locked**. Track 1 already made `fg.rules.inspect(rule_or_inference)` structurally sufficient. Avoid empty or purely symmetric namespaces.

### 5.8 Q8: Docs strategy

Options:

- **I8a** Update SDK docs in the same slice: README/user guide/API surface/rules docs teach `Inference`.
- **I8b** Ship code rename first, docs later.

G0 decision (2026-05-12): **I8a locked**. In a pre-release SDK, docs lag on public naming is more damaging than a larger docs diff.

Sub-decision for docs file naming:

- **I8a-1** Update doc contents only; keep `03_rules_and_derivations.en.md` filename until wire/registry rename.
- **I8a-2** Rename the SDK doc file to `03_rules_and_inferences.en.md` in the same slice.

G0 decision (2026-05-12): **I8a-2 locked**. This is an SDK doc filename, not service wire substrate. If the public SDK hard-cuts to `Inference`, leaving a public SDK doc filename on `derivations` creates avoidable pre-release inconsistency.

### 5.9 Q9: Service/wire rename ordering

Options:

- **I9a** Explicitly defer service route/payload and registry path rename to a follow-up slice before persistence facade work.
- **I9b** Include service/wire/registry rename in Blueprint 1.

G0 decision (2026-05-12): **I9a locked**. The two-vocabulary period is a real cost, but source audit shows a full-stack rename is not the right first cut.

### 5.10 Q10: `InferenceRef`

Options:

- **I10a** Do not introduce `InferenceRef` in Blueprint 1.
- **I10b** Introduce `InferenceRef` early as a name reservation.

G0 decision (2026-05-12): **I10a locked**. Reference types belong with persistence. The design-point should still lock that future public references use `InferenceRef`, never new `DerivationRef`.

### 5.11 Q11: Explain/evidence scope

Options:

- **I11a** Keep explain/evidence/audit untouched; cite it only as a future independent blueprint.
- **I11b** Rename or alias current audit proof helpers into `fg.explain.*`.

G0 decision (2026-05-12): **I11a locked**. The explain taxonomy is important, but unrelated to public `Inference` naming and `FactGraph.create(...)`.

### 5.12 Q12: Compiled-plan SDK public surface

Options:

- **I12a** Hard-cut `fg.eval.evaluate_compiled(...)` and `fg.eval.accept_compiled(...)` from the ordinary public SDK surface; keep compiled-plan evaluation as application/substrate capability.
- **I12b** Keep them as advanced public APIs only, documented exclusively in advanced docs and excluded from normal user-guide/API teaching.
- **I12c** Leave them unchanged as regular `fg.eval` public methods.

G0 decision (2026-05-12): **I12a locked**. `CompiledDerivationPlan` is an application protocol DTO, not a user-layer object. `accept_compiled(...)` in particular is just a thin core accept forwarding surface; `accept(candidate_set, ...)` is the clearer SDK path. Blueprint 1 will hard-cut these from the ordinary public SDK surface while preserving compiled-plan capability as application/substrate behavior.

### 5.13 Q13: Provenance standard naming

Options:

- **I13a** Keep `standard="derivation_v1"` and document it as a substrate provenance standard version, decoupled from the public SDK class name.
- **I13b** Rename the public default to `standard="inference_v1"` and treat `"derivation_v1"` as legacy compatibility.
- **I13c** Rename and bump to a new substrate version such as `standard="inference_v2"`.

G0 decision (2026-05-12): **I13a locked**. Public class naming should not drag substrate version identifiers. If the stored/provenance schema has not changed, the version token should stay stable and be explicitly classified as substrate vocabulary.

## 6. Boundaries And Invariants

- Runtime direct use remains valid: evaluating an unsaved `Inference` object must not require registry setup.
- Track 3 semantics remain unchanged:
  - `ProbLogSemantics`
  - `PyReasonSemantics`
  - `SemanticsProfile`
  - engine auto-derivation
  - PyReason branch bounds
- Track 1 branch identity and `fg.rules.inspect(...)` behavior remain unchanged except for public naming in returned type labels if scoped.
- Assertion/read/write/view APIs remain unchanged.
- Service and registry wire vocabulary can remain `derivation` in this slice if G0 chooses the public/internal split.
- Public docs should not teach both `Derivation` and `Inference` as equal public names if G0 selects hard-cut.
- Compiled-plan DTOs are application/substrate objects. If any compiled-plan SDK escape hatch survives, it must be explicitly classified as advanced, not normal SDK teaching.
- `standard="derivation_v1"` may remain substrate vocabulary even if public SDK classes use `Inference`.
- `accept_many(mode="atomic")` is an accept-transaction keyword and is deferred to a future SDK keyword/boundary polish slice, not Blueprint 1.
- No graph persistence semantics are introduced.

## 7. Acceptance

G0 locked the acceptance gates below.

- [x] G0 locks the public `Derivation` vs `Inference` decision.
- [x] G0 locks whether public SDK parameter names change to `inference`.
- [x] G0 locks whether `Inference.to_authoring_payload()` keeps substrate key `"derivation_id"`.
- [x] G0 locks whether `FactGraph.create(...)` ships and whether `from_schema_classes(...)` remains public.
- [x] G0 locks whether SDK docs file `03_rules_and_derivations.en.md` is renamed in this slice.
- [x] G0 locks that service/wire/registry rename is deferred or included.
- [x] G0 locks whether `evaluate_compiled(...)` / `accept_compiled(...)` remain public, become advanced-only, or are hard-cut.
- [x] G0 locks whether `standard="derivation_v1"` remains as substrate vocabulary.
- [x] G1 inventory enumerates every public method/parameter/error-message/dict-key/doc-file reference to `derivation*` that is in or out of scope.
- [x] G1 adds forward-failing tests for the selected public type/export/signature shape.
- [x] G1 adds guard tests that Track 3 semantics and Track 1 inspect behavior remain intact.
- [x] G2 implements only the scoped public SDK/docs changes.
- [x] G3 updates SDK module docs and reference docs.
- [x] G4 fills §10, marks implemented, and archives this blueprint pair.

## 8. Implementation Plan

Scoped implementation sequence:

1. G1 red baseline:
   - public `Inference` import/export expectations;
   - no public `Derivation` export if hard-cut;
   - `FactGraph.create(...)` constructor behavior;
   - public parameter naming expectations;
   - preservation guards for `fg.rules.inspect(...)`, Track 3 semantics, and direct runtime evaluation.
2. G2 implementation:
   - rename/add SDK DSL public type;
   - update SDK exports;
   - add `FactGraph.create(...)`;
   - update public SDK parameter names and error text as scoped;
   - keep internal lowering/application names stable unless explicitly scoped.
3. G3 docs sync:
  - SDK README/user guide/API surface/rules/inferences docs;
   - design-point note from proposal to current behavior for the parts that land.
4. G4 close-out:
   - archive blueprint;
   - record the remaining wire/registry rename and persistence facades as future slices.

## 9. Docs To Update

Likely docs if G0 selects the recommended path:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/03_rules_and_inferences.en.md` (rename target; currently `03_rules_and_derivations.en.md`)
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/sdk/docs/06_what_if_and_proof.en.md`
- `src/kernel/core/docs/01_architecture.en.md` if public/internal vocabulary split needs architecture mention
- `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`
- `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`

## 10. Outcome / Deviations

### 10.1 Final Landed Behavior

1. Public SDK value-object naming is now `Inference`, exported from `kernel.sdk`, `kernel.sdk.dsl`, and implemented in `src/kernel/sdk/dsl/rule.py`.
2. Public `Derivation` and `Derivation*` SDK symbols are not exported and no compatibility alias is kept.
3. `Inference.to_authoring_payload()` intentionally keeps substrate keys such as `"derivation_id"` and does not emit `"inference_id"`.
4. `FactGraph.create(schema_classes=[...], ...)` is the canonical lifecycle constructor and delegates to `from_schema_classes(...)`.
5. `FactGraph.from_schema_classes(...)` remains available as the lower-level class-first constructor substrate.
6. Public what-if shells now use `inference=` naming: Check, Diagnose, Why-not, and Fact Overlay.
7. Internal application/runtime/helper names may still use `derivation` where they refer to substrate protocol or proof vocabulary.
8. Public `fg.eval.evaluate_compiled(...)` and `fg.eval.accept_compiled(...)` were hard-cut from both namespace and root SDK surfaces.
9. Private compiled-plan capability remains through `_evaluate_compiled_derivation_plans(...)` for `evaluate(...)` lowering and application/substrate use.
10. Blueprint 1 does not add an empty `fg.inferences` namespace.
11. Blueprint 1 does not mint `InferenceRef` or `DerivationRef`; future persistence work owns reference types.
12. `standard="derivation_v1"` remains the provenance substrate standard name.
13. `accept_many(mode="atomic")` remains unchanged and is deferred to a future SDK keyword/boundary polish slice.
14. SDK docs now teach `Inference`, `FactGraph.create(...)`, `inference=`, and the compiled-plan SDK hard-cut.
15. `03_rules_and_derivations.en.md` was renamed to `03_rules_and_inferences.en.md`.
16. The lifecycle design-point and earlier function-tree note now record Blueprint 1 as the public naming boundary.

### 10.2 Validation

- G1 baseline before implementation: 16 tests, with expected red/guard shape after G1 polish.
- G2 implementation closed all code gates while preserving Track 1, Track 3, and post-Track-3 behavior.
- G3 docs sync closed the final docs filename gate.
- `PYTHONPATH=src python -m unittest kernel.tests.test_public_inference_factgraph_create`: 16 OK.
- `PYTHONPATH=src python -m unittest discover -s src/kernel/tests`: 2042 OK / 1 skipped.
- `git diff --check`: clean.
- Working tree after G3 commit remained clean except protected notebooks.

### 10.3 Commit Lineage

```text
1d9e737b docs(sdk): sync public inference vocabulary
c0de0502 feat(sdk): hard-cut compiled evaluation escape hatches
4a071636 feat(sdk): rename what-if shell input to inference
03caf4df feat(sdk): add FactGraph create constructor
1f374ef6 feat(sdk): rename public Derivation to Inference
01851c12 test(sdk): extend public inference baseline with deferral guards
e3313b56 test(sdk): add public inference factgraph create baseline
fc42e5c1 docs(blueprints): scope public inference factgraph create
```

G4 close-out archives the blueprint pair after these eight commits.

### 10.4 Deviations

No scope deviations.

Implementation followed all G0 decisions:

- public SDK hard-cut to `Inference`;
- internal/service/registry/application substrate vocabulary preserved;
- `FactGraph.create(...)` added without removing `from_schema_classes(...)`;
- compiled SDK escape hatches removed while substrate capability remained private;
- docs filename renamed in the same slice;
- service/wire, persistence, schema mutation, query persistence, and explain/evidence remained deferred.

The only notable implementation detail is `_evaluate_compiled_derivation_plans(...)`, which is not a deviation: it is the intentional private substrate path required by I12a.

### 10.5 Archive Notes

Blueprint 1 completes the first lifecycle/asset cleanup slice after the post-Track-3 plan. It establishes the public SDK vocabulary:

- users author `Inference` objects;
- users construct graphs with `FactGraph.create(...)`;
- users pass `inference=` to what-if shells;
- users do not see compiled-plan evaluation as ordinary SDK surface.

The public/internal split remains explicit. `derivation_id`, `derivation_v1`, `CompiledDerivationPlan`, service routes, registry manifests, filesystem paths, and proof/audit vocabulary remain substrate until dedicated follow-up slices decide whether and how to rename them.

Recommended next slices remain independent:

- service/wire/registry vocabulary rename from derivation to inference;
- FactGraph workspace load/save and domain asset persistence facades;
- SDK keyword/boundary polish such as `accept_many(mode=...)`;
- explain/evidence/audit capability under a future `fg.explain.*` surface;
- schema add/deprecate/migrate and query persistence.
