# Final Disposition — Meander Agent Query/Validation Vertical Probe (P0/A0)

**EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT**

- Immutable closure of the one authorized experiment envelope (scoped blueprint `6ce7e2a5`).
- Written 2026-08-11 on branch `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`.
- This is the experiment's result consolidation. It authorizes no successor experiment, no ADR,
  no production work, and does not close `P-GATE` or change `D01`/product authorization.

## 1. Unique terminal disposition

```
disposition          = REVISE
experiment_validity  = EXPERIMENT_INVALID  (mandatory model dimension NOT_TESTED; required gates unmet)
reason               = REQUIRED_GATES_UNMET
architecture_hypothesis = NOT_CONTRADICTED
agent_dimension      = NOT_TESTED / UNRESOLVED
```

Derived mechanically by `DispositionPrecedenceValidatorV0` (`tests/disposition_validator.py`,
fail-closed, self-tested) from the frozen evidence in `reports/final_disposition_evidence.json`:
no STOP-class or REVISE-class kill fired; the envelope ends `REVISE` because required exit/replay
gates are unmet and the model arms were never authorized. **No kill criterion fired; the
architecture hypothesis was not falsified — it was left untested at the model layer and short of the
exact-anchor exit at the deterministic layer.**

The user (2026-08-11) declined to authorize BYOK, EGRESS, or any provider call, and directed
closure at `REVISE / EXPERIMENT_INVALID / REQUIRED_GATES_UNMET` with the two status pins above,
correcting only report/audit facts (no fixture/golden change, no re-execution).

## 2. Per-dimension results (corrected; no PASS overclaim)

| Dimension | Result | Basis |
|---|---|---|
| Deterministic Step 3 core semantics | **PARTIAL** | Verification sweep scored 20/20 cells on the frozen goldens after three located harness output-shaping fixes; the **original** first primary run stands at 15/20 (unaltered manifest). Core semantic behavior is a **partial success**. |
| Step 3 exact-anchor exit (§5.10) | **UNMET** | The exact per-anchor exit was demonstrated only via the separately-accounted verification sweep, not the original 20-invocation primary run; the exit gate over the primary run is **not** satisfied. |
| Replay R0 (three-target) | **UNMET (aggregate)** | RP-R0-ROW was genuinely live; RP-R0-SUMMARY / RP-R0-EXPECTATION were verified from Step-3 captured artifacts rather than live in Step 5. The aggregate three-target R0 claim is therefore **not** PASS. |
| Replay R1 (captured-artifact) | **PARTIAL** | Q02 selected-row bundle reopened without a store; demonstrated on one representative bundle only. Not a general captured-replay PASS. |
| Replay R2 (pinned re-execution) | **PARTIAL / UNRESOLVED** | Q02 rowset/completeness/authored-identity matched on one representative bundle; narrowed to representative evidence, not a durable-replay PASS. |
| Replay R3 | **UNRESOLVED** | detached new-process reconstruction not executed (lean envelope). |
| Replay R4 | **NOT_TESTED** | production CompletedRun/retention/migration/UI replay out of scope. |
| Negative availability | Explicit (recorded) | four negatives each failed typed (RUN_CONTEXT_UNAVAILABLE ×2 / REPLAY_ARTIFACT_EXPIRED / REPLAY_INTEGRITY_FAILURE); never read current state. Recorded as supporting evidence, not a promotion basis. |
| Mutation isolation | Held (recorded) | four child comparative runs on copies; zero-execution digest comparison. |
| Compatibility / no-side-effect | Held | COMPAT-CMD-01 rerun 70 passed; MEANDER-STATE-DIGEST-01 after==before (`b6ba7d6f…`); four-repo manifests unchanged; shipped `src/**` zero drift. |
| Agent (dual-model) fidelity | **NOT_TESTED / UNRESOLVED** | BYOK/EGRESS/model execution never authorized. |
| Translator fidelity / product / P-GATE / D01 | **NOT_TESTED / UNCHANGED / OPEN** | out of scope by construction. |

## 3. Evidence-to-decision map (§4.8) — maximum honest claim

No D-number is closed or adopted. Each candidate is at most `PARTIAL`/`UNRESOLVED`; none reaches
`SUPPORTED_FOR_ADR` because the envelope terminated at `REVISE`.

| Candidate | Status | Note |
|---|---|---|
| D02 semantic ports | PARTIAL | occurrence-qualified specialized-rule addressing exercised deterministically; not exit-gated. |
| D03 Policy AST v0 | PARTIAL | All/Any/compare/unify + SC-01 branch-scoped vs reject-on-partial observably distinguished; **D03 recommendation remains UNRESOLVED** (probe does not adopt). |
| D04 field navigation | PARTIAL | typed resolution + grant + branch-unbound + lineage exercised (NAV01/NAV02); not exit-gated. |
| D05 PolicyQueryContract | UNRESOLVED | P0/A0 ownership held in fixtures; no stable public contract demonstrated. |
| D06 query/expectation semantics | PARTIAL | rows/completeness, complete/incomplete zero, exists/contains_row, unsupported set-mode covered; budgets/continuation untested. |
| D07 minimum A0 assignment | PARTIAL | server-fixed profile + failed-escalation fixtures (A01-AUTH) covered deterministically; no Agent probe ran. |
| D10 replay profile | PARTIAL | only R1/R2 representative + explicit missing-artifact behavior; R3 UNRESOLVED, R4 NOT_TESTED; durable replay not established. |
| D11 anchors | PARTIAL | run-local row/summary/expectation anchors exercised; durable cross-run identity NOT established. |

## 4. Model runner clarification (user ruling item 4)

`model_runner.py` is **an offline projection prototype only**. It constructs two experiment-owned
raw-HTTP request projections (OpenAI Responses / Anthropic Messages dialects) and normalizes canned
responses; it made **zero** network calls, touched **zero** credentials, and issued **zero** provider
calls. Its "conformance all OK" result attests **only** to local serialization / schema
embed→extract byte-identity / canned-response normalization — **not** to any real provider's
acceptance of the schema, which remains `NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION`. It is not a working
model client and must not be read as evidence that either arm functions end-to-end.

## 5. A01-AUTH field-ordering note (§5.6 / A′ item 5)

`A01-AUTH` retains submission order for `attempted_authority_fields` per the frozen oracle. This
order is an **experiment-v0 convention only**; it is **not** a public canonical-ordering contract.
The composite ingress rejection proves only composite fail-closed, never seven independent attack
rates.

## 6. Budget & side-effect ledger (final, corrected)

- Person-hours (agent wall-clock, conservative): Step 2 52/300, Step 3 115/600, Step 5 55/240,
  Step 4 local readiness unbilled to the model cap, reserve 0/120 → well within 24h.
- Engine calls: 13 primary (== oracle pins) + 8 declared non-primary synthetic smokes
  + 13 verification-sweep + 5 Step-5 replay. Semantic/schema repair = **0**.
- Model: **0** provider calls, **0** tokens, **EUR 0**, **0 B** egress. BYOK/EGRESS never granted.
- Durable tracked experiment bytes: **~357 KB** (measured; well under the 512 MiB cap — the earlier
  `durable_artifact_bytes.used_estimate: 0` was a stale placeholder, corrected in the ledger).
- Dirty baseline preserved byte-identical throughout (112 items / `c058409c…`); adjacent repos clean
  at pins; `master` unchanged; no push/merge.

## 7. What a future (separately authorized) envelope would need to move past REVISE

Recorded as observations, **not** as a scheduled successor: (a) satisfy the exact-anchor Step 3 exit
on a single primary run without a repair sweep; (b) make R0 genuinely live for all three targets and
lift R1/R2 beyond one representative bundle; (c) run the two authorized model arms under BYOK/EGRESS.
Any such work requires a new decision that revisits whether `P-GATE` must precede it; this closure
grants none of it.
