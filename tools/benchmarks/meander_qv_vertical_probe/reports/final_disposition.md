# Final Disposition — Meander Agent Query/Validation Vertical Probe (P0/A0)

**EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT**

- Immutable closure of the one authorized experiment envelope (scoped blueprint `6ce7e2a5`).
- Written 2026-08-11 on branch `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`.
- This is the experiment's result consolidation. It authorizes no successor experiment, no ADR,
  no production work, and does not close `P-GATE` or change `D01`/product authorization.

## 1. Unique terminal disposition (§5.15)

```
disposition             = REVISE
reason                  = THRESHOLD_UNMET
experiment_validity     = UNRESOLVED
architecture_hypothesis = NOT_CONTRADICTED
agent_dimension         = NOT_TESTED / UNRESOLVED
```

Derived mechanically by `DispositionPrecedenceValidatorV0` (`tests/disposition_validator.py`,
fail-closed, self-tested across 10 groups incl. STOP-precedence, missing-section, missing mandatory
`dual_model_arms_pass`, type errors, and the full closure terminal-tuple) from the frozen inventory
in `reports/final_disposition_evidence.json`. `validate_declared(evidence, "REVISE", "UNRESOLVED")`
→ `consistent: true`.

**No kill criterion fired.** The envelope ends `REVISE / THRESHOLD_UNMET` because the deterministic
eligibility gates are unmet — the Step 3 exact-anchor exit was **not implemented / not proven**,
replay R0 aggregate is unmet, and the mandatory `dual_model_arms_pass` threshold is unmet (the two
model arms were never eligible to run). `experiment_validity=UNRESOLVED` (the experiment ran validly
but did not clear its gates — it is not `EXPERIMENT_INVALID`). The architecture hypothesis was **not
falsified**; it was left untested at the model layer and unproven at the exact-anchor exit.

## 2. Per-dimension results (no PASS overclaim)

| Dimension | Result | Basis |
|---|---|---|
| Deterministic Step 3 core semantics | **PARTIAL** | The separately-accounted verification sweep scored 20/20 on the frozen goldens after three located harness output-shaping fixes; the **original** first primary run stands at 15/20 (unaltered manifest). Core semantic behavior is a **partial success**. |
| Step 3 exact-anchor exit (§5.10) | **NOT IMPLEMENTED / NOT PROVEN** | An exact per-anchor exit gate over the original 20-invocation primary run was never implemented or demonstrated. The verification sweep is a whole-corpus re-score, not an exact-anchor exit. |
| Replay R0 (three-target) | **UNMET (aggregate)** | RP-R0-ROW was genuinely live; RP-R0-SUMMARY / RP-R0-EXPECTATION were verified from Step-3 captured artifacts, not live in Step 5. The aggregate three-target R0 claim is **not** PASS. |
| Replay R1 (captured-artifact) | **PARTIAL** | Q02 selected-row bundle reopened without a store; one representative bundle only. Not a general captured-replay PASS. |
| Replay R2 (pinned re-execution) | **PARTIAL** | Only the **canonical rowset and completeness** matched on the one representative Q02 bundle. |
| Replay R2 EvidenceGraph / authored-node identity | **UNRESOLVED** | Explain-graph authored-node identity equivalence across the pinned re-execution was **not** established; it is explicitly UNRESOLVED, not a pass. |
| Replay R3 | **UNRESOLVED** | detached new-process reconstruction not executed (lean envelope). |
| Replay R4 | **NOT_TESTED** | production CompletedRun/retention/migration/UI replay out of scope. |
| Negative availability | Explicit (recorded, not a promotion basis) | four negatives each failed typed (RUN_CONTEXT_UNAVAILABLE ×2 / REPLAY_ARTIFACT_EXPIRED / REPLAY_INTEGRITY_FAILURE); never read current state. |
| Mutation isolation | Held (recorded) | four child comparative runs on copies; zero-execution digest comparison. |
| Compatibility / no-side-effect | Held | COMPAT-CMD-01 rerun 70 passed; MEANDER-STATE-DIGEST-01 after==before (`b6ba7d6f…`); four-repo manifests unchanged; shipped `src/**` zero drift. |
| Agent (dual-model) fidelity | **NOT_TESTED / UNRESOLVED** | eligibility gates unmet; the two arms never became eligible to run. |
| Translator fidelity / product / P-GATE / D01 | **NOT_TESTED / UNCHANGED / OPEN** | out of scope by construction. |

## 3. §5.15 per-item terminal states

| Item | Terminal state |
|---|---|
| Overall protocol | Completed (`implementing → implemented`); disposition `REVISE / THRESHOLD_UNMET`; `experiment_validity=UNRESOLVED`. |
| Architecture hypothesis | `NOT_CONTRADICTED` — no kill fired; not falsified, not proven. |
| SC-01 (join × Any candidate fork) | **PARTIAL / D03 UNRESOLVED** — branch-scoped vs reject-on-partial observably distinguished on the frozen fixture (SC01-A one row `ax=1` with explicit per-branch join applicability lineage; SC01-B pre-engine `JOIN_ENDPOINT_NOT_TOTAL`). The probe records a candidate distinction but **adopts no D03 recommendation**; D03 stays UNRESOLVED. |
| SC-02 (total authored→lowered lineage) | **PARTIAL** — `check_totality` invariants 1–7 held on the exercised cells (deterministic layer); not exit-gated, so not a durable SC-02 pass. |
| SC-12 (DNF branch limit / publish-time capability) | **PARTIAL** — SC12-32 accepted at exactly 32 branches; SC12-P rejected `DNF_BRANCH_LIMIT_EXCEEDED` at publish/freeze with `engine_invocations=0`. Failure owner/stage recorded as experiment-local evidence only. |
| AC-21 (`__query__` namespace isolation) | **PARTIAL** — authored `__query__:…` rejected pre-lowering `SYNTHETIC_QUERY_NAMESPACE_COLLISION`, `engine_invocations=0`, namespace preserved without capture; experiment-local evidence only. |
| Model A / Model B (dual arms) | **NOT_TESTED / UNRESOLVED** — `dual_model_arms_pass` unmet; `model_runner.py` is an offline projection prototype only (see §4); zero provider calls. |
| Blind scoring (12 slots) | **NOT_PERFORMED / UNRESOLVED** — no model output was produced, so no blind pack was sealed or scored; the human dimension is UNRESOLVED (consistent with `accept_no_adjudicator_unresolved=true`). |
| D02–D07 / D10–D11 evidence map | All `PARTIAL` / `UNRESOLVED`; none `SUPPORTED_FOR_ADR`; no D-number adopted (see §5). |
| Product / P-GATE / D01 | `NOT_TESTED / UNCHANGED / OPEN`. |

## 4. Model runner clarification

`model_runner.py` is **an offline projection prototype only**. It constructs two experiment-owned
raw-HTTP request projections (OpenAI Responses / Anthropic Messages dialects) and normalizes canned
responses; it made **zero** network calls, touched **zero** credentials, and issued **zero** provider
calls. Its "conformance all OK" result attests **only** to local serialization / schema
embed→extract byte-identity / canned-response normalization — **not** to any real provider's
acceptance of the schema, which remains `NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION`. It is not a working
model client and must not be read as evidence that either arm functions end-to-end.

## 5. Evidence-to-decision map (§4.8) — maximum honest claim

No D-number is closed or adopted; each candidate is at most `PARTIAL`/`UNRESOLVED` because the
envelope terminated at `REVISE`: D02 semantic ports PARTIAL; D03 Policy AST v0 PARTIAL (SC-01
recommendation UNRESOLVED); D04 field navigation PARTIAL; D05 PolicyQueryContract UNRESOLVED;
D06 query/expectation semantics PARTIAL; D07 minimum A0 assignment PARTIAL; D10 replay profile
PARTIAL (R1/R2 rowset+completeness only; EvidenceGraph identity, R3, durable replay UNRESOLVED/
NOT_TESTED); D11 anchors PARTIAL (run-local only; durable cross-run identity NOT established).

## 6. BYOK / EGRESS status (corrected framing)

BYOK-01 and per-provider EGRESS-01 were **not consumed because the deterministic eligibility gates
were unmet** — the mandatory `dual_model_arms_pass` threshold, the Step 3 exact-anchor exit, and the
replay R0 aggregate did not clear, so the model stage never became eligible. No credential was
requested, read, accepted, or stored; **0** provider calls, **0** tokens, **EUR 0**, **0 B** egress.
(This supersedes any earlier "user declined BYOK" phrasing: the operative cause recorded here is the
unmet deterministic eligibility gates.)

## 7. A01-AUTH field-ordering note (§5.6)

`A01-AUTH` retains submission order for `attempted_authority_fields` per the frozen oracle. This
order is an **experiment-v0 convention only**; it is **not** a public canonical-ordering contract.
The composite ingress rejection proves only composite fail-closed, never seven independent attack
rates.

## 8. Budget & side-effect ledger (final, corrected)

- Person-hours (agent wall-clock, conservative): Step 2 52/300, Step 3 115/600, Step 5 55/240,
  Step 4 local readiness unbilled to the model cap, reserve 0/120 → within 24h.
- Engine calls: 13 primary (== oracle pins) + 8 declared non-primary synthetic smokes
  + 13 verification-sweep + 5 Step-5 replay. Semantic/schema repair = **0**.
- Model: **0** provider calls, **0** tokens, **EUR 0**, **0 B** egress.
- Durable tracked experiment bytes: **68 files / 369078 bytes** (measured by tracked-file content;
  under the 512 MiB cap). The earlier `0` and `~357 KB` figures were superseded.
- Dirty baseline preserved byte-identical throughout (112 items / `c058409c…`); adjacent repos clean
  at pins; `master` unchanged; no push/merge.

## 9. What a future (separately authorized) envelope would need to move past REVISE

Recorded as observations, **not** as a scheduled successor: (a) implement and satisfy an exact-anchor
Step 3 exit on a single primary run without a repair sweep; (b) make R0 genuinely live for all three
targets, lift R1/R2 beyond one representative bundle, and establish EvidenceGraph authored-node
identity; (c) run the two authorized model arms under BYOK/EGRESS with sealed blind scoring. Any such
work requires a new decision that revisits whether `P-GATE` must precede it; this closure grants none
of it.
