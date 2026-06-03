# Preflight: Query-style head Slice delta

- Blueprint: [`workflow/blueprints/active/2026-06-03_query-style-head-slice-delta.md`](../../blueprints/active/2026-06-03_query-style-head-slice-delta.md)
- Audit log: [`workflow/blueprints/active/2026-06-03_query-style-head-slice-delta.audit.md`](../../blueprints/active/2026-06-03_query-style-head-slice-delta.audit.md)
- Branch: `v0.2.0-query-style-head-preflight-2026-06-03`
- Fork: `2ce3efef` (Step 4.2 review + tightening)
- Date: 2026-06-03
- Status: Step 4.3 preflight artifact

## 1. Scope

Slice delta relaxes the shipped evaluation invariant that `rule.id` / `target_pred_id`
must match a schema predicate. The intended new behavior is query-style heads:

- no schema predicate match -> accepted; result rows are shaped by `head.ports`;
- schema predicate match -> existing schema-backed path remains active;
- matched-predicate arity mismatch -> strict reject (Step 4.2 Option A lock).

This preflight verifies cross-engine sites, candidate construction implications, service/runtime
compatibility, and docs/tests surfaces before implementation.

## 2. Method

Fresh reads were done from the preflight branch. Primary grep targets:

- `find_schema_pred(...)`, `target predicate not found`, `head_vars length must match`;
- `target_pred_id`, `head_vars`, `RuntimeDerivationRecipe`;
- direct `Rule(id=...)` examples and current docs claims;
- `CandidateSet` canonical payload rules.

## 3. Findings

| ID | Bucket | Severity | Finding | Required action |
| --- | --- | --- | --- | --- |
| PF-R1 | Required | P1 | Cross-engine strict head lookup is broader than native. Native `_evaluate.py:148-157`, Souffle `adapters/souffle/engine_eval.py:118-127`, ProbLog runtime `adapters/problog/engine_eval.py:68-75`, and ProbLog import `adapters/problog/problog_import.py:110-119` all enforce schema predicate lookup + arity strictness. | Step 4.4 must lock native + Souffle + ProbLog as in-scope for the same opt-in schema lookup rule. PyReason is classified separately in PF-r1. |
| PF-R2 | Required | P1 | Query-style candidate construction is a real new builder path, not a tiny `_evaluate.py` conditional. `candidates_from_bindings(...)` requires `schema_pred`, `arg_specs`, `read_group_key_indexes(...)`, first arg `entity_ref`, and emits fact-shaped `{"pred_id", "terms"}` payload. | Step 4.4 must lock a query-style candidate helper/branch. It must derive row bindings from `head.ports` / `head_vars` and must not pass `schema_pred=None` into `candidates_from_bindings(...)`. |
| PF-R3 | Required | P1 | `CandidateSet(candidate_kind="fact")` canonical content still requires payload `terms` list (`candidates.py:126-135`). A pure `{bindings}` payload will fail unless candidate_kind/canonical schema changes. | Step 4.4 must choose compatibility payload shape for query-style candidates: keep fact-like payload with `pred_id=head.id` + ordered `terms` for canonical/content compatibility, or explicitly add a new candidate_kind/schema. Default recommendation: compatibility fact-like payload for δ. |
| PF-R4 | Required | P2 | Service/runtime compiled-plan fields still use `target_pred_id` / `head_vars` naming (`runtime_v1.py:1002-1015`, `:1795-1803`, `sdk/store.py:3839-3852`, `:3885-3889`). | Preserve wire/key names; update docs/meaning only. Do not rename runtime DTO keys in δ. |
| PF-r1 | Recommended | P2 | PyReason strict sites at `pyreason/engine_eval.py:637-695` are fact-to-candidate conversion from PyReason node/edge facts, not public head validation. PyReason where compile accepts non-empty `target_pred_id` without schema lookup, but materialized graph facts still need schema predicates. | Keep PyReason public head relaxation limited unless implementation proves a safe adapter path. Preflight recommends excluding PyReason fact-conversion substrate from query-style rewrite. |
| PF-r2 | Recommended | P2 | `_queries.py` and service `runtime_v1.py:2679` `find_schema_pred(...)` hits are read/query helper paths, not derivation head validation. | Exclude these from δ implementation; keep Step 4.7 scoped to evaluation derivation heads and adapter head import/runtime paths. |
| PF-r3 | Recommended | P2 | Current docs contain explicit shipped-strict claims in `docs/quickstart/evaluate_and_evidence.md:200/:565` and `docs/official/kernel/quickstart/rules-and-inferences.md:466/:533`. | Docs cascade must rewrite these from "must match known predicate" to "schema-backed ids opt into arity validation; free-form ids are valid query-style labels." |
| PF-v1 | Verified | - | `Rule.__post_init__` already accepts arbitrary non-empty `id` (`rule.py:62-63`). | No Rule DTO validation change. |
| PF-v2 | Verified | - | Service evaluate response metadata includes `"target_pred_id": compiled["target_pred_id"]` (`runtime_v1.py:1031-1035`). | Wire key preserved; semantics become head label / optional schema predicate. |
| PF-v3 | Verified | - | Slice ε walker uses result/head labels and should tolerate free-form head ids because it renders existing labels/value summaries. | Add regression test or verify via existing walker path after query-style row construction. |
| PF-v4 | Verified | - | Matched-predicate strict arity Option A is compatible with shipped docs/tests that expect `head_vars length must match target arg_specs`. | Preserve those negative tests by updating expectations only where docs now describe query-style non-match behavior. |
| PF-s1 | Scoped | - | δ closes the parent design chain after implementation/archive. | Step 4.8 Outcome should explicitly record all α/β/γ/ζ/η/ε/δ implemented and parent design eligible for archive review. |
| PF-s2 | Scoped | - | Implementation should avoid a broad service key rename. | Keep `target_pred_id` key names in compiled plans/recipes/responses. |

No abandonment finding was found.

## 4. Task Results

### A1. Cross-engine paths

Active strict head lookup sites:

- Native: `src/factgraph/core/store/_evaluate.py:148-157`.
- Souffle: `src/factgraph/adapters/souffle/engine_eval.py:118-127`.
- ProbLog runtime: `src/factgraph/adapters/problog/engine_eval.py:68-75`.
- ProbLog import: `src/factgraph/adapters/problog/problog_import.py:110-119`.

PyReason classification:

- `src/factgraph/adapters/pyreason/where_compile.py` accepts non-empty `target_pred_id`
  and compiles it into PyReason relation names without schema lookup.
- `src/factgraph/adapters/pyreason/engine_eval.py:637-695` schema lookups convert PyReason
  materialized node/edge facts into FactGraph candidates. These are not the same as public
  head validation and should not be rewritten blindly.

### A2. Backward compatibility enumeration

Existing examples/tests use schema-backed `target_pred_id` / `head.id` values heavily:

- `Person:exists`, `person:eligible`, `user:popular`, `friends:strength`,
  `user:tag`, `person:country_copy`, etc.
- Direct docs already show free-form `Rule(id="adult_in_us")`, `Rule(id="adult")`,
  `Rule(id="rule_alice")`, but evaluate docs currently say such ids fail at evaluation time.

Conclusion: backward compat requires preserving schema-backed path and Option A arity rejection.

### A3. Query-style candidate construction

`candidates_from_bindings(...)` is schema-bound:

- requires `arg_specs` and `schema_pred`;
- reads `group_key_indexes` from `schema_pred`;
- coerces terms by schema arg types;
- requires target arg0 `entity_ref`;
- emits fact-shaped payload terms.

`CandidateSet(candidate_kind="fact")` canonical content requires payload `terms` list. Therefore
δ needs an explicit helper. Recommended default:

- keep `candidate_kind="fact"` for compatibility in δ;
- use `payload={"pred_id": head.id, "terms": ordered terms from head ports}` so canonical
  candidate payload remains valid;
- row bindings remain ζ port-map `{port_name: term}` at EvaluateRow level;
- avoid a new candidate_kind unless Step 4.4 explicitly expands scope.

### A4. Walker compatibility

Free-form `result.head.id` is already used as a label in `evaluate_result.py` conclusion/rule nodes.
Slice ε `walk_evidence(...)` renders labels/summaries; no schema predicate parsing is required.

### A5. Service/runtime wire

The wire field names `target_pred_id` and `head_vars` appear in runtime evaluate input, metadata,
cached recipes, and SDK compiled-plan reconstruction. Renaming those keys would create a separate
wire migration. δ should preserve names and update docs to explain "head label, optionally
schema-backed predicate id."

### A6. Error-message users

Known docs/users:

- `docs/quickstart/evaluate_and_evidence.md:200/:565`;
- `docs/official/kernel/quickstart/rules-and-inferences.md:466/:533`;
- `src/agent/tests/test_agent_l4a_workflow.py:199`.

Step 4.7 should update docs and tests that specifically expect "target predicate not found" for
free-form rule ids. It should preserve matched-predicate arity error expectations.

### A7. Arity mismatch

Option A is sound:

- existing schema-backed users retain strict validation;
- query-style users avoid schema lookup by choosing a free-form id;
- no warning/messaging machinery is required in δ.

### A8. Docs cascade

Required docs:

- `docs/quickstart/evaluate_and_evidence.md`;
- `docs/quickstart/rules.md`;
- `docs/official/kernel/quickstart/rules-and-inferences.md`;
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`;
- service docs mentioning runtime `target_pred_id` if examples imply strict schema id.

### A9. D21 walker output

Slice ε walker remains compatible. A simple free-form head id should render as label text; no
walker change is expected.

## 5. Step 4.4 Amendment Checklist

Step 4.4 should fold:

1. PF-R1: native + Souffle + ProbLog runtime/import all in scope for opt-in lookup.
2. PF-R2/PF-R3: query-style candidate helper with compatibility fact-like payload default.
3. PF-R4: preserve service/runtime `target_pred_id` / `head_vars` keys.
4. PF-r1: PyReason fact-conversion schema lookups excluded unless implementation proves safe.
5. PF-r2: `_queries.py` / service read-query lookup hits excluded.
6. PF-r3: docs cascade for strict-error wording.
7. Acceptance: add no-new-candidate-kind unless explicitly amended; preserve matched-predicate arity reject; add free-form head tests for native/Souffle/ProbLog where feasible.

## 6. Verdict

PASS with amendment required. No abandonment. The Step 4.1/4.2 scope is viable, but Step 4.4 must
lock candidate construction and cross-engine sites before scope freeze.
