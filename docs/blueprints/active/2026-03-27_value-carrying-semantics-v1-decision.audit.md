# Decision Blueprint Audit: Value-Carrying Semantics v1

- Blueprint: [2026-03-27_value-carrying-semantics-v1-decision.md](./2026-03-27_value-carrying-semantics-v1-decision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | L3a decision-only. Initial draft had 6 decisions for numeric value-carrying. |
| 2026-03-27 | draft | 3 P1/P2 corrections | (1) D-VC4 downgraded to open question: PyReason rule parser treats multi-variable atoms as edges, no native value variable for nodes. (2) D-VC2/D-VC3 rewritten: value IS bound in PyReason, no independent payload channel; derived extraction produces bound summary, not preserved value. (3) D-VC1/D-VC5 narrowed: scope is bounded [0,1] values only, not arbitrary numerics; routing requires bounded domain contract, not just type_domain. |
| 2026-03-27 | draft | 2 P2/P3 consistency fixes | (1) D-VC5 routing condition: removed ambiguous ALL-of + OR structure; v1 requires numeric type_domain + bounded annotation + values in [0,1]; normalization registry fully deferred to v2. (2) Audit log first entry corrected to match current state. |
| 2026-03-27 | scoped | Approved | 5 frozen decisions (D-VC1/2/3/5/6) + 1 open question (D-VC4). Partial supersession of #49 (D7) confirmed. |
