"""Red + guard baseline for Track 3-post PyReason branch bounds."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import kernel.application  # noqa: F401
from kernel.adapters.pyreason.rule_ext import PyReasonRuleExt, resolve_pyreason_engine_ext
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.adapters.pyreason.where_compile import compile_where_ir_to_pyreason
from kernel.core.evidence.write_protocol import set_field
from kernel.core.semantics import SemanticsProfile
from kernel.core.store.types import EngineExtBase
from kernel.sdk import Branch, Inference, Pred, SDKStore, vars as sdk_vars
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStoreError, _lower_public_semantics


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    risk_score: float = Field(cardinality="single")
    tag_hint: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


@dataclass(frozen=True)
class MockPyReasonRuleExt(EngineExtBase):
    timestep_delay: int = 0
    body_predicate_bounds: dict[str, tuple[float, float] | list[float]] = field(default_factory=dict)
    head_bound: tuple[float, float] | list[float] | None = None
    branch_head_bounds: dict[int, tuple[float, float] | list[float]] = field(default_factory=dict)


def _schema_ir() -> dict[str, Any]:
    return SDKStore([User]).schema_ir


def _make_sdk() -> SDKStore:
    sdk = SDKStore([User])
    alice_ref = sdk.ref(User, user_id="Alice")
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test", "confidence": 1.0},
    )
    set_field(
        sdk.ledger,
        pred_id="user:risk_score",
        e_ref=alice_ref,
        rest_terms=[("float64", 0.7)],
        meta={"source": "test", "confidence": 1.0},
    )
    set_field(
        sdk.ledger,
        pred_id="user:tag_hint",
        e_ref=alice_ref,
        rest_terms=[("string", "trial")],
        meta={"source": "test", "confidence": 1.0},
    )
    return sdk


def _two_branch_derivation() -> Inference:
    with sdk_vars("u", "name", "risk") as (u, name, risk):
        return Inference(
            id="drv.track3post.pyreason_branch_bounds",
            version="v1",
            where=[
                Branch([Pred("user:name", u, name)], id="sensor_path"),
                Branch([Pred("user:risk_score", u, risk)]),
            ],
            target="user:popular",
            head_vars=[u],
        )


def _single_branch_derivation() -> Inference:
    with sdk_vars("u", "name") as (u, name):
        return Inference(
            id="drv.track3post.pyreason_single",
            version="v1",
            where=[Branch([Pred("user:name", u, name)])],
            target="user:popular",
            head_vars=[u],
        )


def _pyreason_semantics(**kwargs: Any) -> Any:
    from kernel.sdk import PyReasonSemantics

    return PyReasonSemantics(**kwargs)


def _profile_with_branch_entries(entries: list[dict[str, object]]) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.track3post.pyreason",
        engine="pyreason",
        rule_projection={"pyreason": entries},
    )


def _where_two_branches() -> list[list[tuple[str, str, list[str]]]]:
    return [
        [("pred", "user:name", ["$u", "$name"])],
        [("pred", "user:risk_score", ["$u", "$risk"])],
    ]


def _mock_pyreason_empty(session, *, rules=None, rule_defs=None, facts=None, fact_defs=None, config=None):
    del rule_defs
    del facts
    del fact_defs
    return PyReasonRunResult(
        interpretation=None,
        trace=None,
        trace_dict={"engine": "pyreason", "rules": rules or []},
        derived_session=PyReasonSession(session._schema_ir),
        config=config or PyReasonRunConfig(),
        elapsed_seconds=0.01,
    )


class PublicPyReasonBranchBoundsTests(unittest.TestCase):
    def test_pyreason_semantics_accepts_branch_bounds_and_empty_noop(self) -> None:
        configured = _pyreason_semantics(branch_bounds={"sensor_path": [0.8, 1.0]})
        empty = _pyreason_semantics(branch_bounds={})

        self.assertEqual(configured.branch_bounds["sensor_path"], (0.8, 1.0))
        self.assertEqual(empty.branch_bounds, {})

    def test_lowering_resolves_explicit_and_fallback_branch_ids(self) -> None:
        semantics = _pyreason_semantics(
            head_bound=[0.1, 0.9],
            branch_bounds={"sensor_path": [0.8, 1.0], "b1": [0.2, 0.8]},
        )

        profile = _lower_public_semantics(semantics, derivation=_two_branch_derivation())

        self.assertEqual(
            profile.rule_projection["pyreason"],
            [
                {"target": "head:0", "kind": "interval", "value": [0.1, 0.9]},
                {"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]},
                {"target": "branch:1", "kind": "interval", "value": [0.2, 0.8]},
            ],
        )

    def test_unknown_branch_id_rejects_with_anchor(self) -> None:
        semantics = _pyreason_semantics(branch_bounds={"missing_path": [0.8, 1.0]})

        with self.assertRaises(SDKStoreError) as ctx:
            _lower_public_semantics(semantics, derivation=_two_branch_derivation())

        self.assertIn("branch_bounds contains unknown branch id 'missing_path'", str(ctx.exception))

    def test_wrapper_lowered_profile_matches_direct_profile_shape(self) -> None:
        semantics = _pyreason_semantics(branch_bounds={"sensor_path": [0.8, 1.0]})

        lowered = _lower_public_semantics(semantics, derivation=_two_branch_derivation())
        direct = _profile_with_branch_entries(
            [{"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]}]
        )

        self.assertEqual(lowered.engine, direct.engine)
        self.assertEqual(lowered.rule_projection, direct.rule_projection)

    def test_inspect_semantics_wrapper_includes_lowered_branch_targets(self) -> None:
        sdk = _make_sdk()
        semantics = _pyreason_semantics(branch_bounds={"sensor_path": [0.8, 1.0]})

        inspected = sdk.eval.inspect_semantics(semantics)

        self.assertEqual(inspected["semantics_type"], "PyReasonSemantics")
        self.assertIn(
            {"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]},
            inspected["lowered_profile"]["rule_projection"]["pyreason"],
        )

    def test_single_branch_fallback_b0_is_accepted(self) -> None:
        semantics = _pyreason_semantics(branch_bounds={"b0": [0.6, 0.9]})

        profile = _lower_public_semantics(semantics, derivation=_single_branch_derivation())

        self.assertEqual(
            profile.rule_projection["pyreason"],
            [{"target": "branch:0", "kind": "interval", "value": [0.6, 0.9]}],
        )


class PyReasonBranchBoundsProfileTests(unittest.TestCase):
    def test_direct_profile_branch_target_materializes_branch_head_bounds(self) -> None:
        profile = _profile_with_branch_entries(
            [{"target": "branch:1", "kind": "interval", "value": [0.2, 0.8]}]
        )

        resolved = resolve_pyreason_engine_ext(
            where=_where_two_branches(),
            schema_ir=_schema_ir(),
            engine_ext=None,
            semantics_profile=profile,
        )

        self.assertIsInstance(resolved, PyReasonRuleExt)
        self.assertEqual(resolved.branch_head_bounds[1], (0.2, 0.8))

    def test_direct_profile_branch_target_out_of_range_rejects_anchor(self) -> None:
        profile = _profile_with_branch_entries(
            [{"target": "branch:9", "kind": "interval", "value": [0.2, 0.8]}]
        )

        with self.assertRaises(ValueError) as ctx:
            resolve_pyreason_engine_ext(
                where=_where_two_branches(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=profile,
            )

        self.assertIn("rule_projection.pyreason[0] branch index out of range", str(ctx.exception))

    def test_profile_branch_bound_and_global_head_bound_coexist(self) -> None:
        profile = _profile_with_branch_entries(
            [
                {"target": "head:0", "kind": "interval", "value": [0.1, 0.9]},
                {"target": "branch:1", "kind": "interval", "value": [0.2, 0.8]},
            ]
        )

        resolved = resolve_pyreason_engine_ext(
            where=_where_two_branches(),
            schema_ir=_schema_ir(),
            engine_ext=None,
            semantics_profile=profile,
        )

        self.assertEqual(tuple(resolved.head_bound or ()), (0.1, 0.9))
        self.assertEqual(resolved.branch_head_bounds[1], (0.2, 0.8))


class PyReasonBranchBoundsCarrierTests(unittest.TestCase):
    def test_pyreason_rule_ext_accepts_branch_head_bounds(self) -> None:
        ext = PyReasonRuleExt(branch_head_bounds={0: (0.8, 1.0)})

        self.assertEqual(ext.branch_head_bounds[0], (0.8, 1.0))

    def test_pyreason_rule_ext_rejects_invalid_branch_head_bounds(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            PyReasonRuleExt(branch_head_bounds={-1: (0.8, 1.0)})

        self.assertIn("branch_head_bounds keys must be non-negative integers", str(ctx.exception))


class PyReasonBranchBoundsCompileTests(unittest.TestCase):
    def test_branch_head_bounds_compile_to_per_branch_head_annotations(self) -> None:
        ext = MockPyReasonRuleExt(branch_head_bounds={0: (0.8, 1.0), 1: (0.2, 0.8)})

        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$u"],
            where=_where_two_branches(),
            schema_ir=_schema_ir(),
            engine_ext=ext,
        )

        self.assertEqual(
            rules,
            [
                ("popular(u) : [0.8, 1.0] <-0 name(u)", "derived_popular_b0"),
                ("popular(u) : [0.2, 0.8] <-0 risk_score(u)", "derived_popular_b1"),
            ],
        )

    def test_branch_head_bounds_override_global_head_bound_per_branch(self) -> None:
        ext = MockPyReasonRuleExt(
            head_bound=(0.1, 0.9),
            branch_head_bounds={1: (0.2, 0.8)},
        )

        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$u"],
            where=_where_two_branches(),
            schema_ir=_schema_ir(),
            engine_ext=ext,
        )

        self.assertEqual(
            rules,
            [
                ("popular(u) : [0.1, 0.9] <-0 name(u)", "derived_popular_b0"),
                ("popular(u) : [0.2, 0.8] <-0 risk_score(u)", "derived_popular_b1"),
            ],
        )

    def test_single_branch_branch_head_bound_uses_b0_target(self) -> None:
        ext = MockPyReasonRuleExt(branch_head_bounds={0: (0.6, 0.9)})

        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$u"],
            where=[[("pred", "user:name", ["$u", "$name"])]],
            schema_ir=_schema_ir(),
            engine_ext=ext,
        )

        self.assertEqual(rules, [("popular(u) : [0.6, 0.9] <-0 name(u)", "derived_popular")])

    def test_existing_global_head_bound_without_branch_bounds_still_works(self) -> None:
        ext = MockPyReasonRuleExt(head_bound=(0.7, 0.9))

        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$u"],
            where=[("pred", "user:name", ["$u", "$name"])],
            schema_ir=_schema_ir(),
            engine_ext=ext,
        )

        self.assertEqual(rules, [("popular(u) : [0.7, 0.9] <-0 name(u)", "derived_popular")])


class PyReasonBranchBoundsIntegrationTests(unittest.TestCase):
    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_pyreason_empty)
    def test_evaluate_with_branch_bounds_drives_compiled_rules(self, mock_run: Any) -> None:
        sdk = _make_sdk()
        semantics = _pyreason_semantics(branch_bounds={"sensor_path": [0.8, 1.0], "b1": [0.2, 0.8]})

        sdk.eval.evaluate(_two_branch_derivation(), semantics=semantics)

        self.assertEqual(
            mock_run.call_args.kwargs["rules"],
            [
                ("popular(u) : [0.8, 1.0] <-0 name(u)", "derived_popular_b0"),
                ("popular(u) : [0.2, 0.8] <-0 risk_score(u)", "derived_popular_b1"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
