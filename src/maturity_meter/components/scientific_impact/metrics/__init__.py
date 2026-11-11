"""Scientific impact metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the placeholder helpers in
:mod:`maturity_meter.components.utils.scaling`.
"""

from .publications import citation_count, fwci
from .repository import fork_count, star_count

__all__ = [
    "citation_count",
    "fork_count",
    "fwci",
    "star_count",
]
