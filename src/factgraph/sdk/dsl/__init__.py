from __future__ import annotations

from .application_rule import DSLToApplicationRuleError, build_application_rule
from .branch import Case
from .errors import SDKDSLError
from .expr import Not, Pred, agg_count, agg_max, agg_mean, agg_min, agg_sum
from .rule import EmitSpec, Inference, Query, ReturnContractEntry, RuleRef
from .rule import Rule as Rule
from .vars import vars

# ``Rule`` remains importable from this module for internal legacy tests and
# post-T5 cleanup, but it is no longer an advertised SDK DSL export.
__all__ = [
    "Case",
    "DSLToApplicationRuleError",
    "EmitSpec",
    "Inference",
    "Not",
    "Pred",
    "Query",
    "ReturnContractEntry",
    "RuleRef",
    "SDKDSLError",
    "agg_count",
    "agg_max",
    "agg_mean",
    "agg_min",
    "agg_sum",
    "build_application_rule",
    "vars",
]
