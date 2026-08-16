# Task Blueprint: FactGraph Q20/Q21 canonical release reconciliation

- Status: draft
- Created: 2026-08-16
- Last Updated: 2026-08-16
- Authority: task blueprint. This draft constrains a possible private-source
  reconciliation and release-candidate preparation; it does not authorize code
  transfer, a status transition, a public push/PR, merge, tag, artifact
  publication, or Meander consumption.
- Inputs:
  - [Q20/Q21 release-surface audit](../../audit/active/2026-08-16_factgraph-q20q21-release-surface-vs-shipped.md), recorded at private audit commit
    `2458e79a55062be862fb2aec0ea447ac6614b03e`.
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
   behavior.
2. Build a file-by-file source-reconciliation matrix that identifies required
   runtime/protocol/test changes, their import/export closure, their intended
   private owner, their public projection class, and their proof obligation.
3. Preserve the strict R3d split: a sealed
   `CapturedReceiptEvidenceV0` is a capture-only application protocol DTO;
   generic `EvidenceGraph` construction/playback remains a private, separately
   classified seam and is not promoted by R3d.
4. Keep current Q20/Q21 module docs, runnable examples, and example tests
   default-denied from the public projection unless a later, explicit
   documentation slice scopes a curated, link-clean public corpus.
5. Make the sanitized projection verifiable: exact allowlist manifest, no
   excluded-path links, public-source import closure, Q20/Q21 test cohort,
   hard lint/test gates, wheel build from the projection, and a clean installed
   wheel smoke test.
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
| Private `c01dccae` | Development-source baseline from which a new private feature branch must be derived. | That it already contains the candidate's Q20/Q21 implementation. |
| Public `b92d6bf5` | Existing public `main` baseline against which any future public feature branch is reviewed. | A base for private development or proof that every private path is publishable. |
| Candidate `6d7628cd` | Independently developed comparison input: 50 tracked code/test/CI/package paths differ from `b92d6bf5`. | Canonical history, a release tag, an artifact, a clean public worktree, or a permission to publish. |

`b92d6bf5` is not an ancestor of private `c01dccae`. The implementation phase
must therefore reconstruct and verify behavior on the private branch rather
than assume that a commit-level transplant is meaningful. The matrix required
by §5.1 is the auditable bridge between these unrelated coordinates.

### 4.2 Default-deny documentation and source surface

The architecture principle requires a private-source, default-deny projection.
The sync runbook additionally keeps `src/factgraph/**/docs/**` and
`src/factgraph/**/*.md` on the private surface for future publishes. The
candidate's uncommitted module docs link to an excluded `examples/` path, and
the projection script correctly fails that hybrid shape.

The runbook's operational use of public `factgraph/main` as the release-surface
base and the architecture principle's private development-source authority are
different roles, not permission to reverse source direction. Preflight must
confirm the exact public-branch mechanics against both documents; it must not
turn the public baseline or candidate into the private development source.

This draft chooses the conservative Q20/Q21 treatment: do not carry those new
module docs, runnable examples, or example tests into the public projection.
Existing public-baseline documentation is not silently rewritten or removed by
this slice. If a future public documentation corpus is desired, it requires a
separate blueprint with its own allowlist, link/import/smoke checks, and public
reader contract.

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
- The default-deny allowlist needs an intentional file manifest and an import
  closure review; adding a broad directory pattern is not an acceptable
  shortcut.
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
`b92d6bf5` and not at candidate `6d7628cd`. Before code is ported, create a
reconciliation matrix with one row per candidate path (including changed,
added, and intentionally omitted paths). Each row must record:

1. the path and behavior at private `c01dccae`;
2. the path and behavior at public `b92d6bf5`;
3. the candidate delta at `6d7628cd`;
4. whether it is required private runtime/protocol code, required private test,
   public-projection candidate, private-only support, or rejected;
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
blind commit transplant. A candidate-only helper that cannot be justified by a
private owner, import closure, and focused acceptance proof is excluded or
opened as a separate scope amendment.

### 5.2 R3d strict DTO boundary and private playback seam

The public FactGraph source may expose the strict application-protocol DTO
shape only to the extent the reconciled source genuinely exports it:

- `CapturedReceiptConditionV0`, `CapturedReceiptBranchV0`, and
  `CapturedReceiptEvidenceV0` remain immutable, nested-sealed data shapes.
- The application builder selects one receipt-backed captured row only after
  full bundle validation and a fresh canonical decode; malformed, absent,
  ambiguous, or zero-row selection fails closed.
- The DTO and its local validation do not read or write Store, ledger, cache,
  sidecar, registry, or evaluator. A runtime builder's snapshot discipline must
  be tested separately from DTO construction.
- R3d carries no values/source metadata/certainty payload, generic graph,
  verdict, Rule/Policy occurrence attribution, or authorization result. Its
  fixed availability labels remain explicit.

An `EvidenceGraph` builder, detached playback adapter, or Policy overlay that
internally consumes this DTO is a private implementation seam unless and until
another blueprint establishes its public contract. It must not be exported as
the R3d API, smuggled through the SDK/Product/Meander/Agent/MCP surface, or
documented as proof parity. Tests must prove the boundary in both directions:
the R3d module does not construct a generic graph, and any private adapter is
not mistaken for a public receipt DTO.

R3c remains separate: verification may execute at most the declared isolated
captured-input check and returns its own record. It does not replay the original
run. R3e/F4C work is not broadened by this reconciliation; any retained
candidate code must state its exact, smaller availability rather than inherit
an EvidenceGraph/Explanation/Policy conclusion claim from a nearby name.

### 5.3 Sanitized projection and import closure

After private reconciliation is locally verified, derive a staging tree from
that private feature source using the default-deny projection mechanism. The
allowlist change must be a reviewed, explicit file list for public kernel code
and tests only. It must not add a broad `src/factgraph/**` or test glob solely
to make a missing import pass.

The sync runbook currently classifies `.github/`, `pyproject.toml`, and
`CHANGELOG.md` as public-repository-owned surface files rather than projection
inputs. Preflight must choose and record one of two mechanisms before this
blueprint can be scoped: either a separately approved runbook amendment makes
specific surface files reviewed projection inputs, or a public
`features/...` branch reconstructs an explicitly enumerated surface patch
against `b92d6bf5`. This draft selects neither mechanism. In either case, a
future public diff may touch only approved projected kernel/test paths plus the
enumerated public-owned surface files; it may not rewrite existing public docs.

The projection evidence must include all of the following:

1. the generated manifest exactly matches the reviewed allowlist;
2. denylist paths are absent, including workflow/audit material, HNSM-only
   packages, private tools, examples, samples, and generated outputs;
3. projected Markdown does not link to excluded paths, especially `examples/`;
4. static import/export review finds no runtime dependency on a private path;
5. installed-wheel smoke tests import the projected `factgraph` package rather
   than a source checkout or `PYTHONPATH` shadow; and
6. wheel contents contain only the declared public package/material and no
   private documentation, examples, workflow records, Meander code, or local
   build output.

No current Q20/Q21 module doc, runnable example, or example test is added to
the allowlist in this blueprint. Private module docs may be updated later as
implementation truth, but that does not make them public projection input.

### 5.4 CI, wheel, and release-candidate evidence

The private branch must execute the reconciled focused cohorts before any
projection. The projected source must independently run its public test
cohort. If the preflight chooses a public-workflow surface patch, that workflow
must name the Q20/Q21 cohort explicitly and run on a pull request to public
`main`; a local workflow file does not establish that remote CI has run. If it
does not choose that patch, this blueprint cannot claim that the existing
public workflow covers the reconciled capability.

Ruff and the selected tests are hard gates. Mypy and coverage currently have
advisory configuration in the candidate workflow; neither may be described as
a release blocker unless the implementation changes configuration so that it
actually blocks. Regardless of advisory status, new/changed modules receive a
scoped type check and its result is recorded honestly.

Build only a wheel from the sanitized staging tree. In a new environment,
install that wheel without a source-tree import path, run a bounded Q20/Q21
smoke that exercises only actually exposed public API, inspect package contents,
and record the wheel filename, exact SHA-256 digest, source ref, projection
manifest digest, interpreter/dependency coordinates, and test results. Do not
create or upload an sdist in this release line.

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
  parity result. Private graph/playback work never becomes public by import,
  naming, or documentation adjacency.
- **R3e/F4C restraint:** a coordinate, manifest, or overlay must declare only
  what its reviewed code actually supplies. It must not be marketed as an
  already-complete R3e/F4C, Explain, EvidenceGraph, or Policy capability.
- **Projection restraint:** Q20/Q21 module docs/examples/example tests stay
  private in this slice. Allowlist changes are explicit and minimal; a passing
  source tree must also have a passing import/link/wheel closure.
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
- [ ] R3d exports only its strict receipt DTO boundary; tests prevent generic
  `EvidenceGraph`/`Explanation`/Policy conclusions and unintended SDK/Product/
  Meander/Agent/MCP exposure.
- [ ] Any retained R3e/F4C-adjacent code has an explicit narrow availability
  statement and no stronger public capability claim.
- [ ] Private module docs/docstrings are updated only after actual code
  behavior is established; the candidate's dirty docs/examples are neither
  staged nor projected by this slice.
- [ ] The reviewed default-deny allowlist and projection manifest pass deny,
  link, and import/export closure checks.
- [ ] Preflight explicitly resolves whether public CI/package metadata are
  reviewed projection inputs or an enumerated public-owned surface patch; the
  public diff is limited to that recorded set plus approved kernel/test paths
  and does not rewrite existing public docs.
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

1. **Draft review, then independent preflight:** after this draft review,
   create a distinct `features/...-preflight-...` branch. Reread the private
   baseline, public baseline, candidate diff, projection script, allowlist,
   package metadata, and public workflow in full. Produce the three-way
   path/import/test matrix and a required standalone preflight; no runtime file
   is changed before shape conflicts, public/private classes, and public-surface
   ownership are resolved.
2. **Blueprint amendment and scoped anchor:** return to this blueprint branch
   to apply all required preflight findings, explicitly list the minimal public
   file set, the CI/package-metadata mechanism, and the R3d private-playback
   boundary. Self-check, then obtain the required `draft → scoped`
   authorization. Only after that authorization may a separate private
   `features/...-source-reconcile-...` implementation branch be created.
3. **Private canonical implementation:** reconstruct approved runtime,
   protocol, core/SDK bridge, and test changes on a private feature branch.
   Maintain explicit failure-closed behavior and keep R3c, R3d, R3e, and F4C
   claims separate.
4. **Private verification and documentation:** run focused and preservation
   suites, static checks, and adversarial boundary tests. Update private
   module docs/docstrings with actual availability; do not copy the candidate
   example/doc material into public scope.
5. **Projection reconciliation:** update the default-deny allowlist only for
   the approved kernel/test import closure. Apply public CI/package metadata
   only through the preflight-selected mechanism and exact public-owned surface
   list. Generate a staging manifest, run deny/link/import checks, execute
   projected tests, and build/install/inspect the sanitized wheel.
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
