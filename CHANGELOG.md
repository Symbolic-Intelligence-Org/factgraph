# Changelog

All notable changes to FactGraph will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-rc.1] - 2026-05-26

### Breaking

- **PyPI package renamed**: install `factgraph` instead of `factpy-kernel`.
  Existing environments should run:

  ```bash
  pip uninstall factpy-kernel
  pip install factgraph
  ```

  Python imports do not change for the v0.2 surface:
  `from factgraph.sdk import ...`.

### Added

- **Public result/evidence path**: `EvaluateResult`, `EvaluateRow`, `Claim`,
  `EvidenceRef`, `Explanation`, `row.explain()`, `row.close()`, and
  `fg.eval.explain(...)` are the public SDK explanation surface.
- **Application Rule / RuleExpr evaluation**: public `Rule` and `RuleExpr`
  values are the primary rule authoring and evaluation inputs.
- **Public semantics wrappers**: `ProbLogSemantics` and `PyReasonSemantics`
  lower into canonical semantics profiles for public SDK calls.
- **Database and durable view substrate**: `Database.create(...)`,
  `Database.open(...)`, durable assertion views, and read-only
  `FactGraph.attach(db, view=view, schema_classes=[...])` are shipped.
- **Read-side match runtime**: `fg.read.match(EntityCls, Rule | AND RuleExpr,
  **port_constraints)` returns distinct entity snapshots selected by
  application-rule patterns.
- **Property-style assertion access**: field-scoped assertion records now
  support `snapshot.field("name").active`, `.history`, `.all`, and
  `snapshot.assertions.name`; legacy `.active()` / `.all()` call forms remain
  accepted.

### Changed

- **Public package namespace**: v0.2 releases the `factgraph` Python package
  surface. The old `kernel` package shape and `factpy-kernel` distribution name
  are not the v0.2 release target.
- **SDK hard-cut**: legacy candidate `accept` workflows, direct
  check/diagnose/why-not shells, and public candidate-set result teaching were
  removed from the v0.2 SDK path.
- **View scoping**: method-level `view=` remains intentionally unsupported;
  attach-time `FactGraph.attach(db, view=view)` is the shipped scope mechanism.

### Deferred

- Witness/assertion-returning match output, method-level `view=`, snapshot
  attach by `as_of(...)`, full EvidenceGraph Phase B, and adapter-consuming
  semantics beyond carrier-only public wrappers remain future tracks.

## [0.1.0-rc.1] - 2026-05-10

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

### Fixed

- `SDKStore.retract()` now wraps the underlying `WriteProtocolError` from
  `kernel.core.evidence.write_protocol` into `SDKStoreError`, with the
  original exception preserved as `__cause__`. Unknown assertion ids
  carry `code="ASSERTION_NOT_FOUND"`. The SDK-boundary error contract is
  now consistent across all write operations.

### Documentation

- **SDK docs cycle**: full audit + rewrite of `src/kernel/sdk/docs/`
  against source-of-truth code across all 8 files (00 user guide
  through 07 walker, plus README and the 03 rules/derivations
  canonical reference). Corrected fictional API claims, DTO field
  names, status vocabularies (`CheckStatus`, `OverlayCheckStatus`,
  `WhyNotStatus`, `ProofFrameStatus`), and helper-function imports
  (`fg.persist_*_annotations()`, `ensure_domain`, ViewSpec dict form).
- **Cross-doc consistency**: aligned `mode='python'` / `mode='engine'`
  rename framing across 00 + 03 + 04; expanded error-code coverage in
  00 from 3 to all 7 exported codes; clarified multi-head support
  semantics (registry + evaluate accept multi-head; constraint lives
  at capability shells `check / diagnose / why_not`).
- **EN-only migration of module docs**: deleted 5 Chinese halves of
  CN/EN pairs (application/01_overview, audit/01_overview,
  core/01_architecture, core/02_quality_assessment,
  core/03_progress_roadmap); translated 15 Chinese-only docs to
  English; fixed cross-link hygiene (absolute filesystem paths →
  relative paths; stale `.md` → `.en.md` references). The kernel now
  ships EN-only documentation across every module.
- **Translation drift audit**: restored temporal hedging in
  spike-status adapter docs (PyReason §5C.1 propagation /
  derived-head boundary observations, §5A.4 accept constraint;
  core/annotation §2 certainty-lane status) so that
  observed-up-to-here behaviors are not promoted to permanent design
  claims.
- **Top-level kernel landing**: added `src/kernel/README.md` as a
  human-facing module navigation page, paralleling the existing
  `AGENTS.md` for AI agent guidance.
- Translated 4 deprecation docstrings in `kernel.core.store.ledger`
  from Chinese to English (preserving deprecation semantics).

## Earlier History

Prior development took place across the v0.1.x application-first capability
sequence (Check, Diagnose, Fact Overlay, Why-not, Frontier Trace), the A+B
public surface (helpers + walker), the L Direction SDK shells (G1-G5), and
the post-L SDK ergonomics redesign. See git history and the milestone branches
on origin (`milestone/pre-v0.1-2026-04-27` through `milestone/post-l-2026-05-09`)
for the full progression.
