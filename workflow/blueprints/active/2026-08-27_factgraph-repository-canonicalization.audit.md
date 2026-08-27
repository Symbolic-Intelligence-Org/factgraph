# Task Blueprint Audit: FactGraph Repository Canonicalization

- Blueprint: [2026-08-27_factgraph-repository-canonicalization.md](./2026-08-27_factgraph-repository-canonicalization.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-27 | draft | Blueprint created | Recorded canonical FactGraph target topology and lossless-migration constraints before changing remotes, branches, or directories. |
| 2026-08-27 | preflight | Dirty-worktree preservation and lineage preflight completed | PF-R1 through PF-R5 require bounded Q22 replay onto `26a88c`, exact path scoping, workflow preservation, local-config exclusion, and no Meander artifact update. |
| 2026-08-27 | scoped | User authorized FactGraph-first execution and preflight findings were folded into the blueprint | Meander and `meander-ilp` remain protected; recovery material precedes branch, remote, or filesystem changes. |
| 2026-08-27 | preservation | Four-part recovery snapshot created and verified | Complete 526-ref Git bundle, staged binary patch, unstaged binary patch, and 119-file untracked archive stored under `/private/tmp/factgraph-canonicalization-20260827.tfykBb/`. |

## Decision Notes

### 2026-08-27: One canonical FactGraph repository

- `Symbolic-Intelligence-Org/factgraph` is the intended product and release
  authority.
- `hnsm-backend` previously acted as a rough superset so shared workflow could
  be maintained beside FactGraph; it is not a second durable product authority.
- Extracting shared workflow into `symbolic-workflow` removes the reason for the
  product repository's `origin` to point at `hnsm-backend`.
- The steady-state workflow uses ordinary branch tracking and direct feature
  pushes to FactGraph.
- A separate clean clone or projected release branch is not a required
  publication stage.
- The legacy remote is retained only for migration verification and removed
  once unique history and dirty work are safely accounted for.

### 2026-08-27: Preservation precedes identity changes

- The current dirty tree contains product work, workflow material, staged
  dependency removals, and local-only artifacts.
- Remote renaming, directory movement, clone deletion, and workflow extraction
  remain blocked until every class has an explicit preservation/disposition path.

### 2026-08-27: FactGraph-first migration order

- The user authorized proceeding with FactGraph repository canonicalization.
- `meander` is under active development; `meander` and `meander-ilp` remain
  unchanged until the user explicitly confirms that development task is done.
- This slice may inspect and modify only the current FactGraph repository and
  later FactGraph-local workspace placement required by its acceptance criteria.

### 2026-08-27: Candidate wheel and explicit promotion

- A wheel is the immutable FactGraph implementation payload consumed through
  Meander's adapter seam, not a separate source project.
- Future synchronized updates build a candidate wheel from one committed
  FactGraph revision, run Meander compatibility tests, and explicitly promote
  the verified artifact and dependency lock.
- The current Meander C2 wheel stays byte-identical during this FactGraph-only
  migration.

### 2026-08-27: Recovery snapshot

- `repository.bundle`: `sha256:5cd97aabd35ee1d7dc063227ec095db8e65fe4770eb37779a855be38086a6afd`
- `unstaged.patch`: `sha256:ab90825130baad32995ad7fb2356692fe1e5a175502660cdb8d37096016c8a9a`
- `staged.patch`: `sha256:a95a48e1fd7e7b3f95092c9b8b79b4e36d48166b952821c4beec692bb1dfb704`
- `untracked.tar.gz`: `sha256:f661353dc6c53048b303bfe967218082c1b92d589981a2807fc2ec9badebbca9`
- `git bundle verify` reports complete history; the untracked archive contains
  119 paths. The snapshot is temporary safety material, not a repository input.
