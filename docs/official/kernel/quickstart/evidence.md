# Evidence: what-if and audit

The earlier pages wrote facts and ran rules. This page covers the read-only
side: asking the graph whether a hypothetical fact would hold, why a check
failed, what would happen under an imagined fact or rule edit, and how to
compare two persisted rounds.

Every method on this page is read-only. None of them writes to the ledger,
mutates the registry, or changes schema. The two top-level taxonomies are:

| Namespace | Use it for |
| --- | --- |
| `fg.what_if` | Live counterfactual checks against the current snapshot. |
| `fg.audit` | Inspection of persisted facts and recorded rounds. |

## A slightly richer schema

The examples on this page use a `Person` schema with three single-valued
scalar fields. It is small enough to read and rich enough to write
inferences that fail in interesting ways.

```python
from kernel.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    vars,
)


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


fg = FactGraph.create(schema_classes=[Person])

alice = fg.read.ref(Person, name="alice")
fg.write.set(Person.age, alice, 30)
fg.write.set(Person.region, alice, "us")

bob = fg.read.ref(Person, name="bob")
fg.write.set(Person.age, bob, 30)
fg.write.set(Person.region, bob, "eu")

carol = fg.read.ref(Person, name="carol")
fg.write.set(Person.age, carol, 25)
fg.write.set(Person.region, carol, "us")
```

We will reuse one inference: "this `Person.age` fact for this person with
this age is derivable from the ledger". The body looks like a structural
echo of the head, which is what `check` needs.

```python
with vars("p", "age") as (p, age):
    age_inference = Inference(
        id="quickstart.evidence.age",
        version="v1",
        where=[Person(p), p.age == age],
        head=Person.age(value=age),
    )
```

## Check a binding: `fg.what_if.check`

`fg.what_if.check(inference, binding)` asks "given this concrete binding of
the inference's variables, does the inference fire against the current
ledger?" The binding maps each `$`-prefixed variable to a Python value.

```python
result = fg.what_if.check(age_inference, {"$p": alice, "$age": 30})

assert result.status == "passed"
assert result.matched_count == 1
assert result.evidence_envelope is not None
```

`status` is one of `"passed"`, `"failed"`, `"unsupported"`, or
`"invalid_request"`. The full nullable matrix is locked in the application
protocol; the short version is:

| `status` | `matched_count` | `matched_binding` | `evidence_envelope` |
| --- | --- | --- | --- |
| `"passed"` | `>= 1` | populated | populated |
| `"failed"` | `0` | `None` | `None` |
| `"unsupported"` / `"invalid_request"` | `None` | `None` | `None` |

A binding that no row supports produces `"failed"`:

```python
fail = fg.what_if.check(age_inference, {"$p": alice, "$age": 99})

assert fail.status == "failed"
assert fail.matched_count == 0
assert fail.evidence_envelope is None
```

`engine="native"` is the default. The check method accepts `engine` as a
literal from `{"native", "souffle", "problog", "pyreason"}`; only the
native engine produces a `SupportArtifact` (see "The evidence chain"
below). The shells reject `semantics=` and `semantics_profile=` keywords on
purpose — engine selection here is by name, not by `*Semantics` wrapper.

## Diagnose a failure: `fg.what_if.diagnose`

When a check returns `"failed"`, `fg.what_if.diagnose(inference, binding)`
localizes the failure. It is a sibling of check, not a wrapper around it;
calling diagnose does not internally call check.

```python
diag = fg.what_if.diagnose(age_inference, {"$p": alice, "$age": 99})

assert diag.status == "failed"
assert diag.failure_kind == "atom_localized"
locator = diag.diagnostic_payload
assert locator is not None
assert locator.branch_index == 0
assert locator.failed_atom_index == 1
```

The body has two atoms: `Person(p)` at index 0 and `p.age == age` at
index 1. Alice exists, so atom 0 passes; her age is 30, not 99, so atom 1
fails — `failed_atom_index == 1`.

`failure_kind` distinguishes `"no_candidate"` (no row even reached the
body) from `"atom_localized"` (a row was tried and a specific atom
rejected it). Only `"atom_localized"` populates `diagnostic_payload`.

## Why-not over a candidate universe: `fg.what_if.why_not`

`fg.what_if.why_not(inference, candidates)` lifts diagnose to a finite set
of bindings. You supply the universe explicitly; the SDK does not crawl
the store for you.

```python
candidates = [
    {"$p": alice, "$age": 30},
    {"$p": bob, "$age": 30},
    {"$p": carol, "$age": 30},
]

board = fg.what_if.why_not(age_inference, candidates)

assert board.status == "completed"
assert len(board.green) == 2
assert len(board.red) == 1
```

`board.green` is a tuple of bindings that passed. `board.red` is a tuple of
`WhyNotRedRow` items, each carrying the binding plus the same kind of
atom-level diagnostic as `diagnose`.

```python
red_row = board.red[0]
assert dict(red_row.binding)["$p"] == carol
assert red_row.diagnostic.status == "failed"
assert red_row.diagnostic.failure_kind == "atom_localized"
```

Each candidate row may be a mapping (`{"$p": ..., "$age": ...}`) or a
positional sequence in the head-variable order. Rows must cover exactly
the plan's head variables; missing or extra variables produce
`"invalid_request"`.

## The evidence chain: extracting `SupportArtifact`

A passed native-engine check produces a `SupportArtifact` inside
`result.evidence_envelope.engine_payload`. That artifact is the canonical
"proof receipt" — every downstream rechecker and rule-overlay method on
this page consumes it explicitly.

```python
from kernel.core.store._support import SupportArtifact

passed = fg.what_if.check(age_inference, {"$p": alice, "$age": 30})
assert passed.status == "passed"

support = passed.evidence_envelope.engine_payload
assert isinstance(support, SupportArtifact)
```

The handoff is always explicit. The SDK never threads a check result into
an overlay method for you; you read `result.evidence_envelope.engine_payload`,
verify the type, and pass it to the next method yourself.

For non-native engines, `engine_payload` is a `ProvenanceEnvelope` instead
of a `SupportArtifact`. The recheck and rule-overlay methods that need a
support artifact only accept native results.

## Fact overlay: what if facts changed?

Fact overlays describe imagined fact edits. The overlay is a frozen value;
it is never written to the ledger.

```python
from kernel.application.protocol import (
    EvaluationOverlay,
    FactValueOverride,
)
```

A `FactValueOverride` rewrites a single active fact. You supply the
existing assertion id, predicate id, entity ref, the old tuple, and the
new tuple. The assertion id and current value come from the regular
assertion surface introduced earlier:

```python
carol_age_record = (
    fg.read.get(Person, name="carol").field("age").active().one()
)

raise_carol_to_30 = FactValueOverride(
    asrt_id=carol_age_record.asrt_id,
    pred_id=carol_age_record.pred_id,
    e_ref=carol_age_record.e_ref,
    old_fact_tuple=(carol_age_record.e_ref, carol_age_record.value),
    new_fact_tuple=(carol_age_record.e_ref, 30),
    note="hypothetical: Carol turns 30",
)

overlay = EvaluationOverlay(fact_actions=(raise_carol_to_30,))
```

`fg.what_if.fact_overlay.check` runs check twice — once against the
current ledger and once against the ledger with the overlay applied — and
returns both phases plus a diff.

```python
overlay_result = fg.what_if.fact_overlay.check(
    age_inference, {"$p": carol, "$age": 30}, overlay
)

assert overlay_result.status == "passed"
assert overlay_result.before.status == "failed"
assert overlay_result.after.status == "passed"
assert overlay_result.diff.status_changed is True
```

`fg.what_if.fact_overlay.recheck_proof_frame(support, overlay)` answers a
different question: given a proof we already captured, would it still
hold under this overlay?

```python
recheck = fg.what_if.fact_overlay.recheck_proof_frame(support, overlay)

assert recheck.status in {"still_valid", "invalidated", "unknown"}
for verdict in recheck.atom_verdicts:
    assert verdict.verdict in {"still_valid", "invalidated", "unknown"}
```

Recheck takes only `SupportArtifact` plus `EvaluationOverlay`. It has no
`engine=` and no `registry=` — by design, it does not lower an inference
or talk to the rule registry.

`FactRemoveAction` is the other available fact-side action; its shape
mirrors `FactValueOverride` minus `new_fact_tuple`.

## Rule overlay: what if the rule changed?

Rule overlays let you ask the same question about hypothetical rule edits.
Each rule overlay shell consumes a `Rule` (not an `Inference`), a
`SupportArtifact` from a prior check, and the edit-specific arguments.

The three shells are read-only on the rule registry; nothing is mutated.

### Disable an atom

`fg.what_if.rule.disable(rule, support, branch_index=..., atom_index=...)`
asks what happens if a single atom in a single branch were dropped.

```python
from kernel.sdk import Pred, Rule

with vars("p", "age", "region") as (p, age, region):
    age_in_us = Rule(
        id="quickstart.evidence.age_in_us",
        version="v1",
        select=[p, age],
        where=[Person(p), p.age == age, p.region == region],
    )

rule_support = fg.what_if.check(
    age_inference, {"$p": alice, "$age": 30}
).evidence_envelope.engine_payload

disabled = fg.what_if.rule.disable(
    age_in_us,
    rule_support,
    branch_index=0,
    atom_index=1,
)

assert disabled is not None  # RuleDisableResult
```

### Replace a literal

`fg.what_if.rule.literal_replace(...)` swaps one constant for another at
one position inside one atom. `RuleLiteralPath` names the position:

```python
from kernel.application.protocol import RuleLiteralPath

replaced = fg.what_if.rule.literal_replace(
    age_in_us,
    rule_support,
    branch_index=0,
    atom_index=2,
    literal_path=RuleLiteralPath(kind="pred_term", index=2),
    old_literal="us",
    new_literal="de",
)
```

`RuleLiteralPath.kind` is `"pred_term"`, `"lhs"`, `"rhs"`, `"in_value"`,
or `"const_operand"`. `pred_term` and `in_value` require `index`; the
others require `index=None`.

### Add a condition

`fg.what_if.rule.add_condition(...)` tightens a branch with one extra
atom. `RuleAddedAtom` carries a tuple whose first element is the atom kind
(`"eq"`, `"ne"`, `"gt"`, `"ge"`, `"lt"`, `"le"`, or `"in"`):

```python
from kernel.application.protocol import RuleAddedAtom

tightened = fg.what_if.rule.add_condition(
    age_in_us,
    rule_support,
    branch_index=0,
    added_atom=RuleAddedAtom(("lt", "$age", 65)),
)
```

All three rule-overlay shells accept the same optional `overlay=` and
`note=` keywords. `overlay` lets you stack a fact overlay on top of the
rule edit in one call. `note` is a free-form annotation that travels with
the result and any recorded round event.

## Compare two recorded rounds: `fg.audit.diff_proof_frames`

`fg.audit.diff_proof_frames(...)` compares the proof-frame events from two
previously recorded rounds and returns a structured per-frame delta.

Round capture itself is not part of this quickstart surface — it lives at
`kernel.audit.round_events`, which exposes `start_round`,
`record_round_event`, and `finalize_round` as advanced importables.
Persisted rounds are loaded with `kernel.audit.load_audit_package`.

```python
from kernel.audit import load_audit_package

events_a = load_audit_package("rounds/round-a/").events
events_b = load_audit_package("rounds/round-b/").events

diff = fg.audit.diff_proof_frames(
    "round-a", "round-b", events_a, events_b
)

assert diff.round_a_id == "round-a"
assert diff.round_b_id == "round-b"
for delta in diff.frame_deltas:
    # FrameDelta carries identity, status change, atom delta, event refs
    assert delta.identity is not None
```

Pass `include_unchanged=True` to emit deltas for frames that did not
change between rounds.

`fg.audit.explain_fact(pred_id, e_ref, *value_atoms)` and
`fg.audit.conflicts(pred_id, e_ref)` are the existing audit pair for
persisted facts. They take an assertion-level coordinate and return a
dictionary-form explanation; the earlier `Assertion records and views`
page introduces them.

## What evidence does not do

- **No ledger write.** None of these methods appends, retracts, or
  modifies assertions. Overlays describe imagined edits; the proofs they
  produce reference the unchanged ledger plus the frozen overlay.
- **No registry mutation.** Rule overlays never change saved rules.
- **No schema mutation.** Adding fields is `fg.schema.add(...)` from the
  schema page, not the evidence line.
- **No automatic chaining.** A `SupportArtifact` is extracted from a
  check result by you and passed to recheck or rule overlay by you. The
  SDK does not run `check` internally on your behalf.
- **No support artifact under non-native engines.** When `engine=` is
  `"problog"` or `"pyreason"`, `evidence_envelope.engine_payload` is a
  `ProvenanceEnvelope`, which the recheck and rule-overlay methods do not
  accept. Use `engine="native"` to keep the evidence chain.
- **No recorder lifecycle on the SDK.** `start_round`,
  `record_round_event`, and `finalize_round` live at
  `kernel.audit.round_events` as advanced importables; the SDK ships only
  the query-side `diff_proof_frames`.
- **No walker views.** `ProofFrameView`, `SupportArtifactView`, and
  `ProofFrameDiffView` are advanced ergonomic wrappers in
  `kernel.application.walker`. The SDK methods return raw frozen DTOs.
- **No frontier introspection.** Why-not requires an explicit candidate
  universe; whole-store frontier discovery sits at
  `kernel.core.rules.frontier` and is not part of this surface.

## Syntax checklist

- `fg.what_if.check(inference, binding, *, engine="native", registry=None)`
  returns `CheckResult` (`status`, `matched_count`, `matched_binding`,
  `evidence_envelope`, `errors`, `warnings`).
- `fg.what_if.diagnose(inference, binding, *, engine="native", registry=None)`
  returns `DiagnoseResult` (`status`, `failure_kind`,
  `diagnostic_payload`, `matched_count`, `matched_binding`, `errors`,
  `warnings`).
- `fg.what_if.why_not(inference, candidates, *, engine="native", registry=None)`
  returns `WhyNotUniverseResult` (`status` is `"completed"`,
  `"unsupported"`, or `"invalid_request"`; `green`, `red`, `errors`,
  `warnings`).
- `fg.what_if.fact_overlay.check(inference, binding, overlay, *, engine="native", registry=None)`
  returns `FactOverlayCheckResult` (`before`, `after`, `diff`).
- `fg.what_if.fact_overlay.recheck_proof_frame(support_artifact, overlay)`
  returns `ProofFrameRecheckResult` (`status`, `binding_items`,
  `atom_verdicts`).
- `fg.what_if.rule.disable(rule, support, *, branch_index, atom_index, overlay=None, note=None)`.
- `fg.what_if.rule.literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)`.
- `fg.what_if.rule.add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None)`.
- `fg.audit.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)`
  returns `ProofFrameDiff` (`round_a_id`, `round_b_id`, `frame_deltas`,
  `warnings`).
- Binding keys are `$`-prefixed strings; positional candidate rows match
  the plan's head variable order.
- Engine names are `"native"`, `"souffle"`, `"problog"`, `"pyreason"`;
  `semantics=` and `semantics_profile=` keywords are rejected on these
  methods. Use the named-engine form here, even when the same graph
  evaluates inferences with `ProbLogSemantics` / `PyReasonSemantics`
  elsewhere.
- DTO and overlay types live at `kernel.application.protocol`:
  `EvaluationOverlay`, `FactValueOverride`, `FactRemoveAction`,
  `RuleLiteralPath`, `RuleAddedAtom`, plus the result DTOs.
  `SupportArtifact` lives at `kernel.core.store._support`. None of these
  are in `kernel.sdk.__all__`; import them directly when you need typed
  references.
- Round capture (`start_round` / `record_round_event` / `finalize_round`)
  and audit package loading (`load_audit_package`) live at
  `kernel.audit.round_events` and `kernel.audit`.
- The flat `SDKStore.check(...)`, `SDKStore.check_fact_overlay(...)`,
  `SDKStore.check_rule_disable(...)`, etc. are permanent aliases; the
  taxonomy form (`fg.what_if.*`, `fg.audit.*`) is the canonical reading
  path.
