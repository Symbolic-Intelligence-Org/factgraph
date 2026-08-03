"""Meta-based premise admissibility filtering for rule evaluation.

A configured ``MetaExclusion`` makes every assertion whose meta ``key``
currently carries a value in ``values`` invisible to rule evaluation: the
assertion can neither support a derivation nor block one through negation.
For evaluation, the assertion does not exist. Keys are closed by the current
Schema IR: only the two decision-pinned built-ins or keys explicitly declared
``premise_eligible=true`` may be configured.

A configured ``PredicatePremiseAllowance`` narrows a SINGLE predicate: for
assertions of that predicate, only those whose meta ``key`` currently carries
a value in ``allowed_values`` stay visible to evaluation (an assertion missing
the key is admitted only if ``absent_ok``). Assertions of any other predicate
are untouched. The two dimensions are OR-combined, so an assertion is
invisible when the global exclusion OR the per-predicate allowance excludes
it, and a global exclusion can never be re-admitted by an allowance. Both are
pure configuration; no consumer vocabulary is hardcoded here.

Visibility semantics (single logic, shared by every projection):

- LAST-WINS per ``(asrt_id, key)``: only the most recent meta row under the
  exclusion key decides through the shared ``Ledger.effective_meta_rows``
  event resolver. A later ``Ledger.append_meta`` reclassification therefore
  moves an assertion INTO or OUT OF the excluded class for evaluation exactly
  as every effective read path reports it.
- LIVE per access: nothing is snapshotted at wrapper construction. A fact
  (or revoker) written or reclassified while an evaluation is running is
  judged the moment it becomes readable — evaluation can never diverge from
  the ledger state it actually reads. Baseline semantics for assertions
  without a configured key are identical to the unfiltered ledger.

Both properties hinge on ``is_premise_excluded`` below and the shared
``(tx_seq, op_ordinal)`` effective-meta ordering guarantee.

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

Revocations are treated symmetrically BY THE GLOBAL ``MetaExclusion`` (which is
predicate-blind): a revocation whose revoker assertion carries an excluded meta
value is also invisible to evaluation — an inadmissible retraction can neither
remove a fact from the premise set nor lift a negation blocker. Everywhere
outside evaluation the revocation stays effective. The per-predicate dimensions
(``PredicatePremiseAllowance`` / ``PredicatePremiseBlock``) key on
``claim.pred_id`` and short-circuit on a revocation record (``get_claim`` ->
``None``), which carries no predicate id — so they structurally cannot make a
*revocation* inadmissible. If a revocation must itself be made inadmissible by a
meta value (e.g. a revoked ``origin_binding``), that has to go through a global
``MetaExclusion``, not a per-predicate allowance/block.

The ledger wrapper mirrors the full read surface of the production-proven
``_ViewScopedLedger`` (sdk/store.py: claims property, find_claims,
get_claim, find_claim_args, find_meta, find_annotations, revokes,
has_active_revocation, find_revoker, get_ledger_meta) so neither the
souffle export nor the witness reconstruction can leak an excluded claim.
Evaluation entrypoints construct a fresh wrapper per call; within one call
the view and witness projections share the same wrapper object.
Zero-behavior-change contract: with no exclusions configured
``premise_scoped_ledger`` returns the base ledger object unchanged — no
wrapper is introduced. With exclusions configured the wrapper is ALWAYS
introduced (even when no assertion currently matches), so live visibility
also covers facts that gain an excluded class only after wrapper
construction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from factgraph.core.schema.meta_policy import require_premise_eligible_meta_key
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


@dataclass(frozen=True)
class PredicatePremiseAllowance:
    """One per-predicate admissibility rule: for assertions of ``pred_id``, admit
    as a premise ONLY those whose meta ``key`` currently carries a value in
    ``allowed_values``.

    An assertion of ``pred_id`` that is missing the ``key`` is admitted only
    when ``absent_ok`` is set (default: excluded, so a declared requirement is
    enforced against class-less legacy facts). Assertions of any other
    predicate are untouched by this rule. Predicate id, key and values are pure
    configuration; only string meta values participate in matching (a
    non-string last value never equals a configured string value, so it counts
    as not-allowed).
    """

    pred_id: str
    key: str
    allowed_values: frozenset[str]
    absent_ok: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.pred_id, str) or not self.pred_id:
            raise ValueError("PredicatePremiseAllowance.pred_id must be non-empty string")
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("PredicatePremiseAllowance.key must be non-empty string")
        if not isinstance(self.absent_ok, bool):
            raise ValueError("PredicatePremiseAllowance.absent_ok must be bool")
        if isinstance(self.allowed_values, str):
            raise ValueError(
                "PredicatePremiseAllowance.allowed_values must be an iterable of strings, "
                "not a single string"
            )
        try:
            values = frozenset(self.allowed_values)
        except TypeError as exc:
            raise ValueError(
                "PredicatePremiseAllowance.allowed_values must be an iterable of strings"
            ) from exc
        if not values:
            raise ValueError("PredicatePremiseAllowance.allowed_values must be non-empty")
        for value in values:
            if not isinstance(value, str) or not value:
                raise ValueError(
                    "PredicatePremiseAllowance.allowed_values entries must be non-empty strings"
                )
        object.__setattr__(self, "allowed_values", values)


@dataclass(frozen=True)
class PredicatePremiseBlock:
    """One per-predicate blocklist: for assertions of ``pred_id``, hide any whose
    meta ``key`` currently carries a value in ``blocked_values``.

    The complement of ``PredicatePremiseAllowance`` and independent of it: an
    allowance narrows to an ALLOWED set on one key (default-deny), a block
    excludes an explicit DENIED set on another key (default-admit). An assertion
    of ``pred_id`` MISSING the key is never blocked (only explicit matches are);
    an assertion of any other predicate is untouched. The two are orthogonal, so
    a predicate can carry both — e.g. allow class ``accredited`` on
    ``provenance_class`` AND block revoked bindings on ``origin_binding`` — and
    an assertion must clear every configured dimension to stay visible.

    Predicate id, key and values are pure configuration; only string meta values
    participate in matching (a non-string last value never equals a configured
    string value, so it is never blocked).
    """

    pred_id: str
    key: str
    blocked_values: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.pred_id, str) or not self.pred_id:
            raise ValueError("PredicatePremiseBlock.pred_id must be non-empty string")
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("PredicatePremiseBlock.key must be non-empty string")
        if isinstance(self.blocked_values, str):
            raise ValueError(
                "PredicatePremiseBlock.blocked_values must be an iterable of strings, "
                "not a single string"
            )
        try:
            values = frozenset(self.blocked_values)
        except TypeError as exc:
            raise ValueError(
                "PredicatePremiseBlock.blocked_values must be an iterable of strings"
            ) from exc
        if not values:
            raise ValueError("PredicatePremiseBlock.blocked_values must be non-empty")
        for value in values:
            if not isinstance(value, str) or not value:
                raise ValueError(
                    "PredicatePremiseBlock.blocked_values entries must be non-empty strings"
                )
        object.__setattr__(self, "blocked_values", values)


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


def normalize_premise_allowances(
    allowances: "PredicatePremiseAllowance | Iterable[PredicatePremiseAllowance] | None",
) -> tuple[PredicatePremiseAllowance, ...]:
    """Normalize the per-predicate allowance input to a validated tuple (empty = disabled).

    Rejects duplicate ``pred_id`` entries: one predicate carries at most one
    allowance rule, so the visibility decision stays unambiguous.
    """
    if allowances is None:
        return ()
    if isinstance(allowances, PredicatePremiseAllowance):
        return (allowances,)
    try:
        normalized = tuple(allowances)
    except TypeError as exc:
        raise ValueError(
            "premise_allowances must be PredicatePremiseAllowance | "
            "iterable[PredicatePremiseAllowance] | None"
        ) from exc
    seen: set[str] = set()
    for item in normalized:
        if not isinstance(item, PredicatePremiseAllowance):
            raise ValueError(
                "premise_allowances entries must be PredicatePremiseAllowance, "
                f"got {type(item).__name__}"
            )
        if item.pred_id in seen:
            raise ValueError(f"premise_allowances has duplicate pred_id {item.pred_id!r}")
        seen.add(item.pred_id)
    return normalized


def normalize_premise_blocks(
    blocks: "PredicatePremiseBlock | Iterable[PredicatePremiseBlock] | None",
) -> tuple[PredicatePremiseBlock, ...]:
    """Normalize the per-predicate blocklist input to a validated tuple (empty = disabled).

    Rejects duplicate ``pred_id`` entries: one predicate carries at most one
    block rule (all its blocked values on one key), so the visibility decision
    stays unambiguous.
    """
    if blocks is None:
        return ()
    if isinstance(blocks, PredicatePremiseBlock):
        return (blocks,)
    try:
        normalized = tuple(blocks)
    except TypeError as exc:
        raise ValueError(
            "premise_blocks must be PredicatePremiseBlock | "
            "iterable[PredicatePremiseBlock] | None"
        ) from exc
    seen: set[str] = set()
    for item in normalized:
        if not isinstance(item, PredicatePremiseBlock):
            raise ValueError(
                "premise_blocks entries must be PredicatePremiseBlock, "
                f"got {type(item).__name__}"
            )
        if item.pred_id in seen:
            raise ValueError(f"premise_blocks has duplicate pred_id {item.pred_id!r}")
        seen.add(item.pred_id)
    return normalized


def validate_premise_configuration(
    schema_ir: Mapping[str, Any],
    exclusions: tuple[MetaExclusion, ...] = (),
    allowances: tuple[PredicatePremiseAllowance, ...] = (),
    blocks: tuple[PredicatePremiseBlock, ...] = (),
) -> None:
    """Close every premise/visibility key against the current schema policy."""

    for item in exclusions:
        require_premise_eligible_meta_key(
            schema_ir, item.key, context="MetaExclusion"
        )
    for item in allowances:
        require_premise_eligible_meta_key(
            schema_ir, item.key, context="PredicatePremiseAllowance"
        )
    for item in blocks:
        require_premise_eligible_meta_key(
            schema_ir, item.key, context="PredicatePremiseBlock"
        )


def is_premise_excluded(
    ledger: Ledger,
    asrt_id: str,
    exclusions: tuple[MetaExclusion, ...],
) -> bool:
    """THE visibility decision — last-wins per exclusion key, read live from ``ledger``.

    Per key only the event with maximal ``(tx_seq, op_ordinal)`` decides,
    through the same resolver used by AssertionMeta and audit as-of replay.
    An UNSET winner is missing. Only string effective values participate in
    matching (FG free meta keys allow scalars; a non-string value never
    matches).

    Cost per call: one indexed dict lookup per configured exclusion.
    """
    for exclusion in exclusions:
        rows = ledger.effective_meta_rows(asrt_id=asrt_id, key=exclusion.key)
        if not rows:
            continue
        last_value = rows[-1].value
        if isinstance(last_value, str) and last_value in exclusion.values:
            return True
    return False


def is_predicate_premise_excluded(
    ledger: Ledger,
    asrt_id: str,
    allowances_by_pred: Mapping[str, PredicatePremiseAllowance],
) -> bool:
    """Per-predicate admissibility — exclude an assertion of a configured predicate
    whose meta ``key`` last-value is not in that predicate's allowed set.

    An assertion of a configured predicate that is MISSING the key is excluded
    unless the predicate's ``absent_ok`` is set. Assertions of predicates NOT
    in the map, and assertions that are not claims (``get_claim`` -> ``None``,
    e.g. a revocation record), are never excluded here. An empty map never
    excludes.

    Last-wins per ``(asrt_id, key)`` mirrors ``is_premise_excluded``: only the
    most recently written meta row under the key decides, so a reclassification
    moves the assertion INTO or OUT OF the allowed set exactly as every read
    path reports it. Only a string last value can be allowed. Cost when
    configured: one claim lookup, plus one indexed meta lookup for assertions
    of a configured predicate.
    """
    if not allowances_by_pred:
        return False
    claim = ledger.get_claim(asrt_id)
    if claim is None:
        return False
    allowance = allowances_by_pred.get(claim.pred_id)
    if allowance is None:
        return False
    rows = ledger.effective_meta_rows(asrt_id=asrt_id, key=allowance.key)
    if not rows:
        return not allowance.absent_ok
    last_value = rows[-1].value
    return not (isinstance(last_value, str) and last_value in allowance.allowed_values)


def is_predicate_premise_blocked(
    ledger: Ledger,
    asrt_id: str,
    blocks_by_pred: Mapping[str, PredicatePremiseBlock],
) -> bool:
    """Per-predicate blocklist — exclude an assertion of a configured predicate
    whose meta ``key`` last-value IS in that predicate's blocked set.

    Default-admit: an assertion of a configured predicate that is MISSING the
    key, or whose last value is not blocked, stays visible (only explicit
    matches are blocked). Assertions of predicates NOT in the map, and
    non-claims (``get_claim`` -> ``None``), are never blocked. An empty map
    never blocks.

    Last-wins per ``(asrt_id, key)`` mirrors the allowance/exclusion logic: only
    the most recent meta row under the key decides, so removing the blocked
    value (or the block config) re-admits the assertion exactly as every read
    path reports it. Cost when configured: one claim lookup, plus one indexed
    meta lookup for assertions of a configured predicate.
    """
    if not blocks_by_pred:
        return False
    claim = ledger.get_claim(asrt_id)
    if claim is None:
        return False
    block = blocks_by_pred.get(claim.pred_id)
    if block is None:
        return False
    rows = ledger.effective_meta_rows(asrt_id=asrt_id, key=block.key)
    if not rows:
        return False
    last_value = rows[-1].value
    return isinstance(last_value, str) and last_value in block.blocked_values


def premise_scoped_ledger(
    ledger: Ledger,
    exclusions: MetaExclusion | Iterable[MetaExclusion] | None,
    allowances: "PredicatePremiseAllowance | Iterable[PredicatePremiseAllowance] | None" = None,
    blocks: "PredicatePremiseBlock | Iterable[PredicatePremiseBlock] | None" = None,
) -> Ledger:
    """Return ``ledger`` unchanged when nothing is configured, else a live filtered view.

    Three orthogonal, OR-combined dimensions: the global ``exclusions`` (hide any
    assertion carrying an excluded meta value, predicate-blind), the
    per-predicate ``allowances`` (for a configured predicate, hide any assertion
    whose class is not allowed) and the per-predicate ``blocks`` (for a
    configured predicate, hide any assertion whose key value IS in the blocked
    set). An assertion is invisible to evaluation when ANY dimension excludes it,
    so neither a global exclusion nor a block is ever undone by an allowance.
    Empty on all three dimensions returns the base ledger object unchanged
    (zero-behaviour-change contract).
    """
    normalized = normalize_premise_exclusions(exclusions)
    normalized_allowances = normalize_premise_allowances(allowances)
    normalized_blocks = normalize_premise_blocks(blocks)
    if not normalized and not normalized_allowances and not normalized_blocks:
        return ledger
    return _PremiseExcludedLedger(
        ledger,
        exclusions=normalized,
        allowances=normalized_allowances,
        blocks=normalized_blocks,
    )


class _PremiseExcludedLedger(Ledger):
    """Read-only Ledger view hiding assertions excluded by MetaExclusion config.

    Visibility is decided LIVE per access through ``is_premise_excluded``
    (the single last-wins visibility logic) — no frozen exclusion set and no
    revocation snapshot: a fact or revoker written or reclassified while an
    evaluation is running is judged the moment it becomes readable, and the
    view/witness projections of one call read through the same wrapper
    object. It owns no sqlite connection (same no-``super().__init__()``
    construction pattern as ``_ViewScopedLedger`` in sdk/store.py) and
    overrides the full read surface so no evaluate or engine-export path can
    see an excluded claim.
    """

    def __init__(
        self,
        base: Ledger,
        *,
        exclusions: tuple[MetaExclusion, ...],
        allowances: tuple[PredicatePremiseAllowance, ...] = (),
        blocks: tuple[PredicatePremiseBlock, ...] = (),
    ) -> None:
        self._base = base
        self._exclusions = exclusions
        self._allowances_by_pred: dict[str, PredicatePremiseAllowance] = {
            allowance.pred_id: allowance for allowance in allowances
        }
        self._blocks_by_pred: dict[str, PredicatePremiseBlock] = {
            block.pred_id: block for block in blocks
        }

    def _is_visible(self, asrt_id: str) -> bool:
        if is_premise_excluded(self._base, asrt_id, self._exclusions):
            return False
        if is_predicate_premise_excluded(
            self._base, asrt_id, self._allowances_by_pred
        ):
            return False
        if is_predicate_premise_blocked(
            self._base, asrt_id, self._blocks_by_pred
        ):
            return False
        return True

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

    def effective_meta_rows(
        self,
        *,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
        as_of: tuple[int, int] | None = None,
    ) -> tuple[MetaRow, ...]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return ()
        rows = self._base.effective_meta_rows(
            asrt_id=asrt_id,
            key=key,
            kind=kind,
            as_of=as_of,
        )
        return tuple(row for row in rows if self._is_visible(row.asrt_id))

    def _latest_meta_event_sequence(self) -> tuple[int, int] | None:
        return self._base._latest_meta_event_sequence()

    def latest_event_sequence(self) -> tuple[int, int] | None:
        return self._base.latest_event_sequence()

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
        first_revoker = self._base.find_revoker(revoked_asrt_id)
        if first_revoker is None:
            return False
        if self._is_visible(first_revoker):
            return True
        return self.find_revoker(revoked_asrt_id) is not None

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        if not self._is_visible(revoked_asrt_id):
            return None
        first_revoker = self._base.find_revoker(revoked_asrt_id)
        if first_revoker is None:
            return None
        if self._is_visible(first_revoker):
            return first_revoker
        # Rare path — the base's first revoker is excluded: fall back to the
        # first VISIBLE revoker in insertion order, scanning base revokes.
        for row in self._base.revokes:
            if row.revoked_asrt_id == revoked_asrt_id and self._is_visible(
                row.revoker_asrt_id
            ):
                return row.revoker_asrt_id
        return None

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
        # An excluded revoker's revocation is invisible to evaluation
        # (symmetric admissibility, see module docstring); this filtered
        # projection is what the souffle export reads.
        return [
            row for row in self._base.revokes if self._is_visible(row.revoker_asrt_id)
        ]

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
    "PredicatePremiseAllowance",
    "PredicatePremiseBlock",
    "is_premise_excluded",
    "is_predicate_premise_excluded",
    "is_predicate_premise_blocked",
    "normalize_premise_exclusions",
    "normalize_premise_allowances",
    "normalize_premise_blocks",
    "validate_premise_configuration",
    "premise_scoped_ledger",
]
