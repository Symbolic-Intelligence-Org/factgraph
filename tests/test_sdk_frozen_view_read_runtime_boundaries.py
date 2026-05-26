from __future__ import annotations

import unittest

from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, Rule, SDKSchemaError, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name": sdk.write.set(User.name, ref, "Alice", meta={"source": "seed"}),
    }
    return sdk, ids


def _name_rule() -> Rule:
    user = Var("$user")
    name = Var("$name")
    return Rule(
        id="user:name",
        where=(PredAtom("User:exists", [user]), PredAtom("user:name", [user, name])),
        ports={"user": user, "name": name},
    )


class FrozenViewReadBoundaryTests(unittest.TestCase):
    def test_get_does_not_accept_method_level_view_parameter(self) -> None:
        sdk, _ = _seed_store()

        with self.assertRaises(SDKSchemaError):
            sdk.read.get(User, user_id="u-1", view="preferred")

    def test_find_rejects_method_level_view_name_with_attach_hint(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view="review_set")

        msg = str(ctx.exception)
        self.assertIn("method-level view=", msg)
        self.assertIn("FactGraph.attach(db, view=view)", msg)

    def test_find_rejects_method_level_view_object_with_attach_hint(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view=view)

        msg = str(ctx.exception)
        self.assertIn("method-level view=", msg)
        self.assertIn("FactGraph.attach(db, view=view)", msg)

    def test_evaluate_rejects_method_level_view_with_attach_hint(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"]])
        rule = _name_rule()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(rule, head=rule, view="review_set")

        msg = str(ctx.exception)
        self.assertIn("method-level view=", msg)
        self.assertIn("FactGraph.attach(db, view=view)", msg)


if __name__ == "__main__":
    unittest.main()
