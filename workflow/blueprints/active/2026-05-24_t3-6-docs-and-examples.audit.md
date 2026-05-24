# Task Blueprint Audit: T3.6 Docs And Examples

- Blueprint: [2026-05-24_t3-6-docs-and-examples.md](./2026-05-24_t3-6-docs-and-examples.md)
- Status: scoped
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.6 S-class docs-only scope recorded from D5 section 4.7, Stage 3 synthesis section 3 T3.6, track plan T3.6 row, adopted D1-D5, parent C24/C27/C32/C35/C49-C51/C58/C59, and archived T3.1-T3.5 substrate. |
| 2026-05-24 | scoped | Scope locked + P3 precision amendments | T3.6-F1 anti-example wording clarified to `ExplicitBoolError` short-circuit behavior; T3.6-F2 markdown grep acceptance cross-referenced §8 step 8 specifics; T3.6-F3 optional `06_what_if_and_proof.en.md` touch locked to no-touch unless scoped amendment says otherwise. |
| 2026-05-24 | pre-impl | Step 4.6 docs grep clean; targets identified | Grep found one expected stale application-rule deferral sentence, legacy-context `Rule` imports only, no invalid join `==` examples, missing user-facing `join_by_ports` / `ExplicitBoolError` / `unjoined_same_name_ports` teaching outside API surface, and confirmed `04_api_surface.en.md` already contains the T3.5 RuleExpr rows/count baseline. |
| 2026-05-24 | baseline | G7 baseline recorded | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect -v` ran 76 tests OK after Step 4.6 docs grep. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- D1 public surface and operand boundary: `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md` section 4.5.
- D2 join construction: `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md` sections 4.1-4.5 and 7.3.
- D3 inspect coexistence: `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md` sections 4.1-4.6 and 7.3.
- D4 structural equality/hash: `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md` sections 4.1-4.7 and 7.3.
- D5 slice split and bool guard timing: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` section 4.7.
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` section 3 T3.6.
- Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` synced at `9c857d0c`, T3.6 row.
- Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` section 3.6, section 3.7.1 / C5-C6, section 4 C23-C35 and C49-C51, section 5.9 C58, and section 5.10 C59.
- T1.4 archive: `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- T3.1 archive: `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
- T3.2 archive: `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
- T3.3 archive: `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
- T3.4 archive: `workflow/blueprints/archive/2026-05-24_t3-4-join-by-ports.md`
- T3.5 archive: `workflow/blueprints/archive/2026-05-24_t3-5-ruleexpr-inspect.md`

### G1-G7 Visible Mapping

| Gate | T3.6 mapping |
|---|---|
| G1 | Canonical source chain includes Stage 1 audit, D1-D5, synthesis, track plan, parent commitments, and T1.4/T3.1-T3.5 archives. |
| G2 | Blueprint section 4 cites current SDK/application docs files and shipped T3.1-T3.5 behavior to document. |
| G3 | File citations include SDK docs, application rule docs, and the T3.5 test baselines. |
| G4 | Goals map to D1 staged naming, D2 `.eq(...)`, D3 inspect return shapes, D5 T3.6 ownership, and parent C24/C27/C32/C58/C59. |
| G5 | Non-goals and section 5.7 preserve code, exports, T1.4/T1.3/T2.3/T3.1-T3.5 substrate, and execution-lowering deferral. |
| G6 | Reviewer should spot-check docs-only scope, staged import examples, precedence wording, inspect return-shape distinction, and `04_api_surface.en.md` no-touch lock. |
| G7 | Section 8 requires G7 baseline, pre-impl grep, docs grep gates, and preservation unittest gates before closure. |

### Class Trigger Analysis

T3.6 is S-class.

S-class reasons:

- Docs-only slice; no Python source behavior change is planned.
- No public SDK export, DTO, helper function, or error class is added.
- No algorithm or validation semantics are introduced.
- It consumes already shipped T3.1-T3.5 behavior and adopted D1-D5 decisions.
- Acceptance is documentation coverage plus preservation tests, not new runtime behavior.
- It is the final initial T3 authoring/inspect slice and explicitly defers execution lowering.

S-to-M triggers:

- Editing Python source.
- Changing `factgraph.sdk.__all__`, API surface exports, or `04_api_surface.en.md` counts.
- Adding a new durable docs file that changes docs index structure.
- Discovering that current docs cannot be truthful without code changes.

### Preemptive Scope Check

T3.6 applies the T3.3/T3.4/T3.5 zero-deviation pattern for the fourth cycle:

- shipped Python source: do not edit.
- SDK exports and `__all__`: do not edit.
- `04_api_surface.en.md`: do not edit by default; T3.5 already corrected it.
- new DTOs / error classes: do not add.
- T1.4 / T1.3 / T2.3 / T3.1-T3.5 substrate: do not touch.
- legacy SDK Rule / Inference inspect dict output: do not change.
- RuleExprInspect object return shape: do not change.
- `_is_legacy_sdk_rule`: do not replace.
- new docs file: pause for scope amendment before adding.

### Reviewer Focus Areas

- Whether S-class docs-only declaration is justified.
- Whether D1-D5 and parent commitments are all cited.
- Whether all six docs obligations are explicit and testable.
- Whether the docs file placement is precise enough to prevent scope creep.
- Whether `04_api_surface.en.md` is correctly locked as no-touch.
- Whether examples use `ApplicationRule`, `RuleExpr`, and `build_application_rule(...)`, not final-state `Rule`.
- Whether `.eq(...)`, `.join(...)`, `.join_by_ports(...)`, precedence, bool guards, same-name ports, and inspect return shapes are all represented.
- Whether T3.5-F6 `value_type="unknown"` is carried into docs.
- Whether preservation tests exclude only known unrelated `test_public_inference_factgraph_create` failures.

### Cross-Slice Contract Preservation

| Prior slice | Expected preservation |
|---|---|
| T1.1 Rule DTO | Rule fields, atom ids, content digest, ports, and validation unchanged; docs may reference current behavior only. |
| T1.2 DSL bridge | `build_application_rule(...)` remains the bridge for SDK DSL authors; no bridge code changes. |
| T1.3 SDK naming | top-level `factgraph.sdk.Rule` remains legacy; docs teach `ApplicationRule` during the staged period. |
| T1.4 alias/port substrate | `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, `RulePortRef.__eq__`, and `.eq(...)` relationship documented without code changes. |
| T2.3 aggregate substrate | aggregate docs remain intact; T3.6 may reference aggregate helpers only as existing bridge context. |
| T3.1 base RuleExpr | composition, factories, bool guards, and negative-action gates preserved and documented. |
| T3.2 expression-scope validation | alias uniqueness and repeated-rule diagnostics preserved and may be linked as current behavior. |
| T3.3 joins + reach rule | `.eq(...)`, `.join(...)`, reach validation, self-join rejection, symmetry/dedupe preserved and documented. |
| T3.4 join_by_ports | `.join_by_ports(...)` explicit-name expansion and diagnostics preserved and documented. |
| T3.5 RuleExpr inspect | `RuleExprInspect` DTOs, polymorphic inspect dispatch, legacy dict preservation, and `value_type="unknown"` sentinel preserved and documented. |

### Step 4.6 Pre-Implementation Grep

| Check | Command | Result |
|---|---|---|
| Stale deferral language | `rg 'joins.*deferred\|inspect.*deferred\|deferred.*to later T3' src/factgraph/application/docs/ src/factgraph/sdk/docs/` | Expected target found: `src/factgraph/application/docs/rule.md` still says joins / inspect output / full examples remain deferred to later T3 slices. T3.6 should update this current-truth sentence. |
| Final-state SDK `Rule` imports | `rg 'from factgraph.sdk import Rule\b' src/factgraph/sdk/docs/ src/factgraph/application/docs/` | Clean for T3.6 risk: hits are existing legacy SDK Rule / proof docs contexts in `00_user_guide.en.md` and `06_what_if_and_proof.en.md`, not application Rule / RuleExpr teaching. |
| Join examples using `==` instead of `.eq(...)` | `rg '\.user.*==.*\.|\.eq\(' src/factgraph/sdk/docs/ src/factgraph/application/docs/` | Clean for invalid join examples: `.eq(...)` is present in `04_api_surface.en.md`; `==` hits are SDK where-syntax / attr-equality examples or application bridge examples, not RuleExpr join examples. |
| Missing RuleExpr docs terms | `rg 'join_by_ports\|ExplicitBoolError\|unjoined_same_name_ports' src/factgraph/sdk/docs/ src/factgraph/application/docs/` | Expected docs gap confirmed: terms currently appear only in `04_api_surface.en.md` rows. T3.6 must add user-facing teaching in scoped docs files. |
| API surface no-touch baseline | `wc -l src/factgraph/sdk/docs/04_api_surface.en.md` + `grep -c 'RuleExpr\|RuleJoinConstraint\|RuleExprInspect' src/factgraph/sdk/docs/04_api_surface.en.md` | Clean: `04_api_surface.en.md` is 607 lines and has 7 RuleExpr-related hits, including `RuleExpr`, `RuleJoinConstraint`, `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, `PortInspect`, and `ExplicitBoolError`. No T3.6 edit needed. |

### G7 Baseline Record

| Check | Result |
|---|---|
| Branch and sacred state | T3.6 branch `v0.2.0-t3-6-docs-and-examples-2026-05-24`; sacred `master` remains `562c7419`; dirty 4M+1U preserved. |
| T3.5 RuleExpr inspect substrate | Step 4.6 grep already confirmed T3.5 API surface rows/count baseline and no T3.6 API-surface edits needed. |
| Docs grep targets identified | Step 4.6 grep already confirmed stale application-rule deferral target, missing RuleExpr user-facing teaching outside API surface, legacy `Rule` imports in legacy/proof contexts only, and no invalid join `==` examples. |
| Requested pytest baseline | Deferred per T3.1-T3.5 environment lock: pytest has known SIGSEGV in this environment; unittest fallback is the G7 runner. |
| Fallback unittest baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect -v` -> 76 tests OK. |

### Step 4.2 Draft Review Checklist

- [ ] S-class declaration justified and no M trigger left implicit.
- [ ] Source chain includes Stage 1 audit, D1-D5, synthesis, track plan, parent commitments, and six substrate archives.
- [ ] Six docs obligations are visible in goals and acceptance.
- [ ] Module placement lists touched docs files and explicitly locks no-touch files.
- [ ] `04_api_surface.en.md` no-touch decision is explicit.
- [ ] Staged import examples avoid final-state `Rule` teaching before T5.
- [ ] `.eq(...)`, `.join(...)`, `.join_by_ports(...)`, precedence, bool guards, same-name ports, and inspect return shape examples are all scoped.
- [ ] Cross-slice preservation covers T1.1-T3.5.
- [ ] G7 baseline, pre-impl grep, docs grep, preservation tests, and known unrelated public-inference failures are handled.
