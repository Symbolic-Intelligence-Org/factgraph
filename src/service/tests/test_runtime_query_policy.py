"""Phase 1 G1.2 red-baseline tests for the ReadPolicy migration blueprint.

This file is the §7 G1.2 deliverable for blueprint
`docs/blueprints/active/2026-05-11_readpolicy-call-site-migration.md`:

T-NEW-5 — service runtime new shape + 5-endpoint removal + wire-level
field rename.

Covers §6 I6.1–I6.6:
- Service runtime carries no policy registry (`RuntimeSession.views`
  absent).
- 5 RPC endpoints removed: `create_runtime_view` / `update_runtime_view` /
  `delete_runtime_view` / `get_runtime_view` / `list_runtime_views`.
- `_resolve_runtime_view_spec` function removed.
- Wire DTO key `view` → `policy`; `view_name` lookup removed.
- Wire field `active` → `respect_revocations` inside policy object.
- Helper renames: `_parse_view_spec` → `_parse_read_policy`,
  `_view_spec_to_dict` → `_read_policy_to_dict`.

All ReadPolicy-dependent symbols are imported dynamically inside test
bodies; file collection succeeds even though `ReadPolicy` does not yet
exist.

Per §5.7 LOCKED implementation cross-reference, the service function
that consumes inline `dto["policy"]` post-migration is
`project_runtime_view_facts` (source-grounded at
`src/service/runtime_v1.py:831`). The §5.7 LOCKED text referred to
this flow as "query_view_facts" — that label is the `default_kind`
error-tag at line 882, not the function name. Phase 2 implementation
targets `project_runtime_view_facts`.

Error-message assertions are at the **semantic** level (`assertIn` on
substrings), not literal strings.
"""

from __future__ import annotations

import unittest
from typing import Any

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


# ---------------------------------------------------------------------------
# T-NEW-5a — Service endpoint removal (§6 I6.2)
# ---------------------------------------------------------------------------


class ServiceEndpointAbsenceTests(unittest.TestCase):
    """The 5 RPC endpoints for the legacy policy registry must be removed."""

    def test_create_runtime_view_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import create_runtime_view  # noqa: F401

    def test_update_runtime_view_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import update_runtime_view  # noqa: F401

    def test_delete_runtime_view_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import delete_runtime_view  # noqa: F401

    def test_get_runtime_view_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import get_runtime_view  # noqa: F401

    def test_list_runtime_views_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import list_runtime_views  # noqa: F401


# ---------------------------------------------------------------------------
# T-NEW-5b — Helper renames + dead-function removal (§6 I6.3, I6.5)
# ---------------------------------------------------------------------------


class ServiceHelperRenameTests(unittest.TestCase):
    """`_parse_view_spec` and `_view_spec_to_dict` are renamed; the dispatch
    helper `_resolve_runtime_view_spec` is removed entirely.
    """

    def test_resolve_runtime_view_spec_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import _resolve_runtime_view_spec  # noqa: F401

    def test_old_parse_view_spec_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import _parse_view_spec  # noqa: F401

    def test_old_view_spec_to_dict_is_removed(self) -> None:
        with self.assertRaises(ImportError):
            from service.runtime_v1 import _view_spec_to_dict  # noqa: F401

    def test_new_parse_read_policy_exists(self) -> None:
        # Post-migration: `_parse_read_policy` must be importable.
        from service.runtime_v1 import _parse_read_policy  # noqa: F401

    def test_new_read_policy_to_dict_exists(self) -> None:
        # Post-migration: `_read_policy_to_dict` must be importable.
        from service.runtime_v1 import _read_policy_to_dict  # noqa: F401


# ---------------------------------------------------------------------------
# T-NEW-5c — `RuntimeSession` carries no policy registry (§6 I6.1, I6.6)
# ---------------------------------------------------------------------------


class RuntimeSessionFieldAbsenceTests(unittest.TestCase):
    def test_runtime_session_has_no_views_attribute(self) -> None:
        from service.runtime_v1 import RuntimeSession

        # `dataclasses.fields` would also work; `__annotations__` covers the
        # source-locked field set. Either way, no `views` field must remain.
        annotations = getattr(RuntimeSession, "__annotations__", {})
        self.assertNotIn("views", annotations)


# ---------------------------------------------------------------------------
# T-NEW-5d — Wire field rename: `active` → `respect_revocations` (§6 I6.5)
# ---------------------------------------------------------------------------


class WireFieldRenameTests(unittest.TestCase):
    """`_parse_read_policy` consumes `respect_revocations`, NOT `active`.
    `_read_policy_to_dict` emits `respect_revocations`, NOT `active`.
    """

    def test_parse_read_policy_accepts_respect_revocations(self) -> None:
        from service.runtime_v1 import _parse_read_policy

        result = _parse_read_policy(
            {
                "respect_revocations": True,
                "confidence_strategy": "max",
                "prefer_source": "seed",
            },
            path="$.policy",
        )
        # Result is a ReadPolicy instance with the supplied values.
        self.assertEqual(getattr(result, "respect_revocations"), True)
        self.assertEqual(getattr(result, "confidence_strategy"), "max")
        self.assertEqual(getattr(result, "prefer_source"), "seed")

    def test_parse_read_policy_rejects_legacy_active_field(self) -> None:
        from service.runtime_v1 import _parse_read_policy

        # Old wire DTO with `"active"` must be rejected post-migration.
        # Semantic-level assertion: either the function raises, or it
        # ignores `active` entirely (silently dropping unknown keys).
        # We require an explicit raise so callers learn about the rename.
        with self.assertRaises(Exception) as exc:
            _parse_read_policy({"active": True}, path="$.policy")
        msg = str(exc.exception).lower()
        self.assertTrue(
            "active" in msg or "respect_revocations" in msg or "unknown" in msg,
            f"rejection message should mention the rename or the unknown field: {msg!r}",
        )

    def test_read_policy_to_dict_emits_respect_revocations_not_active(self) -> None:
        from kernel.sdk import ReadPolicy
        from service.runtime_v1 import _read_policy_to_dict

        policy = ReadPolicy(respect_revocations=False, confidence_strategy="mean")
        out = _read_policy_to_dict(policy)
        self.assertIn("respect_revocations", out)
        self.assertEqual(out["respect_revocations"], False)
        self.assertEqual(out["confidence_strategy"], "mean")
        # Discriminating: old field name must NOT appear in serialized output.
        self.assertNotIn("active", out)


# ---------------------------------------------------------------------------
# T-NEW-5e — Wire DTO key `view` → `policy` integration (§6 I6.4)
# ---------------------------------------------------------------------------


class ProjectRuntimeViewFactsInlinePolicyTests(unittest.TestCase):
    """`project_runtime_view_facts(sid, dto)` accepts `dto["policy"]` inline.

    Discriminator vs pre-migration:
    - Pre-migration: `dto["policy"]` is ignored; default `ViewSpec` used;
      response contains `view["view_spec"]` (legacy key).
    - Post-migration: `dto["policy"]` is parsed via `_parse_read_policy`;
      response contains `view["policy"]` (new key); no `view_spec` key.
    """

    def test_inline_policy_payload_succeeds(self) -> None:
        from service.runtime_v1 import project_runtime_view_facts

        sid = _open_session()
        result = project_runtime_view_facts(
            sid,
            {
                "policy": {
                    "respect_revocations": True,
                    "confidence_strategy": "max",
                }
            },
        )
        self.assertTrue(result.get("ok"), msg=str(result))
        view = result.get("view", {})
        # Post-migration: response uses `policy` key.
        self.assertIn("policy", view)
        # Discriminator: old `view_spec` key must be gone.
        self.assertNotIn("view_spec", view)

    def test_inline_policy_with_respect_revocations_false(self) -> None:
        from service.runtime_v1 import project_runtime_view_facts

        sid = _open_session()
        result = project_runtime_view_facts(
            sid,
            {
                "policy": {
                    "respect_revocations": False,
                    "confidence_strategy": "max",
                }
            },
        )
        self.assertTrue(result.get("ok"), msg=str(result))
        view = result.get("view", {})
        policy = view.get("policy", {})
        self.assertEqual(policy.get("respect_revocations"), False)

    def test_missing_policy_returns_no_display_facts(self) -> None:
        """When `dto["policy"]` is absent, no display_facts / no policy
        summary in response (mirrors SDK `policy=None` semantic).
        """
        from service.runtime_v1 import project_runtime_view_facts

        sid = _open_session()
        result = project_runtime_view_facts(sid, {})
        self.assertTrue(result.get("ok"), msg=str(result))
        view = result.get("view", {})
        # Post-migration: no policy field and no view_spec field.
        self.assertNotIn("policy", view)
        self.assertNotIn("view_spec", view)

    def test_view_name_lookup_path_is_removed(self) -> None:
        """Pre-migration `dto["view_name"]` looked up a registered ViewSpec.
        Post-migration: registry is gone; `view_name` is no longer a
        recognized DTO key. Either rejected explicitly or silently ignored
        (and falls into the no-policy path).
        """
        from service.runtime_v1 import project_runtime_view_facts

        sid = _open_session()
        result = project_runtime_view_facts(sid, {"view_name": "default"})
        # Either explicit error response OR ok-without-policy.
        if result.get("ok"):
            view = result.get("view", {})
            self.assertNotIn("view_spec", view)
            self.assertNotIn("policy", view)
        else:
            # Error response must mention removal / rename.
            errors = result.get("errors", [])
            self.assertTrue(errors, msg=str(result))


if __name__ == "__main__":
    unittest.main()
