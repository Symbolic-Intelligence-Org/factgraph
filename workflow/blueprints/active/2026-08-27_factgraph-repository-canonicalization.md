# Task Blueprint: FactGraph Repository Canonicalization

- Status: scoped
- Created: 2026-08-27
- Last Updated: 2026-08-27
- Related Modules:
  - Repository topology, Git remotes, branch tracking, and local workspace layout
  - `src/factgraph/`
  - `workflow/`
- Related Docs:
  - [FactGraph dual-repository workflow](./2026-05-14_factgraph-dual-repo-workflow.md)
  - [FactGraph synchronization notes](../../factgraph_sync.md)
  - [Workflow governance](../../AGENTS.md)
  - [Repository canonicalization preflight](../../audit/active/2026-08-27_factgraph-repository-canonicalization-preflight.md)
- Audit Log:
  - [2026-08-27_factgraph-repository-canonicalization.audit.md](./2026-08-27_factgraph-repository-canonicalization.audit.md)

## 1. Problem

The working directory is still named `hnsm-backend` and treats the legacy
`hnsm-backend` GitHub repository as `origin`, while the intended product and
release repository is `Symbolic-Intelligence-Org/factgraph`. This topology was a
rough mechanism for keeping shared workflow material alongside a FactGraph
superset; it was not intended to establish two durable product repositories.
FactGraph is consequently configured as a second remote and the existing
workflow describes a projected dual-repository release surface. This makes an
ordinary feature branch appear unsafe to push directly and has encouraged
creation of additional clean clones such as `factgraph-new`.

The decision to extract shared workflow into the independent
`symbolic-workflow` repository removes the only continuing reason for the local
product repository to point `origin` at `hnsm-backend`.

The repository also contains a mixed dirty worktree: current FactGraph product
changes, workflow-state changes, staged third-party removals, generated or local
configuration, and unrelated experimental directories. Repository identity must
therefore be canonicalized without treating "start again from a clean clone" as
the migration mechanism and without losing or silently publishing local work.

## 2. Goals

- Make `Symbolic-Intelligence-Org/factgraph` the sole canonical product and
  release repository.
- Make the normal local repository identity `factgraph`, with the FactGraph
  GitHub repository configured as `origin`.
- Allow ordinary non-sacred feature branches to track and push directly to the
  corresponding FactGraph remote branch; no projection branch or clean clone is
  required for publication.
- Preserve every current committed ref and every uncommitted or untracked item
  until it has been explicitly classified.
- Reconcile valuable local FactGraph changes with the current published
  FactGraph feature history and verify the result before changing repository
  identity.
- Establish a stable base from which shared workflow material can subsequently
  be extracted into the independent `symbolic-workflow` coordination repository.

## 3. Non-goals

- Migrating the workflow content or creating the `symbolic-workflow` repository
  in this slice.
- Moving `meander-ilp` into the Meander package in this slice.
- Moving, renaming, reconfiguring, or otherwise modifying the actively developed
  `meander` or `meander-ilp` repositories before the user declares the current
  Meander development task complete.
- Deleting `factgraph-new`, `factgraph_test`, legacy repositories, branches, or
  untracked directories before preservation and verification are complete.
- Force-pushing, rewriting published FactGraph history, or directly changing a
  sacred branch.
- Treating all current `workflow/` documents as FactGraph-local or as shared;
  that classification belongs to the subsequent workflow extraction slice.

## 4. Current Context

- Local repository root: `/Users/zhenzhili/hnsm-backend`.
- Current branch: `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`.
- Current committed HEAD: `c01dccae5c524d667dd4414201be3961312076df`.
- Current remotes:
  - `origin` -> `Symbolic-Intelligence-Org/hnsm-backend`
  - `factgraph` -> `Symbolic-Intelligence-Org/factgraph`
- Independently queried FactGraph remote refs on 2026-08-27:
  - `main` -> `b92d6bf5405be8d15eedea5b97aa7408914e76b9`
  - `features/meander-mvp-factgraph-sealed-evaluation-2026-08-23`
    -> `26a88c645dd388632b0d06405c636682d91cfff0`
- The published Meander MVP FactGraph feature ref is 20 commits ahead of the
  current local HEAD, with no commits unique to the local committed HEAD.
- The dirty tree contains four distinct classes that must not be conflated:
  FactGraph code/tests/docs, workflow history and shared coordination material,
  staged third-party removals, and local/untracked experiments or tooling.
- Existing dual-repository workflow material is historical input to this
  migration, not the desired steady-state topology.

## 5. Proposed Shape

The steady-state product topology is one repository identity:

```text
local factgraph repository
  origin -> github.com/Symbolic-Intelligence-Org/factgraph.git
  main   -> origin/main
  feature branches -> origin/<same branch>
```

The legacy `hnsm-backend` remote may remain temporarily under an explicitly
legacy name while migration evidence and otherwise-unreachable history are
checked. It is not a release surface, must not remain the default push target,
and has no steady-state role after shared workflow is extracted.

Repository canonicalization is performed in place from preserved history. A
temporary safety ref, patch archive, or isolated worktree may be used as a
recovery mechanism, but a newly cloned clean repository must not become the
normal place where changes are manually projected before pushing.

After the canonical Git identity is verified, the local directory will occupy
the stable FactGraph project slot in the agreed workspace layout. Directory
movement is a local filesystem operation and must not change Git history or
remote identity.

## 6. Boundaries And Invariants

- No tracked, untracked, staged, or unstaged user work is discarded.
- No existing branch or remote ref is force-moved as part of inventory.
- Remote names are changed only after current remote URLs and target refs have
  been recorded and independently verified.
- `origin` means the canonical repository after migration; it must not continue
  to mean the legacy superset.
- A normal feature push uses ordinary Git branch tracking. Dual-surface
  projection scripts are not part of the steady-state publication path.
- `main` remains protected from agent-initiated direct modification or push.
- Product-code reconciliation is verified by focused tests before old local
  clones or legacy publication paths are retired.
- Local-only absolute paths and agent-machine configuration do not become
  committed cross-machine project configuration.
- Workflow extraction begins only after this repository has one unambiguous
  product identity.
- The active `meander` and `meander-ilp` directories, Git state, dependencies,
  and local configuration remain untouched throughout this FactGraph slice.
- The current Meander C2 wheel remains immutable. Candidate-wheel compatibility
  testing and explicit dependency promotion are the future synchronization
  mechanism; they do not authorize a Meander write in this slice.
- Q22 product files are reconciled as an exact bounded set. Existing staged
  third-party removals, notebooks, Pixi configuration, machine-local settings,
  experiments, and unrelated workflow state are preserved but excluded.

## 7. Acceptance

- [ ] Every pre-migration committed ref and dirty-worktree class has a recorded
      preservation or disposition path.
- [ ] Valuable local FactGraph code, tests, and docs are reconciled on top of the
      selected current FactGraph lineage and pass focused verification.
- [ ] The canonical local repository is named and located as the FactGraph
      project, not as `hnsm-backend` or `factgraph-new`.
- [ ] `git remote get-url origin` resolves to
      `https://github.com/Symbolic-Intelligence-Org/factgraph.git`.
- [ ] A normal feature branch has an explicit FactGraph upstream and a dry-run or
      otherwise non-destructive check demonstrates that ordinary push targets the
      matching FactGraph branch.
- [ ] The legacy `hnsm-backend` remote is removed after migration verification;
      if temporarily retained during verification, it is clearly named as
      legacy and is never a default fetch/push authority.
- [ ] No clean-clone projection step is required by current repository guidance.
- [ ] Sacred branches and published remote history remain unchanged unless the
      user separately authorizes a release operation.
- [ ] The repository is ready for the subsequent shared workflow extraction
      blueprint.

## 8. Implementation Plan

1. Preserve the completed preflight manifest classifying the current staged,
   unstaged, and untracked tree into product changes, workflow material,
   dependency cleanup, and local-only artifacts.
2. Record recovery anchors for committed refs plus staged, unstaged, and
   untracked bytes before altering branch tracking or remotes.
3. Capture the exact Q22 product/evidence paths as a bounded change and compare
   them with the 20 published FactGraph commits after
   `c01dccae`; separate duplicate, compatible, conflicting, and still-new work.
4. Reconcile the retained product changes onto the selected current FactGraph
   feature lineage, then run focused tests and repository checks.
5. Rename Git remotes so FactGraph becomes `origin`; configure branch tracking
   and verify the direct-push target without pushing a sacred branch.
6. Move or rename the local directory into the stable FactGraph project slot and
   update only local path configuration that genuinely depends on it.
7. Mark the old dual-repository publication guidance as superseded input for the
   later workflow extraction; do not migrate shared workflow content in this
   slice.
8. Verify repository identity, remotes, branch/upstream relationships, dirty
   state preservation, focused tests, and the absence of a required clean-clone
   projection path.

## 9. Docs To Update

- `AGENTS.md` and/or `CLAUDE.md` only as needed to describe the canonical
  FactGraph repository entry after workflow extraction boundaries are known.
- `workflow/factgraph_sync.md` or its successor record, marking dual-repository
  projection as superseded rather than silently deleting its rationale.
- The later `symbolic-workflow` project descriptor for FactGraph.

## 10. Outcome / Deviations

To be completed after implementation.

- Final repository identity:
- Preserved and reconciled work:
- Legacy topology disposition:
- Verification performed:
- Deviations from this blueprint:
- Archive note:
