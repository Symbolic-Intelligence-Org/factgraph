# Task Blueprint: Release Surface Cleanup

- Status: implemented
- Created: 2026-04-28
- Last Updated: 2026-04-29
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
- Do not create or push a public repository until projection verification passes and the user explicitly authorizes repo creation / push.
- Do not delete monorepo-private source content as part of this projection work.
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
| `samples/` | 12 | exclude from initial projection; optional future add-back after verification |
| `examples/` | 11 | exclude from initial projection; optional future add-back after import/link/smoke verification |
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

This blueprint is scoped around an allowlist-only public projection. The private monorepo remains the source of truth; the public source release is a generated kernel-only projection.

### 5.1 Projection mechanism

Candidates:

| Option | Shape | Pros | Cons |
| --- | --- | --- | --- |
| A | New public `factpy-kernel` repository seeded from an allowlisted snapshot | Cleanest public surface; no monorepo history leakage | Loses detailed private development history in public repo |
| B | Orphan `release/v0.1-kernel` branch in this repo, then push that branch to a new public repo | Simple, auditable snapshot; keeps private monorepo unchanged | Requires disciplined branch/export workflow |
| C | `git filter-repo` / history rewrite into public repo | Preserves selected file history | Higher risk of accidental history leakage; more operational complexity |
| D | `git subtree split` of `src/kernel` plus hand-added release files | Keeps some history and simple split mechanics | Does not naturally include root docs/metadata/examples; still needs pruning |

**Scoped decision**:use **B feeding A**, implemented as a staging-directory projection, then seed a separate public repository.

- Target public repository identity: `Symbolic-Intelligence-Org/factpy-kernel`.
- The private monorepo must not be made public as-is.
- Implementation should generate a sanitized projection directory from the private monorepo.
- The projection directory may be committed as an orphan audit snapshot if useful, but the public release shape is the separate `factpy-kernel` repository.
- This blueprint does not create the public repository or push to it; those remain explicit release-day / repo-creation actions.
- `git filter-repo` and history-preserving approaches are rejected for v0.1 because the history-leakage risk is not worth the benefit.

### 5.2 Public source allowlist

**Scoped decision**:the projection is default-deny. A file may appear in the public source only if it matches the allowlist below and passes the denylist gates in §5.3.

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
  - `docs/architecture_principles.md` only after scrub/link review
- no `examples/` in the initial v0.1 projection
- no `samples/` in the initial v0.1 projection

Implementation may later add back `examples/01_sdk_basics.ipynb`, `examples/02_rules_and_derivations.ipynb`, and `examples/README.md` only if they pass explicit import grep, link checks, and projection-local smoke. That add-back is optional; v0.1 can ship without examples.

### 5.3 Source denylist hard gates

**Scoped decision**:the primary hard gate is allowlist-only. Any projected path that does not match §5.2 fails.

The denylist below is an additional diagnostic gate. Projected public source must contain **zero** entries matching:

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
- `scripts/**`
- `**/__pycache__/**`
- `*.pyc`
- `dist/**`
- `build/**`
- `*.egg-info/**`
- `archive/**`
- `out/**`
- `*_demo_output/**`
- `test.ipynb`
- `context.md`
- `关于mvp的思考.md`
- `best_conf.csv`
- `path_conf.csv`
- benchmark results, run records, local previews, and generated artifacts

### 5.4 Examples and samples policy

**Scoped decision**:the initial public projection excludes all `examples/` and `samples/`.

- Explicitly excluded from v0.1 projection:
  - `examples/08_agent_document_workflow.ipynb`
  - `examples/09_dora_document_extraction.ipynb`
  - `examples/dora_pdf_extract.py`
  - ECSS/domain/agent/service examples
  - all `samples/*.csv`
- Optional add-back candidates after separate verification:
  - `examples/01_sdk_basics.ipynb`
  - `examples/02_rules_and_derivations.ipynb`
  - `examples/README.md`

Add-back verification must inspect notebook imports for `agent`, `service`, `domains`, third-party private deps, and monorepo-only paths before inclusion.

### 5.5 Sdist policy

Candidates:

| Option | Shape |
| --- | --- |
| A | v0.1 uploads wheel only; no sdist upload |
| B | v0.1 uploads sdist only from sanitized projection and verifies denylist |
| C | v0.1 uploads both wheel and sdist, but both are built from sanitized projection |

**Scoped decision**:v0.1 publishes **wheel only**. No sdist upload.

- Any accidental sdist artifact during release-surface implementation must be deleted and not uploaded.
- If sdist is added in a later release, it must be generated from the sanitized projection and pass the same allowlist/denylist gates as the public source repository.
- Implementation should consider `[tool.setuptools] include-package-data = false` if it reduces accidental data-file inclusion without breaking wheel contents.

### 5.6 Public docs policy

- Public docs should explain the kernel package and API surface, not the private blueprint workflow.
- Module docs under `src/kernel/*/docs/` may be retained only after link/content review.
- Root `docs/architecture_principles.md` may be retained only after scrub/link review.
- `docs/SECURITY.md` may be retained if it is externally readable and does not reference private workflow.
- `docs/blueprints/**`, `docs/blueprint_history/**`, `docs/references/**`, and `memory/**` are internal and excluded.

Scrub/link review requirements:

- `README.md` and `README.en.md` must not link to excluded paths.
- `src/kernel/**/docs/**` must not link to `docs/blueprints`, `docs/blueprint_history`, `docs/references`, `memory`, `.claude`, `AGENTS.md`, `src/agent`, `src/service`, `src/domains`, `third_party`, or `tools`.
- `docs/architecture_principles.md` must remove or rewrite references to private workflow, blueprint history, memory, or monorepo-only package surfaces before inclusion.

### 5.7 Projection workflow form

**Scoped decision**:implement a private projection script in the monorepo.

- Preferred path: `scripts/project_release_surface.sh`.
- The script is private tooling and must not be included in the projected public repository.
- The script should write to a staging directory outside the repository or under a generated ignored directory.
- The script should emit a manifest of projected files for review.
- The script should fail on any path outside §5.2 or any denylisted match in §5.3.

## 6. Boundaries And Invariants

- The private monorepo remains the development source of truth.
- The public v0.1 source surface must be kernel-only.
- The public repository must not expose operational memory, Claude workflow state, blueprint/audit history, agent/service/domain packages, third-party vendored projects, or benchmark results.
- The PyPI wheel remains kernel-only.
- The release projection must be reproducible from the private monorepo.
- The projected source and built artifact verification must be automated enough to re-run on release day.
- Public README claims must match files actually present in the public source projection.
- Default-deny is the security posture:missing allowlist entry means not projected.
- Public repository creation / push requires explicit user authorization after projection verification.

## 7. Acceptance

- [x] Projection mechanism is scoped:staging-directory projection feeding separate public `Symbolic-Intelligence-Org/factpy-kernel`.
- [x] Public source allowlist is scoped and default-deny.
- [x] Source denylist gates are scoped and executable.
- [x] sdist policy is scoped:wheel-only for v0.1.
- [x] `examples/` and `samples/` keep/drop decisions are scoped:initial projection excludes both.
- [x] Projection workflow form is scoped:private script, excluded from public projection.
- [x] Public docs scrub scope is scoped.
- [x] Projected public source contains no denylisted paths(`scripts/project_release_surface.sh` generated 261-file projection and passed allowlist / denylist / link gates).
- [x] Projected public source can build the `factpy-kernel` wheel(`python -m build --wheel` from `/tmp/factpy_kernel_projection`).
- [x] Projected public source README quickstart passes in a clean environment(clean venv install + quickstart output `Alice`).
- [x] No sdist is generated or uploaded for v0.1(projection `dist/` contains only `factpy_kernel-0.1.0-py3-none-any.whl`).
- [x] No publish, tag, or public repo push happens until explicit release-day authorization(no public repo push, no tag, no upload in this pass).

Verification command anchors to implement:

- Projection manifest check:compare generated manifest against the §5.2 allowlist; any non-allowlisted path fails.
- Denylist check:`find "$PROJECTION_DIR" ...` or equivalent script logic must return zero matches for §5.3 denylist globs.
- Link check:`README.md`, `README.en.md`, `src/kernel/**/docs/**`, and retained public docs must not reference excluded paths.
- Wheel check:inside the projection, run `python -m build --wheel` and repeat the RC wheel content / metadata inspection.
- Smoke check:install the projected wheel into a clean virtualenv and run the README quickstart.
- Sdist check:there must be no uploaded sdist for v0.1; if a local sdist is produced during testing, inspect and delete it before release.

## 8. Implementation Plan

1. Recompute source-surface evidence using `git ls-files -z` and record authoritative counts.
2. Implement private projection script (`scripts/project_release_surface.sh`) with allowlist-only behavior.
3. Add denylist/default-deny verification in the script.
4. Generate a projection manifest and inspect it.
5. Scrub public docs and README links for projection compatibility.
6. Build and inspect the projected source tree.
7. Build wheel from projection and re-run the RC hard gates against the projection.
8. Confirm no sdist is uploaded for v0.1.
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

Status moved to `implemented` on 2026-04-29. Blueprint remains under `active/`; archive stays gated on actual v0.1 publish + short stability window, together with OS-prep readiness, runtime-authority cleanup, audit-delivery contract, and RC verification.

- Final projection mechanism:
  - Private monorepo script `scripts/project_release_surface.sh`.
  - Default staging directory:`/tmp/factpy_kernel_projection`.
  - Manifest emitted at `/tmp/factpy_kernel_projection.manifest`.
  - Target public repository identity remains `Symbolic-Intelligence-Org/factpy-kernel`, but this pass did not create or push that repository.
- Final allowlist:
  - `scripts/release_surface_allowlist.txt`.
  - Root release files:README, README.en, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, pyproject, `.gitignore`, kernel workflow, SECURITY, architecture principles.
  - `src/kernel/**` except `src/kernel/AGENTS.md`, generated caches, and bytecode.
  - No `examples/` or `samples/` in the initial projection.
- Final denylist:
  - Enforced in `scripts/project_release_surface.sh` as diagnostic gate on top of allowlist-only projection.
  - Covers `.claude`, `AGENTS.md`, `memory`, blueprints/history/references, agent/service/domains, third_party, tools, generated artifacts, local keep-local outputs, and bytecode/cache paths.
- Final sdist policy:
  - v0.1 is wheel-only.
  - `pyproject.toml` now sets `[tool.setuptools] include-package-data = false`.
  - No sdist was built or uploaded in this pass.
- Projection verification result:
  - `scripts/project_release_surface.sh` passed.
  - Projection manifest contains 261 files.
  - Link/private-path scrub gate passed for README, public docs, and `src/kernel/**/*.md`.
- Wheel verification result:
  - Projection-built wheel:`factpy_kernel-0.1.0-py3-none-any.whl`.
  - Wheel entries:161 total / 156 `kernel/` entries.
  - Bad entries:0 for `agent/`, `service/`, `domains/`, `kernel/tests/`, `docs/`, `memory/`, `third_party/`, `tools/`, `.claude/`, or `AGENTS.md`.
  - Metadata exposes only runtime deps(`pydantic`, `diskcache`) and `[dev]` extra;no private extras or AGPL parser dependencies.
- Smoke verification result:
  - Clean venv install succeeded with runtime deps.
  - README quickstart printed `Alice`.
- Public README/docs adjustments:
  - Root README / README.en removed monorepo-only install/test paths and internal workflow links.
  - `docs/architecture_principles.md` removed private workflow / memory / blueprint-history details.
  - Kernel module docs removed private blueprint, service path, and benchmark/tool references that would break projection.
- Long-term management model:
  - Recorded in `docs/architecture_principles.md` under "Release surface governance".
  - Private monorepo remains the development source of truth.
  - Public `factpy-kernel` repository is a generated projection artifact, not the day-to-day development branch.
  - PyPI wheel / public source release should be built from the verified projection tree.
- Deviations from draft:
  - `examples/` and `samples/` were excluded entirely for v0.1 instead of adding back candidate examples.
  - Build verification required network access for isolated build dependencies and clean venv runtime dependencies.
  - Setuptools emitted deprecation warnings for table-style `project.license` and license classifiers;not a v0.1 blocker, but should be cleaned before the 2027 deprecation deadline.
- Archive note:
  - Do not archive until actual v0.1 publish + short stability window.
