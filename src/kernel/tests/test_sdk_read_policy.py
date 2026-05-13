"""Regression tests for the removed SDK ReadPolicy surface."""

from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, Rule, SDKStore, SDKStoreError, vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _seed_store() -> SDKStore:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    sdk.set(User.name, ref, "Alice", meta={"source": "seed"})
    return sdk


def _name_rule() -> Rule:
    with vars("u", "name") as (u, name):
        return Rule(
            id="readpolicy.removed.name",
            version="v1",
            select=[u, name],
            where=[User(u), u.name == name],
        )


def _assert_removed_guidance(testcase: unittest.TestCase, message: str) -> None:
    lowered = message.lower()
    testcase.assertIn("readpolicy", lowered)
    testcase.assertIn("removed", lowered)
    testcase.assertIn("raw_kind", lowered)
    testcase.assertIn("bound", lowered)


class ReadPolicyRemovalTests(unittest.TestCase):
    def test_readpolicy_not_importable(self) -> None:
        with self.assertRaises(ImportError):
            from kernel.sdk import ReadPolicy  # noqa: F401

    def test_find_rejects_policy_kwarg(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, policy={"confidence_strategy": "max"})  # type: ignore[arg-type]

        _assert_removed_guidance(self, str(ctx.exception))

    def test_run_rejects_policy_kwarg(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_name_rule(), policy={"confidence_strategy": "max"})  # type: ignore[arg-type]

        _assert_removed_guidance(self, str(ctx.exception))

    def test_run_rejects_return_display_meta(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_name_rule(), row_format="dict", return_display_meta=True)

        _assert_removed_guidance(self, str(ctx.exception))

    def test_view_rejections_do_not_point_to_readpolicy(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.read.find(User, view="preferred")  # type: ignore[call-arg]

        self.assertIn("view", str(ctx.exception).lower())
        self.assertNotIn("ReadPolicy", str(ctx.exception))

    def test_evaluate_rejects_policy_kwarg(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.evaluate(object(), policy=object())  # type: ignore[call-arg]

        message = str(ctx.exception).lower()
        self.assertIn("policy", message)
        self.assertIn("removed", message)


if __name__ == "__main__":
    unittest.main()
