"""Sustainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`. ``contribution_and_governance``
is shared with FAIRness.
"""

from maturity_meter.components.shared import contribution_and_governance

from .activity import development_activity
from .community import inverse_simpson_index
from .issues import issue_close_time, resolved_issue_share

__all__ = [
    "contribution_and_governance",
    "development_activity",
    "inverse_simpson_index",
    "issue_close_time",
    "resolved_issue_share",
]
