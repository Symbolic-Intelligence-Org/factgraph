# Task Blueprint Audit: Meander CaseBundle F-GATE 离线可行性验证

- Status: draft
- Created: 2026-08-11
- Last Updated: 2026-08-11
- Authority: paired blueprint audit log；记录 sibling blueprint 的状态、审阅、范围变化和实施事件，不替代独立 preflight，也不授权下一状态或实验执行。
- Inputs:
  - Sibling blueprint [`2026-08-11_meander-case-bundle-feasibility.md`](./2026-08-11_meander-case-bundle-feasibility.md)
  - Adopted Q1 decision [`2026-08-11_q1-offline-feasibility-before-external-validation-decision.md`](../../design/decisions/active/2026-08-11_q1-offline-feasibility-before-external-validation-decision.md)
  - 2026-08-11 user authorization to execute the next stage；在执行前的公开边界说明中，该阶段被限定为起草 blueprint pair、独立审阅与目标文件限定提交；未授权 preflight、case/harness、experiment execution 或状态推进
  - Later 2026-08-11 authorization for Step 4.3 independent preflight only；no `scoped`、case/harness、holdout or experiment authority
  - Fixed independent preflight object: commit `04ad3c722f14e67ab6370d228aa8ee010ea4d9ff`、path `workflow/audit/active/2026-08-11_meander-case-bundle-feasibility-preflight.md`、blob `2e5d5c7361659cc3d53526843de0bf66cb0d51a8`、content SHA-256 `7ab6b6113d501f5dffae8e374f109d061a76b954de51a96ea861e699e502f7d5`、35,151 bytes / 327 lines；branch-local until content-identical Step 4.9 import/archive
  - 2026-08-11 authorization for Step 4.4 amendment、independent diff review and target-pair-only commit；explicitly excludes Step 4.5 self-check、state advance、case/harness、credentials、experiment and product source
  - 2026-08-11 authorization for Step 4.5 full-pair self-check、independent second opinions and a target-pair-only tightening commit only if the self-check finds one necessary；explicitly excludes state advance、case/harness、credentials、experiment and product source
  - 2026-08-11 user-supplied `OBL-REVIEW-01..03` recovery/closure package；authorizes durable transcription of exact wording、source chain、clause mappings、two carry-forwards and custody/environment sequencing guards in this pair only；does not close another gate or authorize state advance、case/harness、credentials、experiment or product source
- Outputs / Downstream:
  - Chronological evidence for the completed fixed preflight、Step 4.4 amendment、completed Step 4.5 self-check and any separately authorized scope-freeze、implementation or archive decision
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
| 2026-08-11 | draft | Environment discrepancy recorded and narrowed | Bare/root `/Users/zhenzhili/miniforge3/bin/python` 3.10.11 exits `139` without pytest output. The explicit `factpy` Python 3.10.20 command recorded in blueprint §4.5 passes 14 focused tests in `0.61s`; two ad-hoc probes also observe stable normalized RuleProgram artifacts. Root cause remains unattributed among interpreter/runtime、native dependency/ABI and project source. The passing `factpy` run is differential evidence only and does not close `ENV-01`. |
| 2026-08-11 | draft | Unrelated dirty state baselined | Before task-file staging, the unrelated worktree baseline was 112 porcelain-v1 lines with SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`; index was empty. `master` was `854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0`; no local/remote `v0.1-oss-prep` ref existed, so no claim is made that such a ref was verified unchanged. |
| 2026-08-11 | draft | Three-way independent draft review completed | Governance/corpus, experimental-protocol, and shipped-repository reviews were performed without edits. Findings were applied to the sibling blueprint or retained below as explicit pre-scoped gates; no preflight or experiment ran. |
| 2026-08-11 | draft | Three-way closure review reached `CLEAR` | Each reviewer re-read the amended pair. No draft-contract blocker remains; operational assignments, exact missing carry-forwards, independent preflight, scope authorization, and execution authorization remain open and were not mistaken for closure. |
| 2026-08-11 | draft | Independent Step 4.3 preflight separately authorized and completed | The branch-local artifact at fixed commit/blob above returned `AMEND REQUIRED` with 4 Required、2 Recommended、3 Verified、2 Scoped-detail and 0 abandonment blockers. It changed no blueprint、case、harness、holdout、credential or product source. |
| 2026-08-11 | draft | Fixed preflight object consumed for Step 4.4 | This amendment reads the exact commit/blob/SHA, not the floating preflight branch tip. The artifact remains branch-local until content-identical Step 4.9 import/archive. |
| 2026-08-11 | draft | Adoption-review source remained unavailable | Preflight independently rechecked recoverable history and still found only the adoption reference. `OBL-REVIEW-01..03` remain `OPEN`; PF findings and Q1 duties do not replace them. |
| 2026-08-11 | draft | Step 4.4 amendment drafted | PF-R01..PF-R04、PF-Rec01..02 and PF-S02 guard were mapped into the sibling blueprint. Independent diff-check and Step 4.5 self-check remain separately visible；no state advance or implementation is authorized. |
| 2026-08-11 | draft | Step 4.4 amendment and independent diff review completed | Runtime/SDK、repository/codec、failure/custody and governance/product-boundary reviewers independently reached `CLEAR` after all residuals were corrected. Step 4.5 self-check、every operational gate、state advance and implementation remain pending and unauthorized. |
| 2026-08-11 | draft | Step 4.5 self-check completed with one tightening | Full-pair review found `SC45-01`: singular bundle-level evidence/support refs conflicted with ordered dual-goal ownership. The aliases were removed, each `GoalCallRaw` became its side's sole artifact owner, and independent technical/governance rechecks returned `CLEAR`. `PREFLIGHT-01` closes；all other operational gates、state advance and implementation remain pending and unauthorized. |
| 2026-08-11 | draft | Session-only adoption obligations recovered | The user supplied the exact “Q1 采纳评估” source description、verbatim three-item list and durable upstream anchors. §4.4 now closes `OBL-REVIEW-01..03` as a provenance/mapping gate while preserving wrong-source and real-workflow-cascade carry-forwards and reviewer legibility as `UNRESOLVED`. Custody staffing feasibility is ordered before budget/corpus/arm acceptance，and exit `139` now requires root-cause closure. No experiment、other gate or lifecycle state is authorized. |

## Decision Notes

### 2026-08-11 — Why `RuleProgram` is only a substrate

The shipped surface can select clauses, evaluate a closed goal read-only, carry premise scope, and expose captured native digest/evidence components with the portable-identity shape limits recorded in the blueprint. It does not establish the proposed Policy/Plan/Scenario contracts or a complete external-source registry. The blueprint therefore forbids renaming the substrate into the target product and requires output attribution.

### 2026-08-11 — Why the reference arm must be strong

`A-REFERENCE` receives the same normalized facts, declared business/rule semantics, and positive/refuting mapping, but no per-case gold. FactGraph is expected to equal it on logic. The experiment looks for native evidence/replay increment, not an accuracy victory manufactured by omitting conditions from the baseline. An executed/frozen semantically invalid or intentionally weakened reference fails the mandatory control；a `NOT_RUN` or telemetry-incomplete reference leaves the comparison and overall envelope `UNRESOLVED` absent another failure.

### 2026-08-11 — Why holdout input and gold are sealed separately

Hiding only gold still permits case-specific tuning. Hiding only input but exposing gold-derived coverage/scorable fields leaks labels. Arms see only `observed_input.json` and the non-label public allowlist; expected status, coverage, exclusions, outcome counts, and metamorphic relations remain in sealed gold. The RunCustodian executes the primary and entire pre-registered replay/mutation suite, seals every output, and only then exposes gold to scoring.

### 2026-08-11 — Why replay has two identities

Native FactGraph digests include workspace, transaction, assertion, and in one path hash-order-sensitive scope shapes. Exact-artifact replay therefore opens separately verified byte-identical disposable copies of one clean-closed retained base under the pinned environment；it never opens or mutates the retained base itself. Portable reconstruction builds a new workspace from portable inputs only and compares a benchmark-owned semantic fingerprint keyed by stable `benchmark_fact_id`; it does not pretend random native IDs are portable identity.

### 2026-08-11 — Why overall `PARTIAL` is disabled

Allowing an absent optional arm to turn an otherwise valid mandatory result into `PARTIAL`, while also allowing `PASS`, was contradictory. `F-GATE-CB0` now derives overall status only from mandatory dimensions: all pass, any fail, or unresolved validity. Optional arms keep their own `N/A`/`UNRESOLVED`; `PARTIAL` is only a pre-registered optional-subdimension label.

### 2026-08-11 — Why no standalone experiment-audit subtype is added

`workflow/audit/README.md` currently permits only `vs-shipped`, `preflight`, and `synthesis`. This slice uses a standard preflight plus the paired blueprint audit and tracked benchmark report. Adding an “experiment report” audit subtype would itself require a separate governance decision.

### 2026-08-11 — Why Step 4.4 consumes a fixed preflight object

The preflight is branch-local by workflow design. Commit `04ad3c...`、blob `2e5d5c...` and content SHA-256 `7ab6b6...` are the authoritative amendment input；a floating branch tip is not. The exact bytes are imported only with Step 4.9 archive, preventing later branch movement from changing the review evidence.

### 2026-08-11 — Why CB0 freezes a strict profile and a dual-goal bundle

The public `RuleProgram` DTO admits shapes broader than this evidence/replay experiment can safely score. CB0 therefore uses application-Rule bodies、acyclic positive derived dependencies、no negation/aggregate/membership/builtin/RuleRef atoms、no program facts or produced-head collisions and an exactly typed scalar/comparison domain with no coercion. One case is explicitly two goal calls with separately captured errors/evidence；a one-sided exception can no longer masquerade as non-entailment. A neutral semantics manifest and parity mapping include primitive truth and operand types, letting the reference arm implement the same conditions without calling FactGraph.

### 2026-08-11 — Why portable evidence needs two codecs

Native EvidenceGraph and recursive support steps carry different structures and workspace-bound identities. The benchmark owns canonical program/scope/source/evidence/support identities；FactGraph owns the raw evaluation、evidence、support and workspace substrate. A total tagged witness mapping fails before verdict consumption, and portable support claims require the separate normalized support DAG rather than treating EvidenceGraph as the proof topology. Each ordered `GoalCallRaw` is the sole owner of its side's evidence/support references；the bundle has no singular alias or second fact source. Exact and portable comparison projections retain an ordered positive/refuting payload with each side's Boolean/error/evidence/support；execution-instance IDs、paths and timing are excluded explicitly, never an entire goal. Fingerprints consume sealed `ArmRawBundleV0` only；downstream `ScoredBundleV0` references those fingerprints and cannot feed replay/candidate/overall results back into their own identity.

### 2026-08-11 — Why corpus-local increment is a binary cap-bound comparison

Native mechanism presence alone does not establish an increment. `NATIVE-INCREMENT-01` freezes two functional candidates—recursive support topology and exact durable-reopen integrity—plus non-vacuous denominators and an ordered exhaustive basis/result table. FactGraph must reach `100%` with native origin, while a real equally capped reference attempt must remain below `100%` or unsupported on at least one candidate；reference parity on both is `FAIL`. Logic/reference-control failure、any global/workstream/per-arm cap violation、missing/invalid telemetry or another invalid basis makes this comparison `UNRESOLVED`, while the separate mandatory dimension deterministically supplies overall `FAIL` or `UNRESOLVED`. This says nothing about reviewer utility、market value or impossibility under another budget.

### 2026-08-11 — Why runtime failure, abstention and experiment verdict are separate

A runtime failure is not logical non-entailment and cannot earn abstention credit. Conversely, a pre-registered unavailable-source check passes only by returning the exact typed failure and `NO_VERDICT`. Runtime outcome、arm disposition and experiment-check status are therefore separate. Gold-side `UNSCORABLE` is a corpus/adjudication state and does not require an arm to predict hidden disagreement. Because CB0 has no non-substantive ambiguity detector, its 32-case corpus contains zero `EXPECTED_ABSTENTION`；a dedicated non-corpus development fixture checks the `ABSTAIN` state with explicit `DECLARED_INPUT_AMBIGUITY` without turning wrapper inference into a capability claim.

### 2026-08-11 — Why count hiding and authentication are separate

A raw digest or public signature over a 16-case count vector is enumerable. CB0 uses a secret-bearing hiding commitment and a separate authenticated attestation under distinct named secret/signing custodians and credential domains. Input、gold、commitment material and output access are physically/temporally separated；same-artifact checks use verified disposable copies rather than mutating the retained workspace base.

### 2026-08-11 — Why substrate and harness have separate pins

Commit `5a37f947...` supports shipped FactGraph claims only. A future authorized harness receives its own commit and artifact digests, and global freeze must prove zero `src/factgraph/**` drift from the substrate pin. CB0 uses a dedicated entrypoint rather than silently joining the existing A–D runner.

### 2026-08-11 — Why capability owners are reported separately

Native RuleProgram logic/evidence/support、benchmark source/portable codecs、native workspace integrity and benchmark custody/reconstruction are different capabilities. Generic minimal evidence remains degraded even with a passed API status. Keeping owners per field prevents adapter work from being laundered into a shipped FactGraph increment.

### 2026-08-11 — Why Restricted Portable Operator remains outside CB0

`PURE_MAP / SNAPSHOT_LOOKUP` may merit a later decision and disposable parity spike, but it adds new product-source and cross-engine semantics. That separate spike must test host-materialized relations first. It cannot become a ninth class、arm、input producer or Query abstraction here, and cannot borrow this holdout、budget or authority.

### 2026-08-11 — Why recovered adoption obligations close provenance but not evidence

Earlier recovery correctly preserved the adoption pointer without inventing the missing text. The user's later closure package supplies the exact session source description、verbatim obligations and corroborating durable anchors, so the provenance/mapping gate may close. That closure is not evidence that wrong-but-consistent source handling、real hidden-workflow/cascade coverage or blind-review value passed. The first two remain explicit later-envelope carry-forwards；the third remains `UNRESOLVED` because CB0 does not include the pre-registered reviewer task.

### 2026-08-11 — Why custody feasibility and exit `139` precede scope freeze

Corpus/gold independence is structurally constrained by the §5.5 incompatibility matrix. Named-principal feasibility must therefore be checked before accepting budget、corpus and arm commitments；otherwise the envelope could spend its cap before discovering that mandatory dimensions are necessarily `UNRESOLVED`. Separately, exit `139` is treated as a crash/SIGSEGV-class failure. Selecting the passing `factpy` environment is useful evidence but not a root-cause explanation；`ENV-01` stays open until the cause and its absence from the pinned clean environment are recorded.

## Open Gates Before `scoped`

| Gate | State | Required closure evidence |
| --- | --- | --- |
| `OBL-REVIEW-01..03` | `PROVENANCE CLOSED / EVIDENCE UNRESOLVED / CARRY-FORWARD` | §4.4 durably records the 2026-08-11 proximate session source、all three verbatim obligations、content-pinned upstream anchors and clause mappings；wrong-source and real-workflow-cascade experiments remain later-envelope obligations, while reviewer legibility remains `UNRESOLVED` |
| `BUDGET-01` | `OPEN；BLOCKED BY CUSTODY FEASIBILITY` | After `CUSTODY-01` proves a feasible named-principal assignment, explicitly accept or revise §5.2 global/workstream caps plus per-scored-arm 6 active-hours / 2-revision sub-cap and its ledger fields |
| `COUNT-COMMITMENT-01` | `CLOSED AS CONTRACT` | §5.3 freezes domain-bound `CB0-CJSON-v1 + 32-byte hidden nonce + SHA-256` and forbids alternatives；operational nonce/authentication custody remains `CUSTODY-01` |
| `CUSTODY-01` | `OPEN` | Before `BUDGET/CORPUS/ARMS` acceptance, prove a feasible named-principal assignment against all role incompatibilities；then freeze physically separate input/gold locations and credentials、temporal gold/commitment access、distinct secret/signing custodians and credential domains、access logs、attestation and retention/release policy |
| `CORPUS-01` | `OPEN；BLOCKED BY CUSTODY FEASIBILITY` | After `CUSTODY-01` proves a feasible named-principal assignment, accept 16 families / 32 instances、one invariant/class、single-variable pairs、zero corpus `EXPECTED_ABSTENTION`、gold-side `UNSCORABLE`、proof contracts、sealed minima/denominators、locator restriction and double annotation |
| `PROGRAM-PROFILE-01` | `CLOSED AS CONTRACT` | §5.4.1 freezes the strict positive grammar、atom exclusions、exact primitive truth/type/no-coercion rules、dependency DAG、global rule ID、produced-head rejection、empty program facts and proof admissibility；operational fixtures remain `CASE-CODEC-01` |
| `DUAL-GOAL-01` | `CLOSED AS CONTRACT` | §5.4.1 freezes two ordered calls and batch/case/goal-call accounting |
| `SEMANTIC-PARITY-01` | `CLOSED AS CONTRACT` | §§5.4.2/5.6 freeze neutral semantics、operand-type/primitive-truth projection parity and independent reference prohibition；arm implementation remains `ARMS-01` |
| `FAILURE-ALGEBRA-01` | `CLOSED AS CONTRACT` | §5.7.1 freezes typed errors、three state layers、precedence and expected-failure/abstention/`UNSCORABLE` truth tables |
| `CODEC-CONTRACT-01` | `CLOSED AS CONTRACT` | Program、scope、source、EvidenceGraph、support-DAG、pre-scorer-only ordered dual-goal exact/portable projections、separate scored record and public-reopen snapshot contracts frozen；concrete schemas/fixtures remain open below |
| `CAPABILITY-ATTRIBUTION-01` | `CLOSED AS CONTRACT` | Native/adapter/scorer/gold owners and generic-evidence degradation frozen in §§4.2–4.3/5.7 |
| `NATIVE-INCREMENT-01` | `CLOSED AS CONTRACT` | §5.7 freezes two candidate capabilities、non-vacuous denominators、five basis statuses and ordered exhaustive `PASS/FAIL/UNRESOLVED` truth table；actual capability manifest/arms/telemetry remain `ARMS-01` |
| `ARMS-01` | `OPEN；BLOCKED BY CUSTODY FEASIBILITY` | After `CUSTODY-01` proves a feasible named-principal assignment, freeze the mandatory/conditional arm list、capability-comparison manifest、actual equally capped reference instrumentation、per-arm ledger/revision accounting、applicability decision、primary/replay batch/case/goal counts and operational semantic-parity validation |
| `ENV-01` | `OPEN` | Preserve the exact exit-`139` command/environment coordinates；attribute or isolate the cause to a specific interpreter/runtime、native dependency/ABI or project-source boundary；prove the pinned interpreter/dependencies remove it；freeze exact commands/hash seed and reproduce the clean-checkout smoke. `UNKNOWN` and switching to the passing entrypoint alone are not closure；a project-source repair would require separate authorization. |
| `CASE-CODEC-01` | `OPEN` | Concrete canonical schemas、round-trip fixtures、single fact truth、schema coordinate、tagged total witness mapping and exact/portable manifest schemas instantiate `CODEC-CONTRACT-01` |
| `PATHS-01` | `OPEN` | Durable path/ignore checks plus named write-once/no-overwrite storage、atomic seal、clean-close retained base、verified disposable copies、public `FactGraph.load_workspace(..., schema_classes=...)` reopen、custodian permissions and pre-gold seal |
| `BENCH-ENTRY-01` | `OPEN` | Freeze dedicated direct-test/runner names、arguments、ownership/output roots and no implicit root pytest/A–D runner；actual harness pin closes before holdout execution |
| `PREFLIGHT-01` | `CLOSED` | Fixed `04ad3c...` preflight、full-pair amendment/diff review and Step 4.5 self-check are complete；`SC45-01` was tightened and independently rechecked with no high residual |
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
| `REFERENCE-01` | protocol | required | Increment depended on a hypothetical rather than executed reference instrumentation cost. | `APPLIED`: `NATIVE-INCREMENT-01` requires an equally capped real attempt、sealed code/time/output evidence and exact two-capability denominators；reference parity on both candidates is increment `FAIL`, semantic non-equivalence independently fails overall, and `NOT_RUN`/telemetry-incomplete reference remains overall `UNRESOLVED` absent another failure. |
| `CORPUS-INVARIANT-01` | protocol | required | Eight umbrella classes contained multiple mechanisms that 32 sparse cases could not attribute. | `APPLIED`: one required invariant per class; other stressors and uninstantiated umbrellas stay explicit/`UNRESOLVED`. |
| `GOLD-01` | protocol | required | One undifferentiated GoldSide could not create genuine disagreement evidence, and a runner could not inspect hidden counts before unseal. | `APPLIED`: two blind independent holdout labels, third adjudication or `UNSCORABLE`, dev spot-check, immutable post-unseal gold, GoldCustodian count statement plus distinct attestation authenticator, and post-unseal verification. Operational roles remain `CUSTODY-01`. |
| `LOCATOR-01` | protocol | required | PDF/character/DB locators lacked a common canonicalization contract. | `APPLIED`: v0 restricted to UTF-8 byte offsets and RFC 6901 pointers; native support and external mapping score separately. |
| `VERDICT-01` | protocol + governance | required | Budget overrun and optional unresolved dimensions allowed contradictory overall dispositions. | `APPLIED`: mandatory/optional truth table, actual-overrun `FAIL`, missing-ledger `UNRESOLVED`, no overall `PARTIAL`. |
| `LLM-01` | protocol | recommended | Optional LLM task, retry, timeout, and provider-error behavior were underdefined. | `APPLIED`: same normalized task plus frozen generation/error/retry contract; no post-inspection rerun. |
| `SOURCE-CONTROL-01` | protocol | recommended | `A-SOURCE` was called mandatory/scored despite emitting no verdict. | `APPLIED`: mandatory non-scored control artifact, excluded from automated denominators. |
| `CONFUSION-01` | protocol | recommended | False support/challenge and silent gap lacked exact definitions; “material” created discretion. | `APPLIED`: exact confusion rules; materiality exemption removed. |
| `BUDGET-LEDGER-01` | protocol | recommended | Numeric cap lacked auditable counting/allocation rules and could double-count supervised agent time. | `APPLIED`: labor is non-overlapping human/operator minutes ÷ 60；agent wall time/compute are separate；per-arm 6-hour/2-revision limits are ledgered inside global/workstream caps；final acceptance remains `BUDGET-01`. |
| `ROLE-01` | protocol | required | No role owned hidden case/rule construction, and final audit independence was ambiguous. | `APPLIED`: CaseAuthor, GoldCustodian, and incompatible FinalAuditor roles plus overlap limits are explicit; operational assignment remains `CUSTODY-01`. |
| `OP-MANIFEST-01` | protocol | required | Replay patches/operators and expected relations could be read as one sealed package. | `APPLIED`: run-visible operation manifest and gold-only replay-expectation manifest are independently digested and separated. |
| `CASE-CODEC-01` | repo | recommended | Fact payload had two truth sources and RuleProgram serialization was undecided. | `GATED`: blueprint selects a single referenced fact file and benchmark-owned codec shape; exact codec/schema/mapping must freeze before scoped. |
| `PATHS-WRITEONCE-01` | repo | recommended | Tracked Git files are not inherently append-only. | `GATED`: actual no-overwrite/content-addressed/atomic/custodian/seal mechanism required by `PATHS-01`. |
| `CITE-01` | repo | recommended | Several shipped claims/ranges overstated identity, immutability, or method coverage. | `APPLIED`: §4.2 states shape limits and uses corrected full ranges/terminology. |
| `SUCCESSOR-01` | governance | recommended | Successor guard omitted immutable `PARTIAL`, parent/diff, and renewed P-GATE choice. | `APPLIED`: §7.4 adds all conditions without authorizing a successor. |
| `DIRTY-01` | governance | recommended | Dirty-worktree preservation needed a recorded baseline. | `APPLIED`: exact unrelated status count/hash and sacred-ref observations recorded above; only this pair may be staged. |
| `TEMPLATE-DRIFT-01` | governance | repository drift | Canonical blueprint templates themselves omit fields required by the seven-field schema. | `OUT OF SCOPE`: this pair conforms manually; template repair requires its own governed slice and is not folded into F-GATE. |
| `PF-R01` | fixed preflight | required | Executable RuleProgram subset、dual-goal call/evidence ownership、neutral reference semantics and winning-proof scoring were not frozen. | `APPLIED AS CONTRACT；STEP 4.5 CLEAR`: §§5.4.1/5.6 close the positive grammar、exact primitive truth/no-coercion、two-call ownership and parity definition；operational fixtures/arms remain gated. |
| `PF-R02` | fixed preflight | required | Program/scope/evidence/support/source/snapshot portable identities and total witness mapping were incomplete. | `APPLIED AS CONTRACT；STEP 4.5 CLEAR`: §§5.4.2/5.8 split native observations from benchmark codecs、retain both ordered goal payloads、freeze pre-scorer raw versus downstream scored identity、exclude run-variant/scorer fields and require shipped public reopen；`CASE-CODEC-01/PATHS-01` still require concrete artifacts. |
| `PF-R03` | fixed preflight | required | Exceptions could be confused with non-entailment；runtime、abstention、gold `UNSCORABLE` and experiment verdict were not closed. | `APPLIED AS CONTRACT；STEP 4.5 CLEAR`: §5.7.1 freezes typed errors、precedence and the three-layer truth table. |
| `PF-R04` | fixed preflight | required | Outcome-count checksum was enumerable and custody/workspace-copy semantics were not executable. | `APPLIED/GATED；STEP 4.5 CLEAR`: hiding construction、authentication boundary and physical/disposable-copy rules are frozen；named custody/write-once mechanisms remain `CUSTODY-01/PATHS-01`. |
| `PF-Rec01` | fixed preflight | recommended | FactGraph substrate and future harness pins/entrypoints were conflated. | `APPLIED/GATED；STEP 4.5 CLEAR`: dual-pin/zero-drift and dedicated-entrypoint rules added；future exact harness identity remains pre-holdout. |
| `PF-Rec02` | fixed preflight | recommended | Adapter-owned/degraded capabilities could be laundered into native complete evidence. | `APPLIED AS CONTRACT；STEP 4.5 CLEAR`: owner/degradation matrix and per-field output attribution added. |
| `PF-V01..03` | fixed preflight | verified | Native read-only substrate、identity split and durable-topology feasibility were directionally valid. | `RECORDED`: retained as bounded shipped observations；not promoted to product/replay claims. |
| `PF-S01` | fixed preflight | scoped-detail | Helper names and internal module decomposition may remain implementation detail. | `DEFERRED BY CONTRACT`: dedicated public entrypoint/path and artifact boundaries are frozen；internal helpers and module decomposition behind that entrypoint remain implementation detail. |
| `PF-S02` | fixed preflight | scoped-detail | Restricted Portable Operator could silently expand CB0. | `APPLIED AS SCOPE GUARD；STEP 4.5 CLEAR`: non-goal、`INV-F23` and §8 guard forbid any Operator artifact/arm/case/budget/authority. |
| `SC45-01` | Step 4.5 self-check | high/required tightening | `ArmRawBundleV0` retained singular bundle-level evidence/support refs beside the two per-goal owners, leaving a second fact source and ambiguous positive/refuting ownership. | `APPLIED；INDEPENDENT RECHECK CLEAR`: removed both bundle-level aliases and made each ordered `GoalCallRaw` the sole owner of its side's raw/normalized evidence/support references. |
| `OBL-CLOSE-01` | user recovery package | required provenance closure | Three mandatory blueprint-stage obligations existed only behind an adoption pointer and could not be inferred safely. | `APPLIED WITH CARRY-FORWARD`: §4.4 preserves the exact source/text/anchors/mappings；closing provenance neither runs the experiments nor resolves their verdict dimensions. |
| `GATE-ORDER-01` | user recovery package | required sequencing guard | Corpus/budget commitment could precede proof that role independence is feasible；exit `139` could be bypassed rather than explained. | `APPLIED/GATED`: §7.1 orders custody feasibility first；`CUSTODY-01` and `ENV-01` remain open with strengthened closure evidence. |

All draft-review and fixed-preflight findings are represented in the amended contract or an explicit later operational gate, Step 4.5 has no high residual after `SC45-01`, and `OBL-REVIEW-01..03` now has exact provenance/mapping with both carry-forwards preserved. This does **not** close any other operational gate or authorize `scoped`.

## Deviations

None at creation or Step 4.4 amendment. `SC45-01` is a Step 4.5 contract tightening, not a scope deviation. The blueprint remains `draft`；proposed numbers、roles、mechanisms、schemas and paths are not yet scope-frozen.
