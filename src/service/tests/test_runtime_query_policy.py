"""Runtime view-facts tests for the removed ReadPolicy wire surface."""

from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _open_session() -> str:
    from service.runtime_v1 import open_runtime_session, reset_runtime_sessions_for_tests

    reset_runtime_sessions_for_tests()
    sdk = SDKStore([User])
    resp = open_runtime_session({"schema_ir": sdk.schema_ir})
    return resp["session"]["session_id"]


class RuntimeViewFactsPolicyRemovalTests(unittest.TestCase):
    def test_policy_payload_is_rejected(self) -> None:
        from service.runtime_v1 import project_runtime_view_facts

        result = project_runtime_view_facts(
            _open_session(),
            {"policy": {"confidence_strategy": "max"}},
        )

        self.assertFalse(result.get("ok"), result)
        message = str(result.get("errors", [])).lower()
        self.assertIn("readpolicy", message)
        self.assertIn("removed", message)
        self.assertIn("raw_kind", message)
        self.assertIn("bound", message)

    def test_missing_policy_returns_active_projection(self) -> None:
        from service.runtime_v1 import project_runtime_view_facts

        result = project_runtime_view_facts(_open_session(), {})

        self.assertTrue(result.get("ok"), result)
        view = result.get("view", {})
        self.assertIn("facts", view)
        self.assertNotIn("policy", view)
        self.assertNotIn("view_spec", view)

    def test_view_and_view_name_are_rejected_without_readpolicy_redirect(self) -> None:
        from service.runtime_v1 import project_runtime_view_facts

        for key in ("view", "view_name"):
            with self.subTest(key=key):
                result = project_runtime_view_facts(_open_session(), {key: "preferred"})
                self.assertFalse(result.get("ok"), result)
                message = str(result.get("errors", [])).lower()
                self.assertIn(key, message)
                self.assertNotIn("readpolicy", message)

    def test_removed_helpers_are_not_importable(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import _parse_read_policy  # noqa: F401
        with self.assertRaises(ImportError):
            from service.runtime_v1 import _read_policy_to_dict  # noqa: F401


if __name__ == "__main__":
    unittest.main()
