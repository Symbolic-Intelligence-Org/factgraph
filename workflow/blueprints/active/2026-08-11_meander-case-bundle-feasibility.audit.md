# Task Blueprint Audit: Meander CaseBundle F-GATE 离线可行性验证

- Status: draft
- Created: 2026-08-11
- Last Updated: 2026-08-11
- Authority: paired blueprint audit log；记录 sibling blueprint 的状态、审阅、范围变化和实施事件，不替代独立 preflight，也不授权下一状态或实验执行。
- Inputs:
  - Sibling blueprint [`2026-08-11_meander-case-bundle-feasibility.md`](./2026-08-11_meander-case-bundle-feasibility.md)
  - Adopted Q1 decision [`2026-08-11_q1-offline-feasibility-before-external-validation-decision.md`](../../design/decisions/active/2026-08-11_q1-offline-feasibility-before-external-validation-decision.md)
  - 2026-08-11 user authorization to execute the next stage；在执行前的公开边界说明中，该阶段被限定为起草 blueprint pair、独立审阅与目标文件限定提交；未授权 preflight、case/harness、experiment execution 或状态推进
- Outputs / Downstream:
  - Chronological evidence for a future separately authorized preflight, scope-freeze, implementation, and archive decision
- Related:
  - [`workflow/blueprints/README.md`](../README.md)
  - [`workflow/CADENCE.md`](../../CADENCE.md)
- Blueprint: [`2026-08-11_meander-case-bundle-feasibility.md`](./2026-08-11_meander-case-bundle-feasibility.md)
- Branch: `v0.3.0-blueprint-meander-case-bundle-feasibility-2026-08-11`

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-11 | draft | Blueprint pair created | Seeded from the canonical task-blueprint and paired-audit templates, then manually completed to the repository's required seven-field metadata schema. No case construction, harness code, model use, product-source change, preflight, or state advance authorized. |
| 2026-08-11 | draft | Independent blueprint review authorized | The same bounded next-stage authorization was publicly stated to include paired independent review and a target-file-only commit. This is recorded separately from creation and does not authorize independent preflight or any later lifecycle transition. |
| 2026-08-11 | draft | Q1 authority boundary imported | Preserved one non-renewable `F-GATE-CB0`, open `P-GATE`, `STOP-except-discovery`, separate review/preflight/execution authorization, and no automatic successor. |
| 2026-08-11 | draft | Read-only shipped substrate audit recorded | `RuleProgram` is the proposed benchmark substrate; target Policy/Plan/SourceRecord/Translator/UI remain absent/deferred. Capability attribution and four replay subcontracts remain explicit gates. |
| 2026-08-11 | draft | Experiment protocol drafted | Proposed 32-instance sparse corpus, role-separated gold, separately sealed input/gold, strong semantic-reference baseline, exact thresholds, one frozen holdout run batch, and fixed numeric cap. All numbers remain subject to explicit scope-freeze approval. |
| 2026-08-11 | draft | Missing adoption-review source preserved | User turn `019ff082-3edb-78f2-b045-ee89db181deb`, item `item-1051`, references three non-blocking carry-forwards without enumerating them. Added `OBL-REVIEW-01..03`; no content was invented; exact upstream text/mapping is required before `scoped`. |
| 2026-08-11 | draft | Environment discrepancy recorded and narrowed | Bare/root `/Users/zhenzhili/miniforge3/bin/python` 3.10.11 exits `139` without pytest output. The explicit `factpy` Python 3.10.20 command recorded in blueprint §4.5 passes 14 focused tests in `0.61s`; two ad-hoc probes also observe stable normalized RuleProgram artifacts. Dependency/command pinning and clean-checkout reproduction remain `ENV-01`; this is not classified as a product-code failure. |
| 2026-08-11 | draft | Unrelated dirty state baselined | Before task-file staging, the unrelated worktree baseline was 112 porcelain-v1 lines with SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`; index was empty. `master` was `854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0`; no local/remote `v0.1-oss-prep` ref existed, so no claim is made that such a ref was verified unchanged. |
| 2026-08-11 | draft | Three-way independent draft review completed | Governance/corpus, experimental-protocol, and shipped-repository reviews were performed without edits. Findings were applied to the sibling blueprint or retained below as explicit pre-scoped gates; no preflight or experiment ran. |
| 2026-08-11 | draft | Three-way closure review reached `CLEAR` | Each reviewer re-read the amended pair. No draft-contract blocker remains; operational assignments, exact missing carry-forwards, independent preflight, scope authorization, and execution authorization remain open and were not mistaken for closure. |

## Decision Notes

### 2026-08-11 — Why `RuleProgram` is only a substrate

The shipped surface can select clauses, evaluate a closed goal read-only, carry premise scope, and expose captured native digest/evidence components with the portable-identity shape limits recorded in the blueprint. It does not establish the proposed Policy/Plan/Scenario contracts or a complete external-source registry. The blueprint therefore forbids renaming the substrate into the target product and requires output attribution.

### 2026-08-11 — Why the reference arm must be strong

`A-REFERENCE` receives the same normalized facts, declared business/rule semantics, and positive/refuting mapping, but no per-case gold. FactGraph is expected to equal it on logic. The experiment looks for native evidence/replay increment, not an accuracy victory manufactured by omitting conditions from the baseline.

### 2026-08-11 — Why holdout input and gold are sealed separately

Hiding only gold still permits case-specific tuning. Hiding only input but exposing gold-derived coverage/scorable fields leaks labels. Arms see only `observed_input.json` and the non-label public allowlist; expected status, coverage, exclusions, outcome counts, and metamorphic relations remain in sealed gold. The RunCustodian executes the primary and entire pre-registered replay/mutation suite, seals every output, and only then exposes gold to scoring.

### 2026-08-11 — Why replay has two identities

Native FactGraph digests include workspace, transaction, assertion, and in one path hash-order-sensitive scope shapes. Exact-artifact replay therefore reopens the same captured workspace under the pinned environment. Portable reconstruction builds a new workspace and compares a benchmark-owned semantic fingerprint keyed by stable `benchmark_fact_id`; it does not pretend random native IDs are portable identity.

### 2026-08-11 — Why overall `PARTIAL` is disabled

Allowing an absent optional arm to turn an otherwise valid mandatory result into `PARTIAL`, while also allowing `PASS`, was contradictory. `F-GATE-CB0` now derives overall status only from mandatory dimensions: all pass, any fail, or unresolved validity. Optional arms keep their own `N/A`/`UNRESOLVED`; `PARTIAL` is only a pre-registered optional-subdimension label.

### 2026-08-11 — Why no standalone experiment-audit subtype is added

`workflow/audit/README.md` currently permits only `vs-shipped`, `preflight`, and `synthesis`. This slice uses a standard preflight plus the paired blueprint audit and tracked benchmark report. Adding an “experiment report” audit subtype would itself require a separate governance decision.

## Open Gates Before `scoped`

| Gate | State | Required closure evidence |
| --- | --- | --- |
| `OBL-REVIEW-01..03` | `OPEN` | Exact original text, source path/message, date, and mapping to blueprint clauses |
| `BUDGET-01` | `OPEN` | Explicit acceptance or revision of §5.2 cumulative caps |
| `CUSTODY-01` | `OPEN` | Named ProtocolOwner, CaseAuthor, two independent GoldAuthors, adjudicator/GoldCustodian, ImplementationSide, RunCustodian/Scorer, FinalAuditor; enforced incompatibility matrix; two durable sealed locations, attestation, access mechanism, retention/release policy |
| `CORPUS-01` | `OPEN` | Acceptance of 16 families / 32 instances, one invariant per class, single-variable pairs, sealed non-vacuity counts/denominators, locator restriction, and double-annotation gold contract |
| `ARMS-01` | `OPEN` | Mandatory/conditional arm list, actual equally capped reference instrumentation attempt, applicability decision, primary/replay operation counts, and parity contract frozen |
| `ENV-01` | `OPEN` | Pinned interpreter/dependencies, exact commands, clean-checkout smoke, and resolution of the exit-139 discrepancy |
| `CASE-CODEC-01` | `OPEN` | Single canonical fact truth source, benchmark RuleProgram codec, schema coordinate, canonical encoding, and benchmark/native assertion-ID mapping frozen |
| `PATHS-01` | `OPEN` | Durable path/ignore checks plus real write-once run IDs, content-addressed naming, atomic completion, custodian permissions, and pre-gold seal mechanism |
| `PREFLIGHT-01` | `OPEN` | Separately authorized independent preflight branch, full-file re-read, hash-seed probe, amendment/diff-check, and self-check complete before scoped |
| `AUTH-01` | `OPEN` | After preflight and all other gates close, separate explicit user authorization for `draft → scoped`; execution authorization remains later and separate |

## Review Findings

| ID | Review | Severity | Finding | Disposition in this draft |
| --- | --- | --- | --- | --- |
| `GOV-01` | governance | required | Drafting/review authorization wording conflicted between the pair. | `APPLIED`: both Inputs now carry the same bounded authorization; creation and review events are separate. |
| `GOV-02` | governance + repo | required | Preflight was placed after `scoped`, contrary to CADENCE; lifecycle omitted `implementing/implemented`. | `APPLIED`: header, Mermaid, acceptance gates, and §8 now use review → separately authorized preflight → amendment/self-check → scoped authorization → execution authorization → implementing → implemented/archive. |
| `LEAKAGE-01` | protocol + repo | blocker/P1 | Arm-visible matrix/input exposed expected coverage or scorable labels. | `APPLIED`: explicit public allowlist and `observed_input.json`; all expected/gold-derived fields and outcome counts are sealed. |
| `DENOM-01` | protocol | blocker | Scorable balance and metric denominators could yield vacuous `100%`. | `APPLIED`: sealed status minima, `n >= 12`, per-metric exact denominators, no post-run exclusions, and invalid-denominator `UNRESOLVED`. Operational acceptance remains `CORPUS-01`. |
| `REPLAY-01` | protocol + governance + repo | blocker/P1 | “One invocation” conflicted with re-execution, and replay followed gold unseal. | `APPLIED`: one primary plus exact pre-registered non-primary replay-verification operations in one frozen pre-unseal batch; exact counts/operators are stated. |
| `ID-NORM-01` | protocol + repo | required/P1 | UUID/hash/workspace-bound native IDs and digests were treated as portable reconstruction identity. | `APPLIED`: exact-artifact and portable semantic fingerprints split; benchmark IDs/mapping and preflight hash-seed probe required. |
| `REFERENCE-01` | protocol | required | Increment depended on a hypothetical rather than executed reference instrumentation cost. | `APPLIED`: equally capped real attempt and actual code/time/output evidence required; otherwise increment `UNRESOLVED`. |
| `CORPUS-INVARIANT-01` | protocol | required | Eight umbrella classes contained multiple mechanisms that 32 sparse cases could not attribute. | `APPLIED`: one required invariant per class; other stressors and uninstantiated umbrellas stay explicit/`UNRESOLVED`. |
| `GOLD-01` | protocol | required | One undifferentiated GoldSide could not create genuine disagreement evidence, and a runner could not inspect hidden counts before unseal. | `APPLIED`: two blind independent holdout labels, third adjudication or `UNSCORABLE`, dev spot-check, immutable post-unseal gold, GoldCustodian-only count attestation, and post-unseal verification. Operational roles remain `CUSTODY-01`. |
| `LOCATOR-01` | protocol | required | PDF/character/DB locators lacked a common canonicalization contract. | `APPLIED`: v0 restricted to UTF-8 byte offsets and RFC 6901 pointers; native support and external mapping score separately. |
| `VERDICT-01` | protocol + governance | required | Budget overrun and optional unresolved dimensions allowed contradictory overall dispositions. | `APPLIED`: mandatory/optional truth table, actual-overrun `FAIL`, missing-ledger `UNRESOLVED`, no overall `PARTIAL`. |
| `LLM-01` | protocol | recommended | Optional LLM task, retry, timeout, and provider-error behavior were underdefined. | `APPLIED`: same normalized task plus frozen generation/error/retry contract; no post-inspection rerun. |
| `SOURCE-CONTROL-01` | protocol | recommended | `A-SOURCE` was called mandatory/scored despite emitting no verdict. | `APPLIED`: mandatory non-scored control artifact, excluded from automated denominators. |
| `CONFUSION-01` | protocol | recommended | False support/challenge and silent gap lacked exact definitions; “material” created discretion. | `APPLIED`: exact confusion rules; materiality exemption removed. |
| `BUDGET-LEDGER-01` | protocol | recommended | Numeric cap lacked auditable counting/allocation rules and could double-count supervised agent time. | `APPLIED`: labor is non-overlapping human/operator minutes ÷ 60; agent wall time and compute are separate; tracked allocation/reserve rules remain subject to `BUDGET-01`. |
| `ROLE-01` | protocol | required | No role owned hidden case/rule construction, and final audit independence was ambiguous. | `APPLIED`: CaseAuthor, GoldCustodian, and incompatible FinalAuditor roles plus overlap limits are explicit; operational assignment remains `CUSTODY-01`. |
| `OP-MANIFEST-01` | protocol | required | Replay patches/operators and expected relations could be read as one sealed package. | `APPLIED`: run-visible operation manifest and gold-only replay-expectation manifest are independently digested and separated. |
| `CASE-CODEC-01` | repo | recommended | Fact payload had two truth sources and RuleProgram serialization was undecided. | `GATED`: blueprint selects a single referenced fact file and benchmark-owned codec shape; exact codec/schema/mapping must freeze before scoped. |
| `PATHS-WRITEONCE-01` | repo | recommended | Tracked Git files are not inherently append-only. | `GATED`: actual no-overwrite/content-addressed/atomic/custodian/seal mechanism required by `PATHS-01`. |
| `CITE-01` | repo | recommended | Several shipped claims/ranges overstated identity, immutability, or method coverage. | `APPLIED`: §4.2 states shape limits and uses corrected full ranges/terminology. |
| `SUCCESSOR-01` | governance | recommended | Successor guard omitted immutable `PARTIAL`, parent/diff, and renewed P-GATE choice. | `APPLIED`: §7.4 adds all conditions without authorizing a successor. |
| `DIRTY-01` | governance | recommended | Dirty-worktree preservation needed a recorded baseline. | `APPLIED`: exact unrelated status count/hash and sacred-ref observations recorded above; only this pair may be staged. |
| `TEMPLATE-DRIFT-01` | governance | repository drift | Canonical blueprint templates themselves omit fields required by the seven-field schema. | `OUT OF SCOPE`: this pair conforms manually; template repair requires its own governed slice and is not folded into F-GATE. |

All draft-review blocker/required findings are now represented in the blueprint contract. This does **not** close operational gates, replace the required independent preflight, or authorize `scoped`.

## Deviations

None at creation. The blueprint is still `draft`; proposed numbers and paths are not yet scope-frozen.
