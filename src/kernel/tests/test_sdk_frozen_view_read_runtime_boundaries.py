from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, Query, ReadPolicy, Rule, SDKSchemaError, SDKStore, SDKStoreError, vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name": sdk.set(User.name, ref, "Alice", meta={"source": "seed"}),
    }
    return sdk, ids


def _name_rule():
    with vars("u", "name") as (u, name):
        return Rule(
            id="frozen_view_boundary.name",
            version="v1",
            select=[u, name],
            where=[User(u), u.name == name],
        )


def _name_query() -> Query:
    with vars("u", "name") as (u, name):
        return Query(
            head=[User(u), User.name(value=name)],
            where=[User(u), u.name == name],
        )


class FrozenViewReadBoundaryTests(unittest.TestCase):
    def test_readpolicy_find_path_uses_policy_kwarg(self) -> None:
        sdk, _ = _seed_store()
        spec = ReadPolicy(confidence_strategy="max")

        rows = sdk.read.find(User, policy=spec)

        self.assertEqual([row.name for row in rows], ["Alice"])

    def test_get_does_not_accept_view_parameter(self) -> None:
        sdk, _ = _seed_store()

        with self.assertRaises(SDKSchemaError):
            sdk.read.get(User, user_id="u-1", view="preferred")

    def test_find_rejects_removed_view_name_with_redirect_message(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view="review_set")

        msg = str(ctx.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_find_rejects_removed_view_object_with_redirect_message(self) -> None:
        sdk, ids = _seed_store()
        view = sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view=view)

        msg = str(ctx.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_run_display_meta_uses_policy_kwarg(self) -> None:
        sdk, _ = _seed_store()

        rows, meta = sdk.run(
            _name_rule(),
            policy=ReadPolicy(confidence_strategy="max"),
            row_format="dict",
            return_display_meta=True,
        )

        self.assertIsInstance(rows, list)
        self.assertIsInstance(meta, list)

    def test_run_rejects_removed_view_name_with_redirect_message(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_name_rule(), view="review_set", return_display_meta=True)

        msg = str(ctx.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_run_query_and_evaluate_view_rejections_remain(self) -> None:
        sdk, ids = _seed_store()
        sdk.views.create("review_set", asrt_ids=[ids["name"]])

        with self.assertRaises(SDKStoreError) as run_ctx:
            sdk.run(_name_query(), view="review_set")
        self.assertIn("policy", str(run_ctx.exception).lower())

        with self.assertRaises(SDKStoreError) as eval_ctx:
            sdk.evaluate("anything", view="review_set")
        self.assertIn("view", str(eval_ctx.exception))


if __name__ == "__main__":
    unittest.main()
