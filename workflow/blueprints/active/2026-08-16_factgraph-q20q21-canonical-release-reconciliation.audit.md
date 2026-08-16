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
| 2026-08-16 | draft | Independent preflight incorporated | Preflight `ad96da6d` classified all 50 candidate paths, found the old-graph/new-R3d name collision, unsafe one-input projection/staging behavior, façade closure drift, and inherited public-doc link baseline. This blueprint remains draft pending its required gates. |

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

### D-5 — Public-owned surface files use a b92-based explicit patch

The sync runbook classifies `.github/`, `pyproject.toml`, `CHANGELOG.md`, root
documents, and module docs as surface-owned rather than HNSM projection inputs.
Preflight therefore selected a dual-input composition: a private feature source
contributes only a named kernel/test manifest; b92 supplies public-owned files;
a later public `features/...` patch may change only an explicit public-owned
list. Initially that list can contain the CI workflow and, only if required by
the approved CI command, public dev test setup. It cannot copy private version
metadata, changelog, or documentation content.

Although the application/protocol/SDK façade files are kernel paths, their
private versions import non-public V1/V2/Scenario modules. The composed public
versions are therefore built from b92 plus an approved export list—not merged
from private `__init__` files. Exact positive and forbidden export tests,
static closure, and installed-wheel import tests are required before a
projection candidate can be reported.

### D-6 — Fixed graph playback and receipt inventory names prevent a semantic type swap

Private `evaluation_run_bundle_evidence(...)->EvidenceGraph` is a stable graph
playback path used by captured-run and Scenario consumers. Candidate R3d used
the same name for a `CapturedReceiptEvidenceV0` return, which would break those
consumers and blur the capture-only boundary. The required reconciliation has
two fixed paths: retain the old graph builder and add a differently named,
graph-free receipt builder only after actual private-source implementation.
R3e/F4C coordinate/overlay/manifest paths are deferred from this slice.

### D-7 — Projection cleanup is itself a safety boundary

The current helper accepts broad caller-supplied staging paths before `rm -rf`;
the preflight found that `/tmp`, home-derived, sibling, and unmarked paths are
not adequately rejected. The later scoped slice must first establish a
tool-owned scratch root, `mktemp` issuance, marker/`realpath` containment, and
hard denial of private paths even if an allowlist is widened. Its tests use
sentinels/mocks rather than destructive broad-path experiments. The inherited
b92 quickstart `BL-1` missing example link remains either a separate curated
doc repair or an explicit non-link-clean baseline; it may not be ignored.

### D-8 — Dual-input evidence pins source objects, not just human-readable refs

The composed-tree procedure records more than branch labels: each private
manifest entry, b92 surface input, and approved public-patch input must resolve
to the recorded Git ref and expected blob digest before the helper reads it.
This prevents a mixed-worktree or changed-current-checkout input from being
misreported as an earlier reviewed coordinate. Wheel evidence records those
resolved input digests alongside its own SHA-256 and manifests.

### Open items before `scoped`

- Complete the required standalone preflight after rereading the exact private,
  public, and candidate sources and all projection/release files.
- Independently review the preflight amendment and record its final decision
  against `ad96da6d`.
- Resolve every carried-path import/export closure in the three-way matrix,
  preserving private Function/navigation/Policy/Scenario behavior.
- Specify the minimal kernel/test private manifest, b92 façade export overlay,
  marker-safe composition helper, hard-deny list, and exact public-diff set.
- Scope the public `BL-1` curated-doc repair separately, or retain its
  non-link-clean status explicitly; do not hide it.
- Reconfirm the public workflow, staging-wheel, version/changelog, and public
  `features/...` PR mechanics against the exact then-current refs.
- Obtain explicit authorization for the preflight amendment and later for
  `draft → scoped`; no code implementation is authorized by this draft.
