"""Gates for the per-predicate premise blocklist (Block E of the accreditation run).

The complement of ``PredicatePremiseAllowance``: for a configured predicate, an
assertion whose meta ``key`` last-value IS in the predicate's ``blocked_values``
is inadmissible as a premise (default-admit: a missing/unblocked value stays
visible). Independent of the allowance dimension and OR-combined with it and the
global exclusion. Models the accreditation revocation: revoking the binding
``"{source_id}:{source_name}"`` for a property lands that binding in the block
list of that property's predicate, so its already-written ``accredited`` facts
stop premising derivations WITHOUT rewriting history — and a DIFFERENT source_id
(a different binding) is untouched.

All tests run against real stores — SDKStore with a compiled schema, the real
SQLite-backed Ledger, native evaluation, and the real souffle/problog export
code paths. No mocks. As in the allowance/exclusion suites, the souffle binary /
problog / pyreason backends are absent here, so the engine gates are tested at
EXPORT level and at the evaluator seam.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import factgraph.adapters.souffle.package as souffle_package
from factgraph.adapters.problog.problog_export import export_problog
from factgraph.core.store.ledger import MetaRow
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    normalize_premise_blocks,
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
    other_seed: str = Field()
    blocked: str = Field()
    tag: str = Field()


SEED_PRED = "user:tag_seed"
OTHER_PRED = "user:other_seed"
BLOCKED_PRED = "user:blocked"

BINDING_A = "srcA:invoice_verifier"  # revoked binding
BINDING_B = "srcB:invoice_verifier"  # same source_name, different source_id -> untouched

# Block on the seed predicate: assertions whose origin_binding is the revoked
# BINDING_A are inadmissible there. Everything else on that predicate is admitted.
SEED_BLOCK = PredicatePremiseBlock(
    pred_id=SEED_PRED, key="origin_binding", blocked_values=frozenset({BINDING_A})
)

BOUND_A_META = {"provenance_class": "accredited", "origin_binding": BINDING_A}
BOUND_B_META = {"provenance_class": "accredited", "origin_binding": BINDING_B}
NOBIND_META = {"provenance_class": "observed"}  # no origin_binding


def _tag_inference(inf_id: str = "inf.block.tag") -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred(SEED_PRED, u, t)], id="seed")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _other_inference(inf_id: str = "inf.block.other") -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred(OTHER_PRED, u, t)], id="other")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _negation_inference(inf_id: str = "inf.block.neg") -> Inference:
    with sdk_vars("u", "t", "b") as (u, t, b):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred(SEED_PRED, u, t), Not([Pred(BLOCKED_PRED, u, b)])], id="main")],
            emits=EmitSpec("user:tag", [u, t]),
        )


def _refs(candidates: list) -> list[str]:
    return sorted(cs.payload["terms"][0]["value"] for cs in candidates)


class BlockConfigTests(unittest.TestCase):
    def test_block_validates_and_normalizes(self) -> None:
        block = PredicatePremiseBlock(
            pred_id="p", key="k", blocked_values=["a", "b"]  # type: ignore[arg-type]
        )
        self.assertEqual(block.blocked_values, frozenset({"a", "b"}))
        for bad in (
            lambda: PredicatePremiseBlock(pred_id="", key="k", blocked_values=frozenset({"a"})),
            lambda: PredicatePremiseBlock(pred_id="p", key="", blocked_values=frozenset({"a"})),
            lambda: PredicatePremiseBlock(pred_id="p", key="k", blocked_values=frozenset()),
            lambda: PredicatePremiseBlock(pred_id="p", key="k", blocked_values="a"),  # type: ignore[arg-type]
        ):
            with self.assertRaises(ValueError):
                bad()

    def test_normalize_rejects_bad_items_and_duplicate_pred(self) -> None:
        with self.assertRaises(ValueError):
            normalize_premise_blocks(["nope"])  # type: ignore[list-item]
        with self.assertRaises(ValueError):
            normalize_premise_blocks(
                [
                    PredicatePremiseBlock(pred_id="p", key="k", blocked_values=frozenset({"a"})),
                    PredicatePremiseBlock(pred_id="p", key="k", blocked_values=frozenset({"b"})),
                ]
            )

    def test_zero_config_introduces_no_wrapper(self) -> None:
        # Empty blocklists are byte-identical: the base ledger/store is returned.
        fg = SDKStore([User])
        self.assertEqual(fg.store.premise_blocks, ())
        self.assertIs(premise_scoped_store_view(fg.store), fg.store)
        self.assertIs(premise_scoped_ledger(fg.ledger, (), (), ()), fg.ledger)
        self.assertIs(premise_scoped_ledger(fg.ledger, None, None, None), fg.ledger)

    def test_configured_block_always_wraps(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        self.assertIsNot(premise_scoped_store_view(fg.store), fg.store)

    def test_sdk_setter_roundtrip_and_none_disables(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        self.assertEqual(fg.premise_blocks, (SEED_BLOCK,))
        fg.set_premise_blocks(None)
        self.assertEqual(fg.premise_blocks, ())

    def test_sdk_setter_rejects_invalid(self) -> None:
        fg = SDKStore([User])
        with self.assertRaises(SDKStoreError):
            fg.set_premise_blocks(["nope"])  # type: ignore[list-item]


class BlockSupportGateTests(unittest.TestCase):
    def test_blocked_binding_does_not_support_others_do(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref_a = fg.entities.ref(User, user_id="u-bound-a")  # revoked binding -> blocked
        fg.fields.set(User.tag_seed, ref_a, "vip", meta=BOUND_A_META)
        ref_b = fg.entities.ref(User, user_id="u-bound-b")  # different source_id -> admitted
        fg.fields.set(User.tag_seed, ref_b, "vip", meta=BOUND_B_META)
        ref_none = fg.entities.ref(User, user_id="u-nobind")  # no binding -> admitted
        fg.fields.set(User.tag_seed, ref_none, "vip", meta=NOBIND_META)

        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_refs(candidates), sorted([ref_b, ref_none]))

    def test_block_is_per_predicate(self) -> None:
        # The same blocked binding on a DIFFERENT predicate still supports —
        # revoke on (source, property) never touches other properties.
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref = fg.entities.ref(User, user_id="u-1")
        fg.fields.set(User.tag_seed, ref, "vip", meta=BOUND_A_META)     # blocked here
        fg.fields.set(User.other_seed, ref, "vip", meta=BOUND_A_META)   # untouched there

        self.assertEqual(fg.eval.evaluate_candidates(_tag_inference(), engine="native"), [])
        self.assertEqual(
            _refs(fg.eval.evaluate_candidates(_other_inference(), engine="native")), [ref]
        )

    def test_different_source_id_same_name_stays_admitted(self) -> None:
        # Explicit binding-granularity gate: only BINDING_A is blocked; the same
        # source_name over source_id B carries BINDING_B and is admitted.
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref_b = fg.entities.ref(User, user_id="u-b")
        fg.fields.set(User.tag_seed, ref_b, "vip", meta=BOUND_B_META)
        self.assertEqual(
            _refs(fg.eval.evaluate_candidates(_tag_inference(), engine="native")), [ref_b]
        )


class BlockNegationGateTests(unittest.TestCase):
    def test_blocked_blocker_does_not_block(self) -> None:
        # Symmetric: a blocked-binding blocker can neither support nor block.
        fg = SDKStore([User])
        fg.set_premise_blocks(
            [PredicatePremiseBlock(pred_id=BLOCKED_PRED, key="origin_binding",
                                   blocked_values=frozenset({BINDING_A}))]
        )
        ref_free = fg.entities.ref(User, user_id="u-free")
        ref_blk_ok = fg.entities.ref(User, user_id="u-blk-ok")     # admitted blocker
        ref_blk_bad = fg.entities.ref(User, user_id="u-blk-bad")   # blocked-binding blocker
        for ref in (ref_free, ref_blk_ok, ref_blk_bad):
            fg.fields.set(User.tag_seed, ref, "vip", meta=NOBIND_META)
        fg.fields.set(User.blocked, ref_blk_ok, "yes", meta=BOUND_B_META)   # admitted -> blocks
        fg.fields.set(User.blocked, ref_blk_bad, "yes", meta=BOUND_A_META)  # blocked -> no block

        candidates = fg.eval.evaluate_candidates(_negation_inference(), engine="native")
        self.assertEqual(_refs(candidates), sorted([ref_free, ref_blk_bad]))


class BlockIndependenceTests(unittest.TestCase):
    """Block + Allowance auf demselben Praedikat: eine Assertion muss BEIDE bestehen."""

    def test_block_and_allowance_compose(self) -> None:
        fg = SDKStore([User])
        # Allowance: nur accredited zulassen. Block: BINDING_A (widerrufen) sperren.
        fg.set_premise_allowances(
            [PredicatePremiseAllowance(pred_id=SEED_PRED, key="provenance_class",
                                       allowed_values=frozenset({"accredited"}))]
        )
        fg.set_premise_blocks([SEED_BLOCK])
        # accredited + BINDING_A -> vom Block ausgeschlossen (widerrufen)
        r1 = fg.entities.ref(User, user_id="u-acc-a")
        fg.fields.set(User.tag_seed, r1, "vip", meta=BOUND_A_META)
        # accredited + BINDING_B -> beide bestanden -> stuetzt
        r2 = fg.entities.ref(User, user_id="u-acc-b")
        fg.fields.set(User.tag_seed, r2, "vip", meta=BOUND_B_META)
        # observed + BINDING_B -> von der Allowance ausgeschlossen (nicht accredited)
        r3 = fg.entities.ref(User, user_id="u-obs-b")
        fg.fields.set(User.tag_seed, r3, "vip", meta={"provenance_class": "observed", "origin_binding": BINDING_B})

        candidates = fg.eval.evaluate_candidates(_tag_inference(), engine="native")
        self.assertEqual(_refs(candidates), [r2])

    def test_global_exclusion_still_wins(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_exclusions(
            [MetaExclusion(key="provenance_class", values=frozenset({"claimed_by_agent"}))]
        )
        fg.set_premise_blocks([SEED_BLOCK])
        ref = fg.entities.ref(User, user_id="u-agent")
        fg.fields.set(User.tag_seed, ref, "vip",
                      meta={"provenance_class": "claimed_by_agent", "origin_binding": BINDING_B})
        # Not blocked (BINDING_B), but the global exclusion removes it anyway.
        self.assertEqual(fg.eval.evaluate_candidates(_tag_inference(), engine="native"), [])


class BlockReclassificationTests(unittest.TestCase):
    """Last-wins: eine neue origin_binding-Zeile bewegt IN/AUS der gesperrten Menge."""

    def test_rebinding_out_of_block_restores_admissibility(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=BOUND_A_META)  # blocked
        self.assertEqual(fg.eval.evaluate_candidates(_tag_inference("a.before"), engine="native"), [])
        # Config-Seite: Sperre entfernen -> wieder zugelassen.
        fg.set_premise_blocks(None)
        self.assertEqual(
            _refs(fg.eval.evaluate_candidates(_tag_inference("a.after"), engine="native")), [ref]
        )

    def test_meta_rebind_last_wins(self) -> None:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta=BOUND_A_META)  # blocked
        self.assertEqual(fg.eval.evaluate_candidates(_tag_inference("m.before"), engine="native"), [])
        # Eine neue origin_binding-Meta-Zeile (last-wins) auf ein nicht gesperrtes Binding.
        fg.ledger.append_meta(
            [MetaRow(asrt_id=asrt_id, key="origin_binding", kind="str", value=BINDING_B)]
        )
        self.assertEqual(
            _refs(fg.eval.evaluate_candidates(_tag_inference("m.after"), engine="native")), [ref]
        )


class BlockLiveVisibilityTests(unittest.TestCase):
    def test_fact_written_after_wrapper_is_filtered_live(self) -> None:
        fg = SDKStore([User])
        scoped = premise_scoped_ledger(fg.ledger, (), (), (SEED_BLOCK,))
        self.assertIsNot(scoped, fg.ledger)
        ref_a = fg.entities.ref(User, user_id="u-a-late")
        a_id = fg.fields.set(User.tag_seed, ref_a, "vip", meta=BOUND_A_META)
        ref_b = fg.entities.ref(User, user_id="u-b-late")
        b_id = fg.fields.set(User.tag_seed, ref_b, "vip", meta=BOUND_B_META)
        self.assertIsNone(scoped.get_claim(a_id))
        self.assertNotIn(a_id, [c.asrt_id for c in scoped.claims])
        self.assertIsNotNone(scoped.get_claim(b_id))


class BlockEngineExportGateTests(unittest.TestCase):
    """Gesperrte Claims erreichen das Engine-Paket/Programm nicht (Export-Ebene)."""

    def _seeded(self) -> tuple[SDKStore, str, str]:
        fg = SDKStore([User])
        fg.set_premise_blocks([SEED_BLOCK])
        ref_b = fg.entities.ref(User, user_id="u-bound-b")
        b_id = fg.fields.set(User.tag_seed, ref_b, "vip", meta=BOUND_B_META)
        ref_a = fg.entities.ref(User, user_id="u-bound-a")
        a_id = fg.fields.set(User.tag_seed, ref_a, "vip", meta=BOUND_A_META)
        return fg, b_id, a_id

    def test_souffle_export_omits_blocked_claims(self) -> None:
        fg, b_id, a_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        self.assertIsNot(view, fg.store)
        with TemporaryDirectory() as tmp:
            scoped_dir = Path(tmp) / "scoped"
            souffle_package.export_package(view, scoped_dir, souffle_package.ExportOptions())
            claim_rows = (scoped_dir / "facts" / "claim.facts").read_text(encoding="utf-8")
            self.assertIn(b_id, claim_rows)
            self.assertNotIn(a_id, claim_rows)
            # Gegenprobe: der ungescopte Store traegt den gesperrten Claim.
            raw_dir = Path(tmp) / "raw"
            souffle_package.export_package(fg.store, raw_dir, souffle_package.ExportOptions())
            self.assertIn(a_id, (raw_dir / "facts" / "claim.facts").read_text(encoding="utf-8"))

    def test_problog_export_omits_blocked_claims(self) -> None:
        fg, b_id, a_id = self._seeded()
        view = premise_scoped_store_view(fg.store)
        rule_spec = {
            "derivation_id": "drv.block.problog",
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
            self.assertIn(b_id, program)
            self.assertNotIn(a_id, program)


if __name__ == "__main__":
    unittest.main()
