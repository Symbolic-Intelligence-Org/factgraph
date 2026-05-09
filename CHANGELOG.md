# Changelog

All notable changes to FactPy Kernel will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0-rc.1] - 2026-05-09

First public preview release candidate.

### Added

- **FactPy Kernel SDK** (`kernel.sdk`): ergonomic OpenAI-style namespaced API
  (`schema`, `read`, `write`, `eval`, `what_if`, `audit`, `package`, `views`)
  layered over a flat `SDKStore` foundation. `FactGraph` is a literal alias of
  `SDKStore` — both surfaces are permanently supported.
- **Application layer** (`kernel.application`): explicit DTO contracts and
  pure functions for every runtime capability (Check, Diagnose, Fact Overlay,
  Why-not, Frontier, ProofFrame Recheck, Rule overlays, ProofFrame Diff,
  round events, package).
- **Walker view layer** (`kernel.application.walker`): deterministic, frozen,
  audit-friendly views over runtime artifacts for SDK-side consumption.
- **L Direction capability shells**:
  - G1: `SDKStore.check()` / `SDKStore.diagnose()`
  - G2: `SDKStore.check_fact_overlay()` / `SDKStore.recheck_proof_frame()`
  - G3: `SDKStore.check_rule_disable()` / `check_rule_literal_replace()` /
    `check_rule_add_condition()`
  - G4: `SDKStore.why_not()` (Frontier stays advanced importable)
  - G5: `SDKStore.diff_proof_frames()`
- **Engine adapters**: native, Souffle, ProbLog, PyReason — selectable at
  evaluation time.
- **Schema authoring** (`kernel.authoring`) with declarative `Entity`,
  `Identity`, `Field`, `Relationship`, `Rule`, `Pred` primitives.
- **Audit subsystem** (`kernel.audit`) with proof-frame and provenance graph
  queries.
- **Release tooling**: `scripts/release.sh` encapsulates the 3-layer
  (master → milestone → release-branch → tag) projection workflow with
  preflight, dry-run, verify, and cleanup-on-failure.
- **Changelog**: this file, following Keep a Changelog 1.1.0.

### Changed

- `pyproject.toml` version bumped to `0.1.0rc1` (PEP 440) for this release
  candidate.

## Earlier History

Prior development took place across the v0.1.x application-first capability
sequence (Check, Diagnose, Fact Overlay, Why-not, Frontier Trace), the A+B
public surface (helpers + walker), the L Direction SDK shells (G1-G5), and
the post-L SDK ergonomics redesign. See git history and the milestone branches
on origin (`milestone/pre-v0.1-2026-04-27` through `milestone/post-l-2026-05-09`)
for the full progression.
