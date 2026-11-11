"""Maintainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`. When several sources measure
the same thing, they are combined with :func:`placeholder_reconcile`.
"""

from .code import avg_ccn, duplicate_rate
from .practices import has_ci_tests, has_no_linting_issues
from .project import has_releases, requirements_specified

__all__ = [
    "avg_ccn",
    "duplicate_rate",
    "has_ci_tests",
    "has_no_linting_issues",
    "has_releases",
    "requirements_specified",
]
