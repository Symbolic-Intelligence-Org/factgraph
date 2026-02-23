"""Data provider abstraction and CSV implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal, Iterable
import csv

from symir.errors import ProviderError
from symir.ir.fact_schema import FactSchema, FactView, PredicateSchema, Rel
from symir.ir.instance import Instance
from symir.ir.filters import FilterAST, apply_filter
from symir.probability import ProbabilityConfig, resolve_probability
from symir.fact_store.rel_builder import RelBuilder, ROW_PROB_KEY


class DataProvider:
    """Abstract data provider interface."""

    def __init__(self, schema: FactSchema, prob_config: Optional[ProbabilityConfig] = None) -> None:
        self.schema = schema
        self.prob_config = prob_config or ProbabilityConfig()

    def query(
        self, view: FactView | FactSchema | None = None, filt: Optional[FilterAST] = None
    ) -> list[Instance]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class CSVSource:
    schema: PredicateSchema
    file: str
    columns: list[str]
    prob_column: Optional[str] = None


class CSVProvider(DataProvider):
    """CSV-backed data provider."""

    def __init__(
        self,
        schema: FactSchema | FactView,
        base_path: Path,
        sources: list[CSVSource],
        prob_config: Optional[ProbabilityConfig] = None,
        datatype_cast: Literal["none", "coerce", "strict"] = "none",
    ) -> None:
        if not isinstance(schema, (FactSchema, FactView)):
            raise ProviderError(
                "CSVProvider requires FactLayer/FactView from ir.fact_schema (predicate schema), "
                "not the CSV mapping schema. Use symir.ir.fact_schema.FactLayer."
            )
        self._default_view: FactView | None = None
        if isinstance(schema, FactView):
            self._default_view = schema
            schema = schema.schema
        if datatype_cast not in {"none", "coerce", "strict"}:
            raise ProviderError("datatype_cast must be one of: none, coerce, strict.")
        super().__init__(schema=schema, prob_config=prob_config)
        self.base_path = base_path
        self.sources = {source.schema.schema_id: source for source in sources}
        self.datatype_cast = datatype_cast

    def query(
        self, view: FactView | FactSchema | None = None, filt: Optional[FilterAST] = None
    ) -> list[Instance]:
        if view is None:
            view = self._default_view or self.schema
        if isinstance(view, FactView):
            allowed_ids = set(view.schema_ids)
            predicates = view.predicates()
        elif isinstance(view, FactSchema):
            predicates = view.predicates()
            allowed_ids = {p.schema_id for p in predicates}
        else:
            raise ProviderError("CSVProvider requires a FactLayer or FactView for query().")
        if filt is not None:
            filtered = apply_filter(predicates, filt)
            allowed_ids = allowed_ids.intersection({p.schema_id for p in filtered})
        facts: list[Instance] = []
        for schema_id in allowed_ids:
            pred_schema = self.schema.get(schema_id)
            if pred_schema is None:
                raise ProviderError(f"Unknown predicate schema_id: {schema_id}")
            if schema_id not in self.sources:
                raise ProviderError(
                    "Missing CSV source mapping for "
                    f"schema_id: {schema_id} (name={pred_schema.name})."
                )
            source = self.sources[schema_id]
            facts.extend(self._load_source(pred_schema, source))
        return facts

    def read_rows(
        self,
        source: CSVSource,
        *,
        maps: Optional[dict[str, str]] = None,
        prob_context: Optional[str] = None,
    ) -> list[dict[str, object]]:
        """Read CSV rows into dicts keyed by logical column names.

        `maps` maps logical column names to CSV column names.
        Probability values are stored under ROW_PROB_KEY.
        """
        path = (self.base_path / source.file).resolve()
        if not path.exists():
            raise ProviderError(f"CSV file not found: {path}")
        rows: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ProviderError(f"CSV file has no header: {path}")
            raw_fieldnames = list(reader.fieldnames)
            normalized_fieldnames = [name.strip() for name in raw_fieldnames]
            fieldname_map = dict(zip(raw_fieldnames, normalized_fieldnames))

            mapped_columns = [
                (maps.get(col, col) if maps else col)
                for col in source.columns
            ]
            missing = [col for col in mapped_columns if col not in normalized_fieldnames]
            if missing:
                raise ProviderError(f"CSV file {path} missing columns: {missing}")

            prob_col = source.prob_column
            mapped_prob_col = None
            if prob_col:
                mapped_prob_col = maps.get(prob_col, prob_col) if maps else prob_col
            prob_available = (
                mapped_prob_col in normalized_fieldnames if mapped_prob_col else False
            )

            for idx, row in enumerate(reader, start=2):
                normalized_row = {
                    fieldname_map[key]: (value.strip() if isinstance(value, str) else value)
                    for key, value in row.items()
                }
                row_out: dict[str, object] = {}
                for logical_col, actual_col in zip(source.columns, mapped_columns):
                    value = self._coerce_value(
                        normalized_row.get(actual_col),
                        path,
                        idx,
                        actual_col,
                        datatype=None,
                    )
                    row_out[logical_col] = value
                prob_raw = None
                if mapped_prob_col and prob_available:
                    prob_raw = normalized_row.get(mapped_prob_col)
                prob = resolve_probability(
                    self._maybe_float(prob_raw),
                    default_value=self.prob_config.default_fact_prob,
                    policy=self.prob_config.missing_prob_policy,
                    context=prob_context or f"row {idx}",
                )
                row_out[ROW_PROB_KEY] = prob
                rows.append(row_out)
        return rows

    def build_relations(
        self,
        *,
        builder: RelBuilder,
        facts: Iterable[Instance],
        source: CSVSource,
        maps: Optional[dict[str, str]] = None,
    ) -> list[Instance]:
        """Build rel instances by matching facts against CSV rows."""
        if not isinstance(builder.rel, Rel):
            raise ProviderError("RelBuilder must be constructed with a Rel schema.")
        if builder.rel.schema_id != source.schema.schema_id:
            raise ProviderError("CSVSource schema does not match RelBuilder rel schema_id.")
        rows = self.read_rows(
            source,
            maps=maps,
            prob_context=f"rel {builder.rel.name}",
        )
        return builder.build(
            facts=facts,
            rows=rows,
            registry=self.schema,
            datatype_cast=self.datatype_cast,
        )

    def _load_source(self, pred_schema: PredicateSchema, source: CSVSource) -> list[Instance]:
        path = (self.base_path / source.file).resolve()
        if not path.exists():
            raise ProviderError(f"CSV file not found: {path}")
        if len(source.columns) != pred_schema.arity:
            raise ProviderError(
                f"CSV column mapping arity mismatch for {pred_schema.name}: expected {pred_schema.arity}"
            )
        results: list[Instance] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ProviderError(f"CSV file has no header: {path}")
            raw_fieldnames = list(reader.fieldnames)
            normalized_fieldnames = [name.strip() for name in raw_fieldnames]
            fieldname_map = dict(zip(raw_fieldnames, normalized_fieldnames))
            missing = [c for c in source.columns if c not in normalized_fieldnames]
            if missing:
                raise ProviderError(f"CSV file {path} missing columns: {missing}")
            prob_available = source.prob_column in normalized_fieldnames if source.prob_column else False
            for idx, row in enumerate(reader, start=2):
                normalized_row = {
                    fieldname_map[key]: (value.strip() if isinstance(value, str) else value)
                    for key, value in row.items()
                }
                try:
                    terms: dict[str, object] = {}
                    for col, arg_spec in zip(source.columns, pred_schema.signature):
                        value = self._coerce_value(
                            normalized_row.get(col),
                            path,
                            idx,
                            col,
                            datatype=arg_spec.datatype,
                        )
                        if arg_spec.name is None:
                            raise ProviderError(
                                f"Predicate {pred_schema.name} has unnamed argument at column {col}."
                            )
                        terms[arg_spec.name] = value
                    prob = None
                    if source.prob_column:
                        prob_raw = normalized_row.get(source.prob_column) if prob_available else None
                        prob = resolve_probability(
                            self._maybe_float(prob_raw),
                            default_value=self.prob_config.default_fact_prob,
                            policy=self.prob_config.missing_prob_policy,
                            context=f"fact {pred_schema.name} row {idx}",
                        )
                    else:
                        prob = resolve_probability(
                            None,
                            default_value=self.prob_config.default_fact_prob,
                            policy=self.prob_config.missing_prob_policy,
                            context=f"fact {pred_schema.name} row {idx}",
                        )
                    results.append(Instance(schema=pred_schema, terms=terms, prob=prob))
                except ProviderError:
                    raise
                except Exception as exc:
                    raise ProviderError(f"Error in {path} row {idx}: {exc}") from exc
        return results

    def _coerce_value(
        self,
        raw: Optional[str],
        path: Path,
        row: int,
        col: str,
        *,
        datatype: Optional[str] = None,
    ) -> object:
        if raw is None:
            raise ProviderError(f"Missing value in {path} row {row} column {col}")
        value = raw.strip() if isinstance(raw, str) else str(raw)
        if value == "":
            raise ProviderError(f"Empty value in {path} row {row} column {col}")
        if self.datatype_cast == "none":
            return value
        if not datatype:
            if self.datatype_cast == "strict":
                raise ProviderError(
                    f"Missing datatype for {path} row {row} column {col} in strict mode."
                )
            return value
        dtype = datatype.strip().lower()
        if dtype == "string":
            return value
        if dtype == "int":
            try:
                return int(value)
            except ValueError as exc:
                if self.datatype_cast == "strict":
                    raise ProviderError(
                        f"Invalid int in {path} row {row} column {col}: {value}"
                    ) from exc
                return value
        if dtype == "float":
            try:
                return float(value)
            except ValueError as exc:
                if self.datatype_cast == "strict":
                    raise ProviderError(
                        f"Invalid float in {path} row {row} column {col}: {value}"
                    ) from exc
                return value
        if dtype == "bool":
            lowered = value.lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            if self.datatype_cast == "strict":
                raise ProviderError(
                    f"Invalid bool in {path} row {row} column {col}: {value}"
                )
            return value
        if self.datatype_cast == "strict":
            raise ProviderError(
                f"Unsupported datatype '{datatype}' in {path} row {row} column {col}."
            )
        return value

    def _maybe_float(self, raw: Optional[str]) -> Optional[float]:
        if raw is None:
            return None
        if isinstance(raw, str) and raw.strip() == "":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise ProviderError(f"Invalid probability value: {raw}")
