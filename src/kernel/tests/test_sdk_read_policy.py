"""Phase 1 G1.1 red-baseline tests for the ReadPolicy migration blueprint.

This file is the §7 G1.1 deliverable for blueprint
`docs/blueprints/active/2026-05-11_readpolicy-call-site-migration.md`:

- T-NEW-6 — absence invariant: `ViewSpec` no longer importable.
- T-NEW-1 — `ReadPolicy` DTO contract.
- T-NEW-2 — `policy=` acceptance / rejection on `find` / `run` / `evaluate`.
- T-NEW-4 — `view=` removal redirect guards on `find` / `run` / `evaluate`,
  including the `run(view=None)` tombstone discriminating gate per §6 I5.3.

All `ReadPolicy` imports are dynamic (inside test bodies) so file collection
does not depend on the not-yet-implemented class. `ViewSpec` is never
imported at top level either, since `from kernel.core.store.types import
ViewSpec` will raise `ImportError` post-migration.

Error-message assertions are at the **semantic** level (`assertIn` on
substrings), not literal strings, per §5.4 / §5.5 / §5.6 LOCKED text
freedom.
"""

from __future__ import annotations

import unittest
from typing import Any

from kernel.sdk import (
    Entity,
    Field,
    Identity,
    SDKStore,
    SDKStoreError,
)
from kernel.sdk.store import FrozenAssertionView


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_store() -> tuple[SDKStore, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name": sdk.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": sdk.add(User.tag, ref, "vip", meta={"source": "seed"}),
    }
    return sdk, ids


# ---------------------------------------------------------------------------
# T-NEW-6 — Absence invariant (§6 I5.1, I7.3)
# ---------------------------------------------------------------------------


class AbsenceInvariantTests(unittest.TestCase):
    """`ViewSpec` must not be importable post-migration.

    Imports are scoped inside the test body so file collection does not
    depend on the still-importable pre-migration class.
    """

    def test_viewspec_not_importable_from_kernel_sdk(self) -> None:
        with self.assertRaises(ImportError):
            from kernel.sdk import ViewSpec  # noqa: F401

    def test_viewspec_not_importable_from_core_store_types(self) -> None:
        with self.assertRaises(ImportError):
            from kernel.core.store.types import ViewSpec  # noqa: F401


# ---------------------------------------------------------------------------
# T-NEW-1 — ReadPolicy DTO contract (§6 I1.1–I1.5)
# ---------------------------------------------------------------------------


class ReadPolicyDTOContractTests(unittest.TestCase):
    """`ReadPolicy` is a frozen dataclass with 3 fields and locked validation.

    All tests dynamically import `ReadPolicy` from `kernel.sdk` so the file
    collects cleanly while `ReadPolicy` does not yet exist.
    """

    def test_default_construction_yields_locked_defaults(self) -> None:
        from kernel.sdk import ReadPolicy

        policy = ReadPolicy()
        self.assertEqual(policy.respect_revocations, True)
        self.assertEqual(policy.confidence_strategy, "max")
        self.assertIsNone(policy.prefer_source)

    def test_respect_revocations_must_be_bool_not_int_one(self) -> None:
        from kernel.sdk import ReadPolicy

        with self.assertRaises(ValueError) as exc:
            ReadPolicy(respect_revocations=1)  # type: ignore[arg-type]
        self.assertIn("respect_revocations", str(exc.exception))

    def test_respect_revocations_int_zero_rejected(self) -> None:
        from kernel.sdk import ReadPolicy

        with self.assertRaises(ValueError):
            ReadPolicy(respect_revocations=0)  # type: ignore[arg-type]

    def test_confidence_strategy_rejects_unknown_literal(self) -> None:
        from kernel.sdk import ReadPolicy

        with self.assertRaises(ValueError) as exc:
            ReadPolicy(confidence_strategy="bogus")  # type: ignore[arg-type]
        self.assertIn("confidence_strategy", str(exc.exception))

    def test_confidence_strategy_accepts_each_literal(self) -> None:
        from kernel.sdk import ReadPolicy

        for strategy in ("max", "mean", "median", "prefer_source"):
            ReadPolicy(confidence_strategy=strategy)  # type: ignore[arg-type]

    def test_prefer_source_none_and_non_empty_string_accepted(self) -> None:
        from kernel.sdk import ReadPolicy

        ReadPolicy(prefer_source=None)
        ReadPolicy(prefer_source="seed")

    def test_prefer_source_empty_string_rejected(self) -> None:
        from kernel.sdk import ReadPolicy

        with self.assertRaises(ValueError) as exc:
            ReadPolicy(prefer_source="")
        self.assertIn("prefer_source", str(exc.exception))

    def test_prefer_source_rejects_non_string(self) -> None:
        from kernel.sdk import ReadPolicy

        with self.assertRaises(ValueError):
            ReadPolicy(prefer_source=42)  # type: ignore[arg-type]

    def test_frozen_dataclass_rejects_setattr(self) -> None:
        from dataclasses import FrozenInstanceError

        from kernel.sdk import ReadPolicy

        policy = ReadPolicy()
        with self.assertRaises(FrozenInstanceError):
            policy.respect_revocations = False  # type: ignore[misc]

    def test_equality_and_hashable(self) -> None:
        from kernel.sdk import ReadPolicy

        a = ReadPolicy(confidence_strategy="max", prefer_source="seed")
        b = ReadPolicy(confidence_strategy="max", prefer_source="seed")
        c = ReadPolicy(confidence_strategy="mean", prefer_source="seed")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(hash(a), hash(b))


# ---------------------------------------------------------------------------
# T-NEW-2 — `policy=` acceptance / rejection (§6 I4.1–I4.5)
# ---------------------------------------------------------------------------


class PolicyAcceptanceFindTests(unittest.TestCase):
    """`sdk.read.find(..., policy=...)` accepts only `ReadPolicy | None`.

    `dict`, `str`, `FrozenAssertionView`, and other types raise
    `SDKStoreError`. Error message must mention both "policy" and the
    expected DTO name (`ReadPolicy`) to discriminate from old-behavior
    "User has no field 'policy'" errors.
    """

    def test_find_accepts_readpolicy_attaches_confidence(self) -> None:
        from kernel.sdk import ReadPolicy

        sdk, _ = _seed_store()
        rows = sdk.read.find(User, policy=ReadPolicy(confidence_strategy="max"))
        self.assertTrue(
            any(getattr(row, "confidence", None) is not None for row in rows)
        )

    def test_find_policy_none_returns_rows_without_confidence(self) -> None:
        sdk, _ = _seed_store()
        rows = sdk.read.find(User, policy=None)
        for row in rows:
            self.assertIsNone(getattr(row, "confidence", None))

    def test_find_rejects_dict_policy(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, policy={"confidence_strategy": "max"})  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)

    def test_find_rejects_str_policy(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, policy="preferred")  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)

    def test_find_rejects_frozen_assertion_view_policy(self) -> None:
        sdk, _ = _seed_store()
        view = FrozenAssertionView(name="x", asrt_ids=frozenset())
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, policy=view)  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)

    def test_find_rejects_int_policy(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, policy=42)  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)


class PolicyAcceptanceRunTests(unittest.TestCase):
    """`sdk.run(..., policy=...)` accepts only `ReadPolicy | None`.

    Tests target the kwarg-validation entry point. Tests use `object()` as
    the rule placeholder; the test assertions discriminate on error
    *message content* so dispatch failures (which raise SDKStoreError with
    no `policy`/`readpolicy` in the message) do not falsely pass.
    """

    def test_run_rejects_dict_policy(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), policy={"confidence_strategy": "max"})  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)

    def test_run_rejects_str_policy(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), policy="preferred")  # type: ignore[arg-type]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("readpolicy", msg)

    def test_run_with_return_display_meta_and_policy_none_raises(self) -> None:
        """§6 I4.4 invariant: `return_display_meta=True ⇒ policy is not None`.

        Semantic-level assertion; the message must reference both
        `return_display_meta` (or `display`) and `policy` to discriminate
        from the old `view`-based wording.
        """
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), policy=None, return_display_meta=True)
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        # Either "display" or "return_display_meta" must appear
        self.assertTrue(
            "display" in msg or "return_display_meta" in msg,
            f"message should reference display_meta context: {msg!r}",
        )


class EvaluateRejectsPolicyTests(unittest.TestCase):
    """`sdk.evaluate(...)` rejects `policy=` (§6 I4.5 + I5.4 R5 combined check).

    `evaluate` has never accepted a projection/display policy and continues
    not to. Test discriminates on message content.
    """

    def test_evaluate_rejects_policy_kwarg(self) -> None:
        from kernel.sdk import ReadPolicy

        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.evaluate(object(), policy=ReadPolicy())
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("evaluate", msg)


# ---------------------------------------------------------------------------
# T-NEW-4 — `view=` removal redirect guards (§6 I5.1–I5.5)
# ---------------------------------------------------------------------------


class FindViewRedirectTests(unittest.TestCase):
    """R3: `find(view=...)` raises with redirect to `policy=` (§6 I5.2).

    All assertions require BOTH `view` and `policy` substrings in the
    lowercase message, to discriminate the new redirect from old-behavior
    errors like `view must be ViewSpec, view name string, or None`.
    """

    def test_find_view_with_string_raises_with_redirect(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, view="preferred")  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_find_view_none_raises_with_redirect(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, view=None)  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_find_view_arbitrary_object_raises_with_redirect(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.read.find(User, view=object())  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)


class RunViewTombstoneTests(unittest.TestCase):
    """R4 tombstone-sentinel: `run(view=anything)` raises (§6 I5.3 + I5.5).

    The `run(view=None)` test is the **discriminating gate** per §6 I5.5:
    any implementation that silently accepts `view=None` violates I5.3.
    Pre-migration `run(view=None)` returns normally because `view: ... = None`
    is the default, so this test is red until the tombstone sentinel ships.
    """

    def test_run_view_with_string_raises_with_redirect(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), view="preferred")  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_run_view_none_raises_tombstone_discriminating_gate(self) -> None:
        """Discriminating gate: pre-migration accepts `view=None` silently
        (it is the named-kwarg default), so this test fails red until
        the tombstone sentinel rejects any explicit `view=` pass.
        """
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), view=None)  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_run_view_arbitrary_object_raises_with_redirect(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.run(object(), view=object())  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("policy", msg)

    def test_run_without_view_or_policy_does_not_hit_tombstone(self) -> None:
        """Regression: tombstone must not fire when `view` is omitted.

        The call itself may raise for unrelated reasons (e.g. `object()` is
        not a valid rule), but the error must NOT carry the view→policy
        redirect signature.
        """
        sdk, _ = _seed_store()
        try:
            sdk.run(object())
        except Exception as exc:
            msg = str(exc).lower()
            self.assertFalse(
                "view" in msg and "policy" in msg,
                f"run() without view= still hit tombstone redirect: {msg!r}",
            )


class EvaluateViewAndPolicyRejectionTests(unittest.TestCase):
    """R5 combined rejection (§6 I5.4): `evaluate(view=...)` and
    `evaluate(policy=...)` both raise via the combined-key guard.
    """

    def test_evaluate_view_raises(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.evaluate(object(), view="preferred")  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("view", msg)
        self.assertIn("evaluate", msg)

    def test_evaluate_policy_raises(self) -> None:
        sdk, _ = _seed_store()
        with self.assertRaises(SDKStoreError) as exc:
            sdk.evaluate(object(), policy=object())  # type: ignore[call-arg]
        msg = str(exc.exception).lower()
        self.assertIn("policy", msg)
        self.assertIn("evaluate", msg)


if __name__ == "__main__":
    unittest.main()
