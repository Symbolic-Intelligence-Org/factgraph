"""Public read-only fg.eval.evaluate_candidates: raw CandidateSets, guard-rails, accept loop.

Self-contained: a tiny User schema, an Inference whose body matches seeded data, and
a regression anchor where the emit target is NOT a schema field. evaluate() behaviour
is covered by the existing suite; here we pin the new candidate seam meander-ilp builds on.
"""

from __future__ import annotations

import unittest

from factgraph._sdk_errors import FrozenSnapshotError, SDKStoreError
from factgraph.application.derivation_runtime import accept_derivation_candidate_set
from factgraph.application.protocol import DerivationAcceptRequest
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom as CorePredAtom, Var as CoreVar
from factgraph.sdk import (
    Case,
    EmitSpec,
    Inference,
    Pred,
    Rule,
    SDKStore,
    vars as sdk_vars,
)
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag_hint: str = Field()
    tag: str = Field()


def _make_sdk() -> SDKStore:
    sdk = SDKStore([User])
    alice_ref = sdk.entities.ref(User, user_id="Alice")
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test"},
    )
    set_field(
        sdk.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test"},
    )
    return sdk


def _inference(
    *,
    target: str = "user:tag",
    seed: str = "user:tag_seed",
    inf_id: str = "inf.eval_candidates.tag",
):
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred(seed, u, tag)], id="seed_path")],
            emits=EmitSpec(target, [u, tag]),
        )


def _rule() -> Rule:
    u = CoreVar("$u")
    tag = CoreVar("$tag")
    return Rule(
        id="eval_candidates_rule",
        version="v1",
        when=(CorePredAtom("user:tag_seed", [u, tag]),),
        ports={"u": u, "tag": tag},
    )


class EvaluateCandidatesTests(unittest.TestCase):
    def test_returns_list_of_candidate_sets(self) -> None:
        sdk = _make_sdk()
        candidates = sdk.eval.evaluate_candidates(_inference(), engine="native")

        self.assertIsInstance(candidates, list)
        self.assertTrue(candidates)
        for cs in candidates:
            self.assertIsInstance(cs, CandidateSet)
        self.assertTrue(any(cs.target == "user:tag" for cs in candidates))

    def test_no_match_returns_empty_list(self) -> None:
        sdk = _make_sdk()
        # tag_hint ist nicht geseedet -> kein Treffer, leere Liste (kein Fehler).
        candidates = sdk.eval.evaluate_candidates(
            _inference(seed="user:tag_hint", inf_id="inf.eval_candidates.nomatch"),
            engine="native",
        )
        self.assertEqual(candidates, [])

    def test_target_without_schema_field_still_yields_candidates(self) -> None:
        # Regressionsanker: das Ziel-Prädikat ist KEIN Schema-Feld, trotzdem Kandidaten.
        sdk = _make_sdk()
        candidates = sdk.eval.evaluate_candidates(
            _inference(
                target="user:grandparent", inf_id="inf.eval_candidates.nonfield"
            ),
            engine="native",
        )
        self.assertTrue(candidates)
        self.assertTrue(any(cs.target == "user:grandparent" for cs in candidates))

    def test_structured_dict_input(self) -> None:
        # Dict-Input-Zweig von evaluate_candidates absichern.
        sdk = _make_sdk()
        payload = _inference().to_authoring_payload()
        self.assertIn("derivation_id", payload)

        candidates = sdk.eval.evaluate_candidates(payload, engine="native")
        self.assertIsInstance(candidates, list)
        self.assertTrue(candidates)
        for cs in candidates:
            self.assertIsInstance(cs, CandidateSet)

    def test_read_only_no_claim_before_accept(self) -> None:
        sdk = _make_sdk()
        before = sdk.ledger.find_claims(pred_id="user:tag")
        sdk.eval.evaluate_candidates(_inference(), engine="native")
        after = sdk.ledger.find_claims(pred_id="user:tag")
        self.assertEqual(before, after)

    def test_accept_loop_writes_claim_with_provenance(self) -> None:
        sdk = _make_sdk()
        candidates = sdk.eval.evaluate_candidates(_inference(), engine="native")
        self.assertTrue(candidates)

        written_ids: list[str] = []
        for cs in candidates:
            result = accept_derivation_candidate_set(
                cs,
                DerivationAcceptRequest(approved_by="tester"),
                store=sdk.store,
                derived_rule_id="inf.eval_candidates.tag",
                derived_rule_version="v1",
            )
            written_ids.extend(a["asrt_id"] for a in result.written_assertions)

        self.assertTrue(written_ids)
        asrt_id = written_ids[0]
        self.assertIsNotNone(sdk.ledger.get_claim(asrt_id))

        meta = {m.key: m.value for m in sdk.ledger.find_meta(asrt_id=asrt_id)}
        self.assertEqual(meta.get("source"), "derivation.accept")
        self.assertEqual(meta.get("derived_rule_id"), "inf.eval_candidates.tag")

    # --- Guard-Rails (identisch zu evaluate) ---

    def test_rejects_string_dsl(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(SDKStoreError):
            sdk.eval.evaluate_candidates("some dsl string", engine="native")

    def test_rejects_application_rule(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(SDKStoreError):
            sdk.eval.evaluate_candidates(_rule())

    def test_rejects_mode_kwarg(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(SDKStoreError):
            sdk.eval.evaluate_candidates(_inference(), mode="native")

    def test_rejects_registry_kwarg(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(SDKStoreError):
            sdk.eval.evaluate_candidates(_inference(), registry=object())

    def test_rejects_semantics_profile_kwarg(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(SDKStoreError):
            sdk.eval.evaluate_candidates(_inference(), semantics_profile=object())


class EvalNamespaceStaysReadOnlyTests(unittest.TestCase):
    def test_eval_namespace_setattr_still_frozen(self) -> None:
        sdk = _make_sdk()
        with self.assertRaises(FrozenSnapshotError):
            sdk.eval.foo = "bar"  # type: ignore[attr-defined]

    def test_eval_exposes_candidates_but_no_accept(self) -> None:
        sdk = _make_sdk()
        self.assertTrue(hasattr(sdk.eval, "evaluate_candidates"))
        self.assertFalse(hasattr(sdk.eval, "accept"))
