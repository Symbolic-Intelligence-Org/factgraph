"""Meta-based premise admissibility filtering for rule evaluation.

A configured ``MetaExclusion`` makes every assertion whose meta rows carry
``key`` with a value in ``values`` invisible to rule evaluation: the
assertion can neither support a derivation nor block one through negation.
For evaluation, the assertion does not exist. Key and values are pure
configuration — no consumer vocabulary is hardcoded here.

Scope (deliberate):

- Applied ONLY at the evaluation entrypoints — ``evaluate_store``
  (``core/store/_evaluate.py``; the native projection reads the scoped
  ledger, while souffle / problog / pyreason adapters receive a
  premise-scoped store view from ``Store.evaluate_engine``),
  ``recheck_proof_frame`` (``application/proofframe_runtime.py``), and the
  native leg of ``check_derivation_binding``
  (``application/derivation_check_runtime.py``; the non-native legs inherit
  the filter through ``evaluate_derivation_plans`` -> ``Store.evaluate_engine``).
- Read/query paths outside evaluation (entity views, fact listings, audit,
  history) stay UNFILTERED: excluded assertions remain fully visible there.
- Why-not / overlay diagnosis runtimes stay UNFILTERED by design — they are
  diagnostic read surfaces, not premise sets.
- Accept (``core/store/_accept.py``) stays UNFILTERED: it only consumes
  candidates produced by an already-filtered evaluation, and its ledger
  reads serve candidate_key idempotency dedup, which must see the full
  ledger.

Revocations are treated symmetrically: a revocation whose revoker assertion
carries an excluded meta value is also invisible to evaluation — an
inadmissible retraction can neither remove a fact from the premise set nor
lift a negation blocker. Everywhere outside evaluation the revocation stays
effective.

The ledger wrapper mirrors the full read surface of the production-proven
``_ViewScopedLedger`` (sdk/store.py: claims property, find_claims,
get_claim, find_claim_args, find_meta, find_annotations, revokes,
has_active_revocation, find_revoker, get_ledger_meta) so neither the
souffle export nor the witness reconstruction can leak an excluded claim.
Visibility is snapshotted per wrapper construction; evaluation entrypoints
construct a fresh wrapper per call. Zero-behavior-change contract: with no
exclusions configured (or no matching assertions) ``premise_scoped_ledger``
returns the base ledger object unchanged — no wrapper is introduced.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from factgraph.core.store.ledger import (
    AnnotationRow,
    Claim,
    ClaimArg,
    Ledger,
    MetaRow,
    Revokes,
)

_READ_ONLY_MESSAGE = (
    "premise-filtered evaluation ledger view is read-only; "
    "writes must go to the base ledger"
)


@dataclass(frozen=True)
class MetaExclusion:
    """One evaluation exclusion: hide assertions whose meta ``key`` carries a value in ``values``.

    Only string meta values participate in matching; FG free meta keys allow
    scalars, and non-string values never equal a configured string value.
    """

    key: str
    values: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("MetaExclusion.key must be non-empty string")
        if isinstance(self.values, str):
            raise ValueError(
                "MetaExclusion.values must be an iterable of strings, not a single string"
            )
        try:
            values = frozenset(self.values)
        except TypeError as exc:
            raise ValueError("MetaExclusion.values must be an iterable of strings") from exc
        if not values:
            raise ValueError("MetaExclusion.values must be non-empty")
        for value in values:
            if not isinstance(value, str) or not value:
                raise ValueError("MetaExclusion.values entries must be non-empty strings")
        object.__setattr__(self, "values", values)


def normalize_premise_exclusions(
    exclusions: MetaExclusion | Iterable[MetaExclusion] | None,
) -> tuple[MetaExclusion, ...]:
    """Normalize the configuration input to a validated tuple (empty = disabled)."""
    if exclusions is None:
        return ()
    if isinstance(exclusions, MetaExclusion):
        return (exclusions,)
    try:
        normalized = tuple(exclusions)
    except TypeError as exc:
        raise ValueError(
            "premise_exclusions must be MetaExclusion | iterable[MetaExclusion] | None"
        ) from exc
    for item in normalized:
        if not isinstance(item, MetaExclusion):
            raise ValueError(
                f"premise_exclusions entries must be MetaExclusion, got {type(item).__name__}"
            )
    return normalized


def excluded_premise_asrt_ids(
    ledger: Ledger,
    exclusions: tuple[MetaExclusion, ...],
) -> frozenset[str]:
    """Collect asrt_ids carrying an excluded meta value (``ledger.find_meta`` is indexed)."""
    excluded: set[str] = set()
    for exclusion in exclusions:
        for row in ledger.find_meta(key=exclusion.key):
            if isinstance(row.value, str) and row.value in exclusion.values:
                excluded.add(row.asrt_id)
    return frozenset(excluded)


def premise_scoped_ledger(
    ledger: Ledger,
    exclusions: MetaExclusion | Iterable[MetaExclusion] | None,
) -> Ledger:
    """Return ``ledger`` unchanged when no exclusion applies, else a filtered snapshot view."""
    normalized = normalize_premise_exclusions(exclusions)
    if not normalized:
        return ledger
    excluded = excluded_premise_asrt_ids(ledger, normalized)
    if not excluded:
        return ledger
    return _PremiseExcludedLedger(ledger, excluded_asrt_ids=excluded)


class _PremiseExcludedLedger(Ledger):
    """Read-only Ledger view hiding assertions excluded by MetaExclusion config.

    Constructed as a snapshot per evaluation call; it owns no sqlite
    connection (same no-``super().__init__()`` construction pattern as
    ``_ViewScopedLedger`` in sdk/store.py) and overrides the full read
    surface so no evaluate or engine-export path can see an excluded claim.
    """

    def __init__(self, base: Ledger, *, excluded_asrt_ids: frozenset[str]) -> None:
        self._base = base
        self._excluded_asrt_ids = excluded_asrt_ids
        # Snapshot of revocations by non-excluded revokers: an excluded
        # revoker's revocation is invisible to evaluation (symmetric
        # admissibility, see module docstring).
        visible_revokes = [
            row for row in base.revokes if row.revoker_asrt_id not in excluded_asrt_ids
        ]
        self._visible_revokes = visible_revokes
        self._visible_revoked_ids = {row.revoked_asrt_id for row in visible_revokes}
        first_visible_revoker: dict[str, str] = {}
        for row in visible_revokes:
            first_visible_revoker.setdefault(row.revoked_asrt_id, row.revoker_asrt_id)
        self._first_visible_revoker = first_visible_revoker

    def _is_visible(self, asrt_id: str) -> bool:
        return asrt_id not in self._excluded_asrt_ids

    def _filter_claims(self, claims: Iterable[Claim]) -> list[Claim]:
        return [claim for claim in claims if self._is_visible(claim.asrt_id)]

    def get_claim(self, asrt_id: str) -> Claim | None:
        if not self._is_visible(asrt_id):
            return None
        return self._base.get_claim(asrt_id)

    def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
        return self._filter_claims(self._base.find_claims(pred_id=pred_id, e_ref=e_ref))

    def find_claim_args(
        self,
        asrt_id: str | None = None,
        idx: int | None = None,
        tag: str | None = None,
    ) -> list[ClaimArg]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_claim_args(asrt_id=asrt_id, idx=idx, tag=tag)
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def find_meta(
        self,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
    ) -> list[MetaRow]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_meta(asrt_id=asrt_id, key=key, kind=kind)
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def find_annotations(
        self,
        asrt_id: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        key: str | None = None,
    ) -> list[AnnotationRow]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_annotations(
            asrt_id=asrt_id,
            namespace=namespace,
            category=category,
            key=key,
        )
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def has_active_revocation(self, revoked_asrt_id: str) -> bool:
        if not self._is_visible(revoked_asrt_id):
            return False
        return revoked_asrt_id in self._visible_revoked_ids

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        if not self._is_visible(revoked_asrt_id):
            return None
        return self._first_visible_revoker.get(revoked_asrt_id)

    @property
    def claims(self) -> list[Claim]:
        return self._filter_claims(self._base.claims)

    @property
    def claim_args(self) -> list[ClaimArg]:
        return [row for row in self._base.claim_args if self._is_visible(row.asrt_id)]

    @property
    def meta_rows(self) -> list[MetaRow]:
        return [row for row in self._base.meta_rows if self._is_visible(row.asrt_id)]

    @property
    def annotation_rows(self) -> list[AnnotationRow]:
        return [row for row in self._base.annotation_rows if self._is_visible(row.asrt_id)]

    @property
    def revokes(self) -> list[Revokes]:
        return list(self._visible_revokes)

    def get_ledger_meta(self, key: str) -> str | None:
        return self._base.get_ledger_meta(key)

    def _reject_read_only(self) -> None:
        raise RuntimeError(_READ_ONLY_MESSAGE)

    def append_assertion(self, **kwargs: Any) -> Any:
        self._reject_read_only()

    def append_revocation(self, *args: Any, **kwargs: Any) -> Any:
        self._reject_read_only()

    def append_claim(self, claim: Claim) -> None:
        self._reject_read_only()

    def append_claim_args(self, rows: list[ClaimArg]) -> None:
        self._reject_read_only()

    def append_meta(self, rows: list[MetaRow]) -> None:
        self._reject_read_only()

    def append_annotations(self, rows: list[AnnotationRow]) -> None:
        self._reject_read_only()

    def append_revokes(self, row: Revokes) -> None:
        self._reject_read_only()

    def set_ledger_meta(self, key: str, value: str) -> None:
        self._reject_read_only()

    def replace_ledger_meta(self, key: str, value: str) -> None:
        self._reject_read_only()


__all__ = [
    "MetaExclusion",
    "excluded_premise_asrt_ids",
    "normalize_premise_exclusions",
    "premise_scoped_ledger",
]
