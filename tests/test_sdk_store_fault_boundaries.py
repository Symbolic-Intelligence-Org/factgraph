"""Fault-injection characterization for the broad boundaries in factgraph.sdk.store.

Two families of guarded sites live in this module:

* evidence-graph builders - engine explainer / provenance-decode adapters are
  external boundaries; any failure there degrades the *explanation* to the
  labelled minimal evidence graph (or to the structural probe), and never to a
  changed row outcome.
* entity-class introspection - ``sdk_entity_spec()`` is user/application code, so
  a class with an unusable spec simply makes no supersede/active-binding claim.

Every test injects a custom exception subclass at the site, pins the exact typed
outcome, asserts the failure is not reported as an engine success, and asserts
KeyboardInterrupt is not swallowed.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk import store as store_mod
from factgraph.sdk.errors import SDKStoreError


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


class _BoundaryFault(Exception):
    """Custom, non-SDK failure raised from the injected adapter boundary."""


_MINIMAL = object()
_ARTIFACT_GRAPH = object()
_PROBE_GRAPH = object()


def _raises(exc: BaseException):
    def _fn(*args, **kwargs):
        raise exc

    return _fn


def _row():
    return SimpleNamespace(row_id="row-1", bindings={}, certainty=None, kind=None)


def _result(engine: str):
    return SimpleNamespace(
        result_id="res-1",
        engine=engine,
        head=SimpleNamespace(id="head-1", render_repr=lambda bindings: ""),
    )


def _plan():
    return SimpleNamespace(head=SimpleNamespace(id="head-1"))


def _sdk() -> SDKStore:
    return SDKStore([Country, User])


class SouffleRowGraphBoundaryTests(unittest.TestCase):
    def _builder(self, sdk: SDKStore, artifacts):
        return sdk._souffle_row_graph_builder(
            artifacts,
            lowering_plan=_plan(),
            rules_by_id={"head-1": _plan().head},
        )

    def test_reach_explain_failure_falls_through_to_minimal_graph(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(
                store_mod, "souffle_reach_explain_to_evidence_graph", _raises(_BoundaryFault("souffle explain"))
            ),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = self._builder(sdk, {})(_row(), _result("souffle"), {})

        # Typed outcome: the labelled minimal fallback graph, never the explainer's
        # exception and never a silently "successful" engine graph.
        self.assertIs(observed, _MINIMAL)

    def test_reach_explain_failure_still_uses_the_witness_artifact_when_present(self) -> None:
        sdk = _sdk()
        artifact = SimpleNamespace(kind=store_mod.SOUFFLE_WITNESS_KIND)
        with (
            mock.patch.object(
                store_mod, "souffle_reach_explain_to_evidence_graph", _raises(_BoundaryFault("souffle explain"))
            ),
            mock.patch.object(
                store_mod, "_souffle_support_artifact_to_evidence_graph", lambda *a, **k: _ARTIFACT_GRAPH
            ),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = self._builder(sdk, {"row-1": artifact})(_row(), _result("souffle"), {})

        self.assertIs(observed, _ARTIFACT_GRAPH)

    def test_witness_artifact_decode_failure_falls_back_to_minimal_graph(self) -> None:
        sdk = _sdk()
        artifact = SimpleNamespace(kind=store_mod.SOUFFLE_WITNESS_KIND)
        with (
            mock.patch.object(
                store_mod, "souffle_reach_explain_to_evidence_graph", _raises(_BoundaryFault("souffle explain"))
            ),
            mock.patch.object(
                store_mod,
                "_souffle_support_artifact_to_evidence_graph",
                _raises(_BoundaryFault("artifact decode")),
            ),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = self._builder(sdk, {"row-1": artifact})(_row(), _result("souffle"), {})

        self.assertIs(observed, _MINIMAL)

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(store_mod, "souffle_reach_explain_to_evidence_graph", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._builder(sdk, {})(_row(), _result("souffle"), {})

        artifact = SimpleNamespace(kind=store_mod.SOUFFLE_WITNESS_KIND)
        with (
            mock.patch.object(
                store_mod, "souffle_reach_explain_to_evidence_graph", _raises(_BoundaryFault("souffle explain"))
            ),
            mock.patch.object(
                store_mod, "_souffle_support_artifact_to_evidence_graph", _raises(KeyboardInterrupt())
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._builder(sdk, {"row-1": artifact})(_row(), _result("souffle"), {})


class ProblogRowGraphBoundaryTests(unittest.TestCase):
    def _builder(self, sdk: SDKStore, envelopes):
        return sdk._problog_row_graph_builder(
            envelopes,
            lowering_plan=_plan(),
            rules_by_id={"head-1": _plan().head},
            semantics_profile=None,
        )

    def _envelope(self):
        return SimpleNamespace(
            engine="problog", payload_type="proof_trace", payload={}, candidate_id="cand-1"
        )

    def test_reach_explain_failure_falls_through_to_minimal_graph(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(
                store_mod, "problog_reach_explain_to_evidence_graph", _raises(_BoundaryFault("problog explain"))
            ),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = self._builder(sdk, {})(_row(), _result("problog"), {})

        self.assertIs(observed, _MINIMAL)

    def test_provenance_trace_decode_failure_falls_back_to_minimal_graph(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(
                store_mod, "problog_reach_explain_to_evidence_graph", _raises(_BoundaryFault("problog explain"))
            ),
            mock.patch.object(store_mod, "problog_trace_from_dict", _raises(_BoundaryFault("trace decode"))),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = self._builder(sdk, {"row-1": self._envelope()})(_row(), _result("problog"), {})

        self.assertIs(observed, _MINIMAL)

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(store_mod, "problog_reach_explain_to_evidence_graph", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._builder(sdk, {})(_row(), _result("problog"), {})

        with (
            mock.patch.object(
                store_mod, "problog_reach_explain_to_evidence_graph", _raises(_BoundaryFault("problog explain"))
            ),
            mock.patch.object(store_mod, "problog_trace_from_dict", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._builder(sdk, {"row-1": self._envelope()})(_row(), _result("problog"), {})


class PyreasonRowGraphBoundaryTests(unittest.TestCase):
    def _envelope(self):
        return SimpleNamespace(
            engine="pyreason", payload_type="event_log", payload={}, candidate_id="cand-1"
        )

    def test_provenance_trace_decode_failure_falls_back_to_minimal_graph(self) -> None:
        sdk = _sdk()
        builder = sdk._pyreason_row_graph_builder({"row-1": self._envelope()})
        with (
            mock.patch.object(store_mod, "pyreason_trace_from_dict", _raises(_BoundaryFault("trace decode"))),
            mock.patch.object(store_mod, "_build_minimal_row_evidence_graph", lambda *a, **k: _MINIMAL),
        ):
            observed = builder(_row(), _result("pyreason"), {})

        self.assertIs(observed, _MINIMAL)

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _sdk()
        builder = sdk._pyreason_row_graph_builder({"row-1": self._envelope()})
        with (
            mock.patch.object(store_mod, "pyreason_trace_from_dict", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            builder(_row(), _result("pyreason"), {})


class ClosedHeadFalseProbeBoundaryTests(unittest.TestCase):
    def _call(self, sdk: SDKStore, engine: str):
        return sdk._closed_head_false_evidence_graph(
            _plan(),
            {},
            result=_result(engine),
            checked_scope={"closed_head_digest": "digest-1"},
        )

    def test_souffle_explain_failure_falls_through_to_structural_probe(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(
                store_mod, "souffle_reach_explain_to_evidence_graph", _raises(_BoundaryFault("souffle explain"))
            ),
            mock.patch.object(
                SDKStore, "_probe_evidence_graph_for_lowering_plan", lambda self, *a, **k: _PROBE_GRAPH
            ),
        ):
            self.assertIs(self._call(sdk, "souffle"), _PROBE_GRAPH)

    def test_problog_explain_failure_falls_through_to_structural_probe(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(
                store_mod, "problog_reach_explain_to_evidence_graph", _raises(_BoundaryFault("problog explain"))
            ),
            mock.patch.object(
                SDKStore, "_probe_evidence_graph_for_lowering_plan", lambda self, *a, **k: _PROBE_GRAPH
            ),
        ):
            self.assertIs(self._call(sdk, "problog"), _PROBE_GRAPH)

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _sdk()
        with (
            mock.patch.object(store_mod, "souffle_reach_explain_to_evidence_graph", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._call(sdk, "souffle")
        with (
            mock.patch.object(store_mod, "problog_reach_explain_to_evidence_graph", _raises(KeyboardInterrupt())),
            self.assertRaises(KeyboardInterrupt),
        ):
            self._call(sdk, "problog")


class EntityClassIntrospectionBoundaryTests(unittest.TestCase):
    """src/factgraph/sdk/store.py: sdk_entity_spec() is application code."""

    def _broken_class(self, exc: BaseException) -> type:
        class BrokenEntityClass:
            @staticmethod
            def sdk_entity_spec():
                raise exc

        return BrokenEntityClass

    def test_unusable_spec_makes_no_supersede_claim(self) -> None:
        sdk = _sdk()
        broken = self._broken_class(_BoundaryFault("spec unavailable"))
        # Typed outcome: returns None (no supersede claim), does not raise.
        self.assertIsNone(sdk._raise_if_superseded_entity_class(broken))

    def test_supersede_guard_still_fires_for_a_usable_stale_class(self) -> None:
        sdk = _sdk()

        class StaleUser:
            @staticmethod
            def sdk_entity_spec():
                return {"entity_type": "User"}

        # The guard is not disabled by the broad boundary: a class with a usable
        # spec that is not the active binding still fails closed.
        with self.assertRaises(SDKStoreError):
            sdk._raise_if_superseded_entity_class(StaleUser)

    def test_unusable_spec_class_is_skipped_when_resolving_the_active_class(self) -> None:
        sdk = _sdk()
        broken = self._broken_class(_BoundaryFault("spec unavailable"))
        original = list(sdk._classes)
        sdk._classes = [broken, *original]
        try:
            # Typed outcome: the broken class is skipped, the real class still wins.
            self.assertIs(sdk._active_entity_class_for_type("User"), User)
            # An entity type nobody claims still resolves to None, not to the broken class.
            self.assertIsNone(sdk._active_entity_class_for_type("NoSuchType"))
        finally:
            sdk._classes = original

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        sdk = _sdk()
        broken = self._broken_class(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            sdk._raise_if_superseded_entity_class(broken)

        original = list(sdk._classes)
        sdk._classes = [broken, *original]
        try:
            with self.assertRaises(KeyboardInterrupt):
                sdk._active_entity_class_for_type("User")
        finally:
            sdk._classes = original


if __name__ == "__main__":
    unittest.main()
