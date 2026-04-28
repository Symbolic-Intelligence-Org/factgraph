# Task Blueprint: Release Surface Cleanup

- Status: draft
- Created: 2026-04-28
- Last Updated: 2026-04-28
- Related Modules:
  - `pyproject.toml`
  - `README.md`
  - `README.en.md`
  - `src/kernel/`
  - `.github/`
  - `examples/`
  - `samples/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/active/2026-04-27_oss-prep-v0.1.md](./2026-04-27_oss-prep-v0.1.md)
  - [docs/blueprints/active/2026-04-28_v0.1-release-candidate.md](./2026-04-28_v0.1-release-candidate.md)
- Audit Log:
  - [2026-04-28_release-surface-cleanup.audit.md](./2026-04-28_release-surface-cleanup.audit.md)

## 1. Problem

The v0.1 wheel-level RC is ready, but the repository/source release surface is not yet clean.

`pyproject.toml` currently builds a kernel-only wheel, and RC verification confirmed the post-fix wheel excludes `kernel.tests`, `agent`, `service`, `domains`, and private extras. That does **not** mean the GitHub/source release surface is publishable.

Tracked repository content still includes internal workflow and out-of-OSS materials:

- `.claude/`
- `AGENTS.md` files
- `memory/`
- `docs/blueprints/`, `docs/blueprint_history/`, and working references
- `src/agent/`
- `src/service/`
- `src/domains/`
- `third_party/`
- `tools/`
- `.tmp_backend_preview/`
- examples and samples whose kernel-only status has not been audited

If the full monorepo is made public, these files are exposed regardless of wheel packaging filters. If an sdist is uploaded without a separate policy, source distribution contents may also expose non-kernel materials.

## 2. Goals

- Define the v0.1 public release surface for source/repository distribution, not only PyPI wheel distribution.
- Decide the projection mechanism for a clean public `factpy-kernel` surface.
- Define an allowlist for files that may appear in the public source surface.
- Define a denylist / hard gate for internal workflow, agent/service/domain, third-party, tool, memory, and blueprint materials.
- Decide the v0.1 sdist policy.
- Add verification commands that prove the projected source surface and built artifacts do not contain out-of-scope content.
- Keep the private monorepo usable as the development source of truth.

## 3. Non-goals

- Do not publish to PyPI.
- Do not tag a release.
- Do not create or push a public repository until the projection decision is scoped.
- Do not delete monorepo-private source content as part of the draft phase.
- Do not rewrite agent/service/domain code.
- Do not archive the implemented v0.1 blueprints before actual publish + stability window.
- Do not make v1.0 stable API promises.

## 4. Current Context

### 4.1 Wheel-level state

- `pyproject.toml` contains:
  - `include = ["kernel*"]`
  - `exclude = ["kernel.tests*"]`
- RC verification found and fixed a wheel leakage issue where `src/kernel/tests/` lacked `__init__.py`; the post-fix wheel excludes `kernel/tests/*`.
- Current RC verdict is `conditional pass` because of that inline packaging fix.

### 4.2 Tracked source surface snapshot

Rough tracked top-level counts from `git ls-files`:

| Top-level | Count | Draft classification |
| --- | ---: | --- |
| `src/kernel/` | 252 | keep, subject to excluding `src/kernel/AGENTS.md` and generated caches |
| `docs/` | 458 | mostly exclude; selectively keep public docs only |
| `src/agent/` | 91 | exclude |
| `third_party/` | 88 | exclude |
| `tools/` | 42 | exclude unless a release helper is explicitly allowlisted |
| `memory/` | 25 | exclude |
| `src/service/` | 21 | exclude |
| `src/domains/` | 15 | exclude |
| `samples/` | 12 | undecided; audit for generic kernel-only usefulness |
| `examples/` | 11 | undecided; keep only kernel-only examples after smoke |
| `.claude/` | 3 | exclude |
| `AGENTS.md` / scoped `AGENTS.md` files | 3 | exclude |
| `.tmp_backend_preview/` | 2 | exclude |
| `.gitmodules` | 1 | exclude |
| `requirements/` | 1 | likely exclude; current file is monorepo dev-oriented |

Note: shell text output can quote filenames with non-ASCII characters; implementation should use `git ls-files -z` for authoritative classification.

### 4.3 Sensitive tracked categories

- `memory/session_handoffs/*.md`: operational session notes.
- `docs/blueprints/**`: active/archive audit trail and internal decision history.
- `docs/blueprint_history/**`: legacy historical material.
- `docs/references/working/**`: working notes and reports.
- `.claude/**`: local Claude Code configuration and skills.
- `AGENTS.md` files: internal workflow rules.
- `third_party/**`: vendored/submodule/foreign project material, including `.env.example` and deployment files.
- `src/agent/**`, `src/service/**`, `src/domains/**`: explicitly out of v0.1 OSS kernel scope.
- `tools/**`: benchmark/results/development tooling outside the published kernel surface.

## 5. Proposed Shape

This blueprint must scope these decisions before implementation:

### 5.1 Projection mechanism

Candidates:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| A | New public `factpy-kernel` repository seeded from an allowlisted snapshot | Cleanest public surface; no monorepo history leakage | Loses detailed private development history in public repo |
| B | Orphan `release/v0.1-kernel` branch in this repo, then push that branch to a new public repo | Simple, auditable snapshot; keeps private monorepo unchanged | Requires disciplined branch/export workflow |
| C | `git filter-repo` / history rewrite into public repo | Preserves selected file history | Higher risk of accidental history leakage; more operational complexity |
| D | `git subtree split` of `src/kernel` plus hand-added release files | Keeps some history and simple split mechanics | Does not naturally include root docs/metadata/examples; still needs pruning |

Pre-scoping default: **B feeding A** - create a sanitized orphan/projection snapshot from the private monorepo, then push that snapshot to a separate public `factpy-kernel` repository. Do not make the private monorepo public.

### 5.2 Public source allowlist

Initial allowlist candidate:

- `pyproject.toml`
- `README.md`
- `README.en.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `.gitignore`
- selected `.github/workflows/` entries that only reference kernel checks
- `src/kernel/**`
  - include kernel module docs and kernel tests for source repo development
  - exclude `src/kernel/AGENTS.md`
  - exclude `__pycache__/` and generated files
- selected public docs:
  - `docs/SECURITY.md`
  - `docs/architecture_principles.md` only if scrubbed for public references
- selected `examples/` only if they are kernel-only and pass from the projected repo
- selected `samples/` only if they are generic and useful for kernel examples

### 5.3 Source denylist hard gates

Projected public source must contain **zero** entries matching:

- `.claude/**`
- `AGENTS.md`
- `**/AGENTS.md`
- `CLAUDE.md`
- `memory/**`
- `docs/blueprints/**`
- `docs/blueprint_history/**`
- `docs/references/**`
- `src/agent/**`
- `src/service/**`
- `src/domains/**`
- `third_party/**`
- `tools/**`
- `.tmp_backend_preview/**`
- `.gitmodules`
- `requirements/dev.txt`
- `**/__pycache__/**`
- `*.pyc`
- benchmark results, run records, local previews, generated `dist/` / `build/`

### 5.4 Examples and samples policy

Pre-scoping default:

- Exclude all `examples/` from the first projected source snapshot unless each retained example is verified kernel-only.
- Exclude `examples/08_agent_document_workflow.ipynb`, `examples/09_dora_document_extraction.ipynb`, `examples/dora_pdf_extract.py`, and any ECSS/domain/agent/service examples.
- Consider adding back only:
  - `examples/01_sdk_basics.ipynb`
  - `examples/02_rules_and_derivations.ipynb`
  - `examples/README.md`
  after projection-local smoke.
- Keep `samples/` only if README/examples need them and contents are generic.

### 5.5 Sdist policy

Candidates:

| Option | Shape |
| --- | --- |
| A | v0.1 uploads wheel only; no sdist upload |
| B | v0.1 uploads sdist only from sanitized projection and verifies denylist |
| C | v0.1 uploads both wheel and sdist, but both are built from sanitized projection |

Pre-scoping default: **A or B**, not monorepo sdist. If an sdist is uploaded, it must be generated from the sanitized projection and pass the same denylist gates as the public source repository.

### 5.6 Public docs policy

- Public docs should explain the kernel package and API surface, not the private blueprint workflow.
- Module docs under `src/kernel/*/docs/` may be retained if they do not link to private-only docs.
- Root `docs/architecture_principles.md` may be retained after link/content review.
- `docs/blueprints/**`, `docs/blueprint_history/**`, `docs/references/**`, and `memory/**` are internal and excluded.

## 6. Boundaries And Invariants

- The private monorepo remains the development source of truth.
- The public v0.1 source surface must be kernel-only.
- The public repository must not expose operational memory, Claude workflow state, blueprint/audit history, agent/service/domain packages, third-party vendored projects, or benchmark results.
- The PyPI wheel remains kernel-only.
- The release projection must be reproducible from the private monorepo.
- The projected source and built artifact verification must be automated enough to re-run on release day.
- Public README claims must match files actually present in the public source projection.

## 7. Acceptance

- [ ] Projection mechanism is scoped.
- [ ] Public source allowlist is scoped.
- [ ] Source denylist gates are scoped and executable.
- [ ] sdist policy is scoped.
- [ ] `examples/` and `samples/` keep/drop decisions are scoped.
- [ ] Projected public source contains no denylisted paths.
- [ ] Projected public source can build the `factpy-kernel` wheel.
- [ ] Projected public source README quickstart passes in a clean environment.
- [ ] If sdist is enabled, sdist contents pass denylist verification.
- [ ] No publish, tag, or public repo push happens until explicit release-day authorization.

## 8. Implementation Plan

1. Recompute source-surface evidence using `git ls-files -z` and record authoritative counts.
2. Scope projection mechanism and public repository shape.
3. Scope allowlist / denylist, including `examples/`, `samples/`, `.github/`, and public docs.
4. Scope sdist policy.
5. Implement a reproducible projection workflow in a private-script or documented command sequence.
6. Build and inspect the projected source tree.
7. Build wheel from projection and re-run the RC hard gates against the projection.
8. If sdist is enabled, build and inspect sdist from projection.
9. Update README/docs if public projection removes paths currently referenced by docs.
10. Fill §10 Outcome / Deviations and append audit decisions.

## 9. Docs To Update

- `README.md`
- `README.en.md`
- `pyproject.toml` if sdist/package-data policy changes
- `.github/workflows/*` if public workflows are projected
- `docs/architecture_principles.md` if it remains in public docs
- `memory/current.md`
- OS-prep / RC blueprints if release-day gating changes materially

## 10. Outcome / Deviations

Task completion will fill:

- Final projection mechanism:
- Final allowlist:
- Final denylist:
- Final sdist policy:
- Projection verification result:
- Wheel/sdist verification result:
- Public README/docs adjustments:
- Deviations from draft:
- Archive note:
