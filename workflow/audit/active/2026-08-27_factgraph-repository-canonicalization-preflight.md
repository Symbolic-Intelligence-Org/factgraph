# FactGraph Repository Canonicalization Preflight

- Date: 2026-08-27
- Status: complete
- Blueprint: [2026-08-27_factgraph-repository-canonicalization.md](../../blueprints/active/2026-08-27_factgraph-repository-canonicalization.md)
- Scope: current `/Users/zhenzhili/hnsm-backend` Git repository only
- Protected outside scope: active `meander` and `meander-ilp` repositories

## 1. Verified Repository State

| Item | Verified state | Migration consequence |
| --- | --- | --- |
| Current HEAD | `c01dccae5c524d667dd4414201be3961312076df` | Preserve as a recovery anchor. |
| Canonical FactGraph feature ref | `26a88c645dd388632b0d06405c636682d91cfff0` | Use as the reconciliation base. |
| Relationship | `26a88c` is 20 commits ahead of `c01dcc`; the current committed HEAD has no unique commit | Reapply local dirty work; do not treat `c01dcc` as the newer lineage. |
| FactGraph `main` | `b92d6bf5405be8d15eedea5b97aa7408914e76b9` | Older public baseline; not the Meander-compatible feature base. |
| Current default remote | `origin` -> `Symbolic-Intelligence-Org/hnsm-backend` | Rename only after reconciliation and verification. |
| Intended product remote | `factgraph` -> `Symbolic-Intelligence-Org/factgraph` | Becomes `origin` in steady state. |
| Meander retained artifact | FactGraph `26a88c`, wheel digest `d82abca5...5af696c` | Confirms `26a88c` is the current integration-compatible base; do not update Meander in this slice. |

The remote SHA values above were independently queried from GitHub on
2026-08-27 rather than inferred only from cached tracking refs.

## 2. Dirty-Worktree Preservation Map

### P1 — Retain and reconcile into canonical FactGraph

The following 15 tracked files form the implemented Q22 operator-sensitive
Policy literal equality slice. Its blueprint reports focused, cross-engine, and
broader regression verification. This work is newer than the current retained
wheel but is based on the older `c01dcc` worktree, so it must be replayed and
reverified on `26a88c`.

```text
docs/quickstart/rules.md
src/factgraph/application/docs/rule.md
src/factgraph/application/evaluation_query_target_runtime.py
src/factgraph/application/policy_runtime.py
src/factgraph/application/protocol/policy.py
src/factgraph/sdk/docs/03_rules_and_inferences.en.md
src/factgraph/sdk/policy_authoring.py
tests/application/test_evaluation_query_target_runtime.py
tests/application/test_evaluation_run_bundle_runtime.py
tests/application/test_evaluation_run_v1_runtime.py
tests/application/test_policy_runtime.py
tests/application/test_portable_evaluation_runtime.py
tests/application/test_product_views_v2.py
tests/sdk/test_policy_authoring.py
tests/sdk/test_unified_evaluation_query.py
```

The Q22 decision, preflight, blueprint, and audit documents are retained with
the slice until shared-workflow extraction classifies their long-term home.

### P2 — Preserve but keep outside the Q22 replay

These tracked changes may be useful FactGraph developer-experience or example
work, but they are not part of Q22 and must not be accidentally included in its
reconciliation commit:

```text
pyproject.toml                         # local Pixi workspace proposal
examples/01_sdk_check_diagnose.ipynb
examples/02_overlay_why_not_frontier.ipynb
examples/03_proofframe_rule_overlays.ipynb
examples/04_round_persistence_diff.ipynb
examples/05_sdk_assertion_views.ipynb
examples/06_workspace_lifecycle_v030.ipynb
examples/aml_compliance_manual_demo.ipynb
examples/rule_composition_demo.ipynb
examples/rule_structure_demo.ipynb
examples/explain_complex_engines_demo.ipynb
examples/meander_test.ipynb
```

Disposition: preserve byte-for-byte during canonicalization; review as separate
FactGraph slices after Q22 is safely based on `26a88c`.

### P3 — Preserve workflow history for later extraction

The dirty tree contains active audits, blueprints, decisions, design points,
archive moves, handoffs, and a 2.9 MiB session export. Some are FactGraph-local;
some describe Meander or cross-repository work. No blanket deletion or blanket
FactGraph commit is safe.

Disposition: preserve all current bytes. Land only the Q22 and repository
canonicalization records needed to explain product changes. Classify the rest
when creating `symbolic-workflow`; do not modify the active Meander repository.

The apparent deleted/added blueprint and design-point pairs are archival moves,
not data loss, and must remain paired during later extraction.

### P4 — Preserve staged dependency removals as an independent decision

The index currently contains:

- removal of the `third_party/rule-parser` submodule registration and gitlink;
- removal of the tracked `third_party/kg-gen` tree;
- 89 staged paths and approximately 60,919 deleted lines.

Disposition: leave the index and working-tree deletions untouched during Q22
reconciliation. These removals require their own verification and must not be
silently bundled into repository identity or product commits.

### P5 — Keep machine-local and outside canonical repositories

```text
.claude/launch.json                   # absolute local paths, including Meander
.vscode/
.meander-ui-ontologies/
```

Disposition: preserve locally, exclude from canonical cross-machine project
configuration, and do not copy into `symbolic-workflow` as shared state.

### P6 — Preserve external/reference experiments outside FactGraph

```text
meander-agent-test/
rainbird-ai sdk code/
```

Disposition: preserve until the user authorizes relocation or deletion. They
are not FactGraph product sources and must not enter a FactGraph commit.

## 3. Findings

| ID | Severity | Finding | Required response |
| --- | --- | --- | --- |
| PF-R1 | Required before scoped | The current worktree combines a newer Q22 slice with an older committed base. | Capture Q22 as a bounded change and replay it onto `26a88c`; never reset it away. |
| PF-R2 | Required before scoped | Existing staged third-party removals are unrelated and very large. | Use exact path-scoped staging/commits; independently preserve the existing index state. |
| PF-R3 | Required before scoped | Workflow files include FactGraph, Meander, and cross-project state. | Preserve all; land only migration/Q22 evidence now and defer final ownership to workflow extraction. |
| PF-R4 | Required before scoped | Local configuration contains absolute paths into both legacy FactGraph and active Meander locations. | Do not publish those paths; update local configuration only after filesystem migration, without touching Meander. |
| PF-R5 | Required before scoped | Meander delivery intentionally pins immutable FactGraph artifact bytes. | Keep the current C2 artifact unchanged; future FactGraph versions use candidate-wheel compatibility testing and explicit promotion. |
| PF-V1 | Verified assumption | `26a88c` is exactly the FactGraph source commit pinned by Meander. | Treat it as the canonical reconciliation base. |
| PF-V2 | Verified assumption | The nested `meander-latest-stack/factgraph-new` checkout is old `main@b92d6bf` and is not Meander's delivery dependency. | Do not use it as the canonical source and do not modify it while Meander is active. |

## 4. Safe Execution Order

1. Create recovery material for committed refs, staged diff, unstaged diff, and
   untracked files before changing the working tree.
2. Create a non-sacred migration branch at `c01dcc` without switching files.
3. Land the Q22 product and evidence files with exact path scoping, leaving all
   unrelated staged and unstaged changes unchanged.
4. Reconcile that bounded commit onto `26a88c` using a reversible branch
   operation; resolve only Q22 conflicts.
5. Run Q22 focused tests plus the sealed-evaluation/Meander-facing FactGraph
   contract tests introduced by the 20 newer commits.
6. Only after green verification, make FactGraph the `origin` remote and verify
   ordinary feature-branch push routing without pushing.
7. Defer filesystem relocation and workflow extraction until the canonical
   branch, recovery material, and dirty-file dispositions have been verified.

## 5. Preflight Result

No abandonment blocker was found. The migration can proceed after PF-R1 through
PF-R5 are reflected in the scoped blueprint. The safe base is `26a88c`, the
current C2 wheel remains unchanged, and all Meander repositories remain outside
the write scope.
