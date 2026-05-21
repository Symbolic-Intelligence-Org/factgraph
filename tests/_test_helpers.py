"""Shared fixtures for factgraph contract tests.

This module is intentionally prefixed with ``_`` so unittest discovery does
not treat it as a test file.
"""

from __future__ import annotations

from pathlib import Path

from factgraph.sdk import (
    Entity,
    Field,
    Identity,
    Pred,
    Rule,
    SDKStore,
    compile_schema_from_classes,
    vars as sdk_vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _register_exposed_user_tag_rule(
    sdk: SDKStore,
    registry_root: str | Path,
    *,
    rule_id: str = "q.child_rule",
    condition_weights: dict[str, float] | None = None,
) -> Rule:
    """Construct (and return) an exposed user.tag Rule for test scenarios.

    Q8 Phase 2 (Slice 6) removed `FileAuthoringRegistry.register_rule_spec`,
    so this helper no longer persists the rule to a registry. It now:
    - upserts the schema (still supported by FileAuthoringRegistry),
    - constructs the Rule value object, and
    - returns the Rule for the caller to pass directly to `fg.eval.run(...)`
      or to register as an ephemeral rule in a runtime session.

    Callers that previously relied on this helper's side-effect of FS
    registration must construct the rule via the returned value and register
    it through whatever in-memory mechanism the caller uses
    (`RuleRegistry.register(...)`, ephemeral-rule POST, etc.).
    """
    from factgraph.authoring import FileAuthoringRegistry

    registry = FileAuthoringRegistry(Path(registry_root))
    registry.upsert_schema_ir(sdk.schema_ir)
    with sdk_vars("u", "tag") as (u, tag):
        rule = Rule(
            id=rule_id,
            version="1.0.0",
            select=[u, tag],
            where=[Pred("user:tag", u, tag)],
            expose=True,
            condition_weights=condition_weights or {},
        )
    return rule


def _schema_ir() -> dict[str, object]:
    return compile_schema_from_classes([User])


def _seed_users_for_syntax_matrix(sdk: SDKStore) -> dict[str, str]:
    with sdk.batch() as tx:
        u1 = tx.entity(User, user_id="u-syntax-1", locale="zh")
        u1.name.set("Alice")
        u1.tag.add("vip")

        u2 = tx.entity(User, user_id="u-syntax-2", locale="en")
        u2.name.set("Bob")
        u2.tag.add("staff")

        u3 = tx.entity(User, user_id="u-syntax-3", locale="zh")
        u3.name.set("Carol")

        tx.commit(objects=[u1, u2, u3])

    return {
        "u1": u1.e_ref,
        "u2": u2.e_ref,
        "u3": u3.e_ref,
    }
