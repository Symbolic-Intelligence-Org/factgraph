"""Actor/business provenance on accepted derived assertions (real ledger round-trip).

Proves the additive ``actor_meta`` channel: a caller (e.g. an authenticated write
boundary) can attach actor provenance to a derivation accept; it persists as ordinary
meta rows on the written derived assertion, never overwrites protocol/system meta, and
rejects the write-protocol-managed keys.
"""
from __future__ import annotations

import unittest

from factgraph.application.derivation_runtime import accept_derivation_candidate_set
from factgraph.application.protocol import DerivationAcceptRequest
from factgraph.core.derivation.accept import AcceptOptions, _build_base_write_meta
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import WriteProtocolError, set_field
from factgraph.sdk import (
    Case,
    EmitSpec,
    Inference,
    Pred,
    SDKStore,
    vars as sdk_vars,
)
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()
    tag: str = Field()


def _make_sdk() -> SDKStore:
    sdk = SDKStore([User])
    ref = sdk.entities.ref(User, user_id="Alice")
    set_field(sdk.ledger, pred_id="user:tag_seed", e_ref=ref, rest_terms=[("string", "vip")], meta={"source": "test"})
    return sdk


def _inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.actor_meta.tag",
            version="v1",
            when=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            emits=EmitSpec("user:tag", [u, tag]),
        )


_ACTOR_META = {
    "actor_id": "user-123",
    "tenant_id": "default",
    "request_id": "req-abc",
    "auth_identity_id": "ai-1",
    "auth_provider": "google",
    "auth_method": "oidc",
    "action": "rule.accept",
}


class DerivationActorMetaTests(unittest.TestCase):
    def test_actor_meta_lands_on_derived_assertion(self) -> None:
        sdk = _make_sdk()
        candidates = sdk.eval.evaluate_candidates(_inference(), engine="native")
        self.assertTrue(candidates)

        written_ids: list[str] = []
        for cs in candidates:
            result = accept_derivation_candidate_set(
                cs,
                DerivationAcceptRequest(approved_by="user-123", meta=dict(_ACTOR_META)),
                store=sdk.store,
                derived_rule_id="inf.actor_meta.tag",
                derived_rule_version="v1",
            )
            written_ids.extend(a["asrt_id"] for a in result.written_assertions)

        self.assertTrue(written_ids)
        meta = {m.key: m.value for m in sdk.ledger.find_meta(asrt_id=written_ids[0])}
        # Actor-Provenance ist da ...
        for key, value in _ACTOR_META.items():
            self.assertEqual(meta.get(key), value, key)
        # ... und die Protokoll-Provenance bleibt unversehrt.
        self.assertEqual(meta.get("source"), "derivation.accept")
        self.assertEqual(meta.get("derived_rule_id"), "inf.actor_meta.tag")
        self.assertEqual(meta.get("approved_by"), "user-123")

    def test_actor_meta_never_overwrites_protocol_meta(self) -> None:
        # actor_meta versucht, Protokoll-Schlüssel zu überschreiben -> wird ignoriert.
        candidate = CandidateSet(
            derivation_id="d1",
            derivation_version="1.0",
            run_id="run-1",
            target="user:tag",
            key_tuple_digest="sha256:" + ("0" * 64),
            tup_digest=None,
            payload={"terms": []},
            support_digest="sha256:" + ("0" * 64),
            support_kind="native",
            generated_at=0,
            state="proposed",
        )
        options = AcceptOptions(
            approved_by="real-actor",
            actor_meta={"source": "spoofed", "derived_rule_id": "spoofed", "actor_id": "user-9"},
        )
        write_meta = _build_base_write_meta(
            candidate_set=candidate,
            options=options,
            derived_rule_id="real.rule",
            derived_rule_version="v1",
            schema_digest_token=None,
            policy_digest_token=None,
            cand_key_digest="sha256:" + ("1" * 64),
        )
        self.assertEqual(write_meta["source"], "derivation.accept")  # nicht "spoofed"
        self.assertEqual(write_meta["derived_rule_id"], "real.rule")  # nicht "spoofed"
        self.assertEqual(write_meta["actor_id"], "user-9")  # echte Akteur-Provenance bleibt

    def test_actor_meta_does_not_break_idempotency(self) -> None:
        # Denselben Kandidaten zweimal akzeptieren, mit UNTERSCHIEDLICHER Akteur-
        # Provenance (anderer request_id): es darf trotzdem nur EINE Assertion
        # entstehen — Akteur-Meta ist Annotation, nie Teil der Claim-Identität.
        sdk = _make_sdk()
        for request_id in ("req-1", "req-2"):
            for cs in sdk.eval.evaluate_candidates(_inference(), engine="native"):
                accept_derivation_candidate_set(
                    cs,
                    DerivationAcceptRequest(
                        approved_by="user-123",
                        meta={"actor_id": "user-123", "tenant_id": "default", "request_id": request_id},
                    ),
                    store=sdk.store,
                    derived_rule_id="inf.actor_meta.tag",
                    derived_rule_version="v1",
                )
        active = [c for c in sdk.ledger.find_claims(pred_id="user:tag") if not sdk.ledger.has_active_revocation(c.asrt_id)]
        assert len(active) == 1, f"erwartet 1 abgeleitete Assertion, bekam {len(active)}"

    def test_actor_meta_rejects_write_protocol_managed_keys(self) -> None:
        candidate = CandidateSet(
            derivation_id="d1",
            derivation_version="1.0",
            run_id="run-1",
            target="user:tag",
            key_tuple_digest="sha256:" + ("0" * 64),
            tup_digest=None,
            payload={"terms": []},
            support_digest="sha256:" + ("0" * 64),
            support_kind="native",
            generated_at=0,
            state="proposed",
        )
        options = AcceptOptions(actor_meta={"ingest_key": "x"})
        with self.assertRaises(WriteProtocolError):
            _build_base_write_meta(
                candidate_set=candidate,
                options=options,
                derived_rule_id="real.rule",
                derived_rule_version="v1",
                schema_digest_token=None,
                policy_digest_token=None,
                cand_key_digest="sha256:" + ("1" * 64),
            )


if __name__ == "__main__":
    unittest.main()
