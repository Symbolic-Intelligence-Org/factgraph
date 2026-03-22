# Sub-Blueprint: Souffle Provenance Adapter V0

- Status: scoped
- Created: 2026-03-22
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/runner.py`
  - `src/factpy_kernel/adapters/souffle/engine_eval.py`
- Audit Log:
  - [2026-03-22_souffle-provenance-adapter-v0.audit.md](./2026-03-22_souffle-provenance-adapter-v0.audit.md)

## 1. Problem

Souffle provenance (`-t explain`) has been verified to produce:
- Full recursive derivation chains (evidence tree's blind spot)
- Negation reasoning (`!component_passivated("battery_2")`)
- Rule number annotations with rule text
- JSON output parseable via stdin pipe

Current evidence tree cannot show any of these. The gap is not theoretical — it was demonstrated on a real ECSS passivation rule with recursive component hierarchy.

This blueprint defines the **minimum viable adapter** to make Souffle provenance consumable, without prematurely committing to a cross-engine abstraction.

## 2. Goals

- Pipe Souffle `-t explain` commands after normal evaluation
- Parse JSON proof trees into a Souffle-specific data structure
- Make proof trees queryable alongside (not replacing) existing evidence tree
- Validate on 2 ECSS cases: flat disposal check + recursive passivation

## 3. Non-Goals (explicit boundaries)

- **No `ProofNode` universal abstraction** — name it `SouffleProofTreeV0`, not `ProofNode`
- **No core contract changes** — nothing enters `core/` public API
- **No audit durable format changes** — no new JSONL files in audit package yet
- **No existing evidence tree replacement** — coexistence only
- **No service endpoint changes** — no new explain API surface
- **No ProbLog/PyReason consideration** — single-engine, single-purpose
- **No narrative/NL integration** — proof tree is raw data, not presentation

## 4. Verified Souffle JSON Shape (from PoC)

### Inner node (derived fact)
```json
{
  "premises": "disposal_compliant(\"sentinel_7\", 920000)",
  "rule-number": "(R1)",
  "children": [...]
}
```

### Leaf node (base fact)
```json
{"axiom": "disposal_probability(\"sentinel_7\", 920000)"}
```

### Negation leaf
```json
{"axiom": "!component_passivated(\"battery_2\")"}
```

### Response envelope
```json
{
  "proof": { ... tree ... },
  "rules": [
    {"rule-number": "(R1)", "rule": "disposal_compliant(M,P) :- ..."}
  ]
}
```

## 5. Design

### 5.1 Data Structure (adapter-local)

```python
# In adapters/souffle/provenance.py

@dataclass(frozen=True)
class SouffleProofNode:
    """Single node in a Souffle proof tree. Adapter-local, NOT a core contract."""
    node_type: str          # "derived" | "axiom" | "negation"
    relation: str           # "disposal_compliant" | "has_sub_component" | ...
    args: tuple[str, ...]   # ("sentinel_7", "920000")
    rule_number: str | None # "(R1)" for derived, None for axiom
    children: tuple['SouffleProofNode', ...]  # empty for leaves

@dataclass(frozen=True)
class SouffleProofTree:
    """Complete proof response from Souffle -t explain."""
    query: str                          # "disposal_compliant(\"sentinel_7\", 920000)"
    root: SouffleProofNode
    rules: dict[str, str]               # {"(R1)": "disposal_compliant(M,P) :- ..."}
```

### 5.2 Runner Changes

**`run_package` signature and return type are unchanged.** It still returns a `Path` to `run_manifest.json`.

A NEW standalone function handles provenance:

```python
def run_provenance_explain(
    souffle_bin_path: Path,
    program_path: Path,
    facts_dir: Path,
    queries: list[str],
) -> list[SouffleProofTree]:
    """Run Souffle with -t explain and parse JSON proof trees.

    Completely independent of run_package. Does not modify any existing
    outputs. Callers who want provenance call this AFTER run_package.
    """
```

This function:
1. Runs Souffle with `-t explain` flag (separate subprocess from normal evaluation)
2. Pipes `format json` + `explain <query>` commands via stdin
3. Parses JSON responses into `SouffleProofTree` objects
4. Returns the list — caller decides what to do with it

Optionally, results can be written to an adapter-local sidecar file
(`outputs/provenance.json`) for later consumption, but this is NOT part
of `run_manifest.json` and NOT consumed by any existing code path.

### 5.3 Coexistence Contract

```
Current path (unchanged):
  evaluate → SupportArtifact → build_candidate_evidence_tree → evidence tree

New path (additive):
  evaluate → provenance_queries → SouffleProofTree → (raw, queryable)

Both paths produce output. Neither depends on the other.
The caller decides which to use.
```

### 5.4 Field Classification

| Field | Status | Notes |
|-------|--------|-------|
| `relation` + `args` | **Observed** — stable across all PoC tests | Direct parse from JSON |
| `rule_number` | **Observed** — present on all derived nodes | Maps to rule text via `rules` dict |
| `children` (recursive) | **Observed** — Souffle correctly expands recursive chains | Verified on passivation case |
| `negation` (axiom starting with `!`) | **Observed** — present in passivation case | `!component_passivated("battery_2")` |
| `node_type` | **Adapter convention** — derived from JSON shape | Not in JSON, inferred by parser |

**None of these are universal commitments.** They are Souffle-specific observations.

## 6. Implementation Plan

### Phase 1: Parser (adapters/souffle/provenance.py)
- `parse_souffle_proof_json(json_str) -> list[SouffleProofTree]`
- Handle inner nodes, axiom leaves, negation leaves
- Parse relation name + args from premise/axiom strings
- Map rule numbers to rule text

### Phase 2: Runner Integration (adapters/souffle/provenance.py or runner.py)
- New standalone `run_provenance_explain()` function
- Separate subprocess with `-t explain` + stdin pipe
- `run_package` signature and return type completely unchanged
- Optional sidecar file write (`outputs/provenance.json`)

### Phase 3: Validation Script (examples/)
- ECSS disposal check: compliant proof tree
- ECSS passivation: recursive non-compliant proof tree with negation
- Print human-readable tree representation
- Verify: every leaf is either an axiom fact or a negation

### Phase 4: Docs
- Update runner.py docstrings
- Add provenance section to adapter docs
- Update mother blueprint audit log

## 7. Acceptance Criteria

1. `parse_souffle_proof_json` correctly parses both PoC outputs (disposal + passivation)
2. `run_provenance_explain(...)` returns proof trees as a standalone call; `run_package` is completely unchanged
3. Recursive chain: `component_not_passivated("power_system")` shows full chain to `battery_2`
4. Negation: `!component_passivated("battery_2")` appears as a leaf node
5. Rule text: each derived node's `rule_number` maps to the correct rule body
6. Normal evaluation (without provenance_queries) is completely unchanged
7. No imports from `adapters/souffle/provenance.py` in `core/`, `service/`, or `audit/`

## 8. Upgrade Threshold (when to extract ProofNode v1)

Do NOT extract a universal `ProofNode` until ALL of:
- [ ] At least 3 real ECSS rules have been validated with provenance
- [ ] Recursive, negation, and flat cases all have stable field sets
- [ ] At least 1 non-Souffle engine (ProbLog) has been prototyped with its own proof format
- [ ] The delivery pipeline (narrative/NL/audit/static) has consumed `SouffleProofTreeV0` in at least 1 real surface
- [ ] The overlapping fields between Souffle and ProbLog have been explicitly compared

Until then, `SouffleProofTreeV0` stays in `adapters/souffle/` and is NOT promoted to `core/`.

## 9. Outcome

*Fill after implementation.*

- Final result:
- Deviations from blueprint:
- Archive notes:
