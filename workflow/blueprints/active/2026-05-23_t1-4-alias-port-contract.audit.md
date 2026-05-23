# T1.4 Alias / Port Contract Audit Log

Status: draft
Last Updated: 2026-05-23
Blueprint: workflow/blueprints/active/2026-05-23_t1-4-alias-port-contract.md

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-05-23 | draft | Initial S-class blueprint drafted from parent §3.6 / shipped Rule port audit. |

## G1-G7 Mapping

### G1 Parent / Canonical Source

- Parent §3.6 defines ports as Rule's explicit public interface.
- Parent §3.6 lines 188-196 preview occurrence aliases and explicit joins.
- Parent §5.3 / C54 states cross-Rule alignment is by external port name, not internal Var name.
- Track plan T1.4 row scopes alias / port contract and RuleExpr `.as_()` infrastructure.

### G2 Source-Grep Audit

Read and/or grep:

- `src/factgraph/application/protocol/rule.py`
- `src/factgraph/sdk/dsl/application_rule.py`
- `tests/application/protocol/test_rule.py`
- `tests/application/protocol/test_rule_aggregate.py`
- `tests/sdk/dsl/test_application_rule.py`
- T1.1 / T1.2 / T1.3 archives and `workflow/memory/current.md`

### G3 File-Line Precision

Blueprint §4 cites parent and shipped source lines. Reviewer should independently verify:

- parent §3.6 port promises
- application Rule `ports` validation and `port_types`
- SDK bridge port conversion
- T1.4 row in track plan

### G4 Goal Mapping

- §2.1 maps to parent §3.6 port contract.
- §2.2 maps to parent §3.6 occurrence alias preview.
- §2.3 maps to T3 RuleExpr future join substrate.
- §2.4 maps to occurrence alias validation.
- §2.5 maps to docs upkeep.

### G5 Deviations

No semantic deviation intended. This slice implements substrate only and explicitly defers RuleExpr expression-level validation to T3.

### G6 Reviewer Spot-Check

Reviewer should check:

- Whether adding `RuleOccurrence.__getattr__` is too much for T1.4.
- Whether alias regex should allow only ASCII letter starts, as drafted, or a broader identifier-like shape.
- Whether `RulePortRef` should store `rule_id` or the full `Rule`.
- Whether docs should mention `.as_(...)` now or defer until T3 user-visible docs.

### G7 Pre-Impl Preconditions

Before implementation, record:

- current absence of `Rule.as_`
- current absence of `RuleOccurrence` / `RulePortRef`
- `Rule.ports` and `Rule.port_types` shape
- SDK bridge return type still application `Rule`
- sacred + dirty state

## Decision Notes

### Initial Scope Lock

T1.4 is S-class because it is additive, contained to application protocol Rule alias/port DTOs plus tests/docs, and does not implement RuleExpr composition or public SDK naming changes.

### Cross-Slice Contract Preservation

- T1.1 Rule DTO remains the template object.
- T1.2 bridge returns the same Rule object and should only benefit from new `.as_(...)`.
- T1.3 SDK top-level aliases remain unchanged.
- T2.3 aggregate port validation remains unchanged.
- T3 owns expression-level alias uniqueness and join reachability.

## Review Surface

Expected Step 4.2 review focus:

- Does T1.4 need only DTO substrate, or should `.as_(...)` be delayed to T3?
- Is `__getattr__` acceptable now, or should only explicit `.port(name)` ship?
- Is `RulePortRef` field set sufficient for T3 without binding future join syntax too early?
- Does alias validation need to reserve `rule.id` / duplicate checks now or leave to T3?
- Are docs over-promising before RuleExpr exists?
