"""Gates for the per-predicate premise admissibility allowance (Block A).

Generalises the global ``MetaExclusion`` filter into a per-predicate
allow-list: for a configured predicate, an assertion is admissible as a
premise only when its meta ``key`` last-value is in the predicate's
``allowed_values`` (an assertion missing the key is admitted only when
``absent_ok``). The two dimensions are OR-combined, so the global exclusion
floor is never lifted by an allowance.

All tests run against real stores — SDKStore with a compiled schema, the real
SQLite-backed Ledger, native evaluation, and the real souffle/problog export
code paths. No mocks. As in test_premise_admissibility_filter.py, the souffle
binary / problog / pyreason backends are absent here, so the engine gates are
tested at EXPORT level (the engine premise set) and at the evaluator seam.
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
    PredicatePremiseAllowance,
    normalize_premise_allowances,
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


SEED_PRED = "user:tag_seed"
BLOCKED_PRED = "user:blocked"

# Allowance on the seed predicate: only observed / human_attested facts may
# serve as a premise; class-less and agent-claimed seeds are inadmissible.
SEED_ALLOWANCE = PredicatePremiseAllowance(
    pred_id=SEED_PRED,
    key="provenance_class",
    allowed_values=frozenset({"observed", "human_attested"}),
)

OBSERVED_META = {"source": "otel", "provenance_class": "observed"}
HUMAN_META = {"source": "human", "provenance_class": "human_attested"}
AGENT_META = {"source": "agent", "provenance_class": "claimed_by_agent"}
NOCLASS_META = {"source": "telemetry"}  # legacy fact: no provenance_class


def _tag_inference(inf_id: str = "inf.allow.tag") -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred(SEED_PRED, u, t)], id="seed")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _negation_inference(inf_id: str = "inf.allow.neg") -> Inference:
    with sdk_vars("u", "t", "b") as (u, t, b):
        return Inference(
            id=inf_id,
            version="v1",
            when=[
                Case(
                    [Pred(SEED_PRED, u, t), Not([Pred(BLOCKED_PRED, u, b)])],
                    id="main",
                )
            ],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _candidate_refs(candidates: list) -> list[str]:
    return sorted(cs.payload["terms"][0]["value"] for cs in candidates)


def _check_plan() -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="check.allow",
        version="v1",
        body_ir=[("pred", SEED_PRED, ["$u", "$t"])],
        heads=(CompiledHeadCall(target_pred_id="user:tag", head_var_names=("$u", "$t")),),
    )


class AllowanceConfigTests(unittest.TestCase):
    """Konfigurations-Objekt, Normalisierung und Zero-Config-Vertrag."""

    def test_allowance_validates_and_normalizes(self) -> None:
        allowance = PredicatePremiseAllowance(
            pred_id="p", key="k", allowed_values=["a", "b"]  # type: ignore[arg-type]
        )
        self.assertEqual(allowance.allowed_values, frozenset({"a", "b"}))
        self.assertFalse(allowance.absent_ok)
        with self.assertRaises(ValueError):
            PredicatePremiseAllowance(pred_id="", key="k", allowed_values=frozenset({"a"}))
        with self.assertRaises(ValueError):
            PredicatePremiseAllowance(pred_id="p", key="", allowed_values=frozenset({"a"}))
        with self.assertRaises(ValueError):
            PredicatePremiseAllowance(pred_id="p", key="k", allowed_values=frozenset())
        with self.assertRaises(ValueError):
            PredicatePremiseAllowance(pred_id="p", key="k", allowed_values="a")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            PredicatePremiseAllowance(
                pred_id="p", key="k", allowed_values=frozenset({"a"}), absent_ok="yes"  # type: ignore[arg-type]
            )

    def test_normalize_rejects_bad_items_and_duplicate_pred(self) -> None:
        with self.assertRaises(ValueError):
            normalize_premise_allowances(["nope"])  # type: ignore[list-item]
        with self.assertRaises(ValueError):
            normalize_premise_allowances(
                [
                    PredicatePremiseAllowance(pred_id="p", key="k", allowed_values=frozenset({"a"})),
                    PredicatePremiseAllowance(pred_id="p", key="k", allowed_values=frozenset({"b"})),
                ]
            )

    def test_zero_config_introduces_no_wrapper(self) -> None:
        fg = SDKStore([User])
        self.assertEqual(fg.store.premise_allowances, ())
        self.assertIs(premise_scoped_store_view(fg.store), fg.store)
        self.assertIs(premise_scoped_ledger(fg.ledger, (), ()), fg.ledger)
        self.assertIs(premise_scoped_ledger(fg.ledger, None, None), fg.ledger)

    def test_configured_allowance_always_wraps(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        self.assertIsNot(premise_scoped_store_view(fg.store), fg.store)

    def test_sdk_setter_roundtrip_and_none_disables(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        self.assertEqual(fg.premise_allowances, (SEED_ALLOWANCE,))
        fg.set_premise_allowances(None)
        self.assertEqual(fg.premise_allowances, ())

    def test_sdk_setter_rejects_invalid(self) -> None:
        fg = SDKStore([User])
        with self.assertRaises(SDKStoreError):
            fg.set_premise_allowances(["nope"])  # type: ignore[list-item]
        with self.assertRaises(SDKStoreError):
            fg.set_premise_allowances(
                [
                    PredicatePremiseAllowance(pred_id="p", key="k", allowed_values=frozenset({"a"})),
                    PredicatePremiseAllowance(pred_id="p", key="k", allowed_values=frozenset({"b"})),
                ]
            )


class AllowanceSupportGateTests(unittest.TestCase):
    """Gate: nur zugelassene Klassen stuetzen; nicht gelistete und klassenlose nicht."""

    def test_only_allowed_classes_support(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref_observed = fg.entities.ref(User, user_id="u-observed")
        fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)
        ref_human = fg.entities.ref(User, user_id="u-human")
        fg.fields.set(User.tag_seed, ref_human, "vip", meta=HUMAN_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        ref_noclass = fg.entities.ref(User, user_id="u-noclass")
        fg.fields.set(User.tag_seed, ref_noclass, "vip", meta=NOCLASS_META)

        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        # observed + human_attested support; agent-claimed and class-less do not.
        self.assertEqual(_candidate_refs(candidates), sorted([ref_observed, ref_human]))

    def test_unconfigured_predicate_is_unaffected(self) -> None:
        # Allowance sits on the (unrelated) blocked predicate; the seed
        # predicate carries no allowance, so class-less seeds still support.
        fg = SDKStore([User])
        fg.set_premise_allowances(
            [
                PredicatePremiseAllowance(
                    pred_id=BLOCKED_PRED,
                    key="provenance_class",
                    allowed_values=frozenset({"observed"}),
                )
            ]
        )
        ref = fg.entities.ref(User, user_id="u-noclass")
        fg.fields.set(User.tag_seed, ref, "vip", meta=NOCLASS_META)
        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_absent_ok_admits_classless_seed(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances(
            [
                PredicatePremiseAllowance(
                    pred_id=SEED_PRED,
                    key="provenance_class",
                    allowed_values=frozenset({"observed"}),
                    absent_ok=True,
                )
            ]
        )
        ref_noclass = fg.entities.ref(User, user_id="u-noclass")
        fg.fields.set(User.tag_seed, ref_noclass, "vip", meta=NOCLASS_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        # class-less now admitted (absent_ok); agent-claimed still not allowed.
        self.assertEqual(_candidate_refs(candidates), [ref_noclass])


class AllowanceNegationGateTests(unittest.TestCase):
    """Gate: ein nicht zugelassener Fakt kann eine Ableitung weder stuetzen noch blockieren."""

    def test_disallowed_blocker_does_not_block(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances(
            [
                PredicatePremiseAllowance(
                    pred_id=BLOCKED_PRED,
                    key="provenance_class",
                    allowed_values=frozenset({"observed"}),
                )
            ]
        )
        ref_free = fg.entities.ref(User, user_id="u-free")             # kein Blocker
        ref_blocked_ok = fg.entities.ref(User, user_id="u-blocked-ok")  # observed Blocker
        ref_blocked_bad = fg.entities.ref(User, user_id="u-blocked-bad")  # agent Blocker
        for ref in (ref_free, ref_blocked_ok, ref_blocked_bad):
            fg.fields.set(User.tag_seed, ref, "vip", meta=NOCLASS_META)
        fg.fields.set(User.blocked, ref_blocked_ok, "yes", meta=OBSERVED_META)
        fg.fields.set(User.blocked, ref_blocked_bad, "yes", meta=AGENT_META)

        candidates = fg.eval.evaluate_candidates(_negation_inference(), engine="native")
        # observed blocker blocks; agent-claimed blocker is inadmissible -> no block.
        self.assertEqual(
            _candidate_refs(candidates), sorted([ref_free, ref_blocked_bad])
        )


class GlobalExclusionFloorTests(unittest.TestCase):
    """Nie lockern: der globale claimed_by_agent-Ausschluss ueberstimmt jede Allowance."""

    def test_global_exclusion_survives_permissive_allowance(self) -> None:
        fg = SDKStore([User])
        # Even a (pathological) allowance that lists claimed_by_agent cannot
        # re-admit it: the global exclusion is OR-combined and wins.
        fg.set_premise_exclusions(
            [MetaExclusion(key="provenance_class", values=frozenset({"claimed_by_agent"}))]
        )
        fg.set_premise_allowances(
            [
                PredicatePremiseAllowance(
                    pred_id=SEED_PRED,
                    key="provenance_class",
                    allowed_values=frozenset({"observed", "claimed_by_agent"}),
                )
            ]
        )
        ref_observed = fg.entities.ref(User, user_id="u-observed")
        fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)

        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_candidate_refs(candidates), [ref_observed])


class AllowanceReclassificationTests(unittest.TestCase):
    """Last-wins fuer die Allowance: Umklassifizierung bewegt IN/AUS der zugelassenen Menge."""

    def test_reclassification_into_allowed_restores_admissibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)
        self.assertEqual(
            fg.eval.evaluate_candidates(_tag_inference("inf.allow.before"), engine="native"),
            [],
        )
        fg.ledger.append_meta(
            [MetaRow(asrt_id=asrt_id, key="provenance_class", kind="str", value="observed")]
        )
        candidates = fg.eval.evaluate_candidates(_tag_inference("inf.allow.after"), engine="native")
        self.assertEqual(_candidate_refs(candidates), [ref])

    def test_reclassification_out_of_allowed_removes_admissibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=OBSERVED_META)
        self.assertEqual(
            _candidate_refs(
                fg.eval.evaluate_candidates(_tag_inference("inf.allow.out.before"), engine="native")
            ),
            [ref],
        )
        fg.ledger.append_meta(
            [MetaRow(asrt_id=asrt_id, key="provenance_class", kind="str", value="claimed_by_agent")]
        )
        self.assertEqual(
            fg.eval.evaluate_candidates(_tag_inference("inf.allow.out.after"), engine="native"),
            [],
        )


class AllowanceLiveVisibilityTests(unittest.TestCase):
    """Sichtbarkeit pro Zugriff LIVE — auch fuer erst nach Wrapper-Bau geschriebene Fakten."""

    def test_fact_written_after_wrapper_is_filtered_live(self) -> None:
        fg = SDKStore([User])
        scoped = premise_scoped_ledger(fg.ledger, (), (SEED_ALLOWANCE,))
        self.assertIsNot(scoped, fg.ledger)

        ref_agent = fg.entities.ref(User, user_id="u-agent-late")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        ref_observed = fg.entities.ref(User, user_id="u-observed-late")
        observed_id = fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)

        self.assertIsNone(scoped.get_claim(agent_id))
        self.assertNotIn(agent_id, [c.asrt_id for c in scoped.claims])
        self.assertEqual(scoped.find_meta(asrt_id=agent_id), [])
        self.assertIsNotNone(scoped.get_claim(observed_id))
        self.assertIn(observed_id, [c.asrt_id for c in scoped.claims])


class AllowanceEngineExportGateTests(unittest.TestCase):
    """Ausgeschlossene Claims erreichen das Engine-Paket/Programm nicht (Export-Ebene)."""

    def _seeded(self) -> tuple[SDKStore, str, str]:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref_observed = fg.entities.ref(User, user_id="u-observed")
        observed_id = fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        return fg, observed_id, agent_id

    def test_souffle_export_omits_disallowed_claims(self) -> None:
        fg, observed_id, agent_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        self.assertIsNot(view, fg.store)
        with TemporaryDirectory() as tmp:
            scoped_dir = Path(tmp) / "scoped"
            souffle_package.export_package(view, scoped_dir, souffle_package.ExportOptions())
            claim_rows = (scoped_dir / "facts" / "claim.facts").read_text(encoding="utf-8")
            meta_rows = (scoped_dir / "facts" / "meta_str.facts").read_text(encoding="utf-8")
            arg_rows = (scoped_dir / "facts" / "claim_arg.facts").read_text(encoding="utf-8")
            self.assertIn(observed_id, claim_rows)
            self.assertNotIn(agent_id, claim_rows)
            self.assertNotIn(agent_id, meta_rows)
            self.assertNotIn(agent_id, arg_rows)

            raw_dir = Path(tmp) / "raw"
            souffle_package.export_package(fg.store, raw_dir, souffle_package.ExportOptions())
            raw_rows = (raw_dir / "facts" / "claim.facts").read_text(encoding="utf-8")
            self.assertIn(agent_id, raw_rows)

    def test_problog_export_omits_disallowed_claims(self) -> None:
        fg, observed_id, agent_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        rule_spec = {
            "derivation_id": "drv.allow.problog",
            "version": "v1",
            "target_pred_id": "user:tag",
            "head_vars": ["$u", "$t"],
            "where": [("pred", SEED_PRED, ["$u", "$t"])],
            "query_pred": "answer",
        }
        with TemporaryDirectory() as tmp:
            scoped_path = Path(tmp) / "scoped.pl"
            export_problog(view, rule_spec, scoped_path)
            program = scoped_path.read_text(encoding="utf-8")
            self.assertIn(observed_id, program)
            self.assertNotIn(agent_id, program)


class AllowanceEngineEvaluatorSeamTests(unittest.TestCase):
    """Produktions-Naht: Store.evaluate_engine reicht die allowance-scoped Store-View durch."""

    def test_engine_evaluator_receives_allowance_scoped_store(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref_observed = fg.entities.ref(User, user_id="u-observed")
        observed_id = fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        agent_id = fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)

        observed: dict[str, object] = {}

        def probe_evaluator(store, **kwargs):  # noqa: ANN001, ANN003
            observed["disallowed_claim"] = store.ledger.get_claim(agent_id)
            observed["allowed_claim"] = store.ledger.get_claim(observed_id)
            observed["claim_ids"] = [c.asrt_id for c in store.ledger.claims]
            return []

        fg.store.set_engine_evaluator(probe_evaluator)
        candidates = fg.eval.evaluate_candidates(_tag_inference("inf.allow.seam"), engine="souffle")
        self.assertEqual(candidates, [])
        self.assertIn("claim_ids", observed)
        self.assertIsNone(observed["disallowed_claim"])
        self.assertIsNotNone(observed["allowed_claim"])
        self.assertNotIn(agent_id, observed["claim_ids"])
        self.assertIn(observed_id, observed["claim_ids"])


class AllowanceDerivationCheckGateTests(unittest.TestCase):
    """Nativer derivation-check nutzt dieselbe Praemissenmenge wie evaluate."""

    def test_native_check_matches_allowance(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref_agent = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref_agent, "vip", meta=AGENT_META)
        failed = check_derivation_binding(
            CheckRequest(plan=_check_plan(), binding=(("$u", ref_agent),), engine="native"),
            store=fg.store,
        )
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.matched_count, 0)

        ref_observed = fg.entities.ref(User, user_id="u-observed")
        fg.fields.set(User.tag_seed, ref_observed, "vip", meta=OBSERVED_META)
        passed = check_derivation_binding(
            CheckRequest(plan=_check_plan(), binding=(("$u", ref_observed),), engine="native"),
            store=fg.store,
        )
        self.assertEqual(passed.status, "passed")


class AllowanceProofFrameRecheckTests(unittest.TestCase):
    """Re-Check konsistent zur Erst-Auswertung unter der Allowance."""

    def test_recheck_consistent_with_allowance(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref = fg.entities.ref(User, user_id="u-1")
        support_id = fg.fields.set(User.tag_seed, ref, "vip", meta=OBSERVED_META)

        candidates = fg.eval.evaluate_candidates(_tag_inference("inf.allow.recheck"), engine="native")
        self.assertEqual(len(candidates), 1)
        receipt = fg.store._lookup_support_artifact(candidates[0].support_digest)
        self.assertIsNotNone(receipt)
        assert receipt is not None

        request = ProofFrameRecheckRequest(support_artifact=receipt, overlay=FactOverlay())
        before = recheck_proof_frame(request, store=fg.store)
        self.assertEqual(before.status, "still_valid")

        # Umklassifizierung der Stuetze AUS der zugelassenen Menge.
        fg.ledger.append_meta(
            [MetaRow(asrt_id=support_id, key="provenance_class", kind="str", value="claimed_by_agent")]
        )
        after = recheck_proof_frame(request, store=fg.store)
        self.assertEqual(after.status, "invalidated")
        self.assertEqual(
            fg.eval.evaluate_candidates(_tag_inference("inf.allow.recheck.after"), engine="native"),
            [],
        )


class AllowanceReadPathsUntouchedTests(unittest.TestCase):
    """Lese-/Query-Pfade ausserhalb der Auswertung bleiben ungefiltert."""

    def test_disallowed_fact_stays_visible_on_read_paths(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_allowances([SEED_ALLOWANCE])
        ref = fg.entities.ref(User, user_id="u-agent")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=AGENT_META)

        record = fg.assertions.by_id(asrt_id)
        self.assertIsNotNone(record)
        self.assertTrue(record.is_active)
        self.assertEqual(fg.fields.get(User.tag_seed, ref), "vip")
        snapshot = fg.entities.get(User, user_id="u-agent")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.tag_seed, "vip")


if __name__ == "__main__":
    unittest.main()
