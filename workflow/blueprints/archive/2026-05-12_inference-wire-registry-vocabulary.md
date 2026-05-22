# Task Blueprint: Inference Wire And Registry Vocabulary

- Status: implemented
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/service/app_v1.py`
  - `src/service/runtime_v1.py`
  - `src/service/registry_v1.py`
  - `src/kernel/sdk/registry.py`
  - `src/kernel/authoring/registry_fs.py`
  - `src/kernel/authoring/apply_execute.py`
  - `src/kernel/authoring/cli.py`
  - `src/kernel/authoring/derivation_compile.py`
  - `src/kernel/application/protocol/derivation.py`
  - `src/kernel/core/derivation/candidates.py`
- Related Docs:
  - [docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md](../../references/working/design-points/factgraph-lifecycle-and-assets.zh.md)
  - [docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md](../archive/2026-05-12_public-inference-factgraph-create.md)
- Audit Log:
  - [2026-05-12_inference-wire-registry-vocabulary.audit.md](./2026-05-12_inference-wire-registry-vocabulary.audit.md)

## 1. Problem

Blueprint 1 hard-cut the public SDK authoring value-object name from `Derivation` to `Inference`:

```python
inf = Inference(...)
fg.eval.evaluate(inf, semantics=PyReasonSemantics(...))
```

It intentionally preserved substrate vocabulary:

- `Inference.to_authoring_payload()` emits `"derivation_id"`;
- service routes remain `/derivations/evaluate` and `/derivations/accept`;
- service runtime request payload still uses top-level `"derivation"`;
- registry routes/methods/manifest/path still use derivation naming;
- application/core DTOs still use `CompiledDerivationPlan`, `DerivationEvaluateRequest`, and `CandidateSet.derivation_id`.

That was a deliberate first cut. It now leaves a user-visible two-vocabulary gap: public SDK says `Inference`, but HTTP wire and registry surfaces still say `derivation`.

This blueprint scopes the next slice: rename the **service wire and registry asset vocabulary** from derivation to inference where it represents the public candidate-producing authoring object, without renaming proof/audit/core candidate protocol vocabulary.

## 2. Goals

- Decide which service routes move from `/derivations/*` to `/inferences/*`.
- Decide whether runtime evaluate request key changes from `"derivation"` to `"inference"`.
- Decide whether registry read route/key/response changes from derivation to inference.
- Decide whether `SDKRegistry` public methods change from `register_derivation*` / `read_derivation*` to `register_inference*` / `read_inference*`.
- Decide whether `FileAuthoringRegistry` manifest and filesystem path change from `derivations/` to `inferences/`.
- Keep core/application candidate protocol and proof/audit vocabulary stable unless G0 explicitly expands scope.
- Preserve Blueprint 1 public SDK `Inference` behavior, Track 3 semantics wrappers, and direct runtime evaluation.

## 3. Non-goals

- Do not add `fg.inferences.save/load/list`.
- Do not add `InferenceRef`.
- Do not implement FactGraph workspace `load/save`.
- Do not implement schema mutation.
- Do not implement query persistence.
- Do not migrate proof/audit/static UI terminology from derivation to proof trace.
- Do not rename `CandidateSet.derivation_id` unless G0 deliberately expands scope.
- Do not rename `CompiledDerivationPlan` / `DerivationEvaluateRequest` unless G0 deliberately expands scope.
- If G0 selects the recommended candidate-protocol boundary, `/inferences/*` routes will still return candidate payloads containing `derivation_id` / `derivation_version`. This residual mixed vocabulary is intentional substrate preservation and belongs to a future proof/candidate protocol cleanup slice.
- Do not alter `release/0.1.x`, `v0.1.0-rc.1`, or existing milestone refs.

## 4. Source Audit

### 4.1 Service routes

`src/service/app_v1.py` exposes three public HTTP routes with derivation vocabulary:

- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- `POST /v1/runtime/sessions/{session_id}/derivations/accept`
- `POST /v1/registry/derivations/read`

The route handlers call:

- `evaluate_runtime_derivation(...)`
- `accept_runtime_derivation(...)`
- `read_registry_derivation(...)`

### 4.2 Runtime request shape

`src/service/runtime_v1.py::_compile_runtime_derivation(...)` reads:

```python
derivation = dto.get("derivation")
```

and emits public boundary paths/errors such as:

- `$.derivation`
- `$.derivation.mode`
- `$.derivation.body_confidences`
- `$.derivation.engine_ext`
- `$.derivation.semantics`
- `$.derivation.semantics_profile`

The evaluate response currently returns:

```python
"evaluation": {
    "derivation_id": compiled["derivation_id"],
    "version": compiled["version"],
    "target_pred_id": compiled["target_pred_id"],
    "candidates": [...]
}
```

The candidates themselves also carry `derivation_id` / `derivation_version` because they are serialized `CandidateSet` objects.

### 4.3 Runtime accept shape

`accept_runtime_derivation(...)` accepts a full candidate payload. It reconstructs a `CandidateSet` through `_candidate_from_dict(...)` and calls `session.store.accept(derivation_id=candidate.derivation_id, ...)`.

Implication: renaming candidate payload fields would touch core candidate protocol, accept path, provenance, audit/static consumers, and many tests. This is much larger than route/request rename.

### 4.4 Registry service shape

`src/service/registry_v1.py::read_registry_derivation(...)` expects:

- request key `derivation_id`;
- response key `derivation_spec`;
- registry functions `get_latest_derivation_spec(...)` / `read_derivation_spec(...)`.

`list_registry_assets(...)` returns:

```python
"derivation_ids": registry.list_derivation_ids()
```

### 4.5 SDKRegistry public method surface

`src/kernel/sdk/registry.py` exposes public methods:

- `register_derivation_spec(...)`
- `register_derivation(...)`
- `list_derivation_ids(...)`
- `list_derivation_versions(...)`
- `get_latest_derivation_spec(...)`
- `read_derivation_spec(...)`

Blueprint 1 docs now describe `register_derivation(inference)` as retained substrate vocabulary. This slice can either hard-cut those names or keep them as substrate until the persistence facade replaces `SDKRegistry`.

### 4.6 FileAuthoringRegistry durable substrate

`src/kernel/authoring/registry_fs.py` stores authoring inference specs as:

- manifest key `derivations`;
- manifest item field `derivation_id`;
- relative path `derivations/{id}/{version}.json`;
- return kind `"derivation"`;
- conflict codes/paths such as `registry_derivation_version_conflict` and `$.derivations[...]`.

This is durable-on-disk vocabulary, not just function naming. Renaming it requires tests for manifest/path shape and may need a decision about whether old `derivations/` workspaces are intentionally unsupported in pre-release.

### 4.7 Authoring compiler and application/core substrate

Deep substrate remains derivation-named:

- `compile_authoring_derivation_v1(...)` requires `"derivation_id"` or `"name"`;
- `CompiledDerivationPlan.derivation_id`;
- `DerivationEvaluateRequest`;
- `DerivationAcceptRequest`;
- `CandidateSet.derivation_id` / `derivation_version`;
- `Store.evaluate(..., derivation_id=...)`;
- `Store.accept(..., derivation_id=...)`.

These names span core candidate protocol and proof/audit semantics. Renaming them is a separate substrate/proof cleanup, not automatically part of service wire and registry vocabulary.

### 4.8 Docs and tests

Release-facing service docs still teach:

- `/v1/runtime/sessions/{session_id}/derivations/evaluate`;
- `/v1/runtime/sessions/{session_id}/derivations/accept`;
- `/v1/registry/derivations/read`;
- request key `"derivation"`;
- response fields `derivation_id` and `derivation_spec`;
- registry path examples under `derivations/...`.

One service test still imports public `Derivation` from `kernel.sdk.dsl`, which is stale after Blueprint 1 and should be fixed regardless of route decisions.

## 5. G0 Questions

### 5.1 Q1: Runtime route names

Options:

- **W1a** Hard-cut runtime routes to `/v1/runtime/sessions/{session_id}/inferences/evaluate` and `/inferences/accept`.
- **W1b** Add `/inferences/*` while keeping `/derivations/*` aliases.
- **W1c** Keep `/derivations/*` until a later service-v2 slice.

Recommendation: **W1a**. Product is pre-release and Blueprint 1 already hard-cut SDK public naming.

G0 decision (2026-05-12): **W1a locked**. Runtime routes move to `/v1/runtime/sessions/{session_id}/inferences/evaluate` and `/inferences/accept`; `/derivations/*` public aliases are not introduced.

### 5.2 Q2: Runtime evaluate request key

Options:

- **W2a** Change request top-level key from `"derivation"` to `"inference"` and reject `"derivation"`.
- **W2b** Accept both keys with conflict rejection.
- **W2c** Keep `"derivation"` as service substrate.

Recommendation: **W2a**. Route rename without payload rename leaves the most visible inconsistency.

G0 decision (2026-05-12): **W2a locked**. Runtime evaluate accepts top-level `"inference"` and rejects top-level `"derivation"`.

### 5.3 Q3: Runtime evaluate response envelope

Options:

- **W3a** Change only the top-level response envelope label from derivation-facing terms to inference-facing terms, but keep candidate payload fields as `derivation_id` / `derivation_version`.
- **W3b** Rename response fields `derivation_id` / `derivation_version` to `inference_id` / `inference_version` everywhere the service returns them.
- **W3c** Keep response shape unchanged and document candidate protocol substrate.

Recommendation: **W3a** if a shallow response envelope exists to rename; otherwise **W3c**. Do **not** choose W3b in this slice unless G0 intentionally expands into CandidateSet/core protocol rename.

G0 decision (2026-05-12): **W3a locked**. The runtime evaluate envelope follows the route/request vocabulary and returns `evaluation.inference_id`; nested candidate payloads remain on `derivation_id` / `derivation_version` per W4a.

### 5.4 Q4: Runtime accept candidate fields

Options:

- **W4a** Keep full candidate payload fields `derivation_id` / `derivation_version`; `/inferences/accept` accepts the candidate returned by evaluate unchanged.
- **W4b** Rename candidate payload fields to `inference_id` / `inference_version`.

Recommendation: **W4a**. Accept works by echoing `CandidateSet`; changing candidate field names reaches core candidate protocol, acceptance, audit, static UI, and many tests.

G0 decision (2026-05-12): **W4a locked**. `/inferences/accept` accepts the candidate payload returned by evaluate unchanged; `CandidateSet` fields remain `derivation_id` / `derivation_version`.

### 5.5 Q5: Registry service route and DTO

Options:

- **W5a** Hard-cut `/v1/registry/derivations/read` to `/v1/registry/inferences/read`, request key `inference_id`, response key `inference_spec`.
- **W5b** Add inference route/key while keeping derivation aliases.
- **W5c** Keep registry service derivation vocabulary until persistence facade.

Recommendation: **W5a** if the slice also renames registry storage; **W5c** if G0 defers storage rename. Avoid W5b unless there is a concrete compatibility need.

G0 decision (2026-05-12): **W5a locked**. Registry service hard-cuts to `/v1/registry/inferences/read`, request key `inference_id`, and response key `inference_spec`.

### 5.6 Q6: Registry manifest and filesystem path

Options:

- **W6a** Rename storage from `derivations/` + manifest `derivations` + `derivation_id` to `inferences/` + manifest `inferences` + `inference_id`.
- **W6b** Rename public service/SDKRegistry names only, but keep FileAuthoringRegistry storage on derivation vocabulary.
- **W6c** Defer all registry vocabulary until Blueprint 2 persistence facade.

Recommendation: **W6a** if this slice is meant to remove durable mixed vocabulary before Blueprint 2. This is the largest G0 decision. W6b is intentionally weak: it leaves a second mixed vocabulary layer where service/docs say inference but developer workspaces still contain `registry/derivations/...`.

If W6a is selected, no migration tool is planned for pre-release workspaces. Developer-side guidance should be documented: recreate the registry workspace or rename `registry/derivations/` to `registry/inferences/` and update the manifest shape.

G0 decision (2026-05-12): **W6a locked**. Registry storage moves to `inferences/`, manifest key `inferences`, and manifest item field `inference_id`; pre-release workspaces do not get a migration tool.

### 5.7 Q7: SDKRegistry method names

Options:

- **W7a** Hard-cut public `SDKRegistry` methods to `register_inference*`, `list_inference*`, `read_inference*`, `get_latest_inference_spec`.
- **W7b** Add inference-named methods and keep derivation-named methods as aliases.
- **W7c** Leave `SDKRegistry` vocabulary unchanged because it may be removed/replaced by domain facades.

Recommendation: **W7a** if W6a is selected; **W7c** if W6c is selected. Avoid aliases in pre-release unless tests reveal heavy internal cost.

G0 decision (2026-05-12): **W7a locked**. Public `SDKRegistry` derivation-named methods are hard-cut to inference-named methods, without aliases.

### 5.8 Q8: FileAuthoringRegistry method names

Options:

- **W8a** Rename internal file-registry methods to inference vocabulary together with storage.
- **W8b** Keep FileAuthoringRegistry methods derivation-named while changing only public SDK/service wrappers.

Recommendation: **W8a** only if W6a is selected. If storage becomes `inferences/`, method names should not keep saying derivation.

G0 decision (2026-05-12): **W8a locked**. `FileAuthoringRegistry` method names move to inference vocabulary with the storage shape.

### 5.9 Q9: Authoring compiler public payload key

Options:

- **W9a** Keep compiler substrate key `"derivation_id"`; public `Inference.to_authoring_payload()` keeps emitting it.
- **W9b** Teach `compile_authoring_derivation_v1(...)` to accept `"inference_id"` as canonical and translate to `derivation_id` internally.
- **W9c** Rename compiler to inference vocabulary.

Recommendation: **W9a** for this slice. Compiler/core substrate remains deep application protocol unless G0 expands scope.

G0 decision (2026-05-12): **W9a locked**. The authoring compiler substrate key remains `derivation_id`; `Inference.to_authoring_payload()` continues to emit the compiler-facing key.

### 5.10 Q10: Application/core DTO names

Options:

- **W10a** Keep `CompiledDerivationPlan`, `DerivationEvaluateRequest`, `DerivationAcceptRequest`, `CandidateSet.derivation_id`, and `Store.evaluate(..., derivation_id=...)` unchanged.
- **W10b** Rename application DTOs but keep core CandidateSet.
- **W10c** Full substrate rename.

Recommendation: **W10a**. This slice is service/registry vocabulary, not proof/candidate protocol rewrite.

G0 decision (2026-05-12): **W10a locked**. Application DTOs, core store parameters, `CompiledDerivationPlan`, and `CandidateSet.derivation_id` remain unchanged.

### 5.11 Q11: Error kind/path text

Options:

- **W11a** User-facing service error paths for renamed request keys change to `$.inference...`; internal exception classes and core errors may keep derivation names.
- **W11b** Leave errors derivation-named even after route/key rename.

Recommendation: **W11a**. Route/key rename must be visible in validation errors.

G0 decision (2026-05-12): **W11a locked**. User-facing validation paths for renamed service request keys use `$.inference...`; internal/core error names may remain derivation-named.

### 5.12 Q12: Docs scope

Options:

- **W12a** Update service docs, SDK registry docs, authoring docs, core service-layer docs, and lifecycle design-point in the same slice.
- **W12b** Update only service docs and defer lower-level docs.

Recommendation: **W12a**. This is a vocabulary slice; docs lag would be the main failure mode.

G0 decision (2026-05-12): **W12a locked**. Service, SDK registry, authoring, core service-layer, and lifecycle design-point docs update in this slice.

### 5.13 Q13: Per-spec JSON file content under W6a

W6a renames manifest/path storage to inference vocabulary, while W9a keeps the authoring compiler's substrate input/output on `derivation_id`. The per-spec JSON file content needs an explicit boundary decision.

Options:

- **W13a** Per-spec JSON files under `inferences/{id}/{version}.json` use `inference_id`; `FileAuthoringRegistry` translates between compiler `derivation_id` and registry-file `inference_id` at its boundary.
- **W13b** Per-spec JSON files keep `derivation_id`; only manifest/path use inference vocabulary.
- **W13c** Rename the compiler substrate to `inference_id` as well, effectively choosing W9c.

Recommendation: **W13a**. This gives developer-visible registry workspaces a consistent inference vocabulary while keeping the deeper authoring compiler/core substrate unchanged. The translation boundary is narrow and local to `FileAuthoringRegistry`.

G0 decision (2026-05-12): **W13a locked**. Per-spec registry JSON files use `inference_id`; `FileAuthoringRegistry` translates to/from compiler-facing `derivation_id` at its boundary.

### 5.14 Decision path summary

The questions above collapse into two coherent paths:

G0 locked **Path A**: `W1a + W2a + W3a + W4a + W5a + W6a + W7a + W8a + W9a + W10a + W11a + W12a + W13a`.

**Path A — aggressive vocabulary cleanup (recommended):**

```text
W1a + W2a + W3a + W4a + W5a + W6a + W7a + W8a + W9a + W10a + W11a + W12a + W13a
```

This hard-cuts the public service and registry vocabulary to inference, including file-registry manifest/path, runtime evaluate envelope, and per-spec JSON file shape. It leaves only the deep candidate/proof/compiler substrate on derivation vocabulary: compiler inputs/outputs, candidate payload fields, `CandidateSet.derivation_id`, `CompiledDerivationPlan`, core store parameters, and proof/audit language.

**Path B — conservative service-only cleanup:**

```text
W1a + W2a + W3a/W3c + W4a + W5c + W6c + W7c + W8b + W9a + W10a + W11a + W12a + W13b
```

This hard-cuts runtime service routes and request keys, but leaves registry/service asset vocabulary and storage for the persistence-facade blueprint. It reduces implementation size but preserves more mixed vocabulary.

Avoid the partial middle path unless G0 identifies a specific implementation blocker. In particular, W6b creates public inference naming above a durable `derivations/` filesystem substrate and makes Blueprint 2 harder to reason about.

## 6. Boundaries And Invariants

- Blueprint 1 public SDK `Inference` stays green.
- Track 3 and post-Track-3 semantics wrappers stay green.
- `Inference.to_authoring_payload()` continues to emit the payload expected by the authoring compiler unless G0 explicitly chooses W9b/W9c.
- Runtime accept still accepts the candidate payload returned by runtime evaluate without client-side field rewriting.
- If routes move to `/inferences/*`, the returned candidate payload still carries `derivation_id` / `derivation_version` under W4a/W10a. That is a known residual substrate boundary, not an accidental stale field.
- Proof/audit/static UI uses of "derivation" remain out of scope unless they directly reference service/registry routes touched by this slice.
- `release/0.1.x`, `v0.1.0-rc.1`, and existing milestone refs remain untouched.

## 7. Acceptance

- [x] G0 locks route rename scope.
- [x] G0 locks runtime request/response key behavior.
- [x] G0 locks candidate payload field behavior.
- [x] G0 locks registry service route/key/response behavior.
- [x] G0 locks registry storage path/manifest behavior.
- [x] G0 locks SDKRegistry and FileAuthoringRegistry method-name behavior.
- [x] G0 locks application/core DTO and CandidateSet boundary.
- [x] G0 locks per-spec registry JSON file vocabulary under W6a.
- [x] G1 adds red tests for selected public service/registry rename surface.
- [x] G1 adds guard tests that CandidateSet/application/core substrate remains unchanged if W10a is selected.
- [x] G2 implements only the locked route/storage/method/doc-surface changes.
- [x] G3 updates affected module docs and reference docs.
- [ ] G4 fills §10, marks implemented, and archives this blueprint pair.

## 8. Implementation Plan

Draft sequence, subject to G0:

1. G1 inventory + red baseline:
   - route existence / old-route rejection;
   - request key behavior;
   - registry route + key + response behavior;
   - storage manifest/path/per-spec JSON behavior if W6a locks;
   - guards for CandidateSet and application DTO names if W10a locks.
   - cleanup of the stale service test import from public `Derivation` to public `Inference`; this is Blueprint 1 fallout and should not depend on any G0 choice.
2. G2 service wire implementation:
   - `app_v1.py` route changes;
   - `runtime_v1.py` request-key and error-path changes;
   - service tests and docs-adjacent fixtures.
3. G2 registry implementation:
   - `registry_v1.py` route/key/response changes;
   - `SDKRegistry` / `FileAuthoringRegistry` method and storage changes if selected.
4. G3 docs sync:
   - service runtime docs;
   - service registry docs;
   - SDK API surface registry section;
   - authoring/core docs;
   - lifecycle design-point.
5. G4 close-out and archive.

## 9. Docs To Update

Likely docs if W1a/W2a/W5a/W6a lock:

- `src/service/docs/01_overview.md`
- `src/service/docs/02_runtime_sessions.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `src/service/docs/04_rules_registry.md`
- `src/service/docs/06_frontend_integration.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/authoring/docs/01_overview.md`
- `src/kernel/core/docs/04_service_layer.md`
- `docs/api/openapi.yaml`
- `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`

## 10. Outcome / Deviations

### 10.1 Final Landed Behavior

- Service runtime routes are now `POST /v1/runtime/sessions/{session_id}/inferences/evaluate` and `POST /v1/runtime/sessions/{session_id}/inferences/accept`; the old `/derivations/*` runtime routes are hard-cut.
- Runtime evaluate requests use top-level `"inference"` for the public candidate-producing object; top-level `"derivation"` now fails shape validation.
- Runtime evaluate response envelopes use `evaluation.inference_id` for the public wire envelope.
- Runtime candidate payloads intentionally continue to carry `derivation_id` and `derivation_version`; accept still round-trips the returned candidate object without client-side field rewriting.
- Registry service reads inference assets at `POST /v1/registry/inferences/read`.
- Registry service requests use `inference_id`, and responses use `inference_spec`.
- `FileAuthoringRegistry` stores inference assets under `inferences/{id}/{version}.json`.
- Registry manifests use an `inferences` collection with `inference_id` entries.
- Per-spec registry JSON uses `inference_id`, while compiler-facing payloads continue to use `derivation_id`.
- `FileAuthoringRegistry` owns the W13a translation seam between persisted `inference_id` JSON and compiler-substrate `derivation_id` payloads.
- `SDKRegistry` public methods are now `register_inference_spec`, `register_inference`, `list_inference_ids`, `list_inference_versions`, `get_latest_inference_spec`, and `read_inference_spec`.
- `FileAuthoringRegistry` public methods use the same inference vocabulary for inference asset registration and reads.
- Application/core substrate names remain unchanged: `CompiledDerivationPlan`, `DerivationEvaluateRequest`, `DerivationAcceptRequest`, `CandidateSet.derivation_id`, `Store.evaluate(..., derivation_id=...)`, and provenance standard `derivation_v1`.
- OpenAPI, service docs, SDK registry docs, authoring docs, core service-layer docs, and the lifecycle design-point now document the landed inference wire/registry vocabulary.

### 10.2 Validation

- G1 baseline: `test_inference_wire_registry_vocabulary` started at 15 tests with 8 failures, 3 errors, and 4 guard passes.
- G2 implementation: `test_inference_wire_registry_vocabulary` is 15/15 green after four bottom-up commits.
- G2 regression: kernel discovery is 2057 OK / 1 skipped.
- G2 regression: agent discovery is 255 OK / 2 skipped.
- G2 service note: full service discovery still exposes the pre-existing `test_annotation_consumer_l2` audit import-cycle collection issue; this slice's service Problog annotation test is green.
- G3 docs: stale public-route/public-method grep for `/derivations/*`, registry derivation route/method names, `derivation_spec`, and top-level `"derivation"` request teaching is clean across the updated release-facing docs.
- G3 regression: `test_inference_wire_registry_vocabulary` remains 15/15 green.
- G3 regression: kernel discovery remains 2057 OK / 1 skipped.
- `git diff --check` is clean.

### 10.3 Commit Lineage

```text
f7f4444e docs(service): sync inference wire registry vocabulary
3381335b feat(service): rename runtime routes and request key to inference
4e0234d0 feat(service): rename registry route to inference vocabulary
be06b900 feat(sdk): rename registry methods to inference vocabulary
f0324e83 feat(authoring): rename file registry to inference vocabulary
3dba1a55 test(service): add inference wire registry baseline
610c5c59 docs(blueprints): scope inference wire registry vocabulary
46acd4e0 docs(blueprints): clarify registry json vocabulary boundary
c5757e6e docs(blueprints): refine inference wire registry draft
76ba480b docs(blueprints): draft inference wire registry vocabulary
```

### 10.4 Deviations

- No scope deviations. Path A landed as locked in G0.
- The docs sync included `docs/api/openapi.yaml` and `src/service/docs/02_runtime_sessions.md` in addition to the initially listed docs because both are public references to the renamed service routes.
- The implementation used four G2 commits rather than one large implementation commit to keep the storage translation seam, SDK registry facade, registry service route, and runtime route/request changes independently reviewable.

### 10.5 Archive Notes

This slice closes the user-visible wire/registry vocabulary gap left by
Blueprint 1. Public SDK, service routes, service request keys, registry route
keys, registry method names, manifest entries, and registry file paths now use
`Inference` / `inference` vocabulary.

The remaining `derivation_*` names are deliberately deeper substrate:
candidate/proof/audit protocol, application DTOs, compiler payloads, core store
parameters, and provenance version identifiers. That boundary keeps the public
authoring object vocabulary coherent without forcing a much larger
candidate/proof protocol rename.

Blueprint 2 can now start from a cleaner model: public persistence facade work
can target `fg.rules.*` and `fg.inferences.*` without first reconciling a
persistent `derivations/` registry surface.
