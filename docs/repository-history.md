# Repository history and cloud consolidation

The September 2026 consolidation joins the earlier projected release history
with the current standalone FactGraph development history. The runtime source
is preserved from the verified producer `2a4f6b8f` and packaging candidate
`36c1b744`; Meander main `07f782f` continues to retain its original rc3 wheel.

## Source equivalence

- Old cloud main `b92d6bf5405be8d15eedea5b97aa7408914e76b9` has exactly the same
  non-documentation `src/factgraph` tree as current-line ancestor
  `f577f1d15fcc461140d3cf9e7bdcd34ae7224c3e` (the explicit source synchronization).
- Storage PR #23 at `2a728d196d7f54223af3e93e9110276fd1fe9e6a` has exactly the
  same non-documentation runtime tree as current-line ancestor
  `68553a44f383eb646264668136690a7bfeaf0a29`.
- Every original source blob, including module documentation, from those two
  snapshots is reachable in the verified candidate history: 278/278 and 282/282.
- Public release `v0.3.0` at `5f8a78f4` has one release-only commit beyond its
  common ancestor. Its version/license/workflow improvements were incorporated
  into `36c1b744`, retaining the current runtime and newer lint configuration.

These checks explain the distinct commit identities without inferring coverage
from commit counts alone. Joining the superseded projected histories therefore
preserves the current implementation tree. This is a deliberate history join,
not a general instruction to discard incoming merge changes.

## Test and behavior coverage

All test files from old main are still present. Of 2762 named test functions,
2748 retain their names and 2663 retain identical ASTs. PR #23 retains 2885 of
2887 names and 2836 identical ASTs. These are source comparisons, not fresh
execution counts; final producer and consumer results are recorded separately.

The twelve additional old-main name changes belong to the storage transition
already shipped on the development/public 0.3.0 line: write-through managed
writes, history-bound state commitments, UUID assertion IDs, workspace layout/
migration and strict managed-ingest references. PR #23 supplies their successor
checks. Its remaining two old names cover a historical working-tree cleanliness
assertion and the removed service application registry route. Current repository
purity and unchanged render/SDK registry-absence tests own those obligations.
No original runtime test is removed by this consolidation.

Storage PR #23's original Meander warning assumed a build from FactGraph main.
Meander now pins the wheel filename, SHA256, RECORD and runtime/source identities;
its shared artifact remains `2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`.
The complete PR storage test/golden inventory (41 files) is retained in the
candidate, including three-table transactions, event metadata/as-of reads,
chosen-by-sequence, lazy metadata, transaction defaults, migration and repair.

## Projected commit inventory

All runtime entries below are covered by the exact old-main/PR snapshots above
and their subsequent current-line changes. Release-only versions/tags remain
immutable. `.github/FUNDING.yaml` is preserved from old main. The old Pixi
manifest/lock is superseded by the standalone project's documented Python and
build extras; existing developer/consumer environments are not modified.

| Old commit | Change | Disposition |
| --- | --- | --- |
| `e4dc9f12` | publish: factgraph release surface — src/factgraph + tests + docs/quickstart + 6 meta files | Documentation/packaging superseded by current release and build instructions |
| `d4e85180` | docs/quickstart: clean up dead workflow/ + docs/official cross-doc links | Documentation/packaging superseded by current release and build instructions |
| `5bce1f42` | publish: sync to hnsm v0.2.0-impl-query-style-head 1e35c043 | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `57cfbc92` | publish: sync fields-get canonical-order fix from hnsm 95c9b295 | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `8af09994` | publish: sync factgraph release surface from hnsm 95c9b295 | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `52867270` | publish: sync schema digest stability fix | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `ed054fd0` | fix(schema): make schema object writes identity-idempotent | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `5e21e817` | publish: sync factgraph release surface from hnsm ea26f566 | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `d24bf1ac` | publish: sync explain :exists anchoring fix from hnsm 192474a7 | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `570c0a16` | fix(sdk): pass identity onto snapshot in unfiltered where() | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `b37955ca` | publish: fix ruff issues after explain sync | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `e1dc4ffa` | Fix missing schema capability bool validator import | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `aff1430b` | fix(explain): cross-engine diagnostic projection + arbitrary and/or composition on souffle/problog | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `8ce0a113` | test(sdk): guard diagnostic-projection dispatch tests behind souffle/problog availability | Test paths retained; subsequent storage/purity changes accounted for above |
| `2d2a84ee` | Add funding and PyPI publish workflow | Funding retained; publisher updated with verified packaging |
| `1825a12d` | Make test workflow reusable | Documentation/packaging superseded by current release and build instructions |
| `d2d8afbe` | Use pyproject.toml as pixi manifest | Superseded local environment configuration; original commits retained |
| `e623e2a0` | Add pixi workspace configuration | Superseded local environment configuration; original commits retained |
| `71aae82a` | Add linux-64 pixi platform | Superseded local environment configuration; original commits retained |
| `2a173f25` | Release v0.2.0 | Documentation/packaging superseded by current release and build instructions |
| `7aea6193` | Add read-only fg.eval.evaluate_candidates seam | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `c4407836` | feat(explain): engine-own reach-chain + full-coverage failure explain + atom support | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `4b27342a` | feat(entity): co-emit <EntityType>:exists at entity materialization | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `ae416ba3` | feat(sdk): evaluate_candidates(rule_expr, head=) — write leg of the RuleExpr path | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `209fe732` | test: fix two pre-existing failures + harden suite determinism | Test paths retained; subsequent storage/purity changes accounted for above |
| `d99ce340` | chore: gitignore the local .pixi environment | Superseded local environment configuration; original commits retained |
| `ab68270a` | Carry caller actor/business provenance onto accepted derived assertions | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `ea7f1d47` | feat(rules): fg.rules.structure — engine-neutral RuleStructure aligned with explain | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `d78b16b2` | feat(rules): RuleStructure.narrate() — text-level alignment with Explanation.narrate() | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `2a5c2226` | feat(audit): engine-neutral audit-package export (Block 1) | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `45197696` | feat(evaluate): meta-based premise admissibility filter at the evaluation seams | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `38b9171f` | test(evaluate): gates for the premise admissibility filter | Test paths retained; subsequent storage/purity changes accounted for above |
| `c4ce82ea` | fix(evaluate): last-wins live premise visibility + engine-seam/revoke-export gates | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `64860fe2` | feat(sdk): public assertions.append_meta reclassification seam | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `e2e3fa3c` | Block A: per-predicate premise admissibility allowance | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `241d95cd` | Block E: PredicatePremiseBlock — feldgenaue Quellen-Sperre | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `30b8dec8` | Block E review: scope the revoker-symmetry docstring to MetaExclusion | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `f11a10b7` | Add SDKStore.premise_scoped_view() read view | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `e253f558` | feat(sdk): EvaluationPremiseScope and rule program for the governance MVP | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `5a00db48` | feat(sdk): one rule surface — the capabilities take both rule forms | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `70e8d66f` | feat(sdk): program evaluation carries canonical evidence, frozen at decision time | Covered by exact main runtime snapshot at f577f1d1 and its successors |
| `2a728d19` | feat(storage): v0.3.0 storage hardening — Stage A + Slice 3b | Exact runtime snapshot at 68553a44; current storage tests retained |

## Original cloud refs and rollback

The immutable `archive/main-before-2026-09-08` tag preserves old main. The original
rc3 wheel and manifest are tracked under `artifacts/compatibility/`. Existing
public version tags are not rewritten. The table records branch heads before
consolidation; branch deletion is allowed only after the head is included in
verified main or otherwise explicitly preserved with resolved provenance.

| Original branch | Original head |
| --- | --- |
| `codex/factgraph-canonical-2026-08-27` | `d7dfae3fd209eb490c5267549117ce1fd181a04a` |
| `feat/mvp-overhaul` | `5a00db48c5556ccd71cb991b364e4915aea8c22b` |
| `feat/program-evidence-graph` | `70e8d66fcf2db9edc8a6896e2e4a1159f28378e4` |
| `feature/premise-admissibility-filter` | `64860fe23fe7491a07528d1b482ecd1d03cbcfdd` |
| `feature/v0.3.0-storage-hardening-2026-08-03` | `2a728d196d7f54223af3e93e9110276fd1fe9e6a` |
| `features/factgraph-product-purity-2026-08-27` | `5d27d20b207ab3eae562313ab80fbf55e73310b4` |
| `features/factgraph-repository-canonicalization-2026-08-27` | `ce60892860ac630bd804cdbc1373e8101e51bb61` |
| `features/meander-mvp-factgraph-sealed-evaluation-2026-08-23` | `26a88c645dd388632b0d06405c636682d91cfff0` |
| `main` | `b92d6bf5405be8d15eedea5b97aa7408914e76b9` |
| `release/v0.1.0-alpha.1` | `938d59c04aa41ccf6e693db2185c5f396972744a` |
| `release/v0.2.0` | `2b08eb2d575227376dd43a7ea5792677b6ff830f` |
| `release/v0.3.0-2026-08-28` | `5f8a78f403c79e72fa2037099e60d4b8ea7a5679` |

## Restored exact-version visibility

The initial cleanup retired the old branch names listed above. Subsequent
[release-history reconciliation](release-history.md) restores read-only
`release/<exact-version>` snapshots at the actual remote release tags. This
preserves visible history without treating snapshots as maintenance lines or
relabeling the earlier RC source milestones.
