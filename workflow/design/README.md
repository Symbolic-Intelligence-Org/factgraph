# Design Pillar

Conceptual design essays (`design-points/`) and ADR-style discrete decisions (`decisions/`).

See [`AGENTS.md`](./AGENTS.md) for the state machines, authority boundaries, and templates pointer. State machines were locked by Q2 (commit `ae375ce5`).

## Layout

- `design-points/{active,archive}/` — iteratively-evolving conceptual essays. Authority: **candidate design / non-authoritative reference. Not current behavior.**
- `decisions/{active,archive}/` — ADR records with 4-state lifecycle (`proposed` / `adopted` / `superseded` / `withdrawn`). `adopted` decisions stay in `active/` because they are current binding constraints.

## Templates

`workflow/templates/design/design-point.md` + `decision.md`.
