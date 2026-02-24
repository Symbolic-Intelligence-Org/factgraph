from __future__ import annotations

import warnings


def install_test_warning_filters() -> None:
    # Narrowly suppress the known evaluate_dummy deprecation noise without
    # hiding unrelated deprecation warnings that should still surface in CI.
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r".*evaluate_dummy.*",
    )


install_test_warning_filters()
