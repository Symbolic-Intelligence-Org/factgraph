from __future__ import annotations

import unittest

from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, Rule, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.entities.ref(User, user_id="u-1")
    ids = {
        "name": sdk.fields.set(User.name, ref, "Alice", meta={"source": "seed"}),
    }
    return sdk, ids


def _name_rule() -> Rule:
    user = Var("$user")
    name = Var("$name")
    return Rule(
        id="user:name",
        when=(PredAtom("User:exists", [user]), PredAtom("user:name", [user, name])),
        ports={"user": user, "name": name},
    )


class FrozenViewReadBoundaryTests(unittest.TestCase):
    def test_read_namespace_is_removed(self) -> None:
        sdk, _ = _seed_store()

        self.assertFalse(hasattr(sdk, "read"))

    def test_assertion_view_name_is_read_back_through_assertions_by_ids(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.assertion_views.create("review_set", asrt_ids=[ids["name"]])

        records = sdk.assertions.by_ids(view.asrt_ids, strict=True)

        self.assertEqual([record.asrt_id for record in records], [ids["name"]])

    def test_evaluate_rejects_method_level_view_with_attach_hint(self) -> None:
        sdk, ids = _seed_store()
        sdk.assertion_views.create("review_set", asrt_ids=[ids["name"]])
        rule = _name_rule()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(rule, head=rule, view="review_set")

        msg = str(ctx.exception)
        self.assertIn("method-level view=", msg)
        self.assertIn("FactGraph.attach(db, view=view)", msg)


if __name__ == "__main__":
    unittest.main()
