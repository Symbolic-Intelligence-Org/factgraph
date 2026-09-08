# Verified release history

Release dates below are the original publication dates, not the date a GitHub
Release page or source snapshot branch was restored. Exact-version branches
retain their tag's source without subsequent fixes. `release/0.4.x` is the
supported maintenance line; it advances through reviewed PRs.

## Published versions

| CHANGELOG version | Original publication | Immutable remote tag | Exact source | Read-only source branch | Original distributions |
| --- | --- | --- | --- | --- | --- |
| `0.4.0rc1` | 2026-09-08, PyPI prerelease | `v0.4.0rc1` | `bb805b4f109ead85a9a2bfc1a51e23ae481711fd` | `release/0.4.0rc1` | [GitHub Release](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/v0.4.0rc1), [PyPI](https://pypi.org/project/factgraph/0.4.0rc1/) |
| `0.3.0` | 2026-08-28, PyPI stable | `v0.3.0` | `5f8a78f403c79e72fa2037099e60d4b8ea7a5679` | `release/0.3.0` | [GitHub Release](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/v0.3.0), [PyPI](https://pypi.org/project/factgraph/0.3.0/) |
| `0.2.0` | 2026-06-14, successful PyPI publisher | `v0.2.0` | `2a173f255074038d4f3708b875f5be814554bb90` | `release/0.2.0` | [GitHub Release](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/v0.2.0); original files recovered from [run 27507472164](https://github.com/Symbolic-Intelligence-Org/factgraph/actions/runs/27507472164) |
| `0.1.0a1` | 2026-05-15, TestPyPI alpha | `v0.1.0a1` | `18a74006560293f59b929e8019b2b974883d4c55` | `release/0.1.0a1` | [GitHub Release](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/v0.1.0a1), [TestPyPI](https://test.pypi.org/project/factgraph/0.1.0a1/); [original run 25921426509](https://github.com/Symbolic-Intelligence-Org/factgraph/actions/runs/25921426509) |

Latest stable remains **0.3.0**. The 0.2.0 PyPI version endpoint currently returns
404 (checked 2026-09-08), while the successful original publisher and its build
artifact survive. Its recovered files are the original Actions outputs, not a
rebuild. Alpha files were recovered from TestPyPI and verified against its
published SHA256 values; its expired Actions artifact was not used.

## 0.4 source lineage

| Source reference | Role | Verified source |
| --- | --- | --- |
| `release/0.4-baseline` | Frozen source of Meander's retained wheel; a pre-0.4 publication baseline | `2a4f6b8fb1e9204c9782213590c61c5d21c069d8` |
| `release/0.4.0rc1` / `v0.4.0rc1` | Frozen source of the published prerelease | `bb805b4f109ead85a9a2bfc1a51e23ae481711fd` |
| `release/0.4.x` | Moving 0.4 maintenance line | `f40c5bae7ad06de6248a5a8f4665a8e54e55dd33` at the 2026-09-08 checkpoint |
| `main` | Moving development line | `864aca3be4d0f3f4bebf5e9b81556e4bf50c0e8c` at the same checkpoint |

The baseline is an ancestor of rc1, which is an ancestor of both maintenance
and main. Existing merge commits preserve that ancestry; this is not a claim
that every milestone lies on a single first-parent path. Adding the baseline
branch created no new source commit or divergent development line. Its source
still declares `0.2.0rc3`; `0.4-baseline` names its role in the release history
and is not a published package version.

At this checkpoint, main and maintenance have different merge commit IDs but
identical complete source trees. Relative to published rc1, their only changes
are CI and documentation; runtime source, tests and runtime dependencies are
unchanged. This documentation update preserves that runtime. All 310 runtime
files also match the original Meander wheel byte for byte. The full rc3 and
published rc1 wheels remain distinct artifacts with different package metadata,
versions and whole-wheel hashes; runtime equality does not make their pins
interchangeable.

The checkpoint records verified history, not a promise that moving branches
will always match. Later changes belong under `Unreleased` until separately
versioned and published. No `0.4.0rc2` has been published as of this checkpoint.
Historical snapshot branches and tags retain their original CHANGELOG files;
updated release explanations live on main and supported maintenance branches.

## Earlier changelog milestones

| Preserved CHANGELOG entry | Source evidence | Public release evidence |
| --- | --- | --- |
| `0.2.0-rc.1` — 2026-05-26 | Historical package metadata declares `factgraph 0.2.0rc1`; package-rename commit `4f4051c0` | No matching public tag or original distribution verified |
| `0.1.0-rc.1` — 2026-05-10 | Historical package metadata declares `factpy-kernel 0.1.0rc1`; release milestone commit `1aa157cc` | No matching public tag or original distribution verified |

These source milestones retain their original names and notes. They are not
aliases for the later alpha or stable tags. Missing current index entries do
not prove they were never published. No release tag, binary or snapshot branch
has been invented for them. Their source evidence belongs to earlier monorepo
history, rather than a newly reconstructed public distribution.

The June 14 `v0.2.0` tag already contained the notes subsequently left under the
August 28 `0.3.0` heading. The current CHANGELOG restores those exact notes to
`0.2.0` and keeps only the later additions under `0.3.0`. Current documentation
also marks the September 8 rc1 as published. Historical tagged CHANGELOG files
and published distributions retain their original bytes, including old wording.

## Ref and artifact preservation

- Use the remote `v0.2.0` identity `2a173f25`. An older local tag and the retired
  `release/v0.2.0` branch pointed at `2b08eb2d`; they are separate history and
  must not replace the actual published tag or its exact-version branch.
- `release/0.1.0a1` snapshots the actual alpha tag `18a74006`. The retired
  `release/v0.1.0-alpha.1` head `938d59c0` had an additional funding change and
  remains retained by `archive/release-v0.1.0-alpha.1-before-2026-09-08`.
- Historical source branches reject updates and deletion. Maintenance fixes
  start from an appropriate supported line through the [release process](releases.md).
- GitHub Release restoration attaches original wheel/sdist bytes, checksums and
  provenance to existing tags. It does not republish to PyPI, change a version,
  or assert that old source passes today's consumer compatibility gate.
- Meander main `07f782f` still retains its exact `0.2.0rc3` wheel, SHA256
  `2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`.
  This privately retained development artifact is distinct from public `0.2.0`.
  Its [backup](../artifacts/compatibility/meander-main-07f782f/) remains unchanged.
