# Stage 1 Audit: Slice 6 — Form I Legacy Debt vs Shipped Surface

- Branch: `v0.2.0-form-i-debt-audit-2026-05-30`
- Fork point: `00488a6e` (Slice 5 archive head)
- Date: 2026-05-30
- Mode: read-only Stage 1 audit
- Status: draft audit

## 1. Audit Question

Slice 5 Step 6 found one import-time failure in
`tests/test_application_rule_disable_runtime_native.py` caused by the
hard-removed Slice 1 Form I surface `Identity(primary_key=True)`.

This audit asks whether that was an isolated stale fixture or a broader legacy
debt surface, and what the next Slice 6 scope should be.

Deprecated Form I call shapes surveyed:

- `Identity(...primary_key...)`
- `Identity(...default=...)`
- `Identity(...default_factory=...)`
- `Field(...cardinality=...)`
- `allow_identity_defaults=True`

## 2. Method

The grep inventory was run against committed audit-branch HEAD, not the dirty
working tree, so dirty notebooks and untracked reference folders do not distort
the baseline.

Representative commands:

```bash
git grep -n -E 'Identity\([^)]*primary_key' HEAD --
git grep -n -E 'Identity\([^)]*default\s*=' HEAD --
git grep -n -E 'Identity\([^)]*default_factory\s*=' HEAD --
git grep -n -E 'Field\([^)]*cardinality\s*=' HEAD --
git grep -n -E 'allow_identity_defaults\s*=\s*True' HEAD --
```

Import probes used `PYTHONPATH=src python -c 'import ...'` on representative
live test modules.

## 3. Baseline Counts

| Pattern | HEAD hits | Notes |
|---|---:|---|
| `Identity\([^)]*primary_key` | 252 | Includes live tests, examples, current docs, historical docs, archive material, and migration examples. |
| `Identity\([^)]*default\s*=` | 46 | Includes current negative docs, live tests, and archive/historical docs. |
| `Identity\([^)]*default_factory\s*=` | 41 | Mostly historical/archive plus one live test fixture. |
| `Field\([^)]*cardinality\s*=` | 336 | Broadest live test fixture debt plus migration-hint text. |
| `allow_identity_defaults\s*=\s*True` | 11 | 8 live test callsites plus historical blueprint/design text. |

Tracked file buckets with at least one deprecated shape:

| Bucket | Files | Initial disposition |
|---|---:|---|
| `tests/` | 63 | Required migration or explicit negative-test rewrite. |
| `src/` | 7 | Mixed: sibling package tests/docs likely current, `src/factgraph/sdk/schema.py` migration hints are valid. |
| current docs (`README.md`, `docs/official`, `src/factgraph/sdk/docs`) | 3 | Root README is stale current truth; SDK docs/official quickstart hits are mostly migration examples/current negative wording. |
| `examples/` | 9 | Active dirty notebooks plus archive examples; needs dirty/archive freeze rules. |
| tools/tutorial/reference docs | 12+ | Mixed current executable tools and historical/reference material. |
| active workflow/audit/decision/design docs | 11 | Mostly historical decision/audit references; needs carve-out. |

## 4. Eight Audit Questions

### Q1. Is the known failing test isolated?

No. `tests/` has 63 tracked files with at least one deprecated Form I shape.
Representative import failures:

- `tests/test_application_rule_disable_runtime_native.py:34` raises
  `SDKSchemaError` at import on `Identity(primary_key=True)`.
- `tests/test_application_entity_view.py:20` raises `SDKSchemaError` at import
  on `Identity(primary_key=True)`.

The debt is repo-wide in live tests, not a single Step 6 leftover.

### Q2. Are sibling package tests affected?

Yes. `src/service/tests`, `src/domains/ecss/tests`, and `src/agent/extraction`
contain Form I legacy callsites. Representative failure:

- `src/service/tests/test_runtime_query_policy.py:11` raises
  `SDKSchemaError` at import on `Identity(primary_key=True)`.

This matches the older Slice 1 audit warning that sibling packages using
`factgraph.sdk` must be included if descriptor behavior is already hard-removed.

### Q3. Are current docs affected?

Yes, but unevenly.

- `README.md:53-58` is current quickstart text and still shows
  `Identity(primary_key=True)`, `Field(cardinality="single")`, `fg.read.ref`,
  and `fg.write.set`; this is stale current truth.
- `docs/official/kernel/quickstart/schema.md:55-56` states that
  `Identity(default=...)` / `Identity(default_factory=...)` are not part of
  Form I; this is correct current negative wording.
- `src/factgraph/sdk/docs/04_api_surface.en.md:110-112` is a migration example
  Old row; this is a valid historical/migration carve-out.

### Q4. Are examples/notebooks affected?

Yes. Tracked examples with hits:

- Active dirty notebooks: `examples/01_sdk_check_diagnose.ipynb`,
  `examples/02_overlay_why_not_frontier.ipynb`.
- Archive examples: `examples/archive/01_sdk_basics.ipynb`,
  `02_rules_and_derivations.ipynb`, `05_dora_pyreason_propagation.ipynb`,
  `06_problog_probabilistic.ipynb`, `10_v01_onboarding_journey.ipynb`,
  `11_capabilities_e2e_demo.ipynb`, `11_capabilities_e2e_demo.py`.

The active dirty notebooks should inherit the Slice 4/Slice 5 dirty-baseline
rule: no automatic overwrite; per-file authorization or record untouched.
Archive examples should remain out of scope unless linked as current tutorials.

### Q5. Are tools/tutorials affected?

Yes.

- `tools/benchmarks/...` contains executable benchmark scripts using legacy
  Form I descriptors.
- `tutorials/evidence-pipeline.cn.md` is tutorial prose/code that presents old
  Form I as current.

These are lower priority than live tests but likely in-scope if Slice 6 is a
repo-current cleanup rather than test-only.

### Q6. Are source runtime modules affected?

No runtime implementation module needs a Form I behavior change. The only
`src/factgraph` source hit is `src/factgraph/sdk/schema.py:152-153`, which is
the intentional migration hint emitted when users pass `Field(cardinality=...)`.
That text should be preserved.

### Q7. Is a Stage 2 Q-decision needed?

Probably no, if the next slice accepts the following already-established
policy:

- live tests/current docs/examples/tools migrate to Form I;
- historical/archive/migration examples are preserved with explicit carve-outs;
- dirty notebooks require per-file user authorization before edit.

A Stage 2 Q-decision is only needed if the team wants to redefine historical
carve-outs, include archive examples, or merge unrelated cleanup.

### Q8. Should this merge with shadow-store removal or other carry-forward work?

No. The audit finds broad callsite debt, but no new design decision. Combining
with shadow-store removal, Q-PR1 work, or runtime descriptor changes would turn
a housekeeping slice into a cross-runtime slice and weaken cadence discipline.

## 5. Five-Bucket Triage

### Required

| ID | Finding | Evidence | Why required |
|---|---|---|---|
| FI-R1 | Live `tests/` still contain hard-removed Form I constructors. | 63 tracked test files hit the deprecated-shape grep; representative import failures in `tests/test_application_rule_disable_runtime_native.py:34` and `tests/test_application_entity_view.py:20`. | Test modules cannot be reliably imported/run until fixtures are migrated or negative tests are rewritten. |
| FI-R2 | Sibling package tests under `src/` also fail on hard-removed constructors. | `src/service/tests/test_runtime_query_policy.py:11`; `src/domains/ecss/tests/test_phase3_contracts_v1.py:158`; `src/agent/extraction/docs/USAGE.md:28-29`. | These use `factgraph.sdk` and are current repo surfaces, not archive material. |
| FI-R3 | Root README current quickstart is stale. | `README.md:53-58` still shows `Identity(primary_key=True)`, `Field(cardinality="single")`, `fg.read.ref`, and `fg.write.set`. | New users hit stale current truth at repo entry. Slice 4 did not cover root README. |
| FI-R4 | `allow_identity_defaults=True` live tests still exist. | `tests/test_application_entity_view.py:62,132,153,171`; `tests/test_application_schema_runtime.py:74,103,129,143`. | The old selector kwarg is removed; these tests need rewrite or explicit negative-test treatment. |
| FI-R5 | Existing negative/legacy tests need semantic rewrite, not blind substitution. | `tests/test_sdk_schema_primary_key_required.py` imports successfully but asserts old "primary key required" behavior and old error text. | Mechanical `Identity()` replacement would produce false green or meaningless tests; blueprint must classify negative-test rewrites. |

### Recommended

| ID | Finding | Evidence | Recommendation |
|---|---|---|---|
| FI-REC1 | Tools benchmark scripts use stale descriptors. | `tools/benchmarks/extraction/run_cross_provider_benchmark.py`, `run_multi_model_entity_benchmark.py`, `run_re_docred.py`. | Include if Slice 6 scope is "current executable repo surfaces"; otherwise record carry-forward. |
| FI-REC2 | `tutorials/evidence-pipeline.cn.md` presents old Form I as current. | `tutorials/evidence-pipeline.cn.md:72-81`. | Migrate if tutorials are considered current docs. |
| FI-REC3 | `src/agent/extraction/docs/USAGE.md` is stale current docs. | `src/agent/extraction/docs/USAGE.md:28-29`. | Migrate alongside sibling package docs if `src/agent` is in scope. |
| FI-REC4 | Use precise grep gates to avoid migration-example false positives. | `src/factgraph/sdk/docs/04_api_surface.en.md:110-112`; `docs/official/kernel/quickstart/schema.md:55-56`. | Final gate should classify remaining hits, not require absolute zero across historical/migration text. |

### Verified

| ID | Verified fact | Evidence |
|---|---|---|
| FI-V1 | Form I runtime descriptor behavior is already hard-removed. | `src/factgraph/sdk/schema.py:97-113` rejects any `Identity` legacy kwargs; `:143-156` rejects any `Field` legacy kwargs. |
| FI-V2 | `src/factgraph/sdk/schema.py` `Field(cardinality=...)` hits are intentional migration hints. | `src/factgraph/sdk/schema.py:152-153`. |
| FI-V3 | Official schema quickstart default hits are correct negative/current wording. | `docs/official/kernel/quickstart/schema.md:55-56`. |
| FI-V4 | SDK API surface old-form hits are migration examples, not current truth. | `src/factgraph/sdk/docs/04_api_surface.en.md:110-112`. |
| FI-V5 | Q-PR1 sacred paths do not need changes for this cleanup. | Form I callsite migration is outside `core/evidence/write_protocol.py`, `core/store/ledger.py`, `_builders.py`, `adapters/pyreason/`, and `core/derivation/accept.py`. |

### Scoped Detail

| ID | Detail | Stage 4 implication |
|---|---|---|
| FI-S1 | Dirty notebooks `examples/01_sdk_check_diagnose.ipynb` and `02_overlay_why_not_frontier.ipynb` contain stale Form I and are already dirty. | Default untouched unless user authorizes per-file edits; record state in audit/outcome. |
| FI-S2 | Archive examples contain many old forms. | Keep `examples/archive/*` out of scope unless an active current doc links them as tutorial truth. |
| FI-S3 | Active workflow/audit/design decision docs intentionally mention removed forms as historical decision/audit material. | Preserve historical/migration references; only current-status docs should be rewritten. |
| FI-S4 | Negative tests require semantic decisions per file. | Stage 4 plan should separate positive fixture migration from negative behavior rewrite. |
| FI-S5 | Pytest may still hit local readline/segfault issues. | Use direct import/smoke invocations when pytest itself is unstable, but record commands. |

### Abandonment

| ID | Rejected path | Rationale |
|---|---|---|
| FI-A1 | Do not change Form I runtime descriptor behavior. | Runtime already enforces hard removal; Slice 6 is callsite/test/docs cleanup. |
| FI-A2 | Do not merge shadow-store, Q-PR1, or `:exists` work. | Unrelated to Form I callsite debt and would expand a housekeeping slice into a runtime design slice. |
| FI-A3 | Do not blanket-rewrite archive/history. | Historical text is valuable context and should be handled by explicit archive/historical carve-out rules. |
| FI-A4 | Do not auto-overwrite dirty notebooks. | User dirty baseline must remain protected; notebook edits require per-file authorization. |

## 6. Proposed Slice 6 Shape

Recommended next step: skip Stage 2 Q-decision unless reviewer finds a true
policy conflict, then draft a scoped blueprint for **Form I Legacy Debt Cleanup**.

Suggested Scope Freeze locks:

| SF | Lock |
|---|---|
| SF1 | Runtime descriptor behavior is already shipped; no changes to `Identity` / `Field` semantics. |
| SF2 | Q-PR1 sacred paths remain 0 diff. |
| SF3 | Positive live tests and sibling package tests migrate to `Identity()` / `Field()` with annotation-inferred cardinality and explicit identity values. |
| SF4 | Negative tests are rewritten semantically rather than mechanically substituted. |
| SF5 | Current docs (`README.md`, tutorials, current package docs) migrate; migration examples and historical notes may remain with explicit classification. |
| SF6 | Dirty notebooks are not auto-overwritten; per-file authorization required. |
| SF7 | `examples/archive/*`, `workflow/heritage/*`, and archived blueprints/design-points are out of scope unless linked by active current docs. |
| SF8 | No shadow-store, `:exists`, Q-PR1, ledger schema, or adapter work. |

Likely implementation phases:

1. Step 0 inventory freeze: exact tracked file list, dirty notebook state, and negative-test classification.
2. Step 1 live core test fixtures: `tests/` root plus `tests/application` / `tests/sdk`.
3. Step 2 sibling package tests: `src/service/tests`, `src/domains/ecss/tests`, and any `src/agent` test/doc fixtures selected by scope.
4. Step 3 negative-test rewrites: especially `test_sdk_schema_primary_key_required.py` and `allow_identity_defaults` tests.
5. Step 4 current docs/tutorials/tools migration.
6. Step 5 dirty notebook decision point.
7. Step 6 final grep gate with historical/migration carve-out table, outcome, and archive.

## 7. Reviewer Questions

| OQ | Question | Audit recommendation |
|---|---|---|
| OQ1 | Should Slice 6 include all 63 `tests/` files with stale Form I callsites? | Yes. This is the main live breakage surface. |
| OQ2 | Should sibling package tests under `src/service`, `src/domains`, and `src/agent` be in scope? | Yes for tests/current docs that import `factgraph.sdk`. |
| OQ3 | Should tools/benchmark scripts be in scope? | Recommended yes if treated as current executable examples; otherwise explicit carry-forward. |
| OQ4 | Should dirty active notebooks be edited? | Default no; only with per-file user authorization. |
| OQ5 | Should archive examples and heritage docs be migrated? | No by default. Preserve as historical/archive material. |
| OQ6 | Should root README and tutorials be migrated? | Yes for current truth. Root README is a Required gap. |
| OQ7 | Is Stage 2 Q-decision required? | No unless reviewer wants to change historical/dirty/archive policy. |
| OQ8 | Should this merge with shadow-store or other carry-forward cleanup? | No. Keep Slice 6 housekeeping-only. |

## 8. Per-Commit Ritual Result

- Branch: `v0.2.0-form-i-debt-audit-2026-05-30`
- Fork point: `00488a6e`
- Sacred master observed: `562c74195df43e933bed92a3ff25de94dd8ce666`
- Q-PR1 paths: no audit edits planned or needed
- Dirty baseline: preserved; audit grep fixed to `HEAD` to avoid dirty working tree noise
- Push: not performed
