"""fg.audit.diff_proof_frames contract tests.

Phase 1 of G5 (per archived blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g5-round-events-proofframe-diff.md`` §8)
ships full §5.1 / §5.2 / §5.3 / §5.4 / §5.7 / §5.8 contract coverage
for ``fg.audit.diff_proof_frames(...)``. Mirrors the G2 ProofFrame
Recheck per-method contract test structure with diff-specific
input-rejection tests for raw ``tuple[RoundEvent, ...]`` × 2 and
``tuple[WarningDTO, ...]``.
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

# Import factgraph.sdk first to warm the factgraph.application + factgraph.audit
# import chain (otherwise importing factgraph.audit.proof_frame_diff cold
# triggers a circular import via
# factgraph.application.capability_helpers.round_events ← factgraph.audit.round_events).
from factgraph.sdk import Entity, Field, Identity, SDKStore, SDKStoreError  # noqa: I001
from factgraph.audit.proof_frame_diff import ProofFrameDiff, ProofFrameDiffError
from factgraph.audit.round_events import (
    ROUND_EVENT_SCHEMA_VERSION,
    RoundEvent,
    make_round_finalized_event,
    make_round_started_event,
)


class _Person(Entity):
    name: str = Identity()
    age: int = Field()


def _build_sdk() -> SDKStore:
    return SDKStore([_Person])


def _empty_round(round_id: str) -> tuple[RoundEvent, ...]:
    """Return a minimal valid round (lifecycle markers only, no
    proof_frame_result events). Diffing two such rounds yields a
    ``ProofFrameDiff`` with zero ``frame_deltas``."""
    started = make_round_started_event(round_id, event_ts=100)
    finalized = make_round_finalized_event(
        round_id, sequence=1, events=(started,), event_ts=200
    )
    return (started, finalized)


def _proof_frame_event(
    round_id: str,
    *,
    sequence: int,
    event_ts: int,
    support_digest: str,
    binding: tuple[tuple[str, object], ...],
    status: str,
    atom_verdicts: list[dict[str, object]],
) -> RoundEvent:
    return RoundEvent(
        round_id=round_id,
        sequence=sequence,
        event_ts=event_ts,
        kind="proof_frame_result",
        schema_version=ROUND_EVENT_SCHEMA_VERSION,
        payload={
            "request": {"support_digest": support_digest},
            "result": {
                "binding_items": [list(item) for item in binding],
                "status": status,
                "atom_verdicts": atom_verdicts,
            },
        },
    )


def _round_with_one_frame(
    round_id: str,
    *,
    support_digest: str,
    status: str,
    atom_verdicts: list[dict[str, object]],
) -> tuple[RoundEvent, ...]:
    started = make_round_started_event(round_id, event_ts=100)
    pf = _proof_frame_event(
        round_id,
        sequence=1,
        event_ts=110,
        support_digest=support_digest,
        binding=(("$p", "alice"),),
        status=status,
        atom_verdicts=atom_verdicts,
    )
    finalized = make_round_finalized_event(
        round_id, sequence=2, events=(started, pf), event_ts=200
    )
    return (started, pf, finalized)


class SDKDiffProofFramesContractTests(unittest.TestCase):
    def test_happy_path_returns_raw_proof_frame_diff(self) -> None:
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        result = sdk.audit.diff_proof_frames(
            "round-a", "round-b", round_a, round_b
        )

        self.assertIsInstance(result, ProofFrameDiff)
        self.assertEqual(result.round_a_id, "round-a")
        self.assertEqual(result.round_b_id, "round-b")
        self.assertEqual(result.frame_deltas, ())

    def test_non_string_round_a_id_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                123,  # type: ignore[arg-type]
                "round-b",
                _empty_round("round-a"),
                _empty_round("round-b"),
            )

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.round_a_id")
        self.assertIn("non-empty str", str(ctx.exception))

    def test_empty_round_a_id_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "",
                "round-b",
                _empty_round("round-a"),
                _empty_round("round-b"),
            )

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.round_a_id")

    def test_non_string_round_b_id_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                None,  # type: ignore[arg-type]
                _empty_round("round-a"),
                _empty_round("round-b"),
            )

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.round_b_id")

    def test_non_tuple_round_a_events_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                list(_empty_round("round-a")),  # type: ignore[arg-type]
                _empty_round("round-b"),
            )

        self.assertEqual(
            ctx.exception.path, "$.diff_proof_frames.round_a_events"
        )
        self.assertIn("tuple[RoundEvent", str(ctx.exception))

    def test_non_round_event_element_in_round_a_events_rejected(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                ("not-a-round-event",),  # type: ignore[arg-type]
                _empty_round("round-b"),
            )

        self.assertEqual(
            ctx.exception.path, "$.diff_proof_frames.round_a_events"
        )

    def test_non_tuple_round_b_events_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                _empty_round("round-a"),
                "not-a-tuple",  # type: ignore[arg-type]
            )

        self.assertEqual(
            ctx.exception.path, "$.diff_proof_frames.round_b_events"
        )

    def test_non_round_event_element_in_round_b_events_rejected(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                _empty_round("round-a"),
                (42,),  # type: ignore[arg-type]
            )

        self.assertEqual(
            ctx.exception.path, "$.diff_proof_frames.round_b_events"
        )

    def test_non_tuple_warnings_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                _empty_round("round-a"),
                _empty_round("round-b"),
                warnings=[],  # type: ignore[arg-type]
            )

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.warnings")
        self.assertIn("tuple[WarningDTO", str(ctx.exception))

    def test_non_warning_dto_element_in_warnings_rejected(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.audit.diff_proof_frames(
                "round-a",
                "round-b",
                _empty_round("round-a"),
                _empty_round("round-b"),
                warnings=("not-a-warning",),  # type: ignore[arg-type]
            )

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.warnings")

    def test_non_bool_include_unchanged_rejected_at_sdk_surface(self) -> None:
        """Pre-publish-Blocker regression: ``include_unchanged`` is
        typed/documented as ``bool`` but Python's annotations are not
        runtime-enforced. Without an explicit ``isinstance(.., bool)``
        check at the SDK boundary, arbitrary truthy/falsy values would
        be silently accepted and propagated to the runtime — creating
        unintended SDK surface (`include_unchanged="yes"` etc.). The
        SDK shell now validates and remaps to
        ``$.diff_proof_frames.include_unchanged``.
        """
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        for bad_value in ("yes", 1, 0, "", None, [True]):
            with self.subTest(value=bad_value):
                with self.assertRaises(SDKStoreError) as ctx:
                    sdk.audit.diff_proof_frames(
                        "round-a",
                        "round-b",
                        round_a,
                        round_b,
                        include_unchanged=bad_value,  # type: ignore[arg-type]
                    )
                self.assertEqual(
                    ctx.exception.path,
                    "$.diff_proof_frames.include_unchanged",
                )
                self.assertIn("must be bool", str(ctx.exception))

    def test_bool_include_unchanged_accepted(self) -> None:
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        for good_value in (True, False):
            with self.subTest(value=good_value):
                result = sdk.audit.diff_proof_frames(
                    "round-a",
                    "round-b",
                    round_a,
                    round_b,
                    include_unchanged=good_value,
                )
                self.assertIsInstance(result, ProofFrameDiff)

    def test_proof_frame_diff_error_remaps_to_request_path(self) -> None:
        """``ProofFrameDiffError`` from helper-internal validation
        (malformed event payloads, duplicate frame identity, etc.)
        remaps to ``$.diff_proof_frames.request`` per §5.8."""
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        with patch(
            "factgraph.sdk.shells.proof_frame_diff.build_proof_frame_diff",
            side_effect=ProofFrameDiffError("simulated payload error"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.audit.diff_proof_frames("round-a", "round-b", round_a, round_b)

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames.request")
        self.assertIsInstance(ctx.exception.__cause__, ProofFrameDiffError)
        self.assertIn("simulated payload error", str(ctx.exception))

    def test_unexpected_runtime_exception_remaps_to_base_path(self) -> None:
        """§5.8 base-path remap: defensive `Exception` wrap for
        forward-compat unexpected raise from `build_proof_frame_diff`."""
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        with patch(
            "factgraph.sdk.shells.proof_frame_diff.build_proof_frame_diff",
            side_effect=RuntimeError("simulated runtime failure"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.audit.diff_proof_frames("round-a", "round-b", round_a, round_b)

        self.assertEqual(ctx.exception.path, "$.diff_proof_frames")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_proof_frame_diff_dtos_not_exported_from_factgraph_sdk_all(self) -> None:
        import factgraph.sdk as sdk_pkg

        for name in (
            "ProofFrameDiff",
            "FrameDelta",
            "AtomDelta",
            "FrameIdentity",
            "FrameStatusChange",
            "EventReference",
            "RoundEvent",
            "RoundSummary",
            "diff_proof_frames",
            "sdk_diff_proof_frames",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, sdk_pkg.__all__)
                self.assertFalse(hasattr(sdk_pkg, name))

    def test_diff_with_real_proof_frame_events_produces_frame_deltas(self) -> None:
        """End-to-end happy path with real proof_frame_result events
        producing non-empty ``frame_deltas``."""
        sdk = _build_sdk()
        round_a = _round_with_one_frame(
            "round-a",
            support_digest="digest-1",
            status="still_valid",
            atom_verdicts=[{"atom_key": "atom-1", "verdict": "still_valid"}],
        )
        round_b = _round_with_one_frame(
            "round-b",
            support_digest="digest-1",
            status="invalidated",
            atom_verdicts=[{"atom_key": "atom-1", "verdict": "invalidated"}],
        )

        result = sdk.audit.diff_proof_frames(
            "round-a", "round-b", round_a, round_b
        )

        self.assertIsInstance(result, ProofFrameDiff)
        self.assertEqual(len(result.frame_deltas), 1)
        delta = result.frame_deltas[0]
        self.assertEqual(delta.frame_status_change.before, "still_valid")
        self.assertEqual(delta.frame_status_change.after, "invalidated")

    def test_sibling_diff_proof_frames_does_not_call_other_sdk_shells_at_runtime(
        self,
    ) -> None:
        """§5.8 Sibling discipline at 9-shell scope: the new G5 shell
        MUST NOT call any of the 8 prior sister SDK shells at runtime."""
        sdk = _build_sdk()
        round_a = _empty_round("round-a")
        round_b = _empty_round("round-b")

        with patch("factgraph.sdk.shells.check.sdk_check") as mock_check, patch(
            "factgraph.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "factgraph.sdk.shells.why_not.sdk_why_not"
        ) as mock_why_not, patch(
            "factgraph.sdk.shells.fact_overlay.sdk_fact_overlay_check"
        ) as mock_fact_overlay, patch(
            "factgraph.sdk.shells.proof_frame.sdk_proof_frame_recheck"
        ) as mock_proof_frame, patch(
            "factgraph.sdk.shells.rule_disable.sdk_rule_disable"
        ) as mock_rule_disable, patch(
            "factgraph.sdk.shells.rule_literal_replace.sdk_rule_literal_replace"
        ) as mock_rule_literal_replace, patch(
            "factgraph.sdk.shells.rule_add_condition.sdk_rule_add_condition"
        ) as mock_rule_add_condition:
            sdk.audit.diff_proof_frames("round-a", "round-b", round_a, round_b)

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()
        mock_why_not.assert_not_called()
        mock_fact_overlay.assert_not_called()
        mock_proof_frame.assert_not_called()
        mock_rule_disable.assert_not_called()
        mock_rule_literal_replace.assert_not_called()
        mock_rule_add_condition.assert_not_called()

    def test_sibling_diff_proof_frames_module_does_not_import_sibling_sdk_shells(
        self,
    ) -> None:
        """§5.8 Sibling static check: factgraph.sdk.shells.proof_frame_diff
        source has no sibling SDK shell references (all 8 prior
        sisters)."""
        import factgraph.sdk.shells.proof_frame_diff as proof_frame_diff_module

        source = inspect.getsource(proof_frame_diff_module)
        for forbidden in (
            "from .check",
            "from .diagnose",
            "from .why_not",
            "from .fact_overlay",
            "from .proof_frame",
            "from .rule_disable",
            "from .rule_literal_replace",
            "from .rule_add_condition",
            "from factgraph.sdk.shells.check",
            "from factgraph.sdk.shells.diagnose",
            "from factgraph.sdk.shells.why_not",
            "from factgraph.sdk.shells.fact_overlay",
            "from factgraph.sdk.shells.proof_frame",
            "from factgraph.sdk.shells.rule_disable",
            "from factgraph.sdk.shells.rule_literal_replace",
            "from factgraph.sdk.shells.rule_add_condition",
            "sdk_check(",
            "sdk_diagnose(",
            "sdk_why_not(",
            "sdk_fact_overlay_check(",
            "sdk_proof_frame_recheck(",
            "sdk_rule_disable(",
            "sdk_rule_literal_replace(",
            "sdk_rule_add_condition(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
