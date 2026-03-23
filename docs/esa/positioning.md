# factpy: Auditable Reasoning for Regulated Domains

## What It Is

factpy is an **auditable reasoning framework** — not an AI chatbot, not a black-box inference engine, and not a requirements management tool.

It takes formally defined compliance rules and factual data, runs them through a certified reasoning engine (Souffle Datalog), and produces a **complete, traceable audit trail** showing exactly *why* each conclusion was reached, down to the individual assertions that contributed.

## The Problem It Solves

In regulated domains like space engineering, compliance decisions must be:

- **Traceable**: every conclusion must be linked back to specific evidence
- **Auditable**: the reasoning process itself must be inspectable, not just the result
- **Reproducible**: the same inputs must always produce the same outputs
- **Explainable**: a non-technical reviewer must be able to understand *why*

Current tools (DOORS, Jama Connect, Polarion) manage requirements — they track *what* needs to be verified. But they don't answer the question: **"Given this specific mission data and these specific rules, is this mission compliant — and exactly why or why not?"**

That question requires a reasoning engine with full audit support. That's factpy.

## How It Works

```
1. DEFINE RULES
   ECSS compliance rules are expressed as formal logic (Datalog).
   Example: "Mission is compliant if disposal probability ≥ 90%
            AND collision probability ≤ 0.1%
            AND all energy sources are passivated."

2. PROVIDE FACTS
   Mission-specific data is entered as structured assertions.
   Each fact can carry metadata: source, date, confidence, analyst.
   Example: "SENTINEL-7 disposal probability = 92% (source: ESA Orbit Report)"

3. RUN COMPLIANCE CHECK
   The reasoning engine evaluates rules against facts.
   Derived conclusions are automatically classified as compliant or non-compliant.
   The engine tracks which rules fired, which facts matched, which conditions passed.

4. AUDIT THE RESULT
   Every conclusion comes with:
   - An evidence tree showing the complete proof structure
   - Certainty scores showing condition-level confidence
   - A human-readable narrative explanation
   - Souffle engine provenance showing the exact derivation chain
   - A static HTML audit site shareable with any reviewer (no software needed)
```

## What Makes It Different

| Capability | DOORS / Jama / Polarion | factpy |
|-----------|------------------------|--------|
| **Requirements tracking** | ✅ Core function | ✅ Supported (VCD predicates) |
| **Automated compliance reasoning** | ❌ Manual verification | ✅ Formal logic engine |
| **Evidence tree** | ❌ Not available | ✅ Hierarchical proof structure |
| **Engine provenance** | ❌ Not available | ✅ Souffle proof trees |
| **Certainty scoring** | ❌ Not available | ✅ Weighted condition impact |
| **Exportable audit package** | ⚠️ Document-based | ✅ Machine-readable + HTML |
| **Multi-engine support** | ❌ Single paradigm | ✅ Souffle (Datalog) + ProbLog (probabilistic) |
| **Reproducible reasoning** | ❌ Depends on reviewer | ✅ Deterministic formal logic |

**In one sentence**: DOORS tells you *what* needs to be checked. factpy tells you *whether it passes, why, and proves it*.

## Use Case: ESSB-ST-U-007 (Space Debris Mitigation)

We have a working demo with ESA's ESSB-ST-U-007 standard:

- **9 compliance rules** encoded as Datalog (disposal probability, collision probability, passivation, profile-dependent branching, top-level compliance composition)
- **2 mission scenarios**: SENTINEL-7 (single mission, compliant) and SWARM-9 (constellation, non-compliant — fails disposal threshold and passivation)
- **Full audit trail**: evidence trees, certainty scores, narrative explanations, engine provenance
- **Static HTML site**: openable in any browser, no installation needed

The demo runs in under 3 seconds and produces a complete audit package.

## Technology

- **Reasoning engine**: Souffle (Datalog) — deterministic, reproducible, formally grounded
- **Provenance**: Souffle `-t explain` produces recursive proof trees with assertion-level traceability
- **Certainty**: condition-level weighted impact scoring with bottleneck and additive aggregation
- **Export**: machine-readable audit packages (JSONL) + static HTML audit sites
- **Rule authoring**: Python DSL (SDK) or future LLM-assisted dialog
- **Architecture**: engine-agnostic framework — can plug in ProbLog (probabilistic) or other engines

## What We're Looking For

We are applying to ESA's Open Discovery programme to explore collaboration on:

1. **ECSS compliance automation**: encoding additional ECSS standards (ECSS-M-ST-10, ECSS-E-ST-10-02) as formal rules
2. **Integration with existing workflows**: connecting factpy to DOORS/requirements databases as data source
3. **Scaling validation**: testing on real mission data with ESA project teams
4. **Regulatory acceptance**: working with ESA compliance officers to validate the approach

## Contact

Raphael Feikert & ZhenZhi Li

factpy — Auditable Reasoning for Regulated Domains
