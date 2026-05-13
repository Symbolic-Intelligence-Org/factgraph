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
asks about a inference:

| # | Question | Method |
|---|---|---|
| Q1 | Does this fact derive given the current store and rules? | `fg.what_if.check` |
| Q2 | If a fact derives, **why** does it derive? | `fg.what_if.diagnose` |
| Q3a | What happens if I changed a fact value? | `fg.what_if.fact_overlay.check` |
| Q3b | What happens if I changed the rule structure? | `fg.what_if.rule.{disable, literal_replace, add_condition}` |
| Q4 | Across this finite candidate universe, what does **not** derive, and why? | `fg.what_if.why_not` |
| Q5 | Between two recorded rounds, how did inference outcomes change? | `fg.audit.diff_proof_frames` |

These are independent operations. Each returns a frozen application DTO
that carries the result and an `evidence_envelope` with the underlying
proof structure.

---

## Running Example

The walkthrough below uses one schema and one Inference:

```python
from factpy.sdk import Inference, Entity, FactGraph, Field, Identity, Relationship, vars

class Country(Entity):
    code: str = Identity(primary_key=True)
    official_language: str = Field(cardinality="single")

class Person(Entity):
    pid: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    lives_in: str = Field(cardinality="single")  # entity_ref to Country

class Speaks(Relationship):
    person: str = Identity(primary_key=True)
    language: str = Identity(primary_key=True)

fg = FactGraph.create(schema_classes=[Country, Person, Speaks])

# Inference: a Person speaks the official language of the Country they live in.
with vars("p", "c", "lang") as (p, c, lang):
    speaks = Inference(
        id="drv.speaks",
        version="1.0.0",
        where=[
            Person(p),
            Country(c),
            p.lives_in == c,
            c.official_language == lang,
        ],
        head=Speaks(person=p, language=lang),
    )

# Seed data — canonical ingest item shape ({kind, field, e_ref, value})
ref_fr      = fg.read.ref(Country, code="FR")
ref_de      = fg.read.ref(Country, code="DE")
ref_alice   = fg.read.ref(Person,  pid="p-alice")
ref_bob     = fg.read.ref(Person,  pid="p-bob")

fg.ingest([
    {"kind": "set", "field": Country.official_language, "e_ref": ref_fr, "value": "French"},
    {"kind": "set", "field": Country.official_language, "e_ref": ref_de, "value": "German"},
    {"kind": "set", "field": Person.name,     "e_ref": ref_alice, "value": "Alice"},
    {"kind": "set", "field": Person.lives_in, "e_ref": ref_alice, "value": ref_fr},
    {"kind": "set", "field": Person.name,     "e_ref": ref_bob,   "value": "Bob"},
    {"kind": "set", "field": Person.lives_in, "e_ref": ref_bob,   "value": ref_de},
])
```

We will use this `fg` and `speaks` for the rest of the page.

For the Rule/Query/Inference DSL deep-dive see
[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md);
for the canonical ingest item shape see
[`02_readwrite_and_ingest.en.md` §7.1](02_readwrite_and_ingest.en.md).

---

## Q1: Does it derive? — `fg.what_if.check`

```python
result = fg.what_if.check(speaks, binding={"$p": ref_alice, "$lang": "French"})

result.status              # "passed" | "failed" | "unsupported" | "invalid_request"
result.matched_count       # int | None — number of matched bindings (None on unsupported / invalid_request)
result.matched_binding     # BindingItems | None — the matched values when status="passed"
result.evidence_envelope   # EvidenceEnvelope | None — engine_payload is a SupportArtifact for native engine
```

`binding` keys are `$`-prefixed variable names matching the
Inference's `where` vars (here `$p` and `$lang`). `engine` defaults to
`"native"`; pass `engine="souffle"` etc. to use an adapter.
Track 1 makes public SDK inferences single-head; define one inference
per head before using `check`, `diagnose`, Fact Overlay, or `why_not`.
Track 3 / E intentionally keeps the what-if shells profile-free:
`semantics=` and `semantics_profile=` are rejected here. Use
`fg.eval.evaluate(..., semantics=ProbLogSemantics(...))`,
`fg.eval.evaluate(..., semantics=PyReasonSemantics(...))`, or the
advanced/canonical `SemanticsProfile` shape for direct semantics-backed
inference evaluation.

**Use when**: you have a specific candidate fact in mind and want a
yes/no plus the evidence trail.

**Returns**: `CheckResult`. The proof support lives in
`result.evidence_envelope.engine_payload` (a `SupportArtifact` for
native runs, or a `ProvenanceEnvelope` for some adapter paths). Hold
on to the SupportArtifact if you plan to recheck it later under an
overlay (see Q3a).

---

## Q2: Why did it derive? — `fg.what_if.diagnose`

```python
diag = fg.what_if.diagnose(speaks, binding={"$p": ref_alice, "$lang": "French"})

diag.status                # "passed" | "failed" | "unsupported" | "invalid_request"
diag.matched_count         # int | None
diag.matched_binding       # BindingItems | None — populated when status="passed"
diag.failure_kind          # "no_candidate" | "atom_localized" | None — populated when status="failed"
diag.diagnostic_payload    # DiagnoseAtomLocator | None — populated when failure_kind="atom_localized"
```

When `failure_kind="atom_localized"`, `diagnostic_payload` is a
`DiagnoseAtomLocator(branch_index, failed_atom_index, attempted_binding)`
pointing at which body atom blocked the proof.

`diagnose` runs an explanation pass independent of `check` (it does
not call `check` internally) and **does not carry an
EvidenceEnvelope** — by design, callers wanting Check's evidence on
a `passed` binding invoke Check separately.

When `status="passed"` you get `matched_count >= 1` and a populated
`matched_binding`; when `status="failed"` with
`failure_kind="atom_localized"`, `diagnostic_payload` localizes the
blocking atom; when `status="unsupported"` or `"invalid_request"`,
inspect `diag.errors` (`tuple[ErrorDTO, ...]`).

**Use when**: `check` returned `passed` and you want a structured
match, or returned `failed` and you need to know which body atom
blocked it.

---

## Q3a: What if a fact were different? — `fg.what_if.fact_overlay.check`

```python
from factpy.application.protocol import EvaluationOverlay, FactValueOverride

# Counterfactual: what if FR's official language were Spanish?
# The overlay needs to point at the actual asrt_id that holds the current value.
fr = fg.read.get(Country, code="FR")
assert fr is not None
fr_lang_asrt_id = (
    fr.field("official_language")
    .active
    .where(value="French")
    .one()
    .asrt_id
)

overlay = EvaluationOverlay(
    fact_actions=(
        FactValueOverride(
            asrt_id=fr_lang_asrt_id,
            pred_id="country:official_language",
            e_ref=ref_fr,
            old_fact_tuple=(ref_fr, "French"),
            new_fact_tuple=(ref_fr, "Spanish"),
            note="counterfactual",
        ),
    ),
    rule_actions=(),
)

cf = fg.what_if.fact_overlay.check(
    speaks,
    binding={"$p": ref_alice, "$lang": "Spanish"},
    overlay=overlay,
)

cf.status              # "passed" | "failed" | "unsupported" | "invalid_request"
cf.before              # OverlayCheckPhase | None — Q1 result on the unchanged store
cf.after               # OverlayCheckPhase | None — Q1 result with the overlay applied
cf.diff                # OverlayCheckDiff | None — bindings added/removed under the overlay
```

`overlay` is an `EvaluationOverlay` with `fact_actions` (a tuple of
`FactValueOverride | FactRemoveAction`) and `rule_actions` (a tuple
of `RuleDisableAction | RuleLiteralReplaceAction | RuleAddConditionAction`).
`FactOverlayAction` is the type alias for the fact-action union; the
`FactValueOverride` constructor needs the existing `asrt_id` plus the
old / new fact tuples. The SDK shell also accepts a bare
`tuple[FactValueOverride, ...]` for the overlay arg as a convenience
form (it wraps it into an `EvaluationOverlay` internally).

**Use when**: you want to test a hypothetical without writing or
retracting any assertion. The overlay is purely in-memory for the
duration of the call. The `before`/`after`/`diff` triple lets the
caller see exactly what the overlay changed at the binding level.

---

## Q3a continued: re-check a held proof — `fg.what_if.fact_overlay.recheck_proof_frame`

```python
# From an earlier check (Q1 above):
support_artifact = result.evidence_envelope.engine_payload

recheck = fg.what_if.fact_overlay.recheck_proof_frame(
    support_artifact,
    overlay,
)
recheck.status            # ProofFrameStatus: "still_valid" | "invalidated" | "unknown"
recheck.binding_items     # BindingItems — the binding the artifact was built for
recheck.atom_verdicts     # tuple[ProofFrameAtomVerdict, ...] — per-atom verdict under the overlay
```

`status` aggregates the atom verdicts:
- `"still_valid"` — every atom still holds; the proof stands.
- `"invalidated"` — at least one atom flipped; the proof breaks.
- `"unknown"` — the overlay touched something the recheck can't
  re-evaluate without re-running the engine.

This shell does not lower a inference. It walks the held
`SupportArtifact` and re-evaluates each leaf under the overlay. There
is no `engine` argument and no registry resolution.

**Use when**: you have a proof from an earlier `check` (or from an
audit log) and want to test "would this same proof still stand if we
overlaid these changes?" — much cheaper than re-running `check` from
scratch.

---

## Q3b: What if the rule were different? — `fg.what_if.rule.*`

Three rule mutations are supported. All accept an SDK `Rule` to mutate
(lowered internally; raw `RuleSpec` IR is rejected) plus a
`SupportArtifact` from a prior `check`. All three return a result DTO
with the same shape: `(status, variant_rows, proof_frame, errors,
warnings)` — `status` is `"completed" | "unsupported" | "invalid_request"`;
`variant_rows` is `tuple[BindingItems, ...]` of the bindings the
mutated rule satisfies; `proof_frame` is an optional
`ProofFrameRecheckResult` for the original support under the mutation.

For Q3b we need a Rule (not a Inference) plus the prior support:

```python
from factpy.sdk import Rule

with vars("p", "c", "lang") as (p, c, lang):
    speaks_rule = Rule(
        id="rule.speaks",
        version="1.0.0",
        select=[p, lang],
        where=[
            Person(p),
            Country(c),
            p.lives_in == c,
            c.official_language == lang,
        ],
        expose=True,
    )

support_artifact = result.evidence_envelope.engine_payload  # from Q1
```

### Disable a body literal

```python
disabled = fg.what_if.rule.disable(
    speaks_rule,
    support_artifact,
    branch_index=0,
    atom_index=0,    # disable the first body atom
)

disabled.status         # "completed" | "unsupported" | "invalid_request"
disabled.variant_rows   # tuple[BindingItems, ...] — bindings the disabled-rule satisfies
disabled.proof_frame    # ProofFrameRecheckResult | None — recheck of original support
```

`branch_index` selects the body branch (only `0` for non-disjunctive
rules); `atom_index` selects the body atom to disable.

### Replace a literal

```python
from factpy.application.protocol import RuleLiteralPath

replaced = fg.what_if.rule.literal_replace(
    speaks_rule,
    support_artifact,
    branch_index=0,
    atom_index=3,                                    # the c.official_language == lang atom
    literal_path=RuleLiteralPath(kind="rhs"),        # the right-hand side of the comparison
    old_literal=lang,                                # the variable being replaced
    new_literal="French",
)

replaced.status         # "completed" | "unsupported" | "invalid_request"
replaced.variant_rows   # bindings the literal-replaced rule satisfies
replaced.proof_frame    # recheck of original support under the replacement
```

`literal_path` is a `RuleLiteralPath(kind, index=None)` from
`factpy.application.protocol`. Allowed `kind` values:
`"pred_term"`, `"lhs"`, `"rhs"`, `"in_value"`, `"const_operand"`.
`index` is required when `kind ∈ {"pred_term", "in_value"}` and must
be `None` otherwise (enforced in `__post_init__`).

Anything else slips past SDK pre-validation and is caught by the
runtime as `ProtocolShapeError` — surface symptom is an
`SDKStoreError(path="$.check_rule_literal_replace.request")`.

### Add a condition

```python
from factpy.application.protocol import RuleAddedAtom

added = fg.what_if.rule.add_condition(
    speaks_rule,
    support_artifact,
    branch_index=0,
    added_atom=RuleAddedAtom(atom=("eq", "$lang", "French")),
)

added.status         # "completed" | "unsupported" | "invalid_request"
added.variant_rows   # bindings the augmented rule satisfies
added.proof_frame    # recheck of original support under the added atom
```

`RuleAddedAtom(atom=...)` takes a single tuple — `atom[0]` must be a
kind tag (one of `"eq"`, `"ne"`, `"gt"`, `"ge"`, `"lt"`, `"le"`,
`"in"`); the remaining tuple elements are the operands.

Note: there is **no** `atom_index` argument. `add_condition` appends
the new atom at the end of the branch.

**Use when** (any of the three): you're prototyping a rule change and
want to see whether an existing proof still holds (or how it would
break) without committing the rule edit to the registry.

---

## Q4: What does not derive across a universe? — `fg.what_if.why_not`

```python
candidates = [
    {"p": ref_alice, "lang": "Spanish"},
    {"p": ref_bob,   "lang": "French"},
    {"p": ref_alice, "lang": "French"},   # this one DOES derive
]

wn = fg.what_if.why_not(speaks, candidates)

wn.status                 # WhyNotStatus: "completed" | "unsupported" | "invalid_request"
wn.requested_universe     # tuple[BindingItems, ...] — every input candidate, normalized
wn.green                  # tuple[BindingItems, ...] — bindings that DO derive
wn.red                    # tuple[WhyNotRedRow, ...] — bindings that don't, with diagnostics

for row in wn.red:
    row.binding           # BindingItems — the candidate that didn't derive
    row.diagnostic        # WhyNotRowDiagnostic — why not (atom-localized when possible)
```

When `status="completed"`, `green ⊕ red` partitions
`requested_universe`. When `status="unsupported"` or `"invalid_request"`,
both `green` and `red` are empty and `wn.errors` carries
`tuple[ErrorDTO, ...]`.

`why_not` requires you to supply the finite candidate universe
explicitly — it does not auto-discover. Each candidate is a `Mapping`
of variable names (without `$` prefix; the SDK normalizes them to
`$`-prefixed `BindingItems` internally) to values.

**Use when**: you have a finite set of candidates and want to know
which ones derive, which don't, and for each that doesn't, which body
atom blocked it. Useful for compliance "did anything fall through
the cracks" checks.

`why_not` rejects application-level `CompiledDerivationPlan` DTOs at
the SDK boundary; pass the SDK `Inference` directly.

---

## Q5: How did inference change between rounds? — `fg.audit.diff_proof_frames`

```python
from factpy.audit import load_audit_package

# Two recorded rounds are loaded from disk (or held from a recorder).
bundle_a = load_audit_package("/path/to/round_a/")
bundle_b = load_audit_package("/path/to/round_b/")
events_a = bundle_a.round_events    # tuple[RoundEvent, ...]
events_b = bundle_b.round_events

diff = fg.audit.diff_proof_frames(
    round_a_id="round-a",
    round_b_id="round-b",
    round_a_events=events_a,
    round_b_events=events_b,
    include_unchanged=False,         # default; set True to keep unchanged frames
)

diff.round_a_id           # "round-a"
diff.round_b_id           # "round-b"
diff.frame_deltas         # tuple[FrameDelta, ...] — every frame that differs
diff.warnings             # tuple[WarningDTO, ...]

for frame in diff.frame_deltas:
    frame.frame_identity         # FrameIdentity(support_digest, binding_items)
    frame.source_a               # EventReference | None — None means "added in round B"
    frame.source_b               # EventReference | None — None means "removed in round A"
    frame.frame_status_change    # FrameStatusChange | None — proof status flip (still_valid/invalidated/unknown)
    frame.atom_deltas            # tuple[AtomDelta, ...] — per-atom changes
    frame.markers                # tuple[FrameMarker, ...]
```

`ProofFrameDiff` does not pre-partition into added/removed/changed —
each `FrameDelta` carries that information directly:
- `source_a is None` → frame is new in round B (added).
- `source_b is None` → frame existed only in round A (removed).
- `frame_status_change is not None` → proof status flipped between
  rounds.
- `atom_deltas` non-empty → atom-level structural change.

`diff_proof_frames` is pure: no store, no registry, no engine, no IO.
It only requires the two event tuples. `include_unchanged=True` keeps
the frames whose status was identical between rounds (off by
default).

**Use when**: comparing audit logs across runs to surface what changed
— useful for regression review, governance reporting, and rule-edit
impact analysis.

---

## Recording rounds (for Q5)

Q5 consumes events from the recorder. The recorder lifecycle
(`start_round`, `record_round_event`, `finalize_round`) is intentionally
**not** part of `factpy.sdk`. Import it directly:

```python
from factpy.audit.round_events import start_round, record_round_event, finalize_round
```

See [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for
the recorder pattern and rationale.

---

## Walker views (advanced)

For richer in-process navigation of a `ProofFrameDiff` (e.g.
"give me all frames whose proof status flipped" or
"iterate every atom delta of kind atom_verdict_changed"), use
`factpy.application.walker.ProofFrameDiffView`:

```python
from factpy.application.walker import ProofFrameDiffView

view = ProofFrameDiffView(diff)

for frame in view.frames_with_status_change():
    print(frame.frame_identity.support_digest, frame.frame_status_change)

for delta in view.iter_atom_deltas(kind="atom_verdict_changed"):
    print(delta.atom_key, delta.before_verdict, "→", delta.after_verdict)
```

The view is a frozen wrapper. The SDK does not auto-wrap because not
every caller wants the indexing cost. See
[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for the
full method surface.

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
