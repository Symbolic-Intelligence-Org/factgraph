# Releases and retained consumer compatibility

The public `0.3.0` release and the subsequent `0.2.0rc3` development artifacts
share history but were versioned on separate branches. `0.4.0rc1` consolidates
the current development runtime and public packaging. It was published as a
prerelease on 2026-09-08; a consumer's adoption is a separate transition.
See the [verified release history](release-history.md) for exact versions,
historical source branches and original distribution provenance.

## Preserve the shared baseline

Meander commit `07f782f` uses the exact rc3 wheel from producer `2a4f6b8f`, SHA-256
`2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`.
The original bytes are retained in a dedicated
[compatibility archive](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/archive%2Fmeander-main-07f782f).
The repository keeps the original manifest, `SHA256SUMS`, exact asset locations
and [retrieval instructions](../artifacts/compatibility/meander-main-07f782f/).
Download outside the source tree and verify against those repository checksum
pins before use. The current source tree contains no backup wheel; compatibility
metadata remains excluded from distributions. Consumers can retain that exact
artifact while new candidates are tested separately.

The archive is a historical storage record, marked prerelease and not latest.
Its tag points to the original producer and its manifest retains
`release_eligible=false`; relocation adds no package publication or consumer
promotion. Source history is preserved, including the original committed backup.

The read-only branch `release/0.4-baseline` points to that original producer
commit. It marks an existing ancestor of published `0.4.0rc1` and the maintained
0.4 line; it does not rename the wheel's `0.2.0rc3` package version or create a
separate development line. See the [0.4 source lineage](release-history.md#04-source-lineage)
for the verified relationship between source trees and runtime payloads.

A consumer may bind source, version, filename, whole-wheel and RECORD digests,
runtime ABI and compiled artifacts together. A package version bump by itself is
not a compatible pin update. Do not overwrite the old wheel, relabel its bytes,
or install a new wheel into a shared environment to experiment.

## Candidate verification

1. Build from a clean committed source with `scripts/release.sh` and the pinned
   `build` extra. It produces a wheel, sdist, manifest and checksum file in a new
   output directory without creating Git refs or publishing.
2. Build twice with the same interpreter/tools and commit epoch; compare wheel
   bytes. Check the version/license metadata, every RECORD member and complete
   package inventory. Verify that the sdist rebuilds the same runtime payload and
   excludes compatibility backups, caches and other local artifacts.
3. Run the supported Python 3.10/3.11 producer gates and installed-wheel golden
   with imports originating from site-packages, not the sibling source checkout.
4. Test the consumer baseline with its original wheel, then a disposable copy
   with the candidate's exact identity pins. Keep API/SDK DTOs, route definitions,
   UI files and test assertions unchanged. Exercise real Query/Reasoning,
   freeze/reload, Explain, auth rejection and installed-product paths.
5. Record the two source revisions, wheel hashes, exact pin-only trial diff and
   passing checks. A failure retains the old consumer artifact; never weaken the
   identity or API guards to make a candidate pass.

The initial 0.4.0rc1 consolidation changes packaging and documentation only.
Runtime payload equality with the shared rc3 wheel is an additional check, not a
replacement for installed API verification.

## Publication and adoption

### Supported release branches

| Ref | Responsibility |
| --- | --- |
| `main` | New development and fixes carried forward from supported release lines |
| `release/0.4.x` | 0.4 candidate stabilization, the future 0.4.0 final release and compatible 0.4 patch releases |
| `release/0.4-baseline` | Frozen pre-publication source marker at `2a4f6b8f` for Meander's original `0.2.0rc3` wheel; receives no commits |
| `v0.4.0rc1`, future `v0.4.0` / `v0.4.1` tags | Immutable source identities for individual published distributions |

The 0.4 maintenance line starts from the published `v0.4.0rc1` source plus the
reviewed CI/documentation bootstrap. It initially has the same runtime and
source as `main`. Creating the branch does not publish another artifact or
replace the existing rc1 files. The latest stable release remains `0.3.0` until
a separately accepted final release is published.

Maintain only lines that are actively supported. Create `release/0.3.x` from
`v0.3.0` if a concrete 0.3 support need appears. Exact-version branches
`release/0.1.0a1`, `release/0.2.0`, `release/0.3.0` and `release/0.4.0rc1`
are read-only historical snapshots at their corresponding remote tags.
They receive no fixes or new commits. See [release history](release-history.md)
for the distinction from earlier RC milestones in CHANGELOG.
Meander's retained `0.2.0rc3` is a distinct artifact from public `0.3.0`; an
urgent fix for that retained baseline starts from its recorded producer commit.
Use a new short-lived branch for such a fix; keep `release/0.4-baseline` frozen.

Develop a 0.4 fix on a short-lived branch based on `release/0.4.x`, then open a
PR targeting that maintenance branch. Carry the fix forward to `main` through a
PR as part of the same change. When a fix originates on newer `main`, backport
only the selected fix through a maintenance PR; do not pull unrelated new
features into a supported release. Both long-lived branches require the same
producer and installed-consumer gates, including for administrators, and reject
force pushes and deletion. Push CI covers `main` and `release/*`; PR CI covers
either target.

Prepare each release in a PR against its maintenance branch, with a new package
version and release notes. Use `0.4.0rc2` for a further candidate, `0.4.0` for the
accepted final release, and `0.4.1` for a later patch; never reuse a published
version for changed source or wheel bytes. After merge, rebuild and verify the
exact maintenance commit, record its independent consumer acceptance, then push
the matching version tag. Attach verified distributions, provenance, checksums
and the safe acceptance summary to its GitHub Release after publication.

### Versioned publication and consumer adoption

The PyPI workflow builds from an explicitly pushed version tag, verifies it
matches the source version, runs reusable producer CI and publishes the resulting
distributions through the existing `pypi` trusted publisher. Configure protected
environment review according to the repository's release policy. Keep exact
candidate compatibility evidence with the release review before pushing a tag.

Consumer adoption updates the wheel, manifest, lock/dependency/container and
runtime pins atomically after compatibility acceptance. It must preserve all
unrelated UI edits. Rollback restores only those coordinated dependency pins and
the preserved artifact; it does not rewind UI commits or workspace databases.

See the [PyPA trusted-publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
for the separation between build artifacts and the publishing job.

## Cloud merge and release gates

`main` is the current development source; supported `release/<major>.<minor>.x`
branches own their respective stabilization and patch work. Exact-version
`release/<version>` branches retain immutable historical source snapshots. Use short-lived branches and PRs
against the appropriate target. Version tags and Releases identify immutable
distributions. The original main
snapshot is `archive/main-before-2026-09-08`; historical branch/source accounting
is in [repository history](repository-history.md). Existing version tags are
never moved to reconcile naming differences.

The required `release-gate` aggregates the complete producer matrix (Python
3.10/3.11 with real Souffle/ProbLog), protocol preservation, complete and repeated
wheel builds, an sdist roundtrip and installed-wheel golden parity. Artifacts
include exact source/manifest/checksums and test reports. Mypy remains an explicit
non-blocking audit, preserving the preexisting policy.

`meander-compatibility` is a separate required commit status from trusted,
independent installed-consumer acceptance. Meander is private: its source and
raw test output must stay outside this public repository and public CI logs.
The acceptance record identifies the exact producer commit/wheel, frozen
consumer commit, baseline/candidate test outcomes and unchanged skip reasons.
The maintainer records only that public-safe summary and sets the status on the
exact verified commit. A new commit requires a new result; producer CI alone
cannot clear this gate. No shared consumer pin is updated by this process.

Before a version tag is pushed, recheck acceptance on the exact maintenance-branch commit;
a PR merge can change the source commit/epoch and therefore the distribution
bytes. The tag workflow reuses the full producer/artifact gates, verifies that
the tag matches the package version, requires successful consumer status for
that commit, and publishes only the already-verified wheel and sdist through
the existing PyPI environment. Keep manifest/checksums and the consumer summary
with the GitHub Release. Old source-projection scripts are historical tools;
the release path is `scripts/release.sh`.
