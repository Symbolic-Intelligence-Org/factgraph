"""Gates for the meta-based premise admissibility filter (core/store/premise_filter.py).

All tests run against real stores — SDKStore with a compiled schema, the real
SQLite-backed Ledger, native evaluation, and the real souffle/problog export
code paths. No mocks.

Engine-mode coverage: the souffle binary, problog, and pyreason backends are
not installed in this environment. Per preflight P6 the engine gates are
therefore tested at EXPORT level, which IS the engine premise set: the
adapters read every fact through ``store.ledger`` (souffle
``_build_fact_rows``, problog ``export_problog``), so an excluded claim that
never reaches the exported package/program cannot influence the engine
result. ``Store.evaluate_engine`` hands every registered evaluator the same
premise-scoped store view exercised here via ``premise_scoped_store_view``;
``EngineEvaluatorSeamTests`` pins that hand-off itself through the real
registration mechanics and the real ``fg.eval.evaluate_candidates`` path.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import factgraph.adapters.souffle.package as souffle_package
from factgraph.adapters.problog.problog_export import export_problog
from factgraph.application.derivation_check_runtime import check_derivation_binding
from factgraph.application.proofframe_runtime import recheck_proof_frame
from factgraph.application.protocol import (
    CheckRequest,
    CompiledDerivationPlan,
    CompiledHeadCall,
    FactOverlay,
    ProofFrameRecheckRequest,
)
from factgraph.core.store.ledger import MetaRow
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    normalize_premise_exclusions,
    premise_scoped_ledger,
)
from factgraph.core.store.runtime import premise_scoped_store_view
from factgraph.sdk import (
    Case,
    EmitSpec,
    Inference,
    Not,
    Pred,
    SDKStore,
    SDKStoreError,
    vars as sdk_vars,
)
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()
    blocked: str = Field()
    tag: str = Field()


EXCLUSION = MetaExclusion(key="provenance_class", values=frozenset({"claimed_by_agent"}))
AGENT_META = {"source": "agent", "provenance_class": "claimed_by_agent"}
HUMAN_META = {"source": "human"}


def _tag_inference(inf_id: str = "inf.premise.tag") -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred("user:tag_seed", u, t)], id="seed")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _negation_inference(inf_id: str = "inf.premise.neg") -> Inference:
    with sdk_vars("u", "t", "b") as (u, t, b):
        return Inference(
            id=inf_id,
            version="v1",
            when=[
                Case(
                    [Pred("user:tag_seed", u, t), Not([Pred("user:blocked", u, b)])],
                    id="main",
                )
            ],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _candidate_refs(candidates: list) -> list[str]:
    return sorted(cs.payload["terms"][0]["value"] for cs in candidates)


def _check_plan() -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="check.premise",
        version="v1",
        body_ir=[("pred", "user:tag_seed", ["$u", "$t"])],
        heads=(CompiledHeadCall(target_pred_id="user:tag", head_var_names=("$u", "$t")),),
    )


class MetaExclusionConfigTests(unittest.TestCase):
    """Konfigurations-Objekt und Zero-Config-Vertrag (Gate 7)."""

    def test_meta_exclusion_validates_and_normalizes(self) -> None:
        exclusion = MetaExclusion(key="k", values=["a", "b"])  # type: ignore[arg-type]
        self.assertEqual(exclusion.values, frozenset({"a", "b"}))
        with self.assertRaises(ValueError):
            MetaExclusion(key="", values=frozenset({"a"}))
        with self.assertRaises(ValueError):
            MetaExclusion(key="k", values=frozenset())
        with self.assertRaises(ValueError):
            MetaExclusion(key="k", values="a")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            normalize_premise_exclusions(["not-an-exclusion"])  # type: ignore[list-item]

    def test_zero_config_introduces_no_wrapper(self) -> None:
        # Default leer: weder Store-View noch Ledger-Wrapper werden eingezogen —
        # byte-identisches Verhalten der bestehenden Suite ist damit strukturell
        # garantiert (dieselben Objekte, kein zusaetzlicher Codepfad).
        fg = SDKStore([User])
        self.assertEqual(fg.store.premise_exclusions, ())
        self.assertIs(premise_scoped_store_view(fg.store), fg.store)
        self.assertIs(premise_scoped_ledger(fg.ledger, ()), fg.ledger)
        self.assertIs(premise_scoped_ledger(fg.ledger, None), fg.ledger)

    def test_configured_exclusions_always_wrap_for_live_visibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        # Konfigurierte Exclusions ziehen den Wrapper IMMER ein — auch ohne
        # aktuell passende Assertion. Nur so greift die Live-Sichtbarkeit
        # fuer Fakten, die erst nach Wrapper-Konstruktion klassifiziert
        # werden (kein Konstruktionszeit-Kurzschluss).
        self.assertIsNot(premise_scoped_store_view(fg.store), fg.store)
        # Baseline-Semantik fuer nicht-klassifizierte Fakten unveraendert.
        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.nomatch"), engine="native"
        )
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_zero_config_evaluation_sees_agent_classed_facts(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)
        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_sdk_setter_rejects_invalid_config(self) -> None:
        fg = SDKStore([User])
        with self.assertRaises(SDKStoreError):
            fg.set_premise_exclusions(["nope"])  # type: ignore[list-item]

    def test_sdk_setter_none_disables(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        self.assertEqual(fg.premise_exclusions, (EXCLUSION,))
        fg.set_premise_exclusions(None)
        self.assertEqual(fg.premise_exclusions, ())


class NativeSupportGateTests(unittest.TestCase):
    """Gate 1: ausgeschlossene Fakten koennen keine Ableitung stuetzen."""

    def test_excluded_support_yields_no_candidate(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref_plain = fg.entities.ref(User, user_id="u-plain")
        fg.fields.set(User.tag_seed, ref_plain, "vip", meta=HUMAN_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)

        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")

        # Identischer Fakt ohne Klasse stuetzt; mit ausgeschlossener Klasse nicht.
        self.assertEqual(_candidate_refs(candidates), [ref_plain])

    def test_only_configured_values_are_excluded(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-verified")
        fg.fields.set(
            User.tag_seed,
            ref,
            "vip",
            meta={"source": "agent", "provenance_class": "verified"},
        )
        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_candidate_refs(candidates), [ref])


class NativeNegationGateTests(unittest.TestCase):
    """Gate 2: ausgeschlossene Fakten verhindern keine Ableitung ueber Negation."""

    def test_excluded_blocker_does_not_violate_negation(self) -> None:
        fg = SDKStore([User])
        ref_free = fg.entities.ref(User, user_id="u-free")      # kein Blocker
        ref_blocked = fg.entities.ref(User, user_id="u-blocked")  # echter Blocker
        ref_agent = fg.entities.ref(User, user_id="u-agent")    # nur Agent-Blocker
        for ref in (ref_free, ref_blocked, ref_agent):
            fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        fg.fields.set(User.blocked, ref_blocked, "yes", meta=HUMAN_META)
        fg.fields.set(User.blocked, ref_agent, "yes", meta=AGENT_META)

        # Ohne Filter blockiert der Agent-Fakt die Negation.
        baseline = fg.eval.evaluate_candidates(
            _negation_inference("inf.premise.neg.baseline"), engine="native"
        )
        self.assertEqual(_candidate_refs(baseline), [ref_free])

        # Mit Filter existiert der Agent-Blocker fuer die Auswertung nicht.
        fg.set_premise_exclusions([EXCLUSION])
        filtered = fg.eval.evaluate_candidates(
            _negation_inference("inf.premise.neg.filtered"), engine="native"
        )
        self.assertEqual(_candidate_refs(filtered), sorted([ref_free, ref_agent]))


class EngineExportGateTests(unittest.TestCase):
    """Gates 3+4: ausgeschlossene Claims erreichen das Engine-Paket/Programm nicht.

    Das souffle-Binary und problog sind lokal nicht installiert; die
    Export-Ebene IST die Engine-Praemissenmenge (die Adapter lesen alle
    Fakten aus ``store.ledger``, siehe Modul-Docstring).
    """

    def _seeded(self) -> tuple[SDKStore, str, str]:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref_plain = fg.entities.ref(User, user_id="u-plain")
        plain_id = fg.fields.set(User.tag_seed, ref_plain, "vip", meta=HUMAN_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        return fg, plain_id, agent_id

    def test_souffle_export_omits_excluded_claims(self) -> None:
        fg, plain_id, agent_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        self.assertIsNot(view, fg.store)
        with TemporaryDirectory() as tmp:
            scoped_dir = Path(tmp) / "scoped"
            souffle_package.export_package(
                view, scoped_dir, souffle_package.ExportOptions()
            )
            claim_rows = (scoped_dir / "facts" / "claim.facts").read_text(encoding="utf-8")
            meta_rows = (scoped_dir / "facts" / "meta_str.facts").read_text(encoding="utf-8")
            arg_rows = (scoped_dir / "facts" / "claim_arg.facts").read_text(encoding="utf-8")
            self.assertIn(plain_id, claim_rows)
            self.assertNotIn(agent_id, claim_rows)
            self.assertNotIn(agent_id, meta_rows)
            self.assertNotIn(agent_id, arg_rows)

            # Roh-Export ohne View (Audit-/Lese-Pfad) bleibt ungefiltert.
            raw_dir = Path(tmp) / "raw"
            souffle_package.export_package(
                fg.store, raw_dir, souffle_package.ExportOptions()
            )
            raw_rows = (raw_dir / "facts" / "claim.facts").read_text(encoding="utf-8")
            self.assertIn(agent_id, raw_rows)

    def test_problog_export_omits_excluded_claims(self) -> None:
        fg, plain_id, agent_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        rule_spec = {
            "derivation_id": "drv.premise.problog",
            "version": "v1",
            "target_pred_id": "user:tag",
            "head_vars": ["$u", "$t"],
            "where": [("pred", "user:tag_seed", ["$u", "$t"])],
            "query_pred": "answer",
        }
        with TemporaryDirectory() as tmp:
            scoped_path = Path(tmp) / "scoped.pl"
            export_problog(view, rule_spec, scoped_path)
            program = scoped_path.read_text(encoding="utf-8")
            self.assertIn(plain_id, program)
            self.assertNotIn(agent_id, program)

            raw_path = Path(tmp) / "raw.pl"
            export_problog(fg.store, rule_spec, raw_path)
            self.assertIn(agent_id, raw_path.read_text(encoding="utf-8"))

    def test_souffle_export_filters_excluded_revocation(self) -> None:
        # Revocation-Symmetrie im Engine-Export: die revokes-Filterung des
        # Wrappers traegt die Symmetrie in den souffle-Export — eine
        # agent-klassifizierte Ruecknahme erreicht revokes.facts nicht.
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        fg.assertions.retract(support_id, meta=dict(AGENT_META))
        revoker_id = fg.ledger.find_revoker(support_id)
        self.assertIsNotNone(revoker_id)

        view = premise_scoped_store_view(fg.store)
        self.assertIsNot(view, fg.store)
        with TemporaryDirectory() as tmp:
            scoped_dir = Path(tmp) / "scoped"
            souffle_package.export_package(
                view, scoped_dir, souffle_package.ExportOptions()
            )
            scoped_revokes = (scoped_dir / "facts" / "revokes.facts").read_text(
                encoding="utf-8"
            )
            # Die Revoke-Zeile fehlt in der scoped View ...
            self.assertNotIn(support_id, scoped_revokes)
            self.assertNotIn(revoker_id, scoped_revokes)

            # ... und ist im Roh-Export (Audit-/Lese-Pfad) vorhanden.
            raw_dir = Path(tmp) / "raw"
            souffle_package.export_package(
                fg.store, raw_dir, souffle_package.ExportOptions()
            )
            raw_revokes = (raw_dir / "facts" / "revokes.facts").read_text(
                encoding="utf-8"
            )
            self.assertIn(support_id, raw_revokes)
            self.assertIn(revoker_id, raw_revokes)


class ProofFrameRecheckGateTests(unittest.TestCase):
    """Gate 5: Re-Check-Konsistenz bei nachtraeglicher Meta-Umklassifizierung.

    Nachtraegliche Umklassifizierung IST im Kern darstellbar: Meta-Rows
    entstehen zwar beim Write, aber ``Ledger.append_meta`` (compatibility
    window, deprecated-but-real) haengt zusaetzliche Meta-Rows an eine
    bestehende Assertion. Kein Zwei-Welten-Fallback noetig — derselbe Store,
    dieselbe Receipt, echte Umklassifizierung.
    """

    def test_reclassified_support_invalidates_existing_receipt(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)

        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.recheck"), engine="native"
        )
        self.assertEqual(len(candidates), 1)
        receipt = fg.store._lookup_support_artifact(candidates[0].support_digest)
        self.assertIsNotNone(receipt)
        assert receipt is not None
        witnessed = {a for w in receipt.pred_witnesses for a in w.asrt_ids}
        self.assertIn(support_id, witnessed)

        request = ProofFrameRecheckRequest(support_artifact=receipt, overlay=FactOverlay())
        before = recheck_proof_frame(request, store=fg.store)
        self.assertEqual(before.status, "still_valid")

        # Echte Umklassifizierung der bestehenden Stuetze.
        fg.ledger.append_meta(
            [
                MetaRow(
                    asrt_id=support_id,
                    key="provenance_class",
                    kind="str",
                    value="claimed_by_agent",
                )
            ]
        )
        after = recheck_proof_frame(request, store=fg.store)
        self.assertEqual(after.status, "invalidated")
        # Und die Auswertung selbst liefert den Kandidaten nicht mehr.
        self.assertEqual(
            fg.eval.evaluate_candidates(
                _tag_inference("inf.premise.recheck.after"), engine="native"
            ),
            [],
        )


class ReclassificationLastWinsTests(unittest.TestCase):
    """Last-wins: Umklassifizierung RAUS aus der Klasse stellt Admissibility wieder her.

    Gegenrichtung zu Gate 5 (ProofFrameRecheckGateTests): dort macht
    ``append_meta`` eine Assertion auswertungs-unsichtbar, hier macht
    derselbe Mechanismus sie wieder sichtbar. Es zaehlt der LETZTE
    Meta-Row-Wert unter dem Schluessel — identische Reihenfolge-Semantik
    wie die kanonische SDK-Lesart (``_meta_raw_for_assertion``,
    last-row-wins; siehe ``is_premise_excluded``).
    """

    def test_reclassification_out_of_excluded_class_restores_admissibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)

        # Agent-klassifiziert: unsichtbar fuer die Auswertung.
        self.assertEqual(
            fg.eval.evaluate_candidates(
                _tag_inference("inf.premise.lastwins.before"), engine="native"
            ),
            [],
        )

        # Umklassifizierung RAUS aus der ausgeschlossenen Klasse — exakt der
        # Gate-5-Mechanismus (Ledger.append_meta) in Gegenrichtung.
        fg.ledger.append_meta(
            [
                MetaRow(
                    asrt_id=asrt_id,
                    key="provenance_class",
                    kind="str",
                    value="verified",
                )
            ]
        )

        # Kanonische Lesart zeigt die neue Klasse ...
        record = fg.assertions.by_id(asrt_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.meta.raw.get("provenance_class"), "verified")
        # ... und die Auswertung folgt ihr: der Kandidat entsteht wieder.
        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.lastwins.after"), engine="native"
        )
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_reclassified_excluded_revoker_becomes_effective(self) -> None:
        # Symmetrie: ein agent-klassifizierter Revoker, spaeter aus der
        # Klasse herausklassifiziert, macht die Ruecknahme auch fuer die
        # Auswertung wirksam.
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        fg.assertions.retract(support_id, meta=dict(AGENT_META))
        revoker_id = fg.ledger.find_revoker(support_id)
        self.assertIsNotNone(revoker_id)
        assert revoker_id is not None

        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.lastwins.revoker.before"), engine="native"
        )
        self.assertEqual(_candidate_refs(candidates), [ref])

        fg.ledger.append_meta(
            [
                MetaRow(
                    asrt_id=revoker_id,
                    key="provenance_class",
                    kind="str",
                    value="verified",
                )
            ]
        )
        self.assertEqual(
            fg.eval.evaluate_candidates(
                _tag_inference("inf.premise.lastwins.revoker.after"), engine="native"
            ),
            [],
        )


class LiveVisibilityTests(unittest.TestCase):
    """Sichtbarkeit wird pro Zugriff LIVE entschieden — kein eingefrorenes Set.

    meander-Evals laufen in Request-Threads ohne den meander-WRITE_LOCK; ein
    mid-eval geschriebener Fakt mit ausgeschlossener Klasse darf die
    Praemissenmenge nicht erreichen. Dieselbe eine Logik
    (``is_premise_excluded``) traegt last-wins und Revocation-Symmetrie.
    """

    def test_fact_written_after_wrapper_construction_is_filtered_live(self) -> None:
        fg = SDKStore([User])
        # Wrapper VOR den Schreib-Vorgaengen konstruieren (mid-eval Szenario);
        # zu diesem Zeitpunkt existiert noch keine klassifizierte Assertion.
        scoped = premise_scoped_ledger(fg.ledger, (EXCLUSION,))
        self.assertIsNot(scoped, fg.ledger)

        ref_agent = fg.entities.ref(User, user_id="u-agent-late")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        ref_plain = fg.entities.ref(User, user_id="u-plain-late")
        plain_id = fg.fields.set(User.tag_seed, ref_plain, "vip", meta=HUMAN_META)

        # Der spaeter geschriebene agent-Fakt ist im selben Moment unsichtbar ...
        self.assertIsNone(scoped.get_claim(agent_id))
        self.assertNotIn(agent_id, [c.asrt_id for c in scoped.claims])
        self.assertEqual(scoped.find_meta(asrt_id=agent_id), [])
        # ... der nicht-klassifizierte bleibt sichtbar (Baseline unveraendert).
        self.assertIsNotNone(scoped.get_claim(plain_id))
        self.assertIn(plain_id, [c.asrt_id for c in scoped.claims])

    def test_revocation_written_after_wrapper_construction_is_filtered_live(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        scoped = premise_scoped_ledger(fg.ledger, (EXCLUSION,))

        fg.assertions.retract(support_id, meta=dict(AGENT_META))

        # Basis sieht die Ruecknahme, die scoped Sicht nicht.
        self.assertTrue(fg.ledger.has_active_revocation(support_id))
        self.assertFalse(scoped.has_active_revocation(support_id))
        self.assertIsNone(scoped.find_revoker(support_id))
        self.assertEqual(scoped.revokes, [])


class EngineEvaluatorSeamTests(unittest.TestCase):
    """Produktions-Naht aller Engine-Modi: ``Store.evaluate_engine`` reicht
    die premise-scoped Store-View an den registrierten Evaluator.

    Der Probe-Evaluator wird ueber die reale Override-Mechanik registriert
    (``Store.set_engine_evaluator`` -> ``_engine_overrides['souffle']``,
    dieselbe Naht, die ``register_engine_evaluator`` global bedient) und
    ueber den ECHTEN Aufrufweg ``fg.eval.evaluate_candidates(...,
    engine='souffle')`` gefahren. Eine Mutation von
    ``runtime.py::evaluate_engine`` zurueck zu ``evaluator(self, ...)``
    macht diesen Test rot.
    """

    def test_engine_evaluator_receives_premise_scoped_store(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref_plain = fg.entities.ref(User, user_id="u-plain")
        plain_id = fg.fields.set(User.tag_seed, ref_plain, "vip", meta=HUMAN_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)

        observed: dict[str, object] = {}

        def probe_evaluator(store, **kwargs):  # noqa: ANN001, ANN003 - EngineEvaluatorFn
            observed["excluded_claim"] = store.ledger.get_claim(agent_id)
            observed["plain_claim"] = store.ledger.get_claim(plain_id)
            observed["claim_ids"] = [c.asrt_id for c in store.ledger.claims]
            return []

        fg.store.set_engine_evaluator(probe_evaluator)
        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.seam"), engine="souffle"
        )
        self.assertEqual(candidates, [])
        # Der Evaluator ist ueber den echten Weg gelaufen ...
        self.assertIn("claim_ids", observed)
        # ... und sieht die ausgeschlossene Assertion NICHT,
        # die nicht-klassifizierte sehr wohl.
        self.assertIsNone(observed["excluded_claim"])
        self.assertIsNotNone(observed["plain_claim"])
        self.assertNotIn(agent_id, observed["claim_ids"])
        self.assertIn(plain_id, observed["claim_ids"])


class DerivationCheckGateTests(unittest.TestCase):
    """Verdrahtung des nativen derivation-check: gleiche Praemissenmenge wie evaluate."""

    def test_native_check_excludes_filtered_support(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)

        passed = check_derivation_binding(
            CheckRequest(plan=_check_plan(), binding=(("$u", ref),), engine="native"),
            store=fg.store,
        )
        self.assertEqual(passed.status, "passed")

        fg.set_premise_exclusions([EXCLUSION])
        failed = check_derivation_binding(
            CheckRequest(plan=_check_plan(), binding=(("$u", ref),), engine="native"),
            store=fg.store,
        )
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.matched_count, 0)


class ReadPathsUntouchedTests(unittest.TestCase):
    """Gate 6: Lese-/Query-Pfade ausserhalb der Auswertung bleiben ungefiltert."""

    def test_excluded_fact_stays_visible_on_read_paths(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-agent")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)

        # Layer 3: Assertion-Queries inkl. Meta-Filter sehen den Fakt.
        by_meta = fg.assertions.where(
            field=User.tag_seed, _meta={"provenance_class": "claimed_by_agent"}
        )
        self.assertEqual([record.asrt_id for record in by_meta.all()], [asrt_id])
        record = fg.assertions.by_id(asrt_id)
        self.assertIsNotNone(record)
        self.assertTrue(record.is_active)

        # Layer 2 + Layer 1: Feld-Wert und Entity-Sicht unveraendert.
        self.assertEqual(fg.fields.get(User.tag_seed, ref), "vip")
        snapshot = fg.entities.get(User, user_id="u-agent")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.tag_seed, "vip")

        # Historie: der Fakt bleibt Teil der vollstaendigen Assertion-Liste.
        self.assertIn(asrt_id, [r.asrt_id for r in fg.assertions.all])


class RevocationSymmetryTests(unittest.TestCase):
    """Symmetrie-Semantik: eine ausgeschlossene Ruecknahme wirkt in der Auswertung nicht.

    Eine Revocation, deren Revoker-Assertion die ausgeschlossene Klasse
    traegt, ist fuer die Auswertung ebenso unsichtbar wie ein
    ausgeschlossener Claim — eine nicht-admissible Ruecknahme kann keinen
    Fakt aus der Praemissenmenge entfernen. Lese-Pfade zeigen die
    Ruecknahme weiterhin als wirksam.
    """

    def test_excluded_revocation_is_invisible_to_evaluation_only(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        fg.assertions.retract(support_id, meta=dict(AGENT_META))

        # Lese-Pfad: Ruecknahme wirksam, Fakt nicht mehr aktiv.
        self.assertIsNone(fg.fields.get(User.tag_seed, ref))

        # Auswertung: die agent-klassifizierte Ruecknahme existiert nicht,
        # der menschliche Fakt stuetzt weiterhin.
        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.revoke"), engine="native"
        )
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_plain_revocation_stays_effective_in_evaluation(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=HUMAN_META)
        fg.assertions.retract(support_id, meta=HUMAN_META)

        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.premise.revoke.plain"), engine="native"
        )
        self.assertEqual(candidates, [])


class ScopedLedgerSurfaceTests(unittest.TestCase):
    """Wrapper-Vertrag: vollstaendige Lese-Oberflaeche gefiltert, Writes abgewiesen."""

    def _scoped(self) -> tuple[SDKStore, object, str, str]:
        fg = SDKStore([User])
        ref_plain = fg.entities.ref(User, user_id="u-plain")
        plain_id = fg.fields.set(User.tag_seed, ref_plain, "vip", meta=HUMAN_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        scoped = premise_scoped_ledger(fg.ledger, (EXCLUSION,))
        self.assertIsNot(scoped, fg.ledger)
        return fg, scoped, plain_id, agent_id

    def test_read_surface_hides_excluded_assertion(self) -> None:
        fg, scoped, plain_id, agent_id = self._scoped()
        self.assertIsNone(scoped.get_claim(agent_id))
        self.assertIsNotNone(scoped.get_claim(plain_id))
        self.assertNotIn(agent_id, [c.asrt_id for c in scoped.claims])
        self.assertNotIn(agent_id, [c.asrt_id for c in scoped.find_claims(pred_id="user:tag_seed")])
        self.assertEqual(scoped.find_claim_args(asrt_id=agent_id), [])
        self.assertEqual(scoped.find_meta(asrt_id=agent_id), [])
        self.assertEqual(scoped.find_annotations(asrt_id=agent_id), [])
        self.assertNotIn(agent_id, [r.asrt_id for r in scoped.meta_rows])
        self.assertNotIn(agent_id, [r.asrt_id for r in scoped.claim_args])
        # Basis-Ledger unveraendert.
        self.assertIn(agent_id, [c.asrt_id for c in fg.ledger.claims])

    def test_writes_are_rejected(self) -> None:
        _, scoped, plain_id, _ = self._scoped()
        with self.assertRaises(RuntimeError):
            scoped.append_meta(
                [MetaRow(asrt_id=plain_id, key="x", kind="str", value="y")]
            )
        with self.assertRaises(RuntimeError):
            scoped.set_ledger_meta("k", "v")


if __name__ == "__main__":
    unittest.main()
