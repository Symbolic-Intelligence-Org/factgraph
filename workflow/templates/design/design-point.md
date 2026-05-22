# Design-Point: <topic>

- Status: working
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: candidate design / non-authoritative reference. **Not current behavior.** Becomes a constraint only when cited by an adopted decision, an implemented blueprint, current module docs (`src/factgraph/*/docs/`), or `workflow/foundations/architecture_principles.md`.
- Inputs:
  - <upstream design-points, external references, audit findings, user-conversation pointers>
- Outputs / Downstream:
  - <decisions / blueprints that will harvest this content; may be `- (none yet)` at first draft>
- Related:
  - <cross-references to sibling design-points or parallel work>

> **Authority reminder** (per Q2 §4.4): a design-point cannot directly override shipped behavior. Implementation must reach the codebase via the downstream consumption chain (decision → blueprint → impl), not by direct reference to this essay.

## 1. Problem framing

What concept or design area this essay explores. Why it matters. What is currently unclear or unsettled.

## 2. Context

Relevant background: shipped state, prior design-points, related decisions, external references. Concise — link more than explain.

## 3. Proposal / direction

The conceptual model, terminology, or design direction this essay advances. Iterative — may evolve in subsequent edits.

## 4. Open questions (if any)

Load-bearing questions that may become formal decisions in `workflow/design/decisions/`. Each gets a candidate Q-number for tracking.

## 5. Consequences / downstream implications

What changes downstream if this direction is adopted. Where decisions / blueprints would land.

## 6. Status notes

Drafting markers: `working` → `mature` (substantive iteration complete) → eventual archival (per Q2 §4.3 3-condition criteria: all load-bearing Qs closed + all impl-eligible content shipped + no active blueprint references it).
