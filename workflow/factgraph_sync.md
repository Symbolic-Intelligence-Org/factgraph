# factgraph ↔ hnsm-backend Sync Runbook

This repo (`origin` = hnsm-backend) is a **superset** of the `factgraph` kernel repo, sharing history. They are two **surfaces** of the same project:

- **`origin`** (hnsm-backend): backup/storage — we **push** here (everything), don't pull.
- **`factgraph/main`**: the **真源 / release surface** — we **pull** `main`, and **publish** via a `feature/`|`fix/` branch + PR (never push `main` directly).

Git ignore rules are a property of a **tree**, not a remote. So the surface split is **not** done with `.gitignore`/`exclude` — it's done by (a) what the publish carries, and (b) `merge=ours` on surface files.

## Path sets

**① kernel allowlist — carried hnsm→factgraph, kept aligned (CODE only):**
- `src/factgraph/**/*.py`  **minus**  `src/factgraph/**/docs/`  and  `src/factgraph/**/*.md`
- `docs/`  (SECURITY.md + quickstart/)
- `tests/`

**② surface files — each repo keeps its own (`merge=ours` on pull; not carried on publish):**
- root: `README.md` `pyproject.toml` `CHANGELOG.md` `CODE_OF_CONDUCT.md` `CONTRIBUTING.md` `LICENSE` `pixi.lock` `.github/`
- module docs: `src/factgraph/**/docs/`  `src/factgraph/**/*.md`  (hnsm = implementation truth)
- `.gitattributes` (hnsm-only; whitelisted in hnsm `.gitignore` via `!/.gitattributes`, absent on factgraph).
  `.gitignore` differs ONLY by that one line — pure hnsm-side addition, merges cleanly. The root-whitelist
  (`/*` + `!/*/`) keeps ALL root dirs trackable, so it does NOT ignore hnsm-only dirs — the surface split
  has no `.gitignore` safety net; the surgical publish (what it carries) is the only guard.

**③ hnsm-only — never carried to factgraph:**
- `workflow/ examples/ tools/ tutorials/ scripts/ requirements/ third_party/ .claude/ .tmp_backend_preview/ AGENTS.md .gitmodules`
- `src/agent/ src/domains/ src/service/`

## Setup (once per clone)

```bash
git config merge.ours.driver true     # makes .gitattributes merge=ours work
```

## Pull (factgraph/main → hnsm)

```bash
git fetch factgraph
git merge factgraph/main              # brings kernel; surface files auto-kept as hnsm's (merge=ours)
```

## Publish (hnsm → factgraph, kernel-only)

```bash
git fetch factgraph
git switch -c <feature|fix>/<topic> factgraph/main      # start from 真源 — no hnsm-only files present
git checkout <hnsm-branch> -- src/factgraph docs tests \
    ':(exclude)src/factgraph/**/docs/**' ':(exclude)src/factgraph/**/*.md'
git commit -m "..."
git push factgraph <feature|fix>/<topic>                # → open PR to factgraph/main
```

The `:(exclude)` pathspec drops module docs/READMEs so only **code** lands on factgraph.
Tip: run the publish in a dedicated `git worktree` so the main working tree (with hnsm-only files) is untouched.

## Residual

factgraph/main currently still carries module docs (`src/factgraph/**/docs/*.md`, READMEs) from past publishes. Going forward they are **not** carried (kept hnsm-side via `merge=ours`), so they freeze in factgraph. To make factgraph pure-code, do a one-time PR removing them.
