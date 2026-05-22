# Sub-Blueprint: ESA Demo Packaging

- Status: implemented
- Created: 2026-03-23
- Parent Blueprint:
  - [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Audit Log:
  - [2026-03-23_esa-demo-packaging.audit.md](./2026-03-23_esa-demo-packaging.audit.md)

## 1. Problem

Engine capabilities are validated: 9 ECSS rules, Souffle provenance on flat + composed rules, certainty v1, static HTML audit site. But there is no **展示级** deliverable that a non-technical ESA evaluator can look at and understand.

ESA explicitly asked for:
- "a concrete use case with a clear advantage compared to other solutions"
- "a clear distinction between your tool and similar technologies"
- "a clearer picture of how a user would interact with the tool"
- "more high-level and understandable for people without a background in formal logic"

## 2. Goal

Produce a self-contained demo package that answers all four ESA requests. Engineering work only if it directly improves the demo.

## 3. Non-Goals

- ProofNode v1 or provenance pipeline integration
- New certainty features
- Probability lane
- Frontend dialog / knowledge graph visualization (separate project)
- Production deployment

## 4. Deliverables

### D1: Demo Script (standalone, runnable)

`examples/esa_demo.py` — a single Python script that:

1. Defines ECSS schema + 9 rules
2. Creates two missions (SENTINEL-7 compliant, SWARM-9 non-compliant)
3. Evaluates all compliance checks
4. Exports audit package
5. Generates static HTML audit site
6. Runs Souffle provenance on key rules
7. Prints a structured summary to stdout

**Output directory**: `esa_demo_output/` containing:
- `audit/` — full audit package
- `site/` — static HTML audit site (openable in browser)
- `provenance/` — proof tree JSON files
- `summary.txt` — human-readable compliance summary

### D2: Static HTML Polish

Template-only changes to the generated HTML surfaces to make the demo site presentable:

- Demo landing page is branded for the ESA walkthrough
- Candidate evidence pages emphasize verdict, rule chain, and audit context
- Certainty bars use green/yellow/red coloring based on impact level
- Compliance status is clearly visible where the candidate binding exposes it

Out of scope for this phase:

- DTO enrichment for human-readable mission names
- Any change that requires modifying audit package shape or query DTOs

### D3: One-Page Positioning Document

`docs/esa/positioning.md` — answers ESA's questions:

1. **What it does**: auditable reasoning framework for compliance checking
2. **How it works**: rules → facts → derivation → evidence tree → audit trail
3. **vs DOORS/Jama**: those are requirements management; factpy is reasoning + audit
4. **User interaction**: rule definition (DSL or future LLM dialog) → compliance result → audit site
5. **Use case**: ESSB-ST-U-007 compliance verification with full traceability

### D4: Walkthrough Document

`docs/esa/demo_walkthrough.md` — step-by-step guide for demo presentation:

1. "Here's a space mission with specific parameters"
2. "Here are the ECSS compliance rules encoded in our system"
3. "We run the compliance check — SENTINEL-7 passes, SWARM-9 fails"
4. "For each check, here's the complete evidence tree showing WHY"
5. "For each check, here's the Souffle proof tree showing HOW the engine derived it"
6. "Everything is auditable — exported as a package, viewable as a static site"
7. "No black box — every step is traceable"

## 5. Acceptance Criteria

1. `python examples/esa_demo.py` runs end-to-end without errors
2. `esa_demo_output/site/index.html` is openable in a browser and presentable
3. Candidate evidence pages show compliance status + evidence tree + certainty
4. At least one provenance proof tree is viewable (disposal check)
5. `docs/esa/positioning.md` answers all 4 ESA questions
6. `docs/esa/demo_walkthrough.md` is followable by someone who hasn't seen the code
7. No changes to `src/factpy_kernel/` core code (static_ui.py polish allowed)

## 6. Implementation Phases

### Phase 1: Demo Script
- Create `examples/esa_demo.py`
- Verify it produces complete output directory

### Phase 2: Static HTML Polish
- Template/CSS/text improvements for presentation quality
- Demo landing page branding
- Candidate evidence status + certainty emphasis

### Phase 3: ESA Documents
- `docs/esa/positioning.md`
- `docs/esa/demo_walkthrough.md`

### Phase 4: Verification
- Run demo end-to-end
- Open site in browser, screenshot key pages
- Review walkthrough for clarity
