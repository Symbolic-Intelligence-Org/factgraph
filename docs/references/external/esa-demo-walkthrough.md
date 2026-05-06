# ESA Demo Walkthrough: ESSB-ST-U-007 Compliance Audit

This document guides a live demo of factpy's compliance auditing capabilities, using ESA's ESSB-ST-U-007 Space Debris Mitigation standard.

**Audience**: ESA evaluators, compliance officers, project managers
**Duration**: 10-15 minutes
**Prerequisites**: Python 3.10+, Souffle installed

---

## Setup (before the demo)

```bash
cd hnsm-backend
python examples/esa_demo.py
```

This generates `esa_demo_output/` with the complete audit package and static site.

Open `esa_demo_output/site/index.html` in a browser.

---

## Slide 1: "The Problem"

> "In space engineering, every compliance decision must be traceable.
> Current tools track requirements — but they don't prove why a mission
> is compliant or why it fails. That proof must be manually assembled."

**Key message**: The gap is not requirements management — it's **auditable reasoning**.

---

## Slide 2: "What We Built"

> "factpy is an auditable reasoning framework. You define compliance rules
> as formal logic. You provide mission data. The system tells you whether
> the mission is compliant — and proves exactly why, with a complete
> evidence trail."

Show the terminal output from `esa_demo.py`:
- 9 ECSS rules defined
- 2 missions created
- Compliance results: SENTINEL-7 ✅ / SWARM-9 ❌

---

## Slide 3: "The Rules" (2 minutes)

Show `summary.txt` or the script's rule definitions:

```
q.essb_u007_disposal_check:
  "Disposal success probability must be ≥ threshold"

q.essb_u007_collision_check:
  "Cumulative collision probability must be ≤ threshold"

q.essb_u007_passivation_check:
  "All energy sources must be passivated"

q.essb_u007_overall_compliance:
  "Mission is compliant if ALL of the above pass"
```

> "These rules are written once, in formal logic. They're the same rules
> you'd find in ESSB-ST-U-007 — but now they're machine-executable."

**Key message**: Rules are not AI-generated guesses. They are formally defined, auditable, deterministic.

---

## Slide 4: "The Data" (1 minute)

Two missions with different parameters:

| Parameter | SENTINEL-7 | SWARM-9 |
|-----------|-----------|---------|
| Profile | single | constellation |
| Disposal probability | 92% | 92% |
| Disposal threshold | 90% | **95%** (higher for constellations) |
| Collision probability | 0.05% | **0.12%** |
| Collision threshold | 0.1% | 0.1% |
| Passivation | complete | **incomplete** |

> "Same system, different missions, different results.
> SENTINEL-7 passes everything. SWARM-9 fails on three counts."

---

## Slide 5: "Compliant Case — Evidence Tree" (3 minutes)

Open the candidate evidence page for SENTINEL-7's overall compliance in the static site.

Point out:
1. **Root node**: "Derived Result — this candidate was derived as compliant"
2. **Rule references**: the system shows which child rules were invoked
3. **Support section**: the actual facts that matched each condition
4. **Assertion facts**: the specific values (920000 ppm, 500 ppm, "complete")

> "This is not just a yes/no answer. It's a complete proof chain —
> from the conclusion back to the individual facts that support it."

---

## Slide 6: "Certainty Scoring" (2 minutes)

Still on the candidate evidence page, point to the certainty section:

- **Aggregate certainty**: e.g., 0.5 (bottleneck)
- **Per-condition breakdown**: disposal weight=0.8 impact=0.68, collision weight=0.9 impact=0.63
- **Bottleneck identification**: the weakest condition is highlighted

> "Not all conditions are equally important. The rule author assigns
> weights, the system computes impact, and the bottleneck is automatically
> identified. This tells the reviewer where to focus attention."

---

## Slide 7: "Non-Compliant Case" (2 minutes)

Show the SWARM-9 non-compliance results from `summary.txt`:

```
SWARM-9: NON-COMPLIANT
  Failures:
  - Disposal probability 92% < 95% threshold (constellation)
  - Passivation status: incomplete
```

> "The system doesn't just say 'non-compliant'. It tells you exactly
> which conditions failed and why. This is what a compliance officer needs."

---

## Slide 8: "Engine Provenance — How the Engine Reasoned" (2 minutes)

Open one of the provenance JSON files in `esa_demo_output/provenance/`:

Show the proof tree structure:
```
RULE (R1): disposal_check_query(SENTINEL-7, 920000, 900000)
  RULE (R1): p_ecss_disposal__success__probability__ppm(SENTINEL-7, 920000)
    RULE (R1): chosen_asrt__...(SENTINEL-7, assertion_id)
      FACT: claim("assertion_id", "ecss:disposal_success_probability_ppm", ...)
      FACT: claim_arg("assertion_id", "0", "920000", ...)
  RULE (R1): p_ecss_disposal__success__threshold__ppm(SENTINEL-7, 900000)
    ...
  FACT: 920000 >= 900000
```

> "This is not our reconstruction — this comes directly from the Souffle
> reasoning engine. Every derivation step, every assertion used, every
> comparison checked. The engine itself proves its work."

---

## Slide 9: "The Full Audit Package" (1 minute)

Show the `esa_demo_output/` directory structure:

```
esa_demo_output/
├── audit/          ← Machine-readable audit package (JSONL)
├── site/           ← Static HTML audit site (open in any browser)
├── provenance/     ← Engine proof trees (JSON)
└── summary.txt     ← Human-readable compliance summary
```

> "Everything is exportable. The audit package is machine-readable
> for automated processing. The static site is human-readable
> for compliance review. No special software needed — just a browser."

---

## Slide 10: "What's Next"

> "We're applying to ESA's Open Discovery programme to explore:
> 1. Encoding additional ECSS standards
> 2. Testing on real mission data
> 3. Integration with existing requirements tools (DOORS)
> 4. LLM-assisted rule authoring for non-programmers"

---

## Handling Questions

**"Is this AI?"**
> "The reasoning engine is not AI — it's formal logic (Datalog), completely
> deterministic and reproducible. We do plan to add AI-assisted rule
> authoring (helping non-programmers write rules), but the reasoning
> itself is always formal and auditable."

**"What about ProbLog / probabilistic reasoning?"**
> "Our framework supports multiple reasoning engines. Souffle handles
> deterministic compliance. ProbLog can handle probabilistic risk
> assessment. Same audit trail, same traceability."

**"How does this compare to Rainbird?"**
> "Rainbird is a commercial expert system focused on decision automation.
> factpy is focused specifically on auditable reasoning for compliance —
> we produce exportable audit packages and engine provenance that
> Rainbird doesn't offer."

**"Can it handle real-scale ECSS standards?"**
> "We've validated on ESSB-ST-U-007 with 9 rules. The engine (Souffle)
> is designed for industrial-scale Datalog — it handles millions of facts.
> The next step is encoding larger standard subsets with real mission data."

**"What about negative reasoning — why did something fail?"**
> "We can derive explicit non-compliance rules that show exactly which
> conditions failed. Souffle also supports interactive negation explanation
> for deeper debugging."
