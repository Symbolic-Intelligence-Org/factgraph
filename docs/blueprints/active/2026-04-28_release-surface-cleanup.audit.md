# Task Blueprint Audit: Release Surface Cleanup

- Blueprint: [2026-04-28_release-surface-cleanup.md](./2026-04-28_release-surface-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-28 | draft | Blueprint created | Created after confirming that v0.1 is wheel-RC ready but not repo/source publish ready. The private monorepo tracks `.claude`, `memory`, blueprint/audit history, agent/service/domain packages, third-party code, tools, and other materials outside the kernel-only OSS surface. |
| 2026-04-29 | scoped | Projection policy scoped | Locked staging-directory projection to separate public `Symbolic-Intelligence-Org/factpy-kernel`, default-deny allowlist, wheel-only v0.1 sdist policy, no examples/samples in initial projection, private projection script, and public docs scrub scope. |
| 2026-04-29 | implemented | Projection workflow implemented and verified | Added `scripts/project_release_surface.sh` + static allowlist, scrubbed public README/docs, set `include-package-data = false`, generated a 261-file projection, built the projected wheel, verified wheel contents/metadata, and ran clean-venv README quickstart. No public repo push, no tag, no upload, no sdist. |

## Decision Notes

1. **Wheel readiness is not source readiness**
   - **Decision**:Treat release-surface cleanup as separate from OS-prep readiness and RC wheel verification.
   - **Why**:`pyproject.toml` can build a kernel-only wheel while the tracked repository still contains non-public materials.
   - **Impact**:No GitHub/source publishing should proceed until projection, allowlist, denylist, and sdist policy are scoped and verified.

2. **Private monorepo should not be made public as-is**
   - **Decision**:A sanitized public projection is required.
   - **Why**:Tracked source includes operational memory, Claude workflow files, internal blueprints, agent/service/domain code, third-party/vendor material, and benchmark artifacts.
   - **Impact**:Implementation should favor a separate public `factpy-kernel` projection over making the private monorepo public.

3. **Projection mechanism locked**
   - **Decision**:Use a staging-directory projection generated from the private monorepo, then seed a separate public `Symbolic-Intelligence-Org/factpy-kernel` repository. The public shape is not the private monorepo and not a history-preserving filter-repo split.
   - **Why**:A clean projection minimizes accidental exposure of private workflow/history while keeping the monorepo as the development source of truth.
   - **Impact**:No public repository push or creation is authorized by this blueprint alone; projection verification must pass first.

4. **Default-deny public source surface**
   - **Decision**:Projection is allowlist-only. Denylist globs remain as a diagnostic safety net, but any path outside the explicit allowlist fails.
   - **Why**:The tracked repository has too many internal categories for denylist-only filtering to be reliable.
   - **Impact**:`examples/` and `samples/` are excluded from the initial v0.1 projection. They may be added later only after kernel-only import/link/smoke verification.

5. **v0.1 sdist policy**
   - **Decision**:v0.1 is wheel-only; no sdist upload.
   - **Why**:The current wheel has been verified as kernel-only, while source distribution needs a separate sanitized projection to avoid monorepo leakage.
   - **Impact**:Release-day workflow must not upload a `.tar.gz` sdist for v0.1. Future sdist support must build from the sanitized projection and pass the same gates.

6. **Projection workflow form**
   - **Decision**:Use private monorepo script tooling, preferably `scripts/project_release_surface.sh`, to generate the staging directory and manifest.
   - **Why**:A script is more repeatable than a hand-written command sequence and can become a CI/release-day gate.
   - **Impact**:The script itself is private tooling and must not be included in the projected public repository.

7. **Implementation verification**
   - **Decision**:Mark the release-surface cleanup blueprint implemented after projection and wheel verification passed.
   - **Evidence**:
     - `scripts/project_release_surface.sh` passed and emitted `/tmp/factpy_kernel_projection.manifest`.
     - Projection manifest count:261 files.
     - Projection-built wheel:`factpy_kernel-0.1.0-py3-none-any.whl`.
     - Wheel entries:161 total,156 `kernel/` entries,0 denylisted entries.
     - Metadata:runtime deps `pydantic>=2`, `diskcache>=5`, only `[dev]` extra, no private extras, no PyMuPDF / PyMuPDF4LLM.
     - Clean venv install succeeded;README quickstart printed `Alice`.
     - Projection `dist/` contained only the wheel, no sdist.
   - **Why**:The public source projection now has an executable, repeatable gate instead of relying on manual pruning.
   - **Impact**:Release-day workflow may use the projection script as the source-surface gate before creating/pushing the public repository. Actual public repo creation, PyPI upload, tag, and release remain explicitly out of scope for this implementation pass.
