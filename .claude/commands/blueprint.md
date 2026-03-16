---
description: Open a blueprint for discussion using the blueprint-editor agent
---

Use the blueprint-editor subagent to begin a focused discussion on the specified blueprint.

The blueprint to discuss is: $ARGUMENTS

If $ARGUMENTS is empty, list all files matching `docs/blueprints/active/*.md` (excluding `*.audit.md` and `README.md`) and ask the user which one to open.

Otherwise, resolve the blueprint as follows:
- If $ARGUMENTS is a full relative path under `docs/blueprints/active/`, use it directly
- If $ARGUMENTS is a filename like `2026-03-15_example-blueprint.md`, resolve it as `docs/blueprints/active/2026-03-15_example-blueprint.md`
- If $ARGUMENTS is a basename without extension like `2026-03-15_example-blueprint`, resolve it as `docs/blueprints/active/2026-03-15_example-blueprint.md`
- If $ARGUMENTS is a short name or title fragment, use Glob inside `docs/blueprints/active/` to find matching non-audit blueprint files; if exactly one matches, use it; if multiple match, list them and ask the user to specify

Once the blueprint is resolved, launch the blueprint-editor subagent with the following prompt:

"Please read [resolved blueprint path] and greet the user with a brief summary of the blueprint (problem, goals, current status). Then ask what aspect they would like to discuss or refine: scope, goals, non-goals, acceptance criteria, implementation plan, open questions, or alternatives."
