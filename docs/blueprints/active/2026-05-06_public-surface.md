# Public Surface Decision(Batch 8 of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Related Modules:
  - `src/kernel/sdk`
  - `src/kernel/application`
  - `src/kernel/audit`
  - `src/service`
  - `src/agent`
  - `scripts/project_release_surface.sh`
  - `scripts/release_surface_allowlist.txt`
  - `README.md` / `README.en.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md)
  - [2026-04-28_release-surface-cleanup.md](./2026-04-28_release-surface-cleanup.md)
  - [2026-04-28_v0.1-release-candidate.md](./2026-04-28_v0.1-release-candidate.md)
  - [src/kernel/application/docs/01_overview.md](../../../src/kernel/application/docs/01_overview.md)
  - [src/kernel/sdk/docs/04_api_surface.md](../../../src/kernel/sdk/docs/04_api_surface.md)
  - [src/kernel/audit/docs/01_overview.md](../../../src/kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-05-06_public-surface.audit.md](./2026-05-06_public-surface.audit.md)

## 1. Problem

Batch 0-7 have stabilized a large internal application/audit capability stack:

- application runtimes:Check,Diagnose,Fact Overlay,ProofFrame,Why-not,Rule Disable,Rule Literal Replace,Rule Add Condition;
- audit read/query surfaces:durable round events and ProofFrame diff;
- release projection tooling:kernel-only wheel/source projection,default-deny allowlist,and release-day no-publish gates.

The parent plan calls Batch 8 "Public Surface Decision":decide SDK shell,service routes,release projection allowlist updates,and README baseline after application protocol stabilizes. This name hides a false-merge risk. "Public surface" may mean at least four lifecycle-different decisions:

1. Python SDK facade convenience over application capabilities.
2. HTTP/service delivery routes.
3. Public source projection / allowlist changes.
4. Public README / docs / examples narrative.

Batch 8 must decide which,if any,graduate now. It must not assume every internal application or audit capability should become public just because the internal protocol is stable.

## 2. Goals

- Use Step 0 to decide whether Batch 8 ships a narrow public surface,only documents internal boundaries,or suspends public expansion.
- If a public surface ships,freeze exactly which capability/audit surfaces graduate and through which layer(SDK,service,docs,projection).
- Keep release branch invariants:`v0.1-oss-prep` and `master` remain untouched without explicit publish/merge authorization.
- Keep application-first authority:SDK/service may wrap application/audit behavior but must not create new runtime substrate.
- Keep public source projection default-deny and update the allowlist only if Step 0 proves a file belongs in the v0.1 public surface.
- Update current module docs if the public/current behavior changes.
- Produce a clear release-day checklist delta without publishing,tagging,or pushing a public repo.

## 3. Non-goals

- No PyPI upload,release tag,GitHub release,or public repository push.
- No merge/cherry-pick into `v0.1-oss-prep` or `master`.
- No SDK replay substrate or SDK-owned capability runtime.
- No service/agent runtime expansion unless Step 0 explicitly selects a service-delivery first slice.
- No public exposure of `agent`, `service`, `domains`, `memory`, `docs/blueprints`, `docs/references`, `third_party`, or internal tooling through release projection.
- No v1.0 stable API promise.
- No broad rewrite of `SDKStore`, `sdk.batch`, or `sdk.facade` god files.
- No new application protocol DTO shape unless Step 0 proves a public wrapper is blocked without it.
- No Batch 4 ProofFrame symmetric `rule_refs` hardening;that remains tracked separately.
- No Batch 6 Frontier/rule-action event family work.
- No Batch 7 L5 aggregation or single-frame diff method unless Step 0 proves Batch 8 is blocked without it.
- No publish-time archive of release blueprints;per release-surface cleanup,that waits until actual publish plus stability window.

## 4. Current Context

### 4.1 Public SDK surface today

`kernel.sdk.__all__` exports schema/DSL/store/registry/errors and authoring helpers. `SDKStore` already exposes read/write/query/derivation/evaluate/accept/audit package helpers,while the newer capability runtimes from Batches 3-7 remain application/audit layer only.

The SDK docs state:

- SDK owns Python product surface and outward compatibility.
- application owns canonical runtime authority.
- SDK docs must not turn application internal DTOs into SDK public API.

### 4.2 Application surface today

`kernel.application` exports the capability runtimes and protocol DTOs created in Batches 0-5c. Module docs explicitly say these are application-layer capabilities only and that SDK shells are future work.

### 4.3 Audit surface today

`kernel.audit` exposes package loading,round events,ProofFrame diff,and optional-domain ECSS convenience. Batch 6/7 behavior is query/recorder layer only;application runtimes do not import `kernel.audit`.

### 4.4 Release projection today

The existing release projection is kernel-only and default-deny:

- `scripts/project_release_surface.sh` writes a sanitized projection.
- `scripts/release_surface_allowlist.txt` controls public source files.
- no `examples/` or `samples/` in initial v0.1 projection.
- no `agent`, `service`, `domains`, `memory`, blueprints, references, or scripts in public projection.

### 4.5 Release branch invariant

Operational memory records `v0.1-oss-prep` and `master` as frozen. Batch 8 may prepare a decision and verification deltas, but may not mutate those branches or publish without explicit user instruction.

## 5. Step 0 Framing

Batch 8 starts in `draft` and must answer the falsifiers below before scope freeze.

### 5.1 Falsifiability Checklist

| # | Falsifier | If true |
|---|---|---|
| 1 | SDK shell over application capabilities would expose raw application DTOs or bind unstable protocol details as product API. | Path B suspend SDK shell;docs-only or application-only close-out. |
| 2 | SDK shell can be a thin ergonomic wrapper over stable DTOs/results without new runtime substrate. | Path A may include SDK shell for that subset. |
| 3 | Application capability set is too heterogeneous for one SDK method family(`check`, `diagnose`, overlay, rule actions, ProofFrame, Why-not, audit diff). | Split by capability family or ship no SDK shell. |
| 4 | Public service routes are a different delivery product from Python SDK and would require auth/session/HTTP DTO policy not present in the kernel-only release. | Service routes become Path C or deferred;do not bundle with SDK/docs. |
| 5 | Release projection allowlist cannot safely include new Batch 3-7 docs/examples without private-path/link scrub. | Keep projection unchanged or docs-only internal;no public projection update. |
| 6 | README baseline cannot show new capabilities without relying on internal application DTO ceremony that is too heavy for v0.1 onboarding. | Do not add README quickstart;maybe module docs only. |
| 7 | Existing `examples/11_capabilities_e2e_demo.ipynb` / `examples/12_evidence_diff_demo.py` are not projection-safe or SDK-friendly. | Keep examples out of projection;Batch 8 may document internal examples only. |
| 8 | Public-facing wrapper requires Batch 7 single-frame diff or L5 aggregation to be usable. | Either trigger that deferred work explicitly or suspend public diff surface. |
| 9 | Public-facing wrapper requires Batch 6 rule-action event families or Frontier events. | Defer or open a separate event-family blueprint;do not sneak into Batch 8. |
| 10 | Users can already import `kernel.application` / `kernel.audit` from the kernel package;the right public decision is to document these as advanced/internal-stable surfaces,not add SDK shell. | Path A docs-only first slice or Path B no code. |
| 11 | `kernel.application` should remain intentionally non-product public:importable but not advertised as stable public API. | Keep product docs on `kernel.sdk`;module docs can remain developer-facing. |
| 12 | Public surface decision requires changing release branch/projection repository state. | Stop;release-day workflow needs explicit user authorization outside Batch 8. |
| 13 | Batch 8 cannot finish without resolving the deferred Batch 4 ProofFrame `rule_refs` hardening. | Either scope a separate hardening first or explicitly keep it deferred and mark affected surfaces internal. |
| 14 | A narrow docs/release-checklist update gives more value than code because v0.1 public API should stay small. | Path A docs/projection/checklist only;no SDK/service code. |
| 15 | Batch 8 has no concrete user-facing value beyond saying "everything stays internal." | Path B close-out is valid;record the no-expand decision and final routemap status. |
| 16 | Public surface changes would require updating `pyproject.toml` package scope or adding new dependencies. | Treat as a hard blocker unless Step 0 records a release-surface amendment. |
| 17 | Public docs can describe application/audit capabilities without expanding `kernel.sdk.__all__` or release projection. | Path A docs-only first slice is viable. |
| 18 | SDK shell can cover only one narrow high-value family(e.g. `SDKStore.check(...)` + `diagnose(...)`) without exposing all Batches 3-7. | Path A may ship that family and defer the rest. |

### 5.2 Candidate Paths

**Path A — Narrow public-surface update.**

Ship a first slice selected by Step 0. Candidate sub-shapes:

- A1 docs/checklist only:document application/audit surfaces and release-day constraints,no code.
- A2 SDK shell for one narrow family,with application as runtime authority.
- A3 projection/docs update,possibly adding selected docs/examples after scrub.
- A4 public release checklist update only,no runtime/API change.

**Path B — Suspend public expansion.**

Record that Batch 8's correct decision is no new public surface before real user feedback or release-day need. This is a valid routemap close-out,not a failure.

**Path C — Split into child blueprints.**

Use if SDK shell,service routes,projection/docs,and release checklist need independent implementation lifecycles. Path C must not implement multiple public surfaces in one blueprint.

### 5.3 Step 0 Source Pass Requirements

Step 0.A must read and cite concrete evidence from:

- `src/kernel/sdk/__init__.py` and `src/kernel/sdk/docs/04_api_surface.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/audit/docs/01_overview.md` and `03_audit_package_contract.md`
- `scripts/release_surface_allowlist.txt` and `scripts/project_release_surface.sh`
- `docs/blueprints/active/2026-04-28_release-surface-cleanup.md`
- `docs/blueprints/active/2026-04-28_v0.1-release-candidate.md`
- `docs/architecture_principles.md`

Step 0.B,if Step 0.A selects Path A,freezes:

- exact public surface family;
- exact files allowed to change;
- API/method names and return shapes if code ships;
- release projection allowlist/docs changes if any;
- tests/drift gates;
- release-day checklist deltas;
- explicit deferrals and reactivation triggers.

### 5.4 Step 0.A Spike — Source-Grounded Falsifier Answers

Step 0.A read the required sources in §5.3 plus the Batch 6/7 archives. The key source facts:

- `src/kernel/sdk/__init__.py` and SDK docs expose the product surface as schema/DSL/store/registry/errors and existing `SDKStore` facade methods. They do not expose Batches 3-7 capability shells.
- `src/kernel/application/__init__.py` exports the new capability runtimes directly:Check,Diagnose,Fact Overlay,ProofFrame,Why-not,Rule Disable,Rule Literal Replace,and Rule Add Condition.
- `src/kernel/audit/__init__.py` exports round persistence and ProofFrame diff surfaces directly.
- `README.md` / `README.en.md` already explain Layer 1(`kernel.sdk`),Layer 2(`kernel.application`),and audit package reading;they do not expose every Batch 3-7 flow as a quickstart.
- `scripts/release_surface_allowlist.txt` excludes `examples/` and `samples/`;release-surface cleanup kept the public source projection kernel-only and default-deny.

| # | Verdict | Source-grounded answer | Consequence |
|---|---|---|---|
| 1 | TRUE | A naive SDK shell over all application capabilities would either expose application DTOs(`CheckRequest`, `ProofFrameRecheckRequest`, rule-action request/result DTOs)or require a new SDK lowering layer. SDK docs explicitly say not to turn application internals into SDK public API. | No broad SDK shell. |
| 2 | PARTIAL | Thin delegates are plausible for a subset,but not for the whole capability set. Existing SDK already delegates query/ingest/derivation paths;new Batch 3-7 wrappers would need per-family outward shapes. | Step 0.B may consider a future narrow SDK family,but not as Batch 8 first slice. |
| 3 | TRUE | The capability set is structurally heterogeneous:status-only check,localized diagnose,overlay before/after/diff,ProofFrame atom verdicts,rule-action variant rows plus nested ProofFrame,Why-not boards,and audit diffs. | One SDK method family would be false merge. |
| 4 | TRUE | Service routes would need transport DTO,auth/session/error policy,and are not part of the kernel-only release surface. `service` is excluded from the projection. | No service route in first slice. |
| 5 | TRUE | Projection allowlist excludes examples/samples and private docs;adding Batch 3-7 examples/docs to public source requires link/path scrub. | Projection change only if Step 0.B scopes exact docs and gates. |
| 6 | TRUE | README quickstart is intentionally SDK-basic;application capability DTO ceremony would be too heavy for the top-level onboarding flow. | Do not add a broad README quickstart for Batches 3-7. |
| 7 | TRUE | `examples/` is not in `release_surface_allowlist.txt`;Batch 7 demo is kernel-level but not projection-safe by policy until explicitly scrubbed. | Keep examples out of public projection in first slice. |
| 8 | FALSE | Public documentation of current audit diff does not require single-frame diff or L5 aggregation;Batch 7 documented both as deferred. | No trigger for Batch 7 deferred work. |
| 9 | FALSE | Public documentation of current surfaces can state Frontier/rule-action event families are deferred. | No trigger for Batch 6 deferred event families. |
| 10 | TRUE | `kernel.application` and `kernel.audit` are already importable from the kernel package and documented as Layer 2 / audit surfaces. | A docs/checklist first slice is useful without SDK shell. |
| 11 | TRUE | SDK docs define `kernel.sdk` as product surface and application as runtime authority. Application should be advertised as advanced/wire/automation layer,not general ergonomic API. | Keep product docs centered on SDK;document application as advanced. |
| 12 | FALSE | Batch 8 can update internal docs/checklists without mutating `v0.1-oss-prep`, `master`,or public projection repo. | No release branch action in Batch 8. |
| 13 | FALSE | Batch 4 ProofFrame `rule_refs` hardening remains tracked,but Batch 7 diff handles RuleRef-degenerate frames with a marker. Public docs can keep that caveat. | Do not bundle Batch 4 hardening. |
| 14 | TRUE | The highest-confidence value is finalizing what is public vs advanced/internal and updating release-day checklist/docs. | Prefer docs/checklist first slice. |
| 15 | FALSE | There is concrete user-facing value in a no-new-code decision:it prevents accidental SDK bloat and makes v0.1 public boundary explicit after Batches 0-7. | Path B no-expand alone is not necessary. |
| 16 | FALSE | Docs/checklist first slice does not require `pyproject.toml` scope or dependency changes. | Keep packaging unchanged. |
| 17 | TRUE | README and module docs can describe application/audit as advanced surfaces without expanding `kernel.sdk.__all__` or allowlisting examples. | Path A docs-only is viable. |
| 18 | PARTIAL | A narrow SDK shell for Check/Diagnose could be designed later,but source evidence does not prove it is needed for v0.1 public close-out. | Defer SDK shell with concrete reactivation trigger. |

#### 5.4.1 Decision

Select **Path A,first slice A1 + A4 only:public boundary docs + release-day checklist update,no SDK/service code and no release projection expansion by default**.

This is not Path B because Batch 8 still has a concrete close-out product:it records the final v0.1 public/advanced/internal boundary after the round-story implementation. It is not Path C because the code-bearing public surfaces(SDK shell,service routes,projection example add-back)are all deferred rather than partially implemented under this batch.

#### 5.4.2 Frozen Constraints For Step 0.B

1. No SDK code change in Batch 8 unless Step 0.B finds a docs/checklist outcome impossible without one.
2. No service/agent code change.
3. No application/audit runtime protocol change.
4. No `pyproject.toml` package-scope/dependency change.
5. No release branch,public repo,publish,or tag action.
6. Public source projection stays default-deny;allowlist changes require explicit Step 0.B file list and link-scrub gates.
7. README top-level quickstart remains SDK-basic;Batch 3-7 capability examples do not become the first quickstart.
8. `kernel.application` may be documented as advanced runtime authority for automation/wire callers,not as ergonomic product surface.
9. `kernel.audit` may be documented as offline audit/query surface,including round events and ProofFrame diff.
10. SDK shell for Check/Diagnose/rule actions/ProofFrame remains deferred unless a future user-facing workflow proves the need.
11. Service route exposure remains deferred to a separate delivery/auth blueprint.

#### 5.4.3 Remaining Step 0.B Carry-Overs

- Exact docs to change:README only,module docs only,release checklist only,or a combination.
- Whether `scripts/release_surface_allowlist.txt` changes at all. Default expectation:no allowlist expansion.
- Whether to add a release-day checklist section to the release-surface or RC blueprint,or only to this Batch 8 archive outcome.
- Exact wording for the public boundary tiers:`product public`, `advanced importable`, `internal/deferred`.
- Whether application/audit module docs need public-facing caveat labels.
- Drift gates:static checks for no SDK/service/agent/application runtime/protocol drift,projection link scrub if docs touched,and README quickstart unchanged if not intentionally edited.
- Reactivation triggers for SDK shell,service routes,example projection add-back,and Batch 4 `rule_refs` hardening.

## 6. Boundaries And Invariants

- `v0.1-oss-prep` and `master` are frozen;Batch 8 does not touch them.
- No publish,upload,tag,or public repo push.
- SDK wrappers must be thin delegates over application/audit;no SDK substrate.
- `kernel.application` must not import `kernel.sdk`.
- application runtimes must not import `kernel.audit`.
- service/agent production runtime must not add SDK runtime imports unless Step 0 explicitly chooses a service slice and records why.
- release projection remains default-deny.
- public docs must not link to excluded private paths.
- old SDK public API remains byte-stable unless Step 0 records a deliberate public API change.
- old `AuditQuery` and application capability methods remain byte-stable unless Step 0 records a deliberate public API change.

## 7. Acceptance

- [x] Step 0.A answers all 18 falsifiers with source-grounded evidence(see §5.4).
- [x] Step 0.A selects Path A/B/C and records why alternatives were rejected(see §5.4.1).
- [ ] Step 0.B freezes exact public surface scope before implementation,if any.
- [ ] No release branch,tag,publish,or public repo push occurs.
- [ ] No SDK/service/agent/application/audit drift outside the scoped files.
- [ ] If SDK changes ship,tests prove wrappers are thin delegates and do not expose raw application internals accidentally.
- [ ] If projection/docs changes ship,projection script and link scrub gates pass.
- [ ] If no code ships,the no-expand decision is recorded as an explicit outcome,not an omission.
- [ ] Module docs and release/checklist docs are synchronized with the final decision.

## 8. Implementation Plan

1. Draft this blueprint and audit log.
2. Step 0.A:source-grounded falsifiability pass over SDK/application/audit/release docs and current code.
3. Step 0.B:freeze selected public-surface first slice or record Path B suspension.
4. Scope transition:`draft` -> `scoped` only after Step 0.B.
5. Implement only the scoped slice.
6. Run focused tests,projection/link gates if touched,and full relevant kernel tests.
7. Update module docs / release checklist / README according to the selected slice.
8. Fill Outcome / Deviations,mark implemented,and archive.

## 9. Docs To Update

Potentially,depending on Step 0:

- `src/kernel/sdk/docs/*`
- `src/kernel/application/docs/*`
- `src/kernel/audit/docs/*`
- `README.md` / `README.en.md`
- `docs/architecture_principles.md`
- `docs/blueprints/active/2026-05-05_round-story-completion-plan.md`
- release-surface / release-candidate blueprints if release-day checklist changes materially

## 10. Outcome / Deviations

To be filled after implementation.
