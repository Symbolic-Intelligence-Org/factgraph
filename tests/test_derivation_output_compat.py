from __future__ import annotations

from dataclasses import fields
import pickle
import unittest

from factgraph.core import CandidateSet
from factgraph.core.derivation.candidates import (
    DerivationOutput,
    make_candidate,
    make_derivation_output,
)


class DerivationOutputCompatibilityTests(unittest.TestCase):
    def _kwargs(self) -> dict[str, object]:
        return {
            "derivation_id": "rule:adult",
            "derivation_version": "1",
            "run_id": "run-1",
            "target": "person:adult",
            "key_terms": [("string", "person:adult"), ("entity_ref", "idref_v1:person:test")],
            "payload": {
                "pred_id": "person:adult",
                "terms": [{"kind": "entity_ref", "value": "idref_v1:person:test"}],
            },
            "support_digest": f"sha256:{'0' * 64}",
            "support_kind": "engine_no_witness",
            "generated_at": 1,
        }

    def test_legacy_name_is_direct_alias(self) -> None:
        self.assertIs(CandidateSet, DerivationOutput)

        output = make_derivation_output(**self._kwargs())
        self.assertIsInstance(output, CandidateSet)
        self.assertIsInstance(output, DerivationOutput)

    def test_legacy_factory_preserves_identity_and_content(self) -> None:
        canonical = make_derivation_output(**self._kwargs())
        legacy = make_candidate(**self._kwargs())

        self.assertEqual(legacy, canonical)
        self.assertEqual(legacy.candidate_id, canonical.candidate_id)
        self.assertEqual(legacy.candidate_key, canonical.candidate_key)
        self.assertEqual(legacy.payload, canonical.payload)
        self.assertEqual(
            [field.name for field in fields(legacy)],
            [field.name for field in fields(canonical)],
        )

    def test_current_output_remains_pickle_roundtrippable(self) -> None:
        output = make_derivation_output(**self._kwargs())
        restored = pickle.loads(pickle.dumps(output))

        self.assertIs(type(restored), DerivationOutput)
        self.assertEqual(restored, output)

    def test_legacy_candidate_set_pickle_global_resolves_through_alias(self) -> None:
        output = make_derivation_output(**self._kwargs())
        current_global = b"factgraph.core.derivation.candidates\nDerivationOutput\n"
        legacy_global = b"factgraph.core.derivation.candidates\nCandidateSet\n"
        serialized = pickle.dumps(output, protocol=0)
        self.assertIn(current_global, serialized)

        restored = pickle.loads(serialized.replace(current_global, legacy_global))

        self.assertIs(type(restored), DerivationOutput)
        self.assertIsInstance(restored, CandidateSet)
        self.assertEqual(restored, output)


if __name__ == "__main__":
    unittest.main()
