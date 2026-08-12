# Q5C Decision: Derivation output and materialization boundary

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint for the F3C semantic-cleanup slice only.
- Inputs:
  - D18 §4.3 and D23 §4.1, §4.4-§4.6
  - Q5B §4.2 and the implemented F3B blueprint
  - 2026-08-12 three-way read-only F3C inventory, surface and migration audits
  - Meander `main@4ddb8e36` cross-repository consumer inventory
  - 2026-08-12 user instruction: “同意，可以继续下一步”
- Outputs / Downstream:
  - [`2026-08-12_factgraph-derivation-output-materialization-cleanup.md`](../../../blueprints/archive/2026-08-12_factgraph-derivation-output-materialization-cleanup.md)
  - A later Meander materialization migration and FactGraph public hard-cut
- Related:
  - [`2026-08-12_q5b-evaluation-query-native-execution-decision.md`](./2026-08-12_q5b-evaluation-query-native-execution-decision.md)
- Branch: `codex/v0.3.0-f3c-derivation-output-cleanup-2026-08-12`
- Base: `4024526c`

## 1. Problem

`CandidateSet` names one engine output, not a set, and conflates read-only
derivation output with the optional act of materializing it into the ledger.
D18/D23 require it to be internal, yet a later reintroduction exposed
`fg.eval.evaluate_candidates(...)`. That drift cannot be hard-cut inside
FactGraph alone: Meander currently consumes it in production paths including
`src/meander/rules/accept_candidates.py`, `rules/rule_source.py`,
`graph/probabilistic.py`, and `graph/self_labels.py`.

The service retains five primary candidate codecs with no callers plus a
four-helper parser chain referenced only by those codecs,
while its HTTP accept endpoint is an intentional removed-surface tombstone.
The application materialization wrappers also have two proven P1 defects:
single-item acceptance bypasses Store digest enrichment, while batch acceptance
drops `dry_run` and other per-item intent. These require narrow safety repairs,
not a public materialization redesign.

## 2. Scope

This decision locks a two-batch cleanup:

1. remove the five unreachable primary service codecs and their four-helper
   private parser chain; retain and label
   `fg.eval.evaluate_candidates(...)` as temporary cross-repository compatibility
   debt, and retain the service tombstone plus Agent/core materialization paths;
2. make `DerivationOutput` canonical with a legacy `CandidateSet` `TypeAlias`,
   migrate the active read-only chain, and repair the two application wrappers
   through Store-owned accept-time enrichment seams.

## 3. Non-scope

- Removing or behavior-changing `fg.eval.evaluate_candidates(...)`.
- Meander migration, Agent accept/review cleanup, HTTP tombstone removal, or
  core/application/Store materialization redesign.
- Renaming `candidate_id`, `candidate_key`, `candidate_ref`, digest prefixes,
  payload keys, persisted metadata, audit records or evidence lookup keys.
- F4 bundle, replay, snapshot, Explain or query execution changes.

## 4. Decision

### 4.1 Read-only output and write intent are different contracts

`DerivationOutput` is the canonical name for an engine-produced, read-only
in-process output. It does not imply ledger admission. Materialization remains
a separate write concern and keeps the existing `CandidateSet` vocabulary only
where compatibility or persisted protocol requires it.

`CandidateSet` is a direct type alias, not a subclass, wrapper, second DTO, or
conversion boundary. Existing construction, `isinstance`, equality, digests
and the v2 payload/wire/ledger serialization therefore remain unchanged. Old
Python pickles that name `...candidates.CandidateSet` resolve through the alias;
new pickles name `DerivationOutput` and are not claimed readable by a pre-F3C
runtime. Python pickle is not a durable protocol of this repository.

### 4.2 The public compatibility seam is acknowledged, not legitimized

D18 §4.3 and D23 remain the target: public evaluation should return
`EvaluateResult`, not candidate objects. However, Meander `main@4ddb8e36`
directly depends on `evaluate_candidates` in four shipped modules and their
tests. F3C therefore records a later reintroduction drift and must not claim the
public API is coherent or the D23 hard-cut complete.

Deletion is allowed only after a separate cross-repository migration replaces
Meander's read paths and its evaluate-then-materialize loop with an explicitly
designed internal/materialization contract.

### 4.3 Compatibility identities remain byte-stable

The alias migration changes Python vocabulary only. All `cand_v2` / `candk_v2`
formulas, fields, `candidate_ref` dependencies, ledger metadata, service/audit
wire keys and support/evidence indexes remain byte-for-byte compatible.

### 4.4 F4 consumes result identity, never output identity

F4 may consume Query/result fingerprints established by F3A/F3B. It must not
serialize `DerivationOutput`, `CandidateSet`, `candidate_id`, or `candidate_key`
as a durable evaluation, replay or Explain anchor.

### 4.5 Repair wrappers without adding a public materialization API

The single application wrapper delegates through a private Store-owned
accept-time enrichment seam, so current schema/policy digests are written while
the established two identities remain distinct: the output's compiler-generated
`derivation_id` and the trusted application resolver's authored/business
`derived_rule_id`. Direct `Store.accept` retains its stricter identity-match
guard. This enrichment is accept-time context, not an evaluation snapshot or
replay claim. The batch wrapper delegates through `Store.accept_many`: it fails
closed on `dry_run=True`, propagates each `AcceptRequest`'s approval/note/actor
metadata, and rejects an `identity_override` applied ambiguously to multiple
outputs. Names, payloads and wire contracts otherwise remain unchanged. A later
cross-repository slice owns any `Materialization*` public vocabulary or API.

## 5. Rejected Alternatives

- **Delete `evaluate_candidates` now** — breaks real Meander consumers and
  mistakes a cross-repository migration for local cleanup.
- **Rename persisted candidate vocabulary now** — creates a wire/evidence
  migration without product value for F3/F4.
- **Wrap every output in a new DTO** — duplicates identity and conversion logic;
  a direct alias supplies the needed migration seam.
- **Rename accept/materialization publicly now** — crosses the Meander and wire
  boundary; F3C only repairs the already-shipped wrappers.

## 6. Acceptance Criteria

- [ ] `DerivationOutput` is the canonical class; `CandidateSet` is a direct alias.
- [ ] Active read-only evaluation code uses `DerivationOutput` terminology.
- [ ] All candidate fields, IDs, payloads, wire and persistence remain unchanged.
- [ ] `evaluate_candidates` remains callable and is explicitly temporary debt.
- [ ] Five zero-call primary codecs and their four-helper-only parser chain are removed; the HTTP tombstone remains.
- [ ] Single/batch wrappers consume Store-owned enrichment and enforce the stated guards without conflating compiler and business rule identity.
- [ ] F4 documentation names only Query/result fingerprints as durable anchors.

## 7. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Three-way read-only audit converged | Candidate naming debt is real, but write semantics and public compatibility have a wider blast radius. |
| 2026-08-12 | adopted | User authorized the next isolated step | Two batches are scoped; no push, merge, Meander edit or materialization redesign is authorized. |
| 2026-08-12 | narrowed | Cross-repository grep found live Meander consumers | Public seam deletion was removed from F3C and made conditional on a later Meander migration. |
| 2026-08-12 | corrected | Cross-repository regression exposed two legitimate rule identities | Meander fixtures proved that RuleExpr outputs use compiler-generated derivation IDs while persisted provenance uses resolver-authorized business rule IDs. The single wrapper now uses a private enriched attribution seam; `Store.accept` remains strict. |
| 2026-08-12 | verified | User-side independent review returned CLEAR | Full suite and 30 adversarial probes confirmed the two-batch decision; the only P2 is a reproduced pre-existing service import defect outside this slice. The implementation blueprint pair is archived. |
