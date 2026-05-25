from __future__ import annotations

from .branch import Branch
from .errors import SDKDSLError
from .application_rule import DSLToApplicationRuleError, build_application_rule
from .expr import Not, Pred, agg_count, agg_max, agg_mean, agg_min, agg_sum
from .rule import Inference, Query, ReturnContractEntry, Rule as Rule, RuleRef
from .vars import vars

# ``Rule`` remains importable from this module for internal legacy tests and
# post-T5 cleanup, but it is no longer an advertised SDK DSL export.
__all__ = [
    "Branch",
    "SDKDSLError",
    "DSLToApplicationRuleError",
    "build_application_rule",
    "vars",
    "RuleRef",
    "Inference",
    "Query",
    "ReturnContractEntry",
    "Pred",
    "Not",
    "agg_count",
    "agg_sum",
    "agg_min",
    "agg_max",
    "agg_mean",
]
