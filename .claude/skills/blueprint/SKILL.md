---
name: blueprint
version: 1.0.0
description: |
  Blueprint lifecycle management for this repository. Covers the full
  draft → scoped → implementing → implemented → archived workflow.
  Use when the user says "/blueprint", "open blueprint", "create blueprint",
  "archive blueprint", "review blueprint", or references a blueprint by name.
  Also triggers on "scope this", "start implementation plan", or "what blueprints
  are active".
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
  - Agent
  - AskUserQuestion
---

# Blueprint Lifecycle Skill

You manage the full blueprint lifecycle for this repository.

## Directory Layout

```
docs/blueprints/
├── active/          ← in-flight blueprints (draft / scoped / implementing)
├── archive/         ← completed blueprints (implemented / archived)
│   └── README.md    ← inventory table of all archived blueprints
└── templates/       ← blueprint and audit log templates (if present)
```

## Blueprint File Convention

- Blueprint: `docs/blueprints/active/YYYY-MM-DD_kebab-name.md`
- Audit log: `docs/blueprints/active/YYYY-MM-DD_kebab-name.audit.md`
- Both move together to `archive/` on completion.

## Lifecycle States

```
draft → scoped → implementing → implemented → archived
```

| State | Meaning |
|-------|---------|
| `draft` | Problem identified, shape not finalized |
| `scoped` | Contract frozen, ready for user review before implementation |
| `implementing` | Code work in progress |
| `implemented` | All phases complete, outcome filled, ready to archive |
| `archived` | Moved to `archive/`, inventory updated |

## Execution Modes

### 1. List Active Blueprints

When the user asks "what blueprints are active" or "/blueprint" with no arguments:

1. `Glob` for `docs/blueprints/active/*.md` (exclude `*.audit.md`)
2. For each, read the first 5 lines to extract `Status`
3. Present a table: `| File | Status | Title |`

### 2. Create New Blueprint

When the user asks to create/start a new blueprint:

1. Ask for: name (kebab-case), problem statement, and scope boundaries
2. Generate today's date prefix: `YYYY-MM-DD`
3. Create `docs/blueprints/active/YYYY-MM-DD_name.md` with this structure:

```markdown
# name

- Status: draft
- Created: YYYY-MM-DD
- Parent: (if applicable)

## 1. Problem
## 2. Goal
## 3. Non-Goals
## 4. Current Context
## 5. Design
## 6. Implementation Plan
## 7. Acceptance Criteria

## 8. Outcome

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
```

4. Create sibling `docs/blueprints/active/YYYY-MM-DD_name.audit.md`:

```markdown
# Audit Log: name

| Date | Status | Event | Details |
|------|--------|-------|---------|
| YYYY-MM-DD | draft | Blueprint created | (brief description) |
```

### 3. Open / Discuss Blueprint

When the user names a specific blueprint or asks to "open" one:

1. Resolve the path:
   - Full path → use directly
   - Filename → prepend `docs/blueprints/active/`
   - Short name / fragment → Glob match in `active/`, require unique match
2. Read the blueprint and its audit log
3. Present a brief summary: problem, goals, current status
4. Ask what to discuss: scope, goals, non-goals, acceptance, implementation plan, open questions

**Discussion edit boundary** (when refining a blueprint):
- May edit: Problem, Goal, Non-Goals, Current Context, Design, Implementation Plan, Acceptance Criteria
- May NOT edit: Status, Created, Outcome (these are maintainer-controlled)
- If uncertain about something, write it as an open question, not a conclusion

### 4. Status Transitions

When the user says "mark as scoped", "start implementing", etc.:

1. Read current status from the blueprint header
2. Validate the transition is legal (draft→scoped→implementing→implemented)
3. Update `- Status:` line
4. Append a row to the audit log

### 5. Archive Blueprint

When the user says "archive blueprint" or a blueprint reaches `implemented`:

1. Read the blueprint to confirm `Status: implemented` and `Outcome` is filled
2. Copy both `.md` and `.audit.md` from `active/` to `archive/`
3. Remove originals from `active/`
4. Append a row to `docs/blueprints/archive/README.md` inventory table

### 6. Exploration for Blueprint Authoring

When drafting or scoping a blueprint, you may need to explore the codebase:

1. Use `Grep` / `Glob` / `Read` to understand the current state of relevant modules
2. Use `Agent` with `subagent_type: "Explore"` for broader codebase exploration
3. Record findings in the blueprint's `§4. Current Context` section
4. Record unknowns as open questions, not assumptions

## Project-Specific Conventions

This repository follows a **blueprint-driven workflow**:
- Senior engineer (bilingual, Chinese primary) reviews all blueprints before implementation
- Blueprints should be precise about scope boundaries (what's in vs what's deferred)
- Implementation plans should reference specific files and line ranges
- Acceptance criteria should be testable assertions, not vague goals
- A PreToolUse hook blocks non-.md file edits in `src/factpy_kernel/`; code changes are provided as snippets for the user to apply

## Behavioral Rules

- Always read the blueprint before editing it
- Keep edits minimal and targeted to the requested change
- If expanding scope, make it explicit and ask for confirmation
- Never present discussion points as already-implemented behavior
- Use the audit log to track all significant decisions and changes
- When archiving, always update the archive inventory table
