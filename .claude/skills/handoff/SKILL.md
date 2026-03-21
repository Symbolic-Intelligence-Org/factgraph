---
name: handoff
version: 1.0.0
description: |
  Generate or update a session handoff document for this repository. Creates a
  structured knowledge transfer file enabling a new agent to resume with full context.
  Use when the user says "/handoff", "create handoff", "update handoff", "session handoff",
  "prepare for session end", or "write handoff doc".
  Proactively suggest when the session has made significant progress (multiple blueprints
  completed, major capability landed) and the user signals winding down.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
---

# Session Handoff Skill

You generate structured session handoff documents that enable a new agent to resume
work with full context. The handoff is a **session restart reference**, not a substitute
for active blueprints, archived blueprints, or module docs.

## Output Location

- File: `docs/session_handoff_YYYY-MM-DD.md`
- Each new handoff supersedes the previous one
- Date is the current session date

## Handoff Document Structure

Generate the handoff with ALL of the following sections, in order:

### § 1. Current Stage

Brief narrative of what this session accomplished, building on the prior baseline.

1. List each major capability/commit landed (with commit hash if available)
2. State the **current position**: what's complete, what's the natural next direction
3. Reference the prior handoff if one exists

To gather this information:
```bash
git log --oneline -30   # recent commits
```

### § 2. Capability Baseline

Enumerate ALL stable capabilities, grouped by subsystem. For each:
- What it does (1-2 sentences)
- Key design decisions (bullet list)
- Whether it's new this session or carried from prior sessions

Read the most relevant module docs to get accurate descriptions:
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/annotation/docs/README.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

Include a **helper layering table** showing module → layer → dependencies → role.

### § 3. Git State

- Current branch
- This session's commits (chronological, with hashes and 1-line descriptions)
- Any uncommitted changes

```bash
git status --short
git log --oneline -30
```

### § 4. Blueprint Status Summary

Three subsections:

**Active Blueprints**: table of all files in `docs/blueprints/active/` with status and notes.

```bash
ls docs/blueprints/active/*.md 2>/dev/null | grep -v audit
```

**Key Archived Blueprints (this session)**: bullet list of blueprints archived during this session.

**Full Archive Inventory**: reference to `docs/blueprints/archive/README.md` with entry count.

### § 5. Test Baseline

- Total test count and status
- Run command
- Note if any tests are flaky or skipped

```bash
PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py" 2>&1 | tail -3
```

### § 6. Key Implementation Files

Two tables:

1. **New/changed files this session**: file path → role (1-line description)
2. **Module docs (implementation truth)**: file path → scope

### § 7. Frozen Contracts

List ALL frozen contracts (carried from prior handoffs + new this session).
Each entry: number, name, 1-line description.

**These contracts must NOT be reopened** without explicit user approval.

To find prior frozen contracts, read the previous handoff document.

### § 8. Known Gaps / Risk Assessment

For each known gap or pending design question:
- What exists (bullet list)
- What's missing (bullet list)
- Key scoping questions for the next blueprint

Read `src/factpy_kernel/core/annotation/docs/README.md` section 5 (Known Gaps) and
architecture docs for gap information.

### § 9. Collaboration Protocol

Document the working conventions:
1. Blueprint-driven workflow
2. Hook restrictions (what can/can't be edited directly)
3. Scope discipline
4. Contract-first approach
5. Docs sync requirements
6. Commit conventions
7. Decision-only blueprints
8. Archive inventory maintenance

### § 10. What the Next Agent Should Do

Three subsections:

**Recommended first action**: always start with a full test regression.

**Recommended next direction**: the most natural next capability line, with reasoning.

**What NOT to do**: explicit list of anti-patterns and frozen boundaries.

### § 11. Minimal Startup Reading List

Ordered list of files a new agent should read first, from most to least important.
Typically:
1. The handoff itself
2. Core architecture docs
3. Annotation/certainty docs
4. Service runtime queries docs
5. Audit overview docs
6. Key implementation files (the pattern to follow)
7. Archive index

## Generation Process

1. **Read prior handoff** (if exists) to carry forward frozen contracts and baseline info
2. **Scan git log** for this session's commits
3. **Read module docs** for accurate capability descriptions
4. **Check blueprint status** (active + recently archived)
5. **Run test suite** to get current count
6. **Read known gaps** from annotation docs and architecture docs
7. **Write the handoff** following the structure above
8. **Verify** the handoff is self-consistent (commit counts match, test counts match)

## Quality Checklist

Before finalizing, verify:
- [ ] All commit hashes are real (from git log)
- [ ] Test count matches actual run
- [ ] Frozen contracts include ALL prior + new
- [ ] No stale information carried from prior handoff without verification
- [ ] Active blueprint table matches actual `docs/blueprints/active/` contents
- [ ] Reading list files all exist
- [ ] Known gaps reflect current code state, not outdated assumptions
