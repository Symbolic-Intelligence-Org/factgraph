# Preflight Audit: Result-fingerprint fold Slice β

- Branch: `v0.2.0-result-fingerprint-fold-preflight-2026-06-03`
- Forked from blueprint HEAD: `de28bc55` (`v0.2.0-blueprint-result-fingerprint-fold-2026-06-03`)
- Date: 2026-06-03
- Status: preflight artifact
- Blueprint: [`workflow/blueprints/active/2026-06-03_result-fingerprint-fold-slice-beta.md`](../../blueprints/active/2026-06-03_result-fingerprint-fold-slice-beta.md)

## 1. Scope

This preflight verifies Slice β before scoped anchor:

- fold `EvaluateResult.run_id`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `config_digest`, `result_digest` into `ResultFingerprint`;
- fold `engine_version` / `adapter_version` into validated `engine_meta`;
- preserve `evaluate_result_digest_v1` canonical bytes;
- preserve service JSON wire shape and user-facing deprecated-property compatibility;
- enumerate construction sites and downstream consumers before implementation.

## 2. Method

Rule 1 fresh reads were performed against shipped source on the preflight branch:

| Task | Command / read target | Outcome |
|---|---|---|
| A1 | `evaluate_result.py:565-612` | `result_digest_for(...)` payload and validation re-read; canonical schema remains `evaluate_result_digest_v1`. |
| A2 | `rg -n "EvaluateResult\\(" src/factgraph tests docs` plus follow-up `src/service/runtime_v1.py` read | Found blueprint command gap: service runtime also constructs `EvaluateResult`. |
| A3 | `rg -n "_evaluate_result_to_dict..." src/service` | `_evaluate_result_to_dict(...)` exists at `runtime_v1.py:2445-2462`. |
| A4 | `rg -n "expr_digest|rule_set_digest|view_snapshot_digest|config_digest|result_digest|run_id|engine_version|adapter_version" ...` | Found protocol, SDK, service, tests, and docs consumers. |
| A5 | direct `nl -ba` reads for `EvaluateResult`, `result_digest_for`, service runtime, SDK store, tests, docs | Anchors recorded below. |

## 3. Findings Summary

| Bucket | Count | Findings |
|---|---:|---|
| Required | 3 | PF-R1, PF-R2, PF-R3 |
| Recommended | 2 | PF-r1, PF-r2 |
| Verified | 8 | PF-v1..PF-v8 |
| Scoped-detail | 2 | PF-s1..PF-s2 |
| Abandonment | 0 | None |

Healthy distribution: 3R / 2r / 8v / 2s / 0A. No abandonment blocker.

## 4. Required Findings

### PF-R1 — A2 construction-site enumeration missed `src/service/runtime_v1.py`

**Finding.** Blueprint A2 currently enumerates `EvaluateResult(...)` construction with:

```bash
rg -n 'EvaluateResult\(' src/factgraph/ tests/ docs/
```

That command misses `src/service/runtime_v1.py`, which is an active production construction site.

**Fresh source evidence.**

- `src/service/runtime_v1.py:2328-2395` defines `_evaluate_result_from_candidates(...)`.
- It computes `run_id`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `config_digest`, `result_id`, rows, and `result_digest`.
- It returns `EvaluateResult(...)` at `runtime_v1.py:2381-2395` with all eight soon-removed flat kwargs:
  - `run_id=`
  - `engine_version=`
  - `adapter_version=`
  - `expr_digest=`
  - `rule_set_digest=`
  - `view_snapshot_digest=`
  - `config_digest=`
  - `result_digest=`

**Impact if missed.** Step 4.7 would update SDK construction but leave service runtime broken at import/test time once `EvaluateResult.__init__` drops those kwargs.

**Required amendment.**

- Add `src/service/runtime_v1.py:2328-2395` to Related Modules and §5.5 construction-site updates.
- Update A2 / §8 implementation plan to enumerate `src/service/` in construction-site grep.
- Step 4.7 must construct `ResultFingerprint` + validated `engine_meta` there with the same §5.4.1 ordering.

### PF-R2 — Service scope has two separate duties, not only serializer N-1

**Finding.** Step 4.2 correctly grounded `_evaluate_result_to_dict(...)`, but the service file has two independent Slice β touch zones:

1. construction (`_evaluate_result_from_candidates`) — PF-R1;
2. serialization (`_evaluate_result_to_dict`) — existing N-1 serializer scope.

**Fresh source evidence.**

- `src/service/runtime_v1.py:2445-2462` returns JSON with flat fields:
  - `"run_id": result.run_id`
  - `"engine_version": result.engine_version`
  - `"adapter_version": result.adapter_version`
  - `"expr_digest": result.expr_digest`
  - `"rule_set_digest": result.rule_set_digest`
  - `"view_snapshot_digest": result.view_snapshot_digest`
  - `"config_digest": result.config_digest`
  - `"result_digest": result.result_digest`
- `runtime_v1.py:1029` wraps `_evaluate_result_to_dict(...)` output into runtime response payload.

**Impact if missed.** A serializer-only amendment would preserve wire output but still leave the service construction path stale.

**Required amendment.**

- Split service scope in the blueprint:
  - `Service construction` at `runtime_v1.py:2328-2395`
  - `Service serialization` at `runtime_v1.py:2445-2462`
- Acceptance must require both.

### PF-R3 — Active docs cascade is broader than `docs/quickstart/evaluate_and_evidence.md`

**Finding.** The blueprint currently names `docs/quickstart/evaluate_and_evidence.md` as the main docs rewrite and leaves “Any active docs consumers” to 4.6.5. Preflight shows multiple active docs already list the old flat fields as if they were direct `EvaluateResult` fields. This is a required documentation cascade, not a late optional cleanup.

**Fresh source evidence.**

- `docs/quickstart/evaluate_and_evidence.md:120-125` shows `result_id, run_id`, `engine_version`, `adapter_version`, four digests, and `result_digest` as direct `EvaluateResult` fields.
- `docs/quickstart/evaluate_and_evidence.md:143-148` explains the four digests and `result_digest` as direct result fields.
- `docs/official/kernel/quickstart/evidence.md:33-35` groups `result_id`, `run_id`, `result_digest`, replay digests, and engine provenance as envelope fields.
- `docs/official/kernel/quickstart/evidence.md:54-59` discusses matching `expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` and `run_id`.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:559-561` lists `result_id`, `run_id`, `result_digest`, and replay anchors.
- `src/service/docs/03_runtime_queries_policy.md:1034-1043` shows service wire JSON fields that must remain flat but should be explained as wire compatibility, not current in-process field shape.
- `docs/official/kernel/quickstart/namespace-map.md:80` says `EvaluateResult.rule_set_digest` records rule content digest. Post-Slice-β this should be `EvaluateResult.fingerprint.rule_set_digest`, with deprecated-property compatibility noted if needed.

**Impact if missed.** Docs would contradict the new in-process DTO shape immediately after Slice β, especially in official kernel quickstarts.

**Required amendment.**

- Add a named docs cascade list to §5.7 / §9:
  - `docs/quickstart/evaluate_and_evidence.md`
  - `docs/official/kernel/quickstart/evidence.md`
  - `docs/official/kernel/quickstart/namespace-map.md`
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
  - `src/service/docs/03_runtime_queries_policy.md`
- Service docs must preserve flat JSON field examples but explain them as wire shape backed by `fingerprint` / `engine_meta`.

## 5. Recommended Findings

### PF-r1 — Active SDK tests outside the current targeted command exercise deprecated fields

**Finding.** Blueprint targeted verification currently centers `tests/application/protocol` + `tests/sdk/test_evaluate_result_exports.py`. Preflight found active SDK/domain tests that access soon-deprecated fields and should be included in Step 4.7 verification or explicitly classified as warning-compatible.

**Fresh source evidence.**

- `tests/sdk/test_rule_expr_evaluate.py:88-90` asserts `result.view_snapshot_digest`, `result.result_digest`, `result.config_digest`.
- `tests/sdk/test_rule_expr_evaluate.py:113` compares two `view_snapshot_digest` values.
- `tests/sdk/test_rule_expr_evaluate.py:337` and `:445` use `config_digest`.
- `tests/test_db_attach_lifecycle.py:256` compares `evaluated.view_snapshot_digest` to `view.view_digest`.
- `tests/test_problog_semantics_profile_migration.py:342-349` checks result wire keys include the soon-folded fields.

**Recommended amendment.**

- Extend §7 / §8 verification command to include:
  - `tests/sdk/test_rule_expr_evaluate.py`
  - `tests/test_db_attach_lifecycle.py`
  - `tests/test_problog_semantics_profile_migration.py`
- Or explicitly record why default `DeprecationWarning` handling is sufficient for these tests.

### PF-r2 — Internal metadata anchors in blueprint are stale after Slice α

**Finding.** Blueprint §5.6 still references expected metadata consumers around older line anchors `evaluate_result.py:1163-1166` and `:1245-1254`. Current shipped anchors are different after Slice α.

**Fresh source evidence.**

- `evaluate_result.py:1251-1267` `_evidence_metadata_payload_for_row_result(...)` reads `result.expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `config_digest`, `result_digest`, `engine_version`, and `adapter_version`.
- `evaluate_result.py:1337-1353` `_checked_scope_for_row_result(...)` reads `result.config_digest`, `expr_digest`, `rule_set_digest`, and `view_snapshot_digest`.
- `src/factgraph/sdk/store.py:2527-2539` `_manual_explain_checked_scope(...)` reads `result.config_digest`, `expr_digest`, `rule_set_digest`, and `view_snapshot_digest`.

**Recommended amendment.**

- Refresh §5.6 anchors to the current line ranges above.
- Keep the same implementation requirement: internal consumers must read `result.fingerprint.*` / validated `engine_meta[...]` directly, not deprecated properties.

## 6. Verified Findings

### PF-v1 — EvaluateResult field-shape anchor verified

`src/factgraph/application/protocol/evaluate_result.py:206-220` defines `EvaluateResult` with 13 direct public fields:

- `result_id`
- `run_id`
- `rows`
- `head`
- `engine`
- `engine_version`
- `adapter_version`
- `expr_digest`
- `rule_set_digest`
- `view_snapshot_digest`
- `config_digest`
- `evaluated_at`
- `result_digest`

Internal plumbing starts at `evaluate_result.py:221`.

### PF-v2 — `__post_init__` validates flat fields directly today

`evaluate_result.py:241-254` validates `result_id`, `run_id`, engine versions, four provenance digests, and `result_digest`. Slice β must move these validations to `ResultFingerprint` + `engine_meta` without weakening them.

### PF-v3 — `result_digest_for(...)` byte contract verified

`evaluate_result.py:565-612` keeps schema `"evaluate_result_digest_v1"` and canonical payload keys:

- `adapter_version`
- `engine`
- `engine_version`
- `expr_digest`
- `head_content_digest`
- `head_id`
- `result_id`
- `row_digests`
- `rule_set_digest`
- `run_id`
- `config_digest`
- `view_snapshot_digest`

No byte-format change is needed for Slice β.

### PF-v4 — SDK store construction order already matches Step 4.2 P1 lock

`src/factgraph/sdk/store.py:2674-2739` computes primitives, `result_id`, rows, row digests, `result_digest`, then returns `EvaluateResult(...)`. This matches the Step 4.2 construction-order lock and should be mirrored with `ResultFingerprint(...)` after `result_digest`.

### PF-v5 — `tests/test_sdk_find_partial_identity.py` SDK export guard verified

`tests/test_sdk_find_partial_identity.py:139-144` asserts SDK `__all__` length is 64 and checks selected public names. Adding `ResultFingerprint` must update this guard intentionally.

### PF-v6 — `tests/sdk/test_evaluate_result_exports.py` is the right export test

`tests/sdk/test_evaluate_result_exports.py:5-19` imports protocol DTOs and asserts SDK re-exports. Step 4.7 should add `ResultFingerprint` here.

### PF-v7 — Q-PR1 sacred paths are out of scope

Slice β edits `evaluate_result.py`, SDK/service/docs/tests. The Q-PR1 sacred paths remain:

- `src/factgraph/core/evidence/write_protocol.py`
- `src/factgraph/core/store/ledger.py`
- `src/factgraph/core/store/_builders.py`
- `src/factgraph/adapters/pyreason/`
- `src/factgraph/application/accept.py`

No preflight finding requires touching those paths.

### PF-v8 — No abandonment blocker

All findings fit Step 4.4 amendment and/or Step 4.6.5 deletion-grep fold. No design assumption is invalidated.

## 7. Scoped Details

### PF-s1 — `engine_meta` remains Mapping, not named DTO

Step 4.2 tightening makes `engine_meta` validated without changing the blueprint's chosen abstraction. Required compatibility keys are mandatory, but extra keys remain allowed for future metadata.

### PF-s2 — Keep `result_digest_for(...)` public helper signature

The preflight supports Option α-style preservation. Construction ergonomics can be improved locally, but the public helper should remain explicit-kwarg and byte-equal.

## 8. Step 4.4 Amendment Checklist

Apply these on the blueprint branch (`v0.2.0-blueprint-result-fingerprint-fold-2026-06-03`), not this preflight branch:

- [ ] PF-R1: add service runtime construction site to Related Modules, §5.5, §8 construction-site enumeration, and §7 acceptance.
- [ ] PF-R2: split service scope into construction + serializer duties.
- [ ] PF-R3: add the named active docs cascade list.
- [ ] PF-r1: add broader active-test verification or explicit warning-compatible classification.
- [ ] PF-r2: refresh §5.6 metadata consumer anchors.
- [ ] Add audit log Event Log row + Decision Notes for PF-R/PF-r/PF-v/PF-s.

## 9. Conclusion

Preflight verdict: **AMEND REQUIRED**.

No abandonment blocker. The Slice β design remains sound, but the blueprint must fold three Required findings before scoped anchor: service runtime construction, split service scope, and broader docs cascade.
