# Releases and retained consumer compatibility

The public `0.3.0` release and the subsequent `0.2.0rc3` development artifacts
share history but were versioned on separate branches. `0.4.0rc1` consolidates
the current development runtime and public packaging. It is a candidate; public
publication and a consumer's adoption are separate transitions.

## Preserve the shared baseline

Meander main `07f782f` uses the exact rc3 wheel from producer `2a4f6b8f`, SHA-256
`2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`.
An immutable backup and original manifest are retained in the repository at
`artifacts/compatibility/meander-main-07f782f/`. Verify its `SHA256SUMS` before use.
Those files are not included in distributions. UI-only development can continue
on that artifact while new candidates are tested separately.

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
