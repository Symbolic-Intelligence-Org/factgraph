# Task Blueprint: FactGraph Q20/Q21 canonical release reconciliation

- Status: scoped
- Created: 2026-08-16
- Last Updated: 2026-08-16
- Authority: private-only scoped task blueprint. Under the user's 2026-08-16
  autonomous, feature-branch-only authorization, this scope permits only a
  separate private `features/...-source-reconcile-...` branch and §8.3–4's
  private runtime/protocol/core/SDK/test/docstring reconciliation. It does not
  authorize public projection/composition, façade/export selection, CI/package/
  changelog/docs patches, wheel building, a public-release status claim beyond
  this private scope, public push/PR, merge, tag, artifact publication, or Meander
  consumption.
- Inputs:
  - [Q20/Q21 release-surface audit](../../audit/active/2026-08-16_factgraph-q20q21-release-surface-vs-shipped.md), recorded at private audit commit
    `2458e79a55062be862fb2aec0ea447ac6614b03e`.
  - [Independent reconciliation preflight](../../audit/active/2026-08-16_factgraph-q20q21-canonical-release-reconciliation-preflight.md),
    recorded at `ad96da6d`. Its required findings are incorporated below; it
    does not itself authorize implementation or a release action.
  - Private HNSM canonical baseline
    `c01dccae5c524d667dd4414201be3961312076df`.
  - Public FactGraph baseline
    `b92d6bf5405be8d15eedea5b97aa7408914e76b9` and independently developed
    candidate `6d7628cd2019b1d2cdd243546c7502684500fd95`.
  - [Release-surface governance](../../foundations/architecture_principles.md#22-release-surface-governance) and the
    [FactGraph sync runbook](../../factgraph_sync.md).
  - [Q6A Run-anchor decision](../../design/decisions/active/2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md),
    [Q6B bundle-capture decision](../../design/decisions/active/2026-08-12_q6b-evaluation-run-bundle-capture-decision.md), and
    [F4 completion blueprint](./2026-08-12_factgraph-f4-completion.md). These
    are boundary rationale, not evidence that the independent candidate is
    already canonical or releasable.
- Related Modules:
  - `src/factgraph/application/**`, including protocol/runtime seams for
    managed Query, captured run bundles, isolated verification, and receipt
    inventory.
  - `src/factgraph/core/rules/where_eval.py`,
    `src/factgraph/core/store/{_evaluate.py,runtime.py}`,
    `src/factgraph/sdk/store.py`, and their direct tests only where the
    reconciled contract requires them.
  - `scripts/project_release_surface.sh`,
    `scripts/release_surface_allowlist.txt`, public CI workflow(s), package
    metadata, and release-candidate validation tooling.
- Related Docs:
  - [Release Surface Cleanup](./2026-04-28_release-surface-cleanup.md)
  - [Blueprint workflow](../README.md)
  - [Architecture principles](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-08-16_factgraph-q20q21-canonical-release-reconciliation.audit.md](./2026-08-16_factgraph-q20q21-canonical-release-reconciliation.audit.md)

> **Release-state guard:** all statements about `6d7628cd` below describe an
> independently tested candidate, not a released FactGraph capability. The
> candidate's separate public worktree also has uncommitted module-doc changes
> and an untracked example/test; neither is an input to this draft's source
> scope or a public-release asset.

## 1. Problem

Q20/Q21 implementation work exists in a separate public FactGraph clone, while
the private HNSM monorepo is the development source of truth. The candidate is
three commits above the public baseline, but its history does not form a direct
transfer chain from the private canonical baseline. Treating it as canonical,
or cherry-picking it wholesale, would reverse the required private-source →
sanitized-projection direction.

The candidate also crosses several high-risk seams at once: managed Policy and
semantic-port Query compilation, `EvaluateResult` attachment, bounded
captured-run records, isolated verification, selected-receipt inventory,
coordinate/overlay helpers, core evaluator bridging, SDK binding, and public
test/CI metadata. The private release allowlist does not currently establish
that whole import closure. Its projection checker rejects documentation that
links to excluded `examples/`, while the candidate's uncommitted documentation
does exactly that.

Meander needs an immutable, installed FactGraph artifact before it can execute
a real vertical. A locally passing public-clone candidate, a digest-sealed DTO,
or an identity anchor is not that artifact. This blueprint therefore defines a
narrow route to reconcile the required code into a private canonical branch,
produce a default-deny projection candidate, and collect release evidence
without pretending that any publication or Meander integration has occurred.

## 2. Goals

1. Reconcile the reviewed Q20/Q21 behavior through a three-way comparison of
   private `c01dccae`, public `b92d6bf5`, and candidate `6d7628cd`, with the
   private feature branch becoming the only development source for any carried
   behavior. This is private-preserving behavioral delta extraction, not a
   candidate import: existing Function, navigation, Policy, Scenario, and
   Product-facing behavior remain explicit preservation obligations.
2. Build a file-by-file source-reconciliation matrix that identifies required
   runtime/protocol/test changes, their import/export closure, their intended
   private owner, their public projection class, and their proof obligation.
3. Preserve two fixed, non-overloaded contracts: existing
   `evaluation_run_bundle_evidence(...)->EvidenceGraph` playback remains
   available to its current private consumers, while an additive, uniquely
   named R3d builder can return only a sealed
   `CapturedReceiptEvidenceV0` capture-only DTO. Neither name, output, or
   import path may stand in for the other.
4. Keep current Q20/Q21 module docs, runnable examples, and example tests
   default-denied from the public projection unless a later, explicit
   documentation slice scopes a curated, link-clean public corpus.
5. Make the sanitized projection verifiable: a safe dual-input composition
   helper, exact kernel/test manifest, b92 public-owned surface plus an
   explicit approved public patch, hard deny/link/import-export closure,
   Q20-core/R3d-only public test cohort, wheel build from the projection, and
   a clean installed-wheel smoke test.
6. Define honest version, public feature-PR, remote-CI, tag, and publish gates
   so that a local projection candidate is never described as a release.

## 3. Non-goals

- No direct cherry-pick, merge, or history transplant from the public candidate
  into private canonical history.
- No public push, PR creation, merge to `main`, tag, GitHub release, package
  upload, or artifact publication. Each remains a separately authorized action.
- No Meander server adapter, HTTP endpoint, Agent transport, MCP surface, UI
  work, SDK wire adapter, or consumer import of the candidate runtime.
- No new Product, Meander, Agent, MCP, or remote SDK public DTO inferred from
  application-protocol imports.
- No attempt to make R3c verification into replay, or R3d receipt capture into
  `EvidenceGraph`, `Explanation`, logical proof, Policy conclusion, source
  admission, governance, or authorization.
- No claim that R3e coordinate material or F4C projection is a completed public
  capability. This slice may preserve only its actually reviewed, explicitly
  classified implementation boundary; it may not enlarge it or advertise it.
- No public Q20/Q21 module documentation, notebook/script example, or example
  test add-back; no mutation of the candidate worktree's existing dirty docs
  and examples.
- No mutation of the user's primary HNSM worktree or the separate Product
  Explanation worktree.

## 4. Current Context

### 4.1 Three independent source coordinates

| Coordinate | Role in this task | What it does **not** establish |
| --- | --- | --- |
| Private `c01dccae` | Development-source baseline from which a new private feature branch must be derived. It already has a richer, divergent implementation across most candidate paths. | That every candidate delta is compatible, or that the private façade is a public release façade. |
| Public `b92d6bf5` | Existing public `main` baseline against which any future public feature branch is reviewed. | A base for private development or proof that every private path is publishable. |
| Candidate `6d7628cd` | Independently developed comparison input: 50 tracked code/test/CI/package paths differ from `b92d6bf5`. | Canonical history, a release tag, an artifact, a clean public worktree, or a permission to publish. |

`b92d6bf5` is not an ancestor of private `c01dccae`. The preflight matrix has
50 tracked candidate rows: six are private-absent, one is candidate-identical,
four equal public `b92`, and thirty-nine are divergent private counterparts.
The implementation phase must therefore reconstruct and verify a behavioral
delta on the private branch rather than assume that a commit-level transplant
is meaningful. The matrix required by §5.1 is the auditable bridge between
these unrelated coordinates.

### 4.2 Dual-input public surface and inherited documentation baseline

The architecture principle requires a private-source, default-deny projection.
The sync runbook keeps `src/factgraph/**/docs/**` and
`src/factgraph/**/*.md` on the private surface and defines root package/CI/
changelog files as public-owned. The current projection allowlist contradicts
that ownership and already fails on an existing private module-doc link to an
excluded `examples/` path. The candidate's uncommitted module docs exhibit the
same invalid hybrid shape.

The runbook's operational use of public `factgraph/main` as the release-surface
base and the architecture principle's private development-source authority are
different roles, not permission to reverse source direction. Preflight must
confirm the exact public-branch mechanics against both documents; it must not
turn the public baseline or candidate into the private development source.

This draft chooses the conservative Q20/Q21 treatment: the private source
contributes only explicit kernel-code and curated-test paths; a composed public
tree inherits root/CI/package/changelog/docs from `b92d6bf5`, then receives at
most an approved, enumerated public `features/...` patch. No private module
docs, runnable examples, or example tests are carried. Existing public-baseline
documentation is not silently rewritten or removed by this slice.

There is an inherited public-doc contradiction that prevents a blanket
"link-clean" claim: `b92d6bf5`'s `docs/quickstart/rules.md:455` links to
excluded/nonexistent `examples/rule_structure_demo.ipynb`. Before a composed
tree is called link-clean or release-candidate-ready, a separately reviewed
public-owned curated-doc patch must repair it. A temporary baseline record may
retain it only as `BL-1`, while explicitly prohibiting a link-clean or final
release-candidate claim. Broad ignores are forbidden.

### 4.3 Availability vocabulary that must remain intact

The following is a boundary inventory for reconciliation planning, not a
release declaration:

| Surface | Required interpretation in this slice | Forbidden inference |
| --- | --- | --- |
| R3a-style Run identity | An identity/freshness pin is not a captured snapshot and cannot recreate a historical execution. | Replay, Store-independent Explain, authenticity, or source truth. |
| R3c bundle verification | An isolated consistency check over captured input may be a technical verification result. | Replay of the source run, source-run identity recreation, source/admission/governance truth, or proof parity. |
| R3d `CapturedReceiptEvidenceV0` | A strict, sealed selected-native-branch receipt inventory with explicit `not_performed` / `not_claimed` labels. | `EvidenceGraph`, `Explanation`, Policy attribution/conclusion, logical proof, verification, replay, or Product explain. |
| R3e coordinates / F4C-related helpers | Candidate-only material to be separately classified if carried; no new public capability is scoped here. | That a coordinate digest, overlay, or private helper proves EvidenceGraph availability, Policy conclusion, or a finished F4C surface. |
| `not_available` / `not_captured` | Capability absence or lack of captured material in the named contract. | Falsehood, a negative logical verdict, or an authorization decision. |
| `unverified` | Absence of the stated verification/authentication claim. | A statement about source, admission, governance, or business truth. |

Every reconciliation docstring, module document, test name, and public-facing
claim that touches these values must retain this vocabulary. A digest validates
the stated seal relationship; it is not an authenticity, authority, admission,
governance, or business-truth credential.

### 4.4 Known release blockers

- Q20/Q21 source must first exist and pass review on a private canonical
  feature branch.
- The default-deny composition helper needs a safe `mktemp`/marker/realpath
  cleanup boundary, normalized allowlist validation, a hard-deny path set, and
  an import/export closure review; adding a broad directory pattern or caller-
  supplied cleanup path is not an acceptable shortcut.
- The existing `EvidenceGraph` playback entry and strict R3d receipt builder
  have a same-name/return-type collision that must be resolved additively.
- Public application, protocol, and SDK façades must be rebuilt from b92 plus
  an approved export allowlist, not copied from the richer private façade.
- The inherited `BL-1` public-doc link must be repaired or openly retained as
  a non-link-clean baseline before a final projection candidate is claimed.
- The existing public CI Q20/Q21 cohort is useful candidate evidence but does
  not validate a private-source projection, an installed wheel, a public PR,
  or remote CI.
- No unique release version, changelog entry, sanitized wheel digest, tag, or
  published artifact exists for this candidate.
- Meander's dependency inventory must continue to report FactGraph execution
  unavailable until a separately authorized release artifact is installed and
  verified.

## 5. Proposed Shape

### 5.1 Three-way private-source reconciliation

The implementation branch starts at private `c01dccae`, not at public
`b92d6bf5` and not at candidate `6d7628cd`. It extracts individually reviewed
behavioral deltas without replacing a divergent private file wholesale. Before
code is ported, create a reconciliation matrix with one row per candidate path
(including changed, added, and intentionally omitted paths). Each row must
record:

1. the path and behavior at private `c01dccae`;
2. the path and behavior at public `b92d6bf5`;
3. the candidate delta at `6d7628cd`;
4. whether it is required private runtime/protocol code, required private test,
   public-projection candidate, private-only support, deferred private seam,
   or rejected;
5. direct imports, exports, dynamic registrations, and test entrypoints needed
   for closure; and
6. the exact acceptance test(s) and invariant(s) that justify carrying it.

The expected categories include, but are not pre-approved merely by name:

- application protocol/runtime for semantic ports, managed Policy, compiled
  Query, Run anchors/bundles, isolated verification, receipt evidence, and any
  coordinate overlay/manifest;
- narrowly necessary core evaluator/Where and SDK bridge changes;
- application, protocol, SDK, and core regression tests;
- public CI and package metadata; and
- private module documentation/example material, which this draft excludes
  from the public projection.

The matrix must reveal shape conflicts rather than overwrite them. Private code
may be reimplemented from the reviewed behavioral contract, but not copied as a
blind commit transplant. Every carried row runs its Q20-core proof alongside
the affected private Function, navigation, Policy (including compare/weighted
choice), Scenario, expectation, and Product preservation cohort. Candidate
R3e/F4C coordinate, overlay, and manifest rows are explicitly deferred from
this slice. A candidate-only helper that cannot be justified by a private owner,
import closure, and focused acceptance proof is excluded or opened as a
separate scope amendment.

### 5.2 Fixed R3d receipt boundary and existing graph-playback seam

The two paths use stable, fixed names and return types. Existing private
`evaluation_run_bundle_evidence(bundle, *, row_capture_digest) -> EvidenceGraph`
remains unchanged for its existing captured-run and Scenario consumers. A new,
additive builder is fixed as
`build_captured_receipt_evidence_v0(bundle, *, row_capture_digest) ->
CapturedReceiptEvidenceV0`, lives in a dedicated receipt runtime module if and
only if the reconciled source genuinely supports it. Aliasing, replacing the
old name, or choosing output type from input is forbidden.

The new strict DTO path is limited as follows:

- `CapturedReceiptConditionV0`, `CapturedReceiptBranchV0`, and
  `CapturedReceiptEvidenceV0` remain immutable, nested-sealed data shapes.
- The application builder selects one receipt-backed captured row only after
  full bundle validation and a fresh canonical decode; malformed, absent,
  ambiguous, stale, foreign, or zero-row selection fails closed.
- The DTO and its local validation do not read or write Store, ledger, cache,
  sidecar, registry, or evaluator. A runtime builder's snapshot discipline must
  be tested separately from DTO construction.
- R3d carries no values/source metadata/certainty payload, generic graph,
  verdict, Rule/Policy occurrence attribution, or authorization result. Its
  fixed availability labels remain explicit.
- The R3d module does not import or construct an `EvidenceGraph`,
  `Explanation`, Policy conclusion/lineage, replay result, or verification
  result. Its DTO is rejected by generic graph, renderer, codec, and
  Explanation consumers. It is not exported by the SDK/Product/Meander/Agent/
  MCP surface.
- Existing graph playback, `explain_captured_evaluation_query_run_v0`,
  `explain_scenario_run_v0`, and their current private regressions remain
  available and must pass. They are not R3d behavior merely because they read
  related captured data.

R3c remains separate: verification may execute at most the declared isolated
captured-input check and returns its own record. It does not replay the original
run. R3e/F4C coordinate, overlay, and manifest paths are deferred rather than
retained in this slice: they may not enter `factgraph.application.__all__`, the
public wheel, SDK/Product/Meander/Agent/MCP claims, or the public CI cohort.

### 5.3 Sanitized projection and import closure

After private reconciliation is locally verified, derive a staging tree through
a dual-input default-deny composition. The private feature ref contributes only
a reviewed manifest of kernel-code and curated-test files. Public-owned
root/CI/package/changelog/docs come from `b92d6bf5` unchanged, then receive at
most one explicitly reviewed public `features/...` surface patch. The selected
ownership mechanism is the public-patch route; this blueprint does not amend
the runbook to project public-owned files from HNSM.

The public patch may modify only named public-owned files, initially
`.github/workflows/factgraph-tests.yml` and, only if required for that exact
workflow, public `pyproject.toml` dev test dependencies. It must not copy
private `0.2.0rc1`, allocate a release version, change `CHANGELOG.md`, or
rewrite public docs. The public application/protocol/SDK façade files are
special public-composition inputs: construct them from their b92 versions plus
an exact approved public-export allowlist. Never copy or merge a private façade
wholesale.

The projection evidence must include all of the following:

1. the composition helper creates its own staging and manifest under a dedicated
   scratch root with `mktemp`, marker verification, `realpath` containment, and
   no caller-controlled broad cleanup; sentinel/mock tests reject `/`, `/tmp`,
   home/repo/sibling/parent paths, symlink escapes, and unmarked directories;
2. every allowlist entry is a normalized ordinary relative path, and a hard-deny
   set rejects `workflow/`, `examples/`, `tutorials/`, `scripts/`,
   `tests/examples/`, private packages, audit/memory, tools, and build/cache
   output even if they are accidentally allowlisted;
3. the generated private and public manifests exactly match their reviewed
   inputs, every listed input blob resolves to the recorded private/public ref
   and expected object digest before it is copied, and final public diff paths
   equal the approved set;
4. the entire composed public Markdown corpus is scanned for excluded/private
   links. `BL-1` must be repaired by a curated-doc patch before link-clean is
   claimed; it may never be hidden by a broad ignore;
5. static import/export review finds no runtime dependency on a private path;
   exact `__all__` positive and forbidden-export tests cover all three façades;
6. installed-wheel smoke tests import the projected `factgraph` package rather
   than a source checkout or `PYTHONPATH` shadow, including positive imports of
   the three façades and forbidden imports of private Scenario/V1/V2/F4C paths;
   and
7. wheel contents contain only the declared public package/material and no
   private documentation, examples, workflow records, Meander code, or local
   build output.

No current Q20/Q21 module doc, runnable example, or example test is added to
the allowlist in this blueprint. Private module docs may be updated later as
implementation truth, but that does not make them public projection input.

### 5.4 CI, wheel, and release-candidate evidence

The private branch must execute the reconciled focused and preservation cohorts
before any projection. The projected source must independently run its public
test cohort. The selected b92-based public-workflow patch must name only the
approved Q20-core/R3d cohort—never deferred R3e/F4C overlay/manifest tests—and
run on a pull request to public `main`; a local workflow file does not establish
that remote CI has run. If its exact pytest invocation requires it, the same
public-owned patch adds pytest to the public dev test setup; it does not import
private package metadata.

Ruff must cover every changed approved Q20-core/R3d source path and every
selected runtime/protocol/SDK/core test path; Ruff and the selected tests are
hard gates. Mypy and coverage currently have advisory configuration in the
candidate workflow; neither may be described as a release blocker unless the
implementation changes configuration so that it actually blocks. Regardless of
advisory status, new/changed modules receive a scoped type check and its result
is recorded honestly.

Build only a wheel from the sanitized staging tree. In a new environment,
install that wheel without a source-tree import path, run a bounded Q20/R3d
smoke that exercises only actually exposed public API, inspect package contents,
and record the wheel filename, exact SHA-256 digest, private source ref,
private/public manifest digests, the ref-resolved input blob digests,
public-base and public-patch refs, interpreter/dependency coordinates, and test
results. Do not create or upload an sdist in this release line. `scripts/release.sh` is not this evidence: it
targets private `origin`/`master`, uses editable installation and a legacy test
set, and may create release-related refs even in a dry-run path.

### 5.5 Ordered version, PR, and publication gates

| Gate | Required evidence | Does not authorize |
| --- | --- | --- |
| Canonical reconcile | Private feature branch, path matrix, focused tests, and module docs/docstrings aligned to actual behavior. | Public projection or remote action. |
| Projection candidate | Exact allowlist/manifest, link/deny/import closure, staging-tree tests, and clean-wheel smoke/digest. | Version selection, public PR, tag, or publish. |
| Version/PR proposal | A new unused version, changelog proposal, public feature branch based on `b92d6bf5`, and explicit user authorization. | Push, PR creation, merge, tag, or upload. |
| Remote CI review | Authorized push/PR plus completed required remote checks on the exact public ref. | Merge, release tag, or artifact publication. |
| Release action | Explicit separate authorization after review of all prior evidence. | Any future version or automatic Meander adoption. |

Every branch in this slice uses the user-required `features/...` prefix: the
private blueprint, independent preflight, private implementation, and public
review branch all have distinct names. The public branch is assembled from
reviewed projection output against `b92d6bf5`; it is not a private branch push
and it is not a direct update of public `main`. A version is chosen only after
the projection is stable, is never reused from an existing tag, and is not
treated as allocated merely because it appears in a draft package file.

## 6. Boundaries And Invariants

- **Source direction:** private HNSM is the development source of truth;
  public FactGraph is a generated, default-deny projection. The candidate is
  comparison evidence only until private reconciliation closes.
- **Three-way discipline:** every carried candidate behavior has an auditable
  `c01dccae` / `b92d6bf5` / `6d7628cd` matrix row. No direct cherry-pick or
  history-preserving shortcut is permitted.
- **Freshness and snapshot honesty:** identity-only anchors remain identity
  pins; a digest is not a snapshot. Capture/codec validation must fail closed
  on malformed, stale, cross-spliced, unknown, or ambiguous inputs. A later
  Store state must never be silently substituted for captured input.
- **Availability honesty:** `not_available` and `not_captured` are neither
  false nor a negative business decision. `unverified` does not describe
  source quality, admission, governance, authorization, or business truth.
- **Verification/replay separation:** R3c verification is not replay and must
  not recreate a source Run or its identity. A verification record is not a
  live result, provenance record, or authorization outcome.
- **R3d/evidence separation:** `CapturedReceiptEvidenceV0` is not an
  `EvidenceGraph`, `Explanation`, Policy conclusion, logical proof, or proof
  parity result. The existing `evaluation_run_bundle_evidence` graph builder
  stays type-stable; an additive R3d builder stays graph-free. Private graph/
  playback work never becomes public by import, naming, or documentation
  adjacency.
- **R3e/F4C restraint:** coordinate, manifest, and overlay paths are deferred
  in this slice. They must not enter the public wheel, public façade exports,
  public CI cohort, or capability claims.
- **Projection restraint:** Q20/Q21 module docs/examples/example tests stay
  private in this slice. Public staging is dual-input; private code/tests and
  b92 public-owned surfaces never substitute for one another. The composition
  helper owns a marker-checked scratch directory, hard-denies private paths,
  and validates exact manifests. A passing source tree must also have a passing
  composed import/link/wheel closure. `BL-1` prevents a link-clean claim until
  a separate curated-doc repair lands.
- **Release restraint:** all commits remain on feature branches. No push,
  merge, tag, release, upload, or Meander runtime dependency occurs without
  the separately named user authorization in §5.5.

## 7. Acceptance

- [ ] A complete three-way reconciliation matrix covers every tracked path in
  `b92d6bf5..6d7628cd`, plus the explicitly omitted dirty docs/examples.
- [ ] Every carried behavior is implemented and reviewed on a private feature
  branch rooted at `c01dccae`; no public-candidate commit is cherry-picked.
- [ ] R3a/R3c/R3d terminology is tested and documented with the availability,
  freshness, seal, and fail-closed boundaries in §4.3 and §6.
- [ ] Existing `evaluation_run_bundle_evidence(...)->EvidenceGraph` playback,
  captured-run Explain, and Scenario Explain remain type-stable and passing;
  any R3d builder has a different fixed name/type and its DTO is rejected by
  generic graph/render/Explanation consumers.
- [ ] R3e/F4C coordinate, overlay, and manifest paths are absent from the
  public wheel, all public façade exports, public CI cohort, SDK/Product/
  Meander/Agent/MCP claims, and the Q20/R3d capability statement.
- [ ] Private module docs/docstrings are updated only after actual code
  behavior is established; the candidate's dirty docs/examples are neither
  staged nor projected by this slice.
- [ ] The reviewed dual-input composition creates only tool-owned marked
  scratch paths, passes normalized allowlist/hard-deny and sentinel path-safety
  tests, and produces exact private/public manifests, ref-resolved input blob
  digests, and public diff paths.
- [ ] Public CI/package metadata use the b92-based, enumerated public-owned
  surface patch. Public application/protocol/SDK façades are b92 plus exact
  approved exports, with installed-wheel import-closure and forbidden-export
  tests; no private façade is copied or merged.
- [ ] All composed public Markdown passes the forbidden-link scan. Until the
  inherited `BL-1` link is fixed in a separately reviewed curated-doc patch,
  no link-clean or final release-candidate claim is made.
- [ ] The private and projected Q20/Q21 test cohorts, applicable preservation
  tests, Ruff, scoped mypy, format/diff checks, and wheel smoke test pass with
  recorded commands/results.
- [ ] A sanitized wheel is built from the projection, installed in a clean
  environment, inspected, and recorded with source/manifest/wheel digests.
- [ ] Version, changelog, public branch, remote CI, tag, and publish evidence
  are reported in their correct gate row; none is claimed before it happens.
- [ ] No Meander adapter/HTTP/Agent/MCP/UI work, public release action, or
  mutation of protected dirty worktrees occurs.

## 8. Implementation Plan

This scoped private phase authorizes only steps 3–4 below. The public
projection/composition, public façade/export selection, CI/package/changelog/
docs patches, wheel/version/PR, and all remote or Meander actions in steps 5–7
remain separate future gates. No public façade export delta is approved in this
private scope.

1. **Draft review, then independent preflight:** after this draft review,
   create a distinct `features/...-preflight-...` branch. Reread the private
   baseline, public baseline, candidate diff, projection script, allowlist,
   package metadata, and public workflow in full. Produce the three-way
   path/import/test matrix and a required standalone preflight; no runtime file
   is changed before shape conflicts, public/private classes, and public-surface
   ownership are resolved.
2. **Blueprint amendment and scoped anchor:** the required preflight findings
   are now recorded: private-preserving delta extraction; fixed old-graph/
   new-R3d names and types; R3e/F4C deferral; b92-based façade overlay/public-
   owned patch; dual-input composition; hard-deny, marker-safe staging; and the
   `BL-1` documentation decision. Independent review and the user's private
   feature-branch authorization permit a separate private
   `features/...-source-reconcile-...` implementation branch only.
3. **Private canonical implementation:** reconstruct approved runtime,
   protocol, core/SDK bridge, and test changes on a private feature branch.
   Maintain explicit failure-closed behavior and keep R3c, R3d, R3e, and F4C
   claims separate.
4. **Private verification and documentation:** run focused and preservation
   suites, static checks, and adversarial boundary tests. Update private
   module docs/docstrings with actual availability; do not copy the candidate
   example/doc material into public scope.
5. **Projection reconciliation:** first implement and test the marker-safe,
   hard-deny composition helper. Update the private manifest only for approved
   kernel/test import closure. Compose b92 public-owned surfaces plus the exact
   public patch only after resolving every source blob from its recorded ref;
   construct the three public façades from b92 plus approved exports, generate
   both manifests, run deny/link/import/forbidden-export checks, execute
   projected Q20-core/R3d tests, and build/install/inspect the sanitized wheel.
6. **Release-candidate report:** record exact private ref, public-base ref,
   matrix result, projection manifest, wheel digest, local checks, outstanding
   advisory checks, and the proposed new version. Stop for explicit user
   authorization before any public push/PR.
7. **Authorized public review only:** if separately authorized, construct a
   `features/...` branch from `b92d6bf5`, populate it from the reviewed
   projection, push/open a PR, and record remote CI. Stop again before merge,
   tag, release, upload, or Meander adoption.

## 9. Docs To Update

During a later authorized implementation phase, update only the documents that
describe shipped private behavior or an explicitly approved public surface:

- private `src/factgraph/application/**/docs/` and protocol docs for actual
  Q20/Q21/R3d semantics and availability, after code/test closure;
- `scripts/release_surface_allowlist.txt`, projection tooling, public CI, and
  package metadata only for the reviewed public import closure;
- `CHANGELOG.md` only after a unique version is proposed at the appropriate
  gate;
- public documentation only in a separately scoped curated-doc slice; the
  current Q20/Q21 module docs/examples/example tests are deliberately absent
  here; and
- this blueprint and its paired audit as the lifecycle progresses.

No new `docs/README.md` entry is planned by this blueprint because it creates
no durable public documentation entry. If that changes, amend the blueprint
before implementation.

## 10. Outcome / Deviations

Not started. This section remains empty until an authorized implementation
phase completes private reconciliation, projection verification, and the
corresponding evidence review. A local branch, a candidate wheel, a public PR,
and a published release must be recorded as distinct outcomes if and when they
occur.
