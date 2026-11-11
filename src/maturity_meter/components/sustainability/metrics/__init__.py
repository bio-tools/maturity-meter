"""Sustainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`. When several sources measure the
same thing, all of them are combined with :func:`placeholder_reconcile`.
"""

from .activity import days_since_last_commit
from .community import has_contribution_guidelines, inverse_simpson_index
from .issues import avg_issue_close_time_days, num_open_issues

__all__ = [
    "avg_issue_close_time_days",
    "days_since_last_commit",
    "has_contribution_guidelines",
    "inverse_simpson_index",
    "num_open_issues",
]
