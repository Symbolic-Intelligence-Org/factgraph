"""Gates for the public post-write meta reclassification seam
``fg.assertions.append_meta(asrt_id, key, value)`` (sdk/store.py).

``Ledger.append_meta`` is a deprecated compatibility seam; this SDK method is
the supported public surface consumers use to reclassify an assertion after
the fact (e.g. move it into or out of a premise-admissibility-excluded class).
All tests run against real stores — SDKStore with a compiled schema, the real
SQLite-backed ledger, native evaluation. No mocks.
"""

from __future__ import annotations

import unittest

from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.sdk import (
    Case,
    EmitSpec,
    Inference,
    Pred,
    SDKStore,
    SDKStoreError,
    vars as sdk_vars,
)
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()
    tag: str = Field()


EXCLUSION = MetaExclusion(key="provenance_class", values=frozenset({"claimed_by_agent"}))


def _tag_inference(inf_id: str) -> Inference:
    with sdk_vars("u", "t") as (u, t):
        return Inference(
            id=inf_id,
            version="v1",
            when=[Case([Pred("user:tag_seed", u, t)], id="seed")],
            emits=EmitSpec("user:tag", [u, t]),
        )


class PublicAppendMetaTests(unittest.TestCase):
    def test_append_meta_is_last_wins_and_keeps_history(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(
            User.tag_seed, ref, "vip",
            meta={"source": "agent", "provenance_class": "claimed_by_agent"},
        )

        fg.assertions.append_meta(asrt_id, "provenance_class", "observed")

        # Canonical read resolves last-wins ...
        record = fg.assertions.by_id(asrt_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.meta.raw.get("provenance_class"), "observed")
        # ... and the full history stays auditable, in write order.
        rows = fg.ledger.find_meta(asrt_id=asrt_id, key="provenance_class")
        self.assertEqual([row.value for row in rows], ["claimed_by_agent", "observed"])

    def test_append_meta_reclassification_moves_assertion_across_premise_filter(self) -> None:
        # The exact consumer scenario: an agent-claimed fact is invisible to
        # evaluation; a later public reclassification makes it admissible —
        # same last-wins semantics the filter and the SDK read share.
        fg = SDKStore([User])
        fg.set_premise_exclusions([EXCLUSION])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(
            User.tag_seed, ref, "vip",
            meta={"source": "agent", "provenance_class": "claimed_by_agent"},
        )
        self.assertEqual(
            fg.eval.evaluate_candidates(
                _tag_inference("inf.appendmeta.before"), engine="native"
            ),
            [],
        )

        fg.assertions.append_meta(asrt_id, "provenance_class", "observed")

        candidates = fg.eval.evaluate_candidates(
            _tag_inference("inf.appendmeta.after"), engine="native"
        )
        self.assertEqual(
            sorted(cs.payload["terms"][0]["value"] for cs in candidates), [ref]
        )

    def test_append_meta_scalar_kinds(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta={"source": "t"})
        fg.assertions.append_meta(asrt_id, "k_str", "v")
        fg.assertions.append_meta(asrt_id, "k_bool", True)
        fg.assertions.append_meta(asrt_id, "k_int", 7)
        fg.assertions.append_meta(asrt_id, "k_float", 1.5)
        kinds = {
            row.key: row.kind
            for row in fg.ledger.find_meta(asrt_id=asrt_id)
            if row.key.startswith("k_")
        }
        self.assertEqual(
            kinds, {"k_str": "str", "k_bool": "bool", "k_int": "int", "k_float": "float"}
        )
        raw = fg.assertions.by_id(asrt_id).meta.raw
        self.assertIs(raw["k_bool"], True)
        self.assertEqual(raw["k_int"], 7)

    def test_append_meta_rejects_invalid_input(self) -> None:
        fg = SDKStore([User])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.tag_seed, ref, "vip", meta={"source": "t"})
        with self.assertRaises(SDKStoreError):
            fg.assertions.append_meta("", "k", "v")
        with self.assertRaises(SDKStoreError):
            fg.assertions.append_meta(asrt_id, "", "v")
        with self.assertRaises(SDKStoreError):
            fg.assertions.append_meta(asrt_id, "k", {"not": "scalar"})
        with self.assertRaises(SDKStoreError) as ctx:
            fg.assertions.append_meta("asrt:unknown", "k", "v")
        self.assertEqual(ctx.exception.code, "ASSERTION_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
