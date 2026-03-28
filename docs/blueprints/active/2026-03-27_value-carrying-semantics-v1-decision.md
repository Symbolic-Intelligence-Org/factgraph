# Decision Blueprint: Value-Carrying Semantics v1

- Status: scoped
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md) (L3a)
- Supersedes:
  - Contract #49 (D7): partially — D7's existence model remains default; this decision extends it for bounded numeric predicates
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/where_compile.py` — WhereIR → PyReason compiler
  - `src/factpy_kernel/adapters/pyreason/runner.py` — graph builder + derived extraction
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py` — EDB materialization
  - `src/factpy_kernel/adapters/pyreason/session.py` — fact write API
- Audit Log:
  - [2026-03-27_value-carrying-semantics-v1-decision.audit.md](./2026-03-27_value-carrying-semantics-v1-decision.audit.md)

## 1. Problem

v0 uses an attribute-existence model (D7/contract #49):
- Node fact: `graph.nodes[ref][pred] = 1` — value is discarded
- Derived extraction: outputs `"true"/"false"` — no actual values
- WhereIR compiler: `popular(X)` — no value variable

This was correct for v0 PoC but limits PyReason to binary classification.

## 2. PyReason Engine Constraints (verified from source)

Before making decisions, these are verified facts about PyReason's native semantics:

### 2.1 Graph ingest

`graphml_parser.py` interprets graph attributes as follows:
- Numeric value in `[0, 1]` → becomes the **bound** for that label (truth degree)
- Numeric value outside `[0, 1]` → becomes a **new label** with key-value encoding
- String value → becomes label name, bound defaults to `[1.0, 1.0]`

**Implication**: There is no independent "payload value channel" separate from bound. When we write `graph.nodes["Alice"]["risk_score"] = 0.85`, PyReason interprets `0.85` as the **truth degree of `risk_score`**, not as "the risk score value is 0.85".

### 2.2 Rule parser

`rule_parser.py` determines atom type by variable count:
- 1 variable → node predicate
- 2+ variables → edge predicate or comparison

**Implication**: `risk_score(X, V)` is NOT "node predicate with value variable" — PyReason parses it as a **binary relation**. There is no native "value variable" concept for node predicates.

### 2.3 What "value-carrying" actually means in PyReason

In PyReason's model, a fact's "value" IS its bound interval. `risk_score(Alice) = [0.85, 0.85]` means "the truth degree of `risk_score` for Alice is 0.85". This is simultaneously the value and the certainty — they are not separable within the engine.

## 3. Decisions to Freeze

### D-VC1: Scope — PyReason-native bounded numeric semantics

**Decision**: v1 extends D7 for predicates whose values naturally map to PyReason's `[0, 1]` bound domain. This means normalized truth-degree-like values only — not arbitrary numerics.

**What qualifies (v1)**:
- Values that are naturally in `[0, 1]`: probabilities, confidence scores, risk scores, similarity measures
- Predicate must be explicitly annotated as bounded in schema

**What does NOT qualify**:
- Arbitrary numerics: `amount_eur=2300000`, `count=42` — no natural bound representation
- String values: `name="Alice"` — no bound representation
- Values outside `[0, 1]` even if numeric — normalization registry is deferred to v2

**Routing condition (v1)**: 3 hard AND conditions per D-VC5:
1. `type_domain` is numeric
2. Predicate explicitly annotated as bounded
3. Values guaranteed in `[0, 1]`

**Impact**: D7 (existence model) remains the default. Bounded numeric is an extension, not a replacement.

### D-VC2: Graph materialization — value IS bound, not separate

**Decision**: For bounded numeric predicates, the session value is stored as the **graph attribute value**, which PyReason interprets as the label's bound.

```
Current (D7):  graph.nodes["Alice"]["risk_score"] = 1       ← existence flag
New (D-VC2):   graph.nodes["Alice"]["risk_score"] = 0.85    ← truth degree
```

**Critical clarification**: In this model, `0.85` is simultaneously:
- The **value** of the assertion (framework perspective: "risk_score is 0.85")
- The **bound** of the label (PyReason perspective: "truth degree of risk_score is [0.85, 0.85]")

The framework records both interpretations via Annotation Store:
- `pyreason/semantic/bound_lower = 0.85` — engine-native truth degree
- `shared/derived/confidence = 0.85` — framework-level confidence (derived from bound)

There is no independent "value channel" in the graph. The framework preserves the original `value` field in the Ledger claim, but the graph materialization collapses it to bound.

### D-VC3: Derived extraction — bound summary, not preserved value

**Decision**: `_extract_derived_facts()` extracts the **derived bound** from PyReason interpretation, not an independently preserved "actual value".

```python
# Bounded numeric predicate: extract bound as derived value
derived_value = str(lower_bound)  # e.g., "0.85"
# This is the derived truth degree, not a preserved input value
```

For non-bounded predicates: unchanged (`"true"/"false"` existence extraction).

**Honest framing**: What we call "value extraction" is actually "reading back the PyReason-computed bound summary". The engine does not preserve the input value independently — it computes a new bound through reasoning. The derived value is the engine's conclusion, not a passthrough.

### D-VC4: Value variables in rule syntax — CLOSED (infeasible in v1)

**Decision**: D-VC4 is **closed as infeasible** on PyReason's current public surface.

**Research spike findings** (verified from PyReason v3.0.0 source):
- `rule_parser.py:118`: variable count hardcoded as node/edge classifier — `len(head_variables) == 1` → node, else edge
- No annotation, configuration, or API to override this classification
- Label suffix comparison mechanism exists but is **deprecated** (`temp.py` — multiple `DEPRECATED` markers)
- Interpretation output contains only `Dict[label] → Interval([lo, hi])` — no independent value channel

**Workarounds considered and rejected**:
- Label suffix encoding (`risk_score_0.7`): depends on deprecated mechanism, label explosion
- Synthetic edge predicates (`has_risk_score(User, Score)`): semantic distortion, dummy nodes
- Both violate the principle that framework entity semantics should not be warped for engine constraints

**Consequence for L3b**: Value-carrying in v1 is limited to:
- Bounded graph materialization (D-VC2) — `= value` instead of `= 1`
- Bound summary extraction (D-VC3) — derived value = lower_bound
- Schema-driven routing (D-VC5) — bounded domain contract
- NO value variables in rule syntax
- NO rule-level numeric comparison

**Not "never possible"**: If upstream PyReason changes its parser/data model, or if a future adapter-internal encoding experiment succeeds, D-VC4 can be reopened as a new research spike. But v1 must not depend on it.

### D-VC5: Schema-driven routing — bounded domain contract

**Decision**: The compiler/runner uses a **bounded domain contract** to route predicates, not just `type_domain`.

A predicate qualifies for bounded numeric treatment in v1 when ALL of:
1. `type_domain` is numeric (`float64`, `float32`, or similar)
2. The predicate is explicitly annotated as bounded (e.g., `bounded=True` in schema)
3. Values are guaranteed to be in `[0, 1]`

Normalization registry (mapping arbitrary ranges to `[0, 1]`) is deferred to v2.

**Fallback**: Any predicate that does not satisfy the bounded domain contract uses existence-based materialization (D7).

### D-VC6: Backward compatibility — existence model as default

**Decision**: Unchanged from original draft. D7 remains the default. Bounded numeric is an opt-in extension via schema annotation, not a breaking change.

**Supersession clause**: Contract #49 (D7) is partially superseded: its existence model is no longer the ONLY materialization strategy, but it remains the default fallback for all predicates that do not satisfy the bounded domain contract.

## 4. What this does NOT decide

- **Value variables in rule syntax** — D-VC4 closed as infeasible (PyReason parser constraint)
- **CompareExpr compilation** — not feasible without value variables; deferred beyond v1
- **Arbitrary numeric encoding** — values outside `[0, 1]` (amounts, counts) not addressed
- **String value encoding** — no attempt to encode strings as bounds
- **Normalization registry** — deferred to v2
- **Multi-valued predicates** — not addressed
- **ProbLog value-carrying** — PyReason-specific decision
- **Rule.engine_ext** — now implemented as the shared definition-time carrier; this decision still does not reopen value variables or broader rule-syntax transport

## 5. Impact Assessment

### Files that change in L3b implementation

| File | Change |
|------|--------|
| `adapters/pyreason/runner.py` | Graph builder: `= value` for bounded preds. Derived extraction: bound summary. |
| `adapters/pyreason/engine_eval.py` | EDB materialization: check bounded domain contract |

### Files that do NOT change (confirmed by D-VC4 closure)

| File | Why |
|------|-----|
| `adapters/pyreason/where_compile.py` | D-VC4 closed — no value variables in rule syntax |
| `adapters/pyreason/session.py` | Session already handles float values; no additional validation needed |

### Files that do NOT change

| File | Why |
|------|-----|
| `core/store/types.py` | No core changes |
| `core/store/_evaluate.py` | No core changes |
| `sdk/dsl/rule.py` | No DSL changes |
| `audit/static_ui.py` | Annotation rendering already handles arbitrary values |

## 6. Acceptance Criteria

- [x] D-VC1 through D-VC3, D-VC5, D-VC6 reviewed and approved (5 frozen decisions)
- [x] D-VC4 closed as infeasible via research spike — PyReason parser evidence definitive
- [ ] Partial supersession of contract #49 (D7) is clear: default preserved, extension added
- [ ] PyReason engine constraints (§2) verified and accepted as design constraints
- [ ] Bounded domain contract (D-VC5) understood: not just type_domain, must be [0,1]
