# Task Blueprint Audit: FactGraph Q20/Q21 canonical release reconciliation

- Blueprint: [2026-08-16_factgraph-q20q21-canonical-release-reconciliation.md](./2026-08-16_factgraph-q20q21-canonical-release-reconciliation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-16 | draft | Blueprint created | Drafted from release-surface audit `2458e79a55062be862fb2aec0ea447ac6614b03e`; no implementation, source transfer, projection, or release action has begun. |
| 2026-08-16 | draft | Three-way source graph recorded | Private canonical baseline `c01dccae`, public baseline `b92d6bf5`, and candidate `6d7628cd` are distinct comparison coordinates. The public baseline is not an ancestor of the private baseline; direct cherry-pick is excluded. |
| 2026-08-16 | draft | Default-deny docs/example boundary recorded | Candidate worktree module docs and runnable example/test are uncommitted and link an excluded `examples/` path. They are not source-transfer or public-projection input in this slice. |
| 2026-08-16 | draft | R3d/R3c/F4 boundary recorded | R3d remains a strict capture-only receipt DTO, R3c verification remains non-replay, and R3e/F4C receive no completed-public-capability claim from this draft. |
| 2026-08-16 | draft | Independent review amendments | P1 review findings require a distinct preflight branch before any implementation branch and an explicit preflight choice for public CI/package metadata ownership. |

## Decision Notes

### D-1 — Canonical direction is private source to public projection

The adopted architecture principle and release-surface audit require private
HNSM to be the development source of truth. `6d7628cd` is treated as reviewed
comparison input, not as a source of canonical Git history. Any future carried
behavior must be reconstructed and verified on a private feature branch rooted
at `c01dccae`, with a three-way path matrix against public `b92d6bf5` and the
candidate. This is a draft constraint; it has not yet authorized implementation.

### D-2 — Q20/Q21 module docs and examples are default-denied

For this slice, the public projection excludes the candidate's current module
doc changes, runnable example, and example test. A projected document cannot
link to a private/excluded `examples/` path. This does not erase or rewrite
existing public-baseline docs, and it does not prevent a future separately
scoped curated documentation corpus.

### D-2a — Public release base is not private development authority

The sync runbook uses `factgraph/main` operationally as the base for a future
public feature branch, while the architecture principle assigns private HNSM
the development-source role. Preflight must validate the mechanics of both
without allowing the public baseline or candidate to reverse the source-of-
truth direction.

### D-3 — Receipt inventory is not a graph/proof/product contract

`CapturedReceiptEvidenceV0` can be a strict application-protocol DTO only
after private reconciliation proves its actual export and tests its seals and
failure paths. It has no generic `EvidenceGraph`, `Explanation`, Policy
conclusion, logical proof, proof-parity, replay, source/admission/governance,
or Product/Meander/Agent/MCP/SDK wire meaning. Any graph/playback bridge is a
private seam until separately established.

### D-4 — Release evidence has non-interchangeable gates

Private test success, a projection manifest, a wheel digest, a pushed public
feature branch, remote CI, a tag, and a published artifact each answer a
different question. None can be used as evidence for a later gate. Mypy and
coverage remain advisory unless their workflow configuration is deliberately
made blocking; they must not be reported as hard release gates otherwise.

### D-5 — Public-owned surface files are not silently projected

The current sync runbook classifies `.github/`, `pyproject.toml`, and
`CHANGELOG.md` as public-repository-owned, not default projection inputs. The
standalone preflight must choose and justify either a narrowly reviewed runbook
amendment or an explicitly enumerated public-owned surface patch against
`b92d6bf5`. Until then, no sentence in this draft assumes that an allowlist
carries CI/package metadata, and no future public diff may change unlisted
surface files or existing public documentation.

### Open items before `scoped`

- Complete the required standalone preflight after rereading the exact private,
  public, and candidate sources and all projection/release files.
- Resolve every path classification and import/export closure in the three-way
  reconciliation matrix.
- Specify the minimal explicit public allowlist delta without broadening into
  private docs/examples or unrelated historical surfaces.
- Resolve the public CI/package-metadata ownership mechanism and exact allowed
  public-diff set before any scoped implementation branch exists.
- Reconfirm the public workflow, staging-wheel, version/changelog, and public
  `features/...` PR mechanics against the exact then-current refs.
- Obtain explicit authorization for the preflight amendment and later for
  `draft → scoped`; no code implementation is authorized by this draft.
