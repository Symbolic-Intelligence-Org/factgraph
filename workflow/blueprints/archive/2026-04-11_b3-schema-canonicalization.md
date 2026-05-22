# Blueprint: B3 Schema Canonicalization — Parallel Canonical Fixture

- Status: implemented with deviations
- Created: 2026-04-11
- Kind: **scoped B3 fixture addition** (not a runner refactor, not an agent/kernel contract change)
- Parent (historical): [2026-04-11_load-test-runner-commit-path.md](../archive/2026-04-11_load-test-runner-commit-path.md) (archived, `implemented with deviations` — wiring complete, smoke blocked by schema non-canonicality)
- Trigger: second smoke test failure on 2026-04-11 at `open_runtime_session` with `predicates[0].arg_specs[0].name must be non-empty string`. Stop-rule fired. Reviewer chose Option 4a (parallel canonical fixture).
- Related Modules:
  - `docs/references/working/load-test-2026-04-11/test_schema_ir.json` (read-only — provisional schema, must NOT be modified)
  - `docs/references/working/load-test-2026-04-11/samples_manifest.yaml` (may gain one optional field)
  - `docs/references/working/load-test-2026-04-11/run_load_test.py` (small patch to load alternate schema in `--commit` mode)
- Audit Log:
  - [2026-04-11_b3-schema-canonicalization.audit.md](./2026-04-11_b3-schema-canonicalization.audit.md)

---

## 0. Scope

Add a **parallel canonical schema fixture** so that the B3 `--commit` path can open a runtime session through `service.runtime_v1.open_runtime_session(...)` without tripping the canonical schema validator. The existing provisional `test_schema_ir.json` is preserved unchanged for historical baseline compatibility with iter 4 / iter 5 / β.1 / format coverage.

**What this blueprint does**:

- Adds a new canonical schema file at `docs/references/working/load-test-2026-04-11/test_schema_ir_canonical.json`
- Adds one new optional field to `samples_manifest.yaml`: `commit_schema_ir_path` (string, relative to manifest directory), defaulting to the canonical file
- Patches `run_load_test.py` to load the canonical schema only in `--commit` mode and pass it to `_build_commit_stack()` instead of the provisional `schema_ir`
- Validates the new fixture by re-running the same smoke test the commit-path blueprint couldn't finish: `--commit --sample medium_02_blueprint_backref`
- Archives as `implemented` on smoke success, or `implemented with deviations` / `abandoned` if the canonical schema still fails the runtime validator

**What this blueprint does NOT do**:

- Does NOT modify `test_schema_ir.json` (explicit non-goal — preserves historical baselines)
- Does NOT modify any archived iter 4 / iter 5 / β.1 / format coverage artifact
- Does NOT change the extraction path's schema — extraction continues to use the provisional `test_schema_ir.json` via the existing `schema_ir_path` manifest field. Only the commit-path's runtime session open call uses the canonical fixture
- Does NOT touch any file under `src/factpy_kernel/`
- Does NOT add new tests (runner-layer integration coverage is still via the existing `test_agent_l4c2_workflow.py`)
- Does NOT modify the runner patches from the archived commit-path blueprint — `CommitStack`, `_build_commit_stack`, 4-call orchestrator sequence, CP-11 teardown, and CP-14 filter all stay as-is
- Does NOT switch to `HttpRuntimeAPI`, does NOT run a full 10-sample commit rerun, does NOT do human review on committed drafts — all out of scope
- Does NOT modify `SYSTEM_PROMPT_TEMPLATE` (β.1 verdict δ still holds)
- Does NOT modify `cross_run_observations.md` unless the smoke test surfaces a genuinely new cross-run finding
- Does NOT touch `generate_review_packet.py` or `format_coverage_generators/`
- Does NOT add a new run_record schema field (same as the archived commit-path blueprint's non-goal — any verification still goes via stdout `[commit_verify]` lines)

---

## 1. Problem

### 1.1 What the archived commit-path blueprint produced

The archived blueprint wired the B3 runner's commit path via the `ReadReviewOrchestrator` facade. Everything the runner needs is in place:

- `CommitStack` dataclass + `_build_commit_stack()` helper (13-component dependency tree)
- 4-call orchestrator sequence (`create_document_bundle` → `open_bundle_review` → `apply_bundle_review` → `commit_bundle`)
- CP-11 try/finally teardown (3 close calls)
- CP-14 filter (strips `_`-prefixed top-level keys from schema_ir before `open_dto`)
- `--commit` CLI flag, opt-in, dry-run stays default

The archived blueprint's smoke test failed at `_build_commit_stack → open_runtime_session(open_dto)`, TWICE, both on the canonical runtime validator. First at `"unexpected top-level keys: ['_note']"` (fixed by CP-14), then at `"predicates[0].arg_specs[0].name must be non-empty string"` (stop-rule triggered).

### 1.2 Why the provisional schema fails canonical validation

`test_schema_ir.json` was explicitly written at iter 2 as "Minimal smoke-test schema_ir for B3. Not a real FactPy SchemaIR — only satisfies the runner's preflight (non-empty dict with entities + predicates lists)". Over iterations 3-5 the prompt layer grew workarounds for the schema's non-canonical aspects (PS-01 positional fallback for nameless arg_specs, PS-05 silently skipping malformed identity_fields). These workarounds let extraction work end-to-end.

**But the canonical runtime validator inside `service.runtime_v1.open_runtime_session` was never exercised before the commit-path blueprint's smoke test.** It has stricter rules:

1. Top-level keys must be canonical (`_note` is rejected — CP-14 handles this)
2. Every `predicates[].arg_specs[].name` must be a non-empty string (the provisional schema omits `name` entirely on all 4 arg_specs)
3. Likely additional rules that haven't been probed yet (e.g., arg_spec `type_domain` must be in a canonical tag set, `entities[].identity_fields[].name` must be non-empty — note: identity fields DO have names in the current fixture, so this one may already pass)

Provisional schema state (from the failure report):

```
predicates[0] pred_id: document:mentions
  arg_specs[0]: keys=['type_domain'], has name=False   ← FAILS canonical validator
  arg_specs[1]: keys=['type_domain'], has name=False
predicates[1] pred_id: module:description
  arg_specs[0]: keys=['type_domain'], has name=False
  arg_specs[1]: keys=['type_domain'], has name=False

entities[0] entity_type: Document
  identity_fields[0]: keys=['name', 'type_domain'], has name=True   ← OK
entities[1] entity_type: Module
  identity_fields[0]: keys=['name', 'type_domain'], has name=True   ← OK
```

All 4 arg_specs across both predicates are nameless. Entities are fine.

### 1.3 Why "parallel canonical fixture" (4a) over alternatives

The reviewer evaluated three fix approaches on 2026-04-11:

- **4a — parallel canonical fixture**: new file next to the existing one, runner loads the right one per mode
- **4b — modify `test_schema_ir.json` in place**: rewrites the historical baseline
- **4c — runner schema canonicalization helper**: the runner synthesizes missing `name` fields programmatically

Reviewer chose **4a** with this reasoning:

> "我不建议 2 [4b]. 改共享 schema fixture 会污染之前 B3 各阶段的历史基线. 我也不建议现在 3 或 4 [4c / bigger blueprint]. 先让这 3 行级别的偏差把第一层错误剥掉, 信息价值最高."

And when 4c-style patching (CP-14) failed at the second layer:

> "选 先关当前 blueprint, 再开 4a"
>
> "具体判断: 继续在当前 blueprint 里补 schema, 会把"commit path wiring"和"schema canonicalization"两条线搅在一起. 4b 会污染历史 fixture, 不值得. 4c 会把 runner 变成 schema-normalizer, 边界最差."

The key advantage of 4a: **two separate files with two separate purposes**. The provisional schema stays as the iter 4/5/β.1/format coverage baseline (historical reproducibility). The canonical schema covers the commit-mode runtime validator. The runner makes a clean mode-based selection, not a runtime transformation.

### 1.4 Why this is a blueprint (not a working plan)

Three reasons:

1. **Adds a new source-of-truth file** to the B3 working directory. Even though it's a fixture and not code, the decision of what goes into a canonical B3 schema is a design decision that deserves scoping and acceptance criteria.
2. **Changes the runner's schema-loading contract** (reading one file vs two, conditional on `--commit`). This is a small contract change for a runner that is referenced by multiple archived blueprints' working flows.
3. **Closes out a smoke test that the previous blueprint could not finish**. This blueprint's success criterion is the same CP-12 acceptance that the commit-path blueprint couldn't verify — there's a direct causal chain the audit trail should document.

Working-plan-sized in the code patch sense (~31 lines to `run_load_test.py` per SC-11's ≤35 / >40 budget, ~1 new 50-line fixture file, ~1 line in `samples_manifest.yaml`), but blueprint-required per the "new source-of-truth file" trigger.

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| **SC-01** | **New canonical schema file at `docs/references/working/load-test-2026-04-11/test_schema_ir_canonical.json`**. Placed alongside the existing provisional `test_schema_ir.json`. Single filename convention with `_canonical` suffix | Parallel placement makes the relationship obvious at a directory listing. Filename suffix `_canonical` makes the purpose explicit without requiring anyone to open the file |
| **SC-02** | **Same entity types + same predicate IDs as the provisional schema** (Document, Module; document:mentions, module:description). Field values' `type_domain` values are also preserved (entity_ref + string). Only added: `name` field on every `predicates[].arg_specs[].*` entry | Preserves compatibility between extraction-layer drafts (generated from the provisional schema) and commit-layer runtime validation (running on the canonical schema). Drafts produced under the provisional schema can be committed under the canonical schema because `entity_type`, `pred_id`, and arg `type_domain` are identical — only the arg_spec `name` fields differ, and runtime fact writing doesn't reference arg_spec `name` (only `type_domain`) |
| **SC-03** | **Source fixture `test_schema_ir.json` is NOT modified**. Extraction path (both dry-run and commit mode) continues to read it via the existing `schema_ir_path` manifest field | Preserves the historical baselines for iter 4 / iter 5 / β.1 / format coverage. These phases' run_records, review packets, and archived artifacts all reference `test_schema_ir.json` as the pipeline input. Modifying it would invalidate comparisons against those baselines |
| **SC-04** | **Manifest gains one new optional top-level field: `commit_schema_ir_path`**. Type: string, relative path from manifest directory. Default: pointing at `./test_schema_ir_canonical.json`. Required if `--commit` is set and the default file doesn't exist | One-field extension avoids adding a whole new manifest subsection. Optional default matches the cleanest operator experience (no manifest change needed if the default file is in place) |
| **SC-05** | **Runner loads TWO schemas in `--commit` mode, ONE in dry-run mode**. Dry-run: `schema_ir` from `schema_ir_path` (unchanged). Commit: `schema_ir` from `schema_ir_path` for extraction + `commit_schema_ir` from `commit_schema_ir_path` for `_build_commit_stack`. The runner's `_run_single_sample()` still receives `schema_ir` (provisional) for the extraction call. `main()` passes `commit_schema_ir` to `_build_commit_stack()` | Extraction baseline preserved exactly — the LLM sees the same provisional schema it saw in β.1 / format coverage / iter 5, so extraction output (and especially the β.1 `medium_02_blueprint_backref` 10-draft baseline) is stable. Only the commit-layer runtime session uses the canonical schema. This decouples extraction quality from runtime canonicalization |
| **SC-06** | **`arg_spec` naming convention in the canonical schema: positional fallback** (`arg0`, `arg1`, `arg2`, ...) matching the prompts.py PS-01 convention | PS-01 already uses `arg{i}:type_domain` as its positional fallback when an arg_spec lacks a `name`. Reusing the same convention in the canonical fixture ensures consistency with the existing prompt-layer workaround and avoids inventing a new naming scheme. Alternative semantic names (`subject`/`topic`/`module`/`description`) are more readable but would require design discussion beyond this blueprint's scope. If the canonical runtime validator has additional rules that reject `arg0` format, a follow-up decision records the new convention |
| **SC-07** | **Zero changes to files under `src/factpy_kernel/`** | Schema canonicalization is an integration-layer fix; the agent and kernel source trees are read-only for this blueprint |
| **SC-08** | **Zero changes to iter 4 / iter 5 / β.1 / format coverage archived artifacts**. This includes run_records, review packets, summaries, plans, and cross_run_observations.md | Historical baselines are sealed evidence. New fixture files are additive, not substitutive |
| **SC-09** | **CP-14 from the archived commit-path blueprint stays in place** as defensive code. With a canonical schema that has no `_`-prefixed keys, the CP-14 filter becomes a no-op (prints nothing when there's nothing to strip), but removing it would eliminate a safety net against future non-canonical schemas being loaded into commit mode | Three lines of defensive code is cheap. Removing them creates a regression vector |
| **SC-10** | **Smoke test**: same as the archived blueprint — `--commit --sample medium_02_blueprint_backref`. Same acceptance criteria (bundle.committed_count > 0, bundle.preview_only = false, bundle.failed_count = 0, outcome.actual_result = "success", stdout `[commit_verify]` line with non-zero claim_count) | Consistency with the archived blueprint's CP-12 acceptance. Re-running the same sample closes the loop on "does the commit path work end-to-end?" |
| **SC-11** | **Runner patch to `run_load_test.py` is bounded to ~35 lines total** (hard cap at 40 lines — anything above 40 is a deviation worth flagging). Composition: new helper `_read_commit_schema_ir(manifest, manifest_dir)` (~20 lines); main() addition to load commit_schema_ir when `--commit` is set (~10 lines); 1 line change to the `_build_commit_stack()` call site; plus any `--commit` flag mutual-exclusion guards that surface during implementation | Surgical runner change. Does not modify `_build_commit_stack()` internals (still takes a `schema_ir` parameter, still filters `_`-prefixed keys via CP-14). Does not modify the extraction path. Does not modify `_run_single_sample()` signature. The budget was originally drafted at ~15-20 lines but §3.3.3's concrete sketch showed ~31 lines, so this row has been corrected to match the sketch. Single-valued budget: **≤35 lines target, >40 lines flags as deviation**. §3.3.3 and §6 Acceptance Criteria reference the same numbers |
| **SC-12** | **No new test files, no new runner files, no changes to `generate_review_packet.py`, no changes to `format_coverage_generators/*.py`**. Acceptance is runtime smoke test only | Same discipline as the archived commit-path blueprint. Runner-layer integration coverage at the test-suite level remains `test_agent_l4c2_workflow.py` |
| **SC-13** | **Stop rule**: if the canonical schema still fails `open_runtime_session` validation (different error or same error), STOP. Do NOT chain more patches. The next step becomes either a deeper schema redesign or an explicit `abandoned` outcome for this blueprint. Repeat of the reviewer's rule from 2026-04-11: *"如果第二次还是 runtime canonicalization failure, 先停, 不要继续补丁链"* — applied here to the first (and only) smoke test of the new canonical schema | Prevents infinite patch chains on a canonicalization rabbit hole. One-shot attempt. If it fails, the problem is either (a) the canonical validator has rules we haven't reverse-engineered yet (warrants deeper investigation, not another blueprint) or (b) the canonical schema needs a proper design review (warrants agent-layer involvement, not a B3 fixture tweak) |

### Explicit non-goals

- No modification of `test_schema_ir.json`
- No modification of `run_load_test.py` beyond SC-11's budget (≤35 lines target, >40 lines flags as deviation)
- No modification of `_build_commit_stack()`, `CommitStack`, CP-14 filter, or any other piece of the archived commit-path blueprint's runner patch
- No new entity types, no new predicates, no new type_domain values (the canonical schema is a **1:1 reshape** of the provisional schema with `name` fields added, nothing more)
- No changes to iter 4 / iter 5 / β.1 / format coverage historical baselines
- No changes to agent-side or kernel-side source
- No `HttpRuntimeAPI` wiring
- No full 10-sample commit rerun (smoke test only)
- No human review on committed drafts
- No schema design beyond positional naming (SC-06)
- No retroactive canonicalization audit (if more rules are discovered, that's a separate blueprint or an explicit abandonment)

---

## 3. The Fix

### 3.1 New file: `test_schema_ir_canonical.json`

**The canonical file is a true 1:1 mirror of `test_schema_ir.json`** (its byte content was verified on 2026-04-11 during scope check v1). Only two things change per SC-02:

1. The top-level `_note` key is removed
2. Each `predicates[].arg_specs[]` entry gains a positional `name` field (`arg0`, `arg1`)

**Everything else is byte-identical to the provisional fixture**, including:
- `schema_ir_version: "v1"`
- `entities[].arg_specs[]` (with `field_name`, `type_domain`, `cardinality` — note: entity arg_specs have `field_name`, not `name`, which is a distinct structure from predicate arg_specs and the canonical validator may treat them differently)
- `predicates[].relationship_type: "true"` (preserved on both predicates)
- `projection: {}`
- `protocol_version` object shape (`idref_v1`, `tup_v1`, `export_v1` as a nested dict)
- `generated_at` full ISO timestamp format (`"2026-04-11T00:00:00Z"`)

If the canonical runtime validator rejects any of these preserved fields, SC-13 stop rule fires (one-shot — no inline patching within this blueprint).

Full proposed content:

```json
{
  "schema_ir_version": "v1",
  "entities": [
    {
      "entity_type": "Document",
      "identity_fields": [
        {"name": "title", "type_domain": "string"}
      ],
      "arg_specs": [
        {"field_name": "title", "type_domain": "string", "cardinality": "single"}
      ]
    },
    {
      "entity_type": "Module",
      "identity_fields": [
        {"name": "module_name", "type_domain": "string"}
      ],
      "arg_specs": [
        {"field_name": "module_name", "type_domain": "string", "cardinality": "single"}
      ]
    }
  ],
  "predicates": [
    {
      "pred_id": "document:mentions",
      "relationship_type": "true",
      "arg_specs": [
        {"name": "arg0", "type_domain": "entity_ref"},
        {"name": "arg1", "type_domain": "string"}
      ]
    },
    {
      "pred_id": "module:description",
      "relationship_type": "true",
      "arg_specs": [
        {"name": "arg0", "type_domain": "entity_ref"},
        {"name": "arg1", "type_domain": "string"}
      ]
    }
  ],
  "projection": {},
  "protocol_version": {
    "idref_v1": "1.0",
    "tup_v1": "1.0",
    "export_v1": "1.0"
  },
  "generated_at": "2026-04-11T00:00:00Z"
}
```

Diff from `test_schema_ir.json` (the ONLY differences):

```diff
- "_note": "Minimal smoke-test schema_ir for B3. Not a real FactPy SchemaIR ...",
  "schema_ir_version": "v1",
  ...
  "predicates": [
    {
      "pred_id": "document:mentions",
      "relationship_type": "true",
      "arg_specs": [
-       {"type_domain": "entity_ref"},
-       {"type_domain": "string"}
+       {"name": "arg0", "type_domain": "entity_ref"},
+       {"name": "arg1", "type_domain": "string"}
      ]
    },
    {
      "pred_id": "module:description",
      "relationship_type": "true",
      "arg_specs": [
-       {"type_domain": "entity_ref"},
-       {"type_domain": "string"}
+       {"name": "arg0", "type_domain": "entity_ref"},
+       {"name": "arg1", "type_domain": "string"}
      ]
    }
  ],
  ...
```

One deleted top-level key + four `name` additions. No other changes.

### 3.2 Manifest field addition (one optional field)

`docs/references/working/load-test-2026-04-11/samples_manifest.yaml` gains one new top-level field:

```yaml
schema_version: "v1"
manifest_version: "2026-04-11-smoke-3"   # unchanged

schema_ir_path: "./test_schema_ir.json"         # existing — provisional schema for extraction
commit_schema_ir_path: "./test_schema_ir_canonical.json"   # NEW — canonical schema for runtime session

# ... rest of manifest unchanged ...
```

Version bump to smoke-4 is **optional**. The new field is additive and fully backward-compatible — dry-run mode never reads it. I lean toward bumping to smoke-4 to signal that a commit-mode field was added, but SC-04 leaves this decision flexible.

### 3.3 Runner patch (~31 lines; SC-11 budget: ≤35 target, >40 deviation)

Three small changes to `docs/references/working/load-test-2026-04-11/run_load_test.py`:

#### 3.3.1 New helper `_read_commit_schema_ir` (after `_read_schema_ir`)

```python
def _read_commit_schema_ir(
    manifest: dict[str, Any],
    manifest_dir: Path,
) -> dict[str, Any]:
    """Load the canonical schema used by --commit mode's runtime session.

    Reads `commit_schema_ir_path` from the manifest if present, otherwise
    falls back to `test_schema_ir_canonical.json` next to the manifest.
    This schema is DIFFERENT from `schema_ir_path` — extraction uses the
    provisional schema, while `--commit` uses this canonical schema only
    for `service.runtime_v1.open_runtime_session(...)`.
    """
    rel = manifest.get("commit_schema_ir_path", "./test_schema_ir_canonical.json")
    path = (manifest_dir / rel).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"commit mode requires a canonical schema; not found at: {path}"
        )
    with path.open() as f:
        return json.load(f)
```

#### 3.3.2 In `main()`, load the commit schema when `--commit` is set

After the existing `schema_ir = _read_schema_ir(schema_ir_path)` load:

```python
commit_schema_ir: dict[str, Any] | None = None
if not dry_run:
    try:
        commit_schema_ir = _read_commit_schema_ir(manifest, manifest_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: failed to load commit schema: {exc}")
        return 1
```

#### 3.3.3 Pass `commit_schema_ir` to `_build_commit_stack()` instead of `schema_ir`

The existing call (added by the archived commit-path blueprint) is:

```python
commit_stack = _build_commit_stack(
    scope=_build_scope(manifest["scope"]),
    schema_ir=schema_ir,
    commit_run_id=commit_run_id,
)
```

Change the `schema_ir=schema_ir` argument to `schema_ir=commit_schema_ir`:

```python
commit_stack = _build_commit_stack(
    scope=_build_scope(manifest["scope"]),
    schema_ir=commit_schema_ir,   # ← canonical schema, not provisional
    commit_run_id=commit_run_id,
)
```

That's the entire runner patch. No changes to `_build_commit_stack()` internals. No changes to `_run_single_sample()`. No changes to the extraction path (it still uses `schema_ir` from `schema_ir_path`).

**Line count**: +20 lines (helper) + ~10 lines (main() additions) + 1 line (call site edit) = **~31 lines**. Within SC-11's corrected single-valued budget (target ≤35 lines, deviation flag at >40 lines). No audit deviation needed unless the actual patch exceeds 40 lines during implementation.

### 3.4 No other files modified

- `test_schema_ir.json` — unchanged (SC-03)
- All files under `src/factpy_kernel/` — unchanged (SC-07)
- All iter 4 / iter 5 / β.1 / format coverage artifacts — unchanged (SC-08)
- `generate_review_packet.py`, `format_coverage_generators/*.py`, `run_records/*.json` — unchanged

---

## 4. Impact Analysis

### Code + data surface (max 3 files)

1. **New file**: `docs/references/working/load-test-2026-04-11/test_schema_ir_canonical.json` (~60 lines)
2. **Modified**: `docs/references/working/load-test-2026-04-11/samples_manifest.yaml` (+1 line for `commit_schema_ir_path`)
3. **Modified**: `docs/references/working/load-test-2026-04-11/run_load_test.py` (+~31 lines)

No other files touched.

### Docs / archive touch points (not counted against the 3-file surface)

- This blueprint: `docs/blueprints/active/2026-04-11_b3-schema-canonicalization.md` — outcome section filled, then moved to archive
- This blueprint's audit log: same directory
- Optional: new smoke test run_record at `run_records/b3_*_medium_02_blueprint_backref.json` (if the smoke test reaches `_run_single_sample()`)

### Backward compatibility

- **Dry-run mode**: byte-identical behavior. `commit_schema_ir_path` is never read in dry-run. No existing dry-run invocation is affected
- **Extraction path**: byte-identical behavior in both dry-run and commit mode. The provisional schema is still read from `schema_ir_path`. β.1 baseline (10 valid drafts on `medium_02_blueprint_backref`) should hold
- **Iter 4/5/β.1/format coverage reproducibility**: preserved. If anyone re-runs those historical invocations with the current runner, they'll still reference `test_schema_ir.json` only (dry-run) and produce results consistent with the archived baselines
- **Existing commit-path blueprint's CP-01 through CP-14**: all still honored. CP-14 filter is a no-op on a canonical schema but stays as defensive code (SC-09)

### Regression surface

- Full test suite: **977 tests, 2 skipped** (expected unchanged — this blueprint adds no tests and touches no production code)
- `test_agent_l4c2_workflow.py` (the reference pattern): untouched
- Dry-run smoke: should still work on any of the 10 existing samples
- Commit smoke: this blueprint's primary acceptance gate

### New failure modes introduced (in commit mode only)

1. **Missing canonical schema file**: if `commit_schema_ir_path` is set but the file doesn't exist, the runner prints an error and exits before building the commit stack. No tempdirs created, no runtime session opened. Clean failure path.
2. **Invalid canonical schema content**: if the new fixture happens to be malformed JSON, `_read_commit_schema_ir` raises during `json.load`. Handled by the main() try/except.
3. **Canonical schema still fails runtime validator**: if `open_runtime_session(open_dto)` rejects the new schema for a reason we didn't anticipate (new validator rule we didn't know about), the runner prints the error and exits. **SC-13 stop rule fires**: no further patches, no chain.
4. **Extraction produces drafts incompatible with the canonical schema**: unlikely because extraction-layer drafts reference `entity_type` + `pred_id` + `type_domain`, all of which are identical between the two schemas. Only `arg_spec.name` differs, and runtime fact writing doesn't use arg_spec names. If this mismatch somehow surfaces (e.g. the canonical validator's write path does reference `name`), the smoke test fails with a commit-time error rather than a schema-open error, and we diagnose from there

None of the new failure modes introduce new runner complexity — they're all single-file reads or existing orchestrator error paths.

---

## 5. Implementation Order

```
Step 1: Create test_schema_ir_canonical.json
        → content per §3.1
        → validate it's well-formed JSON by reading it via json.load()
        → no runtime execution

Step 2: Add commit_schema_ir_path field to samples_manifest.yaml
        → one new line, default ./test_schema_ir_canonical.json
        → manifest_version bump to smoke-4 is optional; recommend yes for audit trail

Step 3: Add _read_commit_schema_ir helper to run_load_test.py
        → ~20 lines after _read_schema_ir
        → no test coverage needed (follows same pattern as _read_schema_ir)

Step 4: Update main() to load commit_schema_ir when --commit is set
        → ~10 lines
        → fail-early error handling: print ERROR + return 1 if schema load fails

Step 5: Change the _build_commit_stack() call site in main() from
        schema_ir=schema_ir to schema_ir=commit_schema_ir
        → 1 line

Step 6: Compile-check run_load_test.py
        → python -m py_compile ...

Step 7: Run full regression
        → PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests
        → expected: 977 tests, 2 skipped (unchanged)

Step 8: Smoke test
        → PYTHONPATH=src python run_load_test.py \
              --manifest samples_manifest.yaml \
              --sample medium_02_blueprint_backref \
              --commit
        → verify SC-10 acceptance criteria against the new run_record
        → verify stdout [commit_verify] line shows claim_count > 0

Step 9: If smoke passes → fill §9 Outcome, flip status to implemented, archive
Step 10: If smoke fails → per SC-13 stop rule, STOP
         → do NOT patch the schema further
         → do NOT patch the runner further
         → report full failure shape and decide: implemented with deviations or abandoned
         → if abandoned, the commit path remains blocked pending a deeper investigation
```

---

## 6. Acceptance Criteria

### Files

- [ ] `test_schema_ir_canonical.json` exists at the correct path with the content sketched in §3.1
- [ ] File parses as valid JSON
- [ ] `samples_manifest.yaml` has the new `commit_schema_ir_path` field pointing to the canonical file
- [ ] `run_load_test.py` has the `_read_commit_schema_ir` helper and main() wiring
- [ ] Zero diffs to `test_schema_ir.json`
- [ ] Zero diffs to any file under `src/factpy_kernel/`
- [ ] Zero diffs to any iter 4 / iter 5 / β.1 / format coverage archived artifact
- [ ] Runner line count grew by ≤35 lines (SC-11 target). If >40 lines, flag as deviation in audit log per SC-11

### Regression

- [ ] Full test suite: **977 tests, 2 skipped** (unchanged)
- [ ] Any dry-run invocation (e.g. `--sample medium_02_blueprint_backref` without `--commit`) produces the same run_record shape as before this blueprint

### Smoke test (SC-10)

- [ ] Runner invoked with `--commit --sample medium_02_blueprint_backref` exits with code 0
- [ ] stdout shows `[commit] CP-14: stripped non-canonical schema_ir metadata keys for open_dto: []` (CP-14 filter is a no-op on the canonical schema — empty list confirms it was passed clean) OR the CP-14 log line is absent because there was nothing to strip
- [ ] stdout shows the per-run tempdir path via `[commit] tempdir: /var/folders/.../b3_commit_...`
- [ ] stdout shows the runtime_session_id after `_build_commit_stack()` returns
- [ ] New run_record `run_records/b3_<timestamp>_medium_02_blueprint_backref.json` has:
  - [ ] `bundle.committed_count > 0`
  - [ ] `bundle.preview_only = false`
  - [ ] `bundle.commit_note` contains `"committed"` and the runtime session ID
  - [ ] `bundle.failed_count = 0`
  - [ ] `outcome.actual_result = "success"`
- [ ] stdout contains at least one `[commit_verify]` line with `claim_count > 0` for at least one committed predicate (`document:mentions` or `module:description`)
- [ ] Per-run tempdir exists on disk after the run finishes, contains both `ledger.db` and `burr.db`
- [ ] stdout shows `[commit] tempdir kept for inspection: ...` after teardown
- [ ] No WARNING lines on stderr from teardown close calls

### Optional ledger content verification

- [ ] `sqlite3 $tempdir/ledger.db "SELECT COUNT(*) FROM <facts table>"` returns > 0 (only if you want to inspect the SQLite file directly; NOT required by acceptance — the `[commit_verify]` stdout signal already covers this)

---

## 7. Known Constraints

1. **Canonical validator rules not fully mapped**: we know it rejects non-canonical top-level keys (CP-14 worked around this) and requires `predicates[].arg_specs[].name`. We do NOT know the full set of rules it enforces. If the new canonical schema trips a rule we haven't anticipated (e.g. `type_domain` enum constraint, `projection` required format), SC-13 stop rule fires. We do not attempt to map all validator rules upfront because that would require reading the `service.runtime_v1` validator source — an agent-layer probe that falls outside "B3 fixture" scope.
2. **Schema name convention (`arg0`, `arg1`) is a guess**: SC-06 locks positional names. If the canonical validator has additional `name` pattern rules (e.g. must start with a letter, must match a regex, must correspond to a specific entity identity), the smoke test will surface that and SC-13 stop rule applies.
3. **`projection` field as empty dict is a guess**: the provisional schema has an empty `projection` dict. If the canonical validator expects a non-trivial projection structure, the smoke test will fail and SC-13 stop rule applies.
4. **Extraction baseline preservation is only theoretical**: SC-05 says extraction continues to use the provisional schema, so extraction output should be identical. But in commit mode both schemas are loaded by the runner, which slightly changes the startup sequence. The β.1 `medium_02_blueprint_backref` 10-draft baseline may shift by OBS-01 variance margins even with identical extraction inputs.
5. **No partial-commit test coverage**: like the archived blueprint, this smoke test uses a sample that β.1 showed has zero structural rejections. Actively exercising `commit_result.failed_count > 0` paths is out of scope; deferred to future commit work if ever needed.
6. **Orchestrator signature stability**: inherited from the archived commit-path blueprint. If `ReadReviewOrchestrator.commit_bundle(...)` or `create_document_bundle(...)` change signatures in the agent layer, the runner patch from the archived blueprint may break. This blueprint doesn't reintroduce that risk; it's inherited.
7. **SC-13 stop rule is strict**: no patch chains, no second attempts at schema tweaks within this blueprint. If the smoke test fails, the options are "close as implemented with deviations" (wiring still correct, schema design needs more work) or "abandon" (problem is deeper than fixture changes can fix). Either outcome is documented via §9 at close.

---

## 8. Open Questions (probe-only; SC-13 stop rule applies)

**Policy**: every open question below is resolved by observing the smoke test outcome with the SC-02 / SC-06 defaults in §3.1. If the smoke test rejects a specific choice, **SC-13 stop rule fires** — the blueprint does NOT retry with an alternative choice inline. The failure is classified (either `implemented with deviations` with a deviation note, or `abandoned` if the problem is structural) and handed back for separate scoping. **No patch chains within this blueprint.**

- [ ] **SC-Q1**: Does the canonical validator accept `arg_spec` names in the `arg0`/`arg1` positional format? **Probe**: the canonical schema in §3.1 uses positional names per SC-06. Run the smoke test. If the validator rejects with a name-format error, do NOT edit to semantic names inline — STOP and classify per SC-13. Alternative naming convention (semantic names like `subject`/`object`/`module`/`description`) is a separate future decision, not a retry loop.
- [ ] **SC-Q2**: Does the canonical validator accept an empty `projection` dict? **Probe**: the canonical schema in §3.1 uses `{}` mirroring the provisional schema (SC-02 byte-identical preservation). Run the smoke test. If the validator rejects with a projection-shape error, do NOT edit inline — STOP and classify per SC-13.
- [ ] **SC-Q3**: Does the canonical validator accept the preserved `schema_ir_version`, `protocol_version` (nested dict with `idref_v1` / `tup_v1` / `export_v1`), and `generated_at` (full ISO timestamp) values? **Probe**: the canonical schema in §3.1 mirrors all three byte-identically from the provisional file. Run the smoke test. If the validator rejects any of them, do NOT edit inline — STOP and classify per SC-13.
- [ ] **SC-Q4**: Should `manifest_version` bump from `smoke-3` to `smoke-4`? **Answer**: recommendation is yes (audit trail for the new field); not strictly required. Reviewer decides during scope check. This is cosmetic, not a smoke test probe — resolve before implementation, not via smoke test.
- [ ] **SC-Q5**: Should the runner also load and pass `commit_schema_ir` for **extraction** in commit mode (Option A from the stop-rule failure report), or only for the runtime session open (Option B, which SC-05 locks in)? **Closed**: Option B per SC-05. Extraction preservation is more valuable than schema unification.

**Three questions remain open as smoke test probes** (SC-Q1, SC-Q2, SC-Q3). **One remains as a cosmetic scope-check decision** (SC-Q4). **One is closed** (SC-Q5).

Per SC-13, probe outcomes have three possible readings:

- **Pass**: the canonical schema in §3.1 satisfies the validator → implementation proceeds to smoke test acceptance (§6)
- **Fail on one rule**: one probe surfaced an error → blueprint closes as `implemented with deviations`, deviation note records the validator rule that rejected, a follow-up blueprint (not this one) picks up the canonicalization work with the new rule known
- **Fail on multiple rules sequentially**: impossible within this blueprint because the stop rule fires on the first smoke test failure; there is no "sequentially" path. If the single smoke test surfaces multiple errors at once, that still counts as one failure event and the blueprint classifies accordingly

This is a one-shot probe. Not a patch-and-retry loop.

---

## 9. Outcome / Deviations

**Final status: implemented with deviations**

### Landed (3-file implementation)

All three implementation artifacts landed as designed:

1. **`docs/references/working/load-test-2026-04-11/test_schema_ir_canonical.json`** — new, 51 lines. Verified programmatically as an exact byte-semantic `provisional minus _note plus 4 arg_spec name` transform of `test_schema_ir.json`. Preserves `schema_ir_version`, `entities[]` with `arg_specs` (`field_name`/`type_domain`/`cardinality`), `predicates[].relationship_type: "true"`, `projection: {}`, nested `protocol_version` (`idref_v1`/`tup_v1`/`export_v1`), and the full ISO `generated_at` timestamp. Only intentional changes: drop `_note`, add `name` to the four `predicates[].arg_specs[]` entries (using the positional `arg0`/`arg1` convention per SC-06).
2. **`docs/references/working/load-test-2026-04-11/samples_manifest.yaml`** — bumped from `smoke-3` to `smoke-4`, +1 new top-level field `commit_schema_ir_path: "./test_schema_ir_canonical.json"`, +10 file lines (field + header comment block documenting smoke-4 addition).
3. **`docs/references/working/load-test-2026-04-11/run_load_test.py`** — +43 lines (1325 → 1368). New `_read_commit_schema_ir(manifest, manifest_dir)` helper, new `main()` commit schema load block gated on `not dry_run`, `assert commit_schema_ir is not None` safety guard, and call site edit passing `schema_ir=commit_schema_ir` to `_build_commit_stack()`. CP-14 filter retained per SC-09.

Compile check passed. Full regression: **977 tests / 2 skipped** (exact match with iter 5 baseline). SC-07 held (zero diffs under `src/factpy_kernel/`). SC-12 held (no new tests, no new runner files, `generate_review_packet.py` and `format_coverage_generators/` untouched).

### Deviation 1 — SC-11 line budget overrun (accepted via Option A)

Runner patch actual: **+43 lines**. SC-11 target: ≤35 lines. SC-11 hard cap: >40 lines flags as deviation. Overrun: **+3 above the hard cap, +8 above the target**.

Breakdown:
- `_read_commit_schema_ir` helper: +25 lines (planned ~20; 5 over due to docstring carrying blueprint path + SC-02/04/05 citations for traceability)
- `main()` commit schema load block: +14 lines (planned ~10; 4 over due to dedicated `FileNotFoundError` branch separate from the generic `Exception` catch — two-branch shape is more informative at failure time)
- `assert commit_schema_ir is not None` runtime safety guard before `_build_commit_stack` call: +4 lines (not in §3.3 sketch — added during implementation as a regression-prevention net)
- Call site edit + blank lines + comments: 0 net

**Reviewer decision (2026-04-11)**: Option A — accept the deviation, do NOT trim. Rationale: *"多出来的行里, FileNotFoundError 分支和 assert commit_schema_ir is not None 都是有价值的防御, 不是装饰. 为了把 +43 压回 ≤35 去删这些, 收益不够."* Option B (trim to ≤35) and Option C (amend SC-11 to ≤40/>45) explicitly rejected. SC-11 row in §2 frozen decisions is NOT amended — budget stays ≤35 / >40 as the historical target. This is recorded as a discrete deviation event, not a scope change.

### Deviation 2 — SC-10 smoke test surfaced a third canonical validator rule (SC-13 stop rule fired)

Smoke test (SC-10): `--commit --sample medium_02_blueprint_backref`. Exit code: **1**. Failure site: `_build_commit_stack` → `service.runtime_v1.open_runtime_session(open_dto)` — the same entry point that blocked both commit-path blueprint smoke attempts.

Failure mode:

```
ERROR: failed to build commit stack: open_runtime_session failed:
  {'ok': False,
   'errors': [{'kind': 'runtime',
               'path': '',
               'details': {'message': 'predicates[0].group_key_indexes must be list'}}],
   'meta': {}}
```

Traceback: `run_load_test.py:1289` (main) → `run_load_test.py:405` (`_build_commit_stack`, the `raise RuntimeError(f"open_runtime_session failed: {resp}")` guard).

The canonical schema (§3.1) did not anticipate the `group_key_indexes` field on predicates — the provisional `test_schema_ir.json` does not have it, and SC-02's "minimum diff" framing explicitly preserved the provisional shape on every field not named in SC-02. This is exactly the kind of unknown that SC-13's strict one-shot policy was designed to surface cleanly rather than chain-patch through.

**SC-13 stop rule fired correctly.** Per SC-13:

> "Strict stop rule: if smoke test fails, STOP — do not patch the canonical schema further within this blueprint."

No inline retry was attempted. The blueprint classifies as `implemented with deviations` — the 3-file implementation is landed and working at every layer except the canonical validator, which rejected on a third rule that neither prior commit-path smoke attempts nor this blueprint's §3.1 fixture design anticipated.

**Cumulative canonical validator rules discovered across 3 smoke attempts** (documented here as the audit-trail record for any future follow-up work):

1. `unexpected top-level keys: ['_note']` — fixed by commit-path blueprint's CP-14 runner filter (stripping `_`-prefixed keys before `open_dto`).
2. `predicates[0].arg_specs[0].name must be non-empty string` — fixed by this blueprint's SC-02 (adding `name` to all four `predicates[].arg_specs[]` entries in the canonical fixture).
3. `predicates[0].group_key_indexes must be list` — **not fixed** (SC-13 fired). The canonical validator requires this field to be present as a list on each predicate, but the provisional schema omits it entirely, and SC-02 did not synthesize it.

Three smoke attempts, three different rules surfaced. Each attempt was expensive (runner patch + full regression + tempdir + smoke invocation), and each surfaced only one new rule at a time — the validator returns on the first violation rather than aggregating. Probing canonical-schema requirements one rule at a time through the runner is provably slow and provably unbounded (no upper limit on how many more rules exist beyond these three).

### Recommendation (carry-forward to any follow-up work)

**Stop probe-by-smoke.** Do not open a fourth blueprint that adds `group_key_indexes` to the canonical fixture and reruns the smoke test. That would almost certainly surface a fourth rule, then a fifth, and so on.

If future work needs a working canonical schema for the B3 commit path, the two sustainable paths are:

1. **Read the canonical validator source directly.** The validator lives inside `service.runtime_v1.open_runtime_session(...)` (and whatever helper it delegates to). Read that code, enumerate the full rule set for `SchemaIR`, and write a canonical fixture that satisfies all of them in one pass. This converts an unbounded probing problem into a bounded reading problem.
2. **Reuse an existing canonical schema from the production code path.** Somewhere in the kernel or test fixtures there is at least one `SchemaIR` payload that passes the canonical validator (otherwise no production flow could open a runtime session). Find it, copy it into the B3 fixture directory under a new name, adapt only the entity types / predicate IDs to match B3's `Document` / `Module` / `document:mentions` / `module:description` set, and keep every other field shape intact.

Both paths replace "guess a field, run smoke, guess another" with "know the answer before you patch." Either one is a separate blueprint with a separate scope, distinct from this one.

### Tempdir status

Three empty B3 commit tempdirs remain on disk (at `/var/folders/05/6btr2vg13b9gvgs3gxt8fw_40000gn/T/b3_commit_*`) from the 3 smoke attempts across the two blueprints:

- `b3commit_20260411T163857Z_froam1fe` (commit-path smoke 1 — pre-CP-14, rule 1)
- `b3commit_20260411T165352Z_27y99k_2` (commit-path smoke 2 — post-CP-14, rule 2)
- `b3commit_20260411T192640Z_xxuwm1xi` (schema-canonicalization smoke — rule 3)

All three are empty (no `ledger.db` / `burr.db` written) because `_build_commit_stack` raised before `AgentCheckpointStore` / `CandidatePayloadCache` creation. Per reviewer instruction, they are left in place and not deleted.

### Follow-up observations log

**No new entry in `cross_run_observations.md`.** Per reviewer (2026-04-11): *"不建议再加新的 OBS"*. The three validator rules are documented in this §9 Outcome and the audit log as the canonical record. OBS-01 (LLM variance at temperature=0), OBS-02 (Pattern B predicate crossover), and FUP-01 are untouched.

### Downstream state

- Archived commit-path blueprint (`2026-04-11_load-test-runner-commit-path.md`): still `implemented with deviations`. Runner wiring still correct. Still blocked on canonical validator at the same entry point.
- This blueprint: `implemented with deviations`. 3-file implementation landed. Smoke blocked on a third canonical validator rule. Carry-forward recommendation: stop probe-by-smoke, switch to source-reading or existing-fixture reuse.
- B3 `--commit` mode: **not yet end-to-end validated**. Runner builds a `CommitStack` up to the point of `open_runtime_session`, and fails there. This is the same state the commit-path blueprint ended in — this blueprint moved the failure from validator rule 2 to validator rule 3 but did not unblock the end-to-end commit path.
- B3 `--dry-run` mode: unchanged. All prior iter 4 / iter 5 / β.1 / format coverage artifacts remain valid.
- `src/factpy_kernel/`: unchanged. SC-07 held.

### Continuation direction

Any future blueprint that aims to unblock the B3 commit path must start by **reading the canonical validator source** (or reusing an existing canonical `SchemaIR` fixture) rather than probing validator rules one at a time through smoke tests. Otherwise the same one-rule-per-attempt pattern will repeat.
