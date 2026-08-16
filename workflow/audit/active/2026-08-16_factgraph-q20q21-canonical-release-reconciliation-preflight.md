# Preflight: FactGraph Q20/Q21 canonical release reconciliation

- Status: complete
- Created: 2026-08-16
- Last Updated: 2026-08-16
- Authority: independent Step 4.3 working triage. It identifies
  blueprint-vs-shipped drift before a scoped anchor; it neither authorizes a
  private implementation, public projection, public push/PR, merge, tag, wheel
  upload, nor Meander consumption.
- Inputs:
  - [draft blueprint](../../blueprints/active/2026-08-16_factgraph-q20q21-canonical-release-reconciliation.md)
    and [paired audit log](../../blueprints/active/2026-08-16_factgraph-q20q21-canonical-release-reconciliation.audit.md)
    at `e77cb7df962946ed6d1d8b419f7526df6a34acbe`.
  - Private HNSM canonical baseline
    `c01dccae5c524d667dd4414201be3961312076df`.
  - Public FactGraph baseline
    `b92d6bf5405be8d15eedea5b97aa7408914e76b9` and independently
    developed candidate `6d7628cd2019b1d2cdd243546c7502684500fd95`.
  - [Q20/Q21 release-surface audit](2026-08-16_factgraph-q20q21-release-surface-vs-shipped.md),
    [architecture release-surface rule](../../foundations/architecture_principles.md#22-release-surface-governance),
    [FactGraph sync runbook](../../factgraph_sync.md),
    `scripts/project_release_surface.sh`, `scripts/release_surface_allowlist.txt`,
    `scripts/release.sh`, the private CI/package files, and the public
    `b92`/candidate CI/package files.
- Outputs / Downstream:
  - Step 4.4 amendment on the blueprint branch. The required decisions are
    listed in [§6](#6-recommended-step-44-amendment-actions).
- Related:
  - Candidate worktree: `/private/tmp/factgraph-q20q21-reconcile-2026-08-15`.
  - Private preflight worktree:
    `/private/tmp/hnsm-factgraph-q20q21-release-reconcile-preflight-2026-08-16`.
- Blueprint: [FactGraph Q20/Q21 canonical release reconciliation](../../blueprints/active/2026-08-16_factgraph-q20q21-canonical-release-reconciliation.md)
- Branch: `features/factgraph-q20q21-release-reconcile-preflight-2026-08-16`

> Trigger: this is a cross-module, protocol, release-surface, and
> pre-release-verification slice. Preflight is therefore required by CADENCE
> Step 4.3. The candidate is comparison evidence only; it is not a private
> source ref, public release, artifact, or Meander dependency.

## 1. Preflight scope and re-read record

The following shipped and candidate material was re-read while drafting the
rows below, rather than inferred from commit messages:

1. Every path in `b92d6bf5..6d7628cd` (50 tracked paths, `23,186` additions
   and `533` deletions), with its private `c01` counterpart where present.
   Candidate direct FactGraph imports and every candidate test entrypoint were
   re-enumerated for the closure keys in §2.3.
2. The R3d collision pair in full: candidate
   `evaluation_run_evidence_runtime.py`/`evaluation_run_evidence.py` and the
   existing private `evaluation_run_evidence_runtime.py`, plus their direct
   tests. The former returns a `CapturedReceiptEvidenceV0`; the latter returns
   an `EvidenceGraph` from the same public function name.
3. The candidate R3e/F4C-a/F4C-b1 coordinate modules and their tests, the
   candidate `application.__init__`, protocol exports, `EvaluateResult`, SDK
   bridge, native lowering, effective-relation bridge, and Store freshness
   changes. The private counterparts were also re-read where they already
   implement richer Function, navigation, Scenario, or Policy behavior.
4. The complete 294-entry private release allowlist, projection script,
   release script, sync runbook, private CI/package metadata, and public
   baseline/candidate CI/package metadata.

The three commits are not a linear source graph. `b92d6bf5` is not an ancestor
of `c01dccae`; `c01` is the only development-source baseline. The candidate
range contains **6 private-absent paths, 1 candidate-identical path, 4 paths
where private equals the public base, and 39 divergent private paths**. Thus
the source is neither blank nor a safe cherry-pick target.

### 1.1 Projection observation made during preflight

Running the existing projection script against private `c01` was a diagnostic
check only; it failed before any release action:

```text
FAIL: projected docs contain private/excluded path references:
.../src/factgraph/sdk/docs/README.md:62:
  ...examples/09_product_scenario_execution_v2.ipynb
```

That is not limited to the candidate's uncommitted Q20/Q21 docs. The current
allowlist copies private module docs and root public-owned files despite the
sync runbook classifying them as surface-owned. It also copies private
`CONTRIBUTING.md` and `CHANGELOG.md`; those contain governance/historical
references that the current script's Markdown scan does not inspect because it
only scans `README*`, `docs/`, and `src/factgraph/`. The failure is evidence of
a release-composition shape conflict, not a reason to relax the deny/link gate.

## 2. Auditable three-way path, import, and test matrix

### 2.1 Matrix notation

`Δ` means the candidate changes an existing `b92` path; `+` means it adds a
path absent from `b92`. Private relation uses the exact private `c01` blob:

- `D` — private content differs from both the public base and candidate.
- `A` — the path is absent from private `c01`.
- `B` — private content equals public `b92`; candidate has the only delta.
- `C` — private content equals candidate.

Disposition keys are defined in §2.3. `manual` always means reconstruct or
extract the reviewed behavioral delta on a new private branch; it never means
copy/cherry-pick a public candidate commit.

### 2.2 One row for every tracked candidate path

| Candidate path | Δ | `c01` | Reconciliation / projection class | Closure and proof obligation |
| --- | --- | --- | --- | --- |
| `.github/workflows/factgraph-tests.yml` | Δ | D | `P1`: public-owned explicit patch only | `S7`; public PR CI must name the approved cohort. |
| `pyproject.toml` | Δ | D | `P1`: public-owned metadata only; candidate adds pytest dev tooling, not a version decision | `S7`; wheel build environment and public `.[dev]` install proof. |
| `src/factgraph/application/__init__.py` | Δ | D | `F1`: public-façade overlay from b92 plus an explicit public export allowlist; never copy/merge private façade wholesale | `S1/S2/S3/S7`; exact `__all__`, negative exports, installed-wheel imports. |
| `src/factgraph/application/_evaluation_run_receipt_coordinate_manifest_runtime.py` | + | A | `X1`: candidate R3e/F4C-b1 private seam; defer from this Q20/Q21 reconcile unless separately scoped | `S4`; no public projection/SDK/Product/Meander/Agent/MCP export. |
| `src/factgraph/application/_evaluation_run_receipt_coordinate_overlay_runtime.py` | + | A | `X1`: candidate R3e/F4C-a private seam; defer from this reconcile | `S4`; no generic graph/proof/public wire claim. |
| `src/factgraph/application/derivation_runtime.py` | Δ | D | `M2`: extract native effective-relation observer without discarding private orchestration | `S2/S6`; `T18` plus private preservation cohort. |
| `src/factgraph/application/evaluation_query_runtime.py` | + | D | `M1`: preserve private navigation/function-aware query shape; compare candidate basic contract only | `S1/S2`; `T05`, `T14`, retained private navigation tests. |
| `src/factgraph/application/evaluation_run_bundle_runtime.py` | + | D | `M2`: merge bounded codec/live-binding hardening into private capture variants | `S2/S3`; `T06/T07/T10/T14/T18`. |
| `src/factgraph/application/evaluation_run_evidence_runtime.py` | + | D | `M3`: name/type collision; retain private graph builder and add R3d under a distinct builder/module | `S3/S5`; split `T07` from existing graph playback tests. |
| `src/factgraph/application/evaluation_run_runtime.py` | + | D | `M1`: preserve private target/navigation anchoring; manually take only compatible candidate anchor hardening | `S1/S2`; `T04/T14` plus private target tests. |
| `src/factgraph/application/evaluation_run_verification_runtime.py` | + | D | `M2`: merge pin/preflight changes without recasting verification as replay | `S2`; `T10`, bounded-work and no-Store fallback tests. |
| `src/factgraph/application/explain/prober.py` | Δ | D | `M3`: preserve existing Explain S5 behavior; candidate changes need an Explain regression review | `S5`; `T15/T16` and existing prober cohort. |
| `src/factgraph/application/policy_runtime.py` | + | D | `M1`: private Policy is richer (Function, navigation, compare, weighted choice); candidate is not replacement | `S1`; `T11` plus private V2/Function preservation. |
| `src/factgraph/application/protocol/__init__.py` | Δ | D | `F1`: public-protocol façade overlay from b92 plus an explicit public export allowlist | `S1/S2/S3/S7`; exact `__all__`, negative exports, installed-wheel imports. |
| `src/factgraph/application/protocol/evaluate_result.py` | Δ | D | `M2`: merge live anchor/bundle binding hardening into private Scenario/expectation model | `S2/S5`; `T03/T14`, stale/splice preservation. |
| `src/factgraph/application/protocol/evaluation_query.py` | + | D | `M1`: preserve private navigation DTOs; candidate base Query is not replacement | `S1`; `T05/T14`, private navigation tests. |
| `src/factgraph/application/protocol/evaluation_run.py` | + | D | `M1`: preserve target/navigation fields and their seals | `S1/S2`; `T04/T14`, private target tests. |
| `src/factgraph/application/protocol/evaluation_run_bundle.py` | + | D | `M2`: merge codec/seal changes only after private extended shape is revalidated | `S2/S3`; `T06/T10/T14`. |
| `src/factgraph/application/protocol/evaluation_run_evidence.py` | + | A | `M3`: strict additive R3d DTO only; no `EvidenceGraph` or Explanation conversion | `S3`; `T07` plus negative consumer tests. |
| `src/factgraph/application/protocol/evaluation_run_verification.py` | + | D | `M2`: preserve verification record shape/limits while adopting reviewed fail-closed checks | `S2`; `T10`. |
| `src/factgraph/application/protocol/policy.py` | + | D | `M1`: preserve private richer Policy AST/lineage; candidate v0 subset is not replacement | `S1`; `T11`, private Function/navigation/compare/weighted tests. |
| `src/factgraph/application/protocol/rule_expr.py` | Δ | D | `M1`: manual merge against private Function/V2 rule-expression state | `S1`; `T01/T03/T04`. |
| `src/factgraph/application/protocol/rule_expr_inspect.py` | Δ | D | `M1`: carry only compatible inspect behavior | `S1`; `T03` and existing inspect preservation. |
| `src/factgraph/application/protocol/rule_expr_lowering.py` | Δ | D | `M2`: separate R3e coordinate tracing from Q20/R3d scope; do not let coordinate capture imply proof parity | `S1/S2/S4`; `T03/T04`, `T08` only in a later R3e scope. |
| `src/factgraph/application/protocol/semantic_address.py` | + | D | `M1`: private evolution wins; compare candidate only for compatible invariant fixes | `S1`; `T12`. |
| `src/factgraph/application/protocol/semantic_port.py` | + | D | `M1`: retain private Function endpoint support; candidate is narrower | `S1`; `T13` and private Function tests. |
| `src/factgraph/application/semantic_address_runtime.py` | + | D | `M1`: preserve private address-space extensions | `S1`; `T12`. |
| `src/factgraph/application/semantic_port_runtime.py` | + | D | `M1`: preserve private resolver extensions | `S1`; `T13`. |
| `src/factgraph/core/rules/where_eval.py` | Δ | B | `M2`: candidate-only context-local gate may be extracted after compatibility review | `S6`; `T17`, capture gate regressions. |
| `src/factgraph/core/store/_evaluate.py` | Δ | D | `M2`: merge observer/effective-relation capture without discarding private evaluator variants | `S2/S6`; `T18`, private Scenario/engine cohort. |
| `src/factgraph/core/store/runtime.py` | Δ | D | `M2`: merge freshness revision behavior without reducing private Store surface | `S2/S6`; stale policy mutation tests. |
| `src/factgraph/sdk/store.py` | Δ | D | `M2`: high-risk bridge; preserve private Scenario/expectation/Product execution paths | `S1/S2/S5`; `T14`, private SDK cohort. |
| `tests/application/protocol/test_evaluate_result_dtos.py` | Δ | D | `T1`: merge anchor/bundle invariants into private result tests | `S2/S5`; run as Q20-core. |
| `tests/application/protocol/test_evaluation_run.py` | + | D | `T1`: merge only against extended private Run DTO | `S1/S2`; run as Q20-core. |
| `tests/application/protocol/test_rule_expr_lowering.py` | Δ | D | `T1`: preserve existing lowerer behavior and add reviewed compatible assertions | `S1`; run as Q20-core. |
| `tests/application/protocol/test_rule_expr_native_coordinates.py` | + | A | `T3`: R3e-only candidate test; defer with `S4` | no Q20/R3d public cohort. |
| `tests/application/test_evaluation_query_runtime.py` | + | D | `T1`: merge against private query navigation/Function behavior | `S1`; Q20-core plus private preservation. |
| `tests/application/test_evaluation_run_bundle_runtime.py` | + | D | `T1`: merge capture hardening tests against private bundle shape | `S2`; Q20-core. |
| `tests/application/test_evaluation_run_evidence_runtime.py` | + | D | `T2`: split strict R3d receipt tests from the retained private graph playback tests | `S3/S5`; explicit type/availability negative tests. |
| `tests/application/test_evaluation_run_receipt_coordinate_manifest_runtime.py` | + | A | `T3`: F4C-b1 test; defer with `S4` | no public CI/cohort. |
| `tests/application/test_evaluation_run_receipt_coordinate_overlay_runtime.py` | + | A | `T3`: F4C-a test; defer with `S4` | no public CI/cohort. |
| `tests/application/test_evaluation_run_verification_runtime.py` | + | D | `T1`: merge non-replay, bounded isolated verification checks | `S2`; Q20-core. |
| `tests/application/test_policy_runtime.py` | + | D | `T1`: retain private richer Policy cases | `S1`; Q20-core plus V2 preservation. |
| `tests/application/test_semantic_address_runtime.py` | + | D | `T1`: merge address strictness cases | `S1`; Q20-core. |
| `tests/application/test_semantic_port_runtime.py` | + | C | `T1`: candidate-identical; retain as a baseline test after import closure check | `S1`; Q20-core. |
| `tests/sdk/test_evaluation_query_evaluate.py` | + | D | `T1`: merge live bridge/capture tests without reducing private Scenario/expectation coverage | `S1/S2/S5`; Q20-core plus private SDK cohort. |
| `tests/sdk/test_explain_atom_support.py` | Δ | B | `T1`: candidate-only Explain assertion delta; retain existing EvidenceGraph contract | `S5`; preservation. |
| `tests/sdk/test_explain_composite_closed_head_false.py` | Δ | B | `T1`: candidate-only Explain assertion delta; retain existing EvidenceGraph contract | `S5`; preservation. |
| `tests/test_core_rules_where_eval_disabled_locators.py` | Δ | B | `T1`: candidate-only gate test delta | `S6`; Q20-core. |
| `tests/test_native_effective_relation_capture.py` | + | D | `T1`: merge single-relation capture proof into private evaluator tests | `S2/S6`; Q20-core. |

### 2.3 Closure-key ledger

| Key | Direct import/export closure to re-check on private implementation | Required test proof |
| --- | --- | --- |
| `S1` semantic compiler | semantic port/address → managed occurrence → Policy → EvaluationQuery → RuleExpr lowering → application/protocol exports → SDK bridge | `T03–T05`, `T11–T14`, plus private Function/navigation/compare/weighted-choice preservation. |
| `S2` live execution and capture | SDK `evaluate` → `EvaluateResult` live pins → run anchor/bundle → derivation runtime → core effective relation/Store freshness | `T01/T02/T04/T06/T10/T14/T18`; stale, splice, zero-row, and no-fallback cases. |
| `S3` R3d receipt inventory | fresh decoded `EvaluationRunBundleV0` → selected native receipt → new strict receipt DTO | `T07`: no Store/ledger/cache/sidecar/registry/evaluator, selector ambiguity/zero-row fail-closed, nested seal checks, and rejection by generic graph/render/Explanation consumers. |
| `S4` R3e/F4C private material | compiler native-coordinate trace + original SDK identity registry + receipt overlay/manifest | `T08/T09/T10` only in a separately scoped private seam; no public project/export cohort in this slice. |
| `S5` existing Explain | `EvaluateResult`/`EvaluateRow` live graph builder → prober → `EvidenceGraph`/renderer | `T15/T16` and existing prober tests; receipt DTO must never satisfy graph assumptions. |
| `S6` core relation/freshness | where-AST gate → core `_evaluate` observer → immutable native relation → Store premise-policy revision | `T17/T18` plus native preservation tests. |
| `S7` public composition | private kernel/test manifest + b92 public-owned surface + explicit public patch → public worktree → wheel | manifest/deny/link/import closure, public PR CI, clean installed-wheel smoke, package-content inspection. |
| `F1` public façades | public `application.__init__`, `application.protocol.__init__`, and `sdk.__init__` start from b92 and receive only a named public-export-allowlist delta; the HNSM kernel manifest does not supply whole façade files | exact `__all__`/negative-export tests and installed-wheel imports; no R3e/F4C/SDK receipt export by accidental private façade merge. |

Candidate test identifiers used above:

| ID | Candidate test entrypoint |
| --- | --- |
| `T01` | `tests/application/protocol/test_evaluate_result_dtos.py` |
| `T02` | `tests/application/protocol/test_evaluation_run.py` |
| `T03` | `tests/application/protocol/test_rule_expr_lowering.py` |
| `T04` | `tests/application/protocol/test_rule_expr_native_coordinates.py` |
| `T05` | `tests/application/test_evaluation_query_runtime.py` |
| `T06` | `tests/application/test_evaluation_run_bundle_runtime.py` |
| `T07` | `tests/application/test_evaluation_run_evidence_runtime.py` |
| `T08` | `tests/application/test_evaluation_run_receipt_coordinate_manifest_runtime.py` |
| `T09` | `tests/application/test_evaluation_run_receipt_coordinate_overlay_runtime.py` |
| `T10` | `tests/application/test_evaluation_run_verification_runtime.py` |
| `T11` | `tests/application/test_policy_runtime.py` |
| `T12` | `tests/application/test_semantic_address_runtime.py` |
| `T13` | `tests/application/test_semantic_port_runtime.py` |
| `T14` | `tests/sdk/test_evaluation_query_evaluate.py` |
| `T15` | `tests/sdk/test_explain_atom_support.py` |
| `T16` | `tests/sdk/test_explain_composite_closed_head_false.py` |
| `T17` | `tests/test_core_rules_where_eval_disabled_locators.py` |
| `T18` | `tests/test_native_effective_relation_capture.py` |

### 2.4 Explicitly omitted dirty documentation/example material

These six paths are not part of `b92..6d`; they are dirty/untracked in the
candidate worktree. They remain private acceptance material and must not be
staged, reconstructed, projected, or used as release proof in this slice.

| Path | Current state | Reason for omission |
| --- | --- | --- |
| `src/factgraph/application/docs/README.md` | modified, uncommitted | Links/claims require a separate curated-doc decision. |
| `src/factgraph/application/docs/rule.md` | modified, uncommitted | Links to excluded `examples/` and mixes later R3e/F4C material. |
| `src/factgraph/application/protocol/docs/README.md` | modified, uncommitted | Module-doc surface is private/default-denied here. |
| `src/factgraph/sdk/docs/04_api_surface.en.md` | modified, uncommitted | SDK surface cannot be enlarged from an application seam. |
| `examples/native_evaluation_query_capture_v0.py` | untracked | `examples/` is excluded by default-deny projection. |
| `tests/examples/test_native_evaluation_query_capture_v0.py` | untracked | Example tests are not release evidence until a curated example slice exists. |

## 3. 5-bucket findings

### 3.1 Required amendment before scoped

#### PF-R1 — private canonical is a divergent, richer implementation, not an empty import target

The blueprint correctly rejects a direct cherry-pick, but it still describes a
reconstruction as though candidate Q20/Q21 behavior were mostly absent from
private `c01`. That is false. Thirty-nine candidate paths have divergent private
counterparts. In particular, private `c01` already adds Function endpoints,
field navigation, Policy comparisons/weighted choices, Scenario/expectation
flows, and extended run DTOs which the candidate's narrower sources omit.

**Required amendment:** replace the implementation premise with a
private-preserving delta-extraction rule. Every `D` matrix row must name the
private behavior to preserve and the candidate behavior to extract; tests must
run both the Q20-core cohort and the private Function/navigation/Policy/Scenario
preservation cohort. No candidate file is an acceptable whole-file replacement.

#### PF-R2 — R3d must coexist with the established `EvidenceGraph` path under a new, explicit name

Private `c01` has public application
`evaluation_run_bundle_evidence(bundle, row_capture_digest=...) -> EvidenceGraph`.
Candidate code changes that same importable name to return
`CapturedReceiptEvidenceV0` and candidate `T07` asserts the module contains no
`EvidenceGraph`. Those types, consumers, and availability guarantees cannot
coexist behind one function name.

**Required amendment:** lock two distinct stable names and fixed return types:

```python
evaluation_run_bundle_evidence(...) -> EvidenceGraph
build_captured_receipt_evidence_v0(...) -> CapturedReceiptEvidenceV0
```

The former is the established private graph/playback contract and remains
unchanged. The latter is the new strict R3d builder in a dedicated receipt
runtime module, with a protocol export only if the reconciled private source
actually exposes it. They must not be aliases, overloads, or an input-dependent
type switch. The R3d builder must use a fresh canonical decode/snapshot and
fail closed on malformed, stale, foreign, zero-row, or ambiguous material. It
must not import/build `EvidenceGraph`, `Explanation`, Policy
conclusion/lineage, or a replay/verification result. Tests must prove both
directions: existing Scenario/captured-run graph playback remains available;
the strict DTO is rejected by graph/render/Explanation consumers.

The same amendment must explicitly **defer** candidate R3e/F4C-a/F4C-b1 paths
(`S4`, coordinate overlay, manifest, and their tests) from this Q20/Q21 release
reconcile. Their internal labels do not make them a completed EvidenceGraph,
Explanation, proof-parity, replay, Policy conclusion, Product, Meander, Agent,
MCP, or SDK capability. A later private-seam blueprint can decide whether they
ever belong in a projection.

#### PF-R3 — projection must become a dual-input composition, with public-owned CI/package files frozen at `b92` until an explicit patch

The sync runbook makes `.github/`, `pyproject.toml`, `CHANGELOG.md`, root
documents, and module docs public-owned/`merge=ours` surface files. The current
allowlist/script instead copies private versions of many of them. Private and
public package metadata already disagree (`0.2.0rc1` versus public `0.2.0`),
and private root content includes internal workflow references. A direct private
staging tree therefore cannot establish the public package or release surface.

**Required amendment:** define a two-input staged-public-tree procedure:

1. Copy from the reconciled private feature source only an explicit kernel-code
   and curated-test manifest.
2. Copy public-owned root/CI/package/changelog/docs from `b92` unchanged, then
   apply only an explicitly reviewed public `features/...` surface patch.
3. Build/tests/wheel inspection run against that composed tree, and record the
   private source ref, public-base ref, public-patch ref, and both manifests.

The approved ownership mechanism is the latter: a future public feature branch
starts from `b92` and receives a deliberately enumerated patch for
`.github/workflows/factgraph-tests.yml` and, only if needed for the test
environment, `pyproject.toml`. `CHANGELOG.md` remains unchanged until a later
unique-version/release proposal. Candidate CI is review input only. A future
public patch may add `pytest` to public `dev` dependencies and add an explicit
PR Q20-core/R3d cohort, but must not copy private `0.2.0rc1`, allocate/reuse a
release version, or make `build` a runtime dependency merely to run a gate.

`src/factgraph/application/__init__.py`,
`src/factgraph/application/protocol/__init__.py`, and `src/factgraph/sdk/__init__.py`
are additionally public façades. A public candidate must construct each from
the b92 public set plus an exact approved public-export allowlist; it must
never copy or merge the private c01 façade wholesale. The amendment must
enumerate every new positive export and every required negative export
(especially no R3e/F4C or SDK receipt-builder exposure), then require exact
`__all__` assertions, import-closure checks, and installed-wheel positive and
forbidden-export import tests.

#### PF-R4 — default-deny module-doc policy and allowlist closure need an executable, whole-tree gate

The candidate dirty docs are not the only broken case: the private allowlist
currently contains module docs, and the projection diagnostic already fails on
an existing private `sdk/docs/README.md` link to excluded `examples/`. The
script's current bad-link grep also omits root `CONTRIBUTING.md` and
`CHANGELOG.md`, creating a blind spot for public-surface leakage.

**Required amendment:** make the private projection manifest exclude all
`src/factgraph/**/docs/**` and `src/factgraph/**/*.md` entries, along with all
public-owned root/CI/package files. Existing public `b92` docs remain frozen in
the composed public tree; they are neither removed nor silently rewritten. A
future curated-doc slice is the only route for changing them or adding examples.
The composition gate must scan **all** staged public Markdown (including root
surface docs) for forbidden private/excluded references, with any historical
exception explicitly reviewed and tested rather than hidden by a broad ignore.
It must also verify: exact manifest equality, denylist absence, static
FactGraph import/export closure, and a clean installed-wheel import that cannot
fall back to the source checkout.

There is an inherited b92 link-clean contradiction that must be decided
explicitly: `docs/quickstart/rules.md:455` links to the excluded and
nonexistent `examples/rule_structure_demo.ipynb`. Therefore “b92 docs frozen”
and “the whole composed tree is link-clean” cannot both be claimed today. The
amendment must select one of these honest paths:

1. **Recommended:** a separately reviewed public-owned curated-doc patch fixes
   that link before any projection candidate claims a link-clean public tree.
2. **Temporary inherited-baseline record:** record that exact line as `BL-1`,
   fail on every new/existing unapproved forbidden link, and state that the
   public tree is *not* link-clean and cannot be reported as a final release
   candidate until a later curated-doc patch clears `BL-1`.

No broad pattern exception, silent rewrite, or scan exclusion is permitted.

#### PF-R5 — projection staging cleanup needs a fail-closed filesystem boundary and an explicit hard deny set

`project_release_surface.sh` currently accepts a caller-selected `STAGING`
path and executes `rm -rf "$STAGING" "$MANIFEST"`. Its narrow rejection only
protects the monorepo path and `/`; it does not prove that a sibling directory,
`/tmp`, a home-derived path, or another pre-existing temporary directory is a
tool-created projection. The allowlist/denylist also lacks explicit
`workflow/**`, `examples/**`, and `tutorials/**` hard rejects. A mistaken future
allowlist entry could therefore turn a default-deny policy into a source leak.

**Required amendment:** scope a safe composition/projection helper contract
before implementation. It must create staging with `mktemp`, write and verify a
unique marker before any cleanup, resolve every cleanup target with `realpath`,
and accept deletion only inside a dedicated, tool-owned scratch root. It must
reject `/`, `/tmp`, the monorepo, home-derived paths, parents/siblings of the
created staging directory, symlink escapes, and every path without the marker.
The manifest path receives the same containment checks. Allowlist entries must
be normalized regular relative paths only: no absolute path, `..`, glob,
newline, or symlink escape is permitted. The hard deny gate must fail even when
allowlisted for `workflow/**`, `examples/**`, `tutorials/**`, `scripts/**`,
`tests/examples/**`, HNSM-only packages, internal tooling, audit/memory,
generated output, and every existing private-path class. Focused tests must use
sentinels/mocks to prove rejection of broad, sibling, home-derived, and
symlinked targets as well as accidental allowlist leakage. No destructive
cleanup is performed by this preflight.

### 3.2 Recommended amendment before scoped

#### PF-Rec1 — split the candidate CI cohort by actual availability

The candidate workflow puts Q20/Q21, R3d, R3e coordinates, and F4C manifest
tests in one named cohort. After PF-R2, that label would overclaim what this
slice carries. The public-owned CI patch should name only the approved
Q20-core/R3d test list. R3e/F4C tests stay private/deferred; mypy and coverage
remain advisory until their configuration changes. Its Ruff invocation must
cover every changed approved Q20/R3d source path **and every selected runtime,
protocol, SDK, and core test file**; the candidate's current Ruff list does not
cover all `tests/application/**` runtime tests.

#### PF-Rec2 — make wheel evidence a separate local gate, not a release-script dry-run

`scripts/release.sh` defaults to `master`, targets `origin`, creates
milestone/release refs and tags, and only runs the legacy 11-module unittest
set. Even `--dry-run` changes local refs before cleanup. It must not be used as
the preflight or local wheel verifier. The scoped blueprint should instead
specify a non-publishing composed-tree wheel build, fresh venv install without
the source tree on `PYTHONPATH`, a clean working directory, public API smoke,
and a site-packages-origin assertion. Build **wheel only** (no sdist), inspect
its file inventory, and record its SHA-256 plus projection-manifest/source and
dependency coordinates.

### 3.3 Verified assumptions

#### PF-V1 — source direction and no-history-transplant constraint are correct

Private HNSM is the development source of truth, `b92` is the public review
base, and `6d` is comparison input. The missing ancestor relationship and the
39 divergent private paths confirm that direct candidate cherry-picking would
be both technically unsound and governance-inverted.

#### PF-V2 — candidate R3d labels are appropriately narrower than a truth/proof claim

The candidate receipt DTO uses `integrity="digest_sealed_not_authenticated"`,
`authenticity="unverified"`, `logical_verification="not_performed"`,
`replay_verification="not_performed"`, and `proof_parity="not_claimed"`.
Those labels are compatible with the required availability vocabulary only if
PF-R2 keeps them separate from the existing graph path. They do not mean false,
source/admission/governance truth, replay, proof parity, or Policy conclusion.

#### PF-V3 — public CI and package metadata are surface-owned, not private projection inputs

The sync runbook explicitly says public CI/package/changelog files are kept by
the public repository. Candidate changes demonstrate a feasible explicit patch:
add a PR trigger and a focused pytest cohort; add pytest as a dev dependency if
the public workflow installs `.[dev]`. No remote CI has run on this candidate,
and neither mypy nor coverage is a hard gate while configured
`continue-on-error`.

### 3.4 Scoped-detail items

#### PF-S1 — exact public wheel smoke program and manifest schema

During implementation, define the exact clean-environment commands, package
content allowlist, source-shadow rejection check, and records for Python and
dependency coordinates. This must happen before a projection candidate is
reported, but it does not require choosing a version or invoking a release
script now.

#### PF-S2 — unique version/changelog/public PR proposal

After local composed-tree evidence exists, propose one unused public version,
public changelog text, and a public `features/...` branch. This is deliberately
after private source reconciliation and requires its own authorization; it is
not a preflight implementation decision.

### 3.5 Abandonment blockers

None. The route is viable after PF-R1 through PF-R5, but it cannot be scoped
without them.

## 4. Cross-slice contract preservation

- Private canonical behavior remains authoritative. Function endpoints, field
  navigation, Policy comparisons/weighted choices, Scenario/expectation flows,
  and existing Product-facing behavior must be preserved unless a separately
  scoped compatibility decision changes them.
- Run anchors remain identity/freshness pins, not snapshots or replay records.
  Bundle verification remains an isolated technical check, not replay. A
  digest validates the stated seal relationship, not authenticity, source,
  admission, governance, authorization, or business truth.
- `not_available`, `not_captured`, and `not_claimed` are availability labels,
  not logical falsehood. `unverified` is not a source/admission/governance or
  business-truth conclusion.
- R3d receipt inventory stays strictly separate from `EvidenceGraph`,
  `Explanation`, Policy conclusion/attribution, logical proof, proof parity,
  verification, replay, Product Explain, and any Meander/Agent/MCP wire shape.
- R3e/F4C material stays unavailable/deferred in this release reconcile. It
  may not enter a public export, wheel smoke, public CI cohort, or capability
  statement by adjacency to Q20/Q21.
- Public source is a default-deny composition. Private module docs/examples,
  workflow/audit material, HNSM-only packages/tools, and user worktrees remain
  absent. Existing b92 public docs stay frozen unless a later curated-doc
  slice explicitly changes them.
- A public façade is b92 plus its named approved export delta, never an opaque
  copy of a private `application`, `protocol`, or SDK initializer. Installed
  wheel tests must prove both intended imports and prohibited exports.
- No public push, PR, merge, tag, release, upload, or Meander dependency is
  authorized by this preflight.

## 5. Findings summary table

| Bucket | Count | Items |
| --- | ---: | --- |
| Required | 5 | PF-R1 private divergence; PF-R2 R3d coexistence/R3e defer; PF-R3 dual-input public-owned composition; PF-R4 default-deny docs/allowlist/full Markdown gate; PF-R5 staging path safety/hard deny |
| Recommended | 2 | PF-Rec1 cohort split; PF-Rec2 independent wheel gate |
| Verified | 3 | PF-V1 source direction; PF-V2 availability vocabulary; PF-V3 CI/package ownership |
| Scoped-detail | 2 | PF-S1 wheel manifest/smoke; PF-S2 version/changelog/public PR proposal |
| Abandonment | 0 | — |

## 6. Recommended Step 4.4 amendment actions

The blueprint branch, not this independent preflight branch, must make all of
the following decisions before it can move from `draft` to `scoped`:

1. **Correct the source model (§1, §4.1, §5.1, §6, §7).** Record the
   `6 A / 1 C / 4 B / 39 D` matrix outcome and turn the implementation rule
   into private-preserving behavioral delta extraction. Add an explicit
   preservation cohort for current private Function, navigation, Policy, and
   Scenario behavior.
2. **Lock R3d coexistence and R3e/F4C allocation (§5.2, §6, §7, §8).** Adopt
   the two distinct stable names and fixed return types in PF-R2; keep
   `evaluation_run_bundle_evidence(...)->EvidenceGraph` intact and add only
   `build_captured_receipt_evidence_v0(...)->CapturedReceiptEvidenceV0`.
   Aliasing, overloading, or input-dependent return types are forbidden.
   Declare all candidate coordinate overlay/manifest paths `deferred` for this
   slice, including their exports and tests. The scoped blueprint must list the
   exact no-graph/no-Explanation/no-Policy/no-replay negative tests.
3. **Replace one-input private staging with dual-input composition (§5.3,
   §5.4, §5.5, §7, §8).** HNSM contributes only approved kernel/test paths.
   b92 contributes public-owned root/CI/package/changelog/docs; a later public
   `features/...` patch may alter only enumerated public-owned files. Record
   the four coordinates (private ref, private manifest, public base ref,
   public patch/manifest) in wheel evidence. Construct public application,
   protocol, and SDK façades from b92 plus an approved public-export allowlist
   only—never from a private façade merge—with exact `__all__`, import-closure,
   negative-export, and installed-wheel forbidden-import tests.
4. **Narrow the allowlist and strengthen the gate (§5.3, §7, §8).** Remove
   private module docs/Markdown and public-owned files from the private
   projection input manifest. Add a whole-composed-tree Markdown scan and
   exact import/export closure check. Retain existing b92 docs unchanged in
   the public branch; do not add candidate dirty docs/examples. Explicitly
   choose the recommended curated-doc repair for b92
   `docs/quickstart/rules.md:455`, or record `BL-1` and forbid a link-clean
   release-candidate claim until that separate patch lands.
5. **Make staging cleanup and deny behavior safe (§5.3, §7, §8).** Require
   `mktemp` issuance, marker verification, `realpath` containment, and a
   dedicated scratch root before any cleanup; reject broad/sibling/home-derived
   targets and symlink escapes. Require normalized regular relative allowlist
   paths, sentinel/mock rejection tests, and hard denial of
   workflow/examples/tutorials/scripts/example-tests/private packages/build or
   cache output even if an allowlist is accidentally broadened.
6. **Name the actual public test policy (§5.4, §7).** The only permitted public
   CI change at this stage is an explicit b92-based surface patch for the
   approved Q20-core/R3d cohort and, if required, public pytest dev setup.
   Coordinate/F4C tests remain out. Ruff must cover every selected source and
   test path; mypy/coverage must be reported as advisory.
7. **Keep package/release authority separate (§5.5, §7, §8).** Do not copy
   private version metadata or change `CHANGELOG.md` now. A unique public
   version, changelog, public PR, remote CI, tag, wheel upload, and Meander
   adoption each remain later, separately authorized gates. The local evidence
   gate builds wheel only, from the composed tree, and validates an installed
   wheel from a clean cwd with `PYTHONPATH` unset.

## 7. Acceptance for this preflight

- [x] Blueprint-referenced private/public/candidate sources and release files
  re-read at preflight-row drafting time.
- [x] All 50 tracked candidate paths classified in a three-way
  path/import/test matrix, plus six explicitly omitted dirty docs/example paths.
- [x] At least three sharp findings independently spot-checked: private/candidate
  R3d `EvidenceGraph` collision; c01 projection failure on excluded example
  link plus b92 inherited link at `docs/quickstart/rules.md:455`; sync-runbook
  public-surface ownership versus current allowlist/script.
- [x] Findings classified into all five buckets.
- [x] No abandonment blocker surfaced.
- [x] Cross-slice identity, freshness, availability, verification/replay,
  EvidenceGraph/R3d, default-deny, and public-release boundaries verified.
- [ ] Composed-wheel acceptance proves each approved façade import resolves
  from the installed wheel and each forbidden R3e/F4C/SDK receipt export fails
  to import; no private façade merge is used.
- [ ] Blueprint amendments PF-R1 through PF-R5 applied and independently
  reviewed on the blueprint branch.
- [ ] Separate explicit authorization received before `draft → scoped`.

Lifecycle: this preflight remains in `workflow/audit/active/` until the
consuming blueprint archives at Step 4.9.
