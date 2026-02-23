import tempfile
from pathlib import Path
import unittest

from symir.errors import FactStoreError
from symir.fact_store.csv_store import CsvFactStore
from symir.ir.schema import FactSchema


class TestCsvFactStore(unittest.TestCase):
    def test_load_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "people.csv").write_text("name\nAlice\nBob\n", encoding="utf-8")
            (base / "cities.csv").write_text("name\nParis\n", encoding="utf-8")
            (base / "lives_in.csv").write_text(
                "person,city\nAlice,Paris\nBob,Paris\n", encoding="utf-8"
            )
            schema = FactSchema.from_dict(
                {
                    "nodes": {
                        "Person": {"file": "people.csv", "column": "name"},
                        "City": {"file": "cities.csv", "column": "name"},
                    },
                    "relations": {
                        "LivesIn": {
                            "file": "lives_in.csv",
                            "columns": ["person", "city"],
                        }
                    },
                }
            )
            store = CsvFactStore(schema=schema, base_path=base)
            facts = store.load_facts()
            self.assertEqual(len(facts), 5)
            self.assertEqual(facts[0].predicate.name, "Person")
            self.assertEqual(facts[-1].predicate.name, "LivesIn")

    def test_invalid_row_reports_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "people.csv").write_text("name\nAlice\n\"\"\n", encoding="utf-8")
            schema = FactSchema.from_dict(
                {"nodes": {"Person": {"file": "people.csv", "column": "name"}}, "relations": {}}
            )
            store = CsvFactStore(schema=schema, base_path=base)
            with self.assertRaisesRegex(FactStoreError, r"people\.csv.*row 3"):
                store.load_facts()


if __name__ == "__main__":
    unittest.main()
