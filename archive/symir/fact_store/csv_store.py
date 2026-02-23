"""CSV-backed fact storage and loading."""

from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Iterable, Optional

from symir.errors import FactStoreError
from symir.ir.schema import FactSchema, FactNodeDef, FactRelationDef
from symir.ir.types import Const, IRAtom

DEFAULT_PROB_VALUE = 1.0

@dataclass(frozen=True)
class CsvFactStore:
    """Load fact predicates from CSV files according to a schema."""

    schema: FactSchema
    base_path: Path

    def load_facts(self) -> list[IRAtom]:
        """Load all facts defined in the schema into IR atoms."""

        facts: list[IRAtom] = []
        for node in self.schema.nodes.values():
            facts.extend(self._load_node(node))
        for rel in self.schema.relations.values():
            facts.extend(self._load_relation(rel))
        return facts

    def _load_node(self, node: FactNodeDef) -> list[IRAtom]:
        return self._load_csv(
            node.file,
            required_columns=[node.column],
            prob_column=node.prob_column or DEFAULT_PROB_VALUE,
            predicate_name=node.name,
            arity=1,
        )

    def _load_relation(self, rel: FactRelationDef) -> list[IRAtom]:
        return self._load_csv(
            rel.file,
            required_columns=list(rel.columns),
            prob_column=rel.prob_column or DEFAULT_PROB_VALUE,
            predicate_name=rel.name,
            arity=2,
        )

    def _load_csv(
        self,
        file: str,
        required_columns: list[str],
        prob_column: Optional[str],
        predicate_name: str,
        arity: int,
    ) -> list[IRAtom]:
        path = (self.base_path / file).resolve()
        if not path.exists():
            raise FactStoreError(f"CSV file not found: {path}")
        atoms: list[IRAtom] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise FactStoreError(f"CSV file has no header: {path}")
            raw_fieldnames = list(reader.fieldnames)
            normalized_fieldnames = [name.strip() for name in raw_fieldnames]
            fieldname_map = dict(zip(raw_fieldnames, normalized_fieldnames))
            missing_cols = [c for c in required_columns if c not in normalized_fieldnames]
            if missing_cols:
                raise FactStoreError(
                    f"CSV file {path} is missing columns: {missing_cols}"
                )
            prob_available = prob_column in normalized_fieldnames if prob_column else False
            for idx, row in enumerate(reader, start=2):
                try:
                    normalized_row = {
                        fieldname_map[key]: (value.strip() if isinstance(value, str) else value)
                        for key, value in row.items()
                    }
                    terms = [
                        self._coerce_value(normalized_row.get(col), path, idx, col)
                        for col in required_columns
                    ]
                    prob = None
                    if prob_column:
                        prob_raw = normalized_row.get(prob_column) if prob_available else None
                        prob = self._coerce_prob_with_default(prob_raw, path, idx, prob_column)
                    predicate = self.schema.predicate_ref(predicate_name)
                    atoms.append(IRAtom(predicate=predicate, terms=[Const(v) for v in terms], prob=prob))
                except FactStoreError:
                    raise
                except Exception as exc:  # pragma: no cover - safeguard
                    raise FactStoreError(
                        f"Unexpected error in {path} at row {idx}: {exc}"
                    ) from exc
        return atoms

    def _coerce_value(self, raw: Optional[str], path: Path, row: int, col: str):
        if raw is None:
            raise FactStoreError(f"Missing value in {path} row {row} column {col}")
        value = raw.strip()
        if value == "":
            raise FactStoreError(f"Empty value in {path} row {row} column {col}")
        if value.isdigit():
            return int(value)
        try:
            float_value = float(value)
            return float_value
        except ValueError:
            return value

    def _coerce_prob(self, value: object, path: Path, row: int, col: str) -> float:
        try:
            prob = float(value)
        except (TypeError, ValueError):
            raise FactStoreError(
                f"Invalid probability in {path} row {row} column {col}: {value}"
            )
        if not (0.0 <= prob <= 1.0):
            raise FactStoreError(
                f"Probability out of range in {path} row {row} column {col}: {value}"
            )
        return prob

    def _coerce_prob_with_default(
        self, raw: object | None, path: Path, row: int, col: str
    ) -> float:
        if raw is None:
            return DEFAULT_PROB_VALUE
        if isinstance(raw, str) and raw.strip() == "":
            return DEFAULT_PROB_VALUE
        return self._coerce_prob(raw, path, row, col)
