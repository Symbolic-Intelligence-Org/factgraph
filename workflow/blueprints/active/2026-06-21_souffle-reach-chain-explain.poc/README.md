# PoC: souffle reach-chain feasibility

Feasibility evidence for [../2026-06-21_souffle-reach-chain-explain.md](../2026-06-21_souffle-reach-chain-explain.md).
Validated 2026-06-21 with `/opt/homebrew/bin/souffle` (arm64 native, no Rosetta).

## What it proves

The riskiest assumption of approach **S** (souffle-self-sufficient explain): **can souffle yield, in-engine, the failure value at a failed condition?** — answered **YES**.

A reach-chain (`reachᵢ :- reach_{i-1}, Aᵢ`, anchored to a fixed subject, each level carrying the accumulated bindings + asrt columns) lets one souffle run report, per subject:
- **holds(Aᵢ)** — subject present in `reachᵢ`; the real `asrt` rides along in the columns.
- **fails(A_{k+1})** — subject in `reach_k` but not `reach_{k+1}`; the **failure value / candidate fact is the `reach_k` tuple**.
- **not_reached** — upstream reach already empty.

Bindings thread coherently through the chain inside souffle (root cause of the old companion's "each atom picks a different fact" is gone).

## Reproduce

```sh
./run.sh        # generates facts, runs souffle, prints reach relations
```

## Captured output (2026-06-21)

```
# new_account: customer(c), tenure(c,td), td<90
na_r2:  C-EVE | 2000 | a_eve_c | a_eve_t     # last non-empty for C-EVE → FAILURE VALUE td=2000 (+ holds asrts)
na_r3:  C-M1  | 20                           # only C-M1 passes td<90; C-EVE/C-DANA absent (fail)

# forwards_out: customer(c), transfer by c, kind=out, amt>=20000
fo_r3:  C-DANA | Do | 4000 | a_do            # last non-empty for C-DANA → FAILURE VALUE amt=4000, witness Do, asrt a_do
fo_r4:  C-EVE | Eo | 28000 ;  C-M1 | M1o | 28000   # C-DANA absent (4000 < 20000, fail)
```

Validated: comparison-failure value (td=2000), pred-chain-failure value + witness (amt=4000, Do), holds-side asrt provenance carried throughout, coherent bindings, one run covering 2 branches × 3 subjects.

## Note

`reach.dl` is the **hand-written target shape**. Implementation generates it from `lowering_plan` (codegen). Fact/rule scoping (vs the current whole-package export) is a separate implementation concern (see blueprint §5.3 step 2). Recursion via `ruleref_links` is an open design point (§5.5).
