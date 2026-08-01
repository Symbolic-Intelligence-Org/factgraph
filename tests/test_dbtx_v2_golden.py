from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from factgraph.core.store.database import DBTX_V2_PREFIX, canonical_bytes_dbtx_v2


_GOLDEN_ROOT = Path(__file__).with_name("golden") / "dbtx_v2"
_FIXTURES = (
    ("assertion_revocation_only.json", frozenset({"assertion", "revocation"})),
    ("append_meta_schema_change.json", frozenset({"append_meta", "schema_change"})),
)


class DbtxV2GoldenTests(unittest.TestCase):
    def test_canonical_bytes_tx_ids_and_head_progression_are_frozen(self) -> None:
        for fixture_name, required_kinds in _FIXTURES:
            with self.subTest(fixture=fixture_name):
                fixture = _load_fixture(fixture_name)
                self.assertEqual(fixture["fixture_version"], 1)

                parent_tx_id: str | None = None
                actual_heads: list[str] = []
                observed_kinds: set[str] = set()

                for transaction in fixture["transactions"]:
                    self.assertEqual(transaction["parent_tx_id"], parent_tx_id)
                    canonical = canonical_bytes_dbtx_v2(
                        parent_tx_id=transaction["parent_tx_id"],
                        schema_digest=transaction["schema_digest"],
                        digest_scheme=transaction["digest_scheme"],
                        tx_seq=transaction["tx_seq"],
                        operations=transaction["operations"],
                    )
                    self.assertTrue(canonical.startswith(DBTX_V2_PREFIX))
                    self.assertEqual(canonical, bytes.fromhex(transaction["canonical_hex"]))

                    tx_id = "tx:" + hashlib.sha256(canonical).hexdigest()
                    self.assertEqual(tx_id, transaction["tx_id"])
                    actual_heads.append(tx_id)
                    parent_tx_id = tx_id
                    observed_kinds.update(op["kind"] for op in transaction["operations"])

                self.assertEqual(actual_heads, fixture["head_progression"])
                self.assertTrue(required_kinds.issubset(observed_kinds))
                if fixture_name == "assertion_revocation_only.json":
                    self.assertTrue(observed_kinds <= {"assertion", "revocation"})


def _load_fixture(name: str) -> dict[str, Any]:
    payload = json.loads((_GOLDEN_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"dbtx_v2 fixture must be an object: {name}")
    return payload


if __name__ == "__main__":
    unittest.main()
