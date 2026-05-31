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
    SDKStore,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from factgraph.sdk.dsl import Rule


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


def _register_exposed_user_tag_rule(
    sdk: SDKStore,
    registry_root: str | Path | None = None,
    *,
    rule_id: str = "q.child_rule",
    condition_weights: dict[str, float] | None = None,
) -> Rule:
    """Construct (and return) an exposed user.tag Rule for test scenarios.

    Slice 7C / Q6-A (a.2): FileAuthoringRegistry was deleted in this slice.
    This helper now constructs and returns an in-memory ``Rule`` value only.
    The ``registry_root`` parameter is preserved (defaulted to ``None``) for
    call-site signature compatibility but is otherwise ignored — callers
    must register the returned Rule via an in-memory mechanism (e.g.
    ``RuleRegistry.register(...)`` or the runtime ephemeral-rule endpoint).
    """
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
