# Working Area

Temporary work area for short-lived artifacts: experimental scripts, ad-hoc test outputs, exploratory data, prototype code.

## Lifecycle

- Contents are **gitignored** (per `.gitignore` `workflow/working/*` rule from Step 0.1). Only this README and `.gitkeep` are tracked.
- Short-lived: hours to days; not persistent across sessions.
- Distinct from `/tmp/`: project-scoped, persists across reboots.
- Distinct from `workflow/heritage/`: heritage is permanent legacy archive; working is ephemeral.

## What goes here

- One-off scripts not worth packaging as a skill yet
- Test inputs / outputs being explored
- Notebook scratch
- API response captures during debugging
- Prototype code not yet ready for `src/`

## What does NOT go here

- Persistent work products (→ appropriate module / docs)
- Reference material (→ obsidian / `workflow/heritage/`)
- Module implementation truth (→ `src/factgraph/*/docs/`)

## Convention

If a working artifact proves valuable, package it as a Claude skill or promote it to a permanent location via a proper slice. Otherwise it can be safely deleted at any time.

No `Status` field, no metadata, no governance — this is a free-form work area.
