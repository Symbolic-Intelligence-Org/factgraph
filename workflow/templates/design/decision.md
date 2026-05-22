# Q<N> Decision: <topic>

- Status: proposed
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: design constraint; locks <what this decision locks> before <downstream consuming work>.
- Inputs:
  - <audit source pointer + §-cites>
  - <peer Q decisions if any depend>
  - <user-conversation locks or external references>
- Outputs / Downstream:
  - <implementing blueprint or consuming decisions>
- Related:
  - <peer Q decisions, sibling slices>
- Branch: `<branch ref where authored>`
- Depends on: <peer Q decisions, if any; otherwise omit>

> ADR 4-state lifecycle (per Q2 §4.5): `proposed` → `adopted` (current binding constraint, stays in `active/`) → `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` → `proposed` re-opening.

## 1. Inputs

Expanded narrative of the upstream inputs listed in the header. Source audit row citations, prior decision dependencies, user-conversation context.

## 2. Scope

What this decision locks.

## 3. Non-scope

What this decision explicitly does not lock; deferred to other decisions or implementing blueprints.

## 4. Decision

The actual locked content. Use sub-sections (§4.1, §4.2, ...) for multi-part decisions. Be explicit; downstream blueprints will cite by §-number.

## 5. Rejected Alternatives

Each rejected option with rationale. Format: `### Option (a-shortlabel): <description>` followed by `- **Why rejected**: ...`.

## 6. Supporting Evidence

Citations to audit rows, shipped code (file:line), prior decisions, external references. Strict per CADENCE Rule 1.

## 7. Consequences

### 7.1 Downstream unblocking
Which audit items / decisions / blueprint phases this decision unblocks.

### 7.2 Required follow-up actions
What the implementing blueprint must do as a consequence.

### 7.3-7.N (as needed)
Cross-pillar interaction, retrofit obligations, no-retroactive boundaries, validator dependencies, etc.

## 8. Acceptance Criteria

Checkboxes for verifying the decision is honored post-implementation.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| YYYY-MM-DD | proposed | Decision drafted | <brief context> |

Status transitions are appended as new rows when they happen.
