# What-If and Proof

This page covers the nine methods on `fg.what_if.*` and `fg.audit.*`
that answer counterfactual and proof-explanation questions about your
data without writing to the ledger.

For the broader API reference see
[`04_api_surface.en.md`](04_api_surface.en.md).
For walker views and recorder lifecycle see
[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md).

---

## The Five Questions

The what-if surface is organized around five questions a user typically
asks about a derivation:

| # | Question | Method |
|---|---|---|
| Q1 | Does this fact derive given the current store and rules? | `fg.what_if.check` |
| Q2 | If a fact derives, **why** does it derive? | `fg.what_if.diagnose` |
| Q3a | What happens if I changed a fact value? | `fg.what_if.fact_overlay.check` |
| Q3b | What happens if I changed the rule structure? | `fg.what_if.rule.{disable, literal_replace, add_condition}` |
| Q4 | Across this finite candidate universe, what does **not** derive, and why? | `fg.what_if.why_not` |
| Q5 | Between two recorded rounds, how did derivation outcomes change? | `fg.audit.diff_proof_frames` |

These are independent operations. Each returns a frozen application DTO
that carries the result and an `evidence_envelope` with the underlying
proof structure.

---

## Running Example

The walkthrough below uses one schema:

```python
from kernel.sdk import Entity, FactGraph, Field, Identity, Rule, Pred, vars

class Country(Entity):
    code: str = Identity(primary_key=True)
    official_language: str = Field(cardinality="single")

class Person(Entity):
    pid: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    lives_in: str = Field(cardinality="single")  # Country.code

# Derivation: a Person speaks the official language of the Country they live in.
person, country, lang = vars("person", "country", "lang")
speaks_rule = Rule(
    head=Pred("speaks", person, lang),
    body=[
        Pred("Person", person, lives_in=country),
        Pred("Country", country, official_language=lang),
    ],
)
speaks = Derivation(rules=[speaks_rule])

fg = FactGraph.from_schema_classes([Country, Person])

# Seed data
fg.ingest([
    {"entity": "Country", "code": "FR", "official_language": "French"},
    {"entity": "Country", "code": "DE", "official_language": "German"},
    {"entity": "Person", "pid": "p-alice", "name": "Alice", "lives_in": "FR"},
    {"entity": "Person", "pid": "p-bob", "name": "Bob", "lives_in": "DE"},
])
```

We will use this `fg` and `speaks` for the rest of the page.

---

## Q1: Does it derive? — `fg.what_if.check`

```python
result = fg.what_if.check(speaks, binding={"$person": "p-alice", "$lang": "French"})

result.status              # "satisfied" | "unsatisfied" | "invalid_request" | ...
result.evidence_envelope   # SupportArtifact in .engine_payload
```

`binding` keys are `$`-prefixed variable names. `engine` defaults to
`"native"`; pass `engine="souffle"` etc. to use an adapter.

**Use when**: you have a specific candidate fact in mind and want a
yes/no plus the evidence trail.

**Returns**: `CheckResult`. The proof support lives in
`result.evidence_envelope.engine_payload` as a `SupportArtifact`. Hold
on to that artifact if you plan to recheck it later under an overlay
(see Q3a).

---

## Q2: Why did it derive? — `fg.what_if.diagnose`

```python
diag = fg.what_if.diagnose(speaks, binding={"$person": "p-alice", "$lang": "French"})

diag.status                # "ok" | "no_support" | ...
diag.derivation_trace      # the per-rule firing trace
diag.evidence_envelope     # SupportArtifact with locator chain
```

`diagnose` runs an explanation pass independent of `check` (it does not
call `check` internally). When the binding is satisfiable it returns
the proof trace; when it isn't it returns a `no_support` status with
diagnostics about which body literal failed to bind.

**Use when**: `check` returned `satisfied` and you want a structured
explanation, or returned `unsatisfied` and you need to know which body
literal blocked it.

---

## Q3a: What if a fact were different? — `fg.what_if.fact_overlay.check`

```python
from kernel.application.protocol import EvaluationOverlay, FactOverlayAction

# Counterfactual: what if FR's official language were Spanish?
overlay = EvaluationOverlay(
    fact_actions=(
        FactOverlayAction(
            entity="Country",
            identity={"code": "FR"},
            field="official_language",
            value="Spanish",
        ),
    ),
)

cf = fg.what_if.fact_overlay.check(
    speaks,
    binding={"$person": "p-alice", "$lang": "Spanish"},
    overlay=overlay,
)

cf.status                  # status under the overlay
cf.evidence_envelope       # SupportArtifact under the overlay
```

`overlay` must be an `EvaluationOverlay`. The
`tuple[FactValueOverride, ...]` form is rejected at the SDK boundary.

**Use when**: you want to test a hypothetical without writing or
retracting any assertion. The overlay is purely in-memory for the
duration of the call.

---

## Q3a continued: re-check a held proof — `fg.what_if.fact_overlay.recheck_proof_frame`

```python
# From an earlier check (Q1 above):
support_artifact = result.evidence_envelope.engine_payload

recheck = fg.what_if.fact_overlay.recheck_proof_frame(
    support_artifact,
    overlay,
)
recheck.status             # whether the same proof still stands under the overlay
recheck.frame_delta        # changed atoms / branches
```

This shell does not lower a derivation. It walks the held
`SupportArtifact` and re-evaluates each leaf under the overlay. There
is no `engine` argument and no registry resolution.

**Use when**: you have a proof from an earlier `check` (or from an
audit log) and want to test "would this same proof still stand if we
overlaid these changes?" — much cheaper than re-running `check` from
scratch.

---

## Q3b: What if the rule were different? — `fg.what_if.rule.*`

Three rule mutations are supported. All accept the SDK `Rule` you want
to mutate (lowered internally; raw `RuleSpec` IR is rejected) plus a
`SupportArtifact` from a prior `check`.

### Disable a body literal

```python
disabled = fg.what_if.rule.disable(
    speaks_rule,
    support_artifact,
    branch_index=0,
    atom_index=0,    # disable the first body atom
)
disabled.status            # "satisfied" if the proof still works without that atom
```

`branch_index` selects the body branch (only `0` for non-disjunctive
rules); `atom_index` selects the body atom to disable.

### Replace a literal

```python
from kernel.application.protocol import RuleLiteralPath

replaced = fg.what_if.rule.literal_replace(
    speaks_rule,
    support_artifact,
    branch_index=0,
    atom_index=1,      # the Country atom
    literal_path=RuleLiteralPath(field="official_language"),
    old_literal=lang,  # the variable being replaced
    new_literal="French",
)
```

`literal_path` is a `RuleLiteralPath` from `kernel.application.protocol`.
Anything else slips past SDK pre-validation and is caught by the
runtime as `ProtocolShapeError` — surface symptom is an
`SDKStoreError(path="$.check_rule_literal_replace.request")`.

### Add a condition

```python
from kernel.application.protocol import RuleAddedAtom

added = fg.what_if.rule.add_condition(
    speaks_rule,
    support_artifact,
    branch_index=0,
    added_atom=RuleAddedAtom(
        predicate="Person",
        positional=(person,),
        keyword={"name": "Alice"},
    ),
)
```

Note: there is **no** `atom_index` argument. `add_condition` appends
the new atom at the end of the branch.

**Use when** (any of the three): you're prototyping a rule change and
want to see whether an existing proof still holds (or how it would
break) without committing the rule edit to the registry.

---

## Q4: What does not derive across a universe? — `fg.what_if.why_not`

```python
candidates = [
    {"person": "p-alice", "lang": "Spanish"},
    {"person": "p-bob",   "lang": "French"},
    {"person": "p-alice", "lang": "French"},   # this one DOES derive
]

wn = fg.what_if.why_not(speaks, candidates)

wn.status                 # overall status
for verdict in wn.candidate_verdicts:
    verdict.candidate     # the candidate dict
    verdict.status        # "satisfied" | "unsatisfied"
    verdict.diagnosis     # if unsatisfied, why not
```

`why_not` requires you to supply the finite candidate universe
explicitly — it does not auto-discover. Each candidate is a `Mapping`
of variable names (without `$` prefix) to values.

**Use when**: you have a finite set of candidates and want to know
which ones derive, which don't, and for each that doesn't, which body
literal blocked it. Useful for compliance "did anything fall through
the cracks" checks.

`why_not` rejects `CompiledDerivationPlan` at the SDK boundary; pass
the SDK `Derivation` directly.

---

## Q5: How did derivation change between rounds? — `fg.audit.diff_proof_frames`

```python
from kernel.audit import load_audit_package

# Two recorded rounds are loaded from disk (or held from a recorder).
events_a = load_audit_package("/path/to/round_a/")["events"]
events_b = load_audit_package("/path/to/round_b/")["events"]

diff = fg.audit.diff_proof_frames(
    round_a_id="round-a",
    round_b_id="round-b",
    round_a_events=events_a,
    round_b_events=events_b,
)

diff.added_frames           # frames present in B but not A
diff.removed_frames         # frames present in A but not B
diff.changed_frames         # frames whose proof structure changed
```

`diff_proof_frames` is pure: no store, no registry, no engine, no IO.
It only requires the two event tuples. `include_unchanged=True`
includes also the frames whose status was identical between rounds
(off by default).

**Use when**: comparing audit logs across runs to surface what changed
— useful for regression review, governance reporting, and rule-edit
impact analysis.

---

## Recording rounds (for Q5)

Q5 consumes events from the recorder. The recorder lifecycle
(`start_round`, `record_round_event`, `finalize_round`) is intentionally
**not** part of `kernel.sdk`. Import it directly:

```python
from kernel.audit.round_events import start_round, record_round_event, finalize_round
```

See [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for
the recorder pattern and rationale.

---

## Walker views (advanced)

For richer in-process navigation of a `ProofFrameDiff` (e.g.
"give me all changed frames whose head predicate is `speaks`"), use
`kernel.application.walker.ProofFrameDiffView`. The SDK does not
auto-wrap because not every caller wants the cost. See
[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md).

---

## Errors

All nine methods raise `SDKStoreError` for inputs that fail SDK-side
validation. The error's `.path` attribute uses JSON-pointer-style
locators rooted at the method name; for example a bad overlay on
`fact_overlay.check` raises `SDKStoreError(path="$.check_fact_overlay.overlay")`.
Inner runtime exceptions chain via `__cause__`.

A method that runs but the runtime decides "this is unsupported on
this input" returns a result DTO with `status="invalid_request"` or
`status="unsupported"` rather than raising. Always inspect `.status`
before consuming the rest of the result.
