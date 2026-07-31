"""Gates for ``SDKStore.premise_scoped_view()`` — the read-only view that applies
the SAME premise admissibility filter as evaluation to ordinary SDK read verbs.

All tests run against real stores (SDKStore + real SQLite Ledger + native
evaluation). No mocks. The view composes the existing
``premise_scoped_store_view`` (proven by test_premise_admissibility_filter.py at
the evaluation seam) with the SDK read facades; these gates pin that the read
verbs a caller like the ILP extract uses (``entities.where`` + ``getattr``,
``fields.get``, ``assertions``) see admissible-only facts, that the base graph
stays unfiltered, and that the zero-config identity contract holds.
"""

from __future__ import annotations

import unittest

from factgraph.sdk import (
    Case,
    EmitSpec,
    Inference,
    Pred,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    SDKStore,
    vars as sdk_vars,
)
from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()


EXCLUSION = MetaExclusion(key="provenance_class", values=frozenset({"claimed_by_agent"}))
AGENT_META = {"source": "agent", "provenance_class": "claimed_by_agent"}
HUMAN_META = {"source": "human"}


def _tag_inference(inf_id: str = "inf.scoped.tag") -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred("user:tag_seed", u, t)], id="seed")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _by_identity(store: SDKStore) -> dict:
    return {snap.user_id: snap for snap in store.entities.where(User)}


class ZeroConfigIdentityTests(unittest.TestCase):
    """Ohne konfigurierte Dimension ist die View das Objekt selbst (Identity)."""

    def test_no_config_returns_self(self) -> None:
        fg = SDKStore([User])
        self.assertIs(fg.premise_scoped_view(), fg)

    def test_no_config_returns_self_even_with_facts(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u")
        fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)
        # Kein Filter konfiguriert -> keine View, kein zusaetzlicher Codepfad.
        self.assertIs(fg.premise_scoped_view(), fg)


class ReadVerbsFilteredTests(unittest.TestCase):
    """Die SDK-Leseverben sehen durch die View nur auswertungs-admissible Fakten."""

    def _seeded(self) -> tuple[SDKStore, str, str, object, object]:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref_h = fg.entities.ref(User, user_id="u-h")
        h_id = fg.fields.set(User.tag_seed, ref_h, "vip", meta=HUMAN_META)
        ref_a = fg.entities.ref(User, user_id="u-a")
        a_id = fg.fields.set(User.tag_seed, ref_a, "vip", meta=AGENT_META)
        return fg, h_id, a_id, ref_h, ref_a

    def test_entities_where_getattr_drops_excluded(self) -> None:
        fg, _h_id, _a_id, _ref_h, _ref_a = self._seeded()
        scoped = fg.premise_scoped_view()
        self.assertIsNot(scoped, fg)

        scoped_by_id = _by_identity(scoped)
        # Exakt der Verb, den extract_background nutzt: entities.where + getattr.
        self.assertEqual(scoped_by_id["u-h"].tag_seed, "vip")
        self.assertIsNone(scoped_by_id["u-a"].tag_seed)

        # Der Basis-Graph bleibt ungefiltert (die View ist ein eigenes Objekt).
        base_by_id = _by_identity(fg)
        self.assertEqual(base_by_id["u-h"].tag_seed, "vip")
        self.assertEqual(base_by_id["u-a"].tag_seed, "vip")

    def test_fields_get_drops_excluded(self) -> None:
        fg, _h_id, _a_id, ref_h, ref_a = self._seeded()
        scoped = fg.premise_scoped_view()
        self.assertEqual(scoped.fields.get(User.tag_seed, ref_h), "vip")
        self.assertIsNone(scoped.fields.get(User.tag_seed, ref_a))
        # Basis unveraendert.
        self.assertEqual(fg.fields.get(User.tag_seed, ref_a), "vip")

    def test_assertions_listing_drops_excluded(self) -> None:
        fg, h_id, a_id, _ref_h, _ref_a = self._seeded()
        scoped = fg.premise_scoped_view()
        scoped_ids = [r.asrt_id for r in scoped.assertions.all]
        self.assertIn(h_id, scoped_ids)
        self.assertNotIn(a_id, scoped_ids)
        # Basis-Historie behaelt den ausgeschlossenen Fakt vollstaendig.
        self.assertIn(a_id, [r.asrt_id for r in fg.assertions.all])


class AllowanceAndBlockDimensionTests(unittest.TestCase):
    """Alle drei Filter-Dimensionen wirken durch die View, nicht nur die globale Exclusion."""

    def test_view_respects_predicate_allowance(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances(
            [
                PredicatePremiseAllowance(
                    pred_id="user:tag_seed",
                    key="provenance_class",
                    allowed_values=frozenset({"accredited"}),
                )
            ]
        )
        ref_ok = fg.entities.ref(User, user_id="u-ok")
        fg.fields.set(User.tag_seed, ref_ok, "vip", meta={"provenance_class": "accredited"})
        ref_no = fg.entities.ref(User, user_id="u-no")
        fg.fields.set(User.tag_seed, ref_no, "vip", meta={"provenance_class": "observed"})

        scoped_by_id = _by_identity(fg.premise_scoped_view())
        self.assertEqual(scoped_by_id["u-ok"].tag_seed, "vip")
        self.assertIsNone(scoped_by_id["u-no"].tag_seed)

    def test_view_respects_predicate_block(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks(
            [
                PredicatePremiseBlock(
                    pred_id="user:tag_seed",
                    key="origin_binding",
                    blocked_values=frozenset({"src-x"}),
                )
            ]
        )
        ref_blocked = fg.entities.ref(User, user_id="u-blocked")
        fg.fields.set(User.tag_seed, ref_blocked, "vip", meta={"origin_binding": "src-x"})
        ref_ok = fg.entities.ref(User, user_id="u-ok")
        fg.fields.set(User.tag_seed, ref_ok, "vip", meta={"origin_binding": "src-y"})

        scoped_by_id = _by_identity(fg.premise_scoped_view())
        self.assertIsNone(scoped_by_id["u-blocked"].tag_seed)
        self.assertEqual(scoped_by_id["u-ok"].tag_seed, "vip")


class LiveVisibilityTests(unittest.TestCase):
    """Sichtbarkeit wird pro Zugriff LIVE entschieden — auch fuer nach View-Bau geschriebene Fakten."""

    def test_fact_written_after_view_construction_is_filtered(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        # View VOR jedem klassifizierten Fakt bauen.
        scoped = fg.premise_scoped_view()
        self.assertIsNot(scoped, fg)

        ref_a = fg.entities.ref(User, user_id="u-a")
        fg.fields.set(User.tag_seed, ref_a, "vip", meta=AGENT_META)
        ref_h = fg.entities.ref(User, user_id="u-h")
        fg.fields.set(User.tag_seed, ref_h, "vip", meta=HUMAN_META)

        scoped_by_id = _by_identity(scoped)
        # Der erst nach View-Bau geschriebene agent-Fakt ist live gefiltert.
        self.assertIsNone(scoped_by_id["u-a"].tag_seed)
        self.assertEqual(scoped_by_id["u-h"].tag_seed, "vip")


class EvaluationParityTests(unittest.TestCase):
    """Die View exponiert exakt die Praemissenmenge, die die Auswertung admittiert."""

    def test_view_read_set_matches_evaluation_admissibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref_h = fg.entities.ref(User, user_id="u-h")
        fg.fields.set(User.tag_seed, ref_h, "vip", meta=HUMAN_META)
        ref_a = fg.entities.ref(User, user_id="u-a")
        fg.fields.set(User.tag_seed, ref_a, "vip", meta=AGENT_META)

        # Auswertung admittiert nur den menschlich belegten Seed.
        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        admitted_refs = sorted(cs.payload["terms"][0]["value"] for cs in candidates)
        self.assertEqual(admitted_refs, [ref_h])

        # Die View zeigt genau denselben admissiblen tag_seed-Satz.
        scoped_by_id = _by_identity(fg.premise_scoped_view())
        visible = sorted(
            ident for ident, snap in scoped_by_id.items() if snap.tag_seed is not None
        )
        self.assertEqual(visible, ["u-h"])


if __name__ == "__main__":
    unittest.main()
